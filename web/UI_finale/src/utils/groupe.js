/*
 * Les règles de lecture d'une FICHE DE GROUPE — lot 3 de la refonte #324
 * (issue #329).
 *
 * Ce module ne dessine rien et ne redéfinit rien : les six fondations du lot 1
 * vivent dans `utils/lecture.js` (`ratio`, `truncation`, `emptyListMessage`,
 * `sourceBadge`, `styleForPosition`, `formatNumber`) et sont consommées ici.
 * Ce qui est propre au groupe — et seulement cela — est écrit ici.
 *
 * Deux populations, jamais mélangées (AGENTS.md §3) : une fiche de groupe
 * agrège les 468 profils `roster_groupe`, qui n'ont pas de page à eux. Aucun
 * chiffre de ce module ne parle des 13 candidats déclarés.
 *
 * Chiffres cités : mesurés au commit `c6edee05` le 31/08/2026, sur les 7 fiches
 * publiées — 5 pour l'Assemblée nationale (XVIe législature) et 2 pour le Sénat,
 * gelées et jamais régénérées depuis #528/#516.
 */

import { formatNumber, ratio } from './lecture';

/* ── Règle : aucun compteur ne veut dire « aujourd'hui » ─────────────────────
 *
 * Une fiche de groupe décrit UNE législature, et aucune des 7 publiées ne
 * décrit celle en cours (#653). Trois compteurs prétendaient au présent et
 * mesuraient en réalité la carrière ULTÉRIEURE des membres : `effectif.actuel`
 * égalait, exactement, le nombre de membres portant un mandat électif ouvert —
 * 38/38 sur `AN:LR`, 85/85 sur `AN:REN`, 60/60 sur `AN:LFI`, c'est-à-dire les
 * réélu⋅es de 2024, pas les membres du groupe en juin 2024.
 *
 * Les noms longs (`a_la_date_de_reference`) sont longs exprès. Ce module les
 * lit, et lit AUSSI les anciens noms, parce que les 2 fiches Sénat gelées ne
 * seront pas régénérées : exiger la clé ferait échouer le portail de qualité
 * sur des fichiers déjà publiés.
 */
export const ORIGINES_DATE_REFERENCE = {
  cloture_legislature: 'clôture de la législature',
  generation: 'date de génération de la fiche',
};

/*
 * `{ date, origine, origineLabel, datee }`. `datee: false` dit que la fiche ne
 * rapporte ses comptes à AUCUNE date — ce n'est pas « aujourd'hui », et c'est
 * exactement ce qu'il faut écrire à l'écran plutôt qu'inventer une date.
 */
export function dateDeReference(groupe) {
  const bloc = groupe?.date_reference;
  const date = bloc?.date ?? null;
  const origine = bloc?.origine ?? null;

  return {
    date,
    origine,
    origineLabel: origine ? (ORIGINES_DATE_REFERENCE[origine] ?? origine) : null,
    datee: Boolean(date),
  };
}

/*
 * L'effectif, sous les deux noms. `a_la_date_de_reference` (#653) d'abord ;
 * `actuel` ensuite, et alors le compte n'est rapporté à aucune date.
 *
 * Le dénominateur publié est le nombre d'entrées de `membres[]` — la couverture
 * disponible de la fiche —, jamais `meta.couverture_roster.roster_total`, qui
 * compte des membres dont aucun profil n'est publié. Les deux diffèrent : 75
 * sur 76 pour `AN:LFI`, 169 sur 193 pour `AN:REN`.
 */
export function effectifDuGroupe(groupe) {
  const bloc = groupe?.effectif || {};
  const aLaDate = bloc.a_la_date_de_reference;
  const ancien = bloc.actuel;
  const valeur = Number.isFinite(aLaDate) ? aLaDate : (Number.isFinite(ancien) ? ancien : null);

  return {
    valeur,
    denominateur: (groupe?.membres || []).length,
    // `true` quand la valeur vient du champ daté, donc quand elle se rapporte
    // à `date_reference`. `false` sur les 2 fiches Sénat.
    rapporteALaDate: Number.isFinite(aLaDate),
  };
}

/*
 * Un mandat agrégé porte DEUX quantités, jamais une (#656) : « qui y siège » et
 * « qui y est passé ». 43 % des adhésions de commission publiées durent une
 * journée ou moins — un⋅e député⋅e n'appartient qu'à une commission permanente
 * à la fois, si bien que tout passage temporaire est écrit dans le référentiel
 * comme un mandat à part entière. Lire le cumul comme un effectif faisait dire
 * à la fiche que 67 des 76 membres LFI siégeaient aux finances quand ils sont 5.
 *
 * Les deux anciens noms (`nb_membres_actifs`, `nb_membres`) sont lus aussi :
 * sans ce repli les 17 cartes de mandats des 2 fiches Sénat rendaient
 * `undefined membre y a siégé au moins une fois`, et « Aucun membre n'y
 * siégeait » sur une donnée simplement absente (AGENTS.md §2 règle 5).
 */
export function siegeEtPasse(mandat, effectifDeSecours) {
  const siege = Number.isFinite(mandat?.nb_membres_a_la_date_de_reference)
    ? mandat.nb_membres_a_la_date_de_reference
    : (Number.isFinite(mandat?.nb_membres_actifs) ? mandat.nb_membres_actifs : null);
  const passe = Number.isFinite(mandat?.nb_membres_cumul_historique)
    ? mandat.nb_membres_cumul_historique
    : (Number.isFinite(mandat?.nb_membres) ? mandat.nb_membres : null);

  return {
    siege,
    passe,
    effectif: Number.isFinite(mandat?.effectif_reference)
      ? mandat.effectif_reference
      : effectifDeSecours,
    // `true` seulement si le compte vient du champ daté : sinon il ne se
    // rapporte à aucune date, et la section le dit une fois pour toutes.
    siegeRapporteALaDate: Number.isFinite(mandat?.nb_membres_a_la_date_de_reference),
  };
}

/* ── Règle : la cohésion se publie en six nombres, jamais en barre ───────────
 *
 * Une barre de progression suggère une échelle du pire au meilleur. Ce sont des
 * CATÉGORIES : la coloriser reviendrait à noter le groupe (§2 règle 1). La
 * fiche affichait `taux_coherence` en barre pleine, teintée de la couleur de la
 * position majoritaire.
 *
 * Les six décomptes forment une partition EXACTE de `membres_eligibles` :
 * vérifié sur les 19 832 entrées des 5 fiches AN, `pour + contre + abstention +
 * non_votant + absents + excuses == membres_eligibles` sur 19 832 / 19 832.
 * C'est ce qui rend les six lisibles ensemble sans dénominateur implicite.
 *
 * Deux d'entre eux ne sont pas des positions et ne portent donc aucune teinte :
 *
 *  - `absents` est nommé « Sans trace de vote » et jamais « Absents ». Le
 *    pipeline compte là les membres éligibles pour qui AUCUN vote n'a été
 *    trouvé sur ce scrutin — une absence de donnée, pas une absence constatée.
 *    L'écrire « absents » fabriquerait le taux de présence qu'interdit §2
 *    règle 3, agrégé mais fabriqué quand même.
 *  - `excuses` vaut 0 sur les 19 832 entrées publiées, parce qu'aucune position
 *    collectée ne vaut `excuse` — exactement le cas d'`absent` dans les
 *    1 312 951 positions individuelles (#326). Un 0 structurel affiché comme un
 *    0 mesuré affirmerait « personne n'était excusé » : `renseigne: false` dit
 *    au rendu de ne pas publier ce zéro (§2 règle 5).
 */
export const LIBELLES_DECOMPTE_COHESION = {
  pour: 'Pour',
  contre: 'Contre',
  abstention: 'Abstention',
  non_votant: 'Non-votant',
  absents: 'Sans trace de vote',
  excuses: 'Excusés',
};

export const ORDRE_DECOMPTE_COHESION = [
  'pour', 'contre', 'abstention', 'non_votant', 'absents', 'excuses',
];

/*
 * `excusesRenseignees` se mesure sur la fiche entière, jamais sur une entrée :
 * une entrée à 0 ne dit pas si la source ne renseigne pas la valeur ou si
 * personne n'était excusé ce jour-là. À l'échelle de la fiche, un 0 partout
 * sur 3 973 scrutins le dit.
 */
export function excusesRenseignees(cohesionVotes) {
  return (cohesionVotes || []).some((v) => Number.isFinite(v?.excuses) && v.excuses > 0);
}

/*
 * Les six décomptes d'une entrée, dans l'ordre publié, chacun avec son libellé.
 * `exhaustif` dit si leur somme retrouve `membres_eligibles` — vrai sur
 * 19 832 / 19 832 aujourd'hui ; le rendu ne présente la partition comme telle
 * que si elle se vérifie sur l'entrée affichée.
 */
export function decomptesCohesion(entree, options = {}) {
  const publierExcuses = options.publierExcuses !== false;
  const cles = ORDRE_DECOMPTE_COHESION.filter((c) => c !== 'excuses' || publierExcuses);

  const decomptes = cles.map((cle) => ({
    cle,
    label: LIBELLES_DECOMPTE_COHESION[cle],
    valeur: Number.isFinite(entree?.[cle]) ? entree[cle] : null,
    // Une position exprimée porte sa couleur via `styleForPosition` ;
    // `non_votant`, « sans trace de vote » et « excusés » n'en portent aucune.
    position: ['pour', 'contre', 'abstention', 'non_votant'].includes(cle) ? cle : null,
  }));

  const somme = ORDRE_DECOMPTE_COHESION.reduce(
    (acc, cle) => acc + (Number.isFinite(entree?.[cle]) ? entree[cle] : 0), 0,
  );

  return {
    decomptes,
    eligibles: Number.isFinite(entree?.membres_eligibles) ? entree.membres_eligibles : null,
    exhaustif: somme === entree?.membres_eligibles,
  };
}

/*
 * Le ratio de cohésion, avec ses deux nombres et jamais un pourcentage seul
 * (§2 règle 7). Le numérateur est le décompte de la position majoritaire ; le
 * dénominateur est `membres_eligibles`, **borné par chambre depuis #492** —
 * une union sur tous les mandats électifs comptait un membre absent sur des
 * scrutins où il ne pouvait plus voter, donc un faux dénominateur.
 *
 * 145 des 19 832 entrées n'ont aucune position exprimée : `position_majoritaire`
 * y est `null` et le ratio rend `N/D`, jamais 0.
 */
export const LIBELLE_DENOMINATEUR_COHESION = 'membres éligibles à ce scrutin';

export function ratioCohesion(entree) {
  const position = entree?.position_majoritaire ?? null;
  const numerateur = position && Number.isFinite(entree?.[position]) ? entree[position] : null;
  return ratio(numerateur, entree?.membres_eligibles, LIBELLE_DENOMINATEUR_COHESION);
}

/*
 * Le quorum est une comparaison à un seuil PUBLIÉ (`meta.seuil_quorum`, 0,5 sur
 * les 7 fiches) : l'afficher sans le seuil laisserait croire à un seuil légal.
 * La participation est rendue avec ses deux nombres, comme tout ratio.
 */
export function quorumDuScrutin(entree, seuil) {
  const eligibles = entree?.membres_eligibles;
  const exprimesEtNonVotants = ['pour', 'contre', 'abstention', 'non_votant']
    .reduce((acc, cle) => acc + (Number.isFinite(entree?.[cle]) ? entree[cle] : 0), 0);

  return {
    atteint: entree?.quorum_atteint ?? null,
    seuil: Number.isFinite(seuil) ? seuil : null,
    seuilLabel: Number.isFinite(seuil) ? `${formatNumber(Math.round(seuil * 100))} %` : null,
    // Dénominateur court : la carte porte déjà le libellé long sur le ratio
    // de cohésion, juste au-dessus. Le répéter deux fois par carte le noie.
    participation: ratio(exprimesEtNonVotants, eligibles, 'membres éligibles'),
  };
}

/* ── Règle : une troncature déclare sa règle (lot 1, règle 3) ────────────────
 *
 * `slice(0, 12)` était déjà dans l'adaptateur, sans dénominateur : le lecteur
 * croyait voir une sélection, il voyait une coupe. Les fiches publient de 3 832
 * à 4 099 scrutins de cohésion.
 *
 * La règle affichée est vérifiable et vérifiée : `cohesion_votes` est trié par
 * date de scrutin DÉCROISSANTE sur les 5 fiches AN (contrôlé entrée par entrée
 * après jointure sur `pivot_data/scrutins.json`, 19 832 / 19 832 résolues).
 * Écrire « les plus importants » serait un jugement (§2 règle 1) ; « les plus
 * récents » est un fait.
 */
export const NB_SCRUTINS_AFFICHES = 12;
export const REGLE_TRONCATURE_COHESION = 'les plus récents, par date de scrutin';

/* ── Règle : une étiquette ne se publie jamais sans son porteur ──────────────
 *
 * `tags_thematiques_agreges` est l'agrégation des `tags_thematiques[]` des
 * membres, eux-mêmes dérivés de leurs `interventions[]` : `theme_officiel`
 * quand le compte rendu de l'Assemblée en porte un, `mots_cles` sinon. Ce sont
 * donc les SUJETS sur lesquels les membres sont intervenus, intitulés par la
 * source — jamais des positions du groupe (AGENTS.md §2 règle 8).
 *
 * Le garde-fou est `nb_membres_porteurs`, et il est publié avec l'étiquette,
 * jamais après elle : une étiquette portée par 1 membre sur 76 ne dit pas ce
 * que dit une étiquette portée par 60, et l'afficher seule donnerait l'empreinte
 * d'UNE personne pour celle du groupe — le défaut exact que #657 a corrigé, en
 * faisant collecter le thème des interventions des 468 membres de roster.
 *
 * Mesuré au commit `c6edee05` le 31/08/2026 : 448 des 468 profils
 * `roster_groupe` portent au moins une étiquette, les 5 fiches AN en publient
 * de 1 554 (`AN:SOC`) à 4 303 (`AN:REN`), et `nb_membres_porteurs` y monte
 * jusqu'à 99. Les 2 fiches Sénat en portent 0, parce qu'elles sont conservées
 * et jamais régénérées (#528) — c'est `ListeVide` qui le dit, pas un zéro.
 *
 * Le dénominateur est `len(membres)`, la population que l'agrégation a
 * réellement lue (vérifié sur les 5 fiches AN : 76, 62, 193, 90, 31, retrouvés
 * à partir de `poids_relatif`), jamais `roster_total`, qui compte des membres
 * dont aucun profil n'est publié. `poids_relatif` lui-même n'est pas publié :
 * la fiche donne ses deux nombres (§2 règle 7), comme `mandats_agreges` depuis
 * #656.
 */
export const LIBELLE_DENOMINATEUR_TAGS = 'membres du groupe dont le profil est publié';

export function etiquettesThematiques(groupe, limite = NB_TAGS_AFFICHES) {
  const denominateur = (groupe?.membres || []).length;
  return (groupe?.tags_thematiques_agreges || []).slice(0, limite).map((t) => {
    const porteurs = ratio(t.nb_membres_porteurs, denominateur, LIBELLE_DENOMINATEUR_TAGS);
    return {
      label: t.tag,
      porteurs: Number.isFinite(t.nb_membres_porteurs) ? t.nb_membres_porteurs : null,
      denominateur,
      // La phrase complète, dénominateur nommé, pour l'infobulle et les
      // technologies d'assistance : le pastille n'affiche que les deux nombres.
      porteursTexte: porteurs.text,
    };
  });
}

export const NB_TAGS_AFFICHES = 20;
export const REGLE_TRONCATURE_TAGS = 'les plus portés par les membres du groupe';

/*
 * Les ENTRÉES de la règle, pas son résultat : c'est `Troncature` (lot 1) qui
 * décide s'il y a coupe, et lui seul. Rendre ici le texte déjà composé
 * obligerait le rendu à le redécouper pour le réafficher.
 */
export function troncatureCohesion(total) {
  return {
    shown: Math.min(NB_SCRUTINS_AFFICHES, total ?? 0),
    total: total ?? 0,
    rule: REGLE_TRONCATURE_COHESION,
  };
}

export function troncatureTags(total) {
  return {
    shown: Math.min(NB_TAGS_AFFICHES, total ?? 0),
    total: total ?? 0,
    rule: REGLE_TRONCATURE_TAGS,
  };
}

/* ── Règle : `meta` se lit, et rien ne le lisait ─────────────────────────────
 *
 * `couverture_roster.etat` et `preuve` sont publiés sur 7 / 7 fiches et aucun
 * composant n'en lisait un seul. Le ratio seul ne dit pas de quoi il est le
 * ratio : `groupe-Senat-LR` publie 15 profils sur 235 — 6,4 % —, et lu sans son
 * état ce chiffre se lit comme une perte. C'en est un périmètre : le Sénat est
 * hors du périmètre éditorial depuis #528, et la `preuve` le dit en toutes
 * lettres, avec ses références et sa condition de reprise.
 *
 * La cause est traduite dans le vocabulaire du lot 1 (`EMPTY_LIST_CAUSES`) :
 * `hors_perimetre` parle de NOTRE décision, donc `hors_couverture` ; un état
 * inconnu ne devient jamais « aucun résultat ».
 */
export const ETATS_COUVERTURE_ROSTER = {
  dans_le_perimetre: {
    titre: 'Dans le périmètre',
    phrase:
      "Les membres du groupe sans profil publié manquent à la collecte : ils n'ont pas été écartés.",
    // Une liste vide sur une fiche du périmètre est une mesure : la collecte a
    // abouti et n'a rien trouvé. La phrase par défaut du lot 1 convient.
    causeListeVide: 'couvert',
    motifListeVide: null,
  },
  hors_perimetre: {
    titre: 'Hors périmètre',
    phrase:
      "Les membres sans profil publié le sont par une décision éditoriale, pas par un défaut de collecte.",
    // `non_collecte`, et non `hors_couverture` : ce vide vient de NOTRE décision
    // de ne plus interroger la source, pas d'une période que la source ne
    // publierait pas. Les deux causes n'affirment pas la même chose (#326).
    causeListeVide: 'non_collecte',
    motifListeVide:
      "Cette fiche est hors du périmètre éditorial du produit : sa collecte est suspendue, et ses listes ne sont plus alimentées. Ce vide est une décision, pas un résultat. La preuve publiée par la fiche — ses références et sa condition de reprise — est reproduite en toutes lettres sous « Vérification ».",
  },
};

export function couvertureRoster(groupe) {
  const bloc = groupe?.meta?.couverture_roster || {};
  const etat = bloc.etat ?? null;
  const connu = etat ? ETATS_COUVERTURE_ROSTER[etat] : null;

  return {
    etat,
    connu: Boolean(connu),
    titre: connu ? connu.titre : 'État de couverture non publié',
    phrase: connu
      ? connu.phrase
      : "Cette fiche ne déclare pas si les membres sans profil publié relèvent d'une décision ou d'un défaut de collecte.",
    // La `preuve` n'est exigée par le schéma que sur `hors_perimetre` : ailleurs
    // son absence est normale et ne se signale pas.
    preuve: typeof bloc.preuve === 'string' && bloc.preuve.trim() ? bloc.preuve : null,
    causeListeVide: connu ? connu.causeListeVide : null,
    // La `preuve` verbatim n'est publiée qu'UNE fois, sous « Vérification » :
    // elle fait un paragraphe, et la répéter sous chacune des trois listes
    // vides d'une fiche Sénat noierait la page.
    motifListeVide: connu ? connu.motifListeVide : null,
    profils: ratio(bloc.profils_disponibles, bloc.roster_total, 'membres du groupe'),
  };
}

/* ── Règle : ce qui est interdit est écrit (lot 1) ───────────────────────────
 *
 * Le refus propre à la fiche de groupe. Les écarts individu / groupe sont une
 * donnée de CONTRÔLE INTERNE (`--rapport-interne`), volontairement absente du
 * schéma de groupe : les publier désignerait qui s'est écarté de la ligne,
 * c'est-à-dire un classement interne au groupe (§2 règles 1 et 7).
 */
export const REFUS_FICHE_GROUPE = [
  {
    id: 'ecarts-individuels',
    sujet: 'Écarts individuels',
    phrase: "Cette fiche ne nomme jamais qui s'est écarté de la position majoritaire.",
    pourquoi:
      "Les décomptes disent combien de membres ont pris chaque position, jamais lesquels. Désigner les écarts produirait un classement à l'intérieur du groupe, et l'écart entre un vote individuel et sa ligne de groupe reste une donnée de contrôle interne.",
  },
  {
    id: 'assiduite-de-groupe',
    sujet: 'Assiduité',
    phrase: "« Sans trace de vote » n'est pas un taux d'absence.",
    pourquoi:
      "Ce décompte réunit les membres éligibles pour lesquels aucun vote n'a été trouvé sur ce scrutin. Il décrit ce que la source publie, pas la présence des personnes — et il n'est jamais rapporté à quiconque individuellement.",
  },
];
