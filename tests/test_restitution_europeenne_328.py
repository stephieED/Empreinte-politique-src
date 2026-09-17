"""Une fiche européenne ne se voit plus reprocher une limite qui est la nôtre (#328).

La revue de l'intégration européenne, 13/09/2026, a mesuré sept écarts sur les
7 fiches concernées. Trois d'entre eux ne demandaient ni donnée nouvelle ni
arbitrage : la page disait quelque chose de faux sur ce qu'elle affichait déjà.

**1 et 2 — la section des votes se contredisait avec le tableau d'à côté.** Sur
`raphael-glucksmann`, le tableau « ce que chaque liste porte » annonçait
« Votes : 1 977 entrées — couvert depuis le 18 juillet 2019 » pendant que la
section affichait « Aucun résultat », expliqué par : « Aucune de ses positions
ne porte sur l'ensemble d'un texte au sens de la règle publiée ». Cette règle est
celle de l'Assemblée ; sur une fiche 100 % européenne, elle attribuait à la
personne une limite qui est la nôtre (§2 règle 2). La cause réelle est mesurable :
**0 des 11 013 votes européens** ne porte de `scrutin_id`, donc notre index n'en
rattache aucun.

**3 — « 0 adopté » là où aucun sort n'est publié.** Les 7 303 amendements
européens n'en portent aucun : le compte était juste, mais le lecteur lisait
« aucun n'a été adopté » là où la vérité est « le sort n'est publié pour aucun »
(§2 règle 5).

Ce que ces tests verrouillent, et pourquoi chacun a failli être faux :

- **le cas européen ne se déclenche que si TOUS les votes le sont** : sur une
  fiche mixte — Maurel, Mélenchon, Le Pen — la section doit continuer d'afficher
  les votes de l'Assemblée, et c'est vérifié hors dépôt ;
- **la cause reste `couvert`, jamais `non_collecte`.** Premier jet : le badge
  affichait « Non collecté » au-dessus d'une phrase disant « sont collectées »,
  c'est-à-dire exactement la contradiction que ce correctif retire ;
- **le compte d'adoptés n'est publié que si un sort l'est.**

CE QU'ILS NE COUVRENT PAS (§2 règle 5) : aucun composant React n'est rendu ici.
Vérifié hors dépôt le 13/09/2026 — Glucksmann : « Ses 1 977 positions au
Parlement européen sont collectées, mais aucune n'est rattachée à un scrutin
identifié », et « 590 amendements · 0 dossiers · sort non publié ». Guedj
(2 429 amendements · 25 dossiers · 160 adoptés) et Maurel (64 textes votés) sont
inchangés.
"""

from __future__ import annotations

import re
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
UI = RACINE / "web" / "UI_finale" / "src"

MODULE_REGLES = UI / "utils" / "profilCandidat.js"
COMPOSANT = UI / "components" / "CandidateProfile.jsx"


def sans_commentaires(source: str) -> str:
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    return re.sub(r"(?<!:)//[^\n]*", "", source)


def test_les_votes_europeens_non_resolus_sont_comptes():
    code = sans_commentaires(MODULE_REGLES.read_text(encoding="utf-8"))
    assert "INSTITUTION_PE_SOURCE = 'parlement_europeen'" in code, (
        "Le marqueur d'institution doit être nommé une fois : trois littéraux "
        "vivaient dans le module, et un quatrième aurait divergé."
    )
    assert "nonResolusEuropeens" in code, (
        "Sans ce compte, la section ne peut pas distinguer « aucun vote sur "
        "l'ensemble d'un texte » de « aucun vote rattaché à un scrutin »."
    )
    bloc = re.search(r"const nonResolusEuropeens = liste\.filter\((.*?)\)\.length;", code, re.DOTALL)
    assert bloc, "Le compte a changé de forme — relire le test."
    assert "!v.scrutin_id" in bloc.group(1), (
        "Un vote rattaché à un scrutin n'est pas un vote non résolu."
    )


def test_le_motif_europeen_ne_se_declenche_que_si_tous_les_votes_le_sont():
    """Sur une fiche mixte, la section doit continuer d'afficher l'Assemblée."""
    code = sans_commentaires(COMPOSANT.read_text(encoding="utf-8"))
    assert "votes.nonResolusEuropeens === votes.total" in code, (
        "La condition doit porter sur la TOTALITÉ des votes : sur Maurel, "
        "Mélenchon ou Le Pen, les votes de l'Assemblée s'affichent et le motif "
        "européen serait faux."
    )


def test_la_cause_du_vide_europeen_reste_couvert():
    """Le test le plus important : le premier jet se contredisait lui-même.

    `cause="non_collecte"` affichait « Non collecté » au-dessus d'une phrase
    disant « sont collectées » — la contradiction que ce correctif retire.
    """
    code = sans_commentaires(COMPOSANT.read_text(encoding="utf-8"))
    bloc = re.search(
        r"votes\.nonResolusEuropeens === votes\.total \?(.*?)\) : votes\.surEnsemble === 0 \?",
        code,
        re.DOTALL,
    )
    assert bloc, "Le bloc du cas européen a disparu ou changé de forme."
    assert 'cause="couvert"' in bloc.group(1), (
        "Ces positions SONT collectées — le tableau « ce que chaque liste "
        "porte » les compte. Déclarer `non_collecte` recréerait la "
        "contradiction (§2 règle 2)."
    )
    assert "rattachée à un scrutin identifié" in bloc.group(1), (
        "Le motif doit nommer la cause réelle : notre index ne rattache pas, "
        "la personne n'y est pour rien."
    )


def test_le_compte_d_adoptes_n_est_publie_que_si_un_sort_l_est():
    regles = sans_commentaires(MODULE_REGLES.read_text(encoding="utf-8"))
    assert "if (a.sort) sortsPublies += 1;" in regles, (
        "Sans ce compte, rien ne distingue « aucun adopté » de « aucun sort "
        "publié » (§2 règle 5)."
    )
    assert "sortsPublies," in regles, "`sortsPublies` n'est pas rendu à la vue."

    composant = sans_commentaires(COMPOSANT.read_text(encoding="utf-8"))
    # La garde porte désormais sur la population AFFICHÉE (`amdt`), depuis que
    # la section sépare les deux parlements (`amendements-deux-parlements-901`) :
    # le fait tenu est le même, le porteur a changé de nom.
    assert "amdt.sortsPublies === 0" in composant, (
        "La ligne de tête publie encore un `0` quand la source ne dit rien du "
        "sort : les 7 303 amendements européens affichaient « 0 adopté »."
    )
    assert "'sort non publié'" in composant, (
        "Le remplacement du zéro a disparu : une absence redeviendrait un zéro."
    )
