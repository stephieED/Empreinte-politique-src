import { Link } from 'react-router-dom';
import Brand from '../components/Brand';
import FriseCouverture from '../components/FriseCouverture';
import PiedDeSite from '../components/PiedDeSite';
import { useAsyncData } from '../hooks/useAsyncData';
import { loadCouverture } from '../data';
import '../styles/shell.css';
import '../components/StaticPage.css';
import './CoveragePage.css';

/* CE QUE CONTIENT CE CORPUS — la page commune aux 59 fiches.
 *
 * POURQUOI ELLE EXISTE. Les deux tiers de « ce qu'on n'a pas pu lire » étaient
 * recopiés à l'identique sur chaque fiche : les bornes de source, les
 * rapprochements qui n'aboutissent pas, les institutions non couvertes. Rien de
 * tout cela ne parle du candidat affiché. La page les dit UNE FOIS, pour les
 * trois populations publiées, et la fiche ne garde que ce qui est vrai de cette
 * personne-là.
 *
 * AUCUN CHIFFRE N'EST ÉCRIT ICI. Effectifs, bornes, noms des fiches où une
 * liste manque : tout vient de `public/data/couverture.json`, mesuré au build
 * par `scripts/couverture-corpus.mjs`. Un chiffre recopié dans du JSX est un
 * chiffre qui aura vieilli au run suivant.
 */

const nb = (n) => n.toLocaleString('fr-FR').replace(/ | /g, ' ');
const jour = (d) => (d ? d.split('-').reverse().join('.') : '');

export default function CoveragePage() {
  const { data, loading, error } = useAsyncData(loadCouverture, []);

  return (
    <div className="app-shell">
      <div className="static-page">
        <Brand />
        <main className="static-main cv-main">
          <p className="static-breadcrumb">
            <Link to="/">← Retour à l'accueil</Link>
          </p>

          <div className="static-banner">
            <span className="static-banner-tag">Vue d'ensemble</span>
            <h1>Ce que contient ce corpus</h1>
            <p>Commun à toutes les fiches — candidats, gouvernements, groupes parlementaires.</p>
          </div>

          {loading && <p className="cv-etat">Chargement…</p>}
          {error && (
            <p className="cv-etat">
              La couverture n'a pas pu être chargée. Rien n'est affiché plutôt qu'approché.
            </p>
          )}

          {data && (
            <>
              <p className="static-updated">
                {nb(data.reperes.fichesPubliees)} fiches publiées — {nb(data.reperes.candidats)}{' '}
                candidats, {nb(data.reperes.gouvernements)} gouvernements, {nb(data.reperes.groupes)}{' '}
                groupes. Collecte du {jour(data.collecteLe)}.
              </p>

              <section className="static-card cv-card" id="frise">
                <h2>Ce que le dépôt porte, et depuis quand</h2>
                <p className="cv-sous">
                  Une teinte par population — candidats, gouvernements, groupes. Le{' '}
                  <b>jaune</b> marque ce qui n'est pas collecté, la <b>hachure</b> les périodes où
                  rien n'est publié. Chaque ligne se déplie sur ses champs.
                </p>
                <FriseCouverture couverture={data} />
                <p className="cv-note">
                  Les blancs entre deux segments sont des mois sans rien : le plus souvent des
                  mois sans séance. Ils ne disent pas qu'une donnée manque.
                </p>
              </section>

              <section className="static-card cv-card" id="manquants">
                <h2>Ce qui manque, et sur quelles fiches</h2>
                <p className="cv-sous">
                  Le dénominateur n'est pas le nombre de fiches : une fiche sans mandat à
                  l'Assemblée n'a pas de vote à porter, et sa liste vide est un fait sur elle.
                  Rapporté aux <b>{data.couvertureFiches.siege} fiches qui y ont siégé</b>, un
                  manquant se nomme — et celui dont le mandat est antérieur à la borne n'est pas un
                  trou, l'autre si.
                </p>
                <TableManquants couverture={data.couvertureFiches} />
              </section>

              <p className="cv-renvoi">
                Ce que ces bornes veulent dire, et pourquoi elles existent :{' '}
                <Link to="/methodologie#couverture">la méthodologie</Link>.
              </p>
            </>
          )}
        </main>
        <PiedDeSite />
      </div>
    </div>
  );
}

function TableManquants({ couverture }) {
  return (
    <div className="cv-tableau">
      <table className="cv-grille">
        <thead>
          <tr>
            <th>Liste</th>
            <th>Fiches qui en portent</th>
            <th>Manquent, mandat antérieur à la borne</th>
            <th>Manquent, et c'est un trou</th>
          </tr>
        </thead>
        <tbody>
          {couverture.listes.map((l) => (
            <tr key={l.cle}>
              <td className="cv-liste">
                {l.titre}
                <small>{l.borne ? `publiée à partir du ${jour(l.borne)}` : 'aucune borne déclarée'}</small>
              </td>
              <td>
                <b>{l.porte}</b> / {couverture.siege}
                <span className="cv-jauge">
                  <i style={{ width: `${(l.porte / couverture.siege) * 100}%` }} />
                </span>
              </td>
              {/* NOMMÉS, JAMAIS SEULEMENT COMPTÉS (#510) : une fiche dont la
                  liste est vide parce que son mandat précède la borne ne se
                  confond pas avec une fiche où la donnée manque sans cause
                  connue. Deux absences, deux colonnes. */}
              <td>{l.horsBorne.length ? l.horsBorne.join(', ') : '—'}</td>
              <td>
                {l.trous.length ? (
                  <span className="cv-trou">{l.trous.join(', ')}</span>
                ) : (
                  <span className="cv-aucun">aucun</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
