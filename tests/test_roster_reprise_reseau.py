"""Reprise sur échec transitoire du fetch de roster (#518).

`fetch_full_roster_nosdeputes` faisait **un seul essai**, là où `_get_payload` en fait
trois pour les appels par candidat depuis longtemps. L'asymétrie a coûté 4
shards sur 8 au run `32738726729` (24/08/2026) : la même URL, interrogée dans
la même minute par 8 jobs, a répondu à 4 d'entre eux.

Ce que ces tests verrouillent, ce n'est pas « il y a un retry » mais **la ligne
de partage** : on retente ce qui peut rendre autre chose (timeout, connexion,
5xx), jamais un verdict déterministe (certificat, 4xx). Retenter un certificat
expiré ferait payer trois fois le même échec et retarderait d'autant le
message qui nomme la panne — c'est exactement ce dont #516 avait besoin pour
décider d'une suspension.

Depuis #527 ces règles décrivent la lecture **NosDéputés/NosSénateurs** sous son
propre nom, `fetch_full_roster_nosdeputes` : le Sénat en régime normal, et
l'Assemblée seulement en repli, `group_roster.fetch_full_roster` dérivant
désormais la clé `deputes` d'AMO30. Elles restent testées ici parce qu'un repli
non testé n'est pas un repli.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import group_roster
from group_roster import _ROSTER_MAX_ATTEMPTS, _erreur_retentable, fetch_full_roster_nosdeputes


@pytest.fixture(autouse=True)
def _pas_de_temporisation(monkeypatch):
    """Le backoff est réel en production, jamais dans la suite."""
    monkeypatch.setattr(group_roster.time, "sleep", lambda _s: None)


def _reponse_ok():
    mock = MagicMock()
    mock.json.return_value = {"deputes": [{"depute": {"slug": "alice", "nom": "Alice"}}]}
    mock.raise_for_status.return_value = None
    return mock


def _reponse_http(statut: int):
    """Une réponse dont `raise_for_status()` lève, comme le ferait requests."""
    mock = MagicMock()
    mock.status_code = statut
    erreur = requests.HTTPError(f"{statut} Server Error")
    erreur.response = mock
    mock.raise_for_status.side_effect = erreur
    return mock


# ---------------------------------------------------------------------------
# Ce qui est retenté
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("transitoire", [
    requests.Timeout("Read timed out"),
    requests.ConnectionError("connection reset"),
])
def test_un_echec_transitoire_est_retente_et_le_roster_est_rendu(transitoire):
    session = MagicMock()
    session.get.side_effect = [transitoire, _reponse_ok()]

    membres = fetch_full_roster_nosdeputes("deputes", legislature="16", session=session)

    assert session.get.call_count == 2
    assert [m["slug"] for m in membres] == ["alice"]


@pytest.mark.parametrize("statut", [502, 503, 504])
def test_un_5xx_d_infrastructure_est_retente(statut):
    """502/503/504 viennent d'un frontal ou d'un backend momentanément
    indisponible : un second essai y change quelque chose. 500 non — voir
    `test_un_500_ne_donne_droit_a_aucune_reprise`."""
    session = MagicMock()
    session.get.side_effect = [_reponse_http(statut), _reponse_ok()]

    membres = fetch_full_roster_nosdeputes("deputes", legislature="16", session=session)

    assert session.get.call_count == 2
    assert [m["slug"] for m in membres] == ["alice"]


def test_les_reprises_sont_plafonnees_et_l_erreur_remonte():
    """Épuisées, les tentatives ne rendent pas une liste vide : elles lèvent.

    Un roster vide rendu ici serait la donnée par défaut qu'AGENTS.md §2 règle 5
    interdit — et exactement l'incident de #511.
    """
    session = MagicMock()
    session.get.side_effect = requests.Timeout("Read timed out")

    with pytest.raises(requests.Timeout):
        fetch_full_roster_nosdeputes("deputes", legislature="16", session=session)

    assert session.get.call_count == _ROSTER_MAX_ATTEMPTS


# ---------------------------------------------------------------------------
# Ce qui ne l'est PAS
# ---------------------------------------------------------------------------

def test_un_certificat_expire_ne_donne_droit_a_aucune_reprise():
    """Le cas Sénat de #516, en un test.

    `requests.exceptions.SSLError` hérite de `ConnectionError` : classé par
    héritage, un certificat expiré serait « transitoire ». Trois tentatives
    de 15 s par invocation, sur 9 invocations, pour un verdict connu dès la
    première.
    """
    session = MagicMock()
    session.get.side_effect = requests.exceptions.SSLError("CERTIFICATE_VERIFY_FAILED")

    with pytest.raises(requests.exceptions.SSLError):
        fetch_full_roster_nosdeputes("senateurs", session=session)

    assert session.get.call_count == 1


def test_un_404_ne_donne_droit_a_aucune_reprise():
    session = MagicMock()
    session.get.return_value = _reponse_http(404)

    with pytest.raises(requests.HTTPError):
        fetch_full_roster_nosdeputes("deputes", legislature="16", session=session)

    assert session.get.call_count == 1


def test_un_500_ne_donne_droit_a_aucune_reprise():
    """Un 500 de nosdeputes.fr n'est pas un aléa (#524).

    L'en-tête de `group_roster` documente depuis toujours que
    `/groupe/<SIGLE>/json` « renvoie systématiquement une erreur HTTP 500 » :
    sur cette plateforme, un 500 est une SIGNATURE DE PANNE applicative, pas un
    hoquet d'infrastructure. Le run 32876863499 l'a payé sur `/deputes/json` —
    3 jobs morts en 8 s, soit 3 tentatives et 6 s de backoff sur des réponses
    reçues en 0,4 s. Les reprises ne changeaient pas le verdict, elles ne
    faisaient que retarder le message qui le nomme.
    """
    session = MagicMock()
    session.get.return_value = _reponse_http(500)

    with pytest.raises(requests.HTTPError):
        fetch_full_roster_nosdeputes("deputes", legislature="16", session=session)

    assert session.get.call_count == 1


def test_erreur_retentable_classe_les_quatre_familles():
    assert _erreur_retentable(requests.Timeout("t")) is True
    assert _erreur_retentable(requests.ConnectionError("c")) is True
    assert _erreur_retentable(requests.exceptions.SSLError("s")) is False

    for statut, attendu in (
        (500, False),  # #524 — déterministe sur cette plateforme
        (502, True), (503, True), (504, True),
        (400, False), (429, False),
    ):
        reponse = MagicMock()
        reponse.status_code = statut
        erreur = requests.HTTPError(str(statut))
        erreur.response = reponse
        assert _erreur_retentable(erreur) is attendu, statut


def test_une_http_error_sans_reponse_n_est_pas_retentee():
    """Sans code de statut, rien ne dit que l'échec est transitoire. Le doute
    ne vaut pas trois tentatives."""
    erreur = requests.HTTPError("pas de réponse attachée")
    erreur.response = None
    assert _erreur_retentable(erreur) is False


def test_le_chemin_nominal_ne_paie_aucune_reprise():
    session = MagicMock()
    session.get.return_value = _reponse_ok()

    fetch_full_roster_nosdeputes("deputes", legislature="16", session=session)

    assert session.get.call_count == 1
