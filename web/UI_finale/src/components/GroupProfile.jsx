import '../styles/shell.css';
import './GroupProfile.css';

const VOTE_STYLE = {
  pour: { color: '#007A45', label: 'Pour' },
  contre: { color: '#E53420', label: 'Contre' },
  abstention: { color: '#8B8794', label: 'Abstention' },
};

const OUTCOME_COLOR = {
  adopté: '#007A45',
  rejeté: '#E53420',
  retiré: '#F2A93B',
  tombé: '#8B8794',
  irrecevable: '#B8B4AE',
  non_soutenu: '#DCD9D3',
};

function VerifiedIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
      <path d="M2.5 9.5L9 3" stroke="#14151A" strokeWidth="1.8" strokeLinecap="round" />
      <path d="M5.7 4.8l1.4 1.4" stroke="#14151A" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

function initialsOf(nom) {
  return nom
    .split(' ')
    .map((p) => p[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();
}

export default function GroupProfile({ group }) {
  const cohesionVotes = group.votes.map((v) => ({
    ...v,
    ...VOTE_STYLE[v.position],
    quorumNote: v.quorum ? '' : ' · quorum non atteint',
  }));

  const members = group.members.map((m) => ({
    nom: m.nom,
    initials: initialsOf(m.nom),
    statusLabel: m.actif ? 'Actif' : 'Ancien',
    statusClass: m.actif ? 'gp-member-status-actif' : 'gp-member-status-ancien',
  }));

  const amendmentSegments = group.amendmentSegments.map((s) => ({ ...s, color: OUTCOME_COLOR[s.key] }));

  return (
    <main className="gp-main">
      <div className="gp-breadcrumb">
        Groupes / <strong>{group.title}</strong>
      </div>

        <div className="gp-hero-grid">
          <div className="gp-banner">
            <span className="gp-banner-tag">Groupe parlementaire</span>
            <h1>{group.title}</h1>
            <p>{group.kicker}</p>
          </div>

          <div className="gp-coverage-card">
            <div
              className="gp-coverage-donut"
              style={{ background: `conic-gradient(#14151A ${group.coveragePct}%, #F0EEEB 0)` }}
            >
              <div className="gp-coverage-donut-inner">{group.coveragePct}%</div>
            </div>
            <div>
              <p className="gp-coverage-title">Couverture de détail</p>
              <p className="gp-coverage-sub">
                {group.profilsDisponibles} / {group.rosterTotal} membres
              </p>
            </div>
          </div>
        </div>

        <div className="gp-kpi-grid">
          {group.kpis.map((kpi) => (
            <div className="gp-kpi-card" key={kpi.label}>
              <div className="gp-kpi-value">{kpi.value}</div>
              <div className="gp-kpi-label">{kpi.label}</div>
              <div className="gp-kpi-caveat">{kpi.caveat}</div>
            </div>
          ))}
        </div>

        <p className="gp-section-title">Cohésion de vote</p>
        {cohesionVotes.length === 0 ? (
          <p className="gp-empty">Aucun scrutin agrégé disponible pour ce groupe.</p>
        ) : (
        <div className="gp-cohesion-grid">
          {cohesionVotes.map((vote) => (
            <div className="gp-vote-card" key={vote.texte}>
              <div className="gp-vote-position">
                <span className="gp-vote-dot" style={{ background: vote.color }} />
                <span className="gp-vote-position-label" style={{ color: vote.color }}>
                  {vote.label}
                </span>
              </div>
              <p className="gp-vote-texte">{vote.texte}</p>
              <div className="gp-coherence-track">
                {vote.coherence != null
                  ? <div className="gp-coherence-fill" style={{ width: `${vote.coherence}%`, background: vote.color }} />
                  : <span className="gp-coherence-nd">N/D</span>}
              </div>
              <div className="gp-vote-footer">
                <span className="gp-verified-badge">
                  <VerifiedIcon /> Source vérifiée
                </span>
                <span className="gp-vote-meta">
                  {vote.date}
                  {vote.quorumNote}
                </span>
              </div>
            </div>
          ))}
        </div>
        )}

        <div className="gp-two-col">
          <div>
            <p className="gp-section-title">Amendements déposés</p>
            <div className="gp-amend-card">
              {group.amendmentsAllDeposantsTotal === 0 ? (
                <p className="gp-empty">Aucun amendement agrégé disponible pour ce groupe.</p>
              ) : (
                <>
                  <p className="gp-amend-caption">
                    {group.amendmentsDeposedTotal} déposés sur {group.amendmentsAllDeposantsTotal} tous déposants confondus.
                  </p>
                  <div className="gp-amend-bar">
                    {amendmentSegments.map((seg) => (
                      <div key={seg.key} style={{ flex: `${seg.count} 0 0`, background: seg.color }} />
                    ))}
                  </div>
                  <div className="gp-amend-legend">
                    {amendmentSegments.map((seg) => (
                      <span className="gp-amend-legend-item" key={seg.key}>
                        <span className="gp-amend-legend-dot" style={{ background: seg.color }} />
                        {seg.label} ({seg.count})
                      </span>
                    ))}
                  </div>
                </>
              )}
            </div>
          </div>

          <div>
            <p className="gp-section-title">Empreinte thématique</p>
            <div className="gp-tags-card">
              {group.tags.length === 0 ? (
                <p className="gp-empty">Aucun mot-clé agrégé disponible pour ce groupe.</p>
              ) : (
                group.tags.map((tag) => (
                  <span className="gp-tag-pill" key={tag.label}>
                    {tag.label} <span className="gp-tag-count">{tag.count}</span>
                  </span>
                ))
              )}
            </div>
          </div>
        </div>

        <p className="gp-section-title">Membres couverts</p>
        {members.length === 0 ? (
          <p className="gp-empty">Aucun membre couvert pour ce groupe.</p>
        ) : (
          <div className="gp-members-grid">
            {members.map((member) => (
              <div className="gp-member-row" key={member.nom}>
                <span className="gp-member-avatar">{member.initials}</span>
                <span className="gp-member-name">{member.nom}</span>
                <span className={`gp-member-status ${member.statusClass}`}>{member.statusLabel}</span>
              </div>
            ))}
          </div>
        )}
    </main>
  );
}
