# ROADMAP — Empreinte politique

Short backlog: known bugs and ideas not yet scheduled. Not automatically
re-read by coding agents (unlike `AGENTS.md`) — consult on request.
Rationale for deferred items lives in
`docs/technical_decisions.md#hors-perimetre`; this file only tracks *that*
something is pending, not *why*.

## Known bugs

- `generate-data.yml`: `if: always()` upload/cache steps still don't survive
  a runner infrastructure `shutdown signal` (#228) for jobs that aren't
  matrix-sharded. `extract-an` is now sharded per-candidate (#344, see
  `technical_decisions.md#matrix-extract-an-par-candidat`) — the same
  mitigation for `extract-roster-groupes` (~750 members) remains deferred to
  the full-scale roster rollout, see `technical_decisions.md#seuil-couverture-groupe`.
- `minoritaire` position unhandled in JS: `classifyDateInHemicycle` /
  `classifyTexteInHemicycle` (in `web/UI_finale/src/data/pivotAdapter.js` and
  archived `web/old/v3/js/render.js`) only handle `"majorite"` and `"opposition"`.
  The value `"minoritaire"` (valid per `schema_pivot.py` `KNOWN_POSITIONS_HEMICYCLE`)
  falls through to `"indetermine"` / `non_distingue`, mis-bucketing texts/amendments
  from minority-group periods when the legislative reading-mode filter is active.

## Ideas not yet scheduled

- `retry-generate-data.yml`: reduce redundant job-log downloads between the
  signature-detection step and the best-effort inputs-reconstruction step
  (up to 3-4 extra full log downloads in the same second, a likely
  contributor to the transient rate-limit diagnosed in #336) — see
  `technical_decisions.md#retry-generate-data-best-effort-non-bloquant`.
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
