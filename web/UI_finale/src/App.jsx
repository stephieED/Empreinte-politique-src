import { Routes, Route, Navigate } from 'react-router-dom';
import ExplorerLayout from './components/ExplorerLayout';
import LandingPage from './pages/LandingPage';
import CandidateProfilePage from './pages/CandidateProfilePage';
import GroupProfilePage from './pages/GroupProfilePage';
import GovernmentProfilePage from './pages/GovernmentProfilePage';
import MethodologyPage from './pages/MethodologyPage';
import LegalNoticePage from './pages/LegalNoticePage';
import { DEFAULT_CANDIDATE_ID, DEFAULT_GROUP_ID, DEFAULT_GOVERNMENT_ID } from './data';

function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      {/* Layout route sans path propre : les enfants gardent leurs URLs actuelles
          (/candidats/:id, /groupes/:id, /gouvernements/:id), seule la racine "/"
          bascule désormais vers la landing page au lieu de rediriger vers un candidat. */}
      <Route element={<ExplorerLayout />}>
        <Route path="candidats" element={<Navigate to={`/candidats/${DEFAULT_CANDIDATE_ID}`} replace />} />
        <Route path="candidats/:candidateId" element={<CandidateProfilePage />} />
        <Route path="groupes" element={<Navigate to={`/groupes/${DEFAULT_GROUP_ID}`} replace />} />
        <Route path="groupes/:groupId" element={<GroupProfilePage />} />
        <Route path="gouvernements" element={<Navigate to={`/gouvernements/${DEFAULT_GOVERNMENT_ID}`} replace />} />
        <Route path="gouvernements/:governmentId" element={<GovernmentProfilePage />} />
      </Route>
      {/* Pages statiques hors ExplorerLayout : pas de candidat/groupe sélectionné,
          les bandeaux Groupes/Gouvernements/Candidats n'ont pas de sens ici. */}
      <Route path="/methodologie" element={<MethodologyPage />} />
      <Route path="/mentions-legales" element={<LegalNoticePage />} />
    </Routes>
  );
}

export default App;
