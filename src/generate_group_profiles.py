#!/usr/bin/env python3
"""Module documentation in English."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

from group_profile import generate_groupe_profile_from_roster
from group_roster import fetch_full_roster, filter_roster_by_sigle


def _roster_key(groupe: dict[str, Any]) -> tuple[str, Optional[str]]:
    """English docstring for  roster key."""   legislature = groupe.get("legislature") if groupe["roster_chambre"] == "deputes" else None
    return (groupe["roster_chambre"], legislature)


def generate_all(
    groupes: list[dict[str, Any]],
    profiles_dir: Path,
    out_dir: Path,
    merge_existing: bool = False,
    validate: bool = False,
) -> int:
    """English docstring for generate all."""    import requests  # Translated comment.

    rosters_bruts: dict[tuple[str, Optional[str]], list[dict[str, Any]]] = {}
    echecs = 0

    for groupe in groupes:
        key = _roster_key(groupe)
        if key not in rosters_bruts:
            roster_chambre, legislature = key
            print(f"→ Récupération du roster complet ({roster_chambre}, législature={legislature or 'courante'})…", file=sys.stderr)
            try:
                rosters_bruts[key] = fetch_full_roster(roster_chambre, legislature=legislature)
            except (ValueError, requests.RequestException) as exc:
                print(f"  [!] Récupération du roster impossible pour {key} : {exc}", file=sys.stderr)
                rosters_bruts[key] = None

        raw_members = rosters_bruts[key]
        if raw_members is None:
            print(f"  [!] {groupe['groupe_id']} ignoré (roster {key} indisponible).", file=sys.stderr)
            echecs += 1
            continue

        roster = filter_roster_by_sigle(
            raw_members,
            groupe["roster_chambre"],
            groupe["groupe_sigle"],
            senat_periode_debut=groupe.get("senat_periode_debut"),
        )

        out_path = out_dir / groupe["fichier"]
        try:
            generate_groupe_profile_from_roster(
                roster=roster,
                groupe_id=groupe["groupe_id"],
                groupe_sigle=groupe["groupe_sigle"],
                groupe_nom=groupe["groupe_nom"],
                chambre=groupe["chambre"],
                legislature=groupe.get("legislature"),
                roster_chambre=groupe["roster_chambre"],
                profiles_dir=profiles_dir,
                out_path=out_path,
                merge_existing=merge_existing,
                validate=validate,
            )
        except Exception as exc:  # Translated comment.
            print(f"  [!] Échec de génération pour {groupe['groupe_id']} : {exc}", file=sys.stderr)
            echecs += 1

    return echecs


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--config",
        default="raw_data/groupes_reels.json",
        metavar="FICHIER",
        help="Fichier JSON listant les groupes à générer (défaut : raw_data/groupes_reels.json).",
    )
    parser.add_argument(
        "--profiles-dir",
        default="pivot_data/profiles",
        metavar="DOSSIER",
        help="Dossier des profils pivot individuels (défaut : pivot_data/profiles).",
    )
    parser.add_argument(
        "--out-dir",
        default="pivot_data/groupes",
        metavar="DOSSIER",
        help="Dossier de sortie des profils de groupe (défaut : pivot_data/groupes).",
    )
    parser.add_argument(
        "--merge-existing",
        action="store_true",
        help=(
            "Réintègre, pour chaque groupe, les membres du fichier de sortie "
            "précédent absents du roster récupéré cette exécution (voir "
            "group_profile.py --merge-existing)."
        ),
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Valide chaque profil de groupe produit et affiche les erreurs éventuelles.",
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
        print(f"[!] Aucun groupe à générer dans {config_path}.", file=sys.stderr)
        return 1

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    echecs = generate_all(
        groupes,
        profiles_dir=Path(args.profiles_dir),
        out_dir=out_dir,
        merge_existing=args.merge_existing,
        validate=args.validate,
    )

    print(f"→ {len(groupes) - echecs}/{len(groupes)} profil(s) de groupe généré(s).", file=sys.stderr)
    return 1 if echecs else 0


if __name__ == "__main__":
    sys.exit(main())
