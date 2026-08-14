import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from generate_gouvernement_profiles import generate_all, main as generate_gouvernement_profiles_main
from schema_gouvernement import validate_profil_gouvernement

REPO_ROOT = Path(__file__).resolve().parents[1]


def _pivot(id_: str, nom: str, mandats: list) -> dict:
    return {
        "schema_version": "1",
        "id": id_,
        "nom": nom,
        "chambre": "AN",
        "parti": None,
        "groupe": None,
        "sources": [],
        "mandats": mandats,
        "votes": [],
        "textes_portes": [],
        "amendements": [],
        "interventions": [],
        "tags_thematiques": [],
        "meta": {"schema_version": "1", "genere_le": "2026-07-29T10:00:00+0000", "licence_donnees": "", "warnings": []},
    }


def _mandat_gouv(label: str, debut: str, fin: str = None, actif: bool = False) -> dict:
    return {
        "categorie": "fonction_gouvernementale",
        "type": "membre",
        "label": label,
        "debut": debut,
        "fin": fin,
        "actif": actif,
        "source_url": "https://data.assemblee-nationale.fr/static/openData/repository/...",
        "position_dans_hemicycle": "gouvernement",
    }


def _dossier(dossier_id: str, statut: str, date_depot: str, chambre: str = "AN") -> dict:
    return {
        "dossier_id": dossier_id,
        "titre": "Projet de loi test",
        "statut": statut,
        "sort_49_3": False,
        "chambre_depot_initial": chambre,
        "date_depot": date_depot,
        "date_dernier_evenement": date_depot,
        "legislature": "17",
        "source_url": f"https://www.assemblee-nationale.fr/dyn/17/dossiers/{dossier_id}",
        "warnings": [],
    }


# ---------------------------------------------------------------------------
# generate_all : un seul fetch réseau / chargement disque partagé entre tous
# les gouvernements du batch
# ---------------------------------------------------------------------------

def test_generate_all_fetches_dossiers_once_for_all_gouvernements(tmp_path, monkeypatch):
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "a.pivot.json").write_text(json.dumps(
        _pivot("nosdeputes:a", "A", [_mandat_gouv("Gouvernement (BAYROU)", "2024-12-24", "2025-09-09")])
    ), encoding="utf-8")
    (profiles_dir / "b.pivot.json").write_text(json.dumps(
        _pivot("nosdeputes:b", "B", [_mandat_gouv("Gouvernement (ATTAL)", "2024-01-10", "2024-09-05", actif=False)])
    ), encoding="utf-8")
    out_dir = tmp_path / "gouvernements"
    out_dir.mkdir()

    call_count = {"n": 0}

    def fake_fetch_dossiers_gouvernementaux():
        call_count["n"] += 1
        return {
            "dossiers": [
                _dossier("D-BAYROU", "adopte", "2025-01-10"),
                _dossier("D-ATTAL", "rejete", "2024-03-01"),
            ],
            "warnings": [],
        }

    monkeypatch.setattr("generate_gouvernement_profiles.fetch_dossiers_gouvernementaux", fake_fetch_dossiers_gouvernementaux)

    gouvernements = [
        {"gouvernement_id": "gouvernement:BAYROU", "nom": "Gouvernement Bayrou", "libelle_an": "BAYROU",
         "periode": {"debut": "2024-12-24", "fin": "2025-09-09"}, "fichier": "gouvernement-BAYROU.json"},
        {"gouvernement_id": "gouvernement:ATTAL", "nom": "Gouvernement Attal", "libelle_an": "ATTAL",
         "periode": {"debut": "2024-01-10", "fin": "2024-09-05"}, "fichier": "gouvernement-ATTAL.json"},
    ]

    echecs = generate_all(gouvernements, profiles_dir=profiles_dir, out_dir=out_dir, validate=True)

    assert echecs == 0
    assert call_count["n"] == 1  # un seul fetch réseau partagé entre les 2 gouvernements

    bayrou = json.loads((out_dir / "gouvernement-BAYROU.json").read_text(encoding="utf-8"))
    attal = json.loads((out_dir / "gouvernement-ATTAL.json").read_text(encoding="utf-8"))

    assert {m["membre_id"] for m in bayrou["membres"]} == {"nosdeputes:a"}
    assert {t["dossier_id"] for t in bayrou["textes"]} == {"D-BAYROU"}
    assert {m["membre_id"] for m in attal["membres"]} == {"nosdeputes:b"}
    assert {t["dossier_id"] for t in attal["textes"]} == {"D-ATTAL"}

    # Aucun double-comptage : chaque dossier n'apparaît que dans le
    # gouvernement dont la période couvre sa date de dépôt.
    assert "D-ATTAL" not in {t["dossier_id"] for t in bayrou["textes"]}
    assert "D-BAYROU" not in {t["dossier_id"] for t in attal["textes"]}

    assert validate_profil_gouvernement(bayrou) == []
    assert validate_profil_gouvernement(attal) == []


def test_generate_all_dossier_fetch_failure_reported_via_warnings(tmp_path, monkeypatch):
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    out_dir = tmp_path / "gouvernements"
    out_dir.mkdir()

    def fake_fetch_dossiers_gouvernementaux():
        return {"dossiers": [], "warnings": ["gouvernement_textes: téléchargement impossible."]}

    monkeypatch.setattr("generate_gouvernement_profiles.fetch_dossiers_gouvernementaux", fake_fetch_dossiers_gouvernementaux)

    gouvernements = [
        {"gouvernement_id": "gouvernement:BAYROU", "nom": "Gouvernement Bayrou", "libelle_an": "BAYROU",
         "periode": {"debut": "2024-12-24", "fin": "2025-09-09"}, "fichier": "gouvernement-BAYROU.json"},
    ]

    echecs = generate_all(gouvernements, profiles_dir=profiles_dir, out_dir=out_dir)
    assert echecs == 0

    bayrou = json.loads((out_dir / "gouvernement-BAYROU.json").read_text(encoding="utf-8"))
    assert bayrou["textes"] == []
    assert any("téléchargement" in w for w in bayrou["meta"]["warnings"])


def test_generate_all_echec_sur_un_gouvernement_n_arrete_pas_les_autres(tmp_path, monkeypatch):
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    out_dir = tmp_path / "gouvernements"
    out_dir.mkdir()

    def fake_fetch_dossiers_gouvernementaux():
        return {"dossiers": [], "warnings": []}

    monkeypatch.setattr("generate_gouvernement_profiles.fetch_dossiers_gouvernementaux", fake_fetch_dossiers_gouvernementaux)

    gouvernements = [
        {"gouvernement_id": "gouvernement:CASSE", "nom": "Gouvernement Casse", "libelle_an": "CASSE",
         "periode": "not-a-dict", "fichier": "gouvernement-CASSE.json"},  # provoque une exception dans build_gouvernement_profile
        {"gouvernement_id": "gouvernement:OK", "nom": "Gouvernement OK", "libelle_an": "OK",
         "periode": {"debut": "2020-01-01", "fin": "2020-06-01"}, "fichier": "gouvernement-OK.json"},
    ]

    echecs = generate_all(gouvernements, profiles_dir=profiles_dir, out_dir=out_dir, validate=True)

    assert echecs == 1
    assert not (out_dir / "gouvernement-CASSE.json").exists()
    assert (out_dir / "gouvernement-OK.json").exists()


# ---------------------------------------------------------------------------
# main() : lecture de la config JSON
# ---------------------------------------------------------------------------

def test_main_reads_config_and_generates(tmp_path, monkeypatch):
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "a.pivot.json").write_text(json.dumps(
        _pivot("nosdeputes:a", "A", [_mandat_gouv("Gouvernement (BAYROU)", "2024-12-24", "2025-09-09")])
    ), encoding="utf-8")
    out_dir = tmp_path / "gouvernements"

    config_path = tmp_path / "gouvernements_reels.json"
    config_path.write_text(json.dumps({
        "gouvernements": [
            {"gouvernement_id": "gouvernement:BAYROU", "nom": "Gouvernement Bayrou", "libelle_an": "BAYROU",
             "periode": {"debut": "2024-12-24", "fin": "2025-09-09"}, "fichier": "gouvernement-BAYROU.json"},
        ]
    }), encoding="utf-8")

    def fake_fetch_dossiers_gouvernementaux():
        return {"dossiers": [], "warnings": []}

    monkeypatch.setattr("generate_gouvernement_profiles.fetch_dossiers_gouvernementaux", fake_fetch_dossiers_gouvernementaux)

    rc = generate_gouvernement_profiles_main([
        "--config", str(config_path),
        "--profiles-dir", str(profiles_dir),
        "--out-dir", str(out_dir),
    ])

    assert rc == 0
    assert (out_dir / "gouvernement-BAYROU.json").exists()


def test_main_missing_config_returns_error(tmp_path):
    rc = generate_gouvernement_profiles_main(["--config", str(tmp_path / "does-not-exist.json")])
    assert rc == 1


def test_main_empty_gouvernements_returns_error(tmp_path):
    config_path = tmp_path / "empty.json"
    config_path.write_text(json.dumps({"gouvernements": []}), encoding="utf-8")
    rc = generate_gouvernement_profiles_main(["--config", str(config_path)])
    assert rc == 1


def test_repository_gouvernements_reels_json_is_valid():
    config_path = REPO_ROOT / "raw_data" / "gouvernements_reels.json"
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    assert isinstance(payload.get("gouvernements"), list)
    assert payload["gouvernements"]
