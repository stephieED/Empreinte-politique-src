"""Garde-fou #551 : la détection de la fenêtre de rétention est ARMÉE, et elle
ne fait que compter.

#434 affirmait que « ce qui est automatisé, c'est la détection ». Le code
existait — `src/audit_volumetrie_profils.py` sait dire si la fenêtre est
contraignante — mais aucun workflow ne l'invoquait : la détection était
outillée, pas armée. Ces tests verrouillent les trois propriétés de la
correction, et chacune répond à une faute précise.

  1. **Le step existe**, dans le job qui écrit les commits de données.
  2. **La valeur de la fenêtre est lue, jamais recopiée.** Elle vit déjà à deux
     endroits dont `tests/test_borner_historique_donnees.py` verrouille
     l'égalité ; un troisième domicile ferait répondre deux valeurs différentes
     à « la fenêtre est-elle contraignante ? ».
  3. **Aucun workflow ne borne ni ne mesure.** La réécriture d'historique est
     irréversible pour tous les clones existants : c'est une décision, pas une
     étape de CI. Et `--mesurer` clone puis repacke deux fois le dépôt entier —
     1 min 52 s de temps réel, 3 min 37 s de CPU au 28/08/2026.

Volontairement sans PyYAML (absent de requirements.txt), comme les autres
gardes-fous de workflow de ce dépôt.
"""

import re
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
WORKFLOWS = sorted((RACINE / ".github" / "workflows").glob("*.yml"))
GENERATE = RACINE / ".github" / "workflows" / "generate-data.yml"
NOM_STEP = "Fenêtre de rétention de l'historique de données (#551)"


def _sans_commentaires(bloc: str) -> str:
    """Les rationales de ce dépôt citent abondamment les commandes qu'elles
    expliquent : les lire comme du workflow serait un faux positif permanent."""
    return "\n".join(l for l in bloc.split("\n") if not l.lstrip().startswith("#"))


def _step_detection() -> str:
    texte = GENERATE.read_text(encoding="utf-8")
    debut = texte.find(f"- name: {NOM_STEP}")
    assert debut != -1, f"step « {NOM_STEP} » absent de {GENERATE.name}"
    suite = re.search(r"^      - name: ", texte[debut + 1:], flags=re.MULTILINE)
    return texte[debut: debut + 1 + suite.start()] if suite else texte[debut:]


def test_la_detection_est_armee():
    """La faute de #551 : le code de détection existait sans que rien ne le
    lance. Un step qui n'existe pas ne détecte rien."""
    assert f"- name: {NOM_STEP}" in GENERATE.read_text(encoding="utf-8")


def test_la_detection_vit_dans_le_job_qui_ecrit_les_commits_de_donnees():
    """Compter ailleurs que là où l'on committe, c'est compter un état qui n'est
    pas encore celui du dépôt."""
    texte = GENERATE.read_text(encoding="utf-8")
    debut = re.search(r"^  merge-and-pivot:\s*$", texte, flags=re.MULTILINE)
    assert debut, "job `merge-and-pivot` absent"
    suite = re.search(r"^  [a-z][a-z0-9-]*:\s*$", texte[debut.end():], flags=re.MULTILINE)
    bloc = texte[debut.end(): debut.end() + suite.start()] if suite else texte[debut.end():]
    assert NOM_STEP in bloc, "la détection doit vivre dans `merge-and-pivot`"


def test_la_fenetre_est_lue_jamais_recopiee():
    """Troisième domicile interdit. `FENETRE` (script de bornage) et
    `FENETRE_COMMITS_DONNEES` (audit) sont déjà tenus égaux par un test ; un
    nombre en dur ici les contredirait sans que rien ne le dise."""
    step = _sans_commentaires(_step_detection())
    assert "FENETRE_COMMITS_DONNEES" in step, (
        "le step doit LIRE la fenêtre depuis `audit_volumetrie_profils`"
    )
    assert "MOTIF_COMMIT_DONNEES" in step, (
        "le motif du commit de données doit être lu, pas recopié"
    )
    valeur = re.search(r"^FENETRE_COMMITS_DONNEES = (\d+)$",
                       (RACINE / "src" / "audit_volumetrie_profils.py").read_text(encoding="utf-8"),
                       flags=re.MULTILINE)
    assert valeur, "FENETRE_COMMITS_DONNEES introuvable"
    assert re.search(rf"\b{valeur.group(1)}\b", step) is None, (
        f"le step écrit {valeur.group(1)} en dur : ce serait un troisième "
        "domicile pour la valeur de la fenêtre"
    )


def test_la_detection_publie_dans_le_resume_de_run():
    """« Rendre le franchissement visible là où on regarde » : une annotation de
    plus se noie, le résumé de run non."""
    assert "GITHUB_STEP_SUMMARY" in _step_detection()


def test_aucun_workflow_ne_borne_l_historique():
    """La réécriture d'historique est irréversible pour tous les clones
    existants. `borner_historique_donnees.sh` garantit par test qu'il ne pousse
    jamais ; l'appeler depuis la CI contournerait cette garantie."""
    for wf in WORKFLOWS:
        corps = _sans_commentaires(wf.read_text(encoding="utf-8"))
        assert "borner_historique_donnees" not in corps, (
            f"{wf.name} invoque le script de bornage : le bornage est une "
            "décision humaine, jamais une étape de CI"
        )


def test_aucun_workflow_n_appelle_la_mesure_lourde():
    """`--mesurer` clone le dépôt entier et le repacke deux fois : 1 min 52 s de
    temps réel et 3 min 37 s de CPU pour ~434 Mo au 28/08/2026. Compter des
    commits coûte une commande."""
    for wf in WORKFLOWS:
        corps = _sans_commentaires(wf.read_text(encoding="utf-8"))
        assert "audit_volumetrie_profils.py --mesurer" not in corps
        assert "--mesurer" not in corps, (
            f"{wf.name} appelle `--mesurer` : mesure lourde interdite en CI (#551)"
        )
