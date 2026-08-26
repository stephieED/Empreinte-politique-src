#!/usr/bin/env python3
"""
build_correspondance_acteurs_an.py — Régénère
`raw_data/correspondance_acteurs_an.json` depuis les profils publiés et le
référentiel AMO30 (#525).

Script de maintenance, pas une étape du pipeline : la table est un artefact
**committé et relu**, on la reconstruit quand le corpus bouge, jamais à chaque
run (c'est précisément ce que le lot 2 remplace).

## Ce qu'il fait, et ce qu'il refuse de faire

Pour chaque `pivot_data/profiles/<slug>.pivot.json` :

1. **une entrée existante est reconduite telle quelle** — c'est le travail
   relu, y compris `motif`, `preuve` et `verifie_le`. Le script vérifie
   seulement que son `acteur_ref` existe toujours dans AMO30, et **signale**
   un état civil qui a changé depuis la vérification (le cas « un député
   change de nom en cours de législature ») ;
2. sinon, il tente la correspondance par nom
   (`candidate_profile._resolve_acteur_ref_par_slug`, qui refuse l'homonymie) ;
   la preuve est la fiche AN de l'acteur ;
3. sinon, il **n'écrit rien pour ce slug** : il le nomme sur stderr et sort en
   code 1.

Le point 3 est le cœur du lot : `identite.source_url` du profil publié porte
souvent le `PA######` et il serait tentant de s'en servir pour combler
automatiquement — mais une correspondance non arbitrée recopiée sans motif ni
preuve relue n'est pas un artefact vérifiable, c'est la même heuristique
déplacée d'un cran. Le résidu se tranche à la main, une fois, et il est
petit : **10 slugs sur 476**.

## Usage

    python src/build_correspondance_acteurs_an.py            # écrit la table
    python src/build_correspondance_acteurs_an.py --verifier # ne réécrit rien

Le référentiel AMO30 est téléchargé (ou relu depuis `.cache/`) par
`candidate_profile` : ce script sort donc sur le réseau, comme tous les
scripts de collecte, et n'est jamais appelé depuis un test.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
import argparse
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

import candidate_profile as cp  # noqa: E402
from correspondance_acteurs_an import (  # noqa: E402
    CHEMIN_PAR_DEFAUT,
    SCHEMA_VERSION,
    charger_correspondance,
)

SUFFIXE_PIVOT = ".pivot.json"


def _slugs_publies(profiles_dir: Path) -> list[str]:
    """Slugs publiés, dotfiles exclus.

    `Path.glob` renvoie les fichiers cachés, contrairement au module `glob` :
    c'est ce qui a fait lire `.generation_checkpoint.json` comme un profil et
    bloqué un commit de 476 profils corrects (#518).
    """
    return sorted(
        chemin.name[: -len(SUFFIXE_PIVOT)]
        for chemin in profiles_dir.glob(f"*{SUFFIXE_PIVOT}")
        if not chemin.name.startswith(".")
    )


def _etat_civil(fiche: dict[str, Any]) -> dict[str, Any]:
    """État civil retenu, réduit aux champs qui identifient une personne."""
    return {
        "civilite": fiche.get("civilite"),
        "prenom": fiche.get("prenom"),
        "nom": fiche.get("nom"),
        "nom_complet": fiche.get("nom_complet"),
        "date_naissance": fiche.get("date_naissance"),
    }


def construire(
    profiles_dir: Path,
    table_existante: dict[str, dict[str, Any]],
    verifie_le: str,
) -> tuple[dict[str, dict[str, Any]], list[str], list[str]]:
    """Renvoie `(correspondances, slugs_a_arbitrer, avertissements)`."""
    index = cp._build_acteur_identite_index()
    if not index:
        raise SystemExit(
            "Référentiel AMO30 vide ou indisponible : la table ne sera pas "
            "réécrite sur une source muette (AGENTS.md §2 règle 5)."
        )

    correspondances: dict[str, dict[str, Any]] = {}
    a_arbitrer: list[str] = []
    avertissements: list[str] = []

    for slug in _slugs_publies(profiles_dir):
        existante = table_existante.get(slug)
        if existante is not None:
            acteur_ref = existante["acteur_ref"]
            if acteur_ref is not None:
                fiche = index.get(acteur_ref)
                if fiche is None:
                    avertissements.append(
                        f"{slug} : {acteur_ref} est absent d'AMO30 — entrée conservée, "
                        "à revérifier."
                    )
                else:
                    attendu = existante["etat_civil"].get("nom_complet")
                    if attendu and attendu != fiche.get("nom_complet"):
                        avertissements.append(
                            f"{slug} : l'état civil AN a changé depuis la vérification "
                            f"du {existante['verifie_le']} ({attendu!r} → "
                            f"{fiche.get('nom_complet')!r}). L'`acteur_ref` reste bon — "
                            "un changement de nom ne change pas l'uid — mais le motif "
                            "et la date de vérification sont à reprendre."
                        )
            correspondances[slug] = existante
            continue

        acteur_ref = cp._resolve_acteur_ref_par_slug(slug, utiliser_table=False)
        if acteur_ref is None:
            a_arbitrer.append(slug)
            continue

        correspondances[slug] = {
            "acteur_ref": acteur_ref,
            "etat_civil": _etat_civil(index.get(acteur_ref) or {}),
            "ecart": None,
            "motif": None,
            "preuve": cp._acteur_ref_to_pseudo_url(acteur_ref),
            "verifie_le": verifie_le,
        }

    return correspondances, a_arbitrer, avertissements


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--profiles-dir", type=Path, default=Path("pivot_data/profiles"))
    parser.add_argument("--sortie", type=Path, default=CHEMIN_PAR_DEFAUT)
    parser.add_argument(
        "--verifie-le",
        default=date.today().isoformat(),
        help="Date de vérification estampillée sur les entrées NOUVELLES (ISO).",
    )
    parser.add_argument(
        "--verifier",
        action="store_true",
        help="N'écrit rien ; sort en 1 si la table ne couvre pas le corpus publié.",
    )
    return parser


def main() -> int:
    args = _build_arg_parser().parse_args()

    try:
        table_existante = charger_correspondance(args.sortie)
    except Exception as exc:  # table absente au premier amorçage
        print(f"-> Table existante non chargée ({exc}) : construction à neuf.")
        table_existante = {}

    correspondances, a_arbitrer, avertissements = construire(
        args.profiles_dir, table_existante, args.verifie_le
    )

    for avertissement in avertissements:
        print(f"  [!] {avertissement}", file=sys.stderr)

    hors_an = sorted(s for s, e in correspondances.items() if e["ecart"] == "hors_an")
    print(
        f"-> {len(correspondances)} correspondance(s) ; "
        f"{len(hors_an)} déclarée(s) sans acteur AN ; "
        f"{len(a_arbitrer)} à arbitrer."
    )

    if a_arbitrer:
        print(
            "  [X] Slugs sans correspondance résolue — à arbitrer à la main, avec "
            "leur preuve, avant de réécrire la table :",
            file=sys.stderr,
        )
        for slug in a_arbitrer:
            print(f"      - {slug}", file=sys.stderr)
        return 1

    if args.verifier:
        print("-> Mode --verifier : rien n'a été écrit.")
        return 0

    document = {
        "schema_version": SCHEMA_VERSION,
        "genere_le": datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+0000"),
        "source_referentiel": cp.AN_ACTEURS_HISTORIQUE_ZIP_URL,
        "correspondances": dict(sorted(correspondances.items())),
    }
    args.sortie.parent.mkdir(parents=True, exist_ok=True)
    with open(args.sortie, "w", encoding="utf-8") as f:
        json.dump(document, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"-> Écrit : {args.sortie}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
