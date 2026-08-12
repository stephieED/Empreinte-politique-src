import argparse
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import generate_all_profiles
from generate_all_profiles import _select_candidats, load_candidats, process_candidat


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
        "synthese_activite": None,
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
