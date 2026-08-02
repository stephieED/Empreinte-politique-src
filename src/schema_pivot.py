#!/usr/bin/env python3
"""Module documentation in English."""

import time
from typing import Any

# Translated comment.
# Translated comment.
SCHEMA_VERSION = "1"

# Translated comment.
REQUIRED_TOP_LEVEL_KEYS: frozenset[str] = frozenset({
    "schema_version", "id", "nom", "chambre", "sources",
    "mandats", "votes", "textes_portes", "interventions",
    "amendements", "tags_thematiques", "meta",
})

# Translated comment.
REQUIRED_META_KEYS: frozenset[str] = frozenset({
    "schema_version", "genere_le", "licence_donnees", "warnings",
})

# Translated comment.
_LIST_KEYS = (
    "votes", "mandats", "textes_portes", "interventions",
    "amendements", "tags_thematiques", "sources",
)

# Translated comment.
KNOWN_SOURCE_TYPES: frozenset[str] = frozenset({
    "nosdeputes", "nossenateurs", "parltrack", "wikidata", "assemblee_nationale", "europarl",
})

# Valeurs de chambre reconnues.
KNOWN_CHAMBRES: frozenset[str] = frozenset({"AN", "Senat", "PE", "mairie"})

# Positions de vote reconnues.
KNOWN_POSITIONS: frozenset[str] = frozenset({
    "pour", "contre", "abstention", "non_votant",
    "absent",   # Translated comment.
    "excuse",   # Translated comment.
})

# Translated comment.
KNOWN_CATEGORIES: frozenset[str] = frozenset({
    "mandat_electif", "commission", "groupe_amitie", "extra_parlementaire", "autre",
})

# Translated comment.
# Translated comment.
# Translated comment.
KNOWN_POSITIONS_HEMICYCLE: frozenset[str] = frozenset({"majorite", "opposition"})

# Translated comment.
KNOWN_MODES_DECLENCHEMENT: frozenset[str] = frozenset({"droit_tirage", "demande_votee"})

# Translated comment.
# Translated comment.
KNOWN_TYPES_RAPPORT: frozenset[str] = frozenset({
    "rapporteur_fond", "rapporteur_avis", "rapporteur_special_budget", "mission_information",
    "rapporteur_general",
})

# Translated comment.
KNOWN_STADES_PROCEDURAUX: frozenset[str] = frozenset({
    "depose", "examine_commission", "inscrit_ordre_jour", "discute_seance",
    "adopte", "promulgue",
})

# Translated comment.
# Translated comment.
KNOWN_ROLES_TEXTE: frozenset[str] = frozenset({"auteur", "rapporteur", "co-rapporteur"})

# Translated comment.
KNOWN_TYPES_SCRUTIN: frozenset[str] = frozenset({"public_ordinaire", "solennel"})

# Translated comment.
# Translated comment.
# Translated comment.
KNOWN_TYPES_VOTE: frozenset[str] = frozenset({"vote_texte", "motion_censure"})

# Translated comment.
KNOWN_TYPES_DEPOSANT: frozenset[str] = frozenset({
    "gouvernement", "commission_rapporteur", "depute",
})

# Translated comment.
# Translated comment.
KNOWN_BASES_IRRECEVABILITE: frozenset[str] = frozenset({"art. 40", "art. 45"})


def make_empty_profil(id_: str, nom: str) -> dict[str, Any]:
    """Create an empty pivot profile structure."""
    return {
        "schema_version": SCHEMA_VERSION,
        "id": id_,
        "nom": nom,
        "chambre": None,
        "parti": None,
        "groupe": None,
        "identite": None,
        "sources": [],
        "mandats": [],
        "votes": [],
        "textes_portes": [],
        "interventions": [],
        "amendements": [],
        "tags_thematiques": [],
        "meta": {
            "schema_version": SCHEMA_VERSION,
            "genere_le": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "licence_donnees": "",
            "warnings": [],
        },
    }


def validate_profil(profil: dict[str, Any]) -> list[str]:
    """Validate top-level invariants for a pivot profile."""
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

    identite = profil.get("identite")
    if identite is not None and not isinstance(identite, dict):
        errors.append(f"'identite' doit être un dict ou null, reçu : {type(identite).__name__}.")

    for key in _LIST_KEYS:
        val = profil.get(key)
        if val is not None and not isinstance(val, list):
            errors.append(f"'{key}' doit être une liste, reçu : {type(val).__name__}.")

    # Translated comment.
    # Translated comment.
    mandats = profil.get("mandats")
    if isinstance(mandats, list):
        for i, m in enumerate(mandats):
            if not isinstance(m, dict):
                continue
            if m.get("position_dans_hemicycle") is not None and not m.get("source_url"):
                errors.append(
                    f"mandats[{i}].position_dans_hemicycle est renseigné sans "
                    "source_url : ce champ requiert une source primaire vérifiable."
                )
            mode_declenchement = m.get("mode_declenchement")
            if mode_declenchement is not None and mode_declenchement not in KNOWN_MODES_DECLENCHEMENT:
                errors.append(
                    f"mandats[{i}].mode_declenchement non reconnu : {mode_declenchement!r}. "
                    f"Valeurs connues : {sorted(KNOWN_MODES_DECLENCHEMENT)}."
                )

    # Translated comment.
    # Translated comment.
    # Translated comment.
    votes = profil.get("votes")
    if isinstance(votes, list):
        for i, v in enumerate(votes):
            if not isinstance(v, dict):
                continue
            type_scrutin = v.get("type_scrutin")
            if type_scrutin is not None and type_scrutin not in KNOWN_TYPES_SCRUTIN:
                errors.append(
                    f"votes[{i}].type_scrutin non reconnu : {type_scrutin!r}. "
                    f"Valeurs connues : {sorted(KNOWN_TYPES_SCRUTIN)}."
                )
            type_vote = v.get("type_vote")
            if type_vote is not None and type_vote not in KNOWN_TYPES_VOTE:
                errors.append(
                    f"votes[{i}].type_vote non reconnu : {type_vote!r}. "
                    f"Valeurs connues : {sorted(KNOWN_TYPES_VOTE)}."
                )
            if type_vote == "motion_censure" and not v.get("texte_lie_id"):
                errors.append(
                    f"votes[{i}] : type_vote='motion_censure' sans 'texte_lie_id' "
                    "(le texte 49.3 concerné doit être identifié, jamais fusionné "
                    "avec le vote sur le texte)."
                )

    # Translated comment.
    # Translated comment.
    textes_portes = profil.get("textes_portes")
    if isinstance(textes_portes, list):
        for i, t in enumerate(textes_portes):
            if not isinstance(t, dict):
                continue
            role = t.get("role")
            if role is not None and role not in KNOWN_ROLES_TEXTE:
                errors.append(
                    f"textes_portes[{i}].role non reconnu : {role!r}. "
                    f"Valeurs connues : {sorted(KNOWN_ROLES_TEXTE)}."
                )
            type_rapport = t.get("type_rapport")
            if type_rapport is not None and type_rapport not in KNOWN_TYPES_RAPPORT:
                errors.append(
                    f"textes_portes[{i}].type_rapport non reconnu : {type_rapport!r}. "
                    f"Valeurs connues : {sorted(KNOWN_TYPES_RAPPORT)}."
                )
            stade_procedural = t.get("stade_procedural")
            if stade_procedural is not None and stade_procedural not in KNOWN_STADES_PROCEDURAUX:
                errors.append(
                    f"textes_portes[{i}].stade_procedural non reconnu : {stade_procedural!r}. "
                    f"Valeurs connues : {sorted(KNOWN_STADES_PROCEDURAUX)}."
                )

    # Translated comment.
    # Translated comment.
    amendements = profil.get("amendements")
    if isinstance(amendements, list):
        for i, a in enumerate(amendements):
            if not isinstance(a, dict):
                continue
            type_deposant = a.get("type_deposant")
            if type_deposant is not None and type_deposant not in KNOWN_TYPES_DEPOSANT:
                errors.append(
                    f"amendements[{i}].type_deposant non reconnu : {type_deposant!r}. "
                    f"Valeurs connues : {sorted(KNOWN_TYPES_DEPOSANT)}."
                )
            base_juridique = a.get("base_juridique_irrecevabilite")
            if a.get("sort") == "irrecevable" and not base_juridique:
                errors.append(
                    f"amendements[{i}] : sort='irrecevable' sans "
                    "'base_juridique_irrecevabilite' (l'irrecevabilité est un statut "
                    "distinct d'un simple rejet)."
                )
            if base_juridique is not None and base_juridique not in KNOWN_BASES_IRRECEVABILITE:
                errors.append(
                    f"amendements[{i}].base_juridique_irrecevabilite non reconnue : "
                    f"{base_juridique!r}. Valeurs connues : {sorted(KNOWN_BASES_IRRECEVABILITE)}."
                )

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
