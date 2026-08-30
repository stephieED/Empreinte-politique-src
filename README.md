# EMPREINTE POLITIQUE

![Projet en construction](https://img.shields.io/badge/PROJET-EN%20CONSTRUCTION-00E5FF?style=for-the-badge&labelColor=17141F)

> [!WARNING]
> **Ce projet est en construction.** Le pipeline et l'interface évoluent
> quotidiennement. Les données publiées sont réelles et sourcées, mais peuvent
> être incomplètes, et certaines absences portent encore une explication
> imprécise — ne pas conclure d'une liste vide sans lire son bloc `couverture`.
>
> L'état courant se lit dans les
> [issues ouvertes](https://github.com/stephieED/Empreinte-politique-src/issues).

Generates structured "political CVs" (mandates, responsibilities, votes,
legislative files, floor interventions) for candidates in the 2027 French
presidential election, using open data from the
[French National Assembly open data portal](https://data.assemblee-nationale.fr/)
(Licence Ouverte / Etalab) — the **only** French source since #529 —,
[Parltrack](https://parltrack.org) + the
[European Parliament Open Data Portal](https://data.europarl.europa.eu/)
(CC BY 4.0) for the European mandate dimension of former MEP candidates, and
Wikipedia/Wikidata for candidacy monitoring.

**Guiding principle**: every displayed fact must be traceable to a primary
source (official vote, legislative file, specific Wikipedia revision).
The project does not make value judgments.

## Repository layout

```
CV_CandidatFR/
|- src/                               # Python scripts
|  |- candidate_profile.py           # Collect raw profile for ONE FR deputy (AN open data only since #529)
|  |- candidate_profile_ue.py        # Build the "European mandate" section for ONE candidate
|  |- generate_all_profiles.py       # Batch: profiles for candidates in a --candidats list (candidats.json by default, or a roster-driven file)
|  |- generate_roster_candidats.py   # Builds a --candidats-compatible list from real group rosters (groupes_reels.json), for full group coverage beyond declared candidates
|  |- merge_profile.py               # Additive merge logic (old wins on lists, new wins on scalars)
|  |- normalize_profil.py            # Raw FR profile -> pivot adapter (was normalize_nosdeputes.py until #529)
|  |- normalize_europarl.py          # European Parliament Open Data -> pivot adapter
|  |- normalize_parltrack_dumps.py   # Parltrack dumps -> pivot adapter (EP mandates)
|  |- parltrack_dumps.py             # Parltrack dump download/cache helpers
|  |- syceron_debates.py             # AN Syceron comptes rendus: download, cache, acteurRef index
|  |- parse_syceron.py               # AN Syceron XML parser -> interventions[]
|  |- text_utils.py                  # Shared text helpers (normalisation, accent folding)
|  |- group_profile.py               # Aggregate individual profiles into a parliamentary group profile
|  |- group_roster.py                # Real group composition: AMO30 only (#527 switch, #529 removed the NosDeputes fallback)
|  |- an_roster.py                   # AN group composition derived from AMO30 (open data AN), incl. legislature 17 — production source since #527
|  |- generate_group_profiles.py     # Batch: all groups from raw_data/groupes_reels.json
|  |- groupes_config.py              # Shared read of groupes_reels.json + temporary extraction suspension (#516)
|  |- gouvernement_roster.py         # Ministerial roster of a government from local pivots (no network call)
|  |- gouvernement_profile.py        # Aggregate roster + legislative files into a full government profile
|  |- generate_gouvernement_profiles.py # Batch: all governments from raw_data/gouvernements_reels.json
|  |- parti_profile.py               # Editorial party aggregates from individual pivots
|  |- check_quality_gate.py          # Pre-commit quality gate + run summary (6 sections)
|  |- correspondance_acteurs_an.py   # Committed slug <-> AN acteur_ref table: load, validate, resolve loudly (#525)
|  |- build_correspondance_acteurs_an.py # Rebuild that table from published profiles + AMO30 (never invents an entry)
|  |- audit_pivot_dataset.py         # Pivot dataset audit: volumetry/completeness/consistency/freshness/warnings + JSON/Markdown report
|  |- audit_groupe_dataset.py        # Groupe dataset audit: same categories as audit_pivot_dataset.py + JSON/Markdown report
|  |- audit_gouvernement_dataset.py  # Gouvernement dataset audit: I/O + volumetry/completeness/consistency/freshness indicators (no CLI/Markdown yet, see #319)
|  |- audit_pipeline.py              # Manual tool: runs both audits above and compiles an overview + combined JSON/Markdown report
|  |- audit_integrite_referentielle.py # Pre-commit guard: every published key resolves in its shared index (#485)
|  |- audit_collecte_non_publiee.py  # Pre-commit guard: every collected raw profile has its pivot (#511)
|  |- audit_collecte_vs_publie.py    # Pre-commit guard: each published list carries what collection returned, per declared relation (#545)
|  |- schema_pivot.py                # Pivot schema v1 - common format across all sources
|  |- schema_groupe.py               # Group profile schema v1 (structure contract)
|  |- schema_parti.py                # Party profile schema v1
|  |- schema_gouvernement.py         # Government profile schema v1 (structure contract, no aggregation logic yet)
|  |- gouvernement_textes.py         # AN legislative files (bulk dump): government-origin filter + statut extraction
|  |- couverture_dossiers.py         # Ingested dossier archives (per legislature) + resulting coverage bound (stdlib only)
|  |- mep_profile.py                 # Collect/normalize EP profiles (Parltrack)
|  `- fetch_wikipedia_candidates.py  # Candidate monitoring via Wikipedia/Wikidata
|- raw_data/                          # Declarative inputs + raw outputs (non-normalized)
|  |- candidats.json                 # Candidate list (name, slug, party, status, sources)
|  |- groupes_reels.json             # Validated list of real groups to generate
|  |- gouvernements_reels.json       # Validated list of real governments (ministerial roster source)
|  |- correspondance_acteurs_an.json # Reviewed slug <-> AN acteur_ref table, with proof per entry (#525)
|  `- profiles/                      # Raw candidate profiles: <slug>.json
|- pivot_data/                        # Anything in pivot schema format (or derived)
|  |- profiles/                      # <slug>.pivot.json per candidate
|  |- scrutins.json                  # Shared deduplicated ballot list (#432)
|  |- amendements/                   # Shared deduplicated amendment list, one file per legislature (#431)
|  |                                 #   <leg>.json (meta) + <leg>.cosignatures.json (companion)
|  |- partis/                        # parti-<slug>.json: editorial party aggregates
|  |- groupes/                       # groupe-<SIGLE>-<leg>.json: real parliamentary group profiles
|  `- gouvernements/                 # gouvernement-<ID>.json: real government profiles
|- web/
|  |- UI_finale/                     # Production interface: React 19 + Vite (Candidats · Groupes · Gouvernement)
|  `- old/                           # Archived design generations (v1–v7, atlas, studies…)
|- docs/
|  |- workflow-generate-data.md      # The run, job by job — the entry point
|  |- pipeline-profiles-groupes.md   # What the data becomes
|  |- extract-roster-groupes.md      # The roster-driven job, in depth
|  |- decisions/                     # One file per architectural decision
|  `- sources/                       # External-source references — they drift with their provider, not with our code
|     |- an-opendata.md              # AN open data (votes, amendments, Syceron) — live, the pipeline's single source
|     `- nosdeputes/                 # NosDeputes/NosSenateurs API reference — historical, no longer queried since #529
|- tests/
|  |- test_candidate_profile.py
|  |- test_candidate_profile_ue.py
|  |- test_group_profile.py
|  |- test_group_roster.py
|  |- test_an_roster.py
|  |- test_generate_group_profiles.py
|  |- test_gouvernement_textes.py
|  |- test_gouvernement_roster.py
|  |- test_gouvernement_profile.py
|  |- test_generate_gouvernement_profiles.py
|  |- test_merge_profile.py
|  |- test_normalize_europarl.py
|  |- test_normalize_profil.py
|  |- test_normalize_parltrack_dumps.py
|  |- test_parltrack_dumps.py
|  |- test_parse_syceron.py
|  |- test_parti_profile.py
|  |- test_quality_gate_amendements.py
|  |- test_quality_gate_syceron.py
|  |- test_schema_groupe.py
|  |- test_schema_gouvernement.py
|  |- test_schema_parti.py
|  |- test_schema_pivot.py
|  |- test_syceron_debates.py
|  |- test_web_v3_issue_66.py
|  |- test_web_v3_issue_128.py
|  `- test_web_v3_mandate_timeline.py
`- README.md
```

- `.cache/` (auto-created, git-ignored): local cache for AN vote archives,
  Parltrack dumps, and European Parliament datasets to avoid re-downloading
  large and mostly static files.

## Schemas and transformations

See:

- `docs/sources/an-opendata.md` - practical AN Open Data references (dataset URLs,
  key fields).
- `docs/pipeline-profiles-groupes.md` - what the data becomes: sources, flow,
  schemas, volumetry and the six `pivot_data/` outputs (`profiles`, `groupes`,
  `partis`, `gouvernements`, `scrutins.json`, `amendements/`).
- `docs/workflow-generate-data.md` - what a run does: the eight jobs (what each one
  does, what it consumes and produces, and the decisions behind its shape), the
  launch form, caches, artifacts, budgets, the push, the automatic retry.
- `docs/extract-roster-groupes.md` - the one extraction job with depth of its own:
  rollout, regenerating existing profiles, the roster's three exit codes.
- `docs/decisions/<anchor>.md` - one file per architectural decision: full rationale,
  alternatives rejected, edge-case history.
- `docs/technical_decisions.md` - their index, newest first. A new decision is a **new
  file** plus one index line, never an edit inside an existing file (`AGENTS.md` §8).
- `AGENTS.md` - condensed non-negotiable rules for agents.

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

`requirements-dev.txt` pulls in `requirements.txt` (runtime dependencies) and
adds the pinned `pytest`. For a runtime-only environment, install
`requirements.txt` alone — that is what the extraction jobs do.

Run all commands below from the repository root with the virtual environment
activated.

## 1. Generate one candidate profile (AN)

```bash
python src/candidate_profile.py jean-luc-melenchon --chambre deputes
```

The Senate left the product's scope in #528: `--chambre senateurs` is refused,
and so is `--source senat` on `generate_all_profiles.py`. Reopening condition:
[`docs/decisions/retrait-senat-528.md`](docs/decisions/retrait-senat-528.md).

Default output: `raw_data/profiles/<slug>.json` — the **socle**, plus one
`raw_data/profiles/<slug>/<legislature>.json` slice per legislature holding the
amendments (#580). `--out` still names the socle; the slices are its sibling
directory. Read them back with `src/profil_brut.py`, never `json.load` alone.

| Option | Effect |
|---|---|
| `--chambre {deputes}` | Parliament chamber (only value since #528) |
| `--out path.json` | Change output file (must end in `.json` — it is the socle) |

## 2. Add the "European mandate" section

Some candidates are former MEPs (e.g., Jordan Bardella, Marine Le Pen,
Jean-Luc Melenchon). This section is fetched separately from the official
European Parliament Open Data Portal:

```bash
python src/candidate_profile_ue.py "Jordan Bardella"
# prints JSON to stdout; add --out path.json to write a file
```

Lookup uses exact full-name matching on normalized names (diacritics, case,
word order ignored) against the full MEP list for a country (`--country`,
default `FR`). Not found is not an error; it means no MEP record was found.
In practice, `generate_all_profiles.py` already invokes this automatically.

### Is this API legal to use?

Yes. `https://data.europarl.europa.eu/api/v2/` is published by the European
Parliament under **CC BY 4.0**. Two technical requirements are already
implemented in `candidate_profile_ue.py`:

- send a project-identifying `User-Agent` header;
- stay under **500 requests / 5 minutes**.

## 2 bis. Résolution de `legislature` sur les votes (#432)

`votes[].numero_scrutin` repart à 1 à chaque législature : la clé d'un scrutin
est `(legislature, numero_scrutin)`. Or 22,5 % des votes collectés ne portent
aucune législature (chemin de collecte antérieur à #403). Passe de corpus, sans
réseau, qui dit si la clé est utilisable — et ne modifie aucun fichier :

```bash
python3 src/audit_legislature_votes.py
python3 src/audit_legislature_votes.py --profils-dir pivot_data/profiles
python3 src/audit_legislature_votes.py --out audit/legislature_votes.md
```

Sortie 0 si tout est résolu, 1 sinon. Deux mécanismes, jamais confondus :
jointure sur un jumeau étiqueté (la donnée existe déjà ailleurs, étiquetée),
puis calendrier des législatures (une dérivation, tracée comme telle). Ce qu'ils
ne résolvent pas échoue bruyamment — jamais de valeur par défaut (AGENTS.md
§2.5). Rapport de référence : `audit/legislature_votes_20260819.md`.

## 2 ter. Index partagé des scrutins (#432)

Un scrutin est identique pour tous ses votants : seul `position` est propre au
membre. Son méta vit donc une seule fois dans `pivot_data/scrutins.json`, et un
profil ne garde que le mapping `{scrutin_id, position}`.

```bash
python3 src/build_scrutins_index.py                 # fusion additive avec l'existant
python3 src/build_scrutins_index.py --no-merge      # reconstruction complète (corpus COMPLET)
```

À construire **avant** toute passe pivot : `generate_all_profiles.py --pivot`
le fait automatiquement (`--scrutins`, `--skip-scrutins-index` pour ne pas le
refaire). Mesuré sur les 209 profils committés :

| | avant | après |
| --- | --- | --- |
| `votes[]` dans les profils | 179,8 Mo | 17,9 Mo |
| index partagé | — | 8,1 Mo |
| **total** | **179,8 Mo** | **26,0 Mo (−85,5 %)** |
| `cohesion_votes` des groupes | 6,23 Mo | 3,41 Mo (−45,3 %) |

Le même index sert les profils et les groupes : les 4 104 scrutins des groupes
sont tous inclus dans les 17 422 des profils. Un profil ne se lit plus seul pour
ses votes, et `sync-data.mjs` copie l'index dans `public/data/`.

## 2 quater. Index partagé des amendements (#431)

Même principe pour les amendements : seul `role_signataire` est propre au
membre, tout le reste — `sort`, `date`, `texte_vise`, `type_deposant`,
`premier_signataire` et surtout `co_signataires` — est identique pour tous les
signataires. Un profil ne garde que le mapping `{amendement_id, role_signataire}`,
avec `amendement_id = "an:<uid AN>"`.

```bash
python3 src/build_amendements_index_pivot.py               # fusion additive avec l'existant
python3 src/build_amendements_index_pivot.py --no-merge    # reconstruction complète (corpus COMPLET)
```

À ne pas confondre avec `build_amendements_index.py` (index **brut** des
archives AN, job CI `extract-amendements-an`) ni avec
`build_amendements_index_figees.py` (législatures closes, `raw_data/`).

`generate_all_profiles.py --pivot` reconstruit l'index automatiquement **après**
la passe pivot (`--amendements`, `--skip-amendements-index` pour ne pas le
refaire). Une seule reconstruction par run, là où les scrutins en demandent deux :
la clé d'un amendement est son `uid`, porté par l'enregistrement lui-même, donc
rien n'a besoin d'être résolu à l'échelle du corpus.

Mesuré sur les 209 profils committés :

| | avant | après |
| --- | --- | --- |
| `amendements[]` dans les profils | 1 342,4 Mo | 73,8 Mo de mapping |
| index partagé (méta) | — | 54,4 Mo |
| index partagé (cosignatures) | — | 75,7 Mo |
| **total** | **1 342,4 Mo** | **203,8 Mo (−84,8 %)** |

**Un fichier par législature**, plus un fichier compagnon pour les cosignatures :
un fichier global unique pèse déjà 130,1 Mo, au-delà de la limite GitHub de
100 Mo par blob, et un fichier de législature contenant aussi les cosignatures
atteindrait 120,3 Mo pour la XV<sup>e</sup> à couverture complète des archives.
Les cosignatures ne sont lues par aucun consommateur : `sync-data.mjs` ne les
copie pas vers le site, et `charger(..., avec_cosignatures=False)` les évite.
Elles ne sont jamais supprimées pour autant (#324).

### Vérifier que les clés publiées résolvent (#485)

Ces deux index font que `pivot_data/` n'est plus **auto-suffisant** : un vote ou
un amendement n'a de sens que si sa clé résout. Le contrôle qui le vérifie :

```bash
python3 src/audit_integrite_referentielle.py                    # tout pivot_data/
python3 src/audit_integrite_referentielle.py --sans-amendements # scrutins seuls, moins cher
python3 src/audit_integrite_referentielle.py --out audit/integrite.md --out-json audit/integrite.json
```

Sortie non nulle si une clé publiée ne résout pas, si l'index ou le shard visé
est absent, ou si une clé manque sans son enregistrement de repli — utilisable
comme garde-fou avant commit, et branché comme tel dans `merge-and-pivot`.

À ne pas confondre avec `audit_diff_profils.py`, qui compare **deux états** :
celui-ci vérifie une **invariance dans un seul**. Leurs tolérances sont
cloisonnées — `allow_declared_losses` ne désarme pas
`allow_broken_references`. Mesuré sur les 209 profils committés : 0
référence orpheline sur 1 347 451, 3,02 s / 162,0 Mio. Voir
`docs/decisions/integrite-referentielle-pivot.md`.

### Régénérer la table slug ↔ acteur AN (#525)

`raw_data/correspondance_acteurs_an.json` associe chaque slug publié à son
`acteur_ref` AN (`PA######`), avec l'état civil AMO30, la preuve (fiche AN) et
la date de vérification. Elle est **committée et relue** : le pipeline la lit,
il ne la recalcule pas.

```bash
python3 src/build_correspondance_acteurs_an.py             # complète et réécrit
python3 src/build_correspondance_acteurs_an.py --verifier   # n'écrit rien, sort 1 si un slug manque
```

Les entrées existantes sont reconduites **verbatim** — c'est le travail relu —
et un changement d'état civil côté AN est signalé, jamais corrigé tout seul. Un
slug que la correspondance par nom ne résout pas est **nommé sur stderr** et le
script sort en 1 : il n'invente jamais une entrée. Mesuré le 26/08/2026 sur les
476 profils publiés et les 3 119 acteurs d'AMO30 : 466 résolus par le nom, 10 à
arbitrer (2 homonymes, 2 apostrophes, 5 noms divergents, 1 hors AN). La
couverture est un **échec dur** du quality gate (§5b), qui nomme le slug
manquant. Voir `docs/decisions/correspondance-acteurs-an-525.md`.

### La composition des groupes AN vient d'AMO30 (#526 → bascule #527)

`src/an_roster.py` reconstruit la composition des groupes de l'Assemblée à
partir de l'open data AN (`AMO30_tous_acteurs_tous_mandats_tous_organes`), que
le pipeline télécharge et met déjà en cache. Depuis #527 c'est **la** source
AN : `group_roster.fetch_full_roster` y délègue toute clé `deputes`. La lecture
NosDéputés (`fetch_full_roster_nosdeputes`) ne servait plus que le Sénat, sorti
du périmètre par #528 ; elle a survécu comme **repli** du drapeau
`AN_ROSTER_ACTIF` jusqu'à ce que **#529 la retire**. Le drapeau n'aiguille donc
plus vers rien : baissé, il coupe — `RosterAnInactif`, jamais un roster vide.

```bash
# Composition d'un groupe (sigle PUBLIÉ, pas le sigle AN)
python3 src/an_roster.py --legislature 16 --sigle REN

# Écart avec les fiches publiées, entrée par entrée (compteur de migration)
python3 src/an_roster.py --divergence
```

La table sigle publié → sigle(s) AN est committée dans
`raw_data/groupes_reels.json` (`correspondance_sigles_an`), avec organes et
effectifs **mesurés**. À la bascule : les 5 fiches de la 16e sont reproduites
**à l'identique** (0 membre perdu ou gagné, agrégats inchangés, roster de
candidats toujours à 452), et l'écart total reste **4** — quatre députés partis
avant la fin de la législature, sans profil publié donc sans slug, qu'AMO30
connaît et que NosDéputés ne publie plus. Ils sont désormais **nommés à chaque
run** et comptés dans `meta.couverture_roster.roster_total`, qui passe de
193/193 à 193/196 sur REN et de 62/62 à 62/63 sur LR : une couverture qui
exclut ce qu'elle ne sait pas mesurer n'en est pas une.

Baisser `AN_ROSTER_ACTIF` ne reproduit plus l'état d'avant la bascule depuis
#529 — il n'y a plus de seconde source. Le module **refuse alors bruyamment**
plutôt que de rendre une liste vide, qui serait indiscernable d'un groupe
dissous. La 17e législature, absente de NosDéputés,
est servie par le module (461 membres sur les 5 familles publiées, 305 ont déjà
un profil) mais **n'est pas encore publiée** — voir `ROADMAP.md`. Détail et
mesures : `docs/decisions/bascule-roster-an-amo30-527.md`.

### Vérifier que tout ce qui est collecté est publié (#511)

Troisième angle : ni le contrôle de perte (un avant / un après) ni l'intégrité
référentielle (les clés publiées résolvent) ne voit un profil **collecté et
publié nulle part** — rien n'a été perdu, et ce qui manque ne porte aucune clé.

```bash
python3 src/audit_collecte_non_publiee.py
python3 src/audit_collecte_non_publiee.py --out audit/collecte.md --out-json audit/collecte.json
```

Sortie non nulle dès qu'un `raw_data/profiles/<slug>.json` n'a pas son
`pivot_data/profiles/<slug>.pivot.json` — branché avant commit dans
`merge-and-pivot`, après les deux passes de normalisation pivot. Seuil **0**,
mesuré : 0 écart sur les 12 commits de run du 16 au 20/08/2026, pendant que le
corpus passait de 48 à 209 profils. Le contrôle ne parse aucun profil (deux
listes de noms de fichiers) : 0,08 s / 13,9 Mio mesurés à 752 profils. Voir
`docs/decisions/collecte-non-publiee.md`.

### Vérifier que chaque liste publiée porte ce qui a été collecté (#545)

Quatrième angle : #511 raisonne sur des **profils**, jamais sur le contenu de
leurs listes. Un pivot présent mais vidé de ses interventions lui est
irréprochable — c'est ce qui a laissé passer #540, 7 767 interventions
collectées et 891 publiées, run vert.

```bash
python3 src/audit_collecte_vs_publie.py
python3 src/audit_collecte_vs_publie.py --out audit/collecte-vs-publie.md --out-json audit/collecte-vs-publie.json
```

Le contrôle applique une **table de relations** committée (`RELATIONS`), une
entrée par liste métier, parce qu'un « le pivot doit porter autant que le brut »
naïf crierait à tort sur deux champs sur cinq : `dossiers_legislatifs` est
**renommé** en `textes_portes`, et `mandats` reçoit dans le pivot les mandats
européens que le brut range sous `mandat_europeen.mandats_europeens`. Chaque
liste publiée déclare donc les chemins du brut dont elle est la **somme** — un
apport nommé, jamais une marge — d'où un seuil **0** partout.

Sortie non nulle dès qu'une liste publiée porte **moins** que ses sources
collectées ; l'excédent et les listes collectées sans relation déclarée sont
rapportés sans bloquer. Branché avant commit dans `merge-and-pivot`, après les
deux passes de normalisation pivot. Mesuré : 0 déficit sur les 2 380 couples
(profil, relation) de `3104e37` ; rejoué sur `deb28a7`, il sort en erreur et
nomme les cinq profils en déficit. 58,7 s / 158,2 Mio sur les 4,3 Go de profils
bruts — aucun profil n'est matérialisé. Voir
`docs/decisions/collecte-vs-publie-545.md`.

## 3. Generate all candidate profiles (batch)

```bash
python src/generate_all_profiles.py
python src/generate_all_profiles.py --only jean-luc-melenchon
python src/generate_all_profiles.py --skip-existing
python src/generate_all_profiles.py --refresh-existing --no-merge  # l'inverse : ne régénère QUE l'existant (#445)
python src/generate_all_profiles.py --pivot
python src/generate_all_profiles.py --skip-ue
python src/generate_all_profiles.py --workers 8
python src/generate_all_profiles.py --out-dir /tmp/profiles
python src/generate_all_profiles.py --pivot-dir /tmp/pivots
python src/generate_all_profiles.py --limit 20    # premiers N candidats (déploiement progressif)
python src/generate_all_profiles.py --sample 20   # échantillon aléatoire de N candidats
python src/generate_all_profiles.py --manifest-out _manifest/profils-ecrits.txt  # cf. ci-dessous (#450)
python src/generate_all_profiles.py --budget-collecte-secondes 160   # plafond de collecte PAR CANDIDAT (#514)
python src/generate_all_profiles.py --budget-collecte-secondes 0     # pas de plafond, décidé et non subi
python src/generate_all_profiles.py --budget-job-secondes 600        # plafond de collecte pour TOUT le run (#514)
```

`--budget-collecte-secondes` borne la collecte réseau d'un candidat (identité,
votes, dossiers, interventions). Épuisé, il rend la main entre deux requêtes : le
profil partiel est **écrit**, donc publié, et la troncature part dans
`meta.warnings[]`. Omettre l'option lance une collecte sans plafond **et** sans
décision écrite : un avertissement le signale, `0` déclare l'absence de budget.
`--budget-job-secondes` fait la même chose pour le run entier — les candidats non
atteints sortent en `budget_job_epuise`, déclarés et comptés au résumé, au lieu
d'être emportés sans trace par le `timeout-minutes` du job.
Voir `docs/decisions/budget-collecte-source-injoignable-514.md`.

`--manifest-out` consigne, une ligne par nom de fichier, les profils bruts que
CE run a réellement écrits — ni ceux qu'il a sautés, ni ceux qui étaient déjà
dans `--out-dir`. C'est ce qui permet à un job d'extraction CI de ne publier que
sa propre contribution : `raw_data/profiles/` contient aussi la baseline
committée déposée par son `actions/checkout`, et la republier réinjectait des
données périmées à la fusion (#450, voir
[`docs/decisions/publication-scopee-artifacts.md`](docs/decisions/publication-scopee-artifacts.md)).
Le fichier est écrit au fil de l'eau et tronqué au démarrage : il décrit une
exécution, pas un répertoire.

Extraction pilotée par roster (composition réelle des groupes parlementaires,
au lieu de la liste éditoriale `raw_data/candidats.json`, voir
[`docs/decisions/provenance-pivot.md`](docs/decisions/provenance-pivot.md)) :

```bash
python src/generate_roster_candidats.py
python src/generate_all_profiles.py --candidats raw_data/roster_candidats.json --pivot --skip-existing
```

With `--limit` **and** `--skip-existing` combined (the invocation used by the CI roster job), selection
is progressive and self-refreshing instead of always retrying the same first N candidates (#224): budget
goes first to roster members with no existing pivot (moving the coverage frontier forward run over run),
then — if budget remains — to already-covered members whose pivot is stale (`--staleness-days`, default
30, same semantics as `audit_pivot_dataset.py --staleness-days`); those are refreshed via additive merge,
never skipped. A covered and fresh profile is neither re-fetched nor counted against the budget.

For each candidate from `raw_data/candidats.json`, the script:

1. tries FR profile collection (`deputes` — the only chamber since #528) using
   the Nos* slug when available;
2. tries EU mandate lookup by name (unless `--skip-ue`) and merges it under
   `mandat_europeen`;
3. writes `raw_data/profiles/<slug>.json` as soon as at least one source
   (FR or EU) returns data.

With `--pivot`, it also writes `pivot_data/profiles/<slug>.pivot.json`.

### Two-level parallelism

- **Level 1 (within candidate)**: Nos* + EP API calls run in parallel.
- **Level 2 (across candidates)**: candidate jobs are parallelized with
  `--workers` (default 4).

Reduce workers (e.g., `--workers 2`) if public APIs start returning 429.

## 4. Generate one MEP profile (Parltrack)

```bash
python src/mep_profile.py --name "Manon Aubry"
python src/mep_profile.py --ep-id 197451
python src/mep_profile.py --list
python src/mep_profile.py --show-cache-date
```

First run downloads large Parltrack dumps to `.cache/parltrack/`.
Always verify freshness with `--show-cache-date`.

## 5. Generate party profiles

`parti_profile.py` builds **party profiles** from party labels declared in
`raw_data/candidats.json` and available individual pivots.

```bash
python src/parti_profile.py \
    --candidats raw_data/candidats.json \
    --profiles-dir pivot_data/profiles \
    --out-dir pivot_data/partis
```

These are editorial aggregates of declared candidates, not real parliamentary
cohesion profiles. `pivot_data/partis/` is still generated for internal use
but is not displayed as a top-level tab in `web/UI_finale/`.

## 6. Generate parliamentary group profiles

`group_profile.py` aggregates individual profiles (raw Nos* or pivot v1)
into a **real parliamentary group profile** (`schema_groupe.py`).

```bash
python src/group_profile.py \
    --groupe-id "AN:SOC" \
    --groupe-sigle SOC \
    --groupe-nom "Socialistes et apparentes" \
    --chambre AN \
    --legislature 16 \
    pivot_data/profiles/jerome-guedj.pivot.json \
    pivot_data/profiles/boris-vallaud.pivot.json \
    --out pivot_data/groupes/groupe-SOC-16.json
```

Input profiles can be raw or pivot format; detection is automatic.

With `--from-roster`, output overwrite is default. `--merge-existing` keeps
previously known members absent from a transiently incomplete roster fetch.

### Generate multiple real groups in one run

`generate_group_profiles.py` avoids repeated roster downloads by fetching once
per `(chambre, legislature)` and filtering locally by group acronym.

```bash
python src/generate_group_profiles.py \
    --config raw_data/groupes_reels.json \
    --profiles-dir pivot_data/profiles \
    --out-dir pivot_data/groupes \
    --rosters-bruts raw_data/rosters_bruts.json \
    --validate
```

`--merge-existing` applies to all groups in config.

`--rosters-bruts` (#518) reuses the raw roster already collected by
`generate_roster_candidats.py --rosters-bruts-out` earlier in the same run —
**zero** network call. In CI both files travel in the `roster-candidats`
artifact. A key missing from the file is fetched normally. Exit codes:
`0` all good, **`2` roster unavailable** (nothing written, published sheets left
untouched — the workflow step tolerates this code and only this one), `1` a
group generation actually crashed.

### Government ministerial roster

`gouvernement_roster.py` extracts a government's ministerial composition
(`membres[]`) from `mandats[].categorie == "fonction_gouvernementale"` already
present in local pivots — no network call. Disambiguates homonymous
successive governments via `raw_data/gouvernements_reels.json`'s manually
validated `libelle_an` (exact match on `mandats[].label`, `organe.libelleAbrege`
from the AN referential) combined with a period-overlap check. `portefeuille`
carries the precise ministerial title, sourced from the `MINISTERE` mandates of
the same AMO30 bulk dataset (#398) — a minister who changes portfolio mid-government
yields one `membres[]` entry per period, never an arbitrary pick. It stays `null`
when no such mandate overlaps. `build_premier_ministre` derives `premier_ministre`
from the same material (a member of *this* government whose `MINISTERE` mandate is
labelled "Premier ministre"), and returns `null` — never a value inferred from the
government's name — when no local pivot carries it. Produces only the roster and
that entry, not a full
`pivot_data/gouvernements/*.json` profile (`schema_gouvernement.py`) — see
`gouvernement_profile.py` below for that combination with sponsored texts.

```bash
python src/gouvernement_roster.py \
    --config raw_data/gouvernements_reels.json \
    --gouvernement-id "gouvernement:BAYROU" \
    --profiles-dir pivot_data/profiles
```

### Government profile

`gouvernement_profile.py` combines `gouvernement_roster.py`'s ministerial
composition and `gouvernement_textes.py`'s legislative files into a full
government profile (`schema_gouvernement.py`), written to
`pivot_data/gouvernements/<id>.json`. A text is attached to a government by
overlap of its `date_depot` with the government's `periode` (never by its
final-status date — a text initiated under government A stays credited to A
even if concluded under government B). A text whose `statut` or
`chambre_depot_initial` can't be determined is excluded from `textes[]` (never
a guessed default), with a warning kept in `meta.warnings`; `comptages.par_statut`
is a raw count of the retained texts only — no rate is ever computed (see
[`docs/decisions/gouvernement-profile-rattachement.md`](docs/decisions/gouvernement-profile-rattachement.md)).

```bash
python src/gouvernement_profile.py \
    --config raw_data/gouvernements_reels.json \
    --gouvernement-id "gouvernement:BAYROU" \
    --profiles-dir pivot_data/profiles \
    --out pivot_data/gouvernements/gouvernement-BAYROU.json \
    --validate
```

`generate_gouvernement_profiles.py` generates every government listed in
`raw_data/gouvernements_reels.json` in a single run, fetching the legislative
files dump and loading the local pivot profiles only once, shared across all
governments (mirrors `generate_group_profiles.py`'s single roster fetch per
`(chambre, legislature)`).

```bash
python src/generate_gouvernement_profiles.py \
    --config raw_data/gouvernements_reels.json \
    --profiles-dir pivot_data/profiles \
    --out-dir pivot_data/gouvernements \
    --validate
```

## 7. Candidate monitoring via Wikipedia / Wikidata

```bash
python src/fetch_wikipedia_candidates.py
python src/fetch_wikipedia_candidates.py --source wikipedia
python src/fetch_wikipedia_candidates.py --source wikidata
python src/fetch_wikipedia_candidates.py --json
```

This script never modifies `candidats.json` automatically; it outputs a review
summary for manual validation.

## 8. CI/CD automated generation workflow

The workflow `.github/workflows/generate-data.yml` runs the full pipeline
on GitHub Actions and is triggered manually (`workflow_dispatch`).

Detailed extraction and merge flow is documented in:

- `docs/workflow-generate-data.md` (the run: the eight jobs, form, caches,
  artifacts, budgets, push, retry)
- `docs/pipeline-profiles-groupes.md` (what the data becomes)
- `docs/extract-roster-groupes.md` (the roster-driven job, in depth)

The `extract-amendements-an` job runs `src/build_amendements_index.py`
independently (no `needs:`) to build the 3 AN amendements legislature
indexes unconditionally and pre-warm the shared `.cache/amendements_an/`
cache (artifact `amendements-index-an`), instead of leaving that
construction to lazy per-candidate calls in `extract-an`/
`extract-roster-groupes`. `continue-on-error: true`, same pattern as
`extract-parltrack` — see `docs/decisions/amendements-index-job-dedie-ci.md`.
Legislatures 15/16 are excluded from this network path: their dossier is
closed and the CI download budget can't reliably fetch their 350-650 MB
archive (recurring `IncompleteRead`, reproduced outside CI too). Their index
is built once, offline, via `src/build_amendements_index_figees.py --legislature
{15,16} (--zip <local archive> | --download)` (`--download` reuses the same
segmented/retried fetch as the CI job, writing into gitignored
`.cache/amendements_an/`; `--stall-cycles` / `--stall-wait-seconds` widen the
wait when the source serves nothing at all — offline, waiting is the only
remedy that works, see
`docs/decisions/telechargement-an-trois-modes-defaillance.md`) and
committed under `raw_data/amendements_an_figes/`
— the script deduplicates the raw per-signataire index into
`amendements.json` + a slim `index_par_acteur.json` before writing, since the
undeduplicated form is multiple GB uncompressed (measured on legislature 16)
and can't be committed. `candidate_profile.py` reads that fallback (expanding
it back to the standard flat shape) instead of hitting the network for those
two — see `docs/decisions/amendements-legislatures-figees.md`.

Nominal votes follow the same shape since #403. `fetch_votes_officiels()`
aggregates **all four AN legislatures** (14 to 17, `AN_SCRUTINS_LEGISLATURES`)
instead of the single one previously derived from the NosDéputés domain, which
froze every profile on legislature 16 and stopped the dataset in June 2024.
Legislatures 14/15/16 are closed: their index is built offline via
`src/build_scrutins_index_figes.py --legislature {14,15,16}` (or `--toutes`)
and committed under `raw_data/scrutins_an_figes/` (2.8 MB gzipped total), so CI
only downloads the active 17th (26 MB). Both the on-disk cache and the
committed fallback store the deduplicated form — scrutin metadata once in
`scrutins.json`, one `[uid, position]` reference per voter, sharded per
`acteurRef` — which keeps the four legislatures at 68 MB instead of 741 MB
flat. See `docs/decisions/votes-multi-legislature.md`.

The merge stage runs `src/check_quality_gate.py`; commit/push occurs only if
the gate exits with code 0. Its **§7 is the blob guard-rail of #580**: it
measures the biggest versioned file, **warns at 50 MiB**, **fails the commit at
80 MiB** — below GitHub's 100 MiB hard refusal, so there is still room to act —
and prints the course of action with the finding. `--blob-warn-mo 0` disables
the section. It lives here and not in the test suite because `tests.yml`
sparse-checks-out without the corpus (#473), so no test can measure it. See
`docs/decisions/partition-profils-legislature-580.md#garde-fou-blob-580`.

Before that step, the `merge-and-pivot` job also
downloads the `amendements-index-an` artifact into `.cache/amendements_an`
(optional, `continue-on-error: true`, same cache-only pattern as `extract-an`/
`extract-roster-groupes`) so the gate's amendements freshness section (3d) can
read the real `fraicheur.json` indicators instead of always reporting "never
built".

`merge-and-pivot` also runs `src/generate_gouvernement_profiles.py --validate`
right after the groupe step, on the same model, writing `pivot_data/gouvernements/`
(included in the automatic commit alongside `pivot_data/groupes`) — see
`docs/decisions/gouvernement-ci-integration.md` for the timeout
budget measurement (no dedicated job needed, unlike the AN extraction jobs).

To run the gate locally:

```bash
python src/check_quality_gate.py
python src/check_quality_gate.py --threshold 0                # zero tolerance
python src/check_quality_gate.py --low-interventions 5        # stricter signal
python src/check_quality_gate.py --groupe-min-coverage-pct 50  # relative groupe coverage soft fail (disabled by default)
python src/check_quality_gate.py --amendements-staleness-days 14  # laxer amendements freshness signal (default: 7, 0 disables)
```

`--groupe-min-coverage-pct` (default `0`, disabled) is a relative alternative/complement
to `--groupe-min-members` (default `1`, absolute count) for the groupe coverage soft
warning — see `docs/decisions/seuil-couverture-groupe.md` for why the absolute
default is kept until full-scale roster-driven extraction (#188/#190/#191) produces real
coverage numbers.

`--amendements-cache-dir` (default `.cache/amendements_an`) / `--amendements-staleness-days`
(default `7`, `0` disables) control the section 3d soft warning that distinguishes, per
legislature, an amendements index that was never built from one that is present but stale
(no successful rebuild within the threshold, per the `fraicheur.json` indicator written by
`candidate_profile.py`, #253), or frozen (légis 15/16, `fraicheur.json` carries `figee: true`
— never staleness-checked, see `docs/decisions/amendements-legislatures-figees.md`) — see
`docs/decisions/amendements-index-quality-gate-fraicheur.md`.

`--gouvernements-dir` (default `pivot_data/gouvernements`) / `--gouvernements-config`
(default `raw_data/gouvernements_reels.json`) drive section 5 (gouvernements), mirroring
`--groupes-dir`/`--groupes-config` for section 4 — hard fail on missing/invalid file or
schema, soft fail on incomplete portefeuille (ministerial portfolio) coverage, empty
`textes[]` with a non-null `periode`, or IncompleteRead network signals.

## 9. Running the full pipeline locally instead of CI

`scripts/generate_data_local.sh` runs the same sequence of stages as
`generate-data.yml` (AN, UE, ParlTrack, amendements index,
roster-driven group members, then pivots + party/group/government profiles +
quality gate) directly on your machine, bypassing GitHub Actions entirely.
Useful when the hosted runner is hitting transient infrastructure
preemptions ("shutdown signal", see `docs/technical_decisions.md`) unrelated
to the code itself — running locally sidesteps that class of failure
completely, since it doesn't depend on GitHub's runner fleet at all.

```bash
./scripts/generate_data_local.sh
```

By default it launches itself in the background (`nohup`) and returns
immediately, printing the PID and the log file to follow:

```
Lancement en arrière-plan — logs : logs/generate_data_local_20260817T104701Z.log
PID : 12345
Suivre : tail -f logs/generate_data_local_20260817T104701Z.log
Arrêter : kill 12345
```

Every run's full output is saved under `logs/` (git-ignored, like `.cache/`),
regardless of foreground/background mode. Run `BACKGROUND=false
./scripts/generate_data_local.sh` to keep it attached to the terminal
instead (output is still duplicated into the same log file via `tee`).

Same tunables as the workflow's `workflow_dispatch` inputs, passed as
environment variables:

```bash
WORKERS=4 EXISTING_PROFILES=overwrite EXTRACT_INTERVENTIONS=true ./scripts/generate_data_local.sh
```

| Variable | Default | Same as `workflow_dispatch` input |
|---|---|---|
| `EXISTING_PROFILES` | `refresh` | `existing_profiles` |
| `ADD_UNCOVERED_MEMBERS` | `true` | `add_uncovered_members` |
| `COLD_START` (alias `FRESH_RUN`) | `false` | `cold_start` |
| `THRESHOLD` | `3` | `incomplete_read_threshold` |
| `WORKERS` | `1` (sequential) | *(local-only: frozen at 1 in CI)* |
| `EXTRACT_INTERVENTIONS` | `false` | `collect_interventions` |
| `ROSTER_EXTRACTION_LIMIT` | `0` (no cap) | `roster_limit` |
| `BACKGROUND` | `true` | *(local-only, no CI equivalent)* |

Two disjoint axes (#578): `EXISTING_PROFILES` decides what happens to profiles
already written (`leave-as-is` / `refresh`, merging / `overwrite`, replacing),
`ADD_UNCOVERED_MEMBERS` (a boolean, `true` by default) decides whether members
with no profile get one, and `COLD_START` only purges the download caches. The
axis-2 field was a `roster_coverage` menu when #578 shipped it; #590 turned it
into the `add_uncovered_members` checkbox, and the old name is dead — see
`docs/decisions/deux-axes-formulaire-578.md` and
`docs/workflow-generate-data.md` §2.

Each stage keeps the CI job's `continue-on-error` behavior: a failure in one
source (e.g. ParlTrack down) doesn't stop the rest. Unlike CI, nothing is
committed/pushed automatically at the end — review `git status`/`git diff`
on `raw_data/profiles`, `pivot_data/profiles`, `pivot_data/partis`,
`pivot_data/groupes`, `pivot_data/gouvernements`, then commit/push manually
if the result looks right. See the script's header comment for the exact
differences from the CI job graph (no per-candidate matrix, no
artifact-based re-merge — both are CI-only orchestration concerns with no
local equivalent needed).

## 10. Open the web UI locally

`web/UI_finale/` is the production interface (React 19 + Vite, **Candidats** · **Groupes** ·
**Gouvernement**, no Partis tab). Before running it, sync pivot data into `public/data/`:

```bash
cd web/UI_finale
npm install          # first time only
npm run dev          # syncs data then starts Vite dev server
```

`scripts/sync-data.mjs` copies `pivot_data/profiles/`, `pivot_data/groupes/`,
`pivot_data/gouvernements/` and `raw_data/candidats.json` into `public/data/` (generated,
git-ignored) and writes `public/data/manifest.json`. Coverage is limited to the
candidates/groups/governments with a local pivot file — see "Coverage limits" below for the
current state of the roster-driven rollout.

Archived design generations are in `web/old/` (v1–v7, atlas, interface-essentielle,
studies) — static HTML, serve with `python -m http.server 8000` from the repo root.

## 11. Audit the pivot dataset

`src/audit_pivot_dataset.py` scans a directory of `*.pivot.json` files and reports
volumetry (including a breakdown by `meta.provenance`, `candidat_declare` vs.
`roster_groupe`), completeness, consistency, source freshness, aggregated
`meta.warnings[]` indicators, and two per-candidate cross-tabs of `votes` /
`textes_portes` / `amendements` / `interventions`: counts, and date range
(min/max, `textes_portes` aggregating `date_min`/`date_max` across entries;
unparseable dates are ignored and tallied per field, never silently
defaulted). Both cross-tabs list **declared candidates only**
(`meta.provenance` = `candidat_declare`); roster-sourced profiles
(`roster_groupe`) appear aggregated per `groupe` (min/max/median/mean for
counts, enclosing range for dates), never member by member — an internal
quality tool, not an end-user report (no score, no ranking, see
`AGENTS.md` §2).

```bash
python src/audit_pivot_dataset.py \
    --input-dir pivot_data/profiles \
    --output-json audit_report.json \
    --output-md audit_report.md \
    --staleness-days 30
```

`--output-json`/`--output-md` default to unset (JSON prints to stdout, Markdown is
skipped if `--output-md` is omitted). `--staleness-days` (default 30) sets the
threshold beyond which a profile with only stale sources is flagged.

To see what a report looks like, generate one on the frozen fixtures — a
command cannot go stale, a committed sample can (the last one drifted from the
tool by a whole section before it was dropped):

```bash
python3 src/audit_pivot_dataset.py --input-dir tests/fixtures/audit_pivot \
        --output-json audit_pivot_exemple.json --output-md audit_pivot_exemple.md
```

Instead of naming both files, `--output-dir DOSSIER` writes both under a
timestamped name (`audit_pivot_<horodatage-UTC>.json`/`.md`) — incompatible
with `--output-json`/`--output-md`:

```bash
python src/audit_pivot_dataset.py --input-dir pivot_data/profiles --output-dir audit_reports/
```

## 12. Audit the groupe dataset

`src/audit_groupe_dataset.py` mirrors `audit_pivot_dataset.py` for
`pivot_data/groupes` (`schema_groupe.py`): it scans a directory of group
profile `*.json` files and reports volumetry (effectifs, `cohesion_votes`,
`amendements_agreges` — global and per `type_deposant`), completeness
(`tags_thematiques_agreges`, groups with members but no cohesion votes),
consistency (`validate_profil_groupe`, `schema_version` divergence, roster
coverage gap with a coverage rate in %, duplicate `groupe_id`), source freshness and stale groups,
aggregated `meta.warnings[]`, and a per-groupe cross-tab of `membres` /
`cohesion_votes` / `tags_thematiques_agreges` / `amendements_agreges`
(global `nb_amendements`) counts — same internal-quality-tool contract as
the pivot audit (no score, no ranking, see `AGENTS.md` §2).

```bash
python src/audit_groupe_dataset.py \
    --input-dir pivot_data/groupes \
    --output-json audit_groupe_report.json \
    --output-md audit_groupe_report.md \
    --staleness-days 30
```

`--input-dir` defaults to `pivot_data/groupes`. `--output-json`/`--output-md`
default to unset (JSON prints to stdout, Markdown is skipped if `--output-md`
is omitted). `--staleness-days` (default 30) sets the threshold beyond which
a group with only stale sources is flagged — same option contract as
`audit_pivot_dataset.py` for combined use, including `--output-dir DOSSIER`
(timestamped `audit_groupe_<horodatage-UTC>.json`/`.md`).

To see what a report looks like, generate one on the frozen fixtures:

```bash
python3 src/audit_groupe_dataset.py --input-dir tests/fixtures/audit_groupe \
        --output-json audit_groupe_exemple.json --output-md audit_groupe_exemple.md
```

## 13. Audit the gouvernement dataset

`src/audit_gouvernement_dataset.py` mirrors `audit_groupe_dataset.py` for
`pivot_data/gouvernements` (`schema_gouvernement.py`): it scans a directory
of `gouvernement-*.json` files and reports volumetry (`periode.actif`
breakdown, `membres`/`textes` distribution, `comptages.par_statut`
aggregated across governments), completeness (`premier_ministre`,
`membres[].portefeuille`, `meta`), consistency
(`validate_profil_gouvernement` — already covers the 49.3 non-collapse
invariant, `schema_version` divergence, duplicate `gouvernement_id`), source
freshness and stale governments, source coverage of carried texts
(`compute_couverture_textes`, #399: classifies each government against the
legislature archives actually ingested — `src/couverture_dossiers.py` — so
that "outside the source's coverage" is never read as "really zero"; the
coverage bound is printed in the report header, and `nb_textes` stays `null`
when the `textes` field is absent, never rendered as `0`), and a
per-government cross-tab of date ranges (`compute_plage_dates_gouvernements`): min/max of
`membres[].debut`/`.fin` (`mandats_membres`) and `textes[].date_depot`/
`.date_dernier_evenement` (`textes`) — a `membres[].fin = null` (ongoing
mandate) is excluded from the max without ever being substituted by today's
date (`AGENTS.md` §2.5). Also aggregates `meta.warnings[]` by type
(`compute_agregation_warnings`, same contract as `audit_groupe_dataset.py`,
added for #321 so `audit_pipeline.py`'s compiled overview can report
government warnings alongside profiles/groups). Same internal-quality-tool
contract as the other audits (no score, no ranking, see `AGENTS.md` §2).

```bash
python src/audit_gouvernement_dataset.py \
    --input-dir pivot_data/gouvernements \
    --output-json audit_gouvernement_report.json \
    --output-md audit_gouvernement_report.md \
    --staleness-days 30
```

`--input-dir` defaults to `pivot_data/gouvernements`. `--output-json`/
`--output-md` default to unset (JSON prints to stdout, Markdown is skipped
if `--output-md` is omitted). `--staleness-days` (default 30) sets the
threshold beyond which a government with only stale sources is flagged —
same option contract as the other audit scripts, including `--output-dir
DOSSIER` (timestamped `audit_gouvernement_<horodatage-UTC>.json`/`.md`).

To see what a report looks like, generate one on the frozen fixtures:

```bash
python3 src/audit_gouvernement_dataset.py --input-dir tests/fixtures/audit_gouvernement \
        --output-json audit_gouvernement_exemple.json --output-md audit_gouvernement_exemple.md
```

## 14. Combined audit pipeline (manual tool)

`src/audit_pipeline.py` is a **manual** entry point that runs all three audits
above by calling their functions directly (no subprocess) and compiles an
"overview" section on top of the three detailed reports: total
profiles/groups/governments audited, aggregated read errors, and aggregated
`meta.warnings[]` across all three document types. Pure composition of the
reports produced by `audit_pivot_dataset.py` / `audit_groupe_dataset.py` /
`audit_gouvernement_dataset.py` — no new business logic (issue #321,
sub-issue 5/6 of #316, extends the profiles+groups compilation from #178 to
governments).

It is separate from `src/check_quality_gate.py` (the only CI-blocking gate)
and is **not** wired into `.github/workflows/generate-data.yml` — this was an
explicit decision (see issue #178): this tool is never invoked automatically
by CI.

```bash
python src/audit_pipeline.py \
    --profiles-dir pivot_data/profiles \
    --groupes-dir pivot_data/groupes \
    --gouvernements-dir pivot_data/gouvernements \
    --output-json audit_pipeline_report.json \
    --output-md audit_pipeline_report.md \
    --staleness-days 30
```

`--profiles-dir`/`--groupes-dir`/`--gouvernements-dir` default to
`pivot_data/profiles` / `pivot_data/groupes` / `pivot_data/gouvernements`.
`--output-json`/`--output-md` default to unset (JSON prints to stdout,
Markdown is skipped if `--output-md` is omitted). `--staleness-days` (default
30) is forwarded unchanged to all three underlying audits. A missing
directory (any of the three) is a hard error (explicit message + exit code
1, never a crash traceback), same behavior across all three. Same
`--output-dir DOSSIER` convenience as the other audit scripts (timestamped
`audit_pipeline_<horodatage-UTC>.json`/`.md`, incompatible with
`--output-json`/`--output-md`).

## Raw profile content (Nos* format)

**A raw profile is two things since #580**: the socle
`raw_data/profiles/<slug>.json`, and — for `amendements` only — one slice per
legislature under `raw_data/profiles/<slug>/<legislature>.json`. `amendements`
weighed 96,7 % of the biggest profile (54,15 of 56,00 MB), and every amendment
already carried its `legislature`, so the list is partitioned on a field that
was already there: 56,0 → 23,4 MB with **not one byte dropped**, nothing
deduplicated and no field trimmed. The socle carries an
`amendements_partitionnes` manifest in the exact place `amendements` occupied,
and **omits** the key itself — absent, never empty (§2.5). Load a profile with
`profil_brut.charger_profil_brut()`, which accepts both this form and the older
monolithic one; stream just the amendments with
`profil_brut.iter_amendements_du_profil()`. Details:
[`docs/decisions/partition-profils-legislature-580.md`](docs/decisions/partition-profils-legislature-580.md).

Each profile includes:

- `identite`: name, political group, profession, constituency, ...
- `mandats`: base elected mandate + real responsibilities with role, dates,
  and `actif` flag
- `votes`: voting positions + source (`votes_source`, listing **every** covered
  legislature), prioritizing official AN open data, with Nos* fallback. Each vote
  carries its own `legislature` and `url_source` (the AN scrutin page), since a
  profile now spans several legislatures
- `dossiers_legislatifs`: chamber legislative files
- `interventions`: speech records with date, topic, text, role at the time, and
  basic length-based format. Source since #510: the AN Syceron debate archives
  **only** (plus official QE/QG/QOSD questions) — the NosDéputés search fallback
  was removed, so an empty collection stays empty and is declared in
  `meta.warnings[]`
- `mandat_europeen`: present only if a candidate has EP records
- `meta.warnings`: transparency on missing/incomplete source fetches
- `meta.synchro_sources`: ISO-8601 timestamp per source

## Pivot schema v1

Defined in `src/schema_pivot.py` and produced by `normalize_profil.py`
(and EU normalizers) to unify AN/Senate/EP representation.

With `--pivot`, `generate_all_profiles.py` writes `<slug>.pivot.json`:

```json
{
  "schema_version": "1",
  "id": "jean-luc-melenchon",  // = le slug, sans prefixe de provenance (#487)
  "nom": "Jean-Luc Melenchon",
  "chambre": "AN",
  "parti": null,
  "groupe": "La France Insoumise",
  "sources": [
    // Since #529 a freshly collected FR profile only ever produces
    // "assemblee_nationale". "nosdeputes"/"nossenateurs" stay VALID values —
    // 476 published profiles carry one, and dropping them from
    // KNOWN_SOURCE_TYPES would make validate_profil() reject the corpus we
    // just published. #530 measured that they do NOT go away on their own:
    // merge_pivot_profile unions sources[] by type, so an already-published
    // "nosdeputes" entry survives an AN collection, and the ODbL attribution
    // stays due (docs/decisions/licence-lot-6-530.md).
    {"type": "assemblee_nationale", "url": "https://www2.assemblee-nationale.fr/deputes/fiche/OMC_PA1234", "synchro_le": "2026-07-29T..."},
    {"type": "assemblee_nationale", "url": "https://data.assemblee-nationale.fr/", "synchro_le": "2026-07-29T..."}
  ],
  "mandats": [ ... ],          // categorie ∈ mandat_electif | commission |
                               // commission_enquete | mission_information |
                               // groupe_etudes | delegation | groupe_amitie |
                               // groupe_politique | extra_parlementaire |
                               // fonction_gouvernementale | autre
                               // (schema_pivot.KNOWN_CATEGORIES)
  "votes": [ ... ],
  "textes_portes": [ ... ],
  "amendements": [ ... ],
  "interventions": [ ... ],
  "tags_thematiques": ["budget", "fiscalite"],
  "meta": { "schema_version": "1", "genere_le": "...", "warnings": [],
            // Derived from sources[] by src/licences.py, never hardcoded (#530):
            // "Licence Ouverte … (Etalab) — data.assemblee-nationale.fr + ODbL v1.0 (…)"
            "licence_donnees": "..." }
}
```

Sensitive institutional constraints are documented in `AGENTS.md`.

## Source taxonomy

| Source | Type | Update cadence | License | Chamber(s) |
|---|---|---|---|---|
| data.assemblee-nationale.fr / questions.assemblee-nationale.fr | ZIP dumps | Daily — **the only French source** | Licence Ouverte / Open Licence (Etalab), attribution only | AN |
| NosDeputes.fr + archives | JSON/XML API | **No longer collected since #529** (lot 5); attribution still due for already-published fields (#530) | ODbL v1.0, **share-alike** | AN |
| NosSenateurs archives | JSON/XML API | **Out of scope since #528** (dead TLS certificate); no longer collected since #529; attribution still due (#530) | ODbL v1.0, **share-alike** | Senate |
| Parltrack | LZMA dumps | Weekly (approx.) — **still collected** | ODbL v1.0, **share-alike** | EP |
| European Parliament (data.europarl.europa.eu, www.europarl.europa.eu) | REST API + MEP pages | Live (fetched per run, no weekly cache) | EP Legal Notice (reuse policy, attribution-based) | EP |
| French Wikipedia | MediaWiki REST API | Immediate | CC BY-SA 4.0 | Candidate monitoring |
| Wikidata | SPARQL | Immediate | CC0 1.0 | Candidate monitoring |

The corpus is **not** under a single licence, and dropping Regards Citoyens from
collection did not make it so (#530): Parltrack is still collected under ODbL, and
published fields derived from NosDeputes/NosSenateurs are still published. Each profile
lists the licences its own content falls under in `meta.licence_donnees`, derived from its
`sources[]` by `src/licences.py`. Details: `AGENTS.md` §7 and
`docs/decisions/licence-lot-6-530.md`.

## Tests

```bash
pytest -q
```

The full suite runs in ~11 s (24 s for the whole CI job, checkout included),
executed by `.github/workflows/tests.yml` on every pull request and on every
push to `main`; the job fails if any test fails.

The suite is **decoupled from the living corpus**: no test reads `pivot_data/`
or `raw_data/profiles/`, none writes anywhere under `pivot_data/` or
`raw_data/`, and none makes an external network call (#473). The CI job enforces
this structurally — it sparse-checks-out only what the suite actually reads, so
the corpus is not on disk at all. A test that re-couples to it fails there with
a `FileNotFoundError` naming the path. Acceptance tests that need real profiles
use the frozen fixtures under `tests/fixtures/`. Rationale:
`docs/decisions/ci-tests-pytest.md`.

## Coverage limits

- **Group scope**: profile generation (roster-driven or not) only covers the
  7 groups declared in `raw_data/groupes_reels.json` (5 AN + 2 Senate) — not
  every parliamentary group that exists. Extending coverage means adding
  entries to that file, a separate editorial decision. The **2 Senate groups
  are suspended** since 2026-08-24 (`extraction_suspendue`, #516) and stay so:
  #528 took the Senate out of the product's scope, so the suspension is no
  longer waiting on a certificate — it waits on an explicit editorial
  reopening. Their published files stay in place, frozen (removing a published
  file is a disappearance, which `audit_diff_profils` blocks). See
  [`docs/decisions/retrait-senat-528.md`](docs/decisions/retrait-senat-528.md)
  and
  [`docs/decisions/extraction-groupe-suspendue-516.md`](docs/decisions/extraction-groupe-suspendue-516.md).
- **Government scope**: profile generation only covers the governments
  declared in `raw_data/gouvernements_reels.json` (10 as of this writing,
  Fillon II through Lecornu II) — not every government in the Fifth
  Republic. `membres[].portefeuille` and `premier_ministre` are filled from the
  AN `MINISTERE` mandates when a member has a local pivot carrying one (24/41
  members and 3/10 governments as of this writing), and stay `null` otherwise —
  never a placeholder like "Ministre" nor a name inferred from the government's
  own label; the 7 remaining Prime Ministers simply have no local pivot, a figure
  that grows mechanically with the full-scale roster rollout. `textes[]` can be empty
  for a recent government; `web/UI_finale` shows an explicit "no data" state
  in both cases (rule 5, `AGENTS.md`).
- **Roster-driven candidate/member coverage**: `generate_roster_candidats.py`
  + `generate_all_profiles.py --candidats raw_data/roster_candidats.json`
  (see [`docs/decisions/provenance-pivot.md`](docs/decisions/provenance-pivot.md))
  aims for near-complete coverage of the ~750 roster members of the 7
  configured groups, but no full-scale run had landed in CI as of this
  writing — see
  [`docs/decisions/seuil-couverture-groupe.md`](docs/decisions/seuil-couverture-groupe.md)
  for the latest real coverage numbers. Until coverage is consistently
  near-100%, `web/UI_finale` shows an explicit "no data" state instead of a
  misleading zero (rule 5, `AGENTS.md`).
- **AN votes**: official open data for deputies (14th-17th legislatures,
  depending on available dumps).
- **Senate**: out of scope since #528 — no collection job, no `--source senat`,
  no `senateurs` chamber. Already-published Senate mandates and the 2 frozen
  Senate group files stay published.
- **Interventions**: Syceron is the only source since #529, and its bare-actor-id
  resolution is still shipped inactive (#510) — a fresh collection therefore yields
  official questions only. Already-published speeches are kept by the additive merge,
  and a `--no-merge` run that lost them would be blocked by `audit_diff_profils`.
- **Mayors**: no dedicated module/source.
- **Coverage bias**: former MPs usually have richer traces than non-MP profiles.
- **API docs**: `docs/sources/nosdeputes/` is historical reference material only —
  the pipeline stopped querying that platform at #529.

## Data freshness

Profiles expose `meta.synchro_sources`; pivots expose `sources[].synchro_le`.
For Parltrack, use:

```bash
python src/mep_profile.py --show-cache-date
```

## Editorial neutrality

This project aggregates factual records and primary sources. It does not
produce rankings, scores, or evaluative judgments of political positions.
See `AGENTS.md` for the full non-negotiable rule set.

## Thematic taxonomy roadmap

See `ROADMAP.md`.
