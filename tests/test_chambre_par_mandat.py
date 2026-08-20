"""Chaque `mandat_electif` porte la chambre dont il relève (#492).

Sous-issue C de l'épic **#486**. Avant, les libellés publiés étaient « Mandat
parlementaire (Les Républicains) », identiques qu'on siège au Palais-Bourbon ou
au Luxembourg : l'information n'était pas seulement non affichée, elle n'était
pas portée.

**Le diagnostic de l'issue était faux sur la méthode.** Elle proposait de dériver
la chambre du `source_url` (« les fiches AN portent `assemblee-nationale.fr`, les
sénatoriales `archive.nossenateurs.fr` »). Mesuré sur `f5a828b`, sur les 209
profils publiés : 14 `mandat_electif` sur 228 portent un `source_url`, et **les
14 pointent sur `www.europarl.europa.eu`**. Aucun ne pointe sur
`assemblee-nationale.fr` ni sur `archive.nossenateurs.fr` — la distinction que
la méthode devait établir est précisément celle qu'elle ne peut pas établir.
`_extract_mandats` n'a jamais renseigné ce champ sur un mandat électif.

La chambre est donc **estampillée à la collecte**, là où elle est connue sans
déduction : `candidate_profile.build_profile(chambre, slug)` sait de quel jeu de
données vient le mandat qu'il fabrique.

Et elle est lue **sur le mandat**, jamais sur `raw_profile["chambre"]` : la
fusion additive accumule dans un même profil des mandats collectés lors de runs
différents, donc sous des chambres potentiellement différentes. Cas mesuré sur
`f5a828b` : le profil brut de `jean-luc-melenchon` porte `chambre: "senateurs"`
et **trois** `mandat_electif`, dont deux manifestement AN (2017-2022, groupe
LFI). Reprendre la chambre du profil aurait estampillé « Sénat » deux mandats de
l'Assemblée.

Aucune lecture du corpus vivant (`pivot_data/`, `raw_data/profiles/`) : ces
tests tournent en CI, où le corpus est absent du disque (#473).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from candidate_profile import _extract_mandats  # noqa: E402
from group_profile import (  # noqa: E402
    _compute_cohesion_votes,
    _derive_membre_entry,
    _member_eligibility_intervals,
    _member_eligible_at,
)
from merge_profile import merge_pivot_profile, merge_raw_profile  # noqa: E402
from normalize_europarl import normalize_europarl  # noqa: E402
from normalize_nosdeputes import (  # noqa: E402
    WARNING_PREFIX_CHAMBRE_MANDAT_NON_RESOLUE,
    normalize_nosdeputes,
)
from schema_pivot import validate_profil  # noqa: E402
from scrutins_index import ScrutinsIndex, cle_scrutin  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures figées, minimales
# ---------------------------------------------------------------------------

def _mandat_brut(chambre=None, label="Mandat parlementaire (Socialistes)", debut="2022-06-22"):
    """Mandat électif au format brut (`candidate_profile.build_profile()`).

    `chambre` absente = mandat collecté avant #492, tel que la fusion additive
    le conserve dans le corpus.
    """
    mandat = {
        "categorie": "mandat_electif",
        "type": "mandat",
        "label": label,
        "debut": debut,
        "fin": None,
        "actif": True,
    }
    if chambre is not None:
        mandat["chambre"] = chambre
    return mandat


def _brut(chambre="deputes", mandats=None):
    """Profil brut minimal, format `candidate_profile.build_profile()`."""
    return {
        "slug": "marie-martin",
        "chambre": chambre,
        "source": "https://www.nosdeputes.fr/marie-martin",
        "identite": {"nom_complet": "Marie Martin", "groupe_nom": "Socialistes"},
        "mandats": mandats if mandats is not None else [_mandat_brut(chambre)],
        "votes": [],
        "interventions": [],
        "amendements": [],
        "dossiers_legislatifs": [],
        "meta": {
            "genere_le": "2026-08-20T12:00:00+0000",
            "synchro_sources": {"nosdeputes": "2026-08-20T12:00:00+0000"},
        },
    }


def _electifs(pivot):
    return [m for m in pivot["mandats"] if m["categorie"] == "mandat_electif"]


def _warnings_chambre(pivot):
    return [
        w for w in pivot["meta"]["warnings"]
        if w.startswith(WARNING_PREFIX_CHAMBRE_MANDAT_NON_RESOLUE)
    ]


# ---------------------------------------------------------------------------
# 1. Collecte : la chambre est estampillée là où elle est connue
# ---------------------------------------------------------------------------

def test_extract_mandats_estampille_la_chambre_de_collecte():
    parlementaire = {"mandat_debut": "2022-06-22", "mandat_fin": None, "groupe": "Socialistes"}
    for chambre in ("deputes", "senateurs"):
        mandats = _extract_mandats(parlementaire, chambre)
        electif = next(m for m in mandats if m["categorie"] == "mandat_electif")
        assert electif["chambre"] == chambre


def test_extract_mandats_sans_chambre_ninvente_rien():
    """§2.5 : appelée sans chambre, la fonction n'écrit pas le champ — elle ne
    retombe pas sur une valeur « probable » comme "deputes"."""
    mandats = _extract_mandats({"mandat_debut": "2022-06-22", "groupe": "Socialistes"})
    electif = next(m for m in mandats if m["categorie"] == "mandat_electif")
    assert "chambre" not in electif


def test_seul_le_mandat_electif_est_estampille():
    """Le périmètre de #492 est le mandat électif. La chambre d'une commission
    est un fait réel mais non publié en v1 : ne pas l'inventer non plus."""
    parlementaire = {
        "mandat_debut": "2022-06-22",
        "groupe": "Socialistes",
        "responsabilites": [
            {"responsabilite": {"organisme": "Commission des lois", "fonction": "membre",
                                "debut_fonction": "2022-07-01", "fin_fonction": None}}
        ],
    }
    mandats = _extract_mandats(parlementaire, "deputes")
    commission = next(m for m in mandats if m["categorie"] == "commission")
    assert "chambre" not in commission


# ---------------------------------------------------------------------------
# 2. Normalisation : la chambre pivot vient du mandat, jamais du profil
# ---------------------------------------------------------------------------

def test_pivot_mappe_la_chambre_de_collecte_vers_la_nomenclature_pivot():
    assert _electifs(normalize_nosdeputes(_brut("deputes")))[0]["chambre"] == "AN"
    assert _electifs(normalize_nosdeputes(_brut("senateurs")))[0]["chambre"] == "Senat"


def test_pivot_ne_reprend_jamais_la_chambre_du_profil():
    """Le cas Mélenchon, réduit à sa forme minimale : un profil brut
    `senateurs` qui porte un mandat AN et un mandat non estampillé.

    Reprendre `raw_profile["chambre"]` publierait « Senat » sur les deux — un
    fait faux sur le mandat AN, et une chambre inventée sur l'autre."""
    brut = _brut("senateurs", mandats=[
        _mandat_brut("deputes", label="Mandat parlementaire (LFI)", debut="2017-06-18"),
        _mandat_brut(None, label="Mandat parlementaire (CRC)", debut="2004-09-26"),
    ])
    chambres = [m["chambre"] for m in _electifs(normalize_nosdeputes(brut))]
    assert chambres == ["AN", None]


def test_pivot_publie_null_et_un_warning_quand_la_chambre_nest_pas_etablie():
    pivot = normalize_nosdeputes(_brut("deputes", mandats=[_mandat_brut(None)]))
    assert _electifs(pivot)[0]["chambre"] is None
    assert len(_warnings_chambre(pivot)) == 1
    assert "1 mandat(s)" in _warnings_chambre(pivot)[0]


def test_un_seul_warning_par_profil_quel_que_soit_le_nombre_de_mandats():
    """Le cas n'est ni celui de #474 (exclusion attendue, sans warning) ni tout
    à fait celui de #488 (panne, un warning par échec) : le `null` est
    déterministe et uniforme, donc **un** warning qui porte le compte.
    `audit_pivot_dataset.compute_agregation_warnings` agrège par préfixe : un
    warning par mandat ferait 214 occurrences (mesuré sur `f5a828b`) là où une
    par profil dit la même chose."""
    brut = _brut("deputes", mandats=[
        _mandat_brut(None, debut="2017-06-21"),
        _mandat_brut(None, debut="2022-06-22"),
        _mandat_brut(None, debut="2024-07-07"),
    ])
    warnings = _warnings_chambre(normalize_nosdeputes(brut))
    assert len(warnings) == 1
    assert "3 mandat(s)" in warnings[0]


def test_aucun_warning_quand_tous_les_mandats_sont_estampilles():
    assert _warnings_chambre(normalize_nosdeputes(_brut("deputes"))) == []


def test_une_chambre_brute_inconnue_ne_passe_pas_en_contrebande():
    """Une valeur hors `_CHAMBRE_MAP` devient `null` + warning, elle n'est pas
    recopiée telle quelle : sinon "deputes" se ferait passer pour une chambre
    pivot et `validate_profil` la refuserait au commit, pas à la collecte."""
    pivot = normalize_nosdeputes(_brut("deputes", mandats=[_mandat_brut("congres")]))
    assert _electifs(pivot)[0]["chambre"] is None
    assert len(_warnings_chambre(pivot)) == 1


def test_le_mandat_europeen_est_estampille_pe():
    """Seul cas où la source établit la chambre sans ambiguïté."""
    ue = {
        "ep_id": "96742",
        "identite": {"nom_complet": "Marie Martin"},
        "mandats_europeens": [
            {"type": "EU_INSTITUTION", "organisation_nom": "Parlement européen",
             "role_label": "Députée", "debut": "2014-07-01", "fin": "2017-06-18", "actif": False},
            {"type": "COMMITTEE_PARLIAMENTARY_STANDING", "organisation_nom": "AFET",
             "role_label": "Membre", "debut": "2014-07-01", "fin": "2017-06-18", "actif": False},
        ],
        "meta": {},
    }
    pivot = normalize_europarl(ue, slug="marie-martin")
    assert _electifs(pivot)[0]["chambre"] == "PE"
    commission = next(m for m in pivot["mandats"] if m["categorie"] == "commission")
    assert "chambre" not in commission


def test_validate_profil_refuse_une_chambre_de_mandat_hors_nomenclature():
    pivot = normalize_nosdeputes(_brut("deputes"))
    assert validate_profil(pivot) == []
    _electifs(pivot)[0]["chambre"] = "deputes"
    errors = validate_profil(pivot)
    assert any("mandats[0].chambre" in e for e in errors), errors


def test_validate_profil_accepte_une_chambre_de_mandat_nulle():
    """`null` est licite : c'est la forme normale d'une chambre non déterminée."""
    pivot = normalize_nosdeputes(_brut("deputes", mandats=[_mandat_brut(None)]))
    assert validate_profil(pivot) == []


# ---------------------------------------------------------------------------
# 3. Fusion : sans report, le champ ne se remplirait jamais
# ---------------------------------------------------------------------------

def test_la_fusion_reporte_la_chambre_sur_un_mandat_deja_connu():
    """`merge_lists_by_key` est additif pur (l'ancienne entrée gagne) et sa clé
    ne contient pas la chambre. Sans report explicite, la version estampillée
    serait écartée à chaque régénération et le champ resterait `null` pour
    toujours en fusion additive."""
    ancien = _brut("deputes", mandats=[_mandat_brut(None)])
    nouveau = _brut("deputes", mandats=[_mandat_brut("deputes")])
    fusionne = merge_raw_profile(ancien, nouveau)
    assert len(fusionne["mandats"]) == 1
    assert fusionne["mandats"][0]["chambre"] == "deputes"


def test_le_report_de_chambre_nefface_jamais_une_chambre_deja_determinee():
    ancien = _brut("deputes", mandats=[_mandat_brut("senateurs")])
    nouveau = _brut("deputes", mandats=[_mandat_brut("deputes")])
    fusionne = merge_raw_profile(ancien, nouveau)
    assert fusionne["mandats"][0]["chambre"] == "senateurs"


def test_le_report_de_chambre_ne_touche_pas_le_profil_ancien():
    """Le report reconstruit l'entrée au lieu de la muter : `merge_raw_profile`
    ne doit pas modifier l'objet que l'appelant lui a passé."""
    ancien = _brut("deputes", mandats=[_mandat_brut(None)])
    merge_raw_profile(ancien, _brut("deputes", mandats=[_mandat_brut("deputes")]))
    assert "chambre" not in ancien["mandats"][0]


def test_le_report_de_chambre_vaut_aussi_au_niveau_pivot():
    """Le pivot est fusionné avec le pivot précédent : sans report ici non plus,
    l'entrée ancienne, non estampillée, gagnerait."""
    ancien = normalize_nosdeputes(_brut("deputes", mandats=[_mandat_brut(None)]))
    nouveau = normalize_nosdeputes(_brut("deputes"))
    fusionne = merge_pivot_profile(ancien, nouveau)
    assert len(_electifs(fusionne)) == 1
    assert _electifs(fusionne)[0]["chambre"] == "AN"


def test_le_report_najoute_aucune_entree():
    """Le report est un remplissage de champ, pas une fusion par champ : il ne
    doit ni dupliquer, ni réordonner, ni toucher un autre champ."""
    ancien = _brut("deputes", mandats=[
        _mandat_brut(None, debut="2017-06-21"),
        _mandat_brut(None, debut="2022-06-22"),
    ])
    nouveau = _brut("deputes", mandats=[_mandat_brut("deputes", debut="2022-06-22")])
    fusionne = merge_raw_profile(ancien, nouveau)
    assert [m["debut"] for m in fusionne["mandats"]] == ["2017-06-21", "2022-06-22"]
    assert [m.get("chambre") for m in fusionne["mandats"]] == [None, "deputes"]


# ---------------------------------------------------------------------------
# 4. Le risque de dénominateur (§2.7) : l'union par chambre est close
# ---------------------------------------------------------------------------

def _mandat_pivot(debut, fin=None, chambre=None, label="Mandat"):
    return {
        "categorie": "mandat_electif", "label": label, "fonction": "mandat",
        "debut": debut, "fin": fin, "actif": fin is None, "chambre": chambre,
    }


def test_un_mandat_dune_autre_chambre_nelargit_plus_la_fenetre():
    """Le cas dangereux nommé par #492 : changement de chambre en cours de
    législature. Le membre quitte l'Assemblée en 2023 et entre au Sénat ; sans
    filtre, l'union le rendait éligible aux scrutins AN de 2024, donc compté
    absent sur des scrutins qu'il ne pouvait plus voter."""
    mandats = [
        _mandat_pivot("2022-06-22", "2023-09-30", chambre="AN"),
        _mandat_pivot("2023-10-01", None, chambre="Senat"),
    ]
    assert _member_eligible_at(mandats, "2024-01-15") is True  # union, sans chambre
    assert _member_eligible_at(mandats, "2024-01-15", "AN") is False
    assert _member_eligible_at(mandats, "2023-01-15", "AN") is True
    assert _member_eligible_at(mandats, "2024-01-15", "Senat") is True


def test_un_mandat_sans_chambre_reste_compte():
    """Écarter un mandat à `chambre: null` réduirait un dénominateur publié sur
    la foi d'une donnée absente — l'erreur exactement symétrique de celle qu'on
    corrige. Conséquence : sur le corpus non estampillé d'aujourd'hui, le filtre
    ne change aucun dénominateur."""
    mandats = [_mandat_pivot("2022-06-22", None, chambre=None)]
    assert _member_eligible_at(mandats, "2024-01-15", "AN") is True
    assert _member_eligible_at(mandats, "2024-01-15", "Senat") is True


def test_aucun_mandat_electif_reste_eligible_par_defaut():
    """Absence d'information : on ne peut pas exclure (comportement historique)."""
    assert _member_eligibility_intervals([], "AN") is None
    assert _member_eligible_at([], "2024-01-15", "AN") is True


def test_des_mandats_mais_aucun_dans_la_chambre_nest_pas_une_absence_dinfo():
    """Distinction structurante : `None` (rien de connu → éligible par défaut)
    vs `[]` (on sait que ce membre ne siège pas dans cette chambre)."""
    mandats = [_mandat_pivot("2004-09-26", None, chambre="Senat")]
    assert _member_eligibility_intervals(mandats, "AN") == []
    assert _member_eligible_at(mandats, "2024-01-15", "AN") is False


def test_cohesion_le_denominateur_exclut_le_membre_parti_dans_lautre_chambre():
    """Bout en bout sur `membres_eligibles`, qui est un dénominateur publié."""
    scrutins = {}

    def vote(numero, position, date):
        scrutin_id = cle_scrutin("16", numero)
        scrutins[scrutin_id] = {
            "id": scrutin_id, "legislature": "16", "legislature_provenance": "collectee",
            "numero_scrutin": str(numero), "date": date, "texte": "PLF", "sort": "adopté",
            "type_scrutin": None, "type_vote": "vote_texte", "texte_lie_id": None,
            "source_url": None,
        }
        return {"scrutin_id": scrutin_id, "position": position}

    def profil(id_, mandats, votes):
        return {
            "schema_version": "1", "id": id_, "nom": id_, "chambre": "AN",
            "parti": None, "groupe": "Socialistes", "sources": [], "identite": None,
            "mandats": mandats, "votes": votes, "textes_portes": [],
            "interventions": [], "amendements": [], "tags_thematiques": [],
            "meta": {"schema_version": "1", "genere_le": "2026-08-20T12:00:00+0000",
                     "licence_donnees": "ODbL", "warnings": []},
        }

    reste = profil("alice", [_mandat_pivot("2022-06-22", None, chambre="AN")],
                   [vote("42", "pour", "2024-01-15")])
    parti_au_senat = profil(
        "bob",
        [_mandat_pivot("2022-06-22", "2023-09-30", chambre="AN"),
         _mandat_pivot("2023-10-01", None, chambre="Senat")],
        [vote("42", "pour", "2024-01-15")],
    )
    index = ScrutinsIndex(dict(scrutins))

    sans_filtre = _compute_cohesion_votes([reste, parti_au_senat], scrutins_index=index)
    assert sans_filtre[0]["membres_eligibles"] == 2

    avec_filtre = _compute_cohesion_votes(
        [reste, parti_au_senat], scrutins_index=index, chambre="AN"
    )
    assert avec_filtre[0]["membres_eligibles"] == 1


def test_debut_dans_groupe_ignore_le_mandat_de_lautre_chambre():
    """`membres[].debut_dans_groupe` est publié : sans filtre, il remonterait au
    mandat sénatorial de 2004 pour un groupe de l'Assemblée."""
    profil = {
        "id": "alice", "nom": "Alice",
        "mandats": [
            _mandat_pivot("2004-09-26", "2010-01-07", chambre="Senat"),
            _mandat_pivot("2022-06-22", None, chambre="AN"),
        ],
    }
    assert _derive_membre_entry(profil)["debut_dans_groupe"] == "2004-09-26"
    assert _derive_membre_entry(profil, "AN")["debut_dans_groupe"] == "2022-06-22"
