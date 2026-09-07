/*
 * LE REPLI DE ROUTAGE, ET POURQUOI IL EST DANS LE BUILD ET PAS DANS LE WORKFLOW.
 *
 * L'application route côté client (`BrowserRouter`). GitHub Pages, lui, sert
 * des FICHIERS : il ne connaît que `/index.html`, et répond 404 à tout chemin
 * qui n'est pas un fichier réel. Conséquence mesurée en production le
 * 07/09/2026 : `/` répondait 200, `/candidats` et `/candidats/<slug>`
 * répondaient **404**. Le site n'était navigable qu'en partant de la racine —
 * un favori, un lien partagé, une entrée d'historique, ou simplement F5 sur
 * une fiche, tombaient sur la page d'erreur de GitHub.
 *
 * Pages sert `404.html` pour tout chemin inconnu. Lui donner le contenu de
 * `index.html` fait donc démarrer l'application, qui lit l'URL et affiche la
 * bonne page. C'est le seul mécanisme disponible : Pages n'a pas de règle de
 * réécriture.
 *
 * CE QUE CE REPLI NE CORRIGE PAS, ET QUI EST ASSUMÉ : le STATUT HTTP reste
 * 404 sur un lien profond. Le lecteur voit la bonne page, un robot voit une
 * erreur. Le corriger demanderait un hébergement qui sait réécrire, ou un
 * routage par fragment (`/#/candidats/…`) qui abîmerait les URL — deux choix
 * plus lourds que le défaut qu'ils réparent.
 *
 * IL VIT DANS LE BUILD, pas dans `deploy-pages.yml` : un `dist/` construit à
 * la main et publié autrement doit porter le même repli. Le workflow ne fait
 * que téléverser `dist/` — c'est au build de le rendre complet.
 */
import { copyFileSync, existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const dist = join(dirname(dirname(fileURLToPath(import.meta.url))), 'dist');
const source = join(dist, 'index.html');
const cible = join(dist, '404.html');

if (!existsSync(source)) {
  console.error(`spa-fallback : ${source} est introuvable — le build a-t-il tourné ?`);
  process.exit(1);
}
copyFileSync(source, cible);
console.log('spa-fallback : dist/404.html écrit — les liens profonds démarrent l’application.');
