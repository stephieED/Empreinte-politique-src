#!/usr/bin/env python3
"""
audit_pivot_dataset.py — Audit du jeu de données pivot (fondations I/O).

Sous-tâche 1/6 de l'issue #137 (Pipeline audit données). Ce module ne
contient pour l'instant que la couche de chargement des fichiers pivot,
volontairement séparée de la logique de calcul des indicateurs (ajoutée
par les sous-issues suivantes de #137) afin de rester testable
indépendamment : un fichier JSON malformé ne doit jamais interrompre le
scan du répertoire.

Aucune dépendance lourde : stdlib uniquement à ce stade.
"""

import json
from pathlib import Path
from typing import Any


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
