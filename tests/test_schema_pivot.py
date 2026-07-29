import sys
from pathlib import Path

# Les modules testés vivent dans src/, à côté du dossier tests/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import time
from schema_pivot import (
    SCHEMA_VERSION,
    KNOWN_CHAMBRES,
    KNOWN_POSITIONS,
    KNOWN_CATEGORIES,
    make_empty_profil,
    validate_profil,
)


# ---------------------------------------------------------------------------
# make_empty_profil
# ---------------------------------------------------------------------------

def test_make_empty_profil_schema_version():
    p = make_empty_profil("nosdeputes:jean-dupont", "Jean Dupont")
    assert p["schema_version"] == SCHEMA_VERSION
    assert p["meta"]["schema_version"] == SCHEMA_VERSION


def test_make_empty_profil_id_and_nom():
    p = make_empty_profil("parltrack:123", "Marie Martin")
    assert p["id"] == "parltrack:123"
    assert p["nom"] == "Marie Martin"


def test_make_empty_profil_default_lists():
    p = make_empty_profil("test:x", "X")
    for key in ("sources", "mandats", "votes", "textes_portes", "interventions", "tags_thematiques"):
        assert isinstance(p[key], list), f"'{key}' doit être une liste vide par défaut"
        assert p[key] == []


def test_make_empty_profil_default_nulls():
    p = make_empty_profil("test:x", "X")
    assert p["chambre"] is None
    assert p["parti"] is None
    assert p["groupe"] is None


def test_make_empty_profil_genere_le_looks_like_iso():
    p = make_empty_profil("test:x", "X")
    ts = p["meta"]["genere_le"]
    # time.strftime('%Y-%m-%dT%H:%M:%S') always produces both 'T' and '-'
    assert "T" in ts and "-" in ts, f"genere_le ne ressemble pas à un ISO-8601 : {ts!r}"


def test_make_empty_profil_warnings_empty():
    p = make_empty_profil("test:x", "X")
    assert p["meta"]["warnings"] == []


# ---------------------------------------------------------------------------
# validate_profil — profil valide
# ---------------------------------------------------------------------------

def _valid_profil() -> dict:
    """Construit un profil pivot minimal valide pour les tests."""
    p = make_empty_profil("nosdeputes:test", "Test Personne")
    p["chambre"] = "AN"
    p["meta"]["licence_donnees"] = "ODbL"
    return p


def test_validate_valid_profil_returns_no_errors():
    assert validate_profil(_valid_profil()) == []


def test_validate_valid_profil_with_chambre_senat():
    p = _valid_profil()
    p["chambre"] = "Senat"
    assert validate_profil(p) == []


def test_validate_valid_profil_with_chambre_pe():
    p = _valid_profil()
    p["chambre"] = "PE"
    assert validate_profil(p) == []


def test_validate_valid_profil_chambre_none():
    p = _valid_profil()
    p["chambre"] = None
    assert validate_profil(p) == []


# ---------------------------------------------------------------------------
# validate_profil — erreurs détectées
# ---------------------------------------------------------------------------

def test_validate_missing_top_level_key():
    p = _valid_profil()
    del p["nom"]
    errors = validate_profil(p)
    assert any("nom" in e for e in errors), f"Erreur attendue pour 'nom' manquant : {errors}"


def test_validate_wrong_schema_version():
    p = _valid_profil()
    p["schema_version"] = "0"
    errors = validate_profil(p)
    assert any("schema_version" in e for e in errors)


def test_validate_empty_id():
    p = _valid_profil()
    p["id"] = ""
    errors = validate_profil(p)
    assert any("'id'" in e for e in errors)


def test_validate_empty_nom():
    p = _valid_profil()
    p["nom"] = ""
    errors = validate_profil(p)
    assert any("'nom'" in e for e in errors)


def test_validate_unknown_chambre():
    p = _valid_profil()
    p["chambre"] = "ASSEMBLEE_GENERALE"
    errors = validate_profil(p)
    assert any("chambre" in e for e in errors)


def test_validate_votes_not_a_list():
    p = _valid_profil()
    p["votes"] = {"not": "a list"}
    errors = validate_profil(p)
    assert any("votes" in e for e in errors)


def test_validate_mandats_not_a_list():
    p = _valid_profil()
    p["mandats"] = "should be a list"
    errors = validate_profil(p)
    assert any("mandats" in e for e in errors)


def test_validate_missing_meta_key():
    p = _valid_profil()
    del p["meta"]["genere_le"]
    errors = validate_profil(p)
    assert any("genere_le" in e for e in errors)


def test_validate_meta_not_a_dict():
    p = _valid_profil()
    p["meta"] = "not a dict"
    errors = validate_profil(p)
    assert any("meta" in e for e in errors)


def test_validate_meta_schema_version_mismatch():
    p = _valid_profil()
    p["meta"]["schema_version"] = "99"
    errors = validate_profil(p)
    assert any("meta.schema_version" in e for e in errors)


def test_validate_meta_warnings_not_a_list():
    p = _valid_profil()
    p["meta"]["warnings"] = "not a list"
    errors = validate_profil(p)
    assert any("warnings" in e for e in errors)


def test_validate_non_dict_input():
    errors = validate_profil("not a dict")  # type: ignore[arg-type]
    assert errors
    assert any("dict" in e for e in errors)


# ---------------------------------------------------------------------------
# Constantes exposées
# ---------------------------------------------------------------------------

def test_known_chambres_contains_expected_values():
    assert "AN" in KNOWN_CHAMBRES
    assert "Senat" in KNOWN_CHAMBRES
    assert "PE" in KNOWN_CHAMBRES
    assert "mairie" in KNOWN_CHAMBRES


def test_known_positions_contains_expected_values():
    assert "pour" in KNOWN_POSITIONS
    assert "contre" in KNOWN_POSITIONS
    assert "abstention" in KNOWN_POSITIONS
    assert "non_votant" in KNOWN_POSITIONS


def test_known_categories_contains_expected_values():
    assert "mandat_electif" in KNOWN_CATEGORIES
    assert "commission" in KNOWN_CATEGORIES
    assert "groupe_amitie" in KNOWN_CATEGORIES
