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

Usage (depuis la racine du dépôt) :
    python src/group_profile.py \\
        --groupe-id "AN:SOC" \\
        --groupe-sigle SOC \\
        --groupe-nom "Socialistes et apparentés" \\
        --chambre AN \\
        --legislature 16 \\
        data/profiles/jerome-guedj.json \\
        data/profiles/boris-vallaud.json \\
        --out data/profiles/groupe-SOC-16.json

    Les profils en entrée peuvent être au format brut NosDéputés (candidate_profile.py)
    ou au format pivot v1 (normalize_nosdeputes.py). Le script détecte automatiquement
    le format et normalise si nécessaire.
"""

import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path
from typing import Any, Optional

from schema_groupe import SCHEMA_GROUPE_VERSION, make_empty_profil_groupe, validate_profil_groupe


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

def _member_eligible_at(mandats: list[dict[str, Any]], vote_date: Optional[str]) -> bool:
    """Détermine si un membre était en mandat (éligible à voter) à la date du scrutin.

    Un membre est éligible si au moins un de ses mandats électifs est actif à
    ``vote_date``. Si la date est absente ou non parseable, le membre est
    considéré éligible par défaut (approche conservatrice).

    Args:
        mandats: liste des mandats du profil pivot (champ ``mandats[]``).
        vote_date: date du scrutin au format "YYYY-MM-DD", ou None.

    Returns:
        True si le membre est éligible pour ce scrutin.
    """
    d = _parse_date(vote_date)
    if d is None:
        return True  # date inconnue → on ne peut pas exclure

    electif = [m for m in mandats if m.get("categorie") == "mandat_electif"]
    if not electif:
        return True  # pas d'info de mandat → on ne peut pas exclure

    for m in electif:
        debut = _parse_date(m.get("debut"))
        fin = _parse_date(m.get("fin"))
        if debut is not None and d < debut:
            continue
        if fin is not None and d > fin:
            continue
        return True  # le membre était en mandat à cette date

    return False


# ---------------------------------------------------------------------------
# Construction de l'entrée membre
# ---------------------------------------------------------------------------

def _derive_membre_entry(profil: dict[str, Any]) -> dict[str, Any]:
    """Dérive une entrée ``membres[]`` du profil de groupe à partir d'un profil pivot.

    La date de début dans le groupe correspond au début du premier mandat électif ;
    la fin correspond à la fin du dernier mandat électif terminé (None si toujours
    actif). Cette approximation est correcte pour les cas sans changement de groupe
    en cours de mandat.

    Args:
        profil: profil pivot v1.

    Returns:
        Dict conformant à la structure membres[] du schéma de groupe.
    """
    electif = [
        m for m in (profil.get("mandats") or [])
        if m.get("categorie") == "mandat_electif"
    ]

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

def _build_vote_index(profil: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Construit un index {numero_scrutin → vote_dict} pour un profil individuel.

    Permet une recherche O(1) par numéro de scrutin lors du calcul de cohésion.
    Les numéros de scrutin sont normalisés en chaînes pour garantir une comparaison
    homogène.
    """
    index: dict[str, dict[str, Any]] = {}
    for v in (profil.get("votes") or []):
        num = v.get("numero_scrutin")
        if num is not None:
            index[str(num)] = v
    return index


# ---------------------------------------------------------------------------
# Calcul de cohésion
# ---------------------------------------------------------------------------

def _compute_cohesion_votes(
    profils: list[dict[str, Any]],
    seuil_quorum: float = 0.5,
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

    Returns:
        Liste de dicts conformes à la structure cohesion_votes[], triée par date
        décroissante.
    """
    # --- 1. Collecte de tous les scrutins ---
    # Clé : numero_scrutin (str) → méta du scrutin
    scrutins: dict[str, dict[str, Any]] = {}
    for profil in profils:
        for v in (profil.get("votes") or []):
            num = v.get("numero_scrutin")
            if num is None:
                continue
            num_str = str(num)
            if num_str not in scrutins:
                scrutins[num_str] = {
                    "date": v.get("date"),
                    "texte": v.get("texte") or "",
                    "sort": v.get("sort"),
                }

    if not scrutins:
        return []

    # --- 2. Index de votes par membre ---
    vote_indexes = [_build_vote_index(p) for p in profils]

    # --- 3. Calcul par scrutin ---
    _EXPRESSED = ("pour", "contre", "abstention")

    cohesion: list[dict[str, Any]] = []
    for num_str, meta in scrutins.items():
        vote_date = meta["date"]

        compteurs: dict[str, int] = {
            "pour": 0, "contre": 0, "abstention": 0,
            "non_votant": 0, "absent": 0, "excuse": 0,
        }
        n_eligible = 0

        for profil, v_index in zip(profils, vote_indexes):
            mandats = profil.get("mandats") or []
            if not _member_eligible_at(mandats, vote_date):
                continue
            n_eligible += 1

            vote = v_index.get(num_str)
            if vote is None:
                compteurs["absent"] += 1
            else:
                pos = vote.get("position") or "absent"
                compteurs[pos] = compteurs.get(pos, 0) + 1

        if n_eligible == 0:
            continue

        # Position majoritaire sur les votes exprimés (pour/contre/abstention)
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
            "numero_scrutin": num_str,
            "date": meta["date"],
            "texte": meta["texte"],
            "sort": meta["sort"],
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

    # Tri par date décroissante (scrutins récents en premier)
    cohesion.sort(key=lambda x: x["date"] or "", reverse=True)
    return cohesion


# ---------------------------------------------------------------------------
# Agrégation des tags thématiques
# ---------------------------------------------------------------------------

def _aggregate_tags_thematiques(
    profils: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], Optional[str]]:
    """Agrège les tags thématiques de tous les profils membres.

    Stratégie : utilise ``tags_thematiques`` de chaque profil individuel.
    Si un profil a ``tags_thematiques`` vide, ses ``interventions[].mots_cles``
    sont utilisés en fallback (les deux sources peuvent coexister dans le même
    appel si les profils sont hétérogènes).

    Args:
        profils: liste de profils pivot v1.

    Returns:
        Tuple (liste triée par nb_membres_porteurs desc, tag_source).
        ``tag_source`` vaut "tags_thematiques", "mots_cles_interventions" ou "mixed".
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
            # Fallback : mots-clés bruts des interventions
            kw_set: set[str] = set()
            for interv in (profil.get("interventions") or []):
                for kw in (interv.get("mots_cles") or []):
                    cleaned = kw.strip().lower() if isinstance(kw, str) else ""
                    if cleaned:
                        kw_set.add(cleaned)
            tags = list(kw_set)
            if tags:
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
# Chargement et détection de format
# ---------------------------------------------------------------------------

def _is_pivot_v1(profil: dict[str, Any]) -> bool:
    """Retourne True si le profil est déjà au format pivot v1 (schema_version présent)."""
    return "schema_version" in profil and "id" in profil


def load_profil_from_file(path: Path) -> dict[str, Any]:
    """Charge un profil depuis un fichier JSON et le normalise en pivot v1 si nécessaire.

    Les profils au format brut NosDéputés (produits par candidate_profile.py) sont
    convertis automatiquement via normalize_nosdeputes.

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

    # Format brut NosDéputés (champ "slug" présent, pas de "schema_version")
    if "slug" in data:
        from normalize_nosdeputes import normalize_nosdeputes  # import local pour éviter les dépendances circulaires
        return normalize_nosdeputes(data)

    raise ValueError(
        f"Format non reconnu dans {path} : ni pivot v1 (schema_version + id) "
        "ni format brut NosDéputés (slug)."
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

    Returns:
        Profil de groupe dict conforme au schéma de groupe v1.
    """
    warnings: list[str] = []

    # --- Membres ---
    membres = [_derive_membre_entry(p) for p in profils]

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
    cohesion_votes = _compute_cohesion_votes(profils, seuil_quorum=seuil_quorum)

    # --- Tags thématiques ---
    tags_agreges, tag_source = _aggregate_tags_thematiques(profils)
    if tag_source == "mots_cles_interventions":
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
    profil_groupe["sources"] = sources

    profil_groupe["meta"]["licence_donnees"] = licence_donnees
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
            "Agrège des profils individuels (pivot v1 ou brut NosDéputés) "
            "en un profil de groupe politique."
        ),
    )
    parser.add_argument(
        "profils",
        nargs="+",
        metavar="PROFIL.json",
        help="Fichiers JSON des profils individuels des membres du groupe.",
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
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    # Chargement des profils
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

    profil_groupe = build_groupe_profile(
        groupe_id=args.groupe_id,
        groupe_sigle=args.groupe_sigle,
        groupe_nom=args.groupe_nom,
        chambre=args.chambre,
        legislature=args.legislature,
        profils=profils,
        seuil_quorum=args.seuil_quorum,
        licence_donnees=args.licence,
    )

    if args.validate:
        errors = validate_profil_groupe(profil_groupe)
        if errors:
            print(f"  [!] {len(errors)} erreur(s) de validation :", file=sys.stderr)
            for e in errors:
                print(f"      - {e}", file=sys.stderr)
        else:
            print("  ✓ Profil de groupe valide selon le schéma.", file=sys.stderr)

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
