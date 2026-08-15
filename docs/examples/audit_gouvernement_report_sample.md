# Rapport d'audit du jeu de données gouvernements

Généré le 2026-08-15T22:03:03.566100+00:00. 3 gouvernement(s) analysé(s), 1 erreur(s) de lecture. Seuil de péremption des sources : 30 jour(s).

Ce rapport est un outil de qualité interne : il présente des indicateurs bruts, sans jugement de valeur ni classement.

## Volumétrie

### Répartition par `periode.actif`

| Total | Actifs | Inactifs | Indéterminés |
| --- | --- | --- | --- |
| 3 | 2 | 1 | 0 |

### Distribution du nombre de `membres` / `textes` par gouvernement

| Champ | Min | Max | Médiane | Moyenne |
| --- | --- | --- | --- | --- |
| membres | 0 | 2 | 1 | 1 |
| textes | 0 | 1 | 1 | 0.67 |

### Comptages agrégés par statut de texte (`comptages.par_statut`)

| Statut | Total |
| --- | --- |
| adopte | 0 |
| adopte_49_3 | 1 |
| depose | 0 |
| navette_en_cours | 0 |
| rejete | 0 |
| rejete_49_3 | 1 |
| retire | 0 |

## Tableau croisé des plages temporelles par gouvernement

Pour chaque gouvernement, la période couverte par les dates disponibles (min → max) des mandats de ses membres et des textes qu'il a portés.

| gouvernement_id | Nom | Mandats membres (min → max) | Textes (min → max) |
| --- | --- | --- | --- |
| gouvernement:BARNIER | Gouvernement Barnier | 2024-09-05 → 2024-12-05 | 2024-11-01 → 2024-12-04 |
| gouvernement:LECORNU | Gouvernement Lecornu | 2025-09-09 → 2025-09-09 | 2024-10-10 → 2024-12-04 |
| gouvernement:LECORNU | Gouvernement Lecornu (bis, doublon volontaire) | N/D | N/D |

> **`mandats_membres`** : calculée sur `membres[].debut`/`.fin`. Un `fin = null` signale un mandat en cours — exclu du calcul sans jamais être remplacé par la date du jour (AGENTS.md §2.5).

### Dates `membres[]`/`textes[]` invalides ignorées pour le calcul (0)

Aucune date invalide détectée.

## Complétude

### Présence d'un `premier_ministre` renseigné

| Renseignés | Total | Taux (%) |
| --- | --- | --- |
| 1 | 3 | 33.33 |

### Taux de `membres[].portefeuille` renseigné

| Renseignés | Total | Taux (%) |
| --- | --- | --- |
| 1 | 3 | 33.33 |

### Présence d'un bloc `meta` renseigné

| Renseignés | Total | Taux (%) |
| --- | --- | --- |
| 3 | 3 | 100.0 |

## Cohérence

### Validation du schéma (`validate_profil_gouvernement`)

Aucun gouvernement invalide détecté.

### Divergence `schema_version` / `meta.schema_version`

Aucune divergence détectée.

### Doublons de `gouvernement_id`

| gouvernement_id | Occurrences |
| --- | --- |
| gouvernement:LECORNU | 2 |

## Fraîcheur

### Ancienneté des sources par type (jours écoulés depuis `synchro_le`)

| Type de source | Nombre de sources | Min | Max | Médiane | Moyenne |
| --- | --- | --- | --- | --- | --- |
| assemblee_nationale | 2 | 14 | 591 | 302.5 | 302.5 |

### Gouvernements périmés (toutes sources > 30 jours)

| gouvernement_id |
| --- |
| gouvernement:BARNIER |

## Warnings

Total : 1

| Type | Fréquence | Gouvernements concernés |
| --- | --- | --- |
| couverture_ministerielle | 1 | gouvernement:BARNIER |

## Erreurs de lecture

| Fichier | Erreur |
| --- | --- |
| tests/fixtures/audit_gouvernement/gouvernement-INVALIDE.json | Expecting property name enclosed in double quotes: line 1 column 2 (char 1) |
