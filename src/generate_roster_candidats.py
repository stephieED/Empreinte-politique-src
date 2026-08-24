#!/usr/bin/env python3
"""
generate_roster_candidats.py — Construit une liste de "candidats" à partir du
roster réel des groupes parlementaires configurés dans raw_data/groupes_reels.json,
au lieu de la liste éditoriale raw_data/candidats.json.

Contexte : raw_data/candidats.json est une liste éditoriale maintenue à la
main (candidats déclarés/pressentis à la présidentielle). Ce script produit
une liste alternative, au même format d'entrée que celui accepté par
generate_all_profiles.py --candidats, mais pilotée par la composition réelle
des groupes parlementaires — utile pour extraire des profils individuels pour
tou·te·s les membres d'un groupe, pas seulement les candidats déclarés.

Comme generate_group_profiles.py, ce script ne fait qu'UN SEUL fetch réseau
par (roster_chambre, legislature) distinct, partagé entre tous les groupes de
la config (voir group_roster.fetch_full_roster / filter_roster_by_sigle).

## Le roster n'est JAMAIS écrit sur une collecte incomplète (#511)

Le 20/08/2026, un `Read timed out` sur les DEUX fetchs a fait écrire ici un
roster de **0 candidat**, avec un code de sortie 0. La passe suivante
(`generate_all_profiles.py --pivot-only --candidats raw_data/roster_candidats.json`)
a donc itéré sur le vide : les 20 membres que ce run venait de collecter n'ont
reçu aucun pivot et ne sont publiés nulle part — run `32405297873`, conclu en
**succès**, 229 profils bruts pour 209 pivots au commit `68bc094`.

La fonction refusait déjà d'écrire sur une ENTRÉE vide (« aucun groupe à
agréger ») trois lignes plus haut. C'est le même raisonnement, appliqué au même
fichier : une donnée non résolue ne reçoit pas de valeur par défaut, elle
échoue bruyamment (AGENTS.md §2 règle 5).

**Trois anomalies bloquent l'écriture**, et aucune n'est un seuil chiffré :

1. **un fetch en échec** — `fetch_rosters_bruts` le sait déjà (`None` pour la
   clé), l'information était simplement jetée. C'est aussi la réponse au
   rétrécissement : la granularité d'une panne est la clé de fetch entière, donc
   un échec partiel n'enlève pas « quelques » membres mais **452 ou 300** sur
   les 752 de `raw_data/groupes_reels.json` (mesuré au 19/08/2026 : 452 AN
   + 300 Sénat). Un test de vacuité ne verrait rien ; celui-ci nomme la clé ;
2. **un groupe configuré qui rend 0 membre** alors que son fetch a réussi —
   le seul mécanisme de rétrécissement restant (sigle renommé en amont). Les 7
   groupes configurés rendent aujourd'hui entre 31 et 235 membres ;
3. **un roster total vide** — le filet de dernier recours, celui de l'incident.

Un seuil de rétrécissement chiffré a été écarté, pas oublié : voir
docs/technical_decisions.md#roster-jamais-ecrit-vide.

## Un groupe à l'extraction suspendue n'est pas interrogé (#516)

Une entrée de `groupes_reels.json` portant `extraction_suspendue` sort des
trois étages ci-dessus : sa clé de fetch n'est pas construite, ses membres ne
sont pas collectés, et son absence n'est **pas** une anomalie — ce n'est pas
une panne, c'est une décision écrite. Les deux entrées Sénat le sont depuis le
24/08/2026 (certificat TLS expiré sur `archive.nossenateurs.fr`), ce qui
faisait échouer tout le run, collecte AN comprise. Voir `groupes_config.py` et
docs/technical_decisions.md#extraction-groupe-suspendue-516.

## Une seule construction par run en CI, et des anomalies annotées (#518)

Ce script était appelé par les **9 invocations** d'un run `generate-data`
(8 shards + `merge-and-pivot`), donc 9 fetchs de la même liste. Il n'est plus
appelé qu'une fois, par `prepare-roster-matrix`, et son résultat transite par
l'artifact `roster-candidats` ; les consommateurs ne le rappellent qu'en repli,
si l'artifact manque. Ce n'était pas qu'une affaire de coût : les shards se
partagent le roster **par position**, et `merge-and-pivot` normalise en pivot
**sa** liste — deux listes qui divergent laissent un membre collecté sans
aucune passe pivot, sans qu'aucune étape n'échoue.

Chaque anomalie ci-dessus part aussi en annotation GitHub Actions
(`::error::`, voir `gha.py`) : trois runs sont morts ici en une semaine, et la
seule trace qu'en gardait l'onglet de résumé était
`Process completed with exit code 1`. Voir
docs/technical_decisions.md#roster-unique-par-run-518.

Usage (depuis la racine du dépôt) :
    python src/generate_roster_candidats.py \\
        --config raw_data/groupes_reels.json \\
        --out raw_data/roster_candidats.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

import gha
from group_roster import _base_url_for, fetch_full_roster, filter_roster_by_sigle
from groupes_config import (
    libelle_groupe,
    partitionner_groupes,
    resume_suspension,
)


def _roster_key(groupe: dict[str, Any]) -> tuple[str, Optional[str]]:
    """Clé (roster_chambre, legislature) identifiant un fetch réseau partageable."""
    legislature = groupe.get("legislature") if groupe["roster_chambre"] == "deputes" else None
    return (groupe["roster_chambre"], legislature)


def _actifs(groupes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Les groupes dont l'extraction n'est pas suspendue (#516).

    Appliqué aux TROIS étages (fetch, aplatissement, anomalies) et pas
    seulement dans `main()` : un groupe suspendu qui resterait visible d'un
    seul d'entre eux rouvrirait sa clé de fetch (étage 1) ou déclencherait un
    « 0 membre retenu » sur un roster qu'on n'a délibérément pas récupéré
    (étage 3). La suspension n'a de sens que si les trois la voient.
    """
    actifs, _ = partitionner_groupes(groupes)
    return actifs


def fetch_rosters_bruts(groupes: list[dict[str, Any]]) -> dict[tuple[str, Optional[str]], Optional[list[dict[str, Any]]]]:
    """Récupère le roster complet (non filtré) de chaque (roster_chambre, legislature)
    distinct présent dans `groupes`, un seul fetch réseau par clé. Une valeur `None`
    signale un échec réseau pour cette clé."""
    import requests  # import tardif : non requis hors récupération réelle

    rosters_bruts: dict[tuple[str, Optional[str]], Optional[list[dict[str, Any]]]] = {}
    for groupe in _actifs(groupes):
        key = _roster_key(groupe)
        if key in rosters_bruts:
            continue
        roster_chambre, legislature = key
        print(f"→ Récupération du roster complet ({roster_chambre}, législature={legislature or 'courante'})…", file=sys.stderr)
        try:
            rosters_bruts[key] = fetch_full_roster(roster_chambre, legislature=legislature)
        except (ValueError, requests.RequestException) as exc:
            print(f"  [!] Récupération du roster impossible pour {key} : {exc}", file=sys.stderr)
            rosters_bruts[key] = None
    return rosters_bruts


def _libelle_groupe(groupe: dict[str, Any]) -> str:
    """Nom d'un groupe dans les messages d'anomalie, stable et sans ambiguïté.

    `groupe_id` est renseigné sur les 7 groupes de `raw_data/groupes_reels.json`
    et distingue les deux `LR` (`AN:LR` et `Senat:LR`), ce que le seul sigle ne
    ferait pas. Repli sur `chambre:sigle` pour une config plus ancienne.

    Délègue à `groupes_config.libelle_groupe` depuis #516 : les trois
    consommateurs de la config nomment désormais un groupe de la même façon.
    """
    return libelle_groupe(groupe)


def build_roster_candidats_detaille(
    groupes: list[dict[str, Any]],
    rosters_bruts: dict[tuple[str, Optional[str]], Optional[list[dict[str, Any]]]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """`build_roster_candidats`, plus le décompte de membres retenus PAR GROUPE.

    Le décompte est relevé pendant l'aplatissement et non recalculé après coup :
    le total seul ne distingue pas « 300 membres manquants » de « ces 300-là
    manquent », et c'est cette distinction qui rend l'anomalie actionnable.

    Attention à ce que ce décompte mesure : le nombre de membres **retenus**,
    donc après déduplication par slug. Un groupe dont tous les membres seraient
    déjà venus d'un autre groupe compterait 0 ici — cas que la déduplication
    qualifie elle-même de config mal renseignée, et qu'on veut voir signalé.
    """
    candidats_par_slug: dict[str, dict[str, Any]] = {}
    membres_par_groupe: dict[str, int] = {}

    for groupe in _actifs(groupes):
        libelle = _libelle_groupe(groupe)
        membres_par_groupe.setdefault(libelle, 0)
        key = _roster_key(groupe)
        raw_members = rosters_bruts.get(key)
        if not raw_members:
            continue

        roster = filter_roster_by_sigle(
            raw_members,
            groupe["roster_chambre"],
            groupe["groupe_sigle"],
            senat_periode_debut=groupe.get("senat_periode_debut"),
        )
        base_url = _base_url_for(groupe["roster_chambre"], key[1])

        for membre in roster:
            slug = membre.get("slug")
            if not slug or slug in candidats_par_slug:
                continue
            candidats_par_slug[slug] = {
                "nom": membre.get("nom"),
                "slug": slug,
                "parti": None,
                "famille_politique": None,
                "statut": "roster_groupe",
                "date_declaration": None,
                "source": f"{base_url}/{slug}",
                "notes": f"Membre du groupe {groupe['groupe_sigle']} ({groupe['groupe_nom']}), issu du roster réel {groupe['chambre']}.",
            }
            membres_par_groupe[libelle] += 1

    return list(candidats_par_slug.values()), membres_par_groupe


def anomalies_roster(
    groupes: list[dict[str, Any]],
    rosters_bruts: dict[tuple[str, Optional[str]], Optional[list[dict[str, Any]]]],
    membres_par_groupe: dict[str, int],
    candidats: list[dict[str, Any]],
) -> list[str]:
    """Les raisons de NE PAS écrire le roster. Liste vide = écriture sûre.

    Fonction pure : elle ne lit que ce que la collecte a déjà relevé. Les trois
    motifs sont ceux du docstring de module (#511), dans cet ordre — du plus
    causal au plus symptomatique, pour que le premier message affiché soit celui
    qui explique les autres.
    """
    anomalies: list[str] = []

    cles_en_echec = {cle for cle, roster in rosters_bruts.items() if roster is None}
    for chambre, legislature in sorted(cles_en_echec, key=lambda c: (c[0], c[1] or "")):
        anomalies.append(
            f"récupération du roster ({chambre}, législature={legislature or 'courante'}) "
            "en échec : la composition de ses groupes est INCONNUE, pas vide."
        )

    for groupe in _actifs(groupes):
        if _roster_key(groupe) in cles_en_echec:
            # Déjà expliqué par la ligne ci-dessus ; le répéter par groupe
            # noierait la cause sous ses conséquences.
            continue
        libelle = _libelle_groupe(groupe)
        if membres_par_groupe.get(libelle, 0) == 0:
            anomalies.append(
                f"groupe {libelle} ({groupe.get('groupe_sigle')}) : 0 membre retenu "
                "alors que son roster a bien été récupéré — sigle renommé en amont, "
                "ou groupe dissous à retirer de la config."
            )

    if not candidats:
        anomalies.append("roster total vide : aucun candidat à écrire.")

    return anomalies


def build_roster_candidats(
    groupes: list[dict[str, Any]],
    rosters_bruts: dict[tuple[str, Optional[str]], Optional[list[dict[str, Any]]]],
) -> list[dict[str, Any]]:
    """Aplatit le roster de chaque groupe en une liste unique de candidats, au format
    attendu par generate_all_profiles.load_candidats() (shape {"candidats": [...]}).

    Fonction pure (aucun accès réseau) : `rosters_bruts` doit déjà contenir, pour
    chaque (roster_chambre, legislature) référencée par `groupes`, le roster brut
    (non filtré) issu de `fetch_full_roster`, ou `None` en cas d'échec réseau (le
    groupe correspondant est alors ignoré).

    Un membre ne peut appartenir qu'à un seul groupe par fetch (`groupe_sigle` est
    un champ mono-valué côté API), donc aucune fusion cross-groupe n'est attendue en
    conditions normales. On déduplique malgré tout par `slug` (garde-fou), au cas où
    deux entrées de la config pointeraient vers le même (chambre, legislature) avec
    un sigle mal renseigné : la première occurrence rencontrée est conservée.

    Reste la façon normale d'obtenir la liste seule. `main()` passe par
    `build_roster_candidats_detaille` parce qu'il a besoin, en plus, du décompte
    par groupe pour décider s'il a le droit d'écrire (#511).
    """
    candidats, _ = build_roster_candidats_detaille(groupes, rosters_bruts)
    return candidats


def generate_roster_candidats(groupes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Récupère les rosters réseau nécessaires puis construit la liste aplatie de candidats."""
    rosters_bruts = fetch_rosters_bruts(groupes)
    return build_roster_candidats(groupes, rosters_bruts)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--config",
        default="raw_data/groupes_reels.json",
        metavar="FICHIER",
        help="Fichier JSON listant les groupes à agréger (défaut : raw_data/groupes_reels.json).",
    )
    parser.add_argument(
        "--out",
        default="raw_data/roster_candidats.json",
        metavar="FICHIER",
        help="Fichier JSON de sortie (défaut : raw_data/roster_candidats.json).",
    )
    parser.add_argument(
        "--autoriser-roster-incomplet",
        action="store_true",
        help="Écrire le roster MALGRÉ une collecte incomplète (fetch en échec, "
             "groupe à 0 membre, roster vide). Les anomalies restent affichées. "
             "N'est câblé sur aucun input de generate-data.yml, délibérément : "
             "le remède d'une source en timeout est de relancer, pas de publier "
             "quand même (#511). Existe pour le travail local et pour qu'une "
             "panne de ce garde-fou ne bloque pas indéfiniment.",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    config_path = Path(args.config)
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"[!] Lecture de {config_path} impossible : {exc}", file=sys.stderr)
        return 1

    groupes = config.get("groupes") or []
    if not groupes:
        print(f"[!] Aucun groupe à agréger dans {config_path}.", file=sys.stderr)
        return 1

    # Une suspension se voit dans les logs du run qui la subit, jamais seulement
    # dans la config (#516) : sans cette ligne, un roster amputé de 300 membres
    # ressemble à un roster complet.
    groupes_actifs, groupes_suspendus = partitionner_groupes(groupes)
    for groupe in groupes_suspendus:
        print(f"⏸  {resume_suspension(groupe)}", file=sys.stderr)
    if not groupes_actifs:
        print(
            f"[!] Les {len(groupes_suspendus)} groupe(s) de {config_path} ont tous "
            "leur extraction suspendue : il n'y a rien à agréger. Réactiver au "
            "moins une entrée, ou ne pas appeler ce script.",
            file=sys.stderr,
        )
        return 1

    # Le fetch et l'aplatissement sont appelés séparément (et non via
    # `generate_roster_candidats`) pour garder sous la main ce que chacun sait :
    # quelles clés ont échoué, et combien de membres chaque groupe a rendus.
    # C'est exactement l'information que la version jusqu'à #511 jetait avant
    # d'écrire son résultat vide.
    rosters_bruts = fetch_rosters_bruts(groupes)
    candidats, membres_par_groupe = build_roster_candidats_detaille(groupes, rosters_bruts)

    out_path = Path(args.out)
    anomalies = anomalies_roster(groupes, rosters_bruts, membres_par_groupe, candidats)
    if anomalies:
        for anomalie in anomalies:
            print(f"[!] {anomalie}", file=sys.stderr)
            # #518 : chaque anomalie est aussi une annotation. Les runs des 21,
            # 22 et 24/08/2026 sont morts ici, et la seule trace qu'un lecteur
            # de l'onglet « Summary » en gardait était
            # `Process completed with exit code 1` — la cause (quelle clé de
            # fetch, quel groupe) restait dans un log de step à télécharger.
            # C'est le motif exact du garde-fou : une donnée non résolue doit
            # échouer BRUYAMMENT, et un log qu'il faut aller chercher n'est pas
            # du bruit (ROADMAP.md, #516).
            gha.annoter("error", f"ROSTER — {anomalie}")
        if not args.autoriser_roster_incomplet:
            message = (
                f"ROSTER_INCOMPLET — {out_path} N'A PAS été écrit : "
                f"{len(candidats)} candidat(s) collecté(s) sur une collecte incomplète. "
                "L'écrire publierait une composition de groupe non mesurée, et la passe "
                "pivot suivante itérerait sur ce qu'il en reste (AGENTS.md §2 règle 5, "
                "#511). Relancer, ou --autoriser-roster-incomplet en connaissance de cause."
            )
            print(f"[!] {message}", file=sys.stderr)
            gha.annoter("error", message)
            return 1
        print("[!] --autoriser-roster-incomplet : écriture forcée malgré les anomalies "
              "ci-dessus.", file=sys.stderr)
        # Écriture forcée : l'annotation reste, en `warning`. Le run continue,
        # donc rien d'autre ne dira que ce qu'il publie a été mesuré partiellement.
        gha.annoter(
            "warning",
            f"ROSTER_INCOMPLET toléré (--autoriser-roster-incomplet) : {out_path} est "
            f"écrit avec {len(candidats)} candidat(s) malgré {len(anomalies)} anomalie(s).",
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"candidats": candidats}, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"→ {len(candidats)} candidat(s) écrit(s) dans {out_path}.", file=sys.stderr)
    for libelle, nombre in sorted(membres_par_groupe.items()):
        print(f"   · {libelle} : {nombre} membre(s)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
