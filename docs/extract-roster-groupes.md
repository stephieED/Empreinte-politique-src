# extract-roster-groupes

## Ce que fait ce job

Il installe l'environnement Python, restaure éventuellement le cache `.cache`,
construit la liste roster-driven puis lance l'extraction individuelle sur
cette liste :

```
python3 src/generate_roster_candidats.py
python3 src/generate_all_profiles.py \
  --candidats raw_data/roster_candidats.json \
  --workers <workers> \
  [--skip-existing | --refresh-existing] --resume \
  --skip-interventions --skip-dossiers-legislatifs \
  [--limit <roster_limit>] [--no-merge]
```

**La population vient de DEUX AXES DISJOINTS (#578).** `existing_profiles`
(`leave-as-is` / `refresh` / `overwrite`) dit ce qu'on fait des profils déjà
écrits ; `roster_coverage` (`current-members-only` / `add-uncovered-members`)
dit si on en écrit de nouveaux. Les six combinaisons se demandent :

| | `current-members-only` | `add-uncovered-members` |
| --- | --- | --- |
| `leave-as-is` | rien à faire (manifeste vide) | `--skip-existing` |
| `refresh` *(défaut)* | `--refresh-existing` | *(aucun drapeau)* |
| `overwrite` | `--refresh-existing --no-merge` | `--no-merge` |

`--skip-existing` est **strict** : il ne saute rien conditionnellement. Pour
recollecter l'existant, on ne le pose pas. `cold_start` n'entre plus dans ce
calcul — il purge les caches de téléchargement, ce qui ne dit rien de ce qu'on
écrit. Voir §*Régénérer l'existant* ci-dessous et
`docs/technical_decisions.md#deux-axes-formulaire-578`.

**Mode d'extraction léger (#357, sous-issue 6/6 de #351)** : `--skip-interventions
--skip-dossiers-legislatifs` sont toujours appliqués ici, indépendamment de
l'input de workflow `collect_interventions` (qui ne pilote que `extract-an`) —
un membre roster n'a besoin que d'identité minimale + mandats + votes +
amendements, seules données consommées par les agrégats de groupe (§4,
`build_groupe_profile()`, #349). `dossiers_legislatifs`/`interventions`/
`questions_officielles` ne sont donc jamais extraits par ce job : ni
consommés par les agrégats de groupe actuels, ni prévus. Voir
`--skip-dossiers-legislatifs` dans `generate_all_profiles.py` (skip aussi bien
le chemin NosDéputés pour les sénateurs que `fetch_textes_portes_officiels`
pour les députés, `candidate_profile.build_profile`).

Voir `.github/workflows/generate-data.yml` (job `extract-roster-groupes`).

Contrairement à `extract-an` / `extract-ue-officiel`, ce job
ne part pas de la liste éditoriale `raw_data/candidats.json` mais de la
composition réelle des groupes parlementaires configurés dans
`raw_data/groupes_reels.json` — couverture de groupe complète (~750+
membres), pas seulement les candidats déclarés/pressentis. Voir
`docs/pipeline-profiles-groupes.md` (tableau des deux sources d'entrée).

---

## Rollout progressif (#188/#190/#192)

## Régénérer l'existant (#445)

Une correction de fond — la clé `uid` de #440, par exemple — ne concerne que
les profils **déjà écrits**. Or `--skip-existing` s'applique *avant*
`--no-merge` : tant qu'il est posé, un run qui écrase saute précisément les
profils qu'il faudrait corriger.

`--refresh-existing` est la sélection strictement inverse de `--skip-existing` :
il ne retient que les candidats dont le profil JSON existe déjà. La combinaison
des deux flags est **refusée** (`SystemExit`) plutôt que de laisser un job
tourner sans écrire un seul profil ; depuis #578 le workflow ne peut plus la
produire, une seule affectation de `POP_FLAG` étant atteinte par run.

Le run correspondant :

| input | valeur |
| --- | --- |
| `existing_profiles` | `overwrite` |
| `roster_coverage` | `current-members-only` |
| `roster_limit` | `0` |

**Le piège réductible a été supprimé (#578).** `roster_limit=0` rafraîchissait
autrefois *moins* que `roster_limit=20` : sans `--limit`, le chemin de #224
(`_select_candidats_couverture`) n'était pas emprunté, et `--skip-existing`
sautait chaque profil existant. Un plafond de volume commandait donc une
politique de rafraîchissement qu'il ne nommait pas. `--limit` n'est plus qu'un
plafond, et recollecter l'existant se demande sur l'axe 1.

Il n'y a plus d'avertissement sur « fusionner au lieu d'écraser ». Le workflow
ne sait pas si le correctif porte sur une clé — il n'a ni le diff de `src/`, ni
l'intention de qui lance le run — et l'avertissement traitait le mode le plus
sûr, devenu le défaut, comme suspect. Le signal qui reste porte sur le mode
destructeur (#460 : écraser sans collecter les interventions), et il chiffre la
perte au lieu de la supposer.

Contrôle après coup : `src/audit_diff_profils.py`, qui compare une ref git au
disque champ par champ et sort en erreur sur toute perte dans les champs
stables (votes, mandats, textes portés).

## Déploiement progressif

Ce job est un **déploiement progressif**, pas encore un run complet :

- `continue-on-error: true` — un échec ou dépassement de ce job ne bloque pas
  `merge-and-pivot` (même traitement que `extract-parltrack`).
- `roster_limit` (input du workflow, défaut `0` depuis #578) borne le nombre
  de membres traités par run (`--limit`) pour rester dans un budget CI
  raisonnable pendant le rollout. **`--limit` est déterministe pour un fichier
  donné, mais l'ordre de `roster_candidats.json` ne l'est pas dans le temps :
  le fichier est régénéré par `generate_roster_candidats.py`.** Une borne
  positionnelle ne désigne donc pas le même sous-ensemble d'un run à l'autre —
  d'où le fait que la sélection utile ne s'appuie jamais sur la position, mais
  sur la couverture (`_select_candidats_couverture`, #224) ou sur l'existence
  du profil (`--refresh-existing`, #445). `0` = pas de plafond, et c'est le
  **défaut depuis #578** : le rollout progressif que ce plafond budgétait est
  terminé (roster couvert à 452/452), et un plafond ferait mentir le défaut
  `existing_profiles=refresh`.
- `timeout-minutes: 60` est provisoire, calibré pour
  `roster_limit=20` avec `--source` implicite (coût par membre
  comparable à `extract-an`) — à recalibrer après un premier run mesuré
  manuellement (`workflow_dispatch`, limite réduite) avant d'envisager
  d'augmenter la limite par défaut.
- L'activation d'un run complet planifié (`schedule: cron`, toujours
  commenté dans `generate-data.yml`) est une décision ultérieure distincte,
  hors périmètre de #192.

---

## Schéma de flux

```mermaid
flowchart TD
    G0["raw_data/groupes_reels.json\nListe des groupes a produire"] --> RC["generate_roster_candidats.py"]

    AMO["data.assemblee-nationale.fr\nAMO30 (archive deja en cache) - cle deputes, #527"] --> GR["group_roster.py\nfetch_full_roster (aiguillage) + filter_roster_by_sigle"]
    NS["NosSenateurs.fr\n/senateurs/json - cle senateurs, et repli AN"] --> GR
    GR --> RC

    RC --> RCJ["raw_data/roster_candidats.json\n(non committe, produit UNE fois par run)"]
    RC --> RBJ["raw_data/rosters_bruts.json\n(--rosters-bruts-out : la MEME collecte, avant filtrage)"]

    RCJ --> ART["artifact : roster-candidats\n(prepare-roster-matrix -> 8 shards + merge-and-pivot)"]
    RBJ --> ART
    ART --> B["generate_all_profiles.py\n--candidats roster_candidats.json"]
    ART --> GP["generate_group_profiles.py\n--rosters-bruts (zero fetch)"]
    B --> C["candidate_profile.py\nbuild_profile(chambre=deputes|senateurs)"]

    CACHE[".cache/\n(evite les re-telechargements)"] -. mise en cache .-> C

    C --> D["raw_data/profiles/<slug>.json\n(meta.provenance = roster_groupe)"]
    D --> E["artifact : raw-profiles-roster-groupes\n(CI/CD - generate-data.yml)"]
    E --> F["merge-and-pivot"]
```

> **Un roster par `(chambre, legislature)` distinct** :
> `generate_roster_candidats.py` le mutualise entre tous les groupes de la
> config (même optimisation que `generate_group_profiles.py` /
> `group_roster.fetch_full_roster`), puis filtre côté client par
> `groupe_sigle` (l'endpoint `/groupe/<SIGLE>/json` de NosDéputés renvoie
> systématiquement une erreur HTTP 500).  
> **La clé `deputes` n'est plus un appel réseau depuis #527** : elle est
> **dérivée d'AMO30**, l'archive que `candidate_profile.py` télécharge et met
> déjà en cache pour quatre autres index. Il ne reste donc, côté roster, que la
> clé `senateurs` — suspendue depuis #516. L'aiguillage est dans
> `group_roster.fetch_full_roster`, seul endroit du dépôt qui choisisse une
> source de roster, et il tient en une condition sur
> `an_roster.AN_ROSTER_ACTIF`. Voir
> `docs/technical_decisions.md#bascule-roster-an-amo30-527`.  
> **`raw_data/roster_candidats.json` n'est pas committé** : source de vérité
> = `raw_data/groupes_reels.json`, produit à chaque run.  
> **UNE construction par run depuis #518** : `prepare-roster-matrix` la fait et
> publie l'artifact `roster-candidats` ; les 8 shards et `merge-and-pivot` le
> téléchargent, et ne régénèrent que si l'artifact manque. Neuf constructions
> indépendantes étaient à la fois fragiles (4 shards perdus sur le run
> `32738726729`) et **incorrectes** : les shards se partagent le roster par
> position, `merge-and-pivot` normalise en pivot **sa** liste — deux listes qui
> divergent produisent un « collecté mais non publié » (#511) sans qu'aucune
> étape n'échoue. Voir
> `docs/technical_decisions.md#roster-unique-par-run-518`.  
> **ZÉRO fetch résiduel depuis le second incident de #518** : le même artifact
> porte aussi le roster **brut** (`--rosters-bruts-out` →
> `generate_group_profiles.py --rosters-bruts`), qui était le dernier à
> refetcher la liste — et le fetch sur lequel le run `32750929942` a perdu son
> commit. Ce n'est pas qu'une requête de moins : la fiche de groupe était bâtie
> sur une composition lue ~7 min après celle qui avait servi à collecter les
> profils. Le plafond de lecture de `fetch_full_roster_nosdeputes` lui est
> désormais propre — `(15, 90)` au lieu des 15 s des pages par candidat, aucune
> réponse de `/deputes/json` n'ayant été mesurée sous 10 s ; depuis #527 il ne
> couvre plus que le Sénat et le repli AN. Voir
> `docs/technical_decisions.md#plafond-roster-et-commit-518`.  
> **Provenance** : chaque profil produit ici porte `meta.provenance =
> "roster_groupe"` — ne rétrograde jamais un profil `candidat_declare`
> existant lors de la fusion (`merge_pivot_profile`), voir
> `docs/technical_decisions.md#provenance-pivot`.  
> **Même fan-out par membre que `extract-an`** : coût par
> candidat identique, seul le volume traité change (borné par
> `roster_limit`).

---

## Logique d'extraction (chaîne interne)

1. `generate_roster_candidats.py` lit `raw_data/groupes_reels.json` (via
   `--config`, défaut ce fichier). Une entrée portant `extraction_suspendue`
   en sort d'emblée (#516) : ni fetch, ni collecte, et son absence n'est pas
   une anomalie. Les **2 groupes Sénat** le sont depuis le 24/08/2026, ce qui
   retire la clé `('senateurs', None)` — donc, aujourd'hui, **1 seul appel
   réseau** au lieu de 2. Voir
   `docs/technical_decisions.md#extraction-groupe-suspendue-516`.
2. Pour chaque `(roster_chambre, legislature)` distinct référencé par les
   groupes **actifs** de la config, il obtient **un seul** roster
   (`group_roster.fetch_full_roster`) — partagé entre tous les groupes de la
   même chambre/législature.
   - Clé `deputes` (#527) : **dérivée d'AMO30**, aucune requête vers
     NosDéputés. Une archive absente, illisible ou sans organe `GP` lève
     `RosterAnIndisponible` ; une législature sans entrée dans
     `correspondance_sigles_an` lève `CorrespondanceSiglesInvalide` en
     **nommant** le couple. Les deux sont dans `group_roster.ERREURS_ROSTER`,
     donc traitées comme un « roster indisponible » ordinaire : rien n'est
     écrit, la clé est annotée, le run ne meurt pas sur une trace de pile.
   - Clé `senateurs` (et repli AN) : fetch réseau, qui reprend jusqu'à 3 fois
     sur un échec **transitoire** (timeout, `ConnectionError`, 502/503/504) et
     **jamais** sur un verdict déterministe (`SSLError`, 4xx, **500**) : #518,
     #524. Un 500 de `nosdeputes.fr` est une signature de panne applicative —
     l'endpoint `/groupe/<SIGLE>/json` en renvoie un systématiquement —, pas un
     hoquet d'infrastructure : le retenter ne change pas le verdict, il retarde
     le message qui le nomme.
3. Chaque roster brut est filtré côté client par `groupe_sigle`
   (`group_roster.filter_roster_by_sigle`), avec filtrage temporel
   additionnel pour le Sénat (`senat_periode_debut`, domaine d'archive
   unique sans sous-domaine par législature).
4. Les membres de tous les groupes sont aplatis en une liste unique de
   candidats (dédupliquée par `slug`, garde-fou en cas de config
   incohérente), écrite dans `raw_data/roster_candidats.json` au même format
   d'entrée que `raw_data/candidats.json` (`{"candidats": [...]}`) —
   `statut: "roster_groupe"`, `notes` référençant le groupe d'origine.
   Un membre **sans slug** ne peut alimenter aucun profil (`<slug>.pivot.json`
   *est* le nom du fichier, #487) : il est donc écarté, mais **nommé** depuis
   #527 — groupe, état civil, dates de mandat, sur `stderr` et en annotation
   `::warning::` (`ROSTER_SANS_SLUG`). Le cas n'existait pas avec NosDéputés,
   dont le slug est l'identifiant ; AMO30 publie un `PA######`, et le slug
   vient de la table committée du lot 2 (#525). Non bloquant : les 4 de la 16e
   sont une catégorie fermée, datée et déclarée dans `groupes_reels.json`
   (`correspondance_sigles_an[].ecart_membres`). Ce qui doit être bruyant,
   c'est leur nombre s'il bouge.
5. **Rien n'est écrit si la collecte est incomplète (#511)** : un fetch en
   échec, un groupe configuré rendant 0 membre, ou un roster total vide font
   sortir le script en 1 sans toucher au fichier. Un `Read timed out` avait
   écrit un roster de 0 candidat en rendant 0, et la passe pivot suivante avait
   itéré sur le vide — run `32405297873`, conclu en `success`. Ce n'est pas un
   seuil de rétrécissement : la granularité d'une panne est la clé de fetch
   entière, soit 452 ou 300 membres sur 752. Voir
   `docs/technical_decisions.md#roster-jamais-ecrit-vide`. Chaque anomalie part
   aussi en annotation `::error::` depuis #518 — un run mort ici ne laissait
   sinon que `Process completed with exit code 1` —, et **nomme sa cause**
   depuis #524 (`HTTPError: 500 …`, `SSLError: …`, `Timeout: …`) : l'exception
   était jusque-là affichée puis jetée, et l'annotation se réduisait à « en
   échec ».
6. **Trois codes de sortie, et ils ne veulent pas dire la même chose** (#524) :

   | Code | Sens | Ce que fait l'appelant |
   |---|---|---|
   | `0` | roster écrit | poursuit la branche roster |
   | `1` | collecte incomplète (§5) **ou** config illisible/vide | `merge-and-pivot` saute la branche roster et committe quand même ; les autres appelants rougissent |
   | `2` | `EXIT_ROSTER_INDISPONIBLE` — **toutes** les entrées ont leur extraction suspendue (#516) | les **trois** appelants sautent la branche roster |

   Aucun de ces codes n'écrit un roster à 0 candidat : `1` et `2` n'écrivent
   rien du tout. Le filtrage se fait **sur le code, dans le shell** — jamais
   par un `continue-on-error: true`, qui avalerait aussi un code non
   documenté. Voir
   `docs/technical_decisions.md#cloisonnement-branche-roster-524`.
5. `generate_all_profiles.py --candidats raw_data/roster_candidats.json`
   pilote ensuite la même chaîne de collecte que `extract-an`
   (`candidate_profile.py`, identité/mandats/votes/amendements via
   NosDéputés + AN Open Data), candidat par candidat, chambre déterminée par
   `roster_chambre` du groupe d'origine — qui ne vaut plus que `deputes`
   depuis #528 — en mode léger
   (`--skip-interventions --skip-dossiers-legislatifs`, #357) : dossiers
   législatifs, interventions et questions officielles ne sont jamais
   extraits ici (non consommés par les agrégats de groupe, #349).
6. `--skip-existing --resume` évite de retraiter les profils déjà présents
   et permet la reprise après interruption ; `--limit` (piloté par
   `roster_limit`) borne le nombre de membres traités ce run.
   `--skip-existing` s'applique **avant** `--no-merge` : voir §*Régénérer
   l'existant* pour la conséquence.
7. Les données sont écrites dans `raw_data/profiles/<slug>.json` puis
   publiées en artifact `raw-profiles-roster-groupes` (`if-no-files-found:
   warn` — ce job peut légitimement ne produire aucun fichier si le fetch
   roster échoue).
   Depuis #580, « les données » = le socle `<slug>.json` **et** ses tranches
   `<slug>/<legislature>.json` — l'action de publication copie les deux.
8. Dans `merge-and-pivot`, cet artifact est fusionné avec ceux de
   `extract-an`/`extract-ue-officiel`
   (`merge_profile.py --dirs`), puis re-normalisé en pivot spécifiquement
   via `raw_data/roster_candidats.json` — **celui du run**, téléchargé depuis
   l'artifact `roster-candidats` (#518), et non plus une liste reconstruite à
   cette étape. No-op silencieux si `extract-roster-groupes` a échoué/été
   absent.

---

## Sources associées

| Source | Contenu |
|---|---|
| `raw_data/groupes_reels.json` | Liste des groupes à couvrir (chambre, législature, sigle) |
| AMO30 (`data.assemblee-nationale.fr`, Licence Ouverte) | Composition des groupes AN, dérivée par `src/an_roster.py` depuis #527 — même archive que les scrutins et les amendements |
| NosSénateurs.fr (`/senateurs/json`) | Liste complète des sénateur·rice·s, filtrée côté client par `groupe_sigle`. Sert aussi de repli AN si `AN_ROSTER_ACTIF` retombe |
| `src/group_roster.py` | Choix de la source (aiguillage #527), mutualisation par clé + filtrage roster par sigle |
| `src/generate_roster_candidats.py` | Aplatissement du roster en liste de candidats (`raw_data/roster_candidats.json`) |
| AN Open Data / NosDéputés / NosSénateurs (via `candidate_profile.py`) | Identité, mandats, votes, amendements — mode léger (#357) : dossiers législatifs/interventions/questions officielles jamais extraits ici |

Référentiel pipeline global : [`pipeline-profiles-groupes.md`](./pipeline-profiles-groupes.md).

---

## À ne pas confondre

| Job | Périmètre |
|---|---|
| `extract-an` | AN / NosDéputés, liste éditoriale `candidats.json` |
| `extract-ue-officiel` | Parlement européen, liste éditoriale `candidats.json` |
| `extract-parltrack` | Téléchargement des dumps ParlTrack (`.zst`) |
| **extract-roster-groupes** | Extraction individuelle pilotée par la composition réelle des groupes (`groupes_reels.json`), rollout progressif borné par `roster_limit`, mode léger (#357) |
| `merge-and-pivot` | Fusion inter-sources + normalisation pivot + profils groupes/partis |

Tout est orchestré dans `.github/workflows/generate-data.yml`.
