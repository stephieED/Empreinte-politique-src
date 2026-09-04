<!-- Extrait d'`AGENTS.md` par #737. Ces règles ne changent pas de nature en
changeant de fichier : elles restent des instructions, et un renvoi
« AGENTS.md §3a » continue de les désigner — `AGENTS.md` en garde la ligne
d'index. Ce qui change, c'est qu'un lot qui ne touche pas ce domaine n'a plus à
les charger, ni à les faire grossir. -->

# §3a — Fichiers, index, fusion

### 3a. Files, indexes, merge

- **Build `pivot_data/scrutins.json` before any pivot pass, and merge it additively.**
  Resolving a ballot's `legislature` is a corpus-wide join, never per-profile.
  → `docs/decisions/normalisation-votes.md`
- **Build `pivot_data/amendements/<legislature>.json` after the pivot pass, once, and
  merge it additively** — with `build_amendements_index_pivot.py`, not
  `build_amendements_index.py` (the raw AN index). `amendement_id` is `an:<uid AN>` and
  the legislature is read **inside** the uid, never derived from the date. Co-signatures
  live in a companion file and are **never deleted**: no consumer reads them, a
  co-signature network is analysis material (#324).
  → `docs/decisions/normalisation-amendements.md`
- **A `texte_vise` is the AN document's uid, never its label (#639).** Each index file
  carries an optional `textes` table (`texte_vise` → `{dossier_id, titre}`), filled
  uid-to-uid from `document.dossierRef` — never by matching a label, not even an exact
  one. A texte with no resolved dossier has **no entry**, and the count is printed.
  **The published index does not heal on its own (#696)**: the additive merge lets a
  populated label win, so the remedy is the named backfill
  `amendements_index.backfill_texte_vise`, run between the merge and `resoudre_textes`,
  reading the sourced uid from `raw_data/amendements_an_figes/<legislature>/`. Its
  criterion is the AN uid **grammar** (`textes_vises_figes.est_uid_texte`), and it is
  wired on **both** call paths: CI never goes through `build_amendements_index_pivot.py`.
  → `docs/decisions/dossier-des-amendements-639.md`,
  `docs/decisions/report-texte-vise-source-696.md`
- **Both shared indexes must be in the workflow's `git add`** — and since #715 so must
  `raw_data/correspondance_acteurs_an.json`, which the run now extends. They are the only
  cross-file dependencies inside `pivot_data/`; an uncommitted index leaves every mapping
  pointing at nothing, silently, and an uncommitted correspondence table rewrites its
  derived entries every run, so the slug freeze it exists for never happens.
- **Individual profiles are written compact, everything else `indent=2`** (`src/json_io.py`).
  Never read a profile line by line — the format carries no meaning.
  → `docs/decisions/profils-json-compact.md`
- **A tool that walks the corpus reads it by projection, and never keeps a document
  (#628).** 623 Mo of JSON on disk is ~2,6 Gio of Python objects (measured inflation:
  × 4,2), and the machine has 4 Gio free with the swap full — an accumulating loop is
  `exit 137`, not a slowdown. Read one profile, reduce it to the blocks your measures
  actually open (declare them in a whitelist), release it. **A ceiling that is not in a
  test is a ceiling nobody re-checks**: measure `ru_maxrss` in a subprocess over fixtures
  and derive the ceiling from the on-disk weight of the blocks you must not keep — never
  from what you observed. Three accumulations remain, named and measured in the decision.
  → `docs/decisions/audit-599-projection-blocs-lus-628.md`
- **Read raw profiles through `src/profil_brut.py`, never `json.load` directly (#580)** —
  a raw profile is a socle plus one amendment slice per legislature, and a broken
  partition must raise `PartitionIllisible`, never return an empty list.
  → `docs/decisions/partition-profils-legislature-580.md`
- **The biggest versioned file is a watched guard-rail with a written course of action
  (#580).** `src/garde_fou_blobs.py` is **§7 of `check_quality_gate.py`**: warn at
  50 MiB, **fail the commit at 80 MiB**. Neither "raise the threshold" nor "delete data"
  is an available remedy.
  → `docs/decisions/partition-profils-legislature-580.md#garde-fou-blob-580`
- **Additive merge (`merge_profile.py`): regeneration never removes collected data.**
  `votes`/`mandats`/`interventions` additive, old entry wins; `amendements`/
  `textes_portes` new entry wins, keyed on `amendement_id` / `dossier_id`, or on the
  `amendement_non_resolu` record — keying on the mapping alone collapses every unresolved
  entry into one. Scalars take the new value only if populated, and **never regress to
  `null`**.
  → `docs/decisions/collecte-vide-necrase-jamais.md`
- **A field added to the schema never reaches an already-collected entry on its own —
  and the fix is a named backfill, never a looser merge (#492, #639, #641, #696, #710,
  #718).** On a list, "old entry wins" and the key does not contain the new field, so the
  regenerated entry is discarded every run. On a scalar, "never regress to `null`"
  restores the very value the publication filter refuses — so **a publication filter runs
  on the COMPOSED block, after the merge, never on what the normaliser produced**. A
  backfill is strictly monotone: it fills only what is absent, it names its fields, and
  **it never touches the merge key** — widening the key to carry the new field is #668's
  defect. Each occurrence passed the whole suite: the test that was missing covered the
  **transition**, not the steps. #710 breaks one property of the family — it **removes** a
  value instead of filling one, so the loss is declared with `allow_declared_losses`.
  → `docs/decisions/qualification-perdue-a-la-fusion-639.md`,
  `docs/decisions/filtre-publication-apres-fusion-641.md`,
  `docs/decisions/creneau-de-seance-nest-pas-un-sujet-710.md`,
  `docs/decisions/categorie-source-des-mandats-718.md`
- **A merge key written `a or b` changes identity the day `a` fills in (#668).** #540 was
  a *sticky* key absorbing distinct entries; this is its mirror — the same dossier keyed
  on the fallback before the run and on `source_url` after, published twice (940 entries
  for 472 collected dossiers, 468 duplicates, 22 profiles, live). **An identifier, never a
  URL** (`dossier_id`, the raw stage's own `dossiers_legislatifs[].id`), and the residual
  `or` is neutralised by a **reprise**, not by the key: `clean_stale_textes_portes` drops
  an entry with no identifier only when an identified twin carries the same fallback.
  Dropping the `or` outright would collapse un-identified entries onto one `None` key
  (#432). **Before adding an `a or b` key, measure how much of the published corpus sits
  on each branch** — and a reprise nobody calls cleans nothing: this one was dead code for
  a whole remediation.
  → `docs/decisions/cle-fusion-textes-portes-668.md`
- **An empty collection never overwrites a non-empty one (#465)** — per field, not per
  profile, even under `--no-merge`. Lifted only by `--autoriser-collecte-vide`, and the
  preservation is always printed. "Zero observed" is not "collection failed" (§2 rule 5).
  → `docs/decisions/collecte-vide-necrase-jamais.md`
