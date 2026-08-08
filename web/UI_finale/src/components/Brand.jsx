import { Link } from 'react-router-dom';
import './Brand.css';

// Lockup complet "Empreinte politique" : sa légende ("POLITIQUE") est vectorisée
// à ~12px à l'échelle de référence (viewBox 329.27 x 87.26) et devient
// illisible en dessous d'environ 50px de hauteur affichée. On le rend à 58px
// (≈ 219px de large), qui correspond à la largeur des rendus de vérification
// du design system (empreinte-lockup-2lignes-mobile-220.png) — cf.
// logo/empreinte-lockup-2lignes-specs.md. Symbole seul en dessous du
// breakpoint (en-tête étroit / mobile). Élément unique cliquable → accueil ;
// les images sont décoratives (alt=""), le lien porte le nom accessible.
export default function Brand() {
  return (
    <Link to="/" className="brand" aria-label="Empreinte politique — retour à l'accueil">
      <img
        src="/brand/empreinte-lockup-horizontal-empreinte-politique-light.svg"
        alt=""
        className="brand-lockup"
      />
      <img src="/brand/empreinte-symbol-light.svg" alt="" className="brand-symbol" />
    </Link>
  );
}
