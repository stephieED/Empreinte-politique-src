"""Tests pour merge_profile.py (fusion additive des profils bruts et pivot)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from merge_profile import clean_stale_textes_portes, merge_lists_by_key, merge_pivot_profile, merge_raw_profile


def test_merge_lists_by_key_keeps_old_and_adds_new_only():
    old = [{"id": 1, "titre": "A"}, {"id": 2, "titre": "B"}]
    new = [{"id": 2, "titre": "B modifié"}, {"id": 3, "titre": "C"}]
    merged = merge_lists_by_key(old, new, key_fn=lambda x: x["id"])
    assert merged == [{"id": 1, "titre": "A"}, {"id": 2, "titre": "B"}, {"id": 3, "titre": "C"}]


def test_merge_lists_by_key_handles_empty_inputs():
    assert merge_lists_by_key(None, None, key_fn=lambda x: x["id"]) == []
    assert merge_lists_by_key([{"id": 1}], None, key_fn=lambda x: x["id"]) == [{"id": 1}]
    assert merge_lists_by_key(None, [{"id": 1}], key_fn=lambda x: x["id"]) == [{"id": 1}]


def test_merge_raw_profile_returns_new_when_no_existing_file():
    new = {"slug": "x", "votes": [{"numero_scrutin": "1", "date": "2024-01-01"}]}
    assert merge_raw_profile(None, new) is new


def test_merge_raw_profile_preserves_votes_lost_in_new_fetch():
    old = {
        "slug": "x",
        "chambre": "deputes",
        "identite": {"nom_complet": "X Y"},
        "mandats": [],
        "votes": [
            {"numero_scrutin": "100", "date": "2023-01-01", "titre": "Ancien vote", "position": "pour"},
        ],
        "votes_source": "open data Assemblée nationale (législature 15)",
        "synthese_activite": {"nom": "X Y"},
        "dossiers_legislatifs": [],
        "interventions": [
            {"id": 111, "url": "https://a.fr/1", "texte": "ancienne intervention"},
        ],
        "meta": {"warnings": []},
    }
    # Nouvelle collecte : l'API des votes/interventions a temporairement échoué.
    new = {
        "slug": "x",
        "chambre": "deputes",
        "identite": {"nom_complet": "X Y"},
        "mandats": [],
        "votes": [],
        "votes_source": None,
        "synthese_activite": None,
        "dossiers_legislatifs": [],
        "interventions": [],
        "meta": {"warnings": ["votes introuvables : ...", "identité introuvable : ..."]},
    }

    merged = merge_raw_profile(old, new)

    assert merged["votes"] == old["votes"]
    assert merged["interventions"] == old["interventions"]
    assert merged["votes_source"] == old["votes_source"]
    assert merged["synthese_activite"] == old["synthese_activite"]
    # Les avertissements devenus faux après restauration des données doivent disparaître.
    assert not any(w.startswith("votes introuvables") for w in merged["meta"]["warnings"])


def test_merge_raw_profile_adds_new_entries_without_dropping_old_ones():
    old = {
        "votes": [{"numero_scrutin": "1", "date": "2024-01-01"}],
        "interventions": [{"id": 1, "url": "u1"}],
        "mandats": [],
        "dossiers_legislatifs": [],
        "meta": {"warnings": []},
    }
    new = {
        "votes": [
            {"numero_scrutin": "1", "date": "2024-01-01"},
            {"numero_scrutin": "2", "date": "2024-02-01"},
        ],
        "interventions": [{"id": 1, "url": "u1"}, {"id": 2, "url": "u2"}],
        "mandats": [],
        "dossiers_legislatifs": [],
        "meta": {"warnings": []},
    }

    merged = merge_raw_profile(old, new)

    assert len(merged["votes"]) == 2
    assert len(merged["interventions"]) == 2


def test_merge_raw_profile_ecarte_dossiers_legislatifs_sans_role_connu():
    old = {
        "votes": [], "interventions": [], "mandats": [],
        "dossiers_legislatifs": [
            {"legislature": "16", "id": "2020-XYZ", "titre": "Dossier hérité (liste globale)", "date_max": "2020-02-01"},
        ],
        "meta": {"warnings": []},
    }
    new = {
        "votes": [], "interventions": [], "mandats": [],
        "dossiers_legislatifs": [
            {"legislature": "17", "id": "DLR5L17N1", "titre": "Dossier officiel", "role": "auteur", "type_rapport": None, "stade_procedural": "depose", "date_max": "2024-02-01"},
        ],
        "meta": {"warnings": []},
    }

    merged = merge_raw_profile(old, new)

    assert len(merged["dossiers_legislatifs"]) == 1
    assert merged["dossiers_legislatifs"][0]["titre"] == "Dossier officiel"


def test_merge_raw_profile_merges_mandat_europeen():
    old = {
        "votes": [], "interventions": [], "mandats": [], "dossiers_legislatifs": [],
        "meta": {"warnings": []},
        "mandat_europeen": {"mandats_europeens": [{"type": "MEMBER", "organisation_sigle": "AFET", "role": None, "debut": "2019-07-02"}]},
    }
    new = {
        "votes": [], "interventions": [], "mandats": [], "dossiers_legislatifs": [],
        "meta": {"warnings": []},
        "mandat_europeen": {"mandats_europeens": [{"type": "MEMBER", "organisation_sigle": "ENVI", "role": None, "debut": "2024-07-16"}]},
    }

    merged = merge_raw_profile(old, new)

    keys = {(m["organisation_sigle"]) for m in merged["mandat_europeen"]["mandats_europeens"]}
    assert keys == {"AFET", "ENVI"}


def test_merge_raw_profile_preserves_amendements_on_empty_new_fetch():
    # Un échec/vide transitoire de l'open data amendements ne doit pas effacer
    # des amendements déjà collectés lors d'une régénération précédente.
    old = {
        "votes": [], "interventions": [], "mandats": [], "dossiers_legislatifs": [],
        "meta": {"warnings": []},
        "amendements": [{"numero": "AS1", "texte_vise": "PRJL01", "date": "2024-01-10", "source_url": None}],
    }
    new = {
        "votes": [], "interventions": [], "mandats": [], "dossiers_legislatifs": [],
        "meta": {"warnings": []},
        "amendements": [],
    }

    merged = merge_raw_profile(old, new)

    assert merged["amendements"] == old["amendements"]


def test_merge_raw_profile_amendements_new_value_wins_on_collision():
    old = {
        "votes": [], "interventions": [], "mandats": [], "dossiers_legislatifs": [],
        "meta": {"warnings": []},
        "amendements": [{"numero": "AS1", "texte_vise": "PRJL01", "date": "2024-01-10", "source_url": None, "sort": "Adopté"}],
    }
    new = {
        "votes": [], "interventions": [], "mandats": [], "dossiers_legislatifs": [],
        "meta": {"warnings": []},
        "amendements": [
            {"numero": "AS1", "texte_vise": "PRJL01", "date": "2024-01-10", "source_url": None, "sort": "Rejeté"},
            {"numero": "AS2", "texte_vise": "PRJL01", "date": "2024-01-11", "source_url": None, "sort": "Adopté"},
        ],
    }

    merged = merge_raw_profile(old, new)

    assert len(merged["amendements"]) == 2
    as1 = next(a for a in merged["amendements"] if a["numero"] == "AS1")
    assert as1["sort"] == "Rejeté"


def test_merge_pivot_profile_preserves_data_and_dedups_sources():
    old = {
        "sources": [{"type": "nosdeputes", "url": "u", "synchro_le": "2026-01-01T00:00:00"}],
        "mandats": [{"label": "Commission X", "categorie": "commission", "fonction": "membre", "debut": "2022-01-01"}],
        "votes": [{"numero_scrutin": "1", "date": "2024-01-01", "texte": "T"}],
        "textes_portes": [],
        "interventions": [{"source_url": "https://a.fr/1", "date": "2023-01-01"}],
        "tags_thematiques": ["budget"],
        "meta": {"warnings": []},
    }
    new = {
        "sources": [{"type": "nosdeputes", "url": "u2", "synchro_le": "2026-02-01T00:00:00"}],
        "mandats": [],
        "votes": [],
        "textes_portes": [],
        "interventions": [],
        "tags_thematiques": ["fiscalité"],
        "meta": {"warnings": ["votes introuvables : ..."]},
    }

    merged = merge_pivot_profile(old, new)

    assert merged["votes"] == old["votes"]
    assert merged["mandats"] == old["mandats"]
    assert merged["interventions"] == old["interventions"]
    assert merged["sources"] == [{"type": "nosdeputes", "url": "u2", "synchro_le": "2026-02-01T00:00:00"}]
    assert merged["tags_thematiques"] == ["budget", "fiscalité"]
    assert not any(w.startswith("votes introuvables") for w in merged["meta"]["warnings"])


def test_merge_pivot_profile_dedups_textes_portes_sur_meme_dossier():
    # Deux entrées du même dossier (même source_url) avec un rôle factuel
    # connu des deux côtés : la nouvelle version l'emporte (pas de doublon).
    old = {
        "sources": [], "mandats": [], "votes": [],
        "textes_portes": [
            {"titre": "Texte X", "role": "rapporteur", "date_min": "2024-01-01", "date_max": "2024-02-01", "legislature": "16", "source_url": "https://a.fr/1"},
        ],
        "interventions": [], "tags_thematiques": [], "meta": {"warnings": []},
    }
    new = {
        "sources": [], "mandats": [], "votes": [],
        "textes_portes": [
            {"titre": "Texte X", "role": "co-rapporteur", "type_rapport": "rapporteur_avis", "stade_procedural": "adopte", "date_min": "2024-01-01", "date_max": "2024-02-01", "legislature": "16", "source_url": "https://a.fr/1"},
        ],
        "interventions": [], "tags_thematiques": [], "meta": {"warnings": []},
    }

    merged = merge_pivot_profile(old, new)

    assert len(merged["textes_portes"]) == 1
    assert merged["textes_portes"][0]["role"] == "co-rapporteur"


def test_merge_pivot_profile_ecarte_textes_portes_sans_role_connu():
    # Liste globale héritée de NosDéputés (mêmes dossiers pour tout le monde,
    # role toujours null) : doit être écartée lors de la fusion, même si elle
    # ne rentre pas en collision avec les nouvelles entrées officielles.
    old = {
        "sources": [], "mandats": [], "votes": [],
        "textes_portes": [
            {"titre": "Texte hérité (liste globale)", "role": None, "date_min": "2020-01-01", "date_max": "2020-02-01", "legislature": "16", "source_url": "https://www.nosdeputes.fr/16/dossier/texte-herite"},
        ],
        "interventions": [], "tags_thematiques": [], "meta": {"warnings": []},
    }
    new = {
        "sources": [], "mandats": [], "votes": [],
        "textes_portes": [
            {"titre": "Texte officiel", "role": "auteur", "type_rapport": None, "stade_procedural": "depose", "date_min": "2024-01-01", "date_max": "2024-02-01", "legislature": "17", "source_url": "https://www.assemblee-nationale.fr/dyn/17/dossiers/texte-officiel"},
        ],
        "interventions": [], "tags_thematiques": [], "meta": {"warnings": []},
    }

    merged = merge_pivot_profile(old, new)

    assert len(merged["textes_portes"]) == 1
    assert merged["textes_portes"][0]["titre"] == "Texte officiel"


def test_clean_stale_textes_portes_keeps_current_schema_entry():
    textes = [
        {"titre": "Texte Y", "role": "rapporteur", "date_min": "2024-01-01", "legislature": "16", "source_url": "https://a.fr/2"},
        {"titre": "Texte Y", "role": None, "type_rapport": None, "stade_procedural": None, "date_min": "2024-01-01", "legislature": "16", "source_url": "https://a.fr/2"},
    ]

    cleaned = clean_stale_textes_portes(textes)

    assert len(cleaned) == 1
    assert cleaned[0]["role"] is None
    assert "type_rapport" in cleaned[0]


def test_merge_pivot_profile_amendements_additifs_preserve_anciennes_entrees():
    # Un échec/vide transitoire de la source open data amendements ne doit pas
    # effacer des amendements déjà collectés lors d'une régénération précédente.
    old = {
        "sources": [], "mandats": [], "votes": [], "textes_portes": [],
        "amendements": [
            {"numero": "AS1", "texte_vise": "T1", "date": "2025-01-01", "sort": "adopté", "type_deposant": "depute"},
        ],
        "interventions": [], "tags_thematiques": [], "meta": {"warnings": []},
    }
    new = {
        "sources": [], "mandats": [], "votes": [], "textes_portes": [],
        "amendements": [],
        "interventions": [], "tags_thematiques": [], "meta": {"warnings": []},
    }

    merged = merge_pivot_profile(old, new)

    assert merged["amendements"] == old["amendements"]


def test_merge_pivot_profile_amendements_nouvelle_valeur_gagne_sur_collision():
    old = {
        "sources": [], "mandats": [], "votes": [], "textes_portes": [],
        "amendements": [
            {"numero": "AS1", "texte_vise": "T1", "date": "2025-01-01", "sort": "en attente", "type_deposant": "depute"},
        ],
        "interventions": [], "tags_thematiques": [], "meta": {"warnings": []},
    }
    new = {
        "sources": [], "mandats": [], "votes": [], "textes_portes": [],
        "amendements": [
            {"numero": "AS1", "texte_vise": "T1", "date": "2025-01-01", "sort": "adopté", "type_deposant": "depute"},
            {"numero": "AS2", "texte_vise": "T2", "date": "2025-02-01", "sort": "rejeté", "type_deposant": "depute"},
        ],
        "interventions": [], "tags_thematiques": [], "meta": {"warnings": []},
    }

    merged = merge_pivot_profile(old, new)

    assert len(merged["amendements"]) == 2
    as1 = next(a for a in merged["amendements"] if a["numero"] == "AS1")
    assert as1["sort"] == "adopté"


def test_prune_stale_warnings_removes_questions_warning_when_questions_present():
    """Le warning "questions indisponibles" doit être retiré après fusion si des
    questions (type_detail == "question") sont présentes dans les interventions."""
    from merge_profile import merge_raw_profile

    old = {
        "slug": "jean-dupont",
        "chambre": "deputes",
        "identite": {"nom_complet": "Jean Dupont"},
        "mandats": [],
        "votes": [],
        "votes_source": None,
        "synthese_activite": None,
        "dossiers_legislatifs": [],
        "amendements": [],
        "interventions": [
            {"id": "question_QANR5L17QE1", "type_detail": "question", "url": "https://..."},
        ],
        "meta": {"warnings": [], "synchro_sources": {}},
    }
    new = {
        "slug": "jean-dupont",
        "chambre": "deputes",
        "identite": {"nom_complet": "Jean Dupont"},
        "mandats": [],
        "votes": [],
        "votes_source": None,
        "synthese_activite": None,
        "dossiers_legislatifs": [],
        "amendements": [],
        "interventions": [],
        "meta": {
            "warnings": ["questions indisponibles : erreur réseau"],
            "synchro_sources": {"nosdeputes": None, "assemblee_nationale": None, "assemblee_nationale_questions": None},
        },
    }
    merged = merge_raw_profile(old, new)
    assert not any("questions indisponibles" in w for w in merged["meta"]["warnings"])


def test_prune_stale_warnings_keeps_questions_warning_when_no_questions():
    """Le warning "questions indisponibles" doit être conservé si aucune question
    n'est présente dans les interventions après fusion."""
    from merge_profile import merge_raw_profile

    old = {
        "slug": "jean-dupont",
        "chambre": "deputes",
        "identite": {"nom_complet": "Jean Dupont"},
        "mandats": [], "votes": [], "votes_source": None, "synthese_activite": None,
        "dossiers_legislatifs": [], "amendements": [], "interventions": [],
        "meta": {"warnings": [], "synchro_sources": {}},
    }
    new = {
        "slug": "jean-dupont",
        "chambre": "deputes",
        "identite": {"nom_complet": "Jean Dupont"},
        "mandats": [], "votes": [], "votes_source": None, "synthese_activite": None,
        "dossiers_legislatifs": [], "amendements": [], "interventions": [],
        "meta": {
            "warnings": ["questions indisponibles : erreur réseau"],
            "synchro_sources": {"nosdeputes": None, "assemblee_nationale": None, "assemblee_nationale_questions": None},
        },
    }
    merged = merge_raw_profile(old, new)
    assert any("questions indisponibles" in w for w in merged["meta"]["warnings"])


def test_merge_pivot_profile_intervention_enrichie_syceron_ancienne_entree_gagne():
    """Quand une intervention déjà présente dans le pivot est enrichie par Syceron
    (theme_officiel, seance, dossier, source renseignés), la stratégie additive
    (ancienne entrée gagne) doit préserver les champs Syceron en cas de refusion
    avec une version NosDéputés seule (champs Syceron absents/null).
    Pas de duplication : une seule entrée pour la même source_url."""
    source_url = "https://nosdeputes.fr/seance/2025-01-15#intervention-123"
    old_interv_enrichie = {
        "date": "2025-01-15",
        "type_detail": "intervention",
        "sujet": "Débat sur le budget",
        "texte": "Je prends la parole pour...",
        "source_url": source_url,
        "theme_officiel": "Finances publiques",
        "seance": {"ref": "PRJLANR5L17B1234", "session_ref": "17ord2024-2025"},
        "dossier": {"point_ordre_du_jour": "PLF 2025"},
        "source": {
            "type": "syceron",
            "url": "https://data.assemblee-nationale.fr/debats/17/2025-01-15.zip",
            "source_id": "syceron_123",
            "legislature": "17",
        },
    }
    old = {
        "sources": [], "mandats": [], "votes": [], "textes_portes": [],
        "amendements": [],
        "interventions": [old_interv_enrichie],
        "tags_thematiques": [], "meta": {"warnings": []},
    }
    # Nouvelle collecte sans Syceron (fallback NosDéputés) : même source_url,
    # champs Syceron absents.
    new_interv_nosdeputes = {
        "date": "2025-01-15",
        "type_detail": "intervention",
        "sujet": "Débat sur le budget",
        "texte": "Je prends la parole pour...",
        "source_url": source_url,
        "theme_officiel": None,
        "seance": None,
        "dossier": None,
        "source": None,
    }
    new = {
        "sources": [], "mandats": [], "votes": [], "textes_portes": [],
        "amendements": [],
        "interventions": [new_interv_nosdeputes],
        "tags_thematiques": [], "meta": {"warnings": []},
    }

    merged = merge_pivot_profile(old, new)

    # Pas de duplication : une seule intervention.
    assert len(merged["interventions"]) == 1
    interv = merged["interventions"][0]
    # L'ancienne entrée (enrichie Syceron) est préservée intégralement.
    assert interv["theme_officiel"] == "Finances publiques"
    assert interv["seance"] is not None
    assert interv["dossier"] is not None
    assert interv["source"] is not None
    assert interv["source"]["type"] == "syceron"


# ---------------------------------------------------------------------------
# merge_pivot_profile — politique de fusion provenance (#189)
# ---------------------------------------------------------------------------

def _base_pivot(meta_extra=None):
    return {
        "sources": [], "mandats": [], "votes": [], "textes_portes": [],
        "amendements": [], "interventions": [], "tags_thematiques": [],
        "meta": {"warnings": [], **(meta_extra or {})},
    }


def test_merge_pivot_profile_candidat_declare_non_degrade_par_run_roster():
    """Un profil déjà enrichi via candidats.json (provenance="candidat_declare",
    parti renseigné) régénéré par un run roster-driven du même slug (#188) ne doit
    jamais perdre son enrichissement éditorial : `parti` reste renseigné et
    `meta.provenance` reste "candidat_declare" (jamais rétrogradé)."""
    old = _base_pivot({"provenance": "candidat_declare"})
    old["parti"] = "La France Insoumise"

    new = _base_pivot({"provenance": "roster_groupe"})
    new["parti"] = None  # generate_roster_candidats.py ne renseigne jamais `parti`.

    merged = merge_pivot_profile(old, new)

    assert merged["parti"] == "La France Insoumise"
    assert merged["meta"]["provenance"] == "candidat_declare"


def test_merge_pivot_profile_candidat_declare_sans_provenance_existante_traite_comme_candidat_declare():
    """Rétro-compatibilité : un pivot existant écrit avant #189 (pas de
    meta.provenance) régénéré par un run roster-driven doit être traité comme
    s'il était "candidat_declare" (valeur par défaut), donc pas rétrogradé."""
    old = _base_pivot()  # pas de "provenance" dans meta
    old["parti"] = "Renaissance"

    new = _base_pivot({"provenance": "roster_groupe"})
    new["parti"] = None

    merged = merge_pivot_profile(old, new)

    assert merged["parti"] == "Renaissance"
    assert merged["meta"]["provenance"] == "candidat_declare"


def test_merge_pivot_profile_roster_groupe_sans_conflit_ecriture_normale():
    """Un profil "roster_groupe" régénéré par un nouveau run roster-driven (pas de
    profil candidat_declare préexistant pour ce slug) garde provenance="roster_groupe" :
    aucune règle de préservation ne s'applique."""
    old = _base_pivot({"provenance": "roster_groupe"})
    new = _base_pivot({"provenance": "roster_groupe"})

    merged = merge_pivot_profile(old, new)

    assert merged["meta"]["provenance"] == "roster_groupe"


def test_merge_pivot_profile_roster_groupe_regenere_par_candidat_declare_prend_le_dessus():
    """Cas inverse : un profil "roster_groupe" devient "candidat_declare" si le
    même slug est désormais suivi via candidats.json (pas de règle de préservation
    à l'envers — seul "candidat_declare" côté ancien profil est protégé)."""
    old = _base_pivot({"provenance": "roster_groupe"})
    new = _base_pivot({"provenance": "candidat_declare"})
    new["parti"] = "Horizons"

    merged = merge_pivot_profile(old, new)

    assert merged["meta"]["provenance"] == "candidat_declare"
    assert merged["parti"] == "Horizons"
