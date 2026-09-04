# Une fonction exercée ne l'est pas toujours au Parlement (#328) — 04/09/2026

« Les fonctions exercées » ne montrait que sept catégories, toutes
parlementaires. Un portefeuille ministériel est pourtant un siège occupé — un
intitulé, des dates, une durée, exactement ce que la section mesure — et
**6 des 13 candidats déclarés en ont exercé un** (65 des 641 profils publiés).
La section n'en montrait donc qu'une moitié.

## 1. Trois natures sous une seule catégorie, séparées par un champ sourcé

`categorie: "fonction_gouvernementale"` couvre trois choses que le champ
`fonction` distingue déjà — c'est le discriminant qu'`appartenancesGouvernementales`
utilise depuis toujours :

| `fonction` | Ce que c'est | Où ça va |
| --- | --- | --- |
| `membre` | l'**appartenance** au gouvernement (`Gouvernement (BORNE)`) | nulle part ici : c'est l'enveloppe, et la frise en fait une piste |
| `en mission` | un⋅e **parlementaire en mission** auprès d'un ministère | son propre bloc |
| le reste | le **portefeuille** (Ministre, Secrétaire d'État, Premier ministre) | le bloc « Portefeuilles ministériels » |

**L'enveloppe est exclue, et ce n'est pas un oubli.** Publier
`Gouvernement (BORNE)` à côté de `Ministère de l'éducation nationale` doublerait
chaque portefeuille d'une ligne qui ne dit pas ce qu'on y faisait — mesuré :
17 enveloppes pour 18 portefeuilles sur les 7 profils concernés.

**Le filtre porte sur `fonction`, jamais sur le libellé.** Reconnaître
« Gouvernement (… ) » dans l'intitulé aurait été une jointure par ressemblance
de chaîne, ce que [`regrouper-nest-pas-joindre-639`](regrouper-nest-pas-joindre-639.md)
interdit.

**La mission n'est pas un ministère.** Un⋅e parlementaire en mission auprès d'un
ministère reste parlementaire : la frise lui donne sa propre piste, et la ranger
avec les ministres serait le contresens que la frise évite déjà. Jérôme Guedj en
a deux, et aucun portefeuille.

## 2. La marque ne s'applique pas aux blocs gouvernementaux

Le filet de la section marque la fonction qui dépasse **la moitié du temps de
mandat électif**. Un portefeuille ne se compare pas à ce tout : Édouard Philippe
a été Premier ministre trois ans **sans siéger**. La marque aurait affirmé
« plus de la moitié » d'un dénominateur dont il était absent — un ratio publié
sans son dénominateur, ce que §2 règle 7 refuse.

Les deux blocs portent donc `sansMarque`, et c'est la seule exception : le reste
de la règle est inchangé.

## 3. La couleur dit le BANC, pas la catégorie

Chaque bloc porte un filet et une pastille : bleu pour l'Assemblée, bronze pour
le gouvernement, **contour tireté** pour la mission. Ce sont les trois pistes de
la frise, sans une teinte de plus.

Une teinte par catégorie aurait demandé **neuf** couleurs, en concurrence avec
la seule grammaire de couleurs de la fiche — et sur un profil qui a connu les
deux bancs, c'est le banc qu'on aurait perdu. Ce qui sépare une commission d'un
groupe d'amitié est écrit en toutes lettres au-dessus de chaque bloc : **la
couleur double l'intitulé, elle ne le remplace pas**, et la mission se distingue
aussi par la forme du filet — la section se lit en niveaux de gris.

## 4. Les deux teintes sont désormais déclarées une seule fois

Elles étaient écrites en littéral à **cinq** endroits — la frise, les colonnes
d'« En bref », deux pastilles de position, la marque de projet de loi — au point
qu'un test existait pour vérifier que deux d'entre elles n'avaient pas divergé.

**Une valeur qu'un test doit surveiller pour rester unique est une valeur qui
n'aurait pas dû être copiée.** Elles vivent sur `.cp-main`, et tous leurs
lecteurs les lisent. `test_les_colonnes_prennent_la_teinte_de_la_frise` devient
`test_la_teinte_d_un_banc_est_declaree_une_seule_fois` : il vérifiait que deux
copies coïncidaient, il vérifie qu'il n'y en a plus qu'une. Même leçon que
[`teintes-des-stades-en-bref-328`](teintes-des-stades-en-bref-328.md), un cran
plus haut.

## Alternatives écartées

| Écartée | Pourquoi |
| --- | --- |
| Publier l'appartenance (`Gouvernement (BORNE)`) comme une fonction | Elle ne dit pas ce qu'on y faisait, et double chaque portefeuille |
| Ranger la mission avec les portefeuilles | Un⋅e parlementaire en mission reste parlementaire — la frise le sait déjà |
| Une teinte par catégorie de fonction | Neuf teintes en concurrence avec le code du banc ; sur un profil bicaméral de fait, c'est le banc qu'on perd |
| Une forme de marqueur par catégorie | Demandait d'inventer un vocabulaire de formes qu'il aurait fallu expliquer en légende |
| Appliquer la marque aux portefeuilles | Le dénominateur est le mandat électif ; Philippe a gouverné trois ans sans siéger |

## Ce qui n'est pas vérifié

- **Aucun harnais JS.** Les 8 tests ajoutés lisent le code exécuté,
  commentaires retirés ; **six mutations** ont été vérifiées échouantes. Ils ne
  couvrent ni le rendu, ni le contraste, ni le parcours clavier.
- Le rendu a été relu **sur les 7 profils publiés qui portent une fonction
  gouvernementale**, rendus par les composants de l'application.
- **Ce lot ne touche pas la section « Les gouvernements dont il a été membre ».**
  Elle continue de publier l'appartenance sous une autre forme : la
  restructuration qui la retire est un lot à part, décidé mais non implémenté.
