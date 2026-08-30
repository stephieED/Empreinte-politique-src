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

Le bloc `meta` est **composé clé par clé** (`fusionner_meta`, #600), et non pris
au dernier écrivain : `warnings` est l'union par famille des deux côtés,
`synchro_sources` est fusionné par source à la valeur la plus récente,
`genere_le` est le plus récent des deux, et chaque autre clé a une règle nommée
dans `REGLES_META`. Sans cela, l'ordre des jobs du workflow décidait quels
avertissements étaient publiés — et `meta.warnings[]` est le véhicule de la
règle « donnée manquante = donnée manquante » (AGENTS.md §2.5).

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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from candidate_profile import (
    WARNING_AUCUN_MANDAT_FR,
    WARNING_PREFIX_IDENTITE_INTROUVABLE,
    WARNING_PREFIX_MANDATS_INTROUVABLES,
    WARNING_PREFIX_VOTES_INTROUVABLES,
    WARNING_PREFIX_AMENDEMENTS_INDISPONIBLES,
    WARNING_PREFIX_BUDGET_COLLECTE,
    WARNING_PREFIX_BUDGET_INTERVENTIONS,
    WARNING_PREFIX_INTERVENTIONS_SYCERON_AUCUNE,
    WARNING_PREFIX_INTERVENTIONS_SYCERON_INDISPONIBLES,
    WARNING_PREFIX_QUESTIONS_INDISPONIBLES,
    WARNING_PREFIX_DEFAUT_COLLECTE,
)
from licences import appliquer_licence_donnees
from normalize_profil import WARNING_PREFIX_CHAMBRES_NON_CORROBOREE
from profil_brut import (
    PartitionIllisible,
    charger_profil_brut,
    ecrire_profil_brut,
)
from schema_pivot import appliquer_chambres

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


def backfill_mandat_chambre(
    merged: list[dict[str, Any]],
    new_list: Optional[list[dict[str, Any]]],
    key_fn: Callable[[dict[str, Any]], Key],
) -> list[dict[str, Any]]:
    """Reporte la `chambre` d'un mandat neuf sur l'entrée ancienne de même clé (#492).

    `merge_lists_by_key` est additif pur : l'entrée ancienne gagne, et sa clé
    (`categorie`, `fonction`, `label`, `debut`) ne contient pas la chambre.
    Sans ce report, un mandat déjà présent dans le corpus n'acquerrait **jamais**
    son estampille de chambre : la version neuve, estampillée, porte la même clé
    et serait écartée à chaque régénération. Le champ resterait à `null` pour
    toujours en fusion additive, et ne se remplirait qu'en `cold_start`/
    `--no-merge`.

    Le report est strictement croissant en information : il ne remplit qu'un
    champ **absent ou nul**, n'écrase jamais une chambre déjà déterminée, ne
    touche aucun autre champ et ne réordonne rien. C'est le même principe que
    `_prefer_non_empty` sur les scalaires, appliqué à un champ d'entrée de liste.
    Il est volontairement limité à `chambre` : généraliser le report ferait de la
    fusion additive une fusion par champ, ce qu'elle n'est pas.
    """
    if not new_list:
        return merged

    chambres_neuves: dict[Key, str] = {}
    for m in new_list:
        if not isinstance(m, dict):
            continue
        chambre = m.get("chambre")
        if chambre:
            chambres_neuves.setdefault(key_fn(m), chambre)

    if not chambres_neuves:
        return merged

    result: list[dict[str, Any]] = []
    for m in merged:
        if isinstance(m, dict) and not m.get("chambre"):
            chambre = chambres_neuves.get(key_fn(m))
            if chambre:
                m = {**m, "chambre": chambre}
        result.append(m)
    return result


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


#: Liste métier nommée par un warning `WARNING_PREFIX_DEFAUT_COLLECTE` (#562) ->
#: champ(s) du profil qui la portent. Les deux schémas sont couverts :
#: `dossiers_legislatifs` côté brut, `textes_portes` côté pivot.
_CHAMPS_PAR_LISTE_DEFAUT_COLLECTE: dict[str, tuple[str, ...]] = {
    "amendements": ("amendements",),
    "interventions": ("interventions",),
    "textes_portes": ("textes_portes", "dossiers_legislatifs"),
    "votes": ("votes",),
    "mandats": ("mandats",),
}


def _defaut_collecte_dementi_par_les_donnees(profile: dict[str, Any], warning: str) -> bool:
    """Un défaut de collecte que la fusion a démenti (#562).

    Même règle que pour « amendements indisponibles » juste en dessous, et pour
    la même raison : la fusion additive peut avoir restauré la liste depuis le
    fichier déjà publié. Continuer à la déclarer non collectée serait faux, et
    `couverture_profil` publierait un `non_collecte` sur une liste pleine.

    Le patron est celui du préfixe de panne, pas celui de
    `WARNING_PREFIX_BUDGET_*` (jamais retiré) : une troncature par budget décrit
    une liste dont le compte est incertain, un défaut de collecte décrit une
    étape qui n'a rien rendu du tout.
    """
    for liste, champs in _CHAMPS_PAR_LISTE_DEFAUT_COLLECTE.items():
        if warning.startswith(f"{WARNING_PREFIX_DEFAUT_COLLECTE} ({liste})"):
            return any(profile.get(champ) for champ in champs)
    return False


def _aucun_mandat_fr_dementi(profile: dict[str, Any], warning: str) -> bool:
    """Le profil minimal de #484, démenti par l'identité que la fusion a gardée.

    `WARNING_AUCUN_MANDAT_FR` n'est pas une trace de ce qu'un run n'a pas
    collecté (comme les préfixes de budget, jamais retirés) : c'est une
    AFFIRMATION sur la personne — « slug absent du référentiel Assemblée
    nationale, ou identité introuvable ». Une identité AN présente dans le
    profil fusionné dément ses deux membres à la fois.

    Le critère est l'identité, jamais `mandats` : un profil PE en publie
    (`jordan-bardella`, 22 mandats européens après normalisation) sans qu'aucun
    mandat FRANÇAIS soit connu. Purger sur `mandats` retirerait un avertissement
    vrai.
    """
    if not warning.startswith(WARNING_AUCUN_MANDAT_FR):
        return False
    identite = profile.get("identite")
    return isinstance(identite, dict) and not bloc_sans_fond(
        identite, BLOCS_PROTEGES_DU_VIDE["identite"]
    )


def _interventions_syceron_dementies(profile: dict[str, Any], warning: str) -> bool:
    """Les deux avertissements Syceron, démentis par les interventions publiées.

    L'union des warnings (#600) peut faire **ressusciter** l'avertissement d'un
    écrivain qui n'a pas obtenu l'archive Syceron, sur un profil où l'autre
    écrivain — ou la fusion additive — a rendu les interventions. Le laisser
    passer publierait une panne que le fichier dément, exactement ce que
    `_defaut_collecte_dementi_par_les_donnees` évite déjà pour les autres listes.
    C'est donc l'extension du mécanisme existant, pas un second mécanisme.

    Les deux familles de #560 sont couvertes ensemble, et le critère les
    distingue sans avoir à les séparer : `..._INDISPONIBLES` est une **panne**
    (l'archive n'a pas répondu), `..._AUCUNE` est un **constat de zéro**
    (l'archive a répondu, rien pour cet acteurRef) ; une intervention Syceron
    publiée dément l'un comme l'autre.

    Le critère est « une intervention qui n'est PAS une question », et non « des
    interventions » : les questions parlementaires viennent de l'open data AN,
    pas de Syceron (#510). Les compter éteindrait le constat Syceron avec la
    preuve d'une autre source — c'est le symétrique exact du critère que
    `_prune_stale_warnings` applique déjà à `WARNING_PREFIX_QUESTIONS_INDISPONIBLES`.
    """
    if not (
        warning.startswith(WARNING_PREFIX_INTERVENTIONS_SYCERON_INDISPONIBLES)
        or warning.startswith(WARNING_PREFIX_INTERVENTIONS_SYCERON_AUCUNE)
    ):
        return False
    return any(
        isinstance(i, dict) and i.get("type_detail") != "question"
        for i in (profile.get("interventions") or [])
    )


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
        if _defaut_collecte_dementi_par_les_donnees(profile, w):
            continue
        if _aucun_mandat_fr_dementi(profile, w):
            continue
        if _interventions_syceron_dementies(profile, w):
            continue
        if (
            w.startswith(WARNING_PREFIX_QUESTIONS_INDISPONIBLES)
            and any(i.get("type_detail") == "question" for i in profile.get("interventions", []))
        ):
            continue
        filtered.append(w)
    meta["warnings"] = filtered


# Champs dont une collecte vide, en mode écrasement, détruirait des données
# acquises. Couvre les deux schémas : `dossiers_legislatifs` côté brut,
# `textes_portes` côté pivot.
CHAMPS_PROTEGES_DU_VIDE: tuple[str, ...] = (
    "votes", "mandats", "amendements", "dossiers_legislatifs",
    "interventions", "textes_portes",
)


# Même décision que ci-dessus (#465), étendue aux BLOCS STRUCTURÉS (#484).
#
# `CHAMPS_PROTEGES_DU_VIDE` ne couvrait que des listes, et une liste vide se
# reconnaît : `[]` est falsy. Un bloc, lui, peut être **vide de fond et truthy
# en même temps** — c'est le trou par lequel l'identité de `jean-luc-melenchon`
# a été écrasée le 29/08/2026 (run 33262372122). Le squelette écrit par
# `generate_all_profiles.build_minimal_profile` porte deux champs, et ces deux
# champs viennent de `raw_data/candidats.json`, pas d'une source parlementaire :
# `nom_complet` et `groupe_nom` (recopié de `parti`). Tout le reste est `null`.
# `_prefer_non_empty` voyait un dict non vide, donc « renseigné », et il gagnait
# sur un bloc collecté à l'AN.
#
# Un bloc n'a donc de « fond » que hors de ces champs-là : la valeur est la
# liste des champs qu'un profil minimal sait remplir **sans avoir rien demandé
# à personne**. Le jour où `build_minimal_profile` en remplit un de plus, il
# s'ajoute ici — et le test `test_merge_profile` le fait tomber sinon.
#
# La règle reste celle de #465, et pas une seconde règle en parallèle : seul le
# passage à **rien** est refusé. Un bloc qui apporte ne serait-ce qu'un champ de
# fond écrase normalement, ce qui laisse une correction aboutir.
BLOCS_PROTEGES_DU_VIDE: dict[str, tuple[str, ...]] = {
    "identite": ("nom_complet", "groupe_nom"),
}


def bloc_sans_fond(bloc: Any, champs_sans_source: tuple[str, ...]) -> bool:
    """Vrai si `bloc` est un dict dont aucun champ HORS `champs_sans_source`
    n'est renseigné — c'est-à-dire un bloc qui n'a rien appris d'une source.

    Un bloc absent (`None`) n'est pas « sans fond » : il est absent, et
    `_prefer_non_empty` sait déjà quoi en faire. La distinction compte, sinon
    ce prédicat répondrait la même chose à deux situations différentes.
    """
    if not isinstance(bloc, dict) or not bloc:
        return False
    return not any(
        valeur not in (None, "", [], {})
        for champ, valeur in bloc.items()
        if champ not in champs_sans_source
    )


def _preferer_bloc_avec_fond(new_bloc: Any, old_bloc: Any, nom_bloc: str) -> Any:
    """`_prefer_non_empty` pour un bloc structuré : un bloc **sans fond** ne
    remplace jamais un bloc qui en a (#484, extension de #465).

    Le bloc n'est jamais fusionné champ par champ, et c'est délibéré : ses
    champs décrivent UNE personne telle qu'UNE source la décrit, et
    `url_an_ou_senat` en porte la provenance. Panacher un `groupe_nom` de
    `raw_data/candidats.json` avec un `groupe_sigle` d'AMO30 publierait une
    identité qu'aucune source ne dit. C'est l'inverse d'`identifiants`, dont
    chaque clé EST une source distincte et qui se fusionne donc clé par clé
    (#539).
    """
    champs_sans_source = BLOCS_PROTEGES_DU_VIDE.get(nom_bloc, ())
    if bloc_sans_fond(new_bloc, champs_sans_source) and not bloc_sans_fond(
        old_bloc, champs_sans_source
    ):
        if isinstance(old_bloc, dict) and old_bloc:
            return old_bloc
    return _prefer_non_empty(new_bloc, old_bloc)


def preserver_collectes_non_vides(
    ancien: Optional[dict[str, Any]], nouveau: dict[str, Any]
) -> tuple[dict[str, Any], list[str]]:
    """**Une collecte vide n'écrase jamais une collecte non vide** (#465).

    S'applique en mode écrasement (`--no-merge`), là où la fusion additive ne
    protège plus rien. Ce n'est pas une demi-fusion : un champ dont la collecte
    a rendu des entrées écrase normalement — c'est ce qui permet à une
    correction de clé d'aboutir (#440 : 2 018 amendements remplacés par 944).
    Seul le passage à **zéro** est refusé.

    Le motif est celui de #427 sur les gouvernements, où il est déjà énoncé :
    *distinguer « zéro constaté » de « collecte incomplète »*. Un `[]` rendu par
    une API en panne n'est pas un fait mesuré, et le publier violerait AGENTS.md
    §2.5. Les profils étaient le seul endroit qui ne l'appliquait pas.

    Ce que ça aurait évité, le 19/08/2026 (run `32302557156`, mode écrasement) :

    - `jean-luc-melenchon` — recherche d'identité en échec, profil minimal
      écrit : 18 721 amendements, 1 016 votes et 33 textes portés à zéro ;
    - `bruno-retailleau` — « votes introuvables » : 36 textes portés à zéro ;
    - `marine-le-pen` — **aucun avertissement**, amendements et votes intacts,
      23 textes portés à zéro.

    Le troisième cas est le plus instructif : rien, dans le profil écrit, ne
    signalait l'échec. Un garde-fou conditionné à la présence d'un avertissement
    ne l'aurait pas vu ; celui-ci ne regarde que le résultat.

    Renvoie `(profil, champs_preserves)` — la liste sert à le **dire**, jamais à
    corriger en silence.
    """
    if not ancien:
        return nouveau, []

    preserves: list[str] = []
    resultat = dict(nouveau)
    for champ in CHAMPS_PROTEGES_DU_VIDE:
        anciennes = ancien.get(champ)
        if not isinstance(anciennes, list) or not anciennes:
            continue
        if resultat.get(champ):
            continue
        resultat[champ] = anciennes
        preserves.append(champ)
    # Les BLOCS structurés, même règle (#484). Deux vides à couvrir, et le
    # second est celui qui a coûté l'identité de `jean-luc-melenchon` : le bloc
    # ABSENT (`identite: None`, collecte d'identité en échec) et le bloc SANS
    # FOND (le squelette du profil minimal, truthy). Le premier était déjà un
    # trou de #465 — sa propre mesure du 19/08/2026 le cite —, il n'était
    # simplement pas couvert par une boucle qui n'acceptait que des listes.
    for bloc, champs_sans_source in BLOCS_PROTEGES_DU_VIDE.items():
        ancien_bloc = ancien.get(bloc)
        if not isinstance(ancien_bloc, dict) or not ancien_bloc:
            continue
        if bloc_sans_fond(ancien_bloc, champs_sans_source):
            continue
        nouveau_bloc = resultat.get(bloc)
        if nouveau_bloc and not bloc_sans_fond(nouveau_bloc, champs_sans_source):
            continue
        resultat[bloc] = ancien_bloc
        preserves.append(bloc)
    return resultat, preserves


def _instant_synchro(valeur: str) -> tuple[int, str]:
    """Ordonne deux horodatages de synchro, offset compris.

    Le repli lexicographique n'est pas une commodité : le corpus publié porte
    des horodatages écrits par `time.strftime('%Y-%m-%dT%H:%M:%S%z')`, que
    `fromisoformat` accepte depuis 3.11 mais qui n'a pas toujours été le cas.
    Une chaîne illisible ne doit pas faire lever une fusion — elle passe
    derrière tout ce qui se parse.
    """
    try:
        return (1, datetime.fromisoformat(valeur).astimezone(timezone.utc).isoformat())
    except (TypeError, ValueError):
        return (0, valeur)


def _synchro_la_plus_recente(new_value: Any, old_value: Any) -> Any:
    """Un horodatage de synchro est une BORNE HAUTE, pas un scalaire (#484).

    `_prefer_non_empty` prend la valeur NEUVE dès qu'elle est renseignée. Sur
    `synchro_sources`, cette règle est à l'envers : le champ dit « la dernière
    fois que cette source a répondu », et un profil fusionné porte les données
    des DEUX côtés. Le run 33262372122 en donne la démonstration exacte — le job
    `extract-an` a resynchronisé AMO30 le 29/08 à 16:22, l'artifact du job
    `extract-ue-officiel`, fusionné après lui, portait le 19/08 recopié du
    profil committé, et c'est le 19/08 qui a été publié. La date publiée
    affirmait une panne de collecte que le run démentait.

    Prendre le plus récent des deux est la seule règle qui décrive le fichier
    écrit, quel que soit l'ordre de fusion — et l'ordre de fusion est un détail
    de la CI (`--dirs an ue roster`), pas un fait sur la donnée.
    """
    candidats = [v for v in (new_value, old_value) if isinstance(v, str) and v]
    if not candidats:
        return _prefer_non_empty(new_value, old_value)
    return max(candidats, key=_instant_synchro)


# ---------------------------------------------------------------------------
# `meta` : composé clé par clé, jamais pris au dernier écrivain (#600)
# ---------------------------------------------------------------------------
#
# Aux deux étages, `meta` était `dict(new)` : le bloc du DERNIER écrivain, pris
# entier. Conséquence mesurée par #599 sur le corpus committé — un profil sur les
# 477 de la population du défaut, `jean-luc-melenchon`, publie pour tout `meta`
# celui de `build_minimal_profile` : un `warnings` réduit à « aucun mandat
# français connu », pas de `collecte_ecartee`, et une synchro AN antérieure de
# 9,9 jours à son propre `genere_le`. Les avertissements de l'écrivain qui a
# collecté ses 1 016 votes ont disparu **sans trace**, et `meta.warnings[]` est
# le véhicule de la règle §2.5.
#
# La forme retenue est celle qui existait déjà pour `identifiants` (#539) : une
# règle par clé, et **aucune clé au hasard**. La règle par défaut n'est pas
# « prendre le nouveau » mais `_prefer_non_empty`, qui ne régresse jamais vers
# `null` — c'est la même règle que pour les scalaires du profil.

#: Le préfixe de `generate_all_profiles.WARNING_PREFIX_CHAMBRE_EN_ECHEC`,
#: recopié plutôt qu'importé : `generate_all_profiles` importe ce module, donc
#: l'importer d'ici serait circulaire. `test_merge_meta_600` vérifie que les
#: deux chaînes n'ont pas divergé — c'est le prix de la recopie, et il est payé.
_PREFIXE_CHAMBRE_EN_ECHEC = "collecte de chambre en échec"
_PREFIXE_DEUX_CHAMBRES = "carrière sur deux chambres"

#: Familles d'avertissements. Un warning appartient à la famille dont il porte
#: le préfixe ; à défaut, **il est sa propre famille** (dédoublonnage exact).
#:
#: La famille compte parce que l'union est par famille, pas par texte : plusieurs
#: de ces messages portent des COMPTEURS calculés sur le profil qui les émet
#: (« 2 mandat(s) électif(s) sans chambre », « chambres=['AN', 'Senat'] »). Une
#: union par texte publierait les deux comptes côte à côte, dont un faux — et
#: c'est exactement pour l'éviter que `merge_pivot_profile` teste déjà
#: `startswith` avant d'ajouter le warning de non-corroboration.
FAMILLES_WARNINGS: tuple[str, ...] = (
    WARNING_PREFIX_IDENTITE_INTROUVABLE,
    WARNING_PREFIX_MANDATS_INTROUVABLES,
    WARNING_PREFIX_VOTES_INTROUVABLES,
    WARNING_PREFIX_AMENDEMENTS_INDISPONIBLES,
    WARNING_PREFIX_DEFAUT_COLLECTE,
    WARNING_PREFIX_QUESTIONS_INDISPONIBLES,
    WARNING_PREFIX_INTERVENTIONS_SYCERON_AUCUNE,
    WARNING_PREFIX_INTERVENTIONS_SYCERON_INDISPONIBLES,
    WARNING_PREFIX_BUDGET_INTERVENTIONS,
    WARNING_PREFIX_BUDGET_COLLECTE,
    WARNING_AUCUN_MANDAT_FR,
    WARNING_PREFIX_CHAMBRES_NON_CORROBOREE,
    _PREFIXE_CHAMBRE_EN_ECHEC,
    _PREFIXE_DEUX_CHAMBRES,
)


def _famille_warning(warning: str) -> str:
    """La famille d'un avertissement, ou son texte s'il n'en a pas de connue.

    L'ordre de `FAMILLES_WARNINGS` compte : `WARNING_PREFIX_INTERVENTIONS_SYCERON_AUCUNE`
    et `..._INDISPONIBLES` sont deux préfixes distincts (#560) et aucun n'est le
    préfixe de l'autre, mais la recherche est faite du plus long au plus court
    pour qu'un futur préfixe emboîté ne rattache pas un message à la mauvaise
    famille.
    """
    for prefixe in sorted(FAMILLES_WARNINGS, key=len, reverse=True):
        if warning.startswith(prefixe):
            return prefixe
    return warning


def unir_warnings(
    new_warnings: Optional[list[Any]], old_warnings: Optional[list[Any]]
) -> list[str]:
    """**Union par famille** des avertissements des deux écrivains (#600).

    Le nouvel écrivain passe en premier et garde l'ordre dans lequel il a écrit
    ses messages ; ceux de l'ancien dont la famille n'est pas déjà représentée
    sont ajoutés à la suite. Deux propriétés en découlent, et ce sont les deux
    qu'on veut :

    1. **Rien ne disparaît sans être remplacé.** Un avertissement du job AN
       survit au passage du job UE, qui n'en sait rien. C'est le défaut de #600.
    2. **Rien n'est publié en double.** Un message à compteur — « 2 mandat(s)
       électif(s) sans chambre » — n'apparaît qu'une fois, dans la version du
       dernier écrivain, qui est celle calculée sur le profil le plus complet.

    Ce que cette fonction NE fait pas : décider si un avertissement est encore
    vrai. C'est le rôle de `_prune_stale_warnings` (étage brut) et du filtre de
    `merge_pivot_profile`, qui tournent **après** et que ce lot étend — un
    warning ressuscité de l'ancien fichier doit pouvoir s'éteindre comme les
    autres.
    """
    unis: list[str] = []
    familles: set[str] = set()
    for source in (new_warnings or [], old_warnings or []):
        for warning in source:
            if not isinstance(warning, str):
                continue
            famille = _famille_warning(warning)
            if famille in familles:
                continue
            familles.add(famille)
            unis.append(warning)
    return unis


def _horodatage_le_plus_recent(new_value: Any, old_value: Any) -> Any:
    """Le plus récent des deux horodatages, jamais celui du dernier écrivain.

    Même raison que `_synchro_la_plus_recente` : `genere_le` dit quand le travail
    publié a été fait, et le profil fusionné porte le travail des DEUX côtés.
    Prendre celui de `new` publierait la date d'un écrivain minimal sur un profil
    dont l'essentiel vient d'un autre — ou, dans l'autre sens, ferait *reculer*
    la date quand l'artifact fusionné est plus vieux que le fichier committé.
    """
    return _synchro_la_plus_recente(new_value, old_value)


def _fusionner_synchro_sources(new_value: Any, old_value: Any) -> Any:
    """`synchro_sources` fusionné **par source**, jamais recopié en bloc (#600).

    Le bloc était repris entier quand le nouveau profil n'en avait pas, et
    fusionné par clé sinon (#484/PR #597) : deux comportements pour une même
    clé, dont un qui recopie une fraîcheur qu'aucune source n'a confirmée. Ici,
    une seule règle — l'union des sources connues des deux côtés, chacune à sa
    valeur la plus récente. Une source qu'un seul écrivain connaît est donc
    conservée, et aucune ne régresse.
    """
    if not isinstance(new_value, dict):
        return dict(old_value) if isinstance(old_value, dict) else new_value
    if not isinstance(old_value, dict):
        return dict(new_value)
    return {
        source: _synchro_la_plus_recente(new_value.get(source), old_value.get(source))
        for source in sorted(set(old_value) | set(new_value))
    }


#: Sentinelle : la clé n'existe pas chez cet écrivain. Distincte de `None`, qui
#: est une valeur publiée (§2.5 : `null` dit « pas de déclaration », l'absence de
#: clé dit « ce producteur n'en parle pas »).
_ABSENTE = object()


def _declaration_du_run(new_value: Any, old_value: Any) -> Any:
    """La déclaration du nouvel écrivain **dès qu'il en fait une**, même vide.

    C'est la règle de `collecte_ecartee` (#539), et elle ne peut pas être
    `_prefer_non_empty` : une liste `[]` y signifie « ce run n'a rien écarté »,
    ce qui est une **affirmation**, pas une absence. `_prefer_non_empty` la
    prendrait pour un vide et rendrait la déclaration d'un run précédent — une
    liste écartée survivrait au run qui l'a collectée, et `couverture_profil`
    publierait `non_collecte` sur une liste pleine.

    L'ancienne valeur n'est rendue que si le nouvel écrivain **n'a pas la clé**,
    c'est-à-dire s'il n'a rien décidé qu'on sache : c'est le cas du chemin
    minimal, qui n'écrit pas `collecte_ecartee` du tout.
    """
    if new_value is _ABSENTE:
        return old_value
    return new_value


def _du_producteur_courant(new_value: Any, old_value: Any) -> Any:
    """La valeur du nouvel écrivain dès qu'il la porte, sans regarder l'ancienne.

    Pour `schema_version` : elle décrit le FORMAT qu'on écrit maintenant, pas la
    donnée. Retomber sur l'ancienne au motif que la nouvelle serait « vide »
    publierait une version de schéma que le fichier ne respecte pas.
    """
    if new_value is _ABSENTE:
        return old_value
    return new_value


def _regle_par_defaut(new_value: Any, old_value: Any) -> Any:
    """La règle des scalaires : la valeur neuve si elle est renseignée, l'ancienne
    sinon. Jamais une régression vers `null` (§2.5).

    C'est la règle de toute clé de `meta` que `REGLES_META` ne nomme pas — donc
    d'aucune clé du schéma publié aujourd'hui, mais de celles qu'un producteur
    ajouterait demain. Le défaut n'est **pas** « prendre le nouveau » : c'est
    précisément ce défaut-là que #600 corrige.
    """
    if new_value is _ABSENTE:
        return old_value
    if old_value is _ABSENTE:
        return new_value
    return _prefer_non_empty(new_value, old_value)


#: Une règle par clé de `meta`, et la raison de chacune. Le tableau couvre les
#: deux étages : `synchro_sources`/`collecte_ecartee` côté brut,
#: `schema_version`/`provenance` côté pivot, le reste des deux côtés.
#:
#: `provenance` n'est pas ici : elle a sa propre règle, plus forte que toutes
#: celles-ci (#189 — un `candidat_declare` n'est jamais rétrogradé), appliquée
#: par `merge_pivot_profile` APRÈS la composition. Le défaut la protège déjà
#: d'une régression vers `null`, ce qui est ce que surveille `audit_diff_profils`.
REGLES_META: dict[str, Callable[[Any, Any], Any]] = {
    "genere_le": _horodatage_le_plus_recent,
    "warnings": lambda new, old: unir_warnings(
        None if new is _ABSENTE else new, None if old is _ABSENTE else old
    ),
    "synchro_sources": lambda new, old: _fusionner_synchro_sources(
        None if new is _ABSENTE else new, None if old is _ABSENTE else old
    ),
    "collecte_ecartee": _declaration_du_run,
    "schema_version": _du_producteur_courant,
    # `licence_donnees` : la règle des scalaires, et rien de plus — elle est
    # RECALCULÉE après la fusion par `appliquer_licence_donnees` à l'étage pivot
    # (#530), qui a le dernier mot. La composer ici ne sert qu'à ne pas publier
    # un `null` transitoire à l'étage brut, où plus personne ne la relit depuis
    # que `normalize_profil` la dérive de `sources[]`.
    "licence_donnees": _regle_par_defaut,
    "provenance": _regle_par_defaut,
}


def fusionner_meta(
    old_meta: Optional[dict[str, Any]], new_meta: Optional[dict[str, Any]]
) -> Optional[dict[str, Any]]:
    """Compose deux blocs `meta` clé par clé (#600).

    Aucune clé n'est prise « parce que son écrivain est passé en dernier » :
    chaque clé de l'union des deux blocs passe par la règle que `REGLES_META` lui
    donne, ou par `_regle_par_defaut` qui ne régresse jamais vers `null`.

    L'ordre des clés est celui du nouvel écrivain, complété par les clés que lui
    seul l'ancien portait : le diff git d'un profil publié ne bouge donc pas
    quand rien ne change.
    """
    if not isinstance(new_meta, dict):
        return dict(old_meta) if isinstance(old_meta, dict) else new_meta
    if not isinstance(old_meta, dict):
        return dict(new_meta)

    cles = list(new_meta) + [c for c in old_meta if c not in new_meta]
    fusionne: dict[str, Any] = {}
    for cle in cles:
        regle = REGLES_META.get(cle, _regle_par_defaut)
        fusionne[cle] = regle(
            new_meta.get(cle, _ABSENTE), old_meta.get(cle, _ABSENTE)
        )
    return fusionne


def merge_raw_profile(old: Optional[dict[str, Any]], new: dict[str, Any]) -> dict[str, Any]:
    """Fusionne un profil brut nouvellement généré (`new`) avec la version
    déjà présente sur disque (`old`, ou None si aucun fichier existant).
    Additif uniquement : ne supprime ni ne modifie aucune entrée déjà connue."""
    if not old:
        return new

    merged = dict(new)

    # `meta` composé clé par clé (#600), là où c'était `dict(new)` : le bloc du
    # dernier écrivain, warnings compris. Le rattrapage de `synchro_sources` qui
    # vivait ici est absorbé par `_fusionner_synchro_sources`, qui applique la
    # même règle que le bloc soit présent des deux côtés ou d'un seul.
    meta_fusionne = fusionner_meta(old.get("meta"), new.get("meta"))
    if meta_fusionne is not None:
        merged["meta"] = meta_fusionne

    merged["identite"] = _preferer_bloc_avec_fond(
        new.get("identite"), old.get("identite"), "identite"
    )
    merged["chambre"] = _prefer_non_empty(new.get("chambre"), old.get("chambre"))
    merged["source"] = _prefer_non_empty(new.get("source"), old.get("source"))
    merged["votes_source"] = _prefer_non_empty(new.get("votes_source"), old.get("votes_source"))
    merged["mandats"] = backfill_mandat_chambre(
        merge_lists_by_key(old.get("mandats"), new.get("mandats"), _mandat_key),
        new.get("mandats"),
        _mandat_key,
    )
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
    """Identité d'un vote pivot depuis sa normalisation (#432).

    `scrutin_id` porte déjà `(legislature, numero_scrutin)` : il identifie le
    scrutin sans ambiguïté, là où `numero_scrutin` seul confondrait deux
    législatures. Le repli sur l'enregistrement complet couvre les votes non
    résolus, qui n'ont pas d'identifiant : les traiter tous comme la même clé
    `None` les fusionnerait en un seul — une perte silencieuse.
    """
    scrutin_id = v.get("scrutin_id")
    if scrutin_id:
        return scrutin_id
    non_resolu = v.get("scrutin_non_resolu") or {}
    return ("non_resolu", non_resolu.get("numero_scrutin"), non_resolu.get("date"))


def _pivot_mandat_key(m: dict[str, Any]) -> Key:
    return (m.get("label"), m.get("categorie"), m.get("fonction"), m.get("debut"))


def _pivot_texte_key(t: dict[str, Any]) -> Key:
    """Identité d'un dossier législatif porté, indépendante de `role`.

    `role`/`type_rapport`/`stade_procedural` ne sont aujourd'hui jamais
    renseignés par la source de collecte (voir normalize_profil.py) : les
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
    # Depuis #431 le pivot ne porte plus que le mapping : `amendement_id`
    # (`an:<uid>`) EST la clé, et elle est la même donnée que l'`uid` du brut,
    # préfixée. Les replis suivants ne servent qu'aux entrées écrites avant la
    # normalisation, que la fusion additive fait cohabiter avec les nouvelles
    # le temps d'une régénération.
    #
    # Pour une entrée non résolue (`amendement_id` à null), la clé est lue dans
    # `amendement_non_resolu` : sans cela, toutes les entrées non résolues d'un
    # profil se réduiraient à une seule à la fusion.
    amendement_id = a.get("amendement_id")
    if amendement_id:
        return amendement_id
    non_resolu = a.get("amendement_non_resolu")
    if isinstance(non_resolu, dict):
        a = non_resolu
    return a.get("uid") or a.get("source_url") or (a.get("numero"), a.get("texte_vise"), a.get("date"))


def _pivot_intervention_key(i: dict[str, Any]) -> Key:
    """Identité d'une intervention pivot (#540).

    **Une URL de source n'est pas un identifiant.** La clé d'origine —
    `source_url or (date, sujet, texte[:50])` — court-circuitait sur le `or` :
    le repli discriminant n'était jamais atteint dès que `source_url` était
    renseignée. Elle a été écrite pour une source qui publiait un permalien par
    intervention (l'ancre `#inter_<hash>` de NosDéputés) ; Syceron publie l'URL
    de **l'archive de la législature**, identique pour toutes les interventions
    de cette législature. `merge_lists_by_key` étant purement additif, il n'a
    ajouté que les clés inédites : 3 351 entrées collectées pour gabriel-attal
    se réduisaient à 17 publiées, et 7 767 collectées à 891 sur tout le corpus.
    C'est le mode de défaillance que `_pivot_vote_key` décrit déjà pour les
    votes non résolus (#432), à ceci près que la clé collante n'est pas `None`
    mais une URL — donc qu'elle *ressemble* à un identifiant.

    `intervention_id` (propagé verbatim depuis le brut par
    `normalize_profil._normalize_intervention`) est **la même identité que
    celle de la fusion brute** `_intervention_key`, qui repose sur `id` et n'a
    jamais souffert du défaut. Les deux étages disent donc la même chose de ce
    qu'est une intervention : c'est la seule forme qui garantisse qu'une entrée
    collectée arrive publiée, une fois et une seule.

    **Alternative écartée : la clé composite `(source_url, date, sujet,
    texte[:80])`** proposée par #540. Elle rend 3 127 entrées pour
    gabriel-attal, pas 3 351 — elle fusionne 224 prises de parole réelles.
    Mesuré : « Même avis, pour les mêmes raisons. » est prononcé 13 fois dans
    la même séance du 08/11/2022, sur 13 amendements successifs. Ce ne sont pas
    des doublons d'archive, ce sont 13 interventions distinctes ; les absorber
    serait une perte silencieuse, exactement celle qu'on corrige. Une clé qui
    dépend du texte est en outre à la merci d'une correction typographique du
    compte rendu — le même paragraphe reviendrait alors comme une entrée neuve.

    Les replis restent pour les entrées écrites avant #540, que la fusion
    additive fait cohabiter avec les nouvelles : `source_url` d'abord (un
    permalien par entrée pour les interventions héritées de NosDéputés), puis
    le contenu. Voir `clean_stale_interventions` pour leur reprise.
    """
    intervention_id = i.get("intervention_id")
    if intervention_id not in (None, ""):
        return ("intervention_id", intervention_id)
    source_url = i.get("source_url")
    if source_url:
        return ("source_url", source_url)
    return ("contenu", i.get("date"), i.get("sujet"), (i.get("texte") or "")[:50])


def clean_stale_interventions(
    interventions: Optional[list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Reprise des entrées écrites avant #540, sur le patron de
    `clean_stale_textes_portes`.

    Les 891 interventions publiées avant le correctif ne portent pas
    d'`intervention_id` : leur clé est leur `source_url`. Les mêmes
    interventions, renormalisées, en portent un. Sans reprise, la fusion
    additive publierait **les deux** — l'ancienne entrée sous sa clé d'URL, la
    neuve sous sa clé d'identifiant — et le corpus se dédoublerait au lieu de
    se compléter.

    Règle appliquée : une entrée **sans** `intervention_id` est écartée quand
    au moins une entrée **avec** `intervention_id` porte la même `source_url`.
    Elle est alors, par construction, l'une de ces entrées-là — soit la même
    intervention renormalisée (permalien NosDéputés, URL de question : une
    entrée par URL), soit l'unique rescapée de l'effondrement Syceron (URL
    d'archive : la première entrée collectée de cette archive, que la liste
    neuve contient aussi).

    Elle ne peut donc rien perdre : sans entrée identifiée sur cette
    `source_url` — collecte en échec, législature non recollectée, archive
    indisponible — rien n'est écarté et l'ancienne entrée reste publiée. Une
    entrée sans `source_url` n'est jamais écartée non plus.
    """
    urls_reprises = {
        i.get("source_url")
        for i in interventions or []
        if isinstance(i, dict)
        and i.get("intervention_id") not in (None, "")
        and i.get("source_url")
    }
    if not urls_reprises:
        return list(interventions or [])
    return [
        i
        for i in interventions or []
        if not (
            isinstance(i, dict)
            and i.get("intervention_id") in (None, "")
            and i.get("source_url") in urls_reprises
        )
    ]


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
        # Même recalcul que sur le chemin fusionné : `licence_donnees` dérive de
        # `sources[]`, et un premier pivot doit publier la même chaîne qu'un
        # pivot régénéré au même contenu (#530).
        appliquer_licence_donnees(new)
        return new

    merged = dict(new)

    # `meta` composé clé par clé (#600) — même règle qu'à l'étage brut, et pour
    # la même raison : sans elle, `merged["meta"]` est celui du dernier écrivain,
    # et les avertissements de l'autre disparaissent sans trace.
    meta_fusionne = fusionner_meta(old.get("meta"), new.get("meta"))
    if meta_fusionne is not None:
        merged["meta"] = meta_fusionne

    merged["parti"] = _prefer_non_empty(new.get("parti"), old.get("parti"))
    merged["groupe"] = _prefer_non_empty(new.get("groupe"), old.get("groupe"))
    merged["chambre"] = _prefer_non_empty(new.get("chambre"), old.get("chambre"))
    merged["identite"] = _preferer_bloc_avec_fond(
        new.get("identite"), old.get("identite"), "identite"
    )

    # --- identifiants : fusionnés CLÉ PAR CLÉ (#539) -------------------------
    #
    # `_prefer_non_empty` sur le bloc entier ferait perdre un identifiant qu'un
    # run précédent avait résolu et que celui-ci n'a pas : un profil AN + PE
    # passe par deux normaliseurs, et une passe `--source an` ne rend pas
    # l'`europarl`. La règle des scalaires, appliquée à chaque clé — la nouvelle
    # valeur si elle est renseignée, l'ancienne sinon, jamais une régression
    # vers `null` (AGENTS.md §2 règle 5).
    identifiants = dict(old.get("identifiants") or {})
    for cle, valeur in (new.get("identifiants") or {}).items():
        identifiants[cle] = _prefer_non_empty(valeur, identifiants.get(cle))
    if identifiants:
        merged["identifiants"] = identifiants

    # --- couverture : REMPLACÉE, jamais fusionnée (#539) ---------------------
    #
    # C'est le piège du bloc, et la seule exception à la règle de ce module. La
    # fusion additive protège la donnée COLLECTÉE : une entrée acquise ne
    # disparaît pas parce qu'un run l'a manquée. La couverture, elle, ne décrit
    # pas la personne — elle décrit **le run** : ce qu'on a demandé à la source
    # ce jour-là, et ce que cette source couvre. La fusionner ferait survivre
    # indéfiniment un `couvert` établi le jour où la collecte tournait, à côté
    # d'un `non_collecte` d'aujourd'hui : la panne serait masquée par son propre
    # historique, exactement le contresens que #539 retire.
    #
    # `_prefer_non_empty` plutôt que `new` sec : un chemin qui ne dérive pas
    # encore de couverture (un pivot construit par un outil autonome) ne doit
    # pas effacer celle du corpus. Il ne peut pas non plus en inventer une — un
    # bloc vide est vide, donc l'ancien est conservé.
    couverture = _prefer_non_empty(new.get("couverture"), old.get("couverture"))
    if couverture is not None:
        merged["couverture"] = couverture
    else:
        merged.pop("couverture", None)

    merged["sources"] = _merge_pivot_sources(old.get("sources"), new.get("sources"))
    merged["mandats"] = backfill_mandat_chambre(
        merge_lists_by_key(old.get("mandats"), new.get("mandats"), _pivot_mandat_key),
        new.get("mandats"),
        _pivot_mandat_key,
    )

    # --- chambres / chambre : RECALCULÉS, jamais fusionnés (#493) -----------
    #
    # `merge_lists_by_key` est additif : `merged["mandats"]` est un **surensemble**
    # des mandats de `new` comme de ceux de `old`. Un `chambres` fusionné —
    # `_prefer_non_empty(new, old)` ou une union de listes — décrirait donc un
    # ensemble de mandats qui n'existe dans aucun des deux profils. C'est le
    # symétrique du piège que #492 a rencontré sur `backfill_mandat_chambre` :
    # un champ dérivé ne se fusionne pas, il se recalcule après la fusion de ce
    # dont il dérive.
    #
    # Le recalcul est monotone : les mandats ne peuvent qu'augmenter, donc
    # `chambres` ne peut que gagner des entrées. Le repli reste `merged["chambre"]`
    # — la valeur qu'on aurait publiée sans #493 : c'est ce qui garantit qu'aucun
    # scalaire publié ne régresse vers `null` (un `chambre` renseigné → `null` est
    # une perte bloquante pour `audit_diff_profils`).
    derivation = appliquer_chambres(merged)
    # Tri par identifiant, plus par date : depuis #432 la date du scrutin n'est
    # plus dans le profil. L'ordre n'a donc plus de sens chronologique, il n'a
    # qu'à être STABLE d'un run à l'autre pour que git ne voie que les vraies
    # différences. Les consommateurs qui ont besoin de l'ordre chronologique
    # joignent l'index et trient eux-mêmes (c'est déjà ce que fait l'UI).
    merged["votes"] = sorted(
        merge_lists_by_key(old.get("votes"), new.get("votes"), _pivot_vote_key),
        key=lambda v: str(v.get("scrutin_id") or ""),
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
    # `clean_stale_interventions` : reprise des entrées d'avant #540, qui n'ont
    # pas d'`intervention_id` et seraient republiées EN DOUBLE à côté de leur
    # renormalisation identifiée. Voir sa docstring pour la preuve de non-perte.
    merged["interventions"] = clean_stale_interventions(
        merge_lists_by_key(old.get("interventions"), new.get("interventions"), _pivot_intervention_key)
    )
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

    # #493 : la déclaration d'une `chambres` non corroborée doit survivre à la
    # fusion **dans les deux sens**. Le filtre ci-dessous ne sait que retirer un
    # warning devenu faux ; il faut aussi pouvoir en ajouter un devenu vrai.
    # Le cas se produit dès qu'un run recollecte proprement un mandat pendant
    # que la fusion additive en conserve un ancien, non estampillé : le profil
    # neuf ne porte alors aucun warning, le profil fusionné le mérite. Sans ce
    # rattrapage, la seule chose qui empêche `chambres` d'être trompeuse
    # disparaîtrait précisément sur les profils mixtes — ceux de la migration.
    if isinstance(merged.get("meta"), dict) and not derivation.corroboree:
        warnings_merged = merged["meta"].setdefault("warnings", [])
        # Le texte est recalculé sur le profil FUSIONNÉ, jamais repris de
        # l'ancien : ses compteurs porteraient sur un autre ensemble de mandats.
        if not any(w.startswith(WARNING_PREFIX_CHAMBRES_NON_CORROBOREE)
                   for w in warnings_merged if isinstance(w, str)):
            warnings_merged.append(
                f"{WARNING_PREFIX_CHAMBRES_NON_CORROBOREE} : "
                f"chambres={derivation.chambres}, dont "
                f"{derivation.chambres_non_corroborees or 'aucune'} sans mandat électif "
                f"estampillé pour l'étayer, et {derivation.mandats_non_estampilles} "
                "mandat(s) électif(s) encore sans chambre, après fusion additive (#493). "
                "Une chambre non corroborée est celle de la collecte : elle dit quel jeu "
                "de données a répondu, pas où la personne a siégé."
            )

    if isinstance(merged.get("meta"), dict) and merged["meta"].get("warnings"):
        filtered = []
        for w in merged["meta"]["warnings"]:
            if w.startswith(WARNING_PREFIX_VOTES_INTROUVABLES) and merged.get("votes"):
                continue
            if w.startswith(WARNING_PREFIX_MANDATS_INTROUVABLES) and merged.get("mandats"):
                continue
            if w.startswith(WARNING_PREFIX_AMENDEMENTS_INDISPONIBLES) and merged.get("amendements"):
                continue
            if _defaut_collecte_dementi_par_les_donnees(merged, w):
                continue
            if _aucun_mandat_fr_dementi(merged, w):
                continue
            if _interventions_syceron_dementies(merged, w):
                continue
            # #493 : le warning de non-corroboration est calculé par
            # `normalize_profil` sur les seuls mandats du profil neuf. La
            # fusion peut avoir ramené des mandats estampillés que le run neuf
            # n'a pas recollectés : la liste est alors corroborée, et le dire
            # encore serait faux.
            if w.startswith(WARNING_PREFIX_CHAMBRES_NON_CORROBOREE) and derivation.corroboree:
                continue
            filtered.append(w)
        merged["meta"]["warnings"] = filtered

    # `licence_donnees` : RECALCULÉ, jamais fusionné (#530, même patron que
    # `chambres` au #493). `_merge_pivot_sources` fusionne `sources[]` par
    # `type` : le profil fusionné est un **surensemble** des sources des deux
    # côtés, et une entrée `nosdeputes` déjà publiée survit donc à une collecte
    # AN. Reprendre la licence de `new` publierait « Licence Ouverte » sur un
    # profil qui porte encore une source ODbL ; reprendre celle de `old`
    # gèlerait l'inverse. Seul le recalcul post-fusion décrit ce qui est
    # réellement publié, et c'est lui qui fera disparaître la clause ODbL le
    # jour où la dernière source Regards Citoyens quittera le profil.
    appliquer_licence_donnees(merged)

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

    Partition par législature (#580) : chaque source est lue par
    `charger_profil_brut`, qui accepte indifféremment un profil monolithique
    (l'ancienne forme, encore committée) et un socle + ses tranches. La fusion
    travaille donc sur le profil **complet**, exactement comme avant — la
    découpe est une affaire de fichiers, pas de sémantique. La sortie, elle, est
    toujours écrite partitionnée : c'est ici que la migration se fait d'elle-même
    à chaque run.

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
                profile = charger_profil_brut(path)
            except (json.JSONDecodeError, OSError, PartitionIllisible) as exc:
                print(f"  [!] Lecture impossible de {path}, ignoré : {exc}")
                continue
            merged = merge_raw_profile(merged, profile)
        if merged is not None:
            ecrire_profil_brut(out_dir, filename[: -len(".json")], merged)
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
