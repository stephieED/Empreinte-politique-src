#!/usr/bin/env python3
"""
generate_all_profiles.py

Récupère les données et génère le CV (JSON + HTML) de chaque candidat de
data/candidats.json qui possède un "slug" (identifiant NosDéputés.fr /
NosSénateurs.fr) et/ou un mandat de député européen (recherché par nom via
candidate_profile_ue.py, cf. Open Data Portal du Parlement européen). Les
candidats sans aucune de ces deux sources sont simplement signalés, sans erreur.

Les fichiers générés sont écrits dans data/profiles/<slug>.json et
data/profiles/<slug>.html. Le volet européen, quand il existe, est fusionné
dans le même profil sous la clé "mandat_europeen" (pour un candidat sans
mandat français, ex. Jordan Bardella, un profil minimal est tout de même créé
à partir de data/candidats.json + du mandat européen).

Fusion additive (comportement par défaut) : si un fichier <slug>.json (ou
<slug>.pivot.json) existe déjà, les nouvelles données collectées sont
fusionnées avec celles déjà présentes plutôt que de les écraser — chaque
liste (votes, mandats, dossiers législatifs, interventions...) est fusionnée
par clé d'unicité : les entrées déjà connues sont conservées telles quelles,
seules les entrées réellement nouvelles sont ajoutées. Cela évite que des
données varient ou disparaissent d'une régénération à l'autre à cause d'un
aléa transitoire des API publiques (pagination, requête ponctuelle en échec...).
Utiliser --no-merge pour revenir à un écrasement complet. Voir merge_profile.py.

Avec --pivot, un fichier supplémentaire data/profiles/<slug>.pivot.json
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
from render_profile import render_html
from text_utils import slugify

# Chemins par défaut, relatifs à la racine du dépôt (voir README pour l'arborescence).
DEFAULT_CANDIDATS_PATH = "data/candidats.json"
DEFAULT_PROFILES_DIR = Path("data/profiles")
DEFAULT_CHECKPOINT_PATH = "data/profiles/.generation_checkpoint.json"

CHAMBRES = ["deputes", "senateurs"]

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


def build_profile_any_chambre(slug: str, max_pages: int) -> tuple[Optional[dict], Optional[str]]:
    """Essaie 'deputes' puis 'senateurs' et renvoie le premier profil avec une identité exploitable."""
    for chambre in CHAMBRES:
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



def process_candidat(
    candidat: dict[str, Any],
    args: argparse.Namespace,
    out_dir: Path,
) -> dict[str, Any]:
    """Traite un candidat : collecte les données FR et UE en parallèle (niveau 1),
    écrit les fichiers JSON/HTML (et pivot si demandé), et renvoie un dict de résultat.

    Conçu pour être appelé depuis un ThreadPoolExecutor (niveau 2) : ne modifie
    aucun état partagé en dehors des fichiers de sortie individuels (thread-safe).
    """
    slug = candidat.get("slug")
    nom = candidat.get("nom")
    effective_slug = slug or _slugify(nom)
    json_path = out_dir / f"{effective_slug}.json"

    if args.skip_existing and json_path.exists():
        _tprint(f"— {nom} ({effective_slug}) : profil déjà présent, ignoré (--skip-existing).")
        return {"nom": nom, "slug": effective_slug, "statut": "deja_present"}

    _tprint(f"\n=== {nom} ({effective_slug}) ===")

    # --- Niveau 1 : appels FR et UE en parallèle ---
    profile: Optional[dict] = None
    chambre: Optional[str] = None
    mandat_ue: Optional[dict] = None

    def _fetch_fr() -> tuple[Optional[dict], Optional[str]]:
        if not slug:
            _tprint(f"  — {nom} : pas de slug renseigné (candidat non référencé sur NosDéputés/NosSénateurs).")
            return None, None
        result = build_profile_any_chambre(slug, args.max_pages)
        if result[0] is None:
            _tprint(f"  [!] Aucune identité trouvée pour {slug} (ni député, ni sénateur).")
        return result

    def _fetch_ue() -> Optional[dict]:
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
        return {"nom": nom, "slug": effective_slug, "statut": "introuvable"}
    if profile is None:
        # Candidat sans mandat français connu, mais avec un mandat européen
        # (ex. Jordan Bardella) : on crée un profil minimal à partir de
        # data/candidats.json plutôt que de ne rien produire.
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

    html_path = out_dir / f"{effective_slug}.html"
    html_path.write_text(render_html(profile), encoding="utf-8")

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
            pivot_path = out_dir / f"{effective_slug}.pivot.json"
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
    _tprint(f"  ✓ {chambre or 'sans chambre FR'} — {json_path} + {html_path} ({nb_interventions} interventions{extra})")

    time.sleep(0.5)  # on reste courtois avec l'API publique entre deux candidats

    return {
        "nom": nom,
        "slug": effective_slug,
        "statut": "ok",
        "chambre": chambre,
        "nb_interventions": nb_interventions,
        "nb_mandats_ue": nb_mandats_ue,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--candidats", default=DEFAULT_CANDIDATS_PATH, help=f"Fichier JSON listant les candidats (défaut: {DEFAULT_CANDIDATS_PATH})")
    parser.add_argument("--only", help="Ne traiter qu'un seul candidat (par slug), utile pour tester")
    parser.add_argument("--max-pages", type=int, default=10, help="Pages max. de recherche d'interventions par candidat (défaut: 10)")
    parser.add_argument("--skip-existing", action="store_true", help="Ne pas régénérer un profil dont le fichier JSON existe déjà")
    parser.add_argument("--skip-ue", action="store_true", help="Ne pas interroger l'Open Data Portal du Parlement européen (mandat européen)")
    parser.add_argument("--out-dir", default=str(DEFAULT_PROFILES_DIR), help=f"Dossier de sortie des profils JSON/HTML (défaut: {DEFAULT_PROFILES_DIR})")
    parser.add_argument("--pivot", action="store_true", help="Écrire aussi <slug>.pivot.json au format schéma pivot v1 (en plus du JSON brut)")
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

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

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
            pool.submit(process_candidat, candidat, args, out_dir): candidat
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
                resultat = {"nom": nom, "slug": slug, "statut": "erreur"}
            resultats.append(resultat)
            if not args.no_checkpoint:
                _save_checkpoint(checkpoint_path, resultats)
            _tprint(f"  [point de sauvegarde {i}/{total}] {resultat.get('nom')} : {resultat.get('statut')}")

    print("\n=== Résumé ===")
    for r in sorted(resultats, key=lambda x: x.get("nom") or ""):
        extra = f" ({r.get('nb_interventions')} interventions, {r.get('chambre')})" if r["statut"] == "ok" else ""
        print(f"  - {r['nom']}: {r['statut']}{extra}")


if __name__ == "__main__":
    main()
