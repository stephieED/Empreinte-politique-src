#!/usr/bin/env python3
"""
generate_roster_candidats.py — Construit une liste de "candidats" à partir du
roster réel des groupes parlementaires configurés dans raw_data/groupes_reels.json,
au lieu de la liste éditoriale raw_data/candidats.json.

Contexte : raw_data/candidats.json est une liste éditoriale maintenue à la
main (candidats déclarés/pressentis à la présidentielle). Ce script produit
une liste alternative, au même format d'entrée que celui accepté par
generate_all_profiles.py --candidats, mais pilotée par la composition réelle
des groupes parlementaires — utile pour extraire des profils individuels pour
tou·te·s les membres d'un groupe, pas seulement les candidats déclarés.

Comme generate_group_profiles.py, ce script ne fait qu'UN SEUL fetch réseau
par (roster_chambre, legislature) distinct, partagé entre tous les groupes de
la config (voir group_roster.fetch_full_roster / filter_roster_by_sigle).

Usage (depuis la racine du dépôt) :
    python src/generate_roster_candidats.py \\
        --config raw_data/groupes_reels.json \\
        --out raw_data/roster_candidats.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

from group_roster import _base_url_for, fetch_full_roster, filter_roster_by_sigle


def _roster_key(groupe: dict[str, Any]) -> tuple[str, Optional[str]]:
    """Clé (roster_chambre, legislature) identifiant un fetch réseau partageable."""
    legislature = groupe.get("legislature") if groupe["roster_chambre"] == "deputes" else None
    return (groupe["roster_chambre"], legislature)


def fetch_rosters_bruts(groupes: list[dict[str, Any]]) -> dict[tuple[str, Optional[str]], Optional[list[dict[str, Any]]]]:
    """Récupère le roster complet (non filtré) de chaque (roster_chambre, legislature)
    distinct présent dans `groupes`, un seul fetch réseau par clé. Une valeur `None`
    signale un échec réseau pour cette clé."""
    import requests  # import tardif : non requis hors récupération réelle

    rosters_bruts: dict[tuple[str, Optional[str]], Optional[list[dict[str, Any]]]] = {}
    for groupe in groupes:
        key = _roster_key(groupe)
        if key in rosters_bruts:
            continue
        roster_chambre, legislature = key
        print(f"→ Récupération du roster complet ({roster_chambre}, législature={legislature or 'courante'})…", file=sys.stderr)
        try:
            rosters_bruts[key] = fetch_full_roster(roster_chambre, legislature=legislature)
        except (ValueError, requests.RequestException) as exc:
            print(f"  [!] Récupération du roster impossible pour {key} : {exc}", file=sys.stderr)
            rosters_bruts[key] = None
    return rosters_bruts


def build_roster_candidats(
    groupes: list[dict[str, Any]],
    rosters_bruts: dict[tuple[str, Optional[str]], Optional[list[dict[str, Any]]]],
) -> list[dict[str, Any]]:
    """Aplatit le roster de chaque groupe en une liste unique de candidats, au format
    attendu par generate_all_profiles.load_candidats() (shape {"candidats": [...]}).

    Fonction pure (aucun accès réseau) : `rosters_bruts` doit déjà contenir, pour
    chaque (roster_chambre, legislature) référencée par `groupes`, le roster brut
    (non filtré) issu de `fetch_full_roster`, ou `None` en cas d'échec réseau (le
    groupe correspondant est alors ignoré).

    Un membre ne peut appartenir qu'à un seul groupe par fetch (`groupe_sigle` est
    un champ mono-valué côté API), donc aucune fusion cross-groupe n'est attendue en
    conditions normales. On déduplique malgré tout par `slug` (garde-fou), au cas où
    deux entrées de la config pointeraient vers le même (chambre, legislature) avec
    un sigle mal renseigné : la première occurrence rencontrée est conservée.
    """
    candidats_par_slug: dict[str, dict[str, Any]] = {}

    for groupe in groupes:
        key = _roster_key(groupe)
        raw_members = rosters_bruts.get(key)
        if not raw_members:
            continue

        roster = filter_roster_by_sigle(
            raw_members,
            groupe["roster_chambre"],
            groupe["groupe_sigle"],
            senat_periode_debut=groupe.get("senat_periode_debut"),
        )
        base_url = _base_url_for(groupe["roster_chambre"], key[1])

        for membre in roster:
            slug = membre.get("slug")
            if not slug or slug in candidats_par_slug:
                continue
            candidats_par_slug[slug] = {
                "nom": membre.get("nom"),
                "slug": slug,
                "parti": None,
                "famille_politique": None,
                "statut": "roster_groupe",
                "date_declaration": None,
                "source": f"{base_url}/{slug}",
                "notes": f"Membre du groupe {groupe['groupe_sigle']} ({groupe['groupe_nom']}), issu du roster réel {groupe['chambre']}.",
            }

    return list(candidats_par_slug.values())


def generate_roster_candidats(groupes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Récupère les rosters réseau nécessaires puis construit la liste aplatie de candidats."""
    rosters_bruts = fetch_rosters_bruts(groupes)
    return build_roster_candidats(groupes, rosters_bruts)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--config",
        default="raw_data/groupes_reels.json",
        metavar="FICHIER",
        help="Fichier JSON listant les groupes à agréger (défaut : raw_data/groupes_reels.json).",
    )
    parser.add_argument(
        "--out",
        default="raw_data/roster_candidats.json",
        metavar="FICHIER",
        help="Fichier JSON de sortie (défaut : raw_data/roster_candidats.json).",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    config_path = Path(args.config)
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"[!] Lecture de {config_path} impossible : {exc}", file=sys.stderr)
        return 1

    groupes = config.get("groupes") or []
    if not groupes:
        print(f"[!] Aucun groupe à agréger dans {config_path}.", file=sys.stderr)
        return 1

    candidats = generate_roster_candidats(groupes)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"candidats": candidats}, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"→ {len(candidats)} candidat(s) écrit(s) dans {out_path}.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
