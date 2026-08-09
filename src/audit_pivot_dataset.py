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
Sous-tâche 4/6 : indicateurs de cohérence (mêmes contraintes de pureté) —
doublons d'`id`, divergence `schema_version`/`meta.schema_version`, dates de
traçabilité invalides ou futures, et cohérence `chambre`/`sources[].type`.
Sous-tâche 3/6 : indicateurs de complétude (taux de remplissage, profils
sans activité, présence des métadonnées `meta`). Mêmes contraintes :
fonctions pures, sans I/O. Une donnée absente ou vide n'est jamais
comptée comme renseignée (AGENTS.md §2.5 : "missing data means missing
data, never default 0").

Sous-tâche 6/6 : CLI (`main()` / `_build_arg_parser()`), assemblage de tous
les indicateurs ci-dessus dans `build_report()` et génération d'un rapport
Markdown lisible par un humain (`generate_markdown_report()`). Ce rapport est
un outil de qualité interne : il ne doit jamais introduire de jugement de
valeur, de score ou de classement (AGENTS.md §2.1).

Aucune dépendance lourde : stdlib uniquement.
"""

import argparse
import json
import statistics
import sys
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

# Champs dont on mesure le taux de remplissage (complétude).
CHAMPS_COMPLETUDE: tuple[str, ...] = ("parti", "groupe", "tags_thematiques", "mandats")

# Listes d'activité : un profil sans aucun élément dans ces trois champs est
# un candidat à un enrichissement manquant.
CHAMPS_ACTIVITE: tuple[str, ...] = ("votes", "amendements", "interventions")


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


def compute_taux_remplissage(profils: list[dict[str, Any]]) -> dict[str, Any]:
    """Taux de remplissage de `parti`, `groupe`, `tags_thematiques`, `mandats`.

    Pour chaque champ : nombre de profils où il est renseigné (ni absent,
    ni `null`, ni chaîne/liste vide), sur le total de profils. Sur une
    liste de profils vide, `taux_pct` vaut `0.0` (rien à mesurer).
    """
    total = len(profils)
    resultat: dict[str, Any] = {}

    for champ in CHAMPS_COMPLETUDE:
        renseignes = sum(1 for profil in profils if _est_renseigne(profil.get(champ)))
        resultat[champ] = {
            "renseignes": renseignes,
            "total": total,
            "taux_pct": round(100 * renseignes / total, 2) if total else 0.0,
        }

    return resultat


def compute_profils_sans_activite(profils: list[dict[str, Any]]) -> dict[str, Any]:
    """Profils sans aucun élément dans `votes`, `amendements` ou `interventions`.

    Ces profils sont des candidats à un enrichissement manquant. Un champ
    absent ou `null` compte comme "aucun élément", au même titre qu'une
    liste vide.
    """
    ids = [
        profil.get("id")
        for profil in profils
        if all(_taille_liste(profil, champ) == 0 for champ in CHAMPS_ACTIVITE)
    ]

    return {
        "total_profils": len(profils),
        "nb_profils_sans_activite": len(ids),
        "profils_sans_activite": ids,
    }


def compute_presence_meta(profils: list[dict[str, Any]]) -> dict[str, Any]:
    """Présence et non-vacuité de `meta.licence_donnees` et `meta.genere_le`.

    Un `meta` absent ou de mauvais type compte comme un défaut pour les
    deux champs. Retourne la liste des `id` en défaut pour chaque critère,
    afin de cibler précisément les profils à corriger.
    """
    ids_meta_absente: list[Any] = []
    ids_licence_manquante: list[Any] = []
    ids_genere_le_manquant: list[Any] = []

    for profil in profils:
        identifiant = profil.get("id")
        meta = profil.get("meta")

        if not isinstance(meta, dict):
            ids_meta_absente.append(identifiant)
            ids_licence_manquante.append(identifiant)
            ids_genere_le_manquant.append(identifiant)
            continue

        if not _est_renseigne(meta.get("licence_donnees")):
            ids_licence_manquante.append(identifiant)

        if not _est_renseigne(meta.get("genere_le")):
            ids_genere_le_manquant.append(identifiant)

    return {
        "total_profils": len(profils),
        "meta_absente": ids_meta_absente,
        "licence_donnees_manquante": ids_licence_manquante,
        "genere_le_manquant": ids_genere_le_manquant,
    }


# ---------------------------------------------------------------------------
# Assemblage du rapport (sous-tâche 6/6)
# ---------------------------------------------------------------------------

def build_report(
    profils: list[dict[str, Any]],
    erreurs_lecture: list[dict[str, Any]],
    staleness_days: int = 30,
    reference_date: datetime | None = None,
) -> dict[str, Any]:
    """Assemble tous les indicateurs `compute_*` en un rapport structuré unique.

    Args:
        profils: profils pivot valides (sortie de `load_pivot_directory`).
        erreurs_lecture: erreurs de lecture (sortie de `load_pivot_directory`).
        staleness_days: seuil d'ancienneté en jours pour `compute_profils_perimes`
            (défaut : 30).
        reference_date: date de référence injectable pour les indicateurs de
            fraîcheur, voir `compute_fraicheur_sources` (défaut :
            `datetime.now(timezone.utc)`).

    Returns:
        Dict sérialisable JSON, une section par catégorie d'indicateur
        (`volumetrie`, `completude`, `coherence`, `fraicheur`, `warnings`) plus
        `meta` et `erreurs_lecture`. Un outil de qualité interne : ce rapport
        ne doit jamais introduire de jugement de valeur, de score ou de
        classement (AGENTS.md §2.1).
    """
    reference = reference_date if reference_date is not None else datetime.now(timezone.utc)

    return {
        "meta": {
            "genere_le": reference.isoformat(),
            "total_profils": len(profils),
            "total_erreurs_lecture": len(erreurs_lecture),
            "staleness_days": staleness_days,
        },
        "volumetrie": {
            "repartition_chambre": compute_repartition_chambre(profils),
            "distribution_listes": compute_distribution_listes(profils),
            "nombre_sources": compute_nombre_sources(profils),
        },
        "completude": {
            "taux_remplissage": compute_taux_remplissage(profils),
            "profils_sans_activite": compute_profils_sans_activite(profils),
            "presence_meta": compute_presence_meta(profils),
        },
        "coherence": {
            "doublons_id": compute_doublons_id(profils),
            "coherence_schema_version": compute_coherence_schema_version(profils),
            "validite_dates": compute_validite_dates(profils),
            "coherence_chambre_sources": compute_coherence_chambre_sources(profils),
        },
        "fraicheur": {
            "fraicheur_sources": compute_fraicheur_sources(profils, reference_date=reference),
            "profils_perimes": compute_profils_perimes(
                profils, staleness_days=staleness_days, reference_date=reference
            ),
        },
        "warnings": compute_agregation_warnings(profils),
        "erreurs_lecture": erreurs_lecture,
    }


# ---------------------------------------------------------------------------
# Génération du rapport Markdown
# ---------------------------------------------------------------------------

def _md_escape(valeur: Any) -> str:
    """Neutralise les caractères cassant une cellule de tableau Markdown."""
    texte = "" if valeur is None else str(valeur)
    return texte.replace("|", "\\|").replace("\n", " ")


def _md_table(en_tetes: list[str], lignes: list[list[Any]], si_vide: str) -> str:
    """Construit un tableau Markdown, ou renvoie `si_vide` si `lignes` est vide."""
    if not lignes:
        return si_vide + "\n"

    entete = "| " + " | ".join(en_tetes) + " |"
    separateur = "| " + " | ".join("---" for _ in en_tetes) + " |"
    corps = "\n".join(
        "| " + " | ".join(_md_escape(cellule) for cellule in ligne) + " |" for ligne in lignes
    )
    return f"{entete}\n{separateur}\n{corps}\n"


def _md_section_volumetrie(volumetrie: dict[str, Any]) -> str:
    par_chambre = volumetrie["repartition_chambre"]["par_chambre"]
    lignes_chambre = [[chambre, effectif] for chambre, effectif in par_chambre.items()]

    lignes_listes = [
        [
            champ,
            stats["min"], stats["max"], stats["mediane"], stats["moyenne"],
            stats["pct_profils_a_zero"],
        ]
        for champ, stats in volumetrie["distribution_listes"].items()
    ]

    sources = volumetrie["nombre_sources"]

    return (
        "## Volumétrie\n\n"
        f"Total profils : {volumetrie['repartition_chambre']['total_profils']}\n\n"
        "### Répartition par chambre\n\n"
        + _md_table(["Chambre", "Profils"], lignes_chambre, "Aucun profil.")
        + "\n### Distribution des listes métier (par profil)\n\n"
        + _md_table(
            ["Champ", "Min", "Max", "Médiane", "Moyenne", "% profils à 0"],
            lignes_listes, "Aucun profil.",
        )
        + "\n### Sources déclarées\n\n"
        + _md_table(
            ["Moyenne de sources par profil", "% profils à une seule source"],
            [[sources["moyenne_sources"], sources["pct_profils_une_source"]]],
            "Aucun profil.",
        )
    )


def _md_section_completude(completude: dict[str, Any]) -> str:
    lignes_remplissage = [
        [champ, stats["renseignes"], stats["total"], stats["taux_pct"]]
        for champ, stats in completude["taux_remplissage"].items()
    ]

    sans_activite = completude["profils_sans_activite"]
    presence_meta = completude["presence_meta"]
    lignes_presence_meta = [
        ["meta absente", len(presence_meta["meta_absente"])],
        ["licence_donnees manquante", len(presence_meta["licence_donnees_manquante"])],
        ["genere_le manquant", len(presence_meta["genere_le_manquant"])],
    ]

    return (
        "## Complétude\n\n"
        "### Taux de remplissage\n\n"
        + _md_table(
            ["Champ", "Renseignés", "Total", "Taux (%)"],
            lignes_remplissage, "Aucun profil.",
        )
        + "\n### Profils sans activité (aucun vote, amendement ni intervention)\n\n"
        f"{sans_activite['nb_profils_sans_activite']} / {sans_activite['total_profils']} profil(s).\n\n"
        "### Présence des métadonnées\n\n"
        + _md_table(
            ["Critère", f"Profils en défaut (sur {presence_meta['total_profils']})"],
            lignes_presence_meta, "Aucun profil.",
        )
    )


def _md_section_coherence(coherence: dict[str, Any]) -> str:
    lignes_doublons = [
        [d["id"], d["occurrences"]] for d in coherence["doublons_id"]["doublons"]
    ]
    lignes_schema = [
        [p["id"], p["schema_version"], p["meta_schema_version"]]
        for p in coherence["coherence_schema_version"]["profils_incoherents"]
    ]
    lignes_dates = [
        [d["id"], d["champ"], d["valeur"], d["erreur"]]
        for d in coherence["validite_dates"]["dates_invalides"]
    ]
    lignes_chambre_sources = [
        [p["id"], p["chambre"], ", ".join(t or "null" for t in p["types_sources"]) or "—"]
        for p in coherence["coherence_chambre_sources"]["profils_incoherents"]
    ]

    return (
        "## Cohérence\n\n"
        "### Doublons d'`id`\n\n"
        + _md_table(["id", "Occurrences"], lignes_doublons, "Aucun doublon détecté.")
        + "\n### Divergence `schema_version` / `meta.schema_version`\n\n"
        + _md_table(
            ["id", "schema_version", "meta.schema_version"],
            lignes_schema, "Aucune divergence détectée.",
        )
        + "\n### Dates de traçabilité invalides ou futures\n\n"
        + _md_table(["id", "Champ", "Valeur", "Erreur"], lignes_dates, "Aucune date invalide détectée.")
        + "\n### Cohérence `chambre` / types de `sources[]`\n\n"
        + _md_table(
            ["id", "Chambre", "Types de sources déclarés"],
            lignes_chambre_sources, "Aucune incohérence détectée.",
        )
    )


def _md_section_fraicheur(fraicheur: dict[str, Any], staleness_days: int) -> str:
    lignes_fraicheur = [
        [
            type_source, stats["nombre_sources"],
            stats["min_jours"], stats["max_jours"], stats["mediane_jours"], stats["moyenne_jours"],
        ]
        for type_source, stats in fraicheur["fraicheur_sources"]["par_type_source"].items()
    ]

    profils_perimes = fraicheur["profils_perimes"]
    lignes_perimes = [[id_] for id_ in profils_perimes]

    return (
        "## Fraîcheur\n\n"
        "### Ancienneté des sources par type (jours écoulés depuis `synchro_le`)\n\n"
        + _md_table(
            ["Type de source", "Nombre de sources", "Min", "Max", "Médiane", "Moyenne"],
            lignes_fraicheur, "Aucune source datée.",
        )
        + f"\n### Profils périmés (toutes sources > {staleness_days} jours)\n\n"
        + _md_table(["id"], lignes_perimes, "Aucun profil périmé.")
    )


def _md_section_warnings(warnings: dict[str, Any]) -> str:
    lignes = [
        [type_warning, entree["frequence"], ", ".join(entree["ids"])]
        for type_warning, entree in warnings["par_type"].items()
    ]

    return (
        "## Warnings\n\n"
        f"Total : {warnings['total_warnings']}\n\n"
        + _md_table(["Type", "Fréquence", "Profils concernés"], lignes, "Aucun warning.")
    )


def _md_section_erreurs_lecture(erreurs_lecture: list[dict[str, Any]]) -> str:
    lignes = [[e["fichier"], e["erreur"]] for e in erreurs_lecture]

    return (
        "## Erreurs de lecture\n\n"
        + _md_table(["Fichier", "Erreur"], lignes, "Aucune erreur de lecture.")
    )


def generate_markdown_report(rapport: dict[str, Any]) -> str:
    """Génère un rapport Markdown lisible par un humain à partir du dict `build_report`.

    Une section par catégorie d'indicateur, sous forme de tableaux synthétiques.
    Aucun score ni classement n'est calculé : ce rapport présente les chiffres
    bruts produits par les fonctions `compute_*` (AGENTS.md §2.1).
    """
    meta = rapport["meta"]

    sections = [
        (
            "# Rapport d'audit du jeu de données pivot\n\n"
            f"Généré le {meta['genere_le']}. "
            f"{meta['total_profils']} profil(s) analysé(s), "
            f"{meta['total_erreurs_lecture']} erreur(s) de lecture. "
            f"Seuil de péremption des sources : {meta['staleness_days']} jour(s).\n\n"
            "Ce rapport est un outil de qualité interne : il présente des "
            "indicateurs bruts, sans jugement de valeur ni classement.\n"
        ),
        _md_section_volumetrie(rapport["volumetrie"]),
        _md_section_completude(rapport["completude"]),
        _md_section_coherence(rapport["coherence"]),
        _md_section_fraicheur(rapport["fraicheur"], meta["staleness_days"]),
        _md_section_warnings(rapport["warnings"]),
        _md_section_erreurs_lecture(rapport["erreurs_lecture"]),
    ]

    return "\n".join(sections)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="audit_pivot_dataset.py",
        description=(
            "Audite un jeu de données pivot : volumétrie, complétude, cohérence, "
            "fraîcheur des sources et warnings agrégés. Outil de qualité interne, "
            "ne produit aucun score ni classement."
        ),
    )
    parser.add_argument(
        "--input-dir",
        required=True,
        metavar="DOSSIER",
        help="Dossier contenant les fichiers *.pivot.json à auditer (scan récursif).",
    )
    parser.add_argument(
        "--output-json",
        default=None,
        metavar="FICHIER",
        help="Chemin du rapport JSON (défaut : affiché sur stdout).",
    )
    parser.add_argument(
        "--output-md",
        default=None,
        metavar="FICHIER",
        help="Chemin du rapport Markdown (défaut : non généré).",
    )
    parser.add_argument(
        "--staleness-days",
        type=int,
        default=30,
        metavar="JOURS",
        help="Seuil d'ancienneté (jours) au-delà duquel un profil est périmé (défaut : 30).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    input_dir = Path(args.input_dir)
    if not input_dir.is_dir():
        print(f"[!] Dossier introuvable : {input_dir}", file=sys.stderr)
        return 1

    profils, erreurs_lecture = load_pivot_directory(input_dir)
    print(
        f"→ {len(profils)} profil(s) chargé(s), {len(erreurs_lecture)} erreur(s) de lecture.",
        file=sys.stderr,
    )

    rapport = build_report(profils, erreurs_lecture, staleness_days=args.staleness_days)
    output_json = json.dumps(rapport, ensure_ascii=False, indent=2)

    if args.output_json:
        out_path = Path(args.output_json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output_json, encoding="utf-8")
        print(f"  ✓ Rapport JSON écrit : {out_path}", file=sys.stderr)
    else:
        print(output_json)

    if args.output_md:
        md_path = Path(args.output_md)
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(generate_markdown_report(rapport), encoding="utf-8")
        print(f"  ✓ Rapport Markdown écrit : {md_path}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
