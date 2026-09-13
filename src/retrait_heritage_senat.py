#!/usr/bin/env python3
"""
retrait_heritage_senat.py — Ce que la collecte sénatoriale remplace (#885, point 5).

Deux retraits, et ils n'ont ni la même cause ni le même moment
---------------------------------------------------------------
**Une entrée `sources[]` qui ment sur sa provenance.** `jean-luc-melenchon`
porte un `sources[]` de type `nossenateurs` dont l'URL est un **article de
LCP** — `lcp.fr/actualites/presidentielle-2027-la-liste-des-candidats…`. Elle
vient de `raw_data/candidats.json`, où ce lien atteste que l'intéressé est
**candidat déclaré** ; ce n'est pas une source de données parlementaires, et
encore moins Regards Citoyens. Une fusion ancienne l'a rangée là, et la fusion
additive l'y garde (#729).

Le défaut est autonome : il ne dépend d'aucune collecte, et il se corrige
**maintenant**. Un profil qui déclare une provenance qu'il n'a pas fausse la
traçabilité (§2 règle 2) et, ici, la licence qu'il en tire (§7).

**Des mandats que le Sénat remplace.** `bruno-retailleau` publie « Mandat
parlementaire (Les Républicains) » depuis le 26/09/2004, **sans fin** ;
`jean-luc-melenchon` le sien de 2004 à 2010. La source sénatoriale en donne
respectivement **4** et **3**, bornés, avec leurs motifs.

Celui-là **ne se fait pas avant** que la publication sénatoriale soit branchée :
retirer d'abord viderait la fiche de Retailleau de son mandat parlementaire, et
un corpus qui perd un fait en attendant son remplaçant publie un trou.

Ce que le retrait ne touche pas
--------------------------------
Les **8 autres** entrées sans `categorie_source` de `bruno-retailleau` — des
commissions, groupes d'études et organismes extra-parlementaires, tous sans
date. C'est la mesure de #878 qui tient : le « doublon hérité » fait **2
entrées, pas 9**.

Leur raison a changé, elle. #878 disait « 2, parce que seules 2 ont un
équivalent chez l'Assemblée ». Aujourd'hui les 9 en ont un — **sénatorial**. Ce
qui rend les 7 autres retirables un jour, c'est qu'on les remplace, pas qu'elles
soient fausses ; et ce jour-là, c'est un appariement entrée par entrée qu'il
faudra, pas un retrait en bloc.
"""

from __future__ import annotations

from typing import Any, Optional

from licences import MOTIFS_URL_REGARDS_CITOYENS

#: Les types de source qui **prétendent** venir de Regards Citoyens. Une entrée
#: de ce type dont l'URL n'en vient pas est une provenance fausse.
TYPES_REGARDS_CITOYENS = frozenset({"nosdeputes", "nossenateurs"})


def source_ment_sur_sa_provenance(source: dict[str, Any]) -> bool:
    """True si l'entrée se dit Regards Citoyens et que son URL dit autre chose.

    Le critère est **l'URL**, pas notre opinion : `licences.MOTIFS_URL_REGARDS_CITOYENS`
    est le référentiel des domaines, et le recopier ici ferait de ce module un
    second référentiel (#530).

    Une entrée **sans URL** n'est pas jugée : elle ne dit rien, et une absence
    n'est pas un mensonge (§2 règle 5).
    """
    if source.get("type") not in TYPES_REGARDS_CITOYENS:
        return False
    url = source.get("url")
    if not isinstance(url, str) or not url.strip():
        return False
    return not any(motif in url.lower() for motif in MOTIFS_URL_REGARDS_CITOYENS)


def retirer_sources_menteuses(profil: dict[str, Any]) -> list[dict[str, Any]]:
    """Retire ces entrées de `sources[]` et rend celles qui sont parties.

    Ne recompose pas `meta.licence_donnees` : c'est un champ dérivé, et sa
    fabrique est `licences.appliquer_licence_donnees` (§7). L'appelant la lance
    après, comme après toute étape qui déplace `sources[]`.
    """
    sources = profil.get("sources") or []
    retirees = [s for s in sources if isinstance(s, dict) and source_ment_sur_sa_provenance(s)]
    if retirees:
        profil["sources"] = [s for s in sources if s not in retirees]
    return retirees


def mandats_electifs_remplaces(
    profil: dict[str, Any],
    chambre_remplacante: str = "Senat",
) -> list[dict[str, Any]]:
    """Les mandats électifs **non estampillés** qu'une source datée remplace.

    Rend la liste sans rien retirer : ce retrait attend la publication, et une
    fonction qui retire ce qui n'a pas encore de remplaçant produit un trou.

    Le critère est l'absence de `categorie_source` — « personne n'a établi cette
    catégorie » (#718) — **et** la présence d'au moins un mandat de la même
    chambre qui, lui, est estampillé. Sans remplaçant, rien n'est proposé : c'est
    ce qui empêche le retrait de s'exécuter trop tôt.
    """
    mandats = profil.get("mandats") or []
    remplacants = [m for m in mandats if isinstance(m, dict)
                   and m.get("categorie_source")
                   and m.get("chambre") == chambre_remplacante
                   and m.get("categorie") == "mandat_electif"]
    if not remplacants:
        return []
    return [m for m in mandats if isinstance(m, dict)
            and m.get("categorie") == "mandat_electif"
            and not m.get("categorie_source")]
