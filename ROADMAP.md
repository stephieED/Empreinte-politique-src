# ROADMAP — Empreinte politique

## Known issues

- **`minoritaire` position unhandled in JS** (`web/v3/index.html`):
  `classifyDateInHemicycle` / `classifyTexteInHemicycle` only handle `"majorite"`
  and `"opposition"`. The value `"minoritaire"` (valid per `schema_pivot.py`
  `KNOWN_POSITIONS_HEMICYCLE`) falls through to `"indetermine"`, mis-bucketing
  texts/amendments from minority-group periods when the legislative reading-mode
  filter is active.

## Data coverage gaps

- **17th legislature freshness**: `groupe`/`identite.groupe_sigle` are frozen on
  the 16th legislature (pre-dissolution 2024). A new adapter against
  `data.assemblee-nationale.fr` actors/organs datasets is needed for real-time
  group composition.
- **Senate votes**: no official structured vote source integrated yet (equivalent
  of AN open data for senators).
- **Mayors**: no dedicated collection module or source.
- **Intervention completeness**: full-text name search can be partial for
  ambiguous names.

## Thematic taxonomy

The 8 stable categories in `theme_taxonomy.STABLE_THEMES` cover the main policy
areas. Future work: refine the classifier for cross-theme items (e.g. a text
tagged both `budget` and `sante`), and add a "non classifié" explicit bucket
rather than silently dropping low-confidence items.

## Next features

- Senate-specific adapter for vote and sponsored-text data.
- Fix `minoritaire` JS classification (see Known issues).
- Evaluate surfacing `pivot_data/partis/` aggregates in a comparison panel
  (non-navigation context) rather than as a top-level tab.
