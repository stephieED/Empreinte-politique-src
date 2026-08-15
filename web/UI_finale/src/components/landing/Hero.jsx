import { Fragment } from 'react';
import { Link } from 'react-router-dom';
import { DEFAULT_CANDIDATE_ID } from '../../data';
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
    label: 'Fiche candidat',
    content: (
      <span className="hero-pipeline-card">
        <span className="hero-pipeline-avatar" aria-hidden="true" />
        Prénom Nom (exemple)
      </span>
    ),
  },
];

// Hero (#143) : promesse factuelle + CTA principal + micro-animation du pipeline
// donnée brute → fait vérifié → fiche candidat. Le CTA principal reste unique
// et cible la fiche candidat, cohérent avec la dernière étape de l'animation ;
// les liens groupe/gouvernement restent réservés à la section CTA finale de la
// page (#139, "Mise à jour" du 2026-08-14) pour ne pas surcharger le Hero.
export default function Hero() {
  return (
    <section className="landing-section landing-hero" aria-label="Présentation">
      <h1>Le mandat de chaque candidat, retracé jusqu'à sa source.</h1>
      <p>
        Empreinte politique rassemble mandats, votes, textes et interventions à partir des
        données publiques de l'Assemblée nationale, du Sénat et du Parlement européen — chaque
        fait relié à sa source primaire. Aucun score, aucun classement.
      </p>
      <div className="landing-cta-group">
        <Link className="landing-cta" to={`/candidats/${DEFAULT_CANDIDATE_ID}`}>
          Explorer une fiche candidat
        </Link>
      </div>

      <div className="hero-pipeline">
        <p className="hero-pipeline-caption">De la donnée brute à la fiche candidat, en trois étapes :</p>
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
    </section>
  );
}
