#!/usr/bin/env python3
"""
audit_pivot_dataset.py — Audit du jeu de données pivot.

Sous-tâche 1/6 de l'issue #137 : couche de chargement des fichiers pivot,
volontairement séparée de la logique de calcul des indicateurs afin de
rester testable indépendamment : un fichier JSON malformé ne doit jamais
interrompre le scan du répertoire.

Sous-tâche 2/6 : indicateurs de volumétrie, sous forme de fonctions pures
(liste de profils pivot -> dict sérialisable JSON), sans aucune I/O. Le
rapport JSON/Markdown et la CLI sont ajoutés par une sous-issue dédiée.

Sous-tâche 5/6 : fraîcheur des données (ancienneté de `sources[].synchro_le`)
et agrégation des `meta.warnings[]`, toujours sous forme de fonctions pures
avec une date de référence injectable (jamais de `datetime.now()` en dur)
pour rendre les tests déterministes.

Aucune dépendance lourde : stdlib uniquement à ce stade.
"""

import json
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from schema_pivot import KNOWN_CHAMBRES

# Listes du schéma pivot dont on mesure la volumétrie par profil.
CHAMPS_LISTES_VOLUMETRIE: tuple[str, ...] = (
    "votes", "textes_portes", "amendements", "interventions",
)


def load_pivot_directory(input_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Scanne récursivement `input_dir` à la recherche de fichiers `*.pivot.json`.

    Args:
        input_dir: répertoire racine à scanner (récursif).

    Returns:
        Tuple (profils_valides, erreurs_lecture) :
          - profils_valides : liste des profils pivot chargés avec succès,
            triés par chemin de fichier pour un résultat déterministe.
          - erreurs_lecture : liste de {"fichier": str, "erreur": str} pour
            chaque fichier n'ayant pas pu être chargé (JSON invalide, objet
            racine non-dict, erreur de lecture...). Un fichier problématique
            n'interrompt jamais le scan des suivants.
    """
    profils_valides: list[dict[str, Any]] = []
    erreurs_lecture: list[dict[str, Any]] = []

    for path in sorted(input_dir.rglob("*.pivot.json")):
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

        profils_valides.append(data)

    return profils_valides, erreurs_lecture


def _taille_liste(profil: dict[str, Any], champ: str) -> int:
    """Longueur de `profil[champ]`, `0` si absent ou `null` (donnée manquante)."""
    valeur = profil.get(champ)
    return len(valeur) if valeur else 0


def compute_repartition_chambre(profils: list[dict[str, Any]]) -> dict[str, Any]:
    """Nombre total de profils et répartition par `chambre`.

    Les valeurs de `chambre` hors `KNOWN_CHAMBRES` (dont `null`) sont
    comptées sous la clé `"null"`, pour garantir un rapport toujours
    sérialisable en JSON quelle que soit la donnée manquante.
    """
    repartition: dict[str, int] = {chambre: 0 for chambre in sorted(KNOWN_CHAMBRES)}
    repartition["null"] = 0

    for profil in profils:
        chambre = profil.get("chambre")
        cle = chambre if chambre in KNOWN_CHAMBRES else "null"
        repartition[cle] += 1

    return {
        "total_profils": len(profils),
        "par_chambre": repartition,
    }


def compute_distribution_listes(profils: list[dict[str, Any]]) -> dict[str, Any]:
    """Distribution du nombre d'éléments par profil pour chaque liste métier.

    Pour `votes`, `textes_portes`, `amendements` et `interventions` : min,
    max, médiane, moyenne du nombre d'éléments par profil, et pourcentage
    de profils à 0 élément. Sur une liste de profils vide, toutes les
    statistiques valent `null` (rien à mesurer) sauf `pct_profils_a_zero`
    qui vaut `0.0`.
    """
    distribution: dict[str, Any] = {}

    for champ in CHAMPS_LISTES_VOLUMETRIE:
        tailles = [_taille_liste(profil, champ) for profil in profils]

        if tailles:
            distribution[champ] = {
                "min": min(tailles),
                "max": max(tailles),
                "mediane": statistics.median(tailles),
                "moyenne": round(statistics.mean(tailles), 2),
                "pct_profils_a_zero": round(
                    100 * sum(1 for taille in tailles if taille == 0) / len(tailles), 2
                ),
            }
        else:
            distribution[champ] = {
                "min": None,
                "max": None,
                "mediane": None,
                "moyenne": None,
                "pct_profils_a_zero": 0.0,
            }

    return distribution


def compute_nombre_sources(profils: list[dict[str, Any]]) -> dict[str, Any]:
    """Volumétrie du nombre de `sources[]` déclarées par profil.

    Moyenne du nombre de sources par profil, et pourcentage de profils
    n'ayant déclaré qu'une seule source.
    """
    if not profils:
        return {"moyenne_sources": None, "pct_profils_une_source": 0.0}

    nombres_sources = [_taille_liste(profil, "sources") for profil in profils]

    return {
        "moyenne_sources": round(statistics.mean(nombres_sources), 2),
        "pct_profils_une_source": round(
            100 * sum(1 for n in nombres_sources if n == 1) / len(nombres_sources), 2
        ),
    }


def _parse_synchro_le(valeur: Any) -> datetime | None:
    """Parse une date ISO-8601 `sources[].synchro_le`, `None` si absente/invalide.

    Les dates invalides sont normalement déjà filtrées en amont (#156) ;
    cette fonction reste défensive pour ne jamais lever d'exception ici. Une
    date naïve (sans fuseau) est supposée UTC.
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


def _anciennetes_sources_jours(profil: dict[str, Any], reference_date: datetime) -> list[int]:
    """Anciennetés (en jours) des sources du profil dont `synchro_le` est valide."""
    anciennetes: list[int] = []
    for source in profil.get("sources") or []:
        if not isinstance(source, dict):
            continue
        date_synchro = _parse_synchro_le(source.get("synchro_le"))
        if date_synchro is not None:
            anciennetes.append(_anciennete_jours(date_synchro, reference_date))
    return anciennetes


def compute_fraicheur_sources(
    profils: list[dict[str, Any]], reference_date: datetime | None = None
) -> dict[str, Any]:
    """Ancienneté des sources (`sources[].synchro_le`) par type de source.

    Pour chaque type de source rencontré (`sources[].type`, `"null"` si
    absent), distribution en jours écoulés depuis la dernière synchro : min,
    max, médiane, moyenne. Les sources sans `synchro_le` valide sont ignorées
    (dates déjà filtrées en amont par #156).

    Args:
        profils: liste de profils pivot.
        reference_date: date de référence pour le calcul de l'ancienneté,
            injectable pour des tests déterministes (défaut :
            `datetime.now(timezone.utc)`).

    Returns:
        `{"total_sources_datees": int, "par_type_source": {type: {...}}}`.
        Un type de source absent de `profils` n'apparaît pas dans le résultat.
    """
    reference = reference_date if reference_date is not None else datetime.now(timezone.utc)

    anciennetes_par_type: dict[str, list[int]] = {}
    for profil in profils:
        for source in profil.get("sources") or []:
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


def compute_profils_perimes(
    profils: list[dict[str, Any]],
    staleness_days: int,
    reference_date: datetime | None = None,
) -> list[str]:
    """`id` des profils dont **toutes** les sources ont plus de `staleness_days` jours.

    Un profil sans aucune source dont `synchro_le` est exploitable n'est
    jamais considéré comme périmé (il n'y a rien à mesurer) : seuls les
    profils ayant au moins une source datée, et dont la source la plus
    fraîche dépasse tout de même le seuil, sont retournés.

    Args:
        profils: liste de profils pivot.
        staleness_days: seuil d'ancienneté (en jours) au-delà duquel une
            source est considérée périmée.
        reference_date: date de référence injectable (voir
            `compute_fraicheur_sources`).

    Returns:
        Liste triée des `id` de profils périmés.
    """
    reference = reference_date if reference_date is not None else datetime.now(timezone.utc)

    perimes = []
    for profil in profils:
        anciennetes = _anciennetes_sources_jours(profil, reference)
        if anciennetes and min(anciennetes) > staleness_days:
            perimes.append(profil.get("id"))

    return sorted(perimes)


def _type_warning(warning: str) -> str:
    """Type d'un warning : préfixe avant le premier ':', message complet sinon.

    Convention déjà utilisée dans le dépôt pour les warnings de
    `meta.warnings[]` (voir les constantes `WARNING_PREFIX_*` de
    `candidate_profile.py`, ex. `"identité introuvable : ..."`).
    """
    prefixe, separateur, _ = warning.partition(":")
    return prefixe.strip() if separateur else warning.strip()


def compute_agregation_warnings(profils: list[dict[str, Any]]) -> dict[str, Any]:
    """Compile tous les `meta.warnings[]` des profils par type.

    Le "type" d'un warning est déterminé par `_type_warning` (préfixe avant
    le premier ':').

    Returns:
        `{"total_warnings": int, "par_type": {type: {"frequence": int,
        "ids": [str, ...]}}}`. `frequence` compte chaque occurrence (un
        profil avec deux warnings du même type compte pour 2) ; `ids` liste
        sans doublon les profils concernés par ce type, triés.
    """
    par_type: dict[str, dict[str, Any]] = {}
    total_warnings = 0

    for profil in profils:
        meta = profil.get("meta") or {}
        warnings = meta.get("warnings") or []
        profil_id = profil.get("id")

        for warning in warnings:
            if not isinstance(warning, str) or not warning:
                continue
            total_warnings += 1
            type_warning = _type_warning(warning)
            entree = par_type.setdefault(type_warning, {"frequence": 0, "ids": set()})
            entree["frequence"] += 1
            entree["ids"].add(profil_id)

    return {
        "total_warnings": total_warnings,
        "par_type": {
            type_warning: {
                "frequence": entree["frequence"],
                "ids": sorted(entree["ids"]),
            }
            for type_warning, entree in sorted(par_type.items())
        },
    }
