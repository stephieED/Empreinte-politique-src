import { useParams } from 'react-router-dom';
import { getGovernmentProfile } from '../data';
import { useAsyncData } from '../hooks/useAsyncData';
import GovernmentProfile from '../components/GovernmentProfile';
import NotFoundProfile from '../components/NotFoundProfile';

export default function GovernmentProfilePage() {
  const { governmentId } = useParams();
  const { data: government, loading } = useAsyncData(() => getGovernmentProfile(governmentId), [governmentId]);

  if (loading) return null;

  if (!government) {
    return <NotFoundProfile message={`Aucun gouvernement trouvé pour l'identifiant « ${governmentId} ».`} />;
  }

  return <GovernmentProfile key={government.id} government={government} />;
}
