/*
 * La fiche d'un candidat déclaré — lot 2 de la refonte #324 (issue #328).
 *
 * Sept sections, identiques pour les treize candidats déclarés, toujours dans
 * le même ordre. Ce qui varie est le contenu, jamais la forme — et chaque
 * emplacement est rempli à hauteur de ce que la donnée porte : uniformiser la
 * forme ne veut pas dire niveler le contenu.
 *
 * Ce composant REND. Les règles vivent dans `utils/profilCandidat.js` (#328),
 * les six fondations communes dans `utils/lecture.js` (#326) : les couleurs de
 * vote, les ratios, les troncatures, les listes vides et les badges de source
 * sont importés, jamais redéfinis. C'est exactement la duplication que le
 * lot 1 a supprimée.
 */
import '../styles/shell.css';
import './CandidateProfile.css';
import { BadgeSource, Interdits, ListeVide, PositionVote } from './Lecture';
import {
  LAST_READING_LABEL,
  LAST_READING_RULE,
  OUTCOME_COLOR,
  WHOLE_TEXT_VOTE_BOUND,
  formatNumber,
} from '../utils/lecture';
import {
  INSTITUTION_GOUVERNEMENT,
  INSTITUTION_MISSION,
  INSTITUTION_PARLEMENT,
  LIBELLE_ROLE_ABSENT,
  LIBELLE_ROLE_POINT,
  POSITION_NON_DECLAREE,
  RENDU_COUPLE,
  RENDU_PODIUM,
  SORT_NON_PUBLIE,
  libellePosition,
  motifPosition,
  positionSurAxe,
} from '../utils/profilCandidat';

const MOIS = [
  'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
  'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre',
];

function jour(iso) {
  if (!iso) return null;
  const [a, m, j] = iso.split('-');
  if (!a) return null;
  if (!m) return a;
  return `${Number(j)} ${MOIS[Number(m) - 1]} ${a}`;
}

function annee(iso) {
  return iso ? iso.slice(0, 4) : null;
}

function periode(debut, fin, actif) {
  if (actif) return `depuis le ${jour(debut)}`;
  return `${jour(debut)} → ${jour(fin)}`;
}

/*
 * Un en-tête de section : son numéro, son titre, et le critère qui dit ce que
 * la section montre ET ce qu'elle refuse de montrer. Le critère est du contenu
 * publié, pas une légende décorative — c'est lui qui empêche de lire un
 * décompte comme une note.
 */
function Section({ numero, titre, critere, children }) {
  return (
    <section className="cp-section">
      <div className="cp-section-bande">
        <span className="cp-section-numero">{numero}</span>
        <span className="cp-section-trait" />
      </div>
      <h2 className="cp-section-titre">{titre}</h2>
      {critere && <p className="cp-section-critere">{critere}</p>}
      <div className="cp-section-corps">{children}</div>
    </section>
  );
}

/*
 * Une pastille de position déclarée. Elle accompagne TOUJOURS le chiffre
 * qu'elle explique, jamais renvoyée en légende de bas de page : « 1 968
 * déposés, 67 adoptés » doit porter « groupe déclaré d'opposition » sur la même
 * ligne, sinon le lecteur lit une incompétence là où il y a une fonction.
 */
function Position({ position }) {
  const motif = motifPosition(position);
  return (
    <span className={`cp-position cp-position--${motif}`}>{libellePosition(position)}</span>
  );
}

/* ── § 1 — le parcours ───────────────────────────────────────────────────────
 *
 * UNE seule bande, une ligne par rôle, ordonnées par date de début, quelle que
 * soit l'institution : rien n'est au-dessus parce que c'est la date qui range.
 * La bande ne porte AUCUN texte — un libellé dans un segment de 2 % ne tient
 * pas, quelle que soit sa position. Des repères numérotés la surmontent et la
 * liste dessous porte les intitulés complets : la frise donne la silhouette, la
 * liste la nomme.
 */
const ECART_MINIMAL_REPERES = 3.4;

function classeInstitution(role) {
  if (role.institution === INSTITUTION_MISSION) return 'cp-fs--mission';
  if (role.institution === INSTITUTION_GOUVERNEMENT) {
    return role.chef ? 'cp-fs--chef' : 'cp-fs--gouvernement cp-fs--motif-rayures';
  }
  return `cp-fs--parlement cp-fs--motif-${motifPosition(role.position)}`;
}

const LEGENDE_FRISE = [
  { classe: 'cp-fs--parlement cp-fs--motif-plein', label: 'Parlementaire · groupe majoritaire' },
  { classe: 'cp-fs--parlement cp-fs--motif-diagonales', label: "Parlementaire · groupe d'opposition" },
  { classe: 'cp-fs--parlement cp-fs--motif-points', label: 'Parlementaire · groupe minoritaire' },
  { classe: 'cp-fs--parlement cp-fs--motif-fines-rayures', label: POSITION_NON_DECLAREE.label },
  { classe: 'cp-fs--gouvernement cp-fs--motif-rayures', label: 'Membre du gouvernement' },
  { classe: 'cp-fs--chef', label: 'Chef du gouvernement' },
  { classe: 'cp-fs--mission', label: 'Parlementaire en mission auprès d’un ministère' },
];

function Frise({ parcours }) {
  const { roles, nbLignes, bornes } = parcours;
  if (!roles.length || !bornes) return null;

  const hauteurLigne = 100 / nbLignes;

  // Repères : un numéro par rôle. Repliés sur un second niveau quand deux
  // débuts sont trop proches pour ne pas se chevaucher.
  const niveaux = [-Infinity, -Infinity];
  const reperes = roles.map((r) => {
    const x = positionSurAxe(r.debut, bornes);
    let n = 0;
    if (x - niveaux[0] < ECART_MINIMAL_REPERES) n = x - niveaux[1] < ECART_MINIMAL_REPERES ? 0 : 1;
    niveaux[n] = x;
    return { numero: r.numero, x, niveau: n };
  });
  const deuxNiveaux = reperes.some((r) => r.niveau === 1);

  return (
    <div className="cp-carte cp-frise">
      <div className="cp-reperes" style={{ height: deuxNiveaux ? 46 : 30 }}>
        {reperes.map((r) => (
          <span
            className="cp-repere"
            key={r.numero}
            style={{ left: `${r.x.toFixed(2)}%`, top: r.niveau === 0 ? 0 : '38%', height: r.niveau === 0 ? '100%' : '62%' }}
          >
            <b>{r.numero}</b>
            <i />
          </span>
        ))}
      </div>

      <div className="cp-bande">
        {roles.map((r) => {
          const gauche = positionSurAxe(r.debut, bornes);
          const largeur = Math.max(0.6, positionSurAxe(r.fin, bornes) - gauche);
          return (
            <span
              className={`cp-fs ${classeInstitution(r)}`}
              key={r.numero}
              style={{
                left: `${gauche.toFixed(2)}%`,
                width: `${largeur.toFixed(2)}%`,
                top: `${(r.ligne * hauteurLigne).toFixed(2)}%`,
                height: `${hauteurLigne.toFixed(2)}%`,
              }}
              title={`${r.role} — ${periode(r.debut, r.fin, r.actif)}`}
            />
          );
        })}
      </div>

      <div className="cp-axe">
        <span>{annee(bornes.debut)}</span>
        <span>{annee(bornes.fin)}</span>
      </div>

      <div className="cp-legende">
        <p className="cp-legende-titre">Légende</p>
        <div className="cp-legende-grille">
          {LEGENDE_FRISE.map((l) => (
            <span className="cp-legende-item" key={l.label}>
              <span className={`cp-legende-pave ${l.classe}`} />
              {l.label}
            </span>
          ))}
        </div>
        <p className="cp-legende-note">
          <b>La teinte porte l’institution, le motif porte la position.</b> Les deux familles sont
          désaturées et n’évoquent aucun parti ; elles ne forment aucune progression — ce sont deux
          catégories, pas deux niveaux. Le vert et le rouge restent réservés aux positions de vote.
          La couleur ne porte jamais seule : chaque situation se distingue aussi par son motif et
          reste lisible en niveaux de gris. Majorité, minorité et opposition sont les trois valeurs
          que <b>l’Assemblée nationale publie elle-même</b> sur chaque groupe politique ; elle ne
          les publie pas pour la législature en cours.
          {nbLignes > 1 && (
            <>
              {' '}
              Quand deux rôles se chevauchent, la bande se scinde et le rôle commencé le premier
              occupe la ligne du haut : <b>c’est un rangement, pas une hiérarchie.</b>
            </>
          )}
        </p>
      </div>

      <ul className="cp-roles">
        {roles.map((r) => (
          <li className="cp-role" key={r.numero}>
            <span className="cp-role-numero">{r.numero}</span>
            <span className="cp-role-dates">{periode(r.debut, r.fin, r.actif)}</span>
            <span className="cp-role-intitule">
              <b>{r.role}</b>
              {r.institution === INSTITUTION_PARLEMENT && <Position position={r.position} />}
              {r.detail && <span className="cp-role-detail"> · {r.detail}</span>}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/*
 * Les fonctions qu'on choisit d'exercer. Un bloc par catégorie, jamais un
 * total : un groupe d'amitié et une commission d'enquête ne s'additionnent pas.
 */
function Fonctions({ fonctions }) {
  if (!fonctions.length) return null;
  return (
    <div className="cp-carte cp-fonctions">
      {fonctions.map((c) => (
        <div className="cp-fonctions-bloc" key={c.cle}>
          <p className="cp-fonctions-titre">
            {c.titre} · <span className="cp-num">{formatNumber(c.total)}</span>{' '}
            {c.total > 1 ? 'mandats' : 'mandat'}
          </p>
          <div className="cp-puces">
            {c.items.map((i) => (
              <span className="cp-puce" key={i.label}>
                {i.label}
                {i.n > 1 && <b className="cp-num">{i.n}</b>}
              </span>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

/*
 * Une barre empilée générique. Les segments portent leur couleur en `style`
 * pour que la source de vérité reste `OUTCOME_COLOR` (lot 1) ; un segment sans
 * couleur reçoit un motif hachuré, jamais une teinte de repli — c'est ce qui
 * distingue « sort non publié » d'un sort.
 */
function Barre({ segments, total }) {
  if (!total) return null;
  return (
    <>
      <div className="cp-barre">
        {segments.map((s) => (
          <span
            className={`cp-barre-seg${s.color ? '' : ' cp-barre-seg--sans-teinte'}`}
            key={s.cle}
            style={{ width: `${((s.n / total) * 100).toFixed(2)}%`, background: s.color || undefined }}
          />
        ))}
      </div>
      <div className="cp-cles">
        {segments.map((s) => (
          <span className="cp-cle" key={s.cle}>
            <i
              className={s.color ? undefined : 'cp-cle-pastille--sans-teinte'}
              style={s.color ? { background: s.color } : undefined}
            />
            {s.label} <b className="cp-num">{formatNumber(s.n)}</b>
          </span>
        ))}
      </div>
    </>
  );
}

/* ── § 2 — les gouvernements dont il a été membre ────────────────────────────
 *
 * En ensembles, jamais en liste attribuée. Cette section précède les actes
 * personnels parce qu'elle en donne le contexte, non parce qu'elle vaudrait
 * davantage.
 */
const LIBELLE_STATUT_TEXTE = {
  promulgue: 'promulgué',
  adopte: 'adopté',
  adopte_cmp: 'adopté en CMP',
  adopte_49_3: 'adopté sans vote (49.3)',
  navette_en_cours: 'en navette',
  rejete: 'rejeté',
  rejete_49_3: 'rejeté après 49.3',
  retire: 'retiré',
  depose: 'déposé',
};

const COULEUR_STATUT = {
  promulgue: '#14151A',
  adopte_cmp: '#4F9B77',
  adopte: OUTCOME_COLOR['adopté'],
  navette_en_cours: '#8B8794',
  rejete: OUTCOME_COLOR['rejeté'],
  retire: OUTCOME_COLOR['retiré'],
  depose: '#DCD9D3',
};

function Gouvernements({ gouvernements, cause, voix }) {
  if (!gouvernements.length) {
    return (
      <div className="cp-carte">
        <ListeVide
          cause={cause}
          motif={`${voix.Sujet} n’a jamais été membre d’un gouvernement. C’est un fait établi, pas une donnée manquante : ses mandats sont collectés et aucun n’est une fonction gouvernementale.`}
        />
      </div>
    );
  }

  return (
    <>
      <div className="cp-carte">
        {gouvernements.map((g) => {
          const segments = g.statuts.map((s) => ({ cle: s.cle, label: s.label, n: s.n, color: COULEUR_STATUT[s.cle] }));
          if (g.adoptesSansVote > 0) {
            segments.push({ cle: '49_3', label: 'adoptés sans vote (49.3)', n: g.adoptesSansVote, color: null });
          }
          return (
            <div className={`cp-gouv${g.chef ? ' cp-gouv--chef' : ''}`} key={g.id}>
              <div className="cp-gouv-tete">
                <span className="cp-gouv-nom">{g.nom}</span>
                <span className="cp-gouv-periode cp-num">
                  {periode(g.debut, g.fin, g.actif)} · {formatNumber(g.total)} textes suivis
                </span>
              </div>
              <p className="cp-gouv-fonction">
                Sa fonction :{' '}
                {g.fonctions.map((f, i) => (
                  <span key={`${f.portefeuille}-${f.debut}`}>
                    {i > 0 && ', puis '}
                    {f.portefeuille}
                  </span>
                ))}
              </p>
              <Barre segments={segments} total={g.total} />
              {g.total === 0 && (
                <p className="cp-gouv-49">
                  Aucun texte n’est rattaché à ce gouvernement dans le corpus. C’est un vide de
                  collecte, pas un bilan : <em>rien ici ne dit qu’il n’en a porté aucun.</em>
                </p>
              )}
              <p className="cp-gouv-49" hidden={g.total === 0}>
                {g.adoptesSansVote > 0 ? (
                  <>
                    Dont <b className="cp-num">{g.adoptesSansVote}</b> texte
                    {g.adoptesSansVote > 1 ? 's adoptés' : ' adopté'} sans vote, par l’article 49.3 —{' '}
                    <em>un fait de procédure, jamais une position de vote</em>.
                  </>
                ) : (
                  'Aucun texte adopté par l’article 49.3.'
                )}
              </p>
              {g.textes && (
                <ul className="cp-nommes">
                  {g.textes.map((t) => (
                    <li className="cp-nomme" key={`${t.titre}-${t.date}`}>
                      <span className="cp-nomme-cle">{LIBELLE_STATUT_TEXTE[t.statut] || t.statut}</span>
                      <span>{t.titre}</span>
                      <span className="cp-nomme-date cp-num">{jour(t.date)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          );
        })}
      </div>
      <p className="cp-note">
        <b>Un bilan de gouvernement est collectif.</b> Ces textes ne sont pas ses propositions : ce
        sont ceux que le gouvernement dont {voix.pronom} était membre a portés. <em>Un chef du gouvernement
        les signe tous — lui en attribuer un personnellement ne voudrait rien dire, et c’est
        pourquoi cette section montre des ensembles et non des actes individuels.</em> L’état des
        textes est celui d’aujourd’hui, pas celui du jour où le gouvernement a pris fin. Il ne
        s’additionne à aucun autre décompte de la page.
      </p>
    </>
  );
}

/* ── § 3 — ce qu'il a proposé ────────────────────────────────────────────── */
function Propositions({ amendements, textes, causeAmendements, causeTextes, voix }) {
  return (
    <>
      {amendements.totalAuteur === 0 ? (
        <div className="cp-carte">
          <ListeVide cause={causeAmendements} source="Amendements déposés comme auteur principal" />
        </div>
      ) : (
        <div className="cp-carte">
          {amendements.legislatures.map((leg) => (
            <div className="cp-ligne" key={leg.legislature}>
              <div className="cp-ligne-cle">
                Auteur d’amendements
                <Position position={leg.position} />
              </div>
              <div className="cp-ligne-corps">
                <p className="cp-ligne-titre">{leg.legislature}<sup>e</sup> législature</p>
                <Barre
                  segments={leg.sorts.map((s) => ({
                    cle: s.cle,
                    label: s.label,
                    n: s.n,
                    color: s.cle === SORT_NON_PUBLIE ? null : OUTCOME_COLOR[s.cle] || null,
                  }))}
                  total={leg.total}
                />
              </div>
              <div className="cp-ligne-nombre cp-num">
                {formatNumber(leg.total)}
                <span>déposés</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {amendements.irrecevabilites.length > 0 && (
        <div className="cp-blocs">
          {amendements.irrecevabilites.map((b) => (
            <div className="cp-carte cp-bloc" key={b.base}>
              <b className="cp-bloc-nombre cp-num">{formatNumber(b.n)}</b>
              <p className="cp-bloc-cle">{b.titre}</p>
              <p className="cp-bloc-texte">{b.explication}</p>
            </div>
          ))}
        </div>
      )}

      {textes.total === 0 ? (
        <div className="cp-carte">
          <ListeVide cause={causeTextes} source="Textes portés comme auteur ou rapporteur" />
        </div>
      ) : (
        <div className="cp-carte cp-textes">
          <div className="cp-gouv-tete">
            <span className="cp-gouv-nom">Où en sont les textes {voix.quil} a portés</span>
            <span className="cp-gouv-periode cp-num">
              {formatNumber(textes.publies.length)} publiés · {formatNumber(textes.promulgues)}{' '}
              promulgué{textes.promulgues > 1 ? 's' : ''}
            </span>
          </div>
          {textes.publies.length > 0 && (
            <Barre
              segments={textes.repartition.map((s) => ({
                cle: s.cle,
                label: s.label,
                n: s.n,
                color: s.cle === 'promulgue' ? '#14151A' : null,
              }))}
              total={textes.publies.length}
            />
          )}
          {textes.ecartes.total > 0 && (
            <p className="cp-note">
              <b>
                {textes.ecartes.total} de ses {textes.total} textes ne sont pas affiché
                {textes.ecartes.total > 1 ? 's' : ''}
              </b>{' '}
              : {textes.ecartes.deposes > 0 &&
                `${textes.ecartes.deposes} ${textes.ecartes.deposes > 1 ? 'ont' : 'a'} été déposé${textes.ecartes.deposes > 1 ? 's' : ''} sans jamais être examiné${textes.ecartes.deposes > 1 ? 's' : ''} en commission`}
              {textes.ecartes.deposes > 0 && textes.ecartes.sansStade > 0 && ', '}
              {textes.ecartes.sansStade > 0 &&
                `${textes.ecartes.sansStade} ne porte${textes.ecartes.sansStade > 1 ? 'nt' : ''} pas de stade procédural`}
              .{' '}
              <em>
                La règle éditoriale du dépôt ne publie par défaut que les textes ayant atteint
                l’examen en commission.
              </em>
            </p>
          )}
          <ul className="cp-nommes">
            {textes.publies.map((t) => (
              <li className="cp-nomme" key={`${t.titre}-${t.dateMax}`}>
                <span className="cp-nomme-cle">{t.role}</span>
                <span>
                  {t.titre}
                  {t.projetDeLoi && <span className="cp-marque">projet de loi</span>}
                </span>
                <span className="cp-nomme-date cp-num">
                  {t.stade} · {annee(t.dateMax)}
                </span>
              </li>
            ))}
          </ul>
          {textes.projetsDeLoi > 0 && (
            <p className="cp-note">
              <b>
                {textes.projetsDeLoi} de ses {textes.total} textes portés sont des projets de loi
              </b>
              , c’est-à-dire des textes du gouvernement signés comme ministre. Le corpus les range
              sous le même rôle « auteur » qu’une proposition déposée comme parlementaire :{' '}
              <em>la distinction se lit dans l’intitulé officiel, aucun champ ne la porte.</em>
            </p>
          )}
        </div>
      )}
    </>
  );
}

/* ── § 4 — ce qu'il a dit, et en quelle qualité ─────────────────────────────── */
function Paroles({ interventions, cause, voix }) {
  const { total, natures, qualite, questions } = interventions;

  if (!total) {
    return (
      <div className="cp-carte">
        <ListeVide cause={cause} source="Interventions en séance et en commission" />
      </div>
    );
  }

  return (
    <>
      <div className="cp-carte cp-bloc">
        {qualite.regime === 'source' && (
          <>
            <span className="cp-etiquette cp-etiquette--pleine">qualité publiée par la source</span>
            <p className="cp-section-critere">
              Le compte rendu publie la qualité de l’orateur sur la totalité de ses{' '}
              <b>{formatNumber(total)}</b> interventions.
            </p>
          </>
        )}
        {qualite.regime === 'partiel' && (
          <>
            <span className="cp-etiquette cp-etiquette--pleine">qualité publiée sur une partie</span>
            <p className="cp-section-critere">
              Le compte rendu publie la qualité de l’orateur sur{' '}
              <b>{formatNumber(qualite.sourcees)}</b> de ses {formatNumber(total)} interventions.
              Les {formatNumber(total - qualite.sourcees)} restantes n’en portent aucune : la source
              ne le dit pas, nous non plus. Ces deux régimes ne se confondent pas, et rien ici ne
              comble le second avec le premier.
            </p>
          </>
        )}
        {qualite.regime === 'derive' && (
          <>
            <span className="cp-etiquette">qualité dérivée des mandats</span>
            <p className="cp-section-critere">
              La source ne publie la qualité de l’orateur que pour une fonction{' '}
              <b>particulière</b> — ministre, rapporteur. Elle est absente des{' '}
              <b>{formatNumber(total)}</b> interventions de ce profil. Lire ce silence comme « {voix.pronom}
              parlait comme {voix.depute} » est une <b>inférence de notre part</b>, licite parce que
              ses mandats disent qu’{voix.pronom === 'il' ? 'il' : voix.pronom} n’exerçait aucune autre fonction à ces dates.{' '}
              <em>Aucune source ne l’affirme.</em>
            </p>
          </>
        )}

        <ul className="cp-mesures">
          {natures.map((n) => (
            <li className="cp-mesure" key={n.label}>
              <span>{n.label}</span>
              <b className="cp-num">{formatNumber(n.n)}</b>
            </li>
          ))}
        </ul>
      </div>

      {qualite.sourcee && (
        <div className="cp-carte cp-bloc">
          <p className="cp-section-critere">
            La qualité telle que le compte rendu l’écrit, sans regroupement de notre part.
          </p>
          <ul className="cp-mesures">
            {qualite.fonctions.map((f) => (
              <li className="cp-mesure" key={f.label}>
                <span>{f.label}</span>
                <b className="cp-num">{formatNumber(f.n)}</b>
              </li>
            ))}
          </ul>
        </div>
      )}

      {questions && (
        <div className="cp-carte cp-bloc">
          <p className="cp-section-critere">
            {questions.sens === 'recues' ? (
              <>
                <b>Ce sur quoi {voix.pronom} a été interpellé{voix.accorde}.</b>{' '}
                {formatNumber(questions.ministerielles)}{' '}
                de ses {formatNumber(questions.total)} questions au gouvernement portent une
                qualité ministérielle publiée par la source, à une date où {voix.pronom} était membre
                d’un gouvernement : {voix.pronom} y a répondu, {voix.pronom} ne les a pas posées.
                Sans cette distinction, ce bloc serait exactement inversé.
              </>
            ) : (
              <>
                <b>Ce sur quoi {voix.pronom} a interpellé le gouvernement.</b> Ses{' '}
                {formatNumber(questions.total)} questions au gouvernement ne portent{' '}
                <b>aucune qualité ministérielle</b> : {voix.pronom} les a posées.
              </>
            )}
          </p>
          <div className="cp-puces">
            {questions.sujets.map((s) => (
              <span className="cp-puce" key={s.label}>
                {s.label}
                <b className="cp-num">{s.n}</b>
              </span>
            ))}
          </div>
        </div>
      )}
    </>
  );
}

/* ── § 5 — ce qu'il a voté ─────────────────────────────────────────────────── */
function Votes({ votes, cause, voix }) {
  if (!votes.total) {
    return (
      <div className="cp-carte">
        <ListeVide cause={cause} source="Positions de vote publiées" />
      </div>
    );
  }

  const max = Math.max(...votes.parAnnee.map((a) => a.n), 1);

  return (
    <>
      <div className="cp-carte cp-bloc">
        <p className="cp-section-critere">
          Ses positions par année, sur un axe continu. Une année sans barre n’est jamais
          publiée comme un chiffre nu : elle dit sa situation.
        </p>
        <div className="cp-annees">
          {votes.parAnnee.map((a) => (
            <div className={`cp-annee cp-annee--${a.situation}`} key={a.annee}>
              <em className="cp-num">{a.n > 0 ? formatNumber(a.n) : ''}</em>
              <i style={{ height: `${Math.max(4, (a.n / max) * 100).toFixed(0)}%` }} />
              <b className="cp-num">{a.annee}</b>
            </div>
          ))}
        </div>
        <div className="cp-cles">
          <span className="cp-cle">
            <i style={{ background: '#14151A' }} />
            année de mandat parlementaire
          </span>
          {votes.parAnnee.some((a) => a.situation === 'gouvernement') && (
            <span className="cp-cle">
              <i className="cp-cle-pastille--gouvernement" />
              fonction gouvernementale — voter était impossible
            </span>
          )}
          {votes.parAnnee.some((a) => a.situation === 'hors_mandat') && (
            <span className="cp-cle">
              <i className="cp-cle-pastille--hors-mandat" />
              aucun mandat parlementaire cette année-là — {voix.pronom} n’avait rien à voter
            </span>
          )}
        </div>
      </div>

      {votes.aExerceAuGouvernement && (
        <p className="cp-note">
          <b>Un membre du gouvernement ne vote pas.</b> Sur ses {formatNumber(votes.total)}{' '}
          positions, <b>{formatNumber(votes.pendantGouvernement)}</b>{' '}
          {votes.pendantGouvernement > 1 ? 'ont été émises' : 'a été émise'} pendant l’une de ses
          fonctions gouvernementales. Ce n’est pas une lacune de collecte, c’est un fait
          établi sur la personne — sans cette phrase, ces années se liraient comme une absence.
        </p>
      )}

      {!votes.derniereLectureDisponible ? (
        <div className="cp-carte">
          <ListeVide
            cause="non_collecte"
            motif="L’index des scrutins n’a pas pu être lu. Sans lui, la dernière lecture de chaque texte n’est pas déterminable, et un décompte non replié afficherait une position de première lecture comme sa position sur la loi."
          />
        </div>
      ) : votes.surEnsemble === 0 ? (
        <div className="cp-carte">
          <ListeVide
            cause="couvert"
            motif="Aucune de ses positions ne porte sur l’ensemble d’un texte au sens de la règle publiée ci-dessous. Ses autres positions — sur un article, sur un amendement — restent comptées dans le total."
          />
        </div>
      ) : votes.textes === 0 ? (
        <div className="cp-carte">
          <ListeVide
            cause="couvert"
            motif="Toutes ses positions sur l’ensemble d’un texte portent sur une lecture qu’un scrutin plus tardif a suivie, et il n’a pas de position enregistrée sur ces dernières lectures. Nous ne pouvons pas dire pourquoi, et le dire serait publier une absence individuelle."
          />
        </div>
      ) : (
        <div className="cp-carte cp-bloc">
          <div className="cp-votes-barre">
            {votes.positions.map((p) => (
              <div className="cp-votes-seg" key={p.position} style={{ flex: p.n }}>
                <PositionVote position={p.position} />
                <b className="cp-num">{formatNumber(p.n)}</b>
              </div>
            ))}
          </div>
          <div className="cp-regles">
            <span className="cp-regle">
              {formatNumber(votes.textes)} textes — {LAST_READING_LABEL}
            </span>
            <span className="cp-regle">
              tirés de {formatNumber(votes.surEnsemble)} votes sur l’ensemble d’un texte, parmi{' '}
              {formatNumber(votes.total)} positions
            </span>
            <span className="cp-regle">absences jamais publiées</span>
            <span className="cp-regle">un plancher, pas un relevé exhaustif</span>
          </div>
        </div>
      )}

      <p className="cp-note">
        <b>{LAST_READING_RULE.phrase}</b> {LAST_READING_RULE.pourquoi}
      </p>

      <p className="cp-note">
        <b>{WHOLE_TEXT_VOTE_BOUND.phrase}</b> {WHOLE_TEXT_VOTE_BOUND.pourquoi}
      </p>
    </>
  );
}

/* ── § 6 — où il s'est écarté des siens ─────────────────────────────────────
 *
 * Scrutin par scrutin, JAMAIS totalisé : « a voté contre son groupe N fois »
 * serait une note, pas un fait. Deux positions sourcées posées côte à côte ; la
 * lecture appartient au lecteur.
 */
function Ecarts({ ecarts, voix }) {
  if (!ecarts.comparable) {
    return (
      <div className="cp-carte">
        <ListeVide
          cause="hors_couverture"
          motif={
            ecarts.fiches.length
              ? 'Aucune fiche de groupe publiée ne recouvre ses périodes de mandat de façon exploitable : aucun scrutin n’est commun à ses votes et aux fiches disponibles.'
              : 'Aucune fiche de groupe n’est publiée pour les groupes où cette personne a siégé. Il n’y a donc rien à comparer — ce n’est pas l’absence d’écart.'
          }
        />
      </div>
    );
  }

  if (!ecarts.ecarts.length) {
    return (
      <div className="cp-carte">
        <ListeVide
          cause="couvert"
          motif={
            ecarts.communs > 1
              ? `Sur les ${formatNumber(ecarts.communs)} scrutins communs à ses votes et aux fiches de groupe publiées, aucun vote sur l’ensemble d’un texte ne diverge de la position majoritaire de son groupe.`
              : 'Un seul scrutin est commun à ses votes et aux fiches de groupe publiées, et il ne diverge pas. Un scrutin ne dit rien : ce vide mesure la comparaison possible, pas son comportement.'
          }
        />
      </div>
    );
  }

  return (
    <>
      <p className="cp-section-critere">
        Relevé sur les {formatNumber(ecarts.communs)} scrutins communs à ses votes et aux fiches
        de groupe publiées, et restreint aux votes sur l’ensemble d’un texte.
      </p>
      <div className="cp-carte">
        {ecarts.ecarts.map((e) => (
          <div className="cp-ecart" key={e.scrutinId}>
            <div>
              <p className="cp-ligne-titre">{e.texte}</p>
              <p className="cp-ecart-meta cp-num">
                {jour(e.date)} · groupe {e.groupe} · {e.legislature}
                <sup>e</sup> législature
              </p>
              <BadgeSource url={e.sourceUrl} />
            </div>
            <div className="cp-ecart-positions">
              <span className="cp-ecart-ligne">
                <span>{voix.pronom}</span>
                <PositionVote position={e.position} />
              </span>
              <span className="cp-ecart-ligne">
                <span>son groupe</span>
                <PositionVote position={e.positionGroupe} />
              </span>
            </div>
          </div>
        ))}
      </div>
    </>
  );
}

/* ── § 7 — ce qu'on n'a pas pu lire ─────────────────────────────────────────── */
const LIBELLE_ETAT = {
  couvert: 'couvert',
  hors_couverture: 'hors couverture',
  non_collecte: 'non collecté',
  fait_etabli: 'fait établi',
};

function Couverture({ couverture, limites }) {
  return (
    <>
      <div className="cp-carte">
        {couverture.map((c) => (
          <div className="cp-ligne cp-ligne--couverture" key={c.cle}>
            <span className="cp-ligne-cle">{c.titre}</span>
            <span className="cp-ligne-corps">
              {c.etats.map((e) => (
                <span className="cp-etat" key={`${e.etat}-${e.debut}-${e.fin}`}>
                  <b>{LIBELLE_ETAT[e.etat] || e.etat}</b>
                  {e.debut && ` depuis le ${jour(e.debut)}`}
                  {!e.debut && e.fin && ` jusqu’au ${jour(e.fin)}`}
                  {e.preuve && <em>{e.preuve}</em>}
                </span>
              ))}
            </span>
            <span className="cp-ligne-nombre cp-num">
              {formatNumber(c.decompte)}
              <span>entrées</span>
            </span>
          </div>
        ))}
      </div>
      {limites.map((l) => (
        <p className="cp-note" key={l.cle}>
          {l.texte}
        </p>
      ))}
      <Interdits />
    </>
  );
}

/* ── § L'essentiel — un point, rendu selon son cas ───────────────────────────
 *
 * « Ne pas se mettre de contrainte à utiliser la même solution pour chacun des
 * points » : la forme suit le cas. Trois rendus, et le choix est justifié point
 * par point dans `utils/profilCandidat.js`.
 *
 * Aucun jaune signal nulle part ici : DESIGN_SYSTEM §3 le réserve à la
 * sélection, à l'action et à la source vérifiée. Un filet jaune sous une
 * répartition lui ferait dire « regardez ça », c'est-à-dire un jugement.
 */

/* Répartition en barre — les trois premières commissions saisies au fond.
 *
 * UN SEUL TON pour les trois segments, séparés par un filet : deux commissions
 * à égalité doivent produire deux segments IDENTIQUES. Les teinter par rang
 * placerait les commissions sur une échelle, ce que la fiche de groupe a
 * précisément retiré en #329 (§2 règle 1).
 *
 * Les segments sont proportionnels au décompte réel sur le TOTAL des dossiers,
 * jamais normalisés à 100 % : ce qui reste — autres commissions, dossiers sans
 * commission publiée — reste visible comme du vide, et la légende le chiffre.
 */
function Repartition({ repartition }) {
  const { titre, segments, total, reste, sansCommission } = repartition;
  return (
    <span className="cp-point-repartition">
      <span className="cp-point-repartition-titre">{titre}</span>
      <span className="cp-barre cp-barre--sombre">
        {segments.map((s) => (
          <span
            className="cp-barre-seg cp-barre-seg--uni"
            key={s.sigle}
            style={{ width: `${(s.n / total) * 100}%` }}
          />
        ))}
      </span>
      <span className="cp-cles cp-cles--sombre">
        {segments.map((s) => (
          <span className="cp-cle" key={s.sigle}>
            <i className="cp-pastille" />
            {s.sigle} <b>{formatNumber(s.n)}</b>
          </span>
        ))}
      </span>
      {(reste > 0 || sansCommission > 0) && (
        <span className="cp-point-socle">
          {[
            reste > 0
              ? `${formatNumber(reste)} ${reste > 1 ? 'autres commissions' : 'autre commission'}`
              : null,
            sansCommission > 0
              ? `${formatNumber(sansCommission)} ${sansCommission > 1 ? 'dossiers' : 'dossier'} dont la source ne publie pas la commission saisie au fond`
              : null,
          ]
            .filter(Boolean)
            .join(' ; ')}
        </span>
      )}
    </span>
  );
}

/* Podium — trois colonnes de hauteur proportionnelle. « 27 sur 60 » se compare
 * mal en prose ; trois hauteurs se comparent d'un regard. C'est un décompte de
 * mandats, pas une note : rien n'y est bon ou mauvais, et deux colonnes égales
 * se voient égales. */
function Podium({ rangs }) {
  const haut = Math.max(...rangs.map((r) => r.n));
  return (
    <span className="cp-podium">
      {rangs.map((r) => (
        <span className="cp-podium-col" key={r.label}>
          <b className="cp-num">{formatNumber(r.n)}</b>
          <i style={{ height: `${Math.max(6, (r.n / haut) * 46)}px` }} />
          <span>{r.label}</span>
        </span>
      ))}
    </span>
  );
}

function Point({ point: p, montrerLeRole }) {
  const couple = p.rendu === RENDU_COUPLE;
  return (
    <div className={`cp-point${couple ? ' cp-point--couple' : ''}`}>
      <span className="cp-point-nombre cp-num">
        {couple ? (
          p.couple.map((n) => (
            <span className="cp-point-couple" key={n.label}>
              {formatNumber(n.n)}
              <small>{n.label}</small>
            </span>
          ))
        ) : (
          <>
            {formatNumber(p.valeur)}
            <small>/ {formatNumber(p.sur)}</small>
          </>
        )}
      </span>
      <span className="cp-point-texte">
        {/* Le rôle ne s'affiche que s'il distingue : voir `montrerLesRoles`. */}
        {montrerLeRole && p.role && (
          <span className="cp-point-role">{LIBELLE_ROLE_POINT[p.role]}</span>
        )}
        {p.texte && <span className="cp-point-tete">{p.texte}</span>}
        {p.suite && <span className="cp-point-suite">{p.suite}</span>}
        {p.rendu === RENDU_PODIUM && p.rangs?.length > 1 && <Podium rangs={p.rangs} />}
        {p.repartition && <Repartition repartition={p.repartition} />}
        {p.socle && <span className="cp-point-socle">{p.socle}</span>}
        {p.garde && <span className="cp-point-garde">{p.garde}</span>}
      </span>
    </div>
  );
}

export default function CandidateProfile({ candidate }) {
  const c = candidate;

  return (
    <main className="cp-main">
      <div className="cp-breadcrumb">
        Candidats / <strong>{c.nom}</strong>
      </div>

      <header className="cp-entete">
        <p className="cp-sourcil">Candidat déclaré · élection présidentielle 2027</p>
        <h1>{c.nom}</h1>
        <p className="cp-qui">
          {[c.profession, c.groupe && `Groupe ${c.groupe}`, c.parti].filter(Boolean).join(' · ')}
          {c.naissance && `. ${c.voix.ne} le ${jour(c.naissance.date)}${c.naissance.lieu ? ` à ${c.naissance.lieu}` : ''}.`}
        </p>
        <BadgeSource url={c.sourceUrl} />
      </header>

      {/* L'essentiel. Cinq points au plus, tirés d'un vivier de sept, chacun
          issu d'un jeu de données distinct — aucun rapprochement thématique,
          aucune synthèse (AGENTS.md §2 règle 8). Le contraste réaction /
          initiative se porte par la TYPOGRAPHIE : pas d'emoji, la charte n'en
          emploie nulle part et il introduirait un ton. Les deux lignes ont même
          taille et même graisse — ce sont deux moitiés d'une opposition, et
          n'accentuer que la seconde faisait lire la première comme une légende.
          L'accent porte sur les DEUX MOTS opposés, jamais sur une ligne. */}
      {c.essentiel.points.length > 0 && (
        <section className="cp-essentiel">
          <p className="cp-essentiel-label">L’essentiel</p>
          <h2 className="cp-these">
            <span className="cp-these-ligne">
              Un vote : une <b>réaction</b> à l’ordre du jour d’autrui.
            </span>
            <span className="cp-these-ligne">
              Un amendement déposé, une commission rejointe, une question posée : à l’
              <b>initiative</b> de la personne.
            </span>
          </h2>
          {/* Le cadre initiative / réaction est parlementaire par construction :
              au banc du gouvernement l'ordre du jour se fixe au lieu de se
              subir. Seule cette phrase s'adapte — les points, eux, restent les
              mêmes pour les treize. */}
          {c.essentiel.aSiegeAuGouvernement && (
            <p className="cp-these-gouvernement">
              Au gouvernement, ce partage ne tient plus : l’ordre du jour s’y fixe au lieu de s’y
              subir, et une question au gouvernement s’y reçoit au lieu de s’y poser.
            </p>
          )}
          <p className="cp-essentiel-voici">
            {c.essentiel.points.length === 1
              ? 'Voici le point qui en ressort'
              : `Voici ${c.essentiel.points.length} points qui en ressortent`}
            {c.essentiel.vivier > c.essentiel.points.length
              ? `, sur les ${c.essentiel.vivier} que la donnée permet`
              : ''}
            {c.essentiel.rolesRepresentes.length > 1
              ? ` — au moins un pour chacun des rôles ${c.voix.quil} a exercés.`
              : '.'}
          </p>
          {/* Un rôle tenu que le vivier ne documente pas se DIT : sans cette
              phrase, un⋅e ancien⋅ne ministre dont le corpus ne publie ni
              intervention ni texte porté paraîtrait n'avoir rien fait au
              gouvernement (§2 règle 5). */}
          {c.essentiel.rolesSansPoint.length > 0 && (
            <p className="cp-essentiel-manque">
              Aucun de ces points ne documente{' '}
              {c.essentiel.rolesSansPoint.map((r) => LIBELLE_ROLE_ABSENT[r]).join(' ni ')} : les
              listes que cette section compte y sont vides.
            </p>
          )}
          <div className="cp-points">
            {c.essentiel.points.map((p) => (
              <Point key={p.cle} point={p} montrerLeRole={c.essentiel.montrerLesRoles} />
            ))}
          </div>
        </section>
      )}

      <Section
        numero="1"
        titre="Le parcours"
        critere="Une seule frise, où chaque situation se distingue par un motif et non par une hiérarchie de position. L’ordre est chronologique, jamais hiérarchique : c’est la date qui range, pour tout le monde. Sous la bande, le détail de chaque rôle, puis les fonctions qu’on choisit d’exercer."
      >
        {c.parcours.roles.length === 0 ? (
          <div className="cp-carte">
            <ListeVide cause={c.causes.mandats} source="Mandats et fonctions" />
          </div>
        ) : (
          <>
            <Frise parcours={c.parcours} />
            <Fonctions fonctions={c.fonctions} />
          </>
        )}
      </Section>

      <Section
        numero="2"
        titre={c.voix.titres.gouvernements}
        critere="Ce que ces gouvernements ont porté, en ensembles. Cette section précède ses actes personnels parce qu’elle en donne le contexte, non parce qu’elle vaudrait davantage."
      >
        <Gouvernements cause="fait_etabli" gouvernements={c.gouvernements} voix={c.voix} />
      </Section>

      <Section
        numero="3"
        titre={c.voix.titres.propose}
        critere="Une seule liste, quel que soit le banc. La position déclarée du groupe accompagne le chiffre qu’elle explique — un amendement d’opposition et un amendement de majorité ne sont pas le même acte. Rien n’est additionné."
      >
        <Propositions
          amendements={c.amendements}
          textes={c.textes}
          causeAmendements={c.causes.amendements}
          causeTextes={c.causes.textes_portes}
          voix={c.voix}
        />
      </Section>

      <Section
        numero="4"
        titre={c.voix.titres.dit}
        critere="La qualité en tête — celle que la source publie, ou celle que ses mandats permettent de dériver. Les deux régimes ne se confondent pas."
      >
        <Paroles cause={c.causes.interventions} interventions={c.interventions} voix={c.voix} />
      </Section>

      <Section
        numero="5"
        titre={c.voix.titres.vote}
        critere="Les positions exprimées sur l’ensemble d’un texte, une seule par texte : celle de sa dernière lecture. Quand une période rendait le vote impossible, la page le dit au lieu de laisser un vide. Aucun taux de participation n’est publié : ce serait un taux d’assiduité individuel."
      >
        <Votes cause={c.causes.votes} votes={c.votes} voix={c.voix} />
      </Section>

      <Section
        numero="6"
        titre={c.voix.titres.ecarts}
        critere="Sa position à côté de la position majoritaire de son groupe, scrutin par scrutin. Jamais totalisé : « a voté contre son groupe N fois » serait une note, pas un fait."
      >
        <Ecarts ecarts={c.ecarts} voix={c.voix} />
      </Section>

      <Section
        numero="7"
        titre="Ce qu’on n’a pas pu lire"
        critere="Chaque liste porte son état et ses bornes, et chaque limite se déclare."
      >
        <Couverture couverture={c.couverture} limites={c.limites} />
      </Section>

      <footer className="cp-pied">
        <span>{c.licence}</span>
        <span>Aucun score, aucun classement, aucun taux de présence individuel.</span>
      </footer>
    </main>
  );
}
