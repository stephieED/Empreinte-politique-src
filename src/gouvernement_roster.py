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

`portefeuille` (#398) vient des mandats `typeOrgane == "MINISTERE"` exposés
par le même zip AMO30 et mappés en `fonction_gouvernementale` depuis #382/#383
(« Ministère de l'éducation nationale et de la jeunesse », « Secrétariat
d'État auprès du Premier ministre… »). La catégorie mélange donc deux natures
de mandats, que seul le label distingue — voir
`_est_mandat_appartenance_gouvernement`. Un portefeuille n'est retenu que s'il
chevauche le mandat d'appartenance du membre, et **tous** les portefeuilles
chevauchants le sont : un ministre qui change de portefeuille en cours de
gouvernement produit une entrée `membres[]` par période, jamais un
portefeuille choisi arbitrairement parmi les siens. `portefeuille` retombe à
`null` (avec un warning) si aucune `source_url` n'est traçable, le schéma
l'exigeant dès que l'intitulé est renseigné. La limite inverse est levée :
`docs/technical_decisions.md#hors-perimetre` § "Ministerial function" est
marquée RÉSOLU.

`premier_ministre` (#398, `build_premier_ministre`) se dérive du même
matériau : le membre du gouvernement dont un mandat `MINISTERE` porte le label
« Premier ministre ». Aucun appariement par la seule période, aucune déduction
depuis le nom du gouvernement — voir la docstring de la fonction.

Hors périmètre de ce module (sous-issue #5 de #184) :
  - Collecte des textes législatifs portés par le gouvernement.
  - Écriture d'un fichier `pivot_data/gouvernements/*.json` conforme au
    schéma complet `schema_gouvernement.py` (textes, comptages...) : ce module
    ne produit que `membres[]` et l'entrée `premier_ministre`.

Usage (depuis la racine du dépôt) :
    python src/gouvernement_roster.py \\
        --config raw_data/gouvernements_reels.json \\
        --gouvernement-id "gouvernement:LECORNU_II" \\
        --profiles-dir pivot_data/profiles
"""

import argparse
import json
import re
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


def _est_mandat_appartenance_gouvernement(label: str) -> bool:
    """Distingue les deux natures de mandats `fonction_gouvernementale`.

    La catégorie en mélange deux, issues du même zip AMO30 mais de deux
    `typeOrgane` différents (voir `candidate_profile._TYPE_ORGANE_TO_CATEGORIE`) :
      - `GOUVERNEMENT` : l'appartenance au gouvernement, label « Gouvernement
        (<libelleAbrege>) » — c'est le mandat qui rattache un membre à CE
        gouvernement (`_mandate_matches_gouvernement`) ;
      - `MINISTERE` : le portefeuille précis, label « Ministère de… »,
        « Secrétariat d'État… », « Premier ministre » (#382/#383).

    Le label est le seul discriminant : `categorie` est identique pour les
    deux, et `position_dans_hemicycle` n'est renseigné que sur les premiers.
    """
    return label == "Gouvernement" or (
        label.startswith("Gouvernement (") and label.endswith(")")
    )


def _mandats_portefeuille(profil: dict[str, Any]) -> list[dict[str, Any]]:
    """Mandats `MINISTERE` d'un profil : les mandats `fonction_gouvernementale`
    qui portent un intitulé de portefeuille plutôt qu'une appartenance."""
    return [
        mandat
        for mandat in (profil.get("mandats") or [])
        if mandat.get("categorie") == "fonction_gouvernementale"
        and not _est_mandat_appartenance_gouvernement(mandat.get("label") or "")
    ]


def _portefeuilles_du_mandat(
    profil: dict[str, Any], mandat_gouvernemental: dict[str, Any]
) -> list[dict[str, Any]]:
    """Mandats de portefeuille chevauchant un mandat d'appartenance donné,
    triés par date de début (l'ordre chronologique de la source).

    Le chevauchement se teste contre la période du **mandat** du membre, pas
    contre celle du gouvernement : un ministre entré en cours de mandature ne
    doit pas se voir attribuer le portefeuille qu'il occupait avant.
    """
    m_debut = _parse_date(mandat_gouvernemental.get("debut"))
    m_fin = _parse_date(mandat_gouvernemental.get("fin"))
    chevauchants = [
        portefeuille
        for portefeuille in _mandats_portefeuille(profil)
        if _periods_overlap(
            _parse_date(portefeuille.get("debut")),
            _parse_date(portefeuille.get("fin")),
            m_debut,
            m_fin,
        )
    ]
    return sorted(chevauchants, key=lambda p: p.get("debut") or "")


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

def _source_url_portefeuille(
    portefeuille: dict[str, Any], mandat_gouvernemental: dict[str, Any]
) -> Optional[str]:
    """URL traçant l'intitulé du portefeuille, ou None si aucune n'est
    disponible — auquel cas le portefeuille n'est pas renseigné du tout.

    Les mandats `MINISTERE` sortent de `candidate_profile._extract_mandats_officiels`
    sans `source_url` (aucun mandat de ce chemin n'en porte). Le repli est le
    `source_url` du mandat d'appartenance du même membre : les deux mandats
    proviennent du **même** zip AMO30 (`AN_ACTEURS_HISTORIQUE_ZIP_URL`), le
    second se contentant de le porter explicitement. Ce n'est donc pas une URL
    inventée pour satisfaire le validateur, c'est la source réelle de l'intitulé.
    """
    return portefeuille.get("source_url") or mandat_gouvernemental.get("source_url")


def _derive_membre_entry(
    profil: dict[str, Any],
    mandat: dict[str, Any],
    portefeuille: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Dérive une entrée `membres[]` (schéma `schema_gouvernement.py`) à partir
    d'un profil pivot et d'un mandat `fonction_gouvernementale` déjà sélectionné.

    Avec un `portefeuille` (mandat `MINISTERE` chevauchant, #398), l'entrée
    porte l'intitulé précis et **les dates du portefeuille**, pas celles du
    mandat d'appartenance : c'est ce que décrit `schema_gouvernement.py` par
    « un enregistrement par ministre et par période si changement de
    portefeuille ». Sans portefeuille, le comportement d'origine est conservé
    (dates du mandat d'appartenance, `portefeuille`/`source_url` à `null`).
    """
    if portefeuille is None:
        return {
            "membre_id": profil.get("id") or "",
            "nom": profil.get("nom") or "",
            "portefeuille": None,
            "debut": mandat.get("debut"),
            "fin": mandat.get("fin"),
            "actif": bool(mandat.get("actif")),
            "source_url": None,
        }

    return {
        "membre_id": profil.get("id") or "",
        "nom": profil.get("nom") or "",
        "portefeuille": portefeuille.get("label"),
        "debut": portefeuille.get("debut"),
        "fin": portefeuille.get("fin"),
        "actif": bool(portefeuille.get("actif")),
        "source_url": _source_url_portefeuille(portefeuille, mandat),
    }


def build_gouvernement_roster(
    libelle_an: str,
    periode_debut: Optional[str],
    periode_fin: Optional[str],
    profils: list[dict[str, Any]],
    warnings: Optional[list[str]] = None,
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
        warnings: liste optionnelle où consigner les anomalies (portefeuille
                  trouvé mais non traçable). Même motif que
                  `candidate_profile.fetch_amendements_officiels`.

    Returns:
        Liste de dicts conformes à la structure `membres[]` de
        `schema_gouvernement.py`, un enregistrement par mandat correspondant —
        et, depuis #398, un enregistrement par **période de portefeuille** dès
        qu'un mandat d'appartenance en chevauche plusieurs (un ministre qui
        change de portefeuille en cours de gouvernement).
    """
    g_debut = _parse_date(periode_debut)
    g_fin = _parse_date(periode_fin)

    membres: list[dict[str, Any]] = []
    for profil in profils:
        for mandat in profil.get("mandats") or []:
            if not _mandate_matches_gouvernement(mandat, libelle_an, g_debut, g_fin):
                continue

            # Tous les portefeuilles chevauchants sont retenus, jamais un seul
            # choisi arbitrairement (#398) : quand un ministre en change en
            # cours de gouvernement, les périodes se succèdent et pavent le
            # mandat d'appartenance — les fondre en une entrée effacerait un
            # des deux portefeuilles réellement occupés.
            portefeuilles: list[dict[str, Any]] = []
            for portefeuille in _portefeuilles_du_mandat(profil, mandat):
                if _source_url_portefeuille(portefeuille, mandat):
                    portefeuilles.append(portefeuille)
                elif warnings is not None:
                    # Le schéma exige `source_url` dès que `portefeuille` est
                    # renseigné : sans traçabilité, on retombe sur `null`
                    # plutôt que de publier un intitulé invérifiable (§2.3).
                    warnings.append(
                        f"gouvernement_roster: {profil.get('nom') or profil.get('id')} : "
                        f"portefeuille {portefeuille.get('label')!r} sans source_url "
                        f"traçable — portefeuille non renseigné."
                    )

            if not portefeuilles:
                membres.append(_derive_membre_entry(profil, mandat))
                continue
            for portefeuille in portefeuilles:
                membres.append(_derive_membre_entry(profil, mandat, portefeuille))

    return membres


# ---------------------------------------------------------------------------
# Premier ministre
# ---------------------------------------------------------------------------

# Intitulé exact du mandat `MINISTERE` correspondant au chef du gouvernement.
# C'est un libellé d'organe de la source AN, pas une convention de notre part.
LABEL_PORTEFEUILLE_PREMIER_MINISTRE = "Premier ministre"


def _acteur_ref_depuis_profil(profil: dict[str, Any]) -> Optional[str]:
    """Extrait l'`acteurRef` AN (ex. `PA722190`) de l'URL de fiche du profil.

    `schema_pivot` n'expose pas l'identifiant du référentiel AN en tant que
    champ : il n'est présent que dans `identite.source_url`
    (`.../deputes/fiche/OMC_PA722190`). L'extraction est un simple motif, pas
    une déduction — absent ou d'une autre forme (fiche Sénat), on retourne
    None plutôt qu'un identifiant reconstruit.
    """
    source_url = (profil.get("identite") or {}).get("source_url") or ""
    correspondance = re.search(r"(PA\d+)", source_url)
    return correspondance.group(1) if correspondance else None


def build_premier_ministre(
    libelle_an: str,
    periode_debut: Optional[str],
    periode_fin: Optional[str],
    profils: list[dict[str, Any]],
    warnings: Optional[list[str]] = None,
) -> Optional[dict[str, Any]]:
    """Détermine le `premier_ministre` d'un gouvernement, ou None (#398).

    Le critère est le **cumul** de deux faits, jamais l'un des deux seul :
      1. être membre de CE gouvernement — même sélection désambiguïsée que
         `build_gouvernement_roster` (libellé exact + chevauchement) ;
      2. porter un mandat `MINISTERE` de label « Premier ministre »
         chevauchant ce mandat d'appartenance.

    Le seul appariement de période serait insuffisant : deux gouvernements
    successifs se suivent d'un jour, et un même Premier ministre peut en
    diriger deux (Philippe I et II). Passer par le mandat d'appartenance
    hérite de la désambiguïsation déjà éprouvée du roster.

    Retourne None — jamais une valeur déduite du nom du gouvernement — si
    aucun profil ne remplit les deux conditions (cas attendu : le Premier
    ministre n'a pas de profil pivot local), et None **avec un warning** si
    plusieurs les remplissent : trancher entre deux candidats serait un choix
    arbitraire (AGENTS.md §2.5).
    """
    g_debut = _parse_date(periode_debut)
    g_fin = _parse_date(periode_fin)

    candidats: list[dict[str, Any]] = []
    for profil in profils:
        for mandat in profil.get("mandats") or []:
            if not _mandate_matches_gouvernement(mandat, libelle_an, g_debut, g_fin):
                continue
            for portefeuille in _portefeuilles_du_mandat(profil, mandat):
                if (portefeuille.get("label") or "") != LABEL_PORTEFEUILLE_PREMIER_MINISTRE:
                    continue
                candidats.append({
                    "nom": profil.get("nom") or "",
                    "acteur_ref": _acteur_ref_depuis_profil(profil),
                    "source_url": _source_url_portefeuille(portefeuille, mandat),
                })

    # Un même profil peut porter plusieurs mandats d'appartenance au même
    # gouvernement (mandat scindé) : ce sont des doublons, pas une ambiguïté.
    uniques: list[dict[str, Any]] = []
    for candidat in candidats:
        if candidat not in uniques:
            uniques.append(candidat)

    if not uniques:
        return None
    if len(uniques) > 1:
        if warnings is not None:
            noms = sorted(candidat["nom"] for candidat in uniques)
            warnings.append(
                f"gouvernement_roster: {len(uniques)} Premiers ministres possibles "
                f"pour le gouvernement {libelle_an!r} ({', '.join(noms)}) — "
                f"premier_ministre non renseigné."
            )
        return None
    return uniques[0]


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
