import { Link } from 'react-router-dom';
import Brand from './Brand';
import '../styles/shell.css';
import './StaticPage.css';

// Page statique partagée (Méthodologie, Mentions légales) : bannière + sections,
// hors ExplorerLayout — ces pages n'ont pas de candidat/groupe sélectionné, les
// bandeaux Groupes/Gouvernements/Candidats n'ont donc pas de sens ici.
export default function StaticPage({ eyebrow, title, tagline, updated, sections }) {
  return (
    <div className="app-shell">
      <div className="static-page">
        <Brand />
        <main className="static-main">
          <p className="static-breadcrumb">
            <Link to="/">← Retour à l'accueil</Link>
          </p>

          <div className="static-banner">
            {eyebrow && <span className="static-banner-tag">{eyebrow}</span>}
            <h1>{title}</h1>
            {tagline && <p>{tagline}</p>}
          </div>

          {updated && <p className="static-updated">{updated}</p>}

          <div className="static-sections">
            {sections.map((section) => (
              <section className="static-card" key={section.heading}>
                <h2>{section.heading}</h2>
                {section.body}
              </section>
            ))}
          </div>
        </main>
      </div>
    </div>
  );
}
