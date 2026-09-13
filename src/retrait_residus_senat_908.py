#!/usr/bin/env python3
"""
retrait_residus_senat_908.py — Le dernier reste de Regards Citoyens (#908).

Ce que ce script clôt
---------------------
#890 a retiré le marqueur `nosdeputes` / `nossenateurs` des profils de
**député**, et s'est arrêté aux deux profils qui touchent le Sénat :
`bruno-retailleau` et `jean-luc-melenchon`. La raison était juste — leur
marqueur couvrait alors une carrière sénatoriale que rien d'autre ne portait, et
le retirer aurait publié un trou (§2 règle 5).

#885 a branché `data.senat.fr`. La carrière est publiée, datée, sourcée : 133
appartenances sur ces deux profils. La condition que #890 posait est remplie, et
ce script en tire la conséquence.

Ce qu'il retire, aux deux couches
----------------------------------
1. **Les appartenances héritées qu'un organe sénatorial remplace.**
   `retrait_heritage_senat.APPARIEMENTS_HERITES` les nomme une par une, et le
   retrait exige que le remplaçant soit **effectivement publié** sur le profil.
   Le pivot et le brut sont traités séparément, chacun contre sa propre source
   de remplaçants : `audit_collecte_vs_publie` les compare, seuil 0, et retirer
   d'un seul côté bloque le commit (#729).

2. **Le marqueur lui-même** — les entrées `sources[]` au pivot, la clé
   `meta.synchro_sources.nosdeputes` au brut — mais **seulement une fois qu'il
   ne couvre plus rien**. C'est la garde centrale de ce script : tant qu'une
   appartenance héritée subsiste sur le profil, l'attribution ODbL lui reste due
   (§2 règle 2, AGENTS.md §7), et le marqueur reste. La mécanique du retrait est
   celle de #890, réutilisée telle quelle plutôt que réécrite.

`meta.licence_donnees` est **recomposé**, jamais réécrit : c'est un champ dérivé
et `licences.appliquer_licence_donnees` en est la seule fabrique (§7, #909).

Ce qu'il ne touche pas
----------------------
Les **agrégats** — fiches de groupe, de lignée, de parti, de gouvernement. Ils
se recomposent au run suivant à partir des profils, et les réécrire ici ferait
de ce script une seconde fabrique. Même partage que #890, qui n'a touché que les
profils : `docs/decisions/retrait-marqueur-regards-citoyens-deputes-890.md`.

Les **phrases** de `couverture[].preuve` qui nomment la source : elles sont
dérivées par `couverture_profil.deriver` et se recomposent de la même façon. Une
donnée résiduelle et une phrase qui la décrit ne se retirent pas par le même
geste, et les confondre a déjà coûté un lot.

Usage :
    python3 src/retrait_residus_senat_908.py --dry-run
    python3 src/retrait_residus_senat_908.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from json_io import ecrire_profil_json  # noqa: E402
from purge_marqueur_regards_citoyens import (  # noqa: E402
    TYPES_RETIRES,
    purger_brut,
    purger_pivot,
)
from retrait_heritage_senat import (  # noqa: E402
    mandats_apparies_remplaces,
    mandats_bruts_apparies_remplaces,
)

DEFAULT_PIVOT_DIR = Path("pivot_data/profiles")
DEFAULT_RAW_DIR = Path("raw_data/profiles")
SUFFIXE_PIVOT = ".pivot.json"


def porte_le_marqueur(profil: dict[str, Any]) -> bool:
    """True si `sources[]` déclare encore une provenance Regards Citoyens."""
    return any(isinstance(s, dict) and s.get("type") in TYPES_RETIRES
               for s in (profil.get("sources") or []))


def appartenances_heritees_restantes(profil: dict[str, Any]) -> list[dict[str, Any]]:
    """Les appartenances **non estampillées** encore publiées sur ce profil.

    C'est la mesure qui autorise — ou refuse — le retrait du marqueur. Elle
    porte sur `mandats[]` seulement : les votes, interventions et amendements de
    ces deux profils ne portent aucune trace de Regards Citoyens, mesuré le
    13/09/2026 par un parcours récursif des deux couches, clés de dict comprises.
    """
    return [m for m in (profil.get("mandats") or [])
            if isinstance(m, dict) and not m.get("categorie_source")]


def traiter(
    slug: str,
    pivot: dict[str, Any],
    brut: Optional[dict[str, Any]],
) -> dict[str, Any]:
    """Applique les deux retraits sur un profil. Rend le compte rendu."""
    rendu: dict[str, Any] = {
        "slug": slug,
        "mandats_pivot": 0,
        "mandats_brut": 0,
        "marqueur_retire": False,
        "marqueur_retenu_par": [],
        "licence_avant": None,
        "licence_apres": None,
    }

    remplaces = mandats_apparies_remplaces(pivot)
    if remplaces:
        pivot["mandats"] = [m for m in pivot["mandats"] if m not in remplaces]
        rendu["mandats_pivot"] = len(remplaces)

    if brut is not None:
        remplaces_bruts = mandats_bruts_apparies_remplaces(brut)
        if remplaces_bruts:
            brut["mandats"] = [m for m in brut["mandats"] if m not in remplaces_bruts]
            rendu["mandats_brut"] = len(remplaces_bruts)

    # La garde : le marqueur ne part que s'il ne couvre plus rien.
    restantes = appartenances_heritees_restantes(pivot)
    if restantes:
        rendu["marqueur_retenu_par"] = [m.get("label") for m in restantes]
        return rendu

    if porte_le_marqueur(pivot):
        _, avant, apres = purger_pivot(pivot)
        rendu["marqueur_retire"] = True
        rendu["licence_avant"], rendu["licence_apres"] = avant, apres
    if brut is not None and purger_brut(brut):
        rendu["marqueur_retire"] = True
    return rendu


def _charger(chemin: Path) -> Optional[dict[str, Any]]:
    if not chemin.exists():
        return None
    import json
    return json.loads(chemin.read_text(encoding="utf-8"))


def retirer(
    pivot_dir: Path = DEFAULT_PIVOT_DIR,
    raw_dir: Path = DEFAULT_RAW_DIR,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    """Parcourt les profils, applique, écrit. Rend un compte rendu par profil touché."""
    rendus: list[dict[str, Any]] = []
    for chemin_pivot in sorted(pivot_dir.glob(f"*{SUFFIXE_PIVOT}")):
        slug = chemin_pivot.name[: -len(SUFFIXE_PIVOT)]
        pivot = _charger(chemin_pivot)
        if pivot is None:
            continue
        chemin_brut = raw_dir / f"{slug}.json"
        brut = _charger(chemin_brut)

        rendu = traiter(slug, pivot, brut)
        if not (rendu["mandats_pivot"] or rendu["mandats_brut"] or rendu["marqueur_retire"]):
            continue
        rendus.append(rendu)
        if dry_run:
            continue
        if rendu["mandats_pivot"] or rendu["marqueur_retire"]:
            ecrire_profil_json(chemin_pivot, pivot)
        if brut is not None and (rendu["mandats_brut"] or rendu["marqueur_retire"]):
            ecrire_profil_json(chemin_brut, brut)
    return rendus


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pivot-dir", type=Path, default=DEFAULT_PIVOT_DIR)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--dry-run", action="store_true",
                        help="mesure et affiche, n'écrit rien")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    rendus = retirer(args.pivot_dir, args.raw_dir, args.dry_run)
    if not rendus:
        print("Aucun profil à traiter — rien d'hérité n'a de remplaçant publié.")
        return 0
    for r in rendus:
        print(f"\n{r['slug']}")
        print(f"  appartenances retirées : {r['mandats_pivot']} au pivot, "
              f"{r['mandats_brut']} au brut")
        if r["marqueur_retire"]:
            print(f"  marqueur retiré — licence : {r['licence_avant']!r}")
            print(f"                       → {r['licence_apres']!r}")
        elif r["marqueur_retenu_par"]:
            print(f"  marqueur RETENU par {len(r['marqueur_retenu_par'])} appartenance(s) "
                  "sans remplaçant :")
            for label in r["marqueur_retenu_par"]:
                print(f"      {label!r}")
    if args.dry_run:
        print("\n(--dry-run : rien n'a été écrit)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
