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
