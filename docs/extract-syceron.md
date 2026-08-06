# extract-syceron

## Statut

Exploration Phase 0 uniquement : ce document décrit la structure XML du ZIP
Syceron de l'Assemblée nationale, pour préparer une intégration ultérieure.
Aucun extracteur `src/` dédié n'est ajouté à ce stade.

Archive inspectée :

- `https://data.assemblee-nationale.fr/static/openData/repository/17/vp/syceronbrut/syseron.xml.zip`
- ZIP disponible au 2026-08-06, ~55 Mo, 601 fichiers XML `xml/compteRendu/*.xml`

Exemple observé :

- `xml/compteRendu/CRSANR5L17S2025O1N037.xml`
- racine namespacée : `<compteRendu xmlns="http://schemas.assemblee-nationale.fr/referentiel">`

---

## Structure générale

Chaque fichier correspond à une séance et contient cinq blocs racine :

```xml
<compteRendu>
  <uid>...</uid>
  <seanceRef>...</seanceRef>
  <sessionRef>...</sessionRef>
  <metadonnees>...</metadonnees>
  <contenu>...</contenu>
</compteRendu>
```

### 1. Métadonnées de séance

Champs vus dans l'échantillon :

| Balise | Exemple | Usage probable |
|---|---|---|
| `dateSeance` | `20241106140000000` | date/heure source à normaliser |
| `dateSeanceJour` | `mercredi 06 novembre 2024` | libellé humain |
| `numSeanceJour` | `1` | rang dans la journée |
| `numSeance` | `37` | identifiant de séance |
| `typeAssemblee` | `AN` | chambre |
| `legislature` | `17` | législature |
| `session` | `Session ordinaire 2024-2025` | libellé de session |
| `nomFichierJo` | `20240037` | référence JO |
| `validite` | `valide` | statut documentaire |
| `etat` | `complet` | complétude |
| `diffusion` | `public` | diffusion |
| `version` | `avant_JO` | version éditoriale |
| `environnement` | `PROD` | environnement |
| `heureGeneration` | `2024-11-14T13:15:20.000+01:00` | horodatage de génération |

Autres balises observées dans `contenu` : `ouvertureSeance`, `finSeance`,
`presidentSeance`.

### 2. Contenu structuré

Le bloc `contenu` est organisé autour de nœuds `point`, plus quelques balises
de cadrage (`quantiemes`, `journee`, `session`).

Balises rencontrées le plus souvent sur 10 fichiers inspectés :

- `point`
- `titreStruct` → `intitule`, `sousIntitule`
- `orateurs` → `orateur` → `nom`, `id`, `qualite`
- `texte` (avec attribut possible `stime`)
- `paragraphe`
- `interExtraction`
- `lienAdt`
- `italique`, `exposant`, `br`, `sup`

Exemples réels observés :

```xml
<titreStruct id_syceron="3555179">
  <intitule>Questions au Gouvernement</intitule>
  <sousIntitule>0</sousIntitule>
</titreStruct>
```

```xml
<orateur>
  <nom>M. Jean-Louis Thiériot</nom>
  <id>643089</id>
  <qualite>ministre délégué auprès du ministre des armées et des anciens combattants</qualite>
</orateur>
```

```xml
<paragraphe
  ordre_absolu_seance="2"
  id_acteur="PA721908"
  id_mandat="PM843467"
  code_grammaire="OUV_SEAN_2_1"
  code_style="NORMAL"
  roledebat="president"
  id_syceron="3555176">
  ...
</paragraphe>
```

```xml
<interExtraction
  nom_orateur="Mme Sabrina Sebaihi"
  id_acteur="PA795808"
  id_mandat="PM843644" />
```

---

## Ce que l'échantillon montre — et ne montre pas

### Disponible directement

- une **séance** identifiable (`uid`, `seanceRef`, `numSeance`, `legislature`)
- une **date** de séance (`dateSeance`)
- un **orateur** (`orateur.nom`, `orateur.id`, `qualite`, `id_acteur`)
- le **texte** de la prise de parole (`paragraphe` + `texte`)
- un **contexte de débat** approximatif via `titreStruct.intitule`
- des repères procéduraux via `code_grammaire`, `code_style`, `art`, `adt`,
  `ordre_absolu_seance`, `valeur_ptsodj`

### Non disponible directement

- pas de balise explicite `theme`
- pas de balise explicite `dossier`
- pas de rôle factuel de type `auteur` / `rapporteur` sur un texte
- pas de ministère interrogé structuré pour les QG

Conclusion : Syceron est une bonne source pour **interventions de séance**,
mais pas une source autonome suffisante pour fabriquer des `textes_portes[]`.

---

## Mapping proposé vers le pipeline

### A. `interventions[]` (oui, source prioritaire potentielle pour les débats)

| Syceron | Pivot actuel | Règle proposée |
|---|---|---|
| `metadonnees.dateSeance` | `date` | normaliser en `YYYY-MM-DD` |
| `titreStruct.intitule` le plus proche | `sujet` | utiliser comme contexte courant du point |
| `paragraphe` / `texte` concaténés | `texte` | concaténer en texte brut nettoyé |
| `orateur.qualite` ou `roledebat` | `fonction` | garder tel quel, sans inférence politique |
| `code_style`, longueur, densité du texte | `format` | `prise_de_parole_developpee` par défaut ; `reaction_courte` seulement si segment très bref/non développé |
| `code_grammaire` | `type_detail` | `question` pour sections `Questions au Gouvernement` / codes `QG_*`, sinon `loi` |
| URL séance / fichier XML | `source_url` | pointer la source primaire de la séance |
| aucun champ fiable | `mots_cles` | laisser `[]` à ce stade |

Recommandation de regroupement :

- regrouper les `paragraphe` consécutifs d'un même `id_acteur` à l'intérieur
  d'un même `point`
- exclure du corps principal les segments purement scéniques
  (`code_style != NORMAL`) ou les conserver dans le texte seulement si le
  nettoyage reste fidèle à la source

### B. `textes_portes[]` (non, sauf enrichissement croisé)

Syceron ne fournit pas, dans l'échantillon inspecté, les informations
nécessaires pour créer directement une entrée `textes_portes[]` conforme :

- pas d'identifiant de dossier législatif explicite
- pas de rôle `auteur` / `rapporteur` / `co-rapporteur`
- `art` / `adt` décrivent surtout l'étape de débat ou un amendement discuté

Usage réaliste :

- utiliser Syceron comme **contexte de discussion** d'un texte déjà connu via
  les dossiers législatifs AN
- ne pas créer de `textes_portes[]` depuis Syceron seul

### C. Métadonnées racine / provenance

| Syceron | Cible actuelle | Remarque |
|---|---|---|
| `uid`, `seanceRef`, `sessionRef` | `meta` ou futur enrichissement d'intervention | utile pour dédoublonnage et regroupement |
| `legislature`, `numSeance`, `numSeanceJour` | `meta` ou futur enrichissement d'intervention | utile pour filtrage par séance |
| `heureGeneration`, `version`, `etat`, `validite` | `meta.warnings[]` ou métadonnées techniques | utile pour traçabilité, pas forcément public |

---

## Champs à enrichir dans le schéma pivot

L'intégration minimale peut démarrer sans rupture de schéma, mais l'échantillon
montre plusieurs enrichissements utiles :

1. **`interventions[].id_source`**
   - pour conserver `id_syceron` ou `uid`
   - utile au dédoublonnage inter-runs

2. **`interventions[].seance_ref`**
   - pour rattacher plusieurs interventions à une même séance
   - utile côté tri, regroupement, et deep-link source

3. **`interventions[].ordre_source`**
   - pour conserver `ordre_absolu_seance`
   - utile si l'on veut rejouer le fil d'une séance

4. **`interventions[].contexte_procedural`**
   - pour exposer `code_grammaire` sans surcharger `type_detail`
   - utile pour distinguer QG, discussion générale, article, rappel au règlement

5. **`interventions[].objet_source`**
   - pour stocker `art`, `adt`, voire `valeur_ptsodj`
   - utile pour relier une prise de parole à un article/amendement discuté

6. **`interventions[].horodatage_source`** (optionnel)
   - pour conserver `texte@stime` quand présent
   - utile seulement pour de futurs cas de synchronisation vidéo

Recommandation : commencer par 1 à 4 si un adaptateur Syceron est implémenté ;
5 et 6 peuvent rester différés.

---

## Recommandation d'implémentation ultérieure

Ordre le plus simple pour une Phase 1 :

1. parser le ZIP Syceron par séance
2. produire un flux brut d'interventions AN de séance
3. mapper uniquement vers `interventions[]`
4. conserver les identifiants de séance en métadonnées techniques
5. ne pas dériver de thème éditorial ni de `textes_portes[]` sans jointure
   complémentaire avec les dossiers AN
