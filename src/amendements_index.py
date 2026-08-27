#!/usr/bin/env python3
"""amendements_index.py — Liste dédupliquée des amendements, partagée (#431).

Un amendement est **identique pour tous ses signataires** : `texte_vise`,
`sort`, `date`, `numero`, `type_deposant`, `premier_signataire`,
`co_signataires`… Seul le `role_signataire` est propre au membre. Pourtant
`_parse_amendement_entry` produit un enregistrement complet **par signataire**,
chacun portant sa propre copie de la liste des cosignataires : pour un
amendement à N cosignataires, N copies d'une liste de N éléments.

Mesuré sur les 209 profils pivot committés au 19/08/2026 (`ff3639b`) :

| | paires | distincts | duplication |
| --- | --- | --- | --- |
| `amendements` | 810 552 | 207 238 | × 3,9 |
| `amendements[].co_signataires` | 77 666 854 | 4 957 807 | **× 15,7** |

Le vrai coût n'est donc pas l'amendement mais **sa liste de cosignataires** :
23,9 cosignataires en moyenne, recopiée dans le profil de chacun d'eux. C'est
1 083,9 Mo des 1 342,4 Mo qu'`amendements[]` pèse dans les profils pivot.

CE QUI RESTE DANS LE PROFIL. Le mapping `{amendement_id, role_signataire}` —
exactement ce qui est propre au membre. Principe directeur de l'épic #429 :
normaliser, jamais supprimer.

L'IDENTIFIANT. `an:<uid>` — convention `<source>:<identifiant_source>` du dépôt.
L'`uid` AN est la **seule** clé unique d'un amendement : le `numero`
(`numeroLong`) repart à chaque texte, et keyer par lui écrase 74,9 % des
amendements (#440, [[amendements-cle-uid]]). Sa couverture est de 100 % sur les
810 552 paires committées — c'est ce qui débloque cette normalisation.

OÙ VIT LA LISTE. Un fichier **par législature**, plus un fichier compagnon pour
les cosignatures :

    pivot_data/amendements/<legislature>.json               (méta)
    pivot_data/amendements/<legislature>.cosignatures.json  (cosignatures)

Ce n'est pas une préférence, c'est une contrainte mesurée — voir
docs/technical_decisions.md#normalisation-amendements. Un fichier global
unique pèserait **128,8 Mo** sur les seuls 209 profils actuels, au-delà de la
limite GitHub de 100 Mo par blob ; et un fichier par législature contenant
aussi les cosignatures atteindrait ~166 Mo pour la XVe à couverture complète
des archives AN (746 000 amendements pour les législatures 14-17).

POURQUOI LES COSIGNATURES À PART. Elles pèsent 75,7 Mo des 128,8 Mo (59 %) et
**aucun consommateur ne les lit** aujourd'hui : ni `group_profile`, ni l'UI, ni
les audits. Les isoler leur évite de télécharger 59 % d'un index dont ils
n'utilisent rien, tout en les gardant accessibles — un réseau de cosignatures
est de la matière première d'analyse (#324). Elles ne sont **jamais** supprimées.

CE QUI N'EST PAS NORMALISÉ. `raw_data/profiles` garde ses amendements
dénormalisés : c'est la couche source-near, et c'est **d'elle** que l'index est
reconstruit. Même décision que pour les votes ([[normalisation-votes]]).

NE JAMAIS RE-MATÉRIALISER LA FORME PLATE. Aucune fonction de ce module ne
reconstruit un enregistrement complet par signataire, et `get()` rend
**l'objet partagé lui-même**, jamais une copie. C'est l'erreur qu'avait faite
`_load_frozen_amendement_index` en appelant `_expand_aggregated_amendements_index`
« pour que le reste du pipeline n'ait pas à distinguer les deux origines » :
facteur ~21 et un OOM (#377, [[cache-amendements-forme-dedupliquee]]).
Verrouillé par `tests/test_amendements_index.py`.
"""

import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Iterator, Optional

from json_io import ecrire_profil_json
from licences import LICENCE_AN

SCHEMA_VERSION = "amendements-v1"
COSIGNATURES_SCHEMA_VERSION = "amendements-cosignatures-v1"
SOURCE_AN = "an"

DEFAULT_AMENDEMENTS_DIR = Path("pivot_data") / "amendements"

#: Alias du libellé canonique, qui vit dans `licences` depuis #530 (lot 6) :
#: une seule fabrique pour toutes les mentions d'attribution du pipeline.
LICENCE_DONNEES = LICENCE_AN

# Champs de l'amendement, communs à tous ses signataires. Le mapping du profil
# n'en porte aucun : les y laisser, c'est la duplication que #431 supprime.
#
# `co_signataires` n'y figure pas : il vit dans le fichier compagnon, pour que
# les consommateurs qui ne le lisent pas (tous, aujourd'hui) n'en chargent pas
# les 75,7 Mo.
CHAMPS_AMENDEMENT = (
    "texte_vise",
    "sort",
    "base_juridique_irrecevabilite",
    "premier_signataire",
    "type_deposant",
    "date",
    "numero",
    "source_url",
)

# Bucket des amendements dont l'`uid` ne porte pas de législature reconnaissable.
# Zéro cas sur les données actuelles ; le bucket existe pour que le jour où il
# s'en présente un, il soit rangé quelque part de nommé plutôt que doté d'une
# législature devinée (AGENTS.md §2.5).
LEGISLATURE_INCONNUE = "inconnue"

_RE_LEGISLATURE_UID = re.compile(r"^AMANR5L(\d+)")

_SUFFIXE_COSIGNATURES = ".cosignatures.json"


def cle_amendement(uid: Any) -> Optional[str]:
    """`AMANR5L17PO59051B2464P0D1N000312` → `an:AMANR5L17PO59051B2464P0D1N000312`.

    `None` si l'`uid` est absent : un amendement sans `uid` n'a **pas** de clé,
    et on ne lui en invente pas (AGENTS.md §2.5). Son enregistrement complet est
    alors conservé côté profil sous `amendement_non_resolu`.
    """
    if not isinstance(uid, str) or not uid:
        return None
    return f"{SOURCE_AN}:{uid}"


def decomposer_id(amendement_id: Any) -> Optional[str]:
    """`"an:AMANR5L17…"` → `"AMANR5L17…"`. `None` si la forme n'est pas
    reconnue — un identifiant mal formé ne doit pas se faire deviner."""
    if not isinstance(amendement_id, str):
        return None
    prefixe = f"{SOURCE_AN}:"
    if not amendement_id.startswith(prefixe):
        return None
    uid = amendement_id[len(prefixe):]
    return uid or None


def legislature_de_uid(uid: Any) -> Optional[str]:
    """Législature portée par l'`uid` AN (`AMANR5L17…` → `"17"`).

    Lecture structurelle de l'identifiant, pas une déduction depuis la date :
    c'est l'AN qui l'y écrit. `None` si l'`uid` ne suit pas la forme connue —
    l'appelant range alors l'amendement dans `LEGISLATURE_INCONNUE` plutôt que
    de lui attribuer une législature par défaut.
    """
    if not isinstance(uid, str):
        return None
    m = _RE_LEGISLATURE_UID.match(uid)
    return m.group(1) if m else None


def legislature_de_id(amendement_id: Any) -> Optional[str]:
    """Législature d'un identifiant pivot `an:<uid>`."""
    return legislature_de_uid(decomposer_id(amendement_id))


def _fichier_meta(dossier: Path, legislature: str) -> Path:
    return Path(dossier) / f"{legislature}.json"


def _fichier_cosignatures(dossier: Path, legislature: str) -> Path:
    return Path(dossier) / f"{legislature}{_SUFFIXE_COSIGNATURES}"


class CosignaturesNonChargees(RuntimeError):
    """Écrire un index chargé sans ses cosignatures les effacerait.

    Levée par `ecrire()` plutôt que de publier silencieusement des fichiers de
    cosignatures vides : le principe de l'épic #429 est « normaliser, jamais
    supprimer », et une perte muette est le contraire d'une normalisation.
    """


class AmendementsIndex:
    """Liste dédupliquée des amendements + leurs cosignatures.

    Deux dictionnaires séparés, exactement comme les deux fichiers : un
    consommateur qui n'a besoin que du `sort` ne paie pas les cosignatures.

    `get()` rend **l'objet partagé**, jamais une copie : c'est la propriété qui
    empêche la re-matérialisation de la forme plate (#377).
    """

    def __init__(
        self,
        amendements: Optional[dict[str, dict[str, Any]]] = None,
        cosignatures: Optional[dict[str, list[str]]] = None,
        *,
        cosignatures_chargees: bool = True,
    ) -> None:
        self.par_id: dict[str, dict[str, Any]] = dict(amendements or {})
        self.par_id_cosignatures: dict[str, list[str]] = dict(cosignatures or {})
        # Distingue « chargé sans les cosignatures » de « chargé, aucun
        # cosignataire ». Sans ce drapeau, `co_signataires()` rendrait `[]` dans
        # les deux cas et un appelant conclurait à tort à une absence de
        # cosignataires.
        self.cosignatures_chargees = bool(cosignatures_chargees)

    def __len__(self) -> int:
        return len(self.par_id)

    def __contains__(self, amendement_id: object) -> bool:
        return amendement_id in self.par_id

    def get(self, amendement_id: Optional[str]) -> Optional[dict[str, Any]]:
        """Amendement d'un identifiant, `None` s'il est inconnu.

        `None` et pas une exception : un profil peut référencer un amendement
        qu'un index partiel ne connaît pas encore. Aux appelants d'en faire une
        donnée manquante — jamais une valeur inventée.

        Rend l'objet stocké, **sans copie** : 810 552 copies d'un
        enregistrement, c'est précisément la forme plate qu'on vient de
        supprimer.
        """
        return self.par_id.get(amendement_id) if amendement_id else None

    def co_signataires(self, amendement_id: Optional[str]) -> Optional[list[str]]:
        """Cosignataires d'un amendement.

        `[]` si l'amendement est connu et n'en a pas ; `None` si l'amendement
        est inconnu **ou** si les cosignatures n'ont pas été chargées — deux
        situations où répondre `[]` serait affirmer une absence non constatée.
        """
        if not self.cosignatures_chargees or not amendement_id:
            return None
        if amendement_id not in self.par_id:
            return None
        return self.par_id_cosignatures.get(amendement_id, [])

    def legislatures(self) -> list[str]:
        """Législatures représentées, triées. `LEGISLATURE_INCONNUE` en dernier."""
        vues = {
            legislature_de_id(amendement_id) or LEGISLATURE_INCONNUE
            for amendement_id in self.par_id
        }
        connues = sorted(v for v in vues if v != LEGISLATURE_INCONNUE)
        return connues + ([LEGISLATURE_INCONNUE] if LEGISLATURE_INCONNUE in vues else [])

    def ids_de_legislature(self, legislature: str) -> list[str]:
        """Identifiants d'une législature, triés — ordre stable d'un run à
        l'autre, pour que git ne voie que les vraies différences."""
        return sorted(
            amendement_id
            for amendement_id in self.par_id
            if (legislature_de_id(amendement_id) or LEGISLATURE_INCONNUE) == legislature
        )


def joindre(
    mapping: Optional[Iterable[dict[str, Any]]], index: Optional[AmendementsIndex]
) -> Iterator[tuple[dict[str, Any], Optional[dict[str, Any]]]]:
    """Itère `(entrée du mapping, amendement partagé)` — **un générateur**.

    C'est le seul chemin de lecture offert aux consommateurs, et il est
    volontairement paresseux : rendre une liste de 810 552 enregistrements
    joints reconstruirait exactement la forme plate que #431 supprime, avec le
    facteur ~21 et l'OOM de #377. `tests/test_amendements_index.py` verrouille
    à la fois la paresse et l'identité (`is`) de l'objet rendu.

    L'amendement vaut `None` quand l'index ne le connaît pas (index partiel) ou
    quand l'entrée n'a pas d'identifiant. L'appelant en fait une donnée
    manquante **comptée**, jamais une exclusion muette (AGENTS.md §2.7).
    """
    for entree in (mapping or ()):
        if not isinstance(entree, dict):
            continue
        amendement_id = entree.get("amendement_id")
        yield entree, (index.get(amendement_id) if index is not None else None)


def _valeur_amendement(champ: str, brut: dict[str, Any], courant: Any) -> Any:
    """Valeur partagée d'un champ, en lisant indifféremment un amendement brut
    ou une entrée pivot d'avant #431.

    Un seul champ demande un arbitrage : `premier_signataire`.
    `normalize_profil._normalize_amendement` le réécrivait à l'identifiant
    pivot du profil courant quand celui-ci était l'auteur — c'est la **seule**
    divergence entre les copies d'un même amendement (44 139 cas sur 207 238
    amendements distincts ; les 8 autres champs et `co_signataires` sont
    strictement identiques sur les 810 552 paires, mesuré le 19/08/2026).

    Une valeur propre au profil lecteur n'a rien à faire dans une liste
    partagée : on retient la référence AN (`an:PA…`), qui est celle que la
    collecte produit et la seule indépendante du lecteur. L'information n'est
    pas perdue pour autant : `role_signataire`, resté dans le mapping, dit déjà
    que le membre est l'auteur principal.
    """
    valeur = brut.get(champ)
    if champ == "premier_signataire":
        if isinstance(valeur, str) and valeur.startswith(f"{SOURCE_AN}:"):
            return valeur
        return courant if courant is not None else valeur
    return valeur if valeur is not None else courant


def construire_index(amendements: Iterable[dict[str, Any]]) -> AmendementsIndex:
    """Construit l'index à partir d'un **flux** d'amendements plats.

    Un flux, et une seule passe : accumuler les profils pour les reparcourir
    coûterait 1,5 Go de JSON et se ferait tuer par l'OOM killer — le mode
    d'échec de #377 et #392, puis de la première version de
    `scrutins_index.construire_index`. Ici seuls les 207 238 amendements
    distincts sont retenus, jamais les 810 552 paires.

    Les chaînes sont **internées** : les 4,96 M références de cosignataires ne
    portent que quelques milliers de valeurs distinctes, et les `texte_vise`
    1 976. Sans internement, la construction pèse plusieurs Go ; avec, elle
    tient en ~330 Mio de RSS sur le corpus complet.
    """
    par_id: dict[str, dict[str, Any]] = {}
    cosignatures: dict[str, list[str]] = {}
    intern = sys.intern

    for brut in amendements:
        if not isinstance(brut, dict):
            continue
        amendement_id = cle_amendement(brut.get("uid"))
        if amendement_id is None:
            # Sans `uid`, pas de clé : l'enregistrement reste côté profil, dans
            # `amendement_non_resolu`. Ni supprimé, ni doté d'une clé inventée.
            continue
        amendement_id = intern(amendement_id)
        courant = par_id.get(amendement_id)
        if courant is None:
            courant = {}
            par_id[amendement_id] = courant
        liste_cosign = brut.get("co_signataires")
        if isinstance(liste_cosign, list) and liste_cosign:
            # Chaque copie plate porte la liste COMPLÈTE des cosignataires (0
            # divergence mesurée sur les 810 552 paires) : la dernière vue vaut
            # la première. Une liste vide, elle, ne remplace jamais une liste
            # renseignée — ce serait une régression vers l'absence.
            cosignatures[amendement_id] = [
                intern(ref) for ref in liste_cosign if isinstance(ref, str)
            ]
        for champ in CHAMPS_AMENDEMENT:
            valeur = _valeur_amendement(champ, brut, courant.get(champ))
            courant[champ] = intern(valeur) if isinstance(valeur, str) else valeur

    return AmendementsIndex(par_id, cosignatures)


def merge_amendements_index(
    ancien: AmendementsIndex, nouveau: AmendementsIndex
) -> AmendementsIndex:
    """Fusion additive de deux index : jamais une suppression.

    Un run qui ne régénère qu'une tranche de profils ne voit qu'une partie des
    amendements. Écraser l'index par ce qu'il vient de voir effacerait ceux des
    profils non retraités, et leurs mappings pointeraient dans le vide — la
    panne exacte que #450 a traitée à l'échelle des profils, transposée à
    l'index comme elle l'a été pour les scrutins.

    Sur les champs, la nouvelle valeur gagne si elle est renseignée, sinon
    l'ancienne est conservée (jamais de régression vers `null`) — même règle que
    `merge_dossier_records`, qui pour les amendements laisse la nouvelle entrée
    gagner afin de permettre une correction de sort.

    Sur les cosignatures, la nouvelle liste gagne dès que l'amendement est
    présent dans le nouvel index : chaque copie plate porte la liste **complète**
    (0 divergence mesurée sur 810 552 paires), donc une liste vue par un run
    partiel n'est jamais une liste tronquée. Une liste absente du nouvel index
    ne touche pas l'ancienne.
    """
    if ancien.cosignatures_chargees and nouveau.cosignatures_chargees:
        cosignatures_chargees = True
    else:
        # Fusionner un index amputé de ses cosignatures produirait un index
        # amputé : on le dit plutôt que de le publier.
        cosignatures_chargees = False

    fusionnes: dict[str, dict[str, Any]] = {k: dict(v) for k, v in ancien.par_id.items()}
    for amendement_id, amendement in nouveau.par_id.items():
        existant = fusionnes.get(amendement_id)
        if existant is None:
            fusionnes[amendement_id] = dict(amendement)
            continue
        for champ, valeur in amendement.items():
            if valeur is not None:
                existant[champ] = valeur

    cosignatures = dict(ancien.par_id_cosignatures)
    if nouveau.cosignatures_chargees:
        for amendement_id in nouveau.par_id:
            liste = nouveau.par_id_cosignatures.get(amendement_id)
            if liste:
                cosignatures[amendement_id] = list(liste)

    return AmendementsIndex(
        fusionnes, cosignatures, cosignatures_chargees=cosignatures_chargees
    )


def charger(
    dossier: Path = DEFAULT_AMENDEMENTS_DIR,
    *,
    legislatures: Optional[Iterable[str]] = None,
    avec_cosignatures: bool = True,
) -> AmendementsIndex:
    """Charge l'index depuis son dossier. Index vide si le dossier est absent —
    un premier run n'a rien à charger.

    `legislatures` restreint la lecture aux fichiers utiles : un consommateur
    qui n'affiche qu'un profil de la XVIIe n'a aucune raison de charger les
    trois autres législatures.

    `avec_cosignatures=False` économise 59 % du volume, et c'est ce que font
    tous les consommateurs actuels — aucun ne lit `co_signataires`. Le défaut
    reste `True` : lire partiellement puis réécrire effacerait les cosignatures,
    et `ecrire()` refuse d'ailleurs de le faire.
    """
    dossier = Path(dossier)
    par_id: dict[str, dict[str, Any]] = {}
    cosignatures: dict[str, list[str]] = {}
    if not dossier.is_dir():
        return AmendementsIndex(cosignatures_chargees=avec_cosignatures)

    demandees = set(legislatures) if legislatures is not None else None
    for chemin in sorted(dossier.glob("*.json")):
        if chemin.name.endswith(_SUFFIXE_COSIGNATURES):
            continue
        legislature = chemin.stem
        if demandees is not None and legislature not in demandees:
            continue
        donnees = _lire_json(chemin)
        for amendement_id, amendement in (donnees.get("amendements") or {}).items():
            if isinstance(amendement, dict):
                par_id[amendement_id] = amendement
        if not avec_cosignatures:
            continue
        chemin_cosign = _fichier_cosignatures(dossier, legislature)
        if not chemin_cosign.exists():
            continue
        donnees_cosign = _lire_json(chemin_cosign)
        for amendement_id, refs in (donnees_cosign.get("co_signataires") or {}).items():
            if isinstance(refs, list):
                cosignatures[amendement_id] = refs

    return AmendementsIndex(par_id, cosignatures, cosignatures_chargees=avec_cosignatures)


def _lire_json(chemin: Path) -> dict[str, Any]:
    try:
        with open(chemin, encoding="utf-8") as f:
            donnees = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"  [!] Lecture impossible de {chemin}, ignoré : {exc}")
        return {}
    return donnees if isinstance(donnees, dict) else {}


def ecrire(
    dossier: Path,
    index: AmendementsIndex,
    *,
    genere_le: Optional[str] = None,
) -> list[Path]:
    """Écrit un fichier de méta et un fichier de cosignatures **par
    législature**, en JSON compact (#433).

    Le découpage n'est pas cosmétique : un fichier global unique pèse 128,8 Mo
    sur les seuls profils actuels, au-delà de la limite GitHub de 100 Mo par
    blob. Voir docs/technical_decisions.md#normalisation-amendements.

    Les amendements sont stockés **en dictionnaire** `{id: amendement}` et non
    en liste d'objets portant leur `id` (choix inverse de `scrutins-v1`) : à
    207 238 entrées, la liste imposerait à chaque consommateur une passe de
    réindexation, et l'`id` répété en clé de champ coûterait 1 Mo de plus. Le
    même choix a été fait pour les index figés de `raw_data/amendements_an_figes/`.

    La `legislature` est portée **une fois par fichier**, jamais par entrée :
    toutes les entrées d'un fichier ont la même, et la répéter coûterait 4 Mo.
    """
    if not index.cosignatures_chargees:
        raise CosignaturesNonChargees(
            "Index chargé sans ses cosignatures : l'écrire les effacerait. "
            "Recharger avec avec_cosignatures=True avant toute écriture."
        )
    dossier = Path(dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    ecrits: list[Path] = []
    for legislature in index.legislatures():
        ids = index.ids_de_legislature(legislature)
        chemin = _fichier_meta(dossier, legislature)
        ecrire_profil_json(chemin, {
            "schema_version": SCHEMA_VERSION,
            "legislature": legislature,
            "genere_le": genere_le,
            "licence_donnees": LICENCE_DONNEES,
            "amendements": {i: index.par_id[i] for i in ids},
        })
        ecrits.append(chemin)

        chemin_cosign = _fichier_cosignatures(dossier, legislature)
        ecrire_profil_json(chemin_cosign, {
            "schema_version": COSIGNATURES_SCHEMA_VERSION,
            "legislature": legislature,
            "genere_le": genere_le,
            "licence_donnees": LICENCE_DONNEES,
            # Les amendements sans cosignataire sont absents : leur écrire une
            # liste vide coûterait sans rien dire de plus. `co_signataires()`
            # rend `[]` pour un amendement connu et absent d'ici, `None` pour un
            # amendement inconnu — l'absence de cosignataire et l'absence
            # d'amendement ne se confondent pas.
            "co_signataires": {
                i: index.par_id_cosignatures[i]
                for i in ids
                if index.par_id_cosignatures.get(i)
            },
        })
        ecrits.append(chemin_cosign)
    return ecrits


def iter_amendements_du_repertoire(profils_dir: Path) -> Iterator[dict[str, Any]]:
    """Itère les amendements de tous les profils d'un répertoire, **un profil à
    la fois**.

    Le profil est relâché avant d'ouvrir le suivant : `raw_data/profiles` pèse
    1,5 Go, et le charger d'un bloc fait tuer le process par l'OOM killer (#377,
    #392). Un fichier illisible est signalé et sauté — il ne doit pas priver
    l'index des amendements de tous les autres.
    """
    if not Path(profils_dir).is_dir():
        return
    for chemin in sorted(Path(profils_dir).glob("*.json")):
        if chemin.name.startswith("."):
            continue
        try:
            with open(chemin, encoding="utf-8") as f:
                profil = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            print(f"  [!] Lecture impossible de {chemin}, ignoré : {exc}")
            continue
        for amendement in (profil.get("amendements") or []):
            if isinstance(amendement, dict):
                yield amendement
        del profil


def rafraichir(
    profils_dir: Path,
    dossier: Path = DEFAULT_AMENDEMENTS_DIR,
    *,
    fusionner: bool = True,
    genere_le: Optional[str] = None,
) -> AmendementsIndex:
    """Reconstruit l'index depuis `profils_dir` et l'écrit, en fusionnant avec
    l'existant par défaut.

    `fusionner=True` est le défaut **et le mode sûr** : un run qui ne régénère
    qu'une tranche de profils ne voit qu'une partie des amendements, et écraser
    l'index laisserait les mappings des profils non retraités pointer dans le
    vide (leçon de #450, transposée à l'index).

    `fusionner=False` correspond à `--no-merge` : reconstruction complète, à
    n'utiliser que sur un corpus complet.
    """
    index = construire_index(iter_amendements_du_repertoire(profils_dir))
    if fusionner:
        index = merge_amendements_index(charger(dossier), index)
    ecrire(dossier, index, genere_le=genere_le)
    return index
