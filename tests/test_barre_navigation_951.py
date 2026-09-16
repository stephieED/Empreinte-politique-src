"""La barre des pages du site sur l'explorateur, et le symbole mobile (#951).

Ce que ces garde-fous protègent :

1. **Les quatre pages, dans l'ordre retenu** le 16/09/2026 : Explorateur,
   Méthodologie, Sources, FAQ.
2. **Le jaune souligne, il ne colore jamais le texte** : 1,05:1 sur le fond
   clair (DESIGN_SYSTEM §2).
3. **Le symbole porte des traits d'encre.** Il a porté les traits blancs de la
   variante pour fond sombre, et le logo mobile ne montrait plus que le point
   jaune.

CE QU'ILS NE COUVRENT PAS : aucun composant n'est rendu ici. Le comportement —
défilement stable, bouton, panneau, menu — a été vérifié au navigateur à 1 440,
600 et 390 px de large le 16/09/2026.
"""

from __future__ import annotations

import re
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
UI = RACINE / "web" / "UI_finale"
NAV = UI / "src" / "components" / "NavigationSite.jsx"
NAV_CSS = UI / "src" / "components" / "NavigationSite.css"
SYMBOLE = UI / "public" / "brand" / "empreinte-symbol-light.svg"
ACCUEIL = UI / "src" / "pages" / "LandingPage.jsx"
EXPLORATEUR = UI / "src" / "components" / "ExplorerLayout.jsx"


def _sans_commentaires(source: str) -> str:
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    return re.sub(r"(?<!:)//[^\n]*", "", source)


def test_les_quatre_pages_dans_l_ordre() -> None:
    source = _sans_commentaires(NAV.read_text(encoding="utf-8"))
    libelles = re.findall(r"libelle: '([^']+)'", source)
    assert libelles == ["Explorateur", "Méthodologie", "Sources", "FAQ"]


def test_la_page_courante_est_annoncee() -> None:
    source = _sans_commentaires(NAV.read_text(encoding="utf-8"))
    assert "aria-current={courante ? 'page' : undefined}" in source


def test_le_jaune_souligne_sans_colorer_le_texte() -> None:
    css = _sans_commentaires(NAV_CSS.read_text(encoding="utf-8"))
    bloc = css.split(".nav-site-lien--courante {")[1].split("}")[0]
    assert "var(--accent)" in bloc and "box-shadow" in bloc
    couleur = [l for l in bloc.splitlines() if l.strip().startswith("color:")]
    assert couleur and all("accent" not in l for l in couleur)


def test_le_menu_masque_a_sa_regle_css() -> None:
    """`display: flex` l'emporte sur le `[hidden]` du navigateur (#324)."""
    css = _sans_commentaires(NAV_CSS.read_text(encoding="utf-8"))
    assert "display: none" in css.split(".nav-site-menu-liste[hidden] {")[1].split("}")[0]


def test_le_symbole_porte_des_traits_d_encre() -> None:
    svg = SYMBOLE.read_text(encoding="utf-8")
    traits = set(re.findall(r'stroke="(#[0-9a-fA-F]{6})"', svg))
    assert traits == {"#17141f"}, traits


def test_l_accueil_et_l_explorateur_portent_la_meme_rangee() -> None:
    """Une seule rangée, pour qu'elle ne diverge pas d'une page à l'autre."""
    for page in (ACCUEIL, EXPLORATEUR):
        source = _sans_commentaires(page.read_text(encoding="utf-8"))
        assert "<EnTeteSite" in source, page.name
        assert "<Brand />" not in source, f"{page.name} : le logo vient de la rangée"
