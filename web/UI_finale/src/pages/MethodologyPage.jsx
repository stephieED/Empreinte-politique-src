import StaticPage from '../components/StaticPage';

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
    heading: 'Votes de texte',
    body: (
      <>
        <p>
          L'univers retenu comprend tous les scrutins publics disponibles, ordinaires et solennels, portant
          sur l'ensemble d'un texte. Pour un même texte, seule la lecture la plus avancée connue est
          conservée dans la synthèse.
        </p>
        <p>
          Les votes sur des articles ou amendements sont exclus de cette synthèse. Le choix de ne pas se
          limiter aux seuls scrutins solennels évite d'écarter des votes publics sur des textes entiers.
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
