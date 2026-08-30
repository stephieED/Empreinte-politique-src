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

Ce fichier porte depuis un **second** garde-fou, sans rapport avec le premier :
le hook `pytest_runtest_makereport` de la fin du fichier, qui nomme la cause
probable quand un test échoue sur un fichier que le sparse-checkout ne
télécharge pas. Son docstring porte le pourquoi.
"""

import os
import sys
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
# `tests/` sur le chemin d'import **avant** `_outils_ci` : le seul analyseur du
# bloc `sparse-checkout:` du dépôt y vit, et un conftest ne peut pas importer un
# module de test. Poser le chemin ici plutôt que compter sur l'`--import-mode`
# de pytest fait que les tests qui importent le même module voient le même objet.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import _outils_ci  # noqa: E402  (l'import dépend du sys.path ci-dessus)

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


# ---------------------------------------------------------------------------
# Second garde-fou du fichier : diagnostiquer le piège du sparse-checkout.
# ---------------------------------------------------------------------------

#: Racine du dépôt et fichier de workflow : repris de `_outils_ci`, le seul
#: analyseur du bloc `sparse-checkout:`. Les réexporter ici garde le hook
#: lisible et laisse un test pointer `WORKFLOW_TESTS` ailleurs.
RACINE_DEPOT = _outils_ci.RACINE_DEPOT
WORKFLOW_TESTS = _outils_ci.WORKFLOW_TESTS

MESSAGE_HORS_LISTE_BLANCHE = (
    "Ce chemin n'est pas dans le `sparse-checkout` de "
    "`.github/workflows/tests.yml`. En CI, il n'est pas téléchargé — c'est "
    "probablement la cause, pas ton test. Ajouter son répertoire de premier "
    "niveau à la liste blanche."
)

#: Les deux exclusions volontaires (#473) : leur conseiller la liste blanche
#: serait un mauvais conseil, le garde-fou du workflow refuse leur présence.
CORPUS_HORS_CHECKOUT = ("pivot_data", "raw_data/profiles")

RAPPEL_CORPUS = (
    "Sauf que ce chemin-là est exclu **exprès** (#473, AGENTS.md §3b) et que le "
    "garde-fou du workflow refuse de le voir apparaître : ne pas l'inscrire dans "
    "la liste blanche — le test doit lire une fixture figée sous tests/fixtures/."
)


@lru_cache(maxsize=1)
def _liste_blanche_sparse_checkout() -> frozenset[str] | None:
    """Entrées du bloc `sparse-checkout: |` de `tests.yml`, ou `None`.

    Lue à la **première défaillance** qui la demande, jamais au chargement :
    une suite verte ne touche pas le fichier. `None` dès que quoi que ce soit
    cloche (fichier absent, bloc introuvable, bloc vide) — le hook se tait
    alors, plutôt que de transformer un échec de test en erreur de collecte.

    Piège récursif assumé : ce fichier est lui-même hors du disque du runner si
    `.github` quitte la liste blanche. Il y est (et `tests/test_ci_perimetre_
    sparse_checkout.py` le vérifie) ; s'il en sortait, ce hook deviendrait muet
    sans rien casser d'autre.

    L'analyse vit dans `tests/_outils_ci.py`, partagée avec les deux tests qui
    lisent le même bloc : ici, seule la mise en cache est locale.
    """
    return _outils_ci.lire_liste_blanche(WORKFLOW_TESTS)


def _chemin_du_fichier_absent(exception: BaseException | None) -> str | None:
    """Le chemin nommé par le premier `FileNotFoundError` de la chaîne.

    `None` si l'échec est autre chose, ou si l'erreur ne nomme aucun fichier
    (`raise FileNotFoundError("gh")` : on ne devine pas ce qu'elle voulait dire).
    """
    vues: set[int] = set()
    tete = exception
    while tete is not None and id(tete) not in vues:
        vues.add(id(tete))
        if isinstance(tete, FileNotFoundError) and tete.filename is not None:
            try:
                return os.fsdecode(tete.filename)
            except (TypeError, ValueError):
                return None
        tete = tete.__cause__ or tete.__context__
    return None


def _relatif_hors_liste_blanche(chemin: str) -> str | None:
    """Le chemin relatif à la racine s'il échappe à la liste blanche, sinon `None`.

    Trois raisons de se taire, toutes du côté « dans le doute, rien » :
    la liste est illisible ; le chemin sort du dépôt (un `tmp_path`, un fichier
    système — la CI ne l'aurait pas téléchargé davantage en local) ; une entrée
    de la liste le couvre, en préfixe de composants (`raw_data/groupes_reels.json`
    couvre ce seul fichier, `docs` couvre tout ce qui est dessous).
    """
    blanche = _liste_blanche_sparse_checkout()
    if not blanche:
        return None
    try:
        absolu = Path(chemin)
        if not absolu.is_absolute():
            absolu = Path.cwd() / absolu
        relatif = absolu.resolve().relative_to(RACINE_DEPOT)
    except (OSError, ValueError, RuntimeError):
        return None
    composants = relatif.parts
    if not composants:
        return None
    for entree in blanche:
        attendus = tuple(entree.split("/"))
        if composants[:len(attendus)] == attendus:
            return None
    return relatif.as_posix()


#: Titre de la section ajoutée au rapport d'échec.
TITRE_SECTION = "Chemin hors du sparse-checkout de la CI"


def _corps_du_diagnostic(relatif: str) -> str:
    """Le texte ajouté au rapport, pour un chemin relatif hors liste blanche.

    Séparé du hook pour être éprouvable sans provoquer d'échec réel
    (`tests/test_hook_diagnostic_sparse_checkout.py`).
    """
    corps = f"{relatif}\n\n{MESSAGE_HORS_LISTE_BLANCHE}"
    if any(relatif == exclu or relatif.startswith(exclu + "/")
           for exclu in CORPUS_HORS_CHECKOUT):
        corps = f"{corps}\n\n{RAPPEL_CORPUS}"
    return corps


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item, call):
    """Ajoute au rapport d'échec la cause probable : le fichier n'a jamais été téléchargé.

    LE PIÈGE. `.github/workflows/tests.yml` ne matérialise qu'une **liste
    blanche** de chemins (`sparse-checkout`), pour ne pas poser sur le runner
    les 8,4 Go de corpus (`raw_data/profiles/`, `pivot_data/`) — la suite passe
    de 4 min 30 à 41 s, et le critère « aucun test ne lit le corpus vivant »
    (#473) devient structurel au lieu d'audité une fois. Le prix : la liste
    s'écrit à la main, donc elle s'oublie. Un test qui lit un fichier hors liste
    **passe en local et échoue en CI**, sur un `FileNotFoundError` qui ne dit
    rien de la vraie cause. On cherche alors un bug dans le test, pendant que le
    fichier n'a simplement jamais été téléchargé.

    TROIS OCCURRENCES. #434, les 10 tests de `scripts/borner_historique_donnees.sh`,
    dès le premier run du workflow. #520, `.gitignore` lu par
    `test_ci_roster_unique_par_run.py` : suite verte en local, rouge sur le push
    vers `main` (run `32773016491`), découverte après fusion. Puis le 30/08/2026,
    `CLAUDE.md` lu par `test_instructions_agents.py`. Les deux dernières fois,
    l'avertissement était **déjà écrit deux lignes au-dessus** de la liste qu'on
    oubliait de compléter : une prose qui prévient ne prévient personne.

    POURQUOI DIAGNOSTIQUER PLUTÔT QUE PRÉVENIR. Prévenir demande de savoir ce que
    la suite lira, donc de lire tout le code de test. `test_ci_perimetre_sparse_
    checkout.py` le fait déjà pour les **littéraux** ancrés à la racine, et
    `test_instructions_agents.py` pour ses propres alias : c'est la moitié qui
    échoue en local, et elle reste la première ligne de défense. Pousser
    l'analyse plus loin — chemins construits, `os.path.join`, indirections —
    coûterait cher et produirait des faux positifs, *et un garde-fou qui crie
    pour rien finit désactivé*. Ce hook prend l'autre moitié : il ne cherche pas
    à empêcher la chute, il supprime les vingt minutes passées à chercher au
    mauvais endroit après coup. Son public est la personne qui lit un journal de
    CI rouge.

    CE QU'IL COÛTE. Rien sur un test qui passe : la première chose lue est
    `rapport.failed`. `tests.yml` n'est ouvert qu'à la première défaillance qui
    ressemble au piège, et une seule fois (`lru_cache`). Rien n'est jamais écrit
    en sortie standard ; le texte s'ajoute au rapport de l'échec, là où on le lit.

    CE QU'IL NE FAIT PAS. Il ne parle que si l'échec est bien un fichier absent
    **et** que le chemin manquant n'est effectivement couvert par aucune entrée
    de la liste blanche, lue depuis `tests.yml` et jamais recopiée ici. Toute
    autre situation — assertion ordinaire, chemin couvert, chemin hors dépôt,
    liste illisible — le laisse muet. En local le fichier existe : il ne se
    déclenche pas, et c'est le comportement attendu.

    CE QUI LE VERROUILLE. `tests/test_hook_diagnostic_sparse_checkout.py`, qui
    appelle les fonctions ci-dessus et pilote ce hook directement, sans faire
    échouer de test. Une aide au diagnostic qui cesse de fonctionner sans le
    dire est pire que pas d'aide : on finit par faire confiance à un silence
    qui ne veut plus rien dire.
    """
    rapport = yield
    try:
        if rapport.failed and call.excinfo is not None:
            chemin = _chemin_du_fichier_absent(call.excinfo.value)
            if chemin is not None:
                relatif = _relatif_hors_liste_blanche(chemin)
                if relatif is not None:
                    rapport.sections.append(
                        (TITRE_SECTION, _corps_du_diagnostic(relatif)))
    except Exception:
        pass  # un diagnostic ne masque jamais l'échec qu'il commente
    return rapport
