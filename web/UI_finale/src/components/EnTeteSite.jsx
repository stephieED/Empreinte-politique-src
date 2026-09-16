import Brand from './Brand';
import NavigationSite from './NavigationSite';
import './EnTeteSite.css';

/* ── La rangée du logo, collée en haut (#951) ─────────────────────────────────
 *
 * Le logo à gauche, les pages du site à droite. Une seule rangée pour
 * l'explorateur et l'accueil, pour qu'elle ne diverge pas d'une page à l'autre.
 *
 * SA HAUTEUR NE CHANGE JAMAIS AU DÉFILEMENT : c'est ce qui rend le défilement
 * stable (voir ExplorerLayout.jsx). Elle se lit dans `--entete-hauteur`, que les
 * enfants — le panneau des listes — reprennent pour se poser dessous.
 *
 * `children` s'ajoute après les liens : l'explorateur y met « Changer de fiche »
 * et son panneau.
 */
export default function EnTeteSite({ children, ref }) {
  return (
    <header className="entete-site" ref={ref}>
      <Brand />
      <div className="entete-site-actions">
        <NavigationSite />
        {children}
      </div>
    </header>
  );
}
