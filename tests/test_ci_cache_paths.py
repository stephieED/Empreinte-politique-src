"""Garde-fou #424 : les répertoires de `.cache/` doivent tous être couverts par
un `actions/cache` de `generate-data.yml`.

Contexte. Jusqu'à #424, les trois jobs AN cachaient `.cache` en bloc sous une
clé partagée. `extract-amendements-an` écrivant la clé exacte de la semaine en
premier, `extract-an` et `extract-roster-groupes` faisaient un *exact key hit*
et `actions/cache` sautait leur sauvegarde post-job : ce qu'ils téléchargeaient
n'était jamais persisté (~438 Mo re-téléchargés par run, confirmé par le run
32136438841).

Le correctif donne aux amendements leur propre clé et **énumère explicitement**
les répertoires cachés par les autres jobs — sans quoi ils ré-embarqueraient
`amendements_an` et déplaceraient le problème au lieu de le résoudre.

Le revers de l'énumération est qu'un nouveau `.cache/<quelque_chose>` ajouté
côté Python ne serait pas caché, **sans que rien ne le signale** : le pipeline
continuerait de fonctionner en re-téléchargeant à chaque run. D'où ce test.

Volontairement sans PyYAML (absent de requirements.txt) : une recherche
textuelle suffit et évite d'ajouter une dépendance pour un seul garde-fou.
"""

import re
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
WORKFLOW = RACINE / ".github" / "workflows" / "generate-data.yml"

# Jobs autorisés à cacher `.cache` en bloc, avec la raison. `extract-senat`
# n'écrit rien sous `.cache` (aucune constante côté Sénat) : son entrée ne
# recopie que ce que la restauration y a mis. Laissé en l'état par #424, qui ne
# supprime pas une entrée de cache en effet de bord.
JOBS_CACHE_LARGE_TOLERES = {"extract-senat"}


def _repertoires_cache_utilises_par_le_code() -> set[str]:
    motif = re.compile(r'Path\("\.cache"\)\s*/\s*"([a-z_]+)"')
    trouves: set[str] = set()
    for fichier in (RACINE / "src").glob("*.py"):
        trouves.update(motif.findall(fichier.read_text(encoding="utf-8")))
    return trouves


def test_le_code_declare_bien_des_repertoires_de_cache():
    """Garde-fou du garde-fou : si l'extraction ne trouve plus rien, le test
    ci-dessous passerait pour une mauvaise raison."""
    assert len(_repertoires_cache_utilises_par_le_code()) >= 5


def _chemins_caches_par_job() -> dict[str, set[str]]:
    """`{job: {sous-répertoires de .cache listés dans ses actions/cache}}`.

    Analyse par job et non sur le fichier entier : un répertoire retiré de
    l'énumération d'UN job resterait présent ailleurs, et une simple recherche
    textuelle ne verrait rien — c'est le trou qu'avait la première version de
    ce test.
    """
    par_job: dict[str, set[str]] = {}
    job = None
    dans_cache = False
    for ligne in WORKFLOW.read_text(encoding="utf-8").split("\n"):
        entete = re.match(r"^  ([a-z][a-z0-9-]*):\s*$", ligne)
        if entete:
            job = entete.group(1)
            par_job.setdefault(job, set())
        if re.match(r"^      - (uses|name):", ligne):
            dans_cache = "actions/cache" in ligne
        elif ligne.strip().startswith("uses:"):
            dans_cache = "actions/cache" in ligne
        if dans_cache and job:
            trouve = re.search(r"\.cache/([a-z_]+)", ligne)
            if trouve:
                par_job[job].add(trouve.group(1))
    return par_job


# Jobs consommant le même jeu de données source AN : leurs `path:` doivent
# rester identiques, sinon l'un d'eux re-télécharge ce que l'autre a persisté.
JOBS_AN = ("extract-an", "extract-roster-groupes")

# Jobs qui lisent les dossiers législatifs. merge-and-pivot en fait partie
# depuis #427 : `generate_gouvernement_profiles.py` appelle directement
# `fetch_dossiers_gouvernementaux()`, et sans cache ce job re-téléchargeait les
# 3 archives à chaque run — avec, à la clé, l'écrasement des textes de
# gouvernement en cas d'échec réseau.
JOBS_DOSSIERS = ("extract-an", "extract-roster-groupes", "merge-and-pivot")


def test_les_deux_jobs_an_cachent_exactement_les_memes_repertoires():
    par_job = _chemins_caches_par_job()
    ensembles = {job: par_job.get(job, set()) for job in JOBS_AN}
    reference, *autres = ensembles.values()
    assert all(e == reference for e in autres), (
        f"Les jobs AN divergent sur les répertoires cachés : {ensembles}. "
        "extract-roster-groupes consomme le même jeu de données que extract-an "
        "(#424) : une divergence signifie qu'un des deux re-télécharge."
    )


def test_tous_les_repertoires_de_cache_sont_couverts_par_le_workflow():
    """Chaque `.cache/<dir>` du code doit être caché par au moins un job.

    Sans cela il serait re-téléchargé à chaque run **sans aucun signal** — le
    pipeline continuerait de fonctionner, simplement plus lentement et plus
    exposé aux coupures réseau de data.assemblee-nationale.fr.
    """
    par_job = _chemins_caches_par_job()
    couverts: set[str] = set().union(*par_job.values()) if par_job else set()
    manquants = sorted(_repertoires_cache_utilises_par_le_code() - couverts)
    assert not manquants, (
        f"Répertoires de cache absents de {WORKFLOW.name} : {manquants}. "
        "Les ajouter au `path:` du job qui les produit (#424)."
    )


def test_amendements_ont_leur_propre_cle_de_cache():
    """Le cœur de #424 : si les amendements repassaient sous la clé AN, les
    jobs qui la partagent recommenceraient à ne jamais sauvegarder."""
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "public-data-cache-amendements-" in workflow

    # Aucun bloc `path:` contenant amendements_an ne doit porter la clé AN.
    for bloc in re.split(r"\n      - (?:uses|name):", workflow):
        if ".cache/amendements_an" not in bloc:
            continue
        if "public-data-cache-an-" in bloc and "cache@" in bloc:
            raise AssertionError(
                "Un actions/cache couvre à la fois .cache/amendements_an et la "
                "clé public-data-cache-an-* : c'est exactement la configuration "
                "qui empêchait extract-an de sauvegarder son cache (#424)."
            )


def test_pas_de_cache_large_non_declare():
    """`path: .cache` en bloc ré-embarque les amendements. Toute nouvelle
    occurrence doit être un choix explicite, pas une régression."""
    workflow = WORKFLOW.read_text(encoding="utf-8")
    jobs_larges: set[str] = set()
    job_courant = None
    for ligne in workflow.split("\n"):
        entete = re.match(r"^  ([a-z][a-z0-9-]*):\s*$", ligne)
        if entete:
            job_courant = entete.group(1)
        if ligne.strip() == "path: .cache" and job_courant:
            jobs_larges.add(job_courant)

    assert jobs_larges <= JOBS_CACHE_LARGE_TOLERES, (
        f"Jobs cachant `.cache` en bloc sans justification : "
        f"{sorted(jobs_larges - JOBS_CACHE_LARGE_TOLERES)}."
    )


def test_les_jobs_lisant_les_dossiers_les_cachent_tous():
    """#427 : merge-and-pivot était le seul job sans aucun actions/cache."""
    par_job = _chemins_caches_par_job()
    sans_cache = sorted(j for j in JOBS_DOSSIERS if "dossiers_an" not in par_job.get(j, set()))
    assert not sans_cache, (
        f"Jobs lisant les dossiers législatifs sans les cacher : {sans_cache}. "
        "Ils re-téléchargent ~33 Mo par run et s'exposent à un échec réseau "
        "dont la conséquence, côté merge-and-pivot, est l'écrasement des "
        "textes de gouvernement (#427)."
    )


def test_les_dossiers_ont_leur_propre_cle():
    """Restaurer `public-data-cache-an-*` pour obtenir les dossiers
    embarquerait aussi `scrutins_an` : plusieurs centaines de Mo pour en
    utiliser 46."""
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "public-data-cache-dossiers-" in workflow

    for bloc in re.split(r"\n      - (?:uses|name):", workflow):
        if ".cache/dossiers_an" not in bloc or "cache@" not in bloc:
            continue
        assert "public-data-cache-an-" not in bloc, (
            "Un actions/cache couvre .cache/dossiers_an sous la clé AN : les "
            "dossiers doivent garder leur clé dédiée (#427)."
        )


# ---------------------------------------------------------------------------
# Découplage `overwrite_profiles` / purge du cache (#440)
# ---------------------------------------------------------------------------

RETRY = RACINE / ".github" / "workflows" / "retry-generate-data.yml"


def test_overwrite_profiles_existe_comme_input():
    """Écraser les profils et purger le cache sont deux besoins distincts : la
    correction de clé de #440 impose le premier, alors que purger obligerait à
    re-télécharger ~300 Mo auprès d'une source dont l'indisponibilité a déjà
    bloqué trois chantiers."""
    assert "overwrite_profiles:" in WORKFLOW.read_text(encoding="utf-8")


def test_overwrite_profiles_ne_purge_jamais_le_cache():
    """L'invariant central de ce découplage. Un step de nettoyage conditionné à
    `overwrite_profiles` annulerait tout l'intérêt du mode."""
    workflow = WORKFLOW.read_text(encoding="utf-8")
    for bloc in re.split(r"\n      - name: ", workflow):
        if not bloc.startswith("Nettoyage"):
            continue
        entete = bloc.split("\n", 1)[0]
        condition = re.search(r"if:\s*\$\{\{([^}]+)\}\}", bloc)
        assert condition, f"step de nettoyage sans condition : {entete}"
        assert "overwrite_profiles" not in condition.group(1), (
            f"le step « {entete} » purge sur overwrite_profiles — or ce mode "
            "existe précisément pour écraser SANS re-télécharger (#440)."
        )


def test_tous_les_no_merge_considerent_les_deux_inputs():
    """`--no-merge` doit être posé par fresh_run OU par overwrite_profiles.
    Un job qui n'en regarderait qu'un fusionnerait alors que les autres
    écrasent — donc produirait les doublons que #440 corrige, sur ce job-là
    seulement, ce qui serait d'autant plus difficile à voir."""
    workflow = WORKFLOW.read_text(encoding="utf-8")
    lignes = [l for l in workflow.split("\n") if "MERGE_FLAG=(--no-merge)" in l]
    assert lignes, "aucun MERGE_FLAG trouvé — le test ne vérifie plus rien"
    for ligne in lignes:
        assert "$FRESH" in ligne and "$OVERWRITE" in ligne, (
            f"condition incomplète : {ligne.strip()}"
        )


def test_le_retry_reconstruit_overwrite_profiles():
    """Sans cette reconstruction, un run `overwrite_profiles=true` préempté
    serait relancé en fusion additive — exactement le scénario de doublons que
    ce mode existe pour éviter."""
    retry = RETRY.read_text(encoding="utf-8")
    assert "overwrite_profiles=" in retry
    assert "-f overwrite_profiles=" in retry, "l'input n'est pas transmis à la relance"


def test_le_retry_deduit_overwrite_apres_avoir_lu_le_log():
    """La déduction s'appuie sur `an_log` : la placer avant sa définition la
    rendrait toujours fausse, silencieusement."""
    retry = RETRY.read_text(encoding="utf-8")
    assert retry.index("an_log=$(job_log") < retry.index("overwrite_profiles=false")


def test_skip_existing_est_leve_par_overwrite_profiles():
    """`--skip-existing` s'applique AVANT `--no-merge` : tant qu'il est posé en
    dur, un run `overwrite_profiles=true` saute les profils déjà committés,
    c'est-à-dire exactement ceux qu'une correction de fond doit atteindre
    (#445). Le remettre en dur rendrait la clé corrigée de #440 non
    propageable, sans qu'aucun log ne le signale."""
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "--skip-existing --resume" not in workflow, (
        "--skip-existing est de nouveau posé en dur sur le job roster : "
        "aucune combinaison d'inputs ne peut plus régénérer l'existant."
    )
    lignes = [l for l in workflow.split("\n") if "SKIP_FLAG=()" in l]
    assert lignes, "aucune levée de SKIP_FLAG trouvée — le test ne vérifie plus rien"
    for ligne in lignes:
        assert "$FRESH" in ligne and "$OVERWRITE" in ligne, (
            f"condition incomplète : {ligne.strip()}"
        )


def test_le_job_roster_pose_skip_existing_par_defaut():
    """Le rollout progressif (#224) repose dessus : sans `--skip-existing` par
    défaut, chaque run repaierait le réseau pour tous les profils déjà écrits."""
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "SKIP_FLAG=(--skip-existing)" in workflow
    assert '"${SKIP_FLAG[@]}" --resume' in workflow, (
        "SKIP_FLAG est calculé mais pas transmis à generate_all_profiles.py"
    )
