import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from audit_pivot_dataset import (
    compute_distribution_listes,
    compute_nombre_sources,
    compute_presence_meta,
    compute_profils_sans_activite,
    compute_repartition_chambre,
    compute_taux_remplissage,
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


# ---------------------------------------------------------------------------
# compute_taux_remplissage
# ---------------------------------------------------------------------------

def test_compute_taux_remplissage_liste_vide():
    resultat = compute_taux_remplissage([])

    for champ in ("parti", "groupe", "tags_thematiques", "mandats"):
        assert resultat[champ] == {"renseignes": 0, "total": 0, "taux_pct": 0.0}


def test_compute_taux_remplissage_champ_absent_du_profil():
    resultat = compute_taux_remplissage([{"id": "a"}])

    assert resultat["parti"] == {"renseignes": 0, "total": 1, "taux_pct": 0.0}
    assert resultat["mandats"] == {"renseignes": 0, "total": 1, "taux_pct": 0.0}


def test_compute_taux_remplissage_distingue_null_vide_et_renseigne():
    profils = [
        {"id": "a", "parti": None, "groupe": "", "tags_thematiques": [], "mandats": []},
        {"id": "b", "parti": "PS", "groupe": "LFI", "tags_thematiques": ["budget"],
         "mandats": [{"type": "depute"}]},
    ]

    resultat = compute_taux_remplissage(profils)

    # null (a.parti) et chaîne/liste vide (a.groupe, a.tags, a.mandats) comptent
    # tous les deux comme "non renseigné" : seul le profil "b" est renseigné.
    assert resultat["parti"] == {"renseignes": 1, "total": 2, "taux_pct": 50.0}
    assert resultat["groupe"] == {"renseignes": 1, "total": 2, "taux_pct": 50.0}
    assert resultat["tags_thematiques"] == {"renseignes": 1, "total": 2, "taux_pct": 50.0}
    assert resultat["mandats"] == {"renseignes": 1, "total": 2, "taux_pct": 50.0}


def test_compute_taux_remplissage_tous_champs_renseignes():
    profils = [
        {"id": "a", "parti": "PS", "groupe": "LFI", "tags_thematiques": ["budget"],
         "mandats": [{"type": "depute"}]},
    ]

    resultat = compute_taux_remplissage(profils)

    for champ in ("parti", "groupe", "tags_thematiques", "mandats"):
        assert resultat[champ]["taux_pct"] == 100.0


# ---------------------------------------------------------------------------
# compute_profils_sans_activite
# ---------------------------------------------------------------------------

def test_compute_profils_sans_activite_liste_vide():
    resultat = compute_profils_sans_activite([])

    assert resultat == {
        "total_profils": 0, "nb_profils_sans_activite": 0, "profils_sans_activite": [],
    }


def test_compute_profils_sans_activite_detecte_les_profils_totalement_vides():
    profils = [
        {"id": "sans-activite-1"},
        {"id": "sans-activite-2", "votes": None, "amendements": [], "interventions": None},
        {"id": "avec-votes", "votes": [{"id": 1}], "amendements": [], "interventions": []},
    ]

    resultat = compute_profils_sans_activite(profils)

    assert resultat["total_profils"] == 3
    assert resultat["nb_profils_sans_activite"] == 2
    assert set(resultat["profils_sans_activite"]) == {"sans-activite-1", "sans-activite-2"}


def test_compute_profils_sans_activite_un_seul_champ_actif_suffit():
    profils = [
        {"id": "a", "votes": [], "amendements": [{"id": 1}], "interventions": []},
    ]

    resultat = compute_profils_sans_activite(profils)

    assert resultat["nb_profils_sans_activite"] == 0
    assert resultat["profils_sans_activite"] == []


# ---------------------------------------------------------------------------
# compute_presence_meta
# ---------------------------------------------------------------------------

def test_compute_presence_meta_liste_vide():
    resultat = compute_presence_meta([])

    assert resultat == {
        "total_profils": 0,
        "meta_absente": [],
        "licence_donnees_manquante": [],
        "genere_le_manquant": [],
    }


def test_compute_presence_meta_meta_absent_du_profil():
    resultat = compute_presence_meta([{"id": "sans-meta"}])

    assert resultat["meta_absente"] == ["sans-meta"]
    assert resultat["licence_donnees_manquante"] == ["sans-meta"]
    assert resultat["genere_le_manquant"] == ["sans-meta"]


def test_compute_presence_meta_meta_incomplet():
    profils = [
        {"id": "licence-vide", "meta": {"licence_donnees": "", "genere_le": "2026-01-01T00:00:00"}},
        {"id": "genere_le-null", "meta": {"licence_donnees": "ODbL", "genere_le": None}},
        {"id": "complet", "meta": {"licence_donnees": "ODbL", "genere_le": "2026-01-01T00:00:00"}},
    ]

    resultat = compute_presence_meta(profils)

    assert resultat["meta_absente"] == []
    assert resultat["licence_donnees_manquante"] == ["licence-vide"]
    assert resultat["genere_le_manquant"] == ["genere_le-null"]


def test_compute_presence_meta_total_profils():
    resultat = compute_presence_meta([{"id": "a"}, {"id": "b", "meta": {}}])

    assert resultat["total_profils"] == 2
    assert resultat["meta_absente"] == ["a"]
    assert set(resultat["licence_donnees_manquante"]) == {"a", "b"}
    assert set(resultat["genere_le_manquant"]) == {"a", "b"}
