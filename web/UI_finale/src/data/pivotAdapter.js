// Transforme un profil pivot individuel (schema_pivot.py) ou un profil de
// groupe (schema_groupe.py) en objets directement consommables par
// CandidateProfile.jsx / GroupProfile.jsx.
//
// La logique de classification (ancienneté, responsabilités dédupliquées,
// position dans l'hémicycle, thème dominant) reprend celle déjà validée dans
// web/v3/js (render.js, utils.js) pour rester cohérente avec les règles
// éditoriales (AGENTS.md §2) : jamais de score, une donnée manquante reste
// "N/D", jamais 0 par défaut.

const MS_PER_YEAR = 365.25 * 24 * 3600 * 1000;

const RESPONSIBILITY_CATEGORIES = ['commission', 'extra_parlementaire', 'groupe_amitie'];
const ROLE_PRIORITY = [
  'président', 'présidente', 'co-président', 'co-présidente',
  'vice-président', 'vice-présidente', 'rapporteur', 'co-rapporteur', 'rapporteure',
];

const THEME_RULES = {
  Santé: ['santé', 'hopital', 'hôpital', 'malad', 'soin', 'medec', 'médec', 'cancer'],
  Environnement: ['climat', 'environ', 'biodivers', 'energie', 'énergie', 'carbone', 'pollution', 'écologi'],
  Économie: ['budget', 'fiscal', 'impôt', 'impot', 'entreprise', 'travail', 'emploi', 'financ'],
  Éducation: ['éduc', 'ecole', 'école', 'universit', 'apprentiss', 'scolair'],
  Sécurité: ['sécurit', 'police', 'défense', 'defense', 'terror', 'justice pénale', 'violence'],
  Institutions: ['constitution', 'assemblée', 'assemblee', 'sénat', 'senat', 'scrutin', 'loi organique', 'collectivités'],
  Europe: ['europe', 'union européenne', 'ue', 'international', 'onu', 'otan', 'étrang', 'maghreb', 'afrique'],
  Social: ['retraite', 'logement', 'social', 'pauvret', 'solidarit', 'sécurité sociale', 'égalité', 'salaire'],
};
const DEFAULT_THEME = 'Institutions';

const TEXT_STAGE_LABELS = {
  examine_commission: 'Examinée en commission',
  inscrit_ordre_jour: "Inscrite à l'ordre du jour",
  discute_seance: 'Discutée en séance',
  adopte: 'Adoptée',
  promulgue: 'Promulguée',
};
const DEBATED_TEXT_STAGES = new Set(Object.keys(TEXT_STAGE_LABELS));
const TEXT_ROLES = new Set(['auteur', 'rapporteur', 'co-rapporteur']);

const HEMICYCLE_LABELS = {
  majorite: 'Majorité',
  opposition: 'Opposition',
  gouvernement: 'Gouvernement',
  mixte: 'Non distingué',
  indetermine: 'Non distingué',
};

const CHAMBRE_LABELS = { AN: 'Député', Senat: 'Sénateur', PE: 'Député européen', mairie: 'Maire' };

const AMENDMENT_OUTCOME_KEYS = ['adopté', 'rejeté', 'retiré', 'tombé', 'irrecevable', 'non_soutenu'];
const AMENDMENT_OUTCOME_LABELS = {
  adopté: 'Adoptés', rejeté: 'Rejetés', retiré: 'Retirés',
  tombé: 'Tombés', irrecevable: 'Irrecevables', non_soutenu: 'Non soutenus',
};

// Libellés des catégories de mandats_agreges (group_profile.MANDATS_AGREGES_CATEGORIES).
// Périmètre élargi par #382/#386 : avant cette taxonomie, commissions
// d'enquête, missions d'information, groupes d'études et délégations
// s'affichaient tous sous « Commission » — ce qui trompait le lecteur sur la
// nature du mandat (AGENTS.md §2.8). Chaque catégorie produite par le backend
// doit avoir son libellé ici ; le repli sur la clé technique en fin de fichier
// n'est qu'un filet, jamais un affichage acceptable.
const MANDAT_CATEGORY_LABELS = {
  commission: 'Commission',
  commission_enquete: "Commission d'enquête",
  mission_information: "Mission d'information",
  groupe_etudes: "Groupe d'études",
  delegation: 'Délégation',
  groupe_amitie: "Groupe d'amitié",
  extra_parlementaire: 'Engagement extra-parlementaire',
};

// Ordre d'affichage des catégories : les instances où l'appartenance est la
// plus significative éditorialement d'abord. À volume élevé (mesuré : 430
// agrégats pour un groupe de 61 membres, et davantage depuis #384), le tri
// par nb_membres seul noyait les commissions permanentes sous les groupes
// d'études ; ce rang sert de critère primaire, le nb_membres départageant
// ensuite au sein d'une même catégorie.
const MANDAT_CATEGORY_ORDER = [
  'commission',
  'commission_enquete',
  'mission_information',
  'delegation',
  'groupe_etudes',
  'groupe_amitie',
  'extra_parlementaire',
];

// Ordre d'affichage + libellés (singulier/pluriel) des comptages par statut
// d'un texte gouvernemental (schema_gouvernement.py). Entiers bruts
// uniquement : jamais de jauge, donut ou pourcentage (AGENTS.md règle 2.1).
const GOVERNMENT_STATUT_ORDER = [
  'promulgue', 'adopte', 'adopte_cmp', 'rejete', 'retire', 'adopte_49_3', 'rejete_49_3', 'navette_en_cours', 'depose',
];
const GOVERNMENT_STATUT_LABELS = {
  promulgue: { singular: 'promulgué', plural: 'promulgués' },
  adopte: { singular: 'adopté', plural: 'adoptés' },
  rejete: { singular: 'rejeté', plural: 'rejetés' },
  retire: { singular: 'retiré', plural: 'retirés' },
  adopte_cmp: { singular: 'adopté (texte de CMP)', plural: 'adoptés (texte de CMP)' },
  adopte_49_3: { singular: 'adopté via 49.3', plural: 'adoptés via 49.3' },
  rejete_49_3: { singular: 'rejeté via 49.3', plural: 'rejetés via 49.3' },
  navette_en_cours: { singular: 'en navette', plural: 'en navette' },
  depose: { singular: 'déposé', plural: 'déposés' },
};
const GOVERNMENT_TEXTE_STATUT_LABELS = {
  depose: 'Déposé',
  navette_en_cours: 'Navette en cours',
  promulgue: 'Promulgué (publié au Journal officiel)',
  adopte: 'Adopté',
  adopte_cmp: 'Adopté (texte de commission mixte paritaire)',
  adopte_49_3: 'Adopté via 49.3',
  rejete: 'Rejeté',
  rejete_49_3: 'Rejeté via 49.3',
  retire: 'Retiré',
};

// Périmètre réellement couvert par les archives de dossiers législatifs
// ingérées (#399) : miroir de `src/couverture_dossiers.py` — législatures XV
// à XVII, la borne étant la première séance de la XV. Les deux valeurs
// doivent rester alignées ; `tests/test_couverture_dossiers.py` échoue si
// elles divergent.
//
// Avant cette borne, un `textes[]` vide n'est pas « aucun texte porté » :
// c'est une absence de source, qui ne doit jamais se lire comme un fait
// mesuré (AGENTS.md §2.5).
export const GOVERNMENT_TEXTS_COVERAGE_START = '2017-06-21';
export const GOVERNMENT_TEXTS_COVERAGE_LABEL =
  'législatures XV à XVII (dossiers déposés à partir du 21 juin 2017)';

/** Classe la période d'un gouvernement face à la couverture des archives ingérées.
 *  Retourne 'couverte' | 'partielle' | 'hors_couverture' | 'indeterminee',
 *  mêmes valeurs que `couverture_dossiers.statut_couverture_textes`. */
export function governmentTextsCoverage(periode = {}) {
  const debut = periode?.debut;
  const fin = periode?.fin;
  if (!debut) return 'indeterminee';
  if (debut >= GOVERNMENT_TEXTS_COVERAGE_START) return 'couverte';
  // `fin` absente = gouvernement en cours : période ouverte, donc à cheval
  // sur la borne — jamais remplacée par la date du jour (AGENTS.md §2.5).
  if (!fin) return 'partielle';
  return fin < GOVERNMENT_TEXTS_COVERAGE_START ? 'hors_couverture' : 'partielle';
}

function toDateMs(value) {
  if (!value) return 0;
  const t = Date.parse(value);
  return Number.isNaN(t) ? 0 : t;
}

function formatFrDate(value) {
  if (!value) return null;
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? null : d.toLocaleDateString('fr-FR');
}

function yearOf(value) {
  if (!value) return null;
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? null : d.getFullYear();
}

function detectTheme(...parts) {
  const text = parts.filter(Boolean).join(' ').toLowerCase();
  for (const [theme, needles] of Object.entries(THEME_RULES)) {
    if (needles.some((needle) => text.includes(needle))) return theme;
  }
  return DEFAULT_THEME;
}

// KPI 1 — ancienneté : mesure la durée du mandat électif, pas l'implication.
function computeMandateTenure(mandats) {
  const electifs = mandats.filter((m) => m.categorie === 'mandat_electif');
  const debuts = electifs.map((m) => toDateMs(m.debut)).filter(Boolean);
  if (!debuts.length) return null;
  const debutMin = Math.min(...debuts);
  const enCours = electifs.some((m) => m.actif);
  const fins = electifs.map((m) => toDateMs(m.fin)).filter(Boolean);
  const refEnd = enCours || !fins.length ? Date.now() : Math.max(...fins);
  const annees = Math.max(0, Math.round(((refEnd - debutMin) / MS_PER_YEAR) * 10) / 10);
  return { annees, enCours };
}

function bestRoleType(types) {
  for (const kw of ROLE_PRIORITY) {
    const match = types.find((t) => (t || '').toLowerCase().includes(kw));
    if (match) return match;
  }
  return types[0] || 'membre';
}

// KPI 2 — responsabilités : dédupliquées par intitulé pour ne pas gonfler le
// chiffre avec des réaffectations administratives internes.
function dedupeResponsibilities(mandats) {
  const relevant = mandats.filter((m) => RESPONSIBILITY_CATEGORIES.includes(m.categorie));
  const byLabel = new Map();
  for (const m of relevant) {
    const key = m.label || 'Responsabilité non précisée';
    if (!byLabel.has(key)) {
      byLabel.set(key, { label: key, types: [], debuts: [], fins: [], actif: false });
    }
    const entry = byLabel.get(key);
    entry.types.push(m.fonction);
    if (m.debut) entry.debuts.push(toDateMs(m.debut));
    if (m.fin) entry.fins.push(toDateMs(m.fin));
    if (m.actif) entry.actif = true;
  }
  return [...byLabel.values()].map((e) => {
    const debut = e.debuts.length ? Math.min(...e.debuts) : null;
    const fin = e.actif ? null : (e.fins.length ? Math.max(...e.fins) : null);
    return {
      label: e.label,
      type: bestRoleType(e.types),
      actif: e.actif,
      period: `${debut ? new Date(debut).getFullYear() : '?'} → ${e.actif ? "aujourd'hui" : (fin ? new Date(fin).getFullYear() : '?')}`,
    };
  });
}

// Position dans l'hémicycle : jamais dérivée sans source_url (AGENTS.md règle 6).
function hemicyclePeriods(mandats) {
  return mandats
    .filter((m) => m.position_dans_hemicycle && m.source_url)
    .map((m) => ({
      position: m.position_dans_hemicycle,
      debutMs: toDateMs(m.debut),
      finMs: m.actif || !m.fin ? Number.POSITIVE_INFINITY : toDateMs(m.fin),
    }))
    .filter((p) => Number.isFinite(p.debutMs));
}

function classifyDateInHemicycle(dateIso, periods) {
  if (!dateIso || !periods.length) return 'indetermine';
  const dateMs = toDateMs(dateIso);
  if (!Number.isFinite(dateMs) || !dateMs) return 'indetermine';
  const matching = periods.filter((p) => dateMs >= p.debutMs && dateMs <= p.finMs).map((p) => p.position);
  if (matching.includes('gouvernement')) return 'gouvernement';
  const hasMajorite = matching.includes('majorite');
  const hasOpposition = matching.includes('opposition');
  if (hasMajorite && hasOpposition) return 'mixte';
  if (hasMajorite) return 'majorite';
  if (hasOpposition) return 'opposition';
  return 'indetermine';
}

function classifyTexteInHemicycle(texte, periods) {
  const anchors = [texte.date_max, texte.date_min].filter(Boolean);
  if (!anchors.length) return 'indetermine';
  const labels = anchors.map((d) => classifyDateInHemicycle(d, periods));
  if (labels.includes('gouvernement')) return 'gouvernement';
  if (labels.includes('majorite') && labels.includes('opposition')) return 'mixte';
  if (labels.includes('majorite')) return 'majorite';
  if (labels.includes('opposition')) return 'opposition';
  return labels[0] || 'indetermine';
}

function isPublicCarriedText(texte) {
  return TEXT_ROLES.has(texte.role) && DEBATED_TEXT_STAGES.has(texte.stade_procedural);
}

function chambreLabel(chambre, actif) {
  const label = CHAMBRE_LABELS[chambre] || 'Élu(e)';
  return actif ? label : `Ancien(ne) ${label.toLowerCase()}`;
}

/**
 * Index des scrutins (#432) : `{ "an:16:4084": { date, texte, sort, … } }`.
 *
 * Un scrutin est identique pour tous ses votants, donc son méta vit une seule
 * fois dans `/data/scrutins.json` et le profil n'en garde que le mapping
 * `{ scrutin_id, position }`. Un profil ne se lit donc plus seul pour ses votes :
 * c'est le couplage assumé de cette normalisation (179,8 → 26,7 Mo).
 *
 * Un scrutin absent de l'index rend une entrée vide plutôt que de faire planter
 * la vue : une donnée manquante reste manquante, elle n'est pas inventée.
 */
function resolveScrutin(scrutinsIndex, scrutinId) {
  return (scrutinsIndex && scrutinId && scrutinsIndex[scrutinId]) || null;
}

/**
 * Joint le mapping du profil à l'index et rend des votes autoportants
 * `{ position, date, texte, sort }` — la forme que le reste de l'adaptateur
 * consommait avant #432.
 *
 * Les votes non résolus (`scrutin_id` null) portent leur enregistrement complet
 * sous `scrutin_non_resolu` : ils sont lus là, jamais écartés.
 */
function joinVotes(votes, scrutinsIndex) {
  return votes
    .map((v) => {
      // Repli sur le vote lui-même pour les pivots d'AVANT #432, qui portaient
      // encore le méta du scrutin. Le code est déployé avant que les données
      // ne soient régénérées : sans ce repli, tous les votes disparaîtraient
      // des vues entre les deux, sans erreur visible. À retirer une fois la
      // régénération committée.
      const scrutin = resolveScrutin(scrutinsIndex, v.scrutin_id) || v.scrutin_non_resolu
        || (v.date || v.texte ? v : null);
      if (!scrutin) return null;
      return {
        position: v.position,
        date: scrutin.date ?? null,
        texte: scrutin.texte ?? null,
        sort: scrutin.sort ?? null,
      };
    })
    .filter(Boolean);
}

/** Construit l'objet consommé par CandidateProfile.jsx à partir d'un profil pivot v1. */
export function buildCandidateView(pivot, manifestEntry, scrutinsIndex = null) {
  const mandats = pivot.mandats || [];
  const votes = joinVotes(pivot.votes || [], scrutinsIndex);
  const amendements = pivot.amendements || [];
  const textesPortes = pivot.textes_portes || [];
  const periods = hemicyclePeriods(mandats);

  const tenure = computeMandateTenure(mandats);
  const responsabilites = dedupeResponsibilities(mandats);
  const actif = mandats.some((m) => m.categorie === 'mandat_electif' && m.actif);

  // Votes publics : positions documentées uniquement (jamais absent/excusé/non_votant —
  // AGENTS.md règle 3, aucun taux ou fait individuel d'absence n'est publié).
  const positionVotes = votes.filter((v) => ['pour', 'contre', 'abstention'].includes(v.position));
  const votesByDate = [...positionVotes].sort((a, b) => toDateMs(b.date) - toDateMs(a.date));
  const voteItems = votesByDate.slice(0, 12).map((v) => ({
    titre: v.texte,
    position: v.position,
    meta: formatFrDate(v.date) || 'Date non renseignée',
  }));

  const themeCounts = {};
  for (const v of votesByDate) {
    const theme = detectTheme(v.texte);
    themeCounts[theme] = (themeCounts[theme] || 0) + 1;
  }
  const dominantTheme = Object.entries(themeCounts).sort((a, b) => b[1] - a[1])[0]?.[0] || null;

  const outcomeCounts = Object.fromEntries(AMENDMENT_OUTCOME_KEYS.map((k) => [k, 0]));
  for (const a of amendements) {
    if (Object.hasOwn(outcomeCounts, a.sort)) outcomeCounts[a.sort] += 1;
  }
  const outcomes = AMENDMENT_OUTCOME_KEYS.map((key) => ({
    key, label: AMENDMENT_OUTCOME_LABELS[key], count: outcomeCounts[key],
  }));

  const publicTextes = textesPortes.filter(isPublicCarriedText);
  const textes = publicTextes.map((t) => ({
    titre: t.titre,
    theme: detectTheme(t.titre),
    meta: `${TEXT_STAGE_LABELS[t.stade_procedural]} · ${HEMICYCLE_LABELS[classifyTexteInHemicycle(t, periods)]}${yearOf(t.date_max || t.date_min) ? ` · ${yearOf(t.date_max || t.date_min)}` : ''}`,
  }));

  const scopeCounts = { majorite: { textes: 0, amend: 0 }, opposition: { textes: 0, amend: 0 }, non_distingue: { textes: 0, amend: 0 } };
  const mergeBucket = (b) => (b === 'majorite' || b === 'opposition' ? b : 'non_distingue');
  for (const t of publicTextes) scopeCounts[mergeBucket(classifyTexteInHemicycle(t, periods))].textes += 1;
  for (const a of amendements) scopeCounts[mergeBucket(classifyDateInHemicycle(a.date, periods))].amend += 1;
  const scopeBuckets = [
    { label: 'Majorité', textes: scopeCounts.majorite.textes, amend: scopeCounts.majorite.amend },
    { label: 'Opposition', textes: scopeCounts.opposition.textes, amend: scopeCounts.opposition.amend },
    { label: 'Non distingué', textes: scopeCounts.non_distingue.textes, amend: scopeCounts.non_distingue.amend },
  ];

  return {
    id: manifestEntry.slug,
    nom: pivot.nom,
    parti: pivot.parti || manifestEntry.parti || '',
    groupe: pivot.groupe || '',
    profession: pivot.identite?.profession || chambreLabel(pivot.chambre, actif),
    actif,
    kpis: {
      anciennete: tenure ? `${tenure.annees}\u00a0${tenure.annees <= 1 ? 'an' : 'ans'}` : 'N/D',
      responsabilites: String(responsabilites.length),
      votes: voteItems.length ? String(positionVotes.length) : 'N/D',
      theme: dominantTheme || 'N/D',
    },
    votes: voteItems,
    outcomes,
    mandats: mandats
      .filter((m) => m.categorie === 'mandat_electif')
      .map((m) => ({ label: m.label, period: `${yearOf(m.debut) || '?'} → ${m.actif ? "aujourd'hui" : (yearOf(m.fin) || '?')}` })),
    responsabilites: responsabilites.map((r) => ({ label: r.label, period: r.period })),
    textes,
    scopeBuckets,
  };
}

/** Construit l'objet consommé par GroupProfile.jsx à partir d'un profil de groupe v1. */
export function buildGroupView(groupe, scrutinsIndex = null) {
  const rosterTotal = groupe.meta?.couverture_roster?.roster_total ?? groupe.effectif?.actuel ?? 0;
  const profilsDisponibles = groupe.meta?.couverture_roster?.profils_disponibles ?? (groupe.membres || []).length;
  const coveragePct = rosterTotal ? Math.round((profilsDisponibles / rosterTotal) * 100) : 0;

  // `date`, `texte` et `sort` ont migré vers l'index partagé (#432) : ce sont
  // des champs du scrutin, qui étaient recopiés dans chacun des groupes l'ayant
  // voté. Les 4 104 scrutins des groupes sont inclus dans ceux des profils —
  // un seul index sert les deux.
  const cohesionVotes = groupe.cohesion_votes || [];
  const votes = cohesionVotes.slice(0, 12).map((v) => {
    // Même repli transitoire que pour les profils : les fichiers de groupe
    // d'avant #432 portent encore `date`/`texte` dans l'entrée.
    const scrutin = resolveScrutin(scrutinsIndex, v.scrutin_id) || v;
    return {
      date: formatFrDate(scrutin?.date) || 'Date non renseignée',
      texte: scrutin?.texte ?? null,
      position: v.position_majoritaire,
      coherence: v.taux_coherence != null ? Math.round(v.taux_coherence * 100) : null,
      quorum: v.quorum_atteint,
    };
  });

  const agg = groupe.amendements_agreges || {};
  const parDepute = agg.par_type_deposant?.depute;
  const amendmentSegments = AMENDMENT_OUTCOME_KEYS.map((key) => {
    const map = {
      adopté: 'nb_adoptes', rejeté: 'nb_rejetes', irrecevable: 'nb_irrecevables',
    };
    const count = map[key] ? (agg[map[key]] ?? 0) : 0;
    return { key, label: AMENDMENT_OUTCOME_LABELS[key], count };
  });

  const tags = (groupe.tags_thematiques_agreges || [])
    .slice(0, 20) // mots-clés bruts, non harmonisés (voir schema_pivot.py) : échantillon, pas une liste exhaustive
    .map((t) => ({ label: t.tag, count: t.nb_membres_porteurs }));

  // mandats_agreges : le backend trie par nb_membres desc puis categorie/label
  // asc. Depuis #382/#386 le volume et la diversité de catégories ont
  // fortement augmenté (7 catégories au lieu de 3) : on re-trie ici par rang
  // de catégorie d'abord, pour que les commissions permanentes ne soient plus
  // noyées sous les groupes d'études, bien plus nombreux. Le nb_membres reste
  // le critère au sein d'une catégorie.
  const mandatsAgreges = (groupe.mandats_agreges || [])
    .map((m) => ({
      categorie: m.categorie,
      categorieLabel: MANDAT_CATEGORY_LABELS[m.categorie] || m.categorie,
      label: m.label,
      nbMembres: m.nb_membres,
      nbMembresActifs: m.nb_membres_actifs,
      parFonction: Object.entries(m.par_fonction || {})
        .sort((a, b) => b[1] - a[1])
        .map(([fonction, count]) => ({ fonction, count })),
    }))
    .sort((a, b) => {
      const ra = MANDAT_CATEGORY_ORDER.indexOf(a.categorie);
      const rb = MANDAT_CATEGORY_ORDER.indexOf(b.categorie);
      // Une catégorie inconnue de l'ordre passe en dernier plutôt qu'en tête
      // (indexOf renverrait -1), sans masquer les catégories connues.
      const ka = ra === -1 ? MANDAT_CATEGORY_ORDER.length : ra;
      const kb = rb === -1 ? MANDAT_CATEGORY_ORDER.length : rb;
      if (ka !== kb) return ka - kb;
      if (b.nbMembres !== a.nbMembres) return b.nbMembres - a.nbMembres;
      return (a.label || '').localeCompare(b.label || '', 'fr');
    });

  return {
    id: groupe.groupe_id,
    title: groupe.groupe_nom,
    kicker: `${groupe.chambre === 'AN' ? 'Assemblée nationale' : 'Sénat'} · Législature ${groupe.legislature} · ${rosterTotal} membres`,
    profilsDisponibles,
    rosterTotal,
    coveragePct,
    kpis: [
      { value: String(rosterTotal), label: 'Effectif actuel', caveat: 'Effectif déclaré par le groupe lui-même ; peut inclure des apparentés.' },
      { value: String(cohesionVotes.length), label: 'Scrutins couverts', caveat: 'Mesure la couverture des scrutins agrégés, pas la qualité du vote.' },
      { value: parDepute?.taux_adoption != null ? `${Math.round(parDepute.taux_adoption * 1000) / 10} %` : 'N/D', label: "Taux d'adoption (député⋅es)", caveat: 'Ne pas comparer entre groupes de taille différente ni aux amendements gouvernement/rapporteur.' },
    ],
    votes,
    tags,
    mandatsAgreges,
    amendmentSegments,
    amendmentsDeposedTotal: parDepute?.nb_amendements ?? 0,
    amendmentsAllDeposantsTotal: agg.nb_amendements ?? 0,
    members: (groupe.membres || []).map((m) => ({
      nom: m.nom,
      actif: m.actif,
    })),
  };
}

/** Construit l'objet consommé par GovernmentProfile.jsx à partir d'un profil de gouvernement v1 (schema_gouvernement.py). */
export function buildGovernmentView(gouvernement) {
  const periode = gouvernement.periode || {};
  const membres = gouvernement.membres || [];
  const textes = gouvernement.textes || [];
  const parStatut = gouvernement.comptages?.par_statut || {};

  const kicker = periode.actif
    ? `En fonction depuis le ${formatFrDate(periode.debut) || 'date non renseignée'}`
    : `Du ${formatFrDate(periode.debut) || '?'} au ${formatFrDate(periode.fin) || '?'}`;

  // Comptages par statut : liste de nombres bruts uniquement, jamais un %
  // ou une jauge (AGENTS.md règle 2.1) — statuts à 0 omis pour lisibilité.
  const statutBadges = GOVERNMENT_STATUT_ORDER
    .filter((key) => (parStatut[key] || 0) > 0)
    .map((key) => {
      const count = parStatut[key];
      const labels = GOVERNMENT_STATUT_LABELS[key];
      return { key, count, label: count === 1 ? labels.singular : labels.plural };
    });

  const textesView = [...textes]
    .sort((a, b) => toDateMs(b.date_depot) - toDateMs(a.date_depot))
    .map((t) => ({
      dossierId: t.dossier_id,
      titre: t.titre,
      statutLabel: GOVERNMENT_TEXTE_STATUT_LABELS[t.statut] || t.statut,
      chambre: t.chambre_depot_initial === 'AN' ? 'Assemblée nationale' : 'Sénat',
      sort493: t.sort_49_3 === true,
      meta: formatFrDate(t.date_depot) || 'Date de dépôt non renseignée',
      sourceUrl: t.source_url,
    }));

  const membresView = membres.map((m) => ({
    nom: m.nom,
    portefeuille: m.portefeuille,
    actif: m.actif,
    period: `${yearOf(m.debut) || '?'} → ${m.actif ? "aujourd'hui" : (yearOf(m.fin) || '?')}`,
  }));

  // Couverture des archives de dossiers : une période antérieure à la borne
  // n'autorise aucune conclusion sur les textes portés (#399).
  const couvertureStatut = governmentTextsCoverage(periode);

  return {
    id: String(gouvernement.gouvernement_id || '').replace(/^gouvernement:/, ''),
    title: gouvernement.nom,
    kicker,
    premierMinistre: gouvernement.premier_ministre?.nom || null,
    actif: Boolean(periode.actif),
    membres: membresView,
    textes: textesView,
    statutBadges,
    textesCouverture: {
      statut: couvertureStatut,
      borne: GOVERNMENT_TEXTS_COVERAGE_START,
      label: GOVERNMENT_TEXTS_COVERAGE_LABEL,
    },
  };
}
