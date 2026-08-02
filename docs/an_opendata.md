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

## Acteurs / mandats / organes (identité + mandats officiels)

`.../17/amo/deputes_actifs_mandats_actifs_organes/AMO10_deputes_actifs_mandats_actifs_organes.json.zip`
(~4,9 Mo, mise à jour quotidienne). Schéma **retro-documenté par
échantillonnage exhaustif du zip réel** (le Schemas.zip de 2016 ne décrit que
l'ancien export XML monolithique par législature, alors que le zip actuel
contient un fichier JSON par entité) :

- 3 types d'entités mélangées dans le même zip, sous des préfixes distincts :
  `json/acteur/PA{id}.json` (577 fichiers = déjà-élus actuels), `json/organe/PO{id}.json`
  (7126 fichiers — référentiel de TOUS les organes historiques : commissions,
  groupes, circonscriptions, ministères... nécessaires pour résoudre les
  `organeRef` en libellés lisibles), `json/deport/DPTR5L{leg}PA{id}D{n}.json`
  (37 fichiers — déclarations officielles de déport/conflit d'intérêt, avec
  `portee`/`lecture`/`instance`/`cible`/`explication` : une source de
  transparence qu'on n'exploite pas du tout aujourd'hui).
- `acteur.uri_hatvp` : lien vers la déclaration HATVP (Haute Autorité pour la
  Transparence de la Vie Publique) du parlementaire — champ absent de notre
  schéma pivot actuel.
- `acteur.mandats.mandat[].typeOrgane` (24 valeurs observées) : `GP` (groupe
  parlementaire), `COMPER` (commission permanente), `PARPOL` (parti),
  `MISINFO`/`MISINFOCOM`/`MISINFOPRE` (missions d'information), `DELEG`,
  `BUREAU`, `CMP`, `GOUVERNEMENT`, `MINISTERE`, etc. Chaque mandat a
  `dateDebut`/`dateFin`/`organeRef` — historique précis, à rapprocher des
  entrées `organe` du même zip pour le libellé.
- `acteur.mandats.mandat[].infosQualite.codeQualite`/`libQualite` : texte
  libre (pas un enum stable), ex. "Membre", "Président", "Secrétaire"...

## Dossiers législatifs (bulk, multi-législatures dans UN seul fichier)

`.../17/loi/dossiers_legislatifs/Dossiers_Legislatifs.json.zip` (~10 Mo, mise
à jour quotidienne). Schéma retro-documenté de la même façon (échantillonnage
exhaustif, 3029 dossiers analysés) :

- `dossierParlementaire.legislature` couvre en réalité `{8, 11, 12, 13, 14,
  15, 16, 17}` dans ce seul fichier — bien plus large que les législatures
  couvertes par NosDéputés (13 à 17) ou par nos jeux scrutins/amendements
  (13/14/15/16/17 séparés par fichier).
- `titreDossier.titre` : titre humain complet (ex. "Les dépenses de soutien
  aux aéroports") — résout la limitation documentée dans la section
  amendements ci-dessus (`texte_vise` ne contenait qu'un code source brut).
- `procedureParlementaire.{code,libelle}` : enum fermé de 19 valeurs (Projet
  de loi ordinaire, Proposition de loi ordinaire, PLF, PLFSS, Résolution...).
- `initiateur.acteurs.acteur[].{acteurRef,mandatRef}` : liste des député⋅e⋅s
  à l'origine d'une proposition de loi (co-auteurs inclus) — permet de
  retrouver tous les textes déposés par un⋅e élu⋅e directement, sans
  dépendre du scraping NosDéputés.
- `actesLegislatifs` est un arbre récursif (`acteLegislatif.actesLegislatifs.acteLegislatif...`,
  jusqu'à 5 niveaux observés) représentant le déroulé complet de la
  procédure. À chaque niveau, `rapporteurs.rapporteur[].{acteurRef,
  typeRapporteur}` donne l'assignation OFFICIELLE des rapporteur⋅e⋅s
  (`typeRapporteur` ∈ {rapporteur, rapporteur général, rapporteur pour avis,
  rapporteur spécial}) — c'est une source structurée qui pourrait remplacer
  l'attribution de `role`/`type_rapport` actuellement absente/scrapée côté
  NosDéputés (voir le bug de doublons `textes_portes` corrigé plus haut dans
  ce projet). `texteAssocie`/`textesAssocies` référence le(s) texte(s) associé
  à chaque acte, dans le même format que `texteLegislatifRef` des amendements.
- **Pas encore implémenté dans le code** (recherche seulement, voir mémoire
  agent `an-opendata-other-datasets.md`) : décision à prendre séparément sur
  si/comment remplacer la source actuelle de `textes_portes` (changement
  d'architecture non trivial vu la logique de fusion/dédoublonnage déjà en
  place), par opposition à un usage plus ciblé (ex. résoudre les titres des
  amendements, ajouter `uri_hatvp`).
