# Design system — Empreinte politique (UI_finale)

Version finale, réconciliée avec le code de production. Cette v2 part de la direction artistique préliminaire publiée en artifact Claude (« Empreinte — Direction artistique · v1 », [claude.ai/code/artifact/d48b7554-0af3-45bd-904e-94367577ff4a](https://claude.ai/code/artifact/d48b7554-0af3-45bd-904e-94367577ff4a), 2026-08-14) et la confronte ligne à ligne au code réel de `web/UI_finale/src`. Chaque valeur ci-dessous est soit **vérifiée** (présente telle quelle dans le code), soit signalée **cible** (présente dans la DA préliminaire mais pas encore strictement respectée par l'implémentation — voir §8 Écarts).

`docs/design_intent.md` (pistes cartographie/géologie/archéologie/architecture pour `web/v4`-`v7`) reste **obsolète et non retenu**, sans lien avec ce document.

Le brief et les itérations qui ont mené à cette DA (cibles, socle « SaaS analytique », pivot loin d'une première direction façon Revolut, alternatives explicitement écartées) sont documentés dans `docs/decisions/direction-artistique-empreinte.md`.

---

## 0. Principe directeur

*« Donner à lire l'activité parlementaire sans jamais la noter. »*

Un système au service d'une règle éditoriale, pas l'inverse : chaque décision de marque, couleur, typographie ou composant sert la neutralité et la traçabilité définies par [[ligne-editoriale-empreinte-politique]] (`AGENTS.md §2`). La section 6 (Voix) formalise ce lien — c'est la partie la plus originale de la DA préliminaire et la moins visible en lisant seulement le CSS.

---

## 1. Marque

**Symbole et lockup** — une empreinte de pas stylisée : la trace, pas le jugement porté sur elle. Le jaune signal ne marque jamais le texte du logo ; il reste réservé à l'arche du pas.

Trois formes, verified dans `src/components/Brand.jsx`/`Brand.css` et cotées dans `web/old/logo-propositions/exports/empreinte-lockup-2lignes-specs.md` :

| Forme | Usage | Cote |
|---|---|---|
| Signature courte (symbole + « Empreinte ») | Nav, en-têtes compacts, contextes à espace comptable | — |
| Lockup complet (symbole + « Empreinte politique ») | Réservé aux contextes ≥ 58px de haut | Sous ce seuil, la légende « POLITIQUE » (vectorisée à 12px de référence) devient illisible |
| Symbole seul | Favicon, app icon, avatar, nav réduite/mobile (< 480px) | Toujours carré, jamais étiré |

**Zone de protection** : 16px minimum sur les 4 côtés, déjà intégrée dans le viewBox de chaque SVG maître — aucun élément de nav ne doit l'entamer. *Vérifié* : viewBox de référence `13.52 -0.73 329.27 87.26`, marge réelle 16px (specs.md).

**À faire** : dimensionner le SVG en `width`/`height` réels pour un rendu vectoriel natif — jamais de `transform: scale()` en CSS.

**À éviter** :
- Afficher le lockup complet sous 50px de haut — la légende devient un magma illisible (*vérifié* : `Brand.css` le rend à 58px précisément pour cette raison).
- Le jaune signal en texte ou trait fin sur fond clair — ratio de contraste **1.05:1, échec AA** (voir §2 pour la table complète). Réservé à l'accent graphique non textuel de jour.

---

## 2. Couleur

**Principe** : l'encre et le blanc cassé portent tout le texte. Le jaune signal ne sert jamais à indiquer un jugement — il marque la sélection, l'action, la source vérifiée. Les couleurs de vote sont **fonctionnelles, pas décoratives** : vert et rouge ne restituent qu'un scrutin réel, jamais une préférence éditoriale.

### Palette neutre — *vérifiée*, `src/index.css` `:root`

| Token | Valeur | Usage |
|---|---|---|
| Encre `--ink`/`--dark` | `#14151A` | Texte, bannières, fonds sombres — base de toute la hiérarchie |
| Blanc cassé `--bg` | `#F7F6F4` | Fond de page. Jamais un blanc pur — toujours légèrement chaud |
| Jaune signal `--accent` | `#DFFF00` | Accent unique : sélection active, badges, focus. **Jamais en texte sur fond clair** |
| Gris sourd `--muted` | `#8B8794` | Texte secondaire, légendes, métadonnées |
| Carte `--card` | `#FFFFFF` | Surface des cartes, contraste doux avec le fond |
| Bordure | `#F0EEEB` · `#E7E4DF` | Séparateurs, contours discrets — deux valeurs, jamais du gris neutre générique |

### Couleurs de vote & d'issue — *vérifiées*, `src/utils/lecture.js` (`VOTE_STYLE` / `OUTCOME_COLOR`)

| Sens | Hex | Constante code |
|---|---|---|
| Pour / Adopté | `#007A45` | `pour` / `adopté` |
| Contre / Rejeté | `#E53420` | `contre` / `rejeté` |
| Abstention / Tombé | `#8B8794` | `abstention` / `tombé` |
| **Non-votant** | **aucune** — contour tireté | `non_votant` |
| Retiré | `#F2A93B` | `retiré` |
| Irrecevable | `#B8B4AE` | `irrecevable` |
| Non soutenu | `#DCD9D3` | `non_soutenu` |

**Les positions de vote ne forment pas une échelle** (#326). Pour, Contre et Abstention sont des positions *exprimées* : elles portent une couleur. `non_votant` n'en est pas une — il se distingue par la **forme**, jamais par une teinte. Un dégradé chaud-froid sur les quatre fabriquerait un jugement (§2 règle 1 de `AGENTS.md`).

**Quatre valeurs, pas cinq.** « Absent » n'apparaît dans aucune des 1 312 951 positions publiées (mesuré au commit de données `245511b4`, 31/08/2026) : lui donner une catégorie publierait une absence comme un fait de vote, c'est-à-dire le taux de présence individuel qu'interdit §2 règle 3. Toute valeur inconnue tombe sur la forme sans teinte. Verrouillé par `tests/test_fondations_lecture_326.py`.

Ces couleurs vivaient en constantes JS **dupliquées** dans `CandidateProfile.jsx` et `GroupProfile.jsx`, sans `non_votant` — les 21 229 positions `non_votant` du corpus s'y affichaient sans couleur **ni libellé**. Elles sont désormais définies une seule fois, dans `src/utils/lecture.js`, que les deux composants importent.

### Table de contraste (WCAG AA, seuil 4.5:1)

| Paire | Premier plan | Fond | Ratio | Verdict |
|---|---|---|---|---|
| Texte principal, jour | `#14151A` | `#F7F6F4` | 16.88:1 | PASS |
| Texte principal, nuit | `#F7F6F4` | `#14151A` | 16.88:1 | PASS |
| Signal sur fond sombre | `#DFFF00` | `#14151A` | 16.01:1 | PASS |
| Signal sur fond clair | `#DFFF00` | `#F7F6F4` | **1.05:1** | **FAIL** |

C'est la justification chiffrée de la règle « accent jamais en texte sur fond clair » (§1, §5) — pas une convention arbitraire.

---

## 3. Typographie

**Manrope porte toute la hiérarchie — aucune deuxième famille.** C'est le poids et la taille qui font le travail, pas un contraste de style. Poids chargés : 400, 500, 600, 700, 800 (`index.html`, Google Fonts). Les nombres restent alignés en tabulaire (`font-variant-numeric: tabular-nums`) partout où ils se comparent — *vérifié* sur `.gp-kpi-value` et `.cp-num`.

### Échelle d'usage

| Usage | Exemple | Spécification | Statut |
|---|---|---|---|
| Titre profil (bannière h1) | « Jean-Luc Mélenchon » | 34px · 800 · -0.01em | Vérifié (`.banner h1`) |
| Valeur KPI | « 1 042 » | 26px · 800 · tabular-nums | Vérifié (`.gp-kpi-value`) |
| Grand nombre de fiche candidat | « 2 429 » | 22–28px · 800 · tabular-nums | Vérifié (`.cp-trace-nombre`, `.cp-bloc-nombre`, #328) |
| Titre de section | « Cohésion de vote » | 16px · 800 | Vérifié (`.gp-section-title`) |
| Titre de carte (vote/texte) | « L'ensemble du projet de loi » | 14px · 700 | **Partiel** — `.cp-ligne-titre` (14px/600, #328) et `.gp-vote-texte` (14px, poids hérité). Voir §8. |
| Libellé de chip/onglet | « Socialistes et apparentés » | 13px · 600 | Vérifié (`.cb-chip`, `.tab-btn`, `.cp-puce`) |
| Badge/pill | « Source vérifiée » | 11–12px · 700 | Vérifié (`.vote-badge`, `.gp-verified-badge`) |
| Libellé de bande (majuscules) | « GROUPES » | 11px · 700 · +0.04em | Vérifié (`.cb-bar-label`, `.gb-bar-label`) |
| Métadonnée/caveat | « Mesure la durée, pas l'implication. » | 12–13px · 400–600 | Vérifié (`.gp-kpi-caveat`, `.cp-section-critere`) |

---

## 4. Espacements & formes

**Principe cible** : une seule gouttière de page (40px) et un vocabulaire de rayons à trois valeurs — le pilulier pour tout ce qui se choisit, la carte à 18px pour ce qui se lit, le cercle pour ce qui représente une personne.

### Espacements

Échelle cible (DA préliminaire) : `4 · 8 · 12 · 16 · 20 · 28 · 40 · 64`.
Échelle réellement observée dans `src/components/*.css` (relevé exhaustif) : `2, 3, 4, 5, 6, 8, 9, 10, 12, 14, 16, 18, 20, 22, 24, 28, 32, 40, 64` px. L'implémentation est plus dense que la cible — voir §8 pour la lecture de cet écart. `40px` reste bien la gouttière de page constante (`padding: 32px 40px 64px` sur `.main`/`.gp-main`).

### Rayons — *vérifiés*

| Rayon | Usage |
|---|---|
| 14–16px | Petit élément (membre, item de liste) |
| 18px | Carte |
| 999px | Chip / pilule |
| 50% | Avatar / donut |

### Élévation — *vérifiée*, correspond exactement aux `box-shadow` du CSS

| État | Valeur |
|---|---|
| Repos, petit item | `0 1px 8px rgba(20,15,40,.05)` |
| Repos, carte | `0 2px 12px rgba(20,15,40,.06)` |
| Survol, chip | `0 4px 14px rgba(20,15,40,.10)` |
| Survol, carte KPI | `0 6px 20px rgba(20,15,40,.14)` |

Toutes les ombres partagent la même teinte de base (`rgba(20,15,40,…)`, un noir-violet proche de `--ink`) — seule l'opacité varie avec le niveau d'élévation.

**Forme signature non couverte par la DA préliminaire** : les bandeaux d'en-tête (`.banner`, `.gp-banner`) ont un coin supérieur droit tranché à 28px (`clip-path: polygon(0 0, calc(100% - 28px) 0, 100% 28px, 100% 100%, 0 100%)`) — la seule rupture de forme rectangulaire du système, à traiter comme un élément de signature récurrent.

---

## 5. Composants

Vocabulaire vérifié dans `src/components/*.css` et `*.jsx` :

| Composant | Règle |
|---|---|
| **Carte KPI** | Survol → la mise en garde (« caveat ») recouvre la carte en overlay. Chaque métrique explique elle-même sa limite (`.gp-kpi-caveat`) — aucune n'est présentée comme un score. **Retirée de la fiche candidat depuis #328** : quatre KPI en tête de page classent avant qu'on ait lu un chiffre ; le critère de chaque section (`.cp-section-critere`) porte désormais la mise en garde, en permanence et non au survol. |
| **Carte de vote** | Point + libellé colorés selon la position (`VOTE_STYLE`). Le badge « Source vérifiée » réutilise systématiquement le jaune signal — jamais une autre couleur pour ce badge précis. |
| **Onglets** | Fond plein jaune signal pour un onglet exclusif (`.tab-btn.active`). |
| **Pills de filtre** | Contour encre inversé pour un filtre multi-état (`.gb-chip.active` : fond `--dark`, texte blanc). Deux formes du même principe visuel, jamais confondues. |
| **Chip de sélection (groupe/candidat)** | Avatar à initiales + libellé. À l'état actif, l'avatar seul bascule au jaune signal — le fond de la chip passe à l'encre (`GroupsBar`) ou reste blanc à bordure encre (`CandidatesBar` — asymétrie assumée entre les deux barres, voir composants respectifs). |
| **Barre de répartition/comparaison** | Segments proportionnels au décompte réel, jamais normalisés à effet visuel — un groupe avec peu d'amendements produit une barre visiblement courte (`.cp-barre` et ses segments, #328).  Un segment **sans teinte** (motif hachuré, `.cp-barre-seg--sans-teinte`) est réservé à ce qui n'est pas une issue : un sort d'amendement non publié (§2 règle 5) et un texte adopté sans vote par l'article 49.3 (§2 règle 4). **Jamais pour une cohésion de vote** : `.gp-coherence-track`/`.gp-coherence-fill` sont retirées depuis #329, parce qu'une barre place des catégories sur une échelle du pire au meilleur (`AGENTS.md` §2 règle 1). |
| **Décomptes de cohésion (fiche de groupe)** | Six nombres, jamais une barre (`.gp-decomptes`, #329). Les positions exprimées gardent leur teinte ; `Non-votant`, `Sans trace de vote` et `Excusés` se distinguent par la **forme** (contour tireté, aucune teinte), comme `non_votant` depuis #326. La somme des six retrouve exactement `membres_eligibles` — vérifié sur 19 832 / 19 832 entrées des 5 fiches AN. |
| **Donut de couverture** | Affirme sans détour la part de données réellement disponible (ex. « 14/66 membres ») — jamais maquillé en score de qualité (`.gp-coverage-donut`). |
| **Statut membre (actif/ancien/non renseigné)** | Pilule 999px, fond plein `--dark` si membre à la date de référence ; contour `#c9c4be` + texte muted si parti avant ; **contour tireté** si l'appartenance n'est pas renseignée (`.gp-member-status-inconnu`, #329) — `null` n'est pas `false`, et un départ ne se publie pas sur une donnée absente (§2 règle 5). Jamais de rouge/vert de statut. |

---

## 6. Voix — le ton fait partie de la direction artistique

*Empreinte documente, elle ne classe pas.* Cette règle se lit autant dans le vocabulaire que dans la couleur — section absente de ma première version de ce document, réintégrée depuis la DA préliminaire car elle formalise un lien direct avec [[ligne-editoriale-empreinte-politique]] :

- **Chaque métrique porte sa propre limite** : aucun chiffre n'est affiché seul. Une phrase de mise en garde accompagne systématiquement la valeur — au survol sur la fiche de groupe (`.gp-kpi-caveat`), **en permanence** sur la fiche candidat depuis #328 (`.cp-section-critere`, `.cp-note`), parce qu'une limite qu'il faut survoler n'est pas lue.
- **Précision plutôt qu'emphase** : « Lecture la plus avancée retenue pour chaque texte », pas « votes comptés ». Le vocabulaire nomme exactement ce qui est mesuré, jamais ce qu'on aimerait suggérer.
- **Aucun vocabulaire de classement** : pas de « score », « note », « rang » ou « performance » nulle part dans l'interface — jusque dans le texte d'aide du panneau latéral. Découle directement de la règle éditoriale 1 (`AGENTS.md §2`).
- **La couverture partielle s'assume** : « 14 / 66 membres » s'affiche tel quel, sans arrondi flatteur ni habillage en pourcentage seul — cohérent avec la règle éditoriale 7 (ratios toujours num/dénom).

Deux textes permanents cités par la DA préliminaire :
> « Données publiques agrégées. Aucun score, aucun classement. » — pied de la navigation
> « Empreinte politique ne publie aucun taux individuel d'assiduité, de présence ou d'absence — un scrutin manqué ne décrit ni le travail parlementaire ni ses motifs. »

Le premier (pied de navigation) est *vérifié* : `ExplorerLayout.jsx` `.explorer-footer`, affiché sur les trois vues principales (candidat/groupe/gouvernement) avec les liens vers `/methodologie` et `/mentions-legales`, et repris à l'identique sur `LandingPage.jsx` (`.landing-footer`) pour que ces deux pages restent atteignables sans détour par l'outil. Le second (panneau latéral) reste à vérifier au prochain audit — non confirmé dans le CSS/JSX lu pour cette version.

---

## 7. Grille & réponse

- **Une seule vraie rupture, sur la marque** : sous 480px, le lockup complet cède la place au symbole seul — la largeur ne suffit plus à garder « POLITIQUE » lisible. *Vérifié* : `Brand.css` `@media (max-width: 480px)`.
- **Grilles de cartes** : `auto-fit`/`minmax()` plutôt que des colonnes fixes — le nombre de colonnes se déduit de la largeur réelle, jamais fixé par point de rupture. *Vérifié* : `.kpi-grid`, `.votes-grid`, `.shelf-items`, `.gp-kpi-grid`, etc.
- **40px** : gouttière horizontale constante de la page — navigation, contenu, bandeau de marque partagent la même marge, jamais une marge indépendante. *Vérifié*.
- **1600px** : largeur maximale de la zone de contenu — au-delà, l'espace supplémentaire se redistribue dans les grilles plutôt que de laisser un vide. *Vérifié* : `.main`, `.gp-main` `max-width: 1600px`.

---

## 8. Écarts entre la DA préliminaire (cible) et l'implémentation actuelle

À corriger ou à assumer explicitement lors d'un prochain passage sur `web/UI_finale` :

1. **Titres de carte vote/texte pas en 700** : `.vote-title` a disparu avec la refonte de la fiche candidat (#328), remplacée par `.cp-ligne-titre` en 14px/600 ; `.gp-vote-texte` est toujours à 14px sans `font-weight` explicite. Reste à harmoniser entre 600 et 700, sur une seule valeur.
2. **Échelle d'espacement plus dense que la cible** : la cible propose 8 valeurs (`4·8·12·16·20·28·40·64`), le code en utilise 19 (`2,3,4,5,6,8,9,10,12,14,16,18,20,22,24,28,32,40,64`). Pas nécessairement un bug — beaucoup de ces valeurs sont des ajustements fins légitimes (ex. `9px` padding tab) — mais si l'intention est de converger vers l'échelle à 8 valeurs, c'est un chantier de refactor CSS, pas une correction ponctuelle.
3. ~~**Couleurs de vote dupliquées sans partage de source**~~ — **corrigé par #326** : `VOTE_STYLE`/`OUTCOME_COLOR` vivent dans `src/utils/lecture.js`, avec les cinq autres primitives de lecture, et les deux composants les importent. Les règles propres à la fiche de groupe sont dans `src/utils/groupe.js` (#329), qui importe le premier.
4. **Chip active — asymétrie Candidats/Groupes** : `CandidatesBar` (`.cb-chip.active`) passe en fond blanc à bordure encre, `GroupsBar` (`.gb-chip.active`) passe en fond encre plein — la DA préliminaire ne documente qu'un seul comportement (« le fond de la chip passe à l'encre »). À vérifier si l'asymétrie est un choix voulu (différencier visuellement candidat vs groupe) ou une divergence non intentionnelle.
5. **Texte permanent du panneau latéral non retrouvé** dans le CSS/JSX lu pour cette version — à confirmer lors d'un prochain passage avant de le citer comme garantie de conformité. Le texte du pied de navigation est désormais implémenté (`ExplorerLayout.jsx` `.explorer-footer`).

---

## Sources de vérité (à relire avant toute modification de ce document)

- DA préliminaire (structure, ton, table de contraste, couleurs de vote) : artifact Claude [d48b7554-0af3-45bd-904e-94367577ff4a](https://claude.ai/code/artifact/d48b7554-0af3-45bd-904e-94367577ff4a)
- Couleurs/typo racine : `web/UI_finale/src/index.css`
- Couleurs de vote/issue et les six règles de lecture communes : `web/UI_finale/src/utils/lecture.js` (`VOTE_STYLE`/`OUTCOME_COLOR`, #326), rendues par `src/components/Lecture.jsx`
- Règles de lecture propres à la fiche de groupe : `web/UI_finale/src/utils/groupe.js` (#329)
- Règles de lecture propres à la fiche candidat : `web/UI_finale/src/utils/profilCandidat.js` (#328), rendues par `src/components/CandidateProfile.jsx` — la trame en sept emplacements, la colormap de la frise (teinte = institution, motif = position) et les trois situations d'une année de vote
- Motif de fond, layout : `web/UI_finale/src/styles/shell.css`, `ExplorerLayout.css`
- Composants : `web/UI_finale/src/components/*.css`
- Cotes exactes du logo : `web/old/logo-propositions/exports/empreinte-lockup-2lignes-specs.md`
- Métadonnées PWA/SEO : `web/UI_finale/index.html`
- Règles éditoriales que la DA sert : `AGENTS.md §2`, mémoire [[ligne-editoriale-empreinte-politique]]
