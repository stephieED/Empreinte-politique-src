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

Aucune dépendance lourde : stdlib uniquement à ce stade.
"""

import json
import statistics
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
