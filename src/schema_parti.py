#!/usr/bin/env python3
"""Module documentation in English."""

import time
from typing import Any

# Translated comment.
# Translated comment.
SCHEMA_PARTI_VERSION = "1"

# Translated comment.
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

# Translated comment.
REQUIRED_META_KEYS: frozenset[str] = frozenset({
    "schema_version",
    "genere_le",
    "licence_donnees",
    "nb_candidats_declares",
    "nb_candidats_avec_pivot",
    "warnings",
})

# Translated comment.
REQUIRED_CANDIDAT_KEYS: frozenset[str] = frozenset({
    "candidat_id",
    "nom",
    "statut",
    "famille_politique",
    "a_un_profil_pivot",
})

# Translated comment.
_LIST_KEYS: tuple[str, ...] = (
    "candidats",
    "tags_thematiques_agreges",
    "sources",
)


def make_empty_profil_parti(parti_id: str, parti_nom: str) -> dict[str, Any]:
    """Create an empty party profile structure."""
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
    """Validate top-level invariants for a party profile."""
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
