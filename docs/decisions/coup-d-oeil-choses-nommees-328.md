<a id="coup-d-oeil-choses-nommees-328"></a>
# Le coup d'œil publie des choses nommées, pas la forme d'une distribution (#328, 01/09/2026)

**Contexte.** Le bloc qui ouvre la fiche d'un candidat déclaré — livré par #684,
`CandidateProfile.jsx` + `utils/profilCandidat.js` — affichait « cinq traces
indépendantes, une même matière ». Sept retours de la propriétaire, un seul lot :
tous portent sur ce bloc, aucun sur le reste de la page.

Deux de ses cinq lignes étaient des **statistiques de distribution** :

> 6 dossiers sur 34 concentrent 2 206 de ses 2 429 amendements

*« C'est difficile de comprendre ce que ce chiffre implique, je ne suis pas sûr
de ce que l'électeur pourra en faire. »* Elle a raison, et le défaut est de
nature, pas de rédaction : un ratio de concentration décrit la **forme** d'une
distribution, jamais ce sur quoi la personne travaille. Aucune reformulation ne
le convertit en quelque chose dont un lecteur fait quelque chose.

## Décision

Le bloc s'appelle **« Coup d'œil »** et publie **cinq points au plus**, chacun
tenu par trois obligations.

### 1. Chaque point nomme une chose

La substance est dans la liste, pas dans le ratio. Le point « amendements »
n'affiche plus combien de dossiers concentrent combien de dépôts : il affiche
**les dossiers, nommés**, avec leur compte, le premier sur la ligne de tête et
les deux suivants derrière. `agregerAmendements` rend donc `dossiers`
(`rattaches`, `distincts`, `nommes`, `distinctsNommes`, `depotsNommes`) là où
elle rendait `concentration` ; `SEUIL_CONCENTRATION` est **supprimée**, avec la
note qui la défendait.

**Un dossier n'est nommable que si la source le nomme**, par deux chemins et pas
un troisième :

| Chemin | Cas | Mesure au SHA `e40d0d3` |
| --- | --- | ---: |
| `textes[texte_vise].titre` de l'index par législature | le cas normal | l'essentiel des législatures 15-17 |
| le `texte_vise` lui-même quand ce n'est **pas** une référence de source | l'index publie parfois l'intitulé en clair à cette place | **2 458 des 2 831** dépôts de Jean-Luc Mélenchon, visés par « Système universel de retraite », qui n'est la clé d'aucune entrée `textes` |
| la référence brute (`PRJLANR5L14B1395`) | **jamais** | — |

Le critère de distinction est **structurel** : une référence de source ne
contient pas d'espace, un intitulé en contient toujours (`nomDeDossier`).

Ce que ça laisse à découvert est mesuré et **dit**, jamais comblé : l'index de la
XIV<sup>e</sup> législature n'a **qu'une** entrée `textes`, donc aucun des 12
dossiers de Xavier Bertrand ni aucun des 3 d'Édouard Philippe n'est nommable.
Leur point affiche le nombre de dépôts et la phrase « qu'aucune entrée d'index ne
nomme » — pas un identifiant à la place d'un texte (§2 règle 5).

### 2. Chaque point porte sa propre couverture, et son dénominateur est de la même population que son numérateur

C'est le défaut le plus grave trouvé, et il était **arithmétique** : le point
« questions au gouvernement » divisait le compte du premier sujet par **toutes**
les questions, y compris celles dont aucun sujet n'est publié. Tant que la
couverture est totale le ratio est juste par accident ; dès qu'elle ne l'est
plus, il est faux. Le dénominateur devient `questions.avecSujet`, et
`directionQuestionsGouvernement` expose `avecSujet` et `sujetsDistincts`
**comptés sur l'ensemble**, jamais sur la tranche de douze qu'elle affiche.

Même correction sur la qualité d'orateur (dénominateur `sourcees`, pas `total`)
et sur les amendements (dénominateur `depotsNommes` quand un dossier est nommé).

**Aucune caractérisation littéraire de la dispersion.** Écrire « sujets très
divers » ou « très ciblés » décrirait **notre collecte** en croyant décrire son
travail. Les nombres suffisent et ne mentent pas : 9 questions sur 250 pour
« Situation du CHU de Grenoble », 154 sujets distincts (Mélenchon) se lisent
autrement que 28 sur 215 pour « Réforme des retraites », 102 sujets distincts
(Guedj) — sans qu'un adjectif s'interpose.

Quand aucun sujet n'est publié, le point ne nomme rien et **dit pourquoi** : « la
source ne dit pas sur quoi elles portaient, et la page ne le devine pas ». Cette
branche n'est **pas exercée par le corpus actuel** (voir la mesure ci-dessous) et
c'est déclaré ici plutôt que présenté comme vérifié.

### 3. Une note met en garde, ou elle disparaît

La frontière est celle de la propriétaire : *« tu dis au lecteur des consignes
éditoriales qui ne lui apportent pas d'information — c'est pour nous, ce sont des
notes »*. Une note qui prévient un **contresens de lecture** est une information
et se garde (`garde`, marquée d'un filet jaune) ; une note qui justifie **notre
méthode** ne sert qu'à nous et se retire.

| Note | Sort | Motif |
| --- | --- | --- |
| « Ces mesures sont indépendantes… Empreinte politique ne classe pas les textes par sujet — c'est le lecteur qui lit la convergence » | **retirée** | son exemple même : elle justifie notre méthode |
| « « 6 » est le plus petit nombre de dossiers atteignant 90 % de ses dépôts » | **retirée** | méthode — partie avec la mesure |
| « la distinction se lit dans l'intitulé officiel, aucun champ ne la porte » | **retirée** | méthode |
| « dénombré sur les interventions dont le compte rendu indique le point de l'ordre du jour » | **remplacée** par le chiffre de couverture | une règle devient un fait |
| « questions reçues depuis le banc du gouvernement, pas des questions posées » | **gardée** | sans elle, les 743 questions de Gabriel Attal se lisent à l'envers |
| « dont 13 projets de loi — des textes du gouvernement signés comme ministre » | **gardée** | la source range projet et proposition sous le même `role: auteur` |
| « qualité publiée par la source » | **gardée** | provenance, §2 règle 2 |

## Le cadre parlementaire ne vaut pas pour un ministre — et la trame ne se dédouble pas

*« C'est très focus sur le travail parlementaire, le travail exécutif semble un
peu moins bien calé. »* Le cadre « ce qu'on fait quand on choisit » est
parlementaire **par construction** : un ministre ne réagit pas à l'ordre du jour,
il le fixe, et une question au gouvernement lui est *posée*.

**Deux gabarits sont refusés** : la trame vaut pour les treize, et une fiche dont
la forme change avec la carrière ne se compare plus. Ce qui s'adapte est **la
seule phrase d'introduction**, et son déclencheur est un **fait collecté** :
avoir été *membre* d'un gouvernement (`appartenancesGouvernementales`, la même
fonction que le reste de la page — un parlementaire en mission n'en est pas un,
ce qui écarte correctement les deux mandats « en mission » de Jérôme Guedj).
**6 des 13** candidats déclarés portent la phrase : Retailleau, Philippe, Attal,
Wauquiez, Royal, Bertrand.

Elle est publiée telle quelle, sous la thèse :

> Au gouvernement, ce partage ne tient plus : l'ordre du jour s'y fixe au lieu de
> s'y subir, et une question au gouvernement s'y reçoit au lieu de s'y poser.

Les **points**, eux, ne changent pas : mêmes champs, même ordre, mêmes règles.
Ils portent déjà la différence là où elle est vraie — la direction des questions
(`sens`), les projets de loi, la qualité ministérielle. C'est la trame qui
uniformise les emplacements, jamais leur remplissage.

## Ce qui a été mesuré, et ce qui ne se reproduit pas

Mesuré au SHA `e40d0d3`, le 01/09/2026, sur les **13 profils
`candidat_declare`** — jamais sur les 481, qui mélangeraient deux populations
(#630). Le run `generate-data.yml` en cours réécrivant `pivot_data/`, tout a été
lu par `git show <SHA>:…`, jamais sur le disque.

**La mesure qui motivait le retour n° 3 ne se reproduit plus.** Elle donnait, au
01/09 au matin, une couverture des sujets de questions de 4 % pour Mélenchon
(11 sur 249), 70 % pour Attal, 84 % pour Le Pen. Re-mesurée :

| Profil | Questions posées ou reçues | Avec un sujet publié | Couverture | Premier sujet | Sujets distincts |
| --- | ---: | ---: | ---: | ---: | ---: |
| Édouard Philippe | 1 781 | 1 781 | 100 % | 173 | 252 |
| Gabriel Attal | 743 | 743 | 100 % | 41 | 148 |
| Bruno Retailleau | 234 | 234 | 100 % | 14 | 46 |
| Jean-Luc Mélenchon | 250 | 250 | **100 %** | **9** | **154** |
| Marine Le Pen | 214 | 214 | 100 % | 12 | 103 |
| Jérôme Guedj | 215 | 215 | 100 % | 28 | 102 |
| Laurent Wauquiez | 22 | 22 | 100 % | 5 | 13 |

**Le problème qu'elle nommait est réel, mais il a changé de nature** : ce n'est
plus une couverture manquante, c'est une **dispersion**. Le premier sujet pèse de
3,6 % (Mélenchon) à 22,7 % (Wauquiez) des questions. La correction tient dans les
deux cas — le point porte sa couverture *et* le nombre de sujets distincts, et ne
qualifie rien — mais le chiffre de 4 % ne doit pas être re-cité.

Le rendu a été vérifié par **rendu SSR réel** (`react-dom/server`, les 13
profils, harnais gardé hors dépôt comme #684). `npm run lint` et `npm run build`
passent ; la suite Python reste verte.

## Alternative écartée

**Un seuil qui déciderait si un premier sujet « ressort » assez pour être
nommé.** Il aurait fallu en fixer la valeur, et cette valeur aurait été un
arbitrage éditorial déguisé en mesure — exactement le défaut du seuil de
concentration à 90 % qu'on retire ici. Publier le compte du premier sujet **et**
le nombre de sujets distincts laisse le lecteur voir la dispersion sans que nous
la qualifiions.
