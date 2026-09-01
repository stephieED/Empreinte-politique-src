/*
 * Les règles du profil candidat — lot 2 de la refonte #324 (issue #328).
 *
 * Ce module ne dessine rien : il décide ce que la fiche d'un candidat déclaré a
 * le droit d'afficher. `components/CandidateProfile.jsx` en donne la forme,
 * `data/pivotAdapter.js` l'appelle. Même partage que le lot 1
 * (`utils/lecture.js`, #326) et le lot 3 (`utils/groupe.js`, #329) : les six
 * fondations communes vivent là-bas et sont IMPORTÉES ici, jamais réécrites.
 *
 * Le principe directeur de la trame, arrêté sur maquette après sept itérations
 * (#328) : **l'institution n'est jamais un chapitre, c'est une colonne.**
 * L'ordre est chronologique, jamais hiérarchique, et AUCUN total n'additionne
 * deux natures d'acte — c'est ce qui empêche la comparaison de virer au
 * classement (AGENTS.md §2 règle 1).
 *
 * Population : les 13 profils `meta.provenance == "candidat_declare"`. Les 468
 * `roster_groupe` ne sont pas une page et ne sont jamais liés. Un chiffre sur
 * les 481 mélange les deux et ne veut rien dire (#630).
 *
 * Chiffres cités : mesurés sur le dépôt au commit `9c702c4b`, 01/09/2026.
 */

import { formatNumber, isWholeTextVote, normalizeLabel } from './lecture';

/* ── Règle : la position dans l'hémicycle est DÉCLARÉE, jamais déduite ───────
 *
 * L'Assemblée publie `organe.positionPolitique` sur chaque groupe politique —
 * trois valeurs, jamais deux : `Majoritaire`, `Minoritaire`, `Opposition`.
 * `candidate_profile.py` la reporte sur les mandats `groupe_politique` sous
 * `position_dans_hemicycle`, avec le `source_url` du référentiel qu'exige
 * AGENTS.md §2 règle 6 — sans `source_url`, la valeur n'est pas affichable.
 *
 * Mesuré sur les 541 mandats des 13 candidats déclarés : 14 `opposition`,
 * 7 `majorite`, 17 `gouvernement`, 503 non renseignés, et **`minoritaire`
 * n'apparaît sur aucun**. La valeur reste déclarée ici parce que le schéma la
 * connaît (`KNOWN_POSITIONS_HEMICYCLE`) : la retirer ferait tomber en silence
 * un groupe `Minoritaire` le jour où l'un des treize en rejoint un.
 *
 * `null` n'est pas une quatrième position : c'est « l'Assemblée ne l'a pas
 * déclaré ». Elle ne le déclare pas pour la législature en cours — Guedj et
 * Attal siègent tous deux dans la XVIIe et aucun de leurs mandats de groupe de
 * cette législature ne porte de position. Le déduire d'un comportement de vote
 * serait exactement le jugement à ne pas porter (§2 règle 1).
 */
export const POSITIONS_HEMICYCLE = {
  majorite: { label: 'groupe majoritaire', motif: 'plein' },
  opposition: { label: "groupe d'opposition", motif: 'diagonales' },
  minoritaire: { label: 'groupe minoritaire', motif: 'points' },
  gouvernement: { label: 'membre du gouvernement', motif: 'rayures' },
};

export const POSITION_NON_DECLAREE = {
  label: "position non déclarée par l'Assemblée",
  motif: 'fines-rayures',
};

export function libellePosition(position) {
  return (POSITIONS_HEMICYCLE[position] ?? POSITION_NON_DECLAREE).label;
}

export function motifPosition(position) {
  return (POSITIONS_HEMICYCLE[position] ?? POSITION_NON_DECLAREE).motif;
}

/* ── Règle : la voix du texte suit la source, ou n'affirme rien ──────────────
 *
 * La trame écrit « ce qu'il a proposé ». Appliquée telle quelle aux treize, la
 * formule se trompe sur quatre d'entre eux — deux des treize candidats déclarés
 * sont des femmes, et deux profils vides ne disent rien. Déduire le genre d'un
 * prénom serait une inférence non sourcée là où la source en porte une :
 * `identite.civilite`, renseignée sur 9 des 13 (« M. » ×7, « Mme » ×2).
 *
 * Quand elle manque, la page ne choisit pas : elle emploie une tournure qui
 * n'affirme aucun genre (« ce que cette personne a proposé »). Un vide reste un
 * vide (§2 règle 5) — y compris dans la grammaire.
 */
const VOIX_MASCULINE = {
  pronom: 'il',
  sujet: 'il',
  Sujet: 'Il',
  quil: "qu'il",
  depute: 'député',
  accorde: '',
  ne: 'Né',
  titres: {
    gouvernements: "Les gouvernements dont il a été membre",
    propose: "Ce qu'il a proposé",
    dit: "Ce qu'il a dit",
    vote: "Ce qu'il a voté",
    ecarts: "Où il s'est écarté des siens",
  },
};

const VOIX_FEMININE = {
  pronom: 'elle',
  sujet: 'elle',
  Sujet: 'Elle',
  quil: "qu'elle",
  depute: 'députée',
  accorde: 'e',
  ne: 'Née',
  titres: {
    gouvernements: "Les gouvernements dont elle a été membre",
    propose: "Ce qu'elle a proposé",
    dit: "Ce qu'elle a dit",
    vote: "Ce qu'elle a voté",
    ecarts: "Où elle s'est écartée des siens",
  },
};

const VOIX_NON_DECLAREE = {
  pronom: 'cette personne',
  sujet: 'cette personne',
  Sujet: 'Cette personne',
  quil: 'que cette personne',
  depute: 'parlementaire',
  accorde: '',
  ne: 'Naissance le',
  titres: {
    gouvernements: "Les gouvernements dont cette personne a été membre",
    propose: 'Ce que cette personne a proposé',
    dit: 'Ce que cette personne a dit',
    vote: 'Ce que cette personne a voté',
    ecarts: 'Les écarts avec son groupe',
  },
};

export function voixDuProfil(civilite) {
  if (civilite === 'M.') return VOIX_MASCULINE;
  if (civilite === 'Mme') return VOIX_FEMININE;
  return VOIX_NON_DECLAREE;
}

const FIN_OUVERTE = '9999-12-31';

function borneFin(mandat) {
  return mandat.actif || !mandat.fin ? FIN_OUVERTE : mandat.fin;
}

function chevauche(a, b) {
  return a.debut <= borneFin(b) && b.debut <= borneFin(a);
}

/* ── Règle : une période de position n'est lue que si elle est sourcée ───────
 *
 * §2 règle 6 : `position_dans_hemicycle` sans `source_url` n'est pas publiable.
 * Le filtre est ici, une fois, et pas dans chaque appelant.
 */
function periodesDePosition(mandats, categorie) {
  return mandats
    .filter(
      (m) =>
        m.categorie === categorie &&
        m.position_dans_hemicycle &&
        m.source_url &&
        m.debut,
    )
    .map((m) => ({
      position: m.position_dans_hemicycle,
      sigle: sigleDeGroupePolitique(m.label),
      debut: m.debut,
      fin: borneFin(m),
      sourceUrl: m.source_url,
    }));
}

/*
 * `groupe_politique` porte son sigle dans l'intitulé : « Groupe politique
 * (SOC) ». Il n'existe pas de champ pour lui. Sans parenthèse, on rend
 * l'intitulé tel que la source l'écrit plutôt que d'inventer un sigle.
 */
export function sigleDeGroupePolitique(label) {
  const m = /\(([^)]+)\)\s*$/.exec(label || '');
  return m ? m[1] : label || null;
}

/* ── Règle : un siège, pas un enregistrement ─────────────────────────────────
 *
 * #640 : « un profil publie TOUS ses mandats électifs, un par siège ». La
 * fusion additive (#465) a pourtant conservé, sur plusieurs profils, DEUX
 * enregistrements pour un même siège — un ancien sans `chambre`, un récent avec.
 * Mesuré : Jérôme Guedj porte 5 enregistrements pour 4 sièges, Gabriel Attal 5
 * pour 3. Les afficher tous ferait lire deux mandats là où il y en a un.
 *
 * Le regroupement se fait sur la DATE DE FIN — deux mandats qui se chevauchent
 * et s'arrêtent le même jour sont le même siège — et jamais sur la seule
 * législature, ce que #640 interdit explicitement (deux mandats séparés par une
 * élection annulée seraient soudés). L'enregistrement qui porte une `chambre`
 * est préféré comme représentant, la date de début retenue est la plus ancienne
 * : on ne raccourcit pas un mandat observé.
 *
 * Le nombre d'enregistrements repliés est RENDU, pas caché : il alimente la
 * section « ce qu'on n'a pas pu lire ».
 */
export function siegesElectifs(mandats) {
  const electifs = (mandats || [])
    .filter((m) => m.categorie === 'mandat_electif' && m.debut)
    .sort((a, b) => (a.debut < b.debut ? -1 : 1));

  const sieges = [];
  for (const m of electifs) {
    const fin = borneFin(m);
    const existant = sieges.find((s) => s.fin === fin && chevauche(s, m));
    if (!existant) {
      sieges.push({
        debut: m.debut,
        fin,
        actif: Boolean(m.actif) || !m.fin,
        chambre: m.chambre ?? null,
        label: m.label ?? null,
        enregistrements: 1,
      });
      continue;
    }
    existant.enregistrements += 1;
    if (m.debut < existant.debut) existant.debut = m.debut;
    if (!existant.chambre && m.chambre) existant.chambre = m.chambre;
    if (m.chambre) existant.label = m.label ?? existant.label;
  }
  return sieges.sort((a, b) => (a.debut < b.debut ? -1 : 1));
}

const CHAMBRE_ROLE = {
  AN: 'Député·e',
  Senat: 'Sénateur·rice',
  PE: 'Député·e européen·ne',
  mairie: 'Maire',
};

/*
 * Une fonction gouvernementale se lit sur deux enregistrements distincts pour
 * la même période : l'appartenance (`fonction: "membre"`, intitulé
 * « Gouvernement (BORNE) ») et le portefeuille (« Ministre délégué… »). Le
 * portefeuille porte le rôle, l'appartenance porte le nom du gouvernement.
 * `fonction: "en mission"` n'est ni l'un ni l'autre : c'est un·e parlementaire
 * en mission auprès d'un ministère, qui reste parlementaire.
 */
const FONCTION_MEMBRE = 'membre';
const FONCTION_MISSION = 'en mission';

export function appartenancesGouvernementales(mandats) {
  return (mandats || [])
    .filter((m) => m.categorie === 'fonction_gouvernementale' && m.fonction === FONCTION_MEMBRE && m.debut)
    .map((m) => ({
      nom: sigleDeGroupePolitique(m.label) || m.label,
      debut: m.debut,
      fin: borneFin(m),
      actif: Boolean(m.actif) || !m.fin,
      sourceUrl: m.source_url ?? null,
    }))
    .sort((a, b) => (a.debut < b.debut ? -1 : 1));
}

/* ── Livrable : le parcours, une seule frise ─────────────────────────────────
 *
 * Pas deux couloirs empilés — un couloir au-dessus de l'autre EST une
 * hiérarchie, au sens littéral. Une ligne par rôle, ordonnées par date de
 * début, quelle que soit l'institution : c'est la date qui range, pour tout le
 * monde. Quand deux rôles se chevauchent (Attal est élu député 33 jours alors
 * qu'il est ministre délégué), la bande se scinde par un rangement glouton et
 * la légende dit que c'en est un.
 */
export const INSTITUTION_PARLEMENT = 'parlement';
export const INSTITUTION_GOUVERNEMENT = 'gouvernement';
export const INSTITUTION_MISSION = 'mission';

const INTITULE_CHEF = /^premier ministre$/;

export function rolesDuParcours(mandats) {
  const liste = mandats || [];
  const positionsGroupe = periodesDePosition(liste, 'groupe_politique');
  const gouvernements = appartenancesGouvernementales(liste);

  const roles = [];

  for (const siege of siegesElectifs(liste)) {
    const chevauchantes = positionsGroupe.filter((p) => chevauche(p, siege));
    // Une position par siège : celle de la période la plus longue passée dans
    // ce siège. Un siège qui en croise deux (un changement de qualification en
    // cours de législature) reste rendu par sa plus longue — et les deux
    // restent visibles dans la liste des rôles, jamais fusionnées en une.
    const retenue = chevauchantes[0] ?? null;
    // Le groupe se lit d'abord sur le mandat `groupe_politique`, qui porte AUSSI
    // la position déclarée. Quand il n'y en a pas — c'est le cas de toute la
    // XVIIe législature — l'intitulé du mandat électif le porte encore
    // (« Mandat parlementaire (Socialistes et apparentés) ») : c'est la même
    // source, pas une déduction. Sans ce repli, le siège en cours s'afficherait
    // sans groupe alors que la source en nomme un.
    const groupe = retenue?.sigle ?? sigleDeGroupePolitique(siege.label);
    roles.push({
      institution: INSTITUTION_PARLEMENT,
      role: CHAMBRE_ROLE[siege.chambre] || 'Mandat parlementaire',
      detail: groupe && groupe !== siege.label ? groupe : null,
      debut: siege.debut,
      fin: siege.fin,
      actif: siege.actif,
      position: retenue?.position ?? null,
      sourceUrl: retenue?.sourceUrl ?? null,
    });
  }

  for (const m of liste) {
    if (m.categorie !== 'fonction_gouvernementale' || !m.debut) continue;
    if (m.fonction === FONCTION_MEMBRE) continue;

    if (m.fonction === FONCTION_MISSION) {
      roles.push({
        institution: INSTITUTION_MISSION,
        role: 'Parlementaire en mission',
        detail: m.label ? `auprès du ${m.label}` : null,
        debut: m.debut,
        fin: borneFin(m),
        actif: Boolean(m.actif) || !m.fin,
        position: null,
        sourceUrl: m.source_url ?? null,
      });
      continue;
    }

    const gouvernement = gouvernements.find((g) => chevauche(g, { debut: m.debut, fin: borneFin(m) }));
    const chef = INTITULE_CHEF.test(normalizeLabel(m.fonction));
    roles.push({
      institution: INSTITUTION_GOUVERNEMENT,
      chef,
      role: m.fonction || 'Membre du gouvernement',
      detail: [m.label, gouvernement ? `gouvernement ${gouvernement.nom}` : null]
        .filter(Boolean)
        .join(' · ') || null,
      debut: m.debut,
      fin: borneFin(m),
      actif: Boolean(m.actif) || !m.fin,
      position: 'gouvernement',
      sourceUrl: m.source_url ?? null,
    });
  }

  roles.sort((a, b) => (a.debut === b.debut ? (a.fin < b.fin ? -1 : 1) : a.debut < b.debut ? -1 : 1));

  // Rangement glouton : la première ligne libre à cette date. Un rangement,
  // pas une hiérarchie — la légende le dit sur la page.
  const lignes = [];
  for (const r of roles) {
    let i = lignes.findIndex((l) => l.every((o) => !chevauche(o, r)));
    if (i < 0) {
      lignes.push([]);
      i = lignes.length - 1;
    }
    lignes[i].push(r);
    r.ligne = i;
  }

  return { roles: roles.map((r, i) => ({ ...r, numero: i + 1 })), nbLignes: Math.max(1, lignes.length) };
}

/*
 * Les bornes de la frise : du premier début observé à la fin la plus tardive,
 * jamais une année ronde inventée. Un axe qui déborde de la carrière laisserait
 * croire à des années sans rien plutôt qu'à des années hors mesure.
 */
export function bornesDuParcours(roles) {
  if (!roles.length) return null;
  const debuts = roles.map((r) => r.debut).filter(Boolean).sort();
  const fins = roles.map((r) => (r.actif ? null : r.fin)).filter(Boolean).sort();
  const finMax = roles.some((r) => r.actif)
    ? new Date().toISOString().slice(0, 10)
    : fins[fins.length - 1];
  return { debut: debuts[0], fin: finMax };
}

export function positionSurAxe(date, bornes) {
  if (!bornes) return 0;
  const a = Date.parse(bornes.debut);
  const b = Date.parse(bornes.fin);
  const d = Date.parse(date === FIN_OUVERTE ? bornes.fin : date);
  if (!Number.isFinite(a) || !Number.isFinite(b) || b <= a || !Number.isFinite(d)) return 0;
  return Math.min(100, Math.max(0, ((d - a) / (b - a)) * 100));
}

/* ── Livrable : les fonctions qu'on choisit d'exercer ────────────────────────
 *
 * 124 mandats chez Guedj, dont 15 groupes d'études et 6 commissions d'enquête,
 * réduits à une puce par la fiche d'avant. Ce sont pourtant les seuls gestes
 * du corpus que personne n'impose : ils disent où quelqu'un choisit de passer
 * son temps. Une catégorie par bloc, jamais un total — un groupe d'amitié et
 * une commission d'enquête ne s'additionnent pas.
 */
export const CATEGORIES_FONCTIONS = [
    // La source range sous `commission` bien plus que les commissions
  // permanentes : commissions spéciales, groupes de travail, un comité
  // consultatif. Le titre reprend donc la catégorie telle qu'elle est, sans
  // promettre une taxonomie que le corpus ne porte pas (§2 règle 2).
  { cle: 'commission', titre: 'Commissions' },
  { cle: 'commission_enquete', titre: "Commissions d'enquête et commissions spéciales" },
  { cle: 'mission_information', titre: "Missions d'information" },
  { cle: 'groupe_etudes', titre: "Groupes d'études" },
  { cle: 'delegation', titre: 'Délégations' },
  { cle: 'extra_parlementaire', titre: 'Organismes extra-parlementaires' },
  { cle: 'groupe_amitie', titre: "Groupes d'amitié" },
];

export function fonctionsExercees(mandats) {
  return CATEGORIES_FONCTIONS.map(({ cle, titre }) => {
    const entrees = (mandats || []).filter((m) => m.categorie === cle);
    const parIntitule = new Map();
    for (const m of entrees) {
      const label = m.label || 'Intitulé non publié';
      parIntitule.set(label, (parIntitule.get(label) || 0) + 1);
    }
    return {
      cle,
      titre,
      total: entrees.length,
      items: [...parIntitule.entries()]
        .map(([label, n]) => ({ label, n }))
        .sort((a, b) => b.n - a.n || a.label.localeCompare(b.label, 'fr')),
    };
  }).filter((c) => c.total > 0);
}

/* ── Livrable : ce qu'il a proposé, par législature ──────────────────────────
 *
 * `role_signataire: "auteur_principal"` — la cosignature n'est pas la même
 * chose et ne se totalise pas avec (§6 : « une cosignature est UN amendement »,
 * et le taux d'adoption sur signatures n'est jamais publié).
 *
 * Le découpage par législature n'est pas décoratif : c'est le seul endroit où
 * la position déclarée du groupe peut accompagner le chiffre qu'elle explique.
 * 24 déposés / 6 adoptés comme député de la MAJORITÉ et 1 968 / 67 comme député
 * d'OPPOSITION ne sont pas deux performances, ce sont deux métiers. Sans la
 * mention sur la même ligne, le lecteur lit une incompétence.
 */
export const SORTS_AMENDEMENT = [
  'adopté',
  'rejeté',
  'tombé',
  'retiré',
  'irrecevable',
  'non_soutenu',
];

export const LIBELLE_SORT = {
  adopté: 'adoptés',
  rejeté: 'rejetés',
  tombé: 'tombés',
  retiré: 'retirés',
  irrecevable: 'irrecevables',
  non_soutenu: 'non soutenus',
  non_publie: 'sort non publié',
};

/*
 * `sort: null` n'est pas un sort : c'est l'absence de sort publié. Le confondre
 * avec « rejeté » publierait un zéro là où il n'y a pas de mesure (§2 règle 5).
 * Mesuré chez Guedj : 659 des 1 968 amendements de la XVIe législature.
 */
export const SORT_NON_PUBLIE = 'non_publie';

/* ── Règle : ce que la Constitution a écarté avant discussion ────────────────
 *
 * `base_juridique_irrecevabilite` vaut « art. 40 » (dépense nouvelle sans
 * compensation) ou « art. 45 » (lien avec le texte discuté). C'est une
 * information sur la RÈGLE, pas sur la personne : 246 amendements écartés au
 * titre de l'article 40 disent qu'ils coûtaient de l'argent public, pas qu'ils
 * étaient mauvais. La phrase qui accompagne le chiffre est donc obligatoire —
 * le chiffre seul se lirait comme un compte d'échecs.
 */
export const BASES_IRRECEVABILITE = {
  'art. 40': {
    titre: "écartés au titre de l'article 40",
    explication:
      "La Constitution interdit à un·e parlementaire de proposer une dépense nouvelle sans la compenser. Ces propositions ont été écartées avant d'être discutées, parce qu'elles coûtaient de l'argent public.",
  },
  'art. 45': {
    titre: "écartés au titre de l'article 45",
    explication:
      "Un amendement doit avoir un lien avec le texte discuté. Ces propositions ont été jugées étrangères au sujet du moment.",
  },
};

/* ── Règle : un dossier se nomme, ou il ne se compte pas au lecteur ──────────
 *
 * « 6 dossiers sur 34 concentrent 2 206 de ses 2 429 amendements » décrivait la
 * FORME d'une distribution, pas ce sur quoi la personne a travaillé. Un ratio
 * de concentration ne se convertit en rien de lisible : la substance est dans
 * la liste des dossiers, pas dans leur nombre. La mesure est donc remplacée par
 * les dossiers eux-mêmes, nommés, avec leur compte.
 *
 * Un dossier n'est nommable que si la source le nomme. Deux chemins, et un
 * troisième qui n'en est pas un :
 *  - `textes[texte_vise].titre` de l'index par législature — le cas normal ;
 *  - le `texte_vise` lui-même quand ce n'en est PAS une référence de source :
 *    l'index publie parfois l'intitulé en clair à cette place (2 458 des 2 831
 *    dépôts de Jean-Luc Mélenchon sont visés par « Système universel de
 *    retraite », qui n'est la clé d'aucune entrée `textes`) ;
 *  - jamais la référence brute — « PRJLANR5L14B1395 » n'est pas un nom, et
 *    l'afficher donnerait au lecteur un identifiant à la place d'un texte.
 *
 * Le critère de distinction est structurel : une référence de source ne contient
 * pas d'espace, un intitulé en contient toujours.
 *
 * Ce que ça laisse à découvert est mesuré, et la page le dit plutôt que de le
 * combler : la XIVe législature n'a qu'UNE entrée `textes` dans l'index, donc
 * aucun des 12 dossiers de Xavier Bertrand ni aucun des 3 d'Édouard Philippe
 * n'est nommable (mesuré au SHA e40d0d3, 01/09/2026).
 */
const REFERENCE_DE_SOURCE = /^\S+$/;

export function nomDeDossier(dossierTitre, texteVise) {
  if (dossierTitre) return dossierTitre;
  if (texteVise && !REFERENCE_DE_SOURCE.test(texteVise)) return texteVise;
  return null;
}

/** Combien de dossiers nommés le coup d'œil montre — les suivants ne sont pas
 * cachés, ils sont ailleurs sur la page, dans « ce qu'il a proposé ». */
export const NB_DOSSIERS_NOMMES = 3;

/*
 * UNE SEULE PASSE sur les amendements, et jamais de forme plate rematérialisée.
 *
 * `joinAmendements` est un générateur pour une raison mesurée (#377, #431) :
 * étendre index × mapping a coûté un facteur ~21 et un OOM. Trois agrégats sont
 * donc calculés dans la même itération plutôt que par trois passes — un
 * générateur ne se relit pas, et le matérialiser pour pouvoir le relire
 * reconstruirait exactement ce que #431 supprime.
 *
 * `positionALaDate` rend la position déclarée du groupe à une date : c'est elle
 * qui accompagne le chiffre, jamais une moyenne de législature.
 */
export function agregerAmendements(amendementsJoints, positionALaDate) {
  const parLeg = new Map();
  const parBase = new Map();
  const parDossier = new Map();
  let totalAuteur = 0;

  for (const a of amendementsJoints) {
    if (a.role_signataire !== 'auteur_principal') continue;
    totalAuteur += 1;

    const leg = a.legislature ?? 'inconnue';
    if (!parLeg.has(leg)) parLeg.set(leg, { legislature: leg, total: 0, sorts: new Map(), dates: [] });
    const bloc = parLeg.get(leg);
    bloc.total += 1;
    const sort = a.sort || SORT_NON_PUBLIE;
    bloc.sorts.set(sort, (bloc.sorts.get(sort) || 0) + 1);
    if (a.date) bloc.dates.push(a.date);

    if (a.base_juridique_irrecevabilite) {
      const base = a.base_juridique_irrecevabilite;
      parBase.set(base, (parBase.get(base) || 0) + 1);
    }

    const cle = a.dossier_id || a.texte_vise;
    if (cle) {
      if (!parDossier.has(cle)) {
        parDossier.set(cle, { cle, nom: nomDeDossier(a.dossier_titre, a.texte_vise), n: 0 });
      }
      parDossier.get(cle).n += 1;
    }
  }

  const ordre = [...SORTS_AMENDEMENT, SORT_NON_PUBLIE];
  const legislatures = [...parLeg.values()]
    .map((bloc) => {
      bloc.dates.sort();
      const mediane = bloc.dates[Math.floor(bloc.dates.length / 2)] ?? null;
      return {
        legislature: bloc.legislature,
        total: bloc.total,
        position: mediane ? positionALaDate(mediane) : null,
        sorts: ordre
          .filter((s) => bloc.sorts.has(s))
          .map((s) => ({ cle: s, label: LIBELLE_SORT[s], n: bloc.sorts.get(s) })),
      };
    })
    .sort((a, b) => Number(a.legislature) - Number(b.legislature));

  const irrecevabilites = [...parBase.entries()]
    .filter(([base]) => BASES_IRRECEVABILITE[base])
    .map(([base, n]) => ({ base, n, ...BASES_IRRECEVABILITE[base] }))
    .sort((a, b) => b.n - a.n);

  // Les dossiers, nommés quand la source les nomme — et le compte de ce qu'elle
  // ne nomme pas, qui reste visible au lieu d'être absorbé dans le total.
  const classes = [...parDossier.values()].sort((a, b) => b.n - a.n || a.cle.localeCompare(b.cle));
  const nommes = classes.filter((d) => d.nom);
  const dossiers = classes.length
    ? {
        rattaches: classes.reduce((s, d) => s + d.n, 0),
        distincts: classes.length,
        nommes: nommes.slice(0, NB_DOSSIERS_NOMMES),
        distinctsNommes: nommes.length,
        depotsNommes: nommes.reduce((s, d) => s + d.n, 0),
      }
    : null;

  return { totalAuteur, legislatures, irrecevabilites, dossiers };
}

/* ── Règle : un texte porté n'est publié qu'à partir de l'examen en commission
 *
 * AGENTS.md §6 : « `textes_portes[]` en deçà du seuil — non publié par défaut ».
 * Les deux maquettes d'août affichaient les textes simplement DÉPOSÉS ; c'était
 * une violation de la règle. Ce qui est écarté est compté et sa raison dite —
 * l'écarter en silence transformerait une règle éditoriale en trou de données.
 */
export const STADES_PUBLIES = [
  'examine_commission',
  'inscrit_ordre_jour',
  'discute_seance',
  'adopte',
  'promulgue',
];

export const LIBELLE_STADE = {
  depose: 'déposé',
  examine_commission: 'examiné en commission',
  inscrit_ordre_jour: "inscrit à l'ordre du jour",
  discute_seance: 'discuté en séance',
  adopte: 'adopté',
  promulgue: 'promulgué',
};

export const LIBELLE_ROLE_TEXTE = {
  auteur: 'Auteur',
  rapporteur: 'Rapporteur',
  'co-rapporteur': 'Co-rapporteur',
};

/*
 * Un texte dont l'intitulé officiel commence par « projet de loi » est un texte
 * du GOUVERNEMENT, signé comme ministre — pas une proposition déposée comme
 * parlementaire. Le corpus les range sous le même `role: auteur` (13 des 34
 * textes d'Attal) : la distinction ne tient qu'à l'intitulé, et la page le dit
 * au lieu de laisser lire 34 initiatives personnelles.
 */
const PROJET_DE_LOI = /^projet de loi\b/;

export function estProjetDeLoi(texte) {
  return PROJET_DE_LOI.test(normalizeLabel(texte?.titre));
}

export function textesPortes(textes) {
  const liste = textes || [];
  const publies = liste.filter((t) => STADES_PUBLIES.includes(t.stade_procedural));
  const ecartes = liste.filter((t) => !STADES_PUBLIES.includes(t.stade_procedural));
  const parStade = new Map();
  for (const t of publies) parStade.set(t.stade_procedural, (parStade.get(t.stade_procedural) || 0) + 1);

  return {
    total: liste.length,
    publies: publies
      .map((t) => ({
        titre: t.titre,
        role: LIBELLE_ROLE_TEXTE[t.role] || t.role || 'Rôle non publié',
        stade: LIBELLE_STADE[t.stade_procedural] || t.stade_procedural,
        stadeCle: t.stade_procedural,
        legislature: t.legislature ?? null,
        dateMin: t.date_min ?? null,
        dateMax: t.date_max ?? null,
        projetDeLoi: estProjetDeLoi(t),
        sourceUrl: t.source_url ?? null,
      }))
      .sort((a, b) => String(b.dateMax || '').localeCompare(String(a.dateMax || ''))),
    repartition: STADES_PUBLIES.filter((s) => parStade.has(s)).map((s) => ({
      cle: s,
      label: LIBELLE_STADE[s],
      n: parStade.get(s),
    })),
    promulgues: parStade.get('promulgue') || 0,
    projetsDeLoi: liste.filter(estProjetDeLoi).length,
    ecartes: {
      total: ecartes.length,
      deposes: ecartes.filter((t) => t.stade_procedural === 'depose').length,
      sansStade: ecartes.filter((t) => !t.stade_procedural).length,
    },
  };
}

/* ── Livrable : ce qu'il a dit, et en quelle qualité ─────────────────────────
 *
 * Deux régimes, jamais confondus (§2 règle 2) :
 *  - SOURCÉ  — le compte rendu publie `fonction` (Attal : 3 555 / 3 963) ;
 *  - DÉRIVÉ  — il ne la publie pas (Guedj : 0 / 2 702), et lire ce silence
 *    comme « il parlait comme député » est NOTRE inférence, licite seulement
 *    parce que ses mandats disent qu'il n'exerçait rien d'autre à ces dates.
 *    Elle est donc déclarée comme telle sur la page.
 */
export const TYPES_INTERVENTION = [
  { cles: ['loi'], label: 'Débats sur un texte de loi' },
  { cles: ['debat'], label: 'Débats' },
  { cles: ['question', 'question_orale'], label: 'Questions écrites et orales' },
  { cles: ['question_gouvernement'], label: 'Questions au gouvernement' },
  { cles: ['motion_censure'], label: 'Motions de censure' },
  { cles: ['explication_vote'], label: 'Explications de vote' },
  { cles: ['commission'], label: 'Commission' },
];

export function interventionsParNature(interventions) {
  const liste = interventions || [];
  const compte = new Map();
  for (const i of liste) compte.set(i.type_detail, (compte.get(i.type_detail) || 0) + 1);

  const lignes = TYPES_INTERVENTION.map(({ cles, label }) => ({
    label,
    n: cles.reduce((s, c) => s + (compte.get(c) || 0), 0),
  })).filter((l) => l.n > 0);

  const connus = new Set(TYPES_INTERVENTION.flatMap((t) => t.cles));
  const autres = [...compte.entries()].filter(([c]) => !connus.has(c));
  for (const [cle, n] of autres) lignes.push({ label: cle || 'Nature non publiée', n });

  return lignes.sort((a, b) => b.n - a.n);
}

export function regimeQualiteOrateur(interventions) {
  const liste = interventions || [];
  const sourcees = liste.filter((i) => i.fonction).length;
  const parFonction = new Map();
  for (const i of liste) {
    if (!i.fonction) continue;
    parFonction.set(i.fonction, (parFonction.get(i.fonction) || 0) + 1);
  }
  // TROIS états, pas deux. « Sourcée » dès la première fonction publiée dirait
  // que la qualité est connue là où elle l'est sur 35 des 3 933 interventions
  // de Jean-Luc Mélenchon (0,9 %). Un seuil serait un arbitrage éditorial : la
  // page publie donc les deux nombres et nomme l'état partiel.
  const regime = sourcees === 0 ? 'derive' : sourcees === liste.length ? 'source' : 'partiel';

  return {
    total: liste.length,
    sourcees,
    regime,
    sourcee: sourcees > 0,
    fonctions: [...parFonction.entries()]
      .map(([label, n]) => ({ label, n }))
      .sort((a, b) => b.n - a.n),
  };
}

/* ── Règle : un même champ recouvre deux actes opposés ───────────────────────
 *
 * `type_detail: "question_gouvernement"` compte les questions POSÉES par un·e
 * député·e et celles auxquelles un·e ministre RÉPOND. Guedj : 215, dont 0
 * portent une qualité ministérielle — il les a posées. Attal : 743, dont 723 —
 * il y a répondu. Publier « ce sur quoi il a interpellé le gouvernement » pour
 * le second serait exactement inversé.
 *
 * Deux conditions, et pas une : la qualité publiée par la source ET une date
 * tombant dans une période de gouvernement. Mesuré sur Attal, les deux règles
 * donnent 723 séparément ; les conjoindre évite qu'un `fonction: "rapporteur"`
 * — 204 chez lui — compte un jour pour une qualité ministérielle.
 */
export function directionQuestionsGouvernement(interventions, appartenances) {
  const qag = (interventions || []).filter((i) => i.type_detail === 'question_gouvernement');
  if (!qag.length) return null;

  const periodes = appartenances || [];
  const dansGouvernement = (date) =>
    Boolean(date) && periodes.some((p) => p.debut <= date && date <= p.fin);
  const ministerielles = qag.filter((i) => i.fonction && dansGouvernement(i.date)).length;

  const parSujet = new Map();
  for (const i of qag) {
    if (!i.sujet) continue;
    parSujet.set(i.sujet, (parSujet.get(i.sujet) || 0) + 1);
  }

  // `sujets` est TRONQUÉ à douze pour l'affichage : `avecSujet` et
  // `sujetsDistincts` se comptent donc sur l'ensemble, jamais sur la tranche.
  // Les sommer après la coupe donnerait un dénominateur faux dès le treizième
  // sujet — et c'est le dénominateur qui porte la couverture du point.
  let avecSujet = 0;
  for (const n of parSujet.values()) avecSujet += n;

  return {
    total: qag.length,
    ministerielles,
    avecSujet,
    sujetsDistincts: parSujet.size,
    sens: ministerielles > qag.length / 2 ? 'recues' : 'posees',
    sujets: [...parSujet.entries()]
      .map(([label, n]) => ({ label, n }))
      .sort((a, b) => b.n - a.n || a.label.localeCompare(b.label, 'fr'))
      .slice(0, 12),
  };
}

/* ── Livrable : ce qu'il a voté, et les périodes où voter était impossible ───
 *
 * La sélection des votes « sur l'ensemble d'un texte » vient du lot 1
 * (`isWholeTextVote`, corrigée par #672) et n'est pas réécrite ici. Elle est un
 * PLANCHER, jamais un relevé exhaustif, et `WHOLE_TEXT_VOTE_BOUND` porte cette
 * phrase sur la page.
 *
 * « Un membre du gouvernement ne vote pas » est un FAIT ÉTABLI sur la personne,
 * pas une lacune de collecte — sans cette phrase, Attal paraît absent de 2018 à
 * 2024. Il n'est pas non plus une raison de masquer ses autres votes : la
 * maquette suspendait la barre entière, ce qui aurait tu 150 votes réels.
 *
 * AUCUN ratio de participation : un dénominateur « scrutins où la personne
 * aurait pu voter » est un taux d'assiduité individuel (§2 règle 3).
 */
export function votesDuProfil(votesJoints, appartenances, rolesParlementaires) {
  const liste = votesJoints || [];
  const surEnsemble = liste.filter((v) => isWholeTextVote(v.scrutin));
  const positions = new Map();
  for (const v of surEnsemble) positions.set(v.position, (positions.get(v.position) || 0) + 1);

  const periodes = appartenances || [];
  const sieges = rolesParlementaires || [];
  const dansGouvernement = (date) =>
    Boolean(date) && periodes.some((p) => p.debut <= date && date <= p.fin);

  const compte = new Map();
  for (const v of liste) {
    const annee = (v.date || '').slice(0, 4);
    if (!annee) continue;
    compte.set(annee, (compte.get(annee) || 0) + 1);
  }

  /*
   * L'axe des années est CONTINU entre la première et la dernière année
   * observée, et chaque année porte sa situation. Un axe troué — 2018 puis 2022
   * chez Gabriel Attal — laisse croire que les années intermédiaires n'existent
   * pas, alors qu'elles portent le fait le plus important de sa fiche : il était
   * au gouvernement et ne pouvait pas voter.
   *
   * Mais un `0` nu serait pire encore. Trois situations, jamais confondues :
   *   - `gouvernement` : voter était impossible, c'est un fait sur la personne ;
   *   - `hors_mandat`  : aucun mandat parlementaire cette année-là, il n'y avait
   *                      rien à voter — publier `0` sans le dire se lirait comme
   *                      une absence, c'est-à-dire le taux de présence
   *                      individuel qu'interdit §2 règle 3 ;
   *   - `en_mandat`    : un zéro mesuré, et celui-là seul est un décompte.
   */
  const annees = [...compte.keys()].sort();
  const parAnnee = [];
  if (annees.length) {
    const debut = Number(annees[0]);
    const fin = Number(annees[annees.length - 1]);
    for (let a = debut; a <= fin; a += 1) {
      const annee = String(a);
      const gouvernement = periodes.some(
        (p) => p.debut.slice(0, 4) <= annee && annee <= p.fin.slice(0, 4),
      );
      const enMandat = sieges.some(
        (r) => r.debut.slice(0, 4) <= annee && annee <= r.fin.slice(0, 4),
      );
      parAnnee.push({
        annee,
        n: compte.get(annee) || 0,
        situation: gouvernement ? 'gouvernement' : enMandat ? 'en_mandat' : 'hors_mandat',
      });
    }
  }

  return {
    total: liste.length,
    surEnsemble: surEnsemble.length,
    positions: ['pour', 'contre', 'abstention', 'non_votant']
      .filter((p) => positions.has(p))
      .map((p) => ({ position: p, n: positions.get(p) })),
    pendantGouvernement: liste.filter((v) => dansGouvernement(v.date)).length,
    aExerceAuGouvernement: periodes.length > 0,
    parAnnee,
  };
}

/* ── Règle : les écarts se montrent scrutin par scrutin, jamais en compte ────
 *
 * « A voté contre son groupe N fois » serait une note (§2 règle 1) : le nombre
 * seul se lit comme une mesure de loyauté, et rien dans la source ne dit qu'un
 * écart vaut plus qu'un autre. La page publie donc la LISTE — sa position et
 * celle du groupe, côte à côte, sur un scrutin nommé et daté — et jamais un
 * total. Deux faits sourcés posés l'un à côté de l'autre ; la lecture appartient
 * au lecteur.
 *
 * Restreint aux votes sur l'ensemble d'un texte : sur un article ou un
 * amendement, la position majoritaire d'un groupe se déplace d'un vote à
 * l'autre pour des raisons de négociation que le corpus ne porte pas.
 *
 * Le nombre de scrutins COMMUNS est publié : sans lui, une section vide se lit
 * comme « il n'a jamais divergé » alors qu'elle dit « rien n'est comparable ».
 * Mesuré : 814 scrutins communs entre Guedj et la fiche SOC de la XVIe, 2
 * écarts sur l'ensemble ; 1 seul scrutin commun entre Attal et la fiche
 * Renaissance de la XVIe — celle qui recouvre son mandat de trente-trois jours.
 */
export function ecartsAvecLeGroupe(votesJoints, fichesGroupe) {
  const fiches = (fichesGroupe || []).filter(Boolean);
  if (!fiches.length) return { fiches: [], communs: 0, ecarts: [], comparable: false };

  const parScrutin = new Map();
  for (const v of votesJoints || []) {
    if (v.scrutin_id) parScrutin.set(v.scrutin_id, v);
  }

  let communs = 0;
  const ecarts = [];
  for (const fiche of fiches) {
    for (const c of fiche.cohesion_votes || []) {
      const mien = parScrutin.get(c.scrutin_id);
      if (!mien) continue;
      communs += 1;
      if (!c.position_majoritaire) continue;
      if (!['pour', 'contre', 'abstention'].includes(mien.position)) continue;
      if (mien.position === c.position_majoritaire) continue;
      if (!isWholeTextVote(mien.scrutin)) continue;
      ecarts.push({
        scrutinId: c.scrutin_id,
        texte: mien.texte ?? null,
        date: mien.date ?? null,
        sourceUrl: mien.scrutin?.source_url ?? null,
        position: mien.position,
        positionGroupe: c.position_majoritaire,
        groupe: fiche.groupe_sigle ?? null,
        legislature: fiche.legislature ?? null,
      });
    }
  }

  ecarts.sort((a, b) => String(b.date || '').localeCompare(String(a.date || '')));
  return {
    fiches: fiches.map((f) => ({
      sigle: f.groupe_sigle,
      nom: f.groupe_nom,
      legislature: f.legislature,
    })),
    communs,
    ecarts,
    comparable: communs > 0,
  };
}

/* ── Livrable : le coup d'œil ────────────────────────────────────────────────
 *
 * Cinq points, tirés de cinq jeux de données distincts. Aucun rapprochement
 * thématique, aucune synthèse : Empreinte politique ne classe pas les textes
 * par sujet (§2 règle 8), et chaque point est DÉRIVÉ par comptage d'un champ de
 * la source, jamais d'une table de mots-clés écrite à la main.
 *
 * ── Ce que chaque point doit porter ────────────────────────────────────────
 *
 * 1. UNE CHOSE NOMMÉE, pas la forme d'une distribution. « 6 dossiers sur 34
 *    concentrent 2 206 de ses 2 429 amendements » est vrai et ne se convertit
 *    en rien : le lecteur ne sait pas quoi en faire. Le dossier nommé, lui, dit
 *    sur quoi la personne a travaillé.
 *
 * 2. SA PROPRE COUVERTURE. Un point qui compte sur une sous-population dit
 *    laquelle et combien elle pèse. C'est ce qui empêche d'écrire « sujets très
 *    ciblés » là où l'on décrirait notre collecte en croyant décrire son
 *    travail (§2 règle 5). Le numérateur et le dénominateur sont TOUJOURS de la
 *    même population : le point « questions » divisait le compte du premier
 *    sujet par TOUTES les questions, y compris celles dont aucun sujet n'est
 *    publié — un dénominateur faux dès que la couverture n'est pas totale.
 *
 * 3. LE MOINS DE NOTES POSSIBLE. Une note qui met en garde contre un contresens
 *    est une information et se garde (`garde`) : « questions reçues depuis le
 *    banc du gouvernement, pas des questions posées » évite de lire à l'envers
 *    les 743 questions de Gabriel Attal. Une note qui justifie notre méthode ne
 *    sert qu'à nous et se retire : « le plus petit nombre de dossiers
 *    atteignant 90 % de ses dépôts » a disparu avec la mesure qu'elle défendait.
 *
 * ── Le cadre parlementaire ne vaut pas pour un ministre ────────────────────
 *
 * « Ce qu'on fait quand on choisit » est parlementaire par construction : un
 * ministre ne réagit pas à l'ordre du jour, il le fixe, et une question au
 * gouvernement lui est POSÉE. La trame ne se dédouble pas pour autant — les
 * points restent les mêmes, dans le même ordre, tirés des mêmes champs. Ce qui
 * s'adapte est la seule phrase d'introduction, et le déclencheur est un fait
 * collecté, pas une catégorie éditoriale : avoir été MEMBRE d'un gouvernement
 * (`appartenancesGouvernementales`, 6 des 13 candidats déclarés au SHA e40d0d3,
 * 01/09/2026 — un parlementaire en mission n'en est pas un).
 *
 * L'ordre est fixe pour les treize ; ne sont rendus que les points dont la
 * donnée existe, cinq au plus. Un point absent n'est pas remplacé : c'est la
 * trame qui uniformise les emplacements, pas leur remplissage.
 */
export const NB_POINTS_COUP_OEIL = 5;

/** « puis « X » (12) et « Y » (7) » — les suivants, nommés, jamais résumés. */
function suiteNommee(items, format) {
  const suivants = items.slice(1, 3);
  if (!suivants.length) return null;
  return `puis ${suivants.map(format).join(' et ')}`;
}

/** L'accord se fait sur le nombre, pas sur un « (s) » : la page est lue, pas
 * remplie. Un seul point d'accord suffit — le reste de la phrase est écrit deux
 * fois plutôt que rendu approximatif. */
function pluriel(n, singulier, pluriels) {
  return n > 1 ? pluriels : singulier;
}

const entreGuillemets = ({ label, n }) => `« ${label} » (${formatNumber(n)})`;
const sansGuillemets = ({ label, n }) => `${label} (${formatNumber(n)})`;

export function coupOeil({
  interventions,
  dossiers,
  fonctions,
  questions,
  qualite,
  textes,
  appartenances,
}) {
  const points = [];

  // 1. Les points de l'ordre du jour où la parole a le plus porté. La
  //    couverture est le nerf : une intervention dont le compte rendu ne donne
  //    pas le point de l'ordre du jour n'est pas classable, et l'inclure au
  //    dénominateur ferait passer un trou de collecte pour de la dispersion.
  const liste = interventions || [];
  const situees = liste.filter((i) => i.sujet);
  if (situees.length) {
    const parSujet = new Map();
    for (const i of situees) parSujet.set(i.sujet, (parSujet.get(i.sujet) || 0) + 1);
    const classes = [...parSujet.entries()]
      .map(([label, n]) => ({ label, n }))
      .sort((a, b) => b.n - a.n || a.label.localeCompare(b.label, 'fr'));
    const muettes = liste.length - situees.length;
    points.push({
      cle: 'interventions',
      valeur: classes[0].n,
      sur: situees.length,
      texte: `${pluriel(classes[0].n, 'intervention porte', 'interventions portent')} sur « ${classes[0].label} »`,
      suite: suiteNommee(classes, entreGuillemets),
      socle:
        `${formatNumber(classes.length)} ${pluriel(classes.length, 'point', 'points')} de l’ordre du jour en tout` +
        (muettes > 0
          ? `, et ${formatNumber(muettes)} ${pluriel(muettes, 'intervention dont le compte rendu n’indique', 'interventions dont le compte rendu n’indique')} aucun point`
          : ''),
      garde: null,
    });
  }

  // 2. Les dossiers où les dépôts se sont portés — nommés. Ce que la source ne
  //    nomme pas reste compté à part : c'est une lacune d'index, pas une
  //    dispersion du travail (§2 règle 5).
  if (dossiers) {
    const nomme = dossiers.nommes[0] || null;
    const anonymes = dossiers.distincts - dossiers.distinctsNommes;
    const depotsAnonymes = dossiers.rattaches - dossiers.depotsNommes;
    // Le dénominateur suit le numérateur : quand un dossier est nommé, les deux
    // se comptent sur les dépôts DONT LE DOSSIER EST NOMMÉ. Le reste ne
    // disparaît pas, il est chiffré à côté.
    points.push({
      cle: 'amendements',
      valeur: nomme ? nomme.n : dossiers.rattaches,
      sur: nomme ? dossiers.depotsNommes : dossiers.rattaches,
      texte: nomme
        ? `amendements déposés comme auteur principal portent sur « ${nomme.nom} »`
        : 'amendements déposés comme auteur principal',
      suite: nomme
        ? suiteNommee(
            dossiers.nommes.map((d) => ({ label: d.nom, n: d.n })),
            entreGuillemets,
          )
        : null,
      socle: anonymes === dossiers.distincts
        ? `${formatNumber(dossiers.distincts)} ${pluriel(dossiers.distincts, 'dossier législatif', 'dossiers législatifs')}, qu’aucune entrée d’index ne nomme`
        : `${formatNumber(dossiers.distincts)} ${pluriel(dossiers.distincts, 'dossier législatif', 'dossiers législatifs')} en tout` +
          (anonymes > 0
            ? ` ; ${formatNumber(depotsAnonymes)} ${pluriel(depotsAnonymes, 'dépôt porte', 'dépôts portent')} sur ${formatNumber(anonymes)} ${pluriel(anonymes, 'dossier que la source ne nomme pas', 'dossiers que la source ne nomme pas')}`
            : ''),
      garde: null,
    });
  }

  // 3. Les commissions. Déjà nommées, rien à réparer — la suite l'est aussi.
  const commissions = (fonctions || []).find((f) => f.cle === 'commission');
  if (commissions?.items.length) {
    points.push({
      cle: 'commissions',
      valeur: commissions.items[0].n,
      sur: commissions.total,
      texte: `${pluriel(commissions.items[0].n, 'mandat en commission est', 'mandats en commission sont')} à la ${commissions.items[0].label}`,
      suite: suiteNommee(commissions.items, sansGuillemets),
      socle: null,
      garde: null,
    });
  }

  // 4. Les questions au gouvernement. Le dénominateur est le nombre de
  //    questions PORTANT UN SUJET PUBLIÉ, jamais le total : diviser par le
  //    total quand la couverture est partielle publie un ratio faux. Et quand
  //    aucun sujet n'est publié, le point ne nomme rien et dit pourquoi —
  //    écrire « sujets très divers » décrirait notre collecte.
  if (questions?.total) {
    const { avecSujet } = questions;
    const garde =
      questions.sens === 'recues'
        ? 'questions reçues depuis le banc du gouvernement, pas des questions posées'
        : null;
    if (avecSujet > 0) {
      points.push({
        cle: 'questions',
        valeur: questions.sujets[0].n,
        sur: avecSujet,
        texte: `${pluriel(questions.sujets[0].n, 'question au gouvernement porte', 'questions au gouvernement portent')} sur « ${questions.sujets[0].label} »`,
        suite: suiteNommee(questions.sujets, entreGuillemets),
        socle:
          `${formatNumber(questions.sujetsDistincts)} ${pluriel(questions.sujetsDistincts, 'sujet distinct', 'sujets distincts')}` +
          (avecSujet < questions.total
            ? `, et ${formatNumber(questions.total - avecSujet)} ${pluriel(questions.total - avecSujet, 'question dont aucun sujet n’est publié', 'questions dont aucun sujet n’est publié')}`
            : ''),
        garde,
      });
    } else {
      points.push({
        cle: 'questions',
        valeur: questions.total,
        sur: questions.total,
        texte: `${pluriel(questions.total, 'question au gouvernement, qui ne porte', 'questions au gouvernement, dont aucune ne porte')} de sujet publié`,
        suite: null,
        socle: 'la source ne dit pas sur quoi elles portaient, et la page ne le devine pas',
        garde,
      });
    }
  }

  // 5. Les textes portés. Ce qui « ressort » d'un texte, c'est son sort : le
  //    nommer sans dire où il s'est arrêté ne se lit pas. Seuls les textes
  //    ayant atteint l'examen en commission sont publiés (§6), et ceux qui sont
  //    restés au dépôt sont comptés plutôt que tus.
  if (textes && textes.publies.length) {
    const promulgues = textes.publies.filter((t) => t.stadeCle === 'promulgue');
    // `publies` est déjà trié du plus récent au plus ancien : nommer les trois
    // premiers est un ORDRE, pas un choix, et la phrase le dit. Sans elle, le
    // lecteur croirait à une sélection éditoriale.
    const nommables = (promulgues.length ? promulgues : textes.publies).slice(0, 3);
    const { total: ecartes, deposes, sansStade } = textes.ecartes;
    points.push({
      cle: 'textes',
      valeur: promulgues.length || textes.publies.length,
      sur: promulgues.length ? textes.publies.length : textes.total,
      texte: promulgues.length
        ? `${pluriel(promulgues.length, 'texte porté a été promulgué', 'textes portés ont été promulgués')}`
        : `${pluriel(textes.publies.length, 'texte porté a atteint', 'textes portés ont atteint')} l’examen en commission`,
      suite: `${pluriel(nommables.length, 'le plus récent', 'les plus récents')} : ${nommables.map((t) => `« ${t.titre} »`).join(', ')}`,
      socle:
        ecartes === 0
          ? null
          : sansStade === 0
            ? `${formatNumber(ecartes)} ${pluriel(ecartes, 'autre texte en est resté', 'autres textes en sont restés')} au dépôt`
            : `${formatNumber(ecartes)} ${pluriel(ecartes, 'autre texte', 'autres textes')} : ${formatNumber(deposes)} au dépôt, ${formatNumber(sansStade)} dont la source ne publie pas le stade`,
      // Un projet de loi engage le gouvernement, pas la personne qui le signe
      // comme ministre : le compter comme une initiative personnelle serait un
      // contresens, et la source range les deux sous le même `role: auteur`.
      garde:
        textes.projetsDeLoi > 0
          ? `dont ${formatNumber(textes.projetsDeLoi)} ${pluriel(textes.projetsDeLoi, 'projet de loi', 'projets de loi')} — des textes du gouvernement signés comme ministre, pas des propositions déposées comme parlementaire`
          : null,
    });
  }

  // 6. La qualité d'orateur. Le dénominateur est le nombre d'interventions dont
  //    la source PUBLIE la qualité : 35 des 3 933 de Jean-Luc Mélenchon. Diviser
  //    par le total ferait lire 1 % là où la mesure porte sur 100 % de ce
  //    qu'on sait.
  if (qualite?.sourcees > 0 && qualite.fonctions.length) {
    points.push({
      cle: 'qualite',
      valeur: qualite.fonctions[0].n,
      sur: qualite.sourcees,
      texte: `${pluriel(qualite.fonctions[0].n, 'intervention a été prononcée', 'interventions ont été prononcées')} comme « ${qualite.fonctions[0].label} »`,
      suite: suiteNommee(qualite.fonctions, entreGuillemets),
      socle:
        qualite.sourcees < qualite.total
          ? `${formatNumber(qualite.sourcees)} des ${formatNumber(qualite.total)} interventions portent une qualité publiée par la source`
          : 'qualité publiée par la source sur chacune',
      garde: null,
    });
  }

  return {
    points: points.slice(0, NB_POINTS_COUP_OEIL),
    // Le cadre initiative/réaction ne tient pas au banc du gouvernement. Un
    // seul fait le déclenche, et il est collecté.
    aSiegeAuGouvernement: (appartenances || []).length > 0,
  };
}

/* ── Livrable : ce qu'on n'a pas pu lire ─────────────────────────────────────
 *
 * `couverture` porte la cause sur 481 / 481 profils. Les états ne disent pas la
 * même chose et ne se confondent pas (§2 règle 5) : `couvert` est une mesure,
 * `hors_couverture` parle de la source, `non_collecte` parle de la collecte.
 * Les libellés viennent d'`EMPTY_LIST_CAUSES` (lot 1) — ils ne sont pas
 * réécrits ici.
 */
export const LISTES_COUVERTES = [
  { cle: 'mandats', titre: 'Mandats et fonctions' },
  { cle: 'votes', titre: 'Votes' },
  { cle: 'amendements', titre: 'Amendements' },
  { cle: 'textes_portes', titre: 'Textes portés' },
  { cle: 'interventions', titre: 'Interventions' },
];

/* ── Règle : une liste vide dit de quelle sorte de vide il s'agit ────────────
 *
 * Les quatre causes d'`EMPTY_LIST_CAUSES` (lot 1) n'affirment pas la même
 * chose, et `couverture` en porte souvent DEUX pour une même liste : « couvert
 * depuis 2012 » et « hors couverture avant ». Quand la liste est vide, c'est la
 * cause la plus spécifique qui explique le vide — une collecte écartée le dit
 * mieux qu'une borne de source, et une borne de source mieux qu'un zéro mesuré.
 * L'ordre est donc une priorité, pas un tri.
 */
const PRIORITE_CAUSES = ['non_collecte', 'hors_couverture', 'fait_etabli', 'couvert'];

export function causeListeVide(entrees) {
  const etats = (entrees || []).map((e) => e.etat);
  return PRIORITE_CAUSES.find((c) => etats.includes(c)) ?? null;
}

export function couvertureDesListes(couverture, decomptes) {
  return LISTES_COUVERTES.map(({ cle, titre }) => {
    const entrees = (couverture || {})[cle] || [];
    return {
      cle,
      titre,
      decompte: decomptes[cle] ?? null,
      etats: entrees.map((e) => ({
        etat: e.etat,
        cause: e.cause ?? null,
        debut: e.portee?.debut ?? null,
        fin: e.portee?.fin ?? null,
        preuve: e.preuve ?? null,
      })),
    };
  });
}

/* ── Règle : une limite se déclare, elle ne se comble pas ────────────────────
 *
 * Quatre manques que la trame suppose et que le corpus ne porte pas. Ils sont
 * CALCULÉS sur le profil affiché, pas recopiés en dur : une limite écrite à la
 * main survit à sa cause, et c'est ainsi qu'un transitoire devient permanent.
 *
 * `meta.avertissements` (#642) ne fournit aujourd'hui que des messages dont le
 * `destinataire` vaut `interne` — ils ne sont donc pas affichés. La clé est
 * lue, pas devinée : un avertissement `lecteur` apparaîtra le jour où il en
 * sera écrit un, sans toucher à ce composant.
 */
export function limitesDeclarees({ profil, roles, textes, sieges }) {
  const limites = [];

  for (const a of profil?.meta?.avertissements || []) {
    if (a.destinataire === 'lecteur') limites.push({ cle: `avertissement:${a.message}`, texte: a.message });
  }

  const sansPosition = roles.filter(
    (r) => r.institution === INSTITUTION_PARLEMENT && !r.position,
  );
  if (sansPosition.length) {
    limites.push({
      cle: 'position-non-declaree',
      texte:
        `L'Assemblée nationale déclare elle-même si un groupe est majoritaire, minoritaire ou d'opposition. ` +
        `Elle ne l'a pas fait pour ${sansPosition.length} des mandats parlementaires de ce profil — dont la législature en cours, ` +
        `pour laquelle la qualification n'est publiée sur aucun groupe. Le déduire d'un comportement de vote serait un jugement, pas une lecture.`,
    });
  }

  const aExerce = (profil?.mandats || []).some(
    (m) => m.categorie === 'fonction_gouvernementale' && m.fonction === FONCTION_MEMBRE,
  );
  const electifs = (profil?.mandats || []).filter((m) => m.categorie === 'mandat_electif');
  if (aExerce && electifs.length && electifs.every((m) => m.suspendu_pour_fonction_gouvernementale == null)) {
    limites.push({
      cle: 'suspension',
      texte:
        `Le corpus ne dit pas si un mandat s'est arrêté parce que la personne entrait au gouvernement : ` +
        `« suspendu_pour_fonction_gouvernementale » n'est renseigné sur aucun de ses ${electifs.length} mandats électifs.`,
    });
  }

  if (textes?.projetsDeLoi > 0) {
    limites.push({
      cle: 'projets-de-loi',
      texte:
        `${textes.projetsDeLoi} de ses ${textes.total} textes portés sont des projets de loi — des textes du gouvernement ` +
        `signés comme ministre — et le corpus les range sous le même rôle « auteur » qu'une proposition déposée comme parlementaire. ` +
        `Seul l'intitulé officiel les distingue.`,
    });
  }

  const enregistrements = electifs.length;
  if (sieges && enregistrements > sieges.length) {
    limites.push({
      cle: 'sieges-replies',
      texte:
        `La source rend ${enregistrements} enregistrements de mandat électif pour ${sieges.length} sièges : ` +
        `certains sièges portent deux entrées, l'une antérieure à l'estampillage de la chambre (#492). ` +
        `Ils sont regroupés sur leur date de fin, aucun n'est supprimé.`,
    });
  }

  return limites;
}
