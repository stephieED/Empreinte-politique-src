import { Link, Outlet } from 'react-router-dom';
import Brand from './Brand';
import GroupsBar from './GroupsBar';
import GovernmentsBar from './GovernmentsBar';
import CandidatesBar from './CandidatesBar';
import { GroupFilterProvider } from '../context/GroupFilterContext';
import '../styles/shell.css';
import './ExplorerLayout.css';

export default function ExplorerLayout() {
  return (
    <GroupFilterProvider>
      <div className="app-shell">
        <div className="explorer-main">
          <div className="explorer-bars">
            <Brand />
            <GroupsBar />
            <GovernmentsBar />
            <CandidatesBar />
          </div>
          <div className="explorer-profile-zone">
            <Outlet />
          </div>
          <footer className="explorer-footer">
            <p className="explorer-footer-text">Données publiques agrégées. Aucun score, aucun classement.</p>
            <nav className="explorer-footer-links" aria-label="Pages légales">
              <Link to="/methodologie">Méthodologie</Link>
              <Link to="/mentions-legales">Mentions légales</Link>
            </nav>
          </footer>
        </div>
      </div>
    </GroupFilterProvider>
  );
}
