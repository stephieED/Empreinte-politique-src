#!/usr/bin/env python3
"""Module documentation in English."""

from typing import Any, Callable, Optional

from candidate_profile import (
    WARNING_PREFIX_IDENTITE_INTROUVABLE,
    WARNING_PREFIX_MANDATS_INTROUVABLES,
    WARNING_PREFIX_VOTES_INTROUVABLES,
    WARNING_PREFIX_AMENDEMENTS_INDISPONIBLES,
    WARNING_PREFIX_QUESTIONS_INDISPONIBLES,
)

Key = Any


def merge_lists_by_key(
    old_list: Optional[list[dict[str, Any]]],
    new_list: Optional[list[dict[str, Any]]],
    key_fn: Callable[[dict[str, Any]], Key],
) -> list[dict[str, Any]]:
    """English docstring for merge lists by key."""   old_list = old_list or []
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
    """English docstring for  prefer non empty."""    if new_value not in (None, "", [], {}):
        return new_value
    return old_value


# Translated comment.

def _vote_key(v: dict[str, Any]) -> Key:
    return (v.get("numero_scrutin"), v.get("date"))


def _dossier_key(d: dict[str, Any]) -> Key:
    return (d.get("legislature"), d.get("id"))


def _mandat_key(m: dict[str, Any]) -> Key:
    return (m.get("categorie"), m.get("type"), m.get("label"), m.get("debut"))


def _intervention_key(i: dict[str, Any]) -> Key:
    return (i.get("id"), i.get("url") or i.get("url_detail"))


def _amendement_key(a: dict[str, Any]) -> Key:
    return a.get("source_url") or (a.get("numero"), a.get("texte_vise"), a.get("date"))


def _mandat_ue_key(m: dict[str, Any]) -> Key:
    return (m.get("type"), m.get("organisation_sigle"), m.get("role"), m.get("debut"))


def _prune_stale_warnings(profile: dict[str, Any]) -> None:
    """English docstring for  prune stale warnings."""
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
    """English docstring for merge raw profile."""  if not old:
        return new

    merged = dict(new)

    # Translated comment.
    # Translated comment.
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
    merged["synthese_activite"] = _prefer_non_empty(new.get("synthese_activite"), old.get("synthese_activite"))
    merged["mandats"] = merge_lists_by_key(old.get("mandats"), new.get("mandats"), _mandat_key)
    merged["votes"] = sorted(
        merge_lists_by_key(old.get("votes"), new.get("votes"), _vote_key),
        key=lambda v: v.get("date") or "",
        reverse=True,
    )
    merged["dossiers_legislatifs"] = sorted(
        (
            d for d in merge_lists_by_key(old.get("dossiers_legislatifs"), new.get("dossiers_legislatifs"), _dossier_key)
            if d.get("role")  # Translated comment.
                              # Translated comment.
                              # — voir candidate_profile.fetch_textes_portes_officiels)
        ),
        key=lambda d: (d.get("date_max") or "", d.get("titre") or ""),
        reverse=True,
    )
    merged["interventions"] = merge_lists_by_key(old.get("interventions"), new.get("interventions"), _intervention_key)
    # Translated comment.
    # Translated comment.
    # Translated comment.
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


# Translated comment.

def _pivot_vote_key(v: dict[str, Any]) -> Key:
    return (v.get("numero_scrutin"), v.get("date"))


def _pivot_mandat_key(m: dict[str, Any]) -> Key:
    return (m.get("label"), m.get("categorie"), m.get("fonction"), m.get("debut"))


def _pivot_texte_key(t: dict[str, Any]) -> Key:
    """English docstring for  pivot texte key."""
    return t.get("source_url") or (t.get("titre"), t.get("date_min"), t.get("legislature"))


def merge_dossier_records(
    old_list: Optional[list[dict[str, Any]]],
    new_list: Optional[list[dict[str, Any]]],
    key_fn: Callable[[dict[str, Any]], Key],
) -> list[dict[str, Any]]:
    """English docstring for merge dossier records."""    old_list = old_list or []
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
    """English docstring for clean stale textes portes."""  by_key: dict[Key, dict[str, Any]] = {}
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
    return a.get("source_url") or (a.get("numero"), a.get("texte_vise"), a.get("date"))


def _pivot_intervention_key(i: dict[str, Any]) -> Key:
    return i.get("source_url") or (i.get("date"), i.get("sujet"), (i.get("texte") or "")[:50])


def _merge_pivot_sources(old_sources: Optional[list[dict[str, Any]]], new_sources: Optional[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """English docstring for  merge pivot sources."""_type: dict[Any, dict[str, Any]] = {}
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
    """English docstring for merge pivot profile."""    if not old:
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
            if t.get("role")  # Translated comment.
                              # null) — voir candidate_profile.fetch_textes_portes_officiels
        ),
        key=lambda t: (t.get("date_max") or "", t.get("titre") or ""),
        reverse=True,
    )
    merged["interventions"] = merge_lists_by_key(old.get("interventions"), new.get("interventions"), _pivot_intervention_key)
    # Translated comment.
    # Translated comment.
    # Translated comment.
    # Translated comment.
    merged["amendements"] = merge_dossier_records(old.get("amendements"), new.get("amendements"), _pivot_amendement_key)

    old_tags = old.get("tags_thematiques") or []
    new_tags = new.get("tags_thematiques") or []
    merged["tags_thematiques"] = list(dict.fromkeys(list(old_tags) + list(new_tags)))

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
