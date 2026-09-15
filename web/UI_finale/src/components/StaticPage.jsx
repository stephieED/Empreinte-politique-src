import { Link } from 'react-router-dom';
import Brand from './Brand';
import PiedDeSite from './PiedDeSite';
import '../styles/shell.css';
import './StaticPage.css';

// Page statique partagée (Méthodologie, Mentions légales) : bannière + sections,
// hors ExplorerLayout — ces pages n'ont pas de candidat/groupe sélectionné, les
// bandeaux Groupes/Gouvernements/Candidats n'ont donc pas de sens ici.
export default function StaticPage({ eyebrow, title, tagline, updated, sections }) {
  return (
    <div className="app-shell">
      <div className="static-page">
        <Brand />
        <main className="static-main">
          <p className="static-breadcrumb">
            <Link to="/">← Retour à l'accueil</Link>
          </p>

          <div className="static-banner">
            {eyebrow && <span className="static-banner-tag">{eyebrow}</span>}
            <h1>{title}</h1>
            {tagline && <p>{tagline}</p>}
          </div>

          {updated && <p className="static-updated">{updated}</p>}

          <div className="static-sections">
            {sections.map((section) =>
              /* UNE ENTRÉE `famille` N'EST PAS UNE SECTION, c'est le titre du
                 groupe qui suit (#328). Le tableau reste PLAT : les ancres
                 (`/methodologie#votes`) ne bougent pas, et une page qui ne
                 déclare aucune famille — les mentions légales — se rend
                 exactement comme avant.

                 Une famille peut être VIDE et porter un `note` : la fiche de
                 gouvernement n'a aucune section de méthode, et le dire est
                 préférable à un lecteur qui cherche sans savoir pourquoi il ne
                 trouve pas (§2 règle 5). */
              section.famille ? (
                <div className="static-famille" key={`famille-${section.famille}`}>
                  <h2>{section.famille}</h2>
                  {section.note}
                </div>
              ) : (
                // `id` optionnel : il rend une section ATTEIGNABLE depuis une
                // fiche (`/methodologie#votes`). Sans lui, un renvoi posé sous une
                // figure dépose le lecteur en haut d'une page de dix sections.
                <section className="static-card" key={section.heading} id={section.id}>
                  <h2>{section.heading}</h2>
                  {section.body}
                </section>
              ),
            )}
          </div>
        </main>
        <PiedDeSite />
      </div>
    </div>
  );
}
