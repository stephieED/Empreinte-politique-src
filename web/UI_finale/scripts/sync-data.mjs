#!/usr/bin/env node
// Copie pivot_data/ (+ raw_data/candidats.json) vers public/data/ et génère un
// manifest listant les candidats et groupes réellement disponibles. Exécuté
// avant `dev`/`build` (voir package.json) car Vite ne sert pas de fichiers
// situés hors du dossier du projet.
import { readFileSync, writeFileSync, mkdirSync, readdirSync, cpSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

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

// --- candidats.json (roster brut : nom, parti, statut) ---
cpSync(candidatsPath, path.join(outDir, 'candidats.json'));
const candidats = JSON.parse(readFileSync(candidatsPath, 'utf-8')).candidats;

// --- profils pivot individuels ---
const profileFiles = readdirSync(pivotProfilesDir).filter((f) => f.endsWith('.pivot.json'));
for (const file of profileFiles) {
  cpSync(path.join(pivotProfilesDir, file), path.join(outDir, 'profiles', file));
}
const availableSlugs = new Set(profileFiles.map((f) => f.replace(/\.pivot\.json$/, '')));

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
const manifestCandidates = candidats
  .filter((c) => availableSlugs.has(c.slug))
  .map((c) => ({
    slug: c.slug,
    nom: c.nom,
    parti: c.parti,
    famillePolitique: c.famille_politique,
    statut: c.statut,
  }));

// --- profils de groupe réels ---
const slugByMembreId = new Map(manifestCandidates.map((c) => [c.slug, c]));
const groupeFiles = readdirSync(pivotGroupesDir).filter((f) => f.endsWith('.json'));
const manifestGroupes = [];
for (const file of groupeFiles) {
  cpSync(path.join(pivotGroupesDir, file), path.join(outDir, 'groupes', file));
  const groupe = JSON.parse(readFileSync(path.join(pivotGroupesDir, file), 'utf-8'));
  const id = file.replace(/^groupe-/, '').replace(/\.json$/, '');
  manifestGroupes.push({
    id,
    fichier: file,
    groupeId: groupe.groupe_id,
    sigle: groupe.groupe_sigle,
    nom: groupe.groupe_nom,
    chambre: groupe.chambre,
    legislature: groupe.legislature,
    rosterTotal: groupe.meta?.couverture_roster?.roster_total ?? null,
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
