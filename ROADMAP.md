# ROADMAP — Empreinte politique

Short backlog: known bugs and ideas not yet scheduled. Not automatically
re-read by coding agents (unlike `AGENTS.md`) — consult on request.
Rationale for deferred items lives in
`docs/technical_decisions.md#hors-perimetre`; this file only tracks *that*
something is pending, not *why*.

## Known bugs

- `minoritaire` position unhandled in JS (`web/v3/index.html`):
  `classifyDateInHemicycle` / `classifyTexteInHemicycle` only handle
  `"majorite"` and `"opposition"`. The value `"minoritaire"` (valid per
  `schema_pivot.py` `KNOWN_POSITIONS_HEMICYCLE`) falls through to
  `"indetermine"`, mis-bucketing texts/amendments from minority-group
  periods when the legislative reading-mode filter is active.

## Ideas not yet scheduled

- Refine thematic classifier: handle cross-theme items (e.g. tagged both
  `budget` and `sante`), add an explicit "non classifié" bucket instead of
  silently dropping low-confidence items.
- Evaluate surfacing `pivot_data/partis/` aggregates in a comparison panel
  (non-navigation context) rather than as a top-level tab.
- Senate adapter (votes/amendments/sponsored texts) — deferred, see
  `technical_decisions.md#hors-perimetre`.
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
- Implementation of test_check_quality_gate.py (needs to integrate test_quality_gate_syceron.py)