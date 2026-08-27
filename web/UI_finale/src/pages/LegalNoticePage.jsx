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
        <p>
          Ce site s'appuie exclusivement sur des données publiques, réutilisées conformément aux
          licences suivantes. Ces licences ne sont pas les mêmes selon les sources, et le jeu de
          données publié ici <strong>n'est donc pas couvert par une licence unique</strong> :
          l'obligation de partage à l'identique s'applique à certains champs et pas à d'autres,
          comme détaillé en fin de section.
        </p>

        <h3>Open Data de l'Assemblée nationale</h3>
        <p>
          <strong>Seule source française collectée.</strong> L'identité et les mandats des députés,
          la composition des groupes parlementaires, les scrutins, les amendements, les dossiers
          législatifs, les questions écrites et les débats en séance (Syceron) proviennent du portail
          Open Data officiel de l'Assemblée nationale (data.assemblee-nationale.fr et
          questions.assemblee-nationale.fr), mis à disposition sous{' '}
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

        <h3>NosDéputés.fr et NosSénateurs.fr (Regards Citoyens)</h3>
        <p>
          Ces deux sources, projets de l'association Regards Citoyens, <strong>ne sont plus
          interrogées</strong> : NosSénateurs.fr est sorti du périmètre du site en août 2026, et
          NosDéputés.fr a été retiré du pipeline de collecte le même mois. Rien de ce qu'elles ont
          produit n'a pour autant été effacé — des mandats, des éléments d'identité, des prises de
          parole (dont l'URL de source pointe encore vers nosdeputes.fr) et les mots-clés dont
          dérivent les tags thématiques restent publiés. L'attribution et les obligations de la{' '}
          <strong>licence Open Database License (ODbL) v1.0</strong> leur restent donc dues :{' '}
          <a href="https://opendatacommons.org/licenses/odbl/1-0/" target="_blank" rel="noopener noreferrer">
            https://opendatacommons.org/licenses/odbl/1-0/
          </a>
        </p>
        <p className="static-note">
          Contient des informations issues de NosDéputés.fr et NosSénateurs.fr, par Regards Citoyens à
          partir de l'Assemblée nationale (ou du Sénat) et du Journal Officiel, mises à disposition sous
          licence ODbL.
        </p>
        <p className="static-note">
          Chaque profil publie la liste des licences dont son contenu relève
          (<code>meta.licence_donnees</code>) : cette mention y disparaît d'elle-même le jour où le
          profil ne porte plus rien qui vienne de ces deux sources.
        </p>

        <h3>Parltrack</h3>
        <p>
          Les données relatives aux député·es européen·nes (dossiers législatifs, votes, activités)
          proviennent des dumps JSON de Parltrack (parltrack.org), mis à disposition sous licence{' '}
          <strong>Open Database License (ODbL) v1.0</strong> :{' '}
          <a href="https://opendatacommons.org/licenses/odbl/1-0/" target="_blank" rel="noopener noreferrer">
            https://opendatacommons.org/licenses/odbl/1-0/
          </a>{' '}
          — <strong>source active</strong>, et la clause de partage à l'identique s'y applique
          pleinement.
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
          licences. <strong>Seuls les champs dérivés de sources sous ODbL (Parltrack, et NosDéputés.fr /
          NosSénateurs.fr pour les champs déjà publiés qui en proviennent)</strong>{' '}
          sont soumis à la clause de partage à l'identique de l'ODbL : toute republication d'un jeu de
          données dérivé téléchargeable incluant ces champs doit être mise à disposition sous une licence à
          clauses équivalentes. Les champs issus de l'Open Data de l'Assemblée nationale (Licence Ouverte /
          Etalab) et du Parlement européen n'imposent qu'une obligation d'attribution, sans partage à
          l'identique. Les champs issus de Wikidata (CC0) ne sont soumis à aucune restriction.
        </p>
        <p>
          Le retrait de NosDéputés.fr et de NosSénateurs.fr de la collecte <strong>ne rend donc pas
          l'ensemble du corpus réutilisable sous simple attribution</strong>, pour deux raisons
          distinctes : Parltrack reste une source active sous ODbL, et des champs dérivés de Regards
          Citoyens restent publiés. Pour savoir ce qui s'applique à un profil donné, lire son champ{' '}
          <code>meta.licence_donnees</code>, qui énumère les licences dont ce profil relève. Dans tous les
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
      updated="Dernière mise à jour : 27 août 2026"
      sections={SECTIONS}
    />
  );
}
