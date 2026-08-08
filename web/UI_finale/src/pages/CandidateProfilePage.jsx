import { useParams } from 'react-router-dom';
import { getCandidateProfile } from '../data';
import { useAsyncData } from '../hooks/useAsyncData';
import CandidateProfile from '../components/CandidateProfile';
import NotFoundProfile from '../components/NotFoundProfile';

export default function CandidateProfilePage() {
  const { candidateId } = useParams();
  const { data: candidate, loading } = useAsyncData(() => getCandidateProfile(candidateId), [candidateId]);

  if (loading) return null;

  if (!candidate) {
    return <NotFoundProfile message={`Aucun candidat trouvé pour l'identifiant « ${candidateId} ».`} />;
  }

  return <CandidateProfile key={candidate.id} candidate={candidate} />;
}
