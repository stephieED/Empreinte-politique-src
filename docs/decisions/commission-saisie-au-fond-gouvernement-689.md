<a id="commission-saisie-au-fond-gouvernement-689"></a>
# Un texte de gouvernement porte sa matière, ou dit pourquoi il ne la porte pas (#689) (2026-09-04)

## 1. Le besoin, et pourquoi il n'était pas servi

Lire les lois d'un gouvernement **par matière** suppose une matière. Les
`textes[]` des 10 fiches publiées portaient `dossier_id`, `titre`, `statut`,
`chambre_depot_initial`, `date_depot`, `date_dernier_evenement`, `sort_49_3`,
`initiateurs`, `source_url` — **rien qui dise de quoi le texte traite**.

Inventer une taxonomie à partir des titres était exclu d'avance : c'est
l'acte éditorial que `AGENTS.md` §2 règle 1 interdit, et la clé tirée d'un
libellé que #639 et #672 ont déjà fait payer deux fois.

**L'Assemblée en fournit une, et nous la publions déjà** : elle renvoie chaque
dossier à une **commission saisie au fond**. `pivot_data/commissions_dossiers.json`
la porte — 6 024 dossiers — depuis le commit de données `5de11422` (02/09/2026).
La ligne d'`AGENTS.md` affirmant que ce fichier « n'a jamais été produit » et que
l'empreinte thématique en dépendant « est donc inerte » était périmée ; elle est
corrigée par ce lot.

## 2. La décision

Chaque entrée de `textes[]` publie **`commission_saisie_au_fond`**
(`{organe_ref, sigle, nom}` ou `null`), jointe sur **`dossier_id`** — jamais sur
le titre (`regrouper-nest-pas-joindre-639`).

Quand elle vaut `null`, l'entrée porte **`commission_non_resolue.motif`**, d'un
vocabulaire fermé de trois valeurs. **Les trois ne se réparent pas au même
endroit, et c'est tout l'objet de les distinguer** :

| Motif | Ce que c'est | Se répare |
| --- | --- | --- |
| `depot_senat` | l'index est celui de l'**AN**, le texte est déposé au Sénat | **jamais** — c'est le périmètre (#528) |
| `absente_de_l_index` | dépôt AN, dossier absent de l'index | un trou de l'index AN |
| `index_indisponible` | l'index n'a pas été fourni au run | une panne du run |

Les confondre ferait lire une **décision éditoriale** comme un défaut, ou une
**panne** comme un constat. C'est la leçon de #726, où un audit rendait 62 705
lignes parce qu'il lisait un champ déplacé, et celle de #510, où un index vide
passait pour un résultat.

**Le schéma refuse la contradiction** : un texte ne peut pas porter à la fois sa
commission et le motif de son absence — ce serait dire « voici sa commission » et
« voici pourquoi elle manque ».

## 3. La mesure, et ce qu'elle établit

Sur les **725 textes** des 10 fiches, régénérées avec l'index :

| | Textes |
| --- | ---: |
| Commission résolue | **551 (76,0 %)** |
| Non résolue, motif `depot_senat` | **174** |
| Non résolue, motif `absente_de_l_index` | **0** |
| Erreurs de schéma | **0** |

Et le fait qui rend l'absence lisible plutôt qu'inquiétante :

| Chambre de dépôt | Résolus |
| --- | ---: |
| **AN** | **381 / 381 — 100 %** |
| Sénat | 170 / 344 |

**Les 174 non résolus sont à 100 % des dépôts au Sénat.** Ce n'est pas un trou de
collecte : un texte déposé au Sénat est examiné par une commission sénatoriale,
que le référentiel de l'AN ne porte pas, et le Sénat est hors périmètre depuis
#528. Une absence dont la cause est connue **se déclare**, elle ne se comble pas
(§2 règle 5).

Le `absente_de_l_index` à **0** est un **compteur-témoin** : non nul, il dira que
l'index a cessé de couvrir ce qu'il couvrait. Sans lui, ce cas serait rangé sous
`depot_senat` et disparaîtrait.

La matière, telle qu'elle se lira : Affaires étrangères 169, Lois 118, Finances
73, Affaires sociales 68, Affaires économiques 44, Affaires culturelles et
éducation 30, Développement durable 23, Défense 7.

## 4. Trois choix de mise en œuvre

- **La projection est explicite.** L'index porte aussi un `type` d'organe
  (`COMPER`), qui décrit le référentiel et non le texte : recopier l'entrée telle
  quelle ferait entrer dans la fiche un champ dont personne n'a décidé qu'il y
  avait sa place.
- **L'index est chargé UNE fois pour les dix fiches**, dans `main()`. Le relire
  par gouvernement serait le coût que #392, #403 et #467 ont déjà payé trois fois
  au même endroit — 1,2 Mo et 6 024 dossiers.
- **Le défaut de la fonction est `None`, pas un chemin du dépôt.** C'est la CLI
  qui porte `--commissions-dossiers` : une valeur par défaut de fonction pointant
  dans l'arbre est le piège d'`AGENTS.md` §3b, mesuré sur les tests par #721. Un
  index **vide** vaut un index absent, sinon « le fichier manquait » se lirait
  « aucun texte n'a de commission ».

## 5. Ce que le lot ne fait pas

- **Il ne touche pas la vue.** La fiche de gouvernement lit désormais une clé au
  lieu de refaire la jointure, mais c'est à qui tient `web/` de s'en servir.
- **Il ne publie pas de thème**, il publie une **commission**. Une commission
  saisie au fond est un fait institutionnel sourcé ; l'appeler « thème » serait
  une interprétation, et le libellé publié reste celui de l'Assemblée.
- **Il ne change rien aux profils** ni aux fiches de groupe : `textes_portes[]`
  d'un profil n'est pas touché.
- **Rien n'est publié tant qu'un run n'a pas régénéré les fiches.** Les mesures
  ci-dessus viennent d'une régénération hors dépôt.

## 6. Vérification

`tests/test_commission_au_fond_gouvernement_689.py` — 14 tests : la résolution,
les trois motifs distingués un par un, l'invariant « exactement un des deux »,
la projection qui ne republie pas le `type`, et le schéma qui refuse un motif
inventé comme la contradiction.

Trois mutations vérifiées échouantes : les deux motifs confondus, l'index absent
rendu muet, la contradiction autorisée.

Suite complète : **3 749 tests, 0 échec**.
