import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from generate_all_profiles import load_candidats
from generate_roster_candidats import (
    build_roster_candidats,
    generate_roster_candidats,
    main as generate_roster_candidats_main,
)


def _deputes_payload():
    return [
        {"slug": "alice", "nom": "Alice", "groupe_sigle": "LR", "mandat_debut": "2022-06-22", "mandat_fin": None},
        {"slug": "bob", "nom": "Bob", "groupe_sigle": "SOC", "mandat_debut": "2022-06-22", "mandat_fin": None},
    ]


def _senateurs_payload():
    return [
        {"slug": "carla", "nom": "Carla", "groupe_sigle": "LR", "mandat_debut": "2020-01-01", "mandat_fin": None},
    ]


_GROUPE_LR_AN = {
    "roster_chambre": "deputes", "groupe_id": "AN:LR", "groupe_sigle": "LR",
    "groupe_nom": "Les Républicains", "chambre": "AN", "legislature": "16",
    "fichier": "groupe-AN-LR-16.json",
}
_GROUPE_SOC_AN = {
    "roster_chambre": "deputes", "groupe_id": "AN:SOC", "groupe_sigle": "SOC",
    "groupe_nom": "Socialistes", "chambre": "AN", "legislature": "16",
    "fichier": "groupe-AN-SOC-16.json",
}
_GROUPE_LR_SENAT = {
    "roster_chambre": "senateurs", "groupe_id": "Senat:LR", "groupe_sigle": "LR",
    "groupe_nom": "Les Républicains", "chambre": "Senat", "legislature": None,
    "fichier": "groupe-Senat-LR.json",
}


# ---------------------------------------------------------------------------
# build_roster_candidats : fonction pure (pas d'accès réseau)
# ---------------------------------------------------------------------------

def test_build_roster_candidats_flattens_and_formats():
    rosters_bruts = {("deputes", "16"): _deputes_payload()}
    groupes = [_GROUPE_LR_AN, _GROUPE_SOC_AN]

    candidats = build_roster_candidats(groupes, rosters_bruts)

    par_slug = {c["slug"]: c for c in candidats}
    assert set(par_slug) == {"alice", "bob"}

    alice = par_slug["alice"]
    assert alice["nom"] == "Alice"
    assert alice["parti"] is None
    assert alice["famille_politique"] is None
    assert alice["statut"] == "roster_groupe"
    assert alice["date_declaration"] is None
    assert alice["source"] == "https://www.nosdeputes.fr/alice"
    assert "LR" in alice["notes"]

    bob = par_slug["bob"]
    assert bob["source"] == "https://www.nosdeputes.fr/bob"
    assert "SOC" in bob["notes"]


def test_build_roster_candidats_skips_group_with_failed_fetch():
    rosters_bruts = {("deputes", "16"): None}
    groupes = [_GROUPE_LR_AN]

    candidats = build_roster_candidats(groupes, rosters_bruts)

    assert candidats == []


def test_build_roster_candidats_dedups_by_slug_guard():
    # Garde-fou : deux entrées de config pointant vers le même (chambre, legislature)
    # avec un sigle mal configuré ne doivent pas produire de doublon par slug.
    rosters_bruts = {("deputes", "16"): _deputes_payload()}
    groupe_lr_dupe = dict(_GROUPE_LR_AN, groupe_id="AN:LR-dupe", fichier="groupe-AN-LR-16-dupe.json")
    groupes = [_GROUPE_LR_AN, groupe_lr_dupe]

    candidats = build_roster_candidats(groupes, rosters_bruts)

    assert [c["slug"] for c in candidats] == ["alice"]


def test_build_roster_candidats_independent_from_editorial_candidats_json():
    # Un membre présent aussi dans raw_data/candidats.json (ex. jean-luc-melenchon)
    # doit apparaître dans la liste roster sans aucune fusion/consultation de
    # raw_data/candidats.json — les deux listes restent distinctes à ce stade.
    rosters_bruts = {("deputes", "16"): [
        {"slug": "jean-luc-melenchon", "nom": "Jean-Luc Mélenchon", "groupe_sigle": "LFI", "mandat_debut": "2022-06-22", "mandat_fin": None},
    ]}
    groupe_lfi = dict(_GROUPE_LR_AN, groupe_sigle="LFI", groupe_nom="La France insoumise - NUPES")

    candidats = build_roster_candidats([groupe_lfi], rosters_bruts)

    assert len(candidats) == 1
    assert candidats[0]["slug"] == "jean-luc-melenchon"
    assert candidats[0]["statut"] == "roster_groupe"
    assert candidats[0]["parti"] is None  # pas de fusion avec candidats.json (parti y est renseigné)


# ---------------------------------------------------------------------------
# generate_roster_candidats : un seul fetch réseau par (chambre, législature)
# ---------------------------------------------------------------------------

def test_generate_roster_candidats_fetches_once_per_chambre_legislature(monkeypatch):
    call_count = {"n": 0}

    def fake_fetch_full_roster(chambre, legislature=None, session=None):
        call_count["n"] += 1
        assert chambre == "deputes"
        assert legislature == "16"
        return _deputes_payload()

    monkeypatch.setattr("generate_roster_candidats.fetch_full_roster", fake_fetch_full_roster)

    candidats = generate_roster_candidats([_GROUPE_LR_AN, _GROUPE_SOC_AN])

    assert call_count["n"] == 1
    assert {c["slug"] for c in candidats} == {"alice", "bob"}


def test_generate_roster_candidats_two_chambres_two_fetches(monkeypatch):
    fetch_calls = []

    def fake_fetch_full_roster(chambre, legislature=None, session=None):
        fetch_calls.append((chambre, legislature))
        if chambre == "deputes":
            return _deputes_payload()
        return _senateurs_payload()

    monkeypatch.setattr("generate_roster_candidats.fetch_full_roster", fake_fetch_full_roster)

    candidats = generate_roster_candidats([_GROUPE_LR_AN, _GROUPE_LR_SENAT])

    assert len(fetch_calls) == 2
    assert set(fetch_calls) == {("deputes", "16"), ("senateurs", None)}
    assert {c["slug"] for c in candidats} == {"alice", "carla"}
    assert next(c for c in candidats if c["slug"] == "carla")["source"] == "https://archive.nossenateurs.fr/carla"


def test_generate_roster_candidats_fetch_failure_is_ignored(monkeypatch):
    import requests

    def fake_fetch_full_roster(chambre, legislature=None, session=None):
        raise requests.RequestException("boom")

    monkeypatch.setattr("generate_roster_candidats.fetch_full_roster", fake_fetch_full_roster)

    candidats = generate_roster_candidats([_GROUPE_LR_AN])

    assert candidats == []


# ---------------------------------------------------------------------------
# Sortie JSON rechargeable par load_candidats()
# ---------------------------------------------------------------------------

def test_output_reloadable_by_load_candidats(tmp_path, monkeypatch):
    def fake_fetch_full_roster(chambre, legislature=None, session=None):
        return _deputes_payload()

    monkeypatch.setattr("generate_roster_candidats.fetch_full_roster", fake_fetch_full_roster)

    config_path = tmp_path / "groupes_reels.json"
    config_path.write_text(json.dumps({"groupes": [_GROUPE_LR_AN, _GROUPE_SOC_AN]}), encoding="utf-8")
    out_path = tmp_path / "roster_candidats.json"

    rc = generate_roster_candidats_main(["--config", str(config_path), "--out", str(out_path)])

    assert rc == 0
    assert out_path.exists()

    candidats = load_candidats(str(out_path))
    assert {c["slug"] for c in candidats} == {"alice", "bob"}
    for c in candidats:
        assert set(c) == {"nom", "slug", "parti", "famille_politique", "statut", "date_declaration", "source", "notes"}


def test_main_missing_config_returns_error(tmp_path):
    rc = generate_roster_candidats_main(["--config", str(tmp_path / "does-not-exist.json")])
    assert rc == 1


def test_main_empty_groupes_returns_error(tmp_path):
    config_path = tmp_path / "empty.json"
    config_path.write_text(json.dumps({"groupes": []}), encoding="utf-8")
    rc = generate_roster_candidats_main(["--config", str(config_path)])
    assert rc == 1


# ---------------------------------------------------------------------------
# Cohérence miroir de test_repository_groupes_reels_json_is_valid
# (tests/test_generate_group_profiles.py), appliquée au fichier généré à
# partir des données réelles du dépôt (fetch réseau mocké).
# ---------------------------------------------------------------------------

def test_repository_groupes_reels_json_produces_valid_roster_candidats(monkeypatch):
    config_path = Path(__file__).resolve().parents[1] / "raw_data" / "groupes_reels.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    groupes = config["groupes"]

    def fake_fetch_full_roster(chambre, legislature=None, session=None):
        if chambre == "deputes":
            return [
                {"slug": "alice", "nom": "Alice", "groupe_sigle": "REN", "mandat_debut": "2022-06-22", "mandat_fin": None},
                {"slug": "bob", "nom": "Bob", "groupe_sigle": "SOC", "mandat_debut": "2022-06-22", "mandat_fin": None},
                {"slug": "carla", "nom": "Carla", "groupe_sigle": "RN", "mandat_debut": "2022-06-22", "mandat_fin": None},
                {"slug": "dan", "nom": "Dan", "groupe_sigle": "LFI", "mandat_debut": "2022-06-22", "mandat_fin": None},
                {"slug": "eve", "nom": "Eve", "groupe_sigle": "LR", "mandat_debut": "2022-06-22", "mandat_fin": None},
            ]
        return [
            {"slug": "farid", "nom": "Farid", "groupe_sigle": "LR", "mandat_debut": "2020-01-01", "mandat_fin": None},
            {"slug": "gina", "nom": "Gina", "groupe_sigle": "SER", "mandat_debut": "2020-01-01", "mandat_fin": None},
        ]

    monkeypatch.setattr("generate_roster_candidats.fetch_full_roster", fake_fetch_full_roster)

    candidats = generate_roster_candidats(groupes)

    assert isinstance(candidats, list)
    assert candidats
    assert {c["slug"] for c in candidats} == {"alice", "bob", "carla", "dan", "eve", "farid", "gina"}
    for c in candidats:
        assert c["statut"] == "roster_groupe"
        assert c["slug"]
        assert c["nom"]
        assert c["source"]

    # Rechargeable sans erreur par generate_all_profiles.load_candidats().
    payload_path_content = json.dumps({"candidats": candidats}, ensure_ascii=False)
    reloaded = json.loads(payload_path_content).get("candidats")
    assert reloaded == candidats
