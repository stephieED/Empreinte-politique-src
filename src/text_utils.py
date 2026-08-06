#!/usr/bin/env python3
"""
text_utils.py — Petits utilitaires de texte partagés entre les modules de génération.
"""

import re
import unicodedata
from typing import Iterable


def slugify(text: str) -> str:
    """Dérive un identifiant slug (ex. "les-republicains-lr") à partir d'un libellé."""
    decomposed = unicodedata.normalize("NFKD", text)
    ascii_only = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", ascii_only.lower())).strip("-")


# ---------------------------------------------------------------------------
# Classification thématique stable
# ---------------------------------------------------------------------------

#: Ensemble des 8 thèmes stables publiés dans tags_thematiques[].
STABLE_THEMES: frozenset[str] = frozenset({
    "budget",
    "sante",
    "education",
    "environnement",
    "securite",
    "social",
    "international",
    "institutions",
})

#: Correspondance token normalisé (sans accent, minuscule) → thème stable.
_KEYWORD_TO_THEME: dict[str, str] = {
    # budget / fiscalité / finances publiques
    "budget": "budget",
    "fiscal": "budget",
    "fiscalite": "budget",
    "impot": "budget",
    "impots": "budget",
    "taxe": "budget",
    "taxes": "budget",
    "taxation": "budget",
    "finance": "budget",
    "finances": "budget",
    "dette": "budget",
    "deficit": "budget",
    "plf": "budget",
    "plfss": "budget",
    "recette": "budget",
    "depense": "budget",
    "depenses": "budget",
    "subvention": "budget",
    "subventions": "budget",
    "dotation": "budget",
    "dotations": "budget",
    # sante
    "sante": "sante",
    "hopital": "sante",
    "hopitaux": "sante",
    "medical": "sante",
    "medicale": "sante",
    "medicaux": "sante",
    "medicament": "sante",
    "medicaments": "sante",
    "maladie": "sante",
    "maladies": "sante",
    "medecin": "sante",
    "medecins": "sante",
    "infirmier": "sante",
    "infirmiers": "sante",
    "pharmacie": "sante",
    "pharmacies": "sante",
    "soins": "sante",
    "assurance": "sante",
    "maladie": "sante",
    "pandemi": "sante",
    "epidemie": "sante",
    "handicap": "sante",
    # education
    "education": "education",
    "enseignement": "education",
    "ecole": "education",
    "ecoles": "education",
    "universite": "education",
    "universites": "education",
    "lycee": "education",
    "lycees": "education",
    "college": "education",
    "colleges": "education",
    "etudiant": "education",
    "etudiants": "education",
    "apprentissage": "education",
    "formation": "education",
    "professeur": "education",
    "professeurs": "education",
    "enseignant": "education",
    "enseignants": "education",
    "recherche": "education",
    # environnement / energie / climat
    "environnement": "environnement",
    "ecologie": "environnement",
    "ecologique": "environnement",
    "energie": "environnement",
    "energetique": "environnement",
    "energies": "environnement",
    "climat": "environnement",
    "climatique": "environnement",
    "transition": "environnement",
    "biodiversite": "environnement",
    "nucleaire": "environnement",
    "renouvelable": "environnement",
    "renouvelables": "environnement",
    "pollution": "environnement",
    "dechets": "environnement",
    "eau": "environnement",
    "foret": "environnement",
    "forets": "environnement",
    "agriculture": "environnement",
    "agricole": "environnement",
    # securite / justice / defense
    "securite": "securite",
    "police": "securite",
    "gendarmerie": "securite",
    "justice": "securite",
    "defense": "securite",
    "militaire": "securite",
    "militaires": "securite",
    "terrorisme": "securite",
    "terroriste": "securite",
    "crime": "securite",
    "criminalite": "securite",
    "prison": "securite",
    "prisons": "securite",
    "penitentiaire": "securite",
    "judiciaire": "securite",
    "tribunal": "securite",
    "tribunaux": "securite",
    "magistrat": "securite",
    "magistrats": "securite",
    "renseignement": "securite",
    "armee": "securite",
    "armees": "securite",
    # social / emploi / logement
    "social": "social",
    "emploi": "social",
    "chomage": "social",
    "retraite": "social",
    "retraites": "social",
    "logement": "social",
    "logements": "social",
    "pauvrete": "social",
    "famille": "social",
    "familles": "social",
    "enfance": "social",
    "enfant": "social",
    "enfants": "social",
    "vieillesse": "social",
    "senior": "social",
    "seniors": "social",
    "travail": "social",
    "salaire": "social",
    "salaires": "social",
    "syndicat": "social",
    "syndicats": "social",
    "precarite": "social",
    "solidarite": "social",
    "minima": "social",
    "rsa": "social",
    # international / europe / immigration
    "europe": "international",
    "europeen": "international",
    "europeenne": "international",
    "europeens": "international",
    "europeennes": "international",
    "international": "international",
    "internationale": "international",
    "immigration": "international",
    "migrant": "international",
    "migrants": "international",
    "asile": "international",
    "diplomatie": "international",
    "diplomatique": "international",
    "ukraine": "international",
    "otan": "international",
    "onu": "international",
    "traite": "international",
    "traites": "international",
    "frontiere": "international",
    "frontieres": "international",
    "etranger": "international",
    "etrangers": "international",
    # institutions / constitution / elections
    "constitution": "institutions",
    "constitutionnel": "institutions",
    "constitutionnelle": "institutions",
    "election": "institutions",
    "elections": "institutions",
    "electoral": "institutions",
    "electorale": "institutions",
    "collectivite": "institutions",
    "collectivites": "institutions",
    "democratie": "institutions",
    "referendum": "institutions",
    "parlement": "institutions",
    "parlementaire": "institutions",
    "senat": "institutions",
    "assemblee": "institutions",
    "decentralisation": "institutions",
    "commune": "institutions",
    "communes": "institutions",
    "departement": "institutions",
    "departements": "institutions",
    "region": "institutions",
    "regions": "institutions",
    "republique": "institutions",
}


def classify_keywords(texts: Iterable[str]) -> list[str]:
    """Classe une liste de textes (mots-clés ou sujets officiels) en thèmes stables.

    Chaque texte est découpé en tokens normalisés (minuscules, sans accent).
    Les tokens connus sont traduits en thème via ``_KEYWORD_TO_THEME``.
    Les tokens inconnus sont silencieusement ignorés.

    Args:
        texts: mots-clés bruts ou textes de sujets officiels de débat.

    Returns:
        Liste triée et dédupliquée de noms de thèmes issus de ``STABLE_THEMES``.
    """
    themes: set[str] = set()
    for text in texts:
        if not text or not isinstance(text, str):
            continue
        normalized = slugify(text)
        for token in re.split(r"[-\s]+", normalized):
            token = token.strip()
            if token:
                theme = _KEYWORD_TO_THEME.get(token)
                if theme:
                    themes.add(theme)
    return sorted(themes)
