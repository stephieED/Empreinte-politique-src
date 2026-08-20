"""Garde-fou #498 : le timeout du job, le budget de la collecte et le message de
temps mur doivent rester d'accord entre eux.

Contexte. `timeout-minutes: 5` sur `extract-an` était justifié par des durées
mesurées « 1m18s-2m10s » — toutes relevées dans le mode par défaut, celui qui
lève `--skip-interventions`. Employé avec `collect_interventions=true`, ce
timeout tuait le shard : 4 shards sur 8 du run 32302557156, 5 sur 5 relevés du
run 32379928098. Le correctif tient en deux valeurs couplées, écrites à deux
endroits différents du même fichier :

- `timeout-minutes` d'`extract-an`, conditionnel au mode ;
- `--budget-interventions-secondes` du step d'extraction, qui borne la collecte
  *à l'intérieur* du process pour que le timeout de job ne soit plus le
  mécanisme d'arrêt normal.

Découplées, elles reproduisent exactement le défaut d'origine : un budget plus
grand que ce que le timeout laisse réellement à l'extraction, et le shard meurt
à nouveau sans rien écrire. D'où ce test.

Les assertions ne sont pas que textuelles : le fragment de bash du step est
réellement exécuté dans les deux modes, parce que c'est un garde-fou débranché
— écrit mais jamais déclenché — qui est à l'origine de #460.

Volontairement sans PyYAML (absent de `requirements.txt`), comme
`test_ci_cache_paths.py` et `test_ci_garde_fou_interventions.py`.
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1]
WORKFLOW = RACINE / ".github" / "workflows" / "generate-data.yml"

# Provision de préambule de job : `actions/checkout`, `setup-python`, `pip
# install`, restauration des deux caches, téléchargement de l'artifact
# d'amendements. Mesurée entre 30 s et 193 s sur les 29 shards `extract-an` des
# runs 32233766814, 32288588518, 32302557156 et 32379928098 — c'est ce que le
# `timeout-minutes` couvre en plus de la collecte, et ce que le budget interne,
# lui, ne couvre pas.
PREAMBULE_PROVISIONNE_SECONDES = 240


def _yaml() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def _timeouts_extract_an() -> tuple[int, int]:
    """`(minutes sans interventions, minutes avec)` lus sur le `timeout-minutes`
    d'`extract-an`."""
    texte = _yaml()
    bloc = re.search(r"^  extract-an:\n(.*?)(?=\n  [a-z][a-z0-9-]*:\n)", texte, flags=re.S | re.M)
    assert bloc, "Job `extract-an` introuvable dans generate-data.yml."
    motif = re.search(
        r"^    timeout-minutes:\s*\$\{\{\s*inputs\.collect_interventions\s*&&\s*(\d+)\s*\|\|\s*(\d+)\s*\}\}",
        bloc.group(1),
        flags=re.M,
    )
    assert motif, (
        "Le `timeout-minutes` d'extract-an n'est plus conditionnel à "
        "`inputs.collect_interventions`. Une valeur unique ne peut pas couvrir les "
        "deux modes : c'est le défaut que #498 corrige (extraction mesurée à "
        "8-18 s sans interventions, 59-286 s avec)."
    )
    avec, sans = int(motif.group(1)), int(motif.group(2))
    return sans, avec


def _script_extraction() -> str:
    """Le shell du step « Extraction AN », tel que GitHub Actions l'exécutera."""
    texte = _yaml()
    motif = re.search(
        r"^      - name: Extraction AN \(NosD.*?\n        run: \|\n(.*?)(?=\n      [-#])",
        texte,
        flags=re.S | re.M,
    )
    assert motif, "Step « Extraction AN » introuvable ou sans `run: |`."
    return "\n".join(ligne[10:] for ligne in motif.group(1).split("\n"))


def _budget_du_script() -> int:
    motif = re.search(r"--budget-interventions-secondes (\d+)", _script_extraction())
    assert motif, (
        "Le step d'extraction ne passe plus `--budget-interventions-secondes`. "
        "Sans budget interne, un shard tué par `timeout-minutes` ne publie AUCUN "
        "profil (constaté : « Publication : 0 profil(s) » sur les 9 shards tués "
        "des runs 32302557156 et 32379928098)."
    )
    return int(motif.group(1))


def _executer_script(collect_interventions: str) -> str:
    """Exécute le fragment de bash du step, sans la ligne d'extraction Python,
    et renvoie les flags calculés."""
    script = _script_extraction()
    lignes = [ligne for ligne in script.split("\n") if "generate_all_profiles.py" not in ligne]
    corps = "\n".join(lignes)
    corps = corps.replace("${{ inputs.collect_interventions }}", collect_interventions)
    corps = re.sub(r"\$\{\{[^}]*\}\}", "0", corps)
    corps += '\necho "BUDGET=${BUDGET_FLAG[*]-}"\necho "INTERV=${INTERV_FLAG[*]-}"\n'
    resultat = subprocess.run(
        ["bash", "-c", corps],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", "FRESH": "false", "OVERWRITE": "false"},
    )
    assert resultat.returncode == 0, resultat.stderr
    return resultat.stdout


# ---------------------------------------------------------------------------
# Le contrat entre les deux valeurs
# ---------------------------------------------------------------------------

def test_le_mode_interventions_a_un_timeout_plus_large():
    sans, avec = _timeouts_extract_an()
    assert avec > sans, (
        "Le mode interventions ajoute trois charges absentes du mode par défaut "
        "(recherche NosDéputés, archives Syceron, archives de questions) : son "
        "timeout ne peut pas être inférieur ou égal."
    )


def test_le_budget_tient_dans_le_timeout_du_mode_ou_il_s_applique():
    """Le cœur du garde-fou. Le budget ne borne que la collecte ; le timeout
    borne le job entier, préambule compris."""
    _, avec = _timeouts_extract_an()
    budget = _budget_du_script()
    plafond = avec * 60
    assert budget + PREAMBULE_PROVISIONNE_SECONDES <= plafond, (
        f"budget={budget} s + préambule provisionné={PREAMBULE_PROVISIONNE_SECONDES} s "
        f"dépasse le timeout du mode interventions ({avec} min = {plafond} s). "
        "Le shard serait de nouveau tué avant d'écrire son profil — exactement "
        "le défaut de #498."
    )


def test_le_timeout_ne_derive_pas_vers_le_blocage_de_20_minutes():
    """La borne haute a une raison : un shard bloqué immobilise tout le matrix
    séquentiel (`max-parallel: 1`) derrière lui — 20+ min constatées le 16/08 sur
    `jerome-guedj`. Élargir le timeout au-delà de 10 min rouvrirait ce risque."""
    sans, avec = _timeouts_extract_an()
    assert sans <= 5
    assert avec <= 10


def test_le_message_de_temps_mur_annonce_le_timeout_du_mode_courant():
    """Annoncer 5 min par shard pendant qu'un run en consomme 9 rendrait cet
    avertissement faux au moment précis où il sert."""
    texte = _yaml()
    motif = re.search(
        r"AN_TIMEOUT_MINUTES:\s*\$\{\{\s*inputs\.collect_interventions\s*&&\s*(\d+)\s*\|\|\s*(\d+)\s*\}\}",
        texte,
    )
    assert motif, (
        "`prepare-an-matrix` n'expose plus AN_TIMEOUT_MINUTES : son avertissement "
        "de temps mur retomberait sur une valeur en dur, désolidarisée du timeout "
        "réel d'extract-an."
    )
    sans, avec = _timeouts_extract_an()
    assert (int(motif.group(1)), int(motif.group(2))) == (avec, sans)
    assert "COUNT * 5" not in texte, (
        "Le calcul du temps mur multiplie encore par une constante 5 : il doit "
        "utiliser AN_TIMEOUT_MINUTES."
    )


# ---------------------------------------------------------------------------
# Le flag est réellement posé, et réellement accepté
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "collect_interventions, budget_attendu, interv_attendu",
    [("true", True, False), ("false", False, True)],
)
def test_le_flag_suit_le_mode(collect_interventions, budget_attendu, interv_attendu):
    sortie = _executer_script(collect_interventions)
    budget_pose = "--budget-interventions-secondes" in sortie.split("BUDGET=")[1].split("\n")[0]
    skip_pose = "--skip-interventions" in sortie.split("INTERV=")[1].split("\n")[0]
    assert budget_pose is budget_attendu, sortie
    assert skip_pose is interv_attendu, sortie


def test_le_flag_existe_vraiment_cote_python():
    """Un flag inconnu ferait échouer argparse *après* le checkout et le pip
    install, c'est-à-dire 2 à 3 min de runner par shard pour rien."""
    aide = subprocess.run(
        [sys.executable, str(RACINE / "src" / "generate_all_profiles.py"), "--help"],
        capture_output=True,
        text=True,
        cwd=RACINE,
    )
    assert aide.returncode == 0, aide.stderr
    assert "--budget-interventions-secondes" in aide.stdout
