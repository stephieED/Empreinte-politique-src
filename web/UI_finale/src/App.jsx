import { Routes, Route, Navigate } from 'react-router-dom';
import ExplorerLayout from './components/ExplorerLayout';
import CandidateProfilePage from './pages/CandidateProfilePage';
import GroupProfilePage from './pages/GroupProfilePage';
import { DEFAULT_CANDIDATE_ID, DEFAULT_GROUP_ID } from './data';

function App() {
  return (
    <Routes>
      <Route path="/" element={<ExplorerLayout />}>
        <Route index element={<Navigate to={`/candidats/${DEFAULT_CANDIDATE_ID}`} replace />} />
        <Route path="candidats" element={<Navigate to={`/candidats/${DEFAULT_CANDIDATE_ID}`} replace />} />
        <Route path="candidats/:candidateId" element={<CandidateProfilePage />} />
        <Route path="groupes" element={<Navigate to={`/groupes/${DEFAULT_GROUP_ID}`} replace />} />
        <Route path="groupes/:groupId" element={<GroupProfilePage />} />
      </Route>
    </Routes>
  );
}

export default App;
