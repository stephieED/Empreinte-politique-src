// Config partagée des sources de données, factuelle et pure (pas de JSX).
// Reprise telle quelle depuis AGENTS.md §7 (Sources and licenses) et README.md
// (Source taxonomy, Coverage limits, Data freshness). Ne pas arrondir/inventer
// une cadence ou une licence : toute mise à jour de ces valeurs doit d'abord
// passer par AGENTS.md / README.md, puis être répercutée ici.
// Consommée par la section "Sources & fraîcheur" et par les tooltips de licence
// de la landing page — ne jamais hardcoder ces informations dans un composant.

export const sourcesConfig = [
  {
    id: 'nosdeputes-nossenateurs',
    nom: 'NosDeputes.fr / NosSenateurs.fr',
    type: 'API JSON/XML',
    contenuCouvert: 'Fiches déclaratives des députés et sénateurs (identité, mandats, groupe).',
    cadenceMiseAJour:
      "Figée sur la 16e législature (les 618 fiches AN ont un mandat_fin) ; archives des législatures closes également figées.",
    licence: 'ODbL v1.0',
    implication:
      "Réutilisation possible, mais toute republication sous forme de jeu de données téléchargeable doit être partagée sous la même licence (share-alike).",
    perimetre: ['AN', 'Senat'],
    couverturePeriode:
      "Identité et groupe (identite.groupe_sigle) figés sur les données pré-dissolution 2024 ; pas de flux vivant au-delà.",
  },
  {
    id: 'assemblee-nationale-opendata',
    nom: 'data.assemblee-nationale.fr',
    type: 'Dumps ZIP (open data)',
    contenuCouvert: 'Votes officiels des députés, questions (questions.assemblee-nationale.fr).',
    cadenceMiseAJour: 'Quotidienne.',
    licence: 'Licence Ouverte / Open Licence (Etalab)',
    implication: 'Réutilisation libre sous réserve de mention de la source (attribution uniquement).',
    perimetre: ['AN'],
    couverturePeriode:
      "Votes officiels disponibles pour les législatures 14 à 17, selon les dumps existants ; aucun équivalent officiel intégré pour le Sénat.",
  },
  {
    id: 'parltrack',
    nom: 'Parltrack',
    type: 'Dumps LZMA (JSON)',
    contenuCouvert: 'Mandats, votes et activité des eurodéputés au Parlement européen.',
    cadenceMiseAJour: 'Hebdomadaire (environ).',
    licence: 'ODbL v1.0',
    implication:
      "Réutilisation possible, mais toute republication sous forme de jeu de données téléchargeable doit être partagée sous la même licence (share-alike).",
    perimetre: ['PE'],
    couverturePeriode: null,
  },
  {
    id: 'parlement-europeen-opendata',
    nom: 'Parlement européen Open Data',
    type: 'API REST + pages MEP',
    contenuCouvert: 'Données institutionnelles des eurodéputés (data.europarl.europa.eu, www.europarl.europa.eu).',
    cadenceMiseAJour: 'En direct (récupérées à chaque exécution, pas de cache hebdomadaire).',
    licence: 'EP Legal Notice (reuse policy, attribution-based)',
    implication: 'Réutilisation libre sous réserve de mention de la source (attribution uniquement).',
    perimetre: ['PE'],
    couverturePeriode: null,
  },
  {
    id: 'wikipedia-fr',
    nom: 'French Wikipedia',
    type: 'API MediaWiki REST',
    contenuCouvert: 'Suivi biographique complémentaire des candidats.',
    cadenceMiseAJour: 'Immédiate.',
    licence: 'CC BY-SA 4.0',
    implication:
      "Utilisable pour des citations verbatim uniquement (usage actuel du projet) ; toute réutilisation plus large doit être partagée sous la même licence (share-alike).",
    perimetre: ['Suivi candidat'],
    couverturePeriode: null,
  },
  {
    id: 'wikidata',
    nom: 'Wikidata',
    type: 'SPARQL',
    contenuCouvert: 'Suivi biographique complémentaire des candidats.',
    cadenceMiseAJour: 'Immédiate.',
    licence: 'CC0 1.0',
    implication: 'Domaine public : aucune restriction de réutilisation.',
    perimetre: ['Suivi candidat'],
    couverturePeriode: null,
  },
];

export default sourcesConfig;
