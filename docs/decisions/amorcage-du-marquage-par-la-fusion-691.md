# La fusion défaisait le marquage de la collecte : un run vert qui n'a rien basculé (#691, lot 3c)

`2026-09-09`

## Le constat

Le run [`34329085168`](https://github.com/stephieED/Empreinte-politique-src/actions/runs/34329085168)
est **vert**, a committé `5e7b5dca` (2 324 fichiers), et **n'a basculé aucune
tranche** : zéro fichier supprimé sous `raw_data/profiles/*/1[456].json`, et
aucun `derivee` dans les manifestes committés.

```
"tranches": [{"legislature": "15", "fichier": "15.json", "nombre": 18751},
             {"legislature": "16", "fichier": "16.json", "nombre": 16915},
             {"legislature": "17", "fichier": "17.json", "nombre": 18893}]
```

Les 5,55 Go sont toujours là.

## La cause : le bon principe, le mauvais fichier

**Les shards, eux, avaient marqué.** Vérifié dans l'artifact
`raw-profiles-an-gabriel-attal` du run :

```
{"legislature": "15", "nombre": 340, "derivee": true, "acteur_ref": "PA722190"}
{"legislature": "16", "nombre": 3,   "derivee": true, "acteur_ref": "PA722190"}
{"legislature": "17", "fichier": "17.json", "nombre": 601}
```

C'est la **fusion** qui a défait ce marquage. `merge_raw_dirs` lisait l'acteur
par `_acteur_du_socle(out_dir, slug)` — le socle de **destination**, celui du
corpus committé, qui n'a jamais été marqué. Il rendait donc `None`, `partitionner`
ne marquait rien, et les tranches étaient réécrites depuis le profil recomposé.

Le principe posé au lot 3b était juste — « la fusion ne résout pas d'identité,
elle reconduit ce que la collecte a déclaré ». L'implémentation lisait le mauvais
fichier : la destination au lieu des sources.

## Décision

L'acteur se lit dans les socles **sources** — ceux que les shards viennent
d'écrire, dans `_artifacts/` —, et le premier qui en déclare un l'emporte. La
fusion reconduit alors ce que la collecte a marqué, ce qu'elle était censée
faire.

## Le motif, pour la troisième fois de la journée

**Un run vert qui n'a rien fait.** C'est #786 (le transport avalé par
`continue-on-error`), c'est #788 (une branche qui rendait `False` à tous les
coups), et c'est celui-ci. À chaque fois, le vert ne prouvait rien parce
qu'aucun garde-fou ne mesurait l'**effet** attendu, seulement l'absence
d'erreur.

Ici, rien ne pouvait rougir : ne pas marquer une tranche est un comportement
légitime — c'est le défaut prudent posé exprès au lot 3b, « sans `acteur_ref`,
rien n'est marqué ». Un non-effet et un défaut prudent sont indistinguables de
l'extérieur.

Le test ajouté ne vérifie donc pas une absence d'erreur mais un **effet** : un
socle source marqué doit rester marqué après fusion, et sa tranche disparaître
du disque. Il échoue sur le code d'avant — vérifié.

## Ce que la bascule sera : progressive

`merge_raw_dirs` ne réécrit que les slugs présents dans les artifacts. Les
profils qu'un run ne recollecte pas gardent leur socle et leurs tranches. La
bascule se fera donc **au fil des runs**, à mesure que chaque profil repasse par
la collecte — sans perte, la fusion étant additive, et sans étape de migration.

C'est plus lent qu'une bascule en une fois, et c'est plus sûr : chaque profil
bascule le jour où sa collecte a réussi.
