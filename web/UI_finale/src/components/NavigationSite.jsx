import { useEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import './NavigationSite.css';

/* ── La barre des pages du site (#951) ────────────────────────────────────────
 *
 * Quatre liens, dans le style discret retenu le 16/09/2026 : gris, la page
 * courante en encre soulignée de jaune. Le jaune est un TRAIT sous le mot,
 * jamais la couleur du texte — 1,05:1 sur le fond clair (DESIGN_SYSTEM §2).
 *
 * Sous 720 px les quatre liens ne tiennent plus à côté du logo et du bouton
 * « Changer de fiche » : ils passent dans un menu.
 *
 * DEUX CIBLES SONT PROVISOIRES, tant que #951 n'a pas créé leurs pages :
 * « Sources » mène à /couverture, qui dit ce que le dépôt contient et depuis
 * quand ; « FAQ » mène aux questions fréquentes de l'accueil.
 */
const PAGES = [
  { libelle: 'Explorateur', vers: '/candidats', racines: ['/candidats', '/groupes', '/gouvernements'] },
  { libelle: 'Méthodologie', vers: '/methodologie', racines: ['/methodologie'] },
  { libelle: 'Sources', vers: '/couverture', racines: ['/couverture'] },
  { libelle: 'FAQ', vers: '/#faq', racines: [] },
];

const estCourante = (page, pathname) =>
  page.racines.some((r) => pathname === r || pathname.startsWith(`${r}/`));

export default function NavigationSite() {
  const { pathname } = useLocation();
  const [menuOuvert, setMenuOuvert] = useState(false);
  const menuRef = useRef(null);

  useEffect(() => {
    setMenuOuvert(false);
  }, [pathname]);

  useEffect(() => {
    if (!menuOuvert) return undefined;
    const surClic = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) setMenuOuvert(false);
    };
    const surTouche = (e) => {
      if (e.key === 'Escape') setMenuOuvert(false);
    };
    document.addEventListener('mousedown', surClic);
    document.addEventListener('keydown', surTouche);
    return () => {
      document.removeEventListener('mousedown', surClic);
      document.removeEventListener('keydown', surTouche);
    };
  }, [menuOuvert]);

  const liens = (className) =>
    PAGES.map((page) => {
      const courante = estCourante(page, pathname);
      return (
        <Link
          key={page.libelle}
          to={page.vers}
          className={`${className}${courante ? ` ${className}--courante` : ''}`}
          aria-current={courante ? 'page' : undefined}
        >
          {page.libelle}
        </Link>
      );
    });

  return (
    <>
      <nav className="nav-site" aria-label="Pages du site">
        {liens('nav-site-lien')}
      </nav>
      <div className="nav-site-menu" ref={menuRef}>
        <button
          type="button"
          className="nav-site-menu-bouton"
          aria-expanded={menuOuvert}
          aria-controls="nav-site-menu-liste"
          onClick={() => setMenuOuvert((v) => !v)}
        >
          <span className="nav-site-menu-icone" aria-hidden="true" />
          Menu
        </button>
        <nav
          id="nav-site-menu-liste"
          className="nav-site-menu-liste"
          aria-label="Pages du site"
          hidden={!menuOuvert}
        >
          {liens('nav-site-menu-lien')}
        </nav>
      </div>
    </>
  );
}
