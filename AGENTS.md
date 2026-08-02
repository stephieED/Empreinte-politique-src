# AGENTS.md — Notes de fond du projet

Ce fichier documente **pourquoi** le projet est construit ainsi, pas
seulement **quoi** il fait. Le code et `README.md` décrivent le "quoi"
(commandes, arborescence) ; ce fichier est la mémoire longue des décisions
qui ne se voient pas en lisant un seul fichier. À maintenir à jour à chaque
décision structurante (nouvelle source, nouveau champ sensible, nouvelle
règle éditoriale).

---

## 1. Identité et positionnement

### Nom

Le produit s'appelle **Empreinte politique**. C'est le nom utilisé dans le
titre de `README.md`, dans la page méthodologie (`web/v3/methodologie.html`)
et dans `meta.licence_donnees` des profils générés.

Le dépôt héberge aussi un portail nommé **CONTRECHAMP** (`web/index.html`),
qui regroupe plusieurs prototypes visuels successifs (`v1/`, `v2/`, `v3/`,
puis des directions plus récentes : `atlas-augmente/`, `matiere-politique/`,
et des études absorbées : `scene-cinetique/`, `interface-essentielle/`,
`revue-civique/`, `moodboard/`). **CONTRECHAMP est un laboratoire de design
d'interface, pas un second produit** : toutes ces variantes affichent les
mêmes données de fond (`pivot_data/`), seule la mise en forme change. `v3`
est aujourd'hui la version la plus aboutie éditorialement (c'est elle qui
porte la page méthodologie).

### Public cible

Des citoyen⋅ne⋅s, journalistes et vérificateur⋅rice⋅s de faits qui veulent
consulter le bilan parlementaire **factuel et sourcé** des candidat⋅e⋅s à
l'élection présidentielle française de 2027, sans avoir à dépouiller
eux-mêmes des dumps de données ouvertes. Ce n'est **pas** un outil de
classement, de comparaison chiffrée entre candidats, ni un site d'analyse
politique. La baseline éditoriale de la page méthodologie résume l'intention :
« Des faits sourcés, sans note de performance » / « Politique en clair ».

### Contraintes éditoriales non négociables

Ces règles sont delibérément dupliquées dans le code (docstrings de
`schema_pivot.py`, `validate_profil()`), dans `README.md` (section
« Neutralité éditoriale ») et dans `web/v3/methodologie.html`. Toute
modification du schéma ou de l'affichage doit continuer à les respecter :

1. **Aucun jugement de valeur, aucun score.** Le projet agrège des faits
   bruts avec leur source primaire. Aucun classement, aucune note de
   "bonne"/"mauvaise" performance.
2. **Traçabilité systématique.** Chaque fait affiché doit pouvoir remonter à
   sa source primaire (scrutin officiel, dossier législatif, révision
   Wikipédia précise, jeu de données AN/PE officiel).
3. **Aucun taux individuel d'assiduité n'est jamais publié.** Un scrutin
   manqué ne décrit ni l'ensemble du travail parlementaire, ni les motifs de
   non-participation (maladie, mission, désaccord de procédure...). Publier
   un taux de présence inviterait à un classement que le projet refuse.
4. **Un 49.3 n'est jamais une position de vote.** Un texte adopté sans vote
   après engagement de la responsabilité du gouvernement (art. 49.3) est un
   **fait de procédure**. Une motion de censure liée est **toujours un
   scrutin distinct**, jamais fusionnée avec une position sur le texte visé.
5. **L'absence de donnée reste une absence de donnée, jamais un zéro.** Ne
   jamais transformer un `null`/liste vide en 0 dans un total affiché : cela
   ferait passer une source indisponible pour une inactivité réelle.
6. **Les champs éditoriaux sensibles exigent une source primaire avant
   d'exister.** Exemple : `position_dans_hemicycle` (majorité/opposition)
   n'est jamais renseigné sans `source_url` vérifiable — c'est vérifié
   techniquement par `schema_pivot.validate_profil()`, pas seulement par
   convention documentaire.
7. **Les ratios de groupe ne sont publiés qu'avec numérateur, dénominateur et
   couverture suffisante** ; sinon la valeur publique est `N/D` (jamais une
   estimation devinée). Les écarts individuels par rapport au groupe restent
   des données de contrôle qualité **internes**, jamais publiées.
8. **Les tags thématiques sont des aides de lecture, pas des positions
   déclarées.** Ce sont des mots-clés bruts extraits d'interventions, pas une
   classification validée par le candidat.

---

## 2. Schéma de données (architecture technique)

### Vue d'ensemble du pipeline

```
Sources publiques (APIs/dumps)
        │
        ▼
raw_data/profiles/<slug>.json          ← candidate_profile.py (AN/Sénat)
                                          + candidate_profile_ue.py (mandat UE, fusionné dedans)
        │  normalize_nosdeputes.py / normalize_europarl.py
        ▼
pivot_data/profiles/<slug>.pivot.json  ← schéma commun (schema_pivot.py)
        │
        ├─ group_profile.py   → pivot_data/groupes/groupe-<SIGLE>-<leg>.json  (schema_groupe.py)
        └─ parti_profile.py   → pivot_data/partis/parti-<slug>.json          (schema_parti.py)
```

- **`raw_data/`** : une représentation aussi proche que possible de chaque
  source (une par API), pas encore harmonisée entre chambres.
- **`pivot_data/`** : le format unique que consomme l'affichage (`web/`),
  indépendant de la source d'origine. C'est le seul niveau que `web/`
  devrait avoir besoin de lire.
- **Pourquoi deux niveaux séparés plutôt qu'un seul format ?** Pour pouvoir
  ajouter une nouvelle source (ex. Parltrack, un jour un équivalent Sénat)
  sans toucher au format consommé par l'affichage, et pour garder un
  débogage possible au niveau brut si l'adaptateur pivot a un bug.
- **Génération des groupes** (`group_profile.py` + `group_roster.py` +
  `generate_group_profiles.py`) : la liste des groupes réels à générer est
  validée manuellement dans `raw_data/groupes_reels.json` (une entrée par
  `(chambre, sigle, législature)` couvrant les candidats actuellement
  suivis) — pas de découverte automatique. `group_roster.py` récupère UNE
  SEULE FOIS la composition complète d'une chambre pour une législature
  donnée (`fetch_full_roster`), puis `filter_roster_by_sigle` la filtre
  localement par sigle : ça évite un appel réseau par groupe (7 groupes
  réels début 2026 → 2 fetches au lieu de 7). `generate_group_profiles.py`
  est l'orchestrateur batch appelé par `.github/workflows/generate-data.yml`.

### Fusion additive (`merge_profile.py`)

Principe : **une régénération ne supprime jamais une donnée déjà obtenue**.
Les API publiques utilisées sont sujettes à des aléas transitoires
(pagination qui bouge, requête HTML ponctuelle en échec...). Si on écrasait
le fichier existant à chaque régénération, un aléa transitoire ferait
disparaître des données réelles d'une exécution à l'autre.

- Listes générales (`votes`, `mandats`, `interventions`, mandats européens) :
  fusionnées via `merge_lists_by_key` avec une **clé d'unicité par type**
  (ex. `(numero_scrutin, date)` pour un vote) — additif pur : l'ancienne
  entrée gagne en cas de collision de clé, seule une entrée dont la clé
  n'existe pas encore est ajoutée.
- Listes « dossiers » (`amendements`, `dossiers_legislatifs`/`textes_portes`) :
  fusionnées via une fonction différente, `merge_dossier_records` — **la
  nouvelle entrée gagne en cas de collision de clé** (contrairement à
  `merge_lists_by_key` ci-dessus). Raison : pour ces deux listes, une
  régénération peut légitimement corriger une valeur déjà connue (ex.
  `role`/`stade_procedural` affiné, ou le `sort` d'un amendement qui passe
  de « en traitement » à un sort définitif) — garder systématiquement
  l'ancienne version figerait ces corrections. Rien n'est perdu pour
  autant : une entrée absente de la nouvelle collecte reste conservée.
- Champs scalaires (identité, groupe...) : la nouvelle valeur est gardée si
  elle est renseignée, sinon on retombe sur l'ancienne (jamais de régression
  vers `null` suite à un échec transitoire).
- **Exception délibérée à "jamais de suppression"** : `dossiers_legislatifs`
  (brut) / `textes_portes` (pivot) écartent désormais, lors d'une fusion,
  toute entrée dépourvue d'un `role` connu. Ce n'est pas un raté de la règle
  générale mais une décision de migration explicite : l'ancienne source
  (NosDéputés) renvoyait la même liste globale de dossiers pour tout le
  monde sur une législature donnée (`role` toujours `null` — voir "Cas
  limites" plus bas), donc conserver ces entrées reviendrait à préserver du
  bruit d'un bug corrigé plutôt qu'une donnée réelle perdue.

### Schéma pivot v1 (`src/schema_pivot.py`)

Un profil pivot est un dict avec ces clés racine (toutes validées par
`validate_profil()`) :

| Clé | Contenu |
|---|---|
| `id` | `"<source>:<identifiant_source>"`, ex. `"nosdeputes:jean-luc-melenchon"` |
| `nom`, `chambre`, `parti`, `groupe` | Identité de premier niveau. `chambre` ∈ `{AN, Senat, PE, mairie, null}` |
| `identite` | Bloc biographique nullable : profession, date/lieu de naissance, circonscription, lien HATVP |
| `sources[]` | Traçabilité : `{type, url, synchro_le}` par source utilisée |
| `mandats[]` | Élections, commissions, groupes d'amitié... avec dates, `actif`, et les champs sensibles ci-dessous |
| `votes[]` | Un enregistrement par scrutin, avec position et distinction 49.3/motion de censure |
| `textes_portes[]` | Dossiers dont l'élu est auteur/rapporteur/co-rapporteur, avec stade procédural |
| `amendements[]` | Amendements déposés, avec sort et distinction irrecevabilité/rejet |
| `interventions[]` | Prises de parole en séance |
| `tags_thematiques[]` | Mots-clés bruts (pré-harmonisation) |
| `meta` | `schema_version`, `genere_le`, `licence_donnees`, `warnings[]` |

**Conventions de nommage** :
- Tous les champs sont en français, `snake_case`.
- Un champ absent/non déterminable est `null`, jamais une chaîne vide ou un
  0 par défaut (cohérent avec la contrainte éditoriale n°5).
- Les valeurs catégorielles fermées sont des `frozenset` `KNOWN_*` dans
  `schema_pivot.py` (ex. `KNOWN_POSITIONS`, `KNOWN_TYPES_RAPPORT`) et
  validées par `validate_profil()` — ajouter une nouvelle valeur légitime
  nécessite d'étendre le frozenset correspondant, jamais de contourner la
  validation.
- Les identifiants externes utiles au cross-référencement (ex. `acteurRef`
  de l'Assemblée nationale, du type `PA1567`) sont conservés tels quels dans
  des champs comme `identite.url_an_ou_senat`, via `_extract_acteur_ref()`
  dans `candidate_profile.py`, plutôt que d'être ré-inventés.

### Logique de normalisation par source

- **NosDéputés/NosSénateurs** (`normalize_nosdeputes.py`) : traduit le
  format brut de `candidate_profile.py` (une chambre à la fois) vers le
  pivot. Ne fait aucun appel réseau — c'est un adaptateur pur.
- **Parlement européen** (`normalize_europarl.py`) : traduit la sortie de
  `candidate_profile_ue.py`. Les catégories `EU_INSTITUTION`,
  `COMMITTEE_PARLIAMENTARY_*`, `DELEGATION_*`... de l'API MEPs sont mappées
  vers les catégories fermées du pivot (`mandat_electif`, `commission`,
  `autre`) via `_CATEGORIE_MAP`.
- **Assemblée nationale (open data officiel)** : pas un adaptateur séparé —
  `candidate_profile.py` interroge directement les jeux de données bulk de
  `data.assemblee-nationale.fr` (scrutins, amendements, acteurs, dossiers
  législatifs) et alimente le format brut, qui repasse ensuite par
  `normalize_nosdeputes.py`. Voir `docs/an_opendata.md` pour le détail des
  schémas JSON réels (retro-documentés par échantillonnage, pas par la
  documentation officielle qui est datée/obsolète sur plusieurs points).

### Cas limites déjà identifiés et leur traitement

- **49.3 / motion de censure** : `votes[].type_vote == "motion_censure"`
  exige `texte_lie_id` (vérifié par `validate_profil()`). Un texte adopté par
  49.3 obtient `sort = "adopte_sans_vote_49_3"` sur le vote du texte, sans
  qu'aucune "position" de l'élu n'y soit associée.
- **Irrecevabilité vs rejet** : `amendements[].sort == "irrecevable"` exige
  `base_juridique_irrecevabilite` (`"art. 40"` recevabilité financière, ou
  `"art. 45"` lien avec le texte / "cavalier législatif"). Une irrecevabilité
  est un rejet **de procédure**, jamais confondue avec un rejet sur le fond.
  Le mapping `(etat.libelle, sousEtat.libelle)` de l'open data AN a été
  déterminé empiriquement sur ~3000 amendements réels (voir
  `_AMENDEMENT_SORT_MAP` et `docs/an_opendata.md`).
- **Suspension pour fonction gouvernementale** : un mandat suspendu (un
  parlementaire nommé ministre, art. 23 de la Constitution) ne doit jamais
  être confondu avec un mandat terminé — `mandats[].suspendu_pour_fonction_gouvernementale`
  porte une période dédiée `{debut, fin, suppleant_id}`.
- **Changement de groupe en cours de législature** : `votes[].groupe_au_moment_du_vote`
  permet de ne pas attribuer rétroactivement le groupe actuel à un vote
  passé ; côté profil de groupe, `membres[].fin_dans_groupe` + les calculs de
  cohésion ne comptent que les membres éligibles à la date de chaque scrutin.
- **Bug corrigé (2026) : `textes_portes` n'était pas spécifique à l'élu.**
  L'ancienne source (NosDéputés, endpoint `/{legislature}/dossiers/nom/json`)
  ne prend aucun paramètre par élu et renvoyait donc la **liste entière** des
  dossiers de la législature, identique pour tout le monde — `role` était
  donc toujours `null`, et la page méthodologie (qui n'affiche un texte que
  si `role` est connu) ne montrait jamais rien dans cette section. Remplacé,
  pour les député⋅e⋅s, par un index construit à partir des champs
  structurés `initiateur`/`rapporteurs` du jeu de données bulk "dossiers
  législatifs" de l'AN (voir `fetch_textes_portes_officiels` dans
  `candidate_profile.py`). Pas encore d'équivalent officiel pour les
  sénateurs (le champ reste vide/non fiable côté Sénat).
- **"Parti" (éditorial) ≠ "groupe parlementaire" (réel)** :
  `schema_parti.py` agrège des candidats déclarés partageant un même libellé
  de parti (`raw_data/candidats.json`), qui peuvent n'avoir **aucun mandat
  commun réel**. Ce schéma exclut donc délibérément toute cohésion de vote
  ou taux d'adoption agrégé — un comparateur qui n'aurait aucun sens sur un
  échantillon hétéroclite de 1 à quelques candidats.
- **Le domaine NosDéputés.fr utilisé (`nosdeputes.fr/deputes/json`) est en
  réalité figé sur la 16e législature (2022-06-22 → dissolution du
  2024-06-09), pas une source « temps réel » de la 17e législature en
  cours.** Vérifié le 2026-08-01 : les 618 entrées ont toutes un
  `mandat_fin` renseigné et `ancien_depute=1`. Aucun sous-domaine « 17e
  législature » équivalent n'a été trouvé. Conséquence concrète :
  `groupe`/`identite.groupe_sigle` dérivés de cette source reflètent la
  dernière composition connue **avant fin 2024**, pas la composition réelle
  actuelle d'un groupe — ne jamais présenter ces champs comme « à jour »
  sans ce caveat. Piste non implémentée pour une vraie fraîcheur 17e
  législature : les jeux « acteurs »/organes de `data.assemblee-nationale.fr`
  (déjà utilisés pour scrutins/amendements/dossiers), qui nécessiteraient un
  nouvel adaptateur dédié.
- **Titre d'un texte visé par un amendement** : l'open data amendements AN
  n'expose qu'un code source brut (`texteLegislatifRef`), pas un titre
  lisible ; résolu séparément via le jeu de données "dossiers législatifs"
  (voir `_build_texte_titre_index` dans `candidate_profile.py`).

---

## 3. Sources et licences

| Source | Type de données | Licence | Implication de partage à l'identique |
|---|---|---|---|
| NosDéputés.fr / NosSénateurs.fr (Regards Citoyens) | Mandats, groupes, textes portés (legacy) | **ODbL** | **Share-alike sur la base de données.** Si `pivot_data/`/`raw_data/` sont un jour publiés/téléchargeables en tant que jeu de données structuré (pas seulement affichés sur le site), ils constituent une "base de données dérivée" au sens ODbL et doivent être proposés sous ODbL (ou licence compatible), avec attribution à Regards Citoyens. Le site web rendu (pages HTML de `web/`) relève probablement du "Produced Work" ODbL, qui n'exige qu'une attribution, pas le partage à l'identique — mais un export de données brutes, lui, l'exige. |
| data.assemblee-nationale.fr (scrutins, amendements, acteurs, dossiers) | Votes nominatifs, amendements, identité, textes portés | **Licence Ouverte / Open Licence (Etalab)** | Attribution uniquement (mentionner la source et la date de mise à jour) ; **pas** d'obligation de partage à l'identique. Compatible avec l'ODbL et la CC BY, ne restreint donc pas la licence sous laquelle nos propres données combinées peuvent être publiées. |
| Parltrack | Mandats/organes du Parlement européen | **CC0 / ODbL** (mixte selon les jeux internes à Parltrack) | Là où une composante est ODbL, même obligation de partage à l'identique que NosDéputés ci-dessus si republiée en base ; les parties CC0 n'imposent rien. |
| Open Data Portal du Parlement européen | Mandats, commissions, groupes, votes UE | **CC BY 4.0** | Attribution uniquement, **pas** de partage à l'identique (contrairement à CC BY-SA). |
| Wikipédia FR | Veille candidatures | **CC BY-SA 4.0** | Ne s'applique en pratique que si du **texte verbatim** (citation longue) est réutilisé — nous n'extrayons que des faits ponctuels (dates, appartenance), pas des paragraphes ; toute citation verbatim future devrait cependant porter attribution + mention de la licence identique. |
| Wikidata | Veille candidatures | **CC0** | Aucune restriction. |

**Conséquence pratique à retenir** : tant que le projet ne fait qu'afficher
des faits sur des pages web (site "Produced Work"), l'attribution suffit
pour toutes les sources. Le jour où `raw_data/`/`pivot_data/` seraient
publiés comme **jeu de données téléchargeable** (API, export CSV/JSON en
libre accès), l'obligation de partage à l'identique de l'ODbL
(NosDéputés/NosSénateurs, et les parties ODbL de Parltrack) s'applique : ce
jeu de données combiné devrait être proposé sous ODbL ou une licence
compatible, pas sous une licence plus restrictive.

---

## 4. Métriques : ce qui est affiché et pourquoi

Cette section reflète la logique déjà énoncée dans
`web/v3/methodologie.html` (page publique de méthode éditoriale), reliée à
sa source de données dans le schéma pivot.

| Métrique | Ce qu'elle mesure | Limite d'interprétation | Affichage |
|---|---|---|---|
| **Textes portés** (`textes_portes[]`) | Textes où l'élu a un rôle factuel attesté : `auteur`, `rapporteur` ou `co-rapporteur`, avec un stade procédural réel. | N'est affiché que si le stade atteint au moins `examine_commission` (dépôt seul, rôle inconnu, ou simple volume d'interventions ne suffisent pas). Ne mesure pas l'investissement réel sur le texte, seulement un rôle institutionnel documenté. | **Public** |
| **Amendements** (`amendements[]`) | Comptes bruts par issue : adopté, rejeté, retiré, tombé, irrecevable, non soutenu. | Aucun taux d'adoption isolé n'est publié au niveau individuel : ces issues dépendent fortement du texte, de la procédure et du type de déposant (un amendement du gouvernement est adopté quasi systématiquement par construction). Un taux brut individuel serait trompeur sans ce contexte. | **Public** (comptes bruts individuels). Le taux d'adoption **par type de déposant** (`amendements_agreges.par_type_deposant` du profil de groupe) est lui aussi **public** — c'est le seul comparateur valide, à ne jamais confondre avec le taux agrégé tous-déposants confondus (`amendements_agreges` sans détail), trompeur car il mélange des amendements de nature institutionnelle très différente |
| **Votes de texte** (`votes[]`, `type_vote == "vote_texte"`) | Position sur des scrutins publics portant sur l'ensemble d'un texte (ordinaires et solennels). Pour un texte donné, seule la lecture la plus avancée connue est retenue. | Les votes sur articles/amendements isolés sont exclus de cette synthèse (bruit trop fin). Le périmètre retenu (public + solennel, pas seulement solennel) est affiché à côté du résultat pour éviter une impression de sélection arbitraire. | **Public** |
| **49.3 / motion de censure** (`votes[].sort == "adopte_sans_vote_49_3"`, `votes[].type_vote == "motion_censure"`) | Un engagement de responsabilité du gouvernement (fait de procédure) et, séparément, un vote de censure lié. | Jamais présenté comme une "position de vote" du candidat sur le texte concerné : l'absence de vote sur l'ensemble n'est pas un choix de l'élu. | **Public**, mais explicitement étiqueté comme fait de procédure, jamais fusionné avec une position de vote |
| **Présence / assiduité** | — (métrique volontairement **non calculée** en façade) | Un scrutin manqué ne dit rien du travail parlementaire global ni de son motif (mission, maladie, désaccord de procédure...). Publier un taux inviterait à un classement que le projet refuse par principe. | **Jamais public.** Les suspensions pour fonction gouvernementale sont signalées comme faits institutionnels, jamais comptées comme absences. |
| **Cohésion de groupe** (`cohesion_votes[]` du profil de groupe) | Participation et alignement du groupe sur un scrutin donné (`taux_participation`, `taux_coherence`). | Publié uniquement scrutin par scrutin, avec `membres_eligibles` (dénominateur) et couverture explicite. Sans numérateur/dénominateur fiable, la valeur publique est `N/D`, jamais une estimation. | **Public au niveau du groupe** ; les écarts d'un membre par rapport au groupe (`compute_ecarts_cohesion_internes` dans `group_profile.py`) restent **contrôle qualité interne** — techniquement, ils ne sont exposés que via l'option CLI `--rapport-interne`, jamais écrits dans le fichier public produit par `--out` |
| **Ordre des catégories** (`mandats[].position_dans_hemicycle`) | Majorité vs opposition, quand une source primaire vérifiable existe. | Ne masque jamais une catégorie de contenu ; change seulement l'ordre de lecture (ex. amendements avant textes pour l'opposition). Sans source, l'ordre neutre (textes puis amendements) s'applique et la règle active est affichée. | **Public** (le champ lui-même n'est renseigné qu'avec `source_url`, contrôlé par `validate_profil()`) |
| **Responsabilités** (`mandats[]`) | Fonctions occupées (présidence, rapport...), dédupliquées par intitulé. | Le volume brut de mentions (`notableCount`) peut servir à trier l'affichage mais n'est jamais montré comme un total ou un score. | Libellés/dates **publics** ; `notableCount` **interne uniquement** |
| **Tags thématiques** (`tags_thematiques[]`) | Mots-clés bruts extraits d'interventions (avant harmonisation — Phase 4 du README). | Aide de lecture, pas une position déclarée par le candidat ; pas encore un référentiel thématique stable (8-12 catégories prévues mais pas encore livrées). | **Public**, présenté explicitement comme non harmonisé |

---

## 5. Prochaines étapes (roadmap)

Séquence de travail en cours, autorisée étape par étape par l'utilisateur.
À maintenir à jour : cocher/déplacer une entrée vers "Fait" ci-dessus dans
les sections concernées dès qu'elle est implémentée et validée, pas seulement
planifiée.

### En cours

- **Questions (QE/QG/QOSD)** : intégrer les 3 jeux de données open data AN
  "questions écrites", "questions au gouvernement" et "questions orales sans
  débat" (mêmes URLs par législature que scrutins/amendements, voir
  `docs/an_opendata.md`). Les 3 partagent EXACTEMENT le même schéma
  (`question.@xsi:type` distingue `QuestionEcrite_Type` /
  `QuestionGouvernement_Type` / `QuestionOrale_Type`) : un seul parseur
  générique suffit pour les 3. Objectif : alimenter
  `interventions[].type_detail == "question"` depuis une source officielle
  structurée (`auteur.identite.acteurRef` direct, texte intégral
  question/réponse, ministère interrogé, date JO) plutôt que par scraping
  NosDéputés comme aujourd'hui — un gain net de fiabilité, pas une simple
  redite d'une donnée déjà correcte.

### Prévu ensuite

- **Représentants d'intérêts** : recherche seule (pas nécessairement une
  implémentation) sur le registre des relations élu⋅e↔lobbyiste. Probablement
  hors du périmètre `data.assemblee-nationale.fr` : l'enregistrement des
  représentants d'intérêts relève de la HATVP (Haute Autorité pour la
  Transparence de la Vie Publique), pas de l'Assemblée nationale — à vérifier
  en premier lieu sur le portail open data de la HATVP plutôt que de chercher
  un jeu de données AN qui n'existe probablement pas. `identite.uri_hatvp`
  (déjà dans le schéma pivot) est le point d'ancrage naturel si une source
  structurée est trouvée.

### Identifiées mais pas planifiées (priorité basse)

- **Agenda / réunions** (`.../vp/reunions/Agenda.json.zip`) : décrit les
  réunions de commission/séance (ordre du jour, dossiers examinés). Organisé
  par organe/réunion, pas par acteur — plus utile pour dater précisément
  l'examen d'un texte en commission que pour enrichir directement un profil
  individuel. Pas un besoin exprimé aujourd'hui.
- **Organismes extra-parlementaires** (CSV,
  `.../amo/oep_csv_opendata/liste_organismes_extra_parlementaires_excel.csv`) :
  correspond à la catégorie `extra_parlementaire` déjà prévue dans
  `schema_pivot.KNOWN_CATEGORIES`, mais le rapprochement avec un profil ne
  peut se faire que par nom en texte libre (pas d'`acteurRef`) — un vrai
  risque de faux positifs sur homonymes. À ne pas implémenter sans une
  stratégie de matching prudente (ex. nom + groupe, ou couverture partielle
  acceptée plutôt qu'un mauvais rapprochement).
- **Taxonomie thématique harmonisée** (Phase 4, voir `README.md`) : remplacer
  les `tags_thematiques[]` bruts par 8 à 12 catégories stables, via une table
  de correspondance versionnée dans le dépôt. Toute modification du découpage
  devra être tracée dans le changelog du projet.

---

## Références internes

- `README.md` : arborescence, commandes de génération, taxonomie des
  sources, limites de couverture connues.
- `src/schema_pivot.py` : contrat de structure du profil individuel
  (docstring exhaustive + `validate_profil()`).
- `src/schema_groupe.py` / `src/schema_parti.py` : contrats d'agrégation
  groupe réel / parti éditorial.
- `docs/an_opendata.md` : schémas JSON réels de l'open data AN
  (scrutins, amendements, acteurs, dossiers législatifs), retro-documentés
  par échantillonnage direct des données.
- `web/v3/methodologie.html` : page publique de méthode éditoriale (source
  de la section 4 de ce document).
