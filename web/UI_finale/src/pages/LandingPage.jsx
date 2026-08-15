import { Link } from 'react-router-dom';
import Brand from '../components/Brand';
import Hero from '../components/landing/Hero';
import HowItWorks from '../components/landing/HowItWorks';
import FactDemo from '../components/landing/FactDemo';
import WhatYouWontFind from '../components/landing/WhatYouWontFind';
import SourcesFreshness from '../components/landing/SourcesFreshness';
import Faq from '../components/landing/Faq';
import FinalCta from '../components/landing/FinalCta';
import '../styles/shell.css';
import '../components/landing/landing.css';

// Squelette de routing (#141) : assemble les sections placeholders, sans
// contenu éditorial final ni style final (voir sub-issues suivantes de #139).
export default function LandingPage() {
  return (
    <div className="app-shell">
      <div className="landing-page">
        <Brand />
        <main className="landing-main">
          <Hero />
          <HowItWorks />
          <FactDemo />
          <WhatYouWontFind />
          <SourcesFreshness />
          <Faq />
          <FinalCta />
        </main>
        <footer className="landing-footer">
          <p className="landing-footer-text">Données publiques agrégées. Aucun score, aucun classement.</p>
          <nav className="landing-footer-links" aria-label="Pages légales">
            <Link to="/methodologie">Méthodologie</Link>
            <Link to="/mentions-legales">Mentions légales</Link>
          </nav>
        </footer>
      </div>
    </div>
  );
}
