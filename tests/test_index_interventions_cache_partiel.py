"""#505 — un index d'interventions incomplet ne doit jamais être mis en cache.

Pourquoi ce fichier existe. Jusqu'à #505, `.cache/questions_an` et
`.cache/syceron_an` n'étaient jamais partagés entre les shards : la clé de
cache de la semaine était écrite par un run qui ne les remplissait pas, chaque
shard reconstruisait donc son index, et un index tronqué mourait avec son
runner.

En rendant la clé sensible au mode, #505 fait exactement l'inverse : l'index
d'un shard sert à tous les autres, pour toute la semaine ISO. Le défaut
suivant devient donc structurel — un index construit sur une archive absente
serait servi à tout le monde comme s'il était complet.

Ce n'est pas une hypothèse. Mesuré le 20/08/2026 sur la législature 17 :
l'archive des questions écrites est tombée en `IncompleteRead`, et
`_build_acteur_questions_index` a quand même écrit son `index_par_acteur.json`
— 16,8 Mo, 2 611 questions issues des seules QG/QOSD. Le commentaire de
`fetch_questions_officielles` affirmait pourtant, depuis #498, que « l'index
par acteur n'est écrit en cache qu'une fois la législature entièrement lue ».
Encore une affirmation exacte à l'écriture, devenue fausse sans être relue.

Règle imposée ici : **collecte incomplète ⇒ pas de mise en cache**. L'index
partiel est rendu à l'appelant (le profil du candidat en cours n'a pas à être
puni de la panne), mais il ne survit pas au process. C'est §2.5 — une donnée
manquante reste manquante, elle ne devient pas un « 0 » mesuré.

Aucun réseau, aucun corpus : archives ZIP et XML sont fabriquées ici.
"""

import io
import json
import zipfile
from pathlib import Path
from unittest.mock import patch

import candidate_profile as cp

LEG = "17"


# ---------------------------------------------------------------------------
# Doublures
# ---------------------------------------------------------------------------


def _zip_questions(uid: str, acteur_ref: str) -> bytes:
    """Une archive de questions officielles minimale mais réaliste."""
    question = {
        "question": {
            "uid": uid,
            "auteur": {"identite": {"acteurRef": acteur_ref}, "groupe": {"abrege": "GRP"}},
            "indexationAN": {"analyses": {"analyse": "Santé"}},
            "textesQuestion": {
                "texteQuestion": {
                    "texte": "Question de doublure.",
                    "infoJO": {"dateJO": "2024-05-01"},
                }
            },
            "minInt": {"developpe": "Ministère de doublure"},
        }
    }
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w") as zf:
        zf.writestr(f"{uid}.json", json.dumps(question))
    return tampon.getvalue()


def _telechargement(echecs: set[str]):
    """Faux `download_with_watchdog` : écrit un ZIP valide, sauf pour `echecs`."""

    def faux(url, dest, **_):
        nom = Path(dest).name  # qe.zip / qg.zip / qosd.zip
        if nom in echecs:
            raise TimeoutError(f"IncompleteRead simulé sur {nom}")
        Path(dest).write_bytes(_zip_questions(f"{nom}-uid", "PA1234"))

    return faux


def _index_questions(tmp_path: Path, echecs: set[str]):
    cp._QUESTIONS_LOCKS.clear()
    with patch("candidate_profile.QUESTIONS_CACHE_DIR", tmp_path), patch(
        "candidate_profile.download_with_watchdog", _telechargement(echecs)
    ):
        index = cp._build_acteur_questions_index(LEG)
    return index, tmp_path / LEG / "index_par_acteur.json"


# ---------------------------------------------------------------------------
# Questions officielles (QE/QG/QOSD)
# ---------------------------------------------------------------------------


def test_index_questions_complet_est_mis_en_cache(tmp_path):
    """Le cas nominal : sans lui, le test suivant passerait même si l'index
    n'était plus jamais écrit."""
    index, chemin = _index_questions(tmp_path, echecs=set())
    assert index["PA1234"], "aucune question indexée — la doublure ne représente plus rien"
    assert len(index["PA1234"]) == 3, "les trois sous-types doivent être agrégés"
    assert chemin.is_file(), "un index complet doit être mis en cache"


def test_index_questions_partiel_n_est_pas_mis_en_cache(tmp_path):
    """Le défaut mesuré. Une seule des trois archives manque et l'index perd
    une part inconnue de son contenu — le mettre en cache le figerait pour
    toute la semaine sur tous les shards."""
    index, chemin = _index_questions(tmp_path, echecs={"qe.zip"})
    assert len(index["PA1234"]) == 2, "les deux archives lisibles doivent être rendues"
    assert not chemin.exists(), (
        "un index construit sans l'archive des questions écrites a été mis en "
        "cache : tout shard qui le restaurerait croirait la collecte faite."
    )


def test_index_questions_totalement_indisponible_n_est_pas_mis_en_cache(tmp_path):
    """Le cas le plus dangereux : un index VIDE mis en cache est indiscernable
    d'une législature réellement sans questions (§2.5)."""
    index, chemin = _index_questions(tmp_path, echecs={"qe.zip", "qg.zip", "qosd.zip"})
    assert index == {}
    assert not chemin.exists(), "un index vide par panne réseau a été mis en cache"


def test_archive_illisible_compte_aussi_comme_incomplete(tmp_path):
    """Le téléchargement peut réussir et l'archive être corrompue — même
    conséquence, donc même règle."""
    def faux(url, dest, **_):
        nom = Path(dest).name
        if nom == "qg.zip":
            Path(dest).write_bytes(b"ceci n'est pas un zip")
        else:
            Path(dest).write_bytes(_zip_questions(f"{nom}-uid", "PA1234"))

    cp._QUESTIONS_LOCKS.clear()
    with patch("candidate_profile.QUESTIONS_CACHE_DIR", tmp_path), patch(
        "candidate_profile.download_with_watchdog", faux
    ):
        index = cp._build_acteur_questions_index(LEG)
    assert len(index["PA1234"]) == 2
    assert not (tmp_path / LEG / "index_par_acteur.json").exists()


# ---------------------------------------------------------------------------
# Débats Syceron
# ---------------------------------------------------------------------------

_XML_SYCERON = """<?xml version="1.0" encoding="UTF-8"?>
<compteRendu xmlns="http://schemas.assemblee-nationale.fr/referentiel">
  <uid>CRSANR5L17S2024D1N001</uid>
  <metadonnees>
    <dateSeance>20240501000000</dateSeance>
    <legislature>17</legislature>
    <etat>complet</etat>
    <version>JO</version>
  </metadonnees>
  <contenu>
    <point>
      <titreStruct><intitule>Discussion générale</intitule></titreStruct>
      <paragraphe>
        <orateurs><orateur><id>PA1234</id><nom>Doublure</nom><qualite>députée</qualite></orateur></orateurs>
        <texte>Intervention de doublure.</texte>
      </paragraphe>
    </point>
  </contenu>
</compteRendu>
"""


def test_index_syceron_vide_par_archive_absente_n_est_pas_mis_en_cache(tmp_path, monkeypatch):
    """`iter_syceron_xml_files` rend un itérateur VIDE quand le téléchargement
    échoue : une fois l'index écrit, cette panne devient indiscernable d'une
    législature sans débats."""
    monkeypatch.chdir(tmp_path)
    cache = tmp_path / ".cache" / "syceron_an" / LEG
    cache.mkdir(parents=True)
    cp._SYCERON_LOCKS.clear()
    with patch("candidate_profile.iter_syceron_xml_files", lambda leg, **_: iter(())):
        index = cp._build_acteur_interventions_syceron_index(LEG)
    assert index == {}
    assert not (cache / "index_par_acteur.json").exists(), (
        "un index Syceron vide par archive absente a été mis en cache"
    )


def test_index_syceron_construit_est_mis_en_cache(tmp_path, monkeypatch):
    """Le témoin. S'il tombait, le test ci-dessus ne prouverait plus rien."""
    monkeypatch.chdir(tmp_path)
    cache = tmp_path / ".cache" / "syceron_an" / LEG
    xml_dir = cache / "xml" / "compteRendu"
    xml_dir.mkdir(parents=True)
    (xml_dir / "CR001.xml").write_text(_XML_SYCERON, encoding="utf-8")

    cp._SYCERON_LOCKS.clear()
    with patch(
        "candidate_profile.iter_syceron_xml_files",
        lambda leg, **_: iter(sorted(xml_dir.glob("*.xml"))),
    ):
        index = cp._build_acteur_interventions_syceron_index(LEG)
    assert index["PA1234"], "la doublure ne produit plus d'intervention indexée"
    assert (cache / "index_par_acteur.json").is_file()


# ---------------------------------------------------------------------------
# L'affirmation corrigée
# ---------------------------------------------------------------------------


def test_le_commentaire_de_fetch_questions_ne_ment_plus():
    """#498 avait écrit que l'index n'était mis en cache qu'une législature
    entièrement lue. Ce n'était vrai ni alors ni après. La phrase est corrigée
    dans le code ; ce test empêche qu'elle revienne telle quelle."""
    source = Path(cp.__file__).read_text(encoding="utf-8")
    assert (
        "l'index par acteur n'est écrit en cache qu'une fois la\n"
        "        # législature entièrement lue" not in source
    ), (
        "L'affirmation de #498 est de retour dans fetch_questions_officielles. "
        "Elle ne décrit le code que depuis #505, et seulement parce que "
        "_build_acteur_questions_index refuse désormais de mettre en cache un "
        "index incomplet."
    )
