import sys
from pathlib import Path
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from parse_syceron import parse_syceron

FIXTURES = Path(__file__).resolve().parent / "fixtures"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load(name: str) -> list[dict]:
    return parse_syceron(FIXTURES / name)


# ---------------------------------------------------------------------------
# Tests — fixture : séance complète
# ---------------------------------------------------------------------------

def test_seance_complete_nombre_interventions():
    """Quatre paragraphes déclarés, un sans <orateur> → 3 interventions retournées."""
    result = _load("syceron_seance_complete.xml")
    assert len(result) == 3


def test_seance_complete_metadonnees():
    """Les métadonnées de séance doivent être présentes sur chaque intervention."""
    result = _load("syceron_seance_complete.xml")
    for item in result:
        assert item["date"] == "2024-10-15"
        assert item["numero_seance"] == "042"
        assert item["legislature"] == "17"
        assert item["session"] == "ordinaire 2024-2025"


def test_seance_complete_premier_orateur():
    """Vérification des champs orateur sur la première intervention."""
    item = _load("syceron_seance_complete.xml")[0]
    assert item["acteur_ref"] == "PA794412"
    assert item["prenom_nom"] == "Jean Dupont"
    assert item["qualite"] == "député"


def test_seance_complete_texte_premier_orateur():
    """Le texte doit être extrait et normalisé."""
    item = _load("syceron_seance_complete.xml")[0]
    assert item["texte"] is not None
    assert "collectivités territoriales" in item["texte"]


def test_seance_complete_contexte_point_odj():
    """Les signaux de contexte ODJ doivent être propagés sur chaque paragraphe du point."""
    result = _load("syceron_seance_complete.xml")
    # Les deux premiers items appartiennent au premier point ODJ
    assert result[0]["titre_point"] == "Projet de loi de finances pour 2025"
    assert result[0]["dossier_ref"] == "PLFR5L17B0512"
    assert result[0]["thematique_ref"] == "budget"
    assert result[1]["titre_point"] == "Projet de loi de finances pour 2025"


def test_seance_complete_second_point_odj():
    """Le troisième item appartient au second point ODJ."""
    item = _load("syceron_seance_complete.xml")[2]
    assert item["titre_point"] == "Questions au gouvernement"
    assert item["thematique_ref"] == "questions_gouvernement"


def test_seance_complete_dossierref_vide_devient_none():
    """Un élément <dossierRef/> vide doit être None, jamais une chaîne vide."""
    item = _load("syceron_seance_complete.xml")[2]
    assert item["dossier_ref"] is None


def test_seance_complete_paragraphe_sans_orateur_ignore():
    """Les paragraphes sans <orateur> ne doivent pas apparaître dans le résultat."""
    result = _load("syceron_seance_complete.xml")
    # Trois interventions (deux du point 1, une du point 2) ; le paragraphe
    # de présidence du point 1 est ignoré.
    prenoms = [r["prenom_nom"] for r in result]
    assert "Jean Dupont" in prenoms
    assert "Marie Martin" in prenoms
    # Aucun enregistrement sans prenom_nom ni acteur_ref
    for r in result:
        assert r["prenom_nom"] is not None or r["acteur_ref"] is not None


# ---------------------------------------------------------------------------
# Tests — fixture : métadonnées partielles
# ---------------------------------------------------------------------------

def test_metadonnees_partielles_date_none():
    """Si <dateSeance> est absent, date doit être None."""
    result = _load("syceron_metadonnees_partielles.xml")
    assert len(result) == 1
    assert result[0]["date"] is None


def test_metadonnees_partielles_numero_seance_none():
    """Si <numSeance> est absent, numero_seance doit être None."""
    result = _load("syceron_metadonnees_partielles.xml")
    assert result[0]["numero_seance"] is None


def test_metadonnees_partielles_champs_presents():
    """Les champs présents sont correctement extraits."""
    result = _load("syceron_metadonnees_partielles.xml")
    assert result[0]["legislature"] == "16"
    assert result[0]["session"] == "extraordinaire 2022-2023"
    assert result[0]["prenom_nom"] == "Sophie Bernard"
    assert result[0]["acteur_ref"] == "PA654321"


def test_metadonnees_partielles_contexte_odj_sans_dossier():
    """Contexte ODJ sans dossierRef ni thematiqueRef : les deux champs sont None."""
    result = _load("syceron_metadonnees_partielles.xml")
    assert result[0]["dossier_ref"] is None
    assert result[0]["thematique_ref"] is None


# ---------------------------------------------------------------------------
# Tests — fixture : texte long (troncature à 180 caractères)
# ---------------------------------------------------------------------------

def test_texte_long_tronque():
    """Un texte de plus de 180 caractères doit être tronqué à exactement 180."""
    result = _load("syceron_texte_long.xml")
    assert len(result) == 1
    assert result[0]["texte"] is not None
    assert len(result[0]["texte"]) == 180


def test_texte_long_debut_preserve():
    """La troncature doit conserver le début du texte."""
    item = _load("syceron_texte_long.xml")[0]
    assert item["texte"].startswith("La transition énergétique")


# ---------------------------------------------------------------------------
# Tests — fixture : sans paragraphes valides
# ---------------------------------------------------------------------------

def test_sans_paragraphes_valides_liste_vide():
    """Quand aucun paragraphe ne possède d'orateur identifié, le résultat est vide."""
    result = _load("syceron_sans_paragraphes_valides.xml")
    assert result == []


# ---------------------------------------------------------------------------
# Tests — parsing depuis une chaîne XML (pas un fichier)
# ---------------------------------------------------------------------------

_XML_INLINE = """\
<?xml version="1.0" encoding="UTF-8"?>
<compteRendu>
  <metadonnees>
    <dateSeance>2025-03-01</dateSeance>
    <numSeance>021</numSeance>
    <legislature>17</legislature>
    <session>ordinaire 2024-2025</session>
  </metadonnees>
  <contenu>
    <pointODJ>
      <titrePointODJ>Motion de procédure</titrePointODJ>
      <dossierRef>DOSS-2025-001</dossierRef>
      <paragraphes>
        <paragraphe>
          <orateur>
            <acteurRef>PA111222</acteurRef>
            <prenomNom>Alice Moreau</prenomNom>
            <qualite>députée</qualite>
          </orateur>
          <texte>Nous votons contre cette motion.</texte>
        </paragraphe>
      </paragraphes>
    </pointODJ>
  </contenu>
</compteRendu>
"""


def test_parse_depuis_chaine_xml():
    """parse_syceron accepte une chaîne XML brute."""
    result = parse_syceron(_XML_INLINE)
    assert len(result) == 1
    assert result[0]["acteur_ref"] == "PA111222"
    assert result[0]["date"] == "2025-03-01"
    assert result[0]["dossier_ref"] == "DOSS-2025-001"


# ---------------------------------------------------------------------------
# Tests — parsing depuis un ET.Element (utile pour les tests d'intégration)
# ---------------------------------------------------------------------------

def test_parse_depuis_element():
    """parse_syceron accepte un ET.Element déjà parsé."""
    root = ET.fromstring(_XML_INLINE)
    result = parse_syceron(root)
    assert len(result) == 1
    assert result[0]["prenom_nom"] == "Alice Moreau"


# ---------------------------------------------------------------------------
# Tests — aucun champ manquant n'est une chaîne vide ou 0
# ---------------------------------------------------------------------------

def test_aucune_valeur_vide_ou_zero():
    """Règle éditoriale : les valeurs manquantes sont None, jamais '' ou 0."""
    all_results = []
    for fixture in FIXTURES.glob("syceron_*.xml"):
        all_results.extend(parse_syceron(fixture))

    for item in all_results:
        for key, value in item.items():
            assert value != "", (
                f"Champ '{key}' vaut '' dans un résultat — doit être None. "
                f"Résultat : {item}"
            )
            assert value != 0, (
                f"Champ '{key}' vaut 0 dans un résultat — doit être None. "
                f"Résultat : {item}"
            )
