import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from parse_syceron import parse_syceron_xml

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _load(filename: str) -> bytes:
    return (FIXTURES / filename).read_bytes()


# ---------------------------------------------------------------------------
# Fixture: syceron_minimal.xml
# Compte rendu complet (etat=complet, version=JO) avec 3 interventions :
#   point 1 "Questions au Gouvernement" → 2 paragraphes avec orateurs
#   point 2 "Discussion générale…"      → 1 paragraphe avec orateur
# ---------------------------------------------------------------------------

def test_minimal_seance_uid():
    result = parse_syceron_xml(_load("syceron_minimal.xml"))
    assert result["seance"]["uid"] == "CRSANR5L17S2025O1N037"


def test_minimal_seance_ref():
    result = parse_syceron_xml(_load("syceron_minimal.xml"))
    assert result["seance"]["seance_ref"] == "RUANR5L17S2025IDS28624"


def test_minimal_session_ref():
    result = parse_syceron_xml(_load("syceron_minimal.xml"))
    assert result["seance"]["session_ref"] == "SCR5A2025O1"


def test_minimal_date_iso():
    result = parse_syceron_xml(_load("syceron_minimal.xml"))
    assert result["seance"]["date"] == "2025-02-11"


def test_minimal_legislature():
    result = parse_syceron_xml(_load("syceron_minimal.xml"))
    assert result["seance"]["legislature"] == "17"


def test_minimal_numero_seance():
    result = parse_syceron_xml(_load("syceron_minimal.xml"))
    assert result["seance"]["numero_seance"] == "037"


def test_minimal_etat():
    result = parse_syceron_xml(_load("syceron_minimal.xml"))
    assert result["seance"]["etat"] == "complet"


def test_minimal_version():
    result = parse_syceron_xml(_load("syceron_minimal.xml"))
    assert result["seance"]["version"] == "JO"


def test_minimal_interventions_count():
    result = parse_syceron_xml(_load("syceron_minimal.xml"))
    assert len(result["interventions"]) == 3


def test_minimal_intervention_date_propagee():
    result = parse_syceron_xml(_load("syceron_minimal.xml"))
    for i in result["interventions"]:
        assert i["date"] == "2025-02-11"


def test_minimal_intervention_source_id_propagee():
    result = parse_syceron_xml(_load("syceron_minimal.xml"))
    for i in result["interventions"]:
        assert i["source_id"] == "CRSANR5L17S2025O1N037"


def test_minimal_premier_point_type_detail():
    result = parse_syceron_xml(_load("syceron_minimal.xml"))
    assert result["interventions"][0]["type_detail"] == "question_gouvernement"


def test_minimal_premier_point_sujet():
    result = parse_syceron_xml(_load("syceron_minimal.xml"))
    assert result["interventions"][0]["sujet"] == "Questions au Gouvernement"


def test_minimal_premier_orateur_id():
    result = parse_syceron_xml(_load("syceron_minimal.xml"))
    assert result["interventions"][0]["orateur_id_source"] == "PA123456"


def test_minimal_premier_orateur_nom():
    result = parse_syceron_xml(_load("syceron_minimal.xml"))
    assert result["interventions"][0]["orateur_nom"] == "Jean Dupont"


def test_minimal_premier_orateur_fonction():
    result = parse_syceron_xml(_load("syceron_minimal.xml"))
    assert result["interventions"][0]["fonction"] == "député"


def test_minimal_deuxieme_orateur_qualite_rapporteure():
    result = parse_syceron_xml(_load("syceron_minimal.xml"))
    assert result["interventions"][1]["fonction"] == "Rapporteure générale"


def test_minimal_texte_non_nul():
    result = parse_syceron_xml(_load("syceron_minimal.xml"))
    assert result["interventions"][0]["texte"] is not None
    assert len(result["interventions"][0]["texte"]) > 10


def test_minimal_troisieme_intervention_type_detail_loi():
    result = parse_syceron_xml(_load("syceron_minimal.xml"))
    assert result["interventions"][2]["type_detail"] == "loi"


def test_minimal_troisieme_intervention_br_inline_normalise():
    """La balise <br/> dans le texte doit être normalisée (remplacée par espace)."""
    result = parse_syceron_xml(_load("syceron_minimal.xml"))
    texte = result["interventions"][2]["texte"]
    assert texte is not None
    assert "<br" not in texte


def test_minimal_format_prise_developpee():
    result = parse_syceron_xml(_load("syceron_minimal.xml"))
    # La 3e intervention est longue → format développé
    assert result["interventions"][2]["format"] == "prise_de_parole_developpee"


def test_minimal_format_reaction_courte():
    result = parse_syceron_xml(_load("syceron_minimal.xml"))
    # La 1re intervention est courte → reaction_courte ou prise_developpee selon longueur
    # On vérifie simplement que le champ est l'une des deux valeurs attendues.
    assert result["interventions"][0]["format"] in ("reaction_courte", "prise_de_parole_developpee")


def test_minimal_mots_cles_liste_vide():
    result = parse_syceron_xml(_load("syceron_minimal.xml"))
    for i in result["interventions"]:
        assert i["mots_cles"] == []


def test_minimal_source_url_none():
    result = parse_syceron_xml(_load("syceron_minimal.xml"))
    for i in result["interventions"]:
        assert i["source_url"] is None


def test_minimal_etat_compte_rendu_propagee():
    result = parse_syceron_xml(_load("syceron_minimal.xml"))
    for i in result["interventions"]:
        assert i["etat_compte_rendu"] == "complet"


def test_minimal_version_compte_rendu_propagee():
    result = parse_syceron_xml(_load("syceron_minimal.xml"))
    for i in result["interventions"]:
        assert i["version_compte_rendu"] == "JO"


def test_minimal_point_ordre_du_jour_propagee():
    result = parse_syceron_xml(_load("syceron_minimal.xml"))
    assert result["interventions"][0]["point_ordre_du_jour"] == "Questions au Gouvernement"
    assert result["interventions"][2]["point_ordre_du_jour"] == "Discussion générale sur le projet de loi de finances pour 2025"


# ---------------------------------------------------------------------------
# Fixture: syceron_missing_fields.xml
# Compte rendu provisoire (avant_JO), champs manquants variés :
#   point 1 : pas de titreStruct, paragraphe avec orateur sans qualite
#   point 2 : titre présent, paragraphes sans orateur ou orateurs vide
#   point 3 : titre présent, paragraphe avec orateur mais sans texte
# ---------------------------------------------------------------------------

def test_missing_seance_uid():
    result = parse_syceron_xml(_load("syceron_missing_fields.xml"))
    assert result["seance"]["uid"] == "CRSANR5L17S2025O1N079"


def test_missing_seance_ref_none():
    result = parse_syceron_xml(_load("syceron_missing_fields.xml"))
    assert result["seance"]["seance_ref"] is None


def test_missing_session_ref_none():
    result = parse_syceron_xml(_load("syceron_missing_fields.xml"))
    assert result["seance"]["session_ref"] is None


def test_missing_date_iso():
    result = parse_syceron_xml(_load("syceron_missing_fields.xml"))
    assert result["seance"]["date"] == "2025-03-18"


def test_missing_etat_provisoire():
    result = parse_syceron_xml(_load("syceron_missing_fields.xml"))
    assert result["seance"]["etat"] == "provisoire"


def test_missing_version_avant_jo():
    result = parse_syceron_xml(_load("syceron_missing_fields.xml"))
    assert result["seance"]["version"] == "avant_JO"


def test_missing_orateur_qualite_none_si_absent():
    """Un orateur sans <qualite> doit avoir fonction=None (pas "")."""
    result = parse_syceron_xml(_load("syceron_missing_fields.xml"))
    # Premier paragraphe du point 1 : orateur sans qualite
    inter = next(i for i in result["interventions"] if i["orateur_id_source"] == "PA999999")
    assert inter["fonction"] is None


def test_missing_sujet_none_si_pas_titrestruct():
    """Un point sans titreStruct doit produire sujet=None."""
    result = parse_syceron_xml(_load("syceron_missing_fields.xml"))
    inter = next(i for i in result["interventions"] if i["orateur_id_source"] == "PA999999")
    assert inter["sujet"] is None


def test_missing_type_detail_debat_si_pas_titre():
    """Sans titre, type_detail doit être "debat"."""
    result = parse_syceron_xml(_load("syceron_missing_fields.xml"))
    inter = next(i for i in result["interventions"] if i["orateur_id_source"] == "PA999999")
    assert inter["type_detail"] == "debat"


def test_missing_paragraphe_sans_orateur_retenu_si_texte():
    """Paragraphe sans orateur mais avec texte → intervention retenue (orateur_id_source=None)."""
    result = parse_syceron_xml(_load("syceron_missing_fields.xml"))
    no_orateur = [i for i in result["interventions"] if i["orateur_id_source"] is None and i["texte"] is not None]
    assert len(no_orateur) >= 1


def test_missing_orateur_id_none_si_absent():
    """Les interventions sans orateur doivent avoir orateur_nom=None aussi."""
    result = parse_syceron_xml(_load("syceron_missing_fields.xml"))
    no_orateur = [i for i in result["interventions"] if i["orateur_id_source"] is None]
    assert len(no_orateur) >= 1
    for i in no_orateur:
        assert i["orateur_nom"] is None


def test_missing_paragraphe_texte_none_avec_orateur():
    """Paragraphe avec orateur mais sans texte → texte=None, intervention retenue."""
    result = parse_syceron_xml(_load("syceron_missing_fields.xml"))
    inter = next(i for i in result["interventions"] if i["orateur_id_source"] == "PA111111")
    assert inter["texte"] is None
    assert inter["orateur_nom"] == "Sophie Bernard"


def test_missing_aucun_champ_chaine_vide():
    """Aucun champ scalaire ne doit être une chaîne vide."""
    result = parse_syceron_xml(_load("syceron_missing_fields.xml"))
    scalar_keys = ("date", "type_detail", "sujet", "texte", "fonction",
                   "source_id", "seance_ref", "session_ref",
                   "orateur_id_source", "orateur_nom", "point_ordre_du_jour",
                   "etat_compte_rendu", "version_compte_rendu")
    for inter in result["interventions"]:
        for key in scalar_keys:
            val = inter.get(key)
            assert val != "", f"Champ '{key}' ne doit pas être une chaîne vide"


# ---------------------------------------------------------------------------
# Robustesse : XML minimal sans contenu
# ---------------------------------------------------------------------------

def test_xml_sans_contenu_retourne_liste_vide():
    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<compteRendu xmlns="http://schemas.assemblee-nationale.fr/referentiel">
  <uid>CRSANR5L17TEST</uid>
  <metadonnees>
    <dateSeance>20250101000000000</dateSeance>
    <legislature>17</legislature>
    <etat>complet</etat>
    <version>JO</version>
  </metadonnees>
</compteRendu>"""
    result = parse_syceron_xml(xml)
    assert result["interventions"] == []
    assert result["seance"]["uid"] == "CRSANR5L17TEST"


def test_xml_accepts_str_input():
    xml_str = """<?xml version="1.0" encoding="UTF-8"?>
<compteRendu xmlns="http://schemas.assemblee-nationale.fr/referentiel">
  <uid>CRSTEST</uid>
  <metadonnees><dateSeance>20260101</dateSeance></metadonnees>
</compteRendu>"""
    result = parse_syceron_xml(xml_str)
    assert result["seance"]["uid"] == "CRSTEST"


def test_multiple_orateurs_distincts_are_treated_as_ambiguous():
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<compteRendu xmlns="http://schemas.assemblee-nationale.fr/referentiel">
  <uid>CRSTEST-AMBIGU</uid>
  <metadonnees><dateSeance>20260101</dateSeance></metadonnees>
  <contenu>
    <point>
      <titreStruct><intitule>Discussion generale</intitule></titreStruct>
      <paragraphe>
        <orateurs>
          <orateur><id>PA1</id><nom>Jean Dupont</nom></orateur>
          <orateur><id>PA2</id><nom>Jeanne Martin</nom></orateur>
        </orateurs>
        <texte>Texte attribuable sans ambiguïté impossible.</texte>
      </paragraphe>
    </point>
  </contenu>
</compteRendu>""".encode("utf-8")
    result = parse_syceron_xml(xml)
    assert len(result["interventions"]) == 1
    assert result["interventions"][0]["orateur_id_source"] is None
    assert result["interventions"][0]["orateur_nom"] is None


def test_xml_malformed_raises():
    import xml.etree.ElementTree as ET
    with pytest.raises(ET.ParseError):
        parse_syceron_xml(b"<not valid xml")
