"""« Ce que contient ce corpus » — la page commune aux fiches (/couverture).

CE QU'ELLE RÈGLE. Les deux tiers de « ce qu'on n'a pas pu lire » étaient
recopiés à l'identique sur chaque fiche : les bornes de source, les périodes que
la source ne publie pas, les institutions dont nous ne montrons rien. Rien de
tout cela ne parle du candidat affiché. La page les dit UNE FOIS, pour les trois
populations publiées — candidats, gouvernements, groupes — et la fiche ne garde
que ce qui est vrai de cette personne-là.

CE QUE CES GARDE-FOUS PROTÈGENT est éditorial, pas graphique. Quatre pentes,
toutes tentantes pour une session qui « améliorerait » la figure :

1. **Dédoubler la frise par origine.** Trois fiches peuvent porter le même fait
   sur la même période. Elles vivent dans le MÊME rail, superposées, et la
   teinte dit d'où vient le trait. Une piste par origine mettrait trois lignes
   là où une suffit, et ferait lire trois faits là où il y en a un.
2. **Écrire un chiffre dans le JSX.** Effectifs, bornes, noms des fiches où une
   liste manque : tout est mesuré au build. Un chiffre recopié à la main est un
   chiffre qui aura vieilli au run suivant — la méthodologie en porte déjà
   (« 1 160 positions »), et c'est exactement ce qu'il ne faut pas reproduire.
3. **Séparer le parlementaire du gouvernemental sur un intitulé.** Chaque liste
   porte son marqueur, publié par la source : `categorie`, `role`, `fonction`.
   Aucun n'est reconstruit depuis un libellé (#639).
4. **Confondre les deux absences.** Une fiche dont la liste est vide parce que
   son mandat précède la borne n'est pas une fiche où la donnée manque sans
   cause connue. Deux colonnes, jamais un total (§2 règle 5).

CE QU'ILS NE COUVRENT PAS, et il faut le dire (§2 règle 5) : aucun composant
React n'est rendu ici, et AUCUN TEST NE LIT `pivot_data/` — la CI monte le dépôt
en sparse-checkout sans le corpus (AGENTS.md §3b). Le rendu en navigateur — repli
des champs, alignement de l'axe sur les rails, défilement horizontal du tableau —
a été vérifié hors dépôt sur le paquet construit, à 1 440, 1 100 et 700 px.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
UI = RACINE / "web" / "UI_finale"
SRC = UI / "src"
GENERATEUR = UI / "scripts" / "couverture-corpus.mjs"
SYNC = UI / "scripts" / "sync-data.mjs"
PAGE = SRC / "pages" / "CoveragePage.jsx"
FRISE = SRC / "components" / "FriseCouverture.jsx"
FRISE_CSS = SRC / "components" / "FriseCouverture.css"
APP = SRC / "App.jsx"


def _sans_commentaires(source: str) -> str:
    """Retire les commentaires : une règle citée en commentaire n'est pas une
    règle appliquée, et un test qui les lit se félicite d'une intention."""
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    return re.sub(r"^\s*//.*$", "", source, flags=re.MULTILINE)


@pytest.fixture(scope="module")
def generateur() -> str:
    return _sans_commentaires(GENERATEUR.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def frise() -> str:
    return _sans_commentaires(FRISE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def page() -> str:
    return _sans_commentaires(PAGE.read_text(encoding="utf-8"))


# ── Les fichiers existent, et sont branchés ─────────────────────────────────


def test_les_quatre_fichiers_de_la_page_existent() -> None:
    for chemin in (GENERATEUR, PAGE, FRISE, FRISE_CSS):
        assert chemin.exists(), f"{chemin.relative_to(RACINE)} manquant"


def test_la_route_existe_et_l_accueil_y_mene() -> None:
    """Une page qu'aucun lien n'atteint n'est pas publiée."""
    app = APP.read_text(encoding="utf-8")
    assert 'path="/couverture"' in app
    assert "CoveragePage" in app

    liens = "".join(
        (SRC / "pages" / "LandingPage.jsx").read_text(encoding="utf-8")
        + (SRC / "components" / "landing" / "SourcesFreshness.jsx").read_text(encoding="utf-8")
    )
    assert 'to="/couverture"' in liens, "l'accueil ne mène pas à la page"


def test_le_build_produit_la_couverture(generateur: str) -> None:
    """Le fichier est calculé par `sync-data`, pas versionné : `public/data/`
    est ignoré par git, et une projection commitée serait périmée au run
    suivant."""
    sync = SYNC.read_text(encoding="utf-8")
    assert "construireCouverture" in sync
    assert "couverture.json" in sync
    assert "export function construireCouverture" in generateur

    ignore = (RACINE / ".gitignore").read_text(encoding="utf-8")
    assert "web/UI_finale/public/data/" in ignore


# ── Règle 1 : une piste, des couches — jamais une piste par origine ─────────


def test_les_origines_se_superposent_dans_un_seul_rail(frise: str) -> None:
    """Un rail contient N couches ; il n'existe pas de rail par origine."""
    assert frise.count('className="fc-rail"') == 1, (
        "un seul point de construction du rail : le dupliquer par origine est "
        "exactement la pente que la figure refuse"
    )
    assert "couches.map" in frise
    feuille = FRISE_CSS.read_text(encoding="utf-8")
    assert "mix-blend-mode: multiply" in feuille, (
        "sans mélange, la couche du dessus masque celle du dessous et la "
        "superposition ne se voit plus"
    )
    assert "position: absolute" in feuille and "inset: 0" in feuille


def test_un_champ_donne_une_seule_ligne(generateur: str) -> None:
    """Deux origines qui mesurent la même chose tombent sur la même ligne : le
    champ porte ses `couches`, il n'est pas répété par origine."""
    assert "const champ = (titre, apports)" in generateur
    assert "couches: apports" in generateur


# ── Règle 2 : aucun chiffre n'est écrit à la main ───────────────────────────


CHIFFRE_ECRIT = re.compile(r"(?<![\w#-])\d{3,}(?![\w%])")


@pytest.mark.parametrize("fichier", ["CoveragePage.jsx", "FriseCouverture.jsx"])
def test_aucun_effectif_n_est_ecrit_dans_le_jsx(fichier: str) -> None:
    """Les seuls nombres tolérés sont des repères de mise en page (années de
    graduation, seuils), jamais un effectif du corpus."""
    chemin = PAGE if fichier == "CoveragePage.jsx" else FRISE
    source = _sans_commentaires(chemin.read_text(encoding="utf-8"))
    autorises = {"2000", "2005", "2010", "2015", "2020", "2025", "100", "640", "108", "262"}
    trouves = {m for m in CHIFFRE_ECRIT.findall(source) if m not in autorises}
    assert not trouves, (
        f"{fichier} porte des nombres écrits à la main : {sorted(trouves)} — "
        "tout effectif vient de couverture.json, mesuré au build"
    )


def test_les_reperes_de_tete_viennent_des_donnees(page: str) -> None:
    for cle in ("reperes.fichesPubliees", "reperes.candidats", "reperes.gouvernements", "reperes.groupes"):
        assert cle in page, f"{cle} n'est pas lu depuis les données"


# ── Règle 3 : la séparation est lue, jamais déduite d'un intitulé ───────────


def test_les_trois_marqueurs_sont_des_champs_publies(generateur: str) -> None:
    """Un mandat, un texte, une intervention : chacun porte le marqueur que la
    source publie. Aucun n'est reconstruit depuis un libellé (#639)."""
    assert "m?.categorie === 'fonction_gouvernementale'" in generateur
    assert "t?.role === 'initiateur_projet_de_loi'" in generateur
    assert "i.fonction" in generateur, "la qualité de l'orateur vient du compte rendu"


def test_le_senat_et_le_parlement_europeen_sortent_de_la_piste_assemblee(generateur: str) -> None:
    """Leur mandat est publié, leur activité n'est pas collectée (#528) : les
    ranger sous « Assemblée nationale » dirait une activité que nous n'avons
    pas."""
    assert "const HORS_ASSEMBLEE = new Set(['Senat', 'PE'])" in generateur
    assert "estMandatAssemblee" in generateur


# ── Règle 4 : deux absences, deux colonnes ──────────────────────────────────


def test_le_manquant_hors_borne_ne_se_confond_pas_avec_un_trou(page: str, generateur: str) -> None:
    assert "l.horsBorne" in page and "l.trous" in page, "les deux colonnes doivent exister"
    assert "horsBorne:" in generateur and "trous:" in generateur


def test_le_denominateur_est_le_nombre_de_fiches_qui_ont_siege(generateur: str, page: str) -> None:
    """Une fiche sans mandat à l'Assemblée n'a pas de vote à porter : sa liste
    vide est un fait sur elle, pas un trou. Le dénominateur l'exclut."""
    assert "siege: siegeants.length" in generateur
    assert "couverture.siege" in page


def test_la_borne_est_celle_que_la_source_declare(generateur: str) -> None:
    """Prendre le minimum des dates rencontrées rendrait la borne tautologique :
    la hachure s'arrêterait là où la première donnée commence, et ne dirait plus
    rien. Elle vient du bloc `couverture` du profil."""
    assert "function bornesPubliees" in generateur
    assert "e.etat !== 'couvert' && e.etat !== 'fait_etabli'" in generateur


# ── Ce que la fiche ne répète plus ──────────────────────────────────────────


def test_les_deux_mentions_de_fiche_renvoient_a_la_methodologie() -> None:
    """« Ce qu'il a voté » et « Ce qu'il a dit » gardent leurs chiffres — vrais
    de cette personne — et renvoient le pourquoi, identique sur les 30 fiches, à
    la méthodologie."""
    votes = (SRC / "components" / "VotesParPeriode.jsx").read_text(encoding="utf-8")
    paroles = (SRC / "components" / "ParolesParPeriode.jsx").read_text(encoding="utf-8")
    assert 'to="/methodologie#votes"' in votes
    assert 'to="/methodologie#interventions"' in paroles
    for source in (votes, paroles):
        assert "Ce que cette figure ne sait pas" in source, (
            "le chiffre reste sous la figure ; c'est le pourquoi qui déménage"
        )
