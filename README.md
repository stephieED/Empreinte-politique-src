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
|  |- gouvernement_profile.py        # Aggregate roster + legislative files into a full government profile
|  |- generate_gouvernement_profiles.py # Batch: all governments from raw_data/gouvernements_reels.json
|  |- parti_profile.py               # Editorial party aggregates from individual pivots
|  |- check_quality_gate.py          # Pre-commit quality gate + run summary (5 sections)
|  |- audit_pivot_dataset.py         # Pivot dataset audit: volumetry/completeness/consistency/freshness/warnings + JSON/Markdown report
|  |- audit_groupe_dataset.py        # Groupe dataset audit: same categories as audit_pivot_dataset.py + JSON/Markdown report
|  |- audit_gouvernement_dataset.py  # Gouvernement dataset audit: I/O + volumetry/completeness/consistency/freshness indicators (no CLI/Markdown yet, see #319)
|  |- audit_pipeline.py              # Manual tool: runs both audits above and compiles an overview + combined JSON/Markdown report
|  |- audit_integrite_referentielle.py # Pre-commit guard: every published key resolves in its shared index (#485)
|  |- schema_pivot.py                # Pivot schema v1 - common format across all sources
|  |- schema_groupe.py               # Group profile schema v1 (structure contract)
|  |- schema_parti.py                # Party profile schema v1
|  |- schema_gouvernement.py         # Government profile schema v1 (structure contract, no aggregation logic yet)
|  |- gouvernement_textes.py         # AN legislative files (bulk dump): government-origin filter + statut extraction
|  |- couverture_dossiers.py         # Ingested dossier archives (per legislature) + resulting coverage bound (stdlib only)
|  |- mep_profile.py                 # Collect/normalize EP profiles (Parltrack)
|  `- fetch_wikipedia_candidates.py  # Candidate monitoring via Wikipedia/Wikidata
|- raw_data/                          # Declarative inputs + raw outputs (non-normalized)
|  |- candidats.json                 # Candidate list (name, slug, party, status, sources)
|  |- groupes_reels.json             # Validated list of real groups to generate
|  |- gouvernements_reels.json       # Validated list of real governments (ministerial roster source)
|  `- profiles/                      # Raw candidate profiles: <slug>.json
|- pivot_data/                        # Anything in pivot schema format (or derived)
|  |- profiles/                      # <slug>.pivot.json per candidate
|  |- scrutins.json                  # Shared deduplicated ballot list (#432)
|  |- amendements/                   # Shared deduplicated amendment list, one file per legislature (#431)
|  |                                 #   <leg>.json (meta) + <leg>.cosignatures.json (companion)
|  |- partis/                        # parti-<slug>.json: editorial party aggregates
|  |- groupes/                       # groupe-<SIGLE>-<leg>.json: real parliamentary group profiles
|  `- gouvernements/                 # gouvernement-<ID>.json: real government profiles
|- web/
|  |- UI_finale/                     # Production interface: React 19 + Vite (Candidats · Groupes · Gouvernement)
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
|  |- test_gouvernement_textes.py
|  |- test_gouvernement_roster.py
|  |- test_gouvernement_profile.py
|  |- test_generate_gouvernement_profiles.py
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
pip install -r requirements-dev.txt
```

`requirements-dev.txt` pulls in `requirements.txt` (runtime dependencies) and
adds the pinned `pytest`. For a runtime-only environment, install
`requirements.txt` alone — that is what the extraction jobs do.

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

## 2 bis. Résolution de `legislature` sur les votes (#432)

`votes[].numero_scrutin` repart à 1 à chaque législature : la clé d'un scrutin
est `(legislature, numero_scrutin)`. Or 22,5 % des votes collectés ne portent
aucune législature (chemin de collecte antérieur à #403). Passe de corpus, sans
réseau, qui dit si la clé est utilisable — et ne modifie aucun fichier :

```bash
python3 src/audit_legislature_votes.py
python3 src/audit_legislature_votes.py --profils-dir pivot_data/profiles
python3 src/audit_legislature_votes.py --out audit/legislature_votes.md
```

Sortie 0 si tout est résolu, 1 sinon. Deux mécanismes, jamais confondus :
jointure sur un jumeau étiqueté (la donnée existe déjà ailleurs, étiquetée),
puis calendrier des législatures (une dérivation, tracée comme telle). Ce qu'ils
ne résolvent pas échoue bruyamment — jamais de valeur par défaut (AGENTS.md
§2.5). Rapport de référence : `audit/legislature_votes_20260819.md`.

## 2 ter. Index partagé des scrutins (#432)

Un scrutin est identique pour tous ses votants : seul `position` est propre au
membre. Son méta vit donc une seule fois dans `pivot_data/scrutins.json`, et un
profil ne garde que le mapping `{scrutin_id, position}`.

```bash
python3 src/build_scrutins_index.py                 # fusion additive avec l'existant
python3 src/build_scrutins_index.py --no-merge      # reconstruction complète (corpus COMPLET)
```

À construire **avant** toute passe pivot : `generate_all_profiles.py --pivot`
le fait automatiquement (`--scrutins`, `--skip-scrutins-index` pour ne pas le
refaire). Mesuré sur les 209 profils committés :

| | avant | après |
| --- | --- | --- |
| `votes[]` dans les profils | 179,8 Mo | 17,9 Mo |
| index partagé | — | 8,1 Mo |
| **total** | **179,8 Mo** | **26,0 Mo (−85,5 %)** |
| `cohesion_votes` des groupes | 6,23 Mo | 3,41 Mo (−45,3 %) |

Le même index sert les profils et les groupes : les 4 104 scrutins des groupes
sont tous inclus dans les 17 422 des profils. Un profil ne se lit plus seul pour
ses votes, et `sync-data.mjs` copie l'index dans `public/data/`.

## 2 quater. Index partagé des amendements (#431)

Même principe pour les amendements : seul `role_signataire` est propre au
membre, tout le reste — `sort`, `date`, `texte_vise`, `type_deposant`,
`premier_signataire` et surtout `co_signataires` — est identique pour tous les
signataires. Un profil ne garde que le mapping `{amendement_id, role_signataire}`,
avec `amendement_id = "an:<uid AN>"`.

```bash
python3 src/build_amendements_index_pivot.py               # fusion additive avec l'existant
python3 src/build_amendements_index_pivot.py --no-merge    # reconstruction complète (corpus COMPLET)
```

À ne pas confondre avec `build_amendements_index.py` (index **brut** des
archives AN, job CI `extract-amendements-an`) ni avec
`build_amendements_index_figees.py` (législatures closes, `raw_data/`).

`generate_all_profiles.py --pivot` reconstruit l'index automatiquement **après**
la passe pivot (`--amendements`, `--skip-amendements-index` pour ne pas le
refaire). Une seule reconstruction par run, là où les scrutins en demandent deux :
la clé d'un amendement est son `uid`, porté par l'enregistrement lui-même, donc
rien n'a besoin d'être résolu à l'échelle du corpus.

Mesuré sur les 209 profils committés :

| | avant | après |
| --- | --- | --- |
| `amendements[]` dans les profils | 1 342,4 Mo | 73,8 Mo de mapping |
| index partagé (méta) | — | 54,4 Mo |
| index partagé (cosignatures) | — | 75,7 Mo |
| **total** | **1 342,4 Mo** | **203,8 Mo (−84,8 %)** |

**Un fichier par législature**, plus un fichier compagnon pour les cosignatures :
un fichier global unique pèse déjà 130,1 Mo, au-delà de la limite GitHub de
100 Mo par blob, et un fichier de législature contenant aussi les cosignatures
atteindrait 120,3 Mo pour la XV<sup>e</sup> à couverture complète des archives.
Les cosignatures ne sont lues par aucun consommateur : `sync-data.mjs` ne les
copie pas vers le site, et `charger(..., avec_cosignatures=False)` les évite.
Elles ne sont jamais supprimées pour autant (#324).

### Vérifier que les clés publiées résolvent (#485)

Ces deux index font que `pivot_data/` n'est plus **auto-suffisant** : un vote ou
un amendement n'a de sens que si sa clé résout. Le contrôle qui le vérifie :

```bash
python3 src/audit_integrite_referentielle.py                    # tout pivot_data/
python3 src/audit_integrite_referentielle.py --sans-amendements # scrutins seuls, moins cher
python3 src/audit_integrite_referentielle.py --out audit/integrite.md --out-json audit/integrite.json
```

Sortie non nulle si une clé publiée ne résout pas, si l'index ou le shard visé
est absent, ou si une clé manque sans son enregistrement de repli — utilisable
comme garde-fou avant commit, et branché comme tel dans `merge-and-pivot`.

À ne pas confondre avec `audit_diff_profils.py`, qui compare **deux états** :
celui-ci vérifie une **invariance dans un seul**. Leurs tolérances sont
cloisonnées — `allow_declared_losses` ne désarme pas
`allow_broken_references`. Mesuré sur les 209 profils committés : 0
référence orpheline sur 1 347 451, 3,02 s / 162,0 Mio. Voir
`docs/technical_decisions.md#integrite-referentielle-pivot`.

## 3. Generate all candidate profiles (batch)

```bash
python src/generate_all_profiles.py
python src/generate_all_profiles.py --only jean-luc-melenchon
python src/generate_all_profiles.py --max-pages 5
python src/generate_all_profiles.py --skip-existing
python src/generate_all_profiles.py --refresh-existing --no-merge  # l'inverse : ne régénère QUE l'existant (#445)
python src/generate_all_profiles.py --pivot
python src/generate_all_profiles.py --skip-ue
python src/generate_all_profiles.py --workers 8
python src/generate_all_profiles.py --out-dir /tmp/profiles
python src/generate_all_profiles.py --pivot-dir /tmp/pivots
python src/generate_all_profiles.py --limit 20    # premiers N candidats (déploiement progressif)
python src/generate_all_profiles.py --sample 20   # échantillon aléatoire de N candidats
python src/generate_all_profiles.py --manifest-out _manifest/profils-ecrits.txt  # cf. ci-dessous (#450)
```

`--manifest-out` consigne, une ligne par nom de fichier, les profils bruts que
CE run a réellement écrits — ni ceux qu'il a sautés, ni ceux qui étaient déjà
dans `--out-dir`. C'est ce qui permet à un job d'extraction CI de ne publier que
sa propre contribution : `raw_data/profiles/` contient aussi la baseline
committée déposée par son `actions/checkout`, et la republier réinjectait des
données périmées à la fusion (#450, voir
[`docs/technical_decisions.md#publication-scopee-artifacts`](docs/technical_decisions.md#publication-scopee-artifacts)).
Le fichier est écrit au fil de l'eau et tronqué au démarrage : il décrit une
exécution, pas un répertoire.

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
carries the precise ministerial title, sourced from the `MINISTERE` mandates of
the same AMO30 bulk dataset (#398) — a minister who changes portfolio mid-government
yields one `membres[]` entry per period, never an arbitrary pick. It stays `null`
when no such mandate overlaps. `build_premier_ministre` derives `premier_ministre`
from the same material (a member of *this* government whose `MINISTERE` mandate is
labelled "Premier ministre"), and returns `null` — never a value inferred from the
government's name — when no local pivot carries it. Produces only the roster and
that entry, not a full
`pivot_data/gouvernements/*.json` profile (`schema_gouvernement.py`) — see
`gouvernement_profile.py` below for that combination with sponsored texts.

```bash
python src/gouvernement_roster.py \
    --config raw_data/gouvernements_reels.json \
    --gouvernement-id "gouvernement:BAYROU" \
    --profiles-dir pivot_data/profiles
```

### Government profile

`gouvernement_profile.py` combines `gouvernement_roster.py`'s ministerial
composition and `gouvernement_textes.py`'s legislative files into a full
government profile (`schema_gouvernement.py`), written to
`pivot_data/gouvernements/<id>.json`. A text is attached to a government by
overlap of its `date_depot` with the government's `periode` (never by its
final-status date — a text initiated under government A stays credited to A
even if concluded under government B). A text whose `statut` or
`chambre_depot_initial` can't be determined is excluded from `textes[]` (never
a guessed default), with a warning kept in `meta.warnings`; `comptages.par_statut`
is a raw count of the retained texts only — no rate is ever computed (see
[`docs/technical_decisions.md#gouvernement-profile-rattachement`](docs/technical_decisions.md#gouvernement-profile-rattachement)).

```bash
python src/gouvernement_profile.py \
    --config raw_data/gouvernements_reels.json \
    --gouvernement-id "gouvernement:BAYROU" \
    --profiles-dir pivot_data/profiles \
    --out pivot_data/gouvernements/gouvernement-BAYROU.json \
    --validate
```

`generate_gouvernement_profiles.py` generates every government listed in
`raw_data/gouvernements_reels.json` in a single run, fetching the legislative
files dump and loading the local pivot profiles only once, shared across all
governments (mirrors `generate_group_profiles.py`'s single roster fetch per
`(chambre, legislature)`).

```bash
python src/generate_gouvernement_profiles.py \
    --config raw_data/gouvernements_reels.json \
    --profiles-dir pivot_data/profiles \
    --out-dir pivot_data/gouvernements \
    --validate
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
`.cache/amendements_an/`; `--stall-cycles` / `--stall-wait-seconds` widen the
wait when the source serves nothing at all — offline, waiting is the only
remedy that works, see
`docs/technical_decisions.md#telechargement-an-trois-modes-defaillance`) and
committed under `raw_data/amendements_an_figes/`
— the script deduplicates the raw per-signataire index into
`amendements.json` + a slim `index_par_acteur.json` before writing, since the
undeduplicated form is multiple GB uncompressed (measured on legislature 16)
and can't be committed. `candidate_profile.py` reads that fallback (expanding
it back to the standard flat shape) instead of hitting the network for those
two — see `docs/technical_decisions.md#amendements-legislatures-figees`.

Nominal votes follow the same shape since #403. `fetch_votes_officiels()`
aggregates **all four AN legislatures** (14 to 17, `AN_SCRUTINS_LEGISLATURES`)
instead of the single one previously derived from the NosDéputés domain, which
froze every profile on legislature 16 and stopped the dataset in June 2024.
Legislatures 14/15/16 are closed: their index is built offline via
`src/build_scrutins_index_figes.py --legislature {14,15,16}` (or `--toutes`)
and committed under `raw_data/scrutins_an_figes/` (2.8 MB gzipped total), so CI
only downloads the active 17th (26 MB). Both the on-disk cache and the
committed fallback store the deduplicated form — scrutin metadata once in
`scrutins.json`, one `[uid, position]` reference per voter, sharded per
`acteurRef` — which keeps the four legislatures at 68 MB instead of 741 MB
flat. See `docs/technical_decisions.md#votes-multi-legislature`.

The merge stage runs `src/check_quality_gate.py`; commit/push occurs only if
the gate exits with code 0. Before that step, the `merge-and-pivot` job also
downloads the `amendements-index-an` artifact into `.cache/amendements_an`
(optional, `continue-on-error: true`, same cache-only pattern as `extract-an`/
`extract-roster-groupes`) so the gate's amendements freshness section (3d) can
read the real `fraicheur.json` indicators instead of always reporting "never
built".

`merge-and-pivot` also runs `src/generate_gouvernement_profiles.py --validate`
right after the groupe step, on the same model, writing `pivot_data/gouvernements/`
(included in the automatic commit alongside `pivot_data/groupes`) — see
`docs/technical_decisions.md#gouvernement-ci-integration` for the timeout
budget measurement (no dedicated job needed, unlike the AN extraction jobs).

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

`--gouvernements-dir` (default `pivot_data/gouvernements`) / `--gouvernements-config`
(default `raw_data/gouvernements_reels.json`) drive section 5 (gouvernements), mirroring
`--groupes-dir`/`--groupes-config` for section 4 — hard fail on missing/invalid file or
schema, soft fail on incomplete portefeuille (ministerial portfolio) coverage, empty
`textes[]` with a non-null `periode`, or IncompleteRead network signals.

## 9. Running the full pipeline locally instead of CI

`scripts/generate_data_local.sh` runs the same sequence of stages as
`generate-data.yml` (AN, Sénat, UE, ParlTrack, amendements index,
roster-driven group members, then pivots + party/group/government profiles +
quality gate) directly on your machine, bypassing GitHub Actions entirely.
Useful when the hosted runner is hitting transient infrastructure
preemptions ("shutdown signal", see `docs/technical_decisions.md`) unrelated
to the code itself — running locally sidesteps that class of failure
completely, since it doesn't depend on GitHub's runner fleet at all.

```bash
./scripts/generate_data_local.sh
```

By default it launches itself in the background (`nohup`) and returns
immediately, printing the PID and the log file to follow:

```
Lancement en arrière-plan — logs : logs/generate_data_local_20260817T104701Z.log
PID : 12345
Suivre : tail -f logs/generate_data_local_20260817T104701Z.log
Arrêter : kill 12345
```

Every run's full output is saved under `logs/` (git-ignored, like `.cache/`),
regardless of foreground/background mode. Run `BACKGROUND=false
./scripts/generate_data_local.sh` to keep it attached to the terminal
instead (output is still duplicated into the same log file via `tee`).

Same tunables as the workflow's `workflow_dispatch` inputs, passed as
environment variables:

```bash
WORKERS=4 ROSTER_EXTRACTION_LIMIT=0 EXTRACT_INTERVENTIONS=true ./scripts/generate_data_local.sh
```

| Variable | Default | Same as `workflow_dispatch` input |
|---|---|---|
| `FRESH_RUN` | `false` | `cold_start` |
| `THRESHOLD` | `3` | `threshold` |
| `WORKERS` | `1` (sequential) | `workers` |
| `EXTRACT_INTERVENTIONS` | `false` | `collect_interventions` |
| `MAX_PAGES` | `5` | `max_pages` |
| `ROSTER_EXTRACTION_LIMIT` | `20` | `roster_limit` |
| `BACKGROUND` | `true` | *(local-only, no CI equivalent)* |

Each stage keeps the CI job's `continue-on-error` behavior: a failure in one
source (e.g. ParlTrack down) doesn't stop the rest. Unlike CI, nothing is
committed/pushed automatically at the end — review `git status`/`git diff`
on `raw_data/profiles`, `pivot_data/profiles`, `pivot_data/partis`,
`pivot_data/groupes`, `pivot_data/gouvernements`, then commit/push manually
if the result looks right. See the script's header comment for the exact
differences from the CI job graph (no per-candidate matrix, no
artifact-based re-merge — both are CI-only orchestration concerns with no
local equivalent needed).

## 10. Open the web UI locally

`web/UI_finale/` is the production interface (React 19 + Vite, **Candidats** · **Groupes** ·
**Gouvernement**, no Partis tab). Before running it, sync pivot data into `public/data/`:

```bash
cd web/UI_finale
npm install          # first time only
npm run dev          # syncs data then starts Vite dev server
```

`scripts/sync-data.mjs` copies `pivot_data/profiles/`, `pivot_data/groupes/`,
`pivot_data/gouvernements/` and `raw_data/candidats.json` into `public/data/` (generated,
git-ignored) and writes `public/data/manifest.json`. Coverage is limited to the
candidates/groups/governments with a local pivot file — see "Coverage limits" below for the
current state of the roster-driven rollout.

Archived design generations are in `web/old/` (v1–v7, atlas, interface-essentielle,
studies) — static HTML, serve with `python -m http.server 8000` from the repo root.

## 11. Audit the pivot dataset

`src/audit_pivot_dataset.py` scans a directory of `*.pivot.json` files and reports
volumetry (including a breakdown by `meta.provenance`, `candidat_declare` vs.
`roster_groupe`), completeness, consistency, source freshness, aggregated
`meta.warnings[]` indicators, and two per-candidate cross-tabs of `votes` /
`textes_portes` / `amendements` / `interventions`: counts, and date range
(min/max, `textes_portes` aggregating `date_min`/`date_max` across entries;
unparseable dates are ignored and tallied per field, never silently
defaulted). Both cross-tabs list **declared candidates only**
(`meta.provenance` = `candidat_declare`); roster-sourced profiles
(`roster_groupe`) appear aggregated per `groupe` (min/max/median/mean for
counts, enclosing range for dates), never member by member — an internal
quality tool, not an end-user report (no score, no ranking, see
`AGENTS.md` §2).

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

Instead of naming both files, `--output-dir DOSSIER` writes both under a
timestamped name (`audit_pivot_<horodatage-UTC>.json`/`.md`) — incompatible
with `--output-json`/`--output-md`:

```bash
python src/audit_pivot_dataset.py --input-dir pivot_data/profiles --output-dir audit_reports/
```

## 12. Audit the groupe dataset

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
`audit_pivot_dataset.py` for combined use, including `--output-dir DOSSIER`
(timestamped `audit_groupe_<horodatage-UTC>.json`/`.md`). See
`docs/examples/audit_groupe_report_sample.json` / `.md` for a sample report
generated on `tests/fixtures/audit_groupe/`.

## 13. Audit the gouvernement dataset

`src/audit_gouvernement_dataset.py` mirrors `audit_groupe_dataset.py` for
`pivot_data/gouvernements` (`schema_gouvernement.py`): it scans a directory
of `gouvernement-*.json` files and reports volumetry (`periode.actif`
breakdown, `membres`/`textes` distribution, `comptages.par_statut`
aggregated across governments), completeness (`premier_ministre`,
`membres[].portefeuille`, `meta`), consistency
(`validate_profil_gouvernement` — already covers the 49.3 non-collapse
invariant, `schema_version` divergence, duplicate `gouvernement_id`), source
freshness and stale governments, source coverage of carried texts
(`compute_couverture_textes`, #399: classifies each government against the
legislature archives actually ingested — `src/couverture_dossiers.py` — so
that "outside the source's coverage" is never read as "really zero"; the
coverage bound is printed in the report header, and `nb_textes` stays `null`
when the `textes` field is absent, never rendered as `0`), and a
per-government cross-tab of date ranges (`compute_plage_dates_gouvernements`): min/max of
`membres[].debut`/`.fin` (`mandats_membres`) and `textes[].date_depot`/
`.date_dernier_evenement` (`textes`) — a `membres[].fin = null` (ongoing
mandate) is excluded from the max without ever being substituted by today's
date (`AGENTS.md` §2.5). Also aggregates `meta.warnings[]` by type
(`compute_agregation_warnings`, same contract as `audit_groupe_dataset.py`,
added for #321 so `audit_pipeline.py`'s compiled overview can report
government warnings alongside profiles/groups). Same internal-quality-tool
contract as the other audits (no score, no ranking, see `AGENTS.md` §2).

```bash
python src/audit_gouvernement_dataset.py \
    --input-dir pivot_data/gouvernements \
    --output-json audit_gouvernement_report.json \
    --output-md audit_gouvernement_report.md \
    --staleness-days 30
```

`--input-dir` defaults to `pivot_data/gouvernements`. `--output-json`/
`--output-md` default to unset (JSON prints to stdout, Markdown is skipped
if `--output-md` is omitted). `--staleness-days` (default 30) sets the
threshold beyond which a government with only stale sources is flagged —
same option contract as the other audit scripts, including `--output-dir
DOSSIER` (timestamped `audit_gouvernement_<horodatage-UTC>.json`/`.md`). See
`docs/examples/audit_gouvernement_report_sample.json` / `.md` for a sample
report generated on `tests/fixtures/audit_gouvernement/`.

## 14. Combined audit pipeline (manual tool)

`src/audit_pipeline.py` is a **manual** entry point that runs all three audits
above by calling their functions directly (no subprocess) and compiles an
"overview" section on top of the three detailed reports: total
profiles/groups/governments audited, aggregated read errors, and aggregated
`meta.warnings[]` across all three document types. Pure composition of the
reports produced by `audit_pivot_dataset.py` / `audit_groupe_dataset.py` /
`audit_gouvernement_dataset.py` — no new business logic (issue #321,
sub-issue 5/6 of #316, extends the profiles+groups compilation from #178 to
governments).

It is separate from `src/check_quality_gate.py` (the only CI-blocking gate)
and is **not** wired into `.github/workflows/generate-data.yml` — this was an
explicit decision (see issue #178): this tool is never invoked automatically
by CI.

```bash
python src/audit_pipeline.py \
    --profiles-dir pivot_data/profiles \
    --groupes-dir pivot_data/groupes \
    --gouvernements-dir pivot_data/gouvernements \
    --output-json audit_pipeline_report.json \
    --output-md audit_pipeline_report.md \
    --staleness-days 30
```

`--profiles-dir`/`--groupes-dir`/`--gouvernements-dir` default to
`pivot_data/profiles` / `pivot_data/groupes` / `pivot_data/gouvernements`.
`--output-json`/`--output-md` default to unset (JSON prints to stdout,
Markdown is skipped if `--output-md` is omitted). `--staleness-days` (default
30) is forwarded unchanged to all three underlying audits. A missing
directory (any of the three) is a hard error (explicit message + exit code
1, never a crash traceback), same behavior across all three. Same
`--output-dir DOSSIER` convenience as the other audit scripts (timestamped
`audit_pipeline_<horodatage-UTC>.json`/`.md`, incompatible with
`--output-json`/`--output-md`).

## Raw profile content (Nos* format)

Each `raw_data/profiles/<slug>.json` includes:

- `identite`: name, political group, profession, constituency, ...
- `mandats`: base elected mandate + real responsibilities with role, dates,
  and `actif` flag
- `votes`: voting positions + source (`votes_source`, listing **every** covered
  legislature), prioritizing official AN open data, with Nos* fallback. Each vote
  carries its own `legislature` and `url_source` (the AN scrutin page), since a
  profile now spans several legislatures
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
  "id": "jean-luc-melenchon",  // = le slug, sans prefixe de provenance (#487)
  "nom": "Jean-Luc Melenchon",
  "chambre": "AN",
  "parti": null,
  "groupe": "La France Insoumise",
  "sources": [
    {"type": "nosdeputes", "url": "...", "synchro_le": "2026-07-29T..."},
    {"type": "assemblee_nationale", "url": "...", "synchro_le": "2026-07-29T..."}
  ],
  "mandats": [ ... ],          // categorie ∈ mandat_electif | commission |
                               // commission_enquete | mission_information |
                               // groupe_etudes | delegation | groupe_amitie |
                               // groupe_politique | extra_parlementaire |
                               // fonction_gouvernementale | autre
                               // (schema_pivot.KNOWN_CATEGORIES)
  "votes": [ ... ],
  "textes_portes": [ ... ],
  "amendements": [ ... ],
  "interventions": [ ... ],
  "tags_thematiques": ["budget", "fiscalite"],
  "meta": { "schema_version": "1", "genere_le": "...", "licence_donnees": "...", "warnings": [] }
}
```

Sensitive institutional constraints are documented in `AGENTS.md`.

## Source taxonomy

| Source | Type | Update cadence | License | Chamber(s) |
|---|---|---|---|---|
| NosDeputes.fr | JSON/XML API | Frozen on 16th legislature (all 618 cards have `mandat_fin`) | ODbL v1.0 | AN |
| NosDeputes archives | JSON/XML API | Frozen closed legislatures | ODbL v1.0 | AN |
| NosSenateurs archives | JSON/XML API | Frozen | ODbL v1.0 | Senate |
| data.assemblee-nationale.fr / questions.assemblee-nationale.fr | ZIP dumps | Daily | Licence Ouverte / Open Licence (Etalab) | AN |
| Parltrack | LZMA dumps | Weekly (approx.) | ODbL v1.0 | EP |
| European Parliament (data.europarl.europa.eu, www.europarl.europa.eu) | REST API + MEP pages | Live (fetched per run, no weekly cache) | EP Legal Notice (reuse policy, attribution-based) | EP |
| French Wikipedia | MediaWiki REST API | Immediate | CC BY-SA 4.0 | Candidate monitoring |
| Wikidata | SPARQL | Immediate | CC0 1.0 | Candidate monitoring |

## Tests

```bash
pytest -q
```

The full suite runs in ~11 s (24 s for the whole CI job, checkout included),
executed by `.github/workflows/tests.yml` on every pull request and on every
push to `main`; the job fails if any test fails.

The suite is **decoupled from the living corpus**: no test reads `pivot_data/`
or `raw_data/profiles/`, none writes anywhere under `pivot_data/` or
`raw_data/`, and none makes an external network call (#473). The CI job enforces
this structurally — it sparse-checks-out only what the suite actually reads, so
the corpus is not on disk at all. A test that re-couples to it fails there with
a `FileNotFoundError` naming the path. Acceptance tests that need real profiles
use the frozen fixtures under `tests/fixtures/`. Rationale:
`docs/technical_decisions.md#ci-tests-pytest`.

## Coverage limits

- **Group scope**: profile generation (roster-driven or not) only covers the
  7 groups declared in `raw_data/groupes_reels.json` (5 AN + 2 Senate) — not
  every parliamentary group that exists. Extending coverage means adding
  entries to that file, a separate editorial decision.
- **Government scope**: profile generation only covers the governments
  declared in `raw_data/gouvernements_reels.json` (10 as of this writing,
  Fillon II through Lecornu II) — not every government in the Fifth
  Republic. `membres[].portefeuille` and `premier_ministre` are filled from the
  AN `MINISTERE` mandates when a member has a local pivot carrying one (24/41
  members and 3/10 governments as of this writing), and stay `null` otherwise —
  never a placeholder like "Ministre" nor a name inferred from the government's
  own label; the 7 remaining Prime Ministers simply have no local pivot, a figure
  that grows mechanically with the full-scale roster rollout. `textes[]` can be empty
  for a recent government; `web/UI_finale` shows an explicit "no data" state
  in both cases (rule 5, `AGENTS.md`).
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
