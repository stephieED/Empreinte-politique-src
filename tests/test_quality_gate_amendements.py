"""Tests de non-régression pour la couverture amendements dans check_quality_gate.py
(issue #185 : une régression de collecte qui vide amendements[] sur tous les
candidats AN n'était détectée par aucune section du quality gate)."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from check_quality_gate import _report_amendements_coverage


def _write_pivot(tmp_path: Path, slug: str, chambre: str, identite, amendements: list, warnings: list) -> None:
    profile = {
        "id": f"nd:{slug}",
        "nom": slug.replace("-", " ").title(),
        "chambre": chambre,
        "identite": identite,
        "mandats": [],
        "interventions": [],
        "votes": [],
        "textes_portes": [],
        "amendements": amendements,
        "tags_thematiques": [],
        "sources": [],
        "meta": {"warnings": warnings},
    }
    (tmp_path / f"{slug}.pivot.json").write_text(json.dumps(profile), encoding="utf-8")


def test_report_amendements_coverage_flags_global_regression_when_all_empty(tmp_path):
    """Plusieurs candidats AN avec identité mais amendements[] vide partout :
    doit déclencher un soft warning global (régression de collecte)."""
    _write_pivot(tmp_path, "jean-dupont", "AN", {"nom_complet": "Jean Dupont"}, amendements=[], warnings=[])
    _write_pivot(tmp_path, "marie-martin", "AN", {"nom_complet": "Marie Martin"}, amendements=[], warnings=[])

    soft, console, md = _report_amendements_coverage(tmp_path)

    assert len(soft) == 1
    assert "2" in soft[0]
    assert "⚠" in console
    assert "⚠️" in md


def test_report_amendements_coverage_no_warning_when_some_have_amendements(tmp_path):
    """Si au moins un candidat AN a des amendements collectés, pas de warning global."""
    _write_pivot(
        tmp_path,
        "jean-dupont",
        "AN",
        {"nom_complet": "Jean Dupont"},
        amendements=[{"sort": "adopté", "type_deposant": "depute"}],
        warnings=[],
    )
    _write_pivot(tmp_path, "marie-martin", "AN", {"nom_complet": "Marie Martin"}, amendements=[], warnings=[])

    soft, console, md = _report_amendements_coverage(tmp_path)

    assert len(soft) == 0
    assert "✓" in console


def test_report_amendements_coverage_flags_per_candidate_fetch_failure(tmp_path):
    """Un warning 'amendements indisponibles' dans meta.warnings doit être
    remonté individuellement, même si d'autres candidats ont bien des amendements."""
    _write_pivot(
        tmp_path,
        "jean-dupont",
        "AN",
        {"nom_complet": "Jean Dupont"},
        amendements=[],
        warnings=["amendements indisponibles : échec du téléchargement (boom)"],
    )
    _write_pivot(
        tmp_path,
        "marie-martin",
        "AN",
        {"nom_complet": "Marie Martin"},
        amendements=[{"sort": "adopté", "type_deposant": "depute"}],
        warnings=[],
    )

    soft, console, md = _report_amendements_coverage(tmp_path)

    assert any("jean-dupont" in w for w in soft)
    # Pas de régression globale puisque marie-martin a bien des amendements.
    assert not any("aucun candidat AN" in w for w in soft)


def test_report_amendements_coverage_ignores_candidates_without_identite(tmp_path):
    """Un candidat AN sans identité (non éligible à la collecte d'amendements
    officiels côté candidate_profile.py) ne doit pas être compté."""
    _write_pivot(tmp_path, "sans-identite", "AN", None, amendements=[], warnings=[])

    soft, console, md = _report_amendements_coverage(tmp_path)

    assert len(soft) == 0
    assert "0" in console


def test_report_amendements_coverage_ignores_non_an_candidates(tmp_path):
    """Les candidats non-AN (Sénat...) ne doivent pas être comptés dans la couverture."""
    _write_pivot(tmp_path, "senateur-x", "Senat", {"nom_complet": "Senateur X"}, amendements=[], warnings=[])

    soft, console, md = _report_amendements_coverage(tmp_path)

    assert len(soft) == 0


def test_report_amendements_coverage_empty_dir_returns_no_warning(tmp_path):
    """Aucun profil AN analysé : pas de faux positif sur régression globale."""
    soft, console, md = _report_amendements_coverage(tmp_path)
    assert len(soft) == 0
