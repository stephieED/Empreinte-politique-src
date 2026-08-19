import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import generate_all_profiles
from generate_all_profiles import (
    _parse_shard,
    _select_candidats,
    _select_shard,
    _select_existants,
    _select_candidats_couverture,
    load_candidats,
    process_candidat,
)


def _fake_raw_profile(slug: str, chambre: str = "deputes") -> dict:
    return {
        "slug": slug,
        "chambre": chambre,
        "source": f"https://www.nosdeputes.fr/{slug}",
        "identite": {
            "nom_complet": slug.title(),
            "groupe_sigle": "LR",
            "groupe_nom": "Les Républicains",
            "profession": None,
            "date_naissance": None,
            "num_circo": None,
            "nb_mandats": None,
            "url_an_ou_senat": None,
        },
        "mandats": [],
        "votes": [],
        "votes_source": None,
        "dossiers_legislatifs": [],
        "interventions": [],
        "meta": {
            "genere_le": "2026-08-12T00:00:00+0000",
            "licence_donnees": "ODbL",
            "warnings": [],
        },
    }


def _make_args(**overrides) -> argparse.Namespace:
    base = dict(
        source="all",
        pivot_only=False,
        skip_existing=False,
        max_pages=1,
        skip_interventions=True,
        skip_dossiers_legislatifs=True,
        skip_ue=True,
        pivot=True,
        no_merge=False,
        enrich_parltrack=False,
    )
    base.update(overrides)
    return argparse.Namespace(**base)


# ---------------------------------------------------------------------------
# load_candidats : fichier --candidats alternatif
# ---------------------------------------------------------------------------

def test_load_candidats_alternate_file(tmp_path):
    candidats_path = tmp_path / "roster_candidats.json"
    candidats_path.write_text(
        json.dumps({"candidats": [{"nom": "Alice", "slug": "alice", "statut": "roster_groupe"}]}),
        encoding="utf-8",
    )

    candidats = load_candidats(str(candidats_path))

    assert candidats == [{"nom": "Alice", "slug": "alice", "statut": "roster_groupe"}]


def test_load_candidats_missing_key_returns_empty_list(tmp_path):
    candidats_path = tmp_path / "empty.json"
    candidats_path.write_text(json.dumps({}), encoding="utf-8")

    assert load_candidats(str(candidats_path)) == []


# ---------------------------------------------------------------------------
# _select_candidats : --limit / --sample (déploiement progressif)
# ---------------------------------------------------------------------------

def test_select_candidats_no_filter_returns_all():
    candidats = [{"slug": "a"}, {"slug": "b"}]
    assert _select_candidats(candidats) == candidats


def test_select_candidats_limit_takes_first_n_in_order():
    candidats = [{"slug": f"c{i}"} for i in range(5)]
    assert _select_candidats(candidats, limit=2) == candidats[:2]


def test_select_candidats_limit_larger_than_list_returns_all():
    candidats = [{"slug": "a"}, {"slug": "b"}]
    assert _select_candidats(candidats, limit=10) == candidats


def test_select_candidats_sample_returns_subset_of_requested_size():
    candidats = [{"slug": f"c{i}"} for i in range(10)]
    result = _select_candidats(candidats, sample=3)
    assert len(result) == 3
    assert all(c in candidats for c in result)
    # pas de doublon
    assert len({c["slug"] for c in result}) == 3


def test_select_candidats_sample_larger_than_list_returns_all():
    candidats = [{"slug": "a"}, {"slug": "b"}]
    result = _select_candidats(candidats, sample=10)
    assert len(result) == 2
    assert {c["slug"] for c in result} == {"a", "b"}


def test_cli_limit_and_sample_are_mutually_exclusive(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["generate_all_profiles.py", "--limit", "1", "--sample", "1"])
    with pytest.raises(SystemExit):
        generate_all_profiles.main()


# ---------------------------------------------------------------------------
# _select_candidats_couverture : sélection progressive + rafraîchissement
# pour --limit + --skip-existing (#224)
# ---------------------------------------------------------------------------

_REF_DATE = datetime(2026, 8, 12, tzinfo=timezone.utc)


def _fake_pivot(slug: str, jours_anciennete: int) -> dict:
    synchro = _REF_DATE - timedelta(days=jours_anciennete)
    return {
        "id": f"nosdeputes:{slug}",
        "sources": [{"type": "nosdeputes", "url": f"https://x/{slug}", "synchro_le": synchro.isoformat()}],
    }


def _write_pivot(pivot_dir: Path, slug: str, jours_anciennete: int) -> None:
    (pivot_dir / f"{slug}.pivot.json").write_text(
        json.dumps(_fake_pivot(slug, jours_anciennete)), encoding="utf-8"
    )


def test_select_candidats_couverture_progressive_no_pivots_takes_first_n(tmp_path):
    candidats = [{"slug": f"c{i}"} for i in range(30)]
    selection, refresh = _select_candidats_couverture(
        candidats, tmp_path, limit=10, staleness_days=30, reference_date=_REF_DATE
    )
    assert [c["slug"] for c in selection] == [f"c{i}" for i in range(10)]
    assert refresh == set()


def test_select_candidats_couverture_progresses_across_simulated_runs(tmp_path):
    candidats = [{"slug": f"c{i}"} for i in range(30)]

    # Run 1 : rien n'est couvert -> les 10 premiers.
    run1, _ = _select_candidats_couverture(
        candidats, tmp_path, limit=10, staleness_days=30, reference_date=_REF_DATE
    )
    assert [c["slug"] for c in run1] == [f"c{i}" for i in range(10)]

    # Les 10 premiers sont désormais couverts et frais (pas de péremption).
    for c in run1:
        _write_pivot(tmp_path, c["slug"], jours_anciennete=1)

    # Run 2 : sans correctif, --limit reprendrait les mêmes 10 premiers.
    run2, refresh2 = _select_candidats_couverture(
        candidats, tmp_path, limit=10, staleness_days=30, reference_date=_REF_DATE
    )
    assert [c["slug"] for c in run2] == [f"c{i}" for i in range(10, 20)]
    assert refresh2 == set()


def test_select_candidats_couverture_prioritizes_non_couverts_then_fills_with_perimes(tmp_path):
    # 3 non-couverts, 2 couverts périmés -> limit 4 doit prendre les 3
    # non-couverts + 1 périmé (budget restant = 1).
    candidats = [{"slug": "new1"}, {"slug": "new2"}, {"slug": "new3"}, {"slug": "old1"}, {"slug": "old2"}]
    _write_pivot(tmp_path, "old1", jours_anciennete=60)
    _write_pivot(tmp_path, "old2", jours_anciennete=90)

    selection, refresh = _select_candidats_couverture(
        candidats, tmp_path, limit=4, staleness_days=30, reference_date=_REF_DATE
    )

    slugs = [c["slug"] for c in selection]
    assert slugs[:3] == ["new1", "new2", "new3"]
    assert len(slugs) == 4
    assert slugs[3] in {"old1", "old2"}
    assert refresh == {slugs[3]}


def test_select_candidats_couverture_refreshes_stale_covered_profile(tmp_path):
    candidats = [{"slug": "old1"}]
    _write_pivot(tmp_path, "old1", jours_anciennete=60)

    selection, refresh = _select_candidats_couverture(
        candidats, tmp_path, limit=5, staleness_days=30, reference_date=_REF_DATE
    )

    assert [c["slug"] for c in selection] == ["old1"]
    assert refresh == {"old1"}


def test_select_candidats_couverture_does_not_reselect_fresh_covered_profile(tmp_path):
    # Non-régression : un profil couvert et frais n'est ni resélectionné, ni
    # compté dans le budget de conquête, même si du budget --limit reste.
    candidats = [{"slug": "fresh1"}]
    _write_pivot(tmp_path, "fresh1", jours_anciennete=5)

    selection, refresh = _select_candidats_couverture(
        candidats, tmp_path, limit=5, staleness_days=30, reference_date=_REF_DATE
    )

    assert selection == []
    assert refresh == set()


def test_select_candidats_couverture_budget_exhausted_by_non_couverts_ignores_perimes(tmp_path):
    candidats = [{"slug": "new1"}, {"slug": "new2"}, {"slug": "old1"}]
    _write_pivot(tmp_path, "old1", jours_anciennete=90)

    selection, refresh = _select_candidats_couverture(
        candidats, tmp_path, limit=2, staleness_days=30, reference_date=_REF_DATE
    )

    assert [c["slug"] for c in selection] == ["new1", "new2"]
    assert refresh == set()


# ---------------------------------------------------------------------------
# process_candidat : propagation de meta.provenance selon candidat["statut"]
# ---------------------------------------------------------------------------

def test_process_candidat_roster_groupe_sets_provenance(tmp_path, monkeypatch):
    monkeypatch.setattr(generate_all_profiles, "build_profile", lambda *a, **k: _fake_raw_profile("alice"))
    monkeypatch.setattr(generate_all_profiles.time, "sleep", lambda *_: None)

    out_dir = tmp_path / "profiles"
    pivot_dir = tmp_path / "pivots"
    out_dir.mkdir()
    pivot_dir.mkdir()

    candidat = {"nom": "Alice", "slug": "alice", "parti": None, "statut": "roster_groupe"}
    resultat = process_candidat(candidat, _make_args(), out_dir, pivot_dir)

    assert resultat["statut"] == "ok"
    pivot = json.loads((pivot_dir / "alice.pivot.json").read_text(encoding="utf-8"))
    assert pivot["meta"]["provenance"] == "roster_groupe"
    assert pivot["parti"] is None


def test_process_candidat_default_statut_sets_candidat_declare_provenance(tmp_path, monkeypatch):
    monkeypatch.setattr(generate_all_profiles, "build_profile", lambda *a, **k: _fake_raw_profile("bob"))
    monkeypatch.setattr(generate_all_profiles.time, "sleep", lambda *_: None)

    out_dir = tmp_path / "profiles"
    pivot_dir = tmp_path / "pivots"
    out_dir.mkdir()
    pivot_dir.mkdir()

    # Candidat éditorial classique (raw_data/candidats.json) : pas de champ "statut".
    candidat = {"nom": "Bob", "slug": "bob", "parti": "Parti Test"}
    resultat = process_candidat(candidat, _make_args(), out_dir, pivot_dir)

    assert resultat["statut"] == "ok"
    pivot = json.loads((pivot_dir / "bob.pivot.json").read_text(encoding="utf-8"))
    assert pivot["meta"]["provenance"] == "candidat_declare"
    assert pivot["parti"] == "Parti Test"


# ---------------------------------------------------------------------------
# #433 : profils brut et pivot écrits en JSON compact
# ---------------------------------------------------------------------------

def test_process_candidat_ecrit_brut_et_pivot_en_json_compact(tmp_path, monkeypatch):
    # 35 % du volume des profils n'était que de l'indentation (#429/#433). Le
    # test porte sur le résultat sur disque, pas sur l'appel : c'est le nombre
    # de lignes du fichier qui matérialise le gain.
    monkeypatch.setattr(generate_all_profiles, "build_profile", lambda *a, **k: _fake_raw_profile("diane"))
    monkeypatch.setattr(generate_all_profiles.time, "sleep", lambda *_: None)

    out_dir = tmp_path / "profiles"
    pivot_dir = tmp_path / "pivots"
    out_dir.mkdir()
    pivot_dir.mkdir()

    candidat = {"nom": "Diane", "slug": "diane", "parti": None, "statut": "roster_groupe"}
    assert process_candidat(candidat, _make_args(), out_dir, pivot_dir)["statut"] == "ok"

    for chemin in (out_dir / "diane.json", pivot_dir / "diane.pivot.json"):
        contenu = chemin.read_text(encoding="utf-8")
        assert len(contenu.splitlines()) == 1, chemin
        assert '": ' not in contenu, chemin
        # Relecture sémantique : le format change, la donnée non.
        assert isinstance(json.loads(contenu), dict)

    assert json.loads((pivot_dir / "diane.pivot.json").read_text(encoding="utf-8"))["nom"] == "Diane"


def test_process_candidat_fusionne_un_profil_existant_ecrit_en_indente(tmp_path, monkeypatch):
    # Les profils déjà commités sont indentés : la première régénération après
    # #433 doit les relire normalement, fusionner, puis réécrire compact.
    monkeypatch.setattr(generate_all_profiles, "build_profile", lambda *a, **k: _fake_raw_profile("elise"))
    monkeypatch.setattr(generate_all_profiles.time, "sleep", lambda *_: None)

    out_dir = tmp_path / "profiles"
    pivot_dir = tmp_path / "pivots"
    out_dir.mkdir()
    pivot_dir.mkdir()

    ancien = _fake_raw_profile("elise")
    ancien["votes"] = [{"uid": "VTANR5L17V1", "position": "pour"}]
    (out_dir / "elise.json").write_text(
        json.dumps(ancien, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    candidat = {"nom": "Elise", "slug": "elise", "parti": None, "statut": "roster_groupe"}
    assert process_candidat(candidat, _make_args(), out_dir, pivot_dir)["statut"] == "ok"

    contenu = (out_dir / "elise.json").read_text(encoding="utf-8")
    assert len(contenu.splitlines()) == 1
    # Fusion additive préservée : le vote déjà collecté n'a pas disparu.
    assert json.loads(contenu)["votes"] == [{"uid": "VTANR5L17V1", "position": "pour"}]


# ---------------------------------------------------------------------------
# process_candidat : --skip-existing sur un candidat issu du roster
# ---------------------------------------------------------------------------

def test_process_candidat_skip_existing_does_not_call_network(tmp_path, monkeypatch):
    call_count = {"n": 0}

    def fake_build_profile(*a, **k):
        call_count["n"] += 1
        return _fake_raw_profile("carla")

    monkeypatch.setattr(generate_all_profiles, "build_profile", fake_build_profile)

    out_dir = tmp_path / "profiles"
    pivot_dir = tmp_path / "pivots"
    out_dir.mkdir()
    pivot_dir.mkdir()
    (out_dir / "carla.json").write_text(json.dumps(_fake_raw_profile("carla")), encoding="utf-8")

    candidat = {"nom": "Carla", "slug": "carla", "statut": "roster_groupe"}
    resultat = process_candidat(candidat, _make_args(skip_existing=True), out_dir, pivot_dir)

    assert resultat["statut"] == "deja_present"
    assert call_count["n"] == 0


def test_process_candidat_refresh_slugs_bypasses_skip_existing(tmp_path, monkeypatch):
    # #224 : un slug listé dans refresh_slugs doit repasser par le fetch +
    # merge additif même si --skip-existing est actif et le profil existe déjà.
    call_count = {"n": 0}

    def fake_build_profile(*a, **k):
        call_count["n"] += 1
        return _fake_raw_profile("dave")

    monkeypatch.setattr(generate_all_profiles, "build_profile", fake_build_profile)
    monkeypatch.setattr(generate_all_profiles.time, "sleep", lambda *_: None)

    out_dir = tmp_path / "profiles"
    pivot_dir = tmp_path / "pivots"
    out_dir.mkdir()
    pivot_dir.mkdir()
    (out_dir / "dave.json").write_text(json.dumps(_fake_raw_profile("dave")), encoding="utf-8")

    candidat = {"nom": "Dave", "slug": "dave", "statut": "roster_groupe"}
    resultat = process_candidat(
        candidat, _make_args(skip_existing=True), out_dir, pivot_dir, refresh_slugs={"dave"}
    )

    assert resultat["statut"] == "ok"
    assert call_count["n"] == 1


# ---------------------------------------------------------------------------
# main() : intégration légère (réseau mocké) sur un lot roster + --resume
# ---------------------------------------------------------------------------

def _write_roster_candidats(path: Path, slugs: list[str]) -> None:
    path.write_text(
        json.dumps({
            "candidats": [
                {"nom": slug.title(), "slug": slug, "parti": None, "statut": "roster_groupe"}
                for slug in slugs
            ]
        }),
        encoding="utf-8",
    )


def test_integration_roster_batch_produces_pivots_with_provenance(tmp_path, monkeypatch):
    candidats_path = tmp_path / "roster_candidats.json"
    _write_roster_candidats(candidats_path, ["alice", "bob"])

    monkeypatch.setattr(
        generate_all_profiles, "build_profile", lambda chambre, slug, **k: _fake_raw_profile(slug, chambre)
    )
    monkeypatch.setattr(generate_all_profiles.time, "sleep", lambda *_: None)

    out_dir = tmp_path / "profiles"
    pivot_dir = tmp_path / "pivots"
    checkpoint_path = tmp_path / "checkpoint.json"

    monkeypatch.setattr(sys, "argv", [
        "generate_all_profiles.py",
        "--candidats", str(candidats_path),
        "--out-dir", str(out_dir),
        "--pivot-dir", str(pivot_dir),
        "--pivot", "--skip-ue", "--skip-interventions",
        # #432 : sans --scrutins, l'index s'écrirait dans le pivot_data/ du
        # dépôt — un test ne doit jamais salir l'arbre de travail.
        "--scrutins", str(tmp_path / "scrutins.json"),
        "--checkpoint-file", str(checkpoint_path),
        "--workers", "2",
    ])

    generate_all_profiles.main()

    for slug in ("alice", "bob"):
        pivot = json.loads((pivot_dir / f"{slug}.pivot.json").read_text(encoding="utf-8"))
        assert pivot["meta"]["provenance"] == "roster_groupe"


def test_resume_skips_already_processed_roster_candidats(tmp_path, monkeypatch):
    candidats_path = tmp_path / "roster_candidats.json"
    _write_roster_candidats(candidats_path, ["alice", "bob"])

    call_count = {"n": 0}

    def fake_build_profile(chambre, slug, **k):
        call_count["n"] += 1
        return _fake_raw_profile(slug, chambre)

    monkeypatch.setattr(generate_all_profiles, "build_profile", fake_build_profile)
    monkeypatch.setattr(generate_all_profiles.time, "sleep", lambda *_: None)

    out_dir = tmp_path / "profiles"
    pivot_dir = tmp_path / "pivots"
    checkpoint_path = tmp_path / "checkpoint.json"

    argv_base = [
        "generate_all_profiles.py",
        "--candidats", str(candidats_path),
        "--out-dir", str(out_dir),
        "--pivot-dir", str(pivot_dir),
        "--skip-ue", "--skip-interventions",
        "--checkpoint-file", str(checkpoint_path),
        "--workers", "2",
    ]

    monkeypatch.setattr(sys, "argv", argv_base)
    generate_all_profiles.main()
    assert call_count["n"] == 2

    # Deuxième run avec --resume : les deux candidats sont déjà "ok" dans le
    # checkpoint, donc ignorés avant même d'appeler build_profile — le
    # comportement de reprise est identique pour un lot roster-driven, sans
    # code spécifique (critère d'acceptation de non-régression).
    monkeypatch.setattr(sys, "argv", argv_base + ["--resume"])
    generate_all_profiles.main()
    assert call_count["n"] == 2

    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    assert {r["slug"] for r in checkpoint["resultats"]} == {"alice", "bob"}


def test_integration_progressive_selection_advances_across_two_runs(tmp_path, monkeypatch):
    """Critère d'acceptation #224 : un run avec --limit fixe fait progresser
    la couverture du roster à chaque exécution successive, sans intervention
    manuelle. Simule deux dispatches CI successifs (pas de --resume entre les
    deux, out-dir/pivot-dir "committés" comme raw_data/profiles + pivot_data/
    profiles le sont réellement entre deux runs de generate-data.yml)."""
    candidats_path = tmp_path / "roster_candidats.json"
    slugs = [f"m{i}" for i in range(6)]
    _write_roster_candidats(candidats_path, slugs)

    call_log: list[str] = []

    def fake_build_profile(chambre, slug, **k):
        call_log.append(slug)
        return _fake_raw_profile(slug, chambre)

    monkeypatch.setattr(generate_all_profiles, "build_profile", fake_build_profile)
    monkeypatch.setattr(generate_all_profiles.time, "sleep", lambda *_: None)

    out_dir = tmp_path / "profiles"
    pivot_dir = tmp_path / "pivots"

    argv_base = [
        "generate_all_profiles.py",
        "--candidats", str(candidats_path),
        "--out-dir", str(out_dir),
        "--pivot-dir", str(pivot_dir),
        "--pivot", "--skip-ue", "--skip-interventions",
        # #432 : sans --scrutins, l'index s'écrirait dans le pivot_data/ du
        # dépôt — un test ne doit jamais salir l'arbre de travail.
        "--scrutins", str(tmp_path / "scrutins.json"),
        "--no-checkpoint",
        "--workers", "2",
        "--limit", "2", "--skip-existing",
    ]

    # Run 1 : rien n'est couvert -> les 2 premiers (m0, m1).
    monkeypatch.setattr(sys, "argv", argv_base)
    generate_all_profiles.main()
    assert set(call_log) == {"m0", "m1"}

    # Run 2 : sans le correctif #224, --limit resélectionnerait m0/m1 (déjà
    # couverts) et --skip-existing les sauterait tous les deux -> plus aucun
    # candidat ne serait jamais traité. Avec le correctif, la sélection
    # avance à m2/m3.
    call_log.clear()
    monkeypatch.setattr(sys, "argv", argv_base)
    generate_all_profiles.main()
    assert set(call_log) == {"m2", "m3"}


# ---------------------------------------------------------------------------
# Partitionnement en shards (#394) — permet un run roster complet et borne la
# perte en cas de préemption runner.
# ---------------------------------------------------------------------------

def _membres(n: int) -> list[dict]:
    return [{"slug": f"m{i}"} for i in range(n)]


def test_select_shard_partitionne_sans_perte_ni_doublon():
    """Les N tranches doivent recouvrir exactement la liste : un membre perdu
    ne serait jamais collecté, un membre dupliqué serait extrait deux fois."""
    candidats = _membres(752)
    shards = [_select_shard(candidats, i, 8) for i in range(8)]

    reunis = [c["slug"] for s in shards for c in s]
    assert sorted(reunis) == sorted(c["slug"] for c in candidats)
    assert len(reunis) == len(set(reunis)), "aucun doublon entre shards"


def test_select_shard_tranches_equilibrees():
    """Découpage par modulo, pas par blocs contigus : le roster étant ordonné
    par groupe parlementaire, des blocs contigus donneraient des tranches très
    inégales en coût (un groupe de 190 membres contre un de 15)."""
    tailles = [len(_select_shard(_membres(752), i, 8)) for i in range(8)]
    assert tailles == [94] * 8


def test_select_shard_repartit_les_groupes_contigus():
    """Un découpage en blocs contigus passerait les assertions de taille
    ci-dessus tout en concentrant un groupe entier dans un seul shard.

    Le fichier roster réel est trié par groupe (7 blocs contigus, du plus
    gros au plus petit). Ce qui rend le coût prévisible, ce n'est pas que les
    tranches aient la même taille, c'est que chacune voie *tous* les groupes :
    un shard ne doit jamais hériter des 190 membres du plus gros groupe.
    """
    # Roster ordonné par groupe, tailles inégales comme dans la réalité.
    tailles_groupes = {"REN": 190, "RN": 140, "LFI": 120, "SOC": 100,
                       "LR": 80, "ECO": 60, "GDR": 62}
    candidats = [
        {"slug": f"{groupe}-{i}", "groupe": groupe}
        for groupe, taille in tailles_groupes.items()
        for i in range(taille)
    ]

    for index in range(8):
        groupes = Counter(c["groupe"] for c in _select_shard(candidats, index, 8))
        assert set(groupes) == set(tailles_groupes), (
            f"shard {index} ne voit pas tous les groupes : {sorted(groupes)}"
        )
        # Aucun groupe ne pèse plus que sa part attendue (+1 pour l'arrondi).
        for groupe, taille in tailles_groupes.items():
            assert groupes[groupe] <= taille // 8 + 1


def test_select_shard_est_deterministe():
    """Condition nécessaire pour que --skip-existing garde son sens d'un run à
    l'autre : un membre doit toujours retomber dans le même shard."""
    candidats = _membres(100)
    assert _select_shard(candidats, 3, 8) == _select_shard(candidats, 3, 8)


def test_select_shard_total_1_retourne_tout():
    """N=1 : comportement identique à l'absence de shardage — c'est ce que la
    CI utilise tant que roster_extraction_limit n'est pas à 0."""
    candidats = _membres(50)
    assert _select_shard(candidats, 0, 1) == candidats


def test_select_shard_plus_de_shards_que_de_membres():
    """Cas limite : certaines tranches sont vides, aucune ne doit lever."""
    shards = [_select_shard(_membres(3), i, 8) for i in range(8)]
    assert sum(len(s) for s in shards) == 3
    assert [len(s) for s in shards] == [1, 1, 1, 0, 0, 0, 0, 0]


@pytest.mark.parametrize("valeur", ["", "8", "0/0", "8/8", "-1/8", "a/b", "0/", "/8"])
def test_parse_shard_rejette_les_formes_invalides(valeur):
    """Un shard mal interprété traiterait silencieusement les mauvais
    candidats : toute forme douteuse doit lever, jamais être devinée."""
    with pytest.raises(ValueError):
        _parse_shard(valeur)


@pytest.mark.parametrize("valeur,attendu", [("0/8", (0, 8)), ("7/8", (7, 8)), (" 3 / 4 ", (3, 4)), ("0/1", (0, 1))])
def test_parse_shard_accepte_les_formes_valides(valeur, attendu):
    assert _parse_shard(valeur) == attendu


# ── --refresh-existing : propager une correction de fond à l'existant (#445) ──

def _c(slug):
    return {"nom": slug.replace("-", " ").title(), "slug": slug}


def test_select_existants_ne_retient_que_les_profils_deja_ecrits(tmp_path):
    (tmp_path / "alice-martin.json").write_text("{}", encoding="utf-8")
    (tmp_path / "carla-nunez.json").write_text("{}", encoding="utf-8")
    candidats = [_c("alice-martin"), _c("bob-durand"), _c("carla-nunez")]

    retenus = _select_existants(candidats, tmp_path)

    assert [c["slug"] for c in retenus] == ["alice-martin", "carla-nunez"]


def test_select_existants_ignore_la_position_dans_la_liste(tmp_path):
    """L'ordre de roster_candidats.json n'est pas stable : le fichier est
    régénéré. Une sélection par position (--limit) manquerait les couverts
    dispersés en fin de liste — mesuré : dernier couvert à l'index 93/94."""
    candidats = [_c(f"membre-{i}") for i in range(100)]
    (tmp_path / "membre-93.json").write_text("{}", encoding="utf-8")

    retenus = _select_existants(candidats, tmp_path)

    assert [c["slug"] for c in retenus] == ["membre-93"]


def test_select_existants_sans_aucun_profil_ne_retient_personne(tmp_path):
    assert _select_existants([_c("alice-martin")], tmp_path) == []


def test_refresh_existing_et_skip_existing_sont_refuses(monkeypatch, tmp_path):
    """Combinés, ils s'annulent : le premier ne retient que les profils
    existants, le second les saute tous. Un job tournerait alors sans jamais
    écrire un seul profil, sans erreur."""
    monkeypatch.setattr(sys, "argv", [
        "generate_all_profiles.py", "--refresh-existing", "--skip-existing",
        "--out-dir", str(tmp_path),
    ])
    with pytest.raises(SystemExit) as exc:
        generate_all_profiles.main()
    assert "s'annulent" in str(exc.value)


# ── --manifest-out : un artifact = la contribution d'un job (#450) ────────────
#
# Chaque job d'extraction publiait tout `raw_data/profiles/`, donc aussi la
# baseline committée récupérée par son checkout. La fusion additive réunissait
# ensuite version fraîche et version périmée du même profil, ce qui annulait
# `--no-merge` et gonflait le volume à chaque run (+107 000 amendements sur le
# run 32277443716). Le manifeste rétablit la propriété manquante : un job ne
# publie que ce qu'il a lui-même écrit.

def _manifest_lines(path: Path) -> list[str]:
    return [ligne for ligne in path.read_text(encoding="utf-8").splitlines() if ligne]


def _argv_manifest(candidats_path, out_dir, pivot_dir, checkpoint_path, manifest_path, *extra):
    return [
        "generate_all_profiles.py",
        "--candidats", str(candidats_path),
        "--out-dir", str(out_dir),
        "--pivot-dir", str(pivot_dir),
        "--checkpoint-file", str(checkpoint_path),
        "--manifest-out", str(manifest_path),
        # #432 : `--scrutins` a une valeur par défaut dans `pivot_data/` du
        # dépôt — un test qui l'omettrait y écrirait l'index.
        "--scrutins", str(Path(out_dir).parent / "scrutins.json"),
        "--skip-ue", "--skip-interventions",
        "--workers", "2",
        *extra,
    ]


def test_manifest_liste_exactement_les_profils_ecrits(tmp_path, monkeypatch):
    candidats_path = tmp_path / "roster_candidats.json"
    _write_roster_candidats(candidats_path, ["alice", "bob"])
    monkeypatch.setattr(
        generate_all_profiles, "build_profile", lambda chambre, slug, **k: _fake_raw_profile(slug, chambre)
    )
    monkeypatch.setattr(generate_all_profiles.time, "sleep", lambda *_: None)

    out_dir = tmp_path / "profiles"
    manifest_path = tmp_path / "manifest.txt"

    # Profil d'un autre job, déjà présent dans le répertoire de sortie : c'est
    # la baseline que le checkout dépose sur le runner. Elle ne doit pas être
    # publiée par ce job, qui ne l'a pas écrite.
    out_dir.mkdir()
    (out_dir / "carla.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(sys, "argv", _argv_manifest(
        candidats_path, out_dir, tmp_path / "pivots", tmp_path / "cp.json", manifest_path,
    ))
    generate_all_profiles.main()

    assert sorted(_manifest_lines(manifest_path)) == ["alice.json", "bob.json"]
    # Le fichier périmé est bien resté sur le disque : c'est la publication qui
    # l'exclut, pas une suppression.
    assert (out_dir / "carla.json").exists()


def test_manifest_exclut_les_profils_sautes_par_skip_existing(tmp_path, monkeypatch):
    """`--skip-existing` n'écrit rien pour un profil déjà couvert : le publier
    reviendrait à republier la version committée, périmée."""
    candidats_path = tmp_path / "roster_candidats.json"
    _write_roster_candidats(candidats_path, ["alice", "bob"])
    monkeypatch.setattr(
        generate_all_profiles, "build_profile", lambda chambre, slug, **k: _fake_raw_profile(slug, chambre)
    )
    monkeypatch.setattr(generate_all_profiles.time, "sleep", lambda *_: None)

    out_dir = tmp_path / "profiles"
    out_dir.mkdir()
    (out_dir / "alice.json").write_text("{}", encoding="utf-8")
    manifest_path = tmp_path / "manifest.txt"

    monkeypatch.setattr(sys, "argv", _argv_manifest(
        candidats_path, out_dir, tmp_path / "pivots", tmp_path / "cp.json", manifest_path,
        "--skip-existing",
    ))
    generate_all_profiles.main()

    assert _manifest_lines(manifest_path) == ["bob.json"]


def test_manifest_est_tronque_a_chaque_run(tmp_path, monkeypatch):
    """Le manifeste décrit UNE exécution, pas un répertoire : sans troncature,
    un second run sur le même runner republierait la tranche du premier."""
    candidats_path = tmp_path / "roster_candidats.json"
    _write_roster_candidats(candidats_path, ["alice", "bob"])
    monkeypatch.setattr(
        generate_all_profiles, "build_profile", lambda chambre, slug, **k: _fake_raw_profile(slug, chambre)
    )
    monkeypatch.setattr(generate_all_profiles.time, "sleep", lambda *_: None)

    manifest_path = tmp_path / "manifest.txt"
    manifest_path.write_text("profil-d-un-run-precedent.json\n", encoding="utf-8")

    monkeypatch.setattr(sys, "argv", _argv_manifest(
        candidats_path, tmp_path / "profiles", tmp_path / "pivots", tmp_path / "cp.json", manifest_path,
        "--only", "alice",
    ))
    generate_all_profiles.main()

    assert _manifest_lines(manifest_path) == ["alice.json"]


def test_manifest_est_ecrit_au_fil_de_l_eau_pas_en_fin_de_run(tmp_path, monkeypatch):
    """Un dump final serait perdu en cas de préemption du runner — cas courant
    ici (#228). Écrit au fil de l'eau, le manifeste laisse au contraire un
    préfixe VALIDE, décrivant exactement les profils déjà sur le disque : même
    principe que #443, ne jamais jeter un préfixe valide.

    Vérifié en observant le manifeste DEPUIS le traitement du second candidat :
    la ligne du premier doit déjà y être."""
    candidats_path = tmp_path / "roster_candidats.json"
    _write_roster_candidats(candidats_path, ["alice", "bob"])

    manifest_path = tmp_path / "manifest.txt"
    vu_pendant_bob = {}

    def build_en_observant(chambre, slug, **k):
        if slug == "bob":
            vu_pendant_bob["lignes"] = _manifest_lines(manifest_path)
        return _fake_raw_profile(slug, chambre)

    monkeypatch.setattr(generate_all_profiles, "build_profile", build_en_observant)
    monkeypatch.setattr(generate_all_profiles.time, "sleep", lambda *_: None)

    monkeypatch.setattr(sys, "argv", _argv_manifest(
        candidats_path, tmp_path / "profiles", tmp_path / "pivots", tmp_path / "cp.json", manifest_path,
        # Un seul worker : l'ordre de traitement est celui du fichier source,
        # donc alice est intégralement écrite avant que bob ne démarre.
        "--workers", "1",
    ))
    generate_all_profiles.main()

    assert vu_pendant_bob["lignes"] == ["alice.json"]
    assert sorted(_manifest_lines(manifest_path)) == ["alice.json", "bob.json"]


def test_manifest_omet_un_candidat_dont_l_extraction_n_a_rien_produit(tmp_path, monkeypatch):
    """Une extraction qui ne trouve aucune identité n'écrit pas de profil — mais
    le checkout a laissé une copie périmée au chemin attendu. Publier « le
    fichier de ce slug » plutôt que « ce que j'ai écrit » republierait cette
    copie."""
    candidats_path = tmp_path / "roster_candidats.json"
    _write_roster_candidats(candidats_path, ["alice", "bob"])

    def build_introuvable_pour_bob(chambre, slug, **k):
        return None if slug == "bob" else _fake_raw_profile(slug, chambre)

    monkeypatch.setattr(generate_all_profiles, "build_profile", build_introuvable_pour_bob)
    monkeypatch.setattr(generate_all_profiles.time, "sleep", lambda *_: None)

    out_dir = tmp_path / "profiles"
    out_dir.mkdir()
    (out_dir / "bob.json").write_text("{}", encoding="utf-8")
    manifest_path = tmp_path / "manifest.txt"

    monkeypatch.setattr(sys, "argv", _argv_manifest(
        candidats_path, out_dir, tmp_path / "pivots", tmp_path / "cp.json", manifest_path,
    ))
    generate_all_profiles.main()

    assert _manifest_lines(manifest_path) == ["alice.json"]


def test_manifest_vide_quand_le_job_n_ecrit_aucun_profil(tmp_path, monkeypatch):
    """Manifeste vide ≠ manifeste absent : l'étape de publication doit pouvoir
    distinguer « ce job n'a rien écrit » de « l'option n'a pas été passée »,
    et surtout ne jamais retomber sur `raw_data/profiles/` par défaut."""
    candidats_path = tmp_path / "roster_candidats.json"
    _write_roster_candidats(candidats_path, ["alice"])
    monkeypatch.setattr(generate_all_profiles, "build_profile", lambda *a, **k: None)
    monkeypatch.setattr(generate_all_profiles.time, "sleep", lambda *_: None)

    manifest_path = tmp_path / "manifest.txt"
    monkeypatch.setattr(sys, "argv", _argv_manifest(
        candidats_path, tmp_path / "profiles", tmp_path / "pivots", tmp_path / "cp.json", manifest_path,
    ))
    generate_all_profiles.main()

    assert manifest_path.exists()
    assert _manifest_lines(manifest_path) == []


def test_manifest_ignore_le_mode_pivot_only(tmp_path, monkeypatch):
    """`--pivot-only` n'écrit aucun profil brut : rien à publier côté raw."""
    candidats_path = tmp_path / "roster_candidats.json"
    _write_roster_candidats(candidats_path, ["alice"])
    monkeypatch.setattr(generate_all_profiles.time, "sleep", lambda *_: None)

    out_dir = tmp_path / "profiles"
    out_dir.mkdir()
    (out_dir / "alice.json").write_text(
        json.dumps(_fake_raw_profile("alice"), ensure_ascii=False), encoding="utf-8"
    )
    manifest_path = tmp_path / "manifest.txt"

    monkeypatch.setattr(sys, "argv", _argv_manifest(
        candidats_path, out_dir, tmp_path / "pivots", tmp_path / "cp.json", manifest_path,
        "--pivot-only",
    ))
    generate_all_profiles.main()

    assert _manifest_lines(manifest_path) == []


# ── Index des scrutins : ne jamais écrire hors de --scrutins (#432) ───────────

def test_index_des_scrutins_est_ecrit_dans_le_chemin_demande(tmp_path, monkeypatch):
    """`--scrutins` a une valeur par défaut qui pointe dans `pivot_data/` : un
    run avec des répertoires de sortie personnalisés (test, mesure hors dépôt)
    ne doit surtout pas écrire l'index dans le dépôt au passage."""
    candidats_path = tmp_path / "roster_candidats.json"
    _write_roster_candidats(candidats_path, ["alice"])
    monkeypatch.setattr(
        generate_all_profiles, "build_profile",
        lambda chambre, slug, **k: dict(_fake_raw_profile(slug, chambre), votes=[
            {"numero_scrutin": "1", "date": "2026-01-05", "legislature": "17", "position": "pour"},
        ]),
    )
    monkeypatch.setattr(generate_all_profiles.time, "sleep", lambda *_: None)

    index_path = tmp_path / "sous" / "dossier" / "scrutins.json"
    monkeypatch.setattr(sys, "argv", [
        "generate_all_profiles.py",
        "--candidats", str(candidats_path),
        "--out-dir", str(tmp_path / "profiles"),
        "--pivot-dir", str(tmp_path / "pivots"),
        "--checkpoint-file", str(tmp_path / "cp.json"),
        "--scrutins", str(index_path),
        "--pivot", "--skip-ue", "--skip-interventions",
    ])
    generate_all_profiles.main()

    assert index_path.exists(), "l'index doit être écrit là où on le demande"
    assert json.loads(index_path.read_text(encoding="utf-8"))["scrutins"][0]["id"] == "an:17:1"

    pivot = json.loads((tmp_path / "pivots" / "alice.pivot.json").read_text(encoding="utf-8"))
    assert pivot["votes"] == [{"scrutin_id": "an:17:1", "position": "pour"}]


def test_index_des_scrutins_n_est_pas_construit_sans_pivot(tmp_path, monkeypatch):
    """Sans `--pivot`, aucun profil pivot n'est écrit : reconstruire l'index
    coûterait une passe de corpus pour rien."""
    candidats_path = tmp_path / "roster_candidats.json"
    _write_roster_candidats(candidats_path, ["alice"])
    monkeypatch.setattr(
        generate_all_profiles, "build_profile", lambda chambre, slug, **k: _fake_raw_profile(slug, chambre)
    )
    monkeypatch.setattr(generate_all_profiles.time, "sleep", lambda *_: None)

    index_path = tmp_path / "scrutins.json"
    monkeypatch.setattr(sys, "argv", [
        "generate_all_profiles.py",
        "--candidats", str(candidats_path),
        "--out-dir", str(tmp_path / "profiles"),
        "--pivot-dir", str(tmp_path / "pivots"),
        "--checkpoint-file", str(tmp_path / "cp.json"),
        "--scrutins", str(index_path),
        "--skip-ue", "--skip-interventions",
    ])
    generate_all_profiles.main()

    assert not index_path.exists()
