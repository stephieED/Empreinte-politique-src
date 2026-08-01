#!/usr/bin/env python3
"""
group_roster.py — Récupère la composition réelle d'un groupe parlementaire.

Contrairement à data/candidats.json (liste éditoriale des candidats déclarés
à l'élection présidentielle, voir parti_profile.py), ce module interroge les
données ouvertes NosDéputés.fr / NosSénateurs.fr pour obtenir la VRAIE liste
des membres d'un groupe parlementaire (ex. tou·te·s les député·es LR d'une
législature), à utiliser ensuite avec group_profile.py.

L'endpoint documenté `/groupe/<SIGLE>/json` renvoie systématiquement une
erreur HTTP 500 (vérifié sur plusieurs sigles et domaines de législature,
comme le endpoint `/votes` déjà contourné dans candidate_profile.py). On
utilise donc à la place la liste complète des parlementaires
(`/deputes/json` ou `/senateurs/json`, qui inclut l'historique complet et un
champ `groupe_sigle` par entrée), filtrée côté client par sigle de groupe.

Usage (depuis la racine du dépôt) :
    python src/group_roster.py --chambre deputes --sigle LR --legislature 16
"""

import argparse
import json
import sys
from typing import Any, Optional

import requests

from candidate_profile import BASE_URLS, HEADERS, LEGISLATURE_BY_BASE_URL, TIMEOUT

# Association legislature AN -> domaine NosDeputes.fr (inverse de
# candidate_profile.LEGISLATURE_BY_BASE_URL). Ne couvre que l'Assemblée : le
# Sénat n'a plus qu'un seul domaine d'archive, quelle que soit la période
# (voir BASE_URLS["senateurs"]).
_BASE_URL_BY_LEGISLATURE_AN: dict[str, str] = {
    legislature: base_url for base_url, legislature in LEGISLATURE_BY_BASE_URL.items()
}

_LIST_ENDPOINT = {
    "deputes": "deputes",
    "senateurs": "senateurs",
}


def _base_url_for(chambre: str, legislature: Optional[str]) -> str:
    """Détermine le domaine NosDéputés/NosSénateurs à interroger.

    Args:
        chambre: "deputes" | "senateurs".
        legislature: pour "deputes", législature AN (ex. "16") ; ignoré pour
                     "senateurs" (domaine d'archive unique, filtrage par date).

    Raises:
        ValueError: chambre inconnue ou législature AN non couverte.
    """
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
    """Filtre côté client pour le Sénat (domaine d'archive unique, pas de sous-domaine par législature).

    Un membre est retenu si son mandat couvre ou suit le début de la période
    demandée. Sans date fournie, aucun filtrage n'est appliqué (tous les
    membres, courants et anciens, sont retournés).
    """
    if legislature_debut is None:
        return True
    fin = member.get("mandat_fin")
    return fin is None or str(fin) >= legislature_debut


def fetch_group_roster(
    chambre: str,
    groupe_sigle: str,
    legislature: Optional[str] = None,
    senat_periode_debut: Optional[str] = None,
    session: Optional[requests.Session] = None,
) -> list[dict[str, Any]]:
    """Récupère la liste des membres réels d'un groupe parlementaire.

    Args:
        chambre: "deputes" | "senateurs".
        groupe_sigle: sigle exact du groupe tel que fourni par l'API
                      (ex. "LR", "RN", "SOC" — voir champ `groupe_sigle` des
                      entrées renvoyées par /deputes/json ou /senateurs/json).
        legislature: pour "deputes" uniquement, législature AN (ex. "16") ;
                     détermine le sous-domaine interrogé. None = domaine courant.
        senat_periode_debut: pour "senateurs" uniquement, date ISO "YYYY-MM-DD"
                              minimale de fin de mandat pour retenir un membre
                              (le domaine d'archive couvre toutes les périodes
                              sans sous-domaine dédié). None = pas de filtrage
                              temporel (courants + anciens).
        session: session requests à réutiliser (optionnel, pour les tests).

    Returns:
        Liste de dicts {slug, nom, groupe_sigle, mandat_debut, mandat_fin, actif}
        pour chaque membre dont `groupe_sigle` correspond exactement.

    Raises:
        ValueError: chambre ou législature inconnue.
        requests.RequestException: échec réseau (non intercepté, remonté tel quel).
    """
    base_url = _base_url_for(chambre, legislature)
    url = f"{base_url}/{_LIST_ENDPOINT[chambre]}/json"

    http = session or requests
    response = http.get(url, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    payload = response.json()

    raw_members = payload.get(chambre) or []
    roster: list[dict[str, Any]] = []

    for entry in raw_members:
        # Les payloads NosDéputés/NosSénateurs enveloppent chaque entrée sous
        # une clé singulière ({"depute": {...}} / {"senateur": {...}}).
        member = entry.get("depute") or entry.get("senateur") or entry
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
