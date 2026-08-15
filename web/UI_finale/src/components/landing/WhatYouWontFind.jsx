import './landing.css';

// Squelette : contenu éditorial et style final traités dans une sub-issue dédiée.
const ITEMS = ['[Placeholder] Pas de score', '[Placeholder] Pas de classement', '[Placeholder] Pas de taux d\'assiduité'];

export default function WhatYouWontFind() {
  return (
    <section className="landing-section" aria-label="Ce que vous ne trouverez pas ici">
      <h2>[Placeholder] Ce que vous ne trouverez pas ici</h2>
      <ul>
        {ITEMS.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </section>
  );
}
