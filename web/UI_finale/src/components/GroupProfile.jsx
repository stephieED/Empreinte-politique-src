/*
 * La fiche d'un groupe parlementaire — lot 3 de la refonte #324 (issue #329),
 * reprise de bout en bout.
 *
 * La version précédente était éditorialement irréprochable et structurellement
 * inutilisable : ses sections s'appelaient « Cohésion de vote », « Empreinte
 * thématique », « Amendements déposés » — le vocabulaire du schéma, pas les
 * questions de quelqu'un qui cherche à comprendre un groupe. Et son fait le
 * plus important, le rapport entre scrutins agrégés et scrutins mesurables,
 * était enterré en fin de section « Vérification ».
 *
 * Six sections, dans l'ordre des questions, une seule focale à la fois :
 * l'interne d'abord, la comparaison à la fin. Le quorum ouvre la section des
 * votes, pas la page — « tout ce qui suit porte sur les 341 » est utile juste
 * avant des chiffres de cohésion, et décourageant en première page.
 *
 * Ce composant REND. Les règles vivent dans `utils/groupe.js` (#329) et les six
 * fondations communes dans `utils/lecture.js` (#326) : couleurs de vote,
 * ratios, troncatures, listes vides et badges de source sont importés, jamais
 * redéfinis.
 */
import '../styles/shell.css';
import './GroupProfile.css';
import { BadgeSource, ListeVide, PositionVote, Troncature } from './Lecture';
import { formatNumber, styleForPosition, titreDuTexteVote } from '../utils/lecture';
import { LIBELLE_DENOMINATEUR_TAGS } from '../utils/groupe';

const MOIS = [
  'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
  'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre',
];

function jour(iso) {
  if (!iso) return null;
  const [a, m, j] = String(iso).split('-');
  if (!a) return null;
  if (!m) return a;
  return `${Number(j)} ${MOIS[Number(m) - 1]} ${a}`;
}

/*
 * Un en-tête de section : son numéro, son titre, et le critère qui dit ce que
 * la section montre ET ce qu'elle refuse de montrer. Le critère est du contenu
 * publié, pas une légende décorative.
 */
function periode({ debut, fin, actif }) {
  if (actif) return debut ? `depuis le ${jour(debut)}` : null;
  if (debut && fin) return `du ${jour(debut)} au ${jour(fin)}`;
  return debut ? `depuis le ${jour(debut)}` : null;
}

/* « 1 membres » se lisait sur la fiche Sénat gelée, dont l'effectif vaut 1. */
function membres(n) {
  return `${formatNumber(n)} membre${Number.isFinite(n) && Math.abs(n) >= 2 ? 's' : ''}`;
}

function Section({ numero, titre, critere, children }) {
  return (
    <section className="gp-section">
      <div className="gp-section-bande">
        <span className="gp-section-numero">{numero}</span>
        <span className="gp-section-trait" />
      </div>
      <h2 className="gp-section-titre">{titre}</h2>
      {critere && <p className="gp-section-critere">{critere}</p>}
      <div className="gp-section-corps">{children}</div>
    </section>
  );
}

/*
 * Une note encadrée : ce que les chiffres au-dessus ne disent pas seuls. Elle
 * est du contenu publié, et elle suit le chiffre qu'elle qualifie — jamais
 * renvoyée en bas de page, où elle ne serait plus lue.
 */
function Note({ children }) {
  return <div className="gp-note">{children}</div>;
}

/*
 * La posture déclarée par l'Assemblée (#686). Le motif reprend celui de la
 * fiche candidat : plein pour la majorité, diagonales pour l'opposition, points
 * pour un groupe minoritaire, fines rayures quand rien n'est déclaré. Ce n'est
 * jamais une couleur — une posture n'est ni bonne ni mauvaise (§2 règle 1).
 */
function Posture({ posture, compacte = false }) {
  return (
    <span className={`gp-posture gp-posture--${posture.forme}${compacte ? ' gp-posture--compacte' : ''}`}>
      {posture.label}
    </span>
  );
}

/* ── § 1 — qui sont-ils ──────────────────────────────────────────────────────
 *
 * La première question qu'on se pose sur un groupe, et elle n'apparaissait
 * nulle part : les membres, nommés, et la période. Un effectif est un effectif
 * — la posture ne le change pas, et n'est donc pas répétée ici. Elle est
 * EXPLIQUÉE ici, une fois, parce que c'est ici que le lecteur en a besoin pour
 * lire les sections 2 à 5.
 */
function QuiSontIls({ group }) {
  const { posture } = group;
  return (
    <div className="gp-duo">
      <div className="gp-carte">
        <p className="gp-carte-titre">
          {group.compositionStable ? 'Une composition stable' : 'La composition du groupe'}
        </p>
        <p className="gp-chiffre">
          <b className="gp-num">{formatNumber(group.effectif)}</b>
          <span>
            {group.dateReferenceDatee
              ? `${group.effectif >= 2 ? 'membres' : 'membre'} au ${jour(group.dateReference)}`
              : `${group.effectif >= 2 ? 'membres' : 'membre'}, sans date de référence publiée`}
          </span>
        </p>
        <p className="gp-carte-sous">
          {group.compositionStable
            ? "Aucune entrée, aucune sortie en cours de législature : les comptes de cette fiche se rapportent tous à cette date de clôture."
            : "Les comptes de cette fiche se rapportent à sa date de référence, jamais à aujourd'hui : la législature décrite peut être close."}
        </p>
        {group.membres.length > 0 ? (
          <ul className="gp-pastilles">
            {group.membres.map((m) => (
              <li className="gp-pastille" key={m.nom}>
                {m.nom}
              </li>
            ))}
          </ul>
        ) : (
          <ListeVide cause={group.couvertureRoster.causeListeVide} motif={group.couvertureRoster.motifListeVide} />
        )}
        <p className="gp-carte-sous">
          {membres(group.profilsDisponibles)} sur {formatNumber(group.rosterTotal)} ont
          un profil publié — c'est cette population que la fiche agrège, jamais le roster entier.
        </p>
      </div>

      <div className="gp-carte">
        <p className="gp-carte-titre">
          {posture.declaree ? posture.label : 'Posture non publiée'}
        </p>
        <p className="gp-carte-sous">
          {group.chambreAN ? (
            <>
              L'Assemblée nationale qualifie elle-même chacun de ses groupes, en trois valeurs.
              <b> Ce n'est pas notre lecture, c'est la sienne</b> — et elle change le sens de
              plusieurs chiffres de cette page, jamais leur valeur.
            </>
          ) : (
            <>
              Cette qualification est celle que <b>l'Assemblée nationale</b> donne à ses propres
              groupes, en trois valeurs. <b>Aucune source équivalente n'est collectée pour cette
              chambre</b> : les trois postures sont rappelées ici pour dire ce qui manque, pas pour
              en attribuer une.
            </>
          )}
        </p>
        <ul className="gp-postures">
          {group.posturesConnues.map((p) => (
            <li key={p.cle}>
              <span className={`gp-posture gp-posture--${p.forme} gp-posture--compacte`}>{p.label}</span>
              <span className="gp-postures-phrase">{p.phrase}</span>
            </li>
          ))}
        </ul>
        {posture.declaree ? (
          <p className="gp-carte-sous">
            {posture.phrase} <BadgeSource url={posture.sourceUrl} />
            {posture.verifieLe ? ` Relu le ${jour(posture.verifieLe)}.` : null}
          </p>
        ) : (
          <ListeVide
            cause="non_collecte"
            motif={posture.phrase}
          />
        )}
      </div>
    </div>
  );
}

/* ── § 2 — sur quoi ils choisissent de travailler ────────────────────────────
 *
 * Personne ne siège d'office dans un groupe d'études ou une commission
 * d'enquête. Et les FONCTIONS exercées, que rien n'affichait, sont l'endroit où
 * la posture se voit le plus concrètement : un rapport se confie, il ne se
 * prend pas.
 */
function SurQuoiIlsTravaillent({ group }) {
  const instances = group.mandatsAgreges;
  const parCategorie = [];
  for (const m of instances) {
    const bloc = parCategorie.find((c) => c.categorie === m.categorie);
    if (bloc) bloc.items.push(m);
    else parCategorie.push({ categorie: m.categorie, label: m.categorieLabel, items: [m] });
  }

  return (
    <>
      {instances.length === 0 ? (
        <ListeVide
          cause={group.couvertureRoster.causeListeVide}
          motif={group.couvertureRoster.motifListeVide}
        />
      ) : (
        <div className="gp-carte gp-instances">
          {parCategorie.map((bloc) => (
            <div className="gp-instance" key={bloc.categorie}>
              <p className="gp-instance-cle">
                {bloc.label} · {formatNumber(bloc.items.length)} instances
              </p>
              <ul className="gp-pastilles">
                {bloc.items.slice(0, 6).map((m) => (
                  <li className="gp-pastille" key={`${bloc.categorie}-${m.label}`}>
                    {m.label}
                    {/* Deux nombres, jamais un (#656) : « qui y siège » et « qui y
                        est passé » ne disent pas la même chose — 43 % des adhésions
                        de commission publiées durent une journée ou moins. */}
                    <b className="gp-num">
                      {formatNumber(m.siege)}
                      {Number.isFinite(m.passe) && m.passe !== m.siege
                        ? ` · ${formatNumber(m.passe)} passés`
                        : null}
                    </b>
                  </li>
                ))}
              </ul>
              <Troncature shown={Math.min(6, bloc.items.length)} total={bloc.items.length} rule="les plus occupées, par nombre de membres y siégeant" />
            </div>
          ))}
        </div>
      )}

      <h3 className="gp-sous-titre">Les fonctions qu'ils y exercent</h3>
      <p className="gp-section-critere">
        Siéger et présider ne sont pas la même chose. Ces fonctions se répartissent au sein de
        l'Assemblée, et <b>c'est là que la posture d'un groupe se voit le plus concrètement</b> :
        un rapport se confie, il ne se prend pas.
      </p>
      {group.fonctions.classes.length === 0 ? (
        <ListeVide
          cause={group.couvertureRoster.causeListeVide}
          motif={group.couvertureRoster.motifListeVide}
        />
      ) : (
        <div className="gp-carte gp-lignes">
          {group.fonctions.classes.map((c) => (
            <div className="gp-ligne" key={c.cle}>
              <span className="gp-ligne-cle">{c.label}</span>
              <span className="gp-ligne-texte">
                {c.phrase}
                {c.cle === 'autre' ? (
                  <span className="gp-ligne-detail">
                    {c.libelles.map((l) => `${l.libelle} (${formatNumber(l.nombre)})`).join(' · ')}
                  </span>
                ) : null}
              </span>
              <span className="gp-ligne-nombre gp-num">{formatNumber(c.total)}</span>
            </div>
          ))}
        </div>
      )}
      <Note>
        <b>Ce que ces nombres ne disent pas seuls.</b> Ils dépendent des textes examinés, des
        accords de commission et de la taille du groupe — <b>ils ne se comparent pas en taux</b>{' '}
        d'un groupe à l'autre. Ils sont donnés bruts, avec l'effectif comme dénominateur :{' '}
        {formatNumber(group.fonctions.total)} fonctions pour {formatNumber(group.fonctions.effectif)}{' '}
        membres. <em>Aucun intitulé du référentiel n'est écarté : ceux que notre lecture ne range
        dans aucune des quatre familles sont publiés tels quels sous « Autres fonctions ».</em>
      </Note>

      <h3 className="gp-sous-titre">Les textes sur lesquels le plus de membres sont intervenus</h3>
      <p className="gp-section-critere">
        Libellés du point de l'ordre du jour, tels que l'Assemblée les écrit. Le compte est celui
        des membres du groupe qui y ont pris la parole — <b>ce sont des sujets abordés, jamais des
        positions du groupe</b> (§2 règle 8).
      </p>
      {group.textesDebattus.length === 0 ? (
        <ListeVide
          cause={group.couvertureRoster.causeListeVide}
          motif={group.couvertureRoster.motifListeVide}
        />
      ) : (
        <>
          <div className="gp-carte gp-carte--simple">
            <ul className="gp-pastilles">
              {group.textesDebattus.map((t) => (
                <li className="gp-pastille" key={t.label} title={t.porteursTexte}>
                  {t.label}
                  <b className="gp-num">
                    {formatNumber(t.porteurs)} / {formatNumber(t.denominateur)}
                  </b>
                </li>
              ))}
            </ul>
          </div>
          <p className="gp-legende">
            Chaque étiquette porte le nombre de membres qui y sont intervenus, rapporté aux{' '}
            {LIBELLE_DENOMINATEUR_TAGS}.
          </p>
          <Troncature {...group.troncatureTextes} />
        </>
      )}
    </>
  );
}

/* ── § 3 — ce qu'ils proposent, et ce qu'il en reste ─────────────────────────
 *
 * Deux lignes séparées, JAMAIS additionnées : `AGENTS.md` §5 interdit
 * d'agréger un taux d'adoption sur des types de déposant différents. Déposer
 * comme rapporteur d'une commission et déposer comme député sont deux actes,
 * et les mêler fabriquerait un chiffre qui ne décrit ni l'un ni l'autre.
 */
function CeQuIlsProposent({ group }) {
  const { amendements, posture } = group;

  if (!amendements.distincts) {
    return (
      <ListeVide
        cause={group.couvertureRoster.causeListeVide}
        motif={group.couvertureRoster.motifListeVide}
      />
    );
  }

  return (
    <>
      <div className="gp-carte gp-lignes">
        {amendements.parTypeDeposant.map((type) => (
          <div className="gp-ligne gp-ligne--sorts" key={type.cle}>
            <span className="gp-ligne-cle">{type.label}</span>
            <span className="gp-ligne-texte">
              {type.phrase}
              {type.segments.length > 0 ? (
                <>
                  <span className="gp-empilement">
                    {type.segments.map((s) => (
                      <span
                        className={`gp-empilement-part${s.couleur ? '' : ' gp-empilement-part--sans-teinte'}`}
                        key={s.cle}
                        style={{
                          width: `${(s.part * 100).toFixed(2)}%`,
                          background: s.couleur || undefined,
                        }}
                      />
                    ))}
                  </span>
                  <span className="gp-cles">
                    {type.segments.map((s) => (
                      <span className="gp-cle" key={s.cle}>
                        <i
                          className={s.couleur ? undefined : 'gp-cle-puce--sans-teinte'}
                          style={s.couleur ? { background: s.couleur } : undefined}
                        />
                        {s.label} <b className="gp-num">{formatNumber(s.valeur)}</b>
                      </span>
                    ))}
                  </span>
                </>
              ) : null}
            </span>
            <span className="gp-ligne-nombre gp-num">
              {formatNumber(type.deposes)}
              <span>déposés</span>
            </span>
          </div>
        ))}
      </div>
      <Note>
        {posture.declaree ? (
          <>
            <b>C'est ici que la posture change le sens des chiffres.</b> {posture.phrase}{' '}
            <em>Le même nombre, sous une autre posture, décrirait un autre travail.</em>{' '}
          </>
        ) : (
          <>
            <b>Ces chiffres se lisent avec une clé que cette fiche ne porte pas.</b> Un groupe
            d'opposition dépose contre un ordre du jour qu'il n'a pas fixé ; un groupe majoritaire
            négocie en amont. <em>Sans la qualification déclarée par l'Assemblée, la même colonne
            décrit deux métiers différents.</em>{' '}
          </>
        )}
        <b>Aucun taux n'est publié qui prétendrait en tenir compte</b>, et les lignes ne
        s'additionnent pas : {formatNumber(amendements.distincts)} amendements distincts en tout,
        un amendement cosigné par vingt membres comptant pour un.
      </Note>
    </>
  );
}

/* ── § 4 — comment ils votent ────────────────────────────────────────────────
 *
 * Le quorum OUVRE la section, parce que tout ce qui suit en dépend. En dessous
 * du seuil, rien n'est publié — pas même approché. Ce n'est pas une lacune de
 * collecte : les autres scrutins sont là, ils ne permettent simplement pas
 * cette mesure (§2 règle 5).
 */
function Quorum({ quorum }) {
  const part = quorum.agreges > 0 ? (quorum.mesurables / quorum.agreges) * 100 : 0;
  return (
    <div className="gp-quorum">
      <p className="gp-quorum-titre">
        Sur {formatNumber(quorum.agreges)} scrutins, la cohésion de ce groupe n'est mesurable que
        sur {formatNumber(quorum.mesurables)}
      </p>
      <p>
        Un groupe ne vote pas : ses membres votent. Pour dire s'il s'est exprimé d'une seule voix,
        il faut qu'assez de ses membres aient pris part au scrutin — c'est le <b>quorum</b>, fixé
        ici à {quorum.seuilLabel || 'un seuil non publié'} des membres éligibles. En dessous, deux
        ou trois voix ne décrivent pas le groupe, et <b>rien n'est publié</b>.{' '}
        <em>
          Ce n'est pas une lacune de collecte : les {formatNumber(quorum.sousLeSeuil)} autres
          scrutins sont là, ils ne permettent simplement pas cette mesure.
        </em>{' '}
        Tout ce qui suit porte sur les {formatNumber(quorum.mesurables)}.
      </p>
      <div
        aria-label={`${quorum.mesurables} scrutins mesurables sur ${quorum.agreges}`}
        className="gp-jauge"
        role="img"
      >
        <span className="gp-jauge-ok" style={{ width: `${part.toFixed(2)}%` }} />
        <span className="gp-jauge-non" style={{ width: `${(100 - part).toFixed(2)}%` }} />
      </div>
      <div className="gp-jauge-legende">
        <span>
          <b className="gp-num">{formatNumber(quorum.mesurables)}</b> mesurables
        </span>
        <span>
          <b className="gp-num">{formatNumber(quorum.sousLeSeuil)}</b> sous le quorum
        </span>
      </div>
    </div>
  );
}

/*
 * Les scrutins où le groupe s'est partagé, montrés UN PAR UN, jamais totalisés
 * en indice. « Cohésion de 87 % » serait une note, et un classement dès qu'on
 * en aligne cinq. Et jamais nominatifs : la fiche dit combien de membres ont
 * pris chaque position, jamais lesquels (§2 règles 1 et 7).
 */
function Partage({ partage }) {
  return (
    <>
      <div className="gp-duo">
        <div className="gp-carte">
          <p className="gp-carte-titre">D'une seule voix</p>
          <p className="gp-chiffre">
            <b className="gp-num">{formatNumber(partage.uneSeuleVoix)}</b>
            <span>des {formatNumber(partage.mesurables)} scrutins mesurables</span>
          </p>
        </div>
        <div className="gp-carte">
          <p className="gp-carte-titre">Groupe partagé</p>
          <p className="gp-chiffre">
            <b className="gp-num">{formatNumber(partage.partages)}</b>
            <span>des {formatNumber(partage.mesurables)} scrutins mesurables</span>
          </p>
          <p className="gp-carte-sous">
            Dont <b>{formatNumber(partage.pourEtContre)}</b> où des membres ont voté{' '}
            <b>pour</b> et d'autres <b>contre</b>.
          </p>
        </div>
      </div>

      {partage.exemples.length > 0 && (
        <div className="gp-carte gp-scrutins">
          {partage.exemples.map((e) => (
            <div className="gp-scrutin" key={e.scrutinId}>
              <div>
                <p className="gp-scrutin-texte">{e.texte || 'Intitulé non publié'}</p>
                <p className="gp-scrutin-meta">
                  {e.date || 'Date non renseignée'} · <BadgeSource url={e.sourceUrl} />
                </p>
              </div>
              <div>
                <span
                  aria-label={e.exprimees
                    .map((d) => `${d.valeur} ${styleForPosition(d.cle).label}`)
                    .join(', ')}
                  className="gp-repartition"
                  role="img"
                >
                  {e.exprimees.map((d) => {
                    const style = styleForPosition(d.cle);
                    return (
                      <span
                        className="gp-repartition-part"
                        key={d.cle}
                        style={{ width: `${(d.part * 100).toFixed(2)}%`, background: style.color || undefined }}
                      >
                        {formatNumber(d.valeur)}
                      </span>
                    );
                  })}
                </span>
                <p className="gp-repartition-legende">
                  {formatNumber(e.voixExprimees)} voix exprimées sur {formatNumber(e.eligibles)}{' '}
                  membres éligibles
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
      <Troncature {...partage.troncature} />
      <Note>
        <b>Ces scrutins sont montrés un par un, jamais totalisés en indice.</b>{' '}
        <em>
          « Cohésion de 87 % » serait une note attribuée à un groupe, et un classement dès qu'on en
          aligne cinq. Les écarts d'un membre par rapport à sa majorité de groupe ne sont jamais
          publiés non plus, et les absences n'entrent dans aucun de ces décomptes : ce serait un
          taux de présence sur des personnes nommées.
        </em>
      </Note>
    </>
  );
}

/*
 * Les textes que le plus de scrutins nomment, avec la position de chaque groupe
 * À CHAQUE LECTURE. C'est la ligne entière qui donne le sens d'une position,
 * pas la case isolée — et une liste plate effacerait le mouvement d'une lecture
 * à l'autre.
 */
function GrandesLois({ lois }) {
  return (
    <>
      <div className="gp-carte">
        {lois.lois.map((loi) => (
          <article className="gp-loi" key={loi.designation}>
            <div className="gp-loi-entete">
              <h4 className="gp-loi-titre" title={loi.lectures[0].intitule}>
                {titreDuTexteVote(loi.lectures[0].intitule) || 'Intitulé non publié'}
              </h4>
              <span className="gp-loi-nombre gp-num">
                {formatNumber(loi.scrutins)}
                <span>scrutins dont l'intitulé nomme ce texte</span>
              </span>
            </div>
            <div className="gp-loi-colonnes">
              <span className="gp-loi-cle">
                {formatNumber(loi.lectures.length)} lecture
                {loi.lectures.length > 1 ? 's' : ''} sur l'ensemble du texte
              </span>
              <span className="gp-matrice-entete">
                {lois.colonnes.map((c) => (
                  <b className={c.estLeGroupe ? 'gp-matrice-moi' : undefined} key={c.sigle} title={c.nom}>
                    {c.sigle}
                  </b>
                ))}
              </span>
            </div>
            {loi.lectures.map((lecture) => (
              <div className="gp-loi-lecture" key={lecture.scrutinId}>
                <span className="gp-loi-date gp-num">
                  {jour(lecture.date)} <BadgeSource url={lecture.sourceUrl} />
                </span>
                <span className="gp-matrice">
                  {lecture.positions.map((p) => (
                    <span
                      className={`gp-case gp-case--${p.position || 'absente'}${p.estLeGroupe ? ' gp-case--moi' : ''}`}
                      key={p.sigle}
                    >
                      {p.position ? <PositionVote position={p.position} /> : '—'}
                    </span>
                  ))}
                </span>
              </div>
            ))}
          </article>
        ))}
      </div>
      <Troncature {...lois.troncature} />
      <Note>
        <b>Un tiret n'est pas une abstention</b> : il signale une lecture où le quorum de ce
        groupe-là n'était pas atteint, donc où aucune position ne se publie.{' '}
        <em>
          Le regroupement se fait sur l'intitulé officiel du scrutin, faute de clé de dossier :
          aucun des {formatNumber(lois.total)} scrutins de cette législature n'en publie une, et nous
          ne reconstruisons pas une clé depuis un titre. Le compte affiché dit donc exactement ce
          qu'il mesure — les scrutins dont l'intitulé nomme ce texte —, et{' '}
          {formatNumber(lois.sansDesignation)} intitulés n'en nomment aucun. Les titres ci-dessus
          sont ceux de la source, dont seuls « l'ensemble du… » et la mention de lecture ont été
          retirés ; chaque lecture porte son lien vers le scrutin.
        </em>{' '}
        <b>Un texte adopté sans vote n'apparaît pas ici</b> : un engagement de responsabilité est un
        fait de procédure, jamais une position sur le texte (§2 règle 4).
      </Note>
    </>
  );
}

/*
 * Position majoritaire du groupe comparée à celle de chaque autre, scrutin par
 * scrutin, et uniquement là où LES DEUX atteignent leur quorum. Les
 * dénominateurs diffèrent d'une ligne à l'autre, et l'ordre est celui du nombre
 * de scrutins comparables — pas celui de l'accord.
 */
function Convergences({ accords }) {
  return (
    <>
      <div className="gp-carte gp-accords">
        {accords.map((a) => (
          <div className="gp-accord" key={a.sigle}>
            <span className="gp-accord-sigle" title={a.nom}>
              {a.sigle}
            </span>
            <div>
              <span
                aria-label={a.natures.map((n) => `${n.valeur} ${n.label}`).join(', ')}
                className="gp-accord-barre"
                role="img"
              >
                {a.natures.map((n) => (
                  <span
                    className={`gp-accord-part gp-accord-part--${n.cle}`}
                    key={n.cle}
                    style={{ width: `${(n.part * 100).toFixed(2)}%` }}
                  />
                ))}
              </span>
              <span className="gp-cles">
                {a.natures.map((n) => (
                  <span className="gp-cle" key={n.cle}>
                    <i className={`gp-accord-puce gp-accord-part--${n.cle}`} />
                    {n.label} <b className="gp-num">{formatNumber(n.valeur)}</b>
                  </span>
                ))}
                {a.autres > 0 && (
                  <span className="gp-cle">
                    autres cas <b className="gp-num">{formatNumber(a.autres)}</b>
                  </span>
                )}
              </span>
            </div>
            <span className="gp-accord-total gp-num">
              {formatNumber(a.communs)}
              <span>{a.denominateurLabel}</span>
            </span>
          </div>
        ))}
      </div>
      <Note>
        <b>Voter dans le même sens n'est pas s'entendre.</b> Deux groupes peuvent rejeter un texte
        pour des raisons opposées, et la donnée ne dit rien de ces raisons. Et{' '}
        <b>« nuance » n'est pas « opposé »</b> : une abstention face à une position exprimée n'est
        pas un vote contraire — un décompte brut additionnerait les deux.{' '}
        <b>Aucun chiffre unique ne résume ces relations.</b>
      </Note>
      <Note>
        <b>Et les thèmes ? Nous ne pouvons pas les montrer, et c'est une décision, pas un oubli.</b>{' '}
        Dire « sur l'écologie ils convergent, sur l'immigration ils divergent » supposerait de
        classer les textes par sujet — rien dans la source ne les classe.{' '}
        <em>
          Le champ le plus proche est l'intitulé du point de l'ordre du jour : une valeur par texte.
        </em>{' '}
        Construire les catégories serait un acte éditorial, et il engage bien plus qu'un affichage.
      </Note>
    </>
  );
}

/* ── § 5 — comment ils se situent ────────────────────────────────────────────
 *
 * Réunis PAR POSTURE, jamais alignés sur une échelle unique : un groupe
 * majoritaire et un groupe d'opposition ne font pas le même métier, et les
 * mettre en concurrence sur une tâche qu'ils ne partagent pas serait le
 * classement que §2 règle 1 refuse.
 */
function Comparaison({ comparaison }) {
  return (
    <>
      <div className="gp-carte gp-comparaison">
        {comparaison.blocs.map((bloc) => (
          <div key={bloc.cle}>
            <p className="gp-comparaison-entete">
              {bloc.cle === 'non_publiee'
                ? "Posture non publiée — ces groupes ne peuvent pas être réunis par posture"
                : bloc.posture.label}
            </p>
            {bloc.groupes.map((g) => (
              <div className={`gp-comparaison-ligne${g.estLeGroupe ? ' gp-comparaison-ligne--moi' : ''}`} key={g.sigle}>
                <span className="gp-comparaison-sigle" title={g.nom}>
                  {g.sigle}
                  <small>{membres(g.effectif)}</small>
                </span>
                <span className="gp-comparaison-barre">
                  <i style={{ width: `${(g.partDeposes * 100).toFixed(2)}%` }} />
                  <u style={{ width: `${(g.partAdoptes * 100).toFixed(2)}%` }} />
                </span>
                <span className="gp-comparaison-nombres gp-num">
                  <b>{formatNumber(g.amendements.deposes)}</b> déposés
                  <br />
                  <b>{formatNumber(g.amendements.adoptes)}</b> adoptés
                </span>
              </div>
            ))}
          </div>
        ))}
        {comparaison.posturesSansFiche.length > 0 && (
          <div>
            <p className="gp-comparaison-entete">Les postures qu'aucune fiche ne porte</p>
            <p className="gp-comparaison-absente">
              <b>Aucune fiche publiée.</b>{' '}
              {comparaison.posturesSansFiche.map((p) => p.label).join(', ')} —{' '}
              <em>ces postures ne peuvent donc pas être montrées.</em>
            </p>
          </div>
        )}
      </div>
      <Note>
        <b>Aucun pourcentage n'est affiché, et c'est délibéré.</b> Un taux d'adoption comparé entre
        groupes serait un classement — et il mesurerait surtout la posture de chacun.{' '}
        <em>
          Ce n'est pas une différence de qualité, c'est la définition d'une majorité.
        </em>{' '}
        Les largeurs ci-dessus partagent une échelle commune pour se lire ensemble ; les deux
        nombres, eux, sont publiés en clair à côté d'elles.
      </Note>
    </>
  );
}

/* ── § 6 — ce que cette fiche ne dit pas ─────────────────────────────────────
 *
 * Une page qui se contente de ne pas répondre laisse croire qu'elle n'y a pas
 * pensé. Ces phrases sont du contenu publié, pas des commentaires de code.
 */
function CeQueLaFicheNeDitPas({ group }) {
  const couverture = group.couvertureRoster;
  return (
    <>
      <div className="gp-carte gp-lignes">
        {group.refus.map((r) => (
          <div className="gp-ligne" key={r.id}>
            <span className="gp-ligne-cle">{r.sujet}</span>
            <span className="gp-ligne-texte">
              <b>{r.phrase}</b>
              <span className="gp-ligne-detail">{r.pourquoi}</span>
            </span>
            <span className="gp-ligne-nombre gp-ligne-nombre--mot">jamais</span>
          </div>
        ))}
        <div className="gp-ligne">
          <span className="gp-ligne-cle">Le quorum</span>
          <span className="gp-ligne-texte">
            <b>Le seuil retenu est publié dans la fiche.</b>
            <span className="gp-ligne-detail">
              En dessous, rien n'est calculé — pas même approché. Les scrutins sous le quorum ne
              disparaissent pas de la fiche : ils n'autorisent simplement pas cette mesure.
            </span>
          </span>
          <span className="gp-ligne-nombre gp-num">
            {formatNumber(group.quorum.mesurables)}
            <span>sur {formatNumber(group.quorum.agreges)}</span>
          </span>
        </div>
        <div className="gp-ligne">
          <span className="gp-ligne-cle">La posture</span>
          <span className="gp-ligne-texte">
            <b>
              {group.posture.declaree
                ? "L'Assemblée déclare la position de ce groupe."
                : "Cette fiche ne porte pas la qualification déclarée par l'Assemblée."}
            </b>
            <span className="gp-ligne-detail">
              Elle est recopiée du référentiel de l'Assemblée, jamais déduite d'un comportement de
              vote. Sans elle, plusieurs chiffres de cette page se lisent sans leur clé.
            </span>
          </span>
          <span className="gp-ligne-nombre gp-ligne-nombre--mot">
            {group.posture.declaree ? group.posture.label : 'non publiée'}
          </span>
        </div>
        <div className="gp-ligne">
          <span className="gp-ligne-cle">Les thèmes</span>
          <span className="gp-ligne-texte">
            <b>Aucune source ne classe les textes par sujet.</b>
            <span className="gp-ligne-detail">
              Les construire serait un acte éditorial, différé pour lui-même.
            </span>
          </span>
          <span className="gp-ligne-nombre gp-ligne-nombre--mot">hors périmètre</span>
        </div>
      </div>

      <h3 className="gp-sous-titre">La couverture de cette fiche</h3>
      <div className="gp-carte gp-carte--simple">
        <p className="gp-carte-titre">{couverture.titre}</p>
        <p className="gp-carte-sous">{couverture.phrase}</p>
        <p className="gp-carte-sous">{couverture.profils.text}</p>
        {couverture.preuve && <p className="gp-preuve">{couverture.preuve}</p>}
      </div>

      {group.avertissements.length > 0 && (
        <>
          <h3 className="gp-sous-titre">Ce que la génération a signalé</h3>
          <ul className="gp-avertissements">
            {group.avertissements.map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
        </>
      )}
    </>
  );
}

/*
 * Une section qui dépend de la comparaison entre groupes et ne l'a pas : elle
 * le DIT. Un tableau vide se lirait comme des zéros mesurés (§2 règle 5).
 */
function ComparaisonManquante({ quoi }) {
  return (
    <ListeVide
      cause="non_collecte"
      motif={`La comparaison entre les groupes de cette législature n'a pas pu être chargée : cette page ne peut donc pas montrer ${quoi}. Ce n'est pas un résultat vide, c'est une donnée absente.`}
    />
  );
}

export default function GroupProfile({ group }) {
  const { posture } = group;

  return (
    <main className="gp-main">
      <div className="gp-breadcrumb">
        Groupes / <strong>{group.title}</strong>
      </div>

      <header className="gp-entete">
        <p className="gp-sourcil">
          Groupe parlementaire · {group.kicker}
        </p>
        <h1>{group.title}</h1>
        <div className="gp-entete-sous">
          <Posture posture={posture} />
          <span className="gp-periode">
            {membres(group.effectif)}
            {periode(group.periode) ? ` · ${periode(group.periode)}` : null}
          </span>
        </div>
      </header>

      <Section
        critere="Les membres du groupe, nommés, et la période pendant laquelle il a existé. Un effectif est un effectif : la posture déclarée par l'Assemblée n'en change pas la valeur — elle est expliquée ici, une fois, parce qu'elle change la lecture des sections suivantes."
        numero="1"
        titre="Qui sont-ils"
      >
        <QuiSontIls group={group} />
      </Section>

      <Section
        critere="Un groupe d'études, une commission d'enquête, un organisme extérieur : personne n'y siège d'office. Les comptes sont ceux des membres dont le profil est publié, à la date de référence de la fiche."
        numero="2"
        titre="Sur quoi ils choisissent de travailler"
      >
        <SurQuoiIlsTravaillent group={group} />
      </Section>

      <Section
        critere="Amendements distincts, dédoublonnés : un amendement cosigné par vingt membres compte pour un. Les lignes ne s'additionnent pas en un taux commun — déposer comme rapporteur d'une commission et déposer comme député sont deux actes différents."
        numero="3"
        titre="Ce qu'ils proposent, et ce qu'il en reste"
      >
        <CeQuIlsProposent group={group} />
      </Section>

      <Section
        critere="Un groupe ne vote pas : ses membres votent. Ce que la donnée autorise à dire commence donc par une question de quorum, et tout le reste de la section en dépend."
        numero="4"
        titre="Comment ils votent"
      >
        {group.quorum.agreges > 0 ? (
          <>
            <Quorum quorum={group.quorum} />

            <h3 className="gp-sous-titre">Parlent-ils d'une seule voix ?</h3>
            <p className="gp-section-critere">
              « D'une seule voix » signifie que toutes les positions exprimées allaient dans le même
              sens. <b>Les absences ne sont jamais comptées</b> : un taux de présence individuel
              n'est pas publiable, agrégé ou non.
            </p>
            <Partage partage={group.partage} />

            <h3 className="gp-sous-titre">Sur les grandes lois</h3>
            <p className="gp-section-critere">
              Les textes que le plus de scrutins publics nomment — un fait sur le débat
              parlementaire, jamais une mesure sur un groupe. Chaque lecture est datée, et les
              groupes de la législature y figurent : <b>c'est la ligne entière qui donne le sens
              d'une position</b>, pas la case isolée.
            </p>
            {group.grandesLois ? (
              group.grandesLois.lois.length > 0 ? (
                <GrandesLois lois={group.grandesLois} />
              ) : (
                <ListeVide
                  cause="couvert"
                  motif="Aucun texte de cette législature ne réunit à la fois des scrutins nommant ce texte et un vote sur son ensemble. Ce vide est une mesure."
                />
              )
            ) : (
              <ComparaisonManquante quoi="la position des autres groupes à chaque lecture" />
            )}

            <h3 className="gp-sous-titre">Avec qui votent-ils dans le même sens</h3>
            <p className="gp-section-critere">
              Position majoritaire du groupe comparée à celle de chaque autre, <b>scrutin par
              scrutin</b>, et uniquement là où <b>les deux groupes atteignent leur quorum</b>. Les
              dénominateurs diffèrent donc d'une ligne à l'autre. <b>L'ordre est celui du nombre de
              scrutins comparables</b>, pas celui de l'accord.
            </p>
            {group.convergences && group.convergences.length > 0 ? (
              <Convergences accords={group.convergences} />
            ) : (
              <ComparaisonManquante quoi="la comparaison avec les autres groupes" />
            )}
          </>
        ) : (
          <ListeVide
            cause={group.couvertureRoster.causeListeVide}
            motif={group.couvertureRoster.motifListeVide}
          />
        )}
      </Section>

      <Section
        critere="Mêmes scrutins, même période, mêmes dénominateurs : la seule comparaison qui ait un sens. Les groupes sont réunis par posture, parce qu'un groupe majoritaire et un groupe d'opposition ne font pas le même métier — les aligner sur une échelle unique les mettrait en concurrence sur une tâche qu'ils ne partagent pas."
        numero="5"
        titre="Comment ils se situent parmi les groupes de la même législature"
      >
        {/* Une fiche dont la collecte est suspendue porte des zéros qui ne sont
            pas des mesures : les comparer en publierait cinq (§2 règle 5). */}
        {group.couvertureRoster.causeListeVide === 'non_collecte' ? (
          <ListeVide
            cause={group.couvertureRoster.causeListeVide}
            motif={group.couvertureRoster.motifListeVide}
          />
        ) : group.comparaison ? (
          <Comparaison comparaison={group.comparaison} />
        ) : (
          <ComparaisonManquante quoi="la comparaison entre groupes" />
        )}
      </Section>

      <Section
        critere="Ce qui est interdit est écrit. Une page qui se contente de ne pas répondre laisse croire qu'elle n'y a pas pensé."
        numero="6"
        titre="Ce que cette fiche ne dit pas, et pourquoi"
      >
        <CeQueLaFicheNeDitPas group={group} />
      </Section>

      <footer className="gp-pied">
        <span>
          {group.genereLe ? `Fiche générée le ${group.genereLe}. ` : null}
          Aucun score, aucun classement, aucun taux de présence.
        </span>
        {group.licence && <span>{group.licence}</span>}
      </footer>
    </main>
  );
}
