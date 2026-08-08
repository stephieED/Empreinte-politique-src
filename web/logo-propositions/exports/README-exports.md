# Exports logo Empreinte v7

Palette utilisee:
- Encre: `#14151A`
- Blanc casse: `#F7F6F4`
- Jaune signal: `#DFFF00`
- Mode nuit fond: `#14151A`

Zone de protection:
- Marge minimale uniforme: **16 px** autour du logo (dans tous les SVG maitres).

Contraste WCAG (ratio):

| Cas | Premier plan | Fond | Ratio | AA 4.5:1 |
|---|---|---|---:|---|
| Main light | `#14151A` | `#F7F6F4` | 16.88:1 | PASS |
| Main dark | `#F7F6F4` | `#14151A` | 16.88:1 | PASS |
| Accent on dark | `#DFFF00` | `#14151A` | 16.01:1 | PASS |
| Accent on light | `#DFFF00` | `#F7F6F4` | 1.05:1 | FAIL |

Notes:
- Le trace principal passe AA en mode jour et nuit.
- Le jaune signal passe AA sur fond sombre.
- Le jaune signal **ne passe pas** AA sur fond clair pour texte/traits fins: reserve aux accents graphiques non textuels en mode jour.
- Favicon 16px: variante simplifiee fournie pour lisibilite (jour/nuit).

Usage recommande (resume):
- `empreinte-symbol-*.svg`: icone seule UI, boutons, app icon source.
- `empreinte-lockup-horizontal-empreinte-*.svg`: signature courte.
- `empreinte-lockup-horizontal-empreinte-politique-*.svg`: marque complete (hero/header/OG source).
- `empreinte-lockup-vertical-empreinte-politique-*.svg`: formats carres/avatars visuels.
- `*-mono.svg`: impression une encre/fonds contraints sans jaune.
- `empreinte-symbol-themable.svg` + lockups `*-themable.svg`: adaptation dynamique via `currentColor` / variables CSS.
- `empreinte-favicon.svg`: favicon themable via `prefers-color-scheme`.
- `empreinte-favicon-light.ico` et `empreinte-favicon-dark.ico`: fallback multi-resolution 16/32/48.
- `empreinte-app-icon-192-*.png`, `empreinte-app-icon-512-*.png`: PWA manifest.
- `apple-touch-icon.png` (light par defaut) + variantes `apple-touch-icon-light.png` et `apple-touch-icon-dark.png`.
- `empreinte-open-graph-1200x630-light.png`: partage social par defaut.
- `empreinte-avatar-400-*.png`: avatar carre.
- `empreinte-lockup-horizontal-empreinte-politique-light.pdf`: print/vector partenaires.
