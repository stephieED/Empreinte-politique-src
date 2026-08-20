#!/usr/bin/env python3
"""
normalize_europarl.py — Adaptateur Open Data Portal du Parlement européen → schéma pivot v1.

Convertit la sortie brute de `candidate_profile_ue.build_profile_ue()` en un
profil pivot v1 (défini dans `schema_pivot.py`).

Usage :
    from normalize_europarl import normalize_europarl
    pivot = normalize_europarl(raw_ue_profile, parti="Rassemblement National")
"""

import time
from typing import Any, Optional

from schema_pivot import appliquer_chambres, make_empty_profil

# Correspondance entre le type brut de l'API EP et la catégorie pivot.
_CATEGORIE_MAP: dict[str, str] = {
    "EU_INSTITUTION": "mandat_electif",
    "COMMITTEE_PARLIAMENTARY_STANDING": "commission",
    "COMMITTEE_PARLIAMENTARY_TEMPORARY": "commission",
    "COMMITTEE_PARLIAMENTARY_SUB": "commission",
    "DELEGATION_PARLIAMENTARY": "autre",
    "DELEGATION_PARLIAMENTARY_ASSEMBLY": "autre",
    "WORKING_GROUP": "commission",
    "EU_POLITICAL_GROUP": "autre",
    "NATIONAL_POLITICAL_GROUP": "autre",
    "GOVERNING_BODY": "autre",
}


def _extract_groupe(mandats_europeens: list[dict[str, Any]]) -> Optional[str]:
    """Retourne le nom du groupe politique européen le plus récent (actif en priorité)."""
    # La liste est déjà triée du plus récent au plus ancien par candidate_profile_ue.
    for m in mandats_europeens:
        if m.get("type") == "EU_POLITICAL_GROUP" and m.get("actif"):
            return m.get("organisation_nom") or m.get("organisation_sigle")
    for m in mandats_europeens:
        if m.get("type") == "EU_POLITICAL_GROUP":
            return m.get("organisation_nom") or m.get("organisation_sigle")
    return None


def normalize_europarl(
    ue_profile: dict[str, Any],
    parti: Optional[str] = None,
    provenance: str = "candidat_declare",
    slug: Optional[str] = None,
) -> dict[str, Any]:
    """Convertit un profil Open Data Portal Parlement européen en pivot v1.

    Args:
        ue_profile: sortie de `candidate_profile_ue.build_profile_ue()`.
        parti: parti politique issu de raw_data/candidats.json (optionnel).
        provenance: "candidat_declare" (défaut) ou "roster_groupe" — voir
                    schema_pivot.KNOWN_PROVENANCES. Propagé tel quel vers
                    meta.provenance du profil pivot.
        slug: slug du profil, c'est-à-dire son identifiant (#487, épic #486).
              Fourni, il devient l'`id` tel quel — même convention que
              `normalize_nosdeputes`, pour que l'espace d'identifiants pivot
              n'ait qu'une seule forme.
              Absent, l'`id` retombe sur `europarl:<identifiant_pe>`. Ce repli
              n'est pas une exception de confort : `ue_profile` ne porte pas de
              slug, et le seul candidat qu'on pourrait en tirer serait dérivé
              de `nom_complet`, donc d'une donnée de collecte — exactement le
              défaut que #487 retire. Mieux vaut un identifiant de source
              explicite qu'un slug inventé.

    Returns:
        Profil pivot v1 dict (chambre: "PE").
    """
    mep_id = str(ue_profile["identifiant_pe"]) if ue_profile.get("identifiant_pe") is not None else ""
    nom = ue_profile.get("nom_complet") or None
    url_source = ue_profile.get("url_source") or None
    meta_ue = ue_profile.get("meta") or {}
    synchro_le = meta_ue.get("genere_le") or time.strftime("%Y-%m-%dT%H:%M:%S%z")
    licence = meta_ue.get("licence_donnees") or None

    profil_id = slug if slug else f"europarl:{mep_id}"
    profil = make_empty_profil(id_=profil_id, nom=nom, provenance=provenance)
    # `chambres`/`chambre` sont dérivées en fin de fonction, une fois `mandats[]`
    # construit (#493) : une seule fabrique pour les deux champs.
    profil["parti"] = parti
    profil["sources"] = [
        {
            "type": "europarl",
            "url": url_source,
            "synchro_le": synchro_le,
        }
    ]
    profil["meta"]["licence_donnees"] = licence
    profil["meta"]["genere_le"] = synchro_le

    mandats_europeens = ue_profile.get("mandats_europeens") or []
    profil["groupe"] = _extract_groupe(mandats_europeens)

    for m in mandats_europeens:
        categorie = _CATEGORIE_MAP.get(m.get("type") or "", "autre")
        label = m.get("organisation_nom") or m.get("organisation_sigle") or ""
        fonction = m.get("role_label") or m.get("role") or ""
        mandat: dict[str, Any] = {
            "label": label,
            "categorie": categorie,
            "fonction": fonction,
            "debut": m.get("debut"),
            "fin": m.get("fin"),
            "actif": bool(m.get("actif")),
            "source_url": url_source,
        }
        if categorie == "mandat_electif":
            # #492 : seul cas où la chambre est établie sans ambiguïté par la
            # source elle-même — le mandat vient du Parlement européen, et son
            # `source_url` pointe déjà sur europarl.europa.eu. C'est aussi le
            # seul `mandat_electif` du corpus qui porte une `source_url` (14 sur
            # 228, mesuré sur `f5a828b`).
            mandat["chambre"] = "PE"
        profil["mandats"].append(mandat)

    # #493 : `chambres` dérivée des mandats estampillés ci-dessus. Le repli
    # `"PE"` couvre le seul cas restant — un profil européen sans aucun
    # `mandat_electif` (`mandats_europeens` ne portant que des groupes/commissions) :
    # la chambre reste alors une donnée de source, le Parlement européen étant la
    # seule chambre que ce normaliseur sache lire.
    profil["chambre"] = "PE"                 # repli, consommé par appliquer_chambres
    appliquer_chambres(profil)

    return profil
