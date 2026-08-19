#!/usr/bin/env python3
"""
normalize_parltrack_dumps.py — Adaptateur dumps ParlTrack → schéma pivot v1.

Convertit les données extraites par `parltrack_dumps` (dossiers rapporteur
et amendements) en entrées pivot v1 (`textes_portes[]` et `amendements[]`).

Usage :
    from normalize_parltrack_dumps import enrich_pivot_with_parltrack
    enrich_pivot_with_parltrack(profil_pivot, mep_id=131580)
"""

import time
from typing import Any, Optional

from parltrack_dumps import get_amendments_for_mep, get_dossiers_for_mep

_PARLTRACK_LICENCE = "ODbL v1.0 (ParlTrack — https://parltrack.org/dumps)"
_PARLTRACK_SOURCE_URL = "https://parltrack.org/dumps"


def _make_texte_porte(dossier: dict[str, Any]) -> dict[str, Any]:
    """Convertit un enregistrement dossier ParlTrack en entrée pivot `textes_portes`.

    Args:
        dossier: dict retourné par `parltrack_dumps.get_dossiers_for_mep`.

    Returns:
        Dict conforme au schéma `textes_portes[]`.
    """
    return {
        "titre": dossier.get("titre") or dossier.get("reference") or "",
        "role": "rapporteur",
        "type_rapport": None,
        "stade_procedural": None,
        "date_min": dossier.get("date"),
        "date_max": dossier.get("date"),
        "legislature": None,
        "source_url": dossier.get("source_url"),
    }


def _make_amendement(amendment: dict[str, Any]) -> dict[str, Any]:
    """Convertit un enregistrement amendement ParlTrack en entrée pivot `amendements`.

    Note : ParlTrack ne fournit pas de champ `sort` (outcome) fiable sur
    les dumps bruts d'amendements. On ne renseigne donc pas `sort` (null),
    conformément à la règle 5 (missing data = null, never default 0).

    **Toujours non résolu** (#431). L'index partagé `pivot_data/amendements/`
    est keyé par l'`uid` de l'Assemblée nationale (`an:<uid>`), et un amendement
    du Parlement européen n'en a pas : lui en fabriquer un serait inventer une
    clé (AGENTS.md §2.5), et le ranger dans un index dont l'identifiant annonce
    une autre source serait pire encore. Son enregistrement complet reste donc
    dans le profil sous `amendement_non_resolu` — la forme exacte que le schéma
    prévoit pour une entrée qu'on ne sait pas rattacher, ni supprimée ni devinée.

    Aucune duplication n'est perdue au passage : la normalisation ne sert à rien
    ici, un amendement PE n'étant pas recopié chez ses cosignataires (ParlTrack
    ne les fournit pas).

    Args:
        amendment: dict retourné par `parltrack_dumps.get_amendments_for_mep`.

    Returns:
        Dict conforme au schéma `amendements[]` (mapping + enregistrement).
    """
    return {
        "amendement_id": None,
        "role_signataire": "auteur_principal",
        "amendement_non_resolu": {
            "texte_vise": amendment.get("reference") or "",
            "sort": None,
            "base_juridique_irrecevabilite": None,
            "premier_signataire": None,
            "co_signataires": [],
            "type_deposant": None,
            "date": amendment.get("date"),
            "numero": amendment.get("id"),
            "source_url": amendment.get("source_url"),
        },
    }


def enrich_pivot_with_parltrack(
    profil: dict[str, Any],
    mep_id: int,
    force_download: bool = False,
) -> None:
    """Enrichit un profil pivot v1 en place avec les données ParlTrack.

    Ajoute les `textes_portes[]` (rôle rapporteur détecté) et
    `amendements[]` signés, en mode additif (n'écrase pas les entrées
    existantes).

    Les clés d'unicité utilisées pour la déduplication additive sont
    identiques à celles de `merge_profile._pivot_texte_key` et
    `merge_profile._pivot_amendement_key` :
    - `textes_portes` : source_url (si présent) sinon (titre, date_min, legislature)
    - `amendements`   : `amendement_id` si résolu, sinon, dans
      `amendement_non_resolu`, source_url (si présent) sinon
      (numero, texte_vise, date)

    Un warning est ajouté à `meta.warnings[]` si les dumps sont
    indisponibles.

    Args:
        profil: profil pivot v1 dict à enrichir (modifié en place).
        mep_id: UserID ParlTrack (entier).
        force_download: re-télécharger les dumps même si un cache existe.
    """
    meta = profil.setdefault("meta", {})
    warnings: list[str] = meta.setdefault("warnings", [])

    # --- textes_portes (rapporteur) ---
    dossiers = get_dossiers_for_mep(mep_id, force_download=force_download)
    def _tp_key(t: dict[str, Any]) -> Any:
        return t.get("source_url") or (t.get("titre"), t.get("date_min"), t.get("legislature"))

    existing_tp_keys = {
        _tp_key(t)
        for t in (profil.get("textes_portes") or [])
        if isinstance(t, dict)
    }
    new_tp = []
    for d in dossiers:
        entry = _make_texte_porte(d)
        key = _tp_key(entry)
        if key not in existing_tp_keys:
            existing_tp_keys.add(key)
            new_tp.append(entry)

    if profil.get("textes_portes") is None:
        profil["textes_portes"] = []
    profil["textes_portes"].extend(new_tp)

    # --- amendements ---
    amendments = get_amendments_for_mep(mep_id, force_download=force_download)

    def _amd_key(a: dict[str, Any]) -> Any:
        # Même clé que `merge_profile._pivot_amendement_key` : `amendement_id`
        # d'abord, puis l'enregistrement non résolu — sans quoi toutes les
        # entrées PE, qui ont toutes `amendement_id: None`, se réduiraient à une.
        if a.get("amendement_id"):
            return a["amendement_id"]
        non_resolu = a.get("amendement_non_resolu")
        if isinstance(non_resolu, dict):
            a = non_resolu
        return a.get("source_url") or (a.get("numero"), a.get("texte_vise"), a.get("date"))

    existing_amd_keys = {
        _amd_key(a)
        for a in (profil.get("amendements") or [])
        if isinstance(a, dict)
    }
    new_amds = []
    for a in amendments:
        entry = _make_amendement(a)
        key = _amd_key(entry)
        if key not in existing_amd_keys:
            existing_amd_keys.add(key)
            new_amds.append(entry)

    if profil.get("amendements") is None:
        profil["amendements"] = []
    profil["amendements"].extend(new_amds)

    # --- source ParlTrack dans sources[] ---
    has_parltrack_source = any(
        s.get("type") == "parltrack" and "dumps" in (s.get("url") or "")
        for s in (profil.get("sources") or [])
    )
    if not has_parltrack_source and (new_tp or new_amds):
        profil.setdefault("sources", []).append({
            "type": "parltrack",
            "url": _PARLTRACK_SOURCE_URL,
            "synchro_le": time.strftime("%Y-%m-%dT%H:%M:%S"),
        })

    # --- licence ---
    if new_tp or new_amds:
        existing_licence = meta.get("licence_donnees") or ""
        if _PARLTRACK_LICENCE not in existing_licence:
            if existing_licence:
                meta["licence_donnees"] = f"{existing_licence} + {_PARLTRACK_LICENCE}"
            else:
                meta["licence_donnees"] = _PARLTRACK_LICENCE

    # Warning si aucune donnée retournée (dumps peut-être indisponibles)
    if not dossiers and not amendments:
        warnings.append(
            f"ParlTrack: aucune donnée trouvée pour le MEP ID {mep_id}. "
            "Vérifier la disponibilité des dumps ou la validité du MEP ID."
        )
