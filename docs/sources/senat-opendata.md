# `data.senat.fr` — open data du Sénat

> **Statut : sondée, pas encore collectée.** Mesurée le **13/09/2026** pour remplir la
> condition 1 du §7 de [`retrait-senat-528`](../decisions/retrait-senat-528.md) — « une source
> est établie, pas supposée ». La décision de réouverture partielle est
> [`reouverture-partielle-senat-885`](../decisions/reouverture-partielle-senat-885.md) ; aucun
> collecteur n'interroge ce domaine à ce jour. Ce fichier décrit ce que le **fournisseur**
> publie, et dérive avec lui, non avec notre code.

## Producteur et licence

Producteur **Sénat**. **Licence Ouverte** — `fr-lo` dans l'API `data.gouv.fr`, « Licence Ouverte
2.0 (Etalab) » sur `data.senat.fr/licence/`. Attribution seule, réutilisation commerciale
autorisée, **pas de partage à l'identique**. Même famille que
`data.assemblee-nationale.fr` ; plus permissive que l'ODbL de Regards Citoyens. L'étiquette
canonique devra vivre dans `src/licences.py`, jamais en dur (AGENTS.md §7).

## Deux formes, et la distinction est le piège

Le jeu « Les Sénateurs » est référencé sur `data.gouv.fr` par **55 ressources**.

| Forme | URL | Ce qu'elle porte |
| --- | --- | --- |
| extraits | `https://data.senat.fr/data/senateurs/ODSEN_<NOM>.csv` (aussi `.json`, `.xls`) | l'appartenance **courante** pour les groupes politiques ; l'historique pour les commissions, délégations, groupes d'études et d'amitié |
| export complet | `https://data.senat.fr/data/senateurs/export_sens.zip` | 8,3 Mo → **58 Mo** de `export_sens.sql` (PostgreSQL) — **l'historique daté des groupes politiques, et lui seul** |

**Lire les seuls extraits conduit à conclure que l'historique des groupes n'existe pas.** C'est
l'erreur commise puis corrigée le 13/09/2026 : `ODSEN_GENERAL.csv` ne porte qu'une colonne
« Groupe politique », celle de la fin du mandat.

## Extraits utiles (volumétrie du 13/09/2026)

| Fichier | Lignes | Contenu |
| --- | ---: | --- |
| `ODSEN_GENERAL` | une par sénateur·rice | état civil, `État` (`ACTIF` / `ANCIEN`), groupe **courant**, commission permanente, circonscription, fonction au Bureau, PCS INSEE |
| `ODSEN_ELUSEN` | 3 348 | mandats sénatoriaux : date d'élection, début, **motif de début**, fin, **motif de fin** |
| `ODSEN_ELUDEP` | — | mandats de **député** des sénateur·rices |
| `ODSEN_COMS` | 17 678 | commissions et missions, datées, **avec la fonction datée à part de l'appartenance** |
| `ODSEN_ETUDES` | 9 818 | groupes d'études, avec commission de rattachement et sections |
| `ODSEN_GIA` | 27 747 | groupes interparlementaires d'amitié |
| `ODSEN_MEMOEP` | 4 551 | organismes extra-parlementaires, datés, avec **titulaire/suppléant** et **mode de désignation** |
| `ODSEN_OEP` | — | le référentiel des organismes extra-parlementaires |

Encodage des CSV : **latin-1**. Les fichiers commencent par des lignes `%` qui reproduisent la
requête SQL de l'extraction — utiles pour lire les jointures, à sauter au parsing.

## Tables de l'export à connaître

| Table | Lignes | Ce qu'elle porte |
| --- | ---: | --- |
| `elusen` | 3 555 | mandats sénatoriaux |
| `memcom` | 17 042 | appartenances aux commissions |
| `memgrppol` | 3 213 | appartenances aux **groupes politiques**, datées, avec `typapppolcod` — membre, apparenté, **rattaché** |
| `libgrppol` | **49** | **les libellés de groupe, bornés par `libgrppoldatdeb` / `libgrppoldatfin`** — `evelic` sigle, `evelib` libellé court, `evelil` libellé long |
| `grppol` | 28 | les groupes |
| `memgrpsen` | 30 540 | groupes d'études, d'amitié et **de liaison** |
| `libgrpsen` | 115 | leurs libellés, bornés de même |
| `grpsenami` | 171 | le référentiel de ces groupes, avec `typgrpsencod` (`LIAISON`, …) |
| `memextpar` | — | organismes extra-parlementaires |
| `activite` | 42 601 | séances et réunions, avec une colonne **`scrid`** |
| `activite_senateur` | **11 069** | **participation nominative — interdite à la publication (§2 règle 3)** |

## Ce que ce jeu ne porte pas

- **Les scrutins.** `activite.scrid` référence un identifiant de scrutin, mais **aucune table de
  scrutins n'est dans ce jeu**. Aucun `cohesion_votes` sénatorial n'en sortira, et c'est ce qui
  laisse la condition 2 du §7 de #528 non remplie.
- **Les comptes rendus des débats.** `data.senat.fr` les annonce dans une **autre** catégorie que
  « Les Sénateurs ». **Non sondée** au 13/09/2026 : à instruire, pas à supposer.

## Le piège éditorial que cette source résout

Le référentiel de l'Assemblée (`AMO30`, voir [`an-opendata.md`](an-opendata.md)) ne porte **qu'un
libellé par organe sénatorial — l'actuel** : `PO286005` publie « Les Républicains » depuis le
11/12/2002 avec `libelleAbrev = UMPPO`, `PO211490` publie « Commission de la culture, de
l'éducation, de la communication **et du sport** » depuis le 31/12/1899 avec
`libelleAbrev = AFCLC`. **19 organes sénatoriaux pour 63 ans**, contre 63 organes de groupe pour
l'Assemblée, un par législature. Le Sénat, lui, publie la table de renommage : la jointure
`memgrppol` × `libgrppol` sur la période qui se chevauche rend le nom **à la date du mandat**.
Le détail et les vérifications externes sont dans
[`reouverture-partielle-senat-885`](../decisions/reouverture-partielle-senat-885.md) §3a.

## Ce qui n'est pas interrogé, et ne le sera pas

`archive.nossenateurs.fr` reste **morte pour le produit** (#528 §7, dernier paragraphe) : sa
joignabilité ne change rien. Les refus bruyants de #528 §8 portent sur la chambre `senateurs`
comme **source de collecte**, et c'est cette porte que #885 ouvre — sur `data.senat.fr`, jamais
sur NosSénateurs.
