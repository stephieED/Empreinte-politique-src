# Le run : `generate-data.yml` et sa relance

Ce que fait un **run** — les jobs, leur ordre, les caches, les artifacts, le
formulaire de lancement, le push, et la relance automatique. Ce que devient la
**donnée** est décrit ailleurs : `docs/pipeline-profiles-groupes.md`. Les
**règles** que ces mécanismes imposent restent dans `AGENTS.md` §3 ; le
**pourquoi** de chacune est un fichier de `docs/decisions/`.

Ce fichier existe pour être lu **avant** d'ouvrir
`.github/workflows/generate-data.yml`, qui fait ~3 200 lignes.

## 1. Les huit jobs, dans l'ordre

| Job | `needs:` | Consomme | Produit |
|---|---|---|---|
| `prepare-an-matrix` | — | `raw_data/candidats.json` | la matrice `extract-an` (un shard par candidat à slug résolvable, #344) |
| `extract-amendements-an` | — | AN open data (dumps amendements) | artifact `amendements-index-an` + cache `public-data-cache-amendements-<semaine>` |
| `extract-ue-officiel` | — | Europarl Open Data | artifact `raw-profiles-ue-officiel`, cache `public-data-cache-ue-<semaine>` |
| `extract-parltrack` | — | dumps ParlTrack | artifact `parltrack-dumps`, cache `public-data-cache-parltrack-<semaine>` |
| `prepare-roster-matrix` | — | `raw_data/groupes_reels.json` | `raw_data/roster_candidats.json` → artifact `roster-candidats`, et la matrice roster |
| `extract-an` | `extract-amendements-an`, `prepare-an-matrix` | AN open data, Syceron, l'index amendements | un artifact `raw-profiles-an-<slug>` par shard, cache `public-data-cache-an-<semaine>[-interv-<empreinte>]` |
| `extract-roster-groupes` | les quatre `extract-*` + `prepare-roster-matrix` | l'artifact `roster-candidats`, les mêmes sources | un artifact `raw-profiles-roster-groupes-<shard>` par shard |
| `merge-and-pivot` | `extract-an`, `extract-ue-officiel`, `extract-parltrack`, `extract-roster-groupes` | tous les artifacts ci-dessus | la fusion, les deux passes pivot, les quatre contrôles, le commit et le push |

Cinq jobs n'ont aucun `needs:` et démarrent ensemble. Le **chemin critique réel,
ce sont les deux matrices en série** (`extract-an` en `max-parallel: 1`, puis la
matrice roster en `max-parallel: 4`), pas le nombre de jobs.

`extract-an`, `extract-ue-officiel`, `extract-parltrack`,
`extract-amendements-an` et `extract-roster-groupes` portent
`continue-on-error: true` : leur échec ne bloque pas `merge-and-pivot`, qui
fusionne ce qui a réussi. Les deux jobs avals portent en plus
`if: ${{ !cancelled() }}` — `continue-on-error` transforme un *échec* en
non-bloquant mais ne fait rien contre un maillon amont *skipped* (#412 §2.1).
`prepare-roster-matrix` n'en porte pas et ne doit pas en recevoir : sa sortie
dimensionne la matrice.

## 2. Le formulaire de lancement

Deux axes **disjoints**, plus le cache à part (#578,
`docs/decisions/deux-axes-formulaire-578.md`) :

| Champ | Type | Défaut | Ce qu'il commande |
|---|---|---|---|
| `existing_profiles` | `choice` : `leave-as-is` / `refresh` / `overwrite` | `refresh` | **Axe 1** — ce qu'on fait des profils DÉJÀ écrits. `overwrite` seul lève `--no-merge`. |
| `add_uncovered_members` | `boolean` | `true` | **Axe 2** — si on écrit un premier profil pour les membres qui n'en ont pas. |
| `cold_start` | `boolean` | `false` | Purge les caches de téléchargement et re-télécharge les sources. Ne dit **rien** de la façon dont les profils sont écrits. |
| `roster_limit` | `number` | `0` | Un plafond, et rien d'autre (`0` = pas de plafond). Ne commande aucune politique de rafraîchissement. |
| `collect_interventions` | `boolean` | `false` | Ajoute les archives Syceron et QE/QG/QOSD à `extract-an` — **jamais** au roster. |
| `incomplete_read_threshold` | `number` | `3` | Seuil d'incidents réseau au-delà duquel le quality gate échoue. |
| `allow_declared_losses` | `boolean` | `false` | Tolérance du contrôle de perte (#460). |
| `allow_broken_references` | `boolean` | `false` | Tolérance de l'intégrité référentielle (#485). |
| `allow_unpublished_profiles` | `boolean` | `false` | Tolérance de « collecté = publié » (#511). |
| `allow_publication_gaps` | `boolean` | `false` | Tolérance de « chaque liste porte ce que la collecte a rendu » (#545). |

Les quatre tolérances sont **cloisonnées** : aucune ne désarme le contrôle d'une
autre.

Les `description:` sont les **libellés affichés** : GitHub montre la description
et masque le nom du champ. Ce sont des titres, pas de la documentation.
**`python3 scripts/rendu_formulaire.py` rend le formulaire tel qu'il s'affiche** —
lire le YAML masque exactement le défaut que #578 a corrigé. Verrouillé par
`tests/test_ci_inputs_workflow.py::test_un_libelle_tient_sur_une_ligne`.

`ROSTER_COVERAGE`, `roster_coverage`, `overwrite_profiles` et
`refresh_existing_only` sont des noms **morts** ; le test
`test_les_deux_axes_sont_deux_champs_distincts` échoue si l'un réapparaît dans
les inputs.

## 3. Les caches

Une clé par source, semainière, avec `restore-keys` pour retomber sur l'entrée
la plus proche :

| Clé | Répertoire | Qui l'**écrit** | Qui la **lit seulement** |
|---|---|---|---|
| `public-data-cache-an-<semaine>[-interv-<empreinte>]` | `.cache/acteurs_historique_an`, `.cache/scrutins_an`, `.cache/questions_an/*/index_par_acteur.json`, `.cache/syceron_an/*/index_par_acteur` | `extract-an` (`actions/cache/save`) | `extract-roster-groupes` (`actions/cache/restore`) |
| `public-data-cache-amendements-<semaine>` | `.cache/amendements_an` | `extract-amendements-an` (`actions/cache`) | `extract-an`, `extract-roster-groupes` (`restore`) |
| `public-data-cache-dossiers-<semaine>` | `.cache/dossiers_an` | `extract-an`, `merge-and-pivot` | `extract-roster-groupes` (`restore`) |
| `public-data-cache-ue-<semaine>` | `.cache/europarl` | `extract-ue-officiel` | — |
| `public-data-cache-parltrack-<semaine>` | `.cache/parltrack` | `extract-parltrack` | — |

**La règle du producteur-écrivain** : un job n'écrit jamais une clé pour un
répertoire qu'il ne remplit pas. `actions/cache` saute la sauvegarde post-job
sur un hit exact, donc le premier écrivain gèle l'entrée pour tout le monde. Le
même défaut est passé trois fois (#412 §2.3 → #424 → #505). Deux corollaires :
un job portant un `--skip-*` utilise `actions/cache/restore`, et une clé dont le
**contenu** dépend d'un input porte cet input — d'où le suffixe
`-interv-<empreinte>` quand `collect_interventions` est vrai. Deux jobs qui
partagent une clé partagent aussi le `path:` exact, la version de l'entrée en
étant un hash. Verrouillé par `tests/test_ci_cache_producteur_ecrivain.py`.
Voir `docs/decisions/cache-mode-interventions-505.md`.

## 4. Les artifacts

**Un artifact = la contribution d'un seul job** (#450). Un job d'extraction
publie uniquement les profils qu'il a **effectivement écrits** — jamais
`raw_data/profiles/`, que son `actions/checkout` a aussi rempli avec la ligne de
base committée. Republier la ligne de base faisait refusionner par la fusion
additive la version périmée et la version corrigée d'un même profil (défaisant
`--no-merge`), et faisait entrer en collision les shards sous `merge-multiple`,
si bien qu'un seul shard survivait.

Le mécanisme : `generate_all_profiles.py --manifest-out` +
`.github/actions/publish-written-profiles`. `merge-and-pivot` n'a besoin
d'aucun artifact pour la ligne de base — il checkoute le dépôt, et
`merge_raw_dirs` ne réécrit que les slugs présents dans les artifacts. Gardé par
`tests/test_ci_publication_profils.py`. Voir
`docs/decisions/publication-scopee-artifacts.md`.

Un artifact sert aussi de **transport horizontal** entre jobs :
`amendements-index-an` et `roster-candidats` sont téléchargés par les jobs
avals plutôt que refabriqués — c'est ce qui donne « zéro fetch roster en CI »
(#518) et « un seul roster par run ».

## 5. Budgets et durées

**Référence : ~66 min pour un run complet** (mesuré le 29/08/2026). Les valeurs
de `timeout-minutes` sont des **filets de sécurité**, pas des dimensionnements —
ne pas budgéter un run à partir d'elles.

| Job | `timeout-minutes` |
|---|---|
| `prepare-an-matrix` | 5 |
| `extract-an` (par shard) | 5, ou 10 si `collect_interventions` |
| `extract-ue-officiel` | 60 |
| `extract-parltrack` | 30 (= `env.PARLTRACK_TIMEOUT_MINUTES`) |
| `extract-amendements-an` | 30 |
| `prepare-roster-matrix` | 15 |
| `extract-roster-groupes` (par shard) | 60 |

Mesures utiles : un shard roster ≈ **200 s**, dont ~130 s de frais fixes (~110 s
de `actions/checkout` seul — le dépôt porte les profils) et ~65 s d'extraction
pour 24 membres. Sharder ×8 paie donc huit fois ces 130 s ; c'est pourquoi la
matrice roster est en `max-parallel: 4` (#467,
`docs/decisions/budget-roster-mesure.md`). `merge-and-pivot` : 7,5 min mesuré à
209 profils, **non mesuré** à 752.

La collecte des interventions se borne **elle-même** par
`--budget-interventions-secondes` (240 s en CI, par candidat, partagé entre les
chambres). Les deux plafonds bougent ensemble : un shard tué par
`timeout-minutes` n'écrit **aucun profil**, tandis qu'un budget épuisé écrit le
profil partiel et déclare la troncature dans `meta.warnings[]`. Gardé par
`tests/test_ci_budget_interventions.py`, voir
`docs/decisions/budget-collecte-interventions.md`.

## 6. Le push

`merge-and-pivot` checkoute avec
`ssh-key: ${{ secrets.DATA_PUSH_SSH_KEY }}` — une **clé de déploiement**, pas le
`GITHUB_TOKEN` (#508). Un ruleset du dépôt applique ses
`required_status_checks` aux **pushes directs**, et ce job pousse sur `main`
sans PR : la règle lui est insatisfiable, pas seulement lente. L'app GitHub
Actions ne peut pas être `bypass_actor` sur un dépôt **personnel**, la clé si.

Deux conséquences à connaître : un push par clé de déploiement **émet un
événement `push`** (le `GITHUB_TOKEN` non), donc `tests.yml` s'exécute
réellement sur les commits de données ; et `deploy-pages.yml` se déclenche deux
fois, sérialisé par son groupe de concurrence `pages`. Secret absent ⇒ le
checkout retombe sur le token et le push est refusé **bruyamment**, en nommant la
règle. Voir `docs/decisions/push-donnees-cle-de-deploiement-508.md`.

Le workflow porte `permissions: contents: read` au niveau global, et
`contents: write` uniquement sur `merge-and-pivot` (#413 §6). Concurrence :
groupe `generate-data`, `cancel-in-progress: false` — deux runs ne committent
jamais en même temps.

## 7. La relance automatique — le couplage invisible

`.github/workflows/retry-generate-data.yml` se déclenche sur
`workflow_run: [completed]` de « Génération des données », que la conclusion soit
`failure` **ou** `success` (#245 : un job en `continue-on-error` peut échouer
réellement sans faire basculer la conclusion globale).

**Rien dans `generate-data.yml` ne référence la relance, et réciproquement.**
Le couplage est réel et muet, et il a déjà cassé deux fois — un `-f` sans input
correspondant (dispatch en **422**, le jour où une relance était nécessaire), et
une sortie écrite sous un nom mais lue sous un autre, qui faisait repartir la
relance **sur les valeurs par défaut, sans erreur ni trace**.

### Ce qui déclenche

1. **Plafond** : si le run échoué a lui-même été déclenché par la relance
   (`triggering_actor == github-actions[bot]`), on ne retente pas. Le plafond est
   porté par l'identité du déclencheur, pas par un compteur : une relance
   **manuelle** repart avec un plafond neuf (#414 §6).
2. **Classement des échecs**, en une seule collecte (`gh api .../jobs --paginate`
   + un seul téléchargement par log de job en échec, #414 §5) : `matched`
   (signature de préemption du runner), `code_change`, `api_error`,
   `inconclusive`, `no_job_failure`. Seuls `matched` et `code_change` relancent.

### Comment les inputs sont reconstruits

**L'API n'expose pas les inputs d'un run.** Ils sont donc **reconstruits en
analysant les logs** des jobs, puis repassés par
`gh workflow run generate-data.yml -f nom=valeur`.

| Input | Où il est lu | Repli |
|---|---|---|
| `cold_start` | le step « Purge des caches… » d'`extract-an` a-t-il conclu `success` | `false` |
| `collect_interventions` | la valeur substituée dans la condition `[[ "<valeur>" != "true" ]] && INTERV_FLAG` du log `extract-an` | `false` |
| `incomplete_read_threshold` | `Seuil : <n>` dans le log `merge-and-pivot` | `3` |
| `roster_limit` | `ROSTER_LIMIT: <n>` dans le bloc `env:` résolu du step roster ; à défaut le stdout de sélection | `0` |
| `existing_profiles` | `EXISTING_PROFILES: <valeur>` dans le même bloc `env:` | la présence de `--no-merge` dans le log `extract-an` ⇒ `overwrite`, sinon `refresh` |
| `add_uncovered_members` | `ADD_UNCOVERED: <bool>` dans le même bloc `env:` | `true` |

Deux pièges qui expliquent la forme de ces greps, et qu'il ne faut pas
« simplifier » :

- le **texte source** `--skip-interventions` est présent dans le log même quand
  la condition était fausse à l'exécution — GitHub journalise le source bash
  substitué, pas la trace d'exécution. Chercher sa seule présence donnerait
  toujours vrai ;
- `roster_limit=0` (le défaut depuis #578) n'émet **aucune** ligne de sélection :
  lire le stdout d'abord faisait retomber tout run complet sur `20`, donc
  relancer un run échantillonné.

Les extractions sont ancrées et restreintes à `[0-9]+` / `(true|false)` pour
qu'une valeur inattendue **échoue la validation** plutôt que d'être transmise
telle quelle, et chaque `grep` porte `|| true` pour qu'une valeur manquante ne
dégrade qu'elle-même au lieu d'avorter tout le step.

Le step de re-déclenchement porte `if: always() && (matched || code_change)`
(#336) : il ne doit pas dépendre du succès du step best-effort qui précède.
Chaque `-f` porte un `|| '<défaut>'` côté expression GHA, aux **mêmes valeurs
par défaut** que celles déclarées dans `generate-data.yml`.

### Les tests qui verrouillent le contrat

Dans `tests/test_ci_inputs_workflow.py` :

- **`test_chaque_input_passe_a_la_relance_existe`** — tout `-f <nom>=` de la
  relance est un input déclaré par `generate-data.yml`. Un `-f` orphelin fait
  échouer le dispatch en 422, jamais avant.
- **`test_chaque_sortie_lue_par_la_relance_est_ecrite`** — tout
  `steps.inputs.outputs.<nom>` lu est un `echo "<nom>=…" >> "$GITHUB_OUTPUT"`
  écrit. Une sortie lue mais jamais écrite vaut la chaîne vide, et la relance
  repart sur les défauts, silencieusement.
- `test_les_deux_axes_sont_propages_par_la_relance` — les deux axes de #578
  passent bien la relance.

Voir `docs/decisions/retry-generate-data-preemption.md`,
`docs/decisions/retry-inputs-appariement-prefixe.md`,
`docs/decisions/retry-generate-data-detection-impossible.md`.

## 8. Les quatre contrôles avant commit, dans `merge-and-pivot`

Les **règles** qu'ils imposent sont dans `AGENTS.md` §3c ; ici, leur ordre, leur
coût et leur placement dans le job. Chacun tourne dans un **processus séparé**,
pour que le pic mémoire du job reste celui du plus gourmand et non leur somme.

| Ordre | Contrôle | Placement | Coût mesuré |
|---|---|---|---|
| 1 | `audit_collecte_non_publiee.py` (#511) | **entre les deux passes `--pivot-only`** — plus tôt, les 543 membres du roster seraient autant de faux manques | 0,08 s / 13,9 Mio à 752 profils ; ne parse aucun profil (deux listages de noms de fichiers) |
| 2 | `audit_diff_profils.py --ref HEAD` (#460/#470) | après les deux passes, avant le commit, sur **tout** `pivot_data/` | pic du job à 186,6 Mio |
| 3 | `audit_integrite_referentielle.py` (#485) | juste après le contrôle de perte | 3,02 s / 162,0 Mio ; 0 orphelin sur 1 347 451 références à `01ffa7f` |
| 4 | `audit_collecte_vs_publie.py` (#545) | après les deux passes, avant le commit | 58,7 s / 158,2 Mio sur 4,3 Go de profils bruts, sans en matérialiser un seul (`object_pairs_hook`) ; 0 déficit et 0 surplus sur 2 380 paires à `3104e37` |

Quatre inputs de tolérance, **cloisonnés** : `allow_declared_losses`,
`allow_broken_references`, `allow_unpublished_profiles`,
`allow_publication_gaps`. Aucun ne désarme le contrôle d'un autre — et
`allow_declared_losses` en particulier ne désarme **pas** l'intégrité
référentielle : une perte peut être légitime, une référence orpheline non.

Le commit ne part que si `check_quality_gate.py` sort en 0, et le push suit la
§6.
