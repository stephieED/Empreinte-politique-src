#!/usr/bin/env python3
"""
schema_pivot.py — Schéma pivot v1 (format commun indépendant de la source).

Ce module définit le schéma pivot unique vers lequel toutes les sources sont
converties (NosDéputés/NosSénateurs, Parltrack, Wikidata). Il ne contient
aucune logique de collecte : c'est un contrat de structure.

Principe directeur : chaque fait doit remonter à sa source primaire.
Chaque section comporte soit une `source_url` soit des métadonnées de synchro
dans le bloc `sources[]`.

Format d'un profil pivot v1 :
{
    "schema_version": "1",
    "id": "nosdeputes:jean-luc-melenchon",  # <source>:<identifiant_source>
    "nom": "Jean-Luc Mélenchon",
    "chambre": "AN",                         # "AN" | "Senat" | "PE" | "mairie" | null
    "parti": null,                           # parti politique (depuis candidats.json si dispo)
    "groupe": "La France Insoumise",         # groupe parlementaire déclaré par la source
    "sources": [                             # traçabilité de chaque source utilisée
        {
            "type": "nosdeputes",            # "nosdeputes" | "nossenateurs" |
                                             # "parltrack" | "wikidata" |
                                             # "assemblee_nationale"
            "url": "https://...",            # URL canonique de la fiche source
            "synchro_le": "2026-07-29T..."   # ISO-8601 de la dernière synchro réussie
        }
    ],
    "mandats": [
        {
            "label": "Commission des affaires étrangères",
            "categorie": "commission",       # "mandat_electif" | "commission" |
                                             # "groupe_amitie" | "extra_parlementaire" | "autre"
            "fonction": "membre",            # ex. "membre", "président", "rapporteur"
            "debut": "2022-01-01",
            "fin": null,
            "actif": true,
            "source_url": null               # URL de la fiche source, si disponible
        }
    ],
    "votes": [
        {
            "date": "2024-06-12",
            "texte": "Projet de loi ...",    # titre du scrutin
            "position": "pour",              # "pour" | "contre" | "abstention" | "non_votant"
            "numero_scrutin": "1234",
            "sort": "adopté",                # résultat du scrutin : "adopté" | "rejeté" | ...
            "source_url": null               # URL de la source primaire du scrutin
        }
    ],
    "textes_portes": [                       # dossiers dont l'élu est auteur ou rapporteur
        {
            "titre": "Proposition de loi ...",
            "role": "rapporteur",            # "auteur" | "rapporteur" | "co-rapporteur"
            "date_min": "2022-01-01",
            "date_max": "2022-06-30",
            "legislature": "16",
            "source_url": null
        }
    ],
    "interventions": [
        {
            "date": "2023-03-15",
            "type_detail": "loi",            # "loi" | "question" | ...
            "sujet": "Budget 2024",
            "texte": "...",                  # extrait (180 premiers caractères)
            "fonction": "Rapporteur",        # rôle institutionnel au moment de l'intervention
            "format": "prise_de_parole_developpee",  # ou "reaction_courte"
            "mots_cles": ["budget", "fiscalité"],
            "source_url": "https://..."
        }
    ],
    "tags_thematiques": ["budget", "fiscalité"],  # bruts, avant harmonisation Phase 4
    "meta": {
        "schema_version": "1",
        "genere_le": "2026-07-29T...",
        "licence_donnees": "ODbL ...",
        "warnings": []
    }
}

Usage :
    from schema_pivot import SCHEMA_VERSION, make_empty_profil, validate_profil
"""

import time
from typing import Any

# Version du schéma ; à incrémenter si une rupture de compatibilité est introduite.
# Les consommateurs peuvent vérifier profil["schema_version"] == SCHEMA_VERSION.
SCHEMA_VERSION = "1"

# Clés obligatoires au niveau racine du profil pivot.
REQUIRED_TOP_LEVEL_KEYS: frozenset[str] = frozenset({
    "schema_version", "id", "nom", "chambre", "sources",
    "mandats", "votes", "textes_portes", "interventions",
    "tags_thematiques", "meta",
})

# Clés obligatoires dans le bloc "meta".
REQUIRED_META_KEYS: frozenset[str] = frozenset({
    "schema_version", "genere_le", "licence_donnees", "warnings",
})

# Champs dont la valeur doit être une liste.
_LIST_KEYS = ("votes", "mandats", "textes_portes", "interventions", "tags_thematiques", "sources")

# Types de sources reconnus (extensible, liste non-exhaustive).
KNOWN_SOURCE_TYPES: frozenset[str] = frozenset({
    "nosdeputes", "nossenateurs", "parltrack", "wikidata", "assemblee_nationale",
})

# Valeurs de chambre reconnues.
KNOWN_CHAMBRES: frozenset[str] = frozenset({"AN", "Senat", "PE", "mairie"})

# Positions de vote reconnues.
KNOWN_POSITIONS: frozenset[str] = frozenset({"pour", "contre", "abstention", "non_votant"})

# Catégories de mandats reconnues.
KNOWN_CATEGORIES: frozenset[str] = frozenset({
    "mandat_electif", "commission", "groupe_amitie", "extra_parlementaire", "autre",
})


def make_empty_profil(id_: str, nom: str) -> dict[str, Any]:
    """Crée un profil pivot v1 vide avec des valeurs par défaut.

    Args:
        id_: identifiant unique de la forme "<source>:<identifiant_source>",
             ex. "nosdeputes:jean-luc-melenchon", "parltrack:197451".
        nom: nom complet de l'élu.

    Returns:
        Profil pivot dict initialisé, prêt à être enrichi.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "id": id_,
        "nom": nom,
        "chambre": None,
        "parti": None,
        "groupe": None,
        "sources": [],
        "mandats": [],
        "votes": [],
        "textes_portes": [],
        "interventions": [],
        "tags_thematiques": [],
        "meta": {
            "schema_version": SCHEMA_VERSION,
            "genere_le": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "licence_donnees": "",
            "warnings": [],
        },
    }


def validate_profil(profil: dict[str, Any]) -> list[str]:
    """Vérifie les invariants de base du schéma pivot v1.

    Validation structurelle de premier niveau : présence des clés obligatoires,
    types, valeur de schema_version. Ne valide pas le contenu fin de chaque
    vote ou mandat (sauf pour les clés de liste).

    Args:
        profil: dict à valider.

    Returns:
        Liste d'erreurs (liste vide = profil valide).
    """
    errors: list[str] = []

    if not isinstance(profil, dict):
        return [f"Le profil doit être un dict, reçu : {type(profil).__name__}."]

    missing_top = REQUIRED_TOP_LEVEL_KEYS - set(profil.keys())
    if missing_top:
        errors.append(f"Clés manquantes au niveau racine : {sorted(missing_top)}.")

    version = profil.get("schema_version")
    if version != SCHEMA_VERSION:
        errors.append(
            f"schema_version inattendu : {version!r} (attendu : {SCHEMA_VERSION!r})."
        )

    if not profil.get("id"):
        errors.append("'id' est vide ou absent.")

    if not profil.get("nom"):
        errors.append("'nom' est vide ou absent.")

    chambre = profil.get("chambre")
    if chambre is not None and chambre not in KNOWN_CHAMBRES:
        errors.append(
            f"'chambre' non reconnue : {chambre!r}. Valeurs connues : {sorted(KNOWN_CHAMBRES)}."
        )

    for key in _LIST_KEYS:
        val = profil.get(key)
        if val is not None and not isinstance(val, list):
            errors.append(f"'{key}' doit être une liste, reçu : {type(val).__name__}.")

    meta = profil.get("meta")
    if not isinstance(meta, dict):
        errors.append("'meta' doit être un dict.")
    else:
        missing_meta = REQUIRED_META_KEYS - set(meta.keys())
        if missing_meta:
            errors.append(f"Clés manquantes dans 'meta' : {sorted(missing_meta)}.")
        if meta.get("schema_version") != SCHEMA_VERSION:
            errors.append(
                f"meta.schema_version inattendu : {meta.get('schema_version')!r} "
                f"(attendu : {SCHEMA_VERSION!r})."
            )
        if not isinstance(meta.get("warnings"), list):
            errors.append("'meta.warnings' doit être une liste.")

    return errors
