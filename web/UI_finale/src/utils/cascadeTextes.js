/*
 * LA CASCADE DES TEXTES PORTÉS — mise en page, et rien d'autre.
 *
 * Ce module ne rend rien : il rend des COORDONNÉES. Le composant les dessine.
 * C'est ce qui permet de vérifier la figure hors navigateur — conservation des
 * textes, contiguïté des barres, départ des rubans — au lieu de la regarder.
 *
 * ── CE QUE d3-sankey APPORTE, ET CE QU'IL FAUT LUI REPRENDRE ───────────────
 *
 * Il pose `y0` (ordonnée du ruban à sa SORTIE d'un nœud) et `y1` (à son
 * ARRIVÉE au suivant), et ces valeurs sont modifiables avant le tracé. Une
 * librairie de flux qui les garde pour elle ne peut pas produire cette figure :
 * quand 30 textes entrent dans un nœud et que 7 en sortent, les 7 sont
 * replacés depuis le bord haut, et au plus une matière reste alignée. Le
 * défaut est arithmétique, pas paramétrique.
 *
 * On corrige donc le DÉPART, et lui seul : chaque ruban sortant repart de la
 * bande par laquelle sa matière est entrée. L'ARRIVÉE reste à d3, qui empile
 * les arrivées d'un nœud de façon contiguë — c'est elle qui fait converger les
 * matières dans une barre pleine. Forcer `y1 = y0` figeait chaque matière sur
 * sa voie et cassait la convergence : les barres se lisaient en morceaux.
 *
 * Ce qui rend les deux compatibles, c'est LA FOURCHE. Tant qu'un nœud perdait
 * une part de son flux, aucun empilement ne pouvait aligner plus d'une
 * matière. La branche basse étant dessinée, ce qui entre égale ce qui sort, et
 * l'empilement des départs coïncide avec celui des arrivées, matière par
 * matière.
 *
 * ── CE QUE LA BRANCHE BASSE NE DIT PAS ─────────────────────────────────────
 *
 * Elle ne s'appelle ni « rejeté », ni « abandonné ». `_STADE_RANKS`
 * (candidate_profile.py) et `KNOWN_STADES_PROCEDURAUX` (schema_pivot.py) ne
 * connaissent que des valeurs CROISSANTES, et un dossier n'en porte qu'une :
 * la plus avancée réellement atteinte. Aucun champ ne dit qu'un texte a été
 * repoussé, retiré, ou qu'il attend encore. Écrire « rejeté » publierait un
 * sort que la source n'établit pas (§2 règle 5, et règle 2). La branche basse
 * dit donc « non discuté en séance », « non adopté », « non promulgué » :
 * aucun acte au-delà à la date du corpus. Un texte en navette est dedans.
 *
 * LA DERNIÈRE ÉTAPE N'A PAS DE SORTIE. Elle achève la procédure ; c'est la
 * seule barre dont rien ne repart, et c'est un fait, pas un manque.
 *
 * ── AUCUN SEUIL ────────────────────────────────────────────────────────────
 *
 * Rien n'est filtré pour cause de petitesse : du plus gros ruban au trait d'un
 * seul texte, tous sont tracés. Un seuil qui déciderait qu'un fait existe est
 * exactement ce que §2 règle 1 interdit.
 */
import { sankey, sankeyLeft, sankeyLinkHorizontal } from 'd3-sankey';
import { LIBELLE_STADE } from './profilCandidat';

/* Le mot court d'une étape, et la négation courte de l'étape SUIVANTE. Deux
 * tables plutôt que deux tableaux parallèles : l'échelle des stades peut
 * gagner un cran (`inscrit_ordre_jour` n'est porté par aucun des 423 textes
 * des 13 candidats déclarés, mais le schéma le publie), et un tableau indexé
 * se décalerait en silence ce jour-là. */
export const MOT_COURT_STADE = {
  examine_commission: 'commission',
  inscrit_ordre_jour: 'ordre du jour',
  discute_seance: 'séance',
  adopte: 'adoption',
  promulgue: 'promulgation',
};

export const NEGATION_STADE = {
  inscrit_ordre_jour: 'non inscrit',
  discute_seance: 'non discuté',
  adopte: 'non adopté',
  promulgue: 'non promulgué',
};

// Largeur moyenne d'un caractère de `.cp-ter-etape` (11,5 px de Manrope) :
// sert à décider si un mot tient à côté d'une barre, sans mesurer le DOM.
const CAR = 6.1;
const HAUTEUR = { large: 430, etroit: 340 };
// La gouttière porte les noms de matière. Sous 560 px elle mangerait la moitié
// des colonnes : la clé des couleurs passe alors dans la légende.
const GOUTTIERE = { large: 172, etroit: 6 };

export function estEtroit(largeur) {
  return largeur < 560;
}

/*
 * L'échelle des étapes VIVES, et pourquoi elle est un préfixe.
 *
 * Une étape est vive dès que quelque chose l'atteint ou la dépasse. Comme
 * `atteint` est décroissant, les étapes vives forment toujours un PRÉFIXE de
 * l'échelle : jamais de trou au milieu, donc jamais de lien vers un nœud qui
 * n'existe pas.
 */
function compter(cascade) {
  const stades = cascade.stades;
  const mats = [...new Set(cascade.flux.map((x) => x[0]))];
  const somme = (predicat) => cascade.flux.filter(predicat).reduce((t, x) => t + x[2], 0);
  const arret = stades.map((st) => somme((x) => x[1] === st));
  const atteint = stades.map((_, i) => arret.slice(i).reduce((t, n) => t + n, 0));
  const parMat = new Map(mats.map((m) => {
    const ar = stades.map((st) => somme((x) => x[0] === m && x[1] === st));
    return [m, { arret: ar, atteint: ar.map((_, i) => ar.slice(i).reduce((t, n) => t + n, 0)) }];
  }));
  return { mats, arret, atteint, parMat };
}

export function disposerCascade(cascade, largeur, teinteDe) {
  const stades = cascade.stades || [];
  if (!cascade.total || (cascade.flux || []).length < 3 || stades.length < 2) return null;

  const { mats, arret, atteint, parMat } = compter(cascade);
  const FIN = stades.length - 1;
  const SORTIE = stades.map((st) => `sortie:${st}`);
  const etapesVives = stades.filter((_, i) => atteint[i] > 0);
  // Une porte n'a de sortie que si quelque chose en sort : pas de barre vide.
  const sortiesVives = stades.map((_, i) => (i < FIN && arret[i] > 0 ? i : -1)).filter((i) => i >= 0);
  if (!etapesVives.length) return null;

  const nom = (i) => LIBELLE_STADE[stades[i]] || stades[i];
  const court = (i) => MOT_COURT_STADE[stades[i]] || nom(i);
  const negation = (i) => (i < FIN ? `non ${nom(i + 1)}` : '');
  const negationCourte = (i) => (i < FIN ? NEGATION_STADE[stades[i + 1]] || negation(i) : '');

  const W = Math.max(320, Math.round(largeur));
  const etroit = estEtroit(W);
  const H = etroit ? HAUTEUR.etroit : HAUTEUR.large;
  const GOUT = etroit ? GOUTTIERE.etroit : GOUTTIERE.large;

  /* UNE SORTIE DE LA DERNIÈRE COLONNE N'A QUE LA MARGE DROITE POUR SON NOM.
   * Les nœuds sont posés par profondeur : les matières à 0, l'étape k à k+1,
   * la sortie de la porte i à i+2. Celle qui tombe dans la dernière colonne
   * n'a aucune colonne suivante où écrire — on élargit la marge juste ce qu'il
   * faut. Pas sous 560 px, où elle coûterait le tiers de la figure. */
  const profMax = Math.max(etapesVives.length, ...sortiesVives.map((i) => i + 2));
  const sortiesDerniere = sortiesVives.filter((i) => i + 2 === profMax);
  const besoinD = (!etroit && sortiesDerniere.length)
    ? Math.max(...sortiesDerniere.map((i) => String(arret[i]).length + 1
      + Math.max(court(i).length, negationCourte(i).length))) * CAR + 18
    : 0;
  const MG = { g: GOUT, d: Math.max(etroit ? 34 : 48, besoinD), h: etroit ? 34 : 16, b: 14 };

  const noeuds = [
    ...mats.map((m) => ({ name: m })),
    ...etapesVives.map((st) => ({ name: st })),
    ...sortiesVives.map((i) => ({ name: SORTIE[i] })),
  ];
  const liens = [];
  for (const m of mats) {
    const c = parMat.get(m);
    if (c.atteint[0] > 0) {
      liens.push({ source: m, target: stades[0], value: c.atteint[0], mat: m, etape: 0, sortie: false });
    }
    for (let i = 0; i < stades.length; i += 1) {
      // La branche haute : ce qui franchit la porte.
      if (i < FIN && c.atteint[i + 1] > 0) {
        liens.push({ source: stades[i], target: stades[i + 1], value: c.atteint[i + 1], mat: m, etape: i + 1, sortie: false });
      }
      // La branche basse : ce dont le corpus n'enregistre aucun acte au-delà.
      if (i < FIN && c.arret[i] > 0) {
        liens.push({ source: stades[i], target: SORTIE[i], value: c.arret[i], mat: m, etape: i, sortie: true });
      }
    }
  }

  const g = sankey()
    .nodeId((n) => n.name)
    .nodeWidth(11)
    .nodePadding(etroit ? 8 : 12)
    // L'ordre des liens est celui du flux, pas celui que la mise en page
    // choisirait : c'est lui qui rend la correction du départ lisible.
    .linkSort(null)
    .nodeSort(null)
    // `justify`, l'alignement par défaut, colle à droite tout nœud sans
    // sortie : les barres de sortie quitteraient leur porte.
    .nodeAlign(sankeyLeft)
    .extent([[MG.g, MG.h], [W - MG.d, H - MG.b]])({
      nodes: noeuds.map((n) => ({ ...n })),
      links: liens.map((l) => ({ ...l })),
    });

  // La correction du départ (voir l'en-tête du module).
  const bandes = new Map();
  let recales = 0;
  for (const n of [...g.nodes].sort((a, b) => a.depth - b.depth)) {
    if (!n.targetLinks.length) continue;
    const curseur = new Map();
    for (const l of n.targetLinks) curseur.set(l.mat, l.y1 - l.width / 2);
    bandes.set(n.name, n.targetLinks.map((l) => ({
      y: l.y1 - l.width / 2, h: l.width, mat: l.mat, val: l.value,
    })));
    const sortants = [...n.sourceLinks].sort((a, b) => (a.sortie ? 1 : 0) - (b.sortie ? 1 : 0));
    for (const l of sortants) {
      const t = curseur.get(l.mat);
      if (t === undefined) continue;
      l.y0 = t + l.width / 2;
      curseur.set(l.mat, t + l.width);
      recales += 1;
    }
  }

  const chemin = sankeyLinkHorizontal();
  const parNom = new Map(g.nodes.map((n) => [n.name, n]));

  /* CE QUE CHAQUE ÉLÉMENT REPRÉSENTE, EN CRANS DE STADE. Un empilement répond
   * « combien », jamais « lesquels » : cliquer ouvre la liste (§2 règle 2).
   * Un ruban qui franchit une porte, c'est « au moins l'étape suivante » ; une
   * branche basse, c'est « exactement cette étape et pas plus ». */
  const rubans = g.links.map((l, k) => ({
    cle: `r${k}`,
    d: chemin(l),
    matiere: l.mat,
    couleur: teinteDe(l.mat),
    epaisseur: Math.max(l.width, 1),
    sortie: l.sortie,
    lo: l.etape,
    hi: l.sortie ? l.etape : FIN,
    valeur: l.value,
    titre: l.sortie
      ? `${l.mat}\n${l.value} texte${l.value > 1 ? 's' : ''} · ${negation(l.etape)}\nAucun acte de cette étape enregistré à la date du corpus`
      : `${l.mat}\n${l.value} texte${l.value > 1 ? 's' : ''} ${l.value > 1 ? 'atteignent' : 'atteint'} « ${nom(l.etape)} »`,
  }));

  /* LES QUATRE MOTS D'ÉTAPE NE TIENNENT PAS PAR HYPOTHÈSE. Ce qui décide est
   * l'écartement des colonnes, pas la largeur de la figure : cinq colonnes à
   * 700 px sont plus serrées que trois à 560. */
  const xEtapes = etapesVives.map((st) => parNom.get(st).x0);
  const esp = xEtapes.length > 1
    ? Math.min(...xEtapes.slice(1).map((x, k) => x - xEtapes[k])) : Infinity;
  const motCourt = etroit
    || Math.max(...etapesVives.map((st) => nom(stades.indexOf(st)).length)) * CAR + 22 > esp;

  const barres = []; const chiffres = []; const etiq = [];
  const nomPose = new Set();
  for (const n of g.nodes) {
    const i = stades.indexOf(n.name);
    const s = SORTIE.indexOf(n.name);
    const b = bandes.get(n.name);
    if (i >= 0 && b) {
      // La barre est d'un seul tenant : les arrivées étant empilées par d3,
      // les segments sont contigus. Ils restent distincts pour l'infobulle.
      for (const [k, seg] of b.entries()) {
        barres.push({
          cle: `b${n.name}-${k}`, etape: i, x: n.x0, y: seg.y,
          w: n.x1 - n.x0, h: Math.max(seg.h, 1.2), matiere: seg.mat,
          lo: i, hi: FIN, sortie: false, couleur: null,
          titre: `${seg.mat} · ${nom(i)}\n${seg.val} texte${seg.val > 1 ? 's' : ''} de cette matière ${seg.val > 1 ? 'atteignent' : 'atteint'} l'étape`,
        });
      }
    } else if (s >= 0 && b) {
      /* AU BOUT DU RUBAN, L'ÉTAPE ATTEINTE — PLUS UN NOMBRE. La barre dit ce
       * qui n'a pas eu lieu ; le lecteur cherche jusqu'où le texte est allé.
       * Deux lignes : la porte, puis ce qu'elle n'a pas franchi — « non
       * adopté » seul ne dit pas de quelle porte il sort, la barre étant posée
       * dans la colonne de l'étape suivante. Le chiffre gouverne les deux
       * lignes et passe donc en tête ; la seconde est en retrait sous lui. */
      const suivant = g.nodes.filter((o) => o.x0 > n.x1 + 1)
        .reduce((m, o) => Math.min(m, o.x0), Infinity);
      const place = (suivant === Infinity ? W - 2 : suivant - 6) - (n.x1 + 5);
      const chiffre = String(arret[s]).length + 1;
      const largeurPaire = (long) => Math.max(
        chiffre + (long ? nom(s) : court(s)).length,
        chiffre + (long ? negation(s) : negationCourte(s)).length,
      ) * CAR;
      const paire = largeurPaire(true) <= place
        ? [nom(s), negation(s)]
        : (largeurPaire(false) <= place ? [court(s), negationCourte(s)] : null);
      const hautB = Math.min(...b.map((seg) => seg.y));
      const basB = Math.max(...b.map((seg) => seg.y + seg.h));
      if (paire) {
        // Un seul nom par barre, pas un par ruban : tous les rubans qui y
        // arrivent disent la même chose, et la barre est d'un seul tenant.
        nomPose.add(n.name);
        const xl = n.x1 + 5;
        const yc = (hautB + basB) / 2;
        chiffres.push({
          cle: `c${n.name}`, x: xl, y: yc - 3, xRetrait: xl + chiffre * CAR, yRetrait: yc + 12,
          nombre: arret[s], haut: paire[0], bas: paire[1], lo: s, hi: s,
        });
      }
      for (const [k, seg] of b.entries()) {
        barres.push({
          cle: `s${n.name}-${k}`, etape: s, x: n.x0, y: seg.y,
          w: n.x1 - n.x0, h: Math.max(seg.h, 1.2), matiere: seg.mat,
          lo: s, hi: s, sortie: true, couleur: null,
          titre: `${seg.mat}\n${seg.val} texte${seg.val > 1 ? 's' : ''} · ${negation(s)}`,
        });
      }
    } else {
      barres.push({
        cle: `m${n.name}`, etape: null, x: n.x0, y: n.y0, w: n.x1 - n.x0,
        h: Math.max(n.y1 - n.y0, 1.2), matiere: n.name, lo: 0, hi: FIN,
        sortie: false, couleur: teinteDe(n.name), rx: 1,
        titre: `${n.name}\ntous ses textes portés`,
      });
    }
    if ((i >= 0 || s >= 0) && b) {
      const total = i >= 0 ? atteint[i] : arret[s];
      const lib = i >= 0 ? (motCourt ? court(i) : nom(i)) : (motCourt ? negationCourte(s) : negation(s));
      const large = (String(total).length + 1 + lib.length) * CAR + 6;
      // Calée à droite seulement quand elle ne tient plus : une étape seule,
      // tout à gauche, garderait sinon son nombre à l'autre bout de la figure.
      const finie = n.x0 + 15 + large > W;
      const x = finie ? W - 2 : n.x0 + 15;
      // La sortie n'entre dans la ligne du haut que si son nom n'a PAS tenu
      // contre sa barre : sinon la même phrase s'écrirait deux fois.
      if (i >= 0 || !nomPose.has(n.name)) {
        etiq.push({
          cle: `e${n.name}`, x, g: finie ? x - large : x, large, finie, total, lib,
          sortie: s >= 0, lo: i >= 0 ? i : s, hi: i >= 0 ? FIN : s,
        });
      }
    }
  }

  /* LES TITRES D'ÉTAPE SONT AU-DESSUS DE LA FIGURE. Sous chaque bande, ils
   * tombaient sur les rubans — une barre de sortie peut être n'importe où en
   * hauteur. Le chevauchement se règle étiquette par étiquette : posées de
   * gauche à droite, on MONTE d'une ligne tant que la place est prise, et le
   * cadre s'ouvre vers le haut d'autant qu'il faut. */
  const hautCommun = Math.min(...[...bandes.values()].map((b) => Math.min(...b.map((seg) => seg.y))));
  for (const e of etiq) e.y = hautCommun - 10;
  etiq.sort((a, b) => a.g - b.g);
  const posees = [];
  for (const e of etiq) {
    while (posees.some((o) => e.g < o.g + o.large && o.g < e.g + e.large && Math.abs(o.y - e.y) < 12)) {
      e.y -= 13;
    }
    posees.push(e);
  }
  const hautEtiq = Math.min(0, ...posees.map((e) => e.y - 11));

  /* LES NOMS DE MATIÈRE, DANS LA GOUTTIÈRE ET ÉCARTÉS. Deux passes : on pousse
   * vers le bas pour garantir l'écart, puis vers le haut pour rester dans le
   * cadre. Un nom déplacé de plus de trois pixels reçoit un tirant vers sa
   * bande — sans lui, une étiquette poussée désigne le ruban du voisin. */
  const nomsMatiere = [];
  const nMats = g.nodes.filter((n) => stades.indexOf(n.name) < 0 && SORTIE.indexOf(n.name) < 0)
    .sort((a, b) => a.y0 - b.y0);
  if (!etroit && nMats.length) {
    const ECART = 14;
    const ys = nMats.map((n) => (n.y0 + n.y1) / 2);
    for (let i = 1; i < ys.length; i += 1) ys[i] = Math.max(ys[i], ys[i - 1] + ECART);
    ys[ys.length - 1] = Math.min(ys[ys.length - 1], H - MG.b);
    for (let i = ys.length - 2; i >= 0; i -= 1) ys[i] = Math.min(ys[i], ys[i + 1] - ECART);
    for (let i = 0; i < ys.length; i += 1) ys[i] = Math.max(ys[i], MG.h + i * ECART);
    const maxCar = Math.max(8, Math.floor((GOUT - 14) / CAR));
    nMats.forEach((n, i) => {
      const cy = (n.y0 + n.y1) / 2;
      nomsMatiere.push({
        cle: `n${n.name}`, nom: n.name,
        court: n.name.length <= maxCar ? n.name : `${n.name.slice(0, maxCar - 1).trimEnd()}…`,
        x: n.x0 - 10, y: ys[i] + 4,
        tirant: Math.abs(ys[i] - cy) > 3
          ? `M${(n.x0 - 7).toFixed(1)},${ys[i].toFixed(1)} H${(n.x0 - 4).toFixed(1)} V${cy.toFixed(1)} H${n.x0.toFixed(1)}`
          : null,
      });
    });
  }

  const sorties = g.links.filter((l) => l.sortie);
  return {
    W, H: Math.round(H + 10 - hautEtiq), y0: hautEtiq, etroit,
    rubans, barres, chiffres, etiquettes: posees, nomsMatiere,
    matieres: mats, fin: FIN, atteint, arret,
    // Ce que la ligne de périmètre écrit — mesuré sur ce qui est DESSINÉ.
    mesures: {
      recales,
      portes: sortiesVives.length,
      rubansBas: sorties.length,
      textesBas: sorties.reduce((t, l) => t + l.value, 0),
      auBout: atteint[FIN],
      derniereEtape: nom(FIN),
    },
  };
}

/*
 * Les textes derrière un élément cliqué. La sélection est un INTERVALLE de
 * crans, et le voile éclaire tout ce qui la CROISE, pas seulement ce qui a été
 * cliqué : un ruban à la troisième porte ne se lit qu'avec les sauts qui l'ont
 * amené là. L'intersection des intervalles le donne gratuitement.
 */
export function croise(selection, matiere, lo, hi) {
  if (!selection) return true;
  return (!selection.matiere || selection.matiere === matiere)
    && lo <= selection.hi && selection.lo <= hi;
}

export function textesDeLaSelection(cascade, selection) {
  if (!selection) return [];
  const rang = (cle) => cascade.stades.indexOf(cle);
  return (cascade.textes || [])
    .filter((t) => (!selection.matiere || t.matiere === selection.matiere)
      && rang(t.stadeCle) >= selection.lo && rang(t.stadeCle) <= selection.hi)
    .sort((a, b) => rang(b.stadeCle) - rang(a.stadeCle) || a.titre.localeCompare(b.titre, 'fr'));
}
