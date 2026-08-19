"""Tests de `audit_diff_profils.py`.

Ce script est le garde-fou d'une régénération `--no-merge` : il détecte ce que
l'abandon de la fusion additive a fait perdre. Ses tests doivent donc surtout
prouver qu'il **détecte** — un comparateur qui ne signale rien est pire
qu'aucun comparateur, puisqu'il donne une fausse assurance.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from audit_diff_profils import (
    CHAMPS_HAUSSE_ATTENDUE,
    CHAMPS_STABLES,
    comparer,
    generate_markdown_report,
    lire_profils_disque,
)


def _profil(**compte) -> dict:
    return {c: [{"x": i} for i in range(n)] for c, n in compte.items()}


def _releve(**compte) -> dict:
    from audit_diff_profils import TOUS_CHAMPS
    return {c: compte.get(c, 0) for c in TOUS_CHAMPS}


# ---------------------------------------------------------------------------
# Détection des pertes
# ---------------------------------------------------------------------------

def test_perte_sur_champ_stable_est_signalee():
    r = comparer({"a.json": _releve(votes=100)}, {"a.json": _releve(votes=90)})
    assert len(r["pertes_sur_champs_stables"]) == 1
    p = r["pertes_sur_champs_stables"][0]
    assert (p["champ"], p["avant"], p["apres"]) == ("votes", 100, 90)


def test_profil_entierement_disparu_est_une_perte():
    """Le pire cas : un profil que la régénération n'a pas produit."""
    r = comparer({"a.json": _releve(votes=100)}, {})
    assert len(r["pertes_sur_champs_stables"]) == 1
    assert r["pertes_sur_champs_stables"][0]["champ"] == "(profil entier)"


def test_baisse_amendements_signalee_mais_pas_bloquante():
    """La correction de clé de #440 fait croître les amendements ; une baisse
    reste anormale, mais elle n'a pas le même statut qu'une perte de votes."""
    r = comparer({"a.json": _releve(amendements=100)}, {"a.json": _releve(amendements=40)})
    assert r["pertes"], "la baisse doit être relevée"
    assert not r["pertes_sur_champs_stables"], "mais pas comme perte bloquante"


def test_hausse_amendements_nest_pas_une_perte():
    r = comparer({"a.json": _releve(amendements=100)}, {"a.json": _releve(amendements=700)})
    assert not r["pertes"]
    assert len(r["gains"]) == 1


# ---------------------------------------------------------------------------
# Le piège que ce script existe pour éviter
# ---------------------------------------------------------------------------

def test_gain_global_ne_masque_pas_une_perte_individuelle():
    """LE cas d'usage. Après #440 les amendements explosent ; si la comparaison
    se faisait en agrégat, une perte de votes sur un profil passerait
    inaperçue derrière ce gain."""
    avant = {
        "a.json": _releve(votes=1000, amendements=100),
        "b.json": _releve(votes=1000, amendements=100),
    }
    apres = {
        "a.json": _releve(votes=1000, amendements=5000),   # gros gain
        "b.json": _releve(votes=200, amendements=5000),    # perte cachée
    }
    r = comparer(avant, apres)

    total_avant = sum(r["totaux_avant"].values())
    total_apres = sum(r["totaux_apres"].values())
    assert total_apres > total_avant, "en agrégat, tout semble en hausse"

    assert len(r["pertes_sur_champs_stables"]) == 1
    assert r["pertes_sur_champs_stables"][0]["fichier"] == "b.json"


def test_champ_absent_equivaut_a_liste_vide():
    """Un champ absent et une liste vide décrivent le même fait : le profil ne
    porte aucune entrée. Les distinguer produirait de fausses alertes."""
    r = comparer({"a.json": _releve()}, {"a.json": _releve()})
    assert not r["pertes"] and not r["gains"]


def test_amendements_hors_des_champs_stables():
    """Garde-fou de la classification elle-même : si `amendements` rejoignait
    les champs stables, toute régénération après #440 serait bloquée."""
    assert "amendements" in CHAMPS_HAUSSE_ATTENDUE
    assert "amendements" not in CHAMPS_STABLES
    assert "votes" in CHAMPS_STABLES


# ---------------------------------------------------------------------------
# Lecture disque et rapport
# ---------------------------------------------------------------------------

def test_lecture_disque_compte_les_entrees(tmp_path):
    (tmp_path / "a.json").write_text(
        json.dumps(_profil(votes=3, amendements=5)), encoding="utf-8")
    releve = lire_profils_disque(tmp_path)
    assert releve["a.json"]["votes"] == 3
    assert releve["a.json"]["amendements"] == 5


def test_lecture_disque_ignore_un_json_illisible(tmp_path):
    (tmp_path / "ok.json").write_text(json.dumps(_profil(votes=1)), encoding="utf-8")
    (tmp_path / "casse.json").write_text("{ pas du json", encoding="utf-8")
    releve = lire_profils_disque(tmp_path)
    assert set(releve) == {"ok.json"}


def test_rapport_dit_explicitement_quand_rien_nest_perdu():
    md = generate_markdown_report(
        comparer({"a.json": _releve(votes=5)}, {"a.json": _releve(votes=5)}), "origin/main")
    assert "Aucune" in md


def test_rapport_avertit_que_les_totaux_ne_suffisent_pas():
    """L'avertissement est le cœur du rapport : sans lui, un lecteur pressé
    conclurait du tableau des totaux."""
    md = generate_markdown_report(
        comparer({"a.json": _releve(votes=5)}, {"a.json": _releve(votes=5)}), "origin/main")
    assert "Les totaux ne suffisent pas" in md
