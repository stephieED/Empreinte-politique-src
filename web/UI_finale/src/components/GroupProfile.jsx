import '../styles/shell.css';
import './GroupProfile.css';
// Lot 1 (#326) : une seule définition des couleurs de vote, partagée.
// Lot 3 (#329) : la forme des règles de groupe, dont les règles vivent dans
// `utils/groupe.js`. Ce composant rend, il n'arbitre pas.
import { BadgeSource, ListeVide, PositionVote, Ratio, Troncature } from './Lecture';
import { OUTCOME_COLOR, formatNumber, styleForPosition } from '../utils/lecture';
import { LIBELLE_DENOMINATEUR_COHESION } from '../utils/groupe';

function initialsOf(nom) {
  return nom
    .split(' ')
    .map((p) => p[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();
}

/*
 * Les six décomptes d'un scrutin, jamais une barre (#329).
 *
 * Une barre de progression suggère une échelle du pire au meilleur ; ce sont
 * des catégories, et les colorier sur un dégradé fabriquerait un jugement
 * (AGENTS.md §2 règle 1). Les positions exprimées gardent la teinte du
 * DESIGN_SYSTEM ; « Non-votant », « Sans trace de vote » et « Excusés » n'en
 * portent aucune — la distinction se fait par la forme, comme dans le lot 1.
 */
function DecomptesCohesion({ decomptes }) {
  return (
    <ul className="gp-decomptes">
      {decomptes.map((d) => {
        const style = d.position ? styleForPosition(d.position) : null;
        const teinte = style?.color ?? null;
        return (
          <li className={`gp-decompte${teinte ? '' : ' gp-decompte--sans-teinte'}`} key={d.cle}>
            <span className="gp-decompte-valeur" style={teinte ? { color: teinte } : undefined}>
              {formatNumber(d.valeur)}
            </span>
            <span className="gp-decompte-label">{d.label}</span>
          </li>
        );
      })}
    </ul>
  );
}

/*
 * Ce qui est interdit sur une fiche de groupe est écrit, pas seulement omis
 * (#326, appliqué au groupe par #329). Une page qui se contente de ne pas
 * répondre laisse croire qu'elle n'y a pas pensé.
 */
function RefusDuGroupe({ refus }) {
  if (!refus?.length) return null;
  return (
    <div className="gp-refus">
      {refus.map((r) => (
        <div className="gp-refus-item" key={r.id}>
          <p className="gp-refus-sujet">{r.sujet}</p>
          <div>
            <p className="gp-refus-phrase">{r.phrase}</p>
            <p className="gp-refus-pourquoi">{r.pourquoi}</p>
          </div>
        </div>
      ))}
    </div>
  );
}

export default function GroupProfile({ group }) {
  // #653 : le statut se lit À LA DATE DE RÉFÉRENCE de la fiche, pas aujourd'hui.
  // « Actif » sur un groupe de la XVIe législature disait « encore député⋅e en
  // 2026 » — une propriété de la carrière de la personne, pas du groupe.
  const dateRefLabel = group.dateReferenceLabel || null;
  const datee = Boolean(group.dateReferenceDatee);
  const auDateRef = datee ? ` au ${dateRefLabel}` : '';

  const members = group.members.map((m) => ({
    nom: m.nom,
    initials: initialsOf(m.nom),
    // `null` n'est pas `false` : une appartenance non renseignée ne se publie
    // pas comme un départ (AGENTS.md §2 règle 5).
    statusLabel: m.present == null ? 'Appartenance non renseignée' : (m.present ? 'Membre' : 'Parti avant'),
    statusClass: m.present == null
      ? 'gp-member-status-inconnu'
      : (m.present ? 'gp-member-status-actif' : 'gp-member-status-ancien'),
  }));

  const amendmentSegments = group.amendmentSegments.map((s) => ({ ...s, color: OUTCOME_COLOR[s.key] }));

  const mandatsAgreges = group.mandatsAgreges || [];
  const couverture = group.couvertureRoster || {};

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

        {/* #653 : la date de référence est publiée À CÔTÉ des comptes qu'elle
            date. Un compteur daté qu'on ne peut pas dater à la lecture est un
            compteur nu (AGENTS.md §2 règle 2). Les 2 fiches Sénat gelées n'en
            portent pas : la page le dit, elle n'en invente pas une. */}
        <p className="gp-date-reference">
          {datee
            ? `Tous les comptes de cette fiche se rapportent au ${dateRefLabel}${group.dateReferenceOrigineLabel ? ` — ${group.dateReferenceOrigineLabel}` : ''}. La législature décrite est close : aucun de ces chiffres ne dit « aujourd'hui ».`
            : "Cette fiche ne publie aucune date de référence : ses décomptes ne se rapportent à aucune date précise, et ne doivent pas se lire comme « aujourd'hui »."}
        </p>

        <div className="gp-kpi-grid">
          {group.kpis.map((kpi) => (
            <div className="gp-kpi-card" key={kpi.label}>
              {kpi.denominator == null ? (
                <div className="gp-kpi-value">{formatNumber(kpi.numerator)}</div>
              ) : (
                <Ratio
                  denominator={kpi.denominator}
                  denominatorLabel={kpi.denominatorLabel}
                  numerator={kpi.numerator}
                />
              )}
              <div className="gp-kpi-label">{kpi.label}</div>
              <div className="gp-kpi-caveat">{kpi.caveat}</div>
            </div>
          ))}
        </div>

        <p className="gp-section-title">Cohésion de vote</p>
        {/* Six décomptes, jamais une barre : leur somme retrouve exactement
            l'effectif éligible (vérifié sur 19 832 / 19 832 entrées des 5
            fiches AN), et ce sont des catégories, pas une échelle (#329). */}
        {group.votes.length === 0 ? (
          <ListeVide
            cause={couverture.causeListeVide}
            motif={couverture.motifListeVide}
            source="Cohésion de vote agrégée à partir des profils publiés des membres du groupe."
          />
        ) : (
        <>
        <p className="gp-section-note">
          Par scrutin, six décomptes qui se somment exactement au nombre de membres éligibles.
          Le dénominateur est borné par chambre : un membre qui ne pouvait plus voter n'y figure pas.
          Les décomptes disent combien de membres ont pris chaque position ; la fiche ne nomme
          jamais qui s'est écarté de la position majoritaire.
          {group.publierExcuses
            ? null
            : " « Excusés » n'est pas publié sur cette fiche : la source ne renseigne cette valeur sur aucun de ses scrutins, et un zéro structurel n'est pas un zéro mesuré."}
        </p>
        <div className="gp-cohesion-grid">
          {group.votes.map((vote) => (
            <div className="gp-vote-card" key={vote.id ?? vote.texte}>
              <div className="gp-vote-position">
                <span className="gp-vote-position-titre">Position majoritaire</span>
                <PositionVote position={vote.position} />
              </div>
              <p className="gp-vote-texte">{vote.texte}</p>

              <p className="gp-vote-sous-titre">Alignés sur la position majoritaire</p>
              <Ratio
                denominator={vote.eligibles}
                denominatorLabel={LIBELLE_DENOMINATEUR_COHESION}
                numerator={vote.coherence.numerator}
              />

              <DecomptesCohesion decomptes={vote.decomptes} />

              {/* Le quorum est une comparaison à un seuil PUBLIÉ par la fiche
                  (`meta.seuil_quorum`), pas un seuil réglementaire : l'écrire
                  sans le seuil laisserait croire le contraire. */}
              <p className="gp-quorum">
                {vote.quorum.atteint == null
                  ? 'Quorum non renseigné pour ce scrutin.'
                  : `Quorum ${vote.quorum.atteint ? 'atteint' : 'non atteint'} — ${vote.quorum.participation.text} ont pris part, pour un seuil retenu de ${vote.quorum.seuilLabel ?? 'N/D'}.`}
              </p>

              <div className="gp-vote-footer">
                <BadgeSource url={vote.sourceUrl} />
                <span className="gp-vote-meta">{vote.date}</span>
              </div>
            </div>
          ))}
        </div>
        <Troncature
          rule={group.troncatureVotes.rule}
          shown={group.troncatureVotes.shown}
          total={group.troncatureVotes.total}
        />
        </>
        )}

        <p className="gp-section-title">Commissions et autres mandats</p>
        {/* #656 : « qui y siège » et « qui y est passé » sont deux nombres, pas
            un. 43 % des adhésions de commission publiées durent une journée ou
            moins — un⋅e député⋅e n'appartient qu'à une commission permanente à
            la fois, tout passage temporaire y est écrit comme un mandat. */}
        <p className="gp-section-note">
          Deux quantités par mandat, jamais une : qui y siégeait{auDateRef}, et qui y est passé au
          moins une fois. Numérateur et dénominateur, jamais un pourcentage seul.
          {datee ? null : " Faute de date de référence sur cette fiche, le premier compte n'est rapporté à aucune date."}
        </p>
        {mandatsAgreges.length === 0 ? (
          <ListeVide
            cause={couverture.causeListeVide}
            motif={couverture.motifListeVide}
            source="Mandats agrégés à partir des profils publiés des membres du groupe."
          />
        ) : (
        <div className="gp-mandats-grid">
          {mandatsAgreges.map((m) => (
            <div className="gp-mandat-card" key={`${m.categorie}-${m.label}`}>
              <span className="gp-mandat-category">{m.categorieLabel}</span>
              <p className="gp-mandat-label">{m.label}</p>
              <p className="gp-mandat-count">
                {m.siege == null
                  ? "Nombre de membres y siégeant : non publié sur cette fiche"
                  : (m.siege > 0
                    ? `${formatNumber(m.siege)} sur ${formatNumber(m.effectifReference)} membres y siégeaient${auDateRef}`
                    : `Aucun membre n'y siégeait${auDateRef}`)}
              </p>
              <p className="gp-mandat-count gp-mandat-count-cumul">
                {m.passe == null
                  ? 'Cumul historique non publié sur cette fiche'
                  : (m.passe > 1
                    ? `${formatNumber(m.passe)} membres y sont passés au moins une fois`
                    : `${formatNumber(m.passe)} membre y est passé au moins une fois`)}
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
                <ListeVide
                  cause={couverture.causeListeVide}
                  motif={couverture.motifListeVide}
                  source="Amendements agrégés à partir des profils publiés des membres du groupe."
                />
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
            {/* §2 règle 8 : des aides à la lecture, jamais des positions
                déclarées. Ces étiquettes sont les intitulés que le compte rendu
                de l'Assemblée donne aux débats où les membres sont intervenus :
                combattre un texte, c'est intervenir dessus autant que le
                défendre. Et chaque étiquette part avec son nombre de porteurs,
                sans quoi la fiche donnerait l'empreinte d'une personne pour
                celle d'un groupe (#657). */}
            <div className="gp-tags-card">
              {group.tags.length === 0 ? (
                <ListeVide
                  cause={couverture.causeListeVide}
                  motif={couverture.motifListeVide}
                  source="Étiquettes agrégées à partir des profils publiés des membres du groupe."
                />
              ) : (
                <>
                  <p className="gp-section-note gp-tags-note">
                    Les sujets sur lesquels les membres du groupe sont intervenus en séance, sous
                    l'intitulé que leur donne le compte rendu officiel de l'Assemblée. Chaque
                    étiquette porte le nombre de membres l'ayant abordée, sur les{' '}
                    {formatNumber(group.profilsDisponibles)} membres dont le profil est publié.
                    Ce n'est pas une position : intervenir sur un texte, c'est aussi bien le
                    combattre que le défendre.
                  </p>
                  {group.tags.map((tag) => (
                    <span className="gp-tag-pill" key={tag.label} title={tag.porteursTexte}>
                      {tag.label}{' '}
                      <span className="gp-tag-count">
                        {formatNumber(tag.porteurs)} / {formatNumber(tag.denominateur)}
                      </span>
                    </span>
                  ))}
                  <Troncature
                    rule={group.troncatureTags.rule}
                    shown={group.troncatureTags.shown}
                    total={group.troncatureTags.total}
                  />
                </>
              )}
            </div>
          </div>
        </div>

        <p className="gp-section-title">
          Membres couverts{datee ? ` — appartenance au ${dateRefLabel}` : ''}
        </p>
        {datee ? null : (
          <p className="gp-section-note">
            Cette fiche ne publie pas de date de référence : l'appartenance affichée est la
            dernière que la source ait publiée, et ne se rapporte à aucune date précise.
          </p>
        )}
        {members.length === 0 ? (
          <ListeVide
            cause={couverture.causeListeVide}
            motif={couverture.motifListeVide}
            source="Membres du groupe dont un profil est publié."
          />
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

        {/* `meta` est publié sur 7 / 7 fiches et rien ne le lisait (#329). La
            couverture du roster sans son état se lit comme une perte : 15
            profils sur 235 sur `groupe-Senat-LR` est un périmètre assumé, et la
            `preuve` le dit en toutes lettres. */}
        <p className="gp-section-title">Vérification</p>
        <div className="gp-verif">
          <div className="gp-verif-bloc">
            <p className="gp-verif-titre">Couverture du roster — {couverture.titre}</p>
            <Ratio
              caveat={couverture.phrase}
              denominator={couverture.profils?.denominator}
              denominatorLabel="membres relevés dans le groupe"
              numerator={couverture.profils?.numerator}
            />
            {couverture.preuve && <p className="gp-verif-preuve">{couverture.preuve}</p>}
          </div>

          <div className="gp-verif-bloc">
            <p className="gp-verif-titre">Seuil de quorum retenu</p>
            <p className="gp-verif-texte">
              {group.seuilQuorum == null
                ? "Cette fiche ne publie pas de seuil de quorum : les scrutins ne portent donc aucune mention de quorum."
                : `${formatNumber(Math.round(group.seuilQuorum * 100))} % des membres éligibles. C'est le seuil retenu pour cette fiche, pas un seuil réglementaire.`}
            </p>
          </div>

          {group.avertissements.length > 0 && (
            <div className="gp-verif-bloc">
              <p className="gp-verif-titre">Ce que cette fiche déclare sur elle-même</p>
              {/* Reproduits verbatim : ce sont les avertissements que le
                  pipeline a écrits DANS le fichier publié, et les résumer
                  reviendrait à les réécrire (AGENTS.md §2 règle 2). Ils sont
                  écrits pour la trace, pas pour la lecture courante : les
                  fiches de groupe ne portent pas encore le champ qui dit à qui
                  chaque avertissement s'adresse. */}
              <p className="gp-verif-texte gp-verif-chapeau">
                Avertissements écrits par le pipeline dans le fichier publié, reproduits mot pour
                mot. Ils s'adressent d'abord à qui vérifie la donnée.
              </p>
              <ul className="gp-verif-liste">
                {group.avertissements.map((a) => (
                  <li key={a}>{a}</li>
                ))}
              </ul>
            </div>
          )}

          {group.genereLe && (
            <div className="gp-verif-bloc">
              <p className="gp-verif-titre">Fiche générée le</p>
              <p className="gp-verif-texte">{group.genereLe}</p>
            </div>
          )}

          <div className="gp-verif-bloc">
            <p className="gp-verif-titre">Ce que cette fiche ne publie pas</p>
            <RefusDuGroupe refus={group.refus} />
          </div>
        </div>
    </main>
  );
}
