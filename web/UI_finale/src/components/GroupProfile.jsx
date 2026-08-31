import '../styles/shell.css';
import './GroupProfile.css';
// #326 : voir CandidateProfile — une seule définition, partagée.
import { PositionVote } from './Lecture';
import { OUTCOME_COLOR, styleForPosition } from '../utils/lecture';

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
    ...styleForPosition(v.position),
    quorumNote: v.quorum ? '' : ' · quorum non atteint',
  }));

  // #653 : le statut se lit À LA DATE DE RÉFÉRENCE de la fiche, pas aujourd'hui.
  // « Actif » sur un groupe de la XVIe législature disait « encore député⋅e en
  // 2026 » — une propriété de la carrière de la personne, pas du groupe.
  const dateRefLabel = group.dateReferenceLabel || null;
  const members = group.members.map((m) => ({
    nom: m.nom,
    initials: initialsOf(m.nom),
    statusLabel: m.present ? 'Membre' : 'Parti avant',
    statusClass: m.present ? 'gp-member-status-actif' : 'gp-member-status-ancien',
  }));

  const amendmentSegments = group.amendmentSegments.map((s) => ({ ...s, color: OUTCOME_COLOR[s.key] }));

  const mandatsAgreges = group.mandatsAgreges || [];

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
                <PositionVote position={vote.position} />
              </div>
              <p className="gp-vote-texte">{vote.texte}</p>
              <div className="gp-coherence-track">
                {vote.coherence != null
                  // Une position sans couleur (`non_votant`, valeur inconnue) ne
                  // laisse pas la barre invisible : elle prend le gris de bordure,
                  // qui n'est celui d'aucune position exprimée.
                  ? <div className="gp-coherence-fill" style={{ width: `${vote.coherence}%`, background: vote.color || 'var(--border-strong)' }} />
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

        <p className="gp-section-title">Mandats agrégés</p>
        {mandatsAgreges.length === 0 ? (
          <p className="gp-empty">Aucun mandat agrégé disponible pour ce groupe.</p>
        ) : (
        <div className="gp-mandats-grid">
          {mandatsAgreges.map((m) => (
            <div className="gp-mandat-card" key={`${m.categorie}-${m.label}`}>
              <span className="gp-mandat-category">{m.categorieLabel}</span>
              <p className="gp-mandat-label">{m.label}</p>
              {/* Deux grandeurs, deux lignes (#656). « Qui y siège » d'abord :
                  c'est la réponse à « ce groupe travaille sur quoi ». Le cumul
                  reste publié, nommé comme un cumul — 43 % des adhésions de
                  commission publiées durent une journée ou moins, et lire le
                  cumul comme un effectif faisait dire à la fiche que 67 des 76
                  membres LFI siègent aux finances quand ils sont 5. Numérateur
                  et dénominateur, jamais un pourcentage (DESIGN_SYSTEM.md §6). */}
              <p className="gp-mandat-count">
                {m.nbMembresActifs > 0
                  ? `${m.nbMembresActifs} / ${m.effectifReference ?? group.profilsDisponibles} membres y siégeaient${dateRefLabel ? ` au ${dateRefLabel}` : ''}`
                  : `Aucun membre n'y siégeait${dateRefLabel ? ` au ${dateRefLabel}` : ''}`}
              </p>
              <p className="gp-mandat-count gp-mandat-count-cumul">
                {m.nbMembresCumul > 1
                  ? `${m.nbMembresCumul} membres y ont siégé au moins une fois`
                  : `${m.nbMembresCumul} membre y a siégé au moins une fois`}
              </p>
              <div className="gp-mandat-fonctions">
                {m.parFonction.map((f) => (
                  <span className="gp-mandat-fonction-pill" key={f.fonction}>
                    {f.fonction} <span className="gp-mandat-fonction-count">{f.count}</span>
                  </span>
                ))}
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

        <p className="gp-section-title">
          Membres couverts{dateRefLabel ? ` — appartenance au ${dateRefLabel}` : ''}
        </p>
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
