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