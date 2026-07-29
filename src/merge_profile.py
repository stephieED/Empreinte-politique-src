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
"""

from typing import Any, Callable, Optional

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
        if w.startswith("votes introuvables") and profile.get("votes"):
            continue
        if w.startswith("identité introuvable") and profile.get("identite"):
            continue
        if w.startswith("mandats introuvables") and profile.get("mandats"):
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
    merged["synthese_activite"] = _prefer_non_empty(new.get("synthese_activite"), old.get("synthese_activite"))
    merged["mandats"] = merge_lists_by_key(old.get("mandats"), new.get("mandats"), _mandat_key)
    merged["votes"] = sorted(
        merge_lists_by_key(old.get("votes"), new.get("votes"), _vote_key),
        key=lambda v: v.get("date") or "",
        reverse=True,
    )
    merged["dossiers_legislatifs"] = sorted(
        merge_lists_by_key(old.get("dossiers_legislatifs"), new.get("dossiers_legislatifs"), _dossier_key),
        key=lambda d: (d.get("date_max") or "", d.get("titre") or ""),
        reverse=True,
    )
    merged["interventions"] = merge_lists_by_key(old.get("interventions"), new.get("interventions"), _intervention_key)

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
    return (t.get("titre"), t.get("role"), t.get("date_min"), t.get("legislature"))


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

    merged["sources"] = _merge_pivot_sources(old.get("sources"), new.get("sources"))
    merged["mandats"] = merge_lists_by_key(old.get("mandats"), new.get("mandats"), _pivot_mandat_key)
    merged["votes"] = sorted(
        merge_lists_by_key(old.get("votes"), new.get("votes"), _pivot_vote_key),
        key=lambda v: v.get("date") or "",
        reverse=True,
    )
    merged["textes_portes"] = sorted(
        merge_lists_by_key(old.get("textes_portes"), new.get("textes_portes"), _pivot_texte_key),
        key=lambda t: (t.get("date_max") or "", t.get("titre") or ""),
        reverse=True,
    )
    merged["interventions"] = merge_lists_by_key(old.get("interventions"), new.get("interventions"), _pivot_intervention_key)

    old_tags = old.get("tags_thematiques") or []
    new_tags = new.get("tags_thematiques") or []
    merged["tags_thematiques"] = list(dict.fromkeys(list(old_tags) + list(new_tags)))

    if isinstance(merged.get("meta"), dict) and merged["meta"].get("warnings"):
        filtered = []
        for w in merged["meta"]["warnings"]:
            if w.startswith("votes introuvables") and merged.get("votes"):
                continue
            if w.startswith("mandats introuvables") and merged.get("mandats"):
                continue
            filtered.append(w)
        merged["meta"]["warnings"] = filtered

    return merged
