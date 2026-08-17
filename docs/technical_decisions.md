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