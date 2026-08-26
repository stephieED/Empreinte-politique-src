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

**`--skip-existing` n'est plus posé en dur (#445).** Il reste le défaut — le
rollout progressif en dépend — mais il est levé par `cold_start` ou par
`overwrite_profiles`, et remplacé par `--refresh-existing` quand l'input
`refresh_existing_only` est actif. Voir §*Régénérer l'existant* ci-dessous.

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

Contrairement à `extract-an` / `extract-senat` / `extract-ue-officiel`, ce job
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
`--no-merge` : tant qu'il est posé, un run `overwrite_profiles=true` saute
précisément les profils qu'il faudrait corriger.

Deux pièges vérifiés, tous deux contre-intuitifs :

- **`roster_limit=0` n'y supplée pas.** Sans `--limit`, le chemin de
  rafraîchissement de #224 (`_select_candidats_couverture`) n'est pas emprunté
  du tout, et `--skip-existing` saute chaque profil existant. Un run à pleine
  échelle n'aurait rien corrigé — il aurait seulement étendu la frontière.
- **Lever `--skip-existing` ne suffit pas non plus.** Avec `--limit`, la
  sélection retombe sur les N premiers du shard, et les profils couverts ne
  forment pas un préfixe : mesuré au 19/08/2026, le dernier couvert se trouvait
  à l'index 93 sur 94 dans deux des huit shards, pour ~26 couverts chacun.

D'où `--refresh-existing` : sélection strictement inverse de `--skip-existing`,
il ne retient que les candidats dont le profil JSON existe déjà. La combinaison
des deux flags est **refusée** (`SystemExit`) plutôt que de laisser un job
tourner sans écrire un seul profil.

Le run correspondant :

| input | valeur |
| --- | --- |
| `overwrite_profiles` | `true` |
| `refresh_existing_only` | `true` |
| `roster_limit` | `0` |

`refresh_existing_only` sans `overwrite_profiles` déclenche un `::warning::` :
la fusion additive conserverait alors les entrées de l'ancienne clé **à côté**
des corrigées, ce qui est pire que de n'avoir rien fait.

Contrôle après coup : `src/audit_diff_profils.py`, qui compare une ref git au
disque champ par champ et sort en erreur sur toute perte dans les champs
stables (votes, mandats, textes portés).

## Déploiement progressif

Ce job est un **déploiement progressif**, pas encore un run complet :

- `continue-on-error: true` — un échec ou dépassement de ce job ne bloque pas
  `merge-and-pivot` (même traitement que `extract-parltrack`).
- `roster_limit` (input du workflow, défaut `20`) borne le nombre
  de membres traités par run (`--limit`) pour rester dans un budget CI
  raisonnable pendant le rollout. **`--limit` est déterministe pour un fichier
  donné, mais l'ordre de `roster_candidats.json` ne l'est pas dans le temps :
  le fichier est régénéré par `generate_roster_candidats.py`.** Une borne
  positionnelle ne désigne donc pas le même sous-ensemble d'un run à l'autre —
  d'où le fait que la sélection utile ne s'appuie jamais sur la position, mais
  sur la couverture (`_select_candidats_couverture`, #224) ou sur l'existence
  du profil (`--refresh-existing`, #445). `0` = pas de limite
  (déconseillé tant que le timeout n'a pas été recalibré sur un run complet).
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

    NS["NosDeputes.fr / NosSenateurs.fr\n/deputes/json ou /senateurs/json"] --> GR["group_roster.py\nfetch_full_roster + filter_roster_by_sigle"]
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

> **2 appels réseau au total** : `generate_roster_candidats.py` mutualise le
> fetch roster par `(chambre, legislature)` distinct présent dans
> `groupes_reels.json` (même optimisation que `generate_group_profiles.py` /
> `group_roster.fetch_full_roster`), puis filtre côté client par
> `groupe_sigle` (l'endpoint `/groupe/<SIGLE>/json` renvoie systématiquement
> une erreur HTTP 500).  
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
> profils. Le plafond de lecture de `fetch_full_roster` lui est désormais
> propre — `(15, 90)` au lieu des 15 s des pages par candidat, aucune réponse
> de `/deputes/json` n'ayant été mesurée sous 10 s. Voir
> `docs/technical_decisions.md#plafond-roster-et-commit-518`.  
> **Provenance** : chaque profil produit ici porte `meta.provenance =
> "roster_groupe"` — ne rétrograde jamais un profil `candidat_declare`
> existant lors de la fusion (`merge_pivot_profile`), voir
> `docs/technical_decisions.md#provenance-pivot`.  
> **Même fan-out par membre que `extract-an`/`extract-senat`** : coût par
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
   groupes **actifs** de la config, il fait **un seul** fetch réseau
   (`group_roster.fetch_full_roster`) — partagé entre tous les groupes de la
   même chambre/législature. Ce fetch reprend jusqu'à 3 fois sur un échec
   **transitoire** (timeout, `ConnectionError`, 502/503/504) et **jamais** sur
   un verdict déterministe (`SSLError`, 4xx, **500**) : #518, #524. Un 500 de
   `nosdeputes.fr` est une signature de panne applicative — l'endpoint
   `/groupe/<SIGLE>/json` en renvoie un systématiquement —, pas un hoquet
   d'infrastructure : le retenter ne change pas le verdict, il retarde le
   message qui le nomme.
3. Chaque roster brut est filtré côté client par `groupe_sigle`
   (`group_roster.filter_roster_by_sigle`), avec filtrage temporel
   additionnel pour le Sénat (`senat_periode_debut`, domaine d'archive
   unique sans sous-domaine par législature).
4. Les membres de tous les groupes sont aplatis en une liste unique de
   candidats (dédupliquée par `slug`, garde-fou en cas de config
   incohérente), écrite dans `raw_data/roster_candidats.json` au même format
   d'entrée que `raw_data/candidats.json` (`{"candidats": [...]}`) —
   `statut: "roster_groupe"`, `notes` référençant le groupe d'origine.
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
   pilote ensuite la même chaîne de collecte que `extract-an`/`extract-senat`
   (`candidate_profile.py`, identité/mandats/votes/amendements via
   NosDéputés/NosSénateurs + AN Open Data), candidat par candidat, chambre
   déterminée par `roster_chambre` du groupe d'origine — en mode léger
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
8. Dans `merge-and-pivot`, cet artifact est fusionné avec ceux de
   `extract-an`/`extract-senat`/`extract-ue-officiel`
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
| NosDéputés.fr / NosSénateurs.fr (`/deputes\|senateurs/json`) | Liste complète des parlementaires, filtrée côté client par `groupe_sigle` |
| `src/group_roster.py` | Fetch mutualisé + filtrage roster par sigle |
| `src/generate_roster_candidats.py` | Aplatissement du roster en liste de candidats (`raw_data/roster_candidats.json`) |
| AN Open Data / NosDéputés / NosSénateurs (via `candidate_profile.py`) | Identité, mandats, votes, amendements — mode léger (#357) : dossiers législatifs/interventions/questions officielles jamais extraits ici |

Référentiel pipeline global : [`pipeline-profiles-groupes.md`](./pipeline-profiles-groupes.md).

---

## À ne pas confondre

| Job | Périmètre |
|---|---|
| `extract-an` | AN / NosDéputés, liste éditoriale `candidats.json` |
| `extract-senat` | Sénat / NosSénateurs, liste éditoriale `candidats.json` |
| `extract-ue-officiel` | Parlement européen, liste éditoriale `candidats.json` |
| `extract-parltrack` | Téléchargement des dumps ParlTrack (`.zst`) |
| **extract-roster-groupes** | Extraction individuelle pilotée par la composition réelle des groupes (`groupes_reels.json`), rollout progressif borné par `roster_limit`, mode léger (#357) |
| `merge-and-pivot` | Fusion inter-sources + normalisation pivot + profils groupes/partis |

Tout est orchestré dans `.github/workflows/generate-data.yml`.
