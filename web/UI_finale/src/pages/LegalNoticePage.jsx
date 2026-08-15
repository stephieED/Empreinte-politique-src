import StaticPage from '../components/StaticPage';

const SECTIONS = [
  {
    heading: 'Éditeur du site',
    body: (
      <>
        <p>
          Ce site est édité à titre non professionnel et non commercial par une personne physique.
          Conformément à l'article 6-III de la loi n° 2004-575 du 21 juin 2004 pour la confiance dans
          l'économie numérique (LCEN), l'identité complète de l'éditeur est tenue à la disposition de
          l'hébergeur du site et pourra être communiquée, sur demande, à toute autorité judiciaire
          compétente.
        </p>
        <p>
          <strong>Contact éditeur</strong> :{' '}
          <a href="mailto:empreinte.politique@gmail.com">empreinte.politique@gmail.com</a>
        </p>
      </>
    ),
  },
  {
    heading: 'Hébergement',
    body: (
      <p>
        <em>À préciser.</em> L'hébergement définitif de ce site n'est pas encore déterminé à la date de
        rédaction de cette page ; cette section sera complétée dès qu'un hébergeur sera choisi.
      </p>
    ),
  },
  {
    heading: 'Directeur de la publication',
    body: (
      <p>
        La direction de la publication est assurée par l'éditeur du site, joignable à l'adresse
        ci-dessus.
      </p>
    ),
  },
  {
    heading: 'Propriété intellectuelle — code et contenu éditorial',
    body: (
      <p>
        Le code source, la charte graphique et les textes rédigés pour ce site sont à préciser, sauf
        mention contraire pour les données présentées (voir « Sources et licences des données »
        ci-dessous).
      </p>
    ),
  },
  {
    heading: 'Sources et licences des données',
    body: (
      <>
        <p>Ce site s'appuie exclusivement sur des données publiques, réutilisées conformément aux licences suivantes.</p>

        <h3>NosDéputés.fr et NosSénateurs.fr (Regards Citoyens)</h3>
        <p>
          Les données relatives aux député·es et sénateur·rices français·es (mandats, votes, amendements)
          proviennent de NosDéputés.fr et NosSénateurs.fr, projets de l'association Regards Citoyens, mises
          à disposition sous licence <strong>Open Database License (ODbL) v1.0</strong> :{' '}
          <a href="https://opendatacommons.org/licenses/odbl/1-0/" target="_blank" rel="noopener noreferrer">
            https://opendatacommons.org/licenses/odbl/1-0/
          </a>
        </p>
        <p className="static-note">
          Contient des informations issues de NosDéputés.fr et NosSénateurs.fr, par Regards Citoyens à
          partir de l'Assemblée nationale (ou du Sénat) et du Journal Officiel, mises à disposition sous
          licence ODbL.
        </p>

        <h3>Open Data de l'Assemblée nationale</h3>
        <p>
          Les scrutins, amendements, dossiers législatifs, questions écrites et débats en séance (Syceron)
          proviennent du portail Open Data officiel de l'Assemblée nationale
          (data.assemblee-nationale.fr), mis à disposition sous{' '}
          <strong>Licence Ouverte / Open Licence</strong> (Etalab) :{' '}
          <a
            href="https://data.assemblee-nationale.fr/licence-ouverte-open-licence"
            target="_blank"
            rel="noopener noreferrer"
          >
            https://data.assemblee-nationale.fr/licence-ouverte-open-licence
          </a>
        </p>
        <p className="static-note">
          Contient des informations publiques issues du portail Open Data de l'Assemblée nationale, sous
          Licence Ouverte / Open Licence. Cette licence autorise la réutilisation commerciale et
          l'adaptation sans obligation de partage à l'identique, sous réserve de mention de la paternité.
        </p>

        <h3>Parltrack</h3>
        <p>
          Les données relatives aux député·es européen·nes (dossiers législatifs, votes, activités)
          proviennent des dumps JSON de Parltrack (parltrack.org), mis à disposition sous licence{' '}
          <strong>Open Database License (ODbL) v1.0</strong> :{' '}
          <a href="https://opendatacommons.org/licenses/odbl/1-0/" target="_blank" rel="noopener noreferrer">
            https://opendatacommons.org/licenses/odbl/1-0/
          </a>
        </p>
        <p className="static-note">
          Contient des informations issues de Parltrack (parltrack.org), mises à disposition sous licence
          ODbL.
        </p>

        <h3>Parlement européen</h3>
        <p>
          Les fiches et photos des député·es européen·nes proviennent du portail Open Data du Parlement
          européen (data.europarl.europa.eu) et du site institutionnel (www.europarl.europa.eu),
          réutilisées conformément au Legal Notice du Parlement européen :{' '}
          <a href="https://www.europarl.europa.eu/legal-notice/fr/" target="_blank" rel="noopener noreferrer">
            https://www.europarl.europa.eu/legal-notice/fr/
          </a>{' '}
          — reproduction, diffusion commerciale ou non commerciale autorisées sous réserve de reproduire
          l'élément dans son intégralité et d'en indiquer la source (« © Union européenne, [année] – Source :
          Parlement européen »).
        </p>

        <h3>Wikipédia et Wikidata</h3>
        <p>
          Le statut de candidature déclarée peut être recoupé via Wikipédia (fr.wikipedia.org) et Wikidata
          (query.wikidata.org). Ces deux sources ont des licences <strong>distinctes</strong> : Wikipédia
          est sous <strong>Creative Commons Attribution — Partage dans les mêmes conditions 4.0 (CC BY-SA 4.0)</strong>{' '}
          (
          <a href="https://creativecommons.org/licenses/by-sa/4.0/" target="_blank" rel="noopener noreferrer">
            https://creativecommons.org/licenses/by-sa/4.0/
          </a>
          ) ; les données structurées de Wikidata sont sous <strong>CC0 1.0</strong>, domaine public (
          <a
            href="https://creativecommons.org/publicdomain/zero/1.0/"
            target="_blank"
            rel="noopener noreferrer"
          >
            https://creativecommons.org/publicdomain/zero/1.0/
          </a>
          ), sans obligation d'attribution ni de partage à l'identique.
        </p>

        <h3>Implication pour la réutilisation de nos propres données</h3>
        <p>
          Les jeux de données JSON produits et publiés par ce site combinent des contenus sous plusieurs
          licences. <strong>Seuls les champs dérivés de sources sous ODbL (NosDéputés.fr, NosSénateurs.fr, Parltrack)</strong>{' '}
          sont soumis à la clause de partage à l'identique de l'ODbL : toute republication d'un jeu de
          données dérivé téléchargeable incluant ces champs doit être mise à disposition sous une licence à
          clauses équivalentes. Les champs issus de l'Open Data de l'Assemblée nationale (Licence Ouverte /
          Etalab) et du Parlement européen n'imposent qu'une obligation d'attribution, sans partage à
          l'identique. Les champs issus de Wikidata (CC0) ne sont soumis à aucune restriction. Dans tous les
          cas, la consultation du site lui-même (page HTML, « Produced Work » au sens de l'ODbL) reste
          couverte par la simple attribution ci-dessus.
        </p>
      </>
    ),
  },
];

export default function LegalNoticePage() {
  return (
    <StaticPage
      eyebrow="Empreinte politique"
      title="Mentions légales"
      updated="Dernière mise à jour : 14 août 2026"
      sections={SECTIONS}
    />
  );
}
