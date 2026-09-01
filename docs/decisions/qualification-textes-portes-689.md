<a id="qualification-textes-portes-689"></a>
# Un projet de loi porté au nom du Gouvernement n'est pas une production personnelle (#689) (2026-09-01)

**Défaut en ligne.** `textes_portes[]` publiait sous un unique `role: "auteur"`
deux actes de nature différente : la **proposition de loi** qu'un·e
parlementaire dépose, et le **projet de loi** qu'un membre du Gouvernement porte
au nom de l'exécutif. Le second n'est pas un acte personnel — il engage un
gouvernement, et un bilan de gouvernement est collectif.

## Mesure de référence

Prise le 01/09/2026 sur `origin/main` (`e40d0d32`), en flux sur les 481 profils
pivot committés, croisée avec les trois archives de dossiers législatifs
(XV/XVI/XVII, 10 674 dossiers).

`textes_portes[]` publiés : **472** entrées sur les 481 profils — 423 chez les
13 candidats déclarés, 49 chez les 468 membres de roster. Ventilation
`role` × nature du texte déposé, corpus entier :

| | `projet_de_loi` | `proposition_de_loi` | `proposition_de_resolution` | nature non établie |
| --- | ---: | ---: | ---: | ---: |
| `auteur` (initiateur) | **316** | 100 | 30 | 5 |
| `rapporteur` | 2 | 3 | 1 | 0 |
| `co-rapporteur` | 8 | 1 | 0 | 6 |

Les 472 `dossier_id` publiés résolvent tous dans les trois archives : **0**
entrée non retrouvée.

Chez les 13 candidats déclarés : **313** projets de loi sur 423 entrées, portés
par trois profils — `edouard-philippe` **282** (sur 283 ; le 283ᵉ est un
engagement de responsabilité, sans nature), `gabriel-attal` **30** (sur 34),
`bruno-retailleau` **1** (sur 36). Sept profils sur treize publient des textes
portés ; **trois portent la totalité de l'anomalie**.

## Le contrôle qui a servi à découvrir le défaut n'est pas la source

Croiser la date de dépôt avec les mandats électifs donne **304 / 423** textes
déposés hors de tout mandat — la mesure de l'issue, reproduite à l'identique.
Elle est un **contrôle**, jamais une source :

| | Croisement date × mandats | Nature lue dans la source |
| --- | ---: | ---: |
| `edouard-philippe` | 282 | 282 |
| `gabriel-attal` | 22 | **30** |
| `bruno-retailleau` | 0 | **1** |
| Total candidats déclarés | 304 | **313** |

Le croisement manque les 8 textes qu'Attal a portés comme ministre alors qu'il
était encore député, et **le seul projet de loi de Retailleau** — ministre de
l'Intérieur tout en restant sénateur. Il dirait « hors mandat » là où il faut
dire « porté au nom du Gouvernement » : deux énoncés différents.

## Ce qui a été rejeté : un discriminant tiré du libellé

Chercher les intitulés commençant par « Projet de loi » trouve 13 textes chez
Attal et **zéro chez Philippe**. Les dossiers de la XVᵉ portent des intitulés
courts et descriptifs — « Bioéthique », « CETA », « Coopération avec le
Luxembourg ». **Un discriminant tiré du libellé en manque 283 sur 304.** C'est
ce que `selection-vote-sur-ensemble-672` vient de corriger ailleurs : une clé
dérivée d'un libellé rouille, et se tait en rouillant.

## Décision 1 — la nature vient du document déposé, et une seule fonction la lit

`gouvernement_textes.nature_texte_depose(dossier)` rend `projet_de_loi` /
`proposition_de_loi` / `proposition_de_resolution` / `None`, depuis le préfixe
de l'uid du document associé à l'acte `*-DEPOT` le plus ancien
(`PRJL`/`PION`/`PNRE`) — le type que l'AN encode elle-même. Repli sur
`procedureParlementaire.code` **seulement** quand aucun document n'est
résolvable, et seulement pour les codes univoques (les codes 5 et 7, « Projet
**ou** proposition de loi organique/constitutionnelle », restent exclus : #400).

C'est le champ que le dépôt lisait **déjà** pour les fiches de gouvernement
(`gouvernement-textes-initiateurs`, #435, et `_origine` depuis #400) et que
`candidate_profile._build_acteur_textes_portes_index` jetait à la collecte.
L'information n'était pas perdue à la source.

**`_origine` en dérive désormais** au lieu de relire l'archive : deux lectures
du même champ auraient fini par diverger. Le verdict est identique sur les
10 674 dossiers des trois archives, vérifié dossier à dossier avant/après. Une
proposition de résolution reste `None` côté origine — elle n'est pas un texte de
loi — mais gagne une valeur propre côté nature, où la distinction compte : une
résolution est une initiative parlementaire personnelle, et la confondre avec
« nature non établie » perdrait 31 des 472 entrées.

## Décision 2 — deux champs, dont un dérivé, qui ne peuvent pas se contredire

`textes_portes[]` gagne **`nature_texte`** (le fait sourcé) et **`role` est
scindé** (le fait dérivé) :

| Nature | `role` publié |
| --- | --- |
| `projet_de_loi` | `initiateur_projet_de_loi` |
| `proposition_de_loi` | `auteur_proposition_de_loi` |
| `proposition_de_resolution` | `auteur_proposition_de_resolution` |
| `null` | `auteur` |
| — (rôle de rapport) | `rapporteur`, `co-rapporteur`, inchangés |

**Le rôle devait changer de nom, et pas seulement gagner un champ voisin.** Un
consommateur qui lit `role` doit cesser de confondre les deux natures *par
défaut* ; un champ supplémentaire qu'il faut penser à lire ne l'y oblige pas.
`auteur` survit et sa définition **rétrécit** : « initiateur déclaré par la
source sur un dossier dont elle n'établit pas la nature » — 5 entrées publiées
(missions d'information, commissions d'enquête, déclaration du Gouvernement,
engagement de responsabilité). Il ne peut plus désigner un projet de loi.

Le rôle est **dérivé**, jamais collecté et jamais fusionné — patron de `chambres`
(#493) et de `meta.licence_donnees` (#530). Et `validate_profil` refuse toute
contradiction entre les deux champs : c'est ce qui rend la redondance sûre au
lieu d'en faire une seconde vérité, exactement comme `chambre` ne peut pas
contredire `chambres[0]`.

**Alternative rejetée — `nature_texte` seul, `role` inchangé.** Elle laisse
`auteur` couvrir les deux natures : la confusion persiste pour qui ne lit pas le
nouveau champ, c'est-à-dire pour tout consommateur écrit avant aujourd'hui.

**Alternative rejetée — scinder `role` sans publier `nature_texte`.** Un seul
champ, aucune redondance, mais deux faits de nature différente soudés dans une
valeur (ce que la personne a fait × ce qu'est le texte), et les 21 entrées de
rapport privées d'une nature que la même lecture rend gratuitement. C'est aussi
le champ dérivé qui deviendrait la seule trace du fait sourcé.

## Décision 3 — la qualification doit traverser la fusion additive

`merge_raw_profile` fusionne `dossiers_legislatifs[]` en additif pur : l'entrée
ancienne gagne. Un champ ajouté à la collecte n'aurait **jamais** atteint les
423 textes déjà collectés, et `normalize_profil` aurait republié `role:
"auteur"` indéfiniment sans qu'aucune étape n'échoue. C'est le trou de #639
(`backfill_vote_qualification`) et celui de #492 (`backfill_mandat_chambre`), au
même endroit et pour la même raison : **un filtre posé avant la fusion additive
ne filtre rien.**

`merge_profile.backfill_dossier_nature` reporte donc `nature_texte` d'une entrée
neuve sur l'entrée ancienne de même clé. Strictement croissant en information :
un seul champ nommé, jamais d'écrasement, jamais de création d'entrée, et
`_dossier_key` **inchangée** — c'est ce qui distingue ce report du défaut de
#668, où c'est la clé elle-même qui avait changé de branche.

## Décision 4 — le cache disque passe en `v3`

`index_acteur_textes_v2.json` ne porte pas `nature_texte`. Le relire
republierait « auteur » sur les 316 projets de loi du corpus, sans qu'aucune
étape n'échoue : **l'existence d'un cache n'est pas la preuve de sa
conformité**, même règle que pour le cache d'amendements (#440) et celui des
scrutins (#639).

## Décision 5 — un garde-fou qui lit le corpus publié, et qui est soft

§5c du portail de qualité : effectifs par rôle, nombre de projets de loi portés
au nom du Gouvernement, et **nombre d'initiateurs sans nature établie** — le
mètre de migration, sur le patron du warning « chambres non corroborée » de
#493. Chaque compte nomme sa population (#630), et aucun ratio n'est calculé
(§2 règle 1).

**Soft, délibérément.** La qualification n'atteint un profil qu'au run réel qui
recollecte ses dossiers législatifs ; bloquer le commit interdirait précisément
les runs censés la propager — le raisonnement de #447, cause #450. Condition de
retrait écrite : la §5c se retire quand le compteur d'attente tombe à 0 et n'y
laisse que les entrées dont la source n'établit pas la nature.

## Ce que ce lot ne fait pas

- **Aucune fiche publiée n'est requalifiée.** Au 01/09/2026 le corpus porte
  **451 initiateurs sans nature sur 472 entrées** : la §5c le dit à chaque
  exécution. Il faut un run réel de collecte des dossiers législatifs.
- **Aucune perte à déclarer.** La correction n'enlève aucune entrée, ne vide
  aucune liste et ne fait régresser aucun scalaire surveillé : `nature_texte`
  est un ajout, et `role` change de valeur — `audit_diff_profils` signale un
  changement de valeur de scalaire sans bloquer. `allow_declared_losses` n'a
  donc pas à être armé.
- **Le repli par intitulé de `web/UI_finale` survit, déclaré.** `estProjetDeLoi`
  lit `nature_texte` dès qu'il est présent, et retombe sur l'expression
  régulière sinon : le retirer aujourd'hui afficherait 0 projet de loi là où la
  page en signale 13. Sa condition de retrait est celle de la §5c.
- **Les 8 dossiers de règlement du budget** typés « Proposition de loi
  ordinaire » à la source alors que leur document est un `PRJL` (#400) restent
  arbitrés en faveur du document. Inchangé.
