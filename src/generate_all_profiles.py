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
from candidate_profile import build_profile
from candidate_profile_ue import build_profile_ue
from merge_profile import merge_pivot_profile, merge_raw_profile, preserve_stable_freshness_timestamps
from normalize_europarl import normalize_europarl
from normalize_nosdeputes import normalize_nosdeputes
from text_utils import slugify

# Chemins par défaut, relatifs à la racine du dépôt (voir README pour l'arborescence).
DEFAULT_CANDIDATS_PATH = "raw_data/candidats.json"
DEFAULT_PROFILES_DIR = Path("raw_data/profiles")
DEFAULT_PIVOT_DIR = Path("pivot_data/profiles")
DEFAULT_CHECKPOINT_PATH = "raw_data/profiles/.generation_checkpoint.json"

CHAMBRES = ["deputes", "senateurs"]

# Répertoire de cache ParlTrack — identique à parltrack_dumps.PARLTRACK_CACHE_DIR.
_PARLTRACK_CACHE_DIR = Path(".cache") / "parltrack"

# Valeurs acceptées par --source.
SOURCE_VALUES = ("an", "senat", "ue", "all")

# Verrou global pour sérialiser les print() et éviter un affichage interleaved.
_PRINT_LOCK = threading.Lock()
# Verrou global pour sérialiser l'écriture du fichier de point de sauvegarde.
_CHECKPOINT_LOCK = threading.Lock()


def _tprint(*args: Any, **kwargs: Any) -> None:
    """Equivalent thread-safe de print())."""
    with _PRINT_LOCK:
        print(*args, **kwargs)


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
    pour ne jamais laisser un fichier tronqué si le process est interrompu pendant l'écriture."""
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
) -> tuple[Optional[dict], Optional[str]]:
    """Essaie les chambres indiquées (défaut : deputes puis senateurs) et renvoie
    le premier profil avec une identité exploitable."""
    if chambres is None:
        chambres = CHAMBRES
    for chambre in chambres:
        try:
            profile = build_profile(
                chambre,
                slug,
                intervention_max_pages=max_pages,
                skip_interventions=skip_interventions,
                skip_dossiers_legislatifs=skip_dossiers_legislatifs,
            )
        except Exception as exc:
            _tprint(f"  [!] Échec ({chambre}) pour {slug} : {exc}")
            continue
        if profile.get("identite"):
            return profile, chambre
    return None, None


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
        # provenance (#189) : "roster_groupe" pour les entrées produites par
        # generate_roster_candidats.py (#188, statut="roster_groupe"), "candidat_declare"
        # sinon (raw_data/candidats.json, comportement historique par défaut).
        provenance = "roster_groupe" if candidat.get("statut") == "roster_groupe" else "candidat_declare"

        pivot_profile = normalize_nosdeputes(profile, parti=parti, provenance=provenance) if chambre else None
        if mandat_ue is not None:
            ue_pivot = normalize_europarl(mandat_ue, parti=parti, provenance=provenance)
            if pivot_profile is None:
                pivot_profile = ue_pivot
            else:
                pivot_profile["sources"].extend(ue_pivot.get("sources") or [])
                pivot_profile["mandats"].extend(ue_pivot.get("mandats") or [])

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
        with open(pivot_path, "w", encoding="utf-8") as f:
            json.dump(pivot_profile, f, ensure_ascii=False, indent=2)
        _tprint(f"  ✓ pivot-only → {pivot_path}")
        return {
            "nom": nom, "slug": effective_slug, "statut": "ok_pivot_only", "parltrack": parltrack_statut,
        }

    # ── Mode normal : skip-existing ─────────────────────────────────────────
    if args.skip_existing and json_path.exists() and effective_slug not in (refresh_slugs or ()):
        _tprint(f"— {nom} ({effective_slug}) : profil déjà présent, ignoré (--skip-existing).")
        return {"nom": nom, "slug": effective_slug, "statut": "deja_present", "parltrack": "n/a"}

    _tprint(f"\n=== {nom} ({effective_slug}) ===")

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

    def _fetch_fr() -> tuple[Optional[dict], Optional[str]]:
        if not chambres_fr:
            return None, None
        if not slug:
            _tprint(f"  — {nom} : pas de slug renseigné (candidat non référencé sur NosDéputés/NosSénateurs).")
            return None, None
        result = build_profile_any_chambre(
            slug,
            args.max_pages,
            chambres=chambres_fr,
            skip_interventions=args.skip_interventions,
            skip_dossiers_legislatifs=args.skip_dossiers_legislatifs,
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
        time.sleep(0.3)
        return result

    with ThreadPoolExecutor(max_workers=2) as pool:
        future_fr = pool.submit(_fetch_fr)
        future_ue = pool.submit(_fetch_ue)
        profile, chambre = future_fr.result()
        mandat_ue = future_ue.result()

    if profile is None and mandat_ue is None:
        return {"nom": nom, "slug": effective_slug, "statut": "introuvable", "parltrack": "n/a"}
    if profile is None:
        # Candidat sans mandat français connu, mais avec un mandat européen
        # (ex. Jordan Bardella) : on crée un profil minimal à partir de
        # raw_data/candidats.json plutôt que de ne rien produire.
        profile = build_minimal_profile(nom, effective_slug, candidat)

    if mandat_ue is not None:
        profile["mandat_europeen"] = mandat_ue

    if not args.no_merge and json_path.exists():
        try:
            with open(json_path, encoding="utf-8") as f:
                existing_profile = json.load(f)
            profile = merge_raw_profile(existing_profile, profile)
        except (json.JSONDecodeError, OSError) as exc:
            _tprint(f"  [!] Fusion impossible avec le profil existant ({json_path}), écrasement : {exc}")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)

    # Optionnel : écriture du profil pivot v1 (--pivot)
    if args.pivot:
        parti = candidat.get("parti")
        # provenance (#189) : voir commentaire équivalent dans le bloc --pivot-only ci-dessus.
        provenance = "roster_groupe" if candidat.get("statut") == "roster_groupe" else "candidat_declare"
        pivot_profile = normalize_nosdeputes(profile, parti=parti, provenance=provenance) if chambre else None
        if mandat_ue is not None:
            ue_pivot = normalize_europarl(mandat_ue, parti=parti, provenance=provenance)
            if pivot_profile is None:
                pivot_profile = ue_pivot
            else:
                # Fusionner les données UE dans le pivot principal :
                # ajouter la source EP et les mandats européens.
                pivot_profile["sources"].extend(ue_pivot.get("sources") or [])
                pivot_profile["mandats"].extend(ue_pivot.get("mandats") or [])
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
            with open(pivot_path, "w", encoding="utf-8") as f:
                json.dump(pivot_profile, f, ensure_ascii=False, indent=2)
            _tprint(f"  ✓ pivot → {pivot_path}")

    nb_interventions = len(profile.get("interventions") or [])
    nb_mandats_ue = len((profile.get("mandat_europeen") or {}).get("mandats_europeens") or [])
    extra = f", {nb_mandats_ue} mandats UE" if mandat_ue or profile.get("mandat_europeen") else ""
    _tprint(f"  ✓ {chambre or 'sans chambre FR'} — {json_path} ({nb_interventions} interventions{extra})")

    time.sleep(0.5)  # on reste courtois avec l'API publique entre deux candidats

    return {
        "nom": nom,
        "slug": effective_slug,
        "statut": "ok",
        "chambre": chambre,
        "nb_interventions": nb_interventions,
        "nb_mandats_ue": nb_mandats_ue,
        "parltrack": "n/a",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--candidats", default=DEFAULT_CANDIDATS_PATH, help=f"Fichier JSON listant les candidats (défaut: {DEFAULT_CANDIDATS_PATH})")
    parser.add_argument("--only", help="Ne traiter qu'un seul candidat (par slug), utile pour tester")
    parser.add_argument("--max-pages", type=int, default=10, help="Pages max. de recherche d'interventions par candidat (défaut: 10)")
    parser.add_argument("--skip-existing", action="store_true", help="Ne pas régénérer un profil dont le fichier JSON existe déjà")
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
            "Avec 'ue', les sources FR (AN/Sénat) sont ignorées."
        ),
    )
    parser.add_argument("--out-dir", default=str(DEFAULT_PROFILES_DIR), help=f"Dossier de sortie des profils JSON bruts (défaut: {DEFAULT_PROFILES_DIR})")
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
    parser.add_argument("--no-merge", action="store_true",
                        help="Écraser complètement les fichiers existants au lieu de fusionner de façon additive "
                             "les nouvelles données avec celles déjà présentes (comportement par défaut : fusion, "
                             "qui évite de perdre des votes/interventions/mandats déjà collectés en cas d'aléa des API).")
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
                             "Réduire si les API publiques commencent à renvoyer des erreurs 429.")
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

    # --pivot-only implique --pivot (normalisation pivot activée)
    if args.pivot_only:
        args.pivot = True

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
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
            pool.submit(process_candidat, candidat, args, out_dir, pivot_dir, refresh_slugs): candidat
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
