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
- **Ministerial function granularity**: `mandats[].categorie ==
  "fonction_gouvernementale"` (position `"gouvernement"`) is sourced from the
  AN `acteurs_historique` bulk dataset (`organe.codeType == "GOUVERNEMENT"`),
  which only identifies *which* government (e.g. "BORNE", "CASTEX") an elected
  official belonged to and the dates — it does not carry the specific
  portfolio title (e.g. "Ministre de l'Intérieur"). No open-data source for
  the precise portfolio has been identified yet.
- **Senate votes/amendements/textes portés**: explored `data.senat.fr`'s open
  data catalog (2026). Findings: no structured roll-call vote dataset exists
  at all (unlike AN's `Scrutins.json.zip`) ; `ameli.zip` (amendments) is a raw
  717 MB SQL dump (`ameli.sql`), not per-senator JSON/CSV, impractical to
  download/parse on every run ; `dossiers-legislatifs.csv` has no
  author/sponsor field, so per-senator sponsored texts would require scraping
  individual `dossier-legislatif` HTML pages (fragile, out of pattern with the
  rest of this project's official-JSON-based sources). A full Senate pipeline
  equivalent to the AN one is therefore not currently feasible without a
  fragile HTML-scraping approach.
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

- Senate-specific adapter for vote and sponsored-text data — **on hold**, see
  Data coverage gaps above (no viable structured source found as of 2026).
- Fix `minoritaire` JS classification (see Known issues).
- Evaluate surfacing `pivot_data/partis/` aggregates in a comparison panel
  (non-navigation context) rather than as a top-level tab.
