# Trois fiches, et six lignées qui remontent enfin (#815, lot 2)

`2026-09-10`

## Contexte

La propriétaire demande une **continuité par groupe entre la XVe et la XVIIe**.
Le lot 1 a rendu les identifiants et les successions capables de l'exprimer ;
celui-ci déclare ce qui manquait pour qu'elle existe.

## Ce que le corpus déclarait, et ce qui manquait

Avant ce lot, une seule lignée remontait à trois maillons, et deux fiches de la
XVIe portaient un prédécesseur. Après :

| Lignée | État |
| --- | --- |
| `LR-15 → LR-16 → DR-17` | **fiche `LR-15` créée** |
| `GDR-15 → GDR-16 → GDR-17` | **fiche `GDR-17` créée** |
| `ECOLO-16 → ECOS-17` | **fiche `ECOS-17` créée** |
| `LAREM-15 → REN-16 → EPR-17` | fiches existantes, **lien manquant déclaré** |
| `FI-15 → LFI-16 → LFI-17` | fiches existantes, **lien manquant déclaré** |
| `NG-15 → SOC-15 → SOC-16 → SOC-17` | fiches existantes, **lien manquant déclaré** |
| `RN-16 → RN-17` | **s'arrête là, et c'est un fait** |

**Les trois liens manquants ne coûtaient rien.** `REN-16`, `LFI-16` et `SOC-16`
avaient déjà leur prédécesseur publié ; personne n'avait déclaré le lien. Les
ajouter ferme trois lignées sans collecter une seule personne.

**`RN` n'a pas de prédécesseur XVe, et ce n'est pas un trou** : le Rassemblement
national n'atteignait pas le seuil de constitution d'un groupe à la XVe. Le
champ reste `None` et ne prétend rien (§2 règle 5).

## Les trois organes, relus

Relevés dans l'index AMO30 le 10/09/2026, jamais repris d'une mesure antérieure :

| Fiche | Organe | `libelleAbrev` | Période | Acteurs | Avec slug | À collecter |
| --- | --- | --- | --- | ---: | ---: | ---: |
| `LR-15` | `PO730934` | `LR` | 2017-06-27 → 2022-06-21 | 120 | 53 | **67** |
| `GDR-17` | `PO845514` | `GDR` | 2024-07-18 → en cours | 18 | 15 | **3** |
| `ECOS-17` | `PO845439` | `ECOS` | 2024-07-18 → en cours | 38 | 24 | **14** |

**84 personnes à collecter**, et non les 116 annoncés la veille : la table de
correspondance a grossi entre-temps. Aucun mandat de transit sur les trois
organes.

## Deux erreurs de mesure, corrigées avant d'écrire

**`est_mandat_de_transit(fin, constitution)` prend la date de constitution du
groupe en second argument**, pas la fin du mandat. Appelée à l'envers, elle
écartait **les 120 acteurs** de `LR-15` — un groupe entier réduit à zéro sans
qu'aucune exception ne se lève. Le chiffre absurde l'a trahie ; une valeur
plausible ne l'aurait pas fait.

**`sigles_an` porte le `libelleAbrev`, pas le `libelleAbrege`.** Pour l'organe
`PO845439` ce sont deux valeurs différentes — `ECOS` et `EcoS` — et j'avais
retenu la seconde. Le roster ne trouvait alors **aucun membre** : il cherche les
organes dont `sigle` (c'est-à-dire `libelleAbrev`) figure dans `sigles_an`. Là
encore c'est un test qui l'a montré, en mesurant 0 contre 38 attendus.

Les deux défauts ont la même forme : une valeur voisine, un résultat nul, et
aucune erreur levée.

## Ce que les tests figeaient

Trois tests encodaient l'état d'avant comme un invariant, et disent maintenant
le nouveau :

- « les fiches de la XVIe ne succèdent à rien » — c'était vrai quand la XVe
  n'était pas couverte. Il vérifie désormais les cinq successions et l'unique
  absence légitime, `RN` ;
- « les cinq groupes de la XVIIe », deux fois. Le second compte désormais **le
  total de la table** au lieu d'une constante : déclarer un groupe de plus ne
  doit pas faire échouer un test qui ne parle pas de lui.

## Effet attendu, et ce qui reste à vérifier

Rien n'est publié tant qu'un run n'a pas tourné : `effectif_publie` reste `null`
sur les trois entrées, et le portail comptera trois fiches manquantes jusque-là.
C'est le régime normal d'une publication configurée, déjà connu de LaREM XVe.

**Ce que je n'ai pas mesuré** : le coût du run avec 84 profils de plus. LaREM XVe
en a ajouté 212 sans que `merge-and-pivot` dépasse 25 minutes sur 60 ; 84 est
plus petit, mais la projection n'est pas une mesure.

## Ce que ce lot ne fait pas

Quatre lignées restent incomplètes, et leur coût est chiffré dans #815 :
**MoDem** (4 fiches, 91 personnes sans profil — la seule totalement absente),
**Horizons** (2 fiches, 45), **LIOT** (3 fiches, 50), **UDR** (3 fiches, 16, et
c'est une **scission** que `succede_a` seul ne sait pas écrire).

`historique_noms` reste vide : c'est lui qui porterait les renommages **à
l'intérieur** d'une législature — `UMP` → `Les Républicains` en XIVe — et il
sera indispensable pour remonter plus haut que la XVe.
