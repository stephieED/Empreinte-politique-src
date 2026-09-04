# Les commandes du dépôt

**À quoi sert ce fichier.** Retrouver *la* commande sans rouvrir le code, six
mois plus tard. Chaque entrée dit **ce qu'elle fait**, **la commande**, et **ce
qu'elle produit** — rien d'autre. Le *pourquoi* vit ailleurs, et chaque entrée
dit où.

Toutes les commandes se lancent **depuis la racine du dépôt**, environnement
virtuel activé (voir `README.md`, section Installation).

Les 45 exécutables du dépôt ne sont pas tous ici : **une commande est
documentée si la propriétaire peut avoir à la lancer elle-même**. Ce qui est
écarté et pourquoi : dernière section.

`tests/test_commandes_documentees.py` relit ce fichier à chaque run de la
suite : il vérifie que chaque script cité existe et que **chaque option longue
citée est déclarée dans son `argparse`**. Une option supprimée du code fait
rougir la suite ici, au lieu de survivre dans la doc.

---

## Générer des données

### Un profil brut, un seul candidat

```bash
python3 src/candidate_profile.py jean-luc-melenchon
```

Produit : `raw_data/profiles/<slug>.json` (le **socle**) plus une tranche
`raw_data/profiles/<slug>/<legislature>.json` par législature pour les
amendements (#580). `--out` nomme le socle ; les tranches sont son répertoire
frère. `--chambre deputes` est la seule valeur : le Sénat est hors périmètre
(#528).

### Le profil pivot d'un seul candidat

```bash
python3 src/generate_all_profiles.py --only jean-luc-melenchon --pivot
```

Produit : le brut **et** `pivot_data/profiles/<slug>.pivot.json`.

### Tous les candidats déclarés

```bash
python3 src/generate_all_profiles.py --pivot
```

Lit `raw_data/candidats.json`. Produit les bruts, les pivots, et reconstruit au
passage les deux index partagés. Options de conduite les plus utiles :

| Option | Effet |
|---|---|
| `--skip-existing` | ne régénère pas un profil déjà écrit |
| `--refresh-existing` | l'inverse : ne régénère **que** l'existant |
| `--limit 20` / `--sample 20` | déploiement progressif / échantillon aléatoire |
| `--workers 4` | parallélisme entre candidats (défaut 4 ; baisser si l'API renvoie 429) |
| `--resume` | reprend après interruption |
| `--budget-collecte-secondes 160` | plafond de collecte **par candidat** ; `0` déclare l'absence de plafond |
| `--budget-job-secondes 600` | plafond de collecte pour **tout le run** |
| `--no-merge` | remplace au lieu de fusionner (la fusion est additive par défaut) |
| `--skip-interventions` | ne collecte ni débats Syceron ni questions officielles |
| `--interventions-theme-seul` | collecte les débats **sans leur verbatim** et laisse les questions officielles ; chaque entrée publiée porte `collecte: "theme_seul"`. Sans effet sur un slug de `raw_data/candidats.json`. Incompatible avec `--skip-interventions` |

Renormaliser sans aucun appel réseau, depuis les bruts déjà collectés :

```bash
python3 src/generate_all_profiles.py --pivot-only --no-checkpoint
```

→ `docs/workflow-generate-data.md` pour ce que le run fait job par job,
`docs/data-architecture.md` pour ce que la donnée devient.

### La couverture complète des groupes (extraction pilotée par roster)

```bash
python3 src/generate_roster_candidats.py
python3 src/generate_all_profiles.py --candidats raw_data/roster_candidats.json --pivot --skip-existing
```

Produit : `raw_data/roster_candidats.json` (la composition réelle des groupes
de `raw_data/groupes_reels.json`, au lieu de la liste éditoriale), puis les
profils de ses membres. `--skip-existing` combiné à `--limit` fait avancer la
frontière de couverture d'un run à l'autre au lieu de retenter les mêmes.

Pour peupler aussi l'empreinte thématique des fiches de groupe, ajouter
`--interventions-theme-seul` : les débats sont collectés sans leur verbatim,
et `tags_thematiques` cesse d'être vide (#657). C'est ce que le job CI fait
quand `collect_interventions` est coché.

→ `docs/extract-roster-groupes.md`.

### Tout le pipeline, en local plutôt qu'en CI

```bash
./scripts/generate_data_local.sh
```

Enchaîne les mêmes étapes que `generate-data.yml` sur la machine. Se relance en
arrière-plan par défaut et rend la main en affichant le PID et le journal
(`logs/`, git-ignoré) ; `BACKGROUND=false ./scripts/generate_data_local.sh` le
garde attaché au terminal. **Rien n'est committé ni poussé** : relire
`git status` avant de committer soi-même.

Réglages, passés en variables d'environnement — mêmes axes que le formulaire de
lancement :

| Variable | Défaut | Input `workflow_dispatch` correspondant |
|---|---|---|
| `EXISTING_PROFILES` | `refresh` | `existing_profiles` |
| `ADD_UNCOVERED_MEMBERS` | `true` | `add_uncovered_members` |
| `COLD_START` (alias `FRESH_RUN`) | `false` | `cold_start` |
| `THRESHOLD` | `3` | `incomplete_read_threshold` |
| `WORKERS` | `1` | *(local seulement — figé à 1 en CI)* |
| `EXTRACT_INTERVENTIONS` | `false` | `collect_interventions` |
| `ROSTER_EXTRACTION_LIMIT` | `0` (sans plafond) | `roster_limit` |
| `BACKGROUND` | `true` | *(local seulement)* |

→ `docs/workflow-generate-data.md` §2 pour les deux axes du formulaire (#578).

### Une fiche de groupe parlementaire

Tous les groupes déclarés dans `raw_data/groupes_reels.json`, en un run :

```bash
python3 src/generate_group_profiles.py --validate
```

Produit : `pivot_data/groupes/groupe-<SIGLE>-<leg>.json`. Codes de sortie :
`0` tout va bien, **`2` roster indisponible** (rien n'est écrit, les fiches
publiées restent intactes), `1` une génération a réellement échoué.
`--merge-existing` conserve les membres déjà connus qu'un fetch incomplet
n'aurait pas rendus.

Un seul groupe, à la main :

```bash
python3 src/group_profile.py --groupe-id "AN:SOC" --groupe-sigle SOC \
    --groupe-nom "Socialistes et apparentés" --chambre AN --legislature 16 \
    --out pivot_data/groupes/groupe-SOC-16.json \
    pivot_data/profiles/jerome-guedj.pivot.json pivot_data/profiles/boris-vallaud.pivot.json
```

### Une fiche de gouvernement

Tous les gouvernements déclarés dans `raw_data/gouvernements_reels.json` :

```bash
python3 src/generate_gouvernement_profiles.py --validate \
    --commissions-dossiers pivot_data/commissions_dossiers.json
```

Produit : `pivot_data/gouvernements/gouvernement-<ID>.json`.

`--commissions-dossiers` (défaut `pivot_data/commissions_dossiers.json`) donne
l'index d'où chaque texte tire sa **commission saisie au fond** (#689) — la
matière qu'une fiche peut afficher sans qu'on en invente une. Absent, illisible
ou vide, chaque texte publie `commission_non_resolue.motif = index_indisponible`,
et jamais un silence : une panne du run ne doit pas se lire « aucun texte n'a de
commission ».

Un seul gouvernement :

```bash
python3 src/gouvernement_profile.py --gouvernement-id "gouvernement:BAYROU" \
    --out pivot_data/gouvernements/gouvernement-BAYROU.json --validate
```

### Les agrégats de partis

```bash
python3 src/parti_profile.py --candidats raw_data/candidats.json \
    --profiles-dir pivot_data/profiles --out-dir pivot_data/partis
```

Produit : `pivot_data/partis/parti-<slug>.json` — des agrégats **éditoriaux** de
candidats déclarés, pas des groupes parlementaires réels. Générés pour un usage
interne, pas affichés comme onglet dans `web/UI_finale`.

### La table des commissions saisies au fond

```bash
python3 src/build_commissions_dossiers.py
python3 src/build_commissions_dossiers.py --no-merge
```

Produit : `pivot_data/commissions_dossiers.json` — par dossier législatif, la
commission que l'Assemblée a saisie au fond, lue sur l'acte
`AN1-COM-FOND-SAISIE` des archives déjà en cache et résolue en organe par le
référentiel AMO30. C'est ce que « L'essentiel » de la fiche candidat publie pour
répartir les dossiers amendés ; sans ce fichier, la répartition n'est pas
affichée, et elle n'est **jamais** déduite d'un intitulé de dossier.

La fusion est additive : un run sans archive lisible conserve la table publiée.
`--no-merge` reconstruit de zéro et exige donc que les trois archives aient été
lues.
→ `docs/decisions/vivier-de-points-et-empreinte-de-commission-328.md`.

### Un profil d'eurodéputé (Parltrack), et la date de son cache

```bash
python3 src/mep_profile.py --name "Manon Aubry"
python3 src/mep_profile.py --list
python3 src/mep_profile.py --show-cache-date
```

Affiche le profil sur la sortie standard (`--out` pour écrire un fichier). Le
premier appel télécharge de gros dumps dans `.cache/parltrack/` :
`--show-cache-date` dit de quand ils datent.

### Le suivi des candidatures (Wikipédia / Wikidata)

```bash
python3 src/fetch_wikipedia_candidates.py
python3 src/fetch_wikipedia_candidates.py --source wikidata --json
```

Produit : un résumé de relecture sur la sortie standard. Ce script **ne modifie
jamais** `raw_data/candidats.json` — la mise à jour de la liste reste une
décision éditoriale, prise à la main.

---

## Auditer

Ce sont des **outils internes de qualité**, jamais des rapports publiables :
pas de score, pas de classement (`AGENTS.md` §2.1). Aucun n'écrit dans
`pivot_data/` ni dans `raw_data/`.

Les quatre premiers partagent le même contrat d'options : `--output-json` /
`--output-md` non renseignés par défaut (le JSON part sur la sortie standard,
le Markdown est simplement sauté), `--staleness-days 30` fixe le seuil
au-delà duquel une fiche dont toutes les sources sont anciennes est signalée,
et `--output-dir DOSSIER` écrit les deux fichiers sous un nom horodaté au lieu
de les nommer un par un.

### Les profils pivot

```bash
python3 src/audit_pivot_dataset.py --input-dir pivot_data/profiles \
    --output-json audit_pivot.json --output-md audit_pivot.md --staleness-days 30
```

Produit : volumétrie (dont la répartition `candidat_declare` / `roster_groupe`),
complétude, cohérence, fraîcheur des sources, `meta.warnings[]` agrégés, et deux
tableaux croisés `votes` / `textes_portes` / `amendements` / `interventions`.
Les candidats déclarés y figurent nommément ; les profils issus du roster sont
agrégés par groupe, jamais membre par membre.

### Les fiches de groupe

```bash
python3 src/audit_groupe_dataset.py --input-dir pivot_data/groupes \
    --scrutins pivot_data/scrutins.json \
    --output-json audit_groupe.json --output-md audit_groupe.md
```

Produit : mêmes axes que ci-dessus pour `pivot_data/groupes`, plus les
`cohesion_votes`, les `amendements_agreges` et l'écart de couverture du roster.

`--scrutins` (défaut `pivot_data/scrutins.json`) fournit l'index partagé d'où
vient la **date** de chaque scrutin de cohésion : `cohesion_votes[]` ne porte
qu'un `scrutin_id` depuis #432. Un index absent ou vide n'est pas une panne —
les plages temporelles sont vides et le rapport le **déclare** (#726).

### Les fiches de gouvernement

```bash
python3 src/audit_gouvernement_dataset.py --input-dir pivot_data/gouvernements \
    --output-json audit_gouvernement.json --output-md audit_gouvernement.md
```

Produit : mêmes axes pour `pivot_data/gouvernements`, plus la présence de
`premier_ministre`, le taux de `membres[].portefeuille` renseigné, et la
**couverture des archives de dossiers** — pour qu'« hors couverture de la
source » ne se lise jamais « vraiment zéro » (#399).

### Les trois d'un coup

```bash
python3 src/audit_pipeline.py --output-json audit_pipeline.json --output-md audit_pipeline.md
```

Il porte lui aussi `--scrutins` (même défaut, même rôle), qu'il passe à l'audit
des groupes.

Produit : les trois rapports détaillés plus une « vue d'ensemble » (totaux
audités, erreurs de lecture, warnings agrégés). Pure composition — aucun calcul
nouveau. Volontairement **jamais** branché sur la CI (#178). Un répertoire
manquant est une erreur explicite, code de sortie 1, jamais une trace d'appel.

### À quoi ressemble un rapport

Sans toucher au corpus, sur les fixtures figées de la suite de tests. Une
commande ne peut pas être périmée, un exemple committé si :

```bash
python3 src/audit_pivot_dataset.py --input-dir tests/fixtures/audit_pivot \
    --output-json audit_pivot_exemple.json --output-md audit_pivot_exemple.md
```

Même chose avec `--input-dir tests/fixtures/audit_groupe` et
`tests/fixtures/audit_gouvernement` pour les deux autres.

### La clé `(legislature, numero_scrutin)` est-elle utilisable ?

```bash
python3 src/audit_legislature_votes.py
python3 src/audit_legislature_votes.py --out audit/legislature_votes.md
```

Passe de corpus, sans réseau, qui **ne modifie aucun fichier**. Sortie 0 si
toutes les législatures de votes sont résolues, 1 sinon. À lancer avant de se
fier à la clé : `numero_scrutin` repart à 1 à chaque législature.
→ `docs/decisions/resolution-legislature-votes.md`.

### Volumétrie : ce que pèse le corpus et ce que rapporterait chaque levier

```bash
python3 src/audit_volumetrie_profils.py --profils-dir pivot_data/profiles \
    --echantillon 60 --out audit/volumetrie.md
```

Produit : le poids mesuré des profils et le gain de chaque levier d'allègement
(compactage, gzip, externalisation d'un champ vers un index dédié), plus une
projection vers `--cible`. Mesure des leviers qui **déplacent** la donnée, pas
qui la suppriment. → `docs/decisions/` (#429).

Variante hors dépôt, pour générer le roster complet sans polluer l'arbre
versionné (~6 Go de churn sinon) :

```bash
./scripts/mesure_volumetrie_roster.sh
```

Écrit dans `../empreinte-mesure-volumetrie` par défaut (`OUT_DIR`), journal sous
`logs/`. Rien n'est jamais committé.

---

## Vérifier avant de committer

Ce sont les **cinq contrôles que la CI exécute avant chaque commit de données**,
tous relançables à la main à l'identique. Chacun tourne dans son propre
processus, et **aucune tolérance n'en désarme un autre**.

### Le quality gate — le seul gate bloquant

```bash
python3 src/check_quality_gate.py
```

Sortie 0 = le commit est autorisé. Sections dures : `IncompleteRead` au-delà du
seuil, fichier de groupe ou de gouvernement manquant ou invalide, format des
index amendements figés, slug publié sans correspondance AN (§5b), et la §7 qui
**échoue à 80 Mio** sur le plus gros fichier versionné (avertissement dès
50 Mio). Réglages courants :

```bash
python3 src/check_quality_gate.py --threshold 0
python3 src/check_quality_gate.py --low-interventions 5
python3 src/check_quality_gate.py --groupe-min-coverage-pct 50
python3 src/check_quality_gate.py --amendements-staleness-days 14
python3 src/check_quality_gate.py --blob-warn-mo 0
```

→ `docs/data-architecture.md` (le tableau des sections, dur/souple).

### Contrôle de perte — une régénération ne retire jamais de la donnée

```bash
python3 src/audit_diff_profils.py --ref HEAD
```

Compare **deux états** de `pivot_data/`. Trois constats bloquent : un fichier
**disparu**, une **baisse sur une liste stable**, un **scalaire surveillé qui
passe de renseigné à `null`**. Le reste est rapporté sans bloquer. Une perte
légitime se **déclare** (`--tolerer-pertes`), elle ne se contourne pas en
retirant le contrôle.

### Intégrité référentielle — chaque clé publiée résout

```bash
python3 src/audit_integrite_referentielle.py
python3 src/audit_integrite_referentielle.py --sans-amendements
```

Vérifie une **invariance dans un seul état** : depuis les deux index partagés,
un vote ou un amendement n'a de sens que si sa clé résout dans l'index qu'elle
désigne. Sortie non nulle en nommant fichier et clé. `--sans-amendements` ne
contrôle que les scrutins, bien moins cher.

### Tout ce qui est collecté est-il publié ?

```bash
python3 src/audit_collecte_non_publiee.py
```

Sortie non nulle dès qu'un `raw_data/profiles/<slug>.json` n'a pas son
`pivot_data/profiles/<slug>.pivot.json`. Seuil **0**. Ne parse aucun profil —
deux listes de noms de fichiers.

### Chaque liste publiée porte-t-elle ce qui a été collecté ?

```bash
python3 src/audit_collecte_vs_publie.py
```

Le contrôle précédent raisonne sur des **profils** ; celui-ci sur le **contenu
de leurs listes** — un pivot présent mais vidé de ses interventions lui est
irréprochable. Chaque liste publiée déclare dans `RELATIONS` les chemins du brut
dont elle est la somme, d'où un seuil **0** partout. Le déficit bloque,
l'excédent est rapporté.

Les quatre derniers écrivent aussi un rapport avec `--out` (Markdown) et
`--out-json`.
→ `docs/workflow-generate-data.md` §8 pour leur placement exact dans le run.

---

## Opérer

### Régénérer la table slug ↔ acteur AN

```bash
python3 src/build_correspondance_acteurs_an.py --verifier
python3 src/build_correspondance_acteurs_an.py
```

`--verifier` n'écrit rien et sort 1 s'il manque un slug ; sans lui, la table
`raw_data/correspondance_acteurs_an.json` est complétée et réécrite. Les
entrées existantes sont reconduites **verbatim** — c'est du travail relu — et un
slug non résolu est **nommé sur stderr** plutôt qu'inventé. C'est le remède
quand le quality gate §5b échoue en nommant un slug **hérité**.

```bash
python3 src/build_correspondance_acteurs_an.py \
  --completer-derivees --rosters-bruts raw_data/rosters_bruts.json
```

Passe **additive et hors ligne** (#715), celle que `merge-and-pivot` lance avant
le portail : elle ajoute une entrée `origine: "derivee"` pour les seuls slugs
que `raw_data/rosters_bruts.json` déclare **fabriqués** (#708), c'est-à-dire
dérivés de l'état civil de leur acteur — il n'y a là aucun rapprochement à
prouver, seulement l'identifiant à **geler**. Elle ne lit ni AMO30 ni le réseau,
ne réécrit aucune entrée relue, et refuse en nommant le slug si le profil publié
ne porte pas exactement l'acteur que le roster déclare.
→ `docs/decisions/correspondance-acteurs-an-525.md`,
`docs/decisions/entree-derivee-correspondance-715.md`.

### Régénérer la table « ce module → ces décisions »

```bash
python3 scripts/generer_decisions_par_module.py --verifier
python3 scripts/generer_decisions_par_module.py
```

`--verifier` n'écrit rien et sort 1 si le fichier committé a dérivé du dépôt ;
sans lui, `docs/decisions-par-module.md` est réécrit. À relancer après avoir
ajouté ou modifié une décision, ajouté ou renommé un module de `src/`, ou
renommé une fonction qu'une décision nomme. `tests/test_decisions_par_module.py`
fait la même vérification dans la suite.
→ `docs/decisions/table-inversee-decisions-par-module.md`.

### Vérifier que les SHA cités sont archivés dans Software Heritage

```bash
python3 src/verifier_archivage_swh.py
python3 src/verifier_archivage_swh.py --json --sans-issues
```

Relève les SHA **effectivement cités** dans les `.md` suivis et les corps
d'issues, puis demande à Software Heritage s'ils résolvent. Trois verdicts, par
code de sortie : `0` vérifié, `1` des SHA manquent (**ne pas couper**), `2`
indéterminé — quota épuisé ou API injoignable, on n'a rien établi.
`--sans-issues` se limite aux fichiers du dépôt (pas de `gh` requis).
**À lancer avant tout bornage d'historique**, jamais après.

### Borner l'historique de données

Deux scripts, deux contrats. **La mesure d'abord** — elle ne touche à rien :

```bash
./scripts/borner_historique_donnees.sh --mesurer
./scripts/borner_historique_donnees.sh --mesurer --fenetre 30
```

Clone le dépôt dans un répertoire temporaire, y applique la coupure, repacke et
rend le gain **réel**. Ne pousse jamais, ne modifie jamais `main`.

**L'exécution ensuite**, par le runner guidé — sept étapes dont trois
irréversibles, dans un ordre dont une seule inversion est irrattrapable :

```bash
./scripts/executer_bornage_guide.sh --lister
./scripts/executer_bornage_guide.sh --fenetre 30
./scripts/executer_bornage_guide.sh --reprendre logs/bornage_<horodatage>.log
```

`--lister` affiche les sept étapes et sort sans rien faire. Le runner impose
l'ordre, refuse d'avancer sur une précondition en échec, et tient un journal de
ce qui a été fait. `--etape N` n'exécute qu'une étape, `--jusqu-a N` s'arrête
après la N-ième.

### Sortir de `commission` les mandats que l'AN type « gouvernement » (#730)

```bash
python3 src/reprise_mandats_gouvernementaux.py            # simulation
python3 src/reprise_mandats_gouvernementaux.py --apply     # applique
```

Huit mandats ministériels étaient publiés en `commission`, sur l'organe
`Gouvernement`. Le critère est **le typage du référentiel** — l'index d'organes
AN type cet organe `GOUVERNEMENT`, et c'est le seul libellé dans ce cas — jamais
une lecture du libellé. Une entrée dont la période est déjà couverte par un
`fonction_gouvernementale` du profil est **retirée** ; sinon elle est
**requalifiée**, parce que la retirer effacerait une période réelle.

Simulation par défaut, idempotent, et sans effet si l'index d'organes manque
(`.cache/acteurs_historique_an/index_organes_v2.json`) : un critère qui ne peut
pas s'établir ne se devine pas.

### Les migrations ponctuelles

Déjà appliquées au corpus. Elles restent relançables : **`--verifier` ne
modifie rien** et dit si le corpus est conforme.

```bash
python3 src/migrer_identite_couverture_539.py --verifier
python3 src/migrer_absences_publiees_556_558_560.py --verifier
python3 src/migrer_profils_partitionnes_580.py --verifier-seulement
python3 src/purge_mandats_dupliques.py --only jean-luc-melenchon
```

Pour écrire réellement : retirer `--verifier` sur les deux premières, passer
`--apply` sur les deux dernières. Chacune est décrite dans la décision qui porte
son numéro, sous `docs/decisions/`.

---

## Voir ce que voit l'utilisatrice

### Le formulaire de lancement, tel que GitHub l'affiche

```bash
python3 scripts/rendu_formulaire.py
```

Rend les inputs `workflow_dispatch` de `generate-data.yml` **tels qu'ils
apparaîtront à l'écran**, largeur comprise. **À lancer avant de toucher à un
libellé** : relire le YAML masque exactement le défaut corrigé par #578.
→ `docs/workflow-generate-data.md` §2.

### L'interface, en local

```bash
cd web/UI_finale
npm install
npm run dev
```

`npm install` seulement la première fois. `npm run dev` synchronise d'abord les
données pivot vers `public/data/` (généré, git-ignoré) puis démarre Vite. La
couverture affichée se limite aux candidats, groupes et gouvernements qui ont un
fichier pivot en local.

Les générations de design archivées (`web/old/`, v1–v7) sont du HTML statique :

```bash
python3 -m http.server 8000
```

### La suite de tests

```bash
pytest -q
```

Environ 11 s. Aucun test ne lit `pivot_data/` ni `raw_data/profiles/`, n'écrit
sous l'un des deux, ni ne sort sur le réseau (#473).
→ `docs/decisions/ci-tests-pytest.md`.

---

## Ce qui n'est pas ici, et pourquoi

Le dépôt compte **45 exécutables** (40 modules `src/` avec un CLI, 5 scripts).
Ce fichier en documente **33**. Les 12 autres ont un CLI, mais personne n'a de
raison de les taper :

| Écarté | Pourquoi |
|---|---|
| `src/candidate_profile_ue.py` | `generate_all_profiles.py` l'appelle déjà pour chaque candidat ; son CLI sert au débogage |
| `src/gouvernement_roster.py` | ne produit que la composition ministérielle, un étage de `gouvernement_profile.py` |
| `src/group_roster.py`, `src/an_roster.py` | la composition réelle d'un groupe, lue par les générateurs ; leur CLI est une vue de débogage |
| `src/merge_profile.py` | la fusion additive, appelée à chaque régénération |
| `src/build_scrutins_index.py`, `src/build_amendements_index_pivot.py` | les deux index partagés — `generate_all_profiles.py --pivot` les reconstruit au bon moment, et l'ordre compte |
| `src/build_amendements_index.py` | le point d'entrée du job CI `extract-amendements-an`, sans option |
| `src/build_scrutins_index_figes.py`, `src/build_amendements_index_figees.py` | les législatures closes (14/15/16) : construites **une fois**, hors ligne, puis committées sous `raw_data/`. La procédure complète et ses modes de défaillance sont dans `docs/decisions/amendements-legislatures-figees.md` et `docs/decisions/votes-multi-legislature.md` |
| `src/cache_an_fraicheur.py`, `src/cache_an_empreinte.py` | la mécanique de cache des jobs CI, sans usage local |

Aucun n'est mort. Dix sont sur le chemin d'exécution du pipeline, et
`docs/workflow-generate-data.md` dit quel job les appelle ; les deux derniers
sont des constructions ponctuelles, hors ligne, dont la procédure est écrite
dans la décision qui les porte.

Les deux index partagés, eux, se reconstruisent à la main quand un run a été
interrompu : la commande et **l'ordre à respecter** sont dans
`docs/data-architecture.md`, avec la raison de cet ordre.
