#!/usr/bin/env python3
"""Quality gate pré-commit + résumé de run du pipeline de génération de données.

Produit quatre sections de rapport :
  1. Erreurs IncompleteRead dans meta.warnings[] de tous les JSON générés.
  2. Candidats générés vs attendus (d'après raw_data/candidats.json).
  3. Candidats avec un faible nombre d'interventions.
  4. Groupes parlementaires : hard fail sur structure cassée, soft fail sur
     qualité dégradée (couverture, signaux réseau).

Codes de sortie :
  0  — aucune erreur bloquante (IncompleteRead dans seuil, groupes valides)
  1  — structure groupe cassée (fichier manquant / JSON invalide / schéma invalide)
       OU erreurs IncompleteRead > seuil

Sorties :
  - Console (stdout) : rapport lisible.
  - $GITHUB_STEP_SUMMARY : tableau Markdown affiché dans le résumé du job GHA.
  - Annotations ::warning:: / ::error:: si GITHUB_ACTIONS=true.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# schema_groupe.py est dans le même répertoire que ce script
sys.path.insert(0, str(Path(__file__).parent))
try:
    from schema_groupe import validate_profil_groupe as _validate_groupe  # type: ignore[import]
    _SCHEMA_GROUPE_AVAILABLE = True
except ImportError:
    _SCHEMA_GROUPE_AVAILABLE = False

INCOMPLETE_READ_MARKER = "IncompleteRead"
# Signaux réseau spécifiques aux groupes (hors IncompleteRead, déjà traité §1)
_GROUPE_NETWORK_SIGNALS = ("roster_indisponible", "Échec de récupération", "timeout")
# Warning attendu sur toutes les données AN/Sénat figées — ne doit pas déclencher d'alerte
_FRAICHEUR_PREFIX = "fraicheur_donnees"

IN_GHA = os.getenv("GITHUB_ACTIONS") == "true"


# ---------------------------------------------------------------------------
# GitHub Actions helpers
# ---------------------------------------------------------------------------

def _gha_annotation(level: str, msg: str) -> None:
    """Émet une annotation GHA (::warning:: / ::error::), ignorée hors GHA."""
    if IN_GHA:
        clean = msg.replace("\n", " ").replace("\r", "")
        print(f"::{level}::{clean}", flush=True)


def _write_step_summary(markdown: str) -> None:
    """Écrit dans $GITHUB_STEP_SUMMARY si disponible."""
    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_path:
        try:
            with open(summary_path, "a", encoding="utf-8") as fh:
                fh.write(markdown + "\n")
        except OSError as exc:
            print(f"  [!] Impossible d'écrire dans GITHUB_STEP_SUMMARY : {exc}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> dict | list | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"  [!] Impossible de lire {path} : {exc}", file=sys.stderr)
        return None


def _slug_from_stem(stem: str) -> str:
    """Retire l'extension .pivot du stem si présente."""
    return stem[: -len(".pivot")] if stem.endswith(".pivot") else stem


# ---------------------------------------------------------------------------
# Section 1 — IncompleteRead
# ---------------------------------------------------------------------------

def _collect_incomplete_reads(dirs: dict[str, Path]) -> list[dict]:
    """Retourne tous les hits IncompleteRead dans meta.warnings[] des JSON fournis."""
    hits: list[dict] = []
    for label, directory in dirs.items():
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.json")):
            data = _load_json(path)
            if data is None:
                continue
            warnings: list[str] = (data.get("meta") or {}).get("warnings") or []
            for warning in warnings:
                if INCOMPLETE_READ_MARKER in warning:
                    endpoint = warning.split(":")[0].strip() if ":" in warning else "inconnu"
                    hits.append(
                        {
                            "slug": _slug_from_stem(path.stem),
                            "label": label,
                            "endpoint": endpoint,
                            "warning": warning,
                        }
                    )
    return hits


def _report_incomplete_reads(
    hits: list[dict], threshold: int
) -> tuple[str, str, int]:
    """
    Retourne (console_text, markdown_text, exit_code).
    exit_code 1 si count > threshold, sinon 0.
    """
    count = len(hits)
    by_endpoint: dict[str, list[dict]] = defaultdict(list)
    for h in hits:
        by_endpoint[h["endpoint"]].append(h)

    # --- statut global ---
    if count == 0:
        status_md = "✅ Aucune"
        status_icon = "✓"
        gate_label = "OK"
    elif count <= threshold:
        status_md = f"⚠️ {count} (≤ seuil {threshold})"
        status_icon = "⚠"
        gate_label = "AVERTISSEMENT"
    else:
        status_md = f"❌ {count} (> seuil {threshold})"
        status_icon = "✗"
        gate_label = "ÉCHEC"

    # ── Console ──────────────────────────────────────────────────────────────
    lines = [
        "",
        "┌─ 1/4  Erreurs IncompleteRead ──────────────────────────────────────",
        f"│  Seuil : {threshold}   Détectées : {count}   Statut : {gate_label}",
    ]
    if hits:
        lines.append("│")
        lines.append("│  Endpoints touchés :")
        for ep in sorted(by_endpoint):
            slugs = ", ".join(h["slug"] for h in by_endpoint[ep])
            lines.append(f"│    • {ep}  ({len(by_endpoint[ep])}×)  ←  {slugs}")
        lines.append("│")
        lines.append("│  Détail :")
        for h in hits:
            trunc = h["warning"][:120] + ("…" if len(h["warning"]) > 120 else "")
            lines.append(f"│    [{h['slug']}]  {trunc}")
    lines.append("└" + "─" * 67)
    console = "\n".join(lines)

    # ── Markdown (GHA Step Summary) ───────────────────────────────────────
    md_lines = [
        "### 1 · Erreurs IncompleteRead",
        "",
        f"| Métrique | Valeur |",
        f"|---|---|",
        f"| Détectées | {status_md} |",
        f"| Seuil configuré | {threshold} |",
        "",
    ]
    if hits:
        md_lines += [
            "**Endpoints touchés**",
            "",
            "| Endpoint | Occurrences | Candidats / fichiers |",
            "|---|---|---|",
        ]
        for ep in sorted(by_endpoint):
            slugs = ", ".join(f"`{h['slug']}`" for h in by_endpoint[ep])
            md_lines.append(f"| `{ep}` | {len(by_endpoint[ep])} | {slugs} |")
        md_lines.append("")
    else:
        md_lines.append("_Aucune erreur IncompleteRead détectée._\n")

    exit_code = 1 if count > threshold else 0
    return console, "\n".join(md_lines), exit_code


# ---------------------------------------------------------------------------
# Section 2 — Candidats générés vs attendus
# ---------------------------------------------------------------------------

def _report_coverage(
    candidats_path: Path, profiles_dir: Path
) -> tuple[str, str]:
    """Retourne (console_text, markdown_text)."""

    # Candidats attendus
    raw = _load_json(candidats_path)
    if raw is None or not isinstance(raw, dict):
        return ("  [!] candidats.json illisible.", "")
    all_candidats: list[dict] = raw.get("candidats") or []

    with_slug = {c["slug"]: c for c in all_candidats if c.get("slug")}
    without_slug = [c for c in all_candidats if not c.get("slug")]

    # Profils générés
    generated_slugs = {
        _slug_from_stem(p.stem)
        for p in profiles_dir.glob("*.pivot.json")
    } if profiles_dir.exists() else set()

    expected_slugs = set(with_slug.keys())
    missing = sorted(expected_slug for expected_slug in expected_slugs if expected_slug not in generated_slugs)
    unexpected = sorted(slug for slug in generated_slugs if slug not in expected_slugs)
    generated_expected = sorted(expected_slugs & generated_slugs)

    total_expected = len(all_candidats)
    total_generated = len(generated_slugs)

    # ── Console ──────────────────────────────────────────────────────────────
    icon = "✓" if not missing else "⚠"
    lines = [
        "",
        "┌─ 2/4  Candidats générés vs attendus ───────────────────────────────",
        f"│  Attendus (total) : {total_expected}   Avec slug : {len(with_slug)}"
        f"   Sans slug (non générables) : {len(without_slug)}",
        f"│  Générés          : {total_generated}   Manquants : {len(missing)}"
        + (f"   Inattendus : {len(unexpected)}" if unexpected else ""),
        "│",
    ]
    if missing:
        lines.append("│  ✗ Manquants :")
        for slug in missing:
            c = with_slug[slug]
            lines.append(f"│    • {c['nom']} ({c['parti']}) — {c['statut']}")
    else:
        lines.append(f"│  {icon} Tous les candidats avec slug ont un profil généré.")
    if unexpected:
        lines.append("│  ⚠ Fichiers sans correspondance dans candidats.json :")
        for slug in unexpected:
            lines.append(f"│    • {slug}")
    if without_slug:
        lines.append("│")
        lines.append("│  Sans slug (non générables via NosDéputés/NosSénateurs) :")
        for c in without_slug:
            lines.append(f"│    · {c['nom']} ({c['parti']})")
    lines.append("└" + "─" * 67)
    console = "\n".join(lines)

    # ── Markdown ──────────────────────────────────────────────────────────
    ok_icon = "✅" if not missing else "⚠️"
    md_lines = [
        "### 2 · Candidats générés vs attendus",
        "",
        "| | Nb |",
        "|---|---|",
        f"| {ok_icon} Générés | {total_generated} |",
        f"| 📋 Attendus (avec slug) | {len(with_slug)} |",
        f"| ❌ Manquants | {len(missing)} |",
        f"| ⬜ Sans slug (non générables) | {len(without_slug)} |",
        "",
    ]
    if missing:
        md_lines += [
            "**Candidats manquants**",
            "",
            "| Nom | Parti | Statut |",
            "|---|---|---|",
        ]
        for slug in missing:
            c = with_slug[slug]
            md_lines.append(f"| {c['nom']} | {c['parti']} | {c['statut']} |")
        md_lines.append("")
    if unexpected:
        md_lines += [
            "**Fichiers inattendus** (présents mais absents de candidats.json)",
            "",
            "| Slug |",
            "|---|",
        ]
        for slug in unexpected:
            md_lines.append(f"| `{slug}` |")
        md_lines.append("")

    return console, "\n".join(md_lines)


# ---------------------------------------------------------------------------
# Section 3 — Interventions faibles
# ---------------------------------------------------------------------------

def _report_low_interventions(
    profiles_dir: Path,
    candidats_path: Path,
    threshold: int,
) -> tuple[str, str]:
    """Retourne (console_text, markdown_text)."""

    # Index candidats pour enrichissement (nom → chambre depuis pivot)
    raw = _load_json(candidats_path)
    candidats_by_slug: dict[str, dict] = {}
    if raw and isinstance(raw, dict):
        for c in raw.get("candidats") or []:
            if c.get("slug"):
                candidats_by_slug[c["slug"]] = c

    rows: list[dict] = []
    if profiles_dir.exists():
        for path in sorted(profiles_dir.glob("*.pivot.json")):
            data = _load_json(path)
            if data is None:
                continue
            slug = _slug_from_stem(path.stem)
            n_interv = len(data.get("interventions") or [])
            chambre = data.get("chambre") or "?"
            nom = data.get("nom") or slug
            has_warns = bool((data.get("meta") or {}).get("warnings"))
            rows.append(
                {
                    "slug": slug,
                    "nom": nom,
                    "chambre": chambre,
                    "nb_interventions": n_interv,
                    "has_warnings": has_warns,
                }
            )

    low = [r for r in rows if r["nb_interventions"] < threshold]
    low.sort(key=lambda r: r["nb_interventions"])

    # ── Console ──────────────────────────────────────────────────────────────
    icon = "✓" if not low else "⚠"
    lines = [
        "",
        f"┌─ 3/4  Candidats avec peu d'interventions (< {threshold}) ───────────",
        f"│  Profils analysés : {len(rows)}   Sous le seuil : {len(low)}",
        "│",
    ]
    if low:
        header = f"│  {'Candidat':<30} {'Chambre':<8} {'Interventions':>13}  Warnings"
        lines.append(header)
        lines.append("│  " + "─" * 60)
        for r in low:
            warn_flag = " ⚠" if r["has_warnings"] else ""
            lines.append(
                f"│  {r['nom']:<30} {r['chambre']:<8} {r['nb_interventions']:>13}{warn_flag}"
            )
    else:
        lines.append(f"│  {icon} Tous les candidats ont ≥ {threshold} interventions.")
    lines.append("└" + "─" * 67)
    console = "\n".join(lines)

    # ── Markdown ──────────────────────────────────────────────────────────
    ok_icon = "✅" if not low else "⚠️"
    md_lines = [
        f"### 3 · Candidats avec peu d'interventions (seuil : {threshold})",
        "",
        f"| Métrique | Valeur |",
        f"|---|---|",
        f"| {ok_icon} Profils analysés | {len(rows)} |",
        f"| Sous le seuil (< {threshold}) | {len(low)} |",
        "",
    ]
    if low:
        md_lines += [
            "| Candidat | Chambre | Interventions | Warnings API |",
            "|---|---|---|---|",
        ]
        for r in low:
            warn_cell = "⚠️" if r["has_warnings"] else "—"
            md_lines.append(
                f"| {r['nom']} | {r['chambre']} | {r['nb_interventions']} | {warn_cell} |"
            )
        md_lines.append("")
    else:
        md_lines.append(f"_Tous les candidats ont au moins {threshold} interventions._\n")

    return console, "\n".join(md_lines)


# ---------------------------------------------------------------------------
# Section 3b — Couverture Syceron (soft warning)
# ---------------------------------------------------------------------------

# Législatures pour lesquelles Syceron fournit des données de débats AN.
_SYCERON_LEGISLATURES = frozenset({"15", "16", "17"})


def _report_low_syceron_coverage(
    profiles_dir: Path,
    threshold: int,
) -> tuple[list[str], str, str]:
    """Détecte les candidats AN ayant des mandats actifs sur une législature
    couverte par Syceron mais un nombre de débats Syceron inférieur au seuil.

    Retourne (soft_warnings, console_text, markdown_text).

    Soft fail uniquement : n'empêche pas le commit (exit_code inchangé).
    Un avertissement est émis si le nombre d'interventions dont
    `source.type == "syceron"` est < threshold pour un candidat dont les
    mandats couvrent au moins une législature Syceron.
    """
    rows: list[dict] = []
    if profiles_dir.exists():
        for path in sorted(profiles_dir.glob("*.pivot.json")):
            data = _load_json(path)
            if data is None:
                continue
            chambre = data.get("chambre") or ""
            if chambre not in ("AN", "deputes"):
                continue
            # Vérifie si le candidat a des mandats sur une législature Syceron.
            mandats = data.get("mandats") or []
            legislatures_syceron = {
                str(m.get("legislature") or "")
                for m in mandats
                if str(m.get("legislature") or "") in _SYCERON_LEGISLATURES
            }
            if not legislatures_syceron:
                continue
            slug = _slug_from_stem(path.stem)
            nom = data.get("nom") or slug
            interventions = data.get("interventions") or []
            n_syceron = sum(
                1
                for i in interventions
                if isinstance(i.get("source"), dict) and i["source"].get("type") == "syceron"
            )
            rows.append(
                {
                    "slug": slug,
                    "nom": nom,
                    "legislatures": sorted(legislatures_syceron),
                    "n_syceron": n_syceron,
                }
            )

    low = [r for r in rows if r["n_syceron"] < threshold]
    low.sort(key=lambda r: r["n_syceron"])

    soft_warnings: list[str] = []
    for r in low:
        legs = ", ".join(r["legislatures"])
        soft_warnings.append(
            f"{r['slug']}: couverture Syceron faible ({r['n_syceron']} débat(s) < seuil {threshold}, législature(s) {legs})"
        )

    icon = "✓" if not low else "⚠"
    lines = [
        "",
        f"┌─ 3b/4  Couverture Syceron (< {threshold} débat(s)) ─────────────────",
        f"│  Candidats AN avec législature Syceron : {len(rows)}   Sous le seuil : {len(low)}",
        "│",
    ]
    if low:
        header = f"│  {'Candidat':<30} {'Législatures':<15} {'Débats Syceron':>14}"
        lines.append(header)
        lines.append("│  " + "─" * 60)
        for r in low:
            legs = ", ".join(r["legislatures"])
            lines.append(f"│  {r['nom']:<30} {legs:<15} {r['n_syceron']:>14}")
    else:
        lines.append(f"│  {icon} Tous les candidats AN ont ≥ {threshold} débat(s) Syceron.")
    lines.append("└" + "─" * 67)
    console = "\n".join(lines)

    ok_icon = "✅" if not low else "⚠️"
    md_lines = [
        f"### 3b · Couverture Syceron (seuil : {threshold} débat(s))",
        "",
        "| Métrique | Valeur |",
        "|---|---|",
        f"| {ok_icon} Candidats AN avec législature Syceron | {len(rows)} |",
        f"| Sous le seuil (< {threshold}) | {len(low)} |",
        "",
    ]
    if low:
        md_lines += [
            "| Candidat | Législatures | Débats Syceron |",
            "|---|---|---|",
        ]
        for r in low:
            legs = ", ".join(r["legislatures"])
            md_lines.append(f"| {r['nom']} | {legs} | {r['n_syceron']} |")
        md_lines.append("")
    else:
        md_lines.append(f"_Tous les candidats AN ont au moins {threshold} débat(s) Syceron._\n")

    return soft_warnings, console, "\n".join(md_lines)


# ---------------------------------------------------------------------------
# Section 4 — Groupes parlementaires
# ---------------------------------------------------------------------------

def _report_groupes(
    groupes_config_path: Path,
    groupes_dir: Path,
    min_members: int,
    min_coverage_pct: float = 0.0,
) -> tuple[list[str], list[str], str, str]:
    """Analyse la qualité des fichiers de groupe générés.

    Retourne (hard_errors, soft_warnings, console_text, markdown_text).

    hard_errors  — chaque élément provoque exit_code=1 (structure cassée) :
      - fichier attendu manquant
      - JSON invalide
      - échec de validation de schéma (validate_profil_groupe)

    soft_warnings — signaux de qualité dégradée (n'empêchent pas le commit) :
      - profils_disponibles < min_members (couverture insuffisante, seuil absolu)
      - taux de couverture < min_coverage_pct (couverture insuffisante, seuil
        relatif — désactivé par défaut, voir doc de `min_coverage_pct`)
      - IncompleteRead dans meta.warnings (signal réseau)
      - pas de cohesion_votes malgré des membres présents (données incomplètes)

    Args:
        min_members: seuil absolu (nombre de profils chargés). Voir
            `docs/technical_decisions.md#seuil-couverture-groupe` pour la
            justification du défaut conservé (1) : les chiffres réels de
            couverture à pleine échelle de l'extraction roster-driven
            (#188/#190/#191) ne sont pas encore disponibles au moment de
            cette recalibration (#193) — seuls des runs à échelle réduite
            (`--limit`/`--sample`) ont été observés.
        min_coverage_pct: seuil relatif optionnel (0-100, `profils_disponibles
            / roster_total`). `0` désactive ce contrôle (défaut) : ce seuil
            relatif est ajouté pour permettre une recalibration future une
            fois des chiffres réels disponibles, sans devoir de nouveau
            changer la signature de cette fonction ni le format du rapport.
    """
    # ── Lecture de la config ──────────────────────────────────────────────
    raw_cfg = _load_json(groupes_config_path)
    if raw_cfg is None:
        msg = f"Impossible de lire la config groupes : {groupes_config_path}"
        return (
            [msg],
            [],
            f"\n┌─ 4/4  Groupes parlementaires ──────────────────────────────────────\n│  ✗ {msg}\n└{'─'*67}",
            f"### 4 · Groupes parlementaires\n\n❌ {msg}\n",
        )

    expected: list[dict] = raw_cfg.get("groupes") or []

    hard_errors: list[str] = []
    soft_warnings: list[str] = []

    # ── Analyse par groupe attendu ────────────────────────────────────────
    rows: list[dict] = []   # one row per expected groupe

    for grp in expected:
        groupe_id = grp.get("groupe_id", "?")
        fichier = grp.get("fichier")
        if not fichier:
            hard_errors.append(f"{groupe_id}: champ 'fichier' absent de groupes_reels.json")
            rows.append({"groupe_id": groupe_id, "nom": grp.get("groupe_nom", "?"),
                         "status": "hard", "detail": "config manquante"})
            continue

        path = groupes_dir / fichier

        # Hard 1 — fichier manquant
        if not path.exists():
            hard_errors.append(f"{groupe_id}: fichier manquant ({path})")
            rows.append({"groupe_id": groupe_id, "nom": grp.get("groupe_nom", "?"),
                         "status": "hard", "detail": "fichier manquant"})
            continue

        # Hard 2 — JSON invalide
        data = _load_json(path)
        if data is None:
            hard_errors.append(f"{groupe_id}: JSON invalide ({fichier})")
            rows.append({"groupe_id": groupe_id, "nom": grp.get("groupe_nom", "?"),
                         "status": "hard", "detail": "JSON invalide"})
            continue

        # Hard 3 — schéma invalide
        schema_errors: list[str] = []
        if _SCHEMA_GROUPE_AVAILABLE:
            schema_errors = _validate_groupe(data)
        if schema_errors:
            detail = "; ".join(schema_errors[:3]) + ("…" if len(schema_errors) > 3 else "")
            hard_errors.append(f"{groupe_id}: schéma invalide — {detail}")
            rows.append({"groupe_id": groupe_id, "nom": grp.get("groupe_nom", "?"),
                         "status": "hard", "detail": f"schéma invalide ({len(schema_errors)} erreur(s))"})
            continue

        # ── Données valides : contrôles de qualité ────────────────────────
        meta = data.get("meta") or {}
        warnings_list: list[str] = meta.get("warnings") or []
        couverture = meta.get("couverture_roster") or {}
        roster_total = couverture.get("roster_total", 0)
        profils_dispo = couverture.get("profils_disponibles", 0)
        nb_membres = len(data.get("membres") or [])
        nb_cohesion = len(data.get("cohesion_votes") or [])
        groupe_nom = data.get("groupe_nom") or groupe_id
        chambre = data.get("chambre") or "?"

        row_soft: list[str] = []
        row_status = "ok"
        coverage_pct = round(100 * profils_dispo / roster_total, 2) if roster_total > 0 else None

        # Soft 1a — couverture insuffisante (seuil absolu)
        if roster_total > 0 and profils_dispo < min_members:
            msg = (
                f"{groupe_id}: couverture insuffisante "
                f"({profils_dispo}/{roster_total} profils chargés < min {min_members})"
            )
            soft_warnings.append(msg)
            row_soft.append(f"couverture {profils_dispo}/{roster_total}")
            row_status = "soft"

        # Soft 1b — couverture insuffisante (seuil relatif, désactivé par défaut)
        if min_coverage_pct > 0 and roster_total > 0 and coverage_pct < min_coverage_pct:
            msg = (
                f"{groupe_id}: taux de couverture insuffisant "
                f"({coverage_pct}% < seuil {min_coverage_pct}%)"
            )
            soft_warnings.append(msg)
            row_soft.append(f"taux couverture {coverage_pct}%")
            row_status = "soft"

        # Soft 2 — signaux réseau (IncompleteRead ou autre pattern réseau)
        for w in warnings_list:
            if INCOMPLETE_READ_MARKER in w:
                endpoint = w.split(":")[0].strip() if ":" in w else "inconnu"
                msg = f"{groupe_id}: signal réseau IncompleteRead sur '{endpoint}'"
                soft_warnings.append(msg)
                row_soft.append(f"IncompleteRead ({endpoint})")
                row_status = "soft"
            elif not w.startswith(_FRAICHEUR_PREFIX) and any(sig in w for sig in _GROUPE_NETWORK_SIGNALS):
                msg = f"{groupe_id}: signal réseau — {w[:80]}"
                soft_warnings.append(msg)
                row_soft.append("signal réseau")
                row_status = "soft"
            # Note: fraicheur_donnees est attendu pour AN/Sénat — ignoré ici

        # Soft 3 — pas de données de vote alors que des membres sont présents
        if nb_membres > 0 and nb_cohesion == 0:
            msg = f"{groupe_id}: {nb_membres} membre(s) mais aucun vote de cohésion (données incomplètes ?)"
            soft_warnings.append(msg)
            row_soft.append("0 votes de cohésion")
            row_status = "soft" if row_status != "hard" else "hard"

        rows.append({
            "groupe_id": groupe_id,
            "nom": groupe_nom,
            "chambre": chambre,
            "profils_dispo": profils_dispo,
            "roster_total": roster_total,
            "coverage_pct": coverage_pct,
            "nb_membres": nb_membres,
            "nb_cohesion": nb_cohesion,
            "status": row_status,
            "soft_flags": ", ".join(row_soft) if row_soft else "—",
        })

    # ── Résumé global ─────────────────────────────────────────────────────
    n_hard = len(hard_errors)
    n_soft = len(soft_warnings)
    n_ok = sum(1 for r in rows if r["status"] == "ok")

    global_icon = "✓" if n_hard == 0 and n_soft == 0 else ("✗" if n_hard > 0 else "⚠")

    # ── Console ──────────────────────────────────────────────────────────────
    lines = [
        "",
        "┌─ 4/4  Groupes parlementaires ──────────────────────────────────────",
        f"│  Attendus : {len(expected)}   OK : {n_ok}   "
        f"Échecs durs : {n_hard}   Avertissements : {n_soft}",
        "│",
    ]
    if not _SCHEMA_GROUPE_AVAILABLE:
        lines.append("│  [!] schema_groupe non disponible — validation de schéma ignorée.")
        lines.append("│")
    if hard_errors:
        lines.append("│  ✗ Erreurs dures (commit bloqué) :")
        for e in hard_errors:
            lines.append(f"│    • {e}")
        lines.append("│")
    if soft_warnings:
        lines.append("│  ⚠ Avertissements qualité :")
        for w in soft_warnings:
            lines.append(f"│    · {w}")
        lines.append("│")

    # Tableau récap
    header = f"│  {'Groupe':<22} {'Chambre':<8} {'Couverts/Roster (%)':>20}  {'Membres':>8}  {'Votes':>6}  Flags"
    lines.append(header)
    lines.append("│  " + "─" * 72)
    for r in rows:
        status_marker = "✗" if r["status"] == "hard" else ("⚠" if r["status"] == "soft" else "✓")
        if r.get("roster_total"):
            coverage = f"{r.get('profils_dispo','?')}/{r.get('roster_total','?')} ({r.get('coverage_pct','?')}%)"
        else:
            coverage = "—"
        membres = str(r.get("nb_membres", "?"))
        votes = str(r.get("nb_cohesion", "?"))
        flags = r.get("soft_flags", "—")
        if r["status"] == "hard":
            flags = r.get("detail", "—")
        lines.append(
            f"│  {status_marker} {r['nom']:<20} {r.get('chambre','?'):<8} {coverage:>20}"
            f"  {membres:>8}  {votes:>6}  {flags}"
        )
    lines.append("└" + "─" * 67)
    console = "\n".join(lines)

    # ── Markdown ──────────────────────────────────────────────────────────
    overall_md = "✅" if n_hard == 0 and n_soft == 0 else ("❌" if n_hard > 0 else "⚠️")
    md_lines = [
        "### 4 · Groupes parlementaires",
        "",
        f"| | Nb |",
        "|---|---|",
        f"| {overall_md} Attendus | {len(expected)} |",
        f"| ✅ Valides | {n_ok} |",
        f"| ❌ Échecs durs | {n_hard} |",
        f"| ⚠️ Avertissements qualité | {n_soft} |",
        "",
    ]
    if not _SCHEMA_GROUPE_AVAILABLE:
        md_lines.append("> ⚠️ `schema_groupe` non importé — validation de schéma ignorée.\n")

    if hard_errors:
        md_lines += [
            "**Erreurs dures** _(bloquent le commit)_",
            "",
            "| Groupe | Problème |",
            "|---|---|",
        ]
        for r in rows:
            if r["status"] == "hard":
                md_lines.append(f"| `{r['groupe_id']}` | {r.get('detail', '?')} |")
        md_lines.append("")

    md_lines += [
        "**Détail par groupe**",
        "",
        "| Groupe | Chambre | Couverts / Roster | Taux de couverture (%) | Membres | Votes cohésion | Flags |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        status_icon = "❌" if r["status"] == "hard" else ("⚠️" if r["status"] == "soft" else "✅")
        coverage = (
            f"{r.get('profils_dispo','?')}/{r.get('roster_total','?')}"
            if r.get("roster_total") else "—"
        )
        coverage_pct = r.get("coverage_pct")
        coverage_pct_cell = f"{coverage_pct}%" if coverage_pct is not None else "—"
        flags = r.get("soft_flags", "—") if r["status"] != "hard" else r.get("detail", "—")
        md_lines.append(
            f"| {status_icon} {r['nom']} | {r.get('chambre','?')} | {coverage} | {coverage_pct_cell} "
            f"| {r.get('nb_membres','?')} | {r.get('nb_cohesion','?')} | {flags} |"
        )
    md_lines.append("")

    return hard_errors, soft_warnings, console, "\n".join(md_lines)


# ---------------------------------------------------------------------------
# Section 5 — Couverture ParlTrack (optionnelle)
# ---------------------------------------------------------------------------

def _report_parltrack_status(status_file: Path) -> tuple[str, str]:
    """Lit le fichier de statut ParlTrack produit par generate_all_profiles.py
    et retourne (console_text, markdown_text).

    Statuts attendus dans le fichier JSON :
      enrichi  — données ParlTrack ajoutées ce run.
      vide     — dumps disponibles, aucune donnée pour ce candidat.
      absent   — dumps absents (fallback sur cache/dépôt précédent).
      erreur   — exception lors de l'enrichissement.
      n/a      — candidat sans mandat UE / enrichissement non demandé.
    """
    if not status_file.exists():
        msg = f"Fichier de statut ParlTrack introuvable : {status_file}"
        return (
            f"\n┌─ 5/5  Enrichissement ParlTrack ────────────────────────────────────\n│  ⚠ {msg}\n└{'─'*67}",
            f"### 5 · Enrichissement ParlTrack\n\n⚠️ {msg}\n",
        )

    data = _load_json(status_file)
    if not isinstance(data, dict):
        return ("", "")

    enrichi: list[str] = data.get("enrichi") or []
    vide: list[str] = data.get("vide") or []
    absent: list[str] = data.get("absent") or []
    erreur: list[str] = data.get("erreur") or []
    na: list[str] = data.get("n/a") or []

    n_enrichi = len(enrichi)
    n_vide = len(vide)
    n_absent = len(absent)
    n_erreur = len(erreur)
    n_na = len(na)

    # ── Console ───────────────────────────────────────────────────────────
    icon = "✓" if n_absent == 0 and n_erreur == 0 else ("⚠" if n_erreur == 0 else "✗")
    lines = [
        "",
        "┌─ 5/5  Enrichissement ParlTrack ────────────────────────────────────",
        f"│  Ce run : {n_enrichi} enrichi(s)   {n_vide} vide(s)   {n_absent} fallback(s)   {n_erreur} erreur(s)   {n_na} sans mandat UE",
        "│",
    ]
    if n_absent > 0:
        lines.append(f"│  ⚠ {n_absent} candidat(s) en fallback (dumps ParlTrack absents ce run) :")
        for slug in absent:
            lines.append(f"│    · {slug}")
        lines.append("│")
    if n_erreur > 0:
        lines.append(f"│  ✗ {n_erreur} candidat(s) en erreur ParlTrack :")
        for slug in erreur:
            lines.append(f"│    • {slug}")
        lines.append("│")
    if n_enrichi > 0:
        lines.append(f"│  ✓ {n_enrichi} candidat(s) enrichi(s) par ParlTrack ce run :")
        for slug in enrichi:
            lines.append(f"│    + {slug}")
    elif n_absent == 0 and n_erreur == 0:
        lines.append("│  ✓ Aucun MEP candidat à enrichir ou données déjà à jour.")
    lines.append("└" + "─" * 67)
    console = "\n".join(lines)

    # ── Markdown ─────────────────────────────────────────────────────────
    overall_md = "✅" if n_absent == 0 and n_erreur == 0 else ("⚠️" if n_erreur == 0 else "❌")
    md_lines = [
        "### 5 · Enrichissement ParlTrack",
        "",
        "| Statut | Nb | Candidats |",
        "|---|---|---|",
        f"| ✅ Enrichis ce run | {n_enrichi} | {', '.join(f'`{s}`' for s in enrichi) or '—'} |",
        f"| 🔵 Dumps OK, aucune donnée | {n_vide} | {', '.join(f'`{s}`' for s in vide) or '—'} |",
        f"| ⚠️ Fallback (dumps absents) | {n_absent} | {', '.join(f'`{s}`' for s in absent) or '—'} |",
        f"| ❌ Erreur enrichissement | {n_erreur} | {', '.join(f'`{s}`' for s in erreur) or '—'} |",
        f"| — Sans mandat UE / N/A | {n_na} | — |",
        "",
    ]
    if n_absent > 0:
        md_lines.append(
            "> ⚠️ Les candidats en **fallback** conservent les données ParlTrack du dépôt précédent. "
            "Relancer le job `extract-parltrack` pour actualiser."
        )
        md_lines.append("")
    return console, "\n".join(md_lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Quality gate + résumé du pipeline de génération de données."
    )
    parser.add_argument("--profiles-dir", type=Path, default=Path("pivot_data/profiles"))
    parser.add_argument("--groupes-dir", type=Path, default=Path("pivot_data/groupes"))
    parser.add_argument("--partis-dir", type=Path, default=Path("pivot_data/partis"))
    parser.add_argument("--raw-dir", type=Path, default=Path("raw_data/profiles"))
    parser.add_argument("--candidats", type=Path, default=Path("raw_data/candidats.json"))
    parser.add_argument(
        "--groupes-config",
        type=Path,
        default=Path("raw_data/groupes_reels.json"),
        dest="groupes_config",
        help="Config des groupes attendus (défaut : raw_data/groupes_reels.json).",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=3,
        help="Seuil IncompleteRead avant échec dur (défaut : 3).",
    )
    parser.add_argument(
        "--low-interventions",
        type=int,
        default=10,
        dest="low_interventions",
        help="Seuil d'interventions 'faibles' à signaler (défaut : 10).",
    )
    parser.add_argument(
        "--groupe-min-members",
        type=int,
        default=1,
        dest="groupe_min_members",
        help=(
            "Nombre minimum de profils candidats attendus dans chaque groupe "
            "(soft fail si inférieur, défaut : 1). 0 = désactivé. Seuil "
            "absolu conservé par défaut faute de chiffres réels de couverture "
            "à pleine échelle (voir docs/technical_decisions.md#seuil-couverture-groupe)."
        ),
    )
    parser.add_argument(
        "--groupe-min-coverage-pct",
        type=float,
        default=0.0,
        dest="groupe_min_coverage_pct",
        help=(
            "Taux de couverture minimum (%%, profils_disponibles / roster_total) "
            "attendu dans chaque groupe (soft fail si inférieur, défaut : 0 = "
            "désactivé). Seuil relatif complémentaire de --groupe-min-members, "
            "à activer une fois des chiffres réels de couverture à pleine "
            "échelle disponibles (voir docs/technical_decisions.md#seuil-couverture-groupe)."
        ),
    )
    parser.add_argument(
        "--low-syceron-coverage",
        type=int,
        default=1,
        dest="low_syceron_coverage",
        help=(
            "Seuil de débats Syceron 'faibles' à signaler pour les candidats AN "
            "avec un mandat sur une législature couverte (défaut : 1). 0 = désactivé."
        ),
    )
    parser.add_argument(
        "--parltrack-status-file",
        type=Path,
        default=None,
        dest="parltrack_status_file",
        help=(
            "Fichier JSON produit par generate_all_profiles.py --parltrack-status-out. "
            "Active la section 5 du rapport (enrichissement ParlTrack ce run vs fallback)."
        ),
    )
    args = parser.parse_args()

    run_date = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # ── Section 1 : IncompleteRead ─────────────────────────────────────────
    ir_dirs = {
        "pivot_data/profiles": args.profiles_dir,
        "pivot_data/groupes": args.groupes_dir,
        "pivot_data/partis": args.partis_dir,
        "raw_data/profiles": args.raw_dir,
    }
    ir_hits = _collect_incomplete_reads(ir_dirs)
    ir_console, ir_md, ir_exit = _report_incomplete_reads(ir_hits, args.threshold)

    # ── Section 2 : Couverture candidats ──────────────────────────────────
    cov_console, cov_md = _report_coverage(args.candidats, args.profiles_dir)

    # ── Section 3 : Interventions faibles ─────────────────────────────────
    low_console, low_md = _report_low_interventions(
        args.profiles_dir, args.candidats, args.low_interventions
    )

    # ── Section 3b : Couverture Syceron ───────────────────────────────────
    syc_soft: list[str] = []
    syc_console = ""
    syc_md = ""
    if args.low_syceron_coverage > 0:
        syc_soft, syc_console, syc_md = _report_low_syceron_coverage(
            args.profiles_dir, args.low_syceron_coverage
        )

    # ── Section 4 : Groupes parlementaires ────────────────────────────────
    grp_hard, grp_soft, grp_console, grp_md = _report_groupes(
        args.groupes_config, args.groupes_dir, args.groupe_min_members,
        min_coverage_pct=args.groupe_min_coverage_pct,
    )
    grp_exit = 1 if grp_hard else 0

    # ── Section 5 : Couverture ParlTrack (optionnelle) ────────────────────
    pt_console = ""
    pt_md = ""
    if args.parltrack_status_file is not None:
        pt_console, pt_md = _report_parltrack_status(args.parltrack_status_file)

    exit_code = 1 if (ir_exit == 1 or grp_exit == 1) else 0

    # ── Sortie console ─────────────────────────────────────────────────────
    gate_label = "✓ COMMIT AUTORISÉ" if exit_code == 0 else "✗ COMMIT BLOQUÉ"
    print(f"\n{'═'*69}")
    print(f"  RÉSUMÉ DU RUN  —  {run_date}")
    print(f"  Quality gate : {gate_label}")
    print(f"{'═'*69}")
    print(ir_console)
    print(cov_console)
    print(low_console)
    if syc_console:
        print(syc_console)
    print(grp_console)
    if pt_console:
        print(pt_console)
    print()

    # ── GitHub Step Summary (Markdown) ────────────────────────────────────
    gate_badge = "✅ Commit autorisé" if exit_code == 0 else "❌ Commit bloqué"
    md = "\n".join([
        f"## 📊 Résumé du run pipeline — {run_date}",
        "",
        f"> **Quality gate** : {gate_badge}",
        "",
        ir_md,
        cov_md,
        low_md,
        syc_md,
        grp_md,
        pt_md,
    ])
    _write_step_summary(md)

    # ── Annotations GHA ───────────────────────────────────────────────────
    ir_count = len(ir_hits)
    if ir_count > 0:
        by_ep: dict[str, list[str]] = defaultdict(list)
        for h in ir_hits:
            by_ep[h["endpoint"]].append(h["slug"])
        ep_summary = "; ".join(
            f"{ep} ({len(slugs)}×: {', '.join(slugs)})" for ep, slugs in sorted(by_ep.items())
        )
        level = "error" if ir_exit == 1 else "warning"
        qualifier = f"> seuil {args.threshold}" if ir_exit == 1 else f"≤ seuil {args.threshold}"
        _gha_annotation(level, f"IncompleteRead — {ir_count} {qualifier}. {ep_summary}")

    for err in grp_hard:
        _gha_annotation("error", f"Groupe — structure cassée : {err}")
    for warn in grp_soft:
        _gha_annotation("warning", f"Groupe — qualité dégradée : {warn}")
    for warn in syc_soft:
        _gha_annotation("warning", f"Syceron — couverture faible : {warn}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
