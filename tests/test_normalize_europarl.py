import sys
from pathlib import Path

# Les modules testés vivent dans src/, à côté du dossier tests/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from normalize_europarl import _extract_groupe, normalize_europarl
from schema_pivot import SCHEMA_VERSION, validate_profil


# ---------------------------------------------------------------------------
# Fixture : profil brut Open Data Portal Parlement européen minimal
# ---------------------------------------------------------------------------

def _raw_ue_profile(extra: dict = None) -> dict:
    """Retourne un profil brut europarl minimal pour les tests."""
    base = {
        "identifiant_pe": "1234",
        "nom_complet": "Jean Dupont",
        "url_source": "https://www.europarl.europa.eu/meps/fr/1234",
        "meta": {
            "genere_le": "2026-07-29T10:00:00+0000",
            "licence_donnees": "CC0",
        },
        "mandats_europeens": [
            {
                "type": "EU_POLITICAL_GROUP",
                "organisation_nom": "Rassemblement ID",
                "organisation_sigle": "ID",
                "role": "def/ep-roles/MEMBER",
                "role_label": "Membre",
                "debut": "2019-07-02",
                "fin": "2024-07-15",
                "actif": False,
            },
            {
                "type": "EU_POLITICAL_GROUP",
                "organisation_nom": "Patriotes pour l'Europe",
                "organisation_sigle": "PfE",
                "role": "def/ep-roles/MEMBER",
                "role_label": "Membre",
                "debut": "2024-07-16",
                "fin": None,
                "actif": True,
            },
            {
                "type": "EU_INSTITUTION",
                "organisation_nom": None,
                "organisation_sigle": "10e législature",
                "role": "def/ep-roles/MEMBER",
                "role_label": "Député européen",
                "debut": "2024-07-16",
                "fin": None,
                "actif": True,
            },
            {
                "type": "COMMITTEE_PARLIAMENTARY_STANDING",
                "organisation_nom": "Commission des affaires étrangères",
                "organisation_sigle": "AFET",
                "role": "def/ep-roles/MEMBER",
                "role_label": "Membre",
                "debut": "2024-09-01",
                "fin": None,
                "actif": True,
            },
        ],
    }
    if extra:
        base.update(extra)
    return base


# ---------------------------------------------------------------------------
# _extract_groupe
# ---------------------------------------------------------------------------

def test_extract_groupe_retourne_groupe_actif_en_priorite():
    mandats = _raw_ue_profile()["mandats_europeens"]
    assert _extract_groupe(mandats) == "Patriotes pour l'Europe"


def test_extract_groupe_retourne_groupe_inactif_si_aucun_actif():
    mandats = [
        {
            "type": "EU_POLITICAL_GROUP",
            "organisation_nom": "Ancien groupe",
            "organisation_sigle": "AG",
            "actif": False,
        }
    ]
    assert _extract_groupe(mandats) == "Ancien groupe"


def test_extract_groupe_retourne_none_si_aucun_groupe():
    mandats = [
        {
            "type": "EU_INSTITUTION",
            "organisation_nom": None,
            "organisation_sigle": "10e législature",
            "actif": True,
        }
    ]
    assert _extract_groupe(mandats) is None


def test_extract_groupe_utilise_sigle_si_nom_absent():
    mandats = [
        {
            "type": "EU_POLITICAL_GROUP",
            "organisation_nom": None,
            "organisation_sigle": "GUE",
            "actif": True,
        }
    ]
    assert _extract_groupe(mandats) == "GUE"


# ---------------------------------------------------------------------------
# Mapping _CATEGORIE_MAP via normalize_europarl
# ---------------------------------------------------------------------------

def test_categorie_map_eu_institution_mappe_mandat_electif():
    pivot = normalize_europarl(_raw_ue_profile())
    m = next(m for m in pivot["mandats"] if m["label"] == "10e législature")
    assert m["categorie"] == "mandat_electif"


def test_categorie_map_committee_standing_mappe_commission():
    pivot = normalize_europarl(_raw_ue_profile())
    m = next(m for m in pivot["mandats"] if m["label"] == "Commission des affaires étrangères")
    assert m["categorie"] == "commission"


def test_categorie_map_eu_political_group_mappe_autre():
    pivot = normalize_europarl(_raw_ue_profile())
    groupes = [m for m in pivot["mandats"] if "Patriotes" in m["label"] or "ID" in m["label"]]
    for m in groupes:
        assert m["categorie"] == "autre"


def test_categorie_map_type_inconnu_mappe_autre():
    raw = _raw_ue_profile()
    raw["mandats_europeens"] = [
        {
            "type": "TYPE_INCONNU",
            "organisation_nom": "Inconnu",
            "organisation_sigle": "INC",
            "role": "def/ep-roles/MEMBER",
            "role_label": "Membre",
            "debut": "2024-01-01",
            "fin": None,
            "actif": True,
        }
    ]
    pivot = normalize_europarl(raw)
    assert pivot["mandats"][0]["categorie"] == "autre"


# ---------------------------------------------------------------------------
# synchro_le / meta.genere_le
# ---------------------------------------------------------------------------

def test_synchro_le_propagee_depuis_meta():
    pivot = normalize_europarl(_raw_ue_profile())
    assert pivot["sources"][0]["synchro_le"] == "2026-07-29T10:00:00+0000"


def test_meta_genere_le_propagee_depuis_meta():
    pivot = normalize_europarl(_raw_ue_profile())
    assert pivot["meta"]["genere_le"] == "2026-07-29T10:00:00+0000"


# ---------------------------------------------------------------------------
# Structure générale
# ---------------------------------------------------------------------------

def test_pivot_valide_selon_schema():
    pivot = normalize_europarl(_raw_ue_profile())
    errors = validate_profil(pivot)
    assert errors == [], f"Erreurs de schéma inattendues : {errors}"


def test_pivot_schema_version():
    pivot = normalize_europarl(_raw_ue_profile())
    assert pivot["schema_version"] == SCHEMA_VERSION


def test_pivot_chambre_est_pe():
    pivot = normalize_europarl(_raw_ue_profile())
    assert pivot["chambre"] == "PE"


def test_pivot_id_est_le_slug_quand_il_est_fourni():
    # #487 : l'`id` pivot est le slug. `normalize_europarl` ne peut pas le
    # déduire de `ue_profile`, il lui est donc passé par le pipeline.
    pivot = normalize_europarl(_raw_ue_profile(), slug="jean-dupont")
    assert pivot["id"] == "jean-dupont"


def test_pivot_id_repli_sur_l_identifiant_de_source_sans_slug():
    # Sans slug, pas de slug inventé depuis `nom_complet` : ce serait dériver
    # l'identifiant d'une donnée de collecte, le défaut que #487 retire.
    pivot = normalize_europarl(_raw_ue_profile())
    assert pivot["id"] == "europarl:1234"


def test_pivot_nom():
    pivot = normalize_europarl(_raw_ue_profile())
    assert pivot["nom"] == "Jean Dupont"


def test_pivot_groupe_actif():
    pivot = normalize_europarl(_raw_ue_profile())
    assert pivot["groupe"] == "Patriotes pour l'Europe"


def test_pivot_parti_optionnel():
    pivot = normalize_europarl(_raw_ue_profile(), parti="Rassemblement National")
    assert pivot["parti"] == "Rassemblement National"


def test_pivot_parti_absent_par_defaut():
    pivot = normalize_europarl(_raw_ue_profile())
    assert pivot["parti"] is None


def test_pivot_provenance_defaut_candidat_declare():
    pivot = normalize_europarl(_raw_ue_profile())
    assert pivot["meta"]["provenance"] == "candidat_declare"


def test_pivot_provenance_roster_groupe_propagee():
    pivot = normalize_europarl(_raw_ue_profile(), provenance="roster_groupe")
    assert pivot["meta"]["provenance"] == "roster_groupe"


def test_pivot_source_type_europarl():
    pivot = normalize_europarl(_raw_ue_profile())
    assert pivot["sources"][0]["type"] == "europarl"


def test_pivot_meta_licence_propagee():
    pivot = normalize_europarl(_raw_ue_profile())
    assert pivot["meta"]["licence_donnees"] == "CC0"


def test_pivot_mandats_count():
    pivot = normalize_europarl(_raw_ue_profile())
    assert len(pivot["mandats"]) == 4


def test_pivot_profil_vide_ne_leve_pas():
    pivot = normalize_europarl({})
    assert isinstance(pivot, dict)
