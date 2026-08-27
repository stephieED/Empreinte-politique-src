"""Garde-fou #530 (lot 6) : le corpus n'est PAS sous licence unique.

L'épic « une seule source AN » (#523) se termine sur une bascule de licence, et
la formule qui vient à l'esprit — *plus rien ne vient de NosDéputés, donc le
corpus est sous Licence Ouverte* — est fausse deux fois :

1. **ParlTrack reste sous ODbL v1.0**, partage à l'identique compris. C'est une
   source vivante du versant européen, que le retrait de Regards Citoyens ne
   concerne pas ;
2. **des champs publiés dérivent encore de NosDéputés / NosSénateurs** —
   475 profils sur 476 portent une entrée `sources[]` de ce type, et 511
   interventions publiées pointent encore vers `www.nosdeputes.fr`. La fusion
   additive les conserve : `_merge_pivot_sources` **unit** `sources[]` par
   `type`, elle ne la remplace pas.

Ce fichier verrouille les deux, sur le code comme sur les pages publiées.
Voir `docs/technical_decisions.md#licence-lot-6-530`.
"""

import re
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1]
SRC = RACINE / "src"
sys.path.insert(0, str(SRC))

from licences import (  # noqa: E402
    LICENCE_AN,
    LICENCE_EUROPARL,
    LICENCE_PARLTRACK,
    LICENCE_REGARDS_CITOYENS,
    SEPARATEUR,
    appliquer_licence_donnees,
    composer_licence_donnees,
    licences_du_profil,
)
from merge_profile import merge_pivot_profile  # noqa: E402
from normalize_profil import normalize_profil  # noqa: E402

ANCRE = "licence-lot-6-530"

PAGE_MENTIONS_LEGALES = RACINE / "web" / "UI_finale" / "src" / "pages" / "LegalNoticePage.jsx"
CONFIG_SOURCES = RACINE / "web" / "UI_finale" / "src" / "data" / "sources.config.js"


def _source(type_: str, url: str = "", synchro: str = "2026-08-27T10:00:00+0000") -> dict:
    return {"type": type_, "url": url, "synchro_le": synchro}


def _pivot(sources: list[dict], interventions: list[dict] | None = None) -> dict:
    return {
        "id": "x",
        "sources": sources,
        "interventions": interventions or [],
        "meta": {"schema_version": "1", "licence_donnees": "", "warnings": []},
    }


# ---------------------------------------------------------------------------
# Les libellés eux-mêmes
# ---------------------------------------------------------------------------

def test_la_licence_an_est_une_licence_ouverte_sans_partage_a_l_identique():
    assert "Licence Ouverte" in LICENCE_AN
    assert "data.assemblee-nationale.fr" in LICENCE_AN
    assert "ODbL" not in LICENCE_AN


@pytest.mark.parametrize("libelle", [LICENCE_REGARDS_CITOYENS, LICENCE_PARLTRACK])
def test_les_deux_licences_share_alike_restent_de_l_odbl(libelle):
    """Les rebaptiser « Licence Ouverte » serait annoncer une licence plus
    permissive que la réalité — le défaut exact que ce lot doit éviter."""
    assert "ODbL" in libelle


# ---------------------------------------------------------------------------
# La dérivation : ce qu'un profil doit annoncer
# ---------------------------------------------------------------------------

def test_un_profil_purement_an_n_annonce_que_la_licence_ouverte():
    """Le gain réel du lot : plus d'ODbL là où plus rien n'en vient."""
    licence = composer_licence_donnees(_pivot([_source("assemblee_nationale")]))
    assert licence == LICENCE_AN
    assert "ODbL" not in licence


def test_une_source_regards_citoyens_publiee_garde_son_attribution_odbl():
    """475 profils sur 476 sont dans ce cas (AGENTS.md §2 règle 2)."""
    licence = composer_licence_donnees(
        _pivot([_source("assemblee_nationale"), _source("nosdeputes")])
    )
    assert LICENCE_AN in licence
    assert LICENCE_REGARDS_CITOYENS in licence


def test_une_intervention_regards_citoyens_suffit_sans_entree_de_source():
    """511 interventions publiées portent un `source_url` nosdeputes.fr. Elles
    survivent à la fusion additive même si `sources[]` cessait de le dire."""
    profil = _pivot(
        [_source("assemblee_nationale")],
        interventions=[{"source_url": "https://www.nosdeputes.fr/marine-le-pen/interventions/42"}],
    )
    assert LICENCE_REGARDS_CITOYENS in composer_licence_donnees(profil)


def test_parltrack_conserve_son_partage_a_l_identique():
    """Le piège central du lot : le share-alike européen n'est pas concerné par
    le retrait de Regards Citoyens."""
    licence = composer_licence_donnees(_pivot([_source("europarl"), _source("parltrack")]))
    assert LICENCE_PARLTRACK in licence
    assert LICENCE_EUROPARL in licence


def test_un_profil_sans_source_n_invente_aucune_licence():
    """Une licence par défaut ferait passer pour attribué ce qui ne l'est pas ;
    `audit_pivot_dataset` doit pouvoir le compter comme manquant."""
    assert composer_licence_donnees(_pivot([])) == ""


def test_un_type_de_source_inconnu_n_ajoute_pas_de_clause():
    assert composer_licence_donnees(_pivot([_source("source_jamais_qualifiee")])) == ""


def test_l_ordre_est_stable_quel_que_soit_l_ordre_de_collecte():
    """Deux profils au même contenu doivent publier la même chaîne : sinon
    `audit_diff_profils` verrait bouger un scalaire que rien n'a fait bouger."""
    a = licences_du_profil(_pivot([_source("parltrack"), _source("nosdeputes"), _source("assemblee_nationale")]))
    b = licences_du_profil(_pivot([_source("assemblee_nationale"), _source("nosdeputes"), _source("parltrack")]))
    assert a == b == [LICENCE_AN, LICENCE_REGARDS_CITOYENS, LICENCE_PARLTRACK]


def test_appliquer_ecrit_dans_meta_et_renvoie_la_valeur():
    profil = _pivot([_source("assemblee_nationale")])
    assert appliquer_licence_donnees(profil) == LICENCE_AN
    assert profil["meta"]["licence_donnees"] == LICENCE_AN


def test_appliquer_ne_fabrique_pas_un_meta_absent():
    """Un document sans `meta` n'est pas un pivot valide : le lui inventer ici
    masquerait le défaut au lieu de le laisser à `validate_profil()`."""
    profil = {"sources": [_source("assemblee_nationale")]}
    assert appliquer_licence_donnees(profil) == ""
    assert "meta" not in profil


# ---------------------------------------------------------------------------
# Le champ est DÉRIVÉ : ni propagé du brut, ni figé par la fusion
# ---------------------------------------------------------------------------

def test_normalize_ne_propage_plus_la_licence_du_profil_brut():
    """Le profil brut portait une constante ODbL qui ne décrivait plus rien."""
    pivot = normalize_profil({
        "slug": "x",
        "chambre": "deputes",
        "meta": {"licence_donnees": "ODbL (Regards Citoyens, à partir de …)"},
    })
    assert pivot["meta"]["licence_donnees"] == LICENCE_AN


def test_la_fusion_recalcule_la_licence_sur_les_sources_reunies():
    """`_merge_pivot_sources` **unit** `sources[]` par type : une entrée
    `nosdeputes` déjà publiée survit à une collecte purement AN. Reprendre la
    licence du profil neuf publierait « Licence Ouverte » sur un profil qui
    porte encore une source ODbL."""
    ancien = _pivot([_source("nosdeputes", "https://www.nosdeputes.fr/x", "2026-01-01T00:00:00+0000")])
    ancien["meta"]["licence_donnees"] = LICENCE_REGARDS_CITOYENS
    nouveau = _pivot([_source("assemblee_nationale")])
    nouveau["meta"]["licence_donnees"] = LICENCE_AN

    fusionne = merge_pivot_profile(ancien, nouveau)

    assert {s["type"] for s in fusionne["sources"]} == {"nosdeputes", "assemblee_nationale"}
    assert fusionne["meta"]["licence_donnees"] == LICENCE_AN + SEPARATEUR + LICENCE_REGARDS_CITOYENS


def test_la_fusion_compose_aussi_quand_il_n_y_a_pas_d_ancien_profil():
    """Un premier pivot doit publier la même chaîne qu'un pivot régénéré au
    même contenu, sans quoi la valeur dépendrait de l'ordre des runs."""
    nouveau = _pivot([_source("assemblee_nationale"), _source("europarl")])
    nouveau["meta"]["licence_donnees"] = "valeur héritée à écraser"
    fusionne = merge_pivot_profile(None, nouveau)
    assert fusionne["meta"]["licence_donnees"] == LICENCE_AN + SEPARATEUR + LICENCE_EUROPARL


# ---------------------------------------------------------------------------
# Les pages publiées disent la même chose que le code
# ---------------------------------------------------------------------------

def _texte(chemin: Path) -> str:
    return chemin.read_text(encoding="utf-8")


def test_les_mentions_legales_nomment_encore_regards_citoyens():
    """L'attribution sort quand la donnée sort, pas avant (#528 §4)."""
    page = _texte(PAGE_MENTIONS_LEGALES)
    assert "NosDéputés.fr" in page and "NosSénateurs.fr" in page
    assert "Open Database License (ODbL) v1.0" in page


def test_les_mentions_legales_maintiennent_le_share_alike_de_parltrack():
    page = _texte(PAGE_MENTIONS_LEGALES)
    bloc = page[page.index("<h3>Parltrack</h3>"):page.index("<h3>Parlement européen</h3>")]
    assert "ODbL" in bloc
    assert "source active" in bloc


def test_les_mentions_legales_nannoncent_pas_un_corpus_sous_licence_unique():
    """Le seul énoncé que ce lot devait rendre impossible."""
    page = _texte(PAGE_MENTIONS_LEGALES)
    assert "n'est donc pas couvert par une licence unique" in page
    assert "ne rend donc pas" in page  # « … l'ensemble du corpus réutilisable sous simple attribution »


def test_la_config_des_sources_garde_regards_citoyens_en_odbl():
    """`sourcesConfig` alimente aussi le compteur « N sources publiques » de la
    landing page : l'entrée reste, avec son ODbL, parce que des champs publiés
    en dérivent encore."""
    config = _texte(CONFIG_SOURCES)
    bloc = config[config.index("id: 'nosdeputes-nossenateurs'"):config.index("id: 'assemblee-nationale-opendata'")]
    assert "ODbL v1.0" in bloc
    assert re.search(r"[Pp]lus collectée", bloc), "l'entrée doit dire qu'elle n'est plus collectée"
    assert "attribution" in bloc.lower()


def test_la_config_des_sources_designe_l_an_comme_seule_source_francaise():
    config = _texte(CONFIG_SOURCES)
    bloc = config[config.index("id: 'assemblee-nationale-opendata'"):config.index("id: 'parltrack'")]
    assert "Licence Ouverte / Open Licence (Etalab)" in bloc
    assert "Seule source française collectée" in bloc


def test_la_config_des_sources_garde_le_share_alike_parltrack():
    config = _texte(CONFIG_SOURCES)
    bloc = config[config.index("id: 'parltrack'"):config.index("id: 'parlement-europeen-opendata'")]
    assert "ODbL v1.0" in bloc
    assert "share-alike" in bloc
