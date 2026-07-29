#!/usr/bin/env python3
"""
normalize_nosdeputes.py — Adaptateur NosDéputés/NosSénateurs → schéma pivot v1.

Convertit un profil JSON produit par candidate_profile.py (format brut
NosDéputés.fr / NosSénateurs.fr) vers le schéma pivot commun défini dans
schema_pivot.py.

Ce module est volontairement découplé de la collecte : il ne fait aucun
appel réseau et ne connaît pas le mécanisme de téléchargement.

Usage :
    from normalize_nosdeputes import normalize_nosdeputes
    pivot = normalize_nosdeputes(raw_profile)

    # Enrichissement optionnel depuis candidats.json :
    pivot["parti"] = "La France Insoumise"
"""

import time
from typing import Any, Optional

from schema_pivot import SCHEMA_VERSION, make_empty_profil

# Correspondance chambre (clé du profil brut) → valeur normalisée du pivot.
_CHAMBRE_MAP: dict[str, str] = {
    "deputes": "AN",
    "senateurs": "Senat",
}

# Type de source selon la chambre.
_SOURCE_TYPE_MAP: dict[str, str] = {
    "deputes": "nosdeputes",
    "senateurs": "nossenateurs",
}


def _first(*values: Any) -> Any:
    """Retourne la première valeur non-None parmi les arguments."""
    for v in values:
        if v is not None:
            return v
    return None


# ---------------------------------------------------------------------------
# Normaliseurs de sections individuelles
# ---------------------------------------------------------------------------

def _normalize_vote(v: dict[str, Any]) -> dict[str, Any]:
    """Normalise un vote brut NosDéputés/AN vers le format pivot."""
    return {
        "date": v.get("date"),
        "texte": v.get("titre") or "",
        "position": v.get("position") or "",
        "numero_scrutin": str(v["numero_scrutin"]) if v.get("numero_scrutin") is not None else None,
        "sort": v.get("sort"),
        # groupe_au_moment_du_vote : null par défaut ; enrichissable en post-traitement
        # (NosDéputés/AN open data ne fournit pas l'historique de groupe par scrutin).
        "groupe_au_moment_du_vote": v.get("groupe_au_moment_du_vote"),
        # url_source présent uniquement dans les votes fallback nosdeputes
        "source_url": v.get("url_source"),
    }


def _normalize_mandat(m: dict[str, Any]) -> dict[str, Any]:
    """Normalise un mandat/responsabilité brut vers le format pivot."""
    return {
        "label": m.get("label") or "",
        "categorie": m.get("categorie") or "autre",
        # Dans le format brut, la fonction s'appelle "type" (héritage de l'API)
        "fonction": m.get("type") or "membre",
        "debut": m.get("debut"),
        "fin": m.get("fin"),
        "actif": bool(m.get("actif")),
        "source_url": None,
    }


def _normalize_texte_porte(d: dict[str, Any]) -> dict[str, Any]:
    """Normalise un dossier législatif brut vers le format pivot `textes_portes`.

    Note : NosDéputés ne distingue pas explicitement auteur et rapporteur dans
    les dossiers ; on utilise "rapporteur" par défaut (rôle le plus fréquent pour
    les dossiers associés à un parlementaire via l'API).
    """
    return {
        "titre": d.get("titre") or "",
        "role": "rapporteur",
        "date_min": d.get("date_min"),
        "date_max": d.get("date_max"),
        "legislature": d.get("legislature"),
        "source_url": _first(d.get("url_source"), d.get("url_institution")),
    }


def _normalize_intervention(i: dict[str, Any]) -> dict[str, Any]:
    """Normalise une intervention brute vers le format pivot."""
    return {
        "date": _first(i.get("date"), i.get("created_at")),
        "type_detail": i.get("type_detail"),
        "sujet": i.get("sujet"),
        "texte": i.get("texte"),
        "fonction": i.get("fonction"),
        "format": i.get("format"),
        "mots_cles": list(i.get("mots_cles") or []),
        "source_url": _first(i.get("url_detail"), i.get("url")),
    }


# ---------------------------------------------------------------------------
# Fonction principale
# ---------------------------------------------------------------------------

def normalize_nosdeputes(raw_profile: dict[str, Any], parti: Optional[str] = None) -> dict[str, Any]:
    """Convertit un profil brut NosDéputés/NosSénateurs vers le schéma pivot v1.

    Args:
        raw_profile: dict produit par candidate_profile.build_profile().
        parti: parti politique de l'élu (optionnel ; peut être passé depuis
               candidats.json car non fourni par l'API NosDéputés).

    Returns:
        Profil pivot dict conforme au schéma v1.
    """
    slug = raw_profile.get("slug") or ""
    chambre_raw = raw_profile.get("chambre") or ""
    chambre = _CHAMBRE_MAP.get(chambre_raw, chambre_raw or None)
    source_type = _SOURCE_TYPE_MAP.get(chambre_raw, "nosdeputes")

    identite = raw_profile.get("identite") or {}
    nom = identite.get("nom_complet") or slug.replace("-", " ").title()

    # Timestamp de synchro depuis le méta du profil brut (ou maintenant si absent)
    meta_raw = raw_profile.get("meta") or {}
    synchro_sources = meta_raw.get("synchro_sources") or {}
    synchro_le = synchro_sources.get("nosdeputes")
    if synchro_le is None and "nosdeputes" not in synchro_sources:
        synchro_le = meta_raw.get("genere_le") or time.strftime("%Y-%m-%dT%H:%M:%S%z")
    # --- Profil pivot de base ---
    profil: dict[str, Any] = make_empty_profil(f"{source_type}:{slug}", nom)
    profil["chambre"] = chambre
    profil["parti"] = parti
    profil["groupe"] = identite.get("groupe_nom") or identite.get("groupe_sigle")

    # --- Sources ---
    source_url = raw_profile.get("source") or f"https://www.nosdeputes.fr/{slug}"
    sources: list[dict[str, Any]] = [
        {
            "type": source_type,
            "url": source_url,
            "synchro_le": synchro_le,
        }
    ]
    votes_source = raw_profile.get("votes_source")
    if votes_source and "assemblee-nationale" in (votes_source or "").lower():
        an_synchro = (meta_raw.get("synchro_sources") or {}).get("assemblee_nationale") or synchro_le
        sources.append({
            "type": "assemblee_nationale",
            "url": "https://data.assemblee-nationale.fr/",
            "synchro_le": an_synchro,
        })
    profil["sources"] = sources

    # --- Sections principales ---
    profil["mandats"] = [_normalize_mandat(m) for m in (raw_profile.get("mandats") or [])]
    profil["votes"] = [_normalize_vote(v) for v in (raw_profile.get("votes") or [])]
    profil["textes_portes"] = [_normalize_texte_porte(d) for d in (raw_profile.get("dossiers_legislatifs") or [])]
    profil["interventions"] = [_normalize_intervention(i) for i in (raw_profile.get("interventions") or [])]

    # --- Tags thématiques bruts : agrégation des mots-clés des interventions ---
    # Pas d'harmonisation thématique à ce stade (Phase 4 à venir).
    tags: set[str] = set()
    for i in (raw_profile.get("interventions") or []):
        for kw in (i.get("mots_cles") or []):
            cleaned = kw.strip().lower()
            if cleaned:
                tags.add(cleaned)
    profil["tags_thematiques"] = sorted(tags)

    # --- Métadonnées ---
    profil["meta"]["licence_donnees"] = meta_raw.get("licence_donnees") or ""
    profil["meta"]["warnings"] = list(meta_raw.get("warnings") or [])

    # Propagation des avertissements de synchro depuis le profil brut
    synchro_sources = meta_raw.get("synchro_sources") or {}
    if synchro_sources.get("nosdeputes") is None:
        profil["meta"]["warnings"].append(
            "synchro_sources.nosdeputes : aucune synchro réussie enregistrée dans le profil source."
        )

    return profil
