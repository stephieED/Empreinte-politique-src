"""« Les grands chiffres » — le bloc de tête de la fiche candidat (#328).

Ce que ce fichier verrouille est ce qui a coûté quinze allers-retours de
maquette, et que rien dans le code ne rappelle une fois écrit :

- le bloc est un **tableau de bord**, pas un résumé, et il est nommé pour ce
  qu'il est — « Coup d'œil » et « L'essentiel » ont été essayés et écartés ;
- **chaque colonne compte contre son propre total** : les additionner ou les
  comparer transformerait deux métiers en deux notes (§2 règle 1) ;
- **le texte explicatif est un aveu d'échec** : la ligne d'introduction a été
  réduite trois fois, jusqu'à cinq mots ;
- deux absences ne se confondent jamais — un **tiret** est un fait sur le
  métier (« un ministre ne dépose pas d'amendement »), une **liste vide** est
  un fait sur la collecte (§2 règle 5).

Les tests lisent le **code exécuté** (commentaires retirés) : une règle
énoncée en commentaire et absente du code passerait sinon au vert.

Ce qui n'est PAS couvert ici : la mise en page rendue, le responsive, le
contraste et le parcours clavier. Le rendu `react-dom/server` des 13 profils
publiés a été fait hors dépôt, et il ne remplace pas une relecture à l'écran.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
UI = RACINE / "web" / "UI_finale" / "src"

MODULE_REGLES = UI / "utils" / "profilCandidat.js"
COMPOSANT = UI / "components" / "CandidateProfile.jsx"
FEUILLE = UI / "components" / "CandidateProfile.css"
ADAPTATEUR = UI / "data" / "pivotAdapter.js"


def sans_commentaires(source: str) -> str:
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    return re.sub(r"(?<!:)//[^\n]*", "", source)


def sans_commentaires_css(source: str) -> str:
    return re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)


@pytest.fixture(scope="module")
def regles() -> str:
    return sans_commentaires(MODULE_REGLES.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def composant() -> str:
    return sans_commentaires(COMPOSANT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def feuille() -> str:
    return sans_commentaires_css(FEUILLE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def adaptateur() -> str:
    return sans_commentaires(ADAPTATEUR.read_text(encoding="utf-8"))


def _corps(source: str, debut: str, fin: str) -> str:
    i = source.index(debut)
    return source[i : source.index(fin, i)]


# ── Le nom, et la ligne qui l'accompagne ────────────────────────────────────


def test_le_bloc_s_appelle_les_grands_chiffres(composant):
    """Deux noms ont été essayés et écartés : « Coup d'œil » promettait de la
    rapidité et non du contenu, « L'essentiel » promettait une synthèse que le
    bloc ne délivre pas."""
    assert "Les grands chiffres" in composant
    assert "Coup d’œil" not in composant and "Coup d'œil" not in composant
    assert "L’essentiel" not in composant


def test_la_these_tient_en_une_ligne(composant):
    """Réduite trois fois. Le motif de chaque coupe est le même : si une phrase
    doit expliquer un chiffre, c'est la forme qui n'a pas fait son travail."""
    assert "Ce que cette personne a engagé." in composant
    bloc = _corps(composant, "cp-gc-these", "</summary>")
    assert bloc.count(".") <= 2, (
        "la thèse est une phrase, pas un paragraphe : le texte explicatif est "
        "un aveu d'échec"
    )


def test_ce_qui_se_replie_est_la_partie_dense_pas_la_frise(composant):
    """La frise est l'ossature : elle donne aux colonnes leur couleur et leur
    raison d'être. Replier le bloc entier cachait ce qui explique le reste —
    relevé en relecture d'écran le 02/09/2026. Le `<details>` n'enveloppe donc
    que les colonnes, et la frise reste dehors."""
    bloc = _corps(composant, "function GrandsChiffres(", "export default function")
    assert bloc.index('className="cp-gc-frise"') < bloc.index("<details"), (
        "la frise est AVANT le pli : elle ne se replie pas"
    )
    assert bloc.index("<details") < bloc.index('className={`cp-gc-duo'), (
        "ce sont les colonnes que le pli enveloppe"
    )


def test_la_these_est_la_poignee_et_precede_les_colonnes(composant):
    """« À déplacer avant À l'Assemblée » : la thèse introduit LES COLONNES, pas
    le parcours. Elle sert de `<summary>`, donc de poignée à ce qu'elle
    annonce."""
    bloc = _corps(composant, "function GrandsChiffres(", "export default function")
    assert '<summary className="cp-gc-these">' in bloc
    assert bloc.index("cp-gc-these") < bloc.index("cp-gc-tete-col"), (
        "la thèse se lit avant l'en-tête « À l'Assemblée »"
    )


def test_le_pli_porte_un_plus_visible(composant, feuille):
    """Un `<details>` sans marqueur ne dit pas qu'il s'ouvre. Le « + » est
    dessiné et non écrit — deux glyphes changeraient de chasse et feraient
    sauter la ligne."""
    bloc = _corps(composant, "function GrandsChiffres(", "export default function")
    assert 'className="cp-gc-plus"' in bloc
    assert ".cp-gc-plis[open] .cp-gc-plus::after" in feuille, (
        "la barre verticale disparaît à l'ouverture : « + » devient « − »"
    )
    assert ".cp-gc-these::-webkit-details-marker" in feuille, (
        "le triangle natif est retiré, sinon deux marqueurs cohabitent"
    )


def test_chaque_piste_etiquette_ce_que_son_nom_ne_dit_pas_deja(regles):
    """Trois pistes, trois clés. Étiqueter la piste du gouvernement par sa
    PÉRIODE remplaçait la seule information qu'elle portait — le poste — par une
    redite de l'axe qui court juste en dessous."""
    assert "[INSTITUTION_PARLEMENT]: 'periode'" in regles
    assert "[INSTITUTION_GOUVERNEMENT]: 'role'" in regles
    assert "[INSTITUTION_MISSION]: 'detail'" in regles
    bloc = _corps(regles, "export function pistesDuParcours(", "\nexport ")
    assert "etiquette: ETIQUETTE_PISTE[institution]" in bloc


def test_aucune_abreviation_n_est_fabriquee(composant):
    """La maquette portait « Sec. d'État, Éducation » et « Éduc. », écrites à la
    main : rien dans la donnée ne les dérive, et un libellé que NOUS écrivons
    n'est plus le libellé de la source (§2 règle 2). L'étiquette rend le champ
    tel quel, l'intitulé complet reste en infobulle."""
    bloc = _corps(composant, "function etiquetteDuSegment(", "\nfunction ")
    assert "return s.role;" in bloc
    for interdit in ("slice(0,", "substring(", "…", "...", "ABREG"):
        assert interdit not in bloc, (
            f"`{interdit}` tronquerait un libellé sourcé dans la vue"
        )


def test_la_periode_compacte_ne_calcule_rien(composant):
    """Une étiquette de 5 % de large ne peut pas porter « 18 juin 2017 → 16
    novembre 2018 ». La forme compacte rend les deux bornes telles qu'elles
    sont, à la granularité qui suffit — jamais une durée, jamais un arrondi."""
    bloc = _corps(composant, "function periodeCompacte(", "\nfunction ")
    for interdit in ("Math.", "Date(", "durée", "duree"):
        assert interdit not in bloc, (
            f"`{interdit}` calculerait une durée là où deux bornes suffisent"
        )


# ── L'appariement des colonnes ──────────────────────────────────────────────


def test_chaque_colonne_compte_contre_son_propre_total(regles):
    """« 580 situées » d'un côté, « 2 759 » de l'autre : le total du profil
    n'apparaît nulle part, et les deux colonnes ne se mélangent pas."""
    bloc = _corps(regles, "export function grandsChiffres(", "\nexport ")
    assert "cotes[cote]" in bloc, (
        "chaque cellule se calcule sur les interventions de SON côté, jamais "
        "sur la liste entière"
    )
    for interdit in ("cotes.parlement.length + ", "+ cotes.gouvernement.length"):
        assert interdit not in bloc, (
            "les deux colonnes ne s'additionnent jamais : ce sont deux métiers, "
            "pas deux parts d'un tout"
        )


def test_le_partage_des_interventions_est_date_jamais_global(regles):
    """`depuisLeBancDuGouvernement` rend une qualité pour TOUT le profil. Ici il
    faut savoir, prise de parole par prise de parole, de quel banc elle vient —
    et c'est la date d'appartenance qui le dit."""
    bloc = _corps(regles, "export function grandsChiffres(", "\nexport ")
    assert "const auBanc = (date) =>" in bloc
    assert "appartenances.some((a) => a.debut <= date && date <= (a.fin" in bloc
    assert "depuisLeBancDuGouvernement(" not in bloc, (
        "la qualité globale ne peut pas trancher un partage par date"
    )


def test_un_tiret_est_un_fait_sur_le_metier_pas_une_liste_vide(regles):
    """« Un ministre ne dépose pas d'amendement » n'est pas « la liste est
    vide » : confondre les deux ferait lire un trou de collecte là où il y a un
    fait institutionnel (§2 règle 5)."""
    bloc = _corps(regles, "export function grandsChiffres(", "\nexport ")
    assert "celluleAbsente('un ministre ne dépose pas d’amendement')" in bloc
    assert "celluleAbsente('un ministre ne siège pas en commission')" in bloc


def test_une_ligne_sans_aucun_chiffre_ne_s_affiche_pas(regles):
    """Cinq rangs vides ne décrivent pas une personne, ils décrivent le
    gabarit."""
    bloc = _corps(regles, "export function grandsChiffres(", "\nexport ")
    assert "const retenues = lignes.filter(" in bloc


def test_le_troisieme_cas_ne_rend_aucune_ligne(regles):
    """Trois des 13 candidats déclarés n'ont ni mandat parlementaire ni
    appartenance gouvernementale. Le bloc n'a rien à montrer, et il le dit
    plutôt que d'afficher cinq tirets : l'arbitrage sur le travail européen et
    municipal est ouvert, pas rendu."""
    bloc = _corps(regles, "export function grandsChiffres(", "\nexport ")
    assert "if (cas === CAS_RIEN_A_MONTRER)" in bloc
    assert "lignes: []" in bloc


# ── Ce que chaque chiffre porte ─────────────────────────────────────────────


def test_seuls_les_nombres_sont_en_gros(feuille):
    """« 24 / 67 mandats » — et quoi ? Chaque cellule nomme ce sur quoi elle
    porte, et l'objet reste à l'échelle des libellés : le mettre à celle du
    chiffre faisait lire le titre du texte comme la mesure."""
    i = feuille.index(".cp-gc-n {")
    grand = feuille[i : feuille.index("}", i)]
    petit = feuille[feuille.index(".cp-gc-n small {") : feuille.index("}", feuille.index(".cp-gc-n small {"))]
    assert "font-size: 24px" in grand
    assert "font-size: 13px" in petit


def test_la_concentration_ne_s_affirme_que_la_ou_elle_se_prouve(regles):
    """Une ligne « N d'entre eux sur X » n'apparaît que si ce texte porte plus
    que tous les autres RÉUNIS. Aucune constante arbitraire : c'est un fait, pas
    un seuil. Un percentile a été essayé et écarté — un P90 sélectionne toujours
    10 % des dossiers, donc il ne peut jamais se taire."""
    bloc = _corps(regles, "export function grandsChiffres(", "\nexport ")
    assert "tete.depots * 2 > totalAuteur" in bloc, (
        "le critère est « plus que tous les autres réunis », et il s'écrit sans "
        "constante"
    )
    assert not re.search(r"\b0\.(8|9)\b|percentile|P90", bloc), (
        "aucun seuil arbitraire ne décide qu'il y a une concentration"
    )


def test_les_roles_de_texte_sont_nommes_un_par_un(regles):
    """Être RAPPORTEUR d'une proposition n'est pas en être l'auteur : replier
    les rôles sur l'institution afficherait « 3 propositions de loi » pour 2
    propositions et 1 rapport."""
    bloc = _corps(regles, "export function grandsChiffres(", "\nexport ")
    assert "ROLES_PROPOSITION = ['auteur_proposition_de_loi', 'auteur_proposition_de_resolution']" in bloc
    assert "t.roleCle === 'initiateur_projet_de_loi'" in bloc


def test_le_seuil_de_publication_des_textes_se_dit(regles):
    """AGENTS.md §6 ne publie par défaut qu'un texte parvenu au moins en
    commission. Taire les autres ferait lire « 2 » comme « il n'en a déposé que
    2 » (§2 règle 5)."""
    bloc = _corps(regles, "export function grandsChiffres(", "\nexport ")
    assert "textes?.ecartes?.total" in bloc
    assert "parvenu au moins en commission" in bloc


# ── La frise : l'ossature ───────────────────────────────────────────────────


def test_la_frise_porte_une_piste_par_role(regles):
    """Le parcours n'est pas une section à part : c'est l'ossature du bloc. Chez
    un ancien ministre, cinq catégories décrivant le métier de député se
    remplissent de ce que son ministère a produit, et son travail parlementaire
    disparaît."""
    bloc = _corps(regles, "export function pistesDuParcours(", "\nexport ")
    assert "for (const institution of ORDRE_PISTES)" in bloc


def test_un_parlementaire_en_mission_a_sa_propre_piste(regles):
    """Ce sont des missions auprès d'un ministère, pas des appartenances : elles
    ne peuvent pas partager la piste du gouvernement."""
    assert "ORDRE_PISTES = [INSTITUTION_PARLEMENT, INSTITUTION_GOUVERNEMENT, INSTITUTION_MISSION]" in regles
    assert "[INSTITUTION_MISSION]: 'Parlementaire en mission'" in regles


def test_la_posture_est_un_motif_jamais_une_couleur(feuille):
    """La couleur code déjà le rôle. Cinq états, cinq motifs — et la couleur
    reste celle de la piste."""
    motifs = ["plein", "diagonales", "points", "rayures", "fines-rayures"]
    for m in motifs:
        assert f".cp-gc-seg--{m}" in feuille, f"le motif `{m}` n'est plus déclaré"


def test_les_deux_absences_de_posture_ne_se_confondent_pas(composant):
    """« Non déclarée par l'Assemblée » est une VALEUR publiée — c'est le cas des
    cinq groupes de la XVIIe législature — quand l'absence chez nous est un trou
    de collecte. Les confondre publierait un trou comme un fait (§2 règle 5)."""
    bloc = _corps(composant, "function LegendePostures(", "\nfunction ")
    assert "'non renseignée chez nous'" in bloc
    assert "libellePosition(p)" in bloc, (
        "la valeur publiée garde son libellé de source, jamais réécrit ici"
    )


def test_le_couple_de_couleurs_survit_au_daltonisme(feuille):
    """Bleu contre bronze. Le vert et le rouge sont pris par les positions de
    vote (`DESIGN_SYSTEM` §2), et ni le bleu ni le bronze ne se lit comme
    positif ou négatif : ce sont deux métiers, pas deux notes."""
    bloc = _corps(feuille, ".cp-gc {", "\n}")
    assert "--parl: #2e4a7d" in bloc
    assert "--gouv: #8a6512" in bloc


def test_le_bloc_a_ses_deux_themes(feuille):
    """Le lecteur a trois états — clair, sombre, et le défaut système qui ne
    marque rien. Une couleur définie seulement sous `[data-theme]` ne s'applique
    jamais dans l'état non marqué."""
    assert "@media (prefers-color-scheme: dark) {\n  :root:not([data-theme='light']) .cp-gc {" in feuille
    assert ":root[data-theme='dark'] .cp-gc {" in feuille


def test_les_colonnes_ont_une_gouttiere(feuille):
    """Zéro espacement entre deux colonnes appariées les fait lire comme une
    seule mesure coupée en deux."""
    bloc = _corps(feuille, ".cp-gc-duo {", "\n}")
    assert "column-gap:" in bloc


# ── L'adaptateur ────────────────────────────────────────────────────────────


def test_aucune_mesure_n_est_refaite_dans_l_adaptateur(adaptateur):
    """Le bloc reçoit les objets DÉJÀ calculés. Recalculer ici ferait porter à la
    fiche deux comptes du même fait, qui divergeraient au premier ajustement —
    c'est la duplication que #672 a fermée sur `isWholeTextVote`."""
    bloc = _corps(adaptateur, "grandsChiffres: grandsChiffres({", "}),")
    for passe in ("roles", "bornes", "mandats", "amendements", "textes", "interventions", "appartenances"):
        assert re.search(rf"^\s+{passe},$", bloc, re.M), f"`{passe}` n'est plus passé au bloc"
