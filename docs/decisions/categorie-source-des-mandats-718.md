<a id="categorie-source-des-mandats-718"></a>
# Un mandat dit quel référentiel a établi sa catégorie, et l'absence n'accuse personne (#718) (2026-09-03)

## 1. Le défaut

**12 % des mandats `categorie: "commission"` des 13 candidats déclarés n'en sont
pas** — mesuré le 02/09/2026 : 27 sur 225. La fiche candidat publie ce total
comme dénominateur, un dénominateur faux à côté d'un numérateur juste, ce que
`AGENTS.md` §2 règle 7 refuse.

**Le taux dépend de la population, et lourdement** : 12,0 % sur les 13 candidats
déclarés, **≈ 2,1 %** sur les 641 profils publiés. Les deux sont vrais ; ils ne
parlent pas du même ensemble.

## 2. Ce que l'instruction a corrigé au cadrage

L'issue supposait qu'il fallait construire un critère sourcé. **Il existait
déjà** : `candidate_profile._TYPE_ORGANE_TO_CATEGORIE` tire la catégorie du
`codeType` de l'organe AMO30 — `COMPER`/`COMNL` → `commission`, `CNPE`/`CNPS` →
`commission_enquete`, `MISINFO*`, `GE`/`GEVI`, `DELEG`… La table est explicite
jusqu'aux types volontairement non mappés, chacun avec sa raison.

Le défaut n'est donc pas une catégorie dérivée d'un libellé : c'est du **résidu
hérité de NosDéputés**, que la fusion additive conserve (`mandats` est additive,
l'ancienne entrée gagne, §3a).

L'issue rangeait les écarts en trois natures. La mesure sur le corpus en montre
une **quatrième, majoritaire** : des mandats **réels** — groupes d'études,
commissions d'enquête, délégations, `Bureau de l'assemblée nationale` — que
NosDéputés aplatissait sous `commission` et que l'AN nomme autrement, si bien que
`purge_mandats_dupliques.py` (#387) ne peut pas les apparier. Leur signature est
nette : un `type` en minuscules (`membre`, `vice-président`, `rapporteur`) là où
AMO30 rend le `libQualite` capitalisé (`Membre`).

**Ce ne sont pas des déchets.** Les supprimer perdrait un mandat réel que le
référentiel n'expose pas sous ce nom — le faux positif que la règle de prudence
de #387 existe pour éviter, et qui est irréversible hors git.

## 3. La décision : marquer, jamais supprimer ni accuser

`mandats[].categorie_source` — vocabulaire fermé `KNOWN_CATEGORIE_SOURCES`,
**clé facultative** :

| Valeur | Ce qu'elle dit |
| --- | --- |
| `an` | la catégorie vient du `codeType` de l'organe AMO30, ou des deux chemins qui lisent la même archive (`mandat_electif`, `groupe_politique`/`fonction_gouvernementale`) |
| `europarl` | la catégorie vient du Parlement européen |
| *clé absente* | **personne ne l'a établie** |

**Il n'existe aucune valeur « héritée », et c'est l'arbitrage du lot.** Une
entrée que la collecte neuve ne rend pas reste **sans clé** : « personne ne l'a
établie », jamais « sa catégorie est fausse ». La nuance est celle que #486 a
payée — 29 des 511 `mandat_electif` publiés sont des entrées que la source ne
sert plus, et les accuser aurait été un fait faux de plus.

**`None` n'est pas licite non plus.** Il dirait la même chose que l'absence sous
la forme d'un constat, et le constat n'a pas été fait (§2 règle 5). Même
arbitrage que `interventions[].collecte` (#657), dont l'absence est la forme
pleine.

## 4. Le report nommé, aux DEUX étages

**Sixième occurrence de la même famille** — #492 (`mandats[].chambre`), #639
(`votes[]`), #641 (`identite.profession`), #696 (`texte_vise`), #710
(`interventions[].sujet`) : un champ ajouté au schéma n'atteint jamais une entrée
déjà collectée tout seul, et le remède est un report **nommé**, jamais une fusion
plus permissive. Ni `_mandat_key` ni `_pivot_mandat_key` ne contiennent le
nouveau champ, donc l'entrée neuve estampillée porte la même clé que l'ancienne
et serait écartée à chaque régénération.

`backfill_mandat_categorie_source` est câblé **au brut et au pivot**. L'oublier
au pivot aurait laissé le champ arriver dans le profil brut sans jamais atteindre
la couche que `web/` lit — un correctif vrai et sans effet. Le trou a été trouvé
par un test du lot, pas par relecture.

Le report est strictement monotone : il ne remplit qu'un champ absent, n'écrase
jamais une estampille posée, ne touche aucun autre champ et ne réordonne rien.

## 5. L'effet, simulé et non encore observé

Simulé le 03/09/2026 contre l'index AMO30 en cache, sur les **468 profils** qui
ont une correspondance relue *et* des mandats AMO30 :

| Mesure | Estampillés | Sans estampille |
| --- | ---: | ---: |
| Mandats catégoriels | 38 809 | **640** (1,6 %) |
| dont `categorie: "commission"` | 11 308 | **467** (4,0 %) |

**33 profils** verraient leur nombre d'**entrées** `commission` baisser, et la
baisse est concentrée : `eric-poulliat` 65 → 27, `emilie-chandler` 61 → 24,
`sabrina-agresti-roubache` 38 → 4.

**Ce sont des entrées, pas ce que le lecteur voit.** Depuis #731 le bloc affiche
un nombre d'**intitulés distincts** et mesure une **durée**, pas un compte
d'entrées : retirer l'entrée `Gouvernement` de `gabriel-attal` fait passer son
bloc de 14 à 13 intitulés, pas de 67 à 66. Un résidu ne change donc l'écran que
s'il introduit un intitulé que rien d'autre ne porte, ou s'il ouvre un intervalle
hors des autres. L'ampleur à l'écran reste **à mesurer sur les intitulés**, et
elle revient à qui tient la vue. Vérifié sur `eric-poulliat` : ses 38 entrées
non estampillées portent toutes la signature NosDéputés (`type` en minuscules,
libellés d'organe que l'AN nomme autrement) et sont, pour l'essentiel, des
**groupes d'études** rangés sous `commission`.

**Ce sont des chiffres simulés.** L'estampille n'existera dans le corpus qu'après
un run qui recollecte, et le report ne peut rien pour une entrée qu'aucun run ne
rend.

## 6. Ce que le lot ne fait pas

- **Il ne touche pas la vue.** L'étape « le bloc ne compte que les entrées
  établies » vit dans `web/UI_finale/src/utils/profilCandidat.js`, qu'une autre
  session tient. Tant qu'elle n'est pas faite, le champ est publié et personne ne
  le lit. **Et l'estampille n'existera dans le corpus qu'après un run qui
  recollecte** : aujourd'hui aucun profil publié ne la porte, donc un filtre sur
  `categorie_source === "an"` viderait les blocs. Le filtre devra se comporter
  comme aujourd'hui sur un corpus sans estampille, et le déclarer.
- **Il ne corrige aucune catégorie fausse.** Une entrée sans estampille reste
  mal catégorisée ; elle est seulement reconnaissable. Ce qui la corrigerait
  serait un appariement AN ↔ NosDéputés par organe, que #387 a instruit et
  écarté (les deux référentiels ne nomment pas les organes de la même façon).
  C'est aussi ce qui distingue ce lot de **#729** (le même organe sous deux
  catégories, 542 mandats) et **#730** (8 mandats ministériels publiés en
  `commission`), qui portent sur des catégories **fausses** et restent ouvertes.
- **Il ne retire pas les 5 intitulés de navigation** (`Amendements`,
  `Interventions`, `Questions`, `Vidéos`, `Loi ou de résolution`, tous sur
  `jean-luc-melenchon`, 6 entrées dans le corpus). Ils cesseront d'être comptés
  faute d'estampille, mais ils resteront publiés.

## 7. Condition de retrait

Le champ disparaît le jour où aucune entrée sans estampille ne subsiste dans le
corpus — c'est-à-dire quand tout mandat publié est qualifié par un référentiel.
Sans cette condition écrite, un transitoire devient permanent, le travers que
`AGENTS.md` nomme pour `chambre` (#493) et pour les replis de #431/#432.

## 8. Vérification

`tests/test_categorie_source_mandats_718.py` — 15 tests : le vocabulaire fermé,
la clé absente licite, `None` refusé, un référentiel inventé refusé, le report
aux deux étages, l'entrée orpheline qui **reste sans clé**, le câblage réel dans
la fusion, et la traversée vers le pivot en clé facultative.

Trois mutations vérifiées échouantes : le report décâblé du brut, un `"heritee"`
écrit par défaut, la validation du vocabulaire retirée.

Suite complète : **3 709 tests, 0 échec**.
