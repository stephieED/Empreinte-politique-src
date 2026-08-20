#!/usr/bin/env python3
"""Quality gate pré-commit + résumé de run du pipeline de génération de données.

Produit cinq sections de rapport :
  1. Erreurs IncompleteRead **non rattrapées** dans meta.warnings[] de tous
     les JSON générés (une lecture reprise avec succès après retry n'y
     figure pas — le log du run peut donc signaler une instabilité réseau
     sans qu'aucune erreur ne soit comptée ici).
  2. Candidats générés vs attendus (d'après raw_data/candidats.json).
  3. Candidats avec un faible nombre d'interventions.
  4. Groupes parlementaires : hard fail sur structure cassée, soft fail sur
     qualité dégradée (couverture, signaux réseau).
  5. Gouvernements : hard fail sur structure cassée, soft fail sur qualité
     dégradée (couverture ministérielle, textes vides sur une période
     couverte par la source, signaux réseau) — miroir de la section 4, sur
     le modèle de #184. Les gouvernements hors couverture des archives
     ingérées sont listés à part, en information (#399).

Codes de sortie :
  0  — aucune erreur bloquante (IncompleteRead dans seuil, groupes et
       gouvernements valides)
  1  — structure groupe ou gouvernement cassée (fichier manquant / JSON
       invalide / schéma invalide) OU erreurs IncompleteRead > seuil

Sorties :
  - Console (stdout) : rapport lisible.
  - $GITHUB_STEP_SUMMARY : tableau Markdown affiché dans le résumé du job GHA.
  - Annotations ::warning:: / ::error:: si GITHUB_ACTIONS=true.
"""

from __future__ import annotations

import argparse
import gzip
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
try:
    from schema_gouvernement import validate_profil_gouvernement as _validate_gouvernement  # type: ignore[import]
    _SCHEMA_GOUVERNEMENT_AVAILABLE = True
except ImportError:
    _SCHEMA_GOUVERNEMENT_AVAILABLE = False
# Lecture des chambres d'un profil (#494) : porte unique, jamais `chambre` ni
# `chambres` en direct. Deux filtres de population en dépendent — la §3c et la
# couverture Syceron —, et le corpus publié ne porte pas encore `chambres`.
# stdlib pure, aucune I/O, comme `couverture_dossiers` juste dessous.
from schema_pivot import libelle_chambres, lire_chambres  # noqa: E402

# Périmètre réellement couvert par les archives de dossiers ingérées (#399) :
# stdlib pure, aucune I/O — importé pour ne pas signaler comme un défaut de
# données ce qui n'est qu'une absence de source.
from couverture_dossiers import (  # noqa: E402
    COUVERTURE_COUVERTE,
    COUVERTURE_HORS,
    COUVERTURE_PARTIELLE,
    LIBELLES_COUVERTURE,
    libelle_couverture_textes,
    statut_couverture_textes,
)

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
        "┌─ 1/4  Erreurs IncompleteRead non rattrapées ───────────────────────",
        f"│  Seuil : {threshold}   Détectées : {count}   Statut : {gate_label}",
        "│  (une lecture reprise avec succès n'apparaît pas ici : seuls les "
        "échecs définitifs sont comptés)",
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
        "### 1 · Erreurs IncompleteRead non rattrapées",
        "",
        f"| Métrique | Valeur |",
        f"|---|---|",
        f"| Détectées | {status_md} |",
        f"| Seuil configuré | {threshold} |",
        "",
        "> Ne compte que les lectures **définitivement** échouées : une "
        "lecture reprise avec succès après retry est absente de ce total, "
        "même quand le log du run signale l'instabilité réseau.",
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
            # #494 — `chambres` (liste) plutôt que le scalaire : un profil
            # bicaméral s'affichait sous une seule chambre, celle du site qui
            # avait répondu. La colonne montre désormais « AN+PE ».
            chambres = libelle_chambres(lire_chambres(data))
            nom = data.get("nom") or slug
            has_warns = bool((data.get("meta") or {}).get("warnings"))
            rows.append(
                {
                    "slug": slug,
                    "nom": nom,
                    "chambres": chambres,
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
        header = f"│  {'Candidat':<30} {'Chambres':<8} {'Interventions':>13}  Warnings"
        lines.append(header)
        lines.append("│  " + "─" * 60)
        for r in low:
            warn_flag = " ⚠" if r["has_warnings"] else ""
            lines.append(
                f"│  {r['nom']:<30} {r['chambres']:<8} {r['nb_interventions']:>13}{warn_flag}"
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
            "| Candidat | Chambres | Interventions | Warnings API |",
            "|---|---|---|---|",
        ]
        for r in low:
            warn_cell = "⚠️" if r["has_warnings"] else "—"
            md_lines.append(
                f"| {r['nom']} | {r['chambres']} | {r['nb_interventions']} | {warn_cell} |"
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
            # #494 — `"AN" in lire_chambres(...)` remplace
            # `chambre in ("AN", "deputes")`. Le scalaire n'en retenait qu'une :
            # un profil bicaméral publié `Senat` sortait de la population alors
            # qu'il siège aussi à l'Assemblée, et ses débats Syceron cessaient
            # d'être surveillés. La tolérance historique pour la valeur de
            # collecte `"deputes"` est conservée — `lire_chambres` la mappe.
            if "AN" not in lire_chambres(data):
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
# Section 3c — Couverture Amendements (soft warning)
# ---------------------------------------------------------------------------

# Préfixe du warning émis par candidate_profile.py (fetch_amendements_officiels)
# quand la collecte des amendements officiels échoue (téléchargement/parsing AN).
_AMENDEMENTS_INDISPONIBLES_PREFIX = "amendements indisponibles"

# Contrat avec candidate_profile.py : législatures couvertes (AN_AMENDEMENTS_PATH)
# et nom du fichier d'indicateur de fraîcheur écrit par _write_amendements_fraicheur
# (issue #253) à côté de chaque index_par_acteur.json mis en cache. Dupliqués ici
# plutôt qu'importés — même choix de découplage que _AMENDEMENTS_INDISPONIBLES_PREFIX
# ci-dessus (ce script n'importe jamais candidate_profile.py).
_AMENDEMENTS_LEGISLATURES = ("17", "16", "15", "14")
_AMENDEMENTS_FRAICHEUR_FILENAME = "fraicheur.json"
# Seuil par défaut (en jours) au-delà duquel un index présent mais sans
# reconstruction réussie récente est signalé comme périmé — voir
# docs/technical_decisions.md#amendements-index-quality-gate-fraicheur.
_AMENDEMENTS_STALENESS_DAYS_DEFAULT = 7
# Législatures dont l'archive AN source est définitivement close — même
# duplication délibérée que ci-dessus vis-à-vis de
# AN_AMENDEMENTS_LEGISLATURES_FIGEES (candidate_profile.py). Leur index,
# committé par build_amendements_index_figees.py, ne sera plus jamais
# reconstruit : la fraîcheur n'a pas de sens pour elles (voir
# docs/technical_decisions.md#amendements-legislatures-figees).
_AMENDEMENTS_LEGISLATURES_FIGEES = frozenset({"14", "15", "16"})
# Répertoire des index figés committés (AN_AMENDEMENTS_FIGEES_DIR côté
# candidate_profile.py) — même duplication délibérée que les constantes
# ci-dessus : ce script ne doit importer que du code sans dépendance réseau.
_AMENDEMENTS_FIGEES_DIR_DEFAUT = Path("raw_data") / "amendements_an_figes"


def _index_par_acteur_au_format_uid(index_par_acteur: object) -> bool:
    """Les références d'un index amendements portent-elles un `uid` (et non un
    `numero`) ? Réplique volontaire de
    `candidate_profile._index_par_acteur_au_format_uid` — ce script n'importe
    pas `candidate_profile`, qui tire les dépendances réseau."""
    if not isinstance(index_par_acteur, dict):
        return False
    for refs in index_par_acteur.values():
        if not isinstance(refs, list):
            return False
        for ref in refs:
            if not isinstance(ref, dict):
                return False
            return bool(ref.get("uid"))
    return True
# Décision #378 : le signal global « aucun candidat AN n'a d'amendements » reste
# un soft warning — jamais un échec dur, dans aucun mode (y compris fresh_run).
# Il est en revanche remonté à part par `_report_amendements_coverage` pour être
# affiché en tête de rapport plutôt que noyé dans la liste des avertissements
# de la §3c : détecté et affiché, mais ignoré, était précisément le mode d'échec
# de #265. Voir docs/technical_decisions.md#amendements-zero-pas-de-hard-fail.
_AMENDEMENTS_ZERO_ICONE = "🚨"
_AMENDEMENTS_ZERO_DECISION_REF = (
    "docs/technical_decisions.md#amendements-zero-pas-de-hard-fail"
)

# Couverture `uid` partielle dans un même profil (#447). Rien ne signalait ce
# cas : ni les logs d'extraction, ni cette gate. Il est passé pour une
# instabilité de collecte pendant deux jours, alors qu'il matérialise la
# cohabitation de deux versions d'un même amendement — celle résolue sur la clé
# écrasée d'avant #440, et celle résolue sur `uid`. Un amendement compté deux
# fois n'est pas une donnée incomplète, c'est un fait faux, et les
# dénominateurs publiés en dépendent (AGENTS.md §2.7).
#
# Soft, comme tout le reste de la §3c (#378) : pendant la fenêtre de remise en
# état de #450 les profils mixtes SONT attendus, et faire échouer la gate
# bloquerait précisément les runs censés les corriger. Ce qui manquait n'était
# pas un verrou, c'était un signal.
_AMENDEMENTS_UID_MIXTE_ICONE = "🔀"
_AMENDEMENTS_UID_DECISION_REF = (
    "docs/technical_decisions.md#publication-scopee-artifacts"
)


def _report_amendements_coverage(profiles_dir: Path) -> tuple[list[str], str | None, str, str]:
    """Détecte les régressions silencieuses sur amendements[] pour les député·e·s AN.

    Retourne (soft_warnings, regression_globale, console_text, markdown_text).
    Soft fail uniquement (n'empêche pas le commit) — y compris pour le signal
    global, cf. décision #378
    (docs/technical_decisions.md#amendements-zero-pas-de-hard-fail).

    Deux signaux distincts :
      - par candidat : un warning `amendements indisponibles` est présent dans
        meta.warnings (échec de collecte tracé côté candidate_profile.py).
      - global : aucun des candidats AN avec identité (éligibles à la collecte
        d'amendements) n'a la moindre entrée dans amendements[], alors que
        plusieurs candidats sont analysés — signal d'une régression touchant
        toute la chaîne, y compris silencieuse (cf. issue #185).

    `regression_globale` porte le message du second signal (ou `None`). Il est
    aussi présent dans `soft_warnings` — il n'est pas d'une autre nature, il est
    seulement retourné à part pour que l'appelant puisse l'afficher en tête de
    rapport (#378) au lieu de le laisser en dernière ligne d'une liste
    d'avertissements par candidat.
    """
    rows: list[dict] = []
    if profiles_dir.exists():
        for path in sorted(profiles_dir.glob("*.pivot.json")):
            data = _load_json(path)
            if data is None:
                continue
            amendements = data.get("amendements") or []
            # Deux populations distinctes, délibérément (#447) :
            #
            # - `population_an` — les députés identifiés — porte les compteurs
            #   « candidats AN » et le signal de régression « amendements[] vide
            #   partout » : ce sont les profils dont on ATTEND des amendements ;
            # - la mesure de couverture `uid`, elle, porte sur tout profil qui
            #   PUBLIE des amendements, quelle que soit sa `chambre`.
            #
            # Filtrer la mesure `uid` sur `chambre == "AN"` laissait un angle
            # mort mesuré le 19/08/2026 : `jean-luc-melenchon`, 18 721
            # amendements AN publiés, est sorti du champ de la §3c en passant à
            # `chambre: "Senat"` avec `identite` vide — soit 2,3 % du corpus
            # invisibles au signal même qui doit les surveiller, sur le profil
            # que #447 cite. Un profil peut cesser d'être compté sans cesser
            # d'être publié : la §3c doit suivre les amendements, pas la fiche.
            #
            # #494 — le test porte désormais sur `chambres` (liste) et non plus
            # sur le scalaire. Ce n'est pas une reformulation : le scalaire ne
            # retenait qu'**une** chambre, donc un profil bicaméral en sortait
            # dès que l'autre chambre l'emportait — c'est le mécanisme même de
            # l'angle mort ci-dessus. `"AN" in chambres` garde dans la population
            # AN quelqu'un qui a aussi siégé au Sénat : l'assiette ne peut plus
            # que croître, jamais rétrécir. La tolérance pour la valeur de
            # collecte `"deputes"` est conservée par `lire_chambres`.
            population_an = bool("AN" in lire_chambres(data) and data.get("identite"))
            if not population_an and not amendements:
                continue
            slug = _slug_from_stem(path.stem)
            nom = data.get("nom") or slug
            n_amendements = len(amendements)
            # La mesure suit le champ (#431) : depuis la normalisation, l'`uid`
            # d'un amendement vit dans l'index partagé et le profil n'en garde
            # que `amendement_id` (`an:<uid>`) — la même donnée, préfixée. Un
            # profil normalisé serait sinon compté à 0 % de couverture et
            # signalé comme cassé alors qu'il est corrigé. `uid` reste lu pour
            # les profils d'avant la normalisation, que la fusion additive fait
            # cohabiter avec les nouveaux le temps d'une régénération.
            n_uid = sum(
                1 for a in amendements
                if isinstance(a, dict) and (a.get("amendement_id") or a.get("uid"))
            )
            warnings_list: list[str] = (data.get("meta") or {}).get("warnings") or []
            has_fetch_error = any(w.startswith(_AMENDEMENTS_INDISPONIBLES_PREFIX) for w in warnings_list)
            rows.append(
                {
                    "slug": slug,
                    "nom": nom,
                    "n_amendements": n_amendements,
                    "n_uid": n_uid,
                    "has_fetch_error": has_fetch_error,
                    "population_an": population_an,
                }
            )

    soft_warnings: list[str] = []
    for r in rows:
        if r["has_fetch_error"]:
            soft_warnings.append(f"{r['slug']}: collecte des amendements officiels en échec (voir meta.warnings)")

    # Un profil est « mixte » quand ses amendements portent un `uid` en partie
    # seulement. Les profils à 0 % ne sont PAS signalés ici : ils sont
    # entièrement sur l'ancienne clé, donc en retard de correction (#440) mais
    # pas dupliqués — c'est une frontière de conquête, pas un fait faux.
    rows_mixtes = [r for r in rows if 0 < r["n_uid"] < r["n_amendements"]]
    for r in sorted(rows_mixtes, key=lambda r: r["n_uid"] / r["n_amendements"]):
        sans_uid = r["n_amendements"] - r["n_uid"]
        soft_warnings.append(
            f"{r['slug']}: {sans_uid}/{r['n_amendements']} amendements sans uid "
            f"({100 * r['n_uid'] / r['n_amendements']:.1f} % couverts) — deux versions du "
            f"même amendement cohabitent probablement, dénominateurs faussés (#447/#450)"
        )

    n_amendements_total = sum(r["n_amendements"] for r in rows)
    n_uid_total = sum(r["n_uid"] for r in rows)
    rows_hors_an = [r for r in rows if not r["population_an"]]
    n_hors_an_amendements = sum(r["n_amendements"] for r in rows_hors_an)
    # Le signal de régression porte sur la population AN attendue, pas sur les
    # lignes ajoutées pour leurs seuls amendements (voir plus haut) : un profil
    # hors population AN n'entre dans `rows` que s'il a des amendements, il ne
    # peut donc jamais faire basculer un « vide partout ».
    rows_an = [r for r in rows if r["population_an"]]
    n_avec_amendements = sum(1 for r in rows_an if r["n_amendements"] > 0)
    regression_globale: str | None = None
    if rows_an and not any(r["n_amendements"] > 0 for r in rows_an):
        regression_globale = (
            f"aucun candidat AN sur {len(rows_an)} n'a d'amendements collectés (amendements[] vide partout) "
            "— possible régression de collecte (candidate_profile.fetch_amendements_officiels)"
        )
        soft_warnings.append(regression_globale)

    # Avertissements par candidat : le signal global est affiché à part
    # ci-dessous, ne pas le répéter dans la liste.
    warnings_par_candidat = [w for w in soft_warnings if w != regression_globale]

    icon = "✓" if not soft_warnings else "⚠"
    pct_uid = f"{100 * n_uid_total / n_amendements_total:.1f} %" if n_amendements_total else "N/D"
    lines = [
        "",
        "┌─ 3c/4  Couverture amendements (AN) ────────────────────────────────",
        f"│  Candidats AN avec identité : {len(rows_an)}   Avec amendements : {n_avec_amendements}"
        f"   Avertissements : {len(soft_warnings)}",
        f"│  Amendements : {n_amendements_total}   dont uid : {n_uid_total} ({pct_uid})"
        f"   Profils mixtes : {len(rows_mixtes)}",
    ]
    if rows_hors_an:
        # Rendu explicite plutôt que fondu dans les compteurs AN : ces profils
        # publient des amendements sans appartenir à la population dont on en
        # attend, et c'est justement ce décalage qui les rendait invisibles.
        lines.append(
            f"│  Dont hors population AN : {len(rows_hors_an)} profil(s), "
            f"{n_hors_an_amendements} amendement(s) — publiés, donc mesurés"
        )
    lines.append("│")
    if rows_mixtes:
        lines += [
            f"│  {_AMENDEMENTS_UID_MIXTE_ICONE} {len(rows_mixtes)} profil(s) à couverture uid PARTIELLE —",
            "│    signature d'une version périmée réinjectée à côté de la version",
            "│    corrigée : les entrées concernées sont comptées deux fois.",
            f"│    À régénérer, pas à refusionner ({_AMENDEMENTS_UID_DECISION_REF}).",
            "│",
        ]
    if regression_globale is not None:
        lines += [
            f"│  {_AMENDEMENTS_ZERO_ICONE} RÉGRESSION PROBABLE DE COLLECTE — {regression_globale}",
            f"│    Signal volontairement NON bloquant ({_AMENDEMENTS_ZERO_DECISION_REF}) :",
            "│    à vérifier avant de se fier aux amendements de ce run.",
            "│",
        ]
    if warnings_par_candidat:
        lines.append("│  ⚠ Avertissements qualité :")
        for w in warnings_par_candidat:
            lines.append(f"│    · {w}")
    elif not soft_warnings:
        lines.append(f"│  {icon} Couverture amendements cohérente.")
    lines.append("└" + "─" * 67)
    console = "\n".join(lines)

    ok_icon = "✅" if not soft_warnings else "⚠️"
    md_lines = [
        "### 3c · Couverture amendements (AN)",
        "",
        "| Métrique | Valeur |",
        "|---|---|",
        f"| {ok_icon} Candidats AN avec identité | {len(rows_an)} |",
        f"| Avec ≥ 1 amendement | {n_avec_amendements} |",
        f"| Amendements | {n_amendements_total} |",
        f"| dont portant un `uid` | {n_uid_total} ({pct_uid}) |",
        f"| Profils à couverture `uid` partielle | {len(rows_mixtes)} |",
        f"| Avertissements | {len(soft_warnings)} |",
        "",
    ]
    if rows_hors_an:
        md_lines.insert(
            -1,
            f"| Dont hors population AN | {len(rows_hors_an)} profil(s), "
            f"{n_hors_an_amendements} amendement(s) |",
        )
    if rows_mixtes:
        md_lines += [
            f"> {_AMENDEMENTS_UID_MIXTE_ICONE} **{len(rows_mixtes)} profil(s) à couverture `uid` partielle** — "
            "signature d'une version périmée réinjectée à côté de la version corrigée. "
            "Les entrées concernées sont comptées deux fois, ce qui fausse les dénominateurs "
            "publiés (AGENTS.md §2.7).",
            ">",
            "> Ces profils sont à **régénérer**, pas à refusionner : `src/audit_diff_profils.py` "
            "signalera une baisse sur `amendements`, qui est ici le résultat attendu "
            f"(`{_AMENDEMENTS_UID_DECISION_REF}`).",
            "",
        ]
    if regression_globale is not None:
        md_lines += [
            f"> {_AMENDEMENTS_ZERO_ICONE} **Régression probable de collecte des amendements** — "
            f"{regression_globale}",
            ">",
            "> Signal volontairement **non bloquant** "
            f"(`{_AMENDEMENTS_ZERO_DECISION_REF}`) : il n'échoue pas le run, mais les "
            "amendements de ce run ne sont pas fiables tant qu'il n'a pas été vérifié.",
            "",
        ]
    if warnings_par_candidat:
        md_lines += ["**Avertissements**", ""]
        for w in warnings_par_candidat:
            md_lines.append(f"- {w}")
        md_lines.append("")
    elif not soft_warnings:
        md_lines.append("_Couverture amendements cohérente._\n")

    return soft_warnings, regression_globale, console, "\n".join(md_lines)


def _parse_amendements_horodatage(valeur: object) -> datetime | None:
    """Parse `fraicheur.json["horodatage"]` (format `time.strftime('%Y-%m-%dT%H:%M:%S%z')`,
    voir `_write_amendements_fraicheur` dans candidate_profile.py). `None` si
    absent/illisible — traité par l'appelant comme fraîcheur non garantie plutôt
    que de lever. Une date sans fuseau (ne devrait pas arriver en pratique, `%z`
    fournit toujours un offset) est supposée UTC, même défense qu'`audit_pivot_dataset.py`."""
    if not isinstance(valeur, str) or not valeur:
        return None
    try:
        horodatage = datetime.fromisoformat(valeur)
    except ValueError:
        return None
    return horodatage if horodatage.tzinfo is not None else horodatage.replace(tzinfo=timezone.utc)


def _report_amendements_figes_format(figees_dir: Path) -> tuple[list[str], str, str]:
    """Vérifie que les index amendements committés référencent les amendements
    par `uid` et non par `numero` (correction du 18/08/2026, voir
    docs/technical_decisions.md#amendements-cle-uid).

    **Hard fail**, contrairement au reste de la section 3d : un index au format
    hérité n'est pas une donnée périmée mais une donnée fausse. Le `numeroLong`
    de l'AN repart à chaque texte, si bien qu'un store keyé par `numero` écrase
    75 % des amendements et attribue 40 % des liens restants au mauvais texte —
    et rien, à la lecture, ne distingue ces enregistrements d'enregistrements
    corrects. Ces index étant committés dans le dépôt, seul un contrôle
    exécutable empêche de re-committer la régression ; une note de
    documentation ne l'empêcherait pas.

    Même ligne de conduite que le garde-fou de #427 (refuser de réécrire des
    profils sur une collecte incomplète plutôt que publier un zéro non mesuré) :
    échec bruyant plutôt que dégradation muette.

    Retourne (hard_errors, console_text, markdown_text).
    """
    hard_errors: list[str] = []
    conformes: list[str] = []
    absents: list[str] = []

    for legislature in sorted(_AMENDEMENTS_LEGISLATURES_FIGEES):
        index_path = figees_dir / legislature / "index_par_acteur.json.gz"
        if not index_path.is_file():
            # Absence traitée ailleurs (section 3d, « jamais construit ») : ce
            # contrôle-ci ne se prononce que sur le FORMAT de ce qui existe.
            absents.append(legislature)
            continue
        try:
            with gzip.open(index_path, "rt", encoding="utf-8") as f:
                index_par_acteur = json.load(f)
        except (OSError, ValueError) as exc:
            hard_errors.append(
                f"législature {legislature} : index figé illisible ({index_path}) — {exc}"
            )
            continue

        if _index_par_acteur_au_format_uid(index_par_acteur):
            conformes.append(legislature)
        else:
            hard_errors.append(
                f"législature {legislature} : index figé au format hérité (références par "
                f"'numero' et non 'uid') — 75 % des amendements y sont écrasés. "
                f"Reconstruire : python3 src/build_amendements_index_figees.py "
                f"--legislature {legislature} --download"
            )

    lignes = [
        "┌─ 3e/4  Format des index amendements figés ─────────────────────────",
        f"│  Conformes (clé uid) : {len(conformes)}   Absents : {len(absents)}   "
        f"Au format hérité : {len(hard_errors)}",
    ]
    for e in hard_errors:
        lignes.append(f"│  ✗ {e}")
    if not hard_errors:
        lignes.append("│  ✓ Tous les index figés présents référencent les amendements par uid.")
    lignes.append("└" + "─" * 68)

    md_lines = [
        "### 3e · Format des index amendements figés",
        "",
        "| Indicateur | Valeur |",
        "| --- | --- |",
        f"| Index conformes (clé `uid`) | {len(conformes)} |",
        f"| Index absents | {len(absents)} |",
        f"| Index au format hérité (clé `numero`) | {len(hard_errors)} |",
        "",
    ]
    if hard_errors:
        md_lines.append(
            "> ✗ **Index au format hérité** — les références par `numero` écrasent "
            "75 % des amendements et en attribuent 40 % au mauvais texte "
            "(`technical_decisions.md#amendements-cle-uid`). À reconstruire avant commit.\n"
        )
        for e in hard_errors:
            md_lines.append(f"> - {e}")
        md_lines.append("")
    else:
        md_lines.append("_Tous les index figés présents référencent les amendements par `uid`._\n")

    return hard_errors, "\n".join(lignes), "\n".join(md_lines)


def _report_amendements_freshness(
    cache_dir: Path,
    staleness_days: int,
    reference_date: datetime | None = None,
) -> tuple[list[str], str, str]:
    """Distingue, pour chaque législature AN d'amendements, un index jamais
    construit d'un index présent mais périmé (issue #254, sous-issue 6/6 de
    #248 — exploite l'indicateur de fraîcheur écrit par
    `_write_amendements_fraicheur`, candidate_profile.py, issue #253).

    Retourne (soft_warnings, console_text, markdown_text). Soft fail uniquement
    (n'empêche pas le commit), même traitement que le reste de la section 3c.

    Quatre états par législature :
      - jamais construit : aucun `index_par_acteur.json` en cache — jamais
        construit avec succès, ou pas encore présent dans ce job CI (voir
        `docs/technical_decisions.md#amendements-index-job-dedie-ci` pour le
        job dédié qui l'alimente).
      - périmé : index présent, mais soit `fraicheur.json` est absent/illisible
        (fraîcheur non garantie), soit sa dernière tentative connue a échoué
        (`derniere_construction_reussie: false`, index existant conservé), soit
        elle a réussi il y a plus de `staleness_days` jours.
      - figé : législature dans `_AMENDEMENTS_LEGISLATURES_FIGEES` avec un
        index dont `fraicheur.json` porte `figee: true` (committé par
        `build_amendements_index_figees.py`, jamais reconstruit) — aucune
        notion de péremption, jamais de warning (voir
        `docs/technical_decisions.md#amendements-legislatures-figees`).
      - frais : index présent, dernière tentative connue réussie et récente —
        pas de warning.
    """
    reference = reference_date if reference_date is not None else datetime.now(timezone.utc)

    soft_warnings: list[str] = []
    jamais_construit: list[str] = []
    perime: list[str] = []
    figees: list[str] = []
    frais: list[str] = []

    for legislature in _AMENDEMENTS_LEGISLATURES:
        # `amendements.json` + le RÉPERTOIRE de tranches par acteur (#392,
        # ex-fichier unique de #377). Ce rapport doit refléter le même verdict
        # que le lecteur réel (`candidate_profile._read_cached_amendements_acteur`,
        # qui exige les deux) : sinon il annoncerait « construit » un index
        # que la collecte ignore. Un cache hérité de l'un ou l'autre des
        # formats précédents est donc rapporté « jamais construit » — ce qui
        # est le comportement voulu, il sera reconstruit.
        index_path = cache_dir / legislature / "index_par_acteur"
        amendements_path = cache_dir / legislature / "amendements.json"
        if not index_path.is_dir() or not amendements_path.is_file():
            jamais_construit.append(legislature)
            soft_warnings.append(
                f"législature {legislature} : index jamais construit (aucun "
                f"{index_path.name} en cache)"
            )
            continue

        fraicheur_path = cache_dir / legislature / _AMENDEMENTS_FRAICHEUR_FILENAME
        fraicheur = _load_json(fraicheur_path) if fraicheur_path.is_file() else None
        if not isinstance(fraicheur, dict):
            perime.append(legislature)
            soft_warnings.append(
                f"législature {legislature} : index périmé — indicateur de fraîcheur "
                f"absent ou illisible ({_AMENDEMENTS_FRAICHEUR_FILENAME}), fraîcheur non garantie"
            )
            continue

        if legislature in _AMENDEMENTS_LEGISLATURES_FIGEES and fraicheur.get("figee"):
            figees.append(legislature)
            continue

        if not fraicheur.get("derniere_construction_reussie"):
            perime.append(legislature)
            soft_warnings.append(
                f"législature {legislature} : index périmé — dernière tentative de "
                "reconstruction en échec (index existant conservé, voir fraicheur.json)"
            )
            continue

        horodatage = _parse_amendements_horodatage(fraicheur.get("horodatage"))
        if horodatage is None:
            perime.append(legislature)
            soft_warnings.append(
                f"législature {legislature} : index périmé — horodatage de fraîcheur "
                "illisible, fraîcheur non garantie"
            )
            continue

        age_days = (reference - horodatage).days
        if age_days > staleness_days:
            perime.append(legislature)
            soft_warnings.append(
                f"législature {legislature} : index périmé — dernière reconstruction "
                f"réussie il y a {age_days} jour(s) (seuil {staleness_days})"
            )
        else:
            frais.append(legislature)

    icon = "✓" if not soft_warnings else "⚠"
    lines = [
        "",
        "┌─ 3d/4  Fraîcheur index amendements (AN) ───────────────────────────",
        f"│  Jamais construit : {len(jamais_construit)}   Périmé : {len(perime)}   "
        f"Figé : {len(figees)}   Frais : {len(frais)}",
        "│",
    ]
    if soft_warnings:
        lines.append("│  ⚠ Avertissements fraîcheur :")
        for w in soft_warnings:
            lines.append(f"│    · {w}")
    else:
        lines.append(f"│  {icon} Index de législature jamais-construit/périmé : aucun.")
    lines.append("└" + "─" * 67)
    console = "\n".join(lines)

    ok_icon = "✅" if not soft_warnings else "⚠️"
    md_lines = [
        "### 3d · Fraîcheur index amendements (AN)",
        "",
        "| Législature | État |",
        "|---|---|",
    ]
    for legislature in _AMENDEMENTS_LEGISLATURES:
        if legislature in jamais_construit:
            etat = "❌ jamais construit"
        elif legislature in perime:
            etat = "⚠️ périmé"
        elif legislature in figees:
            etat = "❄️ figé (dossier clos, non reconstruit)"
        else:
            etat = "✅ frais"
        md_lines.append(f"| {legislature} | {etat} |")
    md_lines += ["", f"| {ok_icon} Avertissements | {len(soft_warnings)} |", ""]
    if soft_warnings:
        md_lines += ["**Avertissements**", ""]
        for w in soft_warnings:
            md_lines.append(f"- {w}")
        md_lines.append("")
    else:
        md_lines.append("_Aucun index jamais-construit ou périmé._\n")

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
# Section 5 — Gouvernements
# ---------------------------------------------------------------------------

def _report_gouvernements(
    gouvernements_config_path: Path,
    gouvernements_dir: Path,
) -> tuple[list[str], list[str], str, str]:
    """Analyse la qualité des fichiers de profil de gouvernement générés.

    Miroir de `_report_groupes` (§4) — mêmes catégories hard/soft, adaptées
    au schéma `schema_gouvernement.py` (pas de notion de roster réseau : un
    gouvernement est agrégé localement depuis les profils pivot déjà
    présents, voir `docs/pipeline-profiles-groupes.md`).

    Retourne (hard_errors, soft_warnings, console_text, markdown_text).

    hard_errors  — chaque élément provoque exit_code=1 (structure cassée) :
      - fichier attendu manquant
      - JSON invalide
      - échec de validation de schéma (validate_profil_gouvernement)

    soft_warnings — signaux de qualité dégradée (n'empêchent pas le commit) :
      - couverture ministérielle incomplète (aucun/peu de `portefeuille`
        confirmé par une source primaire — limitation connue documentée dans
        docs/technical_decisions.md, §"Ministerial function")
      - `textes[]` vide alors que la période du gouvernement est **couverte**
        par les archives de dossiers ingérées (`couverture_dossiers.py`) —
        un gouvernement hors couverture n'est pas signalé comme un défaut,
        mais porté en information : l'absence y vient de la source, pas des
        données (#399, AGENTS.md §2.5)
      - IncompleteRead dans meta.warnings (signal réseau, propagé depuis
        `gouvernement_textes.py`)
    """
    # ── Lecture de la config ──────────────────────────────────────────────
    raw_cfg = _load_json(gouvernements_config_path)
    if raw_cfg is None:
        msg = f"Impossible de lire la config gouvernements : {gouvernements_config_path}"
        return (
            [msg],
            [],
            f"\n┌─ 5/5  Gouvernements ───────────────────────────────────────────────\n│  ✗ {msg}\n└{'─'*67}",
            f"### 5 · Gouvernements\n\n❌ {msg}\n",
        )

    expected: list[dict] = raw_cfg.get("gouvernements") or []

    hard_errors: list[str] = []
    soft_warnings: list[str] = []
    # Constats de couverture : affichés pour être lisibles, jamais comptés
    # comme des avertissements qualité — ils ne diminueront jamais (#399).
    infos: list[str] = []

    # ── Analyse par gouvernement attendu ──────────────────────────────────
    rows: list[dict] = []   # one row per expected gouvernement

    for gouv in expected:
        gouvernement_id = gouv.get("gouvernement_id", "?")
        fichier = gouv.get("fichier")
        if not fichier:
            hard_errors.append(f"{gouvernement_id}: champ 'fichier' absent de gouvernements_reels.json")
            rows.append({"gouvernement_id": gouvernement_id, "nom": gouv.get("nom", "?"),
                         "status": "hard", "detail": "config manquante"})
            continue

        path = gouvernements_dir / fichier

        # Hard 1 — fichier manquant
        if not path.exists():
            hard_errors.append(f"{gouvernement_id}: fichier manquant ({path})")
            rows.append({"gouvernement_id": gouvernement_id, "nom": gouv.get("nom", "?"),
                         "status": "hard", "detail": "fichier manquant"})
            continue

        # Hard 2 — JSON invalide
        data = _load_json(path)
        if data is None:
            hard_errors.append(f"{gouvernement_id}: JSON invalide ({fichier})")
            rows.append({"gouvernement_id": gouvernement_id, "nom": gouv.get("nom", "?"),
                         "status": "hard", "detail": "JSON invalide"})
            continue

        # Hard 3 — schéma invalide
        schema_errors: list[str] = []
        if _SCHEMA_GOUVERNEMENT_AVAILABLE:
            schema_errors = _validate_gouvernement(data)
        if schema_errors:
            detail = "; ".join(schema_errors[:3]) + ("…" if len(schema_errors) > 3 else "")
            hard_errors.append(f"{gouvernement_id}: schéma invalide — {detail}")
            rows.append({"gouvernement_id": gouvernement_id, "nom": gouv.get("nom", "?"),
                         "status": "hard", "detail": f"schéma invalide ({len(schema_errors)} erreur(s))"})
            continue

        # ── Données valides : contrôles de qualité ────────────────────────
        meta = data.get("meta") or {}
        warnings_list: list[str] = meta.get("warnings") or []
        membres = data.get("membres") or []
        textes = data.get("textes") or []
        periode = data.get("periode") or {}
        nb_membres = len(membres)
        nb_textes = len(textes)
        nb_portefeuille_connu = sum(1 for m in membres if m.get("portefeuille"))
        gouvernement_nom = data.get("nom") or gouvernement_id

        row_soft: list[str] = []
        row_status = "ok"

        # Soft 1 — couverture ministérielle incomplète (portefeuille non confirmé)
        if nb_membres > 0 and nb_portefeuille_connu < nb_membres:
            # Formulation : « confirmés par une source primaire » — l'absence
            # porte sur la confirmation, pas sur le portefeuille lui-même,
            # que le ministre a bien exercé (#399). Le compteur disparaîtra
            # avec #398, la formulation reste valable d'ici là.
            msg = (
                f"{gouvernement_id}: couverture ministérielle incomplète "
                f"({nb_portefeuille_connu}/{nb_membres} portefeuilles confirmés "
                f"par une source primaire — absence de confirmation, pas "
                f"absence de portefeuille)"
            )
            soft_warnings.append(msg)
            row_soft.append(f"portefeuilles {nb_portefeuille_connu}/{nb_membres}")
            row_status = "soft"

        # Soft 2 — signaux réseau IncompleteRead
        for w in warnings_list:
            if INCOMPLETE_READ_MARKER in w:
                endpoint = w.split(":")[0].strip() if ":" in w else "inconnu"
                msg = f"{gouvernement_id}: signal réseau IncompleteRead sur '{endpoint}'"
                soft_warnings.append(msg)
                row_soft.append(f"IncompleteRead ({endpoint})")
                row_status = "soft"

        # Soft 3 — textes[] vide sur une période **couverte** par la source.
        #
        # Hors couverture (période antérieure aux archives ingérées, ou à
        # cheval sur leur borne), l'absence de texte ne dit rien du
        # gouvernement : elle dit que la source s'arrête là. La signaler
        # comme un défaut de données afficherait une absence de source comme
        # un fait mesuré (#399, AGENTS.md §2.5) et noierait les vrais
        # signaux — ce qui avait masqué #397.
        couverture = statut_couverture_textes(periode.get("debut"), periode.get("fin"))
        if nb_textes == 0 and couverture == COUVERTURE_COUVERTE:
            msg = (
                f"{gouvernement_id}: aucun texte porté alors que la période est "
                f"couverte par la source ({libelle_couverture_textes()})"
            )
            soft_warnings.append(msg)
            row_soft.append("0 texte porté")
            row_status = "soft"
        elif nb_textes == 0 and couverture in (COUVERTURE_HORS, COUVERTURE_PARTIELLE):
            qualificatif = (
                "hors de la couverture de la source"
                if couverture == COUVERTURE_HORS
                else "seulement partiellement couverte par la source"
            )
            infos.append(
                f"{gouvernement_id}: aucun texte porté, période "
                f"{periode.get('debut')} → {periode.get('fin') or 'en cours'} "
                f"{qualificatif} — absence de source, pas un zéro constaté"
            )
            row_soft.append(f"textes {LIBELLES_COUVERTURE[couverture]}")

        rows.append({
            "gouvernement_id": gouvernement_id,
            "nom": gouvernement_nom,
            "nb_membres": nb_membres,
            "nb_portefeuille_connu": nb_portefeuille_connu,
            "nb_textes": nb_textes,
            "couverture": couverture,
            "status": row_status,
            "soft_flags": ", ".join(row_soft) if row_soft else "—",
        })

    # ── Hard — signature d'un écrasement massif (#427) ────────────────────
    #
    # `generate_gouvernement_profiles.py` refuse désormais de réécrire sur une
    # collecte incomplète, ce qui supprime la cause connue. Ce contrôle est le
    # filet : il attrape la MÊME signature quelle qu'en soit l'origine — bug de
    # collecte, régression de parsing, mauvaise fusion.
    #
    # Le critère porte sur la SIMULTANÉITÉ, pas sur un gouvernement isolé : un
    # gouvernement couvert peut légitimement n'avoir porté aucun texte
    # (Philippe I n'en a qu'un). En revanche, tous les gouvernements couverts
    # tombant à zéro au même instant n'est pas un état plausible du monde —
    # c'est la trace d'une collecte échouée en silence. D'où un hard, là où le
    # cas individuel reste un soft.
    couverts = [
        r for r in rows
        if r.get("couverture") == COUVERTURE_COUVERTE and r.get("nb_membres", 0) > 0
    ]
    if len(couverts) >= 2 and all(r["nb_textes"] == 0 for r in couverts):
        hard_errors.append(
            f"tous les gouvernements couverts par la source ({len(couverts)}) ont "
            "textes[] vide simultanément — signature d'une collecte échouée, pas "
            "d'un zéro constaté (#427)"
        )

    # ── Résumé global ─────────────────────────────────────────────────────
    n_hard = len(hard_errors)
    n_soft = len(soft_warnings)
    n_ok = sum(1 for r in rows if r["status"] == "ok")

    # ── Console ──────────────────────────────────────────────────────────────
    lines = [
        "",
        "┌─ 5/5  Gouvernements ───────────────────────────────────────────────",
        f"│  Attendus : {len(expected)}   OK : {n_ok}   "
        f"Échecs durs : {n_hard}   Avertissements : {n_soft}",
        f"│  Couverture des textes : {libelle_couverture_textes()}",
        "│",
    ]
    if not _SCHEMA_GOUVERNEMENT_AVAILABLE:
        lines.append("│  [!] schema_gouvernement non disponible — validation de schéma ignorée.")
        lines.append("│")
    if infos:
        lines.append("│  ℹ Hors couverture de la source (pas un défaut de données) :")
        for i in infos:
            lines.append(f"│    · {i}")
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
    header = f"│  {'Gouvernement':<24} {'Portefeuilles':>15}  {'Membres':>8}  {'Textes':>6}  Flags"
    lines.append(header)
    lines.append("│  " + "─" * 72)
    for r in rows:
        status_marker = "✗" if r["status"] == "hard" else ("⚠" if r["status"] == "soft" else "✓")
        portefeuilles = f"{r.get('nb_portefeuille_connu','?')}/{r.get('nb_membres','?')}"
        membres = str(r.get("nb_membres", "?"))
        textes = str(r.get("nb_textes", "?"))
        flags = r.get("soft_flags", "—")
        if r["status"] == "hard":
            flags = r.get("detail", "—")
            portefeuilles = "—"
            membres = "—"
            textes = "—"
        lines.append(
            f"│  {status_marker} {r['nom']:<22} {portefeuilles:>15}"
            f"  {membres:>8}  {textes:>6}  {flags}"
        )
    lines.append("└" + "─" * 67)
    console = "\n".join(lines)

    # ── Markdown ──────────────────────────────────────────────────────────
    overall_md = "✅" if n_hard == 0 and n_soft == 0 else ("❌" if n_hard > 0 else "⚠️")
    md_lines = [
        "### 5 · Gouvernements",
        "",
        f"| | Nb |",
        "|---|---|",
        f"| {overall_md} Attendus | {len(expected)} |",
        f"| ✅ Valides | {n_ok} |",
        f"| ❌ Échecs durs | {n_hard} |",
        f"| ⚠️ Avertissements qualité | {n_soft} |",
        f"| ℹ️ Hors couverture de la source | {len(infos)} |",
        "",
        f"> Couverture des textes portés : **{libelle_couverture_textes()}**. "
        "Hors de cette borne, un `textes[]` vide est une absence de source, "
        "pas un zéro constaté — jamais compté comme un avertissement qualité "
        "(#399, AGENTS.md §2.5).",
        "",
    ]
    if not _SCHEMA_GOUVERNEMENT_AVAILABLE:
        md_lines.append("> ⚠️ `schema_gouvernement` non importé — validation de schéma ignorée.\n")

    if infos:
        md_lines += [
            "**Hors couverture de la source** _(pas un défaut de données)_",
            "",
            "| Gouvernement | Constat |",
            "|---|---|",
        ]
        for i in infos:
            gouvernement_id, _, detail = i.partition(": ")
            md_lines.append(f"| `{gouvernement_id}` | {detail} |")
        md_lines.append("")

    if hard_errors:
        md_lines += [
            "**Erreurs dures** _(bloquent le commit)_",
            "",
            "| Gouvernement | Problème |",
            "|---|---|",
        ]
        for r in rows:
            if r["status"] == "hard":
                md_lines.append(f"| `{r['gouvernement_id']}` | {r.get('detail', '?')} |")
        md_lines.append("")

    md_lines += [
        "**Détail par gouvernement**",
        "",
        "| Gouvernement | Portefeuilles confirmés | Membres | Textes | Flags |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        status_icon = "❌" if r["status"] == "hard" else ("⚠️" if r["status"] == "soft" else "✅")
        portefeuilles = (
            f"{r.get('nb_portefeuille_connu','?')}/{r.get('nb_membres','?')}"
            if r["status"] != "hard" else "—"
        )
        flags = r.get("soft_flags", "—") if r["status"] != "hard" else r.get("detail", "—")
        md_lines.append(
            f"| {status_icon} {r['nom']} | {portefeuilles} "
            f"| {r.get('nb_membres','?') if r['status'] != 'hard' else '—'} "
            f"| {r.get('nb_textes','?') if r['status'] != 'hard' else '—'} | {flags} |"
        )
    md_lines.append("")

    return hard_errors, soft_warnings, console, "\n".join(md_lines)


# ---------------------------------------------------------------------------
# Section 6 — Couverture ParlTrack (optionnelle)
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
            f"\n┌─ 6/6  Enrichissement ParlTrack ────────────────────────────────────\n│  ⚠ {msg}\n└{'─'*67}",
            f"### 6 · Enrichissement ParlTrack\n\n⚠️ {msg}\n",
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
        "┌─ 6/6  Enrichissement ParlTrack ────────────────────────────────────",
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
        "### 6 · Enrichissement ParlTrack",
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

def _build_arg_parser() -> argparse.ArgumentParser:
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
        "--gouvernements-dir",
        type=Path,
        default=Path("pivot_data/gouvernements"),
        dest="gouvernements_dir",
        help="Répertoire des profils de gouvernement générés (défaut : pivot_data/gouvernements).",
    )
    parser.add_argument(
        "--gouvernements-config",
        type=Path,
        default=Path("raw_data/gouvernements_reels.json"),
        dest="gouvernements_config",
        help="Config des gouvernements attendus (défaut : raw_data/gouvernements_reels.json).",
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
        "--amendements-cache-dir",
        type=Path,
        default=Path(".cache") / "amendements_an",
        dest="amendements_cache_dir",
        help=(
            "Répertoire de cache des index amendements AN, alimenté par le job CI "
            "dédié extract-amendements-an (défaut : .cache/amendements_an)."
        ),
    )
    parser.add_argument(
        "--amendements-figes-dir",
        type=Path,
        default=_AMENDEMENTS_FIGEES_DIR_DEFAUT,
        dest="amendements_figes_dir",
        help=(
            "Répertoire des index amendements committés des législatures figées "
            "(défaut : raw_data/amendements_an_figes). Leur format de clé est "
            "vérifié en échec dur, voir section 3e."
        ),
    )
    parser.add_argument(
        "--amendements-staleness-days",
        type=int,
        default=_AMENDEMENTS_STALENESS_DAYS_DEFAULT,
        dest="amendements_staleness_days",
        help=(
            "Seuil (jours) au-delà duquel un index amendements présent mais sans "
            f"reconstruction réussie récente est signalé comme périmé (défaut : "
            f"{_AMENDEMENTS_STALENESS_DAYS_DEFAULT}). 0 = désactivé."
        ),
    )
    parser.add_argument(
        "--parltrack-status-file",
        type=Path,
        default=None,
        dest="parltrack_status_file",
        help=(
            "Fichier JSON produit par generate_all_profiles.py --parltrack-status-out. "
            "Active la section 6 du rapport (enrichissement ParlTrack ce run vs fallback)."
        ),
    )
    return parser


def main() -> int:
    parser = _build_arg_parser()
    args = parser.parse_args()

    run_date = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # ── Section 1 : IncompleteRead ─────────────────────────────────────────
    ir_dirs = {
        "pivot_data/profiles": args.profiles_dir,
        "pivot_data/groupes": args.groupes_dir,
        "pivot_data/partis": args.partis_dir,
        "pivot_data/gouvernements": args.gouvernements_dir,
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

    # ── Section 3c : Couverture amendements (AN) ───────────────────────────
    amd_soft, amd_regression, amd_console, amd_md = _report_amendements_coverage(args.profiles_dir)

    # ── Section 3d : Fraîcheur index amendements (AN) ──────────────────────
    amdf_soft: list[str] = []
    amdf_console = ""
    amdf_md = ""
    if args.amendements_staleness_days > 0:
        amdf_soft, amdf_console, amdf_md = _report_amendements_freshness(
            args.amendements_cache_dir, args.amendements_staleness_days
        )

    # ── Section 3e : Format des index amendements figés ────────────────────
    # Échec dur, contrairement à 3c/3d : un index keyé par `numero` porte des
    # amendements attribués au mauvais texte, pas des données simplement
    # périmées (docs/technical_decisions.md#amendements-cle-uid).
    amdfmt_hard, amdfmt_console, amdfmt_md = _report_amendements_figes_format(
        args.amendements_figes_dir
    )
    amdfmt_exit = 1 if amdfmt_hard else 0

    # ── Section 4 : Groupes parlementaires ────────────────────────────────
    grp_hard, grp_soft, grp_console, grp_md = _report_groupes(
        args.groupes_config, args.groupes_dir, args.groupe_min_members,
        min_coverage_pct=args.groupe_min_coverage_pct,
    )
    grp_exit = 1 if grp_hard else 0

    # ── Section 5 : Gouvernements ───────────────────────────────────────────
    gouv_hard, gouv_soft, gouv_console, gouv_md = _report_gouvernements(
        args.gouvernements_config, args.gouvernements_dir,
    )
    gouv_exit = 1 if gouv_hard else 0

    # ── Section 6 : Couverture ParlTrack (optionnelle) ─────────────────────
    pt_console = ""
    pt_md = ""
    if args.parltrack_status_file is not None:
        pt_console, pt_md = _report_parltrack_status(args.parltrack_status_file)

    # Les sections 3c/3d n'entrent PAS dans exit_code : « 0 amendement collecté »
    # et « index jamais construit » restent des signaux non bloquants, décision
    # #378 (docs/technical_decisions.md#amendements-zero-pas-de-hard-fail). Le
    # signal global de 3c est en revanche affiché en tête de rapport ci-dessous.
    exit_code = 1 if (
        ir_exit == 1 or grp_exit == 1 or gouv_exit == 1 or amdfmt_exit == 1
    ) else 0

    # ── Sortie console ─────────────────────────────────────────────────────
    gate_label = "✓ COMMIT AUTORISÉ" if exit_code == 0 else "✗ COMMIT BLOQUÉ"
    print(f"\n{'═'*69}")
    print(f"  RÉSUMÉ DU RUN  —  {run_date}")
    print(f"  Quality gate : {gate_label}")
    if amd_regression is not None:
        print(f"  {_AMENDEMENTS_ZERO_ICONE} Amendements — {amd_regression}")
        print(f"     Signal non bloquant ({_AMENDEMENTS_ZERO_DECISION_REF}).")
    print(f"{'═'*69}")
    print(ir_console)
    print(cov_console)
    print(low_console)
    if syc_console:
        print(syc_console)
    print(amd_console)
    if amdf_console:
        print(amdf_console)
    print(amdfmt_console)
    print(grp_console)
    print(gouv_console)
    if pt_console:
        print(pt_console)
    print()

    # ── GitHub Step Summary (Markdown) ────────────────────────────────────
    gate_badge = "✅ Commit autorisé" if exit_code == 0 else "❌ Commit bloqué"
    banniere_md = (
        [
            f"> {_AMENDEMENTS_ZERO_ICONE} **Amendements** : {amd_regression} "
            f"— signal non bloquant (`{_AMENDEMENTS_ZERO_DECISION_REF}`), voir §3c.",
            "",
        ]
        if amd_regression is not None
        else []
    )
    md = "\n".join([
        f"## 📊 Résumé du run pipeline — {run_date}",
        "",
        f"> **Quality gate** : {gate_badge}",
        "",
        *banniere_md,
        ir_md,
        cov_md,
        low_md,
        syc_md,
        amd_md,
        amdf_md,
        amdfmt_md,
        grp_md,
        gouv_md,
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
    for err in gouv_hard:
        _gha_annotation("error", f"Gouvernement — structure cassée : {err}")
    for warn in gouv_soft:
        _gha_annotation("warning", f"Gouvernement — qualité dégradée : {warn}")
    for warn in syc_soft:
        _gha_annotation("warning", f"Syceron — couverture faible : {warn}")
    for warn in amd_soft:
        if warn == amd_regression:
            _gha_annotation(
                "warning",
                f"Amendements — {_AMENDEMENTS_ZERO_ICONE} RÉGRESSION PROBABLE DE COLLECTE "
                f"(non bloquant, {_AMENDEMENTS_ZERO_DECISION_REF}) : {warn}",
            )
        else:
            _gha_annotation("warning", f"Amendements — {warn}")
    for warn in amdf_soft:
        _gha_annotation("warning", f"Amendements fraîcheur — {warn}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
