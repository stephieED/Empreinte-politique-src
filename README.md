# CV_CandidatFR

Génère des « CV politiques » structurés (mandats, responsabilités, votes,
dossiers législatifs, interventions en séance) pour les candidats à
l'élection présidentielle française de 2027, à partir des données ouvertes
de [NosDéputés.fr / NosSénateurs.fr](https://github.com/regardscitoyens)
(Regards Citoyens, licence ODbL) et de l'
[open data de l'Assemblée nationale](https://data.assemblee-nationale.fr/)
pour le détail des votes.

Le projet ne porte aucun jugement de valeur : il agrège des faits bruts avec
des liens vers leurs sources.

## Arborescence

```
CV_CandidatFR/
├── src/                          # Scripts Python
│   ├── candidate_profile.py      # Construit le profil JSON d'UN candidat
│   ├── generate_all_profiles.py  # Construit les profils de TOUS les candidats (batch)
│   └── render_profile.py         # Convertit un profil JSON en page HTML statique
├── data/
│   ├── candidats.json            # Liste source des candidats (nom, slug, parti...)
│   └── profiles/                 # Profils générés : <slug>.json + <slug>.html
├── web/
│   └── index.html                # Page web dynamique (sélecteur de candidat)
├── docs/
│   └── nosdeputes_doc/           # Documentation de l'API NosDéputés/NosSénateurs (référence)
├── tests/
│   └── test_candidate_profile.py
└── README.md
```

- `.cache/` (créé automatiquement, ignoré par git) : cache local des archives
  de votes officielles téléchargées depuis data.assemblee-nationale.fr, pour
  éviter de re-télécharger ~4000 fichiers à chaque exécution.

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install requests beautifulsoup4 pytest
```

Toutes les commandes ci-dessous sont à exécuter **depuis la racine du
dépôt**, avec l'environnement virtuel activé.

## 1. Générer le profil d'un seul candidat

```bash
python src/candidate_profile.py jean-luc-melenchon --chambre deputes
python src/candidate_profile.py bruno-retailleau --chambre senateurs
```

Écrit par défaut dans `data/profiles/<slug>.json`. Options utiles :

| Option | Effet |
|---|---|
| `--chambre {deputes,senateurs}` | Chambre du parlementaire (défaut : `deputes`) |
| `--out chemin.json` | Change le fichier de sortie |
| `--max-pages N` | Limite la pagination de la recherche d'interventions (défaut : 10 pages de 50 résultats). Réduire accélère fortement la génération, au prix d'une couverture moins complète. |

Puis générer la page HTML correspondante :

```bash
python src/render_profile.py data/profiles/jean-luc-melenchon.json
# écrit data/profiles/jean-luc-melenchon.html par défaut (--out pour changer)
```

## 2. Générer les profils de tous les candidats (batch)

```bash
python src/generate_all_profiles.py                          # tous les candidats avec un slug
python src/generate_all_profiles.py --only jean-luc-melenchon # un seul candidat
python src/generate_all_profiles.py --max-pages 5             # recherche plus légère/rapide
python src/generate_all_profiles.py --skip-existing           # ne relance pas ce qui est déjà généré
```

Ce script lit `data/candidats.json`, ignore proprement les candidats sans
`slug` (non référencés sur NosDéputés/NosSénateurs), essaie automatiquement
`deputes` puis `senateurs`, et écrit `data/profiles/<slug>.json` +
`data/profiles/<slug>.html` pour chaque candidat traité.

## 3. Consulter les profils dans le navigateur

Servir le dépôt via un serveur HTTP local (nécessaire : `index.html` charge
les JSON via `fetch()`, ce qui échoue en ouvrant le fichier directement avec
`file://`) :

```bash
python -m http.server 8000
```

Puis ouvrir <http://localhost:8000/web/> dans un navigateur : un menu
déroulant permet de choisir un candidat et affiche son profil, chargé
dynamiquement depuis `data/profiles/<slug>.json`.

Chaque `data/profiles/<slug>.html` généré par `render_profile.py` est aussi
une page HTML autonome consultable directement.

## Contenu d'un profil

Chaque `data/profiles/<slug>.json` contient :

- `identite` : nom, groupe politique, profession, circonscription...
- `mandats` : mandat électif de base + responsabilités réelles (commissions,
  missions d'information, groupes d'amitié, engagements extra-parlementaires),
  chacune avec sa fonction (membre/président/rapporteur...), ses dates de
  début/fin et un indicateur `actif`.
- `votes` : positions de vote sur les scrutins, avec leur source
  (`votes_source`) — provient en priorité de l'open data officiel de
  l'Assemblée nationale (fiable et à jour), NosDéputés.fr servant de repli
  quand disponible.
- `dossiers_legislatifs` : dossiers législatifs traités par la chambre sur
  les dernières législatures couvertes.
- `interventions` : prises de parole trouvées via la recherche plein texte,
  chacune avec sa date, son sujet, son texte, la `fonction` occupée par
  l'orateur à ce moment-là (ex. « Première ministre »), et un `format` dérivé
  du nombre de mots (`reaction_courte` pour une interjection/exclamation vs
  `prise_de_parole_developpee` pour une intervention construite).
- `meta.warnings` : liste des sources indisponibles ou incomplètes pour ce
  profil (à titre de transparence, jamais masqué).

## Tests

```bash
pytest -q
```

## Limites connues

- Les votes ne sont récupérés via l'open data officiel que pour les
  **députés** (législatures 14 à 16) ; les sénateurs n'ont pas encore
  d'équivalent officiel intégré, et la législature 17 (en cours) n'est pas
  encore couverte.
- Les interventions sont retrouvées par recherche plein texte du nom du
  candidat : un candidat très peu cité ou avec un nom ambigu peut avoir une
  couverture partielle.
- La documentation de l'API dans `docs/nosdeputes_doc/` est fournie par
  Regards Citoyens à titre de référence ; certains endpoints qu'elle décrit
  (ex. le détail des votes par scrutin) sont aujourd'hui hors service côté
  NosDéputés.fr/NosSénateurs.fr.
