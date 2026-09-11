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
import { BadgeSource, ListeVide } from './Lecture';
import { teinteMatiere } from '../utils/matiere';
import { MATIERE_NON_ETABLIE } from '../utils/profilCandidat';
import { croise, disposerCascade, textesDeLaSelection } from '../utils/cascadeTextes';
import { Fragment, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  LAST_READING_LABEL,
  LIBELLE_SORT_TEXTE,
  MOTIF_SORT,
  estProcedure49_3,
  formatNumber,
} from '../utils/lecture';
import ParolesParPeriode from './ParolesParPeriode';
import VotesParPeriode from './VotesParPeriode';
import EcartsGroupe from './EcartsGroupe';
import {
  CAS_RIEN_A_MONTRER,
  INSTITUTION_GOUVERNEMENT,
  INSTITUTION_MISSION,
  INSTITUTION_PARLEMENT,
  INSTITUTION_PE,
  INSTITUTION_SENAT,
  LIBELLE_PISTE,
  pisteDuRole,
  LIBELLE_STADE,
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
/* `id` et `data-section` : c'est par eux que `SommaireSections` LIT la page, au
 * lieu de recevoir une liste. Le sommaire sert ainsi les trois types de fiche
 * sans qu'aucune ait à le connaître, et une section ajoutée y apparaît d'elle-
 * même. L'ancre est dérivée du NUMÉRO, pas du titre : un titre change avec la
 * voix du texte (« ce qu'il » / « ce qu'elle »), un lien partagé ne doit pas. */
function Section({ numero, titre, critere, pied, children }) {
  return (
    <section className="cp-section" id={`section-${numero}`} data-section={titre}>
      <div className="cp-section-bande">
        <span className="cp-section-numero">{numero}</span>
        <span className="cp-section-trait" />
      </div>
      <h2 className="cp-section-titre"><span>{titre}</span></h2>
      {critere && <p className="cp-section-critere">{critere}</p>}
      <div className="cp-section-corps">{children}</div>
      {/* Le pied porte la règle de lecture APRÈS le contenu, jamais avant : une
          section qui s'annonce avant qu'on ait rien lu fait lire la consigne à
          la place du fait. C'est aussi ce qui a fait retirer le critère d'en-tête
          de cette section-ci. */}
      {pied && <p className="cp-section-pied">{pied}</p>}
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
  // LA FRISE DIT L'INSTITUTION, ET RIEN D'AUTRE. Elle portait aussi la
  // qualification du groupe — majoritaire, opposition, minoritaire, non
  // déclarée — par quatre motifs. Deux encodages sur la même bande, dont un que
  // la légende devait expliquer : la qualification reste écrite en toutes
  // lettres dans la liste des rôles, à côté du mandat qu'elle qualifie, et
  // c'est là qu'elle se lit sans décodeur.
  return `cp-fs--${pisteDuRole(role)}`;
}

/* La légende ne montre QUE ce que la frise porte, et la frise ne porte plus que
 * l'institution : les quatre motifs de qualification de groupe sont retirés avec
 * elle. Chaque entrée dit à quelle piste elle appartient, et seules les pistes
 * présentes sur la fiche sont rendues — elle listait sept entrées partout, dont
 * quatre motifs de groupe sur des profils qui n'ont jamais siégé à l'Assemblée. */
const LEGENDE_FRISE = [
  { piste: INSTITUTION_PARLEMENT, classe: 'cp-fs--parlement', label: 'Député(e)' },
  { piste: INSTITUTION_SENAT, classe: 'cp-fs--senat', label: 'Sénateur(rice)' },
  { piste: INSTITUTION_PE, classe: 'cp-fs--pe', label: 'Député(e) européen(ne)' },
  { piste: INSTITUTION_GOUVERNEMENT, classe: 'cp-fs--gouvernement cp-fs--motif-rayures', label: 'Membre du gouvernement' },
  { piste: INSTITUTION_GOUVERNEMENT, classe: 'cp-fs--chef', label: 'Chef du gouvernement' },
  { piste: INSTITUTION_MISSION, classe: 'cp-fs--mission', label: 'Parlementaire en mission auprès d’un ministère' },
];

function Frise({ parcours }) {
  const { roles, nbLignes, bornes } = parcours;
  if (!roles.length || !bornes) return null;
  const pistesPresentes = new Set(roles.map(pisteDuRole));

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
          {LEGENDE_FRISE.filter((l) => pistesPresentes.has(l.piste)).map((l) => (
            <span className="cp-legende-item" key={l.label}>
              <span className={`cp-legende-pave ${l.classe}`} />
              {l.label}
            </span>
          ))}
        </div>
        {/* LA NOTE EST PARTIE AVEC CE QU'ELLE NOMMAIT. Elle disait « Majorité,
            minorité et opposition selon l'AN » — la seule phrase qui rattachait
            les trois postures à l'Assemblée plutôt qu'à nous (§2 règle 2). La
            frise ne les porte plus : la qualification se lit désormais en toutes
            lettres dans la liste des rôles, et son attribution à l'Assemblée
            reste dite par la limite de couverture et par la méthodologie. */}
      </div>

      {/* Le détail daté se replie : c'est du DÉTAIL, et il n'a pas à s'imposer
          entre la frise et ce qui suit. Même poignée que le bloc « Les grands
          chiffres » — deux plis de même nature ne prennent pas deux formes. */}
      <details className="cp-pli">
        <summary className="cp-poignee">
          <i className="cp-poignee-plus" aria-hidden="true" />
          Détails du parcours
        </summary>
      <ul className="cp-roles">
        {roles.map((r) => (
          <li className="cp-role" key={r.numero}>
            <span className="cp-role-numero">{r.numero}</span>
            <span className="cp-role-dates">{periode(r.debut, r.fin, r.actif)}</span>
            <span className="cp-role-intitule">
              <b>{r.role}</b>
              {/* La qualification du groupe est publiée PAR L'ASSEMBLÉE : la
                  porter sur un mandat européen ou sénatorial ferait dire à
                  l'Assemblée qu'elle n'a rien déclaré sur un siège dont elle ne
                  parle pas (§2 règle 2). */}
              {pisteDuRole(r) === INSTITUTION_PARLEMENT && <Position position={r.position} />}
              {r.detail && <span className="cp-role-detail"> · {r.detail}</span>}
            </span>
          </li>
        ))}
      </ul>
      </details>
    </div>
  );
}

/*
 * Un intitulé, coupé à DEUX lignes quand il déborde.
 *
 * Une seule ligne perdait trop : les commissions d'enquête portent des intitulés
 * de plus de 200 caractères, et la moitié du sens y passait. À deux lignes, plus
 * aucun ne déborde en pleine largeur ; c'est en écran étroit que la coupe sert.
 *
 * Le « … » est un VRAI bouton, pas un `text-overflow` : il faut pouvoir
 * l'atteindre au clavier et qu'un lecteur d'écran annonce qu'il déplie. C'est
 * aussi pourquoi la coupe est franche plutôt qu'un `-webkit-line-clamp`, qui
 * peindrait ses propres points et en afficherait deux.
 *
 * Il n'apparaît QUE sur ce qui déborde vraiment, et ça se mesure — poser
 * l'affordance partout apprendrait au lecteur à ne plus cliquer. La mesure se
 * refait au redimensionnement : la place disponible décide, pas le texte.
 */
function Intitule({ label, roles }) {
  const ligne = useRef(null);
  const [deborde, setDeborde] = useState(false);
  const [deplie, setDeplie] = useState(false);

  useLayoutEffect(() => {
    let attente = 0;
    const mesurer = () => {
      const el = ligne.current;
      if (el) setDeborde(el.scrollHeight > el.clientHeight + 1);
    };
    const auRedimensionnement = () => {
      clearTimeout(attente);
      attente = setTimeout(mesurer, 120);
    };
    mesurer();
    window.addEventListener('resize', auRedimensionnement);
    return () => {
      clearTimeout(attente);
      window.removeEventListener('resize', auRedimensionnement);
    };
  }, [label, roles]);

  return (
    <span className="cp-fonctions-objet">
      <span className="cp-fonctions-ligne" ref={ligne} data-deplie={deplie ? '' : undefined}>
        {label}
        {roles && <span className="cp-fonctions-role"> · {roles}</span>}
      </span>
      {deborde && (
        <button
          type="button"
          className="cp-fonctions-plus"
          aria-expanded={deplie}
          onClick={() => setDeplie((o) => !o)}
        >
          {deplie ? 'Replier l’intitulé' : '…'}
        </button>
      )}
    </span>
  );
}

/*
 * Les fonctions qu'on choisit d'exercer — ce que la section publie désormais en
 * entier, la frise et le détail daté vivant tous deux dans « En bref ».
 *
 * Un bloc par catégorie, JAMAIS un total : un groupe d'amitié et une commission
 * d'enquête ne s'additionnent pas. Chaque bloc montre ses trois plus longues, et
 * le filet marque celle qui dépasse la moitié du temps de mandat — deux états,
 * jamais une graduation. Le reste vit sous un pli, avec sa durée.
 *
 * La marque est SANS TEINTE, et ce n'est pas un oubli : aucune couleur n'était
 * libre. Le jaune signal est pris par la sélection, l'action et le badge de
 * source ; le vert et le rouge par les positions de vote ; le bleu et le bronze
 * par les institutions dans la frise. En ajouter une quatrième aurait dilué les
 * trois autres — et l'encre reste lisible en niveaux de gris et sous daltonisme,
 * sans avoir à doubler la marque d'un pictogramme.
 */
function Fonctions({ fonctions }) {
  if (!fonctions || !fonctions.blocs.length) return null;
  return (
    <div className="cp-carte cp-fonctions">
      {fonctions.blocs.map((b) => {
        const marquee = b.montrees.some((e) => e.marquee);
        // Le BANC porte la couleur, pas la catégorie. Neuf catégories auraient
        // demandé neuf teintes, en concurrence avec la seule grammaire de
        // couleurs de la fiche — et sur un profil qui a connu les deux bancs,
        // c'est le banc qu'on aurait perdu. Ce qui sépare une commission d'un
        // groupe d'amitié est écrit en toutes lettres dans le titre du bloc :
        // la marque ne le remplace pas.
        return (
          <div className={`cp-fonctions-bloc cp-fonctions-bloc--${b.banc}`} key={b.cle}>
            {/* Le dénominateur vit dans le titre, pas sous chaque ligne : c'est
                une constante du profil, et la répéter en faisait un refrain. Il
                n'apparaît QUE là où une ligne est marquée — c'est elle qui
                affirme « plus de la moitié », donc elle seule doit ses deux
                nombres (§2 règle 7). */}
            <p className="cp-fonctions-titre">
              {b.titre} · <span className="cp-num">{formatNumber(b.nbIntitules)}</span>{' '}
              {b.nbIntitules > 1 ? 'intitulés' : 'intitulé'}
              {marquee && ` · sur ${fonctions.mandat.duree} de mandat`}
            </p>

            <ul className="cp-fonctions-liste">
              {b.montrees.map((e) => (
                <li
                  className={`cp-fonctions-item${e.marquee ? ' cp-fonctions-item--marquee' : ''}`}
                  key={e.label}
                >
                  <span className="cp-fonctions-duree cp-num">{e.duree}</span>
                  <Intitule label={e.label} roles={e.roles} />
                </li>
              ))}
            </ul>

            {b.reste.length > 0 && (
              <details className="cp-pli cp-pli--fonctions">
                <summary className="cp-poignee">
                  <i className="cp-poignee-plus" aria-hidden="true" />
                  {formatNumber(b.reste.length)} {b.reste.length > 1 ? 'autres' : 'autre'}
                </summary>
                <div className="cp-puces">
                  {b.reste.map((e) => (
                    <span className="cp-puce" key={e.label}>
                      {e.label}
                      {e.roles && <span className="cp-fonctions-role"> · {e.roles}</span>}
                      <b className="cp-num">{e.duree}</b>
                    </span>
                  ))}
                </div>
              </details>
            )}
          </div>
        );
      })}
    </div>
  );
}

/* ── LES MATIÈRES, DEUX MESURES ET LEUR RAPPORT ─────────────────────────────
 *
 * REMPLACE LA CASCADE PAR ANNÉE. Celle-ci empilait les matières sur un axe du
 * temps, avec un bouton pour basculer entre « amendements déposés » et
 * « dossiers amendés » : deux lectures qu'il fallait faire l'une après l'autre,
 * et dont le rapport — le seul fait intéressant — n'apparaissait jamais.
 *
 * Le volume seul ne fait rien ressortir : il suit le calendrier de l'Assemblée,
 * et Finances arrive en tête pour à peu près tout le monde. Le classement
 * S'INVERSE dès qu'on compte les textes. Les deux mesures sont donc côte à côte,
 * avec le ratio AU MILIEU — c'est le terme qui les relie, pas une conclusion
 * posée au bout.
 *
 * CE RAPPORT N'EST NI UNE PERFORMANCE NI UN JUGEMENT. C'est une densité, et elle
 * porte ses deux termes : elle ne se compare à aucune moyenne, ne se normalise
 * par aucun effectif, et n'est jamais un taux d'adoption (§6). Aucune colonne
 * n'est mise en avant — un ratio sans ses deux termes n'est rien.
 *
 * UN NOMBRE PAR COLONNE. Empilés dans une même cellule, « 26 775 » et « 59 » se
 * lisaient « 26 77559 », et se copiaient ainsi.
 *
 * « Matière non établie » garde sa ligne, en gris et sans ratio : un dossier
 * dont la commission n'est pas résolue n'a pas de dénominateur, et lui en
 * inventer un le ferait disparaître dans les autres (§2 règle 5).
 */
function Matieres({ chute, matiere, onMatiere }) {
  const rang = useMemo(
    () => new Map(chute.matieres.map((m, i) => [m, i])),
    [chute.matieres],
  );
  const lignes = useMemo(() => chute.matieres
    .filter((m) => m !== MATIERE_NON_ETABLIE)
    .map((m) => ({
      m,
      amdt: chute.totauxDepots[m] || 0,
      textes: chute.totauxDossiers[m] || 0,
    }))
    .filter((x) => x.amdt > 0)
    .sort((a, b) => b.amdt - a.amdt), [chute]);
  const nd = {
    amdt: chute.totauxDepots[MATIERE_NON_ETABLIE] || 0,
    textes: chute.totauxDossiers[MATIERE_NON_ETABLIE] || 0,
  };
  if (!lignes.length && !nd.amdt) return null;
  const maxA = Math.max(...lignes.map((x) => x.amdt), nd.amdt, 1);
  const maxD = Math.max(...lignes.map((x) => (x.textes ? x.amdt / x.textes : 0)), 1);

  return (
    <div className="cp-mat">
      <div className="cp-mr cp-mr--tete">
        <span className="cp-mr-lib" />
        <span />
        <span className="cp-mr-n">amendements</span>
        <span className="cp-mr-n">ratio par texte</span>
        <span />
        <span className="cp-mr-n">textes distincts</span>
      </div>
      {lignes.map((x) => {
        const dens = x.textes ? x.amdt / x.textes : null;
        const teinte = teinteMatiere(x.m, rang.get(x.m));
        return (
          <button
            aria-pressed={matiere === x.m}
            className="cp-mr cp-mr--cliquable"
            key={x.m}
            onClick={() => onMatiere(x.m)}
            type="button"
          >
            <span className="cp-mr-lib">{x.m}</span>
            <span className="cp-mr-rail">
              <i style={{ background: teinte, width: `${(x.amdt / maxA) * 100}%` }} />
            </span>
            <span className="cp-mr-n">{formatNumber(x.amdt)}</span>
            <span className="cp-mr-n">{dens == null ? '—' : formatNumber(Math.round(dens))}</span>
            <span className="cp-mr-rail">
              {dens != null && (
                <i style={{ background: teinte, opacity: 0.5, width: `${(dens / maxD) * 100}%` }} />
              )}
            </span>
            <span className="cp-mr-n cp-mr-n--textes">{formatNumber(x.textes)}</span>
          </button>
        );
      })}
      {nd.amdt > 0 && (
        <div className="cp-mr cp-mr--nd">
          <span className="cp-mr-lib">{MATIERE_NON_ETABLIE}</span>
          <span className="cp-mr-rail">
            <i style={{ background: '#dcd8d2', width: `${(nd.amdt / maxA) * 100}%` }} />
          </span>
          <span className="cp-mr-n">{formatNumber(nd.amdt)}</span>
          <span className="cp-mr-n">—</span>
          <span />
          <span className="cp-mr-n cp-mr-n--textes">{formatNumber(nd.textes) || '—'}</span>
        </div>
      )}
    </div>
  );
}

/* ── § 3 — ce qu'il a proposé ────────────────────────────────────────────── */

/*
 * LA CASCADE PROCÉDURALE — ce que sont devenus les textes qu'il a portés.
 *
 * Trois portes, six branches : de la commission on va en séance OU nulle part
 * ailleurs, de la séance à l'adoption OU nulle part ailleurs, de l'adoption à
 * la promulgation OU nulle part ailleurs. La mise en page et le vocabulaire
 * vivent dans `utils/cascadeTextes.js` — ici, on rend.
 *
 * LA LARGEUR EST MESURÉE, pas supposée. La chute voisine s'en passe : son
 * viewBox est fixe et le navigateur la met à l'échelle. La cascade ne le peut
 * pas — elle décide de la place de ses étiquettes, du mot long ou court, et de
 * la gouttière des matières d'après la largeur réelle. À viewBox fixe, un
 * téléphone recevrait la disposition d'un écran large, réduite au tiers.
 */
const ENCRE_ETAPE = ['#5b6b82', '#46566d', '#334458', '#17141f'];

function encreDeLEtape(i, fin) {
  if (!fin) return ENCRE_ETAPE[ENCRE_ETAPE.length - 1];
  return ENCRE_ETAPE[Math.round((i / fin) * (ENCRE_ETAPE.length - 1))];
}

function useLargeur() {
  const ref = useRef(null);
  const [largeur, setLargeur] = useState(0);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    const obs = new ResizeObserver((entrees) => {
      setLargeur(Math.round(entrees[0].contentRect.width));
    });
    obs.observe(el);
    return () => obs.disconnect();
  }, []);
  return [ref, largeur];
}

function Cascade({ cascade, selection, onSelection }) {
  const [ref, largeur] = useLargeur();
  const rang = useMemo(
    () => new Map((cascade.matieres || []).map((m, i) => [m, i])),
    [cascade.matieres],
  );
  const teinteDe = useMemo(
    () => (m) => teinteMatiere(m, rang.get(m) ?? 0),
    [rang],
  );
  const vue = useMemo(
    () => (largeur ? disposerCascade(cascade, largeur, teinteDe) : null),
    [cascade, largeur, teinteDe],
  );

  const choisir = (matiere, lo, hi) => {
    const memeChose = selection
      && selection.matiere === matiere && selection.lo === lo && selection.hi === hi;
    onSelection(memeChose ? null : { matiere, lo, hi });
  };

  return (
    <div className="cp-ter" ref={ref}>
      {vue === null ? (
        <p className="cp-note cp-ter-vide">
          {cascade.total <= 1
            ? 'Un seul texte publié : une cascade n’aurait qu’un ruban, et la liste ci-dessous le dit mieux.'
            : 'Trop peu de textes pour un diagramme de flux — la liste ci-dessous les porte tous.'}
        </p>
      ) : (
        <svg
          aria-label="Cascade procédurale des textes portés : à chaque étape, ce qui franchit et ce dont le corpus n’enregistre aucun acte au-delà"
          className="cp-ter-svg"
          role="img"
          viewBox={`0 ${vue.y0.toFixed(1)} ${vue.W} ${vue.H}`}
        >
          {vue.rubans.map((r) => (
            <path
              className={croise(selection, r.matiere, r.lo, r.hi) ? '' : 'cp-ter-voile'}
              d={r.d}
              fill="none"
              key={r.cle}
              onClick={() => choisir(r.matiere, r.lo, r.hi)}
              stroke={r.couleur}
              strokeOpacity={r.sortie ? 0.62 : 0.85}
              strokeWidth={r.epaisseur.toFixed(1)}
            >
              <title>{r.titre}</title>
            </path>
          ))}
          {vue.barres.map((b) => (
            <rect
              className={[
                b.couleur ? 'cp-ter-matiere' : (b.sortie ? 'cp-ter-issue' : 'cp-ter-encre'),
                croise(selection, b.matiere, b.lo, b.hi) ? '' : 'cp-ter-voile',
              ].filter(Boolean).join(' ')}
              fill={b.couleur || (b.sortie ? undefined : encreDeLEtape(b.etape, vue.fin))}
              height={b.h.toFixed(1)}
              key={b.cle}
              onClick={() => choisir(b.matiere, b.lo, b.hi)}
              rx={b.rx || 0}
              width={b.w.toFixed(1)}
              x={b.x.toFixed(1)}
              y={b.y.toFixed(1)}
            >
              <title>{b.titre}</title>
            </rect>
          ))}
          {vue.chiffres.map((c) => (
            <Fragment key={c.cle}>
              <text
                className="cp-ter-etape cp-ter-etape--issue"
                onClick={() => choisir(null, c.lo, c.hi)}
                x={c.x.toFixed(1)}
                y={c.y.toFixed(1)}
              >
                <tspan className="cp-ter-n">{formatNumber(c.nombre)}</tspan> {c.haut}
              </text>
              <text
                className="cp-ter-etape cp-ter-etape--issue"
                onClick={() => choisir(null, c.lo, c.hi)}
                x={c.xRetrait.toFixed(1)}
                y={c.yRetrait.toFixed(1)}
              >
                {c.bas}
              </text>
            </Fragment>
          ))}
          {/* Jamais voilée : l'étiquette porte la lecture, et c'est par elle
              qu'on sélectionne une étape toutes matières confondues. */}
          {vue.etiquettes.map((e) => (
            <text
              className={`cp-ter-etape${e.finie ? ' cp-ter-etape--fin' : ''}${e.sortie ? ' cp-ter-etape--issue' : ''}`}
              key={e.cle}
              onClick={() => choisir(null, e.lo, e.hi)}
              x={e.x.toFixed(1)}
              y={e.y.toFixed(1)}
            >
              <tspan className="cp-ter-n">{formatNumber(e.total)}</tspan> {e.lib}
            </text>
          ))}
          {vue.nomsMatiere.map((n) => (
            <Fragment key={n.cle}>
              {n.tirant && <path className="cp-ter-tirant" d={n.tirant} />}
              <text className="cp-ter-nom" x={n.x.toFixed(1)} y={n.y.toFixed(1)}>
                {n.court}
                <title>{n.nom}</title>
              </text>
            </Fragment>
          ))}
        </svg>
      )}

      <div className="cp-cles">
        {vue?.etroit && vue.matieres.map((m) => (
          <button
            aria-pressed={selection?.matiere === m}
            className="cp-cle cp-cle--cliquable"
            key={m}
            onClick={() => choisir(m, 0, vue.fin)}
            type="button"
          >
            <i style={{ background: teinteDe(m) }} />
            {m}
          </button>
        ))}
      </div>
      {/* LE 49.3 EST DIT ICI PARCE QUE LA FIGURE NE PEUT PAS LE PORTER.
          Son axe est le STADE — jusqu'où le texte est allé — et un texte adopté
          par engagement de responsabilité s'y range comme les autres : quatre
          de Gabriel Attal se fondent dans la barre « promulgué », un d'Édouard
          Philippe tombe dans une barre « non adopté » qui le contredit. Le fait
          est donc nommé à côté de la figure, jamais dedans, et jamais compté
          comme une adoption ordinaire (§2 règle 4). */}
      {cascade.procedure493 > 0 && (
        <p className="cp-ter-493">
          <button
            aria-pressed={Boolean(selection?.procedure493)}
            className="cp-ter-493-bouton"
            onClick={() => onSelection(selection?.procedure493 ? null : { procedure493: true })}
            type="button"
          >
            <span className="cp-ter-493-marque">49.3</span>
            <b>{formatNumber(cascade.procedure493)}</b> de ces textes
            {cascade.procedure493 > 1 ? ' ont été adoptés' : ' a été adopté'} sans vote
            <span className="cp-ter-493-quoi">(fait procédural)</span>
          </button>
        </p>
      )}
    </div>
  );
}

function ListeCascade({ cascade, selection, onRaz }) {
  const sel = useMemo(() => textesDeLaSelection(cascade, selection), [cascade, selection]);
  const colonnes = useMemo(() => [
    { cle: 'parlement', textes: sel.filter((t) => !t.projetDeLoi) },
    { cle: 'gouvernement', textes: sel.filter((t) => t.projetDeLoi) },
  ].filter((c) => c.textes.length > 0), [sel]);
  if (!selection) {
    return (
      <p className="cp-note cp-ter-invite">
        Cliquez un ruban, une barre ou une étiquette pour lire ce qui la compose.
      </p>
    );
  }
  const fin = cascade.stades.length - 1;
  const nomDe = (i) => LIBELLE_STADE[cascade.stades[i]] || cascade.stades[i];
  const ou = selection.procedure493
    ? 'adoptés sans vote, par engagement de responsabilité'
    : selection.lo === selection.hi
    ? (selection.lo === fin ? nomDe(fin) : `${nomDe(selection.lo)}, et non ${nomDe(selection.lo + 1)}`)
    : (selection.lo === 0 ? 'publiés' : `${nomDe(selection.lo)} ou au-delà`);
  return (
    <div className="cp-ter-liste">
      <div className="cp-ter-liste-tete">
        <span className="cp-ter-liste-quoi">
          {selection.procedure493 ? 'Article 49.3' : selection.matiere || 'toutes matières'} ·{' '}
          {ou} — {formatNumber(sel.length)} texte
          {sel.length > 1 ? 's' : ''}
        </span>
        <button className="cp-chute-raz" onClick={onRaz} type="button">Tout afficher</button>
      </div>
      {/* DEUX COLONNES, PARCE QUE CE SONT DEUX QUALITÉS.
          Un projet de loi est signé comme MINISTRE, une proposition déposée
          comme PARLEMENTAIRE : la liste les mêlait, et une phrase sous la
          figure — « 31 de ses 34 textes portés sont des projets de loi » —
          disait en toutes lettres ce que la liste aurait dû montrer. `role` les
          sépare à la source (#689), les teintes sont celles de « ce que cette
          personne a engagé, en chiffres », et rien n'est additionné.

          UNE SEULE COLONNE QUAND LA SÉLECTION N'A QU'UNE QUALITÉ : une colonne
          vide se lirait comme une lacune de collecte, quand c'est l'expérience
          qui n'existe pas (§2 règle 5). */}
      <div className={`cp-ter-cols ${colonnes.length > 1 ? 'cp-ter-cols--deux' : ''}`}>
        {colonnes.map((col) => (
          <div className={`cp-gc-tete-col cp-gc-tete-col--${col.cle}`} key={`t-${col.cle}`}>
            <span className="cp-gc-bandeau" />
            <span className="cp-gc-col-nom">
              <i />
              {LIBELLE_PISTE[col.cle]}
              <b className="cp-ter-col-nb cp-num">{formatNumber(col.textes.length)}</b>
            </span>
          </div>
        ))}
        {colonnes.map((col) => (
          <ul key={`l-${col.cle}`}>
            {col.textes.map((t) => (
              <li key={`${t.titre}-${t.stadeCle}`}>
                <span className="cp-ter-titre">
                  {t.url
                    ? <a href={t.url} rel="noreferrer" target="_blank">{t.titre}</a>
                    : t.titre}
                </span>
                <span
                  className="cp-ter-pastille"
                  style={{ '--pastille': encreDeLEtape(cascade.stades.indexOf(t.stadeCle), fin) }}
                >
                  {t.stade}
                </span>
                <span className="cp-ter-fait">
                  {t.matiere}{t.an ? ` · ${t.an}` : ''}{t.role ? ` · ${t.role}` : ''}
                </span>
            {/* LE SORT À CÔTÉ DU STADE, JAMAIS À SA PLACE. La pastille du haut
                dit jusqu'où le texte est allé, celle-ci ce qu'il est devenu, et
                l'un ne se déduit pas de l'autre : « discuté en séance et pas
                adopté » ne veut pas dire « rejeté ». Un sort absent affiche son
                MOTIF, jamais un sort par défaut (§2 règle 5). */}
                <span className={`cp-ter-sort${estProcedure49_3(t.sortCle) ? ' cp-ter-sort--493' : ''}`}>
                  {t.sortCle
                    ? LIBELLE_SORT_TEXTE[t.sortCle] || t.sortCle
                    : `Sort non résolu${t.sortMotif ? ` — ${MOTIF_SORT[t.sortMotif] || t.sortMotif}` : ''}`}
                </span>
              </li>
            ))}
          </ul>
        ))}
      </div>
    </div>
  );
}

/*
 * L'ORDRE DE LA SECTION EST CELUI DES DEUX POPULATIONS, ET IL S'EMBOÎTE.
 *
 * D'abord ce que sont devenus les textes dont il est l'AUTEUR ou le
 * RAPPORTEUR ; ensuite les amendements qu'il a déposés sur les textes DES
 * AUTRES. Deux populations distinctes, jamais additionnées, et la première
 * éclaire la seconde.
 *
 * CE QUE CETTE SECTION N'AFFICHE PLUS, ET POURQUOI C'EST DIT ICI. La barre des
 * sorts d'amendement par législature, qui portait la position déclarée du
 * groupe, a été retirée : la maquette validée ne la porte pas. Le fait n'est
 * pas perdu — `amendements.legislatures[].position` reste calculé, et la
 * remettre est une carte à écrire, pas une donnée à recollecter.
 */
function Propositions({ amendements, textes, causeAmendements, causeTextes, voix }) {
  const [matiere, setMatiere] = useState(null);
  const [selTexte, setSelTexte] = useState(null);
  const choisirMatiere = (m) => setMatiere((a) => (a === m ? null : m));
  const dossiersDeLaMatiere = matiere
    ? (amendements.chute?.dossiersParMatiere?.[matiere] || [])
        .slice()
        .sort((a, b) => b.n - a.n)
    : [];
  return (
    <>
      {textes.total === 0 ? (
        <div className="cp-carte">
          <ListeVide cause={causeTextes} source="Textes portés comme auteur ou rapporteur" />
        </div>
      ) : (
        <div className="cp-carte cp-textes">
          <div className="cp-gouv-tete">
            <span className="cp-gouv-nom">Les textes {voix.quil} a portés</span>
            <span className="cp-gouv-periode cp-num">
              {formatNumber(textes.publies.length)} publiés · {formatNumber(textes.promulgues)}{' '}
              promulgué{textes.promulgues > 1 ? 's' : ''}
            </span>
          </div>
          {textes.cascade.total > 0 && (
            <>
              <Cascade
                cascade={textes.cascade}
                onSelection={setSelTexte}
                selection={selTexte}
              />
              <ListeCascade
                cascade={textes.cascade}
                onRaz={() => setSelTexte(null)}
                selection={selTexte}
              />
            </>
          )}

        </div>
      )}

      {amendements.totalAuteur === 0 ? (
        <div className="cp-carte">
          <ListeVide cause={causeAmendements} source="Amendements déposés comme auteur principal" />
        </div>
      ) : amendements.chute && (
        <div className="cp-carte">
          <div className="cp-gouv-tete">
            <span className="cp-gouv-nom">Les amendements dont {voix.sujet} est l’auteur</span>
            <span className="cp-gouv-periode cp-num">
              {formatNumber(amendements.totalAuteur)} amendements ·{' '}
              {formatNumber(amendements.dossiers?.distincts ?? amendements.chute.totalDossiers)}{' '}
              dossiers · {formatNumber(amendements.adoptes)} adopté
              {amendements.adoptes > 1 ? 's' : ''}
            </span>
          </div>
          <Matieres
            chute={amendements.chute}
            matiere={matiere}
            onMatiere={choisirMatiere}
          />
          {/* CE QUI RESTAIT EN TROIS CARTES TIENT EN UNE LIGNE. Les adoptés et
              les deux motifs d'irrecevabilité étaient rendus en `cp-bloc`, la
              forme réservée aux grands chiffres : trois nombres de la taille des
              totaux de la fiche, pour un fait qui se lit sous la légende. Aucun
              n'est perdu — ils sont ici, à la suite de la figure qu'ils
              qualifient, et sans accent. */}
          {amendements.irrecevabilites.length > 0 && (
            <p className="cp-chute-mentions">
              {amendements.irrecevabilites
                .map((b) => `${formatNumber(b.n)} ${b.titre}`)
                .join(' · ')}
            </p>
          )}
          {matiere && (
            <div className="cp-chute-liste">
              <div className="cp-chute-liste-tete">
                <span className="cp-chute-liste-quoi">
                  {matiere} — {formatNumber(dossiersDeLaMatiere.length)} dossier
                  {dossiersDeLaMatiere.length > 1 ? 's' : ''}
                </span>
                <button className="cp-chute-raz" onClick={() => setMatiere(null)} type="button">
                  Tout afficher
                </button>
              </div>
              <ul>
                {dossiersDeLaMatiere.map((d) => (
                  <li key={d.cle}>
                    <span className="cp-chute-titre">{d.nom || 'Dossier non nommé par la source'}</span>
                    <span className="cp-chute-fait">
                      {formatNumber(d.n)} amendement{d.n > 1 ? 's' : ''} déposé{d.n > 1 ? 's' : ''}
                      {d.adoptes > 0 ? (
                        <>
                          , <b className="cp-chute-oui">{formatNumber(d.adoptes)} adopté{d.adoptes > 1 ? 's' : ''}</b>
                        </>
                      ) : (
                        ', aucun adopté'
                      )}
                      {d.annee ? ` · ${d.annee}` : ''}
                    </span>
                  </li>
                ))}
              </ul>
              {/* LA NOTE SOUS LA LISTE EST PARTIE EN DEUX TEMPS. Sa première
                  moitié parlait de l'axe des années, retiré avec la cascade. La
                  seconde recomptait ce que la liste montre déjà : chaque ligne
                  porte « N adoptés » ou « aucun adopté », et une phrase qui
                  totalise ce que l'œil vient de lire fait relire au lieu de
                  compléter. */}
            </div>
          )}
        </div>
      )}

      <p className="cp-methodo">
        <Link to="/methodologie#propose">
          Quels textes et quels amendements sont retenus, et pourquoi aucun taux d’adoption
        </Link>
      </p>
    </>
  );
}

/* ── § 4 — ce qu'il a dit ────────────────────────────────────────────────────
 *
 * REMPLACÉ EN ENTIER LE 09/09/2026 (#328). Ce qui était ici — le régime de
 * qualité en pavé, la liste des natures, la liste des fonctions, le bloc des
 * questions au gouvernement — publiait quatre listes de totaux de carrière et
 * un paragraphe de méthode, sans jamais montrer un mot de ce qui avait été dit,
 * alors que le corpus porte 16 188 verbatims du compte rendu intégral. La
 * maquette validée ne garde rien de cela : la section est désormais la figure
 * par période, ses deux facettes croisées et le fil.
 *
 * CE QUI N'EST PAS PERDU. Le régime de qualité et la direction des questions au
 * gouvernement restent calculés — « En bref » les consomme —, et la qualité est
 * écrite intervention par intervention dans le fil (« prononcé comme ministre
 * délégué »), là où elle qualifie un fait plutôt qu'une carrière. Ce que la
 * section ne sait pas est publié sous la figure.
 */
function Paroles({ interventions, cause }) {
  if (!interventions.total) {
    return (
      <div className="cp-carte">
        <ListeVide cause={cause} source="Interventions en séance et en commission" />
      </div>
    );
  }

  if (!interventions.periodes?.length) {
    return (
      <div className="cp-carte">
        <ListeVide
          cause="non_collecte"
          motif="Aucune de ses interventions ne porte de date exploitable : sans date, ni le banc ni le gouvernement en place ne peuvent être lus, et une période politique ne se construit pas."
        />
      </div>
    );
  }

  return (
    <ParolesParPeriode
      periodes={interventions.periodes}
      plafondPeriode={interventions.plafondPeriode}
      plafondEnsemble={interventions.plafondEnsemble}
      couverture={interventions.couverture}
    />
  );
}

/* ── § 5 — ce qu'il a voté ─────────────────────────────────────────────────── */
function Votes({ votes, cause }) {
  if (!votes.total) {
    return (
      <div className="cp-carte">
        <ListeVide cause={cause} source="Positions de vote publiées" />
      </div>
    );
  }

  /* DEUX FIGURES RETIRÉES LE 08/09, ET CE QU'ELLES PORTAIENT.
   *
   * 1. L'AXE DES ANNÉES — une barre par année civile, avec trois situations
   *    (`gouvernement`, `hors_mandat`, `en_mandat`). Il existait pour qu'un
   *    zéro ne se lise pas comme une absence individuelle (§2 règle 3), ce qui
   *    n'a de sens que sur un axe CONTINU. La vue par période n'affiche que
   *    les périodes où la personne a voté : il n'y a plus de zéro à expliquer,
   *    donc plus rien à protéger.
   *
   * 2. LA NOTE « un membre du gouvernement ne vote pas » — corollaire du même
   *    axe : elle nommait les années creuses. Le fait lui-même n'est pas perdu,
   *    il est porté par « Les fonctions exercées » et par la frise d'« En bref ».
   *
   * Ce qui RESTE, et qui n'est pas décoratif : les quatre branches de vide
   * ci-dessous, qui distinguent quatre causes qu'aucune figure ne remplace, et
   * les dénominateurs du repli, qu'un ratio ne peut pas taire (§2 règle 7).
   */
  return (
    <>
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
        <>
          {/* DEUX PHRASES, ET PLUS DEUX PARAGRAPHES (#328).
              Le « pourquoi » des deux règles — quatre lectures d'un même texte,
              un code de scrutin qui ne sépare pas l'ensemble de l'article —
              est passé dans la page de méthodologie, où le renvoi sous la
              figure mène. Trois pages de raisonnement sous un graphique font
              lire la légende à la place du fait.
              Ce qui NE PART PAS : les deux phrases elles-mêmes. #711 les veut
              à côté du chiffre, pas seulement dans la méthodologie — qui
              annonçait déjà la règle à l'époque où rien ne l'appliquait. */}
          {votes.periodes?.length ? (
            <>
              <VotesParPeriode
                periodes={votes.periodes}
                portee={votes.portee}
                reperes={votes.reperes}
                regle={`${formatNumber(votes.textes)} textes — ${LAST_READING_LABEL}`}
              />
            </>
          ) : (
            <div className="cp-carte">
              <ListeVide
                cause="non_collecte"
                motif="Aucune de ses positions de dernière lecture ne porte de date exploitable : sans date, ni le banc ni le gouvernement en place ne peuvent être lus, et une période politique ne se construit pas."
              />
            </div>
          )}
        </>
      )}
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

function Couverture({ couverture, parcours, collecte }) {
  return (
    <>
      {/* `--rangs` : les rangs portent leur marge et leur filet court d'un bord
          à l'autre, donc la carte s'efface devant eux. La seule de la fiche. */}
      <div className="cp-carte cp-carte--rangs">
        <div className="cp-gouv-tete cp-rangs-tete">
          <span className="cp-gouv-nom">Ce que chaque liste porte</span>
          <span className="cp-gouv-periode cp-num">
            {formatNumber(couverture.length)} liste{couverture.length > 1 ? 's' : ''}
          </span>
        </div>
        {couverture.map((c) => (
          <div className="cp-ligne cp-ligne--couverture" key={c.cle}>
            <span className="cp-ligne-cle">{c.titre}</span>
            <span className="cp-ligne-corps">
              {c.etats.map((e) => (
                <span className="cp-etat" key={`${e.etat}-${e.debut}-${e.fin}`}>
                  <b>{LIBELLE_ETAT[e.etat] || e.etat}</b>
                  {e.debut && ` depuis le ${jour(e.debut)}`}
                  {!e.debut && e.fin && ` jusqu’au ${jour(e.fin)}`}
                  {/* La même borne explique souvent « couvert depuis » ET
                      « hors couverture jusqu'au » : elle se dit une fois par
                      liste, jamais deux (`preuveDejaDite`). */}
                  {e.preuve && !e.preuveDejaDite && <em>{e.preuve}</em>}
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

      {/* DEUX SOUS-PARTIES, PARCE QU'IL Y A DEUX SUJETS.
          Le tableau ci-dessus dit, liste par liste, CE QUE LE DÉPÔT PORTE et
          depuis quand. Les signalements ci-dessous disent ce que LA COLLECTE a
          rencontré — une source qui ne publie pas, un identifiant introuvable.
          Mêlés, ils faisaient un tableau suivi de paragraphes flottants que rien
          ne rattachait à rien.

          Chaque signalement est coupé sur son premier tiret cadratin, que nos
          propres messages posent entre la source et son explication (« Parlement
          européen — votes non publiés : … »). Un message qui n'en porte pas est
          rendu entier : on ne devine pas un intitulé qui n'existe pas. */}
      {parcours.length > 0 && (
        <div className="cp-carte cp-signal">
          <div className="cp-gouv-tete">
            <span className="cp-gouv-nom">Ce que le corpus ne dit pas de son parcours</span>
            <span className="cp-gouv-periode cp-num">
              {formatNumber(parcours.length)} point{parcours.length > 1 ? 's' : ''}
            </span>
          </div>
          <dl className="cp-signal-dl">
            {parcours.map((l) => (
              <Fragment key={l.cle}>
                <dt>{LIBELLE_LIMITE[l.cle] || 'Corpus'}</dt>
                <dd>{l.texte}</dd>
              </Fragment>
            ))}
          </dl>
        </div>
      )}

      {collecte.length > 0 && (
        <div className="cp-carte cp-signal">
          <div className="cp-gouv-tete">
            <span className="cp-gouv-nom">Ce que la collecte signale</span>
            <span className="cp-gouv-periode cp-num">
              {formatNumber(collecte.length)} signalement{collecte.length > 1 ? 's' : ''}
            </span>
          </div>
          <dl className="cp-signal-dl">
            {collecte.map((l) => {
              const coupe = /^(.+?)\s+—\s+([\s\S]+)$/.exec(l.texte);
              return (
                <Fragment key={l.cle}>
                  <dt>{coupe ? coupe[1] : 'Collecte'}</dt>
                  <dd>{coupe ? coupe[2] : l.texte}</dd>
                </Fragment>
              );
            })}
          </dl>
        </div>
      )}
      {/* LE BLOC « ASSIDUITÉ / CLASSEMENT / 49.3 » EST RETIRÉ (#328). Mesuré
          sur la page rendue de `delphine-batho` : « aucun classement » y
          apparaissait TROIS fois — ici, dans le pied de la fiche juste en
          dessous, et dans le pied du site. Les trois refus restent publiés là
          où ils s'argumentent : `STATED_REFUSALS` est rendu par la
          méthodologie, source unique, et « Ce que vous ne trouverez pas ici »
          l'expose sur l'accueil. Le 49.3, lui, est déjà porté là où il sert —
          la pastille d'encre de « Ce qu'il a voté » marque chaque texte adopté
          sans vote (#743). */}
      {/* DEUX renvois, deux questions distinctes : ce que ces bornes valent
          pour tout le corpus, et pourquoi une limite se déclare au lieu de se
          combler (DESIGN_SYSTEM §7 règle 2). */}
      <p className="cp-methodo">
        <Link to="/couverture">Ce que le dépôt porte, et depuis quand</Link>
        {' · '}
        <Link to="/methodologie#couverture">
          Pourquoi ces limites se déclarent au lieu de se combler
        </Link>
      </p>
    </>
  );
}

/* ── § Les grands chiffres — la frise commande les colonnes ──────────────────
 *
 * **La frise est CELLE DU PARCOURS, pas une seconde.** Ce bloc en portait une
 * copie — pistes par institution, étiquettes propres, légende propre — et cette
 * copie coûtait exactement ce que #672 a fermé sur `isWholeTextVote` : deux
 * définitions du même objet, qui divergent au premier ajustement. Relevé en
 * relecture d'écran le 03/09/2026 : « reprends exactement la même frise que dans
 * la section parcours, avec la légende et le détail daté ».
 *
 * `Frise` porte déjà tout ce que la copie refaisait, et mieux : la teinte porte
 * l'institution, le MOTIF porte la position, les repères numérotés renvoient à
 * une liste datée, et la légende dit pourquoi les deux familles ne forment
 * aucune progression. La couleur fait donc toujours le lien avec les colonnes —
 * ce sont désormais les colonnes qui prennent la teinte de la frise, et non
 * l'inverse.
 */

/* Une cellule. **Seuls les nombres sont en gros** : mettre l'objet à la même
 * échelle que le chiffre faisait lire « Orientation et réussite des étudiants »
 * comme la mesure, alors que la mesure est 211. */
function CelluleChiffre({ cellule: c, piste }) {
  // La PISTE est portée par la cellule, pas déduite de sa position (#328). La
  // règle d'avant partait de l'en-tête « gouvernement » et descendait sur tous
  // ses frères : dans une grille, les cellules de la colonne PARLEMENT viennent
  // après cet en-tête, et prenaient donc la teinte du gouvernement.
  const classe = `cp-gc-cell cp-gc-cell--${piste}`;
  if (!c) return <div className={`${classe} cp-gc-cell--vide`} />;
  if (c.absent) {
    return (
      <div className={classe}>
        <p className="cp-gc-absent">
          <span aria-hidden="true">—</span> {c.absent}
        </p>
      </div>
    );
  }
  return (
    <div className={classe}>
      <p className="cp-gc-n">
        <b className="cp-num">{formatNumber(c.nombre)}</b> <small>{c.objet}</small>
        {c.sur != null && (
          <>
            {' '}
            <b className="cp-num">{formatNumber(c.sur)}</b> <small>{c.objetSur}</small>
          </>
        )}
      </p>
      {c.quantifieur && (
        <p className="cp-gc-q">
          <span className="cp-num">{formatNumber(c.quantifieur.nombre)}</span>{' '}
          {c.quantifieur.texte}
        </p>
      )}
      {c.barre && (
        <>
          <span className="cp-gc-barre">
            {c.barre.segments.map((s) => (
              <span
                key={s.cle}
                className={`cp-gc-part cp-gc-stade--${s.cle}`}
                style={{ width: `${s.part.toFixed(2)}%` }}
              />
            ))}
          </span>
          <span className="cp-gc-barre-leg">
            {c.barre.segments.map((s) => (
              <em key={s.cle} className={`cp-gc-cle-stade cp-gc-stade--${s.cle}`}>
                <b>{formatNumber(s.nombre)}</b>&nbsp;{s.libelle}
              </em>
            ))}
          </span>
        </>
      )}
      {c.detail && <p className="cp-gc-d">{c.detail}</p>}
    </div>
  );
}

/* La largeur vient de la CLASSE, jamais d'un style en ligne : une valeur en
 * ligne ne se surcharge qu'avec `!important`, que la media query du petit écran
 * devrait alors reprendre. Quatre largeurs, autant que d'institutions. */
const MOT_COLONNES = { 1: 'une', 2: 'deux', 3: 'trois', 4: 'quatre' };

/* LE SÉNAT EST REPLIÉ D'ENTRÉE, SAUF S'IL EST SEUL — et c'est un choix de
 * lecture, pas une suppression : sa puce reste allumée au-dessus du tableau et
 * dit ce qui est là. Sa colonne ne porterait, sur les deux fiches concernées,
 * que des cellules vides : la collecte du Sénat est hors périmètre (#528), donc
 * ni vote, ni amendement, ni intervention. La replier met en avant ce que la
 * fiche sait dire ; la retirer effacerait un siège réel (§2 règle 5).
 *
 * Seule exception, celle qui empêche une fiche vide : si le Sénat est la seule
 * colonne, il s'ouvre. Un tableau sans colonne ne se replie pas, il disparaît. */
function repliParDefaut(colonnes) {
  if (colonnes.length <= 1) return new Set();
  return new Set(colonnes.filter((c) => c === INSTITUTION_SENAT));
}

function GrandsChiffres({ chiffres, parcours }) {
  const { colonnes = [], lignes = [] } = chiffres || {};
  const [replies, setReplies] = useState(() => repliParDefaut(colonnes));
  if (!chiffres || chiffres.cas === CAS_RIEN_A_MONTRER) return null;
  const ouvertes = colonnes.filter((c) => !replies.has(c));
  const basculer = (c) => setReplies((avant) => {
    const apres = new Set(avant);
    // JAMAIS ZÉRO COLONNE : replier la dernière ne laisserait que des intitulés
    // de rang, c'est-à-dire le gabarit et aucune personne.
    if (!apres.has(c) && ouvertes.length === 1) return avant;
    if (apres.has(c)) apres.delete(c);
    else apres.add(c);
    return apres;
  });
  return (
    <section className="cp-gc">
      {/* « En bref » prend la bande, le filet et le h2 d'un titre de section.
          SANS numéro : le numéroter ferait de ce bloc la section 1 et décalerait
          les sept suivantes, ce qui n'a pas été décidé. */}
      <div className="cp-section-bande">
        <span className="cp-section-trait" />
      </div>
      <h2 className="cp-section-titre"><span>En bref</span></h2>

      <div className="cp-carte cp-gc-carte">
        {/* La FRISE reste toujours dépliée : c'est l'ossature, et elle donne aux
            colonnes leur couleur et leur raison d'être. Replier le bloc entier
            cachait ce qui explique le reste.

            C'est LE composant `Frise`, celui de la section « Le parcours » —
            même bande, même légende, même liste datée. Une seconde frise aurait
            divergé de la première au premier ajustement. */}
        <div className="cp-gc-frise">
          <Frise parcours={parcours} />
        </div>

        {/* La thèse introduit LES COLONNES, pas le parcours : elle se lit juste
            avant « À l'Assemblée », et elle sert de poignée à ce qui la suit. La
            partie dense — cinq rangs sur deux colonnes — est ce qui se replie,
            et le « + » le dit sans une phrase.

            La ligne elle-même a été réduite trois fois : le texte explicatif est
            un aveu d'échec, et si une phrase doit expliquer un chiffre, c'est la
            forme qui n'a pas fait son travail. */}
        <details className="cp-pli">
          <summary className="cp-poignee">
            <i className="cp-poignee-plus" aria-hidden="true" />
            Ce que cette personne a engagé, en chiffres.
          </summary>

          {/* Le nombre de colonnes vient de la CLASSE, jamais d'un style en
              ligne : sous 720 px le tableau défile latéralement, et une valeur en
              ligne ne se surcharge qu'avec `!important` — que le prochain
              ajustement oublierait. */}
          {/* LE NOM DU RANG UNE FOIS, À GAUCHE — et non répété au-dessus de
              chaque colonne. Avec deux institutions il se lisait deux fois ;
              avec les quatre qu'une carrière peut traverser, « TEXTES PORTÉS »
              s'écrivait quatre fois sur la même ligne. Le tableau met le rang
              en tête de ligne et laisse les colonnes aux chiffres, qui sont ce
              qu'on compare. */}
          {/* LES PUCES DISENT CE QUE LE TABLEAU NE MONTRE PAS. Une colonne
              repliée sort de la grille — le tableau se resserre sur ce qui
              reste —, mais sa puce demeure, éteinte : le lecteur voit qu'une
              institution existe et qu'il peut la rouvrir. Sans elles, replier
              serait effacer. */}
          {colonnes.length > 1 && (
            <div className="cp-gc-puces" role="group" aria-label="Institutions affichées">
              {colonnes.map((c) => (
                <button
                  type="button"
                  key={`p-${c}`}
                  className={`cp-gc-puce cp-gc-puce--${c}`}
                  aria-pressed={!replies.has(c)}
                  onClick={() => basculer(c)}
                >
                  <i aria-hidden="true" />
                  {LIBELLE_PISTE[c]}
                </button>
              ))}
            </div>
          )}

          <div className={`cp-gc-duo cp-gc-duo--${MOT_COLONNES[ouvertes.length] || 'quatre'}`}>
            <div className="cp-gc-coin" />
            {ouvertes.map((c) => (
              <div className={`cp-gc-tete-col cp-gc-tete-col--${c}`} key={`t-${c}`}>
                <span className="cp-gc-bandeau" />
                <span className="cp-gc-col-nom">
                  <i />
                  {LIBELLE_PISTE[c]}
                </span>
              </div>
            ))}
            {/* La règle « un rang sans aucun chiffre ne s'affiche pas » vaut sur
                les colonnes OUVERTES : replier le Sénat ne doit pas laisser un
                intitulé seul face à rien. */}
            {lignes
              .filter((l) => ouvertes.some((c) => l.cellules[c] && !l.cellules[c].absent))
              .map((l) => (
              <Fragment key={l.cle}>
                <p className="cp-gc-rang">{l.titre}</p>
                {ouvertes.map((c) => (
                  <CelluleChiffre cellule={l.cellules[c]} key={`c-${l.cle}-${c}`} piste={c} />
                ))}
              </Fragment>
            ))}
          </div>
        </details>
      </div>
    </section>
  );
}

/* « L'essentiel » a été remplacé par « Les grands chiffres » (#328) : sa vue —
 * la fonction `Point` et ses trois rendus — est retirée. Le VIVIER, lui, reste
 * calculé dans `profilCandidat.js` et testé : la décision prévoit explicitement
 * qu'un vrai résumé prenne la place que ce bloc libère, et supprimer le calcul
 * avant de savoir ce qui le remplace détruirait ce que
 * `tests/test_essentiel_328.py` documente.
 */

/* L'intitulé de chaque limite de parcours : il nomme SUR QUOI elle porte, pour
 * que trois phrases deviennent trois lignes rangées. Les clés viennent de
 * `profilCandidat.js` ; une clé inconnue retombe sur « Corpus » plutôt que de
 * rendre une ligne sans intitulé. */
const LIBELLE_LIMITE = {
  'position-non-declaree': 'Qualification du groupe',
  suspension: 'Entrée au gouvernement',
  'sieges-replies': 'Enregistrements de mandat',
};

/* DEUX SORTES DE LIMITES, ET ELLES NE DISENT PAS LA MÊME CHOSE.
 *
 * Les unes disent ce que le corpus NE DIT PAS de cette personne : la
 * qualification que l'Assemblée n'a pas déclarée sur un mandat, la suspension
 * pour fonction gouvernementale qu'aucun mandat électif ne renseigne, les
 * enregistrements repliés sur un même siège. Les autres disent ce que la
 * COLLECTE a rencontré : une source qui ne publie pas, un identifiant
 * introuvable.
 *
 * Toutes restent en « ce qu'on n'a pas pu lire » — c'est la section qui parle
 * des trous —, mais chacune sous son intitulé : mêlées, elles faisaient une
 * suite de phrases sans rang. */
const LIMITES_DU_PARCOURS = new Set([
  'position-non-declaree',
  'suspension',
  'sieges-replies',
]);

export default function CandidateProfile({ candidate }) {
  const c = candidate;
  const limitesDuParcours = (c.limites || []).filter((l) => LIMITES_DU_PARCOURS.has(l.cle));
  const limitesDeCollecte = (c.limites || []).filter((l) => !LIMITES_DU_PARCOURS.has(l.cle));

  return (
    <main className="cp-main">
      <div className="cp-breadcrumb">
        Candidats / <strong>{c.nom}</strong>
      </div>

      <header className="cp-entete">
        <p className="cp-sourcil">Candidat déclaré · élection présidentielle 2027</p>
        <h1>{c.nom}</h1>
        {/* LA SOURCE TERMINE LA LIGNE QU'ELLE SOURCE. Elle était posée en
            dessous, sur sa propre ligne : le lecteur devait rattacher un badge
            flottant à un texte, alors qu'il atteste exactement ces faits-là —
            profession, groupe, parti, naissance. */}
        <p className="cp-qui">
          <span>
            {[c.profession, c.groupe && `Groupe ${c.groupe}`, c.parti].filter(Boolean).join(' · ')}
            {c.naissance && `. ${c.voix.ne} le ${jour(c.naissance.date)}${c.naissance.lieu ? ` à ${c.naissance.lieu}` : ''}.`}
          </span>
          <BadgeSource url={c.sourceUrl} />
        </p>
      </header>

      {/* « Les grands chiffres » remplace « L'essentiel » (#328). Deux noms ont
          été essayés et écartés : « Coup d'œil » promettait de la rapidité, pas
          du contenu ; « L'essentiel » promettait une synthèse que le bloc ne
          délivre pas. Ce qu'on a construit est un TABLEAU DE BORD, et le nommer
          honnêtement libère la place pour un vrai résumé ailleurs.

          Il est dense — c'est assumé — donc repliable : il ne doit pas s'imposer
          avant que le lecteur ait choisi de le lire. */}
      <GrandsChiffres chiffres={c.grandsChiffres} parcours={c.parcours} />

      {/* La frise ET le détail daté vivent dans « En bref », au-dessus : les
          republier ici était de la redondance pure. Ce qui reste est ce que
          personne d'autre ne porte — les fonctions qu'on choisit d'exercer —
          et le titre le dit. */}
      <Section
        numero="1"
        titre="Les fonctions exercées"
        pied={
          <>
            Les trois plus longues par catégorie ; ligne surlignée = expérience sur + de la
            moitié du mandat.{' '}
            <Link to="/methodologie#fonctions">Pourquoi ce n’est pas un palmarès →</Link>
          </>
        }
      >
        {c.fonctions.blocs.length === 0 ? (
          <div className="cp-carte">
            <ListeVide cause={c.causes.mandats} source="Fonctions exercées" />
          </div>
        ) : (
          <Fonctions fonctions={c.fonctions} />
        )}
      </Section>

      {/* PAS DE CHAPEAU SUR CETTE SECTION. Il annonçait la règle avant qu'on
          ait rien lu — « une seule liste, quel que soit le banc… » — et faisait
          lire la consigne à la place du fait. Chaque figure porte désormais sa
          note SOUS elle : la cascade dit qu'aucun seuil ne s'applique et que la
          branche basse n'est pas un rejet, la chute dit que l'axe est le
          calendrier et qu'aucun rapport n'est calculé. */}
      <Section numero="2" titre={c.voix.titres.propose}>
        <Propositions
          amendements={c.amendements}
          textes={c.textes}
          causeAmendements={c.causes.amendements}
          causeTextes={c.causes.textes_portes}
          voix={c.voix}
        />
      </Section>

      <Section
        numero="3"
        titre={c.voix.titres.vote}
      >
        <Votes cause={c.causes.votes} votes={c.votes} />
      </Section>

      <Section
        numero="4"
        titre={c.voix.titres.ecarts}
        critere="Sa position à côté de celle de son groupe, scrutin par scrutin. Jamais totalisée."
      >
        <EcartsGroupe ecarts={c.ecarts} voix={c.voix} />
      </Section>

      <Section
        numero="5"
        titre={c.voix.titres.dit}
        critere="Ses interventions par période politique, puis par nature et par sujet. Le verbatim est celui du compte rendu."
      >
        <Paroles cause={c.causes.interventions} interventions={c.interventions} />
      </Section>

      <Section
        numero="6"
        titre="Ce qu’on n’a pas pu lire"
      >
        <Couverture
          couverture={c.couverture}
          parcours={limitesDuParcours}
          collecte={limitesDeCollecte}
        />
      </Section>

      {/* La licence SEULE. La phrase de refus qui l'accompagnait était la
          troisième occurrence de « aucun score, aucun classement » sur la même
          page ; elle vit maintenant dans le pied du site, une fois. */}
      <footer className="cp-pied">
        <span>{c.licence}</span>
      </footer>
    </main>
  );
}
