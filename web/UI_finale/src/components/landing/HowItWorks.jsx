import './landing.css';

// Squelette : contenu éditorial et style final traités dans une sub-issue dédiée.
const STEPS = [
  '[Placeholder] Étape 1',
  '[Placeholder] Étape 2',
  '[Placeholder] Étape 3',
];

export default function HowItWorks() {
  return (
    <section className="landing-section" aria-label="Comment ça marche">
      <h2>[Placeholder] Comment ça marche</h2>
      <ol>
        {STEPS.map((step) => (
          <li key={step}>{step}</li>
        ))}
      </ol>
    </section>
  );
}
