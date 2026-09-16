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


# ── La page /faq ────────────────────────────────────────────────────────────

APP = UI / "src" / "App.jsx"
PAGE_FAQ = UI / "src" / "pages" / "FaqPage.jsx"
PAGE_STATIQUE = UI / "src" / "components" / "StaticPage.jsx"
COUVERTURE = UI / "src" / "pages" / "CoveragePage.jsx"


def test_faq_mene_a_sa_page() -> None:
    nav = _sans_commentaires(NAV.read_text(encoding="utf-8"))
    assert "vers: '/faq'" in nav and "'/#faq'" not in nav
    assert '<Route path="/faq" element={<FaqPage />} />' in APP.read_text(encoding="utf-8")


def test_les_questions_ne_sont_ecrites_qu_une_fois() -> None:
    """La page lit les questions de l'accueil ; elle ne les recopie pas."""
    page = _sans_commentaires(PAGE_FAQ.read_text(encoding="utf-8"))
    assert "import { QUESTIONS } from '../components/landing/Faq';" in page
    assert "question:" not in page


def test_la_faq_est_un_accordeon_premiere_question_ouverte() -> None:
    """Forme B, retenue le 16/09/2026 entre trois maquettes."""
    page = _sans_commentaires(PAGE_FAQ.read_text(encoding="utf-8"))
    assert "<details" in page and "open={i === 0}" in page


def test_les_pages_statiques_portent_la_rangee_et_plus_le_fil_d_ariane() -> None:
    for page in (PAGE_STATIQUE, COUVERTURE):
        source = _sans_commentaires(page.read_text(encoding="utf-8"))
        assert "<EnTeteSite" in source, page.name
        assert "Retour à l'accueil" not in source, page.name


# ── La page /sources ────────────────────────────────────────────────────────

SCHEMA = UI / "src" / "data" / "schemaSources.js"
CONFIG = UI / "src" / "data" / "sources.config.js"


def test_sources_mene_a_sa_page() -> None:
    nav = _sans_commentaires(NAV.read_text(encoding="utf-8"))
    assert "vers: '/sources'" in nav and "'/couverture'" not in nav


def test_le_schema_et_les_cartes_nomment_les_memes_sources() -> None:
    """Une source dans les cartes sans place dans le schéma ferait mentir la
    figure ; l'inverse laisserait une source sans licence ni cadence."""
    schema = SCHEMA.read_text(encoding="utf-8")
    config = CONFIG.read_text(encoding="utf-8")
    renvois = set(re.findall(r"config: '([^']+)'", schema))
    cartes = set(re.findall(r"^    id: '([^']+)'", config, flags=re.M))
    assert renvois == cartes, (renvois ^ cartes)


def test_chaque_source_du_schema_ouvre_sa_page() -> None:
    """Demandé le 16/09/2026 : le pavé d'une source ouvre la source, dans un
    nouvel onglet."""
    schema = SCHEMA.read_text(encoding="utf-8")
    bloc = schema[schema.index("export const SOURCES_SCHEMA") : schema.index("export const DONNEES_SCHEMA")]
    ids = re.findall(r"\{ id: '([a-z]+)',", bloc)
    urls = re.findall(r"url: '(https://[^']+)'", bloc)
    assert len(urls) == len(ids) == 12
    composant = (UI / "src" / "components" / "SchemaSources.jsx").read_text(encoding="utf-8")
    assert 'target="_blank"' in composant and 'rel="noopener noreferrer"' in composant


def test_aucun_lien_ne_mene_encore_a_couverture() -> None:
    """La redirection sert les liens partagés ; le site, lui, pointe juste."""
    for chemin in (UI / "src").rglob("*.jsx"):
        if chemin.name == "App.jsx":
            continue
        source = chemin.read_text(encoding="utf-8")
        assert 'to="/couverture' not in source and "vers: '/couverture" not in source, chemin.name


def test_les_noeuds_portent_les_infos_et_les_cartes_quittent_sources() -> None:
    """Retenu le 16/09/2026 : infobulle à la souris, bande au doigt, choisies sur
    le pointeur et jamais sur la largeur. Les cartes repliées ne sont plus
    rendues sous le schéma."""
    composant = (UI / "src" / "components" / "SchemaSources.jsx").read_text(encoding="utf-8")
    assert "'(hover: hover) and (pointer: fine)'" in composant
    assert "ss-detail--bulle" in composant and "ss-detail--bande" in composant
    assert "import sourcesConfig from '../data/sources.config';" in composant
    page = (UI / "src" / "pages" / "CoveragePage.jsx").read_text(encoding="utf-8")
    assert "<SchemaSources />" in page and "CartesSources" not in page


def test_la_source_a_venir_ouvre_la_liste_et_ne_compte_pas() -> None:
    """Le Conseil constitutionnel, en tête et à venir, avant Wikipédia qu'il
    remplacera (16/09/2026). Ses dates sont celles de la loi, et l'accueil ne le
    compte pas parmi les sources publiques."""
    schema = SCHEMA.read_text(encoding="utf-8")
    bloc = schema[schema.index("export const SOURCES_SCHEMA") : schema.index("export const DONNEES_SCHEMA")]
    ids = re.findall(r"\{ id: '([a-z]+)',", bloc)
    assert ids[:2] == ["cc", "wp"]
    assert "statut: 'a-venir'" in bloc
    config = CONFIG.read_text(encoding="utf-8")
    entree = config[config.index("id: 'conseil-constitutionnel'") : config.index("id: 'nosdeputes-nossenateurs'")]
    assert "aVenir: true" in entree
    assert "12 mars 2027 à 18 h" in entree and "26 mars 2027" in entree and "loi du 6 novembre 1962" in entree
    accueil = (UI / "src" / "components" / "landing" / "HowItWorks.jsx").read_text(encoding="utf-8")
    assert "sourcesConfig.filter((s) => !s.aVenir).length" in accueil
