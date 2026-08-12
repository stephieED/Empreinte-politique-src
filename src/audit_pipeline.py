#!/usr/bin/env python3
"""
audit_pipeline.py — Point d'entrée manuel compilant les audits profils + groupes.

Outil manuel de qualité interne (issue #178, plan #174), distinct de
`check_quality_gate.py` (seul gate bloquant en CI) : n'est appelé nulle part
dans `.github/workflows/`, usage manuel uniquement.

Appelle directement les fonctions de `audit_pivot_dataset.py` et
`audit_groupe_dataset.py` (pas de sous-processus) et compose leurs deux
rapports en un seul, avec une section "vue d'ensemble" ajoutée en plus des
deux rapports détaillés : totaux profils/groupes audités, erreurs de lecture
agrégées, warnings agrégés tous documents confondus. Pure composition à
partir des rapports déjà assemblés par les modules `audit_*` — aucune
nouvelle logique de calcul métier n'est introduite ici (AGENTS.md §2.1 : pas
de score, pas de classement).

Aucune dépendance lourde : stdlib uniquement.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import audit_groupe_dataset
import audit_pivot_dataset


def compute_vue_ensemble(
    rapport_profils: dict[str, Any], rapport_groupes: dict[str, Any]
) -> dict[str, Any]:
    """Compile une vue d'ensemble à partir des deux rapports d'audit déjà assemblés.

    Pure composition : additionne/regroupe les totaux et warnings déjà
    calculés par `audit_pivot_dataset.build_report` et
    `audit_groupe_dataset.build_report`, sans recalculer aucun indicateur à
    partir des profils/groupes bruts.

    Returns:
        `{"total_profils_audites": int, "total_groupes_audites": int,
        "total_erreurs_lecture": int, "erreurs_lecture": {"profils": [...],
        "groupes": [...]}, "warnings": {"total_warnings": int, "par_type":
        {type: {"frequence": int, "profils_ids": [...], "groupe_ids":
        [...]}}}}`. `par_type` couvre l'union des types rencontrés côté
        profils et côté groupes ; un type absent d'un des deux audits a une
        liste d'`ids` vide pour ce côté.
    """
    warnings_profils = rapport_profils["warnings"]["par_type"]
    warnings_groupes = rapport_groupes["warnings"]["par_type"]

    par_type: dict[str, Any] = {}
    for type_warning in sorted(set(warnings_profils) | set(warnings_groupes)):
        entree_profils = warnings_profils.get(type_warning)
        entree_groupes = warnings_groupes.get(type_warning)
        par_type[type_warning] = {
            "frequence": (
                (entree_profils["frequence"] if entree_profils else 0)
                + (entree_groupes["frequence"] if entree_groupes else 0)
            ),
            "profils_ids": entree_profils["ids"] if entree_profils else [],
            "groupe_ids": entree_groupes["groupe_ids"] if entree_groupes else [],
        }

    return {
        "total_profils_audites": rapport_profils["meta"]["total_profils"],
        "total_groupes_audites": rapport_groupes["meta"]["total_groupes"],
        "total_erreurs_lecture": (
            rapport_profils["meta"]["total_erreurs_lecture"]
            + rapport_groupes["meta"]["total_erreurs_lecture"]
        ),
        "erreurs_lecture": {
            "profils": rapport_profils["erreurs_lecture"],
            "groupes": rapport_groupes["erreurs_lecture"],
        },
        "warnings": {
            "total_warnings": (
                rapport_profils["warnings"]["total_warnings"]
                + rapport_groupes["warnings"]["total_warnings"]
            ),
            "par_type": par_type,
        },
    }


def build_report(
    rapport_profils: dict[str, Any], rapport_groupes: dict[str, Any]
) -> dict[str, Any]:
    """Assemble les rapports profils et groupes en un rapport combiné unique.

    Args:
        rapport_profils: sortie de `audit_pivot_dataset.build_report`.
        rapport_groupes: sortie de `audit_groupe_dataset.build_report`.

    Returns:
        `{"meta": {...}, "vue_ensemble": {...}, "audit_profils": {...},
        "audit_groupes": {...}}`. Les deux sous-rapports détaillés sont
        ceux produits tels quels par les modules `audit_*` — aucune donnée
        n'y est recalculée ni modifiée.
    """
    return {
        "meta": {
            "genere_le": rapport_profils["meta"]["genere_le"],
            "staleness_days": rapport_profils["meta"]["staleness_days"],
        },
        "vue_ensemble": compute_vue_ensemble(rapport_profils, rapport_groupes),
        "audit_profils": rapport_profils,
        "audit_groupes": rapport_groupes,
    }


# ---------------------------------------------------------------------------
# Génération du rapport Markdown
# ---------------------------------------------------------------------------

def _md_escape(valeur: Any) -> str:
    """Neutralise les caractères cassant une cellule de tableau Markdown."""
    texte = "" if valeur is None else str(valeur)
    return texte.replace("|", "\\|").replace("\n", " ")


def _md_table(en_tetes: list[str], lignes: list[list[Any]], si_vide: str) -> str:
    """Construit un tableau Markdown, ou renvoie `si_vide` si `lignes` est vide."""
    if not lignes:
        return si_vide + "\n"

    entete = "| " + " | ".join(en_tetes) + " |"
    separateur = "| " + " | ".join("---" for _ in en_tetes) + " |"
    corps = "\n".join(
        "| " + " | ".join(_md_escape(cellule) for cellule in ligne) + " |" for ligne in lignes
    )
    return f"{entete}\n{separateur}\n{corps}\n"


def _md_section_vue_ensemble(vue: dict[str, Any]) -> str:
    lignes_totaux = [
        ["Profils audités", vue["total_profils_audites"]],
        ["Groupes audités", vue["total_groupes_audites"]],
        ["Erreurs de lecture (profils + groupes)", vue["total_erreurs_lecture"]],
        ["Warnings (profils + groupes)", vue["warnings"]["total_warnings"]],
    ]

    lignes_warnings = [
        [
            type_warning,
            entree["frequence"],
            ", ".join(entree["profils_ids"]) or "—",
            ", ".join(entree["groupe_ids"]) or "—",
        ]
        for type_warning, entree in vue["warnings"]["par_type"].items()
    ]

    lignes_erreurs = (
        [["profil", e["fichier"], e["erreur"]] for e in vue["erreurs_lecture"]["profils"]]
        + [["groupe", e["fichier"], e["erreur"]] for e in vue["erreurs_lecture"]["groupes"]]
    )

    return (
        "## Vue d'ensemble\n\n"
        + _md_table(["Indicateur", "Valeur"], lignes_totaux, "Aucune donnée.")
        + "\n### Warnings agrégés (profils + groupes)\n\n"
        + _md_table(
            ["Type", "Fréquence", "Profils concernés", "Groupes concernés"],
            lignes_warnings, "Aucun warning.",
        )
        + "\n### Erreurs de lecture agrégées\n\n"
        + _md_table(["Domaine", "Fichier", "Erreur"], lignes_erreurs, "Aucune erreur de lecture.")
    )


def generate_markdown_report(rapport: dict[str, Any]) -> str:
    """Génère un rapport Markdown lisible par un humain à partir du dict `build_report`.

    Vue d'ensemble d'abord, puis les deux rapports détaillés tels que générés
    par `audit_pivot_dataset.generate_markdown_report` et
    `audit_groupe_dataset.generate_markdown_report` (aucune donnée
    recalculée). Outil de qualité interne : aucun score ni classement
    (AGENTS.md §2.1).
    """
    meta = rapport["meta"]

    entete = (
        "# Rapport d'audit pipeline (profils + groupes)\n\n"
        f"Généré le {meta['genere_le']}. Seuil de péremption des sources : "
        f"{meta['staleness_days']} jour(s).\n\n"
        "Outil manuel de qualité interne, distinct de `check_quality_gate.py` "
        "(seul gate bloquant en CI) : usage manuel uniquement, jamais appelé "
        "par la CI. Compile les rapports `audit_pivot_dataset.py` et "
        "`audit_groupe_dataset.py` sans nouvelle logique de calcul métier, "
        "ni score ni classement.\n"
    )

    return "\n".join([
        entete,
        _md_section_vue_ensemble(rapport["vue_ensemble"]),
        "---\n\n" + audit_pivot_dataset.generate_markdown_report(rapport["audit_profils"]),
        "---\n\n" + audit_groupe_dataset.generate_markdown_report(rapport["audit_groupes"]),
    ])


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="audit_pipeline.py",
        description=(
            "Exécute les audits profils (audit_pivot_dataset.py) et groupes "
            "(audit_groupe_dataset.py) et compile une vue d'ensemble. Outil "
            "manuel de qualité interne — usage manuel uniquement, jamais "
            "appelé par la CI. Ne produit aucun score ni classement."
        ),
    )
    parser.add_argument(
        "--profiles-dir",
        default="pivot_data/profiles",
        metavar="DOSSIER",
        help="Dossier des fichiers *.pivot.json à auditer (défaut : pivot_data/profiles).",
    )
    parser.add_argument(
        "--groupes-dir",
        default="pivot_data/groupes",
        metavar="DOSSIER",
        help="Dossier des fichiers *.json de groupe à auditer (défaut : pivot_data/groupes).",
    )
    parser.add_argument(
        "--output-json",
        default=None,
        metavar="FICHIER",
        help="Chemin du rapport JSON combiné (défaut : affiché sur stdout).",
    )
    parser.add_argument(
        "--output-md",
        default=None,
        metavar="FICHIER",
        help="Chemin du rapport Markdown combiné (défaut : non généré).",
    )
    parser.add_argument(
        "--staleness-days",
        type=int,
        default=30,
        metavar="JOURS",
        help=(
            "Seuil d'ancienneté (jours) au-delà duquel un profil/groupe est "
            "périmé, répercuté vers les deux audits sous-jacents (défaut : 30)."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    profiles_dir = Path(args.profiles_dir)
    groupes_dir = Path(args.groupes_dir)

    if not profiles_dir.is_dir():
        print(f"[!] Dossier profils introuvable : {profiles_dir}", file=sys.stderr)
        return 1
    if not groupes_dir.is_dir():
        print(f"[!] Dossier groupes introuvable : {groupes_dir}", file=sys.stderr)
        return 1

    reference = datetime.now(timezone.utc)

    profils, erreurs_profils = audit_pivot_dataset.load_pivot_directory(profiles_dir)
    rapport_profils = audit_pivot_dataset.build_report(
        profils, erreurs_profils, staleness_days=args.staleness_days, reference_date=reference,
    )
    print(
        f"→ profils : {len(profils)} chargé(s), {len(erreurs_profils)} erreur(s) de lecture.",
        file=sys.stderr,
    )

    groupes, erreurs_groupes = audit_groupe_dataset.load_groupe_directory(groupes_dir)
    rapport_groupes = audit_groupe_dataset.build_report(
        groupes, erreurs_groupes, staleness_days=args.staleness_days, reference_date=reference,
    )
    print(
        f"→ groupes : {len(groupes)} chargé(s), {len(erreurs_groupes)} erreur(s) de lecture.",
        file=sys.stderr,
    )

    rapport = build_report(rapport_profils, rapport_groupes)
    output_json = json.dumps(rapport, ensure_ascii=False, indent=2)

    if args.output_json:
        out_path = Path(args.output_json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output_json, encoding="utf-8")
        print(f"  ✓ Rapport JSON écrit : {out_path}", file=sys.stderr)
    else:
        print(output_json)

    if args.output_md:
        md_path = Path(args.output_md)
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(generate_markdown_report(rapport), encoding="utf-8")
        print(f"  ✓ Rapport Markdown écrit : {md_path}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
