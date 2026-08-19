#!/usr/bin/env python3
"""
merge_profile.py — Fusion additive de profils (brut ou pivot).

Objectif : quand un profil est régénéré à partir des API publiques (souvent
sujettes à des variations transitoires : pagination de recherche qui bouge,
requête HTML supplémentaire qui échoue ponctuellement...), on ne veut pas
perdre les données déjà obtenues lors d'une régénération précédente.

Principe : "une simple addition, jamais une suppression". Pour chaque liste
(votes, mandats, dossiers législatifs, interventions...), les entrées déjà
présentes dans le fichier existant sont conservées telles quelles ; seules
les entrées réellement nouvelles (dont la clé d'unicité n'apparaît pas déjà)
sont ajoutées. Aucune entrée existante n'est modifiée ni supprimée.

Pour les champs scalaires (identité, source des votes, synthèse d'activité...),
on garde la nouvelle valeur si elle est renseignée, sinon on retombe sur
l'ancienne (pour ne pas régresser vers `null` suite à un échec transitoire).

Usage :
    from merge_profile import merge_raw_profile, merge_pivot_profile
    profile = merge_raw_profile(old_profile, new_profile)
    pivot = merge_pivot_profile(old_pivot, new_pivot)

CLI (fusion de répertoires d'extraction parallèles) :
    python src/merge_profile.py --dirs artifacts/an artifacts/senat artifacts/ue \\
                                 --out raw_data/profiles
"""

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Optional

from candidate_profile import (
    WARNING_PREFIX_IDENTITE_INTROUVABLE,
    WARNING_PREFIX_MANDATS_INTROUVABLES,
    WARNING_PREFIX_VOTES_INTROUVABLES,
    WARNING_PREFIX_AMENDEMENTS_INDISPONIBLES,
    WARNING_PREFIX_QUESTIONS_INDISPONIBLES,
)
from json_io import ecrire_profil_json

Key = Any


def merge_lists_by_key(
    old_list: Optional[list[dict[str, Any]]],
    new_list: Optional[list[dict[str, Any]]],
    key_fn: Callable[[dict[str, Any]], Key],
) -> list[dict[str, Any]]:
    """Fusionne deux listes de dicts par clé d'unicité, en mode additif pur :
    les entrées de `old_list` sont toutes conservées inchangées ; seules les
    entrées de `new_list` dont la clé n'apparaît pas déjà dans `old_list`
    sont ajoutées (à la suite, dans leur ordre d'apparition)."""
    old_list = old_list or []
    new_list = new_list or []
    seen_keys = {key_fn(item) for item in old_list if isinstance(item, dict)}
    merged = list(old_list)
    for item in new_list:
        if not isinstance(item, dict):
            continue
        k = key_fn(item)
        if k in seen_keys:
            continue
        seen_keys.add(k)
        merged.append(item)
    return merged


def _prefer_non_empty(new_value: Any, old_value: Any) -> Any:
    """Garde `new_value` si elle est renseignée (non vide/non nulle), sinon
    retombe sur `old_value` (évite qu'un échec transitoire de collecte fasse
    régresser un champ scalaire vers `null`)."""
    if new_value not in (None, "", [], {}):
        return new_value
    return old_value


# --- Clés d'unicité, format brut (candidate_profile.py / candidate_profile_ue.py) ---

def _vote_key(v: dict[str, Any]) -> Key:
    return (v.get("numero_scrutin"), v.get("date"))


def _dossier_key(d: dict[str, Any]) -> Key:
    return (d.get("legislature"), d.get("id"))


def _mandat_key(m: dict[str, Any]) -> Key:
    return (m.get("categorie"), m.get("type"), m.get("label"), m.get("debut"))


def _intervention_key(i: dict[str, Any]) -> Key:
    return (i.get("id"), i.get("url") or i.get("url_detail"))


def _amendement_key(a: dict[str, Any]) -> Key:
    # `uid` d'abord : c'est le seul identifiant unique d'un amendement AN. Les
    # replis restent pour les entrées collectées avant son extraction (#431,
    # correction de clé du 18/08/2026) — `numero` seul ne distingue pas deux
    # amendements de textes différents, et `texte_vise` est tantôt un code
    # source, tantôt un titre résolu, ce qui fait passer le même amendement pour
    # deux entrées distinctes à la fusion.
    return a.get("uid") or a.get("source_url") or (a.get("numero"), a.get("texte_vise"), a.get("date"))


def _mandat_ue_key(m: dict[str, Any]) -> Key:
    return (m.get("type"), m.get("organisation_sigle"), m.get("role"), m.get("debut"))


def _prune_stale_warnings(profile: dict[str, Any]) -> None:
    """Retire les avertissements devenus obsolètes après fusion (ex. "votes
    introuvables" alors que les votes ont en fait été restaurés depuis
    l'ancien fichier)."""
    meta = profile.get("meta")
    if not isinstance(meta, dict) or not meta.get("warnings"):
        return
    filtered = []
    for w in meta["warnings"]:
        if w.startswith(WARNING_PREFIX_VOTES_INTROUVABLES) and profile.get("votes"):
            continue
        if w.startswith(WARNING_PREFIX_IDENTITE_INTROUVABLE) and profile.get("identite"):
            continue
        if w.startswith(WARNING_PREFIX_MANDATS_INTROUVABLES) and profile.get("mandats"):
            continue
        if w.startswith(WARNING_PREFIX_AMENDEMENTS_INDISPONIBLES) and profile.get("amendements"):
            continue
        if (
            w.startswith(WARNING_PREFIX_QUESTIONS_INDISPONIBLES)
            and any(i.get("type_detail") == "question" for i in profile.get("interventions", []))
        ):
            continue
        filtered.append(w)
    meta["warnings"] = filtered


def merge_raw_profile(old: Optional[dict[str, Any]], new: dict[str, Any]) -> dict[str, Any]:
    """Fusionne un profil brut nouvellement généré (`new`) avec la version
    déjà présente sur disque (`old`, ou None si aucun fichier existant).
    Additif uniquement : ne supprime ni ne modifie aucune entrée déjà connue."""
    if not old:
        return new

    merged = dict(new)

    # Préserver aussi la traçabilité de synchro si la nouvelle collecte a échoué
    # (sinon `synchro_sources.*` peut redevenir None alors que les données sont restaurées depuis l'ancien profil).
    if isinstance(merged.get("meta"), dict) and isinstance(old.get("meta"), dict):
        old_synchro = old["meta"].get("synchro_sources")
        new_synchro = merged["meta"].get("synchro_sources")
        if isinstance(old_synchro, dict):
            if not isinstance(new_synchro, dict):
                merged["meta"]["synchro_sources"] = dict(old_synchro)
            else:
                merged["meta"]["synchro_sources"] = {
                    k: _prefer_non_empty(new_synchro.get(k), old_synchro.get(k))
                    for k in set(old_synchro) | set(new_synchro)
                }

    merged["identite"] = _prefer_non_empty(new.get("identite"), old.get("identite"))
    merged["chambre"] = _prefer_non_empty(new.get("chambre"), old.get("chambre"))
    merged["source"] = _prefer_non_empty(new.get("source"), old.get("source"))
    merged["votes_source"] = _prefer_non_empty(new.get("votes_source"), old.get("votes_source"))
    merged["mandats"] = merge_lists_by_key(old.get("mandats"), new.get("mandats"), _mandat_key)
    merged["votes"] = sorted(
        merge_lists_by_key(old.get("votes"), new.get("votes"), _vote_key),
        key=lambda v: v.get("date") or "",
        reverse=True,
    )
    merged["dossiers_legislatifs"] = sorted(
        (
            d for d in merge_lists_by_key(old.get("dossiers_legislatifs"), new.get("dossiers_legislatifs"), _dossier_key)
            if d.get("role")  # écarte la liste globale héritée de NosDéputés (mêmes dossiers
                              # pour tout le monde sur une législature, role toujours absent/null
                              # — voir candidate_profile.fetch_textes_portes_officiels)
        ),
        key=lambda d: (d.get("date_max") or "", d.get("titre") or ""),
        reverse=True,
    )
    merged["interventions"] = merge_lists_by_key(old.get("interventions"), new.get("interventions"), _intervention_key)
    # merge_dossier_records (nouvelle valeur gagne en cas de collision, aucune perte
    # sinon) : un echec/vide transitoire de l'open data amendements ne doit pas
    # effacer des amendements deja collectes lors d'une regeneration precedente.
    merged["amendements"] = merge_dossier_records(old.get("amendements"), new.get("amendements"), _amendement_key)

    old_ue = old.get("mandat_europeen")
    new_ue = new.get("mandat_europeen")
    if old_ue or new_ue:
        merged_ue = dict(new_ue or old_ue or {})
        merged_ue["mandats_europeens"] = sorted(
            merge_lists_by_key(
                (old_ue or {}).get("mandats_europeens"),
                (new_ue or {}).get("mandats_europeens"),
                _mandat_ue_key,
            ),
            key=lambda m: m.get("debut") or "",
            reverse=True,
        )
        merged["mandat_europeen"] = merged_ue

    _prune_stale_warnings(merged)
    return merged


# --- Clés d'unicité, format pivot v1 (schema_pivot.py) ---

def _pivot_vote_key(v: dict[str, Any]) -> Key:
    return (v.get("numero_scrutin"), v.get("date"))


def _pivot_mandat_key(m: dict[str, Any]) -> Key:
    return (m.get("label"), m.get("categorie"), m.get("fonction"), m.get("debut"))


def _pivot_texte_key(t: dict[str, Any]) -> Key:
    """Identité d'un dossier législatif porté, indépendante de `role`.

    `role`/`type_rapport`/`stade_procedural` ne sont aujourd'hui jamais
    renseignés par la source de collecte (voir normalize_nosdeputes.py) : les
    inclure dans la clé ferait fusionner en double une même entrée dès qu'une
    régénération produit une valeur différente (ex. données historiques
    erronées conservées indéfiniment). L'identité du dossier repose donc sur
    son URL source (stable) ou, à défaut, sur titre+date_min+législature.
    """
    return t.get("source_url") or (t.get("titre"), t.get("date_min"), t.get("legislature"))


def merge_dossier_records(
    old_list: Optional[list[dict[str, Any]]],
    new_list: Optional[list[dict[str, Any]]],
    key_fn: Callable[[dict[str, Any]], Key],
) -> list[dict[str, Any]]:
    """Fusionne deux listes de dossiers par identité : contrairement à
    `merge_lists_by_key`, la nouvelle entrée remplace l'ancienne en cas de
    collision de clé (le rôle/stade procédural peut être corrigé d'une
    régénération à l'autre) ; les dossiers absents de `new_list` restent
    conservés."""
    old_list = old_list or []
    new_list = new_list or []
    by_key: dict[Key, dict[str, Any]] = {}
    order: list[Key] = []
    for item in old_list + new_list:
        if not isinstance(item, dict):
            continue
        k = key_fn(item)
        if k not in by_key:
            order.append(k)
        by_key[k] = item
    return [by_key[k] for k in order]


def clean_stale_textes_portes(textes: Optional[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Nettoyage ponctuel des doublons hérités d'un ancien bug de fusion (clé
    incluant `role`, cf. `_pivot_texte_key`) : avant l'ajout de type_rapport/
    stade_procedural au schéma, un `role` (souvent "rapporteur") était
    appliqué à tort à tout dossier, produisant deux entrées pour un même
    dossier une fois régénéré avec `role=null`. Conserve l'entrée la plus
    complète (schéma actuel) pour chaque identité de dossier."""
    by_key: dict[Key, dict[str, Any]] = {}
    order: list[Key] = []
    for t in textes or []:
        if not isinstance(t, dict):
            continue
        k = _pivot_texte_key(t)
        is_current_schema = "type_rapport" in t and "stade_procedural" in t
        if k not in by_key:
            order.append(k)
            by_key[k] = t
        elif is_current_schema and not ("type_rapport" in by_key[k] and "stade_procedural" in by_key[k]):
            by_key[k] = t
    return [by_key[k] for k in order]


def _pivot_amendement_key(a: dict[str, Any]) -> Key:
    # Même clé que côté brut (`_amendement_key`) : l'`uid` AN d'abord, replis
    # ensuite pour les entrées antérieures à son extraction.
    return a.get("uid") or a.get("source_url") or (a.get("numero"), a.get("texte_vise"), a.get("date"))


def _pivot_intervention_key(i: dict[str, Any]) -> Key:
    return i.get("source_url") or (i.get("date"), i.get("sujet"), (i.get("texte") or "")[:50])


def _merge_pivot_sources(old_sources: Optional[list[dict[str, Any]]], new_sources: Optional[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Fusionne les blocs `sources[]` par `type` : contrairement aux autres
    listes, on garde ici l'entrée dont la synchro est la plus récente (simple
    métadonnée de fraîcheur, pas une donnée métier à préserver telle quelle)."""
    by_type: dict[Any, dict[str, Any]] = {}
    order: list[Any] = []
    for item in (old_sources or []) + (new_sources or []):
        if not isinstance(item, dict):
            continue
        t = item.get("type")
        if t not in by_type:
            order.append(t)
            by_type[t] = item
        else:
            current = by_type[t]
            if (item.get("synchro_le") or "") > (current.get("synchro_le") or ""):
                by_type[t] = item
    return [by_type[t] for t in order]


def merge_pivot_profile(old: Optional[dict[str, Any]], new: dict[str, Any]) -> dict[str, Any]:
    """Équivalent de `merge_raw_profile` pour le format pivot v1."""
    if not old:
        return new

    merged = dict(new)

    merged["parti"] = _prefer_non_empty(new.get("parti"), old.get("parti"))
    merged["groupe"] = _prefer_non_empty(new.get("groupe"), old.get("groupe"))
    merged["chambre"] = _prefer_non_empty(new.get("chambre"), old.get("chambre"))
    merged["identite"] = _prefer_non_empty(new.get("identite"), old.get("identite"))

    merged["sources"] = _merge_pivot_sources(old.get("sources"), new.get("sources"))
    merged["mandats"] = merge_lists_by_key(old.get("mandats"), new.get("mandats"), _pivot_mandat_key)
    merged["votes"] = sorted(
        merge_lists_by_key(old.get("votes"), new.get("votes"), _pivot_vote_key),
        key=lambda v: v.get("date") or "",
        reverse=True,
    )
    merged["textes_portes"] = sorted(
        (
            t for t in merge_dossier_records(old.get("textes_portes"), new.get("textes_portes"), _pivot_texte_key)
            if t.get("role")  # écarte la liste globale héritée de NosDéputés (role toujours
                              # null) — voir candidate_profile.fetch_textes_portes_officiels
        ),
        key=lambda t: (t.get("date_max") or "", t.get("titre") or ""),
        reverse=True,
    )
    merged["interventions"] = merge_lists_by_key(old.get("interventions"), new.get("interventions"), _pivot_intervention_key)
    # merge_dossier_records (nouvelle valeur gagne en cas de collision, aucune perte
    # sinon) : un echec/vide transitoire de l'open data amendements (voir
    # candidate_profile.fetch_amendements_officiels) ne doit pas effacer des
    # amendements deja collectes lors d'une regeneration precedente.
    merged["amendements"] = merge_dossier_records(old.get("amendements"), new.get("amendements"), _pivot_amendement_key)

    old_tags = old.get("tags_thematiques") or []
    new_tags = new.get("tags_thematiques") or []
    merged["tags_thematiques"] = list(dict.fromkeys(list(old_tags) + list(new_tags)))

    if isinstance(merged.get("meta"), dict):
        # Politique de fusion provenance (#189) : un profil déjà enrichi via
        # raw_data/candidats.json (provenance="candidat_declare", source éditoriale
        # de vérité) ne doit JAMAIS être rétrogradé vers provenance="roster_groupe"
        # par une régénération roster-driven (#188) du même slug — même si le
        # nouveau run produit provenance="roster_groupe". Un ancien pivot sans
        # meta.provenance (pré-#189) est traité comme "candidat_declare" par défaut,
        # pour rester rétro-compatible. Les autres champs éditoriaux (ex. `parti`)
        # sont déjà protégés plus haut par `_prefer_non_empty` : un run roster-driven
        # ne les renseigne jamais (valeur None côté generate_roster_candidats.py),
        # donc l'ancienne valeur est conservée automatiquement.
        old_meta = old.get("meta") if isinstance(old.get("meta"), dict) else {}
        if old_meta.get("provenance", "candidat_declare") == "candidat_declare":
            merged["meta"]["provenance"] = "candidat_declare"

    if isinstance(merged.get("meta"), dict) and merged["meta"].get("warnings"):
        filtered = []
        for w in merged["meta"]["warnings"]:
            if w.startswith(WARNING_PREFIX_VOTES_INTROUVABLES) and merged.get("votes"):
                continue
            if w.startswith(WARNING_PREFIX_MANDATS_INTROUVABLES) and merged.get("mandats"):
                continue
            if w.startswith(WARNING_PREFIX_AMENDEMENTS_INDISPONIBLES) and merged.get("amendements"):
                continue
            filtered.append(w)
        merged["meta"]["warnings"] = filtered

    return merged


def _pivot_content_fingerprint(pivot: Optional[dict[str, Any]]) -> Any:
    """Sérialise un profil pivot en ignorant les horodatages de fraîcheur
    (`meta.genere_le`, `sources[].synchro_le`) : deux profils dont seuls ces
    champs diffèrent ont la même empreinte."""
    if not isinstance(pivot, dict):
        return None
    stripped = {k: v for k, v in pivot.items() if k not in ("meta", "sources")}
    meta = pivot.get("meta")
    if isinstance(meta, dict):
        stripped["meta"] = {k: v for k, v in meta.items() if k != "genere_le"}
    sources = pivot.get("sources")
    if isinstance(sources, list):
        stripped["sources"] = [
            {k: v for k, v in s.items() if k != "synchro_le"} if isinstance(s, dict) else s
            for s in sources
        ]
    return json.dumps(stripped, sort_keys=True, ensure_ascii=False)


def load_existing_document(path: Any) -> Optional[dict[str, Any]]:
    """Relit un document JSON déjà écrit sur disque, ou `None` s'il est absent
    ou illisible — pensé comme entrée de `preserve_stable_freshness_timestamps`
    (#343) pour les générateurs qui reconstruisent leur sortie à chaque
    exécution (groupes, gouvernements, partis).

    Un fichier illisible est traité comme absent plutôt que comme une erreur :
    la conséquence est seulement un re-tamponnage des horodatages, jamais une
    perte de donnée — le document régénéré est écrit dans tous les cas."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


def preserve_stable_freshness_timestamps(
    old_pivot: Optional[dict[str, Any]], new_pivot: dict[str, Any]
) -> dict[str, Any]:
    """Empêche `meta.genere_le`/`sources[].synchro_le` d'avancer quand le
    document régénéré est identique à `old_pivot` en contenu (#343) : les
    générateurs re-dérivent systématiquement leur sortie depuis les données
    déjà présentes sur disque (aucun appel réseau pour `--pivot-only`) et
    re-tamponnaient ces deux champs à chaque exécution, même quand la donnée
    sous-jacente n'avait pas bougé — trompeur pour un audit de fraîcheur
    (règle de traçabilité, AGENTS.md §2).

    Si le contenu (hors ces deux champs) est identique, restaure les anciens
    horodatages sur `new_pivot` ; sinon le laisse tel quel (changement réel =
    re-tamponnage légitime). Modifie et renvoie `new_pivot`.

    S'applique à tout document portant la forme `meta.genere_le` +
    `sources[].synchro_le` : pivots candidats, mais aussi profils de groupe,
    de gouvernement et de parti, qui partagent exactement cette structure de
    fraîcheur (extension du périmètre initial, #343).

    Les sources sont appariées par `(type, url)` et non par `type` seul : un
    profil de groupe/gouvernement/parti porte une source par membre, donc
    plusieurs dizaines d'entrées partageant le même `type` (mesuré : 63
    sources pour 3 types distincts sur un groupe) — une clé sur le seul
    `type` les écraserait toutes sur la dernière. L'appariement reste
    exact : `url` fait partie de l'empreinte comparée ci-dessus, donc si les
    empreintes sont égales, les couples `(type, url)` le sont aussi.
    """
    if not isinstance(old_pivot, dict):
        return new_pivot
    if _pivot_content_fingerprint(old_pivot) != _pivot_content_fingerprint(new_pivot):
        return new_pivot

    old_meta = old_pivot.get("meta")
    new_meta = new_pivot.get("meta")
    if isinstance(old_meta, dict) and isinstance(new_meta, dict) and "genere_le" in old_meta:
        new_meta["genere_le"] = old_meta["genere_le"]

    old_sources_by_key = {
        (s.get("type"), s.get("url")): s
        for s in (old_pivot.get("sources") or [])
        if isinstance(s, dict)
    }
    for s in new_pivot.get("sources") or []:
        if not isinstance(s, dict):
            continue
        old_s = old_sources_by_key.get((s.get("type"), s.get("url")))
        if old_s and "synchro_le" in old_s:
            s["synchro_le"] = old_s["synchro_le"]

    return new_pivot


# ---------------------------------------------------------------------------
# CLI : fusion de répertoires d'extraction parallèles → merge-and-pivot
# ---------------------------------------------------------------------------

def merge_raw_dirs(source_dirs: list[Path], out_dir: Path) -> int:
    """Fusionne les profils bruts (*.json) de plusieurs répertoires sources
    (jobs d'extraction parallèles AN / Sénat / UE) vers un répertoire cible,
    en appliquant merge_raw_profile de façon additive pour chaque slug.

    Les fichiers de checkpoint (nom commençant par '.') sont ignorés.

    Args:
        source_dirs: liste de répertoires sources (certains peuvent être absents).
        out_dir: répertoire de sortie, créé si nécessaire.

    Returns:
        Nombre de profils écrits dans out_dir.
    """
    slug_paths: dict[str, list[Path]] = defaultdict(list)
    for src_dir in source_dirs:
        if not src_dir.is_dir():
            print(f"  [!] Répertoire source absent, ignoré : {src_dir}")
            continue
        for path in sorted(src_dir.glob("*.json")):
            if path.name.startswith("."):
                continue
            slug_paths[path.name].append(path)

    out_dir.mkdir(parents=True, exist_ok=True)
    n_written = 0
    for filename, paths in sorted(slug_paths.items()):
        merged: Optional[dict[str, Any]] = None
        for path in paths:
            try:
                with open(path, encoding="utf-8") as f:
                    profile = json.load(f)
            except (json.JSONDecodeError, OSError) as exc:
                print(f"  [!] Lecture impossible de {path}, ignoré : {exc}")
                continue
            merged = merge_raw_profile(merged, profile)
        if merged is not None:
            ecrire_profil_json(out_dir / filename, merged)
            n_written += 1

    return n_written


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description=(
            "Fusionne les profils bruts (*.json) de plusieurs répertoires "
            "d'extraction parallèles vers un répertoire cible unique. "
            "Usage typique : job merge-and-pivot après extract-an / "
            "extract-senat / extract-ue-officiel dans le workflow GitHub Actions."
        )
    )
    parser.add_argument(
        "--dirs",
        nargs="+",
        required=True,
        metavar="DIR",
        help="Répertoires sources à fusionner (au moins un requis).",
    )
    parser.add_argument(
        "--out",
        required=True,
        metavar="DIR",
        help="Répertoire de sortie pour les profils fusionnés.",
    )
    _args = parser.parse_args()

    _source_dirs = [Path(d) for d in _args.dirs]
    _out_dir = Path(_args.out)

    print(f"Fusion de {len(_source_dirs)} répertoire(s) → {_out_dir}")
    _n = merge_raw_dirs(_source_dirs, _out_dir)
    print(f"  ✓ {_n} profil(s) écrits dans {_out_dir}")
    sys.exit(0)
