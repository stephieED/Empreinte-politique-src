"""
tests/test_normalize_parltrack_dumps.py — Tests unitaires pour
normalize_parltrack_dumps.py.

Tests du mapping ParlTrack → schéma pivot v1 (textes_portes, amendements)
et de la fusion additive.
"""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from normalize_parltrack_dumps import (
    _make_amendement,
    _make_texte_porte,
    enrich_pivot_with_parltrack,
)
from schema_pivot import make_empty_profil, validate_profil


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _dossier(reference="2024/0001(COD)", titre="Titre test", comite="AFET", date="2024-03-15"):
    return {
        "reference": reference,
        "titre": titre,
        "comite": comite,
        "role": "rapporteur",
        "date": date,
        "source_url": f"https://parltrack.org/dossier/{reference}",
    }


def _amendment(amd_id="A9-0052/2023-1", reference="2020/2202(INI)", date="2023-05-10"):
    return {
        "id": amd_id,
        "reference": reference,
        "comite": None,
        "date": date,
        "source": "plenary",
        "source_url": f"https://parltrack.org/amendments/{amd_id}",
    }


def _empty_pivot():
    p = make_empty_profil("parltrack:131580", "Jordan Bardella")
    p["chambre"] = "PE"
    return p


# ---------------------------------------------------------------------------
# Tests : _make_texte_porte
# ---------------------------------------------------------------------------


def test_make_texte_porte_fields():
    d = _dossier()
    tp = _make_texte_porte(d)
    assert tp["role"] == "rapporteur"
    assert tp["titre"] == "Titre test"
    assert tp["date_min"] == "2024-03-15"
    assert tp["source_url"].startswith("https://parltrack.org/dossier/")
    assert "sort" not in tp  # sort n'appartient pas aux textes_portes
    # Champs obligatoires du schéma
    assert "stade_procedural" in tp
    assert "legislature" in tp
    assert "type_rapport" in tp


def test_make_texte_porte_missing_titre_falls_back_to_reference():
    d = _dossier(titre="", reference="2024/0042(COD)")
    tp = _make_texte_porte(d)
    assert tp["titre"] == "2024/0042(COD)"


# ---------------------------------------------------------------------------
# Tests : _make_amendement
# ---------------------------------------------------------------------------


def test_make_amendement_fields():
    """#431 : un amendement PE n'a pas d'`uid` AN, donc pas d'identifiant dans
    l'index partagé — il garde son enregistrement complet, jamais une clé
    inventée (AGENTS.md §2.5)."""
    a = _amendment()
    amd = _make_amendement(a)
    assert amd["amendement_id"] is None
    assert amd["role_signataire"] == "auteur_principal"
    non_resolu = amd["amendement_non_resolu"]
    assert non_resolu["texte_vise"] == "2020/2202(INI)"
    assert non_resolu["sort"] is None  # ParlTrack ne fournit pas de sort fiable
    assert non_resolu["numero"] == "A9-0052/2023-1"
    assert non_resolu["source_url"].startswith("https://parltrack.org/")
    assert non_resolu["co_signataires"] == []
    assert non_resolu["base_juridique_irrecevabilite"] is None


def test_make_amendement_missing_reference():
    a = _amendment(reference="")
    amd = _make_amendement(a)
    assert amd["amendement_non_resolu"]["texte_vise"] == ""


# ---------------------------------------------------------------------------
# Tests : enrich_pivot_with_parltrack
# ---------------------------------------------------------------------------


def test_enrich_adds_textes_portes(tmp_path):
    """Les textes portés sont ajoutés au profil pivot."""
    profil = _empty_pivot()
    dossiers = [_dossier("2024/0001(COD)", "Titre A"), _dossier("2024/0002(COD)", "Titre B")]
    amendments = []

    with patch("normalize_parltrack_dumps.get_dossiers_for_mep", return_value=dossiers), \
         patch("normalize_parltrack_dumps.get_amendments_for_mep", return_value=amendments):
        enrich_pivot_with_parltrack(profil, mep_id=131580)

    assert len(profil["textes_portes"]) == 2
    assert profil["textes_portes"][0]["role"] == "rapporteur"


def test_enrich_adds_amendements(tmp_path):
    """Les amendements sont ajoutés au profil pivot."""
    profil = _empty_pivot()
    dossiers = []
    amds = [_amendment("AMD-1"), _amendment("AMD-2"), _amendment("AMD-3")]

    with patch("normalize_parltrack_dumps.get_dossiers_for_mep", return_value=dossiers), \
         patch("normalize_parltrack_dumps.get_amendments_for_mep", return_value=amds):
        enrich_pivot_with_parltrack(profil, mep_id=131580)

    assert len(profil["amendements"]) == 3


def test_enrich_additive_no_duplicate(tmp_path):
    """La fusion additive ne duplique pas les entrées existantes."""
    profil = _empty_pivot()
    # Pré-charger un amendement existant
    profil["amendements"] = [{
        "texte_vise": "2020/2202(INI)",
        "sort": None,
        "base_juridique_irrecevabilite": None,
        "role_signataire": "auteur_principal",
        "premier_signataire": None,
        "co_signataires": [],
        "type_deposant": None,
        "date": "2023-05-10",
        "numero": "A9-0052/2023-1",
        "source_url": "https://parltrack.org/amendments/A9-0052/2023-1",
    }]

    amds = [_amendment("A9-0052/2023-1"), _amendment("A9-0053/2023-1")]  # 1er déjà présent

    with patch("normalize_parltrack_dumps.get_dossiers_for_mep", return_value=[]), \
         patch("normalize_parltrack_dumps.get_amendments_for_mep", return_value=amds):
        enrich_pivot_with_parltrack(profil, mep_id=131580)

    # Seul le nouvel amendement est ajouté. L'entrée pré-chargée est à l'ancienne
    # forme (champs à la racine), la nouvelle à la forme #431 : la clé de fusion
    # doit les rapprocher malgré tout, sinon une régénération dupliquerait tout
    # l'existant le jour de la bascule.
    assert len(profil["amendements"]) == 2

    def _numero(a):
        return (a.get("amendement_non_resolu") or a).get("numero")

    numeros = {_numero(a) for a in profil["amendements"]}
    assert "A9-0052/2023-1" in numeros
    assert "A9-0053/2023-1" in numeros


def test_enrich_schema_valid_after_enrichment():
    """Le profil pivot reste valide après enrichissement."""
    profil = _empty_pivot()
    profil["sources"] = [{"type": "parltrack", "url": "https://parltrack.org/mep/131580",
                           "synchro_le": "2026-07-24T00:00:00"}]
    dossiers = [_dossier()]
    amds = [_amendment()]

    with patch("normalize_parltrack_dumps.get_dossiers_for_mep", return_value=dossiers), \
         patch("normalize_parltrack_dumps.get_amendments_for_mep", return_value=amds):
        enrich_pivot_with_parltrack(profil, mep_id=131580)

    errors = validate_profil(profil)
    assert errors == [], f"Erreurs de validation schéma : {errors}"


def test_enrich_adds_warning_when_no_data():
    """Un warning est ajouté si aucun dossier ni amendement n'est trouvé."""
    profil = _empty_pivot()

    with patch("normalize_parltrack_dumps.get_dossiers_for_mep", return_value=[]), \
         patch("normalize_parltrack_dumps.get_amendments_for_mep", return_value=[]):
        enrich_pivot_with_parltrack(profil, mep_id=99999)

    warnings = profil["meta"]["warnings"]
    assert any("ParlTrack" in w for w in warnings)


def test_enrich_parltrack_source_added_once():
    """La source ParlTrack dumps n'est pas dupliquée si appelé deux fois."""
    profil = _empty_pivot()
    profil["sources"] = []
    dossiers = [_dossier()]
    amds = [_amendment()]

    with patch("normalize_parltrack_dumps.get_dossiers_for_mep", return_value=dossiers), \
         patch("normalize_parltrack_dumps.get_amendments_for_mep", return_value=amds):
        enrich_pivot_with_parltrack(profil, mep_id=131580)
        # Deuxième appel — les données sont déjà là (deduplication)
        enrich_pivot_with_parltrack(profil, mep_id=131580)

    dumps_sources = [s for s in profil["sources"] if "dumps" in (s.get("url") or "")]
    assert len(dumps_sources) == 1


def test_enrich_licence_enriched():
    """La licence ParlTrack est ajoutée à meta.licence_donnees."""
    profil = _empty_pivot()
    profil["meta"]["licence_donnees"] = "CC BY 4.0"
    dossiers = [_dossier()]

    with patch("normalize_parltrack_dumps.get_dossiers_for_mep", return_value=dossiers), \
         patch("normalize_parltrack_dumps.get_amendments_for_mep", return_value=[]):
        enrich_pivot_with_parltrack(profil, mep_id=131580)

    assert "ODbL" in profil["meta"]["licence_donnees"]
    assert "CC BY 4.0" in profil["meta"]["licence_donnees"]
