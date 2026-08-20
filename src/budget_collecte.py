"""Budget de temps mur pour une phase de collecte réseau (#498).

Pourquoi un budget INTERNE alors qu'un `timeout-minutes` existe déjà.
`timeout-minutes` borne le *job*, pas la collecte : il couvre aussi
`actions/checkout`, `setup-python`, `pip install`, la restauration des caches
et le téléchargement de l'artifact d'amendements. Mesuré sur les 29 shards
`extract-an` des runs 32233766814, 32288588518, 32302557156 et 32379928098,
ce préambule va de **30 s à 193 s** — soit, sur un timeout de 5 min, entre
107 s et 270 s réellement laissés à l'extraction, sans que rien ne le dise.
Un budget exprimé en secondes de collecte est stable là où le timeout de job
ne l'est pas.

Et surtout : un dépassement de `timeout-minutes` tue le process. GitHub
affiche `##[error]The operation was canceled`, qui ne dit ni combien avait été
collecté, ni où la collecte en était — et `generate_all_profiles.py` n'atteint
jamais son écriture de profil, donc le shard publie **zéro** profil (constaté
sur les 4 shards tués du run 32302557156 et les 5 du run 32379928098 :
« Publication : 0 profil(s) écrits par ce job »). Un budget interne, lui, rend
la main : ce qui est collecté est écrit, et ce qui ne l'est pas est déclaré
dans `meta.warnings[]` (règle éditoriale 2.5 — une collecte tronquée ne doit
jamais se lire comme une collecte complète).

Même famille que les watchdogs de `download_watchdog.py` (#370) et de
`candidate_profile._get_with_watchdog` (#340), à un étage au-dessus : ceux-là
bornent UNE requête, celui-ci borne l'agrégat d'une phase.
"""

from __future__ import annotations

import os
import sys
import threading
import time
from contextlib import contextmanager
from typing import Iterator, Optional


class BudgetCollecte:
    """Budget de temps mur consommé par les sections déclarées avec `section()`.

    Le temps ne court QUE dans une section : le budget d'une phase n'est pas
    entamé par le travail des autres phases du même profil (votes, amendements,
    textes portés), qui n'ont rien à voir avec lui.

    Les unités non collectées sont comptées par `ignorer()` et restituées par
    `message()` : un budget épuisé sans trace de ce qu'il a coûté serait
    exactement la valeur par défaut silencieuse que la règle 2.5 interdit.

    Thread-safe : `epuise()` et `ignorer()` sont appelés depuis le pool de
    threads qui récupère les détails d'intervention (`max_workers=4`).
    """

    def __init__(self, secondes: float, libelle: str = "collecte") -> None:
        if secondes <= 0:
            raise ValueError(
                f"budget de {libelle} invalide : {secondes} s. Un budget nul ou négatif "
                "n'est pas 'pas de budget' — passer None à l'appelant pour cela."
            )
        self.secondes = float(secondes)
        self.libelle = libelle
        self._lock = threading.Lock()
        self._consomme = 0.0
        self._profondeur = 0
        self._debut_racine: Optional[float] = None
        self._ignores: dict[str, int] = {}

    # -- Consommation ------------------------------------------------------

    @contextmanager
    def section(self, nom: str) -> Iterator["BudgetCollecte"]:
        """Compte le temps mur passé dans le bloc. Réentrant : seule la section
        la plus externe compte, pour qu'une section imbriquée ne facture pas
        deux fois la même seconde."""
        _ = nom  # nom conservé pour la lisibilité des appels, pas pour le calcul
        with self._lock:
            if self._profondeur == 0:
                self._debut_racine = time.monotonic()
            self._profondeur += 1
        try:
            yield self
        finally:
            with self._lock:
                self._profondeur -= 1
                if self._profondeur == 0 and self._debut_racine is not None:
                    self._consomme += time.monotonic() - self._debut_racine
                    self._debut_racine = None

    def _ecoule_sans_verrou(self) -> float:
        ecoule = self._consomme
        if self._profondeur > 0 and self._debut_racine is not None:
            ecoule += time.monotonic() - self._debut_racine
        return ecoule

    def consomme(self) -> float:
        """Secondes déjà consommées, section en cours incluse."""
        with self._lock:
            return self._ecoule_sans_verrou()

    def restant(self) -> float:
        """Secondes restantes, jamais négatif."""
        return max(0.0, self.secondes - self.consomme())

    def epuise(self) -> bool:
        return self.consomme() >= self.secondes

    # -- Ce qui n'a pas été collecté ---------------------------------------

    def ignorer(self, unite: str, nombre: int = 1) -> None:
        """Enregistre `nombre` unités non collectées faute de budget."""
        if nombre <= 0:
            return
        with self._lock:
            self._ignores[unite] = self._ignores.get(unite, 0) + nombre

    def unites_ignorees(self) -> dict[str, int]:
        with self._lock:
            return dict(self._ignores)

    def message(self) -> Optional[str]:
        """Description de la troncature, ou None si rien n'a été ignoré.

        None quand le budget a suffi — y compris s'il a été frôlé : ce qui doit
        être signalé, c'est une collecte incomplète, pas un budget serré.
        """
        ignores = self.unites_ignorees()
        if not ignores:
            return None
        details = ", ".join(f"{nombre} {unite}" for unite, nombre in ignores.items())
        return (
            f"budget de {self.libelle} épuisé après {self.consomme():.0f} s "
            f"(plafond {self.secondes:.0f} s) — non collecté : {details}"
        )


# -- Helpers tolérants au budget absent ------------------------------------
# Un budget optionnel truffe sinon les appelants de `if budget is not None`,
# et c'est exactement le genre de garde qu'on oublie sur un chemin.


@contextmanager
def section(budget: Optional[BudgetCollecte], nom: str) -> Iterator[Optional[BudgetCollecte]]:
    """`budget.section(nom)`, ou un no-op si `budget` est None."""
    if budget is None:
        yield None
        return
    with budget.section(nom):
        yield budget


def epuise(budget: Optional[BudgetCollecte]) -> bool:
    """False si `budget` est None : pas de budget = pas d'épuisement."""
    return budget is not None and budget.epuise()


def ignorer(budget: Optional[BudgetCollecte], unite: str, nombre: int = 1) -> None:
    if budget is not None:
        budget.ignorer(unite, nombre)


def annoncer_troncature(budget: Optional[BudgetCollecte], contexte: str) -> Optional[str]:
    """Imprime la troncature (stderr + annotation GHA) et renvoie son message.

    Renvoie None si rien n'a été tronqué — l'appelant n'a alors aucun
    avertissement à consigner.
    """
    if budget is None:
        return None
    message = budget.message()
    if message is None:
        return None
    print(f"  [!] {contexte} : {message}", file=sys.stderr)
    if os.getenv("GITHUB_ACTIONS") == "true":
        propre = message.replace("\n", " ").replace("\r", "")
        print(f"::warning::{contexte} : {propre}", flush=True)
    return message
