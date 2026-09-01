# Le run : `generate-data.yml` et sa relance

Ce que fait un **run** — les jobs, leur ordre, les caches, les artifacts, le
formulaire de lancement, le push, et la relance automatique. Ce que devient la
**donnée** est décrit ailleurs : `docs/data-architecture.md`. Les
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

### Ce que fait chaque job, et pourquoi comme ça

Ce qu'un job **déclare**, le YAML le dit, et il le dit mieux. Ce qui suit est ce
qu'on ne relira pas dans le YAML dans un an : ce que le job fait, ce qu'il
touche, et les deux ou trois décisions qui expliquent sa forme. Le reste du
« pourquoi » vit dans `docs/decisions/` — chaque job y a des dizaines de
fichiers, et ceux cités ici sont les structurants, pas la liste.

#### `prepare-an-matrix`

Lit `raw_data/candidats.json`, en tire la liste des slugs résolvables et la
**Son checkout porte une liste blanche (#674).** Il ne lit que
`raw_data/candidats.json`, et son `timeout-minutes: 5` ne survit pas au
checkout complet : le run `33414042623` l'a vu tué à 5 min 00, donc matrice
jamais publiée, donc `extract-an` **skippé** alors qu'il venait d'être réparé.
La règle vaut pour tout job au budget serré, et un test la fait respecter.

publie comme matrice d'`extract-an` — **un shard par candidat**. Il ne collecte
rien. Il porte aussi deux garde-fous de lancement : un avertissement au-delà de
16 shards (ils s'exécutent en série, donc 16 shards = 16 fois le timeout d'un
shard), et le décompte chiffré des interventions qu'un run
`existing_profiles=overwrite` sans `collect_interventions` effacerait.

**Consomme** `raw_data/candidats.json`. **Produit** la sortie `slugs`.
**Ni `continue-on-error`, ni `if:`** : un `candidats.json` illisible doit
échouer *ici*, lisiblement. Une matrice vide fait *skipper* `extract-an`, et un
job sauté n'est pas un job en échec — `continue-on-error` ne le rattrape pas.

**Pourquoi comme ça** : un runner GitHub peut recevoir un `shutdown signal`
d'infrastructure qui gèle le job entier, steps `if: always()` compris
([résilience au `shutdown signal`](decisions/resilience-generate-data-shutdown-signal.md)) ;
un job séquentiel unique aurait alors perdu la progression de tous les candidats
déjà traités, tandis que le sharding par candidat borne la perte à un seul
([une matrice par candidat](decisions/matrix-extract-an-par-candidat.md)).

#### `extract-amendements-an`

Construit l'index amendements AN **par acteur**, sans condition et
indépendamment de toute liste de candidats :
`python3 src/build_amendements_index.py` sur les législatures
d'`AN_AMENDEMENTS_PATH` (17, 16, 15, 14). Une législature dont l'index est
**figé** — 14, 15 et 16, committés gzippés sous
`raw_data/amendements_an_figes/` — est sautée sans être rechargée : en pratique
la CI ne télécharge que la 17e. Un échec est isolé par législature ; le script
sort en 1 si l'une a échoué, et c'est le `continue-on-error` du job, pas le
script, qui empêche cela de bloquer le run.

**Consomme** les archives amendements de l'open data AN. **Produit**
`.cache/amendements_an/` → artifact `amendements-index-an`, et écrit la clé de
cache `public-data-cache-amendements-<semaine>` (§3).

**Pourquoi comme ça** : la construction paresseuse, au niveau candidat, faisait
télécharger 350 à 650 Mo à l'intérieur d'un shard de 5 minutes, à chaque shard
([un job dédié](decisions/amendements-index-job-dedie-ci.md)) ; ses consommateurs
lisent donc `.cache/amendements_an/` en **cache-only** et ne téléchargent plus
jamais, une législature absente produisant un `meta.warnings` et non un
téléchargement
([consommateurs cache-only](decisions/amendements-index-cache-only-consumers.md)) ;
et un dossier législatif clos ne se re-télécharge pas
([législatures figées](decisions/amendements-legislatures-figees.md)).

#### `extract-ue-officiel`

`python3 src/generate_all_profiles.py --source ue --workers 1` : Open Data
Portal du Parlement européen **uniquement**, aucune source française. Écrit les
profils bruts des candidats dont le MEP ID est résolu, et ne publie que ceux
qu'il a **effectivement écrits** (manifeste + `publish-written-profiles`, §4).

**Consomme** l'Open Data Portal EP. **Produit** l'artifact
`raw-profiles-ue-officiel`, et écrit `public-data-cache-ue-<semaine>` sur
`.cache/europarl` **seul** — cacher `.cache` en bloc lui faisait ré-embarquer
les données AN et amendements, et le quota de cache du dépôt étant partagé,
l'entrée surdimensionnée provoquait l'éviction LRU des autres (#424).

**Pourquoi comme ça** : l'API officielle EP ne permet pas d'attribuer rapports
et amendements à un député européen donné — pas de filtre auteur, ~10-15k
documents sans titre dans la réponse de liste, 1 h 30 et plus de scan par run à
la limite de débit ([périmètre écarté](decisions/hors-perimetre.md)). C'est
l'[investigation des sources UE](decisions/investigation-sources-ue.md) qui a
tranché pour les dumps ParlTrack, d'où le job suivant.

#### `extract-parltrack`

Restaure `.cache/parltrack`, puis télécharge trois dumps `.zst` via
`ensure_dump()` de `src/parltrack_dumps.py` : `ep_dossiers`,
`ep_plenary_amendments`, `ep_amendments`. **Il n'écrit aucun profil** — il
prépare la matière que `merge-and-pivot` consomme à la passe pivot
(`--enrich-parltrack` → `src/normalize_parltrack_dumps.py` → `textes_portes[]`
et `amendements[]` des profils MEP).

**Consomme** `https://parltrack.org/dumps`. **Produit** l'artifact
`parltrack-dumps` — hors de la famille `raw-profiles-*` exprès, puisqu'il ne
contient pas de profils (#412 §4) — et la clé
`public-data-cache-parltrack-<semaine>`.

**Pourquoi comme ça** : source tierce non officielle, donc traitée comme
faillible de bout en bout. Dumps absents ⇒ la passe pivot ajoute un warning de
repli **déclaré** et n'invente rien ; `--parltrack-status-out` écrit le fichier
JSON que `check_quality_gate.py` §5 relit. La licence est ODbL, ce que
`src/licences.py` répercute dans `meta.licence_donnees`
([licences](decisions/licences.md), [lot 6](decisions/licence-lot-6-530.md)).

#### `prepare-roster-matrix`

Construit **une fois pour tout le run** `raw_data/roster_candidats.json` (la
liste roster-driven, filtrée par sigle) *et* `raw_data/rosters_bruts.json` (la
**même** collecte, avant filtrage), publiés dans **un seul** artifact
`roster-candidats` ; puis calcule la liste des 8 shards roster.

**Consomme** `raw_data/groupes_reels.json`. **Produit** l'artifact
`roster-candidats` et les sorties `shards` / `shard_total`. Le filtrage se fait
**sur le code de sortie, dans le shell** : seul le code 2 (« extraction de tous
les groupes suspendue ») est toléré, le code 1 (collecte incomplète) ne l'est
pas — un `continue-on-error: true` avalerait les deux.

**Pourquoi comme ça** : neuf constructions indépendantes du même roster étaient
fragiles et **incorrectes** — les shards se partagent le roster par position,
`merge-and-pivot` normalise **sa** liste, et deux listes divergentes produisent
un « collecté mais non publié » sans qu'aucune étape n'échoue
([un roster par run](decisions/roster-unique-par-run-518.md)) ; le roster brut
voyage dans le même artifact parce que la fiche de groupe était sinon bâtie sur
une composition lue ~7 min après celle qui avait servi à collecter les profils
([plafond roster et commit](decisions/plafond-roster-et-commit-518.md)) ; et un
code de sortie qui distingue « panne » de « rien à collecter » est ce qui permet
au run de conclure vert quand la source est délibérément suspendue
([cloisonnement de la branche roster](decisions/cloisonnement-branche-roster-524.md)).

#### `extract-an`

Un shard par candidat, séquencés un par un (`max-parallel: 1`) :

```
python3 src/generate_all_profiles.py --source an --only <slug> \
  --budget-collecte-secondes 0 --manifest-out _manifest/profils-ecrits.txt \
  [--no-merge] [--skip-interventions] [--budget-interventions-secondes 250]
```

`--source an` force une collecte **Assemblée nationale uniquement**. Un candidat
sans slug est un no-op dans ce scope et n'a donc pas de shard. La chaîne, dans
`src/candidate_profile.py::build_profile(chambre="deputes")` : identité et
mandats depuis le référentiel AMO30 (étape 0, résolue en tout premier),
positions dans l'hémicycle depuis les dumps acteurs historiques, votes depuis
les scrutins nominatifs (législatures 17/16/15/14), amendements lus **en
cache-only** dans `.cache/amendements_an/`, textes portés depuis les dossiers
législatifs (rôle factuel auteur / rapporteur / co-rapporteur), interventions
depuis les comptes rendus Syceron (15/16/17) puis les questions QE/QG/QOSD.
Les URL de jeux de données et les schémas JSON de chacune de ces archives sont
dans [`an-opendata.md`](./sources/an-opendata.md) — référence de la source, qui dérive
avec l'Assemblée et non avec notre code.

**Budget réseau des scrutins, revenu à la normale (#639).** Les trois index
figés committés de `raw_data/scrutins_an_figes/{14,15,16}` ont été reconstruits
le 31/08/2026 et **portent la qualification** : `_load_frozen_scrutins_index` ne
les refuse plus, et les 20,0 Mo d'archives ne sont plus retéléchargés. Relevé le
31/08/2026 — 14 : 1 354 scrutins (`public_ordinaire` 1 213, `solennel` 128,
`tribune` 9, **`motion_censure` 4**) ; 15 : 4 417 (4 288 · 124 · **5**) ; 16 :
4 105 (4 034 · 37 · **34**). Un cache `.cache/scrutins_an` écrit avant #639 reste
refusé, lui, et la première exécution le reconstruit — existence n'est pas
conformité, la règle d'`AGENTS.md` §5.

**Un shard ne matérialise que son propre profil (#674).** Le checkout de ce job
porte une **liste blanche** et `filter: blob:none` : le code, les référentiels de
premier niveau, les index figés, et le seul `raw_data/profiles/<slug>` du shard —
socle et tranches (#580). Le run `33404236969` avait tué ses 13 shards à
5 min 00 **dans `actions/checkout`**, l'étape d'extraction restant `skipped` :
aucun profil écrit, le défaut de #498. L'arbre pesait alors 8 483 Mio, dont
**7 525 pour le seul `raw_data/profiles/`**, quand le plus gros candidat en pèse
16,4. Le `timeout-minutes: 5` n'a **pas** été relevé — le lot supprime la cause.
**Tout nouveau chemin lu par la collecte AN doit entrer dans cette liste** :
oublié, il ne fait pas échouer le checkout, il rend un fichier absent et la
collecte se replie en silence. `tests/test_ci_sparse_checkout_extract_an.py`
échoue localement sur un littéral non couvert, et une étape « Périmètre du
checkout » imprime le poids matérialisé.

**L'AN est source unique, et il n'y a plus aucun repli.** Un slug que le
référentiel AN ne résout pas sort avec `identite: None` et un
`WARNING_PREFIX_IDENTITE_INTROUVABLE` nommant la seule source consultée : il ne
bascule sur rien. Le couple slug ↔ acteur `PA######` est résolu par la table
committée `raw_data/correspondance_acteurs_an.json`, et §5b du garde-fou qualité
échoue déjà sur tout slug publié qui n'y a pas d'entrée.

**Consomme** la matrice de `prepare-an-matrix`, l'open data AN (acteurs actifs et
historiques, scrutins nominatifs, dossiers législatifs, questions, Syceron) et
l'index amendements téléchargé depuis l'artifact `amendements-index-an` — à
défaut, `actions/cache/restore` sur la clé amendements, jamais de sauvegarde,
puisque ce job ne produit pas d'amendements. **Produit** un artifact
`raw-profiles-an-<slug>` par shard, et écrit les clés
`public-data-cache-an-<semaine>[-interv-<empreinte>]` et
`public-data-cache-dossiers-<semaine>`.

**Un profil brut n'est plus un fichier** : `<slug>.json` est le **socle** (le
profil sauf `amendements`), les amendements vivant en tranches sous
`raw_data/profiles/<slug>/<legislature>.json`. L'artifact transporte les deux, et
la relecture passe par `src/profil_brut.py`, jamais par un `json.load` direct
([partition par législature](decisions/partition-profils-legislature-580.md)).

**Pourquoi comme ça** :
[NosDéputés est sorti du pipeline](decisions/retrait-nosdeputes-529.md) — le
profil brut vient entièrement de l'open data AN, et un compteur structurellement
à zéro laissé sous surveillance est un trou muet ;
[Syceron est la seule source de débats](decisions/syceron-actif-510.md) — le
drapeau a été *retiré*, pas baissé, et une collecte vide reste vide en le
déclarant ; [le budget d'interventions](decisions/budget-collecte-interventions.md)
et `timeout-minutes` bougent ensemble, un shard tué par le timeout n'écrivant
**aucun** profil là où un budget épuisé écrit le profil partiel et déclare la
troncature ; et [l'identité AN est primaire](decisions/bascule-identite-an-primaire.md),
adossée à la table [slug ↔ acteur AN](decisions/correspondance-acteurs-an-525.md).

#### `extract-roster-groupes`

La même chaîne de collecte qu'`extract-an`, mais pilotée par la **composition
réelle** des groupes parlementaires (~750 membres) plutôt que par la liste
éditoriale `raw_data/candidats.json` (~8 personnes), et en **mode léger** :
`--skip-dossiers-legislatifs` est toujours posé ici. Les interventions, elles,
suivent `collect_interventions` **depuis #657**, sous une forme réduite —
`--interventions-theme-seul` collecte les débats Syceron sans leur verbatim et
laisse les questions officielles. 8 shards découpés par modulo,
`max-parallel: 4`.

**Consomme** l'artifact `roster-candidats` — régénéré seulement s'il manque — et
les mêmes sources qu'`extract-an`, dont les caches AN et amendements en
**restauration seule**. **Produit** un artifact
`raw-profiles-roster-groupes-<shard>` par shard, tous en
`meta.provenance = "roster_groupe"`, une provenance qui ne rétrograde jamais un
profil `candidat_declare` existant à la fusion
([provenance pivot](decisions/provenance-pivot.md)).

**Pourquoi comme ça** : un membre de roster n'alimente que des agrégats de
groupe, qui ne consomment ni dossiers législatifs ni questions officielles
([mode d'extraction léger](decisions/mode-extraction-leger-roster.md)) — mais
**ils consomment bien les interventions**, dont `tags_thematiques` dérive
intégralement, et l'affirmation inverse a laissé l'« empreinte thématique » de
chaque fiche de groupe être celle d'une seule personne
([collecte réduite au thème](decisions/collecte-interventions-reduite-au-theme-657.md)) ;
la
composition vient d'AMO30 et non plus d'un endpoint tiers, `AN_ROSTER_ACTIF`
étant un interrupteur et non un aiguillage
([bascule vers AMO30](decisions/bascule-roster-an-amo30-527.md)) ; et le
découpage en 8 tranches arbitre entre la borne de perte sur préemption et les
frais fixes de `actions/checkout`, pas le temps de calcul
([shardage en 8 tranches](decisions/shardage-extract-roster-groupes.md)).

**Ce job a de la profondeur** — rollout, régénération de l'existant, les six
combinaisons des deux axes du formulaire, les trois codes de sortie du roster :
→ [`extract-roster-groupes.md`](./extract-roster-groupes.md)

#### `merge-and-pivot`

**Le seul job qui écrit dans le dépôt.** Il enchaîne, dans cet ordre : fusion
additive des profils bruts des trois familles d'artifacts
(`src/merge_profile.py --dirs _artifacts/an _artifacts/ue _artifacts/roster`) ;
**première** passe `--pivot-only` sur `raw_data/candidats.json`, avec
`--enrich-parltrack` ; **seconde** passe `--pivot-only` sur le
`roster_candidats.json` du run ; profils de parti, de groupe parlementaire réel,
de gouvernement ; `check_quality_gate.py` ; les **quatre contrôles** de la §8 ;
la vérification que `src/` et `raw_data/*.json` n'ont pas bougé sur la branche
pendant le run ; le commit et le push ; **le signal disant si ce commit
déclenchera `tests.yml`** (#685, §6) ; la fenêtre de rétention de l'historique
de données ; le déclenchement de `deploy-pages.yml`.

**Consomme** tous les artifacts ci-dessus — mais **aucun** pour la ligne de
base : il checkoute le dépôt, et la fusion ne réécrit que les slugs présents
dans les artifacts. Il lit aussi `.cache/dossiers_an` (restauré par son propre
`actions/cache`, §5) : depuis #639, la construction de `pivot_data/amendements/`
y joint chaque `texte_vise` à son dossier législatif. Archives absentes → aucun
rattachement ajouté, aucun retiré, et le job le dit dans son log. **Produit** le commit de données sur `main`, poussé sous
`secrets.DATA_PUSH_SSH_KEY` — secret qui **n'existe pas** aujourd'hui, si bien
que le push repart sous le `GITHUB_TOKEN` et qu'aucun workflow ne voit le commit
(#685, §6). C'est le seul job à porter
`permissions: contents: write`.

**Pourquoi comme ça** : les quatre contrôles sont **cloisonnés**, aucune
tolérance ne désarmant celui d'un autre — un contrôle grossier rendu bloquant
forcerait à relancer avec sa tolérance, ce qui désarmerait du même coup les
contrôles précis
([contrôle de perte](decisions/controle-de-perte-avant-commit.md)) ; la fusion
est **additive**, une régénération ne retirant jamais de donnée collectée
([une collecte vide n'écrase jamais](decisions/collecte-vide-necrase-jamais.md)) ;
le push passe par une clé de déploiement parce que le ruleset du dépôt applique
ses `required_status_checks` aux pushes directs et qu'une App Actions ne peut pas
être `bypass_actor` sur un dépôt personnel
([clé de déploiement](decisions/push-donnees-cle-de-deploiement-508.md)) ; et un
build dont les entrées ont changé pendant le run ne se committe pas
([ne jamais committer un build périmé](decisions/ne-jamais-committer-un-build-perime.md)).
Le détail est dans la §8 pour les contrôles, la §6 pour le push,
[la fenêtre de rétention](decisions/fenetre-historique-donnees.md) et
[le déclencheur de déploiement](decisions/deploy-pages-declencheur-donnees.md).

## 2. Le formulaire de lancement

Deux axes **disjoints**, plus le cache à part (#578,
`docs/decisions/deux-axes-formulaire-578.md`) :

| Champ | Type | Défaut | Ce qu'il commande |
|---|---|---|---|
| `existing_profiles` | `choice` : `leave-as-is` / `refresh` / `overwrite` | `refresh` | **Axe 1** — ce qu'on fait des profils DÉJÀ écrits. `overwrite` seul lève `--no-merge`. |
| `add_uncovered_members` | `boolean` | `true` | **Axe 2** — si on écrit un premier profil pour les membres qui n'en ont pas. |
| `cold_start` | `boolean` | `false` | Purge les caches de téléchargement et re-télécharge les sources. Ne dit **rien** de la façon dont les profils sont écrits. |
| `roster_limit` | `number` | `0` | Un plafond, et rien d'autre (`0` = pas de plafond). Ne commande aucune politique de rafraîchissement. |
| `collect_interventions` | `boolean` | `false` | Ajoute les archives Syceron et QE/QG/QOSD à `extract-an`, et les **débats seuls, sans verbatim**, au roster (#657). |
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
| `public-data-cache-an-<semaine>[-interv-<empreinte>]` | `.cache/acteurs_historique_an`, `.cache/scrutins_an`, `.cache/questions_an/*/index_par_acteur.json`, `.cache/syceron_an/*/index_par_acteur` | `extract-an` (`actions/cache/save`) | `extract-roster-groupes` (`actions/cache/restore`, **même suffixe** depuis #657) |
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
`-interv-<empreinte>` quand `collect_interventions` est vrai. Le **consommateur**
doit porter ce suffixe aussi (#657) : sans lui, la clé nue de la semaine — écrite
par n'importe quel run en mode par défaut — fait un *exact key hit*, et
`restore-keys` n'est pas consulté après un hit exact ; les 8 shards roster
repartiraient d'une entrée sans contenu Syceron et reconstruiraient les trois
index chacun. Deux jobs qui partagent une clé partagent aussi le `path:` exact,
la version de l'entrée en étant un hash. Verrouillé par `tests/test_ci_cache_producteur_ecrivain.py`.
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

Un push par clé de déploiement **émet un événement `push`**, là où le
`GITHUB_TOKEN` n'en émet aucun : c'est cette bascule qui décide si `tests.yml` et
`deploy-pages.yml` voient passer le commit de données.

**Aujourd'hui elle n'a pas lieu, et c'est mesuré (#685).** Le dépôt n'a **aucune**
clé de déploiement et le secret `DATA_PUSH_SSH_KEY` n'existe pas : `ssh-key` vaut
la chaîne vide, `actions/checkout` retombe sur le `GITHUB_TOKEN` en HTTPS, et
**0 des 15** commits de données arrivés sur `main` depuis que `tests.yml` existe
ne porte de run de la suite. Le refus **bruyant** annoncé sur secret absent ne
parle que sur un `GH013`, lequel suppose le check requis — jamais rétabli non
plus : les deux omissions se couvrent l'une l'autre. Le déclenchement explicite
de `deploy-pages.yml` par `gh workflow run` (#416) est ce qui empêche cette
absence de coûter la publication du site.

Le dernier step du job **mesure** donc `git remote get-url origin` après un push
abouti et dit, en annotation et dans le résumé du job, si `tests.yml` tournera —
non bloquant, parce que les trois gestes qui répareraient le mécanisme (clé,
secret, check requis) vivent hors du dépôt. La garantie revient avec eux, et pas
en réécrivant cette page. Voir
`docs/decisions/push-donnees-cle-de-deploiement-508.md` et
`docs/decisions/identite-du-push-et-declenchement-des-tests-685.md`.

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
| 1 | `audit_collecte_non_publiee.py` (#511) | **après les deux passes `--pivot-only`**, celle de `candidats.json` et celle du roster — placé *entre* elles, tout membre de roster serait un faux manque, puisqu'il est alors légitimement sans pivot. Emplacement vérifié par `tests/test_ci_collecte_non_publiee.py::test_le_controle_suit_les_deux_passes_de_normalisation_pivot` | 0,08 s / 13,9 Mio à 752 profils ; ne parse aucun profil (deux listages de noms de fichiers) |
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
