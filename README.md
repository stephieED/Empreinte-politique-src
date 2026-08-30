# EMPREINTE POLITIQUE

![Projet en construction](https://img.shields.io/badge/PROJET-EN%20CONSTRUCTION-00E5FF?style=for-the-badge&labelColor=17141F)

> [!WARNING]
> **Ce projet est en construction.** Le pipeline et l'interface évoluent
> quotidiennement. Les données publiées sont réelles et sourcées, mais peuvent
> être incomplètes, et certaines absences portent encore une explication
> imprécise — ne pas conclure d'une liste vide sans lire son bloc `couverture`.
>
> L'état courant se lit dans les
> [issues ouvertes](https://github.com/stephieED/Empreinte-politique-src/issues).

**Empreinte politique** produit des « CV politiques » factuels et sourcés —
mandats, responsabilités, votes, textes portés, interventions en séance — pour
les candidats à l'élection présidentielle française de 2027, ainsi que pour les
groupes parlementaires et les gouvernements réels.

**Principe directeur** : tout fait affiché doit être traçable jusqu'à une source
primaire (un scrutin officiel, un dossier législatif, une révision précise de
Wikipédia). Le projet ne porte aucun jugement de valeur.

---

## Ce qu'on n'y trouvera pas

C'est ce qui distingue ce projet, et ce sont des règles non négociables,
dupliquées dans le schéma, dans la validation et dans la page méthodologie :

1. **Aucun jugement de valeur, aucun score, aucun classement.**
2. **Traçabilité intégrale** : chaque fait renvoie à une source primaire.
3. **Aucun taux de présence individuel n'est jamais publié.**
4. **Un 49.3 n'est jamais traité comme une position de vote** — c'est un fait de
   procédure, présenté comme tel.
5. **Une donnée manquante reste manquante**, jamais un `0` par défaut. Une liste
   vide se lit avec son bloc `couverture`, jamais toute seule.
6. Une position dans l'hémicycle exige une `source_url` vérifiable.
7. **Un ratio de groupe n'est publié qu'avec son numérateur, son dénominateur et
   une couverture suffisante** ; sinon `N/D`. Les écarts individu ↔ groupe sont
   du contrôle qualité interne, jamais public.
8. Les étiquettes thématiques sont des aides à la lecture, pas des positions
   déclarées par le candidat.

Le détail et le raisonnement : [`AGENTS.md`](AGENTS.md) §2 et §6.

## D'où viennent les données

| Source | Ce qu'elle apporte | Cadence | Licence |
|---|---|---|---|
| [Open data de l'Assemblée nationale](https://data.assemblee-nationale.fr/) | **La seule source française** depuis #529 : identité, mandats, votes, amendements, dossiers, comptes rendus Syceron, questions | quotidienne | Licence Ouverte (Etalab) — attribution |
| [Parltrack](https://parltrack.org) | Le volet européen des anciens eurodéputés | hebdomadaire (environ) | ODbL v1.0 — **partage à l'identique** |
| [Parlement européen](https://data.europarl.europa.eu/) | Le mandat européen | en direct, à chaque run | CC BY 4.0 — attribution, `User-Agent` identifiant le réutilisateur, 500 requêtes / 5 min |
| Wikipédia / Wikidata | Le suivi des candidatures déclarées | immédiate | CC BY-SA 4.0 / CC0 |
| NosDéputés / NosSénateurs | **Plus collectées** depuis #528/#529, mais des champs déjà publiés en dérivent | — | ODbL v1.0 — **partage à l'identique** |

Le corpus **n'est pas** sous une licence unique, et avoir cessé de collecter
Regards Citoyens n'y a rien changé (#530) : chaque profil déclare dans
`meta.licence_donnees` les licences dont son propre contenu relève, dérivées de
ses `sources[]` par `src/licences.py`. Le site HTML est une « œuvre dérivée »
ODbL (attribution suffisante) ; une republication des données brutes
téléchargeables déclenche le partage à l'identique.
→ [`AGENTS.md`](AGENTS.md) §7, `docs/decisions/licence-lot-6-530.md`.

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

`requirements-dev.txt` tire `requirements.txt` (les dépendances d'exécution) et
y ajoute `pytest`. Pour un environnement d'exécution seul — ce que font les jobs
d'extraction — installer `requirements.txt`.

Toutes les commandes se lancent **depuis la racine du dépôt**, environnement
virtuel activé.

## Une première chose à lancer

Le profil d'un candidat, brut puis pivot :

```bash
python3 src/generate_all_profiles.py --only jean-luc-melenchon --pivot
```

Puis l'interface, sur les données présentes en local :

```bash
cd web/UI_finale
npm install     # la première fois seulement
npm run dev     # synchronise les données puis démarre Vite
```

**Toutes les autres commandes du dépôt sont dans
[`docs/commandes.md`](docs/commandes.md)** — générer, auditer, vérifier avant de
committer, opérer, voir ce que voit l'utilisatrice. Une commande y est
documentée si l'on peut avoir à la lancer soi-même, et
`tests/test_commandes_documentees.py` vérifie à chaque run que ce fichier ne
cite ni un script disparu ni une option qui n'existe plus.

## Où vit quoi

```
raw_data/      Entrées déclaratives + collecte brute (proche de la source)
  candidats.json            la liste éditoriale des candidats déclarés
  groupes_reels.json        les groupes parlementaires à produire
  gouvernements_reels.json  les gouvernements à produire
  profiles/                 <slug>.json + une tranche par législature (#580)
pivot_data/    Le format pivot — la SEULE couche que web/ lit
  profiles/       <slug>.pivot.json
  groupes/        groupe-<SIGLE>-<leg>.json
  gouvernements/  gouvernement-<ID>.json
  partis/         agrégats éditoriaux, usage interne
  scrutins.json   index partagé des scrutins (#432)
  amendements/    index partagé des amendements, un fichier par législature (#431)
src/           Le pipeline (collecte, normalisation, agrégation, audits, gate)
scripts/       Les scripts d'exploitation (run local, bornage, rendu du formulaire)
web/UI_finale/ L'interface de production : React 19 + Vite
web/old/       Les générations de design archivées (v1–v7)
docs/          La documentation (voir ci-dessous)
tests/         La suite pytest
```

`.cache/` et `logs/` sont créés automatiquement et git-ignorés.

Un profil pivot ne se lit **plus seul** : ses votes et ses amendements ne sont
que des renvois (`{scrutin_id, position}`, `{amendement_id, role_signataire}`)
vers les deux index partagés. Pourquoi, et ce que ça a fait gagner :
[`docs/data-architecture.md`](docs/data-architecture.md).

## Où aller pour le reste

| Question | Fichier |
|---|---|
| **« Quelle était la commande, déjà ? »** | [`docs/commandes.md`](docs/commandes.md) |
| **« Que devient la donnée ? »** — flux, schémas, les six sorties de `pivot_data/`, volumétrie | [`docs/data-architecture.md`](docs/data-architecture.md) |
| **« Que fait un run ? »** — les huit jobs, le formulaire de lancement, caches, artifacts, budgets, le push, la relance automatique | [`docs/workflow-generate-data.md`](docs/workflow-generate-data.md) |
| **« Comment marche l'extraction pilotée par roster ? »** — le seul job qui a une page à lui | [`docs/extract-roster-groupes.md`](docs/extract-roster-groupes.md) |
| **« Pourquoi c'est fait comme ça ? »** — une décision par fichier | [`docs/decisions/`](docs/decisions/), indexées par [`docs/technical_decisions.md`](docs/technical_decisions.md) |
| **« Où l'Assemblée publie-t-elle ce champ ? »** — les références qui dérivent avec leur fournisseur, pas avec notre code | [`docs/sources/`](docs/sources/) |
| **Les règles non négociables, pour un agent comme pour un humain** | [`AGENTS.md`](AGENTS.md) |
| **Ce qui est planifié, et les défauts connus restés ouverts** | [`ROADMAP.md`](ROADMAP.md) |

## Ce que la couverture ne couvre pas encore

- **Groupes** : seuls les **7 groupes** déclarés dans
  `raw_data/groupes_reels.json` sont produits, pas tous ceux qui existent. Les
  **2 groupes du Sénat sont suspendus** depuis le 24/08/2026 : #528 a sorti le
  Sénat du périmètre du produit, la suspension attend donc une réouverture
  éditoriale explicite, plus un certificat. Leurs fiches publiées restent en
  place, gelées.
  → [`docs/decisions/retrait-senat-528.md`](docs/decisions/retrait-senat-528.md),
  [`docs/decisions/extraction-groupe-suspendue-516.md`](docs/decisions/extraction-groupe-suspendue-516.md)
- **Gouvernements** : seuls ceux déclarés dans
  `raw_data/gouvernements_reels.json`, pas toute la Ve République.
  `membres[].portefeuille` et `premier_ministre` restent `null` quand aucun
  pivot local ne les porte — jamais un « Ministre » générique ni un nom déduit
  du libellé du gouvernement.
- **Membres des groupes** : l'extraction pilotée par roster vise la couverture
  quasi complète des membres des groupes configurés, mais elle n'est pas encore
  atteinte. Tant qu'elle ne l'est pas, `web/UI_finale` affiche un état « pas de
  donnée » explicite plutôt qu'un zéro trompeur (règle 5).
  → [`docs/decisions/seuil-couverture-groupe.md`](docs/decisions/seuil-couverture-groupe.md)
- **Votes AN** : open data officiel, 14<sup>e</sup> à 17<sup>e</sup> législature
  selon les dumps disponibles.
- **Sénat** : hors périmètre depuis #528 — pas de job de collecte, pas de
  chambre `senateurs`. Les mandats sénatoriaux déjà publiés le restent.
- **Interventions** : Syceron est la seule source depuis #529, et sa résolution
  d'identifiants d'acteur nus reste livrée inactive (#510) — une collecte
  fraîche ne rend donc que les questions officielles. Les prises de parole déjà
  publiées sont conservées par la fusion additive.
- **Maires, portefeuille ministériel hors AN, textes européens** : hors
  périmètre, investigués et écartés.
  → [`docs/decisions/hors-perimetre.md`](docs/decisions/hors-perimetre.md)
- **Biais de couverture** : un ancien parlementaire laisse des traces bien plus
  riches qu'un candidat qui ne l'a jamais été.

## Tests

```bash
pytest -q
```

La suite tourne en une dizaine de secondes et s'exécute sur chaque pull request
et chaque push sur `main` (`.github/workflows/tests.yml`). Elle est **découplée
du corpus vivant** : aucun test ne lit `pivot_data/` ni `raw_data/profiles/`,
aucun n'écrit sous l'un des deux, aucun ne sort sur le réseau (#473). Le job CI
le rend structurel — il ne pose sur le disque du runner qu'une liste blanche de
chemins, si bien qu'un test qui se recouplerait au corpus y échoue en nommant le
fichier. Les tests d'acceptation qui ont besoin de vrais profils lisent les
fixtures figées de `tests/fixtures/`.
→ [`docs/decisions/ci-tests-pytest.md`](docs/decisions/ci-tests-pytest.md)

## Neutralité éditoriale

Ce projet agrège des faits et des sources primaires. Il ne produit ni classement,
ni score, ni appréciation des positions politiques. L'ensemble des règles :
[`AGENTS.md`](AGENTS.md).
