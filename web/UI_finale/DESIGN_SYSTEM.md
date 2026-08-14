# Design system — Empreinte politique (UI_finale)

Ce document formalise la direction artistique effectivement implémentée dans `web/UI_finale`. Il est écrit à partir du code source (`src/index.css`, `src/styles/shell.css`, `src/components/*.css`, `index.html`) — il ne décrit rien qui ne soit déjà en production. C'est la première version de ce document ; avant lui, aucun design system centralisé n'existait pour cette UI (le `README.md` du dossier n'en tient pas lieu, malgré les apparences).

`docs/design_intent.md` documente des pistes visuelles explorées pour d'anciennes générations d'interface (`web/v4` à `web/v7` : cartographie, géologie, archéologie, architecture). Ces pistes sont **obsolètes et non retenues** — `web/UI_finale` n'en reprend aucune. Ne pas s'y référer pour la DA actuelle.

---

## 1. Principes directeurs

- **Éditorial, pas institutionnel-terne, pas startup-flashy.** Beaucoup de blanc, cartes nettes, un seul accent vif utilisé avec parcimonie.
- **Neutralité politique dans la forme autant que dans le fond.** Aucune couleur assimilable à un parti (pas de bleu-blanc-rouge). Le seul accent chromatique fort (`--accent`) est une couleur qui n'appartient à aucun code politique existant — choix délibéré.
- **La rigueur se voit.** Les éléments de preuve/traçabilité (badges "vérifié", ratios num/dénom, notes de couverture) ont un traitement visuel aussi soigné que les données elles-mêmes : ce ne sont pas des mentions légales reléguées en petit gris, mais des éléments de confiance mis en scène (badge sur fond accent, cartouche caveat au survol).
- **Densité maîtrisée.** Beaucoup d'information (votes, amendements, mandats) tenue lisible par une grille de cartes régulière plutôt que par des tableaux denses.

---

## 2. Couleurs

Définies comme custom properties CSS dans `src/index.css` (`:root`). Un seul mode existe (`color-scheme: light` — pas de dark mode implémenté, confirmé par le commentaire `index.html` : *"Favicons (light only — pas de prefers-color-scheme)"*).

| Token | Valeur | Usage |
|---|---|---|
| `--bg` | `#f7f6f4` | Fond de page (ivoire cassé) |
| `--ink` | `#17141f` | Texte principal (quasi-noir, teinte violette) |
| `--dark` | `#14151a` | Fonds sombres (bandeaux, avatars, tags actifs) — aussi `theme-color` PWA |
| `--accent` | `#dfff00` | Couleur d'accent unique — chartreuse électrique. Réservée aux éléments de confiance/action : badge "vérifié", tab active, focus ring, avatar actif |
| `--muted` | `#8b8794` | Texte secondaire, légendes, métadonnées |
| `--border` | `#f0eeeb` | Séparateurs discrets |
| `--border-strong` | `#e7e4df` | Séparateurs plus marqués (ex. sous-titres de section) |
| `--card` | `#ffffff` | Fond des cartes |

**Couleurs hors tokens racine, utilisées ponctuellement dans les composants** (à faire remonter en token si elles se répètent encore) :
- `#efedea` — fond de la piste des tabs (`.tabs`)
- `#c9c4be` — bordure des badges de statut "ancien" (`.gp-member-status-ancien`)
- `#ebe9e5` / `#f5f3ef` — dégradé de shimmer des états de chargement (skeleton)

**Règle d'usage de l'accent** : `--accent` n'est jamais un fond de grande surface. Il sert exclusivement à : badge de statut vérifié, onglet actif, avatar/chip actif, anneau de focus clavier. C'est un signal, pas une décoration.

**Ombres** : toutes les `box-shadow` du système utilisent la même teinte de base `rgba(20, 15, 40, …)` (un noir-violet, proche de `--ink`/`--dark`), seule l'opacité et l'étalement varient selon l'élévation — voir §5.

---

## 3. Typographie

- **Police unique : Manrope**, chargée via Google Fonts dans `index.html` (`weights 400;500;600;700;800`), avec fallback `system-ui, sans-serif`. Aucune autre famille (pas de serif, pas de monospace) dans `web/UI_finale`.
- Déclarée globalement sur `body` (`src/index.css`) — titres compris, pas de police dédiée aux titres.

**Échelle observée dans le code** (aucune échelle typographique n'est formalisée en tokens — voici les tailles réellement utilisées, à traiter comme l'échelle de fait) :

| Taille | Poids | Usage |
|---|---|---|
| 34px / 32px | 800 | `h1` de bandeau (fiche candidat / fiche groupe) |
| 26px | 800 | Valeur KPI (`.kpi-value`) |
| 16px | 800 | Titre de section (`.gp-section-title`) |
| 14–15px | 400–700 | Corps de texte, titres de carte |
| 13px | 600–800 | Labels de tabs, breadcrumb, titres de flyout |
| 11–12px | 700 | Labels de métadonnées, badges, légendes, texte en majuscules |

**Micro-règles typographiques constantes** :
- Chiffres (KPI, compteurs) : `font-variant-numeric: tabular-nums` systématique — évite le tremblement visuel des colonnes de chiffres.
- Grands nombres/titres : `letter-spacing` légèrement négatif (`-0.01em` à `-0.02em`) pour compenser la largeur de Manrope en gras.
- Petits labels en majuscules (`text-transform: uppercase`) : `letter-spacing` positif (`+0.02em` à `+0.04em`) — lisibilité en capitales.
- Poids : 600 = interactif/label, 700 = emphase/donnée, 800 = titre/valeur clé. Jamais de 400 sur un élément interactif.

---

## 4. Logo & identité de marque

Spécifié précisément dans `web/old/logo-propositions/exports/empreinte-lockup-2lignes-specs.md` (référence de cotes qui fait autorité) et implémenté dans `src/components/Brand.jsx` / `Brand.css`.

- **Lockup deux lignes** : "Empreinte" (48px, graisse 800, tracking -0.07em) au-dessus de "POLITIQUE" (12px, graisse 700, tracking +0.07em), texte vectorisé (outlines) dans le SVG final. Delta de baseline L1→L2 : 20px.
- **Symbole seul** : recalé à 51px de hauteur (échelle ×1.9318 depuis la bbox réelle de 26.4px), aligné optiquement au centre vertical du bloc texte en version horizontale.
- **Version de référence** : `empreinte-lockup-horizontal-empreinte-politique-light.svg`, viewBox `13.52 -0.73 329.27 87.26`, marge de protection 16px sur chaque bord.
- **Seuil de lisibilité** : la légende "POLITIQUE" devient illisible sous ~50px de hauteur affichée → le lockup complet est rendu à 58px dans l'en-tête (`.brand-lockup`, `Brand.css`).
- **Bascule responsive** : sous 480px de large, le lockup complet disparaît au profit du symbole seul (40×40px, `.brand-symbol`) — géré en CSS pur (`@media max-width: 480px`), pas en JS.
- **Favicon** : symbole seul uniquement — le lockup n'est jamais recommandé en petite taille (note explicite dans le fichier de specs).
- **Zone de marque** : bandeau de 80px de haut, séparateur bas `1px solid var(--border)`, aligné sur la marge horizontale de la nav (40px, héritée de `.explorer-bars`, pas de padding propre).
- Déclinaisons disponibles (non toutes utilisées dans `UI_finale` actuellement, mais exportées) : horizontal / vertical / 2-lignes, light / dark, couleur / mono, dans `web/old/logo-propositions/exports/`.

---

## 5. Espacement, rayons, élévation

Pas de grille d'espacement formalisée en tokens — mais un vocabulaire de valeurs cohérent en usage :

**Espacements** (gap/padding/margin) : `4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 28, 32, 40, 64` px. Base implicite ≈ 2px, la majorité des usages tombant sur des multiples de 2 entre 8 et 24. Marge de page : `padding: 32px 40px 64px` (`.main` / `.gp-main`).

**Rayons de bordure** — trois familles, jamais mélangées :

| Rayon | Usage |
|---|---|
| `2px` | Éléments quasi-carrés (`.banner-tag`) |
| `4–6px` | Barres de progression, jauges (`.compare-bar-track`, `.outcome-bar`) |
| `14–18px` | Cartes (14px = carte compacte type liste ; 18px = carte principale type KPI/vote/texte) |
| `50%` | Cercles (avatars, dots de statut) |
| `999px` | Pilules (tabs, chips, badges, tags thématiques) — arrondi complet |

**Élévation** — toutes les ombres partagent la teinte `rgba(20, 15, 40, …)`, seule l'intensité change avec le niveau :

| Niveau | Valeur | Usage |
|---|---|---|
| Repos, carte de liste | `0 1px 8px rgba(20,15,40,0.05)` | `.shelf-item`, `.gp-member-row` |
| Repos, carte principale | `0 2px 12px rgba(20,15,40,0.06)` | `.kpi-card`, `.vote-card`, `.textes-card` |
| Repos, chip | `0 2px 8px rgba(20,15,40,0.06)` | `.cb-chip`, `.gb-chip` |
| Bandeau | `0 2px 16px rgba(20,15,40,0.07)` | `.banner`, `.gp-coverage-card` |
| Hover carte | `0 6px 20px rgba(20,15,40,0.14)` | `.kpi-card:hover` |
| Hover chip | `0 4px 14px rgba(20,15,40,0.1)` | `.cb-chip:hover` |

Pas d'ombre portée décorative au-delà de ces niveaux : la surface d'une carte au repos reste quasiment plate, l'ombre ne s'affirme qu'à l'interaction.

**Forme signature — bandeau à coin coupé.** Les deux bandeaux d'en-tête (`.banner` fiche candidat, `.gp-banner` fiche groupe) partagent un `clip-path: polygon(0 0, calc(100% - 28px) 0, 100% 28px, 100% 100%, 0 100%)` : un coin supérieur droit tranché à 28px. C'est la seule rupture de forme rectangulaire du système — à traiter comme un élément de signature graphique récurrent, pas comme un détail isolé.

---

## 6. Motif de fond

`src/styles/shell.css` (`.app-shell`) : un motif SVG de cercles concentriques (16 ellipses emboîtées, `stroke rgb(20,21,26)`, `stroke-width 1.5`, `opacity 0.055`), ancré en bas à gauche de la coque applicative. Évocation directe du nom "Empreinte" (empreinte digitale). Toujours en filigrane quasi imperceptible (opacité 5,5 %) — ne doit jamais devenir un élément décoratif visible au premier plan ni être dupliqué ailleurs sans cette même retenue d'opacité.

---

## 7. Mouvement & interaction

- **Durée unique de transition : 0.15s**, sur `box-shadow` (cartes, chips) et `opacity` (caveat au survol). Pas d'easing custom, pas de transition sur `transform`.
- **Focus clavier : `outline: 2px solid var(--accent); outline-offset: 2px`** — identique sur tous les éléments interactifs (tabs, chips, pills, kpi-card). C'est la seule utilisation d'accent en anneau plutôt qu'en fond ; à ne jamais remplacer par un `outline: none`.
- **Survol carte KPI** : un cartouche `.kpi-caveat` (fond `--dark`, texte blanc) apparaît en overlay plein cadre par transition d'opacité — sert à afficher la nuance méthodologique (ex. limites du chiffre) sans alourdir l'affichage par défaut.
- **Chargement** : squelettes shimmer (`linear-gradient` animé 1.4s, `#ebe9e5` / `#f5f3ef`) sur les barres de candidats/groupes pendant le fetch — jamais de spinner.
- **Navigation sticky** : `.explorer-bars` reste collée en haut (`position: sticky`) avec fond semi-transparent (`rgba(247,246,244,0.85)`) et `backdrop-filter: blur(6px)` — effet verre dépoli au défilement.
- **Défilement horizontal** : barres de candidats/groupes en drag-scroll (`ScrollRow` + `useDragScroll`), scrollbar masquée (`scrollbar-width: none`), curseur `grab`/`grabbing`.

---

## 8. Composants — vocabulaire visuel

| Composant | Forme | Règle |
|---|---|---|
| **Carte KPI** | 18px radius, ombre niveau 2 | Valeur en 26px/800 + label 12px muted ; caveat au survol |
| **Carte vote/texte** | 18px radius, ombre niveau 2 | Dot coloré de position + badge accent "vérifié" en pied de carte |
| **Bandeau d'en-tête** | Coin coupé 28px, fond `--dark`, texte blanc | Un seul par page, contient le tag de statut + h1 |
| **Tag/pilule thématique** | `999px`, bordure `1.5px solid var(--dark)` | Devient fond plein `--dark` à l'état actif |
| **Onglets (`.tabs`)** | Piste `#efedea` en pilule, boutons `999px` | Actif = fond `--accent`, texte `--dark` |
| **Chip candidat/groupe** | `999px`, ombre niveau chip | Avatar rond `--dark`→`--accent` si actif |
| **Badge "vérifié"** | `999px`, fond `--accent`, texte `--dark`, 11px/700 | Seul badge doré du système — réservé à la traçabilité |
| **Barre de comparaison/répartition** | Piste `--border` 4-6px radius, remplissage coloré | Toujours accompagnée du couple numérateur/dénominateur affiché en texte, jamais du seul pourcentage |
| **Avatar** | Cercle `--dark` fond, initiales blanches | `--accent` uniquement si sélectionné/actif |
| **Statut membre (actif/ancien)** | Pilule 999px, 10px/700 uppercase | Actif = fond plein `--dark` ; ancien = contour `#c9c4be`, texte muted (jamais de rouge/vert de statut) |

---

## 9. Accessibilité

- Contraste : texte `--ink` (#17141f) sur `--bg` (#f7f6f4) et `--card` (#ffffff) — contraste élevé par construction.
- Anneau de focus visible et cohérent partout (§7) — ne jamais le supprimer sur un élément cliquable.
- Le logo est un lien unique cliquable ; les images du lockup sont décoratives (`alt=""`), le nom accessible porte sur le lien (`aria-label`).
- Aucune information n'est portée par la couleur seule sans redondance texte (ex. badge vérifié = couleur + texte "vérifié", jamais un simple point coloré).

---

## 10. Ce que ce document ne couvre pas encore

- Pas de dark mode (le système est mono-thème, volontairement).
- Pas de système d'icônes formalisé (les indicateurs actuels sont des formes géométriques simples — dots, cercles — pas une bibliothèque d'icônes).
- Pas d'échelle typographique ni d'espacement déclarés en tokens CSS — ce document formalise l'usage *de fait*, une prochaine itération pourrait les transformer en variables `--space-*` / `--text-*` dans `index.css`.
- Comportement responsive au-delà du breakpoint 480px (logo) non audité ici.

---

## Sources de vérité (à relire avant toute modification de ce document)

- Couleurs/typo racine : `web/UI_finale/src/index.css`
- Motif de fond : `web/UI_finale/src/styles/shell.css`
- Composants : `web/UI_finale/src/components/*.css`
- Cotes exactes du logo : `web/old/logo-propositions/exports/empreinte-lockup-2lignes-specs.md`
- Déclinaisons de logo disponibles : `web/old/logo-propositions/exports/`
- Métadonnées PWA/SEO (favicon, theme-color, OG) : `web/UI_finale/index.html`
- Règles éditoriales que la DA doit servir (traçabilité, pas de score) : `AGENTS.md §2`
