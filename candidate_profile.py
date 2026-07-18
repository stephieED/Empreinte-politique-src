#!/usr/bin/env python3
"""
candidate_profile.py

Construit un profil JSON structuré ("CV politique") d'un parlementaire
à partir des données ouvertes de NosDéputés.fr / NosSénateurs.fr
(Regards Citoyens - licence ODbL / CC-BY-SA).

Usage :
    python candidate_profile.py jean-luc-melenchon --chambre deputes
    python candidate_profile.py bruno-retailleau --chambre senateurs
    python candidate_profile.py jean-luc-melenchon --chambre deputes --out melenchon.json

Le script ne fait AUCUNE interprétation ni jugement de valeur : il se
contente d'agréger les faits bruts (mandats, votes, indicateurs
d'activité) tels que fournis par l'API, avec des liens vers les sources.

Docs API : https://github.com/regardscitoyens/nosdeputes.fr/blob/master/doc/api.md
"""

import argparse
import json
import sys
import time
from typing import Any, Optional
from xml.etree import ElementTree as ET

import requests

BASE_URLS = {
    "deputes": [
        "https://www.nosdeputes.fr",
        "https://2017-2022.nosdeputes.fr",
        "https://2012-2017.nosdeputes.fr",
        "https://2007-2012.nosdeputes.fr",
    ],
    "senateurs": [
        "https://www.nossenateurs.fr",
    ],
}

HEADERS = {
    "User-Agent": "candidate-profile-script/0.1 (usage personnel / non commercial)"
}

TIMEOUT = 15


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


def fetch_recherche(base_url: str, query: str, object_name: Optional[str] = None, limit: int = 5) -> Optional[dict]:
    """Récupère les résultats de recherche API pour un terme donné."""
    params = [f"format=json"]
    if object_name:
        params.append(f"object_name={object_name}")
    url = f"{base_url}/recherche/{query}?{'&'.join(params)}"
    print(f"-> Recherche API : {url}")
    return _get_payload(url)


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


def _extract_mandats(parlementaire: dict[str, Any]) -> list[dict[str, Any]]:
    """Tente d'extraire des mandats lisibles à partir des champs fournis par l'API."""
    mandats: list[dict[str, Any]] = []

    for raw in parlementaire.get("mandats", []) or []:
        if isinstance(raw, dict):
            mandats.append({
                "type": raw.get("type") or "mandat",
                "label": raw.get("label") or raw.get("nom") or raw.get("description"),
                "debut": raw.get("debut") or raw.get("date_debut"),
                "fin": raw.get("fin") or raw.get("date_fin"),
            })
        elif isinstance(raw, str):
            mandats.append({"type": "mandat", "label": raw})

    if not mandats:
        for raw in parlementaire.get("anciens_mandats", []) or []:
            if isinstance(raw, dict):
                mandats.append({
                    "type": "ancien_mandat",
                    "label": raw.get("mandat") or raw.get("label") or raw.get("description"),
                })
            elif isinstance(raw, str):
                mandats.append({"type": "ancien_mandat", "label": raw})

    if not mandats:
        for raw in parlementaire.get("autres_mandats", []) or []:
            if isinstance(raw, dict):
                mandats.append({
                    "type": "autre_mandat",
                    "label": raw.get("mandat") or raw.get("label") or raw.get("description"),
                })
            elif isinstance(raw, str):
                mandats.append({"type": "autre_mandat", "label": raw})

    if not mandats:
        debut = parlementaire.get("mandat_debut")
        fin = parlementaire.get("mandat_fin")
        if debut or fin:
            mandats.append({
                "type": "mandat_depute",
                "label": "Mandat de député",
                "debut": debut,
                "fin": fin,
                "groupe": parlementaire.get("groupe", {}).get("organisme") if isinstance(parlementaire.get("groupe"), dict) else None,
            })

    return mandats


def _extract_search_results(search_payload: Optional[dict]) -> list[dict[str, Any]]:
    """Normalise les résultats de recherche API en une liste compacte."""
    if not isinstance(search_payload, dict):
        return []
    results = search_payload.get("results") or []
    cleaned: list[dict[str, Any]] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        cleaned.append({
            "type": item.get("document_type"),
            "id": item.get("document_id"),
            "url": item.get("document_url"),
        })
    return cleaned


def build_profile(chambre: str, slug: str) -> dict:
    if chambre not in BASE_URLS:
        raise ValueError(f"chambre invalide : {chambre} (attendu: {list(BASE_URLS)})")

    base_urls = BASE_URLS[chambre]

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

    synthesis_payload = None
    dossiers_payload = None
    interventions_payload = None
    try:
        synthesis_payload = fetch_activity_synthesis(base_urls[0], slug)
        time.sleep(0.3)
        dossiers_payload = fetch_dossiers(base_urls[0], "15")
        time.sleep(0.3)
        interventions_payload = fetch_recherche(base_urls[0], slug.replace("-", " "), object_name="Intervention", limit=5)
    except Exception as exc:
        warnings.append(f"récupération supplémentaire impossible : {exc}")

    profile: dict[str, Any] = {
        "slug": slug,
        "chambre": chambre,
        "source": f"{identity_base_url or base_urls[0]}/{slug}",
        "identite": None,
        "mandats": [],
        "votes": [],
        "synthese_activite": None,
        "dossiers_legislatifs": [],
        "interventions": [],
        "meta": {
            "genere_le": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "licence_donnees": "ODbL (Regards Citoyens, à partir de l'Assemblée nationale / Sénat / JO)",
            "warnings": [],
        },
    }

    warnings = profile["meta"]["warnings"]

    if _is_empty_payload(identity_raw):
        warnings.append("identité introuvable : l'API ne renvoie pas de profil exploitable pour ce slug/chambre.")
    else:
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
                "groupe_nom": parlementaire.get("nom_groupe_politique") or parlementaire.get("groupe"),
                "profession": parlementaire.get("profession"),
                "date_naissance": parlementaire.get("date_naissance"),
                "num_circo": parlementaire.get("num_circo") or parlementaire.get("num_deptt"),
                "nb_mandats": parlementaire.get("nb_mandats"),
                "url_an_ou_senat": parlementaire.get("url_an") or parlementaire.get("url_nosdeputes"),
            }
            profile["mandats"] = _extract_mandats(parlementaire)
            if _is_empty_payload(profile["mandats"]):
                warnings.append("mandats introuvables : l'API ne renvoie pas de mandats pour ce profil.")

    if _is_empty_payload(votes_raw):
        warnings.append("votes introuvables : l'endpoint de votes ne renvoie pas de données exploitables pour ce slug/chambre.")
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
        profile["synthese_activite"] = {
            "nom": synthesis_payload.get("nom"),
            "groupe_sigle": synthesis_payload.get("groupe_sigle"),
            "profession": synthesis_payload.get("profession"),
            "nb_mandats": synthesis_payload.get("nb_mandats"),
            "url_an_ou_senat": synthesis_payload.get("url_an") or synthesis_payload.get("url_nosdeputes"),
        }

    if isinstance(dossiers_payload, dict):
        sections = dossiers_payload.get("sections") or []
        cleaned_dossiers = []
        for item in sections:
            if not isinstance(item, dict):
                continue
            section = item.get("section") or item
            if isinstance(section, dict):
                cleaned_dossiers.append({
                    "id": section.get("id"),
                    "titre": section.get("titre"),
                    "date_min": section.get("min_date"),
                    "date_max": section.get("max_date"),
                    "nb_interventions": section.get("nb_interventions"),
                    "url_institution": section.get("url_institution"),
                    "url_source": section.get("url_nosdeputes"),
                })
        profile["dossiers_legislatifs"] = cleaned_dossiers[:10]

    profile["interventions"] = _extract_search_results(interventions_payload)

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
        help="Chemin du fichier JSON de sortie (défaut: <slug>.json)",
    )
    args = parser.parse_args()

    profile = build_profile(args.chambre, args.slug)

    out_path = args.out or f"{args.slug}.json"
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