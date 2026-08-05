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
"""

import argparse
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Optional

from candidate_profile import build_profile
from candidate_profile_ue import build_profile_ue
from merge_profile import merge_pivot_profile, merge_raw_profile
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


# Alias local : voir text_utils.slugify (mutualisé avec parti_profile._slugify).
_slugify = slugify


def build_profile_any_chambre(
    slug: str, max_pages: int, chambres: Optional[list[str]] = None
) -> tuple[Optional[dict], Optional[str]]:
    """Essaie les chambres indiquées (défaut : deputes puis senateurs) et renvoie
    le premier profil avec une identité exploitable."""
    if chambres is None:
        chambres = CHAMBRES
    for chambre in chambres:
        try:
            profile = build_profile(chambre, slug, intervention_max_pages=max_pages)
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
        "synthese_activite": None,
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
) -> dict[str, Any]:
    """Traite un candidat : collecte les données FR et UE en parallèle (niveau 1),
    écrit les fichiers JSON/HTML (et pivot si demandé), et renvoie un dict de résultat.

    Conçu pour être appelé depuis un ThreadPoolExecutor (niveau 2) : ne modifie
    aucun état partagé en dehors des fichiers de sortie individuels (thread-safe).

    Modes :
    - Normal (défaut) : fetch réseau FR et/ou UE selon --source, écriture raw, pivot optionnel.
    - --pivot-only    : charge le profil brut existant, normalise en pivot (pas de réseau).
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

        pivot_profile = normalize_nosdeputes(profile, parti=parti) if chambre else None
        if mandat_ue is not None:
            ue_pivot = normalize_europarl(mandat_ue, parti=parti)
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
        if not args.no_merge and pivot_path.exists():
            try:
                with open(pivot_path, encoding="utf-8") as f:
                    existing_pivot = json.load(f)
                pivot_profile = merge_pivot_profile(existing_pivot, pivot_profile)
            except (json.JSONDecodeError, OSError) as exc:
                _tprint(f"  [!] Fusion impossible avec le pivot existant ({pivot_path}), écrasement : {exc}")
        with open(pivot_path, "w", encoding="utf-8") as f:
            json.dump(pivot_profile, f, ensure_ascii=False, indent=2)
        _tprint(f"  ✓ pivot-only → {pivot_path}")
        return {
            "nom": nom, "slug": effective_slug, "statut": "ok_pivot_only", "parltrack": parltrack_statut,
        }

    # ── Mode normal : skip-existing ─────────────────────────────────────────
    if args.skip_existing and json_path.exists():
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
        result = build_profile_any_chambre(slug, args.max_pages, chambres=chambres_fr)
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
        pivot_profile = normalize_nosdeputes(profile, parti=parti) if chambre else None
        if mandat_ue is not None:
            ue_pivot = normalize_europarl(mandat_ue, parti=parti)
            if pivot_profile is None:
                pivot_profile = ue_pivot
            else:
                # Fusionner les données UE dans le pivot principal :
                # ajouter la source EP et les mandats européens.
                pivot_profile["sources"].extend(ue_pivot.get("sources") or [])
                pivot_profile["mandats"].extend(ue_pivot.get("mandats") or [])
        if pivot_profile is not None:
            pivot_path = pivot_dir / f"{effective_slug}.pivot.json"
            if not args.no_merge and pivot_path.exists():
                try:
                    with open(pivot_path, encoding="utf-8") as f:
                        existing_pivot = json.load(f)
                    pivot_profile = merge_pivot_profile(existing_pivot, pivot_profile)
                except (json.JSONDecodeError, OSError) as exc:
                    _tprint(f"  [!] Fusion impossible avec le pivot existant ({pivot_path}), écrasement : {exc}")
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
            pool.submit(process_candidat, candidat, args, out_dir, pivot_dir): candidat
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
