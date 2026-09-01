import {
  buildCandidateView,
  buildGroupView,
  buildGovernmentView,
  legislatureDeAmendementId,
} from './pivotAdapter';

export const DEFAULT_CANDIDATE_ID = 'jean-luc-melenchon';
export const DEFAULT_GROUP_ID = 'AN-SOC-16';
export const DEFAULT_GOVERNMENT_ID = 'LECORNU_II';

let manifestPromise = null;
let scrutinsPromise = null;
const amendementsPromises = new Map();

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

/**
 * Index des amendements d'UNE législature (#431), mémoïsé.
 *
 * Contrairement aux scrutins, l'index des amendements n'est pas un fichier
 * unique : il en pèserait 128,8 Mo, au-delà de la limite GitHub de 100 Mo par
 * blob. Il est découpé par législature, et l'UI ne charge que celles que le
 * profil affiché référence — un⋅e élu⋅e de la seule XVIIe ne télécharge pas les
 * trois autres.
 *
 * Les cosignatures vivent dans un fichier compagnon jamais chargé ici : elles
 * pèsent 59 % de l'index et aucune vue ne les affiche.
 *
 * Non bloquant : un échec de chargement rend un index vide plutôt que de faire
 * échouer la page. Les vues affichent alors une donnée manquante — jamais une
 * donnée inventée.
 */
function loadAmendementsLegislature(legislature) {
  if (!amendementsPromises.has(legislature)) {
    amendementsPromises.set(
      legislature,
      fetch(`/data/amendements/${legislature}.json`)
        .then((r) => (r.ok ? r.json() : null))
        // `textes` est conservé depuis #328 : il porte, par `texte_vise`, le
        // `dossier_id` et le titre du dossier législatif. Sans lui, les dépôts
        // se compteraient sur les textes visés — 47 là où il y a 34 dossiers
        // chez Jérôme Guedj — et aucun dossier ne pourrait être NOMMÉ au
        // lecteur, ce qui est tout ce que le coup d'œil publie désormais.
        .then((d) => ({ amendements: d?.amendements || {}, textes: d?.textes || {} }))
        .catch(() => ({ amendements: {}, textes: {} })),
    );
  }
  return amendementsPromises.get(legislature);
}

/**
 * Charge les seules législatures que le mapping du profil référence, et rend
 * `{ legislature: { id: amendement } }`.
 *
 * Les index par législature ne sont pas fusionnés en un seul objet : la
 * résolution se fait par législature, lue dans l'identifiant, donc la fusion ne
 * servirait qu'à recopier jusqu'à 207 238 entrées pour rien.
 */
async function loadAmendementsPour(pivot) {
  const legislatures = [
    ...new Set(
      (pivot?.amendements || [])
        .map((a) => legislatureDeAmendementId(a.amendement_id))
        .filter(Boolean),
    ),
  ];
  const parts = await Promise.all(legislatures.map(loadAmendementsLegislature));
  return Object.fromEntries(legislatures.map((l, i) => [l, parts[i]]));
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

/**
 * Fiches de groupe où ce candidat est membre (#328).
 *
 * `manifest.candidates[].groupIds` est calculé par `scripts/sync-data.mjs`, qui
 * a déjà apparié `membre_id` → slug sur chaque fiche : l'UI n'a donc pas à
 * télécharger les sept fiches pour savoir lesquelles la concernent — elles
 * pèsent de 8 Ko à 4,5 Mo.
 *
 * Non bloquant : une fiche manquante rend la section « où il s'est écarté des
 * siens » incomparable, ce que la page DIT, plutôt que vide, ce qui se lirait
 * comme « il n'a jamais divergé ».
 */
function loadFichesGroupe(manifest, entry) {
  const ids = entry.groupIds || [];
  return Promise.all(
    ids.map((id) => {
      const fiche = manifest.groupes.find((g) => g.id === id);
      return fiche ? fetchJson(`/data/groupes/${fiche.fichier}`).catch(() => null) : null;
    }),
  );
}

/**
 * Fiches de gouvernement dont ce candidat a été membre (#328).
 *
 * `manifest.gouvernements[].membreIds` évite de charger les dix fiches pour
 * n'en garder qu'une ou quatre. Un candidat qui n'a jamais été au gouvernement
 * n'en télécharge aucune — et la section le dit comme un FAIT ÉTABLI sur la
 * personne, jamais comme une donnée manquante.
 */
function loadGouvernements(manifest, slug) {
  const fiches = (manifest.gouvernements || []).filter((g) => (g.membreIds || []).includes(slug));
  return Promise.all(fiches.map((g) => fetchJson(`/data/gouvernements/${g.fichier}`).catch(() => null)));
}

export async function getCandidateProfile(id) {
  const manifest = await loadManifest();
  const entry = manifest.candidates.find((c) => c.slug === id);
  if (!entry) return null;
  const [pivot, scrutins, fichesGroupe, gouvernements] = await Promise.all([
    fetchJson(`/data/profiles/${entry.slug}.pivot.json`),
    loadScrutins(),
    loadFichesGroupe(manifest, entry),
    loadGouvernements(manifest, entry.slug),
  ]);
  if (!pivot) return null;
  // L'index des amendements se charge APRÈS le profil : ce sont les
  // identifiants du mapping qui disent quelles législatures aller chercher.
  const amendements = await loadAmendementsPour(pivot);
  return buildCandidateView(
    pivot,
    entry,
    scrutins,
    amendements,
    fichesGroupe.filter(Boolean),
    gouvernements.filter(Boolean),
  );
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
