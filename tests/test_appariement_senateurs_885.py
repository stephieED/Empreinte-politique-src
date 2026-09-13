"""#885 — relier un profil publié à son matricule sénatorial, ou refuser.

`raw_data/correspondance_acteurs_an.json` porte déjà un champ
`identifiants.senat` sur ses 1 196 entrées, **nul sur les 1 196**. Il attendait
une source ; il n'en fallait pas une seconde.

Deux comportements sont gelés ici, et le second compte plus que le premier :

1. **Les particules.** La source range « Dominique de Legge » en
   `senprenomuse = "Dominique"`, `sennomuse = "de Legge"`. Un découpage du nom
   publié sur son dernier mot cherche « Legge » précédé de « Dominique de », et
   ne trouve rien. C'était le seul échec d'appariement mesuré — il venait du
   découpage, pas de la source.
2. **Le refus d'inventer.** Deux sénateurs pour un même état civil normalisé ne
   se tranchent pas automatiquement : un identifiant faux rattacherait la
   carrière de quelqu'un d'autre à une fiche publiée, et rien dans le corpus ne
   le signalerait ensuite. `build_correspondance_acteurs_an.py` refuse d'inventer
   depuis #525 ; ce module ne fait pas exception.

Mesuré le 13/09/2026 : **38 appariements uniques, 0 ambigu** sur les 1 196
profils publiés. Zéro ambiguïté est une mesure sur ce corpus, pas une garantie :
le refus reste armé, et ces tests le vérifient.

Toutes les doublures sont construites ici (AGENTS.md §3, #457/#473/#488).
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from appariement_senateurs import (  # noqa: E402
    ORIGINE_APPARIEMENT,
    AppariementAmbigu,
    apparier,
    indexer_senateurs,
    normaliser,
    proposer_appariements,
)


def _sen(matricule, prenom, nom):
    return {"senmat": matricule, "senprenomuse": prenom, "sennomuse": nom}


def _entree(nom_complet, senat=None):
    return {"identifiants": {"an": "PA1", "senat": senat},
            "etat_civil": {"nom_complet": nom_complet}}


# ---------------------------------------------------------------------------
# La normalisation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("brut,attendu", [
    ("Jean-Luc", "jeanluc"),
    ("Jean Luc", "jeanluc"),
    ("Mélenchon", "melenchon"),
    ("de Legge", "delegge"),
    ("O'Brien", "obrien"),
    (None, ""),
])
def test_la_normalisation_compare_ce_qui_est_comparable(brut, attendu):
    """La source n'est pas régulière sur les traits d'union ni les accents ;
    l'appariement ne peut pas l'être non plus."""
    assert normaliser(brut) == attendu


# ---------------------------------------------------------------------------
# Les particules — le seul échec mesuré
# ---------------------------------------------------------------------------

def test_un_nom_a_particule_est_apparie():
    """`sennomuse` vaut « de Legge », pas « Legge ». Un découpage sur le dernier
    mot du nom publié manquerait tous les noms à particule."""
    index = indexer_senateurs([_sen("08034U", "Dominique", "de Legge")])

    assert apparier("Dominique de Legge", index) == "08034U"


def test_tous_les_decoupages_sont_essayes():
    """Un prénom composé range la coupure ailleurs — et le module ne sait pas
    d'avance de quel côté elle tombe."""
    index = indexer_senateurs([_sen("1", "Marie Claire", "du Pont")])

    assert apparier("Marie Claire du Pont", index) == "1"


def test_un_nom_simple_est_apparie():
    index = indexer_senateurs([_sen("86039K", "Jean-Luc", "Mélenchon")])

    assert apparier("Jean-Luc Mélenchon", index) == "86039K"


# ---------------------------------------------------------------------------
# Le refus
# ---------------------------------------------------------------------------

def test_deux_senateurs_pour_un_nom_ne_se_tranchent_pas():
    """Un identifiant faux rattacherait la carrière de quelqu'un d'autre à une
    fiche publiée. Personne ne le verrait ensuite."""
    index = indexer_senateurs([_sen("1", "Jean", "Dupont"), _sen("2", "Jean", "Dupont")])

    with pytest.raises(AppariementAmbigu) as echec:
        apparier("Jean Dupont", index)

    assert "1" in str(echec.value) and "2" in str(echec.value)


def test_le_refus_dit_ou_trancher():
    """Un refus qui ne dit pas quoi faire se contourne."""
    index = indexer_senateurs([_sen("1", "Jean", "Dupont"), _sen("2", "Jean", "Dupont")])

    with pytest.raises(AppariementAmbigu) as echec:
        apparier("Jean Dupont", index)

    assert "correspondance_acteurs_an.json" in str(echec.value)


def test_aucun_senateur_n_est_le_cas_normal():
    """1 158 des 1 196 profils publiés n'ont aucun passé sénatorial. Lever
    ferait de la normalité une erreur."""
    index = indexer_senateurs([_sen("1", "Jean", "Dupont")])

    assert apparier("Gabriel Attal", index) is None
    assert apparier("", index) is None


# ---------------------------------------------------------------------------
# La proposition, qui n'écrit rien
# ---------------------------------------------------------------------------

def test_la_proposition_ne_modifie_pas_les_correspondances():
    """Une proposition se lit avant de s'écrire."""
    correspondances = {"jean-luc-melenchon": _entree("Jean-Luc Mélenchon")}
    avant = dict(correspondances["jean-luc-melenchon"]["identifiants"])

    proposer_appariements(correspondances, [_sen("86039K", "Jean-Luc", "Mélenchon")])

    assert correspondances["jean-luc-melenchon"]["identifiants"] == avant


def test_un_identifiant_deja_renseigne_n_est_jamais_recalcule():
    """Il a pu être **relu** par un humain. Un appariement automatique qui
    l'écrase défait précisément le travail qu'il faut protéger (#715)."""
    correspondances = {"bruno-retailleau": _entree("Bruno Retailleau", senat="RELU42")}

    appariements, ambigus, deja = proposer_appariements(
        correspondances, [_sen("04033B", "Bruno", "Retailleau")])

    assert appariements == {}
    assert deja == ["bruno-retailleau"]
    assert ambigus == []


def test_les_ambigus_sont_nommes_et_non_apparies():
    """Ils sortent de la proposition par une liste, pas par une exception : un
    corpus qui en porte un ne doit pas empêcher les 37 autres d'être écrits."""
    correspondances = {
        "jean-dupont": _entree("Jean Dupont"),
        "jean-luc-melenchon": _entree("Jean-Luc Mélenchon"),
    }

    appariements, ambigus, _ = proposer_appariements(correspondances, [
        _sen("1", "Jean", "Dupont"), _sen("2", "Jean", "Dupont"),
        _sen("86039K", "Jean-Luc", "Mélenchon"),
    ])

    assert appariements == {"jean-luc-melenchon": "86039K"}
    assert ambigus == ["jean-dupont"]


def test_un_appariement_automatique_gele_sans_prouver():
    """Le même régime que les 699 entrées dérivées de #715 : il fixe
    l'identifiant, il ne l'établit pas. La relecture reste due."""
    assert ORIGINE_APPARIEMENT == "derivee"
