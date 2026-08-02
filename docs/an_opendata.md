# OpenData de l'Assemblée nationale (scrutins, amendements)

Ce projet télécharge deux jeux de données volumineux directement depuis le
catalogue OpenData officiel de l'Assemblée nationale
(<http://data.assemblee-nationale.fr>) : les scrutins (votes nominatifs) et
les amendements. Cette page réunit les repères utiles pour maintenir/étendre
ce code (`src/candidate_profile.py`) sans avoir à re-explorer le catalogue.

## Schéma général des URLs

```
https://data.assemblee-nationale.fr/static/openData/repository/{legislature}/loi/{dossier}/{fichier}.zip
```

- `{legislature}` : `13` à `17` (17 = législature en cours).
- `{dossier}` : varie selon le jeu de données ET la législature (voir tableaux
  ci-dessous) — ne pas supposer qu'il est stable dans le temps.
- Les pages de catalogue (`travaux-parlementaires/...`) sont rendues en JS et
  n'exposent pas les liens `.zip` via un simple fetch HTML. Les sous-pages
  "tous les X" (ex. `travaux-parlementaires/amendements/tous-les-amendements`,
  ou `archives-16e/amendements/tous-les-amendements` pour les législatures
  archivées) intègrent en revanche ces liens directement dans le HTML statique
  — c'est la méthode utilisée pour retrouver les URLs ci-dessous.

## Scrutins (votes nominatifs)

| Législature | Dossier | Fichier |
|---|---|---|
| 17, 16 | `scrutins` | `Scrutins.json.zip` |
| 15 | `scrutins` | `Scrutins_XV.json.zip` |
| 14 | `scrutins` | `Scrutins_XIV.json.zip` |
| 13 | — | pas de jeu de données équivalent disponible |

Voir `AN_SCRUTINS_ZIP_NAME` / `fetch_votes_officiels` dans
[../src/candidate_profile.py](../src/candidate_profile.py).

## Amendements

| Législature | Dossier | Fichier | Taille approx. |
|---|---|---|---|
| 17 (en cours, mise à jour quotidienne) | `amendements_div_legis` | `Amendements.json.zip` | ~283 Mo |
| 16 (archivée) | `amendements_div_legis` | `Amendements.json.zip` | ~363 Mo |
| 15 (archivée) | `amendements_legis` | `Amendements_XV.json.zip` | ~618 Mo (le champ `size` du catalogue data.gouv.fr indique 48 Mo, ce qui est visiblement obsolète — se fier à la taille réelle du téléchargement) |
| 14, 13 | — | pas de jeu de données équivalent (toutes les combinaisons de dossiers testées renvoient 404) |

Le zip contient un fichier JSON par amendement (~123k fichiers pour la 17e
législature), sous `json/{dossier}/{texte}/AMANR5L{legislature}...json`. Voir
`AN_AMENDEMENTS_PATH` / `fetch_amendements_officiels` dans
[../src/candidate_profile.py](../src/candidate_profile.py) — l'index par
acteur est construit en itérant le zip en mémoire (sans extraction sur disque,
vu le nombre de fichiers).

### Champs clés du JSON (constatés empiriquement sur la 17e législature)

- `amendement.signataires.auteur.acteurRef` (`PAxxxxx`) : à rapprocher de
  `identite.url_an_ou_senat` dans nos profils bruts (qui contient déjà cet
  identifiant, ex. `.../fiche/OMC_PA1567`) via `_extract_acteur_ref()`.
- `.signataires.auteur.typeAuteur` : `Député` / `Gouvernement` / `Rapporteur`
  (`Commission` vu aussi occasionnellement dans l'échantillon).
- `.cycleDeVie.etatDesTraitements.etat.libelle` et `.sousEtat.libelle` :
  couple non trivial — `etat` porte la catégorie principale (discuté,
  irrecevable, irrecevable art. 40, retiré...) et `sousEtat` porte le
  sort/motif précis. Voir `_derive_amendement_sort()` et
  `_AMENDEMENT_SORT_MAP` dans `candidate_profile.py` pour le mapping complet,
  dérivé d'un échantillonnage de la distribution jointe (etat, sousEtat) sur
  ~3000 amendements.
- `.texteLegislatifRef` : code source brut du texte visé (pas un titre
  lisible) — stocké tel quel dans `texte_vise`, résoudre un vrai titre
  nécessiterait un jeu de données dossiers/textes séparé (non fait).
- `.representations.representation.contenu.documentURI` : ne résout vers
  aucune URL publique fonctionnelle testée (3 domaines essayés) — `source_url`
  reste `None` pour tous les amendements.

## Archive « Schémas et documentation des données législatives »

<http://data.assemblee-nationale.fr/static/openData/repository/SCHEMAS/Schemas.zip>
(MD5 `67a8dd5b74dea0cc688003b3400c879e`, daté 2016-11-25) contient une
documentation Sphinx (HTML) décrivant le modèle de données législatif de
l'Assemblée (concepts, XSD commentés, glossaire). Utile pour le contexte
général, mais **daté** : le XSD des amendements qu'elle contient (schéma
v0.9.8) utilise encore l'ancien format à plat (`etat`/`sortEnSeance`) et ne
mentionne ni `cycleDeVie`/`etatDesTraitements`/`sousEtat` ni `documentURI`,
qui sont apparus dans le JSON actuellement exposé. À prendre comme repère
conceptuel complémentaire, pas comme source de vérité sur le format JSON
réellement consommé par `candidate_profile.py` (celui-ci a été déterminé par
échantillonnage direct des données réelles).

Éléments utiles malgré tout, car ils confirment/complètent notre mapping :

- Enum historique de `typeAuteur` : `Gouvernement`, `Rapporteur`, `Depute`
  (cohérent avec `_AMENDEMENT_TYPE_AUTEUR_MAP`).
- Enum historique de `sortEnSeance` : `Adopté`, `Rejeté`, `Non soutenu`,
  `Tombé`, `Irrecevable Art 40C`, `Irrecevable Art 41c`, `Irrecevable Art 44c`,
  `Retiré` — confirme que l'irrecevabilité est structurellement liée à un
  article constitutionnel précis (40/41/44 historiquement ; le JSON actuel
  référence en plus les art. 45/98/37/38/42 via `sousEtat`), ce qui justifie
  la simplification actuelle du schéma pivot (`art. 40` / `art. 45` uniquement
  — voir `schema_pivot.KNOWN_BASES_IRRECEVABILITE`).
