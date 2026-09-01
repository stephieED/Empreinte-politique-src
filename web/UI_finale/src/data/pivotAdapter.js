// Transforme un profil pivot individuel (schema_pivot.py) ou un profil de
// groupe (schema_groupe.py) en objets directement consommables par
// CandidateProfile.jsx / GroupProfile.jsx.
//
// La logique de classification (ancienneté, responsabilités dédupliquées,
// position dans l'hémicycle, thème dominant) reprend celle déjà validée dans
// web/v3/js (render.js, utils.js) pour rester cohérente avec les règles
// éditoriales (AGENTS.md §2) : jamais de score, une donnée manquante reste
// "N/D", jamais 0 par défaut.
//
// Les règles de lecture ne sont PAS réécrites ici : les six fondations du lot 1
// vivent dans `utils/lecture.js` (#326) et celles de la fiche de groupe dans
// `utils/groupe.js` (#329). Cet adaptateur met en forme, il n'arbitre pas.

import {
  INSTITUTION_PARLEMENT,
  agregerAmendements,
  appartenancesGouvernementales,
  bornesDuParcours,
  causeListeVide,
  couvertureDesListes,
  directionQuestionsGouvernement,
  ecartsAvecLeGroupe,
  faisceau,
  fonctionsExercees,
  interventionsParNature,
  limitesDeclarees,
  regimeQualiteOrateur,
  rolesDuParcours,
  siegesElectifs,
  textesPortes,
  voixDuProfil,
  votesDuProfil,
} from '../utils/profilCandidat';
import {
  NB_SCRUTINS_AFFICHES,
  REFUS_FICHE_GROUPE,
  couvertureRoster,
  dateDeReference,
  decomptesCohesion,
  effectifDuGroupe,
  etiquettesThematiques,
  excusesRenseignees,
  quorumDuScrutin,
  ratioCohesion,
  siegeEtPasse,
  troncatureCohesion,
  troncatureTags,
} from '../utils/groupe';

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
// par le seul nombre de membres noyait les commissions permanentes sous les
// groupes d'études ; ce rang sert de critère primaire, le nombre de membres
// siégeant départageant ensuite au sein d'une même catégorie (#656).
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
        // `scrutin_id` et `scrutin` sont conservés depuis #328 : la sélection
        // des votes « sur l'ensemble » (`isWholeTextVote`, lot 1) lit
        // `type_vote` et `texte` sur le scrutin, et la comparaison avec la
        // fiche de groupe se fait sur l'identifiant. Les recopier à plat
        // dupliquerait le méta que #432 a justement sorti des profils.
        scrutin_id: v.scrutin_id ?? scrutin.id ?? null,
        scrutin,
        position: v.position,
        date: scrutin.date ?? null,
        texte: scrutin.texte ?? null,
        sort: scrutin.sort ?? null,
      };
    })
    .filter(Boolean);
}

/**
 * Législature portée par un identifiant d'amendement (`an:AMANR5L17…` → `'17'`).
 *
 * Lecture structurelle de l'identifiant, pas une déduction depuis la date :
 * c'est l'AN qui l'y écrit. `null` si la forme n'est pas reconnue — on ne
 * devine pas une législature pour aller chercher le mauvais fichier.
 */
export function legislatureDeAmendementId(amendementId) {
  const m = /^an:AMANR5L(\d+)/.exec(amendementId || '');
  return m ? m[1] : null;
}

/**
 * Index des amendements (#431) : `{ '17': { 'an:AMANR5L17…': { sort, date, … } } }`.
 *
 * Indexé **par législature** parce que c'est ainsi qu'il est stocké et chargé :
 * un fichier global pèserait 128,8 Mo, au-delà de la limite GitHub de 100 Mo
 * par blob, et l'UI n'a besoin que des législatures que le profil affiché
 * référence. La résolution reste en O(1) : la législature se lit dans
 * l'identifiant.
 */
function resolveAmendement(amendementsIndex, amendementId) {
  if (!amendementsIndex || !amendementId) return null;
  const legislature = legislatureDeAmendementId(amendementId);
  const parLegislature = legislature != null ? amendementsIndex[legislature] : null;
  return (parLegislature?.amendements && parLegislature.amendements[amendementId]) || null;
}

/**
 * Titre et clé de dossier du texte visé par un amendement.
 *
 * L'index par législature porte un bloc `textes` : `texte_vise` → `{ dossier_id,
 * titre }`. La concentration se compte sur le DOSSIER, pas sur le `texte_vise` :
 * un même dossier législatif porte plusieurs textes visés successifs (le projet
 * déposé, le texte de commission…), et compter ces derniers séparément
 * éclaterait en trois dossiers ce que le lecteur voit comme une seule bataille.
 * Mesuré sur Jérôme Guedj : 47 `texte_vise` pour 34 dossiers.
 */
function resolveDossier(amendementsIndex, amendementId, texteVise) {
  if (!amendementsIndex || !texteVise) return null;
  const legislature = legislatureDeAmendementId(amendementId);
  const parLegislature = legislature != null ? amendementsIndex[legislature] : null;
  return (parLegislature?.textes && parLegislature.textes[texteVise]) || null;
}

/**
 * Itère les amendements d'un profil joints à l'index — **un générateur**.
 *
 * Volontairement paresseux : rendre un tableau de la forme jointe
 * reconstruirait exactement la forme plate que #431 supprime (810 552
 * enregistrements complets là où il y en a 207 238 distincts), avec le facteur
 * ~21 et l'OOM de #377.
 *
 * Un amendement introuvable rend `null` : la vue en fait une donnée manquante,
 * jamais une valeur inventée.
 */
function* joinAmendements(amendements, amendementsIndex) {
  for (const a of amendements || []) {
    // Repli sur l'entrée elle-même pour les pivots d'AVANT #431, qui portaient
    // encore le méta de l'amendement. Le code est déployé avant que les données
    // ne soient régénérées : sans ce repli, tous les amendements disparaîtraient
    // des vues entre les deux, sans erreur visible. À retirer une fois la
    // régénération committée.
    const amendement = resolveAmendement(amendementsIndex, a.amendement_id)
      || a.amendement_non_resolu
      || (a.sort || a.date ? a : null);
    if (!amendement) continue;

    // `role_signataire` est le SEUL champ propre au signataire (#431) : il vit
    // dans le mapping du profil, pas dans l'index partagé. Sans lui, les 11 906
    // cosignatures de Jérôme Guedj se compteraient avec ses 2 429 dépôts comme
    // auteur principal — deux natures d'acte additionnées, ce qu'interdit la
    // trame, et un dénominateur faux (AGENTS.md §6).
    //
    // La projection reste MINIMALE, et c'est délibéré : rendre `amendement`
    // enrichi rematérialiserait la forme plate de #377. Neuf champs, pas le
    // document.
    const dossier = resolveDossier(amendementsIndex, a.amendement_id, amendement.texte_vise);
    yield {
      role_signataire: a.role_signataire ?? null,
      legislature: legislatureDeAmendementId(a.amendement_id),
      sort: amendement.sort ?? null,
      base_juridique_irrecevabilite: amendement.base_juridique_irrecevabilite ?? null,
      date: amendement.date ?? null,
      texte_vise: amendement.texte_vise ?? null,
      dossier_id: dossier?.dossier_id ?? null,
      dossier_titre: dossier?.titre ?? null,
    };
  }
}

/* ── Livrable : les gouvernements dont la personne a été membre (#328) ───────
 *
 * Une SECTION À PART, placée avant les actes personnels. La maquette d'août
 * rangeait ce bloc dans « ce qu'il a proposé » en portant la phrase « ces textes
 * engagent le gouvernement, pas la personne » : la place contredisait la
 * phrase, et la place gagne.
 *
 * En ENSEMBLES, jamais en liste attribuée — un Premier ministre signe les 25
 * textes de son gouvernement, lui en attribuer un personnellement ne voudrait
 * rien dire. Et jamais additionné aux amendements ou aux textes portés : 49
 * amendements et 25 textes de gouvernement ne font pas 74.
 */
const STATUTS_GOUVERNEMENT = [
  { cle: 'promulgue', label: 'promulgués' },
  { cle: 'adopte_cmp', label: 'adoptés en CMP' },
  { cle: 'adopte', label: 'adoptés' },
  { cle: 'navette_en_cours', label: 'en navette' },
  { cle: 'rejete', label: 'rejetés' },
  { cle: 'retire', label: 'retirés' },
  { cle: 'depose', label: 'déposés' },
];

// Les deux statuts « 49.3 » restent HORS de la répartition colorée : un texte
// adopté sans vote est un fait de procédure, jamais une issue de scrutin
// (AGENTS.md §2 règle 4). Ils sont comptés séparément et dits en toutes lettres.
const STATUTS_49_3 = ['adopte_49_3', 'rejete_49_3'];

function buildGouvernements(slug, gouvernements) {
  return (gouvernements || [])
    .filter((g) => (g.membres || []).some((m) => m.membre_id === slug))
    .map((g) => {
      const comptages = g.comptages?.par_statut || {};
      const total = (g.textes || []).length;
      const fonctions = (g.membres || [])
        .filter((m) => m.membre_id === slug)
        .map((m) => ({ portefeuille: m.portefeuille, debut: m.debut, fin: m.fin }))
        .sort((a, b) => String(a.debut || '').localeCompare(String(b.debut || '')));
      const chef = g.premier_ministre?.membre_id === slug
        || fonctions.some((f) => /^premier ministre$/i.test(f.portefeuille || ''));
      return {
        id: g.gouvernement_id,
        nom: g.nom,
        debut: g.periode?.debut ?? null,
        fin: g.periode?.fin ?? null,
        actif: Boolean(g.periode?.actif),
        chef,
        fonctions,
        total,
        statuts: STATUTS_GOUVERNEMENT.filter((st) => comptages[st.cle] > 0).map((st) => ({
          ...st,
          n: comptages[st.cle],
        })),
        adoptesSansVote: STATUTS_49_3.reduce((n, cle) => n + (comptages[cle] || 0), 0),
        // Les textes ne sont nommés que pour le gouvernement dont la personne
        // était le chef : ailleurs, nommer un texte reviendrait à le lui
        // attribuer alors qu'un autre ministre l'a porté.
        textes: chef
          ? (g.textes || [])
              .slice()
              .sort((a, b) => String(b.date_dernier_evenement || '').localeCompare(String(a.date_dernier_evenement || '')))
              .map((t) => ({
                titre: t.titre,
                statut: t.statut,
                date: t.date_dernier_evenement ?? t.date_depot ?? null,
                sansVote: Boolean(t.sort_49_3),
              }))
          : null,
      };
    })
    .sort((a, b) => String(a.debut || '').localeCompare(String(b.debut || '')));
}

/** Construit l'objet consommé par CandidateProfile.jsx à partir d'un profil pivot v1.
 *
 * Lot 2 (#328) : les règles de lecture propres au profil candidat vivent dans
 * `utils/profilCandidat.js`, les six fondations communes dans `utils/lecture.js`.
 * Cet adaptateur les APPELLE, il n'en écrit pas de seconde version.
 *
 * Sept emplacements, identiques pour les treize candidats déclarés, dans le
 * même ordre. Ce qui varie est le contenu, jamais la forme — et un emplacement
 * vide dit pourquoi il l'est.
 */
export function buildCandidateView(
  pivot,
  manifestEntry,
  scrutinsIndex = null,
  amendementsIndex = null,
  fichesGroupe = null,
  gouvernements = null,
) {
  const mandats = pivot.mandats || [];
  const votes = joinVotes(pivot.votes || [], scrutinsIndex);
  const interventions = pivot.interventions || [];

  const { roles, nbLignes } = rolesDuParcours(mandats);
  const sieges = siegesElectifs(mandats);
  const appartenances = appartenancesGouvernementales(mandats);
  const bornes = bornesDuParcours(roles);

  // La position déclarée du groupe à une date donnée : c'est ce qui permet de
  // la coller au chiffre qu'elle explique, plutôt que de la renvoyer en légende.
  const periodesPosition = roles
    .filter((r) => r.institution === INSTITUTION_PARLEMENT && r.position)
    .map((r) => ({ debut: r.debut, fin: r.fin, position: r.position }));
  const positionALaDate = (date) =>
    periodesPosition.find((p) => p.debut <= date && date <= p.fin)?.position ?? null;

  const amendements = agregerAmendements(
    joinAmendements(pivot.amendements || [], amendementsIndex),
    positionALaDate,
  );
  const textes = textesPortes(pivot.textes_portes);
  const fonctions = fonctionsExercees(mandats);
  const qualite = regimeQualiteOrateur(interventions);
  const questions = directionQuestionsGouvernement(interventions, appartenances);
  const lectureVotes = votesDuProfil(
    votes,
    appartenances,
    roles.filter((r) => r.institution === INSTITUTION_PARLEMENT),
  );
  const ecarts = ecartsAvecLeGroupe(votes, fichesGroupe);

  return {
    id: manifestEntry.slug,
    nom: pivot.nom,
    parti: pivot.parti || manifestEntry.parti || '',
    groupe: pivot.groupe || '',
    // La voix du texte vient de `identite.civilite`, la seule source du genre
    // dans le corpus. Absente, la page n'en invente pas : elle parle de « cette
    // personne » (§2 règle 5).
    voix: voixDuProfil(pivot.identite?.civilite ?? null),
    profession: pivot.identite?.profession || null,
    naissance: pivot.identite?.date_naissance
      ? { date: pivot.identite.date_naissance, lieu: pivot.identite.lieu_naissance ?? null }
      : null,
    sourceUrl: pivot.identite?.source_url ?? null,
    licence: pivot.meta?.licence_donnees ?? null,

    faisceau: faisceau({
      interventions,
      concentration: amendements.concentration,
      fonctions,
      questions,
      qualite,
      textes,
    }),

    parcours: { roles, nbLignes, bornes },
    fonctions,
    gouvernements: buildGouvernements(manifestEntry.slug, gouvernements),
    amendements,
    textes,
    interventions: {
      total: interventions.length,
      natures: interventionsParNature(interventions),
      qualite,
      questions,
    },
    votes: lectureVotes,
    ecarts,

    // La cause d'un vide, par liste : `ListeVide` (lot 1) la rend en phrase.
    // Elle est calculée ici pour n'être lue qu'une fois, pas dans six branches
    // du composant.
    causes: {
      mandats: causeListeVide(pivot.couverture?.mandats),
      votes: causeListeVide(pivot.couverture?.votes),
      amendements: causeListeVide(pivot.couverture?.amendements),
      textes_portes: causeListeVide(pivot.couverture?.textes_portes),
      interventions: causeListeVide(pivot.couverture?.interventions),
    },

    couverture: couvertureDesListes(pivot.couverture, {
      mandats: mandats.length,
      votes: (pivot.votes || []).length,
      amendements: (pivot.amendements || []).length,
      textes_portes: (pivot.textes_portes || []).length,
      interventions: interventions.length,
    }),
    limites: limitesDeclarees({ profil: pivot, roles, textes, sieges }),
  };
}

/** Construit l'objet consommé par GroupProfile.jsx à partir d'un profil de groupe v1.
 *
 * Lot 3 (#329) : les règles de lecture propres au groupe vivent dans
 * `utils/groupe.js`, les six fondations communes dans `utils/lecture.js`. Cet
 * adaptateur les APPELLE, il n'en écrit pas de seconde version.
 */
export function buildGroupView(groupe, scrutinsIndex = null) {
  const membres = groupe.membres || [];
  const rosterTotal = groupe.meta?.couverture_roster?.roster_total
    ?? groupe.effectif?.a_la_date_de_reference ?? 0;

  // #653 : tous les comptes de la fiche se rapportent à cette date, publiée à
  // côté d'eux. Absente des 2 fiches Senat gelées (#516) : l'interface le DIT
  // plutôt que d'inventer une date ou de laisser lire « aujourd'hui ».
  const dateRef = dateDeReference(groupe);
  const dateReferenceLabel = formatFrDate(dateRef.date);

  const effectif = effectifDuGroupe(groupe);
  const profilsDisponibles = groupe.meta?.couverture_roster?.profils_disponibles ?? membres.length;
  const coveragePct = rosterTotal ? Math.round((profilsDisponibles / rosterTotal) * 100) : 0;

  const seuilQuorum = groupe.meta?.seuil_quorum ?? null;

  // `date`, `texte` et `sort` ont migré vers l'index partagé (#432) : ce sont
  // des champs du scrutin, qui étaient recopiés dans chacun des groupes l'ayant
  // voté. Les 4 104 scrutins des groupes sont inclus dans ceux des profils —
  // un seul index sert les deux.
  const cohesionVotes = groupe.cohesion_votes || [];
  // Mesuré : `excuses` vaut 0 sur les 19 832 entrées des 5 fiches AN, faute de
  // position `excuse` dans le corpus. Le décompte est donc structurellement
  // vide, et un 0 structurel ne se publie pas comme un 0 mesuré (§2 règle 5).
  const publierExcuses = excusesRenseignees(cohesionVotes);
  const votes = cohesionVotes.slice(0, NB_SCRUTINS_AFFICHES).map((v) => {
    // Même repli transitoire que pour les profils : les fichiers de groupe
    // d'avant #432 portent encore `date`/`texte` dans l'entrée.
    const scrutin = resolveScrutin(scrutinsIndex, v.scrutin_id) || v;
    const { decomptes, eligibles, exhaustif } = decomptesCohesion(v, { publierExcuses });
    return {
      id: v.scrutin_id ?? scrutin?.id ?? null,
      date: formatFrDate(scrutin?.date) || 'Date non renseignée',
      texte: scrutin?.texte ?? null,
      sourceUrl: scrutin?.source_url ?? null,
      position: v.position_majoritaire,
      // Les six décomptes remplacent la barre de cohérence : ce sont des
      // catégories, pas une échéance du pire au meilleur (#329).
      decomptes,
      eligibles,
      partitionExacte: exhaustif,
      coherence: ratioCohesion(v),
      quorum: quorumDuScrutin(v, seuilQuorum),
    };
  });
  const troncatureVotes = troncatureCohesion(cohesionVotes.length);

  const agg = groupe.amendements_agreges || {};
  const parDepute = agg.par_type_deposant?.depute;
  const amendmentSegments = AMENDMENT_OUTCOME_KEYS.map((key) => {
    const map = {
      adopté: 'nb_adoptes', rejeté: 'nb_rejetes', irrecevable: 'nb_irrecevables',
    };
    const count = map[key] ? (agg[map[key]] ?? 0) : 0;
    return { key, label: AMENDMENT_OUTCOME_LABELS[key], count };
  });

  // Étiquettes thématiques (#329) : les SUJETS sur lesquels les membres sont
  // intervenus, jamais des positions du groupe (§2 règle 8). Chacune part avec
  // son `nb_membres_porteurs` et son dénominateur — une étiquette portée par
  // 1 membre sur 76 ne dit pas ce que dit une étiquette portée par 60.
  const tagsAgreges = groupe.tags_thematiques_agreges || [];
  const tags = etiquettesThematiques(groupe);
  const coupeTags = troncatureTags(tagsAgreges.length);

  // mandats_agreges : le backend trie par nb_membres_a_la_date_de_reference desc, puis
  // nb_membres_cumul_historique desc, puis categorie/label asc (#656). Depuis
  // #382/#386 le volume et la diversité de catégories ont fortement augmenté
  // (7 catégories au lieu de 3) : on re-trie ici par rang de catégorie
  // d'abord, pour que les commissions permanentes ne soient plus noyées sous
  // les groupes d'études, bien plus nombreux.
  //
  // Au sein d'une catégorie, le critère est « qui y siège » et non « qui y est
  // passé » : 43 % des adhésions de commission publiées durent une journée ou
  // moins, et trier sur le cumul mettait en tête d'`AN-LFI-16` la commission
  // des finances (5 membres y siègent, 67 y sont passés dont 44 pour une
  // journée ou moins) devant celle des affaires sociales (9 siègent) (#656).
  const mandatsAgreges = (groupe.mandats_agreges || [])
    .map((m) => {
      // Les deux noms sont lus (#329) : sans ce repli, les 17 cartes des 2
      // fiches Senat rendaient « undefined membre y a siégé au moins une fois ».
      const compte = siegeEtPasse(m, membres.length);
      return {
        categorie: m.categorie,
        categorieLabel: MANDAT_CATEGORY_LABELS[m.categorie] || m.categorie,
        label: m.label,
        siege: compte.siege,
        passe: compte.passe,
        effectifReference: compte.effectif,
        siegeRapporteALaDate: compte.siegeRapporteALaDate,
        parFonction: Object.entries(m.par_fonction || {})
          .sort((a, b) => b[1] - a[1])
          .map(([fonction, count]) => ({ fonction, count })),
      };
    })
    .sort((a, b) => {
      const ra = MANDAT_CATEGORY_ORDER.indexOf(a.categorie);
      const rb = MANDAT_CATEGORY_ORDER.indexOf(b.categorie);
      // Une catégorie inconnue de l'ordre passe en dernier plutôt qu'en tête
      // (indexOf renverrait -1), sans masquer les catégories connues.
      const ka = ra === -1 ? MANDAT_CATEGORY_ORDER.length : ra;
      const kb = rb === -1 ? MANDAT_CATEGORY_ORDER.length : rb;
      if (ka !== kb) return ka - kb;
      // Une donnée absente ne prend pas la place d'un zéro dans le tri.
      const sa = Number.isFinite(a.siege) ? a.siege : -1;
      const sb = Number.isFinite(b.siege) ? b.siege : -1;
      if (sb !== sa) return sb - sa;
      const pa = Number.isFinite(a.passe) ? a.passe : -1;
      const pb = Number.isFinite(b.passe) ? b.passe : -1;
      if (pb !== pa) return pb - pa;
      return (a.label || '').localeCompare(b.label || '', 'fr');
    });

  return {
    id: groupe.groupe_id,
    title: groupe.groupe_nom,
    // Les 2 fiches Senat gelées n'ont pas de `legislature` : « Législature null »
    // s'affichait tel quel. Une donnée absente ne se rend pas (§2 règle 5).
    kicker: [
      groupe.chambre === 'AN' ? 'Assemblée nationale' : 'Sénat',
      groupe.legislature == null ? null : `Législature ${groupe.legislature}`,
      `${rosterTotal} membres`,
    ].filter(Boolean).join(' · '),
    profilsDisponibles,
    rosterTotal,
    coveragePct,
    // Trois compteurs, chacun avec son dénominateur — jamais un pourcentage
    // seul (§2 règle 7). Le premier s'appelait « Effectif actuel » et affichait
    // `roster_total` : ni l'effectif, ni « actuel » sur une législature close.
    kpis: [
      {
        label: dateRef.datee
          ? `Membres du groupe au ${dateReferenceLabel}`
          : 'Membres du groupe',
        numerator: effectif.valeur,
        denominator: effectif.denominateur,
        denominatorLabel: 'membres dont le profil est publié',
        caveat: effectif.rapporteALaDate
          ? "Compté à la date de référence de la fiche, sur les seuls membres dont un profil est publié. Ce n'est pas un effectif d'aujourd'hui : la législature décrite est close."
          : "Cette fiche ne publie pas de date de référence : ce compte n'est rapporté à aucune date, et ne dit pas « aujourd'hui ».",
      },
      {
        label: 'Scrutins agrégés',
        numerator: cohesionVotes.length,
        denominator: null,
        denominatorLabel: null,
        caveat: 'Mesure la couverture des scrutins agrégés, pas la qualité du vote.',
      },
      {
        label: 'Amendements adoptés, déposés par les député⋅es du groupe',
        numerator: parDepute?.nb_adoptes ?? null,
        denominator: parDepute?.nb_amendements ?? null,
        denominatorLabel: 'amendements distincts déposés',
        caveat: "Amendements distincts, dédoublonnés : un amendement cosigné compte une fois. Ne pas comparer entre groupes de taille différente, ni aux amendements du gouvernement ou des rapporteurs.",
      },
    ],
    votes,
    troncatureVotes,
    seuilQuorum,
    publierExcuses,
    tags,
    troncatureTags: coupeTags,
    mandatsAgreges,
    amendmentSegments,
    amendmentsDeposedTotal: parDepute?.nb_amendements ?? 0,
    amendmentsAllDeposantsTotal: agg.nb_amendements ?? 0,
    dateReference: dateRef.date,
    dateReferenceLabel,
    dateReferenceOrigineLabel: dateRef.origineLabel,
    dateReferenceDatee: dateRef.datee,
    // `meta` est publié sur 7 / 7 fiches et rien ne le lisait (#329).
    couvertureRoster: couvertureRoster(groupe),
    avertissements: groupe.meta?.warnings || [],
    genereLe: formatFrDate(groupe.meta?.genere_le) || null,
    refus: REFUS_FICHE_GROUPE,
    members: membres.map((m) => ({
      nom: m.nom,
      // `present_a_la_date_de_reference` remplace `actif` (#653) : sur une fiche
      // de législature close, « actif » désignait les membres encore députés
      // aujourd'hui, pas ceux qui appartenaient au groupe. Les 2 fiches Senat
      // gelées portent encore `actif` ; leur valeur est lue, mais la section
      // déclare alors qu'elle ne se rapporte à aucune date.
      present: m.present_a_la_date_de_reference ?? m.actif ?? null,
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
