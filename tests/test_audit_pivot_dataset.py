import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from audit_pivot_dataset import load_pivot_directory


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "audit_pivot"


# ---------------------------------------------------------------------------
# load_pivot_directory : chargement des fixtures du dépôt
# ---------------------------------------------------------------------------

def test_load_pivot_directory_charge_les_profils_valides():
    profils_valides, erreurs_lecture = load_pivot_directory(FIXTURES_DIR)

    ids = {p["id"] for p in profils_valides}
    assert ids == {
        "nosdeputes:jean-dupont",
        "nosdeputes:marie-martin",
        "nossenateurs:paul-durand",
    }


def test_load_pivot_directory_scanne_recursivement():
    profils_valides, _ = load_pivot_directory(FIXTURES_DIR)

    # profil-3.pivot.json est dans un sous-dossier : doit être trouvé malgré tout.
    assert any(p["id"] == "nossenateurs:paul-durand" for p in profils_valides)


def test_load_pivot_directory_ne_s_interrompt_pas_sur_fichier_invalide():
    profils_valides, erreurs_lecture = load_pivot_directory(FIXTURES_DIR)

    # Le fichier invalide ne doit pas empêcher le chargement des autres profils.
    assert len(profils_valides) == 3
    assert len(erreurs_lecture) == 1


def test_load_pivot_directory_contenu_erreurs_lecture():
    _, erreurs_lecture = load_pivot_directory(FIXTURES_DIR)

    assert len(erreurs_lecture) == 1
    erreur = erreurs_lecture[0]
    assert set(erreur.keys()) == {"fichier", "erreur"}
    assert erreur["fichier"].endswith("invalide.pivot.json")
    assert isinstance(erreur["erreur"], str)
    assert erreur["erreur"]  # message non vide


# ---------------------------------------------------------------------------
# load_pivot_directory : cas limites construits en mémoire (tmp_path)
# ---------------------------------------------------------------------------

def test_load_pivot_directory_repertoire_vide(tmp_path):
    profils_valides, erreurs_lecture = load_pivot_directory(tmp_path)

    assert profils_valides == []
    assert erreurs_lecture == []


def test_load_pivot_directory_ignore_fichiers_non_pivot(tmp_path):
    (tmp_path / "notes.txt").write_text("pas un pivot", encoding="utf-8")
    (tmp_path / "autre.json").write_text('{"id": "x"}', encoding="utf-8")

    profils_valides, erreurs_lecture = load_pivot_directory(tmp_path)

    assert profils_valides == []
    assert erreurs_lecture == []


def test_load_pivot_directory_objet_racine_non_dict(tmp_path):
    (tmp_path / "liste.pivot.json").write_text("[1, 2, 3]", encoding="utf-8")

    profils_valides, erreurs_lecture = load_pivot_directory(tmp_path)

    assert profils_valides == []
    assert len(erreurs_lecture) == 1
    assert erreurs_lecture[0]["fichier"].endswith("liste.pivot.json")


def test_load_pivot_directory_est_pure(tmp_path):
    fichier = tmp_path / "profil.pivot.json"
    contenu = {"schema_version": "1", "id": "nosdeputes:test", "nom": "Test"}
    fichier.write_text(json.dumps(contenu), encoding="utf-8")

    load_pivot_directory(tmp_path)

    # Le fichier source ne doit pas être modifié par le chargement.
    assert json.loads(fichier.read_text(encoding="utf-8")) == contenu
