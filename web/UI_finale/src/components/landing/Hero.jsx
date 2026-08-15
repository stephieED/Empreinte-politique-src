import { Link } from 'react-router-dom';
import { DEFAULT_CANDIDATE_ID, DEFAULT_GROUP_ID, DEFAULT_GOVERNMENT_ID } from '../../data';
import './landing.css';

// Squelette : contenu éditorial et style final traités dans une sub-issue dédiée.
export default function Hero() {
  return (
    <section className="landing-section landing-hero" aria-label="Présentation">
      <h1>[Placeholder] Empreinte politique</h1>
      <p>[Placeholder] Des faits sourcés, sans note de performance ni classement.</p>
      <div className="landing-cta-group">
        <Link className="landing-cta" to={`/candidats/${DEFAULT_CANDIDATE_ID}`}>
          Explorer un candidat
        </Link>
        <Link className="landing-cta" to={`/groupes/${DEFAULT_GROUP_ID}`}>
          Explorer un groupe
        </Link>
        <Link className="landing-cta" to={`/gouvernements/${DEFAULT_GOVERNMENT_ID}`}>
          Explorer un gouvernement
        </Link>
      </div>
    </section>
  );
}
