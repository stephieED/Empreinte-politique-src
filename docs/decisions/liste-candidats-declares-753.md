# La liste des candidats se collecte, et un déclaré entre sans slug (#753)

`2026-09-07`

## Contexte

`raw_data/candidats.json` décide de **qui reçoit une fiche** : il dimensionne la
matrice `extract-an` (un shard par candidat à slug résolvable) et porte la
première passe pivot de `merge-and-pivot`. Il était tenu **à la main**, et sa
`_meta.derniere_verification` valait `2026-07-18` — **51 jours** au 07/09/2026.

Mesuré ce jour-là contre l'article Wikipédia des candidatures :

| Population | Nombre |
| --- | --- |
| « Candidats déclarés », tableau principal | **19** |
| Déclarés dans le cadre d'une primaire (gauche unitaire, PS, autres) | **11** |
| `raw_data/candidats.json` | **13**, dont **11** communs |
| **Déclarés absents de notre fichier** | **19** |
| **Entrées de notre fichier qui ne sont plus déclarées** | **2** |

Les deux entrées périmées sont sourcées : **Laurent Wauquiez** (`statut:
declare`) et **Jordan Bardella** (`statut: pressenti`) figurent tous deux sous
« Candidats pressentis ayant décliné », le premier en soutien à Bruno
Retailleau, le second à Marine Le Pen.

### Le garde-fou existait, et il ne gardait rien

`src/fetch_wikipedia_candidates.py` (356 lignes) n'était appelé par **aucun
workflow**, n'avait **aucun test** ni fichier de décision. Exécuté le
07/09/2026, il rapportait 13 « candidats », dont **aucun n'était une personne** :
« nationalité française », « droits civiques », « parrainages », « Conseil
constitutionnel ». Trois défauts indépendants, tous vérifiés :

1. **il visait le mauvais article.** La liste ne vit pas dans « Élection
   présidentielle française de 2027 », qui ne fait que la transclure, mais dans
   « Candidatures à l'élection présidentielle française de 2027 » ;
2. **sa regex de titre attrapait « Conditions de candidature »** — un titre qui
   contient « candidat » — et en ramassait les puces ;
3. **sa requête Wikidata ne pouvait pas aboutir** : elle imposait
   `?election wdt:P31 wd:Q869519`, quand l'élément de l'élection 2027
   (`Q111594692`) porte `Q890055` et `Q114775014`.

Et **il sortait en 0 sur un échec réseau total**, en affichant « ✓ Aucun nouveau
candidat détecté en ligne » : une collecte vide rendue comme un résultat, le
patron exact de #511.

## Décision

Un script neuf, `src/fetch_candidats_declares.py`, qui **collecte les déclarés
et écrit** `raw_data/candidats.json`. L'ancien est retiré.

### Le périmètre : tout candidat déclaré, sans filtre

« A déclaré sa candidature » est un fait, sourçable ligne à ligne. Tout autre
critère — notoriété, score attendu, taille du parti — reviendrait à arbitrer qui
mérite une fiche, ce que la §2 règle 1 interdit. Les sous-sections de primaire
sont dedans : la source en fait des sous-sections de « Candidats déclarés ».

### Le HTML rendu, et non le wikitext

Les primaires sont **transcluses** (`{{#section-h:}}`) depuis d'autres articles.
Lire le wikitext du seul article dédié perd Mélenchon, Tondelier, Guedj et
Royal — quatre personnes que nous publions déjà. `action=parse&prop=text`
développe les transclusions ; c'est la seule raison pour laquelle ce script
parle HTML.

### Le nom se lit dans le texte de la cellule, jamais dans son premier lien

Deux déclarés n'ont pas d'article Wikipédia — **Selma Labib**, **Benoît
Mathieu** — et leur premier lien est donc celui du parti. Une extraction par
lien publie « Nouveau Parti anticapitaliste » comme nom de candidate. La cellule
d'en-tête est un empilement `<br>` (nom, âge, parti) dont trois parasites sont
retirés avant lecture : la clé de tri de `{{TriNom}}`
(`<span style="display:none">`), l'âge (`<span class="datasortkey">`) et les
appels de note (`<sup class="reference">`, trois sur la seule ligne Fabien
Roussel).

### Trois anomalies bloquent l'écriture, aucune n'est un seuil

Le patron de `generate_roster_candidats.py`, pour la raison de #511 :

1. **la page n'a pas pu être lue** — réseau, HTTP, JSON illisible, erreur d'API.
   L'exception voyage jusqu'au message (#524) : « en échec » ne dit pas s'il faut
   relancer ou corriger le code ;
2. **la section « Candidats déclarés » est introuvable** — un titre qui bouge ne
   doit pas se lire comme une liste vide ;
3. **zéro candidat extrait** alors que la section existe.

Une ligne dont le nom ne se laisse pas lire ne bloque **pas** : elle est comptée
et nommée (`CANDIDATS_LIGNE_ILLISIBLE`), comme `ROSTER_SANS_SLUG` le fait des
membres sans slug (#527). Une ligne **d'en-tête de colonnes** n'en est pas une :
elle se reconnaît à sa structure (que des `th`, aucun `td`) et non à son libellé,
ce qui évite quatre avertissements par run — un avertissement qu'on apprend à
ignorer est un avertissement perdu.

### Un nouveau candidat entre avec `slug: null`

C'est le point qui décide de tout le reste. Fabriquer le slug ferait entrer le
candidat dans la matrice `extract-an`, donc dans la collecte, donc dans la
publication — et la **§5b du portail qualité est un hard fail à seuil 0** sur
tout profil publié sans correspondance slug ↔ acteur AN relue (#525). Dix-neuf
slugs fabriqués, c'est dix-neuf runs bloqués jusqu'à ce qu'une main écrive dix-neuf
entrées de correspondance.

`slug: null` est exactement l'inverse : `prepare-an-matrix` ne retient que les
slugs résolvables, donc pas de shard, pas de collecte, pas de publication, pas
de §5b. La relectrice mint le slug **quand** elle a vérifié la correspondance.
L'état d'attente n'est pas une invention de ce lot : c'est la sémantique que le
pipeline porte déjà.

`famille_politique` et `date_declaration` restent `null` : le tableau des
déclarés ne les porte pas, et une absence se publie en absence (§2 règle 5).

### Une entrée qui n'est plus déclarée est signalée, jamais modifiée

Le script lit la **section des déclarés**. Il ne peut donc pas distinguer un
retrait d'une candidature déclinée ni d'un simple déplacement de section :
trancher à sa place serait inventer une cause. Il annote (`::warning::`), il
n'écrit pas. Et il ne supprime jamais — un `slug` publié est immuable
(#460/#470).

## Ce que la décision ne fait pas

**Wikidata sort du dispositif.** Corrigée de sa classe d'élection, la requête
`?p wdt:P3602 wd:Q111594692` rend **1** personne (Clara Egger), absente de notre
fichier : la propriété n'est pas peuplée pour 2027. Une source qui rend 1 sur 30
n'est pas une source de repli, c'est un faux témoin.

**La liste officielle n'existe pas encore, et ce lot ne la prépare pas.** Le
Conseil constitutionnel est seul compétent et n'émet rien avant l'ouverture du
recueil des présentations. `data.gouv.fr` rendait **0** jeu de données
« présidentielle 2027 » au 07/09/2026 ; le CC y publie bien 2017 et 2022
(organisation « Conseil constitutionnel », licence `other-pd`, JSON/CSV/XLSX,
rafraîchis 2×/semaine pendant le recueil), puis la décision « PDR » arrêtant la
liste au JO — précédent 2022 : décision n° 2022-187 PDR du 7 mars 2022. La liste
passe donc par **trois régimes** — déclaratif (aujourd'hui), parrainages
(~janv-févr 2027), officiel (~mars 2027) — et `statut` porte déjà les trois
valeurs. Écrire aujourd'hui l'adaptateur officiel serait écrire contre une forme
que personne n'a vue : c'est ce que #726 nomme *une fixture qui décrit le monde
tel que le code l'imagine*.

**Le script n'est branché dans aucun workflow.** Il s'exécute à la main, et
`--echouer-si-ecart` existe pour le jour où un job le lancera en tête de run.
Le brancher demande d'abord de trancher où la mise à jour est **commitée** : le
garde-fou `GENERATION_CODE_CHANGED_DURING_RUN` de `merge-and-pivot` annule le
commit si `raw_data/*.json` a bougé sur la branche pendant le run.

**Un effet de bord est déclaré et non corrigé** : `parti_profile.py` groupe
**toutes** les entrées de `candidats.json` par leur champ `parti` et écrit un
`pivot_data/partis/parti-<slug>.json` par label. Les 19 entrées neuves y
créeront donc des fiches de parti à `nb_candidats_avec_pivot: 0` — un compteur
déclaré, sur une sortie qu'aucun onglet de `web/UI_finale` n'affiche.

## Alternative écartée

**Réparer `fetch_wikipedia_candidates.py`.** Les trois défauts sont
indépendants et touchent la cible, l'extraction et la requête — c'est-à-dire
tout le fichier sauf son CLI. Et son contrat change : il promettait de **ne
jamais écrire**, ce que sa ligne de `docs/commandes.md` disait en gras. Garder
le nom d'un script qui fait l'inverse de ce qui est écrit de lui coûte plus
qu'un fichier neuf.

**Fabriquer le slug à l'entrée, et laisser la §5b faire barrage.** C'est ce que
fait `an_roster.resoudre_slugs` pour les membres de roster (#708), et ça marche
là-bas parce que le portail bloque la **publication** d'un profil, pas le run.
Ici, les profils seraient collectés puis publiés dans la foulée : le premier run
échouerait, dix-neuf fois.
