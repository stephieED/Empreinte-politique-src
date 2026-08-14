import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Les modules testés vivent dans src/, à côté du dossier tests/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from candidate_profile import (
    _classify_intervention,
    _classify_intervention_format,
    _collect_acteur_roles,
    _collect_initiateurs,
    _collect_texte_codes,
    _aggregate_amendements_index,
    _derive_amendement_sort,
    _expand_aggregated_amendements_index,
    _extract_mandats,
    _parse_syceron_intervention_entry,
    _format_lieu_naissance,
    _groupe_label,
    _parse_amendement_entry,
    _parse_question_entry,
    _stade_from_code_acte,
    build_profile,
    fetch_interventions_syceron,
    fetch_all_intervention_results_from_domains,
    fetch_questions_officielles,
    fetch_seance_context,
    _extract_speaker_identity_from_html,
)
from normalize_nosdeputes import normalize_nosdeputes


@pytest.fixture(autouse=True)
def _reset_amendements_failed_legislatures_cache():
    """Le cache d'échec inter-candidats (`_amendements_failed_legislatures`, issue
    #239) est un état module-level : sans réinitialisation, un test qui fait
    échouer le téléchargement d'une législature pollue tous les tests suivants
    utilisant la même législature (typiquement "17")."""
    from candidate_profile import _amendements_failed_legislatures

    _amendements_failed_legislatures.clear()
    yield
    _amendements_failed_legislatures.clear()


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


def test_parse_amendement_entry_keeps_primary_author_and_cosignataires():
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
    by_acteur = {acteur_ref: record for acteur_ref, record in result}

    assert set(by_acteur.keys()) == {"PA1567", "PA842001", "PA793182"}

    auteur = by_acteur["PA1567"]
    assert auteur["role_signataire"] == "auteur_principal"
    assert auteur["premier_signataire"] == "an:PA1567"
    assert auteur["numero"] == "AS1"
    assert auteur["texte_vise"] == "PIONANR5L17B0904"
    assert auteur["type_deposant"] == "depute"
    assert auteur["date"] == "2025-02-17"
    assert auteur["sort"] == "adopté"
    assert auteur["co_signataires"] == ["an:PA842001", "an:PA793182"]

    cosign = by_acteur["PA842001"]
    assert cosign["role_signataire"] == "cosignataire"
    assert cosign["premier_signataire"] == "an:PA1567"


def test_parse_amendement_entry_returns_none_without_acteur_ref():
    raw = {"amendement": {"signataires": {"auteur": {}}}}
    assert _parse_amendement_entry(raw) is None


def test_parse_amendement_entry_keeps_cosignataire_from_nested_acteur_dict():
    raw = {
        "amendement": {
            "identification": {"numeroLong": "AS2"},
            "signataires": {
                "auteur": {"typeAuteur": "Député", "acteurRef": "PA1567"},
                "cosignataires": {"acteur": {"acteurRef": "PA842001"}},
            },
            "cycleDeVie": {"dateDepot": "2025-02-18"},
        }
    }

    result = _parse_amendement_entry(raw)

    assert result is not None
    assert {acteur_ref for acteur_ref, _ in result} == {"PA1567", "PA842001"}
    by_acteur = {acteur_ref: record for acteur_ref, record in result}
    assert by_acteur["PA842001"]["role_signataire"] == "cosignataire"
    assert by_acteur["PA842001"]["co_signataires"] == ["an:PA842001"]


def test_parse_amendement_entry_keeps_cosignataires_from_nested_acteur_list():
    raw = {
        "amendement": {
            "identification": {"numeroLong": "AS3"},
            "signataires": {
                "auteur": {"typeAuteur": "Député", "acteurRef": "PA1567"},
                "cosignataires": {
                    "acteur": [
                        {"acteurRef": "PA842001"},
                        {"acteurRef": "PA793182"},
                    ]
                },
            },
            "cycleDeVie": {"dateDepot": "2025-02-19"},
        }
    }

    result = _parse_amendement_entry(raw)

    assert result is not None
    assert {acteur_ref for acteur_ref, _ in result} == {"PA1567", "PA842001", "PA793182"}
    by_acteur = {acteur_ref: record for acteur_ref, record in result}
    assert by_acteur["PA1567"]["co_signataires"] == ["an:PA842001", "an:PA793182"]
    assert by_acteur["PA793182"]["role_signataire"] == "cosignataire"


# ---------------------------------------------------------------------------
# Tests pour `_aggregate_amendements_index` / `_expand_aggregated_amendements_index`
# (issue #268) : le format brut d'`_parse_amendements_zip` duplique
# l'intégralité de chaque amendement (dont `co_signataires`) une fois par
# signataire — mesuré à 3,86 Go décompressés pour la législature 16,
# impossible à committer. `_aggregate_amendements_index` compacte ce résultat
# (chaque amendement une seule fois, référencé par `numero`) avant écriture
# par `build_amendements_index_figees.py` ; `_expand_aggregated_amendements_index`
# est l'inverse, utilisé par `_load_frozen_amendement_index` pour reconstruire
# la forme plate attendue par le reste du pipeline.
# ---------------------------------------------------------------------------

def test_aggregate_amendements_index_deduplicates_shared_amendment():
    """Un amendement à 2 cosignataires (3 entrées dupliquées en entrée) ne doit
    apparaître qu'une seule fois dans `amendements`, sous sa clé `numero` ; les
    3 signataires ne conservent chacun qu'une référence légère."""
    shared_record = {
        "texte_vise": "PIONANR5L17B0904",
        "sort": None,
        "base_juridique_irrecevabilite": None,
        "premier_signataire": "an:PA1567",
        "co_signataires": ["an:PA842001", "an:PA793182"],
        "type_deposant": "depute",
        "date": "2025-02-17",
        "numero": "AS1",
        "source_url": None,
    }
    index = {
        "PA1567": [{**shared_record, "role_signataire": "auteur_principal"}],
        "PA842001": [{**shared_record, "role_signataire": "cosignataire"}],
        "PA793182": [{**shared_record, "role_signataire": "cosignataire"}],
    }

    amendements, index_par_acteur = _aggregate_amendements_index(index)

    assert list(amendements.keys()) == ["AS1"]
    assert amendements["AS1"] == shared_record
    assert "role_signataire" not in amendements["AS1"]
    assert index_par_acteur == {
        "PA1567": [{"numero": "AS1", "role_signataire": "auteur_principal"}],
        "PA842001": [{"numero": "AS1", "role_signataire": "cosignataire"}],
        "PA793182": [{"numero": "AS1", "role_signataire": "cosignataire"}],
    }


def test_aggregate_amendements_index_assigns_synthetic_key_without_dropping_records_missing_numero():
    """Un enregistrement sans `numero` (non observé en pratique) ne doit jamais
    être perdu ni fusionné à tort avec un autre : il reçoit une clé
    synthétique qui lui est propre."""
    index = {
        "PA1": [{"numero": None, "texte_vise": "A"}],
        "PA2": [{"numero": None, "texte_vise": "B"}],
    }

    amendements, index_par_acteur = _aggregate_amendements_index(index)

    assert len(amendements) == 2
    assert {v["texte_vise"] for v in amendements.values()} == {"A", "B"}
    assert len(index_par_acteur["PA1"]) == 1
    assert len(index_par_acteur["PA2"]) == 1


def test_expand_aggregated_amendements_index_reconstructs_flat_form():
    amendements = {
        "AS1": {
            "texte_vise": "PIONANR5L17B0904",
            "premier_signataire": "an:PA1567",
            "co_signataires": ["an:PA842001"],
            "numero": "AS1",
        }
    }
    index_par_acteur = {
        "PA1567": [{"numero": "AS1", "role_signataire": "auteur_principal"}],
        "PA842001": [{"numero": "AS1", "role_signataire": "cosignataire"}],
    }

    expanded = _expand_aggregated_amendements_index(amendements, index_par_acteur)

    assert expanded == {
        "PA1567": [{**amendements["AS1"], "role_signataire": "auteur_principal"}],
        "PA842001": [{**amendements["AS1"], "role_signataire": "cosignataire"}],
    }


def test_expand_aggregated_amendements_index_ignores_dangling_reference():
    """Une référence dont le `numero` est absent de `amendements` (ne devrait
    pas arriver, les deux fichiers étant committés ensemble) est ignorée sans
    lever."""
    expanded = _expand_aggregated_amendements_index(
        {}, {"PA1": [{"numero": "INTROUVABLE", "role_signataire": "auteur_principal"}]}
    )
    assert expanded == {"PA1": []}


def test_aggregate_then_expand_amendements_index_round_trips():
    """L'aller-retour agrégation -> expansion doit reproduire exactement
    l'index plat d'origine — invariant central de la compaction committée."""
    shared_record = {
        "texte_vise": "PIONANR5L17B0904",
        "premier_signataire": "an:PA1567",
        "co_signataires": ["an:PA842001"],
        "numero": "AS1",
    }
    original = {
        "PA1567": [{**shared_record, "role_signataire": "auteur_principal"}],
        "PA842001": [{**shared_record, "role_signataire": "cosignataire"}],
    }

    amendements, index_par_acteur = _aggregate_amendements_index(original)
    roundtripped = _expand_aggregated_amendements_index(amendements, index_par_acteur)

    assert roundtripped == original


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


# ---------------------------------------------------------------------------
# _parse_question_entry
# ---------------------------------------------------------------------------

def _make_question_data(
    xsi_type="QuestionEcrite_Type",
    acteur_ref="PA1567",
    uid="QANR5L17QE12345",
    analyse="Budget 2025",
    texte="Monsieur le ministre, ...",
    date_jo="2025-01-15",
    reponse_texte=None,
    date_reponse=None,
    ministere="Ministère de l'Économie",
    groupe_sigle="LFI-NUPES",
):
    data: dict = {
        "question": {
            "@xsi:type": xsi_type,
            "uid": uid,
            "auteur": {
                "identite": {"acteurRef": acteur_ref},
                "groupe": {"abrege": groupe_sigle, "developpe": "La France Insoumise"},
            },
            "minInt": {"developpe": ministere},
            "indexationAN": {"analyses": {"analyse": analyse}},
            "textesQuestion": {
                "texteQuestion": {"texte": texte, "infoJO": {"dateJO": date_jo}}
            },
        }
    }
    if reponse_texte is not None:
        data["question"]["textesReponse"] = {
            "texteReponse": {"texte": reponse_texte, "infoJO": {"dateJO": date_reponse}}
        }
    return data


def test_parse_question_entry_basic_qe():
    data = _make_question_data()
    result = _parse_question_entry(data, "QE")
    assert result is not None
    acteur_ref, record = result
    assert acteur_ref == "PA1567"
    assert record["uid"] == "QANR5L17QE12345"
    assert record["sous_type"] == "QE"
    assert record["sujet"] == "Budget 2025"
    assert record["texte"] == "Monsieur le ministre, ..."
    assert record["date"] == "2025-01-15"
    assert record["reponse"] is None
    assert record["date_reponse"] is None
    assert record["ministere"] == "Ministère de l'Économie"
    assert record["groupe_sigle"] == "LFI-NUPES"


def test_parse_question_entry_with_response():
    data = _make_question_data(
        reponse_texte="La réponse est ...",
        date_reponse="2025-03-10",
    )
    result = _parse_question_entry(data, "QG")
    assert result is not None
    _, record = result
    assert record["sous_type"] == "QG"
    assert record["reponse"] == "La réponse est ..."
    assert record["date_reponse"] == "2025-03-10"


def test_parse_question_entry_returns_none_without_acteur_ref():
    data = {"question": {"uid": "QANR5L17QE99999", "auteur": {"identite": {}}}}
    assert _parse_question_entry(data, "QE") is None


def test_parse_question_entry_returns_none_without_question_key():
    assert _parse_question_entry({}, "QE") is None
    assert _parse_question_entry({"autre": {}}, "QE") is None


def test_parse_question_entry_analyse_as_list():
    data = _make_question_data(analyse=["Thème A", "Thème B"])
    result = _parse_question_entry(data, "QOSD")
    assert result is not None
    _, record = result
    assert record["sujet"] == "Thème A ; Thème B"


def test_parse_question_entry_texte_question_as_list_takes_last():
    data = {
        "question": {
            "uid": "QANR5L17QE1",
            "auteur": {"identite": {"acteurRef": "PA1"}, "groupe": {}},
            "minInt": {},
            "indexationAN": {"analyses": {"analyse": "Sujet"}},
            "textesQuestion": {
                "texteQuestion": [
                    {"texte": "Version initiale", "infoJO": {"dateJO": "2025-01-01"}},
                    {"texte": "Version révisée", "infoJO": {"dateJO": "2025-02-01"}},
                ]
            },
        }
    }
    result = _parse_question_entry(data, "QE")
    assert result is not None
    _, record = result
    assert record["texte"] == "Version révisée"
    assert record["date"] == "2025-02-01"


# ---------------------------------------------------------------------------
# fetch_questions_officielles
# ---------------------------------------------------------------------------

def test_fetch_questions_officielles_returns_empty_without_acteur_ref():
    # Sans url_an_ou_senat, l'acteur_ref ne peut pas être extrait → liste vide.
    result = fetch_questions_officielles(None)
    assert result == []

    result = fetch_questions_officielles("https://www.nosdeputes.fr/jean-dupont")
    assert result == []


def test_fetch_questions_officielles_maps_index_to_interventions():
    # Simule un index déjà construit (sans réseau) avec 2 questions pour PA1567.
    index = {
        "PA1567": [
            {
                "uid": "QANR5L17QE1",
                "sous_type": "QE",
                "sujet": "Budget 2025",
                "texte": "Question sur le budget.",
                "reponse": None,
                "ministere": "Min. des Finances",
                "date": "2025-01-15",
                "date_reponse": None,
                "groupe_sigle": "LFI",
            },
            {
                "uid": "QANR5L17QG2",
                "sous_type": "QG",
                "sujet": "Santé",
                "texte": "Question au gouvernement sur la santé.",
                "reponse": "Réponse du gouvernement.",
                "ministere": "Min. de la Santé",
                "date": "2025-02-20",
                "date_reponse": "2025-03-10",
                "groupe_sigle": "LFI",
            },
        ]
    }

    def fake_build_index(legislature):
        return index if legislature == "17" else {}

    with patch("candidate_profile._build_acteur_questions_index", side_effect=fake_build_index):
        result = fetch_questions_officielles(
            "https://www.assemblee-nationale.fr/dyn/deputes/PA1567"
        )

    assert len(result) == 2
    # Tri décroissant par date
    assert result[0]["date"] == "2025-02-20"
    assert result[1]["date"] == "2025-01-15"

    q0 = result[0]
    assert q0["type_detail"] == "question"
    assert q0["sous_type"] == "QG"
    assert q0["sujet"] == "Santé"
    assert q0["reponse"] == "Réponse du gouvernement."
    assert q0["ministere"] == "Min. de la Santé"
    assert q0["date_reponse"] == "2025-03-10"
    assert q0["format"] == "prise_de_parole_developpee"
    assert q0["id"] == "question_QANR5L17QG2"
    assert "q17/QANR5L17QG2.htm" in (q0["url"] or "")
    assert q0["legislature"] == "17"

    q1 = result[1]
    assert q1["reponse"] is None
    assert q1["date_reponse"] is None


def test_fetch_questions_officielles_aggregates_multiple_legislatures():
    index_16 = {"PA1567": [{"uid": "QANR5L16QE1", "sous_type": "QE", "sujet": "S16",
                             "texte": "T", "reponse": None, "ministere": None,
                             "date": "2023-05-01", "date_reponse": None, "groupe_sigle": None}]}
    index_17 = {"PA1567": [{"uid": "QANR5L17QE1", "sous_type": "QE", "sujet": "S17",
                             "texte": "T", "reponse": None, "ministere": None,
                             "date": "2025-01-01", "date_reponse": None, "groupe_sigle": None}]}

    def fake_build_index(legislature):
        return index_17 if legislature == "17" else index_16 if legislature == "16" else {}

    with patch("candidate_profile._build_acteur_questions_index", side_effect=fake_build_index):
        result = fetch_questions_officielles(
            "https://www.assemblee-nationale.fr/dyn/deputes/PA1567"
        )

    assert len(result) == 2
    subjects = {r["sujet"] for r in result}
    assert subjects == {"S16", "S17"}


# ---------------------------------------------------------------------------
# Syceron (débats officiels)
# ---------------------------------------------------------------------------

def test_parse_syceron_intervention_entry_keeps_official_actor_match():
    parsed = _parse_syceron_intervention_entry(
        {
            "date": "2025-02-11",
            "type_detail": "question_gouvernement",
            "sujet": "Questions au Gouvernement",
            "texte": "Monsieur le Premier ministre...",
            "fonction": "député",
            "format": "prise_de_parole_developpee",
            "mots_cles": [],
            "source_id": "CRSANR5L17S2025O1N037",
            "seance_ref": "RUANR5L17S2025IDS28624",
            "session_ref": "SCR5A2025O1",
            "orateur_id_source": "PA1567",
            "orateur_nom": "Jean Dupont",
            "point_ordre_du_jour": "Questions au Gouvernement",
            "etat_compte_rendu": "complet",
            "version_compte_rendu": "JO",
        },
        "17",
        3,
    )

    assert parsed is not None
    acteur_ref, record = parsed
    assert acteur_ref == "PA1567"
    assert record["id"] == "syceron_CRSANR5L17S2025O1N037_000003"
    assert record["legislature"] == "17"
    assert record["source_url"].endswith("/17/vp/syceronbrut/syseron.xml.zip")


def test_parse_syceron_intervention_entry_returns_none_without_official_actor_ref():
    assert _parse_syceron_intervention_entry({"orateur_id_source": None}, "17", 0) is None
    assert _parse_syceron_intervention_entry({"orateur_id_source": "GVT1"}, "17", 0) is None


def test_fetch_interventions_syceron_returns_empty_without_acteur_ref():
    assert fetch_interventions_syceron(None) == []
    assert fetch_interventions_syceron("https://www.nosdeputes.fr/jean-dupont") == []


def test_fetch_interventions_syceron_maps_actor_to_candidate_interventions():
    index = {
        "PA1567": [
            {
                "id": "syceron_CRS17_000001",
                "date": "2025-02-11",
                "type_detail": "question_gouvernement",
                "sujet": "Questions au Gouvernement",
                "texte": "Texte 17",
                "source_url": "https://data.assemblee-nationale.fr/static/openData/repository/17/vp/syceronbrut/syseron.xml.zip",
                "legislature": "17",
            }
        ]
    }

    with patch("candidate_profile.SYCERON_AVAILABLE_LEGISLATURES", {"17"}), \
         patch("candidate_profile._build_acteur_interventions_syceron_index", return_value=index):
        result = fetch_interventions_syceron(
            "https://www.assemblee-nationale.fr/dyn/deputes/PA1567"
        )

    assert len(result) == 1
    assert result[0]["id"] == "syceron_CRS17_000001"
    assert result[0]["sujet"] == "Questions au Gouvernement"


def test_fetch_interventions_syceron_aggregates_multiple_legislatures():
    index_16 = {
        "PA1567": [{"id": "syceron_CRS16_000001", "date": "2024-06-01", "sujet": "L16"}]
    }
    index_17 = {
        "PA1567": [{"id": "syceron_CRS17_000001", "date": "2025-02-11", "sujet": "L17"}]
    }

    def fake_build_index(legislature):
        return index_17 if legislature == "17" else index_16 if legislature == "16" else {}

    with patch("candidate_profile.SYCERON_AVAILABLE_LEGISLATURES", {"16", "17"}), \
         patch("candidate_profile._build_acteur_interventions_syceron_index", side_effect=fake_build_index):
        result = fetch_interventions_syceron(
            "https://www.assemblee-nationale.fr/dyn/deputes/PA1567"
        )

    assert [r["sujet"] for r in result] == ["L17", "L16"]


# ---------------------------------------------------------------------------
# build_profile integrates official questions into interventions
# ---------------------------------------------------------------------------

def test_build_profile_includes_official_questions_in_interventions():
    fake_questions = [
        {
            "id": "question_QANR5L17QE1",
            "date": "2025-01-15",
            "type_detail": "question",
            "sous_type": "QE",
            "sujet": "Budget",
            "texte": "Texte Q",
            "reponse": None,
            "date_reponse": None,
            "ministere": "Min. Finances",
            "groupe_sigle": "LFI",
            "fonction": None,
            "format": "prise_de_parole_developpee",
            "mots_cles": [],
            "url": "https://questions.assemblee-nationale.fr/q17/QANR5L17QE1.htm",
            "url_detail": "https://questions.assemblee-nationale.fr/q17/QANR5L17QE1.htm",
            "legislature": "17",
        }
    ]

    with (
        patch("candidate_profile.fetch_identity", return_value={}),
        patch("candidate_profile.fetch_votes", return_value={}),
        patch("candidate_profile.time.sleep", return_value=None),
        patch("candidate_profile.fetch_questions_officielles", return_value=fake_questions),
    ):
        profile = build_profile("deputes", "slug-test")

    # Sans identité, les questions ne sont pas collectées (chambre == "deputes" mais
    # profile["identite"] est None) : les questions ne doivent PAS être dans interventions.
    assert not any(i.get("type_detail") == "question" for i in profile["interventions"])


# ---------------------------------------------------------------------------
# Tests pour la logique de court-circuit sur échecs déterministes (_TERMINAL_FAILURE)
# ---------------------------------------------------------------------------

import requests as _requests


def test_get_payload_returns_terminal_failure_on_4xx():
    """Un HTTP 404 renvoie _TERMINAL_FAILURE (pas None)."""
    from candidate_profile import _get_payload, _TERMINAL_FAILURE

    class Resp404:
        status_code = 404
        headers = {"content-type": "text/html"}
        text = "Not Found"

        def raise_for_status(self):
            raise _requests.HTTPError("404", response=self)

    with patch("candidate_profile.requests.get", return_value=Resp404()):
        result = _get_payload("https://example.test/missing/json")

    assert result is _TERMINAL_FAILURE


def test_get_payload_returns_none_on_5xx():
    """Un HTTP 500 renvoie None (échec transitoire, pas terminal)."""
    from candidate_profile import _get_payload, _TERMINAL_FAILURE

    class Resp500:
        status_code = 500
        headers = {"content-type": "text/html"}
        text = "Server Error"

        def raise_for_status(self):
            raise _requests.HTTPError("500", response=self)

    with patch("candidate_profile.requests.get", return_value=Resp500()):
        result = _get_payload("https://example.test/error/json")

    assert result is None
    assert result is not _TERMINAL_FAILURE


def test_get_payload_returns_terminal_failure_on_unsupported_format():
    """Un format de réponse non pris en charge renvoie _TERMINAL_FAILURE."""
    from candidate_profile import _get_payload, _TERMINAL_FAILURE

    class RespUnknown:
        status_code = 200
        headers = {"content-type": "text/plain"}
        text = "hello world"

        def raise_for_status(self):
            pass

    with patch("candidate_profile.requests.get", return_value=RespUnknown()):
        result = _get_payload("https://example.test/resource")

    assert result is _TERMINAL_FAILURE


def test_get_payload_returns_terminal_failure_on_malformed_json():
    """Une réponse JSON malformée (Content-Type JSON mais corps invalide) renvoie _TERMINAL_FAILURE."""
    from candidate_profile import _get_payload, _TERMINAL_FAILURE

    class RespBadJson:
        status_code = 200
        headers = {"content-type": "application/json"}
        text = "{not valid json"

        def raise_for_status(self):
            pass

        def json(self):
            raise ValueError("Expecting property name")

    with patch("candidate_profile.requests.get", return_value=RespBadJson()):
        result = _get_payload("https://example.test/bad/json")

    assert result is _TERMINAL_FAILURE


def test_try_urls_skips_xml_after_json_terminal_failure():
    """Si /json renvoie _TERMINAL_FAILURE, /xml ne doit pas être essayé pour ce base_url."""
    from candidate_profile import _try_urls, _TERMINAL_FAILURE

    calls: list[str] = []

    def fake_get_payload(url: str):
        calls.append(url)
        return _TERMINAL_FAILURE

    with patch("candidate_profile._get_payload", side_effect=fake_get_payload):
        result, base = _try_urls(["https://base1.test", "https://base2.test"], "label", "slug")

    # Ni /xml pour base1, ni essai de base2 : _TERMINAL_FAILURE doit court-circuiter
    # l'essai de l'autre format MAIS les autres bases URL restent éligibles.
    json_calls = [u for u in calls if u.endswith("/json")]
    xml_calls = [u for u in calls if u.endswith("/xml")]
    assert len(json_calls) == 2, f"Attendu 2 essais /json (un par base), obtenu: {json_calls}"
    assert xml_calls == [], f"Aucun essai /xml attendu après terminal failure, obtenu: {xml_calls}"
    assert result is None
    assert base is None


def test_fetch_votes_skips_xml_after_terminal_failure():
    """fetch_votes ne doit pas tenter /xml si /json renvoie _TERMINAL_FAILURE."""
    from candidate_profile import fetch_votes, _TERMINAL_FAILURE

    calls: list[str] = []

    def fake_get_payload(url: str):
        calls.append(url)
        return _TERMINAL_FAILURE

    with patch("candidate_profile._get_payload", side_effect=fake_get_payload):
        votes, base = fetch_votes(["https://base1.test"], "slug")

    xml_calls = [u for u in calls if "/votes/xml" in u]
    assert xml_calls == [], f"Aucun essai /votes/xml attendu, obtenu: {xml_calls}"
    assert votes is None
    assert base is None


# ---------------------------------------------------------------------------
# #78 — Syceron comme source primaire dans build_profile()
# ---------------------------------------------------------------------------

def _fake_identity_with_acteur_ref():
    """Retourne un payload identité minimal permettant de résoudre un acteurRef."""
    return {
        "depute": {
            "id": "PA123456",
            "nom": "Dupont",
            "prenom": "Jean",
            "slug": "jean-dupont",
            "groupe": {"acronyme": "RE", "nom": "Renaissance"},
            "url_an_ou_senat": "https://www.assemblee-nationale.fr/dyn/deputes/PA123456",
        }
    }


def test_build_profile_uses_syceron_as_primary_for_deputes():
    """Quand Syceron retourne des interventions, elles doivent être utilisées comme source primaire."""
    fake_syceron = [
        {
            "id": "syceron_CRS17_000001",
            "date": "2025-02-11",
            "type_detail": "loi",
            "sujet": "Débat officiel",
            "texte": "Texte officiel.",
            "seance_ref": "RUANR5L17S2025O1N037",
        }
    ]
    with (
        patch("candidate_profile.fetch_identity", return_value=_fake_identity_with_acteur_ref()),
        patch("candidate_profile.fetch_votes", return_value={}),
        patch("candidate_profile.time.sleep", return_value=None),
        patch("candidate_profile.fetch_interventions_syceron", return_value=fake_syceron),
        patch("candidate_profile.fetch_questions_officielles", return_value=[]),
    ):
        profile = build_profile("deputes", "jean-dupont")

    assert profile["interventions"] == fake_syceron
    assert profile["meta"]["synchro_sources"]["assemblee_nationale_syceron"] is not None
    # Pas de warning de fallback
    assert not any("fallback" in w for w in profile["meta"]["warnings"])


def test_build_profile_falls_back_to_nosdeputes_when_syceron_empty():
    """Quand Syceron ne retourne rien, le fallback NosDéputés doit être utilisé et un warning ajouté."""
    with (
        patch("candidate_profile.fetch_identity", return_value=_fake_identity_with_acteur_ref()),
        patch("candidate_profile.fetch_votes", return_value={}),
        patch("candidate_profile.time.sleep", return_value=None),
        patch("candidate_profile.fetch_interventions_syceron", return_value=[]),
        patch("candidate_profile.fetch_questions_officielles", return_value=[]),
        patch("candidate_profile._extract_search_results", return_value=[{"id": "nosdeputes_1"}]),
    ):
        profile = build_profile("deputes", "jean-dupont")

    assert profile["interventions"] == [{"id": "nosdeputes_1"}]
    assert profile["meta"]["synchro_sources"]["assemblee_nationale_syceron"] is None
    fallback_warnings = [w for w in profile["meta"]["warnings"] if "fallback" in w.lower() or "nosdeputes" in w.lower()]
    assert fallback_warnings, "Un warning de fallback NosDéputés doit être présent"


def test_build_profile_syceron_exception_triggers_fallback_warning():
    """Si fetch_interventions_syceron lève une exception, le fallback NosDéputés doit être utilisé et un warning ajouté."""
    with (
        patch("candidate_profile.fetch_identity", return_value=_fake_identity_with_acteur_ref()),
        patch("candidate_profile.fetch_votes", return_value={}),
        patch("candidate_profile.time.sleep", return_value=None),
        patch("candidate_profile.fetch_interventions_syceron", side_effect=RuntimeError("connexion échouée")),
        patch("candidate_profile.fetch_questions_officielles", return_value=[]),
        patch("candidate_profile._extract_search_results", return_value=[]),
    ):
        profile = build_profile("deputes", "jean-dupont")

    assert profile["meta"]["synchro_sources"]["assemblee_nationale_syceron"] is None
    assert any("syceron" in w.lower() for w in profile["meta"]["warnings"])


def test_build_profile_no_syceron_for_senat():
    """Le chemin Syceron ne doit pas être pris pour la chambre sénateurs."""
    with (
        patch("candidate_profile.fetch_identity", return_value={}),
        patch("candidate_profile.fetch_votes", return_value={}),
        patch("candidate_profile.time.sleep", return_value=None),
        patch("candidate_profile.fetch_interventions_syceron") as mock_syceron,
        # Évite un vrai appel réseau : chambre="senateurs" ne prend jamais le
        # chemin Syceron, mais tombe dans la branche NosDéputés générique.
        patch("candidate_profile._extract_search_results", return_value=[]),
    ):
        build_profile("senateurs", "jean-dupont")

    mock_syceron.assert_not_called()


# ---------------------------------------------------------------------------
# #83 — Tests d'intégration bout-en-bout : build_profile() → normalize_nosdeputes()
# ---------------------------------------------------------------------------

def _fake_syceron_interventions():
    """3 interventions Syceron avec seance_ref, session_ref et point_ordre_du_jour."""
    syceron_zip = "https://data.assemblee-nationale.fr/static/openData/repository/17/vp/syceronXML/syceron.zip"
    return [
        {
            "id": "syceron_CRS17_000001_000000",
            "date": "2025-02-11",
            "type_detail": "loi",
            "sujet": "Débat sur le budget rectificatif",
            "texte": "Texte de l'intervention 1.",
            "fonction": None,
            "format": "long",
            "mots_cles": ["budget", "fiscalité"],
            "source": syceron_zip,
            "source_url": syceron_zip,
            "url": syceron_zip,
            "url_detail": None,
            "source_id": "CRS17_000001",
            "seance_ref": "RUANR5L17S2025O1N037",
            "session_ref": "S2024-2025",
            "orateur_id_source": "PA123456",
            "orateur_nom": "Jean Dupont",
            "point_ordre_du_jour": "Examen du PLFR 2025",
            "etat_compte_rendu": "definitif",
            "version_compte_rendu": "1",
            "legislature": "17",
        },
        {
            "id": "syceron_CRS17_000002_000000",
            "date": "2025-03-05",
            "type_detail": "commission",
            "sujet": "Audition du ministre de l'économie",
            "texte": "Texte de l'intervention 2.",
            "fonction": "president",
            "format": "court",
            "mots_cles": ["économie"],
            "source": syceron_zip,
            "source_url": syceron_zip,
            "url": syceron_zip,
            "url_detail": None,
            "source_id": "CRS17_000002",
            "seance_ref": "RUANR5L17S2025O1N041",
            "session_ref": "S2024-2025",
            "orateur_id_source": "PA123456",
            "orateur_nom": "Jean Dupont",
            "point_ordre_du_jour": None,
            "etat_compte_rendu": "definitif",
            "version_compte_rendu": "1",
            "legislature": "17",
        },
        {
            "id": "syceron_CRS17_000003_000000",
            "date": "2025-04-22",
            "type_detail": "loi",
            "sujet": "Discussion générale sur la réforme des retraites",
            "texte": "Texte de l'intervention 3.",
            "fonction": None,
            "format": "long",
            "mots_cles": ["social", "retraites"],
            "source": syceron_zip,
            "source_url": syceron_zip,
            "url": syceron_zip,
            "url_detail": None,
            "source_id": "CRS17_000003",
            "seance_ref": "RUANR5L17S2025O1N055",
            "session_ref": "S2024-2025",
            "orateur_id_source": "PA123456",
            "orateur_nom": "Jean Dupont",
            "point_ordre_du_jour": "Réforme des retraites — PL n° 2025-17",
            "etat_compte_rendu": "provisoire",
            "version_compte_rendu": "1",
            "legislature": "17",
        },
    ]


def test_integration_build_profile_syceron_enrichit_champs_pivot():
    """Intégration bout-en-bout : build_profile() avec Syceron → normalize_nosdeputes()
    doit produire des interventions avec theme_officiel, seance, dossier et source renseignés,
    sans passer par le scraping HTML NosDéputés."""
    fake_syceron = _fake_syceron_interventions()

    with (
        patch("candidate_profile.fetch_identity", return_value=_fake_identity_with_acteur_ref()),
        patch("candidate_profile.fetch_votes", return_value={}),
        patch("candidate_profile.time.sleep", return_value=None),
        patch("candidate_profile.fetch_activity_synthesis", return_value=None),
        patch("candidate_profile.fetch_dossiers_for_legislatures", return_value=[]),
        patch("candidate_profile.fetch_all_intervention_results_from_domains", return_value=None),
        patch("candidate_profile.fetch_identite_officielle", return_value=None),
        patch("candidate_profile.fetch_positions_hemicycle_officielles", return_value=[]),
        patch("candidate_profile.fetch_votes_officiels", return_value=([], None)),
        patch("candidate_profile.fetch_amendements_officiels", return_value=[]),
        patch("candidate_profile.fetch_textes_portes_officiels", return_value=[]),
        patch("candidate_profile.fetch_interventions_syceron", return_value=fake_syceron),
        patch("candidate_profile.fetch_questions_officielles", return_value=[]),
        # Vérifie que le scraping HTML NosDéputés (fetch_seance_context) n'est jamais appelé.
        patch("candidate_profile.fetch_seance_context") as mock_scraping,
    ):
        raw_profile = build_profile("deputes", "jean-dupont")

    mock_scraping.assert_not_called()

    # L'étape de normalisation transforme les enregistrements bruts Syceron en format pivot.
    pivot = normalize_nosdeputes(raw_profile)

    assert len(pivot["interventions"]) == 3, "Les 3 interventions Syceron doivent être présentes dans le pivot"

    # Intervention 1 — avec seance_ref, session_ref et point_ordre_du_jour
    i1 = pivot["interventions"][0]
    assert i1["theme_officiel"] == "Débat sur le budget rectificatif"
    assert i1["seance"] == {"ref": "RUANR5L17S2025O1N037", "session_ref": "S2024-2025"}
    assert i1["dossier"] == {"point_ordre_du_jour": "Examen du PLFR 2025"}
    assert i1["source"]["type"] == "syceron"
    assert i1["source"]["source_id"] == "CRS17_000001"
    assert i1["source"]["legislature"] == "17"

    # Intervention 2 — avec seance_ref mais sans point_ordre_du_jour
    i2 = pivot["interventions"][1]
    assert i2["theme_officiel"] == "Audition du ministre de l'économie"
    assert i2["seance"]["ref"] == "RUANR5L17S2025O1N041"
    assert i2["dossier"] is None
    assert i2["source"]["type"] == "syceron"

    # Intervention 3 — avec seance_ref et point_ordre_du_jour
    i3 = pivot["interventions"][2]
    assert i3["theme_officiel"] == "Discussion générale sur la réforme des retraites"
    assert i3["seance"]["ref"] == "RUANR5L17S2025O1N055"
    assert i3["dossier"] == {"point_ordre_du_jour": "Réforme des retraites — PL n° 2025-17"}
    assert i3["source"]["type"] == "syceron"


def test_integration_build_profile_fallback_sans_acteur_ref():
    """Intégration bout-en-bout : quand fetch_interventions_syceron retourne une liste vide
    (acteurRef non résolu), le fallback NosDéputés est utilisé et les champs pivot
    Syceron (theme_officiel, seance, source syceron) doivent être absents/null."""
    nosdeputes_intervention = {
        "type": "Intervention",
        "date": "2024-11-15",
        "sujet": "Discussion générale",
        "texte": "Intervention de fallback NosDéputés.",
        "url": "https://www.nosdeputes.fr/jean-dupont/intervention/123",
        "url_detail": "https://www.nosdeputes.fr/jean-dupont/intervention/123",
        "speaker_name": "Jean Dupont",
        "speaker_url": "/jean-dupont",
        "mots_cles": [],
        "source_id": None,
        "seance_ref": None,
        "session_ref": None,
        "point_ordre_du_jour": None,
    }

    with (
        patch("candidate_profile.fetch_identity", return_value=_fake_identity_with_acteur_ref()),
        patch("candidate_profile.fetch_votes", return_value={}),
        patch("candidate_profile.time.sleep", return_value=None),
        patch("candidate_profile.fetch_activity_synthesis", return_value=None),
        patch("candidate_profile.fetch_dossiers_for_legislatures", return_value=[]),
        patch("candidate_profile.fetch_all_intervention_results_from_domains", return_value=None),
        patch("candidate_profile.fetch_identite_officielle", return_value=None),
        patch("candidate_profile.fetch_positions_hemicycle_officielles", return_value=[]),
        patch("candidate_profile.fetch_votes_officiels", return_value=([], None)),
        patch("candidate_profile.fetch_amendements_officiels", return_value=[]),
        patch("candidate_profile.fetch_textes_portes_officiels", return_value=[]),
        # Syceron retourne une liste vide : acteurRef non résolu
        patch("candidate_profile.fetch_interventions_syceron", return_value=[]),
        patch("candidate_profile.fetch_questions_officielles", return_value=[]),
        patch("candidate_profile._extract_search_results", return_value=[nosdeputes_intervention]),
    ):
        raw_profile = build_profile("deputes", "jean-dupont")

    # Un warning de fallback NosDéputés doit être présent
    fallback_warnings = [w for w in raw_profile["meta"]["warnings"] if "fallback" in w.lower()]
    assert fallback_warnings, "Un warning de fallback doit être émis quand Syceron ne retourne rien"

    # Pas de synchro Syceron horodatée
    assert raw_profile["meta"]["synchro_sources"].get("assemblee_nationale_syceron") is None

    # La normalisation ne doit pas produire de champs Syceron
    pivot = normalize_nosdeputes(raw_profile)

    assert len(pivot["interventions"]) == 1
    i = pivot["interventions"][0]
    assert i["theme_officiel"] is None, "theme_officiel doit être null pour une intervention NosDéputés"
    assert i["seance"] is None, "seance doit être null pour une intervention NosDéputés"
    assert i["source"] is None, "source syceron doit être null pour une intervention NosDéputés"


# ---------------------------------------------------------------------------
# Tests pour la non-avalage des échecs de collecte des amendements officiels
# (issue #185 : un échec réseau/zip était indiscernable d'un simple "aucun
# amendement" — aucun warning n'était jamais tracé dans meta.warnings).
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Tests pour la séparation téléchargement/construction vs lecture cache-only
# (issue #250, sous-issue 2/6 de #248) : `_read_cached_amendement_index` ne
# doit jamais déclencher d'appel réseau ; `_download_and_build_amendement_index`
# reprend telle quelle la logique réseau (téléchargement/retry/cache d'échec),
# désormais appelée uniquement par le job dédié `extract-amendements-an`
# (`src/build_amendements_index.py`, #251) — plus par `fetch_amendements_officiels`,
# qui lit exclusivement le cache depuis #252 (sous-issue 4/6 de #248).
# ---------------------------------------------------------------------------

def test_read_cached_amendement_index_returns_none_when_absent(tmp_path):
    """Aucun fichier `index_par_acteur.json` en cache : `None` (pas `{}`, pour
    rester distinguable d'un index vide légitime déjà mis en cache), et aucun
    appel réseau ne doit être déclenché."""
    from candidate_profile import _read_cached_amendement_index

    with (
        patch("candidate_profile.AMENDEMENTS_CACHE_DIR", tmp_path),
        patch("candidate_profile.requests.get") as mock_get,
    ):
        result = _read_cached_amendement_index("17")

    assert result is None
    mock_get.assert_not_called()


def test_read_cached_amendement_index_returns_cached_content(tmp_path):
    """Fichier de cache présent : son contenu est retourné tel quel, sans appel
    réseau."""
    from candidate_profile import _read_cached_amendement_index

    cached_index = {"PA1": [{"uid": "AMANR5L17PO123456B0001P0D1N001"}]}
    index_dir = tmp_path / "17"
    index_dir.mkdir(parents=True)
    (index_dir / "index_par_acteur.json").write_text(
        json.dumps(cached_index, ensure_ascii=False), encoding="utf-8"
    )

    with (
        patch("candidate_profile.AMENDEMENTS_CACHE_DIR", tmp_path),
        patch("candidate_profile.requests.get") as mock_get,
    ):
        result = _read_cached_amendement_index("17")

    assert result == cached_index
    mock_get.assert_not_called()


def test_read_cached_amendement_index_returns_none_on_corrupted_cache(tmp_path):
    """Fichier de cache présent mais illisible (JSON corrompu) : traité comme
    absent (`None`), pas d'exception propagée, aucun appel réseau."""
    from candidate_profile import _read_cached_amendement_index

    index_dir = tmp_path / "17"
    index_dir.mkdir(parents=True)
    (index_dir / "index_par_acteur.json").write_text("{not valid json", encoding="utf-8")

    with (
        patch("candidate_profile.AMENDEMENTS_CACHE_DIR", tmp_path),
        patch("candidate_profile.requests.get") as mock_get,
    ):
        result = _read_cached_amendement_index("17")

    assert result is None
    mock_get.assert_not_called()


def test_download_and_build_amendement_index_ignores_existing_cache_write(tmp_path):
    """`_download_and_build_amendement_index` reprend telle quelle la logique
    réseau : sur un échec de téléchargement, elle lève `AmendementsIndexError`
    et marque la législature en échec (#239/#246), exactement comme
    `_build_acteur_amendement_index` avant le découpage de #250."""
    from candidate_profile import (
        AMENDEMENTS_DOWNLOAD_MAX_ATTEMPTS,
        AmendementsIndexError,
        _download_and_build_amendement_index,
    )

    with (
        patch("candidate_profile.AMENDEMENTS_CACHE_DIR", tmp_path),
        patch("candidate_profile.requests.get", side_effect=_requests.RequestException("boom")) as mock_get,
        patch("candidate_profile.time.sleep", return_value=None),
    ):
        try:
            _download_and_build_amendement_index("17")
            assert False, "AmendementsIndexError attendue"
        except AmendementsIndexError:
            pass

    assert mock_get.call_count == AMENDEMENTS_DOWNLOAD_MAX_ATTEMPTS


# ---------------------------------------------------------------------------
# Tests pour l'indicateur de fraîcheur et la non-régression d'un index déjà en
# cache sur échec définitif de reconstruction (issue #253, sous-issue 5/6 de
# #248) : `_download_and_build_amendement_index` n'ouvre `index_path` en
# écriture qu'après succès complet — un échec, quel qu'il soit, laisse donc
# tel quel un index déjà présent sur disque. `fraicheur.json`, écrit à côté,
# permet de distinguer un index frais d'un index conservé faute de mieux.
# ---------------------------------------------------------------------------

def test_download_and_build_amendement_index_success_writes_fraicheur(tmp_path):
    """Reconstruction réussie : l'index est remplacé et `fraicheur.json` reflète
    le succès avec un horodatage."""
    import io
    import zipfile as zipfile_module

    from candidate_profile import _download_and_build_amendement_index

    buf = io.BytesIO()
    with zipfile_module.ZipFile(buf, "w") as zf:
        pass  # zip valide mais vide : suffisant, ce test porte sur la fraîcheur
    valid_zip_bytes = buf.getvalue()

    class FakeStreamResponse:
        status_code = 200  # fichier entier en un seul segment (voir tests ci-dessus)

        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            return False

        def raise_for_status(self):
            pass

        def iter_content(self, chunk_size=1024 * 1024):
            yield valid_zip_bytes

    with (
        patch("candidate_profile.AMENDEMENTS_CACHE_DIR", tmp_path),
        patch("candidate_profile.requests.get", return_value=FakeStreamResponse()),
        patch("candidate_profile.time.strftime", return_value="2026-08-13T12:00:00+0000"),
    ):
        index = _download_and_build_amendement_index("17")

    assert index == {}
    fraicheur = json.loads((tmp_path / "17" / "fraicheur.json").read_text(encoding="utf-8"))
    assert fraicheur == {
        "derniere_construction_reussie": True,
        "horodatage": "2026-08-13T12:00:00+0000",
    }


def test_download_and_build_amendement_index_failure_preserves_existing_index(tmp_path):
    """Échec définitif sur une législature dont un index existait déjà (ici
    corrompu — seul cas où une reconstruction est réellement retentée malgré
    un fichier déjà présent : un index valide est utilisé tel quel sans
    nouvelle tentative, voir
    `test_download_and_build_amendement_index_uses_existing_cache_without_download`) : le
    fichier existant ne doit être ni supprimé ni remplacé par un résultat
    vide/partiel, et `fraicheur.json` doit refléter l'échec."""
    from candidate_profile import (
        AmendementsIndexError,
        _download_and_build_amendement_index,
    )

    index_dir = tmp_path / "17"
    index_dir.mkdir(parents=True)
    existing_content = "{not valid json"
    (index_dir / "index_par_acteur.json").write_text(existing_content, encoding="utf-8")

    with (
        patch("candidate_profile.AMENDEMENTS_CACHE_DIR", tmp_path),
        patch("candidate_profile.requests.get", side_effect=_requests.RequestException("boom")),
        patch("candidate_profile.time.sleep", return_value=None),
        patch("candidate_profile.time.strftime", return_value="2026-08-13T12:05:00+0000"),
    ):
        try:
            _download_and_build_amendement_index("17")
            assert False, "AmendementsIndexError attendue"
        except AmendementsIndexError:
            pass

    assert (index_dir / "index_par_acteur.json").read_text(encoding="utf-8") == existing_content, (
        "Le fichier existant ne doit jamais être supprimé ni remplacé par un résultat vide/partiel sur échec"
    )
    fraicheur = json.loads((index_dir / "fraicheur.json").read_text(encoding="utf-8"))
    assert fraicheur == {
        "derniere_construction_reussie": False,
        "horodatage": "2026-08-13T12:05:00+0000",
    }


def test_download_and_build_amendement_index_failure_without_existing_index_writes_nothing(tmp_path):
    """Échec définitif sur une législature sans index préexistant : comportement
    actuel inchangé — ni `index_par_acteur.json` ni `fraicheur.json` ne sont
    créés (rien à préserver, pas d'indicateur de fraîcheur à qualifier)."""
    from candidate_profile import AmendementsIndexError, _download_and_build_amendement_index

    with (
        patch("candidate_profile.AMENDEMENTS_CACHE_DIR", tmp_path),
        patch("candidate_profile.requests.get", side_effect=_requests.RequestException("boom")),
        patch("candidate_profile.time.sleep", return_value=None),
    ):
        try:
            _download_and_build_amendement_index("17")
            assert False, "AmendementsIndexError attendue"
        except AmendementsIndexError:
            pass

    index_dir = tmp_path / "17"
    assert not (index_dir / "index_par_acteur.json").exists()
    assert not (index_dir / "fraicheur.json").exists()


def test_download_and_build_amendement_index_already_failed_this_run_preserves_existing_index(tmp_path):
    """Même garantie sur le raccourci `_amendements_legislature_failed_this_run`
    (appel suivant du même run pour une législature déjà en échec définitif) :
    un index corrompu déjà présent est préservé et `fraicheur.json` est
    rafraîchi, sans nouvelle tentative réseau."""
    from candidate_profile import (
        AmendementsIndexError,
        _amendements_failed_legislatures,
        _download_and_build_amendement_index,
    )

    index_dir = tmp_path / "17"
    index_dir.mkdir(parents=True)
    existing_content = "{not valid json"
    (index_dir / "index_par_acteur.json").write_text(existing_content, encoding="utf-8")
    _amendements_failed_legislatures.add("17")

    with (
        patch("candidate_profile.AMENDEMENTS_CACHE_DIR", tmp_path),
        patch("candidate_profile.requests.get") as mock_get,
    ):
        try:
            _download_and_build_amendement_index("17")
            assert False, "AmendementsIndexError attendue"
        except AmendementsIndexError:
            pass

    mock_get.assert_not_called()
    assert (index_dir / "index_par_acteur.json").read_text(encoding="utf-8") == existing_content
    fraicheur = json.loads((index_dir / "fraicheur.json").read_text(encoding="utf-8"))
    assert fraicheur["derniere_construction_reussie"] is False


def test_download_and_build_amendement_index_uses_existing_cache_without_download(tmp_path):
    """`_download_and_build_amendement_index` : quand le cache disque existe déjà
    (double-check en tête, sous le même verrou), il est utilisé tel quel — pas de
    téléchargement."""
    from candidate_profile import _download_and_build_amendement_index

    cached_index = {"PA1": [{"uid": "AMANR5L17PO123456B0001P0D1N001"}]}
    index_dir = tmp_path / "17"
    index_dir.mkdir(parents=True)
    (index_dir / "index_par_acteur.json").write_text(
        json.dumps(cached_index, ensure_ascii=False), encoding="utf-8"
    )

    with (
        patch("candidate_profile.AMENDEMENTS_CACHE_DIR", tmp_path),
        patch("candidate_profile.requests.get") as mock_get,
    ):
        result = _download_and_build_amendement_index("17")

    assert result == cached_index
    mock_get.assert_not_called()


# ---------------------------------------------------------------------------
# Législatures figées (15/16) : fallback committé, aucun accès réseau
# (docs/technical_decisions.md#amendements-legislatures-figees).
# ---------------------------------------------------------------------------

def test_download_and_build_amendement_index_uses_frozen_fallback_without_download(tmp_path):
    """Pour une législature dans `AN_AMENDEMENTS_LEGISLATURES_FIGEES`, l'index
    committé (`AN_AMENDEMENTS_FIGEES_DIR`, sous forme dédupliquée
    `amendements.json` + `index_par_acteur.json` allégé — voir
    `_aggregate_amendements_index`) est utilisé sans jamais toucher le réseau,
    même en l'absence de tout cache disque préexistant, et reconstruit sous la
    forme plate standard avant matérialisation dans le cache."""
    from candidate_profile import _download_and_build_amendement_index

    frozen_amendements = {
        "AMANR5L15PO123456B0001P0D1N001": {
            "texte_vise": "PRJLANR5L15B0001",
            "sort": None,
            "base_juridique_irrecevabilite": None,
            "premier_signataire": "an:PA1",
            "co_signataires": [],
            "type_deposant": None,
            "date": "2018-01-01",
            "numero": "AMANR5L15PO123456B0001P0D1N001",
            "source_url": None,
        }
    }
    frozen_index_par_acteur = {
        "PA1": [{"numero": "AMANR5L15PO123456B0001P0D1N001", "role_signataire": "auteur_principal"}]
    }
    expected_index = {
        "PA1": [
            {
                **frozen_amendements["AMANR5L15PO123456B0001P0D1N001"],
                "role_signataire": "auteur_principal",
            }
        ]
    }
    frozen_dir = tmp_path / "figees" / "15"
    frozen_dir.mkdir(parents=True)
    (frozen_dir / "amendements.json").write_text(
        json.dumps(frozen_amendements, ensure_ascii=False), encoding="utf-8"
    )
    (frozen_dir / "index_par_acteur.json").write_text(
        json.dumps(frozen_index_par_acteur, ensure_ascii=False), encoding="utf-8"
    )
    (frozen_dir / "fraicheur.json").write_text(
        json.dumps({"derniere_construction_reussie": True, "horodatage": "2026-08-13T00:00:00+0000", "figee": True}),
        encoding="utf-8",
    )

    cache_dir = tmp_path / "cache"
    with (
        patch("candidate_profile.AMENDEMENTS_CACHE_DIR", cache_dir),
        patch("candidate_profile.AN_AMENDEMENTS_FIGEES_DIR", tmp_path / "figees"),
        patch("candidate_profile.requests.get") as mock_get,
    ):
        result = _download_and_build_amendement_index("15")

    assert result == expected_index
    mock_get.assert_not_called()
    # Matérialisé dans le cache disque standard, sous forme plate (même format
    # qu'une construction réseau), pas la forme dédupliquée committée.
    assert json.loads((cache_dir / "15" / "index_par_acteur.json").read_text(encoding="utf-8")) == expected_index
    assert json.loads((cache_dir / "15" / "fraicheur.json").read_text(encoding="utf-8"))["figee"] is True


def test_download_and_build_amendement_index_frozen_legislature_falls_back_to_network_if_no_committed_index(tmp_path):
    """Une législature figée sans fallback committé (ne devrait pas arriver en
    pratique) ne doit pas lever : elle retombe simplement sur le chemin réseau
    standard, qui échoue ici normalement (aucune archive servie)."""
    from candidate_profile import AmendementsIndexError, _download_and_build_amendement_index

    with (
        patch("candidate_profile.AMENDEMENTS_CACHE_DIR", tmp_path / "cache"),
        patch("candidate_profile.AN_AMENDEMENTS_FIGEES_DIR", tmp_path / "figees_absent"),
        patch("candidate_profile.requests.get", side_effect=_requests.RequestException("boom")) as mock_get,
        patch("candidate_profile.time.sleep", return_value=None),
    ):
        try:
            _download_and_build_amendement_index("15")
            assert False, "AmendementsIndexError attendue"
        except AmendementsIndexError:
            pass

    mock_get.assert_called()


def test_download_and_build_amendement_index_raises_on_download_failure(tmp_path):
    """Échec persistant (toutes les tentatives échouent) : AmendementsIndexError
    doit toujours être levée après épuisement des tentatives (non-régression #199),
    et toutes les tentatives prévues doivent avoir été consommées."""
    from candidate_profile import (
        AMENDEMENTS_DOWNLOAD_MAX_ATTEMPTS,
        AmendementsIndexError,
        _download_and_build_amendement_index,
    )

    with (
        patch("candidate_profile.AMENDEMENTS_CACHE_DIR", tmp_path),
        patch("candidate_profile.requests.get", side_effect=_requests.RequestException("boom")) as mock_get,
        patch("candidate_profile.time.sleep", return_value=None) as mock_sleep,
    ):
        try:
            _download_and_build_amendement_index("17")
            assert False, "AmendementsIndexError attendue"
        except AmendementsIndexError:
            pass

    assert mock_get.call_count == AMENDEMENTS_DOWNLOAD_MAX_ATTEMPTS, (
        "Le téléchargement doit être retenté jusqu'à épuisement du nombre de tentatives borné"
    )
    # Backoff entre chaque tentative, mais pas après la dernière (déjà en échec définitif).
    assert mock_sleep.call_count == AMENDEMENTS_DOWNLOAD_MAX_ATTEMPTS - 1


def test_download_and_build_amendement_index_failed_legislature_is_not_retried_for_next_candidate(tmp_path):
    """Une législature dont le téléchargement échoue définitivement (toutes les
    tentatives épuisées) ne doit être retentée qu'une seule fois par run — pas
    une fois par appelant suivant en ayant besoin (issue #239 : régression de
    #225, où l'absence de mémoire inter-appels d'un échec transformait un
    échec instantané pré-#225 en plusieurs minutes de blocage répétées)."""
    from candidate_profile import (
        AMENDEMENTS_DOWNLOAD_MAX_ATTEMPTS,
        AmendementsIndexError,
        _download_and_build_amendement_index,
    )

    with (
        patch("candidate_profile.AMENDEMENTS_CACHE_DIR", tmp_path),
        patch("candidate_profile.requests.get", side_effect=_requests.RequestException("boom")) as mock_get,
        patch("candidate_profile.time.sleep", return_value=None),
    ):
        # Premier appel ayant besoin de cette législature : cycle complet de
        # tentatives (comportement de #225 préservé), puis échec définitif.
        try:
            _download_and_build_amendement_index("17")
            assert False, "AmendementsIndexError attendue"
        except AmendementsIndexError:
            pass
        assert mock_get.call_count == AMENDEMENTS_DOWNLOAD_MAX_ATTEMPTS

        # Second appel, même législature : échec immédiat depuis le cache
        # d'échec, sans aucun nouvel appel réseau.
        try:
            _download_and_build_amendement_index("17")
            assert False, "AmendementsIndexError attendue"
        except AmendementsIndexError:
            pass
        assert mock_get.call_count == AMENDEMENTS_DOWNLOAD_MAX_ATTEMPTS, (
            "Le second appel ne doit déclencher aucun nouvel appel réseau pour "
            "une législature déjà en échec définitif durant ce run"
        )


def test_download_and_build_amendement_index_failed_legislature_shared_across_jobs_via_disk_marker(tmp_path, monkeypatch):
    """Deux process Python distincts du même run (ex. deux invocations
    successives de `src/build_amendements_index.py` dans le job
    `extract-amendements-an`, ou une reprise du même run) ne doivent pas payer
    chacune le cycle complet de retry pour la même législature en échec : la
    seconde doit lever immédiatement grâce au marqueur disque partagé
    (`GITHUB_RUN_ID`), même sans mémoire process partagée (issue #246,
    extension de #239 au-delà du process courant)."""
    from candidate_profile import (
        AMENDEMENTS_DOWNLOAD_MAX_ATTEMPTS,
        AmendementsIndexError,
        _amendements_failed_legislatures,
        _download_and_build_amendement_index,
    )

    monkeypatch.setenv("GITHUB_RUN_ID", "31685914622")

    with (
        patch("candidate_profile.AMENDEMENTS_CACHE_DIR", tmp_path),
        patch("candidate_profile.requests.get", side_effect=_requests.RequestException("boom")) as mock_get,
        patch("candidate_profile.time.sleep", return_value=None),
    ):
        # Premier process : cycle complet de tentatives, échec définitif.
        try:
            _download_and_build_amendement_index("17")
            assert False, "AmendementsIndexError attendue"
        except AmendementsIndexError:
            pass
        assert mock_get.call_count == AMENDEMENTS_DOWNLOAD_MAX_ATTEMPTS

        # Simule le passage à un second process (ex. reprise du même run) : le
        # cache mémoire intra-process est réinitialisé, mais le cache disque
        # (`.cache/amendements_an/`) est le même.
        _amendements_failed_legislatures.clear()

        try:
            _download_and_build_amendement_index("17")
            assert False, "AmendementsIndexError attendue"
        except AmendementsIndexError:
            pass
        assert mock_get.call_count == AMENDEMENTS_DOWNLOAD_MAX_ATTEMPTS, (
            "Le second process ne doit déclencher aucun nouvel appel réseau : le marqueur "
            "disque du run courant doit suffire à lever immédiatement"
        )


def test_download_and_build_amendement_index_disk_marker_from_different_run_is_ignored(tmp_path, monkeypatch):
    """Un marqueur disque référençant un `GITHUB_RUN_ID` différent du run courant
    (résidu d'une semaine ISO précédente restauré via `restore-keys`) doit être
    ignoré : la législature est retentée normalement, sans dépendre d'un TTL
    explicite (comportement de #239 volontairement préservé, critère
    d'acceptation de #246)."""
    from candidate_profile import (
        AMENDEMENTS_DOWNLOAD_MAX_ATTEMPTS,
        AmendementsIndexError,
        _amendements_failed_marker_path,
        _download_and_build_amendement_index,
    )

    monkeypatch.setenv("GITHUB_RUN_ID", "31694500982")

    marker_path = _amendements_failed_marker_path("17")
    with patch("candidate_profile.AMENDEMENTS_CACHE_DIR", tmp_path):
        marker_path.parent.mkdir(parents=True, exist_ok=True)
        marker_path.write_text("99999999999", encoding="utf-8")  # run_id d'un run précédent

        with (
            patch("candidate_profile.requests.get", side_effect=_requests.RequestException("boom")) as mock_get,
            patch("candidate_profile.time.sleep", return_value=None),
        ):
            try:
                _download_and_build_amendement_index("17")
                assert False, "AmendementsIndexError attendue (échec réseau simulé, pas le marqueur périmé)"
            except AmendementsIndexError:
                pass

    assert mock_get.call_count == AMENDEMENTS_DOWNLOAD_MAX_ATTEMPTS, (
        "Un marqueur d'un GITHUB_RUN_ID différent doit être ignoré : cycle complet de "
        "tentatives réseau attendu, pas un échec immédiat depuis le marqueur périmé"
    )


def test_download_and_build_amendement_index_retries_transient_failure_then_succeeds(tmp_path):
    """Un échec réseau transitoire isolé (ex. un seul IncompleteRead/RequestException)
    ne doit plus faire échouer la construction de l'index si une tentative suivante
    aboutit — c'est le comportement central demandé par #220."""
    import io
    import zipfile as zipfile_module

    from candidate_profile import _download_and_build_amendement_index

    buf = io.BytesIO()
    with zipfile_module.ZipFile(buf, "w") as zf:
        pass  # zip valide mais vide : suffisant pour vérifier l'absence d'erreur
    valid_zip_bytes = buf.getvalue()

    class FakeStreamResponse:
        # status_code=200 (au lieu de 206) simule un serveur qui ignore l'en-tête
        # Range et renvoie le fichier entier en un seul segment — suffisant ici
        # puisque ce test porte sur le retry transitoire, pas sur le découpage
        # par plages (voir test_download_amendements_zip_retries_only_failed_segment
        # pour le retry ciblé d'un seul segment médian).
        status_code = 200

        def __init__(self, payload: bytes):
            self._payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            return False

        def raise_for_status(self):
            pass

        def iter_content(self, chunk_size=1024 * 1024):
            yield self._payload

    with (
        patch("candidate_profile.AMENDEMENTS_CACHE_DIR", tmp_path),
        patch(
            "candidate_profile.requests.get",
            side_effect=[
                _requests.RequestException("IncompleteRead(16779130 bytes read, 346527232 more expected)"),
                FakeStreamResponse(valid_zip_bytes),
            ],
        ) as mock_get,
        patch("candidate_profile.time.sleep", return_value=None) as mock_sleep,
    ):
        index = _download_and_build_amendement_index("17")

    assert index == {}
    assert mock_get.call_count == 2, "Un seul échec transitoire suivi d'un succès : exactement 2 tentatives"
    assert mock_sleep.call_count == 1, "Backoff attendu une seule fois, entre l'échec et la tentative réussie"


def test_download_and_build_amendement_index_raises_on_bad_zip(tmp_path):
    import zipfile

    from candidate_profile import AmendementsIndexError, _download_and_build_amendement_index

    class FakeStreamResponse:
        status_code = 200  # fichier entier en un seul segment, voir commentaire ci-dessus

        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            return False

        def raise_for_status(self):
            pass

        def iter_content(self, chunk_size=1024 * 1024):
            yield b"not a valid zip archive"

    with (
        patch("candidate_profile.AMENDEMENTS_CACHE_DIR", tmp_path),
        patch("candidate_profile.requests.get", return_value=FakeStreamResponse()),
    ):
        try:
            _download_and_build_amendement_index("17")
            assert False, "AmendementsIndexError attendue"
        except AmendementsIndexError:
            pass
        except zipfile.BadZipFile:
            assert False, "BadZipFile ne doit pas être avalée : elle doit être reconvertie en AmendementsIndexError"


def test_download_amendements_zip_retries_only_failed_segment(tmp_path):
    """Une coupure mi-flux sur un segment ne doit retenter que ce segment — pas
    tout le fichier (critère d'acceptation de l'issue #241)."""
    from candidate_profile import _download_amendements_zip

    payload = b"0123456789AB"  # 12 octets, découpés en segments de 4 -> 3 segments
    calls: list[str] = []

    class FakeRangeResponse:
        def __init__(self, data: bytes, total: int):
            self._data = data
            self.status_code = 206
            self.headers = {"Content-Range": f"bytes 0-0/{total}"}

        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            return False

        def raise_for_status(self):
            pass

        def iter_content(self, chunk_size=1024 * 1024):
            yield self._data

    def fake_get(url, headers=None, timeout=None, stream=None):
        range_value = headers["Range"]
        calls.append(range_value)
        start, end = (int(x) for x in range_value.removeprefix("bytes=").split("-"))
        end = min(end, len(payload) - 1)
        # Échec transitoire simulé une seule fois, sur le segment médian (offset 4).
        if start == 4 and calls.count("bytes=4-7") == 1:
            raise _requests.RequestException("IncompleteRead simulée mi-segment")
        return FakeRangeResponse(payload[start : end + 1], len(payload))

    with (
        patch("candidate_profile.AMENDEMENTS_DOWNLOAD_CHUNK_BYTES", 4),
        patch("candidate_profile.requests.get", side_effect=fake_get),
        patch("candidate_profile.time.sleep", return_value=None),
    ):
        zip_path = tmp_path / "amendements.zip"
        _download_amendements_zip("https://example.test/amendements.zip", zip_path, "17")

    assert zip_path.read_bytes() == payload, "Le fichier reconstitué doit être identique octet pour octet"
    assert calls.count("bytes=0-3") == 1, "Le premier segment (déjà réussi) ne doit pas être re-demandé"
    assert calls.count("bytes=4-7") == 2, "Seul le segment en échec doit être retenté"
    assert calls.count("bytes=8-11") == 1, "Le dernier segment ne doit être demandé qu'une fois"


def test_fetch_amendements_officiels_legislature_failure_does_not_erase_others():
    """Légis 17 en cache + légis 16/15 absentes du cache : les amendements de la
    légis 17 doivent être conservés (plus de vidage global sur l'absence d'une
    seule législature), et chaque absence doit être tracée avec la législature
    concernée dans les warnings (critères d'acceptation de l'issue #241,
    adaptés à la lecture cache-only de #252 : plus d'`AmendementsIndexError`,
    une législature absente du cache retourne simplement `None`)."""
    from candidate_profile import (
        WARNING_PREFIX_AMENDEMENTS_INDISPONIBLES,
        fetch_amendements_officiels,
    )

    def fake_index(legislature):
        if legislature == "17":
            return {"PA1": [{"numero": "1", "date": "2024-01-01", "texte_vise": "T1", "sort": None}]}
        return None

    warnings: list[str] = []
    with (
        patch("candidate_profile._read_cached_amendement_index", side_effect=fake_index),
        patch("candidate_profile._build_texte_titre_index", return_value={}),
        patch("candidate_profile._extract_acteur_ref", return_value="PA1"),
    ):
        amendements = fetch_amendements_officiels("https://www.assemblee-nationale.fr/dyn/deputes/PA1", warnings)

    assert len(amendements) == 1, "Les amendements de la législature en cache (17) doivent être conservés"
    assert amendements[0]["legislature"] == "17"

    failure_warnings = [w for w in warnings if w.startswith(WARNING_PREFIX_AMENDEMENTS_INDISPONIBLES)]
    assert len(failure_warnings) == 2, "Un warning distinct par législature absente (16 et 15), pas un échec global"
    assert any("16" in w for w in failure_warnings), "Le warning doit mentionner spécifiquement la législature 16"
    assert any("15" in w for w in failure_warnings), "La légis 15 doit être tentée même quand la légis 16 est absente"


def test_fetch_amendements_officiels_never_triggers_network_when_cache_absent(tmp_path):
    """Critère d'acceptation central de l'issue #252 : quand l'index en cache est
    absent pour toutes les législatures, `fetch_amendements_officiels` ne doit
    déclencher aucun appel réseau (mocké) — seulement le warning existant."""
    from candidate_profile import (
        AN_AMENDEMENTS_PATH,
        WARNING_PREFIX_AMENDEMENTS_INDISPONIBLES,
        fetch_amendements_officiels,
    )

    warnings: list[str] = []
    with (
        patch("candidate_profile.AMENDEMENTS_CACHE_DIR", tmp_path),
        patch("candidate_profile.requests.get") as mock_get,
        patch("candidate_profile._extract_acteur_ref", return_value="PA1"),
    ):
        amendements = fetch_amendements_officiels("https://www.assemblee-nationale.fr/dyn/deputes/PA1", warnings)

    assert amendements == []
    mock_get.assert_not_called()
    failure_warnings = [w for w in warnings if w.startswith(WARNING_PREFIX_AMENDEMENTS_INDISPONIBLES)]
    assert len(failure_warnings) == len(AN_AMENDEMENTS_PATH), (
        "Un warning par législature absente du cache, aucune tentative réseau"
    )


def test_fetch_amendements_officiels_returns_cached_amendements_when_index_present(tmp_path):
    """Quand l'index est présent en cache pour une législature, les amendements
    de l'acteur doivent être retournés — identique au comportement actuel,
    sans passer par un téléchargement (critère d'acceptation de l'issue #252)."""
    from candidate_profile import AN_AMENDEMENTS_PATH as _LEGISLATURES
    from candidate_profile import fetch_amendements_officiels

    legislature = next(iter(_LEGISLATURES))
    cached_index = {
        "PA1": [{"numero": "1", "date": "2024-01-01", "texte_vise": "T1", "sort": None}],
    }
    index_dir = tmp_path / legislature
    index_dir.mkdir(parents=True)
    (index_dir / "index_par_acteur.json").write_text(
        json.dumps(cached_index, ensure_ascii=False), encoding="utf-8"
    )

    warnings: list[str] = []
    with (
        patch("candidate_profile.AMENDEMENTS_CACHE_DIR", tmp_path),
        patch("candidate_profile.requests.get") as mock_get,
        patch("candidate_profile._extract_acteur_ref", return_value="PA1"),
        patch("candidate_profile._build_texte_titre_index", return_value={}),
    ):
        amendements = fetch_amendements_officiels("https://www.assemblee-nationale.fr/dyn/deputes/PA1", warnings)

    mock_get.assert_not_called()
    matching = [a for a in amendements if a["legislature"] == legislature]
    assert len(matching) == 1
    assert matching[0]["numero"] == "1"


def test_build_profile_amendements_fetch_failure_is_tracked_in_warnings():
    """Quand fetch_amendements_officiels échoue de façon inattendue (ex. exception
    propagée), le try/except de build_profile doit ajouter un warning
    WARNING_PREFIX_AMENDEMENTS_INDISPONIBLES — au lieu de silencieusement laisser
    profile['amendements'] absent/vide sans trace."""
    from candidate_profile import AmendementsIndexError, WARNING_PREFIX_AMENDEMENTS_INDISPONIBLES

    with (
        patch("candidate_profile.fetch_identity", return_value=_fake_identity_with_acteur_ref()),
        patch("candidate_profile.fetch_votes", return_value={}),
        patch("candidate_profile.time.sleep", return_value=None),
        patch("candidate_profile.fetch_activity_synthesis", return_value=None),
        patch("candidate_profile.fetch_dossiers_for_legislatures", return_value=[]),
        patch("candidate_profile.fetch_all_intervention_results_from_domains", return_value=None),
        patch("candidate_profile.fetch_identite_officielle", return_value=None),
        patch("candidate_profile.fetch_positions_hemicycle_officielles", return_value=[]),
        patch("candidate_profile.fetch_votes_officiels", return_value=([], None)),
        patch(
            "candidate_profile.fetch_amendements_officiels",
            side_effect=AmendementsIndexError("échec du téléchargement (boom)"),
        ),
        patch("candidate_profile.fetch_textes_portes_officiels", return_value=[]),
        patch("candidate_profile.fetch_interventions_syceron", return_value=[]),
        patch("candidate_profile.fetch_questions_officielles", return_value=[]),
        patch("candidate_profile._extract_search_results", return_value=[]),
    ):
        raw_profile = build_profile("deputes", "jean-dupont")

    amendements_warnings = [
        w for w in raw_profile["meta"]["warnings"] if w.startswith(WARNING_PREFIX_AMENDEMENTS_INDISPONIBLES)
    ]
    assert amendements_warnings, (
        "Un échec de collecte des amendements officiels doit être tracé dans meta.warnings, "
        "pas avalé silencieusement"
    )
