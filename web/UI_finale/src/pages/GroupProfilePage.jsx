import { Navigate, useParams } from 'react-router-dom';
import { getLigneeProfile, ligneeDeLaFiche } from '../data';
import { useAsyncData } from '../hooks/useAsyncData';
import LigneeProfile from '../components/LigneeProfile';
import NotFoundProfile from '../components/NotFoundProfile';

/* Une page par LIGNÉE (#329, sur le socle #836). L'identifiant est celui de la
 * lignée déclarée (`AN-SOC`). Une adresse d'avant — celle d'une fiche de
 * législature, `AN-SOC-17` — mène à sa lignée plutôt qu'à une page vide : un
 * lien partagé ne casse pas parce que le découpage a changé. */
export default function GroupProfilePage() {
  const { groupId } = useParams();
  const { data, loading } = useAsyncData(async () => {
    const lignee = await getLigneeProfile(groupId);
    if (lignee) return { lignee };
    return { redirection: await ligneeDeLaFiche(groupId) };
  }, [groupId]);

  if (loading) return null;
  if (data?.redirection) return <Navigate to={`/groupes/${data.redirection}`} replace />;
  if (!data?.lignee) {
    return <NotFoundProfile message={`Aucun groupe trouvé pour l'identifiant « ${groupId} ».`} />;
  }
  return <LigneeProfile key={data.lignee.id} lignee={data.lignee} />;
}
