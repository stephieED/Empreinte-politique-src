// Config partagée des sources de données, factuelle et pure (pas de JSX).
// Reprise telle quelle depuis AGENTS.md §7 (Sources and licenses) et README.md
// (Source taxonomy, Coverage limits, Data freshness). Ne pas arrondir/inventer
// une cadence ou une licence : toute mise à jour de ces valeurs doit d'abord
// passer par AGENTS.md / README.md, puis être répercutée ici.
// Consommée par la section "Sources & fraîcheur" et par les tooltips de licence
// de la landing page — ne jamais hardcoder ces informations dans un composant.
//
// Ce tableau liste les sources dont le site publie des données, pas seulement
// celles qu'il interroge encore. NosDéputés/NosSénateurs y reste : elle n'est
// plus collectée, mais des champs publiés en dérivent, et l'attribution ODbL
// leur est due tant qu'ils sont là (#530).

export const sourcesConfig = [
  {
    id: 'nosdeputes-nossenateurs',
    nom: 'NosDeputes.fr / NosSenateurs.fr',
    type: 'Source retirée — attribution toujours due',
    contenuCouvert:
      "Champs déjà publiés qui en dérivent : mandats et identité collectés avant 2026, 511 interventions dont l'URL de source pointe encore vers nosdeputes.fr, et les mots-clés dont sont dérivés les tags thématiques.",
    cadenceMiseAJour:
      "Plus collectée depuis août 2026 : NosSénateurs est sorti du périmètre (certificat expiré), et NosDéputés a été retiré du pipeline après une panne durable. Rien n'est plus rafraîchi depuis cette source ; rien de ce qu'elle a produit n'a été effacé.",
    licence: 'ODbL v1.0',
    implication:
      "Réutilisation possible, mais toute republication sous forme de jeu de données téléchargeable incluant ces champs doit être partagée sous la même licence (share-alike). L'attribution reste due tant que ces champs sont publiés.",
    perimetre: ['AN', 'Senat'],
    couverturePeriode:
      "Identité et groupe (identite.groupe_sigle) figés sur les données pré-dissolution 2024 ; aucune donnée postérieure. Les mandats et votes servis aujourd'hui viennent de l'open data de l'Assemblée nationale.",
  },
  {
    id: 'assemblee-nationale-opendata',
    nom: 'data.assemblee-nationale.fr',
    type: 'Dumps ZIP (open data)',
    contenuCouvert:
      "Seule source française collectée : identité et mandats des députés, composition des groupes, votes officiels, amendements, dossiers législatifs, questions (questions.assemblee-nationale.fr) et débats en séance (Syceron).",
    cadenceMiseAJour: 'Quotidienne.',
    licence: 'Licence Ouverte / Open Licence (Etalab)',
    implication: 'Réutilisation libre sous réserve de mention de la source (attribution uniquement, pas de partage à l\'identique).',
    perimetre: ['AN'],
    couverturePeriode:
      "Votes officiels disponibles pour les législatures 14 à 17, selon les dumps existants ; aucun équivalent officiel intégré pour le Sénat, sorti du périmètre.",
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
  // CITÉES, PAS COLLECTÉES (#860). Les mandats nationaux antérieurs à ce que
  // publie l'open data de l'Assemblée sont relus à la main, un par un, et
  // portés par les fiches avec leur lien (`mandats_anterieurs`). Aucun
  // collecteur n'interroge ces deux sites.
  {
    id: 'sycomore',
    nom: 'Sycomore (Assemblée nationale)',
    type: 'Fiches consultées, relues à la main',
    contenuCouvert:
      "Mandats de député antérieurs au 19 juin 2002, que l'open data de l'Assemblée ne rattache pas : fonction et dates, citées mandat par mandat avec un lien vers la fiche du député.",
    cadenceMiseAJour:
      "Aucune collecte : table relue une fois (raw_data/mandats_anterieurs.json), complétée quand un candidat se déclare.",
    licence: 'Tous droits réservés (Assemblée nationale) — faits cités',
    implication:
      "Seuls des faits — une fonction, deux dates — sont repris, chacun avec son lien ; aucun contenu du site n'est reproduit.",
    perimetre: ['AN'],
    couverturePeriode: null,
  },
  {
    id: 'journal-officiel',
    nom: 'Journal officiel (Légifrance)',
    type: 'Décrets consultés, relus à la main',
    contenuCouvert:
      "Fonctions gouvernementales antérieures à celles que publie l'open data de l'Assemblée : décrets relatifs à la composition du Gouvernement, cités fonction par fonction.",
    cadenceMiseAJour:
      "Aucune collecte : table relue une fois (raw_data/mandats_anterieurs.json), complétée quand un candidat se déclare.",
    licence: 'Licence Ouverte 2.0 (Etalab)',
    implication: 'Réutilisation libre sous réserve de mention de la source (attribution uniquement).',
    perimetre: ['Gouvernement'],
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
