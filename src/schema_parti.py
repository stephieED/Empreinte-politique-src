#!/usr/bin/env python3
"""
schema_parti.py — Schéma pivot du profil de parti / liste de candidats v1.

Distinct du profil de groupe parlementaire (schema_groupe.py) : un « parti »
au sens de ce schéma désigne le regroupement éditorial des candidats déclarés
à une élection partageant un même label de parti (raw_data/candidats.json), PAS
un groupe parlementaire réel (effectif officiel, cohésion de vote, amendements
déposés au nom du groupe).

Les candidats agrégés ici peuvent n'avoir aucun mandat commun (voire aucun
mandat du tout — un candidat non encore élu n'a pas de profil pivot). Il ne
contient donc :
  - AUCUNE cohésion de vote (`cohesion_votes` du schéma de groupe) : rien ne
    garantit que les candidats aient jamais siégé ensemble ni voté sur les
    mêmes scrutins.
  - AUCUN `amendements_agreges` : un taux d'adoption agrégé sur 1-2 personnes
    hétéroclites (candidats de chambres/mandats différents) n'est pas un
    comparateur valable.
  - AUCUN `effectif` façon groupe parlementaire : `meta.nb_candidats_declares`
    documente uniquement la taille de l'échantillon éditorial, jamais la
    taille réelle du parti ou de son groupe parlementaire.

Ce module ne contient aucune logique de collecte ni de calcul : c'est un
contrat de structure (constantes, fabrique, validateur). La construction est
dans parti_profile.py.

Principe directeur : faits chiffrés uniquement, aucune interprétation.

Format d'un profil de parti v1 :
{
    "schema_version": "1",
    "type_document": "profil_parti",
    "parti_id": "les-republicains-lr",       # slug dérivé du nom du parti
    "parti_nom": "Les Républicains (LR)",

    "candidats": [                            # un enregistrement par candidat déclaré
        {
            "candidat_id": "bruno-retailleau",   # id pivot = slug (#487) ; null si aucun pivot dispo
            "nom": "Bruno Retailleau",
            "statut": "declare",              # cf. raw_data/candidats.json._meta.statuts_possibles
            "famille_politique": "droite",
            "a_un_profil_pivot": true          # false si aucun mandat FR/UE connu (candidat non référencé)
        }
    ],

    "tags_thematiques_agreges": [             # calculé uniquement sur les candidats avec pivot
        {
            "tag": "budget",
            "nb_membres_porteurs": 1,
            "poids_relatif": 0.5
        }
    ],

    "sources": [                               # traçabilité des sources individuelles agrégées
        {
            "type": "nosdeputes",
            "url": "https://www.nosdeputes.fr/bruno-retailleau",
            "synchro_le": "2026-07-29T10:00:00+0000"
        }
    ],

    "meta": {
        "schema_version": "1",
        "genere_le": "2026-07-29T10:00:00+0000",
        "licence_donnees": "",
        "nb_candidats_declares": 2,
        "nb_candidats_avec_pivot": 2,
        "warnings": []
    }
}

Hors périmètre de ce schéma (volontairement, voir schema_groupe.py pour le
véritable objet « groupe parlementaire ») :
- Toute cohésion de vote, tout effectif de groupe, tout agrégat d'amendements.

Usage :
    from schema_parti import SCHEMA_PARTI_VERSION, make_empty_profil_parti, validate_profil_parti
"""

import time
from typing import Any

# Version du schéma de parti ; indépendante de SCHEMA_VERSION du pivot individuel
# et de SCHEMA_GROUPE_VERSION du profil de groupe parlementaire.
SCHEMA_PARTI_VERSION = "1"

# Clés obligatoires au niveau racine du profil de parti.
REQUIRED_TOP_LEVEL_KEYS: frozenset[str] = frozenset({
    "schema_version",
    "type_document",
    "parti_id",
    "parti_nom",
    "candidats",
    "tags_thematiques_agreges",
    "sources",
    "meta",
})

# Clés obligatoires dans le bloc "meta".
REQUIRED_META_KEYS: frozenset[str] = frozenset({
    "schema_version",
    "genere_le",
    "licence_donnees",
    "nb_candidats_declares",
    "nb_candidats_avec_pivot",
    "warnings",
})

# Clés obligatoires d'une entrée candidats[].
REQUIRED_CANDIDAT_KEYS: frozenset[str] = frozenset({
    "candidat_id",
    "nom",
    "statut",
    "famille_politique",
    "a_un_profil_pivot",
})

# Champs dont la valeur doit être une liste.
_LIST_KEYS: tuple[str, ...] = (
    "candidats",
    "tags_thematiques_agreges",
    "sources",
)


def make_empty_profil_parti(parti_id: str, parti_nom: str) -> dict[str, Any]:
    """Crée un profil de parti v1 vide avec des valeurs par défaut.

    Args:
        parti_id: identifiant slugifié du parti, ex. "les-republicains-lr".
        parti_nom: nom complet du parti, ex. "Les Républicains (LR)".

    Returns:
        Profil de parti dict initialisé, prêt à être enrichi par parti_profile.py.
    """
    return {
        "schema_version": SCHEMA_PARTI_VERSION,
        "type_document": "profil_parti",
        "parti_id": parti_id,
        "parti_nom": parti_nom,
        "candidats": [],
        "tags_thematiques_agreges": [],
        "sources": [],
        "meta": {
            "schema_version": SCHEMA_PARTI_VERSION,
            "genere_le": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "licence_donnees": "",
            "nb_candidats_declares": 0,
            "nb_candidats_avec_pivot": 0,
            "warnings": [],
        },
    }


def validate_profil_parti(profil: dict[str, Any]) -> list[str]:
    """Vérifie les invariants de base du schéma de parti v1.

    Validation structurelle de premier niveau : présence des clés obligatoires,
    types, valeur de schema_version et type_document, et invariants de chaque
    entrée candidats[].

    Args:
        profil: dict à valider.

    Returns:
        Liste d'erreurs (liste vide = profil valide).
    """
    errors: list[str] = []

    if not isinstance(profil, dict):
        return [f"Le profil de parti doit être un dict, reçu : {type(profil).__name__}."]

    missing = REQUIRED_TOP_LEVEL_KEYS - set(profil.keys())
    if missing:
        errors.append(f"Clés manquantes au niveau racine : {sorted(missing)}.")

    version = profil.get("schema_version")
    if version != SCHEMA_PARTI_VERSION:
        errors.append(
            f"schema_version inattendu : {version!r} (attendu : {SCHEMA_PARTI_VERSION!r})."
        )

    if profil.get("type_document") != "profil_parti":
        errors.append(
            f"'type_document' doit être 'profil_parti', reçu : {profil.get('type_document')!r}."
        )

    if not profil.get("parti_id"):
        errors.append("'parti_id' est vide ou absent.")

    if not profil.get("parti_nom"):
        errors.append("'parti_nom' est vide ou absent.")

    for key in _LIST_KEYS:
        val = profil.get(key)
        if val is not None and not isinstance(val, list):
            errors.append(f"'{key}' doit être une liste, reçu : {type(val).__name__}.")

    candidats = profil.get("candidats")
    if isinstance(candidats, list):
        for i, candidat in enumerate(candidats):
            if not isinstance(candidat, dict):
                errors.append(f"candidats[{i}] doit être un dict.")
                continue
            missing_candidat = REQUIRED_CANDIDAT_KEYS - set(candidat.keys())
            if missing_candidat:
                errors.append(f"candidats[{i}] : clés manquantes : {sorted(missing_candidat)}.")
            if "a_un_profil_pivot" in candidat and not isinstance(candidat["a_un_profil_pivot"], bool):
                errors.append(f"candidats[{i}].a_un_profil_pivot doit être un booléen.")

    meta = profil.get("meta")
    if not isinstance(meta, dict):
        errors.append("'meta' doit être un dict.")
    else:
        missing_meta = REQUIRED_META_KEYS - set(meta.keys())
        if missing_meta:
            errors.append(f"Clés manquantes dans 'meta' : {sorted(missing_meta)}.")
        if meta.get("schema_version") != SCHEMA_PARTI_VERSION:
            errors.append(
                f"meta.schema_version inattendu : {meta.get('schema_version')!r} "
                f"(attendu : {SCHEMA_PARTI_VERSION!r})."
            )
        if not isinstance(meta.get("warnings"), list):
            errors.append("'meta.warnings' doit être une liste.")

    return errors
