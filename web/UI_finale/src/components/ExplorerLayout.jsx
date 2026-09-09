import { Link, Outlet, useLocation } from 'react-router-dom';
import { useEffect, useState } from 'react';
import Brand from './Brand';
import GroupsBar from './GroupsBar';
import GovernmentsBar from './GovernmentsBar';
import CandidatesBar from './CandidatesBar';
import SommaireSections from './SommaireSections';
import { GroupFilterProvider } from '../context/GroupFilterContext';
import '../styles/shell.css';
import PiedDeSite from './PiedDeSite';
import './ExplorerLayout.css';

/* ── Le cadre de la page (#324) ───────────────────────────────────────────────
 *
 * L'EN-TÊTE NE RESTE PLUS COLLÉ EN ENTIER. Mesuré le 08/09/2026 sur la fiche de
 * Jérôme Guedj, build de production : la marque et les trois barres de sélection
 * faisaient 357 px collés en haut, sur TOUS les supports — 45 % de la hauteur
 * d'un 1 280 × 800, 42 % d'un mobile 390 × 844. Ce qui est collé ne rend jamais
 * sa place, et la fiche fait 7 968 px sur ordinateur, 12 122 px sur mobile :
 * neuf écrans parcourus avec un demi-écran utile.
 *
 * Les barres défilent donc avec la page. Dès qu'on a défilé, une barre COMPACTE
 * de 56 px prend le relais : la marque, et un bouton qui ramène les listes.
 * 357 → 56 px, soit 301 px rendus au contenu — sur les cinq supports, mobile
 * compris. C'est la seule moitié de la réforme qui vaut pour tout le monde.
 *
 * L'ORDRE DES BARRES EST CANDIDATS, GROUPES, GOUVERNEMENTS. Une fiche s'atteint
 * par un nom ; les deux autres listes sont des entrées de contexte, et elles
 * descendent d'autant.
 */
const SEUIL_REPLI = 180;

export default function ExplorerLayout() {
  const [replie, setReplie] = useState(false);
  const [listesOuvertes, setListesOuvertes] = useState(false);
  const { pathname } = useLocation();

  useEffect(() => {
    const surDefilement = () => {
      const bas = window.scrollY > SEUIL_REPLI;
      setReplie(bas);
      // Remonter en haut referme le rappel : sinon on afficherait deux en-têtes.
      if (!bas) setListesOuvertes(false);
    };
    surDefilement();
    window.addEventListener('scroll', surDefilement, { passive: true });
    return () => window.removeEventListener('scroll', surDefilement);
  }, []);

  // Changer de fiche referme les listes : on vient de s'en servir.
  useEffect(() => {
    setListesOuvertes(false);
  }, [pathname]);

  const barresVisibles = !replie || listesOuvertes;

  return (
    <GroupFilterProvider>
      <div className="app-shell">
        <div className="explorer-main">
          {replie && (
            <div className="explorer-compact">
              {/* LE NOM ENTIER, PAS SA PREMIÈRE MOITIÉ. « Empreinte » seul
                  n'est pas la marque : c'est « Empreinte politique » que le
                  logo, le pied de site et les mentions légales portent, et
                  l'en-tête réduit est justement le moment où le lecteur n'a
                  plus le logo sous les yeux. */}
              <Link to="/" className="explorer-compact-marque">
                Empreinte politique
              </Link>
              <button
                type="button"
                className="explorer-compact-ouvrir"
                aria-expanded={listesOuvertes}
                onClick={() => setListesOuvertes((v) => !v)}
              >
                {listesOuvertes ? 'Masquer les listes' : 'Changer de fiche'}
              </button>
            </div>
          )}

          <div
            className={`explorer-bars${replie ? ' explorer-bars--rappel' : ''}`}
            hidden={!barresVisibles}
          >
            {!replie && <Brand />}
            <CandidatesBar />
            <GroupsBar />
            <GovernmentsBar />
          </div>

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
