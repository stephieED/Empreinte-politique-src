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
    build_groupe_profile,
    _is_pivot_v1,
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
