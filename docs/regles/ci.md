<!-- Extrait d'`AGENTS.md` par #737. Ces règles ne changent pas de nature en
changeant de fichier : elles restent des instructions, et un renvoi
« AGENTS.md §3b » continue de les désigner — `AGENTS.md` en garde la ligne
d'index. Ce qui change, c'est qu'un lot qui ne touche pas ce domaine n'a plus à
les charger, ni à les faire grossir. -->

# §3b — CI : jobs, caches, artefacts

### 3b. CI: jobs, caches, artifacts

- **No test may read `pivot_data/` or `raw_data/profiles/`, write anywhere under
  `pivot_data/`/`raw_data/`, or hit the network (#473).** Acceptance tests use frozen
  fixtures; `tests/conftest.py` cuts `requests.Session.send` and fails loudly, naming the
  URL. **Loopback stays open** — the criterion is leaving the machine, not speaking HTTP.
  Watch CLI/function **defaults** pointing into the repo. Test-only deps go in
  `requirements-dev.txt`.
  → `docs/decisions/ci-tests-pytest.md`
- **A test reading the developer's `.cache/` passes for the wrong reason, and CI never
  sees it (#721).** The eleven cache constants are `Path(".cache") / …` — **relative to
  the cwd**, i.e. the repo root locally. CI's sparse checkout does not materialise
  `.cache/`, so the read fails and the fallback applies; on a machine that has collected,
  it **succeeds**. `tests/conftest.py` filters `builtins.open` and refuses any path under
  the repo's `.cache`, naming the file (patron of #473). **Redirecting the constants was
  tried and rejected**: it breaks the tests that already isolate via
  `monkeypatch.chdir(tmp_path)` and write to a *relative* `.cache` — an absolute constant
  strips their isolation. The property everything rests on — **the constants stay
  relative** — is tested, with a witness counter. `.cache` is listed in
  `_NOMMES_POUR_ETRE_REFUSES` of `tests/test_ci_perimetre_sparse_checkout.py`: it is named
  to be **refused**, never read, and it must stay out of the sparse-checkout or the guard
  becomes a lie.
  → `docs/decisions/cache-du-poste-hors-des-tests-721.md`
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
