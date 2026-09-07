import StaticPage from '../components/StaticPage';
import { LAST_READING_RULE, WHOLE_TEXT_VOTE_BOUND } from '../utils/lecture';

const SECTIONS = [
  {
    heading: 'Textes portés',
    body: (
      <>
        <p>
          Un texte est affiché seulement si le pivot lui attribue un rôle factuel parmi{' '}
          <code>auteur</code>, <code>rapporteur</code> ou <code>co-rapporteur</code>, à un stade attestant
          qu'il a réellement été débattu.
        </p>
        <p>
          Les stades retenus commencent à <code>examine_commission</code>, puis incluent l'inscription à
          l'ordre du jour, la discussion en séance, l'adoption et la promulgation. Un dépôt seul, un rôle
          non retenu ou un volume d'interventions ne suffisent pas.
        </p>
      </>
    ),
  },
  {
    heading: 'Amendements',
    body: (
      <>
        <p>Les issues sont publiées en comptes bruts : adoptés, rejetés, retirés, tombés, irrecevables et non soutenus.</p>
        <p>
          Aucun taux d'adoption isolé n'est présenté. Ces issues dépendent du texte, de la procédure, de la
          recevabilité et du rôle du déposant ; elles ne constituent pas une mesure d'efficacité.
        </p>
      </>
    ),
  },
  {
    id: 'votes',
    heading: 'Votes de texte',
    body: (
      <>
        <p>
          L'univers retenu comprend les scrutins publics disponibles, ordinaires et solennels, portant sur
          l'ensemble d'un texte. Les votes sur un article, sur une partie de texte ou sur un amendement en
          sont exclus, de même que les motions de censure, qui sont des faits de procédure. Pour un même
          texte, une seule lecture est conservée dans la synthèse : la plus récente par sa date.
        </p>
        <p>
          <strong>{LAST_READING_RULE.phrase}</strong> {LAST_READING_RULE.pourquoi}
        </p>
        <p>
          <strong>{WHOLE_TEXT_VOTE_BOUND.phrase}</strong> {WHOLE_TEXT_VOTE_BOUND.pourquoi}
        </p>
        <p>
          Le choix de ne pas se limiter aux seuls scrutins solennels évite d'écarter des votes publics sur
          des textes entiers.
        </p>
        <h3>Pourquoi ces positions sont découpées en périodes</h3>
        <p>
          Un même vote ne dit pas la même chose selon d'où il est émis : depuis la majorité, voter contre
          n'arrive presque jamais ; depuis l'opposition, c'est le vote pour qui se remarque. La fiche ne
          totalise donc pas une carrière entière, elle la découpe en <strong>périodes politiques</strong> —
          une nouvelle dès que le banc ou le gouvernement en place change.
        </p>
        <p>
          Les deux repères sont <strong>déclarés, jamais déduits</strong>, et ils se complètent. Le banc
          vient de <code>position_dans_hemicycle</code>, que la validation du pivot refuse sans{' '}
          <code>source_url</code> ; le gouvernement vient des dates des fiches de gouvernement. De 2012 à
          2017, l'Assemblée publie le banc mais le corpus ne porte aucune fiche de gouvernement ; depuis
          2024, c'est l'inverse. Sur les 1 160 positions de dernière lecture des candidats déclarés, le banc
          seul en couvre 719 et le gouvernement seul 916 — <strong>le banc ou le gouvernement les couvre
          toutes les 1 160</strong>. Une période sans aucun des deux serait affichée comme telle, jamais
          rattachée à sa voisine.
        </p>
        <h3>D'où viennent la matière et l'origine d'un texte</h3>
        <p>
          La <strong>matière</strong> est la commission saisie au fond du dossier législatif, lue dans
          l'archive de l'Assemblée. Un scrutin ne porte aucune référence législative : le rattachement se
          fait dans l'autre sens, depuis les actes du dossier qui nomment les scrutins tenus. Il aboutit
          pour 711 des 1 160 positions. Les autres restent en « matière non établie » : c'est une absence
          de source, jamais une absence de commission, et elle n'est jamais comblée en devinant la matière
          depuis l'intitulé du scrutin.
        </p>
        <p>
          L'<strong>origine</strong> — texte du gouvernement ou du Parlement — est lue dans l'intitulé
          officiel du scrutin, qui nomme lui-même la catégorie juridique : « projet de loi » pour un texte
          du gouvernement, « proposition de loi » ou « proposition de résolution » pour un texte du
          Parlement. Ce n'est pas un rapprochement entre deux corpus, c'est un mot que la source pose ; il
          est reconnu sur les 1 160 positions.
        </p>
        <p>
          Le <strong>sort final du texte</strong> est celui du dossier, et il n'est pas dérivé du vote
          affiché : un texte peut être adopté en dernière lecture puis rejeté au terme de la navette. Il
          est publié pour 722 des 1 160 positions, et un texte adopté par engagement de responsabilité est
          nommé comme tel, jamais fondu dans les adoptions ordinaires.
        </p>
      </>
    ),
  },
  {
    heading: '49.3 et censure',
    body: (
      <>
        <p>
          Un texte adopté sans vote après engagement de responsabilité au titre de l'article 49.3 est
          signalé comme fait de procédure, jamais comme position de vote du candidat.
        </p>
        <p>
          Une motion de censure est un scrutin distinct. Elle est présentée séparément et reliée au texte
          concerné lorsque <code>texte_lie_id</code> est disponible.
        </p>
      </>
    ),
  },
  {
    heading: 'Présence',
    body: (
      <>
        <p>
          Empreinte politique ne publie aucun taux individuel d'assiduité, de présence ou d'absence. Un
          scrutin manqué ne décrit ni l'ensemble du travail parlementaire ni les motifs de non-participation.
        </p>
        <p>
          Les périodes d'incompatibilité liées à une fonction gouvernementale sont signalées comme faits
          institutionnels et ne sont pas assimilées à des absences.
        </p>
      </>
    ),
  },
  {
    heading: 'Groupes',
    body: (
      <>
        <p>
          Les ratios de cohésion de vote ne sont montrés que scrutin par scrutin, avec le nombre de membres
          éligibles et la fraction utilisée. Sans numérateur, dénominateur ou couverture suffisante, la
          valeur publique est <code>N/D</code>.
        </p>
        <p>Les écarts individuels au groupe restent des données de contrôle interne et ne sont pas publiés.</p>
      </>
    ),
  },
  {
    heading: 'Ordre des catégories',
    body: (
      <>
        <p>
          <code>position_dans_hemicycle</code> n'est utilisée que lorsqu'elle possède une source primaire
          (<code>source_url</code>). Elle permet de répartir les textes portés et les amendements d'un
          candidat en trois lots : <strong>Majorité</strong>, <strong>Opposition</strong> et{' '}
          <strong>Non distingué</strong> (éléments à cheval sur les deux périodes, ou dont la date ne
          correspond à aucune période sourcée).
        </p>
        <p>
          Sur le profil d'un candidat, l'onglet « Textes » affiche cette répartition sous forme de barres de
          comparaison (nombre de textes portés et d'amendements par catégorie). Le lot « Non distingué » est
          toujours affiché séparément, même à zéro : l'absence de donnée sourcée reste visible, conformément
          à la règle 6. Cette répartition n'est pour l'instant présentée que sur les profils candidat, pas
          sur les profils de groupe.
        </p>
      </>
    ),
  },
  {
    heading: 'Responsabilités',
    body: (
      <p>
        Les responsabilités sont dédupliquées par intitulé. Les fonctions de présidence ou de rapport
        peuvent servir à ordonner le détail, mais ce classement interne n'est jamais publié comme total ou
        score.
      </p>
    ),
  },
  {
    heading: 'Limites et sources',
    body: (
      <p>
        L'absence de donnée reste une absence de donnée, jamais un zéro. Chaque fait sensible doit remonter
        à une source primaire ; les classifications thématiques par mots-clés sont des aides de lecture, pas
        des positions déclarées.
      </p>
    ),
  },
];

export default function MethodologyPage() {
  return (
    <StaticPage
      eyebrow="Empreinte politique"
      title="Méthode éditoriale"
      tagline="Des faits sourcés, sans note de performance."
      sections={SECTIONS}
    />
  );
}
