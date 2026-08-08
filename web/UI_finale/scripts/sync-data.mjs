#!/usr/bin/env node
// Copie pivot_data/ (+ raw_data/candidats.json) vers public/data/ et génère un
// manifest listant les candidats et groupes réellement disponibles. Exécuté
// avant `dev`/`build` (voir package.json) car Vite ne sert pas de fichiers
// situés hors du dossier du projet.
import { readFileSync, writeFileSync, mkdirSync, readdirSync, cpSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const here = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(here, '..');
const repoRoot = path.resolve(projectRoot, '..', '..');
const outDir = path.join(projectRoot, 'public', 'data');

const pivotProfilesDir = path.join(repoRoot, 'pivot_data', 'profiles');
const pivotGroupesDir = path.join(repoRoot, 'pivot_data', 'groupes');
const candidatsPath = path.join(repoRoot, 'raw_data', 'candidats.json');

mkdirSync(path.join(outDir, 'profiles'), { recursive: true });
mkdirSync(path.join(outDir, 'groupes'), { recursive: true });

// --- candidats.json (roster brut : nom, parti, statut) ---
cpSync(candidatsPath, path.join(outDir, 'candidats.json'));
const candidats = JSON.parse(readFileSync(candidatsPath, 'utf-8')).candidats;

// --- profils pivot individuels ---
const profileFiles = readdirSync(pivotProfilesDir).filter((f) => f.endsWith('.pivot.json'));
for (const file of profileFiles) {
  cpSync(path.join(pivotProfilesDir, file), path.join(outDir, 'profiles', file));
}
const availableSlugs = new Set(profileFiles.map((f) => f.replace(/\.pivot\.json$/, '')));

const manifestCandidates = candidats
  .filter((c) => c.slug && availableSlugs.has(c.slug))
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

writeFileSync(
  path.join(outDir, 'manifest.json'),
  JSON.stringify({ candidates: manifestCandidates, groupes: manifestGroupes }, null, 2),
);

console.log(`sync-data : ${manifestCandidates.length} candidat(s), ${manifestGroupes.length} groupe(s) copiés vers public/data/.`);
