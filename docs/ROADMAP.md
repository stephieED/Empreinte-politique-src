# ROADMAP

Work sequence, authorized step by step by the user. Keep this file up to
date: move an entry to "Done" as soon as it is implemented and validated,
not merely planned.

This file is not automatically re-read by coding agents on every session
(unlike `AGENTS.md`) — consult it only when planning or reviewing next steps.

---

## Done (recent)

- **CI/CD workflow — two-mode generation + quality gate**:
  `.github/workflows/generate-data.yml` reworked with two `workflow_dispatch`
  inputs (`fresh_run`, `threshold`).
  `fresh_run=true` triggers a full purge, no cache restore, `--no-merge`
  on individual profiles, groupe recreation from scratch, and a zero-tolerance
  quality gate.
  `fresh_run=false` (default, scheduled) preserves existing data via additive
  merge, restores the Actions cache, uses `--merge-existing` for groups, and
  applies a configurable IncompleteRead threshold (default 3).
  New script `src/check_quality_gate.py`: pre-commit gate producing a 4-section
  report (IncompleteRead count + endpoints, candidate coverage, low intervention
  signals, groupe hard/soft validation). Hard fail (exit 1) on broken structure;
  soft warnings on degraded quality. Output written to console and to
  `$GITHUB_STEP_SUMMARY` (Markdown tables in the GHA job summary tab).

- **UI/UX web/v3 — Parliamentary questions**: updated in `web/v3/index.html`.
  (1) "Parliamentary questions" filter (`data-inter-mode="questions"`) added
  as the 4th button in the Speeches panel. (2) Dedicated `question-fragment`
  card: QE/QG/QOSD badge, ministry addressed, truncated text, expandable
  answer (`<details>`) with `date_reponse` when available, link to the AN
  source. (3) Question counter added to `versus-metrics` (4th column) and to
  `expressSummaryData` (5th slide, 20% progression per slide).

- **Harmonized thematic taxonomy (Phase 4)**: `src/theme_taxonomy.py`
  created with 8 stable categories (`STABLE_THEMES`) and a mapping table
  (`_RULES`). `normalize_nosdeputes.py` now uses `classify_keywords()` to
  produce stable categories in `tags_thematiques[]` (no more raw keywords).
  `schema_pivot.py` docstring updated. 10 new unit tests added in
  `tests/test_normalize_nosdeputes.py`.

- **Interest representatives (lobbying registry)**: research completed,
  verdict documented in `docs/hatvp_opendata.md`. HATVP open data is
  available (JSON, updated daily), but matching an elected official to a
  lobbyist is not feasible without a mapping between `acteurRef` and the
  HATVP target-identifier. Out of scope for now; `identite.uri_hatvp`
  remains the natural anchor point if this becomes feasible later.

- **Parliamentary questions (QE/QG/QOSD)**: integrated the 3 official AN
  open data sets into `interventions[].type_detail == "question"`.
  Implemented in `candidate_profile.py` (`fetch_questions_officielles`,
  `_build_acteur_questions_index`, `_parse_question_entry`); mapped to the
  pivot schema in `normalize_nosdeputes.py`; merged in `merge_profile.py`.
  Additional fields: `sous_type` (QE/QG/QOSD), `ministere`, `reponse`,
  `date_reponse`. See `docs/an_opendata.md` for the schema documentation.

## In progress

_(nothing in progress)_

## Planned next

_(nothing currently planned — see "Identified but not scheduled" below)_

## Identified but not scheduled (low priority)

- **Agenda / meetings** (`.../vp/reunions/Agenda.json.zip`): describes
  committee/plenary meetings (agenda, bills examined). Organized by
  body/meeting, not by individual — more useful for precisely dating when a
  bill was examined in committee than for enriching an individual profile
  directly. No expressed need for this today.
- **Extra-parliamentary bodies** (CSV,
  `.../amo/oep_csv_opendata/liste_organismes_extra_parlementaires_excel.csv`):
  corresponds to the `extra_parlementaire` category already planned in
  `schema_pivot.KNOWN_CATEGORIES`, but matching to a profile can only be done
  by free-text name (no `acteurRef`) — a real risk of false positives on
  homonyms. Should not be implemented without a careful matching strategy
  (e.g. name + group, or accepting partial coverage rather than a bad match).