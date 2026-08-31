/*
 * Fondations de lecture — lot 1 de la refonte #324 (issue #326).
 *
 * Les six règles que toute vue applique AVANT d'exister vivent ici, et nulle
 * part ailleurs : six règles réécrites trois fois divergent trois fois. Les
 * lots 2, 3 et 4 les appliquent, ils ne les redéfinissent pas.
 *
 * Ce module ne dessine rien. Il décide ce qu'une vue a le droit d'afficher ;
 * `components/Lecture.jsx` en donne la forme.
 *
 * Chiffres cités : mesurés au commit de données `245511b4` le 31/08/2026, sur
 * les 481 profils publiés — 13 `candidat_declare` et 468 `roster_groupe`. Un
 * chiffre sur 481 mélange les deux et ne veut rien dire.
 */

/* ── Règle : les couleurs de vote ne forment pas une échelle ─────────────────
 *
 * Pour, Contre et Abstention sont des positions EXPRIMÉES : elles portent une
 * couleur, celle du DESIGN_SYSTEM. `non_votant` n'en est pas une — il se
 * distingue par la FORME (contour tireté, aucune teinte). Mettre les quatre sur
 * un dégradé chaud-froid fabriquerait un jugement, ce qu'interdit §2 règle 1.
 *
 * QUATRE valeurs, pas cinq. `absent` n'apparaît dans AUCUNE des 1 312 951
 * positions publiées : lui donner une catégorie publierait une absence comme un
 * fait de vote, c'est-à-dire le taux de présence individuel qu'interdit §2
 * règle 3. Toute valeur inconnue — `absent` comprise, si la source en produisait
 * une un jour — tombe donc sur la forme sans teinte, jamais sur une couleur.
 *
 * Ce que ce module ferme : `VOTE_STYLE` vivait dupliqué dans CandidateProfile
 * et GroupProfile, sans `non_votant`. Les 21 229 positions `non_votant` du
 * corpus (1 sur les 13 candidats déclarés) s'affichaient sans couleur NI
 * libellé — une pastille invisible et un texte vide.
 */
export const VOTE_STYLE = {
  pour: { label: 'Pour', color: '#007A45', outlined: false },
  contre: { label: 'Contre', color: '#E53420', outlined: false },
  abstention: { label: 'Abstention', color: '#8B8794', outlined: false },
  non_votant: { label: 'Non-votant', color: null, outlined: true },
};

/*
 * Une position que la table ne connaît pas est rendue telle que la source
 * l'écrit, sans teinte : on n'invente ni couleur ni libellé (§2 règle 2).
 */
export function styleForPosition(position) {
  return (
    VOTE_STYLE[position] ?? { label: position ?? null, color: null, outlined: true }
  );
}

/*
 * Sorts d'amendement et d'issue — mêmes valeurs que le DESIGN_SYSTEM, elles
 * aussi dupliquées jusqu'ici dans les deux composants.
 */
export const OUTCOME_COLOR = {
  adopté: '#007A45',
  rejeté: '#E53420',
  retiré: '#F2A93B',
  tombé: '#8B8794',
  irrecevable: '#B8B4AE',
  non_soutenu: '#DCD9D3',
};

/* ── Règle : un ratio porte ses deux nombres ─────────────────────────────────
 *
 * Un pourcentage seul n'est pas vérifiable (§2 règle 7). Le dénominateur est
 * toujours nommé, parce que c'est lui qui décide si la mesure parle d'un texte
 * ou accuse une personne : « sur les scrutins où elle s'est prononcée » est
 * autorisé, « sur les scrutins où elle aurait pu se prononcer » est un taux
 * d'assiduité individuel, donc jamais publié (§2 règle 3).
 *
 * Un dénominateur absent ou nul rend `N/D` — jamais 0 %, jamais rien.
 */
export function ratio(numerator, denominator, denominatorLabel) {
  const usable =
    Number.isFinite(numerator) && Number.isFinite(denominator) && denominator > 0;

  if (!usable) {
    return { available: false, numerator, denominator, text: 'N/D' };
  }

  return {
    available: true,
    numerator,
    denominator,
    text: `${formatNumber(numerator)} sur ${formatNumber(denominator)} ${denominatorLabel}`,
  };
}

/* ── Règle : une troncature déclare sa règle ─────────────────────────────────
 *
 * Trois listes sont coupées en silence aujourd'hui : 12 votes sur 1 016 à
 * 4 976 selon le profil, 12 scrutins de cohésion sur 3 832 à 4 099, 20
 * mots-clés. Le lecteur croit voir une sélection ; il voit un `slice`.
 *
 * La récence est une règle acceptable À CONDITION d'être annoncée comme telle,
 * jamais présentée comme un choix des plus importants : les 12 votes affichés
 * sur un profil tombent sur deux jours.
 */
export function truncation(shown, total, rule) {
  if (!Number.isFinite(total) || shown >= total) {
    return { truncated: false, shown, total, text: null };
  }

  return {
    truncated: true,
    shown,
    total,
    text: `${formatNumber(shown)} sur ${formatNumber(total)} — ${rule}`,
  };
}

/* ── Règle : une liste vide dit pourquoi ─────────────────────────────────────
 *
 * Le bloc `couverture` porte déjà la cause sur 481 / 481 profils, et aucun
 * composant n'en lit une seule. Les quatre causes n'affirment pas la même
 * chose : les confondre publierait un zéro là où rien n'a été collecté, ce
 * qu'interdit §2 règle 5.
 *
 * `titre` est ce que le lecteur voit en premier ; `parle_de` dit de QUI ou de
 * QUOI la phrase parle, et c'est la distinction qui compte — un `fait_etabli`
 * parle de la personne, un `hors_couverture` parle de la source.
 */
export const EMPTY_LIST_CAUSES = {
  couvert: {
    titre: 'Aucun résultat',
    parle_de: 'la mesure',
    defaut:
      "La collecte a abouti sur toute la période et n'a rien trouvé. Ce vide est une mesure.",
  },
  fait_etabli: {
    titre: 'Aucun résultat',
    parle_de: 'la personne',
    defaut:
      "Un fait établi sur cette personne explique ce vide : elle n'était pas en situation d'en produire.",
  },
  hors_couverture: {
    titre: 'Rien à afficher pour cette période',
    parle_de: 'la source',
    defaut:
      "La source ne publie pas cette période. Ce qui a pu exister avant sa borne n'est pas décrit.",
  },
  non_collecte: {
    titre: 'Non collecté',
    parle_de: 'la collecte',
    defaut:
      "Cette liste n'a pas été interrogée. Nous ne pouvons donc rien affirmer — ni un résultat, ni son absence.",
  },
};

/*
 * `cause` vient de `meta.couverture[<liste>].etat` ; `motif` est la phrase que
 * le pipeline a écrite pour ce profil, et elle prime sur la phrase par défaut.
 * Une cause inconnue ne devient JAMAIS « aucun résultat » : elle se déclare
 * comme non renseignée (§2 règle 5).
 */
export function emptyListMessage(cause, motif) {
  const known = EMPTY_LIST_CAUSES[cause];

  if (!known) {
    return {
      cause: cause ?? null,
      known: false,
      titre: 'Cause non renseignée',
      message:
        "Cette liste est vide et la raison n'est pas publiée. Nous ne pouvons pas dire s'il s'agit d'un zéro mesuré ou d'une collecte absente.",
    };
  }

  return {
    cause,
    known: true,
    titre: known.titre,
    message: motif || known.defaut,
  };
}

/* ── Livrable : le badge de source ───────────────────────────────────────────
 *
 * La couverture est réelle et très inégale : scrutins 17 748 / 17 748,
 * interventions des 13 candidats déclarés 16 242 / 16 242, textes de
 * gouvernement 725 / 725, textes portés 472 / 472, mandats 1 915 / 41 723,
 * amendements 0 / 484 132.
 *
 * D'où la formulation, qui EST le livrable : « Lien de source non publié »
 * parle de NOUS. « Non vérifié » ferait porter le doute sur les 484 132
 * amendements eux-mêmes, qui viennent tous de l'open data de l'Assemblée
 * nationale — ce serait un jugement sur la donnée, pas un constat sur la page.
 */
export const SOURCE_BADGE_VERIFIED = 'Source vérifiée';
export const SOURCE_BADGE_UNPUBLISHED = 'Lien de source non publié';

export function sourceBadge(sourceUrl) {
  const verified = typeof sourceUrl === 'string' && sourceUrl.length > 0;
  return {
    verified,
    label: verified ? SOURCE_BADGE_VERIFIED : SOURCE_BADGE_UNPUBLISHED,
    href: verified ? sourceUrl : null,
  };
}

/* ── Livrable : les trois niveaux de lecture ─────────────────────────────────
 *
 * Les mêmes trois niveaux sur les trois types de profil. Le troisième n'est pas
 * un repli pour ce qui n'a pas trouvé sa place : c'est la contrepartie de la
 * traçabilité (§2 règle 2).
 */
export const READING_LEVELS = [
  { id: 'coup-doeil', label: "Coup d'œil", duree: '~30 s' },
  { id: 'lecture', label: 'Lecture', duree: '~3 min' },
  { id: 'verification', label: 'Vérification', duree: 'sans limite' },
];

/* ── Règle : ce qui est interdit est écrit ───────────────────────────────────
 *
 * Une page qui se contente de ne pas répondre laisse croire qu'elle n'y a pas
 * pensé. Ces phrases sont du contenu publié, pas des commentaires de code.
 */
export const STATED_REFUSALS = [
  {
    id: 'assiduite',
    sujet: 'Assiduité',
    phrase: 'Nous ne publions aucun taux de présence individuel.',
    pourquoi:
      "Un dénominateur « scrutins où la personne aurait pu voter » transformerait une absence en information négative. Nous n'avons aucun moyen de distinguer une absence d'un déport, d'une délégation ou d'une mission.",
  },
  {
    id: 'classement',
    sujet: 'Classement',
    phrase: 'Aucun score, aucun classement, aucune comparaison entre personnes.',
    pourquoi:
      'Les décomptes sont donnés avec leurs dénominateurs pour être vérifiés, jamais pour être ordonnés.',
  },
  {
    id: 'engagement-responsabilite',
    sujet: '49.3',
    phrase: "Un texte adopté sans vote n'est pas une position.",
    pourquoi:
      "L'engagement de responsabilité est un fait de procédure. Il est affiché comme tel, jamais agrégé à un décompte de votes ni coloré comme une position.",
  },
];

/*
 * Espace fine insécable entre les milliers, comme partout ailleurs dans le
 * site. Les nombres se comparent en tabulaire côté CSS.
 */
export function formatNumber(n) {
  return Number.isFinite(n) ? n.toLocaleString('fr-FR').replace(/ /g, ' ') : '—';
}
