# AGENTS.md - Instructions for AI agents

This file contains what an agent must follow in **every** session: non-negotiable
rules, schema conventions, and validation constraints. For the historical
"why" and the detailed rationale behind each decision, see
`docs/technical_decisions.md` (referenced section by section below) - do not
duplicate that content here.

Also see `README.md` for repository structure, commands, source taxonomy,
coverage limits, editorial neutrality, and roadmap.

---

## 1. Product

**Empreinte politique** - baseline "Politics made clear". Factual, sourced
political CVs (mandates, votes, sponsored texts, interventions) for 2027
presidential candidates. `CONTRECHAMP` (`web/`) is the design lab that displays
the same underlying data (`pivot_data/`) across multiple visual directions - it
is not a second product. `v3` is the editorial reference version.

Positioning details, naming history, target audience:
`docs/technical_decisions.md#positionnement`.

## 2. Non-negotiable editorial rules

These rules are intentionally duplicated in code (`schema_pivot.py`,
`validate_profil()`) and `web/v3/methodologie.html`. Any schema/display change
must preserve them:

1. No value judgments, no score, no ranking.
2. Full traceability: every fact must map to a primary source.
3. No individual attendance rate is ever published.
4. A 49.3 procedure is never treated as a vote position (separate procedural fact).
5. Missing data means missing data, never default `0`.
6. `position_dans_hemicycle` always requires a verifiable `source_url`
   (technically enforced by `validate_profil()`).
7. Group ratios are published only with numerator + denominator + sufficient
   coverage; otherwise `N/D`. Individual-vs-group gaps are **internal quality
   control** only, never public.
8. Thematic tags are reading aids, not declared candidate positions - even when
   harmonized (see Section 4), they are classification categories, not validated
   political stances.

## 3. Pipeline

```
Public sources (APIs/dumps)
        |
        v
raw_data/profiles/<slug>.json          <- candidate_profile.py / candidate_profile_ue.py
        |  normalize_nosdeputes.py / normalize_europarl.py
        v
pivot_data/profiles/<slug>.pivot.json  <- pivot schema (schema_pivot.py)
        |
        |- group_profile.py   -> pivot_data/groupes/  (schema_groupe.py)
        `- parti_profile.py   -> pivot_data/partis/   (schema_parti.py)
                |
                v
        check_quality_gate.py  (pre-commit gate — see below)
```

- `raw_data/` = source-near, not harmonized across chambers.
- `pivot_data/` = only layer `web/` should read.
- Groups are generated from `raw_data/groupes_reels.json` (manually validated
  list); `group_roster.py` performs 1 network fetch per `(chambre, legislature)`,
  never 1 per group.

**Additive merge (`merge_profile.py`)**: a regeneration never overwrites already
collected data.
- `votes`, `mandats`, `interventions` -> purely additive, old entry wins on key
  collision (`merge_lists_by_key`).
- `amendements`, `textes_portes` -> new entry wins on key collision
  (`merge_dossier_records`), because regeneration can refine known
  outcome/stage data.
- Scalar fields: new value if populated, otherwise keep old value
  (never regress to `null`).
- Full rationale + exception history:
  `docs/technical_decisions.md#fusion`.

**CI/CD workflow (`.github/workflows/generate-data.yml`)**: two modes
controlled by the `fresh_run` boolean input.
- `fresh_run=true` — full purge, no cache restore, `--no-merge`, groups
  recreated from scratch, quality gate threshold=0 (zero tolerance).
- `fresh_run=false` — no purge, cache restored, additive merge, groups with
  `--merge-existing`, threshold=`inputs.threshold` (default 3).
Commit/push only happens if `check_quality_gate.py` exits 0.
See `docs/technical_decisions.md#ci-cd` for full rationale.

**Quality gate (`src/check_quality_gate.py`)**: runs before every automated
commit. Hard fail (exit 1, blocks commit) on: IncompleteRead count > threshold,
missing/invalid/schema-failing groupe file. Soft warnings (commit allowed) on:
low intervention counts, low groupe coverage, network signals.

## 4. Pivot schema v1 (`src/schema_pivot.py`)

| Key | Content |
|---|---|
| `id` | `"<source>:<identifiant_source>"` |
| `nom`, `chambre`, `parti`, `groupe` | `chambre` in `{AN, Senat, PE, mairie, null}` |
| `identite` | Nullable bio block |
| `sources[]` | `{type, url, synchro_le}` |
| `mandats[]` | Elections, committees... + sensitive fields (Section 5) |
| `votes[]` | One record per vote |
| `textes_portes[]` | Author/reporter/co-reporter + procedural stage |
| `amendements[]` | Outcome + inadmissibility/rejection distinction |
| `interventions[]` | Speeches, questions (`type_detail`) |
| `tags_thematiques[]` | Harmonized thematic categories - 8 stable categories (`theme_taxonomy.STABLE_THEMES`), via `classify_keywords()` in `normalize_nosdeputes.py`. No longer raw keyword strings. |
| `meta` | `schema_version`, `genere_le`, `licence_donnees`, `warnings[]` |

Conventions: French `snake_case` everywhere; missing field = `null` (never `""`
nor `0`); closed categorical values live in `frozenset KNOWN_*` and are
validated by `validate_profil()` - extend the frozenset, never bypass
validation.

## 5. Sensitive institutional fields (validation constraints)

- `mandats[].position_dans_hemicycle`: never allowed without `source_url`
  (rule 6).
- `mandats[].suspendu_pour_fonction_gouvernementale`: never confused with a
  completed mandate.
- `votes[].type_vote == "motion_censure"` requires `texte_lie_id`; 49.3 ->
  `sort = "adopte_sans_vote_49_3"`, never any associated "position"
  (rule 4).
- `amendements[].sort == "irrecevable"` requires
  `base_juridique_irrecevabilite` (`"art. 40"` or `"art. 45"`) - procedural
  rejection is not rejection on the merits.
- `amendements[].type_deposant` distinguishes government/reporter/MP - never
  aggregate adoption rates without this detail (editorial metric rule,
  Section 6).

Edge-case history (2026 `textes_portes` bug, frozen NosDeputes 16th legislature,
etc.): `docs/technical_decisions.md#cas-limites`.

## 6. Metrics: public vs internal

| Metric | Status |
|---|---|
| `textes_portes[]` (if stage >= `examine_commission`) | Public |
| `amendements[]` raw counts + `par_type_deposant` | Public |
| Adoption rate aggregated across all submitter types | **Never** (misleading, mixes government/MP) |
| `votes[]` bill vote (`vote_texte`, latest reading) | Public |
| 49.3 / no-confidence motion | Public, labeled as procedural fact |
| Individual attendance/presence | **Never public** (rule 3) |
| Group `cohesion_votes[]` | Public, with numerator/denominator |
| Individual gaps vs group cohesion | Internal only (`--rapport-interne`) |
| `mandats[].notableCount` | Internal only (display ordering only) |
| `tags_thematiques[]` (harmonized, 8 categories) | Public |

Full rationale per metric: `web/v3/methodologie.html` (public page) - do not
duplicate prose here, only keep the public/internal status above.

## 7. Sources and licenses (reuse implications)

| Source | License | Constraint |
|---|---|---|
| NosDeputes.fr / NosSenateurs.fr | ODbL | Share-alike if `pivot_data`/`raw_data` are published as downloadable datasets |
| data.assemblee-nationale.fr | Open License (Etalab) | Attribution only |
| Parltrack | CC0 / ODbL (mixed) | Share-alike for ODbL parts if republished |
| European Parliament Open Data Portal | CC BY 4.0 | Attribution only |
| French Wikipedia | CC BY-SA 4.0 | Applies only to verbatim quotes (not current use) |
| Wikidata | CC0 | No restriction |

The site (HTML pages) is an ODbL "Produced Work" (attribution is sufficient).
A freely downloadable raw data export would trigger share-alike obligations.
Full details: `docs/technical_decisions.md#licences`.

## References

- `README.md`: commands, structure, coverage limits, roadmap.
- `src/schema_pivot.py`, `schema_groupe.py`, `schema_parti.py`: structure contracts.
- `src/check_quality_gate.py`: pre-commit quality gate (4 sections: IncompleteRead,
  coverage, low interventions, groupe validation). Hard vs soft fail logic.
- `docs/an_opendata.md`: actual AN open-data JSON schemas.
- `docs/hatvp_opendata.md`: conclusions on lobby-register linking (HATVP) - out of short-term scope, with rationale.
- `docs/technical_decisions.md`: full history and rationale (see anchors above: `#positionnement`, `#fusion`, `#cas-limites`, `#licences`, `#ci-cd`).
- `ROADMAP.md`: next steps (current, not read automatically by agent unless requested).
