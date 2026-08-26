"""La lecture NosDéputés/NosSénateurs d'un roster, et l'aiguillage de #527.

Depuis la bascule du lot 1b, `fetch_full_roster` **choisit** sa source : AMO30
pour l'Assemblée (`an_roster`), NosDéputés/NosSénateurs sinon. Les tests de ce
fichier qui décrivent la lecture HTTP visent donc `fetch_full_roster_nosdeputes`
— le repli et le Sénat — et deux tests décrivent l'aiguillage lui-même.

Ceux qui passent par `fetch_group_roster("deputes", …)` baissent le drapeau via
la fixture `source_nosdeputes` : ils vérifient la lecture, pas le choix.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import an_roster
import group_roster
from group_roster import (
    _base_url_for,
    fetch_full_roster,
    fetch_full_roster_nosdeputes,
    fetch_group_roster,
    filter_roster_by_sigle,
)


@pytest.fixture
def source_nosdeputes(monkeypatch):
    """Drapeau #527 baissé : `fetch_full_roster` rend l'Assemblée à NosDéputés.

    `monkeypatch.setattr` et non `an_roster.activer_roster_an(False)` : le
    drapeau est un état de module, et une restauration oubliée ferait passer
    tout le reste de la suite sur le repli sans que rien ne le dise.
    """
    monkeypatch.setattr(an_roster, "AN_ROSTER_ACTIF", False)


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


def test_fetch_group_roster_filters_by_sigle(source_nosdeputes):
    session = MagicMock()
    session.get.return_value = _mock_response(_deputes_payload())

    roster = fetch_group_roster("deputes", "LR", legislature="16", session=session)

    assert len(roster) == 2
    slugs = {m["slug"] for m in roster}
    assert slugs == {"alice", "carla"}


def test_fetch_group_roster_marks_actif_from_mandat_fin(source_nosdeputes):
    session = MagicMock()
    session.get.return_value = _mock_response(_deputes_payload())

    roster = fetch_group_roster("deputes", "LR", legislature="16", session=session)
    by_slug = {m["slug"]: m for m in roster}

    assert by_slug["alice"]["actif"] is True
    assert by_slug["carla"]["actif"] is False


def test_fetch_group_roster_empty_when_no_match(source_nosdeputes):
    session = MagicMock()
    session.get.return_value = _mock_response(_deputes_payload())

    roster = fetch_group_roster("deputes", "GDR", legislature="16", session=session)
    assert roster == []


def test_fetch_group_roster_calls_correct_url(source_nosdeputes):
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


# ---------------------------------------------------------------------------
# L'aiguillage de la bascule (#527, lot 1b)
#
# Ce que ces deux tests figent, c'est que le CHOIX de la source tient en une
# condition et qu'il est réversible : la ligne `AN_ROSTER_ACTIF` décide, et rien
# d'autre. C'est ce qui rend le `git revert` de la bascule trivial — la vraie
# assurance de l'épic « une seule source AN ».
# ---------------------------------------------------------------------------

def test_l_assemblee_est_derivee_d_amo30_et_ne_touche_pas_nosdeputes(monkeypatch):
    appels = []

    def faux_roster_an(legislature, **kwargs):
        appels.append(legislature)
        return [{"slug": "alice", "nom": "Alice", "groupe_sigle": "LR"}]

    def interdit(*_a, **_k):  # pragma: no cover - doit ne jamais être appelé
        raise AssertionError("NosDéputés interrogé alors que le drapeau est levé.")

    monkeypatch.setattr(an_roster, "fetch_full_roster_an", faux_roster_an)
    monkeypatch.setattr(group_roster, "fetch_full_roster_nosdeputes", interdit)

    membres = fetch_full_roster("deputes", legislature="16")

    assert appels == ["16"]
    assert [m["slug"] for m in membres] == ["alice"]


def test_le_senat_reste_sur_sa_source_quel_que_soit_le_drapeau(monkeypatch):
    """AMO30 est un référentiel de l'Assemblée : le Sénat n'y est pas (#526 §10)."""
    def interdit(*_a, **_k):  # pragma: no cover - doit ne jamais être appelé
        raise AssertionError("Le Sénat ne se dérive pas d'AMO30.")

    monkeypatch.setattr(an_roster, "fetch_full_roster_an", interdit)
    session = MagicMock()
    session.get.return_value = _mock_response({"senateurs": []})

    assert fetch_full_roster("senateurs", session=session) == []
    assert session.get.call_args[0][0] == "https://archive.nossenateurs.fr/senateurs/json"


def test_le_repli_rend_l_assemblee_a_nosdeputes(source_nosdeputes, monkeypatch):
    """Drapeau baissé — l'état d'avant #527, obtenu par `git revert` d'une ligne."""
    def interdit(*_a, **_k):  # pragma: no cover - doit ne jamais être appelé
        raise AssertionError("AMO30 lu alors que le drapeau est baissé.")

    monkeypatch.setattr(an_roster, "fetch_full_roster_an", interdit)
    session = MagicMock()
    session.get.return_value = _mock_response(_deputes_payload())

    membres = fetch_full_roster("deputes", legislature="16", session=session)

    assert {m["slug"] for m in membres} == {"alice", "bob", "carla"}
    assert session.get.call_args[0][0] == "https://www.nosdeputes.fr/deputes/json"


def test_les_erreurs_des_deux_sources_sont_interceptables_ensemble():
    """`ERREURS_ROSTER` doit couvrir les deux sources, sinon un job meurt en 1.

    `RosterAnIndisponible` hérite de `RuntimeError` : sans cette liste, une
    archive AMO30 absente traverserait le `except` des deux consommateurs et
    ferait sortir le run en 1 — c'est-à-dire annuler son commit — là où #518 a
    payé pour obtenir un 2 qui laisse les fiches publiées en place.
    """
    for erreur in (
        an_roster.RosterAnIndisponible("archive absente"),
        an_roster.RosterAnInactif("drapeau baissé"),
        an_roster.CorrespondanceSiglesInvalide("sigle inconnu"),
        __import__("requests").Timeout("Read timed out"),
        ValueError("législature inconnue"),
    ):
        assert isinstance(erreur, group_roster.ERREURS_ROSTER), type(erreur).__name__


# ---------------------------------------------------------------------------
# fetch_full_roster_nosdeputes / filter_roster_by_sigle (fetch partagé entre
# plusieurs sigles d'une même chambre/législature — voir
# generate_group_profiles.py)
# ---------------------------------------------------------------------------

def test_fetch_full_roster_returns_unwrapped_members_unfiltered():
    session = MagicMock()
    session.get.return_value = _mock_response(_deputes_payload())

    raw_members = fetch_full_roster_nosdeputes("deputes", legislature="16", session=session)

    assert len(raw_members) == 3
    assert {m["slug"] for m in raw_members} == {"alice", "bob", "carla"}
    # Déballé de l'enveloppe {"depute": {...}}, pas de filtrage par sigle.
    assert {m["groupe_sigle"] for m in raw_members} == {"LR", "SOC"}


def test_fetch_full_roster_calls_session_get_once():
    session = MagicMock()
    session.get.return_value = _mock_response(_deputes_payload())

    fetch_full_roster_nosdeputes("deputes", legislature="16", session=session)

    assert session.get.call_count == 1


def test_filter_roster_by_sigle_matches_fetch_group_roster(source_nosdeputes):
    """fetch_full_roster + filter_roster_by_sigle doit produire exactement le
    même résultat qu'un fetch_group_roster direct (garantie de non-régression
    du refactor fetch-once-per-chambre)."""
    session = MagicMock()
    session.get.return_value = _mock_response(_deputes_payload())
    direct = fetch_group_roster("deputes", "LR", legislature="16", session=session)

    raw_members = fetch_full_roster_nosdeputes("deputes", legislature="16", session=session)
    via_filter = filter_roster_by_sigle(raw_members, "deputes", "LR")

    assert via_filter == direct


def test_filter_roster_by_sigle_empty_when_no_match():
    raw_members = [m.get("depute") for m in _deputes_payload()["deputes"]]
    assert filter_roster_by_sigle(raw_members, "deputes", "GDR") == []


def test_fetch_full_roster_one_call_shared_across_multiple_sigles():
    """Le scénario cible de l'optimisation : un seul appel réseau pour
    construire plusieurs groupes de la même chambre/législature."""
    session = MagicMock()
    session.get.return_value = _mock_response(_deputes_payload())

    raw_members = fetch_full_roster_nosdeputes("deputes", legislature="16", session=session)
    lr = filter_roster_by_sigle(raw_members, "deputes", "LR")
    soc = filter_roster_by_sigle(raw_members, "deputes", "SOC")

    assert session.get.call_count == 1
    assert {m["slug"] for m in lr} == {"alice", "carla"}
    assert {m["slug"] for m in soc} == {"bob"}


# ---------------------------------------------------------------------------
# senat_periode_debut / _member_matches_legislature (#191)
#
# archive.nossenateurs.fr (domaine unique, pas de sous-domaine par
# législature) : filtrage optionnel côté client par date de fin de mandat.
# Voir docs/technical_decisions.md#senat-periode-debut pour la limite connue
# de ce filtrage (mandat_fin pas exploitable pour la majorité des entrées
# archivées) — ces tests verrouillent le comportement du code tel qu'il
# existe, indépendamment de cette limite de données.
# ---------------------------------------------------------------------------

def _senateurs_raw_members():
    return [
        {"slug": "courant", "nom": "Courant", "groupe_sigle": "LR", "mandat_debut": "2023-09-24", "mandat_fin": None},
        {"slug": "ancien", "nom": "Ancien", "groupe_sigle": "LR", "mandat_debut": "2011-09-25", "mandat_fin": "2017-09-30"},
        {"slug": "sans-fin", "nom": "SansFin", "groupe_sigle": "LR", "mandat_debut": "2011-09-25", "mandat_fin": None},
    ]


def test_filter_roster_by_sigle_senat_sans_date_garde_tous_les_membres():
    """Sans senat_periode_debut, aucun filtrage temporel (comportement par défaut,
    voir raw_data/groupes_reels.json qui ne renseigne pas ce paramètre)."""
    roster = filter_roster_by_sigle(_senateurs_raw_members(), "senateurs", "LR")
    assert {m["slug"] for m in roster} == {"courant", "ancien", "sans-fin"}


def test_filter_roster_by_sigle_senat_periode_debut_exclut_ancien_avec_mandat_fin_connu():
    roster = filter_roster_by_sigle(
        _senateurs_raw_members(), "senateurs", "LR", senat_periode_debut="2020-01-01",
    )
    assert {m["slug"] for m in roster} == {"courant", "sans-fin"}


def test_filter_roster_by_sigle_senat_periode_debut_garde_membre_sans_mandat_fin():
    """mandat_fin absent (None) est traité comme 'toujours en fonction' — la
    limite documentée de ce filtrage sur les données archivées (voir
    docs/technical_decisions.md#senat-periode-debut) : un ancien sénateur dont
    mandat_fin n'a jamais été renseigné n'est PAS exclu par ce filtrage."""
    roster = filter_roster_by_sigle(
        [{"slug": "sans-fin", "nom": "SansFin", "groupe_sigle": "LR", "mandat_debut": "2011-09-25", "mandat_fin": None}],
        "senateurs", "LR", senat_periode_debut="2024-01-01",
    )
    assert {m["slug"] for m in roster} == {"sans-fin"}


def test_filter_roster_by_sigle_senat_periode_debut_frontiere_incluse():
    """mandat_fin == senat_periode_debut est retenu (comparaison >=, pas >)."""
    roster = filter_roster_by_sigle(
        [{"slug": "frontiere", "nom": "Frontiere", "groupe_sigle": "LR", "mandat_debut": "2017-01-01", "mandat_fin": "2023-01-01"}],
        "senateurs", "LR", senat_periode_debut="2023-01-01",
    )
    assert {m["slug"] for m in roster} == {"frontiere"}


def test_filter_roster_by_sigle_senat_periode_debut_ignoree_pour_deputes():
    """senat_periode_debut n'a d'effet que pour chambre == 'senateurs'."""
    raw_members = [m.get("depute") for m in _deputes_payload()["deputes"]]
    # carla a un mandat terminé en 2022-06-21, largement avant la date fournie ici ;
    # côté "deputes" ce paramètre est ignoré, carla reste donc incluse.
    roster = filter_roster_by_sigle(raw_members, "deputes", "LR", senat_periode_debut="2024-01-01")
    assert {m["slug"] for m in roster} == {"alice", "carla"}
