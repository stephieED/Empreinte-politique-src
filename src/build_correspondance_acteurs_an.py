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

## La passe dérivée, qui ne fait rien de tout ça (#715)

`--completer-derivees` est une **seconde passe, disjointe**, et le rester est
le sujet. Elle ne lit pas AMO30, ne fait aucune correspondance par nom, ne
touche à aucune entrée existante : elle ajoute une entrée pour les seuls slugs
que `raw_data/rosters_bruts.json` déclare `slug_origine: "fabrique"` — ceux que
#708 a fabriqués **depuis** l'acteur, par `slugify(état civil AMO30)`.

Pour ceux-là il n'y a aucun rapprochement à prouver : le slug est sorti de cet
acteur-là, il ne pouvait pas en désigner un autre. Ce que l'entrée apporte
n'est pas une preuve, c'est le **gel** de l'identifiant — sans elle, un
changement de nom d'usage déplacerait le slug au run suivant et publierait la
même personne deux fois (#487, #668). Elle est estampillée `origine: "derivee"`
pour que personne ne la lise comme relue.

Le point 3 ci-dessus n'est **pas** assoupli : un slug publié que le roster ne
déclare pas fabriqué ne reçoit toujours rien, et la §5b du portail bloque
toujours son commit.

**Hors ligne, et c'est une contrainte, pas une commodité** : cette passe tourne
dans `merge-and-pivot`, juste avant le portail. Un second téléchargement AMO30
à cet endroit ferait qu'une panne de source coûte le commit d'un run dont la
donnée est bonne — ce que #524 interdit. L'état civil vient donc du profil
pivot que le run vient d'écrire, et le `PA######` du roster, recoupé contre
l'`identifiants.an` de ce profil.

## Usage

    python src/build_correspondance_acteurs_an.py            # écrit la table
    python src/build_correspondance_acteurs_an.py --verifier # ne réécrit rien
    python src/build_correspondance_acteurs_an.py \
        --completer-derivees --rosters-bruts raw_data/rosters_bruts.json

Le référentiel AMO30 est téléchargé (ou relu depuis `.cache/`) par
`candidate_profile` : ce script sort donc sur le réseau, comme tous les
scripts de collecte, et n'est jamais appelé depuis un test — sauf
`--completer-derivees`, qui n'y touche pas.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
import argparse
import json
import re
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


# ---------------------------------------------------------------------------
# Passe dérivée (#715) — hors ligne, additive, et qui ne touche à rien d'autre
# ---------------------------------------------------------------------------

#: Forme de l'URL de fiche AN, la même `preuve` que portent 477 des 481 entrées
#: committées. Recopiée ici plutôt qu'importée de `candidate_profile` : cette
#: passe est volontairement découplée de la collecte et de ses dépendances
#: réseau (même arbitrage que `_ACTEUR_REF_DANS_URL` dans `normalize_profil`).
_URL_FICHE_AN = "https://www2.assemblee-nationale.fr/deputes/fiche/OMC_{}"

_ACTEUR_REF_DANS_URL = re.compile(r"PA\d+")


def slugs_fabriques(chemin_rosters_bruts: Path) -> dict[str, str]:
    """`slug → acteur_ref` pour les membres entrés avec un slug **fabriqué**.

    L'autorité est `slug_origine` (#708) : un slug marqué `table` vient d'une
    entrée relue et n'a rien à faire ici, et un slug absent du roster n'est pas
    déclaré fabriqué du tout. C'est ce filtre qui empêche cette passe de
    devenir un tampon posé sur n'importe quel slug publié.

    Un même slug peut apparaître dans plusieurs législatures du roster : les
    occurrences doivent alors désigner **le même acteur**, sinon le roster se
    contredit et on ne devine pas lequel croire.
    """
    with open(chemin_rosters_bruts, encoding="utf-8") as f:
        document = json.load(f)

    fabriques: dict[str, str] = {}
    for membres in (document.get("rosters") or {}).values():
        for membre in membres or []:
            if membre.get("slug_origine") != "fabrique":
                continue
            slug, acteur_ref = membre.get("slug"), membre.get("acteur_ref")
            if not slug or not acteur_ref:
                continue
            deja = fabriques.get(slug)
            if deja is not None and deja != acteur_ref:
                raise SystemExit(
                    f"{chemin_rosters_bruts} : le slug fabriqué {slug!r} est "
                    f"déclaré sur deux acteurs ({deja} et {acteur_ref}). Le "
                    "roster se contredit — aucune entrée n'est écrite."
                )
            fabriques[slug] = acteur_ref
    return fabriques


def _projection_profil(chemin: Path) -> dict[str, Any]:
    """Ce qu'on garde d'un profil pivot, et rien d'autre (AGENTS.md §3a, #628).

    Un profil pivot pèse 1,3 Mio en médiane et jusqu'à 14,6 Mio : il est lu,
    réduit à ces cinq valeurs, puis relâché. Aucun document n'est conservé.
    """
    with open(chemin, encoding="utf-8") as f:
        profil = json.load(f)
    identite = profil.get("identite") or {}
    identifiants = profil.get("identifiants") or {}
    acteur_ref = identifiants.get("an")
    if not acteur_ref:
        # Repli sur l'URL de fiche : c'est la source d'où `normalize_profil`
        # tire lui-même `identifiants.an` quand la table est muette — même
        # fait, même source, pas une seconde autorité.
        trouve = _ACTEUR_REF_DANS_URL.search(identite.get("source_url") or "")
        acteur_ref = trouve.group(0) if trouve else None
    return {
        "acteur_ref": acteur_ref,
        "nom_complet": profil.get("nom"),
        "civilite": identite.get("civilite"),
        "date_naissance": identite.get("date_naissance"),
        "uri_hatvp": identite.get("uri_hatvp"),
    }


def entrees_derivees(
    profiles_dir: Path,
    fabriques: dict[str, str],
    table_existante: dict[str, dict[str, Any]],
    verifie_le: str,
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Renvoie `(entrées à ajouter, refus nommés)`.

    Trois filtres, chacun sur une manière connue d'écrire une entrée fausse :

    1. **la table passe devant** — un slug qui y est déjà n'est pas réécrit,
       c'est la règle #708 §3 qui rend le gel effectif ;
    2. **le profil doit être publié** — la §5b ne bloque que sur ceux-là, et
       une entrée pour un slug qu'aucun profil ne porte n'est pas un tampon
       qu'on veut poser d'avance ;
    3. **le recoupement doit tomber juste** — l'`identifiants.an` du profil
       publié doit valoir *exactement* l'`acteur_ref` que le roster déclare.
       En désaccord, aucune entrée : le profil décrirait alors un acteur et le
       slug en désignerait un autre, ce qui est le défaut de clé collante de
       #540 sur le seul identifiant du dépôt.
    """
    entrees: dict[str, dict[str, Any]] = {}
    refus: list[str] = []

    for slug, acteur_ref in sorted(fabriques.items()):
        if slug in table_existante:
            continue
        chemin = profiles_dir / f"{slug}{SUFFIXE_PIVOT}"
        if not chemin.is_file():
            continue

        projection = _projection_profil(chemin)
        publie = projection["acteur_ref"]
        if publie is None:
            refus.append(
                f"{slug} : le profil publié ne porte aucun identifiant AN — "
                f"le roster le déclare fabriqué depuis {acteur_ref}, mais rien "
                "dans le profil ne le corrobore."
            )
            continue
        if publie != acteur_ref:
            refus.append(
                f"{slug} : le roster le déclare fabriqué depuis {acteur_ref}, "
                f"le profil publié porte {publie}. Aucune entrée n'est écrite "
                "— c'est un arbitrage, pas une dérivation."
            )
            continue

        entrees[slug] = {
            "identifiants": {
                "an": acteur_ref,
                "senat": None,
                "europarl": None,
                "hatvp": projection["uri_hatvp"],
            },
            "etat_civil": {
                "civilite": projection["civilite"],
                # `prenom` et `nom` séparés n'existent que dans la fiche AMO30,
                # que cette passe ne lit pas : `null` dit « non porté », il ne
                # dit rien sur la personne (AGENTS.md §2 règle 5).
                "prenom": None,
                "nom": None,
                "nom_complet": projection["nom_complet"],
                "date_naissance": projection["date_naissance"],
            },
            "ecart": None,
            "motif": None,
            "preuve": _URL_FICHE_AN.format(acteur_ref),
            "verifie_le": verifie_le,
            "origine": "derivee",
        }

    return entrees, refus


def _ecrire_document(chemin: Path, document: dict[str, Any]) -> None:
    document["genere_le"] = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+0000")
    document["correspondances"] = dict(sorted(document["correspondances"].items()))
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(document, f, ensure_ascii=False, indent=2)
        f.write("\n")


def completer_derivees(args: argparse.Namespace) -> int:
    """Passe `--completer-derivees` : additive, hors ligne, ou rien du tout."""
    if args.rosters_bruts is None:
        print(
            "  [X] --completer-derivees exige --rosters-bruts : c'est "
            "`slug_origine` qui dit quel slug a été fabriqué, et rien d'autre.",
            file=sys.stderr,
        )
        return 2

    try:
        table_existante = charger_correspondance(args.sortie)
        with open(args.sortie, encoding="utf-8") as f:
            # Le document BRUT, pas la table normalisée : les entrées relues
            # sont reconduites **verbatim**, octet pour octet. Réécrire la forme
            # normalisée y ajouterait `acteur_ref` en doublon d'`identifiants.an`
            # et `origine` sur les 481, c'est-à-dire réécrire du travail relu
            # pour une passe qui n'a rien à y dire (#525 §6).
            document = json.load(f)
    except Exception as exc:
        print(
            f"  [X] Table de correspondance illisible ({exc}) : la passe "
            "dérivée est additive, elle ne repart pas de zéro.",
            file=sys.stderr,
        )
        return 2

    fabriques = slugs_fabriques(args.rosters_bruts)
    entrees, refus = entrees_derivees(
        args.profiles_dir, fabriques, table_existante, args.verifie_le
    )

    for message in refus:
        print(f"  [X] {message}", file=sys.stderr)

    print(
        f"-> {len(fabriques)} slug(s) déclaré(s) fabriqué(s) par le roster ; "
        f"{len(entrees)} entrée(s) dérivée(s) ajoutée(s) ; "
        f"{len(refus)} refus."
    )
    if refus:
        # Un refus est un slug publié qui restera sans entrée : la §5b bloquera
        # le commit en le nommant. Sortir en 1 le dit ici plutôt que là-bas.
        return 1
    if not entrees:
        # Ne pas réécrire un fichier identique : `genere_le` bougerait à chaque
        # run et le step de commit verrait un changement là où il n'y en a pas.
        print("-> Rien à ajouter : la table est déjà à jour, elle n'est pas réécrite.")
        return 0

    document["correspondances"].update(entrees)
    _ecrire_document(args.sortie, document)
    print(f"-> Écrit : {args.sortie} ({len(document['correspondances'])} entrées)")
    return 0


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
    parser.add_argument(
        "--completer-derivees",
        action="store_true",
        help=(
            "Passe additive HORS LIGNE (#715) : ajoute une entrée `origine: "
            "derivee` pour les slugs que --rosters-bruts déclare fabriqués "
            "(#708). Ne lit ni AMO30 ni les entrées relues."
        ),
    )
    parser.add_argument(
        "--rosters-bruts",
        type=Path,
        default=None,
        help="raw_data/rosters_bruts.json du run — exigé par --completer-derivees.",
    )
    return parser


def main() -> int:
    args = _build_arg_parser().parse_args()

    # Passe disjointe, et rendue disjointe ici : elle sort avant que quoi que
    # ce soit ne touche au réseau ou aux entrées relues.
    if args.completer_derivees:
        return completer_derivees(args)

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
