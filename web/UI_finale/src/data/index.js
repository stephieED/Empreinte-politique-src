import { buildCandidateView, buildGroupView, buildGovernmentView } from './pivotAdapter';

export const DEFAULT_CANDIDATE_ID = 'jean-luc-melenchon';
export const DEFAULT_GROUP_ID = 'AN-SOC-16';
export const DEFAULT_GOVERNMENT_ID = 'LECORNU_II';

let manifestPromise = null;
let scrutinsPromise = null;

function loadManifest() {
  if (!manifestPromise) {
    manifestPromise = fetch('/data/manifest.json').then((r) => {
      if (!r.ok) throw new Error(`manifest.json : HTTP ${r.status}`);
      return r.json();
    });
  }
  return manifestPromise;
}

/**
 * Index des scrutins (#432), chargé une fois pour toute la session.
 *
 * Depuis la normalisation des votes, un profil ne porte plus que le mapping
 * `{ scrutin_id, position }` : le méta du scrutin — identique pour ses ~150
 * votants — vit une seule fois ici. Le fichier pèse ~8 Mo là où les profils
 * pesaient 180 Mo de votes, et il est **partagé** entre profils individuels et
 * profils de groupe (les 4 104 scrutins des groupes sont inclus dans les 17 422
 * des profils : zéro scrutin propre aux groupes).
 *
 * Mémoïsé, et non bloquant : un échec de chargement rend un index vide plutôt
 * que de faire échouer toute la page. Les vues affichent alors une donnée
 * manquante — jamais une donnée inventée.
 */
function loadScrutins() {
  if (!scrutinsPromise) {
    scrutinsPromise = fetch('/data/scrutins.json')
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => Object.fromEntries((d?.scrutins || []).map((s) => [s.id, s])))
      .catch(() => ({}));
  }
  return scrutinsPromise;
}

function fetchJson(url) {
  return fetch(url).then((r) => (r.ok ? r.json() : null));
}

export async function getCandidatesList() {
  const manifest = await loadManifest();
  return manifest.candidates.map((c) => ({
    id: c.slug,
    nom: c.nom,
    groupId: c.groupId ?? null,
    parti: c.parti,
  }));
}

export async function getGroupsList() {
  const manifest = await loadManifest();
  return manifest.groupes.map((g) => ({
    id: g.id,
    title: g.nom,
    kicker: `${g.chambre === 'AN' ? 'Assemblée nationale' : 'Sénat'} · Législature ${g.legislature}`,
  }));
}

export async function getCandidateProfile(id) {
  const manifest = await loadManifest();
  const entry = manifest.candidates.find((c) => c.slug === id);
  if (!entry) return null;
  const [pivot, scrutins] = await Promise.all([
    fetchJson(`/data/profiles/${entry.slug}.pivot.json`),
    loadScrutins(),
  ]);
  if (!pivot) return null;
  return buildCandidateView(pivot, entry, scrutins);
}

export async function getGroupProfile(id) {
  const manifest = await loadManifest();
  const entry = manifest.groupes.find((g) => g.id === id);
  if (!entry) return null;
  const [groupe, scrutins] = await Promise.all([
    fetchJson(`/data/groupes/${entry.fichier}`),
    loadScrutins(),
  ]);
  if (!groupe) return null;
  return buildGroupView(groupe, scrutins);
}

export async function getGovernmentsList() {
  const manifest = await loadManifest();
  return (manifest.gouvernements || []).map((g) => ({
    id: g.id,
    title: g.nom,
    kicker: g.actif ? 'En fonction' : `Jusqu'en ${g.fin ? new Date(g.fin).getFullYear() : '?'}`,
  }));
}

export async function getGovernmentProfile(id) {
  const manifest = await loadManifest();
  const entry = (manifest.gouvernements || []).find((g) => g.id === id);
  if (!entry) return null;
  const gouvernement = await fetchJson(`/data/gouvernements/${entry.fichier}`);
  if (!gouvernement) return null;
  return buildGovernmentView(gouvernement);
}
