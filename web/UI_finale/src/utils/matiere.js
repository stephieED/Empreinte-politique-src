/*
 * LA TEINTE D'UNE MATIÈRE — et pourquoi il a fallu ouvrir une palette.
 *
 * `DESIGN_SYSTEM.md` §5 écrivait « aucune couleur n'était libre » : le jaune
 * signal est pris par la sélection, l'action et le badge de source, le vert et
 * le rouge par les positions de vote, le bleu et le bronze par les institutions
 * de la frise. C'était vrai du besoin d'alors — MARQUER UNE LIGNE dans une
 * liste, ce que la fiche résout par un filet d'encre sans teinte.
 *
 * Une figure qui distingue N MATIÈRES est un besoin différent, et il n'a pas de
 * solution sans teinte : une rampe d'encre placerait les matières sur une
 * échelle, ce que §2 règle 1 interdit. La palette ci-dessous est donc
 * CATÉGORIELLE et sans ordre — aucune teinte n'y est « meilleure », l'ordre
 * d'attribution suit le volume et rien d'autre.
 *
 * Elle vient de Paul Tol (qualitative « muted »), choisie pour rester
 * distinguable sous les trois formes de daltonisme les plus fréquentes, et
 * elle ne recouvre aucune des teintes déjà attribuées : ni le jaune signal, ni
 * le vert/rouge de vote, ni le bleu/bronze des institutions.
 *
 * LE GRIS N'EST PAS UNE COULEUR DE LA PALETTE. Il est réservé à « matière non
 * établie », qui n'est pas une matière de plus mais une absence de donnée
 * (§2 règle 5) — la distinguer par la teinte la rangerait parmi les autres.
 */
import { MATIERE_NON_ETABLIE } from './profilCandidat';

export const PALETTE_MATIERE = [
  '#332288', '#88ccee', '#44aa99', '#999933', '#cc6677',
  '#aa4499', '#882255', '#6699cc', '#661100', '#117733',
  '#ddcc77', '#4477aa', '#ee8866', '#77aadd',
];

export const GRIS_SANS_MATIERE = '#c4c0b9';

export function teinteMatiere(matiere, rang) {
  if (matiere === MATIERE_NON_ETABLIE) return GRIS_SANS_MATIERE;
  return PALETTE_MATIERE[rang % PALETTE_MATIERE.length];
}
