<a id="libelle-chef-du-gouvernement-au-feminin-658"></a>
# Le libellé d'organe du chef du gouvernement s'accorde en genre, la qualité jamais (#658) (2026-08-31)

**Contexte** : `/gouvernements/BORNE` affichait « Premier ministre : Non
renseigné » alors qu'Élisabeth Borne figure dans les `membres[]` de sa propre
fiche. Son mandat `MINISTERE`, dans `pivot_data/profiles/elisabeth-borne.pivot.json` :

| Champ | Valeur | Origine dans AMO30 |
| --- | --- | --- |
| `label` | **« Première ministre »** | `organe.libelle` de `PO791580` |
| `fonction` | « Premier ministre » | `infosQualite.libQualite` du mandat |
| période | 2022-05-17 → 2024-01-09 | `dateDebut`/`dateFin` |

`build_premier_ministre` exige le **cumul** des deux (#474). La qualité passait ;
le libellé était comparé par `!=` à la constante `"Premier ministre"` — égalité
stricte, sans même la normalisation typographique appliquée à la qualité trois
lignes plus bas. **Les deux champs viennent d'endroits différents de la source
et ne s'accordent pas en genre.**

## Le balayage : ce qui s'accorde, et ce qui ne s'accorde pas

Relevé le 2026-08-31 sur `.cache/acteurs_historique_an/acteurs_historique.zip`
(3 117 fiches acteur), sur les **1 162 mandats `typeOrgane == "MINISTERE"`**,
en rejouant l'extraction de `candidate_profile._build_acteur_mandats_index`.

`libQualite` porte **9 valeurs distinctes, toutes au masculin** :

| `libQualite` | Mandats | Personnes | Classée aujourd'hui |
| --- | ---: | ---: | --- |
| `en mission` | 396 | 290 | non ministérielle |
| `Ministre` | 343 | 161 | ministérielle |
| `Secrétaire d'État` | 218 | 114 | ministérielle |
| `Ministre délégué` | 146 | 100 | ministérielle |
| `Ministre d'État, ministre` | 19 | 10 | ministérielle |
| `Premier ministre` | 17 | 11 | ministérielle |
| `Garde des sceaux, ministre de la justice` | 16 | 8 | ministérielle |
| **`Haut-commissaire`** | **4** | **2** | **inconnue** |
| `Ministre d'État, Garde des Sceaux, ministre de la justice` | 3 | 3 | ministérielle |

La question ouverte par l'issue — « une **ministre déléguée** est-elle
reconnue ? » — a donc une réponse mesurée : **oui**, parce que la source ne
l'écrit jamais au féminin. `FONCTIONS_MINISTERIELLES_OBSERVEES` n'a manqué
aucune forme féminine, pour la raison qu'il n'y en a pas.

Le genre se joue sur le **libellé d'organe**, et là il est bien présent : onze
libellés `MINISTERE` de l'archive portent « la Première ministre », dont un
seul est celui du chef du gouvernement — l'organe `PO791580`. Les dix autres
sont des maroquins **auprès de** Matignon (« Ministère auprès de la Première
ministre, chargé des relations avec le Parlement », « Secrétariat d'État auprès
de la Première ministre, chargé de la mer »…), qui ne doivent surtout pas être
confondus avec lui.

### Combien de membres sont manqués aujourd'hui

Deux populations, à ne pas confondre.

| Population | Mesure | Manqués |
| --- | --- | ---: |
| Les 260 mandats `MINISTERE` des **481 profils publiés** | 8 qualités rencontrées, **toutes classées** | **0** |
| Les 1 162 mandats `MINISTERE` de **l'archive AMO30** | 1 qualité non classée (`Haut-commissaire`) | 4 mandats, 2 personnes |
| Les **10 fiches de gouvernement publiées** | libellé de chef non reconnu | 1 (`BORNE`) |

Les deux personnes de `Haut-commissaire` (Martin Hirsch 2007-2010, Jean-Paul
Delevoye 2019) n'ont **pas** de profil pivot publié : la lacune est réelle dans
la source mais sans effet sur le corpus publié. Elle n'est pas comblée ici — la
classer est une vérification humaine, le geste de maintenance que
`FONCTIONS_MINISTERIELLES_OBSERVEES` décrit lui-même, pas un ajout d'office.

## Décision : une liste fermée de libellés, pas une règle de genre

`LABEL_PORTEFEUILLE_PREMIER_MINISTRE` (scalaire) devient
`LABELS_PORTEFEUILLE_PREMIER_MINISTRE_OBSERVES` (tuple relu et daté), comparé
après normalisation typographique :

```python
LABELS_PORTEFEUILLE_PREMIER_MINISTRE_OBSERVES = ("Premier ministre", "Première ministre")
```

C'est le patron déjà employé par `FONCTIONS_MINISTERIELLES_OBSERVEES` juste
au-dessus et par `correspondance_sigles_an` dans `raw_data/groupes_reels.json` :
énumérer ce qui a été vu, après vérification, plutôt que deviner.

**`_normalise_fonction` n'est pas relâchée.** Elle reste purement
typographique — casse et espaces — et le balayage donne la raison de fond de ne
pas y toucher : rapprocher les genres sur `libQualite` ne réparerait rien,
puisque `libQualite` n'a pas de féminin. La normalisation est extraite dans
`_normalise_typographique` et exposée sous **deux** noms,
`_normalise_fonction` et `_normalise_libelle_organe`, pour que l'asymétrie
entre les deux champs se lise à l'appel au lieu de se deviner. Elle gagne au
passage un effet mesurable : `\s` couvre l'espace insécable, que la source AN
pose dans certains libellés d'organe (6 mandats `MINISTERE` de l'archive).

**Le double verrou de #474 reste entier**, et il n'est pas théorique au
féminin. Le même organe `PO791580` porte, dans l'archive, un mandat de qualité
`en mission` — et ce mandat est **publié** : `yannick-chenevard` porte
« Première ministre » / `en mission` du 2023-03-17 au 2023-09-19. Il ne devient
pas chef du gouvernement, et surtout il n'**efface** pas Élisabeth Borne : deux
candidats feraient retourner `None`. C'est le dégât que #474 a nommé, ici en
version féminine, à une nuance près — Chenevard ne porte aucun mandat
d'appartenance `Gouvernement (BORNE)`, donc le cas reste latent comme celui de
David Amiel.

## Résultat mesuré

Rejeu de `build_premier_ministre` sur les 481 profils publiés (`origin/main`,
`2660ed36`) pour les 10 gouvernements configurés :

| Indicateur | Avant | Après |
| --- | --- | --- |
| `premier_ministre` renseigné | 3/10 | **4/10** |
| Warnings émis | 0 | 0 |
| Fiches modifiées | — | `BORNE` seule |

Aucune autre fiche ne bouge, dans aucun sens. `premier_ministre` étant un
scalaire surveillé par `audit_diff_profils` (`COLLECTION_GOUVERNEMENTS`), le
sens `null` → renseigné ne bloque rien ; le sens inverse serait bloqué, et
n'arrive pas ici.

## Ce que cette décision ne traite pas

Les **six** autres fiches sans chef (`BARNIER`, `BAYROU`, `CASTEX`,
`LECORNU_II`, `FILLON_2`, `FILLON_3`) relèvent de **#644** : le chef n'est pas
dans le roster, faute de profil pivot. C'est un chantier de collecte, pas de
reconnaissance — et l'interdiction de déduire le chef du **nom** du
gouvernement reste ce qui empêche de publier « Michel Barnier » sans source.

L'issue demandait aussi de **distinguer les deux « Non renseigné » à l'écran** :
« le chef n'est pas dans notre référentiel » n'est pas « nous n'avons pas su le
reconnaître ». C'est une modification d'interface (`web/`), hors du périmètre de
ce lot.

*Alternative écartée* : dériver la forme féminine par règle (accepter
« Première » partout où « Premier » est attendu). Une règle de genre est
sémantique, elle sortirait du contrat écrit de la normalisation, et elle
accepterait des libellés que personne n'a relus — alors que la liste fermée
rend visible, datée et révisable la seule forme que la source produit
réellement.

---
