/*
 * Les règles de lecture d'une FICHE DE LIGNÉE — la page de groupe de #329,
 * depuis que la propriétaire a tranché, le 10/09/2026, qu'on publie une fiche
 * par lignée et non par maillon (#836).
 *
 * Ce module ne dessine rien. Il est importé DEUX FOIS : par le navigateur, et
 * par `scripts/vue-lignee.mjs`, qui en calcule la projection au build. Une
 * règle écrite une fois et lue par les deux ne peut pas diverger — d'où
 * l'extension explicite des imports, que Node exige et que Vite accepte.
 *
 * Ce qui est propre à la lignée, et seulement cela, est écrit ici. Le quorum,
 * le partage, les convergences restent dans `utils/groupe.js` : un maillon est
 * une fiche de groupe, et ses règles ne changent pas parce qu'on l'enchaîne.
 */

import { urlDossierAN } from './lecture.js';

/* ── Règle : l'effectif se recompte jour par jour, et retombe sur le publié ──
 *
 * La frise de « En bref » trace le nombre de membres du groupe à chaque date où
 * il change, depuis `membres[].periodes` (#809) — les intervalles réels
 * d'appartenance, jamais l'enveloppe `debut_dans_groupe`/`fin_dans_groupe`, qui
 * recolle en un seul intervalle un membre parti puis revenu.
 *
 * La courbe n'est pas une seconde source de l'effectif : sa valeur à la date de
 * référence d'un maillon RETROUVE `effectif.a_la_date_de_reference`, au membre
 * près, sur les 28 maillons AN du corpus du 11/09/2026. Un écart voudrait dire
 * que l'une des deux lectures a changé sans l'autre.
 *
 * Une fin d'appartenance est INCLUSE : le membre compte encore ce jour-là, et
 * ne sort que le lendemain.
 */
function lendemain(iso) {
  const d = new Date(`${iso}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + 1);
  return d.toISOString().slice(0, 10);
}

export function serieEffectif(membres, jusqua = null) {
  const evenements = new Map();
  const ajouter = (date, pas) => evenements.set(date, (evenements.get(date) ?? 0) + pas);

  for (const membre of membres || []) {
    const periodes = Array.isArray(membre?.periodes) && membre.periodes.length
      ? membre.periodes
      : [{ debut: membre?.debut_dans_groupe ?? null, fin: membre?.fin_dans_groupe ?? null }];
    for (const p of periodes) {
      // Une appartenance sans début n'est pas datée : elle ne se place sur
      // aucune date, plutôt que d'être posée d'office au premier jour (§2 r. 5).
      if (!p?.debut) continue;
      ajouter(p.debut, +1);
      if (p.fin) ajouter(lendemain(p.fin), -1);
    }
  }

  let niveau = 0;
  const points = [];
  for (const date of [...evenements.keys()].sort()) {
    niveau += evenements.get(date);
    points.push([date, niveau]);
  }
  return jusqua ? points.filter(([date]) => date <= jusqua) : points;
}

/* ── Règle : d'où vient chaque personne d'un maillon ─────────────────────────
 *
 * « Qui sont-ils » montre un point par personne et par maillon (forme B,
 * retenue par la propriétaire le 11/09/2026). Chaque point dit d'où vient la
 * personne, en trois états et pas plus :
 *
 *  - `prec`    — elle était du maillon qui précède immédiatement ;
 *  - `retour`  — elle était d'un maillon plus ancien, pas du précédent ;
 *  - `nouveau` — c'est son premier maillon dans la lignée.
 *
 * Trois états et non un taux de renouvellement : un taux comparé d'une lignée
 * à l'autre deviendrait un indice (§2 règle 1). Les trois comptes sont publiés
 * côte à côte, et leur somme retombe sur le nombre de personnes du maillon.
 *
 * « Nouveau dans la lignée » ne dit PAS « nouveau député » : la personne a pu
 * siéger ailleurs avant. La donnée ne porte que la lignée, et la page n'en dit
 * pas plus qu'elle.
 */
export const PASSAGES = {
  prec: { label: 'déjà là au groupe précédent', compte: 'déjà là' },
  retour: { label: "revenu d'un groupe plus ancien", compte: 'revenus' },
  nouveau: { label: 'nouveau dans la lignée', compte: 'nouveaux' },
};

export const ORDRE_PASSAGES = ['prec', 'retour', 'nouveau'];

/*
 * `indices` : les rangs des maillons où la personne figure, croissants.
 */
export function passage(indices, rang) {
  if (!indices.length || indices[0] === rang) return 'nouveau';
  return indices.includes(rang - 1) ? 'prec' : 'retour';
}

/*
 * Les personnes de chaque maillon, rangées par état puis par nom.
 *
 * `lignee.membres[].maillons` porte les `groupe_id` traversés (#836) : c'est lui
 * qui est lu, jamais une ressemblance de nom.
 */
export function personnesParMaillon(lignee) {
  const rangs = new Map((lignee?.maillons || []).map((m, i) => [m.groupe_id, i]));
  const personnes = (lignee?.membres || []).map((m) => ({
    id: m.membre_id,
    nom: m.nom,
    indices: (m.maillons || []).map((g) => rangs.get(g)).filter((i) => i != null).sort((a, b) => a - b),
  }));

  return (lignee?.maillons || []).map((_, rang) => {
    const presents = personnes
      .filter((p) => p.indices.includes(rang))
      .map((p) => ({ ...p, passage: passage(p.indices, rang) }))
      .sort((a, b) => ORDRE_PASSAGES.indexOf(a.passage) - ORDRE_PASSAGES.indexOf(b.passage)
        || a.nom.localeCompare(b.nom, 'fr'));
    const comptes = Object.fromEntries(ORDRE_PASSAGES.map((cle) => [cle, 0]));
    for (const p of presents) comptes[p.passage] += 1;
    return { personnes: presents, comptes };
  });
}

/* ── Règle : les amendements d'un maillon, par commission saisie au fond ─────
 *
 * « Ce qu'ils ont proposé » reprend le gabarit de la fiche candidat
 * (annotation de la propriétaire, 11/09/2026) : une barre par commission, le
 * ratio par texte au milieu, les textes distincts au bout, et un switch
 * EXCLUSIF entre les deux types de déposant d'un groupe — ils ne s'additionnent
 * jamais (`AGENTS.md` §6), chacun compte contre son propre total.
 *
 * LA POPULATION EST CELLE DE LA FICHE, et elle se VÉRIFIE. Un amendement compte
 * pour un maillon s'il figure dans l'`amendements[]` d'un de ses membres ET que
 * son identifiant porte la législature du maillon — la règle de #821, lue sur
 * l'identifiant et jamais sur une date —, une fois quel que soit le nombre de
 * cosignataires (#643). C'est une seconde écriture d'une règle du pipeline, et
 * elle n'est tolérable qu'à une condition : retomber sur les totaux publiés.
 * `sync-data` compare, type par type, à `amendements_agreges.par_type_deposant`
 * — 28 maillons AN sur 28 au chiffre près le 11/09/2026 — et ne publie PAS la
 * répartition d'un type qui s'en écarte. Un écart ne se corrige pas ici : il
 * dit que l'une des deux règles a bougé.
 *
 * La matière est la commission saisie au fond du DOSSIER (#328), par le même
 * chemin que la fiche candidat : `texte_vise` → `textes[].dossier_id` →
 * `commissions_dossiers.json`. Un amendement sans dossier, ou dont le dossier
 * n'a pas de commission connue, reste compté sous `null` — « matière non
 * établie » au rendu —, jamais déduit d'un intitulé (§2 règle 1).
 */
export const TYPES_DEPOSANT_GROUPE = ['depute', 'commission_rapporteur'];

export function repartitionParCommission(ids, amendements, textes, commissionDuDossier, statutDuDossier = () => null) {
  const parType = new Map();
  let introuvables = 0;
  for (const id of ids) {
    const a = amendements?.[id];
    if (!a) { introuvables += 1; continue; }
    const type = a.type_deposant || 'inconnu';
    if (!parType.has(type)) {
      parType.set(type, { n: 0, adoptes: 0, dossiers: new Set(), parCommission: new Map() });
    }
    const bloc = parType.get(type);
    bloc.n += 1;
    if (a.sort === 'adopté') bloc.adoptes += 1;
    const dossier = a.texte_vise ? (textes?.[a.texte_vise]?.dossier_id ?? null) : null;
    if (dossier) bloc.dossiers.add(dossier);
    const c = dossier ? commissionDuDossier(dossier) : null;
    const cle = c ? (c.sigle || c.nom || null) : null;
    if (!bloc.parCommission.has(cle)) bloc.parCommission.set(cle, { amendements: 0, dossiers: new Map() });
    const ligne = bloc.parCommission.get(cle);
    ligne.amendements += 1;
    if (dossier) {
      if (!ligne.dossiers.has(dossier)) {
        ligne.dossiers.set(dossier, {
          dossier,
          titre: textes?.[a.texte_vise]?.titre ?? null,
          sourceUrl: urlDossierAN(dossier),
          amendements: 0,
          adoptes: 0,
          dernier: null,
        });
      }
      const d = ligne.dossiers.get(dossier);
      d.amendements += 1;
      if (a.sort === 'adopté') d.adoptes += 1;
      if (a.date && (!d.dernier || a.date > d.dernier)) d.dernier = a.date;
    }
  }

  /* Les textes d'une commission, au clic (annotation du 11/09/2026). RANGÉS PAR
   * DATE, le plus récemment amendé d'abord, jamais par volume : déposer beaucoup
   * sur un texte peut être un travail de fond comme une obstruction, et le
   * nombre ne les distingue pas (règle de forme 6, #326). Le sort du TEXTE vient
   * de `scrutins_dossiers.json` (#758) et n'existe que pour un dossier passé par
   * un scrutin : ailleurs il reste `null`, dit « non publié » au rendu. */
  const textesDe = (dossiers) => [...dossiers.values()]
    .map((d) => ({ ...d, statut: statutDuDossier(d.dossier) }))
    .sort((x, y) => String(y.dernier ?? '').localeCompare(String(x.dernier ?? '')) || x.dossier.localeCompare(y.dossier));

  const types = {};
  for (const [type, bloc] of parType) {
    const lignes = [...bloc.parCommission.entries()]
      .filter(([cle]) => cle !== null)
      .map(([commission, l]) => ({
        commission, amendements: l.amendements, textes: l.dossiers.size, detail: textesDe(l.dossiers),
      }))
      // Par volume, puis par nom : jamais l'ordre d'insertion, qui rendrait une
      // égalité comme une avance.
      .sort((x, y) => y.amendements - x.amendements || x.commission.localeCompare(y.commission, 'fr'));
    const nd = bloc.parCommission.get(null);
    types[type] = {
      amendements: bloc.n,
      adoptes: bloc.adoptes,
      dossiers: bloc.dossiers.size,
      lignes,
      nonEtablie: nd ? { amendements: nd.amendements, textes: nd.dossiers.size, detail: textesDe(nd.dossiers) } : null,
    };
  }
  return { types, introuvables };
}

/* ── Règle : la frise de la lignée porte la posture en MOTIF ─────────────────
 *
 * Retenu par la propriétaire le 11/09/2026, en maquette, sur quatre jeux
 * comparés : majoritaire en aplat foncé, opposition en diagonales, minoritaire
 * en mauve clair uni, non déclarée en petits points serrés — un grisé. Les deux
 * postures « claires » ne sont pas un rang : la clarté sépare ce qui est dit de
 * ce qui ne l'est pas, pas un groupe d'un autre (§2 règle 1).
 *
 * La fiche candidat a retiré ses motifs le même jour (#328, « la frise dit
 * l'institution, et rien d'autre ») parce que la bande y portait DEUX
 * encodages, l'institution en teinte et la posture en motif. La frise d'une
 * lignée n'en porte qu'un : la teinte est toujours celle de l'Assemblée, et le
 * motif y est la seule chose qui change d'un maillon à l'autre.
 *
 * Les points restent dans la teinte de l'Assemblée : gris neutre, ils se
 * liraient comme l'encre des absences, qui désigne le Sénat ailleurs sur le
 * site. `absente` — une fiche qui ne porte pas le champ, les deux du Sénat — ne
 * prend aucun motif : c'est un contour tireté, un trou chez nous.
 */
export const MOTIFS_POSTURE = {
  majorite: 'plein',
  opposition: 'diagonales',
  minoritaire: 'mauve',
  non_declaree: 'points',
};

export function motifDePosture(posture) {
  return (posture?.declaree && MOTIFS_POSTURE[posture.valeur]) || 'absente';
}
