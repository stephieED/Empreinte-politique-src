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
            "source_url": null,              # URL de la fiche source, si disponible
            "position_dans_hemicycle": null, # "majorite" | "opposition" | null ; champ éditorial
                                             # le plus sensible du schéma. Ne JAMAIS renseigner
                                             # sans une source primaire vérifiable (déclaration
                                             # officielle du groupe, liste du socle de soutien au
                                             # gouvernement, JO) — voir source_url ci-dessus, qui
                                             # devient obligatoire dès que ce champ est renseigné.
            "mode_declenchement": null,      # commissions d'enquête uniquement :
                                             # "droit_tirage" | "demande_votee" | null
            "suspendu_pour_fonction_gouvernementale": null
            # période de suspension du mandat pour cause de fonction ministérielle :
            # {"debut": "2024-01-08", "fin": "2024-09-05", "suppleant_id": "nosdeputes:x"}
            # ou null si non applicable.
        }
    ],
    "votes": [
        {
            "date": "2024-06-12",
            "texte": "Projet de loi ...",    # titre du scrutin
            "position": "pour",              # "pour" | "contre" | "abstention" | "non_votant"
                                             # | "absent" | "excuse"
                                             # "absent" : aucune trace de vote (implicite ou explicite)
                                             # "excuse" : absence justifiée/notifiée à la source
            "numero_scrutin": "1234",
            "sort": "adopté",                # résultat du scrutin : "adopté" | "rejeté" |
                                             # "adopte_sans_vote_49_3" (engagement de la
                                             # responsabilité du gouvernement, art. 49.3 :
                                             # absence de vote sur l'ensemble) | ...
            "type_scrutin": null,            # métadonnée du vote, indépendante du résultat :
                                             # "public_ordinaire" | "solennel" | null
            "type_vote": "vote_texte",       # "vote_texte" | "motion_censure" ; une motion de
                                             # censure liée à un 49.3 est TOUJOURS un scrutin
                                             # séparé, jamais fusionnée avec la position sur le texte
            "texte_lie_id": null,            # identifiant commun reliant une motion_censure au
                                             # texte concerné (49.3) ; null pour un vote_texte
            "groupe_au_moment_du_vote": null,# groupe parlementaire au moment du scrutin ;
                                             # null si non renseigné (champ enrichissable en
                                             # post-traitement, utile pour les élus ayant changé
                                             # de groupe en cours de mandat)
            "source_url": null               # URL de la source primaire du scrutin
        }
    ],
    "textes_portes": [                       # dossiers dont l'élu est auteur ou rapporteur
        {
            "titre": "Proposition de loi ...",
            "role": "rapporteur",            # "auteur" | "rapporteur" | "co-rapporteur"
            "type_rapport": null,            # nomenclature officielle, descriptive uniquement :
                                             # "rapporteur_fond" | "rapporteur_avis" |
                                             # "rapporteur_special_budget" | "mission_information"
                                             # | null
            "stade_procedural": null,        # "depose" | "examine_commission" |
                                             # "inscrit_ordre_jour" | "discute_seance" |
                                             # "adopte" | "promulgue" | null
            "date_min": "2022-01-01",
            "date_max": "2022-06-30",
            "legislature": "16",
            "source_url": null
        }
    ],
    "amendements": [                         # amendements déposés par l'élu
        {
            "texte_vise": "Projet de loi de finances 2025",
            "sort": "irrecevable",           # "adopté" | "rejeté" | "retiré" | "tombé" |
                                             # "non_soutenu" | "irrecevable" (statut distinct
                                             # de "rejeté" — voir base_juridique_irrecevabilite)
            "base_juridique_irrecevabilite": "art. 40",  # "art. 40" | "art. 45" | null ;
                                             # renseigné uniquement si sort == "irrecevable"
            "premier_signataire": "nosdeputes:jean-dupont",
            "co_signataires": [],            # liste d'identifiants pivot des co-signataires
            "type_deposant": "depute",       # "gouvernement" | "commission_rapporteur" | "depute"
            "date": "2024-10-15",
            "numero": "CL42",
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
    "amendements", "tags_thematiques", "meta",
})

# Clés obligatoires dans le bloc "meta".
REQUIRED_META_KEYS: frozenset[str] = frozenset({
    "schema_version", "genere_le", "licence_donnees", "warnings",
})

# Champs dont la valeur doit être une liste.
_LIST_KEYS = (
    "votes", "mandats", "textes_portes", "interventions",
    "amendements", "tags_thematiques", "sources",
)

# Types de sources reconnus (extensible, liste non-exhaustive).
KNOWN_SOURCE_TYPES: frozenset[str] = frozenset({
    "nosdeputes", "nossenateurs", "parltrack", "wikidata", "assemblee_nationale", "europarl",
})

# Valeurs de chambre reconnues.
KNOWN_CHAMBRES: frozenset[str] = frozenset({"AN", "Senat", "PE", "mairie"})

# Positions de vote reconnues.
KNOWN_POSITIONS: frozenset[str] = frozenset({
    "pour", "contre", "abstention", "non_votant",
    "absent",   # aucune trace de vote (absence implicite ou explicite)
    "excuse",   # absence justifiée / notifiée à la source primaire
})

# Catégories de mandats reconnues.
KNOWN_CATEGORIES: frozenset[str] = frozenset({
    "mandat_electif", "commission", "groupe_amitie", "extra_parlementaire", "autre",
})

# Position dans l'hémicycle (majorité/opposition). Champ éditorial sensible :
# ne doit jamais être renseigné sans mandats[].source_url pointant vers une
# source primaire vérifiable (voir validate_profil).
KNOWN_POSITIONS_HEMICYCLE: frozenset[str] = frozenset({"majorite", "opposition"})

# Mode de déclenchement d'une commission d'enquête.
KNOWN_MODES_DECLENCHEMENT: frozenset[str] = frozenset({"droit_tirage", "demande_votee"})

# Nomenclature officielle des types de rapport (descriptive, pas une catégorie
# de valorisation éditoriale).
KNOWN_TYPES_RAPPORT: frozenset[str] = frozenset({
    "rapporteur_fond", "rapporteur_avis", "rapporteur_special_budget", "mission_information",
})

# Stade procédural d'un texte, pour identifier ce qui a été réellement débattu.
KNOWN_STADES_PROCEDURAUX: frozenset[str] = frozenset({
    "depose", "examine_commission", "inscrit_ordre_jour", "discute_seance",
    "adopte", "promulgue",
})

# Type de scrutin, métadonnée du vote indépendante de son résultat.
KNOWN_TYPES_SCRUTIN: frozenset[str] = frozenset({"public_ordinaire", "solennel"})

# Type d'entrée de vote : un vote sur motion de censure liée à un 49.3 est
# toujours une entrée de vote séparée, jamais fusionnée avec la position sur
# le texte concerné.
KNOWN_TYPES_VOTE: frozenset[str] = frozenset({"vote_texte", "motion_censure"})

# Type de déposant d'un amendement.
KNOWN_TYPES_DEPOSANT: frozenset[str] = frozenset({
    "gouvernement", "commission_rapporteur", "depute",
})

# Base juridique d'irrecevabilité d'un amendement (art. 40 : recevabilité
# financière ; art. 45 : lien avec le texte — "cavalier législatif").
KNOWN_BASES_IRRECEVABILITE: frozenset[str] = frozenset({"art. 40", "art. 45"})


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

    # position_dans_hemicycle est le champ éditorial le plus sensible du schéma :
    # il ne doit jamais être renseigné sans une source primaire vérifiable.
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
