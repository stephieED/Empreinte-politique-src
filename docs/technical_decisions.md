<a id="retry-preemption-logs"></a>
## `gh api .../logs` sans `--allow-escape-sequences` : cause racine de l'inefficacité du retry automatique sur les runs #26-28 (#236) (2026-08-13)

**Contexte** : [[retry-generate-data-preemption]] (#230) a ajouté
`retry-generate-data.yml`, qui détecte la signature de préemption runner via
`gh api repos/${REPO}/actions/jobs/<id>/logs` (deux points d'appel). Sur les
trois premiers runs `generate-data.yml` en échec après la fusion de #230
(#26, #27, #28 — diagnostic complet en #235), le retry automatique ne s'est
jamais concrétisé alors que la signature de préemption (`shutdown signal`
runner) était bien présente dans les logs bruts des jobs concernés.

**Cause racine** : `gh api` refuse d'écrire sur stdout un contenu contenant
des séquences d'échappement ANSI (couleurs de terminal — présentes dans la
quasi-totalité des logs Actions de ce dépôt) et retourne l'exit code 1 avec
le message `the response contains terminal escape sequences; pass
--allow-escape-sequences to output it anyway`, sauf si ce flag est
explicitement passé. Reproduit manuellement contre le job réel du run #28
(`extract-an`, job id `94359092658`, cf. corps de #235) :
```
$ gh api "repos/stephieED/Empreinte-politique-src/actions/jobs/94359092658/logs" 2>&1 1>/dev/null
the response contains terminal escape sequences; pass --allow-escape-sequences to output it anyway
$ echo $?
1
```
Le `2>/dev/null || true` de `retry-generate-data.yml` avalait cette erreur
silencieusement : `log` était capturé comme une chaîne vide, le
`grep -qE "shutdown signal|The operation was canceled\."` ne matchait donc
jamais, et `matched` restait `false` **même quand la signature était
réellement présente** — un faux négatif systématique et non occasionnel,
puisque la présence de couleurs ANSI dans un log Actions est la norme, pas
l'exception.

**Correctif (#236)** : ajout de `--allow-escape-sequences` aux deux appels
`gh api .../logs` de `retry-generate-data.yml` (step de détection et
fonction `job_log()` de reconstruction des inputs). Diff limité aux deux
lignes concernées, aucun changement de logique de détection — déjà sur
`main` au moment de cette entrée.

**Validation empirique — état par run** :
- **Run #28** (job `extract-an`, id `94359092658`) : confirmé — la commande
  corrigée (`gh api .../logs --allow-escape-sequences`) a été rejouée
  manuellement contre ce job réel (cf. #235) et le
  `grep -qE "shutdown signal|The operation was canceled\."` matche
  désormais, alors que la commande sans le flag échouait avec l'exit code 1
  ci-dessus (log vide côté script).
- **Runs #26 et #27** : ces deux runs n'ont **jamais atteint** le code
  touché par #236. Leur retry a crashé plus tôt, sur
  `jobs_json=$(gh api ".../jobs" --paginate)` (échec transitoire
  d'API/pagination, sous `set -euo pipefail` sans fallback à l'époque) — bug
  distinct, corrigé séparément par #237 (capture explicite + outputs
  `api_error`/`inconclusive`, cf.
  [[retry-generate-data-detection-impossible]]). Il n'existe donc pas de log
  historique de ces deux runs démontrant `matched=true` obtenu via le
  correctif #236 spécifiquement : l'erreur qui les a fait échouer était en
  amont de ce code et transitoire (non reproductible à l'identique a
  posteriori). Ce que #237 garantit pour ce cas précis : une erreur API sur
  le listing des jobs se traduit désormais par `api_error=true` et un
  message dédié « détection impossible », plus jamais par un crash opaque du
  job — un futur run frappé du même incident transitoire restera visible
  dans le résumé au lieu de se terminer en `failure` sans trace exploitable.
- **Portée de la vérification agent (#238)** : le token disponible dans
  l'environnement agent (`metadata=read` uniquement, pas de scope `actions`)
  ne permet pas d'interroger l'API Actions depuis cette session — tout appel
  `gh api repos/.../actions/...` y renvoie `403 Resource not accessible by
  personal access token`. Impossible de rejouer une nouvelle fois la
  commande corrigée contre les trois runs depuis cet agent ; la preuve
  ci-dessus pour #28 réutilise la reproduction déjà réalisée manuellement
  par @stephieED (accès dashboard complet) et documentée dans #235. Aucune
  preuve équivalente n'est disponible pour #26/#27, par nature (voir
  point précédent) — pas un manque de vérification, mais l'absence de
  matière à vérifier pour ces deux runs sur ce correctif précis. Une
  vérification complémentaire sur #26/#27 nécessiterait un token avec le
  scope `actions:read`, ou une exécution manuelle de
  `gh api .../jobs --paginate` sur ces runs (l'erreur d'origine étant
  transitoire, elle peut désormais réussir ou échouer différemment).

**Piège générique à retenir** : tout script CI de ce dépôt qui appelle
`gh api` sur un endpoint `.../logs` ou `.../jobs/<id>/logs` (contenu texte
potentiellement coloré ANSI) doit systématiquement passer
`--allow-escape-sequences`, sous peine d'un échec silencieux si le flux
d'erreur est avalé par `2>/dev/null || true` ou équivalent. Plus
généralement : un `|| true` sur un appel `gh api`/`curl` qui peut
légitimement échouer pour des raisons multiples (contenu, réseau,
permissions, rate-limit) masque la distinction entre « résultat négatif
attendu » et « la vérification elle-même a échoué » —
cf. [[retry-generate-data-detection-impossible]] pour le correctif générique
appliqué à ce risque (outputs dédiés plutôt que capture silencieuse).

*Alternative rejetée* : ne documenter que le correctif de #236 sans
distinguer explicitement le cas #26/#27 (erreur amont, jamais soumise au bug
d'origine) — rejeté pour ne pas laisser croire à une preuve empirique
équivalente sur les trois runs, alors que la nature des trois échecs diffère
(cf. tableau de #235).

<a id="retry-generate-data-detection-impossible"></a>
## Distinguer erreur API et signature absente dans `retry-generate-data.yml` (#237) (2026-08-13)

**Contexte** : [[retry-generate-data-preemption]] (#230) détecte la signature
de préemption runner via deux appels `gh api` (`.../jobs` puis
`.../jobs/<id>/logs`). Sur les runs #26/#27, `gh api .../jobs` a échoué
(erreur transitoire d'API/pagination) sous `set -euo pipefail` sans
fallback : le step entier s'est arrêté immédiatement (`Process completed with
exit code 1`), avant même d'atteindre la boucle de détection — le job
`detect-and-retry` a fini en `failure` sans résumé exploitable. Séparément,
`gh api .../logs` retombait sur `2>/dev/null || true` (#236) : un échec
ponctuel de récupération d'un log individuel produisait un `log=""`, traité
exactement comme une signature absente, donc affiché dans le résumé comme
« probablement un échec applicatif réel » — message trompeur qui a masqué le
bug de listing des jobs pendant trois runs consécutifs (le résumé n'existait
même pas dans ce cas précis, mais le même risque de confusion existe pour
tout échec `.../logs` isolé).

**Décision** : ajoute deux outputs dédiés au step de détection,
`api_error` (échec de `gh api .../jobs`) et `inconclusive` (échec de
`gh api .../jobs/<id>/logs` sur au moins un job candidat), capturés
explicitement (`if ! cmd; then ...; fi`, message `::warning::` avec le détail
de l'erreur) plutôt que laissés remonter via `set -e` ou avalés par
`|| true`. Le step de résumé distingue désormais trois issues au lieu de
deux : retry déclenché (`matched=true`, inchangé), signature non reconnue
sur des logs effectivement lus (`matched=false` et aucune erreur, inchangé),
et détection impossible (`api_error` ou `inconclusive` à `true`, ou
`steps.signature.outcome == 'failure'` en filet de sécurité pour toute
erreur bash non anticipée) — message dédié invitant à une vérification
manuelle du run, explicitement non assimilé à un bug applicatif.

**Note d'implémentation** : contrairement à #228/#230 où l'agent n'avait pas
les permissions GitHub App pour pousser un fichier sous
`.github/workflows/*` (patch livré en commentaire, application manuelle),
le push direct a fonctionné pour ce correctif — la restriction ne semble
plus s'appliquer (ou ne s'appliquait qu'à la création d'un nouveau fichier,
pas à la modification d'un fichier existant). À vérifier si le patch #228
toujours en attente (voir `ROADMAP.md`) peut désormais être appliqué de la
même façon.

*Alternative rejetée* : ne garder qu'un flag booléen unique (« détection
fiable oui/non ») au lieu de deux outputs distincts `api_error`/
`inconclusive` — rejeté pour ne pas perdre, dans les `::warning::` du job,
la distinction entre un échec de listing (affecte toute la détection) et un
échec de log isolé sur un seul job candidat (les autres jobs candidats
restent exploitables), utile pour le diagnostic manuel demandé par le
résumé.

<a id="amendements-range-download-legislature-isolation"></a>
## Téléchargement par plages (Range) + isolation par législature pour les amendements officiels (#241) (2026-08-13)

**Contexte** : #239 (voir [[amendements-retry-blocage-legislature]] ci-dessous)
a corrigé le blocage CI en mémorisant en mémoire process qu'une législature a
définitivement échoué pour le run courant, et en réduisant le timeout de
lecture par tentative (600s → 120s). Correctif suffisant pour le symptôme CI,
mais qui a pour effet secondaire d'abandonner purement et simplement la
collecte de la législature en échec pour tout le run — `amendements[]` est un
champ central du schéma pivot (§4 AGENTS.md), et les législatures 15/16
couvrent une fenêtre (2012-2022) où un profil type de candidat·e 2027 a une
probabilité non négligeable d'avoir siégé (déjà visible sur Guedj, Le Pen).
Deux défauts distincts identifiés : (1) `fetch_amendements_officiels` n'a pas
de `try/except` par législature dans sa boucle sur `AN_AMENDEMENTS_PATH` — la
première à échouer (généralement la légis 16, chroniquement instable)
interrompt l'appel entier, avant même de tenter la légis 15 ; un échec sur la
16 fait donc perdre une légis 17 pourtant récupérée avec succès. (2) le
téléchargement est un flux HTTP continu unique : une coupure `IncompleteRead`
en cours de flux (déjà observée à des points variables, 9 à 40 Mo lus sur des
flux de 300-620 Mo) jette tout le travail déjà fait et force à tout
redémarrer à zéro. Vérifié en direct (13/08 07:29 UTC) que le CDN devant
`data.assemblee-nationale.fr` supporte fonctionnellement les requêtes par
plage (`Range: bytes=...` → HTTP 206 + `Content-Range`), pas seulement
annoncé via l'en-tête.

**Décision** :
1. `_download_amendements_zip` remplace le flux continu par un découpage en
   segments de `AMENDEMENTS_DOWNLOAD_CHUNK_BYTES` (32 Mo) via l'en-tête
   `Range`, écrits séquentiellement dans le fichier local. Chaque segment est
   retenté indépendamment avec le backoff existant de #225
   (`AMENDEMENTS_DOWNLOAD_MAX_ATTEMPTS`/`BACKOFF_SECONDS`, désormais appliqués
   par segment plutôt qu'au fichier entier) : une coupure mi-flux ne force
   plus qu'un nouvel appel pour le seul segment concerné. Taille finale
   validée contre le total déduit de `Content-Range` (pas de requête `HEAD`
   séparée : le premier `GET` par plage la fournit déjà). Repli sur un
   téléchargement classique en un seul segment si le serveur ignore l'en-tête
   Range (réponse 200 au lieu de 206).
2. `fetch_amendements_officiels` encapsule désormais chaque appel à
   `_build_acteur_amendement_index(legislature)` dans un `try/except
   AmendementsIndexError` par itération de la boucle sur
   `AN_AMENDEMENTS_PATH` : les législatures réussies sont conservées même si
   une autre échoue définitivement, et un warning
   `WARNING_PREFIX_AMENDEMENTS_INDISPONIBLES` précisant la législature
   concernée est ajouté par échec (paramètre `warnings` optionnel, propagé
   depuis `build_profile`) au lieu d'un échec binaire global propagé par
   exception.
3. Le cache d'échec inter-candidats de #239
   (`_amendements_failed_legislatures`) est conservé tel quel comme filet de
   sécurité : il ne s'active désormais qu'après épuisement des tentatives
   *par segment*, pour le cas d'une archive réellement indisponible plutôt
   qu'une simple coupure mi-flux.

**Alternative rejetée** : persister le fichier partiel + les offsets déjà
confirmés sur disque pour permettre une reprise *entre processus* (pas
seulement entre tentatives au sein d'un même appel). Écartée pour ce
correctif — gain marginal (l'essentiel du bénéfice vient déjà de la reprise
intra-tentative par segment) face à la complexité ajoutée (état de reprise à
invalider si l'archive distante change entre deux runs) ; à réévaluer
séparément si des coupures en tout début de flux devenaient fréquentes en
pratique.

<a id="amendements-retry-blocage-legislature"></a>
## Le retry avec backoff des amendements (#225) transforme un échec instantané en blocage de plusieurs minutes par candidat (#239) (2026-08-13)

**Contexte** : #185 a diagnostiqué que la collecte des amendements officiels
(`fetch_amendements_officiels`/`_build_acteur_amendement_index`) échouait
silencieusement (`return {}` avalé) sur les trois archives AN Open Data
concernées ; #199 a corrigé cela en levant `AmendementsIndexError` au lieu
d'avaler l'échec. #220/#225 ont ensuite ajouté un retry avec backoff
(`AMENDEMENTS_DOWNLOAD_MAX_ATTEMPTS = 3`, `AMENDEMENTS_DOWNLOAD_BACKOFF_SECONDS
= 5`, timeout de lecture de 600s par tentative) pour absorber les
`IncompleteRead` déjà observés sur ces téléchargements volumineux (voir
[[concurrence-ci-roster]] pour un premier facteur aggravant, le double
téléchargement parallèle extract-an/extract-roster-groupes, déjà mitigé).

**Constat (#239)** : depuis le merge de #225 (2026-08-12T13:02Z), 100 % des
runs de `generate-data.yml` échouent avec la signature « runner shutdown
signal » / exit 143 sur `extract-an` — contre un mélange sain de succès/échecs
auparavant. Chronométrage des logs bruts : sur le dernier succès connu
(07/08, avant #199/#225), les 3 tentatives de téléchargement d'archives
échouaient en moins d'1 ms au total (un seul essai, `IncompleteRead` immédiat,
enchaînement direct au candidat suivant). Depuis #225, le même point du
pipeline (transition candidat 1 → candidat 2, où `fetch_amendements_officiels`
s'exécute) présente un écart silencieux de 3m46s à 8m18s selon les runs — un
job dont le budget total tourne alors autour de 5 à 12 minutes avant que le
runner ne reçoive le signal d'arrêt. Cause : un échec définitif de
téléchargement n'est toujours pas persisté sur le cache disque (seul un index
entièrement construit y est écrit), donc **chaque candidat suivant ayant
besoin de la même législature répète le cycle complet de 3 tentatives ×
600s de timeout depuis zéro**, sans mémoire inter-candidats qu'une
législature est cassée pour ce run.

**Législature spécifiquement en cause** : la 16ᵉ législature
(`amendements_div_legis/Amendements.json.zip`). Vérifié en direct le
13/08 06:53 UTC :
```
$ curl -sI https://data.assemblee-nationale.fr/static/openData/repository/16/loi/amendements_div_legis/Amendements.json.zip
content-length: 363306362
x-cacheable: Not cacheable: too big
```
— le CDN devant `data.assemblee-nationale.fr` refuse de mettre ce fichier en
cache (trop volumineux), donc chaque tentative frappe l'origine sans cache.
`IncompleteRead` observé en échec direct dans les logs de production à trois
reprises (07/08, 12/08 08:45, et implicitement sur tous les runs suivants) —
toujours sur cette même législature 16. La 15ᵉ (`amendements_legis/
Amendements_XV.json.zip`, 618 Mo, également hors cache CDN par sa taille)
n'a pas été observée en échec direct dans les runs examinés : la boucle sur
`AN_AMENDEMENTS_PATH` s'interrompt dès que la législature 16 lève une
exception, avant même de l'atteindre — elle reste donc une candidate
plausible au même défaut, non confirmée faute d'avoir été atteinte. La 17ᵉ
(législature active, dataset rafraîchi quotidiennement, généralement < 300 Mo)
est en revanche régulièrement servie depuis le cache CDN
(`x-cacheable: Matched cache`) et se charge rapidement, y compris en cache-hit
sur le disque local (`.cache/amendements_an/17/`) — elle n'est pas mise en
cause ici.

**Décision (implémentée, PR #240)** : (1) mémoriser en mémoire process (pas
sur disque, `_amendements_failed_legislatures`) qu'une législature a
définitivement échoué pour le run courant, pour que seul le premier candidat
qui la rencontre paie le cycle de retry complet — les suivants lèvent
immédiatement sans nouvel appel réseau ; (2) réduire le budget temps par
tentative (`AMENDEMENTS_DOWNLOAD_READ_TIMEOUT_SECONDS`, 600s → 120s) plutôt
que de le laisser à 3×600s dans le pire cas. Ceci recadre potentiellement une
partie du narratif « préemption infra aléatoire, hors de notre contrôle »
retenu par [[verification-billing-actions]] et [[ci-cd]] : au moins cette
occurrence précise avait une cause déterministe et corrigible côté code.
Correctif suffisant pour le symptôme CI mais qui abandonne toujours la
collecte de la législature en échec pour tout le run — étendu par #241 (voir
[[amendements-range-download-legislature-isolation]] ci-dessus), qui
remplace l'abandon par un téléchargement par plages et une isolation par
législature.

<a id="retry-generate-data-preemption"></a>
## Retry automatique de `generate-data.yml` sur signature de préemption runner (#230) (2026-08-12)

**Contexte** : #217/#221/#228 (voir [[verification-billing-actions]] et
[[ci-cd]] ci-dessous) ont établi qu'un `generate-data.yml` tué par un
`shutdown signal` runner GitHub (préemption infra transitoire, hors contrôle
du workflow) reste en échec jusqu'à un re-déclenchement manuel — vécu deux
fois de suite sur les runs #24/#25. #230 demande une récupération
automatique de ce mode de défaillance précis, sans masquer un vrai échec
applicatif (#218 : bug de script shell du Quality Gate, qu'un retry
généralisé aurait fait disparaître silencieusement au lieu de le signaler).

**Décision** : un second workflow, déclenché sur `workflow_run` (`types:
[completed]`) ciblant `Génération des données`, qui :
1. **Plafonne à 1 tentative** en vérifiant `github.event.workflow_run
   .triggering_actor.login` — si le run échoué a lui-même été déclenché par
   `github-actions[bot]` (identité utilisée par `gh workflow run` via
   `GITHUB_TOKEN`), c'est déjà une relance automatique : pas de nouvelle
   tentative. Choisi plutôt qu'un compteur externe (variable de dépôt,
   artifact dédié) car il ne nécessite aucun état persistant ni permission
   supplémentaire — l'identité de l'acteur déclencheur suffit à distinguer un
   run humain d'un run auto-relancé.
2. **Détecte la signature précise** via l'API Actions (`gh api .../actions/
   runs/<id>/jobs` puis `.../jobs/<job_id>/logs`) : au moins un job en échec
   dont les steps `if: always()`/`if: failure()` (`Upload artifact *`,
   `Diagnostic — job en échec`) sont `skipped` **et** dont les logs
   contiennent `shutdown signal` / `The operation was canceled.`. Un échec
   applicatif (exception Python, Quality Gate en échec réel) laisse toujours
   ces steps s'exécuter normalement — la combinaison des deux signaux évite
   les faux positifs qu'un simple grep de log seul ne suffirait pas à écarter.
3. **Reconstruit les inputs du run échoué en best-effort** : l'API Actions
   n'expose pas les inputs d'un `workflow_dispatch` passé (pas de champ
   dédié sur l'objet run). `fresh_run` est lu de façon fiable via la
   conclusion du step conditionnel `Nettoyage complet (fresh_run
   uniquement)` (skipped/success reflète directement `inputs.fresh_run`) ;
   `workers`/`extract_interventions`/`max_pages` sont extraits du texte
   résolu du step `Extraction AN` (ces valeurs sont substituées directement
   par `${{ inputs.* }}` dans le script, donc visibles telles quelles dans le
   log) ; `threshold` est lu depuis le rapport stdout de
   `check_quality_gate.py` (`Seuil : N`) ; `roster_extraction_limit` depuis
   le rapport stdout de `generate_all_profiles.py`. En cas d'échec
   d'extraction d'une valeur, repli sur le défaut déclaré de
   `generate-data.yml` pour cet input — dégradation documentée, pas un
   blocage du retry.
4. **Re-déclenche** `generate-data.yml` via `gh workflow run` avec les
   inputs reconstruits, sur la même branche que le run échoué
   (`github.event.workflow_run.head_branch`).
5. **Notifie explicitement** via `$GITHUB_STEP_SUMMARY` (même pattern que
   les steps de diagnostic existants de `generate-data.yml`) : retry
   déclenché, plafond déjà atteint, ou signature non reconnue — dans les
   trois cas, une trace visible plutôt qu'un re-run silencieux ou une
   absence de retry inexpliquée.

**Note d'implémentation** : comme pour #228, l'agent qui a traité #230 n'a
pas pu pousser directement le nouveau fichier `.github/workflows/retry-
generate-data.yml` (créé manuellement à partir du YAML fourni en commentaire
de résolution de #230). Restriction d'outillage CI, pas une décision produit
— nuancée depuis par #237 : seule la **création** d'un nouveau fichier sous
`.github/workflows/*` s'est heurtée à la restriction, la **modification**
d'un fichier existant a ensuite fonctionné sans intervention manuelle (détail
et reproduction dans [[retry-generate-data-detection-impossible]]).

*Alternative rejetée* : retry généralisé sur tout `conclusion: failure`
sans vérification de signature — rejeté explicitement par #230 lui-même
(masquerait une régression applicative réelle comme #218 au lieu de la
signaler). *Alternative rejetée* : plafonner le retry via un nouvel input
`workflow_dispatch` dédié sur `generate-data.yml` (ex. `auto_retry_count`)
plutôt que l'identité de l'acteur déclencheur — rejeté car cela nécessiterait
de modifier `generate-data.yml`, hors de portée de cet agent pour la même
raison que le nouveau fichier lui-même (restriction de permissions
`.github/workflows/*`), et l'identité de l'acteur atteint le même résultat
sans ce besoin.

<a id="ci-cd"></a>
## Angle mort du `runner shutdown signal` sur `if: always()` et la sauvegarde de cache (#228) (2026-08-12)

**Contexte** : #219 a ajouté `if: always()` sur les steps `Upload artifact *`
de `generate-data.yml` pour préserver la progression partielle (profils déjà
écrits sur disque) en cas d'annulation/échec de job. Le run #25
(récidive de #217/#221, https://github.com/stephieED/Empreinte-politique-src/actions/runs/31605692943)
montre empiriquement que ce mécanisme a un angle mort : quand le runner
hébergé GitHub reçoit un `shutdown signal` d'infrastructure (cause retenue
pour #217, voir [[verification-billing-actions]] — préemption transitoire,
indépendante de la facturation), **aucun step suivant ne s'exécute, `if:
always()` inclus**. Dans ce run, `Upload artifact AN`, le `Post Run
actions/cache@v4` (sauvegarde implicite du cache `.cache` en fin de job) et
les deux steps de diagnostic `if: cancelled()`/`if: failure()` de #223 sont
tous `skipped`, alors que le job est en `failure`. Toute la progression du
job (profils + cache) est donc perdue dans ce mode précis, contrairement à ce
que #219 visait à garantir : GitHub Actions tue le process runner lui-même
avant que la couche `if:`/post-step ne puisse s'évaluer, ce qui est différent
d'une annulation ou d'un échec applicatif classique que `always()` couvre
correctement.

**Pistes évaluées** (#228) :
1. Réduire la granularité des jobs d'extraction coûteux (`extract-an`,
   `extract-roster-groupes`) en sous-lots (matrix strategy par tranche de
   candidats/roster), pour borner la perte à un lot plutôt qu'à tout le job.
2. Invoquer `actions/cache/save@v4` à des points de contrôle intermédiaires
   plutôt qu'en post-step implicite de fin de job.
3. Documenter explicitement le blind spot dans `generate-data.yml` (commentaire),
   pour éviter une fausse impression de résilience lors de futures modifications.

**Décision retenue : option 3 seule pour l'instant** (commentaire explicite à
ajouter en tête de `generate-data.yml`, à côté du bloc de commentaires
existant sur les timeouts) — patch fourni en commentaire de #228 pour
application manuelle (voir note d'implémentation ci-dessous). Réduit le risque
de régression silencieuse (un futur changement qui s'appuierait à tort sur
`always()` comme garantie totale) à coût nul, sans toucher au comportement du
workflow.

**Options 1 et 2 différées, pas rejetées** : les deux réduiraient réellement
le blast radius, mais seule l'option 1 (sharding) couvre la perte des *deux*
formes de progression (artifacts de profils **et** cache) — l'option 2 seule
ne couvre que la sauvegarde du cache, pas l'upload d'artifact, tant que
l'extraction reste un unique step long ; elle ne devient réellement utile que
combinée à un découpage en plusieurs steps/lots, c'est-à-dire à l'option 1.
Le sharding matrix a un coût de conception non trivial (clés de cache par lot,
fusion de N artifacts au lieu d'un seul dans `merge-and-pivot`, interaction
avec la réduction du pic de jobs concurrents de #222,
[[concurrence-ci-roster]]) et une urgence limitée tant que
`roster_extraction_limit` reste à 20 (rollout restreint, #192) — l'exposition
réelle grandira surtout au passage à un run à pleine échelle (~750 membres),
pas encore planifié (voir [[seuil-couverture-groupe]]). À concevoir avec cette
recalibration plutôt qu'en réaction isolée à #228.

**Note d'implémentation** : l'agent qui a traité #228 n'a pas pu pousser
directement le commentaire YAML de l'option 3 sous `.github/workflows/*`
(appliqué manuellement à partir du patch fourni en commentaire de résolution
de #228). Restriction d'outillage CI, pas une décision produit — nuancée
depuis par #237 : seule la **création** d'un nouveau fichier sous
`.github/workflows/*` s'est heurtée à la restriction, la **modification**
d'un fichier existant a ensuite fonctionné sans intervention manuelle (détail
et reproduction dans [[retry-generate-data-detection-impossible]]).

<a id="verification-billing-actions"></a>
## Vérification quota/limite de dépense GitHub Actions (#221) : hypothèse infirmée (2026-08-12)

**Contexte** : #221, sous-issue du diagnostic #217, vérifiait si l'annulation
des jobs `extract-an`/`extract-roster-groupes` (run #24, récidive sur le run
#25) était due à un plafond de minutes Actions ou à une limite de dépense
atteinte en cours de run sur ce dépôt **privé**, dans un contexte de volume
inhabituellement élevé de runs `Claude Code`/`Claude Code Review` concurrents
ce même jour. Vérification hors périmètre agent (accès au tableau de bord de
facturation requis) — réalisée par @stephieED via Settings → Billing and
plans, capture d'écran "Usage breakdown" et export CSV du cycle en cours
fournis en commentaire.

**Constat (cycle de facturation d'août 2026)** :
- Minutes Actions incluses : 1 511 / 2 000 min utilisées (75 %) — sous quota.
- Stockage Actions inclus : 0,2 / 0,5 GB utilisés (40 %) — sous quota.
- "Usage breakdown" : Actions Linux (1 511 min, $9.07 brut) + Actions storage
  (132,12 GB-h, $0.04 brut) → **montant facturé $0**, entièrement absorbé par
  le quota inclus du plan.
- L'export CSV journalier (`225 min` le 12/08, `discount=0` par ligne) est
  cohérent avec ce total : la déduction du quota inclus n'apparaît qu'au
  niveau agrégé du cycle de facturation, pas ligne à ligne — l'absence de
  remise par jour n'est donc pas un signal de dépassement.

**Conclusion : hypothèse infirmée.** Ni le quota de minutes (marge de 489 min
restante) ni le stockage ne sont dépassés, et rien n'est facturé ce mois-ci
sur ce dépôt. Une limite de dépense à $0 combinée à un quota épuisé
bloquerait le *démarrage* du job (erreur explicite avant exécution), pas un
arrêt en cours de run — or le run #25 montre `The runner has received a
shutdown signal`, un signal d'infrastructure au niveau du runner hébergé,
sans lien avec la facturation. Cause la plus probable retenue pour #217 :
incident/préemption transitoire côté runners hébergés GitHub, indépendante du
statut public/privé du dépôt — passer le dépôt en public n'aurait pas
empêché ce type d'arrêt et n'est donc pas recommandé pour ce problème précis.

*Non vérifié précisément* : la valeur exacte configurée sur *Settings →
Billing and plans → Spending limits* n'a pas été communiquée telle quelle —
seul le résultat ($0 facturé, quota non atteint) est confirmé via le "Usage
breakdown" et le CSV. Suffisant pour trancher #221 (le quota/la dépense n'est
pas la cause de l'annulation), mais à compléter en commentaire si une valeur
précise de configuration est un jour nécessaire.

<a id="concurrence-ci-roster"></a>
## Réduction du pic de jobs concurrents `generate-data.yml` : séquencement + cache AN partagé (2026-08-12)

**Contexte** : #222 (sous-issue du diagnostic #217/#221) — `extract-roster-groupes`
(#192) est le 5ᵉ job du graphe, lancé en parallèle des 4 jobs d'extraction
historiques. `extract-an` et `extract-roster-groupes` téléchargent chacun,
indépendamment, les mêmes dumps AN Open Data immuables dès qu'un membre de
roster appartient à la chambre `deputes` (5 des 7 groupes configurés) — cas
systématique en pratique. Run #24 : `Amendements.json.zip` (283-618 Mo)
téléchargé deux fois en parallèle, doublant la bande passante et l'exposition
aux `IncompleteRead` déjà diagnostiqués (#185/#220), en mitigation de
l'hypothèse d'un plafond de dépense Actions atteint (#221).

**Décision** : faire pointer `extract-roster-groupes` sur la même clé de
cache `.cache` qu'`extract-an` (`public-data-cache-an-*` au lieu de
`public-data-cache-roster-*`) et le séquencer après les 4 jobs existants
(`needs: [extract-an, extract-senat, extract-ue-officiel, extract-parltrack]`)
— option 1 du diagnostic #222. Réduit le pic de jobs simultanés de 5 à 4 et
garantit, via le séquencement, que le cache AN partagé est déjà chaud
(écrit par `extract-an`) au moment de sa restauration par
`extract-roster-groupes` : plus de course au premier run de chaque semaine
ISO, plus de double téléchargement. Coût : temps mur total plus long
(`extract-roster-groupes` démarre après les 4 autres au lieu d'en parallèle).

*Alternatives rejetées* : réduire davantage `roster_extraction_limit`
(option 2) — n'aurait qu'atténué le doublon de téléchargement AN Open Data
sans l'éliminer (le doublon existe dès qu'un seul membre AN est traité,
indépendamment du volume) ; gater `extract-roster-groupes` derrière un input
explicite `run_roster_extraction` (option 3) — retardé au-delà du correctif
obligatoire de #222, car cela retire de la capacité d'extraction plutôt que
de réduire la concurrence, contrairement à l'objectif de l'issue ("sans
perdre en capacité"). Les deux restent des options possibles si #221
confirme un plafond de dépense atteint et qu'une réduction supplémentaire du
pic s'avère nécessaire.

<a id="seuil-couverture-groupe"></a>
## Seuil de couverture de groupe (`--groupe-min-members`) : conservé faute de chiffres réels à pleine échelle (2026-08-12)

**Contexte** : #193 demande de recalibrer `--groupe-min-members` (`check_quality_gate.py`,
défaut 1, cf. `generate-data.yml:413`) maintenant que la couverture roster est censée
approcher 100 % (post #188/#190/#191), ce seuil absolu ayant été pensé à l'origine
pour une couverture quasi nulle. L'issue #193 demande explicitement de trancher
« en fonction des résultats réels [...] (ne pas fixer de nouveau seuil dans le vide
avant d'avoir des chiffres réels) ».

**Constat** : au moment de cette recalibration, aucun run à pleine échelle
(~750 membres roster, #188) n'a encore été exécuté en CI. Les fichiers
`pivot_data/groupes/*.json` présents dans le dépôt proviennent de runs à échelle
réduite (`--limit`/`--sample`, voir [[limit-sample]]) et affichent des taux de
couverture réels très faibles et hétérogènes (ex. `AN:REN` 1/193 ≈ 0,5 %,
`AN:SOC` 1/31 ≈ 3,2 %, `AN:LFI` 0/76 = 0 %) — non représentatifs de la couverture
quasi complète visée. Fixer un seuil relatif strict dès maintenant reviendrait à
choisir un nombre dans le vide, exactement ce que #193 demande d'éviter.

**Décision** : conserver `--groupe-min-members 1` comme seuil par défaut (soft
fail uniquement, jamais bloquant), et ajouter en parallèle un seuil relatif
optionnel `--groupe-min-coverage-pct` (défaut `0`, désactivé) dans `_report_groupes`
(`check_quality_gate.py`), pour permettre d'activer un contrôle basé sur le taux de
couverture (`profils_disponibles / roster_total`) dès que des chiffres réels à
pleine échelle seront disponibles (issues de suivi #188/#190/#191), sans nouveau
changement de signature. `audit_groupe_dataset.py` expose désormais
`taux_couverture_pct` dans `coherence.ecart_couverture_roster` (voir
[[provenance-pivot]] pour le contexte de la recalibration roster), pour suivre
cette progression dans le temps avant de choisir une valeur définitive. Le
fichier `.github/workflows/generate-data.yml` (permissions de modification hors
périmètre agent) n'est pas mis à jour par ce changement : la valeur par défaut de
`--groupe-min-members` y reste `1`, cohérente avec le choix ci-dessus.

*Alternative rejetée* : remplacer directement `--groupe-min-members` par un seuil
relatif avec une valeur par défaut choisie a priori (ex. 80 %) — rejeté car aucune
donnée réelle à pleine échelle ne permet de justifier ce chiffre à ce stade, et un
seuil trop haut ferait immédiatement échouer le gate qualité (en soft fail) sur les
runs actuels à échelle réduite, sans valeur informative.

<a id="senat-periode-debut"></a>
## Groupes Sénat : ne pas renseigner `senat_periode_debut` dans `groupes_reels.json` (2026-08-12)

**Contexte** : #191 durcit `group_profile.py`/`generate_group_profiles.py` pour une
couverture de profils quasi complète (post #190). À couverture quasi complète, les
2 groupes Sénat de `groupes_reels.json` (`Senat:LR`, `Senat:SER`) exposent un effet
auparavant masqué par la faible couverture : `_member_matches_legislature`
(`group_roster.py:73-84`) ne filtre par date que si `senat_periode_debut` est fourni,
et ces 2 entrées ne le renseignent pas — le roster Sénat mélange donc sénateurs·rices
en fonction et anciens·nes, ce qui biaise `cohesion_votes`/`effectif` (calculés sur des
membres qui ne siègent parfois plus).

**Décision** : ne PAS renseigner `senat_periode_debut` pour autant. La cause racine
n'est pas l'absence de date de filtrage mais la donnée source elle-même :
`archive.nossenateurs.fr` (site arrêté par Regards Citoyens) n'expose pas de champ
`mandat_fin` exploitable pour la majorité des entrées archivées — déjà documenté dans
l'avertissement `fraicheur_donnees` de `generate_groupe_profile_from_roster`
(`group_profile.py`). Or `_member_matches_legislature` filtre précisément sur
`mandat_fin` : sans cette donnée fiable, fixer une date arbitraire ne exclurait pas
significativement plus d'anciens sénateurs (la plupart afficheraient encore
`mandat_fin: null`, donc `actif` par défaut) — cela donnerait une fausse impression de
correction sans effet mesurable, pire que de documenter la limite explicitement. Un
second avertissement `couverture_roster_senat` a été ajouté dans
`generate_groupe_profile_from_roster` pour rendre ce comportement visible directement
dans chaque profil de groupe Sénat généré (`meta.warnings`), plutôt que de le laisser
à découvrir uniquement dans l'audit qualité (`audit_groupe_dataset.py`) ou le quality
gate CI.

*Alternative rejetée* : renseigner une date de référence (ex. début de législature en
cours) dans `senat_periode_debut` pour les 2 groupes — rejeté car non fiable tant que
`mandat_fin` n'est pas exploitable côté source (voir ci-dessus) ; réévaluer si
`group_roster.py` change de source de données pour le Sénat.

<a id="limit-sample"></a>
## Déploiement progressif de l'extraction roster-driven : --limit vs --sample (2026-08-12)

**Contexte** : #190 branche la liste roster-driven (#188) dans
`generate_all_profiles.py` (`--candidats raw_data/roster_candidats.json`).
Avant d'ouvrir l'extraction aux ~750 membres complets, une sous-issue CI
dédiée a besoin de pouvoir tester à petite échelle sans consommer tout le
budget CI.

**Décision** : ajouter les deux options plutôt que de trancher entre elles —
`--limit N` (les N premiers candidats, ordre déterministe du fichier source)
et `--sample N` (N candidats tirés aléatoirement sans remise), mutuellement
exclusives (`argparse` mutually exclusive group). `--limit` sert les tests
reproductibles (CI, `--resume` stable d'un run à l'autre) ; `--sample` sert la
vérification ponctuelle de la diversité de couverture (chambres/groupes
différents) sans dépendre de l'ordre du fichier. Aucune graine (`seed`) fixée
pour `--sample` : chaque run tire un échantillon différent, ce qui est
acceptable pour un usage de spot-check et documenté dans l'aide CLI.

*Alternative rejetée* : n'implémenter que l'un des deux (comme suggéré par
l'issue, "à trancher en implémentation") — rejeté car les deux usages
(reproductible pour la CI, aléatoire pour la diversité) sont distincts et peu
coûteux à supporter simultanément.

## `--limit` + `--skip-existing` sur `extract-roster-groupes` : sélection progressive + rafraîchissement (2026-08-12)

**Contexte** : #224 diagnostique que la combinaison `--skip-existing` +
`--limit N` fixe (introduite par #192, voir section précédente) empêche à la
fois la conquête progressive de couverture du roster et le rafraîchissement
des profils déjà collectés — `--limit` resélectionne toujours les N premiers
candidats du fichier source (ordre déterministe), qui existent tous dès le
run 2, et `--skip-existing` les saute alors systématiquement : le job ne
traite plus jamais personne sans intervention manuelle, et les profils
couverts ne sont plus jamais rafraîchis (votes/amendements/interventions
figés à leur état de première extraction).

**Décision** : dans `generate_all_profiles.main()`, quand `--limit` et
`--skip-existing` sont combinés, remplacer la troncature naïve
(`_select_candidats`) par `_select_candidats_couverture` : partitionner les
candidats en "non couverts" (pas de `pivot_data/profiles/<slug>.pivot.json`)
et "couverts" avant application de `--limit`, puis allouer le budget en
priorité aux non-couverts (frontière de conquête, ordre du fichier source) et,
s'il en reste, aux couverts périmés — fraîcheur réutilisée telle quelle depuis
`audit_pivot_dataset.compute_profils_perimes` (`--staleness-days`, défaut 30,
même sémantique). Les slugs sélectionnés pour rafraîchissement sont exemptés
du court-circuit `--skip-existing` dans `process_candidat` (nouveau paramètre
`refresh_slugs`) : ils repassent par le fetch + merge additif normal plutôt
que d'être sautés. `--limit` seul ou `--sample` gardent le comportement
historique (troncature simple), inchangé.

Contrainte de mise en œuvre : `.github/workflows/generate-data.yml` n'est pas
modifiable par cet agent (permissions GitHub App) — la correction devait donc
être transparente pour l'invocation CLI existante du job `extract-roster-groupes`
(`--limit ... --skip-existing`, sans nouveau flag requis), ce qui a aussi
tranché en faveur d'un comportement déclenché par la combinaison de flags
plutôt que par un nouveau flag dédié.

*Alternative rejetée* : trier les profils périmés du plus périmé au moins
périmé pour l'allocation du budget restant (suggéré par l'issue). Rejeté pour
rester simple — l'ordre utilisé est celui renvoyé par
`compute_profils_perimes` (tri alphabétique par `id`), sans tri additionnel
par degré de péremption ; à revisiter si un déséquilibre de rafraîchissement
est observé en usage réel.

*Hors périmètre (explicite dans #224)* : pas de changement du budget/timeout
CI (`generate-data.yml`) ni du seuil de péremption par défaut
(`staleness_days=30`, déjà utilisé par `audit_pivot_dataset.py`) — réutilisé
tel quel. Impact réel sur le budget CI (coût par run d'un mix
conquête+rafraîchissement) à évaluer une fois #222 en place, comme demandé
par l'issue.

<a id="provenance-pivot"></a>
## Provenance des profils pivot : candidat_declare vs roster_groupe (2026-08-10)

**Contexte** : #188 introduit `generate_roster_candidats.py`, qui produit une
liste de "candidats" alternative à `raw_data/candidats.json`, pilotée par la
composition réelle des groupes parlementaires (`statut: "roster_groupe"`) plutôt
que par la liste éditoriale des candidats déclarés à la présidentielle. Une fois
les deux sources utilisées pour générer des pivots (`generate_all_profiles.py`),
un même `slug` peut être régénéré par les deux : un membre de groupe extrait via
le roster peut aussi être un candidat déclaré déjà enrichi manuellement (`parti`
notamment, renseigné depuis `candidats.json`).

**Décision** : ajouter `meta.provenance` (`"candidat_declare"` | `"roster_groupe"`,
voir `schema_pivot.KNOWN_PROVENANCES`) au schéma pivot, propagé par
`normalize_nosdeputes()`/`normalize_europarl()` et renseigné par
`generate_all_profiles.py` selon `candidat["statut"]`. Règle de fusion dans
`merge_profile.merge_pivot_profile()` : un profil déjà `"candidat_declare"` n'est
jamais rétrogradé vers `"roster_groupe"` par une régénération roster-driven du
même slug — la valeur éditoriale de vérité (`candidats.json`) prime toujours sur
l'extraction automatique par roster. Les autres champs éditoriaux (`parti`, etc.)
sont déjà protégés par la stratégie `_prefer_non_empty` existante, car
`generate_roster_candidats.py` ne renseigne jamais ces champs (valeur `None`).
Rétro-compatibilité : un pivot existant sans `meta.provenance` (généré avant
cette décision) reste valide et est traité comme `"candidat_declare"` par défaut
par `validate_profil()` et la politique de fusion — pas de migration nécessaire.

*Alternative rejetée* : marquer la provenance au niveau du fichier `candidats.json`
uniquement (sans persister l'info dans le pivot) — rejeté car le pivot est la
seule couche lue par les agrégations groupes/partis et par `web/` ; sans champ
dédié dans le pivot lui-même, aucune politique de fusion protectrice n'aurait été
possible lors d'une régénération croisée des deux sources.

<a id="web-v3-ui"></a>
## Interfacer web/UI_finale (CONTRECHAMP) aux données réelles (2026-08-08)

**Contexte** : `web/UI_finale` (React/Vite) était câblé sur des données mock
(`candidates.json`/`groups.json`/`mockGenerator.js`) bien plus riches en volume
que les données réelles disponibles : `pivot_data/` ne couvrait alors que 8
candidats (présidentiables 2027 aussi élus, ceux ayant un `slug` dans
`raw_data/candidats.json`) et 7 groupes parlementaires réels (5 AN + 2 Sénat).

**Mise à jour (#187, roster-driven)** : ce chiffre de 8 candidats était une
limite de l'extraction éditoriale-uniquement, résolue par l'extraction
roster-driven (`generate_roster_candidats.py`, #188/#190/#191, voir
[[provenance-pivot]]) qui couvre tou·te·s les membres réels des groupes
configurés, pas seulement les candidats déclarés. Le nombre de 7 groupes reste
en revanche une limite assumée du périmètre : `pivot_data/groupes/` ne couvre
que les groupes listés dans `raw_data/groupes_reels.json`, pas l'ensemble des
groupes parlementaires existants (voir "Coverage limits" dans `README.md`).
La couverture individuelle réelle au sein de ces 7 groupes dépend d'un run à
pleine échelle qui n'avait pas encore eu lieu en CI au moment de cette mise à
jour — chiffres et suivi dans [[seuil-couverture-groupe]].

**Décision** : remplacer intégralement le mock. `web/UI_finale/scripts/sync-data.mjs`
copie `pivot_data/profiles/`, `pivot_data/groupes/` et `raw_data/candidats.json`
vers `public/data/` (généré, gitignoré) et produit `public/data/manifest.json`
(roster candidats/groupes + rattachement candidat→groupe réel via
`membres[].membre_id`), car Vite ne sert pas de fichiers hors du dossier
projet. `src/data/pivotAdapter.js` porte vers React la logique déjà validée
dans `web/old/v3/js` (ancienneté de mandat, dédoublonnage des responsabilités,
classification majorité/opposition/gouvernement par `position_dans_hemicycle`
+ `source_url`, classification thématique par mots-clés) plutôt que de la
dupliquer en Python : cette logique est un pur calcul d'affichage, sans
publication de nouvelle donnée, donc pas de raison de la sortir du pipeline
web. *Alternative rejetée* : script Python générant des JSON pré-calculés —
aurait dupliqué une logique déjà écrite et éprouvée en JS pour v3.

**Périmètre restreint assumé** : `web/UI_finale` affiche désormais uniquement
Candidats + Groupes parlementaires réels (alignement sur l'ancien `web/old/v3`,
pas d'onglet Partis). Plusieurs groupes réels ont 0 ou 1 profil individuel
disponible localement (`profils_disponibles` très inférieur à `roster_total`)
: les composants affichent un état "aucune donnée" explicite plutôt qu'un
graphique à 0 silencieux, conformément à la règle 5 (une donnée manquante
n'est jamais un 0 par défaut).

<a id="syceron"></a>
## Syceron : remplacement du scraping NosDéputés pour les débats en séance (2026-08-07)

**Contexte** : l'enrichissement des `interventions[]` avec le texte intégral des prises de
parole reposait jusqu'ici sur les métadonnées extraites via l'API NosDéputés (titre,
date, type) sans le texte complet des débats.

**Décision** : intégrer les comptes rendus de séance Syceron (AN Open Data,
`/vp/syceronbrut/syseron.xml.zip`) comme source primaire pour le texte intégral des
interventions en séance (L15, L16, L17).

**Pourquoi Syceron plutôt que le scraping HTML NosDéputés** : le scraping HTML de
NosDéputés/NosDeputes.fr pour les textes de débat est fragile (structure HTML non
contractuelle, susceptible de changer sans préavis, pas de version JSON officielle pour
le texte brut des interventions). Les données Syceron sont publiées directement par
l'Assemblée nationale sur son portail open data officiel sous licence Open (Etalab),
dans un format XML structuré et stable. *Alternative rejetée* : continuer avec le
scraping NosDéputés seul — non retenu car la source officielle AN est disponible,
plus fiable, et homogène avec le reste du pipeline.

**Pourquoi des modules dédiés (`syceron_debates.py`, `parse_syceron.py`) plutôt qu'une
intégration directe dans `candidate_profile.py`** : les ZIP Syceron sont des dumps
volumineux (55–149 MB) contenant des centaines de fichiers XML par législature. Le
téléchargement/cache et le parsing XML représentent des responsabilités distinctes qui
alourdiraient `candidate_profile.py` sans apport pour sa lisibilité. La séparation permet
aussi de tester le parseur de façon indépendante et de réutiliser `syceron_debates.py`
dans d'autres jobs (par exemple analyse thématique groupes) sans dépendre du pipeline
profil. `candidate_profile.py` appelle ces modules via `_build_acteur_interventions_syceron_index`
et `fetch_interventions_syceron`, ce qui reste cohérent avec le pattern déjà établi pour
les autres jeux AN (scrutins, amendements, dossiers).

Voir [`docs/an_opendata.md`](./an_opendata.md) (section Syceron) pour la
cartographie des URLs, la structure XML utile et la stratégie de téléchargement.

<a id="hors-perimetre"></a>
## Deferred / out-of-scope investigations

Findings from explored sources that led to a "not now" verdict, with full
rationale — kept here rather than in `ROADMAP.md` so the reasoning survives
even if the backlog entry itself is reworded or dropped.

### Senate votes, amendments, sponsored texts

Explored `data.senat.fr`'s open data catalog (2026). No structured roll-call
vote dataset exists at all (unlike AN's `Scrutins.json.zip`). `ameli.zip`
(amendments) is a raw 717 MB SQL dump (`ameli.sql`), not per-senator
JSON/CSV — impractical to download/parse on every run. `dossiers-legislatifs.csv`
has no author/sponsor field, so per-senator sponsored texts would require
scraping individual `dossier-legislatif` HTML pages (fragile, out of pattern
with the rest of this project's official-JSON-based sources). A full Senate
pipeline equivalent to the AN one is not currently feasible without a fragile
HTML-scraping approach. No official structured vote source has been found
as an alternative either.

### European Parliament — textes_portés / amendements via the official API

Explored the EP Open Data Portal API v2 (2026). `/plenary-documents`
(reports) and `/documents?work_type=AMENDMENT_LIST` exist, but neither
exposes a structured author/rapporteur field referencing a `person/<id>`
MEP URI — the rapporteur name only appears as free text inside multilingual
titles. No server-side filter works (`creator=person/<id>` and text-search
params are all silently ignored). The `/plenary-documents` corpus is
~10-15k documents with no per-item title in the list response, so
identifying a given MEP's reports would require fetching every document's
detail individually — at the API's 500 req/5min rate limit, a full scan
takes 1h30+ per regeneration run. Amendment-list documents are further
compiled per-report batches, not per-amendment/per-signatory records, so
even textual matching would only attribute a whole batch to the report's
rapporteur, not individual amendments to their actual authors.

**Status: superseded.** A follow-up investigation into third-party
aggregators (Parltrack, HowTheyVote) found a viable path — see
`docs/extract-ue.md` for the comparative
feasibility verdict and implementation brief. This entry is kept for
context on why the official-API-only approach was abandoned.

### Ministerial function — precise portfolio title

`mandats[].categorie == "fonction_gouvernementale"` is sourced from the AN
`acteurs_historique` bulk dataset (`organe.codeType == "GOUVERNEMENT"`),
which only identifies *which* government (e.g. "BORNE", "CASTEX") an
elected official belonged to and the dates — not the specific portfolio
title (e.g. "Ministre de l'Intérieur"). No open-data source for the precise
portfolio has been identified yet.

### Extra-parliamentary bodies

Corresponds to the `extra_parlementaire` category already planned in
`schema_pivot.KNOWN_CATEGORIES`, but matching to a profile can only be done
by free-text name (no `acteurRef`) — a real risk of false positives on
homonyms. Not implemented without a careful matching strategy (e.g. name +
group, or accepting partial coverage rather than a bad match).

### Agenda / committee meetings dataset

`.../vp/reunions/Agenda.json.zip` describes committee/plenary meetings
(agenda, bills examined). Organized by body/meeting, not by individual —
more useful for precisely dating when a bill was examined in committee than
for enriching an individual profile directly. No expressed need for this
today.

### Mayors

No dedicated collection module or source identified yet.