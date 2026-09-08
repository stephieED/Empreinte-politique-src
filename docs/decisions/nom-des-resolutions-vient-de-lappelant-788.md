# La seconde déclaration lisait un champ que le corpus ne porte pas (#788)

`2026-09-08`

## Contexte

Le run `34264027824` a transporté ses artifacts — #786 corrigé, **723 profils
fusionnés** contre 0 au run précédent — et s'est arrêté au garde-fou de #511 :

```
[!] anasse-kazib : profil brut collecté, aucun pivot publié.
##[error]COLLECTE_NON_PUBLIEE — 5 profil(s) collecté(s) sur 743 ne sont publiés
nulle part (seuil : 0). Slug(s) : anasse-kazib, francis-lalanne,
francois-asselineau, karim-bouamrane, sylvain-durif
```

Les cinq de #775. Cette fois le brut **est** écrit — la première place de la
seconde déclaration fonctionne — et la passe pivot dit :

```
— François Asselineau (francois-asselineau) : aucune source normalisable en --pivot-only.
```

## La cause

#781 a posé la seconde déclaration à la place du pivot **en écrivant qu'elle
devait être symétrique** de celle de l'écriture du brut. Elle ne l'était pas :

| Place | Ce qu'elle passait à `declare_hors_an_par_identifiant` |
| --- | --- |
| écriture du brut (`process_candidat`) | `nom` — le nom du candidat, venu de `raw_data/candidats.json` |
| normalisation pivot (`_normaliser_en_pivot`) | `profile.get("nom")` — le profil **brut** |

**Aucun profil brut ne porte de champ `nom` : 0 sur 652** mesurés sur le corpus
committé. Le nom y vit sous `identite.nom_complet`. La branche rendait donc
`None` → `""` → aucune résolution trouvée → `False`, **à tous les coups**.

Le fichier de résolutions du run était pourtant correct — six entrées, clés par
le nom de la liste : `'François Asselineau' -> hors_an`, `'Anasse Kazib' ->
hors_an`, `'Francis Lalanne'`, `'Karim Bouamrane'`, `'Sylvain Durif'`, plus
`'Manolo Mlekuz' -> indetermine`.

**La seconde déclaration de #781 n'a jamais pu être vraie.** Elle est morte à
l'écriture, et le lot qui la portait est passé au vert.

## Décision

`_normaliser_en_pivot` reçoit `nom` de son appelant, comme l'autre place le fait
depuis toujours. C'est par construction la clé de
`raw_data/resolutions_candidats.json` : les deux places lisent la même chaîne,
issue du même fichier, au lieu que l'une la cherche dans une structure qui ne la
contient pas.

La symétrie que #781 **décrivait** devient une symétrie que le code **tient**.

## Pourquoi les tests de #781 ne l'ont pas vue

Ils lisent le *source*. `test_les_deux_places_acceptent_la_meme_declaration`
compte les occurrences de `declare_hors_an_par_identifiant` ;
`test_la_place_du_pivot_consulte_bien_lidentifiant` vérifie qu'elle apparaît
dans le corps de la fonction. Les deux étaient vrais, et le sont restés pendant
que la branche rendait `False`.

**Un test de source ne peut pas voir qu'un champ lu n'existe pas.** C'est une
variante du patron de #726 : là, une fixture fournissait un champ que le corpus
avait cessé de porter ; ici, le test ne fait même pas tourner le code. Les tests
de ce lot **exécutent** `_normaliser_en_pivot` sur un brut à la **forme du
corpus** — pas de `nom`, un `identite.nom_complet` — et vérifient qu'un pivot en
sort. Remis dans l'état d'avant, le principal échoue ; c'est ce qui le rend
utile.

Une contre-épreuve l'accompagne : même brut, même résolution, un nom d'appelant
qui ne correspond pas → pas de pivot. Sans elle, « corriger » en lisant
`identite.nom_complet` passerait aussi, et la paire ne dirait plus rien.

## Ce que la correction ne relâche pas

`indetermine` ne vaut toujours pas déclaration (#757), un fichier de résolutions
absent rend le comportement d'avant, et `en_echec` continue d'écarter la branche
à l'écriture du brut : une panne rend le même vide qu'une absence (#484). Les
trois sont désormais vérifiés en exécution et non plus par une expression
régulière.

## Alternative écartée

**Lire `identite.nom_complet` dans le brut.** Ça marcherait aujourd'hui, et ça
rejouerait le défaut : la clé des résolutions est le nom de la **liste**, pas
celui de l'identité collectée, et rien ne garantit qu'ils restent égaux — une
identité fusionnée depuis l'AN peut porter une autre graphie. L'appelant tient
la bonne chaîne ; la chercher ailleurs est ce qui a produit l'incident.
