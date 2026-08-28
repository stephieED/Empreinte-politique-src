#!/usr/bin/env python3
"""
couverture_profil.py — Pourquoi une liste d'un profil est vide (#539).

Fabrique unique du bloc `couverture` du schéma pivot. Le vocabulaire (les
quatre états, les **trois** causes depuis #562, les cinq listes) vit dans
`schema_pivot` avec le reste du contrat de structure ; ce module porte les
**bornes mesurées** et la **dérivation**.

## Le défaut qu'il retire

Une liste vide ne dit rien par elle-même. Mesuré sur les 476 profils publiés au
27/08/2026, le vide est même la norme : `interventions` 469/476,
`tags_thematiques` 469/476, `textes_portes` 454/476, `amendements` 120/476,
`votes` 21/476, `mandats` 9/476. Ces vides recouvrent quatre situations qui
n'ont rien à voir entre elles — un zéro constaté, un fait sur la personne, une
source qui ne couvre pas la période, et une collecte qui n'a pas eu lieu — et
l'interface n'avait aucun moyen de les distinguer.

Le cas le plus nombreux est celui qu'aucun modèle à trois états n'exprimait :
`generate-data.yml:1553-1554` et `:1641` appliquent `--skip-interventions
--skip-dossiers-legislatifs` **en dur** au job roster, « indépendamment des
inputs » (#357). 469 profils sur 476 n'ont donc pas d'interventions parce que
**nous avons choisi de ne pas les collecter**. Le dire « non collecté » tout
court, à côté des vraies pannes, ferait dire au produit « nous n'avons pas
réussi » — le contresens exact que #539 combat. D'où la `cause`, obligatoire
sur `non_collecte` et interdite ailleurs.

## La règle qui gouverne tout le module

**La condition porte sur la santé de la source, jamais sur l'absence de
résultat.** C'est ce qui a manqué à #484 : un échec réseau a produit un vide, et
le vide a été traité comme une donnée — `jean-luc-melenchon` a basculé au Sénat.

Conséquence directe, et contre-intuitive : `WARNING_PREFIX_VOTES_INTROUVABLES`
n'est **pas** un signal de panne. Le même préfixe couvre deux faits opposés dans
`candidate_profile` — « index des scrutins indisponible » (une panne, l. 1208)
et « aucune correspondance officielle AN n'a été trouvée » (un constat, l. 4766).
Seuls les **motifs** de `MOTIFS_PANNE` ci-dessous, qui nomment une source qui
n'a pas répondu, font basculer une liste en `non_collecte`/`panne`.

Corollaire ajouté par #562 : une source en bonne santé et un code cassé sont eux
aussi deux faits différents. `'<' not supported between instances of 'dict' and
'str'` a été publié comme **preuve de panne** sur 99 profils sur 481, alors
qu'aucune source n'était en défaut. `MOTIFS_DEFAUT_COLLECTE` sépare ce cas, et
sa preuve n'est jamais recopiée d'un message d'exception : elle est construite.

## La forme à deux entrées, et pourquoi elle est la forme générale

Chaque liste collectée porte **deux** entrées : ce que la source couvre, et ce
qu'elle ne couvre pas. Elle ne dépend d'aucune connaissance de la carrière de la
personne — donc elle est publiable pour les 9 profils dont les cinq listes sont
déjà vides et dont `mandats` est vide aussi (`eric-dolige`, `charles-guene`,
`thierry-cozic`…), où toute dérivation par mandats serait muette.

Elle dit exactement ce qui est vrai : « dans la fenêtre couverte, le compte
publié est ce que la source contient ; avant, nous ne couvrons pas ». Le mandat
de XIIe législature de Ségolène Royal tombe dans la seconde entrée, et c'est
tout ce que le produit a le droit d'en dire.

Un cinquième état `partielle` — celui de `couverture_dossiers.py` (#399) — n'est
volontairement pas repris : deux entrées disent la même chose **plus** l'endroit
où passe la frontière.

## Ce que le module ne fait pas

Il ne dérive **jamais** « jamais élu·e » pour le Sénat ni pour le Parlement
européen : aucun référentiel dont la complétude soit prouvable n'existe pour ces
chambres. Ces deux faits restent exclusivement humains — voir
`etablir_fait_hors_an`.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Iterable, NamedTuple, Optional

from schema_pivot import (
    CAUSE_DEFAUT_COLLECTE,
    CAUSE_PANNE,
    CAUSE_PAR_DECISION,
    ETAT_COUVERT,
    ETAT_FAIT_ETABLI,
    ETAT_HORS_COUVERTURE,
    ETAT_NON_COLLECTE,
    LISTES_COUVERTES,
    valider_couverture,
)
from scrutins_legislature import LEGISLATURES_AN

# ---------------------------------------------------------------------------
# Calendrier
# ---------------------------------------------------------------------------

# Ouverture de chaque législature, de la XIe à la XVIIe. Les quatre dernières
# ne sont PAS recopiées : elles sont vérifiées contre `LEGISLATURES_AN`
# (`scrutins_legislature`, la table qui résout la législature d'un scrutin) par
# `_verifier_calendrier()`, appelée à l'import. Deux copies d'une même borne
# divergent en silence — c'est l'argument qui a fait écarter le patron de #399
# côté UI (`GOVERNMENT_TEXTS_COVERAGE_START` dupliquant la constante Python).
#
# Les trois plus anciennes n'ont pas d'autre porteur dans le dépôt : le
# calendrier de `scrutins_legislature` s'arrête à la XIVe parce que c'est la
# borne des archives de scrutins, et l'étendre là-bas changerait la résolution
# d'un scrutin (une date de 2005 y résoudrait au lieu d'échouer). Elles vivent
# donc ici, où elles ne servent qu'à borner une couverture.
CALENDRIER_LEGISLATURES: dict[int, tuple[str, Optional[str]]] = {
    11: ("1997-06-12", "2002-06-18"),
    12: ("2002-06-19", "2007-06-19"),
    13: ("2007-06-20", "2012-06-19"),
    14: ("2012-06-20", "2017-06-20"),
    15: ("2017-06-21", "2022-06-21"),
    16: ("2022-06-22", "2024-06-09"),
    17: ("2024-07-18", None),
}


def _verifier_calendrier() -> None:
    """Refuse une divergence avec `LEGISLATURES_AN` plutôt que de la subir."""
    for legislature, bornes in LEGISLATURES_AN.items():
        ici = CALENDRIER_LEGISLATURES.get(int(legislature))
        if ici is None:
            raise ValueError(
                f"législature {legislature} connue de scrutins_legislature mais "
                "absente de CALENDRIER_LEGISLATURES : les deux tables doivent "
                "couvrir au moins le même intervalle."
            )
        if ici != bornes:
            raise ValueError(
                f"législature {legislature} : CALENDRIER_LEGISLATURES dit {ici}, "
                f"scrutins_legislature.LEGISLATURES_AN dit {bornes}. Une borne "
                "d'archive ne peut pas avoir deux valeurs."
            )


_verifier_calendrier()


# ---------------------------------------------------------------------------
# Bornes réelles de chaque source
# ---------------------------------------------------------------------------

class Borne(NamedTuple):
    """Ce qu'une source couvre, et la preuve de cette borne."""

    #: Législatures réellement ingérées, croissantes.
    legislatures: tuple[int, ...]
    #: Preuve : la constante du dépôt qui porte la borne, et sa mesure.
    preuve: str

    @property
    def debut(self) -> str:
        """Ouverture de la plus ancienne législature ingérée."""
        return CALENDRIER_LEGISLATURES[self.legislatures[0]][0]

    @property
    def veille(self) -> str:
        """Veille de `debut` : la fin de ce que la source **ne** couvre pas."""
        return (date.fromisoformat(self.debut) - timedelta(days=1)).isoformat()


# Une entrée par liste métier. Chaque `preuve` NOMME la constante du dépôt qui
# porte la borne : c'est ce qui rend l'entrée relisible, et ce qui fait tomber le
# test `test_couverture_profil.py` le jour où une archive est ajoutée sans que la
# couverture publiée le dise.
BORNES: dict[str, Borne] = {
    # AMO30 est un référentiel HISTORIQUE, pas un roster : sa borne n'est pas
    # celle des autres. Mesurée sur `.cache/acteurs_historique_an/` le
    # 28/08/2026 — 3 117 acteurs, plus ancien `mandat_debut` d'un acteur
    # 2002-06-19 (150 acteurs), soit l'ouverture de la XIIe. Des mandats
    # d'ORGANES remontent au 09/07/1998 (9 en 1998, 10 en 1999, 34 en 2001),
    # mais aucun acteur n'y est rattaché sans mandat de la XIIe : la borne
    # prouvable est donc la XIIe, pas la XIe que nomme l'URL de l'archive.
    # C'est la condition C1 : sans cette mesure écrite avec la règle, la phrase
    # publiable n'est pas « jamais élue » mais « jamais élue depuis la XIIe ».
    "mandats": Borne(
        legislatures=(12, 13, 14, 15, 16, 17),
        preuve=(
            "AMO30 (référentiel historique des acteurs AN) — mesuré le 28/08/2026 : "
            "3 117 acteurs, plus ancien mandat_debut d'acteur 2002-06-19 (XIIe)"
        ),
    ),
    "votes": Borne(
        legislatures=(14, 15, 16, 17),
        preuve=(
            "candidate_profile.AN_SCRUTINS_LEGISLATURES = 17, 16, 15, 14 — "
            "17 748 scrutins ingérés (792 / 4 417 / 4 105 / 8 434)"
        ),
    ),
    "amendements": Borne(
        legislatures=(14, 15, 16, 17),
        preuve=(
            "candidate_profile.AN_AMENDEMENTS_PATH = 14, 15, 16, 17 — un shard "
            "pivot_data/amendements/<legislature>.json par législature ingérée"
        ),
    ),
    "textes_portes": Borne(
        legislatures=(15, 16, 17),
        preuve=(
            "couverture_dossiers.AN_DOSSIERS_ARCHIVES = XV, XVI, XVII — la XIVe et "
            "antérieures sont hors d'atteinte (structure de jeu de données "
            "incompatible, cf. couverture_dossiers.py)"
        ),
    ),
    "interventions": Borne(
        legislatures=(15, 16, 17),
        preuve="syceron_debates.SYCERON_AVAILABLE_LEGISLATURES = {15, 16, 17}",
    ),
}

assert set(BORNES) == set(LISTES_COUVERTES), (
    "chaque liste métier porte sa borne : BORNES et LISTES_COUVERTES ne peuvent "
    "pas diverger."
)


# ---------------------------------------------------------------------------
# Décisions de pipeline
# ---------------------------------------------------------------------------

#: Drapeau de `generate_all_profiles.py` → liste métier qu'il écarte, et preuve.
#: La preuve d'une décision est la DÉCISION, pas une URL : elle nomme le drapeau
#: et l'issue qui l'a posé.
DECISIONS_PIPELINE: dict[str, tuple[str, str]] = {
    "skip_interventions": (
        "interventions",
        "generate-data.yml:1641 — --skip-interventions appliqué en dur au job "
        "extract-roster-groupes, indépendamment des inputs (#357)",
    ),
    "skip_dossiers_legislatifs": (
        "textes_portes",
        "generate-data.yml:1641 — --skip-dossiers-legislatifs appliqué en dur au "
        "job extract-roster-groupes, indépendamment des inputs (#357)",
    ),
}

#: Politique appliquée à tout profil de provenance `roster_groupe` : le job qui
#: les produit porte les deux drapeaux **en dur**, donc la décision se lit sur la
#: provenance seule, sans avoir à rejouer le run. C'est ce qui rend la couverture
#: dérivable sur les 469 profils déjà publiés, dont aucun ne porte la trace des
#: drapeaux du run qui les a écrits.
DECISIONS_ROSTER: tuple[str, ...] = ("skip_interventions", "skip_dossiers_legislatifs")


# ---------------------------------------------------------------------------
# Pannes
# ---------------------------------------------------------------------------

#: Motifs de `meta.warnings[]` qui nomment une SOURCE QUI N'A PAS RÉPONDU, et la
#: liste qu'ils condamnent. Fermé, et volontairement étroit : le critère est la
#: santé de la source, jamais l'absence de résultat.
#:
#: Ce qui n'y est PAS, et pourquoi :
#: - « mandats introuvables : aucun mandat trouvé dans le référentiel officiel »
#:   (`candidate_profile:4679`) est un **constat** de l'AN, pas une panne ;
#: - « votes introuvables : aucune correspondance officielle AN n'a été trouvée »
#:   (`:4766`) aussi — alors que « votes introuvables (législature N) : index des
#:   scrutins indisponible » (`:1208`), sous le **même préfixe**, est une panne.
#:   C'est pourquoi la table est indexée par motif et non par préfixe : traiter
#:   le préfixe comme un signal produirait #484 à l'identique, en publiant
#:   « jamais élu » sur une panne réseau.
MOTIFS_PANNE: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("index des scrutins indisponible", ("votes",)),
    ("cache d'index des scrutins illisible", ("votes",)),
    ("amendements indisponibles", ("amendements",)),
    ("questions indisponibles", ("interventions",)),
    ("interventions syceron indisponibles", ("interventions",)),
    ("collecte d'interventions tronquée", ("interventions",)),
    ("collecte tronquée (budget de temps)", tuple(LISTES_COUVERTES)),
    ("textes portés officiels (Assemblée nationale) indisponibles", ("textes_portes",)),
    ("chambre en échec", tuple(LISTES_COUVERTES)),
)

#: Motifs de `meta.warnings[]` qui nomment un défaut de CE DÉPÔT, et la liste
#: qu'ils condamnent (#562). Dérivés de `LISTES_COUVERTES` plutôt que recopiés :
#: deux expressions du même invariant divergent en silence.
#:
#: Ils sont volontairement HORS de `MOTIFS_PANNE` : la table au-dessus dit « la
#: source n'a pas répondu », et une anomalie de notre code n'a jamais rien dit
#: de la source. `candidate_profile._tracer_echec_collecte` écrit l'un ou
#: l'autre, jamais les deux pour une même exception.
MOTIFS_DEFAUT_COLLECTE: tuple[tuple[str, tuple[str, ...]], ...] = tuple(
    (f"défaut de collecte interne ({liste})", (liste,)) for liste in LISTES_COUVERTES
)

#: Nombre d'acteurs attendus dans AMO30 (condition C1). En **dessous** de ce
#: plancher, le référentiel n'est pas prouvé chargé et aucun « jamais élu·e » ne
#: peut en être dérivé : l'état retombe sur `non_collecte`/`panne`. Mesuré à
#: 3 117 le 28/08/2026 ; le plancher est délibérément plus bas, un référentiel
#: historique ne pouvant que croître, et délibérément non nul — c'est un
#: référentiel à moitié lu, pas un référentiel vide, qui produit #484.
ACTEURS_AN_PLANCHER = 3_000
ACTEURS_AN_MESURE = 3_117


class SanteReferentiel(NamedTuple):
    """État du référentiel AMO30 pour ce run (condition C1)."""

    #: Nombre d'acteurs effectivement lus, ou `None` si personne ne l'a mesuré.
    nb_acteurs: Optional[int] = None

    @property
    def prouve_charge(self) -> bool:
        return self.nb_acteurs is not None and self.nb_acteurs >= ACTEURS_AN_PLANCHER

    @property
    def preuve(self) -> str:
        if self.nb_acteurs is None:
            return "référentiel AMO30 non mesuré ce run"
        return (
            f"référentiel AMO30 : {self.nb_acteurs} acteurs lus "
            f"(plancher {ACTEURS_AN_PLANCHER}, mesure de référence {ACTEURS_AN_MESURE})"
        )


# ---------------------------------------------------------------------------
# Fait établi — « jamais élu·e à l'Assemblée nationale »
# ---------------------------------------------------------------------------

class FaitHorsAn(NamedTuple):
    """Verdict de `etablir_fait_hors_an`."""

    #: `True` = la personne n'a jamais été élue à l'AN dans la fenêtre couverte.
    etabli: bool
    #: `True` si le verdict vient d'une déclaration humaine (motif + preuve
    #: relus) plutôt que d'une dérivation. C5 : elle prime toujours.
    humain: bool
    #: Preuve publiable.
    preuve: str
    #: Renseigné quand rien ne peut être établi : la panne à publier à la place.
    panne: Optional[str] = None


def etablir_fait_hors_an(
    entree_correspondance: Optional[dict[str, Any]],
    sante: SanteReferentiel = SanteReferentiel(),
) -> Optional[FaitHorsAn]:
    """« Jamais élu·e à l'Assemblée nationale » — les cinq conditions, en code.

    Portée : **l'Assemblée nationale uniquement**. AMO30 est un référentiel
    historique dont la complétude est mesurable ; ni le Sénat ni le Parlement
    européen n'ont d'équivalent dont la complétude soit prouvable, donc « jamais
    élu·e au Sénat » reste exclusivement humain. Dériver sans référentiel
    rendrait un « fait établi » là où nous n'avons qu'une absence de couverture.

    - **C1** — le référentiel doit être *prouvé chargé* (`sante`). En dessous du
      plancher, on ne dérive rien : on rend une panne.
    - **C2** — l'appariement se fait sur l'état civil complet, jamais sur le nom
      seul. C'est le travail de `raw_data/correspondance_acteurs_an.json`, qui
      stocke `etat_civil` avec la correspondance ; ce module lit son verdict.
    - **C3** — pas de date de naissance ⇒ pas de dérivation. Le cas Bardella,
      dont la date est `null` dans la table : sans état civil, un humain déclare
      avec un motif, et c'est C5 qui répond.
    - **C4** — rien n'est figé : le verdict est recalculé à chaque appel, depuis
      la table et la santé du run. L'immuabilité porte sur l'identifiant, jamais
      sur le fait.
    - **C5** — une déclaration humaine (`ecart: "hors_an"` + motif + preuve)
      prime toujours, y compris sur un référentiel en panne.

    Returns:
        `None` si la question ne se pose pas (la personne A un acteur AN, ou
        aucune entrée ne la décrit) ; un `FaitHorsAn` sinon.
    """
    if not isinstance(entree_correspondance, dict):
        return None

    acteur_ref = entree_correspondance.get("acteur_ref")
    if acteur_ref:
        # La personne EST un acteur AN : la question ne se pose pas.
        return None

    # C5 — la déclaration humaine prime, et elle prime aussi sur une panne.
    if entree_correspondance.get("ecart") == "hors_an":
        motif = (entree_correspondance.get("motif") or "").strip()
        preuve = (entree_correspondance.get("preuve") or "").strip()
        verifie_le = entree_correspondance.get("verifie_le") or ""
        if motif and preuve:
            return FaitHorsAn(
                etabli=True,
                humain=True,
                preuve=(
                    "raw_data/correspondance_acteurs_an.json — absence déclarée "
                    f"(ecart 'hors_an', vérifiée le {verifie_le}) : {preuve}"
                ),
            )

    # C1 — sans référentiel prouvé chargé, aucune dérivation. Un référentiel
    # injoignable doit produire « non collecté — panne », jamais « jamais élu ».
    if not sante.prouve_charge:
        return FaitHorsAn(
            etabli=False,
            humain=False,
            preuve=sante.preuve,
            panne=(
                "référentiel AN non prouvé chargé, aucun fait négatif dérivable — "
                f"{sante.preuve}"
            ),
        )

    # C2/C3 — sans état civil complet (date de naissance comprise), pas de
    # dérivation : on retombe sur la déclaration humaine, qui n'existe pas ici.
    etat_civil = entree_correspondance.get("etat_civil") or {}
    if not (etat_civil.get("nom") and etat_civil.get("date_naissance")):
        return FaitHorsAn(
            etabli=False,
            humain=False,
            preuve="état civil incomplet (date de naissance absente)",
            panne=(
                "état civil incomplet dans la table de correspondance : sans date "
                "de naissance, aucun fait négatif n'est dérivable (condition C3)"
            ),
        )

    return FaitHorsAn(
        etabli=True,
        humain=False,
        preuve=(
            f"{sante.preuve} — aucun acteur AMO30 pour "
            f"{etat_civil.get('nom_complet') or etat_civil.get('nom')} "
            f"(né·e le {etat_civil.get('date_naissance')})"
        ),
    )


# ---------------------------------------------------------------------------
# Dérivation
# ---------------------------------------------------------------------------

def _entree(
    etat: str,
    preuve: str,
    constate_le: str,
    *,
    cause: Optional[str] = None,
    portee: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Une entrée de couverture, clés dans un ordre stable (git le lit)."""
    entree: dict[str, Any] = {"etat": etat}
    if cause is not None:
        entree["cause"] = cause
    if portee is not None:
        entree["portee"] = portee
    entree["preuve"] = preuve
    entree["constate_le"] = constate_le
    return entree


def _preuve_defaut_collecte(liste: str) -> str:
    """La preuve d'un défaut interne — **construite**, jamais recopiée.

    C'est la règle qui répare #562 à la racine : le message de l'exception reste
    dans `meta.warnings` (canal technique) et sur la sortie d'erreur du run, et
    n'entre JAMAIS dans `preuve`. Ce que le champ publie ici est le seul fait
    vrai et vérifiable : la collecte de cette liste n'a pas abouti, et la cause
    est chez nous. Un lecteur y trouve ce qu'il peut en faire — ne rien conclure
    de ce vide, et surtout rien conclure sur l'Assemblée nationale.
    """
    return (
        f"défaut de collecte interne du dépôt sur « {liste} » : la collecte n'a "
        "pas abouti pour une anomalie qui nous est propre, aucune source de "
        "l'Assemblée nationale n'est en cause. Le détail technique est consigné "
        "dans meta.warnings et au journal de run, pas dans ce champ (#562)."
    )


def _defauts_declares(warnings: Iterable[Any]) -> set[str]:
    """Listes condamnées par un défaut de collecte interne (#562).

    Renvoie les seules listes, pas les warnings : la preuve est construite
    (`_preuve_defaut_collecte`), justement pour qu'aucun texte d'exception ne
    puisse remonter jusqu'au champ publié.
    """
    defauts: set[str] = set()
    for warning in warnings or ():
        if not isinstance(warning, str):
            continue
        minuscule = warning.lower()
        for motif, listes in MOTIFS_DEFAUT_COLLECTE:
            if motif.lower() in minuscule:
                defauts.update(listes)
    return defauts


def _pannes_declarees(warnings: Iterable[Any]) -> dict[str, str]:
    """Listes condamnées par une panne, avec le warning qui l'établit.

    Seuls les motifs de `MOTIFS_PANNE` comptent : ils nomment une source qui
    n'a pas répondu. Une absence de résultat n'en est pas une.
    """
    pannes: dict[str, str] = {}
    for warning in warnings or ():
        if not isinstance(warning, str):
            continue
        minuscule = warning.lower()
        for motif, listes in MOTIFS_PANNE:
            if motif.lower() not in minuscule:
                continue
            for liste in listes:
                pannes.setdefault(liste, warning)
    return pannes


def deriver(
    profil: dict[str, Any],
    *,
    constate_le: Optional[str] = None,
    decisions: Optional[Iterable[str]] = None,
    fait_hors_an: Optional[FaitHorsAn] = None,
) -> dict[str, list[dict[str, Any]]]:
    """Construit le bloc `couverture` d'un profil pivot.

    Args:
        profil: le profil pivot, lu pour `meta.provenance` et `meta.warnings`.
        constate_le: date ISO du constat (défaut : aujourd'hui).
        decisions: drapeaux de `DECISIONS_PIPELINE` appliqués à CE run. `None`
            = déduit de la provenance : un profil `roster_groupe` vient du job
            qui porte les deux drapeaux en dur (#357).
        fait_hors_an: verdict d'`etablir_fait_hors_an`, ou `None` si la question
            ne se pose pas.

    Returns:
        `{liste: [entrée, ...]}`, complet sur les cinq listes métier.
    """
    constate_le = constate_le or date.today().isoformat()
    meta = profil.get("meta") if isinstance(profil.get("meta"), dict) else {}
    provenance = meta.get("provenance", "candidat_declare")

    if decisions is None:
        decisions = DECISIONS_ROSTER if provenance == "roster_groupe" else ()
    ecartees = {
        DECISIONS_PIPELINE[drapeau][0]: DECISIONS_PIPELINE[drapeau][1]
        for drapeau in decisions
        if drapeau in DECISIONS_PIPELINE
    }
    # `meta.collecte_ecartee` (#539) est la trace écrite PAR LA COLLECTE des
    # listes qu'elle a délibérément sautées. Elle prime sur toute inférence :
    # la passe pivot de la CI est un `--pivot-only` sans drapeau, donc elle ne
    # sait rien du run qui a produit le brut — sauf ce que ce run a consigné.
    for liste in meta.get("collecte_ecartee") or ():
        if liste in LISTES_COUVERTES:
            ecartees.setdefault(
                liste,
                f"collecte écartée par le run qui a produit le profil brut "
                f"(meta.collecte_ecartee, #357) : {liste}",
            )
    pannes = _pannes_declarees(meta.get("warnings") or ())
    defauts = _defauts_declares(meta.get("warnings") or ())

    couverture: dict[str, list[dict[str, Any]]] = {}
    for liste in LISTES_COUVERTES:
        borne = BORNES[liste]

        # 1. Une décision de pipeline passe avant tout : rien n'a été demandé à
        #    la source, donc ni son périmètre ni sa santé ne disent quoi que ce
        #    soit sur cette liste.
        if liste in ecartees:
            couverture[liste] = [
                _entree(ETAT_NON_COLLECTE, ecartees[liste], constate_le,
                        cause=CAUSE_PAR_DECISION)
            ]
            continue

        # 1bis. Puis un défaut de NOTRE code, AVANT la santé de la source
        #    (#562) : quand les deux sont signalés pour la même liste, celui
        #    dont nous sommes sûrs est le nôtre. Publier « panne » à sa place
        #    imputerait à l'Assemblée nationale une faute qui est la nôtre —
        #    c'est ce qu'ont fait 99 profils sur 481.
        if liste in defauts:
            couverture[liste] = [
                _entree(ETAT_NON_COLLECTE, _preuve_defaut_collecte(liste),
                        constate_le, cause=CAUSE_DEFAUT_COLLECTE)
            ]
            continue

        # 2. Puis la santé de la source. Jamais l'absence de résultat.
        if liste in pannes:
            couverture[liste] = [
                _entree(ETAT_NON_COLLECTE, pannes[liste], constate_le,
                        cause=CAUSE_PANNE)
            ]
            continue

        # 3. Un fait négatif non établissable est une panne, pas un fait.
        if fait_hors_an is not None and fait_hors_an.panne:
            couverture[liste] = [
                _entree(ETAT_NON_COLLECTE, fait_hors_an.panne, constate_le,
                        cause=CAUSE_PANNE)
            ]
            continue

        # 4. Le fait établi, borné par ce que le référentiel étaye : « jamais
        #    élue » n'est publiable que dans la fenêtre où AMO30 sait répondre.
        etat_dans_la_fenetre = ETAT_COUVERT
        preuve_dans_la_fenetre = borne.preuve
        if fait_hors_an is not None and fait_hors_an.etabli:
            etat_dans_la_fenetre = ETAT_FAIT_ETABLI
            preuve_dans_la_fenetre = fait_hors_an.preuve

        couverture[liste] = [
            _entree(
                etat_dans_la_fenetre,
                preuve_dans_la_fenetre,
                constate_le,
                portee={"debut": borne.debut, "fin": None},
            ),
            _entree(
                ETAT_HORS_COUVERTURE,
                borne.preuve,
                constate_le,
                portee={"debut": None, "fin": borne.veille},
            ),
        ]

    return couverture


def appliquer(
    profil: dict[str, Any],
    *,
    constate_le: Optional[str] = None,
    decisions: Optional[Iterable[str]] = None,
    fait_hors_an: Optional[FaitHorsAn] = None,
) -> dict[str, list[dict[str, Any]]]:
    """Écrit `profil["couverture"]` et le renvoie.

    Refuse bruyamment un bloc non conforme plutôt que de le publier : la
    fabrique se contrôle avec la même règle que le schéma, écrite une fois.
    """
    couverture = deriver(
        profil, constate_le=constate_le, decisions=decisions, fait_hors_an=fait_hors_an
    )
    erreurs = valider_couverture(couverture)
    if erreurs:
        raise ValueError(
            "couverture dérivée non conforme au schéma pivot : "
            + " | ".join(erreurs)
        )
    profil["couverture"] = couverture
    return couverture
