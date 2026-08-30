#!/usr/bin/env python3
"""
generate_all_profiles.py

Récupère les données et génère le CV (JSON) de chaque candidat de
raw_data/candidats.json qui possède un "slug" (l'identifiant du profil, résolu
en acteur AN par raw_data/correspondance_acteurs_an.json, #525) et/ou un mandat
de député européen (recherché par nom via
candidate_profile_ue.py, cf. Open Data Portal du Parlement européen). Les
candidats sans aucune de ces deux sources sont simplement signalés, sans erreur.

Les fichiers générés sont écrits dans raw_data/profiles/<slug>.json (profil
brut). Le volet européen, quand il existe, est fusionné dans le même profil
sous la clé "mandat_europeen" (pour un candidat sans mandat français, ex.
Jordan Bardella, un profil minimal est tout de même créé à partir de
raw_data/candidats.json + du mandat européen).

Fusion additive (comportement par défaut) : si un fichier <slug>.json (dans
raw_data/profiles/) ou <slug>.pivot.json (dans pivot_data/profiles/) existe
déjà, les nouvelles données collectées sont fusionnées avec celles déjà
présentes plutôt que de les écraser — chaque liste (votes, mandats, dossiers
législatifs, interventions...) est fusionnée par clé d'unicité : les entrées
déjà connues sont conservées telles quelles, seules les entrées réellement
nouvelles sont ajoutées. Cela évite que des données varient ou disparaissent
d'une régénération à l'autre à cause d'un aléa transitoire des API publiques
(pagination, requête ponctuelle en échec...). Utiliser --no-merge pour
revenir à un écrasement complet. Voir merge_profile.py.

Avec --pivot, un fichier supplémentaire pivot_data/profiles/<slug>.pivot.json
est généré au format schéma pivot v1 (commun à toutes les sources). Le volet
européen, s'il existe, est normalisé et intégré au pivot.

Parallélisation (deux niveaux) :
  - Niveau 1 : pour chaque candidat, les collectes Assemblée nationale et
    Parlement européen sont lancées simultanément (deux jeux de données
    distincts, aucun état partagé).
  - Niveau 2 : plusieurs candidats sont traités en parallèle grâce à un pool
    de threads (option --workers, défaut : 4). Les caches disque partagés sont
    protégés par des verrous définis dans candidate_profile.py et
    candidate_profile_ue.py.

Usage (depuis la racine du dépôt) :
    python src/generate_all_profiles.py
    python src/generate_all_profiles.py --only jean-luc-melenchon
    python src/generate_all_profiles.py --skip-existing    # ne pas relancer un profil déjà généré
    python src/generate_all_profiles.py --skip-ue          # ne pas interroger l'API du Parlement européen
    python src/generate_all_profiles.py --pivot            # aussi écrire <slug>.pivot.json
    python src/generate_all_profiles.py --workers 4        # nb de candidats traités en parallèle (défaut: 4)
    python src/generate_all_profiles.py --resume            # reprendre depuis le dernier point de sauvegarde après une interruption
    python src/generate_all_profiles.py --limit 20          # plafonner ce run à 20 candidats (non couverts d'abord)
    python src/generate_all_profiles.py --sample 20         # ne traiter qu'un échantillon aléatoire de 20 candidats
    python src/generate_all_profiles.py --manifest-out F    # consigner les profils écrits par CE run (publication CI scopée, #450)

Extraction pilotée par roster (composition réelle des groupes parlementaires,
cf. generate_roster_candidats.py et docs/technical_decisions.md#provenance-pivot)
plutôt que par la liste éditoriale par défaut (raw_data/candidats.json) :
    python src/generate_roster_candidats.py
    python src/generate_all_profiles.py --candidats raw_data/roster_candidats.json --pivot --skip-existing \
        --skip-interventions --skip-dossiers-legislatifs

Trois populations, trois intentions NOMMÉES (#578) — jamais déduites de la
présence d'un plafond :
  --skip-existing     : les candidats sans profil (on étend la couverture) ;
  --refresh-existing  : les candidats qui en ont déjà un (on propage un
                        correctif) ;
  ni l'un ni l'autre  : tout le monde, l'existant recollecté et fusionné.
--limit ne fait que PLAFONNER cette population ; sous plafond, le budget va
d'abord aux non-couverts puis aux couverts périmés (#224, --staleness-days).

--skip-interventions + --skip-dossiers-legislatifs combinés forment le mode
d'extraction léger (#357) : identité + mandats + votes + amendements
uniquement, sans dossiers législatifs/interventions/questions officielles —
utilisé par le job extract-roster-groupes de generate-data.yml, ces champs
n'étant consommés par aucun agrégat de groupe (#349).
"""

import argparse
import json
import os
import random
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from audit_pivot_dataset import compute_profils_perimes
from budget_collecte import (
    BudgetCollecte,
    annoncer_troncature,
    creer as creer_budget,
    epuise as budget_epuise,
    ignorer as budget_ignorer,
    section as budget_section,
)
from candidate_profile import (
    WARNING_AUCUN_MANDAT_FR,
    WARNING_PREFIX_BUDGET_COLLECTE,
    RefusDrapeauInterventionsSyceron,
    build_profile,
    nb_acteurs_referentiel_charge,
)
from candidate_profile_ue import build_profile_ue
import correspondance_acteurs_an
import couverture_profil
from groupes_config import (
    CHEMIN_CONFIG_GROUPES,
    index_membres_de_groupes_suspendus,
)
from json_io import ecrire_profil_json
from profil_brut import (
    PartitionIllisible,
    charger_profil_brut,
    ecrire_profil_brut,
)
from licences import LICENCE_AN
from merge_profile import (
    merge_pivot_profile,
    merge_raw_profile,
    preserve_stable_freshness_timestamps,
    preserver_collectes_non_vides,
)
from normalize_europarl import normalize_europarl
from normalize_profil import normalize_profil
from schema_pivot import appliquer_chambres, poser_identifiant
from amendements_index import (
    DEFAULT_AMENDEMENTS_DIR,
    rafraichir as rafraichir_amendements,
)
from scrutins_index import DEFAULT_SCRUTINS_PATH, ScrutinsIndex, charger as charger_scrutins, rafraichir as rafraichir_scrutins
from scrutins_legislature import LegislatureIrresoluble
from text_utils import slugify

# Chemins par défaut, relatifs à la racine du dépôt (voir README pour l'arborescence).
DEFAULT_CANDIDATS_PATH = "raw_data/candidats.json"
DEFAULT_PROFILES_DIR = Path("raw_data/profiles")
DEFAULT_PIVOT_DIR = Path("pivot_data/profiles")
DEFAULT_CHECKPOINT_PATH = "raw_data/profiles/.generation_checkpoint.json"

# #528 : le Sénat est sorti du périmètre. Cette liste ne porte plus qu'une
# chambre, et `build_profile_any_chambre` en garde la forme — la boucle, les
# warnings d'échec par chambre, la convention d'ordre — parce que ce qui est
# retiré est une SOURCE, pas la possibilité qu'il y en ait plusieurs (le PE en
# est déjà une autre, collectée à part). Rouvrir le Sénat, c'est rajouter une
# entrée ici ET une source dans `candidate_profile.BASE_URLS` : lire d'abord
# docs/technical_decisions.md#retrait-senat-528.
CHAMBRES = ["deputes"]

# Préfixes de warnings publiés dans `meta.warnings` du profil (#488). Même
# convention que candidate_profile.WARNING_PREFIX_* : le texte avant le premier
# ':' est le *type* agrégé par audit_pivot_dataset.compute_agregation_warnings.
WARNING_PREFIX_CHAMBRE_EN_ECHEC = "collecte de chambre en échec"
WARNING_PREFIX_DEUX_CHAMBRES = "carrière sur deux chambres"

# Répertoire de cache ParlTrack — identique à parltrack_dumps.PARLTRACK_CACHE_DIR.
_PARLTRACK_CACHE_DIR = Path(".cache") / "parltrack"

# Valeurs acceptées par --source. `"senat"` a été RETIRÉE par #528 : argparse
# refuse désormais la valeur, ce qui est le comportement voulu — un run qui
# demande encore le Sénat doit échouer à la ligne de commande, pas produire un
# job vert sans profil (c'est exactement ce que faisait `extract-senat`).
SOURCE_VALUES = ("an", "ue", "all")

# Verrou global pour sérialiser les print() et éviter un affichage interleaved.
_PRINT_LOCK = threading.Lock()
# Verrou global pour sérialiser l'écriture du fichier de point de sauvegarde.
_CHECKPOINT_LOCK = threading.Lock()
# Verrou global pour sérialiser l'ajout d'une ligne au manifeste (#450).
_MANIFEST_LOCK = threading.Lock()


def _tprint(*args: Any, **kwargs: Any) -> None:
    """Equivalent thread-safe de print())."""
    with _PRINT_LOCK:
        print(*args, **kwargs)


def _annoter_github(message: str) -> None:
    """Remonte un message en annotation GitHub Actions (#514).

    Même canal que `budget_collecte.annoncer_troncature` : un échec qui ne vit
    que dans 1 200 lignes de log de step n'est pas un échec déclaré. Silencieux
    hors CI — le `_tprint` de l'appelant suffit alors."""
    if os.getenv("GITHUB_ACTIONS") == "true":
        propre = message.replace("\n", " ").replace("\r", "")
        _tprint(f"::warning::{propre}", flush=True)


def _init_manifest(manifest_path: Optional[str]) -> None:
    """Vide (ou crée) le manifeste des profils bruts écrits par CE run (#450).

    Sans troncature initiale, un second run sur le même runner publierait les
    profils du premier : le manifeste doit décrire une exécution, pas un
    répertoire.
    """
    if not manifest_path:
        return
    path = Path(manifest_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")


def _manifest_append(manifest_path: Optional[str], nom_fichier: str) -> None:
    """Consigne un profil brut réellement écrit, une ligne par nom de fichier.

    Écriture incrémentale sous verrou plutôt qu'un dump final (#450) : un job
    préempté ou interrompu laisse alors un manifeste tronqué mais VALIDE,
    décrivant exactement les profils déjà présents sur le disque. Même principe
    que #443 — ne jamais jeter un préfixe valide.

    Le manifeste ne contient que des noms de fichiers (`<slug>.json`), relatifs
    à `--out-dir` : c'est ce que consomme l'étape de publication du workflow.
    """
    if not manifest_path:
        return
    with _MANIFEST_LOCK:
        with open(manifest_path, "a", encoding="utf-8") as f:
            f.write(f"{nom_fichier}\n")


def _load_checkpoint(path: Path) -> dict[str, Any]:
    """Charge le point de sauvegarde existant, ou renvoie un état vide s'il est absent/corrompu."""
    if not path.exists():
        return {"resultats": []}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"resultats": []}


def _save_checkpoint(path: Path, resultats: list[dict[str, Any]]) -> None:
    """Écrit le point de sauvegarde de façon atomique (fichier temporaire puis remplacement),
    pour ne jamais laisser un fichier tronqué si le process est interrompu pendant l'écriture.

    Reste indenté malgré #433 : ce fichier n'est pas versionné (aide à la
    reprise, quelques centaines de lignes) et sert justement à être relu à la
    main quand une exécution s'est interrompue."""
    with _CHECKPOINT_LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(
                {"resultats": resultats, "derniere_maj": time.strftime("%Y-%m-%dT%H:%M:%S%z")},
                f, ensure_ascii=False, indent=2,
            )
        tmp_path.replace(path)


def load_candidats(path: str) -> list[dict[str, Any]]:
    """Charge la liste des candidats depuis le fichier JSON source (clé "candidats")."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("candidats", [])


def _parse_shard(valeur: str) -> tuple[int, int]:
    """Parse `--shard I/N` (ex. `0/8`). Lève `ValueError` sur toute forme
    invalide plutôt que de deviner : un shard mal interprété traiterait
    silencieusement les mauvais candidats."""
    match = re.fullmatch(r"\s*(\d+)\s*/\s*(\d+)\s*", valeur or "")
    if not match:
        raise ValueError(f"--shard attend la forme I/N (ex. 0/8), reçu : {valeur!r}")
    index, total = int(match.group(1)), int(match.group(2))
    if total < 1:
        raise ValueError(f"--shard : N doit valoir au moins 1, reçu {total}")
    if not 0 <= index < total:
        raise ValueError(f"--shard : I doit être dans [0, {total - 1}], reçu {index}")
    return index, total


def _select_shard(
    candidats: list[dict[str, Any]], index: int, total: int
) -> list[dict[str, Any]]:
    """Partitionne la liste en `total` tranches et retourne la `index`-ième
    (#394).

    Découpage par **position modulo**, pas par blocs contigus : le fichier
    roster est ordonné par groupe parlementaire, donc des blocs contigus
    donneraient des tranches très inégales en coût (un groupe de 190 membres
    contre un de 15). Le modulo répartit les groupes uniformément.

    Déterministe à liste source constante — condition nécessaire pour que
    `--skip-existing` garde son sens d'un run à l'autre : un membre doit
    toujours retomber dans le même shard, sinon un shard sauterait des
    profils déjà collectés par un autre.

    Appliqué AVANT `--limit`/`--sample`/`--skip-existing` : l'appartenance à
    un shard ne doit pas dépendre de l'état de couverture, qui évolue.
    """
    return [c for i, c in enumerate(candidats) if i % total == index]


def _select_candidats(
    candidats: list[dict[str, Any]], limit: Optional[int] = None, sample: Optional[int] = None
) -> list[dict[str, Any]]:
    """Réduit la liste de candidats pour un déploiement progressif contrôlé
    (--limit/--sample), utile pour tester à petite échelle avant d'ouvrir
    l'extraction à la liste complète (ex. les ~750 membres d'un roster).

    --limit : les N premiers candidats (ordre du fichier source, déterministe).
    --sample : N candidats tirés aléatoirement sans remise (ordre non garanti).
    Mutuellement exclusifs (appliqué par le groupe argparse dans main()).
    """
    if limit is not None:
        return candidats[:limit]
    if sample is not None:
        return random.sample(candidats, min(sample, len(candidats)))
    return candidats


# Alias local : voir text_utils.slugify (mutualisé avec parti_profile._slugify).
_slugify = slugify


def _effective_slug(candidat: dict[str, Any]) -> str:
    """Slug effectif d'un candidat : `slug` s'il est renseigné, sinon dérivé du nom."""
    return candidat.get("slug") or _slugify(candidat.get("nom") or "")


def _charger_pivot_existant(pivot_dir: Path, slug: str) -> Optional[dict[str, Any]]:
    """Charge le pivot existant d'un candidat (`pivot_dir/<slug>.pivot.json`), ou
    None si absent/illisible."""
    pivot_path = pivot_dir / f"{slug}.pivot.json"
    if not pivot_path.exists():
        return None
    try:
        with open(pivot_path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _select_existants(candidats: list[dict[str, Any]], out_dir: Path) -> list[dict[str, Any]]:
    """Ne retient que les candidats dont le profil brut existe déjà (#445).

    Sélection strictement inverse de la frontière de conquête de
    `_select_candidats_couverture` : une correction de fond (ex. la clé uid de
    #440) ne concerne que les profils DÉJÀ écrits.

    Les atteindre par `--limit` est impossible : l'ordre de
    `raw_data/roster_candidats.json` n'est pas stable dans le temps — le
    fichier est régénéré — donc les profils couverts y sont dispersés, pas
    groupés en tête (mesuré : dernier couvert à l'index 93 sur 94 dans un
    shard de 8, pour 24 couverts).
    """
    return [c for c in candidats if (out_dir / f"{_effective_slug(c)}.json").exists()]


def _select_candidats_couverture(
    candidats: list[dict[str, Any]],
    pivot_dir: Path,
    limit: int,
    staleness_days: int,
    inclure_existants: bool = True,
    reference_date: Optional[datetime] = None,
) -> list[dict[str, Any]]:
    """Répartition d'un PLAFOND de volume entre non-couverts et couverts (#224).

    Appelée dès que `--limit` est posé, et **seulement** pour lui : depuis
    #578 elle ne commande plus aucune politique de rafraîchissement. Qui est
    dans la population est décidé en amont, par une intention nommée
    (`--refresh-existing`, `--skip-existing`, ou ni l'un ni l'autre) ; cette
    fonction ne fait que dépenser le budget.

    Sans elle, --limit sélectionne toujours les N premiers candidats du
    fichier source (ordre déterministe) : dès le run 2, le budget repart sur
    les mêmes, et personne d'autre n'est jamais atteint.

    Partitionne `candidats` en "non couverts" (pas de pivot dans `pivot_dir`)
    et "couverts" (pivot existant), avant toute troncature par `limit` : le
    budget va d'abord aux non-couverts (frontière de conquête, ordre du
    fichier source), puis, s'il en reste, aux couverts périmés — fraîcheur au
    sens de `audit_pivot_dataset.compute_profils_perimes`, même seuil
    `staleness_days`. Un profil couvert et frais n'est jamais resélectionné :
    pas de gaspillage de budget sur des profils déjà à jour.

    `inclure_existants=False` (le job roster quand l'axe 1 vaut `leave-as-is`,
    c'est-à-dire `--skip-existing`) : le budget ne va QU'aux non-couverts. Y
    faire entrer des couverts périmés reviendrait à les sélectionner pour que
    `process_candidat` les saute — du budget dépensé à ne rien faire.

    L'ordre des couverts périmés au sein du budget restant suit celui renvoyé
    par `compute_profils_perimes` (tri alphabétique par `id`), pas un tri par
    degré de péremption — choix volontairement simple, cf. #224.

    NB : la péremption est une règle de PRIORITÉ sous plafond, jamais une
    politique de rafraîchissement. Un correctif de code ne rend aucun profil
    périmé au sens des dates : c'est pourquoi « rafraîchir » se demande
    désormais en retirant le plafond, pas en espérant que la date le veuille
    (#578).
    """
    non_couverts: list[dict[str, Any]] = []
    couverts: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for candidat in candidats:
        pivot = _charger_pivot_existant(pivot_dir, _effective_slug(candidat))
        if pivot is None:
            non_couverts.append(candidat)
        else:
            couverts.append((candidat, pivot))

    selection = non_couverts[:limit]
    restant = limit - len(selection)

    if inclure_existants and restant > 0 and couverts:
        pivots_par_id = {
            pivot["id"]: candidat for candidat, pivot in couverts if pivot.get("id")
        }
        perimes_ids = compute_profils_perimes(
            [pivot for _, pivot in couverts if pivot.get("id")],
            staleness_days=staleness_days,
            reference_date=reference_date,
        )
        for pid in perimes_ids[:restant]:
            selection.append(pivots_par_id[pid])

    return selection


def valider_budgets(args: argparse.Namespace) -> None:
    """Refuse un budget mort, signale une collecte sans budget déclaré (#514).

    La classe de défaut à casser : un chemin de collecte qui se retrouve sans
    plafond, ou avec un plafond que rien ne borne, SANS que ça se voie. Elle
    s'attrape en deux temps — ici pour ce qui est lisible sur la ligne de
    commande, et dans `tests/test_ci_budget_par_job.py` pour l'inventaire des
    invocations du workflow, seul endroit d'où l'on voit qu'un job n'a rien
    déclaré du tout.

    Les deux moitiés du défaut d'origine ont chacune leur garde :

    - **un budget posé mais mort** — `--budget-interventions-secondes` sous
      `--skip-interventions` — est refusé net. C'est la combinaison que
      `build_profile_any_chambre` neutralisait en silence ;
    - **aucun budget du tout** est signalé, pas refusé. Rendre l'option
      obligatoire casserait les commandes locales documentées dans `README.md`,
      et un garde-fou qu'on désactive pour pouvoir travailler ne garde rien
      (leçon de #460). Le garde dur vit côté CI, là où l'oubli coûte des
      quarts d'heure de runner.
    """
    if args.budget_interventions_secondes and args.skip_interventions:
        raise SystemExit(
            "[!] --budget-interventions-secondes avec --skip-interventions : ce budget "
            "ne bornerait rien (aucune intervention n'est collectée), et il donnerait "
            "l'apparence d'une protection. C'est la moitié visible de #514 ; l'autre "
            "moitié était qu'il ne restait alors AUCUN budget sur la collecte. "
            "Utiliser --budget-collecte-secondes, qui borne identité, votes et dossiers."
        )
    if not args.pivot_only and getattr(args, "budget_collecte_secondes", None) is None:
        message = (
            "collecte réseau lancée sans --budget-collecte-secondes : aucun plafond de "
            "temps par candidat, et aucune décision écrite qu'il n'en faut pas. "
            "Passer --budget-collecte-secondes 0 pour déclarer l'absence de budget (#514)."
        )
        print(f"[!] {message}")
        _annoter_github(message)


def build_profile_any_chambre(
    slug: str,
    chambres: Optional[list[str]] = None,
    skip_interventions: bool = False,
    skip_dossiers_legislatifs: bool = False,
    collecte_bicamerale: bool = False,
    budget_interventions_secondes: int = 0,
    budget_collecte_secondes: int = 0,
    budget_job: Optional[BudgetCollecte] = None,
) -> tuple[Optional[dict], Optional[str], list[str]]:
    """Collecte le profil FR et renvoie `(profil_retenu, chambre_retenue, warnings)`.

    Avant #488, cette fonction s'arrêtait à la première chambre qui rendait une
    identité, et un `except Exception: continue` avalait les échecs sans laisser
    de trace ailleurs qu'en log. Deux conséquences mesurées dans le corpus :

    - un parlementaire présent des deux côtés était classé par **l'ordre de la
      boucle** — cas Retailleau, sénateur en exercice publié `chambre: "AN"` ;
    - une **défaillance transitoire** de la première chambre faisait basculer
      la chambre publiée sur la seconde, sans warning (cas Mélenchon, #484).

    **#528 — `CHAMBRES` ne contient plus qu'une chambre.** Le Sénat est sorti du
    périmètre : `chambres` vaut `["deputes"]` en régime normal, la boucle ne fait
    donc qu'un tour et `collecte_bicamerale` n'a plus d'effet observable. Rien
    n'a été retiré ici pour autant, et c'est délibéré — ce qui a disparu est une
    SOURCE, pas la possibilité d'en interroger plusieurs. Les deux warnings
    publiés (`collecte de chambre en échec`, `carrière sur deux chambres`)
    restent produits par le même code ; le second ne peut simplement plus se
    déclencher tant qu'il n'y a qu'une chambre. Condition de réouverture :
    `docs/technical_decisions.md#retrait-senat-528`.

    Deux régimes, séparés par `collecte_bicamerale`, conservés pour cette raison :

    **`collecte_bicamerale=True` — profils de candidats** (`meta.provenance ==
    "candidat_declare"`, 8 slugs résolvables sur les 13 de
    `raw_data/candidats.json`). Toutes les chambres de `chambres` sont
    interrogées, et non plus seulement la première qui répond. C'était le seul
    endroit où un passé sénatorial avait un usage : **biographique**, sur un CV
    (« a été sénateur de 2004 à 2010 »). Cet usage est ce que #528 a tranché
    éditorialement, et les deux profils concernés (#486, #495) gardent leurs
    mandats sénatoriaux DÉJÀ COLLECTÉS — la fusion additive ne retire rien.

    **`collecte_bicamerale=False` — membres de roster** (`roster_groupe`, 201
    des 209 profils). Comportement historique : on s'arrête à la première
    chambre qui répond. Aucun groupe sénatorial n'était agrégé — aucun jeu de
    données Sénat structuré n'est exploitable, et les deux `groupe-Senat-*.json`
    publiés portent `cohesion_votes: 0`.

    Ce que fait cette version, dans les deux régimes :

    1. **quand une chambre échoue**, elle nomme la chambre et la raison dans un
       warning publié (AGENTS.md §2.5) — y compris pour un profil de roster :
       le warning ne se déclenche que sur une exception réelle, jamais en
       régime nominal, et c'est exactement l'échec que #484 a vu disparaître
       dans un log de run ;
    2. **quand les deux chambres répondent** (bicaméral seulement), elle retient
       la première de `chambres` — une *convention d'ordre*, explicitement
       nommée dans un warning publié, pas une détermination. Choisir « la
       chambre du mandat en cours » reviendrait à dériver `chambre` des
       mandats : c'est la sous-issue D de #486, et l'appliquer ici effacerait
       la carrière AN de Retailleau comme on efface aujourd'hui son mandat
       sénatorial — un fait faux remplacé par un autre (#486) ;
    3. elle ne fusionne PAS les deux profils bruts : porter la chambre sur
       chaque mandat est la sous-issue C de #486. Aucun mandat n'est donc ajouté
       à aucun profil par cette fonction, et les dénominateurs de cohésion de
       `group_profile` sont hors d'atteinte.

    Les warnings renvoyés sont aussi ajoutés à `meta.warnings` du profil retenu
    (donc propagés au pivot par `normalize_profil`), et rendus à l'appelant
    pour le cas où aucune chambre ne répond — le profil minimal doit alors
    porter la trace de l'échec (#484).
    """
    if chambres is None:
        chambres = CHAMBRES

    # #498 : UN budget pour le candidat, partagé par les deux chambres. Un budget
    # par appel de `build_profile` doublerait le plafond d'un profil bicaméral
    # (`candidat_declare`, 8 profils sur 209) sans que le `timeout-minutes` du
    # shard, lui, double. Le plafond doit porter sur ce que borne le job : un
    # shard = un candidat.
    #
    # #514 : DEUX budgets emboîtés, et non plus un. Celui de la collecte entière
    # (identité, votes, dossiers, interventions) est chaîné sous celui du job ;
    # celui des interventions, quand il existe, est chaîné sous lui. La
    # condition de mode porte sur la VALEUR (`0 if skip_interventions else ...`)
    # et non sur la fabrique : c'est un `and not skip_interventions` posé ici
    # qui a désactivé le seul budget d'`extract-senat` (voir `budget_collecte.creer`).
    # Le `or budget_job` n'est pas une commodité : sans lui, un job qui pose un
    # budget de run mais pas de budget par candidat ne verrait AUCUNE section
    # s'ouvrir (`creer` rend None sur 0), donc son compteur ne bougerait jamais
    # et son plafond ne serait jamais atteint. Un maillon absent casserait la
    # chaîne en silence — la forme exacte du défaut que cette issue corrige.
    budget_collecte_candidat = creer_budget(
        budget_collecte_secondes, "collecte", parent=budget_job
    ) or budget_job
    budget = creer_budget(
        0 if skip_interventions else budget_interventions_secondes,
        "collecte d'interventions",
        parent=budget_collecte_candidat,
    )

    resultats: list[tuple[str, dict]] = []
    echecs: list[tuple[str, str]] = []
    # Le cumul `identite_sans_reponse` de #514 et le `journal` qui l'alimentait
    # sont partis avec les compteurs de `candidate_profile` (#529) : ils
    # comptaient les requêtes d'identité restées sans réponse chez NosDéputés,
    # une source qui n'est plus interrogée. L'identité se résout désormais dans
    # l'archive AMO30 déjà en cache ; quand cette archive manque, la résolution
    # LÈVE, et l'exception est consignée dans `echecs` puis publiée en
    # `WARNING_PREFIX_CHAMBRE_EN_ECHEC` — la distinction que #514 réclamait
    # (« la source a tranché » vs « la source n'a rien dit ») est portée par
    # l'exception elle-même, pas par un compteur.

    for rang, chambre in enumerate(chambres):
        if budget_epuise(budget_collecte_candidat):
            budget_ignorer(budget_collecte_candidat, "chambre(s) non interrogée(s)",
                           len(chambres) - rang)
            break
        try:
            profile = build_profile(
                chambre,
                slug,
                skip_interventions=skip_interventions,
                skip_dossiers_legislatifs=skip_dossiers_legislatifs,
                budget_interventions=budget,
                budget_collecte=budget_collecte_candidat,
            )
        except Exception as exc:
            _tprint(f"  [!] Échec ({chambre}) pour {slug} : {exc}")
            echecs.append((chambre, f"{type(exc).__name__}: {exc}"))
            continue
        if profile.get("identite"):
            resultats.append((chambre, profile))
            if not collecte_bicamerale:
                break

    warnings: list[str] = []

    # #514 : la troncature du budget par candidat est annoncée ICI et une seule
    # fois — le budget est partagé entre les chambres, l'annoncer dans
    # `build_profile` le répéterait à chacune.
    message_budget = annoncer_troncature(budget_collecte_candidat, slug)
    if message_budget:
        warnings.append(f"{WARNING_PREFIX_BUDGET_COLLECTE} : {message_budget}")

    if not resultats:
        # Aucune chambre ne rend d'identité : le candidat est introuvable côté
        # FR (cas déjà géré par l'appelant). L'échec reste consigné — c'est
        # celui-là que #484 a vu disparaître dans un log de run.
        for chambre, raison in echecs:
            warnings.append(
                f"{WARNING_PREFIX_CHAMBRE_EN_ECHEC} : la collecte '{chambre}' a échoué "
                f"({raison}) et aucune autre chambre n'a rendu d'identité — la chambre "
                f"de ce profil n'a pas été résolue par cette collecte (#488)."
            )
        return None, None, warnings

    chambre_retenue, profil_retenu = resultats[0]

    for chambre, raison in echecs:
        warnings.append(
            f"{WARNING_PREFIX_CHAMBRE_EN_ECHEC} : la collecte '{chambre}' a échoué "
            f"({raison}) alors que '{chambre_retenue}' a répondu — la chambre publiée est "
            f"celle qui a répondu, pas le résultat d'une comparaison des deux (#488)."
        )

    if len(resultats) > 1:
        autres = ", ".join(
            f"'{chambre}' ({profil.get('source')})" for chambre, profil in resultats[1:]
        )
        warnings.append(
            f"{WARNING_PREFIX_DEUX_CHAMBRES} : une identité a aussi été trouvée sur "
            f"{autres}. La chambre publiée est '{chambre_retenue}', par convention d'ordre "
            f"de collecte et non par comparaison des mandats ; les mandats de l'autre "
            f"chambre ne sont pas publiés tant que #486 (sous-issues C/D) n'a pas porté la "
            f"chambre sur chaque mandat."
        )

    if warnings:
        profil_retenu.setdefault("meta", {}).setdefault("warnings", []).extend(warnings)

    return profil_retenu, chambre_retenue, warnings


def _entree_correspondance(slug: str) -> Optional[dict[str, Any]]:
    """Entrée committée du slug dans la table de correspondance (#525), ou None.

    Ne lève jamais : une table absente ou invalide se signale déjà dans
    `candidate_profile._correspondance_committee`, et un profil sans entrée
    reste publiable — c'est le quality gate, sur le corpus **publié**, qui
    transforme un slug non couvert en échec dur.
    """
    try:
        return correspondance_acteurs_an.charger_correspondance().get(slug)
    except correspondance_acteurs_an.CorrespondanceInvalide:
        return None


#: Index `membre_id` → entrée de config d'un groupe suspendu, construit une
#: seule fois par process. `None` = pas encore construit ; `{}` = construit et
#: vide (aucun groupe suspendu, ou aucune fiche lisible), ce qui est un résultat
#: et non un échec à retenter.
_MEMBRES_GROUPES_SUSPENDUS: Optional[dict[str, dict[str, Any]]] = None
_VERROU_GROUPES_SUSPENDUS = threading.Lock()


def _groupe_suspendu_du_slug(slug: str) -> Optional[couverture_profil.GroupeSuspendu]:
    """Le gel d'extraction qui explique les listes vides de ce profil (#558).

    Rend `None` pour l'écrasante majorité des profils — c'est le cas normal. Ne
    lève jamais : une config absente ou illisible n'est pas une raison de faire
    échouer une génération de profil, et son absence est déjà signalée ailleurs
    (`generate_roster_candidats`, `check_quality_gate._report_groupes`).
    """
    global _MEMBRES_GROUPES_SUSPENDUS
    if _MEMBRES_GROUPES_SUSPENDUS is None:
        with _VERROU_GROUPES_SUSPENDUS:
            if _MEMBRES_GROUPES_SUSPENDUS is None:
                try:
                    config = json.loads(
                        CHEMIN_CONFIG_GROUPES.read_text(encoding="utf-8")
                    )
                    groupes = config.get("groupes") if isinstance(config, dict) else config
                    _MEMBRES_GROUPES_SUSPENDUS = index_membres_de_groupes_suspendus(
                        groupes if isinstance(groupes, list) else []
                    )
                except (OSError, json.JSONDecodeError, ValueError, AttributeError):
                    _MEMBRES_GROUPES_SUSPENDUS = {}
    groupe = _MEMBRES_GROUPES_SUSPENDUS.get(slug)
    if groupe is None:
        return None
    return couverture_profil.groupe_suspendu_depuis_config(groupe)


def _normaliser_en_pivot(
    profile: dict[str, Any],
    mandat_ue: Optional[dict[str, Any]],
    *,
    effective_slug: str,
    parti: Optional[str],
    provenance: str,
    chambre: Optional[str],
    scrutins_index: Optional[ScrutinsIndex],
    decisions: Optional[tuple[str, ...]] = None,
) -> Optional[dict[str, Any]]:
    """Normalise le brut FR et/ou le mandat européen en un seul pivot.

    Extraite des deux chemins de `process_candidat` (`--pivot-only` et mode
    normal), qui en portaient deux copies : #539 leur ajoute trois traitements
    identiques — l'`acteur_ref` publié, le slug transmis au normaliseur
    européen, la couverture dérivée — et trois copies auraient divergé.

    Le `slug=` passé à `normalize_europarl` est la correction durable du seul
    `id` préfixé restant : sans lui, un profil sans identité française
    (`jordan-bardella`) repartait à chaque run avec `europarl:131580` pour
    identité, et une réécriture du corpus n'aurait tenu qu'un run (#487, #539).
    """
    entree = _entree_correspondance(effective_slug)
    acteur_ref = entree.get("acteur_ref") if entree else None

    # Le brut est normalisé quand une chambre FR a répondu — ou, depuis #539,
    # quand il est le SEUL matériau disponible et que l'absence d'acteur AN est
    # **déclarée** dans la table. Sans cette seconde branche, un candidat
    # vérifié comme n'ayant jamais siégé (Arthaud, Tondelier, Lisnard) aurait un
    # profil brut et aucun pivot : un « collecté mais non publié » (#511) créé
    # par le lot censé le retirer.
    declaree_hors_an = bool(entree) and entree.get("ecart") == "hors_an"
    pivoter_le_brut = bool(chambre) or (mandat_ue is None and declaree_hors_an)
    pivot_profile = (
        normalize_profil(
            profile,
            parti=parti,
            provenance=provenance,
            scrutins_index=scrutins_index,
            acteur_ref=acteur_ref,
        )
        if pivoter_le_brut
        else None
    )
    if mandat_ue is not None:
        ue_pivot = normalize_europarl(
            mandat_ue, parti=parti, provenance=provenance, slug=effective_slug
        )
        if pivot_profile is None:
            pivot_profile = ue_pivot
        else:
            pivot_profile["sources"].extend(ue_pivot.get("sources") or [])
            pivot_profile["mandats"].extend(ue_pivot.get("mandats") or [])
            # `identifiants` se complète, il ne se remplace pas : le bloc du
            # normaliseur FR porte l'`an` et le `hatvp`, celui du normaliseur
            # européen l'`europarl`. `poser_identifiant` n'écrase jamais par
            # `null`, donc l'ordre des deux ne change rien.
            for cle, valeur in (ue_pivot.get("identifiants") or {}).items():
                poser_identifiant(pivot_profile, cle, valeur)
            # #493 : `mandats[]` vient de changer, donc `chambres` aussi.
            # Sans ce recalcul, un profil AN + PE publierait `["AN"]` et
            # effacerait le mandat européen — le défaut même que #486
            # reproche au scalaire, reconduit dans le champ censé le corriger.
            appliquer_chambres(pivot_profile)

    if pivot_profile is None:
        return None

    # #539 — la couverture est dérivée en DERNIER, une fois les listes et la
    # provenance arrêtées, et elle n'est jamais fusionnée : elle décrit le run,
    # pas la personne (voir merge_profile.merge_pivot_profile).
    couverture_profil.appliquer(
        pivot_profile,
        decisions=decisions,
        fait_hors_an=couverture_profil.etablir_fait_hors_an(
            entree,
            couverture_profil.SanteReferentiel(nb_acteurs_referentiel_charge()),
        ),
        # #558 — le gel du groupe se lit sur l'APPARTENANCE, pas sur la
        # provenance ni sur `chambre` : voir
        # `groupes_config.index_membres_de_groupes_suspendus`.
        groupe_suspendu=_groupe_suspendu_du_slug(effective_slug),
    )
    return pivot_profile


def build_minimal_profile(nom: str, effective_slug: str, candidat: dict[str, Any]) -> dict[str, Any]:
    """Construit un profil minimal (structure identique à build_profile(), mais sans
    aucun appel réseau) pour un candidat sans mandat français connu — ex. Jordan
    Bardella, référencé uniquement via son mandat européen."""
    return {
        "slug": effective_slug,
        "chambre": None,
        "source": candidat.get("source"),
        "identite": {
            "nom_complet": nom,
            "groupe_sigle": None,
            "groupe_nom": candidat.get("parti"),
            "profession": None,
            "date_naissance": None,
            "num_circo": None,
            "nb_mandats": None,
            "url_an_ou_senat": None,
        },
        "mandats": [],
        "votes": [],
        "votes_source": None,
        "dossiers_legislatifs": [],
        "interventions": [],
        "meta": {
            "genere_le": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            # Licence Ouverte depuis #530 : ce repli décrit un candidat sans
            # mandat français connu — il ne porte aucune donnée, et surtout
            # aucune donnée de Regards Citoyens.
            "licence_donnees": LICENCE_AN,
            "warnings": [
            f"{WARNING_AUCUN_MANDAT_FR} (slug absent du référentiel Assemblée "
            "nationale, ou identité introuvable)"
        ],
        },
    }



def _parltrack_cache_available() -> bool:
    """Renvoie True si le cache ParlTrack (.zst dumps) semble disponible."""
    if not _PARLTRACK_CACHE_DIR.is_dir():
        return False
    return any(_PARLTRACK_CACHE_DIR.glob("*.zst"))


def _enrich_pivot_with_parltrack_safe(
    pivot_profile: dict[str, Any],
    mep_id: int,
) -> str:
    """Appelle enrich_pivot_with_parltrack et renvoie un statut lisible.

    N'interrompt jamais : toute exception est capturée et reportée en warning.

    Returns:
        "enrichi"  — des données ParlTrack ont été ajoutées.
        "vide"     — dump disponible, mais aucune donnée pour ce MEP ID.
        "absent"   — dump non disponible (cache manquant ou erreur réseau).
        "erreur"   — exception inattendue.
    """
    try:
        from normalize_parltrack_dumps import enrich_pivot_with_parltrack  # noqa: PLC0415
    except ImportError as exc:
        _tprint(f"  [!] normalize_parltrack_dumps indisponible : {exc}")
        return "absent"

    if not _parltrack_cache_available():
        meta = pivot_profile.setdefault("meta", {})
        meta.setdefault("warnings", []).append(
            "ParlTrack (fallback) : dumps absents ce run — "
            "données ParlTrack issues du cache/dépôt précédent."
        )
        return "absent"

    try:
        nb_tp_avant = len(pivot_profile.get("textes_portes") or [])
        nb_amd_avant = len(pivot_profile.get("amendements") or [])
        enrich_pivot_with_parltrack(pivot_profile, mep_id=mep_id)
        nb_tp_apres = len(pivot_profile.get("textes_portes") or [])
        nb_amd_apres = len(pivot_profile.get("amendements") or [])
        if nb_tp_apres > nb_tp_avant or nb_amd_apres > nb_amd_avant:
            return "enrichi"
        return "vide"
    except Exception as exc:
        pivot_profile.setdefault("meta", {}).setdefault("warnings", []).append(
            f"ParlTrack enrichissement échoué : {exc}"
        )
        _tprint(f"  [!] Erreur ParlTrack pour MEP {mep_id} : {exc}")
        return "erreur"


def process_candidat(
    candidat: dict[str, Any],
    args: argparse.Namespace,
    out_dir: Path,
    pivot_dir: Path,
    scrutins_index: Optional[ScrutinsIndex] = None,
    budget_job: Optional[BudgetCollecte] = None,
) -> dict[str, Any]:
    """Traite un candidat : collecte les données FR et UE en parallèle (niveau 1),
    écrit les fichiers JSON/HTML (et pivot si demandé), et renvoie un dict de résultat.

    Conçu pour être appelé depuis un ThreadPoolExecutor (niveau 2) : ne modifie
    aucun état partagé en dehors des fichiers de sortie individuels (thread-safe).

    Modes :
    - Normal (défaut) : fetch réseau FR et/ou UE selon --source, écriture raw, pivot optionnel.
    - --pivot-only    : charge le profil brut existant, normalise en pivot (pas de réseau).

    `--skip-existing` est STRICT depuis #578 : un profil déjà écrit n'est
    jamais recollecté, sans exemption. L'exemption d'avant (`refresh_slugs`,
    #224) était posée par la seule présence de `--limit` — un plafond de
    volume qui commandait, sans le nommer, une politique de rafraîchissement.
    Recollecter l'existant se demande maintenant en ne posant PAS
    `--skip-existing`.

    `budget_job` (#514) : budget de temps mur pour la collecte réseau du
    process entier. Épuisé, les candidats restants sortent en
    `budget_job_epuise` **sans aucune requête**, et le job se termine
    normalement — résumé, annotations et publication compris — au lieu d'être
    tué par `timeout-minutes`. Ce n'est pas une deuxième expression du budget
    par candidat : 8 candidats × 160 s dépassent le timeout d'`extract-senat`,
    donc borner le candidat ne borne pas le job.
    """
    slug = candidat.get("slug")
    nom = candidat.get("nom")
    effective_slug = slug or _slugify(nom)
    json_path = out_dir / f"{effective_slug}.json"

    source = getattr(args, "source", "all")

    # provenance (#189) : "roster_groupe" pour les entrées produites par
    # generate_roster_candidats.py (#188, statut="roster_groupe"), "candidat_declare"
    # sinon (raw_data/candidats.json, comportement historique par défaut).
    # Calculée ici, et plus seulement au moment de la normalisation pivot : depuis
    # #488 elle décide aussi si la collecte est bicamérale (voir
    # build_profile_any_chambre).
    provenance = "roster_groupe" if candidat.get("statut") == "roster_groupe" else "candidat_declare"

    # ── Mode --pivot-only : pas de réseau, juste normalisation ──────────────
    if getattr(args, "pivot_only", False):
        if not json_path.exists():
            _tprint(f"— {nom} ({effective_slug}) : profil brut absent, ignoré en mode --pivot-only.")
            return {"nom": nom, "slug": effective_slug, "statut": "absent_raw", "parltrack": "n/a"}

        try:
            # `charger_profil_brut` (#580) : accepte le profil monolithique
            # comme le socle + ses tranches de législature, et rend dans les
            # deux cas le profil COMPLET. La normalisation pivot en aval lit
            # `amendements` sans savoir comment le fichier est découpé.
            profile = charger_profil_brut(json_path)
        except (json.JSONDecodeError, OSError, PartitionIllisible) as exc:
            _tprint(f"  [!] Lecture impossible de {json_path} : {exc}")
            return {"nom": nom, "slug": effective_slug, "statut": "erreur", "parltrack": "n/a"}

        chambre = profile.get("chambre")
        mandat_ue = profile.get("mandat_europeen")
        parti = candidat.get("parti")

        # `decisions=None` : en `--pivot-only`, le run ne collecte rien et ses
        # drapeaux ne décrivent donc rien. La décision se lit dans le brut
        # (`meta.collecte_ecartee`, #539) et, à défaut, dans la provenance —
        # le job roster porte les deux `--skip-*` en dur (#357).
        pivot_profile = _normaliser_en_pivot(
            profile, mandat_ue,
            effective_slug=effective_slug, parti=parti, provenance=provenance,
            chambre=chambre, scrutins_index=scrutins_index, decisions=None,
        )

        if pivot_profile is None:
            _tprint(f"— {nom} ({effective_slug}) : aucune source normalisable en --pivot-only.")
            return {"nom": nom, "slug": effective_slug, "statut": "non_normalisable", "parltrack": "n/a"}

        parltrack_statut = "n/a"
        if getattr(args, "enrich_parltrack", False) and mandat_ue:
            mep_id = mandat_ue.get("identifiant_pe")
            if mep_id is not None:
                parltrack_statut = _enrich_pivot_with_parltrack_safe(pivot_profile, int(mep_id))
                _tprint(f"  ParlTrack MEP {mep_id} : {parltrack_statut}")

        pivot_path = pivot_dir / f"{effective_slug}.pivot.json"
        existing_pivot = None
        if pivot_path.exists():
            try:
                with open(pivot_path, encoding="utf-8") as f:
                    existing_pivot = json.load(f)
            except (json.JSONDecodeError, OSError) as exc:
                _tprint(f"  [!] Lecture du pivot existant impossible ({pivot_path}) : {exc}")
        if not args.no_merge and existing_pivot is not None:
            pivot_profile = merge_pivot_profile(existing_pivot, pivot_profile)
        # #343 : ne pas ré-avancer genere_le/synchro_le quand --pivot-only re-dérive
        # un contenu strictement identique au pivot déjà commité (pas d'appel réseau).
        pivot_profile = preserve_stable_freshness_timestamps(existing_pivot, pivot_profile)
        ecrire_profil_json(pivot_path, pivot_profile)
        _tprint(f"  ✓ pivot-only → {pivot_path}")
        return {
            "nom": nom, "slug": effective_slug, "statut": "ok_pivot_only", "parltrack": parltrack_statut,
        }

    # ── Mode normal : skip-existing ─────────────────────────────────────────
    if args.skip_existing and json_path.exists():
        _tprint(f"— {nom} ({effective_slug}) : profil déjà présent, ignoré (--skip-existing).")
        return {"nom": nom, "slug": effective_slug, "statut": "deja_present", "parltrack": "n/a"}

    # ── Mode normal : budget de collecte du job (#514) ──────────────────────
    # Vérifié AVANT le `===` de démarrage : un candidat qui ne sera pas
    # collecté ne doit pas laisser croire qu'il l'a été. Le statut le nomme, et
    # le résumé de fin de run le compte — c'est la différence avec un
    # `timeout-minutes` atteint, où les candidats restants ne sont mentionnés
    # nulle part.
    if budget_epuise(budget_job):
        budget_ignorer(budget_job, "candidat(s) non collecté(s)")
        _tprint(
            f"— {nom} ({effective_slug}) : budget de collecte du job épuisé, "
            "candidat non collecté (#514)."
        )
        return {
            "nom": nom, "slug": effective_slug, "statut": "budget_job_epuise", "parltrack": "n/a",
        }

    _tprint(f"\n=== {nom} ({effective_slug}) ===")

    # Chambres FR à interroger selon --source
    if source == "an":
        chambres_fr: list[str] = ["deputes"]
    elif source == "ue":
        chambres_fr = []  # skip FR entièrement
    else:  # "all"
        chambres_fr = list(CHAMBRES)

    # --- Niveau 1 : appels FR et UE en parallèle ---
    profile: Optional[dict] = None
    chambre: Optional[str] = None
    mandat_ue: Optional[dict] = None
    warnings_chambres: list[str] = []

    def _fetch_fr() -> tuple[Optional[dict], Optional[str], list[str]]:
        if not chambres_fr:
            return None, None, []
        if not slug:
            _tprint(f"  — {nom} : pas de slug renseigné, aucune collecte FR possible.")
            return None, None, []
        result = build_profile_any_chambre(
            slug,
            chambres=chambres_fr,
            skip_interventions=args.skip_interventions,
            skip_dossiers_legislatifs=args.skip_dossiers_legislatifs,
            # #488 : les deux chambres ne sont interrogées que pour un profil de
            # CANDIDAT. Pour un membre de roster, un passé sénatorial n'alimente
            # aucun agrégat (aucun groupe sénatorial n'est agrégé) et coûterait
            # +30,6 min par shard — voir le docstring de la fonction.
            collecte_bicamerale=(provenance == "candidat_declare"),
            budget_interventions_secondes=args.budget_interventions_secondes,
            budget_collecte_secondes=getattr(args, "budget_collecte_secondes", None) or 0,
            budget_job=budget_job,
        )
        if result[0] is None:
            _tprint(f"  [!] Aucune identité trouvée pour {slug} dans {chambres_fr}.")
        return result

    def _fetch_ue() -> Optional[dict]:
        # --source an : extraction scopée, pas d'UE dans cette passe
        if source == "an":
            return None
        if args.skip_ue:
            return None
        try:
            result = build_profile_ue(nom)
        except Exception as exc:
            _tprint(f"  [!] Recherche du mandat européen impossible pour {nom} : {exc}")
            return None
        # Même principe que la temporisation de fin de fonction (#467) : un
        # `None` signifie que le nom n'apparaît pas dans la liste des
        # eurodéputés — liste mise en cache disque et téléchargée une fois par
        # process, donc aucun appel propre à ce candidat n'a eu lieu. Les
        # appels par candidat (détail du mandat, résolution des organisations)
        # n'existent que pour un mandat trouvé, cas où la temporisation reste.
        # Elle pesait sinon sur le chemin critique de chaque non-eurodéputé,
        # c'est-à-dire la quasi-totalité du roster.
        if result is not None:
            time.sleep(0.3)
        return result

    with ThreadPoolExecutor(max_workers=2) as pool:
        future_fr = pool.submit(_fetch_fr)
        future_ue = pool.submit(_fetch_ue)
        profile, chambre, warnings_chambres = future_fr.result()
        mandat_ue = future_ue.result()

    if profile is None and mandat_ue is None:
        # « introuvable » est un CONSTAT — le référentiel AN ne connaît pas ce
        # slug. Le statut `source_indisponible`, qui le distinguait d'une source
        # muette, est parti avec le compteur qui le décidait (#529) : plus aucune
        # requête d'identité ne quitte la machine, donc plus de silence réseau à
        # qualifier. Ce qui reste est une VRAIE panne — archive AMO30 absente ou
        # illisible —, et elle lève : `build_profile_any_chambre` la consigne en
        # `WARNING_PREFIX_CHAMBRE_EN_ECHEC`, qui est ce qu'on annote ici.
        #
        # Aucun profil n'est fabriqué pour autant : un squelette écrit à la place
        # d'une collecte manquée serait la donnée par défaut que la règle 2.5
        # interdit, et ferait basculer `chambre` sur une défaillance transitoire
        # (le défaut même de #484).
        en_echec = [
            w for w in warnings_chambres if w.startswith(WARNING_PREFIX_CHAMBRE_EN_ECHEC)
        ]
        if en_echec:
            for w in warnings_chambres:
                _tprint(f"  [!] {effective_slug} : {w}")
            # L'annotation porte le warning d'échec de chambre, pas le premier
            # de la liste : une troncature de budget peut le précéder, et c'est
            # bien la panne qu'il faut lire dans l'onglet de résumé du job.
            _annoter_github(f"{effective_slug} : {en_echec[0]}")
        # #539 — l'exception, et une seule : un slug **déclaré hors AN** dans la
        # table committée (`ecart: "hors_an"`, avec motif et preuve relus). Ce
        # n'est pas une collecte manquée, c'est un fait vérifié — et sans profil,
        # le candidat existerait dans le manifeste et disparaîtrait au clic.
        #
        # La condition est volontairement la déclaration, jamais l'absence de
        # résultat : un référentiel en panne rend exactement le même vide, et
        # écrire un squelette dessus serait le défaut de #484. Une panne déclarée
        # (`en_echec`) écarte donc la branche.
        declaree_hors_an = (_entree_correspondance(effective_slug) or {}).get("ecart") == "hors_an"
        if not en_echec and declaree_hors_an:
            _tprint(
                f"  — {effective_slug} : absence d'acteur AN DÉCLARÉE dans la table "
                "(#525) — profil écrit depuis raw_data/candidats.json seul (#539)."
            )
            profile = build_minimal_profile(nom, effective_slug, candidat)
        else:
            return {
                "nom": nom,
                "slug": effective_slug,
                "statut": "source_indisponible" if en_echec else "introuvable",
                "parltrack": "n/a",
            }
    if profile is None:
        # Candidat sans mandat français connu, mais avec un mandat européen
        # (ex. Jordan Bardella) : on crée un profil minimal à partir de
        # raw_data/candidats.json plutôt que de ne rien produire.
        profile = build_minimal_profile(nom, effective_slug, candidat)
        # #488/#484 : si la collecte FR a ÉCHOUÉ (au lieu de simplement ne rien
        # trouver), le squelette ne doit pas être écrit comme s'il était un
        # constat. La raison de l'échec part avec lui dans le profil brut.
        if warnings_chambres:
            profile["meta"].setdefault("warnings", []).extend(warnings_chambres)

    if mandat_ue is not None:
        profile["mandat_europeen"] = mandat_ue

    if json_path.exists():
        existing_profile = None
        try:
            existing_profile = charger_profil_brut(json_path)
        except (json.JSONDecodeError, OSError, PartitionIllisible) as exc:
            _tprint(f"  [!] Lecture du profil existant impossible ({json_path}), écrasement : {exc}")

        if existing_profile is not None:
            if not args.no_merge:
                profile = merge_raw_profile(existing_profile, profile)
            elif not args.autoriser_collecte_vide:
                # Mode écrasement : la fusion additive ne protège plus rien, et
                # une sous-collecte en échec (identité introuvable, endpoint en
                # panne) rend un profil d'apparence normale dont un champ est
                # simplement vide. Un `[]` non mesuré n'écrase pas un fait
                # acquis (#465, même principe que #427 sur les gouvernements).
                profile, preserves = preserver_collectes_non_vides(existing_profile, profile)
                if preserves:
                    _tprint(
                        f"  [!] {effective_slug} : collecte vide sur {', '.join(preserves)} — "
                        "entrées existantes PRÉSERVÉES malgré --no-merge (#465). "
                        "Relancer avec --autoriser-collecte-vide pour forcer le vidage."
                    )

    # #580 : l'écriture produit désormais la forme PARTITIONNÉE — un socle
    # `<slug>.json` sans `amendements`, plus `<slug>/<legislature>.json`. Un
    # profil relu monolithique et réécrit ici migre donc de lui-même, sans
    # qu'aucun octet ne se perde : `charger_profil_brut` a rendu la liste
    # entière, `ecrire_profil_brut` la range.
    ecrire_profil_brut(out_dir, effective_slug, profile)
    _manifest_append(getattr(args, "manifest_out", None), json_path.name)

    # Optionnel : écriture du profil pivot v1 (--pivot)
    if args.pivot:
        parti = candidat.get("parti")
        # Mode normal : les drapeaux du run décrivent VRAIMENT la collecte qui
        # vient d'avoir lieu, donc ils sont la source de la décision (#539).
        decisions = tuple(
            drapeau
            for drapeau, actif in (
                ("skip_interventions", args.skip_interventions),
                ("skip_dossiers_legislatifs", args.skip_dossiers_legislatifs),
            )
            if actif
        )
        pivot_profile = _normaliser_en_pivot(
            profile, mandat_ue,
            effective_slug=effective_slug, parti=parti, provenance=provenance,
            chambre=chambre, scrutins_index=scrutins_index, decisions=decisions,
        )
        if pivot_profile is not None:
            pivot_path = pivot_dir / f"{effective_slug}.pivot.json"
            existing_pivot = None
            if pivot_path.exists():
                try:
                    with open(pivot_path, encoding="utf-8") as f:
                        existing_pivot = json.load(f)
                except (json.JSONDecodeError, OSError) as exc:
                    _tprint(f"  [!] Lecture du pivot existant impossible ({pivot_path}) : {exc}")
            if not args.no_merge and existing_pivot is not None:
                pivot_profile = merge_pivot_profile(existing_pivot, pivot_profile)
            # #343 : ne pas ré-avancer genere_le/synchro_le si le contenu régénéré
            # est strictement identique au pivot déjà commité.
            pivot_profile = preserve_stable_freshness_timestamps(existing_pivot, pivot_profile)
            ecrire_profil_json(pivot_path, pivot_profile)
            _tprint(f"  ✓ pivot → {pivot_path}")

    nb_interventions = len(profile.get("interventions") or [])
    nb_mandats_ue = len((profile.get("mandat_europeen") or {}).get("mandats_europeens") or [])
    extra = f", {nb_mandats_ue} mandats UE" if mandat_ue or profile.get("mandat_europeen") else ""
    _tprint(f"  ✓ {chambre or 'sans chambre FR'} — {json_path} ({nb_interventions} interventions{extra})")

    # La temporisation de courtoisie entre deux candidats (#467) est RETIRÉE
    # par #529 : elle ménageait NosDéputés/NosSénateurs, une API publique tierce
    # qui n'est plus interrogée. Elle était déjà conditionnée au compteur
    # d'appels vers ces domaines — mesuré sur les 24 membres du shard 0 du run
    # 32288588518 rejoués en local, 1 seule requête HTTP pour 24 candidats, et
    # 12,0 s d'attente sur 74,1 s de temps mur. Ce qui reste sur le réseau,
    # l'open data de l'AN, est du téléchargement d'archive mis en cache par
    # législature, pas des pages par candidat : rien à lisser.

    return {
        "nom": nom,
        "slug": effective_slug,
        "statut": "ok",
        "chambre": chambre,
        "nb_interventions": nb_interventions,
        "nb_mandats_ue": nb_mandats_ue,
        "parltrack": "n/a",
    }


def _rafraichir_index_scrutins(
    args: argparse.Namespace, out_dir: Path, *, moment: str
) -> Optional[ScrutinsIndex]:
    """Reconstruit (ou charge) l'index partagé des scrutins.

    Appelé deux fois dans un run qui COLLECTE et pivote à la fois :

    - **avant** la boucle, pour que la normalisation dispose de la résolution de
      corpus sur les profils bruts déjà présents — c'est le seul appel utile en
      `--pivot-only`, où tous les bruts sont déjà là ;
    - **après** la boucle, parce que les profils collectés pendant le run
      n'existaient pas au premier appel : sans ce second passage, leurs scrutins
      manqueraient à l'index et les mappings tout juste écrits pointeraient dans
      le vide.

    Les identifiants écrits pendant la boucle restent valides : `_normalize_vote`
    et `construire_index` résolvent la législature dans le même ordre (index,
    puis législature portée par le vote, puis calendrier), donc le second
    passage complète l'index sans jamais renommer un scrutin.
    """
    chemin = Path(args.scrutins)
    if args.skip_scrutins_index:
        index = charger_scrutins(chemin)
        if moment == "avant":
            print(f"Index des scrutins (non reconstruit) : {len(index)} scrutin(s).")
        return index
    try:
        index, _ = rafraichir_scrutins(
            out_dir, chemin,
            strict=True,
            # Fusion additive sauf --no-merge : un run qui ne régénère qu'une
            # tranche ne voit qu'une partie des scrutins, et écraser l'index
            # laisserait les mappings des profils non retraités pointer dans le
            # vide (leçon de #450, au niveau de l'index cette fois). Le second
            # passage fusionne toujours, y compris sous --no-merge : il complète
            # ce que le premier vient d'écrire, il ne le remplace pas.
            fusionner=(moment == "apres") or not args.no_merge,
            genere_le=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        )
    except LegislatureIrresoluble as exc:
        # Échouer franchement : sans index complet, une partie des votes ne
        # référencerait rien, et rien ne le signalerait (AGENTS.md §2.5).
        raise SystemExit(
            f"[!] {exc}\n"
            "    Index des scrutins NON écrit. "
            "Diagnostic : python3 src/audit_legislature_votes.py"
        )
    print(f"Index des scrutins ({moment} collecte) : {len(index)} scrutin(s) → {chemin}")
    return index


def _rafraichir_index_amendements(args: argparse.Namespace, out_dir: Path) -> None:
    """Reconstruit l'index partagé des amendements depuis les profils bruts.

    **Une seule fois**, et après la boucle — contrairement à l'index des
    scrutins, qui l'est avant ET après. La différence est de nature : la clé
    d'un scrutin demande une résolution de corpus (la législature d'un vote se
    lit sur un jumeau étiqueté vivant dans un autre profil), donc la
    normalisation a besoin de l'index. La clé d'un amendement est son `uid` AN,
    porté par l'enregistrement lui-même, et sa législature se lit dans cet
    `uid` : `_normalize_amendement` n'a besoin de rien d'extérieur, et un
    passage préalable ne ferait que relire 1,5 Go pour rien.

    Reste indispensable APRÈS : les amendements des profils collectés pendant le
    run manqueraient sinon à l'index, et les mappings tout juste écrits
    pointeraient dans le vide.
    """
    if args.skip_amendements_index:
        print("Index des amendements : reconstruction sautée (--skip-amendements-index).")
        return
    dossier = Path(args.amendements)
    index = rafraichir_amendements(
        out_dir, dossier,
        # Fusion additive sauf --no-merge : un run qui ne régénère qu'une
        # tranche ne voit qu'une partie des amendements, et écraser l'index
        # laisserait les mappings des profils non retraités pointer dans le vide
        # (leçon de #450, au niveau de l'index).
        fusionner=not args.no_merge,
        genere_le=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    )
    detail = ", ".join(
        f"{legislature}: {len(index.ids_de_legislature(legislature))}"
        for legislature in index.legislatures()
    )
    print(f"Index des amendements : {len(index)} amendement(s) → {dossier} ({detail})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--candidats", default=DEFAULT_CANDIDATS_PATH, help=f"Fichier JSON listant les candidats (défaut: {DEFAULT_CANDIDATS_PATH})")
    parser.add_argument("--only", help="Ne traiter qu'un seul candidat (par slug), utile pour tester")
    parser.add_argument(
        "--budget-interventions-secondes", type=int, default=0,
        help="Budget de temps mur (s) pour la collecte d'interventions d'UN candidat : débats "
             "Syceron et questions officielles. "
             "Épuisé, la collecte s'arrête entre deux unités, le profil est écrit avec ce qui a été "
             "collecté et la troncature est consignée dans meta.warnings[]. 0 (défaut) = aucun "
             "budget. INCOMPATIBLE avec --skip-interventions (le budget n'aurait rien à "
             "borner) : la combinaison est refusée plutôt que neutralisée en silence, "
             "c'est l'origine de #514. Voir #498.")
    parser.add_argument(
        "--budget-collecte-secondes", type=int, default=None,
        help="Budget de temps mur (s) pour la collecte ENTIÈRE d'UN candidat : identité, "
             "votes, dossiers législatifs, interventions comprises. Épuisé, la collecte "
             "s'arrête entre deux requêtes, le profil partiel est écrit et la troncature "
             "part dans meta.warnings[] et en ::warning::. Contrairement au budget "
             "d'interventions, il n'est neutralisé par AUCUN autre drapeau. "
             "0 = pas de budget, DÉCLARÉ comme tel ; omettre l'option laisse la collecte "
             "sans plafond et sans décision écrite — c'est exactement ce qui a coûté "
             "15 minutes de runner pour un profil à l'ex-job extract-senat, retiré "
             "depuis (#514, #528).")
    parser.add_argument(
        "--budget-job-secondes", type=int, default=0,
        help="Budget de temps mur (s) pour la collecte réseau de TOUT le run. Épuisé, les "
             "candidats restants sortent en `budget_job_epuise` sans aucune requête et le "
             "run se termine normalement (résumé, annotations, publication) au lieu d'être "
             "tué par le `timeout-minutes` du job. 0 (défaut) = aucun budget. Voir #514.")
    parser.add_argument("--skip-existing", action="store_true",
                        help="Ne JAMAIS régénérer un profil dont le fichier JSON existe déjà. Strict "
                             "depuis #578 : plus aucune exemption implicite (--limit posait autrefois "
                             "une exemption pour les profils périmés, sans le nommer). Pour recollecter "
                             "l'existant, ne pas poser ce drapeau.")
    parser.add_argument("--refresh-existing", action="store_true",
                        help="Ne traiter QUE les candidats dont le profil JSON existe déjà (#445) : "
                             "l'inverse exact de --skip-existing. Sert à propager une correction de "
                             "fond à l'existant sans étendre la couverture. À combiner avec --no-merge "
                             "quand la correction porte sur une clé (sinon la fusion additive conserve "
                             "les entrées erronées à côté des corrigées).")
    parser.add_argument("--skip-ue", action="store_true", help="Ne pas interroger l'Open Data Portal du Parlement européen (mandat européen)")
    parser.add_argument(
        "--source",
        choices=list(SOURCE_VALUES),
        default="all",
        help=(
            "Scoper l'extraction à une seule source : "
            "'an' = Assemblée nationale uniquement, "
            "'ue' = Open Data Portal UE uniquement, "
            "'all' = toutes les sources (comportement par défaut). "
            "Avec 'an', la source UE est ignorée. Avec 'ue', la source FR (AN) est "
            "ignorée. La valeur 'senat' a été retirée par #528 : le Sénat est hors "
            "périmètre, et argparse refuse la valeur plutôt que de laisser une passe "
            "tourner à vide (docs/technical_decisions.md#retrait-senat-528)."
        ),
    )
    parser.add_argument("--out-dir", default=str(DEFAULT_PROFILES_DIR), help=f"Dossier de sortie des profils JSON bruts (défaut: {DEFAULT_PROFILES_DIR})")
    parser.add_argument("--manifest-out", default=None, metavar="FICHIER",
                        help="Consigne, une par ligne, le nom de fichier de chaque profil brut "
                             "RÉELLEMENT écrit par ce run (#450). Permet à un job d'extraction de "
                             "ne publier que sa contribution, et non tout --out-dir (qui contient "
                             "aussi la baseline committée, périmée). Sans effet en --pivot-only "
                             "(aucun profil brut n'y est écrit).")
    parser.add_argument("--pivot", action="store_true", help="Écrire aussi <slug>.pivot.json au format schéma pivot v1 (en plus du JSON brut)")
    parser.add_argument(
        "--pivot-only",
        action="store_true",
        help=(
            "Mode sans réseau : charge les profils bruts existants dans --out-dir et ne fait que la "
            "normalisation pivot (--pivot implicite). Aucun appel API. Utile dans merge-and-pivot après "
            "assemblage des artifacts d'extraction parallèles."
        ),
    )
    parser.add_argument(
        "--enrich-parltrack",
        action="store_true",
        help=(
            "Enrichir les profils pivot avec les données ParlTrack (textes_portes, amendements) si les "
            "dumps .zst sont disponibles dans .cache/parltrack/. Si les dumps sont absents, un warning "
            "'ParlTrack (fallback)' est ajouté à meta.warnings sans bloquer la génération."
        ),
    )
    parser.add_argument(
        "--parltrack-status-out",
        default=None,
        metavar="FILE",
        help=(
            "Écrire un fichier JSON résumant le statut d'enrichissement ParlTrack par candidat "
            "(enrichi / vide / absent / erreur / n/a). Utilisé par check_quality_gate.py --parltrack-status-file."
        ),
    )
    parser.add_argument("--pivot-dir", default=str(DEFAULT_PIVOT_DIR), help=f"Dossier de sortie des profils pivot (défaut: {DEFAULT_PIVOT_DIR})")
    parser.add_argument("--scrutins", default=str(DEFAULT_SCRUTINS_PATH), metavar="FICHIER",
                        help=f"Index partagé des scrutins (#432, défaut : {DEFAULT_SCRUTINS_PATH}). "
                             "Reconstruit depuis --out-dir avant la passe pivot, puis fourni à la "
                             "normalisation : un profil ne porte plus que le mapping "
                             "{scrutin_id, position}.")
    parser.add_argument("--skip-scrutins-index", action="store_true",
                        help="Ne pas reconstruire l'index des scrutins ; l'index existant est "
                             "simplement chargé. Utile pour re-piver une tranche sans repayer la "
                             "passe de corpus (~26 s sur 209 profils).")
    parser.add_argument("--amendements", default=str(DEFAULT_AMENDEMENTS_DIR), metavar="DOSSIER",
                        help=f"Index partagé des amendements (#431, défaut : {DEFAULT_AMENDEMENTS_DIR}). "
                             "Un fichier par législature, plus un fichier compagnon de cosignatures. "
                             "Reconstruit depuis --out-dir APRÈS la passe pivot : un profil ne porte "
                             "plus que le mapping {amendement_id, role_signataire}.")
    parser.add_argument("--skip-amendements-index", action="store_true",
                        help="Ne pas reconstruire l'index des amendements. Les mappings déjà écrits "
                             "restent valides — l'identifiant est l'uid AN, il ne dépend d'aucune "
                             "résolution de corpus — mais un amendement vu pour la première fois "
                             "pendant ce run manquera à l'index jusqu'à la prochaine reconstruction.")
    parser.add_argument("--autoriser-collecte-vide", action="store_true",
                        help="Lever le garde-fou de #465 : autoriser une collecte VIDE à écraser "
                             "des entrées existantes en mode --no-merge. Par défaut, un champ "
                             "revenu à zéro ne remplace jamais un champ qui en portait — un `[]` "
                             "rendu par une API en panne n'est pas un fait mesuré (AGENTS.md "
                             "§2.5). À n'employer que pour vider délibérément un champ.")
    parser.add_argument("--no-merge", action="store_true",
                        help="Écraser complètement les fichiers existants au lieu de fusionner de façon additive "
                             "les nouvelles données avec celles déjà présentes (comportement par défaut : fusion, "
                             "qui évite de perdre des votes/interventions/mandats déjà collectés en cas d'aléa des API).")
    # #510 : `--max-pages` (recherche NosDéputés) et `--activer-interventions-syceron`
    # ont été retirés ensemble — la recherche parce qu'elle n'alimentait que le
    # repli, le drapeau parce que son contenu est devenu le comportement. Le
    # second est REFUSÉ bruyamment plutôt qu'ignoré : un run qui le passe encore
    # doit lire la décision, pas croire la collecte Syceron désactivée.
    parser.add_argument("--activer-interventions-syceron",
                        action=RefusDrapeauInterventionsSyceron)
    parser.add_argument("--skip-interventions", action="store_true",
                        help="Ne pas extraire les interventions (ni les débats Syceron ni les questions officielles AN). "
                             "Accélère fortement l'extraction ; les interventions existantes restent intactes en mode fusion.")
    parser.add_argument("--skip-dossiers-legislatifs", action="store_true",
                        help="Ne pas extraire les dossiers législatifs — depuis #528, ils n'ont plus "
                             "qu'une source, fetch_textes_portes_officiels (AN). Combiné à --skip-interventions, constitue le "
                             "mode d'extraction léger identité+mandats+votes+amendements (#357) utilisé par "
                             "extract-roster-groupes : les dossiers/interventions/questions officielles ne sont consommés "
                             "par aucun agrégat de groupe (#349). Les dossiers existants restent intacts en mode fusion.")
    parser.add_argument("--workers", type=int, default=4, metavar="N",
                        help="Nombre de candidats traités en parallèle (niveau 2 ; défaut: 4). "
                             "Réduire si les API publiques commencent à renvoyer des erreurs 429. "
                             "En extraction légère AN (--skip-interventions --skip-dossiers-legislatifs, "
                             "mode du job roster), monter cette valeur RALENTIT : la charge y est du "
                             "parsing JSON sous GIL, pas du réseau — mesuré +41 %% à 4 workers (#467, "
                             "docs/technical_decisions.md#budget-execution-pleine-echelle-467).")
    parser.add_argument("--checkpoint-file", default=DEFAULT_CHECKPOINT_PATH,
                        help=f"Fichier de point de sauvegarde de la progression, mis à jour après chaque "
                             f"candidat traité (défaut: {DEFAULT_CHECKPOINT_PATH}).")
    parser.add_argument("--resume", action="store_true",
                        help="Reprendre depuis le dernier point de sauvegarde : ignore les candidats déjà "
                             "marqués 'ok' ou 'deja_present' lors d'une exécution précédente interrompue.")
    parser.add_argument("--no-checkpoint", action="store_true",
                        help="Désactiver l'écriture du point de sauvegarde intermédiaire. À poser "
                             "sur toute passe qui n'a rien à reprendre — une passe --pivot-only, "
                             "par exemple : le point de sauvegarde est écrit dans "
                             f"{DEFAULT_CHECKPOINT_PATH}, c'est-à-dire DANS le répertoire des "
                             "profils bruts, où tout ce qui inventorie le corpus le rencontre "
                             "(#518).")
    limit_group = parser.add_mutually_exclusive_group()
    parser.add_argument("--shard", default=None, metavar="I/N",
                        help="Ne traiter que la tranche I sur N du fichier de candidats "
                             "(ex. --shard 0/8). Découpage par position modulo, déterministe : "
                             "un candidat retombe toujours dans le même shard. Appliqué avant "
                             "--limit/--sample/--skip-existing (#394).")
    limit_group.add_argument("--limit", type=int, default=None, metavar="N",
                        help="PLAFOND de volume : ne traiter que N candidats de la population "
                             "sélectionnée. Le budget va d'abord aux non-couverts, puis aux couverts "
                             "périmés (#224) — sauf sous --skip-existing, où il ne va qu'aux "
                             "non-couverts. Ne commande AUCUNE politique de rafraîchissement (#578). "
                             "Mutuellement exclusif avec --sample.")
    limit_group.add_argument("--sample", type=int, default=None, metavar="N",
                        help="Ne traiter qu'un échantillon aléatoire de N candidats. "
                             "Mutuellement exclusif avec --limit.")
    parser.add_argument("--staleness-days", type=int, default=30, metavar="JOURS",
                        help="Utilisé seulement quand --limit plafonne la population (#224) : seuil "
                             "d'ancienneté (jours) au-delà duquel un candidat déjà couvert (pivot "
                             "existant) devient PRIORITAIRE pour le budget restant. Règle de priorité "
                             "sous plafond, pas une politique de rafraîchissement — un correctif de code "
                             "ne périme aucune date (#578). Même sémantique et défaut que "
                             "audit_pivot_dataset.py --staleness-days (défaut: 30).")
    args = parser.parse_args()

    # --refresh-existing sélectionne exactement ce que --skip-existing écarte :
    # combinés, ils ne traitent personne. Échouer franchement plutôt que
    # laisser un job tourner 8 minutes pour n'écrire aucun profil (#445).
    if args.refresh_existing and args.skip_existing:
        raise SystemExit("[!] --refresh-existing et --skip-existing s'annulent : "
                         "le premier ne retient que les profils existants, le second "
                         "les saute tous. Aucun candidat ne serait traité.")

    # --pivot-only implique --pivot (normalisation pivot activée)
    if args.pivot_only:
        args.pivot = True

    # ── Garde-fous de budget (#514) ─────────────────────────────────────────
    valider_budgets(args)

    # #510 : la source primaire des interventions alimente réellement les
    # profils depuis le 27/08/2026, et elle est la SEULE (le repli NosDéputés a
    # été retiré). Annoncé à chaque run qui collecte : la volumétrie change
    # d'ordre de grandeur, ce n'est pas une ligne de log à découvrir après coup.
    if not args.skip_interventions:
        print("[#510] Interventions : débats Syceron (source unique — le repli NosDéputés a "
              "été retiré). Mesuré le 26/08/2026 sur les trois archives : 1 227 415 "
              "interventions indexables, 1 664,8 Mio d'index, lues par tranche d'acteur.")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    # Tronqué avant tout traitement : un manifeste vide (job qui n'écrit rien)
    # doit rester distinguable d'un manifeste absent (option non passée).
    _init_manifest(args.manifest_out)
    pivot_dir = Path(args.pivot_dir)
    if args.pivot:
        pivot_dir.mkdir(parents=True, exist_ok=True)

    candidats = load_candidats(args.candidats)
    if args.only:
        candidats = [c for c in candidats if (c.get("slug") or _slugify(c.get("nom") or "")) == args.only]
        if not candidats:
            print(f"Aucun candidat avec le slug '{args.only}' dans {args.candidats}.")
            return

    # Partitionnement en shards (#394), AVANT toute autre sélection : voir
    # _select_shard pour pourquoi l'ordre compte.
    if args.shard:
        try:
            shard_index, shard_total = _parse_shard(args.shard)
        except ValueError as exc:
            # Pas de sys importé dans ce module : on échoue franchement plutôt
            # que de traiter silencieusement la mauvaise tranche.
            raise SystemExit(f"[!] {exc}")
        avant_shard = len(candidats)
        candidats = _select_shard(candidats, shard_index, shard_total)
        print(f"Shard {shard_index}/{shard_total} : {len(candidats)}/{avant_shard} candidat(s) dans cette tranche.")

    # Régénération de l'existant (#445) : sélection strictement inverse de la
    # frontière de conquête de #224. Une correction de fond (ex. la clé uid de
    # #440) ne concerne que les profils DÉJÀ écrits ; les atteindre par --limit
    # est impossible, car l'ordre de raw_data/roster_candidats.json n'est pas
    # stable dans le temps — le fichier est régénéré — et les profils couverts
    # y sont donc dispersés, pas groupés en tête (mesuré : dernier couvert à
    # l'index 93 sur 94 dans un shard de 8).
    #
    # Appliqué APRÈS --shard (chaque shard régénère sa propre tranche) et AVANT
    # --limit (qui peut encore borner le lot, pour un run d'essai).
    if getattr(args, "refresh_existing", False):
        avant = len(candidats)
        candidats = _select_existants(candidats, out_dir)
        print(f"Régénération de l'existant (--refresh-existing, #445) : "
              f"{len(candidats)}/{avant} candidat(s) déjà couvert(s) retenu(s).")
        if not candidats:
            print("Aucun profil existant dans cette tranche : rien à régénérer.")
            return

    # ── Plafond de volume (#578) ────────────────────────────────────────────
    # `--limit` est un PLAFOND, et rien d'autre. Jusqu'à #578, sa seule
    # présence décidait aussi si les profils déjà écrits étaient recollectés :
    # `--limit 20 --skip-existing` rafraîchissait les périmés, `--skip-existing`
    # seul n'en rafraîchissait aucun. Un run à pleine échelle (« 0 = pas de
    # plafond ») corrigeait donc STRICTEMENT MOINS qu'un run échantillonné —
    # l'inverse de ce que le formulaire annonçait, et le second run raté du
    # 28/08/2026.
    #
    # Qui est dans la population se décide maintenant plus haut, par une
    # intention nommée : `--refresh-existing` (l'existant seul),
    # `--skip-existing` (les non-couverts seuls), ni l'un ni l'autre (tout le
    # monde, l'existant recollecté et fusionné). Ne rien poser ici ne dégrade
    # donc plus rien : c'est le run complet.
    if args.limit is not None or args.sample is not None:
        avant = len(candidats)
        if args.limit is not None and not args.refresh_existing:
            # Répartition du budget : aux non-couverts d'abord, puis aux
            # couverts périmés (#224). `inclure_existants=False` sous
            # `--skip-existing` : les couverts seraient sélectionnés pour être
            # sautés, c'est-à-dire du budget dépensé à ne rien faire.
            candidats = _select_candidats_couverture(
                candidats, pivot_dir, limit=args.limit,
                staleness_days=args.staleness_days,
                inclure_existants=not args.skip_existing,
            )
            print(f"Plafond réparti par couverture (--limit {args.limit}, #224) : "
                  f"{len(candidats)}/{avant} candidat(s) retenu(s) "
                  f"(non couverts d'abord"
                  f"{', puis couverts périmés' if not args.skip_existing else ' uniquement'}).")
        else:
            candidats = _select_candidats(candidats, limit=args.limit, sample=args.sample)
            print(f"Sélection réduite ({'--limit' if args.limit is not None else '--sample'}) : "
                  f"{len(candidats)}/{avant} candidat(s) retenu(s).")

    # ── Index partagé des scrutins (#432) ───────────────────────────────────
    # Construit depuis `out_dir` (les profils bruts, qui gardent
    # l'enregistrement complet du vote) : la résolution de législature est une
    # passe de CORPUS — un jumeau étiqueté vit dans un autre profil que celui
    # qu'on normalise, donc un travail par profil ne le verrait jamais.
    scrutins_index: Optional[ScrutinsIndex] = None
    if args.pivot:
        scrutins_index = _rafraichir_index_scrutins(args, out_dir, moment="avant")

    checkpoint_path = Path(args.checkpoint_file)
    checkpoint = _load_checkpoint(checkpoint_path) if not args.no_checkpoint else {"resultats": []}
    resultats: list[dict[str, Any]] = list(checkpoint.get("resultats") or []) if args.resume else []

    if args.resume:
        deja_traites = {r["slug"] for r in resultats if r.get("statut") in ("ok", "deja_present")}
        if deja_traites:
            avant = len(candidats)
            candidats = [c for c in candidats if (c.get("slug") or _slugify(c.get("nom") or "")) not in deja_traites]
            print(f"Reprise depuis {checkpoint_path} : {avant - len(candidats)} candidat(s) déjà traité(s) ignoré(s).")

    # --- Niveau 2 : pool de threads inter-candidats ---
    # #514 : le budget de collecte du job est créé ici et partagé par tous les
    # candidats. `BudgetCollecte` est thread-safe, et la mesure reste
    # conservatrice avec `--workers > 1` (le temps de plusieurs candidats
    # simultanés se cumule sur le même compteur) : on rend la main trop tôt
    # plutôt que trop tard, ce qui est le bon sens de l'erreur pour un plafond.
    budget_job = creer_budget(args.budget_job_secondes, "collecte du job")
    total = len(candidats)
    nb_workers = min(args.workers, len(candidats)) if candidats else 1
    with ThreadPoolExecutor(max_workers=nb_workers) as pool:
        futures = {
            pool.submit(
                process_candidat, candidat, args, out_dir, pivot_dir,
                scrutins_index, budget_job,
            ): candidat
            for candidat in candidats
        }
        for i, future in enumerate(as_completed(futures), start=1):
            try:
                resultat = future.result()
            except Exception as exc:
                candidat = futures[future]
                nom = candidat.get("nom", "?")
                slug = candidat.get("slug") or _slugify(nom)
                print(f"  [!] Erreur inattendue pour {nom} ({slug}) : {exc}")
                resultat = {"nom": nom, "slug": slug, "statut": "erreur", "parltrack": "n/a"}
            resultats.append(resultat)
            if not args.no_checkpoint:
                _save_checkpoint(checkpoint_path, resultats)
            _tprint(f"  [point de sauvegarde {i}/{total}] {resultat.get('nom')} : {resultat.get('statut')}")

    # Second passage : les profils bruts collectés pendant la boucle
    # n'existaient pas au premier. Inutile en --pivot-only, qui n'écrit aucun
    # brut, et sauté quand rien n'a été traité.
    if args.pivot and not args.pivot_only and candidats:
        _rafraichir_index_scrutins(args, out_dir, moment="apres")

    # Index des amendements (#431) : une seule reconstruction, après la boucle.
    if args.pivot:
        _rafraichir_index_amendements(args, out_dir)

    print("\n=== Résumé ===")
    for r in sorted(resultats, key=lambda x: x.get("nom") or ""):
        extra = f" ({r.get('nb_interventions')} interventions, {r.get('chambre')})" if r["statut"] in ("ok", "ok_pivot_only") else ""
        print(f"  - {r['nom']}: {r['statut']}{extra}")

    # #514 : ce que le run n'a PAS pu faire, compté et annoté. Une ligne par
    # candidat dans une liste de treize se lit mal ; un total remonte dans
    # l'onglet de résumé du job, là où on cherche pourquoi il n'a rien produit.
    indisponibles = [r for r in resultats if r.get("statut") == "source_indisponible"]
    non_collectes = [r for r in resultats if r.get("statut") == "budget_job_epuise"]
    if indisponibles:
        _annoter_github(
            f"{len(indisponibles)} candidat(s) sans profil parce que la source n'a pas "
            f"répondu (et non parce qu'elle les ignore) : "
            f"{', '.join(sorted(r.get('slug') or '?' for r in indisponibles))}."
        )
    if non_collectes:
        _annoter_github(
            f"{len(non_collectes)} candidat(s) non collecté(s) : budget de collecte du "
            f"job ({args.budget_job_secondes} s) épuisé avant leur tour — "
            f"{', '.join(sorted(r.get('slug') or '?' for r in non_collectes))}."
        )
    # Imprime sur stderr et annote le job ; rien à réafficher ici.
    annoncer_troncature(budget_job, "collecte du job")

    # Écriture du fichier de statut ParlTrack si demandé
    if args.parltrack_status_out:
        parltrack_status: dict[str, Any] = {
            "enrichi": [],
            "vide": [],
            "absent": [],
            "erreur": [],
            "n/a": [],
        }
        for r in resultats:
            statut_pt = r.get("parltrack", "n/a") or "n/a"
            parltrack_status.setdefault(statut_pt, []).append(r.get("slug") or r.get("nom", "?"))

        status_path = Path(args.parltrack_status_out)
        status_path.parent.mkdir(parents=True, exist_ok=True)
        with open(status_path, "w", encoding="utf-8") as f:
            json.dump(parltrack_status, f, ensure_ascii=False, indent=2)
        print(f"\n  ParlTrack status → {status_path}")
        print(f"    enrichi : {len(parltrack_status.get('enrichi', []))}")
        print(f"    absent (fallback) : {len(parltrack_status.get('absent', []))}")


if __name__ == "__main__":
    main()
