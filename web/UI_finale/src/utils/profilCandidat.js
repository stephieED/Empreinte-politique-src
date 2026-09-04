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

import {
  formatNumber,
  isWholeTextVote,
  normalizeLabel,
  selectDerniereLectureVotes,
} from './lecture';

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
  { cle: 'commission', titre: 'Commissions', banc: INSTITUTION_PARLEMENT },
  { cle: 'commission_enquete', titre: "Commissions d'enquête et commissions spéciales", banc: INSTITUTION_PARLEMENT },
  { cle: 'mission_information', titre: "Missions d'information", banc: INSTITUTION_PARLEMENT },
  { cle: 'groupe_etudes', titre: "Groupes d'études", banc: INSTITUTION_PARLEMENT },
  { cle: 'delegation', titre: 'Délégations', banc: INSTITUTION_PARLEMENT },
  { cle: 'extra_parlementaire', titre: 'Organismes extra-parlementaires', banc: INSTITUTION_PARLEMENT },
  { cle: 'groupe_amitie', titre: "Groupes d'amitié", banc: INSTITUTION_PARLEMENT },

  /*
   * UNE FONCTION EXERCÉE NE L'EST PAS TOUJOURS AU PARLEMENT (#328).
   *
   * Un portefeuille ministériel est un siège occupé, au même titre qu'une
   * commission : il a un intitulé, des dates, une durée. Il manquait ici, et la
   * section ne montrait donc qu'une moitié des fonctions — 6 des 13 candidats
   * déclarés ont exercé au gouvernement.
   *
   * LE FILTRE PAR `fonction` EST SOURCÉ, pas lexical. La catégorie
   * `fonction_gouvernementale` mélange trois natures que le même champ sépare
   * déjà pour `appartenancesGouvernementales` :
   *
   *   `membre`     → l'appartenance au gouvernement. C'est l'ENVELOPPE, pas un
   *                  intitulé de fonction : elle nourrit la frise, et la
   *                  publier ici doublerait chaque portefeuille d'une ligne
   *                  « Gouvernement (BORNE) » qui ne dit pas ce qu'on y faisait ;
   *   `en mission` → un⋅e parlementaire en mission auprès d'un ministère, qui
   *                  RESTE parlementaire. La frise lui donne sa propre piste
   *                  depuis #328 ; elle a ici son propre bloc, pour la même
   *                  raison — la ranger avec les ministres serait le
   *                  contresens que la frise évite déjà ;
   *   le reste     → le portefeuille lui-même (Ministre, Secrétaire d'État,
   *                  Premier ministre).
   *
   * Filtrer sur le libellé (« Gouvernement (… ) ») aurait été une jointure par
   * ressemblance de chaîne, ce que `regrouper-nest-pas-joindre-639` interdit.
   */
  {
    cle: 'fonction_gouvernementale',
    titre: 'Portefeuilles ministériels',
    banc: INSTITUTION_GOUVERNEMENT,
    fonctions: (f) => f !== FONCTION_MEMBRE && f !== FONCTION_MISSION,
    sansMarque: true,
  },
  {
    cle: 'fonction_gouvernementale',
    titre: 'Missions auprès d’un ministère',
    suffixe: 'mission',
    banc: INSTITUTION_MISSION,
    fonctions: (f) => f === FONCTION_MISSION,
    sansMarque: true,
  },
];

/* ── Règle : le rôle ne s'affiche que lorsqu'il DISTINGUE ────────────────────
 *
 * `Membre` couvre 90,7 % des 14 128 mandats de commission du corpus, et 203 des
 * 225 des 13 candidats déclarés. L'écrire sur neuf lignes sur dix serait un mot
 * dont le lecteur ne tire rien — la règle 1 de #326 le disqualifie. Ce qui
 * s'affiche est ce qui distingue : une présidence, un rapport, un secrétariat.
 *
 * ⚠ La casse n'est pas normalisée à la source : `Membre`/`membre`,
 * `Vice-Président`/`vice-président`, `vice-présidente`. 48 des 225 mandats de
 * commission des 13 candidats déclarés sont en bas de casse. On normalise à
 * L'AFFICHAGE seulement : la donnée n'est pas touchée, et le défaut de collecte
 * reste lisible pour qui l'ouvre. Le dépôt a déjà tranché ce point côté fiches
 * de groupe — voir `normalisation-fonction-mandats-agreges`.
 */
const ROLES_PAR_DEFAUT = new Set(['membre', 'membre titulaire', 'membre de droit']);

export function roleDistinctif(fonction) {
  const brut = (fonction || '').trim();
  if (!brut || ROLES_PAR_DEFAUT.has(brut.toLowerCase())) return null;
  return brut.slice(0, 1).toUpperCase() + brut.slice(1).toLowerCase();
}

/* ── Règle : une durée de siège se compte en UNION d'intervalles ─────────────
 *
 * Le nombre affiché n'est PAS un compte d'enregistrements. La source réécrit un
 * même siège à chaque changement de composition : 27 entrées pour 5 ans 10 mois
 * continus à la commission des affaires sociales de Jérôme Guedj, dont aucune ne
 * dure un jour ; en face, 4 entrées pour 2 jours à la commission des lois. Le
 * compte ne distingue pas les deux, la durée si. C'est la même confusion que
 * #656 a séparée sur les fiches de groupe — « y siège » n'est pas « y est
 * passé » — vue depuis la fiche candidat.
 *
 * L'union, JAMAIS la somme : la fusion additive a laissé des doublons littéraux
 * (même début, fin décalée d'un jour), et la somme donnerait 9,5 ans là où il y
 * en a 5,8.
 *
 * Un mandat sans `debut` n'est comptable à aucune date : il ne compte pas, et il
 * ne vaut pas zéro non plus — il est simplement absent du calcul (§2 règle 5).
 */
const MS_PAR_JOUR = 86400000;
const JOURS_PAR_MOIS = 30.44;

export function aujourdhuiISO() {
  return new Date().toISOString().slice(0, 10);
}

export function joursCumules(mandats, aujourdhui = aujourdhuiISO()) {
  const intervalles = (mandats || [])
    .filter((m) => m.debut)
    .map((m) => [m.debut, m.actif || !m.fin ? aujourdhui : m.fin])
    .filter(([debut, fin]) => fin >= debut)
    .sort((a, b) => (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0));
  if (!intervalles.length) return 0;

  const ecart = (a, b) => Math.round((Date.parse(b) - Date.parse(a)) / MS_PAR_JOUR);
  let total = 0;
  let [debut, fin] = intervalles[0];
  for (const [d, f] of intervalles.slice(1)) {
    if (d <= fin) {
      if (f > fin) fin = f;
    } else {
      total += ecart(debut, fin);
      debut = d;
      fin = f;
    }
  }
  return total + ecart(debut, fin);
}

/* Une durée se lit en années et en mois, jamais en jours au-delà d'un mois : le
 * lecteur compare des sièges, pas des calendriers. En deçà, le jour reste la
 * seule unité honnête — « 0 mois » effacerait un passage réel. */
export function dureeDeSiege(jours) {
  if (jours < 31) return `${jours} jour${jours > 1 ? 's' : ''}`;
  const mois = Math.round(jours / JOURS_PAR_MOIS);
  const ans = Math.floor(mois / 12);
  const reste = mois % 12;
  if (!ans) return `${reste} mois`;
  const annees = `${ans} an${ans > 1 ? 's' : ''}`;
  return reste ? `${annees} ${reste} mois` : annees;
}

/* ── Règle : ce qui ressort dépasse la MOITIÉ du temps de mandat ─────────────
 *
 * Chaque catégorie montre ses trois fonctions les plus longues — toujours trois,
 * jamais une seule : un bloc à une grande ligne et un autre à trois petites
 * déséquilibraient la carte sans que la donnée le justifie.
 *
 * Une seule d'entre elles peut porter la marque, et c'est un FAIT, pas un seuil
 * choisi : la personne y a passé plus de la moitié de son temps de mandat. C'est
 * le test de majorité que #328 a déjà retenu pour les amendements (« ce dossier
 * porte plus que tous les autres réunis »), posé cette fois sur un dénominateur
 * qui en est un.
 *
 * LE DÉNOMINATEUR EST L'UNION DES SIÈGES ÉLECTIFS, et ce choix est le cœur de la
 * règle : on ne siège pas deux fois à la fois, donc c'est un vrai tout, et le
 * ratio est publiable (§2 règle 7). Le total des fonctions n'en serait pas un —
 * on appartient à treize groupes d'amitié simultanément, et leur somme fait
 * 33 ans sur une carrière de 19.
 *
 * Elle sait se taire, et c'est ce qui la rend utile : mesurée sur les 13 blocs
 * des deux profils de référence, elle parle 4 fois. Une règle qui ne peut pas se
 * taire ne dit rien quand elle parle (#326, règle 5).
 */
export const NB_FONCTIONS_MONTREES = 3;

export function fonctionsExercees(mandats, aujourdhui = aujourdhuiISO()) {
  const liste = mandats || [];
  const jours = joursCumules(
    liste.filter((m) => m.categorie === 'mandat_electif'),
    aujourdhui,
  );

  const blocs = CATEGORIES_FONCTIONS.map(({ cle, titre, banc, fonctions, sansMarque, suffixe }) => {
    const parIntitule = new Map();
    for (const m of liste.filter((x) => x.categorie === cle && (!fonctions || fonctions(x.fonction)))) {
      const label = m.label || 'Intitulé non publié';
      if (!parIntitule.has(label)) parIntitule.set(label, []);
      parIntitule.get(label).push(m);
    }

    const lignes = [...parIntitule.entries()]
      .map(([label, lot]) => {
        const j = joursCumules(lot, aujourdhui);
        const roles = [...new Set(lot.map((m) => roleDistinctif(m.fonction)).filter(Boolean))];
        return {
          label,
          jours: j,
          duree: dureeDeSiege(j),
          roles: roles.length ? roles.sort().join(' · ') : null,
          marquee: false,
        };
      })
      .sort((a, b) => b.jours - a.jours || a.label.localeCompare(b.label, 'fr'));

    // La marque va nécessairement à la plus longue : dépasser la moitié du tout
    // interdit qu'une autre le fasse aussi.
    //
    // Elle ne s'applique PAS aux blocs gouvernementaux (`sansMarque`) : leur
    // dénominateur serait le temps de mandat ÉLECTIF, et un portefeuille ne
    // s'y compare pas. Édouard Philippe a été Premier ministre trois ans sans
    // siéger : la marque aurait dit « plus de la moitié » d'un tout dont il
    // était absent, ce que §2 règle 7 interdit — un ratio se publie avec son
    // numérateur ET son dénominateur, et celui-ci n'en est pas un.
    if (!sansMarque && lignes.length && jours > 0 && lignes[0].jours * 2 > jours) {
      lignes[0].marquee = true;
    }

    return {
      // Deux blocs partagent la catégorie `fonction_gouvernementale` : leur clé
      // les distingue, sinon React en monterait deux sous la même.
      cle: suffixe ? `${cle}_${suffixe}` : cle,
      titre,
      // Le BANC dont relève la fonction, pour que la vue reprenne la grammaire
      // de couleurs de la frise plutôt que d'en inventer une.
      banc,
      nbIntitules: lignes.length,
      montrees: lignes.slice(0, NB_FONCTIONS_MONTREES),
      reste: lignes.slice(NB_FONCTIONS_MONTREES),
    };
  }).filter((c) => c.nbIntitules > 0);

  return { mandat: { jours, duree: dureeDeSiege(jours) }, blocs };
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

/** Combien de dossiers nommés « L'essentiel » montre — les suivants ne sont pas
 * cachés, ils sont ailleurs sur la page, dans « ce qu'il a proposé ». */
export const NB_DOSSIERS_NOMMES = 3;

/** Combien de commissions la barre de répartition porte. Trois, parce qu'au-delà
 * les segments deviennent trop courts pour que leur longueur se compare — pas
 * parce qu'un quatrième compterait moins. Le total est publié à côté. */
export const NB_COMMISSIONS_MONTREES = 3;

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
 *
 * `commissionDuDossier` rend la commission saisie au fond d'un dossier, lue
 * dans `pivot_data/commissions_dossiers.json` (#328). Absente, la répartition
 * n'est pas publiée — jamais remplacée par une déduction depuis l'intitulé.
 */
export function agregerAmendements(
  amendementsJoints,
  positionALaDate,
  commissionDuDossier = () => null,
) {
  const parLeg = new Map();
  const parBase = new Map();
  const parDossier = new Map();
  // La borne, comptée à part et jamais fondue dans le compte de dossiers : un
  // dépôt que la source ne rattache à aucun dossier n'est pas un dossier de
  // plus. Les deux compteurs vivaient sur une clé `dossier_id || texte_vise`,
  // qui publiait « 34 dossiers législatifs » là où il y en a 25 et 9 textes
  // visés orphelins — le défaut de clé `a or b` que décrit AGENTS.md §3a (#668).
  const textesSansDossier = new Set();
  let depotsSansDossier = 0;
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

    if (a.dossier_id) {
      if (!parDossier.has(a.dossier_id)) {
        parDossier.set(a.dossier_id, {
          cle: a.dossier_id,
          nom: nomDeDossier(a.dossier_titre, a.texte_vise),
          n: 0,
        });
      }
      parDossier.get(a.dossier_id).n += 1;
    } else {
      depotsSansDossier += 1;
      if (a.texte_vise) textesSansDossier.add(a.texte_vise);
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

  // La commission SAISIE AU FOND de chaque dossier, comptée en dossiers et
  // jamais en dépôts : un dossier très amendé ne pèse pas plus lourd qu'un
  // autre dans la répartition, sans quoi la barre mesurerait un épisode de
  // dépôt en masse (574 des 2 429 dépôts de Jérôme Guedj, 23,6 %, portent sur
  // le seul PLFRSS 2023) au lieu d'une manière de travailler.
  //
  // Départage alphabétique à égalité — jamais l'ordre d'insertion, qui rendrait
  // une égalité comme une avance. Laurent Wauquiez a 4 et 4 en tête : c'est la
  // DONNÉE qui ne produit pas de tendance, et la barre le montre en n'en
  // montrant pas.
  const parCommission = new Map();
  let dossiersSansCommission = 0;
  for (const d of classes) {
    const commission = commissionDuDossier(d.cle);
    const sigle = commission?.sigle || commission?.nom || null;
    if (!sigle) {
      dossiersSansCommission += 1;
      continue;
    }
    if (!parCommission.has(sigle)) parCommission.set(sigle, { sigle, nom: commission.nom ?? null, n: 0 });
    parCommission.get(sigle).n += 1;
  }
  const commissions = [...parCommission.values()].sort(
    (a, b) => b.n - a.n || a.sigle.localeCompare(b.sigle, 'fr'),
  );

  const dossiers = classes.length || depotsSansDossier
    ? {
        distincts: classes.length,
        depots: classes.reduce((s, d) => s + d.n, 0),
        nommes: nommes.slice(0, NB_DOSSIERS_NOMMES),
        distinctsNommes: nommes.length,
        depotsNommes: nommes.reduce((s, d) => s + d.n, 0),
        commissions,
        dossiersAvecCommission: commissions.reduce((s, c) => s + c.n, 0),
        dossiersSansCommission,
        // La borne se déclare, elle ne se comble pas (§2 règle 5). Elle est
        // grande : 2 499 des 2 831 dépôts de Jean-Luc Mélenchon, faute d'index
        // de la XIVe et de textes visés non résolus (issue #696).
        sansDossier: { depots: depotsSansDossier, textesVises: textesSansDossier.size },
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
  // #689 a scindé `auteur`, qui couvrait deux actes de nature différente. Les
  // trois valeurs neuves DOIVENT figurer ici : sans libellé, la fiche
  // afficherait la clé technique telle quelle dès le premier run qualifié.
  //
  // Le libellé nomme QUI EST À L'ORIGINE du texte, pas le terme juridique. Le
  // terme officiel — « projet » contre « proposition » — est contre-intuitif :
  // il ne dit pas ce qu'on propose mais qui le dépose, et un lecteur qui ne
  // connaît pas l'article 39 lit exactement l'inverse. « Résolution » est pire
  // encore : il se lit comme un morceau de loi, alors qu'une résolution ne
  // crée aucune règle. Mesuré sur les 423 textes portés des 13 candidats
  // déclarés : 313 projets de loi, 78 propositions, 26 résolutions.
  //
  // « à l'initiative du gouvernement » et « issue d'un(e) parlementaire »
  // disent l'initiative, JAMAIS la chambre de dépôt : 122 des 313 projets ont
  // été déposés au Sénat sans cesser d'être des textes du gouvernement, et 35
  // des 78 propositions sont sénatoriales (Bruno Retailleau). « Issue de
  // l'Assemblée nationale » aurait donc été faux 157 fois sur 391.
  //
  // La parenthèse de la résolution énumère les deux procédures que la source
  // distingue elle-même (`procedureParlementaire.code`) sans trancher laquelle
  // s'applique au texte affiché : 10 des 26 sont des résolutions de l'article
  // 34-1 (l'Assemblée déclare une position), 16 relèvent du code 8 générique,
  // dont les intitulés sont des demandes d'enquête. « Demande », et non
  // « décision » : 2 des 26 seulement portent le stade `adopte`, et un texte
  // déposé sans être voté n'a rien décidé (AGENTS.md §2 règle 5).
  initiateur_projet_de_loi: "Projet de loi à l'initiative du gouvernement",
  auteur_proposition_de_loi: "Proposition de loi issue d'un(e) parlementaire",
  auteur_proposition_de_resolution:
    'Résolution (prise de position ou demande procédurale)',
  auteur: 'Auteur',
  rapporteur: 'Rapporteur',
  'co-rapporteur': 'Co-rapporteur',
};

/*
 * Un projet de loi est un texte du GOUVERNEMENT, porté comme ministre — pas une
 * proposition déposée comme parlementaire.
 *
 * `nature_texte` (#689) est le fait sourcé : le préfixe de l'uid du document
 * déposé, lu dans l'archive AN. Il fait foi dès qu'il est présent, y compris
 * contre l'intitulé.
 *
 * Le repli par intitulé est CONSERVÉ, et il est déclaré : le corpus publié ne
 * porte `nature_texte` qu'à partir du run qui recollecte les dossiers, et le
 * retirer aujourd'hui afficherait 0 projet de loi là où la page en signale 13.
 * Il ne tient que sur les XVI/XVII — les dossiers de la XV portent des
 * intitulés descriptifs (« Bioéthique », « CETA ») et il en manque 283 sur 304.
 * Condition de retrait : la §5c du quality gate à 0 initiateur sans nature.
 */
const PROJET_DE_LOI = /^projet de loi\b/;

export function estProjetDeLoi(texte) {
  if (texte?.nature_texte) return texte.nature_texte === 'projet_de_loi';
  return PROJET_DE_LOI.test(normalizeLabel(texte?.titre));
}

/*
 * De quelle institution un texte porté relève — la SEULE attribution de rôle du
 * dépôt qui soit un fait sourcé texte par texte (#689).
 *
 * DEUX CHAMPS, PAS UN. La nature ne suffit pas : Gabriel Attal est RAPPORTEUR
 * d'un projet de loi, ce qui est un acte parlementaire sur un texte du
 * gouvernement. Le ranger au gouvernement sur sa seule nature serait le
 * contresens exact que #689 a corrigé dans l'autre sens. `role` est lu d'abord,
 * et il est lui-même dérivé de la nature par #689 — sauf `rapporteur` /
 * `co-rapporteur`, qui existent indépendamment d'elle.
 *
 * TROIS ÉTATS, PAS DEUX : quand ni le rôle ni la nature ne tranchent (4 des 423
 * textes portés des 13 candidats déclarés, tous `role: auteur` sans nature), le
 * texte n'est attribué à AUCUNE institution. Ranger par défaut au parlement
 * inventerait une initiative personnelle (§2 règle 5).
 *
 * `estProjetDeLoi` ci-dessus répond à une AUTRE question — « de quelle nature
 * est ce texte » — et reste indifférent au rôle : les deux ne se confondent pas
 * et ne se remplacent pas.
 */
const ROLE_INSTITUTION = {
  initiateur_projet_de_loi: INSTITUTION_GOUVERNEMENT,
  auteur_proposition_de_loi: INSTITUTION_PARLEMENT,
  auteur_proposition_de_resolution: INSTITUTION_PARLEMENT,
  rapporteur: INSTITUTION_PARLEMENT,
  'co-rapporteur': INSTITUTION_PARLEMENT,
};

export function institutionDuTexte(texte) {
  const parLeRole = ROLE_INSTITUTION[texte?.role];
  if (parLeRole) return parLeRole;
  const nature = texte?.nature_texte;
  if (nature === 'projet_de_loi') return INSTITUTION_GOUVERNEMENT;
  if (nature === 'proposition_de_loi' || nature === 'proposition_de_resolution') {
    return INSTITUTION_PARLEMENT;
  }
  if (nature) return null;
  // Repli d'intitulé, déclaré : il ne tranche que vers le gouvernement — un
  // intitulé qui ne commence pas par « projet de loi » ne prouve pas une
  // initiative parlementaire.
  return PROJET_DE_LOI.test(normalizeLabel(texte?.titre)) ? INSTITUTION_GOUVERNEMENT : null;
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
        // La CLÉ brute à côté du libellé : composer une phrase sur le libellé
        // la casserait au premier changement de mot (`LIBELLE_ROLE_TEXTE`).
        roleCle: t.role ?? null,
        stade: LIBELLE_STADE[t.stade_procedural] || t.stade_procedural,
        stadeCle: t.stade_procedural,
        legislature: t.legislature ?? null,
        dateMin: t.date_min ?? null,
        dateMax: t.date_max ?? null,
        projetDeLoi: estProjetDeLoi(t),
        institution: institutionDuTexte(t),
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
    // Les textes publiés que la source ne qualifie pas : ni projet, ni
    // proposition. Comptés, jamais rangés par défaut d'un côté (§2 règle 5).
    sansNature: publies.filter((t) => institutionDuTexte(t) === null).length,
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
export function depuisLeBancDuGouvernement(interventions, appartenances) {
  const liste = interventions || [];
  const periodes = appartenances || [];
  const dansGouvernement = (date) =>
    Boolean(date) && periodes.some((p) => p.debut <= date && date <= p.fin);
  const ministerielles = liste.filter((i) => i.fonction && dansGouvernement(i.date)).length;
  return {
    total: liste.length,
    ministerielles,
    // La MAJORITÉ tranche, et rien d'autre : un profil sans qualité publiée
    // (Jérôme Guedj, 0 des 2 702) tombe du côté parlementaire, ce qui est le
    // constat de la source et non une déduction sur la personne. Le compte des
    // deux est publié à côté du verdict, pour que le lecteur voie sur quoi il
    // repose.
    banc: ministerielles > liste.length / 2 ? INSTITUTION_GOUVERNEMENT : INSTITUTION_PARLEMENT,
  };
}

export function directionQuestionsGouvernement(interventions, appartenances) {
  const qag = (interventions || []).filter((i) => i.type_detail === 'question_gouvernement');
  if (!qag.length) return null;

  const { ministerielles, banc } = depuisLeBancDuGouvernement(qag, appartenances);

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
    banc,
    sens: banc === INSTITUTION_GOUVERNEMENT ? 'recues' : 'posees',
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
 * Le décompte porte sur des TEXTES, pas sur des votes (#711) : un texte revenu
 * plusieurs fois devant l'Assemblée ne compte qu'une fois, à sa DERNIÈRE
 * LECTURE — la règle qu'`AGENTS.md` §6 publie depuis toujours et que rien
 * n'appliquait. `selectDerniereLectureVotes` (lot 1) la porte, elle non plus
 * n'est pas réécrite ici, et `LAST_READING_RULE` la publie sur la page.
 *
 * La dernière lecture d'un texte se lit sur le CORPUS des scrutins, jamais sur
 * les seuls votes de la personne. Mesuré sur `gabriel-attal` : ses 150 votes
 * sur l'ensemble d'un texte donnent 120 textes si l'on ordonne ses propres
 * lectures, mais 111 si l'on ordonne celles du corpus. Les 9 d'écart sont des
 * textes dont il a voté une lecture ANTÉRIEURE et pas la dernière — dont le
 * projet de loi de simplification de la vie économique, qu'il avait déposé
 * comme Premier ministre, voté contre en première lecture le 17/06/2025, adopté
 * sur le texte de la commission mixte paritaire le 14/04/2026, scrutin où
 * aucune position de lui n'est enregistrée. Afficher ce « contre » comme sa
 * position sur cette loi aurait été faux, et dire pourquoi il manque au scrutin
 * final publierait une absence individuelle (§2 règle 3).
 *
 * Sans le corpus, la dernière lecture n'est pas déterminable : la fonction le
 * DÉCLARE (`derniereLectureDisponible`) au lieu de retomber sur les seuls votes
 * de la personne. Une règle de repli qui remplace silencieusement la règle
 * publiée est ce qui a rendu #510 invisible.
 *
 * « Un membre du gouvernement ne vote pas » est un FAIT ÉTABLI sur la personne,
 * pas une lacune de collecte — sans cette phrase, Attal paraît absent de 2018 à
 * 2024. Il n'est pas non plus une raison de masquer ses autres votes : la
 * maquette suspendait la barre entière, ce qui aurait tu 150 votes réels.
 *
 * AUCUN ratio de participation : un dénominateur « scrutins où la personne
 * aurait pu voter » est un taux d'assiduité individuel (§2 règle 3).
 */
export function votesDuProfil(
  votesJoints,
  appartenances,
  rolesParlementaires,
  scrutinsCorpus = null,
) {
  const liste = votesJoints || [];
  const surEnsemble = liste.filter((v) => isWholeTextVote(v.scrutin));

  // `null` — et non un tableau vide — quand le corpus des scrutins n'a pas pu
  // être lu : « je ne sais pas quelle est la dernière lecture » n'est pas
  // « aucun texte » (§2 règle 5).
  const dernieresLectures = scrutinsCorpus
    ? new Set(selectDerniereLectureVotes(scrutinsCorpus).map((s) => s.id))
    : null;
  const retenus = dernieresLectures
    ? surEnsemble.filter((v) => dernieresLectures.has(v.scrutin_id))
    : [];

  const positions = new Map();
  for (const v of retenus) positions.set(v.position, (positions.get(v.position) || 0) + 1);

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
    derniereLectureDisponible: dernieresLectures !== null,
    textes: retenus.length,
    // Ce que le repli a retiré, nommé plutôt que laissé à la soustraction. Il
    // ne dit RIEN d'une absence : il compte des positions bien réelles de la
    // personne, sur des lectures qu'un scrutin plus tardif a suivies.
    lecturesDepassees: surEnsemble.length - retenus.length,
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

/* ── Livrable : L'essentiel ──────────────────────────────────────────────────
 *
 * Cinq points, tirés d'un VIVIER de sept, chacun issu d'un jeu de données
 * distinct. Aucun rapprochement thématique, aucune synthèse : Empreinte
 * politique ne classe pas les textes par sujet (§2 règle 8), et chaque point est
 * DÉRIVÉ par comptage d'un champ de la source, jamais d'une table de mots-clés
 * écrite à la main.
 *
 * La section s'appelait « Coup d'œil ». Le titre promettait de la rapidité, pas
 * du contenu, et c'est le contenu qui est en jeu ici.
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
 *    même population.
 *
 * 3. LE MOINS DE NOTES POSSIBLE. Une note qui met en garde contre un contresens
 *    est une information et se garde (`garde`) : « questions reçues depuis le
 *    banc du gouvernement, pas des questions posées » évite de lire à l'envers
 *    les 743 questions de Gabriel Attal. Une note qui justifie notre méthode ne
 *    sert qu'à nous et se retire.
 *
 * 4. SON RÔLE, qui est un fait collecté. Voir ci-dessous.
 *
 * ── Le vivier et la garantie de rôle (option C) ────────────────────────────
 *
 * LE DÉFAUT QU'ELLE CORRIGE EST STRUCTUREL. Les cinq points étaient cinq
 * CATÉGORIES FIXES — interventions, amendements, commissions, questions, textes
 * — qui décrivent le métier d'un⋅e député⋅e. Chez un⋅e ancien⋅ne ministre elles
 * se remplissent surtout de ce que son ministère a produit, et son travail
 * parlementaire disparaît : les 34 « textes portés » de Gabriel Attal étaient à
 * 31 des projets de loi du gouvernement, ses 743 « questions au gouvernement »
 * lui étaient posées, et ses 49 amendements de député se lisaient comme un
 * résidu à côté.
 *
 * LE RÔLE SE LIT SUR UN FAIT COLLECTÉ, jamais sur une catégorie éditoriale :
 *
 *  - `gouvernement` est tenu si la personne a été MEMBRE d'un gouvernement
 *    (`appartenancesGouvernementales`) — 6 des 13 candidats déclarés au SHA
 *    f635cb60, 01/09/2026 : Bruno Retailleau, Édouard Philippe, Gabriel Attal,
 *    Laurent Wauquiez, Ségolène Royal, Xavier Bertrand. Un⋅e parlementaire EN
 *    MISSION auprès d'un ministère n'en est pas membre : les 2 mandats « en
 *    mission » de Jérôme Guedj sont correctement écartés ;
 *  - `parlement` est tenu dès qu'un point du vivier en relève.
 *
 * ET LE RÔLE DE CHAQUE POINT AUSSI. Aucun n'est étiqueté à la main :
 *
 *  - `amendements` → parlement. Les 6 651 dépôts comme auteur principal des 13
 *    candidats déclarés portent `type_deposant` `depute` (6 645) ou
 *    `commission_rapporteur` (6), JAMAIS `gouvernement`, et aucun ne tombe dans
 *    une période d'appartenance gouvernementale ;
 *  - `commissions` → parlement : un siège en commission est un mandat
 *    parlementaire, la source le range sous `mandats` ;
 *  - `interventions` et `questions` → le banc d'où la parole est portée, par la
 *    règle à deux conditions de `depuisLeBancDuGouvernement` (qualité publiée
 *    par la source ET date dans une période de gouvernement) ;
 *  - `textes` → SCINDÉ EN DEUX POINTS par `nature_texte` (#689), et c'est la
 *    réparation principale : porter un projet de loi au nom du gouvernement
 *    n'est pas déposer une proposition comme parlementaire, et la source
 *    rangeait les deux sous le même `role: auteur` jusqu'à #689 ;
 *  - `qualite` → aucun rôle : il compte les qualités d'orateur des deux bancs
 *    confondus. Un point sans rôle ne peut pas satisfaire la garantie ; il ne
 *    remplit qu'une place restante.
 *
 * LA GARANTIE. Pour chaque rôle tenu, le premier point du vivier qui en relève
 * est retenu AVANT que les places restantes ne soient remplies dans l'ordre.
 * L'ordre du vivier est fixe pour les treize ; la sélection est ensuite remise
 * dans cet ordre, si bien que la garantie change QUI est retenu, jamais dans
 * quel ordre la page se lit.
 *
 * ELLE NE FABRIQUE RIEN. Un rôle tenu dont le vivier ne porte aucun point ne
 * reçoit pas de place : la section le DIT (`rolesSansPoint`) au lieu d'inventer
 * un chiffre. C'est le cas de Ségolène Royal et de Xavier Bertrand, membres de
 * gouvernement dont le corpus ne publie ni intervention, ni question, ni texte
 * porté.
 *
 * ELLE VAUT IDENTIQUEMENT POUR UN⋅E DÉPUTÉ⋅E PUR⋅E : un seul rôle tenu, tous
 * les points en relèvent, la garantie retient le premier — c'est-à-dire ce que
 * l'ordre fixe aurait donné. AUCUN SECOND GABARIT : mêmes points possibles,
 * même ordre, mêmes champs pour les treize.
 *
 * CE QU'ELLE NE FAIT PAS AUJOURD'HUI : elle ne déplace aucun point sur les 13
 * profils publiés — sur chacun, l'ordre fixe suffisait déjà à représenter les
 * rôles tenus. Elle est écrite quand même, parce que c'est la règle qui empêche
 * le défaut de revenir quand le vivier ou le corpus bouge, et elle est
 * verrouillée sur un cas construit (`tests/test_essentiel_328.py`).
 *
 * L'ordre est fixe pour les treize ; ne sont rendus que les points dont la
 * donnée existe, cinq au plus. Un point absent n'est pas remplacé : c'est la
 * trame qui uniformise les emplacements, pas leur remplissage.
 */
export const NB_POINTS_ESSENTIEL = 5;

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

/** Ce que le lot parlementaire contient VRAIMENT — déposer une proposition et
 * rapporter un texte ne sont pas le même acte, et écrire « propositions » sur un
 * lot qui contient un rapport serait faux. Le libellé se compose du contenu, il
 * n'est pas choisi d'avance. */
function natureDesTextesPortes(lot) {
  const rapportes = lot.filter((t) => t.roleCle === 'rapporteur' || t.roleCle === 'co-rapporteur').length;
  const deposes = lot.length - rapportes;
  const morceaux = [];
  if (deposes > 0) morceaux.push(pluriel(deposes, 'proposition déposée', 'propositions déposées'));
  if (rapportes > 0) morceaux.push(pluriel(rapportes, 'texte rapporté', 'textes rapportés'));
  return morceaux.join(' et ');
}

/** Comment un point se donne à voir. La forme suit le cas, jamais l'inverse :
 * « 27 sur 60 » se compare mal en prose, cinq intitulés de texte se lisent très
 * bien en liste. Valeur fermée — un rendu inconnu retombe sur `ratio`. */
export const RENDU_RATIO = 'ratio';
export const RENDU_COUPLE = 'couple';
export const RENDU_PODIUM = 'podium';
export const RENDUS_POINT = [RENDU_RATIO, RENDU_COUPLE, RENDU_PODIUM];

/** Les libellés des deux rôles, tels que la page les écrit. « au banc du
 * gouvernement » et non « comme ministre » : la source publie une appartenance,
 * pas toujours un portefeuille. */
export const LIBELLE_ROLE_POINT = {
  [INSTITUTION_PARLEMENT]: 'comme parlementaire',
  [INSTITUTION_GOUVERNEMENT]: 'au banc du gouvernement',
};

/** Le même rôle, nommé pour la phrase qui déclare qu'AUCUN point ne le
 * documente. Forme nominale : « son passage au gouvernement » se lit, « au banc
 * du gouvernement » ne s'insère pas dans cette phrase-là. */
export const LIBELLE_ROLE_ABSENT = {
  [INSTITUTION_PARLEMENT]: 'son travail parlementaire',
  [INSTITUTION_GOUVERNEMENT]: 'son passage au gouvernement',
};

/*
 * Le vivier : tous les points que la donnée permet, dans l'ordre fixe des
 * treize. La sélection vient après, et elle seule décide lesquels sont rendus.
 */
function vivierDesPoints({
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
  //
  //    Pas de barre ici, et c'est un choix de cas : 417 points de l'ordre du
  //    jour forment un vocabulaire OUVERT, où trois segments sur 417 ne disent
  //    rien de la forme. C'est le nombre 417 qui la dit.
  const liste = interventions || [];
  const situees = liste.filter((i) => i.sujet);
  if (situees.length) {
    const parSujet = new Map();
    for (const i of situees) parSujet.set(i.sujet, (parSujet.get(i.sujet) || 0) + 1);
    const classes = [...parSujet.entries()]
      .map(([label, n]) => ({ label, n }))
      .sort((a, b) => b.n - a.n || a.label.localeCompare(b.label, 'fr'));
    const muettes = liste.length - situees.length;
    const { banc, ministerielles } = depuisLeBancDuGouvernement(liste, appartenances);
    points.push({
      cle: 'interventions',
      role: banc,
      rendu: RENDU_RATIO,
      valeur: classes[0].n,
      sur: situees.length,
      texte: `${pluriel(classes[0].n, 'intervention porte', 'interventions portent')} sur « ${classes[0].label} »`,
      suite: suiteNommee(classes, entreGuillemets),
      socle:
        `${formatNumber(classes.length)} ${pluriel(classes.length, 'point', 'points')} de l’ordre du jour en tout` +
        (muettes > 0
          ? `, et ${formatNumber(muettes)} ${pluriel(muettes, 'intervention dont le compte rendu n’indique', 'interventions dont le compte rendu n’indique')} aucun point`
          : ''),
      garde:
        banc === INSTITUTION_GOUVERNEMENT
          ? `${ministerielles === liste.length ? `toutes ces ${formatNumber(liste.length)}` : `${formatNumber(ministerielles)} de ces ${formatNumber(liste.length)}`} interventions portent une qualité ministérielle publiée par la source, à une date d’appartenance à un gouvernement`
          : null,
    });
  }

  // 2. Le COUPLE : combien de dossiers législatifs, et combien de dépôts sur
  //    eux. Un nombre seul appellerait un classement ; deux nombres qui varient
  //    en sens inverse appellent une lecture. Marine Le Pen fait 83 dossiers
  //    pour 685 dépôts (large et léger), Laurent Wauquiez 14 pour 326
  //    (l'inverse) — aucun des deux n'est « meilleur », et c'est ce qui rend le
  //    couple publiable (§2 règle 1).
  //
  //    Ce qui a été écarté, et pourquoi (mesures du 01/09/2026, 13 candidats
  //    déclarés) : le COMPTE BRUT ne dit rien — la médiane de dépôts par dossier
  //    va de 2,5 à 8 sur les quatre profils qui en portent plus de 50, et
  //    l'écart entre 2 831 et 584 mesure la participation à un épisode de dépôt
  //    en masse : 574 des 2 429 dépôts de Jérôme Guedj (23,6 %) portent sur le
  //    seul PLFRSS 2023, 182 des 584 de Laurent Wauquiez (31,2 %) sur le seul
  //    PLF 2026. FILTRER SUR LES ADOPTÉS
  //    mesure le terrain, pas la personne, et le `sort` est inconnu sur 1 822
  //    de ces 2 831 : un décompte sur un dénominateur amputé de 64 % viole
  //    §2 règle 5, et §6 interdit tout taux d'adoption entre types de
  //    déposants. COMPTER LES `texte_vise` DISTINCTS est faux : ce sont des
  //    LECTURES, pas des lois — Jérôme Guedj passe de 47 lectures à 25 dossiers.
  //
  //    QUAND AUCUN DOSSIER N'EST RÉSOLU, le point ne disparaît pas : il dit le
  //    nombre de dépôts et pourquoi il ne peut rien en dire de plus. Xavier
  //    Bertrand (62 dépôts) et Édouard Philippe (6) sont dans ce cas — leurs
  //    textes visés relèvent de la XIVe législature, dont l'archive de dossiers
  //    n'est pas ingérée. Supprimer le point ferait disparaître 68 dépôts
  //    collectés (§2 règle 5).
  if (dossiers && dossiers.distincts === 0 && dossiers.sansDossier.depots > 0) {
    const { depots: horsDossier, textesVises } = dossiers.sansDossier;
    points.push({
      cle: 'amendements',
      role: INSTITUTION_PARLEMENT,
      rendu: RENDU_RATIO,
      valeur: horsDossier,
      sur: horsDossier,
      texte: `${pluriel(horsDossier, 'amendement déposé comme auteur principal', 'amendements déposés comme auteur principal')}`,
      suite: null,
      socle: null,
      garde: `${pluriel(horsDossier, 'il vise', 'ils visent')} ${formatNumber(textesVises)} ${pluriel(textesVises, 'texte que la source ne rattache', 'textes que la source ne rattache')} à aucun dossier législatif : ni le dossier, ni la commission qui l’a examiné ne sont publiables ici`,
    });
  } else if (dossiers && dossiers.distincts > 0) {
    const nomme = dossiers.nommes[0] || null;
    const anonymes = dossiers.distincts - dossiers.distinctsNommes;
    const { depots: horsDossier, textesVises } = dossiers.sansDossier;
    points.push({
      cle: 'amendements',
      role: INSTITUTION_PARLEMENT,
      rendu: RENDU_COUPLE,
      couple: [
        {
          n: dossiers.distincts,
          label: pluriel(dossiers.distincts, 'dossier législatif amendé', 'dossiers législatifs amendés'),
        },
        {
          n: dossiers.depots,
          label: pluriel(dossiers.depots, 'amendement déposé sur eux', 'amendements déposés sur eux'),
        },
      ],
      // « examinées par », jamais « travaille sur » : une commission n'est pas
      // un sujet — « Lois » couvre l'immigration, la justice et les
      // institutions. Aide à la lecture (§2 règle 8), pas position déclarée.
      repartition: dossiers.commissions.length
        ? {
            titre: 'Dossiers examinés par',
            segments: dossiers.commissions.slice(0, NB_COMMISSIONS_MONTREES),
            // Le dénominateur de la barre est le TOTAL des dossiers, pas la
            // somme des trois segments : ce qui reste — autres commissions,
            // dossiers sans commission publiée — reste visible comme du vide,
            // au lieu d'être normalisé à 100 % (DESIGN_SYSTEM §5).
            total: dossiers.distincts,
            reste:
              dossiers.commissions.length > NB_COMMISSIONS_MONTREES
                ? dossiers.commissions.length - NB_COMMISSIONS_MONTREES
                : 0,
            sansCommission: dossiers.dossiersSansCommission,
          }
        : null,
      texte: nomme ? `le plus amendé : « ${nomme.nom} » (${formatNumber(nomme.n)})` : null,
      suite: nomme
        ? suiteNommee(
            dossiers.nommes.map((d) => ({ label: d.nom, n: d.n })),
            entreGuillemets,
          )
        : null,
      socle:
        anonymes > 0
          ? `${formatNumber(anonymes)} ${pluriel(anonymes, 'de ces dossiers n’est nommé par aucune entrée d’index', 'de ces dossiers ne sont nommés par aucune entrée d’index')}`
          : null,
      // LA BORNE SE DÉCLARE. Chez Jean-Luc Mélenchon la répartition reposerait
      // sur 12 % de ses dépôts : la page l'écrit au lieu de la présenter comme
      // complète (§2 règle 5).
      garde:
        horsDossier > 0
          ? `${formatNumber(horsDossier)} ${pluriel(horsDossier, 'autre dépôt vise', 'autres dépôts visent')} ${formatNumber(textesVises)} ${pluriel(textesVises, 'texte que la source ne rattache', 'textes que la source ne rattache')} à aucun dossier : ${pluriel(horsDossier, 'il ne figure', 'ils ne figurent')} ni dans les deux nombres ci-dessus${dossiers.commissions.length ? ', ni dans les commissions' : ''}`
          : null,
    });
  }

  // 3. Les commissions. Déjà nommées, rien à réparer — la suite l'est aussi.
  //    En PODIUM : trois rangs côte à côte se comparent d'un regard là où la
  //    prose oblige à relire. Un siège en commission est un mandat
  //    parlementaire, quel que soit ce que la personne a fait par ailleurs.
  //
  //    Le point se lit sur la DURÉE, jamais sur un compte d'entrées : #328 a
  //    mesuré que le nombre d'entrées d'un intitulé compte des enregistrements
  //    de collecte (27 chez Guedj pour 5 ans 10 mois, 4 chez un autre pour
  //    2 jours) et ne dit rien du temps passé. Il lit donc la forme rendue par
  //    `fonctionsExercees` — `blocs[].montrees`, déjà triées par durée — et
  //    n'en recalcule aucune part.
  const commissions = (fonctions?.blocs || []).find((f) => f.cle === 'commission');
  if (commissions?.montrees.length) {
    const tete = commissions.montrees[0];
    points.push({
      cle: 'commissions',
      role: INSTITUTION_PARLEMENT,
      rendu: RENDU_PODIUM,
      valeur: tete.jours,
      sur: fonctions.mandat.jours,
      rangs: commissions.montrees,
      texte: `le temps passé en commission l'a le plus été à la ${tete.label} : ${tete.duree}`,
      // Pas de `suite` : le podium NOMME déjà les deux suivantes avec leur
      // durée. La garder ferait lire deux fois la même liste, une fois en
      // prose et une fois en colonnes.
      suite: null,
      socle:
        commissions.nbIntitules > NB_COMMISSIONS_MONTREES
          ? `${formatNumber(commissions.nbIntitules)} commissions en tout`
          : null,
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
        role: questions.banc,
        rendu: RENDU_RATIO,
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
        role: questions.banc,
        rendu: RENDU_RATIO,
        valeur: questions.total,
        sur: questions.total,
        texte: `${pluriel(questions.total, 'question au gouvernement, qui ne porte', 'questions au gouvernement, dont aucune ne porte')} de sujet publié`,
        suite: null,
        socle: 'la source ne dit pas sur quoi elles portaient, et la page ne le devine pas',
        garde,
      });
    }
  }

  // 5 et 6. Les textes portés, SCINDÉS par l'institution qui les initie.
  //    Rien de graphique : cinq intitulés se lisent en liste. Seuls les textes
  //    ayant atteint l'examen en commission sont publiés (§6), et ceux qui sont
  //    restés au dépôt sont comptés plutôt que tus.
  if (textes && textes.publies.length) {
    const { total: ecartes, deposes, sansStade } = textes.ecartes;
    // Le socle des écartés est commun aux deux points : il décrit la même
    // liste, et le répéter deux fois le ferait lire comme deux lacunes.
    const socleEcartes =
      ecartes === 0
        ? null
        : sansStade === 0
          ? `${formatNumber(ecartes)} ${pluriel(ecartes, 'autre texte porté en est resté', 'autres textes portés en sont restés')} au dépôt`
          : `${formatNumber(ecartes)} ${pluriel(ecartes, 'autre texte porté', 'autres textes portés')} : ${formatNumber(deposes)} au dépôt, ${formatNumber(sansStade)} dont la source ne publie pas le stade`;

    let premierPointDeTexte = true;
    for (const institution of [INSTITUTION_GOUVERNEMENT, INSTITUTION_PARLEMENT]) {
      const lot = textes.publies.filter((t) => t.institution === institution);
      if (!lot.length) continue;
      const promulgues = lot.filter((t) => t.stadeCle === 'promulgue');
      // `publies` est déjà trié du plus récent au plus ancien : nommer les trois
      // premiers est un ORDRE, pas un choix, et la phrase le dit. Sans elle, le
      // lecteur croirait à une sélection éditoriale.
      const nommables = (promulgues.length ? promulgues : lot).slice(0, 3);
      const gouvernemental = institution === INSTITUTION_GOUVERNEMENT;
      // Le socle des écartés et le compte des textes sans nature décrivent la
      // MÊME liste : ils vont sur le premier point de texte réellement produit,
      // jamais sur une moitié fixe — l'accrocher au point gouvernemental le
      // faisait disparaître de tous les profils qui n'en ont pas.
      const porteLeSocle = premierPointDeTexte;
      premierPointDeTexte = false;
      points.push({
        cle: gouvernemental ? 'textes_gouvernement' : 'textes_parlement',
        role: institution,
        rendu: RENDU_RATIO,
        // Le dénominateur est l'ENSEMBLE des textes publiés de la personne :
        // c'est ce qui dit quelle part de ses textes portés relève de ce banc.
        valeur: lot.length,
        sur: textes.publies.length,
        texte:
          (gouvernemental
            ? `${pluriel(lot.length, 'projet de loi porté au nom du gouvernement', 'projets de loi portés au nom du gouvernement')}`
            : natureDesTextesPortes(lot)) +
          (promulgues.length
            ? `, dont ${formatNumber(promulgues.length)} ${pluriel(promulgues.length, 'promulgué', 'promulgués')}`
            : ''),
        suite: `${pluriel(nommables.length, 'le plus récent', 'les plus récents')} : ${nommables.map((t) => `« ${t.titre} »`).join(', ')}`,
        socle: porteLeSocle
          ? [
              socleEcartes,
              textes.sansNature > 0
                ? `${formatNumber(textes.sansNature)} ${pluriel(textes.sansNature, 'texte publié que la source ne qualifie ni de projet ni de proposition', 'textes publiés que la source ne qualifie ni de projet ni de proposition')}`
                : null,
            ]
              .filter(Boolean)
              .join(' ; ') || null
          : null,
        // Un projet de loi engage le gouvernement, pas la personne qui le signe
        // comme ministre. La garde disait cela sous un point qui mélangeait les
        // deux ; la scission la rend au point qu'elle concerne.
        garde: gouvernemental
          ? 'des textes du gouvernement, portés comme membre de celui-ci — pas des propositions déposées comme parlementaire'
          : null,
      });
    }
  }

  // 7. La qualité d'orateur. Le dénominateur est le nombre d'interventions dont
  //    la source PUBLIE la qualité : 35 des 3 933 de Jean-Luc Mélenchon. Diviser
  //    par le total ferait lire 1 % là où la mesure porte sur 100 % de ce
  //    qu'on sait. AUCUN RÔLE : il compte les deux bancs confondus.
  if (qualite?.sourcees > 0 && qualite.fonctions.length) {
    points.push({
      cle: 'qualite',
      role: null,
      rendu: RENDU_RATIO,
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

  return points;
}

/**
 * Retient au plus `NB_POINTS_ESSENTIEL` points, en réservant une place au
 * premier point de chaque rôle tenu.
 *
 * Le résultat est remis dans l'ordre du vivier : la garantie change QUI est
 * retenu, jamais l'ordre de lecture. `rolesTenus` est une liste, jamais un
 * booléen — un troisième rôle s'ajouterait sans toucher à cette fonction.
 */
export function selectionnerPoints(vivier, rolesTenus, limite = NB_POINTS_ESSENTIEL) {
  const retenus = new Set();
  for (const role of rolesTenus) {
    if (retenus.size >= limite) break;
    const premier = vivier.findIndex((p) => p.role === role);
    if (premier >= 0) retenus.add(premier);
  }
  for (let i = 0; i < vivier.length && retenus.size < limite; i += 1) retenus.add(i);
  return [...retenus].sort((a, b) => a - b).map((i) => vivier[i]);
}

export function essentiel({
  interventions,
  dossiers,
  fonctions,
  questions,
  qualite,
  textes,
  appartenances,
}) {
  const vivier = vivierDesPoints({
    interventions,
    dossiers,
    fonctions,
    questions,
    qualite,
    textes,
    appartenances,
  });

  // Les rôles TENUS, dans l'ordre où la page les nomme. `gouvernement` est un
  // fait collecté ; `parlement` est tenu dès qu'un point du vivier en relève —
  // trois des treize (David Lisnard, Marine Tondelier, Nathalie Arthaud) n'ont
  // aucun point du tout, et la section ne s'affiche pas.
  const rolesTenus = [];
  if (vivier.some((p) => p.role === INSTITUTION_PARLEMENT)) rolesTenus.push(INSTITUTION_PARLEMENT);
  if ((appartenances || []).length > 0) rolesTenus.push(INSTITUTION_GOUVERNEMENT);

  const points = selectionnerPoints(vivier, rolesTenus);

  return {
    points,
    // Combien le vivier portait : sans ce nombre, cinq points sur sept se
    // liraient comme cinq points sur cinq, c'est-à-dire comme un relevé complet.
    vivier: vivier.length,
    rolesTenus,
    // Les rôles que le vivier documente RÉELLEMENT : c'est sur eux que la
    // garantie porte, et c'est eux que la phrase d'annonce peut promettre.
    // Promettre « au moins un par rôle » à Laurent Wauquiez, dont le corpus ne
    // publie rien de son passage au gouvernement, contredirait la ligne
    // suivante.
    rolesRepresentes: rolesTenus.filter((r) => vivier.some((p) => p.role === r)),
    // Un rôle tenu que le vivier ne documente pas. La page le DIT plutôt que de
    // laisser croire que la personne n'y a rien fait (§2 règle 5) : Laurent
    // Wauquiez, Ségolène Royal et Xavier Bertrand sont dans ce cas.
    rolesSansPoint: rolesTenus.filter((r) => !vivier.some((p) => p.role === r)),
    // Le cadre initiative/réaction ne tient pas au banc du gouvernement. Un
    // seul fait le déclenche, et il est collecté.
    aSiegeAuGouvernement: (appartenances || []).length > 0,
    // Le rôle ne s'affiche que s'il distingue : cinq fois « comme
    // parlementaire » sur un profil qui n'a jamais été ministre est du bruit,
    // et le champ existe pourtant sur les treize. Même conditionnel, même fait
    // collecté que la phrase d'introduction.
    montrerLesRoles: rolesTenus.length > 1,
  };
}

/* ── Livrable : « Les grands chiffres » ──────────────────────────────────────
 *
 * Le bloc de tête de la fiche, arbitré en maquette (#328). Ce n'est pas un
 * résumé — c'est un tableau de bord, et il est nommé pour ce qu'il est.
 *
 * DEUX RÈGLES le gouvernent, et tout le reste en découle.
 *
 * 1. **La frise commande les colonnes.** Le parcours n'est pas une section à
 *    part : c'est l'ossature. Une piste par rôle, une colonne par rôle, et la
 *    COULEUR fait le lien. Le constat qui l'a imposé : chez un ancien ministre,
 *    cinq catégories décrivant le métier de député se remplissent de ce que son
 *    ministère a produit, et son travail parlementaire disparaît.
 *
 * 2. **Les lignes sont appariées.** Des objets de même nature se font face et
 *    se traitent pareil, et CHAQUE COLONNE COMPTE CONTRE SON PROPRE TOTAL. Le
 *    total du profil n'apparaît nulle part : « 580 / 618 » d'un côté et
 *    « 2 759 / 3 345 » de l'autre sont deux mesures, pas deux parts d'une
 *    troisième.
 *
 * Ce qui est INTERDIT ici et le restera : additionner les deux colonnes, les
 * comparer, ou en tirer un ratio. Ce sont deux métiers, pas deux notes.
 */

export const COLONNE_PARLEMENT = INSTITUTION_PARLEMENT;
export const COLONNE_GOUVERNEMENT = INSTITUTION_GOUVERNEMENT;

/* Les trois cas de la maquette. Le gabarit est UNIQUE — ce sont les lignes et
 * les colonnes qui apparaissent ou non selon ce que la donnée porte. Deux
 * gabarits rendraient deux fiches incomparables, ce que la garantie par rôle
 * cherche précisément à éviter. */
export const CAS_DEUX_ROLES = 'deux_roles';
export const CAS_PARLEMENT_SEUL = 'parlement_seul';
export const CAS_GOUVERNEMENT_SEUL = 'gouvernement_seul';
export const CAS_RIEN_A_MONTRER = 'rien_a_montrer';


/* `LIBELLE_PISTE` survit à la fabrique de pistes : il nomme les COLONNES, que
 * la frise du parcours ne porte pas. Le reste — `ORDRE_PISTES`,
 * `ETIQUETTE_PISTE`, `pistesDuParcours` — était une seconde frise, et la
 * première la rendait inutile (#672 : jamais deux définitions du même objet).
 */
export const LIBELLE_PISTE = {
  [INSTITUTION_PARLEMENT]: "À l'Assemblée",
  [INSTITUTION_GOUVERNEMENT]: 'Au gouvernement',
  [INSTITUTION_MISSION]: 'Parlementaire en mission',
};

/* ── Une cellule ─────────────────────────────────────────────────────────────
 *
 * **Un nombre sans son objet ne dit rien.** « 24 / 67 » — et quoi ? Chaque
 * cellule nomme donc ce sur quoi elle porte, et SEULS LES NOMBRES sont en gros :
 * mettre l'objet à la même échelle que le chiffre était le défaut de la
 * première maquette.
 *
 * `absent` n'est pas un vide : c'est un FAIT sur le métier — « un ministre ne
 * dépose pas d'amendement » — et il se distingue d'une liste vide, qui est un
 * fait sur la collecte.
 */
function cellule({ nombre, objet, sur = null, objetSur = null, quantifieur = null, detail = null, barre = null }) {
  return { nombre, objet, sur, objetSur, quantifieur, detail, barre };
}

function celluleAbsente(motif) {
  return { absent: motif };
}

/* La barre des stades : une part par stade publié, dans l'ordre de la
 * procédure. Elle ne porte AUCUN taux — elle montre une forme, et chaque
 * segment publie son compte (§2 règle 7). */
function barreDesStades(textes) {
  const parStade = new Map();
  for (const t of textes) parStade.set(t.stadeCle, (parStade.get(t.stadeCle) || 0) + 1);
  const total = textes.length;
  if (!total) return null;
  const segments = STADES_PUBLIES.filter((cle) => parStade.has(cle)).map((cle) => ({
    cle,
    libelle: LIBELLE_STADE[cle],
    nombre: parStade.get(cle),
    part: (parStade.get(cle) / total) * 100,
  }));
  return segments.length ? { segments, total } : null;
}

/* ── Le bloc ─────────────────────────────────────────────────────────────────
 *
 * Les cinq lignes sont ordonnées par DEGRÉ D'ENGAGEMENT sur la nature des
 * actes — porter un texte, l'amender, siéger là où il s'examine, interroger,
 * parler — jamais sur les personnes.
 */
export const RANGS_GRANDS_CHIFFRES = [
  { cle: 'textes', titre: 'Textes portés' },
  { cle: 'amendements', titre: 'Amendements' },
  { cle: 'commissions', titre: 'Mandats en commission' },
  { cle: 'questions', titre: 'Questions au gouvernement' },
  { cle: 'interventions', titre: 'Interventions' },
];

export function grandsChiffres({
  roles = [],
  mandats = [],
  amendements = null,
  textes = null,
  interventions = [],
  appartenances = [],
}) {
  const aParlement = roles.some((r) => r.institution === INSTITUTION_PARLEMENT);
  const aGouvernement = roles.some((r) => r.institution === INSTITUTION_GOUVERNEMENT);

  let cas = CAS_RIEN_A_MONTRER;
  if (aParlement && aGouvernement) cas = CAS_DEUX_ROLES;
  else if (aParlement) cas = CAS_PARLEMENT_SEUL;
  else if (aGouvernement) cas = CAS_GOUVERNEMENT_SEUL;

  const colonnes = [];
  if (aParlement) colonnes.push(COLONNE_PARLEMENT);
  if (aGouvernement) colonnes.push(COLONNE_GOUVERNEMENT);

  if (cas === CAS_RIEN_A_MONTRER) {
    // Quatre des treize candidats déclarés n'ont ni mandat parlementaire ni
    // appartenance gouvernementale — un mandat européen, une mairie. Le bloc
    // n'a rien à montrer, et il le DIT plutôt que d'afficher cinq tirets :
    // l'arbitrage sur ces deux formes d'activité est ouvert, pas rendu.
    return { cas, colonnes, lignes: [] };
  }

  /* Le partage des interventions est DATÉ, jamais global. `depuisLeBancDuGouvernement`
   * rend une qualité pour tout le profil ; ici il faut savoir, pour chaque prise
   * de parole, de quel banc elle vient — c'est la date d'appartenance qui le dit,
   * et rien d'autre. Une intervention sans date n'est attribuée à aucun banc. */
  const auBanc = (date) =>
    Boolean(date) && appartenances.some((a) => a.debut <= date && date <= (a.fin || '9999-12-31'));

  const cotes = {
    [COLONNE_PARLEMENT]: interventions.filter((i) => !auBanc(i.date)),
    [COLONNE_GOUVERNEMENT]: interventions.filter((i) => auBanc(i.date)),
  };

  const lignes = [];

  // 1. Textes portés — le RÔLE publié range le texte (#689), jamais son intitulé :
  //    313 des 414 entrées publiées par les 13 candidats déclarés sont des projets
  //    de loi portés au nom du gouvernement, qui ne sont pas un acte personnel.
  //
  //    Les rôles sont nommés un par un plutôt que repliés sur l'institution :
  //    être RAPPORTEUR d'une proposition n'est pas en être l'auteur, et « 3
  //    propositions de loi » pour 2 propositions et 1 rapport serait faux.
  const publies = textes?.publies ?? [];
  const ROLES_PROPOSITION = ['auteur_proposition_de_loi', 'auteur_proposition_de_resolution'];
  const propositions = publies.filter((t) => ROLES_PROPOSITION.includes(t.roleCle));
  const projets = publies.filter((t) => t.roleCle === 'initiateur_projet_de_loi');
  const autresRoles = publies.filter(
    (t) => !ROLES_PROPOSITION.includes(t.roleCle) && t.roleCle !== 'initiateur_projet_de_loi',
  );
  // Ce que le seuil de publication écarte SE DIT. AGENTS.md §6 ne publie par
  // défaut qu'un texte parvenu au moins en commission ; taire les autres ferait
  // lire « 2 » comme « il n'en a déposé que 2 » (§2 règle 5).
  const ecartes = textes?.ecartes?.total ?? 0;
  const detailTextes = [
    autresRoles.length
      ? `${formatNumber(autresRoles.length)} ${pluriel(autresRoles.length, 'texte porté à un autre titre', 'textes portés à un autre titre')} (${[...new Set(autresRoles.map((t) => t.role))].join(', ')})`
      : null,
    ecartes
      ? `${formatNumber(ecartes)} ${pluriel(ecartes, 'texte déposé n’est pas compté', 'textes déposés ne sont pas comptés')} : la fiche ne publie que ce qui est parvenu au moins en commission`
      : null,
  ]
    .filter(Boolean)
    .join(' · ');
  const celluleTextes = (lot, objet, detail) =>
    lot.length
      ? cellule({ nombre: lot.length, objet, barre: barreDesStades(lot), detail: detail || null })
      : null;
  lignes.push({
    cle: 'textes',
    titre: 'Textes portés',
    cellules: {
      [COLONNE_PARLEMENT]: celluleTextes(propositions, 'propositions de loi', detailTextes),
      [COLONNE_GOUVERNEMENT]: celluleTextes(projets, 'projets de loi', null),
    },
  });

  // 2. Amendements. Le COUPLE dépôts / dossiers, jamais le compte seul : deux
  //    nombres qui varient en sens inverse appellent une lecture, un nombre seul
  //    appelle un classement (§2 règle 1).
  const d = amendements?.dossiers ?? null;
  const totalAuteur = amendements?.totalAuteur ?? 0;
  let celluleAmendements = null;
  if (totalAuteur > 0) {
    // La CONCENTRATION ne s'affirme que là où elle se prouve : ce dossier doit
    // porter plus que tous les autres réunis. Aucune constante arbitraire —
    // c'est un fait, pas un seuil. Un percentile a été essayé et écarté : il
    // sélectionne toujours 10 % des dossiers, donc il ne peut JAMAIS se taire.
    const tete = (d?.nommes ?? []).slice().sort((a, b) => (b.depots ?? 0) - (a.depots ?? 0))[0] ?? null;
    const concentre = tete && tete.depots * 2 > totalAuteur ? tete : null;
    celluleAmendements = cellule({
      nombre: totalAuteur,
      objet: 'amendements sur',
      sur: d?.distincts ?? null,
      objetSur: 'dossiers législatifs',
      quantifieur: concentre
        ? { nombre: concentre.depots, texte: `d’entre eux sur « ${concentre.titre} »` }
        : null,
      // Les dossiers se listent PAR DATE, jamais par volume : déposer beaucoup
      // sur un texte peut être un travail de fond comme une stratégie de
      // blocage, et le nombre ne les distingue pas.
      detail: null,
      barre: null,
    });
  }
  lignes.push({
    cle: 'amendements',
    titre: 'Amendements',
    cellules: {
      [COLONNE_PARLEMENT]: celluleAmendements,
      [COLONNE_GOUVERNEMENT]: celluleAbsente('un ministre ne dépose pas d’amendement'),
    },
  });

  // 3. Mandats en commission. Le NOMBRE DE MANDATS et le nombre de commissions
  //    DISTINCTES ne disent pas la même chose : 67 mandats sur 14 commissions,
  //    c'est une réélection, pas une dispersion.
  const commissions = mandats.filter((m) => m.categorie === 'commission' && m.label);
  const parCommission = new Map();
  for (const m of commissions) parCommission.set(m.label, (parCommission.get(m.label) || 0) + 1);
  const classees = [...parCommission.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], 'fr'));
  lignes.push({
    cle: 'commissions',
    titre: 'Mandats en commission',
    cellules: {
      [COLONNE_PARLEMENT]: classees.length
        ? cellule({
            nombre: classees[0][1],
            objet: 'mandats sur',
            sur: commissions.length,
            objetSur: `à la ${classees[0][0]}`,
            quantifieur: { nombre: parCommission.size, texte: pluriel(parCommission.size, 'commission distincte', 'commissions distinctes') },
          })
        : null,
      [COLONNE_GOUVERNEMENT]: celluleAbsente('un ministre ne siège pas en commission'),
    },
  });

  // 4. Questions au gouvernement. LE MÊME OBJET DE CHAQUE CÔTÉ, et deux actes
  //    opposés : on la pose depuis les bancs, on y répond depuis le banc. Les
  //    deux ne s'additionnent pas et ne se comparent pas.
  const qg = (cote) => cotes[cote].filter((i) => i.type_detail === 'question_gouvernement');
  const celluleQuestions = (cote, objet) => {
    const lot = qg(cote);
    if (!lot.length) return null;
    const sujets = new Set(lot.map((i) => i.sujet).filter(Boolean));
    return cellule({
      nombre: lot.length,
      objet,
      quantifieur: sujets.size
        ? { nombre: sujets.size, texte: pluriel(sujets.size, 'sujet distinct', 'sujets distincts') }
        : null,
    });
  };
  lignes.push({
    cle: 'questions',
    titre: 'Questions au gouvernement',
    cellules: {
      [COLONNE_PARLEMENT]: celluleQuestions(COLONNE_PARLEMENT, 'posées'),
      [COLONNE_GOUVERNEMENT]: celluleQuestions(COLONNE_GOUVERNEMENT, 'prises de parole depuis le banc'),
    },
  });

  // 5. Interventions. « SITUÉES » porte la limite sans phrase : le chiffre se
  //    rapporte aux interventions dont le compte rendu donne un point de l'ordre
  //    du jour, pas à toutes. Chaque colonne compte contre SON propre total.
  const celluleInterventions = (cote) => {
    const lot = cotes[cote];
    if (!lot.length) return null;
    const situees = lot.filter((i) => i.sujet);
    if (!situees.length) return null;
    const parSujet = new Map();
    for (const i of situees) parSujet.set(i.sujet, (parSujet.get(i.sujet) || 0) + 1);
    const classes = [...parSujet.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], 'fr'));
    return cellule({
      nombre: classes[0][1],
      objet: 'sur',
      sur: situees.length,
      objetSur: `situées, dont « ${classes[0][0]} »`,
      quantifieur: {
        nombre: parSujet.size,
        texte: `${pluriel(parSujet.size, 'sujet distinct', 'sujets distincts')} sur ${formatNumber(lot.length)} interventions`,
      },
    });
  };
  lignes.push({
    cle: 'interventions',
    titre: 'Interventions',
    cellules: {
      [COLONNE_PARLEMENT]: celluleInterventions(COLONNE_PARLEMENT),
      [COLONNE_GOUVERNEMENT]: celluleInterventions(COLONNE_GOUVERNEMENT),
    },
  });

  // Une ligne dont AUCUNE colonne ne porte de chiffre ne s'affiche pas : cinq
  // rangs vides ne décrivent pas une personne, ils décrivent le gabarit.
  const retenues = lignes.filter((l) => colonnes.some((c) => l.cellules[c] && !l.cellules[c].absent));

  return { cas, colonnes, lignes: retenues };
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
