#!/usr/bin/env python3
"""Module documentation in English."""

import argparse
import json
import sys
from typing import Any, Optional

import requests

from candidate_profile import BASE_URLS, HEADERS, LEGISLATURE_BY_BASE_URL, TIMEOUT

# Association legislature AN -> domaine NosDeputes.fr (inverse de
# Translated comment.
# Translated comment.
# (voir BASE_URLS["senateurs"]).
_BASE_URL_BY_LEGISLATURE_AN: dict[str, str] = {
    legislature: base_url for base_url, legislature in LEGISLATURE_BY_BASE_URL.items()
}

_LIST_ENDPOINT = {
    "deputes": "deputes",
    "senateurs": "senateurs",
}


def _base_url_for(chambre: str, legislature: Optional[str]) -> str:
    """English docstring for  base url for."""
    if chambre not in BASE_URLS:
        raise ValueError(f"Chambre inconnue : {chambre!r}. Valeurs attendues : {sorted(BASE_URLS)}.")

    if chambre == "senateurs":
        return BASE_URLS["senateurs"][0]

    if legislature is None:
        return BASE_URLS["deputes"][0]

    if legislature not in _BASE_URL_BY_LEGISLATURE_AN:
        raise ValueError(
            f"Législature AN non couverte : {legislature!r}. "
            f"Valeurs connues : {sorted(_BASE_URL_BY_LEGISLATURE_AN)}."
        )
    return _BASE_URL_BY_LEGISLATURE_AN[legislature]


def _member_matches_legislature(member: dict[str, Any], legislature_debut: Optional[str]) -> bool:
    """English docstring for  member matches legislature."""
    if legislature_debut is None:
        return True
    fin = member.get("mandat_fin")
    return fin is None or str(fin) >= legislature_debut


def fetch_full_roster(
    chambre: str,
    legislature: Optional[str] = None,
    session: Optional[requests.Session] = None,
) -> list[dict[str, Any]]:
    """English docstring for fetch full roster."""
    base_url = _base_url_for(chambre, legislature)
    url = f"{base_url}/{_LIST_ENDPOINT[chambre]}/json"

    http = session or requests
    response = http.get(url, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    payload = response.json()

    raw_entries = payload.get(chambre) or []
    return [entry.get("depute") or entry.get("senateur") or entry for entry in raw_entries]


def filter_roster_by_sigle(
    raw_members: list[dict[str, Any]],
    chambre: str,
    groupe_sigle: str,
    senat_periode_debut: Optional[str] = None,
) -> list[dict[str, Any]]:
    """English docstring for filter roster by sigle."""
    roster: list[dict[str, Any]] = []
    for member in raw_members:
        if member.get("groupe_sigle") != groupe_sigle:
            continue
        if chambre == "senateurs" and not _member_matches_legislature(member, senat_periode_debut):
            continue

        mandat_fin = member.get("mandat_fin")
        roster.append({
            "slug": member.get("slug"),
            "nom": member.get("nom"),
            "groupe_sigle": member.get("groupe_sigle"),
            "mandat_debut": member.get("mandat_debut"),
            "mandat_fin": mandat_fin,
            "actif": not mandat_fin,
        })
    return roster


def fetch_group_roster(
    chambre: str,
    groupe_sigle: str,
    legislature: Optional[str] = None,
    senat_periode_debut: Optional[str] = None,
    session: Optional[requests.Session] = None,
) -> list[dict[str, Any]]:
    """English docstring for fetch group roster."""
    raw_members = fetch_full_roster(chambre, legislature=legislature, session=session)
    return filter_roster_by_sigle(raw_members, chambre, groupe_sigle, senat_periode_debut=senat_periode_debut)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Récupère la composition réelle d'un groupe parlementaire "
        "(NosDéputés.fr / NosSénateurs.fr).",
    )
    parser.add_argument("--chambre", choices=["deputes", "senateurs"], required=True)
    parser.add_argument("--sigle", required=True, metavar="SIGLE", help='Ex. "LR", "RN", "SOC".')
    parser.add_argument("--legislature", default=None, metavar="N", help='Pour "deputes" uniquement, ex. "16".')
    parser.add_argument(
        "--senat-periode-debut",
        default=None,
        metavar="YYYY-MM-DD",
        help='Pour "senateurs" uniquement : ne garder que les membres dont le mandat va au moins jusqu\'à cette date.',
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    try:
        roster = fetch_group_roster(
            chambre=args.chambre,
            groupe_sigle=args.sigle,
            legislature=args.legislature,
            senat_periode_debut=args.senat_periode_debut,
        )
    except (ValueError, requests.RequestException) as exc:
        print(f"[!] {exc}", file=sys.stderr)
        return 1

    print(f"→ {len(roster)} membre(s) trouvé(s) pour le groupe {args.sigle!r}.", file=sys.stderr)
    print(json.dumps(roster, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
