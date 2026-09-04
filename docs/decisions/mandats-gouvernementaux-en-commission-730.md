<a id="mandats-gouvernementaux-en-commission-730"></a>
# Le référentiel type l'organe, il n'y a rien à interpréter (#730) (2026-09-04)

## 1. Le constat

Huit mandats ministériels étaient publiés avec `categorie: "commission"` — tous
sur l'organe `Gouvernement`, avec pour `fonction` un intitulé de portefeuille.
Ils gonflaient le bloc « Commissions » de la fiche candidat, sur 7 profils
(1 `candidat_declare`, 6 `roster_groupe`) et 2 fiches de groupe.

**Aucun chemin de collecte actuel ne les produit** : `GOUVERNEMENT` est
volontairement absent de `_TYPE_ORGANE_TO_CATEGORIE`, l'appartenance étant
collectée par l'autre chemin en `fonction_gouvernementale`. Ce sont des entrées
gelées que la fusion additive conserve — la famille de #718 et #729.

## 2. Deux critères écartés par la mesure, pas par principe

**Le croisement (profil × période) seul — celui qui avait été retenu à
l'arbitrage — capture 1 036 mandats, pas 8.** Un ministre garde ses commissions,
ses groupes d'amitié, ses groupes d'études : les compter comme ministériels
serait un contresens. Mesuré avant d'écrire une ligne de code.

**Le vocabulaire ministériel de #474 (`FONCTIONS_MINISTERIELLES`) en capture 0.**
Il est fait pour les `libQualite` courts d'AMO30 — « Ministre », « Secrétaire
d'État » — quand ces entrées portent l'intitulé complet du portefeuille
(« Ministre des outre-mer »). `_normalise_fonction` est **purement
typographique, sans troncature ni rapprochement par préfixe**, et c'est
délibéré : le rapprocher par préfixe serait la classification par libellé que
#639, #718 et #729 écartent toutes les trois.

## 3. Le critère retenu : le typage du référentiel

L'index d'organes AN porte, pour chaque organe, son `type`. `Gouvernement` y est
typé **`GOUVERNEMENT`**, et c'est le **seul** libellé du référentiel dans ce cas.
On ne classe donc rien par ressemblance : on lit ce que la source déclare de
l'organe.

Le croisement de période garde un rôle, et c'est un **verrou** : une entrée n'est
reconnue que si une appartenance gouvernementale **publiée** de cette personne la
recoupe. Détection par le référentiel, confirmation par le croisement — les deux,
jamais l'un ou l'autre. Mesuré : **8 entrées par chacun des deux tests**.

## 4. Le sort de chaque entrée, décidé par ce que le profil porte déjà

| Situation | Geste | Nombre |
| --- | --- | ---: |
| Période **déjà couverte** par un `fonction_gouvernementale` du profil | **retirée** — le fait n'est perdu nulle part | **6** |
| Période **non couverte** | **requalifiée** en `fonction_gouvernementale` | **2** |

Les 2 sont `yael-braun-pivet` (24/06 → 27/06/2022) et `damien-abad`
(24/06 → 05/07/2022). Les retirer aurait effacé du profil une période
ministérielle réelle.

**Rien n'est fabriqué** : la période, le libellé et la fonction restent ceux que
l'entrée portait. Seule la catégorie change, ou l'entrée disparaît au profit
d'une autre qui dit la même chose.

### Le recouvrement, pas le chevauchement

« Déjà couverte » exige un recouvrement **complet**. Un chevauchement suffirait à
faire retirer une entrée dont une partie de la période n'est dite nulle part —
deux intervalles qui se touchent d'un jour décrivent des faits différents. Écrit
en premier avec un simple chevauchement, le lot rendait **8 retraits et 0
requalification** ; le bon test rend **6 et 2**.

## 5. Trois garde-fous

- **`--apply` explicite**, simulation par défaut.
- **Un index d'organes absent ou illisible ne reconnaît rien** et la reprise ne
  modifie rien : un critère qui ne peut pas s'établir ne se devine pas
  (§2 règle 5). C'est aussi ce qui empêche un repli silencieux sur le libellé.
- **L'appariement se fait sur le slug** (`membres[].membre_id`), jamais sur le
  nom d'affichage : un profil brut ne porte pas de champ `nom`, et apparier deux
  corpus sur un nom est ce que #487 et #668 ont fait payer — un *nom d'usage*
  change, un identifiant non.

Idempotent : une seconde exécution ne trouve plus rien.

## 6. Ce que ce lot avait faux, et qui a été corrigé

Ce paragraphe annonçait qu'un run suffirait et qu'il bloquerait au contrôle de
perte. **Les deux étaient faux** : `merge_pivot_profile` est additif comme la
fusion brute, donc retirer une entrée du profil brut ne la retire pas du pivot,
et le contrôle n'a rien eu à bloquer. Détail et règle générale dans
[[purge-doublons-herites-729]] §5.

La reprise s'applique donc **aux deux étages**
(`--profiles-dir pivot_data/profiles`). Au pivot, le sort des 8 entrées diffère —
**8 retirées, 0 requalifiée** au lieu de 6 et 2 — et c'est correct : les deux
requalifications faites au brut sont arrivées au pivot comme entrées **neuves**,
si bien que les 8 anciennes y ont toutes leur jumeau.

Vérifié entrée par entrée après application : **les 8 périodes ministérielles
restent couvertes**, `yael-braun-pivet` et `damien-abad` compris, par une entrée
`fonction_gouvernementale` du même profil.

## 7. Vérification

`tests/test_reprise_mandats_gouvernementaux_730.py` — 18 tests : le typage du
référentiel, l'index absent ou illisible qui ne reconnaît rien, les entrées
qu'on ne touche jamais, les deux gestes et leur condition, le recouvrement
distingué du chevauchement sur quatre cas, l'appariement par slug, et
l'idempotence.

Trois mutations vérifiées échouantes : le recouvrement ramené au chevauchement,
le typage du référentiel retiré du critère, la requalification supprimée.

Suite complète : **3 802 tests, 0 échec**.
