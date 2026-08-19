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
        "texte": v.get("titre") or None,
        "position": v.get("position") or None,
        "numero_scrutin": str(v["numero_scrutin"]) if v.get("numero_scrutin") is not None else None,
        # Législature du scrutin (#403) : le numéro de scrutin repart de 1 à
        # chaque législature, donc lui seul n'identifie pas un scrutin dès lors
        # que plusieurs législatures sont agrégées. `null` pour les votes
        # collectés avant #403 et pour les sources qui ne la fournissent pas.
        "legislature": str(v["legislature"]) if v.get("legislature") is not None else None,
        "sort": v.get("sort"),
        "type_scrutin": v.get("type_scrutin"),
        "type_vote": v.get("type_vote") or "vote_texte",
        "texte_lie_id": v.get("texte_lie_id"),
        # groupe_au_moment_du_vote : null par défaut ; enrichissable en post-traitement
        # (NosDéputés/AN open data ne fournit pas l'historique de groupe par scrutin).
        "groupe_au_moment_du_vote": v.get("groupe_au_moment_du_vote"),
        # url_source présent uniquement dans les votes fallback nosdeputes
        "source_url": v.get("url_source"),
    }


def _normalize_mandat(m: dict[str, Any]) -> dict[str, Any]:
    """Normalise un mandat/responsabilité brut vers le format pivot."""
    return {
        "label": m.get("label") or None,
        "categorie": m.get("categorie") or None,
        # Dans le format brut, la fonction s'appelle "type" (héritage de l'API)
        "fonction": m.get("type") or "membre",
        "debut": m.get("debut"),
        "fin": m.get("fin"),
        "actif": bool(m.get("actif")),
        "source_url": m.get("source_url"),
        "position_dans_hemicycle": m.get("position_dans_hemicycle"),
        "mode_declenchement": m.get("mode_declenchement"),
        "suspendu_pour_fonction_gouvernementale": m.get("suspendu_pour_fonction_gouvernementale"),
    }


def _normalize_texte_porte(d: dict[str, Any]) -> dict[str, Any]:
    """Normalise un dossier législatif brut vers le format pivot `textes_portes`.

    NosDéputés ne distingue pas systématiquement auteur et rapporteur dans les
    dossiers. Le rôle reste donc nul quand la source ne le fournit pas : aucune
    inférence n'est faite à partir du volume d'interventions.
    """
    return {
        "titre": d.get("titre") or None,
        "role": d.get("role"),
        "type_rapport": d.get("type_rapport"),
        "stade_procedural": d.get("stade_procedural"),
        "date_min": d.get("date_min"),
        "date_max": d.get("date_max"),
        "legislature": d.get("legislature"),
        "source_url": _first(d.get("url_source"), d.get("url_institution")),
    }


def _normalize_intervention(i: dict[str, Any]) -> dict[str, Any]:
    """Normalise une intervention brute vers le format pivot."""
    result: dict[str, Any] = {
        "date": _first(i.get("date"), i.get("created_at")),
        "type_detail": i.get("type_detail"),
        "sujet": i.get("sujet"),
        "texte": i.get("texte"),
        "fonction": i.get("fonction"),
        "format": i.get("format"),
        "mots_cles": list(i.get("mots_cles") or []),
        "source_url": _first(i.get("url_detail"), i.get("url")),
        # Champs pivot officiels — renseignés depuis les données Syceron (débats AN)
        # quand disponibles, null sinon (interventions NosDéputés scraping).
        # La présence de seance_ref ou session_ref identifie une intervention Syceron.
        "theme_officiel": i.get("sujet") if i.get("seance_ref") or i.get("session_ref") else None,
        "seance": (
            {
                "ref": i.get("seance_ref"),
                "session_ref": i.get("session_ref"),
            }
            if i.get("seance_ref")
            else None
        ),
        "dossier": (
            {"point_ordre_du_jour": i.get("point_ordre_du_jour")}
            if i.get("point_ordre_du_jour")
            else None
        ),
        "source": (
            {
                "type": "syceron",
                "url": i.get("source_url") or i.get("url"),
                "source_id": i.get("source_id"),
                "legislature": i.get("legislature"),
            }
            if i.get("seance_ref") or i.get("session_ref")
            else None
        ),
    }
    # Champs supplémentaires pour les questions parlementaires officielles (type_detail == "question").
    if i.get("type_detail") == "question":
        result["sous_type"] = i.get("sous_type")      # "QE" | "QG" | "QOSD"
        result["ministere"] = i.get("ministere")       # ministère interrogé
        result["reponse"] = i.get("reponse")           # texte de la réponse (si disponible)
        result["date_reponse"] = i.get("date_reponse") # date JO de la réponse
    return result


def _normalize_amendement(a: dict[str, Any], own_id: str) -> dict[str, Any]:
    """Normalise un amendement officiel (Assemblée nationale) vers le format pivot.

    Le flux brut peut contenir deux cas : l'élu auteur principal ou simple
    cosignataire (champ `role_signataire`).
    """
    role_signataire = a.get("role_signataire")
    premier_signataire = a.get("premier_signataire")
    # Compatibilité ascendante : pour les données historiques sans role explicite,
    # on conserve le comportement ancien (premier_signataire = élu du profil).
    if role_signataire != "cosignataire":
        premier_signataire = own_id

    return {
        # Identifiant AN de l'amendement : seule clé unique, propagée telle
        # quelle du brut au pivot (voir
        # docs/technical_decisions.md#amendements-cle-uid). `None` pour les
        # entrées collectées avant son extraction.
        "uid": a.get("uid"),
        "texte_vise": a.get("texte_vise"),
        "sort": a.get("sort"),
        "base_juridique_irrecevabilite": a.get("base_juridique_irrecevabilite"),
        "role_signataire": role_signataire,
        "premier_signataire": premier_signataire,
        "co_signataires": list(a.get("co_signataires") or []),
        "type_deposant": a.get("type_deposant"),
        "date": a.get("date"),
        "numero": a.get("numero"),
        "source_url": a.get("source_url"),
    }


# ---------------------------------------------------------------------------
# Fonction principale
# ---------------------------------------------------------------------------

def normalize_nosdeputes(
    raw_profile: dict[str, Any],
    parti: Optional[str] = None,
    provenance: str = "candidat_declare",
) -> dict[str, Any]:
    """Convertit un profil brut NosDéputés/NosSénateurs vers le schéma pivot v1.

    Args:
        raw_profile: dict produit par candidate_profile.build_profile().
        parti: parti politique de l'élu (optionnel ; peut être passé depuis
               candidats.json car non fourni par l'API NosDéputés).
        provenance: "candidat_declare" (défaut) ou "roster_groupe" — voir
                    schema_pivot.KNOWN_PROVENANCES. Propagé tel quel vers
                    meta.provenance du profil pivot.

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
    if "nosdeputes" not in synchro_sources:
        synchro_le = meta_raw.get("genere_le") or time.strftime("%Y-%m-%dT%H:%M:%S%z")
    # --- Profil pivot de base ---
    profil: dict[str, Any] = make_empty_profil(f"{source_type}:{slug}", nom, provenance=provenance)
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

    # --- Identité (profession/naissance/HATVP) : uniquement si au moins un champ
    # est renseigné, sinon on laisse `identite` à None (valeur par défaut). ---
    identite_champs = {
        "profession": identite.get("profession"),
        "date_naissance": identite.get("date_naissance"),
        "lieu_naissance": identite.get("lieu_naissance"),
        "num_circo": identite.get("num_circo"),
        "uri_hatvp": identite.get("uri_hatvp"),
        "source_url": identite.get("url_an_ou_senat") or source_url,
    }
    if any(v for k, v in identite_champs.items() if k != "source_url"):
        profil["identite"] = identite_champs

    # --- Sections principales ---
    profil["mandats"] = [_normalize_mandat(m) for m in (raw_profile.get("mandats") or [])]
    profil["votes"] = [_normalize_vote(v) for v in (raw_profile.get("votes") or [])]
    profil["textes_portes"] = [_normalize_texte_porte(d) for d in (raw_profile.get("dossiers_legislatifs") or [])]
    profil["interventions"] = [_normalize_intervention(i) for i in (raw_profile.get("interventions") or [])]
    profil["amendements"] = [_normalize_amendement(a, profil["id"]) for a in (raw_profile.get("amendements") or [])]

    # --- Tags thématiques bruts : source hybride — thème officiel Syceron (quand
    # disponible via `theme_officiel`) ou mots-clés scraping NosDéputés en fallback.
    # `theme_officiel` est préféré car il provient du compte rendu officiel de l'AN.
    tags: set[str] = set()
    for i in profil.get("interventions") or []:
        theme = i.get("theme_officiel")
        if theme and isinstance(theme, str):
            cleaned = theme.strip().lower()
            if cleaned:
                tags.add(cleaned)
        else:
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
