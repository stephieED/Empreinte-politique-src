# « Collecté = publié » compte une tranche dérivée dans l'archive (#691, lot 3a)

`2026-09-09`

## Contexte

Le lot 2 a rendu le **lecteur** capable de servir une tranche dérivée. Trois
préalables restaient avant de pouvoir cesser d'écrire. Ce lot en traite un, en
constate un autre déjà satisfait, et laisse le troisième à un arbitrage.

## Le préalable traité : le garde-fou de #511 comptait sur le disque

`audit_collecte_vs_publie.compter_listes_profil_brut` lit la forme **sur le
disque** :

```python
dossier = raw_dir / slug
if not dossier.is_dir():
    return releve
```

Son docstring dit pourquoi : « le répertoire de tranches est un fait observable
là où le manifeste est une déclaration », et sans lui ce contrôle « lirait
0 amendement collecté face à 6 millions publiés — il ne signalerait aucun
déficit et deviendrait aveugle sur 96,7 % du volume ».

**Une tranche dérivée n'a pas de disque à observer.** Dès la première, ce
contrôle rendait 0 — exactement le défaut que son propre docstring donne comme
celui à éviter.

## Décision : compter dans l'archive, jamais dans le manifeste

Le principe est préservé, et c'est ce qui autorise l'exception. Ce que le
contrôle s'interdit, c'est de **recopier le `nombre` que le manifeste annonce** —
un contrôle qui lit sa conclusion dans le document qu'il contrôle ne contrôle
rien (#576, #579).

L'archive figée n'est pas ce document : elle est versionnée, close, et le compte
y est **mesuré** exactement comme dans une tranche sur disque. Le manifeste ne
sert qu'à dire **où** compter. Un test l'établit en annonçant `nombre: 999` pour
trois amendements réels.

**`signatures()` et non `reconstruire_tranche()`** : compter n'a besoin que de
l'index par acteur — 10,5 Mo pour la XVe au lieu des centaines du store — sur un
contrôle qui boucle sur tout le corpus. Un test vérifie que le store n'est pas
ouvert.

**Une tranche déclarée dérivée et non dérivable lève.** Le taire ferait passer
un déficit pour une absence, ce que ce garde-fou existe pour empêcher (#511).

## Le préalable déjà satisfait

Le sparse-checkout d'`extract-an` porte **déjà** `raw_data/amendements_an_figes`
— ajouté pour la reprise des `texte_vise` de #696. Les deux autres jobs qui
lisent des profils bruts, `extract-roster-groupes` et `merge-and-pivot`, font un
checkout complet. Rien à ajouter, et c'est vérifié plutôt que supposé.

## Le préalable restant, et pourquoi il est un arbitrage

`partitionner` devra marquer les tranches closes. Se pose alors une question que
le code ne tranche pas seul : **le `nombre` d'une tranche dérivée doit-il être
le compte de la collecte, ou celui de l'archive ?**

Les deux coïncident aujourd'hui — 854 tranches sur 854 couvertes, 568 771
amendements comparés sans écart. La question porte sur le jour où ils
divergeront :

| `nombre` = | Conséquence d'une divergence |
| --- | --- |
| la collecte | `recomposer` lève : le profil devient **illisible** |
| l'archive | la lecture tient ; l'écart doit être signalé ailleurs |

Rendre un profil illisible parce que la collecte a trouvé autre chose que
l'archive déplace l'erreur loin de sa cause — le patron que #771 a payé une
heure dix-huit. Mais choisir l'archive suppose de dire **où** l'écart se
signale, sans quoi il devient muet (#510).

Ce lot ne tranche pas : il nomme.

## Ce que ce lot ne fait toujours pas

Rien n'est marqué `derivee` dans le corpus, rien ne cesse d'être écrit, et les
5,55 Go de tranches closes sont intacts.
