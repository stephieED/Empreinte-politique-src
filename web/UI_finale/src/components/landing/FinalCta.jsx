import { Link } from 'react-router-dom';
import { DEFAULT_CANDIDATE_ID, DEFAULT_GROUP_ID, DEFAULT_GOVERNMENT_ID } from '../../data';
import './landing.css';

// Squelette : contenu éditorial et style final traités dans une sub-issue dédiée.
export default function FinalCta() {
  return (
    <section className="landing-section" aria-label="Accéder à l'outil">
      <h2>[Placeholder] Prêt à explorer ?</h2>
      <div className="landing-cta-group">
        <Link className="landing-cta" to={`/candidats/${DEFAULT_CANDIDATE_ID}`}>
          Voir un profil candidat
        </Link>
        <Link className="landing-cta" to={`/groupes/${DEFAULT_GROUP_ID}`}>
          Voir un profil de groupe
        </Link>
        <Link className="landing-cta" to={`/gouvernements/${DEFAULT_GOVERNMENT_ID}`}>
          Voir un profil de gouvernement
        </Link>
      </div>
    </section>
  );
}
