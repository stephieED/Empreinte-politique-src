import sys
from pathlib import Path
from unittest.mock import patch

# Les modules testés vivent dans src/, à côté du dossier tests/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from candidate_profile import (
    _classify_intervention,
    _classify_intervention_format,
    _collect_acteur_roles,
    _collect_initiateurs,
    _collect_texte_codes,
    _derive_amendement_sort,
    _extract_mandats,
    _format_lieu_naissance,
    _groupe_label,
    _parse_amendement_entry,
    _stade_from_code_acte,
    build_profile,
    fetch_all_intervention_results_from_domains,
    fetch_seance_context,
    _extract_speaker_identity_from_html,
)


class DummyResponse:
    def __init__(self, text: str, status_code: int = 200):
        self.text = text
        self.status_code = status_code
        self.encoding = "utf-8"
        self.apparent_encoding = "utf-8"

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


def test_classify_intervention_requires_perso_speaker_match():
    speech = _classify_intervention(
    {
      "texte": "Je souhaite répondre à la question.",
      "speaker_name": "Jean-Luc Mélenchon",
      "speaker_url": "/jean-luc-melenchon",
    },
        "Jean-Luc Mélenchon",
        "62",
    )
    mention = _classify_intervention(
    {
      "texte": "Jean-Luc Mélenchon vous regarde !",
      "speaker_name": "Yaël Braun-Pivet, présidente",
      "speaker_url": "/yael-braun-pivet",
    },
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


def test_classify_intervention_does_not_treat_name_mentions_as_speech():
    classified = _classify_intervention(
        {"texte": "Jean-Luc Mélenchon avait fait une excellente proposition au Président de la République."},
        "Jean-Luc Mélenchon",
        "456",
    )

    assert classified["mode"] == "mention"


def test_extract_speaker_identity_uses_anchor_to_pick_correct_intervention():
    html = """
    <html>
      <body>
        <div class="intervention" id="inter_president">
          <div class="intervenant">
            <div class="perso"><a href="/yael-braun-pivet">Yaël Braun-Pivet, présidente</a></div>
            <div class="texte_intervention"><p>La parole est à M. Jean-Luc Mélenchon.</p></div>
          </div>
        </div>
        <div class="intervention" id="inter_melenchon">
          <div class="intervenant">
            <div class="perso"><a href="/jean-luc-melenchon">Jean-Luc Mélenchon</a></div>
            <div class="texte_intervention"><p>Je vous remercie, madame la présidente.</p></div>
          </div>
        </div>
      </body>
    </html>
    """

    speaker_name, speaker_url = _extract_speaker_identity_from_html(html, anchor_id="inter_melenchon")
    assert speaker_name == "Jean-Luc Mélenchon"
    assert speaker_url == "/jean-luc-melenchon"

    # Sans ancre, le premier div.perso de la page (la présidente) ne doit pas
    # être confondu avec l'orateur de l'intervention ciblée.
    speaker_name_no_anchor, _ = _extract_speaker_identity_from_html(html)
    assert speaker_name_no_anchor == "Yaël Braun-Pivet, présidente"


def test_extract_speaker_identity_from_perso_without_link():
  html = """
  <div class='intervenant'>
    <div class='perso'>Élisabeth Borne, Première ministre</div>
    <div class='texte_intervention'><p>Merci.</p></div>
  </div>
  """

  speaker_name, speaker_url = _extract_speaker_identity_from_html(html)

  assert speaker_name == "Élisabeth Borne, Première ministre"
  assert speaker_url is None


def test_groupe_label_handles_dict_and_string_and_none():
    assert _groupe_label({"organisme": "La France Insoumise", "fonction": "membre"}) == "La France Insoumise"
    assert _groupe_label("La France Insoumise") == "La France Insoumise"
    assert _groupe_label(None) is None


def test_extract_mandats_reads_real_api_responsabilites_fields():
    parlementaire = {
        "mandat_debut": "2017-06-21",
        "mandat_fin": None,
        "groupe": {"organisme": "La France Insoumise", "fonction": "membre"},
        "responsabilites": [
            {
                "responsabilite": {
                    "organisme": "Commission des affaires étrangères",
                    "fonction": "membre",
                    "debut_fonction": "2022-01-14",
                }
            }
        ],
        "historique_responsabilites": [
            {
                "responsabilite": {
                    "organisme": "La France Insoumise",
                    "fonction": "président",
                    "debut_fonction": "2017-06-28",
                    "fin_fonction": "2021-10-12",
                }
            }
        ],
        "groupes_parlementaires": [],
        "responsabilites_extra_parlementaires": [],
    }

    mandats = _extract_mandats(parlementaire)

    mandat_electif = next(m for m in mandats if m["categorie"] == "mandat_electif")
    assert "La France Insoumise" in mandat_electif["label"]
    assert mandat_electif["actif"] is True

    commission_actuelle = next(
        m for m in mandats if m["categorie"] == "commission" and m["label"] == "Commission des affaires étrangères"
    )
    assert commission_actuelle["type"] == "membre"
    assert commission_actuelle["actif"] is True

    ancienne_presidence = next(
        m for m in mandats if m["categorie"] == "commission" and m["label"] == "La France Insoumise"
    )
    assert ancienne_presidence["type"] == "président"
    assert ancienne_presidence["actif"] is False
    assert ancienne_presidence["fin"] == "2021-10-12"


def test_extract_mandats_returns_empty_list_when_no_fields_present():
    assert _extract_mandats({}) == []


def test_fetch_all_intervention_results_from_domains_merges_and_deduplicates():
    with patch(
        "candidate_profile.fetch_all_intervention_results",
        side_effect=[
            {"results": [{"document_id": "1", "document_url": "https://a.fr/1"}]},
            {"results": [{"document_id": "1", "document_url": "https://a.fr/1"}, {"document_id": "2", "document_url": "https://a.fr/2"}]},
        ],
    ) as mocked_fetch:
        merged = fetch_all_intervention_results_from_domains(
            ["https://a.test", "https://b.test"],
            "Jean-Luc Mélenchon",
            max_pages=3,
        )

    assert mocked_fetch.call_count == 2
    assert [item["document_id"] for item in merged["results"]] == ["1", "2"]
    assert merged["results"][0]["_search_base_url"] == "https://a.test"
    assert merged["results"][1]["_search_base_url"] == "https://b.test"


def test_classify_intervention_format_uses_word_count_threshold():
    assert _classify_intervention_format(3) == "reaction_courte"
    assert _classify_intervention_format(274) == "prise_de_parole_developpee"
    assert _classify_intervention_format(None) is None


def test_derive_amendement_sort_maps_discute_states():
    assert _derive_amendement_sort("Discuté", "Adopté") == ("adopté", None)
    assert _derive_amendement_sort("Discuté", "Rejeté") == ("rejeté", None)
    assert _derive_amendement_sort("Discuté", "Tombé") == ("tombé", None)
    assert _derive_amendement_sort("Discuté", "Non soutenu") == ("non_soutenu", None)
    assert _derive_amendement_sort("Retiré", "Retiré avant publication") == ("retiré", None)


def test_derive_amendement_sort_maps_irrecevabilite_by_base_juridique():
    assert _derive_amendement_sort("Irrecevable 40", "Charge") == ("irrecevable", "art. 40")
    assert _derive_amendement_sort("Irrecevable", "Cavalier (45)") == ("irrecevable", "art. 45")


def test_derive_amendement_sort_unknown_or_pending_returns_none():
    assert _derive_amendement_sort("En traitement", None) == (None, None)
    assert _derive_amendement_sort("A discuter", None) == (None, None)


def test_parse_amendement_entry_only_keeps_primary_author():
    raw = {
        "amendement": {
            "identification": {"numeroLong": "AS1"},
            "texteLegislatifRef": "PIONANR5L17B0904",
            "signataires": {
                "auteur": {"typeAuteur": "Député", "acteurRef": "PA1567"},
                "cosignataires": {"acteurRef": ["PA842001", "PA793182"]},
            },
            "cycleDeVie": {
                "dateDepot": "2025-02-17",
                "etatDesTraitements": {
                    "etat": {"libelle": "Discuté"},
                    "sousEtat": {"libelle": "Adopté"},
                },
            },
        }
    }

    result = _parse_amendement_entry(raw)

    assert result is not None
    acteur_ref, record = result
    assert acteur_ref == "PA1567"
    assert record["numero"] == "AS1"
    assert record["texte_vise"] == "PIONANR5L17B0904"
    assert record["type_deposant"] == "depute"
    assert record["date"] == "2025-02-17"
    assert record["sort"] == "adopté"
    assert record["co_signataires"] == ["an:PA842001", "an:PA793182"]


def test_parse_amendement_entry_returns_none_without_acteur_ref():
    raw = {"amendement": {"signataires": {"auteur": {}}}}
    assert _parse_amendement_entry(raw) is None


def test_collect_texte_codes_walks_nested_actes_legislatifs():
    """Un dossier législatif imbrique les codes de texte à plusieurs niveaux
    (actesLegislatifs récursif, textesAssocies en liste) : le collecteur doit
    tous les retrouver, quelle que soit la profondeur."""
    dossier = {
        "titreDossier": {"titre": "Les dépenses de soutien aux aéroports"},
        "actesLegislatifs": {
            "acteLegislatif": {
                "texteAssocie": "RINFANR5L17B1659",
                "actesLegislatifs": {
                    "acteLegislatif": {"texteAssocie": "PIONANR5L17B0904"}
                },
                "textesAssocies": {
                    "texteAssocie": [{"refTexteAssocie": "BTAANR5L17B0905"}]
                },
            }
        },
    }

    codes: set[str] = set()
    _collect_texte_codes(dossier, codes)

    assert codes == {"RINFANR5L17B1659", "PIONANR5L17B0904", "BTAANR5L17B0905"}


def test_collect_texte_codes_empty_for_dossier_without_actes():
    codes: set[str] = set()
    _collect_texte_codes({"titreDossier": {"titre": "Sans acte"}}, codes)
    assert codes == set()


def test_format_lieu_naissance_france_avec_departement():
    assert _format_lieu_naissance("Nantes", "Loire-Atlantique", "France") == "Nantes (Loire-Atlantique)"


def test_format_lieu_naissance_etranger_prefere_le_pays():
    assert _format_lieu_naissance("Alger", None, "Algérie") == "Alger (Algérie)"


def test_format_lieu_naissance_ville_seule():
    assert _format_lieu_naissance("Nantes", None, None) == "Nantes"


def test_format_lieu_naissance_tout_absent():
    assert _format_lieu_naissance(None, None, None) is None


def test_stade_from_code_acte_depot():
    assert _stade_from_code_acte("AN1-DEPOT", None) == "depose"


def test_stade_from_code_acte_commission():
    assert _stade_from_code_acte("AN1-COM-FOND-RAPPORT", None) == "examine_commission"


def test_stade_from_code_acte_debats_seance():
    assert _stade_from_code_acte("AN1-DEBATS-SEANCE", None) == "discute_seance"


def test_stade_from_code_acte_decision_adoptee():
    assert _stade_from_code_acte("AN1-DEBATS-DEC", "adopté") == "adopte"


def test_stade_from_code_acte_decision_rejetee_reste_discute_seance():
    assert _stade_from_code_acte("AN1-DEBATS-DEC", "rejetée") == "discute_seance"


def test_stade_from_code_acte_promulgation():
    assert _stade_from_code_acte("PROM-PUB", None) == "promulgue"


def test_stade_from_code_acte_code_inconnu():
    assert _stade_from_code_acte("CODE-INCONNU", None) is None


def test_collect_initiateurs_acteur_unique():
    acteur_roles: dict = {}
    dossier = {"initiateur": {"acteurs": {"acteur": {"acteurRef": "PA1"}}}}
    _collect_initiateurs(dossier, acteur_roles)
    assert acteur_roles == {"PA1": ("auteur", None)}


def test_collect_initiateurs_liste_acteurs():
    acteur_roles: dict = {}
    dossier = {"initiateur": {"acteurs": {"acteur": [{"acteurRef": "PA1"}, {"acteurRef": "PA2"}]}}}
    _collect_initiateurs(dossier, acteur_roles)
    assert acteur_roles == {"PA1": ("auteur", None), "PA2": ("auteur", None)}


def test_collect_acteur_roles_rapporteur_unique_et_dates():
    dossier = {
        "legislature": "17",
        "initiateur": None,
        "actesLegislatifs": {
            "acteLegislatif": {
                "codeActe": "AN1-COM-FOND-NOMIN",
                "dateActe": "2024-01-10T00:00:00.000+01:00",
                "rapporteurs": {"rapporteur": {"acteurRef": "PA1", "typeRapporteur": "rapporteur"}},
            }
        },
    }
    acteur_roles, stade, date_min, date_max = _collect_acteur_roles(dossier)
    assert acteur_roles == {"PA1": ("rapporteur", "rapporteur_fond")}
    assert stade == "examine_commission"
    assert date_min == date_max == "2024-01-10"


def test_collect_acteur_roles_co_rapporteurs():
    dossier = {
        "legislature": "17",
        "initiateur": None,
        "actesLegislatifs": {
            "acteLegislatif": {
                "codeActe": "AN1-COM-FOND-NOMIN",
                "dateActe": "2024-01-10T00:00:00.000+01:00",
                "rapporteurs": {"rapporteur": [
                    {"acteurRef": "PA1", "typeRapporteur": "rapporteur pour avis"},
                    {"acteurRef": "PA2", "typeRapporteur": "rapporteur pour avis"},
                ]},
            }
        },
    }
    acteur_roles, stade, date_min, date_max = _collect_acteur_roles(dossier)
    assert acteur_roles == {
        "PA1": ("co-rapporteur", "rapporteur_avis"),
        "PA2": ("co-rapporteur", "rapporteur_avis"),
    }


def test_collect_acteur_roles_stade_le_plus_avance_retenu():
    dossier = {
        "legislature": "17",
        "initiateur": {"acteurs": {"acteur": {"acteurRef": "PA1"}}},
        "actesLegislatifs": {
            "acteLegislatif": [
                {"codeActe": "AN1-DEPOT", "dateActe": "2024-01-01T00:00:00.000+01:00"},
                {"codeActe": "PROM-PUB", "dateActe": "2024-06-01T00:00:00.000+02:00"},
            ]
        },
    }
    acteur_roles, stade, date_min, date_max = _collect_acteur_roles(dossier)
    assert acteur_roles == {"PA1": ("auteur", None)}
    assert stade == "promulgue"
    assert date_min == "2024-01-01"
    assert date_max == "2024-06-01"
