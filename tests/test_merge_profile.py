"""Tests pour merge_profile.py (fusion additive des profils bruts et pivot)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from merge_profile import merge_lists_by_key, merge_pivot_profile, merge_raw_profile


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
