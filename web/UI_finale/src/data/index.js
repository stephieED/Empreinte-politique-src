import {
  buildCandidateView,
  buildGovernmentView,
  legislatureDeAmendementId,
} from './pivotAdapter';

export const DEFAULT_CANDIDATE_ID = 'jean-luc-melenchon';
/* Une LIGNÉE, plus une fiche de législature (#329, #836) : l'adresse d'un
 * groupe vient de son `lignee_id` déclaré, et ne bouge pas quand il change de
 * sigle ou de législature. */
export const DEFAULT_GROUP_ID = 'AN-SOC';
export const DEFAULT_GOVERNMENT_ID = 'LECORNU_II';

let manifestPromise = null;
let scrutinsPromise = null;
let couverturePromise = null;
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
/**
 * Ce que le dépôt porte, tous profils confondus (/couverture).
 *
 * Projection calculée au build par `scripts/couverture-corpus.mjs` — 32 Ko là
 * où la page devrait sinon lire les 743 profils. Mémoïsée, et non bloquante :
 * un échec de chargement rend `null`, la page dit qu'elle ne peut pas afficher
 * la couverture plutôt que d'en approcher une.
 */
export function loadCouverture() {
  if (!couverturePromise) {
    couverturePromise = fetch('/data/couverture.json')
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`couverture.json : HTTP ${r.status}`))));
  }
  return couverturePromise;
}

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
        // se compteraient sur les textes visés — 47 là où il y a 25 dossiers
        // chez Jérôme Guedj — et aucun dossier ne pourrait être NOMMÉ au
        // lecteur, ce qui est l'essentiel de ce que la section publie.
        .then((d) => ({ amendements: d?.amendements || {}, textes: d?.textes || {} }))
        .catch(() => ({ amendements: {}, textes: {} })),
    );
  }
  return amendementsPromises.get(legislature);
}

/**
 * Commission saisie au fond, par dossier législatif (#328).
 *
 * Un seul fichier, chargé une fois : la commission est une propriété du
 * DOSSIER, pas du texte visé — la ranger dans la table `textes` de chaque
 * législature la recopierait une fois par texte visé et la dupliquerait entre
 * législatures.
 *
 * Non bloquant, et l'absence n'est pas comblée : sans cette table, « L'essentiel »
 * n'affiche simplement pas la répartition par commission. Elle n'est jamais
 * déduite d'un intitulé de dossier — ce serait une classification construite
 * ici (AGENTS.md §2 règle 1).
 */
let commissionsPromise = null;

function loadCommissionsDossiers() {
  if (!commissionsPromise) {
    commissionsPromise = fetch('/data/commissions_dossiers.json')
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => d?.commissions || null)
      .catch(() => null);
  }
  return commissionsPromise;
}

/**
 * Dossier législatif d'un scrutin, statut du texte et 49.3 (#758).
 *
 * Un scrutin ne porte AUCUNE référence législative — mesuré : 0 des 18 311
 * scrutins de l'archive portent `objet.referenceLegislative`. La jointure se
 * fait donc dans l'autre sens, depuis les `voteRefs` des actes du dossier, et
 * `src/build_scrutins_dossiers.py` la fige dans ce fichier : 715 scrutins vers
 * 561 dossiers, 72 Ko.
 *
 * Sans lui, « ce qu'il a voté » perd la matière du texte et son statut final ;
 * elle ne les remplace pas — une matière déduite d'un intitulé serait une
 * classification construite ici (§2 règle 1).
 *
 * Non bloquant et mémoïsé, comme les autres index partagés.
 */
let scrutinsDossiersPromise = null;

function loadScrutinsDossiers() {
  if (!scrutinsDossiersPromise) {
    scrutinsDossiersPromise = fetch('/data/scrutins_dossiers.json')
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => (d ? { scrutins: d.scrutins || {}, dossiers: d.dossiers || {} } : null))
      .catch(() => null);
  }
  return scrutinsDossiersPromise;
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
    /* Les fiches de groupe dont la personne est membre, appariées par
     * `sync-data`. Le filtre de la barre des candidats les lit : il était
     * servi par le manifeste et perdu ici, si bien que sélectionner un groupe
     * ne retenait AUCUN candidat (constaté en câblant les lignées, #329). */
    groupIds: c.groupIds || [],
    parti: c.parti,
    // Calculé par `scripts/sync-data.mjs` : « AN » dans `chambres`, ou au moins
    // un mandat de catégorie `fonction_gouvernementale` (#328). L'ordre de la
    // liste est déjà alphabétique à la source — l'UI ne retrie pas, sans quoi
    // deux tris cohabiteraient.
    mandatAnOuGouvernement: c.mandatAnOuGouvernement !== false,
  }));
}

export async function getGroupsList() {
  const manifest = await loadManifest();
  /* UNE ENTRÉE PAR LIGNÉE DÉCLARÉE (#836), dans l'ordre alphabétique de son nom.
   *
   * Les lignées viennent du backend (`pivot_data/lignees/`, `lignee_id`
   * déclaré), plus d'un chaînage de `succede_a` refait ici : deux définitions
   * du même objet divergent au premier cas qu'une seule prévoit — une scission.
   *
   * `fiches` accompagne l'entrée parce que le FILTRE des candidats en dépend :
   * sélectionner « Socialistes » retient les membres de n'importe lequel des
   * quatre maillons. */
  return (manifest.lignees || [])
    .map((l) => ({
      id: l.id,
      title: l.nom,
      chambre: l.chambre,
      fiches: l.fiches || [],
    }))
    .sort((a, b) => a.title.localeCompare(b.title, 'fr', { sensitivity: 'base' }));
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

export async function getCandidateProfile(id) {
  const manifest = await loadManifest();
  const entry = manifest.candidates.find((c) => c.slug === id);
  if (!entry) return null;
  const [pivot, scrutins, fichesGroupe, commissions, scrutinsDossiers] = await Promise.all([
    fetchJson(`/data/profiles/${entry.slug}.pivot.json`),
    loadScrutins(),
    loadFichesGroupe(manifest, entry),
    loadCommissionsDossiers(),
    loadScrutinsDossiers(),
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
    commissions,
    scrutinsDossiers,
    // TOUS les gouvernements, pas les seuls dont la personne fut membre : « ce
    // qu'il a voté » découpe la carrière par gouvernement en place, ce qui
    // demande la chronologie entière. Les dates vivent déjà dans le manifeste,
    // aucune fiche supplémentaire n'est téléchargée.
    manifest.gouvernements || [],
  );
}

/**
 * La fiche d'une lignée : sa PROJECTION de build (`scripts/vue-lignee.mjs`),
 * jamais la fiche de `pivot_data/lignees/` ni ses maillons — 134 Ko pour la
 * lignée socialiste, contre 5,3 Mo de fiche de lignée et 11 Mo de maillons.
 * Tout ce que la page affiche y est déjà calculé, par les règles de
 * `utils/groupe.js` et `utils/lignee.js` que ce navigateur importe aussi.
 */
export async function getLigneeProfile(id) {
  const manifest = await loadManifest();
  const entry = (manifest.lignees || []).find((l) => l.id === id);
  if (!entry) return null;
  return fetchJson(`/data/lignees/${entry.fichier}`);
}

/**
 * La lignée d'une fiche de groupe — pour les adresses d'avant #329
 * (`/groupes/AN-SOC-17`), qui mènent désormais à la lignée entière. `null`
 * quand l'identifiant n'est pas une fiche de groupe connue.
 */
export async function ligneeDeLaFiche(idDeFiche) {
  const manifest = await loadManifest();
  return (manifest.groupes || []).find((g) => g.id === idDeFiche)?.lignee ?? null;
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
