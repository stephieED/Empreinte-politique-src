import './landing.css';

// Squelette : contenu éditorial et style final traités dans une sub-issue dédiée.
const QUESTIONS = [
  { question: '[Placeholder] Question 1', answer: '[Placeholder] Réponse 1' },
  { question: '[Placeholder] Question 2', answer: '[Placeholder] Réponse 2' },
];

export default function Faq() {
  return (
    <section className="landing-section" aria-label="Questions fréquentes">
      <h2>[Placeholder] Questions fréquentes</h2>
      {QUESTIONS.map(({ question, answer }) => (
        <details key={question}>
          <summary>{question}</summary>
          <p>{answer}</p>
        </details>
      ))}
    </section>
  );
}
