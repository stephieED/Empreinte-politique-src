import { Outlet } from 'react-router-dom';
import Brand from './Brand';
import GroupsBar from './GroupsBar';
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
            <CandidatesBar />
          </div>
          <div className="explorer-profile-zone">
            <Outlet />
          </div>
        </div>
      </div>
    </GroupFilterProvider>
  );
}
