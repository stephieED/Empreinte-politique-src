"""Tests de `audit_volumetrie_profils.py` (#429)."""

import gzip
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from audit_volumetrie_profils import (
    SEUIL_DEPOT_RECOMMANDE_GO,
    _poids_champ,
    analyser_profil,
    analyser_repertoires,
    compute_leviers,
    compute_projection,
    compute_volumetrie,
    generate_markdown_report,
)


def _ecrire(repertoire: Path, nom: str, profil: dict, indent: int = 2) -> Path:
    chemin = repertoire / nom
    chemin.write_text(json.dumps(profil, ensure_ascii=False, indent=indent), encoding="utf-8")
    return chemin


# ---------------------------------------------------------------------------
# _poids_champ — champs imbriqués
# ---------------------------------------------------------------------------

def test_poids_champ_simple():
    profil = {"votes": [{"a": 1}, {"a": 2}]}
    assert _poids_champ(profil, ("votes",)) > 0
    assert _poids_champ(profil, ("absent",)) == 0


def test_poids_champ_imbrique_ne_compte_que_le_sous_champ():
    """`co_signataires` vit DANS chaque amendement : mesurer son poids demande
    de sommer le sous-champ, pas la liste entière."""
    profil = {"amendements": [
        {"numero": "1", "co_signataires": ["an:PA1", "an:PA2"]},
        {"numero": "2", "co_signataires": []},
    ]}
    imbrique = _poids_champ(profil, ("amendements", "co_signataires"))
    entier = _poids_champ(profil, ("amendements",))
    assert 0 < imbrique < entier


def test_poids_champ_tolere_les_entrees_non_dict():
    profil = {"amendements": ["pas un dict", {"co_signataires": ["an:PA1"]}]}
    assert _poids_champ(profil, ("amendements", "co_signataires")) > 0


# ---------------------------------------------------------------------------
# analyser_profil
# ---------------------------------------------------------------------------

def test_analyser_profil_mesure_les_trois_formes(tmp_path):
    chemin = _ecrire(tmp_path, "p.json", {"votes": [{"x": "é" * 500}]})
    mesure = analyser_profil(chemin)
    assert mesure["octets_compact"] < mesure["octets"], "le compact doit être plus petit"
    assert mesure["octets_gzip"] < mesure["octets_compact"], "gzip doit être plus petit encore"


def test_analyser_profil_json_illisible_retourne_none(tmp_path):
    """Un fichier malformé ne doit jamais interrompre le scan."""
    (tmp_path / "casse.json").write_text("{ pas du json", encoding="utf-8")
    assert analyser_profil(tmp_path / "casse.json") is None


def test_analyser_profil_accents_non_echappes(tmp_path):
    """`ensure_ascii=True` gonflerait chaque accent en `\\uXXXX` et fausserait
    la mesure au profit du compact."""
    chemin = _ecrire(tmp_path, "p.json", {"nom": "é" * 100}, indent=None)
    mesure = analyser_profil(chemin)
    assert mesure["octets_compact"] <= mesure["octets"] + 2


# ---------------------------------------------------------------------------
# compute_volumetrie — extrapolation de l'échantillon
# ---------------------------------------------------------------------------

def test_compute_volumetrie_extrapole_sur_le_total_exact():
    """Les ratios viennent de l'échantillon, mais doivent être rapportés au
    volume RÉEL : rapporter le poids de l'échantillon ne représenterait rien."""
    mesures = [{"fichier": "a.json", "octets": 100, "octets_compact": 60,
                "octets_gzip": 10, "champs": {"votes": 50}}]
    exact = {"nb_profils": 10, "octets_total": 1000, "octets_median": 100,
             "octets_max": 100, "fichier_max": "a.json"}
    vol = compute_volumetrie(mesures, exact)

    assert vol["nb_profils"] == 10
    assert vol["octets_total"] == 1000
    assert vol["extrapole"] is True
    assert vol["octets_compact_total"] == 600, "60 % de 1000, pas 60"
    assert vol["poids_par_champ"]["votes"] == 500


def test_compute_volumetrie_sans_exact_reste_coherent():
    mesures = [{"fichier": "a.json", "octets": 100, "octets_compact": 60,
                "octets_gzip": 10, "champs": {"votes": 50}}]
    vol = compute_volumetrie(mesures)
    assert vol["extrapole"] is False
    assert vol["octets_total"] == 100


def test_compute_volumetrie_liste_vide():
    assert compute_volumetrie([])["nb_profils"] == 0


# ---------------------------------------------------------------------------
# compute_leviers
# ---------------------------------------------------------------------------

def test_compute_leviers_trie_par_gain_decroissant():
    vol = {"octets_total": 1000, "octets_compact_total": 700, "octets_gzip_total": 50,
           "poids_par_champ": {"votes": 100, "amendements": 600}}
    leviers = compute_leviers(vol)
    gains = [l["gain_octets"] for l in leviers]
    assert gains == sorted(gains, reverse=True)


def test_compute_leviers_aucun_ne_declare_de_perte():
    """Garde-fou #429 : tous les leviers proposés doivent DÉPLACER la donnée,
    jamais la supprimer. L'UI n'est pas définitive et la refonte analytics
    (#324) aura besoin de champs aujourd'hui inexploités."""
    vol = {"octets_total": 1000, "octets_compact_total": 700, "octets_gzip_total": 50,
           "poids_par_champ": {"amendements": 600}}
    assert all(l["perte"] is False for l in compute_leviers(vol))


def test_compute_leviers_total_nul():
    assert compute_leviers({"octets_total": 0}) == []


# ---------------------------------------------------------------------------
# compute_projection
# ---------------------------------------------------------------------------

def test_compute_projection_signale_les_deux_seuils():
    vol = {"nb_profils": 100, "octets_total": 1024 ** 3}  # 1 Go pour 100 profils
    proj = compute_projection(vol, cible=752, facteur_duplication=2.0)
    assert proj["go_projetes"] > SEUIL_DEPOT_RECOMMANDE_GO
    assert proj["depasse_seuil_push"] is True
    assert proj["depasse_seuil_depot"] is True


def test_compute_projection_facteur_duplication_agit():
    vol = {"nb_profils": 100, "octets_total": 1024 ** 3}
    seul = compute_projection(vol, 752, 1.0)["go_projetes"]
    double = compute_projection(vol, 752, 2.0)["go_projetes"]
    assert abs(double - 2 * seul) < 0.05


def test_compute_projection_estime_le_seuil_en_profils():
    vol = {"nb_profils": 100, "octets_total": 1024 ** 3}
    proj = compute_projection(vol, 752, 1.0)
    assert proj["profils_avant_seuil_depot"] == 500  # 5 Go / 10 Mo par profil


# ---------------------------------------------------------------------------
# Échantillonnage
# ---------------------------------------------------------------------------

def test_echantillon_couvre_toute_la_distribution(tmp_path):
    """Échantillon pris à intervalle régulier sur les fichiers TRIÉS par taille :
    il doit atteindre le plus gros profil. Un tirage aléatoire pourrait le
    manquer et sous-estimer le poids des gros déposants d'amendements."""
    for i in range(40):
        _ecrire(tmp_path, f"p{i:02d}.json", {"votes": [{"x": "a" * (i * 200 + 10)}]})

    mesures, erreurs, exact = analyser_repertoires([tmp_path], echantillon=8)

    assert exact["nb_profils"] == 40, "le total porte sur TOUS les fichiers"
    assert len(mesures) == 8, "l'analyse profonde ne porte que sur l'échantillon"
    assert not erreurs
    assert max(m["octets"] for m in mesures) == exact["octets_max"]


def test_echantillon_est_deterministe(tmp_path):
    for i in range(30):
        _ecrire(tmp_path, f"p{i:02d}.json", {"votes": [{"x": "a" * (i * 100 + 10)}]})
    premier = [m["fichier"] for m in analyser_repertoires([tmp_path], 6)[0]]
    second = [m["fichier"] for m in analyser_repertoires([tmp_path], 6)[0]]
    assert premier == second


def test_echantillon_zero_analyse_tout(tmp_path):
    for i in range(5):
        _ecrire(tmp_path, f"p{i}.json", {"votes": []})
    mesures, _err, exact = analyser_repertoires([tmp_path], echantillon=0)
    assert len(mesures) == exact["nb_profils"] == 5


def test_repertoire_absent_est_ignore(tmp_path):
    _ecrire(tmp_path, "p.json", {"votes": []})
    mesures, _err, exact = analyser_repertoires([tmp_path, tmp_path / "nexiste-pas"], 0)
    assert exact["nb_profils"] == 1 and len(mesures) == 1


# ---------------------------------------------------------------------------
# Rapport
# ---------------------------------------------------------------------------

def test_rapport_markdown_mentionne_le_biais_dechantillon(tmp_path):
    vol = compute_volumetrie(
        [{"fichier": "a.json", "octets": 100, "octets_compact": 60,
          "octets_gzip": 10, "champs": {"amendements": 50}}],
        {"nb_profils": 10, "octets_total": 1000, "octets_median": 100,
         "octets_max": 100, "fichier_max": "a.json"},
    )
    rapport = {"volumetrie": vol, "leviers": compute_leviers(vol),
               "projection": compute_projection(vol, 752, 2.0), "erreurs_lecture": []}
    md = generate_markdown_report(rapport)
    assert "biaisé" in md, "le biais d'échantillon doit être dit, pas supposé connu"
    assert "sans perte" in md


def test_rapport_markdown_sans_profil():
    assert "Aucun profil" in generate_markdown_report({"volumetrie": {"nb_profils": 0}})
