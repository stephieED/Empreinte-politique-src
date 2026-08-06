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
|  |- generate_all_profiles.py       # Batch: profiles for ALL candidates in candidats.json
|  |- group_profile.py               # Aggregate individual profiles into a parliamentary group profile
|  |- group_roster.py                # Fetch real group composition (NosDeputes/NosSenateurs)
|  |- generate_group_profiles.py     # Batch: all groups from raw_data/groupes_reels.json
|  |- check_quality_gate.py          # Pre-commit quality gate + run summary (4 sections)
|  |- schema_pivot.py                # Pivot schema v1 - common format across all sources
|  |- schema_groupe.py               # Group profile schema v1 (structure contract)
|  |- normalize_nosdeputes.py        # NosDeputes/NosSenateurs -> pivot adapter
|  |- normalize_europarl.py          # European Parliament Open Data -> pivot adapter
|  |- mep_profile.py                 # Collect/normalize EP profiles (Parltrack)
|  `- fetch_wikipedia_candidates.py  # Candidate monitoring via Wikipedia/Wikidata
|- raw_data/                          # Declarative inputs + raw outputs (non-normalized)
|  |- candidats.json                 # Candidate list (name, slug, party, status, sources)
|  |- groupes_reels.json             # Validated list of real groups to generate
|  `- profiles/                      # Raw candidate profiles: <slug>.json
|- pivot_data/                        # Anything in pivot schema format (or derived)
|  |- profiles/                      # <slug>.pivot.json per candidate
|  |- partis/                        # parti-<slug>.json: editorial party aggregates
|  `- groupes/                       # groupe-<SIGLE>-<leg>.json: real parliamentary group profiles
|- web/
|  `- index.html                     # Dynamic web page
|- docs/
|  |- nosdeputes_doc/                # NosDeputes/NosSenateurs API reference (kept in French)
|  `- an_opendata.md                 # Notes on AN open data (votes, amendments)
|- tests/
|  |- test_candidate_profile.py
|  |- test_candidate_profile_ue.py
|  |- test_group_profile.py
|  |- test_group_roster.py
|  |- test_generate_group_profiles.py
|  |- test_normalize_europarl.py
|  |- test_normalize_nosdeputes.py
|  |- test_schema_groupe.py
|  `- test_schema_pivot.py
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
- `docs/extract-syceron.md` - Phase 0 report on AN Syceron XML structure and pivot mapping.
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
```

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
but is not displayed as a top-level tab in `web/v3/`.

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

The merge stage runs `src/check_quality_gate.py`; commit/push occurs only if
the gate exits with code 0.

To run the gate locally:

```bash
python src/check_quality_gate.py
python src/check_quality_gate.py --threshold 0          # zero tolerance
python src/check_quality_gate.py --low-interventions 5  # stricter signal
```

## 9. Open the web UI locally

Serve with a local HTTP server (needed because `fetch()` cannot read `file://`):

```bash
python -m http.server 8000
```

Then open <http://localhost:8000/web/>.

- `web/v1/`, `web/v2/`: older design generations
- `web/v3/`: editorial reference — **Candidats** · **Groupes** (real parliamentary groups); excluded texts accessible via toggle
- `web/atlas-augmente/`: atlas powered by real profiles
- `web/scene-cinetique/`, `web/interface-essentielle/`: studies reused in V3
- `web/matiere-politique/`, `web/revue-civique/`, `web/moodboard/`: intermediate studies

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
