#!/usr/bin/env python3
"""
appariement_senateurs.py — Relier un profil publié à son matricule sénatorial (#885).

Pourquoi il n'y a pas de second référentiel
--------------------------------------------
`raw_data/correspondance_acteurs_an.json` porte déjà, pour chacune de ses
**1 196** entrées, un champ `identifiants.senat` — **nul sur les 1 196**. Il
attendait une source. Ce module la lui donne, et n'écrit **que** ce champ.

Créer une seconde table aurait fabriqué un référentiel concurrent, avec sa
propre notion de slug et sa propre dérive. Le dépôt a déjà réglé ce débat pour
les licences (`src/licences.py`) et pour les acteurs de l'Assemblée : une clé,
un endroit.

Ce que l'appariement sait faire, et ce qu'il refuse
---------------------------------------------------
Il apparie sur l'**état civil normalisé** — accents, casse, ponctuation et
particules retirés — en essayant **tous les découpages** prénom/nom du nom
publié. C'est nécessaire : la source range « Dominique de Legge » en
`senprenomuse = "Dominique"` et `sennomuse = "de Legge"`, et un découpage naïf
sur le dernier mot cherche « Legge » précédé de « Dominique de ». Le seul échec
d'appariement mesuré venait de là, pas de la source.

**Il refuse d'apparier ce qui est ambigu.** Deux sénateurs pour un même état
civil normalisé rendent `AppariementAmbigu`, jamais un choix : `build_correspondance_acteurs_an.py`
« refuse d'inventer » depuis #525, et un identifiant faux est pire qu'un
identifiant absent — il rattacherait la carrière de quelqu'un d'autre.

Mesuré le 13/09/2026 sur les 1 196 profils publiés et les 1 951 lignes de `sen` :
**38 appariements uniques, 0 ambigu**, portant **73 mandats** `elusen`. Zéro
ambiguïté n'est pas une garantie pour l'avenir : c'est une mesure sur ce
corpus-ci, et le refus reste armé.

Ce qu'un appariement automatique n'est pas
-------------------------------------------
Une **preuve**. L'entrée écrite est estampillée `origine: "derivee"` — le même
régime que les 699 entrées dérivées de #715 : elle **gèle** l'identifiant, elle
ne l'établit pas. La faire passer à `relue` demande qu'un humain la regarde, et
la §5b du portail publie le compte de ce qui reste à relire précisément pour que
la file se voie.
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from typing import Any, Iterable, Optional

#: Ce qu'un appariement automatique vaut, dans le vocabulaire de
#: `correspondance_acteurs_an.json` : il gèle, il ne prouve pas (#715).
ORIGINE_APPARIEMENT = "derivee"


class AppariementAmbigu(ValueError):
    """Deux sénateurs répondent au même état civil normalisé.

    Levée plutôt que résolue : un identifiant faux rattacherait la carrière de
    quelqu'un d'autre à une fiche publiée, et rien dans le corpus ne le
    signalerait ensuite.
    """


def normaliser(valeur: Optional[str]) -> str:
    """L'état civil réduit à ce qui compare : lettres minuscules, sans accents.

    Les espaces et les traits d'union disparaissent aussi — « Jean-Luc » et
    « Jean Luc » sont la même personne, et la source n'est pas régulière
    là-dessus.
    """
    sans_accents = unicodedata.normalize("NFD", valeur or "")
    sans_accents = sans_accents.encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]", "", sans_accents.lower())


def indexer_senateurs(lignes: Iterable[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Les sénateurs indexés par état civil normalisé.

    La valeur est une **liste** : c'est elle qui rend l'ambiguïté visible, là où
    un dict l'écraserait en silence.
    """
    index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for ligne in lignes:
        cle = normaliser(ligne.get("senprenomuse")) + normaliser(ligne.get("sennomuse"))
        if cle:
            index[cle].append(ligne)
    return index


def apparier(nom_publie: str, index: dict[str, list[dict[str, Any]]]) -> Optional[str]:
    """Le matricule d'un nom publié, ou `None`.

    Essaie **tous les découpages** prénom/nom : la source range les particules
    dans le nom (« Dominique » + « de Legge »), et le corpus publie un nom
    complet. Un découpage sur le dernier mot manquerait tous les noms à
    particule.

    Rend `None` plutôt que de lever quand rien ne correspond : un profil sans
    passé sénatorial est le cas normal — **1 158 des 1 196**.
    """
    mots = (nom_publie or "").split()
    candidats: dict[str, dict[str, Any]] = {}
    for coupe in range(1, len(mots)):
        cle = normaliser(" ".join(mots[:coupe])) + normaliser(" ".join(mots[coupe:]))
        for ligne in index.get(cle, []):
            candidats[ligne["senmat"]] = ligne
    if not candidats:
        return None
    if len(candidats) > 1:
        raise AppariementAmbigu(
            f"{nom_publie!r} correspond à {len(candidats)} sénateurs "
            f"({', '.join(sorted(candidats))}). Aucun n'est retenu : un "
            "identifiant faux rattacherait la carrière de quelqu'un d'autre. "
            "Trancher à la main dans raw_data/correspondance_acteurs_an.json."
        )
    return next(iter(candidats))


def proposer_appariements(
    correspondances: dict[str, dict[str, Any]],
    senateurs: Iterable[dict[str, Any]],
) -> tuple[dict[str, str], list[str], list[str]]:
    """Rend `(appariements, ambigus, deja_renseignes)`.

    Ne modifie rien : la proposition se lit avant de s'écrire. Une entrée dont
    `identifiants.senat` est **déjà** renseigné n'est jamais recalculée — elle a
    pu être relue par un humain, et un appariement automatique qui écrase une
    relecture défait précisément le travail qu'il faut protéger (#715).
    """
    index = indexer_senateurs(senateurs)
    appariements: dict[str, str] = {}
    ambigus: list[str] = []
    deja: list[str] = []
    for slug, entree in correspondances.items():
        identifiants = entree.get("identifiants") or {}
        if identifiants.get("senat"):
            deja.append(slug)
            continue
        nom = (entree.get("etat_civil") or {}).get("nom_complet") or ""
        try:
            matricule = apparier(nom, index)
        except AppariementAmbigu:
            ambigus.append(slug)
            continue
        if matricule:
            appariements[slug] = matricule
    return appariements, sorted(ambigus), sorted(deja)
