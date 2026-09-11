// Transforme un profil pivot individuel (schema_pivot.py) ou un profil de
// gouvernement en objets directement consommables par CandidateProfile.jsx /
// GovernmentProfile.jsx. La fiche de groupe n'y passe plus depuis #329 : elle
// lit une projection de lignée écrite au build (`scripts/vue-lignee.mjs`).
//
// La logique de classification (ancienneté, responsabilités dédupliquées,
// position dans l'hémicycle, thème dominant) reprend celle déjà validée dans
// web/v3/js (render.js, utils.js) pour rester cohérente avec les règles
// éditoriales (AGENTS.md §2) : jamais de score, une donnée manquante reste
// "N/D", jamais 0 par défaut.
//
// Les règles de lecture ne sont PAS réécrites ici : les six fondations du lot 1
// vivent dans `utils/lecture.js` (#326). Cet adaptateur met en forme, il
// n'arbitre pas.

import {
  INSTITUTION_PARLEMENT,
  agregerAmendements,
  appartenancesGouvernementales,
  bornesDuParcours,
  causeListeVide,
  couvertureDesListes,
  directionQuestionsGouvernement,
  essentiel,
  grandsChiffres,
  fonctionsExercees,
  limitesDeclarees,
  regimeQualiteOrateur,
  rolesDuParcours,
  siegesElectifs,
  textesPortes,
  voixDuProfil,
  votesDuProfil,
} from '../utils/profilCandidat';
import { LIBELLE_SORT_TEXTE, legislatureDeAmendementId } from '../utils/lecture';
import { ecartsAvecLeGroupe } from '../utils/ecartsGroupe';
import {
  couvertureDesReperes,
  periodesDeVote,
  porteeCommune,
  qualifierVotes,
} from '../utils/votesParPeriode';
import {
  couvertureDesParoles,
  periodesDeParole,
  plafondParPeriode,
  plafondToutesPeriodes,
  qualifierInterventions,
} from '../utils/parolesParPeriode';

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

/* `legislatureDeAmendementId` vit dans `utils/lecture.js` depuis #329 : la
 * projection de lignée la lit au build, et Node n'importe pas ce module-ci.
 * Réexportée ici pour ses lecteurs existants. */
export { legislatureDeAmendementId };

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
 * titre }`. Les dépôts se comptent sur le DOSSIER, pas sur le `texte_vise` :
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

/** Construit l'objet consommé par CandidateProfile.jsx à partir d'un profil pivot v1.
 *
 * Lot 2 (#328) : les règles de lecture propres au profil candidat vivent dans
 * `utils/profilCandidat.js`, les six fondations communes dans `utils/lecture.js`.
 * Cet adaptateur les APPELLE, il n'en écrit pas de seconde version.
 *
 * SIX emplacements, identiques pour les treize candidats déclarés, dans le même
 * ordre. Ce qui varie est le contenu, jamais la forme — et un emplacement vide
 * dit pourquoi il l'est.
 *
 * Sept jusqu'au 08/09/2026 : « les gouvernements dont il a été membre » a été
 * retiré, et l'ordre a changé — ce qu'il a VOTÉ et ses ÉCARTS passent avant ce
 * qu'il a DIT. Voir `docs/decisions/six-emplacements-fiche-candidat-328.md`.
 */
export function buildCandidateView(
  pivot,
  manifestEntry,
  scrutinsIndex = null,
  amendementsIndex = null,
  fichesGroupe = null,
  commissionsDossiers = null,
  scrutinsDossiers = null,
  tousLesGouvernements = null,
  ficheDuGroupe = null,
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

  // La commission saisie au fond d'un dossier, lue dans
  // `pivot_data/commissions_dossiers.json` (#328) — l'acte
  // `AN1-COM-FOND-SAISIE` de l'archive AN, résolu en organe. Table absente : la
  // répartition n'est simplement pas publiée, jamais remplacée par une
  // déduction depuis l'intitulé du dossier (§2 règle 2).
  const commissionDuDossier = (dossierId) =>
    (commissionsDossiers && dossierId && commissionsDossiers[dossierId]) || null;

  const amendements = agregerAmendements(
    joinAmendements(pivot.amendements || [], amendementsIndex),
    positionALaDate,
    commissionDuDossier,
  );
  const textes = textesPortes(pivot.textes_portes, commissionDuDossier);
  const fonctions = fonctionsExercees(mandats);
  const qualite = regimeQualiteOrateur(interventions);
  const questions = directionQuestionsGouvernement(interventions, appartenances);
  // `scrutinsIndex` — le CORPUS entier, pas les seuls votes du profil : la
  // dernière lecture d'un texte se lit sur toutes ses lectures, y compris
  // celles où la personne n'a pas de position enregistrée (#711).
  const lectureVotes = votesDuProfil(
    votes,
    appartenances,
    roles.filter((r) => r.institution === INSTITUTION_PARLEMENT),
    scrutinsIndex,
  );
  /* La matière d'un scrutin : le même chemin que « ce qu'il a voté » —
     scrutin → dossier (#758), dossier → commission saisie au fond (#328). Elle
     est passée aux deux sections depuis ICI, pour qu'aucune n'en écrive une
     seconde version. */
  const matiereDuScrutin = (scrutinId) => {
    const dossierId = scrutinsDossiers?.scrutins?.[scrutinId] ?? null;
    return commissionDuDossier(dossierId)?.sigle ?? null;
  };
  const ecarts = ecartsAvecLeGroupe(votes, fichesGroupe, matiereDuScrutin);

  /* « Ce qu'il a voté » : les positions de dernière lecture, rangées par
   * période politique (#328). Elles partent de `lectureVotes.retenus` — la
   * MÊME sélection que le décompte au-dessus, pas une seconde : le repli sur la
   * dernière lecture n'a qu'une implémentation, dans `utils/lecture.js` (#711).
   *
   * `tousLesGouvernements` est la chronologie entière, pas les seuls
   * gouvernements dont la personne fut membre : ce qui découpe la carrière est
   * le gouvernement EN PLACE, pas son appartenance. */
  const votesQualifies = qualifierVotes(lectureVotes.retenus, {
    roles: roles.filter((r) => r.institution === INSTITUTION_PARLEMENT),
    gouvernements: tousLesGouvernements || [],
    scrutinsDossiers,
    commissionDuDossier,
  });
  const periodesDeVotes = periodesDeVote(votesQualifies);

  /* « Ce qu'il a dit » : les interventions rangées par période politique
   * (#328). Le découpage vient des MÊMES repères que les votes — le banc lu
   * dans `mandats[].position_dans_hemicycle`, le gouvernement EN PLACE lu dans
   * la chronologie complète —, et par les mêmes fonctions : deux sections qui
   * découpent le temps pareil doivent le faire au même endroit. */
  const parolesQualifiees = qualifierInterventions(interventions, {
    roles: roles.filter((r) => r.institution === INSTITUTION_PARLEMENT),
    gouvernements: tousLesGouvernements || [],
  });
  const periodesDeParoles = periodesDeParole(parolesQualifiees);

  return {
    id: manifestEntry.slug,
    nom: pivot.nom,
    parti: pivot.parti || manifestEntry.parti || '',
    groupe: pivot.groupe || '',
    /* LE LIEN VERS LA FICHE DE GROUPE, ET SEULEMENT QUAND IL MÈNE AU BON.
     *
     * `pivot.groupe` est un LIBELLÉ, et il ne nomme pas toujours un groupe
     * parlementaire : sur les 30 candidats déclarés, il vaut « Parti
     * socialiste », « Lutte Ouvrière (LO) », « Sans étiquette », ou un groupe du
     * Parlement européen. Dix-huit d'entre eux ne correspondent à aucune fiche.
     *
     * ET UN LIBELLÉ PEUT DEVANCER LA FICHE, ce qui est pire qu'aucun lien :
     * tant que la fiche ECOS XVIIe n'était pas publiée, Delphine Batho et
     * François Ruffin portaient « Écologiste et Social » quand leur fiche la
     * plus récente était un AUTRE groupe.
     *
     * `ficheDuGroupe` est donc calculé en amont, sur `groupIds` — l'appariement
     * structurel `membre_id` → slug que `sync-data` établit fiche par fiche,
     * jamais une ressemblance de nom (#639) — et il n'est posé que si le nom de
     * cette fiche est bien celui qu'on affiche. La comparaison de libellés n'est
     * pas ici une jointure : c'est le garde-fou qui empêche d'envoyer le lecteur
     * ailleurs que là où le texte le dit. */
    groupeFiche: ficheDuGroupe,
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

    // « Les grands chiffres » (#328) : la frise et les cinq lignes appariées.
    // Il reçoit les mêmes objets déjà calculés plus haut — aucune mesure n'est
    // refaite ici, sinon la fiche porterait deux comptes du même fait.
    grandsChiffres: grandsChiffres({
      roles,
      mandats,
      amendements,
      textes,
      interventions,
      appartenances,
    }),

    essentiel: essentiel({
      interventions,
      dossiers: amendements.dossiers,
      fonctions,
      questions,
      qualite,
      textes,
      appartenances,
    }),

    parcours: { roles, nbLignes, bornes },
    fonctions,
    amendements,
    textes,
    /* `natures` a disparu d'ici avec #328 : la nature de l'intervention est
     * devenue une FACETTE de la section, comptée sous la période et le sujet
     * retenus, et non plus une liste de totaux de carrière. `qualite` et
     * `questions` restent : « En bref » les consomme.
     *
     * `periodes` porte les interventions elles-mêmes — c'est la section qui
     * publie le verbatim, il ne se recalcule nulle part ailleurs. */
    interventions: {
      total: interventions.length,
      qualite,
      questions,
      periodes: periodesDeParoles,
      plafondPeriode: plafondParPeriode(periodesDeParoles),
      plafondEnsemble: plafondToutesPeriodes(periodesDeParoles),
      couverture: couvertureDesParoles(parolesQualifiees),
    },
    votes: {
      ...lectureVotes,
      // La liste qualifiée ne remonte PAS jusqu'au composant sous cette clé :
      // ce sont les périodes qui sont l'unité d'affichage. Le total qualifié
      // reste publié pour que la couverture ci-dessous ait un dénominateur.
      qualifies: votesQualifies.length,
      periodes: periodesDeVotes,
      portee: porteeCommune(periodesDeVotes),
      // Ce que la section sait de ses propres trous — publié, jamais deviné à
      // la soustraction par le lecteur (§2 règles 5 et 7).
      reperes: couvertureDesReperes(votesQualifies),
      // L'index scrutin → dossier n'a pas pu être lu : la matière et le statut
      // manquent pour TOUS les votes, ce qui n'est pas la même chose que « ces
      // textes n'ont pas de commission saisie au fond ».
      rattachementDisponible: scrutinsDossiers !== null,
    },
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
    limites: limitesDeclarees({ profil: pivot, roles, sieges }),
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
      statutLabel: LIBELLE_SORT_TEXTE[t.statut] || t.statut,
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
