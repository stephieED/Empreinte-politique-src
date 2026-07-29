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

Avec --pivot, un fichier supplémentaire data/profiles/<slug>.pivot.json
est généré au format schéma pivot v1 (commun à toutes les sources). Le volet
européen, s'il existe, est normalisé et intégré au pivot.

Usage (depuis la racine du dépôt) :
    python src/generate_all_profiles.py
    python src/generate_all_profiles.py --only jean-luc-melenchon
    python src/generate_all_profiles.py --max-pages 5      # recherche d'interventions plus rapide
    python src/generate_all_profiles.py --skip-existing    # ne pas relancer un profil déjà généré
    python src/generate_all_profiles.py --skip-ue          # ne pas interroger l'API du Parlement européen
    python src/generate_all_profiles.py --pivot            # aussi écrire <slug>.pivot.json
"""

import argparse
import json
import re
import time
import unicodedata
from pathlib import Path
from typing import Any, Optional

from candidate_profile import build_profile
from candidate_profile_ue import build_profile_ue
from normalize_europarl import normalize_europarl
from normalize_nosdeputes import normalize_nosdeputes
from render_profile import render_html

# Chemins par défaut, relatifs à la racine du dépôt (voir README pour l'arborescence).
DEFAULT_CANDIDATS_PATH = "data/candidats.json"
DEFAULT_PROFILES_DIR = Path("data/profiles")

CHAMBRES = ["deputes", "senateurs"]


def load_candidats(path: str) -> list[dict[str, Any]]:
    """Charge la liste des candidats depuis le fichier JSON source (clé "candidats")."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("candidats", [])


def _slugify(nom: str) -> str:
    """Dérive un slug ("jordan-bardella") à partir du nom complet d'un candidat
    n'ayant pas de slug NosDéputés.fr/NosSénateurs.fr, pour pouvoir tout de même
    nommer son fichier de profil."""
    decomposed = unicodedata.normalize("NFKD", nom)
    ascii_only = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", ascii_only.lower())).strip("-")


def build_profile_any_chambre(slug: str, max_pages: int) -> tuple[Optional[dict], Optional[str]]:
    """Essaie 'deputes' puis 'senateurs' et renvoie le premier profil avec une identité exploitable."""
    for chambre in CHAMBRES:
        try:
            profile = build_profile(chambre, slug, intervention_max_pages=max_pages)
        except Exception as exc:
            print(f"  [!] Échec ({chambre}) pour {slug} : {exc}")
            continue
        if profile.get("identite"):
            return profile, chambre
    return None, None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--candidats", default=DEFAULT_CANDIDATS_PATH, help=f"Fichier JSON listant les candidats (défaut: {DEFAULT_CANDIDATS_PATH})")
    parser.add_argument("--only", help="Ne traiter qu'un seul candidat (par slug), utile pour tester")
    parser.add_argument("--max-pages", type=int, default=10, help="Pages max. de recherche d'interventions par candidat (défaut: 10)")
    parser.add_argument("--skip-existing", action="store_true", help="Ne pas régénérer un profil dont le fichier JSON existe déjà")
    parser.add_argument("--skip-ue", action="store_true", help="Ne pas interroger l'Open Data Portal du Parlement européen (mandat européen)")
    parser.add_argument("--out-dir", default=str(DEFAULT_PROFILES_DIR), help=f"Dossier de sortie des profils JSON/HTML (défaut: {DEFAULT_PROFILES_DIR})")
    parser.add_argument("--pivot", action="store_true", help="Écrire aussi <slug>.pivot.json au format schéma pivot v1 (en plus du JSON brut)")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    candidats = load_candidats(args.candidats)
    if args.only:
        candidats = [c for c in candidats if (c.get("slug") or _slugify(c.get("nom") or "")) == args.only]
        if not candidats:
            print(f"Aucun candidat avec le slug '{args.only}' dans {args.candidats}.")
            return

    resultats: list[dict[str, Any]] = []
    for candidat in candidats:
        slug = candidat.get("slug")
        nom = candidat.get("nom")

        effective_slug = slug or _slugify(nom)
        json_path = out_dir / f"{effective_slug}.json"
        if args.skip_existing and json_path.exists():
            print(f"— {nom} ({effective_slug}) : profil déjà présent, ignoré (--skip-existing).")
            resultats.append({"nom": nom, "slug": effective_slug, "statut": "deja_present"})
            continue

        print(f"\n=== {nom} ({effective_slug}) ===")

        profile, chambre = (None, None)
        if slug:
            profile, chambre = build_profile_any_chambre(slug, args.max_pages)
            if profile is None:
                print(f"  [!] Aucune identité trouvée pour {slug} (ni député, ni sénateur).")
        else:
            print("  — pas de slug renseigné (candidat non référencé sur NosDéputés/NosSénateurs).")

        mandat_ue = None
        if not args.skip_ue:
            try:
                mandat_ue = build_profile_ue(nom)
            except Exception as exc:
                print(f"  [!] Recherche du mandat européen impossible pour {nom} : {exc}")
            time.sleep(0.3)

        if profile is None and mandat_ue is None:
            resultats.append({"nom": nom, "slug": slug, "statut": "introuvable"})
            continue

        if profile is None:
            # Candidat sans mandat français connu, mais avec un mandat européen
            # (ex. Jordan Bardella) : on crée un profil minimal à partir de
            # data/candidats.json plutôt que de ne rien produire.
            profile = {
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

        if mandat_ue is not None:
            profile["mandat_europeen"] = mandat_ue

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
                with open(pivot_path, "w", encoding="utf-8") as f:
                    json.dump(pivot_profile, f, ensure_ascii=False, indent=2)
                print(f"  ✓ pivot → {pivot_path}")

        nb_interventions = len(profile.get("interventions") or [])
        nb_mandats_ue = len((mandat_ue or {}).get("mandats_europeens") or [])
        extra = f", {nb_mandats_ue} mandats UE" if mandat_ue else ""
        print(f"  ✓ {chambre or 'sans chambre FR'} — {json_path} + {html_path} ({nb_interventions} interventions{extra})")
        resultats.append({
            "nom": nom,
            "slug": effective_slug,
            "statut": "ok",
            "chambre": chambre,
            "nb_interventions": nb_interventions,
            "nb_mandats_ue": nb_mandats_ue,
        })

        time.sleep(0.5)  # on reste courtois avec l'API publique entre deux candidats

    print("\n=== Résumé ===")
    for r in resultats:
        extra = f" ({r.get('nb_interventions')} interventions, {r.get('chambre')})" if r["statut"] == "ok" else ""
        print(f"  - {r['nom']}: {r['statut']}{extra}")


if __name__ == "__main__":
    main()
