import { Link } from 'react-router-dom';
import Brand from '../components/Brand';
import Hero from '../components/landing/Hero';
import HowItWorks from '../components/landing/HowItWorks';
import FactDemo from '../components/landing/FactDemo';
import WhatYouWontFind from '../components/landing/WhatYouWontFind';
import SourcesFreshness from '../components/landing/SourcesFreshness';
import Faq from '../components/landing/Faq';
import '../styles/shell.css';
import '../components/landing/landing.css';

// Assemblage des sections (#141, réagencé le 2026-08-15 suite aux retours
// utilisateur sur #307) : deux colonnes indépendantes (HowItWorks/
// WhatYouWontFind/Faq à gauche, FactDemo/SourcesFreshness à droite), chacune
// empilée avec un gap fixe (landing.css) — un CSS Grid à une seule rangée
// implicite par section avait été essayé d'abord, mais l'auto-sizing des
// rangées selon le contenu le plus haut de chaque paire (ex. FactDemo plus
// haut que HowItWorks) laissait un espace vide variable sous les sections
// plus courtes (align-items: start), d'où des espacements verticaux
// incohérents entre encadrés. Deux colonnes indépendantes garantissent un
// espacement constant à l'intérieur de chaque colonne, quelle que soit la
// hauteur de l'autre. Sur mobile (landing.css, colonnes empilées), l'ordre
// devient donc [HowItWorks, WhatYouWontFind, Faq] puis [FactDemo,
// SourcesFreshness] plutôt que l'ordre narratif d'origine — accepté en
// échange d'un espacement fiable plutôt que de réintroduire un décalage
// visuel/clavier via `order` CSS (voir la note sur l'ordre du DOM ci-dessus,
// #307 également). Le CTA final (candidat/groupe/gouvernement) est intégré
// au Hero (voir Hero.jsx) plutôt que répété dans une section dédiée en bas
// de page — ex-FinalCta.jsx, supprimé.
export default function LandingPage() {
  return (
    <div className="app-shell">
      <div className="landing-page">
        <Brand />
        <main className="landing-main">
          <Hero />
          <div className="landing-columns">
            <div className="landing-column">
              <HowItWorks />
              <WhatYouWontFind />
              <Faq />
            </div>
            <div className="landing-column">
              <FactDemo />
              <SourcesFreshness />
            </div>
          </div>
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
