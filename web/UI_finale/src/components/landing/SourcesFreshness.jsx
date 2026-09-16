import { Link } from 'react-router-dom';
import CartesSources from '../CartesSources';
import CouvertureAccueil from './CouvertureAccueil';
import './landing.css';

// Contenu éditorial : toutes les infos de licence/cadence viennent de
// sources.config.js (lui-même repris d'AGENTS.md §7 et README.md) — rien
// n'est réinventé ici. Chaque source est un <details> replié par défaut
// (seul le nom, et le badge de couverture limitée le cas échéant, restent
// visibles ; la cadence de mise à jour rejoint le contenu couvert/la
// licence derrière le clic — retour utilisateur du 2026-08-15, page perçue
// comme trop chargée). Même pattern que Faq.jsx (accessible clavier/
// tactile nativement, contrairement à un simple :hover).
export default function SourcesFreshness() {
  return (
    <section className="landing-section" aria-label="Sources et fraîcheur des données">
      <h2>Sources &amp; fraîcheur des données</h2>
      {/* EN PREMIER : depuis quand chaque institution est lue. Un candidat dont
          la carrière précède les sources ne doit pas passer pour un candidat
          sans passé (relecture du 11/09/2026). */}
      <CouvertureAccueil />
      <CartesSources />
      {/* « Voir la fraîcheur en détail » est retiré (relecture du 11/09/2026) :
          il menait à une fiche de candidat prise par défaut, où la fraîcheur
          n'est pas détaillée. */}
      {/* La couverture est une propriété du CORPUS, pas d'une fiche : depuis
          quand chaque source publie, ce qu'elle ne publie pas, et sur quelles
          fiches une liste manque. Elle a sa page — la répéter sur chacune des
          fiches disait 59 fois la même chose sans parler de personne. */}
      <p className="sources-freshness-cta">
        <Link to="/sources">Ce que contient ce corpus →</Link>
      </p>
    </section>
  );
}
