"""Les 5 fiches de groupe de la XVIIe législature, et leur succession (#700).

Les 5 fiches de groupe publiées décrivent toutes la XVIe, close le 09/06/2024,
alors que la majorité des votes publiés des candidats déclarés relèvent de la
XVIIe. Le travail préparatoire dormait dans le dépôt depuis le 26/08/2026 :
`correspondance_sigles_an` portait les cinq groupes, mesurés et relus, sous une
mention (« la publication est le lot 1b ») qui désignait #527 — laquelle a
basculé la *source* du roster sur AMO30 et n'a jamais publié de fiche. Ce qui
manquait tenait en cinq entrées du tableau `groupes[]`, celui que le pipeline
lit pour savoir quelles fiches produire.

Deux choses se vérifient ici, et elles ne sont pas de même nature :

- **la recopie** : chaque valeur des 5 nouvelles entrées vient de la table
  voisine ou de l'archive, jamais d'une saisie ;
- **la succession** : `succede_a` est **notre affirmation**, pas un champ de
  l'AN — l'Assemblée ouvre et ferme des organes, elle ne les chaîne pas. Le
  bloc publié le déclare (`etabli_par`) et **refuse** un `source_url`, miroir
  exact de `position_politique` (#686) qui, lui, l'exige.

Tout ce qui se mesure sur l'archive tourne sur
`tests/fixtures/amo30_gp_leg16_17.zip`, réduction verbatim de l'archive réelle
(voir l'en-tête de `tests/test_an_roster.py`).

Aucun réseau, aucune lecture de `pivot_data/` ni de `raw_data/profiles/`.
"""

import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "src"))

import an_roster  # noqa: E402
import check_quality_gate  # noqa: E402
import groupes_config  # noqa: E402
import schema_groupe  # noqa: E402

ARCHIVE = Path(__file__).resolve().parent / "fixtures" / "amo30_gp_leg16_17.zip"
CONFIG = RACINE / "raw_data" / "groupes_reels.json"

#: Ce qu'un run doit produire : cinq fiches, une par groupe de la XVIIe.
#: `groupe_nom` est le `libelle` de l'organe AMO30, VERBATIM — le test
#: `test_le_nom_publie_est_le_libelle_de_lorgane_verbatim` le remesure sur
#: l'archive plutôt que de faire confiance à cette table.
FICHES_17E: dict[str, tuple[str, str, str]] = {
    # groupe_id: (groupe_sigle, groupe_nom, fichier)
    "AN:EPR": ("EPR", "Ensemble pour la République", "groupe-AN-EPR-17.json"),
    "AN:SOC:17": ("SOC", "Socialistes et apparentés", "groupe-AN-SOC-17.json"),
    "AN:RN:17": ("RN", "Rassemblement National", "groupe-AN-RN-17.json"),
    "AN:LFI:17": (
        "LFI",
        "La France insoumise - Nouveau Front Populaire",
        "groupe-AN-LFI-17.json",
    ),
    "AN:DR": ("DR", "Droite Républicaine", "groupe-AN-DR-17.json"),
}


@pytest.fixture(autouse=True)
def _drapeau_restaure():
    initial = an_roster.AN_ROSTER_ACTIF
    an_roster.vider_memo()
    yield
    an_roster.activer_roster_an(initial)
    an_roster.vider_memo()


def _config() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def _groupes_config() -> dict[str, dict]:
    return {g["groupe_id"]: g for g in _config()["groupes"]}


def _table() -> dict[str, dict]:
    return {
        e["groupe_id"]: e
        for e in groupes_config.charger_correspondance_sigles(CONFIG)
    }


# --------------------------------------------------------------------------
# 1. Les cinq entrées de `groupes[]` — recopiées, jamais saisies
# --------------------------------------------------------------------------

def test_les_cinq_groupes_de_la_17e_sont_dans_le_tableau_lu_par_le_pipeline():
    """Le tableau que lisent `generate_roster_candidats` et
    `generate_group_profiles`, et lui seul, décide quelles fiches existent.

    Les cinq groupes étaient dans `correspondance_sigles_an` depuis le
    26/08/2026 — et nulle part ailleurs. Une table de correspondance ne
    produit aucune fiche.
    """
    presents = _groupes_config()
    for groupe_id, (sigle, nom, fichier) in FICHES_17E.items():
        entree = presents.get(groupe_id)
        assert entree is not None, (
            f"{groupe_id} absent de `groupes[]` : il est dans la table de "
            "correspondance, ce qui ne produit aucune fiche (#700)."
        )
        assert entree["groupe_sigle"] == sigle
        assert entree["groupe_nom"] == nom
        assert entree["fichier"] == fichier
        assert entree["chambre"] == "AN"
        assert entree["legislature"] == "17"
        assert entree["roster_chambre"] == "deputes"


def test_chaque_entree_recopie_la_table_de_correspondance():
    """`groupe_id`, `groupe_sigle`, `legislature` et `fichier` viennent de la
    table voisine. Une divergence, et le §4b du portail hard-faile."""
    table = _table()
    for groupe_id, entree in _groupes_config().items():
        if entree.get("chambre") != "AN":
            continue
        reference = table.get(groupe_id)
        assert reference is not None, f"{groupe_id} : aucune entrée de correspondance."
        for champ in ("groupe_sigle", "legislature", "fichier"):
            assert entree[champ] == reference[champ], (
                f"{groupe_id}.{champ} : {entree[champ]!r} en config, "
                f"{reference[champ]!r} dans la table."
            )


def test_le_nom_publie_est_le_libelle_de_lorgane_verbatim(tmp_path):
    """`groupe_nom` se recopie de l'archive ; il ne se rédige pas.

    Mesuré sur la réduction verbatim de l'archive : chaque groupe de la XVIIe
    n'a qu'un organe, et son `libelle` est le nom publié tel quel. Les cinq
    fiches de la XVIe, elles, ne suivent pas toutes cette règle
    (`La France insoumise - NUPES` pour un organe libellé
    `La France insoumise - Nouvelle Union Populaire écologique et sociale`) :
    c'est un état de fait, pas un précédent, et ce test ne porte que sur la
    XVIIe.
    """
    index = an_roster.charger_index_gp(ARCHIVE, repertoire_cache=tmp_path)
    table = _table()
    for groupe_id, (_, nom, _fichier) in FICHES_17E.items():
        organes = table[groupe_id]["organes_an"]
        assert len(organes) == 1, f"{groupe_id} : plus d'un organe, le nom se choisirait."
        assert index["organes"][organes[0]]["libelle"] == nom


def test_la_mention_du_lot_1b_a_disparu_de_la_configuration():
    """La mention qui a rendu l'oubli invisible.

    Les cinq entrées annonçaient « la publication est le lot 1b » ; « lot 1b »
    est #527, qui a basculé la *source* du roster sur AMO30 et s'est fermée le
    26/08/2026 sans publier une seule fiche. Une note qui désigne un lot qui a
    fait autre chose dispense de vérifier — c'est ce qui a coûté la couverture
    de la XVIIe pendant six jours.
    """
    texte = CONFIG.read_text(encoding="utf-8")
    assert "lot 1b. " not in texte
    assert "la publication est le lot 1b" not in texte


# --------------------------------------------------------------------------
# 2. `groupe_id` : opaque, unique — jamais découpé
# --------------------------------------------------------------------------

def test_le_groupe_id_de_la_17e_casse_le_patron_chambre_sigle():
    """Le constat, figé plutôt que corrigé.

    `AN:EPR` et `AN:DR` n'ont pas de suffixe (sigle neuf), `AN:RN:17`,
    `AN:SOC:17` et `AN:LFI:17` en ont un (sigle réutilisé). `groupe_id` n'est
    donc **pas** uniformément `<chambre>:<sigle>`, contrairement à ce que
    l'en-tête de `schema_groupe` a longtemps affirmé. C'est tenable parce que
    rien ne le découpe : le test suivant le vérifie.
    """
    suffixes = {gid: gid.count(":") for gid in FICHES_17E}
    assert suffixes == {
        "AN:EPR": 1, "AN:SOC:17": 2, "AN:RN:17": 2, "AN:LFI:17": 2, "AN:DR": 1
    }


def test_aucun_code_du_depot_ne_decoupe_un_groupe_id():
    """Un identifiant qu'on découpe est un identifiant qu'on ne peut plus
    étendre. Le jour où quelqu'un écrit `groupe_id.split(":")[1]`, les trois
    entrées suffixées rendent `RN` là où le sigle publié est `RN` et la
    législature `17` — un bug muet."""
    fautifs = []
    for chemin in sorted((RACINE / "src").glob("*.py")):
        texte = chemin.read_text(encoding="utf-8")
        for ligne in texte.splitlines():
            nu = ligne.strip()
            if nu.startswith("#"):
                continue
            if "groupe_id" in nu and (".split(" in nu or ".partition(" in nu):
                fautifs.append(f"{chemin.name}: {nu}")
    assert not fautifs, (
        "`groupe_id` est opaque depuis #700 — trois des dix valeurs portent un "
        "suffixe de législature :\n  " + "\n  ".join(fautifs)
    )


def test_les_groupe_id_publies_sont_uniques():
    identifiants = [g["groupe_id"] for g in _config()["groupes"]]
    assert len(identifiants) == len(set(identifiants))


# --------------------------------------------------------------------------
# 3. `succede_a` : notre affirmation, déclarée comme telle
# --------------------------------------------------------------------------

SUCCESSIONS = {
    "AN:EPR": "AN:REN",
    "AN:SOC:17": "AN:SOC",
    "AN:RN:17": "AN:RN",
    "AN:LFI:17": "AN:LFI",
    "AN:DR": "AN:LR",
}


def test_chaque_fiche_de_la_17e_succede_a_une_fiche_du_tableau():
    """« Atteindre la fiche publiée » : le bloc porte le `fichier`, pas
    seulement l'identifiant. La vue empilée n'a rien d'autre à ouvrir."""
    fiches_connues = {g["fichier"] for g in _config()["groupes"]}
    table = _table()
    for groupe_id, attendu in SUCCESSIONS.items():
        entree = table[groupe_id]
        bloc = groupes_config.succession_publiee(
            entree["groupe_sigle"], entree["legislature"], CONFIG
        )
        assert bloc is not None
        assert bloc["groupe_id"] == attendu
        assert bloc["fichier"] in fiches_connues
        assert bloc["fichier"] == table[attendu]["fichier"]
        assert bloc["legislature"] == "16"


def test_le_bloc_publie_est_une_relecture_datee_et_ne_porte_aucune_source():
    """L'invariant qui porte l'arbitrage.

    L'Assemblée ouvre et ferme des organes, elle ne les chaîne pas. Une
    `source_url` posée à côté de cette affirmation lui prêterait une source qui
    ne l'écrit nulle part (AGENTS.md §2 règle 2) : c'est `etabli_par` qui dit
    d'où elle vient, et il est obligatoire.
    """
    bloc = groupes_config.succession_publiee("DR", "17", CONFIG)
    assert bloc["etabli_par"] == schema_groupe.ETABLI_PAR_RELECTURE_HUMAINE
    assert bloc["verifie_le"] == "2026-08-26"
    assert "source_url" not in bloc
    # La preuve : les organes du prédécesseur, recopiés de la table.
    assert bloc["organes_an"] == ["PO800508"]
    assert bloc["sigles_an"] == ["LR"]


def test_le_vocabulaire_detablissement_na_quune_valeur():
    """Pas de `source_ouverte` « au cas où » : ce cas n'existe pas, et une
    valeur ajoutée d'avance laisserait croire le contraire."""
    assert schema_groupe.ETABLISSEMENTS_SUCCESSION == ("relecture_humaine",)


def test_les_fiches_de_la_16e_ne_succedent_a_rien():
    """`None`, pas un trou : la XVe n'est pas couverte par ce dépôt, et un
    champ absent ne prétend rien (AGENTS.md §2 règle 5)."""
    for sigle in ("REN", "SOC", "RN", "LFI", "LR"):
        assert groupes_config.succession_publiee(sigle, "16", CONFIG) is None


def test_une_succession_sans_legislature_est_refusee():
    with pytest.raises(groupes_config.CorrespondanceSiglesInvalide):
        groupes_config.succession_publiee("DR", None, CONFIG)


# --------------------------------------------------------------------------
# 4. Le schéma : `succede_a` optionnel, et validé dès qu'il est là
# --------------------------------------------------------------------------

def _fiche(succede_a):
    fiche = schema_groupe.make_empty_profil_groupe(
        "AN:DR", "DR", "Droite Républicaine", "AN", "17"
    )
    fiche["succede_a"] = succede_a
    return fiche


def _bloc_valide(**surcharges):
    bloc = {
        "groupe_id": "AN:LR",
        "fichier": "groupe-AN-LR-16.json",
        "legislature": "16",
        "sigles_an": ["LR"],
        "organes_an": ["PO800508"],
        "etabli_par": "relecture_humaine",
        "verifie_le": "2026-08-26",
    }
    bloc.update(surcharges)
    return bloc


def test_le_champ_absent_reste_valide():
    """Les 7 fiches publiées avant le lot ne le portent pas, et les 5 fiches de
    la XVIe ne le porteront jamais. L'exiger ferait échouer le portail sur du
    publié — même arbitrage que #686 et #653."""
    fiche = schema_groupe.make_empty_profil_groupe("AN:LR", "LR", "Les Républicains", "AN", "16")
    del fiche["succede_a"]
    assert schema_groupe.validate_profil_groupe(fiche) == []
    assert schema_groupe.validate_profil_groupe(_fiche(None)) == []


def test_le_bloc_complet_est_valide():
    assert schema_groupe.validate_profil_groupe(_fiche(_bloc_valide())) == []


@pytest.mark.parametrize(
    "surcharges, attendu",
    [
        ({"source_url": "https://data.assemblee-nationale.fr/"}, "source_url"),
        ({"etabli_par": None}, "etabli_par"),
        ({"etabli_par": "referentiel_an"}, "etabli_par"),
        ({"verifie_le": ""}, "verifie_le"),
        ({"fichier": "groupe-AN-LR-16"}, "fichier"),
        ({"fichier": None}, "fichier"),
        ({"groupe_id": ""}, "groupe_id"),
        ({"groupe_id": "AN:DR"}, "ne se succède pas"),
        ({"legislature": None}, "legislature"),
        ({"organes_an": []}, "organes_an"),
        ({"organes_an": ["PA800508"]}, "organes_an[0]"),
        ({"sigles_an": []}, "sigles_an"),
    ],
)
def test_un_bloc_qui_ment_est_refuse(surcharges, attendu):
    erreurs = schema_groupe.validate_profil_groupe(_fiche(_bloc_valide(**surcharges)))
    assert any(attendu in e for e in erreurs), erreurs


# --------------------------------------------------------------------------
# 5. La table refuse une succession qui ne résout pas (patron #485)
# --------------------------------------------------------------------------

def _config_mutee(tmp_path, mutation):
    document = _config()
    mutation(document["correspondance_sigles_an"])
    chemin = tmp_path / "groupes_reels.json"
    chemin.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    return chemin


def _entree(bloc, groupe_id):
    return next(e for e in bloc["groupes"] if e["groupe_id"] == groupe_id)


@pytest.mark.parametrize(
    "mutation, attendu",
    [
        (lambda b: _entree(b, "AN:DR").__setitem__("succede_a", "AN:INEXISTANT"),
         "n'est le `groupe_id` d'aucune entrée"),
        (lambda b: _entree(b, "AN:DR").__setitem__("succede_a", "AN:DR"),
         "ne se succède pas"),
        (lambda b: _entree(b, "AN:DR").__setitem__("succede_a", ""),
         "doit être le `groupe_id`"),
        (lambda b: _entree(b, "AN:LR").pop("fichier"),
         "n'atteindrait aucune fiche"),
    ],
)
def test_une_succession_qui_ne_resout_pas_est_refusee(tmp_path, mutation, attendu):
    chemin = _config_mutee(tmp_path, mutation)
    with pytest.raises(groupes_config.CorrespondanceSiglesInvalide) as exc:
        groupes_config.charger_correspondance_sigles(chemin)
    assert attendu in str(exc.value)


def test_la_succession_se_valide_apres_la_boucle_pas_dedans(tmp_path):
    """Un prédécesseur écrit APRÈS son successeur doit passer.

    Vérifier au fil de l'eau ferait dépendre le verdict de l'ordre des entrées
    dans le fichier — un défaut qui ne se voit que le jour où quelqu'un réordonne
    la table.
    """
    document = _config()
    bloc = document["correspondance_sigles_an"]
    bloc["groupes"].reverse()
    chemin = tmp_path / "groupes_reels.json"
    chemin.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    assert len(groupes_config.charger_correspondance_sigles(chemin)) == 10


# --------------------------------------------------------------------------
# 6. Le §4 du portail : une succession orpheline bloque, seuil 0
# --------------------------------------------------------------------------

def _publier(dossier: Path, entree: dict, succede_a=None) -> None:
    fiche = schema_groupe.make_empty_profil_groupe(
        entree["groupe_id"], entree["groupe_sigle"], entree["groupe_nom"],
        entree["chambre"], entree["legislature"],
    )
    fiche["succede_a"] = succede_a
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / entree["fichier"]).write_text(
        json.dumps(fiche, ensure_ascii=False), encoding="utf-8"
    )


def _config_deux_groupes(tmp_path, entrees):
    chemin = tmp_path / "groupes_reels.json"
    chemin.write_text(json.dumps({"groupes": entrees}, ensure_ascii=False), encoding="utf-8")
    return chemin


def test_le_gate_bloque_une_succession_qui_natteint_aucune_fiche(tmp_path):
    """Le renvoi orphelin de #485, transposé : `succede_a` ne vaut que par le
    document qu'il permet d'ouvrir."""
    config = _groupes_config()
    dossier = tmp_path / "groupes"
    _publier(dossier, config["AN:DR"], succede_a=_bloc_valide())
    chemin = _config_deux_groupes(tmp_path, [config["AN:DR"]])
    hard, _soft, _console, _md = check_quality_gate._report_groupes(chemin, dossier, 1)
    assert len(hard) == 1
    assert "succede_a.fichier" in hard[0]


def test_le_gate_accepte_une_succession_qui_atteint_sa_fiche(tmp_path):
    config = _groupes_config()
    dossier = tmp_path / "groupes"
    _publier(dossier, config["AN:LR"])
    _publier(dossier, config["AN:DR"], succede_a=_bloc_valide())
    chemin = _config_deux_groupes(tmp_path, [config["AN:LR"], config["AN:DR"]])
    hard, _soft, _console, _md = check_quality_gate._report_groupes(chemin, dossier, 1)
    assert hard == []


def test_le_gate_4b_accepte_les_cinq_fiches_de_la_17e(tmp_path):
    """`non_declaree` est une VALEUR PUBLIÉE, pas un champ absent (#686).

    L'AN ne qualifie ses groupes qu'une fois la législature achevée : les cinq
    entrées de la XVIIe portent `position: "non_declaree"` avec
    `valeur_source: null`. Le §4b doit les accepter — sans quoi c'est lui qu'il
    faudrait corriger, jamais la donnée.
    """
    dossier = tmp_path / "groupes"
    for groupe_id, entree in _groupes_config().items():
        if entree.get("chambre") != "AN":
            continue
        fiche = schema_groupe.make_empty_profil_groupe(
            entree["groupe_id"], entree["groupe_sigle"], entree["groupe_nom"],
            entree["chambre"], entree["legislature"],
        )
        fiche["position_politique"] = groupes_config.position_politique_publiee(
            entree["groupe_sigle"], entree["legislature"], CONFIG
        )
        assert schema_groupe.validate_profil_groupe(fiche) == [], groupe_id
        dossier.mkdir(parents=True, exist_ok=True)
        (dossier / entree["fichier"]).write_text(
            json.dumps(fiche, ensure_ascii=False), encoding="utf-8"
        )
    hard, _console, _md = check_quality_gate._report_position_politique(CONFIG, dossier)
    assert hard == []
    for groupe_id in FICHES_17E:
        entree = _groupes_config()[groupe_id]
        bloc = groupes_config.position_politique_publiee(
            entree["groupe_sigle"], "17", CONFIG
        )
        assert bloc["position"] == schema_groupe.POSITION_GROUPE_NON_DECLAREE
        assert bloc["source_url"], "un constat d'absence nomme sa source (#686)"
