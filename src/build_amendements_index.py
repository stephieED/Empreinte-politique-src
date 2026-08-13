#!/usr/bin/env python3
"""
build_amendements_index.py

Point d'entrée dédié au job CI `extract-amendements-an` (issue #251,
sous-issue 3/6 du plan d'architecture #248) : construit sans condition les
index amendements des 3 législatures de `AN_AMENDEMENTS_PATH`
(candidate_profile.py), indépendamment de toute liste de candidats — à la
différence de `extract-an`/`extract-roster-groupes`, qui ne déclenchent
cette construction que paresseusement, au niveau candidat.

Appelle `_download_and_build_amendement_index` (#250) pour chaque
législature, dans une boucle isolée par try/except — un échec définitif sur
une législature (ex. archive AN indisponible) n'empêche pas la construction
des autres, même pattern d'isolation que `fetch_amendements_officiels`
(#241/#242). Le job CI qui invoque ce script est `continue-on-error: true` ;
ce script reflète malgré tout un échec partiel via son code de sortie (1 si
au moins une législature a échoué), pour rester diagnosticable manuellement
via les logs du step — le `continue-on-error` du job est ce qui évite que
cela bloque le reste du pipeline, pas ce script.

Usage (depuis la racine du dépôt) :
    python3 src/build_amendements_index.py
"""

import sys

from candidate_profile import (
    AN_AMENDEMENTS_PATH,
    AmendementsIndexError,
    _download_and_build_amendement_index,
)


def build_all_amendements_index() -> bool:
    """Construit sans condition l'index amendements de chaque législature de
    `AN_AMENDEMENTS_PATH`. Retourne True si toutes ont réussi, False si au
    moins une a échoué — un échec est isolé par législature (try/except) et
    n'interrompt jamais la boucle, ni ne lève d'exception non gérée."""
    ok = True
    for legislature in AN_AMENDEMENTS_PATH:
        print(f"-> Construction de l'index amendements, législature {legislature}")
        try:
            index = _download_and_build_amendement_index(legislature)
        except AmendementsIndexError as exc:
            print(f"  [!] Échec pour la législature {legislature} : {exc}", file=sys.stderr)
            ok = False
            continue
        print(f"  -> {len(index)} acteur(s) indexé(s) pour la législature {legislature}")
    return ok


def main() -> int:
    return 0 if build_all_amendements_index() else 1


if __name__ == "__main__":
    sys.exit(main())
