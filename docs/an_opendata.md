# National Assembly Open Data (votes, amendments)

This project downloads two large datasets directly from the official National
Assembly Open Data catalog (<http://data.assemblee-nationale.fr>): votes
(roll-call records) and amendments. This page gathers practical references to
maintain/extend this code (`src/candidate_profile.py`) without re-exploring the
catalog every time.

## General URL pattern

```
https://data.assemblee-nationale.fr/static/openData/repository/{legislature}/loi/{dataset}/{file}.zip
```

- `{legislature}`: `13` to `17` (`17` is current).
- `{dataset}`: varies by data family and legislature (see tables below) - do
  not assume temporal stability.
- Catalog pages rendered in JS do not expose `.zip` links via naive HTML fetch.
  The "all X" subpages (for example amendments pages) include links in static
  HTML and are used as the reliable discovery path.

## Votes (roll-call records)

| Legislature | Dataset | File |
|---|---|---|
| 17, 16 | `scrutins` | `Scrutins.json.zip` |
| 15 | `scrutins` | `Scrutins_XV.json.zip` |
| 14 | `scrutins` | `Scrutins_XIV.json.zip` |
| 13 | - | no equivalent dataset available |

See `AN_SCRUTINS_ZIP_NAME` / `fetch_votes_officiels` in
`src/candidate_profile.py`.

## Amendments

| Legislature | Dataset | File | Approx. size |
|---|---|---|---|
| 17 (ongoing, daily updates) | `amendements_div_legis` | `Amendements.json.zip` | ~283 MB |
| 16 (archived) | `amendements_div_legis` | `Amendements.json.zip` | ~363 MB |
| 15 (archived) | `amendements_legis` | `Amendements_XV.json.zip` | ~618 MB |
| 14, 13 | - | no equivalent dataset (tested paths return 404) |

The ZIP contains one JSON per amendment (~123k files for legislature 17),
under `json/{dataset}/{text}/AMANR5L{legislature}...json`.
See `AN_AMENDEMENTS_PATH` / `fetch_amendements_officiels` in
`src/candidate_profile.py`.

### Key JSON fields (empirical observations on legislature 17)

- `amendement.signataires.auteur.acteurRef` (`PAxxxxx`): linked against
  `identite.url_an_ou_senat` in raw profiles (which already contains the AN ID)
  via `_extract_acteur_ref()`.
- `.signataires.auteur.typeAuteur`: `Depute`, `Gouvernement`, `Rapporteur`
  (`Commission` seen occasionally).
- `.cycleDeVie.etatDesTraitements.etat.libelle` and `.sousEtat.libelle`:
  non-trivial pair used by `_derive_amendement_sort()` and
  `_AMENDEMENT_SORT_MAP` in `candidate_profile.py`.
- `.texteLegislatifRef`: raw target code, not a human title.
- `.representations.representation.contenu.documentURI`: currently does not
  resolve to a stable public URL in tested cases.

## Archive: "Schemas and legislative data documentation"

<http://data.assemblee-nationale.fr/static/openData/repository/SCHEMAS/Schemas.zip>
(MD5 `67a8dd5b74dea0cc688003b3400c879e`, dated 2016-11-25) contains Sphinx
HTML documentation for the Assembly data model. Useful context, but **outdated**
for current JSON payloads.

Still useful confirmations:

- Historical `typeAuteur` values match `_AMENDEMENT_TYPE_AUTEUR_MAP`.
- Historical `sortEnSeance` values confirm procedural constitutional
  inadmissibility distinctions.

## Actors / mandates / bodies (official identity + mandates)

`.../17/amo/deputes_actifs_mandats_actifs_organes/AMO10_deputes_actifs_mandats_actifs_organes.json.zip`
(~4.9 MB, daily updates).

Empirically documented structure:

- Mixed entity types in one ZIP:
  - `json/acteur/PA{id}.json`
  - `json/organe/PO{id}.json`
  - `json/deport/DPTR5L{leg}PA{id}D{n}.json`
- `acteur.uri_hatvp`: link to HATVP declaration (not yet in current pivot schema).
- `acteur.mandats.mandat[].typeOrgane`: wide set of observed types (`GP`,
  `COMPER`, `PARPOL`, `MISINFO*`, `DELEG`, `BUREAU`, `CMP`, `GOUVERNEMENT`,
  `MINISTERE`, ...).
- `acteur.mandats.mandat[].infosQualite.codeQualite/libQualite`: free-text labels.

## Legislative files (bulk, multi-legislature in one file)

`.../17/loi/dossiers_legislatifs/Dossiers_Legislatifs.json.zip` (~10 MB,
daily updates).

Empirical findings:

- `dossierParlementaire.legislature` spans `{8, 11, 12, 13, 14, 15, 16, 17}`
  in a single file.
- `titreDossier.titre`: full human-readable title.
- `procedureParlementaire.{code,libelle}`: closed set of observed values.
- `initiateur.acteurs.acteur[]`: actor-level bill initiators.
- `actesLegislatifs` is a recursive tree, including official reporters and
  procedural milestones.

Implemented path:

- `candidate_profile.fetch_textes_portes_officiels` /
  `_build_acteur_textes_portes_index` build `acteurRef -> dossiers` with known
  factual roles (`auteur`, `rapporteur`, `co-rapporteur`) and inferred
  procedural stage.
- This replaces legacy Nos* dossier lists for deputies.
- `merge_profile.py` drops `dossiers_legislatifs`/`textes_portes` entries that
  have no factual `role` during migration/merge.

### Spike : origine (gouvernementale vs parlementaire) et statuts (`codeActe`) (2026-08-12)

Spike documentaire pour #207 (préparation de #184). **Limite importante** :
cette session n'a pas eu accès réseau sortant vers
`data.assemblee-nationale.fr` (tentatives via `curl`, `gh api` et `WebFetch`
toutes bloquées faute d'approbation possible dans ce contexte automatisé —
voir AGENTS.md règle 5, "missing data means missing data, never assume").
Le ZIP `Dossiers_Legislatifs.json.zip` n'a donc **pas pu être re-téléchargé
ni ré-inspecté** dans le cadre de ce spike. Ce qui suit distingue clairement
ce qui est déjà confirmé (code existant, propre session antérieure) de ce qui
reste à vérifier avec un accès réel au dump.

**Origine gouvernementale vs parlementaire — non confirmé.**

- Le code actuel (`_collect_initiateurs`, `src/candidate_profile.py:1004-1017`)
  ne lit que `initiateur.acteurs.acteur[].acteurRef` ; il ne regarde ni
  `organe.codeType`, ni aucun autre champ d'origine. Aucune distinction
  gouvernemental/parlementaire n'est donc calculée aujourd'hui.
- L'hypothèse posée dans l'issue (repérer un acteur dont l'`organe`
  référencé a `codeType == "GOUVERNEMENT"`, cf. valeurs `typeOrgane`
  déjà observées côté acteurs/mandats — voir section "Actors / mandates /
  bodies" plus haut, qui liste `GOUVERNEMENT`/`MINISTERE` parmi les
  `typeOrgane` réels de `AMO10_...json.zip`) est plausible mais **non
  vérifiée sur `initiateur.acteurs.acteur[]` lui-même** : on ignore si un
  acteur gouvernemental y apparaît avec un `acteurRef` de type `PAxxxxx`
  (comme un député), avec un identifiant distinct, ou pas du tout (dossier
  sans aucun `initiateur.acteurs` renseigné).
- Signal alternatif, connu indépendamment de ce dataset (droit
  constitutionnel, art. 39 de la Constitution, pas une inspection de
  données) : un dossier dont `titreDossier.titre` commence par
  "Projet de loi" est d'origine gouvernementale ; un dossier dont le titre
  commence par "Proposition de loi" est d'origine parlementaire. Ce signal
  est **complémentaire**, pas un substitut : il ne repose pas sur la
  structure `initiateur.acteurs.acteur[]` demandée par l'issue, et ses cas
  limites (ex. propositions issues d'un rapport de commission, textes
  transmis du Sénat) n'ont pas non plus été vérifiés sur un échantillon réel.
- **À faire avant de coder cette distinction en dur** (sous-issue #4) :
  ré-exécuter cette inspection dans un environnement avec accès réseau
  sortant vers `data.assemblee-nationale.fr`, sur un échantillon d'au moins
  quelques dizaines de dossiers couvrant les deux origines.

**Statuts (`codeActe`) — partiellement confirmé.**

- Seul le mapping déjà en production est confirmé par le code existant
  (`_stade_from_code_acte`, `src/candidate_profile.py:982-1001`), et
  volontairement conservateur (nomenclature du schéma pivot, pas la
  nomenclature cible de #184) :
  - `codeActe` contient `"PROM"` → `promulgue`.
  - `codeActe` se termine par `"-DEBATS-DEC"` **et**
    `statutConclusion.libelle` commence par `"adopt"` → `adopte` ; sinon
    `discute_seance`.
  - `codeActe` contient `"DEBATS"` (sans `-DEBATS-DEC`) → `discute_seance`.
  - `codeActe` contient `"COM"` → `examine_commission`.
  - `codeActe` contient `"DEPOT"` → `depose`.
  - Ce sont des correspondances par sous-chaîne, pas une énumération exacte
    des valeurs de `codeActe` observées dans le dump.
- Valeurs illustratives présentes dans `tests/test_candidate_profile.py`
  (`"AN1-COM-FOND-NOMIN"`, `"AN1-DEPOT"`, `"PROM-PUB"`) sont des fixtures de
  test, **pas des valeurs confirmées comme exhaustives ou représentatives**
  du dump réel — à ne pas réutiliser comme référence de nomenclature sans
  revérification.
- **Non confirmable dans ce spike** (aucun exemple réel disponible) :
  - `codeActe` exact pour un **rejet** de dossier (aucun heuristique
    existant ne couvre ce cas — `_stade_from_code_acte` n'a pas de valeur
    de retour pour "rejeté").
  - `codeActe` exact pour un **retrait** de dossier (même limite).
  - `codeActe` et/ou combinaison de champs (`codeActe` +
    `statutConclusion.libelle`, par analogie avec le cas `adopte` ci-dessus)
    identifiant une **adoption via l'article 49.3** (engagement de la
    responsabilité du gouvernement). Le schéma pivot réserve déjà la valeur
    `sort = "adopte_sans_vote_49_3"` pour `votes[]`
    (`src/schema_pivot.py:81-90`, `:403-433`) mais aucun code ne la produit
    encore à partir de `Dossiers_Legislatifs.json.zip` ni de `Scrutins.json.zip`.
  - Absence de confirmation qu'il existe un `codeActe` **unique et stable**
    pour "adoption définitive" à travers toutes les législatures `{8, 11,
    12, ..., 17}` couvertes par le fichier bulk, vs une variation possible
    selon la chambre/législature.

**Conclusion du spike** : aucun des quatre statuts cibles (adopté, rejeté,
retiré, adopté 49.3) ni l'hypothèse d'origine gouvernementale ne peuvent être
considérés comme confirmés à ce stade. Seul le sous-ensemble déjà en
production (`depose`, `examine_commission`, `discute_seance`, `adopte`,
`promulgue`, approximatif) est fiable. Toute sous-issue qui dépend de ces
mappings (schéma #2, parsing #4) doit prévoir sa propre vérification sur
échantillon réel avant implémentation, ou être bloquée en attendant un accès
réseau sortant pour refaire ce spike correctement.

## Parliamentary questions (written/oral/government)

Unlike actors/files, these datasets use per-legislature paths:
`.../{legislature}/questions/{dataset}/{file}.json.zip`

| Type | Dataset | File | Approx. size (17th) |
|---|---|---|---|
| Written (QE) | `questions_ecrites` | `Questions_ecrites.json.zip` | ~45 MB |
| Government (QG) | `questions_gouvernement` | `Questions_gouvernement.json.zip` | ~5.2 MB |
| Oral without debate (QOSD) | `questions_orales_sans_debat` | `Questions_orales_sans_debat.json.zip` | ~3.1 MB |

Useful fields:

- `question.auteur.identite.acteurRef`: direct elected-official ID.
- `question.auteur.groupe.*`: group at question date.
- `question.minInt.developpe`: queried ministry.
- `question.indexationAN.analyses.analyse`: short subject summary.
- `question.textesQuestion...` and `question.textesReponse...`: full texts and
  publication dates.

Implemented in code:

- `candidate_profile._parse_question_entry`
- `_build_acteur_questions_index`
- `fetch_questions_officielles`
- Integration in `build_profile()` and normalization in
  `normalize_nosdeputes._normalize_intervention`
- Merge in `merge_profile.merge_raw_profile`

## Comptes rendus de séance (Syceron)

URL pattern:
```
https://data.assemblee-nationale.fr/static/openData/repository/{legislature}/vp/syceronbrut/syseron.xml.zip
```

Attention path/case:
- `vp` en minuscule (la variante `VP/` retourne 404)
- nom de fichier `syseron.xml.zip`

| Législature | Disponible | Taille ZIP | Statut |
|---|---|---|---|
| 13 | ❌ 404 | — | Non disponible |
| 14 | ❌ 404 | — | Non disponible |
| 15 | ✅ 200 | ~149 MB | Archivé (2022) |
| 16 | ✅ 200 | ~57 MB | Archivé (2024) |
| 17 | ✅ 200 | ~56 MB | Live, quotidien |

Format:
- ZIP vers `xml/compteRendu/CRSANR5L{legislature}*.xml` (un XML par séance)
- identifiants clés: `uid`, `seanceRef`, `sessionRef`
- métadonnées utiles: `metadonnees/dateSeance`, `metadonnees/etat`, `metadonnees/version`

Structure utile de contenu:
- `contenu/point` pour le bloc d'ordre du jour
- `paragraphe/orateurs/orateur/{id,nom,qualite}` pour l'orateur
- `paragraphe/texte` pour le texte (avec balises inline)

Intégration pipeline (active):
- fetch/cache XML via `src/syceron_debates.py`
- parsing via `src/parse_syceron.py`
- indexation acteur via `src/candidate_profile.py` (`_build_acteur_interventions_syceron_index`)
- fusion dans `interventions[]` via `fetch_interventions_syceron`

Mapping effectif dans `interventions[]`:
- `date` depuis `metadonnees/dateSeance` (normalisée)
- `type_detail` / `sujet` depuis `point/titreStruct/intitule` (fallback progressif)
- `texte` depuis `paragraphe/texte`
- `fonction` depuis `orateur/qualite`
- `source_url` conservée pour traçabilité

Contraintes/limites:
- pas de champ `theme` natif (classification dérivée seulement)
- pas de lien direct fiable vers `textes_portes[]` sans jointures additionnelles

Stratégie recommandée:
- full dump par législature (pas de téléchargement ciblé par séance)
- priorité produit: L17 puis L16, L15 en profondeur historique

## Agenda / meetings (committees) - low priority

`.../17/vp/reunions/Agenda.json.zip` (~7.8 MB).

Describes committee/plenary meetings (location, agenda, refs), but data is
organized by meeting/body rather than directly by `acteurRef`. Useful for
procedural chronology, not yet implemented.

## Extra-parliamentary bodies (CSV) - low priority

`.../17/amo/oep_csv_opendata/liste_organismes_extra_parlementaires_excel.csv`
(~1 MB, `;` separator, likely Latin-1 encoding).

Contains free-text member names rather than stable actor IDs, making reliable
matching risky (homonyms). Not implemented.
