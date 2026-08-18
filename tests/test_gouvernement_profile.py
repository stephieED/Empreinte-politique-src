import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gouvernement_profile import (
    _parse_date,
    _texte_dans_periode,
    _select_textes_gouvernement,
    build_gouvernement_profile,
    main as gouvernement_profile_main,
)
from schema_gouvernement import KNOWN_STATUTS_TEXTE_GOUVERNEMENTAL, validate_profil_gouvernement

REPO_ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _pivot(id_: str, nom: str, mandats: list = None, sources: list = None) -> dict:
    return {
        "schema_version": "1",
        "id": id_,
        "nom": nom,
        "chambre": "AN",
        "parti": None,
        "groupe": None,
        "sources": sources if sources is not None else [],
        "mandats": mandats if mandats is not None else [],
        "votes": [],
        "textes_portes": [],
        "amendements": [],
        "interventions": [],
        "tags_thematiques": [],
        "meta": {"schema_version": "1", "genere_le": "2026-07-29T10:00:00+0000", "licence_donnees": "", "warnings": []},
    }


def _mandat_gouv(label: str, debut: str, fin: str = None, actif: bool = False) -> dict:
    return {
        "categorie": "fonction_gouvernementale",
        "type": "membre",
        "label": label,
        "debut": debut,
        "fin": fin,
        "actif": actif,
        "source_url": "https://data.assemblee-nationale.fr/static/openData/repository/...",
        "position_dans_hemicycle": "gouvernement",
    }


def _dossier(
    dossier_id: str,
    statut: str = "adopte",
    date_depot: str = "2024-12-30",
    chambre: str = "AN",
    sort_49_3=False,
    warnings=None,
    titre: str = "Projet de loi test",
) -> dict:
    return {
        "dossier_id": dossier_id,
        "titre": titre,
        "statut": statut,
        "sort_49_3": sort_49_3,
        "chambre_depot_initial": chambre,
        "date_depot": date_depot,
        "date_dernier_evenement": date_depot,
        "legislature": "17",
        "source_url": f"https://www.assemblee-nationale.fr/dyn/17/dossiers/{dossier_id}",
        "warnings": warnings if warnings is not None else [],
    }


# ---------------------------------------------------------------------------
# _texte_dans_periode
# ---------------------------------------------------------------------------

def test_texte_dans_periode_gouvernement_toujours_en_fonction():
    d = _parse_date("2026-01-15")
    g_debut = _parse_date("2025-10-13")
    assert _texte_dans_periode(d, g_debut, None) is True


def test_texte_dans_periode_avant_le_debut_exclu():
    d = _parse_date("2025-09-01")
    g_debut, g_fin = _parse_date("2025-10-13"), None
    assert _texte_dans_periode(d, g_debut, g_fin) is False


def test_texte_dans_periode_apres_la_fin_exclu():
    d = _parse_date("2025-10-01")
    g_debut, g_fin = _parse_date("2024-12-24"), _parse_date("2025-09-09")
    assert _texte_dans_periode(d, g_debut, g_fin) is False


def test_texte_dans_periode_date_depot_inconnue_exclu_sans_defaut():
    assert _texte_dans_periode(None, _parse_date("2024-12-24"), None) is False


# ---------------------------------------------------------------------------
# _select_textes_gouvernement
# ---------------------------------------------------------------------------

def test_select_textes_filtre_par_periode():
    dossiers = [
        _dossier("IN", date_depot="2025-01-01"),
        _dossier("OUT", date_depot="2020-01-01"),
    ]
    g_debut, g_fin = _parse_date("2024-12-24"), _parse_date("2025-09-09")
    textes, par_statut, warnings = _select_textes_gouvernement(dossiers, g_debut, g_fin)
    assert [t["dossier_id"] for t in textes] == ["IN"]
    assert par_statut["adopte"] == 1


def test_select_textes_dedoublonne_par_dossier_id():
    """Un même dossier_id présent deux fois dans l'entrée n'est jamais compté deux fois
    (protège contre un fetch dupliqué en amont)."""
    dossiers = [
        _dossier("DUP", date_depot="2025-01-01"),
        _dossier("DUP", date_depot="2025-01-01"),
    ]
    g_debut, g_fin = _parse_date("2024-12-24"), None
    textes, par_statut, _ = _select_textes_gouvernement(dossiers, g_debut, g_fin)
    assert len(textes) == 1
    assert par_statut["adopte"] == 1


def test_select_textes_statut_none_exclu_avec_warning():
    dossiers = [_dossier("X", statut=None, date_depot="2025-01-01")]
    g_debut = _parse_date("2024-12-24")
    textes, par_statut, warnings = _select_textes_gouvernement(dossiers, g_debut, None)
    assert textes == []
    assert sum(par_statut.values()) == 0
    assert any("X" in w and "statut" in w for w in warnings)


def test_select_textes_chambre_inconnue_exclue_avec_warning():
    dossiers = [_dossier("X", chambre=None, date_depot="2025-01-01")]
    g_debut = _parse_date("2024-12-24")
    textes, par_statut, warnings = _select_textes_gouvernement(dossiers, g_debut, None)
    assert textes == []
    assert any("X" in w and "chambre_depot_initial" in w for w in warnings)


def test_select_textes_propage_les_warnings_du_dossier_source():
    dossiers = [_dossier("X", date_depot="2025-01-01", warnings=["gouvernement_textes: fam_code inconnu"])]
    g_debut = _parse_date("2024-12-24")
    _, _, warnings = _select_textes_gouvernement(dossiers, g_debut, None)
    assert "gouvernement_textes: fam_code inconnu" in warnings


def test_select_textes_49_3_preserve():
    dossiers = [_dossier("X", statut="adopte_49_3", sort_49_3=True, date_depot="2025-01-01")]
    g_debut = _parse_date("2024-12-24")
    textes, par_statut, _ = _select_textes_gouvernement(dossiers, g_debut, None)
    assert textes[0]["sort_49_3"] is True
    assert par_statut["adopte_49_3"] == 1


# ---------------------------------------------------------------------------
# build_gouvernement_profile — agrégation complète
# ---------------------------------------------------------------------------

def test_build_profile_membres_et_textes_combines():
    profils = [
        _pivot("nosdeputes:a", "A", mandats=[_mandat_gouv("Gouvernement (BAYROU)", "2024-12-24", "2025-09-09")]),
        _pivot("nosdeputes:b", "B", mandats=[
            {"categorie": "mandat_electif", "label": "Mandat parlementaire", "debut": "2022-06-22", "fin": None, "actif": True}
        ]),
    ]
    dossiers = [
        _dossier("D1", statut="adopte", date_depot="2025-01-10"),
        _dossier("D2", statut="rejete", date_depot="2025-02-10"),
        _dossier("D3", statut="adopte", date_depot="2020-01-01"),  # hors période
    ]
    profil = build_gouvernement_profile(
        gouvernement_id="gouvernement:BAYROU",
        nom="Gouvernement Bayrou",
        libelle_an="BAYROU",
        periode_debut="2024-12-24",
        periode_fin="2025-09-09",
        profils=profils,
        dossiers_gouvernementaux=dossiers,
    )

    assert {m["membre_id"] for m in profil["membres"]} == {"nosdeputes:a"}
    assert {t["dossier_id"] for t in profil["textes"]} == {"D1", "D2"}
    assert profil["comptages"]["par_statut"]["adopte"] == 1
    assert profil["comptages"]["par_statut"]["rejete"] == 1
    assert profil["periode"] == {"debut": "2024-12-24", "fin": "2025-09-09", "actif": False}


def test_build_profile_gouvernement_toujours_en_fonction_actif_true():
    profil = build_gouvernement_profile(
        gouvernement_id="gouvernement:LECORNU_II",
        nom="Gouvernement Lecornu II",
        libelle_an="LECORNU II",
        periode_debut="2025-10-13",
        periode_fin=None,
        profils=[],
        dossiers_gouvernementaux=[],
    )
    assert profil["periode"]["actif"] is True
    assert profil["periode"]["fin"] is None


def test_build_profile_valide_selon_le_schema():
    profils = [
        _pivot("nosdeputes:a", "A", mandats=[_mandat_gouv("Gouvernement (BAYROU)", "2024-12-24", "2025-09-09")]),
    ]
    dossiers = [
        _dossier("D1", statut="adopte_49_3", sort_49_3=True, date_depot="2025-01-10"),
        _dossier("D2", statut=None, date_depot="2025-02-10"),  # doit être exclu, pas casser la validation
    ]
    profil = build_gouvernement_profile(
        gouvernement_id="gouvernement:BAYROU",
        nom="Gouvernement Bayrou",
        libelle_an="BAYROU",
        periode_debut="2024-12-24",
        periode_fin="2025-09-09",
        profils=profils,
        dossiers_gouvernementaux=dossiers,
    )
    assert validate_profil_gouvernement(profil) == []
    assert any("D2" in w for w in profil["meta"]["warnings"])


def test_build_profile_aucun_taux_calcule_dans_comptages():
    """Critère d'acceptation #211 : comptages.par_statut ne contient que des
    entiers bruts, aucune clé de taux/pourcentage n'est jamais introduite."""
    profils = [
        _pivot("nosdeputes:a", "A", mandats=[_mandat_gouv("Gouvernement (BAYROU)", "2024-12-24", "2025-09-09")]),
    ]
    dossiers = [_dossier("D1", statut="adopte", date_depot="2025-01-10")]
    profil = build_gouvernement_profile(
        gouvernement_id="gouvernement:BAYROU",
        nom="Gouvernement Bayrou",
        libelle_an="BAYROU",
        periode_debut="2024-12-24",
        periode_fin="2025-09-09",
        profils=profils,
        dossiers_gouvernementaux=dossiers,
    )
    par_statut = profil["comptages"]["par_statut"]
    assert set(par_statut.keys()) == KNOWN_STATUTS_TEXTE_GOUVERNEMENTAL
    for valeur in par_statut.values():
        assert isinstance(valeur, int) and not isinstance(valeur, bool)
    assert "taux" not in json.dumps(profil["comptages"])
    assert "pourcentage" not in json.dumps(profil["comptages"])
    assert set(profil["comptages"].keys()) == {"par_statut"}


def test_build_profile_dossier_deux_fois_dans_le_meme_fetch_non_double_compte():
    """Même dossier_id présent deux fois dans dossiers_gouvernementaux (fetch
    dupliqué en amont, cf. acceptance criteria #211) : compté une seule fois."""
    profils = [
        _pivot("nosdeputes:a", "A", mandats=[_mandat_gouv("Gouvernement (BAYROU)", "2024-12-24", "2025-09-09")]),
    ]
    dossiers = [
        _dossier("D1", statut="adopte", date_depot="2025-01-10"),
        _dossier("D1", statut="adopte", date_depot="2025-01-10"),
    ]
    profil = build_gouvernement_profile(
        gouvernement_id="gouvernement:BAYROU",
        nom="Gouvernement Bayrou",
        libelle_an="BAYROU",
        periode_debut="2024-12-24",
        periode_fin="2025-09-09",
        profils=profils,
        dossiers_gouvernementaux=dossiers,
    )
    assert len(profil["textes"]) == 1
    assert profil["comptages"]["par_statut"]["adopte"] == 1


def test_build_profile_sources_uniquement_des_membres_retenus():
    profils = [
        _pivot("nosdeputes:a", "A", mandats=[_mandat_gouv("Gouvernement (BAYROU)", "2024-12-24", "2025-09-09")],
               sources=[{"type": "nosdeputes", "url": "https://www.nosdeputes.fr/a", "synchro_le": "2026-01-01"}]),
        _pivot("nosdeputes:b", "B", mandats=[
            {"categorie": "mandat_electif", "label": "Mandat parlementaire", "debut": "2022-06-22", "fin": None, "actif": True}
        ], sources=[{"type": "nosdeputes", "url": "https://www.nosdeputes.fr/b", "synchro_le": "2026-01-01"}]),
    ]
    profil = build_gouvernement_profile(
        gouvernement_id="gouvernement:BAYROU",
        nom="Gouvernement Bayrou",
        libelle_an="BAYROU",
        periode_debut="2024-12-24",
        periode_fin="2025-09-09",
        profils=profils,
        dossiers_gouvernementaux=[],
    )
    urls = {s["url"] for s in profil["sources"]}
    assert urls == {"https://www.nosdeputes.fr/a"}


def test_build_profile_pas_de_reseau_appele():
    """Module pur : aucune tentative de réseau, même avec des entrées vides."""
    profil = build_gouvernement_profile(
        gouvernement_id="gouvernement:BAYROU",
        nom="Gouvernement Bayrou",
        libelle_an="BAYROU",
        periode_debut="2024-12-24",
        periode_fin="2025-09-09",
        profils=[],
        dossiers_gouvernementaux=[],
    )
    assert profil["membres"] == []
    assert profil["textes"] == []
    assert validate_profil_gouvernement(profil) == []


# ---------------------------------------------------------------------------
# build_gouvernement_profile — pivots réels du dépôt
# ---------------------------------------------------------------------------

def _load_real_pivot(slug: str) -> dict:
    path = REPO_ROOT / "pivot_data" / "profiles" / f"{slug}.pivot.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_build_profile_real_pivot_gabriel_attal():
    profil_pivot = _load_real_pivot("gabriel-attal")
    profil = build_gouvernement_profile(
        gouvernement_id="gouvernement:ATTAL",
        nom="Gouvernement Attal",
        libelle_an="ATTAL",
        periode_debut="2024-01-10",
        periode_fin="2024-09-05",
        profils=[profil_pivot],
        dossiers_gouvernementaux=[
            _dossier("D-ATTAL-1", statut="adopte", date_depot="2024-03-01"),
        ],
    )
    assert {m["membre_id"] for m in profil["membres"]} == {"nosdeputes:gabriel-attal"}
    assert profil["comptages"]["par_statut"]["adopte"] == 1
    assert validate_profil_gouvernement(profil) == []


# ---------------------------------------------------------------------------
# premier_ministre et portefeuille (#398)
# ---------------------------------------------------------------------------

def _mandat_portefeuille(label: str, debut: str, fin: str = None, actif: bool = False) -> dict:
    """Mandat `MINISTERE` tel qu'il sort de la collecte : sans `source_url`."""
    return {
        "categorie": "fonction_gouvernementale",
        "type": "Ministre",
        "label": label,
        "debut": debut,
        "fin": fin,
        "actif": actif,
        "source_url": None,
        "position_dans_hemicycle": None,
    }


def test_build_profile_premier_ministre_cable_et_valide():
    profils = [
        _pivot("nosdeputes:pm", "Première Ministre", mandats=[
            _mandat_gouv("Gouvernement (TEST)", "2025-01-01", "2025-06-30"),
            _mandat_portefeuille("Premier ministre", "2025-01-01", "2025-06-30"),
        ]),
    ]
    profil = build_gouvernement_profile(
        gouvernement_id="gouvernement:TEST", nom="Gouvernement Test", libelle_an="TEST",
        periode_debut="2025-01-01", periode_fin="2025-06-30",
        profils=profils, dossiers_gouvernementaux=[],
    )
    assert profil["premier_ministre"]["nom"] == "Première Ministre"
    assert profil["membres"][0]["portefeuille"] == "Premier ministre"
    assert validate_profil_gouvernement(profil) == []


def test_build_profile_sans_premier_ministre_reste_null():
    """Aucun profil pivot ne porte le mandat : `premier_ministre` reste null,
    jamais une valeur déduite du nom du gouvernement (§2.5)."""
    profils = [
        _pivot("nosdeputes:x", "X", mandats=[
            _mandat_gouv("Gouvernement (TEST)", "2025-01-01", "2025-06-30"),
        ]),
    ]
    profil = build_gouvernement_profile(
        gouvernement_id="gouvernement:TEST", nom="Gouvernement Test", libelle_an="TEST",
        periode_debut="2025-01-01", periode_fin="2025-06-30",
        profils=profils, dossiers_gouvernementaux=[],
    )
    assert profil["premier_ministre"] is None
    assert profil["membres"][0]["portefeuille"] is None
    assert profil["meta"]["warnings"] == []
    assert validate_profil_gouvernement(profil) == []


def test_build_profile_premier_ministre_ambigu_warning_dans_meta():
    """Le warning du roster remonte bien dans `meta.warnings` du profil."""
    profils = [
        _pivot("nosdeputes:a", "A", mandats=[
            _mandat_gouv("Gouvernement (TEST)", "2025-01-01", "2025-06-30"),
            _mandat_portefeuille("Premier ministre", "2025-01-01", "2025-06-30"),
        ]),
        _pivot("nosdeputes:b", "B", mandats=[
            _mandat_gouv("Gouvernement (TEST)", "2025-01-01", "2025-06-30"),
            _mandat_portefeuille("Premier ministre", "2025-01-01", "2025-06-30"),
        ]),
    ]
    profil = build_gouvernement_profile(
        gouvernement_id="gouvernement:TEST", nom="Gouvernement Test", libelle_an="TEST",
        periode_debut="2025-01-01", periode_fin="2025-06-30",
        profils=profils, dossiers_gouvernementaux=[],
    )
    assert profil["premier_ministre"] is None
    assert any("Premiers ministres possibles" in w for w in profil["meta"]["warnings"])
    assert validate_profil_gouvernement(profil) == []


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def test_cli_main_writes_profile(tmp_path, monkeypatch):
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "x.pivot.json").write_text(json.dumps(
        _pivot("nosdeputes:x", "X", mandats=[_mandat_gouv("Gouvernement (BAYROU)", "2024-12-24", "2025-09-09")])
    ), encoding="utf-8")

    config_path = tmp_path / "gouvernements_reels.json"
    config_path.write_text(json.dumps({
        "gouvernements": [
            {"gouvernement_id": "gouvernement:BAYROU", "nom": "Gouvernement Bayrou", "libelle_an": "BAYROU",
             "periode": {"debut": "2024-12-24", "fin": "2025-09-09"}, "fichier": "gouvernement-BAYROU.json"},
        ]
    }), encoding="utf-8")

    def fake_fetch_dossiers_gouvernementaux():
        return {"dossiers": [_dossier("D1", statut="adopte", date_depot="2025-01-10")], "warnings": []}

    monkeypatch.setattr("gouvernement_textes.fetch_dossiers_gouvernementaux", fake_fetch_dossiers_gouvernementaux)

    out_path = tmp_path / "out.json"
    rc = gouvernement_profile_main([
        "--config", str(config_path),
        "--gouvernement-id", "gouvernement:BAYROU",
        "--profiles-dir", str(profiles_dir),
        "--out", str(out_path),
        "--validate",
    ])
    assert rc == 0
    profil = json.loads(out_path.read_text(encoding="utf-8"))
    assert profil["gouvernement_id"] == "gouvernement:BAYROU"
    assert len(profil["membres"]) == 1
    assert len(profil["textes"]) == 1


def test_cli_main_unknown_gouvernement_id_returns_error(tmp_path):
    config_path = tmp_path / "gouvernements_reels.json"
    config_path.write_text(json.dumps({"gouvernements": []}), encoding="utf-8")
    rc = gouvernement_profile_main([
        "--config", str(config_path),
        "--gouvernement-id", "gouvernement:INCONNU",
    ])
    assert rc == 1
