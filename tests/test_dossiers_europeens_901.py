"""#901 — l'index des dossiers européens : un code de procédure devient un titre.

Un amendement européen publie son `texte_vise` — `"2021/0136(COD)"` — sur 100 %
des 7 303 entrées, et `pivotAdapter.js` le lit déjà. Ce qui manquait n'était ni
une collecte ni une lecture : `resolveDossier` cherche la référence dans l'index
**français**, ne l'y trouve pas, et la fiche affiche « 590 amendements · 0
dossiers ». Un code de procédure sans titre attaché ne dit rien à un lecteur.

Cet index est ce référentiel, et rien d'autre : référence → titre, type, stade.
"""

import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "src"))

from dossiers_europeens import (  # noqa: E402
    SCHEMA_VERSION,
    DumpDossiersIndisponible,
    construire,
    document,
    identifiant,
    references_visees,
)


def _dossier(reference, stage="Procedure completed", **procedure):
    proc = {"reference": reference, "title": "Un intitulé législatif",
            "type": "COD - Ordinary legislative procedure"}
    if stage is not None:
        proc["stage_reached"] = stage
    proc.update(procedure)
    return {"procedure": proc, "meta": {"source": f"https://oeil.europarl.europa.eu/{reference}"}}


def _dump(tmp_path, dossiers):
    """Un dump `.zst` au format ParlTrack : un tableau JSON, séparateur en tête."""
    import zstandard as zstd
    chemin = tmp_path / "ep_dossiers.json.zst"
    lignes = [("[" if r == 0 else ",") + json.dumps(d, ensure_ascii=False)
              for r, d in enumerate(dossiers)]
    lignes.append("]")
    chemin.write_bytes(zstd.ZstdCompressor().compress("\n".join(lignes).encode("utf-8")))
    return chemin


def _profil(*references):
    return {"amendements": [
        {"amendement_id": None, "role_signataire": "auteur_principal",
         "amendement_non_resolu": {"institution": "parlement_europeen", "texte_vise": r}}
        for r in references
    ]}


# --------------------------------------------------------------------------
# Le périmètre : ce que les amendements visent
# --------------------------------------------------------------------------

def test_les_references_sont_lues_dans_amendement_non_resolu(tmp_path):
    """`amendement_id` reste `null` pour un amendement européen, et c'est voulu
    (#431) : la référence vit dans le bloc non résolu."""
    (tmp_path / "a.pivot.json").write_text(
        json.dumps(_profil("2021/0136(COD)", "2017/2070(INI)")), encoding="utf-8")
    (tmp_path / "b.pivot.json").write_text(
        json.dumps(_profil("2021/0136(COD)")), encoding="utf-8")

    assert references_visees(tmp_path) == {"2021/0136(COD)", "2017/2070(INI)"}


def test_un_amendement_francais_n_entre_pas_dans_le_perimetre(tmp_path):
    (tmp_path / "x.pivot.json").write_text(json.dumps({"amendements": [
        {"amendement_id": "an:17:1", "amendement_non_resolu": None},
        {"amendement_non_resolu": {"institution": "assemblee_nationale",
                                   "texte_vise": "DLR5L17N47389"}},
    ]}), encoding="utf-8")

    assert references_visees(tmp_path) == set()


def test_seuls_les_dossiers_vises_entrent_dans_l_index(tmp_path):
    """367 références servies, pas les 23 885 dossiers du dump."""
    chemin = _dump(tmp_path, [_dossier("A"), _dossier("B"), _dossier("C")])

    entrees = construire({"B"}, dump_path=chemin)

    assert [e["reference"] for e in entrees] == ["B"]


def test_une_reference_absente_du_dump_ne_produit_aucune_entree(tmp_path):
    """12 des 367, toutes de 2024-2025 : le dump des dossiers est plus ancien
    que celui des amendements. Absence datée, déclarée par l'appelant, jamais
    comblée (§2 règle 5)."""
    entrees = construire({"2025/2084(INI)"}, dump_path=_dump(tmp_path, [_dossier("A")]))

    assert entrees == []


def test_un_dossier_publie_deux_fois_n_entre_qu_une_fois(tmp_path):
    chemin = _dump(tmp_path, [_dossier("A", title="Premier"), _dossier("A", title="Second")])

    entrees = construire({"A"}, dump_path=chemin)

    assert len(entrees) == 1


def test_sans_reference_l_index_est_vide_sans_lire_le_dump():
    assert construire(set()) == []


def test_un_dump_indisponible_leve_au_lieu_de_rendre_un_index_vide(monkeypatch):
    import dossiers_europeens

    monkeypatch.setattr(dossiers_europeens, "ensure_dump", lambda *a, **k: None)

    with pytest.raises(DumpDossiersIndisponible):
        dossiers_europeens.construire({"2021/0136(COD)"})


# --------------------------------------------------------------------------
# Ce que l'entrée porte
# --------------------------------------------------------------------------

def test_l_entree_porte_le_titre_le_type_et_le_stade(tmp_path):
    entrees = construire({"2017/2070(INI)"}, dump_path=_dump(tmp_path, [
        _dossier("2017/2070(INI)", title="Implementation of the common commercial policy",
                 type="INI - Own-initiative procedure")]))

    assert entrees[0]["id"] == "pe-dossier:2017/2070(INI)"
    assert entrees[0]["titre"] == "Implementation of the common commercial policy"
    assert entrees[0]["type_procedure"] == "INI - Own-initiative procedure"
    assert entrees[0]["stade_procedural"] == "ue_procedure_achevee"


def test_le_stade_passe_par_la_table_de_textes_portes(tmp_path):
    """Une seule fabrique de cette correspondance : la recopier ici ferait
    diverger deux tables le jour où la source ajoute une valeur."""
    from normalize_parltrack_dumps import STADE_UE_PAR_LIBELLE_SOURCE

    entrees = construire({"A"}, dump_path=_dump(tmp_path, [
        _dossier("A", stage="Awaiting Parliament 2nd reading")]))

    assert entrees[0]["stade_procedural"] == (
        STADE_UE_PAR_LIBELLE_SOURCE["Awaiting Parliament 2nd reading"])


def test_un_dossier_sans_stade_porte_son_motif(tmp_path):
    entrees = construire({"A"}, dump_path=_dump(tmp_path, [_dossier("A", stage=None)]))

    assert entrees[0]["stade_procedural"] is None
    assert entrees[0]["stade_procedural_non_resolu"] == {"motif": "source_sans_stade"}


def test_un_stade_inconnu_conserve_le_libelle_recu(tmp_path):
    entrees = construire({"A"}, dump_path=_dump(tmp_path, [
        _dossier("A", stage="Awaiting alien invasion")]))

    assert entrees[0]["stade_procedural"] is None
    assert entrees[0]["stade_procedural_non_resolu"]["valeur_source"] == "Awaiting alien invasion"


def test_le_titre_n_est_pas_traduit(tmp_path):
    """Traduire un intitulé législatif produirait un titre que personne n'a
    écrit et qu'aucune source ne confirme (§2 règle 2)."""
    anglais = "Use of passenger name record (PNR) data for the prevention of terrorist offences"
    entrees = construire({"A"}, dump_path=_dump(tmp_path, [_dossier("A", title=anglais)]))

    assert entrees[0]["titre"] == anglais


def test_l_ordre_suit_la_reference(tmp_path):
    """Un ordre instable ferait bouger l'index sans que rien n'ait bougé."""
    chemin = _dump(tmp_path, [_dossier("2021/0136(COD)"), _dossier("2017/2070(INI)")])

    entrees = construire({"2021/0136(COD)", "2017/2070(INI)"}, dump_path=chemin)

    assert [e["reference"] for e in entrees] == ["2017/2070(INI)", "2021/0136(COD)"]


def test_l_entete_nomme_le_schema_et_la_licence_de_parltrack():
    """`licence_donnees` vient de `licences.py`, jamais écrit en dur (#909)."""
    entete = document([])

    assert entete["schema_version"] == SCHEMA_VERSION
    assert "ODbL" in entete["licence_donnees"] and "ParlTrack" in entete["licence_donnees"]
    assert entete["dossiers"] == []


def test_l_identifiant_ne_se_confond_pas_avec_celui_d_un_scrutin():
    """`pe:` nomme un scrutin, `pe-dossier:` un dossier. Deux espaces de noms
    distincts, comme `an:` l'est des deux."""
    from scrutins_europeens import identifiant as identifiant_scrutin

    assert identifiant("2021/0136(COD)") == "pe-dossier:2021/0136(COD)"
    assert not identifiant("X").startswith(identifiant_scrutin("X"))
