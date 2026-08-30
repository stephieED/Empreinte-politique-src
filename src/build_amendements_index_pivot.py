#!/usr/bin/env python3
"""build_amendements_index_pivot.py — Construit `pivot_data/amendements/` (#431).

À ne pas confondre avec `build_amendements_index.py`, qui construit l'index
**brut** des archives AN pour le job CI `extract-amendements-an`, ni avec
`build_amendements_index_figees.py`, qui matérialise les législatures closes
sous `raw_data/amendements_an_figes/`. Celui-ci produit la couche **pivot** :
la liste dédupliquée que les profils publiés référencent.

Un amendement est identique pour tous ses signataires, et sa liste de
cosignataires était recopiée dans le profil de chacun d'eux : 77,7 M entrées de
cosignatures pour 4,96 M distinctes, soit 1 083,9 Mo des 1 342,4 Mo que pèse
`amendements[]` dans les profils pivot. Cet index stocke chaque amendement une
seule fois, et les profils n'en gardent que le mapping
`{amendement_id, role_signataire}`.

Écrit **un fichier par législature**, plus un fichier compagnon de cosignatures :

    pivot_data/amendements/17.json
    pivot_data/amendements/17.cosignatures.json

Un fichier global unique pèserait 128,8 Mo, au-delà de la limite GitHub de
100 Mo par blob — voir docs/decisions/normalisation-amendements.md.

Contrairement à l'index des scrutins, la construction n'est **pas** une passe de
corpus : la clé d'un amendement est son `uid` AN, porté par l'enregistrement
lui-même, et sa législature se lit dans cet `uid`. Rien n'a besoin d'être résolu
par jointure — d'où une seule reconstruction par run, après la passe pivot.

Usage :
    python3 src/build_amendements_index_pivot.py
    python3 src/build_amendements_index_pivot.py --profils-dir raw_data/profiles --out pivot_data/amendements
    python3 src/build_amendements_index_pivot.py --no-merge     # reconstruction complète
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from amendements_index import (  # noqa: E402
    DEFAULT_AMENDEMENTS_DIR,
    rafraichir,
)

DEFAUT_PROFILS_DIR = Path("raw_data") / "profiles"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--profils-dir", default=str(DEFAUT_PROFILS_DIR),
                        help=f"Profils bruts d'où lire les amendements (défaut : {DEFAUT_PROFILS_DIR}). "
                             "Les profils bruts gardent l'enregistrement complet de l'amendement, "
                             "les pivots n'en ont plus que le mapping.")
    parser.add_argument("--out", default=str(DEFAULT_AMENDEMENTS_DIR),
                        help=f"Dossier d'index à écrire (défaut : {DEFAULT_AMENDEMENTS_DIR}).")
    parser.add_argument("--no-merge", action="store_true",
                        help="Reconstruction complète au lieu d'une fusion additive avec "
                             "l'index existant. À réserver à un corpus COMPLET : sur une "
                             "tranche, les amendements des profils non retraités disparaîtraient "
                             "et leurs mappings pointeraient dans le vide.")
    args = parser.parse_args(argv)

    index = rafraichir(
        Path(args.profils_dir),
        Path(args.out),
        fusionner=not args.no_merge,
        genere_le=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    )

    print(f"  ✓ {len(index)} amendement(s) distinct(s) → {args.out}")
    for legislature in index.legislatures():
        n = len(index.ids_de_legislature(legislature))
        print(f"      législature {legislature} : {n} amendement(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
