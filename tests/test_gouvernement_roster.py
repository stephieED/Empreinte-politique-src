import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gouvernement_roster import (
    _parse_date,
    _periods_overlap,
    _expected_label,
    _est_mandat_appartenance_gouvernement,
    _mandate_matches_gouvernement,
    _derive_membre_entry,
    build_gouvernement_roster,
    build_premier_ministre,
    load_profils_from_dir,
    load_gouvernement_config,
    main as gouvernement_roster_main,
)
from schema_gouvernement import REQUIRED_MEMBRE_KEYS, REQUIRED_PREMIER_MINISTRE_KEYS

REPO_ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _pivot(
    id_: str = "nosdeputes:jean-dupont",
    nom: str = "Jean Dupont",
    mandats: list = None,
) -> dict:
    """Construit un profil pivot v1 minimal pour les tests."""
    return {
        "schema_version": "1",
        "id": id_,
        "nom": nom,
        "chambre": "AN",
        "parti": None,
        "groupe": None,
        "sources": [],
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


def _mandat_portefeuille(label: str, debut: str, fin: str = None, actif: bool = False) -> dict:
    """Mandat `typeOrgane == "MINISTERE"` tel qu'il sort de
    `candidate_profile._extract_mandats_officiels` : même catégorie que le
    mandat d'appartenance, mais label de portefeuille, et **sans**
    `source_url` (aucun mandat de ce chemin n'en porte)."""
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


# ---------------------------------------------------------------------------
# _parse_date / _periods_overlap
# ---------------------------------------------------------------------------

def test_parse_date_valid():
    assert _parse_date("2024-01-10").isoformat() == "2024-01-10"


def test_parse_date_none_and_invalid():
    assert _parse_date(None) is None
    assert _parse_date("") is None
    assert _parse_date("not-a-date") is None


def test_periods_overlap_both_unbounded():
    assert _periods_overlap(None, None, None, None) is True


def test_periods_overlap_clearly_before():
    m_debut, m_fin = _parse_date("2020-01-01"), _parse_date("2020-06-01")
    g_debut, g_fin = _parse_date("2021-01-01"), _parse_date("2021-06-01")
    assert _periods_overlap(m_debut, m_fin, g_debut, g_fin) is False


def test_periods_overlap_clearly_after():
    m_debut, m_fin = _parse_date("2022-01-01"), None
    g_debut, g_fin = _parse_date("2021-01-01"), _parse_date("2021-06-01")
    assert _periods_overlap(m_debut, m_fin, g_debut, g_fin) is False


def test_periods_overlap_true_when_intersecting():
    m_debut, m_fin = _parse_date("2021-03-01"), _parse_date("2021-09-01")
    g_debut, g_fin = _parse_date("2021-01-01"), _parse_date("2021-06-01")
    assert _periods_overlap(m_debut, m_fin, g_debut, g_fin) is True


def test_periods_overlap_still_active_mandate():
    m_debut, m_fin = _parse_date("2025-10-13"), None
    g_debut, g_fin = _parse_date("2025-10-13"), None
    assert _periods_overlap(m_debut, m_fin, g_debut, g_fin) is True


# ---------------------------------------------------------------------------
# _expected_label / _mandate_matches_gouvernement
# ---------------------------------------------------------------------------

def test_expected_label_with_sigle():
    assert _expected_label("LECORNU II") == "Gouvernement (LECORNU II)"


def test_expected_label_without_sigle():
    assert _expected_label("") == "Gouvernement"


def test_mandate_matches_gouvernement_true():
    mandat = _mandat_gouv("Gouvernement (BAYROU)", "2024-12-24", "2025-09-09")
    g_debut, g_fin = _parse_date("2024-12-24"), _parse_date("2025-09-09")
    assert _mandate_matches_gouvernement(mandat, "BAYROU", g_debut, g_fin) is True


def test_mandate_matches_gouvernement_wrong_categorie():
    mandat = {
        "categorie": "commission",
        "label": "Gouvernement (BAYROU)",
        "debut": "2024-12-24",
        "fin": "2025-09-09",
        "actif": False,
    }
    g_debut, g_fin = _parse_date("2024-12-24"), _parse_date("2025-09-09")
    assert _mandate_matches_gouvernement(mandat, "BAYROU", g_debut, g_fin) is False


def test_mandate_matches_gouvernement_wrong_label_same_period():
    """Chevauchement de période sans correspondance de libellé : exclu (voir
    docstring du module — le libellé prime sur la seule période)."""
    mandat = _mandat_gouv("Gouvernement (ATTAL)", "2024-12-24", "2025-09-09")
    g_debut, g_fin = _parse_date("2024-12-24"), _parse_date("2025-09-09")
    assert _mandate_matches_gouvernement(mandat, "BAYROU", g_debut, g_fin) is False


def test_mandate_matches_gouvernement_matching_label_disjoint_period():
    """Libellé correspondant mais période totalement disjointe : anomalie de
    données, exclue plutôt qu'incluse à tort."""
    mandat = _mandat_gouv("Gouvernement (BAYROU)", "2010-01-01", "2010-06-01")
    g_debut, g_fin = _parse_date("2024-12-24"), _parse_date("2025-09-09")
    assert _mandate_matches_gouvernement(mandat, "BAYROU", g_debut, g_fin) is False


# ---------------------------------------------------------------------------
# build_gouvernement_roster — cas synthétiques
# ---------------------------------------------------------------------------

def test_build_roster_single_matching_member():
    profils = [
        _pivot("nosdeputes:x", "X", mandats=[_mandat_gouv("Gouvernement (BAYROU)", "2024-12-24", "2025-09-09")]),
    ]
    membres = build_gouvernement_roster("BAYROU", "2024-12-24", "2025-09-09", profils)
    assert len(membres) == 1
    assert membres[0]["membre_id"] == "nosdeputes:x"
    assert membres[0]["nom"] == "X"
    assert membres[0]["portefeuille"] is None
    assert membres[0]["source_url"] is None


def test_build_roster_membre_entry_has_all_required_keys():
    profils = [
        _pivot("nosdeputes:x", "X", mandats=[_mandat_gouv("Gouvernement (BAYROU)", "2024-12-24", "2025-09-09")]),
    ]
    membres = build_gouvernement_roster("BAYROU", "2024-12-24", "2025-09-09", profils)
    assert set(membres[0].keys()) == REQUIRED_MEMBRE_KEYS


def test_build_roster_pivot_without_any_governmental_mandate_excluded():
    """Pivot sans mandat gouvernemental : absent du roster."""
    profils = [
        _pivot("nosdeputes:y", "Y", mandats=[
            {"categorie": "mandat_electif", "label": "Mandat parlementaire", "debut": "2022-06-22", "fin": None, "actif": True},
        ]),
    ]
    membres = build_gouvernement_roster("BAYROU", "2024-12-24", "2025-09-09", profils)
    assert membres == []


def test_build_roster_different_government_excluded():
    profils = [
        _pivot("nosdeputes:x", "X", mandats=[_mandat_gouv("Gouvernement (ATTAL)", "2024-01-10", "2024-09-05")]),
    ]
    membres = build_gouvernement_roster("BAYROU", "2024-12-24", "2025-09-09", profils)
    assert membres == []


def test_build_roster_multiple_members():
    profils = [
        _pivot("nosdeputes:a", "A", mandats=[_mandat_gouv("Gouvernement (LECORNU II)", "2025-10-13", None, actif=True)]),
        _pivot("nosdeputes:b", "B", mandats=[_mandat_gouv("Gouvernement (LECORNU II)", "2025-10-13", "2026-02-26")]),
    ]
    membres = build_gouvernement_roster("LECORNU II", "2025-10-13", None, profils)
    ids = {m["membre_id"] for m in membres}
    assert ids == {"nosdeputes:a", "nosdeputes:b"}


def test_build_roster_membre_with_split_mandate_two_periods():
    """Un même membre avec deux mandats distincts pour un même gouvernement
    (changement de portefeuille en cours de gouvernement) : les deux
    entrées sont conservées, une par période (voir schema_gouvernement.py:
    'un enregistrement par ministre et par période si changement de
    portefeuille')."""
    profils = [
        _pivot("nosdeputes:z", "Z", mandats=[
            _mandat_gouv("Gouvernement (BORNE)", "2022-05-21", "2023-07-20"),
            _mandat_gouv("Gouvernement (BORNE)", "2023-07-21", "2024-01-09"),
        ]),
    ]
    membres = build_gouvernement_roster("BORNE", "2022-05-21", "2024-01-09", profils)
    assert len(membres) == 2
    assert {(m["debut"], m["fin"]) for m in membres} == {
        ("2022-05-21", "2023-07-20"),
        ("2023-07-21", "2024-01-09"),
    }


def test_build_roster_ambiguous_overlap_two_successive_governments():
    """Cas de chevauchement de période ambigu : un mandat d'un gouvernement
    voisin (période adjacente/chevauchante par erreur de saisie) n'est
    jamais confondu avec le gouvernement ciblé grâce au libellé exact."""
    profils = [
        _pivot("nosdeputes:x", "X", mandats=[
            _mandat_gouv("Gouvernement (BARNIER)", "2024-09-28", "2024-12-13"),
            _mandat_gouv("Gouvernement (BAYROU)", "2024-12-24", "2025-09-09"),
        ]),
    ]
    membres_bayrou = build_gouvernement_roster("BAYROU", "2024-12-24", "2025-09-09", profils)
    assert len(membres_bayrou) == 1
    assert membres_bayrou[0]["debut"] == "2024-12-24"

    membres_barnier = build_gouvernement_roster("BARNIER", "2024-09-28", "2024-12-13", profils)
    assert len(membres_barnier) == 1
    assert membres_barnier[0]["debut"] == "2024-09-28"


# ---------------------------------------------------------------------------
# build_gouvernement_roster — pivots réels, figés en fixtures (#457)
# ---------------------------------------------------------------------------

FIXTURES_PIVOTS_DIR = Path(__file__).resolve().parent / "fixtures" / "gouvernement_roster"


def _load_pivot_fixture(slug: str) -> dict:
    """Charge un pivot réel **figé** sous `tests/fixtures/gouvernement_roster/`.

    Ces tests sont les vérifications d'acceptation de #209 : ils confrontent
    `build_gouvernement_roster` à de vrais profils, pas à des cas fabriqués.
    Ils lisaient `pivot_data/profiles/` directement, et cassaient donc à chaque
    mise à jour du corpus — y compris quand la donnée **s'améliore** (#457 : un
    portefeuille jusque-là manquant a fini par être renseigné, et le test l'a
    signalé comme un échec). Un test qui rougit parce qu'une lacune a été
    comblée envoie le mauvais signal : la couverture du corpus vivant relève du
    quality gate (`check_quality_gate.py` §5), pas d'une assertion unitaire.

    Les fixtures sont donc des **extraits** des vrais pivots, réduits aux seuls
    champs que `gouvernement_roster` lit (`id`, `nom`, `identite.source_url`,
    `mandats[]`) et aux catégories de mandat `fonction_gouvernementale` et
    `mandat_electif` — quelques Ko au lieu de quelques centaines. `mandats[]`
    conserve l'ordre de la source : le roster émet ses entrées dans cet ordre.
    `mandat_electif` est gardé bien qu'inerte ici, pour que le filtrage par
    catégorie porte réellement sur quelque chose.

    Chaque fixture consigne sa provenance dans `meta.fixture` (fichier source,
    ref du dépôt, date d'extraction — AGENTS.md §2.2) : la rafraîchir, c'est
    rejouer cette même réduction sur le pivot courant.
    """
    path = FIXTURES_PIVOTS_DIR / f"{slug}.pivot.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_real_pivot_gabriel_attal_attal_government():
    profil = _load_pivot_fixture("gabriel-attal")
    membres = build_gouvernement_roster("ATTAL", "2024-01-10", "2024-09-05", [profil])
    assert len(membres) == 1
    assert membres[0]["membre_id"] == "nosdeputes:gabriel-attal"
    assert membres[0]["debut"] == "2024-01-10"
    assert membres[0]["fin"] == "2024-09-05"
    assert membres[0]["actif"] is False


def test_real_pivot_gabriel_attal_excluded_from_unrelated_government():
    """Gabriel Attal n'a jamais siégé dans le gouvernement Barnier."""
    profil = _load_pivot_fixture("gabriel-attal")
    membres = build_gouvernement_roster("BARNIER", "2024-09-28", "2024-12-13", [profil])
    assert membres == []


def test_real_pivot_charlotte_parmentier_lecocq_bayrou_government():
    """Vérification manuelle (acceptation #209) : Gouvernement Bayrou contre
    un profil pivot réel.

    Ce profil porte cinq portefeuilles ministériels, répartis sur trois
    gouvernements. Le test vérifie que celui rattaché est **celui de la période
    Bayrou** (2024-12-24 → 2025-09-09) : c'est l'objet de
    `_portefeuilles_du_mandat`, qui teste le chevauchement contre le mandat
    d'appartenance du membre. Il assenait auparavant `portefeuille is None`,
    ce qui figeait une lacune de données en invariant (#457) — l'intitulé est
    renseigné depuis, et le test échouait pour cette raison-là.
    """
    profil = _load_pivot_fixture("charlotte-parmentier-lecocq")
    membres = build_gouvernement_roster("BAYROU", "2024-12-24", "2025-09-09", [profil])
    assert len(membres) == 1
    assert membres[0]["nom"] == "Charlotte Parmentier-Lecocq"
    assert membres[0]["portefeuille"] == (
        "Ministère délégué auprès de la ministre du travail, de la santé, "
        "de la solidarité et des familles, chargé de l'autonomie et du handicap"
    )
    assert membres[0]["debut"] == "2024-12-24"
    assert membres[0]["fin"] == "2025-09-09"
    # Renseigné implique traçable : le schéma refuse un intitulé sans source.
    assert membres[0]["source_url"]


def test_real_pivot_david_amiel_lecornu_ii_deux_portefeuilles_un_seul_actif():
    """Vérification manuelle (acceptation #209) : Gouvernement Lecornu II
    contre un profil pivot réel, changement de portefeuille **sans changement
    de gouvernement**.

    David Amiel est ministre délégué chargé de la fonction publique jusqu'au
    2026-02-21, puis ministre de l'action et des comptes publics à partir du
    2026-02-22 — deux fonctions distinctes, deux périodes distinctes, un seul
    mandat d'appartenance (jamais scindé, lui). Le roster rend donc **deux
    entrées pour un même `membre_id`**, une par période : les fondre en une
    seule effacerait un fait vérifiable (AGENTS.md §2.2), et en choisir une
    arbitrairement serait pire encore.

    Corollaire à connaître (#457) : `membres[]` dénombre des **entrées**, pas
    des personnes. Sur les 10 gouvernements publiés, 7 sont concernés — 116
    entrées pour 95 personnes, Borne à lui seul 31 entrées pour 23 personnes.
    Rien ne publie d'effectif aujourd'hui : `comptages.par_statut` dénombre des
    textes de loi, et `GovernmentProfile.jsx` liste les membres sans en donner
    le total. Aucun dénominateur faux n'est donc exposé (§2.7). Mais toute vue
    future annonçant « N ministres » devra dédupliquer par `membre_id`, sans
    quoi elle affichera 31 pour Borne au lieu de 23.
    """
    profil = _load_pivot_fixture("david-amiel")
    membres = build_gouvernement_roster("LECORNU II", "2025-10-13", None, [profil])
    assert len(membres) == 2
    assert {m["membre_id"] for m in membres} == {"nosdeputes:david-amiel"}

    # Ordre chronologique : `_portefeuilles_du_mandat` trie par date de début.
    delegue, ministre = membres
    assert delegue["portefeuille"].startswith(
        "Ministère délégué auprès de la ministre de l'action et des comptes publics"
    )
    assert delegue["debut"] == "2025-10-13"
    assert delegue["fin"] == "2026-02-21"
    assert delegue["actif"] is False

    assert ministre["portefeuille"] == "Ministère de l'action et des comptes publics"
    assert ministre["debut"] == "2026-02-22"
    assert ministre["fin"] is None
    assert ministre["actif"] is True

    # Les deux périodes se succèdent sans trou ni recouvrement : elles pavent
    # le mandat d'appartenance, elles ne le comptent pas deux fois.
    assert delegue["fin"] < ministre["debut"]


# ---------------------------------------------------------------------------
# portefeuille ministériel (#398)
# ---------------------------------------------------------------------------

def test_est_mandat_appartenance_gouvernement_distingue_les_deux_natures():
    """La catégorie `fonction_gouvernementale` mélange l'appartenance
    (typeOrgane GOUVERNEMENT) et le portefeuille (MINISTERE) : seul le label
    les distingue."""
    assert _est_mandat_appartenance_gouvernement("Gouvernement (BORNE)") is True
    assert _est_mandat_appartenance_gouvernement("Gouvernement") is True
    assert _est_mandat_appartenance_gouvernement("Premier ministre") is False
    assert _est_mandat_appartenance_gouvernement(
        "Ministère de l'éducation nationale et de la jeunesse"
    ) is False


def test_build_roster_portefeuille_renseigne_avec_sa_source():
    profils = [
        _pivot("nosdeputes:x", "X", mandats=[
            _mandat_gouv("Gouvernement (BAYROU)", "2024-12-24", "2025-09-09"),
            _mandat_portefeuille("Ministère de l'intérieur", "2024-12-24", "2025-09-09"),
        ]),
    ]
    membres = build_gouvernement_roster("BAYROU", "2024-12-24", "2025-09-09", profils)
    assert len(membres) == 1
    assert membres[0]["portefeuille"] == "Ministère de l'intérieur"
    # Le schéma exige une source dès que le portefeuille est renseigné : elle
    # est reprise du mandat d'appartenance, issu du même zip AMO30.
    assert membres[0]["source_url"]


def test_build_roster_portefeuille_hors_periode_du_mandat_ignore():
    """Le portefeuille occupé dans un gouvernement antérieur ne doit pas être
    recopié sur le mandat courant."""
    profils = [
        _pivot("nosdeputes:x", "X", mandats=[
            _mandat_gouv("Gouvernement (BAYROU)", "2024-12-24", "2025-09-09"),
            _mandat_portefeuille("Ministère de la culture", "2020-07-07", "2022-05-16"),
        ]),
    ]
    membres = build_gouvernement_roster("BAYROU", "2024-12-24", "2025-09-09", profils)
    assert len(membres) == 1
    assert membres[0]["portefeuille"] is None
    assert membres[0]["source_url"] is None


def test_build_roster_deux_portefeuilles_donnent_deux_entrees():
    """Chevauchements multiples : tous retenus, un enregistrement par période
    (§2.5 — ne jamais choisir arbitrairement l'un des deux)."""
    profils = [
        _pivot("nosdeputes:x", "X", mandats=[
            _mandat_gouv("Gouvernement (BORNE)", "2022-05-21", "2024-01-09"),
            _mandat_portefeuille("Ministère des comptes publics", "2022-05-21", "2023-07-20"),
            _mandat_portefeuille("Ministère de l'éducation nationale", "2023-07-21", "2024-01-09"),
        ]),
    ]
    membres = build_gouvernement_roster("BORNE", "2022-05-16", "2024-01-09", profils)
    assert len(membres) == 2
    assert [m["portefeuille"] for m in membres] == [
        "Ministère des comptes publics",
        "Ministère de l'éducation nationale",
    ]
    # Les dates sont celles de chaque portefeuille, pas celles du mandat
    # d'appartenance : c'est ce qui distingue les deux entrées.
    assert [(m["debut"], m["fin"]) for m in membres] == [
        ("2022-05-21", "2023-07-20"),
        ("2023-07-21", "2024-01-09"),
    ]
    assert all(set(m.keys()) == REQUIRED_MEMBRE_KEYS for m in membres)


def test_build_roster_portefeuille_sans_source_tracable_reste_null_avec_warning():
    """Sans source, l'intitulé n'est pas publiable (§2.3) : `portefeuille`
    retombe à null plutôt que d'être renseigné sans traçabilité."""
    mandat_sans_source = _mandat_gouv("Gouvernement (BAYROU)", "2024-12-24", "2025-09-09")
    mandat_sans_source["source_url"] = None
    profils = [
        _pivot("nosdeputes:x", "X", mandats=[
            mandat_sans_source,
            _mandat_portefeuille("Ministère de l'intérieur", "2024-12-24", "2025-09-09"),
        ]),
    ]
    warnings = []
    membres = build_gouvernement_roster(
        "BAYROU", "2024-12-24", "2025-09-09", profils, warnings=warnings
    )
    assert len(membres) == 1
    assert membres[0]["portefeuille"] is None
    assert len(warnings) == 1
    assert "Ministère de l'intérieur" in warnings[0]


def test_real_pivot_gabriel_attal_deux_portefeuilles_sous_borne():
    """Cas réel : Gabriel Attal a changé de portefeuille en cours de
    gouvernement Borne (comptes publics, puis éducation nationale)."""
    profil = _load_pivot_fixture("gabriel-attal")
    membres = build_gouvernement_roster("BORNE", "2022-05-16", "2024-01-09", [profil])
    assert len(membres) == 2
    portefeuilles = [m["portefeuille"] for m in membres]
    assert any("comptes publics" in p for p in portefeuilles)
    assert any("éducation nationale" in p for p in portefeuilles)
    assert all(m["source_url"] for m in membres)


# ---------------------------------------------------------------------------
# build_premier_ministre (#398)
# ---------------------------------------------------------------------------

def test_build_premier_ministre_nominal():
    profils = [
        _pivot("nosdeputes:x", "X", mandats=[
            _mandat_gouv("Gouvernement (BAYROU)", "2024-12-24", "2025-09-09"),
            _mandat_portefeuille("Premier ministre", "2024-12-24", "2025-09-09"),
        ]),
    ]
    pm = build_premier_ministre("BAYROU", "2024-12-24", "2025-09-09", profils)
    assert pm is not None
    assert pm["nom"] == "X"
    assert set(pm.keys()) == REQUIRED_PREMIER_MINISTRE_KEYS


def test_build_premier_ministre_aucun_candidat_reste_none():
    """Cas attendu et majoritaire : le Premier ministre n'a pas de profil
    pivot local. Aucune valeur déduite du nom du gouvernement (§2.5)."""
    profils = [
        _pivot("nosdeputes:x", "X", mandats=[
            _mandat_gouv("Gouvernement (BAYROU)", "2024-12-24", "2025-09-09"),
            _mandat_portefeuille("Ministère de l'intérieur", "2024-12-24", "2025-09-09"),
        ]),
    ]
    warnings = []
    assert build_premier_ministre(
        "BAYROU", "2024-12-24", "2025-09-09", profils, warnings=warnings
    ) is None
    assert warnings == []


def test_build_premier_ministre_ambigu_reste_none_avec_warning():
    """Deux candidats : trancher serait arbitraire — None + warning."""
    profils = [
        _pivot("nosdeputes:x", "X", mandats=[
            _mandat_gouv("Gouvernement (BAYROU)", "2024-12-24", "2025-09-09"),
            _mandat_portefeuille("Premier ministre", "2024-12-24", "2025-09-09"),
        ]),
        _pivot("nosdeputes:y", "Y", mandats=[
            _mandat_gouv("Gouvernement (BAYROU)", "2024-12-24", "2025-09-09"),
            _mandat_portefeuille("Premier ministre", "2024-12-24", "2025-09-09"),
        ]),
    ]
    warnings = []
    assert build_premier_ministre(
        "BAYROU", "2024-12-24", "2025-09-09", profils, warnings=warnings
    ) is None
    assert len(warnings) == 1
    assert "Premiers ministres possibles" in warnings[0]


def test_build_premier_ministre_dun_autre_gouvernement_non_retenu():
    """Le mandat d'appartenance désambiguïse : un Premier ministre d'un autre
    gouvernement n'est jamais capté par simple proximité de période."""
    profils = [
        _pivot("nosdeputes:x", "X", mandats=[
            _mandat_gouv("Gouvernement (ATTAL)", "2024-01-10", "2024-09-05"),
            _mandat_portefeuille("Premier ministre", "2024-01-10", "2024-09-05"),
        ]),
    ]
    assert build_premier_ministre("BARNIER", "2024-09-21", "2024-12-13", profils) is None


def test_real_pivot_premier_ministre_attal_et_philippe():
    """Cas réels : les seuls Premiers ministres ayant un profil pivot local."""
    attal = _load_pivot_fixture("gabriel-attal")
    pm_attal = build_premier_ministre("ATTAL", "2024-01-10", "2024-09-05", [attal])
    assert pm_attal["nom"] == "Gabriel Attal"
    assert pm_attal["acteur_ref"] == "PA722190"
    assert pm_attal["source_url"]

    philippe = _load_pivot_fixture("edouard-philippe")
    pm_philippe = build_premier_ministre("PHILIPPE 2", "2017-06-20", "2020-07-06", [philippe])
    assert pm_philippe["nom"] == "Édouard Philippe"

    # Le même profil ne doit pas devenir Premier ministre d'un gouvernement
    # auquel il n'a pas appartenu.
    assert build_premier_ministre("BAYROU", "2024-12-24", "2025-09-09", [attal]) is None


def test_acteur_ref_absent_si_url_non_reconnue():
    """Fiche Sénat ou identité absente : `acteur_ref` reste None plutôt que
    d'être reconstruit."""
    profil = _pivot("nosdeputes:x", "X", mandats=[
        _mandat_gouv("Gouvernement (BAYROU)", "2024-12-24", "2025-09-09"),
        _mandat_portefeuille("Premier ministre", "2024-12-24", "2025-09-09"),
    ])
    profil["identite"] = {"source_url": "https://archive.nossenateurs.fr/stephane-mazars"}
    pm = build_premier_ministre("BAYROU", "2024-12-24", "2025-09-09", [profil])
    assert pm["acteur_ref"] is None


# ---------------------------------------------------------------------------
# load_profils_from_dir
# ---------------------------------------------------------------------------

def test_load_profils_from_dir(tmp_path):
    (tmp_path / "a.pivot.json").write_text(json.dumps(_pivot("nosdeputes:a", "A")), encoding="utf-8")
    (tmp_path / "b.pivot.json").write_text(json.dumps(_pivot("nosdeputes:b", "B")), encoding="utf-8")
    (tmp_path / "not-a-pivot.json").write_text(json.dumps({"foo": "bar"}), encoding="utf-8")

    profils = load_profils_from_dir(tmp_path)
    assert len(profils) == 2
    ids = {p["id"] for p in profils}
    assert ids == {"nosdeputes:a", "nosdeputes:b"}


def test_load_profils_from_dir_ignores_invalid_json(tmp_path):
    (tmp_path / "broken.pivot.json").write_text("{not valid json", encoding="utf-8")
    (tmp_path / "ok.pivot.json").write_text(json.dumps(_pivot("nosdeputes:ok", "OK")), encoding="utf-8")

    profils = load_profils_from_dir(tmp_path)
    assert len(profils) == 1
    assert profils[0]["id"] == "nosdeputes:ok"


# ---------------------------------------------------------------------------
# load_gouvernement_config
# ---------------------------------------------------------------------------

def test_load_gouvernement_config_found(tmp_path):
    config_path = tmp_path / "gouvernements_reels.json"
    config_path.write_text(json.dumps({
        "gouvernements": [
            {"gouvernement_id": "gouvernement:BAYROU", "nom": "Gouvernement Bayrou", "libelle_an": "BAYROU",
             "periode": {"debut": "2024-12-24", "fin": "2025-09-09"}, "fichier": "gouvernement-BAYROU.json"},
        ]
    }), encoding="utf-8")

    entry = load_gouvernement_config(config_path, "gouvernement:BAYROU")
    assert entry["libelle_an"] == "BAYROU"


def test_load_gouvernement_config_not_found(tmp_path):
    config_path = tmp_path / "gouvernements_reels.json"
    config_path.write_text(json.dumps({"gouvernements": []}), encoding="utf-8")

    try:
        load_gouvernement_config(config_path, "gouvernement:INCONNU")
        assert False, "ValueError attendue"
    except ValueError as exc:
        assert "gouvernement:INCONNU" in str(exc)


# ---------------------------------------------------------------------------
# Test de cohérence du fichier raw_data/gouvernements_reels.json
# (miroir de test_repository_groupes_reels_json_is_valid)
# ---------------------------------------------------------------------------

def test_repository_gouvernements_reels_json_is_valid():
    config_path = REPO_ROOT / "raw_data" / "gouvernements_reels.json"
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    assert isinstance(payload.get("gouvernements"), list)
    assert payload["gouvernements"]

    seen_ids = set()
    for entry in payload["gouvernements"]:
        for key in ("gouvernement_id", "nom", "periode", "fichier", "libelle_an"):
            assert key in entry, f"clé manquante {key!r} dans {entry}"
        assert entry["gouvernement_id"].startswith("gouvernement:")
        assert entry["gouvernement_id"] not in seen_ids, f"doublon : {entry['gouvernement_id']}"
        seen_ids.add(entry["gouvernement_id"])
        assert "debut" in entry["periode"] and "fin" in entry["periode"]
        assert entry["periode"]["debut"] is not None


def test_repository_gouvernements_reels_json_covers_bayrou_and_lecornu():
    """Critère d'acceptation #209 : Bayrou et Lecornu doivent figurer dans
    l'échantillon disponible."""
    config_path = REPO_ROOT / "raw_data" / "gouvernements_reels.json"
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    libelles = {entry["libelle_an"] for entry in payload["gouvernements"]}
    assert "BAYROU" in libelles
    assert any(libelle.startswith("LECORNU") for libelle in libelles)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def test_cli_main_writes_roster(tmp_path):
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

    out_path = tmp_path / "out.json"
    rc = gouvernement_roster_main([
        "--config", str(config_path),
        "--gouvernement-id", "gouvernement:BAYROU",
        "--profiles-dir", str(profiles_dir),
        "--out", str(out_path),
    ])
    assert rc == 0
    roster = json.loads(out_path.read_text(encoding="utf-8"))
    assert roster["gouvernement_id"] == "gouvernement:BAYROU"
    assert len(roster["membres"]) == 1
    assert roster["membres"][0]["membre_id"] == "nosdeputes:x"


def test_cli_main_unknown_gouvernement_id_returns_error(tmp_path):
    config_path = tmp_path / "gouvernements_reels.json"
    config_path.write_text(json.dumps({"gouvernements": []}), encoding="utf-8")
    rc = gouvernement_roster_main([
        "--config", str(config_path),
        "--gouvernement-id", "gouvernement:INCONNU",
    ])
    assert rc == 1
