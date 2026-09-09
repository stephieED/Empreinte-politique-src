# LaREM XVe entre : la condition posée par #779 est levée (#779)

`2026-09-09`

## Contexte

#779 avait scindé LaREM XVe du lot de #777 **sur son coût de stockage** : 227
profils à collecter, ~3,4 Go, pour un seul candidat bénéficiaire. La condition de
réouverture était explicite — « une fois #691 traitée, les 227 profils coûteront
une fraction de ces 3,4 Go ».

#691 est traitée. Le run `34344178203` a retiré **854 fichiers de tranches** et
`raw_data/profiles` est passé de **9,7 à 4,6 Gio** : les amendements des
législatures closes ne sont plus recopiés, ils se dérivent de
`raw_data/amendements_an_figes/`. Un membre de la XVe ne coûte plus que son
socle.

## Ce qui a été relu, et non recopié

L'organe a été relu dans l'index AMO30 le 09/09/2026, pas repris de l'issue :

| Champ | Valeur du référentiel |
| --- | --- |
| `uid` | `PO730964` |
| `libelleAbrev` | `LAREM` (`LaREM` en `libelleAbrege`) |
| `libelle` | La République en Marche |
| bornes | 2017-06-27 → 2022-06-21 |
| `positionPolitique` | **Majoritaire** → `majorite` |
| mandats | 367 |
| **acteurs distincts** | **343** |
| après filtrage des transits | **343** — aucun transit sur cet organe |

L'absence de mandat de transit distingue cet organe des `NI` de la 16e et de la
17e, où le filtre écarte 576 et 577 mandats.

## Un chiffre de #779 était périmé

L'issue annonçait **227 profils à collecter**. Re-mesuré ce jour : **131 des 343
membres ont déjà une entrée** dans `raw_data/correspondance_acteurs_an.json`, il
en reste donc **212**. Le corpus a grossi entre l'écriture de l'issue et sa
reprise — c'est le même effet que #777 avait constaté sur #706, dont le
périmètre avait triplé pendant l'attente.

## Ce que la fiche apportera, et à qui

Gabriel Attal, et lui seul. Ses votes, datés via `pivot_data/scrutins.json` :

| Législature | Ses votes | Fiche de groupe |
| --- | ---: | --- |
| XVIIe | 1 766 | `groupe-AN-EPR-17` |
| **XVe** | **268** | **celle-ci** |
| XVIe | 1 | `groupe-AN-REN-16`, inutile pour lui |

Mais le bénéfice ne s'arrête pas à lui, et c'est ce que #777 n'avait pas nommé :
les cinq fiches XVe publiées — `FI`, `NG`, `SOC`, `EDS`, `GDR` — sont **toutes
d'opposition**. Le site publie la XVe législature **sans sa majorité**.

## Ce qui n'a pas été fait, et pourquoi

**Publier la fiche avec les 131 membres déjà couverts.** Le taux de
participation se calcule sur les membres *ayant un profil* : il afficherait un
dénominateur de 131 pour un groupe de 343 — un ratio dont le dénominateur ne
nomme pas sa population, ce que §2 règle 7 interdit. Rien ne le bloquait
techniquement (le seuil du portail est à 1 membre, soft) ; c'est l'éditorial qui
l'interdit.

Les 212 membres sans entrée reçoivent un slug fabriqué au roster (#527, #708 §3)
puis leur entrée dérivée à la passe hors ligne (#715) — le chemin qu'ont pris
les cinq groupes XVe de #777, dont `FI` publie ses **17 membres sur 17**.

## Le portail est rouge jusqu'au run

`AN:LAREM:15: fichier manquant` est un **échec dur** du bloc 4/4 tant que
`pivot_data/groupes/groupe-AN-LAREM-15.json` n'existe pas. C'est le régime
normal d'une publication configurée : dans le run, les profils de groupe sont
produits **avant** le portail, qui voit donc la fiche. En local, entre le merge
et le run, le portail refuse. Les sept groupes de #777 sont passés par là.
