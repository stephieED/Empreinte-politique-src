import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from audit_pivot_dataset import (
    compute_distribution_listes,
    compute_nombre_sources,
    compute_repartition_chambre,
    load_pivot_directory,
)


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


# ---------------------------------------------------------------------------
# Fixtures minimalistes en mémoire pour les indicateurs de volumétrie.
# ---------------------------------------------------------------------------

def profil(chambre=None, nb_votes=0, nb_textes=0, nb_amendements=0,
           nb_interventions=0, nb_sources=0):
    return {
        "id": "source:x",
        "chambre": chambre,
        "sources": [{"type": "nosdeputes", "url": "u", "synchro_le": "t"}] * nb_sources,
        "votes": [{"id": i} for i in range(nb_votes)],
        "textes_portes": [{"id": i} for i in range(nb_textes)],
        "amendements": [{"id": i} for i in range(nb_amendements)],
        "interventions": [{"id": i} for i in range(nb_interventions)],
    }


# ---------------------------------------------------------------------------
# compute_repartition_chambre
# ---------------------------------------------------------------------------

def test_compute_repartition_chambre_liste_vide():
    resultat = compute_repartition_chambre([])

    assert resultat["total_profils"] == 0
    assert resultat["par_chambre"] == {
        "AN": 0, "PE": 0, "Senat": 0, "mairie": 0, "null": 0,
    }


def test_compute_repartition_chambre_repartit_par_chambre_connue():
    profils = [
        profil(chambre="AN"),
        profil(chambre="AN"),
        profil(chambre="Senat"),
        profil(chambre="PE"),
        profil(chambre="mairie"),
    ]

    resultat = compute_repartition_chambre(profils)

    assert resultat["total_profils"] == 5
    assert resultat["par_chambre"] == {
        "AN": 2, "Senat": 1, "PE": 1, "mairie": 1, "null": 0,
    }


def test_compute_repartition_chambre_valeur_null_ou_inconnue():
    profils = [
        profil(chambre=None),
        profil(chambre="valeur_inconnue"),
        profil(chambre="AN"),
    ]

    resultat = compute_repartition_chambre(profils)

    assert resultat["total_profils"] == 3
    assert resultat["par_chambre"]["null"] == 2
    assert resultat["par_chambre"]["AN"] == 1


def test_compute_repartition_chambre_chambre_absente_du_profil():
    resultat = compute_repartition_chambre([{"id": "source:x"}])

    assert resultat["total_profils"] == 1
    assert resultat["par_chambre"]["null"] == 1


# ---------------------------------------------------------------------------
# compute_distribution_listes
# ---------------------------------------------------------------------------

def test_compute_distribution_listes_liste_vide():
    resultat = compute_distribution_listes([])

    for champ in ("votes", "textes_portes", "amendements", "interventions"):
        assert resultat[champ] == {
            "min": None, "max": None, "mediane": None,
            "moyenne": None, "pct_profils_a_zero": 0.0,
        }


def test_compute_distribution_listes_0_1_plusieurs_elements():
    profils = [
        profil(nb_votes=0),
        profil(nb_votes=1),
        profil(nb_votes=5),
        profil(nb_votes=6),
    ]

    resultat = compute_distribution_listes(profils)
    votes = resultat["votes"]

    assert votes["min"] == 0
    assert votes["max"] == 6
    assert votes["mediane"] == 3
    assert votes["moyenne"] == 3.0
    assert votes["pct_profils_a_zero"] == 25.0


def test_compute_distribution_listes_champ_absent_ou_null_compte_comme_zero():
    profils = [
        {"id": "a"},                 # champ "votes" absent
        {"id": "b", "votes": None},  # champ "votes" explicitement null
        {"id": "c", "votes": [{"id": 1}]},
    ]

    resultat = compute_distribution_listes(profils)
    votes = resultat["votes"]

    assert votes["min"] == 0
    assert votes["max"] == 1
    assert votes["pct_profils_a_zero"] == round(200 / 3, 2)


def test_compute_distribution_listes_couvre_les_quatre_champs_independamment():
    profils = [
        profil(nb_votes=2, nb_textes=0, nb_amendements=1, nb_interventions=3),
    ]

    resultat = compute_distribution_listes(profils)

    assert resultat["votes"]["max"] == 2
    assert resultat["textes_portes"]["max"] == 0
    assert resultat["amendements"]["max"] == 1
    assert resultat["interventions"]["max"] == 3


# ---------------------------------------------------------------------------
# compute_nombre_sources
# ---------------------------------------------------------------------------

def test_compute_nombre_sources_liste_vide():
    resultat = compute_nombre_sources([])

    assert resultat == {"moyenne_sources": None, "pct_profils_une_source": 0.0}


def test_compute_nombre_sources_moyenne_et_pourcentage_une_source():
    profils = [
        profil(nb_sources=0),
        profil(nb_sources=1),
        profil(nb_sources=1),
        profil(nb_sources=3),
    ]

    resultat = compute_nombre_sources(profils)

    assert resultat["moyenne_sources"] == 1.25
    assert resultat["pct_profils_une_source"] == 50.0


def test_compute_nombre_sources_champ_absent_compte_comme_zero():
    resultat = compute_nombre_sources([{"id": "a"}, {"id": "b", "sources": [{"type": "x"}]}])

    assert resultat["moyenne_sources"] == 0.5
    assert resultat["pct_profils_une_source"] == 50.0
