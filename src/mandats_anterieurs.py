#!/usr/bin/env python3
"""
mandats_anterieurs.py — Les mandats nationaux d'un candidat ANTÉRIEURS à la
couverture de l'Assemblée, depuis une table committée et relue (#860).

## Pourquoi une table, et pas une collecte

Les données de l'Assemblée commencent le 19/06/2002 (XIIe législature). Avant,
une carrière existe — 5 des 16 candidats déclarés qui ont un acteur AN en ont
une, mesuré le 11/09/2026 — et le corpus n'en dit rien : le seul critère qu'il
permet, « premier mandat lu », s'est trompé 3 fois sur 5.

Les sources primaires sont hétérogènes — Sycomore pour les députés, décrets au
Journal officiel pour le Gouvernement — et la population est de 11 lignes pour
5 personnes. Trois collecteurs pour cela seraient trois sources hors AGENTS §7
à maintenir ; une table relue, dont chaque ligne porte sa source primaire, suit
le modèle de la correspondance slug ↔ acteur (#525). Arbitrage de la
propriétaire, 11/09/2026.

## Relu, ou pas relu

Un slug présent dans la table a été relu : sa liste, vide ou non, est complète.
Un slug absent ne l'a pas été, et la fiche le dit — `mandats_anterieurs: null`
et `mandats_anterieurs_non_resolu.motif = "non_relu"` —, parce qu'absent n'est
pas « aucun » (AGENTS §2 règle 5).

## Un champ dérivé, recalculé à l'écriture

Comme `chambres` (#493) ou `meta.licence_donnees` (#530), le champ ne se
fusionne pas : `appliquer_mandats_anterieurs` le repose depuis la table juste
avant l'écriture du pivot, si bien qu'une ligne corrigée dans la table se
corrige sur la fiche au run suivant, et qu'une ligne retirée en disparaît.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

from schema_pivot import (
    KNOWN_INSTITUTIONS_ANTERIEURES,
    KNOWN_MOTIFS_MANDAT_ANTERIEUR_NON_RESOLU,
)

CHEMIN_TABLE = Path("raw_data") / "mandats_anterieurs.json"

#: Premier jour des données de l'Assemblée : la XIIe législature.
BORNE_COUVERTURE_AN = "2002-06-19"

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class TableMandatsAnterieursInvalide(ValueError):
    """La table des mandats antérieurs est illisible ou viole un invariant."""


def _valider_ligne(slug: str, i: int, ligne: Any) -> None:
    libelle = f"{slug}[{i}]"
    if not isinstance(ligne, dict):
        raise TableMandatsAnterieursInvalide(f"{libelle} : ligne non-objet.")
    if ligne.get("institution") not in KNOWN_INSTITUTIONS_ANTERIEURES:
        raise TableMandatsAnterieursInvalide(
            f"{libelle} : institution {ligne.get('institution')!r} hors de "
            f"{sorted(KNOWN_INSTITUTIONS_ANTERIEURES)} — étendre le frozenset, "
            "jamais le contourner (le Sénat attend la reprise de #528)."
        )
    for cle in ("libelle", "debut", "source_url", "verifie_le"):
        if not ligne.get(cle):
            raise TableMandatsAnterieursInvalide(f"{libelle} : '{cle}' absent.")
    if not _DATE.match(ligne["debut"]):
        raise TableMandatsAnterieursInvalide(f"{libelle} : debut {ligne['debut']!r} non ISO.")
    if not str(ligne["source_url"]).startswith("https://"):
        raise TableMandatsAnterieursInvalide(
            f"{libelle} : source_url doit être une URL https — chaque fait porte "
            "sa source primaire (§2 règle 2)."
        )
    fin = ligne.get("fin")
    if fin is None:
        motif = (ligne.get("fin_non_resolue") or {}).get("motif")
        if motif not in KNOWN_MOTIFS_MANDAT_ANTERIEUR_NON_RESOLU:
            raise TableMandatsAnterieursInvalide(
                f"{libelle} : une fin nulle exige 'fin_non_resolue.motif' dans "
                f"{sorted(KNOWN_MOTIFS_MANDAT_ANTERIEUR_NON_RESOLU)} — une absence "
                "sans cause est refusée (§2 règle 5)."
            )
        borne = ligne["debut"]
    else:
        if not _DATE.match(str(fin)) or fin < ligne["debut"]:
            raise TableMandatsAnterieursInvalide(f"{libelle} : fin {fin!r} invalide.")
        if "fin_non_resolue" in ligne:
            raise TableMandatsAnterieursInvalide(
                f"{libelle} : 'fin_non_resolue' sur une fin renseignée."
            )
        borne = fin
    if borne >= BORNE_COUVERTURE_AN:
        raise TableMandatsAnterieursInvalide(
            f"{libelle} : se termine le {borne}, dans la couverture de l'Assemblée "
            f"(depuis le {BORNE_COUVERTURE_AN}). Cette table ne porte que ce que "
            "le corpus ne peut pas porter ; un trou après la borne est un autre "
            "défaut (#859)."
        )


def charger_table(chemin: Optional[Path] = None) -> dict[str, list[dict[str, Any]]]:
    """`slug → lignes`, table validée. Lève plutôt que de rendre une table partielle."""
    chemin = Path(chemin) if chemin is not None else CHEMIN_TABLE
    try:
        document = json.loads(chemin.read_text(encoding="utf-8"))
    except OSError as exc:
        raise TableMandatsAnterieursInvalide(f"{chemin} illisible : {exc}") from exc
    except ValueError as exc:
        raise TableMandatsAnterieursInvalide(f"{chemin} : JSON invalide — {exc}") from exc
    candidats = document.get("candidats")
    if not isinstance(candidats, dict):
        raise TableMandatsAnterieursInvalide(f"{chemin} : 'candidats' absent ou non-objet.")
    for slug, lignes in candidats.items():
        if not isinstance(lignes, list):
            raise TableMandatsAnterieursInvalide(f"{slug} : liste attendue.")
        for i, ligne in enumerate(lignes):
            _valider_ligne(slug, i, ligne)
        debuts = [l["debut"] for l in lignes]
        if debuts != sorted(debuts):
            raise TableMandatsAnterieursInvalide(f"{slug} : lignes non triées par début.")
    return candidats


def appliquer_mandats_anterieurs(
    profil: dict[str, Any], table: dict[str, list[dict[str, Any]]]
) -> None:
    """Repose `mandats_anterieurs` sur un pivot de CANDIDAT DÉCLARÉ, depuis la table.

    Sans effet sur un membre de roster : il n'est pas candidat, et ne publie pas
    de fiche. Relu : la liste (éventuellement vide). Non relu : `null` et le
    motif. Jamais fusionné — recalculé à chaque écriture.
    """
    if (profil.get("meta") or {}).get("provenance") != "candidat_declare":
        profil.pop("mandats_anterieurs", None)
        profil.pop("mandats_anterieurs_non_resolu", None)
        return
    slug = profil.get("id")
    if slug in table:
        profil["mandats_anterieurs"] = [dict(ligne) for ligne in table[slug]]
        profil.pop("mandats_anterieurs_non_resolu", None)
    else:
        profil["mandats_anterieurs"] = None
        profil["mandats_anterieurs_non_resolu"] = {"motif": "non_relu"}
