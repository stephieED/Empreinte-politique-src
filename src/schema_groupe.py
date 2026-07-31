#!/usr/bin/env python3
"""
schema_groupe.py — Schéma pivot du profil de groupe politique v1.

Ce module définit le contrat de structure du « profil de groupe », document
agrégé calculé à partir de plusieurs profils individuels (schéma pivot v1)
partageant le même groupe parlementaire.

Il ne contient aucune logique de collecte ni de calcul : c'est un contrat de
structure (constantes, fabrique, validateur). La logique d'agrégation est dans
group_profile.py.

Principe directeur : faits chiffrés uniquement, aucune interprétation.

Format d'un profil de groupe v1 :
{
    "schema_version": "1",
    "type_document": "profil_groupe",
    "groupe_id": "AN:SOC",              # "<chambre>:<sigle>" — même convention que le pivot individuel
    "groupe_sigle": "SOC",
    "groupe_nom": "Socialistes et apparentés",
    "chambre": "AN",                    # "AN" | "Senat" | "PE" | "mairie" | null
    "legislature": "16",

    "periode": {
        "debut": "2022-06-22",          # début du groupe dans cette législature
        "fin": null,
        "actif": true
    },

    "historique_noms": [                # renommages du groupe entre législatures
        {
            "sigle": "SOC",
            "nom": "Socialistes et apparentés",
            "debut": "2022-06-22",
            "fin": null
        }
    ],

    "membres": [                        # un enregistrement par membre (et par période si changement)
        {
            "membre_id": "nosdeputes:jerome-guedj",  # id pivot individuel
            "nom": "Jérôme Guedj",
            "debut_dans_groupe": "2022-06-22",       # début de l'appartenance à CE groupe
            "fin_dans_groupe": null,                 # null = toujours membre
            "actif": true
        }
    ],

    "effectif": {
        "actuel": 64,                   # nombre de membres actifs au moment du calcul
        "min_historique": null,         # min. sur la période (null si non calculé)
        "max_historique": null          # max. sur la période (null si non calculé)
    },

    "cohesion_votes": [                 # une entrée par scrutin sur lequel ≥1 membre a voté
        {
            "numero_scrutin": "4084",
            "date": "2024-06-07",
            "texte": "Projet de loi …",
            "sort": "rejeté",
            "membres_eligibles": 64,    # membres en mandat à la date du scrutin
            "position_majoritaire": "contre",
            "pour": 42,
            "contre": 12,
            "abstention": 3,
            "non_votant": 2,
            "absents": 5,               # membres éligibles sans trace de vote
            "excuses": 0,               # absences notifiées/justifiées
            "taux_participation": 0.921,
            "taux_coherence": 0.656,    # alignés / membres_eligibles
            "taux_coherence_hors_absents": 0.847,  # alignés / (éligibles − absents − excusés)
            "quorum_atteint": true      # taux_participation ≥ seuil_quorum configuré
        }
    ],

    "tags_thematiques_agreges": [       # agrégation des tags individuels, triés par poids desc
        {
            "tag": "budget",
            "nb_membres_porteurs": 14,  # nombre de membres ayant ce tag
            "poids_relatif": 0.218      # nb_membres_porteurs / len(membres)
        }
    ],

    "amendements_agreges": {            # comparateur du taux d'adoption individuel :
                                         # agrégation groupe/chambre des amendements[]
                                         # des profils individuels membres
        "nb_amendements": 120,
        "nb_adoptes": 18,
        "nb_rejetes": 74,
        "nb_irrecevables": 12,
        "nb_retires_ou_tombes": 16,
        "taux_adoption": 0.15           # nb_adoptes / nb_amendements ; null si nb_amendements == 0
    },

    "sources": [                        # traçabilité des sources individuelles agrégées
        {
            "type": "nosdeputes",
            "url": "https://www.nosdeputes.fr/groupe/SOC",
            "synchro_le": "2026-07-29T10:00:00+0000"
        }
    ],

    "meta": {
        "schema_version": "1",
        "genere_le": "2026-07-29T10:00:00+0000",
        "licence_donnees": "ODbL …",
        "profils_sources": [            # ids pivot des profils individuels agrégés
            "nosdeputes:jerome-guedj",
            "nosdeputes:boris-vallaud"
        ],
        "seuil_quorum": 0.5,            # seuil de participation retenu pour quorum_atteint
        "warnings": []
    }
}

Cas limites gérés :
- Élu qui change de groupe : membres[].fin_dans_groupe non null ; la cohésion
  n'utilise que les membres eligibles à la date de chaque scrutin.
- Groupe dissous/renommé : historique_noms[] + periode.fin non null.
- Scrutin sans quorum : quorum_atteint: false, cohésion toujours calculée.
- tags_thematiques vides : le calcul utilise les mots-clés des interventions
  individuelles en fallback (loggé dans meta.warnings).
- amendements_agreges.taux_adoption est null si aucun amendement n'est
  recensé sur les profils membres (nb_amendements == 0).

Hors périmètre de ce schéma (volontairement) :
- Le ratio individuel de cohérence/participation rapporté à la moyenne du
  groupe est une donnée de contrôle interne (voir
  group_profile.compute_ecarts_cohesion_internes) : il n'est PAS exposé dans
  ce document public tant qu'il n'a pas été validé comme sortie publique.

Usage :
    from schema_groupe import SCHEMA_GROUPE_VERSION, make_empty_profil_groupe, validate_profil_groupe
"""

import time
from typing import Any

from schema_pivot import KNOWN_CHAMBRES

# Version du schéma de groupe ; indépendante de SCHEMA_VERSION du pivot individuel.
SCHEMA_GROUPE_VERSION = "1"

# Clés obligatoires au niveau racine du profil de groupe.
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

# Clés obligatoires dans le bloc "meta".
REQUIRED_META_KEYS: frozenset[str] = frozenset({
    "schema_version",
    "genere_le",
    "licence_donnees",
    "profils_sources",
    "warnings",
})

# Champs dont la valeur doit être une liste.
_LIST_KEYS: tuple[str, ...] = (
    "historique_noms",
    "membres",
    "cohesion_votes",
    "tags_thematiques_agreges",
    "sources",
)


def make_empty_profil_groupe(
    groupe_id: str,
    groupe_sigle: str,
    groupe_nom: str,
    chambre: str | None,
    legislature: str | None,
) -> dict[str, Any]:
    """Crée un profil de groupe v1 vide avec des valeurs par défaut.

    Args:
        groupe_id: identifiant unique de la forme "<chambre>:<sigle>",
                   ex. "AN:SOC", "PE:S&D".
        groupe_sigle: sigle court du groupe (ex. "SOC", "LFI", "RN").
        groupe_nom: nom complet du groupe.
        chambre: "AN" | "Senat" | "PE" | "mairie" | None.
        legislature: numéro de législature (ex. "16") ou None.

    Returns:
        Profil de groupe dict initialisé, prêt à être enrichi par group_profile.py.
    """
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
            "nb_amendements": 0,
            "nb_adoptes": 0,
            "nb_rejetes": 0,
            "nb_irrecevables": 0,
            "nb_retires_ou_tombes": 0,
            "taux_adoption": None,
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
    """Vérifie les invariants de base du schéma de groupe v1.

    Validation structurelle de premier niveau : présence des clés obligatoires,
    types, valeur de schema_version et type_document. Ne valide pas le contenu
    de chaque entrée cohesion_votes ou membre.

    Args:
        profil: dict à valider.

    Returns:
        Liste d'erreurs (liste vide = profil valide).
    """
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

    return errors
