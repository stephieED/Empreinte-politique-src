import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from group_roster import fetch_group_roster, _base_url_for


def _mock_response(payload):
    mock = MagicMock()
    mock.json.return_value = payload
    mock.raise_for_status.return_value = None
    return mock


def _deputes_payload():
    return {
        "deputes": [
            {"depute": {"slug": "alice", "nom": "Alice", "groupe_sigle": "LR", "mandat_debut": "2022-06-22", "mandat_fin": None}},
            {"depute": {"slug": "bob", "nom": "Bob", "groupe_sigle": "SOC", "mandat_debut": "2022-06-22", "mandat_fin": None}},
            {"depute": {"slug": "carla", "nom": "Carla", "groupe_sigle": "LR", "mandat_debut": "2017-06-21", "mandat_fin": "2022-06-21"}},
        ]
    }


def test_base_url_for_deputes_known_legislature():
    assert _base_url_for("deputes", "16") == "https://www.nosdeputes.fr"
    assert _base_url_for("deputes", "14") == "https://2012-2017.nosdeputes.fr"


def test_base_url_for_deputes_unknown_legislature_raises():
    try:
        _base_url_for("deputes", "99")
        assert False, "devrait lever ValueError"
    except ValueError as exc:
        assert "99" in str(exc)


def test_base_url_for_senateurs_ignores_legislature():
    assert _base_url_for("senateurs", None) == "https://archive.nossenateurs.fr"
    assert _base_url_for("senateurs", "16") == "https://archive.nossenateurs.fr"


def test_base_url_for_unknown_chambre_raises():
    try:
        _base_url_for("maires", None)
        assert False, "devrait lever ValueError"
    except ValueError as exc:
        assert "maires" in str(exc)


def test_fetch_group_roster_filters_by_sigle():
    session = MagicMock()
    session.get.return_value = _mock_response(_deputes_payload())

    roster = fetch_group_roster("deputes", "LR", legislature="16", session=session)

    assert len(roster) == 2
    slugs = {m["slug"] for m in roster}
    assert slugs == {"alice", "carla"}


def test_fetch_group_roster_marks_actif_from_mandat_fin():
    session = MagicMock()
    session.get.return_value = _mock_response(_deputes_payload())

    roster = fetch_group_roster("deputes", "LR", legislature="16", session=session)
    by_slug = {m["slug"]: m for m in roster}

    assert by_slug["alice"]["actif"] is True
    assert by_slug["carla"]["actif"] is False


def test_fetch_group_roster_empty_when_no_match():
    session = MagicMock()
    session.get.return_value = _mock_response(_deputes_payload())

    roster = fetch_group_roster("deputes", "GDR", legislature="16", session=session)
    assert roster == []


def test_fetch_group_roster_calls_correct_url():
    session = MagicMock()
    session.get.return_value = _mock_response({"deputes": []})

    fetch_group_roster("deputes", "LR", legislature="14", session=session)

    called_url = session.get.call_args[0][0]
    assert called_url == "https://2012-2017.nosdeputes.fr/deputes/json"


def test_fetch_group_roster_senateurs_uses_archive_url():
    session = MagicMock()
    session.get.return_value = _mock_response({"senateurs": []})

    fetch_group_roster("senateurs", "LR", session=session)

    called_url = session.get.call_args[0][0]
    assert called_url == "https://archive.nossenateurs.fr/senateurs/json"
