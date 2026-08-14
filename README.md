# EMPREINTE POLITIQUE

Generates structured "political CVs" (mandates, responsibilities, votes,
legislative files, floor interventions) for candidates in the 2027 French
presidential election, using open data from
[NosDeputes.fr / NosSenateurs.fr](https://github.com/regardscitoyens)
(Regards Citoyens, ODbL), the
[French National Assembly open data portal](https://data.assemblee-nationale.fr/)
for vote details, [Parltrack](https://parltrack.org) + the
[European Parliament Open Data Portal](https://data.europarl.europa.eu/)
(CC BY 4.0) for the European mandate dimension of former MEP candidates, and
Wikipedia/Wikidata for candidacy monitoring.

**Guiding principle**: every displayed fact must be traceable to a primary
source (official vote, legislative file, specific Wikipedia revision).
The project does not make value judgments.

## Repository layout

```
CV_CandidatFR/
|- src/                               # Python scripts
|  |- candidate_profile.py           # Collect raw profile for ONE FR parliamentarian (AN/Senate)
|  |- candidate_profile_ue.py        # Build the "European mandate" section for ONE candidate
|  |- generate_all_profiles.py       # Batch: profiles for candidates in a --candidats list (candidats.json by default, or a roster-driven file)
|  |- generate_roster_candidats.py   # Builds a --candidats-compatible list from real group rosters (groupes_reels.json), for full group coverage beyond declared candidates
|  |- merge_profile.py               # Additive merge logic (old wins on lists, new wins on scalars)
|  |- normalize_nosdeputes.py        # NosDeputes/NosSenateurs -> pivot adapter
|  |- normalize_europarl.py          # European Parliament Open Data -> pivot adapter
|  |- normalize_parltrack_dumps.py   # Parltrack dumps -> pivot adapter (EP mandates)
|  |- parltrack_dumps.py             # Parltrack dump download/cache helpers
|  |- syceron_debates.py             # AN Syceron comptes rendus: download, cache, acteurRef index
|  |- parse_syceron.py               # AN Syceron XML parser -> interventions[]
|  |- text_utils.py                  # Shared text helpers (normalisation, accent folding)
|  |- group_profile.py               # Aggregate individual profiles into a parliamentary group profile
|  |- group_roster.py                # Fetch real group composition (NosDeputes/NosSenateurs)
|  |- generate_group_profiles.py     # Batch: all groups from raw_data/groupes_reels.json
|  |- gouvernement_roster.py         # Ministerial roster of a government from local pivots (no network call)
|  |- parti_profile.py               # Editorial party aggregates from individual pivots
|  |- check_quality_gate.py          # Pre-commit quality gate + run summary (4 sections)
|  |- audit_pivot_dataset.py         # Pivot dataset audit: volumetry/completeness/consistency/freshness/warnings + JSON/Markdown report
|  |- audit_groupe_dataset.py        # Groupe dataset audit: same categories as audit_pivot_dataset.py + JSON/Markdown report
|  |- audit_pipeline.py              # Manual tool: runs both audits above and compiles an overview + combined JSON/Markdown report
|  |- schema_pivot.py                # Pivot schema v1 - common format across all sources
|  |- schema_groupe.py               # Group profile schema v1 (structure contract)
|  |- schema_parti.py                # Party profile schema v1
|  |- schema_gouvernement.py         # Government profile schema v1 (structure contract, no aggregation logic yet)
|  |- mep_profile.py                 # Collect/normalize EP profiles (Parltrack)
|  `- fetch_wikipedia_candidates.py  # Candidate monitoring via Wikipedia/Wikidata
|- raw_data/                          # Declarative inputs + raw outputs (non-normalized)
|  |- candidats.json                 # Candidate list (name, slug, party, status, sources)
|  |- groupes_reels.json             # Validated list of real groups to generate
|  |- gouvernements_reels.json       # Validated list of real governments (ministerial roster source)
|  `- profiles/                      # Raw candidate profiles: <slug>.json
|- pivot_data/                        # Anything in pivot schema format (or derived)
|  |- profiles/                      # <slug>.pivot.json per candidate
|  |- partis/                        # parti-<slug>.json: editorial party aggregates
|  `- groupes/                       # groupe-<SIGLE>-<leg>.json: real parliamentary group profiles
|- web/
|  |- UI_finale/                     # Production interface: React 19 + Vite (Candidats · Groupes)
|  `- old/                           # Archived design generations (v1–v7, atlas, studies…)
|- docs/
|  |- nosdeputes_doc/                # NosDeputes/NosSenateurs API reference (kept in French)
|  `- an_opendata.md                 # Notes on AN open data (votes, amendments, Syceron)
|- tests/
|  |- test_candidate_profile.py
|  |- test_candidate_profile_ue.py
|  |- test_group_profile.py
|  |- test_group_roster.py
|  |- test_generate_group_profiles.py
|  |- test_gouvernement_roster.py
|  |- test_merge_profile.py
|  |- test_normalize_europarl.py
|  |- test_normalize_nosdeputes.py
|  |- test_normalize_parltrack_dumps.py
|  |- test_parltrack_dumps.py
|  |- test_parse_syceron.py
|  |- test_parti_profile.py
|  |- test_quality_gate_amendements.py
|  |- test_quality_gate_syceron.py
|  |- test_schema_groupe.py
|  |- test_schema_gouvernement.py
|  |- test_schema_parti.py
|  |- test_schema_pivot.py
|  |- test_syceron_debates.py
|  |- test_web_v3_issue_66.py
|  |- test_web_v3_issue_128.py
|  `- test_web_v3_mandate_timeline.py
`- README.md
```

- `.cache/` (auto-created, git-ignored): local cache for AN vote archives,
  Parltrack dumps, and European Parliament datasets to avoid re-downloading
  large and mostly static files.

## Schemas and transformations

See:

- `docs/schema_donnees_transformations.md` - input schemas, transformed schemas,
  and pipeline (including additive merge logic in `merge_profile.py`).
- `docs/an_opendata.md` - practical AN Open Data references (dataset URLs,
  key fields).
- `docs/pipeline-profiles-groupes.md` - end-to-end profiles/groups pipeline
  maps and implementation notes.
- `docs/extract-an.md` - CI job `extract-an` (scope, extraction chain, sources).
- `docs/extract-senat.md` - CI job `extract-senat` (scope, extraction chain, sources).
- `docs/extract-ue.md` - UE source investigation report and implementation context.
- `docs/extract-parltrack.md` - CI job `extract-parltrack` (dumps, cache, fallback).
- `docs/technical_decisions.md` - full rationale and edge-case history.
- `AGENTS.md` - condensed non-negotiable rules for agents.

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install requests beautifulsoup4 pytest
```

Run all commands below from the repository root with the virtual environment
activated.

## 1. Generate one candidate profile (AN / Senate)

```bash
python src/candidate_profile.py jean-luc-melenchon --chambre deputes
python src/candidate_profile.py bruno-retailleau --chambre senateurs
```

Default output: `raw_data/profiles/<slug>.json`.

| Option | Effect |
|---|---|
| `--chambre {deputes,senateurs}` | Parliament chamber (`deputes` by default) |
| `--out path.json` | Change output file |
| `--max-pages N` | Limit intervention pagination (default: 10 pages x 50 results). Lower is faster but less complete. |

## 2. Add the "European mandate" section

Some candidates are former MEPs (e.g., Jordan Bardella, Marine Le Pen,
Jean-Luc Melenchon). This section is fetched separately from the official
European Parliament Open Data Portal:

```bash
python src/candidate_profile_ue.py "Jordan Bardella"
# prints JSON to stdout; add --out path.json to write a file
```

Lookup uses exact full-name matching on normalized names (diacritics, case,
word order ignored) against the full MEP list for a country (`--country`,
default `FR`). Not found is not an error; it means no MEP record was found.
In practice, `generate_all_profiles.py` already invokes this automatically.

### Is this API legal to use?

Yes. `https://data.europarl.europa.eu/api/v2/` is published by the European
Parliament under **CC BY 4.0**. Two technical requirements are already
implemented in `candidate_profile_ue.py`:

- send a project-identifying `User-Agent` header;
- stay under **500 requests / 5 minutes**.

## 3. Generate all candidate profiles (batch)

```bash
python src/generate_all_profiles.py
python src/generate_all_profiles.py --only jean-luc-melenchon
python src/generate_all_profiles.py --max-pages 5
python src/generate_all_profiles.py --skip-existing
python src/generate_all_profiles.py --pivot
python src/generate_all_profiles.py --skip-ue
python src/generate_all_profiles.py --workers 8
python src/generate_all_profiles.py --out-dir /tmp/profiles
python src/generate_all_profiles.py --pivot-dir /tmp/pivots
python src/generate_all_profiles.py --limit 20    # premiers N candidats (déploiement progressif)
python src/generate_all_profiles.py --sample 20   # échantillon aléatoire de N candidats
```

Extraction pilotée par roster (composition réelle des groupes parlementaires,
au lieu de la liste éditoriale `raw_data/candidats.json`, voir
[`docs/technical_decisions.md#provenance-pivot`](docs/technical_decisions.md#provenance-pivot)) :

```bash
python src/generate_roster_candidats.py
python src/generate_all_profiles.py --candidats raw_data/roster_candidats.json --pivot --skip-existing
```

With `--limit` **and** `--skip-existing` combined (the invocation used by the CI roster job), selection
is progressive and self-refreshing instead of always retrying the same first N candidates (#224): budget
goes first to roster members with no existing pivot (moving the coverage frontier forward run over run),
then — if budget remains — to already-covered members whose pivot is stale (`--staleness-days`, default
30, same semantics as `audit_pivot_dataset.py --staleness-days`); those are refreshed via additive merge,
never skipped. A covered and fresh profile is neither re-fetched nor counted against the budget.

For each candidate from `raw_data/candidats.json`, the script:

1. tries FR profile collection (`deputes`, then `senateurs`) using Nos*
   slug when available;
2. tries EU mandate lookup by name (unless `--skip-ue`) and merges it under
   `mandat_europeen`;
3. writes `raw_data/profiles/<slug>.json` as soon as at least one source
   (FR or EU) returns data.

With `--pivot`, it also writes `pivot_data/profiles/<slug>.pivot.json`.

### Two-level parallelism

- **Level 1 (within candidate)**: Nos* + EP API calls run in parallel.
- **Level 2 (across candidates)**: candidate jobs are parallelized with
  `--workers` (default 4).

Reduce workers (e.g., `--workers 2`) if public APIs start returning 429.

## 4. Generate one MEP profile (Parltrack)

```bash
python src/mep_profile.py --name "Manon Aubry"
python src/mep_profile.py --ep-id 197451
python src/mep_profile.py --list
python src/mep_profile.py --show-cache-date
```

First run downloads large Parltrack dumps to `.cache/parltrack/`.
Always verify freshness with `--show-cache-date`.

## 5. Generate party profiles

`parti_profile.py` builds **party profiles** from party labels declared in
`raw_data/candidats.json` and available individual pivots.

```bash
python src/parti_profile.py \
    --candidats raw_data/candidats.json \
    --profiles-dir pivot_data/profiles \
    --out-dir pivot_data/partis
```

These are editorial aggregates of declared candidates, not real parliamentary
cohesion profiles. `pivot_data/partis/` is still generated for internal use
but is not displayed as a top-level tab in `web/UI_finale/`.

## 6. Generate parliamentary group profiles

`group_profile.py` aggregates individual profiles (raw Nos* or pivot v1)
into a **real parliamentary group profile** (`schema_groupe.py`).

```bash
python src/group_profile.py \
    --groupe-id "AN:SOC" \
    --groupe-sigle SOC \
    --groupe-nom "Socialistes et apparentes" \
    --chambre AN \
    --legislature 16 \
    pivot_data/profiles/jerome-guedj.pivot.json \
    pivot_data/profiles/boris-vallaud.pivot.json \
    --out pivot_data/groupes/groupe-SOC-16.json
```

Input profiles can be raw or pivot format; detection is automatic.

With `--from-roster`, output overwrite is default. `--merge-existing` keeps
previously known members absent from a transiently incomplete roster fetch.

### Generate multiple real groups in one run

`generate_group_profiles.py` avoids repeated roster downloads by fetching once
per `(chambre, legislature)` and filtering locally by group acronym.

```bash
python src/generate_group_profiles.py \
    --config raw_data/groupes_reels.json \
    --profiles-dir pivot_data/profiles \
    --out-dir pivot_data/groupes \
    --validate
```

`--merge-existing` applies to all groups in config.

### Government ministerial roster

`gouvernement_roster.py` extracts a government's ministerial composition
(`membres[]`) from `mandats[].categorie == "fonction_gouvernementale"` already
present in local pivots — no network call. Disambiguates homonymous
successive governments via `raw_data/gouvernements_reels.json`'s manually
validated `libelle_an` (exact match on `mandats[].label`, `organe.libelleAbrege`
from the AN referential) combined with a period-overlap check. `portefeuille`
stays `null` (see [`docs/technical_decisions.md#hors-perimetre`](docs/technical_decisions.md#hors-perimetre),
§ "Ministerial function"). Produces only the roster, not a full
`pivot_data/gouvernements/*.json` profile (`schema_gouvernement.py`) — that
combination with sponsored texts is a separate, not-yet-implemented step.

```bash
python src/gouvernement_roster.py \
    --config raw_data/gouvernements_reels.json \
    --gouvernement-id "gouvernement:BAYROU" \
    --profiles-dir pivot_data/profiles
```

## 7. Candidate monitoring via Wikipedia / Wikidata

```bash
python src/fetch_wikipedia_candidates.py
python src/fetch_wikipedia_candidates.py --source wikipedia
python src/fetch_wikipedia_candidates.py --source wikidata
python src/fetch_wikipedia_candidates.py --json
```

This script never modifies `candidats.json` automatically; it outputs a review
summary for manual validation.

## 8. CI/CD automated generation workflow

The workflow `.github/workflows/generate-data.yml` runs the full pipeline
on GitHub Actions and is triggered manually (`workflow_dispatch`).

Detailed extraction and merge flow is documented in:

- `docs/pipeline-profiles-groupes.md`
- `docs/extract-an.md`
- `docs/extract-senat.md`
- `docs/extract-ue.md`
- `docs/extract-parltrack.md`

The `extract-amendements-an` job runs `src/build_amendements_index.py`
independently (no `needs:`) to build the 3 AN amendements legislature
indexes unconditionally and pre-warm the shared `.cache/amendements_an/`
cache (artifact `amendements-index-an`), instead of leaving that
construction to lazy per-candidate calls in `extract-an`/
`extract-roster-groupes`. `continue-on-error: true`, same pattern as
`extract-parltrack` — see `docs/technical_decisions.md#amendements-index-job-dedie-ci`.
Legislatures 15/16 are excluded from this network path: their dossier is
closed and the CI download budget can't reliably fetch their 350-650 MB
archive (recurring `IncompleteRead`, reproduced outside CI too). Their index
is built once, offline, via `src/build_amendements_index_figees.py --legislature
{15,16} (--zip <local archive> | --download)` (`--download` reuses the same
segmented/retried fetch as the CI job, writing into gitignored
`.cache/amendements_an/`) and committed under `raw_data/amendements_an_figes/`
— the script deduplicates the raw per-signataire index into
`amendements.json` + a slim `index_par_acteur.json` before writing, since the
undeduplicated form is multiple GB uncompressed (measured on legislature 16)
and can't be committed. `candidate_profile.py` reads that fallback (expanding
it back to the standard flat shape) instead of hitting the network for those
two — see `docs/technical_decisions.md#amendements-legislatures-figees`.

The merge stage runs `src/check_quality_gate.py`; commit/push occurs only if
the gate exits with code 0. Before that step, the `merge-and-pivot` job also
downloads the `amendements-index-an` artifact into `.cache/amendements_an`
(optional, `continue-on-error: true`, same cache-only pattern as `extract-an`/
`extract-roster-groupes`) so the gate's amendements freshness section (3d) can
read the real `fraicheur.json` indicators instead of always reporting "never
built".

To run the gate locally:

```bash
python src/check_quality_gate.py
python src/check_quality_gate.py --threshold 0                # zero tolerance
python src/check_quality_gate.py --low-interventions 5        # stricter signal
python src/check_quality_gate.py --groupe-min-coverage-pct 50  # relative groupe coverage soft fail (disabled by default)
python src/check_quality_gate.py --amendements-staleness-days 14  # laxer amendements freshness signal (default: 7, 0 disables)
```

`--groupe-min-coverage-pct` (default `0`, disabled) is a relative alternative/complement
to `--groupe-min-members` (default `1`, absolute count) for the groupe coverage soft
warning — see `docs/technical_decisions.md#seuil-couverture-groupe` for why the absolute
default is kept until full-scale roster-driven extraction (#188/#190/#191) produces real
coverage numbers.

`--amendements-cache-dir` (default `.cache/amendements_an`) / `--amendements-staleness-days`
(default `7`, `0` disables) control the section 3d soft warning that distinguishes, per
legislature, an amendements index that was never built from one that is present but stale
(no successful rebuild within the threshold, per the `fraicheur.json` indicator written by
`candidate_profile.py`, #253), or frozen (légis 15/16, `fraicheur.json` carries `figee: true`
— never staleness-checked, see `docs/technical_decisions.md#amendements-legislatures-figees`) — see
`docs/technical_decisions.md#amendements-index-quality-gate-fraicheur`.

## 9. Open the web UI locally

`web/UI_finale/` is the production interface (React 19 + Vite, **Candidats** · **Groupes**,
no Partis tab). Before running it, sync pivot data into `public/data/`:

```bash
cd web/UI_finale
npm install          # first time only
npm run dev          # syncs data then starts Vite dev server
```

`scripts/sync-data.mjs` copies `pivot_data/profiles/`, `pivot_data/groupes/` and
`raw_data/candidats.json` into `public/data/` (generated, git-ignored) and writes
`public/data/manifest.json`. Coverage is limited to the candidates/groups with a
local pivot file — see "Coverage limits" below for the current state of the
roster-driven rollout.

Archived design generations are in `web/old/` (v1–v7, atlas, interface-essentielle,
studies) — static HTML, serve with `python -m http.server 8000` from the repo root.

## 10. Audit the pivot dataset

`src/audit_pivot_dataset.py` scans a directory of `*.pivot.json` files and reports
volumetry (including a breakdown by `meta.provenance`, `candidat_declare` vs.
`roster_groupe`), completeness, consistency, source freshness, aggregated
`meta.warnings[]` indicators, and a per-candidate cross-tab of `votes` /
`textes_portes` / `amendements` / `interventions` counts — an internal quality
tool, not an end-user report (no score, no ranking, see `AGENTS.md` §2).

```bash
python src/audit_pivot_dataset.py \
    --input-dir pivot_data/profiles \
    --output-json audit_report.json \
    --output-md audit_report.md \
    --staleness-days 30
```

`--output-json`/`--output-md` default to unset (JSON prints to stdout, Markdown is
skipped if `--output-md` is omitted). `--staleness-days` (default 30) sets the
threshold beyond which a profile with only stale sources is flagged. See
`docs/examples/audit_pivot_report_sample.json` / `.md` for a sample report
generated on `tests/fixtures/audit_pivot/`.

## 11. Audit the groupe dataset

`src/audit_groupe_dataset.py` mirrors `audit_pivot_dataset.py` for
`pivot_data/groupes` (`schema_groupe.py`): it scans a directory of group
profile `*.json` files and reports volumetry (effectifs, `cohesion_votes`,
`amendements_agreges` — global and per `type_deposant`), completeness
(`tags_thematiques_agreges`, groups with members but no cohesion votes),
consistency (`validate_profil_groupe`, `schema_version` divergence, roster
coverage gap with a coverage rate in %, duplicate `groupe_id`), source freshness and stale groups,
aggregated `meta.warnings[]`, and a per-groupe cross-tab of `membres` /
`cohesion_votes` / `tags_thematiques_agreges` / `amendements_agreges`
(global `nb_amendements`) counts — same internal-quality-tool contract as
the pivot audit (no score, no ranking, see `AGENTS.md` §2).

```bash
python src/audit_groupe_dataset.py \
    --input-dir pivot_data/groupes \
    --output-json audit_groupe_report.json \
    --output-md audit_groupe_report.md \
    --staleness-days 30
```

`--input-dir` defaults to `pivot_data/groupes`. `--output-json`/`--output-md`
default to unset (JSON prints to stdout, Markdown is skipped if `--output-md`
is omitted). `--staleness-days` (default 30) sets the threshold beyond which
a group with only stale sources is flagged — same option contract as
`audit_pivot_dataset.py` for combined use. See
`docs/examples/audit_groupe_report_sample.json` / `.md` for a sample report
generated on `tests/fixtures/audit_groupe/`.

## 12. Combined audit pipeline (manual tool)

`src/audit_pipeline.py` is a **manual** entry point that runs both audits
above by calling their functions directly (no subprocess) and compiles an
"overview" section on top of the two detailed reports: total profiles/groups
audited, aggregated read errors, and aggregated `meta.warnings[]` across both
document types. Pure composition of the reports produced by
`audit_pivot_dataset.py` / `audit_groupe_dataset.py` — no new business logic.

It is separate from `src/check_quality_gate.py` (the only CI-blocking gate)
and is **not** wired into `.github/workflows/generate-data.yml` — this was an
explicit decision (see issue #178): this tool is never invoked automatically
by CI.

```bash
python src/audit_pipeline.py \
    --profiles-dir pivot_data/profiles \
    --groupes-dir pivot_data/groupes \
    --output-json audit_pipeline_report.json \
    --output-md audit_pipeline_report.md \
    --staleness-days 30
```

`--profiles-dir`/`--groupes-dir` default to `pivot_data/profiles` /
`pivot_data/groupes`. `--output-json`/`--output-md` default to unset (JSON
prints to stdout, Markdown is skipped if `--output-md` is omitted).
`--staleness-days` (default 30) is forwarded unchanged to both underlying
audits.

## Raw profile content (Nos* format)

Each `raw_data/profiles/<slug>.json` includes:

- `identite`: name, political group, profession, constituency, ...
- `mandats`: base elected mandate + real responsibilities with role, dates,
  and `actif` flag
- `votes`: voting positions + source (`votes_source`), prioritizing official AN
  open data, with Nos* fallback
- `dossiers_legislatifs`: chamber legislative files
- `interventions`: speech records with date, topic, text, role at the time,
  and basic length-based format
- `mandat_europeen`: present only if a candidate has EP records
- `meta.warnings`: transparency on missing/incomplete source fetches
- `meta.synchro_sources`: ISO-8601 timestamp per source

## Pivot schema v1

Defined in `src/schema_pivot.py` and produced by `normalize_nosdeputes.py`
(and EU normalizers) to unify AN/Senate/EP representation.

With `--pivot`, `generate_all_profiles.py` writes `<slug>.pivot.json`:

```json
{
  "schema_version": "1",
  "id": "nosdeputes:jean-luc-melenchon",
  "nom": "Jean-Luc Melenchon",
  "chambre": "AN",
  "parti": null,
  "groupe": "La France Insoumise",
  "sources": [
    {"type": "nosdeputes", "url": "...", "synchro_le": "2026-07-29T..."},
    {"type": "assemblee_nationale", "url": "...", "synchro_le": "2026-07-29T..."}
  ],
  "mandats": [ ... ],
  "votes": [ ... ],
  "textes_portes": [ ... ],
  "amendements": [ ... ],
  "interventions": [ ... ],
  "tags_thematiques": ["budget", "fiscalite"],
  "meta": { "schema_version": "1", "genere_le": "...", "licence_donnees": "...", "warnings": [] }
}
```

Sensitive institutional constraints are documented in `AGENTS.md` and in
`docs/schema_donnees_transformations.md`.

## Source taxonomy

| Source | Type | Update cadence | License | Chamber(s) |
|---|---|---|---|---|
| NosDeputes.fr | JSON/XML API | Frozen on 16th legislature (all 618 cards have `mandat_fin`) | ODbL | AN |
| NosDeputes archives | JSON/XML API | Frozen closed legislatures | ODbL | AN |
| NosSenateurs archives | JSON/XML API | Frozen | ODbL | Senate |
| data.assemblee-nationale.fr | ZIP dumps | Daily | Open License | AN |
| Parltrack | LZMA dumps | Weekly (approx.) | CC0/ODbL | EP |
| French Wikipedia | MediaWiki REST API | Immediate | CC BY-SA 4.0 | Candidate monitoring |
| Wikidata | SPARQL | Immediate | CC0 | Candidate monitoring |

## Tests

```bash
pytest -q
```

## Coverage limits

- **Group scope**: profile generation (roster-driven or not) only covers the
  7 groups declared in `raw_data/groupes_reels.json` (5 AN + 2 Senate) — not
  every parliamentary group that exists. Extending coverage means adding
  entries to that file, a separate editorial decision.
- **Roster-driven candidate/member coverage**: `generate_roster_candidats.py`
  + `generate_all_profiles.py --candidats raw_data/roster_candidats.json`
  (see [`docs/technical_decisions.md#provenance-pivot`](docs/technical_decisions.md#provenance-pivot))
  aims for near-complete coverage of the ~750 roster members of the 7
  configured groups, but no full-scale run had landed in CI as of this
  writing — see
  [`docs/technical_decisions.md#seuil-couverture-groupe`](docs/technical_decisions.md#seuil-couverture-groupe)
  for the latest real coverage numbers. Until coverage is consistently
  near-100%, `web/UI_finale` shows an explicit "no data" state instead of a
  misleading zero (rule 5, `AGENTS.md`).
- **AN votes**: official open data for deputies (14th-17th legislatures,
  depending on available dumps).
- **Senate votes**: no equivalent official source integrated yet.
- **Freshness of `groupe`/`identite.groupe_sigle`**: derived from NosDeputes,
  currently frozen on pre-dissolution 2024 data.
- **Interventions**: full-text name search can be partial for ambiguous names.
- **Mayors**: no dedicated module/source.
- **Coverage bias**: former MPs usually have richer traces than non-MP profiles.
- **API docs**: `docs/nosdeputes_doc/` is reference material; some endpoints
  are deprecated/offline.

## Data freshness

Profiles expose `meta.synchro_sources`; pivots expose `sources[].synchro_le`.
For Parltrack, use:

```bash
python src/mep_profile.py --show-cache-date
```

## Editorial neutrality

This project aggregates factual records and primary sources. It does not
produce rankings, scores, or evaluative judgments of political positions.
See `AGENTS.md` for the full non-negotiable rule set.

## Thematic taxonomy roadmap

See `ROADMAP.md`.
