import { useParams } from 'react-router-dom';
import { getGroupProfile } from '../data';
import { useAsyncData } from '../hooks/useAsyncData';
import GroupProfile from '../components/GroupProfile';
import NotFoundProfile from '../components/NotFoundProfile';

export default function GroupProfilePage() {
  const { groupId } = useParams();
  const { data: group, loading } = useAsyncData(() => getGroupProfile(groupId), [groupId]);

  if (loading) return null;

  if (!group) {
    return <NotFoundProfile message={`Aucun groupe trouvé pour l'identifiant « ${groupId} ».`} />;
  }

  return <GroupProfile key={group.id} group={group} />;
}
