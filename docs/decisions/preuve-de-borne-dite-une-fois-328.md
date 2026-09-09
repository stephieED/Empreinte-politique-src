<a id="preuve-de-borne-dite-une-fois-328"></a>

# Une preuve de borne se dit une fois par liste (#328) (2026-09-09)

## Le contexte

Un audit de verbosité de la fiche candidat, demandé le 09/09/2026, a trouvé
autre chose que de la verbosité : **la même preuve de borne s'imprimait deux
fois par ligne** dans « Ce qu'on n'a pas pu lire ».

Mesuré sur la page rendue : **148 mots en double** sur `jerome-guedj` et
`marine-le-pen`, **197** sur `edouard-philippe`, 0 sur `nathalie-arthaud` — dont
les listes n'ont qu'un seul état.

Le motif est mécanique. `couverture_profil._deriver` écrit **deux entrées** par
liste — « couvert depuis le 19/06/2002 » et « hors couverture jusqu'au
18/06/2002 » — et **une même borne explique les deux** : le référentiel AMO30 ne
rattache aucun acteur à un mandat antérieur à la XIIe législature, ce qui dit à
la fois où la couverture commence et jusqu'où elle ne va pas. La fiche rendait
`preuve` à chaque état.

## La décision

**La preuve reste sur chaque état ; c'est l'affichage qui ne la répète pas.**
`couvertureDesListes` marque `preuveDejaDite` sur la seconde occurrence de la
même chaîne **dans la même liste**, et `Couverture` saute les entrées marquées.

## L'alternative écartée, et pourquoi elle était fausse

**Ne poser la preuve qu'une fois à la source.** C'est un tiers de code en moins,
et cela efface un fait.

Les deux entrées ne portent pas *toujours* la même preuve. Dans `_deriver`, la
seconde porte toujours `borne.preuve` ; la première la porte aussi **sauf**
quand un fait « hors AN » est établi, où elle porte la sienne. Mesuré sur les 27
candidats déclarés, 135 listes portant au moins une preuve :

| Cas | Listes |
| --- | ---: |
| Plusieurs états, **même** preuve | 69 |
| Plusieurs états, preuves **différentes** | 35 |
| Un seul état porteur de preuve | 31 |

Sur `marine-tondelier`, la borne AMO30 et l'absence déclarée dans
`raw_data/correspondance_acteurs_an.json` expliquent **deux états distincts** de
la même liste. Un dédoublonnage à la source aurait supprimé la seconde dans ces
35 cas — soit exactement la moitié des lignes concernées.

Poser `preuve: null` sur la répétition aurait le même défaut à l'étage
d'au-dessus : les deux états portent bien la même borne, et c'est vrai. La
marque dit « ne la répète pas », pas « cet état n'a pas de preuve ».

## Le détail qui décide de la justesse

**Le `Set` de mémoire est déclaré dans la boucle des listes, pas au-dessus.**
Déclaré une fois pour toutes, la borne AMO30 disparaîtrait de « Votes » parce
que « Mandats et fonctions » l'a déjà écrite — deux listes indépendantes qui
partagent une borne doivent chacune la dire. Un test tient ce point, parce que
c'est la seule façon de se tromper qui ne se voie pas à l'écran sur un profil
ordinaire.

## Ce que le lot ne fait pas

Il ne touche à aucun texte. L'audit du 09/09 a relevé par ailleurs six blocs de
copie au-dessus de la limite de `DESIGN_SYSTEM.md` §7 règle 2 — le critère de
« Ce qu'il a voté » à 58 mots en tête — et deux modes d'emploi (« Cliquez une
barre… », « Clique un ruban… ») qui ne s'accordent même pas sur le vouvoiement.
C'est un lot séparé : la propriétaire a tranché que le « pourquoi » descend en
méthodologie, la fiche ne gardant qu'une mention brève et le lien vers le
paragraphe. Réduire un texte est un arbitrage éditorial ; supprimer un doublon
n'en est pas un.
