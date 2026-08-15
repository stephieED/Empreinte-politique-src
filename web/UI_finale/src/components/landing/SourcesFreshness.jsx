import { Link } from 'react-router-dom';
import sourcesConfig from '../../data/sources.config';
import { DEFAULT_CANDIDATE_ID } from '../../data';
import './landing.css';

// Contenu éditorial : toutes les infos de licence/cadence viennent de
// sources.config.js (lui-même repris d'AGENTS.md §7 et README.md) — rien
// n'est réinventé ici. L'info-bulle de licence se révèle au survol ou au
// focus clavier du bouton dédié (aria-describedby), sans script.
export default function SourcesFreshness() {
  return (
    <section className="landing-section" aria-label="Sources et fraîcheur des données">
      <h2>Sources &amp; fraîcheur des données</h2>
      <p>
        On vous dit toujours d'où viennent les faits publiés, et depuis quand. Chaque source
        publique utilisée par Empreinte politique est listée ci-dessous, avec ce qu'elle couvre,
        sa cadence de mise à jour et sa licence de réutilisation.
      </p>
      <div className="sources-grid">
        {sourcesConfig.map((source) => (
          <article className="source-card" key={source.id}>
            <p className="source-card-name">{source.nom}</p>
            <p className="source-card-row">
              <span className="source-card-label">Contenu couvert</span>
              {source.contenuCouvert}
            </p>
            <p className="source-card-row">
              <span className="source-card-label">Cadence de mise à jour</span>
              {source.cadenceMiseAJour}
            </p>
            <p className="source-card-row source-card-license">
              <span className="source-card-label">Licence</span>
              {source.licence}
              <button
                type="button"
                className="source-license-info"
                aria-describedby={`${source.id}-licence-tooltip`}
                aria-label={`Ce qu'implique la licence ${source.licence} pour ${source.nom}`}
              >
                ?
              </button>
              <span role="tooltip" id={`${source.id}-licence-tooltip`} className="source-license-tooltip">
                {source.implication}
              </span>
            </p>
            {source.couverturePeriode && (
              <p className="source-card-badge-row">
                <span className="source-card-badge">Période de couverture limitée</span>
                <span className="source-card-row">{source.couverturePeriode}</span>
              </p>
            )}
          </article>
        ))}
      </div>
      <p className="sources-freshness-cta">
        La date de dernière synchronisation de chaque source est rattachée aux faits qu'elle
        documente, directement sur les fiches candidats, groupes et gouvernements — aucune valeur
        n'est recopiée ici.{' '}
        <Link to={`/candidats/${DEFAULT_CANDIDATE_ID}`}>Voir la fraîcheur en détail →</Link>
      </p>
    </section>
  );
}
