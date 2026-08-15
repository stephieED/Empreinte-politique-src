import { Link } from 'react-router-dom';
import sourcesConfig from '../../data/sources.config';
import { DEFAULT_CANDIDATE_ID } from '../../data';
import './landing.css';

// Contenu éditorial : toutes les infos de licence/cadence viennent de
// sources.config.js (lui-même repris d'AGENTS.md §7 et README.md) — rien
// n'est réinventé ici. Chaque source est un <details> replié par défaut
// (seul le nom, et le badge de couverture limitée le cas échéant, restent
// visibles ; la cadence de mise à jour rejoint le contenu couvert/la
// licence derrière le clic — retour utilisateur du 2026-08-15, page perçue
// comme trop chargée). Même pattern que Faq.jsx (accessible clavier/
// tactile nativement, contrairement à un simple :hover).
export default function SourcesFreshness() {
  return (
    <section className="landing-section" aria-label="Sources et fraîcheur des données">
      <h2>Sources &amp; fraîcheur des données</h2>
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
      <p className="sources-freshness-cta">
        <Link to={`/candidats/${DEFAULT_CANDIDATE_ID}`}>Voir la fraîcheur en détail →</Link>
      </p>
    </section>
  );
}
