import { Link } from 'react-router-dom';
import { useAsyncData } from '../../hooks/useAsyncData';
import { loadCouverture } from '../../data';

/* CE QUE NOUS LISONS, ET DEPUIS QUAND — la frise de /couverture ramenée à une
 * borne par institution, en tête de « Sources & fraîcheur des données ».
 *
 * POURQUOI SUR L'ACCUEIL. Un candidat dont la carrière précède ce que les
 * sources publient voit une partie de son parcours absente de sa fiche, et le
 * lecteur ne doit pas avoir à ouvrir /couverture pour comprendre pourquoi
 * (relecture du 11/09/2026). Pas de détail par liste : il vit sur /couverture.
 *
 * AUCUN CHIFFRE NI AUCUN NOM N'EST ÉCRIT ICI. Les bornes et les fiches nommées
 * viennent de `couverture.json` (`accueil`), calculé au build. */

const AXE_DEBUT = 2000;
const GRADUATIONS = [2000, 2005, 2010, 2015, 2020, 2025];

export default function CouvertureAccueil() {
  const { data } = useAsyncData(loadCouverture, []);
  // Rien plutôt qu'une figure approchée : sans la projection, le bloc se tait
  // et les cartes de sources suivent (§2 règle 5).
  if (!data?.accueil) return null;
  const { institutions, horsCouverture } = data.accueil;
  const fin = Number(data.collecteLe.slice(0, 4)) + (Number(data.collecteLe.slice(5, 7)) - 1) / 12;
  const x = (iso) => {
    const a = Number(iso.slice(0, 4)) + (Number(iso.slice(5, 7)) - 1) / 12;
    return Math.min(100, Math.max(0, ((a - AXE_DEBUT) / (fin - AXE_DEBUT)) * 100));
  };
  const fiches = (liste) => liste.map((p, i) => (
    <span key={p.id}>
      {i > 0 && ', '}
      <Link to={`/candidats/${p.id}`}>{p.nom}</Link>
    </span>
  ));

  return (
    <div className="ca">
      <p className="ca-tete">
        <b>Ce que nous lisons, et depuis quand</b>
        <span>collecte du {data.collecteLe.split('-').reverse().join('.')}</span>
      </p>
      <div className="ca-grille">
        <span />
        <div className="ca-axe" aria-hidden="true">
          {GRADUATIONS.map((g) => (
            <span className={g % 10 ? 'ca-axe-mineure' : undefined} key={g} style={{ left: `${x(`${g}-01-01`)}%` }}>{g}</span>
          ))}
        </div>
        <span />
        {institutions.map((i) => (
          <div className="ca-ligne" key={i.cle}>
            <span className="ca-nom">{i.titre}</span>
            <div className="ca-rail">
              {i.hachureJusqua && <span className="ca-hors" style={{ width: `${x(i.hachureJusqua)}%` }} />}
              <span className={`ca-plein ca-plein--${i.cle}`} style={{ left: `${x(i.debut)}%` }} />
            </div>
            <span className="ca-depuis">depuis {i.debut.slice(0, 4)}</span>
          </div>
        ))}
        <div className="ca-ligne">
          <span className="ca-nom">Sénat</span>
          <div className="ca-rail"><span className="ca-nonc" /></div>
          <span className="ca-depuis">non <small>collecté</small></span>
        </div>
        <div className="ca-ligne">
          <span className="ca-nom">Mandats locaux</span>
          <div className="ca-rail"><span className="ca-hors" style={{ width: '100%' }} /></div>
          <span className="ca-depuis">aucune <small>source</small></span>
        </div>
      </div>
      <p className="ca-legende">
        <span><i className="ca-cle ca-cle--collecte" />Données collectées</span>
        <span><i className="ca-cle ca-cle--nonc" />Non collectées</span>
        <span><i className="ca-cle ca-cle--hors" />Non publiées par la source</span>
      </p>
      {(horsCouverture.senat.length > 0 || horsCouverture.sansMandat.length > 0) && (
        <div className="ca-hc">
          <p className="ca-hc-titre">Les mandats hors couverture</p>
          <dl>
            {horsCouverture.senat.length > 0 && (
              <div>
                <dt>Mandat au Sénat collecté mais non exploitable</dt>
                <dd>{fiches(horsCouverture.senat)}</dd>
              </div>
            )}
            {horsCouverture.sansMandat.length > 0 && (
              <div>
                <dt>Mandats locaux et autres</dt>
                <dd>{fiches(horsCouverture.sansMandat)}</dd>
              </div>
            )}
          </dl>
        </div>
      )}
    </div>
  );
}
