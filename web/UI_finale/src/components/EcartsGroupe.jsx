/* ── « Ses divergences », par scrutin (#328) ──────────────────────────────────
 *
 * Le composant ne calcule rien qui soit un fait : la bande, les divergences et
 * la dispersion du groupe arrivent construites par `utils/ecartsGroupe.js`. Il
 * ne décide ici que de ce qui est montré à l'écran.
 *
 * Maquette validée le 08/09/2026 (artefact « Lui, dans le vote de son groupe »).
 */
import { VOTE_STYLE, formatNumber } from '../utils/lecture';
import { groupeDivise, partDissidente } from '../utils/ecartsGroupe';
import { Link } from 'react-router-dom';
import './EcartsGroupe.css';

const jour = (d) => (d ? `${d.slice(8, 10)}/${d.slice(5, 7)}/${d.slice(0, 4)}` : '');
const mois = (d) => (d ? `${d.slice(0, 4)}/${d.slice(5, 7)}` : '');
const LIBELLE = { pour: 'Pour', contre: 'Contre', abstention: 'Abstention' };
const teinte = (p) => VOTE_STYLE[p]?.color ?? null;

/* La période de couverture d'une fiche, pas le nombre de scrutins qu'elle
 * partage : c'est la DURÉE sur laquelle la comparaison est possible, le seul
 * rôle de cette ligne. Une fiche encore ouverte affiche « en cours » plutôt
 * qu'une date de fin inventée. */
function couverture(f) {
  if (!f.debut) {
    return f.legislature ? `${f.legislature}ᵉ législature` : 'période non publiée';
  }
  return `${mois(f.debut)} → ${f.fin ? mois(f.fin) : 'en cours'}`;
}

/* ── La bande ────────────────────────────────────────────────────────────────
 *
 * TROIS FAITS, TROIS ÉLÉMENTS, et jamais deux faits sur le même. Deux
 * encodages ont été essayés et portaient la même incohérence : la colonne était
 * COLORÉE par la position majoritaire du groupe alors que sa HAUTEUR comptait
 * les votes qui ne la suivaient pas — deux faits opposés sur un seul objet.
 *
 * Les étiquettes sont posées À GAUCHE, à la hauteur exacte du rang qu'elles
 * nomment : une légende sous un graphique oblige à l'aller-retour, on lit un
 * symbole, on descend, on remonte. Ce que la gouttière prend en largeur est
 * rendu par l'écart entre colonnes, ramené à 1 px — mesuré à 1 000 px de page,
 * une colonne passe de 2,97 px à 3,03 px.
 */
function Bande({ bande }) {
  return (
    <>
      <div className="eg-zone">
        <div className="eg-etiq">
          <span>ses positions divergentes</span>
          <span>membres qui n’ont pas suivi</span>
          <span>ce qu’a voté son groupe</span>
        </div>
        <div className="eg-bande">
          {bande.map((x) => {
            const exprimes = x.pour + x.contre + x.abstention;
            const titre =
              `${jour(x.date)} · ${x.pour} pour, ${x.contre} contre, ${x.abstention} abstention, `
              + `${x.absents} absents ou non-votants sur ${x.membresEligibles} éligibles`
              + ` · sa position : ${LIBELLE[x.position]}`
              + (x.ecart ? ' — hors position majoritaire' : '');
            return (
              <span
                className={`eg-col${x.ecart ? ' eg-col--ecart' : ''}`}
                key={x.scrutinId}
                title={titre}
              >
                <span
                  className="eg-lui"
                  style={x.ecart ? { background: teinte(x.position) } : undefined}
                />
                <span
                  className="eg-part"
                  style={{ height: `${(partDissidente(x) * 44).toFixed(1)}px` }}
                />
                <span
                  className="eg-socle"
                  style={{ background: teinte(x.positionGroupe) }}
                />
                <span className="cp-invisible">
                  {jour(x.date)} — {exprimes} exprimés
                </span>
              </span>
            );
          })}
        </div>
      </div>
      <p className="eg-axe cp-num">
        <span>{jour(bande[0].date)}</span>
        <span>{jour(bande[bande.length - 1].date)}</span>
      </p>
      <div className="eg-cles">
        <span className="eg-cles-quoi">Position majoritaire du groupe</span>
        {['pour', 'contre', 'abstention'].map((p) => (
          <span className="eg-cle" key={p}>
            <i style={{ background: teinte(p) }} />
            {p}
          </span>
        ))}
        {/* Sous 720 px la gouttière ne tient plus : les étiquettes redeviennent
            une légende, jamais affichée en même temps que la gouttière. */}
        <span className="eg-cle eg-cle--rang">
          <i className="eg-cle-socle" /> ce qu’a voté son groupe
        </span>
        <span className="eg-cle eg-cle--rang">
          <i className="eg-cle-part" /> membres qui n’ont pas suivi
        </span>
        <span className="eg-cle eg-cle--rang">
          <i className="eg-cle-point" /> ses positions divergentes
        </span>
      </div>
    </>
  );
}

/* Télégraphique, parce que la barre à droite dit déjà la répartition. Le seul
 * fait que le dessin ne porte pas est COMBIEN ILS SONT à tenir sa position :
 * « l'un des 14 » et « le seul » ne se lisent pas dans une largeur, et ils
 * changent le sens de la divergence. Le nombre en face est celui de la position
 * MAJORITAIRE, quelle qu'elle soit — écrire « pour » systématiquement serait
 * faux dès que le groupe s'abstient. */
function lecture(x) {
  const compte = { pour: x.pour, contre: x.contre, abstention: x.abstention };
  const sien = compte[x.position];
  const majoritaires = compte[x.positionGroupe];
  return `${sien > 1 ? `l’un des ${formatNumber(sien)}` : 'le seul'} de son groupe`
    + ` · face à ${formatNumber(majoritaires)} ${LIBELLE[x.positionGroupe].toLowerCase()}`
    + ` · ${formatNumber(x.pour + x.contre + x.abstention)} exprimés sur ${formatNumber(x.membresEligibles)}`;
}

function Ligne({ x }) {
  return (
    <div className="eg-lg">
      <div className="eg-lg-date cp-num">{jour(x.date)}</div>
      <div>
        <p className="eg-lg-titre">
          {x.sourceUrl ? (
            <a href={x.sourceUrl} target="_blank" rel="noreferrer">
              {x.texte}
            </a>
          ) : (
            x.texte
          )}
        </p>
        <p className="eg-lg-lit" style={{ color: teinte(x.position) }}>
          {LIBELLE[x.position]} <span>· {lecture(x)}</span>
        </p>
        <div className="eg-lg-puces">
          <span className="eg-puce">
            {x.groupe}
            {x.legislature ? ` · ${x.legislature}ᵉ législature` : ''}
          </span>
          {x.sort && <span className="eg-puce">{x.sort}</span>}
          {/* « Quorum non atteint » est un mot de règlement, pas une
              information : il ne dit ni le seuil, ni sur quoi il porte. Ce que
              le lecteur doit comprendre est que la « position majoritaire »
              repose ici sur une poignée de membres (§2 règle 7). */}
          {!x.quorum && (
            <span className="eg-puce eg-puce--alerte">
              moins de la moitié du groupe s’est exprimée
            </span>
          )}
        </div>
      </div>
      <div className="eg-lg-barre">
        <span className="eg-rang">
          {[
            ['pour', x.pour],
            ['contre', x.contre],
            ['abstention', x.abstention],
          ].map(([p, n]) => (n ? (
            <span key={p} style={{ flex: n, background: teinte(p) }} />
          ) : null))}
          {x.absents ? <span className="eg-rang-absent" style={{ flex: x.absents }} /> : null}
        </span>
      </div>
    </div>
  );
}

/* ── Les vides : trois causes, jamais confondues ─────────────────────────────
 *
 * Les deux premières sont des faits sur NOTRE couverture, la troisième un fait
 * sur la personne. Les confondre ferait lire « aucune fiche n'est publiée »
 * comme « il n'a jamais divergé » (§2 règle 5).
 */
function Vide({ ecarts, voix }) {
  if (!ecarts.fiches.length) {
    return (
      <div className="eg-vide">
        <h3>Rien n’est comparable — ce n’est pas la même chose qu’« aucune divergence »</h3>
        <p>
          Aucune fiche de groupe n’est publiée pour les groupes où {voix.pronom} a siégé. Il n’y a
          donc <b>rien à comparer</b> : la section ne dit rien de ses votes.
        </p>
      </div>
    );
  }
  return (
    <div className="eg-vide">
      <h3>Les fiches publiées ne recouvrent aucun de ses votes sur l’ensemble d’un texte</h3>
      <p>
        {ecarts.fiches.map((f, i) => (
          <span key={`${f.sigle}-${f.legislature}`}>
            {i > 0 ? ' ; ' : ''}
            <b>{f.sigle}</b> · {couverture(f)}
          </span>
        ))}
        . La comparaison est <b>vide de base</b>, pas de divergence.
      </p>
    </div>
  );
}

export default function EcartsGroupe({ ecarts, voix }) {
  const { bande, fiches } = ecarts;

  return (
    <>
      <div className="cp-carte eg-carte">
        <h3 className="eg-titre">Ses divergences</h3>

        {bande.length ? (
          <>
            <div className="eg-bloc">
              <div className="eg-bloc-tete">
                <h4>Ce qui est comparable</h4>
                {fiches.length > 0 && (
                  <p className="eg-groupes">
                    <span>Ses groupes parlementaires</span>
                    {fiches.map((f, i) => (
                      <span key={`${f.sigle}-${f.legislature}`}>
                        {i > 0 ? ' · ' : ''}
                        <b>{f.sigle}</b> · {couverture(f)}
                      </span>
                    ))}
                  </p>
                )}
              </div>
              <dl className="eg-dl">
                <dt>
                  <b>Votes utilisés pour la comparaison</b>
                  <em>
                    scrutins sur l’ensemble d’un texte où ses votes et ceux de son groupe existent
                    tous les deux · <Link to="/methodologie#ecarts">comment ils sont retenus</Link>
                  </em>
                </dt>
                <dd className="eg-fort">{formatNumber(bande.length)}</dd>
                <dt>
                  Scrutins où son groupe s’est divisé
                  <em>
                    ses membres exprimés n’ont pas tous voté de la même façon ·{' '}
                    <Link to="/methodologie#ecarts">le détail</Link>
                  </em>
                </dt>
                <dd>{formatNumber(bande.filter(groupeDivise).length)}</dd>
              </dl>
            </div>

            <div className="eg-bloc">
              <h4>Ses positions par rapport au groupe, scrutin après scrutin</h4>
              <p className="eg-dit">
                En bas, <b>ce qu’a voté son groupe</b> dans le temps — et en relief,{' '}
                <b>les membres qui ne l’ont pas suivi</b>. En haut,{' '}
                {ecarts.ecarts.length ? (
                  <b>les scrutins où le sien diverge</b>
                ) : (
                  <>
                    <b>rien</b> : le sien ne diverge jamais
                  </>
                )}
                .
              </p>
              <Bande bande={bande} />
            </div>
          </>
        ) : (
          <div className="eg-bloc">
            <Vide ecarts={ecarts} voix={voix} />
          </div>
        )}
      </div>

      {ecarts.ecarts.length > 0 && (
        <div className="cp-carte eg-carte">
          <h3 className="eg-titre">Les scrutins où {voix.pronom} n’est pas du côté majoritaire</h3>
          <p className="eg-sous">
            Chacun avec la répartition réelle du groupe ce jour-là, et le sort du texte.
          </p>
          <div className="eg-lignes">
            {ecarts.ecarts.map((x) => (
              <Ligne x={x} key={x.scrutinId} />
            ))}
          </div>
        </div>
      )}
    </>
  );
}
