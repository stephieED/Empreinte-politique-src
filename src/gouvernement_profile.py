#!/usr/bin/env python3
"""
gouvernement_profile.py — Agrégation d'un profil de gouvernement complet à
partir de la composition ministérielle (`gouvernement_roster.py`) et des
textes législatifs d'origine gouvernementale (`gouvernement_textes.py`).

Miroir de `group_profile.build_groupe_profile` au niveau conceptuel
(agrégation locale pure, aucun appel réseau ici), mais pour un gouvernement :
combine `membres[]` (composition ministérielle) et `textes[]` (dossiers
législatifs) en un objet conforme à `schema_gouvernement.py`.

Sources en entrée :
  - `profils` : l'ensemble des profils pivot individuels déjà collectés
    (`pivot_data/profiles/*.pivot.json`) — passés à
    `gouvernement_roster.build_gouvernement_roster` pour dériver `membres[]`
    (portefeuille ministériel compris, #398) et à
    `gouvernement_roster.build_premier_ministre` pour `premier_ministre`.
    Ces deux champs restent `null` quand aucun profil local ne porte le
    mandat correspondant — jamais une valeur déduite du nom du gouvernement
    (règle AGENTS.md §2.5) ; c'est le cas des 7 Premiers ministres qui n'ont
    pas de profil pivot dans le dépôt.
  - `dossiers_gouvernementaux` : la sortie *non filtrée* de
    `gouvernement_textes.collect_dossiers_gouvernementaux`/
    `fetch_dossiers_gouvernementaux` (tous les dossiers d'origine
    gouvernementale, tous gouvernements confondus). Le rattachement à CE
    gouvernement est explicitement hors périmètre de `gouvernement_textes.py`
    (voir sa docstring) : c'est ce module qui filtre par recouvrement de
    `date_depot` avec `periode`, jamais par date de conclusion — un texte
    déposé sous un gouvernement A puis conclu sous un gouvernement B reste
    crédité à A.

Lien ministre → texte (#435) : `textes[].initiateurs` porte les initiateurs
déclarés par la source (`initiateur.acteurs.acteur[].acteurRef`, extraits par
`gouvernement_textes.py`), résolus vers un `membre_id` quand l'`acteurRef`
correspond à un membre retenu dans `membres[]` — c'est ce module qui peut le
faire, lui seul connaissant la composition du gouvernement. La couverture est
partielle par construction (un initiateur peut n'avoir aucun profil pivot dans
le dépôt, cas des 7 Premiers ministres sans profil) : l'`acteurRef` brut est
alors conservé avec `membre_id = null`, jamais rattaché à un profil approchant
(AGENTS.md §2.5). Un texte sans initiateur déclaré porte `initiateurs = null`,
pas `[]` — voir `_initiateurs_texte`.

Comptages (`comptages.par_statut`) : simple dénombrement des `textes[]`
retenus par statut, aucun taux ni pourcentage calculé nulle part dans ce
module (règle AGENTS.md §2.1) — voir `_select_textes_gouvernement`.

Anti double-comptage : un dossier est identifié par `dossier_id`, dédoublonné
au sein d'un même appel (protège contre un même dossier présent deux fois
dans `dossiers_gouvernementaux`, ex. fetch dupliqué en amont). Comme chaque
appel à `build_gouvernement_profile` ne traite qu'un seul gouvernement, un
même dossier ne peut être compté deux fois pour deux gouvernements
différents QUE s'il a été déposé sous ces deux périodes à la fois, ce qui
n'arrive jamais pour des périodes de gouvernement non chevauchantes.
`generate_gouvernement_profiles.py` ne fetch les dossiers et ne charge les
profils qu'UNE SEULE FOIS, partagés entre tous les gouvernements du batch —
voir sa docstring.

Cas limites gérés :
  - Dossier avec `statut = None` (fam_code inconnu, voir
    `gouvernement_textes._determine_statut`) : exclu de `textes[]` (le
    schéma n'admet pas de statut `null`, jamais de valeur par défaut
    inventée — règle AGENTS.md §2.5), avertissement conservé dans
    `meta.warnings`.
  - Dossier avec `chambre_depot_initial = None` (aucun acte `-DEPOT`
    identifiable) : exclu de `textes[]` pour la même raison.
  - Dossier avec `date_depot = None` : ne peut être rattaché à aucune
    période de gouvernement de façon fiable → exclu silencieusement (pas un
    warning, cas attendu pour un dossier sans dépôt identifiable, symétrique
    au traitement dans `gouvernement_textes.py`).
  - `periode.fin = None` : gouvernement toujours en fonction, tout dossier
    dont `date_depot >= periode.debut` est retenu (borne haute ouverte).

Usage (depuis la racine du dépôt) :
    python src/gouvernement_profile.py \\
        --config raw_data/gouvernements_reels.json \\
        --gouvernement-id "gouvernement:BAYROU" \\
        --profiles-dir pivot_data/profiles \\
        --out pivot_data/gouvernements/gouvernement-BAYROU.json \\
        --validate

    Pour générer tous les gouvernements de `raw_data/gouvernements_reels.json`
    en un seul run (un seul fetch réseau des dossiers, un seul chargement des
    profils), voir `generate_gouvernement_profiles.py`.
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any, Optional

from licences import appliquer_licence_donnees
from schema_gouvernement import (
    KNOWN_CHAMBRES_DEPOT_TEXTE,
    KNOWN_STATUTS_TEXTE_GOUVERNEMENTAL,
    make_empty_comptages_statuts,
    make_empty_profil_gouvernement,
    validate_profil_gouvernement,
)
from gouvernement_roster import (
    acteur_ref_depuis_profil,
    build_gouvernement_roster,
    build_premier_ministre,
    load_gouvernement_config,
    load_profils_from_dir,
)


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


def _texte_dans_periode(date_depot: Optional[date], g_debut: Optional[date], g_fin: Optional[date]) -> bool:
    """Un texte appartient au gouvernement si sa date de dépôt initial se
    situe dans `[g_debut, g_fin]` (`g_fin = None` → gouvernement toujours en
    fonction, borne haute ouverte). Rattachement par date de dépôt
    uniquement, jamais par date de conclusion (voir docstring du module) :
    une date de dépôt inconnue n'est jamais rattachée par défaut.
    """
    if date_depot is None or g_debut is None:
        return False
    if date_depot < g_debut:
        return False
    if g_fin is not None and date_depot > g_fin:
        return False
    return True


# ---------------------------------------------------------------------------
# Résolution des initiateurs de texte vers les membres du gouvernement (#435)
# ---------------------------------------------------------------------------

def _index_acteur_ref_vers_membre(
    profils: list[dict[str, Any]],
    membre_ids: set[str],
    warnings: list[str],
) -> dict[str, str]:
    """Index `acteurRef` AN -> `membre_id` pivot, restreint aux membres retenus
    dans `membres[]`.

    Restreint volontairement aux membres de CE gouvernement : la source déclare
    les initiateurs d'un texte par référence nue, et un `acteurRef` peut
    désigner quelqu'un qui n'est pas membre du gouvernement auquel le texte est
    rattaché (co-signataire, ex-ministre — 15 % de faux positifs mesurés par le
    spike #207 quand cette chaîne servait de signal d'origine, voir
    `gouvernement_textes.py`). Hors de `membres[]`, l'`acteurRef` brut est
    conservé sans `membre_id` plutôt que rattaché à un profil quelconque.

    Deux profils différents portant le même `acteurRef` sont un conflit
    d'identité que ce module ne tranche pas : aucun des deux n'est indexé et un
    warning est émis (AGENTS.md §2.5).
    """
    refs_vers_ids: dict[str, set[str]] = {}
    for profil in profils:
        profil_id = profil.get("id")
        if not profil_id or profil_id not in membre_ids:
            continue
        acteur_ref = acteur_ref_depuis_profil(profil)
        if acteur_ref:
            refs_vers_ids.setdefault(acteur_ref, set()).add(profil_id)

    index: dict[str, str] = {}
    for acteur_ref, ids in refs_vers_ids.items():
        if len(ids) > 1:
            warnings.append(
                f"gouvernement_profile: acteurRef {acteur_ref!r} porté par plusieurs "
                f"profils ({sorted(ids)}) — aucun membre_id résolu pour cet initiateur."
            )
            continue
        index[acteur_ref] = next(iter(ids))
    return index


def _initiateurs_texte(
    acteur_refs: Optional[list[str]],
    acteur_ref_vers_membre: dict[str, str],
) -> Optional[list[dict[str, Any]]]:
    """Normalise les `acteurRef` d'un dossier en entrées
    `textes[].initiateurs` (#435), ou `None` si la source n'en déclare aucun.

    `None` et non `[]` : une liste vide affirmerait qu'aucun ministre n'a porté
    le texte, alors que le fait constaté est que la source ne le dit pas
    (AGENTS.md §2.5). `membre_id` reste `null` quand l'`acteurRef` n'est pas
    résolvable — la référence brute, elle, est toujours conservée.
    """
    if not acteur_refs:
        return None
    return [
        {
            "acteur_ref": acteur_ref,
            "membre_id": acteur_ref_vers_membre.get(acteur_ref),
        }
        for acteur_ref in acteur_refs
    ]


# ---------------------------------------------------------------------------
# Sélection et normalisation des textes du gouvernement
# ---------------------------------------------------------------------------

def _select_textes_gouvernement(
    dossiers_gouvernementaux: list[dict[str, Any]],
    g_debut: Optional[date],
    g_fin: Optional[date],
    acteur_ref_vers_membre: Optional[dict[str, str]] = None,
) -> tuple[list[dict[str, Any]], dict[str, int], list[str]]:
    """Filtre `dossiers_gouvernementaux` (sortie non filtrée de
    `gouvernement_textes`) sur la période du gouvernement, normalise chaque
    dossier retenu en entrée `textes[]` du schéma, et dénombre les statuts.

    `acteur_ref_vers_membre` (voir `_index_acteur_ref_vers_membre`) résout les
    initiateurs déclarés par la source vers un `membre_id`. Absent, les
    initiateurs sont conservés avec leur seul `acteurRef` : c'est une couverture
    réduite, jamais un lien deviné.

    Returns:
        Tuple (textes retenus, comptages.par_statut, warnings). Aucun taux
        calculé : `comptages` ne contient que des entiers bruts (règle
        AGENTS.md §2.1).
    """
    acteur_ref_vers_membre = acteur_ref_vers_membre or {}
    seen_ids: set[str] = set()
    textes: list[dict[str, Any]] = []
    par_statut = make_empty_comptages_statuts()
    warnings: list[str] = []

    for dossier in dossiers_gouvernementaux:
        dossier_id = dossier.get("dossier_id")
        if dossier_id:
            if dossier_id in seen_ids:
                continue  # anti double-comptage : dossier déjà traité dans cet appel
            seen_ids.add(dossier_id)

        parsed_date_depot = _parse_date(dossier.get("date_depot"))
        if not _texte_dans_periode(parsed_date_depot, g_debut, g_fin):
            continue

        for w in dossier.get("warnings") or []:
            warnings.append(w)

        statut = dossier.get("statut")
        chambre = dossier.get("chambre_depot_initial")

        if statut is None or statut not in KNOWN_STATUTS_TEXTE_GOUVERNEMENTAL:
            warnings.append(
                f"gouvernement_profile: dossier {dossier_id!r} exclu de textes[] : "
                f"statut indéterminé ou inconnu ({statut!r})."
            )
            continue
        if chambre not in KNOWN_CHAMBRES_DEPOT_TEXTE:
            warnings.append(
                f"gouvernement_profile: dossier {dossier_id!r} exclu de textes[] : "
                f"chambre_depot_initial indéterminée ({chambre!r})."
            )
            continue

        textes.append({
            "dossier_id": dossier_id,
            "titre": dossier.get("titre"),
            "statut": statut,
            "chambre_depot_initial": chambre,
            "date_depot": dossier.get("date_depot"),
            "date_dernier_evenement": dossier.get("date_dernier_evenement"),
            "sort_49_3": dossier.get("sort_49_3"),
            "initiateurs": _initiateurs_texte(
                dossier.get("initiateurs_acteur_refs"), acteur_ref_vers_membre
            ),
            "source_url": dossier.get("source_url"),
        })
        par_statut[statut] += 1

    return textes, par_statut, warnings


# ---------------------------------------------------------------------------
# Fonction principale d'agrégation
# ---------------------------------------------------------------------------

def build_gouvernement_profile(
    gouvernement_id: str,
    nom: str,
    libelle_an: str,
    periode_debut: Optional[str],
    periode_fin: Optional[str],
    profils: list[dict[str, Any]],
    dossiers_gouvernementaux: list[dict[str, Any]],
    licence_donnees: str = "",
) -> dict[str, Any]:
    """Construit un profil de gouvernement à partir des profils pivot
    individuels déjà collectés et des dossiers législatifs d'origine
    gouvernementale déjà collectés (non filtrés par gouvernement).

    Args:
        gouvernement_id: ex. "gouvernement:BAYROU".
        nom: nom complet, ex. "Gouvernement Bayrou".
        libelle_an: `organe.libelleAbrege` AN du gouvernement (désambiguïsation,
                    voir `gouvernement_roster.py`), ex. "BAYROU".
        periode_debut: début de la période du gouvernement (YYYY-MM-DD).
        periode_fin: fin de la période (YYYY-MM-DD), ou None si toujours en fonction.
        profils: liste de profils pivot v1 (tous les profils disponibles, pas
                 seulement ceux du gouvernement — le filtrage par mandat
                 revient à `gouvernement_roster.build_gouvernement_roster`).
        dossiers_gouvernementaux: sortie non filtrée de
                 `gouvernement_textes.collect_dossiers_gouvernementaux`/
                 `fetch_dossiers_gouvernementaux` (`["dossiers"]`).
        licence_donnees: texte de licence à inscrire dans meta.

    Returns:
        Profil de gouvernement dict conforme à `schema_gouvernement.py`.
    """
    warnings: list[str] = []

    membres = build_gouvernement_roster(
        libelle_an=libelle_an,
        periode_debut=periode_debut,
        periode_fin=periode_fin,
        profils=profils,
        warnings=warnings,
    )
    premier_ministre = build_premier_ministre(
        libelle_an=libelle_an,
        periode_debut=periode_debut,
        periode_fin=periode_fin,
        profils=profils,
        warnings=warnings,
    )

    membre_ids = {m["membre_id"] for m in membres if m.get("membre_id")}

    g_debut = _parse_date(periode_debut)
    g_fin = _parse_date(periode_fin)
    acteur_ref_vers_membre = _index_acteur_ref_vers_membre(profils, membre_ids, warnings)
    textes, par_statut, textes_warnings = _select_textes_gouvernement(
        dossiers_gouvernementaux, g_debut, g_fin, acteur_ref_vers_membre
    )
    warnings.extend(textes_warnings)

    # --- Sources (dédoublonnées) : uniquement celles des profils des membres
    # effectivement retenus dans membres[], pas de tous les profils passés en
    # entrée (qui couvrent potentiellement l'ensemble du dépôt).
    seen_sources: set[tuple[str, str]] = set()
    sources: list[dict[str, Any]] = []
    for p in profils:
        if p.get("id") not in membre_ids:
            continue
        for s in (p.get("sources") or []):
            key = (s.get("type") or "", s.get("url") or "")
            if key not in seen_sources:
                seen_sources.add(key)
                sources.append(s)

    profil_gouvernement = make_empty_profil_gouvernement(gouvernement_id=gouvernement_id, nom=nom)
    profil_gouvernement["periode"] = {
        "debut": periode_debut,
        "fin": periode_fin,
        "actif": periode_fin is None,
    }
    profil_gouvernement["premier_ministre"] = premier_ministre
    profil_gouvernement["membres"] = membres
    profil_gouvernement["textes"] = textes
    profil_gouvernement["comptages"]["par_statut"] = par_statut
    profil_gouvernement["sources"] = sources
    # `licence_donnees` : dérivée de `sources[]` quand l'appelant n'impose rien
    # (#530, lot 6). Le pipeline ne passe pas `--licence`, et les 10 fiches
    # publiées portaient donc une attribution **vide** — un manque, sur des
    # documents dérivés de données ouvertes qui en exigent une (AGENTS.md §7).
    # La dérivation, et non une constante : `sources[]` agrège ici celles des profils membres, qui ne relèvent pas
    # toutes de la même licence. L'argument explicite reste
    # prioritaire, c'est lui qui permet d'annoter une fiche hors pipeline.
    if licence_donnees:
        profil_gouvernement["meta"]["licence_donnees"] = licence_donnees
    else:
        appliquer_licence_donnees(profil_gouvernement)
    profil_gouvernement["meta"]["warnings"] = warnings

    return profil_gouvernement


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gouvernement_profile.py",
        description=(
            "Combine la composition ministérielle (gouvernement_roster.py) et les "
            "textes législatifs (gouvernement_textes.py) en un profil de gouvernement "
            "complet, conforme à schema_gouvernement.py."
        ),
    )
    parser.add_argument(
        "--config",
        default="raw_data/gouvernements_reels.json",
        metavar="FICHIER",
        help="Fichier de référence des gouvernements (défaut : raw_data/gouvernements_reels.json).",
    )
    parser.add_argument(
        "--gouvernement-id",
        required=True,
        metavar="ID",
        help="Ex. 'gouvernement:BAYROU' (doit exister dans --config).",
    )
    parser.add_argument(
        "--profiles-dir",
        default="pivot_data/profiles",
        metavar="DOSSIER",
        help="Dossier des pivots *.pivot.json (défaut : pivot_data/profiles).",
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
        help="Valide le profil de gouvernement produit et affiche les erreurs éventuelles.",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    config_path = Path(args.config)
    try:
        entry = load_gouvernement_config(config_path, args.gouvernement_id)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[!] {exc}", file=sys.stderr)
        return 1

    profils = load_profils_from_dir(Path(args.profiles_dir))
    print(f"→ {len(profils)} profil(s) pivot chargé(s).", file=sys.stderr)

    from gouvernement_textes import fetch_dossiers_gouvernementaux  # import tardif : réseau non requis hors CLI

    print("→ Récupération des dossiers législatifs gouvernementaux…", file=sys.stderr)
    dossiers_result = fetch_dossiers_gouvernementaux()
    print(f"→ {len(dossiers_result['dossiers'])} dossier(s) d'origine gouvernementale récupéré(s).", file=sys.stderr)

    periode = entry.get("periode") or {}
    profil_gouvernement = build_gouvernement_profile(
        gouvernement_id=entry.get("gouvernement_id"),
        nom=entry.get("nom"),
        libelle_an=entry.get("libelle_an") or "",
        periode_debut=periode.get("debut"),
        periode_fin=periode.get("fin"),
        profils=profils,
        dossiers_gouvernementaux=dossiers_result["dossiers"],
        licence_donnees=args.licence,
    )
    if dossiers_result["warnings"]:
        profil_gouvernement["meta"]["warnings"].extend(dossiers_result["warnings"])

    if args.validate:
        errors = validate_profil_gouvernement(profil_gouvernement)
        if errors:
            print(f"  [!] {len(errors)} erreur(s) de validation :", file=sys.stderr)
            for e in errors:
                print(f"      - {e}", file=sys.stderr)
        else:
            print("  ✓ Profil de gouvernement valide selon le schéma.", file=sys.stderr)

    output_json = json.dumps(profil_gouvernement, ensure_ascii=False, indent=2)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output_json, encoding="utf-8")
        print(f"  ✓ Profil de gouvernement écrit : {out_path}", file=sys.stderr)
    else:
        print(output_json)

    return 0


if __name__ == "__main__":
    sys.exit(main())
