#!/usr/bin/env python3
"""
verifier_archivage_swh.py — les SHA cités résolvent-ils dans Software Heritage ?
(#568, sous-issue de #566)

**Ce que ce script remplace.** L'étape 2b de
`scripts/borner_historique_donnees.sh --preparer` décrivait cette vérification
en prose, sous la forme d'une boucle `curl` à recopier. Elle est faite sous
pression, juste avant une opération irréversible — le moment exact où l'on
saute une étape. Or c'est elle qui distingue un archivage d'un rituel
(#551, question 4 : « une vérification après archivage, sinon c'est un
rituel »).

**Pourquoi ce n'est pas une boucle de trois lignes.** La boucle en prose
itérait sur `git log --format=%H`, c'est-à-dire sur **tout** l'historique :
677 commits pour un quota anonyme de 120 requêtes/heure, soit six heures de
temporisation pour vérifier une population qui n'est pas celle qui compte. Ce
qui compte, ce sont les SHA **effectivement cités** — ceux qui cesseraient de
résoudre pour un lecteur d'issue ou de journal de décision. Ils sont noyés dans
la prose des fichiers `.md` suivis et des corps d'issues, et le tri manuel est
le meilleur moyen d'en oublier : au 28/08/2026, **135 chaînes hexadécimales
extraites de 42 fichiers `.md` et 260 corps d'issues, dont 47 résolvent en
commit**. Le reste est fait d'horodatages, d'identifiants de run et de sommes
de contrôle. (#551 relevait 124 pour 42, huit jours d'issues plus tôt : la
population bouge, c'est précisément pourquoi on l'outille au lieu de la
recopier.)

**Trois états, pas deux.** Un SHA absent de l'archive et une visite qui n'a pas
conclu ne se traitent pas pareil, et les confondre coûte dans les deux sens :
renoncer à une coupure légitime parce que l'ingestion est en cours, ou
l'autoriser alors que l'archive est incomplète. D'où :

  VÉRIFIÉ (0)      la visite est `full` et tous les SHA cités résolvent.
  MANQUANTS (1)    la visite est `full` et des SHA cités n'y sont pas. C'est un
                   vrai manque : ne pas couper.
  INDÉTERMINÉ (2)  la visite n'a pas conclu, le quota est épuisé, ou l'API est
                   injoignable. On n'a rien établi : réessayer, ne pas couper.

Le code de sortie porte le verdict ; la sortie nomme les SHA manquants et **où
ils sont cités**. « 3 manquants » n'aide personne ; « `deb28a7`, cité dans
#429, ne résout pas » se traite.

**Une quatrième situation, découverte au premier lancement réel** (28/08/2026)
et qu'il aurait été facile de confondre avec un manque d'archive : un SHA cité
qui résout dans le clone local mais n'est **atteignable depuis aucune ref**. Il
vient d'une branche de PR récrite par un rebase ou un `--force`, il survit ici
en objet pendant, et GitHub ne l'a jamais servi depuis une branche ou un tag.
Software Heritage archive ce qui est atteignable depuis les refs de l'origine :
un tel commit ne pouvait pas y entrer, et **relancer « Save Code Now » n'y
changera rien**.

C'est une citation déjà cassée pour un tiers, aujourd'hui, indépendamment de
toute coupure — donc un défaut de documentation, pas un défaut d'archive. Le
script la nomme sous l'étiquette CITATIONS ORPHELINES et **ne bloque pas**
dessus : couper n'aggrave rien, et un verdict rouge permanent finirait par ne
plus être lu. Ce qui bloque, c'est un SHA atteignable et pourtant absent de
l'archive — celui-là, la coupure le perdrait vraiment.

**Quota.** L'API anonyme de Software Heritage limite la route
`/api/1/revision/` à **120 requêtes/heure** (relevé le 28/08/2026 dans
l'en-tête `X-RateLimit-Limit`). Le script lit `X-RateLimit-Remaining` et
`X-RateLimit-Reset` à chaque réponse, temporise **en le disant** plutôt que
d'échouer en silence sur un `429`, et borne l'attente cumulée
(`--attente-max`) pour qu'un lancement ne puisse pas se transformer en veille
d'une heure sans l'annoncer.

**Ce script ne coupe rien, ne pousse rien, n'écrit rien dans le dépôt.** Il
lit, il interroge, il rend un verdict.

Usage :
    python3 src/verifier_archivage_swh.py
    python3 src/verifier_archivage_swh.py --sans-issues        # .md seulement
    python3 src/verifier_archivage_swh.py --json audit/swh.json

Voir `docs/technical_decisions.md#fenetre-recalibrage-551`, question 4.
"""

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

ORIGINE_PAR_DEFAUT = "https://github.com/stephieED/Empreinte-politique-src"
BASE_SWH = "https://archive.softwareheritage.org/api/1"

# 7 caractères est la longueur de SHA abrégé que git rend par défaut, et celle
# dans laquelle les citations de ce dépôt sont écrites. Les gardes
# lookbehind/lookahead écartent les fragments d'un mot plus long : sans elles,
# une chaîne de 41 caractères rendrait ses 40 premiers, et `deadbeefcafe` serait
# extrait de `xdeadbeefcafe`.
MOTIF_SHA = re.compile(r"(?<![0-9A-Za-z])([0-9a-f]{7,40})(?![0-9A-Za-z])")

# Au-delà, la sortie cesse d'être lisible : on nomme les premiers et on compte
# le reste. Ne s'applique qu'aux LIEUX de citation d'un même SHA, jamais aux
# SHA manquants eux-mêmes — ceux-là sont tous nommés, c'est l'objet du script.
MAX_LIEUX_AFFICHES = 4


# ── Extraction ───────────────────────────────────────────────────────────────


@dataclass
class Citation:
    """Une chaîne hexadécimale trouvée dans un texte, et l'endroit où elle
    l'a été. Le lieu est ce qui rend un manque traitable."""

    chaine: str
    lieu: str


@dataclass
class CommitCite:
    """Un SHA qui résout en commit du dépôt, et tous ses lieux de citation."""

    sha: str
    lieux: list[str] = field(default_factory=list)
    date: Optional[str] = None
    etat: str = "non_verifie"  # presente | absente | indetermine
    detail: str = ""
    # Atteignable depuis une ref du clone local ? Calculé PARESSEUSEMENT, et
    # seulement pour les SHA absents de l'archive : c'est la seule question à
    # laquelle il sert de répondre, et la calculer pour les 47 coûterait 47
    # parcours de graphe pour rien.
    atteignable: Optional[bool] = None
    ref: Optional[str] = None

    @property
    def court(self) -> str:
        return self.sha[:7]

    @property
    def orpheline(self) -> bool:
        """Citation déjà cassée avant toute coupure : le commit n'est
        atteignable depuis aucune ref, donc jamais servi par l'origine, donc
        jamais archivable."""
        return self.etat == "absente" and self.atteignable is False


def extraire_chaines(texte: str) -> list[str]:
    """Les chaînes hexadécimales de 7 caractères ou plus d'un texte.

    Aucun filtrage sémantique ici : une somme de contrôle, un identifiant
    d'artefact ou un nombre en base 10 fait de chiffres hexadécimaux passent.
    C'est `resoudre_commits()` qui tranche, et git est le seul arbitre légitime.
    """
    return [m.group(1).lower() for m in MOTIF_SHA.finditer(texte)]


def citations_des_fichiers_md(
    racine: str, lire: Callable[[str], str], fichiers: Iterable[str]
) -> list[Citation]:
    """Balaie les fichiers `.md` **suivis par git**, ligne à ligne.

    Ligne à ligne parce que le lieu doit être actionnable : « cité dans
    `docs/technical_decisions.md` » envoie chercher dans 2 000 lignes ;
    « `docs/technical_decisions.md:412` » s'ouvre.
    """
    citations: list[Citation] = []
    for chemin in fichiers:
        try:
            texte = lire(f"{racine}/{chemin}")
        except OSError as err:  # un fichier suivi mais absent du disque
            print(f"[!] {chemin} illisible : {err}", file=sys.stderr)
            continue
        for numero, ligne in enumerate(texte.split("\n"), start=1):
            for chaine in extraire_chaines(ligne):
                citations.append(Citation(chaine, f"{chemin}:{numero}"))
    return citations


def citations_des_issues(issues: Iterable[dict[str, Any]]) -> list[Citation]:
    """Balaie les corps d'issues. Le lieu est `#<numéro>`, la seule adresse
    stable — un titre se récrit, un numéro non.

    Les commentaires ne sont pas couverts : `gh issue list` ne les rend pas, et
    les tirer coûterait une requête API par issue. La population vérifiée est
    donc un peu plus étroite que la population citée, et c'est dit dans le
    rapport plutôt que passé sous silence.
    """
    citations: list[Citation] = []
    for issue in issues:
        numero = issue.get("number")
        corps = issue.get("body") or ""
        for chaine in extraire_chaines(corps):
            citations.append(Citation(chaine, f"#{numero}"))
    return citations


# ── Résolution par git ───────────────────────────────────────────────────────


def resoudre_commits(
    citations: Iterable[Citation],
    batch_check: Callable[[list[str]], dict[str, Optional[str]]],
    dater: Callable[[list[str]], dict[str, str]] = lambda shas: {},
) -> tuple[list[CommitCite], int]:
    """Ne garde que les chaînes qui résolvent en **commit** du dépôt.

    Rend `(commits, nb_chaines_distinctes)`. L'écart entre les deux est le
    chiffre à citer : « 42 SHA cités sur 124 chaînes extraites » — nommer la
    population, jamais le seul total.

    Deux chaînes différentes peuvent désigner le même commit (une abrégée, une
    complète) : elles fusionnent sur le SHA plein, et leurs lieux s'additionnent.
    """
    par_chaine: dict[str, list[str]] = {}
    for citation in citations:
        par_chaine.setdefault(citation.chaine, []).append(citation.lieu)

    resolus = batch_check(sorted(par_chaine))

    commits: dict[str, CommitCite] = {}
    for chaine, sha in resolus.items():
        if sha is None:
            continue
        commit = commits.setdefault(sha, CommitCite(sha=sha))
        for lieu in par_chaine.get(chaine, []):
            if lieu not in commit.lieux:
                commit.lieux.append(lieu)

    dates = dater(sorted(commits)) if commits else {}
    for sha, commit in commits.items():
        commit.date = dates.get(sha)

    ordonnes = sorted(commits.values(), key=lambda c: (c.date or "", c.sha))
    return ordonnes, len(par_chaine)


def _batch_check_git(racine: str) -> Callable[[list[str]], dict[str, Optional[str]]]:
    """`git cat-file --batch-check` : une seule invocation pour toute la
    population, là où un `cat-file -t` par chaîne en ferait 124.

    Rend la chaîne d'entrée -> SHA plein si elle résout en commit, `None`
    sinon. Un `tree`, un `blob`, un `tag`, un `missing` ou un `ambiguous` sont
    tous des non-commits : seuls les commits cessent de résoudre après une
    coupure d'historique.
    """

    def executer(chaines: list[str]) -> dict[str, Optional[str]]:
        if not chaines:
            return {}
        sortie = subprocess.run(
            ["git", "-C", racine, "cat-file", "--batch-check"],
            input="\n".join(chaines) + "\n",
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        resultats: dict[str, Optional[str]] = {}
        for chaine, ligne in zip(chaines, sortie.strip().split("\n")):
            champs = ligne.split()
            resultats[chaine] = (
                champs[0] if len(champs) >= 2 and champs[1] == "commit" else None
            )
        return resultats

    return executer


def _dater_git(racine: str) -> Callable[[list[str]], dict[str, str]]:
    """Date d'auteur ISO de chaque commit, pour ordonner le rapport du plus
    ancien au plus récent — l'ordre dans lequel une coupure les emporte."""

    def executer(shas: list[str]) -> dict[str, str]:
        dates: dict[str, str] = {}
        for sha in shas:
            try:
                dates[sha] = subprocess.run(
                    ["git", "-C", racine, "log", "-1", "--format=%aI", sha],
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout.strip()
            except subprocess.CalledProcessError:
                continue
        return dates

    return executer


def _refs_contenant_git(racine: str) -> Callable[[str], Optional[str]]:
    """La première ref — locale, distante suivie, ou tag — d'où un commit est
    atteignable, ou `None` s'il n'y en a aucune.

    `refs/pull/<n>/head` n'est délibérément pas interrogée : GitHub la sert,
    mais Software Heritage n'archive pas les refs de pull request. La question
    posée ici est « l'origine a-t-elle jamais offert ce commit à un
    archiveur ? », pas « GitHub le sert-il encore ? ».
    """

    def executer(sha: str) -> Optional[str]:
        try:
            sortie = subprocess.run(
                ["git", "-C", racine, "for-each-ref",
                 f"--contains={sha}", "--count=1", "--format=%(refname)"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        except subprocess.CalledProcessError:
            return None
        return sortie or None

    return executer


def fichiers_md_suivis(racine: str) -> list[str]:
    sortie = subprocess.run(
        ["git", "-C", racine, "ls-files", "*.md"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [ligne for ligne in sortie.split("\n") if ligne]


def corps_des_issues(racine: str, limite: int = 1000) -> list[dict[str, Any]]:
    """Les corps d'issues via `gh`. Tous états : une issue fermée cite autant
    qu'une ouverte, et son lecteur a le même besoin de vérifier."""
    sortie = subprocess.run(
        [
            "gh", "issue", "list", "--state", "all",
            "--limit", str(limite), "--json", "number,body",
        ],
        cwd=racine,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return json.loads(sortie or "[]")


# ── Interrogation de Software Heritage ───────────────────────────────────────


@dataclass
class Reponse:
    """Le strict nécessaire d'une réponse HTTP, pour qu'un test puisse en
    fabriquer une sans réseau ni bibliothèque."""

    code: int
    corps: Any = None
    entetes: dict[str, str] = field(default_factory=dict)


def _fetch_reel(timeout: float = 30.0) -> Callable[[str], Reponse]:
    """Le seul point du script qui sorte sur le réseau. Isolé pour que tout le
    reste soit vérifiable hors ligne — la suite de tests ne joint jamais SWH
    (AGENTS.md §3 : aucun test ne sort sur le réseau)."""
    import requests

    session = requests.Session()

    def executer(url: str) -> Reponse:
        rep = session.get(url, timeout=timeout)
        try:
            corps = rep.json()
        except ValueError:
            corps = None
        return Reponse(rep.status_code, corps, dict(rep.headers))

    return executer


@dataclass
class Quota:
    """L'état du quota anonyme, tel que les en-têtes le rendent.

    Ce n'est pas un compteur tenu par le script : il est **lu** à chaque
    réponse. Un compteur local se désynchronise dès qu'un autre outil consomme
    le même quota depuis la même adresse IP — ce qui arrive exactement le jour
    où l'on vérifie à la main en parallèle.
    """

    limite: Optional[int] = None
    restant: Optional[int] = None
    reset: Optional[int] = None
    requetes: int = 0
    attente_totale: float = 0.0

    def lire(self, entetes: dict[str, str]) -> None:
        normalises = {k.lower(): v for k, v in entetes.items()}
        for cle, attribut in (
            ("x-ratelimit-limit", "limite"),
            ("x-ratelimit-remaining", "restant"),
            ("x-ratelimit-reset", "reset"),
        ):
            valeur = normalises.get(cle)
            if valeur is not None:
                try:
                    setattr(self, attribut, int(valeur))
                except ValueError:
                    pass


def _attente_avant_reset(quota: Quota, maintenant: float) -> float:
    """Secondes à patienter jusqu'à la remise à zéro du seau, plus une seconde
    de marge — un réveil pile à la borne retombe sur un `429`."""
    if quota.reset is None:
        return 60.0
    return max(0.0, quota.reset - maintenant) + 1.0


def interroger_revision(
    sha: str,
    fetch: Callable[[str], Reponse],
    quota: Quota,
    dormir: Callable[[float], None] = time.sleep,
    horloge: Callable[[], float] = time.time,
    attente_max: float = 3900.0,
    journal: Callable[[str], None] = lambda m: print(m, file=sys.stderr),
    essais: int = 3,
) -> tuple[str, str]:
    """Un SHA résout-il dans l'archive ? Rend `(etat, detail)`.

    `presente` (200) · `absente` (404) · `indetermine` (tout le reste, quota
    épuisé compris). L'état `indetermine` n'est jamais confondu avec `absente` :
    ne pas trouver et ne pas avoir regardé sont deux choses différentes, et
    c'est la seconde qui doit faire réessayer plutôt que renoncer.
    """
    url = f"{BASE_SWH}/revision/{sha}/"
    for essai in range(1, essais + 1):
        # Temporisation PRÉVENTIVE : si la réponse précédente annonçait un seau
        # vide, on attend le reset au lieu d'aller chercher un 429.
        if quota.restant is not None and quota.restant <= 0:
            attente = _attente_avant_reset(quota, horloge())
            if quota.attente_totale + attente > attente_max:
                return (
                    "indetermine",
                    f"quota épuisé, reset dans {attente:.0f} s — au-delà de "
                    f"--attente-max ({attente_max:.0f} s)",
                )
            journal(
                f"    quota épuisé ({quota.limite or '?'} requêtes/heure) — "
                f"attente de {attente:.0f} s avant de reprendre"
            )
            dormir(attente)
            quota.attente_totale += attente
            quota.restant = None

        try:
            rep = fetch(url)
        except Exception as err:  # réseau, DNS, TLS, timeout
            return "indetermine", f"appel impossible : {type(err).__name__}: {err}"

        quota.requetes += 1
        quota.lire(rep.entetes)

        if rep.code == 200:
            return "presente", ""
        if rep.code == 404:
            return "absente", "404 : révision inconnue de l'archive"
        if rep.code == 429:
            attente = _attente_avant_reset(quota, horloge())
            if essai == essais or quota.attente_totale + attente > attente_max:
                return (
                    "indetermine",
                    f"429 (quota de {quota.limite or 120} requêtes/heure) après "
                    f"{essai} essai(s) — vérification non conclue",
                )
            journal(
                f"    429 sur {sha[:7]} : quota atteint, attente de "
                f"{attente:.0f} s puis nouvel essai"
            )
            dormir(attente)
            quota.attente_totale += attente
            continue
        return "indetermine", f"HTTP {rep.code} inattendu"
    return "indetermine", "essais épuisés"


def interroger_visite(
    origine: str, fetch: Callable[[str], Reponse], quota: Quota
) -> dict[str, Any]:
    """L'état de la dernière visite de l'origine.

    Rend `{"connue": bool, "statut": str|None, "snapshot": str|None,
    "date": str|None, "erreur": str|None}`. `statut == "full"` est la seule
    valeur qui autorise à lire un 404 comme un vrai manque.

    Ses en-têtes de quota sont comptés mais **pas lus** : cette route a son
    propre seau, mesuré à 700 requêtes/heure le 28/08/2026 contre 120 pour
    `/revision/`. Y recopier `restant` et `reset` ferait croire au reste du
    script qu'il dispose de 700 requêtes, et la temporisation ne se
    déclencherait qu'une fois le seau des révisions déjà vidé.
    """
    url = f"{BASE_SWH}/origin/{origine}/visit/latest/"
    try:
        rep = fetch(url)
    except Exception as err:
        return {"connue": False, "erreur": f"{type(err).__name__}: {err}"}
    quota.requetes += 1
    if rep.code == 404:
        return {"connue": False, "erreur": "origine inconnue de Software Heritage"}
    if rep.code != 200 or not isinstance(rep.corps, dict):
        return {"connue": False, "erreur": f"HTTP {rep.code}"}
    return {
        "connue": True,
        "statut": rep.corps.get("status"),
        "snapshot": rep.corps.get("snapshot"),
        "date": rep.corps.get("date"),
        "visite": rep.corps.get("visit"),
        "erreur": None,
    }


# ── Verdict et rapport ───────────────────────────────────────────────────────

VERIFIE, MANQUANTS, INDETERMINE = 0, 1, 2


def rendre_verdict(visite: dict[str, Any], commits: list[CommitCite]) -> tuple[int, str]:
    """Le cœur de la distinction demandée par #568.

    Une visite en cours n'est pas un échec d'archivage. Un SHA absent d'une
    visite `full` en est un. Les confondre ferait renoncer à une coupure
    légitime — ou l'autoriser à tort.
    """
    if not commits:
        return INDETERMINE, (
            "Aucun SHA cité n'a été trouvé : population vide, il n'y a rien à "
            "conclure. Vérifier l'extraction avant de couper quoi que ce soit."
        )

    # Un absent atteignable depuis une ref est un vrai trou d'archive : la
    # coupure le perdrait. Un absent orphelin est déjà perdu aujourd'hui, et
    # couper n'y change rien — il ne bloque donc pas, il se signale.
    absents = [c for c in commits if c.etat == "absente" and not c.orpheline]
    orphelines = [c for c in commits if c.orpheline]
    indetermines = [c for c in commits if c.etat in ("indetermine", "non_verifie")]
    visite_conclue = visite.get("connue") and visite.get("statut") == "full"
    reserve = (
        f" ({len(orphelines)} citation(s) orpheline(s) signalée(s) à part : "
        "commits atteignables depuis aucune ref, jamais archivables, et déjà "
        "irrésolvables pour un tiers.)"
        if orphelines
        else ""
    )

    if indetermines:
        return INDETERMINE, (
            f"{len(indetermines)} SHA sur {len(commits)} n'ont pas pu être "
            "interrogés (quota, réseau, ou réponse inattendue). On n'a rien "
            "établi : réessayer plus tard. NE PAS COUPER."
        )
    if not visite_conclue:
        statut = visite.get("statut") or visite.get("erreur") or "inconnu"
        if absents:
            return INDETERMINE, (
                f"La visite n'est pas `full` (statut : {statut}) et "
                f"{len(absents)} SHA sur {len(commits)} n'y résolvent pas "
                "encore. Ce n'est PAS un échec d'archivage : l'ingestion peut "
                "être en cours. Relancer cette vérification plus tard. "
                "NE PAS COUPER."
            )
        return VERIFIE, (
            f"Les {len(commits)} SHA cités archivables résolvent tous, bien que "
            f"la visite ne soit pas encore `full` (statut : {statut}). La "
            "condition de l'étape 2b est remplie ; attendre `full` reste plus "
            "prudent." + reserve
        )
    if absents:
        return MANQUANTS, (
            f"{len(absents)} SHA cités sur {len(commits)} ne résolvent pas alors "
            "qu'ils sont atteignables depuis une ref, et la visite est `full` : "
            "ce sont de vrais manques, pas une ingestion en cours. NE PAS "
            "COUPER — relancer « Save Code Now », puis revérifier." + reserve
        )
    return VERIFIE, (
        f"Les {len(commits) - len(orphelines)} SHA cités archivables résolvent "
        "tous dans une visite `full`. L'archivage n'est pas un rituel : la "
        "coupure peut suivre." + reserve
    )


def _lieux(commit: CommitCite) -> str:
    lieux = commit.lieux[:MAX_LIEUX_AFFICHES]
    reste = len(commit.lieux) - len(lieux)
    texte = ", ".join(lieux)
    return f"{texte} (+{reste} autre{'s' if reste > 1 else ''})" if reste else texte


def formater_rapport(
    origine: str,
    visite: dict[str, Any],
    commits: list[CommitCite],
    nb_chaines: int,
    nb_md: int,
    nb_issues: int,
    quota: Quota,
    verdict: tuple[int, str],
) -> str:
    code, message = verdict
    etiquette = {VERIFIE: "VÉRIFIÉ", MANQUANTS: "MANQUANTS", INDETERMINE: "INDÉTERMINÉ"}[code]
    lignes = [
        "Vérification d'archivage Software Heritage (#568)",
        f"  origine : {origine}",
    ]

    if visite.get("connue"):
        lignes.append(
            f"  visite n°{visite.get('visite', '?')} : statut "
            f"{visite.get('statut')}, snapshot {visite.get('snapshot') or 'null'}"
            + (f", {visite['date']}" if visite.get("date") else "")
        )
    else:
        lignes.append(f"  visite : NON ÉTABLIE — {visite.get('erreur')}")

    presents = sum(1 for c in commits if c.etat == "presente")
    orphelines = [c for c in commits if c.orpheline]
    absents = [c for c in commits if c.etat == "absente" and not c.orpheline]
    indetermines = [c for c in commits if c.etat in ("indetermine", "non_verifie")]

    lignes += [
        "",
        f"  population : {nb_chaines} chaînes hexadécimales extraites de "
        f"{nb_md} fichiers .md suivis et {nb_issues} corps d'issues",
        "               (commentaires d'issues EXCLUS : la population citée est "
        "un peu plus large),",
        f"               dont {len(commits)} résolvent en commit du dépôt "
        "(`git cat-file -t` == commit).",
        f"  résultat   : {presents} résolvent dans l'archive, "
        f"{len(absents)} manquent, {len(orphelines)} orphelines, "
        f"{len(indetermines)} indéterminés.",
        f"  quota      : {quota.requetes} requêtes émises"
        + (
            f", {quota.restant} restantes sur {quota.limite} par heure"
            if quota.restant is not None
            else ""
        )
        + (
            f", {quota.attente_totale:.0f} s d'attente cumulée"
            if quota.attente_totale
            else ""
        ),
    ]

    # Nommer, pas compter : c'est la demande explicite de #568.
    groupes = (
        ("MANQUANTS — archivables et pourtant absents ; la coupure les perdrait",
         absents),
        ("CITATIONS ORPHELINES — atteignables depuis aucune ref, donc jamais "
         "archivables ;\n  déjà irrésolvables pour un tiers, la coupure n'y "
         "change rien. Corriger la citation,\n  pas l'archive",
         orphelines),
        ("INDÉTERMINÉS — non conclus, ni présents ni absents", indetermines),
    )
    for titre, groupe in groupes:
        if not groupe:
            continue
        lignes += ["", f"  {titre} :"]
        for commit in groupe:
            date = f" ({commit.date[:10]})" if commit.date else ""
            lignes.append(f"    {commit.court}{date} — cité dans {_lieux(commit)}")
            if commit.detail:
                lignes.append(f"        {commit.detail}")

    lignes += ["", f"  VERDICT : {etiquette}", f"  {message}"]
    return "\n".join(lignes)


def rapport_json(
    origine: str,
    visite: dict[str, Any],
    commits: list[CommitCite],
    nb_chaines: int,
    nb_md: int,
    nb_issues: int,
    quota: Quota,
    verdict: tuple[int, str],
) -> dict[str, Any]:
    return {
        "origine": origine,
        "visite": visite,
        "population": {
            "chaines_extraites": nb_chaines,
            "fichiers_md": nb_md,
            "issues": nb_issues,
            "sha_resolus_en_commit": len(commits),
        },
        "verdict": {"code": verdict[0], "message": verdict[1]},
        "quota": {
            "limite": quota.limite,
            "restant": quota.restant,
            "requetes": quota.requetes,
            "attente_totale_s": quota.attente_totale,
        },
        "commits": [
            {
                "sha": c.sha,
                "date": c.date,
                "etat": c.etat,
                "detail": c.detail,
                "atteignable": c.atteignable,
                "ref": c.ref,
                "orpheline": c.orpheline,
                "lieux": c.lieux,
            }
            for c in commits
        ],
    }


# ── Assemblage ───────────────────────────────────────────────────────────────


def verifier(
    racine: str,
    origine: str = ORIGINE_PAR_DEFAUT,
    avec_issues: bool = True,
    fetch: Optional[Callable[[str], Reponse]] = None,
    lire: Optional[Callable[[str], str]] = None,
    lister_md: Optional[Callable[[], list[str]]] = None,
    lister_issues: Optional[Callable[[], list[dict[str, Any]]]] = None,
    batch_check: Optional[Callable[[list[str]], dict[str, Optional[str]]]] = None,
    dater: Optional[Callable[[list[str]], dict[str, str]]] = None,
    ref_contenant: Optional[Callable[[str], Optional[str]]] = None,
    attente_max: float = 3900.0,
    dormir: Callable[[float], None] = time.sleep,
    horloge: Callable[[], float] = time.time,
    journal: Callable[[str], None] = lambda m: print(m, file=sys.stderr),
) -> tuple[int, dict[str, Any], str]:
    """Le déroulé complet. Toutes les dépendances externes — git, `gh`, le
    disque, le réseau — sont injectables : c'est ce qui rend le script
    vérifiable sans jamais joindre l'API depuis la CI (#551 : aucune mesure
    lourde en CI, et la vérification d'archivage est un geste de pré-coupure)."""
    fetch = fetch or _fetch_reel()
    # `errors="replace"` : un .md mal encodé ne doit pas faire renoncer à toute
    # la vérification juste avant une opération irréversible.
    lire = lire or (
        lambda p: Path(p).read_text(encoding="utf-8", errors="replace")
    )
    lister_md = lister_md or (lambda: fichiers_md_suivis(racine))
    batch_check = batch_check or _batch_check_git(racine)
    dater = dater or _dater_git(racine)
    ref_contenant = ref_contenant or _refs_contenant_git(racine)

    fichiers = lister_md()
    citations = citations_des_fichiers_md(racine, lire, fichiers)
    issues: list[dict[str, Any]] = []
    if avec_issues:
        lister_issues = lister_issues or (lambda: corps_des_issues(racine))
        try:
            issues = lister_issues()
        except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError) as err:
            # `gh` absent ou non authentifié : on continue sur les .md seuls,
            # en le disant. Un demi-périmètre annoncé vaut mieux qu'un échec
            # qui pousse à sauter l'étape.
            journal(f"[!] Corps d'issues indisponibles ({err}) — .md seuls.")
        citations += citations_des_issues(issues)

    commits, nb_chaines = resoudre_commits(citations, batch_check, dater)
    journal(
        f"→ {len(commits)} SHA cités résolvent en commit, sur {nb_chaines} "
        f"chaînes hexadécimales extraites de {len(fichiers)} fichiers .md "
        f"et {len(issues)} corps d'issues."
    )

    quota = Quota()
    visite = interroger_visite(origine, fetch, quota)

    for index, commit in enumerate(commits, start=1):
        commit.etat, commit.detail = interroger_revision(
            commit.sha,
            fetch,
            quota,
            dormir=dormir,
            horloge=horloge,
            attente_max=attente_max,
            journal=journal,
        )
        if commit.etat == "absente":
            # Seulement ici : distinguer un trou d'archive d'une citation déjà
            # orpheline ne se pose que pour un SHA effectivement absent.
            commit.ref = ref_contenant(commit.sha)
            commit.atteignable = commit.ref is not None
            commit.detail += (
                f" ; atteignable depuis {commit.ref} — l'archive a un trou"
                if commit.atteignable
                else " ; atteignable depuis AUCUNE ref du clone (branche de PR "
                "récrite ?) : l'origine ne l'a jamais servi, donc Software "
                "Heritage n'a jamais pu le voir. Relancer « Save Code Now » n'y "
                "changera rien — c'est la citation qu'il faut corriger"
            )
        if commit.etat != "presente":
            journal(f"  [{index}/{len(commits)}] {commit.court} : {commit.etat}")

    verdict = rendre_verdict(visite, commits)
    texte = formater_rapport(
        origine, visite, commits, nb_chaines, len(fichiers), len(issues), quota, verdict
    )
    donnees = rapport_json(
        origine, visite, commits, nb_chaines, len(fichiers), len(issues), quota, verdict
    )
    return verdict[0], donnees, texte


def construire_parseur() -> argparse.ArgumentParser:
    """Séparé de `main()` pour être inspectable sans exécuter quoi que ce soit :
    une option citée dans la procédure de bornage et absente d'ici ferait perdre
    le seul lancement disponible avant la coupure."""
    parseur = argparse.ArgumentParser(
        description=(
            "Vérifie que les SHA cités dans les .md suivis et les corps "
            "d'issues résolvent dans Software Heritage (#568)."
        )
    )
    parseur.add_argument("--racine", default=".", help="racine du dépôt git")
    parseur.add_argument("--origine", default=ORIGINE_PAR_DEFAUT)
    parseur.add_argument(
        "--sans-issues",
        action="store_true",
        help="n'extraire que des .md suivis (pas d'appel à `gh`)",
    )
    parseur.add_argument(
        "--attente-max",
        type=float,
        default=3900.0,
        help=(
            "secondes d'attente cumulée tolérées pour respecter le quota "
            "anonyme (120 requêtes/heure). Au-delà, le verdict est INDÉTERMINÉ "
            "plutôt qu'une veille silencieuse."
        ),
    )
    parseur.add_argument("--json", dest="json_out", help="écrit aussi le rapport JSON")
    return parseur


def main(argv: Optional[list[str]] = None) -> int:
    args = construire_parseur().parse_args(argv)

    racine = subprocess.run(
        ["git", "-C", args.racine, "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    code, donnees, texte = verifier(
        racine,
        origine=args.origine,
        avec_issues=not args.sans_issues,
        attente_max=args.attente_max,
    )
    print(texte)
    if args.json_out:
        Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_out).write_text(
            json.dumps(donnees, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"→ Rapport JSON écrit : {args.json_out}", file=sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
