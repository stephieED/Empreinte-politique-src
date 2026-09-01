"""Les arbitrages du lot 3 (#329) sont verrouillés dans le code exécuté.

La fiche de groupe a été **reprise de bout en bout**. Sa première version était
éditorialement irréprochable et structurellement inutilisable : ses sections
s'appelaient « Cohésion de vote », « Empreinte thématique », « Amendements
déposés » — le vocabulaire du schéma, pas les questions de quelqu'un qui cherche
à comprendre un groupe. Et son fait le plus important, le rapport entre scrutins
agrégés et scrutins mesurables, était enterré en fin de section « Vérification ».

Une fiche de groupe agrège les **468 profils `roster_groupe`**, qui n'ont pas de
page à eux — jamais les 13 `candidat_declare`.

Neuf décisions y ont été rendues, et chacune est le genre de choix qu'une
session suivante défait sans s'en apercevoir, parce qu'elle a l'air d'un détail
de rendu :

  1. **Six sections, dans l'ordre des questions**, une seule focale à la fois :
     l'interne d'abord, la comparaison à la fin. Le **quorum ouvre la section
     des votes**, pas la page — « tout ce qui suit porte sur les 341 » est utile
     juste avant des chiffres de cohésion, et décourageant en première page.
  2. **Les absences ne franchissent jamais l'écran.** `absents` et `excuses`
     partitionnent `membres_eligibles` avec les quatre positions, et ne sortent
     pas du fichier : publiés, agrégés ou non, ils deviennent un taux de présence
     sur des personnes nommées (AGENTS.md §2 règle 3). La version précédente les
     publiait sous des libellés prudents — un libellé prudent sur une donnée
     interdite reste la donnée interdite.
  3. **Aucun taux synthétique ne sort du fichier.** `taux_coherence`,
     `taux_coherence_hors_absents`, `taux_participation` sont dans la donnée :
     un chiffre unique par groupe est une note, et cinq notes un classement.
  4. **Aucun intitulé de fonction n'est perdu.** 40 libellés distincts sur les 7
     fiches ; ce que la table ne reconnaît pas tombe dans « Autres fonctions »,
     qui est AFFICHÉ avec ses intitulés d'origine. Mesuré : la maquette de cette
     refonte publiait 1 351 sièges simples pour `AN:SOC` là où la fiche en porte
     1 352 — un « représentant suppléant » rangé nulle part.
  5. **Déposer comme rapporteur et comme député sont deux actes** : `AGENTS.md`
     §5 interdit d'en faire un taux commun. Deux lignes séparées, jamais
     additionnées.
  6. **La posture est recopiée, jamais déduite** (#686). Portée par 5 des 7
     fiches depuis le commit de données `693b076d` ; les 2 fiches du Sénat,
     gelées depuis #516, la DÉCLARENT absente. Dans les deux cas elle ne se
     dérive d'aucun comportement de vote (§2 règle 1).
  7. **La comparaison est réunie par posture, jamais alignée** sur une échelle
     unique, et son ordre est celui du nombre de scrutins comparables — pas celui
     de l'accord.
  8. **« Nuance » n'est pas « opposé »** : une abstention face à une position
     exprimée n'est pas un vote contraire. Mesuré : SOC et RN ne sont opposés que
     46 fois sur 231, mais en nuance 106 — un décompte brut aurait affiché
     « 152 divergences ».
  9. **Une fiche de groupe ne nomme jamais qui s'est écarté de la ligne.**
     L'écart individu / groupe est une donnée de contrôle interne
     (`--rapport-interne`) : la publier serait un classement (§2 règles 1 et 7).

Ces tests lisent le **code exécuté** — les commentaires sont retirés avant toute
assertion, comme dans `tests/test_fondations_lecture_326.py`. Un commentaire qui
parle de « barre de cohérence » ne doit pas faire échouer le test qui vérifie
qu'elle a disparu.
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
CHARGEUR = UI / "data" / "index.js"
PROJECTION = RACINE / "web" / "UI_finale" / "scripts" / "comparaison-groupes.mjs"

#: Les six sections, dans l'ordre, telles qu'elles s'affichent. L'ordre EST la
#: décision : une seule focale à la fois, l'interne d'abord.
SECTIONS = (
    "Qui sont-ils",
    "Sur quoi ils choisissent de travailler",
    "Ce qu'ils proposent, et ce qu'il en reste",
    "Comment ils votent",
    "Comment ils se situent parmi les groupes de la même législature",
    "Ce que cette fiche ne dit pas, et pourquoi",
)

#: Les deux décomptes qui ne franchissent jamais l'écran.
DECOMPTES_INTERDITS = ("absents", "excuses")

#: Les trois taux synthétiques que la donnée porte et que la page ne publie pas.
TAUX_INTERDITS = ("taux_coherence", "taux_coherence_hors_absents", "taux_participation")

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


@pytest.fixture(scope="module")
def projection() -> str:
    return sans_commentaires(PROJECTION.read_text(encoding="utf-8"))


def test_les_modules_de_regles_existent():
    """Les règles propres au groupe vivent à UN endroit, comme celles du lot 1."""
    assert MODULE_REGLES_GROUPE.is_file(), f"{MODULE_REGLES_GROUPE} est attendu par #329"
    assert MODULE_REGLES_LECTURE.is_file(), (
        "le module du lot 1 est le socle de celui-ci : #329 le consomme, il ne le remplace pas"
    )
    assert PROJECTION.is_file(), (
        "la projection de comparaison entre groupes (#329) est ce qui permet à la fiche de "
        "comparer sans télécharger les fiches voisines"
    )


def test_les_fondations_du_lot_1_sont_consommees_jamais_redefinies(regles, composant):
    """Six règles réécrites trois fois divergent trois fois (#326)."""
    assert "from './lecture'" in regles, (
        "`utils/groupe.js` doit importer les primitives du lot 1 (`ratio`, `formatNumber`, "
        "`isWholeTextVote`, `normalizeLabel`) plutôt que d'en écrire une seconde version"
    )
    for primitive in ("ratio", "formatNumber", "isWholeTextVote", "normalizeLabel"):
        assert not re.search(rf"^\s*(export\s+)?function\s+{primitive}\s*\(", regles, flags=re.M), (
            f"`{primitive}` est une primitive du lot 1 : `utils/groupe.js` ne la redéfinit pas"
        )
    assert "'../utils/lecture'" in composant and "'../utils/groupe'" in composant, (
        "GroupProfile.jsx lit les deux modules de règles, il n'en recopie aucune"
    )


# ── 1. Six sections, dans l'ordre, et le quorum en tête des votes ────────────

def test_les_six_sections_sont_rendues_dans_l_ordre(composant):
    """L'ordre EST la décision : une seule focale, l'interne avant la comparaison."""
    positions = []
    for titre in SECTIONS:
        motif = re.escape(titre).replace(r"\'", "['’]")
        trouve = re.search(rf'titre="{motif}"', composant)
        assert trouve, f"la section « {titre} » a disparu du rendu (#329)"
        positions.append(trouve.start())
    assert positions == sorted(positions), (
        "les six sections doivent se suivre dans l'ordre des questions : "
        f"{SECTIONS}. L'interne d'abord, la comparaison à la fin — la première refonte "
        "zigzaguait entre les deux, quatre changements de focale."
    )


def test_le_quorum_ouvre_la_section_des_votes_et_non_la_page(composant):
    """« Tout ce qui suit porte sur les 341 » est décourageant en première page."""
    quorum = composant.index("<Quorum quorum={group.quorum} />")
    votes = composant.index('titre="Comment ils votent"')
    partage = composant.index("<Partage partage={group.partage} />")
    qui = composant.index('titre="Qui sont-ils"')
    assert qui < votes < quorum < partage, (
        "le quorum doit ouvrir la section des votes — après « qui sont-ils », et AVANT "
        "tout chiffre de cohésion, parce que tout ce qui suit en dépend"
    )


# ── 2. Les absences ne franchissent jamais l'écran ──────────────────────────

def test_les_deux_decomptes_interdits_sont_nommes_dans_les_regles(regles):
    bloc = re.search(r"DECOMPTES_JAMAIS_PUBLIES\s*=\s*\[(.*?)\];", regles, flags=re.DOTALL)
    assert bloc, (
        "`DECOMPTES_JAMAIS_PUBLIES` déclare, dans le code exécuté, les décomptes que la "
        "page ne publie pas. Une interdiction qui ne vit que dans un commentaire n'est pas "
        "une interdiction"
    )
    declares = tuple(re.findall(r"'(\w+)'", bloc.group(1)))
    assert declares == DECOMPTES_INTERDITS, (
        f"les deux décomptes interdits sont {DECOMPTES_INTERDITS}, pas {declares}"
    )


@pytest.mark.parametrize("decompte", DECOMPTES_INTERDITS)
def test_aucune_absence_n_est_lue_par_le_rendu(decompte, composant, adaptateur, projection):
    """Un libellé prudent sur une donnée interdite reste la donnée interdite."""
    for source, nom in (
        (composant, COMPOSANT_GROUPE.name),
        (adaptateur, ADAPTATEUR.name),
        (projection, PROJECTION.name),
    ):
        assert not re.search(rf"[.\[]\s*'?{decompte}'?\s*\]?", source), (
            f"`{decompte}` est lu dans {nom} : publié, agrégé ou non, ce décompte devient "
            "un taux de présence sur des personnes nommées (AGENTS.md §2 règle 3). Il ne "
            "doit franchir ni l'adaptateur, ni la projection, ni le composant"
        )


def test_les_largeurs_affichees_ne_rapportent_rien_aux_membres_eligibles(regles):
    """Rapporter une barre à `membres_eligibles` ferait entrer une absence dans un %."""
    bloc = re.search(r"export function partageDuGroupe\(groupe\) \{(.*?)\n\}", regles, flags=re.DOTALL)
    assert bloc, "`partageDuGroupe` a disparu"
    corps = bloc.group(1)
    assert "d.valeur / total" in corps or "/ total" in corps, (
        "la part de chaque position se calcule sur le total des voix EXPRIMÉES"
    )
    assert not re.search(r"/\s*(entree\.)?membres_eligibles", corps), (
        "aucune largeur ne se rapporte à `membres_eligibles` : les absences n'entrent "
        "dans aucun pourcentage affiché (AGENTS.md §2 règle 3). Le nombre d'éligibles "
        "reste publié en clair à côté, comme dénominateur nommé"
    )


# ── 3. Aucun taux synthétique ne sort du fichier ────────────────────────────

@pytest.mark.parametrize("taux", TAUX_INTERDITS)
def test_aucun_taux_synthetique_n_atteint_l_ecran(taux, regles, composant, adaptateur, projection):
    for source, nom in (
        (regles, MODULE_REGLES_GROUPE.name),
        (composant, COMPOSANT_GROUPE.name),
        (adaptateur, ADAPTATEUR.name),
        (projection, PROJECTION.name),
    ):
        assert taux not in source, (
            f"`{taux}` est lu dans {nom} : un chiffre unique par groupe est une note, et "
            "cinq notes sont un classement (AGENTS.md §2 règle 1). Ces taux restent dans "
            "le fichier"
        )


def test_la_barre_de_coherence_a_disparu_du_rendu(composant, feuille):
    """Une barre suggère une échelle ; ce sont des catégories (§2 règle 1)."""
    for source, nom in ((composant, COMPOSANT_GROUPE.name), (feuille, FEUILLE_GROUPE.name)):
        for classe in ("gp-coherence-track", "gp-coherence-fill", "gp-coherence-nd"):
            assert classe not in source, (
                f"`{classe}` subsiste dans {nom} : la cohésion ne se publie jamais en barre "
                "de progression — une barre place les positions sur une échelle du pire au "
                "meilleur (AGENTS.md §2 règle 1)"
            )
    assert not re.search(r"width:\s*`\$\{[^}]*coherence", composant), (
        "aucune largeur ne doit être calculée depuis un taux de cohérence"
    )


def test_le_refus_de_l_indice_est_ecrit_et_publie(regles, composant):
    """Ce qui est interdit est écrit — du contenu publié, pas un commentaire."""
    assert "'indice-de-cohesion'" in regles, (
        "le refus de publier un indice de cohésion doit être une entrée de "
        "`REFUS_FICHE_GROUPE`, donc du contenu publié"
    )
    assert "group.refus" in composant, (
        "la section 6 doit rendre les refus : une page qui se contente de ne pas répondre "
        "laisse croire qu'elle n'y a pas pensé"
    )


# ── 4. Aucun intitulé de fonction n'est perdu ───────────────────────────────

def test_un_libelle_de_fonction_inconnu_tombe_dans_autre_et_jamais_dans_le_vide(regles):
    bloc = re.search(r"export function classeDeFonction\(libelle\) \{(.*?)\n\}", regles, flags=re.DOTALL)
    assert bloc, "`classeDeFonction` a disparu"
    corps = bloc.group(1)
    assert corps.rstrip().endswith("return 'autre';"), (
        "un libellé que la table ne reconnaît pas doit tomber dans `autre`, jamais être "
        "ignoré : la maquette de cette refonte a publié 1 351 sièges simples pour `AN:SOC` "
        "là où la fiche en porte 1 352, faute d'avoir rangé « représentant suppléant »"
    )
    ordre = re.search(r"ORDRE_CLASSES_FONCTION\s*=\s*\[(.*?)\];", regles, flags=re.DOTALL)
    assert ordre and "'autre'" in ordre.group(1), (
        "`autre` doit faire partie de l'ordre d'affichage : une classe qui n'est pas rendue "
        "est une classe perdue"
    )


def test_la_classe_autre_publie_les_intitules_de_la_source(regles, composant):
    """Rangés d'office, ces intitulés mentiraient ; publiés, ils se vérifient."""
    assert re.search(r"libelles:\s*\[", regles), (
        "`fonctionsDuGroupe` doit conserver les intitulés d'origine de chaque classe"
    )
    assert "c.cle === 'autre'" in composant and "c.libelles" in composant, (
        "le rendu doit afficher les intitulés d'origine des fonctions rangées dans "
        "« Autres fonctions » — mesuré : 9 intitulés ministériels et de chargé de mission "
        "sur `AN:REN`, qu'un rangement d'office aurait fait passer pour des sièges simples"
    )


def test_la_table_des_fonctions_ne_reconnait_pas_un_prefixe_de_presidence(regles):
    """« membre de droit (président de la commission des lois) » est un siège."""
    prefixes = re.search(r"PREFIXES_SIEGE\s*=\s*\[(.*?)\];", regles, flags=re.DOTALL)
    assert prefixes, "`PREFIXES_SIEGE` a disparu"
    assert "'membre de droit'" in prefixes.group(1), (
        "« membre de droit (président de la commission…) » porte l'instance entre "
        "parenthèses : c'est un siège occupé de droit, pas une présidence de plus. "
        "Un motif cherché en sous-chaîne le rangerait parmi les présidences"
    )


# ── 5. Rapporteur et député ne s'additionnent pas ───────────────────────────

def test_les_types_de_deposant_restent_des_lignes_separees(adaptateur, composant):
    bloc = re.search(r"const TYPES_DEPOSANT = \[(.*?)\n\];", adaptateur, flags=re.DOTALL)
    assert bloc, "`TYPES_DEPOSANT` a disparu"
    for cle in ("depute", "commission_rapporteur", "gouvernement"):
        assert f"cle: '{cle}'" in bloc.group(1), f"le type de déposant `{cle}` doit être publié à part"
    assert "parTypeDeposant.map" in composant, (
        "chaque type de déposant garde sa ligne : `AGENTS.md` §5 interdit d'agréger un "
        "taux d'adoption sur des types de déposant différents"
    )
    assert "taux_adoption" not in adaptateur and "taux_adoption" not in composant, (
        "`taux_adoption` est publié par le schéma de groupe et ne doit atteindre ni "
        "l'adaptateur ni le rendu : un taux commun ne décrirait ni l'un ni l'autre des "
        "deux actes (AGENTS.md §5)"
    )


def test_un_zero_de_procedure_se_declare_comme_un_fait(adaptateur):
    """Un groupe parlementaire ne dépose pas au nom du gouvernement."""
    assert "zeroEstUnFait" in adaptateur, (
        "un 0 de procédure — les amendements du gouvernement sur une fiche de groupe — "
        "se publie comme un fait, et un 0 non mesuré ne se publie pas du tout "
        "(AGENTS.md §2 règle 5). Les deux cas ne se confondent pas"
    )


# ── 6. La posture est recopiée, jamais déduite ──────────────────────────────

def test_une_posture_absente_se_declare_et_ne_se_replie_sur_rien(regles):
    bloc = re.search(r"export function postureDuGroupe\(groupe\) \{(.*?)\n\}", regles, flags=re.DOTALL)
    assert bloc, "`postureDuGroupe` a disparu"
    corps = bloc.group(1)
    assert "declaree: false" in corps, (
        "5 des 7 fiches portent `position_politique` depuis le commit de données "
        "`693b076d` ; les 2 fiches du Sénat, gelées depuis #516, ne l'auront jamais. "
        "La fonction doit rendre `declaree: false` plutôt que se replier sur une valeur"
    )
    assert "position_politique" in corps, (
        "la posture se lit dans le champ recopié du référentiel (#686)"
    )
    for signal in ("cohesion_votes", "position_majoritaire", "convergences("):
        assert signal not in corps, (
            f"`{signal}` apparaît dans `postureDuGroupe` : une posture ne se déduit JAMAIS "
            "d'un comportement de vote (AGENTS.md §2 règle 1). Elle est recopiée de la "
            "déclaration de l'Assemblée, ou déclarée absente"
        )


def test_non_declaree_reste_distincte_d_un_champ_absent(regles):
    """`non_declaree` est une valeur PUBLIÉE ; l'absence du champ n'en est pas une."""
    assert "non_declaree" in regles, (
        "`non_declaree` fait partie du vocabulaire fermé de `position_politique.position` "
        "(schema_groupe.py) : les 14 groupes de la XVIIe sont dans ce cas"
    )
    assert "'Posture non publiée'" in regles, (
        "« l'Assemblée ne l'a pas déclaré » n'est pas « notre fiche ne porte pas le "
        "champ » : les deux se disent différemment (AGENTS.md §2 règle 5)"
    )


# ── 7. La comparaison est réunie par posture ────────────────────────────────

def test_la_comparaison_reunit_par_posture_et_ne_classe_pas(regles, composant):
    assert re.search(r"export function comparaisonParPosture\(", regles), (
        "la comparaison se réunit par posture : un groupe majoritaire et un groupe "
        "d'opposition ne font pas le même métier, et les aligner sur une échelle unique "
        "les mettrait en concurrence sur une tâche qu'ils ne partagent pas (§2 règle 1)"
    )
    assert "posturesSansFiche" in regles and "posturesSansFiche" in composant, (
        "les postures qu'aucune fiche ne porte se disent, plutôt que de laisser croire "
        "qu'elles n'existent pas (AGENTS.md §2 règle 5)"
    )
    assert "Aucun pourcentage n'est affiché" in composant, (
        "la section doit écrire qu'aucun pourcentage n'y est publié : un taux d'adoption "
        "comparé entre groupes serait un classement"
    )


def test_l_ordre_des_convergences_est_celui_des_scrutins_comparables(regles):
    bloc = re.search(r"export function convergences\(comparaison, sigleDuGroupe\) \{(.*?)\n\}", regles, flags=re.DOTALL)
    assert bloc, "`convergences` a disparu"
    tri = re.search(r"\.sort\(\(a, b\) => (.*?)\);", bloc.group(1), flags=re.DOTALL)
    assert tri and "b.communs - a.communs" in tri.group(1), (
        "l'ordre est celui du nombre de scrutins comparables, pas celui de l'accord : "
        "trier par accord ferait un classement des alliés (AGENTS.md §2 règle 1)"
    )
    assert "meme_sens" not in tri.group(1), (
        "le tri ne doit pas dépendre du nombre de scrutins votés dans le même sens"
    )


def test_la_comparaison_ne_compare_que_ce_qui_a_atteint_son_quorum(projection, regles):
    """Les dénominateurs diffèrent d'une ligne à l'autre, et chacun est publié."""
    assert "quorum_atteint !== true" in projection, (
        "la projection n'embarque que les scrutins où le quorum est atteint : en dessous, "
        "rien n'est publié — pas même approché, donc pas même transporté"
    )
    assert "denominateurLabel" in regles, (
        "chaque ligne de convergence publie son dénominateur nommé (AGENTS.md §2 règle 7)"
    )


# ── 8. « Nuance » n'est pas « opposé » ──────────────────────────────────────

def test_une_abstention_n_est_jamais_comptee_comme_un_vote_contraire(regles):
    bloc = re.search(
        r"export function natureDeConvergence\(positionA, positionB\) \{(.*?)\n\}",
        regles, flags=re.DOTALL,
    )
    assert bloc, "`natureDeConvergence` a disparu"
    corps = bloc.group(1)
    assert "'oppose'" in corps and "'nuance'" in corps, "les trois natures doivent être distinguées"
    oppose = corps[corps.index("return 'oppose'") - 400 : corps.index("return 'oppose'")]
    assert "abstention" not in oppose, (
        "« opposé » ne se prononce que sur un couple pour / contre : une abstention face à "
        "une position exprimée est une NUANCE. Mesuré au commit `e40d0d32` : SOC et RN ne "
        "sont opposés que 46 fois sur 231, mais en nuance 106 — un décompte brut aurait "
        "affiché « 152 divergences »"
    )
    assert "'autres'" in corps, (
        "un couple que les trois natures ne décrivent pas se compte à part, plutôt que "
        "d'être rangé d'office en nuance : il vaut 0 sur les quatre paires mesurées, et "
        "ce zéro doit rester vérifiable (AGENTS.md §2 règle 5)"
    )


# ── 9. La fiche ne nomme jamais qui s'est écarté ────────────────────────────

def test_la_fiche_ne_nomme_jamais_qui_s_est_ecarte_de_la_ligne(regles, composant, adaptateur):
    """Désigner les écarts produirait un classement interne au groupe (§2 règles 1 et 7)."""
    assert "'ecarts-individuels'" in regles, (
        "le refus doit être une entrée de `REFUS_FICHE_GROUPE`, donc du contenu publié"
    )
    for source, nom in ((composant, COMPOSANT_GROUPE.name), (adaptateur, ADAPTATEUR.name)):
        assert "ecartsAvecLeGroupe(" not in source or nom == ADAPTATEUR.name, (
            f"{nom} ne doit pas calculer d'écart individu / groupe sur une fiche de groupe"
        )
    bloc = re.search(r"export function partageDuGroupe\(groupe\) \{(.*?)\n\}", regles, flags=re.DOTALL)
    assert "membre" not in bloc.group(1).replace("membres_eligibles", ""), (
        "les scrutins partagés se publient en DÉCOMPTES : combien de membres ont pris "
        "chaque position, jamais lesquels"
    )
    assert "minoritaires" in bloc.group(1), (
        "le nombre de voix minoritaires sert de critère de tri et ne s'affiche pas : un "
        "« nombre de dissidents » publié serait l'indice individuel par un autre chemin"
    )
    assert "e.minoritaires" not in composant and "{e.minoritaires}" not in composant, (
        "le nombre de voix minoritaires ne doit pas atteindre l'écran"
    )


# ── Ce que le lot précédent avait déjà réglé, et qui doit tenir ─────────────

@pytest.mark.parametrize(("long_nom", "ancien_nom"), NOMS_DATES_ET_REPLIS)
def test_les_deux_formes_de_chaque_compteur_sont_lues(long_nom, ancien_nom, regles, adaptateur):
    """Les 2 fiches Sénat gelées (#516/#528) ne seront pas régénérées."""
    ensemble = regles + adaptateur
    assert long_nom in ensemble, f"le nom long `{long_nom}` (#653/#656) doit être lu"
    assert ancien_nom in ensemble, (
        f"l'ancien nom `{ancien_nom}` doit rester lu : les 2 fiches Sénat gelées le portent "
        "encore, et exiger le nom long ferait échouer le rendu sur des fichiers publiés"
    )


def test_aucun_compteur_publie_ne_se_dit_actuel(composant, adaptateur):
    """« Actif » sur un groupe de la XVIe disait « encore député⋅e en 2026 » (#653)."""
    for source, nom in ((composant, COMPOSANT_GROUPE.name), (adaptateur, ADAPTATEUR.name)):
        assert not re.search(r"'[^']*[Aa]ctuel", source), (
            f"un libellé « actuel » subsiste dans {nom} : aucune des 7 fiches ne décrit la "
            "législature en cours, et un compteur « actuel » y mesurait la carrière "
            "ultérieure des membres (#653)"
        )


def test_la_date_de_reference_est_publiee_a_cote_des_comptes(regles, composant):
    assert re.search(r"export function dateDeReference\(", regles), "`dateDeReference` a disparu"
    assert "dateReferenceDatee" in composant, (
        "le rendu doit distinguer une fiche datée d'une fiche qui ne l'est pas : `datee: "
        "false` ne veut pas dire « aujourd'hui »"
    )


def test_siege_et_passe_restent_deux_nombres(regles, composant):
    """Lire le cumul comme un effectif faisait dire à la fiche que 67 des 76 membres
    LFI siégeaient aux finances quand ils sont 5 (#656)."""
    assert re.search(r"export function siegeEtPasse\(", regles), "`siegeEtPasse` a disparu"
    assert "m.passe" in composant and "m.siege" in composant, (
        "un mandat agrégé porte deux quantités — qui y siège et qui y est passé —, et le "
        "rendu doit les distinguer"
    )


def test_l_etat_et_la_preuve_de_couverture_sont_lus(regles, composant):
    assert re.search(r"export function couvertureRoster\(", regles), "`couvertureRoster` a disparu"
    assert "couverture.preuve" in composant, (
        "`meta.couverture_roster.preuve` est publiée sur 7 / 7 fiches : le ratio seul ne "
        "dit pas de quoi il est le ratio — `groupe-Senat-LR` publie 15 profils sur 235, et "
        "c'est un périmètre, pas une perte"
    )
    assert "causeListeVide" in composant, (
        "une liste vide dit POURQUOI, dans le vocabulaire du lot 1 (#326)"
    )


def test_une_fiche_hors_perimetre_ne_publie_pas_de_zeros_comparables(composant):
    """Les 2 fiches Sénat portent 0 amendement parce que leur collecte est suspendue."""
    assert "causeListeVide === 'non_collecte'" in composant, (
        "sur une fiche dont la collecte est suspendue (#516/#528), la comparaison entre "
        "groupes publierait des zéros qui ne sont pas des mesures (AGENTS.md §2 règle 5)"
    )


def test_une_etiquette_ne_se_publie_jamais_sans_son_nombre_de_porteurs(regles, composant):
    assert re.search(r"export function etiquettesThematiques\(", regles), (
        "`etiquettesThematiques` a disparu"
    )
    assert "t.porteurs" in composant and "t.denominateur" in composant, (
        "une étiquette portée par 1 membre sur 76 ne dit pas ce que dit une étiquette "
        "portée par 60 : le nombre de porteurs part AVEC l'étiquette, jamais après elle"
    )
    assert "poids_relatif" not in composant, (
        "`poids_relatif` n'est pas publié : la fiche donne ses deux nombres (§2 règle 7)"
    )


def test_les_etiquettes_ne_se_lisent_pas_comme_des_positions_du_groupe(composant):
    # Le JSX enveloppe ses phrases : on compare sur une forme sans retour à la ligne.
    aplati = re.sub(r"\s+", " ", composant)
    assert "jamais des positions du groupe" in aplati, (
        "la section doit écrire que ce sont les SUJETS sur lesquels les membres sont "
        "intervenus, jamais des positions du groupe (AGENTS.md §2 règle 8)"
    )


# ── La borne de la vue « grandes lois » ─────────────────────────────────────

def test_le_regroupement_par_texte_ne_pretend_pas_reconstruire_une_cle(regles, composant):
    """`AGENTS.md` §4 : un `dossier_id` ne se reconstruit jamais depuis un titre."""
    assert re.search(r"export function designationDuTexte\(", regles), (
        "`designationDuTexte` a disparu"
    )
    bloc = re.search(r"export function designationDuTexte\(intitule\) \{(.*?)\n\}", regles, flags=re.DOTALL)
    assert "return null" in bloc.group(1), (
        "un intitulé qui ne nomme aucun texte rend `null`, jamais une désignation inventée "
        "ni un repli sur l'intitulé entier — qui ferait un « texte » par scrutin "
        "(AGENTS.md §2 règle 5)"
    )
    assert "dossier_id" not in regles, (
        "la vue ne prétend pas porter la clé de dossier : `AGENTS.md` §4 interdit de la "
        "reconstruire depuis un titre"
    )
    assert "sansDesignation" in composant, (
        "la page publie sa borne : le nombre d'intitulés qui ne nomment aucun texte"
    )


def test_un_tiret_de_lecture_ne_se_lit_pas_comme_une_abstention(composant, feuille):
    assert "Un tiret n'est pas une abstention" in composant, (
        "une case vide signale une lecture où le quorum de CE groupe n'était pas atteint, "
        "et la page doit le dire — sans quoi elle se lit comme une abstention"
    )
    assert ".gp-case--absente" in feuille, (
        "la case sans position reste neutre : la colorer la ferait lire comme une position"
    )
