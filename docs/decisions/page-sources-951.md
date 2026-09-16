<a id="page-sources-951"></a>

# /couverture devient /sources, ouverte par un schéma de ce que chaque source apporte (#951) (2026-09-16)

`2026-09-16`

> **En bref** — deuxième des trois pages de #951. `/sources` réunit `/couverture` (la frise de ce que le dépôt porte, le tableau des manquants) et la liste des sources du bloc « Sources & fraîcheur » de l'accueil. **Ordre retenu le 16/09/2026 entre trois maquettes rendues** : les sources d'abord, puis la frise, puis les manquants — d'où viennent les données, avant depuis quand. La propriétaire a demandé **« une façon plus visuelle de montrer les sources appelées et croisées »** : trois figures maquettées (un flux, une matrice, les clés de rapprochement), **le flux retenu** — source → ce qu'elle apporte → la fiche où cela se lit, seule figure qui répond à la fois à « d'où » et à « pour quoi ». **Aucune épaisseur n'y porte de quantité**. Chaque pavé de source **ouvre la source dans un nouvel onglet** (demandé pendant l'implémentation) ; NosDéputés répondant HTTP 500 depuis sa panne, son pavé mène à Regards Citoyens. **Chaque nœud porte les informations de sa source** (couverture, cadence, licence) à la place des cartes repliées, demandé ensuite : **à la souris, le survol montre une infobulle et le clic ouvre la source ; au doigt, le toucher ouvre une bande sous le nœud**, qui porte le lien — le geste se choisit sur le pointeur (`hover: hover` et `pointer: fine`), jamais sur la largeur, et la bande se cale sur la largeur visible de l'écran. **Un test tient égales la liste du schéma et celle de `sources.config.js`** : `sources.config.js` ne portait ni le **Répertoire national des élus** ni **EuroVoc**, pourtant collectés — la page aurait montré neuf sources sur onze. **`/couverture` redirige vers `/sources` en gardant l'ancre**, et les liens du site pointent directement sur `/sources` (`#frise` depuis les fiches). **Alternative écartée** : garder `/couverture` et faire de `/sources` une seconde page — deux pages pour une seule question, « d'où vient ce que je lis ».

## La décision

- `data/schemaSources.js` : les onze sources (`statut` collectée / citée / plus
  interrogée, `teinte` d'institution, `url`, `config`), les onze données, les
  trois fiches. Écrit depuis `docs/data-architecture.md` « Les sources », le bloc
  `rafraichir-candidats` du workflow et AGENTS.md §7 ; aucun chiffre.
- `components/SchemaSources.jsx` : le flux en SVG, 880 px, qui défile en largeur
  sous cette taille — le replier casserait le trajet qu'il montre. Survol et
  focus allument un trajet. Pas de `role="img"`, qui rendrait les liens muets.
- Les informations d'un nœud viennent de `sources.config.js`, sans recopie.
- `components/CartesSources.jsx` : les cartes, extraites de `SourcesFreshness`,
  que seul l'accueil rend encore, jusqu'à sa forme C.
- `CoveragePage` sert `/sources` ; `RedirectionCouverture` renvoie `/couverture`
  avec son ancre ; la page suit l'ancre une fois la couverture chargée.
- Le pied de site nomme la page « Sources ».

## Ce qui reste de #951

La section en tête de `/methodologie`, puis la forme C de l'accueil. Les textes
des cartes Wikipédia et Wikidata (« Suivi biographique complémentaire des
candidats ») ne disent pas ce que le schéma dit d'elles : à reprendre, rendus.
