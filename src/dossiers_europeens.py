#!/usr/bin/env python3
"""
dossiers_europeens.py — L'index des dossiers du Parlement européen (#901).

Ce que cet index résout
------------------------
Un amendement européen publie son `texte_vise` — `"2021/0136(COD)"` — sur
**100 %** des 7 303 entrées, et l'interface le lit déjà. Mais une référence de
procédure n'est pas un titre : `resolveDossier` la cherche dans l'index
français, ne l'y trouve pas, et la fiche affiche « 590 amendements · **0
dossiers** ». Au mieux, l'écran pourrait rendre le code brut, qui ne dit rien à
un lecteur.

Ce qui manquait n'était donc ni une collecte ni une lecture, mais un
**référentiel** : code de procédure → intitulé. Le dump `ep_dossiers` le porte.

Mesuré le 14/09/2026, contre les références réellement visées par les
amendements des 7 candidats déclarés à mandat européen :

  · 367 références distinctes ;
  · **355 résolues** (96,7 %), avec titre, stade et type de procédure ;
  · couvrant **6 925 amendements sur 7 303** (94,8 %).

Les 12 non résolues sont toutes de 2024-2025 : le dump des dossiers est plus
ancien que celui des amendements. C'est une absence **datée**, pas un trou — et
elle se déclare plutôt que de se combler (§2 règle 5).

Les titres sont en anglais
---------------------------
C'est ce que la source publie, et rien ici ne les traduit : une traduction
automatique d'un intitulé législatif produirait un titre que personne n'a écrit
et qu'aucune source ne confirme (§2 règle 2). L'interface affiche ce que le
Parlement européen a publié.

Le stade est repris de la même table que `textes_portes[]`
-----------------------------------------------------------
`normalize_parltrack_dumps.STADE_UE_PAR_LIBELLE_SOURCE` est la seule fabrique de
cette correspondance (#901, lot du stade). La recopier ici ferait diverger deux
tables le jour où la source ajoute une valeur.

Usage :
    python3 src/dossiers_europeens.py \\
        --profils-dir pivot_data/profiles \\
        --out pivot_data/dossiers_europeens.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Iterable, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from licences import LICENCE_PARLTRACK  # noqa: E402
from normalize_parltrack_dumps import _stade_procedural_ue  # noqa: E402
from parltrack_dumps import ensure_dump, iter_dump_zst  # noqa: E402

#: Le dump que ce module lit. Déjà téléchargé par `extract-parltrack`.
DUMP_DOSSIERS = "ep_dossiers.json.zst"

SCHEMA_VERSION = "dossiers-europeens-v1"
DEFAULT_PROFILS_DIR = Path("pivot_data/profiles")
DEFAULT_SORTIE = Path("pivot_data/dossiers_europeens.json")

#: Préfixe de l'identifiant, pendant de `an:` et de `pe:` pour les scrutins.
PREFIXE_ID = "pe-dossier"


class DumpDossiersIndisponible(RuntimeError):
    """Le dump n'a pas pu être obtenu. Levée, jamais avalée : un index vide se
    lirait comme « aucun dossier européen » (#510)."""


def identifiant(reference: str) -> str:
    """`pe-dossier:2021/0136(COD)` — l'identifiant publié d'un dossier."""
    return f"{PREFIXE_ID}:{reference}"


#: Ce qui, dans `committees[].type`, désigne une commission saisie **au fond**.
#: La source emploie quatre libellés qui le contiennent — « Responsible
#: Committee », « Former Responsible Committee », « Joint Responsible
#: Committee », « Former Joint Committee Responsible » — contre « Committee
#: Opinion » et ses variantes pour une saisine pour avis.
MARQUEUR_AU_FOND = "responsible"

#: Le champ que la source renseigne vraiment. `responsible: true` existe aussi,
#: et c'est un piège : il n'est renseigné que sur **521 des 18 242** entrées
#: (2,9 %), là où `type` l'est sur 97 %. S'y fier aurait rendu une commission
#: au fond pour 1,2 % des dossiers au lieu de 97,7 %.
CHAMP_TYPE = "type"


def _sigles_et_noms(commission: dict[str, Any]) -> list[tuple[str, Optional[str]]]:
    """Les couples `(sigle, nom)` d'une entrée `committees[]`.

    Une saisine **conjointe** porte plusieurs commissions, et la source le dit
    en mettant des **listes** dans `committee` et `committee_full` : 36 des 402
    entrées au fond de notre population. Les aplatir ici plutôt que de publier
    une liste dans un champ scalaire évite à chaque consommateur de gérer les
    deux formes.
    """
    sigles = commission.get("committee")
    noms = commission.get("committee_full")
    if isinstance(sigles, str):
        sigles, noms = [sigles], [noms if isinstance(noms, str) else None]
    if not isinstance(sigles, list):
        return []
    if not isinstance(noms, list):
        noms = [None] * len(sigles)
    couples = []
    for rang, sigle in enumerate(sigles):
        if isinstance(sigle, str) and sigle:
            nom = noms[rang] if rang < len(noms) else None
            couples.append((sigle, nom if isinstance(nom, str) and nom else None))
    return couples


def commissions_au_fond(dossier: dict[str, Any]) -> list[dict[str, Any]]:
    """Les commissions saisies au fond d'un dossier, une entrée par sigle.

    C'est le fait équivalent, côté européen, à la commission saisie au fond d'un
    dossier de l'Assemblée — ce que l'interface appelle la « matière » d'un vote
    (`commissions_dossiers.json`, #328). Besoin remonté le 14/09/2026 : aucun
    objet européen n'en portait, et c'est ce qui bloquait deux figures.

    Mesuré sur les 355 dossiers de cet index : **347 en portent au moins une**
    (97,7 %) — 299 une seule, 41 deux, 7 trois.

    **Le libellé de type est conservé tel quel.** La source distingue quatre
    états — saisine au fond, ancienne saisine, saisine conjointe, ancienne
    saisine conjointe — et les fondre publierait une compétence qu'elle
    sépare. Traduire le sigle ou le nom ne serait pas mieux : « JURI » et
    « Legal Affairs » sont ce que le Parlement publie.
    """
    entrees: list[dict[str, Any]] = []
    for commission in dossier.get("committees") or []:
        if not isinstance(commission, dict):
            continue
        type_source = commission.get(CHAMP_TYPE)
        if not isinstance(type_source, str) or MARQUEUR_AU_FOND not in type_source.lower():
            continue
        for sigle, nom in _sigles_et_noms(commission):
            entrees.append({"sigle": sigle, "nom": nom, "type_source": type_source})
    return entrees


def references_visees(profils_dir: Path) -> set[str]:
    """Les `texte_vise` européens que les profils publiés citent.

    Lues dans `amendement_non_resolu`, où elles vivent : `amendement_id` reste
    `null` pour un amendement européen, et c'est voulu (#431).

    Comme pour les scrutins, l'index suit le corpus : 367 références servies,
    pas les 23 885 dossiers du dump.
    """
    refs: set[str] = set()
    for chemin in sorted(profils_dir.glob("*.pivot.json")):
        try:
            profil = json.loads(chemin.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for amendement in profil.get("amendements") or []:
            if not isinstance(amendement, dict):
                continue
            non_resolu = amendement.get("amendement_non_resolu")
            if not isinstance(non_resolu, dict):
                continue
            if non_resolu.get("institution") != "parlement_europeen":
                continue
            vise = non_resolu.get("texte_vise")
            if isinstance(vise, str) and vise:
                refs.add(vise)
    return refs


def construire(
    references: Iterable[str],
    force_download: bool = False,
    dump_path: Optional[Path] = None,
) -> list[dict[str, Any]]:
    """Les entrées d'index pour les références visées, triées par référence."""
    voulues = {r for r in references if r}
    if not voulues:
        return []
    chemin = dump_path or ensure_dump(DUMP_DOSSIERS, force_download)
    if chemin is None:
        raise DumpDossiersIndisponible(
            f"{DUMP_DOSSIERS} indisponible : un index vide se lirait comme "
            "« aucun dossier européen » (#510).")

    entrees: list[dict[str, Any]] = []
    vues: set[str] = set()
    for dossier in iter_dump_zst(Path(chemin)):
        procedure = dossier.get("procedure")
        if not isinstance(procedure, dict):
            continue
        reference = procedure.get("reference")
        if reference not in voulues or reference in vues:
            continue
        vues.add(reference)
        # Le stade passe par la table de `textes_portes[]` — une seule fabrique
        # de cette correspondance, sans quoi les deux divergeraient le jour où
        # la source ajoute une valeur.
        stade, stade_non_resolu = _stade_procedural_ue(
            {"stade_source": procedure.get("stage_reached")})
        entree: dict[str, Any] = {
            "id": identifiant(reference),
            "reference": reference,
            "titre": procedure.get("title") or None,
            "type_procedure": procedure.get("type") or None,
            "stade_procedural": stade,
            "commissions_au_fond": commissions_au_fond(dossier),
            "source_url": (dossier.get("meta") or {}).get("source")
            or f"https://parltrack.org/dossier/{reference}",
        }
        if stade_non_resolu:
            entree["stade_procedural_non_resolu"] = stade_non_resolu
        entrees.append(entree)
    entrees.sort(key=lambda e: e["reference"])
    return entrees


def document(entrees: list[dict[str, Any]]) -> dict[str, Any]:
    """L'index complet, entête comprise — même forme que `scrutins.json`."""
    return {
        "schema_version": SCHEMA_VERSION,
        "genere_le": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "licence_donnees": LICENCE_PARLTRACK,
        "dossiers": entrees,
    }


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--profils-dir", type=Path, default=DEFAULT_PROFILS_DIR)
    parser.add_argument("--out", type=Path, default=DEFAULT_SORTIE)
    parser.add_argument("--force-download", action="store_true",
                        help="re-télécharger le dump même si un cache existe")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    refs = references_visees(args.profils_dir)
    print(f"→ {len(refs)} référence(s) de dossier visée(s) par les amendements publiés")
    entrees = construire(refs, force_download=args.force_download)
    manquantes = sorted(refs - {e["reference"] for e in entrees})
    if manquantes:
        print(f"  [!] {len(manquantes)} non résolue(s) dans le dump — déclarées "
              "absentes, jamais fabriquées (§2 règle 5) :", file=sys.stderr)
        for reference in manquantes[:10]:
            print(f"        {reference}", file=sys.stderr)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(document(entrees), ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8")
    poids = args.out.stat().st_size / 1024
    print(f"  ✓ {len(entrees)} dossier(s) écrit(s) dans {args.out} ({poids:.0f} Ko)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
