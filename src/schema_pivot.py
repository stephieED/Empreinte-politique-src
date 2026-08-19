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
                                             # "extra_parlementaire" | "autre" |
                                             # "commission_enquete" | "mission_information" |
                                             # "groupe_etudes" | "delegation"
                                             # (voir KNOWN_CATEGORIES)
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
    "votes": [                               # MAPPING seul (#432) : un scrutin est identique
                                             # pour tous ses votants, son méta vit une seule fois
                                             # dans pivot_data/scrutins.json (schéma scrutins-v1).
                                             # Ne garder ici que ce qui est propre au membre.
        {
            "scrutin_id": "an:17:1234",      # "an:<legislature>:<numero_scrutin>" — la législature
                                             # fait partie de l'identifiant parce que le numéro
                                             # repart de 1 à chaque législature (AGENTS.md §5).
                                             # null UNIQUEMENT si le scrutin n'a pas pu être
                                             # résolu ; "scrutin_non_resolu" est alors obligatoire.
            "position": "pour"               # "pour" | "contre" | "abstention" | "non_votant"
                                             # | "absent" | "excuse" | null
                                             # "absent" : aucune trace de vote (implicite ou explicite)
                                             # "excuse" : absence justifiée/notifiée à la source
            # "groupe_au_moment_du_vote": "SOC"
                                             # FACULTATIF — écrit seulement s'il est renseigné.
                                             # Son absence signifie "non renseigné", exactement
                                             # comme null : seule exception à la convention
                                             # "missing = null" (§4), et elle est chiffrée —
                                             # le champ n'est jamais peuplé (0 sur 398 085) et
                                             # l'écrire coûtait 12,1 Mo de null, 40 % du mapping.
            # "scrutin_non_resolu": {...}    # FACULTATIF, et anormal : enregistrement complet du
                                             # vote (date, texte, sort, type_vote…) conservé tel
                                             # quel quand aucune législature n'a pu être résolue.
                                             # Ni supprimé ni doté d'une clé inventée (§2.5).
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
            "uid": "AMANR5L17PO59047BTC1376P0D1N000012",  # identifiant AN de l'amendement :
                                             # seule clé unique (le `numero` repart à chaque
                                             # texte — 121 805 amendements pour 30 616 numéros
                                             # distincts en législature 17). Absent des entrées
                                             # collectées avant le 18/08/2026, voir
                                             # docs/technical_decisions.md#amendements-cle-uid
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
            "theme_officiel": null,          # thème officiel du débat si fourni par
                                             # une source institutionnelle (sinon null)
            "seance": null,                  # métadonnées de séance officielles (dict)
            "dossier": null,                 # métadonnées de dossier officiel (dict)
            "source": null,                  # métadonnées de source officielle (dict)
            "texte": "...",                  # extrait (180 premiers caractères)
            "fonction": "Rapporteur",        # rôle institutionnel au moment de l'intervention
            "format": "prise_de_parole_developpee",  # ou "reaction_courte"
            "mots_cles": ["budget", "fiscalité"],
            "source_url": "https://...",
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
        "warnings": [],
        "provenance": "candidat_declare"          # "candidat_declare" | "roster_groupe" ;
                                             # voir KNOWN_PROVENANCES
    }
}

Usage :
    from schema_pivot import SCHEMA_VERSION, make_empty_profil, validate_profil
"""

import time
from typing import Any
from scrutins_index import decomposer_id

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
# Les 4 dernières catégories sont issues de #382/#383 (option « mixte ») :
# le référentiel officiel AN distingue une vingtaine de `typeOrgane`, dont
# près de la moitié des mandats n'étaient jusque-là pas exploités faute de
# catégorie pour les accueillir — commissions d'enquête, missions
# d'information, groupes d'études et délégations se retrouvaient tous rangés
# sous `commission` par l'ancien mapping NosDéputés, ce qui trompait sur leur
# nature (voir docs/technical_decisions.md#taxonomie-mandats-typeorgane-an).
# Choix de granularité : une catégorie par nature institutionnelle
# réellement distincte pour l'utilisateur, pas une par `typeOrgane` — les
# variantes internes (MISINFO/MISINFOCOM/MISINFOPRE, CNPE/CNPS, GE/GEVI,
# DELEG/API/OFFPAR) sont regroupées.
KNOWN_CATEGORIES: frozenset[str] = frozenset({
    "mandat_electif", "commission", "groupe_amitie", "groupe_politique",
    "extra_parlementaire", "fonction_gouvernementale", "autre",
    "commission_enquete", "mission_information", "groupe_etudes", "delegation",
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

# Version du schéma de `pivot_data/scrutins.json` (#432). Distincte de
# SCHEMA_VERSION : la liste partagée des scrutins et les profils évoluent
# séparément, et les confondre obligerait à réécrire tous les profils pour un
# changement qui ne les touche pas.
SCRUTINS_SCHEMA_VERSION = "scrutins-v1"

# Provenance de la `legislature` d'un scrutin (#432, voir scrutins_legislature).
# Nomenclature fermée, et le point n'est pas cosmétique : une législature
# dérivée d'un calendrier ne doit jamais passer pour une donnée collectée.
KNOWN_PROVENANCES_LEGISLATURE: frozenset[str] = frozenset({
    "collectee", "resolue_par_jumeau", "derivee_du_calendrier",
})

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

# Provenance du profil (meta.provenance) : distingue un candidat déclaré à la
# présidentielle (raw_data/candidats.json, source éditoriale) d'un profil
# extrait via le roster réel d'un groupe parlementaire (generate_roster_candidats.py,
# #188). Politique de fusion (voir merge_profile.merge_pivot_profile) : un profil
# "candidat_declare" n'est jamais rétrogradé vers "roster_groupe" par une
# régénération roster-driven du même slug, pour ne jamais perdre l'enrichissement
# éditorial déjà présent (parti, etc.).
KNOWN_PROVENANCES: frozenset[str] = frozenset({"candidat_declare", "roster_groupe"})


def make_empty_profil(id_: str, nom: str, provenance: str = "candidat_declare") -> dict[str, Any]:
    """Crée un profil pivot v1 vide avec des valeurs par défaut.

    Args:
        id_: identifiant unique de la forme "<source>:<identifiant_source>",
             ex. "nosdeputes:jean-luc-melenchon", "parltrack:197451".
        nom: nom complet de l'élu.
        provenance: origine du profil, "candidat_declare" (défaut, raw_data/candidats.json)
                    ou "roster_groupe" (extraction pilotée par le roster réel d'un
                    groupe parlementaire, #188). Voir KNOWN_PROVENANCES.

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
            "provenance": provenance,
        },
    }


def validate_profil(profil: dict[str, Any], scrutins_index: Any = None) -> list[str]:
    """Vérifie les invariants de base du schéma pivot v1.

    `scrutins_index` (facultatif, un `ScrutinsIndex`) : depuis #432, le méta
    d'un scrutin vit dans `pivot_data/scrutins.json` et le profil n'en garde que
    le mapping. Deux invariants deviennent donc des **jointures** et ne sont
    vérifiés que si l'index est fourni : qu'un `scrutin_id` référencé existe, et
    la règle 4 (un 49.3 ne porte jamais de position). Sans index, ils sont
    sautés — jamais déclarés valides par défaut.

    Validation structurelle de premier niveau (clés obligatoires, types,
    schema_version) plus les invariants de contenu des champs sensibles :
    position_dans_hemicycle/source_url, mode_declenchement, forme du
    scrutin_id, type_rapport, stade_procedural,
    type_deposant, sort/base_juridique_irrecevabilite des amendements, et
    structure des champs optionnels de débats officiels dans interventions[]
    (theme_officiel, seance, dossier, source).

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

    # Depuis #432, `votes[]` est un MAPPING : `type_scrutin`, `type_vote`,
    # `texte_lie_id` et `sort` ont migré vers `pivot_data/scrutins.json` et sont
    # validés par `validate_scrutins_index`. Ne restent ici que les invariants
    # du mapping lui-même — plus la règle 4, qui est une jointure et n'est donc
    # vérifiable qu'avec l'index (voir `scrutins_index` ci-dessous).
    votes = profil.get("votes")
    index_par_id = (scrutins_index.par_id if scrutins_index is not None else None)
    if isinstance(votes, list):
        for i, v in enumerate(votes):
            if not isinstance(v, dict):
                continue
            scrutin_id = v.get("scrutin_id")
            if scrutin_id is None:
                # Un vote sans identifiant DOIT porter son enregistrement
                # complet : sans lui, la donnée serait perdue au lieu d'être
                # seulement non normalisée (AGENTS.md §2.5).
                if not isinstance(v.get("scrutin_non_resolu"), dict):
                    errors.append(
                        f"votes[{i}] : 'scrutin_id' absent sans 'scrutin_non_resolu'. "
                        "Un vote qu'on ne sait pas rattacher garde son enregistrement "
                        "complet — il n'est ni supprimé, ni doté d'une clé inventée."
                    )
            else:
                legislature, numero = decomposer_id(scrutin_id)
                if legislature is None or numero is None:
                    errors.append(
                        f"votes[{i}].scrutin_id mal formé : {scrutin_id!r}. "
                        "Forme attendue : 'an:<legislature>:<numero_scrutin>'."
                    )
                elif index_par_id is not None and scrutin_id not in index_par_id:
                    errors.append(
                        f"votes[{i}].scrutin_id introuvable dans l'index des scrutins : "
                        f"{scrutin_id!r}. Le mapping pointerait dans le vide."
                    )
            position = v.get("position")
            if position is not None and position not in KNOWN_POSITIONS:
                errors.append(
                    f"votes[{i}].position non reconnue : {position!r}. "
                    f"Valeurs connues : {sorted(KNOWN_POSITIONS)}."
                )
            # Règle 4 : un 49.3 n'est jamais une position. Le `sort` vivant
            # désormais sur le scrutin, la vérification est une jointure — elle
            # n'est possible qu'avec l'index, et est silencieusement sautée
            # sans lui plutôt que faussement validée.
            if index_par_id is not None and position is not None:
                scrutin = index_par_id.get(scrutin_id) or {}
                if scrutin.get("sort") == "adopte_sans_vote_49_3":
                    errors.append(
                        f"votes[{i}] : le scrutin {scrutin_id} a sort='adopte_sans_vote_49_3' "
                        f"mais ce vote porte une position ({position!r}) — 49.3 = absence de "
                        "vote, jamais une position (AGENTS.md règle 4)."
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
        for i, inter in enumerate(interventions):
            if not isinstance(inter, dict):
                continue
            theme_officiel = inter.get("theme_officiel")
            if theme_officiel is not None and not isinstance(theme_officiel, str):
                errors.append(
                    f"interventions[{i}].theme_officiel doit être une chaîne ou null, "
                    f"reçu : {type(theme_officiel).__name__}."
                )
            for key in ("seance", "dossier", "source"):
                val = inter.get(key)
                if val is not None and not isinstance(val, dict):
                    errors.append(
                        f"interventions[{i}].{key} doit être un dict ou null, "
                        f"reçu : {type(val).__name__}."
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
        # meta.provenance : absent = rétro-compatible (traité comme "candidat_declare"
        # par les consommateurs, voir merge_profile.merge_pivot_profile), donc validé
        # uniquement s'il est présent.
        provenance = meta.get("provenance")
        if provenance is not None and provenance not in KNOWN_PROVENANCES:
            errors.append(
                f"meta.provenance non reconnue : {provenance!r}. "
                f"Valeurs connues : {sorted(KNOWN_PROVENANCES)}."
            )

    return errors


def validate_scrutins_index(index: dict[str, Any]) -> list[str]:
    """Vérifie `pivot_data/scrutins.json` (schéma `scrutins-v1`, #432).

    Les invariants qui portaient sur `votes[]` avant la normalisation ont suivi
    les champs : `type_scrutin`, `type_vote`, `texte_lie_id` (motion de censure)
    et la forme de l'identifiant se vérifient désormais ici, une fois par
    scrutin au lieu d'une fois par votant.

    La règle 4 (49.3 = jamais une position) reste chez `validate_profil` : elle
    joint un `sort` d'ici à une `position` de là-bas, et c'est côté profil que la
    position vit.
    """
    errors: list[str] = []

    if not isinstance(index, dict):
        return ["L'index des scrutins doit être un objet JSON."]

    version = index.get("schema_version")
    if version != SCRUTINS_SCHEMA_VERSION:
        errors.append(
            f"schema_version de l'index : {version!r}, attendu {SCRUTINS_SCHEMA_VERSION!r}."
        )

    scrutins = index.get("scrutins")
    if not isinstance(scrutins, list):
        return errors + ["Clé 'scrutins' manquante ou de mauvais type (liste attendue)."]

    vus: set[str] = set()
    for i, scrutin in enumerate(scrutins):
        if not isinstance(scrutin, dict):
            errors.append(f"scrutins[{i}] n'est pas un objet.")
            continue

        scrutin_id = scrutin.get("id")
        legislature, numero = decomposer_id(scrutin_id) if scrutin_id else (None, None)
        if legislature is None or numero is None:
            errors.append(
                f"scrutins[{i}].id mal formé : {scrutin_id!r}. "
                "Forme attendue : 'an:<legislature>:<numero_scrutin>'."
            )
        else:
            # L'identifiant est dérivé de ces deux champs : une divergence
            # rendrait la liste incohérente avec elle-même, et un consommateur
            # qui décomposerait l'id n'obtiendrait pas ce que porte le champ.
            if str(scrutin.get("legislature")) != legislature:
                errors.append(
                    f"scrutins[{i}] : id {scrutin_id!r} et legislature "
                    f"{scrutin.get('legislature')!r} divergent."
                )
            if str(scrutin.get("numero_scrutin")) != numero:
                errors.append(
                    f"scrutins[{i}] : id {scrutin_id!r} et numero_scrutin "
                    f"{scrutin.get('numero_scrutin')!r} divergent."
                )
            if scrutin_id in vus:
                errors.append(f"scrutins[{i}] : identifiant en double ({scrutin_id!r}).")
            vus.add(scrutin_id)

        provenance = scrutin.get("legislature_provenance")
        if provenance not in KNOWN_PROVENANCES_LEGISLATURE:
            errors.append(
                f"scrutins[{i}].legislature_provenance non reconnue : {provenance!r}. "
                f"Valeurs connues : {sorted(KNOWN_PROVENANCES_LEGISLATURE)}. "
                "Une législature dérivée ne doit jamais passer pour collectée."
            )

        type_scrutin = scrutin.get("type_scrutin")
        if type_scrutin is not None and type_scrutin not in KNOWN_TYPES_SCRUTIN:
            errors.append(
                f"scrutins[{i}].type_scrutin non reconnu : {type_scrutin!r}. "
                f"Valeurs connues : {sorted(KNOWN_TYPES_SCRUTIN)}."
            )

        type_vote = scrutin.get("type_vote")
        if type_vote is not None and type_vote not in KNOWN_TYPES_VOTE:
            errors.append(
                f"scrutins[{i}].type_vote non reconnu : {type_vote!r}. "
                f"Valeurs connues : {sorted(KNOWN_TYPES_VOTE)}."
            )
        if type_vote == "motion_censure" and not scrutin.get("texte_lie_id"):
            errors.append(
                f"scrutins[{i}] : type_vote='motion_censure' sans 'texte_lie_id' "
                "(le texte 49.3 concerné doit être identifié, jamais fusionné "
                "avec le vote sur le texte)."
            )

    return errors
