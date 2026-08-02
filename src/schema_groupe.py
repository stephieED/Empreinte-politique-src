#!/usr/bin/env python3
"""Module documentation in English."""

import time
from typing import Any

from schema_pivot import KNOWN_CHAMBRES, KNOWN_TYPES_DEPOSANT

# Translated comment.
SCHEMA_GROUPE_VERSION = "1"

# Translated comment.
REQUIRED_TOP_LEVEL_KEYS: frozenset[str] = frozenset({
    "schema_version",
    "type_document",
    "groupe_id",
    "groupe_sigle",
    "groupe_nom",
    "chambre",
    "legislature",
    "periode",
    "historique_noms",
    "membres",
    "effectif",
    "cohesion_votes",
    "tags_thematiques_agreges",
    "amendements_agreges",
    "sources",
    "meta",
})

# Translated comment.
REQUIRED_META_KEYS: frozenset[str] = frozenset({
    "schema_version",
    "genere_le",
    "licence_donnees",
    "profils_sources",
    "warnings",
})

# Translated comment.
_LIST_KEYS: tuple[str, ...] = (
    "historique_noms",
    "membres",
    "cohesion_votes",
    "tags_thematiques_agreges",
    "sources",
)

# Translated comment.
# Translated comment.
# Translated comment.
AMENDEMENTS_TYPES_DEPOSANT: tuple[str, ...] = (*sorted(KNOWN_TYPES_DEPOSANT), "inconnu")


def make_empty_amendements_stats() -> dict[str, Any]:
    """English docstring for make empty amendements stats."""
    return {
        "nb_amendements": 0,
        "nb_adoptes": 0,
        "nb_rejetes": 0,
        "nb_irrecevables": 0,
        "nb_retires_ou_tombes": 0,
        "taux_adoption": None,
    }


def make_empty_profil_groupe(
    groupe_id: str,
    groupe_sigle: str,
    groupe_nom: str,
    chambre: str | None,
    legislature: str | None,
) -> dict[str, Any]:
    """Create an empty group profile structure."""
    return {
        "schema_version": SCHEMA_GROUPE_VERSION,
        "type_document": "profil_groupe",
        "groupe_id": groupe_id,
        "groupe_sigle": groupe_sigle,
        "groupe_nom": groupe_nom,
        "chambre": chambre,
        "legislature": legislature,
        "periode": {
            "debut": None,
            "fin": None,
            "actif": True,
        },
        "historique_noms": [],
        "membres": [],
        "effectif": {
            "actuel": 0,
            "min_historique": None,
            "max_historique": None,
        },
        "cohesion_votes": [],
        "tags_thematiques_agreges": [],
        "amendements_agreges": {
            **make_empty_amendements_stats(),
            "par_type_deposant": {
                t: make_empty_amendements_stats() for t in AMENDEMENTS_TYPES_DEPOSANT
            },
        },
        "sources": [],
        "meta": {
            "schema_version": SCHEMA_GROUPE_VERSION,
            "genere_le": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "licence_donnees": "",
            "profils_sources": [],
            "seuil_quorum": 0.5,
            "warnings": [],
        },
    }


def validate_profil_groupe(profil: dict[str, Any]) -> list[str]:
    """Validate top-level invariants for a group profile."""
    errors: list[str] = []

    if not isinstance(profil, dict):
        return [f"Le profil de groupe doit être un dict, reçu : {type(profil).__name__}."]

    missing = REQUIRED_TOP_LEVEL_KEYS - set(profil.keys())
    if missing:
        errors.append(f"Clés manquantes au niveau racine : {sorted(missing)}.")

    version = profil.get("schema_version")
    if version != SCHEMA_GROUPE_VERSION:
        errors.append(
            f"schema_version inattendu : {version!r} (attendu : {SCHEMA_GROUPE_VERSION!r})."
        )

    if profil.get("type_document") != "profil_groupe":
        errors.append(
            f"'type_document' doit être 'profil_groupe', reçu : {profil.get('type_document')!r}."
        )

    if not profil.get("groupe_id"):
        errors.append("'groupe_id' est vide ou absent.")

    chambre = profil.get("chambre")
    if chambre is not None and chambre not in KNOWN_CHAMBRES:
        errors.append(
            f"'chambre' non reconnue : {chambre!r}. Valeurs connues : {sorted(KNOWN_CHAMBRES)}."
        )

    for key in _LIST_KEYS:
        val = profil.get(key)
        if val is not None and not isinstance(val, list):
            errors.append(f"'{key}' doit être une liste, reçu : {type(val).__name__}.")

    periode = profil.get("periode")
    if not isinstance(periode, dict):
        errors.append("'periode' doit être un dict.")

    amendements_agreges = profil.get("amendements_agreges")
    if amendements_agreges is not None and not isinstance(amendements_agreges, dict):
        errors.append("'amendements_agreges' doit être un dict.")
    elif isinstance(amendements_agreges, dict):
        par_type = amendements_agreges.get("par_type_deposant")
        if par_type is not None and not isinstance(par_type, dict):
            errors.append("'amendements_agreges.par_type_deposant' doit être un dict.")

    meta = profil.get("meta")
    if not isinstance(meta, dict):
        errors.append("'meta' doit être un dict.")
    else:
        missing_meta = REQUIRED_META_KEYS - set(meta.keys())
        if missing_meta:
            errors.append(f"Clés manquantes dans 'meta' : {sorted(missing_meta)}.")
        if meta.get("schema_version") != SCHEMA_GROUPE_VERSION:
            errors.append(
                f"meta.schema_version inattendu : {meta.get('schema_version')!r} "
                f"(attendu : {SCHEMA_GROUPE_VERSION!r})."
            )
        if not isinstance(meta.get("warnings"), list):
            errors.append("'meta.warnings' doit être une liste.")
        if not isinstance(meta.get("profils_sources"), list):
            errors.append("'meta.profils_sources' doit être une liste.")
        couverture_roster = meta.get("couverture_roster")
        if couverture_roster is not None and not isinstance(couverture_roster, dict):
            errors.append("'meta.couverture_roster' doit être un dict.")

    return errors
