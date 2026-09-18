"""Ce que la fiche de gouvernement ne doit pas reperdre (#330).

Les arbitrages de la maquette des 17 et 18/09/2026 tiennent à des détails qu'une
session suivante défait sans le savoir : le 49.3 qui prendrait une couleur
d'issue, « le groupe le plus nombreux » qui remplacerait « le groupe déclaré
majoritaire », un seuil de remaniement qui disparaîtrait dans une comparaison.

CE QUE CES GARDES NE COUVRENT PAS, et il faut le dire (§2 règle 5) : elles ne
rendent aucun composant React et n'exécutent pas d3-sankey. La géométrie du flux
et le comportement du dépliage ont été vérifiés en navigateur sur quatre
gouvernements — Philippe II (282 textes, 50 membres), Attal, Lecornu II et
Fillon I (0 texte) —, pas ici.
"""

from __future__ import annotations

import re
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
UI = RACINE / "web" / "UI_finale"

REGLES = UI / "src" / "utils" / "gouvernement.js"
COMPOSANT = UI / "src" / "components" / "GovernmentProfile.jsx"
ADAPTATEUR = UI / "src" / "data" / "pivotAdapter.js"
SYNC = UI / "scripts" / "sync-data.mjs"
DECISION = RACINE / "docs" / "decisions" / "fiche-de-gouvernement-330.md"


def test_les_regles_de_la_fiche_vivent_dans_utils():
    """Une règle testable vit dans `utils/*.js`, pas dans le composant."""
    source = REGLES.read_text(encoding="utf-8")
    for symbole in (
        "export function organigramme",
        "export function vaguesDeNomination",
        "export function fourchetteEffectif",
        "export function majoriteDuGouvernement",
        "export function chiffresDesTextes",
        "export function fluxMatiereSort",
    ):
        assert symbole in source, f"{symbole} a disparu de utils/gouvernement.js"


def test_le_49_3_ne_prend_aucune_teinte():
    """§2 règle 4 : un fait de procédure ne porte pas la couleur d'une issue."""
    source = COMPOSANT.read_text(encoding="utf-8")
    table = re.search(r"const TEINTE_SORT = \{(.+?)\};", source, re.S)
    assert table, "la table des teintes d'issue a disparu"
    for cle in ("adopte_49_3", "rejete_49_3"):
        assert re.search(rf"{cle}:\s*null", table.group(1)), (
            f"{cle} doit rester sans teinte : une couleur le rangerait parmi les issues de vote"
        )


def test_la_majorite_est_declaree_par_l_assemblee_jamais_deduite():
    """On lit `position === 'majorite'` ; on ne classe jamais par effectif."""
    source = REGLES.read_text(encoding="utf-8")
    assert "position === 'majorite'" in source
    assert "aucun groupe déclaré majoritaire" in source, (
        "l'absence de déclaration depuis 2024 se dit ; elle ne se comble pas"
    )
    # Aucun tri par nombre de membres dans la fonction : ce serait notre jugement.
    fonction = re.search(r"export function majoriteDuGouvernement\(.+?\n\}", source, re.S)
    assert fonction, "majoriteDuGouvernement a disparu"
    assert "effectif" not in fonction.group(0), (
        "le groupe le plus nombreux n'est pas le groupe majoritaire (§2 règle 1)"
    )


def test_le_seuil_d_une_vague_de_nominations_est_declare():
    """Le seuil décide du nombre de remaniements : il se nomme, il ne se cache pas."""
    source = REGLES.read_text(encoding="utf-8")
    assert "export const JOURS_MEME_VAGUE" in source


def test_l_effectif_compte_des_personnes_pas_des_portefeuilles():
    source = REGLES.read_text(encoding="utf-8")
    fonction = re.search(r"export function effectifAu\(.+?\n\}", source, re.S)
    assert fonction and "new Set()" in fonction.group(0), (
        "quelqu'un qui tient deux portefeuilles le même jour ne compte qu'une fois"
    )


def test_le_rattachement_se_lit_dans_le_libelle_officiel():
    """La source écrit « après » pour « auprès », et des espaces insécables."""
    source = REGLES.read_text(encoding="utf-8")
    assert "aupr[èe]s|apr[èe]s" in source, (
        "la faute de la source se lit, elle ne se corrige pas : sinon un ministère fantôme apparaît"
    )
    assert "\\u00a0" in source, "les espaces insécables des libellés se normalisent à l'entrée"


def test_la_matiere_d_un_texte_est_la_commission_saisie_au_fond():
    source = ADAPTATEUR.read_text(encoding="utf-8")
    assert "commission_saisie_au_fond" in source, (
        "la matière est sourcée sur la commission, jamais lue dans le titre du texte"
    )


def test_le_manifest_porte_la_position_des_groupes():
    """Sans elle, la fiche téléchargerait des fiches de groupe de 500 Ko."""
    source = SYNC.read_text(encoding="utf-8")
    assert "position: groupe.position_politique?.position" in source


def test_les_criteres_de_section_tiennent_en_une_limite():
    """DESIGN_SYSTEM §7 règle 2 : au-delà de 22 mots, ce n'est plus une limite,
    c'est une explication — et une explication va dans la méthodologie."""
    source = COMPOSANT.read_text(encoding="utf-8")
    criteres = re.findall(r'<p className="gvp-section-critere">(.*?)</p>', source, re.S)
    assert criteres, "aucun critère de section : le sélecteur a changé"
    trop_longs = [
        (len(" ".join(c.split()).split()), " ".join(c.split()))
        for c in criteres
        if len(" ".join(c.split()).split()) > 22
    ]
    assert not trop_longs, f"critères qui expliquent au lieu de limiter : {trop_longs}"


def test_les_renvois_remplacent_l_explication_et_atteignent_une_ancre():
    """La fiche garde le renvoi ; le paragraphe part en méthodologie.

    Un pied de section ne subsiste que là où AUCUNE forme ne porte le fait —
    le 49.3, que §2 règle 4 veut nommé à côté de la figure. Décrire ce que la
    figure montre déjà est l'aveu d'échec que DESIGN_SYSTEM §7 règle 2 refuse.
    """
    source = COMPOSANT.read_text(encoding="utf-8")
    assert '49.3 est un fait de procédure' in source, (
        "le 49.3 se nomme à côté de la figure : aucune forme ne le porte seule"
    )
    ancres = set(re.findall(r"/methodologie#([a-z]+)", source))
    assert ancres, "aucun renvoi vers la méthodologie"
    methodo = (UI / "src" / "pages" / "MethodologyPage.jsx").read_text(encoding="utf-8")
    ids = set(re.findall(r"id: '([a-z]+)'", methodo))
    assert ancres <= ids, f"renvois vers des ancres inexistantes : {ancres - ids}"


def test_la_decision_existe_et_porte_sa_date():
    contenu = DECISION.read_text(encoding="utf-8")
    assert contenu.startswith("# "), "un titre de niveau 1 ouvre la décision"
    assert "`2026-09-18`" in contenu
    assert "> **En bref**" in contenu
