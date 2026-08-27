#!/usr/bin/env python3
"""
group_profile.py — Agrégation de profils individuels en profil de groupe politique.

Ce module calcule, à partir d'une liste de profils pivot v1 (schéma_pivot.py),
un profil de groupe conforme au schéma_groupe.py. Il ne fait aucun appel réseau :
il agrège uniquement les données déjà présentes dans les profils individuels.

Calculs produits :
  1. Cohésion de vote : par scrutin, position majoritaire du groupe + taux
     d'alignement. « Absent » (aucune trace de vote) est distingué de
     « non_votant » et « excusé ».
  2. Thèmes dominants : agrégation des tags_thematiques de tous les membres.
  3. Membres : liste avec dates d'entrée/sortie du groupe (dérivées des mandats
     électifs des profils individuels).
  4. Amendements agrégés (amendements_agreges) : taux d'adoption groupe/chambre,
     ventilé par type de déposant (par_type_deposant) — le total tous déposants
     confondus ne doit jamais servir de comparateur direct, seul le sous-total
     "depute" est de même nature que les amendements d'un⋅e élu⋅e.
  5. Mandats agrégés (mandats_agreges) : agrégation catégorielle sur mandats[]
     (commission, groupe_amitie, extra_parlementaire — voir
     MANDATS_AGREGES_CATEGORIES), par (categorie, label). Éligibilité par
     chevauchement d'intervalles avec les mandats électifs du membre.
  6. Écarts de cohésion/participation individuels (compute_ecarts_cohesion_internes) :
     donnée de CONTRÔLE INTERNE uniquement, volontairement absente du schéma de
     groupe public — accessible via --rapport-interne, jamais via --out.

Cas limites gérés :
  - Élu qui change de groupe en cours de mandat : seuls les membres dont la
    période de mandat électif inclut la date du scrutin sont comptés comme
    éligibles. Les mandats multiples (sur plusieurs législatures) sont tous
    examinés.
  - Groupe dissous/renommé : le groupe_id et groupe_nom sont des paramètres
    explicites ; le champ historique_noms est laissé à renseigner manuellement.
  - Scrutin sans quorum : quorum_atteint = False, cohésion toujours calculée.
  - tags_thematiques vides sur les profils individuels : fallback automatique
    sur les mots-clés des interventions (loggé dans meta.warnings).
  - mandats_agreges : doublon (categorie, label) pour un même membre (ex.
    réélu·e à la même commission) → une seule entrée retenue, priorité à
    actif=true sinon la plus récente par date de fin.

Usage (depuis la racine du dépôt) :
    python src/group_profile.py \\
        --groupe-id "AN:SOC" \\
        --groupe-sigle SOC \\
        --groupe-nom "Socialistes et apparentés" \\
        --chambre AN \\
        --legislature 16 \\
        pivot_data/profiles/jerome-guedj.pivot.json \\
        pivot_data/profiles/boris-vallaud.pivot.json \\
        --out pivot_data/groupes/groupe-SOC-16.json

    Les profils en entrée peuvent être au format brut (candidate_profile.py)
    ou au format pivot v1 (normalize_profil.py). Le script détecte automatiquement
    le format et normalise si nécessaire.

Mode --from-roster (composition réelle du groupe, via group_roster.py) :
    Récupère la vraie liste des membres du groupe parlementaire depuis le
    référentiel AMO30 de l'Assemblée nationale (voir group_roster.py et
    an_roster.py) puis charge le pivot local de chaque membre trouvé dans
    --profiles-dir (pivot_data/profiles/<slug>.pivot.json).
    Les membres du roster sans pivot local sont ignorés et signalés dans
    meta.warnings ; la couverture réelle (roster_total / profils_disponibles)
    est inscrite dans meta.couverture_roster, jamais confondue avec effectif.actuel.

    python src/group_profile.py \\
        --from-roster --roster-chambre deputes \\
        --groupe-id "AN:LR" --groupe-sigle LR --groupe-nom "Les Républicains" \\
        --chambre AN --legislature 16 \\
        --out pivot_data/groupes/groupe-AN-LR-16.json

    NB : distinct de parti_profile.py, qui agrège les candidats présidentiels
    déclarés partageant un même label de parti (raw_data/candidats.json) — un
    échantillon éditorial, pas un groupe parlementaire.
"""

import argparse
import json
import sys
import time
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any, Optional

from licences import appliquer_licence_donnees
from schema_groupe import (
    SCHEMA_GROUPE_VERSION,
    AMENDEMENTS_TYPES_DEPOSANT,
    make_empty_profil_groupe,
    make_empty_amendements_stats,
    validate_profil_groupe,
)
from merge_profile import load_existing_document, preserve_stable_freshness_timestamps
from normalize_profil import normalize_profil
from amendements_index import (
    AmendementsIndex,
    DEFAULT_AMENDEMENTS_DIR,
    charger as charger_amendements,
    joindre as joindre_amendements,
)
from scrutins_index import ScrutinsIndex, charger as charger_scrutins, decomposer_id, DEFAULT_SCRUTINS_PATH


# ---------------------------------------------------------------------------
# Helpers de dates
# ---------------------------------------------------------------------------

def _parse_date(s: Any) -> Optional[date]:
    """Parse une chaîne ISO-8601 (YYYY-MM-DD ou sous-préfixe) en date, sans lever."""
    if not s or not isinstance(s, str):
        return None
    try:
        return date.fromisoformat(s[:10])
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Eligibilité d'un membre à un scrutin
# ---------------------------------------------------------------------------

def _mandats_electifs(
    mandats: list[dict[str, Any]], chambre: Optional[str] = None
) -> list[dict[str, Any]]:
    """Mandats électifs d'un membre, restreints à la chambre du groupe (#492).

    ``_member_eligibility_intervals`` prenait l'**union** de tous les
    `mandat_electif`, sans distinction de chambre. Un mandat sénatorial ne peut
    pas chevaucher un mandat AN (incompatibilité constitutionnelle), donc dans
    le cas général l'union est inoffensive ; le cas dangereux est le
    **changement de chambre en cours de législature**, qui prolongerait la
    fenêtre d'éligibilité au-delà du départ de l'Assemblée et compterait le
    membre absent sur des scrutins qu'il ne pouvait plus voter — un dénominateur
    de cohésion faux (§2.7). Le filtre n'était pas écrivable avant #492 : la
    chambre n'était portée par aucun mandat.

    **Un mandat à `chambre: null` est conservé**, jamais écarté. L'écarter
    réduirait un dénominateur publié sur la foi d'une donnée absente, ce qui est
    l'erreur exactement symétrique de celle qu'on corrige. Conséquence directe :
    sur un corpus entièrement non estampillé — celui d'aujourd'hui, 214 des 228
    `mandat_electif` mesurés sur `f5a828b` — ce filtre ne change **aucun**
    dénominateur publié. La correction entre en vigueur au fil de la collecte,
    mandat par mandat, jamais d'un coup.

    ``chambre=None`` (groupe sans chambre, ou appel hors contexte de groupe) ne
    filtre rien.
    """
    electif = [m for m in mandats if m.get("categorie") == "mandat_electif"]
    if chambre is None:
        return electif
    return [m for m in electif if m.get("chambre") in (None, chambre)]


def _member_eligibility_intervals(
    mandats: list[dict[str, Any]], chambre: Optional[str] = None
) -> Optional[list[tuple[Optional[date], Optional[date]]]]:
    """Pré-analyse les mandats électifs d'un membre en intervalles (début, fin).

    Évite de refiltrer ``mandats`` et de reparser les dates de mandat à chaque
    scrutin dans ``_compute_cohesion_votes`` (le même membre est testé pour des
    milliers de scrutins). Retourne None si aucun mandat électif n'est renseigné
    (éligibilité par défaut, cf. ``_member_eligible_at``).

    ``chambre`` : chambre du groupe, voir ``_mandats_electifs`` (#492). Deux
    absences y sont distinguées, et elles n'ont pas le même sens :

    - **aucun mandat électif du tout** → ``None``, éligibilité par défaut :
      absence d'information, on ne peut pas exclure (comportement historique) ;
    - **des mandats électifs, mais aucun dans cette chambre** → ``[]``, donc
      jamais éligible : ce n'est pas une absence d'information, c'est
      l'information que ce membre ne siège pas dans cette chambre. Le compter au
      dénominateur d'une cohésion qu'il ne pouvait pas voter serait précisément
      le défaut que #492 corrige. Cas impossible tant qu'aucun mandat n'est
      estampillé — un mandat à ``null`` est conservé par ``_mandats_electifs``.
    """
    if not any(m.get("categorie") == "mandat_electif" for m in mandats):
        return None
    return [
        (_parse_date(m.get("debut")), _parse_date(m.get("fin")))
        for m in _mandats_electifs(mandats, chambre)
    ]


def _is_eligible_at(intervals: Optional[list[tuple[Optional[date], Optional[date]]]], d: Optional[date]) -> bool:
    """Vérifie l'éligibilité à partir d'une date et d'intervalles déjà parsés."""
    if d is None or intervals is None:
        return True  # date/mandats inconnus → on ne peut pas exclure
    for debut, fin in intervals:
        if debut is not None and d < debut:
            continue
        if fin is not None and d > fin:
            continue
        return True  # le membre était en mandat à cette date
    return False


def _intervals_overlap(
    a_debut: Optional[date],
    a_fin: Optional[date],
    b_debut: Optional[date],
    b_fin: Optional[date],
) -> bool:
    """Teste le chevauchement de deux intervalles [a_debut, a_fin] et [b_debut, b_fin].

    Bornes ``None`` traitées comme non bornées, même sémantique que ``_is_eligible_at``.
    """
    if a_debut is not None and b_fin is not None and a_debut > b_fin:
        return False
    if a_fin is not None and b_debut is not None and a_fin < b_debut:
        return False
    return True


def _member_eligible_at(
    mandats: list[dict[str, Any]], vote_date: Optional[str], chambre: Optional[str] = None
) -> bool:
    """Détermine si un membre était en mandat (éligible à voter) à la date du scrutin.

    Un membre est éligible si au moins un de ses mandats électifs est actif à
    ``vote_date``. Si la date est absente ou non parseable, le membre est
    considéré éligible par défaut (approche conservatrice).

    Args:
        mandats: liste des mandats du profil pivot (champ ``mandats[]``).
        vote_date: date du scrutin au format "YYYY-MM-DD", ou None.
        chambre: chambre du groupe, voir ``_mandats_electifs`` (#492).

    Returns:
        True si le membre est éligible pour ce scrutin.
    """
    return _is_eligible_at(
        _member_eligibility_intervals(mandats, chambre), _parse_date(vote_date)
    )


# ---------------------------------------------------------------------------
# Construction de l'entrée membre
# ---------------------------------------------------------------------------

def _derive_membre_entry(
    profil: dict[str, Any], chambre: Optional[str] = None
) -> dict[str, Any]:
    """Dérive une entrée ``membres[]`` du profil de groupe à partir d'un profil pivot.

    La date de début dans le groupe correspond au début du premier mandat électif ;
    la fin correspond à la fin du dernier mandat électif terminé (None si toujours
    actif). Cette approximation est correcte pour les cas sans changement de groupe
    en cours de mandat.

    ``chambre`` (#492) restreint les mandats électifs pris en compte à ceux de
    la chambre du groupe : sans ça, `debut_dans_groupe` d'un membre bicaméral
    remonterait à son mandat dans **l'autre** chambre. Voir ``_mandats_electifs``.

    Args:
        profil: profil pivot v1.

    Returns:
        Dict conformant à la structure membres[] du schéma de groupe.
    """
    electif = _mandats_electifs(profil.get("mandats") or [], chambre)

    debut: Optional[str] = None
    fin: Optional[str] = None
    actif = False

    if electif:
        debuts = [_parse_date(m.get("debut")) for m in electif]
        fins = [_parse_date(m.get("fin")) for m in electif]
        actifs = [bool(m.get("actif")) for m in electif]

        parsed_debuts = [d for d in debuts if d is not None]
        if parsed_debuts:
            debut = str(min(parsed_debuts))

        # La fin est None si au moins un mandat est toujours actif.
        if any(actifs) or any(f is None for f in fins):
            fin = None
        else:
            parsed_fins = [f for f in fins if f is not None]
            fin = str(max(parsed_fins)) if parsed_fins else None

        actif = any(actifs)

    return {
        "membre_id": profil.get("id") or "",
        "nom": profil.get("nom") or "",
        "debut_dans_groupe": debut,
        "fin_dans_groupe": fin,
        "actif": actif,
    }


# ---------------------------------------------------------------------------
# Index de votes par membre
# ---------------------------------------------------------------------------

def _votes_de_legislature(
    profil: dict[str, Any], legislature: Optional[str]
) -> list[dict[str, Any]]:
    """Votes d'un profil restreints à la législature du groupe.

    Depuis #403, un profil individuel porte les votes de **toutes** les
    législatures où l'élu a siégé (14 à 17), alors qu'un profil de groupe en
    couvre exactement une. Sans ce filtre, la cohésion d'un groupe de la 16e
    agrégerait les scrutins de la 17e dès qu'un membre y siège encore — un
    scrutin serait attribué à un groupe qui n'existait pas au moment du vote.

    Depuis #432 la législature se lit dans `scrutin_id` (`an:16:4084`), et le
    filtre est **exact**. Il l'était mal avant : un vote sans `legislature`
    était conservé pour n'importe quelle législature de groupe
    (`v.get("legislature") or legislature`), ce qui était juste tant que tous
    les groupes étaient de la 16e — les 89 687 votes concernés en venaient tous
    — mais aurait fait absorber ces mêmes votes par un groupe de la 17e. Le
    repli n'est levé qu'ici, une fois la législature effectivement résolue sur
    les données : le lever plus tôt aurait retiré ces 89 687 votes de la
    cohésion de la 16e, ce qui aurait été une régression, pas une correction.

    Un vote sans `scrutin_id` (scrutin non résolu, `scrutin_non_resolu`) est
    **écarté** : il n'est rattachable à aucune législature. L'appelant en
    compte le nombre et le remonte en warning — écarté, jamais silencieux.

    Un groupe sans législature (Sénat) ne filtre rien.
    """
    votes = profil.get("votes") or []
    if not legislature:
        return list(votes)
    retenus = []
    for v in votes:
        legislature_vote, _ = decomposer_id(v.get("scrutin_id"))
        if legislature_vote == str(legislature):
            retenus.append(v)
    return retenus


def _votes_non_resolus(profils: list[dict[str, Any]]) -> int:
    """Nombre de votes qu'aucun identifiant ne rattache à une législature.

    Zéro sur les données mesurées au 19/08/2026. Compté quand même, et remonté :
    c'est exactement le genre d'exclusion qui, muette, transformerait un
    dénominateur en donnée fausse (AGENTS.md §2.7)."""
    return sum(
        1
        for profil in profils
        for v in (profil.get("votes") or [])
        if not v.get("scrutin_id")
    )


def _build_vote_index(
    profil: dict[str, Any], legislature: Optional[str] = None
) -> dict[str, dict[str, Any]]:
    """Construit un index {scrutin_id → vote_dict} pour un profil individuel.

    Permet une recherche O(1) lors du calcul de cohésion. La clé est
    `scrutin_id` depuis #432 : elle porte déjà la législature, là où
    `numero_scrutin` seul faisait écraser le scrutin n° 1000 de la 16e par celui
    de la 17e — deux textes sans rapport. `legislature` reste appliqué en amont
    pour ne retenir que les scrutins du groupe.
    """
    index: dict[str, dict[str, Any]] = {}
    for v in _votes_de_legislature(profil, legislature):
        scrutin_id = v.get("scrutin_id")
        if scrutin_id:
            index[str(scrutin_id)] = v
    return index


# ---------------------------------------------------------------------------
# Calcul de cohésion
# ---------------------------------------------------------------------------

def _compute_cohesion_votes(
    profils: list[dict[str, Any]],
    seuil_quorum: float = 0.5,
    legislature: Optional[str] = None,
    scrutins_index: Optional[ScrutinsIndex] = None,
    chambre: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Calcule la cohésion de vote pour chaque scrutin couvert par les membres.

    Algorithme :
      1. Collecte tous les scrutins distincts (par numero_scrutin) rencontrés
         dans les profils membres.
      2. Pour chaque scrutin, détermine les membres éligibles (en mandat à la
         date du scrutin).
      3. Comptabilise les positions : pour / contre / abstention / non_votant /
         excusé / absent (implicite = pas de vote trouvé pour ce scrutin).
      4. Calcule la position majoritaire sur les votes exprimés, les taux de
         participation et de cohérence.

    Args:
        profils: liste de profils pivot v1 des membres du groupe.
        seuil_quorum: seuil de taux_participation au-delà duquel quorum_atteint
                      est True (défaut : 0.5).
        legislature: législature du groupe (ex. "16"), qui restreint les
                     scrutins retenus — voir ``_votes_de_legislature``. None
                     (Sénat, ou groupe sans législature) ne filtre rien.
        scrutins_index: index partagé (#432). La `date` d'un scrutin n'est plus
                     dans le profil : elle est nécessaire à l'éligibilité des
                     membres, donc un scrutin absent de l'index est écarté du
                     calcul plutôt que compté sur une date inventée.
        chambre: chambre du groupe ("AN" | "Senat" | …). Restreint les mandats
                     électifs qui ouvrent la fenêtre d'éligibilité à ceux de
                     cette chambre — un dénominateur publié (§2.7) ne doit pas
                     être élargi par un mandat d'une autre chambre. Voir
                     ``_mandats_electifs`` (#492).

    Returns:
        Liste de dicts conformes à la structure cohesion_votes[], triée par date
        décroissante. Les entrées ne portent plus `date`/`texte`/`sort` : ces
        champs sont ceux du scrutin, ils vivent dans l'index (#432).
    """
    # --- 1. Collecte de tous les scrutins ---
    # Clé : scrutin_id → date du scrutin, lue dans l'index partagé. Un scrutin
    # inconnu de l'index n'est pas datable, donc ses membres ne sont pas
    # éligibles de façon vérifiable : il est écarté, et compté comme tel.
    scrutins: dict[str, Optional[str]] = {}
    scrutins_hors_index: set[str] = set()
    for profil in profils:
        for v in _votes_de_legislature(profil, legislature):
            scrutin_id = v.get("scrutin_id")
            if not scrutin_id or scrutin_id in scrutins or scrutin_id in scrutins_hors_index:
                continue
            scrutin = scrutins_index.get(scrutin_id) if scrutins_index is not None else None
            if scrutin is None:
                scrutins_hors_index.add(scrutin_id)
                continue
            scrutins[scrutin_id] = scrutin.get("date")

    if scrutins_hors_index:
        print(
            f"  [!] {len(scrutins_hors_index)} scrutin(s) référencés par les membres mais "
            f"absents de l'index partagé, écartés de la cohésion : "
            f"{sorted(scrutins_hors_index)[:5]}"
        )

    if not scrutins:
        return []

    # --- 2. Index de votes par membre + intervalles d'éligibilité pré-analysés ---
    # Précalculés une seule fois (au lieu de reparser les dates de mandat à chaque
    # scrutin) : un groupe de N membres et M scrutins ferait sinon O(M x N) reparsing
    # de dates au lieu de O(N) ici + une comparaison de dates déjà parsées par scrutin.
    vote_indexes = [_build_vote_index(p, legislature) for p in profils]
    eligibility_intervals = [
        _member_eligibility_intervals(p.get("mandats") or [], chambre) for p in profils
    ]

    # --- 3. Calcul par scrutin ---
    _EXPRESSED = ("pour", "contre", "abstention")

    cohesion: list[dict[str, Any]] = []
    for scrutin_id, vote_date in scrutins.items():
        parsed_vote_date = _parse_date(vote_date)

        compteurs: dict[str, int] = {
            "pour": 0, "contre": 0, "abstention": 0,
            "non_votant": 0, "absent": 0, "excuse": 0,
        }
        n_eligible = 0

        for v_index, intervals in zip(vote_indexes, eligibility_intervals):
            if not _is_eligible_at(intervals, parsed_vote_date):
                continue
            n_eligible += 1

            vote = v_index.get(scrutin_id)
            if vote is None:
                compteurs["absent"] += 1
            else:
                pos = vote.get("position") or "absent"
                compteurs[pos] = compteurs.get(pos, 0) + 1

        if n_eligible == 0:
            continue

        # Position majoritaire sur les votes exprimés (pour/contre/abstention).
        # Note : en cas d'égalité stricte entre deux positions (ex. 10 pour /
        # 10 contre), max() retourne conventionnellement la première position
        # de _EXPRESSED à égalité de score, soit l'ordre "pour" > "contre" >
        # "abstention". Ce choix arbitraire mais déterministe est documenté ici
        # plutôt que de renvoyer None sur égalité, ce qui casserait la lecture
        # simple du taux de cohérence pour ces scrutins (rares en pratique).
        votes_exprimes = sum(compteurs[p] for p in _EXPRESSED)
        if votes_exprimes == 0:
            position_majoritaire = None
        else:
            position_majoritaire = max(_EXPRESSED, key=lambda p: compteurs[p])

        # Taux de participation (éligibles ayant une trace de vote)
        n_absent = compteurs["absent"] + compteurs["excuse"]
        taux_participation = (n_eligible - n_absent) / n_eligible

        # Taux de cohérence
        if position_majoritaire is not None:
            alignes = compteurs[position_majoritaire]
            taux_coherence: Optional[float] = alignes / n_eligible
            voted = n_eligible - n_absent
            taux_coherence_hors_absents: Optional[float] = (
                alignes / voted if voted > 0 else None
            )
        else:
            taux_coherence = None
            taux_coherence_hors_absents = None

        cohesion.append({
            # `date`, `texte` et `sort` ont migré vers l'index partagé (#432) :
            # ce sont des champs du SCRUTIN, recopiés jusque-là dans chacun des
            # 5 groupes qui l'ont voté (12 546 entrées pour 4 104 scrutins,
            # 3,15 Mo de méta répété ramenés à 1,04 Mo une seule fois).
            "scrutin_id": scrutin_id,
            "membres_eligibles": n_eligible,
            "position_majoritaire": position_majoritaire,
            "pour": compteurs["pour"],
            "contre": compteurs["contre"],
            "abstention": compteurs["abstention"],
            "non_votant": compteurs["non_votant"],
            "absents": compteurs["absent"],
            "excuses": compteurs["excuse"],
            "taux_participation": round(taux_participation, 4),
            "taux_coherence": (
                round(taux_coherence, 4) if taux_coherence is not None else None
            ),
            "taux_coherence_hors_absents": (
                round(taux_coherence_hors_absents, 4)
                if taux_coherence_hors_absents is not None
                else None
            ),
            "quorum_atteint": taux_participation >= seuil_quorum,
        })

    # Tri par date décroissante (scrutins récents en premier). La date n'étant
    # plus dans l'entrée, elle est relue dans l'index — l'ordre publié reste
    # celui qu'attendent les consommateurs.
    cohesion.sort(key=lambda x: scrutins.get(x["scrutin_id"]) or "", reverse=True)
    return cohesion


# ---------------------------------------------------------------------------
# Agrégation des tags thématiques
# ---------------------------------------------------------------------------

def aggregate_tags_thematiques(
    profils: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], Optional[str]]:
    """Agrège les tags thématiques de tous les profils membres.

    Stratégie : utilise ``tags_thematiques`` de chaque profil individuel.
    Si un profil a ``tags_thematiques`` vide, ses interventions sont consultées
    en fallback : d'abord ``interventions[].theme_officiel`` (débats officiels
    Syceron), puis ``interventions[].mots_cles`` (scraping NosDéputés).
    Les deux sources peuvent coexister dans le même appel si les profils sont
    hétérogènes (``tag_source`` vaut alors "mixed").

    Args:
        profils: liste de profils pivot v1.

    Returns:
        Tuple (liste triée par nb_membres_porteurs desc, tag_source).
        ``tag_source`` vaut "tags_thematiques", "theme_officiel",
        "mots_cles_interventions" ou "mixed".
    """
    n = len(profils)
    if n == 0:
        return [], None

    tag_counts: dict[str, int] = {}  # tag → nombre de membres porteurs
    sources_used: set[str] = set()

    for profil in profils:
        tags = list(profil.get("tags_thematiques") or [])
        if tags:
            sources_used.add("tags_thematiques")
        else:
            # Fallback : thèmes officiels Syceron en priorité, mots-clés scraping sinon
            kw_set: set[str] = set()
            theme_set: set[str] = set()
            for interv in (profil.get("interventions") or []):
                theme = interv.get("theme_officiel")
                if theme and isinstance(theme, str):
                    cleaned = theme.strip().lower()
                    if cleaned:
                        theme_set.add(cleaned)
                else:
                    for kw in (interv.get("mots_cles") or []):
                        cleaned = kw.strip().lower() if isinstance(kw, str) else ""
                        if cleaned:
                            kw_set.add(cleaned)
            if theme_set:
                tags = list(theme_set)
                sources_used.add("theme_officiel")
            elif kw_set:
                tags = list(kw_set)
                sources_used.add("mots_cles_interventions")

        # Un tag compte une seule fois par membre (même s'il est répété)
        for tag in set(tags):
            if tag:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

    if not tag_counts:
        return [], None

    tag_source: Optional[str] = None
    if len(sources_used) == 1:
        (tag_source,) = sources_used
    elif len(sources_used) > 1:
        tag_source = "mixed"

    result = sorted(
        [
            {
                "tag": tag,
                "nb_membres_porteurs": count,
                "poids_relatif": round(count / n, 4),
            }
            for tag, count in tag_counts.items()
        ],
        key=lambda x: (-x["nb_membres_porteurs"], x["tag"]),
    )
    return result, tag_source


# ---------------------------------------------------------------------------
# Agrégation catégorielle des mandats (mandats_agreges)
#
# Périmètre v1 volontairement restreint : mandat_electif (définit déjà
# l'appartenance au groupe — l'agréger serait circulaire), groupe_politique
# (redondant avec groupe_id/periode dans un profil déjà scopé à un seul
# groupe), fonction_gouvernementale (plus sensible éditorialement, recoupe
# mandats[].suspendu_pour_fonction_gouvernementale — AGENTS.md §5) et autre
# (filet de secours quasi jamais peuplé) sont exclus. Voir la conception
# validée dans #349/#361.
# ---------------------------------------------------------------------------

# Catégories de mandats agrégées au niveau groupe. Élargi par #382/#385 aux
# 4 catégories introduites par la nouvelle taxonomie : ce sont des instances
# de travail collectives auxquelles plusieurs membres d'un même groupe
# appartiennent, donc exactement ce que l'agrégation cherche à montrer.
#
# Restent volontairement hors agrégat, comme avant :
# - `mandat_electif`, `groupe_politique` : structurels, identiques pour tous
#   les membres d'un groupe — agréger n'apprendrait rien.
# - `fonction_gouvernementale` : individuelle par nature (et désormais
#   enrichie du portefeuille précis, #383) ; sa place est sur la fiche
#   individuelle, pas dans un agrégat de groupe.
# - `autre` : fourre-tout (Bureau, Conférence des Présidents) sans unité
#   éditoriale — agréger des natures hétérogènes sous une même étiquette
#   irait contre AGENTS.md §2.8.
MANDATS_AGREGES_CATEGORIES: tuple[str, ...] = (
    "commission",
    "commission_enquete",
    "mission_information",
    "groupe_etudes",
    "delegation",
    "groupe_amitie",
    "extra_parlementaire",
)


def _normalize_fonction_mandat(fonction: Any) -> str:
    """Normalise un libellé de fonction pour le comptage `par_fonction` (#379).

    Depuis #369, les mandats proviennent de deux référentiels aux conventions
    typographiques différentes — NosDéputés écrit `"membre"`, l'Assemblée
    nationale `"Membre"` — et le comptage brut éclatait le même rôle en deux
    entrées (mesuré : `'membre': 521` **et** `'Membre': 312`), donnant à lire
    deux rôles distincts là où il n'y en a qu'un.

    Normalise la casse et les espaces superflus, **sans** toucher aux accents
    ni au genre : `président` et `présidente` (comme `co-rapporteur`/
    `co-rapporteure`) sont des libellés institutionnels réellement distincts,
    les fusionner effacerait une information portée par la source. Un
    dépliage accent-insensible n'apporterait rien ici et dégraderait
    l'affichage.

    Une fonction absente devient `"non_precise"` (inchangé) : distinguer
    « rôle non renseigné par la source » de « simple membre » relève de la
    règle « donnée manquante ≠ valeur par défaut » (AGENTS.md §2.5).
    """
    if not isinstance(fonction, str):
        return "non_precise"
    normalisee = " ".join(fonction.split()).lower()
    return normalisee or "non_precise"


def _select_mandat_entree_unique(mandats: list[dict[str, Any]]) -> dict[str, Any]:
    """Sélectionne une entrée unique parmi des mandats en doublon pour un même
    membre et un même (categorie, label) (ex. réélu·e à la même commission sur
    deux périodes) : priorité à l'entrée ``actif=true``, sinon la plus récente
    par date de fin. Même esprit que le tie-break de ``position_majoritaire``
    en cas d'égalité (voir ``_compute_cohesion_votes``).
    """
    actifs = [m for m in mandats if m.get("actif")]
    if actifs:
        return actifs[0]
    avec_fin = [m for m in mandats if _parse_date(m.get("fin")) is not None]
    if avec_fin:
        return max(avec_fin, key=lambda m: _parse_date(m.get("fin")))
    return mandats[0]


def _aggregate_mandats(
    profils: list[dict[str, Any]],
    membres: list[dict[str, Any]],
    chambre: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Agrège les mandats catégoriels (``MANDATS_AGREGES_CATEGORIES``) de tous
    les membres du groupe, par ``(categorie, label)``.

    Éligibilité temporelle : un mandat catégoriel (commission/groupe_amitie/
    extra_parlementaire) compte pour le groupe si sa période chevauche au
    moins un intervalle de mandat électif du membre (``_intervals_overlap``).
    Si le membre n'a aucun mandat électif renseigné, il est considéré éligible
    par défaut (même approche conservatrice que ``_is_eligible_at``).

    Args:
        profils: liste de profils pivot v1 des membres du groupe.
        membres: sortie de ``[_derive_membre_entry(p) for p in profils]``
                 (même ordre que ``profils``), utilisée pour déterminer si un
                 membre est actuellement actif dans le groupe.

    Returns:
        Liste de dicts conformes à la structure ``mandats_agreges`` du schéma
        de groupe, triée par ``nb_membres`` décroissant puis
        ``(categorie, label)`` croissant.
    """
    n = len(profils)
    if n == 0:
        return []

    membre_actif_par_id = {m["membre_id"]: m["actif"] for m in membres}

    buckets: dict[tuple[str, str], list[dict[str, Any]]] = {}

    for profil in profils:
        membre_id = profil.get("id") or ""
        nom = profil.get("nom") or ""
        mandats = profil.get("mandats") or []
        eligibility_intervals = _member_eligibility_intervals(mandats, chambre)

        # Regroupe les mandats catégoriels éligibles de CE membre par (categorie, label)
        candidats_par_cle: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for m in mandats:
            categorie = m.get("categorie")
            if categorie not in MANDATS_AGREGES_CATEGORIES:
                continue
            label = m.get("label")
            if not label:
                continue

            m_debut = _parse_date(m.get("debut"))
            m_fin = _parse_date(m.get("fin"))
            if eligibility_intervals is not None and not any(
                _intervals_overlap(m_debut, m_fin, e_debut, e_fin)
                for e_debut, e_fin in eligibility_intervals
            ):
                continue

            candidats_par_cle.setdefault((categorie, label), []).append(m)

        for cle, candidats in candidats_par_cle.items():
            chosen = _select_mandat_entree_unique(candidats)
            entree_actif = bool(chosen.get("actif")) and bool(membre_actif_par_id.get(membre_id))
            buckets.setdefault(cle, []).append({
                "membre_id": membre_id,
                "nom": nom,
                "fonction": chosen.get("fonction"),
                "debut": chosen.get("debut"),
                "fin": chosen.get("fin"),
                "actif": entree_actif,
            })

    result: list[dict[str, Any]] = []
    for (categorie, label), entries in buckets.items():
        par_fonction: dict[str, int] = {}
        for e in entries:
            fonction = _normalize_fonction_mandat(e.get("fonction"))
            par_fonction[fonction] = par_fonction.get(fonction, 0) + 1

        result.append({
            "categorie": categorie,
            "label": label,
            "nb_membres": len(entries),
            "nb_membres_actifs": sum(1 for e in entries if e["actif"]),
            "poids_relatif": round(len(entries) / n, 4),
            "par_fonction": par_fonction,
            "membres": entries,
        })

    result.sort(key=lambda x: (-x["nb_membres"], x["categorie"], x["label"]))
    return result


# ---------------------------------------------------------------------------
# Agrégation des amendements (comparateur du taux d'adoption individuel)
# ---------------------------------------------------------------------------

def _normalize_sort_amendement(sort: Any) -> str:
    """Normalise un statut d'amendement en minuscules sans accent, pour comparaison.

    Les sources primaires peuvent fournir des libellés accentués ("adopté")
    ou non ("adopte") ; cette normalisation évite de dupliquer les catégories.
    """
    if not isinstance(sort, str):
        return ""
    s = unicodedata.normalize("NFKD", sort.strip().lower())
    return "".join(c for c in s if not unicodedata.combining(c))


_SORTS_ADOPTES = frozenset({"adopte"})
_SORTS_IRRECEVABLES = frozenset({"irrecevable"})
_SORTS_REJETES = frozenset({"rejete"})
_SORTS_RETIRES_OU_TOMBES = frozenset({"retire", "tombe", "non_soutenu", "non soutenu"})


def _aggregate_amendements(
    profils: list[dict[str, Any]],
    amendements_index: Optional[AmendementsIndex] = None,
) -> tuple[dict[str, Any], int]:
    """Agrège les amendements de tous les profils membres pour servir de comparateur.

    Le total (tous types de déposants confondus) sert de vue d'ensemble mais ne
    doit PAS être utilisé comme comparateur direct du taux d'adoption d'un⋅e
    élu⋅e : les amendements gouvernementaux ou du rapporteur sont adoptés quasi
    systématiquement par construction (ils portent le texte), ce qui gonflerait
    artificiellement la référence. Comparer un⋅e élu⋅e à
    ``par_type_deposant["depute"]``, seule catégorie de même nature que les
    amendements qu'un⋅e député⋅e dépose en son nom propre.

    Depuis #431, `sort` et `type_deposant` vivent dans l'index partagé et non
    dans le profil : l'agrégation est une **jointure**, faite entrée par entrée
    via `joindre_amendements`, un générateur. Ne jamais matérialiser la liste
    jointe : ce serait reconstruire la forme plate que la normalisation vient de
    supprimer, avec le facteur ~21 et l'OOM de #377.

    Repli de lecture transitoire : une entrée d'avant #431 porte encore ses
    champs, une entrée non résolue les porte sous `amendement_non_resolu`. Les
    deux sont lues sur place — sans quoi tout l'agrégat tomberait à zéro entre le
    déploiement du code et la régénération des données.

    Args:
        profils: liste de profils pivot v1 des membres du groupe.
        amendements_index: index partagé (#431). Sans lui, seuls les
            enregistrements encore portés par le profil sont exploitables.

    Returns:
        `(amendements_agreges, nb_non_resolus)`. `nb_non_resolus` compte les
        entrées qu'aucune source ne renseigne : elles sont **exclues** des
        décomptes, et ce nombre est remonté en `meta.warnings` — une exclusion
        muette transformerait un dénominateur en donnée fausse (AGENTS.md §2.7).
    """
    total = make_empty_amendements_stats()
    par_type = {t: make_empty_amendements_stats() for t in AMENDEMENTS_TYPES_DEPOSANT}
    non_resolus = 0

    for profil in profils:
        for entree, amendement in joindre_amendements(
            profil.get("amendements"), amendements_index
        ):
            if amendement is None:
                amendement = entree.get("amendement_non_resolu")
            if amendement is None and "sort" in entree:
                # Entrée d'avant #431, encore autoportante.
                amendement = entree
            if not isinstance(amendement, dict):
                non_resolus += 1
                continue
            sort_norm = _normalize_sort_amendement(amendement.get("sort"))
            type_deposant = amendement.get("type_deposant")
            bucket = par_type[type_deposant] if type_deposant in par_type else par_type["inconnu"]
            for stats in (total, bucket):
                stats["nb_amendements"] += 1
                if sort_norm in _SORTS_ADOPTES:
                    stats["nb_adoptes"] += 1
                elif sort_norm in _SORTS_IRRECEVABLES:
                    stats["nb_irrecevables"] += 1
                elif sort_norm in _SORTS_RETIRES_OU_TOMBES:
                    stats["nb_retires_ou_tombes"] += 1
                elif sort_norm in _SORTS_REJETES:
                    stats["nb_rejetes"] += 1

    for stats in (total, *par_type.values()):
        stats["taux_adoption"] = (
            round(stats["nb_adoptes"] / stats["nb_amendements"], 4)
            if stats["nb_amendements"] else None
        )

    total["par_type_deposant"] = par_type
    return total, non_resolus


# ---------------------------------------------------------------------------
# Contrôle interne : écart de cohésion/participation individuel vs groupe
#
# Donnée de contrôle interne uniquement — volontairement absente du schéma
# de groupe public (schema_groupe.py). Ne pas inclure le résultat de
# `compute_ecarts_cohesion_internes` dans un profil de groupe publié tant que
# ce comparateur n'a pas été validé comme sortie publique.
# ---------------------------------------------------------------------------

def compute_ecarts_cohesion_internes(
    profils: list[dict[str, Any]],
    cohesion_votes: list[dict[str, Any]],
    legislature: Optional[str] = None,
    scrutins_index: Optional[ScrutinsIndex] = None,
    chambre: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Calcule, pour chaque membre, son écart de participation/cohérence vs le groupe.

    Le ratio individuel est calculé sur exactement les mêmes scrutins que ceux
    couverts par ``cohesion_votes`` (donc sur les mêmes membres éligibles par
    scrutin), puis comparé à la moyenne du groupe sur ces mêmes scrutins.

    Args:
        profils: liste de profils pivot v1 des membres du groupe.
        cohesion_votes: sortie de ``_compute_cohesion_votes`` pour ce même groupe.
        legislature: législature du groupe, à passer telle qu'utilisée pour
                     ``_compute_cohesion_votes`` — les numéros de scrutin ne
                     sont comparables qu'à législature égale (#403).

    Returns:
        Liste de dicts {membre_id, nom, nb_scrutins_eligibles,
        taux_participation_individuel, taux_coherence_individuel,
        ecart_participation_vs_groupe, ecart_coherence_vs_groupe}.
        Destinée à un usage de contrôle interne, pas à publication.
    """
    if not cohesion_votes:
        return []

    # Moyennes du groupe sur les mêmes scrutins (celles déjà calculées par scrutin).
    participations = [c["taux_participation"] for c in cohesion_votes if c.get("taux_participation") is not None]
    coherences = [c["taux_coherence"] for c in cohesion_votes if c.get("taux_coherence") is not None]
    moyenne_participation_groupe = sum(participations) / len(participations) if participations else None
    moyenne_coherence_groupe = sum(coherences) / len(coherences) if coherences else None

    coh_by_scrutin = {c["scrutin_id"]: c for c in cohesion_votes}

    resultats: list[dict[str, Any]] = []
    for profil in profils:
        mandats = profil.get("mandats") or []
        v_index = _build_vote_index(profil, legislature)

        n_eligible = 0
        n_present = 0
        n_alignes = 0

        for scrutin_id, c in coh_by_scrutin.items():
            # La date du scrutin vient de l'index partagé depuis #432 : sans
            # elle, l'éligibilité n'est pas vérifiable, et compter le membre
            # comme éligible « par défaut » fausserait le dénominateur.
            scrutin = scrutins_index.get(scrutin_id) if scrutins_index is not None else None
            if scrutin is None:
                continue
            if not _member_eligible_at(mandats, scrutin.get("date"), chambre):
                continue
            n_eligible += 1

            vote = v_index.get(scrutin_id)
            if vote is None:
                continue
            pos = vote.get("position")
            if pos in ("pour", "contre", "abstention"):
                n_present += 1
            if pos is not None and pos == c.get("position_majoritaire"):
                n_alignes += 1

        taux_participation_individuel = n_present / n_eligible if n_eligible else None
        taux_coherence_individuel = n_alignes / n_eligible if n_eligible else None

        resultats.append({
            "membre_id": profil.get("id") or "",
            "nom": profil.get("nom") or "",
            "nb_scrutins_eligibles": n_eligible,
            "taux_participation_individuel": (
                round(taux_participation_individuel, 4)
                if taux_participation_individuel is not None else None
            ),
            "taux_coherence_individuel": (
                round(taux_coherence_individuel, 4)
                if taux_coherence_individuel is not None else None
            ),
            "ecart_participation_vs_groupe": (
                round(taux_participation_individuel - moyenne_participation_groupe, 4)
                if taux_participation_individuel is not None and moyenne_participation_groupe is not None
                else None
            ),
            "ecart_coherence_vs_groupe": (
                round(taux_coherence_individuel - moyenne_coherence_groupe, 4)
                if taux_coherence_individuel is not None and moyenne_coherence_groupe is not None
                else None
            ),
        })

    return resultats


# ---------------------------------------------------------------------------
# Chargement et détection de format
# ---------------------------------------------------------------------------

def _is_pivot_v1(profil: dict[str, Any]) -> bool:
    """Retourne True si le profil est déjà au format pivot v1 (schema_version présent)."""
    return "schema_version" in profil and "id" in profil


def load_profil_from_file(path: Path) -> dict[str, Any]:
    """Charge un profil depuis un fichier JSON et le normalise en pivot v1 si nécessaire.

    Les profils au format brut (produits par candidate_profile.py) sont
    convertis automatiquement via normalize_profil.

    Args:
        path: chemin vers le fichier JSON.

    Returns:
        Profil pivot v1 (dict).

    Raises:
        FileNotFoundError: si le fichier n'existe pas.
        ValueError: si le fichier n'est pas un JSON valide ou si le format est inconnu.
    """
    with open(path, encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as exc:
            raise ValueError(f"JSON invalide dans {path} : {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"Attendu un dict JSON, reçu {type(data).__name__} dans {path}.")

    if _is_pivot_v1(data):
        return data

    # Format brut de collecte (champ "slug" présent, pas de "schema_version")
    if "slug" in data:
        return normalize_profil(data)

    raise ValueError(
        f"Format non reconnu dans {path} : ni pivot v1 (schema_version + id) "
        "ni format brut de collecte (slug)."
    )


# ---------------------------------------------------------------------------
# Fonction principale d'agrégation
# ---------------------------------------------------------------------------

def build_groupe_profile(
    groupe_id: str,
    groupe_sigle: str,
    groupe_nom: str,
    chambre: Optional[str],
    legislature: Optional[str],
    profils: list[dict[str, Any]],
    seuil_quorum: float = 0.5,
    licence_donnees: str = "",
    scrutins_index: Optional[ScrutinsIndex] = None,
    amendements_index: Optional[AmendementsIndex] = None,
) -> dict[str, Any]:
    """Construit un profil de groupe à partir d'une liste de profils individuels pivot v1.

    Args:
        groupe_id: identifiant du groupe, ex. "AN:SOC".
        groupe_sigle: sigle court, ex. "SOC".
        groupe_nom: nom complet, ex. "Socialistes et apparentés".
        chambre: "AN" | "Senat" | "PE" | "mairie" | None.
        legislature: ex. "16" | None.
        profils: liste de profils pivot v1 des membres du groupe.
        seuil_quorum: seuil de taux de participation pour quorum_atteint (défaut : 0.5).
        licence_donnees: texte de licence à inscrire dans meta.
        scrutins_index: index partagé des scrutins (#432). Nécessaire au calcul
                    de cohésion : la date d'un scrutin, qui détermine quels
                    membres étaient éligibles, n'est plus dans les profils.
                    Absent, la cohésion est vide plutôt que fausse.
        amendements_index: index partagé des amendements (#431). Le `sort` et le
                    `type_deposant` d'un amendement n'étant plus dans les
                    profils, l'agrégat est une jointure : sans index, les seules
                    entrées exploitables sont celles qui portent encore leur
                    enregistrement, et les autres sont comptées puis remontées
                    en `meta.warnings` plutôt qu'ignorées en silence.

    Returns:
        Profil de groupe dict conforme au schéma de groupe v1.
    """
    warnings: list[str] = []

    # --- Membres ---
    membres = [_derive_membre_entry(p, chambre) for p in profils]

    # --- Effectif ---
    n_actif = sum(1 for m in membres if m["actif"])
    effectif: dict[str, Any] = {
        "actuel": n_actif,
        "min_historique": None,  # non calculé (nécessiterait une analyse de timeline)
        "max_historique": None,
    }

    # --- Période du groupe ---
    all_debuts = [_parse_date(m["debut_dans_groupe"]) for m in membres]
    all_fins = [_parse_date(m["fin_dans_groupe"]) for m in membres]
    parsed_debuts = [d for d in all_debuts if d is not None]

    periode_debut = str(min(parsed_debuts)) if parsed_debuts else None
    # Le groupe est actif si au moins un membre est actif (fin_dans_groupe = None)
    groupe_actif = any(m["actif"] for m in membres)
    if groupe_actif:
        periode_fin = None
    else:
        parsed_fins = [f for f in all_fins if f is not None]
        periode_fin = str(max(parsed_fins)) if parsed_fins else None

    # --- Cohésion de vote ---
    cohesion_votes = _compute_cohesion_votes(
        profils, seuil_quorum=seuil_quorum, legislature=legislature,
        scrutins_index=scrutins_index, chambre=chambre,
    )
    n_non_resolus = _votes_non_resolus(profils)
    if n_non_resolus:
        warnings.append(
            f"cohesion_votes : {n_non_resolus} vote(s) sans scrutin_id écarté(s) — "
            "aucun rattachement de législature possible, donc aucun scrutin identifiable "
            "(#432). Le dénominateur publié ne les compte pas."
        )

    # --- Tags thématiques ---
    tags_agreges, tag_source = aggregate_tags_thematiques(profils)
    if tag_source == "theme_officiel":
        warnings.append(
            "tags_thematiques_agreges : source=theme_officiel "
            "(tags_thematiques individuels absents ou vides ; thèmes officiels "
            "Syceron des interventions utilisés en fallback)."
        )
    elif tag_source == "mots_cles_interventions":
        warnings.append(
            "tags_thematiques_agreges : source=mots_cles_interventions "
            "(tags_thematiques individuels absents ou vides ; mots-clés des "
            "interventions utilisés en fallback)."
        )
    elif tag_source == "mixed":
        warnings.append(
            "tags_thematiques_agreges : source=mixed (certains profils utilisent "
            "tags_thematiques, d'autres utilisent mots_cles_interventions)."
        )

    # --- Sources uniques (dédoublonnées par type + url) ---
    seen_sources: set[tuple[str, str]] = set()
    sources: list[dict[str, Any]] = []
    for p in profils:
        for s in (p.get("sources") or []):
            key = (s.get("type") or "", s.get("url") or "")
            if key not in seen_sources:
                seen_sources.add(key)
                sources.append(s)

    # --- Mandats agrégés (agrégation catégorielle sur mandats[]) ---
    mandats_agreges = _aggregate_mandats(profils, membres, chambre)

    # --- Amendements agrégés (comparateur du taux d'adoption individuel) ---
    amendements_agreges, n_amendements_non_resolus = _aggregate_amendements(
        profils, amendements_index
    )
    if n_amendements_non_resolus:
        warnings.append(
            f"amendements_agreges : {n_amendements_non_resolus} amendement(s) "
            "introuvable(s) dans l'index partagé et sans enregistrement de repli, "
            "écarté(s) (#431). Le dénominateur publié ne les compte pas."
        )

    # --- Assemblage ---
    profil_groupe = make_empty_profil_groupe(
        groupe_id=groupe_id,
        groupe_sigle=groupe_sigle,
        groupe_nom=groupe_nom,
        chambre=chambre,
        legislature=legislature,
    )

    profil_groupe["periode"] = {
        "debut": periode_debut,
        "fin": periode_fin,
        "actif": groupe_actif,
    }
    profil_groupe["membres"] = membres
    profil_groupe["effectif"] = effectif
    profil_groupe["cohesion_votes"] = cohesion_votes
    profil_groupe["tags_thematiques_agreges"] = tags_agreges
    profil_groupe["mandats_agreges"] = mandats_agreges
    profil_groupe["amendements_agreges"] = amendements_agreges
    profil_groupe["sources"] = sources

    # `licence_donnees` : dérivée de `sources[]` quand l'appelant n'impose rien
    # (#530, lot 6). Le pipeline ne passe pas `--licence`, et les 7 fiches
    # publiées portaient donc une attribution **vide** — un manque, sur des
    # documents dérivés de données ouvertes qui en exigent une (AGENTS.md §7).
    # La dérivation, et non une constante : `groupe-Senat-LR` et `groupe-Senat-SER` dérivent de NosSénateurs (ODbL)
    # quand les 5 fiches AN dérivent d'AMO30 (Licence Ouverte). L'argument explicite reste
    # prioritaire, c'est lui qui permet d'annoter une fiche hors pipeline.
    if licence_donnees:
        profil_groupe["meta"]["licence_donnees"] = licence_donnees
    else:
        appliquer_licence_donnees(profil_groupe)
    profil_groupe["meta"]["profils_sources"] = [
        p.get("id") or "" for p in profils
    ]
    profil_groupe["meta"]["seuil_quorum"] = seuil_quorum
    profil_groupe["meta"]["warnings"] = warnings

    return profil_groupe


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="group_profile.py",
        description=(
            "Agrège des profils individuels (pivot v1 ou brut de collecte) "
            "en un profil de groupe politique."
        ),
    )
    parser.add_argument(
        "profils",
        nargs="*",
        metavar="PROFIL.json",
        help="Fichiers JSON des profils individuels des membres du groupe (ignoré avec --from-roster).",
    )
    parser.add_argument(
        "--from-roster",
        action="store_true",
        help=(
            "Récupère la composition réelle du groupe via group_roster.py "
            "(référentiel AMO30 de l'Assemblée nationale) au lieu des fichiers "
            "PROFIL.json."
        ),
    )
    parser.add_argument(
        "--roster-chambre",
        choices=["deputes"],
        default=None,
        help=(
            "Requis avec --from-roster : chambre interrogée pour la composition du "
            "groupe. Seule valeur depuis #528 — le Sénat est hors périmètre."
        ),
    )
    parser.add_argument(
        "--profiles-dir",
        default="pivot_data/profiles",
        metavar="DOSSIER",
        help="Avec --from-roster : dossier des pivots *.pivot.json (défaut : pivot_data/profiles).",
    )
    parser.add_argument(
        "--merge-existing",
        action="store_true",
        help=(
            "Avec --from-roster --out FICHIER : si FICHIER existe déjà, réintègre les "
            "membres qui y figuraient mais sont absents du roster récupéré cette "
            "exécution (protège contre un échec partiel de récupération du roster live). "
            "Sans cette option, --out écrase entièrement le fichier existant à chaque exécution."
        ),
    )
    parser.add_argument("--groupe-id", required=True, help="Ex. AN:SOC")
    parser.add_argument("--groupe-sigle", required=True, help="Ex. SOC")
    parser.add_argument("--groupe-nom", required=True, help="Ex. 'Socialistes et apparentés'")
    parser.add_argument(
        "--chambre",
        choices=["AN", "Senat", "PE", "mairie"],
        default=None,
        help="Chambre parlementaire.",
    )
    parser.add_argument("--legislature", default=None, help="Ex. 16")
    parser.add_argument(
        "--scrutins", default=str(DEFAULT_SCRUTINS_PATH), metavar="FICHIER",
        help=(
            "Index partagé des scrutins (#432, défaut : "
            f"{DEFAULT_SCRUTINS_PATH}). La cohésion en dépend : la date d'un scrutin, "
            "qui détermine les membres éligibles, n'est plus dans les profils."
        ),
    )
    parser.add_argument(
        "--amendements", default=str(DEFAULT_AMENDEMENTS_DIR), metavar="DOSSIER",
        help=(
            "Index partagé des amendements (#431, défaut : "
            f"{DEFAULT_AMENDEMENTS_DIR}). `amendements_agreges` en dépend : le "
            "`sort` et le `type_deposant` d'un amendement ne sont plus dans les profils."
        ),
    )
    parser.add_argument(
        "--seuil-quorum",
        type=float,
        default=0.5,
        metavar="FLOAT",
        help="Seuil de participation pour quorum_atteint (défaut : 0.5).",
    )
    parser.add_argument(
        "--licence",
        default="",
        metavar="TEXTE",
        help="Texte de licence à inscrire dans meta.licence_donnees.",
    )
    parser.add_argument(
        "--out",
        default=None,
        metavar="FICHIER",
        help="Fichier de sortie JSON (défaut : stdout).",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Valide le profil de groupe produit et affiche les erreurs éventuelles.",
    )
    parser.add_argument(
        "--rapport-interne",
        default=None,
        metavar="FICHIER",
        help=(
            "Écrit dans FICHIER un rapport interne (écarts de cohésion/participation "
            "individuels vs moyenne du groupe). Donnée de contrôle interne : jamais "
            "incluse dans le profil de groupe public écrit via --out."
        ),
    )
    return parser


def _avertissement_fraicheur_an() -> str:
    """`meta.warnings` de fraîcheur d'une fiche AN — il doit NOMMER sa source.

    C'est un champ **publié**, et la règle 2 d'AGENTS §2 (traçabilité totale)
    ne souffre pas qu'il nomme une source dont la composition ne vient pas.
    Jusqu'à #529 il avait DEUX rédactions, choisies sur
    `an_roster.AN_ROSTER_ACTIF` : celle d'AMO30 et celle de NosDéputés, qui
    était le repli du drapeau. Ce repli est retiré — le drapeau baissé ne rend
    plus la lecture à personne, il refuse (`RosterAnInactif`) — donc il n'y a
    plus qu'une source à nommer, et une seule rédaction.

    AMO30 est le référentiel de l'Assemblée elle-même : une législature close y
    est complète, y compris les mandats terminés en cours de législature, ce
    que le miroir — qui ne publiait que la dernière appartenance connue —
    perdait (4 acteurs mesurés, #526 §2).
    """
    return (
        "fraicheur_donnees : composition dérivée du référentiel AMO30 de "
        "l'Assemblée nationale (data.assemblee-nationale.fr, Licence "
        "Ouverte), et non plus de www.nosdeputes.fr depuis #527. Une "
        "législature close y est complète : les mandats terminés en cours "
        "de législature y figurent, alors que la dernière composition "
        "connue d'un miroir les perd. La fiche reflète donc l'appartenance "
        "au groupe telle que l'Assemblée la publie à la date de "
        "meta.genere_le ; un membre sans profil publié n'y apparaît pas "
        "(voir meta.couverture_roster)."
    )


def generate_groupe_profile_from_roster(
    *,
    roster: list[dict[str, Any]],
    groupe_id: str,
    groupe_sigle: str,
    groupe_nom: str,
    chambre: Optional[str],
    legislature: Optional[str],
    roster_chambre: str,
    profiles_dir: Path,
    out_path: Optional[Path] = None,
    merge_existing: bool = False,
    seuil_quorum: float = 0.5,
    licence_donnees: str = "",
    validate: bool = False,
    rapport_interne_path: Optional[Path] = None,
    scrutins_index: Optional[ScrutinsIndex] = None,
    amendements_index: Optional[AmendementsIndex] = None,
) -> dict[str, Any]:
    """Construit (et écrit si `out_path` fourni) un profil de groupe à partir d'un
    roster déjà récupéré (voir `fetch_group_roster`, ou `fetch_full_roster` +
    `filter_roster_by_sigle` pour partager un même fetch réseau entre plusieurs
    sigles d'une même chambre/législature — voir generate_group_profiles.py).

    Factorise la logique partagée entre le CLI `--from-roster` de `main()` et
    `generate_group_profiles.py`.
    """
    print(f"→ {len(roster)} membre(s) réel(s) trouvé(s) pour {groupe_sigle!r}.", file=sys.stderr)

    # --merge-existing : réintègre les membres du fichier --out précédent
    # absents du roster récupéré cette exécution (protège contre un échec
    # partiel de récupération du roster live). Sans cette option, --out
    # écrase entièrement le fichier existant à chaque exécution.
    recovered_slugs: list[str] = []
    if merge_existing and out_path and out_path.exists():
        try:
            old_profil = json.loads(out_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print(f"  [!] --merge-existing : lecture de {out_path} impossible ({exc}), ignoré.", file=sys.stderr)
            old_profil = None
        if old_profil:
            roster_slugs = {m.get("slug") for m in roster if m.get("slug")}
            old_slugs = {
                membre_id.split(":", 1)[1] if ":" in membre_id else membre_id
                for membre_id in (m.get("membre_id") for m in old_profil.get("membres", []))
                if membre_id
            }
            recovered_slugs = sorted(old_slugs - roster_slugs)
            if recovered_slugs:
                print(
                    f"  [i] --merge-existing : {len(recovered_slugs)} membre(s) de {out_path} "
                    f"absent(s) du roster récupéré cette exécution, réintégré(s) : "
                    f"{', '.join(recovered_slugs)}",
                    file=sys.stderr,
                )

    profils: list[dict[str, Any]] = []
    missing_slugs: list[str] = []
    for member in roster:
        slug = member.get("slug")
        pivot_path = profiles_dir / f"{slug}.pivot.json" if slug else None
        if pivot_path is None or not pivot_path.exists():
            missing_slugs.append(slug or member.get("nom") or "?")
            continue
        try:
            profils.append(load_profil_from_file(pivot_path))
        except (FileNotFoundError, ValueError) as exc:
            print(f"  [!] {exc}", file=sys.stderr)
            missing_slugs.append(slug)

    for slug in recovered_slugs:
        pivot_path = profiles_dir / f"{slug}.pivot.json"
        if not pivot_path.exists():
            continue
        try:
            profils.append(load_profil_from_file(pivot_path))
        except (FileNotFoundError, ValueError) as exc:
            print(f"  [!] {exc}", file=sys.stderr)

    couverture_roster = {"roster_total": len(roster), "profils_disponibles": len(profils)}
    if missing_slugs:
        print(
            f"  [!] {len(missing_slugs)} membre(s) du roster sans profil pivot local "
            f"dans {profiles_dir} : {', '.join(missing_slugs)}",
            file=sys.stderr,
        )

    print(f"→ {len(profils)} profil(s) chargé(s). Calcul en cours…", file=sys.stderr)

    profil_groupe = build_groupe_profile(
        groupe_id=groupe_id,
        groupe_sigle=groupe_sigle,
        groupe_nom=groupe_nom,
        chambre=chambre,
        legislature=legislature,
        profils=profils,
        seuil_quorum=seuil_quorum,
        licence_donnees=licence_donnees,
        scrutins_index=scrutins_index,
        amendements_index=amendements_index,
    )

    profil_groupe["meta"]["couverture_roster"] = couverture_roster
    if recovered_slugs:
        profil_groupe["meta"]["warnings"].append(
            f"fusion_avec_existant : {len(recovered_slugs)} membre(s) présent(s) dans "
            f"{out_path} avant cette exécution mais absent(s) du roster récupéré cette "
            f"fois-ci ont été réintégré(s) (probable échec partiel de récupération du "
            f"roster live, ou départ réel du groupe non distinguable automatiquement ici) : "
            f"{', '.join(recovered_slugs)}. meta.couverture_roster.roster_total ne reflète "
            f"que le roster récupéré cette exécution, pas ces membres réintégrés."
        )
    # #528 : la branche `roster_chambre == "senateurs"` a été retirée. Elle
    # posait deux avertissements publiés (`fraicheur_donnees` sur
    # archive.nossenateurs.fr, `couverture_roster_senat` sur l'impossibilité de
    # distinguer les sénateurs en fonction des anciens) sur les deux fiches
    # `groupe-Senat-*.json`. Ces fiches restent PUBLIÉES et FIGÉES, avec leurs
    # avertissements : la suspension d'extraction de #516 les empêche d'être
    # régénérées, et les retirer supprimerait un fichier publié — ce que
    # `audit_diff_profils` bloque (#460/#470). Voir
    # docs/technical_decisions.md#retrait-senat-528.
    if roster_chambre == "deputes":
        profil_groupe["meta"]["warnings"].append(_avertissement_fraicheur_an())

    if validate:
        errors = validate_profil_groupe(profil_groupe)
        if errors:
            print(f"  [!] {len(errors)} erreur(s) de validation :", file=sys.stderr)
            for e in errors:
                print(f"      - {e}", file=sys.stderr)
        else:
            print("  ✓ Profil de groupe valide selon le schéma.", file=sys.stderr)

    if rapport_interne_path:
        rapport = compute_ecarts_cohesion_internes(
            profils, profil_groupe["cohesion_votes"], profil_groupe.get("legislature"),
            scrutins_index=scrutins_index, chambre=profil_groupe.get("chambre"),
        )
        rapport_interne_path.parent.mkdir(parents=True, exist_ok=True)
        rapport_interne_path.write_text(
            json.dumps(rapport, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"  ✓ Rapport interne (non public) écrit : {rapport_interne_path}", file=sys.stderr)

    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        # #343 : ne pas faire avancer meta.genere_le / sources[].synchro_le
        # quand le profil régénéré est identique en contenu. Ce script
        # reconstruit sa sortie à chaque exécution sans comparer à la version
        # précédente — sans ça, chaque run produit un diff sur les 7 fichiers
        # groupe alors que rien n'a changé, ce qui bruite les commits et
        # fausse toute lecture de fraîcheur (AGENTS.md §2).
        profil_groupe = preserve_stable_freshness_timestamps(
            load_existing_document(out_path), profil_groupe
        )
        out_path.write_text(json.dumps(profil_groupe, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  ✓ Profil de groupe écrit : {out_path}", file=sys.stderr)

    return profil_groupe


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    if args.from_roster:
        if not args.roster_chambre:
            print("[!] --from-roster requiert --roster-chambre (deputes).", file=sys.stderr)
            return 1
        from group_roster import fetch_group_roster  # import tardif : requests non requis hors ce mode
        import requests

        legislature = args.legislature if args.roster_chambre == "deputes" else None
        try:
            roster = fetch_group_roster(
                chambre=args.roster_chambre,
                groupe_sigle=args.groupe_sigle,
                legislature=legislature,
            )
        except (ValueError, requests.RequestException) as exc:
            print(f"[!] Récupération du roster impossible : {exc}", file=sys.stderr)
            return 1

        out_path = Path(args.out) if args.out else None
        profil_groupe = generate_groupe_profile_from_roster(
            roster=roster,
            groupe_id=args.groupe_id,
            groupe_sigle=args.groupe_sigle,
            groupe_nom=args.groupe_nom,
            chambre=args.chambre,
            legislature=args.legislature,
            roster_chambre=args.roster_chambre,
            profiles_dir=Path(args.profiles_dir),
            out_path=out_path,
            merge_existing=args.merge_existing,
            seuil_quorum=args.seuil_quorum,
            licence_donnees=args.licence,
            validate=args.validate,
            rapport_interne_path=Path(args.rapport_interne) if args.rapport_interne else None,
        )
        if not out_path:
            print(json.dumps(profil_groupe, ensure_ascii=False, indent=2))
        return 0

    profils: list[dict[str, Any]] = []
    for path_str in args.profils:
        path = Path(path_str)
        print(f"→ Chargement : {path}", file=sys.stderr)
        try:
            profils.append(load_profil_from_file(path))
        except (FileNotFoundError, ValueError) as exc:
            print(f"  [!] {exc}", file=sys.stderr)
            return 1

    print(
        f"→ {len(profils)} profil(s) chargé(s). Calcul en cours…",
        file=sys.stderr,
    )

    scrutins_index = charger_scrutins(Path(args.scrutins))
    if len(scrutins_index) == 0:
        # Sans index, la cohésion sort vide plutôt que fausse : mieux vaut le
        # dire ici que laisser lire un `cohesion_votes: []` comme un fait.
        print(
            f"  [!] Index des scrutins vide ou absent ({args.scrutins}) : la cohésion "
            "de vote ne pourra pas être calculée (#432). Construire l'index avec "
            "`python3 src/build_scrutins_index.py`.",
            file=sys.stderr,
        )
    else:
        print(f"→ Index des scrutins : {len(scrutins_index)} scrutin(s).", file=sys.stderr)

    # `avec_cosignatures=False` : l'agrégat ne lit que `sort` et `type_deposant`.
    # Charger les cosignatures coûterait 59 % de l'index pour rien (#431).
    amendements_index = charger_amendements(
        Path(args.amendements), avec_cosignatures=False
    )
    if len(amendements_index) == 0:
        print(
            f"  [!] Index des amendements vide ou absent ({args.amendements}) : "
            "`amendements_agreges` ne comptera que les entrées portant encore leur "
            "enregistrement (#431). Construire l'index avec "
            "`python3 src/build_amendements_index_pivot.py`.",
            file=sys.stderr,
        )
    else:
        print(f"→ Index des amendements : {len(amendements_index)} amendement(s).", file=sys.stderr)

    profil_groupe = build_groupe_profile(
        groupe_id=args.groupe_id,
        groupe_sigle=args.groupe_sigle,
        groupe_nom=args.groupe_nom,
        chambre=args.chambre,
        legislature=args.legislature,
        profils=profils,
        seuil_quorum=args.seuil_quorum,
        licence_donnees=args.licence,
        scrutins_index=scrutins_index,
        amendements_index=amendements_index,
    )

    if args.validate:
        errors = validate_profil_groupe(profil_groupe)
        if errors:
            print(f"  [!] {len(errors)} erreur(s) de validation :", file=sys.stderr)
            for e in errors:
                print(f"      - {e}", file=sys.stderr)
        else:
            print("  ✓ Profil de groupe valide selon le schéma.", file=sys.stderr)

    if args.rapport_interne:
        rapport = compute_ecarts_cohesion_internes(
            profils, profil_groupe["cohesion_votes"], profil_groupe.get("legislature"),
            scrutins_index=scrutins_index, chambre=profil_groupe.get("chambre"),
        )
        rapport_path = Path(args.rapport_interne)
        rapport_path.parent.mkdir(parents=True, exist_ok=True)
        rapport_path.write_text(
            json.dumps(rapport, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"  ✓ Rapport interne (non public) écrit : {rapport_path}", file=sys.stderr)

    output_json = json.dumps(profil_groupe, ensure_ascii=False, indent=2)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output_json, encoding="utf-8")
        print(f"  ✓ Profil de groupe écrit : {out_path}", file=sys.stderr)
    else:
        print(output_json)

    return 0


if __name__ == "__main__":
    sys.exit(main())
