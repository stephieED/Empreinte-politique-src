"""Tests de non-régression pour la couverture amendements dans check_quality_gate.py
(issue #185 : une régression de collecte qui vide amendements[] sur tous les
candidats AN n'était détectée par aucune section du quality gate) et pour le
signal de fraîcheur des index de législature (issue #254, sous-issue 6/6 de
#248 : distinguer un index jamais construit d'un index présent mais périmé,
en s'appuyant sur `fraicheur.json` écrit par `_write_amendements_fraicheur`,
candidate_profile.py, issue #253)."""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from check_quality_gate import (
    _AMENDEMENTS_LEGISLATURES,
    _AMENDEMENTS_LEGISLATURES_FIGEES,
    _report_amendements_coverage,
    _report_amendements_freshness,
)


def _write_pivot(tmp_path: Path, slug: str, chambre: str, identite, amendements: list, warnings: list) -> None:
    profile = {
        "id": f"nd:{slug}",
        "nom": slug.replace("-", " ").title(),
        "chambre": chambre,
        "identite": identite,
        "mandats": [],
        "interventions": [],
        "votes": [],
        "textes_portes": [],
        "amendements": amendements,
        "tags_thematiques": [],
        "sources": [],
        "meta": {"warnings": warnings},
    }
    (tmp_path / f"{slug}.pivot.json").write_text(json.dumps(profile), encoding="utf-8")


def test_report_amendements_coverage_flags_global_regression_when_all_empty(tmp_path):
    """Plusieurs candidats AN avec identité mais amendements[] vide partout :
    doit déclencher un soft warning global (régression de collecte)."""
    _write_pivot(tmp_path, "jean-dupont", "AN", {"nom_complet": "Jean Dupont"}, amendements=[], warnings=[])
    _write_pivot(tmp_path, "marie-martin", "AN", {"nom_complet": "Marie Martin"}, amendements=[], warnings=[])

    soft, console, md = _report_amendements_coverage(tmp_path)

    assert len(soft) == 1
    assert "2" in soft[0]
    assert "⚠" in console
    assert "⚠️" in md


def test_report_amendements_coverage_no_warning_when_some_have_amendements(tmp_path):
    """Si au moins un candidat AN a des amendements collectés, pas de warning global."""
    _write_pivot(
        tmp_path,
        "jean-dupont",
        "AN",
        {"nom_complet": "Jean Dupont"},
        amendements=[{"sort": "adopté", "type_deposant": "depute"}],
        warnings=[],
    )
    _write_pivot(tmp_path, "marie-martin", "AN", {"nom_complet": "Marie Martin"}, amendements=[], warnings=[])

    soft, console, md = _report_amendements_coverage(tmp_path)

    assert len(soft) == 0
    assert "✓" in console


def test_report_amendements_coverage_flags_per_candidate_fetch_failure(tmp_path):
    """Un warning 'amendements indisponibles' dans meta.warnings doit être
    remonté individuellement, même si d'autres candidats ont bien des amendements."""
    _write_pivot(
        tmp_path,
        "jean-dupont",
        "AN",
        {"nom_complet": "Jean Dupont"},
        amendements=[],
        warnings=["amendements indisponibles : échec du téléchargement (boom)"],
    )
    _write_pivot(
        tmp_path,
        "marie-martin",
        "AN",
        {"nom_complet": "Marie Martin"},
        amendements=[{"sort": "adopté", "type_deposant": "depute"}],
        warnings=[],
    )

    soft, console, md = _report_amendements_coverage(tmp_path)

    assert any("jean-dupont" in w for w in soft)
    # Pas de régression globale puisque marie-martin a bien des amendements.
    assert not any("aucun candidat AN" in w for w in soft)


def test_report_amendements_coverage_ignores_candidates_without_identite(tmp_path):
    """Un candidat AN sans identité (non éligible à la collecte d'amendements
    officiels côté candidate_profile.py) ne doit pas être compté."""
    _write_pivot(tmp_path, "sans-identite", "AN", None, amendements=[], warnings=[])

    soft, console, md = _report_amendements_coverage(tmp_path)

    assert len(soft) == 0
    assert "0" in console


def test_report_amendements_coverage_ignores_non_an_candidates(tmp_path):
    """Les candidats non-AN (Sénat...) ne doivent pas être comptés dans la couverture."""
    _write_pivot(tmp_path, "senateur-x", "Senat", {"nom_complet": "Senateur X"}, amendements=[], warnings=[])

    soft, console, md = _report_amendements_coverage(tmp_path)

    assert len(soft) == 0


def test_report_amendements_coverage_empty_dir_returns_no_warning(tmp_path):
    """Aucun profil AN analysé : pas de faux positif sur régression globale."""
    soft, console, md = _report_amendements_coverage(tmp_path)
    assert len(soft) == 0


# ---------------------------------------------------------------------------
# _report_amendements_freshness (issue #254)
# ---------------------------------------------------------------------------

REFERENCE = datetime(2026, 8, 13, 12, 0, 0, tzinfo=timezone.utc)


def _horodatage(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S%z")


def _write_index(cache_dir: Path, legislature: str) -> None:
    """Écrit un cache d'amendements au format dédupliqué (#377) : les deux
    fichiers `amendements.json` + `index_par_acteur.json` vont toujours de
    pair, et le rapport de fraîcheur exige désormais les deux (un cache
    n'ayant que l'un des deux est un cache hérité d'avant #377, traité comme
    absent aussi bien ici que par le lecteur réel)."""
    leg_dir = cache_dir / legislature
    leg_dir.mkdir(parents=True, exist_ok=True)
    (leg_dir / "amendements.json").write_text(json.dumps({}), encoding="utf-8")
    shards = leg_dir / "index_par_acteur"
    shards.mkdir(exist_ok=True)
    (shards / "PA123.json").write_text(json.dumps([]), encoding="utf-8")


def _write_fraicheur(cache_dir: Path, legislature: str, reussi: bool, horodatage: str, figee: bool = False) -> None:
    leg_dir = cache_dir / legislature
    leg_dir.mkdir(parents=True, exist_ok=True)
    payload = {"derniere_construction_reussie": reussi, "horodatage": horodatage}
    if figee:
        payload["figee"] = True
    (leg_dir / "fraicheur.json").write_text(json.dumps(payload), encoding="utf-8")


def _write_all_fresh(cache_dir: Path) -> None:
    """Prépare les 3 législatures comme fraîches, pour isoler une seule
    législature sous test dans les cas ci-dessous (une législature non
    créée du tout serait autrement comptée « jamais construite »)."""
    for legislature in _AMENDEMENTS_LEGISLATURES:
        _write_index(cache_dir, legislature)
        _write_fraicheur(cache_dir, legislature, reussi=True, horodatage=_horodatage(REFERENCE - timedelta(days=1)))


def test_report_amendements_freshness_all_never_built_on_empty_cache_dir(tmp_path):
    """Répertoire de cache absent/vide : chaque législature est signalée
    « jamais construite », pas de faux « périmé »."""
    soft, console, md = _report_amendements_freshness(tmp_path / "amendements_an", staleness_days=7)

    assert len(soft) == len(_AMENDEMENTS_LEGISLATURES)
    assert all("jamais construit" in w for w in soft)
    assert "⚠" in console


def test_report_amendements_freshness_fresh_index_no_warning(tmp_path):
    """Index présent, dernière reconstruction réussie et récente : pas de warning."""
    cache_dir = tmp_path / "amendements_an"
    for legislature in _AMENDEMENTS_LEGISLATURES:
        _write_index(cache_dir, legislature)
        _write_fraicheur(cache_dir, legislature, reussi=True, horodatage=_horodatage(REFERENCE - timedelta(days=1)))

    soft, console, md = _report_amendements_freshness(cache_dir, staleness_days=7, reference_date=REFERENCE)

    assert len(soft) == 0
    assert "✓" in console


def test_report_amendements_freshness_legacy_flat_cache_reported_as_never_built(tmp_path):
    """Cache hérité d'un format précédent (ici #377 : `index_par_acteur.json`
    en fichier unique, sans le répertoire de tranches de #392) : doit être
    rapporté « jamais construit », le
    même verdict que celui du lecteur réel
    (`candidate_profile._read_cached_amendements_agreges`, qui exige les deux
    fichiers et ne relit jamais l'ancien format en mémoire). Sans ça, le
    rapport annoncerait « construit » un index que la collecte ignore."""
    cache_dir = tmp_path / "amendements_an"
    legislature = _AMENDEMENTS_LEGISLATURES[0]
    leg_dir = cache_dir / legislature
    leg_dir.mkdir(parents=True, exist_ok=True)
    (leg_dir / "index_par_acteur.json").write_text(json.dumps({"PA123": []}), encoding="utf-8")
    (leg_dir / "amendements.json").write_text(json.dumps({}), encoding="utf-8")
    _write_fraicheur(cache_dir, legislature, reussi=True, horodatage=_horodatage(REFERENCE))

    soft, console, md = _report_amendements_freshness(cache_dir, staleness_days=7, reference_date=REFERENCE)

    assert any(legislature in w and "jamais construit" in w for w in soft)


def test_report_amendements_freshness_stale_successful_build_flagged(tmp_path):
    """Index présent, dernière reconstruction réussie mais au-delà du seuil : périmé."""
    cache_dir = tmp_path / "amendements_an"
    _write_all_fresh(cache_dir)
    legislature = _AMENDEMENTS_LEGISLATURES[0]
    _write_fraicheur(cache_dir, legislature, reussi=True, horodatage=_horodatage(REFERENCE - timedelta(days=10)))

    soft, console, md = _report_amendements_freshness(cache_dir, staleness_days=7, reference_date=REFERENCE)

    assert len(soft) == 1
    assert "périmé" in soft[0]
    assert "10 jour" in soft[0]


def test_report_amendements_freshness_failed_last_attempt_flagged_regardless_of_age(tmp_path):
    """Dernière tentative de reconstruction en échec (index préservé, #253) :
    périmé même si l'horodatage de l'échec est récent."""
    cache_dir = tmp_path / "amendements_an"
    _write_all_fresh(cache_dir)
    legislature = _AMENDEMENTS_LEGISLATURES[0]
    _write_fraicheur(cache_dir, legislature, reussi=False, horodatage=_horodatage(REFERENCE))

    soft, console, md = _report_amendements_freshness(cache_dir, staleness_days=7, reference_date=REFERENCE)

    assert len(soft) == 1
    assert "échec" in soft[0]


def test_report_amendements_freshness_index_without_fraicheur_file_flagged(tmp_path):
    """Index présent mais sans fraicheur.json (ex. cache antérieur à #253) :
    fraîcheur non garantie, traité comme périmé plutôt que comme faux frais."""
    cache_dir = tmp_path / "amendements_an"
    _write_all_fresh(cache_dir)
    legislature = _AMENDEMENTS_LEGISLATURES[0]
    (cache_dir / legislature / "fraicheur.json").unlink()

    soft, console, md = _report_amendements_freshness(cache_dir, staleness_days=7, reference_date=REFERENCE)

    assert len(soft) == 1
    assert "absent" in soft[0]


def test_report_amendements_freshness_mixed_states_across_legislatures(tmp_path):
    """Des législatures différentes peuvent être dans des états différents
    simultanément : chacune est rapportée indépendamment."""
    cache_dir = tmp_path / "amendements_an"
    leg_fresh, leg_stale, leg_never = _AMENDEMENTS_LEGISLATURES[:3]
    _write_index(cache_dir, leg_fresh)
    _write_fraicheur(cache_dir, leg_fresh, reussi=True, horodatage=_horodatage(REFERENCE - timedelta(days=1)))
    _write_index(cache_dir, leg_stale)
    _write_fraicheur(cache_dir, leg_stale, reussi=True, horodatage=_horodatage(REFERENCE - timedelta(days=30)))
    # leg_never : aucun fichier créé.
    # Toute autre législature au-delà des 3 ci-dessus (ex. l'ajout futur d'une
    # 4e) est mise fraîche pour ne pas fausser l'assertion `len(soft) == 2`
    # ci-dessous, qui ne porte que sur leg_stale/leg_never.
    for leg_autre in _AMENDEMENTS_LEGISLATURES[3:]:
        _write_index(cache_dir, leg_autre)
        _write_fraicheur(cache_dir, leg_autre, reussi=True, horodatage=_horodatage(REFERENCE - timedelta(days=1)))

    soft, console, md = _report_amendements_freshness(cache_dir, staleness_days=7, reference_date=REFERENCE)

    assert len(soft) == 2
    assert any(leg_stale in w and "périmé" in w for w in soft)
    assert any(leg_never in w and "jamais construit" in w for w in soft)
    assert not any(leg_fresh in w for w in soft)


# ---------------------------------------------------------------------------
# État « figé » (légis 15/16 : dossier clos, fallback committé, jamais
# reconstruit — docs/technical_decisions.md#amendements-legislatures-figees).
# ---------------------------------------------------------------------------

def test_report_amendements_freshness_frozen_legislature_no_warning_even_when_very_old(tmp_path):
    """Une législature figée (fraicheur.json avec figee: true) ne doit jamais
    être signalée périmée, même très au-delà du seuil de péremption."""
    cache_dir = tmp_path / "amendements_an"
    _write_all_fresh(cache_dir)
    legislature = next(iter(_AMENDEMENTS_LEGISLATURES_FIGEES))
    _write_fraicheur(
        cache_dir, legislature, reussi=True,
        horodatage=_horodatage(REFERENCE - timedelta(days=365)), figee=True,
    )

    soft, console, md = _report_amendements_freshness(cache_dir, staleness_days=7, reference_date=REFERENCE)

    assert not any(legislature in w for w in soft)
    assert "❄️" in md


def test_report_amendements_freshness_legislature_marked_figee_but_not_in_frozen_set_still_checked(tmp_path):
    """Défense en profondeur : un `figee: true` errant sur une législature hors
    `_AMENDEMENTS_LEGISLATURES_FIGEES` (ex. la 17e, active) ne doit pas la
    dispenser du contrôle de péremption normal."""
    cache_dir = tmp_path / "amendements_an"
    _write_all_fresh(cache_dir)
    active_legislature = next(leg for leg in _AMENDEMENTS_LEGISLATURES if leg not in _AMENDEMENTS_LEGISLATURES_FIGEES)
    _write_fraicheur(
        cache_dir, active_legislature, reussi=True,
        horodatage=_horodatage(REFERENCE - timedelta(days=30)), figee=True,
    )

    soft, console, md = _report_amendements_freshness(cache_dir, staleness_days=7, reference_date=REFERENCE)

    assert any(active_legislature in w and "périmé" in w for w in soft)


def test_report_amendements_freshness_disabled_via_zero_threshold_is_caller_responsibility(tmp_path):
    """staleness_days=0 : tout âge positif dépasse le seuil (aucun raccourci
    interne de désactivation — c'est main() qui saute l'appel sur 0, voir CLI)."""
    cache_dir = tmp_path / "amendements_an"
    legislature = _AMENDEMENTS_LEGISLATURES[0]
    _write_index(cache_dir, legislature)
    _write_fraicheur(cache_dir, legislature, reussi=True, horodatage=_horodatage(REFERENCE - timedelta(days=1)))

    soft, console, md = _report_amendements_freshness(cache_dir, staleness_days=0, reference_date=REFERENCE)

    assert any(legislature in w and "périmé" in w and "seuil 0" in w for w in soft)
