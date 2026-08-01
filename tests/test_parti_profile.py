import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from parti_profile import _slugify, _group_candidats_by_parti, build_parti_profile
from schema_parti import validate_profil_parti


def _pivot(id_="nosdeputes:bruno-retailleau", tags=None, sources=None):
    return {
        "schema_version": "1",
        "id": id_,
        "nom": "Bruno Retailleau",
        "tags_thematiques": tags or [],
        "sources": sources or [{"type": "nossenateurs", "url": "https://archive.nossenateurs.fr/bruno-retailleau"}],
        "interventions": [],
    }


def _candidat(nom="Bruno Retailleau", slug="bruno-retailleau", parti="Les Républicains (LR)"):
    return {
        "nom": nom,
        "slug": slug,
        "parti": parti,
        "famille_politique": "droite",
        "statut": "declare",
    }


def test_slugify():
    assert _slugify("Les Républicains (LR)") == "les-republicains-lr"
    assert _slugify("Rassemblement National (RN)") == "rassemblement-national-rn"


def test_group_candidats_by_parti():
    candidats = [_candidat(parti="LR"), _candidat(nom="X", slug="x", parti="LR"), _candidat(nom="Y", slug=None, parti="PS")]
    grouped = _group_candidats_by_parti(candidats)
    assert set(grouped.keys()) == {"LR", "PS"}
    assert len(grouped["LR"]) == 2
    assert len(grouped["PS"]) == 1


def test_group_candidats_by_parti_ignores_missing_parti():
    candidats = [{"nom": "Sans parti", "slug": None, "parti": None}]
    grouped = _group_candidats_by_parti(candidats)
    assert grouped == {}


def test_build_parti_profile_with_pivot(tmp_path):
    profiles_dir = tmp_path
    (profiles_dir / "bruno-retailleau.pivot.json").write_text(
        json.dumps(_pivot(tags=["budget"])), encoding="utf-8"
    )
    candidats = [_candidat()]
    profil = build_parti_profile("Les Républicains (LR)", candidats, profiles_dir)

    assert profil["parti_id"] == "les-republicains-lr"
    assert len(profil["candidats"]) == 1
    assert profil["candidats"][0]["candidat_id"] == "nosdeputes:bruno-retailleau"
    assert profil["candidats"][0]["a_un_profil_pivot"] is True
    assert profil["meta"]["nb_candidats_declares"] == 1
    assert profil["meta"]["nb_candidats_avec_pivot"] == 1
    assert len(profil["sources"]) == 1
    assert validate_profil_parti(profil) == []


def test_build_parti_profile_without_pivot_warns(tmp_path):
    candidats = [_candidat(nom="Sans profil", slug=None, parti="Horizons")]
    profil = build_parti_profile("Horizons", candidats, tmp_path)

    assert profil["candidats"][0]["candidat_id"] is None
    assert profil["candidats"][0]["a_un_profil_pivot"] is False
    assert profil["meta"]["nb_candidats_avec_pivot"] == 0
    assert validate_profil_parti(profil) == []


def test_build_parti_profile_missing_pivot_file_warns(tmp_path):
    candidats = [_candidat(slug="introuvable")]
    profil = build_parti_profile("Les Républicains (LR)", candidats, tmp_path)

    assert profil["candidats"][0]["a_un_profil_pivot"] is False
    assert any("introuvable" in w for w in profil["meta"]["warnings"])


def test_build_parti_profile_never_has_cohesion_or_amendements(tmp_path):
    candidats = [_candidat()]
    profil = build_parti_profile("Les Républicains (LR)", candidats, tmp_path)
    assert "cohesion_votes" not in profil
    assert "amendements_agreges" not in profil
