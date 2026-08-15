#!/usr/bin/env python3
"""
audit_gouvernement_dataset.py — Audit du jeu de données gouvernements
(pivot_data/gouvernements).

Structure jumelle de `audit_groupe_dataset.py` (lui-même jumeau de
`audit_pivot_dataset.py`), pour les profils de gouvernement agrégés
(`schema_gouvernement.py`), voir issue #319 (sous-issue 3/6 de #316). Couche
de chargement (`load_gouvernement_directory`) volontairement séparée de la
logique de calcul des indicateurs, pour rester testable indépendamment : un
fichier JSON malformé ne doit jamais interrompre le scan du répertoire.

Indicateurs sous forme de fonctions pures (liste de profils de gouvernement
-> dict sérialisable JSON), sans aucune I/O :
  - volumétrie : nombre de gouvernements, répartition par `periode.actif`,
    distribution de `len(membres)` / `len(textes)`, `comptages.par_statut`
    agrégé tous gouvernements confondus ;
  - complétude : présence de `premier_ministre`, taux de
    `membres[].portefeuille` renseigné, présence des métadonnées `meta` ;
  - cohérence : validation `schema_gouvernement.validate_profil_gouvernement`
    (couvre déjà l'invariant du 49.3, non redupliqué ici), divergence
    `schema_version`/`meta.schema_version`, doublons de `gouvernement_id` ;
  - fraîcheur : ancienneté de `sources[].synchro_le`, gouvernements périmés
    (`compute_gouvernements_perimes`, seuil `staleness_days` injectable), même
    logique que les deux scripts existants.

`build_report()` assemble tous ces indicateurs en un rapport structuré
unique, sérialisable en JSON. Pas de CLI ni de rendu Markdown dans ce
fichier : la couche présentation (CLI, rapport Markdown, tableau croisé des
plages temporelles) est hors périmètre de cette sous-issue, réservée à la
sous-issue 4 de #316.

Aucune dépendance lourde : stdlib uniquement.
"""

import json
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from schema_gouvernement import make_empty_comptages_statuts, validate_profil_gouvernement


def load_gouvernement_directory(input_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Scanne récursivement `input_dir` à la recherche de fichiers `gouvernement-*.json`.

    Args:
        input_dir: répertoire racine à scanner (récursif), convention de
            nommage `gouvernement-<LIBELLE>.json` déjà en place (voir
            `pivot_data/gouvernements/`).

    Returns:
        Tuple (gouvernements_valides, erreurs_lecture) :
          - gouvernements_valides : liste des profils de gouvernement chargés
            avec succès, triés par chemin de fichier pour un résultat
            déterministe.
          - erreurs_lecture : liste de {"fichier": str, "erreur": str} pour
            chaque fichier n'ayant pas pu être chargé (JSON invalide, objet
            racine non-dict, erreur de lecture...). Un fichier problématique
            n'interrompt jamais le scan des suivants.
    """
    gouvernements_valides: list[dict[str, Any]] = []
    erreurs_lecture: list[dict[str, Any]] = []

    for path in sorted(input_dir.rglob("gouvernement-*.json")):
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

        gouvernements_valides.append(data)

    return gouvernements_valides, erreurs_lecture


def _taille_liste(gouvernement: dict[str, Any], champ: str) -> int:
    """Longueur de `gouvernement[champ]`, `0` si absent ou `null` (donnée manquante)."""
    valeur = gouvernement.get(champ)
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

def compute_repartition_periode_actif(gouvernements: list[dict[str, Any]]) -> dict[str, Any]:
    """Répartition des gouvernements par `periode.actif`.

    Un `periode` absent, non-dict, ou `actif` non booléen compte comme
    "indetermine" — jamais assimilé à `False` (AGENTS.md §2.5 : donnée
    manquante n'est jamais un défaut à 0/faux).
    """
    actifs = 0
    inactifs = 0
    indetermines = 0

    for gouvernement in gouvernements:
        periode = gouvernement.get("periode")
        actif = periode.get("actif") if isinstance(periode, dict) else None
        if actif is True:
            actifs += 1
        elif actif is False:
            inactifs += 1
        else:
            indetermines += 1

    return {
        "total_gouvernements": len(gouvernements),
        "actifs": actifs,
        "inactifs": inactifs,
        "indetermines": indetermines,
    }


def compute_distribution_membres_textes(gouvernements: list[dict[str, Any]]) -> dict[str, Any]:
    """Distribution du nombre de `membres` et de `textes` par gouvernement.

    Min/max/médiane/moyenne sur `len(membres)` et `len(textes)` — un champ
    absent ou `null` compte pour 0 (ces listes sont toujours calculables,
    jamais "non calculées" comme `effectif.min_historique` côté groupe).
    """
    tailles_membres = [_taille_liste(gouvernement, "membres") for gouvernement in gouvernements]
    tailles_textes = [_taille_liste(gouvernement, "textes") for gouvernement in gouvernements]

    return {
        "membres": _stats_entiers(tailles_membres),
        "textes": _stats_entiers(tailles_textes),
    }


def compute_comptages_agreges(gouvernements: list[dict[str, Any]]) -> dict[str, int]:
    """Agrège `comptages.par_statut` de tous les gouvernements.

    Un bloc `comptages`/`par_statut` absent ou invalide est simplement
    ignoré (jamais compté comme une répartition à 0). Résultat : entiers
    bruts uniquement (AGENTS.md §2.1) — aucun taux, pourcentage ou
    classement.
    """
    agregats = make_empty_comptages_statuts()

    for gouvernement in gouvernements:
        comptages = gouvernement.get("comptages")
        par_statut = comptages.get("par_statut") if isinstance(comptages, dict) else None
        if not isinstance(par_statut, dict):
            continue
        for statut, valeur in par_statut.items():
            if statut in agregats and isinstance(valeur, int) and not isinstance(valeur, bool):
                agregats[statut] += valeur

    return agregats


# ---------------------------------------------------------------------------
# Complétude
# ---------------------------------------------------------------------------

def compute_presence_premier_ministre(gouvernements: list[dict[str, Any]]) -> dict[str, Any]:
    """Taux de gouvernements avec un `premier_ministre` renseigné (non `null`)."""
    total = len(gouvernements)
    renseignes = sum(1 for g in gouvernements if _est_renseigne(g.get("premier_ministre")))

    return {
        "renseignes": renseignes,
        "total": total,
        "taux_pct": round(100 * renseignes / total, 2) if total else 0.0,
    }


def compute_taux_portefeuille_renseigne(gouvernements: list[dict[str, Any]]) -> dict[str, Any]:
    """Taux de `membres[].portefeuille` renseigné, agrégé tous gouvernements confondus.

    Compte tous les ministres recensés (tous gouvernements confondus) : un
    `membres[]` vide ne contribue à aucun des deux compteurs — ce taux ne
    porte que sur les ministres effectivement présents dans le corpus.
    """
    total_membres = 0
    membres_avec_portefeuille = 0

    for gouvernement in gouvernements:
        membres = gouvernement.get("membres")
        if not isinstance(membres, list):
            continue
        for membre in membres:
            if not isinstance(membre, dict):
                continue
            total_membres += 1
            if _est_renseigne(membre.get("portefeuille")):
                membres_avec_portefeuille += 1

    return {
        "renseignes": membres_avec_portefeuille,
        "total": total_membres,
        "taux_pct": (
            round(100 * membres_avec_portefeuille / total_membres, 2) if total_membres else 0.0
        ),
    }


def compute_presence_meta(gouvernements: list[dict[str, Any]]) -> dict[str, Any]:
    """Taux de gouvernements avec un bloc `meta` renseigné (dict non vide)."""
    total = len(gouvernements)
    renseignes = sum(1 for g in gouvernements if isinstance(g.get("meta"), dict) and g.get("meta"))

    return {
        "renseignes": renseignes,
        "total": total,
        "taux_pct": round(100 * renseignes / total, 2) if total else 0.0,
    }


# ---------------------------------------------------------------------------
# Cohérence
# ---------------------------------------------------------------------------

def compute_validation_schema(gouvernements: list[dict[str, Any]]) -> dict[str, Any]:
    """Agrège les résultats de `schema_gouvernement.validate_profil_gouvernement` sur le corpus.

    Couvre déjà l'invariant du 49.3 (`statut`/`sort_49_3` non collapsés,
    voir `schema_gouvernement.validate_profil_gouvernement`) : ces erreurs
    remontent ici, sans indicateur dédié dupliqué.

    Returns:
        `{"total_gouvernements": int, "nb_gouvernements_invalides": int,
        "gouvernements_invalides": [{"gouvernement_id":..., "erreurs": [str,
        ...]}, ...]}`, triés par `gouvernement_id` pour un résultat
        déterministe.
    """
    gouvernements_invalides = [
        {"gouvernement_id": gouvernement.get("gouvernement_id"), "erreurs": erreurs}
        for gouvernement in gouvernements
        for erreurs in [validate_profil_gouvernement(gouvernement)]
        if erreurs
    ]
    gouvernements_invalides.sort(
        key=lambda entree: (entree["gouvernement_id"] is None, entree["gouvernement_id"])
    )

    return {
        "total_gouvernements": len(gouvernements),
        "nb_gouvernements_invalides": len(gouvernements_invalides),
        "gouvernements_invalides": gouvernements_invalides,
    }


def compute_coherence_schema_version(gouvernements: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare `schema_version` (racine) et `meta.schema_version`.

    Les deux champs doivent porter la même valeur : une divergence signale
    un profil de gouvernement partiellement régénéré.

    Returns:
        `{"gouvernements_incoherents": [{"gouvernement_id":...,
        "schema_version":..., "meta_schema_version":...}, ...]}`.
    """
    gouvernements_incoherents: list[dict[str, Any]] = []

    for gouvernement in gouvernements:
        schema_version = gouvernement.get("schema_version")
        meta = gouvernement.get("meta")
        meta_schema_version = meta.get("schema_version") if isinstance(meta, dict) else None

        if schema_version != meta_schema_version:
            gouvernements_incoherents.append({
                "gouvernement_id": gouvernement.get("gouvernement_id"),
                "schema_version": schema_version,
                "meta_schema_version": meta_schema_version,
            })

    return {"gouvernements_incoherents": gouvernements_incoherents}


def compute_doublons_gouvernement_id(gouvernements: list[dict[str, Any]]) -> dict[str, Any]:
    """Détecte les `gouvernement_id` présents plusieurs fois dans le corpus.

    Le `gouvernement_id` (`"gouvernement:<libelle_abrege_an>"`) doit être
    unique : un doublon signale une erreur amont de génération. Les
    gouvernements sans `gouvernement_id` (absent ou vide) sont ignorés — ce
    défaut relève de la validation structurelle
    (`validate_profil_gouvernement`), pas de la cohérence inter-gouvernements.

    Returns:
        `{"doublons": [{"gouvernement_id": str, "occurrences": int}, ...]}`,
        trié par `gouvernement_id` pour un résultat déterministe ; liste
        vide si aucun doublon.
    """
    occurrences_par_id: dict[str, int] = {}
    for gouvernement in gouvernements:
        gouvernement_id = gouvernement.get("gouvernement_id")
        if not gouvernement_id:
            continue
        occurrences_par_id[gouvernement_id] = occurrences_par_id.get(gouvernement_id, 0) + 1

    return {
        "doublons": [
            {"gouvernement_id": gouvernement_id, "occurrences": occurrences}
            for gouvernement_id, occurrences in sorted(occurrences_par_id.items())
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
    gouvernements: list[dict[str, Any]], reference_date: datetime | None = None
) -> dict[str, Any]:
    """Ancienneté des sources (`sources[].synchro_le`) par type de source.

    Pour chaque type de source rencontré (`sources[].type`, `"null"` si
    absent), distribution en jours écoulés depuis la dernière synchro : min,
    max, médiane, moyenne. Les sources sans `synchro_le` valide sont
    ignorées.

    Args:
        gouvernements: liste de profils de gouvernement.
        reference_date: date de référence pour le calcul de l'ancienneté,
            injectable pour des tests déterministes (défaut :
            `datetime.now(timezone.utc)`).

    Returns:
        `{"total_sources_datees": int, "par_type_source": {type: {...}}}`.
        Un type de source absent de `gouvernements` n'apparaît pas dans le
        résultat.
    """
    reference = reference_date if reference_date is not None else datetime.now(timezone.utc)

    anciennetes_par_type: dict[str, list[int]] = {}
    for gouvernement in gouvernements:
        for source in gouvernement.get("sources") or []:
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


def _anciennetes_sources_jours(gouvernement: dict[str, Any], reference_date: datetime) -> list[int]:
    """Anciennetés (en jours) des sources du gouvernement dont `synchro_le` est valide."""
    anciennetes: list[int] = []
    for source in gouvernement.get("sources") or []:
        if not isinstance(source, dict):
            continue
        date_synchro = _parse_synchro_le(source.get("synchro_le"))
        if date_synchro is not None:
            anciennetes.append(_anciennete_jours(date_synchro, reference_date))
    return anciennetes


def compute_gouvernements_perimes(
    gouvernements: list[dict[str, Any]],
    staleness_days: int,
    reference_date: datetime | None = None,
) -> list[str]:
    """`gouvernement_id` des gouvernements dont **toutes** les sources ont plus de `staleness_days` jours.

    Un gouvernement sans aucune source dont `synchro_le` est exploitable
    n'est jamais considéré comme périmé (il n'y a rien à mesurer) : seuls
    les gouvernements ayant au moins une source datée, et dont la source la
    plus fraîche dépasse tout de même le seuil, sont retournés.

    Args:
        gouvernements: liste de profils de gouvernement.
        staleness_days: seuil d'ancienneté (en jours) au-delà duquel une
            source est considérée périmée.
        reference_date: date de référence injectable (voir
            `compute_fraicheur_sources`).

    Returns:
        Liste triée des `gouvernement_id` de gouvernements périmés.
    """
    reference = reference_date if reference_date is not None else datetime.now(timezone.utc)

    perimes = []
    for gouvernement in gouvernements:
        anciennetes = _anciennetes_sources_jours(gouvernement, reference)
        if anciennetes and min(anciennetes) > staleness_days:
            perimes.append(gouvernement.get("gouvernement_id"))

    return sorted(perimes)


# ---------------------------------------------------------------------------
# Assemblage du rapport
# ---------------------------------------------------------------------------

def build_report(
    gouvernements: list[dict[str, Any]],
    erreurs_lecture: list[dict[str, Any]],
    staleness_days: int = 30,
    reference_date: datetime | None = None,
) -> dict[str, Any]:
    """Assemble tous les indicateurs `compute_*` en un rapport structuré unique.

    Args:
        gouvernements: profils de gouvernement valides (sortie de
            `load_gouvernement_directory`).
        erreurs_lecture: erreurs de lecture (sortie de
            `load_gouvernement_directory`).
        staleness_days: seuil d'ancienneté en jours pour
            `compute_gouvernements_perimes` (défaut : 30).
        reference_date: date de référence injectable pour les indicateurs de
            fraîcheur, voir `compute_fraicheur_sources` (défaut :
            `datetime.now(timezone.utc)`).

    Returns:
        Dict sérialisable JSON, une section par catégorie d'indicateur
        (`volumetrie`, `completude`, `coherence`, `fraicheur`) plus `meta` et
        `erreurs_lecture`. Outil de qualité interne : ce rapport ne doit
        jamais introduire de jugement de valeur, de score ou de classement
        (AGENTS.md §2.1).
    """
    reference = reference_date if reference_date is not None else datetime.now(timezone.utc)

    return {
        "meta": {
            "genere_le": reference.isoformat(),
            "total_gouvernements": len(gouvernements),
            "total_erreurs_lecture": len(erreurs_lecture),
            "staleness_days": staleness_days,
        },
        "volumetrie": {
            "repartition_periode_actif": compute_repartition_periode_actif(gouvernements),
            "distribution_membres_textes": compute_distribution_membres_textes(gouvernements),
            "comptages_agreges": compute_comptages_agreges(gouvernements),
        },
        "completude": {
            "presence_premier_ministre": compute_presence_premier_ministre(gouvernements),
            "taux_portefeuille_renseigne": compute_taux_portefeuille_renseigne(gouvernements),
            "presence_meta": compute_presence_meta(gouvernements),
        },
        "coherence": {
            "validation_schema": compute_validation_schema(gouvernements),
            "coherence_schema_version": compute_coherence_schema_version(gouvernements),
            "doublons_gouvernement_id": compute_doublons_gouvernement_id(gouvernements),
        },
        "fraicheur": {
            "fraicheur_sources": compute_fraicheur_sources(gouvernements, reference_date=reference),
            "gouvernements_perimes": compute_gouvernements_perimes(
                gouvernements, staleness_days=staleness_days, reference_date=reference
            ),
        },
        "erreurs_lecture": erreurs_lecture,
    }
