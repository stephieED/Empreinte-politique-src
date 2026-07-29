#!/usr/bin/env python3
"""
generate_all_profiles.py

Récupère les données et génère le CV (JSON + HTML) de chaque candidat de
candidats.json qui possède un "slug" (identifiant NosDéputés.fr / NosSénateurs.fr).
Les candidats sans slug (non référencés dans ces bases) sont simplement signalés.

Usage :
    python generate_all_profiles.py
    python generate_all_profiles.py --only jean-luc-melenchon
    python generate_all_profiles.py --max-pages 5      # recherche d'interventions plus rapide
    python generate_all_profiles.py --skip-existing    # ne pas relancer un profil déjà généré
"""

import argparse
import json
import time
from pathlib import Path
from typing import Any, Optional

from candidate_profile import build_profile
from render_profile import render_html

CHAMBRES = ["deputes", "senateurs"]


def load_candidats(path: str) -> list[dict[str, Any]]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("candidats", [])


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
    parser.add_argument("--candidats", default="candidats.json", help="Fichier JSON listant les candidats (défaut: candidats.json)")
    parser.add_argument("--only", help="Ne traiter qu'un seul candidat (par slug), utile pour tester")
    parser.add_argument("--max-pages", type=int, default=10, help="Pages max. de recherche d'interventions par candidat (défaut: 10)")
    parser.add_argument("--skip-existing", action="store_true", help="Ne pas régénérer un profil dont le fichier JSON existe déjà")
    args = parser.parse_args()

    candidats = load_candidats(args.candidats)
    if args.only:
        candidats = [c for c in candidats if c.get("slug") == args.only]
        if not candidats:
            print(f"Aucun candidat avec le slug '{args.only}' dans {args.candidats}.")
            return

    resultats: list[dict[str, Any]] = []
    for candidat in candidats:
        slug = candidat.get("slug")
        nom = candidat.get("nom")

        if not slug:
            print(f"— {nom} : pas de slug renseigné (candidat non référencé sur NosDéputés/NosSénateurs), ignoré.")
            resultats.append({"nom": nom, "slug": None, "statut": "sans_slug"})
            continue

        json_path = Path(f"{slug}.json")
        if args.skip_existing and json_path.exists():
            print(f"— {nom} ({slug}) : profil déjà présent, ignoré (--skip-existing).")
            resultats.append({"nom": nom, "slug": slug, "statut": "deja_present"})
            continue

        print(f"\n=== {nom} ({slug}) ===")
        profile, chambre = build_profile_any_chambre(slug, args.max_pages)
        if profile is None:
            print(f"  [!] Aucune identité trouvée pour {slug} (ni député, ni sénateur).")
            resultats.append({"nom": nom, "slug": slug, "statut": "introuvable"})
            continue

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(profile, f, ensure_ascii=False, indent=2)

        html_path = Path(f"{slug}.html")
        html_path.write_text(render_html(profile), encoding="utf-8")

        nb_interventions = len(profile.get("interventions") or [])
        print(f"  ✓ {chambre} — {json_path} + {html_path} ({nb_interventions} interventions)")
        resultats.append({
            "nom": nom,
            "slug": slug,
            "statut": "ok",
            "chambre": chambre,
            "nb_interventions": nb_interventions,
        })

        time.sleep(0.5)  # on reste courtois avec l'API publique entre deux candidats

    print("\n=== Résumé ===")
    for r in resultats:
        extra = f" ({r.get('nb_interventions')} interventions, {r.get('chambre')})" if r["statut"] == "ok" else ""
        print(f"  - {r['nom']}: {r['statut']}{extra}")


if __name__ == "__main__":
    main()
