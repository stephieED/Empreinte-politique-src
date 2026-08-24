#!/usr/bin/env python3
"""
groupes_config.py — Lecture partagée de `raw_data/groupes_reels.json`, et
**suspension temporaire** de l'extraction d'un groupe configuré (#516).

## Pourquoi une suspension plutôt qu'une suppression

`raw_data/groupes_reels.json` pilote trois choses à la fois : les fetchs de
roster (`generate_roster_candidats.py`), la génération des fiches de groupe
(`generate_group_profiles.py`) et la liste des fichiers attendus par le
quality gate (`check_quality_gate._report_groupes`). Retirer une entrée les
coupe toutes les trois **et** fait disparaître un fichier publié — ce que
`audit_diff_profils` traite, à raison, comme une perte bloquante (#460/#470).

Une suspension coupe la **collecte** sans toucher au **publié** : le fichier
de groupe déjà committé reste en place, servi par l'onglet Groupes, gelé à sa
dernière génération réussie. C'est une position réversible d'une ligne, ce
qu'une suppression n'est pas.

## Le bloc de suspension se documente, sinon il ne vaut rien

    "extraction_suspendue": {
      "depuis": "2026-08-24",
      "motif": "…",
      "references": ["#516", "run 32548486495"],
      "condition_reprise": "…"
    }

Les quatre champs sont **exigés** (`anomalies_suspension`), et le quality gate
en fait une erreur dure. Une suspension sans motif, sans date, sans référence
et sans condition de reprise est un assouplissement silencieux qui devient
permanent par oubli — exactement ce contre quoi #511 a été écrit. La condition
de reprise est le champ qui empêche le « temporaire » de durer : c'est elle
qu'on relit pour savoir si on peut réactiver.

Une valeur fausse (`false`, `null`, absente) = groupe actif. Le groupe n'est
jamais « à moitié » suspendu : la granularité est l'entrée de config entière.
"""

from __future__ import annotations

from typing import Any

#: Clé portant la suspension dans une entrée de `groupes_reels.json`.
#: Nommée `extraction_suspendue` et non `suspendu` : c'est l'**extraction**
#: qui s'arrête, pas le groupe parlementaire — et `suspendu` est déjà pris,
#: dans un tout autre sens, par `mandats[].suspendu_pour_fonction_gouvernementale`
#: (AGENTS.md §5).
CLE_SUSPENSION = "extraction_suspendue"

#: Les quatre champs qui font d'une suspension une décision documentée.
CHAMPS_SUSPENSION_REQUIS: tuple[str, ...] = (
    "depuis",
    "motif",
    "references",
    "condition_reprise",
)


def libelle_groupe(groupe: dict[str, Any]) -> str:
    """Nom d'un groupe dans les messages, stable et sans ambiguïté.

    `groupe_id` distingue les deux `LR` (`AN:LR` et `Senat:LR`), ce que le seul
    sigle ne ferait pas. Repli sur `<chambre>:<sigle>` pour une config plus
    ancienne, `?` en dernier recours (un libellé n'est jamais un motif d'échec :
    l'anomalie qu'il nomme, elle, l'est).
    """
    if groupe.get("groupe_id"):
        return str(groupe["groupe_id"])
    return f"{groupe.get('chambre') or '?'}:{groupe.get('groupe_sigle') or '?'}"


def est_suspendu(groupe: dict[str, Any]) -> bool:
    """`True` si l'extraction de ce groupe est suspendue (#516)."""
    return bool(groupe.get(CLE_SUSPENSION))


def partitionner_groupes(
    groupes: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Sépare `(groupes actifs, groupes suspendus)`, dans l'ordre de la config."""
    actifs = [groupe for groupe in groupes if not est_suspendu(groupe)]
    suspendus = [groupe for groupe in groupes if est_suspendu(groupe)]
    return actifs, suspendus


def anomalies_suspension(groupe: dict[str, Any]) -> list[str]:
    """Les raisons pour lesquelles une suspension n'est pas documentée.

    Liste vide = suspension en règle, ou groupe actif. Fonction pure.
    """
    if not est_suspendu(groupe):
        return []

    libelle = libelle_groupe(groupe)
    bloc = groupe.get(CLE_SUSPENSION)
    if not isinstance(bloc, dict):
        return [
            f"{libelle} : '{CLE_SUSPENSION}' doit être un objet documenté "
            f"({', '.join(CHAMPS_SUSPENSION_REQUIS)}), pas {type(bloc).__name__}."
        ]

    manquants = [champ for champ in CHAMPS_SUSPENSION_REQUIS if not bloc.get(champ)]
    if manquants:
        return [
            f"{libelle} : suspension d'extraction non documentée — "
            f"champ(s) manquant(s) : {', '.join(manquants)}. Une suspension sans "
            "motif ni condition de reprise devient permanente par oubli (#516)."
        ]
    return []


def resume_suspension(groupe: dict[str, Any]) -> str:
    """Une ligne lisible en log : libellé, motif, date, références."""
    bloc = groupe.get(CLE_SUSPENSION)
    if not isinstance(bloc, dict):
        return f"{libelle_groupe(groupe)} : extraction suspendue (non documentée)"

    references = bloc.get("references") or []
    if isinstance(references, str):
        references = [references]
    suffixe = f" [{', '.join(str(r) for r in references)}]" if references else ""
    return (
        f"{libelle_groupe(groupe)} : extraction suspendue depuis "
        f"{bloc.get('depuis') or '?'} — {bloc.get('motif') or '?'}{suffixe}"
    )
