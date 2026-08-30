#!/usr/bin/env python3
"""
an_roster.py — La composition des groupes de l'Assemblée nationale est
**dérivée d'AMO30**, le référentiel que le pipeline télécharge déjà (#526).

**Source de production depuis le lot 1b (#527)**, et **seule source depuis le
lot 5 (#529)** : `AN_ROSTER_ACTIF = True`, et `group_roster.fetch_full_roster`
délègue ici toute clé `deputes`. Le drapeau n'est plus un aiguillage — la
lecture NosDéputés vers laquelle il basculait a été retirée — mais un
interrupteur : baissé, le module ne rend **jamais** une liste vide, il refuse
bruyamment (`RosterAnInactif`), et il n'y a alors plus de roster du tout.

## Pourquoi AMO30 plutôt que NosDéputés

`group_roster.py` interroge `https://www.nosdeputes.fr/deputes/json` — 814 Ko
générés à la volée, « aucune réponse en moins de 10 s » mesurées sur 24 appels
(#518), puis **500 déterministe** pendant trois runs (#524). Or la composition
des groupes est déjà dans AMO30
(`tous_acteurs_mandats_organes_xi_legislature`), que `candidate_profile.py`
télécharge et met en cache pour quatre autres index
(`_ensure_acteurs_historique_zip_downloaded`, `.cache/acteurs_historique_an/`).

Trois gains, tous vérifiables :

- **une seule source AN** — la même que les scrutins et les amendements, au
  lieu d'un miroir tiers qui tombe ;
- **Licence Ouverte (attribution)** au lieu d'ODbL *share-alike* (AGENTS §7) ;
- **la 17e législature devient accessible** : NosDéputés n'a jamais été étendu
  au-delà de la 16e, ce que `LEGISLATURE_BY_BASE_URL` traduisait en une table
  de domaines s'arrêtant à la 16e — supprimée par ce lot.

Mesuré le 26/08/2026 sur l'archive réelle : **13,6 Mo**, **3 119 acteurs**,
**63 organes `GP`**, index construit en **~0,6 s** (archive déjà en cache).

## Trois pièges, mesurés, et ce que le module en fait

### 1. `NI` compte 592 membres sur la 16e — le filtrage par dates est obligatoire

L'organe « Non inscrit » **ouvre avant les groupes** : 2022-06-22 contre
2022-06-28 sur la 16e, 2024-07-01 contre 2024-07-18 sur la 17e. Tout le monde
y transite entre les deux dates. Mesuré : **576** mandats `2022-06-22 →
2022-06-28` sur la 16e, **577** mandats se terminant le 2024-07-18 sur la 17e.

Un mandat dont la fin **tombe au plus tard le jour où les groupes de la
législature se constituent** est un transit, pas une appartenance — aucun
groupe réel ne se termine avant d'exister. `date_constitution_groupes()` lit
cette date dans le référentiel lui-même (le plus petit `dateDebut` des organes
`GP` de la législature **hors `NI`**), elle n'est jamais écrite en dur.

Effet mesuré : `NI` 16e **592 → 39**, `NI` 17e **640 → 94**, et **aucun autre
groupe ne perd un seul membre** — le filtre ne coupe que ce qu'il vise.

### 2. Les sigles diffèrent — table committée, pas heuristique

Le sigle AN est `organe.libelleAbrev` (`RE`, `LFI-NUPES`, `SOC-A`,
`UDDPLR`…), pas le sigle publié par ce dépôt (`REN`, `LFI`, `SOC`…), et pas
non plus `libelleAbrege`, qui écrit `LFI - NUPES` avec des espaces et **ne
distingue pas** les deux organes `SOC` de la 16e. La correspondance vit dans
`raw_data/groupes_reels.json`, clé `correspondance_sigles_an` : relue, datée,
avec les organes et l'effectif **mesurés** au moment de la relecture. Une
heuristique sur les sigles rapprocherait `RE` de `REN` et `DR` de rien.

### 3. Un groupe peut avoir deux organes successifs dans une législature

`SOC` 16e : `PO800496` (2022-06-28 → 2023-10-18) puis `PO830170`
(2023-10-19 → 2024-06-09), le second portant `libelleAbrev = "SOC-A"`. Un
roster « par sigle » sans **union** perdrait la moitié de l'année. Le module
prend l'union des organes listés par la table, **déduplique par acteur**, et
recolle les périodes (`mandat_debut` = la plus ancienne, `mandat_fin` = la
plus récente, `None` = mandat ouvert). Même forme sur la 17e :
`AD` → `UDR` → `UDDPLR`.

## Contrat de sortie : celui de `group_roster.fetch_full_roster`

`fetch_full_roster_an()` rend une liste de membres bruts portant
`groupe_sigle` (le sigle **publié**, pas celui de l'AN), `slug`, `nom`,
`mandat_debut`, `mandat_fin` — exactement ce que
`group_roster.filter_roster_by_sigle` lit. Rien en aval n'a à changer pour
consommer cette source ; c'est la condition pour que le lot 1b soit une
bascule et pas une réécriture.

## Le slug vient du lot 2, et son absence est déclarée

AMO30 ne publie aucun identifiant externe : le slug — qui **est** l'`id` du
profil (#487) — vient de `raw_data/correspondance_acteurs_an.json` (#525),
lue à l'envers (`acteur_ref → slug`). Un acteur sans entrée sort avec
`slug: None` **et** dans `membres_sans_slug` du rapport : jamais absent, jamais
inventé (AGENTS §2 règle 5). C'est ce qui explique, entrée par entrée, les
écarts de la 16e — voir `rapport_divergence()`.

## Patron #493 : dérivé + divergence déclarée + condition de retrait

Depuis #527 ce module **est** la source AN, et depuis #529 la seule : le repli
NosDéputés a été retiré du dépôt. L'écart par groupe se lit toujours avec
`python src/an_roster.py --divergence`, entrée par entrée : c'est le
**compteur de migration**, et il reste le seul moyen de relire ce que la
bascule a changé. La condition de retrait du double calcul — les trois clauses
qui autorisent à supprimer le drapeau et le repli — est écrite dans
`docs/decisions/roster-an-derive-amo30-526.md` §9, et son état du
jour dans `docs/decisions/bascule-roster-an-amo30-527.md`.

Usage (depuis la racine du dépôt) :
    python src/an_roster.py --legislature 17 --sigle REN
    python src/an_roster.py --divergence
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import zipfile
from pathlib import Path
from typing import Any, Iterable, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

import correspondance_acteurs_an  # noqa: E402


# ── Le drapeau (patron #510) ─────────────────────────────────────────────────
# ACTIF depuis #527 (lot 1b). Le lot 1 l'avait posé à `False` pour que la
# bascule soit une DÉCISION, prise seule, dans une PR d'une ligne.
#
# Ce qu'il signifie a changé avec #529 : il n'y a plus de seconde source vers
# laquelle basculer, donc plus de `git revert` à préparer. Ce qu'il garde, et
# qui est la seule raison de ne pas le retirer avec le repli, c'est le **refus
# bruyant** : baissé, le module lève au lieu de rendre une liste vide — un
# roster vide est indiscernable d'un groupe dissous une fois écrit sur disque,
# et c'est très exactement le défaut que #511 puis #524 ont payé. Voir
# `_exiger_actif`. Sa condition de retrait est celle du double calcul, #526 §9,
# dont la clause 3 reste ouverte (voir
# docs/decisions/retrait-nosdeputes-529.md).
AN_ROSTER_ACTIF = True

AIDE_ROSTER_AN = (
    "La composition des groupes AN vient d'AMO30 et non de NosDéputés depuis "
    "#527 (lot 1b de l'épic « une seule source AN »), sur la mesure du lot 1 "
    "(#526) : les 5 rosters publiés de la 16e sont reproduits à l'identique à "
    "4 entrées près, toutes nommées et datées dans "
    "raw_data/groupes_reels.json (des membres partis avant la fin de la "
    "législature, sans profil publié, donc sans slug). La 17e législature, que "
    "NosDéputés n'a jamais servie, reste HORS périmètre tant que ses 5 fiches "
    "ne sont pas configurées : elle apporterait 461 membres sur les 5 familles "
    "publiées, dont 305 seulement ont déjà un slug — 156 profils à collecter "
    "(641 et 326 si on la prend entière). Élargir le corpus est une décision "
    "distincte de celle de changer de source."
)


class RosterAnInactif(RuntimeError):
    """Le roster AMO30 a été demandé sans que le drapeau soit levé.

    Jamais rattrapée en une liste vide : voir `AN_ROSTER_ACTIF`.
    """


class RosterAnIndisponible(RuntimeError):
    """L'archive AMO30 est absente, illisible, ou ne porte aucun organe `GP`.

    « Archive lisible, index vide » est un cas distinct de « archive absente »,
    et c'est celui par lequel #510 est passé : il ne doit jamais être mis en
    cache ni rendu en silence.
    """


def activer_roster_an(actif: bool) -> None:
    """Active (ou non) la dérivation du roster depuis AMO30 (#526, bascule #527).

    Drapeau de module et non paramètre d'appel, pour la même raison qu'en
    #510 : l'index GP est construit **une** fois par archive, mis en cache sur
    disque et partagé entre les appelants. C'est une propriété de l'index, pas
    de l'appel.
    """
    global AN_ROSTER_ACTIF
    AN_ROSTER_ACTIF = bool(actif)


def _exiger_actif() -> None:
    if not AN_ROSTER_ACTIF:
        raise RosterAnInactif(
            "Roster AN dérivé d'AMO30 désactivé (drapeau baissé). Rendre une "
            "liste vide ici publierait « groupe sans membre » à la place de "
            "« source non activée » (AGENTS §2 règle 5) — c'est pour cela que "
            "l'appel échoue au lieu de rendre `[]`. Relever le drapeau avec "
            "`an_roster.activer_roster_an(True)`. Depuis #529 il n'existe plus "
            "de seconde source de roster : baisser ce drapeau ne bascule sur "
            "rien, il coupe. " + AIDE_ROSTER_AN
        )


# ── L'index GP, construit une fois, mémoïsé par chemin ───────────────────────
#: Nom du fichier d'index dans `.cache/acteurs_historique_an/`. Distinct des
#: quatre index que `candidate_profile.py` y écrit déjà : il n'en dérive aucun
#: et ne doit surtout pas leur être resservi.
NOM_INDEX_GP = "index_groupes_politiques.json"

#: Version du contenu de l'index. Un index d'une autre version est reconstruit
#: plutôt que lu au mieux : `.cache/acteurs_historique_an/` est partagé entre
#: les jobs par la clé de cache CI, et un index d'un format antérieur servi à
#: un run neuf est le défaut de #505 sous un autre nom.
VERSION_INDEX_GP = "an-roster-gp-v1"

#: Où l'index est écrit. Le même répertoire que les quatre index que
#: `candidate_profile.py` dérive déjà de cette archive — un seul cache CI à
#: restaurer. Relatif au répertoire courant, comme le reste du dépôt : c'est
#: ce qui permet aux tests de travailler dans un `tmp_path` sans écrire une
#: ligne dans `tests/fixtures/`.
REPERTOIRE_CACHE_PAR_DEFAUT = Path(".cache") / "acteurs_historique_an"

#: `codeType` d'un organe « groupe politique » dans le référentiel AN.
CODE_TYPE_GP = "GP"

#: `typeOrgane` d'un mandat d'appartenance à un groupe politique.
TYPE_ORGANE_GP = "GP"

#: Sigle de l'organe « Non inscrit ». Il n'est PAS une exception cosmétique :
#: c'est le seul organe `GP` qui ouvre avec la législature elle-même, et non le
#: jour où les groupes se constituent. `date_constitution_groupes()` l'exclut
#: pour cette raison, jamais pour ce qu'il représente politiquement.
SIGLE_NON_INSCRIT = "NI"

# Mémo intra-process indexé par CHEMIN de l'archive, jamais par nom logique :
# les tests règlent leur propre archive par cas et un mémo global ferait fuiter
# l'index d'un test dans le suivant — le piège qui avait fait revenir #377
# (AGENTS §5). L'objet rendu est PARTAGÉ, jamais copié : aucun appelant ne le
# mute.
_MEMO_INDEX: dict[str, dict[str, Any]] = {}
_MEMO_LOCK = threading.Lock()


def vider_memo() -> None:
    """Oublie les index déjà matérialisés. Usage test ; sans effet ailleurs."""
    with _MEMO_LOCK:
        _MEMO_INDEX.clear()


def _texte(valeur: Any) -> Optional[str]:
    """`"PA1234"` que l'AN écrive la valeur nue ou `{"#text": ...}`."""
    if isinstance(valeur, dict):
        valeur = valeur.get("#text")
    if isinstance(valeur, str) and valeur.strip():
        return valeur
    return None


def _mandats_de(acteur: dict[str, Any]) -> list[dict[str, Any]]:
    """`acteur.mandats.mandat`, toujours en liste (l'AN écrit un objet à 1)."""
    mandats = (acteur.get("mandats") or {}).get("mandat")
    if isinstance(mandats, dict):
        mandats = [mandats]
    return [m for m in (mandats or []) if isinstance(m, dict)]


def construire_index_gp(zip_path: Path) -> dict[str, Any]:
    """Parcourt l'archive AMO30 et rend `{version, organes, mandats, acteurs}`.

    - `organes` : `{organeRef: {sigle, sigle_abrege, libelle, legislature,
      debut, fin}}` pour les seuls `codeType == "GP"` ;
    - `mandats` : `{organeRef: [[acteurRef, debut, fin], …]}` pour les seuls
      `typeOrgane == "GP"` visant un organe connu ;
    - `acteurs` : `{acteurRef: "Prénom Nom"}`, pour **nommer** un écart. Un
      décompte ne se relit pas ; un nom et une date, si.

    `sigle` est `libelleAbrev` et non `libelleAbrege` : c'est lui qui distingue
    les deux organes `SOC` de la 16e (`SOC` puis `SOC-A`) et les deux `UDR` de
    la 17e (`UDR` puis `UDDPLR`). Prendre l'autre ferait de deux organes
    successifs un seul sigle, donc un roster qui a l'air complet.

    Fonction pure vis-à-vis du réseau : elle ne lit qu'un fichier local.
    """
    organes: dict[str, dict[str, Any]] = {}
    mandats: dict[str, list[list[Optional[str]]]] = {}
    acteurs: dict[str, str] = {}

    with zipfile.ZipFile(zip_path) as zf:
        noms = zf.namelist()
        for nom in noms:
            if not nom.startswith("json/organe/") or not nom.endswith(".json"):
                continue
            try:
                with zf.open(nom) as f:
                    data = json.load(f)
            except (json.JSONDecodeError, KeyError):
                continue
            organe = data.get("organe") if isinstance(data, dict) else None
            if not isinstance(organe, dict) or organe.get("codeType") != CODE_TYPE_GP:
                continue
            organe_ref = _texte(organe.get("uid"))
            if organe_ref is None:
                continue
            vie = organe.get("viMoDe") or {}
            organes[organe_ref] = {
                "sigle": organe.get("libelleAbrev"),
                "sigle_abrege": organe.get("libelleAbrege"),
                "libelle": organe.get("libelle"),
                "legislature": _texte(organe.get("legislature")),
                "debut": vie.get("dateDebut"),
                "fin": vie.get("dateFin"),
            }

        for nom in noms:
            if not nom.startswith("json/acteur/") or not nom.endswith(".json"):
                continue
            try:
                with zf.open(nom) as f:
                    data = json.load(f)
            except (json.JSONDecodeError, KeyError):
                continue
            acteur = data.get("acteur") if isinstance(data, dict) else None
            if not isinstance(acteur, dict):
                continue
            acteur_ref = _texte(acteur.get("uid"))
            if acteur_ref is None:
                continue
            for mandat in _mandats_de(acteur):
                if mandat.get("typeOrgane") != TYPE_ORGANE_GP:
                    continue
                organe_ref = (mandat.get("organes") or {}).get("organeRef")
                if organe_ref not in organes:
                    continue
                mandats.setdefault(organe_ref, []).append(
                    [acteur_ref, mandat.get("dateDebut"), mandat.get("dateFin")]
                )
                if acteur_ref not in acteurs:
                    ident = (acteur.get("etatCivil") or {}).get("ident") or {}
                    acteurs[acteur_ref] = " ".join(
                        p for p in (ident.get("prenom"), ident.get("nom")) if p
                    )

    return {
        "version": VERSION_INDEX_GP,
        # Taille de l'archive dont cet index est tiré. C'est la clé de #505
        # appliquée ici : un contenu qui dépend d'une entrée doit porter cette
        # entrée. Une archive rafraîchie par l'AN change de taille, donc
        # invalide l'index au lieu de laisser un run neuf lire la composition
        # de la semaine passée.
        "archive_taille": zip_path.stat().st_size,
        "organes": organes,
        "mandats": mandats,
        "acteurs": acteurs,
    }


def _telecharger_archive() -> Path:
    """Chemin local de l'archive AMO30, téléchargée si absente du cache.

    Délègue à `candidate_profile._ensure_acteurs_historique_zip_downloaded`,
    **seul** point de téléchargement de cette archive dans le dépôt : c'est ce
    qui garantit le critère « zéro appel réseau hors `data.assemblee-nationale.fr`
    dans le chemin roster », et c'est aussi ce qui fait qu'un run ayant déjà
    collecté des profils ne retélécharge rien du tout.

    Import tardif : `candidate_profile` tire `requests` et la moitié du
    pipeline, alors que tout le reste de ce module travaille hors ligne.
    """
    import candidate_profile  # noqa: PLC0415 — voir docstring

    zip_path = candidate_profile._ensure_acteurs_historique_zip_downloaded()
    if zip_path is None:
        raise RosterAnIndisponible(
            "Archive AMO30 indisponible : "
            f"{candidate_profile.AN_ACTEURS_HISTORIQUE_ZIP_URL}. La composition "
            "des groupes est INCONNUE, pas vide."
        )
    return Path(zip_path)


def charger_index_gp(
    zip_path: Optional[Path] = None,
    *,
    repertoire_cache: Optional[Path] = None,
) -> dict[str, Any]:
    """Index GP de l'archive AMO30 : mémo, puis cache disque, puis construction.

    Args:
        zip_path: archive à lire. `None` = celle du cache partagé, téléchargée
            au besoin.
        repertoire_cache: où écrire l'index dérivé. `None` =
            `REPERTOIRE_CACHE_PAR_DEFAUT`, **jamais** le répertoire de
            l'archive : une archive de test vit dans `tests/fixtures/`, et une
            suite qui y écrit son index salit le dépôt à chaque exécution.

    Raises:
        RosterAnIndisponible: archive absente, illisible, ou **lisible mais
            sans aucun organe `GP`**. Ce dernier cas n'est ni mis en cache ni
            rendu en silence : c'est le trou par lequel #510 est passé (un
            index vide construit sur une archive parfaitement lisible, figé
            puis servi à tous les shards de la semaine).
    """
    zip_path = Path(zip_path) if zip_path is not None else _telecharger_archive()
    cle = str(zip_path.resolve())

    with _MEMO_LOCK:
        memoise = _MEMO_INDEX.get(cle)
    if memoise is not None:
        return memoise

    racine_cache = Path(repertoire_cache) if repertoire_cache else REPERTOIRE_CACHE_PAR_DEFAUT
    index_path = racine_cache / NOM_INDEX_GP
    index: Optional[dict[str, Any]] = None
    if index_path.is_file():
        try:
            with open(index_path, encoding="utf-8") as f:
                lu = json.load(f)
            if (
                isinstance(lu, dict)
                and lu.get("version") == VERSION_INDEX_GP
                and lu.get("archive_taille") == zip_path.stat().st_size
            ):
                index = lu
        except (json.JSONDecodeError, OSError):
            index = None  # cache corrompu : on reconstruit

    if index is None:
        try:
            index = construire_index_gp(zip_path)
        except (zipfile.BadZipFile, OSError) as exc:
            raise RosterAnIndisponible(
                f"Archive AMO30 illisible ({zip_path}) : {exc}"
            ) from exc

        if not index["organes"]:
            raise RosterAnIndisponible(
                f"{zip_path} est lisible mais ne porte AUCUN organe "
                f"'{CODE_TYPE_GP}'. L'index n'est PAS mis en cache : un index "
                "vide figé sur une archive lisible est le défaut de #510."
            )
        try:
            index_path.parent.mkdir(parents=True, exist_ok=True)
            with open(index_path, "w", encoding="utf-8") as f:
                json.dump(index, f, ensure_ascii=False)
        except OSError:
            pass  # cache best-effort : un index non écrit est simplement reconstruit

    with _MEMO_LOCK:
        _MEMO_INDEX[cle] = index
    return index


# ── Dates : la constitution des groupes, lue dans le référentiel ─────────────

def date_constitution_groupes(index: dict[str, Any], legislature: str) -> Optional[str]:
    """Jour où les groupes de cette législature se constituent, ou `None`.

    C'est le plus petit `dateDebut` des organes `GP` de la législature **hors
    `NI`** : 2022-06-28 sur la 16e, 2024-07-18 sur la 17e, 2017-06-27 sur la
    15e, 2012-06-26 sur la 14e. Lue, jamais écrite en dur — une date de
    constitution codée en dur est une donnée qui vieillit sans prévenir.

    `None` si la législature n'a aucun organe `GP` hors `NI` : l'appelant ne
    filtre alors rien, plutôt que de filtrer sur une date inventée.
    """
    debuts = [
        organe["debut"]
        for organe in index["organes"].values()
        if organe.get("legislature") == str(legislature)
        and organe.get("sigle") != SIGLE_NON_INSCRIT
        and organe.get("debut")
    ]
    return min(debuts) if debuts else None


def est_mandat_de_transit(fin: Optional[str], constitution: Optional[str]) -> bool:
    """Ce mandat est-il un passage administratif, et non une appartenance ?

    Vrai quand il se **termine au plus tard** le jour où les groupes se
    constituent : aucun groupe réel ne se termine avant d'exister, et c'est
    exactement la forme des 576 mandats `NI` `2022-06-22 → 2022-06-28` de la
    16e et des 577 mandats `NI` s'achevant le 2024-07-18 sur la 17e.

    Un mandat ouvert (`fin is None`) n'est jamais un transit. Sans date de
    constitution connue, rien n'est écarté.
    """
    if fin is None or constitution is None:
        return False
    return str(fin) <= str(constitution)


# ── La table de correspondance des sigles, committée ─────────────────────────
#: Fichier de configuration portant la table. Le même que les groupes eux-mêmes
#: (`raw_data/groupes_reels.json`) : un sigle publié et sa correspondance AN
#: sont deux faces du même choix éditorial, et les séparer garantit qu'un jour
#: l'un bougera sans l'autre.
# Porté par `groupes_config` depuis #558 — réexporté ici pour les appelants
# historiques. Deux définitions du même chemin divergeraient en silence.
from groupes_config import CHEMIN_CONFIG_GROUPES  # noqa: E402

#: Clé portant la table dans ce fichier.
CLE_CORRESPONDANCE_SIGLES = "correspondance_sigles_an"


class CorrespondanceSiglesInvalide(ValueError):
    """La table sigle publié → sigle(s) AN est absente ou viole un invariant."""


def charger_correspondance_sigles(
    chemin: Optional[Path] = None,
) -> list[dict[str, Any]]:
    """Charge et valide la table `correspondance_sigles_an`.

    Chaque entrée doit porter `groupe_sigle` (le sigle **publié**),
    `legislature`, `sigles_an` (liste non vide), `organes_an` (liste des
    organes **mesurés** au moment de la relecture) et `verifie_le`.

    `organes_an` n'est pas ce qui sert à construire le roster — c'est un
    **fil-piège** : si l'union des organes portant `sigles_an` cesse de
    coïncider avec cette liste, l'AN a ouvert ou fermé un organe et la table
    doit être relue. Le roster, lui, se construit par sigle, pour qu'un organe
    successif nouvellement ouvert entre quand même dans l'union plutôt que
    d'être perdu en silence.
    """
    chemin = Path(chemin) if chemin is not None else CHEMIN_CONFIG_GROUPES
    try:
        document = json.loads(chemin.read_text(encoding="utf-8"))
    except OSError as exc:
        raise CorrespondanceSiglesInvalide(
            f"Configuration des groupes illisible ({chemin}) : {exc}"
        ) from exc
    except ValueError as exc:
        raise CorrespondanceSiglesInvalide(f"{chemin} : JSON invalide — {exc}") from exc

    bloc = document.get(CLE_CORRESPONDANCE_SIGLES)
    if not isinstance(bloc, dict):
        raise CorrespondanceSiglesInvalide(
            f"{chemin} : clé '{CLE_CORRESPONDANCE_SIGLES}' absente ou non-objet. "
            "La correspondance des sigles est un artefact committé, pas une "
            "heuristique (#526)."
        )
    entrees = bloc.get("groupes")
    if not isinstance(entrees, list) or not entrees:
        raise CorrespondanceSiglesInvalide(
            f"{chemin} : '{CLE_CORRESPONDANCE_SIGLES}.groupes' absent ou vide."
        )

    vues: set[tuple[str, str]] = set()
    valides: list[dict[str, Any]] = []
    for entree in entrees:
        if not isinstance(entree, dict):
            raise CorrespondanceSiglesInvalide(f"{chemin} : entrée non-objet.")
        sigle = entree.get("groupe_sigle")
        legislature = entree.get("legislature")
        sigles_an = entree.get("sigles_an")
        organes_an = entree.get("organes_an")
        if not isinstance(sigle, str) or not sigle:
            raise CorrespondanceSiglesInvalide(f"{chemin} : 'groupe_sigle' absent.")
        if not isinstance(legislature, str) or not legislature:
            raise CorrespondanceSiglesInvalide(f"{sigle} : 'legislature' absente.")
        if not isinstance(sigles_an, list) or not sigles_an or not all(
            isinstance(s, str) and s for s in sigles_an
        ):
            raise CorrespondanceSiglesInvalide(
                f"{sigle}-{legislature} : 'sigles_an' doit être une liste non "
                "vide de sigles AN (organe.libelleAbrev)."
            )
        if not isinstance(organes_an, list) or not organes_an or not all(
            isinstance(o, str) and o.startswith("PO") for o in organes_an
        ):
            raise CorrespondanceSiglesInvalide(
                f"{sigle}-{legislature} : 'organes_an' doit lister les organes "
                "mesurés (PO######) — c'est le fil-piège de la table."
            )
        if not entree.get("verifie_le"):
            raise CorrespondanceSiglesInvalide(
                f"{sigle}-{legislature} : 'verifie_le' absent — une "
                "correspondance non datée n'est pas relisible."
            )
        cle = (sigle, legislature)
        if cle in vues:
            raise CorrespondanceSiglesInvalide(
                f"{sigle}-{legislature} : deux entrées pour le même "
                "(groupe_sigle, législature)."
            )
        vues.add(cle)
        valides.append(entree)
    return valides


def entree_correspondance(
    groupe_sigle: str,
    legislature: str,
    chemin: Optional[Path] = None,
) -> dict[str, Any]:
    """Entrée de la table pour ce `(sigle publié, législature)`.

    Raises:
        CorrespondanceSiglesInvalide: aucune entrée. Le message **nomme** le
            couple : deviner le sigle AN est précisément ce que ce lot refuse.
    """
    for entree in charger_correspondance_sigles(chemin):
        if entree["groupe_sigle"] == groupe_sigle and entree["legislature"] == str(legislature):
            return entree
    raise CorrespondanceSiglesInvalide(
        f"Aucune correspondance de sigle AN pour ({groupe_sigle!r}, "
        f"législature {legislature!r}) dans {chemin or CHEMIN_CONFIG_GROUPES}. "
        "Ajouter l'entrée avec ses organes et son effectif mesurés (#526)."
    )


# ── Dérivation du roster ─────────────────────────────────────────────────────

def organes_du_groupe(
    index: dict[str, Any],
    legislature: str,
    sigles_an: Iterable[str],
) -> list[str]:
    """Organes `GP` de cette législature portant l'un de ces sigles AN.

    Triés par date d'ouverture : c'est l'ordre de succession (`SOC` puis
    `SOC-A`), le seul qui rende la lecture d'un log utile.
    """
    voulus = {str(s) for s in sigles_an}
    trouves = [
        (organe.get("debut") or "", ref)
        for ref, organe in index["organes"].items()
        if organe.get("legislature") == str(legislature) and organe.get("sigle") in voulus
    ]
    return [ref for _, ref in sorted(trouves)]


def _fusionner_periodes(
    periodes: list[tuple[Optional[str], Optional[str]]],
) -> tuple[Optional[str], Optional[str]]:
    """Recolle les mandats successifs d'un acteur en une période unique.

    `mandat_debut` = le plus ancien début connu ; `mandat_fin` = la fin la plus
    tardive, et **`None` l'emporte** — un mandat ouvert ne se referme pas
    parce qu'un mandat antérieur, lui, s'est terminé. C'est le cas
    `SOC`/`SOC-A`, et le cas d'un membre qui quitte puis revient.
    """
    debuts = [d for d, _ in periodes if d]
    debut = min(debuts) if debuts else None
    if any(f is None for _, f in periodes):
        return debut, None
    fins = [f for _, f in periodes if f]
    return debut, (max(fins) if fins else None)


def _index_slug_par_acteur(chemin_correspondance: Optional[Path] = None) -> dict[str, str]:
    """`acteur_ref → slug`, la table du lot 2 lue à l'envers (#525).

    Un `acteur_ref` n'est attribué qu'à un slug (`charger_correspondance` le
    vérifie), donc l'inversion est totale et sans arbitrage.
    """
    table = correspondance_acteurs_an.charger_correspondance(chemin_correspondance)
    return {
        entree["acteur_ref"]: slug
        for slug, entree in table.items()
        if entree.get("acteur_ref")
    }


def deriver_membres_organes(
    index: dict[str, Any],
    organe_refs: Iterable[str],
    legislature: str,
    slug_par_acteur: dict[str, str],
    groupe_sigle_publie: str,
) -> list[dict[str, Any]]:
    """Membres de l'**union** de ces organes, filtrés par dates, dédupliqués.

    Rend le contrat de `group_roster.fetch_full_roster` : `slug`, `nom`,
    `groupe_sigle` (le sigle **publié**), `mandat_debut`, `mandat_fin`, plus
    ce qui permet de relire l'entrée (`acteur_ref`, `sigles_an`, `organes_an`,
    `legislature`). Trié par `acteur_ref` : la sortie d'un run doit être
    comparable à celle du précédent sans passer par un tri d'appelant.
    """
    constitution = date_constitution_groupes(index, legislature)
    par_acteur: dict[str, dict[str, Any]] = {}

    for organe_ref in organe_refs:
        organe = index["organes"].get(organe_ref)
        if organe is None:
            continue
        for acteur_ref, debut, fin in index["mandats"].get(organe_ref, []):
            if est_mandat_de_transit(fin, constitution):
                continue
            entree = par_acteur.setdefault(
                acteur_ref,
                {
                    "acteur_ref": acteur_ref,
                    "slug": slug_par_acteur.get(acteur_ref),
                    "nom": index["acteurs"].get(acteur_ref),
                    "groupe_sigle": groupe_sigle_publie,
                    "legislature": str(legislature),
                    "sigles_an": [],
                    "organes_an": [],
                    "_periodes": [],
                },
            )
            if organe.get("sigle") and organe["sigle"] not in entree["sigles_an"]:
                entree["sigles_an"].append(organe["sigle"])
            if organe_ref not in entree["organes_an"]:
                entree["organes_an"].append(organe_ref)
            entree["_periodes"].append((debut, fin))

    membres: list[dict[str, Any]] = []
    for acteur_ref in sorted(par_acteur):
        entree = par_acteur[acteur_ref]
        debut, fin = _fusionner_periodes(entree.pop("_periodes"))
        entree["mandat_debut"] = debut
        entree["mandat_fin"] = fin
        # Même champ dérivé que `filter_roster_by_sigle` : un membre est actif
        # tant qu'aucune fin de mandat n'est publiée.
        entree["actif"] = not fin
        membres.append(entree)
    return membres


def deriver_roster_groupe(
    groupe_sigle: str,
    legislature: str,
    *,
    zip_path: Optional[Path] = None,
    chemin_config: Optional[Path] = None,
    chemin_correspondance: Optional[Path] = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Roster d'un groupe publié, et le **rapport** de ce qui n'a pas résolu.

    Returns:
        `(membres, rapport)`. `rapport` porte `membres_sans_slug` (nommés, avec
        leurs dates de mandat), `organes_attendus` / `organes_trouves` (le
        fil-piège de la table) et `effectif_attendu` / `effectif_mesure`.

    Le rapport n'est pas décoratif : un membre sans slug est un membre que la
    chaîne aval laisserait tomber sans un mot (`build_roster_candidats_detaille`
    ignore un membre sans slug). Le rendre ici est ce qui empêche le trou muet
    de #510 de se rouvrir ailleurs.

    Raises:
        RosterAnInactif: drapeau baissé.
        RosterAnIndisponible: archive absente/illisible/sans organe `GP`.
        CorrespondanceSiglesInvalide: pas d'entrée pour ce couple.
    """
    _exiger_actif()
    entree = entree_correspondance(groupe_sigle, legislature, chemin_config)
    index = charger_index_gp(zip_path)
    slug_par_acteur = _index_slug_par_acteur(chemin_correspondance)

    organes_trouves = organes_du_groupe(index, legislature, entree["sigles_an"])
    membres = deriver_membres_organes(
        index, organes_trouves, legislature, slug_par_acteur, groupe_sigle
    )

    sans_slug = [
        {
            "acteur_ref": m["acteur_ref"],
            "nom": m["nom"],
            "mandat_debut": m["mandat_debut"],
            "mandat_fin": m["mandat_fin"],
            "organes_an": m["organes_an"],
        }
        for m in membres
        if not m["slug"]
    ]
    rapport = {
        "groupe_sigle": groupe_sigle,
        "legislature": str(legislature),
        "sigles_an": list(entree["sigles_an"]),
        "organes_attendus": list(entree["organes_an"]),
        "organes_trouves": organes_trouves,
        "date_constitution_groupes": date_constitution_groupes(index, legislature),
        "effectif_attendu": entree.get("effectif_amo30"),
        "effectif_mesure": len(membres),
        "membres_sans_slug": sans_slug,
    }
    return membres, rapport


def fetch_full_roster_an(
    legislature: str,
    *,
    zip_path: Optional[Path] = None,
    chemin_config: Optional[Path] = None,
    chemin_correspondance: Optional[Path] = None,
) -> list[dict[str, Any]]:
    """Roster complet d'une législature, au contrat de `fetch_full_roster`.

    Tous les groupes **de la table** pour cette législature, concaténés, chacun
    portant son `groupe_sigle` **publié** : `group_roster.filter_roster_by_sigle`
    s'applique dessus sans modification. C'est ce qui fait du lot 1b une
    bascule d'une ligne et non une réécriture.

    Un acteur passé d'un groupe à l'autre dans la même législature apparaît une
    fois **par groupe**, comme un roster NosDéputés ne sait pas le faire — la
    déduplication par slug reste à la charge de l'appelant, qui la fait déjà
    (`build_roster_candidats_detaille`).
    """
    _exiger_actif()
    roster: list[dict[str, Any]] = []
    for entree in charger_correspondance_sigles(chemin_config):
        if entree["legislature"] != str(legislature):
            continue
        membres, _ = deriver_roster_groupe(
            entree["groupe_sigle"],
            legislature,
            zip_path=zip_path,
            chemin_config=chemin_config,
            chemin_correspondance=chemin_correspondance,
        )
        roster.extend(membres)
    return roster


# ── Patron #493 : l'écart est publié entrée par entrée ───────────────────────
#: Où sont les fiches de groupe publiées, celles qu'on compare.
CHEMIN_GROUPES_PIVOT = Path("pivot_data") / "groupes"


def divergence_groupe(
    membres_amo30: list[dict[str, Any]],
    membres_publies: Iterable[str],
) -> dict[str, Any]:
    """Compare deux compositions **entrée par entrée**, jamais en volume.

    « ~3 de plus » n'est pas une mesure : ce qui se relit, c'est un nom, un
    `acteur_ref` et une date de fin de mandat. Fonction pure.
    """
    publies = set(membres_publies)
    par_slug = {m["slug"]: m for m in membres_amo30 if m.get("slug")}
    return {
        "commun": sorted(set(par_slug) & publies),
        "amo30_seulement": [
            {
                "slug": slug,
                "acteur_ref": par_slug[slug]["acteur_ref"],
                "nom": par_slug[slug]["nom"],
                "mandat_debut": par_slug[slug]["mandat_debut"],
                "mandat_fin": par_slug[slug]["mandat_fin"],
            }
            for slug in sorted(set(par_slug) - publies)
        ],
        "publie_seulement": sorted(publies - set(par_slug)),
        "sans_slug": [
            {
                "acteur_ref": m["acteur_ref"],
                "nom": m["nom"],
                "mandat_debut": m["mandat_debut"],
                "mandat_fin": m["mandat_fin"],
            }
            for m in membres_amo30
            if not m.get("slug")
        ],
    }


def _membres_publies(fichier: Path) -> Optional[list[str]]:
    """`membres[].membre_id` d'une fiche publiée, ou `None` si absente.

    `None` et `[]` ne disent pas la même chose : « pas encore publiée » (les
    groupes de la 17e) contre « publiée sans membre ».
    """
    try:
        document = json.loads(fichier.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    membres = document.get("membres")
    if not isinstance(membres, list):
        return None
    return [m.get("membre_id") for m in membres if isinstance(m, dict) and m.get("membre_id")]


def rapport_divergence(
    *,
    legislature: Optional[str] = None,
    zip_path: Optional[Path] = None,
    chemin_config: Optional[Path] = None,
    chemin_correspondance: Optional[Path] = None,
    chemin_groupes_pivot: Optional[Path] = None,
) -> dict[str, Any]:
    """Le compteur de migration : l'écart AMO30 ↔ fiches publiées, par groupe.

    Le total (`ecart_total`) est ce qui doit tomber à 0 — ou n'être composé que
    d'écarts **expliqués** — pour que le drapeau et son repli puissent
    disparaître (#526 §9). Il valait **4** à la bascule (#527), quatre acteurs
    sans slug, nommés et datés : c'est la clause 2 de la condition de retrait,
    et c'est elle qui reste ouverte. Un groupe dont la fiche n'est pas encore
    publiée (la 17e) est compté à part, dans `non_publies` : il n'a pas
    d'écart, il a un périmètre.
    """
    _exiger_actif()
    racine = Path(chemin_groupes_pivot) if chemin_groupes_pivot else CHEMIN_GROUPES_PIVOT
    groupes: list[dict[str, Any]] = []
    non_publies: list[str] = []
    ecart_total = 0

    for entree in charger_correspondance_sigles(chemin_config):
        if legislature is not None and entree["legislature"] != str(legislature):
            continue
        membres, rapport = deriver_roster_groupe(
            entree["groupe_sigle"],
            entree["legislature"],
            zip_path=zip_path,
            chemin_config=chemin_config,
            chemin_correspondance=chemin_correspondance,
        )
        libelle = f"{entree['groupe_sigle']}-{entree['legislature']}"
        publies = _membres_publies(racine / entree["fichier"]) if entree.get("fichier") else None
        if publies is None:
            non_publies.append(libelle)
            groupes.append({"groupe": libelle, "rapport": rapport, "divergence": None})
            continue
        divergence = divergence_groupe(membres, publies)
        ecart_total += (
            len(divergence["amo30_seulement"])
            + len(divergence["publie_seulement"])
            + len(divergence["sans_slug"])
        )
        groupes.append({"groupe": libelle, "rapport": rapport, "divergence": divergence})

    return {"groupes": groupes, "non_publies": non_publies, "ecart_total": ecart_total}


# ── CLI ──────────────────────────────────────────────────────────────────────

def _afficher_rapport_divergence(rapport: dict[str, Any]) -> None:
    for bloc in rapport["groupes"]:
        r = bloc["rapport"]
        print(
            f"→ {bloc['groupe']} : {r['effectif_mesure']} membre(s) AMO30 "
            f"(sigles AN {', '.join(r['sigles_an'])} ; organes "
            f"{', '.join(r['organes_trouves']) or '—'})"
        )
        if r["organes_trouves"] != r["organes_attendus"]:
            print(
                f"   [!] fil-piège : organes attendus {r['organes_attendus']}, "
                f"trouvés {r['organes_trouves']} — relire la table de "
                "correspondance (#526)."
            )
        divergence = bloc["divergence"]
        if divergence is None:
            print("   · fiche non publiée — périmètre, pas écart.")
            continue
        print(f"   · communs : {len(divergence['commun'])}")
        for m in divergence["amo30_seulement"]:
            print(
                f"   + AMO30 seul : {m['slug']} ({m['acteur_ref']}, {m['nom']}) "
                f"{m['mandat_debut']} → {m['mandat_fin']}"
            )
        for slug in divergence["publie_seulement"]:
            print(f"   - publié seul : {slug}")
        for m in divergence["sans_slug"]:
            print(
                f"   ? sans slug : {m['acteur_ref']} ({m['nom']}) "
                f"{m['mandat_debut']} → {m['mandat_fin']}"
            )
    if rapport["non_publies"]:
        print(f"→ non publiés (périmètre) : {', '.join(rapport['non_publies'])}")
    print(f"→ écart total (compteur de migration) : {rapport['ecart_total']}")


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Composition des groupes de l'Assemblée nationale dérivée "
                    "d'AMO30 (#526). Source de production depuis #527.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    # #527 : l'option dit désormais l'inverse de ce qu'elle disait, et c'est
    # volontaire. Garder un `--activer-roster-an` en `store_true` sur un
    # drapeau déjà levé aurait fait **baisser** le drapeau à chaque appel qui
    # l'omet — un défaut muet, du type exact que ce module passe son temps à
    # refuser. Une option qui ne peut plus dire vrai se retire ; elle ne se
    # garde pas « au cas où ».
    parser.add_argument(
        "--desactiver-roster-an",
        action="store_true",
        help="Baisser le drapeau pour cet appel : le module refuse alors "
             "bruyamment au lieu de dériver le roster. Sert à reproduire "
             "l'état d'avant #527, jamais à obtenir une liste vide. "
             + AIDE_ROSTER_AN,
    )
    parser.add_argument("--legislature", metavar="N", help='Ex. "16", "17".')
    parser.add_argument(
        "--sigle",
        metavar="SIGLE",
        help="Sigle PUBLIÉ du groupe (ex. \"REN\"), pas le sigle AN.",
    )
    parser.add_argument(
        "--divergence",
        action="store_true",
        help="Publier l'écart entre le roster AMO30 et les fiches déjà "
             "publiées, entrée par entrée (patron #493).",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        metavar="FICHIER",
        help=f"Défaut : {CHEMIN_CONFIG_GROUPES}.",
    )
    parser.add_argument(
        "--archive",
        type=Path,
        default=None,
        metavar="FICHIER",
        help="Archive AMO30 locale. Défaut : le cache partagé "
             ".cache/acteurs_historique_an/, téléchargée au besoin.",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    if args.desactiver_roster_an:
        activer_roster_an(False)

    try:
        if args.divergence:
            _afficher_rapport_divergence(
                rapport_divergence(
                    legislature=args.legislature,
                    zip_path=args.archive,
                    chemin_config=args.config,
                )
            )
            return 0

        if not args.sigle or not args.legislature:
            parser.error("--sigle et --legislature sont requis hors --divergence.")

        membres, rapport = deriver_roster_groupe(
            args.sigle,
            args.legislature,
            zip_path=args.archive,
            chemin_config=args.config,
        )
    except (
        RosterAnInactif,
        RosterAnIndisponible,
        CorrespondanceSiglesInvalide,
        correspondance_acteurs_an.CorrespondanceInvalide,
    ) as exc:
        print(f"[!] {exc}", file=sys.stderr)
        return 1

    print(
        f"→ {rapport['effectif_mesure']} membre(s) pour {args.sigle} "
        f"(législature {args.legislature}), "
        f"{len(rapport['membres_sans_slug'])} sans slug.",
        file=sys.stderr,
    )
    print(json.dumps(membres, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
