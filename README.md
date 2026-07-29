# CV_CandidatFR

Génère des « CV politiques » structurés (mandats, responsabilités, votes,
dossiers législatifs, interventions en séance) pour les candidats à
l'élection présidentielle française de 2027, à partir des données ouvertes
de [NosDéputés.fr / NosSénateurs.fr](https://github.com/regardscitoyens)
(Regards Citoyens, licence ODbL), de l'
[open data de l'Assemblée nationale](https://data.assemblee-nationale.fr/)
pour le détail des votes, des données [Parltrack](https://parltrack.org)
pour les députés européens, et de Wikipédia/Wikidata pour la veille des
candidatures.

**Principe directeur** : chaque fait affiché doit pouvoir remonter jusqu'à
sa source primaire (scrutin officiel, dossier législatif, révision Wikipédia
précise). Le projet ne porte aucun jugement de valeur.

## Arborescence

```
CV_CandidatFR/
├── src/                               # Scripts Python
│   ├── candidate_profile.py           # Collecte le profil brut d'UN parlementaire FR (AN/Sénat)
│   ├── generate_all_profiles.py       # Batch : profils de TOUS les candidats de candidats.json
│   ├── render_profile.py              # Convertit un profil JSON en page HTML statique
│   ├── schema_pivot.py                # Schéma pivot v1 — format commun à toutes les sources
│   ├── normalize_nosdeputes.py        # Adaptateur NosDéputés/NosSénateurs → schéma pivot
│   ├── mep_profile.py                 # Collecte et normalise les profils PE (Parltrack)
│   └── fetch_wikipedia_candidates.py  # Veille candidats via Wikipédia/Wikidata
├── data/
│   ├── candidats.json                 # Liste des candidats (nom, slug, parti, statut, sources)
│   └── profiles/                      # Profils générés : <slug>.json, <slug>.html,
│                                      # et optionnellement <slug>.pivot.json
├── web/
│   └── index.html                     # Page web dynamique (sélecteur de candidat)
├── docs/
│   └── nosdeputes_doc/                # Documentation de l'API NosDéputés/NosSénateurs (référence)
├── tests/
│   ├── test_candidate_profile.py
│   ├── test_schema_pivot.py
│   └── test_normalize_nosdeputes.py
└── README.md
```

- `.cache/` (créé automatiquement, ignoré par git) : cache local des archives
  de votes AN et des dumps Parltrack, pour éviter de re-télécharger à chaque exécution.

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install requests beautifulsoup4 pytest
```

Toutes les commandes ci-dessous sont à exécuter **depuis la racine du
dépôt**, avec l'environnement virtuel activé.

## 1. Générer le profil d'un seul candidat (AN / Sénat)

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
python src/generate_all_profiles.py --pivot                   # aussi écrire <slug>.pivot.json
```

Ce script lit `data/candidats.json`, ignore proprement les candidats sans
`slug` (non référencés sur NosDéputés/NosSénateurs), essaie automatiquement
`deputes` puis `senateurs`, et écrit `data/profiles/<slug>.json` +
`data/profiles/<slug>.html` pour chaque candidat traité.

Avec `--pivot`, un fichier `data/profiles/<slug>.pivot.json` est également
généré au format schéma pivot v1 (voir section « Schéma pivot »).

## 3. Générer le profil d'un député européen (Parltrack)

```bash
python src/mep_profile.py --name "Manon Aubry"
python src/mep_profile.py --ep-id 197451
python src/mep_profile.py --list              # liste les MEPs FR dans le dump
python src/mep_profile.py --show-cache-date   # vérifie la fraîcheur du dump local
```

Le premier appel télécharge les dumps Parltrack (~plusieurs centaines de Mo,
mis en cache sous `.cache/parltrack/`). **Vérifier la fraîcheur du dump avant
usage** : `--show-cache-date` affiche l'âge du cache ; la date officielle est
visible sur https://parltrack.org/dumps.

## 4. Veille des candidats via Wikipédia / Wikidata

```bash
python src/fetch_wikipedia_candidates.py         # toutes les sources
python src/fetch_wikipedia_candidates.py --source wikipedia
python src/fetch_wikipedia_candidates.py --source wikidata
python src/fetch_wikipedia_candidates.py --json  # sortie machine-readable
```

**Ce script ne modifie jamais `candidats.json` automatiquement** : il produit
un diff lisible (nouveaux candidats détectés, candidats locaux absents en ligne)
pour validation manuelle avant intégration.

## 5. Consulter les profils dans le navigateur

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

## Contenu d'un profil (format brut NosDéputés)

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
- `meta.synchro_sources` : horodatage ISO-8601 de la dernière synchro réussie
  par source (`nosdeputes`, `assemblee_nationale`). `null` = source non
  contactée ou indisponible lors de la dernière génération.

## Schéma pivot v1

Le format brut NosDéputés est spécifique à cette source. Pour unifier la
représentation entre AN, Sénat et Parlement européen (et préparer les vues
thématiques), un **schéma pivot v1** est défini dans `src/schema_pivot.py`.

Avec `--pivot`, `generate_all_profiles.py` écrit un `<slug>.pivot.json`
converti par `normalize_nosdeputes.py`. Le format pivot contient :

```json
{
  "schema_version": "1",
  "id": "nosdeputes:jean-luc-melenchon",
  "nom": "Jean-Luc Mélenchon",
  "chambre": "AN",
  "parti": null,
  "groupe": "La France Insoumise",
  "sources": [
    {"type": "nosdeputes", "url": "...", "synchro_le": "2026-07-29T..."},
    {"type": "assemblee_nationale", "url": "...", "synchro_le": "2026-07-29T..."}
  ],
  "mandats":       [ ... ],
  "votes":         [ ... ],
  "textes_portes": [ ... ],
  "interventions": [ ... ],
  "tags_thematiques": ["budget", "fiscalité"],
  "meta": { "schema_version": "1", "genere_le": "...", "licence_donnees": "...", "warnings": [] }
}
```

Chaque adaptateur source (`normalize_nosdeputes`, `normalize_parltrack` dans
`mep_profile.py`) traduit les données brutes vers ce schéma commun sans
logique d'affichage.

## Taxonomie des sources

| Source | Type | Cadence de mise à jour | Licence | Chambre(s) |
|---|---|---|---|---|
| NosDéputés.fr | API JSON/XML | Quasi temps réel (législature courante) | ODbL | AN |
| Archives NosDéputés.fr | API JSON/XML | Figées (législatures closes) | ODbL | AN |
| NosSénateurs.fr (archive) | API JSON/XML | Figée | ODbL | Sénat |
| data.assemblee-nationale.fr | Dumps ZIP | Quotidien | Licence ouverte AN | AN (votes nominatifs) |
| Parltrack | Dumps LZMA | Hebdomadaire (environ) | CC0/ODbL | PE |
| Wikipédia FR | API MediaWiki REST | Immédiat | CC BY-SA 4.0 | Veille candidatures |
| Wikidata | SPARQL | Immédiat | CC0 | Veille candidatures |

## Tests

```bash
pytest -q
```

## Limites de couverture

- **Votes AN** : récupérés via l'open data officiel pour les **députés** des
  législatures 14, 15 et 16. La législature 17 (juillet 2024 à aujourd'hui)
  est incluse dans l'infrastructure mais la couverture dépend de la
  disponibilité des dumps sur data.assemblee-nationale.fr.
- **Votes Sénat** : pas d'équivalent officiel open data intégré ; section
  `votes` souvent vide pour les sénateurs.
- **Interventions** : retrouvées par recherche plein texte du nom du candidat.
  Un candidat peu cité ou avec un nom ambigu peut avoir une couverture partielle.
- **Maires** : aucun module dédié (pas de source structurée généralisable).
  Les maires candidats présidentiables sont traités uniquement via leurs
  mandats parlementaires, si disponibles.
- **Biais de couverture** : les anciens parlementaires ont plus de données que
  les ministres ou maires sans mandat parlementaire. Ne pas interpréter un
  profil peu rempli comme une inactivité.
- **Docs API** : `docs/nosdeputes_doc/` est fournie à titre de référence ;
  certains endpoints (ex. `/votes`) sont aujourd'hui hors service.

## Fraîcheur des données

Chaque profil généré expose `meta.synchro_sources` (horodatage par source) et
les profils pivot exposent `sources[].synchro_le`. Les dumps Parltrack ont leur
propre rythme de publication ; utiliser `python src/mep_profile.py --show-cache-date`
pour vérifier l'âge du cache local avant toute utilisation publique.

## Neutralité éditoriale

Ce projet agrège des faits bruts avec leurs sources primaires. Il ne produit
aucun classement, aucun score de « bonne » ou « mauvaise » performance, et
aucune évaluation éditoriale des positions politiques. Les seules décisions
éditoriales assumées et documentées sont :

1. **Choix des sources** : les sources listées dans le tableau ci-dessus ont
   été sélectionnées pour leur caractère officiel ou structuré et leur licence
   ouverte. Toute source ajoutée doit être documentée ici.
2. **Taxonomie thématique (Phase 4, à venir)** : le découpage en thèmes sera
   documenté explicitement avec la justification de chaque catégorie.
   Les `tags_thematiques` actuels sont des mots-clés bruts non harmonisés.

## Phase 4 — Taxonomie thématique (à venir)

Les `tags_thematiques[]` dans le schéma pivot contiennent des mots-clés bruts
issus des interventions. La Phase 4 harmonisera ces tags en un ensemble de
thèmes stables (8 à 12 catégories, ex. *santé, environnement, économie,
sécurité, éducation, international, institutions, social*).

**Décision éditoriale à documenter ici** : le découpage thématique sera fixé
par une table de correspondance explicite (`tags_thematiques[]` bruts →
thème normalisé), versionnée dans ce dépôt. Toute modification du découpage
sera tracée dans le changelog.

