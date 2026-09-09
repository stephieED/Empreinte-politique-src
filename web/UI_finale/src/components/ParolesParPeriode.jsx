/* ── « Ce qu'il a dit », par période politique (#328) ─────────────────────────
 *
 * Le composant ne calcule aucun fait : les périodes, les sujets, les plafonds
 * et la couverture arrivent construits par `utils/parolesParPeriode.js`. Il ne
 * décide ici que ce qui est montré — quelle période, quelles natures, quel
 * sujet, et si le détail est ouvert.
 *
 * Maquette validée le 09/09/2026 (artefact « Ce qu'il a dit, en trois
 * formes »), forme A. Trois entrées croisées, de la plus large à la plus fine :
 *
 *   période politique  →  nature de l'intervention  →  sujet  →  le détail
 *
 * DEUX ÉCHELLES, ET C'EST VOULU. Les COMPTEURS suivent la sélection : ils
 * disent « combien reste-t-il sous ce filtre », donc ils sont le dénominateur
 * de ce qu'on lit et jamais un palmarès (§2 règle 7). Les BARRES gardent le
 * plafond de la fiche, parce qu'elles servent à comparer deux périodes entre
 * elles — un filtre retire de la masse, il ne redimensionne pas. Sur « toutes
 * les périodes », le plafond change et le libellé le dit : une barre
 * d'ensemble ne se compare pas à une barre de période.
 *
 * LE DÉTAIL EST FERMÉ TANT QU'AUCUN SUJET N'EST CHOISI. Ouvrir 3 963
 * interventions d'emblée, c'est publier un mur où le lecteur ne cherche rien —
 * et la première phrase visible deviendrait, de fait, une phrase mise en avant,
 * ce qu'aucune règle ne nous autorise à faire (§2 règle 1).
 */
import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { formatNumber } from '../utils/lecture';
import { libellePosition, TYPES_INTERVENTION } from '../utils/profilCandidat';
import { SUJET_NON_PUBLIE, sujetsDuLot } from '../utils/parolesParPeriode';
import NavigationPeriodes from './NavigationPeriodes';
import './ParolesParPeriode.css';

const jour = (d) => (d ? `${d.slice(8, 10)}/${d.slice(5, 7)}/${d.slice(0, 4)}` : '');
const mois = (d) => (d ? `${d.slice(0, 4)}/${d.slice(5, 7)}` : '');

const SUJETS_REPLIES = 10;
const PAS_DE_FIL = 25;

/* Le titre nomme CE QU'ON SAIT. Un repère non publié est écrit, jamais escamoté
 * ni comblé par la période voisine — mêmes formules que « Ce qu'il a voté ». */
function titreDePeriode(periode) {
  if (!periode.banc && !periode.gouvernement) return 'Repère non publié';
  const banc = periode.banc ? libellePosition(periode.banc) : 'banc non publié';
  const gouvernement = periode.gouvernement
    ? `gouvernement ${periode.gouvernement}`
    : 'gouvernement non publié';
  return `${banc} · ${gouvernement}`.replace(/^./, (c) => c.toUpperCase());
}

function libelleCourtDePeriode(periode) {
  const banc = periode.banc ? libellePosition(periode.banc) : 'banc non publié';
  return periode.gouvernement ? `${banc} · ${periode.gouvernement}` : banc;
}

/* Les natures, dans le vocabulaire que la fiche emploie déjà — une seule table
 * de libellés pour ce champ, ici comme dans « En bref ». Un type que la table
 * ne connaît pas garde sa clé brute : un libellé inventé serait pire. */
function naturesDuLot(interventions) {
  const compte = new Map();
  for (const i of interventions) compte.set(i.type, (compte.get(i.type) || 0) + 1);

  const connus = new Set(TYPES_INTERVENTION.flatMap((t) => t.cles));
  const lignes = TYPES_INTERVENTION.map(({ cles, label }) => ({
    cle: cles.join('+'),
    cles,
    label,
    n: cles.reduce((s, c) => s + (compte.get(c) || 0), 0),
  }));
  for (const [cle] of compte) {
    if (!connus.has(cle)) lignes.push({ cle, cles: [cle], label: cle || 'Nature non publiée', n: compte.get(cle) });
  }
  return lignes.filter((l) => l.n > 0 || connus.has(l.cles[0]));
}

function Intervention({ i }) {
  return (
    <li className="pp-item">
      <div className="pp-quand">
        {jour(i.date)}
        <em>{i.libelleNature}</em>
      </div>
      <div className="pp-quoi">
        <p className="pp-chemin">
          {i.chemin ? (
            <>
              <b>{i.sujet}</b>
              {i.reste && <span className="pp-reste"> › {i.reste}</span>}
            </>
          ) : (
            <span className="pp-reste">{SUJET_NON_PUBLIE} par la source</span>
          )}
        </p>
        {i.fonction && (
          <p className="pp-qualite">
            prononcé comme <b>{i.fonction}</b>
          </p>
        )}
        {i.verbatim ? (
          <blockquote className="pp-verbatim">{i.verbatim}</blockquote>
        ) : (
          <p className="pp-sans-verbatim">
            {i.themeSeul
              ? 'Collecte au thème seul : le verbatim n’a pas été rapporté. Ce n’est pas un silence de la personne.'
              : 'Le compte rendu ne porte pas de verbatim pour cette entrée.'}
          </p>
        )}
        {i.sourceUrl && (
          <a className="pp-source" href={i.sourceUrl} target="_blank" rel="noreferrer">
            Source · Assemblée nationale
          </a>
        )}
      </div>
    </li>
  );
}

export default function ParolesParPeriode({ periodes, plafondPeriode, plafondEnsemble, couverture }) {
  const [index, setIndex] = useState(periodes.length - 1);
  const [natures, setNatures] = useState(() => new Set());
  const [sujet, setSujet] = useState(null);
  const [tousSujets, setTousSujets] = useState(false);
  const [limite, setLimite] = useState(PAS_DE_FIL);

  const tout = index === null;
  const lot = useMemo(
    () => (tout ? periodes.flatMap((p) => p.interventions) : periodes[index].interventions),
    [periodes, index, tout],
  );

  const parNature = useMemo(() => naturesDuLot(lot), [lot]);
  const clesRetenues = useMemo(() => {
    const s = new Set();
    for (const l of parNature) if (natures.has(l.cle)) for (const c of l.cles) s.add(c);
    return s;
  }, [parNature, natures]);

  const passeNature = (i) => clesRetenues.size === 0 || clesRetenues.has(i.type);

  /* Chaque facette est comptée sous la sélection de l'AUTRE. C'est ce qui fait
     du chiffre un dénominateur, et non un classement. */
  const naturesAffichees = useMemo(() => {
    const sousSujet = lot.filter((i) => !sujet || (i.sujet || SUJET_NON_PUBLIE) === sujet);
    return naturesDuLot(sousSujet)
      .map((l) => ({ ...l, actif: natures.has(l.cle) }))
      .sort((a, b) => b.n - a.n || a.label.localeCompare(b.label, 'fr'));
  }, [lot, sujet, natures]);

  const sujets = useMemo(() => sujetsDuLot(lot.filter(passeNature)), [lot, clesRetenues]);
  const plafond = tout ? plafondEnsemble : plafondPeriode;

  const visibles = useMemo(
    () =>
      lot
        .filter((i) => passeNature(i) && sujet && (i.sujet || SUJET_NON_PUBLIE) === sujet)
        .slice()
        .reverse(),
    [lot, clesRetenues, sujet],
  );

  const libelleNature = (type) =>
    TYPES_INTERVENTION.find((t) => t.cles.includes(type))?.label ?? type ?? 'Nature non publiée';

  const changerPeriode = (i) => {
    setIndex(i);
    setSujet(null);
    setTousSujets(false);
    setLimite(PAS_DE_FIL);
  };

  const basculerNature = (cle) => {
    setNatures((s) => {
      const n = new Set(s);
      if (n.has(cle)) n.delete(cle);
      else n.add(cle);
      return n;
    });
    setLimite(PAS_DE_FIL);
  };

  const periodeCourante = tout ? null : periodes[index];
  const sujetsVus = tousSujets ? sujets : sujets.slice(0, SUJETS_REPLIES);

  return (
    <div className="pp">
      <NavigationPeriodes
        periodes={periodes}
        index={index}
        onIndex={changerPeriode}
        poids={(p) => p.interventions.length}
        libelle={libelleCourtDePeriode}
        unite="interventions"
        uniteSingulier="intervention"
        avecTout
      />

      <div className="cp-carte cp-bloc pp-cadre">
        <div className="pp-tete">
          <h3 className="pp-titre">
            {tout ? 'Toutes les périodes' : titreDePeriode(periodeCourante)}
          </h3>
          <span className="pp-quand-periode">
            {tout
              ? `${mois(periodes[0].debut)} → ${mois(periodes[periodes.length - 1].fin)} · ${formatNumber(periodes.length)} périodes`
              : `${mois(periodeCourante.debut)} → ${mois(periodeCourante.fin)}${
                  periodeCourante.groupes.length ? ` · ${periodeCourante.groupes.join(', ')}` : ''
                }`}
          </span>
        </div>

        <div className="pp-facette">
          <span className="pp-facette-quoi">
            Nature <i>— {formatNumber(naturesAffichees.reduce((s, l) => s + l.n, 0))} sous la sélection</i>
          </span>
          <div className="pp-chips">
            {naturesAffichees.map((l) => (
              <button
                type="button"
                key={l.cle}
                className="pp-chip"
                aria-pressed={l.actif}
                disabled={l.n === 0}
                onClick={() => basculerNature(l.cle)}
              >
                {l.label} <span className="pp-chip-n">{formatNumber(l.n)}</span>
              </button>
            ))}
            {natures.size > 0 && (
              <button type="button" className="pp-raz" onClick={() => setNatures(new Set())}>
                Tout retirer
              </button>
            )}
          </div>
        </div>

        <div className="pp-facette">
          <span className="pp-facette-quoi">
            Sujet{' '}
            <i>
              — {formatNumber(sujets.length)} sous la sélection ·{' '}
              {tout
                ? 'échelle propre à l’ensemble, non comparable à celle d’une période'
                : 'échelle commune aux périodes'}
            </i>
          </span>
          {sujets.length ? (
            <ul className="pp-sujets">
              {sujetsVus.map((s) => (
                <li key={s.sujet} className={s.sujet === sujet ? 'pp-sujet--actif' : undefined}>
                  <button
                    type="button"
                    onClick={() => {
                      setSujet(s.sujet === sujet ? null : s.sujet);
                      setLimite(PAS_DE_FIL);
                    }}
                    aria-pressed={s.sujet === sujet}
                  >
                    <span className="pp-sujet-nom">{s.sujet}</span>
                    <span
                      className="pp-sujet-barre"
                      style={{ width: `${Math.max(1, (s.n / plafond) * 100)}%` }}
                    />
                  </button>
                  <span className="pp-sujet-n">{formatNumber(s.n)}</span>
                </li>
              ))}
              {sujets.length > SUJETS_REPLIES && (
                <li className="pp-sujets-plus">
                  <button type="button" onClick={() => setTousSujets((v) => !v)}>
                    {tousSujets
                      ? 'Réduire la liste'
                      : `Voir les ${formatNumber(sujets.length - SUJETS_REPLIES)} autres sujets`}
                  </button>
                </li>
              )}
            </ul>
          ) : (
            <p className="pp-vide">Aucun sujet publié sous cette sélection.</p>
          )}
        </div>
      </div>

      <div className="pp-fil">
        {!sujet ? (
          <p className="pp-invite">
            <b>Choisissez un sujet</b> pour lire ce qui a été dit —{' '}
            {formatNumber(lot.filter(passeNature).length)} interventions sous la sélection.
          </p>
        ) : (
          <>
            <div className="pp-fil-tete">
              <span className="pp-fil-quoi">
                {sujet} — {formatNumber(visibles.length)} intervention
                {visibles.length > 1 ? 's' : ''}
              </span>
              <button type="button" className="pp-raz" onClick={() => setSujet(null)}>
                Toute la période
              </button>
            </div>
            {visibles.length ? (
              <ul className="pp-liste">
                {visibles.slice(0, limite).map((i) => (
                  <Intervention
                    key={i.id ?? `${i.date}-${i.chemin}`}
                    i={{
                      ...i,
                      libelleNature: libelleNature(i.type),
                      reste: i.chemin
                        ? i.chemin
                            .split('>')
                            .map((s) => s.trim())
                            .filter((s) => s && s !== i.sujet)
                            .join(' › ')
                        : null,
                    }}
                  />
                ))}
              </ul>
            ) : (
              <p className="pp-vide">
                Aucune intervention sous ce croisement — le croisement est vide, pas le corpus.
              </p>
            )}
            {visibles.length > limite && (
              <button
                type="button"
                className="pp-plus"
                onClick={() => setLimite((n) => n + PAS_DE_FIL)}
              >
                Voir {formatNumber(Math.min(PAS_DE_FIL, visibles.length - limite))} interventions de
                plus — {formatNumber(visibles.length - limite)} restantes
              </button>
            )}
          </>
        )}
      </div>

      <p className="cp-note pp-couverture">
        <b>Ce que cette figure ne sait pas.</b> Sur ses {formatNumber(couverture.total)}{' '}
        interventions collectées, {formatNumber(couverture.sujet)} portent l’intitulé officiel sous
        lequel elles ont été prononcées, {formatNumber(couverture.verbatim)} le verbatim du compte
        rendu et {formatNumber(couverture.fonction)} la qualité de l’orateur — que la source ne
        publie que pour une fonction particulière, ministre ou rapporteur. Son absence est un
        silence de la source, jamais un fait sur la personne.
        {couverture.themeSeul > 0 && (
          <>
            {' '}
            {formatNumber(couverture.themeSeul)} d’entre elles relèvent d’un régime de collecte
            déclaré, au thème seul : la date, la nature et le thème, et rien d’autre.
          </>
        )}
        {couverture.datees < couverture.total && (
          <>
            {' '}
            {formatNumber(couverture.total - couverture.datees)} ne portent pas de date exploitable
            et restent hors du découpage : sans date, ni le banc ni le gouvernement en place ne se
            lisent.
          </>
        )}
      </p>

      <p className="pp-methodo">
        <Link to="/methodologie#interventions">
          Comment ces interventions sont collectées, datées et qualifiées
        </Link>
      </p>
    </div>
  );
}
