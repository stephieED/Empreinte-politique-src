import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import generate_all_profiles
from generate_all_profiles import (
    _select_candidats,
    _select_candidats_couverture,
    load_candidats,
    process_candidat,
)


def _fake_raw_profile(slug: str, chambre: str = "deputes") -> dict:
    return {
        "slug": slug,
        "chambre": chambre,
        "source": f"https://www.nosdeputes.fr/{slug}",
        "identite": {
            "nom_complet": slug.title(),
            "groupe_sigle": "LR",
            "groupe_nom": "Les Républicains",
            "profession": None,
            "date_naissance": None,
            "num_circo": None,
            "nb_mandats": None,
            "url_an_ou_senat": None,
        },
        "mandats": [],
        "votes": [],
        "votes_source": None,
        "dossiers_legislatifs": [],
        "interventions": [],
        "meta": {
            "genere_le": "2026-08-12T00:00:00+0000",
            "licence_donnees": "ODbL",
            "warnings": [],
        },
    }


def _make_args(**overrides) -> argparse.Namespace:
    base = dict(
        source="all",
        pivot_only=False,
        skip_existing=False,
        max_pages=1,
        skip_interventions=True,
        skip_ue=True,
        pivot=True,
        no_merge=False,
        enrich_parltrack=False,
    )
    base.update(overrides)
    return argparse.Namespace(**base)


# ---------------------------------------------------------------------------
# load_candidats : fichier --candidats alternatif
# ---------------------------------------------------------------------------

def test_load_candidats_alternate_file(tmp_path):
    candidats_path = tmp_path / "roster_candidats.json"
    candidats_path.write_text(
        json.dumps({"candidats": [{"nom": "Alice", "slug": "alice", "statut": "roster_groupe"}]}),
        encoding="utf-8",
    )

    candidats = load_candidats(str(candidats_path))

    assert candidats == [{"nom": "Alice", "slug": "alice", "statut": "roster_groupe"}]


def test_load_candidats_missing_key_returns_empty_list(tmp_path):
    candidats_path = tmp_path / "empty.json"
    candidats_path.write_text(json.dumps({}), encoding="utf-8")

    assert load_candidats(str(candidats_path)) == []


# ---------------------------------------------------------------------------
# _select_candidats : --limit / --sample (déploiement progressif)
# ---------------------------------------------------------------------------

def test_select_candidats_no_filter_returns_all():
    candidats = [{"slug": "a"}, {"slug": "b"}]
    assert _select_candidats(candidats) == candidats


def test_select_candidats_limit_takes_first_n_in_order():
    candidats = [{"slug": f"c{i}"} for i in range(5)]
    assert _select_candidats(candidats, limit=2) == candidats[:2]


def test_select_candidats_limit_larger_than_list_returns_all():
    candidats = [{"slug": "a"}, {"slug": "b"}]
    assert _select_candidats(candidats, limit=10) == candidats


def test_select_candidats_sample_returns_subset_of_requested_size():
    candidats = [{"slug": f"c{i}"} for i in range(10)]
    result = _select_candidats(candidats, sample=3)
    assert len(result) == 3
    assert all(c in candidats for c in result)
    # pas de doublon
    assert len({c["slug"] for c in result}) == 3


def test_select_candidats_sample_larger_than_list_returns_all():
    candidats = [{"slug": "a"}, {"slug": "b"}]
    result = _select_candidats(candidats, sample=10)
    assert len(result) == 2
    assert {c["slug"] for c in result} == {"a", "b"}


def test_cli_limit_and_sample_are_mutually_exclusive(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["generate_all_profiles.py", "--limit", "1", "--sample", "1"])
    with pytest.raises(SystemExit):
        generate_all_profiles.main()


# ---------------------------------------------------------------------------
# _select_candidats_couverture : sélection progressive + rafraîchissement
# pour --limit + --skip-existing (#224)
# ---------------------------------------------------------------------------

_REF_DATE = datetime(2026, 8, 12, tzinfo=timezone.utc)


def _fake_pivot(slug: str, jours_anciennete: int) -> dict:
    synchro = _REF_DATE - timedelta(days=jours_anciennete)
    return {
        "id": f"nosdeputes:{slug}",
        "sources": [{"type": "nosdeputes", "url": f"https://x/{slug}", "synchro_le": synchro.isoformat()}],
    }


def _write_pivot(pivot_dir: Path, slug: str, jours_anciennete: int) -> None:
    (pivot_dir / f"{slug}.pivot.json").write_text(
        json.dumps(_fake_pivot(slug, jours_anciennete)), encoding="utf-8"
    )


def test_select_candidats_couverture_progressive_no_pivots_takes_first_n(tmp_path):
    candidats = [{"slug": f"c{i}"} for i in range(30)]
    selection, refresh = _select_candidats_couverture(
        candidats, tmp_path, limit=10, staleness_days=30, reference_date=_REF_DATE
    )
    assert [c["slug"] for c in selection] == [f"c{i}" for i in range(10)]
    assert refresh == set()


def test_select_candidats_couverture_progresses_across_simulated_runs(tmp_path):
    candidats = [{"slug": f"c{i}"} for i in range(30)]

    # Run 1 : rien n'est couvert -> les 10 premiers.
    run1, _ = _select_candidats_couverture(
        candidats, tmp_path, limit=10, staleness_days=30, reference_date=_REF_DATE
    )
    assert [c["slug"] for c in run1] == [f"c{i}" for i in range(10)]

    # Les 10 premiers sont désormais couverts et frais (pas de péremption).
    for c in run1:
        _write_pivot(tmp_path, c["slug"], jours_anciennete=1)

    # Run 2 : sans correctif, --limit reprendrait les mêmes 10 premiers.
    run2, refresh2 = _select_candidats_couverture(
        candidats, tmp_path, limit=10, staleness_days=30, reference_date=_REF_DATE
    )
    assert [c["slug"] for c in run2] == [f"c{i}" for i in range(10, 20)]
    assert refresh2 == set()


def test_select_candidats_couverture_prioritizes_non_couverts_then_fills_with_perimes(tmp_path):
    # 3 non-couverts, 2 couverts périmés -> limit 4 doit prendre les 3
    # non-couverts + 1 périmé (budget restant = 1).
    candidats = [{"slug": "new1"}, {"slug": "new2"}, {"slug": "new3"}, {"slug": "old1"}, {"slug": "old2"}]
    _write_pivot(tmp_path, "old1", jours_anciennete=60)
    _write_pivot(tmp_path, "old2", jours_anciennete=90)

    selection, refresh = _select_candidats_couverture(
        candidats, tmp_path, limit=4, staleness_days=30, reference_date=_REF_DATE
    )

    slugs = [c["slug"] for c in selection]
    assert slugs[:3] == ["new1", "new2", "new3"]
    assert len(slugs) == 4
    assert slugs[3] in {"old1", "old2"}
    assert refresh == {slugs[3]}


def test_select_candidats_couverture_refreshes_stale_covered_profile(tmp_path):
    candidats = [{"slug": "old1"}]
    _write_pivot(tmp_path, "old1", jours_anciennete=60)

    selection, refresh = _select_candidats_couverture(
        candidats, tmp_path, limit=5, staleness_days=30, reference_date=_REF_DATE
    )

    assert [c["slug"] for c in selection] == ["old1"]
    assert refresh == {"old1"}


def test_select_candidats_couverture_does_not_reselect_fresh_covered_profile(tmp_path):
    # Non-régression : un profil couvert et frais n'est ni resélectionné, ni
    # compté dans le budget de conquête, même si du budget --limit reste.
    candidats = [{"slug": "fresh1"}]
    _write_pivot(tmp_path, "fresh1", jours_anciennete=5)

    selection, refresh = _select_candidats_couverture(
        candidats, tmp_path, limit=5, staleness_days=30, reference_date=_REF_DATE
    )

    assert selection == []
    assert refresh == set()


def test_select_candidats_couverture_budget_exhausted_by_non_couverts_ignores_perimes(tmp_path):
    candidats = [{"slug": "new1"}, {"slug": "new2"}, {"slug": "old1"}]
    _write_pivot(tmp_path, "old1", jours_anciennete=90)

    selection, refresh = _select_candidats_couverture(
        candidats, tmp_path, limit=2, staleness_days=30, reference_date=_REF_DATE
    )

    assert [c["slug"] for c in selection] == ["new1", "new2"]
    assert refresh == set()


# ---------------------------------------------------------------------------
# process_candidat : propagation de meta.provenance selon candidat["statut"]
# ---------------------------------------------------------------------------

def test_process_candidat_roster_groupe_sets_provenance(tmp_path, monkeypatch):
    monkeypatch.setattr(generate_all_profiles, "build_profile", lambda *a, **k: _fake_raw_profile("alice"))
    monkeypatch.setattr(generate_all_profiles.time, "sleep", lambda *_: None)

    out_dir = tmp_path / "profiles"
    pivot_dir = tmp_path / "pivots"
    out_dir.mkdir()
    pivot_dir.mkdir()

    candidat = {"nom": "Alice", "slug": "alice", "parti": None, "statut": "roster_groupe"}
    resultat = process_candidat(candidat, _make_args(), out_dir, pivot_dir)

    assert resultat["statut"] == "ok"
    pivot = json.loads((pivot_dir / "alice.pivot.json").read_text(encoding="utf-8"))
    assert pivot["meta"]["provenance"] == "roster_groupe"
    assert pivot["parti"] is None


def test_process_candidat_default_statut_sets_candidat_declare_provenance(tmp_path, monkeypatch):
    monkeypatch.setattr(generate_all_profiles, "build_profile", lambda *a, **k: _fake_raw_profile("bob"))
    monkeypatch.setattr(generate_all_profiles.time, "sleep", lambda *_: None)

    out_dir = tmp_path / "profiles"
    pivot_dir = tmp_path / "pivots"
    out_dir.mkdir()
    pivot_dir.mkdir()

    # Candidat éditorial classique (raw_data/candidats.json) : pas de champ "statut".
    candidat = {"nom": "Bob", "slug": "bob", "parti": "Parti Test"}
    resultat = process_candidat(candidat, _make_args(), out_dir, pivot_dir)

    assert resultat["statut"] == "ok"
    pivot = json.loads((pivot_dir / "bob.pivot.json").read_text(encoding="utf-8"))
    assert pivot["meta"]["provenance"] == "candidat_declare"
    assert pivot["parti"] == "Parti Test"


# ---------------------------------------------------------------------------
# process_candidat : --skip-existing sur un candidat issu du roster
# ---------------------------------------------------------------------------

def test_process_candidat_skip_existing_does_not_call_network(tmp_path, monkeypatch):
    call_count = {"n": 0}

    def fake_build_profile(*a, **k):
        call_count["n"] += 1
        return _fake_raw_profile("carla")

    monkeypatch.setattr(generate_all_profiles, "build_profile", fake_build_profile)

    out_dir = tmp_path / "profiles"
    pivot_dir = tmp_path / "pivots"
    out_dir.mkdir()
    pivot_dir.mkdir()
    (out_dir / "carla.json").write_text(json.dumps(_fake_raw_profile("carla")), encoding="utf-8")

    candidat = {"nom": "Carla", "slug": "carla", "statut": "roster_groupe"}
    resultat = process_candidat(candidat, _make_args(skip_existing=True), out_dir, pivot_dir)

    assert resultat["statut"] == "deja_present"
    assert call_count["n"] == 0


def test_process_candidat_refresh_slugs_bypasses_skip_existing(tmp_path, monkeypatch):
    # #224 : un slug listé dans refresh_slugs doit repasser par le fetch +
    # merge additif même si --skip-existing est actif et le profil existe déjà.
    call_count = {"n": 0}

    def fake_build_profile(*a, **k):
        call_count["n"] += 1
        return _fake_raw_profile("dave")

    monkeypatch.setattr(generate_all_profiles, "build_profile", fake_build_profile)
    monkeypatch.setattr(generate_all_profiles.time, "sleep", lambda *_: None)

    out_dir = tmp_path / "profiles"
    pivot_dir = tmp_path / "pivots"
    out_dir.mkdir()
    pivot_dir.mkdir()
    (out_dir / "dave.json").write_text(json.dumps(_fake_raw_profile("dave")), encoding="utf-8")

    candidat = {"nom": "Dave", "slug": "dave", "statut": "roster_groupe"}
    resultat = process_candidat(
        candidat, _make_args(skip_existing=True), out_dir, pivot_dir, refresh_slugs={"dave"}
    )

    assert resultat["statut"] == "ok"
    assert call_count["n"] == 1


# ---------------------------------------------------------------------------
# main() : intégration légère (réseau mocké) sur un lot roster + --resume
# ---------------------------------------------------------------------------

def _write_roster_candidats(path: Path, slugs: list[str]) -> None:
    path.write_text(
        json.dumps({
            "candidats": [
                {"nom": slug.title(), "slug": slug, "parti": None, "statut": "roster_groupe"}
                for slug in slugs
            ]
        }),
        encoding="utf-8",
    )


def test_integration_roster_batch_produces_pivots_with_provenance(tmp_path, monkeypatch):
    candidats_path = tmp_path / "roster_candidats.json"
    _write_roster_candidats(candidats_path, ["alice", "bob"])

    monkeypatch.setattr(
        generate_all_profiles, "build_profile", lambda chambre, slug, **k: _fake_raw_profile(slug, chambre)
    )
    monkeypatch.setattr(generate_all_profiles.time, "sleep", lambda *_: None)

    out_dir = tmp_path / "profiles"
    pivot_dir = tmp_path / "pivots"
    checkpoint_path = tmp_path / "checkpoint.json"

    monkeypatch.setattr(sys, "argv", [
        "generate_all_profiles.py",
        "--candidats", str(candidats_path),
        "--out-dir", str(out_dir),
        "--pivot-dir", str(pivot_dir),
        "--pivot", "--skip-ue", "--skip-interventions",
        "--checkpoint-file", str(checkpoint_path),
        "--workers", "2",
    ])

    generate_all_profiles.main()

    for slug in ("alice", "bob"):
        pivot = json.loads((pivot_dir / f"{slug}.pivot.json").read_text(encoding="utf-8"))
        assert pivot["meta"]["provenance"] == "roster_groupe"


def test_resume_skips_already_processed_roster_candidats(tmp_path, monkeypatch):
    candidats_path = tmp_path / "roster_candidats.json"
    _write_roster_candidats(candidats_path, ["alice", "bob"])

    call_count = {"n": 0}

    def fake_build_profile(chambre, slug, **k):
        call_count["n"] += 1
        return _fake_raw_profile(slug, chambre)

    monkeypatch.setattr(generate_all_profiles, "build_profile", fake_build_profile)
    monkeypatch.setattr(generate_all_profiles.time, "sleep", lambda *_: None)

    out_dir = tmp_path / "profiles"
    pivot_dir = tmp_path / "pivots"
    checkpoint_path = tmp_path / "checkpoint.json"

    argv_base = [
        "generate_all_profiles.py",
        "--candidats", str(candidats_path),
        "--out-dir", str(out_dir),
        "--pivot-dir", str(pivot_dir),
        "--skip-ue", "--skip-interventions",
        "--checkpoint-file", str(checkpoint_path),
        "--workers", "2",
    ]

    monkeypatch.setattr(sys, "argv", argv_base)
    generate_all_profiles.main()
    assert call_count["n"] == 2

    # Deuxième run avec --resume : les deux candidats sont déjà "ok" dans le
    # checkpoint, donc ignorés avant même d'appeler build_profile — le
    # comportement de reprise est identique pour un lot roster-driven, sans
    # code spécifique (critère d'acceptation de non-régression).
    monkeypatch.setattr(sys, "argv", argv_base + ["--resume"])
    generate_all_profiles.main()
    assert call_count["n"] == 2

    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    assert {r["slug"] for r in checkpoint["resultats"]} == {"alice", "bob"}


def test_integration_progressive_selection_advances_across_two_runs(tmp_path, monkeypatch):
    """Critère d'acceptation #224 : un run avec --limit fixe fait progresser
    la couverture du roster à chaque exécution successive, sans intervention
    manuelle. Simule deux dispatches CI successifs (pas de --resume entre les
    deux, out-dir/pivot-dir "committés" comme raw_data/profiles + pivot_data/
    profiles le sont réellement entre deux runs de generate-data.yml)."""
    candidats_path = tmp_path / "roster_candidats.json"
    slugs = [f"m{i}" for i in range(6)]
    _write_roster_candidats(candidats_path, slugs)

    call_log: list[str] = []

    def fake_build_profile(chambre, slug, **k):
        call_log.append(slug)
        return _fake_raw_profile(slug, chambre)

    monkeypatch.setattr(generate_all_profiles, "build_profile", fake_build_profile)
    monkeypatch.setattr(generate_all_profiles.time, "sleep", lambda *_: None)

    out_dir = tmp_path / "profiles"
    pivot_dir = tmp_path / "pivots"

    argv_base = [
        "generate_all_profiles.py",
        "--candidats", str(candidats_path),
        "--out-dir", str(out_dir),
        "--pivot-dir", str(pivot_dir),
        "--pivot", "--skip-ue", "--skip-interventions",
        "--no-checkpoint",
        "--workers", "2",
        "--limit", "2", "--skip-existing",
    ]

    # Run 1 : rien n'est couvert -> les 2 premiers (m0, m1).
    monkeypatch.setattr(sys, "argv", argv_base)
    generate_all_profiles.main()
    assert set(call_log) == {"m0", "m1"}

    # Run 2 : sans le correctif #224, --limit resélectionnerait m0/m1 (déjà
    # couverts) et --skip-existing les sauterait tous les deux -> plus aucun
    # candidat ne serait jamais traité. Avec le correctif, la sélection
    # avance à m2/m3.
    call_log.clear()
    monkeypatch.setattr(sys, "argv", argv_base)
    generate_all_profiles.main()
    assert set(call_log) == {"m2", "m3"}
