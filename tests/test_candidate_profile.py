import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from candidate_profile import _classify_intervention, build_profile, fetch_seance_context, _extract_speaker_identity_from_html


class DummyResponse:
    def __init__(self, text: str, status_code: int = 200):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception("HTTP error")


def test_build_profile_reports_empty_api_payloads():
    with patch("candidate_profile.fetch_identity", return_value={}), patch(
        "candidate_profile.fetch_votes", return_value={}
    ), patch("candidate_profile.time.sleep", return_value=None):
        profile = build_profile("deputes", "slug-inexistant")

    assert profile["identite"] is None
    assert profile["mandats"] == []
    assert profile["votes"] == []
    assert any("identité" in warning for warning in profile["meta"]["warnings"])
    assert any("vote" in warning for warning in profile["meta"]["warnings"])


def test_classify_intervention_distinguishes_speech_from_mention():
    speech = _classify_intervention(
        {"texte": "Je souhaite répondre à la question.", "parlementaire_id": "62"},
        "Jean-Luc Mélenchon",
        "62",
    )
    mention = _classify_intervention(
        {"texte": "Jean-Luc Mélenchon vous regarde !", "parlementaire_id": "123"},
        "Jean-Luc Mélenchon",
        "62",
    )

    assert speech["mode"] == "prise_de_parole"
    assert mention["mode"] == "mention"


def test_fetch_seance_context_prefers_summary_over_page_title():
    html = """
    <html>
      <head><title>Commission du jeudi 14 mars 2024 - Séance</title></head>
      <body>
        <div class='session-summary'>
          <h2>Résumé de la réunion</h2>
          <p>Audit des autorisations de diffusion télévisée</p>
        </div>
        <div class='nuage_de_tags'>Mots clés: numérique audiovisuel télévision</div>
      </body>
    </html>
    """

    with patch("candidate_profile.requests.get", return_value=DummyResponse(html)):
        context = fetch_seance_context({"url": "https://example.test/seance"})

    assert context["sujet"] == "Audit des autorisations de diffusion télévisée"
    assert context["mots_cles"] == ["numérique", "audiovisuel", "télévision"]


def test_fetch_seance_context_extracts_subject_from_summary_links():
    html = """
    <html>
      <head><title>Seance du lundi 24 juin</title></head>
      <body>
        <div class='orga_dossier'>
          <h2>Sommaire</h2>
          <ul>
            <li><a href='#table_15'>Motion de censure</a> <span class='dossier'>(<a href='/16/dossier/15'>voir le dossier</a>)</span></li>
            <li><a href='#table_16'>Discussion et vote</a></li>
          </ul>
        </div>
      </body>
    </html>
    """

    with patch("candidate_profile.requests.get", return_value=DummyResponse(html)):
        context = fetch_seance_context({"url": "https://example.test/seance"})

    assert context["sujet"] == "Motion de censure"


def test_classify_intervention_uses_speaker_name_from_html():
    html = """
    <div class='intervenant'>
      <div class='perso'><span><a href='/yael-braun-pivet'>Yaël Braun-Pivet, présidente</a></span></div>
      <div class='texte_intervention'>
        <p>La parole est à M. Jérôme Guedj.</p>
      </div>
    </div>
    """

    speaker_name, speaker_url = _extract_speaker_identity_from_html(html)
    assert speaker_name == "Yaël Braun-Pivet, présidente"
    assert speaker_url == "/yael-braun-pivet"

    classified = _classify_intervention(
        {"texte": "La parole est à M. Jérôme Guedj.", "speaker_name": "Yaël Braun-Pivet, présidente"},
        "Yaël Braun-Pivet",
        "123",
    )

    assert classified["mode"] == "prise_de_parole"


def test_classify_intervention_requires_perso_block_to_count_as_speech():
    classified = _classify_intervention(
        {
            "texte": "Je souhaite intervenir sur ce sujet.",
            "html": "<div class='intervenant'><div class='texte_intervention'><p>Je souhaite intervenir sur ce sujet.</p></div></div>",
        },
        "Jean-Luc Mélenchon",
        "456",
    )

    assert classified["mode"] == "mention"


def test_classify_intervention_does_not_treat_name_mentions_as_speech():
    classified = _classify_intervention(
        {"texte": "Jean-Luc Mélenchon avait fait une excellente proposition au Président de la République."},
        "Jean-Luc Mélenchon",
        "456",
    )

    assert classified["mode"] == "mention"
