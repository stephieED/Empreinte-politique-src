#!/usr/bin/env python3
"""Module documentation in English."""

import argparse
import json
import re
import threading
import time
import unicodedata
from pathlib import Path
from typing import Any, Optional

import requests

EP_API_BASE = "https://data.europarl.europa.eu/api/v2"

# Translated comment.
# Translated comment.
# Translated comment.
HEADERS = {
    "User-Agent": "CV-CandidatFR-dev-1.0.0 (https://github.com/, usage personnel / non commercial)"
}

TIMEOUT = 20
CACHE_DIR = Path(".cache") / "europarl"

# Translated comment.
# Translated comment.
# Translated comment.
# Translated comment.
_ORG_CACHE_LOCK = threading.Lock()

# Translated comment.
# `hasMembership[].membershipClassification` (valeurs brutes = URI de type
# Translated comment.
# Translated comment.
CLASSIFICATION_LABELS = {
    "def/ep-entities/COMMITTEE_PARLIAMENTARY_STANDING": "Commission parlementaire permanente",
    "def/ep-entities/COMMITTEE_PARLIAMENTARY_TEMPORARY": "Commission parlementaire spéciale/temporaire",
    "def/ep-entities/COMMITTEE_PARLIAMENTARY_SUB": "Sous-commission parlementaire",
    "def/ep-entities/DELEGATION_PARLIAMENTARY": "Délégation interparlementaire",
    "def/ep-entities/DELEGATION_PARLIAMENTARY_ASSEMBLY": "Délégation à une assemblée parlementaire",
    "def/ep-entities/WORKING_GROUP": "Groupe de travail",
    "def/ep-entities/EU_POLITICAL_GROUP": "Groupe politique européen",
    "def/ep-entities/NATIONAL_POLITICAL_GROUP": "Parti national (au sein du groupe européen)",
    "def/ep-entities/GOVERNING_BODY": "Organe de direction du Parlement européen",
    "def/ep-entities/EU_INSTITUTION": "Mandat de député européen",
}

# Translated comment.
ROLE_LABELS = {
    "def/ep-roles/MEMBER": "Membre",
    "def/ep-roles/MEMBER_SUBSTITUTE": "Membre suppléant(e)",
    "def/ep-roles/MEMBER_PARLIAMENT": "Membre du Parlement européen",
    "def/ep-roles/CHAIR": "Président(e)",
    "def/ep-roles/CHAIR_CO": "Coprésident(e)",
    "def/ep-roles/VICE_CHAIR": "Vice-président(e)",
    "def/ep-roles/TREASURER": "Trésorier(ère)",
    "def/ep-roles/TREASURER_CO": "Co-trésorier(ère)",
}


def _prettify_uri(value: Optional[str]) -> Optional[str]:
    """English docstring for  prettify uri."""    if not value:
        return None
    tail = value.rsplit("/", 1)[-1]
    return tail.replace("_", " ").capitalize()


def _normalize_name(name: str) -> str:
    """English docstring for  normalize name."""   decomposed = unicodedata.normalize("NFKD", name)
    ascii_only = "".join(c for c in decomposed if not unicodedata.combining(c))
    tokens = re.findall(r"[A-Za-z0-9]+", ascii_only.upper())
    return " ".join(sorted(tokens))


def _get_json(path: str, params: Optional[dict[str, Any]] = None) -> Optional[dict]:
    """English docstring for  get json.""" request_params = {"format": "application/ld+json"}
    if params:
        request_params.update(params)
    response = requests.get(
        f"{EP_API_BASE}{path}", params=request_params, headers=HEADERS, timeout=TIMEOUT
    )
    if response.status_code == 204:
        return None
    response.raise_for_status()
    return response.json()


def fetch_all_meps_by_country(country: str = "FR", use_cache: bool = True) -> list[dict[str, Any]]:
    """English docstring for fetch all meps by country."""
    cache_path = CACHE_DIR / f"meps_{country}.json"
    if use_cache and cache_path.exists():
        with open(cache_path, encoding="utf-8") as f:
            return json.load(f)

    meps: list[dict[str, Any]] = []
    offset = 0
    limit = 100
    while True:
        payload = _get_json(
            "/meps",
            {"country-of-representation": country, "limit": limit, "offset": offset},
        )
        items = (payload or {}).get("data", [])
        if not items:
            break
        meps.extend(items)
        offset += limit
        time.sleep(0.2)  # Translated comment.

    if use_cache:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(meps, f, ensure_ascii=False, indent=2)

    return meps


def find_mep_by_name(nom: str, country: str = "FR", use_cache: bool = True) -> Optional[dict[str, Any]]:
    """English docstring for find mep by name."""
    target = _normalize_name(nom)
    for mep in fetch_all_meps_by_country(country, use_cache=use_cache):
        if _normalize_name(mep.get("label", "")) == target:
            return mep
    return None


def fetch_mep_detail(mep_id: str) -> Optional[dict[str, Any]]:
    """English docstring for fetch mep detail."""
    payload = _get_json(f"/meps/{mep_id}")
    items = (payload or {}).get("data", [])
    return items[0] if items else None


def resolve_organization(org_id: str, cache: dict[str, Any]) -> dict[str, Any]:
    """English docstring for resolve organization."""
    if org_id in cache:
        return cache[org_id]

    identifier = org_id.split("/", 1)[-1]
    resolved: dict[str, Any] = {"sigle": identifier, "nom_complet": None}
    for attempt in range(2):  # Translated comment.
        try:
            payload = _get_json(f"/corporate-bodies/{identifier}")
            items = (payload or {}).get("data", [])
            if items:
                item = items[0]
                resolved["sigle"] = item.get("label") or identifier
                pref_label = item.get("prefLabel") or {}
                alt_label = item.get("altLabel") or {}
                resolved["nom_complet"] = pref_label.get("fr") or alt_label.get("fr") or resolved["sigle"]
            break
        except requests.RequestException:
            if attempt == 0:
                time.sleep(1)
                continue
            pass  # Translated comment.

    time.sleep(0.15)  # Translated comment.
    cache[org_id] = resolved
    return resolved


def _load_org_cache() -> dict[str, Any]:
    cache_path = CACHE_DIR / "organisations.json"
    if cache_path.exists():
        with open(cache_path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_org_cache(cache: dict[str, Any]) -> None:
    cache_path = CACHE_DIR / "organisations.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def _extract_mandats_europeens(mep_detail: dict[str, Any], org_cache: dict[str, Any]) -> list[dict[str, Any]]:
    """English docstring for  extract mandats europeens."""    mandats = []
    for membership in mep_detail.get("hasMembership") or []:
        period = membership.get("memberDuring") or {}
        debut = period.get("startDate")
        fin = period.get("endDate")
        classification = membership.get("membershipClassification")
        org_id = membership.get("organization")

        if org_id and str(org_id).split("/", 1)[-1].startswith("ep-"):
            # Translated comment.
            # Translated comment.
            legislature = str(org_id).split("-", 1)[-1]
            organisation = {"sigle": f"{legislature}e législature", "nom_complet": "Mandat de député européen"}
        else:
            organisation = resolve_organization(org_id, org_cache) if org_id else {"sigle": None, "nom_complet": None}

        mandats.append({
            "type": (classification or "AUTRE").rsplit("/", 1)[-1],
            "type_label": CLASSIFICATION_LABELS.get(classification) or _prettify_uri(classification) or "Autre",
            "organisation_sigle": organisation.get("sigle"),
            "organisation_nom": organisation.get("nom_complet"),
            "role": (membership.get("role") or "").rsplit("/", 1)[-1] or None,
            "role_label": ROLE_LABELS.get(membership.get("role")) or _prettify_uri(membership.get("role")),
            "debut": debut,
            "fin": fin,
            "actif": fin is None,
        })

    mandats.sort(key=lambda m: m.get("debut") or "", reverse=True)
    return mandats


def build_profile_ue(nom: str, country: str = "FR", use_cache: bool = True) -> Optional[dict[str, Any]]:
    """English docstring for build profile ue."""
    mep_entry = find_mep_by_name(nom, country=country, use_cache=use_cache)
    if mep_entry is None:
        return None

    mep_id = mep_entry.get("identifier")
    detail = fetch_mep_detail(mep_id) or mep_entry

    # Translated comment.
    # Translated comment.
    with _ORG_CACHE_LOCK:
        org_cache = dict(_load_org_cache())
    mandats = _extract_mandats_europeens(detail, org_cache)
    # Translated comment.
    # Translated comment.
    # Translated comment.
    with _ORG_CACHE_LOCK:
        current = _load_org_cache()
        current.update(org_cache)
        _save_org_cache(current)

    return {
        "identifiant_pe": mep_id,
        "nom_complet": detail.get("label"),
        "date_naissance": detail.get("bday"),
        "lieu_naissance": detail.get("placeOfBirth"),
        "photo": detail.get("img") or f"https://www.europarl.europa.eu/mepphoto/{mep_id}.jpg",
        "url_source": f"https://www.europarl.europa.eu/meps/fr/{mep_id}",
        "mandats_europeens": mandats,
        "meta": {
            "genere_le": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "licence_donnees": "CC BY 4.0 (Parlement européen, Open Data Portal - data.europarl.europa.eu)",
            "source_api": EP_API_BASE,
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("nom", help='Nom complet du candidat, ex: "Jordan Bardella"')
    parser.add_argument("--country", default="FR", help="Code pays ISO 3166-1 alpha-2 (défaut: FR)")
    parser.add_argument("--out", help="Chemin du fichier JSON de sortie (défaut: affichage sur stdout)")
    parser.add_argument("--no-cache", action="store_true", help="Ignorer le cache disque de la liste des eurodéputés")
    args = parser.parse_args()

    profile_ue = build_profile_ue(args.nom, country=args.country, use_cache=not args.no_cache)

    if profile_ue is None:
        print(f"— {args.nom} : aucune correspondance trouvée parmi les eurodéputé⋅e⋅s représentant {args.country}.")
        return

    output = json.dumps(profile_ue, ensure_ascii=False, indent=2)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output, encoding="utf-8")
        nb = len(profile_ue["mandats_europeens"])
        print(f"✓ {args.nom} : {nb} mandat(s)/fonction(s) européen(s) écrit(s) dans {out_path}")
    else:
        print(output)


if __name__ == "__main__":
    main()
