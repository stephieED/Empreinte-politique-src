#!/usr/bin/env python3
"""
gouvernement_roster.py — Composition ministérielle d'un gouvernement, dérivée
des profils pivot individuels déjà collectés.

Aucun appel réseau : ce module ne fait que parcourir les pivots individuels
(`pivot_data/profiles/*.pivot.json`) déjà présents sur disque et en extraire
les mandats `categorie == "fonction_gouvernementale"` (peuplés depuis
`AMO30_tous_acteurs_tous_mandats_tous_organes_historique.json.zip`, voir
`candidate_profile.py`) qui appartiennent au gouvernement demandé.

Désambiguïsation : l'AN n'expose que `organe.libelleAbrege` (ex. "BORNE",
"LECORNU II") dans `mandats[].label` ("Gouvernement (<libelleAbrege>)"), ce
qui peut être ambigu entre deux gouvernements homonymes lors d'un
remaniement. La sélection d'un membre requiert donc :
  1. une correspondance exacte du libellé (`libelle_an`, tel que renseigné
     manuellement dans `raw_data/gouvernements_reels.json` — même principe de
     désambiguïsation éditoriale humaine que `groupes_reels.json`) ;
  2. un chevauchement de la période du mandat avec la période du gouvernement
     (garde-fou supplémentaire contre une anomalie de données, pas le critère
     principal — voir `_mandate_matches_gouvernement`).
Un mandat dont le libellé correspond mais dont la période ne chevauche pas du
tout celle du gouvernement est exclu (anomalie de données jugée plus sûre à
ignorer qu'à inclure) ; symétriquement, un mandat dont la période chevauche
mais dont le libellé diffère (autre gouvernement) est exclu — c'est
précisément le cas qui justifie de ne pas se fier à la seule période.

Même pattern que `group_profile._derive_membre_entry` (`src/group_profile.py`)
pour la dérivation des champs (nom, dates, statut actif) : un enregistrement
par mandat correspondant, donc potentiellement plusieurs entrées pour un même
membre si son mandat a été scindé en plusieurs périodes (changement de
portefeuille en cours de gouvernement) — cf. `schema_gouvernement.py`, qui
documente ce même principe pour `membres[]`.

`portefeuille` reste toujours `null` : aucune source fiable du titre précis
du portefeuille n'est disponible sans risque de faux positifs (déduction du
libellé ou recherche texte libre), gap documenté dans
`docs/technical_decisions.md#hors-perimetre` § "Ministerial function" — même
décision que pour `extra_parlementaire`. `source_url` reste donc également
`null` (obligatoire uniquement quand `portefeuille` est renseigné, cf.
`schema_gouvernement.validate_profil_gouvernement`).

Hors périmètre de ce module (sous-issue #5 de #184) :
  - Collecte des textes législatifs portés par le gouvernement.
  - Écriture d'un fichier `pivot_data/gouvernements/*.json` conforme au
    schéma complet `schema_gouvernement.py` (premier_ministre, textes,
    comptages...) : ce module ne produit que la liste `membres[]`.

Usage (depuis la racine du dépôt) :
    python src/gouvernement_roster.py \\
        --config raw_data/gouvernements_reels.json \\
        --gouvernement-id "gouvernement:LECORNU_II" \\
        --profiles-dir pivot_data/profiles
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any, Optional


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


def _periods_overlap(
    m_debut: Optional[date],
    m_fin: Optional[date],
    g_debut: Optional[date],
    g_fin: Optional[date],
) -> bool:
    """Teste le chevauchement de deux intervalles [debut, fin], bornes ouvertes si None.

    None en fin signifie « toujours en cours » ; None en début signifie
    « origine inconnue ». Une date manquante d'un côté ne permet jamais
    d'exclure : seule une incompatibilité explicite (une borne connue qui
    précède/suit strictement l'autre intervalle) exclut le chevauchement.
    """
    if m_debut is not None and g_fin is not None and m_debut > g_fin:
        return False
    if m_fin is not None and g_debut is not None and m_fin < g_debut:
        return False
    return True


# ---------------------------------------------------------------------------
# Sélection des mandats fonction_gouvernementale
# ---------------------------------------------------------------------------

def _expected_label(libelle_an: str) -> str:
    """Reconstruit le libellé attendu de mandats[].label pour un gouvernement.

    Miroir exact de la construction faite côté collecte
    (`candidate_profile.py`, § positions dans l'hémicycle) : `"Gouvernement
    (<libelleAbrege>)"`, ou `"Gouvernement"` seul si le sigle est absent.
    """
    return f"Gouvernement ({libelle_an})" if libelle_an else "Gouvernement"


def _mandate_matches_gouvernement(
    mandat: dict[str, Any],
    libelle_an: str,
    g_debut: Optional[date],
    g_fin: Optional[date],
) -> bool:
    """Détermine si un mandat individuel appartient au gouvernement ciblé.

    Voir la note de désambiguïsation en tête de module : correspondance
    exacte du libellé d'abord, chevauchement de période ensuite (garde-fou,
    pas critère principal).
    """
    if mandat.get("categorie") != "fonction_gouvernementale":
        return False
    if (mandat.get("label") or "") != _expected_label(libelle_an):
        return False
    return _periods_overlap(
        _parse_date(mandat.get("debut")),
        _parse_date(mandat.get("fin")),
        g_debut,
        g_fin,
    )


# ---------------------------------------------------------------------------
# Construction du roster
# ---------------------------------------------------------------------------

def _derive_membre_entry(profil: dict[str, Any], mandat: dict[str, Any]) -> dict[str, Any]:
    """Dérive une entrée `membres[]` (schéma `schema_gouvernement.py`) à partir
    d'un profil pivot et d'un mandat `fonction_gouvernementale` déjà sélectionné.
    """
    return {
        "membre_id": profil.get("id") or "",
        "nom": profil.get("nom") or "",
        "portefeuille": None,
        "debut": mandat.get("debut"),
        "fin": mandat.get("fin"),
        "actif": bool(mandat.get("actif")),
        "source_url": None,
    }


def build_gouvernement_roster(
    libelle_an: str,
    periode_debut: Optional[str],
    periode_fin: Optional[str],
    profils: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Construit la liste `membres[]` d'un gouvernement à partir de profils pivot.

    Args:
        libelle_an: `organe.libelleAbrege` du gouvernement tel qu'il apparaît
                    dans `mandats[].label` (ex. "LECORNU II", "BAYROU"), tel
                    que renseigné dans `raw_data/gouvernements_reels.json`.
        periode_debut: début de la période du gouvernement (YYYY-MM-DD), ou None.
        periode_fin: fin de la période du gouvernement (YYYY-MM-DD), ou None
                     si le gouvernement est toujours en fonction.
        profils: liste de profils pivot v1 (déjà chargés depuis
                 `pivot_data/profiles/*.pivot.json`).

    Returns:
        Liste de dicts conformes à la structure `membres[]` de
        `schema_gouvernement.py`, un enregistrement par mandat correspondant
        (potentiellement plusieurs par membre si son mandat a été scindé en
        plusieurs périodes).
    """
    g_debut = _parse_date(periode_debut)
    g_fin = _parse_date(periode_fin)

    membres: list[dict[str, Any]] = []
    for profil in profils:
        for mandat in profil.get("mandats") or []:
            if _mandate_matches_gouvernement(mandat, libelle_an, g_debut, g_fin):
                membres.append(_derive_membre_entry(profil, mandat))

    return membres


# ---------------------------------------------------------------------------
# Chargement des pivots
# ---------------------------------------------------------------------------

def load_profils_from_dir(profiles_dir: Path) -> list[dict[str, Any]]:
    """Charge tous les profils pivot v1 (`*.pivot.json`) d'un dossier.

    Un fichier illisible ou invalide est ignoré (signalé sur stderr), sans
    interrompre le chargement des autres profils.
    """
    profils: list[dict[str, Any]] = []
    for path in sorted(profiles_dir.glob("*.pivot.json")):
        try:
            with open(path, encoding="utf-8") as f:
                profils.append(json.load(f))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"  [!] {path} : {exc}", file=sys.stderr)
    return profils


def load_gouvernement_config(config_path: Path, gouvernement_id: str) -> dict[str, Any]:
    """Charge l'entrée d'un gouvernement depuis `raw_data/gouvernements_reels.json`.

    Raises:
        ValueError: fichier de config invalide ou `gouvernement_id` absent.
    """
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    for entry in payload.get("gouvernements") or []:
        if entry.get("gouvernement_id") == gouvernement_id:
            return entry
    raise ValueError(f"gouvernement_id {gouvernement_id!r} absent de {config_path}.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gouvernement_roster.py",
        description=(
            "Extrait la composition ministérielle d'un gouvernement à partir des "
            "profils pivot individuels déjà collectés. Aucun appel réseau."
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
        help="Ex. 'gouvernement:LECORNU_II' (doit exister dans --config).",
    )
    parser.add_argument(
        "--profiles-dir",
        default="pivot_data/profiles",
        metavar="DOSSIER",
        help="Dossier des pivots *.pivot.json (défaut : pivot_data/profiles).",
    )
    parser.add_argument(
        "--out",
        default=None,
        metavar="FICHIER",
        help="Fichier de sortie JSON (défaut : stdout).",
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
    print(f"→ {len(profils)} profil(s) pivot chargé(s). Extraction en cours…", file=sys.stderr)

    periode = entry.get("periode") or {}
    membres = build_gouvernement_roster(
        libelle_an=entry.get("libelle_an") or "",
        periode_debut=periode.get("debut"),
        periode_fin=periode.get("fin"),
        profils=profils,
    )
    print(f"→ {len(membres)} entrée(s) membres[] extraite(s).", file=sys.stderr)

    roster = {
        "gouvernement_id": entry.get("gouvernement_id"),
        "libelle_an": entry.get("libelle_an"),
        "periode": periode,
        "membres": membres,
    }
    output_json = json.dumps(roster, ensure_ascii=False, indent=2)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output_json, encoding="utf-8")
        print(f"  ✓ Roster écrit : {out_path}", file=sys.stderr)
    else:
        print(output_json)

    return 0


if __name__ == "__main__":
    sys.exit(main())
