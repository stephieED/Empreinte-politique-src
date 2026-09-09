#!/usr/bin/env node
// Copie pivot_data/ (+ raw_data/candidats.json) vers public/data/ et génère un
// manifest listant les candidats et groupes réellement disponibles. Exécuté
// avant `dev`/`build` (voir package.json) car Vite ne sert pas de fichiers
// situés hors du dossier du projet.
import { readFileSync, writeFileSync, mkdirSync, readdirSync, cpSync, existsSync, rmSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { cleLegislature, construireComparaisons } from './comparaison-groupes.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(here, '..');
const repoRoot = path.resolve(projectRoot, '..', '..');
const outDir = path.join(projectRoot, 'public', 'data');

const pivotProfilesDir = path.join(repoRoot, 'pivot_data', 'profiles');
const pivotGroupesDir = path.join(repoRoot, 'pivot_data', 'groupes');
const pivotGouvernementsDir = path.join(repoRoot, 'pivot_data', 'gouvernements');
const candidatsPath = path.join(repoRoot, 'raw_data', 'candidats.json');
const scrutinsPath = path.join(repoRoot, 'pivot_data', 'scrutins.json');
const amendementsDir = path.join(repoRoot, 'pivot_data', 'amendements');

mkdirSync(path.join(outDir, 'profiles'), { recursive: true });
mkdirSync(path.join(outDir, 'groupes'), { recursive: true });
mkdirSync(path.join(outDir, 'gouvernements'), { recursive: true });

// --- scrutins.json (index partagé, #432) ---
// Depuis la normalisation des votes, un profil ne porte plus que le mapping
// { scrutin_id, position } : sans cet index, l'UI n'a ni date, ni texte, ni
// sort à afficher. Copié en premier, et son absence est signalée plutôt que
// silencieuse — c'est la seule dépendance entre fichiers de pivot_data/, et
// une copie oubliée viderait les votes de toutes les vues d'un coup.
if (existsSync(scrutinsPath)) {
  cpSync(scrutinsPath, path.join(outDir, 'scrutins.json'));
} else {
  console.warn(
    `sync-data : ${scrutinsPath} absent — les votes s'afficheront vides (#432). ` +
    'Construire l\'index : python3 src/build_scrutins_index.py',
  );
}

// --- amendements/ (index partagé, #431) ---
// Un fichier de méta par législature. Les fichiers `.cosignatures.json` ne sont
// PAS copiés : ils pèsent 59 % de l'index et aucune vue ne les lit — les y
// copier ferait porter au site 75,7 Mo d'un contenu jamais affiché. Ils restent
// dans le dépôt, accessibles pour l'analyse (#324).
if (existsSync(amendementsDir)) {
  mkdirSync(path.join(outDir, 'amendements'), { recursive: true });
  const metaFiles = readdirSync(amendementsDir)
    .filter((f) => f.endsWith('.json') && !f.endsWith('.cosignatures.json'));
  for (const file of metaFiles) {
    cpSync(path.join(amendementsDir, file), path.join(outDir, 'amendements', file));
  }
  if (metaFiles.length === 0) {
    console.warn(`sync-data : ${amendementsDir} vide — les amendements s'afficheront vides (#431).`);
  }
} else {
  console.warn(
    `sync-data : ${amendementsDir} absent — les amendements s'afficheront vides (#431). ` +
    'Construire l\'index : python3 src/build_amendements_index_pivot.py',
  );
}

// --- commissions_dossiers.json (commission saisie au fond par dossier, #328) ---
// Absent tant qu'aucun run n'a exécuté `build_commissions_dossiers.py` : la
// fiche candidat n'affiche alors pas la répartition par commission, et ne la
// déduit surtout pas d'un intitulé de dossier (AGENTS.md §2 règle 1).
const commissionsPath = path.join(repoRoot, 'pivot_data', 'commissions_dossiers.json');
if (existsSync(commissionsPath)) {
  cpSync(commissionsPath, path.join(outDir, 'commissions_dossiers.json'));
} else {
  console.warn(
    `sync-data : ${commissionsPath} absent — « L'essentiel » n'affichera pas la ` +
    'répartition par commission saisie au fond (#328). Construire l\'index : ' +
    'python3 src/build_commissions_dossiers.py',
  );
}

// --- scrutins_dossiers.json (scrutin → dossier, statut, 49.3 — #758) ---
// Un scrutin ne porte aucune référence législative : la jointure vient des
// `voteRefs` des actes du dossier, figée par `src/build_scrutins_dossiers.py`.
// Absent, « ce qu'il a voté » n'affiche ni matière ni statut du texte — et ne
// les déduit surtout pas de l'intitulé du scrutin (AGENTS.md §2 règle 1).
const scrutinsDossiersPath = path.join(repoRoot, 'pivot_data', 'scrutins_dossiers.json');
if (existsSync(scrutinsDossiersPath)) {
  cpSync(scrutinsDossiersPath, path.join(outDir, 'scrutins_dossiers.json'));
} else {
  console.warn(
    `sync-data : ${scrutinsDossiersPath} absent — « ce qu'il a voté » n'affichera ni `
    + 'matière ni statut du texte (#758). Construire l\'index : '
    + 'python3 src/build_scrutins_dossiers.py',
  );
}

// --- candidats.json (roster brut : nom, parti, statut) ---
cpSync(candidatsPath, path.join(outDir, 'candidats.json'));
const candidats = JSON.parse(readFileSync(candidatsPath, 'utf-8')).candidats;

// Statuts dont la fiche n'est PAS publiée par l'interface (#761).
//
// Une candidature déclinée cesse d'être une candidature : sa fiche sort de
// l'onglet Candidats, et son profil n'est même pas copié — un fichier servi que
// rien ne référence est du poids mort, et une URL qui répond ferait de la fiche
// masquée une page encore atteignable.
//
// Ce que le masquage NE fait PAS : supprimer quoi que ce soit de `pivot_data/`.
// Le profil reste publié dans le dépôt — ce que la personne a fait au Parlement
// reste vrai, seule sa candidature a cessé — et supprimer un fichier publié est
// une disparition qu'`audit_diff_profils` bloque (#460/#470). Elle reste aussi
// membre de son groupe : les fiches de groupe sont bâties sur `membres[]` et ne
// passent pas par cette liste.
//
// MÊME ENSEMBLE que `STATUTS_GELES` de `src/perimetre_candidats.py`, qui décide
// du périmètre de COLLECTE (#760), et `tests/test_fiches_masquees_761.py` fait
// échouer la suite s'ils divergent. Les deux disent la même chose — « cette
// personne n'est plus candidate » — et les séparer un jour devra être une
// décision écrite, pas une dérive.
export const STATUTS_MASQUES = new Set(['decline']);

const estMasque = (c) => STATUTS_MASQUES.has(c.statut);
const slugsMasques = new Set(candidats.filter(estMasque).map((c) => c.slug));

// --- profils pivot individuels ---
const profileFiles = readdirSync(pivotProfilesDir).filter((f) => f.endsWith('.pivot.json'));
for (const file of profileFiles) {
  const cible = path.join(outDir, 'profiles', file);
  if (slugsMasques.has(file.replace(/\.pivot\.json$/, ''))) {
    // Ce script ne nettoie pas son dossier de sortie : sans cette suppression,
    // le profil copié par une exécution PRÉCÉDENTE resterait servi à son URL, et
    // la fiche « masquée » serait encore atteignable.
    if (existsSync(cible)) rmSync(cible);
    continue;
  }
  cpSync(path.join(pivotProfilesDir, file), cible);
}
const availableSlugs = new Set(
  profileFiles
    .map((f) => f.replace(/\.pivot\.json$/, ''))
    .filter((slug) => !slugsMasques.has(slug)),
);

// `c.slug &&` est retiré (#539) : il datait du jour où un slug valait
// « référencé sur nosdeputes.fr », plateforme hors pipeline depuis #529. Le
// slug est désormais l'identifiant du profil, renseigné pour les 13 candidats
// déclarés — le test ne filtrait donc plus rien de vrai, il ne faisait que
// perpétuer une prémisse fausse. Le manifeste liste les candidats DÉCLARÉS.
//
// `availableSlugs.has(...)` reste, et c'est délibéré : ce script copie les
// fichiers de profil, et un candidat listé sans profil sur disque produirait
// un lien qui casse au clic. Le rendu d'un candidat déclaré sans page relève
// du lot UI #324/#328 ; ici on ne fabrique pas la promesse d'une page absente.
/* ── Qui a siégé à l'Assemblée, ou gouverné (#328) ───────────────────────────
 *
 * La barre des candidats grise les fiches qui ne portent NI mandat à
 * l'Assemblée nationale NI fonction gouvernementale. Ce n'est pas un jugement
 * sur la personne : c'est ce que la fiche peut montrer. Sans l'un des deux, le
 * corpus n'a ni vote, ni intervention, ni amendement à publier — la page existe
 * et le dit, mais elle ne porte pas d'activité parlementaire.
 *
 * DEUX FAITS, ET AUCUN DEVINÉ. `chambres` est le champ DÉRIVÉ des mandats
 * (#493) : il vaut `["PE"]` pour un député européen, et un mandat au Parlement
 * européen n'est pas un mandat à l'Assemblée. `fonction_gouvernementale` est une
 * catégorie de mandat, pas une inférence sur un intitulé.
 *
 * Mesuré sur les 27 candidats déclarés au commit de données courant : 17 ont
 * l'un des deux, 10 n'ont ni l'un ni l'autre — 6 sans aucun mandat collecté
 * (Tondelier, Arthaud, Lisnard, Labib, Verdier, Mathieu) et 4 dont toute la
 * carrière est au Parlement européen (Bardella, Glucksmann, Philippot,
 * Massard). Ségolène Royal, elle, n'a aucun vote publié mais sept fonctions
 * gouvernementales : elle n'est pas grisée, parce que le critère porte sur ce
 * qu'elle a exercé et non sur ce que nous avons collecté.
 */
const aSiegeOuGouverne = (slug) => {
  const profil = JSON.parse(
    readFileSync(path.join(pivotProfilesDir, `${slug}.pivot.json`), 'utf-8'),
  );
  /* `chambres` UNIQUEMENT, jamais le scalaire `chambre` : #328 avait retiré le
   * dernier consommateur de ce scalaire dans l'interface, et le rétablir en
   * repli annulerait la condition de retrait que `test_garde_fou_chambre.py`
   * surveille. Les 19 profils du corpus sans la clé sont tous des
   * `roster_groupe`, jamais listés comme candidats — l'absence retomberait
   * donc sur le seul test de fonction gouvernementale, et le dirait. */
  const chambres = profil.chambres || [];
  const gouvernement = (profil.mandats || []).some(
    (m) => m.categorie === 'fonction_gouvernementale',
  );
  return chambres.includes('AN') || gouvernement;
};

const manifestCandidates = candidats
  .filter((c) => !estMasque(c) && availableSlugs.has(c.slug))
  .map((c) => ({
    slug: c.slug,
    nom: c.nom,
    parti: c.parti,
    famillePolitique: c.famille_politique,
    statut: c.statut,
    mandatAnOuGouvernement: aSiegeOuGouverne(c.slug),
  }))
  /* L'ORDRE EST CELUI DU LIBELLÉ AFFICHÉ, pas celui du fichier source.
   * `raw_data/candidats.json` suit l'ordre de collecte, que rien ne rend
   * lisible : une barre de vingt-cinq pastilles où l'œil ne peut pas prédire
   * la place d'un nom se parcourt en entier à chaque fois. Le tri porte sur
   * `nom` — ce que le lecteur lit — et non sur un patronyme reconstruit :
   * découper « Le Pen » ou « Dupont-Aignan » demanderait une règle que la
   * source ne donne pas. */
  .sort((a, b) => a.nom.localeCompare(b.nom, 'fr', { sensitivity: 'base' }));

// --- profils de groupe réels ---
const slugByMembreId = new Map(manifestCandidates.map((c) => [c.slug, c]));
const groupeFiles = readdirSync(pivotGroupesDir).filter((f) => f.endsWith('.json'));
const manifestGroupes = [];
const fichesPourComparaison = [];
for (const file of groupeFiles) {
  cpSync(path.join(pivotGroupesDir, file), path.join(outDir, 'groupes', file));
  const groupe = JSON.parse(readFileSync(path.join(pivotGroupesDir, file), 'utf-8'));
  const id = file.replace(/^groupe-/, '').replace(/\.json$/, '');
  fichesPourComparaison.push({ id, groupe });
  manifestGroupes.push({
    id,
    fichier: file,
    groupeId: groupe.groupe_id,
    sigle: groupe.groupe_sigle,
    nom: groupe.groupe_nom,
    chambre: groupe.chambre,
    legislature: groupe.legislature,
    rosterTotal: groupe.meta?.couverture_roster?.roster_total ?? null,
    // #329 : la fiche compare les groupes de la MÊME législature. Le manifeste
    // porte la clé pour que l'UI sache quel fichier de comparaison charger,
    // sans télécharger une seule fiche voisine (les 5 fiches AN pèsent 15,1 Mo).
    comparaison: `comparaison-${cleLegislature(groupe)}.json`,
  });
  // Rattache chaque candidat au groupe réel dont il est membre (membre_id ->
  // slug), pour permettre le filtrage "Candidats" par "Groupes" côté UI sans
  // avoir à télécharger les fichiers de groupe (certains dépassent 500 Ko).
  for (const membre of groupe.membres || []) {
    const slug = String(membre.membre_id || '').split(':').pop();
    const candidate = slugByMembreId.get(slug);
    if (candidate) {
      if (!candidate.groupIds) candidate.groupIds = [];
      candidate.groupIds.push(id);
    }
  }
}

// --- comparaisons par législature (#329) ---
// Une projection par (chambre, législature) : sigle, effectif, amendements
// agrégés, position politique déclarée, et les positions majoritaires des seuls
// scrutins où le quorum est atteint. C'est ce qui permet à la fiche de comparer
// sans faire télécharger les fiches voisines — 150 Ko au lieu de 15,1 Mo.
for (const [cle, comparaison] of construireComparaisons(fichesPourComparaison)) {
  writeFileSync(
    path.join(outDir, 'groupes', `comparaison-${cle}.json`),
    JSON.stringify(comparaison),
  );
}

// --- profils de gouvernement réels ---
const gouvernementFiles = readdirSync(pivotGouvernementsDir).filter((f) => f.endsWith('.json'));
const manifestGouvernements = [];
for (const file of gouvernementFiles) {
  cpSync(path.join(pivotGouvernementsDir, file), path.join(outDir, 'gouvernements', file));
  const gouvernement = JSON.parse(readFileSync(path.join(pivotGouvernementsDir, file), 'utf-8'));
  const id = file.replace(/^gouvernement-/, '').replace(/\.json$/, '');
  manifestGouvernements.push({
    id,
    fichier: file,
    gouvernementId: gouvernement.gouvernement_id,
    nom: gouvernement.nom,
    debut: gouvernement.periode?.debut ?? null,
    fin: gouvernement.periode?.fin ?? null,
    actif: gouvernement.periode?.actif ?? false,
    // #328 : la fiche de profil doit savoir de QUELS gouvernements la personne
    // a été membre avant d'en télécharger un seul (les dix pèsent 580 Ko).
    // L'appariement se fait ici, une fois, sur `membre_id` — le même champ que
    // pour les groupes, quelques lignes plus haut.
    membreIds: [...new Set((gouvernement.membres || []).map((m) => m.membre_id).filter(Boolean))],
  });
}
manifestGouvernements.sort((a, b) => (b.debut || '').localeCompare(a.debut || ''));

writeFileSync(
  path.join(outDir, 'manifest.json'),
  JSON.stringify(
    { candidates: manifestCandidates, groupes: manifestGroupes, gouvernements: manifestGouvernements },
    null,
    2,
  ),
);

console.log(`sync-data : ${manifestCandidates.length} candidat(s), ${manifestGroupes.length} groupe(s), ${manifestGouvernements.length} gouvernement(s) copiés vers public/data/.`);
if (slugsMasques.size) {
  // Nommés, jamais seulement comptés : une fiche retirée de l'interface doit se
  // distinguer d'une fiche qu'on a oublié de produire (#510).
  console.log(`sync-data : ${slugsMasques.size} fiche(s) masquée(s) — ${[...slugsMasques].join(', ')} (statut masqué, profil conservé dans pivot_data/).`);
}
