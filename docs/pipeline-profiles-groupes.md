# Pipeline groupes parlementaires et profils candidats

Les données des groupes parlementaires sont construites en deux étages:

- construction des profils candidats (collecte + normalisation pivot),
- agrégation de ces profils en profils de groupes parlementaires réels.

## Schéma de flux complet

```mermaid
graph TD
    %% =========================
    %% SOURCES
    %% =========================
    S1[NosDeputes.fr / NosSenateurs.fr\nAPI elus, votes, interventions]
    S2[data.assemblee-nationale.fr\nScrutins, amendements, dossiers]
    S2b[data.assemblee-nationale.fr\nComptes rendus Syceron - deputes]
    S3[Parltrack dumps\nMEPs, dossiers, amendments]
    S4[Europarl Open Data Portal\nReferentiel officiel MEP]
    S5[Wikipedia / Wikidata\nMonitoring candidatures]

    %% =========================
    %% CONSTRUCTION PROFILS CANDIDATS
    %% =========================
    S1 --> C1[src/candidate_profile.py\nExtraction profil FR]
    S2 --> C1
    S2b --> C1
    S3 --> C2[src/candidate_profile_ue.py + src/mep_profile.py\nExtraction mandat europeen]
    S4 --> C2
    S5 --> C3[src/fetch_wikipedia_candidates.py\nSuivi candidats]

    C1 --> R1[raw_data/profiles/<slug>.json]
    C2 --> R1
    C3 --> R2[raw_data/candidats.json\nMise a jour editoriale manuelle]

    R1 --> N1[src/normalize_nosdeputes.py]
    R1 --> N2[src/normalize_europarl.py]
    N1 --> P1[pivot_data/profiles/<slug>.pivot.json]
    N2 --> P1

    %% =========================
    %% CONSTRUCTION PROFILS GROUPES
    %% =========================
    G0[raw_data/groupes_reels.json\nListe des groupes a produire] --> B1[src/generate_group_profiles.py]
    S1 --> B2[src/group_roster.py\nRoster reel par chambre/legislature]
    B2 --> B1
    P1 --> B3[src/group_profile.py\nAggregation locale du groupe]
    B1 --> B3
    B3 --> O1[pivot_data/groupes/groupe-*.json]

    %% =========================
    %% VALIDATION / QUALITE
    %% =========================
    O1 --> V1[src/schema_groupe.py\nValidation schema]
    O1 --> Q1[src/check_quality_gate.py\nQuality gate CI]
    O1 --> A1[src/audit_groupe_dataset.py\nAudit qualite interne - CLI]
```

## Variante: flux prolongé jusqu'aux vues web (UI_finale)

Cette variante explicite la consommation des artefacts JSON par l'interface
`web/UI_finale` (React 19 + Vite, onglets `Candidats` et `Groupes`).

```mermaid
graph TD
        %% =========================
        %% SOURCES ET EXTRACTION
        %% =========================
        S1[NosDeputes / NosSenateurs] --> C1[candidate_profile.py]
        S2[Open Data Assemblee nationale] --> C1
        S2b[Open Data AN - Syceron\ncomptes rendus deputes] --> C1
        S3[Europarl API + ParlTrack] --> C2[candidate_profile_ue.py / mep_profile.py]
        S4[Wikipedia / Wikidata] --> C3[fetch_wikipedia_candidates.py]

        %% =========================
        %% ARTEFACTS DONNEES
        %% =========================
        C1 --> R1[raw_data/profiles slash slug.json]
        C2 --> R1
        C3 --> R2[raw_data/candidats.json]

        R1 --> N1[normalize_nosdeputes.py]
        R1 --> N2[normalize_europarl.py]
        N1 --> P1[pivot_data/profiles slash slug.pivot.json]
        N2 --> P1

        R2 --> G0[generate_group_profiles.py]
        P1 --> G0
        G0 --> G1[group_profile.py + group_roster.py]
        G1 --> PG[pivot_data/groupes slash groupe-*.json]

        %% =========================
        %% SYNCHRONISATION FRONT
        %% =========================
        R2 --> SYNC[web/UI_finale/scripts/sync-data.mjs]
        P1 --> SYNC
        PG --> SYNC

        SYNC --> MAN[public/data/manifest.json\ncandidats + groupes + groupIds]
        SYNC --> PP[public/data/profiles slash slug.pivot.json]
        SYNC --> PGP[public/data/groupes slash groupe-*.json]

        %% =========================
        %% COUCHE DONNEES REACT
        %% =========================
        MAN --> IDX[data/index.js\ngetCandidateProfile / getGroupProfile]
        PP --> IDX
        PGP --> IDX
        IDX --> ADP[data/pivotAdapter.js\nbuildCandidateView / buildGroupView]

        %% =========================
        %% VUES REACT
        %% =========================
        ADP --> VC[Vue Candidats\n/candidats/:id\nKPIs, Votes, Textes]
        ADP --> VG[Vue Groupes\n/groupes/:id\ncohesion, effectifs, themes, amendements]
```

Repères d'implémentation UI_finale :

- `web/UI_finale/scripts/sync-data.mjs` copie les artefacts pivot vers
    `public/data/` et génère `manifest.json` (index des candidats et groupes
    disponibles, avec `groupIds[]` pour le filtrage côté client).
- `web/UI_finale/src/data/index.js` expose l'API de fetch (`getCandidateProfile`,
    `getGroupProfile`, `getCandidatesList`, `getGroupsList`).
- `web/UI_finale/src/data/pivotAdapter.js` transforme le JSON pivot en objets
    prêts à l'affichage (calcul KPIs, tri votes, classification thématique,
    classification hémicycle majorité/opposition).
- Les profils de groupes affichés sont ceux copiés depuis `pivot_data/groupes`
    par `sync-data.mjs`.

## Lecture rapide

1. Les profils candidats sont d'abord produits depuis les sources ouvertes,
   puis normalises en format pivot dans `pivot_data/profiles`.
2. La pipeline groupes combine roster reel et profils pivot individuels pour
   construire `pivot_data/groupes`.
3. Chaque profil groupe est valide via le schema puis controle par le quality gate.

## Points importants

- `group_profile.py` n'interroge pas le reseau: il agrege des profils locaux.
- Le fetch roster est mutualise par `(chambre, legislature)` dans
  `generate_group_profiles.py` pour eviter les appels redondants.
- La logique groupe parlementaire reel est distincte de l'agregation editoriale
  par parti (`parti_profile.py`).


## Détails: pipeline profils candidats

Comment ça marche concrètement

1. Source de vérité éditoriale
     - `raw_data/candidats.json` contient la liste des candidats suivis
         (`nom`, `slug`, `parti`, `statut`, `source`).
     - Ce fichier reste éditorial: `fetch_wikipedia_candidates.py` propose des
         écarts, mais ne modifie jamais automatiquement `candidats.json`.

2. Collecte du profil FR (Assemblée/Sénat)
     - `candidate_profile.py` collecte les faits bruts depuis NosDéputés /
         NosSénateurs (identité, mandats, interventions).
     - Pour les votes/amendements/questions, la pipeline complète avec les
         jeux de données officiels AN Open Data quand disponibles.
     - Pour les interventions des députés, les comptes rendus de séance
         Syceron (`syceron_debates.py` / `parse_syceron.py`, législatures 15-17)
         sont la source primaire ; le scraping NosDéputés reste un fallback si
         Syceron ne retourne rien pour l'acteurRef du candidat. Voir
         `docs/an_opendata.md` (section Syceron).
     - Sortie: `raw_data/profiles/<slug>.json`.

3. Collecte du volet européen
     - `candidate_profile_ue.py` cherche un mandat PE par correspondance de nom
         (normalisée), puis récupère les mandats `hasMembership` via l'API officielle
         du Parlement européen.
     - `mep_profile.py` et les dumps ParlTrack peuvent enrichir la dimension UE
         selon le mode d'exécution.
     - Le volet UE est fusionné dans le même profil brut sous
         `mandat_europeen`.

4. Batch multi-candidats
     - `generate_all_profiles.py` pilote la génération globale.
     - Niveau 1 de parallélisme: pour un candidat, collecte FR et UE en parallèle.
     - Niveau 2 de parallélisme: plusieurs candidats traités en parallèle
         (`--workers`).
     - En cas d'interruption, reprise possible via checkpoint (`--resume`).

5. Fusion additive (stabilité des données)
     - Par défaut, la régénération ne remplace pas brutalement l'existant:
         `merge_profile.py` fusionne le nouveau et l'ancien pour éviter la perte
         de données lors d'un aléa API temporaire.
     - `--no-merge` force un écrasement complet.

6. Normalisation vers le pivot commun
     - `normalize_nosdeputes.py` convertit le profil brut FR vers
         `schema_pivot.py`.
     - `normalize_europarl.py` convertit le volet UE vers le même schéma.
     - Sortie pivot: `pivot_data/profiles/<slug>.pivot.json` (option `--pivot`
         dans `generate_all_profiles.py`).

7. Validation implicite pour la suite
     - Ces pivots servent d'entrée unique aux agrégations groupes/partis.
     - Les données manquantes restent `null` (jamais des zéros par défaut),
         pour respecter les invariants éditoriaux.

Commandes usuelles

- Générer tous les profils bruts candidats:
    `python src/generate_all_profiles.py`
- Générer aussi les pivots:
    `python src/generate_all_profiles.py --pivot`
- Limiter à un candidat:
    `python src/generate_all_profiles.py --only jean-luc-melenchon --pivot`
- Reprendre après interruption:
    `python src/generate_all_profiles.py --resume --pivot`

Entrées / sorties de la pipeline candidats

- Entrées principales:
    - `raw_data/candidats.json`
    - APIs NosDéputés / NosSénateurs
    - Open Data AN
    - API Open Data Parlement européen (+ éventuel enrichissement ParlTrack)
- Sorties:
    - `raw_data/profiles/<slug>.json` (profil brut fusionné)
    - `pivot_data/profiles/<slug>.pivot.json` (profil normalisé pivot v1)


## Détails: pipeline groupes parlementaires
Comment ça marche concrètement

La liste des groupes à produire est définie dans groupes_reels.json.
Le batch generate_group_profiles.py fait un seul fetch réseau par couple (chambre, législature) (optimisation clé).
Ce fetch passe par group_roster.py:
  - récupération de la liste complète députés/sénateurs,
  - filtrage côté client par groupe_sigle (car endpoint groupe direct peu fiable).

Pour chaque membre trouvé, le script charge son profil pivot local dans profiles.
group_profile.py agrège les faits:
  - membres et périodes,
  - cohésion de vote par scrutin,
  - tags thématiques agrégés,
  - amendements agrégés (avec ventilation par type de déposant).
Le JSON final est contraint par schema_groupe.py, puis contrôlé par check_quality_gate.py.

Points importants de la pipeline

  - La logique « groupe parlementaire réel » est distincte de la logique « parti éditorial ».
  - Les partis sont générés séparément (pas la même finalité).
  - group_profile.py n’interroge pas le réseau: il agrège des données déjà présentes localement.
  - En mode batch, la couverture roster/profils disponibles est tracée (pour éviter de confondre effectif réel et effectif effectivement agrégé).
  - Le quality gate peut faire échouer le run si structure invalide ou incidents réseau au-delà du seuil.

### Audit du jeu de données groupes

`src/audit_groupe_dataset.py` est un outil de qualité interne, distinct du
quality gate CI : il scanne `pivot_data/groupes` (par défaut) et produit un
rapport JSON/Markdown (volumétrie, complétude, cohérence, fraîcheur des
sources, warnings agrégés), sur le même modèle que `audit_pivot_dataset.py`
pour `pivot_data/profiles`. Aucun score ni classement — voir `README.md`
§11 et `docs/examples/audit_groupe_report_sample.md` pour un exemple de
rapport.

### Pipeline d'audit combiné (outil manuel)

`src/audit_pipeline.py` est un point d'entrée **manuel** qui exécute les deux
audits ci-dessus (`audit_pivot_dataset.py` et `audit_groupe_dataset.py`) en
appelant directement leurs fonctions (pas de sous-processus) et compile une
section « vue d'ensemble » en plus des deux rapports détaillés : totaux
profils/groupes audités, erreurs de lecture agrégées, warnings agrégés tous
documents confondus. Pure composition des rapports déjà produits par les deux
modules `audit_*` — aucune nouvelle logique de calcul métier.

Cet outil est distinct de `src/check_quality_gate.py` (seul gate bloquant en
CI) et n'est **pas** intégré à `.github/workflows/generate-data.yml` — choix
explicite (issue #178) : jamais appelé automatiquement par la CI, usage
manuel uniquement. Voir `README.md` §12 pour la commande CLI.

