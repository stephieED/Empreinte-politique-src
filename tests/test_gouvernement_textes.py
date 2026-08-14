import io
import json
import sys
import zipfile
from pathlib import Path
from unittest.mock import patch

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from schema_gouvernement import KNOWN_STATUTS_TEXTE_GOUVERNEMENTAL
from gouvernement_textes import (
    collect_dossiers_gouvernementaux,
    ensure_dossiers_zip_downloaded,
    fetch_dossiers_gouvernementaux,
    parse_dossier_gouvernemental,
)


# ---------------------------------------------------------------------------
# Fixtures (structures calquées sur le JSON réel observé dans
# Dossiers_Legislatifs.json.zip, voir docs/an_opendata.md)
# ---------------------------------------------------------------------------

def _acte(code_acte, date_acte=None, statut_conclusion=None, enfants=None):
    return {
        "codeActe": code_acte,
        "dateActe": date_acte,
        "statutConclusion": statut_conclusion,
        "actesLegislatifs": {"acteLegislatif": enfants} if enfants else None,
    }


def _dossier(uid, titre, actes, *, legislature="17", titre_chemin="titre-chemin"):
    return {
        "uid": uid,
        "legislature": legislature,
        "titreDossier": {"titre": titre, "titreChemin": titre_chemin, "senatChemin": None},
        "initiateur": {"acteurs": {"acteur": [{"acteurRef": "PA643210", "mandatRef": "PM873637"}]}},
        "actesLegislatifs": {"acteLegislatif": actes},
    }


def _make_zip(dossiers: dict[str, dict], *, extra_files: dict[str, str] | None = None) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for uid, dossier in dossiers.items():
            zf.writestr(f"json/dossierParlementaire/{uid}.json", json.dumps({"dossierParlementaire": dossier}))
        for name, content in (extra_files or {}).items():
            zf.writestr(name, content)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# parse_dossier_gouvernemental — origine
# ---------------------------------------------------------------------------

def test_origine_proposition_de_loi_exclue():
    dossier = _dossier("TEST-PPL", "Proposition de loi test", [
        _acte("AN1-DEPOT", "2024-01-10"),
    ])
    assert parse_dossier_gouvernemental(dossier) is None


def test_origine_sans_prefixe_reconnu_exclue():
    dossier = _dossier("TEST-RES", "Résolution portant sur un sujet quelconque", [
        _acte("AN1-DEPOT", "2024-01-10"),
    ])
    assert parse_dossier_gouvernemental(dossier) is None


def test_origine_projet_de_loi_organique_incluse():
    dossier = _dossier("TEST-ORGA", "Projet de loi organique test", [
        _acte("AN1-DEPOT", "2024-01-10"),
    ])
    record = parse_dossier_gouvernemental(dossier)
    assert record is not None
    assert record["statut"] == "depose"


# ---------------------------------------------------------------------------
# parse_dossier_gouvernemental — statut : cas nominaux
# ---------------------------------------------------------------------------

def test_statut_adopte():
    dossier = _dossier("TEST-ADOPTE", "Projet de loi ordinaire test", [
        _acte("AN1-DEPOT", "2024-01-10"),
        _acte("AN1-DEBATS-DEC", "2024-03-01", {"fam_code": "TSORTF01", "libelle": "adoptée"}),
    ])
    record = parse_dossier_gouvernemental(dossier)
    assert record["statut"] == "adopte"
    assert record["sort_49_3"] is False
    assert record["warnings"] == []


def test_statut_rejete():
    dossier = _dossier("TEST-REJETE", "Projet de loi ordinaire test", [
        _acte("AN1-DEPOT", "2024-01-10"),
        _acte("AN1-DEBATS-DEC", "2024-03-01", {"fam_code": "TSORTF07", "libelle": "rejetée"}),
    ])
    record = parse_dossier_gouvernemental(dossier)
    assert record["statut"] == "rejete"
    assert record["sort_49_3"] is False
    assert record["warnings"] == []


def test_statut_retire():
    dossier = _dossier("TEST-RETIRE", "Projet de loi ordinaire test", [
        _acte("AN1-DEPOT", "2024-01-10"),
        _acte("AN1-RTRINI", "2024-02-15"),
    ])
    record = parse_dossier_gouvernemental(dossier)
    assert record["statut"] == "retire"
    assert record["sort_49_3"] is None
    assert record["warnings"] == []


def test_statut_navette_en_cours_quand_deja_examine_sans_decision():
    dossier = _dossier("TEST-NAVETTE", "Projet de loi ordinaire test", [
        _acte("AN1-DEPOT", "2024-01-10"),
        _acte("AN1-COM", "2024-02-01"),
    ])
    record = parse_dossier_gouvernemental(dossier)
    assert record["statut"] == "navette_en_cours"
    assert record["warnings"] == []


def test_statut_depose_quand_seul_le_depot_existe():
    dossier = _dossier("TEST-DEPOSE", "Projet de loi ordinaire test", [
        _acte("AN1-DEPOT", "2024-01-10"),
    ])
    record = parse_dossier_gouvernemental(dossier)
    assert record["statut"] == "depose"
    assert record["warnings"] == []


# ---------------------------------------------------------------------------
# parse_dossier_gouvernemental — cas limites de statut
# ---------------------------------------------------------------------------

def test_fam_code_inconnu_produit_un_warning_jamais_un_statut_par_defaut():
    dossier = _dossier("TEST-INCONNU", "Projet de loi ordinaire test", [
        _acte("AN1-DEPOT", "2024-01-10"),
        _acte("AN1-DEBATS-DEC", "2024-03-01", {"fam_code": "TSORTF99", "libelle": "inconnu"}),
    ])
    record = parse_dossier_gouvernemental(dossier)
    assert record["statut"] is None
    assert len(record["warnings"]) == 1
    assert "TEST-INCONNU" in record["warnings"][0]
    assert "TSORTF99" in record["warnings"][0]


def test_fam_code_sentinelle_tsortfnull_ignore_sans_warning():
    dossier = _dossier("TEST-SENTINELLE", "Projet de loi ordinaire test", [
        _acte("AN1-DEPOT", "2024-01-10"),
        _acte("SNNLEC-DEBATS-DEC", "2024-02-01", {"fam_code": "TSORTFnull"}),
    ])
    record = parse_dossier_gouvernemental(dossier)
    assert record["statut"] == "navette_en_cours"
    assert record["warnings"] == []


def test_rejete_via_49_3_censure_mappe_vers_rejete_49_3_sans_warning():
    dossier = _dossier("TEST-CENSURE", "Projet de loi ordinaire test", [
        _acte("AN1-DEPOT", "2024-01-10"),
        _acte("CMP-DEBATS-AN-DEC", "2024-03-01", {
            "fam_code": "TSORTF24",
            "libelle": "considéré comme rejeté [...] article 49, alinéa 3, motion de censure adoptée",
        }),
    ])
    record = parse_dossier_gouvernemental(dossier)
    assert record["statut"] == "rejete_49_3"
    assert record["sort_49_3"] is True
    assert record["warnings"] == []


def test_conclusion_conseil_constitutionnel_nest_pas_une_decision_de_seance():
    """CC-CONCLUSION porte un statutConclusion mais n'est pas un `-DEBATS-DEC` :
    la dernière vraie décision de séance (adoption) doit rester déterminante,
    même si la conclusion du Conseil constitutionnel est chronologiquement
    postérieure (cas réel DLR5L17N50588, voir docs/an_opendata.md)."""
    dossier = _dossier("TEST-CC", "Projet de loi ordinaire test", [
        _acte("AN1-DEPOT", "2024-01-10"),
        _acte("AN1-DEBATS-DEC", "2024-03-01", {"fam_code": "TSORTF01", "libelle": "adoptée"}),
        _acte("CC-CONCLUSION", "2024-04-01", {"fam_code": "TCD02", "libelle": "Partiellement conforme"}),
    ])
    record = parse_dossier_gouvernemental(dossier)
    assert record["statut"] == "adopte"
    assert record["warnings"] == []


def test_derniere_decision_de_seance_chronologique_prevaut_sur_une_decision_anterieure():
    """Une première lecture adoptée, puis modifiée en seconde chambre : le
    dossier est toujours en navette, pas 'adopté' (cas réel DLR5L17N54196,
    voir docs/an_opendata.md)."""
    dossier = _dossier("TEST-NAVETTE-2", "Projet de loi ordinaire test", [
        _acte("AN1-DEPOT", "2024-01-10"),
        _acte("AN1-DEBATS-DEC", "2024-03-01", {"fam_code": "TSORTF07", "libelle": "rejetée"}),
        _acte("SN1-DEBATS-DEC", "2024-04-01", {"fam_code": "TSORTF05", "libelle": "modifié"}),
    ])
    record = parse_dossier_gouvernemental(dossier)
    assert record["statut"] is None
    assert len(record["warnings"]) == 1
    assert "TSORTF05" in record["warnings"][0]


# ---------------------------------------------------------------------------
# parse_dossier_gouvernemental — dates / chambre / source_url
# ---------------------------------------------------------------------------

def test_date_depot_est_le_premier_depot_chronologique_toutes_chambres():
    dossier = _dossier("TEST-DATES", "Projet de loi ordinaire test", [
        _acte("AN1-DEPOT", "2024-01-10"),
        _acte("SN1-DEPOT", "2024-02-05"),
        _acte("AN1-DEBATS-DEC", "2024-03-01", {"fam_code": "TSORTF01", "libelle": "adoptée"}),
    ])
    record = parse_dossier_gouvernemental(dossier)
    assert record["date_depot"] == "2024-01-10"
    assert record["date_dernier_evenement"] == "2024-03-01"
    assert record["chambre_depot_initial"] == "AN"


def test_chambre_depot_initial_senat_quand_premier_depot_au_senat():
    dossier = _dossier("TEST-SENAT-DEPOT", "Projet de loi ordinaire test", [
        _acte("SN1-DEPOT", "2024-01-10"),
        _acte("AN1-DEPOT", "2024-02-05"),
    ])
    record = parse_dossier_gouvernemental(dossier)
    assert record["chambre_depot_initial"] == "Senat"
    assert record["date_depot"] == "2024-01-10"


def test_source_url_construite_depuis_legislature_et_titre_chemin():
    dossier = _dossier(
        "TEST-URL", "Projet de loi ordinaire test", [_acte("AN1-DEPOT", "2024-01-10")],
        legislature="17", titre_chemin="mon_titre_chemin",
    )
    record = parse_dossier_gouvernemental(dossier)
    assert record["source_url"] == "https://www.assemblee-nationale.fr/dyn/17/dossiers/mon_titre_chemin"


# ---------------------------------------------------------------------------
# Texte réel vérifié manuellement (PLFSS 2025, DLR5L17N50588 — structure et
# dates constatées en direct sur data.assemblee-nationale.fr le 2026-08-14,
# voir docs/an_opendata.md) : engagement de responsabilité rejeté en 1ère
# lecture (49.3 + motion de censure adoptée, chute du gouvernement Barnier),
# puis nouvel engagement en nouvelle lecture, considéré comme adopté.
# ---------------------------------------------------------------------------

def test_texte_reel_plfss_2025_49_3_puis_adoption_49_3():
    dossier = _dossier(
        "DLR5L17N50588",
        "Projet de loi de financement de la sécurité sociale pour 2025",
        [
            _acte("AN1-DEPOT", "2024-10-10"),
            _acte("SN1-DEPOT", "2024-11-08"),
            _acte("SN1-DEBATS-DEC", "2024-11-26", {"fam_code": "TSORTF05", "libelle": "modifié"}),
            _acte("CMP-DEBATS-AN-DEC", "2024-12-04", {
                "fam_code": "TSORTF24",
                "libelle": "considéré comme rejeté [...] article 49, alinéa 3, motion de censure adoptée",
            }),
            _acte("CMP-DEBATS-SN-DEC", "2025-01-23", {
                "fam_code": "TSORTF18",
                "libelle": "adopté, dans les conditions prévues à l'article 45, alinéa 3",
            }),
            _acte("CMP-DEC", "2024-11-28", {"fam_code": "TCCMP01", "libelle": "Accord"}),
            _acte("ANNLEC-DEPOT", "2024-11-26"),
            _acte("ANNLEC-DEBATS-DEC", "2025-02-12", {
                "fam_code": "TSORTF06",
                "libelle": "considéré comme adopté [...] article 49, alinéa 3",
            }),
            _acte("SNNLEC-DEPOT", "2025-02-12"),
            _acte("SNNLEC-DEBATS-DEC", "2025-02-17", {"fam_code": "TSORTFnull"}),
            _acte("CC-CONCLUSION", "2025-02-28", {"fam_code": "TCD02", "libelle": "Partiellement conforme"}),
        ],
        legislature="17",
        titre_chemin="plfss_pour_2025",
    )
    record = parse_dossier_gouvernemental(dossier)
    assert record["dossier_id"] == "DLR5L17N50588"
    assert record["titre"] == "Projet de loi de financement de la sécurité sociale pour 2025"
    assert record["statut"] == "adopte_49_3"
    assert record["sort_49_3"] is True
    assert record["date_depot"] == "2024-10-10"
    assert record["date_dernier_evenement"] == "2025-02-28"
    assert record["chambre_depot_initial"] == "AN"
    assert record["source_url"] == "https://www.assemblee-nationale.fr/dyn/17/dossiers/plfss_pour_2025"
    assert record["warnings"] == []


# ---------------------------------------------------------------------------
# collect_dossiers_gouvernementaux
# ---------------------------------------------------------------------------

def test_collect_ignore_les_entrees_non_dossier_et_les_json_illisibles():
    dossiers = {
        "TEST-OK": _dossier("TEST-OK", "Projet de loi ordinaire test", [
            _acte("AN1-DEPOT", "2024-01-10"),
        ]),
    }
    zip_bytes = _make_zip(dossiers, extra_files={
        "json/document/sans-rapport.json": "{}",
        "json/dossierParlementaire/TEST-CASSE.json": "{not valid json",
    })
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        result = collect_dossiers_gouvernementaux(zf)

    assert [d["dossier_id"] for d in result["dossiers"]] == ["TEST-OK"]
    assert result["warnings"] == []


def test_collect_exclut_les_dossiers_non_gouvernementaux():
    dossiers = {
        "TEST-GOUV": _dossier("TEST-GOUV", "Projet de loi ordinaire test", [
            _acte("AN1-DEPOT", "2024-01-10"),
        ]),
        "TEST-PARL": _dossier("TEST-PARL", "Proposition de loi test", [
            _acte("AN1-DEPOT", "2024-01-10"),
        ]),
    }
    zip_bytes = _make_zip(dossiers)
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        result = collect_dossiers_gouvernementaux(zf)

    assert [d["dossier_id"] for d in result["dossiers"]] == ["TEST-GOUV"]


def test_collect_agrege_les_warnings_de_chaque_dossier():
    dossiers = {
        "TEST-A": _dossier("TEST-A", "Projet de loi ordinaire test", [
            _acte("AN1-DEPOT", "2024-01-10"),
            _acte("AN1-DEBATS-DEC", "2024-03-01", {"fam_code": "TSORTF99"}),
        ]),
        "TEST-B": _dossier("TEST-B", "Projet de loi ordinaire test", [
            _acte("AN1-DEPOT", "2024-01-10"),
            _acte("AN1-DEBATS-DEC", "2024-03-01", {"fam_code": "TSORTF01", "libelle": "adoptée"}),
        ]),
    }
    zip_bytes = _make_zip(dossiers)
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        result = collect_dossiers_gouvernementaux(zf)

    assert len(result["warnings"]) == 1
    assert "TEST-A" in result["warnings"][0]


def test_tous_les_statuts_connus_appartiennent_a_la_nomenclature_fermee():
    dossiers = {
        "TEST-A": _dossier("TEST-A", "Projet de loi ordinaire test", [
            _acte("AN1-DEPOT", "2024-01-10"),
            _acte("AN1-DEBATS-DEC", "2024-03-01", {"fam_code": "TSORTF01", "libelle": "adoptée"}),
        ]),
    }
    zip_bytes = _make_zip(dossiers)
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        result = collect_dossiers_gouvernementaux(zf)

    for record in result["dossiers"]:
        if record["statut"] is not None:
            assert record["statut"] in KNOWN_STATUTS_TEXTE_GOUVERNEMENTAL


# ---------------------------------------------------------------------------
# ensure_dossiers_zip_downloaded / fetch_dossiers_gouvernementaux
# ---------------------------------------------------------------------------

class DummyStreamResponse:
    def __init__(self, content: bytes, status_code: int = 200):
        self.content = content
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def iter_content(self, chunk_size: int = 1024 * 1024):
        for start in range(0, len(self.content), chunk_size):
            yield self.content[start:start + chunk_size]

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


def test_ensure_dossiers_zip_downloaded_downloads_once_then_reuses_cache(tmp_path):
    zip_bytes = _make_zip({"TEST": _dossier("TEST", "Projet de loi ordinaire test", [
        _acte("AN1-DEPOT", "2024-01-10"),
    ])})
    cache_dir = tmp_path / "cache"

    with patch("gouvernement_textes.DOSSIERS_CACHE_DIR", cache_dir), \
         patch("gouvernement_textes.requests.get", return_value=DummyStreamResponse(zip_bytes)) as mock_get:
        first = ensure_dossiers_zip_downloaded()
        second = ensure_dossiers_zip_downloaded()

    assert first == second == cache_dir / "dossiers.zip"
    assert first.is_file()
    assert mock_get.call_count == 1


def test_ensure_dossiers_zip_downloaded_returns_none_on_http_error_and_leaves_no_partial_file(tmp_path):
    cache_dir = tmp_path / "cache"

    with patch("gouvernement_textes.DOSSIERS_CACHE_DIR", cache_dir), \
         patch("gouvernement_textes.requests.get", return_value=DummyStreamResponse(b"", status_code=404)):
        result = ensure_dossiers_zip_downloaded()

    assert result is None
    assert not (cache_dir / "dossiers.zip").exists()
    assert not (cache_dir / "dossiers.zip.part").exists()


def test_fetch_dossiers_gouvernementaux_returns_warning_when_download_fails():
    with patch("gouvernement_textes.ensure_dossiers_zip_downloaded", return_value=None):
        result = fetch_dossiers_gouvernementaux()

    assert result["dossiers"] == []
    assert len(result["warnings"]) == 1


def test_fetch_dossiers_gouvernementaux_delegates_to_collect(tmp_path):
    zip_bytes = _make_zip({"TEST": _dossier("TEST", "Projet de loi ordinaire test", [
        _acte("AN1-DEPOT", "2024-01-10"),
    ])})
    zip_path = tmp_path / "dossiers.zip"
    zip_path.write_bytes(zip_bytes)

    with patch("gouvernement_textes.ensure_dossiers_zip_downloaded", return_value=zip_path):
        result = fetch_dossiers_gouvernementaux()

    assert [d["dossier_id"] for d in result["dossiers"]] == ["TEST"]
