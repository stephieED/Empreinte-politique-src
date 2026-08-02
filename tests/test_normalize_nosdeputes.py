import sys
from pathlib import Path

# Translated comment.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from normalize_nosdeputes import normalize_nosdeputes
from schema_pivot import SCHEMA_VERSION, validate_profil


# ---------------------------------------------------------------------------
# Translated comment.
# ---------------------------------------------------------------------------

def _raw_depute(extra: dict = None) -> dict:
    """English docstring for  raw depute."""   base = {
        "slug": "jean-dupont",
        "chambre": "deputes",
        "source": "https://www.nosdeputes.fr/jean-dupont",
        "identite": {
            "nom_complet": "Jean Dupont",
            "groupe_sigle": "RE",
            "groupe_nom": "Renaissance",
            "profession": "Avocat",
            "date_naissance": "1970-01-01",
            "num_circo": 3,
            "nb_mandats": 2,
            "url_an_ou_senat": "https://www.assemblee-nationale.fr/dyn/deputes/PA123456",
        },
        "mandats": [
            {
                "categorie": "mandat_electif",
                "type": "mandat",
                "label": "Mandat parlementaire (Renaissance)",
                "debut": "2022-06-20",
                "fin": None,
                "actif": True,
            },
            {
                "categorie": "commission",
                "type": "membre",
                "label": "Commission des lois",
                "debut": "2022-07-01",
                "fin": None,
                "actif": True,
            },
        ],
        "votes": [
            {
                "date": "2023-11-10",
                "titre": "Projet de loi de finances 2024",
                "position": "pour",
                "numero_scrutin": 1234,
                "sort": "adopté",
            },
            {
                "date": "2022-10-05",
                "titre": "Motion de censure",
                "position": "contre",
                "numero_scrutin": 567,
                "sort": "rejeté",
            },
        ],
        "votes_source": "open data Assemblée nationale (data.assemblee-nationale.fr, législature 17)",
        "synthese_activite": {"nom": "Jean Dupont", "groupe_sigle": "RE"},
        "dossiers_legislatifs": [
            {
                "legislature": "17",
                "id": "2023-PLF",
                "titre": "Projet de loi de finances 2024",
                "date_min": "2023-09-01",
                "date_max": "2023-12-20",
                "url_source": "https://www.nosdeputes.fr/17/dossier/2023-PLF",
                "url_institution": "https://www.assemblee-nationale.fr/dyn/17/dossiers/2023-PLF",
            }
        ],
        "interventions": [
            {
                "type": "Intervention",
                "id": "42",
                "url": "https://www.nosdeputes.fr/seance/abc",
                "date": "2023-03-15",
                "created_at": "2023-03-15T14:30:00",
                "type_detail": "loi",
                "texte": "Je soutiens ce projet de loi.",
                "url_detail": "https://www.nosdeputes.fr/seance/abc#inter_42",
                "classification": {"mode": "prise_de_parole", "reason": "..."},
                "sujet": "Budget 2024",
                "mots_cles": ["budget", "fiscalité"],
                "fonction": "Rapporteur",
                "nb_mots": 48,
                "format": "prise_de_parole_developpee",
            }
        ],
        "meta": {
            "genere_le": "2026-07-29T10:00:00+0000",
            "licence_donnees": "ODbL (Regards Citoyens, ...)",
            "synchro_sources": {
                "nosdeputes": "2026-07-29T10:00:00+0000",
                "assemblee_nationale": "2026-07-29T10:00:00+0000",
            },
            "warnings": [],
        },
    }
    if extra:
        base.update(extra)
    return base


def _raw_senateur() -> dict:
    """English docstring for  raw senateur."""    p = _raw_depute()
    p["chambre"] = "senateurs"
    p["source"] = "https://archive.nossenateurs.fr/marie-martin"
    p["slug"] = "marie-martin"
    p["identite"]["nom_complet"] = "Marie Martin"
    return p


# ---------------------------------------------------------------------------
# Tests de structure de base
# ---------------------------------------------------------------------------

def test_pivot_valide_selon_schema():
    pivot = normalize_nosdeputes(_raw_depute())
    errors = validate_profil(pivot)
    assert errors == [], f"Erreurs de schéma inattendues : {errors}"


def test_pivot_schema_version():
    pivot = normalize_nosdeputes(_raw_depute())
    assert pivot["schema_version"] == SCHEMA_VERSION


def test_pivot_id_prefixe_nosdeputes():
    pivot = normalize_nosdeputes(_raw_depute())
    assert pivot["id"] == "nosdeputes:jean-dupont"


def test_pivot_id_prefixe_nossenateurs():
    pivot = normalize_nosdeputes(_raw_senateur())
    assert pivot["id"] == "nossenateurs:marie-martin"


def test_pivot_nom_depuis_identite():
    pivot = normalize_nosdeputes(_raw_depute())
    assert pivot["nom"] == "Jean Dupont"


def test_pivot_chambre_deputes_mappe_an():
    pivot = normalize_nosdeputes(_raw_depute())
    assert pivot["chambre"] == "AN"


def test_pivot_chambre_senateurs_mappe_senat():
    pivot = normalize_nosdeputes(_raw_senateur())
    assert pivot["chambre"] == "Senat"


def test_pivot_groupe_depuis_identite():
    pivot = normalize_nosdeputes(_raw_depute())
    assert pivot["groupe"] == "Renaissance"


def test_pivot_parti_optionnel():
    pivot = normalize_nosdeputes(_raw_depute(), parti="Renaissance")
    assert pivot["parti"] == "Renaissance"


def test_pivot_parti_absent_par_defaut():
    pivot = normalize_nosdeputes(_raw_depute())
    assert pivot["parti"] is None


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

def test_pivot_sources_contient_nosdeputes():
    pivot = normalize_nosdeputes(_raw_depute())
    types = [s["type"] for s in pivot["sources"]]
    assert "nosdeputes" in types


def test_pivot_sources_contient_assemblee_nationale_quand_votes_officiels():
    pivot = normalize_nosdeputes(_raw_depute())
    types = [s["type"] for s in pivot["sources"]]
    assert "assemblee_nationale" in types


def test_pivot_sources_pas_assemblee_nationale_si_votes_source_absent():
    raw = _raw_depute()
    raw["votes_source"] = None
    pivot = normalize_nosdeputes(raw)
    types = [s["type"] for s in pivot["sources"]]
    assert "assemblee_nationale" not in types


def test_pivot_source_synchro_le_propagee():
    pivot = normalize_nosdeputes(_raw_depute())
    nd_source = next(s for s in pivot["sources"] if s["type"] == "nosdeputes")
    assert nd_source["synchro_le"] == "2026-07-29T10:00:00+0000"


# ---------------------------------------------------------------------------
# Mandats
# ---------------------------------------------------------------------------

def test_pivot_mandats_count():
    pivot = normalize_nosdeputes(_raw_depute())
    assert len(pivot["mandats"]) == 2


def test_pivot_mandat_electif_champs():
    pivot = normalize_nosdeputes(_raw_depute())
    m = next(m for m in pivot["mandats"] if m["categorie"] == "mandat_electif")
    assert m["label"] == "Mandat parlementaire (Renaissance)"
    assert m["fonction"] == "mandat"
    assert m["debut"] == "2022-06-20"
    assert m["fin"] is None
    assert m["actif"] is True


def test_pivot_commission_champs():
    pivot = normalize_nosdeputes(_raw_depute())
    m = next(m for m in pivot["mandats"] if m["categorie"] == "commission")
    assert m["label"] == "Commission des lois"
    assert m["fonction"] == "membre"


# ---------------------------------------------------------------------------
# Votes
# ---------------------------------------------------------------------------

def test_pivot_votes_count():
    pivot = normalize_nosdeputes(_raw_depute())
    assert len(pivot["votes"]) == 2


def test_pivot_vote_champs():
    pivot = normalize_nosdeputes(_raw_depute())
    v = pivot["votes"][0]
    assert v["texte"] == "Projet de loi de finances 2024"
    assert v["position"] == "pour"
    assert v["date"] == "2023-11-10"
    assert v["numero_scrutin"] == "1234"
    assert v["sort"] == "adopté"


def test_pivot_vote_numero_scrutin_converti_en_str():
    pivot = normalize_nosdeputes(_raw_depute())
    for v in pivot["votes"]:
        if v.get("numero_scrutin") is not None:
            assert isinstance(v["numero_scrutin"], str)


def test_pivot_vote_preserve_type_et_lien_49_3():
    raw = _raw_depute()
    raw["votes"][0].update({
        "type_scrutin": "solennel",
        "type_vote": "motion_censure",
        "texte_lie_id": "texte-49-3-1",
    })
    vote = normalize_nosdeputes(raw)["votes"][0]
    assert vote["type_scrutin"] == "solennel"
    assert vote["type_vote"] == "motion_censure"
    assert vote["texte_lie_id"] == "texte-49-3-1"


# ---------------------------------------------------------------------------
# Translated comment.
# ---------------------------------------------------------------------------

def test_pivot_textes_portes_count():
    pivot = normalize_nosdeputes(_raw_depute())
    assert len(pivot["textes_portes"]) == 1


def test_pivot_texte_porte_champs():
    pivot = normalize_nosdeputes(_raw_depute())
    t = pivot["textes_portes"][0]
    assert t["titre"] == "Projet de loi de finances 2024"
    assert t["role"] is None
    assert t["legislature"] == "17"
    assert t["date_min"] == "2023-09-01"
    assert t["date_max"] == "2023-12-20"


def test_pivot_texte_porte_preserve_role_et_stade_factuels():
    raw = _raw_depute()
    raw["dossiers_legislatifs"][0].update({
        "role": "auteur",
        "type_rapport": None,
        "stade_procedural": "discute_seance",
    })
    texte = normalize_nosdeputes(raw)["textes_portes"][0]
    assert texte["role"] == "auteur"
    assert texte["stade_procedural"] == "discute_seance"


def test_pivot_texte_porte_source_url_prefere_url_source():
    pivot = normalize_nosdeputes(_raw_depute())
    t = pivot["textes_portes"][0]
    assert t["source_url"] == "https://www.nosdeputes.fr/17/dossier/2023-PLF"


# ---------------------------------------------------------------------------
# Interventions
# ---------------------------------------------------------------------------

def test_pivot_interventions_count():
    pivot = normalize_nosdeputes(_raw_depute())
    assert len(pivot["interventions"]) == 1


def test_pivot_intervention_champs():
    pivot = normalize_nosdeputes(_raw_depute())
    i = pivot["interventions"][0]
    assert i["date"] == "2023-03-15"
    assert i["type_detail"] == "loi"
    assert i["sujet"] == "Budget 2024"
    assert i["fonction"] == "Rapporteur"
    assert i["format"] == "prise_de_parole_developpee"
    assert "budget" in i["mots_cles"]
    assert i["source_url"] == "https://www.nosdeputes.fr/seance/abc#inter_42"


# ---------------------------------------------------------------------------
# Amendements
# ---------------------------------------------------------------------------

def test_pivot_amendements_vides_si_absent():
    pivot = normalize_nosdeputes(_raw_depute())
    assert pivot["amendements"] == []


def test_pivot_amendement_champs():
    raw = _raw_depute()
    raw["amendements"] = [
        {
            "texte_vise": "PIONANR5L17B0904",
            "sort": "adopté",
            "base_juridique_irrecevabilite": None,
            "co_signataires": ["an:PA842001"],
            "type_deposant": "depute",
            "date": "2025-02-17",
            "numero": "AS1",
            "source_url": None,
        }
    ]
    pivot = normalize_nosdeputes(raw)
    assert len(pivot["amendements"]) == 1
    a = pivot["amendements"][0]
    assert a["texte_vise"] == "PIONANR5L17B0904"
    assert a["sort"] == "adopté"
    assert a["premier_signataire"] == pivot["id"]
    assert a["co_signataires"] == ["an:PA842001"]
    assert a["type_deposant"] == "depute"
    assert a["numero"] == "AS1"


# ---------------------------------------------------------------------------
# Translated comment.
# ---------------------------------------------------------------------------

def test_pivot_tags_thematiques_agrege_mots_cles():
    pivot = normalize_nosdeputes(_raw_depute())
    assert "budget" in pivot["tags_thematiques"]
    assert "fiscalité" in pivot["tags_thematiques"]


def test_pivot_tags_thematiques_minuscules():
    raw = _raw_depute()
    raw["interventions"][0]["mots_cles"] = ["Budget", "FISCALITÉ"]
    pivot = normalize_nosdeputes(raw)
    assert "budget" in pivot["tags_thematiques"]
    assert "fiscalité" in pivot["tags_thematiques"]


def test_pivot_tags_thematiques_tries():
    pivot = normalize_nosdeputes(_raw_depute())
    assert pivot["tags_thematiques"] == sorted(pivot["tags_thematiques"])


def test_pivot_tags_thematiques_vide_si_pas_interventions():
    raw = _raw_depute()
    raw["interventions"] = []
    pivot = normalize_nosdeputes(raw)
    assert pivot["tags_thematiques"] == []


# ---------------------------------------------------------------------------
# Translated comment.
# ---------------------------------------------------------------------------

def test_pivot_meta_licence_propagee():
    pivot = normalize_nosdeputes(_raw_depute())
    assert "ODbL" in pivot["meta"]["licence_donnees"]


def test_pivot_meta_warnings_propagees():
    raw = _raw_depute()
    raw["meta"]["warnings"] = ["test warning"]
    pivot = normalize_nosdeputes(raw)
    assert "test warning" in pivot["meta"]["warnings"]


def test_pivot_meta_avertissement_si_synchro_nosdeputes_nulle():
    raw = _raw_depute()
    raw["meta"]["synchro_sources"]["nosdeputes"] = None
    pivot = normalize_nosdeputes(raw)
    assert any("synchro_sources" in w for w in pivot["meta"]["warnings"])


def test_pivot_meta_pas_avertissement_si_synchro_ok():
    pivot = normalize_nosdeputes(_raw_depute())
    synchro_warnings = [w for w in pivot["meta"]["warnings"] if "synchro_sources" in w]
    assert synchro_warnings == []


# ---------------------------------------------------------------------------
# Translated comment.
# ---------------------------------------------------------------------------

def test_pivot_profil_vide_ne_leve_pas():
    pivot = normalize_nosdeputes({})
    assert isinstance(pivot, dict)
    # Translated comment.
    # Translated comment.
    errors = validate_profil(pivot)
    assert all(isinstance(e, str) for e in errors)


def test_pivot_identite_nulle_utilise_slug_pour_nom():
    raw = {"slug": "jean-dupont", "chambre": "deputes", "meta": {}}
    pivot = normalize_nosdeputes(raw)
    assert pivot["nom"] == "Jean Dupont"


def test_pivot_mandats_vides_si_absent():
    raw = _raw_depute()
    raw["mandats"] = []
    pivot = normalize_nosdeputes(raw)
    assert pivot["mandats"] == []


def test_pivot_votes_vides_si_absent():
    raw = _raw_depute()
    raw["votes"] = []
    pivot = normalize_nosdeputes(raw)
    assert pivot["votes"] == []


def test_pivot_identite_reprend_profession_et_naissance():
    raw = _raw_depute()
    pivot = normalize_nosdeputes(raw)
    assert pivot["identite"]["profession"] == "Avocat"
    assert pivot["identite"]["date_naissance"] == "1970-01-01"
    assert pivot["identite"]["num_circo"] == 3
    assert pivot["identite"]["source_url"] == "https://www.assemblee-nationale.fr/dyn/deputes/PA123456"


def test_pivot_identite_inclut_enrichissement_an():
    raw = _raw_depute()
    raw["identite"]["lieu_naissance"] = "Nantes (Loire-Atlantique)"
    raw["identite"]["uri_hatvp"] = "https://www.hatvp.fr/pages_nominatives/x"
    pivot = normalize_nosdeputes(raw)
    assert pivot["identite"]["lieu_naissance"] == "Nantes (Loire-Atlantique)"
    assert pivot["identite"]["uri_hatvp"] == "https://www.hatvp.fr/pages_nominatives/x"


def test_pivot_identite_reste_none_si_aucun_champ_renseigne():
    raw = {
        "slug": "jean-dupont",
        "chambre": "deputes",
        "identite": {"nom_complet": "Jean Dupont", "groupe_nom": "Renaissance"},
        "meta": {},
    }
    pivot = normalize_nosdeputes(raw)
    assert pivot["identite"] is None


def test_normalize_intervention_question_includes_extra_fields():
    """English docstring for test normalize intervention question includes extra fields."""
    raw = _raw_depute()
    raw["interventions"] = [
        {
            "date": "2025-01-15",
            "type_detail": "question",
            "sous_type": "QE",
            "sujet": "Budget 2025",
            "texte": "Monsieur le ministre...",
            "reponse": "La réponse est...",
            "date_reponse": "2025-03-10",
            "ministere": "Ministère de l'Économie",
            "groupe_sigle": "LFI",
            "fonction": None,
            "format": "prise_de_parole_developpee",
            "mots_cles": [],
            "url": "https://questions.assemblee-nationale.fr/q17/QANR5L17QE1.htm",
            "url_detail": "https://questions.assemblee-nationale.fr/q17/QANR5L17QE1.htm",
        }
    ]
    pivot = normalize_nosdeputes(raw)

    assert len(pivot["interventions"]) == 1
    i = pivot["interventions"][0]
    assert i["type_detail"] == "question"
    assert i["sous_type"] == "QE"
    assert i["ministere"] == "Ministère de l'Économie"
    assert i["reponse"] == "La réponse est..."
    assert i["date_reponse"] == "2025-03-10"
    assert i["source_url"] == "https://questions.assemblee-nationale.fr/q17/QANR5L17QE1.htm"


def test_normalize_intervention_non_question_has_no_extra_fields():
    """English docstring for test normalize intervention non question has no extra fields."""   raw = _raw_depute()
    raw["interventions"] = [
        {
            "date": "2023-03-15",
            "type_detail": "loi",
            "sujet": "PLF 2024",
            "texte": "Je prends la parole...",
            "fonction": "Rapporteur",
            "format": "prise_de_parole_developpee",
            "mots_cles": ["budget"],
            "url_detail": "https://...",
        }
    ]
    pivot = normalize_nosdeputes(raw)

    assert len(pivot["interventions"]) == 1
    i = pivot["interventions"][0]
    assert "sous_type" not in i
    assert "ministere" not in i
    assert "reponse" not in i
    assert "date_reponse" not in i
