#!/usr/bin/env python3
"""
audit_diff_profils.py — Compare la couche publiée `pivot_data/` d'une référence
git à celle du disque, fichier par fichier et champ par champ, pour détecter ce
qu'une régénération a perdu.

**Pourquoi.** La fusion additive de `merge_profile.py` n'est pas un confort :
elle préserve les données d'un run à l'autre quand une collecte échoue. On l'a
constaté le 18/08/2026 — les 283 textes de la XV d'Édouard Philippe ont
survécu à une collecte ratée uniquement grâce à elle.

Un run `--no-merge` (ou `fresh_run`) abandonne cette mémoire : tout ce que la
collecte du jour ne récupère pas est définitivement perdu, **silencieusement**.
Ce script est le contrôle qui manque avant de committer une telle
régénération.

**Comparaison par fichier et par champ, jamais en agrégat** : un gain global
masquerait des pertes individuelles. C'est précisément ce qui rend le contrôle
utile — la correction de clé de #440 fait mécaniquement grimper le nombre
d'amendements, et cette hausse cacherait n'importe quelle perte de votes ou de
mandats si on ne regardait que le total.

Trois catégories de constats, deux statuts :

  - **listes stables** — une baisse est une alerte **bloquante**. Votes,
    mandats, textes portés, interventions, tags thématiques, cohésion de vote
    d'un groupe n'ont aucune raison de diminuer d'un run à l'autre.
  - **listes signalées** — une baisse est relevée sans bloquer : les
    amendements (la correction de clé de #440 les fait varier des deux côtés,
    × 2,8 à × 7,1 selon la législature) et `sources`, dont l'historique montre
    des variations légitimes (16 → 15, 4 → 3) au gré des sous-collectes.
  - **scalaires** — seule la régression **renseigné → null** bloque. Un
    changement de valeur (A → B) est relevé sans bloquer : voir plus bas.

## Périmètre étendu par #470

Jusqu'à cette issue, le contrôle ne regardait que `pivot_data/profiles` et n'y
comparait que des longueurs de listes. Deux pertes réelles sont passées au
travers, alors qu'il tournait :

  1. **La cohésion de vote du groupe SOC-16 est tombée de 814 à 0** entre
     `25f7bc7` et `a125e9e`, sur la couche publiée. 24 des mandats perdus
     étaient des `mandat_electif`, la catégorie qui détermine si un membre
     était en fonction à la date d'un scrutin
     (`group_profile._member_eligibility_intervals`). Sans mandat électif,
     aucun membre n'est éligible, aucun scrutin n'est comptable, et
     `cohesion_votes` tombe à zéro. Ce n'est pas une fiche incomplète : c'est
     un **dénominateur publié devenu faux** (AGENTS.md §2.7). Même run,
     REN-16 : `mandats_agreges` 1 032 → 646.
  2. **`parti` est passé de renseigné à `null`** sur `jean-luc-melenchon`,
     `edouard-philippe` et `laurent-wauquiez` entre `e4d71cf` et `ffa24ec`,
     et l'UI ne le montrait pas non plus — `pivotAdapter` retombe sur
     `manifestEntry.parti`, issu de `candidats.json`. La donnée publiée était
     fausse, l'affichage restait juste.

Le contrôle couvre donc désormais les cinq répertoires de `pivot_data/` et les
index partagés. Ce qu'il ne couvre toujours pas est énuméré dans
`docs/technical_decisions.md#perimetre-controle-perte`.

## Pourquoi un changement de valeur ne bloque pas

Mesuré sur les 13 transitions committées entre le 16 et le 20/08/2026, sur les
209 profils :

  - **10 régressions `renseigné → null`, dont 10 défauts réels** — les quatre
    `parti` écrasés par la passe roster-driven, les trois `parti` des
    restaurations de #460/#465, deux `identite` perdues, un `groupe`. Aucun
    faux positif. C'est ce qui justifie de bloquer dessus, et AGENTS.md §3 le
    dit déjà du côté de la fusion : « Scalars: new value if populated, else
    keep old (**never regress to null**) ». Une régression vers `null` est donc
    toujours une violation de contrat, jamais un fait mesuré (règle §2.5).
  - **129 changements de valeur, quasi tous légitimes** — normalisations
    (`'REN'` → `'Renaissance'`, `'LREM'` → `'Ensemble pour la République'`),
    accents (`'Edouard Philippe'` → `'Édouard Philippe'`), bascules de source
    (`nosdeputes` ↔ `nossenateurs`, et le `chambre` qui suit), et
    `meta.provenance` qui alterne `candidat_declare` / `roster_groupe` selon
    l'ordre des passes. Bloquer là-dessus interdirait presque tous les commits
    de données.

D'où l'arbitrage, explicite : **faux négatif assumé sur le changement de
valeur, faux positif refusé**. Un changement suspect (Mélenchon passant de
`AN` à `Senat`) est relevé dans le rapport, à charge de relecture humaine.

## Dimensionnement

Ce script tourne AVANT le commit : s'il meurt, rien n'est publié. Il s'est
déjà fait tuer par l'OOM killer une fois (#460), et un garde-fou qui meurt est
pire qu'un garde-fou absent — il donne une assurance qu'il ne tient pas.

Deux règles tenues ici :

  - un seul document en mémoire à la fois, jamais le corpus (lecture en flux
    du `git cat-file --batch`, cf. `lire_collection_git`) ;
  - les fichiers `<legislature>.cosignatures.json` ne sont **pas** ouverts :
    à eux seuls ils portent le pic de mémoire (222 Mio pour les 25,7 Mo de
    `15.cosignatures.json`, soit plus que tout le reste du contrôle réuni),
    aucun consommateur ne les lit (AGENTS.md §3), et leur **disparition** —
    le seul cas catastrophique — est détectée gratuitement par la comparaison
    des listings.

Mesuré sur les 209 profils de `3a8455a` (`--ref HEAD`, `/usr/bin/time -v`,
médiane de trois exécutions) : **2,79 s / 133,4 Mio** pour les profils seuls,
**4,74 s / 184,8 Mio** pour les six collections. Sous les 236 Mio actés par
#460, et `--seulement-profils` rend exactement les chiffres d'avant.

Sortie non nulle si un fichier a perdu sur un champ stable, a disparu, ou a vu
un scalaire surveillé régresser vers `null` — utilisable comme garde-fou avant
commit.

Usage :
    python3 src/audit_diff_profils.py --ref origin/main \\
        --profils-dir pivot_data/profiles --pivot-dir pivot_data \\
        --out audit/diff.md
"""

import argparse
import fnmatch
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


@dataclass(frozen=True)
class Collection:
    """Un répertoire (ou un fichier) de `pivot_data/` et ce qu'on y surveille.

    `motif_present` désigne les fichiers dont la **disparition** est une perte.
    `motif_exclu` en retire ceux dont le **contenu** n'est pas comparé : un
    fichier présent mais non lu ne coûte que sa ligne de listing.
    """

    nom: str
    sous_chemin: str
    listes_stables: tuple[str, ...] = ()
    listes_signalees: tuple[str, ...] = ()
    scalaires: tuple[str, ...] = ()
    motif_present: str = "*.json"
    #: Motif des fichiers présents mais volontairement non ouverts. `fnmatch`
    #: et non un motif positif : `*` y traverse le point, si bien que
    #: `[0-9]*.json` attraperait aussi `14.cosignatures.json`.
    motif_exclu: str = ""
    #: `True` pour `pivot_data/profiles`, dont l'absence dans la référence est
    #: une erreur d'invocation (`--ref-dir`) et non un constat.
    obligatoire: bool = False

    @property
    def tous_champs(self) -> tuple[str, ...]:
        return self.listes_stables + self.listes_signalees

    def concerne(self, nom_fichier: str) -> bool:
        return fnmatch.fnmatch(nom_fichier, self.motif_present)

    def se_lit(self, nom_fichier: str) -> bool:
        if not self.concerne(nom_fichier):
            return False
        return not (self.motif_exclu
                    and fnmatch.fnmatch(nom_fichier, self.motif_exclu))


# --- Profils individuels ----------------------------------------------------
#
# `tags_thematiques` a rejoint les champs stables avec #470 : c'est un champ
# **publié** (AGENTS.md §6), il est passé de 647 à 0 dans le run `a125e9e` que
# #460 documente — et il ne figurait dans aucune des deux catégories. Le
# rapport de #460 le comptait dans ses dégâts sans que le contrôle le regarde.
#
# `dossiers_legislatifs` est conservé bien qu'inerte : mesuré sur les 209
# profils de `3a8455a` et sur les 7 refs de l'historique récent, aucun pivot ne
# porte cette clé — c'est un champ de `raw_data/profiles`, que
# `normalize_profil` verse dans `textes_portes`. Le garder ne coûte rien et
# couvre `--profils-dir raw_data/profiles`.
#
# `chambres` (#493) est signalé et non bloquant. Signalé, parce qu'un champ
# publié qui ne figure dans aucune des deux catégories est exactement la faille
# que #470 a payée sur `tags_thematiques`. Non bloquant, parce que la perte qui
# compte est déjà couverte : `chambre` est un scalaire surveillé, et il vaut
# `chambres[0]` — `chambres` ne peut pas se vider sans que `chambre` régresse
# vers `null`, ce qui bloque déjà. En faire un champ stable ajouterait un
# second verrou sur le même événement. Et la seule baisse réelle possible —
# `--no-merge` recollectant moins de mandats qu'avant — fait d'abord tomber
# `mandats`, qui est un champ **stable** : le blocage est déjà là, sur la cause
# plutôt que sur son reflet.
#
# `sources` est signalé et non bloquant : son historique montre des baisses
# (2 → 1, 3 → 2) qui accompagnent aussi bien une perte réelle qu'une
# sous-collecte non rejouée. Bloquer dessus doublerait l'alerte des champs qui
# la causent vraiment.
COLLECTION_PROFILS = Collection(
    nom="profiles",
    sous_chemin="profiles",
    listes_stables=(
        "votes", "mandats", "textes_portes", "interventions",
        "tags_thematiques", "dossiers_legislatifs",
    ),
    listes_signalees=("amendements", "sources", "chambres"),
    scalaires=("id", "nom", "chambre", "parti", "groupe", "identite",
               "meta.provenance"),
    motif_present="*.json",
    obligatoire=True,
)

# --- Groupes parlementaires -------------------------------------------------
#
# `cohesion_votes` est LE champ de #470 : un dénominateur publié (AGENTS.md
# §2.7). `membres`, `mandats_agreges` et `tags_thematiques_agreges` en sont les
# entrées amont — les trois sont tombés ensemble sur SOC-16.
#
# `effectif.actuel` est volontairement absent des scalaires : c'est un compte
# de membres **actifs**, qui baisse légitimement quand un élu quitte le groupe
# (observé : REN-16 50 → 77 dans l'autre sens sur le même run). `membres`
# couvre déjà la perte d'enregistrement.
#
# `meta.couverture_roster.roster_total` en revanche est surveillé : c'est le
# dénominateur réel du groupe, issu d'un fetch réseau, et le seul champ dont la
# disparition rendrait un ratio publié incalculable sans que rien ne le dise.
COLLECTION_GROUPES = Collection(
    nom="groupes",
    sous_chemin="groupes",
    listes_stables=("membres", "cohesion_votes", "mandats_agreges",
                    "tags_thematiques_agreges", "historique_noms"),
    listes_signalees=("sources",),
    scalaires=("groupe_id", "groupe_sigle", "groupe_nom", "chambre",
               "legislature", "periode.debut",
               "meta.couverture_roster.roster_total"),
)

COLLECTION_PARTIS = Collection(
    nom="partis",
    sous_chemin="partis",
    listes_stables=("candidats", "tags_thematiques_agreges"),
    listes_signalees=("sources",),
    scalaires=("parti_id", "parti_nom"),
)

# `premier_ministre` est un bloc nullable : sa perte a été observée dans
# l'autre sens (null → renseigné, run `d96799c`), ce qui prouve qu'il peut
# aussi repartir.
COLLECTION_GOUVERNEMENTS = Collection(
    nom="gouvernements",
    sous_chemin="gouvernements",
    listes_stables=("membres", "textes"),
    listes_signalees=("sources",),
    scalaires=("gouvernement_id", "nom", "premier_ministre", "periode.debut"),
)

# --- Index partagés (#431, #432) --------------------------------------------
#
# `scrutins` et `amendements` sont des CONTENEURS d'entrées distinctes : une
# liste pour l'un, un dict indexé par `amendement_id` pour l'autre. `len()`
# rend le nombre d'entrées distinctes dans les deux cas.
#
# Baisse SIGNALÉE et non bloquante — l'arbitrage est explicite. Une baisse y
# serait grave (AGENTS.md : « an uncommitted index leaves every mapping
# pointing at nothing, silently ») mais elle est aussi le résultat attendu
# d'une correction de clé, ce qu'ont fait #431 et #432. Or ces compteurs sont
# des totaux de corpus, pas des mesures par fiche : les bloquer forcerait
# l'opérateur à relancer avec `--tolerer-pertes`, qui désarme du même coup les
# contrôles **précis** par profil et par groupe. Bloquer sur le compteur le
# plus grossier pour faire taire les plus fins serait le pire des échanges.
#
# La disparition d'un fichier d'index, elle, reste bloquante : elle n'a aucune
# explication légitime et laisse chaque mapping pointer dans le vide.
COLLECTION_INDEX_SCRUTINS = Collection(
    nom="index scrutins",
    sous_chemin="",
    listes_signalees=("scrutins",),
    scalaires=("schema_version", "licence_donnees"),
    motif_present="scrutins.json",
)

COLLECTION_INDEX_AMENDEMENTS = Collection(
    nom="index amendements",
    sous_chemin="amendements",
    listes_signalees=("amendements",),
    scalaires=("schema_version", "legislature", "licence_donnees"),
    motif_present="*.json",
    # Les `*.cosignatures.json` sont listés mais jamais ouverts : 222 Mio de
    # RSS pour le seul `15.cosignatures.json`, aucun consommateur (AGENTS.md
    # §3), et leur disparition est détectée par le listing.
    motif_exclu="*.cosignatures.json",
)

COLLECTIONS_AGREGATS: tuple[Collection, ...] = (
    COLLECTION_GROUPES,
    COLLECTION_PARTIS,
    COLLECTION_GOUVERNEMENTS,
    COLLECTION_INDEX_SCRUTINS,
    COLLECTION_INDEX_AMENDEMENTS,
)

# Compatibilité : ces noms désignent le périmètre historique, celui des
# profils. Ils restent le vocabulaire du rapport et des tests.
CHAMPS_STABLES: tuple[str, ...] = COLLECTION_PROFILS.listes_stables
CHAMPS_HAUSSE_ATTENDUE: tuple[str, ...] = COLLECTION_PROFILS.listes_signalees
TOUS_CHAMPS: tuple[str, ...] = COLLECTION_PROFILS.tous_champs


# ---------------------------------------------------------------------------
# Relevé d'un document
# ---------------------------------------------------------------------------

def _chemin_pointe(doc: Any, chemin: str) -> Any:
    """Valeur d'un chemin pointé (`meta.provenance`), `None` si la route casse."""
    courant = doc
    for segment in chemin.split("."):
        if not isinstance(courant, dict):
            return None
        courant = courant.get(segment)
    return courant


def _resume_scalaire(valeur: Any) -> Any:
    """Réduit un scalaire à une valeur comparable et sérialisable en JSON.

    `None` signifie « non renseigné », et c'est la seule chose sur laquelle le
    contrôle bloque. Un conteneur vide (`{}`, `[]`) ou une chaîne blanche
    valent `None` : la convention du dépôt est que manquant s'écrit `null`, et
    un `""` qui remplace un nom n'est pas moins une perte (règle §2.5).

    `0` et `False` sont en revanche des valeurs **renseignées** — d'où le test
    `is None` partout, jamais un test de vérité.
    """
    if valeur is None:
        return None
    if isinstance(valeur, str):
        return valeur if valeur.strip() else None
    if isinstance(valeur, bool) or isinstance(valeur, (int, float)):
        return valeur
    if isinstance(valeur, (dict, list, tuple)):
        # Le contenu d'un bloc (`identite`, `premier_ministre`) n'est pas
        # comparé : seule sa présence l'est. Comparer les blocs entiers ferait
        # du bruit sur chaque enrichissement.
        return "<renseigné>" if len(valeur) else None
    return str(valeur)


def relever(doc: Any, collection: Collection) -> dict[str, Any]:
    """Relevé d'un document : longueurs de conteneurs + scalaires surveillés.

    Un champ absent vaut 0 — indistinct d'une liste vide, ce qui est le
    comportement voulu : dans les deux cas le document ne porte aucune entrée.

    `len()` et non `len(list)` : les index partagés indexent leurs entrées dans
    un **dict** (`amendements` par `amendement_id`), les profils dans une
    liste. Le nombre d'entrées distinctes est `len()` des deux côtés.
    """
    if not isinstance(doc, dict):
        raise ValueError("document JSON qui n'est pas un objet")
    listes: dict[str, int] = {}
    for champ in collection.tous_champs:
        valeur = doc.get(champ)
        listes[champ] = len(valeur) if isinstance(valeur, (list, dict)) else 0
    scalaires = {
        chemin: _resume_scalaire(_chemin_pointe(doc, chemin))
        for chemin in collection.scalaires
    }
    return {"listes": listes, "scalaires": scalaires, "lu": True}


def _releve_non_lu() -> dict[str, Any]:
    """Fichier dont on ne surveille que la présence (`*.cosignatures.json`)."""
    return {"listes": {}, "scalaires": {}, "lu": False}


# ---------------------------------------------------------------------------
# Lecture
# ---------------------------------------------------------------------------

def lire_collection_git(
    ref: str, repertoire: str, collection: Collection
) -> Optional[dict[str, dict[str, Any]]]:
    """Relève chaque fichier d'une collection dans une référence git.

    `git cat-file --batch` plutôt qu'un `git show` par fichier : sur 752
    profils de ~10 Mo, lancer autant de processus prend des minutes. Ici un
    seul processus reçoit la liste des chemins et renvoie les blobs à la
    suite.

    Rend `None` si le chemin n'existe pas dans la référence et que la
    collection n'est pas obligatoire — un répertoire qui n'existait pas encore
    n'est pas un constat de perte, c'est une absence de point de comparaison.
    """
    listing = subprocess.run(
        ["git", "ls-tree", "--name-only", f"{ref}:{repertoire}".rstrip(":")],
        capture_output=True, text=True,
    )
    if listing.returncode != 0:
        if not collection.obligatoire:
            return None
        raise SystemExit(
            f"[!] Chemin introuvable dans la référence git : {ref}:{repertoire}\n"
            "    `--ref-dir` vaut par défaut `--profils-dir`. Si les profils "
            "régénérés sont hors du dépôt (répertoire de mesure, worktree...), "
            "préciser le chemin côté référence :\n"
            "      --profils-dir /chemin/hors/depot --ref-dir pivot_data/profiles"
        )
    fichiers = [f for f in listing.stdout.split() if collection.concerne(f)]
    if not fichiers:
        return {}

    a_lire = [f for f in fichiers if collection.se_lit(f)]
    resultats: dict[str, dict[str, Any]] = {
        f: _releve_non_lu() for f in fichiers if not collection.se_lit(f)
    }
    if not a_lire:
        return resultats

    # Lecture EN FLUX du `--batch`, blob par blob. `capture_output=True`
    # bufferisait la totalité des profils avant d'en compter la première
    # entrée : 3,2 Gio de RSS sur les 209 profils du 19/08/2026, et un process
    # tué par l'OOM killer. À 752 profils ce serait ~11 Go, donc un échec
    # certain en CI — pour un script dont tout l'intérêt est de tourner AVANT
    # le commit (#460).
    #
    # Seuls les relevés sont retenus, jamais les documents : la mémoire ne
    # dépend plus que du plus gros blob (~26 Mo), pas du corpus. Même
    # correction que sur l'index des scrutins (#432) et sur celui des
    # amendements (#431) — c'est le troisième outil de ce dépôt à buter là-
    # dessus. Les `*.cosignatures.json` ne sont même pas demandés au `--batch`
    # (#470) : leur présence se lit dans le listing ci-dessus.
    prefixe = f"{ref}:{repertoire}/" if repertoire else f"{ref}:"
    proc = subprocess.Popen(
        ["git", "cat-file", "--batch"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
    )
    assert proc.stdin is not None and proc.stdout is not None

    try:
        for fichier in a_lire:
            proc.stdin.write(f"{prefixe}{fichier}\n".encode())
            proc.stdin.flush()
            entete = proc.stdout.readline().split()
            if len(entete) < 3:        # « <oid> missing »
                continue
            taille = int(entete[2])
            contenu = proc.stdout.read(taille)
            proc.stdout.read(1)        # saut de ligne final
            try:
                resultats[fichier] = relever(json.loads(contenu), collection)
            except ValueError:
                continue
            finally:
                del contenu
    finally:
        proc.stdin.close()
        proc.stdout.read()
        proc.wait()
    return resultats


def lire_collection_disque(
    repertoire: Path, collection: Collection
) -> Optional[dict[str, dict[str, Any]]]:
    """Relève chaque fichier d'une collection sur le disque.

    Rend `None` si le répertoire n'existe pas et que la collection n'est pas
    obligatoire — symétrique de `lire_collection_git`.
    """
    if not repertoire.is_dir():
        return None if not collection.obligatoire else {}
    resultats: dict[str, dict[str, Any]] = {}
    for chemin in sorted(repertoire.iterdir()):
        if not chemin.is_file() or not collection.concerne(chemin.name):
            continue
        if not collection.se_lit(chemin.name):
            resultats[chemin.name] = _releve_non_lu()
            continue
        try:
            resultats[chemin.name] = relever(
                json.loads(chemin.read_bytes()), collection)
        except (OSError, ValueError):
            continue
    return resultats


def lire_profils_git(ref: str, repertoire: str) -> dict[str, dict[str, Any]]:
    """Relevé des profils d'une référence git (périmètre historique)."""
    return lire_collection_git(ref, repertoire, COLLECTION_PROFILS) or {}


def lire_profils_disque(repertoire: Path) -> dict[str, dict[str, Any]]:
    """Relevé des profils sur le disque (périmètre historique)."""
    return lire_collection_disque(repertoire, COLLECTION_PROFILS) or {}


# ---------------------------------------------------------------------------
# Comparaison
# ---------------------------------------------------------------------------

def _listes(releve: dict[str, Any], champ: str) -> int:
    return int(releve.get("listes", {}).get(champ, 0))


def comparer(
    avant: dict[str, dict[str, Any]],
    apres: dict[str, dict[str, Any]],
    collection: Collection = COLLECTION_PROFILS,
) -> dict[str, Any]:
    """Compare deux relevés d'une même collection. Fonction pure.

    Trois familles de constats bloquants :
      - un fichier présent avant et absent après ;
      - une baisse sur une liste stable ;
      - un scalaire surveillé passé de renseigné à `null`.

    Et deux familles non bloquantes, relevées dans le rapport : les baisses sur
    les listes signalées, et les changements de valeur d'un scalaire.
    """
    pertes: list[dict[str, Any]] = []
    gains: list[dict[str, Any]] = []
    pertes_scalaires: list[dict[str, Any]] = []
    evolutions_scalaires: list[dict[str, Any]] = []

    for fichier in sorted(set(avant) | set(apres)):
        a, b = avant.get(fichier), apres.get(fichier)
        if a is None:
            gains.append({"fichier": fichier, "champ": "(fichier entier)",
                          "avant": 0, "apres": sum(b.get("listes", {}).values()),
                          "stable": False})
            continue
        if b is None:
            # Un fichier disparu est une perte, y compris quand son contenu
            # n'était pas lu (`*.cosignatures.json`) : c'est justement le cas
            # catastrophique que le listing seul suffit à voir.
            pertes.append({"fichier": fichier, "champ": "(fichier entier)",
                           "avant": sum(a.get("listes", {}).values()) or 1,
                           "apres": 0, "stable": True})
            continue
        for champ in collection.tous_champs:
            av, ap = _listes(a, champ), _listes(b, champ)
            if ap < av:
                pertes.append({"fichier": fichier, "champ": champ,
                               "avant": av, "apres": ap,
                               "stable": champ in collection.listes_stables})
            elif ap > av:
                gains.append({"fichier": fichier, "champ": champ,
                              "avant": av, "apres": ap,
                              "stable": champ in collection.listes_stables})
        for chemin in collection.scalaires:
            va = a.get("scalaires", {}).get(chemin)
            vb = b.get("scalaires", {}).get(chemin)
            if va == vb:
                continue
            if va is not None and vb is None:
                pertes_scalaires.append(
                    {"fichier": fichier, "champ": chemin, "avant": va, "apres": None})
            elif va is not None:
                evolutions_scalaires.append(
                    {"fichier": fichier, "champ": chemin, "avant": va, "apres": vb})
            # va is None : le scalaire apparaît. C'est un gain, pas un constat.

    pertes_stables = [p for p in pertes if p["stable"]]
    return {
        "collection": collection.nom,
        "nb_avant": len(avant),
        "nb_apres": len(apres),
        "pertes": pertes,
        "gains": gains,
        "pertes_sur_champs_stables": pertes_stables,
        "pertes_scalaires": pertes_scalaires,
        "evolutions_scalaires": evolutions_scalaires,
        "bloquant": bool(pertes_stables) or bool(pertes_scalaires),
        "totaux_avant": {c: sum(_listes(v, c) for v in avant.values())
                         for c in collection.tous_champs},
        "totaux_apres": {c: sum(_listes(v, c) for v in apres.values())
                         for c in collection.tous_champs},
    }


def comparer_tout(
    releves: list[tuple[Collection, Optional[dict], Optional[dict]]]
) -> dict[str, Any]:
    """Assemble les rapports de chaque collection en un verdict unique."""
    rapports: list[dict[str, Any]] = []
    ignorees: list[str] = []
    for collection, avant, apres in releves:
        if avant is None and apres is None:
            ignorees.append(collection.nom)
            continue
        rapport = comparer(avant or {}, apres or {}, collection)
        rapport["absente_avant"] = avant is None
        rapport["absente_apres"] = apres is None
        rapports.append(rapport)
    return {
        "collections": rapports,
        "collections_ignorees": ignorees,
        "bloquant": any(r["bloquant"] for r in rapports),
        "nb_pertes_bloquantes": sum(
            len(r["pertes_sur_champs_stables"]) + len(r["pertes_scalaires"])
            for r in rapports
        ),
    }


# ---------------------------------------------------------------------------
# Rapport
# ---------------------------------------------------------------------------

_PLAFOND = 40


def _tableau(lignes: list[dict[str, Any]], entete: str) -> list[str]:
    out = [entete, "| --- | --- | --- | --- |"]
    for ligne in lignes[:_PLAFOND]:
        out.append(f"| `{ligne['fichier']}` | `{ligne['champ']}` | "
                   f"{ligne['avant']} | {ligne['apres']} |")
    if len(lignes) > _PLAFOND:
        out.append(f"| … | | | {len(lignes) - _PLAFOND} de plus |")
    out.append("")
    return out


def _section_collection(rapport: dict[str, Any]) -> list[str]:
    nom = rapport["collection"]
    lignes = [f"## `{nom}`", ""]
    if rapport["absente_avant"]:
        lignes += ["Absente de la référence : tout y est un gain.", ""]
    if rapport["absente_apres"]:
        lignes += ["**Absente du disque alors qu'elle existait dans la "
                   "référence.** Perte totale.", ""]
    lignes += [f"{rapport['nb_avant']} fichier(s) avant, "
               f"{rapport['nb_apres']} après.", ""]

    if rapport["totaux_avant"]:
        lignes += ["| Champ | Avant | Après | Écart |", "| --- | --- | --- | --- |"]
        for champ, avant in rapport["totaux_avant"].items():
            apres = rapport["totaux_apres"][champ]
            lignes.append(f"| `{champ}` | {avant} | {apres} | {apres - avant:+} |")
        lignes.append("")

    pertes_stables = rapport["pertes_sur_champs_stables"]
    if pertes_stables:
        lignes += [f"**{len(pertes_stables)} perte(s) sur une liste stable** — "
                   "une baisse n'y a pas d'explication attendue.", ""]
        lignes += _tableau(pertes_stables,
                           "| Fichier | Champ | Avant | Après |")
    pertes_scalaires = rapport["pertes_scalaires"]
    if pertes_scalaires:
        lignes += [f"**{len(pertes_scalaires)} scalaire(s) passé(s) de renseigné "
                   "à `null`** — la fusion ne régresse jamais vers `null` "
                   "(AGENTS.md §3) : c'est une violation de contrat, pas un "
                   "fait mesuré.", ""]
        lignes += _tableau(pertes_scalaires,
                           "| Fichier | Champ | Avant | Après |")
    if not pertes_stables and not pertes_scalaires:
        lignes += ["Aucune perte bloquante.", ""]

    signalees = [p for p in rapport["pertes"] if not p["stable"]]
    if signalees:
        lignes += [f"<details><summary>{len(signalees)} baisse(s) signalée(s), "
                   "non bloquante(s)</summary>", ""]
        lignes += _tableau(signalees, "| Fichier | Champ | Avant | Après |")
        lignes += ["</details>", ""]
    evolutions = rapport["evolutions_scalaires"]
    if evolutions:
        lignes += [f"<details><summary>{len(evolutions)} changement(s) de valeur "
                   "d'un scalaire, non bloquant(s)</summary>", "",
                   "Normalisations, accents et bascules de source sont "
                   "légitimes et majoritaires ; un changement de `chambre` ou "
                   "d'`id` mérite un regard.", ""]
        lignes += _tableau(evolutions, "| Fichier | Champ | Avant | Après |")
        lignes += ["</details>", ""]
    lignes += [f"{len(rapport['gains'])} augmentation(s) relevée(s).", ""]
    return lignes


def generate_markdown_report(rapport: dict[str, Any], ref: str) -> str:
    """Rapport Markdown. Accepte un rapport de collection ou le rapport global."""
    if "collections" not in rapport:      # rapport d'une seule collection
        rapport = {"collections": [dict(rapport, absente_avant=False,
                                        absente_apres=False)],
                   "collections_ignorees": [],
                   "bloquant": rapport["bloquant"],
                   "nb_pertes_bloquantes": (
                       len(rapport["pertes_sur_champs_stables"])
                       + len(rapport["pertes_scalaires"]))}

    lignes = [
        "# Diff de `pivot_data/` avant / après régénération",
        "",
        f"Référence comparée : `{ref}`.",
        "",
        "> Les totaux ne suffisent pas : une hausse globale des amendements "
        "masquerait des pertes individuelles. Le verdict porte sur le détail "
        "de chaque fichier.",
        "",
    ]
    if rapport["bloquant"]:
        lignes += [f"**{rapport['nb_pertes_bloquantes']} constat(s) bloquant(s)** "
                   "— à élucider avant de committer.", ""]
    else:
        lignes += ["**Aucune perte bloquante**, sur aucune des collections "
                   "comparées.", ""]
    if rapport["collections_ignorees"]:
        lignes += ["Collections absentes des deux côtés, donc non comparées : "
                   + ", ".join(f"`{n}`" for n in rapport["collections_ignorees"])
                   + ".", ""]
    for sous in rapport["collections"]:
        lignes += _section_collection(sous)
    lignes += [
        "## Hors périmètre de ce contrôle",
        "",
        "- le **contenu** d'un scalaire de type bloc (`identite`, "
        "`premier_ministre`) : seule sa présence est comparée ;",
        "- les `*.cosignatures.json`, dont seule la présence est vérifiée "
        "(222 Mio de RSS pour les ouvrir, aucun consommateur) ;",
        "- l'**intégrité référentielle** entre un `votes[].scrutin_id` et "
        "`scrutins.json` : un mapping peut pointer dans le vide sans qu'aucun "
        "compteur ne bouge. Couverte depuis #485 par un contrôle distinct, "
        "`src/audit_integrite_referentielle.py`, qui tourne juste après "
        "celui-ci — une invariance dans un état donné n'est pas une variation "
        "dans le temps, et sa tolérance est cloisonnée de celle-ci ;",
        "- la **valeur** des entrées d'une liste : seule leur cardinalité est "
        "comparée.",
        "",
    ]
    return "\n".join(lignes)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--ref", default="origin/main", metavar="REF",
                        help="Référence git servant d'avant (défaut : origin/main).")
    parser.add_argument("--profils-dir", default="pivot_data/profiles", metavar="REP",
                        help="Répertoire des profils régénérés (défaut : pivot_data/profiles).")
    parser.add_argument("--ref-dir", default=None, metavar="REP",
                        help="Répertoire des profils côté référence, si différent de --profils-dir.")
    parser.add_argument("--pivot-dir", default="pivot_data", metavar="REP",
                        help="Racine des agrégats et index (groupes, partis, "
                             "gouvernements, scrutins.json, amendements/). "
                             "Défaut : pivot_data.")
    parser.add_argument("--ref-pivot-dir", default=None, metavar="REP",
                        help="Racine des agrégats côté référence, si différente de --pivot-dir.")
    parser.add_argument("--seulement-profils", action="store_true",
                        help="Restreindre au périmètre d'avant #470 : les "
                             "profils seuls, sans les agrégats ni les index.")
    parser.add_argument("--out", metavar="FICHIER", help="Rapport Markdown.")
    parser.add_argument("--out-json", metavar="FICHIER", help="Rapport JSON.")
    parser.add_argument(
        "--tolerer-pertes", action="store_true",
        help="Ne pas sortir en erreur en cas de perte bloquante. "
             "À n'utiliser qu'après avoir élucidé chaque perte.",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    ref_dir = args.ref_dir or args.profils_dir
    ref_pivot = args.ref_pivot_dir or args.pivot_dir

    releves: list[tuple[Collection, Optional[dict], Optional[dict]]] = []

    print(f"→ {COLLECTION_PROFILS.nom} : {args.ref}:{ref_dir} ↔ {args.profils_dir}…",
          file=sys.stderr)
    releves.append((
        COLLECTION_PROFILS,
        lire_profils_git(args.ref, ref_dir),
        lire_profils_disque(Path(args.profils_dir)),
    ))

    if not args.seulement_profils:
        for collection in COLLECTIONS_AGREGATS:
            chemin_ref = f"{ref_pivot}/{collection.sous_chemin}".rstrip("/")
            chemin_disque = Path(args.pivot_dir) / collection.sous_chemin
            print(f"→ {collection.nom} : {args.ref}:{chemin_ref} ↔ {chemin_disque}…",
                  file=sys.stderr)
            releves.append((
                collection,
                lire_collection_git(args.ref, chemin_ref, collection),
                lire_collection_disque(chemin_disque, collection),
            ))

    profils_avant, profils_apres = releves[0][1], releves[0][2]
    if not profils_avant and not profils_apres:
        print("[!] Aucun profil des deux côtés.", file=sys.stderr)
        return 1

    rapport = comparer_tout(releves)
    markdown = generate_markdown_report(rapport, args.ref)

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(markdown, encoding="utf-8")
        print(f"→ Rapport écrit : {args.out}", file=sys.stderr)
    else:
        print(markdown)
    if args.out_json:
        Path(args.out_json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out_json).write_text(
            json.dumps(rapport, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    if rapport["bloquant"]:
        for sous in rapport["collections"]:
            for perte in sous["pertes_sur_champs_stables"]:
                print(f"[!] {sous['collection']} · {perte['fichier']} · "
                      f"{perte['champ']} : {perte['avant']} → {perte['apres']}",
                      file=sys.stderr)
            for perte in sous["pertes_scalaires"]:
                print(f"[!] {sous['collection']} · {perte['fichier']} · "
                      f"{perte['champ']} : {perte['avant']!r} → null",
                      file=sys.stderr)
        print(f"[!] {rapport['nb_pertes_bloquantes']} constat(s) bloquant(s).",
              file=sys.stderr)
        return 0 if args.tolerer_pertes else 1
    print("✓ Aucune perte bloquante sur les collections comparées.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
