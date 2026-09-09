<a id="contact-et-comptes-publics-328"></a>

# Le contact et les comptes publics : les mentions légales, et un rappel discret (#328) (2026-09-09)

## Le contexte

Trois demandes de la propriétaire, le 09/09/2026 : l'adresse de contact devient
`contact@empreinte-politique.fr`, et les deux comptes publics — LinkedIn et X —
sont ajoutés.

## La décision

**Les mentions légales font foi.** C'est la page que la LCEN désigne, et c'est
là que l'adresse de l'éditeur doit se trouver — avec les deux comptes, sous leur
propre intitulé « Comptes publics » plutôt qu'accrochés à la ligne de contact :
un compte n'est pas une adresse de contact éditeur au sens de l'article 6-III.

**Le pied de page les rappelle, en discret.** Une adresse qu'il faut aller
chercher dans une page légale est une adresse qu'on n'écrit pas. Les cinq
entrées prennent la teinte des métadonnées, comme les deux liens qui s'y
trouvaient déjà, et passent à la ligne plutôt que de pousser le pied hors de la
colonne sur un écran étroit.

## Une seule adresse dans le dépôt, et une citation qui reste datée

`docs/decisions/licences.md` cite le texte des mentions légales dans son état du
14/08/2026, ancienne adresse comprise. **Cette citation n'est pas réécrite** :
c'est un enregistrement, et réécrire un enregistrement pour qu'il colle au
présent est ce qui rend les décisions illisibles a posteriori.

Elle porte en revanche une note qui dit où se trouve le texte qui fait foi. Une
adresse périmée qu'on peut recopier de bonne foi est pire qu'une adresse
absente — c'est le même principe que « une documentation qui affirme un fait
périmé est pire qu'une documentation absente ».

Un test tient les deux bouts : plus une seule occurrence de l'ancienne adresse
dans `web/UI_finale/src/`, et l'ancienne **toujours présente** dans la citation
datée, accompagnée de la nouvelle.

## Le détail qui n'est pas cosmétique

`target="_blank"` sans `rel="noopener"` laisse la page ouverte piloter celle
qu'elle a quittée. Les trois liens sortants le portent, et un test le vérifie
partout où `_blank` apparaît dans ces deux fichiers.
