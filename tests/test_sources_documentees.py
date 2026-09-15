"""Une source vit dans quatre fichiers, ou elle n'y est qu'à moitié.

Demandé par la propriétaire le 15/09/2026 : « lorsqu'il y a un changement ou un
ajout d'une source, il faut mettre à jour la doc de la source et les docs
architecture, workflow et README ».

L'instruction naît d'un manque mesuré le jour même. Le Répertoire national des
élus est entré au corpus avec #922, et il avait atteint :

| Fichier | Atteint ? |
| --- | --- |
| `AGENTS.md` §7 — licence et contrainte de réutilisation | oui |
| `docs/data-architecture.md` — ce que la donnée devient | oui |
| `docs/workflow-generate-data.md` — le job qui la collecte | oui |
| `docs/sources/` — ce que le fournisseur publie, et ses pièges | **non** |
| `README.md` — la table du lecteur, avec sa licence | **non** |

Deux sur cinq manquaient, et rien ne le signalait : chaque fichier était
cohérent avec lui-même. C'est exactement le genre d'omission qu'un test attrape
et qu'une relecture manque.

## Ce que ce test vérifie, et ce qu'il ne peut pas

Il vérifie la **présence croisée** : toute source qui a une fiche sous
`docs/sources/` est nommée dans le README, et réciproquement pour les sources
vivantes. Il ne juge pas le contenu — une fiche peut être à jour ou périmée, il
ne le sait pas. Ce qu'il sait, c'est qu'une source ne peut pas exister dans un
fichier et pas dans l'autre.
"""

import re
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1]
SOURCES = RACINE / "docs" / "sources"
README = RACINE / "README.md"
ARCHITECTURE = RACINE / "docs" / "data-architecture.md"

#: Ce qui nomme chaque source, dans les fichiers qui doivent la citer. La clé
#: est le nom de la fiche sous `docs/sources/` ; la valeur, les formes sous
#: lesquelles le README et l'architecture ont le droit de l'appeler.
NOMS_ATTENDUS: dict[str, tuple[str, ...]] = {
    "an-opendata": ("Assemblée nationale", "data.assemblee-nationale.fr"),
    "senat-opendata": ("Sénat", "data.senat.fr"),
    "parltrack-et-europarl": ("Parltrack", "Parlement européen"),
    "sycomore-et-journal-officiel": ("Sycomore", "Journal officiel"),
    "repertoire-national-des-elus": ("Répertoire national des élus", "RNE"),
}

#: `nosdeputes/` est un répertoire, et son statut est *historique* : plus
#: interrogé depuis #529. Il reste cité au README sous la mention « plus
#: collectées », ce qui est une autre exigence que celle des sources vivantes.
FICHES_HISTORIQUES = {"nosdeputes"}


def _fiches_de_sources() -> set[str]:
    """Les sources qui ont une fiche, fichier ou répertoire."""
    return {chemin.stem if chemin.is_file() else chemin.name
            for chemin in SOURCES.iterdir()
            if chemin.is_file() and chemin.suffix == ".md" or chemin.is_dir()}


def test_chaque_fiche_de_source_est_declaree_dans_ce_test():
    """Le garde-fou du garde-fou.

    Une fiche ajoutée sans entrée dans `NOMS_ATTENDUS` passerait inaperçue, et
    ce test cesserait silencieusement de la couvrir — le défaut qu'il est censé
    empêcher, appliqué à lui-même.
    """
    non_declarees = _fiches_de_sources() - set(NOMS_ATTENDUS) - FICHES_HISTORIQUES

    assert not non_declarees, (
        f"Ces fiches de source ne sont pas déclarées ici : {sorted(non_declarees)}. "
        "Ajouter leur entrée dans NOMS_ATTENDUS, sinon elles ne sont vérifiées "
        "nulle part.")


@pytest.mark.parametrize("fiche", sorted(NOMS_ATTENDUS))
def test_chaque_source_vivante_a_sa_fiche(fiche: str):
    """La fiche dit ce que le fournisseur publie — elle dérive avec lui."""
    assert (SOURCES / f"{fiche}.md").is_file(), (
        f"`docs/sources/{fiche}.md` manque. Une source sans fiche oblige à "
        "relire le code pour savoir ce que le fournisseur publie.")


@pytest.mark.parametrize("fiche,noms", sorted(NOMS_ATTENDUS.items()))
def test_chaque_source_est_nommee_dans_le_readme(fiche: str, noms: tuple[str, ...]):
    """Le README porte la table du lecteur : ce qu'on collecte, et sous quelle
    licence. C'est la moitié qui manquait au RNE."""
    texte = README.read_text(encoding="utf-8")

    assert any(nom in texte for nom in noms), (
        f"La source « {fiche} » a une fiche sous `docs/sources/` mais n'est "
        f"nommée nulle part dans le README (cherché : {list(noms)}). "
        "Une source citée dans un fichier et pas dans l'autre n'existe qu'à "
        "moitié — voir AGENTS.md §8.")


@pytest.mark.parametrize("fiche,noms", sorted(NOMS_ATTENDUS.items()))
def test_chaque_source_est_nommee_dans_l_architecture(fiche: str, noms: tuple[str, ...]):
    """`data-architecture.md` dit ce que la donnée DEVIENT, une fois collectée."""
    texte = ARCHITECTURE.read_text(encoding="utf-8")

    assert any(nom in texte for nom in noms), (
        f"La source « {fiche} » n'est nommée nulle part dans "
        "`docs/data-architecture.md` (cherché : "
        f"{list(noms)}). Ce fichier dit ce que la donnée devient ; une source "
        "absente y laisse un champ sans origine.")


def test_chaque_fiche_declare_son_statut_en_tete():
    """`docs/sources/` mélange des sources vivantes et historiques, et le nom du
    répertoire ne le dit pas — c'est l'en-tête de chaque fiche qui le dit."""
    manquants = []
    for fiche in sorted(NOMS_ATTENDUS):
        entete = (SOURCES / f"{fiche}.md").read_text(encoding="utf-8")[:600].lower()
        # Le dépôt est bilingue : `an-opendata.md` écrit « Status: live », les
        # fiches récentes « Statut : vivante ». Les deux disent la même chose.
        if not re.search(r"statut?\s*:|vivante|historique|historical|live|citée",
                         entete):
            manquants.append(fiche)

    assert not manquants, (
        f"Ces fiches ne déclarent pas leur statut en tête : {manquants}. "
        "Sans lui, rien ne distingue une source interrogée à chaque run d'une "
        "source qu'on ne consulte plus depuis un an.")


# --------------------------------------------------------------------------
# La table d'orientation d'AGENTS.md
# --------------------------------------------------------------------------

AGENTS = RACINE / "AGENTS.md"

#: Ce que la table doit savoir adresser. Chaque entrée est un besoin réel d'une
#: session, et la cible qui y répond. Mesuré le 15/09/2026 sur cinq questions
#: posées dans la journée : trois trouvaient leur réponse, deux non — « où est ce
#: mécanisme dans le code » et « à quoi ressemble une table relue ».
CIBLES_ATTENDUES = (
    "docs/regles/",
    "docs/decisions-par-module.md",
    "docs/decisions/",
    "docs/data-architecture.md",
    "docs/workflow-generate-data.md",
    "docs/sources/",
    "docs/commandes.md",
    "README.md",
)


@pytest.mark.parametrize("cible", CIBLES_ATTENDUES)
def test_la_table_d_orientation_adresse_chaque_documentation(cible: str):
    """Un agent doit trouver où chercher sans relire tout le dépôt.

    Le contenu existait, dispersé entre trois endroits — l'en-tête, le tableau
    des `docs/regles/` et les References — et aucun n'était rangé par BESOIN.
    Résultat mesuré : une session a cherché un mécanisme à la main dans `src/`
    alors que `docs/decisions-par-module.md` le nomme.
    """
    entete = AGENTS.read_text(encoding="utf-8").split("## 1. Product")[0]

    assert cible in entete, (
        f"La table d'orientation d'AGENTS.md n'adresse pas « {cible} ». "
        "Un agent qui ne sait pas où chercher cherche dans le code.")


def test_la_table_precede_les_regles():
    """Elle sert en début de lot : après les règles, elle arrive trop tard."""
    texte = AGENTS.read_text(encoding="utf-8")

    assert texte.index("Where to look") < texte.index("## 1. Product")
