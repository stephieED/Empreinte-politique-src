import { useParams } from 'react-router-dom';
import { getGovernmentProfile, getGovernmentsList } from '../data';
import { useAsyncData } from '../hooks/useAsyncData';
import GovernmentProfile from '../components/GovernmentProfile';
import NotFoundProfile from '../components/NotFoundProfile';

export default function GovernmentProfilePage() {
  const { governmentId } = useParams();
  const { data: government, loading } = useAsyncData(() => getGovernmentProfile(governmentId), [governmentId]);
  // « En bref » situe le gouvernement parmi les autres : la chronologie vient
  // du manifest, déjà chargé pour la barre de sélection (#330).
  const { data: chronologie } = useAsyncData(getGovernmentsList, []);

  if (loading) return null;

  if (!government) {
    return <NotFoundProfile message={`Aucun gouvernement trouvé pour l'identifiant « ${governmentId} ».`} />;
  }

  return <GovernmentProfile key={government.id} government={government} chronologie={chronologie || []} />;
}
