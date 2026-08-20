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
    _normalise_fonction,
    _qualite_portefeuille,
    FONCTIONS_MINISTERIELLES,
    FONCTIONS_MINISTERIELLES_OBSERVEES,
    FONCTIONS_NON_MINISTERIELLES_OBSERVEES,
    QUALITE_INCONNUE,
    QUALITE_MINISTERIELLE,
    QUALITE_NON_MINISTERIELLE,
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
        "fonction": "membre",
        "label": label,
        "debut": debut,
        "fin": fin,
        "actif": actif,
        "source_url": "https://data.assemblee-nationale.fr/static/openData/repository/...",
        "position_dans_hemicycle": "gouvernement",
    }


def _mandat_portefeuille(
    label: str,
    debut: str,
    fin: str = None,
    actif: bool = False,
    fonction: str = "Ministre",
) -> dict:
    """Mandat `typeOrgane == "MINISTERE"` tel qu'il apparaît dans un pivot :
    même catégorie que le mandat d'appartenance, mais label de portefeuille, et
    **sans** `source_url` (aucun mandat de ce chemin n'en porte).

    `fonction` reprend `infosQualite.libQualite` du zip AMO30 — c'est le champ
    qui sépare un maroquin d'une mission parlementaire (#474). Ces fabriques
    portaient `type` et non `fonction` : la clé `type` est celle produite par
    `candidate_profile._extract_mandats_officiels`, mais
    `normalize_nosdeputes` la renomme en `fonction` avant écriture du pivot,
    et c'est un pivot que `gouvernement_roster` lit. Les fixtures figées de
    #457 portent bien `fonction` ; ces fabriques les suivent désormais.
    """
    return {
        "categorie": "fonction_gouvernementale",
        "fonction": fonction,
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
# Parlementaire en mission ≠ ministre (#474)
# ---------------------------------------------------------------------------

def test_qualite_portefeuille_reconnait_les_qualites_ministerielles_observees():
    """Les 7 qualités relevées sur les mandats `MINISTERE` du dépôt."""
    for fonction in FONCTIONS_MINISTERIELLES_OBSERVEES:
        assert _qualite_portefeuille(fonction) == QUALITE_MINISTERIELLE, fonction


def test_qualite_portefeuille_en_mission_nest_pas_ministerielle():
    """Un parlementaire en mission (art. LO144) n'est pas ministre : c'est le
    fait qui a publié une attribution fausse (#474)."""
    for fonction in FONCTIONS_NON_MINISTERIELLES_OBSERVEES:
        assert _qualite_portefeuille(fonction) == QUALITE_NON_MINISTERIELLE, fonction
    assert "en mission" not in FONCTIONS_MINISTERIELLES


def test_qualite_portefeuille_valeur_inconnue_nest_jamais_un_portefeuille():
    """Liste blanche, pas liste noire (§2.5) : une 8e valeur qui apparaîtrait
    à pleine échelle est « inconnue », pas « ministérielle par défaut »."""
    assert _qualite_portefeuille("Haut-commissaire au plan") == QUALITE_INCONNUE
    assert _qualite_portefeuille(None) == QUALITE_INCONNUE
    assert _qualite_portefeuille("") == QUALITE_INCONNUE
    # `normalize_nosdeputes` remplace un `libQualite` absent par « membre » :
    # sur un mandat MINISTERE, c'est une lacune de source, pas une qualité.
    assert _qualite_portefeuille("membre") == QUALITE_INCONNUE


def test_normalise_fonction_casse_et_espaces_seulement():
    """La source écrit « Garde des sceaux » et « Garde des Sceaux » pour la
    même qualité : normalisation typographique, jamais sémantique."""
    assert _normalise_fonction("Garde des sceaux, ministre de la justice") == (
        _normalise_fonction("Garde des Sceaux, ministre de la justice")
    )
    assert _normalise_fonction("  Ministre   délégué ") == _normalise_fonction("Ministre délégué")
    # Deux libellés distincts restent distincts : aucun rapprochement par préfixe.
    assert _normalise_fonction("Ministre") != _normalise_fonction("Ministre délégué")


def test_build_roster_mandat_en_mission_nest_pas_un_portefeuille():
    """Cas synthétique minimal du défaut : le label d'un mandat de
    parlementaire en mission est l'intitulé du ministère **auprès duquel** la
    personne est missionnée — indiscernable d'un maroquin sur ce seul critère.
    """
    profils = [
        _pivot("nosdeputes:x", "X", mandats=[
            _mandat_gouv("Gouvernement (BAYROU)", "2024-12-24", "2025-09-09"),
            _mandat_portefeuille(
                "Ministère de l'économie", "2024-12-24", "2025-09-09",
                fonction="en mission",
            ),
        ]),
    ]
    warnings = []
    membres = build_gouvernement_roster(
        "BAYROU", "2024-12-24", "2025-09-09", profils, warnings=warnings
    )
    assert len(membres) == 1
    assert membres[0]["portefeuille"] is None
    assert membres[0]["source_url"] is None
    # Exclusion attendue, pas anomalie : 92 des 209 profils du dépôt portent au
    # moins un tel mandat. Un warning par occurrence noierait les vraies alertes.
    assert warnings == []


def test_build_roster_qualite_inconnue_warning_explicite_et_portefeuille_null():
    """Une qualité hors liste blanche ne devient jamais un portefeuille, et ne
    passe jamais en silence : warning nommant la personne, l'intitulé et la
    qualité rencontrée, pour que l'ajout à la liste soit une décision humaine."""
    profils = [
        _pivot("nosdeputes:x", "X", mandats=[
            _mandat_gouv("Gouvernement (BAYROU)", "2024-12-24", "2025-09-09"),
            _mandat_portefeuille(
                "Ministère de l'intérieur", "2024-12-24", "2025-09-09",
                fonction="Haut-commissaire au plan",
            ),
        ]),
    ]
    warnings = []
    membres = build_gouvernement_roster(
        "BAYROU", "2024-12-24", "2025-09-09", profils, warnings=warnings
    )
    assert len(membres) == 1
    assert membres[0]["portefeuille"] is None
    assert len(warnings) == 1
    assert "Haut-commissaire au plan" in warnings[0]
    assert "Ministère de l'intérieur" in warnings[0]
    assert "X" in warnings[0]


def test_build_roster_warning_de_qualite_inconnue_dedupe():
    """Deux mandats d'appartenance au même gouvernement réexaminent le même
    mandat ministériel : le fait est consigné une fois, pas deux."""
    profils = [
        _pivot("nosdeputes:x", "X", mandats=[
            _mandat_gouv("Gouvernement (BAYROU)", "2024-12-24", "2025-09-09"),
            _mandat_gouv("Gouvernement (BAYROU)", "2024-12-24", None, actif=True),
            _mandat_portefeuille(
                "Ministère de l'intérieur", "2024-12-24", "2025-09-09",
                fonction="Haut-commissaire au plan",
            ),
        ]),
    ]
    warnings = []
    build_gouvernement_roster("BAYROU", "2024-12-24", "2025-09-09", profils, warnings=warnings)
    assert len(warnings) == 1


def test_build_roster_portefeuille_posterieur_a_la_fin_du_gouvernement_exclu():
    """Second défaut de #474, indépendant de la qualité : un mandat
    d'appartenance jamais clos (`fin: null`) sur un gouvernement pourtant
    achevé accroche n'importe quel mandat ministériel postérieur.

    Sans borne sur la période du gouvernement, le portefeuille de 2026
    ci-dessous entrerait dans un gouvernement clos en 2025 — avec `actif:
    true` dans un gouvernement `actif: false`.
    """
    profils = [
        _pivot("nosdeputes:x", "X", mandats=[
            # Le mandat d'appartenance sans fin, l'anomalie de source.
            _mandat_gouv("Gouvernement (BAYROU)", "2024-12-24", None, actif=True),
            _mandat_portefeuille(
                "Ministère de l'économie", "2026-02-04", None, actif=True,
                fonction="Ministre",
            ),
        ]),
    ]
    membres = build_gouvernement_roster("BAYROU", "2024-12-24", "2025-09-09", profils)
    assert len(membres) == 1
    assert membres[0]["portefeuille"] is None
    assert membres[0]["debut"] == "2024-12-24"


def test_build_roster_borne_gouvernement_ne_casse_pas_le_ministre_entre_en_cours():
    """Non-régression du garde-fou de #398 : la borne ajoutée par #474 ne fait
    que restreindre, elle ne peut rien rattraper.

    Un ministre entré en cours de mandature ne doit pas se voir attribuer le
    portefeuille qu'il occupait avant — même quand ce portefeuille antérieur
    chevauche, lui, la période du gouvernement.
    """
    profils = [
        _pivot("nosdeputes:x", "X", mandats=[
            # Entré en cours de gouvernement.
            _mandat_gouv("Gouvernement (BORNE)", "2023-07-21", "2024-01-09"),
            # Portefeuille antérieur : dans la période du gouvernement, hors
            # de celle du mandat.
            _mandat_portefeuille(
                "Ministère de la culture", "2022-05-21", "2023-07-20",
                fonction="Ministre",
            ),
        ]),
    ]
    membres = build_gouvernement_roster("BORNE", "2022-05-21", "2024-01-09", profils)
    assert len(membres) == 1
    assert membres[0]["portefeuille"] is None


def test_real_pivot_astrid_panosyan_bouvet_pas_de_maroquin_fantome_sous_bayrou():
    """L'attribution fausse publiée sur `main` à `ea6f0d5` (#474).

    Le profil porte un mandat de parlementaire en mission auprès du ministère
    de l'économie (`fonction: "en mission"`, 2026-02-04, jamais clos) et
    **deux** mandats d'appartenance au gouvernement Bayrou, dont un jamais clos
    lui non plus. Le second accrochait le premier, et
    `gouvernement-BAYROU.json` publiait un portefeuille de l'économie daté du
    2026-02-04 dans un gouvernement achevé le 2025-09-09, `actif: true` dans un
    gouvernement `actif: false`.

    Les assertions portent sur des propriétés, pas sur un compte d'entrées :
    ce profil déclenche par ailleurs une duplication d'entrées (deux mandats
    d'appartenance identiques en tout sauf leur `fin`), défaut distinct et hors
    périmètre de #474 — figer le compte ici le graverait en invariant, ce que
    #457 a précisément appris à ne pas faire.
    """
    profil = _load_pivot_fixture("astrid-panosyan-bouvet")
    membres = build_gouvernement_roster("BAYROU", "2024-12-24", "2025-09-09", [profil])

    assert membres, "le mandat ministériel légitime sous Bayrou doit rester"
    assert not any(
        "économie" in (m["portefeuille"] or "") for m in membres
    ), "le ministère de la mission LO144 ne doit plus être attribué"
    # Aucun début postérieur à la fin du gouvernement, aucun actif dans un
    # gouvernement clos (critères d'acceptation de #474).
    assert all(m["debut"] <= "2025-09-09" for m in membres)
    assert all(m["actif"] is False for m in membres)
    # Le portefeuille réellement occupé, lui, est conservé.
    assert all(
        m["portefeuille"].startswith("Ministère auprès de la ministre du travail")
        for m in membres
    )
    assert all(m["source_url"] for m in membres)


def test_real_pivot_astrid_panosyan_bouvet_portefeuille_reel_conserve_sous_barnier():
    """Contrôle positif : le filtre ne rogne pas les vrais maroquins.

    Sous Barnier, la même personne détient « Ministère du travail et de
    l'emploi » (`fonction: "Ministre"`) — attribution qui doit rester intacte.
    """
    profil = _load_pivot_fixture("astrid-panosyan-bouvet")
    membres = build_gouvernement_roster("BARNIER", "2024-09-28", "2024-12-13", [profil])
    assert len(membres) == 1
    assert membres[0]["portefeuille"] == "Ministère du travail et de l’emploi"
    assert membres[0]["debut"] == "2024-09-22"
    assert membres[0]["source_url"]


def test_le_mandat_en_mission_reste_dans_le_profil():
    """#474 retire une attribution fausse, il ne supprime aucune donnée
    collectée : le mandat de parlementaire en mission est un fait public et
    traçable, il reste dans `mandats[]` du profil (critère d'acceptation).
    """
    for slug in ("astrid-panosyan-bouvet", "david-amiel"):
        profil = _load_pivot_fixture(slug)
        missions = [
            m for m in profil["mandats"]
            if m.get("categorie") == "fonction_gouvernementale"
            and m.get("fonction") == "en mission"
        ]
        assert missions, slug


# ---------------------------------------------------------------------------
# build_premier_ministre (#398)
# ---------------------------------------------------------------------------

def test_build_premier_ministre_nominal():
    profils = [
        _pivot("nosdeputes:x", "X", mandats=[
            _mandat_gouv("Gouvernement (BAYROU)", "2024-12-24", "2025-09-09"),
            _mandat_portefeuille(
                "Premier ministre", "2024-12-24", "2025-09-09",
                fonction="Premier ministre",
            ),
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
            _mandat_portefeuille(
                "Premier ministre", "2024-12-24", "2025-09-09",
                fonction="Premier ministre",
            ),
        ]),
        _pivot("nosdeputes:y", "Y", mandats=[
            _mandat_gouv("Gouvernement (BAYROU)", "2024-12-24", "2025-09-09"),
            _mandat_portefeuille(
                "Premier ministre", "2024-12-24", "2025-09-09",
                fonction="Premier ministre",
            ),
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
            _mandat_portefeuille(
                "Premier ministre", "2024-01-10", "2024-09-05",
                fonction="Premier ministre",
            ),
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


def test_build_premier_ministre_missionne_ninvente_pas_un_premier_ministre():
    """Cas latent de #474 : le label « Premier ministre » est aussi celui d'une
    mission parlementaire **auprès de** Matignon.

    Seul en lice, un missionné ne doit pas devenir Premier ministre.
    """
    profils = [
        _pivot("nosdeputes:missionne", "Missionné", mandats=[
            _mandat_gouv("Gouvernement (ATTAL)", "2024-01-10", "2024-09-05"),
            _mandat_portefeuille(
                "Premier ministre", "2024-01-12", "2024-05-05",
                fonction="en mission",
            ),
        ]),
    ]
    warnings = []
    assert build_premier_ministre(
        "ATTAL", "2024-01-10", "2024-09-05", profils, warnings=warnings
    ) is None
    assert warnings == []


def test_build_premier_ministre_missionne_nefface_pas_le_vrai_premier_ministre():
    """Le dégât ne serait pas seulement d'inventer un Premier ministre : deux
    candidats font retourner `None` **avec un warning d'ambiguïté** (§2.5), donc
    un missionné pourrait *effacer* le vrai (#474).

    Cas synthétique et non fixture : les deux mandats existent bien dans le
    corpus — `nosdeputes:david-amiel` porte « Premier ministre » /
    `en mission` du 2024-01-12 au 2024-05-05, période du gouvernement Attal —
    mais son seul mandat d'appartenance est postérieur (Lecornu II,
    2025-10-13), si bien qu'aucun chevauchement ne se produit *aujourd'hui*.
    Le fait « en mission » lui-même est vérifié sur la fixture figée, ci-dessous
    et dans `test_le_mandat_en_mission_reste_dans_le_profil`.
    """
    profils = [
        _pivot("nosdeputes:vrai-pm", "Vrai PM", mandats=[
            _mandat_gouv("Gouvernement (ATTAL)", "2024-01-10", "2024-09-05"),
            _mandat_portefeuille(
                "Premier ministre", "2024-01-10", "2024-09-05",
                fonction="Premier ministre",
            ),
        ]),
        _pivot("nosdeputes:missionne", "Missionné", mandats=[
            _mandat_gouv("Gouvernement (ATTAL)", "2024-01-10", "2024-09-05"),
            _mandat_portefeuille(
                "Premier ministre", "2024-01-12", "2024-05-05",
                fonction="en mission",
            ),
        ]),
    ]
    warnings = []
    pm = build_premier_ministre(
        "ATTAL", "2024-01-10", "2024-09-05", profils, warnings=warnings
    )
    assert pm is not None, "le vrai Premier ministre ne doit pas être effacé"
    assert pm["nom"] == "Vrai PM"
    assert not any("Premiers ministres possibles" in w for w in warnings)


def test_build_premier_ministre_label_pm_mais_autre_qualite_warning():
    """Second verrou, propre à `build_premier_ministre` : une qualité
    ministérielle connue mais différente de « Premier ministre » sur un mandat
    de label « Premier ministre » est une incohérence de source — écartée avec
    un warning, jamais retenue en silence."""
    profils = [
        _pivot("nosdeputes:x", "X", mandats=[
            _mandat_gouv("Gouvernement (BAYROU)", "2024-12-24", "2025-09-09"),
            _mandat_portefeuille(
                "Premier ministre", "2024-12-24", "2025-09-09",
                fonction="Ministre délégué",
            ),
        ]),
    ]
    warnings = []
    assert build_premier_ministre(
        "BAYROU", "2024-12-24", "2025-09-09", profils, warnings=warnings
    ) is None
    assert len(warnings) == 1
    assert "Ministre délégué" in warnings[0]
    assert "#474" in warnings[0]


def test_real_pivot_david_amiel_mission_aupres_de_matignon_jamais_premier_ministre():
    """Fixture figée : David Amiel porte bien un mandat de label « Premier
    ministre » de qualité « en mission ». Il ne devient Premier ministre
    d'aucun des gouvernements auxquels il a appartenu, et son roster Lecornu II
    ne fait apparaître aucun portefeuille « Premier ministre »."""
    profil = _load_pivot_fixture("david-amiel")
    mission = [
        m for m in profil["mandats"]
        if m.get("label") == "Premier ministre" and m.get("fonction") == "en mission"
    ]
    assert len(mission) == 1

    warnings = []
    assert build_premier_ministre(
        "LECORNU II", "2025-10-13", None, [profil], warnings=warnings
    ) is None
    assert build_premier_ministre(
        "ATTAL", "2024-01-10", "2024-09-05", [profil], warnings=warnings
    ) is None
    assert warnings == []

    membres = build_gouvernement_roster("LECORNU II", "2025-10-13", None, [profil])
    assert all(m["portefeuille"] != "Premier ministre" for m in membres)


def test_acteur_ref_absent_si_url_non_reconnue():
    """Fiche Sénat ou identité absente : `acteur_ref` reste None plutôt que
    d'être reconstruit."""
    profil = _pivot("nosdeputes:x", "X", mandats=[
        _mandat_gouv("Gouvernement (BAYROU)", "2024-12-24", "2025-09-09"),
        _mandat_portefeuille(
                "Premier ministre", "2024-12-24", "2025-09-09",
                fonction="Premier ministre",
            ),
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
