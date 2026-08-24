# ROADMAP — Empreinte politique

Short backlog: known bugs and ideas not yet scheduled. Not automatically
re-read by coding agents (unlike `AGENTS.md`) — consult on request.
Rationale for deferred items lives in
`docs/technical_decisions.md#hors-perimetre`; this file only tracks *that*
something is pending, not *why*.

## Known bugs

- Les deux groupes Sénat ont leur extraction **suspendue** depuis le 24/08/2026
  (certificat TLS expiré sur `archive.nossenateurs.fr`, runs `32463926808` et
  `32548486495`, #516) : leurs fiches publiées sont gelées. Reprise conditionnée à
  un certificat valide ou à une source de remplacement — sinon, trancher le retrait
  définitif. Voir `technical_decisions.md#extraction-groupe-suspendue-516`.
- `fetch_full_roster` fait **un seul essai** (timeout 15 s, aucun backoff) et chacune
  des 9 invocations d'un run reconstruit le roster pour elle-même : 18 requêtes par
  run, toutes devant passer. C'est ce qui a transformé une panne transitoire en run
  rouge le 21/08/2026 (#516). À corriger par un retry sur ce qui est retentable
  (timeout/`ConnectionError`/5xx, jamais `SSLError` ni 4xx) et un roster unique par
  run transité par artifact depuis `prepare-roster-matrix`.
- Les anomalies de `generate_roster_candidats.py` restent enterrées dans les logs de
  step : la seule annotation d'un run mort là-dessus est `Process completed with exit
  code 1`. Les émettre en `::error::` (#516).
- `extract-senat` traite ses candidats dans l'ordre du fichier et n'a ni `--resume`
  ni rotation : quand le budget de collecte du job (#514, 600 s) est épuisé par une
  source dégradée, ce sont toujours les mêmes premiers slugs qui l'ont consommé. Voir
  `technical_decisions.md#budget-collecte-source-injoignable-514`.
- `extract-roster-groupes` déclare `--budget-collecte-secondes 0` (absence de budget
  assumée, #514) faute d'une mesure sur ses 752 membres. À dimensionner si un shard
  roster meurt sur une source dégradée.
- 21 of the 207 profiles published as `chambre: "AN"` are known to the Senate's own
  roster, 18 with a still-open Senate mandate (measured 2026-08-20, #488). All but
  Retailleau are `roster_groupe`, so they are deliberately **out of scope**: no Senate
  group is aggregated, and their Senate past feeds nothing. #492 (sub-issue C) put the
  chamber on each **mandate**; #493 (D) made the profile level a derived `chambres` list.
  Neither corrects these 18 — they have **no `mandat_electif` at all**, so nothing can
  back a chamber for them, and #488 restricts bicameral collection to the 8
  `candidat_declare`. They now carry a `chambres du profil non corroborée` warning that
  says so. Correcting them is a **collection** matter, not a schema one. See
  `technical_decisions.md#deux-chambres-interrogees` and `#chambres-profil-derivees`.
- `mandats[].chambre` is `null` on 214 of the 228 published `mandat_electif` (189 profiles,
  measured on `f5a828b`): the stamp is written at collection (#492) and is not
  reconstructible for already-collected mandates. They fill in at their next real
  collection, via `merge_profile.backfill_mandat_chambre`. Each affected profile carries one
  `chambre de mandat électif non résolue` warning until then — the count is the migration's
  progress bar, not an anomaly. See `technical_decisions.md#chambre-par-mandat-electif`.
- The UI still shows one parliamentary experience per candidate. The data model no longer
  stands in the way — #492 carries the chamber on each mandate, #493 publishes the
  profile-level `chambres` list — but the values only become real after a full
  regeneration re-collects the 228 published `mandat_electif`, all still at
  `chambre: null`. #486 sub-issue F (#495) and #324.
- In CI a candidate's `chambre` is also decided by **artifact merge order**, not only by
  the collection loop: `extract-an` (`--source an`) and `extract-senat` (`--source senat`)
  are two scoped passes whose raw profiles meet in `merge_raw_profile`, where
  `chambre = _prefer_non_empty(new, old)` lets the last one landing win. #488 fixed the
  default `--source all` path. #493 narrowed this one without closing it: the **raw**
  profile's `chambre` is still order-dependent, but it now only feeds the *fallback* of
  `deriver_chambres()`, and both passes' mandates are merged additively — so a chamber
  established by a mandate can no longer be overwritten by arrival order. What arrival
  order still decides is the unbacked fallback value, which the profile now declares.
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
- `generate-data.yml`: the same #424 defect had reappeared on the two cache
  directories only `collect_interventions=true` ever fills. **Fixed in #505**,
  with a different mechanism than the one first diagnosed: `extract-roster-groupes`
  never wrote the weekly key (it runs behind `extract-an` by `needs:`), the
  dissociation was between the two **modes** of `extract-an` — one key for the
  ISO week, two possible contents. The key now carries the mode, the `path:`
  keeps only the per-legislature indexes (never the 650,5 MB of archives, measured),
  and the roster job is `actions/cache/restore` on both its cache steps.
  See `technical_decisions.md#cache-mode-interventions-505`.
- `generate-data.yml`: a `Read timed out` on NosDéputés made
  `generate_roster_candidats.py` overwrite the roster with **0 candidate** and exit 0,
  so the roster pivot pass iterated on nothing — run `32405297873` concluded
  `success` with 229 raw profiles for 209 pivots, the 20 members it had just
  collected published nowhere. **Fixed in #511**: the roster is never written on a
  failed fetch, a 0-member configured group, or an empty result (a shrink threshold
  was measured and rejected — a partial failure drops 452 or 300 of 752 at once, and
  is observable at its cause); and `src/audit_collecte_non_publiee.py` now reconciles
  collected against published before every commit. See
  `technical_decisions.md#collecte-non-publiee`.
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

- Syceron debates are collected, parsed and indexed but **never retained**:
  `_parse_syceron_intervention_entry` requires an `acteurRef` matching `PA\d+`,
  while the AN's `syseron.xml.zip` publishes a bare numeric speaker id
  (`<orateur><id>942</id>`). 0 of the 789 interventions in the 209 raw profiles
  come from Syceron; 115 of the corpus's 207 `PA<n>` ids appear unprefixed among
  the 730 speaker ids of legislature 17. Rebuilt locally with the prefix, that
  single legislature indexes **105 392 interventions for 674 speakers** (102,3 MB).
  Cost paid today for zero: 262,3 MB of archives and ~1,1 GB of extracted XML per
  shard, 118 s measured on `laurent-wauquiez` (#498). Fixing it is a collection
  change with a large data footprint, not a cache change — hence deliberately out
  of #505. Measured in `technical_decisions.md#cache-mode-interventions-505`.

- Senate speeches are collectable but never attributed: `fetch_intervention_details`
  resolves a speaker through the document's `url_nosdeputes` key, which
  `archive.nossenateurs.fr` never emits — it publishes `url_nossenateurs`. Every Senate
  intervention is therefore classified `mention` and dropped, which is why `extract-senat`
  now hard-codes `--skip-interventions` (#501). Reopening it means teaching that
  function the Senate key *and* confronting the archive's HTML with
  `_extract_speaker_identity_from_html`, for a body of work no aggregate consumes yet
  (#488). `tests/test_interventions_senat_non_retenues.py` fails the day the key is
  read. See `technical_decisions.md#interventions-senat-501`.

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
