import { useState } from 'react';
import { DONNEES_SCHEMA, FICHES_SCHEMA, SOURCES_SCHEMA } from '../data/schemaSources';
import './SchemaSources.css';

/* ── Le flux des sources : source → ce qu'elle apporte → où cela se lit (#951) ──
 *
 * Un dessin, pas un graphique : aucune épaisseur ne porte de quantité. Un trait
 * épais se lirait comme « cette source compte plus », ce que rien ne mesure ici.
 *
 * Survoler (ou focaliser) une source, une donnée ou une fiche allume son trajet
 * et estompe le reste. La figure garde sa largeur et défile sur mobile : la
 * replier en colonne casserait le trajet, qui est ce qu'elle montre. */

const PAS = 42;
const HAUT = 30;
const HAUT_ENTETE = 34;
const LARGEUR = 880;
const COLONNES = { source: [0, 210], donnee: [330, 262], fiche: [712, 168] };

const courbe = (x1, y1, x2, y2) => {
  const m = (x1 + x2) / 2;
  return `M${x1},${y1} C${m},${y1} ${m},${y2} ${x2},${y2}`;
};

export default function SchemaSources() {
  const [survol, setSurvol] = useState(null);

  const yDe = (liste, id) => HAUT_ENTETE + liste.findIndex((x) => x.id === id) * PAS;
  const yFiche = (f) => HAUT_ENTETE + f.ligne * PAS;
  const hauteur = HAUT_ENTETE + SOURCES_SCHEMA.length * PAS + 10;

  // Les clés allumées : l'élément survolé et tout ce qu'un trait relie à lui.
  const allumees = new Set();
  if (survol) {
    allumees.add(survol);
    for (const d of DONNEES_SCHEMA) {
      if (d.id === survol || d.de.includes(survol)) {
        allumees.add(d.id);
        d.de.forEach((s) => allumees.add(s));
      }
    }
    for (const f of FICHES_SCHEMA) {
      if (f.id === survol) f.de.forEach((d) => allumees.add(d));
      if (f.id === survol || f.de.some((d) => allumees.has(d))) allumees.add(f.id);
    }
  }
  const etat = (...cles) => (!survol ? '' : cles.every((c) => allumees.has(c)) ? ' ss-vif' : ' ss-estompe');
  const handlers = (id) => ({
    onMouseEnter: () => setSurvol(id),
    onMouseLeave: () => setSurvol(null),
    onFocus: () => setSurvol(id),
    onBlur: () => setSurvol(null),
    tabIndex: 0,
  });

  return (
    <div className="ss">
      <div className="ss-defile">
        <svg
          className="ss-svg"
          width={LARGEUR}
          height={hauteur}
          viewBox={`0 0 ${LARGEUR} ${hauteur}`}
          // Pas de role="img" : il rendrait les onze liens muets pour un
          // lecteur d'écran.
          aria-labelledby="ss-titre"
        >
          <title id="ss-titre">
            Ce que chaque source apporte, et sur quelle fiche cela se lit
          </title>
          <defs>
            <pattern id="ss-hachure" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
              <rect width="5" height="5" className="ss-hachure-fond" />
              <rect width="2" height="5" className="ss-hachure-trait" />
            </pattern>
          </defs>

          <text className="ss-entete" x={COLONNES.source[0]} y="14">SOURCE</text>
          <text className="ss-entete" x={COLONNES.donnee[0]} y="14">CE QU’ELLE APPORTE</text>
          <text className="ss-entete" x={COLONNES.fiche[0]} y="14">OÙ CELA SE LIT</text>

          {DONNEES_SCHEMA.flatMap((d) =>
            d.de.map((sid) => {
              const s = SOURCES_SCHEMA.find((x) => x.id === sid);
              return (
                <path
                  key={`${sid}-${d.id}`}
                  className={`ss-lien ss-lien--${s.teinte} ss-lien--${s.statut}${etat(sid, d.id)}`}
                  d={courbe(
                    COLONNES.source[0] + COLONNES.source[1],
                    yDe(SOURCES_SCHEMA, sid) + HAUT / 2,
                    COLONNES.donnee[0],
                    yDe(DONNEES_SCHEMA, d.id) + HAUT / 2,
                  )}
                />
              );
            }),
          )}
          {FICHES_SCHEMA.flatMap((f) =>
            f.de.map((did) => (
              <path
                key={`${did}-${f.id}`}
                className={`ss-lien ss-lien--fiche${etat(did, f.id)}`}
                d={courbe(
                  COLONNES.donnee[0] + COLONNES.donnee[1],
                  yDe(DONNEES_SCHEMA, did) + HAUT / 2,
                  COLONNES.fiche[0],
                  yFiche(f) + HAUT / 2,
                )}
              />
            )),
          )}

          {SOURCES_SCHEMA.map((s) => {
            const y = yDe(SOURCES_SCHEMA, s.id);
            const [x, w] = COLONNES.source;
            // Un LIEN, pas un groupe focalisable : il s'ouvre dans un nouvel
            // onglet, et le clavier l'atteint comme n'importe quel lien.
            return (
              <a
                key={s.id}
                href={s.url}
                target="_blank"
                rel="noopener noreferrer"
                aria-label={`${s.nom} — ouvrir la source dans un nouvel onglet`}
                className={`ss-noeud ss-source ss-source--${s.teinte} ss-source--${s.statut}${etat(s.id)}`}
                onMouseEnter={() => setSurvol(s.id)}
                onMouseLeave={() => setSurvol(null)}
                onFocus={() => setSurvol(s.id)}
                onBlur={() => setSurvol(null)}
              >
                <rect className="ss-pave" x={x + 0.75} y={y + 0.75} width={w - 1.5} height={HAUT - 1.5} rx="7" />
                {s.statut === 'retiree' && <rect x={x + 5} y={y + 5} width="10" height={HAUT - 10} rx="2" fill="url(#ss-hachure)" />}
                <text x={x + (s.statut === 'retiree' ? 22 : 10)} y={y + HAUT / 2 + 4.5}>{s.nom}</text>
                <text className="ss-sortie" x={x + w - 12} y={y + HAUT / 2 + 4.5} textAnchor="end" aria-hidden="true">↗</text>
              </a>
            );
          })}
          {DONNEES_SCHEMA.map((d) => {
            const y = yDe(DONNEES_SCHEMA, d.id);
            const [x, w] = COLONNES.donnee;
            return (
              <g key={d.id} className={`ss-noeud ss-donnee${etat(d.id)}`} {...handlers(d.id)}>
                <rect x={x} y={y} width={w} height={HAUT} rx="7" />
                <text x={x + 10} y={y + HAUT / 2 + 4.5}>{d.nom}</text>
              </g>
            );
          })}
          {FICHES_SCHEMA.map((f) => {
            const y = yFiche(f);
            const [x, w] = COLONNES.fiche;
            return (
              <g key={f.id} className={`ss-noeud ss-fiche${etat(f.id)}`} {...handlers(f.id)}>
                <rect x={x} y={y} width={w} height={HAUT} rx="7" />
                <text x={x + 10} y={y + HAUT / 2 + 4.5}>{f.nom}</text>
              </g>
            );
          })}
        </svg>
      </div>

      <ul className="ss-legende">
        <li><i className="ss-cle ss-cle--an" />Assemblée</li>
        <li><i className="ss-cle ss-cle--senat" />Sénat</li>
        <li><i className="ss-cle ss-cle--pe" />Europe</li>
        <li><i className="ss-cle ss-cle--gouv" />Gouvernement</li>
        <li><i className="ss-cle ss-cle--local" />Local</li>
        <li><i className="ss-cle ss-cle--candidat" />Qui est candidat</li>
        <li><i className="ss-cle ss-cle--citee" />Citée, relue à la main</li>
        <li><i className="ss-cle ss-cle--retiree" />Plus interrogée</li>
      </ul>
    </div>
  );
}
