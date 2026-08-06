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
    "identite": {                            # bloc biographique, tout est nullable/optionnel
        "profession": "Avocat",              # activité professionnelle déclarée (nosdeputes)
        "date_naissance": "1951-08-19",       # ISO-8601, date seule (nosdeputes ou AN)
        "lieu_naissance": null,              # ville + département/pays, texte libre ; fourni
                                             # uniquement par le référentiel AN (acteurs), pas nosdeputes
        "num_circo": "13",                    # numéro de circonscription tel que fourni par la
                                             # source ; absent pour un sénateur ou un mandat sans circonscription
        "uri_hatvp": null,                   # lien vers la déclaration HATVP (Haute Autorité pour
                                             # la Transparence de la Vie Publique), source AN (acteurs)
        "source_url": null                   # URL de la fiche source utilisée pour ce bloc
    },
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
                                             # "groupe_amitie" | "groupe_politique" |
                                             # "extra_parlementaire" | "autre"
            "fonction": "membre",            # ex. "membre", "président", "rapporteur"
            "debut": "2022-01-01",
            "fin": null,
            "actif": true,
            "source_url": null,              # URL de la fiche source, si disponible
            "position_dans_hemicycle": null, # "majorite" | "opposition" | "minoritaire" |
                                             # "gouvernement" | null ; champ éditorial le plus
                                             # sensible du schéma. Ne JAMAIS renseigner sans une
                                             # source primaire vérifiable (déclaration officielle
                                             # du groupe, liste du socle de soutien au gouvernement,
                                             # JO, ou positionPolitique/codeType du référentiel
                                             # officiel des organes de l'Assemblée nationale) — voir
                                             # source_url ci-dessus, qui devient obligatoire dès que
                                             # ce champ est renseigné. "gouvernement" n'est utilisé
                                             # que sur un mandat de categorie
                                             # "fonction_gouvernementale" (voir KNOWN_CATEGORIES).
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
                                             # | "rapporteur_general" | null
            "stade_procedural": null,        # "depose" | "examine_commission" |
                                             # "inscrit_ordre_jour" | "discute_seance" |
                                             # "adopte" | "promulgue" | null
            "date_min": "2022-01-01",
            "date_max": "2022-06-30",
            "legislature": "16",
            "source_url": null
        }
    ],
    "amendements": [                         # amendements liés à l'élu (auteur principal ou cosignataire)
        {
            "texte_vise": "Projet de loi de finances 2025",
            "sort": "irrecevable",           # "adopté" | "rejeté" | "retiré" | "tombé" |
                                             # "non_soutenu" | "irrecevable" (statut distinct
                                             # de "rejeté" — voir base_juridique_irrecevabilite)
            "base_juridique_irrecevabilite": "art. 40",  # "art. 40" | "art. 45" | null ;
                                             # renseigné uniquement si sort == "irrecevable"
            "role_signataire": "auteur_principal",  # rôle de l'élu sur l'amendement :
                                             # "auteur_principal" | "cosignataire"
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
            "source_url": "https://...",
            # Champs optionnels d'enrichissement issus des débats officiels
            # (ex. Syceron / comptes rendus institutionnels), sans rupture de
            # compatibilité pour les anciennes interventions :
            "theme_officiel": "Discussion générale",
            "seance": {
                "id": "3301",
                "titre": "2e séance du mercredi 15 mars 2023",
            },
            "dossier": {
                "id": "plf-2024",
                "titre": "Projet de loi de finances pour 2024",
            },
            "source": "compte_rendu_officiel",
            # Champs supplémentaires présents uniquement si type_detail == "question"
            # (questions parlementaires officielles, source open data AN) :
            "sous_type": "QE",               # "QE" (écrite) | "QG" (au gouvernement) | "QOSD" (orale sans débat)
            "ministere": "Ministère...",     # ministère interrogé (texte libre)
            "reponse": "...",                # texte de la réponse, si disponible (null sinon)
            "date_reponse": "2023-04-20",    # date JO de la réponse (null si pas encore répondu)
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

# Catégories de mandats reconnues. "groupe_politique" désigne une période
# d'appartenance à un groupe politique (distincte du mandat électif global),
# utilisée pour dater les changements de groupe et les rattacher à une
# position dans l'hémicycle (voir position_dans_hemicycle ci-dessous).
# "fonction_gouvernementale" désigne une période d'appartenance à un
# gouvernement (ministre, secrétaire d'État...), datée par le référentiel
# officiel des organes de l'Assemblée nationale (organe.codeType ==
# "GOUVERNEMENT") ; distincte de mandats[].suspendu_pour_fonction_gouvernementale,
# qui documente la suspension corrélative du mandat électif, pas la fonction
# gouvernementale elle-même.
KNOWN_CATEGORIES: frozenset[str] = frozenset({
    "mandat_electif", "commission", "groupe_amitie", "groupe_politique",
    "extra_parlementaire", "fonction_gouvernementale", "autre",
})

# Position dans l'hémicycle (majorité/opposition/minoritaire/gouvernement).
# Champ éditorial sensible : ne doit jamais être renseigné sans
# mandats[].source_url pointant vers une source primaire vérifiable (voir
# validate_profil). "minoritaire" correspond à la qualification officielle
# "Minoritaire" de l'Assemblée nationale (groupe ni majoritaire ni
# d'opposition formelle). "gouvernement" qualifie une période d'appartenance
# à un gouvernement (l'élu n'est alors ni majorité ni opposition au sens
# parlementaire du terme, mais membre de l'exécutif) : cette valeur n'est
# jamais déduite depuis un mandat de catégorie autre que
# "fonction_gouvernementale".
KNOWN_POSITIONS_HEMICYCLE: frozenset[str] = frozenset({
    "majorite", "opposition", "minoritaire", "gouvernement",
})

# Mode de déclenchement d'une commission d'enquête.
KNOWN_MODES_DECLENCHEMENT: frozenset[str] = frozenset({"droit_tirage", "demande_votee"})

# Nomenclature officielle des types de rapport (descriptive, pas une catégorie
# de valorisation éditoriale).
KNOWN_TYPES_RAPPORT: frozenset[str] = frozenset({
    "rapporteur_fond", "rapporteur_avis", "rapporteur_special_budget", "mission_information",
    "rapporteur_general",
})

# Stade procédural d'un texte, pour identifier ce qui a été réellement débattu.
KNOWN_STADES_PROCEDURAUX: frozenset[str] = frozenset({
    "depose", "examine_commission", "inscrit_ordre_jour", "discute_seance",
    "adopte", "promulgue",
})

# Rôle factuel de l'élu sur le texte. ``None`` signifie que la source ne
# permet pas de distinguer auteur, rapporteur et co-rapporteur.
KNOWN_ROLES_TEXTE: frozenset[str] = frozenset({"auteur", "rapporteur", "co-rapporteur"})

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

# Rôle de signature de l'élu sur un amendement.
KNOWN_ROLES_SIGNATAIRE_AMENDEMENT: frozenset[str] = frozenset({
    "auteur_principal", "cosignataire",
})

# Base juridique d'irrecevabilité d'un amendement (art. 40 : recevabilité
# financière ; art. 45 : lien avec le texte — "cavalier législatif").
KNOWN_BASES_IRRECEVABILITE: frozenset[str] = frozenset({"art. 40", "art. 45"})

# Champs optionnels d'interventions enrichies depuis des débats officiels :
# thèmes/sources textuels, séance et dossier sous forme libre mais structurée.
KNOWN_OPTIONAL_INTERVENTION_STRING_FIELDS: tuple[str, ...] = ("theme_officiel", "source")
KNOWN_OPTIONAL_INTERVENTION_CONTEXT_FIELDS: tuple[str, ...] = ("seance", "dossier")
KNOWN_OPTIONAL_INTERVENTION_FIELDS: tuple[str, ...] = (
    *KNOWN_OPTIONAL_INTERVENTION_STRING_FIELDS,
    *KNOWN_OPTIONAL_INTERVENTION_CONTEXT_FIELDS,
)


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
    """Vérifie les invariants de base du schéma pivot v1.

    Validation structurelle de premier niveau (clés obligatoires, types,
    schema_version) plus les invariants de contenu des champs sensibles :
    position_dans_hemicycle/source_url, mode_declenchement, type_scrutin,
    type_vote/texte_lie_id (motion_censure), type_rapport, stade_procedural,
    type_deposant, sort/base_juridique_irrecevabilite des amendements, et les
    champs optionnels d'enrichissement des débats officiels dans interventions[].

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

    identite = profil.get("identite")
    if identite is not None and not isinstance(identite, dict):
        errors.append(f"'identite' doit être un dict ou null, reçu : {type(identite).__name__}.")

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
            mode_declenchement = m.get("mode_declenchement")
            if mode_declenchement is not None and mode_declenchement not in KNOWN_MODES_DECLENCHEMENT:
                errors.append(
                    f"mandats[{i}].mode_declenchement non reconnu : {mode_declenchement!r}. "
                    f"Valeurs connues : {sorted(KNOWN_MODES_DECLENCHEMENT)}."
                )

    # type_vote == "motion_censure" doit toujours être lié à son texte 49.3 via
    # texte_lie_id : une motion de censure n'est jamais fusionnée avec le vote
    # sur le texte concerné (voir docstring du module).
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
            sort = v.get("sort")
            if sort == "adopte_sans_vote_49_3" and v.get("position") is not None:
                errors.append(
                    f"votes[{i}] : sort='adopte_sans_vote_49_3' ne peut avoir de position "
                    "(49.3 = absence de vote, jamais une position — AGENTS.md règle 4)."
                )
            position = v.get("position")
            if position is not None and position not in KNOWN_POSITIONS:
                errors.append(
                    f"votes[{i}].position non reconnue : {position!r}. "
                    f"Valeurs connues : {sorted(KNOWN_POSITIONS)}."
                )

    # role / type_rapport / stade_procedural : nomenclature factuelle, jamais une
    # catégorie éditoriale de valorisation.
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

    # base_juridique_irrecevabilite est obligatoire dès que sort == "irrecevable" :
    # l'irrecevabilité est un statut distinct d'un simple rejet sur le fond.
    amendements = profil.get("amendements")
    if isinstance(amendements, list):
        for i, a in enumerate(amendements):
            if not isinstance(a, dict):
                continue
            role_signataire = a.get("role_signataire")
            if role_signataire is not None and role_signataire not in KNOWN_ROLES_SIGNATAIRE_AMENDEMENT:
                errors.append(
                    f"amendements[{i}].role_signataire non reconnu : {role_signataire!r}. "
                    f"Valeurs connues : {sorted(KNOWN_ROLES_SIGNATAIRE_AMENDEMENT)}."
                )
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

    interventions = profil.get("interventions")
    if isinstance(interventions, list):
        for i, intervention in enumerate(interventions):
            if not isinstance(intervention, dict):
                continue
            for key in KNOWN_OPTIONAL_INTERVENTION_STRING_FIELDS:
                value = intervention.get(key)
                if value is not None and not isinstance(value, str):
                    errors.append(
                        f"interventions[{i}].{key} doit être une chaîne ou null, "
                        f"reçu : {type(value).__name__}."
                    )
            for key in KNOWN_OPTIONAL_INTERVENTION_CONTEXT_FIELDS:
                value = intervention.get(key)
                if value is not None and not isinstance(value, dict):
                    errors.append(
                        f"interventions[{i}].{key} doit être un dict ou null, "
                        f"reçu : {type(value).__name__}."
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
