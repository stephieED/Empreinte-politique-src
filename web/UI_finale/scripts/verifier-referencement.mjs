#!/usr/bin/env node
/*
 * LE CONTRÔLE DE RÉFÉRENCEMENT (#969) — « pour que la régression se voie ».
 *
 * Parcourt le `sitemap.xml` d'un site en ligne et relève, adresse par adresse :
 * le statut HTTP, le `<title>`, la `canonical`, et la longueur du texte lisible
 * SANS JavaScript. Sort en échec si une adresse répond autre chose que 200, si
 * un titre manque, si deux pages partagent le même titre, ou si une fiche a
 * perdu son texte en clair.
 *
 *   node scripts/verifier-referencement.mjs [https://empreinte-politique.fr]
 *
 * Il interroge un SITE SERVI, jamais `dist/` : ce qui est mesuré ici, c'est ce
 * que le serveur répond — `vite preview` ne reproduit pas le comportement de
 * GitHub Pages, et c'est précisément ce comportement qui a fait le défaut.
 */
const base = (process.argv[2] || 'https://empreinte-politique.fr').replace(/\/$/, '');

const sansBalises = (html) => {
  const corps = html.replace(/<script[\s\S]*?<\/script>/g, '').match(/<body>([\s\S]*)<\/body>/);
  return corps ? corps[1].replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim() : '';
};
const entre = (html, motif) => (html.match(motif) || [])[1] || null;

const plan = await fetch(`${base}/sitemap.xml`);
if (!plan.ok) {
  console.error(`${base}/sitemap.xml : HTTP ${plan.status} — rien à parcourir.`);
  process.exit(1);
}
/* Les `loc` portent le domaine de production ; sur une autre base (un build
 * local servi comme Pages), c'est le CHEMIN qui compte, sinon le contrôle
 * mesure le site en ligne en croyant mesurer le build. */
const adresses = [...(await plan.text()).matchAll(/<loc>([^<]+)<\/loc>/g)]
  .map((m) => base + new URL(m[1]).pathname);
const robotsTxt = await fetch(`${base}/robots.txt`).then((r) => (r.ok ? r.text() : null));

const lignes = [];
for (const url of adresses) {
  const reponse = await fetch(url);
  const html = reponse.ok ? await reponse.text() : '';
  lignes.push({
    url,
    statut: reponse.status,
    titre: entre(html, /<title>([^<]*)<\/title>/),
    canonical: entre(html, /rel="canonical" href="([^"]*)"/),
    texte: sansBalises(html).length,
  });
}

const fiches = lignes.filter((l) => /\/(candidats|groupes|gouvernements)\//.test(l.url));
const titres = new Map();
for (const l of lignes) titres.set(l.titre, (titres.get(l.titre) || 0) + 1);

const defauts = [
  ...lignes.filter((l) => l.statut !== 200).map((l) => `${l.url} : HTTP ${l.statut}`),
  ...lignes.filter((l) => l.statut === 200 && !l.titre).map((l) => `${l.url} : aucun titre`),
  ...lignes.filter((l) => l.statut === 200 && !l.canonical).map((l) => `${l.url} : aucune canonical`),
  ...[...titres].filter(([titre, n]) => titre && n > 1).map(([titre, n]) => `${n} pages portent le titre « ${titre} »`),
  ...fiches.filter((l) => l.texte < 100).map((l) => `${l.url} : ${l.texte} caractères lisibles sans JavaScript`),
  ...(robotsTxt === null ? [`${base}/robots.txt : absent`] : []),
  ...(robotsTxt && !robotsTxt.includes('/sitemap.xml') ? [`${base}/robots.txt ne désigne pas le sitemap`] : []),
];

for (const l of lignes) {
  console.log(`${l.statut} ${String(l.texte).padStart(6)} car.  ${l.url}\n         ${l.titre ?? '— aucun titre —'}`);
}
console.log(
  `\n${lignes.length} adresses du sitemap, dont ${fiches.length} fiches ; `
  + `${lignes.filter((l) => l.statut === 200).length} en 200, ${titres.size} titres distincts.`,
);
if (defauts.length) {
  console.error(`\n${defauts.length} défaut(s) :\n  - ${defauts.join('\n  - ')}`);
  process.exit(1);
}
console.log('Aucun défaut.');
