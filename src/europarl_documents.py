#!/usr/bin/env python3
"""
europarl_documents.py — De la référence citée dans un intitulé de vote à
l'adresse vérifiée du document qu'elle désigne (#827).

## Le problème

Les explications de vote du Parlement européen sont la seule matière du corpus
européen où le candidat écrit lui-même pourquoi il a voté ainsi. ParlTrack en
transcrit le texte, mais **ne donne aucun lien** : mesuré le 10/09/2026 sur les
7 candidats déclarés ayant un mandat européen, **0 des 1 801 entrées `WEXP`**
porte une `url` ou un `formats[]`, alors que les neuf autres types d'activité
en portent **100 %**. Le trou est d'un seul type, pas de la source.

## Ce que l'intitulé donne, et ce qu'il ne donne pas

L'intitulé cite le document entre parenthèses :

    Mobilisation of the EGF: application EGF/2016/008 FI/Nokia (A8-0196/2017 - Petri Sarvamaa) FR

**1 530 des 1 801** entrées (85 %) en portent une. Les 271 autres n'en portent
aucune — leur intitulé est en prose (« Allocation of slots at Community
airports: common rules ») — et n'auront donc **jamais** de lien : c'est un fait
sur la source, pas une lacune de la collecte (§2 règle 5).

## Pourquoi l'adresse est dérivée mais l'existence prouvée

L'adresse publique se déduit de la référence. **Sa validité, non** :
`www.europarl.europa.eu` est derrière un pare-feu anti-robot AWS qui répond
`HTTP 202`, 0 octet, `x-amzn-waf-action: challenge` — *identiquement* pour une
URL vraie et pour une URL inventée, même avec un User-Agent de navigateur.
Aucun job ne peut donc vérifier ces adresses, ni à la collecte, ni au contrôle
qualité, ni jamais.

Publier une URL dérivée sans preuve fabriquerait des liens morts indétectables
— **22 sont déjà connus**, dont 17 documents transmis par une autre institution
(type `C`) et une coquille de la source (`A9-0390/2017` annonce le terme 9 pour
2017, alors qu'il commence en 2019). Ce serait contraire à §2 règle 2.

D'où la règle : **l'existence est établie sur `data.europarl.europa.eu`**, qui
n'a pas de pare-feu et répond `200` ou `404`, puis l'adresse publique est écrite
pour le lecteur.

Éprouvé le 10/09/2026 sur **18 URL** ouvertes une à une dans un navigateur —
seule façon de franchir le défi anti-robot : les **13** documents que le portail
confirme s'ouvrent, les **5** contrôles négatifs échouent. **Zéro divergence.**
L'échantillon couvre 2015→2024, les types `A`, `B` et `RC`, et six documents
dont le portail n'expose qu'un PDF — le format servi par le portail n'a aucune
incidence sur l'existence de la page publique.

**Cette équivalence est éprouvée, jamais surveillée.** 18 URL, pas 1 508, et le
pare-feu interdit tout contrôle continu : si le Parlement change sa chaîne de
publication, rien ne nous en avertira.

## Le débit du portail se déclare en le dépassant

Aucune réponse `200` ne porte d'en-tête de limite. Une première passe sans
pause a rendu **1 320 réponses `429` sur 1 424** — mesure entièrement perdue.
La limite ne s'annonce qu'une fois franchie, par `HTTP 429` + `Retry-After: 60`.
Reprise à une requête toutes les 0,6 s : 47 minutes, **13 blocages de 60 s**
malgré la pause. D'où le cache disque, qui rend la seconde passe gratuite, et le
respect du `Retry-After`, sans lequel un job perd son heure comme la première
passe a perdu la sienne.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Optional

import requests

#: Le portail open data — pas de pare-feu, répond 200 ou 404.
PORTAIL_API = "https://data.europarl.europa.eu/api/v2"

#: Le site public — lisible par un humain, invérifiable par un job.
DOCEO_BASE = "https://www.europarl.europa.eu/doceo/document"

CACHE_DIR = Path(".cache") / "europarl"
CACHE_DOCUMENTS = CACHE_DIR / "documents_doceo.json"

#: Une requête toutes les 0,6 s — le débit que le portail tolère avant de
#: répondre 429. Mesuré : il en reste 13 sur 1 320 requêtes, d'où le respect
#: du `Retry-After` en plus de la pause.
PAUSE_ENTRE_REQUETES = 0.6
DELAI_REPLI_429 = 60
MAX_ESSAIS = 4
TIMEOUT = 30

#: La référence telle que l'intitulé la cite, entre parenthèses.
#: `(A8-0196/2017 - Petri Sarvamaa)` ou `(RC-B8-0292/2018)`.
_RE_REFERENCE = re.compile(r"\((RC-)?([ABC])(\d{1,2})-(\d{4})/(\d{4})")


def reference_doceo(intitule: Any) -> Optional[str]:
    """La référence de document citée dans un intitulé, en forme `doceo`.

    Deux formes, et la seconde n'est pas une variante de la première :

    - `B8-0240/2017`     → `B-8-2017-0240`
    - `RC-B8-0292/2018`  → `RC-8-2018-0292`  — **la lettre disparaît**

    Vérifié sur 79 785 paires du corpus européen, 0 divergence, puis éprouvé
    dans un navigateur sur deux `RC-` : c'est la conversion la plus risquée du
    lot, parce qu'une lettre gardée par erreur produirait une URL fausse et
    silencieuse.

    `None` si l'intitulé ne cite aucun document — 271 des 1 801 explications.
    """
    if not isinstance(intitule, str):
        return None
    m = _RE_REFERENCE.search(intitule)
    if not m:
        return None
    resolution_commune, lettre, legislature, numero, annee = m.groups()
    if resolution_commune:
        return f"RC-{legislature}-{annee}-{numero}"
    return f"{lettre}-{legislature}-{annee}-{numero}"


def url_doceo(doceo: str) -> str:
    """L'adresse publique du document, celle qu'un lecteur peut ouvrir.

    Fonction **pure** : elle écrit une adresse, elle ne prouve rien. Son
    résultat ne se publie qu'après `ResolveurDocuments.existe()`.
    """
    return f"{DOCEO_BASE}/{doceo}_FR.html"


class ResolveurDocuments:
    """Dit si un document existe, en interrogeant le portail open data.

    Le cache disque est la pièce maîtresse, pas une optimisation : sans lui,
    chaque run repaie 47 minutes pour un corpus qui ne bouge pas. Une entrée
    négative (404) est mise en cache **comme les autres** — c'est un fait établi
    sur le document, pas un échec de collecte.

    `session` est injectable pour que les tests n'aient jamais besoin du réseau,
    que `tests/conftest.py` refuse depuis #473.
    """

    def __init__(
        self,
        cache_path: Optional[Path] = None,
        session: Optional[Any] = None,
        hors_ligne: bool = False,
    ) -> None:
        self.cache_path = Path(cache_path) if cache_path else CACHE_DOCUMENTS
        self.session = session
        self.hors_ligne = hors_ligne
        self._cache: dict[str, bool] = self._charger()
        self._interroges = 0
        self._refuses = 0

    def _charger(self) -> dict[str, bool]:
        try:
            with open(self.cache_path, encoding="utf-8") as fh:
                document = json.load(fh)
        except (OSError, json.JSONDecodeError):
            return {}
        entrees = document.get("documents") if isinstance(document, dict) else None
        return {k: bool(v) for k, v in entrees.items()} if isinstance(entrees, dict) else {}

    def enregistrer(self) -> None:
        """Écrit le cache. À appeler une fois, en fin de passe."""
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cache_path, "w", encoding="utf-8") as fh:
            json.dump(
                {"schema_version": "documents-doceo-v1", "documents": self._cache},
                fh, ensure_ascii=False,
            )

    def existe(self, doceo: str) -> Optional[bool]:
        """`True` si le document existe, `False` s'il est introuvable.

        `None` quand la question n'a pas pu être posée — hors ligne, ou portail
        injoignable. **Ce n'est pas `False`** : une ignorance publiée comme un
        fait négatif est exactement ce que §2 règle 5 interdit, et l'appelant
        doit pouvoir distinguer « ce document n'existe pas » de « nous n'avons
        pas pu demander ».
        """
        if doceo in self._cache:
            return self._cache[doceo]
        if self.hors_ligne or self.session is None:
            return None
        resultat = self._interroger(doceo)
        if resultat is not None:
            self._cache[doceo] = resultat
        return resultat

    def _interroger(self, doceo: str) -> Optional[bool]:
        url = f"{PORTAIL_API}/documents/{doceo}"
        params = {"language": "fr", "format": "application/ld+json"}
        for _ in range(MAX_ESSAIS):
            try:
                reponse = self.session.get(url, params=params, timeout=TIMEOUT)
            except Exception:
                return None
            self._interroges += 1
            if reponse.status_code == 429:
                self._refuses += 1
                attente = reponse.headers.get("Retry-After")
                try:
                    delai = int(attente)
                except (TypeError, ValueError):
                    delai = DELAI_REPLI_429
                time.sleep(delai + 1)
                continue
            time.sleep(PAUSE_ENTRE_REQUETES)
            if reponse.status_code == 404:
                return False
            if reponse.status_code == 200:
                return True
            return None
        return None

    def url_verifiee(self, intitule: Any) -> Optional[str]:
        """L'adresse du document cité par cet intitulé, si et seulement si il existe.

        `None` dans les trois cas où rien ne peut être publié : aucune référence
        citée, document introuvable, ou question non posée. Les trois se
        comptent séparément chez l'appelant — ils ne disent pas la même chose.
        """
        doceo = reference_doceo(intitule)
        if doceo is None:
            return None
        return url_doceo(doceo) if self.existe(doceo) else None

    @property
    def statistiques(self) -> dict[str, int]:
        return {
            "documents_connus": len(self._cache),
            "requetes": self._interroges,
            "refus_429": self._refuses,
        }


def resolveur_par_defaut(hors_ligne: bool = False) -> ResolveurDocuments:
    """Le résolveur du pipeline : cache du dépôt, session `requests` réelle."""
    return ResolveurDocuments(
        session=None if hors_ligne else requests.Session(),
        hors_ligne=hors_ligne,
    )
