import { buildCandidateView, buildGroupView, buildGovernmentView } from './pivotAdapter';

export const DEFAULT_CANDIDATE_ID = 'jean-luc-melenchon';
export const DEFAULT_GROUP_ID = 'AN-SOC-16';
export const DEFAULT_GOVERNMENT_ID = 'LECORNU_II';

let manifestPromise = null;

function loadManifest() {
  if (!manifestPromise) {
    manifestPromise = fetch('/data/manifest.json').then((r) => {
      if (!r.ok) throw new Error(`manifest.json : HTTP ${r.status}`);
      return r.json();
    });
  }
  return manifestPromise;
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
  const pivot = await fetchJson(`/data/profiles/${entry.slug}.pivot.json`);
  if (!pivot) return null;
  return buildCandidateView(pivot, entry);
}

export async function getGroupProfile(id) {
  const manifest = await loadManifest();
  const entry = manifest.groupes.find((g) => g.id === id);
  if (!entry) return null;
  const groupe = await fetchJson(`/data/groupes/${entry.fichier}`);
  if (!groupe) return null;
  return buildGroupView(groupe);
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
