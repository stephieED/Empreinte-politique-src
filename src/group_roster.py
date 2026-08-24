#!/usr/bin/env python3
"""
group_roster.py — Récupère la composition réelle d'un groupe parlementaire.

Contrairement à raw_data/candidats.json (liste éditoriale des candidats déclarés
à l'élection présidentielle, voir parti_profile.py), ce module interroge les
données ouvertes NosDéputés.fr / NosSénateurs.fr pour obtenir la VRAIE liste
des membres d'un groupe parlementaire (ex. tou·te·s les député·es LR d'une
législature), à utiliser ensuite avec group_profile.py.

L'endpoint documenté `/groupe/<SIGLE>/json` renvoie systématiquement une
erreur HTTP 500 (vérifié sur plusieurs sigles et domaines de législature,
comme le endpoint `/votes` déjà contourné dans candidate_profile.py). On
utilise donc à la place la liste complète des parlementaires
(`/deputes/json` ou `/senateurs/json`, qui inclut l'historique complet et un
champ `groupe_sigle` par entrée), filtrée côté client par sigle de groupe.

Usage (depuis la racine du dépôt) :
    python src/group_roster.py --chambre deputes --sigle LR --legislature 16
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Optional

import requests

from candidate_profile import BASE_URLS, HEADERS, TIMEOUT

# Association domaine NosDeputes.fr -> legislature AN. Definie ici depuis #403 :
# candidate_profile ne l'utilisait plus que pour les votes, ou elle figeait
# chaque profil sur une seule legislature (voir AN_SCRUTINS_LEGISLATURES) ; ce
# module en reste le seul utilisateur legitime, car les rosters de groupes sont
# bien servis par un domaine NosDeputes different par legislature. Verifie le
# 18/08/2026 : www.nosdeputes.fr sert toujours la 16e (618 deputes, mandats
# 2022-06-22 -> 2024-06-09), le site n'ayant pas ete etendu a la 17e — d'ou
# l'absence de cette derniere ici, contrairement aux votes qui viennent
# desormais directement de l'open data AN.
LEGISLATURE_BY_BASE_URL: dict[str, str] = {
    "https://www.nosdeputes.fr": "16",
    "https://2017-2022.nosdeputes.fr": "15",
    "https://2012-2017.nosdeputes.fr": "14",
    "https://2007-2012.nosdeputes.fr": "13",
}

# Association legislature AN -> domaine NosDeputes.fr (inverse du mapping
# ci-dessus). Ne couvre que l'Assemblée : le Sénat n'a plus qu'un seul domaine
# d'archive, quelle que soit la période (voir BASE_URLS["senateurs"]).
_BASE_URL_BY_LEGISLATURE_AN: dict[str, str] = {
    legislature: base_url for base_url, legislature in LEGISLATURE_BY_BASE_URL.items()
}

_LIST_ENDPOINT = {
    "deputes": "deputes",
    "senateurs": "senateurs",
}

# ── Reprise sur échec transitoire du fetch de roster (#518) ──────────────────
# `fetch_full_roster` faisait UN SEUL essai (timeout 15 s, aucun backoff), là où
# `candidate_profile._get_payload` en fait trois depuis longtemps pour les
# appels par candidat. L'asymétrie coûtait cher : ce fetch est le PREMIER pas
# de `generate_roster_candidats.py`, et #511 refuse — à raison — d'écrire un
# roster sur une collecte incomplète. Un hoquet de 15 s tuait donc le job
# entier, pas un membre.
#
# Mesuré sur le run 32738726729 (24/08/2026) : 4 shards roster sur 8 morts sur
# `Construction de la liste roster-driven`, alors que la seule clé de fetch
# restante — ('deputes', '16'), le Sénat étant suspendu depuis #516 — répondait
# normalement aux 4 autres, lancés dans la même minute. Rien de déterministe :
# 4 échecs et 4 succès sur la même URL, la signature d'un aléa transitoire.
#
# CE QUI EST RETENTÉ, et rien d'autre (voir `_erreur_retentable`) : timeout,
# erreur de connexion, 5xx. Un `SSLError` (certificat expiré, cas Sénat de
# #516) et un 4xx sont DÉTERMINISTES — les retenter ferait payer trois fois le
# même verdict et retarderait d'autant le message qui nomme la panne. C'est la
# même ligne de partage que `_get_payload`, et elle compte double ici : la
# suspension d'extraction de #516 s'appuie sur un échec qui remonte VITE.
_ROSTER_MAX_ATTEMPTS = 3
#: Temporisation avant la n-ième reprise, multipliée par le rang de la
#: tentative écoulée (2 s puis 4 s) : au pire 6 s d'attente ajoutés à un job
#: qui en dure ~200, contre un run entier perdu.
_ROSTER_RETRY_BACKOFF_SECONDS = 2.0

# ── Le plafond de lecture du roster lui est propre (#518, second incident) ───
# `fetch_full_roster` héritait de `candidate_profile.TIMEOUT` (15 s), une
# constante dimensionnée pour les pages PAR CANDIDAT (quelques Ko, servies
# depuis un cache). Or `/deputes/json` fait **814 Ko** et est généré à la
# volée : son coût est presque entièrement du time-to-first-byte.
#
# Mesuré le 24/08/2026, 24 appels sur `https://www.nosdeputes.fr/deputes/json` :
# aucune réponse en moins de 10 s, la plus rapide à 10,7 s, médiane des succès
# ~16,7 s. Le plafond de production était donc À L'INTÉRIEUR de la distribution
# de réponse de l'endpoint — 0 succès sur 8 à `timeout=15`, 3 sur 8 à
# `timeout=30`. (Ces latences absolues sont celles d'un environnement derrière
# proxy, pas d'un runner GitHub ; ce qui est robuste est la forme, pas le
# chiffre.) C'est ce qui a fait tomber `merge-and-pivot` sur le run
# 32750929942 : trois tentatives sous un plafond trop bas ne rachètent pas le
# plafond.
#
# Séparé en (connect, read) comme `gouvernement_textes.TIMEOUT` et
# `syceron_debates.TIMEOUT` le font déjà pour leurs gros dumps. Le CONNECT
# reste à `TIMEOUT` : c'est lui que la détection déterministe de #516 emprunte
# (poignée de main TLS, `SSLError`), et l'allonger retarderait le verdict qui
# justifie une suspension d'extraction. Seule la LECTURE est desserrée.
#
# Pire cas ajouté : 3 x 90 s + 6 s de backoff ≈ 4,5 min, sur un job qui en a 60.
_ROSTER_READ_TIMEOUT_SECONDS = 90
_ROSTER_TIMEOUT: tuple[int, int] = (TIMEOUT, _ROSTER_READ_TIMEOUT_SECONDS)


# ── Transit du roster BRUT par artifact (#518, second incident) ──────────────
# Il restait DEUX fetchs de la même liste par run après #519 :
# `prepare-roster-matrix` (→ artifact `roster-candidats`) et
# `generate_group_profiles.py`, qui refetche pour son propre compte. Le second
# n'est pas qu'une requête de trop : la fiche de groupe publiée est bâtie sur
# une composition lue ~7 min après celle qui a servi à la collecte des profils.
# Une entrée/sortie de groupe entre les deux, et la composition publiée diverge
# du corpus collecté — exactement le défaut de correction de #518, sans qu'une
# seule étape n'échoue.
#
# Le format est un dict {clé texte → membres bruts}, tel que rendu par
# `fetch_full_roster` : aucune projection, pour que le consommateur applique
# `filter_roster_by_sigle` sur la MÊME matière que le producteur.

#: Séparateur de la clé texte. `None` (législature non applicable, cas Sénat)
#: se sérialise en chaîne vide — jamais en `"None"` ni en `"courante"`, qui
#: seraient des valeurs de législature possibles au relire.
_SEPARATEUR_CLE = ":"


def cle_roster_texte(chambre: str, legislature: Optional[str]) -> str:
    """Clé JSON d'un roster brut : `"deputes:16"`, `"senateurs:"`."""
    return f"{chambre}{_SEPARATEUR_CLE}{legislature or ''}"


def _cle_roster_depuis_texte(cle: str) -> tuple[str, Optional[str]]:
    chambre, _, legislature = cle.partition(_SEPARATEUR_CLE)
    return (chambre, legislature or None)


def ecrire_rosters_bruts(
    chemin: Path,
    rosters_bruts: dict[tuple[str, Optional[str]], Optional[list[dict[str, Any]]]],
) -> int:
    """Sérialise les rosters bruts RÉUSSIS ; retourne le nombre de clés écrites.

    Une clé en échec (`None`) n'est pas écrite : un fetch raté ne doit pas
    devenir une liste vide chez le consommateur (AGENTS.md §2 règle 5) — son
    absence le fait retomber sur son propre fetch, ce qui est le mode dégradé
    voulu, pas une composition de 0 membre.
    """
    charge = {
        cle_roster_texte(chambre, legislature): membres
        for (chambre, legislature), membres in rosters_bruts.items()
        if membres is not None
    }
    chemin.parent.mkdir(parents=True, exist_ok=True)
    # Compact : 814 Ko par clé, et personne ne lit ce fichier à l'œil (#433).
    chemin.write_text(
        json.dumps({"rosters": charge}, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    return len(charge)


def charger_rosters_bruts(chemin: Path) -> dict[tuple[str, Optional[str]], list[dict[str, Any]]]:
    """Relit un fichier écrit par `ecrire_rosters_bruts`.

    Raises:
        OSError: fichier absent ou illisible.
        ValueError: JSON invalide, ou structure inattendue — jamais un dict
            vide par défaut : « fichier corrompu » et « aucun roster » n'ont
            pas la même conséquence chez l'appelant.
    """
    charge = json.loads(chemin.read_text(encoding="utf-8"))
    rosters = charge.get("rosters")
    if not isinstance(rosters, dict):
        raise ValueError(f"{chemin} : clé `rosters` absente ou de type inattendu.")
    resultat: dict[tuple[str, Optional[str]], list[dict[str, Any]]] = {}
    for cle, membres in rosters.items():
        if not isinstance(membres, list):
            raise ValueError(f"{chemin} : roster {cle!r} n'est pas une liste.")
        resultat[_cle_roster_depuis_texte(cle)] = membres
    return resultat


def _erreur_retentable(exc: Exception) -> bool:
    """Un nouvel essai sur la MÊME URL a-t-il une chance de rendre autre chose ?

    L'ordre des tests n'est pas indifférent : `requests.exceptions.SSLError`
    hérite de `ConnectionError`, donc un `isinstance(exc, ConnectionError)`
    placé en premier classerait un certificat expiré comme transitoire — et
    ferait exactement ce que la panne Sénat de #516 a montré qu'il ne faut pas
    faire.
    """
    if isinstance(exc, requests.exceptions.SSLError):
        return False
    if isinstance(exc, requests.HTTPError):
        statut = exc.response.status_code if exc.response is not None else None
        return statut is not None and 500 <= statut < 600
    return isinstance(exc, (requests.Timeout, requests.ConnectionError))


def _base_url_for(chambre: str, legislature: Optional[str]) -> str:
    """Détermine le domaine NosDéputés/NosSénateurs à interroger.

    Args:
        chambre: "deputes" | "senateurs".
        legislature: pour "deputes", législature AN (ex. "16") ; ignoré pour
                     "senateurs" (domaine d'archive unique, filtrage par date).

    Raises:
        ValueError: chambre inconnue ou législature AN non couverte.
    """
    if chambre not in BASE_URLS:
        raise ValueError(f"Chambre inconnue : {chambre!r}. Valeurs attendues : {sorted(BASE_URLS)}.")

    if chambre == "senateurs":
        return BASE_URLS["senateurs"][0]

    if legislature is None:
        return BASE_URLS["deputes"][0]

    if legislature not in _BASE_URL_BY_LEGISLATURE_AN:
        raise ValueError(
            f"Législature AN non couverte : {legislature!r}. "
            f"Valeurs connues : {sorted(_BASE_URL_BY_LEGISLATURE_AN)}."
        )
    return _BASE_URL_BY_LEGISLATURE_AN[legislature]


def _member_matches_legislature(member: dict[str, Any], legislature_debut: Optional[str]) -> bool:
    """Filtre côté client pour le Sénat (domaine d'archive unique, pas de sous-domaine par législature).

    Un membre est retenu si son mandat couvre ou suit le début de la période
    demandée. Sans date fournie, aucun filtrage n'est appliqué (tous les
    membres, courants et anciens, sont retournés).
    """
    if legislature_debut is None:
        return True
    fin = member.get("mandat_fin")
    return fin is None or str(fin) >= legislature_debut


def fetch_full_roster(
    chambre: str,
    legislature: Optional[str] = None,
    session: Optional[requests.Session] = None,
) -> list[dict[str, Any]]:
    """Récupère en UN seul appel réseau la liste complète (tous groupes confondus)
    des député·e·s/sénateur·rice·s d'une chambre/législature.

    À réutiliser pour construire plusieurs profils de groupe de la même
    chambre/législature sans refaire le même appel réseau à chaque sigle
    (voir generate_group_profiles.py) : filtrer ensuite le résultat avec
    `filter_roster_by_sigle`.

    Un échec TRANSITOIRE (timeout, erreur de connexion, 5xx) est retenté
    jusqu'à `_ROSTER_MAX_ATTEMPTS` fois, avec temporisation croissante (#518).
    Un échec DÉTERMINISTE (certificat, 4xx) remonte à la première tentative :
    voir `_erreur_retentable`.

    Le plafond appliqué est `_ROSTER_TIMEOUT` — propre à ce fetch, pas celui
    des pages par candidat, dont la valeur tombait au milieu de la
    distribution de réponse de cet endpoint (#518).

    Returns:
        Liste des membres bruts (déjà déballés de l'enveloppe {"depute": {...}}
        / {"senateur": {...}}), sans filtrage par groupe.

    Raises:
        ValueError: chambre ou législature inconnue.
        requests.RequestException: échec réseau, après épuisement des reprises
            pour un échec retentable (non intercepté, remonté tel quel).
    """
    base_url = _base_url_for(chambre, legislature)
    url = f"{base_url}/{_LIST_ENDPOINT[chambre]}/json"

    http = session or requests
    for tentative in range(1, _ROSTER_MAX_ATTEMPTS + 1):
        try:
            response = http.get(url, headers=HEADERS, timeout=_ROSTER_TIMEOUT)
            response.raise_for_status()
        except requests.RequestException as exc:
            if tentative == _ROSTER_MAX_ATTEMPTS or not _erreur_retentable(exc):
                raise
            attente = _ROSTER_RETRY_BACKOFF_SECONDS * tentative
            print(
                f"  [!] Roster {url} — tentative {tentative}/{_ROSTER_MAX_ATTEMPTS} "
                f"en échec ({type(exc).__name__}: {exc}). Nouvelle tentative dans "
                f"{attente:.0f} s.",
                file=sys.stderr,
            )
            time.sleep(attente)
            continue
        payload = response.json()
        raw_entries = payload.get(chambre) or []
        return [entry.get("depute") or entry.get("senateur") or entry for entry in raw_entries]

    # Inatteignable : la boucle sort par `return` ou par `raise`. Présent pour
    # que l'absence de valeur de retour ne dépende pas de la lecture du corps.
    raise AssertionError("fetch_full_roster : sortie de boucle impossible.")


def filter_roster_by_sigle(
    raw_members: list[dict[str, Any]],
    chambre: str,
    groupe_sigle: str,
    senat_periode_debut: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Filtre une liste de membres bruts (issue de `fetch_full_roster`) par sigle de groupe."""
    roster: list[dict[str, Any]] = []
    for member in raw_members:
        if member.get("groupe_sigle") != groupe_sigle:
            continue
        if chambre == "senateurs" and not _member_matches_legislature(member, senat_periode_debut):
            continue

        mandat_fin = member.get("mandat_fin")
        roster.append({
            "slug": member.get("slug"),
            "nom": member.get("nom"),
            "groupe_sigle": member.get("groupe_sigle"),
            "mandat_debut": member.get("mandat_debut"),
            "mandat_fin": mandat_fin,
            "actif": not mandat_fin,
        })
    return roster


def fetch_group_roster(
    chambre: str,
    groupe_sigle: str,
    legislature: Optional[str] = None,
    senat_periode_debut: Optional[str] = None,
    session: Optional[requests.Session] = None,
) -> list[dict[str, Any]]:
    """Récupère la liste des membres réels d'un groupe parlementaire.

    Args:
        chambre: "deputes" | "senateurs".
        groupe_sigle: sigle exact du groupe tel que fourni par l'API
                      (ex. "LR", "RN", "SOC" — voir champ `groupe_sigle` des
                      entrées renvoyées par /deputes/json ou /senateurs/json).
        legislature: pour "deputes" uniquement, législature AN (ex. "16") ;
                     détermine le sous-domaine interrogé. None = domaine courant.
        senat_periode_debut: pour "senateurs" uniquement, date ISO "YYYY-MM-DD"
                              minimale de fin de mandat pour retenir un membre
                              (le domaine d'archive couvre toutes les périodes
                              sans sous-domaine dédié). None = pas de filtrage
                              temporel (courants + anciens).
        session: session requests à réutiliser (optionnel, pour les tests).

    Returns:
        Liste de dicts {slug, nom, groupe_sigle, mandat_debut, mandat_fin, actif}
        pour chaque membre dont `groupe_sigle` correspond exactement.

    Raises:
        ValueError: chambre ou législature inconnue.
        requests.RequestException: échec réseau (non intercepté, remonté tel quel).

    Note : pour construire plusieurs groupes de la même chambre/législature,
    préférer `fetch_full_roster` + `filter_roster_by_sigle` pour éviter de
    refaire le même appel réseau à chaque sigle.
    """
    raw_members = fetch_full_roster(chambre, legislature=legislature, session=session)
    return filter_roster_by_sigle(raw_members, chambre, groupe_sigle, senat_periode_debut=senat_periode_debut)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Récupère la composition réelle d'un groupe parlementaire "
        "(NosDéputés.fr / NosSénateurs.fr).",
    )
    parser.add_argument("--chambre", choices=["deputes", "senateurs"], required=True)
    parser.add_argument("--sigle", required=True, metavar="SIGLE", help='Ex. "LR", "RN", "SOC".')
    parser.add_argument("--legislature", default=None, metavar="N", help='Pour "deputes" uniquement, ex. "16".')
    parser.add_argument(
        "--senat-periode-debut",
        default=None,
        metavar="YYYY-MM-DD",
        help='Pour "senateurs" uniquement : ne garder que les membres dont le mandat va au moins jusqu\'à cette date.',
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    try:
        roster = fetch_group_roster(
            chambre=args.chambre,
            groupe_sigle=args.sigle,
            legislature=args.legislature,
            senat_periode_debut=args.senat_periode_debut,
        )
    except (ValueError, requests.RequestException) as exc:
        print(f"[!] {exc}", file=sys.stderr)
        return 1

    print(f"→ {len(roster)} membre(s) trouvé(s) pour le groupe {args.sigle!r}.", file=sys.stderr)
    print(json.dumps(roster, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
