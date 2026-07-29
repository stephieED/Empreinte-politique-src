#!/usr/bin/env python3
"""
candidate_profile.py

Construit un profil JSON structuré ("CV politique") d'un parlementaire
à partir des données ouvertes de NosDéputés.fr / NosSénateurs.fr
(Regards Citoyens - licence ODbL / CC-BY-SA), complétées par les votes
officiels de l'Assemblée nationale (data.assemblee-nationale.fr).

Usage (depuis la racine du dépôt) :
    python src/candidate_profile.py jean-luc-melenchon --chambre deputes
    python src/candidate_profile.py bruno-retailleau --chambre senateurs
    python src/candidate_profile.py jean-luc-melenchon --chambre deputes --out data/profiles/jean-luc-melenchon.json

Le script ne fait AUCUNE interprétation ni jugement de valeur : il se
contente d'agréger les faits bruts (mandats, responsabilités, votes,
interventions) tels que fournis par les API, avec des liens vers les sources.

Docs API : https://github.com/regardscitoyens/nosdeputes.fr/blob/master/doc/api.md
"""

import argparse
import io
import json
import re
import sys
import threading
import time
import unicodedata
import zipfile
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET

import requests
from bs4 import BeautifulSoup

BASE_URLS = {
    "deputes": [
        "https://www.nosdeputes.fr",
        "https://2017-2022.nosdeputes.fr",
        "https://2012-2017.nosdeputes.fr",
        "https://2007-2012.nosdeputes.fr",
    ],
    "senateurs": [
        # www.nossenateurs.fr a definitivement ferme (le site affiche desormais
        # un message "Le site NosSenateurs.fr est desormais arrete" et redirige
        # vers son archive) : on utilise directement l'archive, qui reste servie.
        "https://archive.nossenateurs.fr",
    ],
}

HEADERS = {
    "User-Agent": "candidate-profile-script/0.1 (usage personnel / non commercial)"
}

TIMEOUT = 15

# Donnees ouvertes officielles de l'Assemblee nationale (scrutins avec detail
# nominatif des votes par depute). Utilisees en remplacement de l'endpoint
# /votes de NosDeputes.fr, qui renvoie systematiquement une erreur HTTP 500
# (verifie y compris sur l'exemple de leur propre documentation, sur tous les
# domaines/legislatures disponibles).
AN_OPENDATA_BASE = "https://data.assemblee-nationale.fr/static/openData/repository"
AN_SCRUTINS_ZIP_NAME = {
    "17": "Scrutins.json.zip",
    "16": "Scrutins.json.zip",
    "15": "Scrutins_XV.json.zip",
    "14": "Scrutins_XIV.json.zip",
    # Pas de donnees ouvertes de scrutins disponibles pour la 13e legislature
    # (2007-2012) sur data.assemblee-nationale.fr.
}
# Association du domaine NosDeputes.fr (celui ou l'identite du parlementaire a
# ete trouvee) a la legislature Assemblee nationale correspondante.
LEGISLATURE_BY_BASE_URL = {
    "https://www.nosdeputes.fr": "16",
    "https://2017-2022.nosdeputes.fr": "15",
    "https://2012-2017.nosdeputes.fr": "14",
    "https://2007-2012.nosdeputes.fr": "13",
}
SCRUTINS_CACHE_DIR = Path(".cache") / "scrutins_an"

# Verrous par législature pour `_build_acteur_vote_index` : plusieurs threads peuvent
# appeler cette fonction simultanément pour des législatures différentes (pas de blocage
# entre eux), mais on sérialise les accès pour une même législature afin d'éviter un
# double téléchargement de l'archive zip et une écriture concurrente du cache disque.
_SCRUTINS_LOCKS: dict[str, threading.Lock] = {}
_SCRUTINS_LOCKS_META = threading.Lock()


def _get_scrutins_lock(legislature: str) -> threading.Lock:
    """Retourne (ou crée) le verrou associé à une législature donnée."""
    with _SCRUTINS_LOCKS_META:
        if legislature not in _SCRUTINS_LOCKS:
            _SCRUTINS_LOCKS[legislature] = threading.Lock()
        return _SCRUTINS_LOCKS[legislature]


def _is_empty_payload(value: Any) -> bool:
    """Vérifie si une valeur de réponse API est vide ou absente."""
    if value is None:
        return True
    if isinstance(value, (dict, list, tuple, set)):
        return len(value) == 0
    if isinstance(value, str):
        return value.strip() == ""
    return False


def _xml_to_data(xml_text: str) -> Optional[Any]:
    """Convertit un XML simple en structure Python de base."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None

    def convert(elem: ET.Element) -> Any:
        children = list(elem)
        if not children:
            return elem.text.strip() if elem.text and elem.text.strip() else None
        result: dict[str, Any] = {}
        for child in children:
            converted = convert(child)
            if child.tag in result:
                if not isinstance(result[child.tag], list):
                    result[child.tag] = [result[child.tag]]
                result[child.tag].append(converted)
            else:
                result[child.tag] = converted
        return result

    return {root.tag: convert(root)}


def _get_payload(url: str) -> Optional[Any]:
    """GET une URL et renvoie un objet Python (JSON ou XML simple), ou None en cas d'échec."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        if "json" in content_type.lower() or resp.text.lstrip().startswith("{"):
            try:
                return resp.json()
            except ValueError as exc:
                print(f"  [!] Réponse JSON invalide depuis {url} : {exc}", file=sys.stderr)
                return None
        if "xml" in content_type.lower() or resp.text.lstrip().startswith("<"):
            parsed = _xml_to_data(resp.text)
            if parsed is not None:
                return parsed
        print(f"  [!] Format de réponse non pris en charge depuis {url}", file=sys.stderr)
        return None
    except requests.RequestException as exc:
        print(f"  [!] Échec de requête sur {url} : {exc}", file=sys.stderr)
        return None


def _try_urls(urls: list[str], label: str, slug: str) -> tuple[Optional[Any], Optional[str]]:
    """Essaie plusieurs URLs jusqu'à trouver un payload exploitable."""
    for base_url in urls:
        for suffix in ["/json", "/xml"]:
            url = f"{base_url}/{slug}{suffix}"
            print(f"-> {label} : {url}")
            data = _get_payload(url)
            if not _is_empty_payload(data):
                return data, base_url
            time.sleep(0.2)
    return None, None


def fetch_identity(base_urls: list[str], slug: str) -> tuple[Optional[Any], Optional[str]]:
    """Infos biographiques, mandats, contacts."""
    return _try_urls(base_urls, "Récupération de l'identité", slug)


def fetch_activity_synthesis(base_url: str, slug: str) -> Optional[dict]:
    """Récupère la synthèse d'activité globale via l'API NosDéputés."""
    url = f"{base_url}/synthese/data/json"
    print(f"-> Synthèse d'activité : {url}")
    data = _get_payload(url)
    if isinstance(data, dict):
        deputes = data.get("deputes") or []
        for item in deputes:
            if isinstance(item, dict):
                depute = item.get("depute") or item
                if isinstance(depute, dict):
                    if depute.get("slug") == slug:
                        return depute
                    if depute.get("nom") and slug.replace("-", " ") in depute.get("nom", "").lower():
                        return depute
    return None


def fetch_dossiers(base_url: str, legislature: str) -> Optional[dict]:
    """Récupère la liste des dossiers législatifs d'une législature."""
    url = f"{base_url}/{legislature}/dossiers/nom/json"
    print(f"-> Dossiers législatifs : {url}")
    return _get_payload(url)


def fetch_dossiers_for_legislatures(base_url: str, legislatures: list[str]) -> list[dict[str, Any]]:
    """Récupère et fusionne les dossiers législatifs pour plusieurs législatures."""
    dossiers: list[dict[str, Any]] = []
    for legislature in legislatures:
        payload = fetch_dossiers(base_url, legislature)
        if not isinstance(payload, dict):
            continue
        sections = payload.get("sections") or []
        for item in sections:
            if not isinstance(item, dict):
                continue
            section = item.get("section") or item
            if isinstance(section, dict):
                dossiers.append({
                    "legislature": legislature,
                    "id": section.get("id"),
                    "titre": section.get("titre"),
                    "date_min": section.get("min_date"),
                    "date_max": section.get("max_date"),
                    "nb_interventions": section.get("nb_interventions"),
                    "url_institution": section.get("url_institution"),
                    "url_source": section.get("url_nosdeputes"),
                })
        time.sleep(0.2)
    return dossiers


def _normalize_search_query(text: str) -> str:
    """Normalise une requête de recherche (minuscules, sans accents).

    Le moteur de recherche de nosdeputes.fr/nossenateurs.fr renvoie parfois 0
    résultat pour une requête multi-mots contenant une majuscule accentuée en
    première position (ex. "Élisabeth Borne" -> 0 résultat), alors que la même
    requête en minuscules et sans accents ("elisabeth borne") renvoie bien les
    résultats attendus. On normalise donc systématiquement la requête envoyée
    à l'API pour éviter ce comportement erratique.
    """
    decomposed = unicodedata.normalize("NFKD", text)
    without_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    return without_accents.lower()


def fetch_recherche(base_url: str, query: str, object_name: Optional[str] = None, page: int = 1) -> Optional[dict]:
    """Récupère les résultats de recherche API pour un terme donné."""
    params = [f"format=json"]
    if object_name:
        params.append(f"object_name={object_name}")
    if page and page > 1:
        params.append(f"page={page}")
    url = f"{base_url}/recherche/{query}?{'&'.join(params)}"
    print(f"-> Recherche API : {url}")
    return _get_payload(url)


def _pick_best_search_base_url(base_urls: list[str], query: str, object_name: str = "Intervention") -> str:
    """Choisit le domaine (législature courante ou archivée) où la recherche renvoie le plus de résultats.

    Un parlementaire dont le mandat s'est terminé lors d'une législature précédente
    (ex. Jean-Luc Mélenchon, mandat clos le 21/06/2022) n'a quasiment aucune
    intervention sur le site de la législature courante : ses interventions réelles
    sont archivées sur le sous-domaine de sa législature (ex. 2017-2022.nosdeputes.fr).
    On sonde donc chaque domaine avec une requête légère (1 page) et on retient celui
    qui a le plus de résultats totaux avant de lancer la recherche complète, coûteuse.
    """
    normalized_query = _normalize_search_query(query)
    best_base_url = base_urls[0]
    best_total = -1
    for base_url in base_urls:
        payload = fetch_recherche(base_url, normalized_query, object_name=object_name, page=1)
        total = payload.get("last_result") if isinstance(payload, dict) else None
        if isinstance(total, int) and total > best_total:
            best_total = total
            best_base_url = base_url
        time.sleep(0.2)
    return best_base_url


def fetch_all_intervention_results(base_url: str, query: str, object_name: str = "Intervention", max_pages: int = 10) -> dict[str, Any]:
    """Agrège les résultats de recherche sur plusieurs pages jusqu'à épuisement ou plafond."""
    aggregated: list[dict[str, Any]] = []
    normalized_query = _normalize_search_query(query)
    for page in range(1, max_pages + 1):
        payload = fetch_recherche(base_url, normalized_query, object_name=object_name, page=page)
        if not isinstance(payload, dict):
            break
        results = payload.get("results") or []
        if not results:
            break
        aggregated.extend(results)
        time.sleep(0.2)
    return {"results": aggregated}


def _extract_acteur_ref(url_an_ou_senat: Optional[str]) -> Optional[str]:
    """Extrait l'identifiant officiel Assemblée nationale (ex: PA2150) depuis une URL de fiche."""
    if not url_an_ou_senat:
        return None
    match = re.search(r"PA\d+", url_an_ou_senat)
    return match.group(0) if match else None


def _scrutins_json_dir(legislature: str) -> Path:
    return SCRUTINS_CACHE_DIR / legislature / "json"


def _ensure_scrutins_downloaded(legislature: str) -> Optional[Path]:
    """Télécharge (avec cache local) l'archive open data des scrutins d'une législature."""
    json_dir = _scrutins_json_dir(legislature)
    if json_dir.is_dir() and any(json_dir.iterdir()):
        return json_dir

    zip_name = AN_SCRUTINS_ZIP_NAME.get(legislature)
    if not zip_name:
        return None

    url = f"{AN_OPENDATA_BASE}/{legislature}/loi/scrutins/{zip_name}"
    print(f"-> Téléchargement des scrutins officiels (Assemblée nationale) : {url}")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=60)
        resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"  [!] Échec du téléchargement des scrutins officiels : {exc}")
        return None

    try:
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            for member in zf.namelist():
                if member.endswith(".json"):
                    zf.extract(member, path=SCRUTINS_CACHE_DIR / legislature)
    except zipfile.BadZipFile as exc:
        print(f"  [!] Archive de scrutins invalide : {exc}")
        return None

    return json_dir if json_dir.is_dir() else None


def _iter_votants(decompte_nominatif: dict, position: str, list_key: str):
    """Parcourt la liste nominative des votants pour une position donnée (pour/contre/...)."""
    block = decompte_nominatif.get(list_key)
    if not isinstance(block, dict):
        return
    votants = block.get("votant")
    if votants is None:
        return
    if isinstance(votants, dict):
        votants = [votants]
    for v in votants:
        if isinstance(v, dict) and v.get("acteurRef"):
            yield v["acteurRef"], position


def _build_acteur_vote_index(legislature: str) -> dict[str, list[dict[str, Any]]]:
    """Construit (et met en cache sur disque) un index acteurRef -> liste de votes.

    Thread-safe : un verrou par législature garantit qu'un seul thread à la fois
    télécharge l'archive et écrit le cache disque pour une législature donnée.
    Des législatures différentes sont traitées indépendamment sans blocage mutuel.
    """
    with _get_scrutins_lock(legislature):
        index_path = SCRUTINS_CACHE_DIR / legislature / "index_par_acteur.json"
        if index_path.is_file():
            try:
                with open(index_path, encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass  # cache corrompu : on reconstruit

        json_dir = _ensure_scrutins_downloaded(legislature)
        if json_dir is None:
            return {}

        index: dict[str, list[dict[str, Any]]] = {}
        fichiers = sorted(json_dir.glob("*.json"))
        print(f"-> Indexation de {len(fichiers)} scrutins officiels (législature {legislature})...")
        for path in fichiers:
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue
            scrutin = data.get("scrutin") or {}
            organe = (scrutin.get("ventilationVotes") or {}).get("organe") or {}
            groupes = (organe.get("groupes") or {}).get("groupe")
            if groupes is None:
                continue
            if isinstance(groupes, dict):
                groupes = [groupes]
            meta = {
                "numero": scrutin.get("numero"),
                "date": scrutin.get("dateScrutin"),
                "titre": scrutin.get("titre"),
                "sort": (scrutin.get("sort") or {}).get("libelle"),
            }
            for groupe in groupes:
                if not isinstance(groupe, dict):
                    continue
                decompte = (groupe.get("vote") or {}).get("decompteNominatif") or {}
                for acteur_ref, position in [
                    *_iter_votants(decompte, "pour", "pours"),
                    *_iter_votants(decompte, "contre", "contres"),
                    *_iter_votants(decompte, "abstention", "abstentions"),
                    *_iter_votants(decompte, "non_votant", "nonVotants"),
                ]:
                    index.setdefault(acteur_ref, []).append({**meta, "position": position})

        try:
            index_path.parent.mkdir(parents=True, exist_ok=True)
            with open(index_path, "w", encoding="utf-8") as f:
                json.dump(index, f, ensure_ascii=False)
        except OSError:
            pass

        return index


def fetch_votes_officiels(base_url: str, url_an_ou_senat: Optional[str]) -> tuple[list[dict[str, Any]], Optional[str]]:
    """Récupère les votes nominatifs officiels d'un député via l'open data de l'Assemblée nationale.

    L'endpoint /votes de NosDéputés.fr est en panne (HTTP 500 systématique,
    y compris sur l'exemple officiel de leur propre documentation, testé sur
    tous les domaines et législatures disponibles). On utilise donc directement
    les données ouvertes de data.assemblee-nationale.fr, qui contiennent le
    détail nominatif (pour/contre/abstention/non-votant) de chaque scrutin,
    identifié par l'acteurRef (ex: PA2150) du parlementaire.
    """
    legislature = LEGISLATURE_BY_BASE_URL.get(base_url)
    acteur_ref = _extract_acteur_ref(url_an_ou_senat)
    if not legislature or not acteur_ref:
        return [], None

    index = _build_acteur_vote_index(legislature)
    votes = index.get(acteur_ref, [])
    votes_sorted = sorted(votes, key=lambda v: v.get("date") or "", reverse=True)
    return votes_sorted, legislature


def fetch_votes(base_urls: list[str], slug: str) -> tuple[Optional[list], Optional[str]]:
    """Liste des scrutins auxquels le parlementaire a participé, avec sa position."""
    for base_url in base_urls:
        for suffix in ["/votes/json", "/votes/xml"]:
            url = f"{base_url}/{slug}{suffix}"
            print(f"-> Récupération des votes : {url}")
            data = _get_payload(url)
            if data is None:
                continue
            votes = data.get("votes", data) if isinstance(data, dict) else data
            if not _is_empty_payload(votes):
                return votes, base_url
            time.sleep(0.2)
    return None, None


def _groupe_label(groupe_field: Any) -> Optional[str]:
    """Le champ « groupe » de l'API est un dict {organisme, fonction, debut_fonction},
    pas une chaîne : on en extrait le nom du groupe politique."""
    if isinstance(groupe_field, dict):
        return groupe_field.get("organisme")
    if isinstance(groupe_field, str):
        return groupe_field
    return None


def _extract_responsabilite_entries(raw_list: Any, categorie: str) -> list[dict[str, Any]]:
    """Normalise une liste de responsabilités (commissions, missions, groupes d'amitié...)
    telle que fournie par les champs `responsabilites`, `historique_responsabilites`,
    `groupes_parlementaires` ou `responsabilites_extra_parlementaires` de l'API."""
    entries: list[dict[str, Any]] = []
    for raw in raw_list or []:
        if not isinstance(raw, dict):
            continue
        resp = raw.get("responsabilite") if isinstance(raw.get("responsabilite"), dict) else raw
        organisme = resp.get("organisme")
        if not organisme:
            continue
        fin = resp.get("fin_fonction")
        entries.append({
            "categorie": categorie,
            "type": resp.get("fonction") or "membre",
            "label": organisme,
            "debut": resp.get("debut_fonction"),
            "fin": fin,
            "actif": not fin,
        })
    return entries


def _extract_mandats(parlementaire: dict[str, Any]) -> list[dict[str, Any]]:
    """Extrait les responsabilités lisibles (commissions, missions, groupes d'amitié,
    engagements extra-parlementaires) et le mandat électif de base, à partir des
    champs réels renvoyés par l'API NosDéputés.fr / NosSénateurs.fr :
    `responsabilites`, `historique_responsabilites`, `groupes_parlementaires`,
    `responsabilites_extra_parlementaires`.

    Chaque entrée a le format {categorie, type (la fonction : membre/président/
    rapporteur/...), label (le nom de l'organisme), debut, fin, actif}.
    """
    mandats: list[dict[str, Any]] = []

    debut_mandat = parlementaire.get("mandat_debut")
    fin_mandat = parlementaire.get("mandat_fin")
    if debut_mandat or fin_mandat:
        groupe_label = _groupe_label(parlementaire.get("groupe"))
        mandats.append({
            "categorie": "mandat_electif",
            "type": "mandat",
            "label": "Mandat parlementaire" + (f" ({groupe_label})" if groupe_label else ""),
            "debut": debut_mandat,
            "fin": fin_mandat,
            "actif": not fin_mandat,
        })

    mandats.extend(_extract_responsabilite_entries(parlementaire.get("responsabilites"), "commission"))
    mandats.extend(_extract_responsabilite_entries(parlementaire.get("historique_responsabilites"), "commission"))
    mandats.extend(_extract_responsabilite_entries(parlementaire.get("groupes_parlementaires"), "groupe_amitie"))
    mandats.extend(_extract_responsabilite_entries(parlementaire.get("responsabilites_extra_parlementaires"), "extra_parlementaire"))

    # Filets de secours pour d'anciens formats d'API (champs génériques non
    # observés dans les réponses actuelles, mais conservés par prudence).
    if not mandats:
        for raw in parlementaire.get("mandats_generiques", []) or []:
            if isinstance(raw, dict):
                mandats.append({
                    "categorie": "autre",
                    "type": raw.get("type") or "mandat",
                    "label": raw.get("label") or raw.get("nom") or raw.get("description"),
                    "debut": raw.get("debut") or raw.get("date_debut"),
                    "fin": raw.get("fin") or raw.get("date_fin"),
                    "actif": not (raw.get("fin") or raw.get("date_fin")),
                })
            elif isinstance(raw, str):
                mandats.append({"categorie": "autre", "type": "mandat", "label": raw, "actif": True})

    return mandats


# Seuil (en nombre de mots, champ `nb_mots` de l'API) en-deçà duquel une intervention
# est considérée comme une réaction/interjection courte plutôt qu'une prise de parole
# développée. Heuristique ajustable : les interjections observées ("Oh !", "Bravo !",
# "Très bien !", "Mais non !") comptent 2 à 3 mots, tandis qu'une intervention
# construite dépasse largement ce seuil.
REACTION_COURTE_NB_MOTS_MAX = 15


def _to_int(value: Any) -> Optional[int]:
    """Convertit une valeur (souvent une chaîne renvoyée par l'API) en entier, sans lever."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _classify_intervention_format(nb_mots: Optional[int]) -> Optional[str]:
    """Distingue une réaction courte (interjection/exclamation lancée depuis les bancs)
    d'une prise de parole développée, à partir de la longueur de l'intervention.
    Ne remplace pas `classification.mode` (qui identifie l'orateur) : les deux se
    combinent pour répondre à « était-il à la tribune/au micro, ou a-t-il juste réagi ? »."""
    if nb_mots is None:
        return None
    return "reaction_courte" if nb_mots <= REACTION_COURTE_NB_MOTS_MAX else "prise_de_parole_developpee"


def fetch_intervention_details(base_url: str, intervention_id: str) -> Optional[dict[str, Any]]:
    """Récupère les détails d’une intervention via l’API de document."""
    url = f"{base_url}/api/document/Intervention/{intervention_id}/json"
    print(f"-> Détail intervention : {url}")
    data = _get_payload(url)
    if isinstance(data, dict):
        intervention = data.get("intervention") or {}
        if isinstance(intervention, dict):
            speaker_name = None
            speaker_url = None
            url_nosdeputes = intervention.get("url_nosdeputes")
            if url_nosdeputes:
                try:
                    page = requests.get(url_nosdeputes, headers=HEADERS, timeout=TIMEOUT)
                    page.raise_for_status()
                    # Le site ne déclare pas toujours son charset : sans cela, requests
                    # utilise ISO-8859-1 par défaut et corrompt les caractères accentués.
                    page.encoding = page.apparent_encoding or page.encoding
                    anchor_id = urlsplit(url_nosdeputes).fragment or None
                    speaker_name, speaker_url = _extract_speaker_identity_from_html(page.text, anchor_id=anchor_id)
                except requests.RequestException:
                    speaker_name, speaker_url = None, None

            return {
                "id": intervention.get("id"),
                "date": intervention.get("date"),
                "created_at": intervention.get("created_at"),
                "type": intervention.get("type"),
                "source": intervention.get("source"),
                "texte": intervention.get("intervention"),
                "url": url_nosdeputes,
                "parlementaire_id": intervention.get("parlementaire_id"),
                "personnalite_id": intervention.get("personnalite_id"),
                "seance_id": intervention.get("seance_id"),
                "speaker_name": speaker_name,
                "speaker_url": speaker_url,
                # `fonction` est le rôle institutionnel officiel occupé par l'orateur au
                # moment précis de cette intervention (ex. "Première ministre", "Rapporteur",
                # "Président de la commission des lois") : vide pour un simple député sans
                # fonction particulière. `nb_mots` sert de proxy pour distinguer une réaction
                # courte (interjection) d'une prise de parole développée.
                "fonction": intervention.get("fonction") or None,
                "nb_mots": _to_int(intervention.get("nb_mots")),
            }
    return None


def fetch_seance_context(detail: Optional[dict[str, Any]]) -> dict[str, Any]:
    """Enrichit une intervention à partir du contenu HTML de la page de séance, quand la page est accessible."""
    if not detail:
        return {"sujet": None, "mots_cles": []}

    url_detail = detail.get("url") or detail.get("source")
    if not url_detail:
        return {"sujet": None, "mots_cles": []}

    try:
        resp = requests.get(url_detail, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        # Même remarque que pour les pages d'intervention : forcer l'encodage détecté
        # évite le mojibake sur les accents lorsque le serveur ne déclare pas de charset.
        resp.encoding = resp.apparent_encoding or resp.encoding
        html_text = resp.text
    except requests.RequestException:
        return {"sujet": detail.get("type"), "mots_cles": []}

    soup = BeautifulSoup(html_text, "html.parser")

    sujet = None
    keywords: list[str] = []

    summary_block = None
    for node in soup.find_all(["div", "section", "aside"]):
        if not node.get("class"):
            continue
        class_names = " ".join(node.get("class", [])).lower()
        if "orga_dossier" in class_names or "sommaire" in class_names or "summary" in class_names:
            summary_block = node
            break

    if summary_block is None:
        summary_block = soup.find(["div", "section"], string=lambda value: value and "sommaire" in value.lower())

    if summary_block is not None:
        link_candidates = []
        for link in summary_block.find_all("a"):
            text = " ".join(link.get_text(" ", strip=True).split())
            if not text:
                continue
            lowered = text.lower()
            if any(skip in lowered for skip in ["voir le dossier", "retour au sommaire", "permalink", "commentaire", "source"]):
                continue
            if len(text) < 120:
                link_candidates.append(text)
        if link_candidates:
            sujet = link_candidates[0]

    if not sujet:
        summary_candidates: list[str] = []

        for node in soup.find_all(["h1", "h2", "h3", "p", "div", "li", "span"]):
            text = " ".join(node.get_text(" ", strip=True).split())
            if not text:
                continue
            lowered = text.lower()
            if any(marker in lowered for marker in ["résumé de la réunion", "resume de la reunion", "résumé de la séance", "resume de la seance", "résumé de la seance", "résumé"]):
                summary_candidates.append(text)
                continue
            if node.name in {"h2", "h3"} and len(text) < 180 and not re.search(r"(mots clés|mot-clé|source|permalien|commentaires)", lowered):
                summary_candidates.append(text)

        for candidate in summary_candidates:
            cleaned = re.sub(r"^(?:résumé|resume)\s*(?:de la|de la séance|de la reunion|de la seance)?\s*[:\-]?\s*", "", candidate, flags=re.I)
            cleaned = re.sub(r"^(?:réunion|seance|séance|session|table ronde|audition)\s*[:\-]?\s*", "", cleaned, flags=re.I)
            cleaned = cleaned.strip(" :.-")
            if cleaned and len(cleaned) < 220:
                sujet = cleaned
                break

    if not sujet:
        title = soup.title.get_text(" ", strip=True) if soup.title else None
        if title:
            title_parts = re.split(r"\s*-\s*", title, flags=re.I)
            title_candidate = title_parts[0].strip() if title_parts else title
            if title_candidate:
                sujet = title_candidate

    if not sujet:
        sujet = detail.get("type")

    tag_block = soup.find(class_="nuage_de_tags")
    if tag_block:
        text = " ".join(tag_block.get_text(" ", strip=True).split())
        if text:
            parts = [p.strip() for p in re.split(r"[\s,;]+", text) if p.strip()]
            keywords = []
            for p in parts:
                cleaned = re.sub(r"^(?:mots\s+clés|mots\s+cles|mot-clé|mot-cle|mots clés|mots cles|clés|cles)\s*[:\-]?\s*", "", p, flags=re.I)
                cleaned = cleaned.strip(" :.-")
                if cleaned and cleaned.lower() not in {"les", "de", "cette", "réunion", "reunion", "mot", "mots", "clé", "cle"}:
                    keywords.append(cleaned)

    return {"sujet": sujet, "mots_cles": keywords[:8]}


def _extract_speaker_identity_from_html(html_text: Optional[str], anchor_id: Optional[str] = None) -> tuple[Optional[str], Optional[str]]:
    """Extrait le nom et l'URL du profil de l'orateur depuis le HTML d'une intervention.

    Une page de séance contient les interventions de tous les orateurs. Si un
    identifiant d'ancre (ex. "inter_abc123", tiré du fragment #... de l'URL de
    l'intervention) est fourni, on restreint la recherche du bloc div.perso au
    conteneur de CETTE intervention précise, plutôt que de prendre le premier
    div.perso de la page (souvent le/la président·e de séance).
    """
    if not html_text:
        return None, None

    try:
        soup = BeautifulSoup(html_text, "html.parser")
    except Exception:
        return None, None

    scope = soup
    restrict_to_scope = False
    if anchor_id:
        anchor = soup.find(id=anchor_id) or soup.find(attrs={"name": anchor_id})
        if anchor is not None:
            classes = anchor.get("class") or []
            container = anchor if "intervention" in classes else anchor.find_parent(class_="intervention")
            scope = container or anchor
            restrict_to_scope = True

    for container in scope.select("div.perso"):
        text = " ".join(container.get_text(" ", strip=True).split())
        if text and len(text) < 220:
            for link in container.find_all("a"):
                href = link.get("href")
                if href:
                    return text, href
            return text, None

    if restrict_to_scope:
        # On ne remonte pas à l'orateur d'une autre intervention de la page :
        # mieux vaut ne rien renvoyer que d'attribuer la mauvaise identité.
        return None, None

    return None, None


def _classify_intervention(item: dict[str, Any], candidate_name: str, candidate_id: Optional[str]) -> dict[str, Any]:
    """Classe une intervention en prise de parole uniquement via l'orateur du bloc div.perso."""
    _ = candidate_id  # Conservé pour compatibilité de signature.
    structured_speaker = item.get("speaker_name") or item.get("speaker") or item.get("orateur")
    speaker_url = item.get("speaker_url") or item.get("speaker_href")
    if not structured_speaker and not speaker_url:
        html_payload = item.get("html")
        if html_payload:
            structured_speaker, speaker_url = _extract_speaker_identity_from_html(str(html_payload))

    if not structured_speaker and not speaker_url:
        return {
            "mode": "mention",
            "reason": "orateur_bloc_perso_introuvable",
        }

    candidate_name_lower = candidate_name.lower()
    speaker_lower = (structured_speaker or "").lower()
    speaker_url_lower = (speaker_url or "").lower()
    slug = candidate_name_lower.replace(" ", "-")

    if slug and slug in speaker_url_lower:
        return {
            "mode": "prise_de_parole",
            "reason": "orateur_bloc_perso_url_correspondante",
        }

    if structured_speaker and candidate_name_lower in speaker_lower:
        return {
            "mode": "prise_de_parole",
            "reason": "orateur_bloc_perso_nom_correspondant",
        }

    return {
        "mode": "mention",
        "reason": "orateur_bloc_perso_non_correspondant",
    }


def _extract_search_results(base_url: str, search_payload: Optional[dict], candidate_name: str, candidate_id: Optional[str]) -> list[dict[str, Any]]:
    """Normalise les résultats de recherche API et enrichit chaque intervention avec un détail."""
    if not isinstance(search_payload, dict):
        return []
    results = search_payload.get("results") or []
    cleaned: list[dict[str, Any]] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        document_id = item.get("document_id")
        detail = None
        if document_id:
            detail = fetch_intervention_details(base_url, str(document_id))
        classification = _classify_intervention(detail or {}, candidate_name, candidate_id) if detail else {"mode": "mention", "reason": "detail_indisponible"}
        if classification.get("mode") == "prise_de_parole":
            seance_context = fetch_seance_context(detail) if detail else {"sujet": None, "mots_cles": []}
            sujet = seance_context.get("sujet")
            keywords = seance_context.get("mots_cles") or []
            if not sujet:
                sujet = detail.get("type") if detail else None
            nb_mots = detail.get("nb_mots") if detail else None
            cleaned.append({
                "type": item.get("document_type"),
                "id": document_id,
                "url": item.get("document_url"),
                "date": detail.get("date") if detail else None,
                "created_at": detail.get("created_at") if detail else None,
                "type_detail": detail.get("type") if detail else None,
                "source": detail.get("source") if detail else None,
                "texte": detail.get("texte") if detail else None,
                "url_detail": detail.get("url") if detail else None,
                "classification": classification,
                "sujet": sujet,
                "mots_cles": keywords,
                # Rôle institutionnel occupé au moment de l'intervention (ex. "Ministre
                # de l'Intérieur", "Rapporteur") : vide si simple parlementaire sans
                # fonction particulière à cet instant.
                "fonction": detail.get("fonction") if detail else None,
                "nb_mots": nb_mots,
                # "reaction_courte" (interjection) vs "prise_de_parole_developpee",
                # dérivé de nb_mots : permet de distinguer une réaction lancée depuis
                # les bancs d'une véritable prise de parole à la tribune/au micro.
                "format": _classify_intervention_format(nb_mots),
            })
        time.sleep(0.1)
    return cleaned


def build_profile(chambre: str, slug: str, intervention_max_pages: int = 10) -> dict:
    """Construit le profil complet d'un parlementaire (identité, mandats/responsabilités,
    votes, dossiers législatifs, interventions) en enchaînant les appels aux différentes
    sources de données (NosDéputés.fr / NosSénateurs.fr + open data Assemblée nationale).

    Aucune source indisponible ne fait échouer l'appel : chaque section manquante reste
    simplement vide, avec un message explicatif ajouté à `profile["meta"]["warnings"]`.

    Args:
        chambre: "deputes" ou "senateurs".
        slug: identifiant NosDéputés.fr / NosSénateurs.fr du parlementaire
            (ex. "jean-luc-melenchon").
        intervention_max_pages: nombre max. de pages de résultats de recherche
            d'interventions à parcourir (chaque page = jusqu'à 50 résultats, chacun
            nécessitant une requête de détail supplémentaire : réduire ce nombre accélère
            fortement la génération d'un profil, au prix d'une couverture moins complète).

    Returns:
        Le dict de profil, sérialisable en JSON tel quel.
    """
    if chambre not in BASE_URLS:
        raise ValueError(f"chambre invalide : {chambre} (attendu: {list(BASE_URLS)})")

    base_urls = BASE_URLS[chambre]

    # --- 1. Identité brute + votes bruts (fallback nosdeputes.fr, souvent indisponible
    # côté votes : cf. fetch_votes_officiels plus bas pour la source qui fonctionne). ---
    identity_result = fetch_identity(base_urls, slug)
    if isinstance(identity_result, tuple):
        identity_raw, identity_base_url = identity_result
    else:
        identity_raw = identity_result
        identity_base_url = None

    time.sleep(0.5)  # on reste courtois avec l'API publique

    votes_result = fetch_votes(base_urls, slug)
    if isinstance(votes_result, tuple):
        votes_raw, _ = votes_result
    else:
        votes_raw = votes_result

    # --- 2. Nom de recherche fiable, dérivé de l'identité, pour l'API de recherche
    # d'interventions : un slug transformé en espaces (ex. "jean luc melenchon")
    # ne renvoie souvent aucun résultat, contrairement au nom complet. ---
    parlementaire_for_search = None
    if isinstance(identity_raw, dict):
        parlementaire_for_search = (
            identity_raw.get("depute")
            if identity_raw.get("depute") is not None
            else identity_raw.get("senateur")
            if identity_raw.get("senateur") is not None
            else identity_raw
        )
    search_candidate_name = (
        parlementaire_for_search.get("nom")
        if isinstance(parlementaire_for_search, dict) and parlementaire_for_search.get("nom")
        else slug.replace("-", " ").title()
    )

    # --- 3. Synthèse d'activité, dossiers législatifs, et recherche des interventions
    # (sur le meilleur domaine/législature disponible). ---
    synthesis_payload = None
    dossiers_payload = []
    interventions_payload = None
    interventions_base_url = base_urls[0]
    pre_profile_warnings: list[str] = []
    try:
        synthesis_payload = fetch_activity_synthesis(base_urls[0], slug)
        time.sleep(0.3)
        dossiers_payload = fetch_dossiers_for_legislatures(base_urls[0], ["15", "16"])
        time.sleep(0.3)
        # Un parlementaire dont le mandat s'est terminé lors d'une législature
        # précédente (mandat clos) n'a quasiment aucune intervention sur le site de
        # la législature courante : ses interventions réelles sont archivées sur le
        # sous-domaine de sa législature. On sonde donc tous les domaines disponibles
        # pour trouver celui qui contient réellement ses interventions.
        interventions_base_url = _pick_best_search_base_url(base_urls, search_candidate_name, object_name="Intervention")
        interventions_payload = fetch_all_intervention_results(
            interventions_base_url, search_candidate_name, object_name="Intervention", max_pages=intervention_max_pages
        )
    except Exception as exc:
        pre_profile_warnings.append(f"récupération supplémentaire impossible : {exc}")

    # --- 4. Structure de base du profil, valeurs par défaut si une source manque. ---
    profile: dict[str, Any] = {
        "slug": slug,
        "chambre": chambre,
        "source": f"{identity_base_url or base_urls[0]}/{slug}",
        "identite": None,
        "mandats": [],
        "votes": [],
        "votes_source": None,
        "synthese_activite": None,
        "dossiers_legislatifs": [],
        "interventions": [],
        "meta": {
            "genere_le": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "licence_donnees": "ODbL (Regards Citoyens, à partir de l'Assemblée nationale / Sénat / JO)",
            # Traçabilité de fraîcheur : horodatage ISO-8601 de la dernière synchro
            # réussie pour chaque source (None = source non contactée ou indisponible).
            "synchro_sources": {
                "nosdeputes": None,
                "assemblee_nationale": None,
            },
            "warnings": [],
        },
    }

    warnings = profile["meta"]["warnings"]
    warnings.extend(pre_profile_warnings)

    # --- 5. Identité + mandats/responsabilités (commissions, missions, groupes d'amitié...). ---
    if _is_empty_payload(identity_raw):
        warnings.append("identité introuvable : l'API ne renvoie pas de profil exploitable pour ce slug/chambre.")
    else:
        profile["meta"]["synchro_sources"]["nosdeputes"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        # La clé racine varie selon l'endpoint ("depute" ou "senateur")
        parlementaire = (
            identity_raw.get("depute")
            if isinstance(identity_raw, dict) and identity_raw.get("depute") is not None
            else identity_raw.get("senateur")
            if isinstance(identity_raw, dict) and identity_raw.get("senateur") is not None
            else identity_raw
        )

        if not isinstance(parlementaire, dict) or _is_empty_payload(parlementaire):
            warnings.append("identité introuvable : la réponse API ne contient pas de données de parlementaire exploitables.")
        else:
            profile["identite"] = {
                "nom_complet": parlementaire.get("nom"),
                "groupe_sigle": parlementaire.get("groupe_sigle"),
                "groupe_nom": parlementaire.get("nom_groupe_politique") or _groupe_label(parlementaire.get("groupe")),
                "profession": parlementaire.get("profession"),
                "date_naissance": parlementaire.get("date_naissance"),
                "num_circo": parlementaire.get("num_circo") or parlementaire.get("num_deptt"),
                "nb_mandats": parlementaire.get("nb_mandats"),
                "url_an_ou_senat": parlementaire.get("url_an") or parlementaire.get("url_nosdeputes"),
            }
            profile["mandats"] = _extract_mandats(parlementaire)
            if _is_empty_payload(profile["mandats"]):
                warnings.append("mandats introuvables : l'API ne renvoie pas de mandats pour ce profil.")

    # --- 6. Votes : on privilégie l'open data officiel de l'Assemblée nationale
    # (fiable et à jour), et on ne retombe sur les champs bruts de nosdeputes.fr
    # (souvent en erreur côté serveur, cf. fetch_votes) que s'il n'y a pas de
    # correspondance officielle. ---
    official_votes: list[dict[str, Any]] = []
    if chambre == "deputes" and profile.get("identite"):
        try:
            official_votes, official_legislature = fetch_votes_officiels(
                identity_base_url or base_urls[0], profile["identite"].get("url_an_ou_senat")
            )
        except Exception as exc:
            warnings.append(f"votes officiels (Assemblée nationale) indisponibles : {exc}")
            official_legislature = None
    else:
        official_legislature = None

    if official_votes:
        profile["votes"] = [
            {
                "date": v.get("date"),
                "titre": v.get("titre"),
                "position": v.get("position"),
                "numero_scrutin": v.get("numero"),
                "sort": v.get("sort"),
            }
            for v in official_votes
        ]
        profile["votes_source"] = (
            f"open data Assemblée nationale (data.assemblee-nationale.fr, législature {official_legislature})"
        )
        profile["meta"]["synchro_sources"]["assemblee_nationale"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    elif _is_empty_payload(votes_raw):
        warnings.append(
            "votes introuvables : l'endpoint /votes de NosDéputés.fr renvoie une erreur serveur "
            "(fonctionnalité indisponible côté API), et aucune correspondance officielle "
            "Assemblée nationale n'a été trouvée pour ce parlementaire/cette législature."
        )
    else:
        # On garde uniquement les champs utiles à un affichage type "CV"
        cleaned_votes = []
        votes_payload = votes_raw.get("votes", votes_raw) if isinstance(votes_raw, dict) else votes_raw
        for v in votes_payload:
            if not isinstance(v, dict):
                continue
            scrutin = v.get("vote", v)  # certaines réponses imbriquent sous "vote"
            cleaned_votes.append({
                "date": scrutin.get("date"),
                "titre": scrutin.get("titre") or scrutin.get("title"),
                "position": scrutin.get("position") or scrutin.get("vote"),
                "numero_scrutin": scrutin.get("numero"),
                "url_source": scrutin.get("url_nosdeputes") or scrutin.get("url"),
            })
        profile["votes"] = cleaned_votes
        if _is_empty_payload(profile["votes"]):
            warnings.append("votes introuvables : aucune information de scrutin n'a été extraite de la réponse API.")

    if not _is_empty_payload(synthesis_payload):
        # --- 7. Synthèse d'activité globale (indicateurs agrégés fournis par l'API). ---
        profile["synthese_activite"] = {
            "nom": synthesis_payload.get("nom"),
            "groupe_sigle": synthesis_payload.get("groupe_sigle"),
            "profession": synthesis_payload.get("profession"),
            "nb_mandats": synthesis_payload.get("nb_mandats"),
            "url_an_ou_senat": synthesis_payload.get("url_an") or synthesis_payload.get("url_nosdeputes"),
        }

    if dossiers_payload:
        # --- 8. Dossiers législatifs, triés du plus récent au plus ancien. ---
        profile["dossiers_legislatifs"] = sorted(
            dossiers_payload,
            key=lambda item: (item.get("date_max") or "", item.get("titre") or ""),
            reverse=True,
        )

    candidate_name = profile["identite"].get("nom_complet") if profile.get("identite") else slug.replace("-", " ").title()
    candidate_id = None
    if isinstance(identity_raw, dict):
        # --- 9. Interventions : classification prise de parole/mention, format
        # (réaction courte / prise de parole développée), fonction occupée, etc. ---
        parlementaire = (
            identity_raw.get("depute")
            if isinstance(identity_raw, dict) and identity_raw.get("depute") is not None
            else identity_raw.get("senateur")
            if isinstance(identity_raw, dict) and identity_raw.get("senateur") is not None
            else identity_raw
        )
        if isinstance(parlementaire, dict):
            candidate_id = parlementaire.get("id")
    profile["interventions"] = _extract_search_results(interventions_base_url, interventions_payload, candidate_name, candidate_id)

    return profile


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("slug", help="Identifiant du parlementaire, ex: jean-luc-melenchon")
    parser.add_argument(
        "--chambre",
        choices=["deputes", "senateurs"],
        default="deputes",
        help="Chambre concernée (défaut: deputes)",
    )
    parser.add_argument(
        "--out",
        help="Chemin du fichier JSON de sortie (défaut: data/profiles/<slug>.json)",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=10,
        help="Nombre max. de pages (50 résultats/page) de recherche d'interventions (défaut: 10)",
    )
    args = parser.parse_args()

    profile = build_profile(args.chambre, args.slug, intervention_max_pages=args.max_pages)

    out_path = Path(args.out) if args.out else Path("data/profiles") / f"{args.slug}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)

    nb_votes = len(profile["votes"])
    print(f"\n✓ Profil écrit dans {out_path}")
    print(f"  - Identité récupérée : {'oui' if profile['identite'] else 'non'}")
    print(f"  - Votes récupérés : {nb_votes}")
    if profile["meta"].get("warnings"):
        print("  [!] " + " | ".join(profile["meta"]["warnings"]))
    elif nb_votes == 0:
        print("  [!] Aucun vote récupéré : vérifie le slug, la chambre, ou la structure JSON renvoyée par l'API (peut avoir changé).")


if __name__ == "__main__":
    main()