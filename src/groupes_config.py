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

import json
from pathlib import Path
from typing import Any, Optional

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


#: Fichier de configuration des groupes. Il vit ICI depuis #558, et non plus
#: dans `an_roster` : ce module est celui qui dit ce que `groupes_reels.json`
#: pilote, et trois consommateurs le lisent sans avoir la moindre raison de
#: dépendre du dérivateur de roster AN. `an_roster` le réexporte pour ses
#: propres appelants.
CHEMIN_CONFIG_GROUPES = Path("raw_data") / "groupes_reels.json"

#: Répertoire des fiches de groupe publiées.
GROUPES_PUBLIES_DIR = Path("pivot_data") / "groupes"


def index_membres_de_groupes_suspendus(
    groupes: list[dict[str, Any]],
    groupes_dir: Optional[Path] = None,
) -> dict[str, dict[str, Any]]:
    """`membre_id` → entrée de config du groupe **suspendu** qui l'explique.

    ## Pourquoi la fiche publiée, et pas le roster

    Un groupe suspendu n'est plus interrogé : `generate_roster_candidats.py` ne
    construit même pas sa clé de fetch (#516). Sa composition n'existe donc plus
    nulle part **sauf** dans la fiche déjà publiée et gelée,
    `pivot_data/groupes/<fichier>` — qui est précisément la source sur laquelle
    #558 a mesuré sa population. Lire ailleurs reviendrait à ne rien lire.

    ## Pourquoi pas la provenance, et pourquoi pas `chambre`

    Deux pièges, tous deux mesurés le 29/08/2026 sur les 481 profils publiés :

    1. **`chambre` ne dit pas la chambre.** Les 20 membres des deux fiches
       `groupe-Senat-*` publient `chambre: "AN"` (défaut distinct, tenu par
       #486). Compter les sénateurs par ce champ en rend **zéro**, et fait
       conclure que la population a disparu.
    2. **La provenance ne recouvre pas la population.** 19 des 20 sont
       `roster_groupe` ; le vingtième est `bruno-retailleau`, de provenance
       `candidat_declare` — et c'est le plus visible des vingt. Un correctif
       branché sur la provenance seule l'aurait manqué.

    L'appartenance, elle, se lit sans ambiguïté et pour les vingt.

    Une fiche absente ou illisible ne lève pas : un groupe suspendu dont la
    fiche a disparu ne rend simplement aucun membre, et les profils concernés
    retombent sur la dérivation générale. Ce module n'est pas le garde-fou du
    fichier publié — `audit_diff_profils` l'est déjà (#460/#470).
    """
    racine = Path(groupes_dir) if groupes_dir is not None else GROUPES_PUBLIES_DIR
    index: dict[str, dict[str, Any]] = {}
    for groupe in groupes:
        if not est_suspendu(groupe):
            continue
        fichier = groupe.get("fichier")
        if not fichier:
            continue
        chemin = racine / str(fichier)
        try:
            fiche = json.loads(chemin.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, ValueError):
            continue
        if not isinstance(fiche, dict):
            continue
        for membre in fiche.get("membres") or ():
            if not isinstance(membre, dict):
                continue
            membre_id = membre.get("membre_id")
            if isinstance(membre_id, str) and membre_id:
                index.setdefault(membre_id, groupe)
    return index


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
