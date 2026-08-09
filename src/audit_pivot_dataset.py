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

Sous-tâche 4/6 : indicateurs de cohérence (mêmes contraintes de pureté) —
doublons d'`id`, divergence `schema_version`/`meta.schema_version`, dates de
traçabilité invalides ou futures, et cohérence `chambre`/`sources[].type`.

Aucune dépendance lourde : stdlib uniquement à ce stade.
"""

import json
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from schema_pivot import KNOWN_CHAMBRES

# Types de sources attendus par chambre pour compute_coherence_chambre_sources :
# chaque chambre doit avoir déclaré au moins une source de l'un de ces types.
# "PE" utilise "parltrack" (dumps croisés Parltrack/Wikidata, voir
# normalize_parltrack_dumps.py / mep_profile.py) et "europarl" (Open Data
# Portal du Parlement européen, voir normalize_europarl.py) — pas
# "assemblee_nationale", qui désigne le référentiel officiel des acteurs de
# l'Assemblée nationale (chambre "AN" uniquement). "mairie" n'a pas de type de
# source dédié dans KNOWN_SOURCE_TYPES à ce stade et n'est donc jamais
# signalée en incohérence par cette fonction.
MAPPING_CHAMBRE_SOURCES: dict[str, frozenset[str]] = {
    "AN": frozenset({"nosdeputes", "assemblee_nationale"}),
    "Senat": frozenset({"nossenateurs"}),
    "PE": frozenset({"parltrack", "europarl"}),
}

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


def compute_doublons_id(profils: list[dict[str, Any]]) -> dict[str, Any]:
    """Détecte les `id` présents plusieurs fois dans le corpus pivot.

    L'`id` pivot (`"<source>:<identifiant_source>"`) doit être unique : un
    doublon signale une erreur amont de génération ou de fusion. Les profils
    sans `id` (absent ou vide) sont ignorés — ce défaut relève de la
    validation structurelle (`validate_profil`), pas de la cohérence
    inter-profils.

    Returns:
        {"doublons": [{"id": str, "occurrences": int}, ...]}, trié par `id`
        pour un résultat déterministe ; liste vide si aucun doublon.
    """
    occurrences_par_id: dict[str, int] = {}
    for profil in profils:
        id_ = profil.get("id")
        if not id_:
            continue
        occurrences_par_id[id_] = occurrences_par_id.get(id_, 0) + 1

    return {
        "doublons": [
            {"id": id_, "occurrences": occurrences}
            for id_, occurrences in sorted(occurrences_par_id.items())
            if occurrences > 1
        ]
    }


def compute_coherence_schema_version(profils: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare `schema_version` (racine) et `meta.schema_version`.

    Les deux champs doivent porter la même valeur : une divergence signale un
    profil partiellement régénéré (ex. `meta` reconstruit sans mettre à jour
    la racine, ou l'inverse).

    Returns:
        {"profils_incoherents": [{"id":..., "schema_version":...,
                                   "meta_schema_version":...}, ...]}
    """
    profils_incoherents: list[dict[str, Any]] = []

    for profil in profils:
        schema_version = profil.get("schema_version")
        meta = profil.get("meta")
        meta_schema_version = meta.get("schema_version") if isinstance(meta, dict) else None

        if schema_version != meta_schema_version:
            profils_incoherents.append({
                "id": profil.get("id"),
                "schema_version": schema_version,
                "meta_schema_version": meta_schema_version,
            })

    return {"profils_incoherents": profils_incoherents}


def _erreur_date(valeur: Any, maintenant: datetime) -> str | None:
    """Code d'erreur pour `valeur` si ce n'est pas une date ISO-8601 passée valide, sinon `None`."""
    if not isinstance(valeur, str) or not valeur:
        return "format_invalide"

    try:
        parsed = datetime.fromisoformat(valeur.replace("Z", "+00:00"))
    except ValueError:
        return "format_invalide"

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return "date_future" if parsed > maintenant else None


def compute_validite_dates(profils: list[dict[str, Any]]) -> dict[str, Any]:
    """Valide les dates de traçabilité `sources[].synchro_le` et `meta.genere_le`.

    Une date est en défaut si elle n'est pas une chaîne ISO-8601 parseable
    (`datetime.fromisoformat`, suffixe `Z` accepté comme UTC) ou si elle est
    postérieure à l'instant de l'audit — ces deux champs sont générés par le
    pipeline lui-même (pas une donnée source potentiellement manquante), une
    valeur absente ou future y signale toujours une anomalie amont.

    Returns:
        {"dates_invalides": [{"id":..., "champ": "meta.genere_le" |
                               "sources[i].synchro_le", "valeur":...,
                               "erreur": "format_invalide" | "date_future"}, ...]}
    """
    maintenant = datetime.now(timezone.utc)
    dates_invalides: list[dict[str, Any]] = []

    for profil in profils:
        id_ = profil.get("id")

        meta = profil.get("meta")
        meta = meta if isinstance(meta, dict) else {}
        valeur_meta = meta.get("genere_le")
        erreur_meta = _erreur_date(valeur_meta, maintenant)
        if erreur_meta:
            dates_invalides.append({
                "id": id_, "champ": "meta.genere_le", "valeur": valeur_meta, "erreur": erreur_meta,
            })

        sources = profil.get("sources")
        if isinstance(sources, list):
            for i, source in enumerate(sources):
                if not isinstance(source, dict):
                    continue
                valeur_source = source.get("synchro_le")
                erreur_source = _erreur_date(valeur_source, maintenant)
                if erreur_source:
                    dates_invalides.append({
                        "id": id_,
                        "champ": f"sources[{i}].synchro_le",
                        "valeur": valeur_source,
                        "erreur": erreur_source,
                    })

    return {"dates_invalides": dates_invalides}


def compute_coherence_chambre_sources(profils: list[dict[str, Any]]) -> dict[str, Any]:
    """Vérifie la cohérence entre `chambre` et les types de `sources[]` déclarés.

    Chaque chambre attend au moins une source d'un type de référence, voir
    `MAPPING_CHAMBRE_SOURCES` : `"AN"` -> `nosdeputes`/`assemblee_nationale`,
    `"Senat"` -> `nossenateurs`, `"PE"` -> `parltrack`/`europarl`. `"mairie"`
    et `chambre` absente/inconnue n'ont pas de mapping de référence à ce
    stade et ne sont jamais signalées en incohérence par cette fonction.

    Returns:
        {"profils_incoherents": [{"id":..., "chambre":...,
                                   "types_sources": [...]}, ...]}
    """
    profils_incoherents: list[dict[str, Any]] = []

    for profil in profils:
        chambre = profil.get("chambre")
        types_attendus = MAPPING_CHAMBRE_SOURCES.get(chambre)
        if types_attendus is None:
            continue

        sources = profil.get("sources")
        types_sources = (
            [s.get("type") for s in sources if isinstance(s, dict)]
            if isinstance(sources, list) else []
        )

        if not types_attendus.intersection(types_sources):
            profils_incoherents.append({
                "id": profil.get("id"),
                "chambre": chambre,
                "types_sources": types_sources,
            })

    return {"profils_incoherents": profils_incoherents}
