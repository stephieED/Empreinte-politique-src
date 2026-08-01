# EMPREINTE POLITIQUE

Génère des « CV politiques » structurés (mandats, responsabilités, votes,
dossiers législatifs, interventions en séance) pour les candidats à
l'élection présidentielle française de 2027, à partir des données ouvertes
de [NosDéputés.fr / NosSénateurs.fr](https://github.com/regardscitoyens)
(Regards Citoyens, licence ODbL), de l'
[open data de l'Assemblée nationale](https://data.assemblee-nationale.fr/)
pour le détail des votes, des données [Parltrack](https://parltrack.org) +
[Open Data Portal du Parlement européen](https://data.europarl.europa.eu/)
(licence CC BY 4.0) pour le volet mandat européen des candidats ayant été
eurodéputé⋅e⋅s, et de Wikipédia/Wikidata pour la veille des
candidatures.

**Principe directeur** : chaque fait affiché doit pouvoir remonter jusqu'à
sa source primaire (scrutin officiel, dossier législatif, révision Wikipédia
précise). Le projet ne porte aucun jugement de valeur.

## Arborescence

```
CV_CandidatFR/
├── src/                               # Scripts Python
│   ├── candidate_profile.py           # Collecte le profil brut d'UN parlementaire FR (AN/Sénat)
│   ├── candidate_profile_ue.py        # Construit le volet "mandat européen" d'UN candidat
│   ├── generate_all_profiles.py       # Batch : profils de TOUS les candidats de candidats.json
│   ├── group_profile.py               # Agrège des profils individuels en profil de groupe politique
│   ├── group_roster.py                # Récupère la composition réelle d'un groupe (NosDéputés/NosSénateurs)
│   ├── generate_group_profiles.py     # Batch : tous les groupes de data/groupes_reels.json (1 fetch/chambre)
│   ├── render_profile.py              # Convertit un profil JSON en page HTML statique
│   ├── schema_pivot.py                # Schéma pivot v1 — format commun à toutes les sources
│   ├── schema_groupe.py               # Schéma pivot v1 du profil de groupe (contrat de structure)
│   ├── normalize_nosdeputes.py        # Adaptateur NosDéputés/NosSénateurs → schéma pivot
│   ├── normalize_europarl.py          # Adaptateur Open Data Portal Parlement européen → schéma pivot
│   ├── mep_profile.py                 # Collecte et normalise les profils PE (Parltrack)
│   └── fetch_wikipedia_candidates.py  # Veille candidats via Wikipédia/Wikidata
├── data/
│   ├── candidats.json                 # Liste des candidats (nom, slug, parti, statut, sources)
│   ├── groupes_reels.json             # Liste validée des groupes réels à générer (voir §6)
│   ├── profiles/                      # Profils générés : <slug>.json, <slug>.html,
│   │                                  # <slug>.pivot.json (optionnel), parti-<slug>.json
│   └── groupes/                       # Profils de groupe parlementaire réel :
│                                      # groupe-<SIGLE>-<leg>.json (produits par generate_group_profiles.py)
├── web/
│   └── index.html                     # Page web dynamique (sélecteur de candidat)
├── docs/
│   └── nosdeputes_doc/                # Documentation de l'API NosDéputés/NosSénateurs (référence)
├── tests/
│   ├── test_candidate_profile.py
│   ├── test_candidate_profile_ue.py
│   ├── test_group_profile.py
│   ├── test_group_roster.py
│   ├── test_generate_group_profiles.py
│   ├── test_normalize_europarl.py
│   ├── test_normalize_nosdeputes.py
│   ├── test_schema_groupe.py
│   └── test_schema_pivot.py
└── README.md
```

- `.cache/` (créé automatiquement, ignoré par git) : cache local des archives
  de votes AN et des dumps Parltrack, pour éviter de re-télécharger à chaque exécution, 
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
python src/generate_all_profiles.py                           # tous les candidats
python src/generate_all_profiles.py --only jean-luc-melenchon # un seul candidat
python src/generate_all_profiles.py --max-pages 5             # recherche plus légère/rapide
python src/generate_all_profiles.py --skip-existing           # ne relance pas ce qui est déjà généré
python src/generate_all_profiles.py --pivot                   # aussi écrire <slug>.pivot.json
python src/generate_all_profiles.py --skip-ue                 # ne pas interroger l'API du Parlement européen
python src/generate_all_profiles.py --workers 8               # augmenter le parallélisme (défaut: 4)
python src/generate_all_profiles.py --out-dir /tmp/profiles   # dossier de sortie alternatif
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

Avec `--pivot`, un fichier `data/profiles/<slug>.pivot.json` est également
généré au format schéma pivot v1 (voir section « Schéma pivot »).

### Parallélisation à deux niveaux

Le script exploite deux niveaux de parallélisme pour réduire le temps de
génération :

- **Niveau 1** (intra-candidat) : pour chaque candidat, les appels vers
  NosDéputés.fr et vers l'Open Data Portal du Parlement européen sont
  lancés simultanément dans deux threads dédiés (deux API distinctes, aucun
  état partagé entre elles).
- **Niveau 2** (inter-candidats) : plusieurs candidats sont traités en
  parallèle grâce à un pool de threads dont la taille est contrôlée par
  `--workers` (défaut : 4). Les caches disque partagés sont protégés par des
  verrous définis respectivement dans `candidate_profile.py` et
  `candidate_profile_ue.py`.

Réduire `--workers` (ex. `--workers 2`) si les API publiques commencent à
renvoyer des erreurs 429 (trop de requêtes).

## 4. Générer le profil d'un député européen (Parltrack)

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

## 5. Générer le profil d'un parti / liste de candidats

`parti_profile.py` construit un **profil de parti** à partir des labels de
parti déclarés dans `data/candidats.json` et des pivots individuels disponibles
sur disque. Ce profil est un objet éditorial : il agrège des candidats
déclarés par label de parti, mais ne prétend pas représenter un groupe
parlementaire réel ni sa cohésion de vote.

```bash
python src/parti_profile.py \
    --candidats data/candidats.json \
    --profiles-dir data/profiles \
    --out-dir data/profiles
```

## 6. Générer le profil d'un groupe politique

`group_profile.py` agrège plusieurs profils individuels (format brut
NosDéputés ou pivot v1) en un **profil de groupe parlementaire** conforme au
schéma de groupe v1 (`schema_groupe.py`). Contrairement à un profil de parti,
il représente une composition parlementaire réelle, avec des membres, une
période et des métriques de cohésion et d'amendements lorsqu'elles sont
couvrent par les données disponibles.

```bash
python src/group_profile.py \
    --groupe-id "AN:SOC" \
    --groupe-sigle SOC \
    --groupe-nom "Socialistes et apparentés" \
    --chambre AN \
    --legislature 16 \
    data/profiles/jerome-guedj.json \
    data/profiles/boris-vallaud.json \
    --out data/groupes/groupe-SOC-16.json
```

Les profils en entrée peuvent être indifféremment au format brut NosDéputés
(produit par `candidate_profile.py`) ou au format pivot v1 (produit par
`generate_all_profiles.py --pivot`) : le script détecte et normalise
automatiquement.

Avec `--from-roster` (composition réelle récupérée en direct auprès de
NosDéputés.fr/NosSénateurs.fr, voir `group_roster.py`), `--out FICHIER`
**écrase entièrement** le fichier existant à chaque exécution par défaut.
L'option `--merge-existing` réintègre les membres qui figuraient dans
`FICHIER` lors d'une exécution précédente mais sont absents du roster
récupéré cette fois-ci (protège contre un échec partiel de l'API live) ;
un avertissement `fusion_avec_existant` est alors ajouté à `meta.warnings`.
Voir les deux commandes proposées (l'une commentée) dans
`.github/workflows/generate-data.yml`.

### Générer plusieurs groupes réels en un seul run

`group_profile.py --from-roster` fait un appel réseau par exécution : générer
les 7 groupes réels validés (5 AN + 2 Sénat) en 7 invocations séparées
refetch donc 5 fois le même roster AN et 2 fois le même roster Sénat, alors
que NosDéputés.fr/NosSénateurs.fr n'exposent qu'un seul point d'accès « liste
complète de la chambre » (pas d'endpoint par groupe).

`generate_group_profiles.py` évite cette redondance : il lit la liste des
groupes à générer depuis un fichier de config JSON (`data/groupes_reels.json`,
liste validée manuellement — voir plus haut) et ne récupère le roster complet
qu'**une seule fois par (chambre, législature)** distincte, réutilisé ensuite
pour filtrer localement chaque sigle de groupe.

```bash
python src/generate_group_profiles.py \
    --config data/groupes_reels.json \
    --profiles-dir data/profiles \
    --out-dir data/groupes \
    --validate
```

`--merge-existing` s'applique alors à tous les groupes de la config (même
sémantique qu'avec `group_profile.py`). C'est ce script, et non plus la
boucle bash historique, qu'appelle `.github/workflows/generate-data.yml`.

Le profil de groupe produit contient :

- `membres` : liste des membres avec leurs dates d'entrée/sortie dans le
  groupe (dérivées des mandats électifs des profils individuels).
- `effectif` : nombre de membres actifs au moment du calcul.
- `cohesion_votes` : par scrutin, position majoritaire + taux de
  participation et de cohérence du groupe (membres alignés / membres
  éligibles à la date du scrutin). Distingue absents, non-votants et excusés.
- `tags_thematiques_agreges` : agrégation des `tags_thematiques` individuels,
  triés par poids décroissant (`nb_membres_porteurs / len(membres)`).
- `amendements_agreges` : comptes bruts (adoptés/rejetés/irrecevables/
  retirés ou tombés) et taux d'adoption, agrégés sur les `amendements[]` des
  profils membres. Le total mélange tous les types de déposants — **ne pas**
  l'utiliser comme comparateur direct du taux d'un⋅e élu⋅e, car les
  amendements gouvernementaux/rapporteur sont adoptés quasi systématiquement
  par construction. `par_type_deposant["depute"]` isole les amendements
  déposés à titre individuel, seule catégorie comparable à un⋅e élu⋅e ;
  `par_type_deposant["inconnu"]` regroupe les amendements sans
  `type_deposant` renseigné (jamais rattachés à "depute" par défaut).
- `sources` et `meta` : traçabilité des profils agrégés, horodatage, licence.

L'option `--rapport-interne FICHIER` écrit séparément un rapport de
**contrôle interne** (écarts de cohésion/participation individuels par
rapport à la moyenne du groupe) : cette donnée n'est volontairement pas
intégrée au profil de groupe public tant qu'elle n'a pas été validée comme
sortie destinée aux lecteurs.

## 6. Veille des candidats via Wikipédia / Wikidata

```bash
python src/fetch_wikipedia_candidates.py         # toutes les sources
python src/fetch_wikipedia_candidates.py --source wikipedia
python src/fetch_wikipedia_candidates.py --source wikidata
python src/fetch_wikipedia_candidates.py --json  # sortie machine-readable
```

**Ce script ne modifie jamais `candidats.json` automatiquement** : il produit
un diff lisible (nouveaux candidats détectés, candidats locaux absents en ligne)
pour validation manuelle avant intégration.

## 7. Consulter les profils dans le navigateur

Servir le dépôt via un serveur HTTP local (nécessaire : `index.html` charge
les JSON via `fetch()`, ce qui échoue en ouvrant le fichier directement avec
`file://`) :

```bash
python -m http.server 8000
```

Puis ouvrir <http://localhost:8000/web/> dans un navigateur. Cette page sert
de laboratoire visuel et donne accès aux variantes conservées :

- `web/v1/`, `web/v2/` et `web/v3/` : les trois premiers designs. La V3,
  « Empreinte politique — En clair », propose des vues par candidat et par
  parti ;
- `web/atlas-augmente/` : l'Atlas alimenté par les profils réels ;
- `web/scene-cinetique/` et `web/interface-essentielle/` : les études ayant
  servi au résumé express intégré à la V3 et à l'Atlas ;
- `web/matiere-politique/`, `web/revue-civique/` et `web/moodboard/` : les
  études intermédiaires.

Les trois premiers designs chargent les profils dynamiquement depuis
`data/profiles/<slug>.json`. La V3 complète le profil brut avec
`data/profiles/<slug>.pivot.json` pour les faits sensibles : rôle et stade
des textes portés, amendements, type de scrutin, 49.3, motions de censure,
position sourcée dans l'hémicycle et incompatibilités ministérielles. Un
pivot absent ou incomplet n'est jamais remplacé par une inférence.

La page publique `web/v3/methodologie.html` documente les règles éditoriales
de la V3 : aucun taux individuel de présence ou d'absence, issues
d'amendements en comptes bruts, ratios de groupe avec numérateur et
dénominateur, distinction 49.3/censure et univers des votes sur textes
entiers (tous les scrutins publics, ordinaires et solennels).

La vue « Partis » de la V3 charge les agrégats `data/profiles/parti-*.json`
(profils de parti/liste de candidats, voir §5). Ces fiches décrivent
uniquement les profils candidats présents dans chaque agrégat : la
couverture affichée ne représente pas l'ensemble des membres ou élus du
parti. Les profils de groupe parlementaire réel (`data/groupes/groupe-*.json`,
voir §6) ne sont pas encore consommés par une vue web.

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
  "amendements":   [ ... ],
  "interventions": [ ... ],
  "tags_thematiques": ["budget", "fiscalité"],
  "meta": { "schema_version": "1", "genere_le": "...", "licence_donnees": "...", "warnings": [] }
}
```

Chaque adaptateur source (`normalize_nosdeputes`, `normalize_parltrack` dans
`mep_profile.py`) traduit les données brutes vers ce schéma commun sans
logique d'affichage.

### Champs institutionnels sensibles (schéma pivot v1)

- `mandats[].position_dans_hemicycle` (`"majorite" | "opposition"`) est le
  champ éditorial le plus sensible du schéma : `validate_profil()` refuse ce
  champ sans `mandats[].source_url` pointant vers une source primaire
  vérifiable (déclaration officielle du groupe, liste du socle de soutien au
  gouvernement, JO). Attaché au mandat plutôt qu'à la personne, car ce statut
  peut changer d'une législature à l'autre.
- `mandats[].suspendu_pour_fonction_gouvernementale` signale une période
  d'incompatibilité ministérielle (art. 23 de la Constitution), pour ne
  jamais confondre un mandat suspendu avec un désengagement.
- `votes[].type_vote` (`"vote_texte" | "motion_censure"`) et
  `votes[].texte_lie_id` : une motion de censure liée à un engagement de
  responsabilité (art. 49.3, `sort = "adopte_sans_vote_49_3"`) est toujours
  un scrutin séparé, jamais fusionnée avec une position sur le texte visé.
- `amendements[].sort == "irrecevable"` exige
  `base_juridique_irrecevabilite` (`"art. 40" | "art. 45"`) : l'irrecevabilité
  est un rejet de procédure, distinct d'un rejet sur le fond.
- `amendements[].type_deposant` (`"gouvernement" | "commission_rapporteur" |
  "depute"`) et `co_signataires[]` permettent de ne pas mélanger des
  amendements de nature institutionnelle très différente (voir
  `amendements_agreges.par_type_deposant` côté profil de groupe).
- `textes_portes[].type_rapport` utilise une nomenclature officielle
  (`rapporteur_fond`, `rapporteur_avis`, `rapporteur_special_budget`,
  `mission_information`) et `.stade_procedural` distingue un texte déposé
  d'un texte réellement débattu — descriptifs uniquement, jamais une
  catégorie de valorisation éditoriale.

Collecte encore à implémenter : `candidate_profile.py`/`normalize_nosdeputes.py`
ne peuplent pas encore ces champs depuis les sources primaires ; ils sont
aujourd'hui définis au niveau du schéma et de sa validation uniquement.

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
