// Fait fictif à but pédagogique, utilisé uniquement par le widget de démo de
// la landing page (section "Un fait, une source", issue #145). Jamais une
// donnée candidate réelle — ne pas remplacer par un extrait de `public/data/`.
// Le domaine de la source utilise le TLD réservé `.example` (RFC 2606), qui ne
// résout jamais vers un site réel, pour qu'aucune URL affichée ne puisse être
// confondue avec une vraie source.
const demoFact = {
  acteur: 'Élu·e X',
  mandat: 'Député·e (exemple fictif) — circonscription fictive',
  fait: {
    texte: 'Vote sur le Texte Y — projet de loi (exemple fictif)',
    positionLabel: 'Pour',
    color: '#007A45',
    date: '12 mars 2026',
  },
  source: {
    label: 'Scrutin officiel (exemple fictif)',
    url: 'https://scrutins.assemblee.example/texte-y/vote-234',
    syncedAt: '1 août 2026',
  },
};

export default demoFact;
