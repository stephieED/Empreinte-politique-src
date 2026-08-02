#!/usr/bin/env python3
"""Module documentation in English."""

import argparse
import concurrent.futures
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
        # Translated comment.
        # Translated comment.
        # vers son archive) : on utilise directement l'archive, qui reste servie.
        "https://archive.nossenateurs.fr",
    ],
}

HEADERS = {
    "User-Agent": "candidate-profile-script/0.1 (usage personnel / non commercial)"
}

TIMEOUT = 15

# Translated comment.
# Translated comment.
# Translated comment.
# Translated comment.
# domaines/legislatures disponibles).
AN_OPENDATA_BASE = "https://data.assemblee-nationale.fr/static/openData/repository"
AN_SCRUTINS_ZIP_NAME = {
    "17": "Scrutins.json.zip",
    "16": "Scrutins.json.zip",
    "15": "Scrutins_XV.json.zip",
    "14": "Scrutins_XIV.json.zip",
    # Translated comment.
    # Translated comment.
}
# Association du domaine NosDeputes.fr (celui ou l'identite du parlementaire a
# Translated comment.
LEGISLATURE_BY_BASE_URL = {
    "https://www.nosdeputes.fr": "16",
    "https://2017-2022.nosdeputes.fr": "15",
    "https://2012-2017.nosdeputes.fr": "14",
    "https://2007-2012.nosdeputes.fr": "13",
}
SCRUTINS_CACHE_DIR = Path(".cache") / "scrutins_an"

# Translated comment.
# Translated comment.
# Translated comment.
# 15e (fichier unique nomme par numero romain). Verifie manuellement (HTTP 200)
# Translated comment.
# Translated comment.
AN_AMENDEMENTS_PATH: dict[str, tuple[str, str]] = {
    "17": ("amendements_div_legis", "Amendements.json.zip"),
    "16": ("amendements_div_legis", "Amendements.json.zip"),
    "15": ("amendements_legis", "Amendements_XV.json.zip"),
}
AMENDEMENTS_CACHE_DIR = Path(".cache") / "amendements_an"

# Translated comment.
# multi-legislatures (constate : legislatures 8 a 17 confondues), utilise ici
# Translated comment.
# amendement, ex. "PIONANR5L17B0904") vers son titre lisible (titreDossier.titre).
AN_DOSSIERS_ZIP_URL = f"{AN_OPENDATA_BASE}/17/loi/dossiers_legislatifs/Dossiers_Legislatifs.json.zip"
DOSSIERS_CACHE_DIR = Path(".cache") / "dossiers_an"

# Translated comment.
# Translated comment.
# Translated comment.
# Translated comment.
# (profession/date_naissance/lieu_naissance/uri_hatvp) au-dela de ce que fournit
# Translated comment.
AN_ACTEURS_ZIP_URL = f"{AN_OPENDATA_BASE}/17/amo/deputes_actifs_mandats_actifs_organes/AMO10_deputes_actifs_mandats_actifs_organes.json.zip"
ACTEURS_CACHE_DIR = Path(".cache") / "acteurs_an"

# Translated comment.
# Translated comment.
# Translated comment.
# Translated comment.
# Translated comment.
AN_QUESTIONS_PATH: dict[str, dict[str, tuple[str, str]]] = {
    "17": {
        "QE":   ("questions_ecrites",           "Questions_ecrites.json.zip"),
        "QG":   ("questions_gouvernement",      "Questions_gouvernement.json.zip"),
        "QOSD": ("questions_orales_sans_debat", "Questions_orales_sans_debat.json.zip"),
    },
    "16": {
        "QE":   ("questions_ecrites",           "Questions_ecrites.json.zip"),
        "QG":   ("questions_gouvernement",      "Questions_gouvernement.json.zip"),
        "QOSD": ("questions_orales_sans_debat", "Questions_orales_sans_debat.json.zip"),
    },
    "15": {
        "QE":   ("questions_ecrites",           "Questions_ecrites_XV.json.zip"),
        "QG":   ("questions_gouvernement",      "Questions_gouvernement_XV.json.zip"),
        "QOSD": ("questions_orales_sans_debat", "Questions_orales_sans_debat_XV.json.zip"),
    },
    "14": {
        "QE":   ("questions_ecrites",           "Questions_ecrites_XIV.json.zip"),
        "QG":   ("questions_gouvernement",      "Questions_gouvernement_XIV.json.zip"),
        "QOSD": ("questions_orales_sans_debat", "Questions_orales_sans_debat_XIV.json.zip"),
    },
}
QUESTIONS_CACHE_DIR = Path(".cache") / "questions_an"

# Translated comment.
# Translated comment.
# Translated comment.
# Translated comment.
_SCRUTINS_LOCKS: dict[str, threading.Lock] = {}
_SCRUTINS_LOCKS_META = threading.Lock()

# Translated comment.
_AMENDEMENTS_LOCKS: dict[str, threading.Lock] = {}
_AMENDEMENTS_LOCKS_META = threading.Lock()

# Translated comment.
_QUESTIONS_LOCKS: dict[str, threading.Lock] = {}
_QUESTIONS_LOCKS_META = threading.Lock()

# Translated comment.
# Translated comment.
_DOSSIERS_TITRE_LOCK = threading.Lock()

# Translated comment.
# decoupage par legislature).
_ACTEURS_IDENTITE_LOCK = threading.Lock()

# Translated comment.
# Translated comment.
_DOSSIERS_TEXTES_PORTES_LOCK = threading.Lock()

# Translated comment.
# legislatifs Assemblee nationale) -> nomenclature du schema pivot.
TYPE_RAPPORTEUR_MAP = {
    "rapporteur": "rapporteur_fond",
    "rapporteur pour avis": "rapporteur_avis",
    "rapporteur spécial": "rapporteur_special_budget",
    "rapporteur général": "rapporteur_general",
}

# Translated comment.
# Translated comment.
# Translated comment.
# Translated comment.
# Translated comment.
WARNING_PREFIX_IDENTITE_INTROUVABLE = "identité introuvable"
WARNING_PREFIX_MANDATS_INTROUVABLES = "mandats introuvables"
WARNING_PREFIX_VOTES_INTROUVABLES = "votes introuvables"
WARNING_PREFIX_AMENDEMENTS_INDISPONIBLES = "amendements indisponibles"
WARNING_PREFIX_QUESTIONS_INDISPONIBLES = "questions indisponibles"


def _get_scrutins_lock(legislature: str) -> threading.Lock:
    """English docstring for  get scrutins lock."""with _SCRUTINS_LOCKS_META:
        if legislature not in _SCRUTINS_LOCKS:
            _SCRUTINS_LOCKS[legislature] = threading.Lock()
        return _SCRUTINS_LOCKS[legislature]


def _get_amendements_lock(legislature: str) -> threading.Lock:
    """English docstring for  get amendements lock."""with _AMENDEMENTS_LOCKS_META:
        if legislature not in _AMENDEMENTS_LOCKS:
            _AMENDEMENTS_LOCKS[legislature] = threading.Lock()
        return _AMENDEMENTS_LOCKS[legislature]


def _get_questions_lock(legislature: str) -> threading.Lock:
    """English docstring for  get questions lock."""with _QUESTIONS_LOCKS_META:
        if legislature not in _QUESTIONS_LOCKS:
            _QUESTIONS_LOCKS[legislature] = threading.Lock()
        return _QUESTIONS_LOCKS[legislature]


def _is_empty_payload(value: Any) -> bool:
    """English docstring for  is empty payload."""   if value is None:
        return True
    if isinstance(value, (dict, list, tuple, set)):
        return len(value) == 0
    if isinstance(value, str):
        return value.strip() == ""
    return False


def _extract_parlementaire(identity_raw: Any) -> Optional[dict]:
    """English docstring for  extract parlementaire."""
    if not isinstance(identity_raw, dict):
        return None
    if identity_raw.get("depute") is not None:
        return identity_raw.get("depute")
    if identity_raw.get("senateur") is not None:
        return identity_raw.get("senateur")
    return identity_raw


def _xml_to_data(xml_text: str) -> Optional[Any]:
    """English docstring for  xml to data."""
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
    """English docstring for  get payload."""    try:
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
    """English docstring for  try urls."""    for base_url in urls:
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
    """English docstring for fetch activity synthesis."""rl = f"{base_url}/synthese/data/json"
    print(f"-> Synthèse d'activité : {url}")
    data = _get_payload(url)
    if not isinstance(data, dict):
        return None
    deputes = [item.get("depute") or item for item in (data.get("deputes") or []) if isinstance(item, dict)]
    deputes = [d for d in deputes if isinstance(d, dict)]

    for depute in deputes:
        if depute.get("slug") == slug:
            return depute

    # Translated comment.
    # Translated comment.
    # Translated comment.
    normalized_slug_name = _normalize_search_query(slug.replace("-", " "))
    for depute in deputes:
        nom = depute.get("nom")
        if nom and _normalize_search_query(nom) == normalized_slug_name:
            return depute
    return None


def fetch_dossiers(base_url: str, legislature: str) -> Optional[dict]:
    """English docstring for fetch dossiers.""" url = f"{base_url}/{legislature}/dossiers/nom/json"
    print(f"-> Dossiers législatifs : {url}")
    return _get_payload(url)


def fetch_dossiers_for_legislatures(base_url: str, legislatures: list[str]) -> list[dict[str, Any]]:
    """English docstring for fetch dossiers for legislatures.""" dossiers: list[dict[str, Any]] = []
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
    """English docstring for  normalize search query."""
    decomposed = unicodedata.normalize("NFKD", text)
    without_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    return without_accents.lower()


def fetch_recherche(base_url: str, query: str, object_name: Optional[str] = None, page: int = 1) -> Optional[dict]:
    """English docstring for fetch recherche.""" params = [f"format=json"]
    if object_name:
        params.append(f"object_name={object_name}")
    if page and page > 1:
        params.append(f"page={page}")
    url = f"{base_url}/recherche/{query}?{'&'.join(params)}"
    print(f"-> Recherche API : {url}")
    return _get_payload(url)


def fetch_all_intervention_results(base_url: str, query: str, object_name: str = "Intervention", max_pages: int = 10) -> dict[str, Any]:
    """English docstring for fetch all intervention results.""" aggregated: list[dict[str, Any]] = []
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


def fetch_all_intervention_results_from_domains(
    base_urls: list[str],
    query: str,
    object_name: str = "Intervention",
    max_pages: int = 10,
) -> dict[str, Any]:
    """English docstring for fetch all intervention results from domains."""   if not base_urls:
        return {"results": []}

    normalized_query = _normalize_search_query(query)

    def _fetch_one(base_url: str) -> list[dict[str, Any]]:
        payload = fetch_all_intervention_results(base_url, normalized_query, object_name=object_name, max_pages=max_pages)
        results = payload.get("results") or []
        enriched: list[dict[str, Any]] = []
        for item in results:
            if not isinstance(item, dict):
                continue
            enriched_item = dict(item)
            enriched_item["_search_base_url"] = base_url
            enriched_item["_search_query"] = normalized_query
            enriched_item["_search_object_name"] = object_name
            enriched.append(enriched_item)
        return enriched

    # Translated comment.
    # Translated comment.
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, len(base_urls))) as executor:
        domain_results = list(executor.map(_fetch_one, base_urls))

    merged_results: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for results in domain_results:
        for item in results:
            if not isinstance(item, dict):
                continue
            document_id = item.get("document_id")
            if not document_id:
                continue
            key = str(document_id)
            if key in seen_ids:
                continue
            seen_ids.add(key)
            merged_results.append(item)

    return {"results": merged_results}


def _extract_acteur_ref(url_an_ou_senat: Optional[str]) -> Optional[str]:
    """English docstring for  extract acteur ref."""    if not url_an_ou_senat:
        return None
    match = re.search(r"PA\d+", url_an_ou_senat)
    return match.group(0) if match else None


def _scrutins_json_dir(legislature: str) -> Path:
    return SCRUTINS_CACHE_DIR / legislature / "json"


def _ensure_scrutins_downloaded(legislature: str) -> Optional[Path]:
    """English docstring for  ensure scrutins downloaded."""  json_dir = _scrutins_json_dir(legislature)
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
    """English docstring for  iter votants."""    block = decompte_nominatif.get(list_key)
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
    """English docstring for  build acteur vote index."""
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
    """English docstring for fetch votes officiels."""
    legislature = LEGISLATURE_BY_BASE_URL.get(base_url)
    acteur_ref = _extract_acteur_ref(url_an_ou_senat)
    if not legislature or not acteur_ref:
        return [], None

    index = _build_acteur_vote_index(legislature)
    votes = index.get(acteur_ref, [])
    votes_sorted = sorted(votes, key=lambda v: v.get("date") or "", reverse=True)
    return votes_sorted, legislature


# Type d'auteur (open data amendements) -> type_deposant du schema pivot.
_AMENDEMENT_TYPE_AUTEUR_MAP: dict[str, str] = {
    "Député": "depute",
    "Gouvernement": "gouvernement",
    "Rapporteur": "commission_rapporteur",
    "Commission": "commission_rapporteur",
}

# (etat.libelle, sousEtat.libelle) -> sort du schema pivot. Determine
# Translated comment.
# Translated comment.
# Translated comment.
# Translated comment.
# Translated comment.
# motifs d'irrecevabilite.
_AMENDEMENT_SORT_MAP: dict[tuple[Optional[str], Optional[str]], str] = {
    ("Discuté", "Rejeté"): "rejeté",
    ("Discuté", "Adopté"): "adopté",
    ("Discuté", "Tombé"): "tombé",
    ("Discuté", "Non soutenu"): "non_soutenu",
    ("Discuté", "Retiré"): "retiré",
    ("Retiré", "Retiré après publication"): "retiré",
    ("Retiré", "Retiré avant publication"): "retiré",
}


def _derive_amendement_sort(etat_libelle: Optional[str], sousetat_libelle: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """English docstring for  derive amendement sort."""
    if etat_libelle in ("Irrecevable", "Irrecevable 40"):
        base = "art. 40" if etat_libelle == "Irrecevable 40" else "art. 45"
        return "irrecevable", base
    return _AMENDEMENT_SORT_MAP.get((etat_libelle, sousetat_libelle)), None


def _parse_amendement_entry(data: Any) -> Optional[tuple[str, dict[str, Any]]]:
    """English docstring for  parse amendement entry."""
    amendement = data.get("amendement") if isinstance(data, dict) else None
    if not isinstance(amendement, dict):
        return None

    signataires = amendement.get("signataires") or {}
    auteur = signataires.get("auteur") or {}
    acteur_ref = auteur.get("acteurRef")
    if not isinstance(acteur_ref, str) or not acteur_ref:
        return None

    cosignataires_bloc = signataires.get("cosignataires") or {}
    cosign_refs = cosignataires_bloc.get("acteurRef")
    if isinstance(cosign_refs, str):
        cosign_refs = [cosign_refs]
    elif not isinstance(cosign_refs, list):
        cosign_refs = []

    cycle_de_vie = amendement.get("cycleDeVie") or {}
    etat = cycle_de_vie.get("etatDesTraitements") or {}
    etat_libelle = (etat.get("etat") or {}).get("libelle") if isinstance(etat.get("etat"), dict) else None
    sousetat_libelle = (etat.get("sousEtat") or {}).get("libelle") if isinstance(etat.get("sousEtat"), dict) else None
    sort, base_juridique = _derive_amendement_sort(etat_libelle, sousetat_libelle)

    record = {
        # Translated comment.
        # titre lisible : resolu en titre humain a posteriori si possible, voir
        # fetch_amendements_officiels/_build_texte_titre_index (dossiers legislatifs).
        "texte_vise": amendement.get("texteLegislatifRef"),
        "sort": sort,
        "base_juridique_irrecevabilite": base_juridique,
        # Translated comment.
        # Translated comment.
        # Translated comment.
        "co_signataires": [f"an:{ref}" for ref in cosign_refs if isinstance(ref, str)],
        "type_deposant": _AMENDEMENT_TYPE_AUTEUR_MAP.get(auteur.get("typeAuteur")),
        "date": cycle_de_vie.get("dateDepot"),
        "numero": (amendement.get("identification") or {}).get("numeroLong"),
        "source_url": None,
    }
    return acteur_ref, record


def _amendements_zip_url(legislature: str) -> Optional[str]:
    entry = AN_AMENDEMENTS_PATH.get(legislature)
    if not entry:
        return None
    path_segment, zip_name = entry
    return f"{AN_OPENDATA_BASE}/{legislature}/loi/{path_segment}/{zip_name}"


def _build_acteur_amendement_index(legislature: str) -> dict[str, list[dict[str, Any]]]:
    """English docstring for  build acteur amendement index."""
    with _get_amendements_lock(legislature):
        index_path = AMENDEMENTS_CACHE_DIR / legislature / "index_par_acteur.json"
        if index_path.is_file():
            try:
                with open(index_path, encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass  # cache corrompu : on reconstruit

        url = _amendements_zip_url(legislature)
        if not url:
            return {}

        print(f"-> Téléchargement des amendements officiels (Assemblée nationale) : {url}")
        zip_path = AMENDEMENTS_CACHE_DIR / legislature / "amendements.zip"
        try:
            zip_path.parent.mkdir(parents=True, exist_ok=True)
            with requests.get(url, headers=HEADERS, timeout=(TIMEOUT, 600), stream=True) as resp:
                resp.raise_for_status()
                with open(zip_path, "wb") as out:
                    for chunk in resp.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            out.write(chunk)
        except (requests.RequestException, OSError) as exc:
            print(f"  [!] Échec du téléchargement des amendements officiels : {exc}")
            return {}

        index: dict[str, list[dict[str, Any]]] = {}
        try:
            with zipfile.ZipFile(zip_path) as zf:
                noms = [n for n in zf.namelist() if n.endswith(".json")]
                for nom in noms:
                    try:
                        with zf.open(nom) as f:
                            data = json.load(f)
                    except (json.JSONDecodeError, KeyError):
                        continue
                    parsed = _parse_amendement_entry(data)
                    if parsed is None:
                        continue
                    acteur_ref, record = parsed
                    index.setdefault(acteur_ref, []).append(record)
        except zipfile.BadZipFile as exc:
            print(f"  [!] Archive d'amendements invalide : {exc}")
            return {}

        try:
            index_path.parent.mkdir(parents=True, exist_ok=True)
            with open(index_path, "w", encoding="utf-8") as f:
                json.dump(index, f, ensure_ascii=False)
        except OSError:
            pass

        return index


def _collect_texte_codes(node: Any, codes: set[str]) -> None:
    """English docstring for  collect texte codes."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key in ("texteAssocie", "refTexteAssocie") and isinstance(value, str):
                codes.add(value)
            else:
                _collect_texte_codes(value, codes)
    elif isinstance(node, list):
        for item in node:
            _collect_texte_codes(item, codes)


def _build_texte_titre_index() -> dict[str, str]:
    """English docstring for  build texte titre index."""    with _DOSSIERS_TITRE_LOCK:
        index_path = DOSSIERS_CACHE_DIR / "index_texte_titre.json"
        if index_path.is_file():
            try:
                with open(index_path, encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass  # cache corrompu : on reconstruit

        print(f"-> Téléchargement des dossiers législatifs (Assemblée nationale) : {AN_DOSSIERS_ZIP_URL}")
        zip_path = DOSSIERS_CACHE_DIR / "dossiers.zip"
        try:
            zip_path.parent.mkdir(parents=True, exist_ok=True)
            with requests.get(AN_DOSSIERS_ZIP_URL, headers=HEADERS, timeout=(TIMEOUT, 600), stream=True) as resp:
                resp.raise_for_status()
                with open(zip_path, "wb") as out:
                    for chunk in resp.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            out.write(chunk)
        except (requests.RequestException, OSError) as exc:
            print(f"  [!] Échec du téléchargement des dossiers législatifs : {exc}")
            return {}

        index: dict[str, str] = {}
        try:
            with zipfile.ZipFile(zip_path) as zf:
                noms = [n for n in zf.namelist() if n.startswith("json/dossierParlementaire/") and n.endswith(".json")]
                for nom in noms:
                    try:
                        with zf.open(nom) as f:
                            data = json.load(f)
                    except (json.JSONDecodeError, KeyError):
                        continue
                    dossier = data.get("dossierParlementaire") if isinstance(data, dict) else None
                    if not isinstance(dossier, dict):
                        continue
                    titre = (dossier.get("titreDossier") or {}).get("titre")
                    if not titre:
                        continue
                    codes: set[str] = set()
                    _collect_texte_codes(dossier, codes)
                    for code in codes:
                        index[code] = titre
        except zipfile.BadZipFile as exc:
            print(f"  [!] Archive des dossiers législatifs invalide : {exc}")
            return {}

        try:
            index_path.parent.mkdir(parents=True, exist_ok=True)
            with open(index_path, "w", encoding="utf-8") as f:
                json.dump(index, f, ensure_ascii=False)
        except OSError:
            pass

        return index


# Translated comment.
# Translated comment.
# Translated comment.
_STADE_RANKS = {
    "depose": 1,
    "examine_commission": 2,
    "discute_seance": 3,
    "adopte": 4,
    "promulgue": 5,
}


def _stade_from_code_acte(code_acte: Optional[str], statut_libelle: Optional[str]) -> Optional[str]:
    """English docstring for  stade from code acte."""    if not code_acte:
        return None
    if "PROM" in code_acte:
        return "promulgue"
    if code_acte.endswith("-DEBATS-DEC"):
        if statut_libelle and statut_libelle.strip().lower().startswith("adopt"):
            return "adopte"
        return "discute_seance"
    if "DEBATS" in code_acte:
        return "discute_seance"
    if "COM" in code_acte:
        return "examine_commission"
    if "DEPOT" in code_acte:
        return "depose"
    return None


def _collect_initiateurs(dossier: dict, acteur_roles: dict[str, tuple[str, Optional[str]]]) -> None:
    """English docstring for  collect initiateurs."""
    initiateur = dossier.get("initiateur")
    if not isinstance(initiateur, dict):
        return
    acteurs = (initiateur.get("acteurs") or {}).get("acteur")
    items = acteurs if isinstance(acteurs, list) else [acteurs]
    for item in items:
        if isinstance(item, dict):
            acteur_ref = item.get("acteurRef")
            if isinstance(acteur_ref, str) and acteur_ref:
                acteur_roles.setdefault(acteur_ref, ("auteur", None))


def _collect_dossier_facts(
    node: Any,
    acteur_roles: dict[str, tuple[str, Optional[str]]],
    dates: list[str],
    stades: list[str],
) -> None:
    """English docstring for  collect dossier facts."""    if isinstance(node, dict):
        date_acte = node.get("dateActe")
        if isinstance(date_acte, str) and date_acte:
            dates.append(date_acte[:10])

        code_acte = node.get("codeActe")
        if isinstance(code_acte, str):
            statut = node.get("statutConclusion")
            statut_libelle = statut.get("libelle") if isinstance(statut, dict) else None
            stade = _stade_from_code_acte(code_acte, statut_libelle)
            if stade:
                stades.append(stade)

        rapporteurs = node.get("rapporteurs")
        if isinstance(rapporteurs, dict):
            entries = rapporteurs.get("rapporteur")
            items = [it for it in (entries if isinstance(entries, list) else [entries]) if isinstance(it, dict)]
            role = "co-rapporteur" if len(items) > 1 else "rapporteur"
            for item in items:
                acteur_ref = item.get("acteurRef")
                if isinstance(acteur_ref, str) and acteur_ref:
                    type_rapport = TYPE_RAPPORTEUR_MAP.get((item.get("typeRapporteur") or "").strip().lower())
                    acteur_roles.setdefault(acteur_ref, (role, type_rapport))

        for key, value in node.items():
            if key != "rapporteurs":
                _collect_dossier_facts(value, acteur_roles, dates, stades)
    elif isinstance(node, list):
        for item in node:
            _collect_dossier_facts(item, acteur_roles, dates, stades)


def _collect_acteur_roles(dossier: dict) -> tuple[dict[str, tuple[str, Optional[str]]], Optional[str], Optional[str], Optional[str]]:
    """English docstring for  collect acteur roles."""    acteur_roles: dict[str, tuple[str, Optional[str]]] = {}
    _collect_initiateurs(dossier, acteur_roles)
    dates: list[str] = []
    stades: list[str] = []
    _collect_dossier_facts(dossier.get("actesLegislatifs"), acteur_roles, dates, stades)
    date_min = min(dates) if dates else None
    date_max = max(dates) if dates else None
    stade = max(stades, key=lambda s: _STADE_RANKS[s]) if stades else None
    return acteur_roles, stade, date_min, date_max


def _build_acteur_textes_portes_index() -> dict[str, list[dict[str, Any]]]:
    """English docstring for  build acteur textes portes index."""  with _DOSSIERS_TEXTES_PORTES_LOCK:
        index_path = DOSSIERS_CACHE_DIR / "index_acteur_textes.json"
        if index_path.is_file():
            try:
                with open(index_path, encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass  # cache corrompu : on reconstruit

        zip_path = DOSSIERS_CACHE_DIR / "dossiers.zip"
        if not zip_path.is_file():
            print(f"-> Téléchargement des dossiers législatifs (Assemblée nationale) : {AN_DOSSIERS_ZIP_URL}")
            try:
                zip_path.parent.mkdir(parents=True, exist_ok=True)
                with requests.get(AN_DOSSIERS_ZIP_URL, headers=HEADERS, timeout=(TIMEOUT, 600), stream=True) as resp:
                    resp.raise_for_status()
                    with open(zip_path, "wb") as out:
                        for chunk in resp.iter_content(chunk_size=1024 * 1024):
                            if chunk:
                                out.write(chunk)
            except (requests.RequestException, OSError) as exc:
                print(f"  [!] Échec du téléchargement des dossiers législatifs : {exc}")
                return {}

        index: dict[str, list[dict[str, Any]]] = {}
        try:
            with zipfile.ZipFile(zip_path) as zf:
                noms = [n for n in zf.namelist() if n.startswith("json/dossierParlementaire/") and n.endswith(".json")]
                for nom in noms:
                    try:
                        with zf.open(nom) as f:
                            data = json.load(f)
                    except (json.JSONDecodeError, KeyError):
                        continue
                    dossier = data.get("dossierParlementaire") if isinstance(data, dict) else None
                    if not isinstance(dossier, dict):
                        continue
                    titre_dossier = dossier.get("titreDossier") or {}
                    titre = titre_dossier.get("titre")
                    titre_chemin = titre_dossier.get("titreChemin")
                    if not titre:
                        continue
                    acteur_roles, stade, date_min, date_max = _collect_acteur_roles(dossier)
                    if not acteur_roles:
                        continue
                    legislature = dossier.get("legislature")
                    source_url = (
                        f"https://www.assemblee-nationale.fr/dyn/{legislature}/dossiers/{titre_chemin}"
                        if legislature and titre_chemin else None
                    )
                    for acteur_ref, (role, type_rapport) in acteur_roles.items():
                        index.setdefault(acteur_ref, []).append({
                            "id": dossier.get("uid"),
                            "titre": titre,
                            "role": role,
                            "type_rapport": type_rapport,
                            "stade_procedural": stade,
                            "date_min": date_min,
                            "date_max": date_max,
                            "legislature": legislature,
                            "source_url": source_url,
                        })
        except zipfile.BadZipFile as exc:
            print(f"  [!] Archive des dossiers législatifs invalide : {exc}")
            return {}

        try:
            index_path.parent.mkdir(parents=True, exist_ok=True)
            with open(index_path, "w", encoding="utf-8") as f:
                json.dump(index, f, ensure_ascii=False)
        except OSError:
            pass

        return index


def fetch_textes_portes_officiels(url_an_ou_senat: Optional[str]) -> list[dict[str, Any]]:
    """English docstring for fetch textes portes officiels."""   acteur_ref = _extract_acteur_ref(url_an_ou_senat)
    if not acteur_ref:
        return []
    index = _build_acteur_textes_portes_index()
    entries = index.get(acteur_ref, [])
    return sorted(entries, key=lambda t: (t.get("date_max") or "", t.get("titre") or ""), reverse=True)


def _format_lieu_naissance(ville: Optional[str], departement: Optional[str], pays: Optional[str]) -> Optional[str]:
    """English docstring for  format lieu naissance."""
    if pays and pays != "France":
        complement = pays
    else:
        complement = departement
    if ville and complement:
        return f"{ville} ({complement})"
    return ville or complement or None


def _build_acteur_identite_index() -> dict[str, dict[str, Any]]:
    """English docstring for  build acteur identite index."""   with _ACTEURS_IDENTITE_LOCK:
        index_path = ACTEURS_CACHE_DIR / "index_identite.json"
        if index_path.is_file():
            try:
                with open(index_path, encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass  # cache corrompu : on reconstruit

        print(f"-> Téléchargement des acteurs actifs (Assemblée nationale) : {AN_ACTEURS_ZIP_URL}")
        zip_path = ACTEURS_CACHE_DIR / "acteurs.zip"
        try:
            zip_path.parent.mkdir(parents=True, exist_ok=True)
            with requests.get(AN_ACTEURS_ZIP_URL, headers=HEADERS, timeout=(TIMEOUT, 600), stream=True) as resp:
                resp.raise_for_status()
                with open(zip_path, "wb") as out:
                    for chunk in resp.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            out.write(chunk)
        except (requests.RequestException, OSError) as exc:
            print(f"  [!] Échec du téléchargement des acteurs actifs : {exc}")
            return {}

        index: dict[str, dict[str, Any]] = {}
        try:
            with zipfile.ZipFile(zip_path) as zf:
                noms = [n for n in zf.namelist() if n.startswith("json/acteur/") and n.endswith(".json")]
                for nom in noms:
                    try:
                        with zf.open(nom) as f:
                            data = json.load(f)
                    except (json.JSONDecodeError, KeyError):
                        continue
                    acteur = data.get("acteur") if isinstance(data, dict) else None
                    if not isinstance(acteur, dict):
                        continue
                    uid = acteur.get("uid")
                    acteur_ref = uid.get("#text") if isinstance(uid, dict) else uid
                    if not isinstance(acteur_ref, str) or not acteur_ref:
                        continue

                    etat_civil = acteur.get("etatCivil") or {}
                    info_naissance = etat_civil.get("infoNaissance") or {}
                    profession = (acteur.get("profession") or {}).get("libelleCourant")

                    index[acteur_ref] = {
                        "profession": profession,
                        "date_naissance": info_naissance.get("dateNais"),
                        "lieu_naissance": _format_lieu_naissance(
                            info_naissance.get("villeNais"),
                            info_naissance.get("depNais"),
                            info_naissance.get("paysNais"),
                        ),
                        "uri_hatvp": acteur.get("uri_hatvp"),
                    }
        except zipfile.BadZipFile as exc:
            print(f"  [!] Archive des acteurs actifs invalide : {exc}")
            return {}

        try:
            index_path.parent.mkdir(parents=True, exist_ok=True)
            with open(index_path, "w", encoding="utf-8") as f:
                json.dump(index, f, ensure_ascii=False)
        except OSError:
            pass

        return index


def fetch_identite_officielle(url_an_ou_senat: Optional[str]) -> Optional[dict[str, Any]]:
    """English docstring for fetch identite officielle."""  acteur_ref = _extract_acteur_ref(url_an_ou_senat)
    if not acteur_ref:
        return None
    index = _build_acteur_identite_index()
    return index.get(acteur_ref)


def fetch_amendements_officiels(url_an_ou_senat: Optional[str]) -> list[dict[str, Any]]:
    """English docstring for fetch amendements officiels."""
    acteur_ref = _extract_acteur_ref(url_an_ou_senat)
    if not acteur_ref:
        return []

    amendements: list[dict[str, Any]] = []
    for legislature in AN_AMENDEMENTS_PATH:
        index = _build_acteur_amendement_index(legislature)
        for record in index.get(acteur_ref, []):
            amendements.append({**record, "legislature": legislature})

    if amendements:
        titre_index = _build_texte_titre_index()
        if titre_index:
            for record in amendements:
                titre = titre_index.get(record.get("texte_vise"))
                if titre:
                    record["texte_vise"] = titre

    amendements.sort(key=lambda a: a.get("date") or "", reverse=True)
    return amendements


def _parse_question_entry(data: dict, sous_type: str) -> Optional[tuple[str, dict[str, Any]]]:
    """English docstring for  parse question entry."""
    question = data.get("question")
    if not isinstance(question, dict):
        return None

    auteur = question.get("auteur") or {}
    identite_auteur = auteur.get("identite") or {}
    acteur_ref = identite_auteur.get("acteurRef")
    if not acteur_ref:
        return None

    uid = question.get("uid")

    # Translated comment.
    indexation = question.get("indexationAN") or {}
    analyses = indexation.get("analyses") or {}
    analyse = analyses.get("analyse")
    if isinstance(analyse, list):
        analyse = " ; ".join(str(a) for a in analyse if a)
    elif not isinstance(analyse, str):
        analyse = None

    # Translated comment.
    textes_question = question.get("textesQuestion") or {}
    texte_q_block = textes_question.get("texteQuestion")
    if isinstance(texte_q_block, list):
        texte_q_block = texte_q_block[-1] if texte_q_block else {}
    if not isinstance(texte_q_block, dict):
        texte_q_block = {}
    texte_question = texte_q_block.get("texte") if isinstance(texte_q_block.get("texte"), str) else None
    info_jo_q = texte_q_block.get("infoJO") or {}
    date_question = info_jo_q.get("dateJO") if isinstance(info_jo_q.get("dateJO"), str) else None

    # Translated comment.
    textes_reponse = question.get("textesReponse") or {}
    texte_r_block = textes_reponse.get("texteReponse")
    if isinstance(texte_r_block, list):
        texte_r_block = texte_r_block[-1] if texte_r_block else None
    reponse: Optional[str] = None
    date_reponse: Optional[str] = None
    if isinstance(texte_r_block, dict):
        reponse = texte_r_block.get("texte") if isinstance(texte_r_block.get("texte"), str) else None
        info_jo_r = texte_r_block.get("infoJO") or {}
        date_reponse = info_jo_r.get("dateJO") if isinstance(info_jo_r.get("dateJO"), str) else None

    # Translated comment.
    min_int = question.get("minInt") or {}
    ministere = min_int.get("developpe") if isinstance(min_int.get("developpe"), str) else None

    # Translated comment.
    groupe = auteur.get("groupe") or {}
    groupe_sigle = groupe.get("abrege") if isinstance(groupe.get("abrege"), str) else None

    return acteur_ref, {
        "uid": uid,
        "sous_type": sous_type,
        "sujet": analyse,
        "texte": texte_question,
        "reponse": reponse,
        "ministere": ministere,
        "date": date_question,
        "date_reponse": date_reponse,
        "groupe_sigle": groupe_sigle,
    }


def _build_acteur_questions_index(legislature: str) -> dict[str, list[dict[str, Any]]]:
    """English docstring for  build acteur questions index."""
    with _get_questions_lock(legislature):
        index_path = QUESTIONS_CACHE_DIR / legislature / "index_par_acteur.json"
        if index_path.is_file():
            try:
                with open(index_path, encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass  # cache corrompu : on reconstruit

        question_types = AN_QUESTIONS_PATH.get(legislature)
        if not question_types:
            return {}

        index: dict[str, list[dict[str, Any]]] = {}

        for sous_type, (dossier, fichier) in question_types.items():
            url = f"{AN_OPENDATA_BASE}/{legislature}/questions/{dossier}/{fichier}"
            print(f"-> Téléchargement des questions {sous_type} (Assemblée nationale, législature {legislature}) : {url}")
            zip_path = QUESTIONS_CACHE_DIR / legislature / f"{sous_type.lower()}.zip"
            try:
                zip_path.parent.mkdir(parents=True, exist_ok=True)
                with requests.get(url, headers=HEADERS, timeout=(TIMEOUT, 600), stream=True) as resp:
                    resp.raise_for_status()
                    with open(zip_path, "wb") as out:
                        for chunk in resp.iter_content(chunk_size=1024 * 1024):
                            if chunk:
                                out.write(chunk)
            except (requests.RequestException, OSError) as exc:
                print(f"  [!] Questions {sous_type} législature {legislature} indisponibles : {exc}")
                continue

            try:
                with zipfile.ZipFile(zip_path) as zf:
                    noms = [n for n in zf.namelist() if n.endswith(".json")]
                    for nom in noms:
                        try:
                            with zf.open(nom) as f:
                                data = json.load(f)
                        except (json.JSONDecodeError, KeyError):
                            continue
                        parsed = _parse_question_entry(data, sous_type)
                        if parsed is None:
                            continue
                        acteur_ref, record = parsed
                        index.setdefault(acteur_ref, []).append(record)
            except zipfile.BadZipFile as exc:
                print(f"  [!] Archive de questions {sous_type} législature {legislature} invalide : {exc}")

        try:
            index_path.parent.mkdir(parents=True, exist_ok=True)
            with open(index_path, "w", encoding="utf-8") as f:
                json.dump(index, f, ensure_ascii=False)
        except OSError:
            pass

        return index


def fetch_questions_officielles(url_an_ou_senat: Optional[str]) -> list[dict[str, Any]]:
    """English docstring for fetch questions officielles."""
    acteur_ref = _extract_acteur_ref(url_an_ou_senat)
    if not acteur_ref:
        return []

    questions: list[dict[str, Any]] = []
    for legislature in AN_QUESTIONS_PATH:
        index = _build_acteur_questions_index(legislature)
        for record in index.get(acteur_ref, []):
            uid = record.get("uid") or ""
            source_url = (
                f"https://questions.assemblee-nationale.fr/q{legislature}/{uid}.htm"
                if uid else None
            )
            questions.append({
                "id": f"question_{uid}" if uid else None,
                "date": record.get("date"),
                "type_detail": "question",
                "sous_type": record.get("sous_type"),
                "sujet": record.get("sujet"),
                "texte": record.get("texte"),
                "reponse": record.get("reponse"),
                "date_reponse": record.get("date_reponse"),
                "ministere": record.get("ministere"),
                "groupe_sigle": record.get("groupe_sigle"),
                "fonction": None,
                "format": "prise_de_parole_developpee",
                "mots_cles": [],
                "url": source_url,
                "url_detail": source_url,
                "legislature": legislature,
            })

    questions.sort(key=lambda q: q.get("date") or "", reverse=True)
    return questions


def fetch_votes(base_urls: list[str], slug: str) -> tuple[Optional[list], Optional[str]]:
    """English docstring for fetch votes."""    for base_url in base_urls:
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
    """English docstring for  groupe label."""    if isinstance(groupe_field, dict):
        return groupe_field.get("organisme")
    if isinstance(groupe_field, str):
        return groupe_field
    return None


def _extract_responsabilite_entries(raw_list: Any, categorie: str) -> list[dict[str, Any]]:
    """English docstring for  extract responsabilite entries."""
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
    """English docstring for  extract mandats."""
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

    # Translated comment.
    # Translated comment.
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


# Translated comment.
# Translated comment.
# Translated comment.
# Translated comment.
# Translated comment.
REACTION_COURTE_NB_MOTS_MAX = 15


def _to_int(value: Any) -> Optional[int]:
    """English docstring for  to int."""   if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _classify_intervention_format(nb_mots: Optional[int]) -> Optional[str]:
    """English docstring for  classify intervention format.""" nb_mots is None:
        return None
    return "reaction_courte" if nb_mots <= REACTION_COURTE_NB_MOTS_MAX else "prise_de_parole_developpee"


def fetch_intervention_details(base_url: str, intervention_id: str) -> Optional[dict[str, Any]]:
    """English docstring for fetch intervention details."""l = f"{base_url}/api/document/Intervention/{intervention_id}/json"
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
                    # Translated comment.
                    # Translated comment.
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
                # Translated comment.
                # Translated comment.
                # Translated comment.
                # Translated comment.
                # Translated comment.
                "fonction": intervention.get("fonction") or None,
                "nb_mots": _to_int(intervention.get("nb_mots")),
            }
    return None


def fetch_seance_context(detail: Optional[dict[str, Any]]) -> dict[str, Any]:
    """English docstring for fetch seance context."""   if not detail:
        return {"sujet": None, "mots_cles": []}

    url_detail = detail.get("url") or detail.get("source")
    if not url_detail:
        return {"sujet": None, "mots_cles": []}

    try:
        resp = requests.get(url_detail, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        # Translated comment.
        # Translated comment.
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
    """English docstring for  extract speaker identity from html."""
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
        # Translated comment.
        # Translated comment.
        return None, None

    return None, None


def _classify_intervention(item: dict[str, Any], candidate_name: str, candidate_id: Optional[str]) -> dict[str, Any]:
    """English docstring for  classify intervention."""
    _ = candidate_id  # Translated comment.
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
    # Translated comment.
    # Translated comment.
    # Translated comment.
    slug = _normalize_search_query(candidate_name).replace(" ", "-")

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


def _process_search_result(item: dict[str, Any], base_url: str, candidate_name: str, candidate_id: Optional[str]) -> Optional[dict[str, Any]]:
    """English docstring for  process search result."""
    document_id = item.get("document_id")
    search_base_url = item.get("_search_base_url") or base_url
    detail = None
    if document_id:
        detail = fetch_intervention_details(search_base_url, str(document_id))
    classification = _classify_intervention(detail or {}, candidate_name, candidate_id) if detail else {"mode": "mention", "reason": "detail_indisponible"}
    cleaned = None
    if classification.get("mode") == "prise_de_parole":
        seance_context = fetch_seance_context(detail) if detail else {"sujet": None, "mots_cles": []}
        sujet = seance_context.get("sujet")
        keywords = seance_context.get("mots_cles") or []
        if not sujet:
            sujet = detail.get("type") if detail else None
        nb_mots = detail.get("nb_mots") if detail else None
        cleaned = {
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
            # Translated comment.
            # Translated comment.
            # Translated comment.
            "fonction": detail.get("fonction") if detail else None,
            "nb_mots": nb_mots,
            # "reaction_courte" (interjection) vs "prise_de_parole_developpee",
            # Translated comment.
            # Translated comment.
            "format": _classify_intervention_format(nb_mots),
        }
    time.sleep(0.1)
    return cleaned


def _extract_search_results(base_url: str, search_payload: Optional[dict], candidate_name: str, candidate_id: Optional[str]) -> list[dict[str, Any]]:
    """English docstring for  extract search results."""
    if not isinstance(search_payload, dict):
        return []
    results = [item for item in (search_payload.get("results") or []) if isinstance(item, dict)]
    if not results:
        return []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        processed = list(executor.map(
            lambda item: _process_search_result(item, base_url, candidate_name, candidate_id),
            results,
        ))
    return [item for item in processed if item is not None]



def build_profile(chambre: str, slug: str, intervention_max_pages: int = 10) -> dict:
    """English docstring for build profile."""
    if chambre not in BASE_URLS:
        raise ValueError(f"chambre invalide : {chambre} (attendu: {list(BASE_URLS)})")

    base_urls = BASE_URLS[chambre]

    # Translated comment.
    # Translated comment.
    identity_result = fetch_identity(base_urls, slug)
    if isinstance(identity_result, tuple):
        identity_raw, identity_base_url = identity_result
    else:
        identity_raw = identity_result
        identity_base_url = None

    time.sleep(0.5)  # Translated comment.

    votes_result = fetch_votes(base_urls, slug)
    if isinstance(votes_result, tuple):
        votes_raw, _ = votes_result
    else:
        votes_raw = votes_result

    # Translated comment.
    # Translated comment.
    # Translated comment.
    parlementaire_for_search = None
    if isinstance(identity_raw, dict):
        parlementaire_for_search = _extract_parlementaire(identity_raw)
    search_candidate_name = (
        parlementaire_for_search.get("nom")
        if isinstance(parlementaire_for_search, dict) and parlementaire_for_search.get("nom")
        else slug.replace("-", " ").title()
    )

    # Translated comment.
    # Translated comment.
    synthesis_payload = None
    dossiers_payload = []
    interventions_payload = None
    interventions_base_url = base_urls[0]
    pre_profile_warnings: list[str] = []
    try:
        synthesis_payload = fetch_activity_synthesis(base_urls[0], slug)
        time.sleep(0.3)
        # Translated comment.
        # Translated comment.
        # Translated comment.
        # Translated comment.
        dossiers_base_url = identity_base_url or base_urls[0]
        dossiers_legislatures = (
            [LEGISLATURE_BY_BASE_URL[dossiers_base_url]]
            if dossiers_base_url in LEGISLATURE_BY_BASE_URL
            else ["15", "16"]
        )
        dossiers_payload = fetch_dossiers_for_legislatures(dossiers_base_url, dossiers_legislatures)
        time.sleep(0.3)
        # Translated comment.
        # Translated comment.
        # Translated comment.
        # Translated comment.
        # Translated comment.
        interventions_payload = fetch_all_intervention_results_from_domains(
            base_urls,
            search_candidate_name,
            object_name="Intervention",
            max_pages=intervention_max_pages,
        )
        interventions_base_url = base_urls[0]
    except Exception as exc:
        pre_profile_warnings.append(f"récupération supplémentaire impossible : {exc}")

    # Translated comment.
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
        "amendements": [],
        "interventions": [],
        "meta": {
            "genere_le": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "licence_donnees": "ODbL (Regards Citoyens, à partir de l'Assemblée nationale / Sénat / JO)",
            # Translated comment.
            # Translated comment.
            "synchro_sources": {
                "nosdeputes": None,
                "assemblee_nationale": None,
                "assemblee_nationale_questions": None,
            },
            "warnings": [],
        },
    }

    warnings = profile["meta"]["warnings"]
    warnings.extend(pre_profile_warnings)

    # Translated comment.
    if _is_empty_payload(identity_raw):
        warnings.append(f"{WARNING_PREFIX_IDENTITE_INTROUVABLE} : l'API ne renvoie pas de profil exploitable pour ce slug/chambre.")
    else:
        profile["meta"]["synchro_sources"]["nosdeputes"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        parlementaire = _extract_parlementaire(identity_raw)

        if not isinstance(parlementaire, dict) or _is_empty_payload(parlementaire):
            warnings.append(f"{WARNING_PREFIX_IDENTITE_INTROUVABLE} : la réponse API ne contient pas de données de parlementaire exploitables.")
        else:
            profile["identite"] = {
                "nom_complet": parlementaire.get("nom"),
                "groupe_sigle": parlementaire.get("groupe_sigle"),
                "groupe_nom": parlementaire.get("nom_groupe_politique") or _groupe_label(parlementaire.get("groupe")),
                "profession": parlementaire.get("profession"),
                "date_naissance": parlementaire.get("date_naissance"),
                "lieu_naissance": None,
                "num_circo": parlementaire.get("num_circo") or parlementaire.get("num_deptt"),
                "nb_mandats": parlementaire.get("nb_mandats"),
                "uri_hatvp": None,
                "url_an_ou_senat": parlementaire.get("url_an") or parlementaire.get("url_nosdeputes"),
            }
            profile["mandats"] = _extract_mandats(parlementaire)
            if _is_empty_payload(profile["mandats"]):
                warnings.append(f"{WARNING_PREFIX_MANDATS_INTROUVABLES} : l'API ne renvoie pas de mandats pour ce profil.")

            # Translated comment.
            # Translated comment.
            # Translated comment.
            if chambre == "deputes":
                try:
                    identite_an = fetch_identite_officielle(profile["identite"].get("url_an_ou_senat"))
                except Exception as exc:
                    warnings.append(f"identité officielle (Assemblée nationale) indisponible : {exc}")
                    identite_an = None
                if identite_an:
                    profile["identite"]["profession"] = profile["identite"]["profession"] or identite_an.get("profession")
                    profile["identite"]["date_naissance"] = profile["identite"]["date_naissance"] or identite_an.get("date_naissance")
                    profile["identite"]["lieu_naissance"] = identite_an.get("lieu_naissance")
                    profile["identite"]["uri_hatvp"] = identite_an.get("uri_hatvp")

    # Translated comment.
    # Translated comment.
    # Translated comment.
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
            f"{WARNING_PREFIX_VOTES_INTROUVABLES} : l'endpoint /votes de NosDéputés.fr renvoie une erreur serveur "
            "(fonctionnalité indisponible côté API), et aucune correspondance officielle "
            "Assemblée nationale n'a été trouvée pour ce parlementaire/cette législature."
        )
    else:
        # Translated comment.
        cleaned_votes = []
        votes_payload = votes_raw.get("votes", votes_raw) if isinstance(votes_raw, dict) else votes_raw
        for v in votes_payload:
            if not isinstance(v, dict):
                continue
            scrutin = v.get("vote", v)  # Translated comment.
            cleaned_votes.append({
                "date": scrutin.get("date"),
                "titre": scrutin.get("titre") or scrutin.get("title"),
                "position": scrutin.get("position") or scrutin.get("vote"),
                "numero_scrutin": scrutin.get("numero"),
                "url_source": scrutin.get("url_nosdeputes") or scrutin.get("url"),
            })
        profile["votes"] = cleaned_votes
        if _is_empty_payload(profile["votes"]):
            warnings.append(f"{WARNING_PREFIX_VOTES_INTROUVABLES} : aucune information de scrutin n'a été extraite de la réponse API.")

    # Translated comment.
    # Translated comment.
    if chambre == "deputes" and profile.get("identite"):
        try:
            profile["amendements"] = fetch_amendements_officiels(profile["identite"].get("url_an_ou_senat"))
        except Exception as exc:
            warnings.append(f"{WARNING_PREFIX_AMENDEMENTS_INDISPONIBLES} : {exc}")

    if not _is_empty_payload(synthesis_payload):
        # Translated comment.
        profile["synthese_activite"] = {
            "nom": synthesis_payload.get("nom"),
            "groupe_sigle": synthesis_payload.get("groupe_sigle"),
            "profession": synthesis_payload.get("profession"),
            "nb_mandats": synthesis_payload.get("nb_mandats"),
            "url_an_ou_senat": synthesis_payload.get("url_an") or synthesis_payload.get("url_nosdeputes"),
        }

    if dossiers_payload:
        # Translated comment.
        profile["dossiers_legislatifs"] = sorted(
            dossiers_payload,
            key=lambda item: (item.get("date_max") or "", item.get("titre") or ""),
            reverse=True,
        )

    # Translated comment.
    # Translated comment.
    # Translated comment.
    # Translated comment.
    if chambre == "deputes" and profile.get("identite"):
        try:
            profile["dossiers_legislatifs"] = fetch_textes_portes_officiels(profile["identite"].get("url_an_ou_senat"))
        except Exception as exc:
            warnings.append(f"textes portés officiels (Assemblée nationale) indisponibles : {exc}")

    candidate_name = profile["identite"].get("nom_complet") if profile.get("identite") else slug.replace("-", " ").title()
    candidate_id = None
    if isinstance(identity_raw, dict):
        # --- 9. Interventions : classification prise de parole/mention, format
        # Translated comment.
        parlementaire = _extract_parlementaire(identity_raw)
        if isinstance(parlementaire, dict):
            candidate_id = parlementaire.get("id")
    profile["interventions"] = _extract_search_results(interventions_base_url, interventions_payload, candidate_name, candidate_id)

    # Translated comment.
    # Translated comment.
    # Translated comment.
    if chambre == "deputes" and profile.get("identite"):
        try:
            official_questions = fetch_questions_officielles(profile["identite"].get("url_an_ou_senat"))
            if official_questions:
                profile["interventions"].extend(official_questions)
                profile["meta"]["synchro_sources"]["assemblee_nationale_questions"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        except Exception as exc:
            warnings.append(f"{WARNING_PREFIX_QUESTIONS_INDISPONIBLES} : {exc}")

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
        help="Chemin du fichier JSON de sortie (défaut: raw_data/profiles/<slug>.json)",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=10,
        help="Nombre max. de pages (50 résultats/page) de recherche d'interventions (défaut: 10)",
    )
    args = parser.parse_args()

    profile = build_profile(args.chambre, args.slug, intervention_max_pages=args.max_pages)

    out_path = Path(args.out) if args.out else Path("raw_data/profiles") / f"{args.slug}.json"
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