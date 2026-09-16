import sourcesConfig from '../data/sources.config';
import './landing/landing.css';

// Les cartes des sources, repliées : nom visible, cadence, contenu et licence
// derrière le clic. Toutes les valeurs viennent de sources.config.js (repris
// d'AGENTS.md §7 et du README) — rien n'est réinventé ici. Rendues par l'accueil
// et par /sources (#951), sous le schéma qui dit ce que chaque source apporte.
export default function CartesSources() {
  return (
    <div className="sources-grid">
      {sourcesConfig.map((source) => (
        <details className="source-card" key={source.id}>
          <summary className="source-card-summary">
            <span className="source-card-name">{source.nom}</span>
            {source.couverturePeriode && (
              <span className="source-card-badge">Couverture limitée</span>
            )}
          </summary>
          <div className="source-card-body">
            <p className="source-card-row">
              <span className="source-card-label">Cadence de mise à jour</span>
              {source.cadenceMiseAJour}
            </p>
            <p className="source-card-row">
              <span className="source-card-label">Contenu couvert</span>
              {source.contenuCouvert}
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
              <p className="source-card-row">
                <span className="source-card-label">Période de couverture limitée</span>
                {source.couverturePeriode}
              </p>
            )}
          </div>
        </details>
      ))}
    </div>
  );
}
