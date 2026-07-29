# CV_CandidatFR

Génère des « CV politiques » structurés (mandats, responsabilités, votes,
dossiers législatifs, interventions en séance) pour les candidats à
l'élection présidentielle française de 2027, à partir des données ouvertes
de [NosDéputés.fr / NosSénateurs.fr](https://github.com/regardscitoyens)
(Regards Citoyens, licence ODbL), de l'
[open data de l'Assemblée nationale](https://data.assemblee-nationale.fr/)
pour le détail des votes, et de l'
[Open Data Portal du Parlement européen](https://data.europarl.europa.eu/)
(licence CC BY 4.0) pour le volet mandat européen des candidats ayant été
eurodéputé⋅e⋅s.

Le projet ne porte aucun jugement de valeur : il agrège des faits bruts avec
des liens vers leurs sources.

## Arborescence

```
CV_CandidatFR/
├── src/                          # Scripts Python
│   ├── candidate_profile.py      # Construit le profil JSON français d'UN candidat
│   ├── candidate_profile_ue.py   # Construit le volet "mandat européen" d'UN candidat
│   ├── generate_all_profiles.py  # Construit les profils de TOUS les candidats (batch, FR + UE)
│   └── render_profile.py         # Convertit un profil JSON en page HTML statique
├── data/
│   ├── candidats.json            # Liste source des candidats (nom, slug, parti...)
│   └── profiles/                 # Profils générés : <slug>.json + <slug>.html
├── web/
│   └── index.html                # Page web dynamique (sélecteur de candidat)
├── docs/
│   └── nosdeputes_doc/           # Documentation de l'API NosDéputés/NosSénateurs (référence)
├── tests/
│   ├── test_candidate_profile.py
│   └── test_candidate_profile_ue.py
└── README.md
```

- `.cache/` (créé automatiquement, ignoré par git) : cache local des archives
  de votes officielles téléchargées depuis data.assemblee-nationale.fr, ainsi
  que de la liste des eurodéputé⋅e⋅s et des organisations du Parlement
  européen (`.cache/europarl/`), pour éviter de re-télécharger ces données
  volumineuses et quasi-statiques à chaque exécution.

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

## 2. Ajouter le volet "mandat européen" d'un candidat

Certains candidats ont été eurodéputé⋅e⋅s (ex. Jordan Bardella, Marine Le
Pen, Jean-Luc Mélenchon). Ce volet est récupéré séparément, via l'Open Data
Portal officiel du Parlement européen, et peut être consulté seul :

```bash
python src/candidate_profile_ue.py "Jordan Bardella"
# affiche le JSON sur stdout ; ajouter --out chemin.json pour l'écrire dans un fichier
```

La recherche se fait par égalité exacte du nom complet (normalisé : accents,
casse et ordre des mots ignorés) parmi la liste complète des eurodéputé⋅e⋅s
ayant représenté un pays (`--country`, défaut `FR`). Un candidat non trouvé
n'est pas une erreur : cela signifie simplement qu'il n'a jamais été membre
du Parlement européen. En pratique, ce script est surtout utile en isolation
pour déboguer : `generate_all_profiles.py` (section suivante) l'appelle déjà
automatiquement pour chaque candidat et fusionne le résultat dans le profil.

### Cette API est-elle légale à utiliser ?

Oui. L'API `https://data.europarl.europa.eu/api/v2/` est publiée par le
Parlement européen lui-même sous licence **CC BY 4.0** (Creative Commons
Attribution 4.0 International — réutilisation libre, y compris commerciale,
à condition de créditer la source), comme indiqué explicitement dans le champ
`info.license` de sa spécification OpenAPI publique. Deux règles techniques
sont à respecter (déjà implémentées dans `candidate_profile_ue.py`) :

- envoyer un en-tête `User-Agent` identifiant le projet réutilisateur ;
- rester sous la limite de **500 requêtes / 5 minutes**.

## 3. Générer les profils de tous les candidats (batch)

```bash
python src/generate_all_profiles.py                          # tous les candidats
python src/generate_all_profiles.py --only jean-luc-melenchon # un seul candidat
python src/generate_all_profiles.py --max-pages 5             # recherche plus légère/rapide
python src/generate_all_profiles.py --skip-existing           # ne relance pas ce qui est déjà généré
python src/generate_all_profiles.py --skip-ue                 # ne pas interroger l'API du Parlement européen
```

Ce script lit `data/candidats.json` et, pour chaque candidat :

1. essaie de construire son profil français (`deputes` puis `senateurs`) via
   son `slug` NosDéputés/NosSénateurs, s'il en a un ;
2. recherche systématiquement (sauf `--skip-ue`) un mandat européen par nom
   via `candidate_profile_ue.py`, et le fusionne dans le profil sous la clé
   `mandat_europeen` ;
3. écrit `data/profiles/<slug>.json` + `data/profiles/<slug>.html` dès que
   l'une des deux sources (française ou européenne) a produit un résultat —
   un candidat sans mandat français connu mais eurodéputé (ex. Jordan
   Bardella) obtient ainsi tout de même un profil minimal.

## 4. Consulter les profils dans le navigateur

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
- `mandat_europeen` (uniquement si le candidat a été eurodéputé⋅e) :
  identité au Parlement européen (`identifiant_pe`, `nom_complet`, `photo`) et
  `mandats_europeens`, la liste triée (plus récent en premier) de tous les
  mandats/fonctions occupés — mandat de député européen par législature,
  commissions permanentes/spéciales, délégations interparlementaires, groupes
  politiques européens et partis nationaux affiliés, groupes de travail,
  organes de direction — chacun avec son rôle (`role_label`, ex. « Membre »,
  « Président(e) »), ses dates de début/fin et un indicateur `actif`.
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
- Le mandat européen (`candidate_profile_ue.py`) ne couvre que les mandats,
  commissions, délégations et groupes politiques (via `hasMembership` de
  l'API MEPs) : il n'inclut pas encore les votes en plénière ni les rapports
  déposés au Parlement européen, bien que l'API expose des endpoints
  (`/meetings/{id}/vote-results`, `/documents`) qui permettraient de les
  ajouter dans une prochaine itération.
- La recherche d'un mandat européen se fait par égalité exacte du nom
  normalisé : un candidat dont le nom sur `data/candidats.json` diffère
  significativement de son libellé officiel au Parlement européen (ex. nom
  d'usage vs nom légal) ne serait pas trouvé.
