#!/usr/bin/env python3
"""
audit_groupe_dataset.py — Audit du jeu de données groupes (pivot_data/groupes).

Miroir de `audit_pivot_dataset.py` (issue #137) pour les profils de groupe
agrégés (`schema_groupe.py`), voir issue #176 (plan #174). Couche de
chargement (`load_groupe_directory`) volontairement séparée de la logique de
calcul des indicateurs, pour rester testable indépendamment : un fichier
JSON malformé ne doit jamais interrompre le scan du répertoire.

Indicateurs sous forme de fonctions pures (liste de profils de groupe ->
dict sérialisable JSON), sans aucune I/O :
  - volumétrie : effectifs, nombre de `cohesion_votes`, distribution des
    `amendements_agreges` (global + `par_type_deposant`) ;
  - complétude : présence de `tags_thematiques_agreges`, groupes avec des
    membres mais 0 `cohesion_votes` ;
  - cohérence : validation `schema_groupe.validate_profil_groupe`, divergence
    `schema_version`/`meta.schema_version`, écart
    `couverture_roster.profils_disponibles`/`roster_total`, doublons de
    `groupe_id` ;
  - fraîcheur : ancienneté de `sources[].synchro_le` ;
  - agrégation des `meta.warnings[]` par fichier.

Pas encore de CLI ni de `build_report()`/rapport Markdown à ce stade (voir
sous-issue suivante) — un `id` manquant, une donnée absente ou vide n'est
jamais comptée comme renseignée (AGENTS.md §2.5 : "missing data means
missing data, never default 0").

Aucune dépendance lourde : stdlib uniquement.
"""

import json
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from schema_groupe import AMENDEMENTS_TYPES_DEPOSANT, validate_profil_groupe

# Sous-champs de `effectif` dont on mesure la distribution.
CHAMPS_EFFECTIF: tuple[str, ...] = ("actuel", "min_historique", "max_historique")

# Compteurs de `amendements_agreges` (bloc global et chaque bloc de
# `par_type_deposant`) dont on mesure la distribution.
CHAMPS_AMENDEMENTS: tuple[str, ...] = (
    "nb_amendements", "nb_adoptes", "nb_rejetes", "nb_irrecevables", "nb_retires_ou_tombes",
)


def load_groupe_directory(input_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Scanne récursivement `input_dir` à la recherche de fichiers `*.json`.

    Args:
        input_dir: répertoire racine à scanner (récursif).

    Returns:
        Tuple (groupes_valides, erreurs_lecture) :
          - groupes_valides : liste des profils de groupe chargés avec
            succès, triés par chemin de fichier pour un résultat
            déterministe.
          - erreurs_lecture : liste de {"fichier": str, "erreur": str} pour
            chaque fichier n'ayant pas pu être chargé (JSON invalide, objet
            racine non-dict, erreur de lecture...). Un fichier problématique
            n'interrompt jamais le scan des suivants.
    """
    groupes_valides: list[dict[str, Any]] = []
    erreurs_lecture: list[dict[str, Any]] = []

    for path in sorted(input_dir.rglob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            erreurs_lecture.append({"fichier": str(path), "erreur": str(exc)})
            continue

        if not isinstance(data, dict):
            erreurs_lecture.append({
                "fichier": str(path),
                "erreur": f"Attendu un objet JSON, reçu {type(data).__name__}.",
            })
            continue

        groupes_valides.append(data)

    return groupes_valides, erreurs_lecture


def _taille_liste(groupe: dict[str, Any], champ: str) -> int:
    """Longueur de `groupe[champ]`, `0` si absent ou `null` (donnée manquante)."""
    valeur = groupe.get(champ)
    return len(valeur) if valeur else 0


def _est_renseigne(valeur: Any) -> bool:
    """True si `valeur` est une donnée renseignée.

    `None`, chaîne vide et liste vide comptent comme non renseignés — une
    chaîne/liste vide est une absence de donnée déguisée, jamais un
    remplissage valide (AGENTS.md §2.5).
    """
    if valeur is None:
        return False
    if isinstance(valeur, (str, list)):
        return len(valeur) > 0
    return True


def _stats_entiers(valeurs: list[int]) -> dict[str, Any]:
    """Min/max/médiane/moyenne d'une liste d'entiers, `None` partout si vide."""
    if not valeurs:
        return {"min": None, "max": None, "mediane": None, "moyenne": None}

    return {
        "min": min(valeurs),
        "max": max(valeurs),
        "mediane": statistics.median(valeurs),
        "moyenne": round(statistics.mean(valeurs), 2),
    }


# ---------------------------------------------------------------------------
# Volumétrie
# ---------------------------------------------------------------------------

def compute_effectifs(groupes: list[dict[str, Any]]) -> dict[str, Any]:
    """Distribution de `effectif.actuel`/`min_historique`/`max_historique`.

    Pour chaque sous-champ, min/max/médiane/moyenne sur les groupes où la
    valeur est un entier renseigné. `min_historique`/`max_historique` sont
    souvent `null` (historique non calculé, voir `schema_groupe.py`) : un
    `null` est exclu du calcul, jamais compté comme `0`
    (AGENTS.md §2.5).

    Returns:
        `{champ: {"nombre_groupes_renseignes": int, "min":..., "max":...,
        "mediane":..., "moyenne":...}}` pour chaque champ de
        `CHAMPS_EFFECTIF`.
    """
    resultat: dict[str, Any] = {}

    for champ in CHAMPS_EFFECTIF:
        valeurs = []
        for groupe in groupes:
            effectif = groupe.get("effectif")
            if not isinstance(effectif, dict):
                continue
            valeur = effectif.get(champ)
            if isinstance(valeur, int) and not isinstance(valeur, bool):
                valeurs.append(valeur)

        resultat[champ] = {
            "nombre_groupes_renseignes": len(valeurs),
            **_stats_entiers(valeurs),
        }

    return resultat


def compute_nombre_cohesion_votes(groupes: list[dict[str, Any]]) -> dict[str, Any]:
    """Distribution du nombre de `cohesion_votes` par groupe.

    Min, max, médiane, moyenne du nombre de scrutins recensés par groupe, et
    pourcentage de groupes sans aucun scrutin. Sur une liste de groupes
    vide, toutes les statistiques valent `null` sauf `pct_groupes_a_zero`
    qui vaut `0.0`.
    """
    tailles = [_taille_liste(groupe, "cohesion_votes") for groupe in groupes]

    if not tailles:
        return {"min": None, "max": None, "mediane": None, "moyenne": None, "pct_groupes_a_zero": 0.0}

    return {
        **_stats_entiers(tailles),
        "pct_groupes_a_zero": round(100 * sum(1 for taille in tailles if taille == 0) / len(tailles), 2),
    }


def _valeurs_champ_amendements(groupes: list[dict[str, Any]], champ: str, type_deposant: str | None) -> list[int]:
    """Valeurs entières de `champ` dans `amendements_agreges` (globales ou par type de déposant)."""
    valeurs = []
    for groupe in groupes:
        amendements = groupe.get("amendements_agreges")
        if not isinstance(amendements, dict):
            continue

        bloc = amendements
        if type_deposant is not None:
            par_type = amendements.get("par_type_deposant")
            bloc = par_type.get(type_deposant) if isinstance(par_type, dict) else None

        if not isinstance(bloc, dict):
            continue

        valeur = bloc.get(champ)
        if isinstance(valeur, int) and not isinstance(valeur, bool):
            valeurs.append(valeur)

    return valeurs


def compute_distribution_amendements(groupes: list[dict[str, Any]]) -> dict[str, Any]:
    """Distribution des compteurs de `amendements_agreges`, global et par type de déposant.

    Pour chaque compteur de `CHAMPS_AMENDEMENTS` (`nb_amendements`,
    `nb_adoptes`, `nb_rejetes`, `nb_irrecevables`, `nb_retires_ou_tombes`) :
    min/max/médiane/moyenne sur l'ensemble des groupes, à la fois pour le
    bloc global et pour chaque type de déposant connu
    (`schema_groupe.AMENDEMENTS_TYPES_DEPOSANT`, incluant `"inconnu"`) —
    ne jamais agréger les taux d'adoption entre types de déposants
    (AGENTS.md §5 : `type_deposant`).

    Returns:
        `{"global": {champ: {...}}, "par_type_deposant": {type: {champ: {...}}}}`.
    """
    return {
        "global": {
            champ: _stats_entiers(_valeurs_champ_amendements(groupes, champ, None))
            for champ in CHAMPS_AMENDEMENTS
        },
        "par_type_deposant": {
            type_deposant: {
                champ: _stats_entiers(_valeurs_champ_amendements(groupes, champ, type_deposant))
                for champ in CHAMPS_AMENDEMENTS
            }
            for type_deposant in sorted(AMENDEMENTS_TYPES_DEPOSANT)
        },
    }


# ---------------------------------------------------------------------------
# Complétude
# ---------------------------------------------------------------------------

def compute_presence_tags_thematiques(groupes: list[dict[str, Any]]) -> dict[str, Any]:
    """Taux de remplissage de `tags_thematiques_agreges`.

    Nombre de groupes où le champ est renseigné (ni absent, ni `null`, ni
    liste vide), sur le total de groupes. `taux_pct` vaut `0.0` sur une
    liste de groupes vide (rien à mesurer).
    """
    total = len(groupes)
    renseignes = sum(1 for groupe in groupes if _est_renseigne(groupe.get("tags_thematiques_agreges")))

    return {
        "renseignes": renseignes,
        "total": total,
        "taux_pct": round(100 * renseignes / total, 2) if total else 0.0,
    }


def compute_groupes_membres_sans_cohesion(groupes: list[dict[str, Any]]) -> dict[str, Any]:
    """Groupes ayant au moins un membre mais aucun `cohesion_votes`.

    Ces groupes sont des candidats à un enrichissement manquant (agrégation
    de cohésion non calculée alors que des profils individuels sont
    disponibles).
    """
    ids = [
        groupe.get("groupe_id")
        for groupe in groupes
        if _taille_liste(groupe, "membres") > 0 and _taille_liste(groupe, "cohesion_votes") == 0
    ]

    return {
        "total_groupes": len(groupes),
        "nb_groupes_membres_sans_cohesion": len(ids),
        "groupes_membres_sans_cohesion": ids,
    }


# ---------------------------------------------------------------------------
# Cohérence
# ---------------------------------------------------------------------------

def compute_validation_schema(groupes: list[dict[str, Any]]) -> dict[str, Any]:
    """Agrège les résultats de `schema_groupe.validate_profil_groupe` sur le corpus.

    Returns:
        `{"total_groupes": int, "nb_groupes_invalides": int,
        "groupes_invalides": [{"groupe_id":..., "erreurs": [str, ...]}, ...]}`,
        triés par `groupe_id` pour un résultat déterministe.
    """
    groupes_invalides = [
        {"groupe_id": groupe.get("groupe_id"), "erreurs": erreurs}
        for groupe in groupes
        for erreurs in [validate_profil_groupe(groupe)]
        if erreurs
    ]
    groupes_invalides.sort(key=lambda entree: (entree["groupe_id"] is None, entree["groupe_id"]))

    return {
        "total_groupes": len(groupes),
        "nb_groupes_invalides": len(groupes_invalides),
        "groupes_invalides": groupes_invalides,
    }


def compute_coherence_schema_version(groupes: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare `schema_version` (racine) et `meta.schema_version`.

    Les deux champs doivent porter la même valeur : une divergence signale
    un profil de groupe partiellement régénéré (ex. `meta` reconstruit sans
    mettre à jour la racine, ou l'inverse).

    Returns:
        `{"groupes_incoherents": [{"groupe_id":..., "schema_version":...,
        "meta_schema_version":...}, ...]}`
    """
    groupes_incoherents: list[dict[str, Any]] = []

    for groupe in groupes:
        schema_version = groupe.get("schema_version")
        meta = groupe.get("meta")
        meta_schema_version = meta.get("schema_version") if isinstance(meta, dict) else None

        if schema_version != meta_schema_version:
            groupes_incoherents.append({
                "groupe_id": groupe.get("groupe_id"),
                "schema_version": schema_version,
                "meta_schema_version": meta_schema_version,
            })

    return {"groupes_incoherents": groupes_incoherents}


def compute_ecart_couverture_roster(groupes: list[dict[str, Any]]) -> dict[str, Any]:
    """Écart entre `meta.couverture_roster.profils_disponibles` et `roster_total`.

    `couverture_roster` est optionnel — présent seulement pour les groupes
    construits via `group_profile.py --from-roster` (voir `schema_groupe.py`).
    Un groupe sans ce bloc, ou avec des valeurs non entières, n'est jamais
    inclus : il n'y a rien à mesurer.

    Returns:
        `{"groupes": [{"groupe_id":..., "roster_total":...,
        "profils_disponibles":..., "ecart": int}, ...]}`, `ecart` =
        `roster_total - profils_disponibles`, triés par `groupe_id`.
    """
    resultat: list[dict[str, Any]] = []

    for groupe in groupes:
        meta = groupe.get("meta")
        couverture = meta.get("couverture_roster") if isinstance(meta, dict) else None
        if not isinstance(couverture, dict):
            continue

        roster_total = couverture.get("roster_total")
        profils_disponibles = couverture.get("profils_disponibles")
        if not isinstance(roster_total, int) or not isinstance(profils_disponibles, int):
            continue
        if isinstance(roster_total, bool) or isinstance(profils_disponibles, bool):
            continue

        resultat.append({
            "groupe_id": groupe.get("groupe_id"),
            "roster_total": roster_total,
            "profils_disponibles": profils_disponibles,
            "ecart": roster_total - profils_disponibles,
        })

    resultat.sort(key=lambda entree: (entree["groupe_id"] is None, entree["groupe_id"]))
    return {"groupes": resultat}


def compute_doublons_groupe_id(groupes: list[dict[str, Any]]) -> dict[str, Any]:
    """Détecte les `groupe_id` présents plusieurs fois dans le corpus.

    Le `groupe_id` (`"<chambre>:<sigle>"`) doit être unique : un doublon
    signale une erreur amont de génération. Les groupes sans `groupe_id`
    (absent ou vide) sont ignorés — ce défaut relève de la validation
    structurelle (`validate_profil_groupe`), pas de la cohérence
    inter-groupes.

    Returns:
        `{"doublons": [{"groupe_id": str, "occurrences": int}, ...]}`, trié
        par `groupe_id` pour un résultat déterministe ; liste vide si aucun
        doublon.
    """
    occurrences_par_id: dict[str, int] = {}
    for groupe in groupes:
        groupe_id = groupe.get("groupe_id")
        if not groupe_id:
            continue
        occurrences_par_id[groupe_id] = occurrences_par_id.get(groupe_id, 0) + 1

    return {
        "doublons": [
            {"groupe_id": groupe_id, "occurrences": occurrences}
            for groupe_id, occurrences in sorted(occurrences_par_id.items())
            if occurrences > 1
        ]
    }


# ---------------------------------------------------------------------------
# Fraîcheur
# ---------------------------------------------------------------------------

def _parse_synchro_le(valeur: Any) -> datetime | None:
    """Parse une date ISO-8601 `sources[].synchro_le`, `None` si absente/invalide.

    Une date naïve (sans fuseau) est supposée UTC.
    """
    if not isinstance(valeur, str) or not valeur:
        return None

    texte = valeur[:-1] + "+00:00" if valeur.endswith("Z") else valeur
    try:
        date_synchro = datetime.fromisoformat(texte)
    except ValueError:
        return None

    return date_synchro if date_synchro.tzinfo is not None else date_synchro.replace(tzinfo=timezone.utc)


def _anciennete_jours(date_synchro: datetime, reference_date: datetime) -> int:
    """Nombre de jours écoulés entre `date_synchro` et `reference_date`."""
    return (reference_date - date_synchro).days


def compute_fraicheur_sources(
    groupes: list[dict[str, Any]], reference_date: datetime | None = None
) -> dict[str, Any]:
    """Ancienneté des sources (`sources[].synchro_le`) par type de source.

    Pour chaque type de source rencontré (`sources[].type`, `"null"` si
    absent), distribution en jours écoulés depuis la dernière synchro : min,
    max, médiane, moyenne. Les sources sans `synchro_le` valide sont
    ignorées.

    Args:
        groupes: liste de profils de groupe.
        reference_date: date de référence pour le calcul de l'ancienneté,
            injectable pour des tests déterministes (défaut :
            `datetime.now(timezone.utc)`).

    Returns:
        `{"total_sources_datees": int, "par_type_source": {type: {...}}}`.
        Un type de source absent de `groupes` n'apparaît pas dans le résultat.
    """
    reference = reference_date if reference_date is not None else datetime.now(timezone.utc)

    anciennetes_par_type: dict[str, list[int]] = {}
    for groupe in groupes:
        for source in groupe.get("sources") or []:
            if not isinstance(source, dict):
                continue
            date_synchro = _parse_synchro_le(source.get("synchro_le"))
            if date_synchro is None:
                continue
            type_source = source.get("type") or "null"
            anciennetes_par_type.setdefault(type_source, []).append(
                _anciennete_jours(date_synchro, reference)
            )

    par_type_source: dict[str, Any] = {}
    for type_source in sorted(anciennetes_par_type):
        anciennetes = anciennetes_par_type[type_source]
        par_type_source[type_source] = {
            "nombre_sources": len(anciennetes),
            "min_jours": min(anciennetes),
            "max_jours": max(anciennetes),
            "mediane_jours": statistics.median(anciennetes),
            "moyenne_jours": round(statistics.mean(anciennetes), 2),
        }

    return {
        "total_sources_datees": sum(len(v) for v in anciennetes_par_type.values()),
        "par_type_source": par_type_source,
    }


# ---------------------------------------------------------------------------
# Agrégation des warnings
# ---------------------------------------------------------------------------

def _type_warning(warning: str) -> str:
    """Type d'un warning : préfixe avant le premier ':', message complet sinon."""
    prefixe, separateur, _ = warning.partition(":")
    return prefixe.strip() if separateur else warning.strip()


def compute_agregation_warnings(groupes: list[dict[str, Any]]) -> dict[str, Any]:
    """Compile tous les `meta.warnings[]` des groupes par type.

    Le "type" d'un warning est déterminé par `_type_warning` (préfixe avant
    le premier ':').

    Returns:
        `{"total_warnings": int, "par_type": {type: {"frequence": int,
        "groupe_ids": [str, ...]}}}`. `frequence` compte chaque occurrence
        (un groupe avec deux warnings du même type compte pour 2) ;
        `groupe_ids` liste sans doublon les groupes concernés par ce type,
        triés.
    """
    par_type: dict[str, dict[str, Any]] = {}
    total_warnings = 0

    for groupe in groupes:
        meta = groupe.get("meta") or {}
        warnings = meta.get("warnings") or []
        groupe_id = groupe.get("groupe_id")

        for warning in warnings:
            if not isinstance(warning, str) or not warning:
                continue
            total_warnings += 1
            type_warning = _type_warning(warning)
            entree = par_type.setdefault(type_warning, {"frequence": 0, "groupe_ids": set()})
            entree["frequence"] += 1
            entree["groupe_ids"].add(groupe_id)

    return {
        "total_warnings": total_warnings,
        "par_type": {
            type_warning: {
                "frequence": entree["frequence"],
                "groupe_ids": sorted(entree["groupe_ids"]),
            }
            for type_warning, entree in sorted(par_type.items())
        },
    }
