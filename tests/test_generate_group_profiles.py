import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from generate_group_profiles import generate_all, main as generate_group_profiles_main
from schema_groupe import validate_profil_groupe


def _pivot(id_: str, nom: str) -> dict:
    return {
        "schema_version": "1",
        "id": id_,
        "nom": nom,
        "chambre": "AN",
        "parti": None,
        "groupe": None,
        "sources": [],
        "mandats": [
            {
                "categorie": "mandat_electif",
                "label": "Mandat parlementaire",
                "fonction": "mandat",
                "debut": "2022-06-22",
                "fin": None,
                "actif": True,
            }
        ],
        "votes": [],
        "textes_portes": [],
        "interventions": [],
        "amendements": [],
        "tags_thematiques": [],
        "meta": {
            "schema_version": "1",
            "genere_le": "2026-07-29T10:00:00+0000",
            "licence_donnees": "ODbL",
            "warnings": [],
        },
    }


def _deputes_payload():
    return {
        "deputes": [
            {"depute": {"slug": "alice", "nom": "Alice", "groupe_sigle": "LR", "mandat_debut": "2022-06-22", "mandat_fin": None}},
            {"depute": {"slug": "bob", "nom": "Bob", "groupe_sigle": "SOC", "mandat_debut": "2022-06-22", "mandat_fin": None}},
        ]
    }


# ---------------------------------------------------------------------------
# Translated comment.
# ---------------------------------------------------------------------------

def test_generate_all_fetches_once_per_chambre_legislature(tmp_path, monkeypatch):
    (tmp_path / "profiles").mkdir()
    (tmp_path / "profiles" / "alice.pivot.json").write_text(json.dumps(_pivot("nosdeputes:alice", "Alice")), encoding="utf-8")
    (tmp_path / "profiles" / "bob.pivot.json").write_text(json.dumps(_pivot("nosdeputes:bob", "Bob")), encoding="utf-8")
    out_dir = tmp_path / "groupes"
    out_dir.mkdir()

    call_count = {"n": 0}

    def fake_fetch_full_roster(chambre, legislature=None, session=None):
        call_count["n"] += 1
        assert chambre == "deputes"
        assert legislature == "16"
        return [m["depute"] for m in _deputes_payload()["deputes"]]

    monkeypatch.setattr("generate_group_profiles.fetch_full_roster", fake_fetch_full_roster)

    groupes = [
        {"roster_chambre": "deputes", "groupe_id": "AN:LR", "groupe_sigle": "LR", "groupe_nom": "Les Républicains", "chambre": "AN", "legislature": "16", "fichier": "groupe-AN-LR-16.json"},
        {"roster_chambre": "deputes", "groupe_id": "AN:SOC", "groupe_sigle": "SOC", "groupe_nom": "Socialistes", "chambre": "AN", "legislature": "16", "fichier": "groupe-AN-SOC-16.json"},
    ]

    echecs = generate_all(groupes, profiles_dir=tmp_path / "profiles", out_dir=out_dir, validate=True)

    assert echecs == 0
    assert call_count["n"] == 1  # Translated comment.

    lr = json.loads((out_dir / "groupe-AN-LR-16.json").read_text(encoding="utf-8"))
    soc = json.loads((out_dir / "groupe-AN-SOC-16.json").read_text(encoding="utf-8"))
    assert {m["membre_id"] for m in lr["membres"]} == {"nosdeputes:alice"}
    assert {m["membre_id"] for m in soc["membres"]} == {"nosdeputes:bob"}
    assert validate_profil_groupe(lr) == []
    assert validate_profil_groupe(soc) == []


def test_generate_all_two_chambres_two_fetches(tmp_path, monkeypatch):
    (tmp_path / "profiles").mkdir()
    out_dir = tmp_path / "groupes"
    out_dir.mkdir()

    fetch_calls = []

    def fake_fetch_full_roster(chambre, legislature=None, session=None):
        fetch_calls.append((chambre, legislature))
        if chambre == "deputes":
            return [m["depute"] for m in _deputes_payload()["deputes"]]
        return [{"slug": "carla", "nom": "Carla", "groupe_sigle": "LR", "mandat_debut": "2020-01-01", "mandat_fin": None}]

    monkeypatch.setattr("generate_group_profiles.fetch_full_roster", fake_fetch_full_roster)

    groupes = [
        {"roster_chambre": "deputes", "groupe_id": "AN:LR", "groupe_sigle": "LR", "groupe_nom": "Les Républicains", "chambre": "AN", "legislature": "16", "fichier": "groupe-AN-LR-16.json"},
        {"roster_chambre": "senateurs", "groupe_id": "Senat:LR", "groupe_sigle": "LR", "groupe_nom": "Les Républicains", "chambre": "Senat", "legislature": None, "fichier": "groupe-Senat-LR.json"},
    ]

    echecs = generate_all(groupes, profiles_dir=tmp_path / "profiles", out_dir=out_dir)

    assert echecs == 0
    assert len(fetch_calls) == 2
    assert set(fetch_calls) == {("deputes", "16"), ("senateurs", None)}


def test_generate_all_roster_fetch_failure_reported_as_echec(tmp_path, monkeypatch):
    import requests

    (tmp_path / "profiles").mkdir()
    out_dir = tmp_path / "groupes"
    out_dir.mkdir()

    def fake_fetch_full_roster(chambre, legislature=None, session=None):
        raise requests.RequestException("boom")

    monkeypatch.setattr("generate_group_profiles.fetch_full_roster", fake_fetch_full_roster)

    groupes = [
        {"roster_chambre": "deputes", "groupe_id": "AN:LR", "groupe_sigle": "LR", "groupe_nom": "Les Républicains", "chambre": "AN", "legislature": "16", "fichier": "groupe-AN-LR-16.json"},
    ]

    echecs = generate_all(groupes, profiles_dir=tmp_path / "profiles", out_dir=out_dir)

    assert echecs == 1
    assert not (out_dir / "groupe-AN-LR-16.json").exists()


# ---------------------------------------------------------------------------
# Translated comment.
# ---------------------------------------------------------------------------

def test_main_reads_config_and_generates(tmp_path, monkeypatch):
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "alice.pivot.json").write_text(json.dumps(_pivot("nosdeputes:alice", "Alice")), encoding="utf-8")
    out_dir = tmp_path / "groupes"

    config_path = tmp_path / "groupes_reels.json"
    config_path.write_text(json.dumps({
        "groupes": [
            {"roster_chambre": "deputes", "groupe_id": "AN:LR", "groupe_sigle": "LR", "groupe_nom": "Les Républicains", "chambre": "AN", "legislature": "16", "fichier": "groupe-AN-LR-16.json"},
        ]
    }), encoding="utf-8")

    def fake_fetch_full_roster(chambre, legislature=None, session=None):
        return [m["depute"] for m in _deputes_payload()["deputes"]]

    monkeypatch.setattr("generate_group_profiles.fetch_full_roster", fake_fetch_full_roster)

    rc = generate_group_profiles_main([
        "--config", str(config_path),
        "--profiles-dir", str(profiles_dir),
        "--out-dir", str(out_dir),
    ])

    assert rc == 0
    assert (out_dir / "groupe-AN-LR-16.json").exists()


def test_main_missing_config_returns_error(tmp_path):
    rc = generate_group_profiles_main(["--config", str(tmp_path / "does-not-exist.json")])
    assert rc == 1


def test_main_empty_groupes_returns_error(tmp_path):
    config_path = tmp_path / "empty.json"
    config_path.write_text(json.dumps({"groupes": []}), encoding="utf-8")
    rc = generate_group_profiles_main(["--config", str(config_path)])
    assert rc == 1


def test_repository_groupes_reels_json_is_valid():
    config_path = Path(__file__).resolve().parents[1] / "raw_data" / "groupes_reels.json"
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    assert isinstance(payload.get("groupes"), list)
    assert payload["groupes"]
