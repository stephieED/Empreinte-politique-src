"""Tests de `scripts/audit_fusion_blocs_599.py` (lot 0 de l'épic #598).

Un audit qui compte mal est pire qu'aucun audit : il publie un chiffre. Ces
tests éprouvent donc ses **détecteurs**, pas son formatage — chacun construit un
corpus minuscule dont la réponse attendue est connue, et vérifie que l'audit la
rend.

Trois pièges sont éprouvés nommément, parce que les trois ont déjà produit une
mesure fausse dans ce dépôt :

1. le marqueur `xsi:nil` compté comme une valeur renseignée (#539/#556) ;
2. les profils dont l'absence d'identité AN est **attendue** comptés dans le
   défaut (#539) ;
3. une population non nommée — ici, `nosdeputes` compté comme une source périmée
   alors que #529 ne l'écrit plus.
"""

import json
import sys
from pathlib import Path

import pytest

_RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_RACINE / "src"))
sys.path.insert(0, str(_RACINE / "scripts"))

from audit_fusion_blocs_599 import (  # noqa: E402
    HORS_DEFAUT,
    charger_corpus,
    construire_rapport,
    identite_du_chemin_minimal,
    mesurer_identite,
    mesurer_synchro,
    mesurer_warnings,
    porte_des_donnees_parlementaires,
    rendre_markdown,
    valeur_de_fond,
)

MARQUEUR_NIL = {
    "@xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
    "@xsi:nil": "true",
}


def _identite_minimale(nom: str = "Jean Test", parti: str = "Parti") -> dict:
    """La forme exacte de `generate_all_profiles.build_minimal_profile`."""
    return {
        "nom_complet": nom,
        "groupe_sigle": None,
        "groupe_nom": parti,
        "profession": None,
        "date_naissance": None,
        "num_circo": None,
        "nb_mandats": None,
        "url_an_ou_senat": None,
    }


def _identite_an() -> dict:
    """La forme de l'écrivain AN : dix clés, `lieu_naissance` et `uri_hatvp`
    comprises."""
    return {
        "nom_complet": "Jean Test",
        "groupe_sigle": "LFI",
        "groupe_nom": "La France insoumise",
        "profession": "Professeur",
        "date_naissance": "1951-08-19",
        "lieu_naissance": "Tanger",
        "num_circo": 4,
        "nb_mandats": 3,
        "uri_hatvp": "https://www.hatvp.fr/fiche/jean-test",
        "url_an_ou_senat": "https://www2.assemblee-nationale.fr/deputes/fiche/OMC_PA1234",
    }


# ---------------------------------------------------------------------------
# Les prédicats de base
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "valeur",
    [None, "", [], {}, MARQUEUR_NIL, "{'@xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance', '@xsi:nil': 'true'}"],
)
def test_valeur_de_fond_refuse_toutes_les_formes_d_absence(valeur):
    """Le marqueur XML d'AMO30 n'est pas une valeur.

    C'est la mesure fausse de #539 — « 465 profils portent `uri_hatvp` » quand
    186 portaient le marqueur. Un audit qui le recompte referait l'erreur.
    """
    assert valeur_de_fond(valeur) is None


def test_valeur_de_fond_garde_une_vraie_valeur():
    assert valeur_de_fond("Tanger") == "Tanger"
    assert (
        valeur_de_fond(
            "Chauny ({'@xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance',"
            " '@xsi:nil': 'true'})"
        )
        == "Chauny"
    )


def test_valeur_de_fond_garde_un_zero_mesure():
    """`nb_mandats: 0` et `num_circo: 0` sont des valeurs, pas des absences.

    C'est §2.5 lue dans l'autre sens : si l'audit les traitait comme vides, il
    déclarerait « champ perdu » sur un champ correctement publié, et le lot
    suivant irait le « réparer » en republiant l'ancienne valeur.
    """
    assert valeur_de_fond(0) == 0


def test_identite_du_chemin_minimal_reconnait_le_squelette():
    assert identite_du_chemin_minimal(_identite_minimale()) is True


def test_identite_du_chemin_minimal_refuse_une_identite_an():
    assert identite_du_chemin_minimal(_identite_an()) is False


def test_identite_du_chemin_minimal_refuse_une_collecte_an_en_echec():
    """Une identité AN entièrement vide n'est PAS le squelette minimal.

    Elle a dix clés, pas huit : la distinction tient à la forme autant qu'au
    fond, sinon l'audit confondrait deux défauts différents et attribuerait à
    #484 des profils dont la collecte AN a simplement échoué.
    """
    vide = {champ: None for champ in _identite_an()}
    assert identite_du_chemin_minimal(vide) is False


def test_identite_du_chemin_minimal_refuse_un_squelette_enrichi():
    """Huit clés mais une profession : ce bloc a appris quelque chose d'une
    source, il n'est plus celui du chemin minimal."""
    enrichi = _identite_minimale() | {"profession": "Professeur"}
    assert identite_du_chemin_minimal(enrichi) is False


def test_porte_des_donnees_parlementaires():
    assert porte_des_donnees_parlementaires({"votes": [{"a": 1}]}) is True
    assert porte_des_donnees_parlementaires({"votes": [], "mandats": []}) is False


# ---------------------------------------------------------------------------
# Mesure 1 — identité
# ---------------------------------------------------------------------------

def test_mesure_1_compte_le_squelette_minimal_gagnant():
    """Le cas #484 : identité du chemin minimal, 1 016 votes dans le même
    fichier. L'écrivain qui n'avait rien a gagné sur celui qui avait tout."""
    bruts = {
        "jean-luc-melenchon": {
            "identite": _identite_minimale(),
            "votes": [{"numero_scrutin": 1}],
            "meta": {"warnings": []},
        }
    }
    mesure = mesurer_identite(bruts, {})
    constats = mesure["constats"]["brut_squelette_minimal"]
    assert [e["slug"] for e in constats] == ["jean-luc-melenchon"]
    assert mesure["nb_profils_touches"] == 1


def test_mesure_1_ne_compte_pas_un_squelette_sans_donnees_parlementaires():
    """Sans donnée collectée, le bloc pauvre n'a écrasé personne : il est le
    seul qui existe. Le compter gonflerait la mesure d'un défaut absent."""
    bruts = {"quelqu-un": {"identite": _identite_minimale(), "votes": [], "mandats": []}}
    assert mesurer_identite(bruts, {})["nb_profils_touches"] == 0


def test_mesure_1_compte_a_part_les_quatre_profils_attendus():
    """Les trois non-parlementaires de #539 et `jordan-bardella` ne sont jamais
    dans le défaut : leur identité nulle est un fait, pas une perte."""
    bruts = {
        slug: {"identite": _identite_minimale(), "mandats": [{"label": "m"}]}
        for slug in sorted(HORS_DEFAUT)
    }
    mesure = mesurer_identite(bruts, {})
    assert mesure["nb_profils_touches"] == 0
    assert mesure["hors_defaut_attendu"]["brut_squelette_minimal"] == sorted(HORS_DEFAUT)
    assert mesure["population_mesuree"] == 0


def test_mesure_1_repere_un_champ_pivot_null_que_le_brut_renseigne():
    bruts = {"depute": {"identite": _identite_an(), "votes": [{"n": 1}]}}
    pivots = {
        "depute": {
            "identite": {
                "profession": None,
                "date_naissance": "1951-08-19",
                "lieu_naissance": None,
                "num_circo": 4,
                "uri_hatvp": "https://www.hatvp.fr/fiche/jean-test",
                "source_url": "https://www2.assemblee-nationale.fr/",
            }
        }
    }
    perdus = mesurer_identite(bruts, pivots)["constats"]["pivot_champ_perdu"]
    assert perdus == [{"slug": "depute", "champs": ["lieu_naissance", "profession"]}]


def test_mesure_1_ne_signale_pas_un_marqueur_nil_comme_une_perte():
    """Le brut porte le marqueur, le pivot publie `null` : c'est exactement ce
    que #556 demande. Un audit qui l'appellerait une perte réclamerait la
    republication d'une absence comme si c'était une valeur (§2.5)."""
    brut_identite = _identite_an() | {"profession": MARQUEUR_NIL}
    bruts = {"depute": {"identite": brut_identite, "votes": [{"n": 1}]}}
    pivots = {
        "depute": {
            "identite": {
                "profession": None,
                "date_naissance": "1951-08-19",
                "lieu_naissance": "Tanger",
                "num_circo": 4,
                "uri_hatvp": "https://www.hatvp.fr/fiche/jean-test",
                "source_url": "https://x",
            }
        }
    }
    assert mesurer_identite(bruts, pivots)["constats"].get("pivot_champ_perdu") is None


def test_mesure_1_repere_uri_hatvp_null_avec_identifiant_renseigne():
    bruts = {"depute": {"identite": {"nom_complet": "X"}}}
    pivots = {
        "depute": {
            "identite": {"uri_hatvp": None, "source_url": "https://x"},
            "identifiants": {"hatvp": "https://www.hatvp.fr/fiche/x"},
        }
    }
    constats = mesurer_identite(bruts, pivots)["constats"]["hatvp_incoherent"]
    assert [e["slug"] for e in constats] == ["depute"]


def test_mesure_1_repere_un_pivot_sans_bloc_identite():
    bruts = {"depute": {"identite": _identite_an(), "votes": [{"n": 1}]}}
    pivots = {"depute": {"identite": None}}
    constats = mesurer_identite(bruts, pivots)["constats"]["pivot_identite_absente"]
    assert constats[0]["slug"] == "depute"
    assert "profession" in constats[0]["champs_connus_du_brut"]


# ---------------------------------------------------------------------------
# Mesure 2 — warnings
# ---------------------------------------------------------------------------

def test_mesure_2_compte_les_warnings_reduits_au_chemin_minimal():
    bruts = {
        "depute": {
            "votes": [{"n": 1}],
            "meta": {
                "genere_le": "2026-08-29T16:00:00+0000",
                "collecte_ecartee": [],
                "warnings": [
                    "aucun mandat français connu (slug absent du référentiel "
                    "Assemblée nationale, ou identité introuvable)"
                ],
            },
        }
    }
    mesure = mesurer_warnings(bruts, {}, "2026-08-29")
    assert [e["slug"] for e in mesure["constats"]["warnings_reduits_au_chemin_minimal"]] == ["depute"]


def test_mesure_2_ne_compte_pas_un_profil_qui_porte_aussi_d_autres_warnings():
    """Un `meta` qui porte le warning du chemin minimal **et** ceux de
    l'écrivain AN n'a rien perdu — c'est la cible de #600."""
    bruts = {
        "depute": {
            "votes": [{"n": 1}],
            "meta": {
                "genere_le": "2026-08-29T16:00:00+0000",
                "collecte_ecartee": [],
                "warnings": [
                    "aucun mandat français connu (…)",
                    "amendements indisponibles : …",
                ],
            },
        }
    }
    mesure = mesurer_warnings(bruts, {}, "2026-08-29")
    assert mesure["constats"].get("warnings_reduits_au_chemin_minimal") is None


def test_mesure_2_n_accuse_pas_les_profils_non_regeneres():
    """Dix-neuf sénateurs ne sont plus régénérés depuis #528 : leur `meta` est
    légitimement d'avant `collecte_ecartee` (#539). Les compter serait un
    chiffre juste sur la mauvaise population."""
    bruts = {
        "senateur": {
            "mandats": [{"label": "m"}],
            "meta": {"genere_le": "2026-08-19T10:00:00+0000", "warnings": []},
        }
    }
    mesure = mesurer_warnings(bruts, {}, "2026-08-29")
    assert mesure["constats"].get("collecte_ecartee_absente") is None
    assert mesure["non_regeneres_par_le_dernier_run"] == ["senateur"]


def test_mesure_2_accuse_un_meta_sans_collecte_ecartee_du_dernier_run():
    bruts = {
        "depute": {
            "votes": [{"n": 1}],
            "meta": {"genere_le": "2026-08-29T16:00:00+0000", "warnings": []},
        }
    }
    mesure = mesurer_warnings(bruts, {}, "2026-08-29")
    assert [e["slug"] for e in mesure["constats"]["collecte_ecartee_absente"]] == ["depute"]


def test_mesure_2_liste_les_warnings_du_brut_absents_du_pivot():
    bruts = {"depute": {"meta": {"genere_le": "2026-08-29T00:00:00+0000", "warnings": ["a", "b"]}}}
    pivots = {"depute": {"meta": {"warnings": ["b", "c"]}}}
    mesure = mesurer_warnings(bruts, pivots, "2026-08-29")
    assert mesure["warnings_du_brut_non_publies_au_pivot"] == [
        {"slug": "depute", "warnings": ["a"]}
    ]


# ---------------------------------------------------------------------------
# Mesure 3 — synchro_sources
# ---------------------------------------------------------------------------

def test_mesure_3_separe_la_source_retiree_des_sources_encore_ecrites():
    """`nosdeputes` n'est plus écrit depuis #529 : sa vieille valeur est un
    reliquat exact. Le mélanger aux trois sources AN publierait un compteur de
    « défauts » dont la majorité n'en sont pas."""
    bruts = {
        "reliquat": {
            "meta": {
                "genere_le": "2026-08-29T16:00:00+0000",
                "synchro_sources": {
                    "nosdeputes": "2026-08-19T10:00:00+0000",
                    "assemblee_nationale": "2026-08-29T15:59:00+0000",
                },
                "warnings": [],
            }
        },
        "vraie-perte": {
            "meta": {
                "genere_le": "2026-08-29T16:00:00+0000",
                "synchro_sources": {"assemblee_nationale": "2026-08-19T18:00:00+0000"},
                "warnings": [],
            }
        },
    }
    mesure = mesurer_synchro(bruts)
    assert mesure["nb_anterieure_au_genere_le"] == 2
    assert mesure["dont_source_retiree_seulement"] == ["reliquat"]
    assert [e["slug"] for e in mesure["dont_source_encore_ecrite"]] == ["vraie-perte"]
    assert mesure["retard_max_jours_par_source"]["assemblee_nationale"] == pytest.approx(9.92, abs=0.02)


def test_mesure_3_ignore_l_ecart_intra_run():
    """Quelques minutes entre la synchro et le `genere_le` du même profil, c'est
    l'ordonnancement normal d'un run, pas une reprise."""
    bruts = {
        "normal": {
            "meta": {
                "genere_le": "2026-08-29T16:00:00+0000",
                "synchro_sources": {"assemblee_nationale": "2026-08-29T15:40:00+0000"},
                "warnings": [],
            }
        }
    }
    assert mesurer_synchro(bruts)["nb_anterieure_au_genere_le"] == 0


def test_mesure_3_repere_un_meta_sans_bloc_synchro():
    bruts = {
        "depute": {
            "votes": [{"n": 1}],
            "meta": {"genere_le": "2026-08-29T16:00:00+0000", "warnings": []},
        }
    }
    assert mesurer_synchro(bruts)["meta_sans_synchro_sources"] == ["depute"]


def test_mesure_3_ne_compte_pas_les_quatre_profils_attendus_sans_synchro():
    bruts = {
        slug: {"mandats": [{"label": "m"}], "meta": {"genere_le": "2026-08-29T16:00:00+0000"}}
        for slug in sorted(HORS_DEFAUT)
    }
    assert mesurer_synchro(bruts)["meta_sans_synchro_sources"] == []


# ---------------------------------------------------------------------------
# Bout en bout : lecture du corpus et rendu
# ---------------------------------------------------------------------------

def test_charger_corpus_lit_un_profil_partitionne_et_ignore_les_fichiers_de_service(tmp_path):
    """La partition par législature (#580) et le checkpoint sont les deux
    pièges d'énumération. Un `json.load` direct sur le socle rendrait un profil
    sans amendements ; un `glob` naïf compterait `.generation_checkpoint.json`
    comme un profil et fausserait toutes les populations."""
    bruts = tmp_path / "raw"
    bruts.mkdir()
    (bruts / ".generation_checkpoint.json").write_text("{}", encoding="utf-8")
    socle = {
        "slug": "depute",
        "identite": _identite_an(),
        "votes": [{"numero_scrutin": 1}],
        "amendements_partitionnes": {
            "cle": "amendements",
            "total": 1,
            "tranches": [{"legislature": 16, "fichier": "16.json", "nb": 1}],
        },
        "meta": {"genere_le": "2026-08-29T16:00:00+0000", "warnings": []},
    }
    (bruts / "depute.json").write_text(json.dumps(socle), encoding="utf-8")
    (bruts / "depute").mkdir()
    (bruts / "depute" / "16.json").write_text(
        json.dumps({"amendements": [{"uid": "AMANR5L16PO1234B0001P1D1N1"}]}), encoding="utf-8"
    )

    pivots = tmp_path / "pivot"
    pivots.mkdir()
    (pivots / ".cache.pivot.json").write_text("{}", encoding="utf-8")
    (pivots / "depute.pivot.json").write_text(json.dumps({"id": "depute"}), encoding="utf-8")

    charges_bruts, charges_pivots, illisibles = charger_corpus(bruts, pivots)
    assert sorted(charges_bruts) == ["depute"]
    assert sorted(charges_pivots) == ["depute"]
    assert illisibles == []


def test_rapport_complet_est_serialisable_et_nomme_ses_populations(tmp_path):
    bruts = tmp_path / "raw"
    bruts.mkdir()
    (bruts / "depute.json").write_text(
        json.dumps({
            "identite": _identite_minimale(),
            "votes": [{"numero_scrutin": 1}],
            "meta": {
                "genere_le": "2026-08-29T16:00:00+0000",
                "synchro_sources": {"assemblee_nationale": "2026-08-19T18:00:00+0000"},
                "warnings": ["aucun mandat français connu (…)"],
            },
        }),
        encoding="utf-8",
    )
    pivots = tmp_path / "pivot"
    pivots.mkdir()
    (pivots / "depute.pivot.json").write_text(
        json.dumps({"identite": None, "meta": {"warnings": []}}), encoding="utf-8"
    )

    rapport = construire_rapport(bruts, pivots)
    json.dumps(rapport, ensure_ascii=False)  # ne doit pas lever

    assert rapport["mesure_1_identite"]["population_bruts"] == 1
    assert rapport["mesure_1_identite"]["profils_touches"] == ["depute"]
    assert rapport["mesure_2_warnings"]["profils_touches"] == ["depute"]
    assert rapport["mesure_3_synchro"]["nb_dont_source_encore_ecrite"] == 1

    markdown = rendre_markdown(rapport)
    assert "Population du défaut" in markdown
    assert "`depute`" in markdown
