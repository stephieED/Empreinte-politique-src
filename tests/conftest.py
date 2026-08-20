"""Garde-fous partagés par toute la suite.

**Aucun test ne doit toucher le réseau** (AGENTS.md §3, #473 — un test qui
appelait réellement `archive.nossenateurs.fr` coûtait 16 des 35 s d'un fichier).
Depuis #488, `generate_all_profiles` charge un index des slugs connus du Sénat
en une requête par process : sans le neutraliser ici, chaque test passant par
`process_candidat` rouvrirait cette requête (mesuré : 13,4 s pour ce seul
fichier de tests, contre 0,5 s une fois la doublure en place).

La doublure par défaut renvoie un index **vide et disponible** — « le Sénat ne
connaît aucun de ces slugs » — ce qui est le cas de tous les slugs inventés par
la suite. Un test qui veut l'inverse remplace `slugs_connus_du_senat` lui-même ;
un test qui veut la vraie fonction demande la fixture
`slugs_connus_du_senat_reel` (et fournit sa propre doublure de réseau).
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

_SLUGS_CONNUS_REEL = None


@pytest.fixture(autouse=True)
def _index_senat_hors_ligne(monkeypatch):
    global _SLUGS_CONNUS_REEL
    import generate_all_profiles

    if _SLUGS_CONNUS_REEL is None:
        _SLUGS_CONNUS_REEL = generate_all_profiles.slugs_connus_du_senat

    generate_all_profiles._reinitialiser_index_senat()

    def _interdit(*args, **kwargs):
        raise AssertionError(
            "fetch_full_roster() appelé depuis un test sans doublure : aucun test "
            "ne doit toucher le réseau (AGENTS.md §3, #473)."
        )

    monkeypatch.setattr(generate_all_profiles, "fetch_full_roster", _interdit)
    monkeypatch.setattr(generate_all_profiles, "slugs_connus_du_senat", lambda: frozenset())
    yield
    generate_all_profiles._reinitialiser_index_senat()


@pytest.fixture
def slugs_connus_du_senat_reel(_index_senat_hors_ligne):
    """La vraie `slugs_connus_du_senat`, que la doublure autouse a remplacée
    dans le module. À n'utiliser qu'avec une doublure de `fetch_full_roster`."""
    return _SLUGS_CONNUS_REEL
