"""
test_integration_pipeline.py — Test d'intégration bout-en-bout du flux de
génération de profil pivot.

Valide le parcours complet :
  build_profile → (enrichissement EU) → normalize_nosdeputes / normalize_europarl
  → (enrichissement ParlTrack) → merge_pivot_profile → sortie pivot validée.

Deux scénarios :
  1. Avec source officielle AN (profil NosDéputés complet) et fallback ParlTrack.
  2. Avec source officielle AN + mandat EU + enrichissement ParlTrack simulé.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from merge_profile import merge_pivot_profile
from normalize_europarl import normalize_europarl
from normalize_nosdeputes import normalize_nosdeputes
from schema_pivot import validate_profil

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _raw_profile_fr() -> dict:
    """Profil brut NosDéputés simulé (sortie de build_profile())."""
    return {
        "slug": "marie-dupont",
        "chambre": "deputes",
        "source": "https://www.nosdeputes.fr/marie-dupont",
        "identite": {
            "nom_complet": "Marie Dupont",
            "groupe_sigle": "LFI",
            "groupe_nom": "La France Insoumise",
            "profession": "Enseignante",
            "date_naissance": "1975-05-20",
            "num_circo": 5,
            "nb_mandats": 1,
            "url_an_ou_senat": "https://www.assemblee-nationale.fr/dyn/deputes/PA987654",
        },
        "mandats": [
            {
                "categorie": "mandat_electif",
                "type": "mandat",
                "label": "Mandat parlementaire (La France Insoumise)",
                "debut": "2022-06-20",
                "fin": None,
                "actif": True,
            },
        ],
        "votes": [
            {
                "date": "2023-10-15",
                "titre": "Projet de loi de finances 2024",
                "position": "pour",
                "numero_scrutin": 2001,
                "sort": "adopté",
            },
        ],
        "votes_source": "open data Assemblée nationale (data.assemblee-nationale.fr, législature 17)",
        "synthese_activite": {"nom": "Marie Dupont", "groupe_sigle": "LFI"},
        "dossiers_legislatifs": [
            {
                "legislature": "17",
                "id": "2023-PLF2024",
                "titre": "Projet de loi de finances 2024",
                "date_min": "2023-09-01",
                "date_max": "2023-12-20",
                "url_source": "https://www.nosdeputes.fr/17/dossier/2023-PLF2024",
                "url_institution": "https://www.assemblee-nationale.fr/dyn/17/dossiers/2023-PLF2024",
                "role": "rapporteur",
            },
        ],
        "interventions": [
            {
                "type": "Intervention",
                "id": "99",
                "url": "https://www.nosdeputes.fr/seance/xyz",
                "date": "2023-03-10",
                "created_at": "2023-03-10T11:00:00",
                "type_detail": "loi",
                "texte": "Je défends ce projet.",
                "url_detail": "https://www.nosdeputes.fr/seance/xyz#inter_99",
                "classification": {"mode": "prise_de_parole", "reason": "speaker_match"},
                "sujet": "Projet de loi sur l'éducation",
                "mots_cles": ["éducation", "budget"],
                "fonction": "Rapporteure",
                "nb_mots": 12,
                "format": "prise_de_parole_developpee",
            },
        ],
        "meta": {
            "genere_le": "2026-08-01T08:00:00+0000",
            "licence_donnees": "ODbL (Regards Citoyens)",
            "synchro_sources": {
                "nosdeputes": "2026-08-01T08:00:00+0000",
            },
            "warnings": [],
        },
    }


def _raw_profile_ue() -> dict:
    """Profil brut Open Data Parlement européen simulé (sortie de build_profile_ue())."""
    return {
        "identifiant_pe": 12345,
        "nom_complet": "Marie Dupont",
        "url_source": "https://www.europarl.europa.eu/meps/fr/12345",
        "mandats_europeens": [
            {
                "type": "mandat_europeen",
                "organisation_nom": "Parlement européen",
                "organisation_sigle": "PE",
                "role_label": "Membre",
                "role": "membre",
                "debut": "2019-07-02",
                "fin": "2024-07-01",
                "actif": False,
            },
        ],
        "meta": {
            "genere_le": "2026-08-01T08:00:00+0000",
            "licence_donnees": "CC BY 4.0 (European Parliament Open Data Portal)",
        },
    }


# ---------------------------------------------------------------------------
# Scénario 1 : source officielle AN uniquement, fallback ParlTrack (cache absent)
# ---------------------------------------------------------------------------

def test_pipeline_source_officielle_an_sans_parltrack():
    """
    Flux complet avec un profil NosDéputés (source officielle AN).
    ParlTrack est indisponible (fallback) : aucun enrichissement ParlTrack,
    mais le pivot doit être complet et valide.
    """
    raw = _raw_profile_fr()

    # Étape 1 : normalisation → pivot
    pivot = normalize_nosdeputes(raw, parti="La France Insoumise")

    # Étape 2 : enrichissement ParlTrack simulé comme "absent" (fallback)
    with patch("generate_all_profiles._parltrack_cache_available", return_value=False):
        from generate_all_profiles import _enrich_pivot_with_parltrack_safe
        statut = _enrich_pivot_with_parltrack_safe(pivot, mep_id=12345)

    assert statut == "absent"
    # Warning fallback ajouté
    assert any("ParlTrack" in w for w in pivot["meta"]["warnings"])

    # Étape 3 : vérification des champs extraits
    assert pivot["id"].startswith("nosdeputes:")
    assert pivot["nom"] == "Marie Dupont"
    assert pivot["chambre"] == "AN"
    assert pivot["parti"] == "La France Insoumise"
    assert pivot["groupe"] == "La France Insoumise"

    # Mandats
    assert len(pivot["mandats"]) == 1
    assert pivot["mandats"][0]["categorie"] == "mandat_electif"

    # Votes
    assert len(pivot["votes"]) == 1
    v = pivot["votes"][0]
    assert v["date"] == "2023-10-15"
    assert v["position"] == "pour"
    assert v["numero_scrutin"] == "2001"

    # Textes portés
    assert len(pivot["textes_portes"]) == 1
    tp = pivot["textes_portes"][0]
    assert tp["titre"] == "Projet de loi de finances 2024"
    assert tp["role"] == "rapporteur"

    # Interventions
    assert len(pivot["interventions"]) == 1
    inter = pivot["interventions"][0]
    assert inter["type_detail"] == "loi"
    assert inter["source_url"] is not None

    # Identité
    assert pivot["identite"]["profession"] == "Enseignante"
    assert pivot["identite"]["date_naissance"] == "1975-05-20"

    # Validation schéma
    errors = validate_profil(pivot)
    assert errors == [], f"Erreurs de validation schéma : {errors}"


# ---------------------------------------------------------------------------
# Scénario 2 : source officielle AN + mandat UE + enrichissement ParlTrack simulé
# ---------------------------------------------------------------------------

def test_pipeline_source_officielle_an_avec_mandat_ue_et_parltrack():
    """
    Flux complet avec profil NosDéputés (AN) + mandat européen (PE) +
    enrichissement ParlTrack simulé (textes portés + amendements ajoutés).
    """
    raw_fr = _raw_profile_fr()
    raw_ue = _raw_profile_ue()

    # Étape 1 : normalisation AN → pivot FR
    pivot = normalize_nosdeputes(raw_fr, parti="La France Insoumise")

    # Étape 2 : normalisation UE → pivot PE, puis fusion dans le pivot FR
    ue_pivot = normalize_europarl(raw_ue, parti="La France Insoumise")
    pivot["sources"].extend(ue_pivot.get("sources") or [])
    pivot["mandats"].extend(ue_pivot.get("mandats") or [])

    # Étape 3 : enrichissement ParlTrack simulé (dump disponible, données ajoutées)
    texte_parltrack = {
        "titre": "Rapport sur le budget UE 2020",
        "role": "rapporteur",
        "legislature": None,
        "date_min": "2019-09-01",
        "date_max": "2019-11-30",
        "source_url": "https://parltrack.org/dossier/2019-budget-ue",
        "stade": "adopte",
    }
    amendement_parltrack = {
        "numero": "AM-1001",
        "texte_vise": "Rapport budget UE",
        "date": "2019-10-15",
        "sort": "adopte",
        "type_deposant": "commission_rapporteur",
        "source_url": "https://parltrack.org/amendement/AM-1001",
    }

    def _mock_enrich(profil, mep_id, force_download=False):
        profil.setdefault("textes_portes", []).append(texte_parltrack)
        profil.setdefault("amendements", []).append(amendement_parltrack)

    with patch("normalize_parltrack_dumps.enrich_pivot_with_parltrack", side_effect=_mock_enrich), \
         patch("generate_all_profiles._parltrack_cache_available", return_value=True):
        from generate_all_profiles import _enrich_pivot_with_parltrack_safe
        statut = _enrich_pivot_with_parltrack_safe(pivot, mep_id=12345)

    assert statut == "enrichi"

    # Étape 4 : fusion additive avec un pivot existant vide (idempotent si existant absent)
    pivot_merged = merge_pivot_profile(None, pivot)

    # Étape 5 : vérification des champs extraits

    # Sources : AN + PE
    source_types = {s["type"] for s in pivot_merged["sources"]}
    assert "nosdeputes" in source_types
    assert "europarl" in source_types

    # Mandats : AN + PE
    mandats_categories = [m["categorie"] for m in pivot_merged["mandats"]]
    assert "mandat_electif" in mandats_categories
    # Le mandat PE est mappé via _CATEGORIE_MAP de normalize_europarl
    assert len(pivot_merged["mandats"]) >= 2

    # Textes portés : AN (nosdeputes) + ParlTrack (UE)
    titres_tp = [tp["titre"] for tp in pivot_merged["textes_portes"]]
    assert "Projet de loi de finances 2024" in titres_tp
    assert "Rapport sur le budget UE 2020" in titres_tp

    # Amendements issus de ParlTrack
    assert len(pivot_merged["amendements"]) >= 1
    amd = pivot_merged["amendements"][0]
    assert amd["numero"] == "AM-1001"
    assert amd["sort"] == "adopte"

    # Votes
    assert len(pivot_merged["votes"]) == 1
    assert pivot_merged["votes"][0]["position"] == "pour"

    # Identité toujours présente
    assert pivot_merged["identite"]["profession"] == "Enseignante"

    # Validation schéma
    errors = validate_profil(pivot_merged)
    assert errors == [], f"Erreurs de validation schéma : {errors}"
