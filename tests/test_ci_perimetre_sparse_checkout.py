"""Le sparse-checkout de `tests.yml` couvre ce que la suite lit (#518).

`.github/workflows/tests.yml` ne matérialise sur le disque du runner qu'une
**liste blanche** de chemins : c'est ce qui rend structurel le critère « aucun
test ne lit le corpus vivant » (#473), et c'est aussi un piège à sens unique.
Un test qui lit un fichier hors liste **passe en local et échoue en CI**, avec
un `FileNotFoundError` qui ne dit rien de la cause.

Le piège s'est refermé deux fois :

  - #434 — les 10 tests de `scripts/borner_historique_donnees.sh`, dès le
    premier run du workflow ;
  - #520 — `tests/test_ci_roster_unique_par_run.py` lit `.gitignore`, absent de
    la liste. Suite verte en local (2 109 tests), rouge sur le push vers `main`
    (run `32773016491`). Un fichier de premier niveau compte autant qu'un
    répertoire, ce que le commentaire de la liste ne disait pas.

Ce test transforme cette panne en échec **local**. Il ne devine pas ce que la
suite lit : il relève les littéraux de chemin ancrés à la racine du dépôt
(`RACINE`, `ROOT`, `REPO_ROOT`, `parents[1]`, suivis d'un nom entre guillemets)
et vérifie que chacun est couvert — ce fichier compris, d'où l'absence
d'exemple littéral dans cette prose : il se relèverait lui-même.
Un test qui lirait un chemin construit dynamiquement lui échapperait —
mais la convention du dépôt est le littéral, et c'est sous cette forme que les
deux incidents se sont produits.

Volontairement sans PyYAML (absent de requirements.txt), comme les autres
gardes-fous de workflow de ce dépôt.
"""

import re
from pathlib import Path

import _outils_ci

RACINE = Path(__file__).resolve().parents[1]
WORKFLOW = RACINE / ".github" / "workflows" / "tests.yml"

#: Les noms sous lesquels la racine du dépôt est désignée dans les tests.
#: `parents[1]` est la forme inline de `Path(__file__).resolve().parents[1]`.
_ANCRES = r"(?:RACINE|ROOT|REPO_ROOT|parents\[1\])"

#: `ANCRE / "a"` ou `ANCRE / "a" / "b"`. Deux composants suffisent : la liste
#: blanche ne descend jamais plus bas (`raw_data/groupes_reels.json`).
_LITTERAL = re.compile(_ANCRES + r'\s*/\s*"([^"/]+)"(?:\s*/\s*"([^"/]+)")?')


def _liste_blanche() -> frozenset[str]:
    """Entrées du bloc `sparse-checkout: |` de `tests.yml`.

    L'analyse est celle de `tests/_outils_ci.py`, partagée avec `conftest.py`
    et `test_instructions_agents.py` — trois lecteurs, un seul format à
    corriger le jour où le bloc change. Elle rend `None` au lieu de lever :
    ici, un bloc devenu illisible doit échouer, et bruyamment.
    """
    blanche = _outils_ci.lire_liste_blanche(WORKFLOW)
    assert blanche, (
        "bloc `sparse-checkout: |` absent, vide ou de forme inattendue dans "
        "tests.yml — voir `tests/_outils_ci.lire_liste_blanche`.")
    return blanche


def _chemins_lus() -> set[tuple[str, ...]]:
    """Chemins ancrés à la racine, relevés dans tous les fichiers de tests."""
    trouves = set()
    for fichier in sorted(Path(__file__).parent.glob("*.py")):
        for premier, second in _LITTERAL.findall(
                fichier.read_text(encoding="utf-8")):
            trouves.add((premier, second) if second else (premier,))
    return trouves


def test_la_liste_blanche_couvre_tout_ce_que_la_suite_lit():
    blanche = _liste_blanche()
    non_couverts = sorted(
        "/".join(chemin) for chemin in _chemins_lus()
        if chemin[0] not in blanche and "/".join(chemin) not in blanche
    )
    assert not non_couverts, (
        "ces chemins sont lus par la suite mais absents du sparse-checkout de "
        f"tests.yml — ils passeront en local et échoueront en CI : {non_couverts}")


def test_gitignore_est_dans_la_liste_blanche():
    """Le cas de #520, nommé : `test_le_roster_brut_n_est_pas_committe` lit
    `.gitignore` pour vérifier que `raw_data/rosters_bruts.json` n'est pas
    committé. Le retirer de la liste blanche casserait la CI et rien d'autre."""
    assert ".gitignore" in _liste_blanche()


def test_le_corpus_vivant_reste_hors_de_la_liste_blanche():
    """L'autre sens de la liste, et celui-là ne doit jamais céder (#473) : le
    garde-fou du workflow refuse `pivot_data/` et `raw_data/profiles/` sur le
    disque. Les inscrire ici les y ramènerait."""
    blanche = _liste_blanche()
    assert "pivot_data" not in blanche
    assert not any(e.startswith("raw_data/profiles") for e in blanche)
    assert not any(e == "raw_data" for e in blanche), (
        "`raw_data` entier ramènerait `raw_data/profiles/` : n'inscrire que "
        "les fichiers de configuration lus par la suite.")
