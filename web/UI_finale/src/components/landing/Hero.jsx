import { Fragment } from 'react';
import { Link } from 'react-router-dom';
import { DEFAULT_CANDIDATE_ID, DEFAULT_GROUP_ID, DEFAULT_GOVERNMENT_ID } from '../../data';
import './landing.css';

function CheckIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
      <path d="M2.5 9.5L9 3" stroke="#14151A" strokeWidth="1.8" strokeLinecap="round" />
      <path d="M5.7 4.8l1.4 1.4" stroke="#14151A" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

function ArrowIcon() {
  return (
    <svg
      className="hero-pipeline-arrow"
      width="18"
      height="12"
      viewBox="0 0 18 12"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M0 6h15M10 1l5 5-5 5"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

// Exemple fictif : aucune donnée candidate réelle (AGENTS.md §2).
const PIPELINE_STEPS = [
  {
    key: 'donnee-brute',
    label: 'Donnée brute',
    content: <code className="hero-pipeline-sample">{'{ vote: "pour", texte: "PJL exemple" }'}</code>,
  },
  {
    key: 'fait-verifie',
    label: 'Fait vérifié',
    content: (
      <span className="hero-pipeline-verified">
        <CheckIcon /> Source vérifiée
      </span>
    ),
  },
  {
    key: 'fiche-candidat',
    label: 'Profil',
    content: (
      <span className="hero-pipeline-card">
        <span className="hero-pipeline-avatar" aria-hidden="true" />
        Prénom Nom (exemple)
      </span>
    ),
  },
];

// Hero (#143) : promesse factuelle + micro-animation du pipeline donnée brute
// → fait vérifié → fiche candidat. Le CTA final (candidat/groupe/gouvernement,
// ex-FinalCta) est intégré directement ici plutôt que répété dans une section
// dédiée en bas de page, pour éviter un unique bouton perdu en haut et un
// second bloc de CTA redondant en bas (retour utilisateur du 2026-08-15).
export default function Hero() {
  return (
    <section className="landing-section landing-hero" aria-label="Présentation">
      <h1>L'explorateur neutre et sourcé des parcours parlementaires pour la présidentielle 2027.</h1>
      <p>Des faits sourcés, sans note ni classement — à consulter par candidat, par groupe ou par gouvernement.</p>

      <div className="hero-pipeline">
        <p className="hero-pipeline-caption">Le concept</p>
        <div className="hero-pipeline-steps">
          {PIPELINE_STEPS.map((step, index) => (
            <Fragment key={step.key}>
              <div className="hero-pipeline-step" style={{ animationDelay: `${index * 2}s` }}>
                <span className="hero-pipeline-marker" aria-hidden="true" />
                <span className="hero-pipeline-label">{step.label}</span>
                {step.content}
              </div>
              {index < PIPELINE_STEPS.length - 1 && <ArrowIcon />}
            </Fragment>
          ))}
        </div>
      </div>

      <div className="hero-ready">
        <h2>Prêt à explorer ?</h2>
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
      </div>
    </section>
  );
}
