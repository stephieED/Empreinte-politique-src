import { useMemo, useState } from 'react';
import '../styles/shell.css';
import './CandidateProfile.css';

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

const TABS = [
  { key: 'votes', label: 'Votes' },
  { key: 'textes', label: 'Textes' },
  { key: 'donnees', label: 'Données' },
];

export default function CandidateProfile({ candidate }) {
  const [tab, setTab] = useState('votes');
  const [openFlyout, setOpenFlyout] = useState(null);
  const [themeFilter, setThemeFilter] = useState('all');

  const toggleFlyout = (key) => setOpenFlyout((cur) => (cur === key ? null : key));

  const kpis = [
    {
      key: 'anciennete',
      value: candidate.kpis.anciennete,
      label: 'Ancienneté du mandat',
      caveat: "Mesure la durée, pas l'implication.",
      onClick: () => toggleFlyout('mandats'),
    },
    {
      key: 'responsabilites',
      value: candidate.kpis.responsabilites,
      label: 'Responsabilités',
      caveat: 'Fonctions dédupliquées par intitulé. Jamais un score.',
      onClick: () => toggleFlyout('resp'),
    },
    {
      key: 'votes',
      value: candidate.kpis.votes,
      label: 'Votes de texte',
      caveat: 'Positions documentées (pour/contre/abstention) ; absences non publiées.',
      onClick: null,
    },
    {
      key: 'theme',
      value: candidate.kpis.theme,
      label: 'Thème dominant',
      caveat: 'Aide de lecture par mots-clés, pas une position déclarée.',
      onClick: null,
    },
  ];

  const votes = candidate.votes.map((v) => ({ ...v, ...VOTE_STYLE[v.position] }));
  const outcomes = candidate.outcomes.map((o) => ({ ...o, color: OUTCOME_COLOR[o.key] }));
  const totalAmendements = outcomes.reduce((sum, o) => sum + o.count, 0);

  const scopeCompare = useMemo(() => {
    const maxScope = Math.max(1, ...candidate.scopeBuckets.map((b) => Math.max(b.textes, b.amend)));
    return candidate.scopeBuckets.map((b) => ({
      label: b.label,
      textesCount: b.textes,
      amendCount: b.amend,
      textesPct: Math.round((b.textes / maxScope) * 100),
      amendPct: Math.round((b.amend / maxScope) * 100),
    }));
  }, [candidate.scopeBuckets]);

  const themeCounts = useMemo(() => {
    const counts = {};
    candidate.textes.forEach((t) => {
      counts[t.theme] = (counts[t.theme] || 0) + 1;
    });
    return counts;
  }, [candidate.textes]);

  const themePills = useMemo(() => {
    const themes = Object.keys(themeCounts);
    return [
      { key: 'all', label: `Tous les thèmes (${candidate.textes.length})` },
      ...themes.map((k) => ({ key: k, label: `${k} (${themeCounts[k]})` })),
    ];
  }, [themeCounts, candidate.textes]);

  const themeShelves = useMemo(() => {
    const visible = themeFilter === 'all' ? candidate.textes : candidate.textes.filter((t) => t.theme === themeFilter);
    const byTheme = new Map();
    visible.forEach((t) => {
      if (!byTheme.has(t.theme)) byTheme.set(t.theme, []);
      byTheme.get(t.theme).push(t);
    });
    return Array.from(byTheme.entries()).map(([label, items]) => ({ label, items }));
  }, [themeFilter, candidate.textes]);

  const flyoutTitle = openFlyout === 'mandats' ? 'Mandats en cours' : openFlyout === 'resp' ? 'Responsabilités' : '';
  const flyoutItems = openFlyout === 'mandats' ? candidate.mandats : openFlyout === 'resp' ? candidate.responsabilites : [];

  return (
    <main className="main">
      <div className="breadcrumb">
        Candidats / <strong>{candidate.nom}</strong>
      </div>

        <div className="banner">
          <span className="banner-tag">{candidate.parti}</span>
          <h1>{candidate.nom}</h1>
          <p>
            {candidate.groupe} · {candidate.profession}
          </p>
        </div>

        <div className="kpi-grid">
          {kpis.map((kpi) => (
            <button
              key={kpi.key}
              type="button"
              className="kpi-card"
              onClick={kpi.onClick ?? undefined}
              style={{ cursor: kpi.onClick ? 'pointer' : 'default' }}
            >
              <div className="kpi-value">{kpi.value}</div>
              <div className="kpi-label">{kpi.label}</div>
              <div className="kpi-caveat">{kpi.caveat}</div>
            </button>
          ))}
        </div>

        {openFlyout && (
          <div className="flyout">
            <p className="flyout-title">{flyoutTitle}</p>
            <div className="flyout-list">
              {flyoutItems.map((item) => (
                <div className="flyout-row" key={item.label}>
                  <span>{item.label}</span>
                  <span className="period">{item.period}</span>
                </div>
              ))}
            </div>
            <p className="flyout-note">Échantillon illustratif — liste complète non représentée dans cette maquette.</p>
          </div>
        )}

        <div className="tabs">
          {TABS.map((t) => (
            <button
              key={t.key}
              type="button"
              className={`tab-btn ${tab === t.key ? 'active' : ''}`}
              onClick={() => setTab(t.key)}
            >
              {t.label}
            </button>
          ))}
        </div>

        {tab === 'votes' && (
          <div className="votes-grid">
            {votes.length === 0 && <p className="donnees-text">Aucune position de vote documentée pour ce mandat.</p>}
            {votes.map((vote) => (
              <div className="vote-card" key={vote.titre}>
                <div className="vote-position">
                  <span className="vote-dot" style={{ background: vote.color }} />
                  <span className="vote-position-label" style={{ color: vote.color }}>
                    {vote.label}
                  </span>
                </div>
                <p className="vote-title">{vote.titre}</p>
                <div className="vote-footer">
                  <span className="vote-badge">
                    <VerifiedIcon /> Source vérifiée
                  </span>
                  <span className="vote-meta">{vote.meta}</span>
                </div>
              </div>
            ))}
          </div>
        )}

        {tab === 'textes' && (
          <>
            <div className="textes-card">
              <p className="textes-caption">
                Répartition des amendements par scène décisionnelle. Ne pas lire comme un score d&apos;influence.
              </p>
              {totalAmendements === 0 ? (
                <p className="donnees-text">Aucun amendement recensé pour ce mandat.</p>
              ) : (
                <>
                  <div className="outcome-bar">
                    {outcomes.map((seg) => (
                      <div key={seg.key} style={{ flex: `${seg.count} 0 0`, background: seg.color }} />
                    ))}
                  </div>
                  <div className="outcome-legend">
                    {outcomes.map((seg) => (
                      <span className="outcome-legend-item" key={seg.key}>
                        <span className="outcome-legend-dot" style={{ background: seg.color }} />
                        {seg.label} ({seg.count})
                      </span>
                    ))}
                  </div>
                </>
              )}
              <div className="compare-header">
                <span />
                <span>Textes portés</span>
                <span>Amendements</span>
              </div>
              <div className="compare-rows">
                {scopeCompare.map((row) => (
                  <div className="compare-row" key={row.label}>
                    <span className="compare-row-label">{row.label}</span>
                    <div className="compare-bar-wrap">
                      <span className="compare-bar-track">
                        <span className="compare-bar-fill" style={{ width: `${row.textesPct}%`, background: '#14151A' }} />
                      </span>
                      <span className="compare-bar-count">{row.textesCount}</span>
                    </div>
                    <div className="compare-bar-wrap">
                      <span className="compare-bar-track">
                        <span className="compare-bar-fill" style={{ width: `${row.amendPct}%`, background: '#DFFF00' }} />
                      </span>
                      <span className="compare-bar-count">{row.amendCount}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {candidate.textes.length === 0 ? (
              <p className="donnees-text">Aucun texte porté publié pour ce mandat (rôle ou stade non retenus).</p>
            ) : (
              <>
                <div className="theme-pills">
                  {themePills.map((pill) => (
                    <button
                      key={pill.key}
                      type="button"
                      className={`theme-pill ${themeFilter === pill.key ? 'active' : ''}`}
                      onClick={() => setThemeFilter(pill.key)}
                    >
                      {pill.label}
                    </button>
                  ))}
                </div>

                <div className="theme-shelves">
                  {themeShelves.map((shelf) => (
                    <div key={shelf.label}>
                      <div className="shelf-header">
                        <span className="shelf-dot" />
                        <strong className="shelf-label">{shelf.label}</strong>
                      </div>
                      <div className="shelf-items">
                        {shelf.items.map((item) => (
                          <div className="shelf-item" key={item.titre}>
                            <div className="shelf-item-title">{item.titre}</div>
                            <div className="shelf-item-meta">{item.meta}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </>
        )}

        {tab === 'donnees' && (
          <div className="donnees-card">
            <span className="donnees-icon">i</span>
            <p className="donnees-text">
              Empreinte politique ne publie aucun taux individuel d&apos;assiduité, de présence ou d&apos;absence — un
              scrutin manqué ne décrit ni le travail parlementaire ni ses motifs.
            </p>
          </div>
        )}
    </main>
  );
}
