import { useDeferredValue, useMemo } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { chargerSourcesCandidat, vueCandidat } from '../data';
import { useAsyncData } from '../hooks/useAsyncData';
import CandidateProfile from '../components/CandidateProfile';
import NotFoundProfile from '../components/NotFoundProfile';

export default function CandidateProfilePage() {
  const { candidateId } = useParams();
  const { data: sources, loading } = useAsyncData(() => chargerSourcesCandidat(candidateId), [candidateId]);

  /* LE MOT VIT DANS L'ADRESSE (#979) : `?mot=finances` se recharge, se
   * partage et revient avec le bouton précédent. `replace` : chaque lettre
   * tapée n'est pas une page de l'historique. */
  const [params, setParams] = useSearchParams();
  const mot = params.get('mot') ?? '';
  const changerMot = (valeur) => {
    setParams((p) => {
      const suivant = new URLSearchParams(p);
      if (valeur) suivant.set('mot', valeur);
      else suivant.delete('mot');
      return suivant;
    }, { replace: true });
  };
  /* La fiche se recalcule sur le mot DIFFÉRÉ : le champ suit la frappe, le
   * recalcul suit quand il peut. */
  const motDiffere = useDeferredValue(mot);
  const candidate = useMemo(() => vueCandidat(sources, motDiffere), [sources, motDiffere]);

  if (loading) return null;

  if (!candidate) {
    return <NotFoundProfile message={`Aucun candidat trouvé pour l'identifiant « ${candidateId} ».`} />;
  }

  return (
    <CandidateProfile
      key={candidate.id}
      candidate={candidate}
      mot={motDiffere.trim()}
      saisie={mot}
      onSaisie={changerMot}
    />
  );
}
