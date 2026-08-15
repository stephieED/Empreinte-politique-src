import './landing.css';

const QUESTIONS = [
  {
    question: 'Est-ce que c’est objectif ?',
    answer:
      'Empreinte politique n’attribue ni note, ni classement, ni avis. Chaque fait affiché — vote, mandat, texte porté, intervention — est relié à sa source primaire et à sa date de synchronisation. L’outil donne à lire l’activité parlementaire telle qu’elle est publiée, sans la commenter.',
  },
  {
    question: 'D’où viennent les données ?',
    answer:
      'De sources publiques : NosDéputés.fr, NosSénateurs.fr, l’open data de l’Assemblée nationale, du Parlement européen et de Wikidata. Chaque profil indique ses sources et sa date de dernière synchronisation ; une donnée manquante est affichée comme manquante, jamais remplacée par un zéro.',
  },
  {
    question: 'Pourquoi pas de notation ?',
    answer:
      'Une note ou un classement résume — et masque autant qu’il éclaire. Empreinte politique montre les faits bruts (votes, textes portés, mandats) pour que chacun se forme son propre jugement, plutôt que de le préformer à sa place.',
  },
  {
    question: 'Pourquoi n’y a-t-il pas de taux de présence individuel ?',
    answer:
      'Un scrutin manqué ne décrit ni le travail parlementaire ni ses motifs (commission, texte porté, absence justifiée…). Empreinte politique ne publie donc aucun taux individuel d’assiduité, de présence ou d’absence.',
  },
];

export default function Faq() {
  return (
    <section className="landing-section" aria-label="Questions fréquentes">
      <h2>Questions fréquentes</h2>
      <div className="landing-faq-list">
        {QUESTIONS.map(({ question, answer }) => (
          <details className="landing-faq-item" key={question}>
            <summary>{question}</summary>
            <p>{answer}</p>
          </details>
        ))}
      </div>
    </section>
  );
}
