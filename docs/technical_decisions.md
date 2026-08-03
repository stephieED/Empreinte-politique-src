# Technical decisions — history and rationale

This file documents the **why** behind the project's structural choices:
what is not visible when reading only the code or `AGENTS.md`.
`AGENTS.md` remains the reference for what an agent must follow in each
session (rules, validation constraints); this file is the long-term memory,
consulted on demand, not reread systematically.

Keep this up to date with every structural decision (new source, new
sensitive field, new edge case encountered).

---

<a id="positionnement"></a>
## Positioning

### Name

The product is called **Empreinte politique**. This is the name used in the
title of `README.md`, on the methodology page (`web/v3/methodologie.html`),
and in `meta.licence_donnees` for generated profiles.

The repository also hosts a portal called **CONTRECHAMP** (`web/index.html`),
which brings together several successive visual prototypes (`v1/`, `v2/`,
`v3/`, then more recent directions: `atlas-augmente/`,
`matiere-politique/`, and absorbed studies: `scene-cinetique/`,
`interface-essentielle/`, `revue-civique/`, `moodboard/`).
**CONTRECHAMP is an interface design lab, not a second product**: all of
these variants display the same underlying data (`pivot_data/`), only the
presentation changes. `v3` is currently the most editorially mature version
(it is the one that includes the methodology page).

### Target audience

Citizens, journalists, and fact-checkers who want to consult the
**factual, sourced** parliamentary track record of candidates in the 2027
French presidential election, without having to sift through open-data dumps
themselves. This is **not** a ranking tool, a quantified comparison between
candidates, or a political analysis website. The editorial baseline on the
methodology page summarizes the intent:
"Sourced facts, no performance score" / "Politics made clear."

---

<a id="fusion"></a>
## Additive merge and pipeline architecture

### Why two separate layers (`raw_data/` then `pivot_data/`) instead of a single format?

To add a new source (e.g., Parltrack, or one day a Senate equivalent)
without changing the format consumed by the frontend, and to keep debugging
possible at raw level if the pivot adapter has a bug.
`raw_data/` stays as close as possible to each source (one per API), not yet
harmonized across chambers. `pivot_data/` is the single format consumed by
the frontend (`web/`), independent from the source of origin - it is the
only layer `web/` should need to read.

### Group generation: avoid redundant network fetching

`group_profile.py` + `group_roster.py` + `generate_group_profiles.py`: the
list of real groups to generate is manually validated in
`raw_data/groupes_reels.json` (one entry per `(chambre, sigle, legislature)`
covering currently tracked candidates) - no automatic discovery.
`group_roster.py` fetches the full composition of a chamber for a given
legislature ONCE (`fetch_full_roster`), then `filter_roster_by_sigle`
filters it locally by acronym: this avoids one network call per group
(7 real groups in early 2026 -> 2 fetches instead of 7).
`generate_group_profiles.py` is the batch orchestrator called by
`.github/workflows/generate-data.yml`.

### Additive merge (`merge_profile.py`)

Principle: **a regeneration never removes data already collected**.
The public APIs in use are subject to transient issues
(moving pagination, occasional failed HTML requests...).
If we overwrote the existing file at every regeneration,
a transient issue could make real data disappear from one run to the next.

- **General lists** (`votes`, `mandats`, `interventions`, European mandates):
  merged via `merge_lists_by_key` with a **type-specific uniqueness key**
  (e.g., `(numero_scrutin, date)` for a vote) - purely additive:
  the old entry wins on key collision; only entries whose key does not yet
  exist are added.
- **"Case-file" lists** (`amendements`, `dossiers_legislatifs`/
  `textes_portes`): merged via a different function,
  `merge_dossier_records` - **the new entry wins on key collision**
  (unlike `merge_lists_by_key` above). Reason: for these two lists,
  a regeneration can legitimately correct a previously known value
  (e.g., refined `role`/`stade_procedural`, or an amendment `sort` moving
  from "in processing" to a final outcome) - always keeping the old version
  would freeze those corrections. Nothing is lost, however: an entry absent
  from the new collection is still preserved.
- **Scalar fields** (identity, group...): the new value is kept if present;
  otherwise we keep the old value (never regressing to `null` after a
  transient failure).
- **Deliberate exception to "never delete"**: `dossiers_legislatifs`
  (raw) / `textes_portes` (pivot) now discard, during merge,
  any entry without a known `role`. This is not a failure of the general
  rule but an explicit migration decision: the old source (NosDeputes)
  returned the same global list of files for everyone within a given
  legislature (`role` always `null` - see [Edge cases](#cas-limites)),
  so keeping these entries would preserve noise from a fixed bug rather than
  real lost data.

### Source-specific normalization logic

- **NosDeputes/NosSenateurs** (`normalize_nosdeputes.py`): translates the
  raw format from `candidate_profile.py` (one chamber at a time) into
  pivot format. Makes no network calls - this is a pure adapter.
- **European Parliament** (`normalize_europarl.py`): translates output from
  `candidate_profile_ue.py`. Categories such as `EU_INSTITUTION`,
  `COMMITTEE_PARLIAMENTARY_*`, `DELEGATION_*`... from the MEPs API are mapped
  to the pivot's closed categories (`mandat_electif`, `commission`, `autre`)
  via `_CATEGORIE_MAP`.
- **National Assembly (official open data)**: no separate adapter -
  `candidate_profile.py` directly queries bulk datasets from
  `data.assemblee-nationale.fr` (votes, amendments, actors, legislative
  files) and populates the raw format, which is then passed through
  `normalize_nosdeputes.py`. See `docs/an_opendata.md` for details of the
  actual JSON schemas (reverse-documented through sampling, not from official
  documentation, which is outdated/obsolete on several points).

---

<a id="cas-limites"></a>
## Edge cases already identified and their handling

- **49.3 / no-confidence motion**: `votes[].type_vote == "motion_censure"`
  requires `texte_lie_id` (checked by `validate_profil()`). A bill passed via
  49.3 gets `sort = "adopte_sans_vote_49_3"` on the bill vote, without any
  associated elected-official "position".
- **Inadmissibility vs rejection**: `amendements[].sort == "irrecevable"`
  requires `base_juridique_irrecevabilite` (`"art. 40"` financial
  admissibility, or `"art. 45"` relation to the bill / "legislative rider").
  Inadmissibility is a **procedural** rejection, never confused with a
  rejection on the merits.
  The `(etat.libelle, sousEtat.libelle)` mapping from AN open data was
  established empirically on ~3000 real amendments (see
  `_AMENDEMENT_SORT_MAP` and `docs/an_opendata.md`).
- **Suspension for government office**: a suspended mandate
  (a parliamentarian appointed minister, Art. 23 of the Constitution) must
  never be confused with a finished mandate -
  `mandats[].suspendu_pour_fonction_gouvernementale` carries a dedicated
  period `{debut, fin, suppleant_id}`.
- **Group change during a legislature**:
  `votes[].groupe_au_moment_du_vote` prevents retroactively attributing the
  current group to a past vote; on the group profile side,
  `membres[].fin_dans_groupe` + cohesion calculations only count members who
  were eligible on the date of each vote.
- **Fixed bug (2026): `textes_portes` was not person-specific.**
  The old source (NosDeputes, endpoint `/{legislature}/dossiers/nom/json`)
  takes no per-person parameter and therefore returned the **entire list** of
  files for the legislature, identical for everyone - `role` was always
  `null`, and the methodology page (which only displays an item if `role` is
  known) never showed anything in this section. Replaced, for MPs,
  by an index built from structured `initiateur`/`rapporteurs` fields in the
  AN bulk "legislative files" dataset (see `fetch_textes_portes_officiels` in
  `candidate_profile.py`). No official equivalent yet for senators
  (the field remains empty/unreliable on the Senate side).
- **"Party" (editorial) != "parliamentary group" (real)**:
  `schema_parti.py` aggregates declared candidates sharing the same party
  label (`raw_data/candidats.json`), who may have **no real common mandate**.
  This schema therefore deliberately excludes any vote cohesion or aggregated
  adoption rate - a comparator that would make no sense on a heterogeneous
  sample from 1 to a few candidates.
- **The NosDeputes.fr domain used (`nosdeputes.fr/deputes/json`) is actually
  frozen on the 16th legislature (2022-06-22 -> dissolution on 2024-06-09),
  not a "real-time" source for the ongoing 17th legislature.**
  Verified on 2026-08-01: all 618 entries have `mandat_fin` populated and
  `ancien_depute=1`. No equivalent "17th legislature" subdomain was found.
  Concrete consequence: `groupe`/`identite.groupe_sigle` derived from this
  source reflect the last known composition **before end-2024**, not the
  current real composition of a group - never present these fields as
  "up to date" without this caveat. Non-implemented path for real 17th
  legislature freshness: the "actors"/organs datasets of
  `data.assemblee-nationale.fr` (already used for votes/amendments/files),
  which would require a dedicated new adapter.
- **Title of a bill targeted by an amendment**: AN amendments open data
  exposes only a raw source code (`texteLegislatifRef`), not a readable
  title; resolved separately through the "legislative files" dataset
  (see `_build_texte_titre_index` in `candidate_profile.py`).

---

<a id="licences"></a>
## Sources and licenses - full details

| Source | Data type | License | Share-alike implications |
|---|---|---|---|
| NosDeputes.fr / NosSenateurs.fr (Regards Citoyens) | Mandates, groups, sponsored bills (legacy) | **ODbL** | **Share-alike on the database.** If `pivot_data/`/`raw_data/` are one day published/downloadable as a structured dataset (not only displayed on the website), they constitute a "derived database" under ODbL and must be offered under ODbL (or a compatible license), with attribution to Regards Citoyens. The rendered website (HTML pages in `web/`) likely qualifies as ODbL "Produced Work", which requires only attribution, not share-alike - but raw data export does require it. |
| data.assemblee-nationale.fr (votes, amendments, actors, files) | Roll-call votes, amendments, identity, sponsored bills | **Licence Ouverte / Open Licence (Etalab)** | Attribution only (state the source and update date); **no** share-alike obligation. Compatible with ODbL and CC BY, and therefore does not restrict the license under which our combined data can be published. |
| Parltrack | European Parliament mandates/bodies | **CC0 / ODbL** (mixed depending on internal Parltrack datasets) | Where a component is ODbL, the same share-alike obligation as NosDeputes above applies if republished as a database; CC0 parts impose no constraints. |
| European Parliament Open Data Portal | Mandates, committees, groups, EU votes | **CC BY 4.0** | Attribution only, **no** share-alike (unlike CC BY-SA). |
| French Wikipedia | Candidate monitoring | **CC BY-SA 4.0** | In practice, applies only if **verbatim text** (long quotations) is reused - we extract only factual points (dates, affiliation), not paragraphs; any future verbatim quote should still include attribution + mention of the same license. |
| Wikidata | Candidate monitoring | **CC0** | No restrictions. |

**Practical takeaway**: as long as the project only displays facts on web
pages ("Produced Work" website), attribution is sufficient for all sources.
The day `raw_data/`/`pivot_data/` are published as a **downloadable dataset**
(API, open-access CSV/JSON export), the ODbL share-alike obligation
(NosDeputes/NosSenateurs, and ODbL parts of Parltrack) applies: this
combined dataset should be offered under ODbL or a compatible license,
not under a more restrictive license.

---

## Internal references

- `AGENTS.md`: condensed version intended for AI agents (rules, schema,
  validation constraints) - this file only expands on its Sections 1-2 and 7.
- `README.md`: repository structure, generation commands, source taxonomy,
  known coverage limitations.
- `src/schema_pivot.py`: structure contract for individual profiles
  (exhaustive docstring + `validate_profil()`).
- `src/schema_groupe.py` / `src/schema_parti.py`: aggregation contracts for
  real groups / editorial party.
- `docs/an_opendata.md`: actual JSON schemas from AN open data
  (votes, amendments, actors, legislative files), reverse-documented by
  direct data sampling.
- `docs/hatvp_opendata.md`: finding on linking interest representatives with
  elected officials (out of short-term scope).
- `web/v3/methodologie.html`: public page describing editorial methodology.