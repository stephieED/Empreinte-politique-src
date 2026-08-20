"""Garde-fou partagé par toute la suite : **aucun test ne sort sur le réseau**.

AGENTS.md §3 l'exige depuis #473 — un test qui appelait réellement
`archive.nossenateurs.fr` coûtait 16 des 35 s d'un fichier. C'était jusqu'ici
une règle **auditée une fois**, pas une règle tenue : rien n'empêchait un test
neuf de rouvrir une socket. #488 l'a vérifié à ses dépens — une seule requête
ajoutée dans le chemin de `process_candidat` a fait passer
`test_generate_all_profiles.py` de 0,50 s à 13,4 s, sans qu'aucun test échoue.

La fixture ci-dessous coupe `requests` à sa couche la plus basse
(`Session.send`, par où passent `requests.get`, `requests.post` et toute
session construite ailleurs) et **échoue bruyamment** en nommant l'URL.

**La boucle locale reste ouverte** : 11 tests de `test_amendements_download_modes`
montent un `http.server` sur `127.0.0.1` pour éprouver la reprise par `Range`
sur un vrai socket. C'est une doublure, pas une source tierce — le critère est
« sortir de la machine », pas « parler HTTP ». Un test qui a besoin d'une
réponse d'un hôte distant fournit sa propre doublure, comme le reste de la
suite le fait déjà.

Le sparse-checkout du workflow de tests couvre l'autre moitié de la règle
(le corpus vivant est absent du disque en CI) ; celle-ci couvre le réseau.
"""

import sys
from pathlib import Path
from urllib.parse import urlsplit

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

HOTES_AUTORISES = frozenset({"127.0.0.1", "localhost", "::1", "[::1]"})


class ReseauInterditDansLesTests(AssertionError):
    """Levée quand un test tente une requête HTTP vers un hôte distant
    (AGENTS.md §3, #473)."""


def _est_boucle_locale(url: str) -> bool:
    return (urlsplit(url).hostname or "").lower() in HOTES_AUTORISES


@pytest.fixture(autouse=True)
def _reseau_coupe(monkeypatch):
    envoyer_reel = requests.sessions.Session.send

    def _filtrer(self, request, **kwargs):
        url = getattr(request, "url", "") or ""
        if _est_boucle_locale(url):
            return envoyer_reel(self, request, **kwargs)
        raise ReseauInterditDansLesTests(
            f"Requête HTTP réelle vers {url or '?'} depuis un test. Aucun test ne "
            "doit sortir sur le réseau (AGENTS.md §3, #473) : remplace l'appel par "
            "une doublure, ou sers la réponse depuis 127.0.0.1."
        )

    monkeypatch.setattr(requests.sessions.Session, "send", _filtrer)
