# AGENTS.md - Instructions for AI agents

Non-negotiable rules, schema conventions, validation constraints for every session.
"Why" behind each decision: **one file per decision** under `docs/decisions/`,
indexed newest-first by `docs/technical_decisions.md`. Write a new one, never
edit that index in place — see Section 8.
Every command the owner may have to type: `docs/commandes.md`.
Front door, editorial line, coverage limits: `README.md`.

---

## 1. Product

**Empreinte politique** — "Politics made clear". Factual, sourced political CVs
(mandates, votes, texts, interventions) for 2027 presidential candidates.
`CONTRECHAMP` (`web/`) is the interface design lab. `web/UI_finale` (React 19 + Vite) is
the current production interface, wired to real pivot data (`docs/decisions/web-v3-ui.md`). Earlier design
generations — `v1`-`v7`, including the `v3` editorial reference — are archived under `web/old/`.
`web/UI_finale` navigation: **Candidats** · **Groupes** (real parliamentary groups) ·
**Gouvernement** (real governments) — no Partis tab.
Positioning, naming, target audience: `docs/decisions/direction-artistique-empreinte.md`.

## 2. Non-negotiable editorial rules

Duplicated in `schema_pivot.py`, `validate_profil()`, and `web/old/v3/methodologie.html`.
Any schema/display change must preserve them:

1. No value judgments, no score, no ranking.
2. Full traceability: every fact must map to a primary source.
3. No individual attendance rate is ever published.
4. A 49.3 procedure is never treated as a vote position (separate procedural fact).
5. Missing data means missing data, never default `0`.
6. `position_dans_hemicycle` always requires a verifiable `source_url` (enforced by `validate_profil()`).
7. Group ratios published only with numerator + denominator + sufficient coverage; otherwise `N/D`.
   **An individual index measured against a group average** — cohesion rate, participation rate —
   is **internal quality control** only, never public (`--rapport-interne`). **Juxtaposing, on one
   sourced ballot, a member's position and their group's majority position is a fact, and is
   publishable** — never counted, never rated, never turned into a frequency: « a voté contre son
   groupe 47 fois » is that same individual index by another route.
8. Thematic tags are reading aids, not declared candidate positions.

## 3. Pipeline

Three files carry what this section deliberately does not. **Why** a rule
exists: one file per decision under `docs/decisions/`, indexed by
`docs/technical_decisions.md`. **What the data becomes** — flow, files, schemas,
volumetry: `docs/data-architecture.md` — the six outputs of `pivot_data/`,
rewritten from the code on 30/08/2026 (#606). **What a run does** — the eight
jobs, caches, artifacts, budgets, the launch form, the push, the automatic
retry: `docs/workflow-generate-data.md`. **The rules stay here**, because a rule
behind a link is a rule that gets missed.

Public sources → `raw_data/profiles/<slug>.json` + per-legislature amendment
slices → `pivot_data/profiles/<slug>.pivot.json` → groupes / partis /
gouvernements → `check_quality_gate.py`, which gates every commit. `raw_data/` is
source-near; `pivot_data/` is the only layer `web/` reads.

**`pivot_data/profiles/` holds two populations, and nothing on disk says so
(#630).** 481 files, one directory, one naming pattern — a `glob` returns 481.
`meta.provenance == "candidat_declare"` marks the **13** declared candidates,
the ones `web/` publishes a page for; `meta.provenance == "roster_groupe"` marks
the **468** group members, collected **to feed the group and government
aggregates** — `group_profile.py` never reads their `identite` block, it
consumes `nom`, `mandats`, `votes`, `interventions`, `amendements`, all lists.
**What differs is the use, not the standard**: an identity **merge** fix covers
13 profiles, an identity **quality** fix covers 481 (#556's 191 HATVP markers
were in the roster). Name the population before you quote a figure — and the
tools now do it for you: every profile count they print carries its breakdown,
via `src/population_profils.py`.
→ `docs/decisions/populations-profils-portees-par-les-outils-630.md`

### 3a. Files, indexes, merge

- **Build `pivot_data/scrutins.json` before any pivot pass, and merge it additively.**
  Resolving a ballot's `legislature` is a corpus-wide join, never per-profile.
  → `docs/decisions/normalisation-votes.md`
- **Build `pivot_data/amendements/<legislature>.json` after the pivot pass, once, and
  merge it additively** — with `build_amendements_index_pivot.py`, not
  `build_amendements_index.py` (the raw AN index). `amendement_id` is `an:<uid AN>` and
  the legislature is read **inside** the uid, never derived from the date. Co-signatures
  live in a companion file and are **never deleted**: no consumer reads them, a
  co-signature network is analysis material (#324).
  → `docs/decisions/normalisation-amendements.md`
- **A `texte_vise` is the AN document's uid, never its label (#639).** The collection
  used to overwrite the sourced code with the dossier title *before writing the raw
  profile*: 293 582 of 484 132 published amendments carry no key because of it. Each
  index file carries an optional `textes` table (`texte_vise` → `{dossier_id, titre}`),
  filled uid-to-uid from `document.dossierRef` — never by matching a label, not even an
  exact one. A texte with no resolved dossier has **no entry**, and the count is printed.
  → `docs/decisions/dossier-des-amendements-639.md`
- **Both shared indexes must be in the workflow's `git add`.** They are the only
  cross-file dependencies inside `pivot_data/`; an uncommitted index leaves every mapping
  pointing at nothing, silently.
- **Individual profiles are written compact, everything else `indent=2`** (`src/json_io.py`).
  Never read a profile line by line — the format carries no meaning.
  → `docs/decisions/profils-json-compact.md`
- **A tool that walks the corpus reads it by projection, and never keeps a document
  (#628).** 623 Mo of JSON on disk is ~2,6 Gio of Python objects (measured inflation:
  × 4,2), and the machine has 4 Gio free with the swap full — an accumulating loop is
  `exit 137`, not a slowdown. Read one profile, reduce it to the blocks your measures
  actually open (declare them in a whitelist), release it. **A ceiling that is not in a
  test is a ceiling nobody re-checks**: measure `ru_maxrss` in a subprocess over fixtures
  and derive the ceiling from the on-disk weight of the blocks you must not keep — never
  from what you observed. Three accumulations remain, named and measured in the decision.
  → `docs/decisions/audit-599-projection-blocs-lus-628.md`
- **Read raw profiles through `src/profil_brut.py`, never `json.load` directly (#580)** —
  a raw profile is a socle plus one amendment slice per legislature, and a broken
  partition must raise `PartitionIllisible`, never return an empty list.
  → `docs/decisions/partition-profils-legislature-580.md`
- **The biggest versioned file is a watched guard-rail with a written course of action
  (#580).** `src/garde_fou_blobs.py` is **§7 of `check_quality_gate.py`**: warn at
  50 MiB, **fail the commit at 80 MiB**. Neither "raise the threshold" nor "delete data"
  is an available remedy.
  → `docs/decisions/partition-profils-legislature-580.md#garde-fou-blob-580`
- **Additive merge (`merge_profile.py`): regeneration never removes collected data.**
  `votes`/`mandats`/`interventions` additive, old entry wins; `amendements`/
  `textes_portes` new entry wins, keyed on `amendement_id` / `dossier_id`, or on the
  `amendement_non_resolu` record — keying on the mapping alone collapses every unresolved
  entry into one. Scalars take the new value only if populated, and **never regress to
  `null`**.
  → `docs/decisions/collecte-vide-necrase-jamais.md`
- **A field added to the schema never reaches an already-collected entry on its own —
  and the fix is a named backfill, never a looser merge (#492, #639, #641).** Twice on a
  list (`mandats[].chambre`, then `votes[]`'s `type_scrutin`/`type_vote`/`demandeur`):
  "old entry wins" and the key does not contain the new field, so the regenerated entry is
  discarded every run. Once on a scalar (`identite.profession`): "never regress to `null`"
  restores the very value the publication filter refuses, so **a publication filter runs
  on the COMPOSED block, after the merge, never on what the normaliser produced**. Both
  reports are strictly monotone — they fill only what is absent, they name their fields,
  and **they never touch the merge key**: widening it to carry the new field is #668's
  defect (468 duplicates on 940 entries). Each of the three passed the whole suite: the
  test that was missing covered the **transition**, not the steps.
  → `docs/decisions/qualification-perdue-a-la-fusion-639.md`,
  `docs/decisions/filtre-publication-apres-fusion-641.md`
- **A merge key written `a or b` changes identity the day `a` fills in (#668).** #540 was
  a *sticky* key absorbing distinct entries; this is its mirror — the same dossier keyed
  on the fallback before the run and on `source_url` after, published twice (940 entries
  for 472 collected dossiers, 468 duplicates, 22 profiles, live). **An identifier, never a
  URL** (`dossier_id`, the raw stage's own `dossiers_legislatifs[].id`), and the residual
  `or` is neutralised by a **reprise**, not by the key: `clean_stale_textes_portes` drops
  an entry with no identifier only when an identified twin carries the same fallback.
  Dropping the `or` outright would collapse un-identified entries onto one `None` key
  (#432). **Before adding an `a or b` key, measure how much of the published corpus sits
  on each branch** — and a reprise nobody calls cleans nothing: this one was dead code for
  a whole remediation.
  → `docs/decisions/cle-fusion-textes-portes-668.md`
- **An empty collection never overwrites a non-empty one (#465)** — per field, not per
  profile, even under `--no-merge`. Lifted only by `--autoriser-collecte-vide`, and the
  preservation is always printed. "Zero observed" is not "collection failed" (§2 rule 5).
  → `docs/decisions/collecte-vide-necrase-jamais.md`

### 3b. CI: jobs, caches, artifacts

- **No test may read `pivot_data/` or `raw_data/profiles/`, write anywhere under
  `pivot_data/`/`raw_data/`, or hit the network (#473).** Acceptance tests use frozen
  fixtures; `tests/conftest.py` cuts `requests.Session.send` and fails loudly, naming the
  URL. **Loopback stays open** — the criterion is leaving the machine, not speaking HTTP.
  Watch CLI/function **defaults** pointing into the repo. Test-only deps go in
  `requirements-dev.txt`.
  → `docs/decisions/ci-tests-pytest.md`
- **A test reading a file outside `tests.yml`'s sparse-checkout passes locally and fails
  in CI** — #434, then #518 twice. Whitelisting the file is half of it; the other half is
  `tests/test_ci_perimetre_sparse_checkout.py`, which fails **locally** on an uncovered
  path literal and checks the reverse too. **A top-level file counts as much as a
  directory.** When it slips through anyway (three times now: #434, #520, `CLAUDE.md` on
  30/08/2026), the `pytest_runtest_makereport` hook of `tests/conftest.py` names the cause
  in the CI log — it diagnoses, it does not prevent, and it stays silent on any other
  failure. It is locked by `tests/test_hook_diagnostic_sparse_checkout.py`, which drives
  it without failing anything: **a diagnostic that goes mute without saying so is worse
  than none.** The block itself is parsed in **one** place, `tests/_outils_ci.py` — a
  conftest cannot import a test module, so the shared parser lives beside it, unparsed by
  pytest and imported by path.
  → `docs/decisions/point-de-sauvegarde-dans-les-profils-518.md`,
  `docs/decisions/hook-diagnostic-sparse-checkout.md`
- **The launch form is two disjoint axes plus the cache (#578).** `existing_profiles`
  decides what happens to profiles already written (`overwrite` alone raises
  `--no-merge`); `add_uncovered_members` decides whether members with no profile get one;
  `cold_start` says nothing about how profiles are written; `roster_limit` is a cap and
  commands no refresh policy. Commit only if `check_quality_gate.py` exits 0. **Run
  `python3 scripts/rendu_formulaire.py` before touching a label** — reading the YAML hides
  exactly the defect #578 fixed.
  → `docs/decisions/ci-cd.md`, `docs/decisions/deux-axes-formulaire-578.md`
- **The push identity decides whether any workflow sees the data commit — and today none
  does (#508, #685).** A `GITHUB_TOKEN` push emits **no `push` event**; only a deploy-key
  push does. #508 wired `ssh-key: ${{ secrets.DATA_PUSH_SSH_KEY }}` into `merge-and-pivot`,
  but the three manual gestures its §7 names — deploy key, secret, ruleset — were **never
  performed** (measured 01/09/2026: zero deploy keys, no such secret, no
  `required_status_checks`), so the push still goes out under the token and **0 of the 15
  data commits since `tests.yml` exists carry a test run**, the 11 since #508 included. Its
  **loud** rejection cannot fire either: it speaks only on a `GH013`, which needs the
  required check that was never restored — two omissions covering each other, which is why
  fifteen commits went unnoticed. `merge-and-pivot` now **measures the remote it actually
  pushed to** and says so in an annotation and in the job summary, non-blocking; the
  guarantee returns only with #508 §7, never by editing this line.
  → `docs/decisions/push-donnees-cle-de-deploiement-508.md`,
  `docs/decisions/identite-du-push-et-declenchement-des-tests-685.md`
- **A job never writes a cache key for a directory it does not fill.** Three times:
  #412 §2.3 → #424 → #505. A job carrying a `--skip-*` flag uses `actions/cache/restore`;
  a key whose **content** depends on an input carries that input; two jobs sharing a key
  share the exact same `path:`; an index is cached only once **complete**. Locked by
  `tests/test_ci_cache_producteur_ecrivain.py`.
  → `docs/decisions/cache-mode-interventions-505.md`
- **Never raise `timeout-minutes` without `--budget-interventions-secondes`, or the
  reverse (#498).** A shard killed by `timeout-minutes` writes **no profile at all**; an
  exhausted budget writes the partial profile and declares the truncation in
  `meta.warnings[]` (§2.5). Guarded by `tests/test_ci_budget_interventions.py`.
  → `docs/decisions/budget-collecte-interventions.md`
- **Every collection path must declare what it does with interventions (#501).** A new
  invocation of `generate_all_profiles.py` goes into `tests/test_ci_interventions_par_job.py`
  with its mode, and a job that ignores the input is named in the input's description.
  → `docs/decisions/interventions-senat-501.md`
- **One artifact = one job's contribution (#450).** An extraction job publishes only the
  profiles it actually wrote — never `raw_data/profiles/`, which its `actions/checkout`
  also filled with the committed baseline. Guarded by
  `tests/test_ci_publication_profils.py`.
  → `docs/decisions/publication-scopee-artifacts.md`
- **One roster per run (#518).** `raw_data/roster_candidats.json` is built once and
  shipped as an artifact; a consumer regenerates it **only if the artifact is missing**.
  `fetch_full_roster` retries timeout/`ConnectionError`/5xx and **never** `SSLError`
  (subclass of `ConnectionError` — order matters) or 4xx. Blocking anomalies are
  `::error::` annotations via `src/gha.py`, **stdout only**, single-line.
  → `docs/decisions/roster-unique-par-run-518.md`
- **Retrying under a ceiling set too low does not buy back the ceiling (#518, second
  incident).** A production timeout sits **outside** the endpoint's response distribution;
  `_ROSTER_TIMEOUT` is split `(connect, read)` with **connect unchanged** — #516's
  deterministic `SSLError` verdict rides on it. The run's **raw** roster ships in the same
  artifact, or a group sheet diverges from the collected corpus with no step failing.
  → `docs/decisions/plafond-roster-et-commit-518.md`
- **A source outage costs the roster branch, never the commit (#524).** The exception —
  not the key — reaches the `::error::` annotation; the roster steps tolerate codes **1
  and 2 in the shell** and the pivot step is gated on `hashFiles(...)`, on the **file**,
  not on a step's success; "every group suspended" returns `EXIT_ROSTER_INDISPONIBLE = 2`,
  tolerated by all **three** callers. **Never `continue-on-error: true`** there: it would
  swallow code 1 and commit a stale sheet with nothing blocking.
  → `docs/decisions/cloisonnement-branche-roster-524.md`
- **`retry-generate-data.yml` is coupled to `generate-data.yml`, and nothing in either
  file says so.** The API does not expose a run's inputs, so the retry **rebuilds them
  from the logs** and re-dispatches with `-f`. Two silent failure modes: a `-f` with no
  matching input (422 on the day a retry is needed), and an output written under one name
  and read under another (the retry restarts on the defaults, no error, no trace). Locked
  by `tests/test_ci_inputs_workflow.py`. Read `docs/workflow-generate-data.md` §7 before
  touching either workflow's inputs.
  → `docs/decisions/retry-inputs-appariement-prefixe.md`

### 3c. The four pre-commit guards

`merge-and-pivot` runs all four before the commit, each in a separate process. Each
tolerance is **partitioned** — no input disarms another's check.

- **Loss check (#460, extended by #470)**: `audit_diff_profils.py --ref HEAD` over all of
  `pivot_data/`. Three findings abort the commit — a file that **disappeared**, a **drop
  on a stable list**, a **watched scalar going from populated to `null`**; drops on
  `amendements`/`sources`, index counts and scalar value changes are reported only. A run
  may legitimately lose entries — declare it with `allow_declared_losses`, never by
  removing the check. **The published aggregates are watched scalars, not stable lists
  (#649)** — `amendements_agreges` and `comptages.par_statut` block on disappearing or
  going `null`, never on their value falling, and `0` is a measurement while `null` is
  not. **There is no ratio threshold, and adding one is settled**: the *correct* drop of
  `3c8e1f0c` (× 0,03 to × 0,21) is larger than the *defective* one of `a125e9e` (× 0,00
  to × 0,64) on every fiche, so no threshold separates them.
  → `docs/decisions/controle-de-perte-avant-commit.md`,
  `docs/decisions/perimetre-controle-perte.md`,
  `docs/decisions/agregats-publies-controle-perte-649.md`
- **Referential integrity (#485)**: `audit_integrite_referentielle.py`. Every published
  key resolves in the index it points at, or the commit aborts naming file and key — an
  orphan reference is a vote published with no object, on a groupe a false denominator
  (§2.7). A `null` key **with** its `*_non_resolu` record never blocks. Index entries
  nobody references are non-blocking. **`allow_declared_losses` does not disarm it**, and
  it must never be merged with `allow_broken_references`.
  → `docs/decisions/integrite-referentielle-pivot.md`
- **Collected must equal published (#511)**: `audit_collecte_non_publiee.py`, run
  **after both `--pivot-only` passes** — placement is half the control; run between them,
  every roster member would be a phantom gap. Threshold **0**; a pivot with no raw is
  non-blocking. Tolerance `allow_unpublished_profiles`. `generate_roster_candidats.py`
  refuses to write on a failed fetch, on a configured group returning 0 members, or on an
  empty roster.
  → `docs/decisions/collecte-non-publiee.md`
- **Each published list must carry what collection returned (#545)**:
  `audit_collecte_vs_publie.py`. #511 reasons about profiles, this one about the
  **contents of their lists**. Each published list declares in `RELATIONS` the raw **paths
  whose lengths it sums** — a named source, never a tolerated margin, which keeps the
  threshold at **0** everywhere. Blocking: a deficit, or an unreadable profile. Reported:
  a surplus, and a raw list with no declared relation. Tolerance
  `allow_publication_gaps`.
  → `docs/decisions/collecte-vs-publie-545.md`
- **A progress file is not a profile — and `Path.glob` disagrees (#518, third incident).**
  `Path.glob("*.json")` **returns dotfiles**, unlike the `glob` module: every inventory of
  `raw_data/profiles/` skips `name.startswith(".")`, safe by construction since no slug
  starts with a dot. Cause fixed too: **`--no-checkpoint` on every `--pivot-only` pass**.
  → `docs/decisions/point-de-sauvegarde-dans-les-profils-518.md`

### 3d. Scope, sources, rosters

- **The Senate is out of scope, and `extract-senat` is retired (#528).** The decision is
  **editorial**, not technical: a renewed certificate changes nothing, and reopening
  requires the three written conditions of the decision's §7. Three loud refusals guard
  the non-return, frozen by `tests/test_retrait_senat_528.py`. **Kept**: the 2 published
  `groupe-Senat-*.json` (deleting a published file is a disappearance `audit_diff_profils`
  blocks), their `groupes_reels.json` entries, the Senate mandates already collected, the
  NosSénateurs ODbL attribution.
  → `docs/decisions/retrait-senat-528.md`
- **NosDéputés is out of the pipeline (#529).** The raw profile comes entirely from AN
  open data; `normalize_profil.py` (ex-`normalize_nosdeputes.py`) writes
  `sources[].type = assemblee_nationale`. **A counter structurally at zero, kept under
  watch, is #510's mute hole** — both NosDéputés counters went with the source. **Kept on
  purpose**, because they read the published corpus rather than collect: `nosdeputes`/
  `nossenateurs` in `KNOWN_SOURCE_TYPES` and `MAPPING_CHAMBRE_SOURCES`, the
  `meta.synchro_sources.nosdeputes` fallback read, and the `mots_cles` → `tags_thematiques`
  fallback. The published NosDéputés speeches **stay** — `interventions` is a blocking
  watched list. Guarded by `tests/test_retrait_nosdeputes_529.py`, which reads the
  **executed** code — strings and identifiers, never comments.
  → `docs/decisions/retrait-nosdeputes-529.md`
- **The slug ↔ AN actor correspondence is a committed artifact, not a heuristic (#525).**
  `raw_data/correspondance_acteurs_an.json` carries, per published slug, its `PA######`,
  the état civil, the **proof** (the AN fiche URL) and a verification date. A declared
  `hors_an` returns `None` with **no** name fallback; an *absent* slug does fall back; a
  missing table is a **declared** fallback. **Gate §5b hard-fails the commit naming any
  published slug with no entry**, threshold 0. `build_correspondance_acteurs_an.py`
  reconducts reviewed entries verbatim and **refuses to invent**.
  → `docs/decisions/correspondance-acteurs-an-525.md`
- **The AN group roster comes from AMO30, and `AN_ROSTER_ACTIF` is a kill switch (#527)** —
  lowered → `RosterAnInactif`, never an empty roster. `ERREURS_ROSTER` unites both sources'
  failures so an absent archive stays a named « roster indisponible » (`exit 2`, committed
  sheets intact); a **slugless** member is counted and named (`ROSTER_SANS_SLUG`), never
  dropped without a word; the **published** `fraicheur_donnees` warning follows the flag,
  because naming a source the composition no longer comes from breaks §2 rule 2. **The
  double computation is NOT retired** — of #526 §9's three clauses only the first holds.
  → `docs/decisions/bascule-roster-an-amo30-527.md`
- **A roster derived from AMO30 obeys three measured traps (#526).** A mandate ending on
  or before the day the legislature's groups are constituted is a **transit**, and that
  date is *read* from the referential, never hard-coded; the AN sigle is
  `organe.libelleAbrev`, **not** `libelleAbrege`, and the published sigle → AN sigle(s)
  table is committed in `raw_data/groupes_reels.json`; one group can have **successive
  organs** in one legislature, so the roster is their deduplicated **union** with periods
  re-glued. An actor with no entry in #525's table gets `slug: None` **and** a named,
  dated line in `membres_sans_slug`. Guarded by `tests/test_an_roster.py`, on a
  **reduction** of the real archive — never a hand-written fixture (#510).
  → `docs/decisions/roster-an-derive-amo30-526.md`
- **A configured group's extraction can be suspended, never silently (#516).** A
  `groupes_reels.json` entry carrying `extraction_suspendue` is not fetched, not
  regenerated, **not counted as a failure**, and keeps its **hard** gate checks but not
  its soft ones. Suspending is not removing — removing deletes a published file, which
  `audit_diff_profils` blocks. The block requires `depuis`, `motif`, `references`,
  `condition_reprise`, and **the gate hard-fails without them**: a suspension with nothing
  left to re-read becomes permanent by omission.
  → `docs/decisions/extraction-groupe-suspendue-516.md`
- **Bicameral collection is for candidates only (#488)** — both chambers are queried only
  when `meta.provenance == "candidat_declare"`; a `roster_groupe` member keeps
  first-answer-wins. When both answer, the **first of `CHAMBRES` wins by documented
  convention**, and no mandate is ever merged across chambers. Two warnings reach the
  published `meta.warnings`: `carrière sur deux chambres` (candidates only) and `collecte
  de chambre en échec` (all profiles — a chamber silently picked by an outage is §2.5).
  → `docs/decisions/deux-chambres-interrogees.md`
- **A profile's chambers are derived, and the fallback is declared (#493).** **Call
  `appliquer_chambres()` after any mutation of `mandats[]`** — a derived field is
  recomputed, never merged. The collection chamber is always **unioned in**, never
  substituted and never dropped: removing an observed chamber is a deletion. The fallback
  is usable, not verified, and what keeps it from misleading is that it is **declared** —
  one `chambres du profil non corroborée` warning per profile (§2.5), whose corpus count
  is the migration meter. `chambre`'s retirement condition is written down; without a
  written criterion a transitional becomes permanent, as #431's and #432's read fallbacks
  did. **That warning declares one thing only: a published chamber that no stamped mandate
  backs (#486).** It does not restate the completeness of `mandats[]` — that is #492's own
  warning, recomputed on the **merged** mandates in both directions. Conflating the two
  gaged a profile-level field's retirement on a mandate-level completeness the additive
  merge cannot reach: 29 of the 511 published `mandat_electif` are entries the source no
  longer serves, so `backfill_mandat_chambre` can never match them.
  → `docs/decisions/chambres-profil-derivees.md`,
  `docs/decisions/corroboration-chambres-publiees-486.md`
- **A group's eligibility window is chamber-scoped (#492)** — a union over all
  `mandat_electif` counted a member absent on ballots he could no longer vote, a false
  cohesion denominator (§2.7). A mandate with `chambre: null` is **kept** (excluding it
  would shrink a published denominator on missing data), and "no elective mandate at all"
  stays distinct from "elective mandates, none in this chamber".
  → `docs/decisions/chambre-par-mandat-electif.md`

### 3e. Interventions (Syceron)

- **Syceron publishes the speaker id BARE (#510)** — prefix it with `PA`, which is not an
  inference: the same `<paragraphe>` carries `id_acteur="PA<id>"`. When `id_acteur`
  **contradicts** the prefixing, the source itself refuses the attribution and so do we:
  keeping the first would fabricate a speech (§2 rule 2).
  → `docs/decisions/syceron-acteur-ref-nu-510.md`
- **Measure only on verbatim reductions of the archive.** The two invented fixtures are
  **deleted**, not deprecated — keeping them under test kept the cause armed. What
  separates a subject from a procedural heading is **structural**, not lexical (the
  point's `code_grammaire`); `sujet` is `None` otherwise (§2 rule 5), never a procedural
  title, which would then feed `tags_thematiques` (§2 rule 8).
  → `docs/decisions/syceron-archives-verifiees-parseur-510.md`
- **An index that resolves zero actors is never cached nor returned silently.** #505's
  guard only covered "no readable file", and that gap is how #510 survived (§2.5).
  Unresolved ids are **counted, not warned** per entry; the tripwires are
  `forme_inattendue` and "not one indexed entry carries a subject", both at **0**.
  → `docs/decisions/syceron-actif-510.md`
- **Syceron is live and the NosDéputés fallback is gone (#510).** The flag is **removed**,
  not lowered — a defective mode behind a switch keeps the defect armed;
  `--activer-interventions-syceron` is still declared and **loudly refused**, because
  `unrecognized arguments` would read as "Syceron collection is off". **A source that
  replaces the primary one is what made #510 invisible.** An empty Syceron collection now
  stays empty and says so, under a label that is a **prefix** of the old one so published
  warnings stay recognisable.
  → `docs/decisions/syceron-actif-510.md`
- **The interventions index is sharded per actor**, published by one `os.replace` (patron
  #392/#403). Both flat legacy indexes are **deleted** on publication and never re-read.
  The per-legislature lock is **reentrant**, and the memo of built-but-unpublished indexes
  is keyed on the cache **path** (the #377 trap).
  → `docs/decisions/syceron-actif-510.md`
- **A group aggregate is a consumer nobody greps for (#657).** `--skip-interventions` was
  hard-wired into the roster job on the written ground that "no group aggregate consumes
  interventions". It was **false**: `tags_thematiques` derives entirely from
  `interventions[]`, and each group sheet's `tags_thematiques_agreges` from that — so every
  sheet's "thematic footprint" was **one person's** (470 tags on `AN:RN`, 0 on `AN:LFI`).
  The derivation crosses two stages, and nobody re-reads `normalize_profil` when deciding
  what an extraction job collects. **Before declaring a list unconsumed, grep the
  derivations, not the aggregates.** The roster now collects **theme only**
  (`--interventions-theme-seul`): debates without verbatim, official questions not at all
  (they carry no theme). **Two index forms, two directories** — the reduced run reads the
  full index and drops the heavy fields; the full run never reads the reduced one. A
  **declared candidate is never reduced**: additive merge keeps the *older* entry, so a
  reduced entry would freeze his full form forever.
  → `docs/decisions/collecte-interventions-reduite-au-theme-657.md`
- **What is not measured says so** — per-candidate cost and RSS of the sharded index are
  bounded by construction, not by measurement, and the #429 and #500 balances are
  un-remeasured. Naming them is the rule: §2.5 applies to our own work too.
  → `docs/decisions/syceron-actif-510.md`

### 3f. Quality gate

- **Hard fail**: IncompleteRead over threshold, invalid or missing groupe/gouvernement
  file, broken structure (#212), §5b's unmapped published slug (#525), §7's 80 MiB blob
  (#580). **Soft**: low interventions, low coverage, network signals, partial identifier
  coverage in `amendements[]` (§3c), index freshness (§3d), couverture ministérielle,
  empty `textes[]` (§5, mirroring groupes §4).
- **Partial `uid` coverage is soft on purpose** — mixed profiles were expected during the
  remediation window, and failing the gate would have blocked the very runs meant to fix
  them (#447, cause #450). Two versions of one amendment cohabiting means the entry is
  counted twice and the published denominators are wrong.
  → `docs/decisions/cache-amendements-existence-nest-pas-conformite.md`
- **The `uid` measurement follows the amendments, not the record**: it covers every
  profile that *publishes* `amendements[]`, whatever its `chambre`. The "AN candidates"
  counters and the "empty everywhere" signal keep the narrower population, the one
  amendments are *expected* from. **Name the population of every figure.**
  → `docs/decisions/cache-amendements-existence-nest-pas-conformite.md`
- **Frozen legislatures are never re-fetched** — 14/15/16 are closed dossiers, their index
  is committed under `raw_data/amendements_an_figes/`. §3d distinguishes "never built"
  from "present but stale beyond N days" from "frozen".
  → `docs/decisions/amendements-legislatures-figees.md`

## 4. Pivot schema v1 (`src/schema_pivot.py`)

| Key | Content |
|---|---|
| `id` | The profile's **slug** — its filename, **no provenance prefix** (#487). `nosdeputes:`/`nossenateurs:` derived from whichever chamber answered the collection, so it *changed value* on an unchanged career (two profiles flipped, in opposite directions, between `25f7bc7` and `01ffa7f`). Provenance stays where it is true: `sources[].type`, `identite.source_url`, `meta.provenance`. Standalone tools with no slug (`mep_profile.py --ep-id`) keep an explicit source id — better that than a slug invented from a collected name. See `docs/decisions/id-pivot-sans-prefixe.md`. |
| `nom`, `chambres`, `chambre`, `parti`, `groupe` | `chambres` (#493) is the **derived list** of chambers the person sat in, values from `KNOWN_CHAMBRES`, ordered by `ORDRE_CHAMBRES` (`AN`, `Senat`, `PE`, `mairie`). `chambre` is `chambres[0]` — never collected, never able to contradict it (`validate_profil` enforces it). Both come from `schema_pivot.deriver_chambres()`, the single factory. See `docs/decisions/chambres-profil-derivees.md` |
| `identite` | Nullable bio block. **`civilite` and the two INSEE PCS levels come from AMO30 and are copied, never inferred (#659)** — `civilite` from `etatCivil.ident.civ` (3 117/3 117 fiches: M. 2 106, Mme 1 011), **never derived from a first name**; `famille_socioprofessionnelle`/`categorie_socioprofessionnelle` from `profession.socProcINSEE` (2 177/3 117, both levels always filled or absent together). Publishing them is legitimate **because the source classifies, not us**: a socio-professional categorisation built by this repo would be an editorial act (§2 rule 1). `null` on the 940 fiches the source does not classify — and **« not classified » is not the family « Sans profession déclarée »** (85 fiches), which is a value of the nomenclature; conflating them is #556's exact contresens. Labels are published **verbatim**, typographic variants included; grouping belongs to whoever aggregates, purely typographic, never semantic. `profession` stays free text (#641). The three keys are optional, like `identifiants` and `provenance_champs`. See `docs/decisions/civilite-et-pcs-insee-659.md` |
| `sources[]` | `{type, url, synchro_le}` |
| `mandats[]` | Elections, committees... + sensitive fields (Section 5). `mandats[].chambre` (#492) is written **only on `mandat_electif`**: `AN`/`Senat`/`PE`/`null`, meaning *the chamber whose dataset returned this mandate*, stamped at collection. Never derived from `source_url` (0 of 214 AN/Senate elective mandates carry one) nor from the profile's `chambre` (additive merge accumulates mandates from both chambers in one profile). `null` + one aggregated warning per profile, never a default. See `docs/decisions/chambre-par-mandat-electif.md`. **A profile publishes ALL its elective mandates (#640)**, one per seat, grouped on AMO30's `(legislature, dateDebut)` — never on the legislature alone, which would weld together two terms separated by an annulled election. `identite.nb_mandats` counts AMO30 *records*, the list counts *seats*: the two are no longer meant to be equal. See `docs/decisions/mandats-electifs-liste-complete-640.md` |
| `votes[]` | **Mapping only** (`#432`): `{scrutin_id, position}`. The ballot's metadata (date, text, sort, type_vote…) lives once in `pivot_data/scrutins.json`, not once per voter — 179,8 → 17,9 Mo + 8,1 Mo of shared index, −85,5 %. AN legislatures 14-17 aggregated (`#403`) |
| `textes_portes[]` | Author/reporter/co-reporter + procedural stage. `dossier_id` (#639) is the AN legislative-dossier key (`DLR5L15N37607`), copied verbatim from the raw `dossiers_legislatifs[].id` (472/472) — **same name as a government sheet's `textes[].dossier_id`**, deliberately: two names for one identifier send every cross-reference back to the label. Never rebuilt from a title. See `docs/decisions/qualification-scrutins-et-cle-dossier-639.md` |
| `amendements[]` | **Mapping only** (`#431`): `{amendement_id, role_signataire}`. Outcome, inadmissibility, date, `co_signataires`… live once in `pivot_data/amendements/<legislature>.json`, not once per signatory — 1 342,4 → 73,8 Mo of mapping + 130,1 Mo of shared index, −84,8 %. `role_signataire` is the only member-specific field |
| `interventions[]` | Speeches, questions (`type_detail`). An entry carrying `collecte: "theme_seul"` (#657) was collected **without its verbatim**: its heavy fields are **absent, never `null`** — a `"texte": null` would read as a fact about the person, where the fact is about the run (§2 rule 5). `collecte` is a closed value (`KNOWN_COLLECTES_INTERVENTION`); its **absence** is the full form. See `docs/decisions/collecte-interventions-reduite-au-theme-657.md` |
| `tags_thematiques[]` | 8 stable categories (`STABLE_THEMES`), via `classify_keywords()`. |
| `meta` | `schema_version`, `genere_le`, `licence_donnees`, `warnings[]`, `avertissements[]` (#642), `provenance` (`candidat_declare`\|`roster_groupe`, see `docs/decisions/provenance-pivot.md`), `provenance_champs` (#603). **`provenance` says why the profile exists; `provenance_champs` says which source filled which field of `identite`, and when** — optional (absent from the 481 profiles published before the lot), `identite`-only, and an unknown origin is published `{"source": null, "synchro_le": null}`, never omitted. Derived after the merge like `chambres` and `licence_donnees`, never merged. Not to be confused with `couverture` either: that one says *why a business list is empty*, per list, not per field. See `docs/decisions/provenance-par-champ-603.md`. **`meta.avertissements[]` (#642) is the typed twin of `warnings[]`** — one `{message, destinataire}` entry per warning, same order, same strings, enforced by `valider_avertissements()`. `destinataire` is a closed two-value vocabulary (`lecteur`, `interne`, `DESTINATAIRES_AVERTISSEMENT`): the key is **mandatory**, `null` says « nobody declared it », the omission says nothing. There is no third « mixed » value — a warning addressing both is **written twice**. It is declared **at the site that writes it**, via `avertissements.avertissement(message, destinataire)`, never by a table keyed on the message prefix: `votes introuvables` covers a constat *and* a panne (#484 verbatim). Derived like `chambres` and `licence_donnees`, never merged; optional on the 481 profiles published before the lot, with a written retirement condition. See `docs/decisions/destinataire-avertissements-642.md` |

Conventions: French `snake_case`; missing = `null` (never `""` or `0`); closed values in
`frozenset KNOWN_*`, validated by `validate_profil()` — extend the frozenset, never bypass.

### 4a. Group fiches: every count is taken at one published date (#653)

**A group fiche describes a legislature, and none of the 7 published describes
the one in progress. No counter on it may mean "today".** Three did, and all
three measured the members' *later careers* instead of the group:
`effectif.actuel` equalled, exactly, the number of members holding an **open
elective mandate** (38/38, 85/85, 60/60 on `LR`, `REN`, `LFI` — re-elected in
2024, not group members in June 2024), and `nb_membres_actifs` counted their
**present-day** committee.

- **`date_reference` is published in the fiche** — `{date, origine}`, `origine`
  in `ORIGINES_DATE_REFERENCE`. **Derived, never guessed**: the latest
  `fin_dans_groupe` when every membership is closed (`cloture_legislature`,
  `2024-06-09` for the XVIᵉ), the generation date while one is still open
  (`generation`). A dated counter the reader cannot date is a bare counter
  (§2 rule 2).
- **The three counters are named for it**: `effectif.a_la_date_de_reference`,
  `mandats_agreges[].nb_membres_a_la_date_de_reference`,
  `membres[].present_a_la_date_de_reference`. The names are long on purpose —
  a short name that reads "today" is what produced the defect.
- **`periode.actif` is *not* rebased on it.** It describes the *period*, not a
  headcount at an instant; `false` on a closed legislature is exact.
- **Selecting the entry matters as much as the flag.** A duplicate
  `(categorie, label)` must be resolved to the mandate **open at the reference
  date** (`_select_mandat_a_la_date`) before `_select_mandat_entree_unique`'s
  rule applies: that one prefers the `actif` entry, i.e. a re-elected member's
  committee in the **next** legislature. 1 000 of `AN:LFI-16`'s 2 384 entries
  have several candidates; without the preference, its `affaires sociales`
  drops from 9 sitting members to 3.
- **A mandate with no `debut` is open at no date.** `_intervals_overlap` treats
  an absent bound as unbounded, which would make it cover every date (§2 rule 5).
- **`date_reference` is optional, never required.** The 2 frozen `groupe-Senat-*`
  fiches (#516) will not be regenerated and keep the old names; requiring the
  key would hard-fail the quality gate on already-published files. Readers must
  therefore accept both names — `audit_groupe_dataset.CHAMPS_EFFECTIF` does.

→ `docs/decisions/date-de-reference-des-comptes-de-groupe-653.md`,
`docs/decisions/dates-appartenance-groupe-653.md` (where the membership dates
themselves come from), `docs/decisions/mandats-agreges-siege-vs-passe-656.md`
(the two counters they feed).

## 5. Sensitive institutional fields (validation constraints)

- `mandats[].position_dans_hemicycle`: requires `source_url` (rule 6).
- `mandats[].suspendu_pour_fonction_gouvernementale`: never confuse with completed mandate.
- `votes[].type_vote == "motion_censure"` requires `texte_lie_id` **or a declared `texte_lie_non_resolu.motif`** (#639); 49.3 → `sort = "adopte_sans_vote_49_3"`, no position (rule 4).
  A censure motion is a **procedural fact**, never a position on the text — and its link is not
  sourceable: `objet.referenceLegislative` and `demandeur.referenceLegislative` are null on **0 of
  18 311** raw AN scrutins (legs 14-17), and an article 49-2 motion has no text to link at all.
  Hence the repo's own `*_non_resolu` pattern — null key **plus** the declaration, never an invented
  key and never silence. A mute motion is still a schema error.
- **`type_scrutin` and `type_vote` come from `typeVote.codeTypeVote`, one source field, no inference
  (#639).** `SPO`→`public_ordinaire`, `SPS`→`solennel`, `SAT`→`tribune`, `MOC`→`motion_censure`
  (+`vote_texte`/`motion_censure` on `type_vote`). An unknown or absent code stays `null` — never
  filed under `SPO`, which is 97,5 % of published scrutins (rule 5). `SSG` (Congress) is absent from the table
  on purpose: those scrutins are dropped upstream on their uid. `vote_texte` stays **coarse** — `SPO`
  covers article, amendment and whole-text ballots alike, so it does NOT constitute the "votes on the
  whole text" universe the published methodology claims.
- **A scrutins cache that carries no qualification is refused, not re-read (#639)** — disk cache **and**
  committed frozen index (`raw_data/scrutins_an_figes/`), whose three legislatures now carry it
  (rebuilt 31/08/2026: 1 354 / 4 417 / 4 105 scrutins, 4 / 5 / 34 censure motions). Same rule as the amendments
  cache: existence is not conformity. Accepting a stale one would have published 43 of the 66 censure motions as
  `vote_texte`. **Carrying it to the index is a third thing**: the raw vote acquires it only through
  `backfill_vote_qualification` (#639, above).
  → `docs/decisions/qualification-scrutins-et-cle-dossier-639.md`
- `votes[].numero_scrutin` restarts at 1 in each legislature: never a key on its own.
  Dedupe by AN `uid` **at index level** (`raw_data/scrutins_an_figes/`, where the AN
  `uid` exists); key group cohesion by `(legislature, numero)` — see
  `docs/decisions/votes-multi-legislature.md`. A profile's `votes[]` carries no
  `uid`: its key is `(legislature, numero_scrutin)`, and 22,5 % of collected votes have no
  `legislature` at all. Resolve it with `src/scrutins_legislature.py` — labelled-twin join
  first, legislature calendar second, loud failure third; never a default (rule 5). Audit
  the corpus with `src/audit_legislature_votes.py` before relying on the key
  (`docs/decisions/resolution-legislature-votes.md`).
- `amendements[].sort == "irrecevable"` requires `base_juridique_irrecevabilite` (`"art. 40"` or `"art. 45"`).
  Since `#431` both fields live in the shared index: the invariant followed them, into
  `validate_amendements_index()` — checked once per amendment, not once per signatory.
  What `validate_profil()` can no longer check alone is that a referenced `amendement_id`
  exists: it does so **only if** `amendements_index=` is passed, and skips it otherwise —
  never declares it valid by default.
- `amendements[].type_deposant`: never aggregate adoption rates across depositor types (rule, Section 6).
- Amendements cache (`.cache/amendements_an/<leg>/`): **a directory that exists is not
  evidence of what it holds.** Presence checks must also check the key format — a frozen
  cache written before the `uid` correction is skipped by `build_amendements_index.py` and
  refused by `_read_cached_amendements_acteur` at once, losing the whole legislature in
  silence. And the shard directory is published by a single `os.replace` from a temp dir,
  never filled in place: a half-written directory reads as "this member has no amendments"
  instead of "index unavailable". That atomicity is what makes the single-shard format
  check legitimate — do not fill in place.
  See `docs/decisions/cache-amendements-existence-nest-pas-conformite.md`.
- **A disk cache prevents a re-download, never a re-parse.** Any shared index read
  once per candidate must be memoised in-process — third occurrence of the same
  cost at the same spot (#392 amendements, #403 scrutins, #467 AN acteurs/organes:
  2 255 re-reads of one index for 24 members, 59 % of wall time). Key the memo on the
  index **path**, never on a logical name: tests patch the cache dir per case, and a
  global memo leaks one test's index into the next (the trap that reverted #377).
  See `docs/decisions/budget-execution-pleine-echelle-467.md`.
- An amendment with no AN `uid` gets **no invented key**: `amendement_id: null` plus its full
  record under `amendement_non_resolu`. That is the normal shape for European Parliament
  amendments, which ParlTrack ships without an AN uid.
- **Never re-materialise the flat form.** `joindre()` is a generator and `get()` returns the
  shared object itself, never a copy — expanding index × mapping cost a ~21 × factor and an
  OOM in `#377`. Locked by `tests/test_amendements_index.py`.
Edge-case history: the amendments and votes entries of `docs/technical_decisions.md`
(the index is chronological, newest first).

## 6. Metrics: public vs internal

| Metric | Status |
|---|---|
| `textes_portes[]` (stage ≥ `examine_commission`) | Public |
| `textes_portes[]` below threshold | Via explicit user toggle — not published by default |
| `amendements[]` raw counts + `par_type_deposant` | Public |
| Adoption rate across all submitter types | **Never** (misleading) |
| `amendements_agreges` on a group sheet | Public — **distinct amendments**, deduplicated on `amendement_id`. A co-signed amendment is **one** |
| Signatures laid by a group's members | Public, under `amendements_agreges.signatures`, never under the word "amendments" |
| Adoption rate over signatures | **Never** — numerator and denominator are inflated by different co-signatory counts, so the bias has no known direction (§2 rule 7) |
| `votes[]` bill vote (`vote_texte`, latest reading) | Public |
| 49.3 / no-confidence motion | Public, labeled as procedural fact |
| Individual attendance/presence | **Never public** (rule 3) |
| Group `cohesion_votes[]` | Public, with numerator/denominator |
| Individual cohesion/participation **index** vs group average | **Never** — internal only (`--rapport-interne`) |
| A member's position beside their group's majority position, **one sourced ballot at a time** | Public — never counted, never rated |
| `mandats[].notableCount` | Internal only (display ordering) |
| `tags_thematiques[]` (8 categories) | Public |

Full rationale: `web/old/v3/methodologie.html` — do not duplicate prose here.

## 7. Sources and licenses (reuse implications)

| Source | Collected? | License | Constraint |
|---|---|---|---|
| data.assemblee-nationale.fr / questions.assemblee-nationale.fr | **Yes — the only French source** (#529) | Licence Ouverte / Open Licence (Etalab) | Attribution only |
| Parltrack (JSON dumps) | Yes | ODbL v1.0 | **Share-alike** if republished as downloadable dataset |
| European Parliament (data.europarl.europa.eu, www.europarl.europa.eu) | Yes | EP Legal Notice (reuse policy, attribution-based) | Attribution only |
| NosDeputes.fr / NosSenateurs.fr | **No** since #528/#529 — but published fields still derive from it | ODbL v1.0 | **Share-alike** if published as downloadable dataset |
| French Wikipedia | Yes | CC BY-SA 4.0 | Verbatim quotes only (not current use) |
| Wikidata | Yes | CC0 1.0 | No restriction |

**"No French source is collected from Regards Citoyens any more" does not mean "the corpus
is under Licence Ouverte" (#530).** Share-alike survives on two counts: Parltrack is a
*live* source under ODbL, and 475 of 476 published profiles still carry a
`sources[].type` of `nosdeputes`/`nossenateurs` (511 published interventions still link to
`www.nosdeputes.fr`) — `merge_pivot_profile` unions `sources[]` by type, so additive
regeneration never drops them. Attribution stays due while the fields stay published
(§2 rule 2), exactly as `docs/decisions/retrait-senat-528.md` §4 already ruled.

`meta.licence_donnees` is therefore a **derived** field, never a constant: `src/licences.py`
holds the four canonical labels and `appliquer_licence_donnees(profil)` recomposes the
string from `sources[]` after every step that changes it (`normalize_profil`,
`normalize_europarl`, `enrich_pivot_with_parltrack`, `merge_pivot_profile`). Same pattern as
`chambres` in #493 — and its retirement condition runs itself: the ODbL clause leaves a
profile the day that profile stops carrying anything from Regards Citoyens.
Never hardcode a licence label elsewhere; import it from `src/licences.py`, and keep
`AGENTS.md` §7, `sources.config.js` and `LegalNoticePage.jsx` saying the same thing.

Site HTML = ODbL "Produced Work" (attribution sufficient). Downloadable raw data → share-alike.
Full details: `docs/decisions/licences.md`, `docs/decisions/licence-lot-6-530.md`.

## 8. End-of-task documentation upkeep

Before finishing a task, update only what actually changed — skip a file if nothing changed for it:

| File | Update when |
|---|---|
| `AGENTS.md` | New agent-facing rule, command, or constraint. Rare edit; stay terse. |
| `README.md` | **The front door, one page.** A new setup step, a change to the editorial line or to a coverage limit, a doc that becomes an entry point. Never a command — that is the row below. |
| `docs/commandes.md` | **An option is added or removed, a script is renamed or retired, a command's output moves.** Not when the pipeline changes: the file says what to type, never how the run works. `tests/test_commandes_documentees.py` fails on a script or a long option that no longer exists. |
| `docs/data-architecture.md` | A file under `pivot_data/`/`raw_data/` appears or changes shape, a schema changes, a source is added or removed, a normalisation or aggregation step moves. |
| `docs/workflow-generate-data.md` | **The entry point for all eight jobs** (§1: what each one does, consumes, produces, and its structuring decisions). Update when a job is added or removed, when what a job does or touches changes, when a form input, cache key or artifact name changes, when a budget is re-measured, or when the retry contract is touched. |
| `docs/extract-roster-groupes.md` | The only extraction job with a page of its own — it has depth a block cannot hold (rollout, regenerating existing profiles, the roster's three exit codes). A new job does **not** get a file: it gets a block in `docs/workflow-generate-data.md` §1. Eight files drift independently; one is reread in a single pass. |
| `docs/sources/` | **External-source references — the only docs that drift with their provider, not with our code.** Update when the provider moves a dataset, a URL pattern or a field, never because our pipeline changed. Each file states its own status in its header (`an-opendata.md`: live, the pipeline's single source; `nosdeputes/`: historical, not queried since #529) — the directory names the category, the header names the status. |
| `docs/decisions-par-module.md` | **Never by hand — it is generated.** Run `python3 scripts/generer_decisions_par_module.py` whenever a decision is added or edited, a `src/` module is added, renamed or removed, or a top-level function/constant a decision names is renamed. `tests/test_decisions_par_module.py` fails when the committed file has drifted, and when a module governed by 5 or more decisions cites none. |
| `docs/decisions/<anchor>.md` | New architectural choice or trade-off. **One decision = one new file**, never an insertion into an existing one. Level-1 `#` title carrying the issue number and the date, then context, decision, alternative rejected. Name it in kebab-case with the issue number (`retrait-senat-528`). |
| `docs/technical_decisions.md` | The index of the above, and nothing else. Add **one line at the top** of the list: the anchors, the date, the title, the link, and one sentence saying what the decision settles. Adding the file without the line (or the reverse) fails `tests/test_index_decisions.py`. |
| `ROADMAP.md` | **A large piece of work to plan for**, or a known defect that stays open. **Never a small fix — that is a GitHub issue.** It holds what GitHub cannot: the scoping findings that must not be re-litigated, and the known defects a cold-start session has to read. **Never a list of issues**: one was removed on purpose, because a table copying GitHub's state goes stale with every lot shipped, and a wrong table is worse than none. Keep entries to one line; put rationale in `docs/decisions/<anchor>.md` instead. |
| `CLAUDE.md`, `.github/copilot-instructions.md` | **Never — they are symlinks to this file.** One source, several names, so the instructions cannot drift between tools. Adding a tool that expects another name: create the symlink and add it to `ALIAS` in `tests/test_instructions_agents.py`. |
| `requirements.txt` | A new package is imported that isn't already listed. Pin the version actually installed/tested (`==`), don't add unpinned entries. |
| `requirements-dev.txt` | A new **test-only** package is imported. Same pinning rule; it already pulls `requirements.txt` via `-r`. |

Never create a missing file from this list without flagging it first.

## 9. Reporting to the owner

The rationale lives in this file and in `docs/decisions/`. Don't restate it in
chat.

**Length is a rule, not only shape — aim for ten lines.** Formatting buys no
extra room: a forty-line reply, tables and short paragraphs included, still makes
the owner reread everything to find the one thing that needs her decision.
Measured on three consecutive reports, 30/08/2026, each well-formatted and each
too long. Sorting is the agent's work, not hers.

- **One arbitration per reply.** When several points need a decision, raise the
  first and wait. Sequenced replies beat one complete report — she asked for this
  explicitly.
- **The detail lives in the deliverable, not in chat.** The document, the issue,
  the decision file carry the full reasoning; the reply carries the conclusion
  and the question.
- **A table whenever two things compare.** Prose forces a reread to compare two
  lines; a table is scanned. Applies to issue rundowns, before/after
  measurements, options with their costs.
- **No paragraph over four lines.** Break it, or turn it into a table.
- **Every figure names its population.** "20 members of the two Senate group
  files", never "20 senators". A correct figure on the wrong population is an
  error, not an approximation.
- **Never restate what the previous turn established.** No preamble, no "in
  summary" recap, no list of files read or alternatives discarded.
- **One recommendation, not a survey.** If two options are open, say which one
  and why in a sentence — then let the owner overrule.
- Test/command output: pass/fail counts only, unless something failed.
- Always flag, even briefly: schema/validation changes, anything touching
  Section 2, new warnings or errors introduced.

## 10. A subagent's report is a claim, not a result

Before relaying **any** figure, file path, test name or measurement produced by
a subagent, re-run the check yourself. Say what you verified, and say what you
could not.

This is not precautionary. Three drifts in a single day, 29-30/08/2026:

- an issue cited `test_les_inputs_du_retry_sont_tous_ecrits`; **that test does
  not exist**, and the name was passed on into agent instructions before anyone
  checked;
- a review reported "680 of 1 016 positions"; re-measured, it was **715** — the
  substance held, the figure did not;
- an agent reported a repo state that a second agent had already changed under
  it, and the collision only surfaced because the state was re-read.

A subagent that reports honestly still reports from a corpus that moved, a
grep that missed a case, or an instruction that was wrong. Verification is the
main agent's job, and it is the only place it can happen.

## 11. What to ask the owner, and what to decide alone

**Ask when the answer changes what gets built, and cannot be derived** from the
code, from Section 2, or from a decision already recorded in `docs/decisions/`.
A form's shape, a threshold's fate, a trade-off with a measured cost, deleting
unmerged work, pushing to a public repo: those are hers.

**Show before implementing anything a human will read on screen** — input
labels, published copy, page text. She has asked for this explicitly, and it is
the one case where reviewing draft wording is wanted. Render it as it will
appear (`scripts/rendu_formulaire.py` for workflow inputs), not as source.

**Do not ask her to review your own work.** Sub-issue bodies, commit messages,
agent instructions, which files to touch, how to name a branch: that is the
agent's job. Bad work gets corrected, not pre-approved. A report listing every
draft produced buries the two or three decisions that are genuinely hers —
sorting is the agent's work, not the owner's.

**One "awaiting your decision" section per report, and nothing else pending.**

### The shape of an arbitration

When something does need deciding, five parts, in this order:

1. **The concrete problem, with the measurement that makes it real.** Not "the
   labels are unclear" but "22 rendered lines for 10 fields".
2. **The question, on one bold line of its own.** This is the part most often
   lost: a question buried in exposition reads as commentary.
3. **Each option with its cost.** A table beyond two options.
4. **"My recommendation", and its reason in one sentence.**
5. **What follows regardless of the choice**, so the decision isn't taken
   under the impression that everything hangs on it.

## References

- `src/schema_pivot.py`, `schema_groupe.py`, `schema_parti.py`, `schema_gouvernement.py`: structure contracts.
- `src/check_quality_gate.py`: quality gate, eleven blocks (1, 2, 3, 3b-3e, 4, 5, 5b, §7).
  The `n/4` denominators printed are themselves stale. Hard vs soft fail logic.
  Amendements coverage/freshness are deliberately never hard fails — see
  `docs/decisions/amendements-zero-pas-de-hard-fail.md`.
- `docs/sources/`: external-source references, which drift with their provider and not
  with our code. `an-opendata.md` (AN open-data JSON schemas — live, our single source);
  `nosdeputes/` (historical, not queried since #529). Status is in each file's header,
  not in the directory name.
- `docs/extract-roster-groupes.md`: the roster-driven job, in depth (the other seven jobs are blocks in `docs/workflow-generate-data.md` §1).
- `docs/commandes.md`: every command the owner may have to type, grouped by
  intention (generate, audit, check before committing, operate, see what the user
  sees). 32 of the repo's 44 executables; the other 12 are pipeline-internal and
  the file says so. Locked by `tests/test_commandes_documentees.py`.
- `docs/data-architecture.md`: what the data becomes — the six outputs of
  `pivot_data/` (profiles, groupes, gouvernements, partis, scrutins, amendements).
- `docs/workflow-generate-data.md`: what a run does — the eight jobs one by one, the
  form, caches, artifacts, budgets, push, automatic retry. **Start here for "what was
  that job again, and why like that".**
- HATVP lobby-register: out of scope, and **there is no file for it** — this
  line named `docs/hatvp_opendata.md`, which never existed. The verdict now
  lives in `docs/decisions/hors-perimetre.md`, with the distinction from
  `identite.uri_hatvp`, the one HATVP datum the pipeline does carry.
- `src/json_io.py`: profile JSON write format (compact vs indented, #433).
- `src/normalize_profil.py`: raw FR profile → pivot adapter (named
  `normalize_nosdeputes.py` until #529).
- `src/licences.py`: canonical licence labels + the derivation of `meta.licence_donnees` (#530).
- `docs/decisions-par-module.md`: the same decisions read the other way round —
  **this module → these decisions**, generated from the symbols each decision
  names. Open it when you are about to change a file under `src/` and want to
  know what governs it. `docs/decisions/table-inversee-decisions-par-module.md`
  holds the criterion and what it misses.
- `docs/technical_decisions.md`: the index of the 158 decision files under
  `docs/decisions/`, newest first — the chronological read. Frequent entry points:
  `docs/decisions/direction-artistique-empreinte.md` (positioning, naming, targets),
  `docs/decisions/collecte-vide-necrase-jamais.md` (merge), `docs/decisions/licences.md`,
  `docs/decisions/licence-lot-6-530.md`, `docs/decisions/ci-cd.md`,
  `docs/decisions/ci-tests-pytest.md`, `docs/decisions/web-v3-ui.md`,
  `docs/decisions/hors-perimetre.md`, `docs/decisions/profils-json-compact.md`.
- `docs/archive/`: the pre-split copy of the old single file, frozen at 30/08/2026.
  **Never cite it** — its anchors are prefixed `archive-` on purpose, and
  `tests/test_index_decisions.py` refuses any path pointing into it.
- `ROADMAP.md`: known bugs + unscheduled ideas, kept short (not read
  automatically — consult on request). Rationale for deferred items lives
  in `docs/decisions/hors-perimetre.md`, not duplicated here.
