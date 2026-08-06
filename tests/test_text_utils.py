#!/usr/bin/env python3
"""Tests unitaires pour text_utils.py (slugify, classify_keywords, STABLE_THEMES)."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from text_utils import STABLE_THEMES, classify_keywords, slugify


# ---------------------------------------------------------------------------
# slugify
# ---------------------------------------------------------------------------

def test_slugify_simple():
    assert slugify("Les Républicains") == "les-republicains"


def test_slugify_removes_accents():
    assert slugify("éàüî") == "eaui"


def test_slugify_numbers_preserved():
    assert slugify("LR-17") == "lr-17"


# ---------------------------------------------------------------------------
# STABLE_THEMES
# ---------------------------------------------------------------------------

def test_stable_themes_count():
    assert len(STABLE_THEMES) == 8


def test_stable_themes_contient_categories_attendues():
    for expected in ("budget", "sante", "education", "environnement",
                     "securite", "social", "international", "institutions"):
        assert expected in STABLE_THEMES


# ---------------------------------------------------------------------------
# classify_keywords
# ---------------------------------------------------------------------------

def test_classify_keywords_vide():
    assert classify_keywords([]) == []


def test_classify_keywords_none_in_list():
    # None ou chaîne vide ne doit pas lever d'exception
    assert classify_keywords(["", None]) == []  # type: ignore[list-item]


def test_classify_keywords_budget():
    assert "budget" in classify_keywords(["budget"])
    assert "budget" in classify_keywords(["fiscalité"])
    assert "budget" in classify_keywords(["impôts"])


def test_classify_keywords_sante():
    assert "sante" in classify_keywords(["santé"])
    assert "sante" in classify_keywords(["hôpital"])
    assert "sante" in classify_keywords(["médicaments"])


def test_classify_keywords_education():
    assert "education" in classify_keywords(["éducation"])
    assert "education" in classify_keywords(["enseignement"])
    assert "education" in classify_keywords(["université"])


def test_classify_keywords_environnement():
    assert "environnement" in classify_keywords(["écologie"])
    assert "environnement" in classify_keywords(["énergie"])
    assert "environnement" in classify_keywords(["climat"])


def test_classify_keywords_securite():
    assert "securite" in classify_keywords(["sécurité"])
    assert "securite" in classify_keywords(["justice"])
    assert "securite" in classify_keywords(["défense"])


def test_classify_keywords_social():
    assert "social" in classify_keywords(["emploi"])
    assert "social" in classify_keywords(["retraites"])
    assert "social" in classify_keywords(["logement"])


def test_classify_keywords_international():
    assert "international" in classify_keywords(["Europe"])
    assert "international" in classify_keywords(["immigration"])
    assert "international" in classify_keywords(["diplomatie"])


def test_classify_keywords_institutions():
    assert "institutions" in classify_keywords(["constitution"])
    assert "institutions" in classify_keywords(["élections"])
    assert "institutions" in classify_keywords(["collectivités"])


def test_classify_keywords_sujet_officiel():
    """Un sujet officiel de débat est classifié correctement."""
    assert "budget" in classify_keywords(["Projet de loi de finances pour 2025"])
    # PLFSS : "sécurité" dans le sujet → securite (classification par token)
    assert "securite" in classify_keywords(["Projet de loi de financement de la sécurité sociale"])


def test_classify_keywords_multi_themes():
    """Un sujet peut couvrir plusieurs thèmes."""
    themes = set(classify_keywords(["budget emploi retraites"]))
    assert "budget" in themes
    assert "social" in themes


def test_classify_keywords_tous_stables():
    """Chaque tag produit appartient à STABLE_THEMES."""
    themes = classify_keywords(["budget", "santé", "éducation", "environnement",
                                "sécurité", "emploi", "Europe", "constitution"])
    for t in themes:
        assert t in STABLE_THEMES, f"Tag inattendu : {t!r}"


def test_classify_keywords_trie():
    """Le résultat est trié."""
    themes = classify_keywords(["emploi", "budget", "constitution"])
    assert themes == sorted(themes)


def test_classify_keywords_deduplique():
    """Les mots-clés multiples menant au même thème ne sont comptés qu'une fois."""
    themes = classify_keywords(["budget", "fiscalité", "impôts", "PLF"])
    assert themes.count("budget") == 1


def test_classify_keywords_tokens_inconnus_ignores():
    """Les mots inconnus n'empêchent pas la classification et sont silencieusement ignorés."""
    themes = classify_keywords(["xyznotatheme", "budget"])
    assert themes == ["budget"]
