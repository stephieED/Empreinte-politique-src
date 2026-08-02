#!/usr/bin/env python3
"""Module documentation in English."""

import argparse
import json
import sys
import time
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any, Optional

from schema_groupe import (
    SCHEMA_GROUPE_VERSION,
    AMENDEMENTS_TYPES_DEPOSANT,
    make_empty_profil_groupe,
    make_empty_amendements_stats,
    validate_profil_groupe,
)
from normalize_nosdeputes import normalize_nosdeputes


# ---------------------------------------------------------------------------
# Helpers de dates
# ---------------------------------------------------------------------------

def _parse_date(s: Any) -> Optional[date]:
    """English docstring for  parse date."""   if not s or not isinstance(s, str):
        return None
    try:
        return date.fromisoformat(s[:10])
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Translated comment.
# ---------------------------------------------------------------------------

def _member_eligibility_intervals(mandats: list[dict[str, Any]]) -> Optional[list[tuple[Optional[date], Optional[date]]]]:
    """English docstring for  member eligibility intervals."""
    electif = [m for m in mandats if m.get("categorie") == "mandat_electif"]
    if not electif:
        return None
    return [(_parse_date(m.get("debut")), _parse_date(m.get("fin"))) for m in electif]


def _is_eligible_at(intervals: Optional[list[tuple[Optional[date], Optional[date]]]], d: Optional[date]) -> bool:
    """English docstring for  is eligible at.""" d is None or intervals is None:
        return True  # Translated comment.
    for debut, fin in intervals:
        if debut is not None and d < debut:
            continue
        if fin is not None and d > fin:
            continue
        return True  # Translated comment.
    return False


def _member_eligible_at(mandats: list[dict[str, Any]], vote_date: Optional[str]) -> bool:
    """English docstring for  member eligible at."""
    return _is_eligible_at(_member_eligibility_intervals(mandats), _parse_date(vote_date))


# ---------------------------------------------------------------------------
# Translated comment.
# ---------------------------------------------------------------------------

def _derive_membre_entry(profil: dict[str, Any]) -> dict[str, Any]:
    """English docstring for  derive membre entry."""
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

        # Translated comment.
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
    """English docstring for  build vote index."""
    index: dict[str, dict[str, Any]] = {}
    for v in (profil.get("votes") or []):
        num = v.get("numero_scrutin")
        if num is not None:
            index[str(num)] = v
    return index


# ---------------------------------------------------------------------------
# Translated comment.
# ---------------------------------------------------------------------------

def _compute_cohesion_votes(
    profils: list[dict[str, Any]],
    seuil_quorum: float = 0.5,
) -> list[dict[str, Any]]:
    """English docstring for  compute cohesion votes."""
    # Translated comment.
    # Translated comment.
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

    # Translated comment.
    # Translated comment.
    # Translated comment.
    # Translated comment.
    vote_indexes = [_build_vote_index(p) for p in profils]
    eligibility_intervals = [_member_eligibility_intervals(p.get("mandats") or []) for p in profils]

    # --- 3. Calcul par scrutin ---
    _EXPRESSED = ("pour", "contre", "abstention")

    cohesion: list[dict[str, Any]] = []
    for num_str, meta in scrutins.items():
        vote_date = meta["date"]
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

            vote = v_index.get(num_str)
            if vote is None:
                compteurs["absent"] += 1
            else:
                pos = vote.get("position") or "absent"
                compteurs[pos] = compteurs.get(pos, 0) + 1

        if n_eligible == 0:
            continue

        # Translated comment.
        # Translated comment.
        # Translated comment.
        # Translated comment.
        # Translated comment.
        # Translated comment.
        # Translated comment.
        votes_exprimes = sum(compteurs[p] for p in _EXPRESSED)
        if votes_exprimes == 0:
            position_majoritaire = None
        else:
            position_majoritaire = max(_EXPRESSED, key=lambda p: compteurs[p])

        # Translated comment.
        n_absent = compteurs["absent"] + compteurs["excuse"]
        taux_participation = (n_eligible - n_absent) / n_eligible

        # Translated comment.
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

    # Translated comment.
    cohesion.sort(key=lambda x: x["date"] or "", reverse=True)
    return cohesion


# ---------------------------------------------------------------------------
# Translated comment.
# ---------------------------------------------------------------------------

def aggregate_tags_thematiques(
    profils: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], Optional[str]]:
    """English docstring for aggregate tags thematiques."""
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
            # Translated comment.
            kw_set: set[str] = set()
            for interv in (profil.get("interventions") or []):
                for kw in (interv.get("mots_cles") or []):
                    cleaned = kw.strip().lower() if isinstance(kw, str) else ""
                    if cleaned:
                        kw_set.add(cleaned)
            tags = list(kw_set)
            if tags:
                sources_used.add("mots_cles_interventions")

        # Translated comment.
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
# Translated comment.
# ---------------------------------------------------------------------------

def _normalize_sort_amendement(sort: Any) -> str:
    """English docstring for  normalize sort amendement."""
    if not isinstance(sort, str):
        return ""
    s = unicodedata.normalize("NFKD", sort.strip().lower())
    return "".join(c for c in s if not unicodedata.combining(c))


_SORTS_ADOPTES = frozenset({"adopte"})
_SORTS_IRRECEVABLES = frozenset({"irrecevable"})
_SORTS_REJETES = frozenset({"rejete"})
_SORTS_RETIRES_OU_TOMBES = frozenset({"retire", "tombe", "non_soutenu", "non soutenu"})


def _aggregate_amendements(profils: list[dict[str, Any]]) -> dict[str, Any]:
    """English docstring for  aggregate amendements."""
    total = make_empty_amendements_stats()
    par_type = {t: make_empty_amendements_stats() for t in AMENDEMENTS_TYPES_DEPOSANT}

    for profil in profils:
        for a in (profil.get("amendements") or []):
            sort_norm = _normalize_sort_amendement(a.get("sort"))
            type_deposant = a.get("type_deposant")
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
    return total


# ---------------------------------------------------------------------------
# Translated comment.
#
# Translated comment.
# Translated comment.
# Translated comment.
# Translated comment.
# ---------------------------------------------------------------------------

def compute_ecarts_cohesion_internes(
    profils: list[dict[str, Any]],
    cohesion_votes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """English docstring for compute ecarts cohesion internes."""
    if not cohesion_votes:
        return []

    # Translated comment.
    participations = [c["taux_participation"] for c in cohesion_votes if c.get("taux_participation") is not None]
    coherences = [c["taux_coherence"] for c in cohesion_votes if c.get("taux_coherence") is not None]
    moyenne_participation_groupe = sum(participations) / len(participations) if participations else None
    moyenne_coherence_groupe = sum(coherences) / len(coherences) if coherences else None

    coh_by_scrutin = {c["numero_scrutin"]: c for c in cohesion_votes}

    resultats: list[dict[str, Any]] = []
    for profil in profils:
        mandats = profil.get("mandats") or []
        v_index = _build_vote_index(profil)

        n_eligible = 0
        n_present = 0
        n_alignes = 0

        for num_str, c in coh_by_scrutin.items():
            if not _member_eligible_at(mandats, c.get("date")):
                continue
            n_eligible += 1

            vote = v_index.get(num_str)
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
# Translated comment.
# ---------------------------------------------------------------------------

def _is_pivot_v1(profil: dict[str, Any]) -> bool:
    """English docstring for  is pivot v1."""  return "schema_version" in profil and "id" in profil


def load_profil_from_file(path: Path) -> dict[str, Any]:
    """English docstring for load profil from file."""
    with open(path, encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as exc:
            raise ValueError(f"JSON invalide dans {path} : {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"Attendu un dict JSON, reçu {type(data).__name__} dans {path}.")

    if _is_pivot_v1(data):
        return data

    # Translated comment.
    if "slug" in data:
        return normalize_nosdeputes(data)

    raise ValueError(
        f"Format non reconnu dans {path} : ni pivot v1 (schema_version + id) "
        "ni format brut NosDéputés (slug)."
    )


# ---------------------------------------------------------------------------
# Translated comment.
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
    """English docstring for build groupe profile."""
    warnings: list[str] = []

    # --- Membres ---
    membres = [_derive_membre_entry(p) for p in profils]

    # --- Effectif ---
    n_actif = sum(1 for m in membres if m["actif"])
    effectif: dict[str, Any] = {
        "actuel": n_actif,
        "min_historique": None,  # Translated comment.
        "max_historique": None,
    }

    # Translated comment.
    all_debuts = [_parse_date(m["debut_dans_groupe"]) for m in membres]
    all_fins = [_parse_date(m["fin_dans_groupe"]) for m in membres]
    parsed_debuts = [d for d in all_debuts if d is not None]

    periode_debut = str(min(parsed_debuts)) if parsed_debuts else None
    # Translated comment.
    groupe_actif = any(m["actif"] for m in membres)
    if groupe_actif:
        periode_fin = None
    else:
        parsed_fins = [f for f in all_fins if f is not None]
        periode_fin = str(max(parsed_fins)) if parsed_fins else None

    # Translated comment.
    cohesion_votes = _compute_cohesion_votes(profils, seuil_quorum=seuil_quorum)

    # Translated comment.
    tags_agreges, tag_source = aggregate_tags_thematiques(profils)
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

    # Translated comment.
    seen_sources: set[tuple[str, str]] = set()
    sources: list[dict[str, Any]] = []
    for p in profils:
        for s in (p.get("sources") or []):
            key = (s.get("type") or "", s.get("url") or "")
            if key not in seen_sources:
                seen_sources.add(key)
                sources.append(s)

    # Translated comment.
    amendements_agreges = _aggregate_amendements(profils)

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
    profil_groupe["amendements_agreges"] = amendements_agreges
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
        nargs="*",
        metavar="PROFIL.json",
        help="Fichiers JSON des profils individuels des membres du groupe (ignoré avec --from-roster).",
    )
    parser.add_argument(
        "--from-roster",
        action="store_true",
        help=(
            "Récupère la composition réelle du groupe via group_roster.py "
            "(NosDéputés.fr/NosSénateurs.fr) au lieu des fichiers PROFIL.json."
        ),
    )
    parser.add_argument(
        "--roster-chambre",
        choices=["deputes", "senateurs"],
        default=None,
        help="Requis avec --from-roster : chambre interrogée pour la composition du groupe.",
    )
    parser.add_argument(
        "--roster-senat-periode-debut",
        default=None,
        metavar="YYYY-MM-DD",
        help="Avec --from-roster --roster-chambre senateurs : filtre les membres par date (voir group_roster.py).",
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
) -> dict[str, Any]:
    """English docstring for generate groupe profile from roster."""
    print(f"→ {len(roster)} membre(s) réel(s) trouvé(s) pour {groupe_sigle!r}.", file=sys.stderr)

    # Translated comment.
    # Translated comment.
    # Translated comment.
    # Translated comment.
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
    if roster_chambre == "deputes":
        profil_groupe["meta"]["warnings"].append(
            "fraicheur_donnees : composition dérivée de www.nosdeputes.fr, qui "
            "n'a plus été mis à jour depuis la dissolution du 9 juin 2024 (16e "
            "législature, 2022-2024, 100% des mandats y figurent comme terminés). "
            "Ce profil reflète donc la DERNIÈRE COMPOSITION CONNUE avant la "
            "dissolution, pas nécessairement la composition actuelle de "
            "l'Assemblée nationale."
        )
    elif roster_chambre == "senateurs":
        profil_groupe["meta"]["warnings"].append(
            "fraicheur_donnees : composition dérivée de archive.nossenateurs.fr, "
            "site arrêté par Regards Citoyens (plus de mise à jour, pas de champ "
            "mandat_fin exploitable). Ce profil reflète donc la dernière donnée "
            "disponible avant l'arrêt du site, pas nécessairement la composition "
            "actuelle du Sénat (ex. incompatibilités liées à une fonction "
            "ministérielle non détectables automatiquement)."
        )

    if validate:
        errors = validate_profil_groupe(profil_groupe)
        if errors:
            print(f"  [!] {len(errors)} erreur(s) de validation :", file=sys.stderr)
            for e in errors:
                print(f"      - {e}", file=sys.stderr)
        else:
            print("  ✓ Profil de groupe valide selon le schéma.", file=sys.stderr)

    if rapport_interne_path:
        rapport = compute_ecarts_cohesion_internes(profils, profil_groupe["cohesion_votes"])
        rapport_interne_path.parent.mkdir(parents=True, exist_ok=True)
        rapport_interne_path.write_text(
            json.dumps(rapport, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"  ✓ Rapport interne (non public) écrit : {rapport_interne_path}", file=sys.stderr)

    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(profil_groupe, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  ✓ Profil de groupe écrit : {out_path}", file=sys.stderr)

    return profil_groupe


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    if args.from_roster:
        if not args.roster_chambre:
            print("[!] --from-roster requiert --roster-chambre (deputes|senateurs).", file=sys.stderr)
            return 1
        from group_roster import fetch_group_roster  # import tardif : requests non requis hors ce mode
        import requests

        legislature = args.legislature if args.roster_chambre == "deputes" else None
        try:
            roster = fetch_group_roster(
                chambre=args.roster_chambre,
                groupe_sigle=args.groupe_sigle,
                legislature=legislature,
                senat_periode_debut=args.roster_senat_periode_debut,
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

    if args.rapport_interne:
        rapport = compute_ecarts_cohesion_internes(profils, profil_groupe["cohesion_votes"])
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
