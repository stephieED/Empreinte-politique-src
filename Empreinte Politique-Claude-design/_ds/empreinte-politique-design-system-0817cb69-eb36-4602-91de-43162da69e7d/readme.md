# Empreinte Politique — Design System

**Empreinte politique** ("Politics made clear") publishes factual, sourced political CVs — mandates, votes, sponsored texts, floor interventions — for candidates to the French 2027 presidential election. It aggregates open data (NosDéputés.fr/NosSénateurs.fr, the Assemblée nationale open-data portal, the European Parliament open-data portal, Parltrack, Wikipedia/Wikidata) into per-candidate and per-parliamentary-group profiles. **Every displayed fact must trace to a primary source; the project makes no value judgments, scores, or rankings.**

`CONTRECHAMP` is the project's internal interface-design lab (`web/` in the source repo) — a sequence of visual explorations (v1 through v7, plus thematic studies: cartography, geology, archaeology, architecture). **`web/v3` — codename "the deconstructed variant" — is the editorial reference and the sole basis for this design system.** Its navigation is **Candidats · Groupes** (real parliamentary groups) — there is deliberately no "Partis" tab; `pivot_data/partis/` is an internal editorial aggregate, not a public product surface.

## Sources

- GitHub repo: [stephieED/Empreinte-politique-src](https://github.com/stephieED/Empreinte-politique-src) (branch `main`) — explore `web/v3/` (HTML/CSS/JS, no build step) for the live reference UI, `docs/design_intent.md` for the full rationale behind each `web/v*` visual direction, `docs/technical_decisions.md#positionnement` for positioning/naming/audience, and `AGENTS.md` for the non-negotiable editorial rules baked into the schema. Re-explore the repo directly for anything this design system simplified away.
- No Figma file, slide deck, or brand-guideline document was attached — everything here is reverse-engineered from `web/v3`'s actual markup, CSS and JS.
- No logo or brand mark exists in the source repo — none was invented here. Wherever a mark would go, the wordmark ("Empreinte politique") is set in Archivo Black.

## Content fundamentals

- **Language**: French. Formal but plain — no marketing voice, no second person ("vous"/"tu") address to a reader; copy describes the data, not the visitor.
- **Tone**: neutral, procedural, precise. Sentences read like methodology notes, not persuasion ("Un texte est affiché seulement si le pivot fournit un rôle factuel…"). No adjectives characterizing a candidate's positions.
- **Never**: value judgments, rankings, scores, adoption rates presented as performance, individual attendance/absence rates. A missing fact is displayed as missing (`N/D`), never as zero.
- **Numbers get a caveat.** Every raw metric (KPI cards, vote counts) ships with an explicit statement of what it does *not* measure — "mesure la durée, pas l'implication" — surfaced on-demand (KPI flip-card back face) rather than omitted.
- **Sourcing is visible inline**: dates, scrutin numbers and source names render in monospace next to the fact they support (`.source-ref`), functioning as a citation, not decoration.
- **Section labels are dateline-style**: small uppercase monospace kickers ("Présidentielle 2027 / données publiques") precede headlines, evoking wire-service/editorial framing.
- No emoji anywhere in the source.

## Visual foundations

- **Palette**: `offwhite` (#F2F0E7) page background, `ink` (#11110F) for text and 2px structural rules, `muted` (#5E5C55) secondary text. One functional accent, `blue` (#006FEE) with a pale `blue-soft` (#B9DEFF) tint for active/selected states. Two flat, unmixed "flag" colors carry no fixed meaning on their own but mark navigation/emphasis: acid yellow-green (`#DFFF00`) for nav chrome and highlighted cells, pink (`#FF70A6`) for coverage/warning notes. Two colors are reserved strictly for vote semantics and never used decoratively: vote-pour green (`#007A45`), vote-contre red (`#E53420`). A six-step outcome scale (adopté/rejeté/retiré/tombé/irrecevable/non_soutenu) extends the same logic for amendments. Max ~2 background colors active on a given screen at once, per the brand's own restraint.
- **Type**: three families, each with one job. **Archivo Black** for display/headlines — always uppercase, tight leading (~0.85), tight/negative letter-spacing, no italics. **Space Grotesk** for UI and body copy. **IBM Plex Mono** for anything that is *data*: KPI values, source references, dates, badges, buttons, tab labels — monospace is the project's visual signal for "verifiable, not decorative."
- **Spacing**: strict 8px grid (8/16/24/32/40/64), plus a few fluid `clamp()` values for hero/section padding and type that scale with viewport rather than breakpoint-jump.
- **Borders & radius**: 2px solid ink rules are the primary structural device (masthead, dock, grid cells) — the layout is drawn with lines, not shadows. Radius is **0px everywhere** in the deconstructed variant (no soft corners at all — a deliberate break from the softer, rounded-corner `.panel`/`.cockpit` variants explored earlier in `web/v1`–`v2`, which this design system does not carry forward).
- **Shadows**: none. Depth comes from solid color blocks and rules, never elevation/blur.
- **Backgrounds**: flat color fields only — no photography, no gradients (aside from a decorative diagonal tint used sparingly on avatar placeholders in earlier variants, dropped here), no textures, no illustration. Full-bleed color blocks (ink hero sections, acid nav bars) are the main "imagery."
- **Layout**: an asymmetric editorial grid — a 6-column grid where KPI/candidate/group cells span uneven widths (3+3+4, or 2-up on mobile) rather than uniform tiles; this asymmetry is intentional and recurring, not an artifact.
- **Motion**: minimal. KPI cards flip on hover/click (flat, no 3D perspective, in the deconstructed variant — earlier "cockpit" variant used a real 3D `rotateY`). Panel switches are instant, no easing curves to speak of beyond a short `opacity`/`transform` fade.
- **Hover/press states**: hover = solid fill invert (acid or ink), not color-shift or lightening. No press/shrink animation.
- **Color use in imagery**: n/a — there is no photography in the reference UI.
- **Transparency/blur**: `backdrop-filter: blur()` only on two sticky/fixed chrome elements (theme filter dock, bottom panel nav) so content can scroll underneath without chrome looking flat against it — never decorative.
- **Cards**: no shadow, no rounded corners, 1–2px ink borders (or none — many "cards" are just grid cells separated by rules, not bordered boxes at all).

## Iconography

- **No external icon font or CDN icon set.** Every glyph in `web/v3` is a small hand-built inline SVG (`viewBox 0 0 20 20`, `stroke-width 1.6–1.7`, round caps/joins, `stroke="currentColor"`, no fill) defined once in `js/config.js` and reused inline — copied verbatim into `assets/icons/*.svg` and into `components/core/Icon.jsx` here.
- No emoji, no Unicode-glyph icons, no PNG icons anywhere in the source.
- Icons are used sparingly and functionally: one per thematic tag (stéthoscope=santé, feuille=environnement, etc.), one per bottom-nav panel, and one per KPI card. Never purely decorative.

## Intentional additions

The source is a working web app, not a component library — there is no enumerated inventory to follow exactly. The primitives below were extracted from CSS classes/JS patterns that recur across `web/v3` (`avatar-carousel`/rail, `kpi-flip`, `vote-badge`, `outcome-bar`, `scope-bar-row`, `panel-dot`, `theme-pill`) rather than invented from a generic component checklist. No Button/Input/Dialog/Toast/etc. were added — the reference UI doesn't use them (its "buttons" are always one of the navigation/filter patterns below).

## Components

- **Core** — `Icon` (brand line-icon set), `Tag` (outline pill / theme filter chip / inverse-on-dark), `SectionKicker` (mono dateline label)
- **Navigation** — `ModeSwitch` (Candidats/Groupes segmented tabs), `CandidateRail` (typographic candidate/group index rail), `PanelNav` (fixed bottom section nav)
- **Feedback** — `VoteBadge` (pour/contre/abstention/absent), `OutcomeBar` (stacked amendment-outcome bar + legend)
- **Data** — `KpiCard` (flip KPI block: value + methodology caveat), `ScopeBar` (labeled filterable bar row), `VoteCard` (vote-record card with position-colored left border)

## Index

```
styles.css                  entry point — @import only
tokens/                      colors.css · typography.css · spacing.css · fonts.css
assets/icons/                19 brand SVG icons (thematic tags, panel nav, KPI cards)
components/
  core/                      Icon, Tag, SectionKicker            (+ core.card.html)
  navigation/                ModeSwitch, CandidateRail, PanelNav (+ navigation.card.html)
  feedback/                  VoteBadge, OutcomeBar                (+ feedback.card.html)
  data/                      KpiCard, ScopeBar, VoteCard           (+ data.card.html)
guidelines/                  colors-*.card.html · type-*.card.html · spacing-scale.card.html · brand-*.card.html
ui_kits/empreinte-politique/ index.html — interactive Candidats/Groupes profile recreation
  data.js                    illustrative sample data (candidate/group profiles)
  HomeView.jsx · CandidateProfile.jsx · GroupProfile.jsx
thumbnail.html               homepage tile
SKILL.md                     Claude-Code-portable skill wrapper
github.md                    source-repo sync record
```

## Caveats

- No Figma/brand-guideline source was attached — this system is reverse-engineered entirely from the `web/v3` HTML/CSS/JS. If a Figma file or brand deck exists, attach it and this can be tightened against ground truth.
- `web/v3` is one interface direction among several explored in the repo (`v1`, `v2`, `v4`–`v7`, plus `atlas-augmente`, `moodboard`, etc.) — this system intentionally follows only `v3` per the brief; the other explorations (cartography/geology/archaeology/architecture motifs in `docs/design_intent.md`) were read but not carried forward.
- Fonts are loaded via the same Google Fonts stack the source uses (Archivo Black, Space Grotesk, IBM Plex Mono) rather than self-hosted binaries — no substitution needed since the source itself uses Google Fonts, not custom font files.
- The UI kit uses illustrative sample data (plausible but invented vote/KPI values) for real 2027 candidates — it is a visual recreation only, not live output of the actual data pipeline.

**Ask**: tell me if there's a Figma file, more `web/v3` screens/states (comparison view, group member grid, methodology/mentions-légales pages) I should recreate, or specific components you want pulled from a different `web/v*` variant — happy to iterate.
