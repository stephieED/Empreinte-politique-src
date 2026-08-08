import { useMemo } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { getCandidatesList, getGroupsList } from '../data';
import { useGroupFilter } from '../context/GroupFilterContext';
import { useAsyncData } from '../hooks/useAsyncData';
import { initialsOf } from '../utils/text';
import ScrollRow from './ScrollRow';
import './CandidatesBar.css';

export default function CandidatesBar() {
  const { selectedGroupId } = useGroupFilter();
  const { data: candidates, loading } = useAsyncData(getCandidatesList, []);
  const { data: groups } = useAsyncData(getGroupsList, []);
  const navigate = useNavigate();
  const { candidateId: activeCandidateId } = useParams();

  const filtered = useMemo(
    () => (selectedGroupId ? (candidates || []).filter((c) => c.groupIds?.includes(selectedGroupId)) : (candidates || [])),
    [candidates, selectedGroupId],
  );

  const filteredGroupTitle = useMemo(
    () => (selectedGroupId ? (groups || []).find((g) => g.id === selectedGroupId)?.title : null),
    [groups, selectedGroupId],
  );

  return (
    <div className="cb-bar">
      <span className="cb-bar-label">
        Candidats{filteredGroupTitle ? ` · ${filteredGroupTitle}` : ''}
      </span>
      {loading ? (
        <ScrollRow ariaLabel="Candidats (chargement)">
          {Array.from({ length: 6 }).map((_, i) => (
            <div className="cb-chip cb-skeleton" key={i} />
          ))}
        </ScrollRow>
      ) : filtered.length === 0 ? (
        <p className="cb-empty">Aucun candidat dans ce groupe.</p>
      ) : (
        <ScrollRow ariaLabel="Liste des candidats">
          {filtered.map((candidate) => {
            const active = activeCandidateId === candidate.id;
            return (
              <button
                key={candidate.id}
                type="button"
                role="listitem"
                aria-pressed={active}
                className={`cb-chip ${active ? 'active' : ''}`}
                onClick={() => navigate(`/candidats/${candidate.id}`)}
              >
                <span className="cb-chip-avatar">{initialsOf(candidate.nom)}</span>
                <span className="cb-chip-label">{candidate.nom}</span>
              </button>
            );
          })}
        </ScrollRow>
      )}
    </div>
  );
}
