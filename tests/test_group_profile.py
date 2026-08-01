import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from group_profile import (
    _parse_date,
    _member_eligible_at,
    _derive_membre_entry,
    _build_vote_index,
    _compute_cohesion_votes,
    _aggregate_tags_thematiques,
    _aggregate_amendements,
    compute_ecarts_cohesion_internes,
    build_groupe_profile,
    _is_pivot_v1,
    main as group_profile_main,
)
from schema_groupe import validate_profil_groupe


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _pivot(
    id_: str = "nosdeputes:jean-dupont",
    nom: str = "Jean Dupont",
    groupe: str = "Socialistes et apparentés",
    mandats: list = None,
    votes: list = None,
    tags: list = None,
    interventions: list = None,
    amendements: list = None,
) -> dict:
    """Construit un profil pivot v1 minimal pour les tests."""
    return {
        "schema_version": "1",
        "id": id_,
        "nom": nom,
        "chambre": "AN",
        "parti": None,
        "groupe": groupe,
        "sources": [
            {"type": "nosdeputes", "url": f"https://www.nosdeputes.fr/{id_.split(':')[1]}", "synchro_le": "2026-07-29T10:00:00+0000"}
        ],
        "mandats": mandats if mandats is not None else [
            {
                "categorie": "mandat_electif",
                "label": "Mandat parlementaire",
                "fonction": "mandat",
                "debut": "2022-06-22",
                "fin": None,
                "actif": True,
            }
        ],
        "votes": votes if votes is not None else [],
        "textes_portes": [],
        "interventions": interventions if interventions is not None else [],
        "amendements": amendements if amendements is not None else [],
        "tags_thematiques": tags if tags is not None else [],
        "meta": {
            "schema_version": "1",
            "genere_le": "2026-07-29T10:00:00+0000",
            "licence_donnees": "ODbL",
            "warnings": [],
        },
    }


def _vote(numero: str, position: str, date: str = "2024-01-15", texte: str = "PLF", sort: str = "adopté") -> dict:
    return {
        "date": date,
        "texte": texte,
        "position": position,
        "numero_scrutin": numero,
        "sort": sort,
        "groupe_au_moment_du_vote": None,
        "source_url": None,
    }


def _mandat_electif(debut: str, fin: str = None, actif: bool = None) -> dict:
    return {
        "categorie": "mandat_electif",
        "label": "Mandat",
        "fonction": "mandat",
        "debut": debut,
        "fin": fin,
        "actif": actif if actif is not None else (fin is None),
    }


# ---------------------------------------------------------------------------
# _parse_date
# ---------------------------------------------------------------------------

def test_parse_date_valid():
    d = _parse_date("2022-06-22")
    from datetime import date
    assert d == date(2022, 6, 22)


def test_parse_date_with_time():
    d = _parse_date("2022-06-22T14:30:00")
    from datetime import date
    assert d == date(2022, 6, 22)


def test_parse_date_none_returns_none():
    assert _parse_date(None) is None


def test_parse_date_empty_string_returns_none():
    assert _parse_date("") is None


def test_parse_date_invalid_returns_none():
    assert _parse_date("not-a-date") is None


# ---------------------------------------------------------------------------
# _member_eligible_at
# ---------------------------------------------------------------------------

def test_eligible_active_mandat_no_end():
    mandats = [_mandat_electif("2022-06-22")]
    assert _member_eligible_at(mandats, "2024-01-15") is True


def test_eligible_within_closed_mandat():
    mandats = [_mandat_electif("2017-06-21", "2022-06-21")]
    assert _member_eligible_at(mandats, "2019-06-01") is True


def test_not_eligible_before_mandat():
    mandats = [_mandat_electif("2022-06-22")]
    assert _member_eligible_at(mandats, "2020-01-01") is False


def test_not_eligible_after_closed_mandat():
    mandats = [_mandat_electif("2017-06-21", "2022-06-21")]
    assert _member_eligible_at(mandats, "2023-01-01") is False


def test_eligible_no_date_returns_true():
    mandats = [_mandat_electif("2022-06-22")]
    assert _member_eligible_at(mandats, None) is True


def test_eligible_no_mandats_returns_true():
    # Pas d'info = conservateur → éligible
    assert _member_eligible_at([], "2024-01-15") is True


def test_eligible_multiple_mandats_second_matches():
    mandats = [
        _mandat_electif("2017-06-21", "2022-06-21"),
        _mandat_electif("2022-06-22"),
    ]
    assert _member_eligible_at(mandats, "2023-01-01") is True


def test_not_eligible_between_two_mandats():
    mandats = [
        _mandat_electif("2012-06-01", "2017-06-20"),
        _mandat_electif("2022-06-22"),
    ]
    # Date dans la fenêtre entre les deux mandats
    assert _member_eligible_at(mandats, "2018-01-01") is False


def test_eligible_ignores_non_electif_mandats():
    mandats = [
        {"categorie": "commission", "debut": "2022-07-01", "fin": None, "actif": True},
    ]
    # Pas de mandat_electif → conservateur
    assert _member_eligible_at(mandats, "2023-01-01") is True


# ---------------------------------------------------------------------------
# _derive_membre_entry
# ---------------------------------------------------------------------------

def test_derive_membre_id_nom():
    p = _pivot("nosdeputes:jean-dupont", "Jean Dupont")
    m = _derive_membre_entry(p)
    assert m["membre_id"] == "nosdeputes:jean-dupont"
    assert m["nom"] == "Jean Dupont"


def test_derive_membre_debut_from_electif():
    p = _pivot(mandats=[_mandat_electif("2022-06-22")])
    m = _derive_membre_entry(p)
    assert m["debut_dans_groupe"] == "2022-06-22"


def test_derive_membre_fin_none_if_active():
    p = _pivot(mandats=[_mandat_electif("2022-06-22")])
    m = _derive_membre_entry(p)
    assert m["fin_dans_groupe"] is None
    assert m["actif"] is True


def test_derive_membre_fin_set_if_closed():
    p = _pivot(mandats=[_mandat_electif("2017-06-21", "2022-06-21", actif=False)])
    m = _derive_membre_entry(p)
    assert m["fin_dans_groupe"] == "2022-06-21"
    assert m["actif"] is False


def test_derive_membre_multiple_mandats_earliest_debut():
    p = _pivot(mandats=[
        _mandat_electif("2022-06-22"),
        _mandat_electif("2017-06-21", "2022-06-21", actif=False),
    ])
    m = _derive_membre_entry(p)
    assert m["debut_dans_groupe"] == "2017-06-21"
    assert m["fin_dans_groupe"] is None  # le deuxième est actif
    assert m["actif"] is True


def test_derive_membre_no_mandats():
    p = _pivot(mandats=[])
    m = _derive_membre_entry(p)
    assert m["debut_dans_groupe"] is None
    assert m["fin_dans_groupe"] is None
    assert m["actif"] is False


# ---------------------------------------------------------------------------
# _build_vote_index
# ---------------------------------------------------------------------------

def test_build_vote_index_basic():
    p = _pivot(votes=[_vote("100", "pour"), _vote("200", "contre")])
    idx = _build_vote_index(p)
    assert "100" in idx
    assert "200" in idx
    assert idx["100"]["position"] == "pour"


def test_build_vote_index_normalizes_to_str():
    p = _pivot(votes=[{"date": "2024-01-01", "position": "pour", "numero_scrutin": 123, "texte": "X", "sort": "adopté"}])
    idx = _build_vote_index(p)
    assert "123" in idx


def test_build_vote_index_empty():
    p = _pivot(votes=[])
    assert _build_vote_index(p) == {}


# ---------------------------------------------------------------------------
# _compute_cohesion_votes
# ---------------------------------------------------------------------------

def _make_groupe_profils():
    """Deux membres, un scrutin commun."""
    p1 = _pivot("nosdeputes:alice", votes=[_vote("42", "pour")])
    p2 = _pivot("nosdeputes:bob", votes=[_vote("42", "pour")])
    return [p1, p2]


def test_cohesion_unanimite():
    profils = _make_groupe_profils()
    cohesion = _compute_cohesion_votes(profils)
    assert len(cohesion) == 1
    r = cohesion[0]
    assert r["numero_scrutin"] == "42"
    assert r["position_majoritaire"] == "pour"
    assert r["pour"] == 2
    assert r["contre"] == 0
    assert r["absents"] == 0
    assert r["taux_coherence"] == 1.0
    assert r["taux_participation"] == 1.0


def test_cohesion_partielle():
    p1 = _pivot("nosdeputes:alice", votes=[_vote("42", "pour")])
    p2 = _pivot("nosdeputes:bob", votes=[_vote("42", "contre")])
    p3 = _pivot("nosdeputes:charlie", votes=[_vote("42", "pour")])
    cohesion = _compute_cohesion_votes([p1, p2, p3])
    r = cohesion[0]
    assert r["position_majoritaire"] == "pour"
    assert r["pour"] == 2
    assert r["contre"] == 1
    # 2 alignés sur 3 éligibles
    assert abs(r["taux_coherence"] - 2 / 3) < 1e-4


def test_cohesion_absent_implicite():
    """Un membre n'a aucun vote pour le scrutin → absent."""
    p1 = _pivot("nosdeputes:alice", votes=[_vote("42", "pour")])
    p2 = _pivot("nosdeputes:bob", votes=[])  # n'a pas voté
    cohesion = _compute_cohesion_votes([p1, p2])
    r = cohesion[0]
    assert r["absents"] == 1
    assert r["membres_eligibles"] == 2
    assert abs(r["taux_participation"] - 0.5) < 1e-4


def test_cohesion_quorum_atteint():
    profils = _make_groupe_profils()
    cohesion = _compute_cohesion_votes(profils, seuil_quorum=0.5)
    assert cohesion[0]["quorum_atteint"] is True


def test_cohesion_quorum_non_atteint():
    p1 = _pivot("nosdeputes:alice", votes=[_vote("42", "pour")])
    p2 = _pivot("nosdeputes:bob", votes=[])
    # 50 % de participation, seuil à 0.6 → quorum non atteint
    cohesion = _compute_cohesion_votes([p1, p2], seuil_quorum=0.6)
    assert cohesion[0]["quorum_atteint"] is False


def test_cohesion_trie_par_date_desc():
    p1 = _pivot("nosdeputes:alice", votes=[
        _vote("10", "pour", date="2023-01-10"),
        _vote("20", "contre", date="2024-06-01"),
    ])
    cohesion = _compute_cohesion_votes([p1])
    dates = [r["date"] for r in cohesion]
    assert dates == sorted(dates, reverse=True)


def test_cohesion_membre_non_eligible_exclu():
    """Un membre dont le mandat est terminé avant le vote ne compte pas."""
    p1 = _pivot(
        "nosdeputes:alice",
        mandats=[_mandat_electif("2022-06-22")],
        votes=[_vote("42", "pour", date="2024-01-15")],
    )
    p2 = _pivot(
        "nosdeputes:ancien",
        mandats=[_mandat_electif("2017-06-21", "2022-06-21", actif=False)],
        votes=[_vote("42", "contre", date="2024-01-15")],
    )
    cohesion = _compute_cohesion_votes([p1, p2])
    r = cohesion[0]
    # bob (mandat terminé en 2022) ne devrait pas être éligible au scrutin de 2024
    assert r["membres_eligibles"] == 1
    assert r["pour"] == 1
    assert r["contre"] == 0


def test_cohesion_vide_si_aucun_scrutin():
    p1 = _pivot(votes=[])
    p2 = _pivot(votes=[])
    assert _compute_cohesion_votes([p1, p2]) == []


def test_cohesion_plusieurs_scrutins():
    p1 = _pivot("nosdeputes:alice", votes=[
        _vote("10", "pour"),
        _vote("11", "contre"),
    ])
    cohesion = _compute_cohesion_votes([p1])
    nums = {r["numero_scrutin"] for r in cohesion}
    assert nums == {"10", "11"}


def test_cohesion_position_majoritaire_none_si_aucun_vote_exprime():
    """Scrutin où tous les membres ont non_votant → pas de position majoritaire."""
    p1 = _pivot(votes=[{"date": "2024-01-01", "texte": "X", "position": "non_votant", "numero_scrutin": "99", "sort": None, "groupe_au_moment_du_vote": None, "source_url": None}])
    cohesion = _compute_cohesion_votes([p1])
    assert cohesion[0]["position_majoritaire"] is None


def test_cohesion_taux_coherence_hors_absents():
    p1 = _pivot("nosdeputes:alice", votes=[_vote("42", "pour")])
    p2 = _pivot("nosdeputes:bob", votes=[_vote("42", "pour")])
    p3 = _pivot("nosdeputes:charlie", votes=[])  # absent
    cohesion = _compute_cohesion_votes([p1, p2, p3])
    r = cohesion[0]
    assert r["taux_coherence_hors_absents"] == 1.0  # 2/2 parmi ceux qui ont voté
    assert abs(r["taux_coherence"] - 2 / 3) < 1e-4  # 2/3 globalement


# ---------------------------------------------------------------------------
# _aggregate_tags_thematiques
# ---------------------------------------------------------------------------

def test_tags_agrege_compte_membres():
    p1 = _pivot(tags=["budget", "fiscalité"])
    p2 = _pivot(tags=["budget", "santé"])
    tags, _ = _aggregate_tags_thematiques([p1, p2])
    budget_entry = next(t for t in tags if t["tag"] == "budget")
    assert budget_entry["nb_membres_porteurs"] == 2
    assert budget_entry["poids_relatif"] == 1.0


def test_tags_agrege_deduplication_par_membre():
    """Un tag répété dans le profil d'un membre ne compte qu'une fois."""
    p1 = _pivot(tags=["budget", "budget", "budget"])
    tags, _ = _aggregate_tags_thematiques([p1])
    budget_entry = next(t for t in tags if t["tag"] == "budget")
    assert budget_entry["nb_membres_porteurs"] == 1


def test_tags_trie_par_nombre_membres_desc():
    p1 = _pivot(tags=["budget", "santé", "défense"])
    p2 = _pivot(tags=["budget", "santé"])
    p3 = _pivot(tags=["budget"])
    tags, _ = _aggregate_tags_thematiques([p1, p2, p3])
    counts = [t["nb_membres_porteurs"] for t in tags]
    assert counts == sorted(counts, reverse=True)


def test_tags_fallback_sur_mots_cles_interventions():
    """Si tags_thematiques est vide, on utilise les mots-clés des interventions."""
    interventions = [{"mots_cles": ["immigration", "social"], "date": "2024-01-01"}]
    p1 = _pivot(tags=[], interventions=interventions)
    tags, source = _aggregate_tags_thematiques([p1])
    tag_names = {t["tag"] for t in tags}
    assert "immigration" in tag_names
    assert source == "mots_cles_interventions"


def test_tags_source_tags_thematiques():
    p1 = _pivot(tags=["budget"])
    _, source = _aggregate_tags_thematiques([p1])
    assert source == "tags_thematiques"


def test_tags_source_mixed():
    p1 = _pivot(tags=["budget"])
    p2 = _pivot(tags=[], interventions=[{"mots_cles": ["santé"], "date": "2024-01-01"}])
    _, source = _aggregate_tags_thematiques([p1, p2])
    assert source == "mixed"


def test_tags_vide_si_aucun_tag():
    p1 = _pivot(tags=[], interventions=[])
    tags, source = _aggregate_tags_thematiques([p1])
    assert tags == []
    assert source is None


def test_tags_poids_relatif():
    p1 = _pivot(tags=["budget"])
    p2 = _pivot(tags=[])
    tags, _ = _aggregate_tags_thematiques([p1, p2])
    budget_entry = next(t for t in tags if t["tag"] == "budget")
    assert budget_entry["poids_relatif"] == 0.5  # 1 membre sur 2


# ---------------------------------------------------------------------------
# _is_pivot_v1
# ---------------------------------------------------------------------------

def test_is_pivot_v1_true():
    p = _pivot()
    assert _is_pivot_v1(p) is True


def test_is_pivot_v1_false_raw_format():
    raw = {"slug": "jean-dupont", "chambre": "deputes"}
    assert _is_pivot_v1(raw) is False


def test_is_pivot_v1_false_missing_id():
    p = {"schema_version": "1", "nom": "X"}
    assert _is_pivot_v1(p) is False


# ---------------------------------------------------------------------------
# build_groupe_profile
# ---------------------------------------------------------------------------

def test_build_groupe_profile_valide():
    profils = [
        _pivot("nosdeputes:alice", votes=[_vote("42", "pour")]),
        _pivot("nosdeputes:bob", votes=[_vote("42", "pour")]),
    ]
    g = build_groupe_profile(
        groupe_id="AN:SOC",
        groupe_sigle="SOC",
        groupe_nom="Socialistes et apparentés",
        chambre="AN",
        legislature="16",
        profils=profils,
        licence_donnees="ODbL",
    )
    errors = validate_profil_groupe(g)
    assert errors == [], f"Erreurs de schéma inattendues : {errors}"


def test_build_groupe_profile_membres():
    profils = [
        _pivot("nosdeputes:alice", "Alice"),
        _pivot("nosdeputes:bob", "Bob"),
    ]
    g = build_groupe_profile("AN:SOC", "SOC", "Socialistes", "AN", "16", profils)
    assert len(g["membres"]) == 2
    ids = {m["membre_id"] for m in g["membres"]}
    assert ids == {"nosdeputes:alice", "nosdeputes:bob"}


def test_build_groupe_profile_effectif_actuel():
    profils = [
        _pivot("nosdeputes:alice", mandats=[_mandat_electif("2022-06-22")]),
        _pivot("nosdeputes:ancien", mandats=[_mandat_electif("2017-06-21", "2022-06-21", actif=False)]),
    ]
    g = build_groupe_profile("AN:SOC", "SOC", "Socialistes", "AN", "16", profils)
    assert g["effectif"]["actuel"] == 1  # seulement alice est active


def test_build_groupe_profile_periode():
    profils = [_pivot(mandats=[_mandat_electif("2022-06-22")])]
    g = build_groupe_profile("AN:SOC", "SOC", "Socialistes", "AN", "16", profils)
    assert g["periode"]["debut"] == "2022-06-22"
    assert g["periode"]["fin"] is None
    assert g["periode"]["actif"] is True


def test_build_groupe_profile_cohesion_votes():
    profils = [
        _pivot("nosdeputes:alice", votes=[_vote("42", "pour")]),
        _pivot("nosdeputes:bob", votes=[_vote("42", "contre")]),
    ]
    g = build_groupe_profile("AN:SOC", "SOC", "Socialistes", "AN", "16", profils)
    assert len(g["cohesion_votes"]) == 1
    assert g["cohesion_votes"][0]["numero_scrutin"] == "42"


def test_build_groupe_profile_profils_sources_dans_meta():
    profils = [
        _pivot("nosdeputes:alice"),
        _pivot("nosdeputes:bob"),
    ]
    g = build_groupe_profile("AN:SOC", "SOC", "Socialistes", "AN", "16", profils)
    assert "nosdeputes:alice" in g["meta"]["profils_sources"]
    assert "nosdeputes:bob" in g["meta"]["profils_sources"]


def test_build_groupe_profile_seuil_quorum_dans_meta():
    profils = [_pivot()]
    g = build_groupe_profile("AN:SOC", "SOC", "Socialistes", "AN", "16", profils, seuil_quorum=0.7)
    assert g["meta"]["seuil_quorum"] == 0.7


def test_build_groupe_profile_tags():
    profils = [
        _pivot(tags=["budget"]),
        _pivot(tags=["budget", "santé"]),
    ]
    g = build_groupe_profile("AN:SOC", "SOC", "Socialistes", "AN", "16", profils)
    tag_names = {t["tag"] for t in g["tags_thematiques_agreges"]}
    assert "budget" in tag_names
    assert "santé" in tag_names


def test_build_groupe_profile_sources_deduplication():
    """Les sources identiques entre profils ne doivent apparaître qu'une fois."""
    same_source = {
        "type": "nosdeputes",
        "url": "https://www.nosdeputes.fr/groupe/SOC",
        "synchro_le": "2026-07-29T10:00:00+0000",
    }
    profils = [
        {**_pivot("nosdeputes:alice"), "sources": [same_source]},
        {**_pivot("nosdeputes:bob"), "sources": [same_source]},
    ]
    g = build_groupe_profile("AN:SOC", "SOC", "Socialistes", "AN", "16", profils)
    # La même source ne doit apparaître qu'une fois
    urls = [s["url"] for s in g["sources"]]
    assert urls.count(same_source["url"]) == 1


def test_build_groupe_profile_warning_tags_fallback():
    """Un warning doit être émis si on utilise mots_cles en fallback."""
    profils = [
        _pivot(tags=[], interventions=[{"mots_cles": ["santé"], "date": "2024-01-01"}]),
    ]
    g = build_groupe_profile("AN:SOC", "SOC", "Socialistes", "AN", "16", profils)
    assert any("mots_cles_interventions" in w for w in g["meta"]["warnings"])


def test_build_groupe_profile_profils_vide():
    """Appel avec liste vide ne doit pas lever d'exception."""
    g = build_groupe_profile("AN:SOC", "SOC", "Socialistes", "AN", "16", [])
    assert g["membres"] == []
    assert g["cohesion_votes"] == []
    assert g["effectif"]["actuel"] == 0


# ---------------------------------------------------------------------------
# _aggregate_amendements
# ---------------------------------------------------------------------------

def _amendement(sort: str, deposant: str = "depute") -> dict:
    return {
        "texte_vise": "PLF 2025",
        "sort": sort,
        "base_juridique_irrecevabilite": "art. 40" if sort == "irrecevable" else None,
        "premier_signataire": "nosdeputes:jean-dupont",
        "co_signataires": [],
        "type_deposant": deposant,
        "date": "2024-10-15",
        "numero": "CL42",
        "source_url": None,
    }


def test_aggregate_amendements_compte_par_statut():
    p1 = _pivot("nosdeputes:alice", amendements=[
        _amendement("adopté"), _amendement("rejeté"), _amendement("irrecevable"),
    ])
    p2 = _pivot("nosdeputes:bob", amendements=[_amendement("retiré")])
    agg = _aggregate_amendements([p1, p2])
    assert agg["nb_amendements"] == 4
    assert agg["nb_adoptes"] == 1
    assert agg["nb_rejetes"] == 1
    assert agg["nb_irrecevables"] == 1
    assert agg["nb_retires_ou_tombes"] == 1


def test_aggregate_amendements_taux_adoption():
    p1 = _pivot(amendements=[_amendement("adopté"), _amendement("rejeté")])
    agg = _aggregate_amendements([p1])
    assert agg["taux_adoption"] == 0.5


def test_aggregate_amendements_sans_accent_est_reconnu():
    """'adopte' (sans accent) doit être reconnu comme 'adopté'."""
    p1 = _pivot(amendements=[_amendement("adopte")])
    agg = _aggregate_amendements([p1])
    assert agg["nb_adoptes"] == 1


def test_aggregate_amendements_taux_none_si_aucun():
    agg = _aggregate_amendements([_pivot(amendements=[])])
    assert agg["nb_amendements"] == 0
    assert agg["taux_adoption"] is None


def test_build_groupe_profile_inclut_amendements_agreges():
    profils = [_pivot(amendements=[_amendement("adopté"), _amendement("rejeté")])]
    g = build_groupe_profile("AN:SOC", "SOC", "Socialistes", "AN", "16", profils)
    assert g["amendements_agreges"]["nb_amendements"] == 2
    assert g["amendements_agreges"]["taux_adoption"] == 0.5
    assert validate_profil_groupe(g) == []


def test_aggregate_amendements_par_type_deposant_depute():
    p1 = _pivot(amendements=[
        _amendement("adopté", deposant="depute"), _amendement("rejeté", deposant="depute"),
    ])
    agg = _aggregate_amendements([p1])
    assert agg["par_type_deposant"]["depute"]["nb_amendements"] == 2
    assert agg["par_type_deposant"]["depute"]["taux_adoption"] == 0.5


def test_aggregate_amendements_par_type_deposant_ne_pollue_pas_depute():
    """Les amendements gouvernement/rapporteur (quasi tous adoptés) ne doivent pas
    gonfler le sous-total 'depute', utilisé comme comparateur d'un⋅e élu⋅e."""
    p1 = _pivot(amendements=[
        _amendement("rejeté", deposant="depute"),
        _amendement("adopté", deposant="gouvernement"),
        _amendement("adopté", deposant="commission_rapporteur"),
    ])
    agg = _aggregate_amendements([p1])
    assert agg["par_type_deposant"]["depute"]["nb_amendements"] == 1
    assert agg["par_type_deposant"]["depute"]["taux_adoption"] == 0.0
    assert agg["par_type_deposant"]["gouvernement"]["nb_amendements"] == 1
    assert agg["par_type_deposant"]["commission_rapporteur"]["nb_amendements"] == 1
    # Le total, lui, mélange bien tout (c'est pour ça qu'il ne doit pas servir
    # de comparateur direct).
    assert agg["nb_amendements"] == 3
    assert agg["taux_adoption"] == round(2 / 3, 4)


def test_aggregate_amendements_type_deposant_absent_est_inconnu():
    a = _amendement("adopté")
    del a["type_deposant"]
    agg = _aggregate_amendements([_pivot(amendements=[a])])
    assert agg["par_type_deposant"]["inconnu"]["nb_amendements"] == 1
    assert agg["par_type_deposant"]["depute"]["nb_amendements"] == 0


def test_build_groupe_profile_amendements_agreges_par_type_deposant_valide():
    profils = [_pivot(amendements=[
        _amendement("adopté", deposant="depute"), _amendement("adopté", deposant="gouvernement"),
    ])]
    g = build_groupe_profile("AN:SOC", "SOC", "Socialistes", "AN", "16", profils)
    assert g["amendements_agreges"]["par_type_deposant"]["depute"]["nb_amendements"] == 1
    assert g["amendements_agreges"]["par_type_deposant"]["gouvernement"]["nb_amendements"] == 1
    assert validate_profil_groupe(g) == []


# ---------------------------------------------------------------------------
# compute_ecarts_cohesion_internes (contrôle interne, hors schéma public)
# ---------------------------------------------------------------------------

def test_ecarts_cohesion_internes_membre_aligne_ecart_nul():
    p1 = _pivot("nosdeputes:alice", votes=[_vote("42", "pour")])
    p2 = _pivot("nosdeputes:bob", votes=[_vote("42", "pour")])
    cohesion = _compute_cohesion_votes([p1, p2])
    ecarts = compute_ecarts_cohesion_internes([p1, p2], cohesion)
    for e in ecarts:
        assert e["taux_participation_individuel"] == 1.0
        assert e["taux_coherence_individuel"] == 1.0
        assert e["ecart_participation_vs_groupe"] == 0.0
        assert e["ecart_coherence_vs_groupe"] == 0.0


def test_ecarts_cohesion_internes_membre_moins_coherent():
    p1 = _pivot("nosdeputes:alice", votes=[_vote("42", "pour")])
    p2 = _pivot("nosdeputes:bob", votes=[_vote("42", "contre")])
    p3 = _pivot("nosdeputes:charlie", votes=[_vote("42", "pour")])
    cohesion = _compute_cohesion_votes([p1, p2, p3])
    ecarts = compute_ecarts_cohesion_internes([p1, p2, p3], cohesion)
    bob = next(e for e in ecarts if e["membre_id"] == "nosdeputes:bob")
    assert bob["taux_coherence_individuel"] == 0.0
    assert bob["ecart_coherence_vs_groupe"] < 0


def test_ecarts_cohesion_internes_vide_si_pas_de_cohesion():
    assert compute_ecarts_cohesion_internes([_pivot()], []) == []


def test_ecarts_cohesion_internes_absent_du_profil_groupe_public():
    """Champ de contrôle interne : ne doit jamais apparaître dans le profil public."""
    profils = [_pivot("nosdeputes:alice", votes=[_vote("42", "pour")])]
    g = build_groupe_profile("AN:SOC", "SOC", "Socialistes", "AN", "16", profils)
    assert "ecarts_cohesion_internes" not in g
    assert "compute_ecarts_cohesion_internes" not in str(g)


# ---------------------------------------------------------------------------
# CLI --from-roster (composition réelle du groupe via group_roster.py)
# ---------------------------------------------------------------------------

def test_main_from_roster_builds_group_and_reports_couverture(tmp_path, monkeypatch):
    (tmp_path / "alice.pivot.json").write_text(json.dumps(_pivot("nosdeputes:alice")), encoding="utf-8")
    # "bob" fait partie du roster mais n'a aucun pivot local dans tmp_path.

    def fake_fetch_group_roster(chambre, groupe_sigle, legislature=None, senat_periode_debut=None):
        assert chambre == "deputes"
        assert groupe_sigle == "LR"
        assert legislature == "16"
        return [
            {"slug": "alice", "nom": "Alice", "groupe_sigle": "LR", "mandat_debut": "2022-06-22", "mandat_fin": None, "actif": True},
            {"slug": "bob", "nom": "Bob", "groupe_sigle": "LR", "mandat_debut": "2022-06-22", "mandat_fin": None, "actif": True},
        ]

    monkeypatch.setattr("group_roster.fetch_group_roster", fake_fetch_group_roster)

    out_path = tmp_path / "out.json"
    rc = group_profile_main([
        "--from-roster", "--roster-chambre", "deputes",
        "--groupe-id", "AN:LR", "--groupe-sigle", "LR", "--groupe-nom", "Les Républicains",
        "--chambre", "AN", "--legislature", "16",
        "--profiles-dir", str(tmp_path),
        "--out", str(out_path),
    ])

    assert rc == 0
    profil_groupe = json.loads(out_path.read_text(encoding="utf-8"))
    assert profil_groupe["meta"]["couverture_roster"] == {"roster_total": 2, "profils_disponibles": 1}
    assert len(profil_groupe["membres"]) == 1
    assert validate_profil_groupe(profil_groupe) == []


def test_main_from_roster_missing_roster_chambre_returns_error(capsys):
    rc = group_profile_main([
        "--from-roster",
        "--groupe-id", "AN:LR", "--groupe-sigle", "LR", "--groupe-nom", "Les Républicains",
    ])
    assert rc == 1
    assert "--roster-chambre" in capsys.readouterr().err


def test_main_from_roster_merge_existing_recupere_membre_absent_du_roster(tmp_path, monkeypatch):
    """--merge-existing : un membre présent dans --out lors d'une exécution précédente
    mais absent du roster récupéré cette fois-ci (échec partiel de récupération) doit
    être réintégré, avec un avertissement explicite dans meta.warnings."""
    (tmp_path / "alice.pivot.json").write_text(json.dumps(_pivot("nosdeputes:alice")), encoding="utf-8")
    (tmp_path / "bob.pivot.json").write_text(json.dumps(_pivot("nosdeputes:bob")), encoding="utf-8")

    def fake_fetch_group_roster_complet(chambre, groupe_sigle, legislature=None, senat_periode_debut=None):
        return [
            {"slug": "alice", "nom": "Alice", "groupe_sigle": "LR", "mandat_debut": "2022-06-22", "mandat_fin": None, "actif": True},
            {"slug": "bob", "nom": "Bob", "groupe_sigle": "LR", "mandat_debut": "2022-06-22", "mandat_fin": None, "actif": True},
        ]

    out_path = tmp_path / "out.json"
    monkeypatch.setattr("group_roster.fetch_group_roster", fake_fetch_group_roster_complet)
    rc = group_profile_main([
        "--from-roster", "--roster-chambre", "deputes",
        "--groupe-id", "AN:LR", "--groupe-sigle", "LR", "--groupe-nom", "Les Républicains",
        "--chambre", "AN", "--legislature", "16",
        "--profiles-dir", str(tmp_path),
        "--out", str(out_path),
    ])
    assert rc == 0
    assert len(json.loads(out_path.read_text(encoding="utf-8"))["membres"]) == 2

    # Exécution suivante : le roster live ne renvoie plus que "bob" (échec partiel simulé).
    def fake_fetch_group_roster_partiel(chambre, groupe_sigle, legislature=None, senat_periode_debut=None):
        return [
            {"slug": "bob", "nom": "Bob", "groupe_sigle": "LR", "mandat_debut": "2022-06-22", "mandat_fin": None, "actif": True},
        ]

    monkeypatch.setattr("group_roster.fetch_group_roster", fake_fetch_group_roster_partiel)
    rc = group_profile_main([
        "--from-roster", "--roster-chambre", "deputes",
        "--groupe-id", "AN:LR", "--groupe-sigle", "LR", "--groupe-nom", "Les Républicains",
        "--chambre", "AN", "--legislature", "16",
        "--profiles-dir", str(tmp_path),
        "--out", str(out_path),
        "--merge-existing",
    ])
    assert rc == 0
    profil_groupe = json.loads(out_path.read_text(encoding="utf-8"))
    membres_ids = {m["membre_id"] for m in profil_groupe["membres"]}
    assert "nosdeputes:alice" in membres_ids
    assert "nosdeputes:bob" in membres_ids
    assert any("fusion_avec_existant" in w and "alice" in w for w in profil_groupe["meta"]["warnings"])


def test_main_from_roster_sans_merge_existing_perd_membre_absent_du_roster(tmp_path, monkeypatch):
    """Sans --merge-existing (comportement par défaut), --out écrase entièrement :
    un membre absent du roster récupéré cette fois-ci disparaît du fichier de sortie."""
    (tmp_path / "alice.pivot.json").write_text(json.dumps(_pivot("nosdeputes:alice")), encoding="utf-8")
    (tmp_path / "bob.pivot.json").write_text(json.dumps(_pivot("nosdeputes:bob")), encoding="utf-8")

    def fake_fetch_group_roster_complet(chambre, groupe_sigle, legislature=None, senat_periode_debut=None):
        return [
            {"slug": "alice", "nom": "Alice", "groupe_sigle": "LR", "mandat_debut": "2022-06-22", "mandat_fin": None, "actif": True},
            {"slug": "bob", "nom": "Bob", "groupe_sigle": "LR", "mandat_debut": "2022-06-22", "mandat_fin": None, "actif": True},
        ]

    out_path = tmp_path / "out.json"
    monkeypatch.setattr("group_roster.fetch_group_roster", fake_fetch_group_roster_complet)
    group_profile_main([
        "--from-roster", "--roster-chambre", "deputes",
        "--groupe-id", "AN:LR", "--groupe-sigle", "LR", "--groupe-nom", "Les Républicains",
        "--chambre", "AN", "--legislature", "16",
        "--profiles-dir", str(tmp_path),
        "--out", str(out_path),
    ])

    def fake_fetch_group_roster_partiel(chambre, groupe_sigle, legislature=None, senat_periode_debut=None):
        return [
            {"slug": "bob", "nom": "Bob", "groupe_sigle": "LR", "mandat_debut": "2022-06-22", "mandat_fin": None, "actif": True},
        ]

    monkeypatch.setattr("group_roster.fetch_group_roster", fake_fetch_group_roster_partiel)
    group_profile_main([
        "--from-roster", "--roster-chambre", "deputes",
        "--groupe-id", "AN:LR", "--groupe-sigle", "LR", "--groupe-nom", "Les Républicains",
        "--chambre", "AN", "--legislature", "16",
        "--profiles-dir", str(tmp_path),
        "--out", str(out_path),
    ])
    profil_groupe = json.loads(out_path.read_text(encoding="utf-8"))
    membres_ids = {m["membre_id"] for m in profil_groupe["membres"]}
    assert membres_ids == {"nosdeputes:bob"}


