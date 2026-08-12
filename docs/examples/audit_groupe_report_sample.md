> Exemple statique généré sur `tests/fixtures/audit_groupe` (3 profils de groupe,
> dont un doublon volontaire de `groupe_id`, + 1 fichier corrompu) avec une date
> de référence fixée au 2026-08-09, pour que ce document reste reproductible. La
> commande CLI réelle (`python src/audit_groupe_dataset.py --input-dir
> tests/fixtures/audit_groupe --output-json ... --output-md ...`) utilise l'heure
> courante : `meta.genere_le` et les anciennetés de fraîcheur (calculées à partir
> de `synchro_le`) diffèrent alors d'une exécution à l'autre sur ces fixtures.

# Rapport d'audit du jeu de données groupes

Généré le 2026-08-09T00:00:00+00:00. 3 groupe(s) analysé(s), 1 erreur(s) de lecture. Seuil de péremption des sources : 30 jour(s).

Ce rapport est un outil de qualité interne : il présente des indicateurs bruts, sans jugement de valeur ni classement.

## Volumétrie

### Effectifs (`effectif.actuel` / `min_historique` / `max_historique`)

| Champ | Groupes renseignés | Min | Max | Médiane | Moyenne |
| --- | --- | --- | --- | --- | --- |
| actuel | 3 | 1 | 2 | 1 | 1.33 |
| min_historique | 1 | 2 | 2 | 2 | 2 |
| max_historique | 1 | 3 | 3 | 3 | 3 |

### Cohésion de vote (nombre de scrutins recensés par groupe)

| Min | Max | Médiane | Moyenne | % groupes à 0 |
| --- | --- | --- | --- | --- |
| 0 | 2 | 0 | 0.67 | 66.67 |

### Amendements agrégés (tous types de déposants confondus)

| Compteur | Min | Max | Médiane | Moyenne |
| --- | --- | --- | --- | --- |
| nb_amendements | 0 | 10 | 0 | 3.33 |
| nb_adoptes | 0 | 2 | 0 | 0.67 |
| nb_rejetes | 0 | 6 | 0 | 2 |
| nb_irrecevables | 0 | 1 | 0 | 0.33 |
| nb_retires_ou_tombes | 0 | 1 | 0 | 0.33 |

### Amendements agrégés par type de déposant

#### commission_rapporteur

| Compteur | Min | Max | Médiane | Moyenne |
| --- | --- | --- | --- | --- |
| nb_amendements | 0 | 1 | 0 | 0.33 |
| nb_adoptes | 0 | 0 | 0 | 0 |
| nb_rejetes | 0 | 0 | 0 | 0 |
| nb_irrecevables | 0 | 0 | 0 | 0 |
| nb_retires_ou_tombes | 0 | 1 | 0 | 0.33 |

#### depute

| Compteur | Min | Max | Médiane | Moyenne |
| --- | --- | --- | --- | --- |
| nb_amendements | 0 | 8 | 0 | 2.67 |
| nb_adoptes | 0 | 1 | 0 | 0.33 |
| nb_rejetes | 0 | 6 | 0 | 2 |
| nb_irrecevables | 0 | 1 | 0 | 0.33 |
| nb_retires_ou_tombes | 0 | 0 | 0 | 0 |

#### gouvernement

| Compteur | Min | Max | Médiane | Moyenne |
| --- | --- | --- | --- | --- |
| nb_amendements | 0 | 1 | 0 | 0.33 |
| nb_adoptes | 0 | 1 | 0 | 0.33 |
| nb_rejetes | 0 | 0 | 0 | 0 |
| nb_irrecevables | 0 | 0 | 0 | 0 |
| nb_retires_ou_tombes | 0 | 0 | 0 | 0 |

#### inconnu

| Compteur | Min | Max | Médiane | Moyenne |
| --- | --- | --- | --- | --- |
| nb_amendements | 0 | 0 | 0 | 0 |
| nb_adoptes | 0 | 0 | 0 | 0 |
| nb_rejetes | 0 | 0 | 0 | 0 |
| nb_irrecevables | 0 | 0 | 0 | 0 |
| nb_retires_ou_tombes | 0 | 0 | 0 | 0 |

## Tableau croisé des volumes par groupe

| groupe_id | Nom | Chambre | Membres | Cohésion de vote | Tags thématiques | Amendements |
| --- | --- | --- | --- | --- | --- | --- |
| AN:LFI | La France insoumise | AN | 2 | 2 | 2 | 10 |
| AN:LFI | La France insoumise (doublon) | AN | 1 | 0 | 0 | 0 |
| Senat:SOC | Socialiste, Ecologiste et Republicain | Senat | 1 | 0 | 0 | 0 |

## Complétude

### Présence des tags thématiques agrégés

| Renseignés | Total | Taux (%) |
| --- | --- | --- |
| 1 | 3 | 33.33 |

### Groupes avec des membres mais sans `cohesion_votes`

2 / 3 groupe(s).

## Cohérence

### Validation du schéma (`validate_profil_groupe`)

Aucun groupe invalide détecté.

### Divergence `schema_version` / `meta.schema_version`

Aucune divergence détectée.

### Écart de couverture du roster

| groupe_id | Roster total | Profils disponibles | Écart | Taux de couverture (%) |
| --- | --- | --- | --- | --- |
| AN:LFI | 5 | 2 | 3 | 40.0 |

### Doublons de `groupe_id`

| groupe_id | Occurrences |
| --- | --- |
| AN:LFI | 2 |

## Fraîcheur

### Ancienneté des sources par type (jours écoulés depuis `synchro_le`)

| Type de source | Nombre de sources | Min | Max | Médiane | Moyenne |
| --- | --- | --- | --- | --- | --- |
| nosdeputes | 2 | 7 | 38 | 22.5 | 22.5 |

### Groupes périmés (toutes sources > 30 jours)

| groupe_id |
| --- |
| AN:LFI |

## Warnings

Total : 1

| Type | Fréquence | Groupes concernés |
| --- | --- | --- |
| couverture_roster | 1 | AN:LFI |

## Erreurs de lecture

| Fichier | Erreur |
| --- | --- |
| tests/fixtures/audit_groupe/invalide.json | Expecting property name enclosed in double quotes: line 1 column 2 (char 1) |

