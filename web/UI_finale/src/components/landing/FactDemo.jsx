import { useId, useState } from 'react';
import './landing.css';
import demoFact from '../../data/demoFact.fixture';

function VerifiedIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
      <path d="M2.5 9.5L9 3" stroke="#14151A" strokeWidth="1.8" strokeLinecap="round" />
      <path d="M5.7 4.8l1.4 1.4" stroke="#14151A" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

// Démo interactive neutre (issue #145) : un seul fait fictif exploré à la
// fois, jamais deux "candidats" comparés. Le bouton natif gère déjà le clic
// et le clavier (Enter/Space, focus visible) sans handler dédié.
export default function FactDemo() {
  const [revealed, setRevealed] = useState(false);
  const sourceId = useId();
  const { acteur, mandat, fait, source } = demoFact;

  return (
    <section className="landing-section fact-demo" aria-label="Exemple de fait sourcé">
      <h2>Un fait, une source</h2>
      <p>
        Exemple fictif, à but illustratif — aucun candidat réel. Chaque fait publié sur Empreinte
        politique se vérifie de la même façon : un clic suffit pour révéler sa source primaire.
      </p>

      <div className="fact-demo-card">
        <span className="fact-demo-kicker">{mandat}</span>
        <div className="fact-demo-position">
          <span className="fact-demo-dot" style={{ background: fait.color }} />
          <span className="fact-demo-position-label" style={{ color: fait.color }}>
            {fait.positionLabel}
          </span>
        </div>
        <p className="fact-demo-titre">
          <strong>{acteur}</strong> — {fait.texte}
        </p>
        <p className="fact-demo-meta">{fait.date}</p>

        <button
          type="button"
          className="fact-demo-toggle"
          aria-expanded={revealed}
          aria-controls={sourceId}
          onClick={() => setRevealed((v) => !v)}
        >
          {revealed ? 'Masquer la source primaire' : 'Voir la source primaire'}
        </button>

        <div id={sourceId} className="fact-demo-source" hidden={!revealed} aria-live="polite">
          <span className="fact-demo-badge">
            <VerifiedIcon /> Source vérifiée
          </span>
          <dl className="fact-demo-source-details">
            <div>
              <dt>Source</dt>
              <dd>{source.label}</dd>
            </div>
            <div>
              <dt>URL (exemple fictif)</dt>
              <dd className="fact-demo-url">{source.url}</dd>
            </div>
            <div>
              <dt>Synchronisée le</dt>
              <dd>{source.syncedAt}</dd>
            </div>
          </dl>
          <p className="fact-demo-note">
            Exemple fictif à but pédagogique — aucune donnée candidate réelle.
          </p>
        </div>
      </div>
    </section>
  );
}
