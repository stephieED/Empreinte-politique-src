"""Garde-fou #528 : le Sénat ne rentre pas par la fenêtre.

Le Sénat est sorti du périmètre du produit par une **décision éditoriale**
(`docs/technical_decisions.md#retrait-senat-528`). Une décision éditoriale ne se
défait pas en rajoutant une clé dans un dict : elle se reprend explicitement,
datée, en satisfaisant les trois conditions écrites au §7 de cette section.

Ce fichier est le verrou qui l'impose. Il ne teste pas un comportement de
collecte — il n'y a plus rien à collecter — mais l'**absence** des trois portes
d'entrée, et la **présence** des trois refus bruyants qui les remplacent. C'est
la même mécanique que les deux tests retournés de #526/#527 sur
`AN_ROSTER_ACTIF` : un verrou qu'on supprime le jour où il se déclenche n'a
jamais rien gardé.

Ce qui reste EXPRESSÉMENT en place, et que ce fichier vérifie aussi :

- les 2 entrées Sénat de `raw_data/groupes_reels.json`, toujours
  `extraction_suspendue` — les retirer supprimerait deux fichiers publiés, ce
  que `audit_diff_profils` bloque (#460/#470) ;
- leur `condition_reprise`, qui doit renvoyer à la décision éditoriale et **pas**
  à un état de source : un certificat renouvelé sur `archive.nossenateurs.fr` ne
  rouvre plus rien.

Volontairement sans PyYAML (absent de `requirements.txt`), comme les autres
gardes-fous de workflow de ce dépôt.
"""

import json
import re
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1]
WORKFLOW = RACINE / ".github" / "workflows" / "generate-data.yml"
GROUPES = RACINE / "raw_data" / "groupes_reels.json"

sys.path.insert(0, str(RACINE / "src"))

import candidate_profile
import generate_all_profiles
import group_roster

#: L'ancre de la décision. Un refus qui ne la cite pas oblige son lecteur à
#: deviner s'il regarde une panne ou un choix.
ANCRE = "retrait-senat-528"


# ---------------------------------------------------------------------------
# Les trois portes d'entrée sont fermées
# ---------------------------------------------------------------------------

def test_senateurs_nest_plus_une_base_d_url():
    """La porte la plus basse. Tant que `BASE_URLS` porte une entrée
    `senateurs`, tout le reste du chemin de collecte redevient atteignable."""
    assert set(candidate_profile.BASE_URLS) == {"deputes"}, candidate_profile.BASE_URLS
    assert not any(
        "nossenateurs" in url
        for urls in candidate_profile.BASE_URLS.values()
        for url in urls
    )


def test_chambres_ne_contient_que_l_assemblee():
    assert generate_all_profiles.CHAMBRES == ["deputes"]


def test_source_senat_nest_plus_une_valeur():
    assert "senat" not in generate_all_profiles.SOURCE_VALUES
    assert set(generate_all_profiles.SOURCE_VALUES) == {"an", "ue", "all"}


def test_les_fetchs_senatoriaux_nont_plus_de_definition():
    """`fetch_votes` et `fetch_dossiers_for_legislatures` n'avaient plus
    d'appelant : côté députés, votes et textes portés viennent de l'open data
    AN. Les laisser vivantes aurait gardé un chemin réseau vers une source
    morte, prêt à être rebranché sans décision."""
    for nom in ("fetch_votes", "fetch_dossiers", "fetch_dossiers_for_legislatures"):
        assert not hasattr(candidate_profile, nom), (
            f"`candidate_profile.{nom}` est de retour : c'est un chemin de "
            f"collecte sénatorial. Voir docs/technical_decisions.md#{ANCRE}."
        )


# ---------------------------------------------------------------------------
# Les trois refus sont bruyants, et nomment la décision
# ---------------------------------------------------------------------------

def test_build_profile_refuse_la_chambre_en_nommant_la_decision():
    """Le refus doit dire POURQUOI. Un `KeyError` sur `BASE_URLS`, ou un
    « chambre inconnue » générique, se lit comme une faute de frappe."""
    with pytest.raises(ValueError) as echec:
        candidate_profile.build_profile("senateurs", "bruno-retailleau")
    message = str(echec.value)
    assert "#528" in message, message
    assert ANCRE in message, message


def test_base_url_for_refuse_avant_toute_requete():
    with pytest.raises(ValueError) as echec:
        group_roster._base_url_for("senateurs", None)
    assert ANCRE in str(echec.value)


def test_le_refus_roster_est_un_roster_indisponible():
    """`ValueError` appartient à `ERREURS_ROSTER` : les appelants le traitent en
    « roster indisponible » (exit 2, fiches publiées intactes) et non en trace
    de pile qui coûte le commit du run (#518/#524)."""
    assert ValueError in group_roster.ERREURS_ROSTER


# ---------------------------------------------------------------------------
# Le job CI a disparu, et rien ne le rappelle en vie
# ---------------------------------------------------------------------------

def _workflow() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def _noms_de_jobs() -> list[str]:
    corps = _workflow().split("\njobs:\n", 1)
    assert len(corps) == 2, "Section `jobs:` introuvable dans generate-data.yml."
    return re.findall(r"^  ([a-z][a-z0-9-]*):\n", corps[1], flags=re.M)


def test_le_job_extract_senat_nexiste_plus():
    jobs = _noms_de_jobs()
    assert "extract-senat" not in jobs, (
        "`extract-senat` est de retour dans generate-data.yml. Ce job tournait, "
        "échouait sur 8 candidats sur 8 et concluait vert : c'est le motif de "
        f"#501, #510 et #528. Voir docs/technical_decisions.md#{ANCRE}."
    )
    assert jobs, "aucun job détecté — le découpage ne lit plus le workflow"


def test_aucun_needs_ne_reference_le_job_retire():
    """Un `needs:` orphelin ne fait pas échouer le workflow à la validation :
    GitHub *skippe* le job qui en dépend. C'est la forme de panne silencieuse
    que #412 §2.1 a payée."""
    jobs = set(_noms_de_jobs())
    orphelins = []
    for motif in re.finditer(r"^    needs:\s*\[([^\]]*)\]", _workflow(), flags=re.M):
        for besoin in (b.strip() for b in motif.group(1).split(",")):
            if besoin and besoin not in jobs:
                orphelins.append(besoin)
    assert not orphelins, f"`needs:` pointant sur des jobs inexistants : {sorted(set(orphelins))}"


def test_le_workflow_ne_lance_plus_de_collecte_senatoriale():
    lignes = [
        ligne for ligne in _workflow().splitlines()
        if not ligne.lstrip().startswith("#")
    ]
    corps = "\n".join(lignes)
    for interdit in ("--source senat", "raw-profiles-senat", "_artifacts/senat",
                     "public-data-cache-senat"):
        assert interdit not in corps, (
            f"`{interdit}` est de retour dans generate-data.yml (hors commentaire). "
            f"Voir docs/technical_decisions.md#{ANCRE}."
        )


# ---------------------------------------------------------------------------
# Les 2 groupes suspendus : suspendus, pas retirés, et pour la bonne raison
# ---------------------------------------------------------------------------

def _entrees_senat() -> list[dict]:
    groupes = json.loads(GROUPES.read_text(encoding="utf-8"))["groupes"]
    return [g for g in groupes if g.get("chambre") == "Senat"]


def test_les_deux_entrees_senat_restent_dans_la_config():
    """Suspendre n'est pas retirer (#516) : retirer une entrée supprimerait un
    fichier publié, et une disparition abort le commit (#460/#470)."""
    entrees = _entrees_senat()
    assert {g["groupe_id"] for g in entrees} == {"Senat:LR", "Senat:SER"}
    assert {g["fichier"] for g in entrees} == {
        "groupe-Senat-LR.json", "groupe-Senat-SER.json",
    }


def test_les_deux_entrees_senat_restent_suspendues():
    for groupe in _entrees_senat():
        bloc = groupe.get("extraction_suspendue")
        assert bloc, f"{groupe['groupe_id']} n'est plus suspendu."
        # Le bloc complet reste exigé par le quality gate (#516) : une
        # suspension sans rien à relire devient permanente par omission.
        assert set(bloc) >= {"depuis", "motif", "references", "condition_reprise"}


def test_la_condition_de_reprise_est_editoriale_et_non_un_etat_de_source():
    """Le cœur de la décision. L'ancienne condition disait « un certificat
    valide sur archive.nossenateurs.fr » : un renouvellement de certificat
    aurait rouvert tout seul une collecte que le produit ne veut plus."""
    for groupe in _entrees_senat():
        reprise = groupe["extraction_suspendue"]["condition_reprise"]
        assert ANCRE in reprise, (
            f"{groupe['groupe_id']} : la condition de reprise ne renvoie pas à la "
            "décision écrite."
        )
        assert "#528" in groupe["extraction_suspendue"]["references"]
