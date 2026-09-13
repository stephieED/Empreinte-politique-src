#!/usr/bin/env python3
"""
senat_opendata.py — Lire l'open data du Sénat sans base de données (#885).

La source, et pourquoi elle
---------------------------
`data.senat.fr`, producteur **Sénat**, sous **Licence Ouverte** — attribution
seule, pas de partage à l'identique. Elle rentre dans le périmètre pour les
**appartenances**, pas pour l'activité en séance : le jeu ne porte ni scrutins
ni comptes rendus, et la condition 2 du §7 de #528 est **déclarée non remplie**,
pas contournée. Voir `docs/decisions/reouverture-partielle-senat-885.md`.

Elle publie deux formes, et la différence a coûté deux allers-retours :

  - les **extraits** `ODSEN_*.csv` ne portent, pour les groupes politiques, que
    l'appartenance **courante** ;
  - l'**export PostgreSQL** `export_sens.zip` porte l'**historique daté**, et
    lui seul. Lire les seuls extraits mène à conclure que l'historique n'existe
    pas. Il existe.

Ce module lit l'export **sans PostgreSQL** : un dump `pg_dump` au format texte
range chaque table dans un bloc `COPY … FROM stdin;` qui est du TSV, terminé par
`\\.`. Monter une base pour lire du TSV coûterait une dépendance de service à
un pipeline qui n'en a aucune.

Ce que ce module refuse, et pourquoi il le refuse
-------------------------------------------------
**Un export vide n'est pas un corpus vide.** Mesuré le 13/09/2026 : l'archive
publiée à 03 h 33 faisait **444 octets** et ne contenait **aucune table** —
en-tête PostgreSQL et quatre `GRANT`. HTTP 200, `Content-Type: application/zip`,
donc rien qu'un code de retour ne signale. Republiée saine à 12 h 42, 93 tables.
Une régénération quotidienne ratée, transitoire.

Un collecteur qui aurait tourné entre les deux aurait vidé les fiches
sénatoriales **en silence** : la fusion additive protège le pivot, pas le brut,
et §2 règle 5 interdit de lire une absence comme un constat. D'où
`ExportSenatVide`, levée à la lecture — même geste que
`generate_roster_candidats.py`, qui refuse d'écrire sur un roster vide (§3c).

Les dates, et les trois formes qu'elles prennent
------------------------------------------------
1. `\\N` — absent. Rendu `None`, jamais une date de repli (§2 règle 5).
   **1 064 appartenances de groupe sur 3 213 n'ont pas de date de début**, soit
   un tiers : ce n'est pas un cas rare à traiter en passant.
2. Un horodatage `YYYY-MM-DD HH:MM:SS` — seule la date est publiable, l'heure
   d'un mandat ne veut rien dire.
3. Une **sentinelle** `1899-12-31` / `1900-01-01`, souvent assortie de l'heure
   `00:50:39` — c'est « depuis toujours », pas une date. **23 des 49 libellés de
   groupe en portent une.** Publiée telle quelle, elle ferait commencer un
   groupe politique au XIXe siècle.

Usage :
    from senat_opendata import charger_export, DUMP_TABLES_UTILES
    tables = charger_export(Path("export_sens.sql"))
    for ligne in tables["memgrppol"]:
        ...
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable, Iterator, Optional

#: L'URL de l'export. Citée ici parce que c'est le module qui la consomme ;
#: `docs/sources/senat-opendata.md` en porte le contexte et la licence.
URL_EXPORT = "https://data.senat.fr/data/senateurs/export_sens.zip"

#: Les tables que ce produit lit, et rien d'autre. Le dump en porte **93** :
#: les charger toutes coûterait 58 Mo en mémoire pour en utiliser huit.
#:
#: `activite_senateur` en est **délibérément absente** (§2 règle 3) — voir
#: `TABLES_REFUSEES`.
DUMP_TABLES_UTILES: frozenset[str] = frozenset({
    "sen",          # le sénateur : matricule, état civil
    "elusen",       # les mandats, avec motif de début et de fin
    "memgrppol",    # appartenance à un groupe politique, datée, avec son type
    "libgrppol",    # les libellés de groupe, BORNÉS — le nom à la date
    "grppol",       # les groupes eux-mêmes
    "typapppol",    # N = membre, R = rattaché, A = apparenté
    "memcom",       # commissions et missions, datées
    "libcom",       # leurs libellés, bornés — même mécanique que libgrppol
    "com",          # les commissions elles-mêmes
    "memgrpsen",    # groupes d'études, d'amitié, de liaison
    "libgrpsen",    # leurs libellés, bornés de la même façon
    "grpsenami",    # les groupes sénatoriaux, et leur type
    "typgrpsen",    # AMITIE, INFO, ETUDES, LIAISON
    "fonmemgrppol", # fonction tenue dans un groupe politique, datée
    "fonmemcom",    # fonction tenue en commission, datée
    "fonmemgrpsen", # fonction tenue dans un groupe sénatorial, datée
    "fongrppol",    # les libellés de ces fonctions
    "foncom",
    "fongrpsen",
})

#: Ce que la collecte refuse **à l'entrée**, et la raison.
#:
#: `activite_senateur` porte **11 069 lignes de participation nominative** —
#: un taux de présence individuel, que §2 règle 3 interdit de publier. Le refus
#: est ici, à la lecture, et non à l'affichage : un filtre à l'affichage
#: laisserait la donnée dans `raw_data/`, où la fusion additive la garderait
#: indéfiniment (#729). Une donnée qu'on ne publiera jamais ne se collecte pas.
TABLES_REFUSEES: dict[str, str] = {
    "activite_senateur": (
        "participation nominative en séance : un taux de présence individuel, "
        "que AGENTS.md §2 règle 3 interdit de publier. Refusée à l'entrée de la "
        "collecte, jamais filtrée à l'affichage (#729)."
    ),
}

#: Dates que la source emploie pour dire « depuis toujours ». Ce ne sont pas des
#: dates : les publier ferait commencer un groupe en 1899.
SENTINELLES_DATE: frozenset[str] = frozenset({"1899-12-31", "1900-01-01"})

_DEBUT_COPY = re.compile(r"^COPY (?P<table>[a-z_]+) \((?P<colonnes>[^)]*)\) FROM stdin;")

#: Une date sans son heure. Le dump écrit `2015-06-02 00:00:00`, et l'heure d'un
#: mandat ne veut rien dire — sauf celle des sentinelles, qui la trahit.
_DATE = re.compile(r"^(\d{4}-\d{2}-\d{2})")


class ExportSenatVide(RuntimeError):
    """L'export est lisible mais ne porte aucune des tables attendues.

    Distincte d'une erreur de lecture : le fichier est un dump valide, il est
    simplement vide. C'est l'état publié le 13/09/2026 à 03 h 33, et le seul
    que ni le code HTTP ni le type MIME ne signalent.
    """


def date_publiable(valeur: Optional[str]) -> Optional[str]:
    """Rend `YYYY-MM-DD`, ou `None` — jamais une date inventée.

    Trois entrées, trois sorties :

      - `None` ou vide → `None` (§2 règle 5 : une absence se publie absente) ;
      - une sentinelle → `None`, parce que « depuis toujours » n'est pas une
        date et qu'une borne fausse est pire qu'une borne absente ;
      - un horodatage → sa seule date.

    Une valeur qui ne ressemble à aucune des trois rend `None` plutôt que de
    lever : ce module lit une source tierce, et une forme inattendue est une
    donnée manquante, pas une panne du pipeline.
    """
    if not valeur:
        return None
    trouve = _DATE.match(valeur.strip())
    if not trouve:
        return None
    date = trouve.group(1)
    return None if date in SENTINELLES_DATE else date


def periodes_se_recouvrent(
    debut_a: Optional[str], fin_a: Optional[str],
    debut_b: Optional[str], fin_b: Optional[str],
) -> bool:
    """Deux périodes datées se recouvrent-elles, au moins d'un jour ?

    C'est la jointure qui donne **le nom d'un organe à la date du mandat** — ce
    que le référentiel de l'Assemblée ne sait pas faire, et ce qui a fait
    échouer #878.

    Une borne absente est **ouverte**, jamais zéro : une fin inconnue se lit
    « toujours en cours », un début inconnu « depuis toujours ». C'est le seul
    endroit de ce module où une absence reçoit une valeur, et elle ne sort pas
    d'ici — elle sert à comparer, jamais à publier (§2 règle 5).
    """
    debut_a = debut_a or "0000-01-01"
    debut_b = debut_b or "0000-01-01"
    fin_a = fin_a or "9999-12-31"
    fin_b = fin_b or "9999-12-31"
    return debut_a <= fin_b and debut_b <= fin_a


def _lignes_du_bloc(flux: Iterator[str], colonnes: list[str]) -> Iterator[dict[str, Any]]:
    """Les lignes TSV d'un bloc `COPY`, jusqu'au `\\.` qui le ferme."""
    for ligne in flux:
        if ligne.startswith("\\."):
            return
        champs = ligne.rstrip("\n").split("\t")
        yield {colonne: (None if valeur == "\\N" else valeur)
               for colonne, valeur in zip(colonnes, champs)}


def lire_tables(
    chemin: Path,
    tables: Iterable[str] = DUMP_TABLES_UTILES,
) -> dict[str, list[dict[str, Any]]]:
    """Les tables demandées, lues en un seul passage du dump.

    Un `pg_dump` texte est séquentiel : relire le fichier par table coûterait
    58 Mo de lecture par table. Les blocs non demandés sont **traversés sans
    être matérialisés** — c'est ce qui borne la mémoire, et c'est aussi ce qui
    rend `TABLES_REFUSEES` effectif : leurs lignes ne sont jamais construites.

    Lève `ExportSenatVide` si aucune table demandée n'a été trouvée.
    """
    voulues = set(tables) - set(TABLES_REFUSEES)
    trouvees: dict[str, list[dict[str, Any]]] = {}
    with chemin.open(encoding="utf-8", errors="replace") as flux:
        for ligne in flux:
            entete = _DEBUT_COPY.match(ligne)
            if not entete:
                continue
            table = entete.group("table")
            if table not in voulues:
                # Traversé, jamais construit : c'est ici que les 11 069 lignes
                # d'`activite_senateur` cessent d'exister pour ce produit.
                for _ in flux:
                    if _.startswith("\\."):
                        break
                continue
            colonnes = [c.strip() for c in entete.group("colonnes").split(",")]
            trouvees[table] = list(_lignes_du_bloc(flux, colonnes))
    if not trouvees:
        raise ExportSenatVide(
            f"{chemin} ne porte aucune des tables attendues "
            f"({', '.join(sorted(voulues))}). L'export publié par data.senat.fr "
            "a déjà été servi vide — 444 octets, 0 table, le 13/09/2026 à "
            "03 h 33, avec un HTTP 200 et un type MIME correct. Un run qui "
            "poursuivrait viderait les fiches sénatoriales en silence."
        )
    return trouvees


def tables_manquantes(tables: dict[str, list[dict[str, Any]]]) -> list[str]:
    """Celles qui étaient attendues et que l'export n'a pas rendues.

    Rendu **déclaré**, jamais levé : une table absente d'un export par ailleurs
    valide est une information sur la source, et l'appelant décide si elle lui
    est vitale. Une table **vide** compte comme présente — zéro ligne est une
    mesure, l'absence de la table n'en est pas une (§2 règle 5).
    """
    return sorted(DUMP_TABLES_UTILES - set(TABLES_REFUSEES) - set(tables))
