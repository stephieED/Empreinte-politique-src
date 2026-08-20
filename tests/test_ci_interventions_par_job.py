"""Garde-fou #501 : aucun chemin de collecte ne peut plus diverger en silence
sur les interventions.

Contexte. Trois jobs de `generate-data.yml` lancent `generate_all_profiles.py`
sur le réseau, et pendant des mois ils se sont comportés de trois façons
différentes face au même input `collect_interventions`, sans que rien ne le
signale :

- `extract-an` obéissait à l'input (`INTERV_FLAG`) ;
- `extract-roster-groupes` levait `--skip-interventions` en dur (#357) ;
- `extract-senat` collectait **toujours**, quel que soit le réglage — aucun
  flag, aucune lecture de l'input. Le run 32379928098 y a passé 74 minutes.

Aucun de ces trois comportements n'est illégitime en soi ; ce qui manquait,
c'est qu'ils soient *déclarés*. Une divergence lisible se discute, une
divergence tacite se découvre au bout de 74 minutes de runner.

Ce que ce fichier impose : **toute** invocation de `generate_all_profiles.py`
dans le workflow tombe dans exactement un mode explicite, et l'inventaire des
modes est écrit ici. Ajouter un quatrième chemin de collecte sans se prononcer
sur les interventions fait échouer `test_l_inventaire_est_a_jour` — le mode
doit être choisi et inscrit, pas hérité par défaut.

Volontairement sans PyYAML (absent de `requirements.txt`), comme
`test_ci_budget_interventions.py` et `test_ci_cache_paths.py`.
"""

import re
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1]
WORKFLOW = RACINE / ".github" / "workflows" / "generate-data.yml"

# Provision de préambule d'un job (checkout, bootstrap-extraction, restauration
# du cache). Mesurée entre 6 s et 170 s sur les 15 derniers runs portant un
# `extract-senat` (14/08 → 20/08/2026). Même provision que `extract-an`, dont
# la mesure max est 193 s : c'est ce que `timeout-minutes` couvre EN PLUS de la
# collecte, et l'oublier est l'erreur d'origine de #498.
PREAMBULE_PROVISIONNE_SECONDES = 240

# Les quatre modes possibles face à `collect_interventions`.
MODE_INPUT = "piloté par collect_interventions"
MODE_JAMAIS = "--skip-interventions en dur"
MODE_SANS_CHAMBRE_FR = "--source ue : aucune chambre française, donc aucune intervention"
MODE_PIVOT = "--pivot-only : aucun appel réseau"

# L'INVENTAIRE. Une entrée par invocation de `generate_all_profiles.py` dans
# generate-data.yml, clé `(job, rang dans le job)`.
#
# Toute nouvelle invocation doit être ajoutée ici avec son mode — c'est le
# point du garde-fou : le mode devient une décision écrite, pas un défaut.
INVENTAIRE = {
    ("extract-an", 0): MODE_INPUT,
    # #501 : la collecte sénatoriale ne retenait rien, par construction —
    # `fetch_intervention_details` résout l'orateur via la clé `url_nosdeputes`,
    # que `archive.nossenateurs.fr` n'expose jamais (elle publie
    # `url_nossenateurs`). Voir docs/technical_decisions.md#interventions-senat-501.
    ("extract-senat", 0): MODE_JAMAIS,
    ("extract-ue-officiel", 0): MODE_SANS_CHAMBRE_FR,
    # #357, mode d'extraction léger : seuls identité/mandats/votes/amendements
    # sont consommés en aval par les agrégats de groupe.
    ("extract-roster-groupes", 0): MODE_JAMAIS,
    ("merge-and-pivot", 0): MODE_PIVOT,
    ("merge-and-pivot", 1): MODE_PIVOT,
}

# Jetons attendus dans la description de l'input pour chaque job qui ignore le
# réglage. Un job qui n'obéit pas à un input doit être nommé là où l'opérateur
# lit cet input, pas seulement dans un commentaire YAML.
JETON_DESCRIPTION = {
    "extract-roster-groupes": "roster",
    "extract-senat": "Senate",
}


def _yaml() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def _blocs_de_job() -> dict[str, str]:
    """`{nom de job: corps}` pour chaque job de `generate-data.yml`."""
    texte = _yaml()
    apres_jobs = texte.split("\njobs:\n", 1)
    assert len(apres_jobs) == 2, "Section `jobs:` introuvable dans generate-data.yml."
    corps = apres_jobs[1]
    debuts = [(m.start(), m.group(1)) for m in re.finditer(r"^  ([a-z][a-z0-9-]*):\n", corps, flags=re.M)]
    assert debuts, "Aucun job détecté."
    blocs = {}
    for i, (debut, nom) in enumerate(debuts):
        fin = debuts[i + 1][0] if i + 1 < len(debuts) else len(corps)
        blocs[nom] = corps[debut:fin]
    return blocs


def _invocations() -> dict[tuple[str, int], str]:
    """`{(job, rang): commande}` pour chaque appel à `generate_all_profiles.py`.

    Les continuations `\\` sont recollées : `extract-roster-groupes` et
    `merge-and-pivot` écrivent leur commande sur plusieurs lignes, et une
    recherche ligne à ligne y raterait `--skip-interventions`.
    """
    trouvees: dict[tuple[str, int], str] = {}
    for nom, bloc in _blocs_de_job().items():
        lignes = bloc.split("\n")
        recollees: list[str] = []
        tampon = ""
        for ligne in lignes:
            nue = ligne.strip()
            if nue.startswith("#"):
                continue
            if nue.endswith("\\"):
                tampon += nue[:-1].strip() + " "
                continue
            recollees.append((tampon + nue).strip())
            tampon = ""
        if tampon:
            recollees.append(tampon.strip())
        rang = 0
        for commande in recollees:
            if "generate_all_profiles.py" not in commande:
                continue
            trouvees[(nom, rang)] = commande
            rang += 1
    return trouvees


def _script_du_job(nom: str) -> str:
    """Tout le shell d'un job, commentaires compris : c'est là que vivent les
    assignations de `INTERV_FLAG`."""
    return _blocs_de_job()[nom]


def _mode_observe(job: str, commande: str) -> str:
    """Le mode réellement déclaré par une invocation, lu sur le YAML."""
    if "--pivot-only" in commande:
        return MODE_PIVOT
    if re.search(r"--source\s+ue\b", commande):
        return MODE_SANS_CHAMBRE_FR
    if "--skip-interventions" in commande:
        return MODE_JAMAIS
    motif_tableau = re.search(r'"\$\{([A-Z_]*INTERV[A-Z_]*)\[@\]\}"', commande)
    if motif_tableau:
        tableau = motif_tableau.group(1)
        script = _script_du_job(job)
        assignation = re.search(
            rf"inputs\.collect_interventions[^\n]*\)\s*&&\s*{tableau}=\(|"
            rf"{tableau}=\([^)]*\)[^\n]*inputs\.collect_interventions|"
            rf"inputs\.collect_interventions[^\n]*{tableau}=",
            script,
        )
        if assignation:
            return MODE_INPUT
    return "AUCUN MODE DÉCLARÉ"


# ---------------------------------------------------------------------------
# Le garde-fou : l'inventaire et le YAML disent la même chose
# ---------------------------------------------------------------------------

def test_l_inventaire_est_a_jour():
    """Un quatrième chemin de collecte ne peut pas apparaître en silence."""
    observees = set(_invocations())
    inventoriees = set(INVENTAIRE)
    nouvelles = observees - inventoriees
    disparues = inventoriees - observees
    assert not nouvelles, (
        "Invocation(s) de generate_all_profiles.py absente(s) de l'INVENTAIRE : "
        f"{sorted(nouvelles)}. Décidez ce que ce chemin fait des interventions "
        "et inscrivez-le — c'est précisément la divergence tacite que #501 corrige "
        "(extract-senat a collecté hors de tout réglage pendant des mois)."
    )
    assert not disparues, (
        f"L'INVENTAIRE référence des invocations qui n'existent plus : {sorted(disparues)}."
    )


@pytest.mark.parametrize("cle", sorted(INVENTAIRE))
def test_chaque_invocation_declare_le_mode_inventorie(cle):
    invocations = _invocations()
    if cle not in invocations:
        pytest.skip("couvert par test_l_inventaire_est_a_jour")
    observe = _mode_observe(cle[0], invocations[cle])
    assert observe == INVENTAIRE[cle], (
        f"{cle[0]} (invocation n°{cle[1]}) : mode attendu « {INVENTAIRE[cle]} », "
        f"observé « {observe} ».\n  {invocations[cle]}"
    )


def test_aucune_invocation_reseau_ne_reste_muette():
    """La formulation directe du défaut de #501 : sur le chemin réseau, ne rien
    dire des interventions n'est pas un mode."""
    muettes = [
        cle for cle, commande in _invocations().items()
        if _mode_observe(cle[0], commande) == "AUCUN MODE DÉCLARÉ"
    ]
    assert not muettes, (
        f"Invocation(s) sans mode d'interventions déclaré : {sorted(muettes)}. "
        "Attendu : --skip-interventions, un tableau INTERV_* piloté par "
        "inputs.collect_interventions, --source ue ou --pivot-only."
    )


def test_la_description_de_l_input_nomme_les_jobs_qui_l_ignorent():
    """Un job qui n'obéit pas à `collect_interventions` doit être nommé là où
    l'opérateur lit cet input. La description disait « Affects extract-an only —
    the roster job always skips them » alors qu'extract-senat collectait
    toujours : elle décrivait deux jobs sur trois."""
    motif = re.search(r'^      collect_interventions:\n        description: "([^"]*)"', _yaml(), flags=re.M)
    assert motif, "Input `collect_interventions` introuvable ou description non littérale."
    description = motif.group(1)
    ignorants = {job for (job, _), mode in INVENTAIRE.items() if mode == MODE_JAMAIS}
    manquants = [
        JETON_DESCRIPTION[job] for job in sorted(ignorants)
        if job in JETON_DESCRIPTION and JETON_DESCRIPTION[job].lower() not in description.lower()
    ]
    assert not manquants, (
        f"La description de collect_interventions ne nomme pas {manquants} alors que "
        f"ces jobs ignorent le réglage : {sorted(ignorants)}.\n  « {description} »"
    )


# ---------------------------------------------------------------------------
# Le timeout d'extract-senat
# ---------------------------------------------------------------------------

def _timeout_senat_minutes() -> int:
    bloc = _blocs_de_job()["extract-senat"]
    motif = re.search(r"^    timeout-minutes:\s*(\d+)\s*$", bloc, flags=re.M)
    assert motif, (
        "`timeout-minutes` d'extract-senat introuvable ou non littéral. Ce job "
        "n'a qu'un mode depuis #501 : une valeur conditionnelle n'aurait rien à "
        "conditionner."
    )
    return int(motif.group(1))


def test_le_timeout_senat_couvre_le_preambule_et_la_collecte_residuelle():
    """`timeout-minutes` borne `préambule + collecte`, pas la collecte seule.

    Collecte résiduelle mesurée après #501 : 4 requêtes par slug résolvable
    (identité, votes, 2 législatures de dossiers), soit 32 requêtes pour les
    8 slugs de raw_data/candidats.json — 2,7 s chronométrées sur
    `bruno-retailleau` le 20/08/2026, ~30 s projetées pour les 8.
    """
    collecte_residuelle_projetee = 30
    plafond = _timeout_senat_minutes() * 60
    assert PREAMBULE_PROVISIONNE_SECONDES + collecte_residuelle_projetee <= plafond, (
        f"préambule provisionné ({PREAMBULE_PROVISIONNE_SECONDES} s) + collecte "
        f"résiduelle ({collecte_residuelle_projetee} s) dépasse le timeout "
        f"d'extract-senat ({plafond} s)."
    )


def test_le_timeout_senat_ne_redevient_pas_un_plafond_qui_ne_borne_rien():
    """90 min n'ont jamais coupé ce job : ses deux runs les plus longs (969 s et
    4 482 s) ont été arrêtés par une annulation de RUN, pas par leur timeout.
    Un plafond qu'on n'atteint jamais ne protège de rien."""
    assert _timeout_senat_minutes() <= 20, (
        "Le timeout d'extract-senat repasse au-dessus de 20 min. Sans collecte "
        "d'interventions, ce job fait 32 requêtes : une valeur plus large ne "
        "bornerait à nouveau rien."
    )


def test_le_senat_ne_pose_pas_de_budget_d_interventions():
    """Cohérence avec #500 : `--budget-interventions-secondes` n'a de sens que
    sur un chemin qui collecte. `build_profile_any_chambre` le neutralise sous
    `--skip-interventions` — le poser ici serait un réglage mort, du genre qui
    fait croire à une protection."""
    commande = _invocations()[("extract-senat", 0)]
    assert "--budget-interventions-secondes" not in commande, (
        "extract-senat pose un budget d'interventions alors qu'il lève "
        "--skip-interventions : le budget serait None par construction."
    )
