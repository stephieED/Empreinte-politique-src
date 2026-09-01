#!/usr/bin/env python3
"""
schema_groupe.py — Schéma pivot du profil de groupe politique v1.

Ce module définit le contrat de structure du « profil de groupe », document
agrégé calculé à partir de plusieurs profils individuels (schéma pivot v1)
partageant le même groupe parlementaire.

Il ne contient aucune logique de collecte ni de calcul : c'est un contrat de
structure (constantes, fabrique, validateur). La logique d'agrégation est dans
group_profile.py.

Principe directeur : faits chiffrés uniquement, aucune interprétation.

Format d'un profil de groupe v1 :
{
    "schema_version": "1",
    "type_document": "profil_groupe",
    "groupe_id": "AN:SOC",              # "<chambre>:<sigle>" — même convention que le pivot individuel
    "groupe_sigle": "SOC",
    "groupe_nom": "Socialistes et apparentés",
    "chambre": "AN",                    # "AN" | "Senat" | "PE" | "mairie" | null
    "legislature": "16",

    "periode": {
        "debut": "2022-06-22",          # début du groupe dans cette législature
        "fin": null,
        "actif": true
    },

    "historique_noms": [                # renommages du groupe entre législatures
        {
            "sigle": "SOC",
            "nom": "Socialistes et apparentés",
            "debut": "2022-06-22",
            "fin": null
        }
    ],

    "membres": [                        # un enregistrement par membre (et par période si changement)
        {
            "membre_id": "jerome-guedj",         # id pivot individuel = son slug (#487)
            "nom": "Jérôme Guedj",
            "debut_dans_groupe": "2022-06-29",       # début de l'appartenance à CE groupe,
                                                     # lu sur le mandat GP de la législature
                                                     # de la fiche (#653). null = appartenance
                                                     # non établie, jamais approximée depuis
                                                     # le mandat électif.
            "fin_dans_groupe": "2024-06-09",         # null = appartenance encore ouverte
            "present_a_la_date_de_reference": true   # le membre appartenait-il au groupe à
                                                     # `date_reference.date` ? Remplace `actif`
                                                     # (#653) : « actif » disait un présent
                                                     # qu'une fiche de législature close n'a
                                                     # pas. false si l'appartenance n'est pas
                                                     # établie — jamais « présent par défaut ».
        }
    ],

    "date_reference": {                 # LA date à laquelle TOUS les comptes de la fiche se
                                        # rapportent (#653) : `effectif`,
                                        # `mandats_agreges[].nb_membres_a_la_date_de_reference`
                                        # et `membres[].present_a_la_date_de_reference`.
                                        # Dérivée, jamais devinée ; publiée parce qu'un
                                        # compteur daté qu'on ne peut pas dater à la lecture
                                        # est un compteur nu. ABSENTE des fiches publiées
                                        # avant le lot (les 2 `groupe-Senat-*`, gelées par
                                        # #516) : optionnelle, jamais obligatoire.
        "date": "2024-06-09",           # ISO-8601
        "origine": "cloture_legislature"  # ORIGINES_DATE_REFERENCE : `cloture_legislature`
                                        # (toutes les appartenances refermées → la plus
                                        # tardive) | `generation` (au moins une encore
                                        # ouverte → meta.genere_le)
    },

    "effectif": {
        "a_la_date_de_reference": 169,  # membres appartenant au groupe à `date_reference.date`
                                        # (#653). Remplace `actuel`, qui comptait les membres
                                        # encore députés le JOUR DU CALCUL — une propriété de
                                        # leur carrière, pas du groupe : 85 des 193 membres de
                                        # `AN:REN-16`, quand 169 y siégeaient à la clôture.
        "min_historique": null,         # min. sur la période (null si non calculé)
        "max_historique": null          # max. sur la période (null si non calculé)
    },

    "position_politique": {             # QUALIFICATION DÉCLARÉE PAR L'ASSEMBLÉE (#686).
                                        # Recopiée, jamais produite : `organe.positionPolitique`
                                        # du référentiel AMO30. ABSENTE des fiches publiées avant
                                        # le lot (les 2 `groupe-Senat-*`, gelées par #516, et
                                        # toute fiche non régénérée) : optionnelle, jamais
                                        # obligatoire.
        "position": "majorite",         # POSITIONS_POLITIQUES_GROUPE : majorite | minoritaire |
                                        # opposition | non_declaree | divergente. `non_declaree`
                                        # est une VALEUR PUBLIÉE, distincte d'un champ absent —
                                        # les 14 groupes de la XVIIe sont dans ce cas. Jamais
                                        # déduite d'un comportement de vote (AGENTS.md §2 règle 1).
        "source_url": "https://data.assemblee-nationale.fr/…AMO30_…json.zip",
                                        # OBLIGATOIRE dès que le bloc est présent, y compris sur
                                        # `non_declaree` : un constat d'absence nomme sa source
                                        # comme un constat de présence (§2 règle 2). Miroir de la
                                        # règle 6, qui exige déjà un `source_url` sur
                                        # `mandats[].position_dans_hemicycle`.
        "verifie_le": "2026-09-01",     # date de relecture de la table committée
        "organes": [                    # LA PREUVE, organe par organe, dans l'ordre de succession.
                                        # Un groupe peut avoir deux organes successifs dans une
                                        # même législature (`SOC` puis `SOC-A`, XVIe) : les deux
                                        # sont publiés, aucun n'est replié sur l'autre.
            {
                "organe_an": "PO800538",     # uid de l'organe dans AMO30
                "sigle_an": "RE",            # organe.libelleAbrev — PAS le sigle publié (`REN`)
                "valeur_source": "Majoritaire",  # la chaîne de l'AN, verbatim ; null si muette
                "position": "majorite"       # sa traduction, ou null si `valeur_source` est null
            }
        ]
    },

    "cohesion_votes": [                 # une entrée par scrutin sur lequel ≥1 membre a voté
        {
            "scrutin_id": "an:16:4084",  # référence vers pivot_data/scrutins.json (#432).
                                        # `date`, `texte` et `sort` y vivent : ce sont des
                                        # champs du SCRUTIN, qui étaient recopiés dans chacun
                                        # des groupes l'ayant voté (12 546 entrées pour 4 104
                                        # scrutins, 3,15 Mo de méta répété → 1,04 Mo).
                                        # L'index est le même que celui des profils : les 4 104
                                        # scrutins des groupes y sont tous inclus.
            "membres_eligibles": 64,    # membres en mandat à la date du scrutin
            "position_majoritaire": "contre",
            "pour": 42,
            "contre": 12,
            "abstention": 3,
            "non_votant": 2,
            "absents": 5,               # membres éligibles sans trace de vote
            "excuses": 0,               # absences notifiées/justifiées
            "taux_participation": 0.921,
            "taux_coherence": 0.656,    # alignés / membres_eligibles
            "taux_coherence_hors_absents": 0.847,  # alignés / (éligibles − absents − excusés)
            "quorum_atteint": true      # taux_participation ≥ seuil_quorum configuré
        }
    ],

    "tags_thematiques_agreges": [       # agrégation des tags individuels, triés par poids desc
        {
            "tag": "budget",
            "nb_membres_porteurs": 14,  # nombre de membres ayant ce tag
            "poids_relatif": 0.218      # nb_membres_porteurs / len(membres)
        }
    ],

    "mandats_agreges": [                # agrégation catégorielle des mandats[] (commission,
                                         # groupe_amitie, extra_parlementaire — voir
                                         # group_profile.MANDATS_AGREGES_CATEGORIES), liste plate
                                         # triée nb_membres_a_la_date_de_reference desc,
                                         # puis nb_membres_cumul_historique desc, puis
                                         # categorie/label asc (#656).
                                         # mandat_electif/groupe_politique/fonction_gouvernementale/
                                         # autre volontairement exclus (voir group_profile.py).
        {
            "categorie": "commission",
            "label": "Commission des affaires étrangères",
            # Deux grandeurs qui ne se confondent pas (#656) : « qui y siège »
            # et « qui y est passé ». 43 % des adhésions de commission publiées
            # durent une journée ou moins — un⋅e député⋅e n'appartient qu'à une
            # commission permanente à la fois, tout passage temporaire y est
            # donc écrit comme un mandat à part entière.
            "nb_membres_a_la_date_de_reference": 2,
                                         # QUI Y SIÈGE, à `date_reference.date` (#653) :
                                         # mandat ouvert à cette date ET appartenance au
                                         # groupe couvrant cette date. S'appelait
                                         # `nb_membres_actifs` et se lisait « aujourd'hui »,
                                         # ce qui, sur une fiche de législature close,
                                         # comptait les commissions ACTUELLES de membres
                                         # d'hier.
            "nb_membres_cumul_historique": 5,
                                         # QUI Y EST PASSÉ : membres distincts (éligibles, cf.
                                         # chevauchement mandat/appartenance) ayant occupé ce
                                         # mandat au moins une fois, adhésions d'un jour
                                         # comprises. Cumul, jamais un effectif.
            "effectif_reference": 64,    # dénominateur des deux compteurs = len(membres),
                                         # couverture disponible — jamais confondue avec
                                         # meta.couverture_roster.roster_total. Publié plutôt
                                         # que pré-divisé : « 2 / 64 », jamais « 3 % »
                                         # (AGENTS.md §2.7). Remplace poids_relatif, qui ne
                                         # disait pas de laquelle des deux grandeurs il
                                         # était le poids.
            "par_fonction": {            # une entrée par membre (tie-break sur doublon
                                         # (categorie, label) : actif=true prioritaire,
                                         # sinon la plus récente par date de fin)
                "membre": 3,
                "président": 1,
                "rapporteur": 1
            },
            "membres": [                 # traçabilité : qui, quelle fonction, quelle période
                {
                    "membre_id": "jerome-guedj",
                    "nom": "Jérôme Guedj",
                    "fonction": "président",
                    "debut": "2022-06-22",
                    "fin": null,
                    "actif": true
                }
            ]
        }
    ],

    "amendements_agreges": {            # tous types de déposants confondus — NE JAMAIS
                                         # comparer directement au taux d'un⋅e élu⋅e (voir
                                         # par_type_deposant ci-dessous)
        "nb_amendements": 120,
        "nb_adoptes": 18,
        "nb_rejetes": 74,
        "nb_irrecevables": 12,
        "nb_retires_ou_tombes": 16,
        "taux_adoption": 0.15,          # nb_adoptes / nb_amendements ; null si nb_amendements == 0
        "par_type_deposant": {          # comparateur valide du taux d'adoption individuel :
                                         # les amendements gouvernement/rapporteur sont adoptés
                                         # quasi systématiquement par construction — comparer un⋅e
                                         # élu⋅e à par_type_deposant["depute"], jamais au total
            "depute": { "nb_amendements": 98, "nb_adoptes": 6, "nb_rejetes": 70,
                        "nb_irrecevables": 12, "nb_retires_ou_tombes": 10, "taux_adoption": 0.0612 },
            "gouvernement": { "nb_amendements": 15, "nb_adoptes": 9, "nb_rejetes": 3,
                              "nb_irrecevables": 0, "nb_retires_ou_tombes": 3, "taux_adoption": 0.6 },
            "commission_rapporteur": { "nb_amendements": 7, "nb_adoptes": 3, "nb_rejetes": 1,
                                       "nb_irrecevables": 0, "nb_retires_ou_tombes": 3, "taux_adoption": 0.4286 },
            "inconnu": { "nb_amendements": 0, "nb_adoptes": 0, "nb_rejetes": 0,
                        "nb_irrecevables": 0, "nb_retires_ou_tombes": 0, "taux_adoption": null }
            # "inconnu" : amendements sans type_deposant renseigné — jamais rattachés par
            # défaut à "depute", pour ne pas masquer une donnée manquante
        }
    },

    "sources": [                        # traçabilité des sources individuelles agrégées
        {
            "type": "assemblee_nationale",
            "url": "https://data.assemblee-nationale.fr/",
            "synchro_le": "2026-07-29T10:00:00+0000"
        }
    ],

    "meta": {
        "schema_version": "1",
        "genere_le": "2026-07-29T10:00:00+0000",
        "licence_donnees": "ODbL …",
        "profils_sources": [            # ids pivot des profils individuels agrégés
            "jerome-guedj",
            "boris-vallaud"
        ],
        "seuil_quorum": 0.5,            # seuil de participation retenu pour quorum_atteint
        "warnings": [],
        # "couverture_roster" (optionnel, présent seulement si le groupe a été
        # construit via group_profile.py --from-roster) : {"roster_total": 62,
        # "profils_disponibles": 12} — nombre réel de membres du groupe (via
        # group_roster.py) vs. nombre de profils pivot locaux effectivement
        # chargés. Ne JAMAIS confondre avec effectif.a_la_date_de_reference (qui ne décrit que
        # les membres présents dans `profils`, pas le groupe réel).
}

Cas limites gérés :
- Élu qui change de groupe : membres[].fin_dans_groupe non null ; la cohésion
  n'utilise que les membres eligibles à la date de chaque scrutin.
- Groupe dissous/renommé : historique_noms[] + periode.fin non null.
- Scrutin sans quorum : quorum_atteint: false, cohésion toujours calculée.
- tags_thematiques vides : le calcul utilise les mots-clés des interventions
  individuelles en fallback (loggé dans meta.warnings).
- amendements_agreges.taux_adoption est null si aucun amendement n'est
  recensé sur les profils membres (nb_amendements == 0).
- amendements_agreges.par_type_deposant : un amendement sans type_deposant
  renseigné est classé sous "inconnu", jamais sous "depute" par défaut (une
  donnée manquante ne doit jamais se travestir en fait positif).
- mandats_agreges : doublon (categorie, label) pour un même membre → une
  seule entrée retenue par membre (priorité actif=true, sinon la plus
  récente par date de fin) ; voir group_profile._select_mandat_entree_unique.

Hors périmètre de ce schéma (volontairement) :
- Le ratio individuel de cohérence/participation rapporté à la moyenne du
  groupe est une donnée de contrôle interne (voir
  group_profile.compute_ecarts_cohesion_internes) : il n'est PAS exposé dans
  ce document public tant qu'il n'a pas été validé comme sortie publique.
- mandats_agreges se limite à MANDATS_AGREGES_CATEGORIES (commission,
  groupe_amitie, extra_parlementaire) : mandat_electif, groupe_politique,
  fonction_gouvernementale et autre sont volontairement exclus de la v1
  (raisons détaillées dans group_profile.py et #349/#361).

Usage :
    from schema_groupe import SCHEMA_GROUPE_VERSION, make_empty_profil_groupe, validate_profil_groupe
"""

import time
from typing import Any

from schema_pivot import (
    KNOWN_CHAMBRES,
    KNOWN_TYPES_DEPOSANT,
    POSITION_POLITIQUE_AN_VERS_PIVOT,
)

# Version du schéma de groupe ; indépendante de SCHEMA_VERSION du pivot individuel.
SCHEMA_GROUPE_VERSION = "1"

# Clés obligatoires au niveau racine du profil de groupe.
REQUIRED_TOP_LEVEL_KEYS: frozenset[str] = frozenset({
    "schema_version",
    "type_document",
    "groupe_id",
    "groupe_sigle",
    "groupe_nom",
    "chambre",
    "legislature",
    "periode",
    "historique_noms",
    "membres",
    "effectif",
    "cohesion_votes",
    "tags_thematiques_agreges",
    "mandats_agreges",
    "amendements_agreges",
    "sources",
    "meta",
})

# Clés obligatoires dans le bloc "meta".
REQUIRED_META_KEYS: frozenset[str] = frozenset({
    "schema_version",
    "genere_le",
    "licence_donnees",
    "profils_sources",
    "warnings",
})

# États de `meta.couverture_roster.etat` (#558).
#
# Le ratio seul ne dit pas de quoi il est le ratio. `groupe-Senat-LR.json`
# publie `{"roster_total": 235, "profils_disponibles": 15}` — 6,4 % — et rien à
# côté ne dit si les 220 manquants sont une collecte en retard ou un périmètre
# assumé. Ce sont les seconds : le Sénat est hors du périmètre éditorial du
# produit depuis #528, et l'extraction des deux groupes est suspendue depuis
# #516. Lu sans cet état, 15/235 se lit comme une perte.
#
# C'est la même règle que celle des cinq listes d'un profil (#539) appliquée au
# niveau du groupe : une absence produite par une décision se publie comme une
# décision, jamais comme un fait.
# Origines de `date_reference.origine` (#653).
#
# Une fiche de groupe décrit une législature, et aucune des 7 publiées ne décrit
# la législature en cours. Tout compteur ancré sur « aujourd'hui » y est donc
# vide de sens : `effectif.actuel` comptait les membres de la XVIe encore
# députés le jour du calcul — une propriété de leur carrière, pas du groupe.
#
# Tous les comptes d'une fiche se rapportent désormais à UNE date, publiée à
# côté d'eux. Elle est **dérivée**, jamais devinée : la clôture de la période du
# groupe quand toutes les appartenances sont refermées, la date de génération
# tant qu'au moins une reste ouverte. Un compteur daté qu'on ne peut pas dater à
# la lecture est un compteur nu (AGENTS.md §2 règle 2).
ORIGINE_DATE_REFERENCE_CLOTURE = "cloture_legislature"
ORIGINE_DATE_REFERENCE_GENERATION = "generation"
ORIGINES_DATE_REFERENCE: tuple[str, ...] = (
    ORIGINE_DATE_REFERENCE_CLOTURE,
    ORIGINE_DATE_REFERENCE_GENERATION,
)

# Position politique déclarée d'un groupe (#686).
#
# L'Assemblée nationale qualifie **elle-même** chacun de ses groupes dans le
# référentiel AMO30 (`organe.positionPolitique`). Ce champ recopie cette
# déclaration ; il n'en produit aucune. C'est ce qui l'autorise à figurer sur
# une fiche publiée sans contrevenir à la règle 1 d'AGENTS.md §2 — et c'est
# aussi ce qui interdit d'en déduire quoi que ce soit d'un comportement de
# vote, ce qui serait, cette fois, un jugement porté par ce dépôt.
#
# Deux valeurs n'existent pas dans le référentiel et sont **produites ici**,
# parce qu'un champ absent ne dit rien tandis qu'une valeur publiée dit
# quelque chose (AGENTS.md §2 règle 5) :
#
# - `non_declaree` : aucun organe du groupe ne porte de qualification. C'est
#   le cas des **14 groupes de la XVIIe législature** — l'AN ne qualifie ses
#   groupes qu'une fois la législature achevée. Ce n'est pas « pas de
#   position », c'est « position non déclarée par la source ».
# - `divergente` : deux organes successifs du même groupe dans la même
#   législature portent des qualifications **différentes**. Aucun des deux ne
#   l'emporte : choisir serait décider laquelle des deux moitiés de la
#   législature définit le groupe. Mesuré nul au 01/09/2026 (les deux organes
#   `SOC` de la XVIe sont tous deux `Opposition`) — publié quand même, parce
#   qu'un cas non prévu se replierait sinon sur le premier organe venu.
#
# Il n'y a **pas** de quatrième valeur produite : un groupe dont une partie des
# organes est qualifiée et l'autre muette prend la qualification déclarée, et
# le détail reste lisible dans `organes[]`, où l'organe muet porte
# `position: null`.
POSITION_GROUPE_NON_DECLAREE = "non_declaree"
POSITION_GROUPE_DIVERGENTE = "divergente"

#: Vocabulaire fermé de `position_politique.position`. Les trois premières
#: valeurs sont celles du référentiel, traduites par
#: `POSITION_POLITIQUE_AN_VERS_PIVOT` — les mêmes que
#: `mandats[].position_dans_hemicycle` d'un profil individuel, volontairement :
#: c'est la même déclaration, lue dans le même champ de la même archive.
POSITIONS_POLITIQUES_GROUPE: tuple[str, ...] = (
    *sorted(set(POSITION_POLITIQUE_AN_VERS_PIVOT.values())),
    POSITION_GROUPE_NON_DECLAREE,
    POSITION_GROUPE_DIVERGENTE,
)


def resumer_position_politique(organes: list[dict[str, Any]]) -> str:
    """Résume les déclarations organe par organe en **une** valeur publiable.

    Règle unique, et elle ne choisit jamais à la place de la source :

    - aucune déclaration → `non_declaree` ;
    - les organes qui déclarent disent tous la même chose → cette valeur ;
    - ils se contredisent → `divergente`.

    Fonction pure. C'est aussi l'invariant que `validate_profil_groupe`
    vérifie : un résumé que les déclarations ne portent pas est une
    qualification inventée, pas une qualification recopiée.
    """
    declarees = {
        o.get("position")
        for o in organes
        if isinstance(o, dict) and o.get("position")
    }
    if not declarees:
        return POSITION_GROUPE_NON_DECLAREE
    if len(declarees) == 1:
        return next(iter(declarees))
    return POSITION_GROUPE_DIVERGENTE


ETAT_ROSTER_DANS_LE_PERIMETRE = "dans_le_perimetre"
ETAT_ROSTER_HORS_PERIMETRE = "hors_perimetre"
ETATS_COUVERTURE_ROSTER: tuple[str, ...] = (
    ETAT_ROSTER_DANS_LE_PERIMETRE,
    ETAT_ROSTER_HORS_PERIMETRE,
)

# Champs dont la valeur doit être une liste.
_LIST_KEYS: tuple[str, ...] = (
    "historique_noms",
    "membres",
    "cohesion_votes",
    "tags_thematiques_agreges",
    "mandats_agreges",
    "sources",
)

# Ventilation de amendements_agreges par type de déposant. "inconnu" couvre les
# amendements sans type_deposant renseigné : ils ne doivent jamais être classés
# par défaut sous "depute", ce qui masquerait une donnée manquante.
AMENDEMENTS_TYPES_DEPOSANT: tuple[str, ...] = (*sorted(KNOWN_TYPES_DEPOSANT), "inconnu")


def make_empty_amendements_stats() -> dict[str, Any]:
    """Structure vide d'un bloc de statistiques d'amendements (total ou ventilation)."""
    return {
        "nb_amendements": 0,
        "nb_adoptes": 0,
        "nb_rejetes": 0,
        "nb_irrecevables": 0,
        "nb_retires_ou_tombes": 0,
        "taux_adoption": None,
    }


def make_empty_profil_groupe(
    groupe_id: str,
    groupe_sigle: str,
    groupe_nom: str,
    chambre: str | None,
    legislature: str | None,
) -> dict[str, Any]:
    """Crée un profil de groupe v1 vide avec des valeurs par défaut.

    Args:
        groupe_id: identifiant unique de la forme "<chambre>:<sigle>",
                   ex. "AN:SOC", "PE:S&D".
        groupe_sigle: sigle court du groupe (ex. "SOC", "LFI", "RN").
        groupe_nom: nom complet du groupe.
        chambre: "AN" | "Senat" | "PE" | "mairie" | None.
        legislature: numéro de législature (ex. "16") ou None.

    Returns:
        Profil de groupe dict initialisé, prêt à être enrichi par group_profile.py.
    """
    return {
        "schema_version": SCHEMA_GROUPE_VERSION,
        "type_document": "profil_groupe",
        "groupe_id": groupe_id,
        "groupe_sigle": groupe_sigle,
        "groupe_nom": groupe_nom,
        "chambre": chambre,
        "legislature": legislature,
        "periode": {
            "debut": None,
            "fin": None,
            "actif": True,
        },
        "historique_noms": [],
        "membres": [],
        "position_politique": None,
        "date_reference": None,
        "effectif": {
            "a_la_date_de_reference": 0,
            "min_historique": None,
            "max_historique": None,
        },
        "cohesion_votes": [],
        "tags_thematiques_agreges": [],
        "mandats_agreges": [],
        "amendements_agreges": {
            **make_empty_amendements_stats(),
            "par_type_deposant": {
                t: make_empty_amendements_stats() for t in AMENDEMENTS_TYPES_DEPOSANT
            },
        },
        "sources": [],
        "meta": {
            "schema_version": SCHEMA_GROUPE_VERSION,
            "genere_le": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "licence_donnees": "",
            "profils_sources": [],
            "seuil_quorum": 0.5,
            "warnings": [],
        },
    }


def _valider_couverture_roster(couverture: dict[str, Any]) -> list[str]:
    """Vérifie `meta.couverture_roster` (#558).

    `etat` reste **facultatif** : les fiches publiées avant ce lot n'en portent
    pas, et les déclarer invalides ne dirait rien de vrai sur elles — même
    précédent que `identifiants` et `couverture` côté pivot (#539). Présent, il
    est tenu à ses invariants.

    `preuve` est exigée sur `hors_perimetre`, et seulement là : dire qu'un
    groupe est hors périmètre sans dire par quelle décision est exactement le
    défaut que cet état existe pour corriger. Sur `dans_le_perimetre`, il n'y a
    rien à prouver — c'est le cas par défaut de tous les groupes collectés.
    """
    errors: list[str] = []
    etat = couverture.get("etat")
    if etat is None:
        return errors
    if etat not in ETATS_COUVERTURE_ROSTER:
        errors.append(
            f"'meta.couverture_roster.etat' non reconnu : {etat!r}. "
            f"Valeurs connues : {list(ETATS_COUVERTURE_ROSTER)}."
        )
        return errors
    preuve = couverture.get("preuve")
    if etat == ETAT_ROSTER_HORS_PERIMETRE:
        if not (isinstance(preuve, str) and preuve.strip()):
            errors.append(
                "'meta.couverture_roster.preuve' est obligatoire sur un "
                f"'{ETAT_ROSTER_HORS_PERIMETRE}' : elle nomme la décision qui "
                "sort ce groupe du périmètre (#516/#528). Sans elle, le ratio "
                "publié redevient indistinct d'une collecte en échec."
            )
    elif preuve is not None and not isinstance(preuve, str):
        errors.append("'meta.couverture_roster.preuve' doit être une chaîne.")
    return errors


def _valider_position_politique(bloc: dict[str, Any]) -> list[str]:
    """Vérifie `position_politique` (#686) : recopie déclarée, jamais résumé libre.

    Quatre invariants, et le dernier est le seul qui compte vraiment :

    1. `position` appartient au vocabulaire fermé ;
    2. `source_url` est présente — y compris sur `non_declaree`, parce qu'un
       constat d'absence nomme sa source comme un constat de présence ;
    3. `verifie_le` est présente — une qualification non datée ne se relit pas,
       même règle que `verifie_le` de la table de correspondance (#526) ;
    4. `position` est **exactement** ce que `organes[]` porte
       (`resumer_position_politique`). C'est l'invariant qui interdit de
       publier une posture que les déclarations de la source ne portent pas :
       replier deux organes divergents sur l'un des deux, ou repêcher une
       posture pour un groupe que l'AN n'a pas qualifié, deviennent des erreurs
       de schéma et non des choix d'implémentation.
    """
    errors: list[str] = []
    position = bloc.get("position")
    if position not in POSITIONS_POLITIQUES_GROUPE:
        errors.append(
            f"'position_politique.position' non reconnue : {position!r}. "
            f"Valeurs connues : {list(POSITIONS_POLITIQUES_GROUPE)}."
        )
    source_url = bloc.get("source_url")
    if not (isinstance(source_url, str) and source_url.strip()):
        errors.append(
            "'position_politique.source_url' est obligatoire : la qualification "
            "est celle de l'Assemblée, elle doit pointer vers le référentiel qui "
            "la porte (AGENTS.md §2 règle 2). Vaut aussi pour "
            f"'{POSITION_GROUPE_NON_DECLAREE}' — un constat d'absence nomme sa source."
        )
    if not bloc.get("verifie_le"):
        errors.append(
            "'position_politique.verifie_le' est absente : une qualification non "
            "datée n'est pas relisible (#526)."
        )

    organes = bloc.get("organes")
    if not isinstance(organes, list):
        errors.append("'position_politique.organes' doit être une liste.")
        return errors

    for i, organe in enumerate(organes):
        if not isinstance(organe, dict):
            errors.append(f"'position_politique.organes[{i}]' doit être un objet.")
            continue
        organe_an = organe.get("organe_an")
        if not (isinstance(organe_an, str) and organe_an.startswith("PO")):
            errors.append(
                f"'position_politique.organes[{i}].organe_an' doit être un uid "
                f"d'organe AN (PO######), reçu : {organe_an!r}."
            )
        pos_organe = organe.get("position")
        if pos_organe is not None and pos_organe not in POSITION_POLITIQUE_AN_VERS_PIVOT.values():
            errors.append(
                f"'position_politique.organes[{i}].position' non reconnue : "
                f"{pos_organe!r}. Un organe porte la qualification du référentiel "
                f"({sorted(set(POSITION_POLITIQUE_AN_VERS_PIVOT.values()))}) ou `null` — "
                f"jamais '{POSITION_GROUPE_NON_DECLAREE}' ni '{POSITION_GROUPE_DIVERGENTE}', "
                "qui résument plusieurs organes et n'en décrivent aucun."
            )
        valeur_source = organe.get("valeur_source")
        if "valeur_source" not in organe:
            errors.append(
                f"'position_politique.organes[{i}].valeur_source' absente : c'est "
                "la preuve, la chaîne du référentiel telle quelle."
            )
        elif valeur_source is None and pos_organe is not None:
            errors.append(
                f"'position_politique.organes[{i}]' traduit une qualification que "
                "la source ne porte pas (`valeur_source` null)."
            )
        elif valeur_source is not None and (
            POSITION_POLITIQUE_AN_VERS_PIVOT.get(valeur_source) != pos_organe
        ):
            errors.append(
                f"'position_politique.organes[{i}]' : {valeur_source!r} ne se "
                f"traduit pas en {pos_organe!r} (voir POSITION_POLITIQUE_AN_VERS_PIVOT)."
            )

    attendu = resumer_position_politique(organes)
    if position in POSITIONS_POLITIQUES_GROUPE and position != attendu:
        errors.append(
            f"'position_politique.position' vaut {position!r} alors que les "
            f"déclarations publiées dans 'organes' donnent {attendu!r}. Le résumé "
            "est dérivé des déclarations, jamais choisi (#686)."
        )
    return errors


def validate_profil_groupe(profil: dict[str, Any]) -> list[str]:
    """Vérifie les invariants de base du schéma de groupe v1.

    Validation structurelle de premier niveau : présence des clés obligatoires,
    types, valeur de schema_version et type_document. Ne valide pas le contenu
    de chaque entrée cohesion_votes ou membre.

    Args:
        profil: dict à valider.

    Returns:
        Liste d'erreurs (liste vide = profil valide).
    """
    errors: list[str] = []

    if not isinstance(profil, dict):
        return [f"Le profil de groupe doit être un dict, reçu : {type(profil).__name__}."]

    missing = REQUIRED_TOP_LEVEL_KEYS - set(profil.keys())
    if missing:
        errors.append(f"Clés manquantes au niveau racine : {sorted(missing)}.")

    version = profil.get("schema_version")
    if version != SCHEMA_GROUPE_VERSION:
        errors.append(
            f"schema_version inattendu : {version!r} (attendu : {SCHEMA_GROUPE_VERSION!r})."
        )

    if profil.get("type_document") != "profil_groupe":
        errors.append(
            f"'type_document' doit être 'profil_groupe', reçu : {profil.get('type_document')!r}."
        )

    if not profil.get("groupe_id"):
        errors.append("'groupe_id' est vide ou absent.")

    chambre = profil.get("chambre")
    if chambre is not None and chambre not in KNOWN_CHAMBRES:
        errors.append(
            f"'chambre' non reconnue : {chambre!r}. Valeurs connues : {sorted(KNOWN_CHAMBRES)}."
        )

    for key in _LIST_KEYS:
        val = profil.get(key)
        if val is not None and not isinstance(val, list):
            errors.append(f"'{key}' doit être une liste, reçu : {type(val).__name__}.")

    periode = profil.get("periode")
    if not isinstance(periode, dict):
        errors.append("'periode' doit être un dict.")

    # `position_politique` est OPTIONNELLE, jamais obligatoire (#686) : les 7
    # fiches publiées avant le lot ne la portent pas, et les 2 `groupe-Senat-*`
    # ne la porteront jamais — le référentiel AMO30 ne qualifie que des groupes
    # de l'Assemblée. Même précédent que `date_reference` (#653) et
    # `couverture_roster.etat` (#558) : l'exiger ferait échouer le portail de
    # qualité sur du publié qui ne sera pas régénéré.
    position_politique = profil.get("position_politique")
    if position_politique is not None:
        if not isinstance(position_politique, dict):
            errors.append("'position_politique' doit être un dict ou null.")
        else:
            errors.extend(_valider_position_politique(position_politique))

    # `date_reference` est OPTIONNELLE, jamais obligatoire (#653) : les 2 fiches
    # `groupe-Senat-*` publiées avant le lot ne la portent pas et ne seront pas
    # régénérées (extraction suspendue, #516). L'exiger les ferait échouer au
    # portail de qualité, qui hard-fail sur un schéma de groupe invalide — une
    # migration ne se paie pas en cassant ce qui est déjà publié. Présente, elle
    # est validée : une origine hors vocabulaire est un compteur mal daté.
    date_reference = profil.get("date_reference")
    if date_reference is not None:
        if not isinstance(date_reference, dict):
            errors.append("'date_reference' doit être un dict ou null.")
        else:
            origine = date_reference.get("origine")
            if origine not in ORIGINES_DATE_REFERENCE:
                errors.append(
                    f"'date_reference.origine' non reconnue : {origine!r}. "
                    f"Valeurs connues : {sorted(ORIGINES_DATE_REFERENCE)}."
                )
            if not date_reference.get("date"):
                errors.append("'date_reference.date' est vide ou absente.")

    amendements_agreges = profil.get("amendements_agreges")
    if amendements_agreges is not None and not isinstance(amendements_agreges, dict):
        errors.append("'amendements_agreges' doit être un dict.")
    elif isinstance(amendements_agreges, dict):
        par_type = amendements_agreges.get("par_type_deposant")
        if par_type is not None and not isinstance(par_type, dict):
            errors.append("'amendements_agreges.par_type_deposant' doit être un dict.")

    meta = profil.get("meta")
    if not isinstance(meta, dict):
        errors.append("'meta' doit être un dict.")
    else:
        missing_meta = REQUIRED_META_KEYS - set(meta.keys())
        if missing_meta:
            errors.append(f"Clés manquantes dans 'meta' : {sorted(missing_meta)}.")
        if meta.get("schema_version") != SCHEMA_GROUPE_VERSION:
            errors.append(
                f"meta.schema_version inattendu : {meta.get('schema_version')!r} "
                f"(attendu : {SCHEMA_GROUPE_VERSION!r})."
            )
        if not isinstance(meta.get("warnings"), list):
            errors.append("'meta.warnings' doit être une liste.")
        if not isinstance(meta.get("profils_sources"), list):
            errors.append("'meta.profils_sources' doit être une liste.")
        couverture_roster = meta.get("couverture_roster")
        if couverture_roster is not None and not isinstance(couverture_roster, dict):
            errors.append("'meta.couverture_roster' doit être un dict.")
        elif isinstance(couverture_roster, dict):
            errors.extend(_valider_couverture_roster(couverture_roster))

    return errors
