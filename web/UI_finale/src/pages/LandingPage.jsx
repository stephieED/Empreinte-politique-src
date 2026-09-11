import Brand from '../components/Brand';
import PiedDeSite from '../components/PiedDeSite';
import Hero from '../components/landing/Hero';
import HowItWorks from '../components/landing/HowItWorks';
import WhatYouWontFind from '../components/landing/WhatYouWontFind';
import SourcesFreshness from '../components/landing/SourcesFreshness';
import Faq from '../components/landing/Faq';
import '../styles/shell.css';
import '../components/landing/landing.css';

// Assemblage des sections (#141, réagencé le 2026-08-15 suite aux retours
// utilisateur sur #307) : deux colonnes indépendantes (HowItWorks/
// WhatYouWontFind/Faq à gauche, SourcesFreshness à droite), chacune
// empilée avec un gap fixe (landing.css) — un CSS Grid à une seule rangée
// implicite par section avait été essayé d'abord, mais l'auto-sizing des
// rangées selon le contenu le plus haut de chaque paire (ex. une section de
// droite plus haute que HowItWorks) laissait un espace vide variable sous les sections
// plus courtes (align-items: start), d'où des espacements verticaux
// incohérents entre encadrés. Deux colonnes indépendantes garantissent un
// espacement constant à l'intérieur de chaque colonne, quelle que soit la
// hauteur de l'autre. Sur mobile (landing.css, colonnes empilées), l'ordre
// devient donc [HowItWorks, WhatYouWontFind, Faq] puis [SourcesFreshness]
// plutôt que l'ordre narratif d'origine — accepté en
// échange d'un espacement fiable plutôt que de réintroduire un décalage
// visuel/clavier via `order` CSS (voir la note sur l'ordre du DOM ci-dessus,
// #307 également). Le CTA final (candidat/groupe/gouvernement) est intégré
// au Hero (voir Hero.jsx) plutôt que répété dans une section dédiée en bas
// de page — ex-FinalCta.jsx, supprimé.
//
// « Un fait, une source » (FactDemo) est retiré le 11/09/2026 à la demande de
// la propriétaire : un fait fictif (« Élu·e X », « Texte Y ») relevé par
// l'audit du 29/08, et « Sources & fraîcheur des données » remonte en tête de
// la colonne de droite, avec la borne de chaque institution.
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
              <SourcesFreshness />
            </div>
          </div>
        </main>
        <PiedDeSite />
      </div>
    </div>
  );
}
