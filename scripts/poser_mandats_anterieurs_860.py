#!/usr/bin/env python3
"""
poser_mandats_anterieurs_860.py — Repose `mandats_anterieurs` sur les profils de
candidats déclarés déjà écrits, depuis la table relue (#860).

Pourquoi une reprise, et pas l'attente d'un run
----------------------------------------------
#861 a livré la table relue (`raw_data/mandats_anterieurs.json`) et le champ
dérivé qui la porte, posé par `appliquer_mandats_anterieurs()` **à chaque
écriture de profil**. Mais aucun run n'a régénéré les profils depuis la fusion :
mesuré le 12/09/2026, le champ est absent des **32** profils de candidats
déclarés — pas même en `null` + `non_relu`.

L'interface, elle, le lit déjà : `scripts/couverture-corpus.mjs` calcule au build
la ligne « Mandat antérieur à la publication des données de l'Assemblée
nationale » de l'accueil en filtrant `mandats_anterieurs` non vide. Le champ
absent, la liste est vide et le bloc entier disparaît — un silence qui se lit
comme « aucun candidat n'a de mandat antérieur », quand la table en nomme cinq.

Attendre le prochain run complet serait attendre des heures de collecte pour un
champ qui n'en demande aucune : `appliquer_mandats_anterieurs()` est une
fonction **pure** — un profil, une table commitée, rien d'autre. D'où cette
reprise nommée, sur le modèle de `purger_textes_portes_roster_747.py`.

Ce que la reprise touche, et ce qu'elle ne touche pas
----------------------------------------------------
- **Le pivot seul.** `mandats_anterieurs` est un champ dérivé du pivot ; le brut
  ne le porte pas, et `normalize_profil` n'en dérive rien. Rien à faire en amont.
- **Les candidats déclarés seuls.** Sur un membre de roster,
  `appliquer_mandats_anterieurs()` retire les deux clés : il ne publie pas de
  fiche. Les profils `roster_groupe` ne sont donc même pas ouverts.
- **Les deux clés, et rien d'autre.** Vérifié le 12/09/2026 sur une écriture
  d'essai hors dépôt : sur les 32 profils, **zéro** différence en dehors de
  `mandats_anterieurs` et `mandats_anterieurs_non_resolu`. Coût : 16 s,
  +5,4 Kio sur 63,2 Mio.

La reprise n'est pas en concurrence avec le pipeline : le champ étant recalculé
à chaque écriture, le prochain run reposera exactement la même valeur depuis la
même table. Elle avance la date, elle ne crée pas un second chemin.

`--verifier` est le mode du test : il échoue s'il reste un profil de candidat
déclaré sans le champ.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "src"))

from json_io import ecrire_profil_json  # noqa: E402
from mandats_anterieurs import (  # noqa: E402
    CHEMIN_TABLE,
    appliquer_mandats_anterieurs,
    charger_table,
)

PROVENANCE_PUBLIEE = "candidat_declare"
# Le champ, c'est CETTE clé. `mandats_anterieurs_non_resolu` ne l'accompagne que
# sur un profil non relu : compter son absence comme un manque ferait échouer la
# vérification sur les cinq profils justement relus.
CLE = "mandats_anterieurs"


def _profils_publies(racine: Path) -> list[Path]:
    """Les profils qui publient une fiche, dans l'ordre du disque.

    Les deux populations partagent un répertoire et un motif de nom (#630) :
    c'est `meta.provenance` qui les sépare, et rien d'autre.
    """
    chemins = []
    for chemin in sorted((racine / "pivot_data" / "profiles").glob("*.pivot.json")):
        profil = json.loads(chemin.read_text(encoding="utf-8"))
        if (profil.get("meta") or {}).get("provenance") == PROVENANCE_PUBLIEE:
            chemins.append(chemin)
    return chemins


def poser(racine: Path, ecrire: bool) -> dict[str, Any]:
    """Repose le champ sur chaque profil publié ; rend le compte par état."""
    table = charger_table(racine / CHEMIN_TABLE)
    rapport = {"profils": 0, "relus": 0, "non_relus": 0, "manquants": 0, "lignes": 0}

    for chemin in _profils_publies(racine):
        profil = json.loads(chemin.read_text(encoding="utf-8"))
        rapport["profils"] += 1
        if CLE not in profil:
            rapport["manquants"] += 1

        appliquer_mandats_anterieurs(profil, table)

        valeur = profil.get(CLE)
        if isinstance(valeur, list) and valeur:
            rapport["relus"] += 1
            rapport["lignes"] += len(valeur)
        else:
            rapport["non_relus"] += 1

        if ecrire:
            ecrire_profil_json(chemin, profil)

    return rapport


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--racine", type=Path, default=RACINE,
                        help="racine du dépôt (défaut : celle du script)")
    parser.add_argument("--dry-run", action="store_true",
                        help="compte sans écrire")
    parser.add_argument("--verifier", action="store_true",
                        help="échoue s'il reste un profil publié sans le champ — le mode du test")
    args = parser.parse_args()

    ecrire = not (args.dry_run or args.verifier)
    rapport = poser(args.racine, ecrire=ecrire)

    print(f"  candidats déclarés : {rapport['profils']}")
    print(f"  relus              : {rapport['relus']} ({rapport['lignes']} ligne(s) de mandat)")
    print(f"  non relus          : {rapport['non_relus']} (`null` + motif `non_relu`)")

    if args.verifier:
        if rapport["manquants"]:
            print(f"✗ {rapport['manquants']} profil(s) de candidat déclaré sans "
                  "`mandats_anterieurs` : ni la liste relue, ni le motif (#860).")
            return 1
        print("✓ Tout profil de candidat déclaré porte `mandats_anterieurs` — "
              "une liste s'il est relu, `null` et son motif sinon.")
        return 0

    if ecrire:
        print(f"✓ Champ reposé sur {rapport['profils']} profil(s) "
              f"({rapport['manquants']} ne le portaient pas).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
