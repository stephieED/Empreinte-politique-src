# UI finale — Empreinte politique

Interface de production de l'explorateur **Empreinte politique** (React 19 + Vite 8).

Elle consomme exclusivement les fichiers du dossier `pivot_data/` produits par le pipeline Python, et ne contient aucune logique d'extraction ni de normalisation.

---

## Stack

| Rôle | Outil |
|---|---|
| Framework UI | React 19 |
| Bundler / dev server | Vite 8 |
| Routing | React Router v7 (SPA, BrowserRouter) |
| Linter | Oxlint |
| Typage | JSDoc uniquement (pas de TypeScript) |

---

## Lancer l'application

```bash
# Depuis la racine du dépôt
cd web/UI_finale
npm install

# Dev (synchronise les données puis lance Vite)
npm run dev

# Build de production
npm run build

# Prévisualiser le build
npm run preview
```

Le serveur de développement écoute sur le port `5173` par défaut (ou `$PORT` si défini).

---

## Synchronisation des données

Avant chaque démarrage (`dev`) ou build, le script `scripts/sync-data.mjs` est exécuté automatiquement. Il :

1. Copie `raw_data/candidats.json` → `public/data/candidats.json`
2. Copie les profils `pivot_data/profiles/*.pivot.json` → `public/data/profiles/`
3. Copie les groupes `pivot_data/groupes/groupe-*.json` → `public/data/groupes/`
4. Génère `public/data/manifest.json` : index central `{ candidates[], groupes[] }` avec l'appartenance de chaque candidat à son groupe

Le dossier `public/data/` n'est **pas versionné** ; il est entièrement généré à la volée.

---

## Structure de `src/`

```
src/
├── main.jsx                  # Point d'entrée React (StrictMode + BrowserRouter)
├── App.jsx                   # Déclaration des routes
├── index.css                 # Variables CSS globales (couleurs, typographie)
├── components/               # Composants réutilisables
│   ├── ExplorerLayout        # Coque principale : sidebar gauche + outlet central
│   ├── Brand                 # En-tête / logo
│   ├── CandidatesBar         # Liste horizontale des candidats (filtrée par groupe)
│   ├── GroupsBar             # Liste horizontale des groupes (toggle de filtre)
│   ├── ScrollRow             # Conteneur générique à défilement horizontal drag-able
│   ├── CandidateProfile      # Fiche candidat (KPIs, onglets Votes / Textes / Données)
│   ├── GroupProfile          # Fiche groupe (effectif, cohésion, amendements)
│   └── NotFoundProfile       # Fallback 404
├── pages/                    # Pages routées (chargement async → composant)
│   ├── CandidateProfilePage  # Résout l'id URL → CandidateProfile
│   └── GroupProfilePage      # Résout l'id URL → GroupProfile
├── context/
│   └── GroupFilterContext    # État global : groupe sélectionné (filtre candidats)
├── data/
│   ├── index.js              # API de fetch : manifest, profils candidats, profils groupes
│   └── pivotAdapter.js       # Transformation pivot JSON → objets consommables par l'UI
├── hooks/
│   ├── useAsyncData.js       # Chargement async générique { data, loading, error }
│   └── useDragScroll.js      # Drag-scroll horizontal sur les barres latérales
├── utils/
│   └── text.js               # Helpers texte (initiales, etc.)
└── styles/
    └── shell.css             # CSS de la coque applicative
```

---

## Flux de données

```
manifest.json + *.pivot.json + groupe-*.json   (public/data/)
        │
        ▼
data/index.js         — fetch + cache manifest, expose getCandidateProfile() / getGroupProfile()
        │
        ▼
data/pivotAdapter.js  — buildCandidateView() / buildGroupView()
        │             (calcul KPIs, tri votes, filtres textes, classification thématique)
        ▼
useAsyncData()        — { data, loading, error }
        │
        ▼
CandidateProfile / GroupProfile   — affichage
```

La couche `pivotAdapter.js` est le seul endroit où la logique métier de présentation réside (ex. : calcul d'ancienneté, classification hémicycle majorité/opposition, filtre des textes par stade procédural).

---

## Routes

| URL | Composant | Description |
|---|---|---|
| `/` | → redirect | Redirige vers le premier candidat du manifest |
| `/candidats/:candidateId` | `CandidateProfilePage` | Fiche candidat |
| `/groupes/:groupId` | `GroupProfilePage` | Fiche groupe |
| `/groupes` | → redirect | Redirige vers le premier groupe |

---

## Règles éditoriales respectées dans l'UI

Les règles de `AGENTS.md §2` s'appliquent également au code d'affichage :

- Aucun taux de présence individuel n'est affiché (`pivotAdapter.js` n'en expose pas).
- Les 49.3 sont étiquetés comme fait procédural, sans position de vote.
- Les ratios de groupe ne s'affichent qu'avec numérateur + dénominateur + couverture suffisante.
- Les tags thématiques sont des aides à la lecture, pas des positions déclarées.

---

## Linter

```bash
npm run lint
```

Oxlint (Rust-based). Pas de configuration TypeScript — JSDoc uniquement.
