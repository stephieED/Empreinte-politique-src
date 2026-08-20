#!/usr/bin/env python3
"""
audit_diff_profils.py — Compare les profils d'une référence git à ceux du
disque, champ par champ, pour détecter ce qu'une régénération a perdu.

**Pourquoi.** La fusion additive de `merge_profile.py` n'est pas un confort :
elle préserve les données d'un run à l'autre quand une collecte échoue. On l'a
constaté le 18/08/2026 — les 283 textes de la XV d'Édouard Philippe ont
survécu à une collecte ratée uniquement grâce à elle.

Un run `--no-merge` (ou `fresh_run`) abandonne cette mémoire : tout ce que la
collecte du jour ne récupère pas est définitivement perdu, **silencieusement**.
Ce script est le contrôle qui manque avant de committer une telle
régénération.

**Comparaison par profil et par champ, jamais en agrégat** : un gain global
masquerait des pertes individuelles. C'est précisément ce qui rend le contrôle
utile — la correction de clé de #440 fait mécaniquement grimper le nombre
d'amendements, et cette hausse cacherait n'importe quelle perte de votes ou de
mandats si on ne regardait que le total.

Deux catégories de champs :

  - **stables** : une baisse est une alerte. Votes, mandats, textes portés,
    interventions n'ont aucune raison de diminuer d'un run à l'autre.
  - **attendus en hausse** : les amendements après la correction de clé de
    #440 (facteur × 2,8 à × 7,1 selon la législature). Une baisse y reste
    signalée, mais une hausse est normale.

Sortie non nulle si un profil a perdu sur un champ stable — utilisable comme
garde-fou avant commit.

Usage :
    python3 src/audit_diff_profils.py --ref origin/main \\
        --profils-dir pivot_data/profiles --out audit/diff.md
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

# Champs dont une baisse est anormale. `amendements` en est volontairement
# absent : la correction de clé de #440 le fait légitimement croître.
CHAMPS_STABLES: tuple[str, ...] = (
    "votes", "mandats", "textes_portes", "interventions", "dossiers_legislatifs",
)
CHAMPS_HAUSSE_ATTENDUE: tuple[str, ...] = ("amendements",)

TOUS_CHAMPS = CHAMPS_STABLES + CHAMPS_HAUSSE_ATTENDUE


def _compter(profil: dict[str, Any]) -> dict[str, int]:
    """Longueur de chaque liste métier. Un champ absent vaut 0 — indistinct
    d'une liste vide, ce qui est le comportement voulu : dans les deux cas le
    profil ne porte aucune entrée."""
    return {c: len(profil.get(c) or []) for c in TOUS_CHAMPS}


def lire_profils_git(ref: str, repertoire: str) -> dict[str, dict[str, int]]:
    """Compte les entrées de chaque profil d'une référence git.

    `git cat-file --batch` plutôt qu'un `git show` par fichier : sur 752
    profils de ~10 Mo, lancer autant de processus prend des minutes. Ici un
    seul processus reçoit la liste des chemins et renvoie les blobs à la
    suite.
    """
    listing = subprocess.run(
        ["git", "ls-tree", "--name-only", f"{ref}:{repertoire}"],
        capture_output=True, text=True,
    )
    if listing.returncode != 0:
        raise SystemExit(
            f"[!] Chemin introuvable dans la référence git : {ref}:{repertoire}\n"
            "    `--ref-dir` vaut par défaut `--profils-dir`. Si les profils "
            "régénérés sont hors du dépôt (répertoire de mesure, worktree...), "
            "préciser le chemin côté référence :\n"
            "      --profils-dir /chemin/hors/depot --ref-dir pivot_data/profiles"
        )
    fichiers = [f for f in listing.stdout.split() if f.endswith(".json")]
    if not fichiers:
        return {}

    # Lecture EN FLUX du `--batch`, blob par blob. `capture_output=True`
    # bufferisait la totalité des profils avant d'en compter la première
    # entrée : 3,2 Gio de RSS sur les 209 profils du 19/08/2026, et un process
    # tué par l'OOM killer. À 752 profils ce serait ~11 Go, donc un échec
    # certain en CI — pour un script dont tout l'intérêt est de tourner AVANT
    # le commit (#460).
    #
    # Seuls les comptes sont retenus, jamais les profils : la mémoire ne dépend
    # plus que du plus gros blob (~26 Mo), pas du corpus. Même correction que
    # sur l'index des scrutins (#432) et sur celui des amendements (#431) —
    # c'est le troisième outil de ce dépôt à buter là-dessus.
    proc = subprocess.Popen(
        ["git", "cat-file", "--batch"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
    )
    assert proc.stdin is not None and proc.stdout is not None

    resultats: dict[str, dict[str, int]] = {}
    try:
        for fichier in fichiers:
            proc.stdin.write(f"{ref}:{repertoire}/{fichier}\n".encode())
            proc.stdin.flush()
            entete = proc.stdout.readline().split()
            if len(entete) < 3:        # « <oid> missing »
                continue
            taille = int(entete[2])
            contenu = proc.stdout.read(taille)
            proc.stdout.read(1)        # saut de ligne final
            try:
                resultats[fichier] = _compter(json.loads(contenu))
            except ValueError:
                continue
            del contenu
    finally:
        proc.stdin.close()
        proc.stdout.read()
        proc.wait()
    return resultats


def lire_profils_disque(repertoire: Path) -> dict[str, dict[str, int]]:
    resultats: dict[str, dict[str, int]] = {}
    for chemin in sorted(repertoire.glob("*.json")):
        try:
            resultats[chemin.name] = _compter(json.loads(chemin.read_bytes()))
        except (OSError, ValueError):
            continue
    return resultats


def comparer(
    avant: dict[str, dict[str, int]], apres: dict[str, dict[str, int]]
) -> dict[str, Any]:
    """Compare deux relevés. Fonction pure."""
    pertes: list[dict[str, Any]] = []
    gains: list[dict[str, Any]] = []
    for fichier in sorted(set(avant) | set(apres)):
        a, b = avant.get(fichier), apres.get(fichier)
        if a is None:
            gains.append({"fichier": fichier, "champ": "(profil entier)",
                          "avant": 0, "apres": sum(b.values()), "stable": False})
            continue
        if b is None:
            pertes.append({"fichier": fichier, "champ": "(profil entier)",
                           "avant": sum(a.values()), "apres": 0, "stable": True})
            continue
        for champ in TOUS_CHAMPS:
            if b[champ] < a[champ]:
                pertes.append({"fichier": fichier, "champ": champ,
                               "avant": a[champ], "apres": b[champ],
                               "stable": champ in CHAMPS_STABLES})
            elif b[champ] > a[champ]:
                gains.append({"fichier": fichier, "champ": champ,
                              "avant": a[champ], "apres": b[champ],
                              "stable": champ in CHAMPS_STABLES})

    pertes_stables = [p for p in pertes if p["stable"]]
    return {
        "nb_avant": len(avant),
        "nb_apres": len(apres),
        "pertes": pertes,
        "gains": gains,
        "pertes_sur_champs_stables": pertes_stables,
        "totaux_avant": {c: sum(v[c] for v in avant.values()) for c in TOUS_CHAMPS},
        "totaux_apres": {c: sum(v[c] for v in apres.values()) for c in TOUS_CHAMPS},
    }


def generate_markdown_report(rapport: dict[str, Any], ref: str) -> str:
    lignes = [
        "# Diff des profils avant / après régénération",
        "",
        f"Référence comparée : `{ref}` — **{rapport['nb_avant']} profils** avant, "
        f"**{rapport['nb_apres']}** après.",
        "",
        "## Totaux par champ",
        "",
        "| Champ | Avant | Après | Écart |",
        "| --- | --- | --- | --- |",
    ]
    for champ in TOUS_CHAMPS:
        a, b = rapport["totaux_avant"][champ], rapport["totaux_apres"][champ]
        ecart = b - a
        marque = "" if champ in CHAMPS_HAUSSE_ATTENDUE else ""
        lignes.append(f"| `{champ}`{marque} | {a} | {b} | {ecart:+} |")

    pertes_stables = rapport["pertes_sur_champs_stables"]
    lignes += [
        "",
        "> Les totaux ne suffisent pas : une hausse globale des amendements "
        "masquerait des pertes individuelles. Le verdict porte sur le détail "
        "ci-dessous.",
        "",
        "## Pertes sur champs stables",
        "",
    ]
    if not pertes_stables:
        lignes += ["Aucune. **Aucun profil n'a perdu de votes, mandats, textes "
                   "portés, interventions ni dossiers.**", ""]
    else:
        lignes += [
            f"**{len(pertes_stables)} perte(s) détectée(s)** — une baisse sur ces "
            "champs n'a pas d'explication attendue et doit être élucidée avant "
            "de committer.",
            "",
            "| Profil | Champ | Avant | Après | Perdu |",
            "| --- | --- | --- | --- | --- |",
        ]
        for p in pertes_stables[:60]:
            lignes.append(
                f"| `{p['fichier']}` | `{p['champ']}` | {p['avant']} | "
                f"{p['apres']} | **{p['avant'] - p['apres']}** |"
            )
        if len(pertes_stables) > 60:
            lignes.append(f"| … | | | | {len(pertes_stables) - 60} de plus |")
        lignes.append("")

    autres_pertes = [p for p in rapport["pertes"] if not p["stable"]]
    if autres_pertes:
        lignes += [
            "## Baisses sur `amendements`",
            "",
            f"{len(autres_pertes)} profil(s). Une hausse y est attendue après la "
            "correction de clé (#440) ; une **baisse** ne l'est pas et mérite "
            "vérification.",
            "",
        ]
    lignes += [
        "## Gains",
        "",
        f"{len(rapport['gains'])} augmentation(s) relevée(s), tous champs confondus.",
        "",
    ]
    return "\n".join(lignes)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--ref", default="origin/main", metavar="REF",
                        help="Référence git servant d'avant (défaut : origin/main).")
    parser.add_argument("--profils-dir", default="pivot_data/profiles", metavar="REP",
                        help="Répertoire des profils régénérés (défaut : pivot_data/profiles).")
    parser.add_argument("--ref-dir", default=None, metavar="REP",
                        help="Répertoire côté référence, si différent de --profils-dir.")
    parser.add_argument("--out", metavar="FICHIER", help="Rapport Markdown.")
    parser.add_argument("--out-json", metavar="FICHIER", help="Rapport JSON.")
    parser.add_argument(
        "--tolerer-pertes", action="store_true",
        help="Ne pas sortir en erreur en cas de perte sur un champ stable. "
             "À n'utiliser qu'après avoir élucidé chaque perte.",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    ref_dir = args.ref_dir or args.profils_dir

    print(f"→ Lecture de {args.ref}:{ref_dir}…", file=sys.stderr)
    avant = lire_profils_git(args.ref, ref_dir)
    print(f"→ Lecture de {args.profils_dir}…", file=sys.stderr)
    apres = lire_profils_disque(Path(args.profils_dir))

    if not avant and not apres:
        print("[!] Aucun profil des deux côtés.", file=sys.stderr)
        return 1

    rapport = comparer(avant, apres)
    markdown = generate_markdown_report(rapport, args.ref)

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(markdown, encoding="utf-8")
        print(f"→ Rapport écrit : {args.out}", file=sys.stderr)
    else:
        print(markdown)
    if args.out_json:
        Path(args.out_json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out_json).write_text(
            json.dumps(rapport, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    pertes = rapport["pertes_sur_champs_stables"]
    if pertes:
        print(f"[!] {len(pertes)} perte(s) sur des champs stables.", file=sys.stderr)
        return 0 if args.tolerer_pertes else 1
    print("✓ Aucune perte sur les champs stables.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
