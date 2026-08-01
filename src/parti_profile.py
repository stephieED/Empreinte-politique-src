#!/usr/bin/env python3
"""
parti_profile.py — Construit un profil de parti à partir de data/candidats.json.

Contrairement à group_profile.py (groupe parlementaire réel : cohésion de
vote, amendements agrégés), ce module agrège uniquement des candidats
partageant un label de parti déclaratif (élection présidentielle), sans
prétendre représenter un groupe parlementaire ni son effectif réel. Aucun
appel réseau : les pivots individuels doivent déjà exister sur disque.

Usage (depuis la racine du dépôt) :
    python src/parti_profile.py \\
        --candidats data/candidats.json \\
        --profiles-dir data/profiles \\
        --out-dir data/profiles

    Génère un fichier data/profiles/parti-<slug>.json par parti présent dans
    data/candidats.json.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

from group_profile import aggregate_tags_thematiques
from schema_parti import SCHEMA_PARTI_VERSION, make_empty_profil_parti, validate_profil_parti
from text_utils import slugify as _slugify


def _load_pivot(profiles_dir: Path, slug: str) -> Optional[dict[str, Any]]:
    """Charge le pivot v1 d'un candidat s'il existe, sinon None (sans lever)."""
    pivot_path = profiles_dir / f"{slug}.pivot.json"
    if not pivot_path.exists():
        return None
    try:
        with open(pivot_path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def build_parti_profile(
    parti_nom: str,
    candidats: list[dict[str, Any]],
    profiles_dir: Path,
    licence_donnees: str = "",
) -> dict[str, Any]:
    """Construit un profil de parti à partir des candidats d'un même label `parti`.

    Args:
        parti_nom: libellé de parti tel qu'il apparaît dans data/candidats.json.
        candidats: sous-liste de data/candidats.json partageant ce `parti`.
        profiles_dir: dossier contenant les pivots individuels (*.pivot.json).
        licence_donnees: texte de licence à inscrire dans meta.

    Returns:
        Profil de parti dict conforme au schéma de parti v1.
    """
    parti_id = _slugify(parti_nom)
    profil = make_empty_profil_parti(parti_id, parti_nom)

    pivots: list[dict[str, Any]] = []
    seen_sources: set[tuple[str, str]] = set()
    warnings: list[str] = []

    for candidat in candidats:
        slug = candidat.get("slug")
        pivot = _load_pivot(profiles_dir, slug) if slug else None

        if pivot is not None:
            pivots.append(pivot)
            candidat_id = pivot.get("id")
            for s in (pivot.get("sources") or []):
                key = (s.get("type") or "", s.get("url") or "")
                if key not in seen_sources:
                    seen_sources.add(key)
                    profil["sources"].append(s)
        else:
            candidat_id = None
            if slug:
                warnings.append(
                    f"candidat={slug} : aucun profil pivot trouvé dans {profiles_dir} "
                    "(fichier <slug>.pivot.json absent)."
                )

        profil["candidats"].append({
            "candidat_id": candidat_id,
            "nom": candidat.get("nom") or "",
            "statut": candidat.get("statut"),
            "famille_politique": candidat.get("famille_politique"),
            "a_un_profil_pivot": pivot is not None,
        })

    tags_agreges, tag_source = aggregate_tags_thematiques(pivots)
    profil["tags_thematiques_agreges"] = tags_agreges
    if tag_source == "mots_cles_interventions":
        warnings.append(
            "tags_thematiques_agreges : source=mots_cles_interventions "
            "(tags_thematiques individuels absents ou vides ; mots-clés des "
            "interventions utilisés en fallback)."
        )
    elif tag_source == "mixed":
        warnings.append(
            "tags_thematiques_agreges : source=mixed (certains profils utilisent "
            "tags_thematiques, d'autres utilisent mots_cles_interventions)."
        )

    profil["meta"]["licence_donnees"] = licence_donnees
    profil["meta"]["nb_candidats_declares"] = len(candidats)
    profil["meta"]["nb_candidats_avec_pivot"] = len(pivots)
    profil["meta"]["warnings"] = warnings

    return profil


def _group_candidats_by_parti(candidats: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Regroupe les candidats de data/candidats.json par leur champ `parti`."""
    by_parti: dict[str, list[dict[str, Any]]] = {}
    for candidat in candidats:
        parti = candidat.get("parti")
        if not parti:
            continue
        by_parti.setdefault(parti, []).append(candidat)
    return by_parti


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Construit un profil de parti par label `parti` de data/candidats.json.",
    )
    parser.add_argument(
        "--candidats",
        default="data/candidats.json",
        metavar="FICHIER",
        help="Fichier data/candidats.json (défaut : data/candidats.json).",
    )
    parser.add_argument(
        "--profiles-dir",
        default="data/profiles",
        metavar="DOSSIER",
        help="Dossier contenant les pivots individuels *.pivot.json (défaut : data/profiles).",
    )
    parser.add_argument(
        "--out-dir",
        default="data/profiles",
        metavar="DOSSIER",
        help="Dossier de sortie des fichiers parti-<slug>.json (défaut : data/profiles).",
    )
    parser.add_argument(
        "--licence",
        default="",
        metavar="TEXTE",
        help="Texte de licence à inscrire dans meta.licence_donnees.",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Valide chaque profil de parti produit et affiche les erreurs éventuelles.",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    candidats_path = Path(args.candidats)
    with open(candidats_path, encoding="utf-8") as f:
        data = json.load(f)
    candidats = data.get("candidats", [])

    profiles_dir = Path(args.profiles_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    by_parti = _group_candidats_by_parti(candidats)
    print(f"→ {len(by_parti)} parti(s) distinct(s) dans {candidats_path}.", file=sys.stderr)

    for parti_nom, parti_candidats in by_parti.items():
        profil = build_parti_profile(parti_nom, parti_candidats, profiles_dir, args.licence)

        if args.validate:
            errors = validate_profil_parti(profil)
            if errors:
                print(f"  [!] {profil['parti_id']} : {len(errors)} erreur(s) de validation :", file=sys.stderr)
                for e in errors:
                    print(f"      - {e}", file=sys.stderr)
            else:
                print(f"  ✓ {profil['parti_id']} : profil valide selon le schéma.", file=sys.stderr)

        out_path = out_dir / f"parti-{profil['parti_id']}.json"
        out_path.write_text(
            json.dumps(profil, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(
            f"  ✓ {parti_nom} : {profil['meta']['nb_candidats_avec_pivot']}/"
            f"{profil['meta']['nb_candidats_declares']} candidat(s) avec pivot → {out_path}",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
