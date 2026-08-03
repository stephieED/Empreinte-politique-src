import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from schema_parti import (
    SCHEMA_PARTI_VERSION,
    make_empty_profil_parti,
    validate_profil_parti,
)


def test_make_empty_profil_parti_defaults():
    p = make_empty_profil_parti("les-republicains-lr", "Les Républicains (LR)")
    assert p["schema_version"] == SCHEMA_PARTI_VERSION
    assert p["type_document"] == "profil_parti"
    assert p["parti_id"] == "les-republicains-lr"
    assert p["parti_nom"] == "Les Républicains (LR)"
    assert p["candidats"] == []
    assert p["tags_thematiques_agreges"] == []
    assert p["sources"] == []
    assert p["meta"]["nb_candidats_declares"] == 0
    assert p["meta"]["nb_candidats_avec_pivot"] == 0
    assert p["meta"]["warnings"] == []


def test_validate_profil_parti_empty_is_valid():
    p = make_empty_profil_parti("lo", "Lutte Ouvrière (LO)")
    assert validate_profil_parti(p) == []


def test_validate_profil_parti_not_a_dict():
    errors = validate_profil_parti("not a dict")
    assert len(errors) == 1
    assert "dict" in errors[0]


def test_validate_profil_parti_missing_top_level_keys():
    p = make_empty_profil_parti("lo", "Lutte Ouvrière (LO)")
    del p["candidats"]
    errors = validate_profil_parti(p)
    assert any("candidats" in e for e in errors)


def test_validate_profil_parti_wrong_schema_version():
    p = make_empty_profil_parti("lo", "Lutte Ouvrière (LO)")
    p["schema_version"] = "2"
    errors = validate_profil_parti(p)
    assert any("schema_version" in e for e in errors)


def test_validate_profil_parti_wrong_type_document():
    p = make_empty_profil_parti("lo", "Lutte Ouvrière (LO)")
    p["type_document"] = "profil_groupe"
    errors = validate_profil_parti(p)
    assert any("type_document" in e for e in errors)


def test_validate_profil_parti_empty_parti_id():
    p = make_empty_profil_parti("lo", "Lutte Ouvrière (LO)")
    p["parti_id"] = ""
    errors = validate_profil_parti(p)
    assert any("parti_id" in e for e in errors)


def test_validate_profil_parti_candidats_not_a_list():
    p = make_empty_profil_parti("lo", "Lutte Ouvrière (LO)")
    p["candidats"] = "not a list"
    errors = validate_profil_parti(p)
    assert any("candidats" in e for e in errors)


def test_validate_profil_parti_candidat_missing_keys():
    p = make_empty_profil_parti("lo", "Lutte Ouvrière (LO)")
    p["candidats"] = [{"nom": "Nathalie Arthaud"}]
    errors = validate_profil_parti(p)
    assert any("candidats[0]" in e for e in errors)


def test_validate_profil_parti_candidat_a_un_profil_pivot_not_bool():
    p = make_empty_profil_parti("lo", "Lutte Ouvrière (LO)")
    p["candidats"] = [{
        "candidat_id": None,
        "nom": "Nathalie Arthaud",
        "statut": "declare",
        "famille_politique": "extrême gauche",
        "a_un_profil_pivot": "oui",
    }]
    errors = validate_profil_parti(p)
    assert any("a_un_profil_pivot doit être un booléen" in e for e in errors)


def test_validate_profil_parti_meta_missing_keys():
    p = make_empty_profil_parti("lo", "Lutte Ouvrière (LO)")
    del p["meta"]["nb_candidats_declares"]
    errors = validate_profil_parti(p)
    assert any("nb_candidats_declares" in e for e in errors)


def test_validate_profil_parti_meta_not_a_dict():
    p = make_empty_profil_parti("lo", "Lutte Ouvrière (LO)")
    p["meta"] = "not a dict"
    errors = validate_profil_parti(p)
    assert any("'meta' doit être un dict" in e for e in errors)


def test_no_cohesion_or_amendements_fields_in_schema():
    """Le schéma de parti ne doit jamais exposer de champs de groupe parlementaire."""
    p = make_empty_profil_parti("lo", "Lutte Ouvrière (LO)")
    assert "cohesion_votes" not in p
    assert "amendements_agreges" not in p
    assert "effectif" not in p
