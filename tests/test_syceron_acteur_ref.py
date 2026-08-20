"""Résolution de l'identifiant d'orateur Syceron en acteurRef AN (#510).

L'archive Syceron publie l'identifiant d'orateur **nu** (`<orateur><id>847629
</id>`), et `_parse_syceron_intervention_entry` lui appliquait
`re.fullmatch(r"PA\\d+")`. L'index de la source *primaire* des interventions se
construisait donc vide depuis toujours : 0 des 789 interventions publiées à
`f1fff09` venaient de Syceron, et le repli NosDéputés comblait le silence.

Ces tests travaillent sur `tests/fixtures/syceron_reel_leg17.xml`, extraite de
l'archive réelle (CRSANR5L17S2025O1N053.xml, 17e législature) — les deux
fixtures précédentes décrivent un schéma que l'Assemblée nationale ne publie
pas, et c'est précisément ce qui a rendu le défaut invisible aux tests.

Aucun réseau, aucune lecture de `raw_data/` ni de `pivot_data/` : le ZIP servi à
`iter_syceron_xml_files` est fabriqué en mémoire depuis la fixture.
"""

import io
import json
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import candidate_profile as cp
from parse_syceron import parse_syceron_xml

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "syceron_reel_leg17.xml"


# --------------------------------------------------------------------------
# 1. La forme publiée par la source
# --------------------------------------------------------------------------

def test_larchive_publie_lidentifiant_nu_et_le_prefixe_cote_a_cote():
    """`id_acteur="PA847629"` et `<orateur><id>847629</id>` sur le MÊME paragraphe.

    C'est la preuve que le préfixage n'est pas une inférence : la source écrit
    elle-même les deux formes. Mesuré sur les 601 comptes rendus de la 17e :
    `id_acteur == "PA" + orateur/id` sur 289 701 des 289 702 paragraphes qui
    portent les deux.
    """
    brut = FIXTURE.read_text(encoding="utf-8")
    assert "<id>847629</id>" in brut
    assert 'id_acteur="PA847629"' in brut
    assert "<id>PA847629</id>" not in brut

    interventions = parse_syceron_xml(FIXTURE.read_bytes())["interventions"]
    ids = {i.get("orateur_id_source") for i in interventions}
    assert "847629" in ids, "le parseur rend l'identifiant nu, tel que publié"
    assert not any((i or "").startswith("PA") for i in ids if i), (
        "aucun identifiant d'orateur n'est publié préfixé dans l'archive réelle"
    )


# --------------------------------------------------------------------------
# 2. La normalisation, cas par cas
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "valeur, attendu, motif",
    [
        ("847629", "PA847629", "identifiant_nu_prefixe"),
        ("795310", "PA795310", "identifiant_nu_prefixe"),
        ("PA847629", "PA847629", "prefixe_deja_present"),
        # Orateur collectif anonyme (« Un député du groupe LFI-NFP ») : 1 153
        # occurrences sur la 17e. `PA0` n'existe pas — l'indexer fabriquerait un
        # acteur.
        ("0", None, "orateur_collectif_anonyme"),
        ("000", None, "orateur_collectif_anonyme"),
        # Pseudo-acteur de rôle, hors référentiel AN (304 occurrences). L'archive
        # écrit `id_acteur="PA-125799"` : syntaxiquement formé, ne résout rien.
        ("-125799", None, "pseudo_acteur_hors_referentiel"),
        # Paragraphe sans orateur : didascalie, applaudissements.
        (None, None, "absent"),
        ("", None, "absent"),
        ("   ", None, "absent"),
        (42, None, "absent"),
        # Compteur-témoin : à 0 mesuré sur la 17e. Non nul, il dit que la forme
        # de l'identifiant a de nouveau bougé sous le code.
        ("PA12A", None, "forme_inattendue"),
        ("acteur/PA123", None, "forme_inattendue"),
    ],
)
def test_normalisation_orateur_id(valeur, attendu, motif):
    assert cp._normaliser_orateur_id_syceron(valeur) == (attendu, motif)


def test_le_prefixage_ne_fabrique_jamais_un_acteur_a_partir_de_zero():
    """`0` ne doit jamais devenir `PA0` — c'est un orateur collectif, pas une personne."""
    ref, _ = cp._normaliser_orateur_id_syceron("0")
    assert ref is None
    assert ref != "PA0"


# --------------------------------------------------------------------------
# 3. L'index, dans les deux modes
# --------------------------------------------------------------------------

@pytest.fixture
def cache_syceron(tmp_path, monkeypatch):
    """Sert la fixture réelle à `iter_syceron_xml_files` depuis un cache temporaire."""
    monkeypatch.chdir(tmp_path)
    xml_dir = tmp_path / ".cache" / "syceron_an" / "17" / "xml" / "compteRendu"
    xml_dir.mkdir(parents=True)
    (xml_dir / "CRSANR5L17S2025O1N053.xml").write_bytes(FIXTURE.read_bytes())
    return tmp_path / ".cache" / "syceron_an" / "17"


@pytest.fixture(autouse=True)
def resolution_inactive_par_defaut():
    """Restaure le drapeau après chaque test : c'est un état de module."""
    initial = cp.SYCERON_RESOLUTION_ACTEUR_NU_ACTIVE
    yield
    cp.activer_resolution_acteur_nu_syceron(initial)


def test_le_defaut_reste_le_comportement_publie(cache_syceron, capsys):
    """Drapeau inactif : index vide, exactement comme à `f1fff09`.

    Le correctif est livré INACTIF. Ce test est la garantie qu'il ne publie
    aucun octet tant que l'activation n'est pas décidée.
    """
    cp.activer_resolution_acteur_nu_syceron(False)
    index = cp._build_acteur_interventions_syceron_index("17")

    assert index == {}
    # Il reste mis en cache : ne plus le faire ferait re-parcourir l'archive à
    # chaque candidat, au débit du budget de 240 s de #498.
    assert (cache_syceron / cp.SYCERON_INDEX_FILENAME).is_file()
    # Mais il n'est plus muet — c'est le silence qui a coûté #510.
    sortie = capsys.readouterr().out
    assert "#510" in sortie
    assert "--activer-interventions-syceron" in sortie


def test_active_lindex_se_remplit(cache_syceron, capsys):
    """Drapeau actif : les orateurs résolubles entrent, les autres non."""
    cp.activer_resolution_acteur_nu_syceron(True)
    index = cp._build_acteur_interventions_syceron_index("17")

    assert "PA847629" in index
    assert "PA0" not in index
    assert "PA-125799" not in index
    assert all(entree["orateur_id_source"].startswith("PA") for v in index.values() for entree in v)

    # Défaut INDÉPENDANT de #510, mesuré sur la même archive et laissé en l'état
    # ici : `parse_syceron._parse_interventions` fait `point.findall("paragraphe")`
    # — non récursif — alors que les <point> sont imbriqués jusqu'à nivpoint 5.
    # PA795310 parle dans le <point nivpoint="2"> de la fixture et reste donc
    # invisible. 212 264 des 321 892 paragraphes de la 17e législature sont
    # perdus ainsi, soit les deux tiers du débat. Ce test fige la mesure : le jour
    # où le parcours devient récursif, il échoue et rappelle de revoir la
    # volumétrie sur laquelle l'activation de #510 a été décidée.
    assert "PA795310" not in index, (
        "les <point> imbriqués restent hors du parseur : défaut distinct de #510"
    )

    sortie = capsys.readouterr().out
    assert "identifiant_nu_prefixe=" in sortie
    assert "orateur_collectif_anonyme=" in sortie
    assert "pseudo_acteur_hors_referentiel=" in sortie


def test_les_deux_modes_nutilisent_pas_le_meme_fichier_dindex(cache_syceron):
    """Un index construit dans un mode ne doit jamais être servi à l'autre.

    `.cache/syceron_an` est partagé entre les shards par la clé de cache de
    #505 : un index de 2 octets servi à un run en mode actif est exactement le
    défaut que #505 vient de corriger.
    """
    cp.activer_resolution_acteur_nu_syceron(False)
    cp._build_acteur_interventions_syceron_index("17")
    cp.activer_resolution_acteur_nu_syceron(True)
    index = cp._build_acteur_interventions_syceron_index("17")

    assert index, "l'index vide du mode par défaut ne doit pas être resservi"
    assert cp.SYCERON_INDEX_FILENAME != cp.SYCERON_INDEX_FILENAME_ACTEUR_NU
    assert (cache_syceron / cp.SYCERON_INDEX_FILENAME).is_file()
    assert (cache_syceron / cp.SYCERON_INDEX_FILENAME_ACTEUR_NU).is_file()
    fige = json.loads((cache_syceron / cp.SYCERON_INDEX_FILENAME).read_text(encoding="utf-8"))
    assert fige == {}


def test_un_index_vide_sur_une_archive_lisible_nest_jamais_mis_en_cache(cache_syceron, capsys):
    """§2.5 : le trou par lequel #510 est passé.

    La garde de #505 ne couvrait que « aucun fichier lisible ». Un `{}` construit
    à partir de 601 comptes rendus lus passait, lui, pour un résultat — une
    donnée manquante figée en zéro mesuré, propagée à tous les shards de la
    semaine par la clé de cache.
    """
    cp.activer_resolution_acteur_nu_syceron(True)
    xml_dir = cache_syceron / "xml" / "compteRendu"
    for f in xml_dir.glob("*.xml"):
        f.unlink()
    # Un compte rendu lisible dont AUCUN orateur ne résout.
    xml_dir.joinpath("vide.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<compteRendu xmlns="http://schemas.assemblee-nationale.fr/referentiel">'
        "<uid>CR</uid><contenu><point><paragraphe><orateurs><orateur>"
        "<nom>Un député du groupe RN</nom><id>0</id></orateur></orateurs>"
        "<texte>Bravo !</texte></paragraphe></point></contenu></compteRendu>",
        encoding="utf-8",
    )

    index = cp._build_acteur_interventions_syceron_index("17")

    assert index == {}
    assert not (cache_syceron / cp.SYCERON_INDEX_FILENAME_ACTEUR_NU).exists()
    sortie = capsys.readouterr().out
    assert "NON mis en cache" in sortie
    assert "AUCUN acteur résolu" in sortie


def test_fetch_interventions_syceron_resout_le_deputes_par_son_url(cache_syceron, monkeypatch):
    """Bout en bout : l'URL de fiche AN d'un député rend ses interventions."""
    cp.activer_resolution_acteur_nu_syceron(True)
    # Seule la 17e est servie depuis le cache temporaire : les autres
    # législatures de SYCERON_AVAILABLE_LEGISLATURES déclencheraient un
    # téléchargement, que `tests/conftest.py` interdit (#473).
    monkeypatch.setattr(cp, "SYCERON_AVAILABLE_LEGISLATURES", {"17"})
    interventions = cp.fetch_interventions_syceron(
        "https://www.assemblee-nationale.fr/dyn/deputes/PA847629"
    )
    assert interventions
    assert {i["orateur_id_source"] for i in interventions} == {"PA847629"}
    assert all(i["legislature"] == "17" for i in interventions)


def test_les_anciennes_fixtures_decrivent_un_schema_que_lan_ne_publie_pas():
    """Garde-fou de contexte : ne pas réintroduire le schéma inventé.

    `syceron_minimal.xml` et `syceron_missing_fields.xml` portent des `<id>PA…</id>`
    et des `<titreStruct>` sous `<point>`. Ni l'un ni l'autre n'existe dans
    l'archive : 0 occurrence de `<titreStruct>` sous `<contenu>` sur les 601
    comptes rendus de la 17e, et 0 identifiant d'orateur préfixé. Elles restent
    en place — elles couvrent la robustesse du parseur aux champs manquants —
    mais aucune mesure ne doit plus être prise sur elles.
    """
    parsed = parse_syceron_xml(FIXTURE.read_bytes())
    assert all(i["sujet"] is None for i in parsed["interventions"]), (
        "sans <titreStruct>, `sujet` sort à None sur 100 % des 104 239 "
        "interventions de la 17e — le titre du point vit dans <point><texte>"
    )
    assert all(i["type_detail"] == "debat" for i in parsed["interventions"])
    for nom in ("syceron_minimal.xml", "syceron_missing_fields.xml"):
        inventee = (FIXTURE.parent / nom).read_text(encoding="utf-8")
        assert "<id>PA" in inventee, (
            f"{nom} décrit le schéma inventé ; si elle change, relire #510 avant "
            "d'en tirer une mesure"
        )
