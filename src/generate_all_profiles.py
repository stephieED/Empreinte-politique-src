#!/usr/bin/env python3
"""
generate_all_profiles.py

Récupère les données et génère le CV (JSON) de chaque candidat de
raw_data/candidats.json qui possède un "slug" (identifiant NosDéputés.fr /
NosSénateurs.fr) et/ou un mandat de député européen (recherché par nom via
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
  - Niveau 1 : pour chaque candidat, les appels NosDéputés.fr et Parlement
    européen sont lancés simultanément (deux API distinctes, aucun état partagé).
  - Niveau 2 : plusieurs candidats sont traités en parallèle grâce à un pool
    de threads (option --workers, défaut : 4). Les caches disque partagés sont
    protégés par des verrous définis dans candidate_profile.py et
    candidate_profile_ue.py.

Usage (depuis la racine du dépôt) :
    python src/generate_all_profiles.py
    python src/generate_all_profiles.py --only jean-luc-melenchon
    python src/generate_all_profiles.py --max-pages 5      # recherche d'interventions plus rapide
    python src/generate_all_profiles.py --skip-existing    # ne pas relancer un profil déjà généré
    python src/generate_all_profiles.py --skip-ue          # ne pas interroger l'API du Parlement européen
    python src/generate_all_profiles.py --pivot            # aussi écrire <slug>.pivot.json
    python src/generate_all_profiles.py --workers 4        # nb de candidats traités en parallèle (défaut: 4)
    python src/generate_all_profiles.py --resume            # reprendre depuis le dernier point de sauvegarde après une interruption
    python src/generate_all_profiles.py --limit 20          # ne traiter que les 20 premiers candidats (déploiement progressif)
    python src/generate_all_profiles.py --sample 20         # ne traiter qu'un échantillon aléatoire de 20 candidats
    python src/generate_all_profiles.py --manifest-out F    # consigner les profils écrits par CE run (publication CI scopée, #450)

Extraction pilotée par roster (composition réelle des groupes parlementaires,
cf. generate_roster_candidats.py et docs/technical_decisions.md#provenance-pivot)
plutôt que par la liste éditoriale par défaut (raw_data/candidats.json) :
    python src/generate_roster_candidats.py
    python src/generate_all_profiles.py --candidats raw_data/roster_candidats.json --pivot --skip-existing \
        --skip-interventions --skip-dossiers-legislatifs

Avec --limit ET --skip-existing combinés (cas ci-dessus), la sélection est
progressive et rafraîchissante plutôt que de reprendre systématiquement les N
premiers candidats du fichier source (#224) : voir _select_candidats_couverture
et --staleness-days.

--skip-interventions + --skip-dossiers-legislatifs combinés forment le mode
d'extraction léger (#357) : identité + mandats + votes + amendements
uniquement, sans dossiers législatifs/interventions/questions officielles —
utilisé par le job extract-roster-groupes de generate-data.yml, ces champs
n'étant consommés par aucun agrégat de groupe (#349).
"""

import argparse
import json
import random
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from audit_pivot_dataset import compute_profils_perimes
from budget_collecte import BudgetCollecte
from candidate_profile import (
    AIDE_ACTIVER_INTERVENTIONS_SYCERON,
    activer_resolution_acteur_nu_syceron,
    build_profile,
    compteur_appels_nosdeputes,
)
from candidate_profile_ue import build_profile_ue
from json_io import ecrire_profil_json
from merge_profile import (
    merge_pivot_profile,
    merge_raw_profile,
    preserve_stable_freshness_timestamps,
    preserver_collectes_non_vides,
)
from normalize_europarl import normalize_europarl
from normalize_nosdeputes import normalize_nosdeputes
from schema_pivot import appliquer_chambres
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

CHAMBRES = ["deputes", "senateurs"]

# Préfixes de warnings publiés dans `meta.warnings` du profil (#488). Même
# convention que candidate_profile.WARNING_PREFIX_* : le texte avant le premier
# ':' est le *type* agrégé par audit_pivot_dataset.compute_agregation_warnings.
WARNING_PREFIX_CHAMBRE_EN_ECHEC = "collecte de chambre en échec"
WARNING_PREFIX_DEUX_CHAMBRES = "carrière sur deux chambres"

# Répertoire de cache ParlTrack — identique à parltrack_dumps.PARLTRACK_CACHE_DIR.
_PARLTRACK_CACHE_DIR = Path(".cache") / "parltrack"

# Valeurs acceptées par --source.
SOURCE_VALUES = ("an", "senat", "ue", "all")

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
    reference_date: Optional[datetime] = None,
) -> tuple[list[dict[str, Any]], set[str]]:
    """Sélection progressive + rafraîchissement pour --limit combiné à
    --skip-existing (#224).

    Sans cela, --limit sélectionne toujours les N premiers candidats du
    fichier source (ordre déterministe) ; dès qu'ils existent tous (run 2),
    --skip-existing les saute tous et le job ne traite plus jamais personne.
    Les profils déjà couverts, eux, ne sont alors plus jamais rafraîchis.

    Partitionne `candidats` en "non couverts" (pas de pivot dans `pivot_dir`)
    et "couverts" (pivot existant), avant toute troncature par `limit` : le
    budget va d'abord aux non-couverts (frontière de conquête, ordre du
    fichier source), puis, s'il en reste, aux couverts périmés — fraîcheur au
    sens de `audit_pivot_dataset.compute_profils_perimes`, même seuil
    `staleness_days`. Un profil couvert et frais n'est jamais resélectionné :
    pas de gaspillage de budget sur des profils déjà à jour.

    L'ordre des couverts périmés au sein du budget restant suit celui renvoyé
    par `compute_profils_perimes` (tri alphabétique par `id`), pas un tri par
    degré de péremption — choix volontairement simple, cf. #224.

    Returns:
        (selection, slugs_a_rafraichir) : `slugs_a_rafraichir` est le
        sous-ensemble de `selection` (slugs effectifs) à exempter de
        --skip-existing dans `process_candidat` — ces profils existent déjà
        et doivent repasser par le merge additif plutôt que d'être sautés.
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

    slugs_a_rafraichir: set[str] = set()
    if restant > 0 and couverts:
        pivots_par_id = {
            pivot["id"]: candidat for candidat, pivot in couverts if pivot.get("id")
        }
        perimes_ids = compute_profils_perimes(
            [pivot for _, pivot in couverts if pivot.get("id")],
            staleness_days=staleness_days,
            reference_date=reference_date,
        )
        for pid in perimes_ids[:restant]:
            candidat = pivots_par_id[pid]
            selection.append(candidat)
            slugs_a_rafraichir.add(_effective_slug(candidat))

    return selection, slugs_a_rafraichir


def build_profile_any_chambre(
    slug: str,
    max_pages: int,
    chambres: Optional[list[str]] = None,
    skip_interventions: bool = False,
    skip_dossiers_legislatifs: bool = False,
    collecte_bicamerale: bool = False,
    budget_interventions_secondes: int = 0,
) -> tuple[Optional[dict], Optional[str], list[str]]:
    """Collecte le profil FR et renvoie `(profil_retenu, chambre_retenue, warnings)`.

    Avant #488, cette fonction s'arrêtait à la première chambre qui rendait une
    identité, et un `except Exception: continue` avalait les échecs sans laisser
    de trace ailleurs qu'en log. Deux conséquences mesurées dans le corpus :

    - un parlementaire présent des deux côtés était classé par **l'ordre de la
      boucle** — cas Retailleau, sénateur en exercice publié `chambre: "AN"` ;
    - une **défaillance transitoire** de la première chambre faisait basculer
      la chambre publiée sur la seconde, sans warning (cas Mélenchon, #484).

    Deux régimes, séparés par `collecte_bicamerale` :

    **`collecte_bicamerale=True` — profils de candidats** (`meta.provenance ==
    "candidat_declare"`, 8 slugs résolvables sur les 13 de
    `raw_data/candidats.json`). Toutes les chambres de `chambres` sont
    interrogées, et non plus seulement la première qui répond. C'est le seul
    endroit où un passé sénatorial a un usage : **biographique**, sur un CV
    (« a été sénateur de 2004 à 2010 »).

    **`collecte_bicamerale=False` — membres de roster** (`roster_groupe`, 201
    des 209 profils). Comportement historique : on s'arrête à la première
    chambre qui répond. Aucun groupe sénatorial n'est agrégé — aucun jeu de
    données Sénat structuré n'est exploitable, voir
    `docs/technical_decisions.md` § *Senate votes, amendments, sponsored texts*,
    et les deux `groupe-Senat-*.json` publiés portent `cohesion_votes: 0`. Le
    passé sénatorial d'un membre de roster n'alimente donc rien, et le collecter
    coûterait deux requêtes à ~9,5 s de médiane pour 752 membres, soit
    **+30,6 min par shard** et **+4 h 04** à pleine échelle (mesuré le
    20/08/2026, voir `docs/technical_decisions.md#deux-chambres-interrogees`).

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
    (donc propagés au pivot par `normalize_nosdeputes`), et rendus à l'appelant
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
    budget = (
        BudgetCollecte(budget_interventions_secondes, libelle="collecte d'interventions")
        if budget_interventions_secondes and not skip_interventions
        else None
    )

    resultats: list[tuple[str, dict]] = []
    echecs: list[tuple[str, str]] = []

    for chambre in chambres:
        try:
            profile = build_profile(
                chambre,
                slug,
                intervention_max_pages=max_pages,
                skip_interventions=skip_interventions,
                skip_dossiers_legislatifs=skip_dossiers_legislatifs,
                budget_interventions=budget,
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
            "licence_donnees": "ODbL (Regards Citoyens, à partir de l'Assemblée nationale / Sénat / JO)",
            "warnings": ["aucun mandat français connu (candidat non référencé sur NosDéputés/NosSénateurs, ou identité introuvable)"],
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
    refresh_slugs: Optional[set[str]] = None,
    scrutins_index: Optional[ScrutinsIndex] = None,
) -> dict[str, Any]:
    """Traite un candidat : collecte les données FR et UE en parallèle (niveau 1),
    écrit les fichiers JSON/HTML (et pivot si demandé), et renvoie un dict de résultat.

    Conçu pour être appelé depuis un ThreadPoolExecutor (niveau 2) : ne modifie
    aucun état partagé en dehors des fichiers de sortie individuels (thread-safe).

    Modes :
    - Normal (défaut) : fetch réseau FR et/ou UE selon --source, écriture raw, pivot optionnel.
    - --pivot-only    : charge le profil brut existant, normalise en pivot (pas de réseau).

    `refresh_slugs` (#224) : sous-ensemble de slugs à traiter normalement
    (fetch + merge additif) même si --skip-existing est actif et que le
    profil existe déjà — utilisé par `_select_candidats_couverture` pour
    rafraîchir les profils couverts mais périmés sans jamais les sauter.
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
            with open(json_path, encoding="utf-8") as f:
                profile = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            _tprint(f"  [!] Lecture impossible de {json_path} : {exc}")
            return {"nom": nom, "slug": effective_slug, "statut": "erreur", "parltrack": "n/a"}

        chambre = profile.get("chambre")
        mandat_ue = profile.get("mandat_europeen")
        parti = candidat.get("parti")

        pivot_profile = normalize_nosdeputes(profile, parti=parti, provenance=provenance, scrutins_index=scrutins_index) if chambre else None
        if mandat_ue is not None:
            ue_pivot = normalize_europarl(mandat_ue, parti=parti, provenance=provenance)
            if pivot_profile is None:
                pivot_profile = ue_pivot
            else:
                pivot_profile["sources"].extend(ue_pivot.get("sources") or [])
                pivot_profile["mandats"].extend(ue_pivot.get("mandats") or [])
                # #493 : `mandats[]` vient de changer, donc `chambres` aussi.
                # Sans ce recalcul, un profil AN + PE publierait `["AN"]` et
                # effacerait le mandat européen — le défaut même que #486
                # reproche au scalaire, reconduit dans le champ censé le corriger.
                appliquer_chambres(pivot_profile)

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
    if args.skip_existing and json_path.exists() and effective_slug not in (refresh_slugs or ()):
        _tprint(f"— {nom} ({effective_slug}) : profil déjà présent, ignoré (--skip-existing).")
        return {"nom": nom, "slug": effective_slug, "statut": "deja_present", "parltrack": "n/a"}

    _tprint(f"\n=== {nom} ({effective_slug}) ===")

    # Point de repère pour la temporisation de courtoisie de fin de fonction
    # (#467) : relevé AVANT toute collecte, comparé APRÈS.
    appels_nosdeputes_avant = compteur_appels_nosdeputes()

    # Chambres FR à interroger selon --source
    if source == "an":
        chambres_fr: list[str] = ["deputes"]
    elif source == "senat":
        chambres_fr = ["senateurs"]
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
            _tprint(f"  — {nom} : pas de slug renseigné (candidat non référencé sur NosDéputés/NosSénateurs).")
            return None, None, []
        result = build_profile_any_chambre(
            slug,
            args.max_pages,
            chambres=chambres_fr,
            skip_interventions=args.skip_interventions,
            skip_dossiers_legislatifs=args.skip_dossiers_legislatifs,
            # #488 : les deux chambres ne sont interrogées que pour un profil de
            # CANDIDAT. Pour un membre de roster, un passé sénatorial n'alimente
            # aucun agrégat (aucun groupe sénatorial n'est agrégé) et coûterait
            # +30,6 min par shard — voir le docstring de la fonction.
            collecte_bicamerale=(provenance == "candidat_declare"),
            budget_interventions_secondes=args.budget_interventions_secondes,
        )
        if result[0] is None:
            _tprint(f"  [!] Aucune identité trouvée pour {slug} dans {chambres_fr}.")
        return result

    def _fetch_ue() -> Optional[dict]:
        # --source an ou senat : extraction scopée, pas d'UE dans cette passe
        if source in ("an", "senat"):
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
        return {"nom": nom, "slug": effective_slug, "statut": "introuvable", "parltrack": "n/a"}
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
            with open(json_path, encoding="utf-8") as f:
                existing_profile = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
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

    ecrire_profil_json(json_path, profile)
    _manifest_append(getattr(args, "manifest_out", None), json_path.name)

    # Optionnel : écriture du profil pivot v1 (--pivot)
    if args.pivot:
        parti = candidat.get("parti")
        pivot_profile = normalize_nosdeputes(profile, parti=parti, provenance=provenance, scrutins_index=scrutins_index) if chambre else None
        if mandat_ue is not None:
            ue_pivot = normalize_europarl(mandat_ue, parti=parti, provenance=provenance)
            if pivot_profile is None:
                pivot_profile = ue_pivot
            else:
                # Fusionner les données UE dans le pivot principal :
                # ajouter la source EP et les mandats européens.
                pivot_profile["sources"].extend(ue_pivot.get("sources") or [])
                pivot_profile["mandats"].extend(ue_pivot.get("mandats") or [])
                # #493 : voir --pivot-only ci-dessus — `chambres` est dérivé de
                # `mandats[]`, il se recalcule après chaque mutation de la liste.
                appliquer_chambres(pivot_profile)
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

    # Courtoisie envers NosDéputés/NosSénateurs entre deux candidats — mais
    # seulement envers une source réellement sollicitée (#467). Depuis #369 un
    # député trouvé dans le référentiel historique AN ne déclenche AUCUN appel
    # NosDéputés, et depuis #392/#403 ses amendements et ses votes viennent
    # d'index locaux : mesuré sur les 24 membres du shard 0 du run 32288588518
    # rejoués en local, 1 seule requête HTTP pour les 24 candidats, et 12,0 s
    # de cette temporisation sur 74,1 s de temps mur — et la moitié de ce qui
    # restait une fois la relecture d'index supprimée : du travail passé à
    # ménager une source qu'on n'interrogeait pas.
    # Un sénateur, un député absent du référentiel AN ou une passe avec
    # interventions continuent d'appeler NosDéputés, donc de temporiser.
    # `compteur_appels_nosdeputes` est global, donc conservateur avec
    # `--workers > 1` : on peut temporiser pour les appels d'un autre candidat,
    # jamais s'en dispenser à tort.
    if compteur_appels_nosdeputes() != appels_nosdeputes_avant:
        time.sleep(0.5)

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
    parser.add_argument("--max-pages", type=int, default=10, help="Pages max. de recherche d'interventions par candidat (défaut: 10)")
    parser.add_argument(
        "--budget-interventions-secondes", type=int, default=0,
        help="Budget de temps mur (s) pour la collecte d'interventions d'UN candidat : recherche "
             "NosDéputés, débats Syceron, détails document par document, questions officielles. "
             "Épuisé, la collecte s'arrête entre deux unités, le profil est écrit avec ce qui a été "
             "collecté et la troncature est consignée dans meta.warnings[]. 0 (défaut) = aucun "
             "budget. Sans effet avec --skip-interventions. Voir #498.")
    parser.add_argument("--skip-existing", action="store_true", help="Ne pas régénérer un profil dont le fichier JSON existe déjà")
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
            "'senat' = Sénat uniquement, "
            "'ue' = Open Data Portal UE uniquement, "
            "'all' = toutes les sources (comportement par défaut). "
            "Avec 'an'/'senat', la source UE est ignorée. "
            "Avec 'ue', les sources FR (AN/Sénat) sont ignorées. "
            "Avec 'all', les DEUX chambres FR sont interrogées — et non plus seulement "
            "la première qui répond — pour les seuls profils de CANDIDATS "
            "(meta.provenance = candidat_declare, #488). Un membre de roster garde le "
            "comportement historique : on s'arrête à la première chambre qui répond."
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
    parser.add_argument("--activer-interventions-syceron", action="store_true",
                        help=AIDE_ACTIVER_INTERVENTIONS_SYCERON)
    parser.add_argument("--skip-interventions", action="store_true",
                        help="Ne pas extraire les interventions (ni la recherche NosDéputés ni les questions officielles AN). "
                             "Accélère fortement l'extraction ; les interventions existantes restent intactes en mode fusion.")
    parser.add_argument("--skip-dossiers-legislatifs", action="store_true",
                        help="Ne pas extraire les dossiers législatifs (ni la recherche NosDéputés pour les sénateurs, ni "
                             "fetch_textes_portes_officiels pour les députés). Combiné à --skip-interventions, constitue le "
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
                        help="Désactiver l'écriture du point de sauvegarde intermédiaire.")
    limit_group = parser.add_mutually_exclusive_group()
    parser.add_argument("--shard", default=None, metavar="I/N",
                        help="Ne traiter que la tranche I sur N du fichier de candidats "
                             "(ex. --shard 0/8). Découpage par position modulo, déterministe : "
                             "un candidat retombe toujours dans le même shard. Appliqué avant "
                             "--limit/--sample/--skip-existing (#394).")
    limit_group.add_argument("--limit", type=int, default=None, metavar="N",
                        help="Ne traiter que les N premiers candidats de la liste (déploiement progressif "
                             "contrôlé, ex. avant d'ouvrir l'extraction à un roster complet). "
                             "Mutuellement exclusif avec --sample.")
    limit_group.add_argument("--sample", type=int, default=None, metavar="N",
                        help="Ne traiter qu'un échantillon aléatoire de N candidats. "
                             "Mutuellement exclusif avec --limit.")
    parser.add_argument("--staleness-days", type=int, default=30, metavar="JOURS",
                        help="Utilisé seulement quand --limit et --skip-existing sont combinés (#224, lot "
                             "roster) : seuil d'ancienneté (jours) au-delà duquel un candidat déjà couvert "
                             "(pivot existant) est considéré périmé et resélectionné pour rafraîchissement "
                             "par merge additif plutôt que sauté par --skip-existing. Même sémantique et "
                             "défaut que audit_pivot_dataset.py --staleness-days (défaut: 30).")
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

    # #510 : réglé une fois, avant tout appel de collecte. L'index Syceron est
    # construit par législature et partagé entre les shards (#505), donc le mode
    # de résolution est une propriété du process, pas du candidat.
    activer_resolution_acteur_nu_syceron(args.activer_interventions_syceron)
    if args.activer_interventions_syceron and not args.skip_interventions:
        print("[#510] Résolution des identifiants d'orateur Syceron nus ACTIVÉE : la source "
              "primaire des interventions va alimenter les profils. Volumétrie mesurée sur la "
              "17e législature : 673 acteurs, 104 239 interventions, index de 136,8 Mio.")

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

    refresh_slugs: set[str] = set()
    if args.limit is not None or args.sample is not None:
        avant = len(candidats)
        if args.limit is not None and args.skip_existing:
            # Sélection progressive + rafraîchissement (#224) : voir
            # _select_candidats_couverture. Ne s'applique qu'à cette
            # combinaison précise de flags (--limit + --skip-existing,
            # utilisée par le job roster de generate-data.yml) ; --sample ou
            # --limit seul gardent le comportement historique ci-dessous.
            candidats, refresh_slugs = _select_candidats_couverture(
                candidats, pivot_dir, limit=args.limit, staleness_days=args.staleness_days,
            )
            print(f"Sélection progressive + rafraîchissement (--limit + --skip-existing, #224) : "
                  f"{len(candidats)}/{avant} candidat(s) retenu(s) "
                  f"({len(candidats) - len(refresh_slugs)} non couvert(s), "
                  f"{len(refresh_slugs)} périmé(s) à rafraîchir).")
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
    total = len(candidats)
    nb_workers = min(args.workers, len(candidats)) if candidats else 1
    with ThreadPoolExecutor(max_workers=nb_workers) as pool:
        futures = {
            pool.submit(
                process_candidat, candidat, args, out_dir, pivot_dir, refresh_slugs, scrutins_index,
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
