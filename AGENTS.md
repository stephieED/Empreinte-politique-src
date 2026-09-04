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
volumetry: `docs/data-architecture.md` — the seven outputs of `pivot_data/`,
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

### The domain rules, and why they are not here

The rules below govern **one area each**. They live in `docs/regles/`, one file
per domain, and are loaded when you touch that domain — not at every session.
`AGENTS.md` keeps the index, so a reference to « AGENTS.md §3a » still resolves.

| Where | What it governs |
| --- | --- |
| [`docs/regles/fusion-et-index.md`](docs/regles/fusion-et-index.md) | **§3a. Files, indexes, merge** — the two shared indexes, additive merge, named backfills, compact profile JSON, projection reads. |
| [`docs/regles/ci.md`](docs/regles/ci.md) | **§3b. CI: jobs, caches, artifacts** — no test reads the live corpus, cache keys, budgets, artifacts, the launch form, the push identity, the retry. |
| [`docs/regles/gardes-avant-commit.md`](docs/regles/gardes-avant-commit.md) | **§3c. The four pre-commit guards** — loss check, referential integrity, collected = published, each list carries what collection returned. |
| [`docs/regles/roster-et-sources.md`](docs/regles/roster-et-sources.md) | **§3d. Scope, sources, rosters** — Senate and NosDéputés out, the slug ↔ AN actor table, AMO30 rosters, group positions, bicameral collection. |
| [`docs/regles/interventions-syceron.md`](docs/regles/interventions-syceron.md) | **§3e. Interventions (Syceron)** — bare actor ids, verbatim reductions, séance slots, index conformity and sharding, theme-only collection. |
| [`docs/regles/portail-qualite.md`](docs/regles/portail-qualite.md) | **§3f. Quality gate** — what hard-fails, what stays soft, and why. |

**A new pipeline rule goes into one of those files, never here.** That is the
whole point: a lot about the merge touches `docs/regles/fusion-et-index.md`, and
`AGENTS.md` does not move.
## 4. Pivot schema v1 (`src/schema_pivot.py`)

**The schema lives in [`docs/regles/schema-pivot.md`](docs/regles/schema-pivot.md)** —
the field-by-field table, the group-fiche counters taken at one published date
(§4a, #653), and one sheet per group *and* per legislature (§4b, #700).

What holds everywhere, and is worth carrying without opening the file:
French `snake_case`; missing is `null`, never `""` or `0`; closed values live in
`frozenset KNOWN_*` and are checked by `validate_profil()` — **extend the
frozenset, never bypass it**. A derived field (`chambres`, `licence_donnees`,
`tags_thematiques`, `meta.avertissements`) is **recomputed after the merge**, never
merged.

## 5. Sensitive institutional fields (validation constraints)

**The constraints live in
[`docs/regles/champs-sensibles.md`](docs/regles/champs-sensibles.md)** — hemicycle
position, censure motions, ballot qualification, amendment inadmissibility, and
the caches whose existence is not conformity.

The one that governs every one of them: **a key we cannot source is never
invented, and never silently dropped** — it is published `null` alongside its
`*_non_resolu` record, which names the reason (§2 rule 5).
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
| `votes[]` bill vote (`vote_texte`, latest reading) | Public — **one text, one position**. The fold and the selection live ONLY in `web/UI_finale/src/utils/lecture.js`, beside `isWholeTextVote` (#711); the last reading is chosen by the **date**, over the **whole** scrutins corpus, never over the person's own votes — the rule was published for a year and implemented nowhere. See `docs/decisions/derniere-lecture-retenue-711.md` |
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
| `AGENTS.md` | **A rule that governs everything** — editorial, reporting, what to ask. A rule that governs **one area** goes to `docs/regles/`, never here (#737). Rare edit; stay terse. |
| `docs/regles/<domaine>.md` | **The rule you are about to add governs one module or one job.** Eight files, one per domain, indexed by `AGENTS.md` §3 — loaded when you touch that domain, not at every session. Keep the instruction, put the measurement and the incident in the decision file. `tests/test_regles_par_domaine_737.py` fails when a file empties, leaves the index, or when a section the repo cites stops being named in `AGENTS.md`. |
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
- **An audit is a consumer like any other, and nothing warns it that a field moved
  (#726).** Two blocks of `audit_pipeline.py` read fields a schema decision had since
  moved or dried up: `sources[].synchro_le` on `nosdeputes` entries, which #529 stopped
  collecting while keeping them for the ODbL clause, and `cohesion_votes[].date`, which
  #432 moved into `pivot_data/scrutins.json`. Hence `non_renseigne` split from
  `format_invalide` (an absence is not a fault, §2 rule 5; a **non-string** value still
  is), aggregated in the render while faults stay enumerated; and the date resolved
  **where it lives**, through `scrutins_index.charger()`. A missing index is a
  **declared** hole (`index_disponible: False`), and an **empty** index counts as missing
  — `charger()` returns one on an absent file, and calling it available would read "the
  file was missing" as "these groups have no ballot" (#510). The lesson is about the
  tests: they supplied a `date` inside the entry, so they checked that the function read
  a field the corpus does not carry. **A fixture describing the world as the code
  imagines it cannot reveal that the world moved.**
  → `docs/decisions/audit-champs-deplaces-726.md`
- `src/check_quality_gate.py`: quality gate, fourteen blocks (1, 2, 3, 3b-3e, 4, 4b, 5, 5b, 5c, 6, §7).
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
  sees). 33 of the repo's 45 executables; the other 12 are pipeline-internal and
  the file says so. Locked by `tests/test_commandes_documentees.py`.
- `docs/data-architecture.md`: what the data becomes — the seven outputs of
  `pivot_data/` (profiles, groupes, gouvernements, partis, scrutins, amendements,
  commissions_dossiers). **`commissions_dossiers.json` est produit et versionné depuis le commit de
  données `5de11422`** (02/09/2026) — 6 024 dossiers, 1,2 Mo : la ligne qui disait ici qu'il
  « n'a jamais été produit » et que l'empreinte thématique de la fiche candidat
  « est donc inerte » (#328) est périmée. Les **sept** outputs sont sur disque.
  Sa jointure `dossier_id` → commission saisie au fond résout **381/381** des
  dossiers déposés à l'AN et **0** des 174 déposés au Sénat : le référentiel est
  celui de l'AN, et le Sénat est hors périmètre (#528) — une absence de cause
  connue, à déclarer et non à combler.
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
