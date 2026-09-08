"""Le cadre de la page : en-tête repliable et sommaire de sections (#324).

L'en-tête restait collé en entier : marque plus trois barres de sélection, soit
**357 px sur tous les supports**. Mesuré le 08/09/2026 sur la fiche de Jérôme
Guedj, build de production — 45 % de la hauteur d'un écran 1 280 × 800, 42 %
d'un mobile 390 × 844. Ce qui est collé ne rend jamais sa place, et la fiche
fait 7 968 px sur ordinateur, 12 122 px sur mobile : neuf écrans parcourus avec
un demi-écran utile.

Ce que ces garde-fous protègent :

1. **Les barres ne se recollent pas.** C'est la moitié de la réforme qui vaut
   pour TOUT LE MONDE — 357 → 56 px, soit 301 px rendus sur les cinq supports,
   mobile compris.
2. **Le sommaire ne prend jamais sur le contenu.** Il occupe 204 px de marge
   au-delà de 1 440 px de fenêtre ; en dessous il n'existe pas, et le contenu
   garde exactement la largeur qu'il avait.
3. **Le seuil de 1 440 px est une mesure, pas un goût.** Statcounter France,
   août 2026 : il couvre 39 % du parc de bureau nommé, 21 % de toutes les
   visites. Un seuil à 1 600 px aurait exclu les écrans 1 600 × 900 eux-mêmes,
   dont la fenêtre fait 1 585 px.

CE QU'ILS NE COUVRENT PAS (§2 règle 5) : aucun composant React n'est rendu ici.
Le comportement — repli au défilement, rappel des listes, suivi de la section
lue, largeur du contenu — a été vérifié hors dépôt à 1920×1080, 1536×864,
1366×768 et 390×844, sans erreur console.

UN DÉFAUT QUE LA MESURE AVAIT MANQUÉ, et qui explique un de ces tests : la
première vérification lisait `element.hidden` et déclarait les barres masquées,
alors qu'elles restaient à l'écran — `display: flex` l'emporte sur le
`[hidden] { display: none }` de la feuille de l'agent utilisateur. Seule la
capture l'a montré. Vérifier un attribut n'est pas vérifier son effet.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
SRC = RACINE / "web" / "UI_finale" / "src"

LAYOUT = SRC / "components" / "ExplorerLayout.jsx"
LAYOUT_CSS = SRC / "components" / "ExplorerLayout.css"
SOMMAIRE = SRC / "components" / "SommaireSections.jsx"
SOMMAIRE_CSS = SRC / "components" / "SommaireSections.css"
FICHE = SRC / "components" / "CandidateProfile.jsx"

SEUIL_SOMMAIRE = "1440px"


def sans_commentaires(source: str) -> str:
    """Le code exécuté seul : les en-têtes CITENT les valeurs qu'ils proscrivent."""
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    return re.sub(r"(?<!:)//[^\n]*", "", source)


@pytest.fixture(scope="module")
def layout() -> str:
    return sans_commentaires(LAYOUT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def layout_css() -> str:
    return sans_commentaires(LAYOUT_CSS.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def sommaire() -> str:
    return sans_commentaires(SOMMAIRE.read_text(encoding="utf-8"))


# ── L'en-tête ne se recolle pas ─────────────────────────────────────────────


def test_les_barres_ne_sont_plus_collees(layout_css: str) -> None:
    """357 px collés sur tous les supports : c'est ce qui est corrigé.

    Seul le RAPPEL — les listes redemandées par le bouton — peut se coller, et
    sous la barre compacte.
    """
    bloc = layout_css.split(".explorer-bars {")[1].split("}")[0]
    assert "position: sticky" not in bloc, (
        "les barres défilent avec la page ; c'est tout l'objet du lot"
    )
    rappel = layout_css.split(".explorer-bars--rappel {")[1].split("}")[0]
    assert "position: sticky" in rappel and "top: 56px" in rappel


def test_l_attribut_hidden_a_sa_regle_css(layout_css: str) -> None:
    """`display: flex` l'emporte sur `[hidden]` de la feuille du navigateur.

    Sans cette règle, l'attribut est posé et les barres restent affichées — une
    mesure qui lit `element.hidden` le déclare pourtant corrigé.
    """
    assert ".explorer-bars[hidden]" in layout_css
    bloc = layout_css.split(".explorer-bars[hidden] {")[1].split("}")[0]
    assert "display: none" in bloc


def test_la_barre_compacte_fait_56_px(layout_css: str) -> None:
    bloc = layout_css.split(".explorer-compact {")[1].split("}")[0]
    assert "height: 56px" in bloc
    assert "position: sticky" in bloc and "top: 0" in bloc


def test_le_rappel_est_opaque(layout_css: str) -> None:
    """Un fond translucide laissait lire le contenu à travers les listes.

    Le flou d'arrière-plan est un raffinement qui ne survit pas partout ;
    l'opacité est un fait.
    """
    for bloc_nom in (".explorer-compact {", ".explorer-bars--rappel {"):
        bloc = layout_css.split(bloc_nom)[1].split("}")[0]
        fond = [l for l in bloc.splitlines() if l.strip().startswith("background")]
        assert fond, f"{bloc_nom} doit déclarer un fond"
        # `rgba` reste permis dans une ombre portée : c'est le FOND qui doit être
        # opaque, pas chaque couleur de la règle.
        assert all("rgba(" not in l for l in fond), f"{bloc_nom} doit être opaque"
        assert "background: var(--bg);" in bloc


# ── L'ordre des listes ──────────────────────────────────────────────────────


def test_l_ordre_est_candidats_groupes_gouvernements(layout: str) -> None:
    """Une fiche s'atteint par un NOM ; les deux autres listes sont du contexte."""
    ordre = [m for m in re.findall(r"<(CandidatesBar|GroupsBar|GovernmentsBar)\s*/>", layout)]
    assert ordre == ["CandidatesBar", "GroupsBar", "GovernmentsBar"], ordre


# ── Le sommaire ─────────────────────────────────────────────────────────────


def test_le_sommaire_n_apparait_qu_au_dessus_du_seuil() -> None:
    """1 440 px de FENÊTRE, mesure Statcounter France d'août 2026.

    Un seuil à 1 600 px aurait exclu les écrans 1 600 × 900, dont la fenêtre
    fait 1 585 px : quinze pixels sous la barre.
    """
    css = sans_commentaires(SOMMAIRE_CSS.read_text(encoding="utf-8"))
    assert ".som {\n  display: none;\n}" in css.replace("\r\n", "\n")
    assert f"@media (min-width: {SEUIL_SOMMAIRE})" in css


def test_le_sommaire_prend_sur_la_marge_jamais_sur_le_contenu(layout_css: str) -> None:
    """Hors seuil, la grille n'a qu'UNE colonne : le contenu garde sa largeur.

    Une grille à deux colonnes en permanence ferait glisser le contenu dans la
    colonne de 204 px dès que le sommaire est absent — c'est arrivé, et seule la
    mesure de la largeur rendue l'a montré.
    """
    bloc = layout_css.split(".explorer-corps {")[1].split("}")[0]
    assert "grid-template-columns: minmax(0, 1fr)" in bloc
    media = layout_css.split(f"@media (min-width: {SEUIL_SOMMAIRE})")[1].split("}")[0]
    assert "204px" in media


def test_le_sommaire_lit_la_page_et_l_observe(sommaire: str) -> None:
    """Il est monté AVANT la fiche, dont les données arrivent en réseau.

    Une lecture unique au montage ne trouve rien et le sommaire reste vide pour
    toujours. Il sert par ailleurs les trois types de fiche sans qu'aucune ait à
    le connaître.
    """
    assert "querySelectorAll('[data-section]')" in sommaire
    assert "MutationObserver" in sommaire
    assert "disconnect()" in sommaire, "l'observateur se débranche au démontage"


def test_le_nav_est_toujours_rendu(sommaire: str) -> None:
    """Le retirer du DOM faisait glisser le contenu dans sa colonne."""
    assert "return null" not in sommaire, (
        "le nav occupe la colonne de gauche même vide ; c'est son absence qui "
        "déplaçait le contenu"
    )


def test_les_sections_portent_une_ancre_stable() -> None:
    """L'ancre est dérivée du NUMÉRO, pas du titre.

    Un titre change avec la voix du texte (« ce qu'il » / « ce qu'elle ») ; un
    lien partagé ne doit pas.
    """
    fiche = sans_commentaires(FICHE.read_text(encoding="utf-8"))
    assert "id={`section-${numero}`}" in fiche
    assert "data-section={titre}" in fiche


def test_la_section_lue_est_la_derniere_franchie(sommaire: str) -> None:
    """Pas la plus visible : le lecteur descend, et ce qui compte est où il en
    est, pas ce qui occupe le plus de place à l'écran."""
    assert "getBoundingClientRect().top <= SEUIL_LECTURE" in sommaire


def test_l_ancre_prend_une_avance_sur_la_barre_collante(sommaire: str) -> None:
    """Sans elle, la barre compacte recouvre le titre qu'on vient de demander."""
    assert "AVANCE_ANCRE" in sommaire
