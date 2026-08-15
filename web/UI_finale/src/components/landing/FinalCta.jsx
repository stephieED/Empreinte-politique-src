import { Link } from 'react-router-dom';
import { DEFAULT_CANDIDATE_ID, DEFAULT_GROUP_ID, DEFAULT_GOVERNMENT_ID } from '../../data';
import './landing.css';

export default function FinalCta() {
  return (
    <section className="landing-section" aria-label="Accéder à l'outil">
      <h2>Prêt à explorer ?</h2>
      <p>Des faits sourcés, sans note ni classement — à consulter par candidat, par groupe ou par gouvernement.</p>
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
