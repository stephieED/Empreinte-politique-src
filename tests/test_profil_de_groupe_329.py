"""Les arbitrages du lot 3 (#329) sont verrouillés dans le code exécuté.

Une fiche de groupe agrège les **468 profils `roster_groupe`**, qui n'ont pas de
page à eux — jamais les 13 `candidat_declare`. Cinq décisions y ont été rendues,
et chacune est le genre de choix qu'une session suivante défait sans s'en
apercevoir, parce qu'elle a l'air d'un détail de rendu :

  1. **La cohésion se publie en six nombres, jamais en barre.** Une barre de
     progression suggère une échelle du pire au meilleur ; ce sont des
     catégories, et les mettre sur un dégradé fabriquerait un jugement
     (AGENTS.md §2 règle 1). Les six décomptes forment une partition EXACTE de
     `membres_eligibles` : vérifié sur les 19 832 entrées des 5 fiches AN,
     `pour + contre + abstention + non_votant + absents + excuses ==
     membres_eligibles` sur 19 832 / 19 832.
  2. **`absents` se nomme « Sans trace de vote ».** Le pipeline compte là les
     membres éligibles pour lesquels AUCUN vote n'a été trouvé — une absence de
     donnée, pas une absence constatée. L'écrire « Absents » publierait un taux
     de présence (§2 règle 3), agrégé mais fabriqué quand même.
  3. **`excuses` vaut 0 sur les 19 832 entrées publiées**, faute de position
     `excuse` dans le corpus — exactement le cas d'`absent` dans les 1 312 951
     positions individuelles (#326). Un zéro structurel ne se publie pas comme
     un zéro mesuré (§2 règle 5).
  4. **Aucun compteur ne dit « aujourd'hui » (#653).** Les noms longs
     (`a_la_date_de_reference`) sont lus, et les anciens noms le sont AUSSI :
     les 2 fiches Sénat gelées (#516/#528) ne seront pas régénérées, et sans ce
     repli leurs 17 cartes de mandats rendaient `undefined`.
  5. **Une fiche de groupe ne nomme jamais qui s'est écarté de la ligne.**
     L'écart individu / groupe est une donnée de contrôle interne
     (`--rapport-interne`) : la publier serait un classement (§2 règles 1 et 7).

Ces tests lisent le **code exécuté** — les commentaires sont retirés avant
toute assertion, comme dans `tests/test_fondations_lecture_326.py`. Un
commentaire qui parle de « barre de cohérence » ne doit pas faire échouer le
test qui vérifie qu'elle a disparu.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
UI = RACINE / "web" / "UI_finale" / "src"

MODULE_REGLES_GROUPE = UI / "utils" / "groupe.js"
MODULE_REGLES_LECTURE = UI / "utils" / "lecture.js"
COMPOSANT_GROUPE = UI / "components" / "GroupProfile.jsx"
FEUILLE_GROUPE = UI / "components" / "GroupProfile.css"
ADAPTATEUR = UI / "data" / "pivotAdapter.js"

#: Les six décomptes d'une entrée de `cohesion_votes`, dans l'ordre publié par
#: `schema_groupe.py`. Leur somme retrouve `membres_eligibles` sur les 19 832
#: entrées des 5 fiches AN.
DECOMPTES_COHESION = ("pour", "contre", "abstention", "non_votant", "absents", "excuses")

#: Les paires (nom long #653/#656, ancien nom encore porté par les 2 fiches
#: Sénat gelées). Le rendu doit lire les DEUX : exiger le nom long ferait
#: échouer le portail de qualité sur des fichiers déjà publiés.
NOMS_DATES_ET_REPLIS = (
    ("a_la_date_de_reference", "actuel"),
    ("nb_membres_a_la_date_de_reference", "nb_membres_actifs"),
    ("nb_membres_cumul_historique", "nb_membres"),
    ("present_a_la_date_de_reference", "actif"),
)


def sans_commentaires(source: str) -> str:
    """Le code exécuté seul : ni `/* … */`, ni `// …`, ni `{/* … */}` de JSX.

    Le retrait de `//` épargne les `://` (une URL n'est pas un commentaire).
    """
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    return re.sub(r"(?<!:)//[^\n]*", "", source)


@pytest.fixture(scope="module")
def regles() -> str:
    return sans_commentaires(MODULE_REGLES_GROUPE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def composant() -> str:
    return sans_commentaires(COMPOSANT_GROUPE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def adaptateur() -> str:
    return sans_commentaires(ADAPTATEUR.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def feuille() -> str:
    return sans_commentaires(FEUILLE_GROUPE.read_text(encoding="utf-8"))


def test_le_module_des_regles_de_groupe_existe():
    """Les règles propres au groupe vivent à UN endroit, comme celles du lot 1."""
    assert MODULE_REGLES_GROUPE.is_file(), f"{MODULE_REGLES_GROUPE} est attendu par #329"
    assert MODULE_REGLES_LECTURE.is_file(), (
        "le module du lot 1 est le socle de celui-ci : #329 le consomme, il ne le remplace pas"
    )


def test_les_fondations_du_lot_1_sont_consommees_jamais_redefinies(regles, composant):
    """Six règles réécrites trois fois divergent trois fois (#326)."""
    assert "from './lecture'" in regles, (
        "`utils/groupe.js` doit importer les primitives du lot 1 (`ratio`, "
        "`formatNumber`) plutôt que d'en écrire une seconde version"
    )
    for primitive in ("ratio", "formatNumber"):
        assert not re.search(rf"^\s*(export\s+)?function\s+{primitive}\s*\(", regles, flags=re.M), (
            f"`{primitive}` est une primitive du lot 1 : `utils/groupe.js` ne la redéfinit pas"
        )
    assert "'../utils/lecture'" in composant and "'../utils/groupe'" in composant, (
        "GroupProfile.jsx lit les deux modules de règles, il n'en recopie aucune"
    )


# ── 1. Six nombres, jamais une barre ────────────────────────────────────────

def test_la_barre_de_coherence_a_disparu_du_rendu(composant, feuille):
    """Une barre suggère une échelle ; ce sont des catégories (§2 règle 1)."""
    for source, nom in ((composant, COMPOSANT_GROUPE.name), (feuille, FEUILLE_GROUPE.name)):
        for classe in ("gp-coherence-track", "gp-coherence-fill", "gp-coherence-nd"):
            assert classe not in source, (
                f"`{classe}` subsiste dans {nom} : la cohésion de vote se publie en six "
                "décomptes, jamais en barre de progression — une barre place quatre "
                "positions sur une échelle du pire au meilleur (AGENTS.md §2 règle 1)"
            )
    assert not re.search(r"width:\s*`\$\{[^}]*coherence", composant), (
        "aucune largeur ne doit être calculée depuis un taux de cohérence"
    )


def test_les_six_decomptes_sont_declares_dans_l_ordre_publie(regles):
    bloc = re.search(r"ORDRE_DECOMPTE_COHESION\s*=\s*\[(.*?)\];", regles, flags=re.DOTALL)
    assert bloc, "`ORDRE_DECOMPTE_COHESION` a disparu"
    declares = tuple(re.findall(r"'(\w+)'", bloc.group(1)))
    assert declares == DECOMPTES_COHESION, (
        "les six décomptes d'une entrée de `cohesion_votes` doivent être déclarés "
        f"dans l'ordre publié par schema_groupe.py : {DECOMPTES_COHESION}, pas {declares}"
    )

    libelles = re.search(r"LIBELLES_DECOMPTE_COHESION\s*=\s*\{(.*?)\n\};", regles, flags=re.DOTALL)
    assert libelles, "`LIBELLES_DECOMPTE_COHESION` a disparu"
    for cle in DECOMPTES_COHESION:
        assert re.search(rf"^\s{{2}}{cle}:", libelles.group(1), flags=re.M), (
            f"le décompte `{cle}` doit porter son libellé publié"
        )


def test_absents_ne_se_publie_jamais_sous_le_mot_absents(regles):
    """« Absents » publierait un taux de présence (§2 règle 3), pas une mesure."""
    libelles = re.search(r"LIBELLES_DECOMPTE_COHESION\s*=\s*\{(.*?)\n\};", regles, flags=re.DOTALL)
    ligne = re.search(r"^\s*absents:\s*'([^']+)'", libelles.group(1), flags=re.M)
    assert ligne, "le libellé de `absents` a disparu"
    assert "bsent" not in ligne.group(1), (
        f"`absents` ne doit pas s'afficher « {ligne.group(1)} » : le pipeline y compte les "
        "membres éligibles pour lesquels AUCUN vote n'a été trouvé — une absence de "
        "donnée, pas une absence constatée. Le nommer « absents » publierait un taux "
        "de présence individuel agrégé (AGENTS.md §2 règle 3)"
    )


def test_un_zero_structurel_ne_se_publie_pas_comme_un_zero_mesure(regles, adaptateur):
    """`excuses` vaut 0 sur les 19 832 entrées publiées (§2 règle 5)."""
    assert re.search(r"export function excusesRenseignees\(", regles), (
        "`excusesRenseignees` porte la mesure à l'échelle de la FICHE : une entrée "
        "à 0 ne dit pas si la source ne renseigne pas la valeur ou si personne "
        "n'était excusé ce jour-là ; un 0 partout sur 3 973 scrutins, si"
    )
    assert "excusesRenseignees(" in adaptateur, (
        "l'adaptateur doit décider par la fiche entière si `excuses` est publié"
    )
    assert "publierExcuses" in regles and "publierExcuses" in adaptateur, (
        "`publierExcuses` est ce qui empêche un zéro structurel de s'afficher "
        "comme un zéro mesuré (AGENTS.md §2 règle 5)"
    )


def test_le_ratio_de_cohesion_porte_ses_deux_nombres(regles):
    """§2 règle 7 : numérateur, dénominateur, ou `N/D` — jamais un pourcentage seul."""
    corps = re.search(r"export function ratioCohesion\(entree\)\s*\{(.*?)\n\}", regles, flags=re.DOTALL)
    assert corps, "`ratioCohesion` a disparu"
    assert "ratio(" in corps.group(1), (
        "le ratio de cohésion passe par la primitive `ratio` du lot 1, qui rend "
        "`N/D` sur un dénominateur absent ou nul plutôt que 0 %"
    )
    assert "membres_eligibles" in corps.group(1), (
        "le dénominateur est `membres_eligibles`, borné par chambre depuis #492 : "
        "une union sur tous les mandats électifs comptait un membre absent sur des "
        "scrutins où il ne pouvait plus voter, donc un faux dénominateur (§2 règle 7)"
    )
    assert "taux_coherence" not in corps.group(1), (
        "le taux pré-divisé ne se publie pas : la fiche publie ses deux nombres"
    )


# ── 2. Aucun compteur ne dit « aujourd'hui » ────────────────────────────────

@pytest.mark.parametrize("long_nom,ancien_nom", NOMS_DATES_ET_REPLIS, ids=lambda v: v)
def test_les_deux_formes_de_chaque_compteur_sont_lues(long_nom, ancien_nom, regles, adaptateur):
    """Les 2 fiches Sénat gelées gardent les anciens noms et ne seront pas régénérées.

    Exiger la clé longue les ferait échouer au portail de qualité ; ne lire que
    la clé longue rendait `undefined membre y a siégé au moins une fois` sur
    leurs 17 cartes de mandats.
    """
    lu = regles + adaptateur
    assert long_nom in lu, f"le nom daté `{long_nom}` (#653/#656) doit être lu"
    assert re.search(rf"\b{ancien_nom}\b", lu), (
        f"l'ancien nom `{ancien_nom}` doit être lu en repli : les 2 fiches Sénat "
        "gelées (#516/#528) ne seront pas régénérées et ne portent que lui"
    )


def test_la_date_de_reference_est_publiee_a_cote_des_comptes(regles, composant):
    """Un compteur daté qu'on ne peut pas dater à la lecture est un compteur nu."""
    assert "ORIGINES_DATE_REFERENCE" in regles, (
        "l'origine de la date (`cloture_legislature` | `generation`) se publie avec elle"
    )
    assert "dateReferenceDatee" in composant or "datee" in composant, (
        "le rendu doit distinguer « rapporté à une date » de « rapporté à aucune date »"
    )
    assert "ne publie aucune date de référence" in composant, (
        "sans date de référence, la page le DIT — elle n'en invente pas une et ne "
        "laisse pas lire « aujourd'hui » (#653)"
    )


def test_aucun_compteur_publie_ne_se_dit_actuel(composant, adaptateur):
    """« Effectif actuel » affichait `roster_total` : ni l'effectif, ni actuel."""
    for source, nom in ((composant, COMPOSANT_GROUPE.name), (adaptateur, ADAPTATEUR.name)):
        for libelle in re.findall(r"label:\s*'([^']*)'", source) + re.findall(
            r"label:\s*\"([^\"]*)\"", source
        ):
            assert "actuel" not in libelle.lower(), (
                f"{nom} publie le libellé « {libelle} » : aucun compteur d'une fiche "
                "de groupe ne dit « aujourd'hui », parce qu'aucune des 7 fiches "
                "publiées ne décrit la législature en cours (#653)"
            )


def test_siege_et_passe_restent_deux_nombres(regles, composant):
    """« Qui y siège » et « qui y est passé » ne se confondent pas (#656)."""
    assert re.search(r"export function siegeEtPasse\(", regles), "`siegeEtPasse` a disparu"
    assert "y est passé au moins une fois" in composant, (
        "le cumul reste publié, nommé comme un cumul : lire le cumul comme un "
        "effectif faisait dire à la fiche que 67 des 76 membres LFI siégeaient aux "
        "finances quand ils sont 5 (#656)"
    )
    assert "y siégeaient" in composant, "« qui y siège » reste le chiffre de tête"
    assert not re.search(r"poids_relatif", regles + composant), (
        "`poids_relatif` est retiré depuis #656 : il ne disait plus de laquelle "
        "des deux grandeurs il était le poids"
    )


# ── 3. La troncature déclare sa règle (lot 1, règle 3) ──────────────────────

def test_les_douze_cartes_declarent_leur_regle_et_leur_denominateur(regles, adaptateur, composant):
    """`slice(0, 12)` sur 3 832 à 4 099 scrutins : le lecteur voyait une coupe."""
    assert "NB_SCRUTINS_AFFICHES" in regles and "REGLE_TRONCATURE_COHESION" in regles, (
        "le nombre affiché et la règle de coupe sont déclarés, pas écrits dans un `slice`"
    )
    assert not re.search(r"slice\(0,\s*\d", adaptateur[adaptateur.find("buildGroupView"):]), (
        "le `slice` de la cohésion et celui des étiquettes doivent passer par les "
        "constantes déclarées, pour que le dénominateur affiché ne puisse pas diverger"
    )
    assert "<Troncature" in composant, (
        "la coupe s'annonce avec son total : c'est la règle 3 du lot 1 (#326)"
    )

    regle = re.search(r"REGLE_TRONCATURE_COHESION\s*=\s*'([^']+)'", regles)
    assert regle, "`REGLE_TRONCATURE_COHESION` a disparu"
    assert "récent" in regle.group(1), (
        "la règle affichée est vérifiable et vérifiée : `cohesion_votes` est trié "
        "par date de scrutin décroissante sur les 5 fiches AN (19 832 / 19 832 "
        "entrées jointes à `pivot_data/scrutins.json`)"
    )
    assert "important" not in regle.group(1), (
        "« les plus importants » serait un jugement (AGENTS.md §2 règle 1) ; "
        "« les plus récents » est un fait"
    )


# ── 4. `meta` se lit, et rien ne le lisait ──────────────────────────────────

def test_l_etat_et_la_preuve_de_couverture_sont_lus(regles, composant):
    """15 profils sur 235 est un périmètre, pas une perte — et l'état le dit."""
    assert "couverture_roster" in regles, "`meta.couverture_roster` doit être lu (#329)"
    for etat in ("dans_le_perimetre", "hors_perimetre"):
        assert etat in regles, (
            f"l'état `{etat}` de `schema_groupe.ETATS_COUVERTURE_ROSTER` doit être "
            "traduit : un ratio seul ne dit pas de quoi il est le ratio"
        )
    assert "preuve" in regles and "preuve" in composant, (
        "la `preuve` est exigée par le schéma sur `hors_perimetre` et doit être "
        "publiée verbatim : elle porte ses références et sa condition de reprise"
    )
    assert "seuilQuorum" in composant, (
        "`meta.seuil_quorum` se publie à côté du quorum : sans lui, « quorum non "
        "atteint » se lirait comme un seuil réglementaire"
    )


def test_un_etat_de_couverture_inconnu_ne_devient_jamais_aucun_resultat(regles):
    """Même règle que les quatre causes du lot 1 (§2 règle 5)."""
    corps = re.search(
        r"export function couvertureRoster\(groupe\)\s*\{(.*?)\n\}", regles, flags=re.DOTALL
    )
    assert corps, "`couvertureRoster` a disparu"
    assert "connu ?" in corps.group(1) or "connu\n" in corps.group(1), (
        "un état inconnu doit se déclarer comme non renseigné, jamais tomber sur "
        "l'un des deux états connus"
    )
    assert "non publié" in corps.group(1) or "non publié" in regles, (
        "un état absent se dit « non publié » : c'est un fait sur la fiche, pas sur le groupe"
    )


# ── 5. Les écarts individu / groupe restent internes ────────────────────────

def test_la_fiche_ne_nomme_jamais_qui_s_est_ecarte_de_la_ligne(regles, composant):
    """§2 règle 7 : l'écart individu / groupe est un contrôle interne."""
    assert "REFUS_FICHE_GROUPE" in regles, (
        "ce qui est interdit est écrit, pas seulement omis (#326)"
    )
    assert "ne nomme jamais qui s'est écarté" in regles + composant, (
        "la fiche déclare qu'elle ne nomme pas les écarts : les publier désignerait "
        "qui s'est écarté de la ligne, c'est-à-dire un classement interne au groupe "
        "(AGENTS.md §2 règles 1 et 7)"
    )

    # La carte de scrutin ne doit porter aucune liste nominative.
    carte = re.search(r"gp-vote-card(.*?)gp-vote-footer", composant, flags=re.DOTALL)
    assert carte, "la carte de scrutin a disparu"
    for interdit in ("membres", "membre_id", "nom"):
        assert not re.search(rf"vote\.{interdit}\b", carte.group(1)), (
            f"une carte de scrutin ne lit jamais `vote.{interdit}` : elle publie des "
            "décomptes, jamais qui a pris quelle position"
        )


# ── 6. L'empreinte thématique : jamais une étiquette sans son porteur ───────
#
# Passée de la case D à la case A du tableau de #329 le 31/08/2026 : le motif
# de son report — « 0 / 468 membres de roster portent une intervention ou un
# tag » — est périmé depuis #657. Re-mesuré au commit `c6edee05` : **448 des
# 468** profils `roster_groupe` portent au moins une étiquette, les 5 fiches AN
# en publient de **1 554** (`AN:SOC`) à **4 303** (`AN:REN`), et
# `nb_membres_porteurs` y monte jusqu'à **99**. Les 2 fiches Sénat restent à 0,
# parce qu'elles sont conservées et jamais régénérées (#528).

def test_une_etiquette_ne_se_publie_jamais_sans_son_nombre_de_porteurs(regles, composant):
    """Sinon la fiche donne l'empreinte d'UNE personne pour celle d'un groupe."""
    corps = re.search(
        r"export function etiquettesThematiques\(.*?\n\}", regles, flags=re.DOTALL
    )
    assert corps, "`etiquettesThematiques` a disparu"
    assert "nb_membres_porteurs" in corps.group(0), (
        "chaque étiquette part avec son `nb_membres_porteurs` : une étiquette "
        "portée par 1 membre sur 76 ne dit pas ce que dit une étiquette portée "
        "par 60 (AGENTS.md §2 règle 7)"
    )
    assert "ratio(" in corps.group(0), (
        "le nombre de porteurs passe par la primitive `ratio` du lot 1, qui rend "
        "`N/D` plutôt qu'un nombre sans dénominateur"
    )
    assert "poids_relatif" not in corps.group(0), (
        "`poids_relatif` est un ratio pré-divisé : la fiche publie ses deux "
        "nombres, comme `mandats_agreges` depuis #656"
    )

    pastille = re.search(r"gp-tag-pill(.*?)</span>\s*\)\)\}", composant, flags=re.DOTALL)
    assert pastille, "la pastille d'étiquette a disparu"
    assert "porteurs" in pastille.group(1) and "denominateur" in pastille.group(1), (
        "la pastille affiche les deux nombres, pas l'étiquette seule : c'est le "
        "défaut exact que #657 a corrigé côté données"
    )


def test_le_denominateur_des_etiquettes_est_la_population_reellement_lue(regles):
    """`len(membres)`, jamais `roster_total` — qui compte des membres sans profil."""
    corps = re.search(
        r"export function etiquettesThematiques\(.*?\n\}", regles, flags=re.DOTALL
    )
    assert "membres" in corps.group(0), "le dénominateur est le nombre d'entrées de `membres[]`"
    assert "roster_total" not in corps.group(0), (
        "`roster_total` compte des membres dont aucun profil n'est publié : "
        "l'agrégation ne les a pas lus, ils ne peuvent pas être au dénominateur"
    )


def test_les_etiquettes_ne_se_lisent_pas_comme_des_positions_du_groupe(composant):
    """§2 règle 8 : aides à la lecture, jamais des positions déclarées."""
    assert "Ce n'est pas une position" in composant, (
        "la section doit écrire que ces étiquettes ne sont pas des positions du "
        "groupe (AGENTS.md §2 règle 8) : ce sont les sujets sur lesquels ses "
        "membres sont intervenus, et intervenir sur un texte c'est aussi bien le "
        "combattre que le défendre"
    )
    for verbe in ("défend", "soutient", "priorité", "combat de"):
        assert f"groupe {verbe}" not in composant.lower(), (
            f"« groupe {verbe} » ferait de l'étiquette une position déclarée (§2 règle 8)"
        )


def test_une_empreinte_vide_dit_pourquoi_et_n_affiche_jamais_zero(composant):
    """Les 2 fiches Sénat sont à 0 étiquette : c'est une décision, pas un résultat."""
    bloc = re.search(
        r"Empreinte thématique.*?gp-tags-card(.*?)\n          </div>", composant, flags=re.DOTALL
    )
    assert bloc, "la section « Empreinte thématique » a disparu"
    assert "<ListeVide" in bloc.group(1), (
        "une empreinte vide passe par `ListeVide` (règle 1 du lot 1) : les 2 fiches "
        "Sénat sont à 0 étiquette parce qu'elles sont conservées et jamais "
        "régénérées (#528), et ce vide est une décision, pas une mesure"
    )
    assert "causeListeVide" in bloc.group(1) and "motifListeVide" in bloc.group(1), (
        "la cause ET son motif sont passés : une cause seule tomberait sur la "
        "phrase par défaut, qui parle d'une collecte aboutie"
    )
