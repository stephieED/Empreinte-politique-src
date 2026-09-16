import { Outlet, useLocation } from 'react-router-dom';
import { useEffect, useRef, useState } from 'react';
import EnTeteSite from './EnTeteSite';
import GroupsBar from './GroupsBar';
import GovernmentsBar from './GovernmentsBar';
import CandidatesBar from './CandidatesBar';
import SommaireSections from './SommaireSections';
import { GroupFilterProvider } from '../context/GroupFilterContext';
import '../styles/shell.css';
import PiedDeSite from './PiedDeSite';
import './ExplorerLayout.css';

/* ── Le cadre de la page (#324, refait par #951) ──────────────────────────────
 *
 * LA RANGÉE DU LOGO RESTE COLLÉE, LES LISTES DÉFILENT. Retenu le 16/09/2026 sur
 * maquette jouable. La rangée porte le logo, les pages du site et « Changer de
 * fiche » ; les trois listes vivent dans la page, sous elle.
 *
 * LA MISE EN PAGE NE CHANGE JAMAIS AU DÉFILEMENT, et c'est tout l'objet de la
 * refonte. L'en-tête de #324 RETIRAIT les listes de la page au-delà de 180 px :
 * la page raccourcissait de 385 px, le navigateur ramenait le défilement à 0,
 * les listes revenaient, et la boucle reprenait. Mesuré le 16/09/2026 sur la
 * fiche de Jérôme Guedj, défilement par pas de 40 px : à 200 px les listes
 * partent, 22 ms plus tard le défilement est à 0. Ici, franchir les listes ne
 * change qu'une VISIBILITÉ — celle du bouton, dont la place est réservée.
 *
 * LA POSITION SE LIT À CHAQUE DÉFILEMENT, PAS PAR UN IntersectionObserver :
 * l'observateur ne signale qu'un franchissement, et un saut direct — une ancre,
 * un lien partagé — passe les listes sans jamais les croiser. Mesuré sur
 * maquette : à 390 px, un saut à 2 600 px laissait le bouton caché.
 *
 * SOUS 720 PX, LES LISTES QUITTENT LA PAGE. Elles y faisaient 1 277 px : deux
 * écrans avant le premier mot de la fiche. Le bandeau seul reste, et « Changer
 * de fiche » les ouvre dans le panneau.
 */
export default function ExplorerLayout() {
  const [listesPassees, setListesPassees] = useState(false);
  const [panneauOuvert, setPanneauOuvert] = useState(false);
  const { pathname } = useLocation();
  const enteteRef = useRef(null);
  const repereRef = useRef(null);

  useEffect(() => {
    let attente = false;
    const lire = () => {
      attente = false;
      const entete = enteteRef.current;
      const repere = repereRef.current;
      if (!entete || !repere) return;
      setListesPassees(repere.getBoundingClientRect().top <= entete.getBoundingClientRect().bottom);
    };
    const surDefilement = () => {
      if (attente) return;
      attente = true;
      requestAnimationFrame(lire);
    };
    lire();
    window.addEventListener('scroll', surDefilement, { passive: true });
    window.addEventListener('resize', surDefilement);
    return () => {
      window.removeEventListener('scroll', surDefilement);
      window.removeEventListener('resize', surDefilement);
    };
  }, []);

  // Remonter jusqu'aux listes referme le panneau : sinon elles seraient deux fois
  // à l'écran. Sous 720 px les listes ne sont plus dans la page, le repère est
  // collé à l'en-tête et cette règle ne se déclenche jamais.
  useEffect(() => {
    if (!listesPassees) setPanneauOuvert(false);
  }, [listesPassees]);

  // Changer de fiche referme le panneau : on vient de s'en servir.
  useEffect(() => {
    setPanneauOuvert(false);
  }, [pathname]);

  useEffect(() => {
    if (!panneauOuvert) return undefined;
    const surTouche = (e) => {
      if (e.key === 'Escape') setPanneauOuvert(false);
    };
    document.addEventListener('keydown', surTouche);
    return () => document.removeEventListener('keydown', surTouche);
  }, [panneauOuvert]);

  return (
    <GroupFilterProvider>
      <div className="app-shell">
        <div className="explorer-main">
          <EnTeteSite ref={enteteRef}>
            <button
              type="button"
              className={`explorer-changer${listesPassees ? ' explorer-changer--visible' : ''}`}
              aria-expanded={panneauOuvert}
              aria-controls="explorer-panneau"
              onClick={() => setPanneauOuvert((v) => !v)}
            >
              {/* Les deux libellés occupent la même case : le bouton garde sa
                  largeur, et les liens à sa gauche ne bougent pas. */}
              <span className="explorer-changer-libelle">
                Changer de fiche
              </span>
              <span className="explorer-changer-libelle">
                Masquer les listes
              </span>
            </button>
            <div id="explorer-panneau" className="explorer-panneau" hidden={!panneauOuvert}>
              {panneauOuvert && (
                <>
                  <CandidatesBar />
                  <GroupsBar />
                  <GovernmentsBar />
                </>
              )}
            </div>
          </EnTeteSite>

          <div className="explorer-bars">
            <CandidatesBar />
            <GroupsBar />
            <GovernmentsBar />
          </div>
          <div className="explorer-repere" ref={repereRef} aria-hidden="true" />

          <div className="explorer-corps">
            <SommaireSections />
            <div className="explorer-profile-zone">
              <Outlet />
            </div>
          </div>

          <PiedDeSite />
        </div>
      </div>
    </GroupFilterProvider>
  );
}
