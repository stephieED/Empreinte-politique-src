"""#501 : pourquoi `extract-senat` lève `--skip-interventions` en dur.

La collecte d'interventions sénatoriales ne retenait pas *peu* — elle retenait
**zéro**, et pour une raison structurelle, pas conjoncturelle.

`fetch_intervention_details` rattache une intervention à son orateur en allant
lire le bloc `div.perso` de la page de séance, dont il tire l'URL depuis la clé
**`url_nosdeputes`** du document. L'API de `archive.nossenateurs.fr` ne publie
jamais cette clé : elle expose **`url_nossenateurs`** (vérifié sur 4 documents
le 20/08/2026, dont 909543 et 843155). Sans URL, aucune page n'est chargée,
`speaker_name`/`speaker_url` restent `None`, `_classify_intervention` rend
`mention`, et `_process_search_result` jette le document.

Constaté côté CI, corpus vivant : 0 des 789 interventions publiées ne porte de
domaine sénatorial, et le résumé d'`extract-senat` affiche
« Bruno Retailleau: ok (0 interventions, senateurs) » sur les 7 runs relevés
entre le 14/08 et le 19/08/2026 — le seul sénateur en exercice de
`raw_data/candidats.json`.

Ces tests fixent l'asymétrie et non le zéro : le jour où
`fetch_intervention_details` apprendra `url_nossenateurs`, c'est
`test_le_document_senat_reste_ignore` qui tombera, et il faudra rouvrir le
`--skip-interventions` du job plutôt que le découvrir par hasard.

Aucun réseau, aucune lecture du corpus : `_get_payload` et `requests.get` sont
doublés.
"""

import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "src"))

import candidate_profile as cp  # noqa: E402


# Page de séance telle que servie par NosDéputés : le bloc `div.perso` porte
# l'orateur, et c'est le seul rattachement que le classifieur accepte.
PAGE_SEANCE = """
<html><body>
  <div class="intervention" id="inter_abc123">
    <div class="perso"><a href="/bruno-retailleau">Bruno Retailleau</a></div>
    <p>Texte de l'intervention.</p>
  </div>
</body></html>
"""


def _document(cle_url: str) -> dict:
    """Le payload d'un document d'intervention, à la clé d'URL près.

    C'est la SEULE différence entre les deux chambres sur ce chemin : même
    endpoint `/api/document/Intervention/<id>/json`, mêmes champs, une clé qui
    ne porte pas le même nom.
    """
    return {
        "intervention": {
            "id": "909543",
            "date": "2011-03-15",
            "created_at": "2011-03-15T10:00:00",
            "type": "commission",
            "source": "https://exemple.test/seance",
            "intervention": "<p>Texte de l'intervention.</p>",
            cle_url: "https://exemple.test/seance/4321#inter_abc123",
            "parlementaire_id": "479",
            "personnalite_id": None,
            "seance_id": "4321",
            "fonction": "Président",
            "nb_mots": "240",
        }
    }


@pytest.fixture
def sources_doublees(monkeypatch):
    """Double le document ET la page de séance : rien ne sort sur le réseau."""
    pages_demandees: list[str] = []

    class _Reponse:
        status_code = 200
        text = PAGE_SEANCE
        encoding = "utf-8"
        apparent_encoding = "utf-8"

        def raise_for_status(self):
            return None

    def _get(url, **_kwargs):
        pages_demandees.append(url)
        return _Reponse()

    monkeypatch.setattr(cp.requests, "get", _get)
    return pages_demandees


def _detail(monkeypatch, sources_doublees, cle_url):
    monkeypatch.setattr(cp, "_get_payload", lambda url: _document(cle_url))
    return cp.fetch_intervention_details("https://exemple.test", "909543")


# ---------------------------------------------------------------------------
# L'asymétrie
# ---------------------------------------------------------------------------

def test_le_document_an_est_retenu(monkeypatch, sources_doublees):
    """Témoin. Avec `url_nosdeputes`, la page de séance est chargée, l'orateur
    est résolu, et l'intervention est retenue comme prise de parole."""
    detail = _detail(monkeypatch, sources_doublees, "url_nosdeputes")
    assert sources_doublees, "La page de séance aurait dû être chargée."
    assert detail["speaker_name"] == "Bruno Retailleau"
    classification = cp._classify_intervention(detail, "Bruno Retailleau", None)
    assert classification["mode"] == "prise_de_parole"


def test_le_document_senat_reste_ignore(monkeypatch, sources_doublees):
    """Le cœur de #501. Avec `url_nossenateurs`, aucune page n'est chargée et
    l'intervention est classée `mention` — donc jetée par
    `_process_search_result`, qui ne renvoie que les prises de parole.

    Si ce test tombe, `fetch_intervention_details` sait désormais lire la clé
    sénatoriale : rouvrir le `--skip-interventions` en dur d'`extract-senat`
    (docs/technical_decisions.md#interventions-senat-501).
    """
    detail = _detail(monkeypatch, sources_doublees, "url_nossenateurs")
    assert not sources_doublees, (
        "Une page de séance a été chargée : `fetch_intervention_details` sait "
        "désormais résoudre l'orateur côté Sénat."
    )
    assert detail["speaker_name"] is None
    assert detail["speaker_url"] is None
    classification = cp._classify_intervention(detail, "Bruno Retailleau", None)
    assert classification == {
        "mode": "mention",
        "reason": "orateur_bloc_perso_introuvable",
    }


def test_le_document_senat_est_jete_par_le_traitement(monkeypatch, sources_doublees):
    """Bout en bout : ce n'est pas seulement une classification défavorable,
    c'est un document qui ne ressort pas de la collecte."""
    monkeypatch.setattr(cp, "_get_payload", lambda url: _document("url_nossenateurs"))
    retenu = cp._process_search_result(
        {"document_id": "909543", "document_type": "Intervention",
         "document_url": "https://archive.nossenateurs.test/api/document/Intervention/909543/json"},
        "https://archive.nossenateurs.test",
        "Bruno Retailleau",
        None,
    )
    assert retenu is None


def test_le_texte_du_senat_est_pourtant_bien_la(monkeypatch, sources_doublees):
    """Ce qui est perdu n'est pas la donnée, c'est son rattachement : le texte,
    la date et le nombre de mots arrivent intacts. C'est ce qui rend la
    réouverture possible — et pourquoi elle est en ROADMAP plutôt qu'écartée."""
    detail = _detail(monkeypatch, sources_doublees, "url_nossenateurs")
    assert detail["texte"] == "<p>Texte de l'intervention.</p>"
    assert detail["date"] == "2011-03-15"
    assert detail["nb_mots"] == 240
