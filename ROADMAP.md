# ROADMAP — Empreinte politique

Short backlog: known bugs and ideas not yet scheduled. Not automatically
re-read by coding agents (unlike `AGENTS.md`) — consult on request.
Rationale for deferred items lives in
`docs/technical_decisions.md#hors-perimetre`; this file only tracks *that*
something is pending, not *why*.

## Known bugs

- 21 of the 207 profiles published as `chambre: "AN"` are known to the Senate's own
  roster, 18 with a still-open Senate mandate (measured 2026-08-20, #488). All but
  Retailleau are `roster_groupe`, so they are deliberately **out of scope**: no Senate
  group is aggregated, and their Senate past feeds nothing. The published value stays
  wrong for them until #486 sub-issues C/D put the chamber on each mandate. See
  `technical_decisions.md#deux-chambres-interrogees`.
- In CI a candidate's `chambre` is also decided by **artifact merge order**, not only by
  the collection loop: `extract-an` (`--source an`) and `extract-senat` (`--source senat`)
  are two scoped passes whose raw profiles meet in `merge_raw_profile`, where
  `chambre = _prefer_non_empty(new, old)` lets the last one landing win. #488 fixed the
  default `--source all` path; this second path belongs to #486 sub-issue D.
- Profiles collected before 2026-08-18 carry amendements resolved through the
  old `numero`-keyed store: ~75% of a legislature's amendements are missing and
  ~40% of the remaining (member, amendement) links point at the wrong text/date/
  sort. The key is fixed and the frozen indexes rebuilt, but **the profiles
  themselves need a full regeneration** to be correct — no in-place migration is
  possible (the lost amendements were never written). See
  `technical_decisions.md#amendements-cle-uid`.
- `generate-data.yml`: `if: always()` upload/cache steps still don't survive
  a runner infrastructure `shutdown signal` (#228) for jobs that aren't
  matrix-sharded. `extract-an` is now sharded per-candidate (#344, see
  `technical_decisions.md#matrix-extract-an-par-candidat`) — the same
  mitigation for `extract-roster-groupes` (~750 members) remains deferred to
  the full-scale roster rollout, see `technical_decisions.md#seuil-couverture-groupe`.
- `generate-data.yml`: the weekly AN cache key may no longer be written back by
  `extract-an` / `extract-roster-groupes`. `extract-amendements-an` writes the
  exact key first, and `actions/cache` skips its post-job save after an exact
  key hit — so the ~290 MB of AN dumps each shard downloads would never be
  persisted. **Confirmed by run 32136438841 and fixed in #424**: amendements
  moved to their own `public-data-cache-amendements-*` key, AN jobs now list
  their cached directories explicitly (`technical_decisions.md#cache-cle-amendements-separee`).
- `minoritaire` position unhandled in JS: `classifyDateInHemicycle` /
  `classifyTexteInHemicycle` (in `web/UI_finale/src/data/pivotAdapter.js` and
  archived `web/old/v3/js/render.js`) only handle `"majorite"` and `"opposition"`.
  The value `"minoritaire"` (valid per `schema_pivot.py` `KNOWN_POSITIONS_HEMICYCLE`)
  falls through to `"indetermine"` / `non_distingue`, mis-bucketing texts/amendments
  from minority-group periods when the legislative reading-mode filter is active.
- `pivot_data/gouvernements/gouvernement-BAYROU.json` publishes 12 `membres[]`
  where the current code rebuilds 9 — 2 strict duplicates removed by #480, plus
  an `astrid-panosyan-bouvet` entry (`debut: 2026-02-04`, `actif: true`) the
  code no longer reproduces. The pre-commit loss check blocks on it, and will at
  the next `merge-and-pivot` run, independently of #487 that measured it (see
  `technical_decisions.md#id-pivot-sans-prefixe`).

## Ideas not yet scheduled

- `actions/checkout` is now the dominant per-shard cost in `generate-data.yml`:
  93–117 s measured per roster shard on run 32288588518, i.e. ~55 % of a shard,
  against ~65 s of actual extraction — and it is paid once per shard, so
  sharding multiplies it. A shallow/partial checkout (`fetch-depth`, sparse
  paths) would attack it, but the extraction jobs read the committed profile
  baseline, so what can be pruned has to be established first. Measure before
  deciding, see `technical_decisions.md#budget-execution-pleine-echelle-467`.

- `tests/test_amendements_download_modes.py` now dominates the suite: eleven
  teardowns wait 0.5 s each for a local HTTP server to stop — ~5.5 s of the
  11 s total (#473). The waits are part of the scenario under test (the three
  Range-download degradation states); shortening them means touching the module,
  not the test. Only worth doing if the CI job becomes a contention point.

- CI still deletes the partial amendements archive on download failure (#264
  `try/finally`), so it gains nothing from the byte-level resume of #241/#443
  between runs. The premise behind that deletion ("the archive is never reread
  to resume a download") stopped being true with cross-invocation resume.
  Reversing it trades weekly cache volume for resume — measure before deciding,
  see `technical_decisions.md#telechargement-an-trois-modes-defaillance`.

- Congrès scrutins (AN + Sénat at Versailles) are excluded from `votes[]`
  (`AN_SCRUTIN_UID_PREFIXE`): their numbering restarts at 1 inside the AN
  number space, so the only one published to date — the 2024-03-04 IVG
  constitutional vote — would cite the wrong source page and collide with AN
  scrutin n° 1 in group cohesion. Publishing it needs its own identifier and
  source URL, see `technical_decisions.md#votes-multi-legislature`.

- Refine thematic classifier: handle cross-theme items (e.g. tagged both
  `budget` and `sante`), add an explicit "non classifié" bucket instead of
  silently dropping low-confidence items.
- Evaluate surfacing `pivot_data/partis/` aggregates in a comparison panel
  (non-navigation context) rather than as a top-level tab.
- Senate adapter (votes/amendments/sponsored texts) — deferred, see
  `technical_decisions.md#hors-perimetre`. Also applies to the gouvernement
  view's `textes[]` (AN dossiers dump only, Senate-initiated bills not
  captured), confirmed in `technical_decisions.md#gouvernement-doc-cloture`.
- EU textes_portés/amendements via the official API — superseded by the
  Parltrack approach, see `technical_decisions.md#hors-perimetre` and
  `docs/extract-ue.md`.
- Precise ministerial portfolio title — no source identified, see
  `technical_decisions.md#hors-perimetre`.
- Extra-parliamentary bodies matching — homonym risk, see
  `technical_decisions.md#hors-perimetre`.
- Syceron (comptes rendus de séance) AN open data — fetch/caching, parse XML -> `interventions[]` et index `acteurRef -> interventions` implémentés ; intégration éditoriale aval encore à planifier. Voir `docs/an_opendata.md`.
- Agenda/committee meetings dataset — low priority, see
  `technical_decisions.md#hors-perimetre`.
- Mayors — no dedicated collection module yet.
- Consolidate `test_quality_gate_syceron.py` and `test_quality_gate_groupes.py`
  (added by #193 for `_report_groupes`) into a single `test_check_quality_gate.py`
  covering all sections of `check_quality_gate.py`.
- `gouvernement_textes.py`: `AMO30` fallback for government-origin detection
  on dossiers without a "Projet de loi"/"Proposition de loi" title prefix
  (2355/3044 dossiers, mostly motions/résolutions/rapports) — needs mandate-date
  vs. deposit-date filtering to avoid the ~15% false-positive rate measured
  in #207 (ex-minister co-signatories). See `technical_decisions.md#gouvernement-textes-statut`.
- Surface `textes[].initiateurs` (minister → bill link, #435) in the
  gouvernement view: the data layer carries it, `web/` does not display it yet.
  Also unmeasured by `audit_gouvernement_dataset.py`/`check_quality_gate.py`
  (no coverage indicator for resolved vs. raw-`acteurRef` links, 556/1213
  today). See `technical_decisions.md#gouvernement-textes-initiateurs`.
- #431 (normalising `amendements[]` in profiles) is unblocked now that the store
  is keyed by `uid`, but its baseline must be re-measured: its 4 246 026 pairs /
  67 058 distinct amendements were counted on collapsed data. The shared
  deduplicated list is to be a single global file (arbitrated 2026-08-18); it
  will exceed GitHub's 100 MB blob limit, so it needs the same treatment already
  applied twice in this repo — per-actor sharding (#392) or gzip as for the
  frozen legislatures. See `technical_decisions.md#amendements-cle-uid`.
- Audit temporal-range cross-tables (`compute_plage_dates_*`, #316): no
  alerting on threshold yet (e.g. "profile doesn't cover the current
  legislature") — raw min/max indicator only. See
  `technical_decisions.md#audit-plages-temporelles`.
- `schema_groupe.py`: `amendements_agreges` has no date field, so its audit
  temporal-range cell is always `null` — schema change, out of scope for
  #316. See `technical_decisions.md#audit-plages-temporelles`.
- Same unconditional `meta.genere_le` re-stamping pattern as #343 (fixed for
  candidate pivots via `preserve_stable_freshness_timestamps`) likely applies
  to `group_profile.py`/`gouvernement_profile.py`/`parti_profile.py`, which
  rebuild their output unconditionally on every run with no old-vs-new
  content comparison — not confirmed with a real repro, out of scope for #343.
- Rattacher `_build_organe_index` (#353) aux mandats/responsabilités du profil
  député (commissions avec rôle, groupes d'amitié, engagements
  extra-parlementaires, groupe déclaré) : ces champs restent sourcés
  uniquement depuis NosDéputés après #355 (identité bio seule basculée vers
  l'AN). Voir `technical_decisions.md#bascule-identite-an-primaire`.
