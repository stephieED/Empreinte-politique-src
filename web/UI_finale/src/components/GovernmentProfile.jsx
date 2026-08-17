import '../styles/shell.css';
import './GovernmentProfile.css';

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

export default function GovernmentProfile({ government }) {
  const members = government.membres.map((m) => ({
    nom: m.nom,
    initials: initialsOf(m.nom),
    portefeuille: m.portefeuille,
    period: m.period,
    statusLabel: m.actif ? 'Actif' : 'Ancien',
    statusClass: m.actif ? 'gvp-member-status-actif' : 'gvp-member-status-ancien',
  }));

  // Couverture des archives de dossiers législatifs (#399). Hors couverture,
  // l'absence de texte est une absence de source : elle ne doit jamais être
  // présentée comme un « 0 texte porté » constaté (AGENTS.md §2.5).
  const couverture = government.textesCouverture || {};
  const horsCouverture = couverture.statut === 'hors_couverture';
  const couvertureIncomplete = horsCouverture || couverture.statut === 'partielle';
  const messageTextesVides = couvertureIncomplete
    ? `Période non couverte par les archives ouvertes de l'Assemblée nationale (${couverture.label}) : le nombre de textes portés par ce gouvernement n'est pas mesurable ici. Ce n'est pas un « aucun texte porté ».`
    : 'Aucune donnée de texte disponible pour ce gouvernement.';

  return (
    <main className="gvp-main">
      <div className="gvp-breadcrumb">
        Gouvernement / <strong>{government.title}</strong>
      </div>

      <div className="gvp-banner">
        <span className="gvp-banner-tag">Gouvernement</span>
        <h1>{government.title}</h1>
        <p>{government.kicker}</p>
        <p className="gvp-banner-pm">
          Premier ministre : {government.premierMinistre || 'Non renseigné'}
        </p>
      </div>

      <p className="gvp-section-title">Textes portés — comptages par statut</p>
      {couvertureIncomplete && (
        <p className="gvp-coverage-note">
          {horsCouverture
            ? "Les archives ouvertes de l'Assemblée nationale ne couvrent pas cette période"
            : "Les archives ouvertes de l'Assemblée nationale ne couvrent qu'une partie de cette période"}{' '}
          ({couverture.label}). Les textes ci-dessous ne peuvent donc pas être
          considérés comme la liste complète de ceux portés par ce gouvernement,
          et une absence n'y vaut pas zéro.
        </p>
      )}
      {government.statutBadges.length === 0 ? (
        <p className="gvp-empty">
          {couvertureIncomplete
            ? 'Aucun comptage par statut ne peut être établi sur cette période — voir la note ci-dessus.'
            : 'Aucune donnée de statut disponible pour ce gouvernement.'}
        </p>
      ) : (
        <div className="gvp-statut-badges">
          {government.statutBadges.map((badge) => (
            <span className="gvp-statut-badge" key={badge.key}>
              {badge.count} {badge.label}
            </span>
          ))}
        </div>
      )}

      <p className="gvp-section-title">Textes suivis</p>
      {government.textes.length === 0 ? (
        <p className="gvp-empty">{messageTextesVides}</p>
      ) : (
        <div className="gvp-textes-grid">
          {government.textes.map((texte) => (
            <div className="gvp-texte-card" key={texte.dossierId}>
              <div className="gvp-texte-header">
                <span className="gvp-texte-statut">{texte.statutLabel}</span>
                {texte.sort493 && <span className="gvp-texte-493">Art. 49.3</span>}
              </div>
              <p className="gvp-texte-titre">{texte.titre}</p>
              <div className="gvp-texte-footer">
                {texte.sourceUrl ? (
                  <a className="gvp-verified-badge" href={texte.sourceUrl} target="_blank" rel="noreferrer">
                    <VerifiedIcon /> Source vérifiée
                  </a>
                ) : (
                  <span className="gvp-texte-nd">Source non renseignée</span>
                )}
                <span className="gvp-texte-meta">
                  {texte.chambre} · {texte.meta}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      <p className="gvp-section-title">Membres du gouvernement</p>
      {members.length === 0 ? (
        <p className="gvp-empty">Aucun membre disponible pour ce gouvernement.</p>
      ) : (
        <div className="gvp-members-grid">
          {members.map((member) => (
            <div className="gvp-member-row" key={member.nom}>
              <span className="gvp-member-avatar">{member.initials}</span>
              <div className="gvp-member-info">
                <span className="gvp-member-name">{member.nom}</span>
                <span className="gvp-member-portefeuille">
                  {member.portefeuille || 'Portefeuille non renseigné'}
                </span>
              </div>
              <span className={`gvp-member-status ${member.statusClass}`}>{member.statusLabel}</span>
            </div>
          ))}
        </div>
      )}
    </main>
  );
}
