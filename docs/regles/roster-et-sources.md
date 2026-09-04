<!-- Extrait d'`AGENTS.md` par #737. Ces règles ne changent pas de nature en
changeant de fichier : elles restent des instructions, et un renvoi
« AGENTS.md §3d » continue de les désigner — `AGENTS.md` en garde la ligne
d'index. Ce qui change, c'est qu'un lot qui ne touche pas ce domaine n'a plus à
les charger, ni à les faire grossir. -->

# §3d — Périmètre, sources, rosters

### 3d. Scope, sources, rosters

- **The Senate is out of scope, and `extract-senat` is retired (#528).** The decision is
  **editorial**, not technical: a renewed certificate changes nothing, and reopening
  requires the three written conditions of the decision's §7. Three loud refusals guard
  the non-return, frozen by `tests/test_retrait_senat_528.py`. **Kept**: the 2 published
  `groupe-Senat-*.json` (deleting a published file is a disappearance `audit_diff_profils`
  blocks), their `groupes_reels.json` entries, the Senate mandates already collected, the
  NosSénateurs ODbL attribution.
  → `docs/decisions/retrait-senat-528.md`
- **NosDéputés is out of the pipeline (#529).** The raw profile comes entirely from AN
  open data; `normalize_profil.py` (ex-`normalize_nosdeputes.py`) writes
  `sources[].type = assemblee_nationale`. **A counter structurally at zero, kept under
  watch, is #510's mute hole** — both NosDéputés counters went with the source. **Kept on
  purpose**, because they read the published corpus rather than collect: `nosdeputes`/
  `nossenateurs` in `KNOWN_SOURCE_TYPES` and `MAPPING_CHAMBRE_SOURCES`, the
  `meta.synchro_sources.nosdeputes` fallback read, and the `mots_cles` → `tags_thematiques`
  fallback. The published NosDéputés speeches **stay** — `interventions` is a blocking
  watched list. Guarded by `tests/test_retrait_nosdeputes_529.py`, which reads the
  **executed** code — strings and identifiers, never comments.
  → `docs/decisions/retrait-nosdeputes-529.md`
- **The slug ↔ AN actor correspondence is a committed artifact, not a heuristic (#525).**
  `raw_data/correspondance_acteurs_an.json` carries, per published slug, its `PA######`,
  the état civil, the **proof** (the AN fiche URL) and a verification date. A declared
  `hors_an` returns `None` with **no** name fallback; an *absent* slug does fall back; a
  missing table is a **declared** fallback. **Gate §5b hard-fails the commit naming any
  published slug with no entry**, threshold 0. `build_correspondance_acteurs_an.py`
  reconducts reviewed entries verbatim and **refuses to invent**.
  → `docs/decisions/correspondance-acteurs-an-525.md`
- **A roster member the table does not cover receives a fabricated slug — and a collision
  never does (#708).** The table was built from **published** profiles, so no new member
  could ever enter it: 156 of the 461 XVIIe roster entries were dropped in silence.
  `an_roster.resoudre_slugs` fabricates `text_utils.slugify(AMO30 état civil)` — the
  repo's **only** slug factory — with **the table always first**, which is what keeps a
  changed *nom d'usage* from moving an already-collected person's identifier (#487, #668;
  4 of #525's 10 écarts are noms d'usage). Three closed motifs receive nothing and are
  named and counted (`nom_absent`, `slug_deja_publie` — the slug belongs to **someone
  else**, `hors_an` included —, `homonymie_amo30`); the same slug borne by the **same**
  person is not a collision. Resolution spans the **whole** GP index, never the configured
  groups. **This does not relax #525**: fabricating is not filling a reviewed entry, gate
  §5b still hard-fails on publication, and #525 §7's retirement condition is unchanged.
  → `docs/decisions/slug-fabrique-membre-de-roster-708.md`
- **A fabricated slug still needs a table entry before publication — and that entry
  records a derivation, not a proof (#715).** A slug inherited from NosDéputés had its AN
  actor **discovered**, and a discovery is proved; a slug **derived from** the actor
  proves nothing. What the entry still buys is the **freeze**: the table comes before
  fabrication (#708 §3), so without it a changed *nom d'usage* moves the slug next run.
  Hence a closed `origine` key (`relue` | `derivee`) — **optional on read**, and never
  carried by `ecart`, since a derived entry has none (the validator refuses both
  together). `--completer-derivees` is **additive**, **offline** (#524) and **disjoint**
  from `construire()`. Three filters keep it from being a rubber stamp: the table first,
  the profile must be **published**, and its `identifiants.an` must equal the roster's
  declared `acteur_ref` **exactly** — a disagreement writes nothing and exits 1. The
  authority on "who is fabricated" is `slug_origine`, which leaves #525 §6's refusal
  intact. Wired into `merge-and-pivot` **after** the pivots and **before** the gate — and
  `raw_data/correspondance_acteurs_an.json` **enters the workflow's `git add`**, without
  which the freeze is an illusion. §5b publishes the count of `derivee` entries: a
  counter, not a threshold.
  → `docs/decisions/entree-derivee-correspondance-715.md`
- **The AN group roster comes from AMO30, and `AN_ROSTER_ACTIF` is a kill switch (#527)** —
  lowered → `RosterAnInactif`, never an empty roster. `ERREURS_ROSTER` unites both sources'
  failures so an absent archive stays a named « roster indisponible » (`exit 2`, committed
  sheets intact); a **slugless** member is counted and named (`ROSTER_SANS_SLUG`), never
  dropped without a word — **and since #708 that counter names collisions only**, a
  member with no reviewed correspondence now *entering* with a fabricated slug; the **published** `fraicheur_donnees` warning follows the flag,
  because naming a source the composition no longer comes from breaks §2 rule 2. **The
  double computation is NOT retired** — of #526 §9's three clauses only the first holds.
  → `docs/decisions/bascule-roster-an-amo30-527.md`
- **A roster derived from AMO30 obeys three measured traps (#526).** A mandate ending on
  or before the day the legislature's groups are constituted is a **transit**, and that
  date is *read* from the referential, never hard-coded; the AN sigle is
  `organe.libelleAbrev`, **not** `libelleAbrege`, and the published sigle → AN sigle(s)
  table is committed in `raw_data/groupes_reels.json`; one group can have **successive
  organs** in one legislature, so the roster is their deduplicated **union** with periods
  re-glued. An actor with no entry in #525's table gets `slug: None` **and** a named,
  dated line in `membres_sans_slug`. Guarded by `tests/test_an_roster.py`, on a
  **reduction** of the real archive — never a hand-written fixture (#510).
  → `docs/decisions/roster-an-derive-amo30-526.md`
- **A group's political position is the Assembly's own declaration, read from the
  committed table (#686).** `organe.positionPolitique` qualifies 40 of the 63 `GP` organs;
  the sheet publishes `position_politique` — `position`, `source_url` **required even on
  `non_declaree`** (mirror of §2 rule 6), `verifie_le`, and `organes[]` carrying each
  organ's **verbatim source string**. Wired through `correspondance_sigles_an`
  (`position_politique_an`), **never by sigle resemblance** — `RE` is not `REN`, and the
  direct match returned `None` on two sheets of five, the majority one included.
  `non_declaree` is a **published value**, never a vote-derived guess (§2 rule 1): the
  XVIIth's 14 groups are all in that case. Two successive organs that disagree publish
  **`divergente`**, never folded onto the last one; `position` must be **exactly** the
  summary of `organes[]`, so an invented posture is a schema error. **Gate §4b hard-fails,
  threshold 0**, on a published AN sheet with no entry. No rate, ranking or average by
  posture — the posture *explains* figures, it does not *correct* them.
  → `docs/decisions/position-politique-groupes-686.md`
- **A configured group's extraction can be suspended, never silently (#516).** A
  `groupes_reels.json` entry carrying `extraction_suspendue` is not fetched, not
  regenerated, **not counted as a failure**, and keeps its **hard** gate checks but not
  its soft ones. Suspending is not removing — removing deletes a published file, which
  `audit_diff_profils` blocks. The block requires `depuis`, `motif`, `references`,
  `condition_reprise`, and **the gate hard-fails without them**: a suspension with nothing
  left to re-read becomes permanent by omission.
  → `docs/decisions/extraction-groupe-suspendue-516.md`
- **Bicameral collection is for candidates only (#488)** — both chambers are queried only
  when `meta.provenance == "candidat_declare"`; a `roster_groupe` member keeps
  first-answer-wins. When both answer, the **first of `CHAMBRES` wins by documented
  convention**, and no mandate is ever merged across chambers. Two warnings reach the
  published `meta.warnings`: `carrière sur deux chambres` (candidates only) and `collecte
  de chambre en échec` (all profiles — a chamber silently picked by an outage is §2.5).
  → `docs/decisions/deux-chambres-interrogees.md`
- **A profile's chambers are derived, and the fallback is declared (#493).** **Call
  `appliquer_chambres()` after any mutation of `mandats[]`** — a derived field is
  recomputed, never merged. The collection chamber is always **unioned in**, never
  substituted and never dropped: removing an observed chamber is a deletion. The fallback
  is usable, not verified, and what keeps it from misleading is that it is **declared** —
  one `chambres du profil non corroborée` warning per profile (§2.5), whose corpus count
  is the migration meter. `chambre`'s retirement condition is written down; without a
  written criterion a transitional becomes permanent, as #431's and #432's read fallbacks
  did. **That warning declares one thing only: a published chamber that no stamped mandate
  backs (#486).** It does not restate the completeness of `mandats[]` — that is #492's own
  warning, recomputed on the **merged** mandates in both directions. Conflating the two
  would gage a profile-level field's retirement on a mandate-level completeness the
  additive merge cannot reach.
  → `docs/decisions/chambres-profil-derivees.md`,
  `docs/decisions/corroboration-chambres-publiees-486.md`
- **A group's eligibility window is chamber-scoped (#492)** — a union over all
  `mandat_electif` counted a member absent on ballots he could no longer vote, a false
  cohesion denominator (§2.7). A mandate with `chambre: null` is **kept** (excluding it
  would shrink a published denominator on missing data), and "no elective mandate at all"
  stays distinct from "elective mandates, none in this chamber".
  → `docs/decisions/chambre-par-mandat-electif.md`
