<a id="purge-doublons-herites-729"></a>
# 185 doublons hérités retirés : l'outil existait, il n'avait jamais été relancé (#729) (2026-09-04)

## 1. Ce que le lot fait, et ce qu'il n'écrit pas

**Aucun code.** `src/purge_mandats_dupliques.py` (#387) couvrait déjà ce cas ;
personne ne l'avait relancé depuis que le corpus a été régénéré. Le lot est
l'exécution de `--apply`, et la trace de ce qu'elle a retiré.

| Simulation puis application, 04/09/2026 | |
| --- | ---: |
| Profils analysés | 641 |
| **Profils modifiés** | **13** |
| **Doublons retirés** | **185** |
| Ignorés (pas d'`acteurRef`) | 4 |
| Ignorés (extraction AN vide ou en échec) | **9** |

## 2. Le critère est celui de #387, et il est plus sûr que celui que j'avais proposé

L'instruction de #729 détectait les **libellés rangés sous deux catégories** dans
le corpus — 22 libellés, dont 9 arbitrables, **18 entrées**. C'est ce chiffre qui
a été soumis à l'arbitrage, et il était trop étroit.

Le critère de #387 ne regarde pas le corpus mais **le profil** : une entrée
héritée n'est retirée que si le **même profil** porte déjà son équivalent AN, sur
un organe dont le libellé normalisé correspond et dont la période recouvre la
sienne. Il en trouve **185**, et il ne peut pas se tromper dans le sens qui
coûte : sans jumeau présent, il ne retire rien.

**Le chiffre soumis était donc faux, dans le sens le moins grave** — la mesure
plus sûre en trouve dix fois plus, et chacune est un doublon vérifié.

## 3. Ce que « doublon » veut dire ici, et pourquoi une vérification naïve crie au loup

Les deux référentiels ne nomment pas les organes de la même façon : **l'AN nomme
par le thème nu, NosDéputés préfixait la nature.**

| | Catégorie | `type` | Libellé | Période |
| --- | --- | --- | --- | --- |
| **Retirée** | `commission` | `membre` | `Groupe d'études polices municipales` | 2023-05-12 → 2024-06-09 |
| **Survit** | `groupe_etudes` | `Membre` | `Polices municipales` | 2023-05-11 → 2024-06-09 |

Même organe, bonne catégorie, un jour d'écart à l'ouverture.

Vérifié après application, sur les 185 entrées relues depuis `git show HEAD:` :
comparées **libellé brut à libellé brut**, 155 des 185 semblent avoir perdu leur
organe ; comparées avec `_normalize_label`, celle de l'outil, **0**. La première
mesure était la mienne, et elle était naïve : c'est exactement le point que le
docstring de #387 annonce — « un appariement par libellé exact ne rapproche aucun
doublon ». Le noter ici évite qu'on le redécouvre en paniquant.

## 4. Ce qui reste, et qui n'est pas de la même nature

**Les 41 entrées des 13 libellés non arbitrables ne sont pas touchées**, et ne
peuvent pas l'être : leurs **deux** catégories sont héritées — `Groupe d'études
fin de vie` publié à la fois en `commission` et en `groupe_amitie`, et douze
autres du même genre. NosDéputés se contredisait lui-même, la source n'est plus
interrogée, et aucun référentiel vivant ne peut arbitrer. Elles restent
**marquées** par `categorie_source` (#718) sans être accusées. #729 reste ouverte
pour elles.

**Les 9 profils ignorés faute d'extraction AN** ne sont pas un refus de purger :
c'est une absence de référence. Ils peuvent porter des doublons que personne ne
voit, et cela n'a pas été instruit — déclaré ici plutôt que passé sous silence.

**#730 n'est pas couvert**, et la mesure le confirme : `gabriel-attal` et
`yael-braun-pivet` rendent **0** doublon, parce qu'aucun organe AMO30 nommé
`Gouvernement` n'existe pour servir de jumeau. Ce lot-là reste à écrire.

## 5. Ce que ce lot avait faux, et qui a été corrigé

Ce paragraphe disait : « le lot ne touche que `raw_data/profiles/` … il faut un
run, qui bloquera au contrôle de perte ». **Les deux affirmations étaient
fausses**, et le run du 04/09 (`33872886135`) l'a montré.

**Retirer une entrée du profil BRUT ne la retire pas du PIVOT.**
`merge_pivot_profile` est additif exactement comme la fusion brute : l'ancienne
entrée publiée gagne, et la purge ne l'atteint jamais. Mesuré après ce run :
`alexandra-martin` porte **54 mandats au brut et 65 au pivot**.

Et le contrôle de perte n'a donc **rien bloqué** : il n'y avait rien à perdre.
C'est la même mécanique qui avait rendu « aucune perte bloquante » à #710 le
02/09, pour la même raison, et je ne l'ai pas reconnue dans l'autre sens.

**La règle qui manquait, et qu'il faut lire à côté de §3a** : la fusion additive
protège les deux étages. Une correction qui **ajoute** un champ passe par un
report nommé au brut ; une correction qui **retire** une entrée doit être
appliquée **aux deux corpus**, sinon elle n'est nulle part.

`purge_mandats_dupliques.py` et `reprise_mandats_gouvernementaux.py` acceptent
donc `--profiles-dir pivot_data/profiles`. Au pivot, l'`acteurRef` ne vient plus
du profil — il n'y figure pas — mais de la **table de correspondance** (#525),
qui est l'autorité du dépôt sur « ce slug, cet acteur AN ».

Appliqué : **193 entrées retirées sur 19 profils pivot** — 185 doublons de ce lot
et 8 mandats ministériels de #730. Le prochain run, lui, bloquera pour de bon.
