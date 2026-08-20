<a id="chambre-par-mandat-electif"></a>
## La chambre est un fait du mandat, pas du profil : `mandats[].chambre` estampillée à la collecte (#492) (2026-08-20)

Sous-issue C de l'épic **#486**, après #488 (sous-issue B). Ne touche pas à
`chambre` au niveau profil (sous-issue D, `needs-human`), ne corrige pas le
profil de Mélenchon (#484), n'ajoute aucun mandat à aucun profil.

### Le défaut

Les `mandat_electif` ne portaient **aucun marqueur de chambre**. Les libellés
publiés sont « Mandat parlementaire (Les Républicains) », « Mandat parlementaire
(Renaissance) » — identiques qu'on siège au Palais-Bourbon ou au Luxembourg.
Seuls les mandats européens étaient explicites (« Mandat de député européen »,
14 occurrences). L'information n'était pas seulement non affichée : elle n'était
pas portée, et l'UI (sous-issue F) n'aurait eu aucun moyen de distinguer les deux
expériences parlementaires d'un candidat.

### La méthode suggérée par l'issue ne tient pas, et la mesure le dit

#492 proposait de dériver la chambre du `source_url` — « les fiches AN portent
`assemblee-nationale.fr`, les sénatoriales `archive.nossenateurs.fr` » — en
signalant que le champ était « à `None` sur plusieurs mandats ». Mesuré sur
`f5a828b`, sur les **228 `mandat_electif` des 209 profils publiés** :

| `source_url` sur un `mandat_electif` | Mandats |
| --- | ---: |
| absent | **214** |
| présent, `www.europarl.europa.eu` | **14** |
| présent, `assemblee-nationale.fr` | **0** |
| présent, `archive.nossenateurs.fr` | **0** |

Le champ n'est pas « souvent vide » : il est **systématiquement** vide sur les
mandats AN et Sénat, et systématiquement rempli sur les seuls mandats européens.
`candidate_profile._extract_mandats` ne l'a jamais renseigné sur un mandat
électif. La méthode proposée aurait donc pu établir exactement la distinction
qu'on n'a pas besoin d'établir (le PE se lit déjà dans le libellé) et aucune de
celle qu'on cherche. Pour situer, la couverture de `source_url` par catégorie sur
les 16 853 mandats du corpus : `groupe_politique` 398/398 (le champ y est
obligatoire, règle 6), `fonction_gouvernementale` 107/319, `autre` 88/174,
`commission` 75/5 285, `mandat_electif` 14/228, toutes les autres 0.

### Ce qui a été fait : estampiller à la collecte

`candidate_profile.build_profile(chambre, slug)` **sait** de quel jeu de données
vient le mandat qu'il fabrique — c'est son paramètre. La chambre est donc écrite
sur le mandat au moment où il est construit, dans le vocabulaire brut
(`deputes` / `senateurs`), et traduite en nomenclature pivot (`AN` / `Senat` /
`PE`) par `normalize_nosdeputes` / `normalize_europarl`.

Sémantique exacte du champ, et elle compte : **la chambre dont le jeu de données
a rendu ce mandat**. C'est un fait de collecte traçable (§2.2), pas une
qualification juridique déduite. Le profil de Retailleau reste un contre-exemple
utile : son unique `mandat_electif` débute le 2004-09-26 — la date du
renouvellement sénatorial — et reste ouvert, tout en venant de
`www.nosdeputes.fr`. #492 ne tranche pas ce cas ; elle le rend **visible sur le
mandat** au lieu de le laisser au seul niveau profil.

### La chambre est lue sur le mandat, jamais sur le profil

Le raccourci tentant — reprendre `raw_profile["chambre"]` pour tous les mandats
du profil — est faux, et le corpus le prouve. La fusion additive
(`merge_profile.merge_lists_by_key`) accumule dans un même profil des mandats
collectés lors de runs différents, donc sous des chambres potentiellement
différentes. Mesuré sur `f5a828b` : le profil brut de `jean-luc-melenchon` porte
`chambre: "senateurs"` et **trois** `mandat_electif`, dont deux manifestement AN
(2017-2022, groupe LFI). Reprendre la chambre du profil aurait estampillé
« Sénat » deux mandats de l'Assemblée — un fait faux de plus, exactement ce que
l'épic #486 reproche au champ de niveau profil.

C'est aussi ce qui distingue ce champ de `chambre` au niveau profil : dériver la
chambre d'**une personne** de « quel site a répondu » est faux, parce qu'une
carrière n'est pas réductible à une chambre ; dériver la chambre d'**un mandat**
du jeu de données qui l'a rendu est exact, parce que ce mandat vient de là.

### Correction au diagnostic : les deux chambres se rencontrent déjà, dans la CI

#488 note qu'elle « ne fusionne pas les deux profils bruts », et #492 en déduit
qu'aucun profil ne porte de mandats des deux chambres. C'est vrai de
`build_profile_any_chambre` ; **c'est faux du pipeline**. `generate-data.yml`
lance deux passes scopées — `extract-an` (`--source an`) et `extract-senat`
(`--source senat`) — dont les profils bruts se retrouvent dans
`merge_profile.merge_raw_dirs`, additivement, pour le **même slug**. Un candidat
présent des deux côtés y accumule donc déjà les `mandat_electif` des deux
chambres dans un seul `mandats[]`. C'est la trace qu'on lit sur
`jean-luc-melenchon` : profil brut `senateurs`, trois `mandat_electif`, dont deux
AN. Le ROADMAP note déjà cette voie pour le scalaire `chambre` (« artifact merge
order », sous-issue D) ; elle vaut aussi pour les mandats.

Deux conséquences. L'estampille sert **dès le prochain run complet** : les
mandats AN et Sénat d'un même candidat arriveront dans le même profil, chacun
portant sa chambre — ce dont l'UI (sous-issue F) a besoin, sans travail de fusion
supplémentaire. Et le filtre d'éligibilité par chambre n'est pas une précaution
théorique : c'est le garde-fou de cette voie-là.

### Le `null`, et pourquoi un seul warning par profil

Un mandat collecté avant #492 ne porte pas d'estampille, et sa chambre **n'est
pas reconstituable a posteriori** : ni par `source_url` (mesuré nul ci-dessus),
ni par la chambre du profil (démonstration ci-dessus). Il est publié à `null`,
jamais à une valeur par défaut (§2.5).

Le warning est **agrégé par profil**, pas émis par mandat, et il porte le compte.
Ce cas n'est ni celui de #474 — les 92 parlementaires en mission sont écartés
**sans** warning, parce que leur exclusion est le comportement attendu et
permanent — ni tout à fait celui de #488, où chaque échec de chambre est une
panne et mérite sa ligne. Ici le `null` est déterministe, uniforme et
**transitoire** : le compte est précisément la mesure qui dira quand la migration
est terminée. Un warning par mandat produirait 214 occurrences sur 189 profils
là où `audit_pivot_dataset.compute_agregation_warnings`, qui agrège par préfixe,
n'en montrerait de toute façon qu'une ligne.

### Le report à la fusion, sans lequel le champ ne se remplirait jamais

`merge_lists_by_key` est additif pur : l'entrée ancienne gagne, et la clé d'un
mandat (`categorie`, `fonction`, `label`, `debut`) ne contient pas la chambre. La
version neuve, estampillée, porte donc la **même clé** que l'ancienne et serait
écartée à chaque régénération : le champ resterait à `null` pour toujours en
fusion additive, et ne se remplirait qu'en `cold_start` / `--no-merge`.

`merge_profile.backfill_mandat_chambre`, appelée aux deux niveaux de fusion
(brut et pivot), reporte donc la chambre d'un mandat neuf sur l'entrée ancienne
de même clé. Le report est strictement croissant en information : il ne remplit
qu'un champ **absent ou nul**, n'écrase jamais une chambre déjà déterminée, ne
touche aucun autre champ, ne réordonne ni ne duplique rien, et reconstruit
l'entrée au lieu de muter l'objet de l'appelant. Il est **volontairement limité à
`chambre`** : généraliser le report ferait de la fusion additive une fusion par
champ, ce qu'elle n'est pas.

*Alternative écartée* : mettre la chambre dans la clé de fusion. Elle
dédoublerait chaque mandat déjà connu au premier run estampillé — un mandat en
double, c'est un `debut_dans_groupe` faux et un `mandats_agreges` gonflé.

### Le risque de dénominateur (§2.7) : corrigé ici, sans effet aujourd'hui

`group_profile._member_eligibility_intervals` retenait **tous** les
`mandat_electif` sans distinction de chambre, et `_is_eligible_at` renvoyait
`True` dès qu'une date tombait dans n'importe lequel — une union. Un mandat
sénatorial ne peut pas chevaucher un mandat AN (incompatibilité
constitutionnelle), donc dans le cas général l'union est inoffensive ; le cas
dangereux est le **changement de chambre en cours de législature**, qui prolonge
la fenêtre d'éligibilité au-delà du départ de l'Assemblée et compte le membre
absent sur des scrutins qu'il ne pouvait plus voter.

Le filtre est écrit ici parce que #492 le rend écrivable pour la première fois :
avant, aucun mandat ne portait de chambre. `_mandats_electifs(mandats, chambre)`
restreint à la chambre du groupe, et la chambre est passée depuis
`build_groupe_profile` à `_derive_membre_entry`, `_compute_cohesion_votes`,
`_aggregate_mandats` et `compute_ecarts_cohesion_internes`.

Deux règles qui font tout l'écart entre corriger et casser :

- **un mandat à `chambre: null` est conservé.** L'écarter réduirait un
  dénominateur publié sur la foi d'une donnée absente — l'erreur exactement
  symétrique de celle qu'on corrige. Conséquence directe et mesurée : sur le
  corpus d'aujourd'hui, où les 214 `mandat_electif` AN/Sénat sont tous à `null`,
  **ce filtre ne change aucun dénominateur publié**. La correction entre en
  vigueur au fil de la collecte, mandat par mandat, jamais d'un coup ;
- **« aucun mandat électif » et « des mandats électifs, mais aucun dans cette
  chambre » ne sont pas la même chose.** Le premier reste `None` → éligible par
  défaut (absence d'information, comportement historique). Le second renvoie `[]`
  → jamais éligible : ce n'est pas une absence d'information, c'est
  l'information que ce membre ne siège pas dans cette chambre.

**Mesuré vs projeté.** L'exposition réelle au défaut est **nulle aujourd'hui**,
et le dénominateur d'un groupe est borné à sa seule législature — ce n'est pas
une fraction des 17 535 scrutins de l'index. Mesuré sur `f5a828b`, sur les 7
profils de groupe publiés :

| Groupe | `cohesion_votes` | Candidats déclarés parmi les membres |
| --- | ---: | --- |
| `AN-REN-16` | 4 099 | `gabriel-attal` |
| `AN-RN-16` | 3 405 | `marine-le-pen` |
| `AN-LR-16` | 2 232 | — |
| `AN-LFI-16` | 1 996 | — |
| `AN-SOC-16` | 814 | `jerome-guedj` |
| `Senat-LR` | **0** | `bruno-retailleau` |
| `Senat-SER` | **0** | — |

Deux raisons indépendantes, chacune suffisante : les trois candidats siégeant
dans un groupe à dénominateur réel viennent tous d'un profil brut
`chambre: "deputes"` (le seul profil brut `senateurs` du corpus est
`jean-luc-melenchon`, qui n'est membre d'aucun groupe publié) ; et le seul
bicaméral, `bruno-retailleau`, est dans un groupe à `cohesion_votes: 0` —
aucun jeu de données Sénat structuré n'étant exploitable (§ *Senate votes,
amendments, sponsored texts*). Ce qui est corrigé ici est donc une **exposition
future**, celle qu'ouvrirait toute publication de mandats des deux chambres sur
un même profil.

*Repli écarté, vérifié plutôt que supposé* : filtrer sur les mandats
`groupe_politique` au lieu de la chambre. Ils existent sur **188 des 209
profils**, 398 mandats — dont **0 sans date de fin**. Ils ne couvrent donc pas la
législature en cours et ne peuvent pas servir de fenêtre d'éligibilité.

### Ce que ça change sur le corpus, mesuré à vide

Aucune régénération n'a été lancée ; les chiffres ci-dessous viennent d'une
simulation en lecture seule sur `f5a828b` (normalisation des 209 profils bruts
committés, fusion avec les pivots publiés, en mémoire).

- **0** des 209 pivots publiés devient invalide avec la nouvelle règle de schéma ;
- après une passe `--pivot-only` (aucun appel réseau) : 228 `mandat_electif`, dont
  **14 estampillés `PE`** (le chemin européen est immédiatement déterminé) et
  **214 à `null`**, portés par **189 profils** qui reçoivent chacun **un** warning ;
- les 214 restants s'estampillent à leur prochaine collecte réelle, via le report
  de fusion.

### Périmètre

Le champ n'est écrit que sur les `mandat_electif`. La chambre d'une commission ou
d'un groupe d'amitié est un fait réel, mais non publié en v1 : l'inventer sur
16 625 mandats pour l'homogénéité du dictionnaire serait la même faute, en plus
volumineux.

Aucun mandat n'est fusionné entre chambres par ce changement : un profil de
candidat bicaméral continue de ne publier que les mandats de la chambre retenue
par #488. Publier les deux suppose de trancher `chambre` au niveau profil — c'est
la sous-issue D (#493, `needs-human`), et #492 ne la préempte pas.

<a id="budget-collecte-interventions"></a>
## Borner la collecte d'interventions, pas le job qui la contient (#498) (2026-08-20)

`timeout-minutes: 5` sur `extract-an` tuait les shards dès que
`collect_interventions=true`. Sur les deux seuls runs connus dans ce mode :
4 shards tués sur 8 (run `32302557156`, 19/08 21:11), puis **8 sur 8** (run
`32379928098`, 20/08 14:24) — ce dernier n'a collecté aucun profil AN.

### Deux chiffres, deux populations

Le commentaire qui justifiait `5` s'appuyait sur des durées de « 1m18s-2m10s ».
Elles sont exactes — et elles portent **toutes sur des runs qui ne collectent
pas d'interventions**, `collect_interventions` valant `false` par défaut.

En séparant les populations, le relevé par step change complètement de sens :

| population | n | job total | dont extraction | dont préambule |
| --- | ---: | ---: | ---: | ---: |
| `collect_interventions=false` (runs `32233766814`, `32288588518`) | 16 shards | 117-207 s | **8-18 s** | 107-193 s |
| `collect_interventions=true` (runs `32302557156`, `32379928098`) | 16 shards | 208-321 s | 59-286 s | 30-149 s |

Le « pire cas normal » de 2m10 n'était donc **pas** un coût d'extraction : dans
le mode par défaut, l'extraction coûte 8 à 18 secondes. Les deux minutes sont le
préambule du job — `actions/checkout` (14 à 127 s selon les shards),
`setup-python`, `pip install`, restauration des deux caches, téléchargement de
l'artifact d'amendements.

Conséquence, jamais nommée jusqu'ici : `timeout-minutes` ne borne pas la
collecte, il borne `préambule + collecte`. Ce qui reste réellement à
l'extraction varie de 107 s à 270 s **d'un shard à l'autre du même run**, selon
la durée du checkout. `laurent-wauquiez` (run `32302557156`) a été tué après
173 s d'extraction seulement : son checkout en avait consommé 126.

### Ce que le mode interventions ajoute

Trois charges, dont deux que l'issue n'avait pas identifiées :

1. **la recherche NosDéputés** (jusqu'à `nosdeputes_max_pages` pages × 4
   domaines) — 90 s mesurées sur `jean-luc-melenchon`, run `32379928098` ;
2. **les archives de débats Syceron**, 3 législatures, 22 à 55 s chacune quand
   `data.assemblee-nationale.fr` répond, 118 s au total sur `laurent-wauquiez` ;
3. **les archives de questions officielles** QE/QG/QOSD, jusqu'à 12 fichiers ;
4. et seulement ensuite, **le repli NosDéputés document par document**, qui ne
   se déclenche que si Syceron ne rend rien pour cet `acteurRef`.

L'issue attribuait le surcoût au seul point 4. `laurent-wauquiez` le dément :
**zéro** appel de détail NosDéputés, et pourtant un timeout — il était encore
dans les archives de questions à la 5ᵉ minute. Un circuit ouvert sur
`nosdeputes.fr` (piste 3 de l'issue) ne l'aurait pas sauvé.

### Décision : un budget interne, et un timeout conditionnel qui le contient

**Un budget de temps mur pour la collecte d'interventions d'un candidat**
(`src/budget_collecte.py`, `--budget-interventions-secondes`, 240 s en CI). Il
est vérifié entre deux unités de travail : entre deux législatures Syceron,
entre deux législatures de questions, et **à l'entrée de chaque document**
NosDéputés — la seule granularité fine du parcours, où un document coûte jusqu'à
45 s sur une source dégradée (`read timeout=15` × 3 tentatives) et où il y en a
jusqu'à ~250 par candidat. Jamais au milieu d'une législature : son index par
acteur n'est mis en cache qu'une fois l'archive entièrement lue, et un index
partiel ferait passer une collecte incomplète pour une collecte faite.

Épuisé, il rend la main. Le profil partiel est **écrit**, donc publié, et la
troncature part dans `meta.warnings[]` (`collecte d'interventions tronquée
(budget de temps)`, propagé au pivot par `normalize_nosdeputes`) et en
`::warning::` GitHub, en nommant ce qui n'a pas été collecté :
`87 document(s) d'intervention NosDéputés, 2 législature(s) de questions
officielles`.

C'est là que le budget se distingue du timeout, et c'est la vraie raison de le
préférer. **Un shard tué par `timeout-minutes` ne publie rien du tout.**
L'issue supposait l'inverse (« ce qui avait été collecté avant la coupure est
publié ») parce que les steps `Profils écrits par ce job` et `Upload artifact
AN` s'exécutent bien, en `success`, sur un job tué. Ils s'exécutent — et
rapportent `Publication : 0 profil(s) écrits par ce job`, sur les 12 shards tués
des deux runs, vérifiés un par un, sans exception. Le profil n'est écrit qu'à la fin de la collecte
du candidat : coupé avant, le manifeste est vide et l'artifact aussi. Cinq
minutes de runner par shard pour aucune donnée.

**Le `timeout-minutes` devient conditionnel au mode** :
`${{ inputs.collect_interventions && 9 || 5 }}`.

- 5 min sans interventions : inchangé, et désormais justifié par la bonne
  population (extraction 8-18 s, préambule 107-193 s) ;
- 9 min avec : 240 s de préambule provisionné (mesure max : 193 s) + les 240 s
  du budget + ~60 s de marge.

240 s de budget, c'est 1,5× la plus longue extraction qui soit allée au bout
dans ce mode (160 s, `edouard-philippe`, run `32302557156`) — une mesure prise
dans le mode où la valeur s'applique, ce qui manquait à la valeur qu'elle
remplace.

### Le risque d'origine reste borné

Ce qui justifiait 5 min était un shard resté bloqué 20+ min sans signature
reconnue (run du 16/08, `jerome-guedj`), qui avait immobilisé tout le matrix
séquentiel (`max-parallel: 1`) derrière lui. Trois raisons pour lesquelles 9 min
ne le réintroduit pas :

1. la valeur ne s'applique que si `collect_interventions` est coché, ce qui
   n'est pas le défaut ;
2. dans ce mode, la collecte se borne elle-même : le timeout de job n'est plus
   le mécanisme d'arrêt normal, mais le dernier recours contre un vrai gel — que
   le budget, vérifié entre deux unités, ne peut pas voir (c'est le rôle des
   watchdogs par requête, `_get_with_watchdog` #340 et `download_watchdog` #370) ;
3. un tel gel coûte alors 9 min au lieu de 20+.

Le couplage entre les deux valeurs est vérifié par
`tests/test_ci_budget_interventions.py` : budget + préambule provisionné doit
tenir dans le timeout du mode où il s'applique, le timeout du mode par défaut ne
peut pas augmenter, et celui du mode interventions ne peut pas dépasser 10 min.
Le message de temps mur de `prepare-an-matrix` lit la même valeur — annoncer
5 min par shard pendant qu'un run en consomme 9 rendrait cet avertissement faux
au moment précis où il sert.

### Alternatives écartées

**Élargir simplement le timeout.** C'est la solution que le commentaire existant
interdisait déjà, à raison : elle rend au blocage silencieux exactement le coût
qu'on lui avait retiré, et elle ne produit toujours aucun signal — un shard
tronqué resterait indiscernable d'un shard complet.

**Un circuit ouvert après N échecs consécutifs sur un hôte** (piste 3 de
l'issue). Réduirait le coût du repli NosDéputés dégradé, mais `laurent-wauquiez`
montre qu'on peut atteindre le timeout sans un seul appel de détail : le
mécanisme ne couvre qu'une des trois charges. Le budget, lui, les couvre toutes,
et son plafond est indépendant du mode de panne. Reste une piste valable pour
réduire le *gaspillage* (3 × 15 s par document sur une source à terre), pas pour
borner la phase.

**Faire du budget un `input` du workflow.** Refusé : les inputs viennent d'être
refondus (#497) et un dixième bouton ferait porter à l'opérateur un arbitrage
qui se déduit du timeout. La valeur vit à côté de celui-ci, avec le test qui les
tient ensemble.

### Ce qui n'est pas traité ici, et qui est le vrai coût fixe du mode

Les archives Syceron et de questions **sont** dans le `path:` du cache
`public-data-cache-an-<semaine>` — mais elles n'y arrivent jamais. La clé de la
semaine est écrite par le premier job qui la touche, et ce sont des jobs en
`--skip-interventions` : ils ne remplissent ni `.cache/syceron_an` ni
`.cache/questions_an`. Les shards en mode interventions font ensuite un *exact
key hit* et `actions/cache` saute leur sauvegarde post-job — `Cache hit occurred
on the primary key public-data-cache-an-2026-W34, not saving cache` (job
`96228895556`). Vérifié sur le run `32379928098` : le tar restauré ne contient
que `acteurs_historique_an`, `scrutins_an` et `dossiers_an`.

Chaque shard re-télécharge donc l'intégralité des archives de débats et de
questions — c'est le défaut de #424, reparu sur les deux répertoires que seul le
mode interventions remplit. Le corriger proprement demande le même traitement
qu'aux amendements : un job dédié qui construit les index une fois et les publie
en artifact, `extract-an` les consommant en lecture seule. Une clé de cache
séparée ne suffirait pas — le premier shard sauvegarderait un index partiel et
les suivants, en *exact key hit*, ne pourraient plus le compléter de toute la
semaine. Hors périmètre de cette PR, consigné dans `ROADMAP.md`.

Tant que ce coût fixe reste, le budget de 240 s sera souvent consommé par des
téléchargements déjà faits par le shard précédent : les profils seront partiels,
mais partiels **et déclarés**, au lieu d'absents et muets.

---

<a id="refonte-inputs-workflow"></a>
## Le formulaire de lancement disait pourquoi, pas quoi (2026-08-20)

Les neuf inputs de `workflow_dispatch` portaient **~575 mots** de description,
jusqu'a 138 pour `roster_extraction_limit` seul. Elles avaient grossi par
sedimentation : chaque incident y ajoutait son rationale, ses numeros d'issue
et ses mesures.

Un formulaire de lancement se lit sous contrainte de temps, souvent au moment
ou quelque chose ne va pas. Un essai y est ignore. Les descriptions ne disent
plus que **ce que fait** l'input ; le pourquoi vit ici, atteignable par ancre.

### Renommage, en anglais

Demande explicite. Les noms melangeaient trois conventions (`fresh_run`,
`tolerer_pertes_profils`, `max_pages`).

| avant | apres |
| --- | --- |
| `fresh_run` | `cold_start` |
| `overwrite_profiles` | inchange (deja anglais et exact) |
| `roster_refresh_existing` | `refresh_existing_only` |
| `threshold` | `incomplete_read_threshold` |
| `tolerer_pertes_profils` | `allow_declared_losses` |
| `tolerer_references_orphelines` | `allow_broken_references` |
| `extract_interventions` | `collect_interventions` |
| `max_pages` | `nosdeputes_max_pages` |
| `roster_extraction_limit` | `roster_limit` |

### Les trois confusions traitees

**`roster_limit` s'applique PAR SHARD.** Dit en une ligne dans la description,
la ou 138 mots l'enterraient. C'est ce qui explique le forcage a un seul shard
des qu'elle est non nulle.

**`cold_start` implique `overwrite_profiles`.** Les deux booleens se
recouvraient sans que rien ne le dise ; cocher les deux n'a jamais eu de sens.
Chaque description nomme desormais l'autre.

*Alternative ecartee* : fusionner les deux en un `type: choice` a trois modes
(incremental / overwrite / cold_start). C'est le design correct — il rend la
combinaison absurde impossible par construction — mais `fresh_run` compte **22
usages** et `overwrite_profiles` **8**, avec des conditions composees. Une
refonte de logique conditionnelle a l'occasion d'une tache de nommage aurait
melange deux risques. A rouvrir separement.

**Les deux tolerances ne se ressemblaient que par le prefixe.** `allow_declared_losses`
couvre une perte legitime et **declaree** ; `allow_broken_references` couvre une
reference cassee, qui n'a jamais de cas d'emploi normal. Les nouveaux noms les
opposent au lieu de les rapprocher, et la description du second porte la
distinction explicitement (verifiee par test).

### Une regression trouvee en route, et le garde-fou qui manquait

`retry-generate-data.yml` ne relit pas les inputs du run precedent — l'API ne
les expose pas — il les **reconstruit en analysant les logs**, puis redeclenche
par `gh workflow run -f nom=valeur`. Ce couplage est reel mais invisible : rien
dans l'un ne reference l'autre.

Deux pannes silencieuses ont ete constatees le meme jour :

1. **`-f workers=...` survivait a la suppression de l'input** (#workers-fige-a-1,
   une heure plus tot). Le dispatch aurait echoue en 422 « Unexpected inputs
   provided » — decouvert seulement le jour ou une relance devient necessaire.
2. **Au renommage, les lectures `steps.inputs.outputs.X` ont ete mises a jour
   mais pas les `echo "X=..." >> $GITHUB_OUTPUT`.** La relance serait repartie
   sur les valeurs par defaut au lieu de celles du run d'origine, sans erreur ni
   trace : un run `cold_start=true` relance en incremental. C'est exactement la
   regression que le commentaire de la relance dit avoir deja corrigee une fois.

`tests/test_ci_inputs_workflow.py` verifie desormais les deux sens du contrat,
plus le plafond de 40 mots par description. Le premier test a ete verifie en
echec sur l'etat reel de `main`.

Nettoyage associe : l'extraction de `workers` depuis le log d'`extract-senat`,
sa sortie sans consommateur et les trois commentaires devenus faux ont ete
retires. Les cinq noms d'etape `(fresh_run uniquement)` sont alignes — la
relance en selectionne un **par son nom**.

<a id="workers-fige-a-1"></a>
## `workers` retire du formulaire : un bouton qui ne pouvait que nuire (2026-08-20)

`workflow_dispatch` exposait un input `workers` dont la description disait
elle-meme, depuis #467 : « MAINTENU A 1 PAR #467, et desormais sur une mesure :
augmenter cette valeur RALENTIT l'extraction ».

Un parametre qu'on documente comme nuisible reste un piege. Dans un formulaire
`workflow_dispatch`, « workers » se lit comme un levier d'optimisation ; sa
valeur par defaut ne protege que celui qui n'y touche pas.

### Ce que la mesure de #467 etablit

| | `workers=1` | `workers=4` |
| --- | ---: | ---: |
| avant #467 | 74,1 s | **94,6 s** (+28 %) |
| apres #467 | 9,8 s | **13,8 s** (+41 %) |

La charge est du parsing JSON sous GIL, serialise de surcroit par les verrous
par legislature : quatre threads se disputent le meme interpreteur. Le RSS de
pointe monte en prime (1 281 -> 1 374 Mo en local), sur un job deja expose a
l'OOM (#377).

### Pourquoi le figer plutot que le decouper

L'input etait **partage par trois charges de natures differentes** — le chemin
AN et le roster (CPU, parsing sous GIL), `extract-senat`, et `extract-ue-officiel`.
C'est ce qui rendait la question insoluble : impossible de le figer sans perdre
le levier sur les deux autres, impossible de l'ouvrir sans degrader l'AN.

Le decoupage a ete envisage puis ecarte : la description de l'input notait que
le Senat est « reellement borne par NosDeputes », c'est-a-dire par la source et
non par le CPU. Y ajouter des workers ne le rendrait pas plus rapide — cela le
rendrait moins courtois envers une source publique, ce que le projet refuse par
ailleurs (la temporisation de politesse de #467). Le levier ne servait donc
nulle part.

`extract-senat` a ete chronometre a **4,6 min pour un timeout de 90** : aucune
urgence ne justifie de rouvrir la question.

### Ce qui change

L'input disparait du formulaire ; les **cinq** sites qui le lisaient passent a
`--workers 1` en dur (`extract-senat`, `extract-ue-officiel`, le shard roster,
et les deux invocations de `merge-and-pivot`). Le flag `--workers` de
`generate_all_profiles.py` **reste** : il garde son utilite en local, et rien
n'indique qu'il faille amputer la CLI parce que la CI n'en veut plus.

**A rouvrir si** la duree d'`extract-senat` ou d'`extract-ue-officiel` devenait
dimensionnante — auquel cas ce serait un input propre a ces jobs, pas un input
partage avec un chemin que le parallelisme degrade.

<a id="id-pivot-sans-prefixe"></a>
## L'`id` d'un profil pivot est le slug : le préfixe de provenance était instable (#487) (2026-08-20)

Sous-issue A de l'épic #486.
`normalize_nosdeputes` construisait `f"{source_type}:{slug}"`, où `source_type`
venait de `_SOURCE_TYPE_MAP` (`deputes` → `nosdeputes`, `senateurs` →
`nossenateurs`). L'`id` est désormais le **slug** seul.

### Ce n'est pas la redondance qui a tranché, c'est l'instabilité

Le préfixe était redondant — la provenance est consignée trois fois ailleurs
(`sources[].type`, `identite.source_url`, `meta.provenance`) — mais la
redondance seule ne justifiait pas une migration. Ce qui l'a justifiée est
mesuré : entre `25f7bc7` et `01ffa7f`, sur les mêmes 209 profils et sur des
carrières inchangées, **deux profils ont changé d'`id`, en sens opposés** :

| Profil | Avant | Après |
| --- | --- | --- |
| `jean-luc-melenchon` | `nosdeputes:` | `nossenateurs:` |
| `stephane-mazars` | `nossenateurs:` | `nosdeputes:` |

Ce n'est pas un accident isolé, c'est le comportement normal d'un identifiant
dérivé de « quel site a répondu ce jour-là » : `generate_all_profiles` s'arrête
à la première chambre qui répond, et une défaillance transitoire de
`nosdeputes.fr` suffit à faire basculer le préfixe (#488, #484). L'option
concurrente — garder le préfixe en cessant de le lire comme une chambre — a été
écartée pour cette raison : **documenter la sémantique d'un identifiant qui
change ne le stabilise pas.**

### Le slug peut porter l'identité, et rien ne joignait sur l'`id`

Sur les 209 profils de `01ffa7f` : **209 slugs distincts, aucun doublon**, et
`raw_profile["slug"]` égale le nom de fichier sur les 209 — l'`id`, le slug et
le chemin ne font donc qu'un.
`merge_raw_profile` fusionne par chemin de fichier, `audit_diff_profils` compare
par chemin, l'UI joint sur le slug (`manifest.candidates.find((c) => c.slug ===
id)`) et expose `id: c.slug`. Le seul lecteur du préfixe dans tout le dépôt est
`group_profile.py:1295` (`--merge-existing`), et il le **retire** pour récupérer
le slug : un `id` déjà sans préfixe le traverse inchangé.

### Le cas européen : `europarl:131580` (Bardella)

Un seul profil portait un `id` qui ne dérivait pas de son slug. Le retirer ne
coûte aucune traçabilité (§2.2) : le numéro `131580` apparaît **25 fois** dans
le profil, dont 24 hors de l'`id` — la source EP et le `source_url` de chacun
des 22 mandats européens. `normalize_europarl` prend donc un paramètre `slug`
optionnel qui devient l'`id`.

**Reste à câbler, et c'est dit ici plutôt que découvert plus tard** : le
paramètre existe et est testé, mais ses deux appelants sont dans
`src/generate_all_profiles.py` (l. 520 et 675), fichier qu'une autre issue en
vol (#488) réécrit au même moment. Le câblage est d'un mot-clé —
`slug=effective_slug` — et il appartient à qui touchera ce fichier ensuite.
Jusque-là, `jordan-bardella` conserve `europarl:131580` : c'est le seul profil
du corpus dont l'`id` n'est pas son slug, et il n'est pas instable pour autant
(l'identifiant EP ne dépend pas de quelle chambre a répondu). L'énoncé « l'`id`
est le slug » vaut donc pour 208 des 209 profils tant que ce mot-clé n'est pas
posé.

**Sans slug, aucun slug n'est inventé.** `ue_profile` n'en porte pas, et le seul
qu'on pourrait en tirer viendrait de `nom_complet` — donc d'une donnée de
collecte, exactement le défaut qu'on retire. Le repli reste
`europarl:<identifiant_pe>`. Même raisonnement pour `mep_profile.py:351`
(`parltrack:{ep_id}`), laissé tel quel : c'est un outil autonome dont les seules
entrées sont un nom ou un identifiant EP, et **aucun profil de
`pivot_data/profiles/` n'en sort** (0 sur 209 à `01ffa7f` ; le pipeline appelle
`normalize_parltrack_dumps.enrich_pivot_with_parltrack`, qui enrichit un pivot
existant sans en créer).

### La réserve instruite avant de coder : ce que le contrôle de perte en fait

`gouvernement_roster` publie `membre_id: profil["id"]`. Changer la convention
réécrit **113 entrées dans 10 fichiers**, et le contrôle de perte étendu par
#470 tourne dans `merge-and-pivot` **en échec dur avant le commit**, sur tout
`pivot_data/`. Si la réécriture s'y lisait comme une régression, la correction
bloquerait le commit qu'elle doit produire.

Scénario rejoué, pas déduit — rosters reconstruits des deux côtés par
`build_gouvernement_roster` depuis les 209 pivots de `01ffa7f`, puis
`audit_diff_profils --ref HEAD` sur les six collections, avec un **témoin** :
les mêmes rosters reconstruits **sans** le changement d'`id`. Différence entre
les deux rapports :

| Constat | Témoin | Avec #487 |
| --- | ---: | ---: |
| `profiles` · changement de valeur d'un scalaire (`id`) | 0 | **208** |
| `gouvernements` · perte sur liste stable | 1 | 1 |
| pertes bloquantes **ajoutées** par #487 (6 collections) | — | **0** |

Deux régimes se combinent, et aucun ne bloque :

- **Les 113 `membre_id` sont invisibles au contrôle.** `membre_id` vit à
  l'intérieur d'une entrée de `membres[]`, et le contrôle ne compare d'une liste
  que sa **cardinalité** — inchangée, 113 avant, 113 après. Les scalaires
  surveillés d'un gouvernement sont `gouvernement_id`, `nom`,
  `premier_ministre`, `periode.debut` ; `membre_id` n'en est pas. Le rapport le
  dit déjà sous « Hors périmètre » : « la **valeur** des entrées d'une liste :
  seule leur cardinalité est comparée. » Idem pour les `membre_id` des groupes.
- **Les 208 `id` de profils sont vus, signalés, non bloquants.** `id` *est* un
  scalaire surveillé de `COLLECTION_PROFILS` ; le passage `nosdeputes:x` → `x`
  est un changement de valeur (A → B), le régime que #470 a explicitement
  retenu comme non bloquant. Seule une régression `renseigné → null` bloque, et
  il n'y en a aucune.

L'unique constat bloquant du run — `gouvernement-BAYROU.json · membres : 12 →
9` — **est présent à l'identique dans le témoin** : il ne vient pas de #487. Il
vient de ce que les fichiers de gouvernement committés datent d'avant la
déduplication de [[deduplication-entrees-membres]] (2 entrées) et d'une
troisième entrée `astrid-panosyan-bouvet` (« Ministère de l'économie… »,
`debut: 2026-02-04`, `actif: true`) que le code actuel ne reproduit plus. Le
prochain `merge-and-pivot` bloquera dessus **indépendamment de cette issue** ;
c'est à instruire à part.

### Migration : par régénération, sans table de correspondance

`normalize_nosdeputes` reconstruit l'`id` à chaque passage, et
`merge_pivot_profile` part de `dict(new)` sans jamais rattraper `id` : la valeur
régénérée l'emporte sur l'ancienne, y compris préfixée (vérifié, et figé par
`tests/test_id_pivot_sans_prefixe.py`). Aucun fichier de `pivot_data/` n'a été
réécrit à la main.

Conséquence collatérale, inerte aujourd'hui :
`amendements[].amendement_non_resolu.premier_signataire` reprend l'`id` du
profil (`normalize_nosdeputes.py:230`) et suit donc la nouvelle forme — zéro
occurrence sur le corpus, dont la couverture `uid` est de 100 %.

### Le garde-fou

Un test qui vérifie `id == slug` serait faible : un préfixe **stable**
réintroduit le passerait. `tests/test_id_pivot_sans_prefixe.py` vérifie donc que
l'`id` **ne dépend d'aucune donnée de collecte** — chaque champ du profil brut
autre que `slug` est absenté puis remplacé par huit variantes, et l'`id` ne doit
pas bouger. Sans le correctif, il échoue en nommant la cause : « l'`id` a suivi
le champ collecté `'chambre'` ».

`_SOURCE_TYPE_MAP` n'est pas supprimé : il reste la source de `sources[].type`,
où il décrit la provenance d'**une source** — ce qui est vrai et stable.

<a id="integrite-referentielle-pivot"></a>
## Rien ne vérifiait que les clés publiées résolvent : le contrôle d'invariance (#485) (2026-08-20)

**Il n'y avait aucun défaut.** Mesuré sur `01ffa7f` le 20/08/2026, index et
couches référençantes relevés ensemble :

| Vérification | Résultat |
| --- | ---: |
| Références `votes[].scrutin_id` (profils) | 524 353 |
| Références `cohesion_votes[].scrutin_id` (groupes) | 12 546 |
| Références `amendements[].amendement_id` (profils) | 810 552 |
| **Références orphelines**, les trois renvois confondus | **0 / 1 347 451** |
| Entrées de `scrutins.json` jamais référencées | **0 / 17 535** |
| Entrées de `amendements/` jamais référencées | **0 / 207 238** |

Rien à réparer. Ce qui manquait, c'est qu'**aucun outil ne vérifiait cette
propriété**, devenue structurellement fragile.

### Pourquoi elle est fragile depuis #431 et #432

Ces deux issues ont sorti le détail du scrutin et de l'amendement des profils
pour un index partagé ; les profils n'en gardent qu'une **clé**. La donnée est
passée d'un état **auto-suffisant** — chaque profil portait sa copie complète —
à un état **référentiel** : un vote n'a plus de sens que si sa clé résout.
Trois façons de casser ça, dont **aucune ne bouge un compteur** : une clé qui ne
résout pas, une convention de clé changée, un index publié partiellement.

### Pourquoi ce n'est pas une extension du contrôle de perte

[[controle-de-perte-avant-commit]] compare un **avant** et un **après**. Il
verrait une chute du nombre d'entrées d'un index, mais **pas** une rupture de
correspondance entre deux couches du **même** état : un run où les profils et
l'index seraient tous deux régénérés de façon cohérente-mais-fausse lui
paraîtrait irréprochable. C'est une **invariance dans un état donné**, pas une
variation dans le temps — deux contrôles complémentaires, jamais alternatifs.

`tests/test_audit_integrite_referentielle.py::test_le_controle_de_perte_ne_voit_pas_ce_que_celui_ci_voit`
en fait la démonstration plutôt que de l'affirmer : il réécrit les identifiants
de l'index (`an:` → `an-v2:`) des deux côtés, constate que le contrôle de perte
ne relève **rien** — toutes les cardinalités sont identiques — et que celui-ci
relève chaque référence.

### Le diagnostic de #470 était trop pessimiste, et c'est ce qui débloque le sujet

La section « ce qu'il ne couvre pas » écrivait que l'intégrité référentielle
était « hors de portée d'un contrôle à mémoire bornée : il faudrait tenir les
deux ensembles de clés en mémoire simultanément ». **Non** : il n'en faut qu'un,
et c'est le petit. Les clés d'index tiennent dans un `set` ; le côté
référençant — les 102 Mo de profils, la seule couche qui grossira — se parcourt
**un document à la fois**. Ce renversement est tout le contrôle.

### De quel côté chaque arbitrage penche

Ce code décide si un commit de données part. Faux positif = publication de
données saines bloquée ; faux négatif = incohérence publiée.

**Référence orpheline : bloquant.** Le fichier et la clé sont nommés. Aucun faux
positif possible **par construction** : la propriété est binaire — la clé est
dans l'index ou elle n'y est pas — jamais un seuil ni une comparaison à un état
antérieur. C'est la différence de nature avec toutes les décisions de #470, qui
arbitraient des variations légitimes contre des variations suspectes. §2.5 le
tranche seul : une donnée non résolue échoue bruyamment.

**Index ou shard absent : bloquant, mais rapporté à part.** Le remède n'est pas
le même — publier un fichier, pas corriger des clés — et un shard manquant rend
orphelines toutes les références d'une législature d'un coup. Les énumérer une à
une noierait la cause : le motif est distinct, et le compteur reste juste
pendant que les exemples nommés sont bornés à 20.

**Clé absente sans son enregistrement de repli : bloquant.**
`validate_profil()` l'interdit déjà. **Avec** son `scrutin_non_resolu` /
`amendement_non_resolu` : **non bloquant** — c'est la forme normale d'un
amendement du Parlement européen, que ParlTrack livre sans uid AN. La donnée est
conservée, rien n'est perdu ni inventé.

**Le sens inverse — entrées d'index que personne ne référence : rapporté,
jamais bloquant.** Que ce soit exactement 0 à couverture partielle (209 profils
sur 752) méritait d'être compris avant d'en faire une règle. Ce n'est pas une
coïncidence : les deux index sont **construits depuis** `raw_data/profiles`
(`build_scrutins_index.py`, `build_amendements_index_pivot.py`), donc toute
entrée vient d'un profil, et il y a autant de profils bruts que de pivots (209
et 209). Mais leur fusion est **additive par contrat** — « a partial run must
never drop ballots that other profiles' mappings still point at » (AGENTS.md
§3). Cette additivité **implique** qu'une entrée survive légitimement à son
référent : profil corrigé, membre sorti du corpus, tranche non retraitée.
Bloquer dessus reviendrait à interdire la propriété de sûreté principale du
pipeline. C'est un **compteur de dérive**, pas un verdict.

**Les amendements : traités, pas écartés.** Leur index est shardé par
législature, donc plus exposé à une publication partielle qu'un fichier unique
(#431) — c'était la raison de les inclure, pas de les sauter. Coût mesuré :
+1,2 s et +87 Mio, et l'ensemble reste sous le plafond. `--sans-amendements`
existe comme soupape, et **retire le renvoi du périmètre** au lieu de filtrer
ses constats : le rapport dit alors qu'il n'a pas regardé, plutôt que de
déclarer sain ce qu'il n'a pas lu.

### La tolérance est distincte, et ce n'est pas un détail

`tolerer_references_orphelines` **ne partage rien** avec
`tolerer_pertes_profils`. #470 avait identifié le piège dans l'autre sens :
rendre bloquant un contrôle grossier force l'opérateur à relancer avec la
tolérance, ce qui **désarme du même coup les contrôles précis**. Les fusionner
ferait qu'une perte déclarée légitime publierait au passage des références
cassées. Une perte peut être légitime ; une référence orpheline, non. Ce drapeau
n'a **aucun cas d'emploi normal** : il n'existe que pour qu'une panne de l'outil
lui-même ne puisse pas bloquer indéfiniment toute publication.
`test_la_tolerance_est_distincte_de_celle_du_controle_de_perte` verrouille le
cloisonnement.

### Où il est branché, et pourquoi là

Dans `merge-and-pivot`, **après** le contrôle de perte et **avant** le commit.
L'ordre importe dans un seul sens : l'index doit être écrit avant d'être
vérifié. Il l'est — `generate_all_profiles.py --pivot-only` produit
`scrutins.json` (avant la boucle) et `amendements/` (après), et
`generate_group_profiles.py` produit les `cohesion_votes`. Les trois couches
référençantes et les deux index sont donc sur le disque quand le step tourne, et
`test_le_controle_suit_l_ecriture_des_index` le verrouille.

### Le dimensionnement, qui était le vrai risque

Ce script tourne avant le commit : s'il meurt, rien n'est publié, et un
garde-fou qui meurt est pire qu'un garde-fou absent.
[[controle-de-perte-avant-commit]] s'est déjà fait tuer par l'OOM killer une
fois. Mesuré sur les 209 profils et 7 groupes de `01ffa7f` (`/usr/bin/time`,
médiane de trois exécutions, même machine que #470) :

| | durée | RSS max |
| --- | --- | --- |
| contrôle de perte seul, pour repère | 4,76 s | 186,6 Mio |
| **intégrité référentielle, les deux index** | **3,02 s** | **162,0 Mio** |
| intégrité, `--sans-amendements` | 1,79 s | 74,9 Mio |

Sous les 236 Mio actés par #460, et **sous le contrôle de perte lui-même**. Ce
sont deux **processus successifs**, pas un seul : le pic du job reste celui du
plus coûteux des deux, donc **le plafond ne bouge pas** — 186,6 Mio avant comme
après.

La RSS est **invariante au nombre de profils**. Elle est fixée par le plus gros
shard d'index (`15.json`, 24,7 Mo → ~102 Mio à parser) et par le `set` de clés ;
le côté référençant ne coûte qu'un document (le plus gros profil pèse 2,5 Mo, la
médiane 0,44 Mo). Or les deux index sont **déjà à pleine échelle** : leurs
17 535 scrutins et 207 238 amendements distincts sont construits depuis les
archives AN figées, pas depuis les 209 membres actuels. Le passage à 752 membres
multiplie les **références**, pas l'index.

Seule la durée suit, linéairement, et le détail le montre : **0,79 s** de
lecture d'index (fixe : 0,10 s scrutins + 0,69 s amendements) + **9,1 ms par
profil**. Soit **~7,7 s projetées à 752 profils**, dans un job dont le budget est
de 60 min et la mesure de 47,4.

Une alternative a été écartée : extraire les clés d'un shard sans en construire
les valeurs (lecture ligne à ligne, ou `object_pairs_hook`) ferait tomber le pic
sous les 60 Mio. Refusée — `object_pairs_hook` est appelé de bas en haut et ne
connaît pas sa profondeur, donc ne peut pas garder les clés du **deuxième**
niveau ; et lire un JSON ligne à ligne fait dépendre le contrôle d'un format
d'écriture qui ne porte aucune signification (AGENTS.md §3). Une économie dont on
n'a pas besoin ne vaut pas une fragilité.

### Les fixtures sont figées, et les clés y sont réelles

`tests/fixtures/integrite_referentielle/` : un corpus `sain/` (2 profils, 1
groupe, l'index des scrutins réduit à ses seules entrées référencées, l'index
des amendements shardé sur deux législatures) et six **variantes** qui ne
portent que le fichier qui diffère — orpheline côté profil, côté groupe, côté
amendement, shard absent, clé absente déclarée ou non, entrée d'index dérivée.
Provenance dans `meta.fixture` / `meta_fixture`, sur le modèle de
`tests/fixtures/audit_diff_pertes_reelles/`. Aucun test ne lit le corpus vivant,
absent du disque en CI ([[ci-tests-pytest]]).

Les identifiants sont **extraits du corpus**, pas inventés : une clé fabriquée
ne prouverait rien d'une convention de clé. Seules les clés **cassées** des
variantes sont fabriquées, et elles le sont pour être introuvables.

Vérification que ces tests testent bien quelque chose : le blocage sur
l'orpheline désarmé et la couche `groupes` retirée du périmètre, **15 des 33
tests passent au rouge**.


<a id="deux-chambres-interrogees"></a>
## Le passé sénatorial est un fait de carrière, pas une donnée d'activité : bicaméral pour les candidats seulement (#488) (2026-08-20)

Sous-issue B de l'épic **#486**. Ne touche pas au schéma pivot (la chambre sur
chaque mandat est la sous-issue C), ne corrige pas le profil de Mélenchon
(#484), ne change aucune valeur de `chambre` publiée (sous-issue D).

### Le défaut

`generate_all_profiles.build_profile_any_chambre` retenait **la première chambre
qui rendait une identité** (`CHAMBRES = ["deputes", "senateurs"]`) et avalait
les échecs par un `except Exception: continue` qui n'écrivait qu'une ligne de
log. Deux conséquences, toutes deux observées :

1. un parlementaire présent des deux côtés est classé par **l'ordre de la
   boucle** — Retailleau, sénateur en exercice, publié `chambre: "AN"` ;
2. une **défaillance transitoire** réattribue la chambre publiée sans trace
   (Mélenchon, basculé de `AN` à `Senat`, #484).

### Le périmètre : la provenance, pas la chambre

La collecte bicamérale ne vaut que pour un profil de **candidat**
(`meta.provenance == "candidat_declare"`). Le partage est déjà dans les
données :

| Provenance | Profils (209) | Rôle |
| --- | ---: | --- |
| `candidat_declare` | **8** | le CV publié |
| `roster_groupe` | **201** | matière première d'agrégation groupe/gouvernement |

**Pourquoi ce n'est pas un arbitrage nouveau.** Aucun jeu de données Sénat
structuré n'est exploitable — pas de scrutins nominatifs, `ameli.zip` est un
dump SQL de 717 Mo, `dossiers-legislatifs.csv` n'a pas de champ auteur (§ *Senate
votes, amendments, sponsored texts*, reconfirmé pour la vue Gouvernement).
Conséquence directe, vérifiable dans le corpus : **aucun groupe sénatorial n'est
agrégé**. Les deux fichiers publiés le disent —
`groupe-Senat-LR.json` et `groupe-Senat-SER.json` portent `cohesion_votes: 0`,
là où `groupe-AN-REN-16.json` en porte 4 099.

Le passé sénatorial d'un membre de roster n'alimente donc **rien**. Le seul
usage légitime est **biographique**, sur un CV de candidat : « a été sénateur de
2004 à 2010 » est un fait de carrière, pas une donnée d'activité.

**La population réelle**, mesurée sur `raw_data/candidats.json` :

| | |
| --- | ---: |
| candidats déclarés | 13 |
| … à slug résolvable (seuls à atteindre la collecte FR) | **8** |
| … dont le slug figure au roster complet du Sénat | **2** |

Ces deux-là sont `jean-luc-melenchon` et `bruno-retailleau` — **exactement les
deux cas qui ont motivé l'épic**. Les 21 autres profils que le premier relevé de
cette issue signalait (Larcher, Deroche, Procaccia, Guené, Raynal, Mazars…) sont
tous `roster_groupe`, donc hors périmètre.

### Ce que coûtait la généralisation, et pourquoi elle est écartée

L'issue supposait qu'« un 404 est bon marché ». **C'est faux sur cette source**,
et c'est ce qui achève de justifier la restriction.

Mesuré le 20/08/2026 entre 14:45 et 14:55 UTC, avec le `User-Agent` et le
`TIMEOUT=15` du projet, en 7 requêtes (courtoisie : quelques requêtes suffisent
à établir un coût unitaire, le reste s'extrapole) :

| requête | statut | durée |
| --- | --- | --- |
| `/gabriel-attal/json` | 404 | 9,25 s |
| `/aurore-berge/json` | 404 | 15,91 s |
| `/bruno-retailleau/json` | 200 | 12,62 s |
| `/bruno-retailleau/votes/json` | 404 | 8,99 s |
| `/gabriel-attal/votes/json` | 404 | 10,56 s |
| `/jean-luc-melenchon/json` | 200 | 14,98 s |
| `/gabriel-attal/json` (2ᵉ passage) | 200 (page générique) | 10,20 s |

Médiane **≈ 10,6 s**, min 8,99 s, max 15,91 s. Une requête `curl` sur la même
URL a mis **66,7 s**, dont **63,3 s de poignée de main TLS** — la latence n'est
pas dans le transfert, elle est dans l'établissement de connexion.

Coût **par candidat**, mesuré de bout en bout avec le vrai code
(`fetch_identity` + `fetch_votes`, mode d'extraction léger) : `gabriel-attal`
**21,1 s / 2 requêtes**, `aurore-berge` **17,7 s / 2 requêtes**. Deux requêtes,
pas une : l'identité *et* les votes sont demandés au Sénat.

Ces chiffres sont un **majorant d'un mauvais jour** — `www.nosdeputes.fr` a
répondu en 12,3 s puis dépassé 120 s dans la même fenêtre, toute
l'infrastructure Regards Citoyens était dégradée. Mais la forme tient : sur ces
domaines, une réponse négative se compte en **secondes**.

D'où la projection, sur le seul job qui n'utilise pas `--source`,
**`extract-roster-groupes`** (752 membres, 8 shards, ~94 par shard) :

| | par candidat | par shard (94) | pleine échelle (752) |
| --- | --- | --- | --- |
| bicaméral généralisé au roster | +19,5 s | **+30,6 min** | **+4 h 04** |
| bicaméral restreint aux candidats | **0 s** | **0 s** | **0 s** |

Les 19,5 s se décomposent en ~19 s de réseau et **0,5 s de temporisation de
courtoisie** : `process_candidat` ne temporise que si la source publique a
réellement été appelée (#467). Généraliser l'appel Sénat **rendrait cette
temporisation due pour chaque membre**, c'est-à-dire réinstallerait exactement
ce que #467 avait supprimé (12,0 s pour 24 membres). Un shard roster tourne en
~200 s, dont ~130 s de frais fixes : la version généralisée multipliait son
temps d'extraction par ~40.

**La restriction de périmètre ramène ce surcoût à zéro sur le roster**, et à
16 requêtes au total sur les 8 candidats à slug.

### L'index d'existence : construit, mesuré, retiré

Une première version chargeait le roster complet du Sénat
(`archive.nossenateurs.fr/senateurs/json` — **1 requête, 1 357 entrées,
1,09 Mo, 9,53 s**, historique compris) et n'appelait le Sénat que pour les slugs
qui y figurent. À 752 membres c'était le bon geste : ÷10 sur le surcoût, même
motif que #369, #392 et #403.

À 8 candidats, l'arithmétique s'inverse :

| | requêtes | temps |
| --- | ---: | ---: |
| sans index | 8 × 2 = **16** | ~2 min 36 s |
| avec index | 1 + 2 × 2 = **5** | ~48 s |

L'index fait gagner **1 min 48 s** — sur un chemin qu'**aucun job CI n'emprunte**
(voir ci-dessous). En regard, il coûtait ~60 lignes, un cache de module, un
verrou, une distinction `None`/`frozenset()` à ne pas confondre, un troisième
type de warning, et surtout **un mode de défaillance neuf** : index injoignable
⇒ Sénat non interrogé, silencieusement si le warning n'est pas relu. Une
collecte conditionnelle de plus, dans une issue qui existe parce qu'un chemin
conditionnel a fait disparaître un fait.

**Retiré.** Pour un candidat, les deux chambres sont interrogées, sans
condition. La mesure, elle, reste : c'est elle qui établit que la
généralisation au roster n'était pas finançable.

### Une correction au diagnostic : en CI, la boucle n'est pas seule à décider

`grep generate_all_profiles.py .github/workflows/generate-data.yml` :
**aucun job n'exécute la commande sans `--source` sur `raw_data/candidats.json`.**
`extract-an` passe `--source an`, `extract-senat` `--source senat`,
`extract-ue-officiel` `--source ue`, `merge-and-pivot` `--pivot-only` ; seul
`extract-roster-groupes` omet `--source`, et il travaille sur
`raw_data/roster_candidats.json`.

Autrement dit, **en CI un candidat est déjà interrogé sur les deux chambres**,
par deux jobs scopés distincts, dont les profils bruts se rejoignent à la fusion
additive — où `merge_raw_profile` fait `chambre = _prefer_non_empty(new, old)`.
La chambre publiée d'un candidat y dépend donc aussi de **l'ordre d'arrivée des
artifacts**, pas seulement de la boucle corrigée ici.

Cette PR ne prétend pas régler ce second chemin : il relève de la sous-issue D
(`chambre` dérivée plutôt que collectée). Elle règle le chemin par défaut —
`--source all`, celui de toute exécution locale et de la valeur documentée du
drapeau — et rend le cas bicaméral **nommé** partout où il se produit.

### Ce que le profil publie

Deux types de warnings dans `meta.warnings` — donc dans le jeu de données
publié, pas seulement dans un log de run. Même modèle que #474 : le texte avant
le premier `:` est le *type* agrégé par
`audit_pivot_dataset.compute_agregation_warnings`.

| type | quand | portée |
| --- | --- | --- |
| `carrière sur deux chambres` | les deux chambres rendent une identité ; nomme l'autre chambre et sa `source` | candidats (structurellement impossible ailleurs) |
| `collecte de chambre en échec` | une chambre a levé une exception ; nomme la chambre et la raison | **tous les profils** |

Le second n'est **pas** restreint aux candidats, et c'est délibéré. Il ne se
déclenche que sur une exception réelle — jamais en régime nominal, donc jamais
en volume — et il signale une `chambre` publiée qu'une panne a choisie à notre
place. `chambre` est lu par `group_profile`, `check_quality_gate` et le contrôle
de perte de #470 : le taire sur les 201 profils de roster rétablirait, pour eux,
le silence exact que cette issue corrige (AGENTS.md §2.5). C'est l'inverse du
cas #474, où ne rien émettre sur les 92 parlementaires en mission était juste
parce que leur exclusion est le comportement **attendu**.

Les deux cas que l'issue demandait de distinguer le sont : « aucune chambre ne
répond » reste le statut `introuvable` (déjà géré), « une échoue, l'autre
répond » produit le warning nommé.

### Quand les deux chambres répondent : convention d'ordre, dite explicitement

C'est le cas Retailleau, et il fallait bien écrire quelque chose dans `chambre`
tant que la sous-issue C n'a pas porté la chambre sur chaque mandat.

**La première chambre de `chambres` est retenue** — `deputes`, donc `chambre:
"AN"`. La valeur publiée ne change pas ; ce qui change, c'est qu'elle cesse
d'être muette : le profil dit qu'une identité existe des deux côtés, nomme
l'autre source, et dit que « AN » vient d'une **convention d'ordre de collecte**
et non d'une comparaison des mandats.

L'alternative — dériver la chambre du mandat en cours, ce qui ferait basculer
Retailleau sur `Senat` — a été écartée pour la raison même que l'épic énonce :
elle **effacerait sa carrière de député** comme on efface aujourd'hui son mandat
sénatorial. On remplacerait un fait faux par un autre.

### Le risque `group_profile`, instruit et mesuré : exposition nulle

`group_profile._member_eligibility_intervals` retient **tous** les
`mandat_electif` sans distinction de chambre, et `_is_eligible_at` est une
**union** d'intervalles. Un mandat sénatorial ajouté à un profil de membre
élargirait donc sa fenêtre d'éligibilité, et le compterait absent sur des
scrutins AN postérieurs à son départ de l'Assemblée. Le cas dangereux est
étroit — un mandat Sénat ne peut pas chevaucher un mandat AN (incompatibilité
constitutionnelle) — mais réel : **un changement de chambre en cours de
législature**.

Il faut pour cela un profil **à la fois candidat et membre d'un groupe publié**.
Mesuré sur les 7 groupes du corpus :

| candidat | groupe | `cohesion_votes` | connu du Sénat |
| --- | --- | ---: | --- |
| `gabriel-attal` | `groupe-AN-REN-16` | 4 099 | **non** |
| `marine-le-pen` | `groupe-AN-RN-16` | 3 405 | **non** |
| `jerome-guedj` | `groupe-AN-SOC-16` | 814 | **non** |
| `bruno-retailleau` | `groupe-Senat-LR` | **0** | oui |

**Exposition nulle**, pour deux raisons indépendantes :

1. les trois candidats dont le groupe a un dénominateur de cohésion réel ne
   sont **pas** connus du Sénat — aucun mandat sénatorial ne peut leur être
   ajouté ;
2. le seul bicaméral, Retailleau, appartient à un groupe sénatorial dont
   `cohesion_votes` vaut 0, et son unique `mandat_electif` publié
   (2004-09-26 → `null`) **est déjà** le mandat sénatorial.

Et surtout : **cette PR n'ajoute aucun mandat à aucun profil.** Le profil de la
seconde chambre est collecté puis abandonné ; seul un warning en sort. Le risque
appartient à la sous-issue C, celle qui fusionnera réellement les mandats des
deux chambres. Verrouillé par
`test_le_profil_de_lautre_chambre_nest_pas_fusionne`.

*(Un chiffre de 224 scrutins avait d'abord circulé sur Mazars : il était calculé
contre les 17 535 scrutins de l'index entier, alors que `cohesion_votes` est
strictement borné à une législature — `groupe-AN-SOC-16.json` ne contient que
des `an:16:*`, 814 entrées. Le risque réel est celui décrit ci-dessus, et il est
nul aujourd'hui.)*

### Interaction avec `build_minimal_profile`, signalée et non corrigée

Quand la collecte FR échoue entièrement et qu'un mandat européen existe,
`build_minimal_profile` écrit un squelette (`chambre: None`, `identite` à six
champs vides). #484 a montré la suite : la fusion additive garde l'ancienne
`chambre` non-null (`_prefer_non_empty`) tandis que le squelette, *truthy*,
écrase une `identite` réelle — la chambre est collante, l'identité ne l'est pas.

Cette issue **ne corrige pas cette asymétrie** (c'est #484), mais elle empêche
l'échec d'être muet : les warnings `collecte de chambre en échec` partent
désormais avec le squelette dans le profil brut. **Limite assumée** : sur ce
chemin `chambre` vaut `None`, donc le pivot est construit par
`normalize_europarl`, qui ne relit pas `meta.warnings` du brut. La trace
s'arrête à `raw_data/` dans ce cas précis.

### Le garde-fou de test qui manquait

L'index Sénat, dans sa première version, a fait entrer un appel réseau dans
**62 tests existants** sans qu'aucun n'échoue :
`tests/test_generate_all_profiles.py` est passé de 0,50 s à **13,4 s**,
exactement la pathologie que #473 avait supprimée. La règle « aucun test ne
touche le réseau » était **auditée une fois**, pas tenue.

D'où `tests/conftest.py` : une fixture `autouse` qui coupe
`requests.Session.send` — le point de passage de `requests.get`, `requests.post`
et de toute session construite ailleurs — et échoue en nommant l'URL. **La
boucle locale reste ouverte** : 11 tests de `test_amendements_download_modes`
montent un `http.server` sur `127.0.0.1` pour éprouver la reprise par `Range`
sur un vrai socket ; le critère est « sortir de la machine », pas « parler
HTTP ». Le sparse-checkout du workflow couvre l'autre moitié de la règle (le
corpus vivant absent du disque), celle-ci couvre le réseau.

<a id="deduplication-entrees-membres"></a>
## `membres[]` publiait deux fois le même fait : dédupliquer sans effacer les changements de portefeuille (#480) (2026-08-20)

Mesuré sur `main` à `3a8455a`, en reconstruisant les 10 rosters depuis
`pivot_data/profiles/` — donc **après** [[parlementaire-en-mission-nest-pas-ministre]] :
115 entrées `membres[]` pour 95 personnes, dont **2 entrées strictement
identiques** à une autre — `astrid-panosyan-bouvet` et `marc-ferracci`, mêmes
`membre_id`, `portefeuille`, `debut`, `fin`, `actif` **et** `source_url`, sous
Bayrou.

`build_gouvernement_roster` itère sur les mandats d'appartenance et, pour
chacun, sur les portefeuilles qui le chevauchent. Ces deux personnes portent
deux mandats d'appartenance au gouvernement Bayrou ; le même portefeuille
chevauche les deux, donc la même entrée sort deux fois.
`build_premier_ministre` faisait déjà ce raisonnement pour ses candidats
(« un mandat scindé produit des doublons, pas une ambiguïté ») ;
`build_gouvernement_roster` ne le faisait pas pour ses entrées.

### L'anomalie amont est dans la source, pas dans notre collecte

Le mandat non clos porte `actif: true` pour un gouvernement dont la période
publiée s'achève le 2025-09-09. Deux lectures étaient possibles, et la
correction n'aurait pas été la même : source AN incohérente (à tracer), ou
perte de la date de fin à l'extraction (bug de collecte, à corriger en amont).
**C'est la première**, vérifié dans le zip AMO30 lui-même
(`.cache/acteurs_historique_an/acteurs_historique.zip`, le 20/08/2026) :

| acteur | mandat AN (`uid`) | `organeRef` | `dateDebut` | `dateFin` |
| --- | --- | --- | --- | --- |
| PA795050 (Panosyan-Bouvet) | `PM15855880` | PO855052 | 2024-12-24 | 2025-09-09 |
| PA795050 | `PM15855061` | PO855052 | 2024-12-24 | **absent** |
| PA795884 (Ferracci) | `PM15855886` | PO855052 | 2024-12-24 | 2025-09-09 |
| PA795884 | `PM15855100` | PO855052 | 2024-12-24 | **absent** |

Deux `uid` distincts pour le même organe, la même `dateDebut`, la même
`preseance`, le même `infosQualite` — l'un clos, l'autre non. L'organe lui-même
déclare `viMoDe.dateFin: 2025-09-09` : le mandat jamais clos contredit son
propre organe. Notre extraction
(`candidate_profile._build_acteur_positions_hemicycle_index`) recopie
`dateDebut`/`dateFin` mandat par mandat, sans valeur par défaut ni fusion : elle
ne perd rien, elle reproduit fidèlement une source incohérente. Aucune issue de
collecte à ouvrir ; la déduplication en aval est la bonne correction, et elle
ne masque aucun défaut de chez nous.

### Dédupliquer strictement, jamais par `membre_id`

L'écart 115 → 95 **n'est pas un défaut** : `schema_gouvernement.py` prévoit
« un enregistrement par ministre et par période si changement de portefeuille ».
18 des 20 entrées surnuméraires sont des changements de portefeuille réels
(`david-amiel` sous Lecornu II, `gabriel-attal` sous Borne…). Une déduplication
par `membre_id` seul aurait ramené l'écart à 95 → 95 en effaçant 18 faits
vérifiables (§2.2) — l'erreur exactement inverse, et la plus coûteuse des deux.
Après correction : **113 entrées pour 95 personnes**. Les 10 rosters
reconstruits depuis `pivot_data/profiles/` (`main` à `3a8455a`, le 20/08/2026),
avant et après :

| gouvernement | entrées avant | entrées après | personnes |
| --- | ---: | ---: | ---: |
| FILLON 2 | 5 | 5 | 2 |
| FILLON 3 | 3 | 3 | 1 |
| PHILIPPE | 3 | 3 | 3 |
| PHILIPPE 2 | 9 | 9 | 8 |
| CASTEX | 14 | 14 | 12 |
| BORNE | 31 | 31 | 23 |
| ATTAL | 17 | 17 | 17 |
| BARNIER | 10 | 10 | 10 |
| **BAYROU** | **11** | **9** | 9 |
| LECORNU II | 12 | 12 | 10 |
| **TOTAL** | **115** | **113** | **95** |

Seul Bayrou bouge, de deux entrées : c'est la mesure qui prouve que la
déduplication n'a pas mordu sur les changements de portefeuille. Un
dénombrement par `membre_id` seul aurait ramené la colonne « après » sur la
colonne « personnes », ligne par ligne.

La déduplication porte donc sur l'**entrée entière**, pas sur une clé partielle.
Décidé de ne pas trancher un cas qu'on ne sait pas trancher : deux entrées
identiques sur les cinq champs d'identité (`membre_id`, `portefeuille`, `debut`,
`fin`, `actif`) mais de `source_url` différentes sont **conservées toutes les
deux, avec un warning**. Aucune n'est plus traçable que l'autre — dans le
pipeline actuel, `_source_url_portefeuille` retombe toujours sur l'URL du zip
AMO30 du mandat d'appartenance, donc les deux portent la même valeur et le cas
ne se présente pas — et en choisir une serait un arbitrage silencieux sur une
donnée non résolue (§2.5). Alternative écartée : dédupliquer sur les cinq champs
en gardant la première entrée ; c'est plus court, mais ça fait disparaître sans
bruit une divergence de source le jour où elle apparaît.

Le corollaire de [[test-adosse-au-corpus-vivant]] tient toujours : `membres[]`
dénombre des **entrées**, pas des personnes, et toute vue affichant « N
ministres » devra dédupliquer par `membre_id` à l'affichage. Le tableau de cette
entrée-là (116 entrées, Bayrou à 12) est celui de son époque : il précède #474
puis #480, qui ont retiré respectivement le portefeuille fantôme et les deux
répétitions.

<a id="perimetre-controle-perte"></a>
## Le périmètre du contrôle de perte : ce qu'il couvre, ce qu'il ne couvre pas (#470) (2026-08-20)

Le contrôle branché par #460 avant le commit de données ([[controle-de-perte-avant-commit]])
avait deux angles morts, et les deux ont laissé passer une perte réelle **alors
qu'il tournait** :

1. il ne lisait que `pivot_data/profiles`, jamais `groupes/`, `partis/`,
   `gouvernements/`, ni les index partagés `scrutins.json` et `amendements/` ;
2. il ne comparait que des **longueurs de listes**, si bien qu'un scalaire qui
   régresse lui était invisible.

Les deux pertes, reproduites depuis l'historique :

| perte | avant | après | vue par le contrôle |
| --- | --- | --- | --- |
| `groupe-AN-SOC-16` · `cohesion_votes` (`25f7bc7` → `a125e9e`) | 814 | **0** | non |
| `groupe-AN-SOC-16` · `mandats_agreges` | 44 | 23 | non |
| `groupe-AN-REN-16` · `mandats_agreges` | 1 032 | 646 | non |
| `parti` sur 3 profils (`e4d71cf` → `ffa24ec`) | renseigné | **null** | non |

La première n'est pas une fiche incomplète : c'est un **dénominateur publié
devenu faux** (AGENTS.md §2.7). La seconde était invisible partout, y compris à
l'écran — `pivotAdapter` retombe sur `manifestEntry.parti`, issu de
`candidats.json` : la donnée publiée était fausse et l'affichage restait juste.

### Le périmètre, désormais explicite

Un périmètre tacite se croit complet ; celui-ci s'énonce, dans le module, dans
le rapport Markdown produit à chaque run, et ici.

| couche | listes bloquantes | listes signalées | scalaires surveillés |
| --- | --- | --- | --- |
| `profiles` | `votes`, `mandats`, `textes_portes`, `interventions`, `tags_thematiques`, `dossiers_legislatifs` | `amendements`, `sources` | `id`, `nom`, `chambre`, `parti`, `groupe`, `identite`, `meta.provenance` |
| `groupes` | `membres`, `cohesion_votes`, `mandats_agreges`, `tags_thematiques_agreges`, `historique_noms` | `sources` | `groupe_id`, `groupe_sigle`, `groupe_nom`, `chambre`, `legislature`, `periode.debut`, `meta.couverture_roster.roster_total` |
| `partis` | `candidats`, `tags_thematiques_agreges` | `sources` | `parti_id`, `parti_nom` |
| `gouvernements` | `membres`, `textes` | `sources` | `gouvernement_id`, `nom`, `premier_ministre`, `periode.debut` |
| `scrutins.json` | — | `scrutins` | `schema_version`, `licence_donnees` |
| `amendements/` | — | `amendements` | `schema_version`, `legislature`, `licence_donnees` |

Trois familles de constats **bloquent** : un fichier disparu, une baisse sur une
liste bloquante, un scalaire surveillé passé de renseigné à `null`.

### De quel côté chaque arbitrage penche, et pourquoi

Ce contrôle décide si un commit de données part. Un faux positif bloque la
publication de données saines ; un faux négatif laisse passer une perte. Chaque
choix a donc été instruit contre l'historique réel — les 13 transitions
committées entre le 16 et le 20/08/2026 — et non contre une intuition.

**Scalaire `renseigné → null` : bloquant.** 10 occurrences sur ces 13
transitions, **10 défauts réels**, aucun faux positif — les quatre `parti`
écrasés par la passe roster-driven, les trois `parti` des restaurations de
#460/#465, deux `identite`, un `groupe`. Le contrat de fusion l'interdit déjà
explicitement (AGENTS.md §3 : « Scalars: new value if populated, else keep old
— **never regress to null** ») : une régression vers `null` est une violation de
contrat, jamais un fait mesuré (règle §2.5).

**Changement de valeur d'un scalaire : signalé, non bloquant.** 129 occurrences
sur les mêmes transitions, quasi toutes légitimes : normalisations (`'REN'` →
`'Renaissance'`, `'LREM'` → `'Ensemble pour la République'`), accents
(`'Edouard Philippe'` → `'Édouard Philippe'`), bascules de source
(`nosdeputes` ↔ `nossenateurs`, et le `chambre` qui suit), `meta.provenance` qui
alterne `candidat_declare` / `roster_groupe` selon l'ordre des passes. Bloquer
là-dessus interdirait presque tous les commits de données. **Faux négatif
assumé** : un changement suspect — Mélenchon passant de `AN` à `Senat` — est
relevé dans le rapport, à charge de relecture humaine. C'est le seul endroit du
contrôle où la décision revient à un lecteur.

**Index partagés : signalés, non bloquants.** Une baisse du nombre d'entrées
distinctes serait grave — « an uncommitted index leaves every mapping pointing
at nothing, silently » — mais elle est aussi le résultat attendu d'une
correction de clé, ce qu'ont fait #431 et #432. Or ce sont des **totaux de
corpus**, pas des mesures par fiche : les rendre bloquants forcerait l'opérateur
à relancer avec `tolerer_pertes_profils=true`, qui désarme du même coup les
contrôles **précis** par profil et par groupe. Bloquer sur le compteur le plus
grossier pour faire taire les plus fins serait le pire des échanges. La
**disparition** d'un fichier d'index, elle, reste bloquante : elle n'a aucune
explication légitime.

**`sources` : signalé, non bloquant.** Son historique montre des baisses
(16 → 15, 4 → 3, 3 → 2) qui accompagnent tantôt une perte réelle, tantôt une
sous-collecte non rejouée. Quand elle accompagne une perte réelle, le champ qui
la cause vraiment bloque déjà.

**`membres` d'un groupe : bloquant, mais pas `effectif.actuel`.** Le premier est
un enregistrement dont la disparition est une perte ; le second compte les
membres **actifs** et baisse légitimement quand un élu quitte le groupe.

### Trois erreurs dans le diagnostic de l'issue, corrigées

- **`votes_source` n'existe pas dans le pivot.** L'issue le cite parmi les
  « autres scalaires exposés ». Mesuré sur les 209 profils de `3a8455a` et sur
  7 refs de l'historique : la clé n'apparaît nulle part. C'est un champ de
  `raw_data/profiles` (`candidate_profile.py`), que la passe pivot ne reporte
  pas. Non surveillé, donc.
- **`dossiers_legislatifs` est inerte pour la même raison** — il figurait dans
  les champs stables depuis l'origine et ne pouvait jamais se déclencher :
  aucun pivot ne porte cette clé, `normalize_nosdeputes` la verse dans
  `textes_portes`. Conservé (il couvre `--profils-dir raw_data/profiles`), mais
  il ne faut pas le compter comme une protection.
- **La perte de `parti` ne date pas de `a125e9e^`**, comme l'écrit
  [[mandat-electif-perdu-fausse-le-denominateur]]. `a125e9e` **et** `e4d71cf`
  portent encore les trois `parti`. La régression est entrée en `ffa24ec` — la
  première des deux restaurations — et a été corrigée en `e82406a`. Le
  mécanisme décrit reste juste ; c'est la datation qui était fausse.

Et un angle mort que l'issue ne nommait pas : **`tags_thematiques` n'était
surveillé nulle part**. C'est un champ publié (AGENTS.md §6), passé de 647 à 0
dans le run que #460 documente — le rapport de #460 le comptait dans ses dégâts
sans que le contrôle le regarde. Il rejoint les listes bloquantes.

### Ce que le contrôle étendu trouve dès sa première exécution

Passé sur `25f7bc7` → `3a8455a`, il signale une perte **toujours présente dans
le corpus** : `jean-luc-melenchon.pivot.json` · `identite`, un bloc renseigné en
`25f7bc7` et `null` depuis `a125e9e`. Personne ne l'avait vue — c'est
exactement la classe de défaut que #470 décrit, et elle n'est pas corrigée ici :
c'est une donnée à restaurer, pas un défaut d'outil, et la mêler à l'extension
du contrôle mélangerait deux sujets. Consignée pour qu'elle ne se reperde pas.

### Le dimensionnement, qui était le vrai risque

Ce script tourne **avant** le commit : s'il meurt, rien n'est publié, et un
garde-fou qui meurt est pire qu'un garde-fou absent — il donne une assurance
qu'il ne tient pas. Il s'est déjà fait tuer par l'OOM killer une fois
([[controle-de-perte-avant-commit]]).

Mesuré sur le corpus réel (`3a8455a`, 209 profils, `--ref HEAD`, même machine,
`/usr/bin/time -v`, médiane de trois exécutions) :

| | durée | RSS max |
| --- | --- | --- |
| avant — profils seuls | 2,79 s | 133,4 Mio |
| **après — 5 couches + 2 index** | **4,74 s** | **184,8 Mio** |
| après, `--seulement-profils` | 2,89 s | 133,4 Mio |

Sous les 236 Mio que #460 avait actés, pour six collections au lieu d'une. La
troisième ligne isole le coût : à périmètre égal, la réécriture ne coûte rien —
tout l'écart vient des cinq collections ajoutées. Deux règles y suffisent :

- **un seul document en mémoire à la fois**, jamais le corpus — la lecture en
  flux du `git cat-file --batch` de #460 sert désormais toutes les collections ;
- **les `*.cosignatures.json` ne sont jamais ouverts.** Mesuré fichier par
  fichier, `15.cosignatures.json` coûte à lui seul **222 Mio** de RSS à parser,
  plus que tout le reste du contrôle réuni, pour 25,7 Mo sur disque. Aucun
  consommateur ne les lit (AGENTS.md §3). Ils sont **listés** — donc leur
  disparition, le seul cas catastrophique, est détectée gratuitement — mais
  jamais rapatriés : le `--batch` ne les demande même pas.

Le motif d'exclusion est **négatif** (`*.cosignatures.json`) et non positif :
`fnmatch` laisse `*` traverser le point, si bien qu'un `[0-9]*.json` censé ne
retenir que `14.json` attraperait aussi `14.cosignatures.json`. Écrit dans
l'autre sens, l'économie de mémoire aurait été silencieusement annulée.

Les index n'ont d'ailleurs **pas** vocation à grossir avec le corpus : leurs
207 238 amendements distincts sont déjà le chiffre de pleine échelle
d'AGENTS.md — ils sont construits à partir des archives AN figées, pas des
209 membres actuels. Le passage à 752 membres n'y changera rien.

### Ce que le contrôle ne couvre toujours pas

Énuméré ici *et* dans le rapport produit à chaque run, parce qu'un périmètre
qu'on ne dit pas se croit complet :

- ~~**l'intégrité référentielle** entre un `votes[].scrutin_id` d'un profil et
  `pivot_data/scrutins.json`, ou entre un `amendements[].amendement_id` et son
  index~~ — **comblé par #485**, voir [[integrite-referentielle-pivot]].
  `src/audit_integrite_referentielle.py` tourne dans `merge-and-pivot`, juste
  après ce contrôle-ci et avant le commit, et couvre les trois renvois de
  `pivot_data/` (`votes[].scrutin_id`, `cohesion_votes[].scrutin_id` d'un
  groupe, `amendements[].amendement_id`). Ce contrôle-ci ne le couvrira jamais,
  et c'est structurel : il compare un **avant** et un **après**, quand
  l'intégrité référentielle est une **invariance dans un état donné** — deux
  couches régénérées de façon cohérente-mais-fausse ne bougent aucun compteur.
  Deux contrôles complémentaires, avec **deux tolérances cloisonnées** :
  `tolerer_pertes_profils` ne désarme pas `tolerer_references_orphelines`, et
  réciproquement. La raison invoquée ici — « il faudrait tenir les deux
  ensembles de clés en mémoire simultanément » — était **fausse** : il n'en faut
  qu'un, le petit, et le côté référençant se parcourt un document à la fois ;
- **le contenu des entrées d'une liste** : seule leur cardinalité est comparée.
  Un `votes[]` dont toutes les positions basculeraient à `null` passerait ;
- **le contenu d'un scalaire de type bloc** (`identite`, `premier_ministre`) :
  seule sa présence est comparée ;
- **le contenu des `*.cosignatures.json`**, pour la raison de mémoire ci-dessus ;
- **`amendements_agreges` d'un groupe**, `comptages` d'un gouvernement,
  `effectif` : des compteurs dérivés, qui bougent légitimement dans les deux
  sens et dont les listes amont sont déjà surveillées ;
- **le changement de valeur d'un scalaire**, non bloquant par choix (ci-dessus).

### Les tests sont adossés aux pertes réelles

`tests/test_audit_diff_agregats.py` rejoue les deux pertes depuis des fixtures
figées (`tests/fixtures/audit_diff_pertes_reelles/`, provenance dans
`meta.fixture`, sur le modèle de `tests/fixtures/gouvernement_roster/`), jamais
depuis le corpus vivant — absent du disque en CI ([[ci-tests-pytest]]). Les
listes y sont réduites à leur cardinalité, seule chose que le contrôle lise :
les 814 entrées réelles de `cohesion_votes` pèsent 1,3 Mo dont pas une n'est
lue.

Deux tests portent la démonstration plus que les autres :
`test_le_perimetre_d_avant_470_etait_aveugle_a_la_perte_soc16`, qui applique
l'ancien périmètre aux fixtures de groupe et ne relève rien, et
`test_ce_run_ne_perdait_aucune_liste_et_passait_donc_inapercu`, qui montre que
sur le run où `parti` a disparu **toutes** les listes ne faisaient que croître —
`jean-luc-melenchon` y regagnait 1 016 votes et 18 721 amendements. Un contrôle
de longueurs de listes y voyait un run exemplaire.

<a id="fenetre-historique-donnees"></a>
## Borner l'historique de données : ce que ça rend vraiment, et quand (#434) (2026-08-20)

Décision : **option D**, borner l'historique de données plutôt que son contenu.
Variante retenue : **squash déclenché par la mesure, fenêtre de 30 commits de
données**, jamais de réécriture automatique. Rien à exécuter aujourd'hui — le
dépôt porte 23 commits de données, la fenêtre n'est pas contraignante.

Ce qui suit est mesuré sur un **clone** du dépôt (`git clone --mirror
--no-hardlinks`), `main` = `0466957`, le 20/08/2026 à 12:00. Aucune mesure n'a
été prise sur l'arbre de travail réel, et aucun historique réel n'a été
réécrit.

### Le dépôt pèse trois chiffres différents, et un seul compte

| mesure | valeur |
| --- | --- |
| `.git` sur disque | 853 Mo |
| `git rev-list --disk-usage --objects --all` | 386 Mo |
| **après `gc --prune=now`** | **284 Mo** |
| annoncé par l'API GitHub (`repos/…/.size`) | 395 Mo |

Les 853 Mo ne sont pas de l'historique : 569 Mo sont des objets **devenus
inaccessibles** par les rebases et les pushs forcés de la journée. Et
`rev-list --disk-usage` lui-même surestime — il additionne la représentation
*actuelle* de chaque objet, répartie sur 12 packs mal compactés. Le seul
chiffre comparable aux seuils GitHub est celui d'après repack : **284 Mo**,
soit 5,5 % du seuil recommandé de 5 Go.

L'écart avec les 395 Mo annoncés par GitHub est le même phénomène, côté
serveur : 111 Mo (39 %) de résidus que nous ne pouvons pas faire ramasser.
GitHub annonçait 275 Mo dans un commentaire de #434 la veille ; la hausse de
120 Mo en une journée n'est pas de la donnée, c'est le prix des pushs forcés
déjà faits.

### La contrainte annoncée n'existe pas, et c'est la principale correction

Le dimensionnement de la fenêtre devait être choisi **pour
`audit_diff_profils.py`**, au motif qu'il « compare à une ref git » et qu'une
fenêtre trop courte le priverait de point de comparaison.

**Lu dans le code, il ne dépend d'aucune profondeur d'historique.** Il fait
`git ls-tree --name-only <ref>:<répertoire>` puis `git cat-file --batch` sur
`<ref>:<répertoire>/<fichier>` : il lit **un arbre**, celui de la ref, et rien
d'autre. Aucun parcours de commits, aucun `log`, aucun `diff`. Avec
`--ref HEAD` — le choix fait en #461, et le seul juste hors `main` — il lui
faut exactement **un commit**.

C'est cohérent avec le reste : aucun `fetch-depth` n'est fixé dans
`generate-data.yml`, donc les 9 `actions/checkout` du workflow clonent déjà à
la **profondeur 1**. Le garde-fou qui aurait attrapé l'effacement des 789
interventions tourne aujourd'hui sur un clone d'un seul commit. Aucune fenêtre
≥ 1 ne peut le priver de quoi que ce soit.

Les trois mécanismes défendus dans #434 se vérifient de la même façon, et
tiennent :

| mécanisme | ce dont il dépend réellement |
| --- | --- |
| fusion additive (`merge_raw_profile`) | `json_path.exists()` puis lecture du fichier |
| `--skip-existing` | `json_path.exists()` |
| `--refresh-existing` (`_select_existants`) | `(out_dir / f"{slug}.json").exists()` |
| `build_scrutins_index.py` | `--profils-dir raw_data/profiles` au HEAD |
| `build_amendements_index_pivot.py` | `--profils-dir raw_data/profiles` au HEAD |

**Présence du fichier au HEAD, jamais profondeur d'historique.** C'est ce qui
rend l'option D viable, et ce n'est pas une supposition.

### Ce qui dimensionne vraiment la fenêtre : la latence de détection

Reste un consommateur réel de profondeur : la **restauration après incident**.
#463 et #464 ont utilisé `git show a125e9e^:…` et `git show e4d71cf^:…` —
respectivement le 2e et le 1er commit de données depuis le sommet. C'est peu,
mais c'est le mauvais chiffre à retenir : ce qu'il faut couvrir n'est pas la
profondeur des incidents passés, c'est le **délai avant qu'on les remarque**.

Deux mesures :

- **cadence de pointe : 4 commits de données par jour** (18/08 et 19/08/2026) ;
- **latence de réparation de l'incident le plus grave** : `a125e9e` committé le
  19/08 à 19:32Z, interventions restaurées le 20/08 à 08:32Z — 13 h. Et la
  réparation n'était pas finie : le 20/08 à midi, `#468` puis `#469`
  restauraient encore des mandats, des textes portés, puis un parti effacé par
  les restaurations elles-mêmes. Le sillage forensique d'un incident se compte
  en jours, pas en heures, et il est itératif.

D'où la règle : **fenêtre = cadence de pointe × période sans surveillance**.
4 × 7 jours = 28, arrondi à **30**. Une semaine d'absence, à la cadence la plus
forte jamais observée, reste réparable.

À pleine échelle (752 profils), cette fenêtre plafonne le dépôt à environ
**2,9 Go** — socle projeté 457 Mo + 30 × 81 Mo de coût moyen par run. Sous le
seuil recommandé, avec de la marge. C'est ça, l'objet de l'option D : un
plafond, pas un gain.

### Le coût par run : c'est la distribution, jamais la moyenne

Sur les 8 runs les plus récents :

| | Mo |
| --- | --- |
| médian | 12,6 |
| moyen | 20,2 |
| minimum | 0,2 |
| maximum | 53,5 |

**Un facteur 4 entre la médiane et le maximum.** Les deux runs chers
(`a125e9e`, `25f7bc7`) sont des propagations en `--no-merge`, structurellement
exceptionnelles. Une moyenne seule dimensionnerait la fenêtre sur un run qui
n'existe pas.

Et la distribution ne porte **que** sur les runs récents. Étendue aux 23
commits de données, la médiane tombe à 2,6 Mo et l'écart min/max grimpe à
× 1 790 — parce que les plus anciens décrivent un corpus de 14 à 30 profils.
Un chiffre qui ne décrit aucun run existant.

### Le gain réel, mesuré variante par variante

Taille du dépôt après réécriture *et* `gc --prune=now`, sur le clone :

| fenêtre | 0 | 1 | 2 | 3 | 4 | 6 | 8 | 10 | 15 | 20 | 23 (tout) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| dépôt | 127 | 169 | 175 | 218 | 246 | 258 | 259 | 280 | 280 | 283 | **284** Mo |

**La courbe sature à partir de ~10.** Tout ce qui précède le 10e commit de
données vaut moins de 2 % du dépôt : ces commits ont été écrits quand le corpus
faisait 14 à 30 profils. À 23 commits de données pour une fenêtre de 30,
**l'opération ne retirerait rien aujourd'hui**.

D'où l'écartement des variantes, sur mesure et non sur principe :

- **Fenêtre glissante appliquée à chaque run** — écartée : gain mesuré nul
  aujourd'hui, pour un push forcé par run. Le rapport risque/bénéfice est le
  pire des quatre.
- **Branche orpheline périodiquement écrasée** — écartée malgré le meilleur
  gain (127 Mo, −55 %). Elle détruit l'historique du **code**, donc `git log`
  et `git blame` sur `src/`, et les 27 SHA cités dans ce journal cessent de
  résoudre. Le journal de décision est la mémoire du projet ; l'échanger contre
  157 Mo est un mauvais troc.
- **Élagage des seuls répertoires de données dans les vieux commits** (garder
  tous les commits, retirer les blobs) — séduisante parce qu'elle préserve
  toute l'archéologie du code. Écartée pour deux raisons : elle exige
  `git-filter-repo`, absent de l'environnement, et la saturation ci-dessus
  borne son gain aux mêmes < 2 %. Elle change d'ailleurs tous les SHA elle
  aussi.
- **Squash déclenché par la mesure** — retenue. C'est la seule dont la
  fréquence s'ajuste au problème : elle ne s'exécute que quand la fenêtre
  devient contraignante *et* que le gain mesuré le justifie.

### Le piège du majorant : × 15 d'écart

La tentation est d'estimer le gain en additionnant ce qu'ont coûté les commits
hors fenêtre. C'est faux, et largement :

| fenêtre | somme des coûts par run | **gain réel mesuré** | écart |
| --- | --- | --- | --- |
| 10 | 93 Mo | **6 Mo** | × 15 |
| 3 | 254 Mo | **115 Mo** | × 2,2 |

La raison est structurelle : le squash conserve l'**arbre complet** à la
coupure, et les objets des commits retirés sont majoritairement des deltas dont
la base doit de toute façon être gardée. `audit_volumetrie_profils.py` publie
donc ce total sous le nom de *majorant*, avec l'avertissement à l'endroit exact
où on lit le chiffre — même correction qu'en
[[volumetrie-arbre-de-travail-nest-pas-depot]]. **Le seul gain fiable se mesure
en repackant un clone.**

### Trois pièges rencontrés en mesurant, tous silencieux

1. **`git replace --graft` ne suffit pas.** `main` porte des commits de merge
   dont le second parent plonge avant la coupure : greffer le seul commit de
   coupure laisse tout l'ancien historique atteignable par un autre chemin.
   Mesuré : 677 commits avant la greffe, 677 après. D'où le rejeu explicite qui
   remappe **tous** les parents (677 → 20 commits à la fenêtre 3).
2. **Les index bitmap sont calculés sur le graphe non greffé**, et `rev-list`
   les utilise en priorité. Sans `-c pack.useBitmaps=false`, la vérification
   rend le résultat d'**avant** la coupure sans rien signaler.
3. **Les autres refs ré-épinglent l'ancien historique.** Le dépôt local porte
   18 refs, GitHub 3 branches et 1 tag. Une branche oubliée annule tout le
   gain, en silence.

Un quatrième, pour qui vérifie : `git clone` sur un **chemin** local recopie le
répertoire d'objets tel quel, résidus compris. Il faut `--no-local` ou une URL
`file://` pour mesurer ce qu'un serveur sert réellement.

### Ce que l'opération coûte, et ce qu'elle ne rend pas tout de suite

Un push forcé ne libère rien tant qu'un `gc` n'a pas tourné, et **côté GitHub
on ne peut pas en déclencher un**. Mesuré sur un dépôt nu local :

| | |
| --- | --- |
| serveur, historique complet, `gc` fait | 284 Mo |
| après push forcé d'une fenêtre à 3 (169 Mo atteignables) | **284 Mo — inchangé** |
| après `gc --prune=now` | 169 Mo |

Mais il faut séparer deux choses, et la mesure les sépare nettement. Depuis le
**même serveur non ramassé**, un clone passé par le protocole git :

| | |
| --- | --- |
| serveur sur disque, sans `gc` | 284 Mo |
| **clone frais depuis ce serveur** | **218 Mo — déjà borné** |

`upload-pack` reconstruit le pack à partir des seuls objets **atteignables**.
Donc : le coût pour les consommateurs — clone, checkout CI, temps de fetch —
tombe **immédiatement** après le push forcé, sans attendre aucun `gc`. Ce qui
reste haut, c'est l'empreinte disque de GitHub et le `size` de son API, dont la
date de ramassage n'est ni annoncée ni déclenchable. Le « plafond » de l'option
D est donc réel pour le quota affiché, et **inexistant pour l'usage**.

Le reste du prix, lui, est immédiat et entier :

- **tous les SHA changent** à partir de la coupure, y compris ceux des commits
  conservés — leur ascendance change, donc leur hachage. Les 27 SHA cités dans
  ce fichier et ceux cités dans les issues cessent de résoudre. Archiver
  l'ancien `main` **ailleurs** est la seule parade : le garder en tag dans le
  même dépôt le rendrait atteignable, et le gain serait nul.
- **tout clone existant est invalidé.** Un `git pull` dessus recrée l'ancien
  historique et peut le repousser.
- **un push forcé ne doit jamais croiser un run de données** : le run
  committerait sur un historique qui n'existe plus.

### Pourquoi ce n'est pas automatisé

#434 demandait de peser l'automatisation, au motif qu'un squash manuel qu'on
oublie ne vaut rien. La mesure tranche dans l'autre sens.

Ce qui est automatisé, c'est la **détection** : `audit_volumetrie_profils.py`
dit désormais si la fenêtre est contraignante, avec la distribution du coût par
run et le majorant assorti de son avertissement. Ce qui ne l'est pas, c'est la
**réécriture**. Trois raisons, toutes constatées :

1. Les trois pièges ci-dessus produisent chacun un résultat **faux et
   silencieux** — un gain nul présenté comme un succès. Un script qui pousse en
   force sur la foi d'une telle mesure est plus dangereux que l'oubli qu'il
   corrige.
2. Le dépôt a de l'**activité concurrente** : pendant cette mesure, une autre
   session committait les restaurations de #468 et #469, et `origin/main` a
   avancé trois fois en une heure. Un `schedule:` qui pousse en force ne peut
   pas savoir qu'il écrase du travail en cours.
3. Le gain est **nul aujourd'hui**. Automatiser une opération irréversible pour
   qu'elle ne rende rien, ce n'est pas de la prévoyance.

`scripts/borner_historique_donnees.sh` est donc à deux modes, et **ne pousse
jamais** : `--mesurer` clone dans un répertoire temporaire et rend le gain réel
sans rien toucher ; `--preparer` écrit une branche locale et un tag de
sauvegarde, vérifie, puis affiche les commandes de push à exécuter à la main,
dans l'ordre, avec leurs points de non-retour.

La vérification qui compte tient en une ligne, et le script la fait :
**l'arbre du sommet doit être identique avant et après**. Un arbre git est un
hachage récursif de tout le contenu ; s'il coïncide, chaque fichier coïncide.
C'est une preuve, pas un sondage.

### Traçabilité (AGENTS.md §2.2) : aucun obstacle, et il faut le dire

La règle exige que **tout fait publié soit rattaché à une source primaire**.
Elle porte sur le chaînage fait → source, matérialisé dans `sources[]`,
`source_url` et les identifiants AN — tous **dans les fichiers**, au HEAD.

L'historique git de `raw_data/profiles` et `pivot_data/profiles` n'est pas une
source : ce sont des fichiers **dérivés**, reconstructibles depuis les APIs
publiques, et aucun champ publié ne référence un commit. Squasher les vieux
commits ne retire donc **aucun lien de traçabilité** : après l'opération, tout
profil au HEAD porte exactement les mêmes `sources[]` qu'avant — c'est ce que
prouve l'identité de l'arbre du sommet.

Ce qui est perdu est d'une autre nature : la capacité de **rejouer l'historique
d'un fichier dérivé** — de l'archéologie de pipeline, utile (c'est ce que #463
et #464 ont fait) mais qui ne relève pas de §2.2. C'est précisément ce que la
fenêtre de 30 protège, et c'est pour ça qu'elle est dimensionnée sur la latence
de détection.

**§2.2 ne fait pas obstacle à l'option D.** Je n'ai pas trouvé de lecture qui
conduise à l'inverse.

<a id="parlementaire-en-mission-nest-pas-ministre"></a>
## Le `label` d'un mandat `MINISTERE` ne dit pas si c'est un maroquin (#474) (2026-08-20)

`pivot_data/gouvernements/gouvernement-BAYROU.json`, sur `main` à `ea6f0d5`,
publiait ceci :

```json
{
  "membre_id": "nosdeputes:astrid-panosyan-bouvet",
  "portefeuille": "Ministère de l'économie, des finances et de la souveraineté industrielle, énergétique et numérique",
  "debut": "2026-02-04", "fin": null, "actif": true
}
```

dans un document dont la période se referme le 2025-09-09, `actif: false`.
Trois faussetés en un enregistrement : un portefeuille jamais détenu, une date
postérieure à la fin du gouvernement, un `actif: true` dans un gouvernement
clos. C'est une affirmation factuelle fausse publiée dans le jeu de données
(§2).

### Pourquoi le label ne suffit pas

`categorie == "fonction_gouvernementale"` réunit deux `typeOrgane` du zip AMO30,
et #398 avait établi que le label les sépare (voir
[[gouvernement-premier-ministre-portefeuille]]). C'est vrai pour cette
séparation-là — et seulement pour elle. La docstring de
`_est_mandat_appartenance_gouvernement` en tirait implicitement une seconde
conclusion, fausse : qu'un mandat `MINISTERE` soit un portefeuille.

Un **parlementaire en mission** (art. LO144) porte lui aussi un mandat
`MINISTERE`, et son label est l'intitulé du ministère **auprès duquel** il est
missionné. « Ministère de l'économie… » désigne alors le ministère d'accueil de
la mission, pas un maroquin. Sur ce seul critère, les deux sont **strictement
indiscernables** — la personne missionnée reste députée, elle n'est pas membre
du gouvernement.

Ce que le label ne dit pas, `mandats[].fonction` le dit : il reprend
`infosQualite.libQualite` de la source AN (`candidate_profile`, renommé `type`
→ `fonction` par `normalize_nosdeputes`). `gouvernement_roster.py` ne le lisait
nulle part. Répartition mesurée sur les 209 profils du dépôt au 2026-08-20 :

| `fonction` sur un mandat `MINISTERE` | Occurrences |
| --- | --- |
| **`en mission`** | **92** |
| `Ministre délégué` | 48 |
| `Ministre` | 43 |
| `Secrétaire d'État` | 18 |
| `Ministre d'État, ministre` | 4 |
| `Premier ministre` | 4 |
| `Garde des sceaux, ministre de la justice` | 2 |
| `Ministre d'État, Garde des Sceaux, ministre de la justice` | 1 |

43 % des mandats traités comme des portefeuilles n'en étaient pas. Une seule
attribution fausse était publiée, parce qu'il faut de surcroît un chevauchement
— mais le vivier est de 92 mandats pour 209 profils ; à 752, il dépassera 330.

### Liste blanche, pas liste noire

Exclure `"en mission"` aurait suffi à corriger le fichier publié. C'est
précisément le geste que §2.5 interdit : une liste noire traite toute valeur
non prévue comme un maroquin, c'est-à-dire pose une valeur par défaut sur une
donnée non résolue. Les 7 qualités ministérielles observées le sont sur 209
profils du corpus cible de ~752 : une 8e apparaîtra.

`FONCTIONS_MINISTERIELLES` est donc une liste blanche, et
`_qualite_portefeuille` rend **trois** états, pas deux :

- **ministérielle** → portefeuille retenu ;
- **non ministérielle** (`en mission`) → écarté **sans warning** : c'est
  l'exclusion attendue, 92 occurrences, un warning par occurrence noierait les
  vraies alertes ;
- **inconnue** → écarté **avec un warning** nommant la personne, l'intitulé et
  la qualité rencontrée.

L'inconnu ne plante pas le pipeline et ne disparaît pas non plus : le membre
reste dans `membres[]` avec `portefeuille: null`, et le warning remonte dans
`meta.warnings` du profil de gouvernement (`gouvernement_profile`), donc dans
le jeu de données publié — traçable, pas seulement affiché en CI. Le geste de
maintenance attendu est d'ajouter la valeur à
`FONCTIONS_MINISTERIELLES_OBSERVEES` après vérification humaine : même
principe éditorial que `raw_data/gouvernements_reels.json`.

*Coût assumé* : une qualité ministérielle légitime mais non encore listée fait
temporairement retomber un portefeuille réel à `null`. Une donnée manquante et
signalée, plutôt qu'une donnée fausse et silencieuse — c'est l'arbitrage
constant de §2.5.

*Normalisation* : la comparaison se fait sur casse et espaces normalisés
(`_normalise_fonction`). La source écrit déjà « Garde des sceaux » et « Garde
des Sceaux » pour la même qualité. Purement typographique : aucun rapprochement
par préfixe, aucune troncature — « Ministre » et « Ministre délégué » restent
deux qualités distinctes.

### Le second défaut : un mandat d'appartenance jamais clos

La qualité n'explique pas tout. Panosyan-Bouvet porte **deux** mandats
`Gouvernement (BAYROU)`, identiques en tout sauf leur fin :

```
fonction='membre' | 2024-12-24 -> 2025-09-09 | actif=False
fonction='membre' | 2024-12-24 -> None       | actif=True
```

Le second n'est jamais clos, alors que le gouvernement l'est depuis le
2025-09-09. `_portefeuilles_du_mandat` ne testait le chevauchement que contre
la période du **mandat** : un mandat sans fin accroche donc n'importe quel
mandat ministériel postérieur, indéfiniment. C'est ce qui a donné au
portefeuille fantôme de 2026 quelque chose à quoi s'accrocher.

Le chevauchement est désormais borné **aussi** par la période du gouvernement.
Le garde-fou de #398 — « un ministre entré en cours de mandature ne doit pas se
voir attribuer le portefeuille qu'il occupait avant » — reste entier : la
nouvelle condition est un ET, elle ne peut que restreindre, jamais rattraper un
portefeuille que la période du mandat écarte. Un test de non-régression le
vérifie explicitement (portefeuille antérieur chevauchant le gouvernement mais
pas le mandat : toujours exclu).

Cette borne rend par ailleurs structurellement impossibles les deux autres
faussetés du record : plus aucune entrée `membres[]` ne peut avoir un `debut`
postérieur au `fin` du gouvernement, ni être `actif` dans un gouvernement clos.

*Note* : #398 avait mesuré « aucun mandat `MINISTERE` ne déborde de la période
du mandat d'appartenance qu'il chevauche (0 cas sur 24) ». C'était vrai du
corpus d'alors. Le corpus a grandi, et le cas est apparu — illustration de la
raison pour laquelle une mesure sur corpus partiel ne fonde jamais un
invariant de code.

### `build_premier_ministre` : ce qui était en jeu n'était pas seulement un faux PM

Le même défaut y était latent, et plus grave. `nosdeputes:david-amiel` porte un
mandat de label **« Premier ministre »**, `fonction: "en mission"`, du
2024-01-12 au 2024-05-05 : une mission auprès de Matignon, pas Matignon. Sans
effet aujourd'hui — son seul mandat d'appartenance est postérieur (Lecornu II,
2025-10-13), donc aucun chevauchement.

Mais `build_premier_ministre` retourne `None` **avec un warning** quand
plusieurs candidats remplissent les conditions. Un missionné chevauchant
n'aurait donc pas seulement inventé un Premier ministre : il aurait *effacé* le
vrai. Le filtre de qualité amont l'écarte déjà ; la fonction exige en plus la
qualité exacte « Premier ministre », second verrou indépendant, pour qu'un
desserrement futur de la liste blanche ne rouvre pas ce chemin-là.

### Ce que la correction ne fait pas

Elle ne supprime **aucune donnée collectée**. Le mandat de parlementaire en
mission est un fait public et traçable : il reste dans `mandats[]` du profil,
un test le vérifie sur fixture figée. Ce qui est retiré, c'est une
**attribution** — l'entrée dans `membres[]` d'un gouvernement.

### Propagation aux fichiers déjà committés

`generate_gouvernement_profiles.py` réécrit intégralement
`pivot_data/gouvernements/*.json` à chaque run (`write_text`, jamais de fusion,
résultat entièrement déterministe à partir des pivots locaux). La correction se
propagera donc au prochain run réussi de `generate-data`, sans intervention.
Deux réserves à connaître :

- le garde-fou #427 : si une archive de dossiers législatifs manque, la
  fonction rend `COLLECTE_INCOMPLETE` et **aucun** profil n'est réécrit — le
  fichier fautif resterait alors en place ;
- `preserve_stable_freshness_timestamps` (#343) ne fige que `meta.genere_le` et
  `sources[].synchro_le` quand le contenu est par ailleurs identique ; un
  changement de contenu est toujours écrit.

D'ici là, `gouvernement-BAYROU.json` conserve l'entrée fausse : la correction
porte sur le code de dérivation, elle ne réécrit pas les données publiées.

### Défaut adjacent, hors périmètre

Le même mandat d'appartenance dupliqué produit aussi des **entrées `membres[]`
strictement identiques** : sous Bayrou, Panosyan-Bouvet et Marc Ferracci ont
chacun leur portefeuille réel publié deux fois. `build_premier_ministre`
déduplique ses candidats ; `build_gouvernement_roster` ne déduplique pas ses
entrées. Ce n'est pas une attribution fausse — c'est un doublon — et cela
touche au corollaire de [[test-adosse-au-corpus-vivant]] : `membres[]` dénombre
des entrées, pas des personnes. Laissé en l'état, à traiter séparément.

<a id="budget-execution-pleine-echelle-467"></a>
## Budget d'exécution à pleine échelle : 630 min annoncées, 55 mesurées (#467) (2026-08-20)

L'en-tête de `generate-data.yml` portait un budget de **210 min** en
configuration par défaut et **630 min (10 h 30)** en run complet. Ce chiffre
n'a jamais été confronté à un run. Il l'est ici : le run complet
`32288588518` du 19/08/2026 a duré **54,9 min**. Facteur d'écart : **×11,5**.

### 1. Pourquoi 630 était faux : une charge fixe multipliée par le nombre de shards

Le calcul sommait les `timeout-minutes`. Pour la matrice roster il écrivait
`S × 60`, soit 480 min à S=8. Or ces 8 shards se partagent une charge
**fixe** — sharder ne crée pas de travail, il le divise. Le timeout de 60 min
couvrait ~712 membres ; un shard en contient ~94. Écrire `8 × 60` supposait
5 696 membres à traiter, sur un roster de 752.

Le timeout avait été dimensionné pour le job **non shardé** ([[budget-roster-mesure]],
#376) et n'a pas été relu quand #394 l'a découpé. C'est le mode de défaillance
d'une valeur qu'on additionne au lieu de la lire : chaque terme était juste,
la somme ne voulait rien dire.

**Correctif** : l'en-tête distingue désormais le **plafond autorisé** (somme
des timeouts, filet de sécurité, jamais atteint) du **temps mur**, mesuré et
seul à budgéter. Les timeouts eux-mêmes sont laissés en l'état : ils ne coûtent
rien tant qu'ils ne sont pas atteints, et les rabaisser aurait échangé un
chiffre faux contre un risque réel.

### 2. Où passe réellement le temps : ce n'est pas le calcul, c'est le checkout

Décomposition d'un shard roster, relevée dans le log du run `32288588518` :

| poste | shard 0 | shard 7 |
| --- | --- | --- |
| `actions/checkout` (fetch du dépôt) | 117 s | 93 s |
| **extraction (24 membres)** | **63 s** | **67 s** |
| tout le reste (setup-python, pip, cache, artifact, construction du roster, publication, upload, teardown) | 25 s | 34 s |
| **total du job** | **205 s** | **194 s** |

**Les deux tiers d'un shard sont des frais fixes, et la moitié est un
`git fetch`.** À `max-parallel: 1`, sharder ×8 payait donc ~17 min de temps mur
pour zéro travail utile. C'est le poste que ni `--workers` ni aucune
optimisation de code ne touche.

### 3. La répartition du temps par candidat : 0 requête réseau

Mesure demandée par l'issue, faite en rejouant **la population exacte** du
shard 0 (ses 24 membres, mêmes options : `--skip-interventions
--skip-dossiers-legislatifs --workers 1`), cache AN chaud, cache amendements au
format `uid` shardé (matérialisé hors ligne depuis
`raw_data/amendements_an_figes/`, législatures 14/15/16 — la 17e n'est pas figée
et aurait exigé le réseau), en instrumentant `requests` et `time.sleep`.
Temps mur total : **74,1 s**, RSS de pointe **1 266 Mo** (à comparer aux
1 596 Mo relevés en CI sur le même shard — les deux environnements se
correspondent).

| poste | part du temps mur |
| --- | --- |
| relecture d'index locaux (`_extract_mandats_officiels`, dont `fetch_organe` 43,4 s) | 68,9 % (51,0 s) |
| temporisations de courtoisie (`time.sleep`) | 27,7 % (20,5 s) |
| lecture des amendements (`fetch_amendements_officiels`) | 8,6 % (6,4 s) |
| **réseau** | **0,7 % (0,52 s) — 1 requête HTTP pour 24 candidats** |

(Les deux premiers postes se recouvrent partiellement : les sleeps de
`_fetch_ue` s'exécutent en parallèle de la collecte FR.)

**Une requête HTTP pour vingt-quatre candidats**, vers
`data.europarl.europa.eu` (la liste des eurodéputés, téléchargée une fois par
process). **Zéro requête vers NosDéputés, zéro vers data.assemblee-nationale.fr.**
Depuis #369 un député trouvé dans le référentiel historique AN ne déclenche
aucun appel NosDéputés ; depuis #392 ses amendements et depuis #403 ses votes
viennent d'index locaux. La collecte roster n'est plus une opération réseau.

### 4. Ce que ça change, poste par poste

#### a. La relecture d'index : le vrai coût, et il était invisible

`fetch_organe` a été appelé **2 255 fois** pour ces 24 membres, et chaque appel
**rouvrait et reparsait** `.cache/acteurs_historique_an/index_organes.json`.
Les quatre index dérivés du zip AMO30 (identité, mandats, organes, positions
dans l'hémicycle) avaient un cache **disque** — qui évitait le
retéléchargement, jamais le reparsing.

C'est la troisième occurrence de la même pathologie au même endroit :
[[budget-roster-mesure]] (#376) l'avait trouvée sur les amendements (93 % du
coût par membre), #403 sur les scrutins. Elle survivait sur le référentiel des
acteurs.

**Correctif** : mémo intra-process, indexé par **chemin** d'index et non par
nom logique — chaque test patche `ACTEURS_HISTORIQUE_CACHE_DIR` vers son propre
`tmp_path`, et un mémo global leur ferait lire l'index du test précédent. C'est
exactement le piège qui avait fait reverter la mémoïsation de #377 ; une
fixture autouse purge en plus le mémo, ceinture et bretelles. L'objet rendu est
partagé, jamais copié (même règle que l'index amendements, AGENTS.md §5).

#### b. La temporisation de courtoisie : conservée, mais envers une source réellement appelée

`time.sleep(0.5)  # on reste courtois avec l'API publique entre deux candidats`
datait de l'ère NosDéputés. Mesurée, elle représentait **12,0 s sur 74,1 s de
temps mur** — et une fois la relecture d'index supprimée, la moitié de ce qui
restait : du travail passé à ménager une source qu'on n'interrogeait pas.

**Correctif** : `_get_payload` — chokepoint **exclusif** de
NosDéputés/NosSénateurs, l'Open Data AN ne passant jamais par lui — incrémente
un compteur ; `process_candidat` ne temporise que si le compteur a bougé
pendant le traitement du candidat. Un sénateur, un député absent du référentiel
AN ou une passe avec interventions continuent d'appeler NosDéputés, donc de
temporiser. Même principe pour le `time.sleep(0.3)` du volet européen, qui ne
se paie plus que pour un mandat effectivement trouvé.

*Pourquoi un compteur global et non thread-local* : les appels partent de
sous-pools (`_fetch_fr`/`_fetch_ue`, recherche d'interventions multi-domaines),
donc d'autres threads que celui qui traite le candidat. Le global rend la
mesure **conservatrice** avec `--workers > 1` : on peut temporiser à cause d'un
autre candidat, jamais s'en dispenser à tort. Le sens de l'erreur est celui de
la courtoisie.

*Alternative écartée* : supprimer la temporisation. Elle reste due — la mesure
dit qu'elle était payée au mauvais moment, pas qu'elle est inutile.

#### Résultat, sur la population exacte du shard 0

| | temps mur | par membre | RSS max |
| --- | --- | --- | --- |
| avant | 74,1 s | 3,09 s | 1 266 Mo |
| après | **9,8 s** | **0,41 s** | 1 287 Mo |

**−86,8 %**, sans dégradation mémoire (le mémo remplace une allocation
transitoire par membre par une allocation unique ; +21 Mo, soit +1,7 %).
Après correctif, le poste dominant n'est plus la relecture d'index mais la
lecture des amendements (5,7 s des 9,8 s), c'est-à-dire du travail utile.

**Projection en CI** — le même shard y coûtait 63,1 s pour 24 membres, soit
~1,9 s par membre : la mesure locale part d'une base ~1,6× plus lente, donc
transposer le rapport donne **≈ 0,5 s par membre** en retenant une marge pour
la 17e législature, absente du cache local. À pleine échelle (94 membres par
shard) l'extraction passerait de ~3,2 min à **~1 min**. Projection, pas mesure.

### 5. `max-parallel` : la condition de réouverture de #412 était remplie

[[concurrence-shards-extraction-412]] avait écrit sa propre condition :

> *À rouvrir si §3 se confirme et que le run complet devient la norme.*

§3 confirmée par [[cache-cle-amendements-separee]] (#424), run complet devenu la
norme au passage à pleine échelle. Les deux arguments qui restaient à #412 sont
tombés à la mesure — mais **pour la matrice roster seulement** :

- **Cache** : les shards roster ne se passent rien. Le `needs:` de ce job
  garantit que `public-data-cache-an-*` est déjà écrite par `extract-an` quand
  la matrice démarre. Log du run `32288588518` : `Cache hit occurred on the
  primary key public-data-cache-an-2026-W34, not saving cache` sur **tous** les
  shards roster, entrée de **21 Mo** restaurée en **1,1 s**. Chaque shard
  restaure la même entrée immuable. Sérialiser ne réchauffe rien.
- **Prudence réseau** : profil mesuré d'un shard = 2 requêtes NosDéputés
  (construction du roster) + 1 requête `data.europarl.europa.eu` + **0 par
  candidat**. Quatre shards simultanés, c'est 8 requêtes au lieu de 2, une fois
  par run.

**Décision : `max-parallel: 4` sur `extract-roster-groupes`.**

**`extract-an` reste à `max-parallel: 1`**, et l'asymétrie est le cœur de la
décision : ses shards **écrivent** réellement la clé de la semaine (le premier
sauvegarde, les suivants font un exact key hit) — la chaîne de réchauffement y
existe, c'est ce que #424 a réparé. Le job roster démarre derrière lui : sa clé
est déjà chaude. Le même `max-parallel: 1` recouvrait deux situations
différentes ; une seule le justifiait.

*Pourquoi 4 et non 8* : en `fresh_run=true` les steps de cache sont sautés et
chaque shard retélécharge ~40 Mo d'archives AN (acteurs historiques 13,6 Mo +
scrutins XVII 26,3 Mo, `content-length` relevé le 20/08/2026). 4 borne cette
rafale à la moitié pour ~3 min de temps mur en plus à pleine échelle. Ce dépôt
a déjà documenté trois modes de défaillance de l'AN (#443) ; on ne va pas les
provoquer pour trois minutes.

*Ce qui reste une projection* : `max-parallel` ne se teste pas en local. La
mesure porte sur le profil réseau et sur le comportement du cache ; le gain de
temps mur (~23 min → ~6 min à pleine échelle) est déduit des durées de shard
observées, pas observé.

### 6. Ce que le cache AN protège encore : deux répertoires sur quatre

L'issue demandait de chiffrer les quatre répertoires listés dans le `path:` du
job. Relevé le 20/08/2026 :

| répertoire | poids local | téléchargement évité | lu par le job roster ? |
| --- | --- | --- | --- |
| `.cache/scrutins_an` | 89 Mo | **26,3 Mo** (XVII seule — XIV/XV/XVI sont figées et committées) | oui |
| `.cache/acteurs_historique_an` | 35 Mo | **13,6 Mo** | oui |
| `.cache/syceron_an` | 39 Mo | — | **non** (`--skip-interventions`) |
| `.cache/questions_an` | non matérialisé | — | **non** (`--skip-interventions`) |

L'entrée de cache réellement restaurée par un shard roster pèse **21 Mo**
(`Cache Size: ~21 MB`, log du run) : elle ne contient donc, de fait, que ce que
`extract-an` a matérialisé.

Le job cache donc deux répertoires qu'il ne lit jamais. **Laissé en l'état** :
`tests/test_ci_cache_paths.py` exige que `extract-an` et
`extract-roster-groupes` cachent **exactement le même ensemble**, précisément
pour qu'aucun des deux ne re-télécharge ce que l'autre a persisté (#424).
Resserrer le `path:` du seul job roster casserait cette invariance pour
économiser une restauration de cache de 1,1 s. Le vrai chiffre est là :
**39,9 Mo** par shard en cas de cache froid, pas les 163 Mo que suggère la
taille sur disque.

### 7. Le troisième levier : découpage proportionnel, et pourquoi `TOTAL=1`

`prepare-roster-matrix` force 1 seul shard dès que `roster_extraction_limit`
est non nulle. C'était le seul endroit du fichier où une décision n'était pas
argumentée. Elle l'est maintenant, et la raison est **sémantique, pas de coût** :
dans `generate_all_profiles.main()`, `--shard` s'applique **avant** `--limit`,
donc la limite vaut par shard. `limite=100` sur 8 shards ne traiterait pas 100
candidats mais jusqu'à 800 — on demanderait un lot, on en obtiendrait huit.

*Alternative examinée et écartée* — découper quand même, en 8 tranches de
`limite/8`, pour paralléliser le rollout progressif :

- **Ce n'est pas un levier distinct de `max-parallel`** : il signifie
  exactement la même chose côté réseau, huit jobs roster simultanés frappant
  les mêmes sources. C'est une variante, pas une alternative.
- **Le lot cesse d'être exact.** La sélection progressive de #224 prend d'abord
  les non couverts, qui ne sont pas répartis uniformément (#445 : 24, 24, 28,
  27 couverts selon le shard). On demanderait 100 et on obtiendrait 70 ou 80,
  sans savoir lesquels à l'avance.
- **Le gain a fondu.** Un shard coûte ~130 s de frais fixes pour une extraction
  tombée à ~0,3 s par membre : découper un lot de 100 ferait payer huit fois
  ces frais fixes pour économiser ~1 min de temps mur.

Le nombre effectivement traité, lui, est **déjà** rapporté par
`_select_candidats_couverture` — `Sélection progressive + rafraîchissement : X/Y
candidat(s) retenu(s) (N non couvert(s), M périmé(s))` — par shard, dans le log
du job. Rien à ajouter de ce côté.

### 8. `--workers` : maintenu à 1, mais plus pour la raison écrite

Le second verrou de l'issue. Sa justification était la courtoisie ; celle-ci est
désormais portée par la temporisation conditionnelle, pas par la sérialisation.
Ce qui maintient 1 :

- **Le parallélisme inter-candidats ne fait pas gagner de temps ici : il en
  coûte.** Mesuré sur les 24 membres, cache amendements réel :

  | | `--workers 1` | `--workers 4` |
  | --- | --- | --- |
  | avant #467 | 74,1 s | **94,6 s** (+28 %) |
  | après #467 | 9,8 s | **13,8 s** (+41 %) |

  Dans les deux états. La charge est du parsing JSON sous GIL, sérialisé de
  surcroît par les verrous par législature (`_get_amendements_lock`,
  `_ACTEURS_*_LOCK`) : quatre threads ne font que se disputer le même
  interpréteur. Le mode dont l'input parle — « candidats traités
  simultanément » — décrit une charge réseau qui n'existe plus.
- **Le RSS de pointe monte** (1 281 → 1 374 Mo en local ; 1 596 Mo mesuré en CI
  à `--workers 1`), sur un job déjà exposé à l'OOM (#377). Payer de la mémoire
  pour perdre du temps serait un mauvais échange deux fois.
- **L'input est partagé** avec `extract-senat` et `merge-and-pivot`, et le
  Sénat, lui, est réellement borné par NosDéputés. L'augmenter changerait deux
  profils de charge à la fois — exactement ce que #412 refusait de faire.

### Limites assumées de cette mesure

- **Faite en local**, comme [[budget-roster-mesure]] et pour la même raison.
  Elle est ancrée sur un point CI réel — la population exacte du shard 0 et sa
  durée mesurée en CI (63,1 s) — mais le poste dominant est CPU/disque, pas
  réseau : la transposition porte sur un rapport, pas sur une valeur absolue.
- **Cache chaud.** Le cas froid (`fresh_run=true`) n'a pas été mesuré, seulement
  chiffré en volume (39,9 Mo par shard, `content-length` relevé à la source).
- **17e législature absente du cache amendements local.** Elle n'est pas figée,
  la matérialiser aurait exigé de retélécharger 676 Mo à l'AN. Les mesures
  couvrent donc 3 législatures sur 4 côté amendements — c'est ce qui justifie
  la marge prise dans la projection à 0,5 s par membre. Premier constat de
  cette limite : le cache local était au format plat hérité de #377, donc
  `fetch_amendements_officiels` y répondait « index absent » et la phase
  n'apparaissait pas du tout dans une première série de mesures. Une phase qui
  échoue proprement se lit comme une phase rapide.
- **`max-parallel` n'est pas testable en local.** Le gain de temps mur est
  déduit des durées de shard observées, pas observé.
- **`merge-and-pivot` à 752 profils reste l'inconnue.** 7,5 min mesurées à 209
  profils ; rien ne dit comment ce job se comporte à 752, et c'est désormais le
  poste le moins connu du budget. Le premier run complet réel tranchera.

---

<a id="ci-tests-pytest"></a>
## Un job CI exécute la suite de tests : audit préalable et arbitrages (#473) (2026-08-20)

Aucun workflow n'exécutait les 1 632 tests. `grep -rln pytest .github/workflows/`
ne renvoyait que `claude.yml`, et uniquement dans `--allowed-tools` — une
autorisation donnée à l'agent de revue, pas un job. La suite n'était verte que si
quelqu'un la lançait en local. C'est la cause racine de #457 : deux tests
d'acceptation cassaient depuis une mise à jour du corpus, découverts par hasard.

Le workflow est `.github/workflows/tests.yml`. Ce qui suit consigne l'audit qui
l'a rendu défendable, puis chacun des arbitrages qu'il fallait trancher.

### L'audit d'abord : un job qui rougit au gré des données est un job qu'on apprend à ignorer

La condition nécessaire posée par #473 — aucun test ne doit dépendre du corpus
vivant ni écrire dedans — a été **mesurée, pas supposée**. Un plugin pytest
jetable a instrumenté `io.open`, `builtins.open`, `os.open`, `socket.connect`,
`socket.create_connection` et `socket.getaddrinfo` sur la totalité de la suite,
en attribuant chaque accès au test qui l'avait déclenché.

C'est cette méthode qui compte, plus que les chiffres : **un `grep` ne voit pas
ces dépendances.** Les tests fautifs ne nommaient aucun chemin ; ils appelaient
une CLI ou une fonction dont une *valeur par défaut* pointait dans le dépôt.
C'est déjà le piège qui avait fait écrire un test dans `pivot_data/`, et c'est le
même en lecture. Le relevé initial :

| | Constat |
|---|---|
| **Écritures** dans `pivot_data/` ou `raw_data/` | **0 test** — confirmé aussi par un `git status` propre après un run complet. Le piège d'écriture était déjà refermé. |
| **Lectures du corpus vivant** | **10 tests**, dont **9 invisibles au `grep`** |
| **Lectures de config déclarative** | 5 tests, délibérées, conservées (voir plus bas) |
| **Sorties réseau réelles** | **1 test**, vers un site tiers |

Les dix lectures du corpus, et leur traitement :

- **`tests/test_audit_pivot_dataset.py`, 4 tests.** Ils surchargeaient
  `--input-dir` vers les fixtures mais pas `--scrutins` ni `--amendements`, dont
  les défauts argparse valent `pivot_data/scrutins.json` et
  `pivot_data/amendements/`. Ils lisaient donc ~66 Mo du corpus vivant sans
  qu'une seule assertion n'en dépende. Corrigé par une fixture `autouse` qui
  réécrit les deux globales : le parser étant reconstruit à chaque appel de
  `main()`, la surcharge couvre aussi les tests à venir.
- **`tests/test_generate_group_profiles.py`, 5 tests.** Même piège, variante plus
  retorse : `generate_all()` reçoit ces chemins en **valeur par défaut de
  paramètre**, liée à la définition — un monkeypatch de la globale du module n'y
  peut rien. Corrigé en substituant les chargeurs, appliqués à un chemin absent :
  ils rendent alors un index vide *du bon type*, en s'appuyant sur leur contrat
  documenté (« index vide si le fichier est absent ») plutôt que sur un faux.
- **`tests/test_gouvernement_profile.py`, 1 test.**
  `test_build_profile_real_pivot_gabriel_attal` lisait
  `pivot_data/profiles/gabriel-attal.pivot.json` : exactement le défaut de #457,
  dans un fichier que #472 n'avait pas traité parce que l'échec ne s'y était pas
  manifesté. Rebranché sur la fixture figée déjà produite par #472. **Le
  diagnostic de #473 était donc incomplet sur ce point** — il annonçait le
  découplage comme acquis ; il l'était pour le fichier où le symptôme était
  apparu, pas pour le module voisin.

Restent **5 tests** qui lisent `raw_data/groupes_reels.json` et
`raw_data/gouvernements_reels.json`. **Ils sont conservés, délibérément** : ces
deux fichiers ne sont pas du corpus mais de la **config déclarative éditée à la
main**. La frontière est vérifiable, pas déclarative — le `git add` de
`generate-data.yml` liste `raw_data/profiles`, `pivot_data/profiles`,
`pivot_data/partis`, `pivot_data/groupes`, `pivot_data/gouvernements`,
`pivot_data/scrutins.json` et `pivot_data/amendements`, et **aucun des deux
fichiers de config**. Le bot ne peut pas les changer ; seule une personne le
peut, et c'est précisément à ce moment-là qu'on veut savoir si la config reste
valide. Les figer en fixtures ne testerait plus que la copie.

La sortie réseau, enfin :
`tests/test_candidate_profile.py::test_build_profile_no_syceron_for_senat`
appelait réellement `archive.nossenateurs.fr` sur deux législatures à
`TIMEOUT = 15 s`. Le test patchait tout ce qu'il croyait nécessaire, mais pas
`fetch_dossiers_for_legislatures`, la seule branche réservée à
`chambre != "deputes"` — donc la seule que ce test empruntait. Il coûtait **16 s
des 35 s** de la suite et aurait fait dépendre le job d'un site tiers.

**Résultat, mesuré après correction : 1 632 tests, 0 écriture, 0 lecture du
corpus vivant, 0 sortie réseau externe, et 35 s → 11 s.** La suite est
déterministe : elle ne peut plus rougir à cause d'une mise à jour de données.

### Arbitrage 1 — déclencheurs : `pull_request` **et** `push` sur `main`, sans `paths-ignore`

`pull_request` seul laisserait passer le cas qui nous concerne directement : deux
PR vertes séparément peuvent casser `main` une fois fusionnées l'une après
l'autre, par conflit sémantique et non textuel — que git ne voit pas. Le dépôt
vit dans ce régime, plusieurs branches ouvertes en parallèle sur le même code.
`push: [main]` est le filet, à 11 s le run.

**Pas de `paths-ignore`, ni pour les commits de données du bot, ni pour la
documentation.** Deux raisons, la seconde plus intéressante que la première :

1. **Le piège du check requis.** Un job filtré par `paths-ignore` n'est pas
   « réussi », il est *absent* — et un check requis absent laisse la PR
   indéfiniment `pending`. Une PR purement documentaire serait bloquée sans
   moyen de la débloquer autrement qu'en retirant l'exigence.
2. **Le commit de données est le canari.** Exclure les commits de
   `generate-data` reviendrait à inscrire dans le YAML l'hypothèse « les tests ne
   dépendent pas des données » — l'hypothèse même dont #473 existe parce que
   personne ne l'avait vérifiée. Tant qu'elle tient, ces runs sont verts et
   coûtent 11 s ; le jour où un test se recouple au corpus, c'est ce run-là qui
   le dit. Payer 11 s pour transformer une hypothèse en vérification continue est
   un bon prix. (Accessoirement, `generate-data.yml` est aujourd'hui en
   `workflow_dispatch` seul, son `schedule` étant commenté : ces commits sont
   rares.)

### Arbitrage 2 — matrice Python : une seule version, 3.12, et pas de matrice

Le plancher réel a été **mesuré sur le code**, pas choisi : aucune trace de
`match`, `tomllib`, `datetime.UTC`, `itertools.batched`, `except*`, `StrEnum`,
`typing.Self` ni de génériques PEP 695. Ce qu'on trouve, ce sont 53 annotations
`X | None` (PEP 604) évaluées à l'exécution — seuls 6 fichiers de `src/` ont
`from __future__ import annotations` — et `zip(..., strict=True)`. **Le plancher
est donc 3.10**, sans aucun usage de 3.11 ou 3.12.

Ce plancher est un fait mesuré, pas une promesse : rien dans le dépôt ne
s'engage sur une version (ni `pyproject.toml`, ni `setup.cfg`, ni
`python_requires` — le projet n'est pas un paquet distribué). Une matrice
3.10/3.11/3.12 multiplierait par trois le coût pour garantir un support que
personne ne réclame et qu'aucun utilisateur n'exerce.

Le job tourne donc sur **la version qui exécute la production**, en réutilisant
`./.github/actions/bootstrap-extraction` — dont `inputs.python-version` vaut
`'3.12'`. C'est le point décisif : la version n'a qu'une seule déclaration dans
tout le dépôt, et si quelqu'un l'y change, les tests le suivent sans qu'on ait à
y penser. Tester sur un interpréteur que la production n'utilise pas serait
tester autre chose. Le plancher 3.10 est consigné ici pour que l'élargissement
de la matrice, s'il devient utile, parte d'un chiffre plutôt que d'un pari.

### Arbitrage 3 — bloquant tout de suite, pas informatif

#473 penchait pour « informatif quelques semaines, le temps de vérifier la
stabilité ». Ce délai sert à se prémunir d'un job instable ; l'audit ci-dessus
montre qu'il n'y a rien à observer. Aucune écriture, aucune lecture du corpus
vivant, aucune sortie réseau, aucun `sleep` dépendant d'une horloge externe :
les seules sockets restantes sont des serveurs HTTP locaux (`127.0.0.1`) montés
par les tests eux-mêmes. Un job informatif, lui, a un coût certain — il apprend
à lire un rouge comme du bruit, et c'est exactement ce qui rendait #457
possible. Le job **échoue** donc dès maintenant si un test échoue.

**Réserve explicite, parce qu'elle n'est pas dans ce dépôt** : en faire un
*required check* qui bloque le bouton « merge » est un réglage de protection de
branche, dans les paramètres GitHub, qu'aucun fichier versionné ne porte. En
l'état, l'échec est visible et rouge sur la PR, mais n'empêche pas
mécaniquement la fusion tant que ce réglage n'est pas posé à la main.

### Arbitrage 4 — coût runner : la suite ne domine pas, le checkout le ferait

Chiffres mesurés en local (Python 3.12.3, la même version qu'en CI) :

| | Durée | Pic mémoire |
|---|---|---|
| Avant correctifs, à froid | 45,5 s | 285 Mio |
| Avant correctifs, à chaud | ~35 s | |
| **Après correctifs** | **11,2 s** | |

Et en CI, sur le premier run réel du job (`32361952284`, PR #478, commit
`efed279`, 20/08/2026 11:03 UTC) — **job complet en 24 s**, soit :

| Étape | Durée |
|---|---|
| `actions/checkout` (sparse + `blob:none`) | **2 s** |
| Garde « corpus hors du checkout » | < 1 s |
| `bootstrap-extraction` (setup-python + `pip install`) | 5 s |
| **pytest (1 639 tests)** | **12 s** |

Les 2 s de checkout sont à comparer aux **93–117 s** que #467 a mesurées pour un
checkout complet du même dépôt : la liste de chemins ci-dessous vaut un facteur
~50 sur ce poste.

La correction a supprimé les trois postes qui dominaient : 16 s d'appel réseau
réel, ~8 s de chargement d'index du corpus, et le reste en désérialisation. Ce
qui domine désormais est `tests/test_amendements_download_modes.py`, dont onze
teardowns attendent 0,5 s l'arrêt d'un serveur HTTP local — ~5,5 s, soit la
moitié de la suite. **Signalé, pas traité** : ces temporisations font partie du
scénario testé (les trois états de dégradation du téléchargement par Range), et
les raccourcir demande de retoucher le module, pas le test. À reprendre dans une
issue dédiée si le job devient un jour un point de contention.

Le vrai poste de coût est ailleurs : l'arbre de travail pèse **1,8 Gio**, dont
1,5 Gio de `raw_data/profiles/` et 240 Mio de `pivot_data/`. Un `checkout` complet
coûterait plusieurs fois la durée des tests — #467 vient de le mesurer sur ce
même dépôt : **93 à 117 s par shard** sur le run 32288588518, soit ~55 % du temps
d'un shard d'extraction (voir `#budget-execution-pleine-echelle-467`). Le job
fait donc un
**sparse-checkout** (`sparse-checkout-cone-mode: false`) doublé de
`filter: blob:none` — sans le filtre, git téléchargerait les blobs de tout
l'arbre avant de n'en matérialiser qu'une fraction.

La liste des chemins n'est pas une devinette : l'instrumentation a relevé
l'ensemble **exhaustif** des fichiers du dépôt que la suite touche hors `src/` et
`tests/` — trois fichiers sous `.github/`, les deux JSON de config, et cinq
fichiers sous `web/` lus par les tests `test_web_v3_*`.

Et ce n'est pas qu'une économie. **Ne pas poser le corpus sur le disque rend le
critère « aucun test ne lit `pivot_data/` » structurel au lieu d'audité une
fois.** Un test qui s'y recouplerait échoue sur un `FileNotFoundError` nommant
le chemin fautif, au lieu de passer en silence jusqu'à la prochaine mise à jour
du corpus — le scénario #457, précisément. Un step de garde vérifie d'ailleurs
que `pivot_data/` et `raw_data/profiles/` sont bien absents du checkout : si le
périmètre est élargi un jour, ce sera une décision, pas un effet de bord.

Le revers assumé : le checkout de CI diffère de celui d'un poste de
développement, et un test qui lirait un chemin non listé passerait en local et
échouerait en CI. C'est le sens de l'échange — cette divergence *est* le
garde-fou, et le message d'erreur nomme le chemin manquant.

### Arbitrage 5 — dépendances : `requirements-dev.txt`, pas un `pip install pytest` en dur

Le dépôt n'avait ni `requirements-dev.txt`, ni `pyproject.toml`, ni `setup.cfg` :
`requirements.txt` ne porte que les dépendances d'exécution, et la suite a besoin
de pytest en plus. Écrire `pip install -r requirements.txt pytest` dans le YAML
aurait mis une version de pytest hors de toute déclaration, libre de diverger de
celle des postes de développement sans que rien ne le signale.

D'où `requirements-dev.txt`, qui fait `-r requirements.txt` (une seule
déclaration des dépendances d'exécution) puis épingle `pytest==9.1.1` — la
version réellement installée dans `.venv/` et celle avec laquelle les durées
ci-dessus ont été mesurées, au `==` comme l'exige AGENTS.md §8. Le job le passe à
`bootstrap-extraction` via son `inputs.requirements`, sans dupliquer l'étape
`setup-python` + `pip install`.

---

<a id="test-adosse-au-corpus-vivant"></a>
## Un test d'acceptation adossé au corpus vivant rougit quand la donnée s'améliore (#457) (2026-08-20)

Les vérifications d'acceptation de #209 (`tests/test_gouvernement_roster.py`)
lisaient `pivot_data/profiles/` directement, pour confronter
`build_gouvernement_roster` à de vrais profils plutôt qu'à des cas fabriqués.
L'intention était bonne ; le montage, non. Deux d'entre elles étaient rouges sur
`main`, et **aucune ne signalait une régression de code** :

- `charlotte-parmentier-lecocq` : le test assenait `portefeuille is None` pour la
  période Bayrou. Le portefeuille a fini par être renseigné dans le corpus. Le
  test échouait donc **parce qu'une lacune de données avait été comblée** — il
  avait figé l'absence en invariant.
- `david-amiel` : le test attendait 1 membre, en obtenait 2, parce que l'intéressé
  a changé de portefeuille sans changer de gouvernement.

**La leçon** : un test unitaire adossé à un corpus vivant n'a que deux issues, et
les deux sont mauvaises. Ou bien il fige une valeur, et il rougit à la première
mise à jour — y compris, comme ici, une mise à jour qui *améliore* la donnée, et
le signal est alors exactement inversé : rouge veut dire « ça va mieux ». Ou bien
il s'assouplit jusqu'à ne vérifier que la forme, et il cesse de contrôler ce pour
quoi il avait été écrit. Mesurer la couverture du corpus réel est le travail du
quality gate (`check_quality_gate.py` §5), qui est fait pour ça : il mesure un
niveau et le compare à un seuil, sans prétendre qu'une valeur est immuable.

D'où des **fixtures figées** sous `tests/fixtures/gouvernement_roster/` (modèle
`tests/fixtures/audit_pivot/`) : de vrais profils, réduits aux seuls champs que
`gouvernement_roster` lit (`id`, `nom`, `identite.source_url`, `mandats[]`) et
aux catégories `fonction_gouvernementale` / `mandat_electif` — 3 à 6 Ko au lieu
de 0,3 à 0,5 Mo. Chacune consigne sa provenance dans `meta.fixture` (fichier
source, ref, date d'extraction : §2.2), pour qu'on sache toujours de quel état du
corpus elle est le témoin. `mandat_electif` y est gardé bien qu'inerte pour ce
module, afin que le filtrage par catégorie porte réellement sur quelque chose.

### Le corollaire, qui dépasse les tests : `membres[]` dénombre des entrées, pas des personnes

Le cas `david-amiel` posait une vraie question éditoriale — un ministre qui change
de portefeuille sans changer de gouvernement doit-il compter deux fois ? — en
opposant §2.2 (traçabilité : deux fonctions distinctes sur deux périodes
distinctes, les fondre effacerait un fait vérifiable) à §2.7 (un dénominateur
publié doit être juste).

Elle se tranche par une vérification, pas par un arbitrage : **aucun effectif
n'est publié aujourd'hui**. `comptages.par_statut` dénombre des textes de loi, et
`web/UI_finale/src/components/GovernmentProfile.jsx` liste les membres sans en
donner le total (`members.length` n'y sert qu'au test de liste vide). Deux entrées
factuelles distinctes sont donc conformes à §2.2, et §2.7 n'est pas en cause :
rien n'expose de dénominateur faux.

Mais le décalage, lui, est bien réel et **systémique** — mesuré sur les 10
gouvernements publiés : 116 entrées pour 95 personnes, dont 7 gouvernements
concernés.

| gouvernement | entrées | personnes | écart |
| --- | --- | --- | --- |
| BORNE | 31 | 23 | 8 |
| BAYROU | 12 | 9 | 3 |
| CASTEX | 14 | 12 | 2 |
| FILLON_2 | 5 | 2 | 3 |
| FILLON_3 | 3 | 1 | 2 |
| LECORNU_II | 12 | 10 | 2 |
| PHILIPPE_2 | 9 | 8 | 1 |

Le risque est **différé, pas absent** : la première vue qui affichera « N
ministres » annoncera 31 pour Borne au lieu de 23, sans que rien ne l'avertisse.
La déduplication est à faire au moment de l'affichage, par `membre_id` — pas dans
`membres[]`, dont la granularité par période est ce qui porte l'information.
Même principe qu'en [[mandat-electif-perdu-fausse-le-denominateur]] : la
structure de `mandats[]` décide de ce qu'un décompte veut dire, et un
dénominateur faux se publie sans avertissement.

`src/audit_gouvernement_dataset.py` (`compute_taux_portefeuille_renseigne`) n'est
pas concerné : il rapporte des entrées à des entrées — c'est un taux
d'attribution par entrée, ce qu'il doit être —, et ce rapport d'audit n'est pas
publié.

---
<a id="mandat-electif-perdu-fausse-le-denominateur"></a>
## Un mandat électif perdu ne manque pas seulement sur la fiche : il sort le membre du dénominateur de son groupe (#465) (2026-08-20)

Les 355 `mandats` et 49 `textes_portes` restés perdus après [[restauration-interventions]]
ont été restaurés par la **même méthode** — champ seul, réinjecté dans le brut,
pivot re-dérivé par le code du jour. Rien de neuf de ce côté : ce qui suit est ce
que la restauration a révélé **en aval**, et qui ne s'était pas présenté en #463
ni en #464.

### Ce qui est nouveau

Les 355 mandats se répartissent en 301 commissions, 29 groupes d'amitié,
1 extra-parlementaire… et **24 mandats électifs**. Ces 24-là ne sont pas une
ligne de plus sur une fiche : `mandats[].categorie == "mandat_electif"` est ce
qui définit, dans `group_profile.py`, **la période pendant laquelle un membre est
éligible à un scrutin** (`_member_eligibility_intervals`). Les perdre revient à
déclarer le membre non éligible, donc à le retirer du **dénominateur** d'un ratio
publié (AGENTS.md §2.7).

Mesuré sur les trois groupes concernés :

| groupe | membres restaurés | effet |
| --- | --- | --- |
| `groupe-AN-REN-16` | 18 | `membres_eligibles` 63 → **69** sur les 4 099 scrutins ; `mandats_agreges` 646 → 729 entrées |
| `groupe-AN-RN-16` | 1 | 3 405 scrutins recalculés |
| `groupe-AN-SOC-16` | 1 | `cohesion_votes` **0 → 814 scrutins** |

Le cas de `groupe-AN-SOC-16` est le plus net. Son unique membre couvert,
`jerome-guedj`, n'avait plus que son mandat de la XVII (2024-07-07) : la XVI
(2022-06-22 → 2024-06-09) était partie avec les mandats perdus. Le groupe
publiait donc **zéro scrutin de cohésion**, et le quality gate le signalait
comme « données incomplètes ? ». Ce n'était pas une lacune de collecte : la
donnée était là, c'est la clé de lecture qui manquait.

Même effet sur `membres[].debut_dans_groupe`, dérivé du premier mandat électif :
10 des 23 profils affichaient une entrée dans le groupe trop tardive de deux ans.

**La leçon** : une perte sur `mandats` ne se lit pas au nombre d'entrées. Selon
la `categorie`, elle est soit une ligne manquante, soit un **dénominateur faux** —
et un dénominateur faux est publié sans avertissement, parce que rien, dans le
profil de groupe, ne distingue « ce membre n'était pas élu ce jour-là » de « on a
perdu son mandat ».

### Le patch de groupe, et son contrôle

Patch chirurgical, comme en #464 : régénérer les profils de groupe écraserait
`meta.couverture_roster`, qui vient d'un fetch réseau. Les cinq champs qui
dépendent de `mandats[]` — `membres`, `effectif`, `periode`, `cohesion_votes`,
`mandats_agreges` — sont recalculés par les fonctions du pipeline elles-mêmes et
réinjectés ; `tags_thematiques_agreges`, `amendements_agreges`, `sources` et
`meta` ne sont pas touchés (vérifié : `_aggregate_amendements` ne lit pas
`mandats`, `parti_profile.py` non plus, et `gouvernement_roster.py` ne lit que
les mandats `fonction_gouvernementale` — dont **aucun** n'a été restauré).

Ce recalcul ne vaut que si l'on prouve qu'il reproduit le pipeline. **Contrôle
préalable** : recalculer ces cinq champs à partir des pivots d'**avant** la
restauration doit rendre les profils de groupe committés **à l'identique**. Fait
sur les 7 groupes, y compris les 4 sans membre restauré — zéro écart. Sans ce
contrôle, un écart après restauration serait indiscernable d'un artefact de la
méthode de recalcul.

Même logique côté profils : re-dériver les 32 pivots par `--pivot-only
--no-merge` **avant** de toucher au brut rend les 32 fichiers committés
octet pour octet. La re-dérivation est donc un no-op vérifié, et tout écart
constaté après coup est imputable à la restauration seule.

### Ce que ça n'a pas rattrapé

`audit_diff_profils.py` compte des **listes**. Un scalaire qui régresse lui est
invisible, et il y en a : `parti` est passé de renseigné à `null` depuis
`a125e9e^` sur `jean-luc-melenchon`, `edouard-philippe` et `laurent-wauquiez` —
trois candidats déclarés, dont `raw_data/candidats.json` porte pourtant le parti.
Quatre autres (`jerome-guedj`, `gabriel-attal`, `bruno-retailleau`,
`marine-le-pen`) ne l'ont jamais eu dans leur pivot, pour la même raison
probable : la passe pivot roster-driven repasse après la passe candidats et, en
`--no-merge`, réécrit le pivot sans le `parti` que seule la première connaît.

Non corrigé ici : c'est un défaut de pipeline, pas une donnée à restaurer, et le
réparer dans un commit de restauration mélangerait deux sujets. Consigné pour
qu'il ne se reperde pas.

<a id="collecte-vide-necrase-jamais"></a>
## Une collecte vide n'écrase jamais une collecte non vide (#465) (2026-08-20)

En mode écrasement (`--no-merge`), la fusion additive ne protège plus rien. Or
une **sous-collecte** peut échouer sans que le profil écrit n'ait l'air anormal :
identité introuvable, endpoint en panne, archive indisponible. Le profil part
alors avec un champ simplement vide, et il remplace le bon.

### Ce que ça a coûté

Run `32302557156` du 19/08/2026, lancé en écrasement pour propager une
correction :

| profil | perte | ce que portait le profil écrit |
| --- | --- | --- |
| `jean-luc-melenchon` | 18 721 amendements, 1 016 votes, 33 textes | « aucun mandat français connu — identité introuvable » |
| `bruno-retailleau` | 36 textes portés | « votes introuvables » |
| `marine-le-pen` | 23 textes portés | **aucun avertissement** |

Le troisième cas est le plus instructif. Ses amendements (13 991) et ses votes
(1 813) sont **intacts** : seuls ses textes portés sont tombés à zéro, et rien
dans le profil ne le signalait. Un garde-fou conditionné à la présence d'un
avertissement ne l'aurait pas vu. Un garde-fou raisonnant sur le profil entier
non plus.

### Ce que le diagnostic initial avait manqué

J'avais d'abord attribué ces pertes à la publication d'un job **annulé** — quatre
shards l'avaient été — et au `if: always()` de l'étape de publication. C'était
faux, et vérifiable : le profil de Mélenchon a été écrit à 21:13:30, **deux
minutes après le lancement**, bien avant l'annulation de son job. Celui de Le Pen
ne portait aucune trace d'interruption.

L'annulation n'est pas la cause. La cause est qu'un `[]` non mesuré a la même
forme qu'un `[]` constaté, et que `--no-merge` ne fait pas la différence.

### La règle, et elle existait déjà ailleurs

> Une collecte **vide** ne remplace jamais une collecte **non vide**. Champ par
> champ, pas profil par profil.

Ce n'est pas une invention : #427 l'a énoncée pour les gouvernements, et le code
le dit noir sur blanc — *« distinguer "zéro dossier constaté" de "collecte
incomplète" ; sans elle, l'appelant écraserait des profils avec un `textes: []`
qui n'a jamais été mesuré »*. Les profils étaient le seul endroit à ne pas
l'appliquer.

### Ce que la règle ne bloque pas

**Une correction de clé aboutit toujours.** #440 a remplacé 2 018 amendements par
944 — une baisse de plus de moitié, parfaitement légitime, et non bloquée :
944 n'est pas zéro. Seul le passage à **zéro** est refusé. C'est ce qui distingue
ce garde-fou d'une demi-fusion, laquelle rendrait toute correction impossible et
recréerait le défaut de [[publication-scopee-artifacts]].

Et le champ est traité **isolément** : Le Pen aurait gardé ses 23 textes portés
tout en voyant ses amendements écrasés normalement.

### Levée explicite, préservation jamais silencieuse

`--autoriser-collecte-vide` permet de vider délibérément un champ. Sans lui, la
préservation est **imprimée** : « collecte vide sur *champ* — entrées existantes
PRÉSERVÉES malgré `--no-merge` ». Une préservation muette serait un autre défaut :
on croirait la collecte réussie.

### Deux couches, pas une

| | quand | attrape |
| --- | --- | --- |
| ce garde-fou | à l'écriture du profil | la collecte ratée, avant qu'elle ne touche le disque |
| [[controle-de-perte-avant-commit]] (#461) | avant le commit | le reste — baisse partielle, profil disparu |

La première empêche le dégât, la seconde le rattrape s'il passe quand même.
Aucune ne remplace l'autre : une baisse de 2 035 à 5 votes n'est pas un vide, et
seul le contrôle de perte la verrait.

### Ce que ça ne corrige pas

Le `if: always()` de l'étape de publication reste en place, et c'est désormais un
choix : puisque la destruction ne vient pas de là, le publier reste utile — un
job préempté en fin de course garde son travail. La question de savoir si un
artifact de job annulé doit être marqué comme partiel se pose toujours, mais
elle ne porte plus l'urgence qu'on lui prêtait.

<a id="publication-dun-job-annule"></a>
## Un préfixe de flux est valide, un préfixe de profil est faux (#460) (2026-08-20)

> ⚠️ **Diagnostic corrigé le 20/08/2026 — voir [[collecte-vide-necrase-jamais]] (#465).**
> Cette entrée attribue la destruction du run `32302557156` à la publication
> d'un job **annulé** et au `if: always()` de l'étape de publication. C'est
> faux. Le profil de `jean-luc-melenchon` a été écrit **deux minutes après le
> lancement**, bien avant l'annulation de son job, et celui de `marine-le-pen`
> ne portait aucune trace d'interruption. La cause réelle est qu'une
> **sous-collecte en échec** rend un `[]` que `--no-merge` ne distingue pas d'un
> zéro constaté.
>
> Ce qui reste juste ici : le constat chiffré des pertes, la restauration, et la
> remarque sur la transposition abusive du principe de #443 — un préfixe de flux
> est exact, un profil partiel est faux. Elle vaut toujours, elle n'explique
> simplement pas ce cas-ci.

Le run `32302557156`, lancé pour **réparer** la perte d'interventions de #460, a
détruit davantage qu'il n'a réparé. Il s'est terminé `cancelled` — 4 de ses 8
shards `extract-an` annulés de l'extérieur — mais `merge-and-pivot` a réussi et
a committé (`e4d71cf`).

| profil | champ | avant | après |
| --- | --- | --- | --- |
| `jean-luc-melenchon` | `amendements` | 18 721 | **0** |
| | `votes` | 1 016 | **0** |
| | `textes_portes` | 33 | **0** |
| | `mandats` | 68 | 29 |
| `bruno-retailleau` | `textes_portes` | 36 | **0** |
| `marine-le-pen` | `textes_portes` | 23 | **0** |
| | `mandats` | 53 | 52 |

Restauré : **121 interventions sur 789**. Les trois profils sinistrés sont
parmi les quatre dont le shard a été annulé.

### La cause est dans #450, et elle vient d'une transposition abusive

L'étape de publication introduite par #450 porte `if: always()`. Elle publie
donc ce qu'un job **annulé** avait écrit — y compris un profil collecté à
moitié. Avec `--no-merge`, ce demi-profil écrase le bon.

Ce `if: always()` était délibéré, et justifié par [[telechargement-an-trois-modes-defaillance]]
(#443) : *ne jamais jeter un préfixe valide*. Les préemptions sont fréquentes
ici (#228), et un job interrompu ne devait pas perdre son travail.

**La transposition était fausse.** Sur un flux de téléchargement, un préfixe est
un préfixe : les octets déjà reçus sont exacts, et la reprise complète. Sur un
profil, un « préfixe » n'est pas un profil incomplet — c'est un profil **faux** :
rien ne distingue « ce membre n'a aucun amendement » de « la collecte s'est
arrêtée avant les amendements ». Le manifeste consigne l'écriture, pas sa
complétude.

Le principe de #443 reste juste dans son domaine. Il ne se transpose pas à un
enregistrement structuré, dont la validité n'est pas croissante avec le nombre
d'octets écrits.

### Ce qui aurait dû l'arrêter

[[controle-de-perte-avant-commit]] (#461) : le contrôle aurait vu −18 721
amendements, écrit `PERTE_PROFILS_NON_DECLAREE` et annulé le commit. Il était
ouvert en PR au moment du run, non mergé — le run tournait sur `280faa8`.
Mergé depuis (`81e36e8`).

### La restauration

Faite **à la main**, par fusion additive depuis `e4d71cf^` :

1. les trois profils **bruts** sont fusionnés (`merge_raw_profile`) avec leur
   version d'avant — additif, donc rien de ce que le run aurait légitimement
   ajouté n'est écarté ;
2. les index partagés sont reconstruits — sans ça, les 18 721 amendements
   restaurés ne seraient référencés par aucune entrée d'index ;
3. les trois pivots sont re-dérivés par le code d'aujourd'hui (`--pivot-only
   --no-merge`), donc au **schéma courant** (#431/#432).

Le brut ne pouvait pas être copié depuis le pivot d'avant : `e4d71cf^` porte
l'**ancien** schéma pivot, et le recopier annulerait #431 et #432. Le brut, lui,
n'est pas normalisé — c'est la couche source-near — donc son schéma est stable
d'un commit à l'autre. C'est ce qui rend la restauration possible, et c'est un
argument de plus pour [[normalisation-votes]] : ne pas normaliser le brut, ce
n'est pas de la place perdue, c'est la seule copie depuis laquelle reconstruire.

Vérification : `audit_diff_profils.py --ref e4d71cf^` rend « aucune perte sur
les champs stables », et les totaux du corpus retrouvent l'état d'avant —
524 353 votes, 810 552 amendements, 423 textes portés, 16 498 mandats — **plus**
les 121 interventions que le run avait légitimement rendues.

### Ce qui reste ouvert

Le `if: always()` de l'étape de publication **n'est pas corrigé ici**. Le
corriger demande de trancher : ne rien publier depuis un job annulé (on perd
alors le travail d'un job préempté en fin de course), ou marquer l'artifact
comme partiel pour que la fusion le refuse en mode écrasement. Les deux se
défendent, et ce n'est pas une décision à prendre dans un commit de
restauration.

<a id="controle-de-perte-avant-commit"></a>
## Le contrôle de perte était écrit, documenté, et branché sur rien (#460) (2026-08-19)

Le run `32288588518` a effacé **les 789 interventions du corpus**, et avec elles
647 `tags_thematiques` et 497 `tags_thematiques_agreges` — des champs
**publiés** (AGENTS.md §6). La section « thèmes » d'un profil de groupe s'est
vidée sur le site. Personne ne l'a vu.

### Deux comportements corrects, une donnée détruite

Ni la collecte ni l'écrasement n'étaient fautifs :

- `extract_interventions=false` saute la **collecte**. C'est le mode rapide
  documenté, et c'est voulu.
- `overwrite_profiles=true` réécrit le profil **sans** ce que ce run n'a pas
  collecté. C'est voulu aussi : c'est ce qui permet de propager une correction
  de clé, et c'est précisément ce que #445 et #451 ont rendu possible.

Chacun isolément est juste. Ensemble, ils effacent une donnée déjà acquise —
exactement ce que la fusion additive existe pour empêcher.

**Le filet qui a disparu était accidentel.** Avant #451, le bug de publication
de #450 réinjectait les copies périmées à chaque run : l'écrasement ne prenait
jamais effet, et les interventions survivaient *par accident*. En corrigeant la
publication, on a retiré un filet involontaire — et le premier run en mode
écrasement a effacé pour de bon. C'est le même run qui a fait passer les
amendements à 100 % d'`uid` : le gain était réel, le coût n'a été vu de
personne.

### Pourquoi la quality gate ne pouvait pas l'attraper

Elle a parlé. Sa §3 affichait :

```
│  Profils analysés : 209   Sous le seuil : 209
```

Un signal qui se déclenche sur **100 % du corpus** ne dit rien de ce qui a
changé — et par construction il ne le peut pas : il mesure un **niveau**, pas
une **variation**. Un profil à 0 intervention lui est indiscernable selon qu'il
n'en a jamais eu ou qu'il vient d'en perdre 789.

### Ce qui manquait n'était pas un outil, c'était un appel

`src/audit_diff_profils.py` compare une référence git au contenu courant,
profil par profil et champ par champ, et sort en erreur sur une perte. Il était
cité dans quatre documents, dont #429 qui le disait « indispensable avant tout
commit de régénération ».

Recherché dans `.github/`, `src/` et `scripts/` : **aucun appel**. Un garde-fou
écrit, testé, documenté, recommandé — et débranché. C'est le genre d'écart que
seule une recherche explicite révèle : rien dans le dépôt ne signalait qu'un
outil n'était appelé de nulle part.

### La décision

L'appel est posé dans `merge-and-pivot`, **avant** l'étape de commit. Une perte
sur un champ stable produit `::error::PERTE_PROFILS_NON_DECLAREE` et un `exit 1`
— le step suivant ne s'exécute pas, donc rien n'est committé ni déployé.

**`--ref HEAD`, pas `origin/main`.** HEAD est le commit que le job a checkouté,
donc exactement l'état d'avant ce run. C'est aussi le seul qui fonctionne avec
le `fetch-depth: 1` par défaut d'`actions/checkout`, et le seul juste sur un run
lancé hors `main` — même raison qu'au garde-fou de #413 §2.

**Une perte peut être légitime**, et la régénération de #450 en attendait une.
Elle doit alors être **déclarée** : l'input `tolerer_pertes_profils` laisse une
trace dans les paramètres du run, là où un contrôle simplement retiré n'en
laisserait aucune. Il émet un `::warning::` à l'usage.

Le rapport est joint au `$GITHUB_STEP_SUMMARY` **dans tous les cas** : c'est en
échec qu'on en a le plus besoin, et un artifact qu'il faut aller télécharger ne
serait pas lu.

### Le contrôle ne tenait pas à l'échelle — corrigé avant de le brancher

Mesuré avant de poser l'appel : `audit_diff_profils.py` culminait à **3,2 Gio de
RSS** sur les 209 profils et se faisait tuer par l'OOM killer. À 752 profils,
~11 Go : un échec certain en CI, pour un script dont tout l'intérêt est de
tourner **avant** le commit.

La cause : `git cat-file --batch` lu avec `capture_output=True`, qui bufferisait
la totalité des profils avant d'en compter la première entrée. Lu **en flux**,
blob par blob, la mémoire ne dépend plus que du plus gros blob (~26 Mo) :
**236 Mio**, soit −93 %.

C'est le troisième outil de ce dépôt à buter sur ce mode d'échec, après l'index
des amendements ([[cache-amendements-forme-dedupliquee]] #377, #392) et les
index de #431/#432. Le motif est stable : **compter n'exige jamais de tout
matérialiser**.

Le risque propre à cette réécriture est le décalage de protocole — la lecture
entrelace l'écriture des requêtes et la lecture des blobs, et un octet de
décalage décalerait tous les profils suivants en rendant des comptes faux *sans
rien signaler*. D'où un test sur 60 profils de tailles croissantes, un autre
mêlant un blob de plusieurs Mo à des petits, et un troisième sur un JSON
corrompu au milieu.
<a id="restauration-interventions"></a>
## Restaurer 789 interventions sans revenir sur le reste du schéma (#460) (2026-08-19)

Le commit de données `a125e9e` a effacé la totalité des interventions du
corpus, brut **et** pivot, et la perte s'est propagée aux deux champs qui en
dérivent — `tags_thematiques` des profils, `tags_thematiques_agreges` des
groupes, tous deux **publiés** (AGENTS.md §6). Le mécanisme est celui de
l'issue : `overwrite_profiles=true` lève `--no-merge`,
`extract_interventions=false` lève `--skip-interventions`, et le profil est
réécrit sans ce que le run n'a pas collecté.

Ce qui était perdu, mesuré profil par profil sur `a125e9e^` :

| profil | interventions | `tags_thematiques` |
| --- | --- | --- |
| `jerome-guedj` | 395 | 179 |
| `marine-le-pen` | 302 | 318 |
| `edouard-philippe` | 50 | 150 |
| `laurent-wauquiez` | 22 | 0 |
| `jean-luc-melenchon` | 15 | 0 |
| `gabriel-attal` | 5 | 0 |
| **total** | **789** | **647** |

Côté groupes, 497 `tags_thematiques_agreges` : 318 sur `groupe-AN-RN-16`
(via `marine-le-pen`), 179 sur `groupe-AN-SOC-16` (via `jerome-guedj`). Les
150 tags d'`edouard-philippe` n'alimentent aucun groupe — il n'appartient à
aucun des 7 rosters committés.

### Pourquoi ne pas avoir attendu la régénération

Le run `32302557156` portait `extract_interventions=true` et aurait dû les
recollecter. Il a perdu **4 de ses 8 shards `extract-an` sur annulation
externe** — le motif récurrent de #221/#228 — et l'arbitrage se lit
directement dans la liste :

| shard | issue | interventions en jeu |
| --- | --- | --- |
| `jerome-guedj` | succès | 395 |
| `edouard-philippe` | succès | 50 |
| `gabriel-attal` | succès | 5 |
| `marine-le-pen` | **annulé** | 302 |
| `laurent-wauquiez` | **annulé** | 22 |
| `jean-luc-melenchon` | **annulé** | 15 |
| `bruno-retailleau` | **annulé** | 0 |

Le run ne pouvait donc rendre que **450 des 789 interventions**. Les 339
restantes, dont les 302 de `marine-le-pen`, seraient restées perdues — et avec
elles la totalité des 318 `tags_thematiques_agreges` de `groupe-AN-RN-16`,
qu'elle alimente à elle seule. Un run qui annule la moitié de ses shards ne
peut pas servir de plan de restauration : il rend les profils qu'il a eu le
temps de traiter, et rien, dans le commit produit, ne signale lesquels.
Attendre revenait à faire dépendre la récupération d'un aléa d'ordonnancement.

La restauration depuis git est immédiate, exhaustive et vérifiable. Elle ne
concurrence pas la recollecte : la fusion additive de `merge_profile.py`
(`interventions` : additif, l'ancienne entrée gagne) fait que tout run
ultérieur s'ajoute à ce qui est restauré, sans doublon ni écrasement.

### Ce qui a été écarté : recopier les fichiers de `a125e9e^`

C'était la voie évidente et elle est fausse. Les profils de `a125e9e^`
sont à l'**ancien schéma** — d'avant la normalisation des votes
([[normalisation-votes]], #432) et des amendements
([[normalisation-amendements]], #431). Les recopier aurait restauré 789
interventions en annulant 84,8 % de réduction de volume et en remettant en
place les `votes[]` dénormalisés que #432 vient de sortir des profils. On
répare une perte, on ne rejoue pas un état.

**Seul le champ `interventions` a donc été extrait de `a125e9e^`**, réinjecté
dans le brut au schéma courant, puis le pivot a été **re-dérivé** par le code
d'aujourd'hui : `_normalize_intervention` pour `interventions[]`, la dérivation
`theme_officiel` / `mots_cles` de `normalize_nosdeputes` pour
`tags_thematiques`, `group_profile.aggregate_tags_thematiques` pour les
groupes.

Ce qui autorise ce découpage est une propriété vérifiée, pas supposée :
appliquer `_normalize_intervention` d'aujourd'hui aux interventions brutes de
`a125e9e^` redonne **exactement**, pour les 6 profils, les
`interventions[]` pivot de `a125e9e^`. La normalisation des interventions n'a
pas bougé depuis ; #431 et #432 n'ont touché ni ce champ ni ses dérivés. Les
`tags_thematiques_agreges` recalculés sont eux aussi identiques, entrée pour
entrée, à ceux de `a125e9e^`.

### Vérification par l'outil prévu pour ça

`audit_diff_profils.py --ref origin/main`, c'est-à-dire le contrôle que #460
reprochait de n'être branché nulle part, appliqué à la correction elle-même :

| champ | avant | après | écart |
| --- | --- | --- | --- |
| `votes` | 524 353 | 524 353 | +0 |
| `mandats` | 16 498 | 16 498 | +0 |
| `textes_portes` | 423 | 423 | +0 |
| `interventions` | 0 | **789** | **+789** |
| `amendements` | 810 552 | 810 552 | +0 |

*« Aucune perte sur les champs stables »*, et un gain sur le seul champ visé.
Le diff est confiné : les 6 profils bruts ne changent que sur `interventions`,
les 6 pivots que sur `interventions` et `tags_thematiques`, les 2 groupes que
sur `tags_thematiques_agreges`. `validate_profil()` rend le **même nombre
d'erreurs qu'avant** sur les profils touchés (2 979 sur `gabriel-attal`,
15 804 sur `marine-le-pen` — des `votes[]` sans `scrutin_id`, antérieurs et
sans rapport), et aucune ne mentionne les interventions ni les tags.

Au passage, l'outil s'est fait **tuer par l'OOM killer** sur ce corpus dans sa
version de `main` — 3,14 Gio, `exit 137`. La vérification ci-dessus a été
conduite avec la version corrigée de [[controle-de-perte-avant-commit]]
(236 Mio). Un garde-fou qui meurt avant de conclure ne garde rien : c'est la
même classe de panne muette que celle qui a produit #460.

### Le commit de données est fait à la main

14 fichiers de données sont modifiés hors pipeline. C'est assumé et signalé
comme tel : aucun run ne peut produire ce résultat, puisque la recollecte
dépend de sources tierces dont deux jobs viennent d'être annulés. La
traçabilité (AGENTS.md §2.2) est intacte — chaque intervention restaurée
porte son `source_url` d'origine, aucune valeur n'est inventée, aucun champ
absent n'est comblé par un défaut (§2.5).

### Le garde-fou : avertir au lancement, refuser au commit

#460 listait deux pistes non exclusives. [[controle-de-perte-avant-commit]]
pose le contrôle **générique** : toute perte sur un champ stable échoue le job
avant l'étape de commit. Il manquait le signal **en amont** — rien ne disait,
au moment de lancer le run, que la combinaison d'inputs allait détruire des
données déjà acquises.

Un step de `prepare-an-matrix` s'en charge. Ce job n'a aucun `needs` : il
démarre immédiatement, donc l'avertissement est lisible avant qu'une minute de
runner ait été consommée. Sa condition reproduit **en négatif** le calcul de
`MERGE_FLAG` des jobs d'extraction (`fresh_run` **ou** `overwrite_profiles`),
parce que c'est `--no-merge`, et lui seul, qui rend l'écrasement destructeur —
un test échoue si les deux formulations divergent.

**Avertissement et non refus.** Un `exit 1` ici ferait double emploi avec le
refus d'aval, et casserait un usage légitime : propager une correction de clé
(#431, #432) sans repayer la collecte des interventions est un choix valide
dès lors qu'il est conscient. Ce qui manquait n'était pas un veto, c'était de
rendre le choix conscient. Le refus, lui, reste en aval, où il porte sur une
perte **mesurée** plutôt que **prédite**, avec `tolerer_pertes_profils` pour
la déclarer. Même forme et même ton que le `::warning::` de
`roster_refresh_existing` sans `overwrite_profiles` (#445).

**Le signal porte sur une variation, pas sur un niveau.** C'est ce qui
manquait à la quality gate : sa §3 se déclenchait sur 209 profils sur 209 et
ne distinguait donc pas « n'en a jamais eu » de « vient d'en perdre 789 ». Le
step compte les interventions réellement committées et **ne dit rien s'il n'y
en a aucune** — il n'y a alors rien à détruire, et un garde-fou qui crie à
vide se fait ignorer, ce qui est précisément le mécanisme par lequel le
signal de la §3 est devenu inaudible. Quand il parle, il chiffre : « ce run va
EFFACER les 789 interventions sur 6 profils », avec le détail par profil dans
le résumé de job, où il survit au bruit des logs.

Le comptage lit un profil à la fois et le libère : le corpus pèse ~1,5 Go par
répertoire, et trois outils de ce dépôt s'y sont déjà fait tuer par l'OOM
killer — dont `audit_diff_profils.py` deux paragraphes plus haut.

<a id="normalisation-amendements"></a>
## Normaliser les amendements : le coût n'est pas l'amendement, c'est sa liste de cosignataires (#431) (2026-08-19)

Un amendement est **identique pour tous ses signataires** — `texte_vise`,
`sort`, `date`, `numero`, `type_deposant`, `premier_signataire` et
`co_signataires`. Seul le `role_signataire` est propre au membre.
`_parse_amendement_entry` produit pourtant un enregistrement complet **par
signataire**, chacun portant sa propre copie de la liste des cosignataires.

### Le facteur × 63,3 de l'issue était un artefact de la clé écrasée

L'issue annonçait 4 246 026 paires pour 67 058 amendements distincts. Ce
décompte était fait **par `numero`**, qui repart à chaque texte
([[amendements-cle-uid]]) : il fusionnait des amendements sans rapport et
sous-estimait massivement le nombre de distincts. Redérivé sur `ff3639b`, la
couverture `uid` étant à 100 % :

| | paires | distincts | duplication |
| --- | --- | --- | --- |
| `amendements` | 810 552 | 207 238 | × 3,9 |
| `amendements[].co_signataires` | 77 666 854 | 4 957 807 | **× 15,7** |

**Le vrai coût est `co_signataires`**, pas l'amendement : 23,9 cosignataires en
moyenne, et la liste complète recopiée dans le profil de chacun d'eux — un N².
Elle pèse **1 083,9 Mo des 1 342,4 Mo** d'`amendements[]`.

### Résultat, mesuré sur les 209 profils committés

| | avant | après |
| --- | --- | --- |
| `amendements[]` dans les profils pivot | 1 342,4 Mo | **73,8 Mo** de mapping |
| `pivot_data/amendements/` (méta) | — | **54,4 Mo** |
| `pivot_data/amendements/` (cosignatures) | — | **75,7 Mo** |
| **total** | **1 342,4 Mo** | **203,8 Mo (−84,8 %)** |
| fichiers pivot, tous champs confondus | 1 601,2 Mo | **332,5 Mo** (+ 130,1 d'index = 462,6 Mo, **−71,1 %**) |

Les 810 552 paires sont **toutes** conservées, 0 amendement reste non résolu, et
les 4 957 807 entrées de cosignatures distinctes sont intégralement présentes
dans l'index.

### Où vit la liste dédupliquée : un fichier par législature, cosignatures à part

L'issue laissait la question ouverte. Elle est tranchée par la mesure, pas par
une préférence — la contrainte est la **limite GitHub de 100 Mo par blob**,
celle-là même qui avait imposé le découpage des index figés
([[amendements-legislatures-figees]]).

**Un fichier global unique est exclu dès aujourd'hui** : 130,1 Mo sur les seuls
209 profils actuels, soit 30 % au-dessus de la limite, et le corpus n'est qu'au
tiers de sa couverture.

**Un fichier par législature contenant aussi les cosignatures est exclu à
couverture complète.** Ce n'est pas une extrapolation : les archives figées
donnent le plafond exact, tous signataires confondus, indépendamment du nombre
de profils suivis.

| législature | amendements (archive complète) | méta | cosignatures | tout-en-un |
| --- | --- | --- | --- | --- |
| XIV | 154 296 | 37,2 Mo | 24,0 Mo | 61,2 Mo |
| XV | 307 644 | **74,9 Mo** | 45,4 Mo | **120,3 Mo** |
| XVI | 162 240 | 39,6 Mo | 48,7 Mo | 88,3 Mo |

La XV<sup>e</sup> dépasserait la limite à elle seule. **Cosignatures dans un
fichier compagnon**, donc : le plus gros blob plafonne alors à 74,9 Mo, avec
25 % de marge. Si elle venait à se réduire, gzip reste disponible — mesuré à
**25:1** sur ces fichiers — mais il n'est pas payé d'avance : `pivot_data/` est
lu par le navigateur, et un `.json.gz` y demanderait un `DecompressionStream`.

```
pivot_data/amendements/15.json                 méta partagé
pivot_data/amendements/15.cosignatures.json    fichier compagnon
```

### Le fichier compagnon n'est pas une mise à l'écart

`co_signataires` n'est lu par **personne** aujourd'hui — ni `group_profile`, ni
l'UI, ni les audits — et pèse 59 % de l'index. L'isoler évite à tous les
consommateurs de télécharger ce qu'aucun n'utilise : `charger(...,
avec_cosignatures=False)` est ce que font tous les appelants du dépôt, et
`sync-data.mjs` ne copie pas ces fichiers vers le site.

Ils ne sont pour autant **jamais** supprimés : un réseau de cosignatures est de
la matière première d'analyse (#324), et le principe directeur de l'épic #429
est « normaliser, jamais supprimer ». `ecrire()` refuse d'ailleurs d'écrire un
index chargé sans elles, plutôt que de les effacer en silence.

### L'identifiant : `an:<uid>`, et rien d'autre

Convention `<source>:<identifiant_source>` du dépôt. L'`uid` AN est la **seule**
clé unique d'un amendement — le `numero` repart à chaque texte, et keyer par lui
écrase 74,9 % des amendements ([[amendements-cle-uid]]). Contrairement à celui
d'un scrutin, l'identifiant n'a pas besoin de porter la législature : l'`uid` la
contient déjà (`AMANR5L17…`), et c'est de là qu'elle est lue pour choisir le
fichier — jamais déduite de la date.

Conséquence sur l'ordre des opérations : la construction de l'index **n'est pas
une passe de corpus**. Là où la législature d'un vote se résout par jointure sur
un jumeau étiqueté vivant dans un autre profil ([[resolution-legislature-votes]]),
tout ce dont un amendement a besoin est dans son propre enregistrement.
`generate_all_profiles --pivot` ne reconstruit donc l'index **qu'une fois**,
après la boucle, au lieu de deux pour les scrutins.

### Le seul champ qui divergeait entre les copies

Sur les 810 552 paires, 8 des 9 champs partagés — `co_signataires` compris —
sont **strictement identiques** d'une copie à l'autre. Un seul divergeait :
`premier_signataire`, que `_normalize_amendement` réécrivait à l'identifiant
pivot du profil lecteur quand celui-ci était l'auteur (44 139 cas). Une valeur
propre au lecteur n'a rien à faire dans une liste partagée : l'index retient la
référence AN (`an:PA…`), la seule que la collecte produise et la seule
indépendante du lecteur. Rien n'est perdu — `role_signataire`, resté dans le
mapping, dit déjà que le membre est l'auteur principal.

### Un invariant devenu jointure, trois qui ont suivi les champs

`type_deposant`, `sort` et `base_juridique_irrecevabilite` ont migré vers
l'index : leur validation les a suivis (`validate_amendements_index`), et
s'exécute désormais **une fois par amendement au lieu d'une fois par
signataire** — 207 238 vérifications au lieu de 810 552.

Une règle ne peut plus se vérifier sur un profil seul : **qu'un `amendement_id`
référencé existe**. `validate_profil(profil, amendements_index=...)` la vérifie
**si** l'index est fourni, et la **saute** sinon — jamais ne la déclare valide
par défaut. C'est le prix de la normalisation, et il est explicite plutôt que
caché.

`role_signataire` reste validé côté profil : c'est le seul champ qui y reste.

### Un amendement qu'on ne sait pas rattacher n'est ni supprimé ni deviné

`amendement_id: null` + `amendement_non_resolu` portant l'enregistrement complet.
Zéro cas côté AN (couverture `uid` à 100 %), mais **c'est la forme normale des
amendements du Parlement européen** : ParlTrack ne fournit pas d'`uid` AN, et lui
en fabriquer un serait inventer une clé (AGENTS.md §2.5). Ils gardent donc leur
enregistrement dans le profil — sans perte, un amendement PE n'étant de toute
façon pas recopié chez ses cosignataires.

### La forme plate n'est jamais re-matérialisée

C'est le critère d'acceptation explicite de l'issue, et la panne a déjà eu lieu :
`_load_frozen_amendement_index` appelait `_expand_aggregated_amendements_index`
« pour que le reste du pipeline n'ait pas à distinguer les deux origines », au
prix d'un facteur ~21 et d'un OOM ([[cache-amendements-forme-dedupliquee]],
#377).

Trois propriétés le verrouillent, chacune testée dans les deux sens
(`tests/test_amendements_index.py`) :

1. `joindre()` est un **générateur**, jamais une liste ;
2. `get()` rend **l'objet partagé lui-même** (`is`), jamais une copie ;
3. le pic d'allocation d'une jointure de 5 000 paires sur 10 amendements reste
   plus de 10 × sous celui de la forme plate équivalente — mesure calibrée par
   un témoin, pour ne pas dépendre de la version de Python.

Côté JS, `joinAmendements` est une fonction génératrice pour la même raison.

### `amendements_agreges` identique avant/après

Critère d'acceptation. Vérifié sur les données réelles, en recalculant
`_aggregate_amendements` deux fois sur les mêmes profils — forme d'origine, puis
forme normalisée jointe à l'index — et en comparant les 20 champs de décompte :

| population | paires | champs divergents |
| --- | --- | --- |
| AN-LR-16 (6 membres) | 32 378 | 0 |
| AN-REN-16 (166 membres) | 621 875 | 0 |
| AN-RN-16 (9 membres) | 117 744 | 0 |
| AN-SOC-16 (1 membre) | 14 335 | 0 |
| **les 209 profils** | **810 552** | **0** |

Un amendement qu'aucune source ne renseigne est **écarté et compté**, puis
remonté en `meta.warnings` du groupe : une exclusion muette transformerait un
dénominateur en donnée fausse (AGENTS.md §2.7).

### Ce qui n'est pas normalisé, et pourquoi

`raw_data/profiles` garde ses amendements dénormalisés. C'est la couche
source-near : elle porte l'enregistrement tel que la collecte l'a produit, et
c'est **d'elle** que l'index est reconstruit. Même décision que pour les votes.

### Construction en flux, comme pour les scrutins

Une seule passe, un profil à la fois, chaînes internées : **43 s et 351 Mio de
RSS** pour les 1,5 Go de `raw_data/profiles`. Charger le corpus d'un bloc, c'est
l'OOM de #377 et #392.

### Un index qui n'est pas committé ne sert à rien

Constaté en passant : `pivot_data/scrutins.json` manquait au `git add` du
workflow depuis #432 — l'index n'aurait jamais atterri sur `main`, et les
mappings des profils auraient pointé dans le vide sans la moindre erreur
visible. Corrigé en même temps que l'ajout de `pivot_data/amendements/`, et
verrouillé par `tests/test_ci_publication_profils.py`.

---
<a id="volumetrie-arbre-de-travail-nest-pas-depot"></a>
## Volumétrie : l'arbre de travail n'est pas le dépôt, et la photo n'est pas le coût (2026-08-19)

`audit_volumetrie_profils.py` comparait un total d'**arbre de travail** aux
seuils GitHub, qui portent sur le **dépôt** — ce qu'on clone, donc l'historique
compressé. L'écart n'est pas marginal : les profils JSON se déltifient
remarquablement bien.

| | arbre de travail | historique sur disque | facteur |
| --- | --- | --- | --- |
| `raw_data/profiles` | 1 490 Mo | 143 Mo | × 10,4 |
| `pivot_data/profiles` | 1 527 Mo | 109 Mo | × 14,0 |
| dépôt entier | 3 017 Mo de profils | **347 Mo** d'objets atteignables | |

`.git` pèse 670 Mo. Le cadrage de #429 annonçait donc une urgence **d'un ordre
de grandeur au-dessus du réel**, et l'erreur venait de l'outil de mesure
lui-même — pas d'une approximation de rédaction.

### Le vrai compteur : le coût par run

La photo ne grandit qu'avec le nombre de profils. L'**historique**, lui, grandit
à chaque run, définitivement. Le dernier commit de données (`a125e9e`, 209
profils) a ajouté **49,5 Mo** — 23,5 Mo pour le brut, 25,9 Mo pour le pivot.

À 752 profils, un run coûterait environ 180 Mo. En partant des 670 Mo actuels,
le seuil des 5 Go serait atteint après une vingtaine de runs à pleine échelle,
soit quelques semaines de runs quotidiens. **Aucune optimisation de la photo n'y
répond seule** : c'est le caractère récurrent qui décide, et c'est ce que le
rapport dit désormais en toutes lettres.

### Un second piège, corrigé là où on lit le chiffre

`--cible` compte des **fichiers**, pas des profils : `octets_total` est divisé
par le nombre de fichiers scannés. Passer deux répertoires avec
`--facteur-duplication 1.0` projette donc 752 *fichiers*, soit ~376 profils —
ni l'état actuel, ni le scénario d'un seul répertoire. Le bon usage est **un
seul répertoire**, avec le facteur en paramètre.

Je m'y suis fait prendre le 19/08 en mesurant pour #434, et l'invocation citée
dans #429 avait la même forme. Le rapport porte maintenant l'avertissement, à
l'endroit exact où on lit le chiffre — pas seulement dans une docstring que
personne ne relit au moment de conclure.

### Ce qui n'a pas changé

La mesure d'arbre de travail est **conservée** : un checkout de 10 Go est
pénible même si le dépôt tient dans 700 Mo. Les deux chiffres sont rendus côte
à côte, avec ce que chacun signifie — plutôt que de remplacer une mesure
trompeuse par une autre.

`--sans-historique-git` permet de sauter la mesure hors dépôt ou sur un très
gros dépôt, au prix explicite de perdre la seule mesure comparable aux seuils.

<a id="cache-amendements-existence-nest-pas-conformite"></a>
## L'existence d'un cache n'est pas la preuve de son contenu — et #447 n'avait pas de seconde cause (2026-08-19)

### Ce que #447 soupçonnait, et ce que la mesure dit

Le dernier commentaire de #447 (19/08 18:58Z) concluait que la couverture `uid`
partielle était **reproduite à la génération**, et donc qu'une seconde cause
subsistait dans le chemin de code d'`extract-an`, à côté de
[[publication-scopee-artifacts]]. L'argument : les 6 candidats déclarés sont
rigoureusement inchangés entre `698a882` et l'état committé après le run
`32277443716`, alors que les 8 jobs `extract-an` ont tourné avec succès.

**Cet argument ne conclut pas.** Sous fusion additive, « inchangé » est
exactement ce qu'on observe quand la version fraîche est un **sous-ensemble** de
la version committée : l'union d'un sous-ensemble et de son sur-ensemble est le
sur-ensemble. Une sortie fraîche à 100 % d'`uid` et un profil committé mixte
produisent donc le même « aucun changement » qu'une sortie mixte.

Le run suivant tranche. `32288588518` (sha `36d51e8`, donc avec #451/#452/#453,
succès le 19/08 à 19:34Z, données committées en `a125e9e`) a régénéré ces mêmes
profils, cette fois sans le défaut de publication de #450 :

| slug | avant (`698a882`) | après (`a125e9e`) |
| --- | --- | --- |
| gabriel-attal | 2 018 / 944 uid | **944 / 944** |
| jean-luc-melenchon | 38 175 / 18 721 uid | **18 721 / 18 721** |
| edouard-philippe | 2 715 / 1 966 uid | **1 966 / 1 966** |
| laurent-wauquiez | 5 482 / 3 533 uid | **3 533 / 3 533** |
| marine-le-pen | 27 085 / 13 991 uid | **13 991 / 13 991** |
| jerome-guedj | 27 812 / 14 335 uid | **14 335 / 14 335** |

Et la mesure décisive n'est pas le compte, c'est l'**identité d'ensemble** :
comparés entrée par entrée (JSON canonique), les amendements d'après sont
**exactement** le sous-ensemble portant un `uid` d'avant — 0 entrée ajoutée, 0
entrée perdue, sur les 6 profils et 53 490 entrées. La sortie d'`extract-an`
était donc déjà à 100 % au run précédent. Corpus committé à `a125e9e` : **179
profils AN à 100 %, 0 mixte, 0 à 0 %, 791 831 amendements tous porteurs d'un
`uid`**.

**#447 n'avait pas de seconde cause.** Sa cause était entièrement le `path:`
d'upload de [[publication-scopee-artifacts]], et #451 l'a refermée. La leçon
n'est pas dans le code mais dans l'inférence : *sous fusion additive, l'absence
de différence n'est pas une observation sur la version fraîche.* Le contrôle qui
l'aurait dit tout de suite existe déjà — `src/audit_diff_profils.py`, qui compare
par profil et par champ au lieu de comparer des totaux.

### Ce que l'enquête a trouvé à la place : deux impasses silencieuses

Aucune des deux n'a causé #447. Les deux sont mesurées, et les deux sont du même
mode d'échec que [[signal-uid-partiel]] : un zéro qui ne se signale pas.

**1. Un cache figé au format hérité n'est ni reconstruit, ni lu.**
`amendements_index_deja_figee()` vérifiait la *présence* (`amendements.json` +
répertoire de tranches + `fraicheur.json` portant `figee: true`) et jamais le
*format*. Un cache matérialisé avant la correction de clé du 18/08
([[amendements-cle-uid]]) est donc déclaré « déjà figé », et
`build_amendements_index.py` le saute — pendant que
`_read_cached_amendements_acteur` le **refuse** à la lecture, précisément parce
qu'il est hérité. Ni reconstruit, ni lu : la législature perd la **totalité** de
ses amendements, et le seul signe est un warning soft « index en cache absent ».

Mesuré le 19/08/2026 sur le cache local, sans réseau — les trois législatures
figées étaient simultanément dans les deux états :

| législature | `amendements_index_deja_figee` | `_read_cached_amendements_acteur` |
| --- | --- | --- |
| 14 | `True` | `None` (index refusé) |
| 15 | `True` | `None` (index refusé) |
| 16 | `True` | `None` (index refusé) |

Le contrôle ajouté lit **une** tranche (~285 Ko), jamais l'index entier : la
contrainte qui a fait naître cette fonction — ne pas recharger plusieurs Go en
clair, sous peine d'OOM ([[amendements-legislatures-figees]]) — reste tenue. Un
refus coûte au pire un retéléchargement ; l'accepter coûte une législature
entière, silencieusement.

**2. Un répertoire de tranches à moitié écrit ressemble à un cache complet.**
`_write_cached_amendements_agreges` promettait dans sa propre docstring qu'« une
écriture interrompue laisse un cache traité comme absent, jamais un cache
incohérent ». Le code ne le tenait pas : il faisait `rmtree` puis `mkdir` puis
remplissait **en place**, donc pendant toute la boucle le répertoire existait à
moitié rempli. Or `index_dir.is_dir()` suffit à `_download_and_build_amendement_index`
pour conclure au cache-hit — il n'est alors jamais reconstruit — et chaque acteur
dont la tranche manque encore est lu comme « aucun amendement » (liste vide) au
lieu de « index indisponible » (`None`). C'est exactement la distinction dont
dépend le warning de `fetch_amendements_officiels`.

Le cas est atteignable, pas théorique : le step `Upload artifact amendements AN`
de `generate-data.yml` est en `if: always()`, donc un job interrompu publie
l'état partiel du disque, que les jobs consommateurs téléchargent ensuite.

Les tranches sont désormais écrites dans un répertoire temporaire, publié d'un
seul `os.replace`. C'est cette propriété — et elle seule — qui rend légitime le
contrôle sur une **tranche unique** de `_cache_amendements_au_format_uid`, dont
#447 demandait s'il constituait un défaut latent : l'échantillon unique est
correct **si** un répertoire qui existe est toujours complet, ce qui n'était pas
garanti. Réponse : le défaut n'était pas dans la garde, il était dans l'écriture
qu'elle présuppose.

**Alternative écartée** : contrôler *toutes* les tranches au lieu d'une. 650
fichiers relus à chaque décision de cache-hit, pour un invariant que l'écriture
peut garantir gratuitement — on paierait à chaque lecture le prix d'un défaut
d'écriture.

**Alternative écartée** : un fichier-marqueur « complet » écrit en dernier dans
le répertoire. Il faudrait le contrôler partout où le répertoire est jugé
valide, et rien n'empêcherait un lecteur futur d'oublier. Le `os.replace` rend
l'état incohérent **inobservable** au lieu de le rendre détectable.

### Un angle mort du signal de #447 lui-même

La §3c du quality gate — le signal ajouté par #452 pour surveiller précisément
ce défaut — ne regardait que les profils de `chambre` `AN`/`deputes` **avec
identité**. Or un profil peut cesser d'être compté sans cesser d'être publié :
au 19/08/2026, `jean-luc-melenchon` porte **18 721 amendements AN publiés** et
est sorti du champ de la section en passant à `chambre: "Senat"` avec `identite`
vide. Soit **2,3 % du corpus invisibles au signal même qui doit les surveiller**,
sur l'un des profils que #447 cite nommément — et s'il était revenu mixte, la
§3c n'aurait rien dit.

La §3c distingue donc désormais deux populations. Les compteurs « candidats AN »
et le signal de régression « `amendements[]` vide partout » gardent la
population dont on **attend** des amendements ; la mesure de couverture `uid`,
elle, porte sur tout profil qui en **publie**, quelle que soit sa `chambre`. Un
profil hors population AN n'entre dans le décompte que s'il a des amendements,
il ne peut donc jamais éteindre le signal de régression.

L'apport hors population AN est affiché sur sa propre ligne plutôt que fondu
dans les compteurs « candidats AN » — chaque nombre garde ainsi un sens unique.
Rendu sur le corpus de `a125e9e` : 207 candidats AN avec identité, dont 179 avec
amendements, **plus 1 profil hors population portant 18 721 amendements**, pour
810 552 amendements mesurés (791 831 avant) tous porteurs d'un `uid`.

*La §3c suit les amendements, pas la fiche.* Un dénominateur publié dépend de ce
qui est publié, pas de ce qui est classé (AGENTS.md §2.7).

### Reste ouvert

`_write_cached_scrutins` a la même forme d'écriture non atomique que son
homologue amendements (`rmtree` + `mkdir` + remplissage en place, autour de
`_scrutins_shard_path_acteur`). Aucune garde de format n'en dépend et rien ne
l'a signalé en pratique ; ce n'est **pas** corrigé ici, délibérément, pour ne pas
toucher au chemin des votes dans la foulée de [[normalisation-votes]]. Noté pour
que le prochain passage ne le redécouvre pas.

---
<a id="normalisation-votes"></a>
## Normaliser les votes : une liste partagée, un mapping, et deux invariants devenus des jointures (#432) (2026-08-19)

Un scrutin est **identique pour tous ses votants** — `texte`, `date`, `sort`,
`type_vote`, `source_url`. Seule la `position` est propre au membre. Le méta
complet était pourtant recopié dans chaque profil ayant voté : mesuré sur les
209 profils committés, **398 085 paires (membre, vote) pour 17 422 scrutins
distincts**, soit un facteur 22,8 ×.

### Résultat, mesuré sur régénération complète hors dépôt

| | avant | après |
| --- | --- | --- |
| `votes[]` dans les profils pivot | 179,8 Mo | **17,9 Mo** |
| `pivot_data/scrutins.json` | — | **8,1 Mo** |
| **total** | **179,8 Mo** | **26,0 Mo (−85,5 %)** |
| `cohesion_votes` des groupes | 6,23 Mo | **3,41 Mo (−45,3 %)** |

Les 398 085 paires sont **toutes** conservées, et 0 vote reste non résolu.

### Une liste partagée, pas une liste par profil

Les 4 104 scrutins qu'agrègent les profils de groupe sont **intégralement
inclus** dans les 17 422 des profils individuels : zéro scrutin propre aux
groupes. Une seule liste sert donc les deux, sans exception à gérer. Une liste
par profil, elle, ne dédupliquerait qu'à l'intérieur d'un profil — un scrutin
voté par 74 membres y resterait stocké 74 fois.

C'est la **seule dépendance entre fichiers** de `pivot_data/`, et elle est
assumée : un profil ne se lit plus seul pour ses votes. L'UI charge l'index une
fois par session (mémoïsé), `group_profile` une fois pour les 7 groupes.

### L'identifiant porte la législature

`an:<legislature>:<numero_scrutin>` — convention `<source>:<identifiant_source>`
du dépôt. La législature en fait partie parce que le numéro repart à 1 à chaque
législature (AGENTS.md §5) : un identifiant qui ne la porterait pas confondrait
le n° 1000 de la 16e et celui de la 17e. Elle est résolue par
[[resolution-legislature-votes]] avant toute construction d'identifiant.

### Le champ qui coûtait 12,1 Mo de `null`

`groupe_au_moment_du_vote` est propre au membre, donc légitime dans le mapping —
mais il n'est **jamais peuplé** (0 sur 398 085) et l'écrire quand même coûtait
**12,1 Mo, soit 40 % du mapping**. Il n'est donc écrit que s'il est renseigné,
et son absence signifie « non renseigné », exactement comme `null`.

C'est la **seule** exception à la convention « missing = null » d'AGENTS.md §4,
et elle est chiffrée plutôt que décrétée. Le reste du mapping ne l'imite pas :
`position` reste écrit, même à `null`.

### Ce qui n'est pas normalisé, et pourquoi

`raw_data/profiles` garde ses votes dénormalisés. C'est la couche source-near :
elle porte l'enregistrement tel que la collecte l'a produit, et c'est **d'elle**
que l'index est reconstruit. La normaliser ferait perdre la seule copie
complète, et rendrait l'index irreconstructible.

### Deux invariants sont devenus des jointures

`type_scrutin`, `type_vote`, `texte_lie_id` et `sort` ont migré vers l'index :
leur validation a suivi (`validate_scrutins_index`), et s'exécute désormais une
fois par scrutin au lieu d'une fois par votant.

Mais deux règles ne peuvent plus se vérifier sur un profil seul :

1. **qu'un `scrutin_id` référencé existe** — sinon le mapping pointe dans le vide ;
2. **la règle 4** (un 49.3 n'est jamais une position) — le `sort` est sur le
   scrutin, la `position` sur le profil.

`validate_profil(profil, scrutins_index=...)` les vérifie **si** l'index est
fourni, et les **saute** sinon — jamais ne les déclare valides par défaut. C'est
le prix de la normalisation, et il est explicite plutôt que caché.

### Un vote qu'on ne sait pas rattacher n'est ni supprimé ni deviné

`scrutin_id: null` + `scrutin_non_resolu` portant l'enregistrement complet
(date, texte, sort…). Ni supprimé — ce serait une perte —, ni doté d'une clé
inventée (AGENTS.md §2.5). Zéro cas sur les données actuelles ; le chemin existe
pour que le jour où il s'en présente un, il soit visible et non muet.
`validate_profil` refuse d'ailleurs un `scrutin_id` nul **sans** cet
enregistrement.

### Le repli de `_votes_de_legislature`, enfin retiré

`group_profile` conservait un vote sans législature pour **n'importe quelle**
législature de groupe (`v.get("legislature") or legislature`). C'était juste tant
que tous les groupes étaient de la 16e — les 89 687 votes concernés en venaient
tous — mais un groupe de la 17e les aurait absorbés.

Le repli n'est levé **qu'ici**, une fois la législature effectivement résolue
dans les données : le lever plus tôt aurait retiré ces 89 687 votes de la
cohésion de la 16e, ce qui aurait été une régression, pas une correction.

Un vote sans `scrutin_id` est désormais **écarté** de la cohésion — et compté,
puis remonté en `meta.warnings` du groupe. Une exclusion muette transformerait
un dénominateur en donnée fausse (AGENTS.md §2.7).

### Critère d'acceptation : `cohesion_votes` identique

Vérifié en régénérant les 209 pivots hors dépôt, puis en reconstruisant les 5
groupes AN à partir de leurs membres réels et en comparant les 12 champs de
décompte de chaque entrée :

| groupe | scrutins | écarts |
| --- | --- | --- |
| LFI-16 | 1 996 | 0 |
| LR-16 | 2 232 | 0 |
| REN-16 | 4 099 | 0 |
| RN-16 | 3 405 | 0 |
| SOC-16 | 814 | 0 |
| **total** | **12 546** | **0** |

L'ordre chronologique décroissant des entrées est conservé — il est simplement
relu dans l'index, la date n'étant plus dans l'entrée.

### Deux OOM évités, un rappel

La première version chargeait les 209 profils bruts (1,1 Go de JSON) pour les
reparcourir : tuée par l'OOM killer, comme l'index des amendements en #377 et
#392. La construction est donc **en flux et en une seule passe** — seuls les
17 422 scrutins distincts sont retenus, jamais les 398 085 paires. Pic mesuré :
**347 Mio de RSS, 26 s**.

### `votes_source` : le critère était déjà satisfait

L'issue demandait un `votes_source` cohérent avec les législatures réellement
présentes. Vérification faite : **`votes_source` n'existe pas dans le schéma
pivot** — il n'est lu que côté brut, pour décider d'ajouter la source AN à
`sources[]`, et ce test porte sur le domaine, pas sur les numéros de législature.
Les 86 profils bruts dont le texte libre annonce « législature 16 » à tort
n'affectent donc aucune donnée publiée. Constaté, non traité ici : c'est un
défaut de la couche de collecte, sans conséquence sur la couche publiée.

### Ordre des opérations

L'index doit exister **avant** la passe pivot : `generate_all_profiles --pivot`
le reconstruit lui-même depuis `--out-dir`, échoue franchement si un scrutin
reste irrésoluble, et fusionne additivement sauf `--no-merge`. Un run partiel qui
écraserait l'index laisserait les mappings des profils non retraités pointer
dans le vide — c'est la leçon de [[publication-scopee-artifacts]], transposée à
l'index.

<a id="resolution-legislature-votes"></a>
## Où vit la liste dédupliquée des scrutins : un fichier partagé, pas un par entité (#432) (2026-08-19)

La normalisation des votes (#432) sépare un scrutin — identique pour tous ses
votants — du mapping qui, seul, est propre au membre. Restait à trancher **où
vit la liste dédupliquée** : un fichier partagé, ou un par entité (candidat,
groupe, gouvernement) à l'image de `pivot_data/groupes/` et
`pivot_data/gouvernements/`, qui dédupliquent déjà chacun dans leur périmètre.

### Ce que la mesure a montré

Les 4 104 scrutins portés par les profils de groupe sont **intégralement
inclus** dans les 17 422 portés par les profils individuels : **aucun scrutin
n'est propre à un groupe**. Les ensembles sont strictement emboîtés, pas
disjoints.

C'est la conséquence directe de ce qu'est un scrutin : un vote de séance
publique auquel participent les membres de **tous** les groupes. Stocker la
liste par groupe réécrirait donc le même scrutin dans les sept fichiers — on
reconstruirait la duplication que #429 existe pour supprimer, au lieu de la
supprimer.

### La décision

Une liste partagée `pivot_data/scrutins.json`, et dans chaque profil le seul
mapping :

```json
"votes": [{"legislature": "16", "numero_scrutin": 3210, "position": "contre"}]
```

### La réserve qui a motivé la question, et pourquoi elle est levée

L'inquiétude était qu'une liste globale laisse croire que tout membre est
rattaché à l'ensemble des scrutins. Elle ne se matérialise pas : **le
rattachement est porté par le mapping, pas par la liste**. Un profil ne
référence que les scrutins où ce membre a voté, avec sa position. Le fichier
partagé est une table de **résolution**, jamais une affirmation de couverture.

Deux garde-fous en découlent, et ils sont contraignants :

- **§2.8** — la liste partagée ne doit jamais être lue comme un périmètre. Un
  consommateur qui inférerait la couverture d'un profil depuis elle produirait
  un regroupement trompeur.
- **§2.5** — chaque profil garde un champ de couverture explicite (les
  législatures réellement collectées), pour qu'une absence de vote ne se lise
  jamais comme « n'a pas voté ». C'est le sens de rendre `votes_source`
  dérivable du mapping plutôt que de le maintenir en texte libre.

Rappel de clé, cf. §*Résoudre la `legislature` d'un vote* : `numero_scrutin`
repart à 1 à chaque législature. L'identité d'un scrutin est la paire
`(legislature, numero_scrutin)` — même leçon que le `numero` des amendements
avant #440.

### Le coût assumé

Un profil **cesse d'être auto-portant** : lu seul, il ne dit plus de quel
scrutin il parle. C'est un vrai renoncement, qui touche #434 (versionnement) et
tout consommateur d'un fichier isolé. Il est accepté parce que l'alternative —
répliquer 6,1 Mo de scrutins dans chaque entité — annule le gain recherché.

### Séquencement

Le fichier **n'arrive pas avant le mapping qui le consomme**. Le poser d'abord
ajouterait ~8,7 Mo dupliquant ce que les profils portent déjà, le temps que la
migration suive. C'est aussi là que vit le vrai risque : la fusion additive
devra fusionner mapping et liste sans perdre une position.

## Résoudre la `legislature` d'un vote : deux mécanismes, pas un seul (#432) (2026-08-19)

`votes[].numero_scrutin` repart à 1 à chaque législature ([[votes-multi-legislature]],
#403) : la clé d'un scrutin est `(legislature, numero_scrutin)`. Toute
normalisation des votes en dépend — or **89 687 votes sur 398 085 (22,5 %),
répartis sur 83 profils, ne portent aucune législature**. Ils viennent du chemin
de collecte antérieur à #403, qui n'interrogeait qu'une législature et ne
renseignait donc pas le champ.

Le coût de ne rien faire est chiffrable : la clé compte alors **21 520** scrutins
« distincts » là où il n'y en a que **17 422** — 23 % de sur-comptage, et 4 098
scrutins stockés deux fois dans la liste dédupliquée qu'introduit #432. Combler
`legislature` est donc un préalable, pas un nettoyage de confort.

### Deux mécanismes, parce qu'ils ne sont pas de même nature

**1. Jointure sur un jumeau étiqueté.** Le même scrutin — même
`(numero_scrutin, date)` — apparaît ailleurs dans le corpus **avec** sa
législature. Ce n'est pas une inférence, c'est une **résolution** : la donnée
existe déjà, étiquetée, dans un autre profil. Mesuré : **4 098 des 4 104**
paires, **zéro ambiguïté** — aucune paire ne porte deux législatures différentes.

Ce mécanisme est nécessairement **global au corpus**, et c'est le point non
évident : un profil est soit entièrement sur l'ancien chemin de collecte, soit
entièrement sur le nouveau. Les deux formes ne coexistent jamais dans le même
fichier, donc le jumeau vit toujours **ailleurs**. Une résolution profil par
profil ne trouverait rien.

**2. Calendrier des législatures**, pour les 6 paires restantes. Datées du
25/11/2022 au 16/12/2023, elles sont en plein XVI, à plus de six mois de la
dissolution de juin 2024 : aucune zone grise. C'est une **dérivation**, et elle
est tracée comme telle (`derivee_du_calendrier`) — jamais présentée comme
collectée.

**3. Tout le reste échoue bruyamment.** Aucune valeur par défaut, aucun
rattachement à « la législature la plus probable » (AGENTS.md §2.5). Sont
irrésolubles : une date hors de tout intervalle connu, une date absente ou
malformée, un jumeau contradictoire, et une législature collectée absente du
calendrier — ce dernier cas signalant un calendrier à étendre, pas une donnée à
corriger.

### Le trou de cinq semaines

La XVI se termine à la dissolution du **09/06/2024**, la XVII ouvre le
**18/07/2024**. Les cinq semaines qui les séparent n'appartiennent à **aucune**
législature. Un vote qui y serait daté échoue, plutôt que d'être rattaché au
voisin le plus proche — c'est exactement le genre de trou qu'un repli silencieux
comblerait en inventant une donnée.

Pour la même raison la XVII est laissée **ouverte** (`fin=None`) plutôt que
bornée à une date lointaine : une borne factice se périmerait sans bruit le jour
d'une dissolution, et rattacherait alors des votes de la XVIII à la XVII.

### Le calendrier a été validé contre les données, pas seulement contre l'usage

Confronté aux **308 398 votes qui portent déjà leur législature** : aucun ne
tombe hors de l'intervalle de la sienne.

| Législature | Calendrier | Étendue réelle des votes |
| --- | --- | --- |
| 14 | 2012-06-20 → 2017-06-20 | 2012-07-03 → 2016-11-22 |
| 15 | 2017-06-21 → 2022-06-21 | 2017-07-04 → 2022-02-24 |
| 16 | 2022-06-22 → 2024-06-09 | 2022-07-11 → 2024-06-07 |
| 17 | 2024-07-18 → en cours | 2024-10-08 → 2026-07-21 |

Un test vérifie en outre que les dates d'ouverture concordent avec
`couverture_dossiers.LEGISLATURES_DEBUT`, déjà présent au dépôt : deux
calendriers qui divergeraient rattacheraient les votes et les textes à des
périodes différentes, sans que rien ne le signale.

### Résultat sur le corpus (19/08/2026, `e42631a`)

| | Scrutins | Paires (membre, vote) |
| --- | --- | --- |
| collectée | 17 416 | 308 398 |
| résolue par jumeau étiqueté | — | 89 671 |
| dérivée du calendrier | 6 | 16 |
| **irrésoluble** | **0** | **0** |

4 profils seulement dépendent d'une dérivation calendaire, pour 16 paires.

### Ce que la résolution ne change pas — vérifié

Les 89 687 votes sans législature se résolvent **tous** en « 16 ». Or
`group_profile._votes_de_legislature` conserve aujourd'hui un vote sans
législature pour **n'importe quelle** législature de groupe (`v.get("legislature")
or legislature`). Comme tous les groupes existants sont de la XVI, la cohésion
reste donc **identique** après résolution — c'est le critère d'acceptation de
#432, satisfait par construction et non par chance.

Ce repli cache en revanche un **défaut latent** : un groupe de la XVII
absorberait ces 89 687 votes de la XVI. Il ne sera retiré qu'avec la
normalisation elle-même — le retirer avant, sur des données non encore résolues,
supprimerait 89 687 votes de la cohésion de la XVI, ce qui serait une régression.

### Pourquoi une passe séparée, qui n'écrit rien

`src/audit_legislature_votes.py` ne modifie aucun fichier et rend un code de
sortie. Un chantier qui découvrirait ses cas irrésolubles **au milieu** d'une
migration de schéma devrait la défaire ; ici, on le sait avant de commencer.
Même raison d'être que [[budget-roster-mesure]] : mesurer avant de généraliser.

<a id="signal-uid-partiel"></a>
## Couverture `uid` partielle : ce qui manquait n'était pas un verrou, c'était un signal (#447) (2026-08-19)

Le défaut de #450 a mis deux jours à être identifié, et il a d'abord été pris
pour de l'instabilité de collecte. La raison tient en une phrase : **rien ne le
signalait**. Ni les logs d'extraction — les 8 shards imprimaient la ligne
attendue — ni `merge-and-pivot`, qui annonçait « Total of 8 artifact(s)
downloaded », ni la quality gate, qui ne regardait que le *nombre* d'amendements
et jamais leur forme. Le run se terminait en `success`, et le seul symptôme
visible était un volume qui montait.

C'est le même mode d'échec que #185 (« amendements[] vide partout, détecté par
aucune section ») et que l'index absent qui « fait disparaître les amendements en
silence » : ce dépôt traite une panne muette comme un défaut à part entière, pas
comme un désagrément.

### La mesure ajoutée (§3c)

Pour chaque profil pivot AN, la §3c compte désormais les amendements portant un
`uid`, et classe :

- **100 %** — profil sur la clé corrigée de #440 ;
- **0 %** — profil entièrement sur l'ancienne clé : en retard de correction, pas
  dupliqué. C'est une frontière de conquête, **pas** un fait faux ;
- **partiel** — les deux versions du même amendement cohabitent. L'entrée est
  comptée deux fois, ce qui fausse les dénominateurs publiés (AGENTS.md §2.7).

Seul le cas **partiel** déclenche un avertissement. Signaler aussi les profils à
0 % noierait le signal utile sous les 119 profils qui attendent simplement leur
régénération — c'est exactement ainsi qu'un signal cesse d'être lu.

Un taux global (`dont uid : N (X %)`) accompagne le tout : c'est lui qui dit si
une re-mesure de #429 est exploitable, le comptage d'amendements distincts
reposant sur l'`uid`. Au 19/08/2026 : 229 254 / 727 132, soit 31,5 % — donc
non exploitable en l'état.

### Pourquoi soft, et pas un refus d'écriture

L'issue demandait « un contrôle qui refuse d'écrire un profil dont les
amendements sont partiellement sans `uid` ». Deux raisons de ne pas le faire là :

1. **Le mélange ne naît pas à l'écriture.** Chaque job écrit un profil homogène ;
   c'est la fusion des artifacts qui réunit les deux versions (#450). Un garde
   posé sur l'écriture ne verrait jamais le cas qu'il vise.
2. **Pendant la remise en état, les profils mixtes sont attendus.** Un échec dur
   bloquerait précisément les runs censés les corriger — le quality gate refuse
   le commit, donc la correction ne serait jamais committée.

La §3c est soft dans son entier depuis #378, pour une raison voisine. Ce qui
manquait n'était pas un verrou, c'était un signal : la §3c le rend visible dans
la console, dans le résumé Markdown, et en `::warning::` GitHub Actions.

<a id="publication-scopee-artifacts"></a>
## Un artifact = la contribution d'un job : ce qu'on publie décide de ce qu'on peut corriger (#450) (2026-08-19)

Le run `32277443716` (19/08/2026, sha `698a882`, `overwrite_profiles=true` +
`roster_refresh_existing=true` + `roster_extraction_limit=0`) devait faire
passer les 205 profils de roster sur la clé `uid` de #440. Les 8 shards ont
tourné, chacun a écrit sa tranche, et le résultat committé est celui-ci :

| | avant | après |
| --- | --- | --- |
| profils à 100 % d'`uid` | 19 | 21 |
| profils à 0 % | 135 | 119 |
| profils **mixtes** | 6 | **22** |
| amendements committés | 620 208 | **727 132** |

Les profils régénérés ne sont pas passés à 100 % : ils sont devenus mixtes, et
le volume a **augmenté de 107 000 entrées**. Sur `antoine-armand`, 3 335
amendements = 1 289 périmés (présents à l'identique avant le run) + 2 046
corrigés : le profil corrigé n'a pas remplacé l'ancien, il s'y est **ajouté**.

### La cause : le `path:` de l'upload, pas la fusion

Chaque job d'extraction commence par un `actions/checkout` — `raw_data/profiles/`
y contient donc les ~209 profils committés, dont la quasi-totalité que ce job ne
touchera jamais. `extract-senat`, `extract-ue-officiel` et les 8 shards de
`extract-roster-groupes` uploadaient `path: raw_data/profiles/` : chaque artifact
publiait sa tranche fraîche **et** une copie périmée de tout le reste.

`extract-an` avait déjà, lui, un `path:` scopé (#344) — il n'était pas porteur,
mais **victime** : ses 3 profils mixtes qui ne figurent même pas au roster
(`edouard-philippe`, `jean-luc-melenchon`, `laurent-wauquiez`) ont été réinjectés
par les artifacts Sénat/UE, qui transportaient tout le répertoire.

De là, deux dégâts distincts et indépendants.

**1. Réinjection.** `merge_raw_dirs` fusionne les répertoires sources
additivement, slug par slug. Une version fraîche et une version périmée du même
profil donnent leur **union**, jamais un remplacement. `--no-merge` faisait
correctement son travail dans le job d'extraction, et se faisait défaire à
l'étape de fusion. Aucune correction de clé ne pouvait aboutir, quels que soient
les inputs — et le volume enflait à chaque run.

Ce n'est pas qu'une question de taille : un amendement compté deux fois n'est pas
une donnée incomplète, c'est un **fait faux**. Les dénominateurs publiés en
dépendent (AGENTS.md §2.7).

**2. Collision entre shards.** Les 8 artifacts du roster arrivent par `pattern`
+ `merge-multiple`, qui les **aplatit dans un seul dossier** : à nom de fichier
égal, un seul survit. Comme chaque shard publiait les 752 profils, les 8
entraient en collision sur chacun des noms. Nombre de profils régénérés lu dans
les logs de chaque shard ; trace d'arrivée au commit mesurée sur les fichiers
committés, un profil devenu **mixte** prouvant qu'une version fraîche l'a
atteint (les slugs présents aussi dans `candidats.json` sont exclus : leur
version fraîche vient d'`extract-an`, dont le `path:` était déjà scopé) :

| shard | régénérés (logs) | devenus mixtes |
| --- | --- | --- |
| 0 | 24 | 0 |
| 1 | 24 | 0 |
| 2 | 26 | 0 |
| 3 | 24 | 0 |
| 4 | 26 | 0 |
| 5 | 26 | 0 |
| 6 | 28 | **16** |
| 7 | 27 | 0 |

Un seul shard laisse une trace ; les sept autres, aucune. **177 profils de
travail réseau écrasés sans le moindre signal**, run après run. Que ce soit le
shard 6 qui l'emporte n'est décidé nulle part dans ce dépôt : c'est l'ordre
d'extraction concurrent de `download-artifact`.

Ce défaut-là est antérieur à #440 et indépendant de toute correction de clé — il
rendait le sharding du roster (#394) essentiellement décoratif. Personne ne
l'aurait vu sans une mesure profil par profil : le run se termine en `success`,
les 8 shards impriment la ligne attendue, et les logs de `merge-and-pivot`
annoncent « Total of 8 artifact(s) downloaded ».

### La décision

Rétablir la propriété manquante — **un artifact = la contribution d'un job** —
plutôt que d'arbitrer à la fusion.

`generate_all_profiles.py --manifest-out FICHIER` consigne le nom de fichier de
chaque profil brut réellement écrit, une ligne à la fois, sous verrou.
`.github/actions/publish-written-profiles` recopie ces seuls fichiers dans
`_publish/profiles/`, et c'est ce répertoire que les 4 jobs d'extraction
uploadent.

Traiter les deux dégâts **par construction plutôt que par arbitrage** est ce qui
motive ce choix : des jobs qui ne publient que leur propre tranche produisent des
jeux de fichiers **disjoints**. Il ne reste ni baseline périmée à réinjecter, ni
nom en collision à départager — le second défaut disparaît sans qu'aucune règle
ne le vise.

L'alternative envisagée — retenir à la fusion la version la plus récente en mode
écrasement — était plus simple mais laissait le problème entier pour tout autre
consommateur des artifacts, et faisait dépendre `merge-and-pivot` d'un input
appartenant à un autre job.

**Écriture au fil de l'eau, pas un dump final.** Les préemptions sont fréquentes
ici (#228) : un manifeste écrit à la fin serait perdu précisément quand il sert.
Tronqué au démarrage puis complété ligne à ligne, il laisse un préfixe **valide**
décrivant exactement ce qui est sur le disque — le principe de #443 appliqué à la
publication.

**Aucun repli sur `raw_data/profiles/`.** Manifeste absent (échec avant la
première écriture) → artifact vide, avec un `::warning::`. Un repli « publier
tout le répertoire » restaurerait le bug dans le seul cas où il est certain que
le job n'a rien produit.

### Ce qui a été vérifié avant de conclure

**La baseline n'a jamais eu besoin de transiter par un artifact.**
`merge-and-pivot` fait son propre `actions/checkout`, et `merge_raw_dirs` boucle
sur les fichiers **sources** : il ne réécrit que les slugs présents dans les
artifacts. Un profil qu'aucun job n'a touché conserve donc sa version committée
sans que rien ne le transporte. Le commentaire d'`extract-an` qui justifiait le
transport par les autres jobs (« merge-and-pivot reçoit toujours la baseline
complète via eux ») décrivait un besoin qui n'existait pas.

**L'union entre sources différentes reste intacte.** Un slug couvert par deux
jobs (candidat déclaré présent aussi au roster : `gabriel-attal`,
`marine-le-pen`, `bruno-retailleau`, `jerome-guedj`) reste l'union de leurs
contributions — les deux sont fraîches, la fusion additive y joue son rôle
légitime. C'est le seul cas où elle doit encore intervenir entre artifacts.

**`fresh_run` n'est pas la purge globale que son nom suggère** — et ne l'était
pas non plus avant #450. La purge de `raw_data/profiles/` a lieu sur les runners
d'**extraction** ; le checkout de `merge-and-pivot`, lui, n'est pas purgé. Un
profil qu'aucun job d'extraction ne couvre survit donc à un `fresh_run`.
Constaté, non traité ici.

**Le cas « rien écrit » était un angle mort d'`extract-an`.** Son `path:` scopé
désignait le chemin *attendu* d'un slug, pas une écriture *constatée* : une
extraction sans identité trouvée (statut `introuvable`) republiait la copie
périmée laissée par le checkout. Le manifeste ferme ce cas.

### Remise en état

Les 22 profils mixtes portent aujourd'hui les deux versions de chaque amendement.
Ils sont à **régénérer** après cette correction, pas à fusionner :
`src/audit_diff_profils.py` signalera une baisse sur `amendements`, qui est ici
le résultat attendu et non une perte.

<a id="telechargement-an-trois-modes-defaillance"></a>
## Régénérer l'existant : `--refresh-existing`, l'inverse de `--skip-existing` (#445) (2026-08-19)

Une correction de fond — la clé `uid` de #440 — ne concerne que les profils
**déjà écrits**. Le job `extract-roster-groupes` posait `--skip-existing` en
dur, et ce flag s'applique **avant** `--no-merge` : un run
`overwrite_profiles=true` sautait donc exactement les profils à corriger. Les
205 profils de roster écrits sur la clé écrasée étaient inatteignables par
toute combinaison d'inputs.

Deux issues supposées, toutes deux fausses à la vérification :

**« Le passage à pleine échelle refermerait le problème de lui-même. »** Non :
sans `--limit`, la condition `args.limit is not None` court-circuite le chemin
de rafraîchissement de #224 (`_select_candidats_couverture`), et
`--skip-existing` saute alors *chaque* profil existant. Un run à
`roster_extraction_limit=0` n'aurait rien corrigé — il aurait seulement étendu
la frontière de conquête de 205 à 752.

**« Lever `--skip-existing` suffit. »** Non plus : avec `--limit`, la sélection
retombe sur les N premiers du shard, et les profils couverts ne forment pas un
préfixe. Mesuré au 19/08/2026, sur les 8 shards de 94 membres :

| shard | couverts | index du dernier couvert |
| --- | --- | --- |
| 3 | 24 | 61 |
| 0 | 24 | 78 |
| 6 | 28 | **93** |
| 7 | 27 | **93** |

La cause est que **l'ordre de `raw_data/roster_candidats.json` n'est pas stable
dans le temps** : le fichier est régénéré par `generate_roster_candidats.py`.
Aucune borne positionnelle ne peut donc désigner les couverts. Le `--limit`
minimal qui les couvrirait tous vaut 94 — le roster entier, avec 547 profils
neufs en prime, c'est-à-dire trancher le dimensionnement de #429 par accident
plutôt que par décision.

### La décision

`--refresh-existing` : sélection strictement inverse de `--skip-existing`, ne
retenant que les candidats dont le profil JSON existe déjà. Appliqué **après**
`--shard` (chaque shard régénère sa tranche) et **avant** `--limit` (qui peut
encore borner un lot d'essai). Exposé par l'input `roster_refresh_existing`.

La combinaison avec `--skip-existing` est **refusée** (`SystemExit`) plutôt que
tolérée : les deux flags s'annulent exactement, et un job qui les recevrait
tournerait huit minutes sans écrire un seul profil, sans erreur — le genre de
panne muette que ce dépôt traite comme un défaut à part entière (cf. §*index
amendements figé au format hérité*).

`roster_refresh_existing` sans `overwrite_profiles` émet un `::warning::` : la
fusion additive conserverait les entrées de l'ancienne clé **à côté** des
corrigées, résultat pire que l'inaction, et indistinguable à l'usage.

### Ce qui a été vérifié avant de conclure

Les 4 slugs présents à la fois dans le roster et dans `candidats.json`
(`gabriel-attal`, `marine-le-pen`, `bruno-retailleau`, `jerome-guedj`) ne
perdent pas leurs interventions ni leurs dossiers législatifs malgré le mode
léger du job roster : `merge-and-pivot` fusionne les artifacts via
`merge_raw_dirs`, additif slug par slug, et non par écrasement de fichier.

`--skip-existing` reste le **défaut** : le déploiement progressif de #224 en
dépend, et le supprimer ferait repayer le réseau pour chaque profil déjà écrit
à chaque run.

## Téléchargement AN : trois modes de défaillance, un seul principe — ne jamais jeter un préfixe valide (#443) (2026-08-19)

**Contexte** : `data.assemblee-nationale.fr` ne tombe pas en panne, il **change
de mode de défaillance**, et assez vite pour qu'une mesure de quelques minutes
induise en erreur. Relevé le 18/08/2026 sur `Amendements_XV.json.zip` (648 Mo),
puis reconfirmé le 19/08 avant d'écrire une ligne de code :

| État | `Range` | GET séquentiel | Repli utile |
| --- | --- | --- | --- |
| 1 | fonctionne | — | reprise par segments — l'existant ([[amendements-range-download-legislature-isolation]], #241) |
| 2 | 0 octet à toutes les tailles (8 Kio à 32 Mio) | délivre | GET séquentiel, conservé comme préfixe |
| 3 | 0 octet | coupe à 13-25 Mo | **aucun** — seule l'attente fonctionne |

Le serveur annonce `Accept-Ranges: bytes` et un `Content-Length` correct dans
les trois états : **aucune sonde `HEAD` ne les distingue**, seul le transfert
lui-même le peut. C'est pourquoi l'arbitrage se fait en cours de
téléchargement et non par configuration.

Le téléchargeur ne connaissait que l'état 1. Son unique repli — réduire
`AMENDEMENTS_DOWNLOAD_CHUNK_BYTES` — porte sur une dimension qui n'est pas en
cause dans les états 2 et 3 : des segments de 8 Kio y échouent autant que des
segments de 32 Mo. Le repli existant était donc inopérant précisément quand il
aurait fallu qu'il serve. Trois chantiers ont buté sur ce symptôme en deux
jours ([[cache-cle-amendements-separee]] #424,
[[gouvernement-textes-non-ecrasement]] #427, et la reconstruction des index
figés de #440, arrêtée plusieurs heures), à chaque fois traité comme de
l'instabilité subie.

**Mesures du 19/08/2026** (rappelées ici parce qu'elles corrigent deux
affirmations de l'issue) :

- La panne du `Range` dépend du **décalage**, pas du fichier : une plage à
  l'octet 0 ou à 4 Mio est servie normalement (206 + 8192 octets) pendant que
  la même plage à 64 Mio, 100 Mio et 300 Mio ne rend rien. Sonder le support du
  `Range` en tête de fichier conclurait donc à tort qu'il fonctionne — l'arbitrage
  doit porter sur le décalage courant, ce que fait naturellement la boucle.
- Ce n'est pas un artefact HTTP/2 : `curl --http1.1` échoue identiquement
  (`transfer closed with 8192 bytes remaining to read`). Inutile de chercher un
  remède du côté du protocole.
- Le GET séquentiel a rendu 58,7 Mo puis 17,2 Mo sur deux essais successifs :
  le point de coupure est aléatoire, et **inférieur au préfixe déjà obtenu une
  fois sur deux**. D'où l'obligation de comparer les longueurs avant d'adopter.

**Le principe** : *ne jamais jeter un préfixe valide, d'où qu'il vienne.* Un
`Range` partiel, un GET séquentiel interrompu et une reprise réussie produisent
tous des préfixes du **même** fichier : le plus long doit gagner, quelle que
soit sa provenance. C'est le principe de #241 appliqué un cran plus bas, au
flux plutôt qu'au segment.

**Décision** :

1. **Écriture au fil de l'eau** (`_telecharger_flux`). Le
   `b"".join(resp.iter_content(...))` matérialisait tout le segment avant de
   l'écrire : une coupure en cours propageait l'exception depuis `iter_content`
   et relançait le segment **depuis son offset de départ**, perdant tout ce qui
   avait été reçu. Sous un mode de défaillance où la coupure tombe à un point
   aléatoire, cela annulait l'essentiel de ce qui arrivait.
2. **Lecture sur `resp.raw`, pas `iter_content`.** Corollaire mesuré, et non
   prévu : écrire au fil de l'eau ne suffit pas, car `iter_content` jette
   lui-même le tampon partiel. Sur un corps tronqué à 40 000 octets pour
   100 000 annoncés, `iter_content(chunk_size=N)` rend **0 octet** dès
   N ≥ 64 Kio et 39 936 octets pour N = 1 Kio, là où `raw.read()` rend les
   40 000. En cause le tampon de décodage d'urllib3 : `read(amt,
   decode_content=True)` accumule jusqu'à `amt` octets avant de rendre, et
   `_raw_read` lève `IncompleteRead` sur la lecture *suivante* — celle qui rend
   zéro octet — ce qui jette le tampon. Le corps devant rester non décodé, la
   requête pose `Accept-Encoding: identity` et un `Content-Encoding` autre est
   refusé bruyamment plutôt qu'écrit tel quel.
3. **Repli GET séquentiel** (`_tenter_get_sequentiel`), déclenché quand les
   plages ne rendent **aucun** octet après épuisement des tentatives. Le flux
   est écrit dans un fichier voisin `.seq` et **adopté seulement s'il est plus
   long** que le préfixe déjà détenu. Adopter le fichier entier plutôt que d'en
   recoller la fin sur l'existant évite par construction tout raccord entre deux
   versions distinctes de l'archive distante.
4. **Arbitrage à l'exécution**, jamais par configuration : chaque cycle retente
   les plages au décalage courant, puis le séquentiel. Un `Range` redevenu
   opérant est donc repris immédiatement, en repartant du préfixe déjà obtenu.
5. **État 3 traité explicitement.** Quand un cycle complet ne rend pas un seul
   octet, on **attend** (`AMENDEMENTS_SOURCE_STALL_WAIT_SECONDS`, 30 s) au lieu
   de marteler, jusqu'à `AMENDEMENTS_SOURCE_STALL_MAX_CYCLES` (3), puis on lève
   `SourceAmendementsIndisponibleError` — dont le message dit que **la source
   est indisponible**, pas que le téléchargement a échoué. La distinction n'est
   pas cosmétique : elle change ce que fait la personne qui lit le log — dans un
   cas elle relance, dans l'autre elle attend ou passe par un index figé. Les
   deux bornes sont basses par défaut (budget CI) et exposées en CLI par
   `build_amendements_index_figees.py` (`--stall-cycles`,
   `--stall-wait-seconds`), car hors CI l'attente longue est le seul remède qui
   fonctionne.
6. **Une 4xx n'est pas une source indisponible.** Un 404/403 ne rend aucun
   octet lui non plus ; sans garde-fou il aurait été rapporté comme « source
   indisponible », envoyant attendre un rétablissement qui n'arriverait jamais.
   `_est_erreur_http_definitive` le fait remonter tel quel (4xx hors 408/429).
7. **Pas de troncature silencieuse.** Une réponse 200 n'est tenue pour le
   fichier entier que si le flux s'est achevé **sans erreur** ; sinon elle n'est
   qu'un préfixe de plus. L'ancien code posait `total_size = len(chunk)` sur
   toute réponse 200, ce qui aurait déclaré complète une archive tronquée. Le
   contrôle de taille finale est conservé.

**Alternative rejetée** : choisir le mode par configuration (une option
`--sequential`, ou un réglage déduit d'une sonde initiale). Le mode de
défaillance change en quelques minutes — j'ai moi-même conclu à tort que « la
taille de segment était la cause », sur la foi de six mesures prises dans une
fenêtre où le `Range` fonctionnait encore. Un réglage posé d'après un
diagnostic ponctuel serait faux la plupart du temps, et faux silencieusement.

**Vérification** : 11 tests contre un **vrai serveur HTTP local** simulant les
trois états (`tests/test_amendements_download_modes.py`) — pas des doubles de
`requests`, qui n'auraient prouvé que le chemin nominal : ce qui est en cause
est le comportement du transfert lui-même (corps tronqué par rapport au
`Content-Length` annoncé, connexion fermée en cours de flux), que seul un vrai
serveur reproduit. Les six protections ont été neutralisées une à une, chacune
fait échouer son test — y compris la restauration littérale du
`b"".join(iter_content(...))` d'origine. 1409 tests verts.

Vérifié aussi contre la source réelle : `Amendements_XIV.json.zip` téléchargée
intégralement (103 716 698 octets, archive zip valide) par le chemin nominal.

**Ce que ceci ne résout pas** — et il vaut mieux le dire que le laisser croire :

- Dans l'état 3, **aucun repli réseau ne fonctionne.** Le correctif ne peut
  qu'attendre plus intelligemment et échouer en le disant. Pire, le repli
  séquentiel redémarre à l'octet 0 (le `Range` étant mort, aucune reprise n'est
  possible) : son utilité décroît à mesure que le préfixe grandit, et sur une
  archive de 648 Mo dont les transferts séquentiels cassent vers 20-60 Mo, elle
  est nulle en pratique. Pour les artefacts **immuables** — index figés des
  législatures closes — la vraie réponse reste de ne pas avoir à les
  retélécharger ([[amendements-legislatures-figees]]).
- Le chemin CI supprime toujours l'archive partielle en cas d'échec (`try/finally`
  de #264), donc n'en tire aucun bénéfice de reprise d'un run à l'autre. Ce
  choix reposait sur une prémisse devenue fausse (« `_download_amendements_zip`
  réécrit toujours depuis zéro », vrai avant la reprise entre invocations de
  #241). Le corriger échange du volume de cache CI contre de la reprise : arbitrage
  à mesurer, noté dans `ROADMAP.md` plutôt que tranché ici en passant.

---
<a id="overwrite-profiles-sans-purge-cache"></a>
## `overwrite_profiles` : écraser les profils sans purger le cache (2026-08-19)

**Contexte** : la correction de clé des amendements (#440, préalable à #431)
impose un premier run **en écrasement**. Les profils committés n'ont pas de
champ `uid` ; la nouvelle clé de fusion est `uid or source_url or (numero,
texte_vise, date)`. Le même amendement reçoit donc deux clés différentes avant
et après, et la fusion additive le compte **deux fois**. Vérifié en appelant
`merge_lists_by_key` : un amendement en entrée de chaque côté, deux en sortie.

Sur 4,2 millions de paires, cela doublerait le volume et fausserait tous les
comptages, agrégats de groupe compris.

**Le piège** : le seul mode d'écrasement exposé en CI était `fresh_run`, qui
fait aussi `rm -rf .cache`. Or purger le cache oblige à re-télécharger les
archives AN — ~300 Mo — auprès d'une source dont l'indisponibilité a bloqué
trois chantiers en deux jours ([[cache-cle-amendements-separee]] #424,
[[gouvernement-textes-non-ecrasement]] #427, et la reconstruction des index
figés de #440, arrêtée plusieurs heures). On aurait échangé un risque de
doublons contre un risque de run entièrement bloqué.

**Décision** : nouvel input `overwrite_profiles`, qui pose `--no-merge` sans
rien purger.

| `fresh_run` | `overwrite_profiles` | `--no-merge` | purge cache | `--merge-existing` |
| --- | --- | --- | --- | --- |
| false | false | non | non | oui |
| false | **true** | **oui** | **non** | non |
| true | false | oui | oui | non |

`overwrite_profiles` agit aussi sur les profils de groupe (`--merge-existing`
désactivé) : réintégrer des membres depuis un fichier produit avec l'ancien
schéma ramènerait précisément les données que l'écrasement vise à remplacer.

**Reconstruction par le retry** : `retry-generate-data.yml` déduit
`overwrite_profiles` de la combinaison « `--no-merge` présent dans la commande
d'extraction **et** `fresh_run` faux » — les deux seuls inputs qui posent ce
flag. Sans cela, un run préempté serait relancé en fusion additive, soit
exactement le scénario de doublons que ce mode évite. La déduction s'appuie sur
`an_log` et doit donc figurer **après** sa définition ; la placer avant la
rendrait toujours fausse, silencieusement — un test vérifie cet ordre.

**Garde-fous** : `tests/test_ci_cache_paths.py` vérifie qu'aucun step de
nettoyage n'est conditionné à `overwrite_profiles`, que tous les `MERGE_FLAG`
considèrent les deux inputs — un job qui n'en regarderait qu'un fusionnerait
pendant que les autres écrasent, produisant des doublons sur ce seul job — et
que le retry reconstruit puis transmet l'input. Vérifiés discriminants par
sabotage des trois invariants.

**Contrôle associé** : `src/audit_diff_profils.py` compare les profils
régénérés à une référence git, par profil et par champ. Écraser abandonne la
mémoire de la fusion additive, qui protège des collectes ratées — les 283
textes de la XV d'Édouard Philippe lui doivent leur survie. Le contrôle porte
sur le détail et non sur les totaux : la correction de clé fait exploser les
amendements, et ce gain masquerait n'importe quelle perte de votes.

---
<a id="amendements-cle-uid"></a>
## Amendements : la clé du store est l'`uid`, jamais le `numero` (préalable à #431) (2026-08-18)

**Contexte** : #431 (sous-issue de l'épic volumétrie #429) prescrivait de
normaliser `amendements[]` en écrivant dans chaque profil un mapping
`{numero, role_signataire}` pointant vers une liste dédupliquée, en réutilisant
`_aggregate_amendements_index` — le mécanisme qui produit déjà les index des
législatures figées. En vérifiant le point de vigilance noté dans l'issue
(« le `numero` doit rester unique dans la portée choisie »), il s'est avéré
que **la clé était déjà fausse, et l'est dans les données committées**.

**Mesure — archive AN de la législature 17, 18/08/2026** :

| | Valeur |
| --- | --- |
| Amendements dans l'archive (uid distincts) | 121 805 |
| `numeroLong` distincts | 30 616 |
| Amendements perdus par un store keyé `numero` | 91 189 (74,9 %) |
| Paires (acteur, amendement) réelles | 3 216 366 |
| Paires résolues vers un AUTRE amendement que le leur | 1 302 198 (40,5 %) |

Le `numeroLong` de l'AN **repart à chaque texte** : `AE12` est porté par 7
textes sans rapport, `1` et `10 (Rect)` par des dizaines. La législature 14 est
pire encore : 167 420 amendements pour 22 159 `numeroLong` distincts.

Ce n'est pas une simple perte de volume. Un store `numero -> amendement` garde
le premier amendement rencontré ; toutes les références des autres résolvent
alors vers lui, et le profil affiche un amendement **attribué au mauvais
texte, à la mauvaise date, avec le mauvais sort** — un fait faux, indiscernable
d'un fait correct à la lecture (AGENTS.md §2.2, §2.5). Constaté sur les profils
committés : pour les trois membres dont la législature 17 a été collectée
fraîchement, le nombre d'amendements du profil est **exactement** leur nombre de
`numero` distincts, pas leur nombre d'amendements (christophe-bentz : 4 066 dans
le profil, 7 261 dans l'archive).

**Décision** : la clé du store dédupliqué et des références par acteur devient
l'`uid` AN de l'amendement (`AMANR5L17PO59047BTC1376P0D1N000012`), présent sur
chaque amendement des deux schémas AN — moderne (XV/XVI/XVII) et legacy XIV
(vérifié : 167 420 amendements, 167 420 uid distincts). C'est exactement le
choix déjà fait pour les scrutins (`_build_scrutins_index` : store `uid ->
scrutin`, index `acteurRef -> [[uid, position]]`), dont l'uid porte lui aussi la
législature et reste unique toutes législatures confondues. La leçon était donc
**déjà écrite dans ce fichier** — « Déduplication par `uid`, jamais par
`numero` : le numéro de scrutin AN repart de 1 à chaque législature » (voir
[[votes-multi-legislature]]) — mais n'avait pas été transposée aux
amendements, où la collision est pourtant plus large encore : le numéro d'un
amendement ne repart pas seulement à chaque législature, il repart à chaque
texte. `numero` reste
collecté — il est affichable — mais n'identifie plus rien.

**Décision 2 — un index hérité est refusé, jamais relu.** `_load_frozen_amendement_index`
et `_read_cached_amendements_acteur` vérifient que les références portent un
`uid` (`_index_par_acteur_au_format_uid`) et traitent un index au format
`{numero, ...}` comme un cache absent : le pipeline reconstruit. Servir un tel
index serait pire que ne rien servir, puisque rien à l'usage ne distinguerait
ses enregistrements d'enregistrements corrects.

**Index figés reconstruits** (`build_amendements_index_figees.py`) :

| Législature | Amendements avant (clé `numero`) | Après (clé `uid`) | Facteur | Liens acteur/amendement | Poids committé |
| --- | --- | --- | --- | --- | --- |
| 14 | 21 624 | **154 296** | × 7,1 | 1 338 262 (inchangé) | 4,4 + 4,1 Mo gz |
| 15 | 68 030 | **307 644** | × 4,5 | 3 098 642 (inchangé) | 5,7 + 10,6 Mo gz |
| 16 | 58 305 | **162 240** | × 2,8 | 3 310 514 (inchangé) | 3,2 + 11,1 Mo gz |

Le nombre de liens ne bouge pas — ce sont les mêmes signatures — mais ils
pointent désormais chacun vers le bon amendement. Tous restent très en deçà de
la limite GitHub de 100 Mo par blob. Le facteur d'écrasement varie fortement
d'une législature à l'autre (× 2,8 à × 7,1) : il dépend du nombre de textes sur
lesquels les numéros se réutilisent, pas d'un taux fixe — citer une moyenne
serait trompeur.

Contrôle de non-régression, via le vrai chemin de lecture
(`_load_frozen_amendement_index` -> cache -> `_read_cached_amendements_acteur`),
sur le plus gros signataire de chaque législature :

| Législature | Acteur | Amendements résolus | `numero` distincts | Exemple de collision |
| --- | --- | --- | --- | --- |
| 14 | PA608416 | 12 216 | 3 871 | n° 8 porté par 57 textes |
| 15 | PA719318 | 25 116 | 9 358 | n° 185 porté par 24 textes |
| 16 | PA722142 | 17 272 | 11 438 | n° AE1 porté par 2 textes |

**Conséquence pour #431** : son constat de départ (4 246 026 paires pour 67 058
amendements distincts, facteur 63,3 ×) est mesuré sur des données écrasées, et
son critère d'acceptation (« `amendements` sous 200 Mo sur 752 profils ») doit
être redérivé une fois les données correctes — corriger la clé **augmente** le
nombre réel de paires. La normalisation elle-même reste à faire, sur cette base
saine, et le mapping y référencera l'`uid`.

**Et cette correction alourdit les profils, elle ne les allège pas.** Un profil
ne contenait qu'une entrée par `numero` distinct (les références en doublon
résolvaient vers le même enregistrement, que la fusion dédoublonnait ensuite) ;
il en contient désormais une par signature réelle. Le facteur mesuré va de
1,7 × (législature 17 : 3 216 366 paires réelles contre 1 914 168 distinguables
par `numero`) à 3,2 × (PA608416 en législature 14 : 12 216 amendements contre
3 871 numéros). Les `amendements[]` pesant déjà 81 % du volume d'un profil,
c'est l'ensemble du jeu de profils qui croît d'autant à la prochaine
régénération complète. #431 n'en devient que plus urgent : c'est lui qui rend
ce volume tenable, et il travaille maintenant sur des faits corrects plutôt que
sur un échantillon écrasé.

**Alternative rejetée** : garder `numero` en le qualifiant par le texte
(`(legislature, texte_vise, numero)`). Trois défauts : `texte_vise` est tantôt
un code source (`PIONANR5L15B4852`), tantôt un titre résolu selon l'état de
l'index des dossiers au moment de la collecte — la clé changerait donc d'un run
à l'autre pour le même amendement ; le triplet reste non unique (396 collisions
mesurées sur la seule législature 17) ; et il pèse plus lourd que l'uid qu'il
cherche à éviter.

**Alternative rejetée** : un identifiant synthétique compact (entier de
position) pour alléger le mapping de #431. Non stable d'une reconstruction à
l'autre, donc incompatible avec la fusion additive et `--skip-existing`, qui
doivent pouvoir rapprocher deux collectes successives.

<a id="profils-json-compact"></a>
## Profils écrits en JSON compact, groupes et gouvernements indentés (#433) (2026-08-18)

**Contexte** : troisième levier de l'épic volumétrie #429. La mesure sur les 752
profils du roster complet (`audit_volumetrie_profils.py`,
`audit/volumetrie_roster_752.md`) donne 8 093 Mo sur disque pour 5 263 Mo de
contenu réel : **2 830 Mo, soit 35 %, ne sont que de l'indentation**.

C'est le seul levier de l'épic qui ne demande aucun arbitrage : aucun champ
touché, aucun schéma modifié, aucun consommateur à adapter. Tout le pipeline
relit ses fichiers par `json.load()` / `json.loads()` — vérifié sur l'ensemble
des lecteurs, aucun ne procède ligne à ligne, et rien dans `scripts/` ni dans
les workflows ne fait de `grep`/`wc -l` sur un profil.

**Décision** : `json.dumps(..., separators=(",", ":"))` pour les profils
individuels — `raw_data/profiles/` et `pivot_data/profiles/` — via l'helper
partagé `src/json_io.py`. Restent indentés `pivot_data/groupes`,
`pivot_data/gouvernements`, `pivot_data/partis`, les rosters, les rapports
d'audit et le checkpoint de génération : 9,8 Mo au total, effectivement relus à
la main lors des audits.

`ensure_ascii=False` est conservé : l'échappement `\uXXXX` coûterait 6 octets
par caractère accentué et annulerait une part du gain sur des profils français.

### Contrepartie assumée : la lisibilité du diff git

Un profil compact apparaît comme **une seule ligne changée**. L'objection est
réelle, mais l'avantage était déjà perdu : le commit de données du 2026-08-18
affichait 16,6 millions de lignes modifiées sur 239 fichiers — un diff que
personne ne lit. Les profils de gouvernement, eux, ont un vrai intérêt à rester
lisibles, et ils pèsent 0,33 Mo.

### Ce qui aurait pu casser, et pourquoi ça ne casse pas

`preserve_stable_freshness_timestamps` et la comparaison de contenu de #343
travaillent sur la structure **déjà désérialisée** :
`_pivot_content_fingerprint` re-sérialise avec `sort_keys=True` après avoir
retiré `meta.genere_le` et `sources[].synchro_le`. La détection « contenu
identique » est donc indifférente au formatage — un profil indenté sur disque
face à une régénération compacte reste reconnu comme inchangé, et les
horodatages ne ré-avancent pas. Couvert par
`tests/test_json_io.py::test_freshness_preservee_quand_l_ancien_fichier_etait_indente`.

### Pas de commit de reformatage

Les profils déjà commités restent indentés jusqu'à leur prochaine
régénération, que le pipeline effectue de toute façon à chaque run. Un commit
de reformatage en masse serait contre-productif pour l'objectif de l'épic :
il ajouterait ~5 Go de nouveaux blobs à l'historique **sans** retirer les
anciens, donc ferait grossir `.git`. Le gain se matérialise fichier par
fichier, à mesure que le pipeline les réécrit.

**Vérification sur données réelles** : les 378 profils présents dans le dépôt
passent de 2 282 Mo à 1 505 Mo (**34,1 %**), avec égalité sémantique
(`json.loads` avant/après) sur chacun — la projection à 35 % est confirmée.

---
<a id="gouvernement-textes-initiateurs"></a>
## Profils de gouvernement : le lien ministre → texte (#435) (2026-08-18)

**Contexte** : `textes[]` d'un profil de gouvernement portait 8 champs, dont
aucun ne désignait un membre. On savait qu'un gouvernement avait porté 725
textes, jamais **quel ministre avait déposé lequel** — le pendant manquant de
`role_signataire` pour les amendements. La donnée existait dans la source
(`initiateur.acteurs.acteur[].acteurRef` du dump AN) et était jetée par
`parse_dossier_gouvernemental`. Repéré en cadrant #429, hors de son périmètre
(un enrichissement, pas une optimisation de volume).

**Mesuré sur les trois archives (XV/XVI/XVII), 725 textes rattachés à un
gouvernement** :

| | Valeur |
| --- | --- |
| Textes avec au moins un initiateur | 723 / 725 |
| Textes sans initiateur | 2 |
| Liens initiateur → texte (après dédoublonnage) | 1213 |
| Liens résolus vers un `membre_id` | 556 |
| Acteurs initiateurs distincts | 77 |

**Décision 1 — extraction brute au niveau du parseur, résolution au niveau du
profil.** `gouvernement_textes.parse_dossier_gouvernemental` rend
`initiateurs_acteur_refs` (liste d'`acteurRef`, ordre de la source,
dédoublonnée) ; `gouvernement_profile.py` seul résout vers un `membre_id`,
parce que lui seul connaît la composition du gouvernement. Même séparation que
partout ailleurs dans ce module : le parseur reste pur et testable sans la
composition ministérielle.

**Décision 2 — résolution restreinte aux membres du gouvernement concerné.**
L'index `acteurRef -> membre_id` est construit depuis les seuls profils retenus
dans `membres[]` (l'`acteurRef` d'un profil pivot n'existe que dans
`identite.source_url`, voir `gouvernement_roster.acteur_ref_depuis_profil`).
Hors de `membres[]`, l'`acteurRef` brut est conservé avec `membre_id = null` :
un `acteurRef` peut désigner un co-signataire ou un ex-ministre — c'est
exactement la source des ~15 % de faux positifs qui avaient fait écarter cette
chaîne comme signal d'origine (voir [[gouvernement-textes-statut]]). Ici elle
ne sert qu'à dire qui a déposé, jamais de quelle origine est le texte. Deux
profils partageant un même `acteurRef` sont un conflit d'identité non tranché :
aucun `membre_id` résolu, warning explicite.

657 des 1213 liens restent sans `membre_id`, essentiellement des ministres sans
profil pivot dans le dépôt (dont les 7 Premiers ministres déjà connus pour ce
manque). C'est une couverture partielle assumée, pas un défaut à combler par
approximation : la référence AN reste vérifiable dans la source.

**Décision 3 — `initiateurs = null`, jamais `[]`, pour les 2 textes sans
initiateur.** Une liste vide affirmerait qu'aucun ministre n'a porté le texte,
alors que le fait constaté est que la source ne le dit pas (AGENTS.md §2.5).
`[]` est explicitement **refusé** par `validate_profil_gouvernement`, pour que
l'absence ne puisse pas être écrite des deux façons.

**Décision 4 — clé obligatoire, et `membre_id` vérifié contre `membres[]`.**
`initiateurs` entre dans `REQUIRED_TEXTE_KEYS` : un texte généré par une
version antérieure du pipeline est signalé, pas silencieusement accepté sans
lien. Le validateur refuse aussi un `membre_id` qui ne correspond à aucune
entrée de `membres[]` — un lien membre → texte doit pointer vers un membre du
profil (AGENTS.md §2.2). Les 10 profils de `pivot_data/gouvernements/` ont été
régénérés en conséquence ; le diff est purement additif (aucun champ existant
modifié).

**Coût réel, plus élevé que l'estimation de l'issue** : 403,7 Kio → 539,3 Kio
(+135,6 Kio, +34 %) pour les 10 profils. L'issue annonçait « quelques
kilo-octets » ; un objet `{acteur_ref, membre_id}` indenté pèse ~90 octets et
il y en a 1213. L'ordre de grandeur reste négligeable en absolu (0,53 Mo pour
l'ensemble des profils de gouvernement, à comparer aux 7,9 Go mesurés en #429
sur les profils individuels), mais l'écart est noté pour ne pas laisser croire
que le champ est gratuit.

**Alternative rejetée** : porter le `nom` du ministre dans chaque entrée
`initiateurs[]`. Redondant avec `membres[]`, qui est joignable par `membre_id`,
et sans réponse pour les initiateurs non résolus — pour ~1213 duplications de
chaîne. Le nom se lit côté présentation.

**Alternative rejetée** : une table de mapping unique à la racine du profil
plutôt qu'une liste par texte. `textes[]` est déjà l'unité de lecture du profil
(un texte, son statut, son 49.3) ; une table séparée obligerait `web/` à faire
la jointure pour afficher ce que le texte porte lui-même, sans rien économiser
(le même nombre de liens y figure).

**Non fait** : `mandatRef`, présent à côté d'`acteurRef` dans la source, n'est
pas conservé — il n'ajoute rien au lien membre → texte tant que les mandats du
profil ne sont pas indexés par cette référence.

<a id="gouvernement-textes-non-ecrasement"></a>
## Profils de gouvernement : ne jamais réécrire sur une collecte incomplète, et cache dossiers dédié (#427) (2026-08-18)

**Contexte** : `merge-and-pivot` était le seul job de `generate-data.yml` sans
aucun `actions/cache`. Il re-téléchargeait les trois archives de dossiers
(~33 Mo) à chaque run — repéré en validant [[cache-cle-amendements-separee]]
(#424), qui avait supprimé les 438 Mo des jobs d'extraction et rendu ce résidu
visible.

**Mais le coût réseau n'était pas le problème.** `generate_gouvernement_profiles.py`
**écrase** les profils (`out_path.write_text`) ; `preserve_stable_freshness_timestamps`
(#343) ne préserve que les horodatages. Or `fetch_dossiers_gouvernementaux()`
est non-fatal : en cas de coupure réseau il rend `{"dossiers": []}` avec un
warning. L'enchaînement complet était donc :

1. coupure réseau sur `data.assemblee-nationale.fr` — observée 5 fois sur la
   seule archive XV lors du run `32136438841` ;
2. les 10 profils réécrits avec `textes: []` ;
3. le quality gate ne traitant ce cas qu'en **avertissement**, le commit reste
   autorisé ;
4. commit, push, puis publication par le déploiement automatique de #416.

**725 textes** auraient été perdus et mis en ligne — dont les 282 de Philippe II
et les 195 de Castex, que #400 venait de faire apparaître. Aucun incident ne
s'était produit (vérifié sur l'historique de `gouvernement-CASTEX.json` : les
`textes=0` antérieurs au 18/08 datent d'avant #400), mais les deux conditions
coexistaient.

### Correctif 1 — refus de réécrire (le vrai)

`fetch_dossiers_gouvernementaux()` retourne désormais `legislatures_ingerees`.
Ce n'est pas une information d'affichage : c'est **le seul moyen pour l'appelant
de distinguer « zéro dossier constaté » de « collecte incomplète »**. Sans elle,
les deux cas sont indiscernables.

`generate_all()` abandonne alors toute écriture si une archive manque, et rend
la sentinelle `COLLECTE_INCOMPLETE`. Les profils déjà committés restent en
place, intacts. Un zéro non mesuré n'est pas une donnée (AGENTS.md §2.5).

Le contrôle porte sur **toute** archive manquante, pas seulement sur l'échec
total : perdre la seule XV, c'est perdre les 282 textes de Philippe II.

Deux pièges rencontrés :

- **Sentinelle, pas code de retour.** `generate_all()` retourne un *compte*
  d'échecs. Une première version signalait la collecte incomplète par la valeur
  `2` — exactement deux gouvernements en échec l'aurait alors déclenchée à tort.
  D'où un objet dédié, converti en code de sortie `2` seulement dans `main()`.
- **Un test existant assertait le comportement dangereux.**
  `test_generate_all_dossier_fetch_failure_reported_via_warnings` vérifiait que
  le profil ÉTAIT écrit avec `textes == []`. Il fallait le réécrire, pas
  l'adapter.

Côté workflow, le step est `continue-on-error: true` : faire échouer tout le
job priverait le run du commit des profils de candidats et de groupes, qui eux
sont corrects. L'échec reste visible dans la liste des steps.

### Correctif 2 — filet du quality gate

Le refus de réécrire supprime la cause connue. Le gate attrape la **signature**,
quelle qu'en soit l'origine — bug de collecte, régression de parsing, fusion
fautive : **tous** les gouvernements couverts à `textes[] == 0` simultanément
devient un échec **dur**.

Le critère porte sur la simultanéité, jamais sur un gouvernement isolé : un
gouvernement couvert peut légitimement n'avoir porté aucun texte — Philippe I
n'en a qu'un. Et il exige au moins deux gouvernements couverts, faute de quoi
« tous à zéro » ne distingue plus rien.

C'est un contrôle **sans accès à l'historique git** : le gate ne compare rien à
l'état précédent, et lui ajouter cette plomberie pour ce seul besoin n'était pas
justifié.

### Correctif 3 — clé de cache dédiée aux dossiers

`.cache/dossiers_an` sort de `public-data-cache-an-*` et reçoit
`public-data-cache-dossiers-<semaine>`, partagée par `extract-an`,
`extract-roster-groupes` et `merge-and-pivot` (qui gagne au passage le step
`week` qui lui manquait).

Restaurer `public-data-cache-an-*` depuis `merge-and-pivot` aurait embarqué
`scrutins_an` : plusieurs centaines de Mo pour en utiliser 46.

Contrairement au défaut de #424, il n'y a ici **aucune dissociation** entre
producteur de contenu et écrivain de clé — les trois jobs téléchargent et
consomment les mêmes archives, donc le premier qui sauvegarde suffit.

`tests/test_ci_cache_paths.py` s'étend en conséquence : les jobs lisant les
dossiers doivent tous les cacher, et la clé dédiée ne doit pas retomber sous la
clé AN.

**Vérification** : les trois protections ont été neutralisées une à une, chacune
fait échouer ses tests. 1310 tests verts.

---

<a id="cache-cle-amendements-separee"></a>
## Cache CI : clé propre aux amendements, et chemins énumérés pour les jobs AN (#424) (2026-08-18)

**Contexte** : `extract-amendements-an`, `extract-an` et `extract-roster-groupes`
partageaient la clé `public-data-cache-an-<semaine>` avec `path: .cache`. Le
premier étant séquencé en tête, il écrivait la **clé exacte** de la semaine ;
les deux autres faisaient alors un *exact key hit*, et `actions/cache` saute sa
sauvegarde post-job dans ce cas.

#412 §2.3 avait posé l'hypothèse sans la corriger, faute de preuve — décision
qui s'est révélée juste, puisqu'elle a produit un critère d'acceptation net.
Le run `32136438841` a fourni la preuve :

```
extract-an (gabriel-attal) | Post Run actions/cache@v5
  Cache hit occurred on the primary key public-data-cache-an-2026-W34, not saving cache.
```

sur **les 8 shards `extract-an` et le shard `extract-roster-groupes`**.

**Coût mesuré sur ce seul run** (rollout progressif, 1 shard roster) : 11
téléchargements de l'archive dossiers XV (14,5 Mo), 9 de la XVI (8,7 Mo) et 8
des scrutins XVII (25,1 Mo), soit **~438 Mo re-téléchargés**. À pleine échelle
du roster, 16 jobs seraient concernés, donc **~780 Mo par run**.

Le coût avait **augmenté après** la rédaction de la réserve : [[dossiers-multi-archives-origine-document]]
(#400) a ajouté les dossiers XV/XVI et #403 les scrutins XIV–XVII à `.cache`.
Une réserve laissée en l'état vieillit mal quand d'autres chantiers alimentent
le répertoire qu'elle concerne.

**Décision** :

- `extract-amendements-an` reçoit sa propre clé `public-data-cache-amendements-*`,
  avec `path: .cache/amendements_an` — le seul répertoire qu'il produise.
- `extract-an` et `extract-roster-groupes` gardent `public-data-cache-an-*` mais
  **énumèrent explicitement** leurs répertoires (`acteurs_historique_an`,
  `dossiers_an`, `scrutins_an`, `questions_an`, `syceron_an`).

**Pourquoi énumérer plutôt que garder `path: .cache`** : `.cache` englobe
`amendements_an`. Conserver le chemin large aurait fait ré-embarquer les
amendements par les jobs AN, déplaçant le problème au lieu de le résoudre —
c'est le piège principal de ce correctif.

**Le revers, et son garde-fou** : un nouveau `.cache/<quelque_chose>` ajouté
côté Python ne serait pas caché, **sans qu'aucun signal ne l'indique** — le
pipeline continuerait de tourner, simplement plus lentement. `tests/test_ci_cache_paths.py`
vérifie donc que tout répertoire `.cache/*` déclaré dans `src/` est couvert par
un `actions/cache`, et que les deux jobs AN cachent **exactement le même
ensemble** (une divergence signifierait que l'un re-télécharge ce que l'autre a
persisté).

Sa première version comparait les répertoires au fichier entier : retirer un
chemin d'**un seul** job passait inaperçu, puisque l'autre le mentionnait
encore. Vérifié par sabotage, corrigé en analyse par job.

**Repli sur l'artifact** : `extract-an` et `extract-roster-groupes` reçoivent
les amendements par l'artifact `amendements-index-an` (#251) et s'appuyaient,
en cas d'absence, sur le cache partagé — qui ne les contient plus. Un
`actions/cache/restore` (lecture seule) a donc été ajouté, **conditionné à
l'échec du téléchargement de l'artifact** : restaurer 676 Mo dans chaque shard
pour un cas rare recréerait le coût que cette issue supprime.

**Effet de bord traité** : `extract-ue-officiel` cachait aussi `.cache` en bloc
sous sa propre clé, y embarquant les données AN et amendements présentes. Le
quota de cache d'un dépôt étant partagé, une entrée surdimensionnée provoque
l'éviction LRU des autres — dont la clé AN que ce correctif vient de réparer.
Son `path` est resserré sur `.cache/europarl`.

`extract-senat` garde `path: .cache` : ce job n'écrit **rien** sous `.cache`,
son entrée ne recopie donc que ce que la restauration y a placé. Laissé en
l'état plutôt que supprimé — retirer une entrée de cache est une décision de
comportement, pas un effet de bord de cette issue.

**Critère d'acceptation** : le post-job de `extract-an` doit afficher
`Cache saved with key: …` et non `not saving cache`. L'hypothèse ayant déjà
survécu une fois à l'analyse statique seule, seul un run réel tranche.

---

<a id="amendements-zero-pas-de-hard-fail"></a>
## Quality gate : « 0 amendement collecté » reste non bloquant, mais cesse d'être discret (#378) (2026-08-18)

**Contexte** : dernier des 5 fixes de l'investigation de #265 encore ouvert
(les 4 autres tranchés lors du re-check du 2026-08-17, voir
[[amendements-zero-silencieux-acteur-ref]]), sorti en issue dédiée parce qu'il
demandait un arbitrage produit et non un correctif. Les sections 3c (couverture
amendements) et 3d (fraîcheur des index, [[amendements-index-quality-gate-fraicheur]])
de `check_quality_gate.py` ne produisent que des avertissements souples ;
`exit_code` ne vaut 1 que sur `IncompleteRead` au-delà du seuil, structure de
groupe cassée ou structure de gouvernement cassée. Un run avait ainsi committé
28 profils avec `amendements[]` vide **partout** sans que rien ne bloque, alors
que la §3c avait bien détecté et affiché le signal.

**Décision : pas d'escalade en échec dur, dans aucun mode — y compris
`fresh_run=true`.** Aucun flag `--amendements-hard-fail` n'est ajouté. En
revanche le signal global de la §3c est rendu impossible à manquer.

### Pourquoi ne pas bloquer

1. **Le mode d'échec de #265 n'était pas l'absence de blocage, c'était l'absence
   de lecture.** Le signal existait, correct, mais en dernière ligne d'une
   section sur six d'un rapport qui en fait plusieurs centaines. Le rendre
   visible traite la cause ; bloquer traite le symptôme en faisant payer le
   coût à tous les runs suivants.
2. **La collecte dépend d'une source réseau chroniquement défaillante.** La
   législature 17 (active) échoue de façon répétée au téléchargement
   (`IncompleteRead` sur le CDN `data.assemblee-nationale.fr` —
   [[amendements-retry-blocage-legislature]],
   [[amendements-range-download-legislature-isolation]]), problème préexistant
   et hors de notre contrôle. Un run dont l'index n'a pas pu être construit
   produit légitimement zéro amendement : bloquer le commit y ferait perdre
   **tout le reste** du run (mandats, votes, interventions, groupes,
   gouvernements) pour une donnée dont l'absence est déjà tracée. On
   échangerait une donnée manquante contre aucune donnée.
3. **Cohérence avec la dégradation gracieuse déjà tranchée sur toute cette
   chaîne** : `continue-on-error: true` sur le job `extract-amendements-an`
   ([[amendements-index-job-dedie-ci]]), artefact d'index téléchargé en
   optionnel par les consommateurs ([[amendements-index-cache-only-consumers]]),
   retry global qui n'échoue pas sur une extraction partielle
   ([[retry-generate-data-continue-on-error]]). Un échec dur du gate
   contredirait frontalement ces trois décisions pour la même donnée.
4. **Le risque spécifiquement redouté est déjà couvert ailleurs, à la source.**
   Ce qui rendait #265 dangereux, c'est qu'un zéro pouvait être *silencieux*
   (acteurRef introuvable → `[]` sans warning), et qu'un
   `fresh_run=true`/`--no-merge` aurait effacé des amendements ne survivant que
   par la fusion additive. Depuis [[amendements-zero-silencieux-acteur-ref]], ce
   cas émet un warning par candidat : le zéro n'est plus indiscernable d'une
   absence légitime, ce qui était le vrai défaut.

### Ce qui change quand même — la moitié « make it loud » du fix 3

- `_report_amendements_coverage` retourne désormais le signal global à part
  (`regression_globale`), en plus de le laisser dans `soft_warnings` : même
  nature, affichage différent.
- **Affiché en tête de rapport**, avant les six sections : bandeau console juste
  sous la ligne `Quality gate : ✓ COMMIT AUTORISÉ`, et bandeau Markdown juste
  sous le badge dans le GitHub Step Summary.
- Dans la §3c : bloc dédié `🚨 RÉGRESSION PROBABLE DE COLLECTE`, disant
  explicitement que le caractère non bloquant est une **décision** (avec le
  lien vers cette section) et non un oubli. Le message n'est plus répété dans
  la liste des avertissements par candidat, où il se noyait.
- Annotation GHA : conservée au niveau `warning`, préfixée. *Alternative
  rejetée* : `::error::`, qui afficherait une annotation rouge sur un job vert.
  Dans ce script, `error` est réservé aux erreurs qui font effectivement
  `exit 1` (structures de groupe/gouvernement cassées) — le niveau doit rester
  lisible comme « ce run a échoué ».

### Alternatives rejetées

- **Flag `--amendements-hard-fail` désactivé par défaut** (la piste de
  compromis de #378). Rejeté parce qu'il resterait non câblé : le workflow ne
  le passerait jamais, et aucune donnée future ne viendrait changer
  l'arbitrage. C'est la différence avec `--groupe-min-coverage-pct`
  ([[seuil-couverture-groupe]]), option elle aussi désactivée par défaut mais
  qui attend un chiffre précis pour être activée. Une option que rien
  n'activera jamais est du code mort, pas une souplesse.
- **Escalader uniquement en `fresh_run=true`** (« quality gate à tolérance
  zéro » selon la description de l'input). Rejeté : c'est précisément le mode
  où aucun cache n'est restauré et où les trois archives sont retéléchargées —
  donc celui où un zéro d'origine réseau est le **plus** probable. On ferait
  échouer en priorité les runs les plus propres.
- **Escalader le signal par législature de la §3d** (« index jamais
  construit »). Jamais : c'est l'aléa réseau chronique de la 17, il rendrait le
  pipeline définitivement rouge pour une raison étrangère à toute régression.

### Ce qui ferait rouvrir la décision

Que la construction d'index cesse d'échouer de façon chronique — concrètement,
la 17 rapportée « frais » sur une série de runs consécutifs. Un zéro
deviendrait alors une anomalie franche plutôt qu'un état de fait de la source,
et l'escalade redeviendrait discutable.

**Tests** : `tests/test_quality_gate_amendements.py` verrouille les deux
moitiés — la visibilité (signal retourné à part, affiché en tête, non dupliqué)
et l'absence d'échec dur bout en bout (`main()` sort 0 avec `amendements[]` vide
partout, et sort 0 avec un index jamais construit). Suite complète : 1298/1298.

<a id="merge-and-pivot-budget-permissions-413"></a>
## `merge-and-pivot` : garde-fou #390 hors `main`, entrées de configuration, budget de temps mur, permissions (#413) (2026-08-18)

**Contexte** : sous-issue 2/6 de [[revue-workflows-ci-342]], sur le job de fusion
de `generate-data.yml`, le budget annoncé en tête de fichier et le scoping des
permissions. Suite directe de [[concurrence-shards-extraction-412]].

### 1. Le garde-fou #390 empêchait tout commit hors `main`

`git diff "$BASE_SHA" origin/main -- src/` compare **toujours** à `main`, alors
que le workflow est déclenchable par `workflow_dispatch` sur n'importe quelle
ref — et que `retry-generate-data.yml` propage explicitement
`--ref "${{ github.event.workflow_run.head_branch }}"`. Sur un run lancé depuis
`dev` ou une branche de worktree, `$BASE_SHA` est le HEAD de cette branche : le
diff remontait **toutes** les différences entre la branche et `main`, pas les
commits arrivés *pendant* le run. Conséquence : commit annulé,
`GENERATION_CODE_CHANGED_DURING_RUN` émis, retry automatique déclenché qui
échouait à l'identique puis s'arrêtait sur le plafond d'une tentative — un run
hors `main` **ne pouvait jamais committer**, pour une raison étrangère au motif
de #390.

Corrigé en comparant à `origin/${{ github.ref_name }}` (passé par `env:`, jamais
substitué directement dans le script : un nom de branche est contrôlable par qui
déclenche le run).

**Corollaire trouvé au passage** : la boucle de retry du push avait le même
`main` en dur — `git rebase --autostash origin/main` rejouait le commit de
données par-dessus `main` au lieu de la branche poussée. Plus grave que le
garde-fou, puisque celui-ci se contente de refuser. Corrigé de la même façon.

### 2. Le garde-fou ne couvrait pas les entrées de configuration

La condition « volontairement ÉTROITE (`src/` seulement) » se justifiait par
« un commit de doc ou de données ne doit rien déclencher ». Cette phrase
confondait deux natures de données :

- les **dérivées** (`raw_data/profiles/`, `pivot_data/`), régénérées par ce job,
  dont le conflit est traité par la boucle de rebase du push ([[retry-push-merge-and-pivot-bash-e]]) ;
- les **configurations**, qui sont des *entrées* du build :
  `raw_data/candidats.json`, `raw_data/groupes_reels.json`,
  `raw_data/gouvernements_reels.json`. Un merge modifiant `groupes_reels.json`
  pendant le run faisait committer des groupes générés avec l'**ancienne**
  config — exactement le défaut que #390 veut empêcher, et sans aucune alerte.

Périmètre étendu à `src/` **+** `raw_data/*.json` **hors** `raw_data/profiles/`.

**Piège à ne pas re-découvrir** : dans un pathspec git, `*` traverse les
répertoires (pas de `FNM_PATHNAME`). `raw_data/*.json` seul matche donc les ~750
profils bruts, et le garde-fou se déclencherait sur n'importe quel commit de
données. L'exclusion explicite `:(exclude)raw_data/profiles/` n'est pas
cosmétique, elle est ce qui rend la règle utilisable.

*Alternative rejetée* : lister les trois fichiers de configuration en dur. Un
quatrième fichier de config ajouté plus tard échapperait silencieusement au
garde-fou ; le glob + exclusion couvre le cas par construction.

### 3. Le budget de temps mur annoncé était faux (190 min → 210 / 630)

L'en-tête publiait `max(30+5×8, 90, 60, 30) + 60 + 60 = 190 min`. Deux erreurs :
`max(70, 90, 60, 30)` vaut **90** (`extract-senat` était oublié du `max`), et le
terme « 60 » du roster n'est le budget que d'**un** shard depuis #394, exécutés
en série (`max-parallel: 1`, conservé en #412).

Chaîne réelle, en sommant les `timeout-minutes` : les 6 jobs sans `needs:`
finissent au plus tard à 90 (Sénat) ; `extract-an` démarre à 30 et finit à 70 ;
`extract-roster-groupes` démarre à 90 et finit à 90 + 60·S ; `merge-and-pivot`
ajoute 60. Soit **210 min** en configuration par défaut (S=1, rollout) et
**630 min (10 h 30)** en run complet (S=8). Aucune limite GitHub n'est atteinte
(6 h par *job* — le plus long est à 90 min —, 35 j par *run*) : ce n'était pas un
blocage, c'était une documentation trompeuse pour qui dimensionne un run complet.

Le commentaire distingue désormais explicitement la **somme des timeouts** (pire
cas théorique) du **temps mur observé**, bien inférieur ([[budget-roster-mesure]],
1m18–2m10 par shard AN). Les libellés `JOB 1/4`…`JOB 4/4` sont remplacés par des
rôles (`JOB PRÉPARATOIRE` / `JOB D'EXTRACTION` / `JOB FUSION`) : la numérotation
était périmée depuis #344/#394 et le redevenait à chaque ajout de job.

### 4. `contents: write` accordé aux 9 jobs

Déclaré au niveau du workflow, donc hérité partout : les 6 jobs d'extraction
exécutaient du code réseau contre des sources tierces (AN Open Data, NosDéputés,
Sénat, Parlement européen, ParlTrack) avec un token en écriture sur le dépôt dont
ils n'avaient aucun usage. Passé à `contents: read` au niveau du workflow, la
surcharge `contents: write` restant sur `merge-and-pivot` — seul job qui pousse,
et qui portait déjà une surcharge `actions: write` depuis #416.

### 5. Deux fichiers générés étaient trackés, contre ce qu'affirmait la doc

`raw_data/roster_candidats.json` et `parltrack-status.json` sont régénérés à
chaque run, et trois documents l'écrivaient noir sur blanc — mais `git ls-files`
les listait, et le step de commit ne les ajoute pas. Ils laissaient donc l'arbre
de travail sale au moment du `git rebase --autostash` du push, et la version
committée dérivait silencieusement de ce que le run venait de produire.

Décision : les **gitignorer et désindexer**, plutôt que les inclure au commit —
c'est le sens que toute la documentation leur donnait déjà, et aucun consommateur
ne les lit depuis le dépôt (`sync-data.mjs` ne copie que `raw_data/candidats.json` ;
le README et les jobs CI régénèrent le roster avant de s'en servir).

*Alternative rejetée* : les committer. Ce sont des sorties de run, pas des
sources ; les publier ajouterait du bruit de diff à chaque run et deux fichiers
générés de plus à arbitrer en cas de conflit de rebase.

### 6. Revue de l'ordre des étapes de pivot : conservé, deux points documentés

L'ordre (fusion brute → pivot candidats déclarés → pivot roster → partis →
groupes → gouvernements → quality gate → garde-fou → commit) est **conservé**.
Deux choses qui n'étaient pas écrites le sont maintenant, dans le YAML :

- **`--enrich-parltrack` seulement au premier passage** : ParlTrack est une
  source UE et le roster ne contient que des membres AN/Sénat — l'enrichissement
  n'aurait aucun pivot à enrichir au second passage. Asymétrie voulue, pas un
  oubli.
- **`merge-and-pivot` télécharge `amendements-index-an` sans `needs:
  extract-amendements-an`** : cela ne marche que par transitivité
  (`extract-roster-groupes` en dépend). Fragile si un `needs:` bouge, et la
  casse serait silencieuse puisque l'artifact est optionnel. Documenté plutôt
  que corrigé : ajouter le `needs:` direct changerait le graphe pour un gain nul
  tant que la chaîne tient.

Restent conservés sans changement, déjà commentés : candidats déclarés avant
roster (neutre grâce à la protection de provenance de `merge_pivot_profile`,
[[provenance-pivot]]) et le double appel de `generate_roster_candidats.py`.

### 7. `--groupe-min-coverage-pct` : pas un réglage en attente d'arbitrage

Le commentaire `# To be set after running and audit of workflow (cf. #193)`
pointait vers une issue **close**, laissant croire qu'un réglage traînait. #193 a
été tranchée par [[seuil-couverture-groupe]] : garder `--groupe-min-members 1`,
et n'activer le seuil relatif que lorsqu'un run à pleine échelle
(`roster_extraction_limit=0`) aura fourni des taux représentatifs — les chiffres
à regarder étant `taux_couverture_pct` dans `coherence.ecart_couverture_roster`
(`audit_groupe_dataset.py`). Le commentaire renvoie désormais à cette décision et
à la donnée qui la débloquera, au lieu d'un chantier terminé.

<a id="concurrence-shards-extraction-412"></a>
## Jobs d'extraction de `generate-data.yml` : résilience au *skip*, concurrence des shards, factorisation (#412) (2026-08-18)

**Contexte** : première sous-issue d'application de la revue transversale
[[revue-workflows-ci-342]] — les 9 jobs de `.github/workflows/generate-data.yml`
relus job par job. Contrairement à l'epic, ce ticket **modifie le YAML**.

### 1. `continue-on-error:` ne protège pas d'un job *skipped*

Erreur de raisonnement partagée par tout l'historique du fichier (#222, #251,
#344, #394) : `continue-on-error: true` transforme un **échec** en non-bloquant,
mais un job *skipped* skippe ses dépendants quoi qu'il arrive. Or les deux jobs
préparatoires de matrix (`prepare-an-matrix`, `prepare-roster-matrix`) n'avaient
ni `continue-on-error:` ni repli : leur échec — ou un matrix simplement **vide**
— skippait `extract-an`, donc `extract-roster-groupes`, donc `merge-and-pivot`.
**Le run entier ne produisait rien**, exactement l'inverse de ce que l'en-tête
de `merge-and-pivot` affirmait depuis #222.

Correctif, en trois pièces qui ne valent qu'ensemble :

- `if: ${{ !cancelled() }}` sur `extract-roster-groupes` et `merge-and-pivot` :
  seule une annulation externe arrête encore la chaîne. C'est la formulation qui
  rend enfin vrai le « on fusionne ce qui a réussi » du fichier.
- Repli de forme sur les matrix : `fromJson(… || '[]')` pour `extract-an`,
  `fromJson(… || '[0]')` (et `shard_total || '1'`) pour `extract-roster-groupes`
  — sans quoi `fromJson('')` échoue à l'évaluation, avec un message que
  l'interface Actions ne rattache à rien.
- `set -euo pipefail` dans le step de calcul de `prepare-an-matrix` (celui de
  `prepare-roster-matrix` l'avait déjà) : un `python3` en échec y écrivait
  silencieusement `slugs=` dans `$GITHUB_OUTPUT`. Mieux vaut échouer là où la
  cause est lisible.

Un matrix vide reste possible (aucun candidat à slug résolvable) : il est
désormais **annoncé** — `::warning::` + bloc de résumé — au lieu de se déduire
d'un job grisé.

*Alternative rejetée* : donner `continue-on-error: true` aux jobs préparatoires.
Ça ne traite rien — c'est précisément le mécanisme qui ne couvre pas le skip.

### 2. `max-parallel: 1` : conservé, mais la justification écrite était fausse

Question laissée ouverte par #342, tranchée ici. Le plafond venait de #222, en
mitigation d'un **plafond de dépense Actions suspecté** (#221) —
[[verification-billing-actions]] a infirmé cette hypothèse (quota non atteint,
$0 facturé, cause retenue = préemption d'infrastructure). Et le « pic de 4 jobs
simultanés » qu'il prétendait préserver est **6** depuis #344/#394.

Décision : **conserver `max-parallel: 1`** sur les deux matrix, sur les deux
arguments qui tiennent encore, et eux seuls —

1. **Cache** (l'argument réellement valide de #222) : les shards se passent le
   cache AN chaud de proche en proche ; en parallèle, chacun retéléchargerait
   les dumps AN Open Data.
2. **Prudence réseau** : 8 shards parallèles frapperaient simultanément les
   mêmes sources AN/NosDéputés.

Coût assumé et chiffré : ~63 min de temps mur en run complet du roster contre
~8 min en parallèle ([[budget-roster-mesure]]). Ce que le shardage apporte à
`max-parallel: 1` est la **borne de perte sur préemption** (63 min → ~8 min),
pas la vitesse — c'est aussi ce que #394 achetait réellement.

*Alternative rejetée* : ouvrir le parallélisme maintenant. Le gain (55 min de
temps mur sur un run complet qui n'est pas encore la configuration par défaut,
`roster_extraction_limit=20`) ne justifie pas d'engager en même temps un
changement de profil de charge réseau et une hypothèse de cache **non validée**
(§3). À rouvrir si §3 se confirme et que le run complet devient la norme.

### 3. Réserve tranchée depuis : le cache AN n'était effectivement plus réécrit

> **Confirmée et corrigée par #424** (run `32136438841`, 2026-08-18). Le log de
> post-job attendu ci-dessous a été obtenu, sur les 8 shards `extract-an` et le
> shard roster. Coût mesuré : **~438 Mo re-téléchargés par run**. Voir
> [[cache-cle-amendements-separee]]. Le texte d'origine est conservé tel quel
> ci-dessous : la démarche — ne pas corriger sur une hypothèse d'analyse
> statique, exiger un log réel — reste la bonne, et c'est elle qui a produit le
> critère d'acceptation du correctif.

#### Texte d'origine

`extract-amendements-an` s'exécute en premier et écrit la **clé exacte**
`public-data-cache-an-<semaine>`. Les jobs suivants restaurent donc cette clé
exacte — et `actions/cache` **saute la sauvegarde post-job dès qu'il y a eu
exact key hit**. Si c'est bien le cas ici, ce que télécharge `extract-an`
(`acteurs_an`, `scrutins_an`, `dossiers_an`, ~290 Mo) n'est jamais persisté dans
la clé de la semaine, et chaque shard de chaque run le re-télécharge.

**Aucun correctif appliqué** : la conclusion dépend d'un log de post-job réel
(« Cache hit occurred on the primary key, not saving cache »), qu'aucun run
n'a encore fourni. La réserve est écrite dans le YAML, à l'endroit exact
(commentaire du `actions/cache` d'`extract-an`), avec le correctif envisagé :
clé propre à `extract-amendements-an` (`public-data-cache-amendements-*`, path
`.cache/amendements_an`), en laissant `…-an-*` à `extract-an`. C'est presque la
proposition fermée en #374, mais pour une raison différente — là-bas réduire le
volume restauré, ici restaurer la capacité d'écriture.

### 4. Deux actions composites locales, et pas une de plus

`.github/actions/bootstrap-extraction` (horodatage + relevé mémoire OOM +
`setup-python` + `pip install`) et `.github/actions/job-diagnostics` (blocs de
résumé « job annulé » / « job en échec »), appliquées aux 6 jobs d'extraction :
~145 lignes de duplication en moins pour une indirection d'un seul niveau.

Deux points de sémantique, faciles à casser dans une reprise :

- Les `if: cancelled()` / `if: failure()` restent portés par le **step
  appelant**. Évalués dans l'action, ils porteraient sur l'état de ses propres
  steps — ce n'est pas le même test.
- Une action locale suppose le `actions/checkout` du job déjà fait : un job
  annulé avant la fin de son checkout n'aura pas son résumé. Angle mort
  résiduel assumé (le cas majoritaire, préemption en cours d'extraction #228,
  reste couvert).

Le relevé mémoire `free -h` est du coup appliqué aux **6** jobs, et plus
seulement à `extract-an`/`extract-roster-groupes` : `extract-amendements-an`
manipule les plus gros volumes (archives ~1,2 Gio) et en était le seul dépourvu.

*Alternative rejetée* : factoriser aussi `MERGE_FLAG`/`INTERV_FLAG`/
`MAX_PAGES_FLAG`. `retry-generate-data.yml` reconstruit les inputs du run échoué
en **grepant le texte bash substitué** de ces steps dans les logs ; les déplacer
casserait ce couplage. Contrainte non évidente, désormais écrite en commentaire
dans le YAML (et dans l'action composite, pour qui viendrait l'y ajouter).

*Alternative rejetée* : factoriser « Semaine ISO courante », « Nettoyage
complet (fresh_run) » et `actions/cache` — 3 à 4 lignes chacun, corps déjà
divergents, clé de cache différente par job. La variabilité y domine la
duplication.

### 5. Garde-fou de volume sur `extract-an`

Le commentaire « recalculer si `raw_data/candidats.json` change
significativement » n'était outillé par rien : à 5 min par shard en série, un
passage à 40 candidats porterait ce seul job à 200 min sans aucun signal.
`prepare-an-matrix` émet désormais un `::warning::` au-delà de `AN_SHARDS_WARN`
(16, soit ~80 min), valeur unique et modifiable en place.

### 6. Nommage : `raw-profiles-parltrack` → `parltrack-dumps`

Seul écart de la famille `raw-profiles-*` : cet artifact ne contient pas de
profils bruts mais les dumps `.zst` ParlTrack, consommés dans `.cache/parltrack`
par `merge-and-pivot`. Aucun consommateur hors du run courant (le retry ne
manipule pas d'artifacts) → renommé.

**Hors périmètre, traité ailleurs** : budget de temps mur et libellés « JOB n/4 »
périmés, garde-fou #390, permissions par job (#413) ; reconstruction des inputs
du retry (#414).
<a id="retry-inputs-appariement-prefixe"></a>
## `retry-generate-data.yml` : reconstruction des inputs réparée par appariement de préfixe, collecte de jobs unifiée (#414) (2026-08-18)

**Contexte** : le shardage d'`extract-an` (#344) et d'`extract-roster-groupes`
(#394) a donné à ces jobs un `name:` explicite — `extract-an (<slug>)`,
`extract-roster-groupes (shard N)`. Or le step « Reconstituer les inputs du run
échoué » les identifiait **par nom exact**
(`jq 'select(.name=="extract-an")'`) : plus aucun job ne portant ces noms, la
reconstruction retombait sur les défauts pour cinq des six inputs, sans rien
signaler. Ce que le fichier documentait comme une « dégradation documentée, pas
un blocage » était devenu le **chemin nominal** : un run `fresh_run=true` était
relancé en incrémental, un run `roster_extraction_limit=0` (run complet) relancé
à 20. Seul `threshold` survivait (lu sur `merge-and-pivot`, non shardé).
`workers` était doublement cassé : le matrix a aussi supprimé `--workers` de la
ligne de commande d'`extract-an` (`--only "<slug>"` remplace le parallélisme
inter-candidats), donc le motif n'existait plus, nom de job correct ou non.

**Décision** :
- **Appariement par préfixe** : `job_log()` matche `<préfixe>` ou
  `<préfixe> (…)`, et privilégie un shard dont la `conclusion` est `success` —
  le log d'un shard préempté peut être tronqué avant même la ligne `Run ...`.
  Même règle pour la lecture de `fresh_run` (conclusion du step « Nettoyage
  complet ») sur l'ensemble des shards `extract-an`.
- **`workers` est lu sur `extract-senat`**, seul job non shardé portant encore
  `--source senat --workers N`.
- **`roster_extraction_limit` est lu dans le bloc `env:` résolu**
  (`ROSTER_LIMIT: <valeur>`) plutôt que dans le stdout « Sélection … », qui ne
  rapporte que le nombre de candidats *retenus* (`min(limite, restants)`) et
  n'est pas émis du tout quand la limite vaut 0 — le cas « run complet » était
  donc irrécupérable. Le grep « Sélection » reste en repli.
- **Un seul step de collecte** (`collect`) remplace les trois listings
  `gh api .../jobs --paginate` et classe les deux motifs de relance
  (préemption runner, refus de commit pour code périmé #390) en **un seul
  passage** sur les jobs en échec, avec **un seul téléchargement par log**. La
  liste des jobs et les logs sont mis en cache dans `$RUNNER_TEMP` et réutilisés
  par la reconstruction des inputs. Le rate-limit transitoire diagnostiqué en
  #336 était un risque réel, aggravé par le shardage (8 + 8 jobs).
- Les issues `api_error` / `inconclusive` (#237) **couvrent désormais les deux
  motifs** : la détection #390 redirigeait ses erreurs vers `/dev/null` et
  n'exposait que `matched`, si bien qu'un hoquet de l'API s'y présentait comme
  « pas de #390 » plutôt que « indéterminé ».
- La reconstruction des inputs est conditionnée aux **deux** motifs, comme le
  re-déclenchement : une relance déclenchée par #390 repartait des défauts par
  construction.
- `jq -s '{jobs: [.[].jobs[]]}'` normalise la sortie de `--paginate` : au-delà
  de 100 jobs (atteignable avec le shardage), gh émet plusieurs objets JSON
  concaténés et un comptage `jq` direct produisait une valeur *par page*,
  cassant les comparaisons numériques.

*Alternative rejetée* : publier les inputs en artifact depuis
`generate-data.yml` (`echo '${{ toJson(inputs) }}' > run-inputs.json`) et les
relire via `gh run download`. Exact, insensible aux renommages de jobs et de
flags, et cela supprimerait la contrainte de ne pas factoriser les motifs
`MERGE_FLAG`/`INTERV_FLAG` sous peine de casser les greps. Écarté ici pour ne
pas modifier `generate-data.yml`, qui est le fichier le plus chargé du dépôt et
dont chaque run coûte du temps mur : le correctif reste confiné au workflow de
retry. Le couplage à la mise en forme du YAML et des `print()` Python subsiste
et reste le point faible connu de ce mécanisme.

*Alternative rejetée* : lire `workers` sur `extract-roster-groupes` ou
`merge-and-pivot`, qui portent aussi `--workers`. `extract-senat` est préféré
car non shardé (pas de sélection de shard) et non `continue-on-error` sur le
chemin critique de la relance.
<a id="deploy-pages-declencheur-donnees"></a>
## Publication du site après un run de données : le commit du bot n'émet aucun événement `push` (#416) (2026-08-18)

**Contexte** : les données du site sont figées **au build**. `npm run build`
= `npm run sync-data && vite build`, et `web/UI_finale/scripts/sync-data.mjs`
copie `pivot_data/` + `raw_data/candidats.json` vers
`web/UI_finale/public/data/` (dossier gitignoré) que Vite embarque dans
`dist/` ; le front les lit ensuite à l'exécution via
`fetch('/data/manifest.json')`. Un run de génération qui met à jour les
données n'est donc visible en ligne qu'après un **nouveau build**.

`deploy-pages.yml` ne se déclenchait que sur un `push` sur `main` touchant
`web/UI_finale/**` ou son propre fichier. Le commit produit par
`merge-and-pivot` (`chore: mise à jour automatique des données (…)`) ne touche
que `raw_data/profiles` et
`pivot_data/{profiles,partis,groupes,gouvernements}` — aucun chemin
déclencheur. Constaté le 18/08/2026 : `main` portait un commit de données du
jour, le dernier run `deploy-pages.yml` datait du 2026-08-17T23:53. Les
données finissaient par arriver en production, mais **par coïncidence**, à la
prochaine modification de `web/UI_finale/`.

**Le point non évident** : élargir les `paths:` ne suffit pas. Le push de
`merge-and-pivot` est fait avec le `GITHUB_TOKEN` par défaut (credentials
persistées par `actions/checkout`), et GitHub n'émet **aucun** événement
déclencheur pour une action effectuée avec ce token — protection anti-boucle.
Le commit du bot ne peut donc structurellement pas déclencher un workflow
`on: push`, quels que soient ses `paths:`. Vérifié sur l'historique des runs :
**zéro** run, tous workflows confondus, n'a jamais eu pour déclencheur un
commit `chore: mise à jour automatique des données`. Une correction limitée
aux `paths:` aurait été livrée, mergée, et n'aurait rien changé — sans signal
visible d'échec.

**Décision** — les deux moitiés, complémentaires :

1. `deploy-pages.yml` : ajout de `pivot_data/**` et `raw_data/candidats.json`
   aux `paths:`. Couvre les pushs **humains** (merge de PR) qui touchent les
   données — un cas réel, distinct du commit du bot.
2. `generate-data.yml` (job `merge-and-pivot`) : après un push de données
   réussi, une étape déclenche explicitement
   `gh workflow run deploy-pages.yml --ref main`. `workflow_dispatch` (comme
   `repository_dispatch`) est l'exception documentée à la règle anti-boucle :
   un dispatch émis avec le `GITHUB_TOKEN` démarre bien un run. Même mécanique
   que le re-déclenchement de `generate-data.yml` par
   `retry-generate-data.yml` (voir [[retry-generate-data-preemption]]).

   L'étape est gardée par un output `pushed` du step de commit (`true`
   uniquement si `git push` a réussi ; `false` s'il n'y avait rien à
   committer) **et** par `github.ref == 'refs/heads/main'` — un run de
   génération lancé depuis une branche de travail ne doit jamais publier le
   site de production. L'output est écrit **avant** chaque `exit 0` du step :
   `exit` termine le step immédiatement, une écriture placée après ne serait
   jamais faite.

**Permissions** : `pages: write` et `id-token: write` étaient déclarés au
niveau workflow dans `deploy-pages.yml`, donc hérités par `build`, qui ne fait
que `npm ci && npm run build` + `upload-pages-artifact`. Un job qui exécute
`npm ci` sur des dépendances tierces ne doit pas porter `id-token: write`.
Désormais : `contents: read` au niveau workflow, `contents: read` +
`pages: read` sur `build` (`actions/configure-pages` lit la configuration
Pages du dépôt via l'API — la lecture seule suffit), `pages: write` +
`id-token: write` sur le seul job `deploy` (qui ne checkoute pas, donc pas de
`contents:`). De même, `actions: write` (requis par le `gh workflow run`) est
déclaré sur le seul job `merge-and-pivot` de `generate-data.yml`, pas au
niveau workflow : les jobs d'extraction n'ont aucune raison de pouvoir
déclencher un workflow.

*Question tranchée — pas de `concurrency` distinct pour les runs de données* :
le groupe `pages` avec `cancel-in-progress: false` **sérialise déjà** un
déploiement déclenché par les données et un déploiement déclenché par un
changement d'UI ; ils ne peuvent pas se marcher dessus. Deux groupes séparés
feraient exactement l'inverse — ils autoriseraient deux déploiements
concurrents vers le même site. Conservé tel quel.

*Alternative rejetée* : déclencher `deploy-pages.yml` sur
`workflow_run: [Génération des données]`, comme `retry-generate-data.yml`.
Rejeté : `workflow_run` se déclenche sur la **conclusion du run**, pas sur le
fait qu'un commit de données ait été poussé. Un run réussi sans changement de
données (« Aucun changement de données à committer »), ou dont le commit a été
refusé par la garde de code périmé (#390), lancerait un déploiement inutile.
Le dispatch depuis le step de push est conditionné à ce qui compte réellement :
un push effectif.

*Alternative rejetée* : un PAT à la place du `GITHUB_TOKEN` pour le push, afin
que l'événement `push` soit bien émis. Rejeté : introduit un secret à gérer et
à faire tourner, et rouvre le risque de boucle que la règle GitHub prévient,
pour un gain nul par rapport au dispatch explicite.

`timeout-minutes: 10` ajouté sur les deux jobs de `deploy-pages.yml`
(auparavant le défaut de 360 min), par cohérence avec `generate-data.yml` —
`build` tourne en ~35 s et `deploy` en ~11 s sur les runs récents, la marge
couvre la croissance du volume de `pivot_data` copié dans `dist/`.

**Relu sans changement** : `debug-network-shutdown-signal.yml`, hors de
l'inventaire de #342 (rédigé quand le dossier comptait 5 workflows). Workflow
de diagnostic isolé — `workflow_dispatch` seul, aucune donnée touchée, aucun
commit, aucun `needs` vers le pipeline de production. Rien à corriger.

**À valider par un run réel** : le prochain `generate-data.yml` sur `main` qui
pousse des données doit faire apparaître, dans la foulée, un run
`deploy-pages.yml` déclenché par `workflow_dispatch`.
<a id="workflows-claude-securite"></a>
## Workflows Claude : garde d'auteur, asymétrie de sandbox levée, marketplace non épinglé (#415) (2026-08-18)

**Contexte** : le dépôt est public et `claude.yml` / `claude-code-review.yml`
se déclenchent tous deux sur `issue_comment`, event qui s'exécute toujours dans
le contexte du dépôt de base, avec accès aux secrets. Ni l'un ni l'autre ne
filtrait l'auteur du commentaire, et les deux fichiers avaient divergé sans
qu'aucune ligne n'écrive pourquoi (cf. [[revue-workflows-ci-342]], qui laissait
la question ouverte).

**Premier constat, qui corrige la prémisse de l'issue** : l'absence de garde
d'auteur n'ouvre **pas** l'usage du `CLAUDE_CODE_OAUTH_TOKEN` à n'importe qui.
`anthropics/claude-code-action` vérifie elle-même que l'acteur déclencheur a le
droit d'**écriture** sur le dépôt — pour les events issue, pull request,
comment et review — et s'arrête avant d'appeler Claude sinon
(`docs/security.md` de l'action). Le seul contournement documenté est
`allowed_non_write_users`, resté à sa valeur par défaut (vide) ici. Le risque
réel n'était donc pas l'exécution d'un prompt hostile, mais la **consommation
de minutes Actions** : un commentaire d'un inconnu démarrait un runner,
installait bubblewrap et les dépendances de l'action avant de se faire refuser.

**Décisions** :

- **Garde d'auteur ajoutée dans les deux `if:`**
  (`contains(fromJson('["OWNER","MEMBER","COLLABORATOR"]'), …author_association)`),
  assumée comme **pré-filtre** et non comme mécanisme de sécurité : elle évite
  le démarrage du runner, la vérification qui fait foi reste celle de l'action.
  Elle est répétée sur chacune des quatre branches de `claude.yml` plutôt que
  factorisée en fin d'expression, parce que `author_association` vit dans
  `.comment`, `.review` ou `.issue` selon l'event : une forme factorisée
  (`a || b || c`) reposerait sur le déréférencement d'objets absents.
  `COLLABORATOR` inclut un invité en lecture seule — accepté, puisque ce n'est
  pas cette garde qui décide.
- **L'asymétrie de `github_token` / `permissions` / `--allowed-tools` est
  confirmée volontaire**, et désormais écrite en en-tête des deux fichiers :
  `claude.yml` reçoit un prompt arbitraire *et* un `WORKFLOW_PAT` en écriture,
  donc défense en profondeur proportionnée ; `claude-code-review.yml` tourne un
  prompt fixe avec un token en lecture seule, donc surface d'écriture nulle et
  aucune raison de brider les outils du plugin de review.
- **L'asymétrie de sandbox, elle, est supprimée.** `claude-code-review.yml`
  reçoit les mêmes deux étapes de préparation (bubblewrap/socat, contournement
  AppArmor d'Ubuntu 24.04+) et le **même** bloc `settings.sandbox` que
  `claude.yml`, allowlist réseau comprise. Raison : le token OAuth Claude est
  présent dans les deux workflows, et celui de review lit du contenu de PR
  potentiellement hostile (diff, titre, description d'une PR de fork) — la
  garde d'auteur n'y change rien, un mainteneur peut légitimement lancer
  `/claude-review` sur une PR externe. Sans isolation réseau, une injection
  réussie exfiltrait ce secret vers un domaine arbitraire. Coût accepté :
  ~20-30 s d'`apt-get` par run de review, et un échec dur si bubblewrap ne
  démarre pas (`failIfUnavailable: true`, même choix que `claude.yml`).
  L'installation du marketplace et du plugin a lieu dans les étapes de l'action,
  avant Claude, donc hors sandbox : elle n'est pas affectée.

*Réserve non levée, refus argumenté* : **`plugin_marketplaces` reste non
épinglé**. Aucune syntaxe de révision n'existe — l'input de l'action valide
l'entrée contre `^https://…\.git$` et se contente de lancer
`claude plugin marketplace add <url>`, qui clone la branche par défaut ; il n'y
a ni argument `--ref` ni forme `url#sha`. Les deux seuls contournements
seraient de vendorer une copie du marketplace dans ce dépôt ou d'en maintenir
un fork, c'est-à-dire déplacer la confiance de « la branche `main`
d'Anthropic » vers « une copie locale à resynchroniser à la main », avec le
risque de la laisser pourrir. Or ce marketplace est le dépôt de l'éditeur de
l'action elle-même, référencée ici par le tag flottant
`anthropics/claude-code-action@v1` : épingler le marketplace en laissant
l'action flotter ne réduirait aucune surface réelle. **Condition de
réouverture** : si `claude-code-action` est un jour épinglée sur un SHA, épingler
le marketplace dans la foulée — sinon la décision devient incohérente.

*Divergences mineures corrigées dans la foulée* :

- `claude-code-review.yml` reçoit `timeout-minutes: 45` (il tournait avec le
  défaut de 360) et un `concurrency` par PR — N commentaires `/claude-review`
  produisaient N runs parallèles sur le même diff. `cancel-in-progress: true`,
  contrairement à `claude.yml` qui sérialise : une review n'écrit rien qu'une
  annulation perdrait, et un second `/claude-review` veut l'état le plus récent
  de la PR, pas deux fois la même review.
- `actions/checkout@v4` → `@v5` dans les deux, alignement sur les quatre autres
  workflows.
- `--allowed-tools` de `claude.yml` nettoyé : une entrée était précédée d'une
  espace parasite (`Bash(python3 -m unittest), Bash(python3:*)`) qui pouvait
  faire échouer son matching, `Bash(pytest:*)` apparaissait deux fois, et les
  quatre variantes `Bash(python3 -m pytest…)` / `Bash(python3 -m unittest)`
  étaient toutes couvertes par `Bash(python3:*)`. Liste ramenée à six entrées
  Bash, couverture inchangée.
- `--model` : le pin est **reconfirmé** (sans lui, le modèle dépend du défaut
  du CLI et de l'abonnement au moment du run, qui peut basculer sur un modèle
  plus petit sans que rien ne le signale dans ce fichier) et **mis à jour** —
  il était resté sur `claude-opus-4-8`, une génération en retard, ce qui est
  précisément la contrepartie du pin. Rendez-vous de revalidation : chaque
  revue de ce fichier.

*Point vérifié, acté tel quel* : le `--append-system-prompt` interdit à Claude
de modifier `claude.yml` et `claude-code-review.yml` — les deux fichiers qui
définissent ses propres privilèges, dont la modification depuis un run Claude
serait une auto-élévation. `generate-data.yml`, `retry-generate-data.yml`,
`deploy-pages.yml` et `debug-network-shutdown-signal.yml` ne sont
volontairement **pas** couverts : workflows de données/déploiement, sans secret
d'élévation, dont toute modification passe de toute façon par une PR relue. La
justification est maintenant écrite à côté du garde-fou pour que la question ne
se repose pas.

<a id="revue-workflows-ci-342"></a>
## Revue transversale des workflows GitHub Actions : ce qui est gardé, ce qui est corrigé (#342) (2026-08-18)

**Contexte** : `.github/workflows/` a grossi par ajouts successifs, chacun
justifié localement dans sa propre issue (#192, #215, #222, #245, #248, #251,
#344, #390, #394…), sans qu'aucune passe transversale n'ait jamais revérifié la
cohérence de l'ensemble une fois tous les jobs en place. #342 est cette passe :
revue documentaire, job par job et fichier par fichier, **sans modification de
comportement CI** — chaque correction retenue part en sous-issue dédiée, pour
qu'un run de validation puisse être attribué à un changement et un seul.

**Périmètre réellement relu : 6 workflows, pas 5.**
`debug-network-shutdown-signal.yml` a été ajouté après la rédaction de #342 et
n'avait jamais été relu ; il entre dans le périmètre (#416).
`generate-data.yml` compte désormais **9 jobs** (dont 2 jobs préparatoires de
matrix et 2 jobs shardés), pas les 7 que décrit #342.

### Ce qui est gardé tel quel, et pourquoi

- **Les motifs `MERGE_FLAG` / `INTERV_FLAG` / `MAX_PAGES_FLAG` restent
  dupliqués** dans les jobs d'extraction. Raison principale, non évidente et
  jamais écrite jusqu'ici : `retry-generate-data.yml` reconstruit les inputs du
  run échoué en **grepant le texte bash substitué de ces steps** ; les déplacer
  dans une action composite casserait ce couplage. La contrainte doit rester
  visible en commentaire dans le YAML tant que le mécanisme de reconstruction
  n'est pas remplacé (#414).
- **Les steps « Semaine ISO courante » et « Nettoyage complet (fresh_run) »
  restent dupliqués** : 3 à 4 lignes par job, et la seule alternative
  (les exposer depuis un job partagé) ajouterait une arête `needs:` à des jobs
  volontairement indépendants — c'est-à-dire exactement le mode de défaillance
  décrit plus bas pour les jobs préparatoires.
- **Les blocs de diagnostic annulation/échec, eux, sont factorisables** en
  action composite locale : les `if: cancelled()` / `if: failure()` restent
  portés par le step appelant, la sémantique est donc préservée. ~145 lignes de
  duplication pour une indirection d'un seul niveau — retenu (#412), à la
  différence des motifs ci-dessus.
- **L'ordre des étapes de pivot de `merge-and-pivot`** (candidats déclarés
  avant roster) est conservé : il n'est neutre que grâce à la protection de
  provenance de `merge_pivot_profile` ([[provenance-pivot]]), déjà commentée.
  Le double appel de `generate_roster_candidats.py` (une fois par shard, une
  fois au pivot) est également conservé : 2 appels réseau mutualisés, moins
  cher qu'un transit par artifact.
- **Le plafond d'une seule tentative de retry** ([[retry-preemption-logs]])
  reste basé sur `triggering_actor == github-actions[bot]`. Corollaire à
  écrire : une relance **manuelle** après un retry automatique repart avec un
  plafond neuf — comportement voulu, aujourd'hui implicite.
- **L'asymétrie de sandbox entre `claude.yml` et `claude-code-review.yml` est
  volontaire**, contrairement à ce que #342 laissait ouvert : le premier reçoit
  un prompt arbitraire *et* un `WORKFLOW_PAT` en écriture (sandbox bubblewrap +
  allowlist réseau + `--allowed-tools` proportionnés) ; le second tourne un
  prompt fixe avec le token par défaut en lecture seule. Défendable — mais à
  écrire dans les deux fichiers, et sous réserve des deux points traités en
  #415 (le token OAuth Claude est exposé dans les deux, et le marketplace de
  plugins n'est pas épinglé). **Suite donnée en #415**
  ([[workflows-claude-securite]]) : l'asymétrie de `github_token` /
  `permissions` / `--allowed-tools` est confirmée et écrite en en-tête des deux
  fichiers, mais celle du **sandbox est supprimée** — le workflow de review
  reçoit la même isolation réseau, parce qu'il lit du contenu de PR hostile avec
  le token OAuth en mémoire. Le marketplace reste non épinglé, refus argumenté
  (aucune syntaxe de révision n'existe côté action).
- **Le `schedule:` cron reste commenté.** Hors périmètre de #342 (décision
  produit/coût) : la revue constate seulement que rien depuis #192 ne l'a
  reconfirmé, et que la désactivation n'a jamais été justifiée par écrit.

### Ce qui est corrigé, et dans quelle sous-issue

| Constat | Sous-issue |
|---|---|
| `prepare-an-matrix` / `prepare-roster-matrix` sont des SPOF : leur échec *skippe* toute la chaîne jusqu'à `merge-and-pivot`, que `continue-on-error:` ne protège pas (il couvre l'échec, pas le skip) | #412 |
| Trois commentaires affirment le contraire du YAML (« pas de `needs:` sur `extract-amendements-an` ») | #412 |
| Seul `extract-amendements-an` écrit encore le cache AN hebdomadaire (exact key hit → pas de sauvegarde post-job chez les consommateurs) | #412 |
| Budget de temps mur faux : 210 min réels en rollout, 630 min en run complet, contre 190 annoncés ; libellés « JOB n/4 » périmés | #413 |
| Le garde-fou #390 compare toujours à `origin/main`, donc bloque tout run lancé hors `main` | #413 |
| Le garde-fou #390 ne couvre pas les fichiers de configuration (`groupes_reels.json`…), qui sont pourtant des entrées du build | #413 |
| `raw_data/roster_candidats.json` et `parltrack-status.json` sont trackés alors que le YAML affirme le contraire | #413 |
| `contents: write` accordé aux 9 jobs, alors que seul `merge-and-pivot` en a besoin | #413 |
| La reconstruction best-effort des inputs du retry est morte depuis le shardage (noms de jobs `extract-an (<slug>)`) | #414 |
| Dans la branche #390, la reconstruction des inputs n'est même pas tentée | #414 |
| Aucune garde sur l'auteur du commentaire : sur un dépôt **public**, le commentaire de n'importe qui démarre un runner (l'action refuse ensuite les acteurs sans droit d'écriture — voir [[workflows-claude-securite]]) | #415 |
| Le site Pages ne se redéploie jamais sur un commit de données | #416 |
| `debug-network-shutdown-signal.yml` sans bloc `permissions:` | #416 |

### Questions de #342 refermées sans travail

- **Le fallback `extract_interventions`** cité en exemple par l'epic est déjà
  corrigé (`7debd61`) ; les **six** fallbacks du retry sont alignés sur les
  défauts déclarés dans `generate-data.yml`.
- **Les « 3 blocs de résumé » de `retry-generate-data.yml`** n'existent plus :
  c'est un bloc `if/elif` unique à 6 branches depuis #245/#336.
- **La course d'écriture sur le cache AN partagé**, actée hors périmètre en
  #248 sous-issue 4 ([[amendements-index-budget-ci-cache-granularite]]), est
  **éteinte** : les trois jobs qui écrivent `public-data-cache-an-*` sont
  strictement séquencés depuis #344, et les deux consommateurs sont en lecture
  cache-only depuis #252. Résolue par effet de bord, jamais actée jusqu'ici.
- **Les noms et chemins d'artifacts** sont cohérents, à une exception près
  (`raw-profiles-parltrack` contient des dumps `.zst`, pas des profils).

### Trois conclusions non évidentes, à ne pas re-dériver

1. **Le pic de jobs simultanés n'est plus 4 mais 6.** Six jobs démarrent sans
   `needs:` depuis l'ajout des deux jobs préparatoires de matrix (#344/#394).
   Les commentaires « `max-parallel: 1` préserve le pic de 4 jobs acté par
   #222 » ([[concurrence-ci-roster]]) sont faux depuis.
2. **La justification du plafond de concurrence repose sur une hypothèse
   infirmée.** #222 a réduit le pic en mitigation d'un plafond de dépense
   Actions suspecté — hypothèse explicitement démentie depuis
   ([[verification-billing-actions]]). Ce qui reste valide de #222 est
   l'argument *cache* (ne pas télécharger deux fois les dumps AN), pas
   l'argument *concurrence*. Conséquence concrète : `max-parallel: 1` sur
   `extract-roster-groupes` coûte ~63 min de temps mur en run complet contre
   ~8 min en parallèle ([[budget-roster-mesure]]), pour une contrainte à
   re-trancher (#412).
3. **Les données du site sont figées au build.** `npm run build` exécute
   `sync-data.mjs`, qui copie `pivot_data/` dans `public/data/` (gitignoré) ;
   le front les lit ensuite par `fetch('/data/…')`. Comme `deploy-pages.yml` ne
   se déclenche que sur `web/UI_finale/**`, le commit de données de
   `merge-and-pivot` ne redéploie rien — vérifié le 18/08/2026 : commit de
   données du 18/08 sur `main`, dernier déploiement du 17/08. Les données
   n'atteignent la production qu'à la faveur d'une modification d'interface
   ultérieure (#416).

*Alternative rejetée* : appliquer les correctifs directement dans cette epic —
rejetée par #342 lui-même, et confirmée par la revue : treize corrections
touchant 5 fichiers dans un seul diff CI seraient inattribuables en cas de
régression, alors que chacune demande son propre run de validation
(`workflow_dispatch`).

*Alternative rejetée* : produire la revue sous forme d'un document séparé
(`docs/ci_review.md`) — rejetée pour éviter une deuxième autorité concurrente
de ce fichier ; le détail par fichier vit dans les sous-issues #412-#417, seules
les décisions durables sont ici.

<a id="audit-rapport-perimetre-candidats"></a>
## Rapport d'audit pivot : détail réservé aux candidats déclarés, indicateurs de distribution retirés (2026-08-18)

**Contexte** : le rapport Markdown de `audit_pivot_dataset.py` avait grossi
au rythme du jeu de données. Sur `pivot_data/profiles` (129 profils au
18/08/2026), les deux tableaux croisés par candidat (`#174` pour les
volumes, `#317` pour les plages temporelles) listaient **une ligne par
profil**, soit 258 lignes de détail dont 242 pour des profils de roster
(`meta.provenance == "roster_groupe"`, 121 profils) qui ne sont pas des
candidats : ils sont collectés pour la cohésion de groupe, jamais pour un
affichage individuel. Le rapport devenait illisible pour son unique usage —
repérer d'un coup d'œil un profil de candidat mal enrichi.

**Décision** :
- Les deux tableaux croisés ne détaillent plus que les **candidats déclarés**
  (`meta.provenance` absente ou `candidat_declare`, cf.
  [[provenance-pivot]] — helper `_est_candidat`). Les profils de roster sont
  restitués **agrégés par `groupe`** (min/max/médiane/moyenne pour les
  volumes, plage englobante pour les dates), plus une ligne « Ensemble » ;
  aucun `id` ni `nom` de membre non candidat n'apparaît dans l'agrégat, ce
  qu'un test verrouille. Un `groupe` absent est regroupé sous `"null"`,
  comme ailleurs dans le rapport.
- Deux indicateurs de volumétrie sont supprimés du rapport JSON **et**
  Markdown : « Distribution des listes métier (par profil) »
  (`compute_distribution_listes`) et « Sources déclarées »
  (`compute_nombre_sources` : moyenne de sources par profil, % de profils à
  une seule source). Sans distinction candidat/roster, leurs statistiques
  mélangeaient deux populations aux volumétries incomparables ; la
  ventilation par groupe des non-candidats couvre désormais le même besoin
  là où il a un sens. Leur logique min/max/médiane/moyenne survit dans le
  helper `_stats_volumes`, réutilisé par l'agrégat par groupe.

*Alternative rejetée* : filtrer les profils de roster hors du rapport
entièrement (ne rien afficher pour eux) — rejeté car un roster mal collecté
(votes à 0 sur tout un groupe) resterait invisible dans l'audit, alors que
c'est précisément un défaut de pipeline que ce rapport doit faire remonter.
L'agrégat par groupe garde ce signal sans le détail individuel.

*Alternative rejetée* : garder les deux indicateurs supprimés en les
ventilant par provenance — rejeté comme redondant avec l'agrégat par groupe
introduit ici, pour un rapport qu'on cherchait justement à alléger.

<a id="votes-multi-legislature"></a>
## Votes : agrégation des législatures 14 à 17, index dédupliqué, 14/15/16 figées (#403) (2026-08-18)

**Contexte** : les votes ne couvraient qu'**une seule législature par profil**,
et en pratique toujours la 16e — 86 des 87 profils bruts, aucun en 17e. Le jeu
de données s'arrêtait donc en **juin 2024**, sur la législature en cours.
`fetch_votes_officiels()` prenait un `base_url` NosDéputés unique et le
convertissait en législature via `LEGISLATURE_BY_BASE_URL`. Depuis l'étape 4 de
#369, `identity_base_url` vaut `None` pour tout député résolu via l'AN : on
retombait systématiquement sur `base_urls[0]`, mappé en dur sur « 16 ». Double
défaut hérité de l'ère NosDéputés — mono-législature *par construction*, et un
mapping dont plus rien ne garantissait la pertinence.

**Décision** : `AN_SCRUTINS_LEGISLATURES = ("17", "16", "15", "14")` remplace le
mapping par domaine ; `fetch_votes_officiels(url_an_ou_senat, warnings)` agrège
les quatre législatures, chacune tentée indépendamment (une archive absente
n'interrompt plus les autres, même précaution qu'en #241 sur les amendements).
Le mapping domaine → législature n'est pas supprimé mais **déplacé dans
`group_roster.py`**, son seul utilisateur légitime restant : les rosters de
groupes sont bien servis par un domaine NosDéputés par législature (vérifié le
18/08/2026 : `www.nosdeputes.fr` sert toujours la 16e, 618 députés, mandats
2022-06-22 → 2024-06-09 — le site n'a pas été étendu à la 17e).

**Déduplication par `uid`, jamais par `numero`** — le point non évident. Le
numéro de scrutin AN **repart de 1 à chaque législature** : dédoublonner par
numéro effacerait des scrutins distincts. L'`uid` (`VTANR5L17V1000`) porte la
législature et est unique toutes législatures confondues. Le corollaire vaut
côté agrégats : `group_profile._compute_cohesion_votes` indexait par
`numero_scrutin` seul, ce qui aurait **fusionné les décomptes** du n° 1000 de la
16e et de celui de la 17e dès la première regénération. La cohésion (et le
rapport d'écarts internes) filtre donc désormais sur la législature du groupe —
un profil de groupe de la 16e ne peut plus se voir attribuer des scrutins de la
17e par ses membres réélus. Les votes sans `legislature` (collectés avant #403)
sont conservés par ce filtre : une donnée absente n'est pas une donnée
contradictoire (règle 5).

**Deux conditionnements d'archive**. La 14e est livrée en JSON **monolithique**
(`Scrutins_XIV.json`, `scrutins.scrutin[]`), les 15e/16e/17e en arborescence
`json/` d'un fichier par scrutin. Le conditionnement est détecté par la clé
racine, jamais par le nom de fichier. Même changement d'architecture AN qu'en
#400 sur les dossiers législatifs — mais ici, contrairement aux dossiers, les
données de la 14e sont bien présentes (1 354 scrutins) : seul le
conditionnement diffère, et l'indexeur qui n'attendait que `json/*.json` y
trouvait 0 acteur.

**Trois schémas de `decompteNominatif`, pas deux** (relevé exhaustif sur les
quatre archives) : pluriel `pours`/`contres` (15e, 17e, et 4 105 des 4 106
scrutins de la 16e), singulier `pour`/`contre` avec `abstentions`/`nonVotants`
au pluriel (toute la 14e), et tout au singulier pour un unique scrutin.
L'indexeur d'avant #403 n'acceptait que le pluriel : il perdait donc en silence
la totalité de la 14e — et un scrutin de la 16e.

**Scrutins du Congrès écartés**. Ce scrutin isolé est celui du **Congrès du
4 mars 2024** (constitutionnalisation de l'IVG, uid `VTCGR5L16V1`), présent dans
l'archive AN de la 16e. Il est volontairement exclu (`AN_SCRUTIN_UID_PREFIXE`) :
le Congrès est une assemblée distincte — d'où les 24 sénateurs apparaissant dans
sa ventilation nominative — et sa numérotation **repart de 1 en partageant
l'espace de numéros de l'AN**. Il porte le n° 1, déjà attribué à la motion de
censure du 11/07/2022. Le publier tel quel donnerait une source primaire fausse
(vérifié : `/dyn/16/scrutins/1` renvoie bien la motion de censure) et le
confondrait avec elle dans la cohésion de groupe. Le publier *correctement*
suppose un identifiant et une source propres au Congrès, hors périmètre de
#403 : noté au ROADMAP plutôt que bâclé ici. Une fois exclu, l'index de la 16e
retombe exactement sur les chiffres de référence de l'issue (617 acteurs,
602 911 votes nominatifs).

**Traçabilité par vote, plus par profil**. `votes_source` énumère désormais
*toutes* les législatures couvertes (« législatures 15, 16, 17 ») — le singulier
sur un profil qui en agrège trois rendrait la limite du jeu de données illisible
(AGENTS.md §2.8). Comme aucune législature ne vaut plus pour tous les votes d'un
profil, chaque vote porte sa propre source primaire
(`https://www.assemblee-nationale.fr/dyn/<legislature>/scrutins/<numero>`,
vérifiée sur les 14e/15e/17e) au lieu de la laisser déduire de `votes_source` —
ce que faisait `web/old/v3/js/utils.js` par expression régulière, et qui devient
faux dès que plusieurs législatures sont agrégées.

### Budget CI : mesuré avant généralisation, pas après

C'était le point dur de l'issue — ~994 Mo de cache décompressé pour les quatre
législatures, un ordre de grandeur au-dessus de #400 (46 Mo), sur un pipeline
qui a déjà connu **deux OOM** sur l'index des amendements (#377, #392). Mesure
préalable (méthode [[budget-roster-mesure]] #376), sur les archives réelles :

| Forme d'index | 14 | 15 | 16 | 17 | Total |
| --- | --- | --- | --- | --- | --- |
| Plate (une copie du méta par votant) | 29,5 Mo | 140,7 Mo | 189,4 Mo | 381,5 Mo | **741 Mo** |
| Dédupliquée (`scrutins.json` + réf. `[uid, position]`) | 3,0 Mo | 13,1 Mo | 16,7 Mo | 35,5 Mo | **68 Mo** |
| Dédupliquée, gzippée (forme committée) | 0,13 Mo | 1,14 Mo | 1,51 Mo | — | **2,8 Mo** |

Les deux remèdes qui avaient fonctionné sur les amendements sont donc repris
tels quels : **forme dédupliquée** (#377) — le méta du scrutin, titre compris,
stocké une fois au lieu d'être recopié pour chacun de ses ~150 votants, d'où le
facteur 11 ci-dessus, et un pic de construction ramené à **138 Mio de RSS** pour
la 17e (la plus lourde) — et **shardage par acteur** (#392) : une tranche
`index_par_acteur/PA1567.json` (~55 Ko) est lue par candidat au lieu des 132 à
357 Mo d'index complets, ce qui ramène le coût par candidat à **0,02 s** après
matérialisation du cache.

**Législatures 14/15/16 figées** (`AN_SCRUTINS_LEGISLATURES_FIGEES`,
`src/build_scrutins_index_figes.py`, sortie committée sous
`raw_data/scrutins_an_figes/`), même schéma que
[[amendements-legislatures-figees]] mais **pas pour la même raison** : les
archives de scrutins sont petites (0,7 à 26 Mo) et toutes marquées `Cacheable`
par le CDN AN, donc rien à voir avec les `IncompleteRead` chroniques des
archives d'amendements (283-618 Mo). Ce qui est évité ici, c'est un coût
**répété inutilement par chaque shard CI** pour trois législatures closes
(Last-Modified vérifié : 2018-03-21, 2022-06-09, 2024-06-28) dont l'index est
identique à l'octet près d'un run à l'autre. Le chemin réseau reste fonctionnel
si le fallback committé manque : le gel est une économie, jamais une dépendance.

**Résultat mesuré, cache froid** : 18,9 s et un seul téléchargement (26 Mo, la
17e) pour l'ensemble ; **80 Mo** de cache disque au lieu des 992 Mo qu'aurait
coûtés la généralisation naïve — soit moins que les 251 Mo du cache
mono-législature *actuel*. Le cache hérité (fichier unique, forme plate) est
indiscernable d'un cache absent pour le lecteur : il est reconstruit, jamais
relu en mémoire — c'est précisément la relecture qui avait déclenché l'OOM
killer en #377.

**Effet de la fusion additive sur l'existant** : `votes[]` suit la règle « ancienne
entrée gagne » (`merge_profile.merge_lists_by_key`, AGENTS.md §3), et la clé de
fusion reste `(numero_scrutin, date)` —
inchangée, donc les 92 344 votes déjà collectés se réconcilient bien avec leur
équivalent recollecté au lieu de se dédoubler (vérifié : aucune collision
`numero`+`date` à l'intérieur d'une législature, et les périodes de législature
ne se chevauchent pas). Contrepartie : ces entrées existantes **conservent leur
forme d'avant #403**, sans `legislature` ni `source_url`, jusqu'à un run
`fresh_run=true`. C'est précisément le cas que le filtre de cohésion traite en
conservant les votes sans législature. Aucun changement de politique de fusion
n'est fait ici : enrichir champ à champ une entrée existante serait un
changement de comportement pour tous les votes, hors périmètre de #403.

**Gain éditorial** : 92 344 → **246 196 votes** (×2,7), 0 → **55 profils** avec
des votes de la 17e. Vérifié sur les quatre profils témoins de l'issue
(`christophe-bentz` 2 480 → 7 401, `beatrice-piron` 1 921 → 6 413,
`christine-le-nabour` 2 178 → 6 048, `antoine-villedieu` 1 041 → 4 202).

**Alternative écartée** : basculer les votes en lecture *cache-only* avec un job
CI dédié, comme les amendements ([[amendements-index-job-dedie-ci]]). Justifié
là-bas par des archives de 283-618 Mo dont le téléchargement échouait ; ici, une
seule archive active de 26 Mo reste à charge du chemin paresseux, pour un job CI
et un artifact en moins.
<a id="couverture-dossiers-hors-couverture-vs-zero"></a>
## Couverture des dossiers : « hors couverture de la source » ≠ « réellement à zéro » (#399) (2026-08-18)

**Contexte** : le quality gate signalait « aucun texte porté malgré une
période renseignée » pour tout gouvernement dont `textes[]` était vide. Après
#400, il ne restait que Fillon II/III — dont la XIII<sup>e</sup> législature
n'a **aucune archive publiée**. Le warning affirmait donc un défaut de
données là où il n'y a qu'une limite de source : un « 0 texte porté » se lit
comme un fait mesuré (§2.5), et ces warnings, qui ne diminueront jamais,
diluent les signaux réels — c'est exactement ce qui avait masqué #397 (473
warnings noyant 45 exclusions bien réelles).

### Décision : dériver la borne des législatures ingérées

Nouveau module `src/couverture_dossiers.py`, **stdlib pure, sans I/O** :

- il porte désormais `AN_DOSSIERS_ARCHIVES` (déplacé depuis
  `gouvernement_textes.py`, qui le ré-exporte — un seul inventaire) ;
- il y adjoint `LEGISLATURES_DEBUT` (date de première séance) ;
- `borne_couverture_textes()` = début de la plus ancienne législature
  ingérée, soit **2017-06-21** avec les archives XV/XVI/XVII ;
- `statut_couverture_textes(debut, fin)` classe une période en
  `couverte` / `partielle` / `hors_couverture` / `indeterminee`.

Le module est stdlib pure **parce que** ses deux consommateurs de rapport
(`audit_gouvernement_dataset.py`, `check_quality_gate.py`) ne doivent jamais
importer `requests` ni toucher au réseau : c'est ce qui interdisait de lire
l'inventaire directement dans `gouvernement_textes.py`.

Conséquences :

- **quality gate** : un `textes[]` vide n'est un avertissement que si la
  période est `couverte`. Hors couverture (ou à cheval), le constat passe
  dans un bloc **information** distinct, non compté dans les avertissements
  qualité. Les deux gouvernements Fillon quittent ainsi le compteur.
- **audit** : nouvelle section « Couverture des textes portés », borne
  affichée dans l'en-tête, et `N/D (hors couverture)` au lieu d'un `N/D` nu
  dans le tableau des plages. `nb_textes` reste `null` quand le champ
  `textes` est absent — `[]` (zéro observé) et champ absent (donnée
  manquante) ne sont pas fondus.
- **UI** (`GovernmentProfile.jsx`) : une note explicite le périmètre quand la
  couverture est partielle ou nulle, et le vide affiche « période non
  couverte […] ce n'est pas un “aucun texte porté” » au lieu du message
  générique.

### Alternative écartée : porter la couverture dans `meta` du profil

Inscrire `meta.couverture_textes` à la génération aurait été plus traçable
(la donnée dirait elle-même ce qu'elle couvre), mais aurait imposé un
changement de schéma **et** une régénération complète de `pivot_data` pour
que l'information apparaisse — les fichiers déjà committés seraient restés
muets, obligeant de toute façon à un repli calculé. La dérivation à la
lecture donne le bon résultat immédiatement, sur les données existantes.

### Duplication assumée côté UI

`pivotAdapter.js` redéfinit la borne (`GOVERNMENT_TEXTS_COVERAGE_START`) :
l'UI lit les JSON pivot, pas le code Python. La divergence est verrouillée
par un test (`tests/test_couverture_dossiers.py`) qui relit la constante dans
le fichier JS et la compare à `borne_couverture_textes()` — ajouter une
archive sans mettre l'UI à jour fait échouer la suite.

### Note connexe : libellé IncompleteRead

Le gate affichait « Erreurs IncompleteRead — Détectées : 0 » alors que le log
du même run montrait 5/9 segments repris en retry. Le comptage
(échecs **non rattrapés**) est le bon ; seul le libellé prêtait à confusion.
Renommé « Erreurs IncompleteRead non rattrapées », avec une ligne explicite
en console et en Markdown. Seuil inchangé.

Le warning « couverture ministérielle incomplète » est reformulé dans le même
esprit : « portefeuilles confirmés **par une source primaire** — absence de
confirmation, pas absence de portefeuille ». #398 l'a depuis rendu informatif
plutôt que systématique (« 8/11 » au lieu de « 0/11 ») sans le faire
disparaître : la couverture reste partielle tant que tous les ministres n'ont
pas de profil pivot.

---

<a id="gouvernement-premier-ministre-portefeuille"></a>
## `gouvernement_profile` : `premier_ministre` et `portefeuille` câblés depuis les mandats `MINISTERE` (#398) (2026-08-18)

**Contexte** : l'audit remontait deux taux à **zéro absolu** — `premier_ministre`
0/10, `membres[].portefeuille` 0/36 — documentés comme des limites de source.
Les deux justifications étaient périmées : #382/#383 avaient mappé
`typeOrgane == "MINISTERE"` (l'intitulé précis du portefeuille) en
`fonction_gouvernementale`, mais `gouvernement_roster.py` / `gouvernement_profile.py`
n'avaient pas été recâblés pour le lire. La donnée était **déjà dans le dépôt**,
inexploitée.

### Deux natures de mandats dans une même catégorie

`categorie == "fonction_gouvernementale"` en mélange deux, du même zip AMO30 :

| `typeOrgane` | Label | Ce qu'il dit |
| --- | --- | --- |
| `GOUVERNEMENT` | « Gouvernement (BORNE) » | l'appartenance à CE gouvernement |
| `MINISTERE` | « Ministère de l'éducation nationale et de la jeunesse » | le portefeuille précis |

Seul le **label** les distingue (`_est_mandat_appartenance_gouvernement`) :
`categorie` est identique, et `position_dans_hemicycle` n'est renseigné que sur
les premiers. Le rattachement à un gouvernement continue de passer par le
premier — désambiguïsation éditoriale par `libelle_an`, inchangée depuis #209 —
et le portefeuille ne fait que l'enrichir.

> **Corrigé depuis (#474)** — la ligne « `MINISTERE` → le portefeuille précis »
> de ce tableau était fausse, et le paragraphe qui la suit ne l'est plus qu'à
> moitié. Le label sépare bien les deux `typeOrgane`, mais un mandat
> `MINISTERE` n'est pas nécessairement un maroquin : un parlementaire en
> mission en porte un aussi, avec pour label le ministère **auprès duquel** il
> est missionné. Voir [[parlementaire-en-mission-nest-pas-ministre]].

### Chevauchements multiples : tous, jamais un choix arbitraire

Un ministre peut changer de portefeuille en cours de gouvernement. Mesuré sur le
dépôt : 15 membres ont un seul portefeuille chevauchant, 3 en ont deux, 1 en a
trois (Laurent Wauquiez sous Fillon III). L'option retenue est **une entrée
`membres[]` par période de portefeuille**, avec les dates du portefeuille et non
celles du mandat d'appartenance — ce que `schema_gouvernement.py` décrivait déjà
(« un enregistrement par ministre et par période si changement de
portefeuille »). Fondre les périodes en une seule entrée aurait effacé un des
portefeuilles réellement occupés ; en choisir un aurait été arbitraire (§2.5).

Vérification préalable sur données réelles : **aucun** mandat `MINISTERE` ne
déborde de la période du mandat d'appartenance qu'il chevauche (0 cas sur 24).
Les dates du portefeuille sont donc reprises telles quelles, sans rognage — rien
n'est recalculé.

### Traçabilité : d'où vient la `source_url`

Le schéma exige une `source_url` dès que `portefeuille` est renseigné. Or les
mandats `MINISTERE` sortent de `candidate_profile._extract_mandats_officiels`
**sans** `source_url` (aucun mandat de ce chemin n'en porte). Le repli retenu est
la `source_url` du mandat d'appartenance du même membre : les deux mandats
viennent du **même** zip `AN_ACTEURS_HISTORIQUE_ZIP_URL`, le second se contentant
de la porter explicitement. Ce n'est donc pas une URL choisie pour satisfaire le
validateur, c'est la source réelle de l'intitulé. Sans aucune URL disponible,
`portefeuille` retombe à `null` **avec un warning** plutôt que d'être publié
sans traçabilité (§2.3).

*Alternative écartée* : corriger `_extract_mandats_officiels` pour poser
`source_url` sur tous les mandats du référentiel. C'est la correction de fond,
mais elle impose de régénérer les 68 pivots individuels (coût réseau complet) et
déborde de #398 — le repli donne exactement la même URL en attendant.

### `premier_ministre` : le cumul de deux faits, jamais la période seule

Le Premier ministre est le membre de CE gouvernement dont un mandat `MINISTERE`
porte le label « Premier ministre ». Passer par le mandat d'appartenance hérite
de la désambiguïsation déjà éprouvée du roster : l'appariement par la seule
période aurait été fragile (deux gouvernements successifs se suivent d'un jour,
et un même Premier ministre peut en diriger deux — Philippe I puis II).

`acteur_ref` est extrait de `identite.source_url`
(`.../deputes/fiche/OMC_PA722190`) par simple motif, `schema_pivot` n'exposant
pas ce champ ; une fiche d'une autre forme (Sénat) donne `None` plutôt qu'un
identifiant reconstruit. Deux candidats donneraient `None` **avec un warning** :
trancher serait arbitraire. Aucun cas dans les données actuelles.

### Résultat mesuré (audit régénéré)

| Indicateur | Avant | Après |
| --- | --- | --- |
| `premier_ministre` renseigné | 0/10 (0 %) | **3/10 (30 %)** |
| `membres[].portefeuille` renseigné | 0/36 (0 %) | **24/41 (58,5 %)** |
| Warnings de collecte | 0 | 0 |

Le dénominateur passe de 36 à 41 : c'est l'effet du découpage par période de
portefeuille, pas de nouveaux membres. Les 3 Premiers ministres sont Attal
(gouvernement Attal) et Édouard Philippe (Philippe I et II) ; les 7 autres n'ont
pas de profil pivot dans le dépôt et restent `null` **à juste titre** — ce
chiffre progressera mécaniquement avec le passage à pleine échelle du roster
(#394/#192), sans qu'aucune valeur ne soit inventée entre-temps.

Le quality gate reste passant (`exit 0`) : la couverture ministérielle
incomplète y est un signal *soft*, désormais informatif (« 8/11 portefeuilles
confirmés » plutôt que « 0/11 »).

---

<a id="gouvernement-textes-fam-codes-archives"></a>
## `gouvernement_textes` : 3 derniers `fam_code` mappés ; `TSORTF02` tranché sur données réelles (#402) (2026-08-18)

**Contexte** : l'ingestion des archives XV/XVI (#400) a fait apparaître 3
`fam_code` absents de `_FAM_CODE_STATUT_MAP`. Suite directe de #397, même
nature — mais l'enjeu n'était plus le volume, il était de **ne pas deviner le
sens d'un libellé ambigu**.

**Impact réel** : sur les 726 dossiers gouvernementaux des 3 archives, le
module n'émettait que **4 warnings distincts** et n'excluait que **2 dossiers**
de `textes[]` — pour les autres, la promulgation détermine déjà le statut
(#400). Les « 46 warnings » relevés dans l'audit sont le même constat vu depuis
les profils : chaque profil de gouvernement porte la liste consolidée des
warnings de la collecte, donc les 4 warnings se répliquent sur les 10 profils
(44 warnings `gouvernement_textes` + 2 warnings d'exclusion
`gouvernement_profile`). Les 53 occurrences de `TSORTF02` du dataset, elles,
comptent tous les dossiers : seules 6 sont sur un dossier gouvernemental, et
seules 2 sont en position terminale, donc susceptibles de produire un warning.

| `fam_code` | Libellé AN | Décision |
| --- | --- | --- |
| `TSORTF02` | « adopté avec modifications » | `navette_en_cours` |
| `TSORTF14` | « voté par les deux assemblées du Parlement en termes identiques » | `adopte` |
| `TSORTF13` | « rejeté définitivement » | `rejete` |

### `TSORTF02` : le point à trancher, résolu par les données

L'issue posait la question : « adopté avec modifications » décrit-il une
adoption effective par la chambre, ou la poursuite de la navette comme
`TSORTF05` (« modifié ») ? Le libellé seul ne tranche pas — il commence par
« adopté ». Relevé sur les 53 occurrences des trois archives :

| Position de la décision `TSORTF02` | Cas | Ce qui suit |
| --- | --- | --- |
| Non terminale | 29 | **Toujours** une lecture dans l'autre chambre : « modifié » ×17, « adopté sans modification » ×8, CMP, rejet |
| Terminale, dossier promulgué | 17 | Publication au JO |
| Terminale, jamais promulgué | 7 | Rien — le texte n'est pas devenu loi |

Les 29 cas non terminaux établissent le sens : une chambre adopte un texte
**qu'elle a modifié**, donc l'autre chambre doit le réexaminer. C'est le même
fait procédural que `TSORTF05`, d'où le même statut. Les 7 cas terminaux non
promulgués le confirment *a contrario* : `DLR5L16N47697` (réforme de
l'audiovisuel public, Sénat le 11/07/2025) ou `DLR5L16N49849` ne sont jamais
devenus lois. Les mapper à `adopte` affirmerait une adoption que rien
n'établit — exactement ce qu'interdit §2.5.

Les deux codes restent **mappés séparément** plutôt que fusionnés : le
`fam_code` source est conservé tel quel dans le commentaire du mapping, avec
son libellé propre, de sorte que la relecture de l'archive vérifie la décision.

**Le mapping ne change rien à la sortie actuelle** : les 2 dossiers
gouvernementaux dont la décision terminale est `TSORTF02` portent tous deux un
acte de promulgation (`DLR5L15N42841`, `DLR5L16N48973`), donc la correction de
#400 leur donnait déjà `promulgue`. Le mapping supprime le warning et fixe le
comportement pour les données futures, sans rien réécrire.

### `TSORTF14` : adoption parlementaire ≠ promulgation

Unique occurrence : `DLR5L16N49373`, projet de loi constitutionnelle portant
modification du corps électoral calédonien — Sénat « adopté » le 02/04/2024,
puis AN « voté par les deux assemblées du Parlement en termes identiques » le
14/05/2024. Le vote conforme des deux chambres est une adoption parlementaire
achevée : `adopte`. Le texte n'a jamais été promulgué (Congrès jamais réuni,
dissolution de juin 2024) — c'est précisément la distinction que le statut doit
préserver, et la raison pour laquelle `adopte` n'est pas écrasé par la
promulgation dans `_STATUTS_CORRIGES_PAR_PROMULGATION`.

### `TSORTF13` : un rejet par vote, pas par 49.3

Unique occurrence : `DLR5L16N45929`, règlement du budget 2021 — adopté à l'AN
(13/07/2022), rejeté au Sénat, adopté en nouvelle lecture, rejeté à nouveau au
Sénat, puis **rejeté en lecture définitive** à l'AN le 03/08/2022. Jamais
promulgué. `rejete` avec `sort_49_3 = False` : le rejet est prononcé par un
vote, à la différence de `TSORTF24` (rejet consécutif à l'adoption d'une motion
de censure), qui reste seul à porter `rejete_49_3`.

### Résultat mesuré (726 dossiers gouvernementaux, 3 archives)

| Indicateur | Avant | Après |
| --- | --- | --- |
| Warnings distincts à la collecte | 4 | **0** |
| Warnings cumulés sur les 10 profils de gouvernement | 46 | **0** |
| Dossiers à `statut = None` (exclus de `textes[]`) | 2 | **0** |
| `adopte` | 187 | 188 |
| `rejete` | 8 | 9 |

Les deux textes réintégrés : le règlement du budget 2021 sous Borne
(`rejete`) et le projet de loi constitutionnelle calédonien sous Attal
(`adopte`). Les autres statuts sont inchangés — le mapping de `TSORTF02` ne
réécrit rien, il ferme le trou.

Les 10 `fam_code` observés sur une décision de séance de dossier
gouvernemental (`TSORTF01/02/03/05/06/07/13/14/18/24`) sont désormais tous
mappés, et **aucun code non mappé ne subsiste en position terminale**. La
protection §2.5 reste active et testée : un `fam_code` réellement inconnu
produit toujours `statut = None` et un warning.

---

<a id="dossiers-multi-archives-origine-document"></a>
## Dossiers législatifs : ingestion multi-archives, origine par document déposé, statut `promulgue` (#400) (2026-08-18)

**Contexte** : `gouvernement_textes.py` ne lisait qu'une archive, celle de la
XVII législature. Elle est multi-législature mais ne garde des précédentes
qu'une **traîne résiduelle** : aucun projet de loi antérieur à la XVI. Les
gouvernements Borne, Castex et Philippe I/II étaient donc à zéro texte.

### Inventaire des archives

Deux conventions de nommage coexistent chez l'AN — c'est ce qui rend
l'inventaire non évident, et ce qui m'avait fait conclure à tort dans une
première version de #400 que seules les XVI/XVII existaient.

| Législature | Nom de fichier | Taille | Exploitable |
| --- | --- | --- | --- |
| 12, 13 | *(aucune des deux formes)* | — | non, 404 |
| 14 | `Dossiers_Legislatifs_XIV.json.zip` | 2,5 Mo | **non** |
| 15 | `Dossiers_Legislatifs_XV.json.zip` | 15,2 Mo | oui |
| 16 | `Dossiers_Legislatifs.json.zip` | 9,1 Mo | oui |
| 17 | `Dossiers_Legislatifs.json.zip` | 10,25 Mo | oui |

Le listing de répertoire est désactivé (404 même sur les chemins valides) :
l'inventaire ne peut pas être découvert dynamiquement et doit être tenu à jour
dans `AN_DOSSIERS_ARCHIVES`.

**La XIV est inexploitable** : changement d'architecture du jeu de données AN
entre la XIV et la XV (déjà constaté côté amendements). Son archive contient
un JSON monolithique de 36 Mo décompressés, structuré en
`export.textesLegislatifs.document[]` — 7120 `document`, **aucun
`dossierParlementaire`**. Fillon II/III (XIII) sont hors d'atteinte
définitivement.

### Origine : le document déposé, pas le titre

Le signal historique était le préfixe de `titreDossier.titre` (spike #207). Il
ne fonctionne que sur les XVI/XVII : **sur la XV les titres sont descriptifs**
(« Taxe sur les services numériques », « Démocratie plus représentative,
responsable, efficace ») et le filtre y retenait **zéro** projet de loi déposé
entre 2017 et 2019.

Le signal retenu est le **type du document réellement déposé** — préfixe de
l'uid du `texteAssocie` de l'acte `*-DEPOT` le plus ancien : `PRJL` (projet de
loi), `PION` (proposition), `PNRE` (résolution, hors champ). Sur le corpus
complet, le filtre par titre ne voyait que **271 des 726** dossiers
gouvernementaux.

`procedureParlementaire.code` sert de repli quand aucun document n'est
résolvable, et **seulement pour les codes univoques** : les codes 5 et 7
(« Projet **ou** proposition de loi organique/constitutionnelle ») en sont
exclus, car deviner violerait §2.5.

Le document **prime sur la procédure** quand les deux divergent : 8 dossiers de
règlement du budget sont typés « Proposition de loi ordinaire » à la source
alors que le document déposé est bien un `PRJL`. Le type du texte réellement
déposé fait foi.

### Déduplication inter-archives

Un dossier figure dans plusieurs archives. L'arbitrage se fait **par uid, la
législature la plus élevée l'emportant** : elle porte l'état le plus à jour des
`actesLegislatifs`, donc du statut — un texte « en navette » dans la XVI peut
être « adopté » dans la XVII.

Deux points d'implémentation non évidents :

- **Le nom de fichier dans le zip porte l'uid** (vérifié sans exception sur les
  10 967 dossiers). L'arbitrage se fait donc sur les seuls `namelist()`, sans
  rien désérialiser. Charger les trois archives en mémoire pour comparer
  coûterait plusieurs centaines de Mo, sur un pipeline qui a déjà connu deux
  OOM (#377, #392). `iter_dossiers_bruts` est un générateur : un seul dossier
  vivant à la fois.
- **L'arbitrage utilise `max()` explicite**, pas l'écrasement dans l'ordre de
  parcours. Ma première version dépendait de l'ordre d'appel — un test
  vérifiant l'invariance à l'ordre l'a attrapée.

### Statut `promulgue`

L'ingestion des archives anciennes a fait remonter **62 textes marqués
`navette_en_cours` et 3 marqués `rejete` qui portaient un acte de promulgation**
(`PROM`/`PROM-PUB`, publication au Journal officiel). Exemple : la convention
sur les infractions à bord des aéronefs, dernière décision de séance
« modifié » au Sénat le 2021-01-28, **promulguée le 2021-02-03** — publier
« en navette » en 2026 serait faux.

Décision (arbitrage humain, comme pour `adopte_cmp` en #397) : **statut dédié
`promulgue`**, appliqué comme correctif ciblé.

Il ne remplace **jamais** `adopte_cmp` ni `adopte_49_3` : ces statuts portent
la voie procédurale suivie, que `promulgue` ne dit pas. Les écraser ferait
disparaître le fait CMP ou 49.3 de 116 textes — exactement le collapse
qu'interdit §2.4. `retire` n'est pas écrasé non plus : retrait puis
promulgation est contradictoire, et trancher n'est pas notre rôle. Le warning
d'un `fam_code` non mappé est conservé même quand la promulgation détermine le
statut : le code reste inconnu et mérite d'être signalé.

### Résultat mesuré

| Gouvernement | Avant #400 | Après |
| --- | --- | --- |
| PHILIPPE_2 | 0 | **282** |
| CASTEX | 0 | **195** |
| BORNE | 0 | **110** |
| LECORNU_II | 60 | 63 |
| BAYROU | 26 | 35 |
| ATTAL | 8 | 24 |
| BARNIER | 10 | 13 |
| PHILIPPE | 0 | 1 |
| FILLON_2 / FILLON_3 | 0 | 0 (hors couverture définitive) |
| **Total** | **104** | **723** |

Sur les profils individuels — le gain le plus large, car la même archive
alimente `candidate_profile.py` (lignes 1945 et 2108) : index acteur→textes
portés de **1 076 → 1 643 acteurs** et **8 351 → 24 333 associations** (×2,9).

**Budget CI** : cache 14 → 46 Mo, index construit en 2,3 s pour **55 Mo de RSS**
— sans risque d'OOM grâce au générateur.

**Invalidation des index** : `index_texte_titre.json` et
`index_acteur_textes.json` sont renommés en `*_v2.json`. Sans nouveau nom, un
cache CI ou local existant aurait servi silencieusement l'ancien index
mono-archive, et le gain aurait été invisible sans que rien ne le signale.

**Reste à traiter** : 3 `fam_code` apparaissent dans les archives anciennes et
ne sont pas mappés — `TSORTF02` (« adoptée avec modifications », 53),
`TSORTF14` (« voté par les deux assemblées en termes identiques »), `TSORTF13`
(« rejeté définitivement »). Ils ne coûtent que 2 exclusions, la promulgation
déterminant le statut des autres. Même nature que #397.
*Traité en #402 — voir [la section dédiée](#gouvernement-textes-fam-codes-archives) :
les 3 codes sont mappés, `TSORTF02` tranché sur données réelles.*

---

<a id="gouvernement-textes-fam-codes-manquants"></a>
## `gouvernement_textes` : 3 `fam_code` manquants excluaient 42 % des textes ; `adopte_cmp` ajouté à la nomenclature (#397) (2026-08-18)

**Contexte** : la revue de l'audit `audit_pipeline_20260817T153911Z` a montré
518 warnings sur les profils de gouvernement, dont **473 du seul type
`gouvernement_textes`**. Dépliés, ils provenaient de **3 `fam_code` distincts
seulement**, absents de `_FAM_CODE_STATUT_MAP`.

Le comportement en place était correct au regard d'AGENTS.md §2.5 — un code
inconnu donne `statut = None`, jamais un statut par défaut — mais
`gouvernement_profile.py` exclut alors le dossier de `textes[]`. Résultat :
**45 dossiers exclus contre 61 retenus, soit 42 % des textes gouvernementaux
absents du jeu de données**, dont le *Projet de loi de finances pour 2025*.

**Sens des trois codes, relevé dans le dataset source** (`statutConclusion.libelle`
du dump AN), donc sans interprétation de notre part :

| `fam_code` | Libellé AN | Décision |
| --- | --- | --- |
| `TSORTF03` | « adopté sans modification » | `adopte` |
| `TSORTF18` | « adopté, dans les conditions prévues à l'art. 45 al. 3 » | `adopte_cmp` (nouveau) |
| `TSORTF05` | « modifié » | `navette_en_cours` |

**Arbitrage sur `TSORTF18` (décision humaine, option B retenue)** : l'issue est
une adoption, mais par une voie procédurale distincte — approbation du texte
élaboré en commission mixte paritaire, sur demande du Gouvernement. Deux
options étaient ouvertes : fondre dans `adopte`, ou créer un statut dédié. Le
statut dédié `adopte_cmp` a été retenu, par symétrie explicite avec le
traitement du 49.3 en #208 : le fait procédural n'est jamais fusionné avec
l'issue du vote (AGENTS.md §2.4). `sort_49_3` reste `False` — `adopte_cmp`
n'est pas un statut 49.3, et le validateur refuse la combinaison
`adopte_cmp` + `sort_49_3 = True`. Il n'y a pas de cumul possible : si le
Gouvernement engage sa responsabilité sur le texte de CMP, la décision de
séance la plus récente porte `TSORTF06`/`TSORTF24`, pas `TSORTF18`.

**`TSORTF05` réaligne un test sur sa propre intention** :
`test_derniere_decision_de_seance_chronologique_prevaut_sur_une_decision_anterieure`
décrivait dans sa docstring un dossier « toujours en navette », mais assertait
`statut is None` — parce que le code ne savait pas encore l'exprimer. La
docstring du module anticipait déjà ce cas sans l'avoir encodé.

**Résultat mesuré après régénération des 10 gouvernements** :

| Indicateur | Avant | Après |
| --- | --- | --- |
| Textes retenus | 61 | **104** |
| Warnings gouvernement | 518 | **2** |
| `adopte` | 20 | 43 |
| `adopte_cmp` | — | 16 |
| `navette_en_cours` | 36 | 40 |

Les 2 warnings restants relèvent d'une autre cause (`chambre_depot_initial`
indéterminée sur `DLR5L17N50840` et `DLR5L17N53195`).

**La nomenclature reste fermée.** L'élargissement du mapping ne l'affaiblit
pas : un `fam_code` réellement inconnu produit toujours `statut = None` et un
warning. Un test dédié le vérifie, précisément parce qu'un tel élargissement
est le moment où cette protection risque d'être perdue de vue.

**Propagation** : `make_empty_comptages_statuts()` dérive de
`KNOWN_STATUTS_TEXTE_GOUVERNEMENTAL`, donc `adopte_cmp` s'est propagé sans
modification supplémentaire côté schéma et audit. En revanche, **trois jeux de
fixtures de tests énuméraient les statuts en dur** et sont devenus invalides —
ils dérivent désormais de la nomenclature. Seule l'UI
(`web/UI_finale/src/data/pivotAdapter.js`) exige une entrée manuelle, pour
l'ordre d'affichage et les libellés : « adopté (texte de CMP) ».

**Suites** : #400 (ingérer les archives `/15/` et `/16/`, qui débloqueront
Borne et Castex, aujourd'hui à 0), #399 (bruit d'audit — ce sont ces 473
warnings qui avaient masqué le présent défaut), #398 (`premier_ministre` et
`portefeuille`).

---

<a id="shardage-extract-roster-groupes"></a>
## Shardage de `extract-roster-groupes` en 8 tranches, découpées par modulo (#394) (2026-08-18)

**Contexte** : `extract-roster-groupes` traitait les 752 membres du roster dans
un job unique. Après [[index-amendements-sharde-par-acteur]] (#392), le coût
marginal mesuré est de **5,05 s/membre** (contre 11,7 s avant, [[budget-roster-mesure]] #376),
soit **63 min**
pour le roster complet — au-delà du timeout de 60 min, et surtout exposé en
totalité à une préemption runner ([[resilience-generate-data-shutdown-signal]], #228) : une
préemption à la 55ᵉ minute faisait perdre les 752 extractions.

**Décision** : découper le job en une `matrix` de 8 shards (`fail-fast: false`,
`max-parallel: 1`), chacun ~94 membres ≈ 8 min, avec **un artifact par shard**
récupéré par `merge-and-pivot` via `pattern:` + `merge-multiple: true` — le même
schéma que les shards `extract-an` (#344). Une préemption ne coûte donc plus
qu'une tranche.

**Découpage par position modulo, pas par blocs contigus** — le point non
évident. `raw_data/roster_candidats.json` est **trié par groupe parlementaire**
(vérifié : 7 blocs contigus pour 7 groupes distincts, du plus gros au plus
petit). Un découpage en tranches contiguës aurait donné des shards très inégaux
en coût, un seul héritant des ~190 membres du plus gros groupe. Le modulo
(`i % total == index`) répartit les groupes uniformément.

Cette propriété est facile à casser lors d'un refactor **sans qu'aucune
assertion de taille ne s'en aperçoive** : 752/8 = 94 tombe juste, donc un
découpage contigu produit lui aussi 8 tranches de 94. Un test dédié
(`test_select_shard_repartit_les_groupes_contigus`) vérifie donc la vraie
propriété — chaque shard voit *tous* les groupes, aucun au-delà de sa part —
sur une entrée aux tailles de groupes inégales. Vérifié discriminant : réécrit
en découpage contigu, seul ce test échoue.

**Nombre de shards paramétré à un seul endroit** : le job préparatoire
`prepare-roster-matrix` expose deux sorties, `shards` (la liste pour la matrix)
et `shard_total` (le dénominateur passé à `--shard I/N`). Une première version
recalculait le total dans l'expression du flag
(`outputs.shards == '[0]' && 1 || 8`) : dupliquer la logique ainsi garantissait
qu'un changement du nombre de shards produise un `--shard` incohérent, donc des
membres jamais extraits, **silencieusement**.

**Interaction avec le rollout progressif** : quand `roster_extraction_limit > 0`
([[limit-sample]]), le total est forcé à 1 — `--shard 0/1`
retourne la liste entière, et `--limit` s'applique ensuite comme avant. Vérifié
que le mode rollout est **strictement identique** au comportement pré-#394. Le
shardage ne s'active donc que sur un run complet (`limit = 0`), le seul cas où
il sert à quelque chose. À l'inverse, N shards en rollout multiplieraient le
volume traité, puisque `--limit` s'applique *par job*.

`--shard` est appliqué **avant** `--limit`/`--sample`/`--skip-existing`, et est
déterministe à liste source constante : un membre retombe toujours dans le même
shard, condition nécessaire pour que `--skip-existing` garde son sens d'un run
à l'autre.

**Vérification à l'exécution** (`--shard 3/376`, 2 membres) : profils complets,
108 et 115 mandats avec la taxonomie étendue de #382, 3 673 et 35 969
amendements — le chemin shardé ne dégrade rien.

---

<a id="scission-cache-ci-ecartee"></a>
## Scission du cache CI `.cache` par sous-répertoire : écartée (#374, fermée non planifiée) (2026-08-17)

**Contexte** : #374 proposait de scinder le cache GitHub Actions partagé
`public-data-cache-an-*` (`path: .cache`) en deux entrées — amendements d'un
côté, le reste de l'autre — au motif que chaque shard `extract-an` restaurait
~915 Mio alors qu'il n'avait besoin que de `.cache/acteurs_an/` à l'étape 0
(résolution d'identité), sur un budget de 5 min/shard.

**Réévaluation après [[cache-amendements-forme-dedupliquee]] (#377) et
[[nettoyage-archive-brute-amendements]] (#264)** :

1. *L'argument principal a disparu.* #374 chiffrait le gaspillage sur les
   « 3 archives amendements ≈ 1,22 Gio ». #264 supprime `amendements.zip`
   dès l'index construit : ces archives n'entrent plus jamais dans le cache.
2. *Les index ont fondu.* #377 : législature 16 de 4,67 Go à 211 Mo. Clé AN
   mesurée après coup : 965 Mo au total, dont 673 Mo d'amendements (69 %) —
   mais des données désormais réellement utiles, plus des archives jetables.
3. *Défaut logique de la proposition elle-même* : `extract-an` **consomme**
   les amendements (`build_profile` appelle `fetch_amendements_officiels`
   pour tout `chambre == "deputes"`, et ce job traite des députés), tout
   comme `extract-roster-groupes`. Les deux jobs qui restaurent cette clé ont
   donc besoin des 673 Mo **dans le même job** : scinder en deux entrées
   restaurées au même endroit ne supprime aucun octet, il les déplace.

**Décision : fermée non planifiée.** Le bénéfice ne se matérialiserait que
via une restauration *différée* (un second `actions/cache/restore` placé plus
bas dans le job), pas via la simple scission proposée — et il resterait
limité au seul chemin d'erreur (un shard gelé avant d'atteindre les
amendements aurait perdu moins de temps). Coût/bénéfice défavorable face à un
changement structurel sur 3 jobs, avec un risque de course sur l'écriture du
cache partagé déjà documenté (#248 sous-issue 4). À rouvrir en visant la
restauration différée si le budget de 5 min/shard redevient contraignant
après la recalibration de #376.

**Note connexe** : la législature 17 dispose d'un index construit avec succès
(`derniere_construction_reussie: true`, 193 Mo) — les `IncompleteRead` sur
son archive ne sont donc pas systématiques, contrairement à ce que laissaient
penser les runs précédents et à ce qui avait été affirmé dans les entrées
antérieures de ce fichier.

<a id="amendements-zero-silencieux-acteur-ref"></a>
## Zéro amendement silencieux quand l'acteurRef est introuvable (#265, fix 5) (2026-08-17)

**Contexte** : re-check de #265 (« Zero amendments according to audit ») après
la résolution de [[cache-amendements-forme-dedupliquee]] (#377),
[[nettoyage-archive-brute-amendements]] (#264) et
[[verification-bout-en-bout-legislatures-figees]] (#273). Le fix 5 de son
investigation restait ouvert : déterminer si le zéro-sans-warning observé sur
les profils `candidat_declare` était une absence réelle ou un second bug
indépendant.

**Réponse : les deux à la fois.**
- *Absence réelle* pour `bruno-retailleau` (sénateur) et `jordan-bardella`
  (MEP) : `fetch_amendements_officiels` n'est jamais appelée pour eux, l'appel
  étant gardé par `if chambre == "deputes"` dans `build_profile`. Zéro
  correct, aucun warning attendu.
- *Bug indépendant réel* : quand `url_an_ou_senat` est absent ou non parsable,
  `fetch_amendements_officiels` retournait `[]` **sans aucun warning** — un
  zéro parfaitement silencieux, indiscernable d'une absence légitime.

**Ce n'était pas théorique** : `marine-le-pen` et `jean-luc-melenchon` avaient
tous deux `url_an_ou_senat: None` dans leur profil brut, écrit partiellement
par un run interrompu par l'OOM ([[oom-lecture-amendements-par-candidat]]),
accompagné du warning trompeur « aucun mandat français connu ». Leurs
amendements ne survivaient que par la fusion additive avec des runs
antérieurs — un `--no-merge`/`fresh_run=true` les aurait effacés en silence.
Régénération après correctifs : `url_an_ou_senat` correctement renseigné
(`.../OMC_PA720614`), 8 999 amendements, zéro warning.

**Décision** : émettre un warning `WARNING_PREFIX_AMENDEMENTS_INDISPONIBLES`
quand aucun acteurRef ne peut être extrait. Sans risque de bruit pour les
sénateurs/MEP puisqu'ils n'atteignent jamais ce chemin — le garde
`chambre == "deputes"` en amont fait que cette situation est *toujours* une
anomalie, jamais un cas nominal.

**État des 5 fixes de #265 après ce re-check** : fix 1 (séquencement
`needs: [extract-amendements-an]`) appliqué ; fix 2 caduc (alternative au
fix 1, explicitement conditionnée à « si le parallélisme doit être
préservé ») ; fix 3 (escalade en hard failure du quality gate) sorti dans
l'issue dédiée #378 — arbitrage produit (bloquer le commit vs. laisser passer
la panne CDN chronique de la législature 17), tranché depuis :
[[amendements-zero-pas-de-hard-fail]] (pas de blocage, mais signal affiché en
tête de rapport) ; fix 4 résolu par #268/#273 ; fix 5 tranché et
corrigé ici. #265 close : symptôme initial résolu, 32 279 amendements sur les
candidats déclarés contre 0 à son ouverture.

**Tests** : deux formes d'URL invalide (`None` et URL sans acteurRef)
produisent bien un warning ; non-régression quand `warnings` n'est pas
fourni par l'appelant (paramètre optionnel). Suite complète : 1153/1153.

<a id="verification-bout-en-bout-legislatures-figees"></a>
## Vérification de bout en bout des législatures figées 15/16 (#273, clôture de l'epic #268) (2026-08-17)

**Contexte** : sous-issue 5/5 de #268, débloquée une fois #269/#270/#271/#272
fermées. Vérification uniquement, aucun changement de code attendu — et
aucun n'a été nécessaire.

**Constat préalable, non prévu par l'issue** : la vérification n'a pu
aboutir qu'après la résolution de deux problèmes découverts entre-temps, qui
empêchaient toute collecte d'amendements et auraient fait conclure à tort à
un échec de l'epic #268 — [[cache-amendements-forme-dedupliquee]] (#377,
l'ancienne forme plate déclenchait l'OOM killer avant collecte) et
[[nettoyage-archive-brute-amendements]] (#264). Avant eux, l'audit
rapportait encore 97,92 % des profils à 0 amendement alors que les index
figés étaient déjà committés et corrects.

**Critère 1 — quality gate §3d** (run local réel, exit code 0) : les
législatures 14, 15 et 16 sont rapportées **❄️ figé (dossier clos, non
reconstruit)**, jamais **❌ jamais construit**. Seule la 17 est en « jamais
construit » — législature active, `IncompleteRead` répétés sur le CDN
`data.assemblee-nationale.fr`, problème réseau distinct et préexistant
([[amendements-legislatures-figees]]), explicitement hors périmètre.

**Critère 2 — non-régression du symptôme « zero amendments »** (profils
régénérés avec le pipeline réel, aucun appel réseau pour 14/15/16) :

| Profil | L14 | L15 | L16 | Total pivot |
|---|---|---|---|---|
| `damien-abad` | 2 896 | 5 989 | 1 589 | 10 474 |
| `jerome-guedj` | 288 | 0 | 5 827 | 6 115 |

Deux points élucidés au passage, tous deux préexistants et **non** des
pertes de données — consignés pour éviter qu'une future vérification ne les
prenne pour des régressions :
1. Le champ `legislature` n'existe pas dans le schéma pivot des
   `amendements[]` (contrairement à `textes_portes[]`, qui le porte) : la
   ventilation par législature ci-dessus provient des profils bruts, pas des
   pivots. Choix de conception de `schema_pivot.py`, jamais remis en cause.
2. L'index contient 9 217 *références* pour Guedj en L16 alors que son
   profil n'affiche que 5 827 amendements : ce sont 5 827 numéros distincts,
   dédupliqués par `merge_profile._amendement_key` sur `(numero,
   texte_vise, date)`. Un même amendement peut légitimement être référencé
   plusieurs fois pour un même élu (rôles de signature multiples).

**Critère 3** : #265 commentée pour signaler la résolution de la piste
légis 15/16 (fix 4 de son investigation), sans clore l'issue — ses fixes
1/2/3/5 restent ouverts, hors périmètre de #268.

**Reste attendu** : la section 3c (couverture amendements) affiche encore 39
avertissements « collecte en échec » — ce sont des warnings *hérités* dans
les pivots non régénérés depuis les runs cassés par l'OOM, pas un défaut
actuel du pipeline. Ils se purgent d'eux-mêmes à la régénération
(`merge_profile._prune_stale_warnings` retire ce warning dès qu'un profil
porte des amendements), ce que confirment les deux profils régénérés
ci-dessus : zéro warning amendements pour eux.

**Tests** : suites demandées par l'issue au vert (`test_candidate_profile.py`,
`test_quality_gate_amendements.py`, `test_build_amendements_index.py`, 182
tests) ; suite complète 1151/1151.

<a id="nettoyage-archive-brute-amendements"></a>
## Suppression de l'archive brute `amendements.zip` après construction de l'index (#264) (2026-08-17)

**Contexte** : `_download_and_build_amendement_index` téléchargeait
`amendements.zip` (283-618 Mo selon la législature), le parsait, puis ne le
supprimait jamais — ni après succès, ni après échec. Constaté sur le run #32
de `generate-data.yml` : l'artifact `amendements-index-an` pesait 328 Mio
alors que l'index utile ne représente que quelques Mo, la quasi-totalité
étant le zip brut conservé sans raison.

**Décision** : `try`/`finally` autour du téléchargement et du parsing, avec
`zip_path.unlink(missing_ok=True)` en sortie — dans **tous** les cas (succès,
échec réseau, `BadZipFile`). Justification du nettoyage même en échec : le
fichier n'est jamais relu ensuite, ni par la lecture cache-only
(`_read_cached_amendements_acteur` ne lit que l'index), ni pour reprendre un
téléchargement entre deux tentatives (`_download_amendements_zip` réécrit
toujours depuis zéro, en `wb`) — un fichier partiel ou invalide n'a donc pas
plus d'utilité qu'une archive correctement parsée. Suppression best-effort
(`except OSError: pass`), comme l'écriture du cache elle-même : un échec de
nettoyage ne doit jamais masquer l'erreur métier en cours de propagation.

**Portée** : `index_path` n'est jamais touché par ce nettoyage — la
préservation d'un index existant en cas d'échec ([[amendements-index-quality-gate-fraicheur]],
#253) et le cache d'échec inter-jobs (#246) sont inchangés, ce que la suite
de tests existante vérifie toujours.

**Mesure** (cache local, après nettoyage des zips résiduels) : 1,6 Go →
480 Mo, soit **1,06 Go de zips morts** supprimés (99 + 619 + 347 Mo pour les
législatures 14/15/16). Ce gain se cumule avec celui de
[[cache-amendements-forme-dedupliquee]] : le cache amendements complet passe
de 7,9 Go (forme plate + zips) à 480 Mo.

**Hors périmètre** (repris tel quel de l'issue) : les autres archives zip du
dépôt (`dossiers.zip`, `acteurs.zip`, `syseron.xml.zip`...) ne sont pas
traitées ici — celles-ci sont, à l'inverse, réellement relues d'un run à
l'autre comme cache de contenu, la comparaison ne tient donc pas telle
quelle et mériterait sa propre évaluation.

**Tests** : succès → zip absent et index présent ; échec de téléchargement →
pas de fichier partiel résiduel ; `BadZipFile` → zip supprimé malgré
l'échec. Les 3 tests ont été vérifiés comme réellement discriminants (ils
échouent tous les 3 si l'on neutralise le `finally`). Suite complète :
1151/1151.

<a id="cache-amendements-forme-dedupliquee"></a>
## Cache amendements stocké et lu sous forme dédupliquée (#377) (2026-08-17)

**Contexte** : correctif de l'OOM diagnostiqué dans
[[oom-lecture-amendements-par-candidat]]. Le mécanisme de déduplication
existait déjà (`_aggregate_amendements_index`, écrit pour committer les
législatures figées sous la limite GitHub de 100 Mo par blob) mais était
défait juste avant l'usage qui posait problème : `_load_frozen_amendement_index`
appelait `_expand_aggregated_amendements_index` pour matérialiser le cache
sous forme plate, « pour que le reste du pipeline n'ait pas à distinguer les
deux origines ». C'est ce compromis qui coûtait un facteur ~21.

**Décision** : le cache disque (`AMENDEMENTS_CACHE_DIR/<legislature>/`)
stocke désormais la MEME forme dédupliquée que le fallback committé, en clair
plutôt que gzippée — `amendements.json` (chaque amendement une fois, clé
`numero`) + `index_par_acteur.json` (acteurRef -> `[{numero,
role_signataire}]`). Plus aucune expansion vers la forme plate n'a lieu :
- Lecture : `_read_cached_amendements_agreges` (le couple) et
  `_read_cached_amendements_acteur(legislature, acteur_ref)` qui ne
  matérialise que les entrées de CET acteur. Remplace
  `_read_cached_amendement_index`, qui renvoyait l'index entier expansé.
- Écriture : `_write_cached_amendements_agreges`, partagée par le chemin
  réseau (`_download_and_build_amendement_index`, qui agrège désormais avant
  d'écrire) et le fallback figé.
- `_expand_aggregated_amendements_index` n'est plus utilisée en production
  (conservée : inverse exact, utile aux tests de round-trip).

**Migration automatique** : les deux fichiers sont exigés ensemble pour
qu'un cache soit valide. Un cache écrit avant #377 n'a qu'un
`index_par_acteur.json` plat — il est donc indiscernable d'un cache absent
(`_read_cached_amendements_acteur` renvoie `None`, `amendements_index_deja_figee`
renvoie `False`, section 3d du quality gate rapporte « jamais construit »),
ce qui force sa reconstruction au format compact au lieu de sa relecture en
mémoire. L'écriture écrase le fichier plat au passage, libérant les Go qu'il
occupait. Le rapport du quality gate a été aligné sur ce même verdict, sinon
il aurait annoncé « construit » un index que la collecte ignore.

**Mesures (machine locale, 7,6 Gio de RAM)** :

| Indicateur | Avant | Après |
|---|---|---|
| Cache disque (législatures 14+15+16, hors zips) | 7,9 Go | **480 Mo** |
| Législature 16 seule | 4,67 Go | 211 Mo |
| Pic RSS, 7 candidats × 3 législatures | 6,83 Go (**OOM**) | **1,40 Go** |

**Effet fonctionnel, au-delà de la mémoire** : la collecte d'amendements
fonctionne à nouveau. Avant ce correctif, l'audit rapportait 97,92 % des
profils à 0 amendement (seul Wauquiez en avait) — conséquence directe des
OOM qui tuaient le job avant collecte. Après : Mélenchon 18 721, Guedj
9 516, Le Pen 9 917, Wauquiez 2 702, Philippe 1 966, Attal 343 (vérifié via
`fetch_amendements_officiels` sur le cache migré). À rapprocher de #265
(« Zero amendments according to audit »), qui pourrait se refermer en
grande partie de lui-même sur un prochain run complet.

**Reste ouvert** :
- La législature 17 (active, non figée) n'a toujours pas d'index : son
  téléchargement échoue en `IncompleteRead` côté CDN AN, problème réseau
  distinct et préexistant ([[amendements-legislatures-figees]]).
- Coût CPU : ~8,6 s par candidat pour relire les 3 index compacts (480 Mo de
  JSON reparsés à chaque candidat). Acceptable au volume actuel, mais à
  reconsidérer avant un run à pleine échelle (#376) — une mémoïsation reste
  écartée pour l'instant (l'expansion Python des `{numero, role_signataire}`
  fait passer 480 Mo de JSON à ~3-4 Go résidents si les 3 législatures sont
  gardées simultanément, cf. le pic de 1,40 Go pour une seule à la fois).
- Le pic mémoire lors de la *construction* initiale (chemin réseau :
  `_parse_amendements_zip` produit la forme plate avant agrégation) n'est
  pas traité ici — il ne concerne que le job CI dédié, sur la seule
  législature 17.

**Tests** : `_read_cached_amendements_acteur` (résolution des références,
acteur inconnu → `[]` vs cache absent → `None`, référence orpheline ignorée,
cache hérité plat traité comme absent, cache corrompu), migration du fallback
figé sans expansion, `amendements_index_deja_figee` sur cache hérité, et
alignement du rapport 3d du quality gate. Suite complète : 1148/1148.

<a id="parallele-oom-local-runner-ci"></a>
## Parallèle RAM entre l'exécution locale et les runners GitHub Actions hébergés, diagnostic ajouté (2026-08-17)

**Contexte** : suite à [[oom-lecture-amendements-par-candidat]] (ci-dessous) —
plusieurs OOM réels confirmés en local (`journalctl -k`) sur `extract-an`/
`extract-roster-groupes`, cause identifiée précisément (rechargement complet
en mémoire de l'index amendements d'une législature, jusqu'à 4,35 Gio pour
la 16e, par candidat). Question posée : ce même mécanisme peut-il expliquer
(au moins une partie) des incidents `shutdown signal` observés en CI depuis
le 12/08 (#217 et suivants), jusqu'ici attribués à une « préemption infra
transitoire, indépendante » ?

**Constat — le parallèle est plausible et n'a jamais été testé** :
1. Les runners GitHub Actions hébergés standard (`ubuntu-latest`, 2 vCPU)
   ont **~7 Gio de RAM** — spec publiée et stable de longue date, le même
   ordre de grandeur que la machine locale où l'OOM a été confirmé
   (7,6 Gio). Charger la seule législature 16 (4,35 Gio mesurés) y est donc
   tout aussi risqué qu'en local.
2. Le code concerné (`fetch_amendements_officiels` →
   `_read_cached_amendement_index`) tourne à l'identique en CI, sans
   protection supplémentaire : `extract-an` est shardé par candidat (#344)
   mais un **seul** candidat suffit à charger la législature 16 en entier ;
   `extract-roster-groupes` n'est pas shardé du tout et traite plusieurs
   membres dans le même process — exposition au moins aussi importante
   qu'en local, voire supérieure une fois #376 (passage à pleine échelle)
   réalisé.
3. **Point décisif** : GitHub Actions n'expose jamais les diagnostics
   kernel (`journalctl -k`/`dmesg`) dans les logs de job. Si le runner
   hébergé se fait tuer par OOM, le seul symptôme visible côté logs serait
   `The runner has received a shutdown signal` — **exactement** la
   signature déjà chassée dans ce fichier depuis le 12/08
   ([[verification-billing-actions]], [[resilience-generate-data-shutdown-signal]]).
   La conclusion du 12/08 (« préemption infra, indépendante ») a écarté
   facturation/quota mais n'a jamais mesuré la mémoire réelle, faute
   d'accès — absence de preuve d'OOM dans les logs, pas preuve d'absence
   d'OOM.

**Nuance** : les deux incidents CI diagnostiqués précisément cette session
(runs #45/#47, voir [[resolution-an-prenom-compose-et-gel-runner-etape0]])
se sont produits à l'étape de résolution d'identité (avant la collecte
d'amendements dans `build_profile`), pas pendant `fetch_amendements_officiels`
— ce parallèle n'explique donc pas *ces* deux incidents précis. Mais
l'historique plus ancien du projet (#185/#199/#220/#225/#239/#241/#246,
classés « réseau uniquement » dans [[amendements-index-budget-ci-cache-granularite]])
n'a jamais pu être réévalué à la lumière de cette hypothèse, faute d'avoir
identifié à l'époque que la collecte d'amendements par candidat pouvait à
elle seule approcher la RAM totale d'un runner standard.

**Décision — ajout d'un diagnostic, pas de conclusion prématurée** :
plutôt que de réattribuer rétroactivement les incidents passés sans preuve,
deux steps de diagnostic ajoutés à `extract-an` et `extract-roster-groupes`
(`.github/workflows/generate-data.yml`), à évaluer sur le prochain run réel :
- `free -h` en tout début de job (avant toute charge) — confirme/infirme la
  RAM totale réellement disponible sur ce runner.
- `/usr/bin/time -v` autour de l'appel Python principal de chaque job — trace
  le pic de RSS atteint dans les logs, si le process Python se termine
  (normalement ou tué) sans que le runner entier ne disparaisse avec lui.

**Limite connue et acceptée** : si c'est bien le runner entier qui se fait
tuer par OOM (pas seulement le process Python), rien ne s'exécute après —
même angle mort déjà documenté que `if: always()` (#228). `/usr/bin/time -v`
ne capture donc que le cas où le process Python meurt seul (OOM ciblé sur lui,
ou `MemoryError` Python) sans emporter le runner — mais c'est déjà mieux que
l'absence totale de signal actuelle, et `free -h` seul confirme au moins la
RAM de départ sans dépendre de ce cas.

<a id="oom-lecture-amendements-par-candidat"></a>
## OOM persistant : lecture per-candidat de l'index amendements, tentative de mémoïsation revertée (2026-08-17)

**Contexte** : après [[oom-reconstruction-amendements-figees]] (ci-dessous),
`build_amendements_index.py` ne rechargeait plus les index déjà figés — mais
l'OOM a persisté sur un run local suivant (`extract-an` puis
`extract-roster-groupes` tués par le kernel, confirmé `journalctl -k`,
anon-rss 4,2 à 5,7 Gio). Cause différente : `fetch_amendements_officiels`
(appelée une fois par candidat) boucle sur les 4 législatures de
`AN_AMENDEMENTS_PATH` et appelle `_read_cached_amendement_index` à chaque
fois — cette fonction, elle, n'a **jamais** été protégée par la correction
précédente (qui ne touchait que `build_amendements_index.py`) : elle
recharge le fichier disque en JSON pur Python à **chaque candidat**, pas
seulement au démarrage du job.

**Tentative #1 (revertée)** : `@lru_cache(maxsize=None)` sur
`_read_cached_amendement_index`, pour ne lire chaque législature qu'une
seule fois par process. Mesuré après coup : tailles réelles sur disque des 3
index figés — `14` 1,46 Gio, `15` 2,04 Gio, `16` 4,35 Gio (`ls -la
.cache/amendements_an/*/index_par_acteur.json`), soit **7,85 Gio cumulés**
rien qu'en JSON brut sur disque (davantage une fois désérialisé en objets
Python — mesuré ~6,8 Gio de RSS rien que pour boucler sur 7 candidats
factices touchant les 4 législatures). Un cache non borné garde les 3
simultanément résidents pour le reste du run — sur une machine à 7,6 Gio de
RAM totale, c'est **pire** que le comportement d'origine (un seul index à la
fois, libéré entre deux candidats, jamais plus d'~4,35 Gio transitoire).
Confirmé par de nouveaux kills OOM survenus *après* application du fix.
**Reverté** : `_read_cached_amendement_index` reste sans mémoïsation.

**Non résolu** : le comportement d'origine (rechargement complet à chaque
candidat) reste risqué sur une machine dont la RAM est du même ordre de
grandeur que la plus grosse législature figée (16 : 4,35 Gio) — chaque appel
pour cette législature s'approche dangereusement du plafond physique, avec
ou sans mémoïsation. Le correctif réel nécessite d'éviter de matérialiser
l'index entier d'une législature pour n'en lire qu'un seul acteur (ex.
restructurer le cache disque en un fichier par acteurRef plutôt qu'un seul
gros `index_par_acteur.json` par législature) — changement de format
cascadant (écriture réseau, fallback figé, quality gate section 3d, script
CI dédié), hors périmètre d'une correction ponctuelle. Voir l'issue de suivi
associée pour le chantier complet.

**Différence CI vs local** : ce risque est spécifique à une exécution locale
« tout-en-un-process » (`scripts/generate_data_local.sh`, qui traite tous
les candidats dans le même process Python) — en CI, `extract-an` est déjà
shardé en matrix par candidat (#344), donc chaque shard ne charge chaque
législature qu'une fois avant que le runner (et sa mémoire) ne soit
recyclé ; `extract-roster-groupes`, lui, n'est pas shardé et reste exposé au
même risque une fois le volume de candidats augmenté (voir #376).

**Tests** : le test de mémoïsation ajouté puis reverté a été retiré avec le
code qu'il testait (`tests/test_candidate_profile.py`). Suite complète :
1143/1143.

<a id="oom-reconstruction-amendements-figees"></a>
## OOM lors de la relecture d'un index amendements figé déjà en cache (exécution locale) (2026-08-17)

**Contexte** : exécution locale via `scripts/generate_data_local.sh`.
Symptôme rapporté : la section 3d de `check_quality_gate.py` signale la
législature 15 comme « jamais construit », alors qu'elle est bien dans
`AN_AMENDEMENTS_LEGISLATURES_FIGEES` et que le fallback committé
(`raw_data/amendements_an_figes/15/`) est complet.

**Diagnostic** (log complet relu, `logs/generate_data_local_*.log`) : le
process `python3 src/build_amendements_index.py` s'arrête net avec
`Processus arrêté` juste après avoir commencé la législature 16 — confirmé
via `journalctl -k` comme un **OOM kill** du noyau (`Out of memory: Killed
process ... python3 ... anon-rss:6061768kB` sur une machine à 7,6 Gio de
RAM). Même symptôme un peu plus tard sur `generate_all_profiles.py`, et sur
le process VS Code lui-même (`Killed process ... (code)`) — la fermeture de
fenêtre perçue par l'utilisatrice n'était pas volontaire, c'est le kernel qui
a tué VS Code par pression mémoire.

Cause : `_download_and_build_amendement_index` (candidate_profile.py), sur
cache-hit, `json.load()` **l'intégralité** de `index_par_acteur.json` — y
compris pour une législature figée déjà validée, où ce rechargement ne sert
qu'à re-confirmer une donnée qui, par construction, ne change plus jamais.
Pour la législature 16, ce fichier pèse **4,7 Gio en clair** (forme plate
non dédupliquée — voir [[amendements-legislatures-figees]] pour le choix de
committer sous forme compressée/dédupliquée puis de l'étendre localement) :
le charger en JSON pur Python consomme largement plus que sa taille sur
disque, jusqu'à épuiser la RAM disponible. `build_amendements_index.py`
itère les 4 législatures de `AN_AMENDEMENTS_PATH` dans l'ordre `17, 16, 15,
14` : le kill sur la 16 empêche donc la 15 d'être ne serait-ce que tentée à
chaque exécution — pas un incident isolé, un blocage systématique tant que
le cache de la 16 reste présent sur cette machine.

**Décision** : nouvelle fonction `amendements_index_deja_figee(legislature)`
(candidate_profile.py) — vérifie la présence de `index_par_acteur.json` +
`fraicheur.json["figee"] is True` en ne lisant **que** `fraicheur.json`
(quelques dizaines d'octets), sans jamais toucher au gros index.
`build_amendements_index.py` l'appelle en tête de boucle et saute
entièrement une législature déjà figée en cache, au lieu de la refaire
passer par `_download_and_build_amendement_index`. Mesuré après fix : pic
mémoire de la commande complète 42 Mio (contre ~6 Gio avant, OOM).

**Non touché** : `_download_and_build_amendement_index` elle-même garde son
comportement (cache-hit = relecture complète) — c'est le seul appelant
(`build_amendements_index.py`, confirmé par grep, seul point d'entrée réseau
amendements depuis #252) qui évite maintenant de l'invoquer inutilement pour
une législature figée, plutôt que de complexifier la fonction partagée.

**Tests** : 4 nouveaux tests unitaires pour `amendements_index_deja_figee`
(matérialisé+figé → True, législature active même si le cache y ressemble →
False, non matérialisé → False, JSON invalide dans `index_par_acteur.json`
n'affecte pas le résultat car jamais lu). `test_build_amendements_index.py` :
les 5 tests existants patchent désormais aussi
`amendements_index_deja_figee` (sinon ils dépendaient silencieusement de
l'état réel du cache disque de la machine qui les exécute) + 1 nouveau test
vérifiant qu'une législature figée est sautée sans appeler la fonction
lourde. Suite complète : 1143/1143.

<a id="resolution-an-prenom-compose-et-gel-runner-etape0"></a>
## Bug de résolution AN pour les prénoms composés, et gel runner déplacé sur l'étape 0 (run #47) (2026-08-17)

**Contexte** : run `#47` de `generate-data.yml`, premier run réel après
[[mandats-officiels-an-369]] (étape 4). Résultat inattendu : les échecs
`extract-an` persistent (6/7 députés), mais plus du tout au même endroit que
le run `#45` (avant étape 4, gel systématique sur `fetch_identity`
NosDéputés — 3ᵉ domaine).

**Constat 1 — le gel runner ("shutdown signal") a suivi le point d'appel
réseau, pas disparu** : sur `#47`, 6 candidats (Attal, Retailleau, Wauquiez,
Le Pen, Philippe, Guedj) gèlent immédiatement après le print `=== Nom ===`,
**avant même le premier appel nosdeputes.fr** — donc pendant l'étape 0
(résolution AN, `fetch_identite_officielle_par_slug` /
`_ensure_acteurs_historique_zip_downloaded`), pas pendant le fallback
NosDéputés. Confirme ce que documentait déjà le commentaire au-dessus de
`_get_payload` : un vrai gel runner (assez profond pour empêcher même le
thread démon du watchdog de s'exécuter) peut frapper n'importe quel point
d'I/O réseau du job, pas spécifiquement nosdeputes.fr. Réduire l'exposition
à nosdeputes.fr (#369) a donc déplacé le point de blocage sans traiter la
cause racine — aucune régression du travail #369/#370, seulement une preuve
que ce n'était pas ce qu'on pensait résoudre.

**Constat 2 — bug réel et distinct, corrigé ici** : le seul candidat à
atteindre nosdeputes.fr sur `#47` (Jean-Luc Mélenchon) y arrive parce que sa
résolution AN échoue silencieusement. Cause : `_normalize_search_query` ne
convertit pas les tirets en espaces — `nom_complet` "Jean-Luc Mélenchon" se
normalise en `"jean-luc melenchon"` (tiret interne conservé) alors que le
slug `"jean-luc-melenchon"` remplace **tous** ses tirets par des espaces
avant normalisation, donnant `"jean luc melenchon"` — les deux clés ne
matchent jamais. Bug latent depuis #355 (jamais détecté car jamais testé en
production contre un prénom composé jusqu'à ce que l'étape 4 rende ce chemin
réellement emprunté). Corrigé dans `_build_acteur_nom_index`
(`src/candidate_profile.py`) en appliquant le même `.replace("-", " ")` que
côté slug avant normalisation — `_normalize_search_query` elle-même n'est
pas touchée (partagée avec les requêtes de recherche NosDéputés/NosSénateurs,
où le tiret a un sens différent). Vérifié en local contre un téléchargement
frais du zip AN réel : les 6 candidats se résolvent tous correctement après
le fix (`jean-luc-melenchon -> PA2150`, etc.) — confirmant au passage que
leur échec de résolution AN sur `#47` n'était PAS dû à ce bug (eux se
résolvent très bien), seulement au gel runner du Constat 1.

**Constat 3 — le cache partagé `.cache` (915 Mio en prod) ralentit l'étape 0
pour rien** : chaque shard restaure/extrait l'intégralité de
`public-data-cache-an-*` avant même de savoir s'il en a besoin (40 à 90s de
restore+`tar --use-compress-program unzstd` observés sur `#47`, sur un budget
de 5 min/shard). [[amendements-index-budget-ci-cache-granularite]] (#249)
avait mesuré que les 3 archives amendements (17/16/15) pèsent à elles seules
**≈1,22 Gio**, l'essentiel du volume — alors que l'étape 0 (résolution
identité) n'a besoin que de `.cache/acteurs_an/`. Ce spike avait déjà noté
qu'un `path` de cache séparé par sous-répertoire serait nécessaire pour
changer cette granularité mais l'avait classé hors périmètre. Piste non
implémentée ici (changement structurel sur 3 jobs — `extract-an`,
`extract-roster-groupes`, `extract-amendements-an` — qui mérite sa propre
issue/revue plutôt qu'une édition à l'aveugle) : voir issue de suivi
associée.

**Non résolu** : le gel runner lui-même (Constat 1) reste un problème
d'infrastructure CI, pas applicatif — aucun retry/watchdog ne peut s'en
protéger. Scinder le cache (Constat 3) réduirait la fenêtre d'exposition sans
l'éliminer.

**Tests** : `test_fetch_identite_officielle_par_slug_resolves_hyphenated_prenom`
(nouveau, `tests/test_candidate_profile.py`) — reproduit le bug prénom
composé et vérifie la résolution correcte après fix. Suite complète :
1130/1130.

<a id="mandats-officiels-an-369"></a>
## Mandats commission/groupe_amitie/extra_parlementaire sourcés depuis l'AN, fetch_identity NosDéputés rendu conditionnel (#369, complet), watchdog générique sur tous les téléchargements zip (#370, complet) (2026-08-17)

**Contexte** : run `#44` de `generate-data.yml` — tous les shards `extract-an`
en échec, y compris les candidats non-députés (finissaient auparavant en
15-20s). Log de Bruno Retailleau : les 8 tentatives `fetch_identity`
(NosDéputés) se terminent normalement, puis silence total (~31s, aucun
print) avant `shutdown signal`. Diagnostic : `fetch_identite_officielle_par_slug`
(#355) est appelée sans condition juste après, et déclenche
`_ensure_acteurs_historique_zip_downloaded` — un `requests.get(...,
timeout=(TIMEOUT, 600), stream=True)` en un seul essai, **non protégé** par
le pattern watchdog déjà en place sur `_get_payload` (#340/[[get-payload-retry]]).
Cache disque partagé entre shards via la même clé GitHub Actions : le
premier shard à tenter ce téléchargement (Mélenchon) ayant lui-même échoué
avant de sauvegarder le cache, chaque shard suivant repartait à froid —
effet boule de neige expliquant l'échec de tous les shards, pas seulement
certains.

**Décision 1 — `download_with_watchdog` (#370, complet)** : généralisation
de `_get_with_watchdog` aux téléchargements de fichier — thread démon +
budget mur indépendant, écriture d'abord dans un fichier temporaire (`.part`)
renommé seulement en cas de succès complet (un thread abandonné continuant
d'écrire en arrière-plan ne corrompt jamais `dest_path`). Extrait dans un
module dédié `src/download_watchdog.py` (pas laissé dans `candidate_profile.py`) :
`gouvernement_textes.py` est déjà importé par `candidate_profile.py`, un
helper partagé y vivant aurait créé une dépendance circulaire. `headers`/
`timeout` passés en paramètre plutôt que codés en dur — chaque module garde
son réglage existant (`candidate_profile.py`/`gouvernement_textes.py`/
`syceron_debates.py` : défaut 120s ; `parltrack_dumps.py`/`mep_profile.py` :
900s, dumps de plusieurs centaines de Mo, budget mur dimensionné en
conséquence via `hard_timeout_seconds` explicite plutôt que le défaut).

Appliqué aux 6 points d'appel non protégés listés dans #370 :
`_ensure_acteurs_historique_zip_downloaded` (priorité #1, cause confirmée du
run #44), boucle questions officielles AN (`candidate_profile.py`),
`ensure_dossiers_zip_downloaded` (`gouvernement_textes.py` — simplifie au
passage : l'écriture atomique manuelle qui y existait déjà devient
redondante avec celle du helper), `_download_dump` (`parltrack_dumps.py` et
`mep_profile.py`, fonctions dupliquées à l'identique dans les deux fichiers),
`_download_syceron_zip` (`syceron_debates.py`).

Effet de bord découvert en testant : `unittest.mock.patch("module.requests.get",
...)` patche l'objet module `requests` partagé (`sys.modules`), pas une copie
par fichier — patcher `candidate_profile.requests.get` intercepte donc aussi
les appels faits depuis `download_watchdog.py`. Les 54 tests existants qui
patchaient déjà `candidate_profile.requests.get` pour les téléchargements
zip AN ont continué à passer sans modification.

**Décision 2 — mandats commission/groupe_amitie/extra_parlementaire sourcés
depuis l'AN (#369, partiel)** : `_build_acteur_identite_index()` lisait déjà
`acteur.mandats.mandat[]` en entier mais n'en extrayait que le mandat
`ASSEMBLEE` (circonscription/place hémicycle) — les mandats `COMPER`/`GA`/
`ORGEXTPARL` étaient lus puis jetés, sans passer par `_build_organe_index()`/
`fetch_organe()` (#353) pourtant déjà disponible pour les résoudre en noms
lisibles. Ajout de `_build_acteur_mandats_index()` (même zip déjà téléchargé
et parsé pour l'identité/les organes, aucun coût réseau supplémentaire) et
`_extract_mandats_officiels(acteur_ref)`, équivalents AN de `_extract_mandats`
(NosDéputés). Dans `build_profile`, étape 5 : quand l'acteur est résolu côté
AN, les mandats des 3 catégories partagées viennent désormais de l'AN
(NosDéputés ne complète que le mandat électif de base et les catégories non
couvertes) — évite un doublon du même organisme sous un libellé différent.

*Mapping* : `COMPER` → `commission`, `GA` → `groupe_amitie`,
`ORGEXTPARL` → `extra_parlementaire` (`_TYPE_ORGANE_TO_CATEGORIE`). Le reste
(`MISINFO`/`CNPE`/`DELEG`/`GE`/`GEVI`/`PARPOL`/`CMP`/`API`...) n'est pas
mappé — périmètre minimal-invasif, cohérent avec ce que #349/#361 excluent
déjà de l'agrégation de groupe.

**Décision 3 — étape 4, `fetch_identity` (NosDéputés) rendu réellement
conditionnel** : la résolution AN (`fetch_identite_officielle_par_slug`) est
déplacée en tout début de `build_profile` (nouvelle étape 0, avant l'ancienne
étape 1). `fetch_identity` n'est alors appelé que si `chambre != "deputes"`
(sénateurs, non couverts par l'AN) ou si l'AN n'a pas trouvé l'acteur
(`acteur_ref_an is None`, repli complet inchangé) — pour un député trouvé côté
AN, les 8 requêtes NosDéputés (identité) sont désormais entièrement évitées.
Cela nécessitait d'abord d'étendre `_build_acteur_identite_index()` (déjà fait
en préparation) pour qu'elle porte aussi `groupe_sigle`/`groupe_nom` (mandat
`GP` courant, résolu via `_build_organe_index()`), `mandat_debut`/`mandat_fin`
(bornes du mandat `ASSEMBLEE` courant) et `nb_mandats` (nombre de mandats
`ASSEMBLEE`) — sans ces champs, sauter NosDéputés aurait fait disparaître
silencieusement le groupe parlementaire déclaré et le mandat électif de base
pour chaque député résolu côté AN. Le nom de recherche d'interventions (étape
2) retombe sur `identite_an.get("nom_complet")` quand `identity_raw` n'a pas
été récupéré. L'entrée `mandat_electif` (jusqu'ici produite uniquement par
`_extract_mandats(parlementaire)`) est reconstruite depuis `identite_an`
quand NosDéputés n'est pas appelé, avec le même format que l'original
(`categorie`/`type`/`label`/`debut`/`fin`/`actif`).

`identity_base_url` reste `None` quand NosDéputés est sauté, plutôt que de
tenter de le reconstruire depuis la législature courante : `LEGISLATURE_BY_BASE_URL`
n'a pas d'entrée pour la législature 17 (courante), et les 3 usages restants
de `identity_base_url` (dossiers pour sénateurs, `profile["source"]` cosmétique,
`fetch_votes_officiels`) retombent déjà proprement sur `base_urls[0]` — c'est
le même chemin que le repli "candidat non trouvé" déjà en usage.

#369 est donc désormais complet, comme #370.

**Tests** : `download_with_watchdog` (`tests/test_download_watchdog.py`,
nouveau — abandon après budget mur, écriture `dest_path` seulement en cas de
succès, propagation d'une erreur réseau normale sans la transformer en
`TimeoutError`), `_build_acteur_mandats_index` (mapping typeOrgane, exclusion
`MISINFO`/`ASSEMBLEE`), `_extract_mandats_officiels` (résolution de label via
`fetch_organe`, acteur inconnu → liste vide), `_build_acteur_identite_index`
(résolution groupe politique + bornes de mandat), `build_profile` (préférence
AN sur les catégories partagées, mandat électif reconstruit depuis l'AN,
`fetch_identity` non appelé quand l'AN résout l'acteur, `fetch_identity`
toujours appelé en repli quand l'AN ne trouve rien). Suite complète : 1129/1129.
<a id="mandats-agreges-famille-1"></a>
## `mandats_agreges` : agrégation catégorielle sur `mandats[]`, famille 1 (#361, sous-issue de #349) (2026-08-16)

**Contexte** : #349 (agrégats de groupe) prévoyait une famille d'agrégats
génériques sur `mandats[]` (commissions, groupes d'amitié, mandats
extra-parlementaires…). Design proposé et validé sur #349 avant
implémentation (voir historique de commentaires) : bloc dédié
`mandats_agreges` plutôt qu'une structure générique `attributs_agreges:
[{champ, type_agregation, résultat}]` — cohérent avec le style déjà en
place (`cohesion_votes`, `amendements_agreges` sont déjà des blocs nommés,
pas une structure générique unique) et plus simple à consommer côté UI. Le
caractère « générique » demandé porte sur le *mécanisme de calcul* (une
seule fonction `group_profile._aggregate_mandats` paramétrée par
`MANDATS_AGREGES_CATEGORIES`), pas sur la forme de sortie.

**Périmètre v1** : `MANDATS_AGREGES_CATEGORIES = ("commission",
"groupe_amitie", "extra_parlementaire")`. Exclus explicitement (pas
oubliés) : `mandat_electif` (définit déjà l'appartenance au groupe —
l'agréger serait circulaire), `groupe_politique` (redondant avec
`groupe_id`/`periode` dans un profil déjà scopé à un seul groupe),
`fonction_gouvernementale` (recoupe
`mandats[].suspendu_pour_fonction_gouvernementale`, AGENTS.md §5 — mérite
sa propre décision), `autre` (filet de secours quasi jamais peuplé,
`candidate_profile.py`).

**Éligibilité temporelle** : réutilise `_member_eligibility_intervals`
(intervalles de mandat électif du membre, déjà utilisés pour
`cohesion_votes`) + nouvelle `_intervals_overlap` : un mandat catégoriel
compte pour le groupe si sa période `[debut, fin]` chevauche au moins un
intervalle de mandat électif (bornes `None` non bornées). Inclusion
binaire, pas de pondération à la durée de chevauchement — cohérent avec les
comptages simples déjà utilisés ailleurs dans ce module. Membre sans mandat
électif renseigné → éligible par défaut (même approche conservatrice que
`_is_eligible_at`).

**Doublon `(categorie, label)` par membre** (ex. réélu·e à la même
commission sur deux périodes) : une seule entrée retenue par
`_select_mandat_entree_unique`, priorité à `actif=true`, sinon la plus
récente par date de fin — même esprit que le tie-break déjà documenté pour
`position_majoritaire` en cas d'égalité (`_compute_cohesion_votes`).

**`poids_relatif`** : `nb_membres / len(profils)`, où `profils` est la
couverture *disponible* (même dénominateur que `tags_thematiques_agreges`),
jamais `meta.couverture_roster.roster_total` — point soulevé en revue de
conception pour rester cohérent avec la règle éditoriale 7 (`AGENTS.md`
§2). `nb_membres_actifs` requiert à la fois le mandat actif *et*
l'appartenance au groupe active aujourd'hui (`membres[].actif`, dérivé de
`_derive_membre_entry`), pas seulement l'un des deux.

**Impact `mandats[]` plus riche à venir** (#351/#352/#353, nouvelles
catégories côté source AN officielle — missions d'information, commissions
d'enquête, délégations, groupes d'études, CMP…) : non bloquant pour cette
implémentation, le schéma `mandats_agreges` ne change pas de forme selon la
source ; `MANDATS_AGREGES_CATEGORIES` pourra être revisité séparément.

<a id="mode-extraction-leger-roster"></a>
## Mode d'extraction léger pour `extract-roster-groupes` (#357, sous-issue 6/6 de #351) (2026-08-16)

**Contexte** : une fois #355 en place (identité biographique des députés
résolue depuis l'AN, indépendante d'un appel réseau NosDéputés préalable),
un membre roster n'a quasiment plus besoin d'appeler nosdeputes.fr pour son
identité/mandats. `extract-roster-groupes` ne consomme, en aval, que
`identite`/`mandats`/`votes`/`amendements` (agrégats de groupe, #349,
`cohesion_votes`/`amendements_agreges`/`mandats_agreges`) — jamais
`dossiers_legislatifs`/`interventions`/`questions_officielles`.

**Décision** : nouveau paramètre `skip_dossiers_legislatifs` sur
`candidate_profile.build_profile()`, symétrique à `skip_interventions` déjà
existant (qui couvrait déjà interventions + questions officielles AN) — il
neutralise l'étape 3 (dossiers NosDéputés, sénateurs) et l'étape 8bis
(`fetch_textes_portes_officiels`, députés). Exposé côté CLI via
`--skip-dossiers-legislatifs` (`generate_all_profiles.py`), combiné à
`--skip-interventions` pour former le mode léger.

**Toujours actif pour ce job, pas un toggle** : contrairement à
`--skip-interventions` sur `extract-an` (piloté par l'input de workflow
`extract_interventions`, réglable par run), les deux flags sont désormais
appliqués *inconditionnellement* dans le step `extract-roster-groupes` de
`generate-data.yml` — l'énoncé de #357 demande de sauter ces champs
« entièrement », pas d'en faire une option : ils ne sont consommés par aucun
agrégat de groupe actuel ni prévu, quel que soit le run. Alternative
écartée : réutiliser `inputs.extract_interventions` pour piloter aussi
`--skip-dossiers-legislatifs` sur ce job — rejetée car elle aurait couplé un
choix de rollout `extract-an` (candidats déclarés, profils complets voulus)
à un choix structurel roster (champs jamais voulus), deux décisions
indépendantes.

**Effet de bord attendu, pas une régression** : les ~750+ profils
`roster_groupe` afficheront `nb_interventions == 0` dans la section « 3 ·
Candidats avec peu d'interventions » de `check_quality_gate.py` — déjà le
cas aujourd'hui pour la quasi-totalité d'entre eux (l'input
`extract_interventions` vaut `false` par défaut) ; ce warning reste un soft
warning (§6 `AGENTS.md`), jamais un hard fail.
<a id="retrait-fetch-activity-synthesis"></a>
## Retrait de `fetch_activity_synthesis` (#356) (2026-08-16)

**Contexte** : sous-issue 5/6 de #351, une fois `fetch_identity` basculé sur
l'AN pour l'identité (bio) (#355, [[bascule-identite-an-primaire]]).
L'énoncé demandait de réévaluer si `fetch_activity_synthesis` (endpoint
NosDéputés `/synthese/data/json`) apporte encore une donnée non couverte
ailleurs et publiable, et de le retirer purement et simplement si rien n'en
dépend — plutôt que d'investir dans sa mise en cache comme envisagé
initialement (voir la mention `fetch_activity_synthesis` dans la décision
Résilience du 2026-08-16 : ce point d'appel a hérité du `shutdown signal`
runner lors d'une vérification post-Décision 4, sans qu'un retry ciblé ne
soit retenu).

**Constat** : `synthese_activite` (nom, `groupe_sigle`, profession,
`nb_mandats`, `url_an_ou_senat`) était stocké dans le profil brut mais
**jamais lu par `normalize_nosdeputes.py`** — aucun de ces champs n'atteint
`pivot_data/`. Ce n'était donc pas une donnée publiée mise en cache
manquante, mais un appel réseau et un champ de profil brut entièrement
morts : les champs qu'il portait sont soit déjà couverts (`profession` via
`fetch_identity`, mandats/groupe via NosDéputés `identite`), soit hors
périmètre éditorial (taux de présence agrégé, règle 3, §2 d'AGENTS.md), soit
sans consommateur.

**Décision : retrait complet**, pas de mise en cache. Supprimé :
`fetch_activity_synthesis` et son appel dans `build_profile`
(`candidate_profile.py`), le champ `synthese_activite` du profil brut
(structure par défaut dans `build_profile`/`build_minimal_profile`), et sa
fusion additive dans `merge_raw_profile` (`merge_profile.py`). Aucun impact
sur le schéma pivot (`schema_pivot.py`) : ce champ n'y a jamais existé.

<a id="bascule-identite-an-primaire"></a>
## `fetch_identity` : identité (bio) des députés basculée sur l'AN comme source primaire, mandats/groupe restent sur NosDéputés (#355) (2026-08-16)

**Contexte** : sous-issue 4/6 de #351, une fois l'index identité AN étendu
(#352), les `organeRef` résolus (#353) et la couverture multi-législatures
en place (#354). L'énoncé demandait de « basculer `fetch_identity` vers la
source officielle AN, avec repli NosDéputés uniquement si un candidat reste
introuvable dans les archives AN combinées ».

**Constat qui borne le périmètre réel** : le payload NosDéputés consommé par
`fetch_identity` sert à *deux* choses distinctes dans `build_profile` : les
champs biographiques (profession, naissance, HATVP...) et les
mandats/responsabilités + groupe parlementaire déclaré
(`_extract_mandats`, `groupe_sigle`/`groupe_nom`). Cette seconde partie n'est
**pas** encore sourcée depuis l'AN : #353 a construit l'index
`organeRef -> {sigle, nom, type}` mais son rattachement aux mandats du profil
(commissions avec rôle, groupes d'amitié, engagements extra-parlementaires)
est explicitement noté « non traité ici » dans sa propre décision — futur
travail, pas dans le périmètre de cette sous-issue. Basculer *tout*
`fetch_identity` vers l'AN aurait donc silencieusement vidé `mandats[]` et
`groupe_sigle`/`groupe_nom` pour tous les députés, une régression bien plus
large que ce que l'énoncé visait.

**Décision : ne basculer que les champs biographiques.** L'identité (bio) est
désormais résolue en priorité via `fetch_identite_officielle_par_slug`,
nouvelle fonction qui résout un `acteur_ref` AN directement depuis le slug
NosDéputés par correspondance de nom normalisé (`_build_acteur_nom_index`,
réutilise la même normalisation que le fallback nom de
`fetch_activity_synthesis`) — donc sans dépendre d'un appel réseau NosDéputés
préalable pour extraire l'URL AN, contrairement à l'ancien enrichissement
« 5bis » qui ne faisait que compléter des champs après coup. NosDéputés
reste la seule source pour les mandats/groupe, et sert de repli complet
d'identité uniquement quand le candidat est absent des archives AN
combinées (`identite_an is None`).

**Effet de bord positif, cas résiduel réduit à zéro pour l'identité (bio)** :
un député qui n'a plus de fiche exploitable sur nosdeputes.fr (ex. mandat
clos d'une législature ancienne) n'obtenait auparavant *aucune* identité —
`fetch_identite_officielle` (5bis) n'était jamais appelée car nichée sous le
bloc « parlementaire NosDéputés valide ». Désormais l'identité (bio) est
renseignée même dans ce cas, avec une URL AN synthétique
(`_acteur_ref_to_pseudo_url`, même format que le champ `url_an` de
NosDéputés) qui débloque en cascade tous les autres appels officiels AN
qui n'ont besoin que d'en extraire l'`acteur_ref` (votes, amendements,
textes portés, positions hémicycle) — seuls `mandats[]`/`groupe_sigle`
restent vides dans ce cas résiduel, avec le warning `mandats introuvables`
dédié (pas `identité introuvable`, pour ne pas mélanger les deux causes dans
`merge_profile.py`, qui filtre chaque warning sur son propre champ).

**Homonymie** : `_build_acteur_nom_index` peut associer plusieurs
`acteur_ref` à un même nom normalisé (rare mais réel sur un référentiel de
3117 acteurs, XIe-XVIIe législature). `fetch_identite_officielle_par_slug`
renonce (retourne `None, None`) plutôt que de choisir arbitrairement — pas de
règle éditoriale explicite là-dessus, mais attribuer une biographie au
mauvais élu serait pire qu'un repli NosDéputés.

**Non traité ici, reste dans le périmètre de #353/futur** : rattacher
`_build_organe_index` aux mandats du profil (commissions avec rôle, groupes
d'amitié, extra-parlementaire) et au groupe parlementaire déclaré — une fois
fait, le repli NosDéputés pourrait se réduire encore, potentiellement à zéro
pour les députés couverts par le référentiel AN.

<a id="identite-acteurs-amo30"></a>
## `_build_acteur_identite_index` : couvrir les élu⋅e⋅s dont le mandat est terminé via `AMO30`, pas en combinant `AMO20` par législature (#354) (2026-08-16)

**Contexte** : sous-issue 3/6 de #351. `_build_acteur_identite_index`
utilisait `AMO10` ("deputes_actifs_mandats_actifs_organes"), limité aux
~577 député⋅e⋅s actifs de la législature en cours — aucune entrée pour un élu
dont le mandat est terminé. L'issue proposait de combiner les archives
`AMO20_dep_sen_min_tous_mandats_et_organes*`, une par législature (15/16/17
confirmées disponibles en amont, 14 non trouvée sous les noms testés).

**Décision : réutiliser `AMO30` (`AN_ACTEURS_HISTORIQUE_ZIP_URL`), déjà en
production pour #353, plutôt que combiner des archives `AMO20` par
législature.** Vérifié par téléchargement réel (13,6 Mo, 3117
`json/acteur/*.json`, contre 577 sur `AMO10`) : `AMO30` a la même structure
que `AMO10` (`etatCivil`, `profession`, `adresses`, `mandats` — vérifié champ
par champ sur des député⋅e⋅s actifs et d'anciens député⋅e⋅s de législatures
12 à 17), mais couvre déjà tous les acteurs référencés depuis la XIe
législature — un strict sur-ensemble de ce qu'aurait apporté la combinaison
`AMO20` sur 14-17, sans avoir à retrouver l'URL introuvable de la 14e ni à
gérer 3-4 téléchargements/parseurs distincts. `AMO30` est de plus déjà
téléchargé (et mis en cache disque) par `_build_organe_index`/
`_build_acteur_positions_hemicycle_index` lors de la construction d'un profil
député : `_build_acteur_identite_index` réutilise le même
`_ensure_acteurs_historique_zip_downloaded` (issue #353) — zéro
téléchargement réseau supplémentaire dans le cas courant où organes et
identité sont tous deux résolus pour le même profil, aligné avec l'objectif
de réduction des requêtes réseau redondantes posé par l'épic #351.

**Effet de bord à corriger : sélection du mandat `ASSEMBLEE` pertinent.**
`AMO10` ne contenant qu'un mandat actif par acteur, l'ancien code prenait le
premier mandat `typeOrgane == "ASSEMBLEE"` rencontré pour en tirer
circonscription/place hémicycle. Sur `AMO30`, un acteur réélu a plusieurs
mandats `ASSEMBLEE` (un par législature) : prendre le premier trouvé aurait pu
renvoyer une circonscription obsolète pour un élu actif. Nouvelle fonction
`_select_mandat_assemblee_courant` : préfère le mandat sans `dateFin` (en
cours) s'il existe, sinon celui dont `dateDebut` est le plus récent (élu dont
le mandat est terminé).

**Alternative rejetée : combiner `AMO20` par législature.** Aurait nécessité
un téléchargement/parseur par législature (3-4 archives), une logique de
fusion pour dédupliquer un même acteur présent dans plusieurs `AMO20`
(réélections), et une couverture bornée à 14-17 — contre XIe-17e pour `AMO30`
sans effort supplémentaire. Écarté une fois `AMO30` confirmé structurellement
identique et déjà intégré au pipeline.

**Non traité ici** : le branchement des champs déjà extraits mais non encore
consommés par `build_profile` (`contact`, `numero_departement`, `numero_circo`,
`place_hemicycle`, `nom_complet`) dans le schéma pivot — prérequis posé par
la sous-issue 1, exploité par la sous-issue 4 de #351.

<a id="organe-index-organeref"></a>
## `_build_organe_index` : résoudre `organeRef` via `AMO30` (historique) sans filtrage par `codeType` (#353) (2026-08-16)

**Contexte** : sous-issue 2/6 de #351. `mandats[].organes.organeRef` (ex.
`PO59048`) ne référence un organe (commission, groupe politique, groupe
d'amitié, engagement extra-parlementaire...) que par identifiant — aucun nom
lisible sans résolution. Un index partiel existait déjà
(`_build_organe_positions_index`), mais limité aux `codeType` `GP`/
`GOUVERNEMENT`, pour un besoin différent (qualification majorité/opposition/
gouvernement, voir `fetch_positions_hemicycle_officielles`).

**Décision : réutiliser le zip bulk historique (`AMO30`,
`AN_ACTEURS_HISTORIQUE_ZIP_URL`), pas `AMO10` (actifs).** Vérifié par
téléchargement réel (13,6 Mo, 10 812 `json/organe/*.json`, 33 `codeType`
distincts) : `AMO10` (mandats actifs de la législature en cours) ne couvre
qu'un sous-ensemble des organes référencés par des mandats plus anciens —
`AMO30` est nécessaire pour résoudre l'historique complet des mandats d'un
élu, pas seulement ses mandats en cours. `_build_organe_index` indexe donc
`organeRef -> {sigle, nom, type}` = `{libelleAbrege, libelle, codeType}`
sans filtrer par `codeType`, contrairement à `_build_organe_positions_index`
— voir `docs/an_opendata.md`, section "Actors / mandates / bodies", pour le
détail des champs.

**Refactor associé : téléchargement du zip mutualisé.**
`_build_acteur_positions_hemicycle_index` et `_build_organe_index` lisent
tous deux `AN_ACTEURS_HISTORIQUE_ZIP_URL`, mais construisent chacun leur
propre index mis en cache séparément (`index_positions_hemicycle.json` /
`index_organes.json`). Sans mutualisation, les deux fonctions auraient pu
télécharger le zip (~13,6 Mo) chacune de leur côté en cas d'appel concurrent
depuis des threads différents, avec un risque d'écriture concurrente sur le
même fichier zip. Extrait dans
`_ensure_acteurs_historique_zip_downloaded`, verrouillé par un verrou dédié
(`_ACTEURS_HISTORIQUE_ZIP_LOCK`), séparé du verrou de construction de
chaque index (un seul téléchargement, peu importe combien d'index en
dépendent).

**Non traité ici** : le rattachement de `_build_organe_index` aux mandats du
schéma pivot (commissions avec rôle, groupes d'amitié, engagements
extra-parlementaires, groupe politique) — prérequis posé par cette
sous-issue, exploité par les sous-issues suivantes de #351.

<a id="matrix-extract-an-par-candidat"></a>
## `extract-an` en matrix strategy par candidat, pour isoler la perte en cas de shutdown signal runner (#344) (2026-08-16)

**Contexte** : prolonge l'option 1, différée et non rejetée par
[[resilience-generate-data-shutdown-signal]] (angle mort du `runner shutdown
signal` sur `if: always()`, #228) — un seul `extract-an` séquentiel sur toute
`raw_data/candidats.json` perd la progression de *tous* les candidats déjà
traités ce run dès qu'un `shutdown signal` gèle le runner, pas seulement
celle du candidat en cours. Périmètre volontairement limité à `extract-an`
(liste éditoriale, 13 entrées / 8 à slug résolvable) ; `extract-roster-groupes`
(~750 membres) reste hors périmètre, l'urgence y étant limitée tant que
`roster_extraction_limit` reste à 20 ([[seuil-couverture-groupe]]).

**Décisions, sous-questions par sous-questions** :
1. **Granularité : un job par candidat, pas de lot.** `--only <slug>`
   (`generate_all_profiles.py`) filtre déjà nativement sur un seul candidat —
   aucun changement Python nécessaire. Un lot de 2-3 candidats n'aurait rien
   apporté ici : avec `max-parallel: 1` (décision 2), les shards s'exécutent
   déjà en série, donc le temps mur total est indépendant de la granularité
   (identique en shards de 1 ou de 3) — seule la *perte maximale par
   incident* varie, et un shard de 1 la borne au minimum possible.
2. **`max-parallel: 1`.** Le pic de jobs concurrents a été explicitement
   plafonné à 4 par #222 ([[concurrence-ci-roster]]). `extract-an` fait déjà
   partie de ce pic de 4 (concurrent à Sénat/UE/ParlTrack une fois
   `extract-amendements-an` terminé) : plusieurs shards en parallèle entre
   eux le dépasseraient mécaniquement. `max-parallel: 1` préserve l'invariant
   de #222 à l'identique, au prix du temps mur (accepté explicitement par
   l'issue #344 — "moins de jobs concurrents, plus de temps mur en échange").
   Une valeur plus élevée reste une option future si le pic de 4 est
   lui-même revisité, pas un choix isolé de ce chantier.
3. **Cache AN (`public-data-cache-an-*`) : clé partagée inchangée, pas de
   clé par shard.** La course déjà documentée en #248 sous-issue 4
   ([[amendements-index-budget-ci-cache-granularite]]) n'est pas aggravée :
   `extract-an` reste chaîné après `extract-amendements-an` (`needs:`
   inchangé), et `max-parallel: 1` fait que les shards restaurent/écrivent
   cette clé en série entre eux, pas en concurrence nouvelle.
4. **Nommage des artifacts : `raw-profiles-an-<slug>`, scopés au seul fichier
   du candidat** (`raw_data/profiles/<slug>.json`, pas tout le dossier).
   `merge-and-pivot` reste correct sans dupliquer la baseline dans chacun des
   8 shards : les jobs Sénat/UE/roster uploadent déjà, eux, l'intégralité de
   `raw_data/profiles/` (baseline committée + leur propre mise à jour), donc
   la baseline complète leur parvient toujours par ces 3 autres sources.
   `actions/download-artifact@v7` supporte `pattern: raw-profiles-an-*` +
   `merge-multiple: true` pour aplatir les N artifacts en un seul dossier —
   pas besoin d'un step par shard connu à l'avance.
5. **`needs:` de `extract-roster-groupes`/`merge-and-pivot` : inchangé
   (`needs: [..., extract-an, ...]`), pas de job de synthèse
   intermédiaire.** GitHub Actions résout nativement `needs: [extract-an]`
   comme une dépendance sur la *totalité* du matrix (tous les shards),
   pas sur une seule combinaison — un agrégateur dédié aurait été redondant.
6. **`continue-on-error: true` conservé au niveau du job (donc appliqué par
   shard automatiquement), plus `strategy.fail-fast: false` ajouté.**
   Sémantique identique une fois multiplié : l'échec d'un shard ne bloque
   jamais `merge-and-pivot`. Point de vigilance identifié en écrivant ce
   matrix et absent de la liste initiale de sous-questions : sans
   `fail-fast: false` explicite (le défaut GitHub Actions est `true`), un
   shard en échec aurait annulé tous les shards restants du matrix — ce qui
   aurait annulé l'intégralité du bénéfice d'isolation recherché par #344.
7. **Commentaire de budget mur mis à jour** en tête de `generate-data.yml` :
   timeout 20 min/shard (vs 120 min pour le job unique), 8 shards en série
   (`max-parallel: 1`) → ≈160 min pire cas pour le segment AN (vs 120 min
   avant), total mur pire cas ≈310 min (vs 270 min avant #344) — hausse de
   ~15%, cohérente avec le compromis accepté en décision 2. Formule non
   figée : dépend de `nb_candidats_a_slug`, à recalculer si
   `raw_data/candidats.json` change significativement.

**Job préparatoire ajouté : `prepare-an-matrix`.** Le matrix doit être connu
avant le démarrage du job (limite structurelle de `strategy.matrix` en
GitHub Actions), donc un job amont léger (checkout + un script Python
utilisant uniquement la bibliothèque standard, pas de `pip install`) lit
`raw_data/candidats.json` et expose en sortie (`outputs.slugs`) la liste JSON
des slugs non-null, consommée via
`fromJson(needs.prepare-an-matrix.outputs.slugs)`. Les candidats sans slug
sont exclus du matrix plutôt que de générer un shard qui n'écrirait jamais de
fichier (`--source an` sans slug ne peut interroger aucune chambre FR, et ne
déclenche jamais la recherche UE — voir `process_candidat`/`_fetch_ue` dans
`generate_all_profiles.py`) : comportement équivalent au job séquentiel
précédent, qui traitait ces candidats en no-op silencieux (`statut:
introuvable`, aucun fichier écrit).

*Coût accepté, non optimisé ici* : le step "Download artifact amendements AN
(optionnel)" (cache-only, #251/#252) s'exécute maintenant une fois par shard
au lieu d'une fois par job — léger surcoût réseau répété 8 fois plutôt qu'une,
jugé négligeable (artifact index, pas les dumps AN Open Data volumineux) au
regard du bénéfice d'isolation. *Edge case non géré explicitement* : si
`raw_data/candidats.json` ne contient plus aucun slug résolvable, le matrix
serait vide et `extract-an` ne produirait aucune exécution — scénario jugé
irréaliste en pratique (liste éditoriale activement maintenue, 8/13 slugs
résolvables aujourd'hui) et non traité pour éviter la validation
prématurée que proscrit AGENTS.md.

**Retour d'expérience sur le premier run réel, et correctif appliqué** : ce
premier run s'est terminé `cancelled` après 44m55s, sans jamais atteindre
`merge-and-pivot` (skipped). Sur 8 shards (`max-parallel: 1`, séquentiel) :
2 succès (Bruno Retailleau, Jordan Bardella — tous deux *non* rattachés à
l'Assemblée nationale, `Aucune identité trouvée`, shard fini en ~15-20s
avant toute exposition réelle), 5 échecs par la signature `shutdown signal`
habituelle (1m18s-2m10s chacun, cohérent avec tous les runs déjà observés
avant ce chantier), et 1 blocage anormal (Jérôme Guedj, 20+ min, **sans**
signature `shutdown signal` reconnaissable — logs expirés avant
investigation possible, cause non identifiée) qui a immobilisé tous les
shards suivants derrière lui (séquentiel, décision 2 ci-dessus).

Proposition initiale d'augmenter `max-parallel` (pour réduire le temps mur
et limiter l'impact d'un shard bloqué) — **écartée** sur retour d'expérience
direct de l'utilisatrice : une parallélisation antérieure d'appels vers une
même source de données s'était révélée peu robuste. Risque jugé réel : si
une partie du phénomène `shutdown signal` est liée au volume/à la charge sur
nosdeputes.fr plutôt qu'à un aléa runner pur (question non tranchée, voir le
workflow de debug ci-dessous), plus de parallélisme pourrait aggraver la
fréquence des gels plutôt que la réduire. `max-parallel` reste donc à `1`,
la décision 2 ci-dessus n'est pas remise en cause.

**Correctif retenu et implémenté à la place** : réduire `timeout-minutes`
d'`extract-an` de 20 à 5 min. Preuve à l'appui : tous les shards observés à
ce jour (succès et échecs confondus) se terminent en 1m18s-2m10s, sans
exception sauf le cas anormal de Guedj — 5 min laisse une marge large (>2x
le pire cas normal) tout en bornant à 5 min (au lieu de 20+) l'impact d'un
futur blocage du même type sur le matrix séquentiel. Budget mur en tête de
fichier recalculé en conséquence (décision 7 ci-dessus) :
`max(30+5×8, 90, 60, 30) + 60 + 60 = 190 min` pire cas (contre 310 min avec
l'ancien timeout de 20 min/shard).

**Piste de recherche ouverte en parallèle, non tranchée** : un workflow de
debug dédié (`.github/workflows/debug-network-shutdown-signal.yml`), isolé
de la production (aucun checkout de données, aucun commit, aucun artifact),
compare à volume de requêtes identique un groupe test vers nosdeputes.fr et
un groupe témoin vers `api.github.com` — objectif : déterminer si le
`shutdown signal` est corrélé au volume/temps d'activité réseau soutenue
depuis le runner (indépendamment de la destination) ou spécifique à
nosdeputes.fr. Premier run (20 requêtes/groupe, délai 0,3s) : succès complet
des deux côtés, aucun gel — attendu, le phénomène étant probabiliste ;
plusieurs runs par palier de volume restent nécessaires avant de pouvoir
conclure.

<a id="resilience-roster-decision"></a>
## Résilience de `extract-roster-groupes` : le sharding reste nécessaire (#347) (2026-08-17)

**Contexte** : #347 demandait de trancher, *avec des chiffres*, si une
stratégie de sharding restait nécessaire une fois le coût par membre réduit,
ou si `--skip-existing --resume` suffisait. Ses deux prérequis (mode léger
#357, retrait de `synthese_activite` #356) et la mesure de budget (#376) sont
livrés ; #392 a ensuite divisé le coût marginal par 2,3.

**Re-mesure après #392** (même protocole que [[budget-roster-mesure]] :
extraction légère, `--workers 1`, échantillons aléatoires) :

| | Coût marginal | Roster complet (752) |
|---|---|---|
| Avant #392 | 11,7 s | ≈ 148 min |
| **Après #392** | **5,05 s** | **≈ 63 min** |

*Correction d'une extrapolation erronée* : après #392 j'avais annoncé ~15 min
pour un run complet, en déduisant le coût résiduel de la différence
`11,7 − 10,9`. C'était faux. La lecture d'amendements mesurée isolément
(10,9 s) surestimait sa part dans un run réel, où le cache de pages du
système amortit les relectures. Seule la mesure de bout en bout fait foi :
**5,05 s/membre**, pas ~1 s.

**Décision — point 3 : oui, le sharding reste nécessaire, mais pas pour la
raison d'origine.** Deux problèmes distincts subsistent :
1. **63 min dépasse le timeout de 60 min.** 60 min couvrent ~712 des 752
   membres — un run complet ne tient pas d'un seul tenant.
2. **Une préemption fait perdre tout le job.** Vérifié : le checkpoint
   `--resume` (`raw_data/profiles/.generation_checkpoint.json`) est
   **gitignoré**, donc il ne sert qu'à l'intérieur d'un run, jamais entre
   deux ; et l'`Upload artifact` en `if: always()` ne s'exécute pas sur
   `shutdown signal` (angle mort #228). Rien n'atteint `merge-and-pivot`,
   rien n'est committé. La réponse à « `--skip-existing --resume` suffit-il ? »
   est donc **non**, et ce indépendamment du coût.

À la limite actuelle (20 membres, ~1,7 min) aucun des deux ne mord : le
sharding n'est nécessaire **que** pour le passage à l'échelle. Conception
reportée dans #394 plutôt que traitée ici, conformément au « hors périmètre »
que #347 s'était donné (pas de conception détaillée avant que le passage à
pleine échelle soit décidé, #192).

**Décision — point 4 : `roster_extraction_limit` par défaut inchangé à 20.**
Le faire passer à 0 *serait* la décision de passer à pleine échelle, qui
appartient à #192. La description de l'input porte désormais les coûts
mesurés (1,7 min à 20 · 25 min à 300 · 59 min à 700 · 63 min à 752) et
indique que le timeout actuel autorise une montée progressive jusqu'à ~700
sans rien changer d'autre — l'information nécessaire à la décision, sans la
prendre.

**Commentaire de budget mur** mis à jour avec les deux jeux de mesures
(avant/après #392) et ce que le timeout couvre réellement.

<a id="index-amendements-sharde-par-acteur"></a>
## Index amendements shardé par acteur (#392) (2026-08-17)

**Contexte** : la mesure de [[budget-roster-mesure]] (#376) a montré que **93 %
du coût d'extraction d'un membre du roster** (10,9 s sur 11,7 s) était la
relecture des index amendements — 673 Mo de JSON reparsés à **chaque**
candidat par `fetch_amendements_officiels`, soit ~500 Go sur un run complet,
payés même pour les candidats sans aucun amendement.

**Décision** : le cache runtime passe d'un `index_par_acteur.json` unique par
législature à un **répertoire d'une tranche par acteurRef**
(`index_par_acteur/PA1567.json`). Lire un candidat ne coûte plus que sa
tranche (~285 Ko) au lieu de l'index entier.

**Le store `amendements.json` est mémoïsé** — et cette fois c'est sûr, ce que
les mesures tranchent :

| Ce qui reste résident | RSS |
|---|---|
| Les 4 `index_par_acteur` complets (tentative #377, revertée) | **3,84 Go** |
| Les 4 `amendements.json` seuls (retenu) | **426 Mo** |

Le store est petit parce qu'il est dédupliqué (89 Mo sur disque, ~178 000
amendements uniques) ; c'est `index_par_acteur` qui pesait (580 Mo), et il
n'est plus jamais chargé en entier. La mémoïsation revertée en
[[oom-lecture-amendements-par-candidat]] échouait précisément parce qu'elle
gardait la mauvaise moitié.

**Résultat mesuré** : **0,17 s par candidat** pour 3 législatures, contre
~8,2 s auparavant — **gain ×49**, RSS 347 Mo. Le coût par membre du roster
passe donc de ~11,7 s à ~1 s, ce qui ramène la projection d'un run complet
(752 membres) de ~148 min à ~15 min, largement dans le timeout de 60 min.

**Équivalence fonctionnelle vérifiée** contre la source figée committée
(vérité terrain, indépendante du cache) : `_expand_aggregated_amendements_index`
appliquée aux `.json.gz` committés, comparée entrée par entrée à la lecture
shardée — **0 écart sur 360 acteurs** (120 par législature).

*Piège évité au passage* : ma première comparaison opposait les références
brutes lues au nombre d'amendements du profil committé, et affichait des
écarts partout. C'était un artefact — le profil est dédupliqué par
`merge_profile._amendement_key` sur `(numero, texte_vise, date)`, la lecture
ne l'est pas. La bonne vérité terrain est la source figée, pas le profil.

**Migration** : le répertoire de tranches est exigé en lecture ; un cache
hérité (fichier unique de #377, ou forme plate d'avant) est indiscernable
d'un cache absent et donc reconstruit. L'écriture supprime l'ancien fichier
plat et reconstruit le répertoire **de zéro** — une tranche d'acteur disparu
d'une reconstruction ne doit pas survivre.

**Sécurité** : le nom de tranche dérivant de l'acteurRef, tout identifiant
hors forme `PA<chiffres>` est refusé plutôt qu'assaini — un acteurRef
malformé ne peut jamais désigner un chemin hors du cache.

**Effet de bord sur `_download_and_build_amendement_index`** : sur cache-hit,
la liste des acteurs indexés se déduit désormais des **noms** de tranches
sans en ouvrir aucune. Son unique consommateur (`build_amendements_index.py`)
n'en fait que `len()` ; matérialiser les valeurs coûterait des centaines de
Mo pour une information dont personne ne se sert.

**Tests** : lecture limitée à la tranche demandée (vérifié en corrompant la
tranche d'un *autre* acteur — un parcours de l'index complet échouerait),
refus des acteurRef hors forme, suppression de l'index plat hérité,
reconstruction complète du répertoire, plus la mise à jour des fixtures
existantes et du quality gate §3d (qui doit rendre le même verdict que le
lecteur réel). Suite complète : 1179/1179.

<a id="budget-roster-mesure"></a>
## Budget CI de `extract-roster-groupes` : mesure réelle (#376) (2026-08-17)

**Contexte** : le `timeout-minutes: 60` de ce job était marqué « provisoire »
depuis sa création, sans aucune mesure de débit — contrairement aux
amendements, qui avaient eu leur spike dédié
([[amendements-index-budget-ci-cache-granularite]]).

**Protocole** : extraction légère telle que la CI l'exécute
(`--skip-interventions --skip-dossiers-legislatifs`, `--workers 1`), deux
échantillons **aléatoires** du roster (`--sample`, pas `--limit` : les 20
premiers déterministes auraient pu biaiser par l'ordre du fichier source).
Volontairement **sans** `--skip-existing` : on mesure le coût de traitement
réel d'un membre, c'est-à-dire le cas d'un run à pleine échelle où presque
tout est à collecter.

| Échantillon | Temps | RSS max |
|---|---|---|
| N=8 | 137,9 s | 1,54 Go |
| N=16 | 231,7 s | 1,48 Go |

**Modèle** : `T(N) ≈ 44 s + 11,7 s × N` (44 s de coût fixe, 11,7 s par membre).

**Projections** : roster complet (752 membres) ≈ **148 min** ; restant à
collecter (688) ≈ 135 min. Le timeout de 60 min couvre
`(3600 − 44) / 11,7 ≈ **300 membres**`, soit 15× la valeur par défaut de
`roster_extraction_limit` (20, qui coûte ~5 min).

**Décision — timeout inchangé à 60 min**, mais le commentaire passe de
« provisoire » à *mesuré*, avec ce que la valeur couvre réellement. L'inflater
pour faire tenir un run complet aurait entériné le gaspillage décrit
ci-dessous au lieu de le corriger.

**Le vrai blocage n'est pas le timeout** : **93 % du coût par membre est la
relecture de l'index amendements** (10,9 s sur 11,7 s). `fetch_amendements_officiels`
relit 673 Mo de JSON à *chaque* candidat, soit ~500 Go de parsing sur un run
complet — et ce coût est payé même pour les candidats sans aucun amendement
(48 profils sur 90 en ont). Suivi dans #392, prérequis technique du passage à
pleine échelle.

**Point 4 de l'issue — `--skip-existing --resume` suffit-il à borner la perte
en cas d'échec ?** Non, et c'est vérifiable : le fichier de point de
sauvegarde (`raw_data/profiles/.generation_checkpoint.json`) est **gitignoré**,
donc `--resume` ne sert qu'à l'intérieur d'un même run, jamais entre deux.
Entre runs, la seule progression préservée est celle des profils effectivement
committés par `merge-and-pivot`. Or si le job roster est préempté, son
`Upload artifact` en `if: always()` ne s'exécute pas ([[resilience-generate-data-shutdown-signal]],
angle mort #228) : rien n'atteint `merge-and-pivot`, rien n'est committé, et
**toute la progression du run est perdue**. À 20 membres (~5 min) c'est
indolore ; à 300 (~60 min) beaucoup moins. Le sharding (#347) garde donc sa
justification — mais elle tient à la **résilience**, pas au coût CPU, que
#392 traite séparément.

**Point 5 — recalibrage de `--groupe-min-coverage-pct`** : impossible à ce
stade, et pour la même raison qu'en 2026-08-12 ([[seuil-couverture-groupe]]) —
il faudrait des taux de couverture issus d'un run à pleine échelle, qui reste
bloqué par #392. Non traité plutôt que fixé dans le vide.

**Limite de cette mesure, assumée** : réalisée en local, pas sur un runner
GitHub hébergé — chemin réseau différent. Elle reste représentative sur le
poste dominant (la relecture d'index est CPU/disque, pas réseau), mais les
appels réseau résiduels (~0,8 s/membre) pourraient différer en CI. Même
réserve que celle déjà consignée pour le spike amendements.

<a id="ne-jamais-committer-un-build-perime"></a>
## Ne jamais committer un build produit avec du code périmé (#390) (2026-08-17)

**Contexte** : run `#266`. `merge-and-pivot` fait `actions/checkout` sans
`ref`, donc sur le SHA de `main` figé au **déclenchement** du run — alors que
le job ne démarre qu'après les 5 jobs d'extraction, ~18 min plus tard. La PR
#381 (correctif #379) a été mergée dans cette fenêtre. Le job a donc
régénéré `pivot_data/groupes/*.json` avec l'**ancien** `src/group_profile.py`
et tenté de le committer. Seul un conflit de rebase a empêché d'écraser le
correctif.

**Le conflit était une chance, pas le problème.** Le cas dangereux est
l'inverse : quand git parvient à merger proprement, la donnée périmée est
publiée **en silence**.

**Arbitrage (utilisatrice)** : ne rien committer, et relancer sur le `main` à
jour. L'asymétrie le justifie — ne rien committer coûte un run et toute la
donnée dérivée est régénérable ; committer un build périmé publie une erreur.
Refuser de committer est donc le **défaut**, pas le cas d'échec.

**Option écartée — `ref: main` au checkout** (ma recommandation initiale) :
elle réduirait la fenêtre, mais le job dériverait avec du code neuf à partir
d'artifacts extraits avec du code ancien — un état mixte, plus cohérent
qu'aujourd'hui mais toujours pas cohérent. La relance sur un `main` à jour
rend cette option **inutile** : tous les jobs du nouveau run partagent alors
le même SHA, ce qui est correct par construction plutôt que « moins faux ».
Un seul mécanisme au lieu de deux.

*Autres options écartées* : rebase + régénération in situ (correcte mais
nettement plus complexe à câbler ; gardée en réserve, et elle éviterait de
jeter l'extraction — la partie coûteuse et fragile — si la fréquence des
abandons le justifiait) ; discipline de branche (non outillable) ; toute
résolution « la version du run gagne » (`-X theirs`, force-push), qui aurait
ici réintroduit sciemment le bug #379.

**Implémentation** :
- Step `Vérifier que le code de génération n'a pas changé pendant le run`,
  placé **juste avant** le commit — position choisie pour couvrir toute la
  fenêtre (déclenchement → commit) ; une vérification en début de job n'en
  couvrirait qu'une partie tout en donnant une fausse assurance.
- Condition volontairement **étroite** : `src/` uniquement. Un commit de doc
  ou de données ne déclenche rien — c'est le cas que la boucle de retry du
  push sait traiter depuis [[retry-push-merge-and-pivot-bash-e]] (#389).
- Marqueur `GENERATION_CODE_CHANGED_DURING_RUN` émis en `::error::`, détecté
  par `retry-generate-data.yml` comme **second motif de relance**, distinct de
  la signature de préemption runner — sinon le résumé attribuerait à tort une
  préemption. Le plafond d'une seule tentative automatique préexistant
  s'applique identiquement, ce qui borne le risque de boucle si `main` bouge
  encore pendant la relance.

**Vérifié sur dépôts git réels** (remote bare + clones), en exécutant le step
tel quel :
- *Commit concurrent sur `docs/` seulement* → `✓ src/ inchangé — commit sûr`,
  exit 0. Aucun faux positif : c'est le cas nominal que le retry doit
  absorber, pas abandonner.
- *PR touchant `src/` mergée pendant le run* (scénario exact du run #266) →
  fichiers modifiés listés, marqueur émis, exit 1, résumé explicite écrit
  dans `$GITHUB_STEP_SUMMARY`.

**Non résolu, assumé** : une relance jette le travail d'extraction déjà fait
(~20 min, et c'est la partie exposée aux `IncompleteRead`). Acceptable tant
que la condition d'abandon reste étroite ; à reconsidérer via l'option
« rebase + régénération » si la fréquence réelle des abandons le justifie —
donnée à mesurer, pas à supposer.

<a id="retry-push-merge-and-pivot-bash-e"></a>
## La boucle de retry du push ne rebouclait jamais (`bash -e`) (#389) (2026-08-17)

**Contexte** : run `#266`. Toutes les étapes de données de `merge-and-pivot`
ont réussi ; seul le push final a échoué, et le log ne montrait qu'une
« tentative 1/3 » là où le step en promet 3.

**Cause** : le workflow ne déclare aucun `defaults: shell`, donc GitHub
Actions exécute chaque `run:` avec `bash -e {0}`. Le `git rebase` en conflit
retournant un code non nul, le shell terminait immédiatement le step — les
tentatives 2 et 3 n'existaient que sur le papier, et le
`::error::Échec après 3 tentatives` en fin de boucle n'était **jamais**
atteint. Le diagnostic affiché en cas d'échec réel était donc trompeur, ce
qui a longtemps masqué le défaut : le retry paraissait fonctionner puisque
personne ne voyait de message contredisant.

Effet secondaire : le step se terminait avec le dépôt du runner **en rebase
inachevé** (`.git/rebase-merge/` présent, index en conflit).

**Correctif** : `set +e` sur la seule portée de la boucle (restauré ensuite),
et sortie immédiate sur conflit — un conflit de rebase ne se résout jamais en
rebouclant, les deux côtés ayant réécrit les mêmes fichiers générés. Ajout
d'un `git rebase --abort` avant de sortir, pour laisser le dépôt propre. Le
message final distingue désormais les deux causes : conflit de rebase (cas du
run #266, cause traitée séparément dans #390) vs. rejet persistant après 3
rebases réussis (concurrence soutenue) — la première ne se traite pas par un
retry, la seconde si.

**Vérifié sur dépôts git réels**, en exécutant le step sous `bash -e` comme
le fait GitHub Actions :
- *Ancien code, conflit* : une seule « tentative 1/3 », aucun message
  d'erreur final, `.git/rebase-merge/` laissé en place — défaut reproduit à
  l'identique.
- *Nouveau code, conflit* : message explicite désignant la bonne cause, exit
  1, dépôt propre.
- *Nouveau code, commit concurrent sur un fichier disjoint* (le cas que le
  retry vise depuis le run #29) : « tentative 2/3 », **push réussi**, les deux
  commits préservés sur le remote. Ce scénario ne fonctionnait pas non plus
  avant le correctif.

**Périmètre** : uniquement la mécanique de retry. La raison pour laquelle un
conflit survient — le job régénère des fichiers générés depuis un SHA figé et
écrase le travail d'une PR mergée entre-temps — reste ouverte dans #390.
Corriger la boucle seule ne rend pas le run #266 vert : elle transforme un
échec confus en échec explicite.

<a id="purge-mandats-dupliques-prudence"></a>
## Purge des mandats hérités dupliqués : appariement prudent (#387) (2026-08-17)

**Contexte** : après [[taxonomie-mandats-typeorgane-an]] (#384), l'AN fournit
les mandats correctement catégorisés, mais les entrées héritées de l'ère
NosDéputés subsistent — la fusion additive ne remplace jamais. Le même organe
apparaît deux fois, dont une sous une étiquette fausse.

**Arbitrage retenu (utilisatrice) : prudence.** Un faux négatif laisse un
doublon visible — bénin ; un faux positif supprime un mandat réel —
irréversible hors git.

**Règle implémentée** (`src/purge_mandats_dupliques.py`) — une entrée n'est
retirée que si les 4 conditions sont réunies :
1. catégorie couverte par le référentiel AN ;
2. elle n'est pas elle-même une entrée AN ;
3. son libellé normalisé correspond à celui d'une entrée AN **présente dans
   le profil** ;
4. sa période **recouvre** celle de cette entrée.

**Deux obstacles mesurés, qui ont façonné la règle** :

*Nommage divergent* — l'AN nomme l'organe par son seul thème
(« Trufficulture »), NosDéputés préfixe la nature (« Groupe d'études
trufficulture »). Aucun appariement exact ne rapproche les doublons : d'où la
normalisation par retrait de préfixe (`_PREFIXES_NATURE`, liste établie **par
mesure** sur les profils réels — un préfixe non listé produit une
non-correspondance, donc une conservation, jamais une suppression à tort).

*Datation divergente* — les deux référentiels ne datent jamais un même mandat
identiquement (écart de quelques jours à plusieurs semaines). Un appariement
par date exacte ne rapprocherait rien ; mais un même organe héberge aussi des
périodes réellement distinctes (entrée/sortie/remplacement). D'où le test de
**recouvrement**, ni exact ni absent.

**Défaut détecté à la mise au point, et corrigé** : la première version
comparait à l'extraction AN *fraîche* au lieu des entrées AN *présentes dans
le profil*. Sur un profil pas encore régénéré, cela retirait l'entrée héritée
sans que son équivalent soit là — **18 organes distincts perdus sur
`benjamin-haddad`, 16 sur `pascale-boyer`**, détecté par une vérification
indépendante comptant les organes distincts avant/après. La correction rend
le script sans effet tant que le profil n'est pas régénéré, ce qui *est* la
garantie « ne jamais retirer avant que l'équivalent soit présent » posée par
#387. Écart entre les deux versions : 599 suppressions sur 43 profils
(fautive) contre **193 sur 23** (correcte).

**Garde-fous** : `--dry-run` par défaut (`--apply` requis pour écrire) ;
profil sans acteurRef ignoré ; extraction AN vide ignorée (indiscernable d'un
échec transitoire, résilience #241) ; idempotent (vérifié : 0 suppression au
second passage).

**Résultat** : 193 doublons retirés sur 23 profils, **0 organe distinct
perdu** (vérifié par comptage indépendant), `gabriel-attal` passe de 10
doublons commission/groupe_etudes à 0.

**Tests** : 15 tests dédiés — normalisation (retrait de préfixe, casse/accents,
et garde-fou vérifiant qu'elle ne rapproche PAS deux organes distincts),
recouvrement de périodes (nominal, disjoint, bornes ouvertes jamais
substituées par aujourd'hui), et la règle complète (doublon avéré retiré,
période distincte conservée, entrée sans équivalent conservée, entrée AN
jamais retirée, catégories hors périmètre ignorées, idempotence, extraction
vide sans effet, et le cas du défaut ci-dessus). Suite complète : 1175/1175.

<a id="taxonomie-mandats-typeorgane-an"></a>
## Taxonomie des mandats : exploitation des `typeOrgane` AN non mappés (#382, option « mixte ») (2026-08-17)

**Contexte** : #369 avait mappé 3 `typeOrgane` sur ~25 (« périmètre
minimal-invasif »). Mesuré sur 65 profils résolus AN, cela laissait
**3 150 mandats inexploités contre 3 273 exploités** — presque la moitié du
référentiel. Ces mandats existaient malgré tout dans les profils, mais
uniquement parce que la fusion additive préservait des entrées héritées de
l'ère NosDéputés, où `_extract_mandats` les mappait **toutes** en dur vers
`commission` : d'où le symptôme de #379 (197 libellés sur 246 classés
« Commission » sans en être).

**Décision — option « mixte » (arbitrée par l'utilisatrice)** : une catégorie
par nature institutionnelle réellement distincte pour le lecteur, pas une par
`typeOrgane`. Ajouts à `schema_pivot.KNOWN_CATEGORIES` :

| Catégorie ajoutée | `typeOrgane` regroupés | Mandats |
|---|---|---|
| `groupe_etudes` | `GE`, `GEVI` | 1185 |
| `commission_enquete` | `CNPE`, `CNPS` | 371 |
| `mission_information` | `MISINFO`, `MISINFOCOM`, `MISINFOPRE` | 348 |
| `delegation` | `DELEG`, `DELEGBUREAU`, `API`, `OFFPAR` | 143 |

Rangés dans l'existant : `COMNL` → `commission` (97) ; `BUREAU`/`CONFPT` →
`autre` (35, deux organes seulement — ne justifient pas une catégorie).

**`MINISTERE` → `fonction_gouvernementale` (79 mandats, 52 intitulés)** :
apporte le **portefeuille ministériel précis** (« Ministère de la cohésion
des territoires », « Secrétariat d'État auprès du ministre de… »), en
complément — non en remplacement — du rattachement au gouvernement produit
par `fetch_positions_hemicycle_officielles` (« Gouvernement (BORNE) »). Ceci
**lève la limitation documentée en [[hors-perimetre]]**, dont l'affirmation
« no open-data source for the precise portfolio has been identified yet »
est désormais factuellement dépassée — la section a été corrigée en
conséquence.

**Exclusions, explicites et justifiées** (`_TYPE_ORGANE_NON_MAPPES`, déclarées
en dur plutôt qu'omises — le silence de #369 sur ces types avait rendu son
propre périmètre difficile à rediscuter) :
- `ASSEMBLEE` : c'est le mandat électif, produit ailleurs.
- `GP`, `GOUVERNEMENT` : **doublons** — déjà collectés par
  `fetch_positions_hemicycle_officielles`.
- `CMP` (616) : organe temporaire créé par texte de loi, une entrée par
  texte — les agréger noierait les instances permanentes sous des centaines
  d'entrées à membre unique.
- `PARPOL` (222) : recoupe le champ `parti` du pivot et `groupe_politique` ;
  mêler appartenance partisane et mandat institutionnel demande son propre
  arbitrage, hors #382.
- Types Sénat (`DELEGSENAT`/`COMSENAT`/`GROUPESENAT`/`SENAT`, 4 mandats) et
  `CJR` (1) : volume négligeable.

**Agrégation de groupe** (`MANDATS_AGREGES_CATEGORIES`) : les 4 nouvelles
catégories sont agrégées — ce sont des instances de travail collectives,
exactement ce que l'agrégat cherche à montrer. Restent exclus
`mandat_electif`/`groupe_politique` (structurels, identiques pour tous les
membres), `fonction_gouvernementale` (individuelle par nature) et `autre`
(fourre-tout sans unité éditoriale, AGENTS.md §2.8).

**UI** : `MANDAT_CATEGORY_LABELS` complété, et **tri par rang de catégorie**
introduit dans `pivotAdapter.js` — à 7 catégories, le tri par `nb_membres`
seul noyait les commissions permanentes sous les groupes d'études, bien plus
nombreux.

**Effet mesuré** : `pascale-boyer` passe de 33 à **82 mandats AN exploités**
(groupe_etudes 29, commission 16, groupe_amitie 16, mission_information 13,
commission_enquete 5, extra_parlementaire 2, delegation 1). Sur les candidats
déclarés : Attal 111 → 134, Édouard Philippe 23 → 31, Le Pen 11 → 16.

**Non traité — migration des entrées héritées (#387)** : les anciennes
entrées NosDéputés mal catégorisées coexistent désormais avec leurs
équivalents AN. Mesuré sur `gabriel-attal` : **10 doublons**, le même organe
apparaissant en `commission` (libellé NosDéputés « Groupe d'études
trufficulture ») et en `groupe_etudes` (libellé AN « Trufficulture »). Les
deux référentiels ne nomment pas les organes de la même façon — l'AN omet le
préfixe de nature — donc aucun appariement exact ne les rapproche. Purge
laissée à #387, qui requiert un arbitrage sur la stratégie d'appariement et
sa tolérance au risque (un faux positif supprime un mandat réel).

**Tests** : chaque `typeOrgane` mappé produit sa catégorie ; les exclusions
ne produisent rien (pas même un fourre-tout) ; garde-fou de cohérence
vérifiant qu'aucun type n'est à la fois mappé et exclu, et que toute
catégorie produite appartient à `KNOWN_CATEGORIES` (sinon `validate_profil`
rejetterait les profils générés). Suite complète : 1160/1160.

<a id="normalisation-fonction-mandats-agreges"></a>
## Normalisation de `par_fonction` dans `mandats_agreges`, et requalification du défaut « catégorie commission » (#379) (2026-08-17)

**Défaut 1 — casse de `fonction` (corrigé)** : depuis [[mandats-officiels-an-369]],
les mandats proviennent de deux référentiels aux conventions typographiques
différentes — NosDéputés écrit `"membre"`, l'Assemblée nationale `"Membre"`.
`_aggregate_mandats` comptait sur la valeur brute : le même rôle était éclaté
en deux entrées (`'membre': 521` **et** `'Membre': 312`), donnant à lire deux
rôles distincts là où il n'y en a qu'un — trompeur au sens de la règle de
traçabilité (AGENTS.md §2).

*Décision* : `_normalize_fonction_mandat` normalise casse et espaces
surnuméraires, **sans** toucher au genre ni aux accents. `président` et
`présidente` (comme `co-rapporteur`/`co-rapporteure`) sont des libellés
institutionnels réellement distincts : les fusionner effacerait une
information portée par la source. Une fonction absente reste `non_precise`,
distincte de « simple membre » (§2.5, donnée manquante ≠ valeur par défaut).
*Mesuré après régénération* : `membre` unifié à 833, **0 collision de casse**
restante, variantes genrées préservées.

**Défaut 2 — catégorie `commission` trop large : requalifié, pas un défaut du
pipeline actuel.** Le constat initial (197 libellés sur 246 classés
`commission` n'en sont pas : « Comité de massif des Alpes », « Bureau de
l'Assemblée nationale »…) est exact, mais l'investigation a infirmé la cause
supposée :

1. *Le mapping AN est fidèle.* Vérifié sur `pascale-boyer` : ses 15 mandats
   AN mappés `commission` ont tous `typeOrgane == "COMPER"` et un libellé
   commençant bien par « Commission ». Aucun faux positif issu de
   `_TYPE_ORGANE_TO_CATEGORIE`.
2. *L'hypothèse « ça vient des profils non résolus AN » est fausse aussi* :
   les plus gros contributeurs sont tous résolus AN. Et le seul profil
   réellement jamais résolu AN du jeu (`bruno-retailleau`, sénateur) affiche
   0 suspect.
3. *Cause réelle : données périmées conservées par la fusion additive.* Les
   profils bruts portent `synchro nosdeputes` au 14/08 — antérieur à l'étape
   4 de #369, quand `_extract_mandats` mappait encore en dur toutes les
   `responsabilites` NosDéputés vers `commission`. Preuve décisive :
   `pascale-boyer` régénérée avec `--no-merge` donne **15 commissions,
   0 suspect**, contre 38/26 avec fusion.

*Conséquence* : aucune décision éditoriale sur la taxonomie n'est requise —
le pipeline produit déjà la bonne catégorisation. Ce qui reste est une
question d'hygiène de données (purger les entrées héritées), avec une
tension réelle : un `--no-merge` global purgerait aussi des données
légitimement préservées par la fusion additive (ex. les amendements de la
législature 17 conservés d'un run à l'autre, mécanisme de résilience #241).
Laissé ouvert dans #379 plutôt que tranché ici.

**Tests** : normalisation de casse, préservation des variantes genrées,
`non_precise` pour une fonction absente ou vide — les deux premiers vérifiés
comme discriminants (ils échouent si l'on retire la normalisation). Suite
complète : 1158/1158.

<a id="freshness-timestamps-groupes-gouvernements-partis"></a>
## Extension de la stabilité des horodatages aux profils groupe/gouvernement/parti (#343, complet) (2026-08-17)

**Contexte** : [[pivot-freshness-timestamps-stables]] (ci-dessous) corrigeait
le motif pour les seuls pivots candidats, en notant que
`group_profile.py`/`gouvernement_profile.py`/`parti_profile.py` étaient
« probablement » affectés du même défaut, mais sans repro confirmé — donc
laissé en ROADMAP plutôt que corrigé à l'aveugle.

**Repro obtenu** : deux exécutions successives de
`generate_gouvernement_profiles.py` sans aucune modification des données
sources donnent un contenu strictement identique (hors `meta`) mais un
`meta.genere_le` qui avance (`17:36:23` → `18:13:05`). Le motif était donc
bien présent, et sur les trois familles de documents.

**Décision** : réutiliser `preserve_stable_freshness_timestamps` telle quelle
plutôt que d'écrire une variante par script — les quatre types de documents
partagent exactement la même forme de fraîcheur (`meta.genere_le` +
`sources[].synchro_le`), vérifié sur les fichiers réellement produits.
Appliquée au point d'écriture de chacun : `group_profile.generate_groupe_profile_from_roster`,
`generate_gouvernement_profiles.generate_all`, `parti_profile` (boucle
d'écriture). Helper partagé `load_existing_document` ajouté dans
`merge_profile.py` pour relire le document précédent (illisible = traité
comme absent : la seule conséquence est un re-tamponnage, jamais une perte —
le document régénéré est écrit dans tous les cas).

**Correctif nécessaire à la généralisation — appariement des sources** :
la fonction indexait les anciennes sources par `type` seul. Ça suffisait pour
un pivot candidat (quelques sources, chacune d'un type distinct), mais pas
ici : un profil de groupe porte une source PAR MEMBRE, donc plusieurs
dizaines d'entrées de même `type` (mesuré : 63 sources pour 3 types distincts
sur `groupe-AN-REN-16`). Une clé sur le seul `type` les aurait toutes
écrasées sur la dernière, attribuant à chaque membre l'horodatage d'un autre.
Clé passée à `(type, url)`. L'appariement reste exact par construction :
`url` fait partie de l'empreinte comparée, donc si les empreintes sont
égales, les couples `(type, url)` le sont aussi.

**Mesure** : re-génération des trois familles à données inchangées —
**0 fichier modifié sur 27** (7 groupes + 10 partis + 10 gouvernements),
contre 27 avant le correctif. Vérifié aussi octet-pour-octet sur
`gouvernement-BAYROU.json`.

**Effet attendu au-delà de la traçabilité** : les commits automatiques du
pipeline ne porteront plus de diff sur ces 27 fichiers quand rien n'a changé,
ce qui rend enfin lisible la question « qu'est-ce qui a réellement bougé ce
run ? » — motif observé en pratique (123 fichiers modifiés pour zéro
changement de contenu, cf. l'entrée ci-dessous).

**Tests** : appariement `(type, url)` sur un document à sources multiples de
même type (test vérifié comme discriminant : il échoue si l'on revient à une
clé sur `type` seul), et `load_existing_document` (absent, corrompu, JSON
non-objet, cas nominal). Suite complète : 1155/1155.

<a id="pivot-freshness-timestamps-stables"></a>
## `genere_le`/`synchro_le` des pivots ne doivent avancer que si le contenu change réellement (#343) (2026-08-16)

**Contexte** : en creusant les conséquences de l'angle mort `if: always()`
documenté ci-dessous ([[resilience-generate-data-shutdown-signal]]), constat
sur un run réel (`extract-an`/`extract-roster-groupes` en échec, aucune
donnée AN fraîche disponible) qu'un commit a quand même été poussé avec 123
fichiers modifiés — diff réel vérifié sur
`pivot_data/profiles/jean-luc-melenchon.pivot.json` : **zéro changement de
contenu**, seuls `meta.genere_le` et `sources[].synchro_le` avaient avancé.
Cause : `--pivot-only` (`generate_all_profiles.py`) re-dérive systématiquement
le pivot depuis le profil brut déjà présent sur disque (aucun appel réseau),
mais `schema_pivot.make_empty_profil` tamponne `meta.genere_le =
time.strftime(...)` inconditionnellement à chaque appel, et
`normalize_europarl`/`normalize_nosdeputes` retombent sur `time.strftime(...)`
dès que le profil brut source ne porte pas lui-même un horodatage exploitable
— sans jamais comparer au pivot déjà commité. Contraire à la règle de
traçabilité (AGENTS.md §2 règle 2) : ces champs sont censés refléter quand la
donnée a été *effectivement* collectée, pas la dernière exécution du script.

**Décision** : `merge_profile.preserve_stable_freshness_timestamps(old_pivot,
new_pivot)` compare une empreinte JSON du pivot en ignorant précisément
`meta.genere_le` et `sources[].synchro_le` (`_pivot_content_fingerprint`) ;
si le contenu est identique à l'ancien pivot committé, les anciens
horodatages sont restaurés sur `new_pivot` avant écriture (comparaison
`sources[]` par `type`, pas par index, pour rester robuste à un réordonnancement).
Appelée juste avant l'écriture disque dans les deux chemins de
`generate_all_profiles.py` qui écrivent un pivot (`--pivot-only` et
`--pivot` normal, après un éventuel `merge_pivot_profile`) — le mode normal
peut produire le même symptôme si un run réseau ne rapporte aucune donnée
nouvelle.

**Périmètre** : uniquement les pivots candidats (`pivot_data/profiles/`). Le
même motif (`meta.genere_le` re-tamponné inconditionnellement à chaque
régénération, `schema_groupe.py`/`schema_gouvernement.py`/`schema_parti.py`)
est probable pour `group_profile.py`/`gouvernement_profile.py`/
`parti_profile.py`, qui reconstruisent leur sortie sans jamais comparer à
l'ancienne version — pas de repro confirmé pour ces pivots, laissé en
`ROADMAP.md` plutôt que corrigé à l'aveugle ici.

<a id="resilience-generate-data-shutdown-signal"></a>
## Résilience de `generate-data.yml` face aux `shutdown signal` runner : continue-on-error généralisé, watchdog réseau, retry générique sur `_get_payload`, retry `retry-generate-data.yml` non-régressif, et appels NosDéputés morts pour les députés (dossiers, votes) (2026-08-16)

**Contexte** : investigation déclenchée par des échecs répétés d'`extract-an`
et `extract-roster-groupes`, tous avec la même signature `shutdown signal`
déjà documentée ([[retry-generate-data-preemption]], #217/#221/#228) —
observée systématiquement juste après le print `-> Dossiers législatifs :
...` (`fetch_dossiers`, `candidate_profile.py`), sur des candidats et
législatures différents d'un run à l'autre.

**Décision 1 — `continue-on-error: true` sur `extract-an`/`extract-senat`/
`extract-ue-officiel`** : avant ce changement, ces 3 jobs n'avaient pas
`continue-on-error`, contrairement à `extract-parltrack`/
`extract-amendements-an`/`extract-roster-groupes`. Un échec de l'un des 3
faisait donc sauter `extract-roster-groupes` **et** `merge-and-pivot` en
entier (`needs:` bloquant), alors que la fusion additive de
`merge_profile.py::merge_raw_dirs` gère déjà nativement un répertoire source
absent. Étendu le même pattern aux 3 jobs restants, et rendu les
téléchargements d'artifacts AN/Sénat/UE dans `merge-and-pivot` optionnels
(`continue-on-error: true`) pour le même motif (un job ayant échoué avant son
étape `Upload artifact` peut laisser l'artifact totalement absent, pas
seulement vide). Résultat vérifié sur un run réel : `extract-an` et
`extract-roster-groupes` en échec, `merge-and-pivot` a quand même tourné et
réussi.

**Décision 2 — watchdog mur (`_get_with_watchdog`,
`candidate_profile.py`)** : `_get_payload` (chokepoint de `fetch_identity`/
`fetch_votes`/`fetch_dossiers`/`fetch_activity_synthesis`) n'utilisait que
`timeout=` de `requests`, qui ne couvre pas la résolution DNS
(`getaddrinfo`) sur toutes les plateformes. Ajout d'un timeout mur
indépendant : la requête tourne dans un thread démon, abandonné après
`TIMEOUT + 10s` quoi qu'il arrive. **Vérifié insuffisant en pratique** : un
run réel a rejoué exactement la même signature `shutdown signal` après ce
correctif (commit confirmé via `headSha` du run), le blocage se produisant
apparemment au niveau du runner entier (aucun thread, pas même celui du
watchdog, n'a pu s'exécuter pour lever l'exception) — cohérent avec une
préemption infra GitHub, pas un bug applicatif. Le watchdog reste une
amélioration défensive légitime (protège contre un DNS/connect réellement
bloqué en cas normal), mais n'était pas la cause du symptôme observé.

**Décision 3 — fix de `retry-generate-data.yml` (reconstruction des
inputs)** : avec le logging de debug activé sur ce dépôt, le log brut d'un
step contenant plusieurs `${{ }}` contient aussi le texte du template GitHub
Actions non résolu (ex. littéralement `--workers {3}`, émis par
`##[debug]Evaluating format(...)`) en plus de la ligne `Run ...` réellement
résolue. `grep -oP -- '--workers \K\S+' | head -1` capturait ce placeholder
au lieu de la vraie valeur — régression constatée sur un run réel :
`workers="{3}"` transmis tel quel au `workflow_dispatch` de relance, faisant
planter `extract-senat`/`extract-ue-officiel` avec `invalid int value:
'{3}'`. Fix : ancrage des motifs sur la ligne de commande finale et
restriction aux caractères attendus (`[0-9]+`, `true|false`) — la valeur
placeholder ne matche alors plus du tout, peu importe sa position dans le
log. Découvert au passage : la détection d'`extract_interventions` était
structurellement toujours fausse (`grep -q -- '--skip-interventions'`
matchait le texte source du script, toujours présent que la condition soit
vraie ou non) ; corrigé en lisant directement la valeur substituée dans la
condition `[[ "<valeur>" != "true" ]]`. Chaque extraction est aussi passée en
`|| true` : sous `set -e`/`pipefail`, un motif non trouvé faisait avant
avorter tout le step (donc perdre les valeurs suivantes, correctement
extractibles) plutôt que de ne dégrader que la valeur en cause vers son
défaut.

<a id="dossiers-legislatifs-nosdeputes-vs-an-officiel"></a>
**Décision 4 — suppression de l'appel NosDéputés pour les dossiers
législatifs des députés** : en creusant pourquoi `fetch_dossiers` (étape 3 de
`build_profile`) était justement le point qui pendait dans tous les runs
observés, découverte que pour `chambre == "deputes"`, son résultat
(`dossiers_payload`, étape 8) est de toute façon **écrasé** juste après par
l'étape 8bis (`fetch_textes_portes_officiels`, source officielle AN via
`ensure_dossiers_zip_downloaded`/`gouvernement_textes.py`, déjà en place et
donnant un résultat propre à chaque élu — voir le commentaire déjà présent
avant ce jour à l'étape 8bis : « Remplace la liste NosDéputés [...], qui
n'est pas propre à l'élu »). L'appel réseau à `nosdeputes.fr/.../dossiers/
nom/json` pour les députés ne servait donc plus à rien depuis que 8bis existe
— juste un risque de blocage gratuit. Décision : ne plus appeler
`fetch_dossiers_for_legislatures` du tout quand `chambre == "deputes"`
(`candidate_profile.py`, étape 3), sans ajouter de retry ni de bascule vers
un téléchargement direct du zip AN pour ce cas — le zip AN est déjà consommé
par 8bis, un deuxième chemin d'accès au même jeu de données officiel aurait
été redondant. Pour `chambre == "senateurs"`, l'appel est conservé
inchangé : aucun remplacement officiel n'est branché pour cette chambre
(l'archive NosSénateurs reste la seule source), donc la question d'un retry
dédié y reste ouverte et distincte — non traitée ici, ce chantier n'ayant mis
en évidence aucun blocage côté sénateurs dans les runs examinés.

**Vérification post-Décision 4** : un run réel avec ce correctif déployé
(`headSha` confirmé) a de nouveau échoué avec la même signature `shutdown
signal` — mais cette fois bloqué sur l'appel suivant dans la séquence
(`-> Synthèse d'activité : .../synthese/data/json`, `fetch_activity_synthesis`,
aucun remplaçant officiel branché pour ce point), pas sur les dossiers.
Confirme ce qu'on avait déjà déduit du watchdog (Décision 2) : le blocage
n'est pas propre à une URL précise, c'est un gel du runner GitHub lui-même à
peu près au même moment dans le job (~1-2 min), quel que soit l'appel réseau
en cours à cet instant — retirer un appel donné ne fait donc que déplacer le
point de blocage, pas disparaître le symptôme. Seul `continue-on-error`
(Décision 1) protège réellement le run dans son ensemble contre ce mode de
défaillance ; les Décisions 4/5 (ce chantier et le suivant) restent
justifiées pour leur propre mérite (suppression d'appels réseau prouvés
morts/inutiles), pas comme correctif du `shutdown signal`.

**Décision 5 — même traitement pour les votes NosDéputés des députés** :
`fetch_votes_officiels` (AN, déjà préféré à l'étape 6) documente déjà dans
son propre docstring que « l'endpoint /votes de NosDéputés.fr est en panne
(HTTP 500 systématique, testé sur tous les domaines et législatures
disponibles) ». Constat confirmé empiriquement dans tous les logs de ce
chantier : `fetch_votes` (étape 1, jusqu'à 8 requêtes — 4 domaines × 2
formats) échoue systématiquement en HTTP 500 ou format non pris en charge,
pour les députés. Conséquence : `votes_raw` y est *garanti* vide, rendant la
branche de repli « `else`: utiliser `votes_raw` » (étape 6) strictement
inatteignable pour cette chambre — plus net encore que pour les dossiers
(pas de simple écrasement après coup, mais une branche de code déjà morte en
pratique). Décision : ne plus appeler `fetch_votes` du tout quand `chambre
== "deputes"` (`candidate_profile.py`, étape 1), même limite que la Décision
4 (aucun effet sur le `shutdown signal` lui-même — voir vérification
ci-dessus). Message de warning (`WARNING_PREFIX_VOTES_INTROUVABLES`) ajusté
en conséquence pour ne plus mentionner une « erreur serveur » qui, pour les
députés, ne se produit plus puisque l'appel n'est plus fait. Pour
`chambre == "senateurs"`, l'appel est conservé inchangé — aucune preuve
équivalente que l'archive NosSénateurs soit cassée, et c'est la seule source
de votes pour cette chambre.

<a id="get-payload-retry"></a>
**Décision 6 — retry léger généralisé dans `_get_payload`** : suite à la
vérification post-Décision 4 ci-dessus (le point de blocage se déplace d'un
appel à l'autre — après le retrait de `fetch_dossiers_for_legislatures`,
`fetch_activity_synthesis` a hérité du `shutdown signal` sur un run réel),
question posée de retenter spécifiquement `fetch_activity_synthesis`.
Écartée : ce point n'est pas la cause, seulement le prochain appel en vol au
moment du gel — un retry câblé sur cette seule fonction n'aurait fait que
redéplacer le symptôme vers l'appel suivant (interventions), et n'aide de
toute façon pas contre un vrai gel du runner (Décision 2 : même un thread de
watchdog totalement indépendant n'arrive pas à s'exécuter dans ce cas).
Généralisé à la place : 3 tentatives max avec backoff fixe 1,5s, ajoutées
directement dans `_get_payload` (le chokepoint déjà partagé par identité/
votes/synthèse/dossiers-Sénat, entre autres). Un seul point d'ajout plutôt
qu'un retry dupliqué par fonction appelante — couvre aussi la demande de
retry Sénat de l'issue #340 (dossiers/votes) sans changement supplémentaire.
Ne retente que les échecs transitoires (5xx, `requests.RequestException`, y
compris le `Timeout` levé par le watchdog) — jamais `_TERMINAL_FAILURE`
(4xx, format non exploitable, JSON malformé), qui reste un échec déterministe
à usage unique. **Effet de bord sur les tests** : plusieurs tests
`build_profile(...)` ne mockaient pas `fetch_activity_synthesis`/
`fetch_all_intervention_results_from_domains`, s'appuyant sur un appel réseau
réel qui échouait vite en sandbox — le retry l'a fait échouer 3× plus
lentement (un test est passé de <1s à 22s). Corrigé en ajoutant les mocks
manquants plutôt qu'en réduisant le retry : plus correct de toute façon (un
test unitaire ne devrait pas dépendre d'un comportement réseau réel, retry ou
pas).

**Décision 7 — deux incohérences relevées par relecture indépendante** (mêmes
fichiers, mêmes commits que ce chantier, non détectées avant relecture) :
1. Le fallback GHA `-f extract_interventions="${{ ... || 'true' }}"`
   (`retry-generate-data.yml`, step *« Re-déclencher generate-data.yml »*)
   divergeait du vrai défaut `workflow_dispatch` déclaré dans
   `generate-data.yml` (`default: false`) — contrairement aux 5 autres
   fallbacks de ce step (`fresh_run||'false'`, `threshold||'3'`,
   `workers||'1'`, `max_pages||'5'`, `roster_extraction_limit||'20'`), tous
   correctement alignés. La justification d'origine de #336
   ([[retry-generate-data-best-effort-non-bloquant]] ci-dessous — « valeur
   initiale du script best-effort avant détection de --skip-interventions »)
   est elle-même devenue caduque : la Décision 3 de ce jour a réécrit cette
   logique bash pour qu'elle retombe correctement sur `false`, donc même le
   script best-effort ne justifie plus le `'true'` du fallback GHA. Corrigé
   en `|| 'false'`.
2. Le commentaire de budget en tête de `generate-data.yml` (« Total mur
   (parallèle) ≈ 120 + 60 = 180 min ») ne comptait que `max(AN, Sénat, UE)`
   + `merge-and-pivot`, sans `extract-roster-groupes` — qui n'est *pas*
   parallèle aux 4 jobs d'extraction (`needs:` sur les 4, #222,
   [[concurrence-ci-roster]]) ni `extract-an` à `extract-amendements-an`
   (`needs:` direct). Chemin critique réel : `max(30+120, 90, 60, 30)` (phase
   parallèle, dominée par la chaîne amendements-an→AN) `+ 60` (roster,
   séquencé après) `+ 60` (merge-and-pivot, séquencé après roster) `= 270
   min`, pas 180. Commentaire manifestement écrit avant l'ajout du
   séquencement roster (#222) et jamais mis à jour depuis. Corrigé avec le
   détail des chaînes de dépendance, pour éviter qu'un futur ajout de job
   laisse à nouveau ce commentaire dériver silencieusement.

<a id="retry-generate-data-best-effort-non-bloquant"></a>
## `retry-generate-data.yml` : le step best-effort d'extraction des inputs ne doit pas pouvoir bloquer le retry (#336) (2026-08-16)

**Contexte** : [[retry-generate-data-preemption]] (#230) déclenche le retry
réel (step *« Re-déclencher generate-data.yml »*) uniquement via `if:
steps.signature.outputs.matched == 'true'`, sans `always()` — GitHub Actions
y ajoute donc implicitement `success()`. Sur les runs #35/#36 (2026-08-15T22:55:56Z
et 2026-08-16T05:26:00Z), la signature de préemption runner est correctement
détectée (`matched=true`) mais le step intermédiaire *« Reconstituer les
inputs du run échoué (best-effort) »* échoue en ~1,5s sans sortie visible
dans les logs — cohérent avec un échec précoce d'un appel `gh api`,
probablement un rate-limit transitoire déclenché par l'enchaînement de
plusieurs téléchargements complets de logs de jobs entre le step de détection
et ce step (jusqu'à 3-4 en l'espace d'une seconde). Ce step est documenté
comme *best-effort* (dégradation vers les valeurs par défaut, cf. commentaire
existant), mais deux défauts en faisaient un point de blocage réel : (1)
`jobs_json=$(gh api ".../jobs" --paginate)` n'avait aucune garde sous `set
-euo pipefail`, contrairement aux appels de `job_log()` (`2>/dev/null ||
true`) — un seul hoquet API faisait échouer tout le step ; (2) le step
suivant héritait de `success()` sur ce step best-effort, donc son échec
skippait le retry réel lui-même, alors même que la signature de préemption
avait été identifiée avec certitude. Résultat : deux runs consécutifs sans
aucun retry automatique tenté, le filet de sécurité de #230 étant
silencieusement inopérant sur ce mode de défaillance précis.

**Décision** :
1. `jobs_json=$(gh api ".../jobs" --paginate)` du step best-effort est
   désormais gardé avec le même pattern que le step de détection (`if ! cmd;
   then ::warning:: + repli; fi`) — un hoquet API dégrade vers une liste de
   jobs vide (`jobs_json='{"jobs": []}'`) au lieu de faire échouer tout le
   step ; `job_log()` traite déjà correctement une liste vide (id introuvable
   → chaîne vide).
2. Le step *« Re-déclencher generate-data.yml »* passe à `if: always() &&
   steps.signature.outputs.matched == 'true'` — découplé du succès du step
   best-effort. Les inputs passés à `gh workflow run` utilisent désormais le
   fallback d'expression GHA `${{ steps.inputs.outputs.X || 'défaut' }}` (pas
   seulement les `${var:-default}` bash internes au step best-effort, qui ne
   s'appliquent que si ce step atteint effectivement ses lignes `echo ... >>
   "$GITHUB_OUTPUT"`) — mêmes valeurs que les défauts déclarés dans
   `generate-data.yml` (`fresh_run=false`, `threshold=3`, `workers=1`,
   `extract_interventions=true` — valeur initiale du script best-effort avant
   détection de `--skip-interventions`, pas le défaut `workflow_dispatch` de
   `generate-data.yml` lui-même qui est `false` —, `max_pages=5`,
   `roster_extraction_limit=20`), pour rester sûr même si le step best-effort
   n'a écrit aucun de ses outputs.

**Note d'implémentation** : modification d'un fichier existant sous
`.github/workflows/*`, poussée directement sans intervention manuelle —
cohérent avec #237 (voir [[retry-generate-data-detection-impossible]]), qui
avait déjà établi que seule la *création* d'un nouveau fichier sous ce
répertoire se heurte à la restriction de permissions GitHub App.

*Alternative rejetée* : ne garder que le fix n°2 (découplage de la
condition) sans garder le fix n°1 (garde sur `gh api`) — rejeté car un step
best-effort qui continue d'échouer bruyamment (`Process completed with exit
code 1`, job `detect-and-retry` en `failure`) reste un signal trompeur dans
l'historique des runs même si le retry finit par partir ; les deux corrections
sont complémentaires, pas substituables. *Hors périmètre de #336* :
réduction des téléchargements de logs redondants entre le step de détection
et le step best-effort (piste évoquée dans #336 pour réduire le risque de
rate-limit en amont) — non traitée ici, voir `ROADMAP.md`.

<a id="audit-plages-temporelles"></a>
## Épic #316 — tableaux croisés des plages temporelles (#317/#318/#320/#321) : bilan et décisions transverses (2026-08-15)

**Contexte** : #316 fait suite à #174 (« Amélioration de la pipeline audit »,
clos), qui avait ajouté le tableau croisé des **volumes** par candidat
(`compute_tableau_croise_candidats`). Ce tableau répond à « combien
d'éléments ? » mais pas à « sur quelle période ? » — un profil avec 800
votes peut couvrir 2007-2025 ou seulement les 6 derniers mois sans que le
rapport ne le distingue. Distinct de la fraîcheur déjà auditée
(`sources[].synchro_le`, quand la donnée a été *collectée*) : la plage
temporelle porte sur la date des *faits* eux-mêmes (`votes[].date`,
`membres[].debut/fin`, etc.), pas sur leur date de collecte. #316 a décliné
ce besoin en 6 sous-issues sur les trois types de profil (candidat, groupe,
gouvernement) ; cette entrée clôt l'épic et documente les décisions
transverses qui ne rentraient dans le périmètre fichiers d'aucune
sous-issue individuelle.

**Pourquoi une plage temporelle en plus du volume** : un tableau de volume
seul ne distingue pas un profil réellement complet (couverture longue) d'un
profil récemment initialisé mais déjà actif (couverture courte, volume
comparable après quelques mois) — seule la comparaison min/max face à la
période institutionnelle attendue (législature, mandat) permet ce diagnostic
en un coup d'œil. Implémenté en parité sur les trois types de profil plutôt
que sur le seul candidat (déjà couvert par le tableau de volumes historique),
pour que l'audit gouvernement — jusqu'ici totalement absent — ne devienne pas
le seul angle mort restant.

**Pourquoi `amendements_agreges` (groupe) n'a pas de colonne plage
temporelle** : `schema_groupe.py` n'agrège que des compteurs sous
`amendements_agreges` (`nb_amendements`, `nb_adoptes`, `nb_rejetes`,
`nb_irrecevables`, `nb_retires_ou_tombes`, `taux_adoption`,
`par_type_deposant`) — aucun champ date n'existe au niveau de ce bloc
agrégé. `compute_plage_dates_groupes` retourne donc `null` pour cette
cellule, documenté dans le rapport Markdown comme limite structurelle du
schéma actuel (voir [[plage-dates-groupes]]), pas une donnée manquante que
ce chantier aurait dû corriger — ajouter cette date impliquerait un
changement de schéma (`schema_groupe.py`), explicitement mis hors périmètre
par #316 dès sa rédaction.

**Pourquoi `audit_gouvernement_dataset.py` a été construit avec parité
complète plutôt qu'un script minimal** : avant #316, aucun audit
n'existait pour `pivot_data/gouvernements/` — `check_quality_gate.py`
(#212) valide la structure des profils de gouvernement, mais sans rapport
de qualité dédié équivalent à `audit_pivot_dataset.py`/`audit_groupe_dataset.py`.
Un script minimal ne portant que `compute_plage_dates_gouvernements` aurait
répondu à la lettre du tableau croisé demandé, mais aurait laissé
`audit_gouvernement_dataset.py` structurellement asymétrique par rapport aux
deux scripts jumeaux — notamment sans agrégation de `meta.warnings[]`
(nécessaire à `audit_pipeline.py::compute_vue_ensemble` pour agréger les
warnings des trois types de profil, voir [[audit-pipeline-gouvernement]]) ni
volumétrie/complétude/cohérence/fraîcheur comparables. Décision prise lors
de la préparation de l'épic (actée dans le corps de #316 avant même la
sous-issue #319) : construire `audit_gouvernement_dataset.py` sur le même
modèle complet que `audit_groupe_dataset.py` dès #319/#320 (sous-issues 3
et 4/6), pour que la vue d'ensemble compilée par `audit_pipeline.py` (#321)
traite les trois types de profil de façon strictement symétrique — jamais
une vue d'ensemble à 0 gouvernement audité par construction.

**Hors périmètre, noté pour la trace long-terme** :
- `interventions[].date_reponse` (délai de réponse aux questions
  parlementaires officielles) reste hors du tableau des plages temporelles
  de `audit_pivot_dataset.py`, qui se limite au champ `date` de chaque
  entrée (`compute_plage_dates_candidats`/`_plage_dates_champ_simple`) —
  déjà acté dans le corps de #316 (« Hors périmètre »), repris ici pour ne
  pas se perdre au fil des sous-issues individuelles. Un futur besoin
  éditorial sur le délai de réponse serait un chantier séparé.
- Toute alerte/warning basée sur un seuil de plage temporelle (ex. « profil
  ne couvre pas la législature en cours ») : cette épic ajoute l'indicateur
  brut (min/max), jamais de logique de détection d'anomalie dessus. Ajouté
  à `ROADMAP.md`.
- Ajout d'un champ date à `amendements_agreges` (`schema_groupe.py`) pour
  combler le gap noté ci-dessus — changement de schéma, hors périmètre.
  Ajouté à `ROADMAP.md`.
- `check_quality_gate.py` (gate bloquant en CI) : cette épic ne touche que
  l'outil d'audit manuel (`audit_pipeline.py`), jamais appelé par la CI.

<a id="audit-pipeline-gouvernement"></a>
## `audit_pipeline.py` : intégration du rapport gouvernement (#321, sous-issue 5/6 de #316) (2026-08-15)

**Contexte** : `audit_pipeline.py` compilait jusqu'ici uniquement les audits
profils (`audit_pivot_dataset.py`) et groupes (`audit_groupe_dataset.py`,
#178). #321 étend la vue d'ensemble compilée à `audit_gouvernement_dataset.py`
(#319/#320), au même niveau de parité que les deux audits existants :
`compute_vue_ensemble`/`build_report` prennent désormais trois rapports en
entrée (`total_gouvernements_audites`, `erreurs_lecture.gouvernements`,
`warnings.par_type[...].gouvernement_ids`), un nouveau flag CLI
`--gouvernements-dir` (défaut `pivot_data/gouvernements`, même comportement
que `--profiles-dir`/`--groupes-dir` sur dossier absent : erreur explicite +
code de sortie 1, jamais de traceback), et une troisième section Markdown
compilée.

**Écart comblé — agrégation des warnings gouvernement** : contrairement à
`audit_pivot_dataset.py` et `audit_groupe_dataset.py`, `audit_gouvernement_dataset.py`
(#319/#320) n'avait jamais implémenté de `compute_agregation_warnings` sur
`meta.warnings[]` — l'epic #316 ne le listait pas explicitement dans
l'architecture cible de ces deux sous-issues, alors même que
`gouvernement_profile.py`/`gouvernement_textes.py` peuplent réellement ce
champ (ex. `gouvernement_profile` : dossier exclu de `textes[]`,
`gouvernement_textes` : statut/chambre de dépôt non déterminable). #321
demandait explicitement un compteur "warnings" gouvernement dans la vue
d'ensemble, ce qui n'était possible qu'en comblant ce trou plutôt qu'en le
contournant silencieusement (une vue d'ensemble à 0 warning gouvernement
aurait été trompeuse — vérifié sur les 10 gouvernements réels de
`raw_data/gouvernements_reels.json` : 518 warnings, types `gouvernement_profile`
et `gouvernement_textes`). Ajouté à `audit_gouvernement_dataset.py`
(`compute_agregation_warnings`, section `warnings` de `build_report`, section
Markdown `## Warnings`), en dehors de la liste "Fichiers concernés" de
l'issue mais strictement au même contrat que la fonction jumelle de
`audit_groupe_dataset.py` (`{"total_warnings": int, "par_type": {type:
{"frequence": int, "gouvernement_ids": [...]}}}`).

**Alternative rejetée** : dégrader silencieusement `compute_vue_ensemble` en
traitant l'absence de section `warnings` côté gouvernement comme "toujours
0" (`.get("warnings", {"total_warnings": 0, "par_type": {}})`), pour rester
strictement dans le périmètre fichiers de #321. Écartée : la donnée
`meta.warnings` existe réellement dans `pivot_data/gouvernements/*.json`
(vérifié en conditions réelles ci-dessus), donc masquer ce warning aurait
contredit le critère d'acceptation "Vue d'ensemble agrégée mise à jour avec
les compteurs gouvernement" et laissé un vrai signal de qualité invisible.

Pure composition inchangée côté `audit_pipeline.py` (AGENTS.md §2.1 : aucune
nouvelle logique de calcul métier n'y est introduite) ; le calcul réel des
warnings gouvernement vit dans `audit_gouvernement_dataset.py`, comme pour
les deux autres audits.

<a id="plage-dates-groupes"></a>
## Tableau croisé des plages temporelles par groupe (#318, sous-issue 2/6 de #316) (2026-08-15)

**Contexte** : `audit_groupe_dataset.py` avait un tableau croisé des
*volumes* par groupe (`compute_tableau_croise_groupes`, #174) mais rien
sur la *période* couverte. #316 demande le symétrique pour les trois
types de profil (candidat, groupe, gouvernement) ; cette sous-issue
traite le groupe.

**Décision — format `dates_invalides`** : la sous-issue 1 (candidats,
`audit_pivot_dataset.py`) n'existait pas encore au moment de ce chantier,
donc pas de convention à réutiliser telle quelle. Retenu pour
`compute_plage_dates_groupes` : chaque ligne porte une cellule
`{"min":..., "max":...} | null` pour `cohesion_votes` (calculée sur les
dates valides uniquement, jamais une date par défaut — AGENTS.md §2.5),
et une liste séparée `dates_invalides` (`{groupe_id, champ, valeur}`)
recense chaque date ignorée pour traçabilité, plutôt qu'un simple
compteur global. Les sous-issues 1 et 4 (candidat, gouvernement)
devraient suivre la même forme pour rester cohérentes entre les trois
audits.

**Décision — `amendements_agreges` toujours `null`** : `schema_groupe.py`
n'agrège aucune date au niveau du bloc `amendements_agreges` (seulement
des compteurs). Cellule `null`, documentée explicitement dans le rapport
Markdown (« N/A (non applicable) » + note) comme limite structurelle du
schéma actuel — pas une donnée manquante à corriger dans ce chantier
(ajouter une date à `amendements_agreges` est listé dans le Hors périmètre
de #316).

<a id="pages-statiques-methodologie-mentions-legales"></a>
## Pages Méthodologie et Mentions légales dans web/UI_finale (#289, plan #140) (2026-08-14)

**Contexte** : sous-issue 2/3 du plan #140, portant `web/old/v3/methodologie.html`
et `mentions-legales.html` dans `web/UI_finale`. Bloquée par #288 pour le
contenu Mentions légales — voir [[licences]] pour le texte validé, repris
tel quel.

**Décision — composant partagé** : `src/components/StaticPage.jsx` + `.css`
factorise bannière + sections pour les deux pages (`MethodologyPage.jsx`,
`LegalNoticePage.jsx`), avec des classes entièrement préfixées
(`static-*`) plutôt que de réutiliser les classes `.main`/`.banner` de
`CandidateProfile.css` — ce fichier ne définit ses classes qu'une fois
(`GroupProfile.jsx`/`GovernmentProfile.jsx` préfixent déjà en `gp-`/`gov-`
pour la même raison) ; s'appuyer dessus par coïncidence de bundle CSS
global aurait couplé silencieusement une page statique à l'implémentation
d'un composant candidat.

**Décision — routes hors `ExplorerLayout`** : l'issue laissait le choix
ouvert entre bandeaux visibles ou page seule. Retenu : `/methodologie` et
`/mentions-legales` sont déclarées en dehors de la route `ExplorerLayout`
dans `App.jsx`, sans les bandeaux Groupes/Gouvernements/Candidats — ces
pages n'ont pas de candidat/groupe sélectionné, et `GroupsBar`/`CandidatesBar`
n'ont de sens que dans ce contexte. *Alternative rejetée* : les nicher sous
`ExplorerLayout` pour réutiliser `Brand` déjà monté — `StaticPage` importe
directement `Brand`, le gain de réutilisation ne justifiait pas d'exposer
des bandeaux de sélection inertes sur une page sans profil.

**Contenu Méthodologie corrigé vs v3** : la section "Ordre des catégories"
de `web/old/v3/methodologie.html` décrit un clic sur les KPI
Majorité/Opposition/Non distingué qui filtre la liste détaillée, avec un
bouton "Réinitialiser". Vérifié dans `CandidateProfile.jsx` et
`src/data/pivotAdapter.js` (`buildCandidateView`, `scopeBuckets`) : ce
comportement n'existe plus — la répartition Majorité/Opposition/Non
distingué s'affiche aujourd'hui comme un graphique de comparaison en
barres (`compare-rows`), non cliquable, uniquement dans l'onglet "Textes"
du profil candidat (`GroupProfile.jsx` n'a pas d'équivalent). Le texte
repris dans `MethodologyPage.jsx` décrit ce comportement actuel plutôt que
celui de v3.

**Hors périmètre** (comme précisé par l'issue) : aucun lien de navigation
vers ces pages depuis le reste de l'app (sous-issue 3/3).

<a id="licences"></a>
## Audit des sources de données et de leurs licences, pour les Mentions légales (#288) (2026-08-14)

**Contexte** : sous-issue 1/3 du plan #140. L'ancien `web/old/v3/mentions-legales.html`
ne couvre que NosDéputés/NosSénateurs, Parltrack et Wikipédia, alors que le pipeline
actuel interroge aussi l'Open Data de l'Assemblée nationale, l'Open Data du Parlement
européen et Wikidata. Audit exhaustif via `grep -rn https:// src/*.py` (tous les
domaines listés en AGENTS.md §7), puis vérification en direct de chaque page de
licence officielle (accessible dans le sandbox réseau de cet agent pour tous les
domaines listés, sauf `data.europarl.europa.eu`, portail Angular non rendu par un
simple `curl`, et `www.wikidata.org`, hors liste des hôtes autorisés — `query.wikidata.org`
seul y figure).

**Constat par domaine** :

| Domaine(s) | Donnée réutilisée | Licence | Texte officiel | Attribution requise |
|---|---|---|---|---|
| `www.nosdeputes.fr`, `2007-2012\|2012-2017\|2017-2022.nosdeputes.fr`, `archive.nossenateurs.fr` | Mandats, votes, amendements, fiches parlementaires (législatures 13 à 17) | **ODbL v1.0** | https://opendatacommons.org/licenses/odbl/1-0/ (référencée par https://www.nosdeputes.fr/a-propos : « les données sous licence ODbL ») | Oui — « NosDéputés.fr (ou NosSénateurs.fr) par Regards Citoyens à partir de l'Assemblée nationale (ou du Sénat) et du Journal Officiel » |
| `data.assemblee-nationale.fr`, `questions.assemblee-nationale.fr`, `www.assemblee-nationale.fr`, `schemas.assemblee-nationale.fr` | Scrutins, amendements, dossiers législatifs, questions écrites, débats Syceron | **Licence Ouverte / Open Licence (Etalab)** | https://data.assemblee-nationale.fr/licence-ouverte-open-licence (PDF/RTF téléchargeables sur cette page — la page ne précise pas explicitement 1.0 vs 2.0 ; utiliser le PDF de l'AN comme texte de référence plutôt que de présumer une version) | Oui, mention de la paternité obligatoire — **pas** de partage à l'identique |
| `parltrack.org` (dumps JSON) | Dossiers législatifs, votes, activités des député·es européen·nes | **ODbL v1.0** | https://opendatacommons.org/licenses/odbl/1-0/, référencée en direct par https://parltrack.org/ (section Copyright : « data … ODBLv1.0 ») | Oui — partage à l'identique si republication d'un jeu de données dérivé |
| `data.europarl.europa.eu`, `www.europarl.europa.eu` | Fiches et photos des député·es européen·nes (API v2 + pages MEP) | Politique de réutilisation du **Legal Notice** du Parlement européen (reproduction/adaptation/diffusion commerciale ou non commerciale autorisée si l'élément est reproduit intégralement et la source indiquée) | https://www.europarl.europa.eu/legal-notice/fr/ (confirmée en direct) | Oui — « © Union européenne, [année] – Source : Parlement européen » |
| `fr.wikipedia.org` | Statut de candidature déclarée (pas de citation de texte actuellement) | **CC BY-SA 4.0** | https://creativecommons.org/licenses/by-sa/4.0/ (confirmée en direct via le pied de page Wikipédia) | Oui, + partage à l'identique si citation de texte |
| `query.wikidata.org` | Identifiants/métadonnées structurées liées aux candidatures | **CC0 1.0** | https://creativecommons.org/publicdomain/zero/1.0/ (politique de licence Wikidata bien établie — non re-vérifiée en direct dans ce sandbox, `www.wikidata.org` n'étant pas dans la liste des hôtes réseau autorisés) | Non — aucune obligation |

**Correction apportée à AGENTS.md §7** : la ligne Parltrack indiquait « CC0 / ODbL
(mixed) », ce que ne confirme pas la page Copyright de parltrack.org (uniquement
ODbL v1.0 pour les dumps JSON que consomme ce pipeline — le CC BY-SA 3.0 mentionné
sur ce site concerne le contenu HTML des pages, jamais téléchargé ici). Corrigée en
« ODbL v1.0 ». *Point non corrigé dans ce ticket* (hors périmètre, aucun fichier de
code) : `src/mep_profile.py:419` inscrit `"Open Data — Parltrack (CC0 / Open Database
License)"` dans `meta.licence_donnees`, la même approximation — à corriger dans la
sous-issue d'implémentation ou un ticket dédié. De même, `candidate_profile.py:2829`
et `generate_all_profiles.py:287` étiquettent tout `meta.licence_donnees` d'un profil
`"ODbL (Regards Citoyens…)"` alors que le même profil peut aussi contenir des champs
issus de l'Open Data AN (Etalab) via Syceron/scrutins/amendements — la métadonnée
interne ne distingue donc pas aujourd'hui les deux licences au sein d'un même profil ;
sans incidence sur le texte public des Mentions légales ci-dessous (qui couvre les deux
sources séparément), mais à garder en tête si `licence_donnees` est un jour affiché
tel quel côté `web/`.

**Hébergement de `web/UI_finale`** : aucun pipeline de déploiement du site trouvé —
`.github/workflows/` ne contient que `claude.yml`, `claude-code-review.yml`,
`generate-data.yml` et `retry-generate-data.yml` (génération de données, pas de build/
déploiement front), et `web/UI_finale` n'a ni config Vercel/Netlify ni workflow
GitHub Pages. **Statué : à préciser** — ne pas reprendre la mention « GitHub, Inc. »
de `web/old/v3/mentions-legales.html` tant qu'un hébergeur réel n'est pas choisi.

**Clause de partage à l'identique révisée** : dans `web/old/v3/mentions-legales.html`,
la clause « Implication pour la réutilisation de nos propres données » applique le
partage à l'identique ODbL à l'ensemble du jeu de données combiné. C'est inexact
depuis l'ajout des sources Etalab (AN) et CC0 (Wikidata), qui n'ont pas de clause de
réciprocité. Le partage à l'identique ne s'applique qu'aux **champs dérivés de
sources ODbL** (NosDéputés/NosSénateurs, Parltrack) en cas de republication d'un jeu
de données téléchargeable — voir le texte ci-dessous.

**Texte "Mentions légales" prêt à intégrer (sous-issue 2/3)** :

> # Mentions légales
>
> *Dernière mise à jour : 14 août 2026*
>
> ## Éditeur du site
>
> Ce site est édité à titre non professionnel et non commercial par une personne
> physique. Conformément à l'article 6-III de la loi n° 2004-575 du 21 juin 2004 pour
> la confiance dans l'économie numérique (LCEN), l'identité complète de l'éditeur est
> tenue à la disposition de l'hébergeur du site et pourra être communiquée, sur
> demande, à toute autorité judiciaire compétente.
>
> **Contact éditeur** : empreinte.politique@gmail.com
>
> ## Hébergement
>
> *À préciser.* L'hébergement définitif de ce site n'est pas encore déterminé à la
> date de rédaction de cette page ; cette section sera complétée dès qu'un hébergeur
> sera choisi.
>
> ## Directeur de la publication
>
> La direction de la publication est assurée par l'éditeur du site, joignable à
> l'adresse ci-dessus.
>
> ## Propriété intellectuelle — code et contenu éditorial
>
> Le code source, la charte graphique et les textes rédigés pour ce site sont à
> préciser, sauf mention contraire pour les données présentées (voir « Sources et
> licences des données » ci-dessous).
>
> ## Sources et licences des données
>
> Ce site s'appuie exclusivement sur des données publiques, réutilisées conformément
> aux licences suivantes.
>
> ### NosDéputés.fr et NosSénateurs.fr (Regards Citoyens)
>
> Les données relatives aux député·es et sénateur·rices français·es (mandats, votes,
> amendements) proviennent de NosDéputés.fr et NosSénateurs.fr, projets de
> l'association Regards Citoyens, mises à disposition sous licence **Open Database
> License (ODbL) v1.0** : https://opendatacommons.org/licenses/odbl/1-0/
>
> *Contient des informations issues de NosDéputés.fr et NosSénateurs.fr, par Regards
> Citoyens à partir de l'Assemblée nationale (ou du Sénat) et du Journal Officiel,
> mises à disposition sous licence ODbL.*
>
> ### Open Data de l'Assemblée nationale
>
> Les scrutins, amendements, dossiers législatifs, questions écrites et débats en
> séance (Syceron) proviennent du portail Open Data officiel de l'Assemblée nationale
> (data.assemblee-nationale.fr), mis à disposition sous **Licence Ouverte / Open
> Licence** (Etalab) : https://data.assemblee-nationale.fr/licence-ouverte-open-licence
>
> *Contient des informations publiques issues du portail Open Data de l'Assemblée
> nationale, sous Licence Ouverte / Open Licence.* Cette licence autorise la
> réutilisation commerciale et l'adaptation sans obligation de partage à l'identique,
> sous réserve de mention de la paternité.
>
> ### Parltrack
>
> Les données relatives aux député·es européen·nes (dossiers législatifs, votes,
> activités) proviennent des dumps JSON de Parltrack (parltrack.org), mis à
> disposition sous licence **Open Database License (ODbL) v1.0** :
> https://opendatacommons.org/licenses/odbl/1-0/
>
> *Contient des informations issues de Parltrack (parltrack.org), mises à disposition
> sous licence ODbL.*
>
> ### Parlement européen
>
> Les fiches et photos des député·es européen·nes proviennent du portail Open Data du
> Parlement européen (data.europarl.europa.eu) et du site institutionnel
> (www.europarl.europa.eu), réutilisées conformément au Legal Notice du Parlement
> européen : https://www.europarl.europa.eu/legal-notice/fr/ — reproduction, diffusion
> commerciale ou non commerciale autorisées sous réserve de reproduire l'élément dans
> son intégralité et d'en indiquer la source (« © Union européenne, [année] – Source :
> Parlement européen »).
>
> ### Wikipédia et Wikidata
>
> Le statut de candidature déclarée peut être recoupé via Wikipédia (fr.wikipedia.org)
> et Wikidata (query.wikidata.org). Ces deux sources ont des licences **distinctes** :
> Wikipédia est sous **Creative Commons Attribution — Partage dans les mêmes
> conditions 4.0 (CC BY-SA 4.0)** (https://creativecommons.org/licenses/by-sa/4.0/) ;
> les données structurées de Wikidata sont sous **CC0 1.0**, domaine public
> (https://creativecommons.org/publicdomain/zero/1.0/), sans obligation d'attribution
> ni de partage à l'identique.
>
> ### Implication pour la réutilisation de nos propres données
>
> Les jeux de données JSON produits et publiés par ce site combinent des contenus sous
> plusieurs licences. **Seuls les champs dérivés de sources sous ODbL (NosDéputés.fr,
> NosSénateurs.fr, Parltrack)** sont soumis à la clause de partage à l'identique de
> l'ODbL : toute republication d'un jeu de données dérivé téléchargeable incluant ces
> champs doit être mise à disposition sous une licence à clauses équivalentes.
> Les champs issus de l'Open Data de l'Assemblée nationale (Licence Ouverte / Etalab)
> et du Parlement européen n'imposent qu'une obligation d'attribution, sans partage à
> l'identique. Les champs issus de Wikidata (CC0) ne sont soumis à aucune restriction.
> Dans tous les cas, la consultation du site lui-même (page HTML, « Produced Work » au
> sens de l'ODbL) reste couverte par la simple attribution ci-dessus.

<a id="gouvernement-ci-integration"></a>
## Intégration de `generate_gouvernement_profiles.py` dans `generate-data.yml` (#215) (2026-08-14)

**Contexte** : #212 avait explicitement laissé le branchement CI hors
périmètre (voir [[quality-gate-gouvernements]], dernier paragraphe). #215
ajoute l'appel dans le job `merge-and-pivot`, juste après le step groupes
et avant le téléchargement (optionnel) de l'artifact amendements AN.

**Décision** : pas de job dédié, contrairement à `extract-amendements-an`/
`extract-parltrack`. `generate_gouvernement_profiles.py` n'a qu'un seul appel
réseau (le dump AN des dossiers législatifs, `gouvernement_textes.py`,
mutualisé pour tous les gouvernements du batch, ~10 Mo) — mesuré localement
à ~2 s à froid (téléchargement + parsing) et <0.5 s à chaud (cache
`.cache/dossiers_an/dossiers.zip` déjà présent), pour 10 gouvernements
générés à partir de 28 profils pivot locaux. Négligeable face au budget de
60 min de `merge-and-pivot` : mesuré, pas deviné (critère d'acceptation de
#215), aucun ajustement de `timeout-minutes` nécessaire.

Contrairement au step groupes (`--merge-existing` en mode `fresh_run=false`,
résilience réseau sur un roster live), le step gouvernement n'a pas
d'équivalent : `gouvernement_roster.py` n'interroge aucun réseau
(agrégation locale depuis les pivots déjà présents, voir
[[quality-gate-gouvernements]]), donc pas de FRESH-branching — le résultat
est déterministe à partir des données locales à chaque run, que `fresh_run`
soit `true` ou `false`.

`pivot_data/gouvernements` ajouté au `git add` du step de commit final, aux
côtés de `pivot_data/groupes`. La quality gate passait déjà `--gouvernements-dir`/
`--gouvernements-config` avec des défauts qui coïncidaient exactement avec
les valeurs utilisées ici ; ils sont désormais passés explicitement dans le
step CI, par cohérence avec `--groupes-dir`/`--groupes-config` (déjà
explicites) plutôt que de compter silencieusement sur les défauts du script.

*Hors périmètre* (comme #212 le précisait déjà, et non remis en cause ici) :
activation d'un `schedule:` cron pour ce nouvel appel — le `schedule:`
global du workflow reste commenté.
<a id="gouvernement-doc-cloture"></a>
## Documentation upkeep de clôture, vue Gouvernement (#214, plan #184) (2026-08-14)

**Contexte** : #214 demandait une passe finale de mise à jour documentaire
une fois #207-#213 réellement mergées, sans anticiper de fonctionnalité non
livrée. Les PR #207-#213 avaient déjà fait leur propre upkeep `AGENTS.md §8`
au fil de l'eau ; cette entrée ne duplique pas ce contenu, elle le
consolide par renvoi :

1. **Rattachement des textes par `date_depot`** : décision et alternative
   rejetée (chaîne `AMO30`) déjà documentées in extenso —
   voir [[gouvernement-profile-rattachement]] (#211) et [[gouvernement-textes-statut]]
   (#210, section "Alternative rejetée").
2. **Gap couverture ministérielle (`portefeuille`)** : déjà documenté comme
   hors périmètre — voir [[hors-perimetre]] § "Ministerial function", repris
   dans `check_quality_gate.py` ([[quality-gate-gouvernements]]) et `ROADMAP.md`.
   Pas de nouvelle source identifiée depuis #212 ; toujours non résolu.
3. **Limite Sénat, confirmée spécifique à cette vue** : `gouvernement_textes.py`
   ne lit que le dump AN `Dossiers_Legislatifs.json.zip` — un texte dont le
   Sénat est la chambre de dépôt *primaire* n'est jamais vu (seuls les textes
   déposés à l'AN, y compris ceux transmis en 2e lecture au Sénat, entrent
   dans `textes[]`). C'est un cas particulier de la limite déjà actée en
   [[hors-perimetre]] § "Senate votes, amendments, sponsored texts" (aucun
   dataset Sénat structuré exploitable), reconfirmé ici pour la vue
   Gouvernement spécifiquement car `schema_gouvernement.py` expose
   `chambre_depot_initial` (`"AN"` ou `"Senat"`) et pourrait laisser croire à
   tort à une couverture bicamérale complète.

**Hors périmètre de cette entrée** : aucun changement de code ; voir la table
`AGENTS.md §8` appliquée dans la PR de #214 pour le détail fichier par
fichier. `docs/pipeline-gouvernement.md` (miroir de
`docs/pipeline-profiles-groupes.md`) n'est pas créé ici : proposition
soumise à validation explicite (hors table d'upkeep existante), voir la PR.

<a id="quality-gate-gouvernements"></a>
## `check_quality_gate.py` : section gouvernements (§5), couverture ministérielle proxy par `portefeuille` (#212) (2026-08-14)

**Contexte** : #212 (plan #184) demandait d'intégrer les profils de
gouvernement au quality gate CI sur le modèle de la section groupes
existante (`_report_groupes`, §4) : hard fail sur structure cassée, soft
fail sur qualité dégradée. Contrairement à `_report_groupes`, `schema_gouvernement.py`
n'a pas de notion de `meta.couverture_roster` (roster_total/profils_disponibles) :
un gouvernement est agrégé localement à partir des profils pivot déjà présents,
sans fetch réseau dédié (`gouvernement_roster.py` n'interroge aucun roster
externe, voir [[gouvernement-roster-desambiguisation]]) — il n'y a donc pas de
dénominateur "effectif réel" à comparer aux `membres[]` obtenus.

**Décision** : `_report_gouvernements()` (miroir de `_report_groupes()`) retient
trois soft fails adaptés :
1. **Couverture ministérielle incomplète** — proxy sur `membres[].portefeuille`
   (nb de portefeuilles confirmés / nb de membres), pas sur un ratio
   roster/profils. Cette incomplétude est structurelle et documentée
   ([[hors-perimetre]] § "Ministerial function") : aucune source open-data
   n'identifie encore le portefeuille précis, donc ce warning se déclenche
   aujourd'hui sur la totalité des gouvernements réels — signal volontairement
   bruyant tant que la source manque, non bloquant (soft), utile pour
   constater automatiquement une future amélioration de couverture.
2. **`textes[]` vide alors que `periode.debut` est renseigné** — mirroir de
   "membres présents mais 0 cohesion_votes" côté groupes.
3. **Signaux réseau `IncompleteRead`** dans `meta.warnings`, propagés depuis
   `gouvernement_textes.py` (même logique que `_GROUPE_NETWORK_SIGNALS`, sans
   les motifs spécifiques roster qui n'ont pas d'équivalent gouvernemental).

Hard fails identiques à `_report_groupes` : fichier attendu manquant, JSON
invalide, `validate_profil_gouvernement()` en erreur — OR-é dans le code de
sortie final aux côtés de `grp_exit`. `pivot_data/gouvernements` ajouté au
scan `IncompleteRead` générique (`ir_dirs`, section 1). Nouveaux arguments
CLI `--gouvernements-dir` (défaut `pivot_data/gouvernements`) et
`--gouvernements-config` (défaut `raw_data/gouvernements_reels.json`), miroir
de `--groupes-dir`/`--groupes-config`. Rapport renuméroté en conséquence :
groupes reste §4, gouvernements §5, ParlTrack (optionnel) devient §6.

**Alternative rejetée** : réutiliser `min_members`/`min_coverage_pct` (seuils
de `_report_groupes`) tels quels pour la couverture ministérielle. Écartée
car ces seuils comparent à un roster réseau qui n'existe pas ici — le seul
dénominateur disponible localement est `len(membres)`, donc un seuil absolu
sur le nombre de membres n'aurait mesuré qu'une réalité déjà garantie par la
construction du roster (`gouvernement_roster.build_gouvernement_roster`), pas
une qualité de donnée dégradée.

Hors périmètre (comme demandé par #212) : pas de branchement dans
`generate-data.yml` (sous-issue #9), pas de nouvelle section dans
`audit_pivot_dataset.py`/`audit_groupe_dataset.py`.

<a id="direction-artistique-empreinte"></a>
## Direction artistique de `web/UI_finale` : brief, itérations et alternatives écartées (2026-08-14)

**Contexte** : refonte de la direction artistique de `web/UI_finale` (CONTRECHAMP),
pensée pour trois cibles emboîtées — des citoyens français en âge de voter,
engagés et avec une appétence tech/data/analytics (cœur de cible ayant guidé
les choix), jusqu'au grand public français. Le brief demandait une DA moderne,
orientée tech & analytics, en **rupture explicite** avec les codes
médias/presse et avec `web/old/v3` en particulier (masthead, police Archivo
Black, kickers datés, rayon de bordure zéro).

Socle retenu dès le départ : un « produit SaaS analytique » (sidebar, cartes
blanches, hairlines) avec un vocabulaire « instrumentation scientifique » pour
les chiffres (nombres tabulaires stricts, `font-variant-numeric: tabular-nums`) ;
un graphe de réseau a été explicitement mis de côté pour une éventuelle vue
avancée future, pas retenu dans ce socle. Le brief demandait aussi une
composante user-friendly, dynamique jeu/appli mobile façon Revolut — mais
**forme et geste uniquement, jamais le ton** : poser un score, un streak, un
badge, un classement ou une félicitation aurait directement contredit la règle
1 de `AGENTS.md §2` (aucun jugement de valeur, aucun score, aucun classement) —
posé dès le brief comme une règle fondatrice du projet, pas une préférence
esthétique.

Une première itération inspirée de Revolut a ensuite été **explicitement
corrigée** pour s'en éloigner visuellement : abandon du violet, des chips
pastel par catégorie, des avatars multicolores. Réintroduction du code
jaune fluo / noir — l'acide `#DFFF00` déjà présent dans `web/old/v3` — mais
cette fois en usage strictement fonctionnel (accent de sélection/action/source
vérifiée, jamais décoratif, jamais en texte sur fond clair — voir la table de
contraste WCAG dans `web/UI_finale/DESIGN_SYSTEM.md` §2, ratio 1.05:1 = échec
AA). Ajustements de détail en revue de maquette : texte noir sur fond jaune
(pas l'inverse) ; carte héro finalement en noir/texte blanc plutôt qu'en
jaune ; fond non neutre — filigrane d'arcs concentriques façon empreinte
digitale, en transparence, couvrant tout le fond (explicitement pas une
mosaïque répétée du logo — implémenté dans `src/styles/shell.css`, `.app-shell`).

**Décision** : livrer des maquettes mobile puis web sur les deux fiches
existantes (Candidat, Groupe) sans modifier le socle analytique déjà validé,
en intégrant les retours de revue : surbrillance au survol des cartes KPI
(`.kpi-caveat`), flyouts au clic pour mandats et responsabilités, reprise des
infographies de la page Gabriel Attal dans l'onglet Textes, correction de
l'alignement logo/wordmark. Le design system a ensuite été généré à partir de
ces maquettes App Web, publié en artifact Claude (« Empreinte — Direction
artistique · v1 »,
`claude.ai/code/artifact/d48b7554-0af3-45bd-904e-94367577ff4a`), puis
réconcilié ligne à ligne avec le code réel de `web/UI_finale/src` pour produire
`web/UI_finale/DESIGN_SYSTEM.md` (v2) — voir ce fichier pour l'état final
détaillé (palette, typographie, composants) et sa section 8 pour les écarts
constatés entre la cible et l'implémentation.

*Alternative rejetée* : conserver la direction visuelle façon Revolut (violet,
chips pastel par catégorie, avatars multicolores) et son registre ludique
(score/streak/badge/classement/félicitation) — rejetée non pas pour goût
esthétique mais parce qu'elle réintroduirait un jugement de valeur explicitement
interdit par la règle 1 de `AGENTS.md §2`. Toute proposition future de
gamification de l'interface doit être évaluée à l'aune de cette même règle, pas
seulement d'une préférence de design.
<a id="gouvernement-profile-rattachement"></a>
## `gouvernement_profile.py` : rattachement des textes par `date_depot`, exclusion silencieuse des dossiers non classifiables (#211) (2026-08-14)

**Contexte** : #211 combine la sortie de `gouvernement_roster.py` (composition
ministérielle, pure) et `gouvernement_textes.py` (dossiers d'origine
gouvernementale, non filtrés par gouvernement — le rattachement était
explicitement laissé hors périmètre par sa docstring) en un profil de
gouvernement complet conforme à `schema_gouvernement.py`.

**Décision** :
1. Rattachement d'un dossier à un gouvernement par recouvrement de sa
   `date_depot` avec `periode` (bornes incluses, `periode.fin = None` = borne
   haute ouverte), jamais par `date_dernier_evenement` — un texte déposé sous
   un gouvernement A puis conclu sous un gouvernement B reste crédité à A, qui
   l'a initié (décision déjà actée dans le plan d'implémentation de #184, voir
   docstring `gouvernement_textes.py`). Une `date_depot` absente exclut
   silencieusement le dossier (jamais de rattachement par défaut).
2. Un dossier dont `statut` est `None` (fam_code inconnu côté
   `gouvernement_textes.py`, voir [#gouvernement-textes-statut](#gouvernement-textes-statut))
   ou dont `chambre_depot_initial` est `None` (aucun acte `-DEPOT`
   identifiable) est exclu de `textes[]`, avec un warning explicite dans
   `meta.warnings` : le schéma n'admet aucune valeur `null` sur ces deux
   champs (`KNOWN_STATUTS_TEXTE_GOUVERNEMENTAL`/`KNOWN_CHAMBRES_DEPOT_TEXTE`),
   et inventer une valeur par défaut violerait la règle AGENTS.md §2.5.
   Conséquence directe : `comptages.par_statut` ne compte que les dossiers
   effectivement inclus dans `textes[]`, jamais un dossier exclu.
3. Anti double-comptage : dédoublonnage par `dossier_id` au sein d'un même
   appel à `build_gouvernement_profile` (protège contre un dossier présent
   deux fois dans l'entrée non filtrée) ; `generate_gouvernement_profiles.py`
   ne fetch les dossiers et ne charge les profils pivot qu'UNE SEULE fois
   pour l'ensemble du batch (mutualisé entre tous les gouvernements), comme
   `generate_group_profiles.py` le fait pour le roster par `(chambre,
   legislature)`. Vérifié sur les 10 gouvernements réels de
   `raw_data/gouvernements_reels.json` (run du 2026-08-14) : 61 `dossier_id`
   dans `textes[]` au total, tous distincts, aucun partagé entre deux
   fichiers `pivot_data/gouvernements/*.json`.
4. `comptages.par_statut` : uniquement des entiers bruts (dénombrement),
   aucun taux ni pourcentage — vérifié par test explicite sur les clés du
   dict (règle AGENTS.md §2.1).
5. `sources[]` du profil de gouvernement : dédoublonnées, mais limitées aux
   profils pivot des membres effectivement retenus dans `membres[]` (pas de
   tous les profils passés en entrée, qui couvrent potentiellement
   l'ensemble du dépôt local) — sinon un gouvernement à faible couverture
   afficherait des sources sans rapport avec ses membres réels.

**Vérification manuelle (critère d'acceptation #211)** : `gouvernement:ATTAL`
généré en conditions réelles inclut le dossier `DLR5L16N50115` (« Projet de
loi autorisant la ratification de la convention n°155 sur la sécurité et la
santé des travailleurs, 1981 »), déposé le 2024-06-12 (dans la période Attal,
2024-01-10/2024-09-05), `statut = "adopte"`. Confirmé contre
`assemblee-nationale.fr` : promulguée sous le n° 2025-983 au Journal officiel
du 23/10/2025.

**Hors périmètre** : `premier_ministre` reste `null` (aucune source encore
câblée pour le déterminer) ; intégration à `check_quality_gate.py` (#6) et
CI/CD (#9) non traitées ici.
*Périmé depuis #398 — voir [la section dédiée](#gouvernement-premier-ministre-portefeuille) :
`premier_ministre` et `membres[].portefeuille` sont câblés depuis les mandats
`MINISTERE`. La source existait déjà, elle n'était pas consommée.*

<a id="gouvernement-textes-statut"></a>
## `gouvernement_textes.py` : filtre de statut par décision de séance, pas par `codeActe`/`fam_code` seul (#210) (2026-08-14)

**Contexte** : #210 (sous-issue de #184) demandait la collecte des dossiers
législatifs d'origine gouvernementale et l'extraction de leur statut, en
s'appuyant sur le mapping `statutConclusion.fam_code` confirmé par le spike
#207 (déjà reporté dans `docs/an_opendata.md`, section « Spike : origine »).
Vérification sur données réelles (téléchargement direct de
`Dossiers_Legislatifs.json.zip` le 2026-08-14, mêmes deux dossiers cités par
le spike, `DLR5L17N50588`/`DLR5L17N54196`) : un dossier accumule souvent
*plusieurs* actes portant `statutConclusion` à des dates différentes (une
décision par lecture/chambre, plus les constats de CMP et les décisions du
Conseil constitutionnel), et pas seulement les 4 `fam_code` confirmés. Deux
angles morts non couverts par le spike :
1. Le Conseil constitutionnel (`CC-CONCLUSION`) et l'accord/désaccord de CMP
   (`CMP-DEC`) portent eux aussi un `statutConclusion` (`fam_code` `TCD0x`/
   `TCCMP01`), postérieur en date à la décision de séance qui a réellement
   tranché le sort du texte (constaté sur `DLR5L17N50588` : `CC-CONCLUSION`
   daté du 2025-02-28, après l'adoption via 49.3 du 2025-02-12) — un simple
   « dernier `statutConclusion` par date » aurait donc rapporté un statut
   inexistant plutôt que le vrai statut final.
2. Le code de décision de CMP ne se termine pas par `-DEBATS-DEC` mais par
   `-AN-DEC`/`-SN-DEC` (`CMP-DEBATS-AN-DEC`, `CMP-DEBATS-SN-DEC`) : un filtre
   `codeActe.endswith("-DEBATS-DEC")` les exclut à tort, alors que ce sont de
   vraies décisions de séance (constaté sur `DLR5L17N50588`, l'unique
   occurrence connue de `TSORTF24` dans le dataset).

**Décision** :
1. `_est_decision_de_seance(code_acte)` filtre sur `"-DEBATS-" in code_acte
   and code_acte.endswith("-DEC")` plutôt qu'un `endswith` unique, pour
   couvrir les codes de CMP sans réintroduire `CC-CONCLUSION`/`CMP-DEC` (qui
   ne contiennent pas `-DEBATS-`).
2. Seule la décision de séance **chronologiquement la plus récente** parmi
   celles-ci détermine le statut du dossier (pas le dernier `statutConclusion`
   toutes origines confondues) — un dossier adopté en 1ère lecture puis
   modifié par la seconde chambre reste en navette, pas « adopté ».
3. `fam_code == "TSORTFnull"` (constaté sur un acte de décision sans issue
   tranchée) est traité comme absence d'événement, jamais comme un `fam_code`
   inconnu à signaler.
4. Cas non résolu, volontairement flagué plutôt que masqué : `TSORTF24`
   (rejeté consécutivement à l'engagement de l'art. 49.3, motion de censure
   adoptée) est mappé à `statut = "rejete"` + `sort_49_3 = True`, qui reflète
   fidèlement le fait mais est **incompatible** avec l'invariant actuel de
   `schema_gouvernement.validate_profil_gouvernement` (`sort_49_3 = True`
   n'est autorisé qu'avec `statut == "adopte_49_3"`, faute de statut « rejeté
   via 49.3 » dans la nomenclature fermée de #208). Un warning explicite est
   émis dans ce cas ; la résolution (étendre la nomenclature ou assouplir le
   validateur) relève de #208/#211, pas de la collecte.
5. Infrastructure de téléchargement : `gouvernement_textes.py` devient la
   source canonique de `AN_DOSSIERS_ZIP_URL`/`DOSSIERS_CACHE_DIR` et d'un
   `ensure_dossiers_zip_downloaded()` partagé (écriture atomique via fichier
   `.part`) ; `candidate_profile.py` (`_build_texte_titre_index`,
   `_build_acteur_textes_portes_index`) importe désormais ces symboles au
   lieu de dupliquer le téléchargement (deux blocs identiques avant ce
   correctif) — un seul cache pour ce fichier ~10 Mo, comme demandé par #210.

**Alternative rejetée** : implémenter la chaîne `initiateur.acteurs.acteur[]
-> mandat GOUVERNEMENT -> organeRef` (dataset `AMO30`) comme signal
d'origine. Rejetée pour ce module : ~15 % de faux positifs sans filtrage par
date de mandat vs date de dépôt (co-signataires ex-ministres, mesuré par le
spike #207), pour ne couvrir que les dossiers hors préfixe de titre (2355 sur
3044, majoritairement motions/résolutions/rapports hors périmètre éditorial).
Seul le préfixe de titre (« Projet de loi » vs « Proposition de loi »,
689/3044 dossiers, aucun faux positif) est implémenté ; `AMO30` reste un
repli possible pour un futur complément, non fait ici.
<a id="gouvernement-textes-statut-49-3-rejete"></a>
## `KNOWN_STATUTS_TEXTE_GOUVERNEMENTAL` : ajout de `rejete_49_3` (#208, réouverte) (2026-08-14)

**Contexte** : la nomenclature fermée des statuts de texte gouvernemental
(#208, fusionnée dans `main`) n'anticipait le 49.3 (art. 49 al. 3 de la
Constitution) que comme voie d'**adoption** (`statut = "adopte_49_3"`). En
implémentant la collecte réelle (#210), un cas non anticipé est apparu sur
des données AN réelles : `fam_code` `TSORTF24` = « rejeté via 49.3, motion de
censure adoptée » — c'est le sort effectivement survenu au budget 2025 sous
le gouvernement Barnier (décembre 2024). Ce n'est pas un cas hypothétique
qu'on choisirait d'anticiper par prudence : c'est un fait déjà survenu, donc
certain de réapparaître dans la donnée historique. `gouvernement_textes.py`
mappait ce cas à `statut = "rejete"` + `sort_49_3 = True`, une combinaison
que `validate_profil_gouvernement` rejetait (seul `"adopte_49_3"` était
autorisé avec `sort_49_3 = True`) — ce qui aurait fait échouer dur
l'agrégation (#211) dès le premier gouvernement réel touché par ce cas.

**Décision** : ajout de `"rejete_49_3"` à `KNOWN_STATUTS_TEXTE_GOUVERNEMENTAL`,
symétrique d'`"adopte_49_3"` — même exigence d'appariement avec
`sort_49_3 = True`, même interdiction de collapse silencieux (cette fois vers
`"rejete"` simple plutôt que vers `"adopte"`). Alternative rejetée : assouplir
le validateur pour rendre `sort_49_3` orthogonal au `statut` (autorisé avec
n'importe quelle valeur) — écartée car elle affaiblirait la garantie actuelle
que le 49.3 reste toujours visible comme son propre statut explicite plutôt
que comme un simple booléen surimposé (règle AGENTS.md §2.4). Cohérent avec
le principe déjà acté en #208 : le 49.3 est un fait procédural distinct de
l'issue du vote, jamais fusionné avec elle — cette règle s'applique
symétriquement au rejet, pas seulement à l'adoption.

<a id="gouvernement-roster-desambiguisation"></a>
## `gouvernement_roster.py` : désambiguïsation par libellé exact + garde-fou de période, pas l'inverse (#209) (2026-08-14)

**Contexte** : `mandats[].categorie == "fonction_gouvernementale"` (déjà peuplé
par `candidate_profile.py` depuis `AMO30_tous_acteurs_tous_mandats_tous_organes_historique.json.zip`,
voir [[hors-perimetre]] § "Ministerial function") porte un `label` du type
`"Gouvernement (<libelleAbrege>)"`, où `libelleAbrege` est le seul identifiant
que l'AN expose pour un gouvernement (ex. "BORNE", "LECORNU II") — ambigu en
cas de gouvernements homonymes lors d'un remaniement.

**Décision** : `raw_data/gouvernements_reels.json` (miroir éditorial de
`groupes_reels.json`) fixe manuellement `libelle_an` par gouvernement.
`gouvernement_roster.build_gouvernement_roster` sélectionne un mandat membre
d'abord par correspondance **exacte** de ce libellé, puis vérifie en second
lieu que la période du mandat chevauche celle du gouvernement (garde-fou
contre une anomalie de données, pas critère principal). Périodes de
`gouvernements_reels.json` dérivées des dates min/max réellement observées
sur les mandats `fonction_gouvernementale` déjà présents dans
`pivot_data/profiles/*.pivot.json` (zéro appel réseau, zéro date inventée).

**Alternative rejetée** : filtrer uniquement par chevauchement de période
(sans libellé). Rejeté parce que c'est précisément le chevauchement qui est
ambigu lors d'un remaniement rapproché (l'exemple donné dans l'issue #209 est
la distinction entre deux gouvernements homonymes successifs) — le libellé
exact est la seule donnée qui lève cette ambiguïté de façon fiable.

<a id="gouvernement-textes-statut"></a>
## `gouvernement_textes.py` : filtre de statut par décision de séance, pas par `codeActe`/`fam_code` seul (#210) (2026-08-14)

**Contexte** : #210 (sous-issue de #184) demandait la collecte des dossiers
législatifs d'origine gouvernementale et l'extraction de leur statut, en
s'appuyant sur le mapping `statutConclusion.fam_code` confirmé par le spike
#207 (déjà reporté dans `docs/an_opendata.md`, section « Spike : origine »).
Vérification sur données réelles (téléchargement direct de
`Dossiers_Legislatifs.json.zip` le 2026-08-14, mêmes deux dossiers cités par
le spike, `DLR5L17N50588`/`DLR5L17N54196`) : un dossier accumule souvent
*plusieurs* actes portant `statutConclusion` à des dates différentes (une
décision par lecture/chambre, plus les constats de CMP et les décisions du
Conseil constitutionnel), et pas seulement les 4 `fam_code` confirmés. Deux
angles morts non couverts par le spike :
1. Le Conseil constitutionnel (`CC-CONCLUSION`) et l'accord/désaccord de CMP
   (`CMP-DEC`) portent eux aussi un `statutConclusion` (`fam_code` `TCD0x`/
   `TCCMP01`), postérieur en date à la décision de séance qui a réellement
   tranché le sort du texte (constaté sur `DLR5L17N50588` : `CC-CONCLUSION`
   daté du 2025-02-28, après l'adoption via 49.3 du 2025-02-12) — un simple
   « dernier `statutConclusion` par date » aurait donc rapporté un statut
   inexistant plutôt que le vrai statut final.
2. Le code de décision de CMP ne se termine pas par `-DEBATS-DEC` mais par
   `-AN-DEC`/`-SN-DEC` (`CMP-DEBATS-AN-DEC`, `CMP-DEBATS-SN-DEC`) : un filtre
   `codeActe.endswith("-DEBATS-DEC")` les exclut à tort, alors que ce sont de
   vraies décisions de séance (constaté sur `DLR5L17N50588`, l'unique
   occurrence connue de `TSORTF24` dans le dataset).

**Décision** :
1. `_est_decision_de_seance(code_acte)` filtre sur `"-DEBATS-" in code_acte
   and code_acte.endswith("-DEC")` plutôt qu'un `endswith` unique, pour
   couvrir les codes de CMP sans réintroduire `CC-CONCLUSION`/`CMP-DEC` (qui
   ne contiennent pas `-DEBATS-`).
2. Seule la décision de séance **chronologiquement la plus récente** parmi
   celles-ci détermine le statut du dossier (pas le dernier `statutConclusion`
   toutes origines confondues) — un dossier adopté en 1ère lecture puis
   modifié par la seconde chambre reste en navette, pas « adopté ».
3. `fam_code == "TSORTFnull"` (constaté sur un acte de décision sans issue
   tranchée) est traité comme absence d'événement, jamais comme un `fam_code`
   inconnu à signaler.
4. `TSORTF24` (rejeté consécutivement à l'engagement de l'art. 49.3, motion
   de censure adoptée) est mappé à `statut = "rejete_49_3"` + `sort_49_3 =
   True`, symétrique d'`adopte_49_3` — voir
   [[gouvernement-textes-statut-49-3-rejete]] (#208 réouverte) pour l'ajout de
   ce statut à la nomenclature fermée, qui rend la combinaison représentable
   par `schema_gouvernement.validate_profil_gouvernement` sans warning.
5. Infrastructure de téléchargement : `gouvernement_textes.py` devient la
   source canonique de `AN_DOSSIERS_ZIP_URL`/`DOSSIERS_CACHE_DIR` et d'un
   `ensure_dossiers_zip_downloaded()` partagé (écriture atomique via fichier
   `.part`) ; `candidate_profile.py` (`_build_texte_titre_index`,
   `_build_acteur_textes_portes_index`) importe désormais ces symboles au
   lieu de dupliquer le téléchargement (deux blocs identiques avant ce
   correctif) — un seul cache pour ce fichier ~10 Mo, comme demandé par #210.

**Alternative rejetée** : implémenter la chaîne `initiateur.acteurs.acteur[]
-> mandat GOUVERNEMENT -> organeRef` (dataset `AMO30`) comme signal
d'origine. Rejetée pour ce module : ~15 % de faux positifs sans filtrage par
date de mandat vs date de dépôt (co-signataires ex-ministres, mesuré par le
spike #207), pour ne couvrir que les dossiers hors préfixe de titre (2355 sur
3044, majoritairement motions/résolutions/rapports hors périmètre éditorial).
Seul le préfixe de titre (« Projet de loi » vs « Proposition de loi »,
689/3044 dossiers, aucun faux positif) est implémenté ; `AMO30` reste un
repli possible pour un futur complément, non fait ici.

<a id="amendements-legislatures-figees"></a>
## Index amendements des législatures 15/16 : construction manuelle hors CI, committée (2026-08-13)

**Contexte** : le job CI dédié `extract-amendements-an` ([[amendements-index-job-dedie-ci]],
#251) a échoué sur son tout premier run réel pour les législatures 15 et 16 —
`IncompleteRead` répété dès le premier segment de `Amendements_XV.json.zip`
(648 Mo) et `Amendements.json.zip`/16 (363 Mo), les 3 tentatives
(`AMENDEMENTS_DOWNLOAD_MAX_ATTEMPTS`) épuisées à chaque fois (voir logs du run
GitHub Actions #31705965678, job `extract-amendements-an`). La quality gate
section 3d ([[amendements-index-quality-gate-fraicheur]], #254) rapportait
alors, à raison, les deux comme « jamais construit ». Reproduit hors CI :
un téléchargement manuel (`curl --http1.1`, retries, resume `-C -`, budget
1h+) rencontre le même type de coupure (`HTTP/2 stream ... PROTOCOL_ERROR`
puis, en HTTP/1.1, `transfer closed with N bytes remaining to read`) —
confirme que la cause est le CDN d'`data.assemblee-nationale.fr` lui-même sur
ces deux grosses archives, pas une contrainte spécifique aux runners GitHub
Actions.

Ces deux législatures sont closes : leurs dossiers législatifs ne seront plus
jamais amendés, et l'en-tête `Last-Modified` des archives le confirme
(`2022-06-09` pour la 15e, `2024-06-28` pour la 16e — probablement une
dernière correction éditoriale AN, pas une évolution de fond). Retenter à
chaque run CI un téléchargement de 350-650 Mo pour une donnée figée n'a donc
aucune valeur — contrairement à la législature 17 (en cours), dont l'archive
évolue et doit rester reconstruite en continu par le job CI existant.

**Décision** :
1. `AN_AMENDEMENTS_LEGISLATURES_FIGEES = frozenset({"15", "16"})`
   (`candidate_profile.py`), et un nouveau script one-shot
   `src/build_amendements_index_figees.py --legislature {15,16} (--zip <archive
   locale> | --download)` qui réutilise le parsing existant
   (`_parse_amendements_zip`, extrait de `_download_and_build_amendement_index`)
   sur une archive amendements AN, soit déjà téléchargée manuellement
   (patience/retries hors budget CI, cas d'origine documenté ci-dessous), soit
   téléchargée par le script lui-même via `--download` (réutilise
   `_download_amendements_zip` — mêmes segments HTTP Range + retries que le
   job CI réseau — dans `.cache/amendements_an/<legislature>/`, gitignoré,
   jamais committé).
2. `_download_and_build_amendement_index` court-circuite tout accès réseau
   pour ces deux législatures : `_load_frozen_amendement_index` lit le
   fallback committé et le matérialise dans le cache disque standard
   (`.cache/amendements_an/<legislature>/`), au même format qu'une
   construction réseau réussie — transparent pour `fetch_amendements_officiels`
   et pour `check_quality_gate.py`.
3. Section 3d du quality gate : nouvel état **figé** (distinct de
   jamais-construit/périmé/frais), déclenché quand la législature est dans
   `_AMENDEMENTS_LEGISLATURES_FIGEES` *et* que `fraicheur.json` porte
   `figee: true`. Aucune notion de péremption ne s'applique — pas de
   warning, jamais, même après `--amendements-staleness-days`.

**Révision (2026-08-13, après inspection de la release `amendements-figes-v1`)** :
le point 1 ci-dessus committait initialement `index_par_acteur.json` tel que
produit par `_parse_amendements_zip` — un enregistrement complet par
signataire (auteur + chaque cosignataire), chacun portant sa propre copie
intégrale de l'amendement (dont `co_signataires`). Un premier build réel de la
législature 16 a mesuré ce fichier à **3,86 Go décompressés** (63,7 Mo une
fois gzippé) — l'inverse de l'affirmation « plusieurs ordres de grandeur plus
petit » ci-dessous, et surtout largement au-delà de la limite GitHub de
100 Mo par blob une fois décompressé, rendant un `git add` direct
structurellement impossible (pas seulement indésirable). La législature 15
(archive source plus grosse) aurait vraisemblablement heurté la même limite,
y compris compressée (marge insuffisante par simple extrapolation du ratio
observé sur la 16).

> **Révisé le 18/08/2026** — la clé de déduplication décrite ci-dessous
> (`numero`) était fausse : elle écrasait 74,9 % des amendements et en
> attribuait 40,5 % au mauvais texte. Le store est désormais keyé par l'`uid`
> AN et les index figés ont été reconstruits ; voir
> [[amendements-cle-uid]]. Le reste de cette entrée (pourquoi dédupliquer,
> pourquoi gzip, pourquoi hors CI) reste valable.

Plutôt que de committer le `.json.gz` compressé tel quel (alternative
initialement envisagée, pariant sur le ratio de compression ~60:1 pour rester
sous 100 Mo — non garanti pour la 15e), le format committé a été revu pour
dédupliquer la donnée à la source : `_aggregate_amendements_index` (nouveau,
`candidate_profile.py`) sépare l'index brut en `amendements.json` (chaque
amendement stocké une seule fois, sous la clé `numero`) et
`index_par_acteur.json` allégé (`acteurRef` -> liste de
`{numero, role_signataire}`, une référence légère au lieu d'une copie
complète). `_load_frozen_amendement_index` recompose la forme plate standard
via `_expand_aggregated_amendements_index` (inverse exact) au moment de la
matérialisation dans le cache disque — aucun changement pour
`fetch_amendements_officiels` ni pour le chemin réseau (législature 17), qui
continuent de produire/lire la forme plate non dédupliquée dans
`.cache/amendements_an/` (gitignoré, jamais committé, donc son volume n'a
jamais posé de problème).

**Révision (2026-08-14, reprise du téléchargement entre invocations)** : un
premier `--download` réel pour la législature 16 a échoué en cours de segment
(`IncompleteRead(0 bytes read, ...)`), reproduit à la main juste après contre
le CDN AN en dehors de toute exécution du script — coupures aléatoires en
cours de flux, pas seulement en fin de fichier, sur des offsets variables
d'un essai à l'autre. `_download_amendements_zip` ne persistait aucun état
entre deux invocations : chaque nouvel appel repartait de l'octet 0, faisant
perdre les dizaines/centaines de Mo déjà reçus lors d'une tentative
précédente. `_download_amendements_zip` détecte désormais un `zip_path`
existant non vide au démarrage, sonde la taille distante réelle via une
requête `HEAD` (`_probe_amendements_total_size`, best-effort) puis choisit
entre trois issues : fichier déjà complet (taille locale = taille distante)
→ aucune requête de téléchargement, seulement la sonde ; fichier partiel plus
petit → reprise en mode ajout (`"ab"`) à partir de l'octet déjà écrit ; sonde
en échec ou taille locale incohérente (plus grande que la taille distante) →
redémarrage prudent depuis le début plutôt que de deviner un offset invalide.
`build_amendements_index_figees.py --download` appelle désormais
systématiquement `_download_amendements_zip` (l'ancien raccourci "fichier déjà
présent -> réutilisé tel quel sans vérification" contournait entièrement ce
mécanisme et pouvait tenter de parser une archive partielle/corrompue comme
si elle était complète). Garde-fou associé : si un segment demandé à un
offset non nul reçoit malgré tout une réponse `200` (le serveur ignore
`Range`), l'écriture est refusée (`OSError`) plutôt que d'ajouter le corps
complet à la suite d'un fichier déjà partiellement écrit, ce qui produirait
une archive corrompue silencieusement.

Complément (même date) : le CDN AN a ensuite traversé une fenêtre où même une
requête Range de quelques Ko au-delà des tout premiers Mo du fichier échouait
systématiquement (`IncompleteRead(0 bytes read, ...)`) — un segment de 32 Mo
(`AMENDEMENTS_DOWNLOAD_CHUNK_BYTES`, défaut) n'avait alors quasiment aucune
chance d'aboutir intégralement. `_download_amendements_zip` accepte désormais
un paramètre `chunk_bytes` optionnel, exposé via `--chunk-size-mb` sur
`build_amendements_index_figees.py`, pour réduire ponctuellement la taille de
segment (ex. 1 Mo) sans toucher au défaut partagé avec le chemin réseau de la
législature 17 — la reprise entre invocations garantit qu'aucun petit gain
n'est perdu d'un essai à l'autre. `_download_amendements_zip` affiche
également désormais une ligne de progression (octets/total, pourcentage)
après chaque segment écrit avec succès, pas seulement en cas
d'échec/retry : avec de petits `chunk_bytes`, une invocation peut compter des
centaines de segments et rester silencieuse plusieurs minutes sans ce retour.

De même, `max_attempts` (optionnel, défaut `AMENDEMENTS_DOWNLOAD_MAX_ATTEMPTS`,
3) permet d'augmenter le nombre de tentatives par segment via `--max-attempts`
sans toucher au défaut CI de la législature 17 — utile quand le CDN traverse
une fenêtre où 3 tentatives ne suffisent pas systématiquement ; chaque
tentative supplémentaire ne coûte que le temps d'attente (un retry ne
retente jamais que le segment en échec), et la reprise entre invocations
couvre de toute façon le cas d'un abandon total.

**Révision (2026-08-15, la dédup seule ne suffit pas non plus)** : le premier
build réel complet de la législature 16 (archive téléchargée en entier) a
mesuré `index_par_acteur.json` allégé (post-`_aggregate_amendements_index`,
donc déjà `{numero, role_signataire}` par lien plutôt qu'une copie complète)
à **177 Mo en clair** — toujours au-delà de la limite GitHub de 100 Mo par
blob, contrairement à ce que laissait supposer la révision du 2026-08-13
(`amendements.json` compacté à 1,1 Mo gzippé n'a en revanche jamais posé de
problème). La structure `{numero, role_signataire}` étant très répétitive,
gzip compresse ce fichier à **10,4 Mo** — `build_amendements_index_figees.py`
écrit donc désormais `amendements.json.gz` et `index_par_acteur.json.gz`
(constantes `AMENDEMENTS_FIGEES_AMENDEMENTS_FILENAME`/
`AMENDEMENTS_FIGEES_INDEX_PAR_ACTEUR_FILENAME`, `candidate_profile.py`) via
`gzip.open(..., "wt")`, et `_load_frozen_amendement_index` les décompresse à
la lecture avant `_expand_aggregated_amendements_index` — `fraicheur.json`
reste en clair (quelques dizaines d'octets, aucun intérêt à le compresser).
Le fallback runtime matérialisé dans `.cache/amendements_an/` (gitignoré)
reste en clair, non compressé : seuls les fichiers committés changent de
format.

**Révision (2026-08-15, ajout de la 14e législature)** : l'affirmation
initiale (« pas de jeu de données équivalent trouvé pour les législatures
13/14 ») était inexacte pour la 14e. L'archive existe, mais pas au chemin
openData standard (`AN_AMENDEMENTS_PATH`) : elle est publiée via une page
d'archives dédiée hors du répertoire openData habituel
(`data.assemblee-nationale.fr/archives-anterieures/archives-14e/amendements`),
à un chemin distinct — `14/loi/amendements_legis_XIV/Amendements_XIV.json.zip`
(vérifié le 15/08/2026 : HTTP 200, 103 716 698 octets, Last-Modified
2018-03-21). Contrairement aux archives 15/16/17, le CDN la marque
`x-cacheable: Cacheable: force cache` (probablement du fait de sa taille,
~99 Mo, sous le seuil qui rend 15/16/17 non cacheables) — le risque
d'`IncompleteRead` en cours de flux qui a motivé toute la mécanique de
reprise/segments ci-dessus est donc structurellement plus faible pour cette
archive, sans que cela change son statut : son dossier législatif est clos
au même titre que la 15e/16e, donc figée elle aussi (`AN_AMENDEMENTS_PATH`
et `AN_AMENDEMENTS_LEGISLATURES_FIGEES` dans `candidate_profile.py`,
`_AMENDEMENTS_LEGISLATURES`/`_AMENDEMENTS_LEGISLATURES_FIGEES` dans
`check_quality_gate.py`, mis à jour en conséquence). La 13e reste sans
équivalent trouvé : ni chemin openData ni page d'archives dédiée ne répond
(vérifié le 15/08/2026).

**Révision (2026-08-15, schéma legacy de l'archive 14e législature) (#299)** :
l'archive légis 14 obtenue ci-dessus ne suit pas le schéma 15/16/17
(`_parse_amendement_entry`, un fichier JSON par amendement, racine
`{"amendement": {...}}`). Elle contient une unique entrée
(`Amendements_XIV.json`) de racine `{"textesEtAmendements": {"texteleg":
[...]}}`, chaque `texteleg` (843 au total) listant ses amendements
(`amendements.amendement[]`, 167 420 au total, singulier en dict plutôt
qu'en liste pour un `texteleg` à un seul amendement — même écueil que
`signataires.cosignataires.acteur`). `_parse_amendement_entry` retournait
`None` pour cette entrée (`data.get("amendement")` absent à la racine) :
l'index légis 14 se construisait donc silencieusement vide, sans erreur ni
warning — un défaut latent plus général que le seul cas légis 14 (tout
schéma inattendu produisait le même résultat vide silencieux).

`_parse_amendements_zip` détecte désormais le schéma de chaque entrée par
sa clé racine (`"amendement"` vs `"textesEtAmendements"`) et bascule vers
`_parse_amendement_entry_legacy` (nouveau) pour la seconde — qui aplatit
`texteleg[] -> amendements.amendement[]` et produit les mêmes clés de
sortie que `_parse_amendement_entry` (`texte_vise` porté par le `texteleg`
parent plutôt que par l'amendement individuel ; `numero` depuis
`identifiant.numeroLong`/`numero` plutôt que `identification.numeroLong` ;
`date` depuis `dateDepot` racine plutôt que `cycleDeVie.dateDepot`).
`_extract_cosignataire_refs` et la boucle auteur+cosignataires sont
réutilisées telles quelles (`signataires` est structurellement identique).
Pour `sort`/`base_juridique_irrecevabilite`, `_derive_amendement_sort_legacy`
(nouveau) reprend la même logique d'irrecevabilité que
`_derive_amendement_sort` (`etat` "Irrecevable"/"Irrecevable 40" — identique
littéralement), mais l'issue en séance n'a plus besoin d'une table
`(etat, sousEtat)` ambiguë selon le contexte : `sort.sortEnSeance` la porte
déjà sans ambiguïté, une simple table de normalisation de casse suffit
(`_LEGACY_AMENDEMENT_SORT_EN_SEANCE_MAP`). Un schéma qui n'est ni l'un ni
l'autre (`"amendement"` absent et `"textesEtAmendements"` absent) continue
de produire un index vide pour cette entrée, mais avec un warning explicite
sur `stderr` — corrige le défaut latent constaté ci-dessus au lieu de ne
traiter que le cas légis 14.

**Révision (2026-08-15, la légis 15 ne partage pas le schéma legacy de la
14e) (#301)** : la convention de nommage « fichier unique » du sous-répertoire
et du zip (`amendements_legis`/`Amendements_XV.json.zip` pour la 15e,
identique dans l'esprit à `amendements_legis_XIV`/`Amendements_XIV.json.zip`
pour la 14e, à l'inverse de `amendements_div_legis`/`Amendements.json.zip`
pour les 16e/17e) laissait supposer que la 15e partage aussi le schéma
imbriqué `textesEtAmendements.texteleg[].amendements.amendement[]` de la 14e
(#299) plutôt que le schéma par-fichier des légis 16/17. Vérifié le
15/08/2026 sans télécharger l'archive complète (648 539 281 octets,
`Last-Modified: 2022-06-09`, confirmé par `HEAD`, cohérent avec la révision
du 2026-08-13 ci-dessus) : une lecture partielle en HTTP Range
(`curl -r <offset>-<offset+N>`, contournant le même CDN instable documenté
ci-dessus — les requêtes `-H "Range: ..."` demandent une approbation
interactive indisponible en session non surveillée, `-r` non) aux offsets 0
et ~5 Mo suffit à lire plusieurs en-têtes locaux ZIP consécutifs (signature
`PK\x03\x04`, nom, méthode, tailles) sans extraire l'archive entière : les
noms d'entrée suivent le schéma
`json/<dossier>/<texteLegislatifRef>/<amendementUid>.json` (un fichier par
amendement, ex. `json/DLR5L15N36728/PRJLANR5L15B1088/AMANR5L15PO757…N000396.json`)
et chaque entrée décompressée (`zlib.decompress(..., -15)` sur les octets
compressés bruts) a pour racine `{"amendement": {...}}` — exactement le
schéma 16/17 consommé par `_parse_amendement_entry`, vérifié sur deux textes
législatifs distincts (`PRJLANR5L15B1088` en tête d'archive,
`PRJLANR5L15BTC1237` vers 5 Mo) pour exclure un schéma hétérogène au sein
même de l'archive.

**Conclusion** : la convention de nommage « fichier unique » du
sous-répertoire/zip ne prédit donc pas le schéma interne — seule la 14e
utilise réellement un fichier JSON unique agrégeant tous les amendements ;
la 15e, malgré un nommage similaire, est structurée comme les 16e/17e (un
fichier par amendement, racine `amendement`). `_parse_amendements_zip`
détecte déjà le schéma par entrée via sa clé racine (révision précédente,
2026-08-15, #299) : la 15e emprunte donc naturellement la branche
`_parse_amendement_entry` (pas `_parse_amendement_entry_legacy`) sans aucune
modification de code. Aucun travail supplémentaire requis pour #271 (le
build légis 15 peut aboutir avec le parseur existant) ; le commentaire de
`AN_AMENDEMENTS_PATH` (`candidate_profile.py`) a été corrigé pour ne plus
laisser entendre que la 15e partage le format « fichier unique » de la 14e.

**Alternatives rejetées** :
- *Committer les archives `.zip` brutes* (283-618 Mo chacune) : bloat du
  dépôt Git sans bénéfice — seul l'index dérivé, une fois dédupliqué, est
  effectivement consommé en aval.
- *Committer le `.json.gz` compressé sans dédupliquer* : évitait de toucher au
  format/à la logique de parsing, mais reposait sur un ratio de compression
  observé sur une seule législature (16) sans garantie qu'il tienne pour la
  15e (archive source ~1,8× plus grosse) — écarté au profit d'une déduplication
  structurelle, qui ne dépend d'aucune hypothèse de ratio.
- *Laisser le job CI retenter indéfiniment* : coût réseau/temps CI répété
  pour un résultat qui ne peut structurellement pas changer une fois obtenu
  une fois — pas de bénéfice, seulement un budget CI gaspillé et un signal
  de warning permanent et non actionnable pour l'équipe.
- *Étendre le seuil de péremption (`--amendements-staleness-days`) à
  l'infini pour 15/16 au lieu d'un état dédié* : aurait masqué la vraie
  distinction sémantique (« ne sera plus jamais reconstruit » vs « pas
  reconstruit récemment mais pourrait/devrait l'être ») et empêché de
  détecter un futur vrai problème si le fallback committé venait à
  disparaître ou se corrompre (l'état « jamais construit »/« périmé »
  resterait alors correctement déclenché).

**Révision (2026-08-15, la dédup seule ne suffit pas non plus + 14e
législature)** : un premier build réel complet de la législature 16 a mesuré
`index_par_acteur.json` allégé (post-`_aggregate_amendements_index`, donc
déjà `{numero, role_signataire}` par lien plutôt qu'une copie complète) à
**177 Mo en clair** — toujours au-delà de la limite GitHub de 100 Mo par
blob. La structure `{numero, role_signataire}` étant très répétitive, gzip
compresse ce fichier à **10,4 Mo** — `build_amendements_index_figees.py`
écrit donc désormais `amendements.json.gz` et `index_par_acteur.json.gz`
(constantes `AMENDEMENTS_FIGEES_AMENDEMENTS_FILENAME`/
`AMENDEMENTS_FIGEES_INDEX_PAR_ACTEUR_FILENAME`, `candidate_profile.py`) via
`gzip.open(..., "wt")`, et `_load_frozen_amendement_index` les décompresse à
la lecture avant `_expand_aggregated_amendements_index` — `fraicheur.json`
reste en clair (quelques dizaines d'octets). Le fallback runtime matérialisé
dans `.cache/amendements_an/` (gitignoré) reste en clair, non compressé :
seuls les fichiers committés changent de format.

Une **14e législature** a par ailleurs été ajoutée au même mécanisme figé
(`AN_AMENDEMENTS_PATH["14"]`, `AN_AMENDEMENTS_LEGISLATURES_FIGEES`) : son
archive (`amendements_legis_XIV/Amendements_XIV.json.zip`, ~99 Mo, marquée
`Cacheable` par le CDN AN contrairement à la 15e/16e/17e) n'est publiée que
via une page d'archives dédiée
(`data.assemblee-nationale.fr/archives-anterieures/archives-14e/amendements`),
pas via le répertoire openData standard. Elle porte surtout un **schéma JSON
différent** (« legacy ») des législatures 15/16/17 : un unique fichier JSON
pour toute la législature (`{"textesEtAmendements": {"texteleg": [...]}}`,
843 texteleg, 167 420 amendements), avec des noms de champs différents par
amendement (`dateDepot`/`numeroLong`/`etat` à la racine au lieu de
`cycleDeVie.dateDepot`/`identification.numeroLong`/
`cycleDeVie.etatDesTraitements.etat.libelle`) — un premier essai avec le
parseur existant (`_parse_amendement_entry`, qui s'attend à
`{"amendement": {...}}` par entrée de zip) a silencieusement produit un
index à 0 amendement, sans erreur.

`_parse_amendements_zip` détecte désormais le schéma au contenu (clé racine
`textesEtAmendements`) et bascule sur `_iter_legacy_amendements`
(aplatit `texteleg[].amendements.amendement`, liste ou singulier) +
`_parse_amendement_entry_legacy` (mapping des champs, réutilise telle quelle
`_derive_amendement_sort(etat, sort.sortEnSeance)` — le vocabulaire
`etat`/`sortEnSeance` de la 14e coïncide avec celui de `_AMENDEMENT_SORT_MAP`
déjà utilisée pour 15/16/17 ; `_extract_cosignataire_refs` déjà compatible
avec la forme `signataires.cosignataires` observée). Seul écart de
vocabulaire trouvé : `typeAuteur` sans accent (`"Depute"` vs `"Député"`),
ajouté comme alias dans `_AMENDEMENT_TYPE_AUTEUR_MAP`. Build réel
(103 716 698 octets) : **21 624 amendements uniques, 636 acteurs,
1 338 262 liens acteur/amendement** — committé compressé comme les autres
législatures figées (753 Ko + 3,4 Mo, largement sous la limite). La 13e
reste sans équivalent trouvé (ni chemin openData ni page d'archives dédiée
ne répond). Voir #298/#299/#300.

**Révision (2026-08-15, vérification finale de bout en bout) (#302)** :
- Quality gate section 3d (`check_quality_gate.py`) confirmée sur un run
  réel : avec `.cache/amendements_an/14/` matérialisé depuis le fallback
  committé (`_load_frozen_amendement_index("14")`), la législature 14 est
  rapportée **❄️ figé**, sans aucun avertissement de fraîcheur — même
  comportement que la 16e (déjà vérifiée sous #273).
- Pipeline exécuté sur un parlementaire réel ayant siégé sous la 14e
  législature (Laurent Wauquiez, `identite.url_an_ou_senat` ->
  `PA267285`) : `generate_all_profiles.py --source an --only
  laurent-wauquiez --pivot` fait passer son nombre d'amendements de 0 à
  **1 200** entrées (`profile["amendements"]`, toutes `"legislature": "14"`
  côté profil brut), sans régression sur `votes`/`mandats`/`interventions`/
  `dossiers_legislatifs` (fusion additive, aucune perte). Confirme la levée
  du défaut initial de l'epic (index légis 14 silencieusement vide).
- Suite de tests complète (`pytest`) : 962 tests passés, aucune régression.
- Docstrings `_parse_amendement_entry`/`_parse_amendement_entry_legacy`
  (`candidate_profile.py`) mises à jour pour se référencer mutuellement et
  nommer explicitement les deux schémas supportés.

<a id="pythonunbuffered-generate-data"></a>
## `PYTHONUNBUFFERED` global sur `generate-data.yml` : stdout fiable en CI non-TTY (#259) (2026-08-13)

**Contexte** : CPython bufferise `stdout` par blocs (pas par ligne) dès qu'il
détecte une sortie non-TTY — le cas de tout step GitHub Actions — alors que
`stderr` n'est jamais bufferisé. Les `print()` de progression (ex.
`candidate_profile.py`, `build_amendements_index.py`) apparaissaient donc en
rafale différée en fin de step dans les logs CI, avec un ordre chronologique
trompeur déjà rencontré au cours des diagnostics #239/#241/#246/#249. Risque
aggravé : en cas de kill du job par timeout/préemption runner (angle mort
déjà documenté en [[ci-cd]]), les lignes encore en buffer stdout ne sont
jamais vidées vers le log — perte pure, contrairement à `stderr`.

**Décision** : ajouter `PYTHONUNBUFFERED: "1"` au bloc `env:` global de
`generate-data.yml`, à côté de `PARLTRACK_TIMEOUT_MINUTES` (déjà hérité par
tous les jobs) — équivalent à `python3 -u` pour tout interpréteur Python
invoqué dans le workflow, sans toucher aux scripts individuels.

**Alternatives rejetées** : `flush=True` sur chaque `print()` du code source
(dizaines de sites d'appel, oubli facile à chaque nouveau `print()`) ;
`sys.stdout.reconfigure(line_buffering=True)` par point d'entrée (même
défaut de maintenance dispersée) ; flag `-u` répété sur chaque `run:` du YAML
(redondant avec la variable d'environnement globale, à répéter sur une
dizaine de lignes). Coût du changement retenu : négligeable — sortie
strictement identique, seul l'ordre d'apparition/flush change.

<a id="amendements-index-quality-gate-fraicheur"></a>
## Quality gate : distinguer un index amendements jamais construit d'un index périmé (#254) (2026-08-13)

**Contexte** : sous-issue 6/6 (dernière) du plan d'architecture #248, bloquée
par #251 ([[amendements-index-job-dedie-ci]]), #252
([[amendements-index-cache-only-consumers]]) et #253
([[amendements-index-non-regression-fraicheur]]). Clôture le fil ouvert par
#239 ([[amendements-retry-blocage-legislature]]) → #241/#242
([[amendements-range-download-legislature-isolation]]) → #245/#246
([[retry-generate-data-continue-on-error]], [[amendements-failed-legislature-marker-inter-jobs]])
→ cette issue : le quality gate n'exploitait jusqu'ici aucun des signaux déjà
construits par cette chaîne de correctifs (isolation par législature, job
dédié, indicateur de fraîcheur), alors que #253 avait explicitement laissé
« l'exploitation par le quality gate » hors périmètre pour cette sous-issue.

**Décision** :
1. Nouvelle section 3d dans `check_quality_gate.py`
   (`_report_amendements_freshness`) : pour chacune des 3 législatures de
   `AN_AMENDEMENTS_PATH` (dupliquées localement en `_AMENDEMENTS_LEGISLATURES`
   — même choix de découplage que `_AMENDEMENTS_INDISPONIBLES_PREFIX`
   existant, ce script n'importe jamais `candidate_profile.py`), lit
   `.cache/amendements_an/<legislature>/{index_par_acteur.json,fraicheur.json}`
   et distingue trois états : **jamais construit** (aucun
   `index_par_acteur.json` en cache), **périmé** (index présent mais
   `fraicheur.json` absent/illisible, ou `derniere_construction_reussie:
   false`, ou réussie il y a plus de `--amendements-staleness-days` jours) et
   **frais** (index présent, dernière tentative connue réussie et récente).
   Soft warning uniquement (n'empêche pas le commit), même traitement que le
   reste de la section 3c dont elle prolonge la numérotation.
2. **Limite assumée du signal « périmé »** : `fraicheur.json` (#253) ne
   conserve que l'issue de la *dernière tentative connue*, pas un historique —
   un échec écrase le `reussi`/`horodatage` d'un succès antérieur éventuel.
   Le quality gate ne peut donc pas calculer un véritable « nombre de jours
   sans reconstruction réussie » quand la dernière tentative a échoué ; dans
   ce cas (ainsi que fraîcheur absente/illisible), l'index est signalé périmé
   **immédiatement**, sans attendre le seuil en jours — seul le cas
   `reussi=true` applique réellement le seuil `--amendements-staleness-days`
   (défaut 7, aligné sur la granularité de cache hebdomadaire déjà tranchée
   par #249, voir
   [[amendements-index-budget-ci-cache-granularite]]). *Alternative rejetée* :
   ajouter un champ supplémentaire à `fraicheur.json` (ex. horodatage du
   dernier succès distinct de la dernière tentative) pour permettre un calcul
   exact dans tous les cas — explicitement hors périmètre de #254 (« Pas de
   nouveau mécanisme de détection au-delà du signal de péremption décrit
   ci-dessus ») : le gate consomme strictement le contrat déjà livré par
   #253, sans l'étendre.
3. Deux nouvelles options CLI : `--amendements-cache-dir` (défaut
   `.cache/amendements_an`) et `--amendements-staleness-days` (défaut 7, `0`
   désactive entièrement la section, même convention que
   `--low-syceron-coverage`).
4. `.github/workflows/generate-data.yml` (job `merge-and-pivot`, seul job qui
   exécute `check_quality_gate.py`) : ajout d'une étape `download-artifact`
   optionnelle (`continue-on-error: true`) pour `amendements-index-an` vers
   `.cache/amendements_an`, avant l'étape « Quality gate ». Nécessaire :
   contrairement à `extract-an`/`extract-roster-groupes` (qui ont déjà cette
   étape depuis #251/#252), `merge-and-pivot` ne restaurait jusqu'ici aucun
   contenu de `.cache/amendements_an` — sans cet ajout, la nouvelle section 3d
   aurait signalé les 3 législatures « jamais construites » à **chaque** run
   réel, quelle que soit leur fraîcheur réelle côté job dédié, rendant le
   signal inutilisable en production. Poussé directement dans ce commit —
   contrairement à #228/#230 (création d'un nouveau fichier sous
   `.github/workflows/`, bloquée par les permissions de l'app GitHub),
   modifier un fichier existant a fonctionné pour #237 ; à vérifier au
   prochain retour humain si ce n'est pas le cas ici.
5. `docs/an_opendata.md` : **laissé inchangé** — ce fichier documente les
   points d'accès AN Open Data (URLs, tailles d'archives), jamais la structure
   du cache local ni le contrat `fraicheur.json` ; cette issue ne change ni
   l'un ni l'autre, seulement un nouveau consommateur d'un fichier déjà livré
   par #253.
6. `AGENTS.md` §3 (diagramme pipeline Mermaid) : **laissé inchangé** — ce
   diagramme représente le flux de transformation des données (raw_data →
   pivot_data → quality gate), pas les jobs CI individuels ; le job dédié
   `extract-amendements-an` lui-même (#251) n'y figure pas, pas plus que les
   autres jobs `extract-*`. Le texte de prose au-dessus du diagramme (§3,
   ligne « Quality gate ») est en revanche mis à jour pour mentionner le
   nouveau signal.

**Tests** : `tests/test_quality_gate_amendements.py` — cache absent (3×
« jamais construit »), index frais (aucun warning), reconstruction réussie
mais au-delà du seuil (périmé), dernière tentative en échec signalée
immédiatement quel que soit l'âge, index sans `fraicheur.json` traité comme
périmé plutôt que faux-frais, états mixtes sur les 3 législatures
simultanément, et le cas `--amendements-staleness-days 0` (aucun raccourci de
désactivation interne à `_report_amendements_freshness` — c'est `main()` qui
saute l'appel sur seuil nul, la fonction elle-même applique un seuil de 0
jour littéral si on l'appelle directement).

*Alternative rejetée* : hard fail sur index périmé/jamais construit plutôt que
soft warning — rejeté, l'issue #254 demande explicitement un traitement
cohérent avec les autres signaux de la section 3c (soft warning), une
législature d'amendements indisponible n'étant pas une régression de
structure au même titre qu'un fichier groupe cassé (section 4).

<a id="amendements-index-non-regression-fraicheur"></a>
## Non-régression sur échec de reconstruction d'un index amendements + indicateur de fraîcheur (#253) (2026-08-13)

**Contexte** : sous-issue 5/6 du plan d'architecture #248, bloquée par #251
([[amendements-index-job-dedie-ci]]). Objectif : garantir qu'un échec
définitif de reconstruction d'une législature dans `_download_and_build_amendement_index`
(appelée par le job dédié `extract-amendements-an`, #251) ne peut jamais
effacer un `index_par_acteur.json` déjà en cache et fonctionnel.

**Constat** : `_download_and_build_amendement_index` (#250) n'ouvrait déjà
`index_path` en écriture qu'après succès complet du téléchargement et du
parsing — aucun chemin d'échec (`AmendementsIndexError`, raccourci
`_amendements_legislature_failed_this_run`) n'écrivait donc jamais sur un
index existant. Le seul cas où une reconstruction est réellement retentée
malgré un fichier déjà présent est un cache corrompu (`JSONDecodeError`) :
un index valide est utilisé tel quel sans nouvelle tentative (lecture en
tête de fonction). L'invariant demandé par #253 était donc déjà correct,
mais non testé explicitement ni observable par un consommateur externe.

**Décision** :
1. Tests de non-régression ajoutés (`tests/test_candidate_profile.py`) :
   succès (index remplacé), échec sur cache corrompu préexistant (fichier
   préservé à l'identique, byte pour byte), échec sans index préexistant
   (comportement inchangé, aucun fichier créé), et le raccourci
   inter-candidats/inter-jobs (`_amendements_legislature_failed_this_run`).
2. Indicateur de fraîcheur `fraicheur.json`, écrit par
   `_write_amendements_fraicheur` à côté de `index_par_acteur.json` :
   `{"derniere_construction_reussie": bool, "horodatage": str}`. Écrit à
   chaque tentative concernant un index existant ou nouvellement créé —
   succès (`reussi=True`) ou échec définitif sur un index préexistant
   conservé (`reussi=False`) ; jamais écrit si aucun index n'existe (rien à
   qualifier). Best-effort comme l'écriture de l'index lui-même (`OSError`
   avalée). Hors périmètre ici : exploitation par le quality gate
   (sous-issue 6 de #248).

*Alternative rejetée* : forcer un re-téléchargement inconditionnel à chaque
exécution du job dédié (bypasser la lecture cache-only en tête de fonction)
pour que la protection soit exercée à chaque run plutôt que seulement sur
cache corrompu — rejeté car hors périmètre de #253 (qui ne demande pas de
changer la politique de fraîcheur du cache, seulement de ne jamais régresser
sur échec) et parce que cela viderait de son sens le choix déjà tranché par
#250/#251 de ne retélécharger que si le cache est absent/corrompu.
<a id="amendements-index-cache-only-consumers"></a>
## Bascule d'`extract-an`/`extract-roster-groupes` vers la lecture cache-only des amendements (#252) (2026-08-13)

**Contexte** : sous-issue 4/6 du plan d'architecture #248, bloquée par #250
([[amendements-index-cache-only-split]]) et #251
([[amendements-index-job-dedie-ci]]). C'est ce changement qui élimine
réellement le problème documenté par #239/#245/#246 (coût réseau payé
indépendamment par chaque job) : les deux sous-issues précédentes ont préparé
le terrain (fonction cache-only isolée, job dédié qui pré-chauffe le cache)
sans changer le comportement observable des appelants.

**Décision** :
1. `fetch_amendements_officiels` (`src/candidate_profile.py`) appelle
   désormais `_read_cached_amendement_index` directement, pour chaque
   législature de `AN_AMENDEMENTS_PATH` — plus d'appel à
   `_build_acteur_amendement_index` (supprimée, devenue un pur orchestrateur
   mort une fois ce dernier appelant retiré) ni, par transitivité, à
   `_download_and_build_amendement_index` depuis ce chemin. Une législature
   absente du cache produit le warning `WARNING_PREFIX_AMENDEMENTS_INDISPONIBLES`
   existant (par législature, cf. #241/#242) au lieu d'un
   `AmendementsIndexError` intercepté — `_read_cached_amendement_index` ne
   lève jamais, elle retourne `None`.
2. `_download_and_build_amendement_index` reste inchangée et devient le seul
   point d'entrée réseau restant pour les amendements officiels, désormais
   appelée exclusivement par le job dédié `extract-amendements-an`
   (`src/build_amendements_index.py`, #251).
3. `.github/workflows/generate-data.yml` : un step `download-artifact` pour
   `amendements-index-an` (`continue-on-error: true`) doit être ajouté sur
   `extract-an` et `extract-roster-groupes`, avant leur étape d'extraction —
   en cas d'échec (artifact pas encore prêt, course sans `needs:` documentée
   dans le job `extract-amendements-an` ; ou job en échec), ces deux jobs
   s'appuient sur ce que la restauration du cache partagé `public-data-cache-an-*`
   contient déjà. **Non appliqué dans le commit associé à cette entrée** : les
   permissions de l'app GitHub utilisée par l'agent ne permettent pas de
   pousser une modification sous `.github/workflows/` — un reviewer humain
   doit appliquer ce step manuellement (voir le commentaire de la PR pour le
   YAML exact).

**Tests** : `test_fetch_amendements_officiels_never_triggers_network_when_cache_absent`
(aucun appel réseau mocké quand le cache est absent pour toutes les
législatures) et `test_fetch_amendements_officiels_returns_cached_amendements_when_index_present`
(comportement inchangé quand le cache est présent) — `tests/test_candidate_profile.py`.
Les tests existants ciblant l'ex-`_build_acteur_amendement_index` (retry,
cache d'échec mémoire/disque, isolation par législature) sont retargetés vers
`_download_and_build_amendement_index`, seule fonction restante à exercer
cette logique.

*Alternative rejetée* : garder `_build_acteur_amendement_index` comme
fonction utilitaire inutilisée « au cas où » — rejeté, code mort non justifié
une fois son unique appelant retiré (sa documentation la présentait
explicitement comme le point d'entrée réservé à `fetch_amendements_officiels`).

<a id="amendements-index-job-dedie-ci"></a>
## Job CI dédié `extract-amendements-an` : construction inconditionnelle des 3 index de législature (#251) (2026-08-13)

**Contexte** : sous-issue 3/6 du plan d'architecture #248, bloquée par #250
([[amendements-index-cache-only-split]], qui isole
`_download_and_build_amendement_index` comme point d'entrée réseau
appelable indépendamment de tout candidat). Objectif : un job CI qui
construit les 3 index de législature de `AN_AMENDEMENTS_PATH` sans
condition, pour pré-chauffer le cache partagé `.cache/amendements_an/` une
seule fois par run, au lieu de la construction paresseuse actuelle
(déclenchée seulement quand un candidat traité par `extract-an`/
`extract-roster-groupes` en a besoin).

**Décision** :
1. Nouveau point d'entrée `src/build_amendements_index.py`
   (`build_all_amendements_index()` + `main()`) : boucle sur
   `AN_AMENDEMENTS_PATH` (17/16/15), appelle
   `_download_and_build_amendement_index` pour chacune dans un `try/except
   AmendementsIndexError` isolé — un échec sur une législature n'interrompt
   pas la boucle ni ne lève d'exception non gérée, même pattern d'isolation
   que `fetch_amendements_officiels` (#241/#242). Le code de sortie du
   script (1 si au moins une législature a échoué) reste diagnosticable dans
   les logs du step CI ; c'est `continue-on-error: true` sur le job, pas ce
   script, qui empêche qu'un échec bloque le reste du pipeline.
2. Nouveau job `extract-amendements-an` dans `generate-data.yml` : mêmes
   `checkout`/`setup-python`/`pip install` que les autres jobs
   d'extraction, restauration de cache sur la clé hebdomadaire partagée
   `public-data-cache-an-<semaine ISO>` (pas de clé dédiée — déjà tranché
   par #249, voir
   [[amendements-index-budget-ci-cache-granularite]]), exécution du script,
   upload artifact `amendements-index-an` (`path: .cache/amendements_an/`).
   `continue-on-error: true` et `timeout-minutes: 30`, mêmes valeurs que
   `extract-parltrack`/déjà tranchées par #249.
3. **Pas de `needs:`** (exigence explicite de l'issue #251) : ce job tourne
   en parallèle des 4 jobs d'extraction existants et d'
   `extract-roster-groupes`, plutôt que d'être séquencé après eux comme
   `extract-roster-groupes` l'a été pour la clé de cache AN partagée
   (#222, [[concurrence-ci-roster]]). Accepté explicitement : tant que les
   jobs consommateurs (`extract-an`/`extract-roster-groupes`) continuent de
   déclencher leur propre téléchargement paresseux (bascule vers une
   lecture cache-only hors périmètre ici, sous-issue 4 de #248), une course
   sur la clé de cache partagée reste possible si un candidat sollicite une
   législature avant que ce nouveau job ait sauvegardé son cache — pas une
   régression fonctionnelle (le pire cas est un téléchargement dupliqué
   ponctuel, déjà toléré aujourd'hui en l'absence de ce job), seulement un
   gain de pré-chauffage partiel tant que la sous-issue 4 n'est pas faite.

**Tests** : `tests/test_build_amendements_index.py` — appel des 3
législatures dans l'ordre déclaré, isolation d'un échec partiel (une légis
en échec n'empêche pas les autres, pas d'exception non gérée), code de
sortie de `main()` reflétant un échec partiel ou total. Pas de test
automatisé pour le YAML CI (pattern déjà établi dans ce dépôt, cf. les jobs
existants) — validation par `workflow_dispatch` manuel réservée à
@stephieED (vérifier l'artifact `amendements-index-an` et la sauvegarde de
cache sur un run réel).

*Alternative rejetée* : séquencer ce job après les 4 jobs d'extraction
existants (`needs:`), comme `extract-roster-groupes` (#222) — éliminerait la
course décrite au point 3, mais rejeté ici car explicitement hors périmètre
de l'issue #251 (« Le job n'a pas de `needs:` sur les autres jobs
d'extraction — il tourne en parallèle », critère d'acceptation explicite) ;
à réévaluer si la course s'avère coûteuse en pratique une fois la
sous-issue 4 en place.

<a id="amendements-index-cache-only-split"></a>
## Séparer téléchargement/construction et lecture cache-only dans `_build_acteur_amendement_index` (#250) (2026-08-13)

**Contexte** : sous-issue 2/6 du plan d'architecture #248, bloquée par
[[amendements-index-budget-ci-cache-granularite]] (#249, granularité de cache
tranchée : clé hebdomadaire existante, `.cache/amendements_an/<legislature>/
index_par_acteur.json`). Préparation nécessaire avant de pouvoir déplacer la
partie réseau dans un job dédié (sous-issue 3) sans changer le comportement
des appelants existants dans cette sous-issue.

**Décision** : `_build_acteur_amendement_index` (`src/candidate_profile.py`)
scindée en deux fonctions :
1. `_read_cached_amendement_index(legislature)` — lecture seule de
   `index_par_acteur.json` s'il existe ; retourne `None` (pas `{}`, pour
   rester distinguable d'un index vide légitime déjà mis en cache) si absent
   ou corrompu. Ne déclenche jamais d'appel réseau.
2. `_download_and_build_amendement_index(legislature)` — reprend telle quelle
   la logique réseau précédemment inline (téléchargement par plages #241,
   cache d'échec mémoire+disque #239/#246, écriture de
   `index_par_acteur.json`), y compris son propre double-check du cache en
   tête (sous le même verrou par législature) pour rester thread-safe.

`_build_acteur_amendement_index` (nom conservé, seul point d'entrée utilisé
par `fetch_amendements_officiels`) devient un simple orchestrateur : essaie
`_read_cached_amendement_index`, puis retombe sur
`_download_and_build_amendement_index` si absent — comportement observable
strictement inchangé (tous les tests existants sur le téléchargement/retry/
cache d'échec/isolation par législature passent sans modification de leurs
assertions). La bascule réelle vers "jamais de téléchargement depuis ces
jobs" reste hors périmètre de cette sous-issue (sous-issue 4).

**Granularité du verrou** : les deux nouvelles fonctions acquièrent chacune
séparément `_get_amendements_lock(legislature)` (verrou non réentrant)
plutôt qu'un unique verrou tenu sur toute la section critique comme avant le
découpage. Un thread peut donc en théorie observer un cache absent via
`_read_cached_amendement_index` puis, pendant l'appel séparé à
`_download_and_build_amendement_index`, retomber sur son propre double-check
de cache (qui retrouvera le fichier si un autre thread l'a entre-temps
écrit) — pas de régression : le pire cas est un aller-retour disque
supplémentaire, jamais un téléchargement dupliqué ni une corruption.

*Alternative rejetée* : faire porter le fallback réseau par
`_read_cached_amendement_index` elle-même (une seule fonction avec un
paramètre `allow_download`) — rejeté car cela va à l'encontre de l'objectif
explicite de l'issue (deux responsabilités testables indépendamment, la
fonction cache-only devant être *structurellement* incapable de déclencher
un appel réseau, pas seulement par défaut).

<a id="amendements-index-budget-ci-cache-granularite"></a>
## Spike : budget CI pour un job dédié `extract-amendements-an` et granularité de cache (#249) (2026-08-13)

**Contexte** : sous-issue 1/6 du plan d'architecture #248, en préparation
d'un futur job dédié qui construirait les 3 index de législature (17/16/15)
sans condition (indépendamment de la liste de candidats traitée par
`extract-an`/`extract-roster-groupes`), pour pré-chauffer le cache partagé
`.cache/amendements_an/`. Spike sans code : mesurer un budget de timeout
réaliste et trancher la granularité de clé de cache, avant la conception du
job lui-même (sous-issue 3, hors périmètre ici).

**Mesures effectuées** :

1. Tailles exactes (vérifiées en direct, requêtes `Range` sur l'origine,
   13/08 11:31 UTC — affinent les approximations « 283-618 Mo » déjà
   présentes dans `docs/an_opendata.md`) :
   ```
   $ curl -sS --http1.1 -D - -o /dev/null -r 0-4194303 \
     https://data.assemblee-nationale.fr/static/openData/repository/<leg>/loi/<segment>/<fichier>
   ```
   | Législature | Content-Range total | ~MiB | Cache CDN |
   |---|---|---|---|
   | 17 | 296 735 207 o | 283,0 | `Cacheable: force cache` (rafraîchi quotidiennement, cf. `docs/an_opendata.md`) |
   | 16 | 363 306 362 o | 346,5 | `Not cacheable: too big` (confirmé, cohérent avec [[amendements-retry-blocage-legislature]]) |
   | 15 | 648 539 281 o | 618,6 | `Not cacheable: too big` |

   Total des 3 archives : 1 308 580 850 o (≈ 1,22 Gio). Le support des
   requêtes `Range` (206 + `Content-Range`) est reconfirmé sur les 3 URLs,
   cohérent avec la vérification du 13/08 07:29 UTC déjà consignée dans
   [[amendements-range-download-legislature-isolation]].

2. Reproduction, depuis l'environnement d'exécution de ce spike (bac à sable
   Claude Code — **pas** un runner GitHub Actions, chemin réseau différent
   via une passerelle egress restreinte), du comportement de retry par
   segment de `_download_amendements_zip` (script autonome réutilisant les
   mêmes constantes — `AMENDEMENTS_DOWNLOAD_CHUNK_BYTES`,
   `AMENDEMENTS_DOWNLOAD_MAX_ATTEMPTS`, `AMENDEMENTS_DOWNLOAD_BACKOFF_SECONDS`,
   `AMENDEMENTS_DOWNLOAD_READ_TIMEOUT_SECONDS` — et la même logique de
   segment/retry/`Content-Range`). Deux essais indépendants sur la
   législature 17 ont chacun atteint un échec définitif après 3 tentatives
   (`IncompleteRead`), en 20 à 68 s — bien en-deçà du plafond théorique de
   370 s (3 × 120 s de timeout de lecture + 2 × 5 s de backoff), signe que
   les échecs observés ici sont des coupures de connexion rapides plutôt que
   des blocages. Fait notable : les deux essais échouent au même offset
   cumulé exact (33 554 432 o = 32 Mio), ce qui pointe vers un plafond
   propre à la passerelle réseau du bac à sable plutôt qu'un phénomène de
   l'origine AN — **ces essais ne sont donc pas utilisés comme mesure de
   débit de référence** ; ils servent uniquement à revalider le support
   `Range`/`Content-Range` et le comportement de retry par segment sur les
   URLs réelles.
3. Aucun téléchargement complet et propre des 3 archives n'a pu être obtenu
   depuis cet environnement (plafond ci-dessus), et les logs bruts d'un run
   GitHub Actions réel n'ont pas pu être récupérés depuis ce spike (l'hôte de
   stockage des logs, `*.blob.core.windows.net`, n'est pas dans la liste
   d'autorisation réseau de cet environnement). Le budget proposé ci-dessous
   s'appuie donc principalement sur des mesures de production **déjà
   consignées dans ce fichier**, réutilisées ici comme la mesure réelle la
   plus fiable disponible :
   - Run #30 (13/08, `https://github.com/stephieED/Empreinte-politique-src/actions/runs/31685914622`) :
     un blocage réel (pas une coupure rapide) sur une législature amendements
     a consommé **6 min 48 s** avant préemption du runner — cf.
     [[amendements-failed-legislature-marker-inter-jobs]]. Cohérent avec le
     plafond théorique par législature (3 tentatives × 120 s de lecture +
     2 × 5 s de backoff = 370 s ≈ 6 min 10 s, marge de préemption/latence
     réseau incluse).
   - [[amendements-retry-blocage-legislature]] : la législature 17 (servie
     depuis le cache CDN) « se charge rapidement » en conditions saines ; les
     législatures 16/15 (toujours servies depuis l'origine, non
     cacheables) sont les seules concernées par les `IncompleteRead`
     observés en production.

**Décision — budget de timeout proposé** : **30 minutes** pour le futur job
`extract-amendements-an`, calculé comme la somme du pire cas raisonnable
couvrant les deux scénarios demandés (le job doit tenir dans les deux) :
- 2 législatures en conditions saines : 5 min chacune (marge large — aucune
  mesure de débit soutenu fiable n'a pu être obtenue depuis cet
  environnement ; valeur volontairement prudente plutôt qu'optimiste) → 10 min.
- 1 législature en échec définitif après épuisement des tentatives (scénario
  dégradé demandé par l'issue) : 6 min 48 s mesurés en production
  (arrondis à 7 min).
- Overhead fixe (checkout, `setup-python`, `pip install`, parsing en mémoire
  des zips téléchargés avec succès — dizaines à centaines de milliers de
  fichiers JSON par archive, jamais extraits sur disque) : 3 min, cohérent
  avec l'overhead de démarrage observé sur les jobs `extract-*` existants
  (~10 s hors installation) mais avec marge pour le coût CPU du parsing zip.

Total ≈ 20 min ; **30 min** retenu pour une marge ×1,5 et pour rester un
nombre rond cohérent avec les autres jobs du fichier (`generate-data.yml` :
120/90/60/30 min). Valeur **provisoire**, comme déjà pratiqué pour le
timeout de `extract-roster-groupes` dans ce même workflow (60 min
« provisoire ») : à recalibrer sur le premier run réel du job dédié
(sous-issue 3), aucune mesure de débit GitHub Actions authentique n'ayant pu
être obtenue depuis ce spike.

**Décision — granularité de clé de cache** : réutiliser la clé
hebdomadaire existante `public-data-cache-an-<semaine ISO>`, **pas** de clé
quotidienne dédiée aux amendements. Justification :
1. Les jobs AN existants (`extract-an`, `extract-roster-groupes`) partagent
   déjà un seul répertoire `.cache` et une seule clé hebdomadaire pour
   plusieurs jeux de données également documentés comme rafraîchis
   quotidiennement côté AN Open Data (acteurs actifs, dossiers législatifs —
   cf. `docs/an_opendata.md`), sans que cela ait posé de problème identifié
   dans l'historique de ce fichier. Une clé quotidienne spécifique aux
   amendements introduirait une incohérence de granularité au sein du même
   répertoire de cache sans bénéfice démontré.
2. `actions/cache` met en cache le répertoire `.cache` dans son ensemble : on
   ne peut pas donner une granularité différente à un seul sous-répertoire
   sans un `path` de cache séparé — changement de structure hors périmètre
   de ce spike (« pas d'implémentation »).
3. Seule la 17ᵉ législature est concernée par la mise à jour quotidienne ; les
   16ᵉ et 15ᵉ sont des législatures archivées dont les archives ne changeront
   plus jamais (`Last-Modified` observé : 2024-06-28 pour la 16ᵉ, 2022-06-09
   pour la 15ᵉ — vérifié en direct le 13/08). Une clé quotidienne
   multiplierait par ~7 la fréquence de re-téléchargement des 2/3 du volume
   (965 Mio sur 1,22 Gio) sans aucune justification de fraîcheur.
4. Une clé quotidienne multiplie aussi par ~7 le nombre d'entrées de cache
   distinctes sous le préfixe `public-data-cache-an-*` (partagé par tous les
   jeux AN, pas seulement les amendements), ce qui accélère la pression
   d'éviction LRU du cache GitHub Actions (limite globale par dépôt) — allant
   à l'encontre de l'objectif même du job dédié (pré-chauffer un cache
   durable).
5. Le produit (CV politiques factuels) ne porte aucune exigence de fraîcheur
   infra-hebdomadaire documentée dans `AGENTS.md` — une amende récente
   n'ayant pas encore atteint le cache n'est pas un défaut fonctionnel.

**Décision — `runs-on`** : pas de runner différent, `ubuntu-latest` standard
(cohérent avec les 5 autres jobs de `generate-data.yml`). Ces mêmes
téléchargements s'exécutent déjà aujourd'hui, sur ce runner standard, au sein
de `extract-an`/`extract-roster-groupes` (mémoire/bande passante suffisantes
en pratique) ; aucun incident de mémoire ou de CPU n'apparaît dans l'historique
d'incidents amendements de ce fichier (#185/#199/#220/#225/#239/#241/#246,
uniquement des incidents réseau). `_download_amendements_zip` écrit chaque
segment directement sur disque (jamais le zip entier en mémoire) et
`_build_acteur_amendement_index` ne lit qu'un membre du zip à la fois sans
extraction sur disque — empreinte mémoire déjà conçue pour rester modeste,
indépendamment du runner.

**Alternative rejetée** : mesurer le budget en déclenchant un run
`workflow_dispatch` réel et en lisant ses logs. Écartée pour ce spike — la
sous-issue 3 (hors périmètre ici) n'existe pas encore en tant que job
dédié isolable, et les jobs existants ne téléchargent les amendements que
paresseusement (au niveau candidat, avec cache), rendant une mesure isolée
du futur comportement « sans condition » impossible sans implémenter
d'abord le job — précisément ce que ce spike doit précéder.

<a id="amendements-failed-legislature-marker-inter-jobs"></a>
## Marqueur disque inter-jobs pour le cache d'échec amendements par législature (#246) (2026-08-13)

**Contexte** : [[amendements-retry-blocage-legislature]] (#239) mémorise en
mémoire process (`_amendements_failed_legislatures`) qu'une législature
d'amendements a définitivement échoué, pour que seul le premier candidat
rencontrant l'échec paie le cycle complet de retry. Ce cache est scopé au
process Python — or `extract-an` et `extract-roster-groupes` sont deux jobs
CI distincts (deux process), séquencés sur le même cache disque partagé
`public-data-cache-an-*` par [[concurrence-ci-roster]] (#222). Sur le run #30
(https://github.com/stephieED/Empreinte-politique-src/actions/runs/31685914622),
`extract-an` a épuisé ses tentatives dès le premier segment sur les
législatures 17/16/15 (`IncompleteRead` immédiat, aucun `index_par_acteur.json`
mis en cache) sans que `extract-roster-groupes`, quelques minutes plus tard
dans le même run, en garde aucune mémoire : son premier candidat AN a donc
retenté les trois législatures depuis zéro, cette fois en stallant réellement
jusqu'au timeout de lecture (`AMENDEMENTS_DOWNLOAD_READ_TIMEOUT_SECONDS = 120`
× `AMENDEMENTS_DOWNLOAD_MAX_ATTEMPTS = 3` ≈ 6 min), consommant l'écart de
6m48s observé avant que le job soit tué par la préemption runner déjà
documentée ([[retry-generate-data-preemption]]). Cause distincte du gap de
visibilité tracé par #245 ([[retry-generate-data-continue-on-error]]) : ici
c'est le temps de blocage lui-même qui est payé deux fois dans le même run.

**Décision** : `_build_acteur_amendement_index` écrit désormais, en plus du
cache mémoire process (#239 conservé tel quel comme raccourci intra-process),
un marqueur disque `.cache/amendements_an/<legislature>/failed_run_id`
contenant `GITHUB_RUN_ID` quand les tentatives sont épuisées pour une
législature. Avant toute tentative réseau, ce marqueur est consulté après le
cache mémoire : s'il existe et référence le `GITHUB_RUN_ID` courant, échec
immédiat identique au cache mémoire de #239 ; s'il référence un
`GITHUB_RUN_ID` différent (résidu d'une semaine ISO précédente via
`restore-keys`), il est ignoré et la législature retentée normalement —
préserve intentionnellement le comportement de #239 (un run suivant repart de
zéro) sans TTL explicite à maintenir. Le marqueur vit dans le même
sous-répertoire que `index_par_acteur.json`, donc profite du même
restore/save de cache disque déjà séquencé par #222 : aucun changement de
workflow CI nécessaire.

*Hors périmètre (reporté)* : réduire davantage
`AMENDEMENTS_DOWNLOAD_READ_TIMEOUT_SECONDS` (120s → 60s), qui réduirait le
pire cas payé par le *premier* job du run à rencontrer une législature qui
stalle réellement (ce correctif élimine la répétition entre jobs, pas le coût
initial de découverte) — proposé dans l'issue comme optionnel, à évaluer
séparément si ce coût initial redevient un problème en pratique.

<a id="retry-generate-data-continue-on-error"></a>
## Étendre `retry-generate-data.yml` aux échecs de job `continue-on-error` masqués par une conclusion de run `success` (#245) (2026-08-13)

**Contexte** : [[retry-generate-data-preemption]] (#230) détecte la
signature de préemption runner au niveau job, mais le job `detect-and-retry`
n'était invoqué que sur `github.event.workflow_run.conclusion == 'failure'`.
Run #30 (2026-08-13T09:17:33Z,
https://github.com/stephieED/Empreinte-politique-src/actions/runs/31685914622) :
`extract-roster-groupes` (`continue-on-error: true`, choix délibéré #192/#222)
a été tué par la même signature de préemption déjà documentée
([[retry-generate-data-preemption]], #217/#228/#230) — `shutdown signal` à
09:29:44, confirmé `conclusion: "failure"` via `gh api
.../jobs/94402695448` (`started_at 09:21:14`, `completed_at 10:14:16`,
message serveur différent : *"The hosted runner lost communication with the
server"*, 44 min après l'arrêt réel du job). Un job `continue-on-error` en
échec ne fait pas basculer la conclusion globale du run à `failure` : le run
#30 reste `success`, le `workflow_run` déclenché à 10:15:25Z a
`conclusion: success`, et `detect-and-retry` a donc été entièrement
`skipped` — aucune inspection de la liste des jobs, donc aucun retry, et
aucune visibilité (le run s'affiche vert ; seuls les soft warnings du
quality gate sur la couverture groupe, conformes à
[[seuil-couverture-groupe]], révèlent l'échec à qui les lit).
`extract-parltrack` (même configuration, ligne 332 de `generate-data.yml`)
est exposé au même angle mort.

**Décision** :
1. Garde du job `detect-and-retry` élargie à
   `conclusion == 'failure' || conclusion == 'success'` (exclut de fait
   `cancelled`/`skipped`, pour lesquels un retry n'a pas de sens).
2. Step de détection : nouvel output `no_job_failure`, positionné à `true`
   uniquement quand la conclusion du run est `success` **et** qu'aucun job
   de la liste n'a `conclusion == "failure"` — court-circuite la boucle de
   détection existante dans ce seul cas. Sans ce circuit dédié, élargir la
   garde du point 1 aurait fait tomber tout run 100% vert dans la branche
   « signature non reconnue » du résumé (destinée à un vrai échec
   applicatif), un faux signal sur l'immense majorité des runs qui n'ont
   simplement aucun job en échec.
3. La boucle de détection elle-même (filtrage `select(.conclusion==
   "failure")` sur la liste des jobs, puis grep `shutdown signal|The
   operation was canceled\.` sur leurs logs) n'a nécessité **aucune
   modification** : elle opère déjà au niveau job et fonctionne
   correctement dès qu'elle est atteinte — vérifié manuellement contre le
   job réel 94402695448 du run #30.
4. Step Résumé : quatrième branche dédiée à `no_job_failure == 'true'`
   (« run réussi sans échec de job — rien à signaler »), distincte des
   trois branches existantes ([[retry-generate-data-detection-impossible]]).

Portée générique, pas spécifique à `extract-roster-groupes` : le correctif
opère au niveau job (n'importe quel job en échec, `continue-on-error` ou
non), donc `extract-parltrack` en bénéficie sans changement supplémentaire.

*Hors périmètre* : retirer `continue-on-error: true` de
`extract-parltrack`/`extract-roster-groupes` — choix délibéré et correct
(#192/#222), non remis en cause par cette issue (visibilité/retry de
l'échec, pas changement de comportement). Expliquer pourquoi le nettoyage
runner a mis cette fois 44 minutes à se signaler côté serveur (`"lost
communication with the server"` vs terminaison immédiate dans les
incidents précédents) — signal d'infrastructure hors du contrôle du
workflow, cohérent avec [[verification-billing-actions]].

*Alternative rejetée* : ouvrir la garde du job sur toute conclusion
(supprimer le filtre) plutôt que de lister explicitement `failure`/
`success` — rejeté car `cancelled`/`skipped` ne doivent pas déclencher de
tentative de détection (rien à détecter, `workflow_run.id` peut même ne pas
avoir de jobs exploitables), et le lister explicitement documente
l'intention plutôt que de la laisser implicite.

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

**Complété depuis** : ce découpage suppose que le `Range` fonctionne. Quand il
ne rend plus rien — mode de défaillance observé les 18 et 19/08/2026 —, réduire
la taille de segment ne sert à rien et le repli à ajouter est le GET séquentiel.
Voir [[telechargement-an-trois-modes-defaillance]] (#443), qui étend le principe
de cette entrée du segment au flux, et corrige au passage le
`b"".join(resp.iter_content(...))` qui jetait ici les octets déjà reçus quand la
coupure survenait en cours de segment.

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

**Mise à jour (#213, onglet Gouvernement)** : `web/UI_finale` ajoute un troisième
onglet, Gouvernement, sur le modèle exact de Groupes (`GovernmentsBar`/
`GovernmentProfile`/`GovernmentProfilePage`, `buildGovernmentView` dans
`pivotAdapter.js`) — `sync-data.mjs` copie désormais aussi `pivot_data/gouvernements/`
vers `public/data/gouvernements/`. Point d'attention spécifique retenu de
`schema_gouvernement.py` (règle AGENTS.md §2.1) : `comptages.par_statut` est rendu
comme une liste de badges texte (nombres bruts, statuts à 0 omis), jamais comme une
jauge, un donut ou un pourcentage — contrairement au donut de couverture de
`GroupProfile` (qui mesure la complétude des données collectées, pas un score). Même
pattern "aucune donnée" que les groupes à faible couverture pour `textes[]` vide
(gouvernements récents) et `membres[].portefeuille` manquant.

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

Applies to the gouvernement view's `textes[]` too (confirmed in
[[gouvernement-doc-cloture]], #214): `gouvernement_textes.py` only reads the
AN dossiers-legislatifs dump, so a bill whose primary deposit chamber is the
Senate is never captured, regardless of `schema_gouvernement.py` exposing a
`"Senat"` value for `chambre_depot_initial` (reachable only via texts
deposited at the AN and later transmitted to the Senate).

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

**RÉSOLU (#382/#383, 2026-08-17) — section conservée pour l'historique.**

L'affirmation ci-dessous (« no open-data source has been identified yet »)
était **factuellement inexacte** : le même jeu de données bulk expose un
`typeOrgane == "MINISTERE"` portant l'intitulé précis (« Ministère de la
cohésion des territoires », « Secrétariat d'État auprès du ministre de la
transition écologique »), soit 52 intitulés distincts sur les profils
analysés. Il n'était simplement pas mappé. Désormais exploité — voir
[[taxonomie-mandats-typeorgane-an]], et
[[gouvernement-premier-ministre-portefeuille]] pour sa consommation par les
profils de gouvernement (#398 : le mapping de #382/#383 avait rendu l'intitulé
disponible sans que `gouvernement_profile.py` le lise).

*Constat d'origine, dépassé :* `mandats[].categorie ==
"fonction_gouvernementale"` is sourced from the AN `acteurs_historique` bulk
dataset (`organe.codeType == "GOUVERNEMENT"`), which only identifies *which*
government (e.g. "BORNE", "CASTEX") an elected official belonged to and the
dates — not the specific portfolio title (e.g. "Ministre de l'Intérieur"). No
open-data source for the precise portfolio has been identified yet.

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