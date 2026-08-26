"""#514 — une source injoignable ne consomme plus le timeout d'un job, et son
silence ne se lit plus comme un constat.

Ce que ces tests éprouvent, et qui n'est pas « s'arrêter à temps » :

1. **la collecte entière est bornée**, pas seulement la phase d'interventions.
   Le budget de #498 était neutralisé par `--skip-interventions`, et
   `extract-senat` levait ce drapeau en dur depuis #501 : il n'avait donc plus
   aucun plafond interne. Run 32421439590 (20/08/2026) : 15 min 18 s de
   `timeout-minutes` consommées, **1 profil écrit** ;
2. **le job rend la main**, résumé et annotations compris, au lieu d'être tué ;
3. **« introuvable » cesse de vouloir dire deux choses.** `_try_urls` rend
   `(None, None)` aussi bien quand l'archive répond « je ne connais pas ce
   slug » que quand elle ne répond pas. Le run 32421439590 a imprimé onze
   « introuvable », dont trois sincères (candidats sans slug) et huit dus à une
   source en timeout. Rien ne les distinguait ;
4. **ce que le budget ne doit PAS casser.** Le seul profil que ce run ait
   écrit vient d'une 3ᵉ tentative réussie après deux timeouts sur le même
   format. C'est le contre-exemple des deux autres pistes de l'issue — un
   circuit ouvert après N échecs consécutifs, ou l'abandon de la reprise après
   un timeout — et `test_le_correctif_ne_detruit_pas_la_seule_donnee_du_run`
   est là pour qu'on ne les réintroduise pas sans le voir.

**La source réelle n'est jamais sollicitée.** Tout passe par une doublure qui
rejoue les réponses relevées dans le log du job 96594132947, et le temps est
piloté par une horloge factice — un test qui dormirait réellement 160 s serait
un test qu'on désactive.

**#528 — les mesures viennent du Sénat, le mécanisme n'en venait pas.** Le job
`extract-senat` a été retiré et `archive.nossenateurs.fr` n'est plus une source
(docs/technical_decisions.md#retrait-senat-528). Les scénarios sont donc rejoués
sur la chambre `deputes`, avec `BASE_URLS` réduit à UN domaine — c'était la
propriété du Sénat qui donnait au pire cas sa forme (2 formats × 3 tentatives =
6 requêtes d'identité), et c'est elle, pas le domaine, que ces tests éprouvent.
Deux tests sont partis avec la source : ils regardaient les sections `votes` et
`dossiers législatifs` de NosSénateurs, qui n'existent plus — côté AN ces deux
champs viennent de l'open data, qui ne passe pas par `_get_payload`.
"""

import argparse
import sys
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import budget_collecte
import candidate_profile
from budget_collecte import BudgetCollecte, creer
from candidate_profile import (
    WARNING_PREFIX_BUDGET_COLLECTE,
    WARNING_PREFIX_SOURCE_INJOIGNABLE,
    build_profile,
)
from generate_all_profiles import (
    build_profile_any_chambre,
    process_candidat,
    valider_budgets,
)

# ---------------------------------------------------------------------------
# Mesures du run 32421439590, job extract-senat (96594132947), 20/08/2026 UTC.
# Population : candidat avec slug résolvable, `--source senat
# --skip-interventions`, source DÉGRADÉE (elle a répondu 3 fois sur 45).
# ---------------------------------------------------------------------------

# Durée d'une tentative en timeout, relevée sur les 42 échecs du job : de 14 s
# (connect timeout) à 25 s (watchdog). 16 s est la valeur la plus fréquente.
COUT_TENTATIVE_EN_TIMEOUT = 16.0

# Résolution d'identité (2 formats × 3 tentatives) sur source dégradée :
# jerome-guedj 103 s, jean-luc-melenchon 109 s, edouard-philippe 125 s.
IDENTITE_LA_PLUS_CHERE_MESUREE = 125.0

# La valeur retenue par le workflow pour `--budget-collecte-secondes`.
BUDGET_PAR_CANDIDAT = 160


class HorlogeFactice:
    """`time.monotonic` pilotée à la main."""

    def __init__(self) -> None:
        self.maintenant = 1000.0

    def __call__(self) -> float:
        return self.maintenant

    def avancer(self, secondes: float) -> None:
        self.maintenant += secondes


class ReponseFactice:
    """Le strict nécessaire de l'interface `requests.Response` qu'utilise
    `_get_payload` : statut, en-têtes, corps."""

    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.headers = {"content-type": "application/json"}

    @property
    def text(self) -> str:
        import json

        return json.dumps(self._payload)

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} Error", response=self)


class ArchiveRejouee:
    """Doublure de `_get_with_watchdog` : rejoue une archive dégradée.

    `scenario` associe une URL à la liste de ses résultats successifs, dans
    l'ordre des tentatives — `None` pour un timeout, un dict pour un corps JSON,
    un entier pour un statut HTTP. Toute URL absente du scénario est en timeout,
    ce qui est le comportement par défaut voulu : l'archive du 20/08 ne
    répondait presque jamais.
    """

    def __init__(self, horloge: HorlogeFactice, scenario: dict | None = None) -> None:
        self.horloge = horloge
        self.scenario = scenario or {}
        self.appels: list[str] = []

    def __call__(self, url: str, *, timeout: int):
        self.appels.append(url)
        rang = self.appels.count(url) - 1
        resultats = self.scenario.get(url, [])
        resultat = resultats[rang] if rang < len(resultats) else None
        if resultat is None:
            self.horloge.avancer(COUT_TENTATIVE_EN_TIMEOUT)
            raise requests.exceptions.Timeout(
                f"HTTPSConnectionPool(host='www.nosdeputes.fr', port=443): "
                f"Read timed out. (read timeout={timeout})"
            )
        # Une réponse, même en erreur, coûte moins cher qu'un timeout.
        self.horloge.avancer(1.0)
        if isinstance(resultat, int):
            return ReponseFactice({}, status_code=resultat)
        return ReponseFactice(resultat)


#: Domaine unique des scénarios rejoués (voir la fixture `archive`).
BASE = "https://www.nosdeputes.fr"

IDENTITE_PARLEMENTAIRE = {
    "depute": {
        "nom": "Jean-Luc Mélenchon",
        "slug": "jean-luc-melenchon",
        "groupe_sigle": "SOC",
        "nb_mandats": 2,
    }
}


@pytest.fixture
def horloge(monkeypatch):
    faux = HorlogeFactice()
    monkeypatch.setattr(budget_collecte.time, "monotonic", faux)
    # Les temporisations de courtoisie (backoff de reprise, 0,2 s entre deux
    # formats, 0,5 s après l'identité) sont du temps mur réel : les payer
    # rendrait le fichier inutilisable, les ignorer fausserait le budget. On
    # les fait donc avancer l'horloge factice sans dormir.
    monkeypatch.setattr(candidate_profile.time, "sleep", faux.avancer)
    return faux


@pytest.fixture
def archive(horloge, monkeypatch):
    """Doublure de source + périmètre de collecte réduit à un domaine.

    `BASE_URLS["deputes"]` porte 4 sous-domaines de législature en production.
    Les scénarios rejoués ici ont été relevés sur une source à UN domaine :
    laisser les 4 multiplierait par 4 le nombre de requêtes du pire cas et
    changerait ce que le budget borne. On réduit donc, explicitement.

    `fetch_identite_officielle_par_slug` est neutralisé : c'est le référentiel
    AN (archive AMO30), il ne passe pas par `_get_with_watchdog` et le laisser
    vivant ferait sortir ces tests sur le réseau — ce que `conftest.py` refuse.
    """
    def _monter(scenario: dict | None = None) -> ArchiveRejouee:
        double = ArchiveRejouee(horloge, scenario)
        monkeypatch.setattr(candidate_profile, "_get_with_watchdog", double)
        monkeypatch.setattr(candidate_profile, "BASE_URLS", {"deputes": [BASE]})
        monkeypatch.setattr(
            candidate_profile, "fetch_identite_officielle_par_slug",
            lambda slug: (None, None),
        )
        return double

    return _monter


def _compteur_remis_a_zero(monkeypatch):
    """`compteur_requetes_sans_reponse` est un global de process : les tests le
    comparent avant/après, donc sa valeur absolue n'a pas d'importance — mais
    on part d'un état connu pour que les messages soient lisibles."""
    monkeypatch.setattr(candidate_profile, "_requetes_sans_reponse", 0)


# ---------------------------------------------------------------------------
# La chaîne de budgets
# ---------------------------------------------------------------------------

def test_un_budget_enfant_est_epuise_par_son_parent(horloge):
    """C'est ce qui permet au budget par candidat de borner la collecte
    d'interventions sans qu'une ligne de #500 ne change."""
    parent = BudgetCollecte(10, libelle="collecte")
    enfant = BudgetCollecte(1000, libelle="collecte d'interventions", parent=parent)

    with enfant.section("travail"):
        horloge.avancer(11)

    assert enfant.epuise(), "l'enfant doit voir l'épuisement du parent"
    assert parent.consomme() == pytest.approx(11), (
        "le parent doit être facturé du temps passé dans les sections de l'enfant"
    )


def test_le_message_nomme_le_budget_reellement_epuise(horloge):
    """Dire « plafond 1 000 s » alors que c'est un plafond de 10 s qui a rendu
    la main serait un chiffre juste attribué à la mauvaise population."""
    parent = BudgetCollecte(10, libelle="collecte du job")
    enfant = BudgetCollecte(1000, libelle="collecte d'interventions", parent=parent)

    with enfant.section("travail"):
        horloge.avancer(11)
    enfant.ignorer("document(s)", 3)

    message = enfant.message()
    assert "collecte du job" in message
    assert "plafond 10 s" in message
    assert "plafond 1000 s" not in message


def test_creer_ne_depend_que_de_la_valeur():
    """La fabrique refuse d'avoir une opinion sur les modes : c'est un
    `and not skip_interventions` posé là qui a produit #514."""
    assert creer(0, "collecte") is None
    assert creer(None, "collecte") is None
    budget = creer(120, "collecte")
    assert isinstance(budget, BudgetCollecte)
    assert budget.secondes == 120


# ---------------------------------------------------------------------------
# Ce que le correctif ne doit PAS casser
# ---------------------------------------------------------------------------

def test_le_correctif_ne_detruit_pas_la_seule_donnee_du_run(archive, monkeypatch):
    """Rejoue `jean-luc-melenchon` tel qu'il s'est passé le 20/08/2026.

    `/json` : trois timeouts. `/xml` : deux timeouts, puis **une réponse** à la
    troisième tentative, à t+109 s. C'est le seul profil que le job ait écrit.

    Trois façons de « corriger » #514 l'auraient supprimé :
      - un circuit ouvert après N ≤ 5 échecs consécutifs sur l'hôte (il y en a
        eu exactement 5 avant cette réponse) ;
      - l'abandon de la reprise après un timeout (la réponse est venue de la
        3ᵉ tentative) ;
      - un budget par candidat inférieur à 109 s.
    Le budget retenu, 160 s, laisse passer les trois.
    """
    _compteur_remis_a_zero(monkeypatch)
    double = archive({
        f"{BASE}/jean-luc-melenchon/xml": [None, None, IDENTITE_PARLEMENTAIRE],
    })

    profil, chambre, warnings = build_profile_any_chambre(
        "jean-luc-melenchon",
        max_pages=0,
        chambres=["deputes"],
        skip_interventions=True,
        budget_collecte_secondes=BUDGET_PAR_CANDIDAT,
    )

    assert profil is not None, (
        "le budget a supprimé la seule collecte que la source dégradée rendait encore"
    )
    assert chambre == "deputes"
    assert profil["identite"]["nom_complet"] == "Jean-Luc Mélenchon"
    assert f"{BASE}/jean-luc-melenchon/xml" in double.appels


def test_le_budget_couvre_la_resolution_d_identite_la_plus_chere_mesuree():
    """160 s n'est pas un chiffre rond : c'est le pire cas structurel de la
    résolution d'identité (6 tentatives × 26,5 s = 159 s), et il domine les
    trois mesures de source dégradée du run 32421439590."""
    pire_cas_structurel = 6 * (25 + 1.5)
    assert BUDGET_PAR_CANDIDAT >= IDENTITE_LA_PLUS_CHERE_MESUREE
    assert BUDGET_PAR_CANDIDAT >= pire_cas_structurel


# ---------------------------------------------------------------------------
# La collecte entière est bornée, y compris sous --skip-interventions
# ---------------------------------------------------------------------------

def test_le_budget_borne_la_collecte_meme_sans_interventions(archive, monkeypatch, horloge):
    """Le défaut de #514, en une assertion : avec `--skip-interventions`, la
    collecte doit rester bornée. Avant, `build_profile_any_chambre` rendait
    `budget = None` et les six requêtes sénatoriales partaient sans plafond."""
    _compteur_remis_a_zero(monkeypatch)
    double = archive()
    debut = horloge.maintenant

    build_profile_any_chambre(
        "edouard-philippe",
        max_pages=0,
        chambres=["deputes"],
        skip_interventions=True,
        budget_collecte_secondes=BUDGET_PAR_CANDIDAT,
    )

    ecoule = horloge.maintenant - debut
    # Le dépassement est plafonné à UNE tentative (la requête en vol) parce que
    # le budget est vérifié entre deux tentatives et non entre deux requêtes.
    assert ecoule <= BUDGET_PAR_CANDIDAT + 25 + 2, (
        f"collecte de {ecoule:.0f} s pour un budget de {BUDGET_PAR_CANDIDAT} s"
    )
    # Sans budget, les 6 URLs (identité, votes, dossiers 15/16 × 2 formats)
    # auraient toutes été tentées trois fois.
    assert len(double.appels) < 18, (
        f"{len(double.appels)} tentatives : le budget n'a rien arrêté"
    )


def test_la_troncature_par_budget_est_declaree(archive, monkeypatch):
    """Un budget épuisé sans trace serait la valeur par défaut silencieuse que
    la règle 2.5 interdit : la troncature part dans `meta.warnings[]` ET remonte
    à l'appelant, qui en fait une annotation `::warning::`.

    #528 — ce que ce test regardait, et ce qu'il regarde maintenant. La phase
    tronquée était « votes + dossiers NosSénateurs », obtenue APRÈS une identité
    résolue : le profil partiel était donc écrit, et le test le vérifiait. Cette
    phase n'existe plus — côté AN, votes/amendements/textes viennent de l'open
    data, qui déclare ses propres échecs et ne passe pas par le budget de
    collecte NosDéputés. La seule unité que le budget peut encore refuser sur ce
    chemin est un FORMAT d'identité non tenté, et l'identité est ce qui décide
    qu'un profil est écrit : « tronqué » et « écrit » ne peuvent plus être vrais
    en même temps ici. Ce qui est testé reste le point de #514 — la troncature
    est DÉCLARÉE, jamais subie."""
    _compteur_remis_a_zero(monkeypatch)
    # `/json` en timeout sur ses 3 tentatives (48 s) : le budget de 40 s est
    # épuisé avant que `/xml` ne soit tenté.
    double = archive()

    profil, _, warnings = build_profile_any_chambre(
        "bruno-retailleau",
        max_pages=0,
        chambres=["deputes"],
        skip_interventions=True,
        budget_collecte_secondes=40,
    )

    assert profil is None, "sans identité, aucun profil n'est écrit (comportement acquis)"
    tronquees = [w for w in warnings if w.startswith(WARNING_PREFIX_BUDGET_COLLECTE)]
    assert tronquees, f"aucune troncature déclarée dans {warnings}"
    assert "non tenté" in tronquees[0], (
        "la troncature doit NOMMER ce qui n'a pas été collecté, pas seulement "
        f"annoncer un dépassement : {tronquees[0]}"
    )
    assert not [u for u in double.appels if u.endswith("/xml")], (
        "le format non tenté doit vraiment ne pas avoir été tenté"
    )


# ---------------------------------------------------------------------------
# « introuvable » cesse de vouloir dire deux choses
# ---------------------------------------------------------------------------

def test_une_source_muette_n_est_pas_une_absence(archive, monkeypatch):
    """Sur le run 32421439590, `jerome-guedj` et `edouard-philippe` sont sortis
    en « introuvable » sans un mot sur les 25 requêtes en timeout qui les y
    avaient menés."""
    _compteur_remis_a_zero(monkeypatch)
    archive()

    profil, chambre, warnings = build_profile_any_chambre(
        "jerome-guedj",
        max_pages=0,
        chambres=["deputes"],
        skip_interventions=True,
        budget_collecte_secondes=BUDGET_PAR_CANDIDAT,
    )

    assert profil is None and chambre is None
    injoignable = [w for w in warnings if w.startswith(WARNING_PREFIX_SOURCE_INJOIGNABLE)]
    assert injoignable, f"aucun signal de source injoignable dans {warnings}"
    # Le verdict porte sur les requêtes d'IDENTITÉ, pas sur le total : c'est
    # l'identité qui décide qu'un profil est écrit ou jeté.
    assert "requête(s) d'identité restée(s) sans réponse" in injoignable[0]


# `test_un_profil_partiel_declare_ce_que_la_source_n_a_pas_rendu` a été retiré
# par #528. Il posait qu'un `votes: []` obtenu par timeout devait porter une
# réserve — sur le chemin sénatorial, où `votes` venait de `_get_payload`. Côté
# AN, `votes` vient de l'open data (`fetch_votes_officiels`), qui déclare ses
# propres échecs et n'incrémente pas `compteur_requetes_sans_reponse` : la
# section a donc quitté `sections_vides` avec la chambre. Ce que le test
# éprouvait — « un vide obtenu par silence n'est pas un constat » — reste
# couvert sur `identité` par les deux tests qui l'encadrent.


def test_une_source_qui_repond_vraiment_ne_declenche_aucune_reserve(archive, monkeypatch):
    """Le pendant du test précédent, et ce qui empêche l'avertissement de
    devenir du bruit : une archive qui répond « rien pour ce slug » (404) est un
    constat, pas une panne."""
    _compteur_remis_a_zero(monkeypatch)
    archive({
        f"{BASE}/bruno-retailleau/json": [IDENTITE_PARLEMENTAIRE],
        f"{BASE}/bruno-retailleau/votes/json": [404],
        f"{BASE}/bruno-retailleau/votes/xml": [404],
        f"{BASE}/15/dossiers/nom/json": [404],
        f"{BASE}/16/dossiers/nom/json": [404],
    })

    profil, _, warnings = build_profile_any_chambre(
        "bruno-retailleau",
        max_pages=0,
        chambres=["deputes"],
        skip_interventions=True,
        budget_collecte_secondes=BUDGET_PAR_CANDIDAT,
    )

    assert profil is not None
    assert not [
        w for w in profil["meta"]["warnings"] if w.startswith(WARNING_PREFIX_SOURCE_INJOIGNABLE)
    ], "un 404 est une réponse : rien à signaler"
    assert not [w for w in warnings if w.startswith(WARNING_PREFIX_SOURCE_INJOIGNABLE)]


# ---------------------------------------------------------------------------
# process_candidat : le statut qui distingue les deux silences
# ---------------------------------------------------------------------------

def _args(**overrides) -> argparse.Namespace:
    base = dict(
        source="an",
        pivot_only=False,
        skip_existing=False,
        max_pages=0,
        skip_interventions=True,
        skip_dossiers_legislatifs=False,
        budget_interventions_secondes=0,
        budget_collecte_secondes=BUDGET_PAR_CANDIDAT,
        budget_job_secondes=0,
        skip_ue=True,
        pivot=False,
        no_merge=False,
        enrich_parltrack=False,
    )
    base.update(overrides)
    return argparse.Namespace(**base)


def test_process_candidat_distingue_source_indisponible_d_introuvable(
    archive, monkeypatch, tmp_path
):
    _compteur_remis_a_zero(monkeypatch)
    archive()

    resultat = process_candidat(
        {"nom": "Édouard Philippe", "slug": "edouard-philippe"},
        _args(),
        tmp_path / "raw",
        tmp_path / "pivot",
    )

    assert resultat["statut"] == "source_indisponible", (
        "« introuvable » affirmerait que l'archive ne connaît pas ce slug, "
        "alors qu'elle n'a rien répondu"
    )


def test_process_candidat_dit_toujours_introuvable_quand_la_source_repond(
    archive, monkeypatch, tmp_path
):
    """Le constat sincère doit rester un constat : un 404 sur les deux formats
    d'identité est une réponse."""
    _compteur_remis_a_zero(monkeypatch)
    archive({
        f"{BASE}/marine-tondelier/json": [404],
        f"{BASE}/marine-tondelier/xml": [404],
    })

    resultat = process_candidat(
        {"nom": "Marine Tondelier", "slug": "marine-tondelier"},
        _args(),
        tmp_path / "raw",
        tmp_path / "pivot",
    )

    assert resultat["statut"] == "introuvable"


# ---------------------------------------------------------------------------
# Le budget de job : le run se termine au lieu d'être tué
# ---------------------------------------------------------------------------

def test_le_budget_de_job_rend_la_main_sans_requete(archive, monkeypatch, tmp_path, horloge):
    """Un candidat que le budget de job n'atteint pas doit sortir DÉCLARÉ et
    sans toucher au réseau — la différence avec un `timeout-minutes` atteint,
    où les candidats restants ne figurent nulle part."""
    _compteur_remis_a_zero(monkeypatch)
    double = archive()
    budget_job = BudgetCollecte(90, libelle="collecte du job")

    premier = process_candidat(
        {"nom": "Édouard Philippe", "slug": "edouard-philippe"},
        _args(),
        tmp_path / "raw",
        tmp_path / "pivot",
        budget_job=budget_job,
    )
    appels_apres_le_premier = len(double.appels)

    second = process_candidat(
        {"nom": "Jérôme Guedj", "slug": "jerome-guedj"},
        _args(),
        tmp_path / "raw",
        tmp_path / "pivot",
        budget_job=budget_job,
    )

    assert premier["statut"] == "source_indisponible"
    assert second["statut"] == "budget_job_epuise"
    assert len(double.appels) == appels_apres_le_premier, (
        "un candidat non collecté ne doit émettre aucune requête"
    )
    assert budget_job.unites_ignorees().get("candidat(s) non collecté(s)") == 1


# ---------------------------------------------------------------------------
# Le garde-fou de ligne de commande
# ---------------------------------------------------------------------------

def test_un_budget_mort_est_refuse_et_non_neutralise():
    """La moitié visible de #514. `--budget-interventions-secondes` sous
    `--skip-interventions` était accepté puis rendu `None` en silence, ce qui
    donnait à `extract-senat` l'apparence d'une protection qu'il n'avait pas.

    Le refuser plutôt que le neutraliser oblige à choisir : soit on collecte
    des interventions et le budget vit, soit on ne collecte pas et il n'a rien
    à faire là.
    """
    args = _args(budget_interventions_secondes=240, skip_interventions=True)

    with pytest.raises(SystemExit) as echec:
        valider_budgets(args)

    assert "--budget-collecte-secondes" in str(echec.value), (
        "le refus doit indiquer le budget qui, lui, borne quelque chose"
    )


def test_une_collecte_sans_budget_declare_est_signalee(capsys):
    """L'autre moitié : ne rien dire. Un avertissement et non une erreur —
    rendre l'option obligatoire casserait les commandes locales de README.md, et
    un garde-fou qu'on désactive pour travailler ne garde rien (#460). Le garde
    dur est dans tests/test_ci_budget_par_job.py."""
    valider_budgets(_args(budget_collecte_secondes=None))

    sortie = capsys.readouterr().out
    assert "sans --budget-collecte-secondes" in sortie
    assert "--budget-collecte-secondes 0" in sortie, (
        "l'avertissement doit dire comment déclarer l'absence de budget"
    )


def test_un_zero_explicite_ne_declenche_aucun_avertissement(capsys):
    """`--budget-collecte-secondes 0` est une décision, pas un oubli : la
    distinction entre les deux est tout l'objet du garde-fou."""
    valider_budgets(_args(budget_collecte_secondes=0))

    assert "budget-collecte-secondes" not in capsys.readouterr().out
