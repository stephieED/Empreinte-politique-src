#!/usr/bin/env python3
"""
lignee_profile.py — Compose la fiche d'une LIGNÉE depuis ses maillons (#836).

## Ce qui s'agrège, et ce qui se recalcule

Trois régimes, et c'est toute la difficulté du lot. Mesuré sur la lignée
socialiste (`NG:15 → SOC:15 → SOC:16 → SOC:17`), corpus du 11/09/2026 :

| Champ | Somme des maillons | Union réelle | Régime |
| --- | ---: | ---: | --- |
| `membres` | 170 | **96** | union sur `membre_id` |
| `cohesion_votes` | 20 524 | — | union sur `scrutin_id` |
| `amendements_agreges` | 88 709 | — | **recalcul depuis les profils** |
| `tags_thematiques_agreges` | — | — | **recalcul depuis les profils** |

Un membre présent sous trois maillons y est compté trois fois. Les deux
derniers champs ne se dédoublonnent **pas** au niveau des fiches : un
amendement cosigné par deux membres compte une fois dans chaque maillon, et
rien dans les fiches ne permet de savoir que c'est le même. Il faut repasser par
`profiles[].amendements`, ce que fait `group_profile`.

## Ce qui ne s'agrège PAS, et qui est recopié

`position_politique` est publiée **par législature** par l'Assemblée (#686) :
elle ne se réunit pas. Un groupe peut être qualifié autrement d'une législature
à l'autre, et écraser ces qualifications en une seule serait produire un
jugement que personne n'a porté (§2 règle 1). Chaque maillon garde la sienne,
recopiée dans `maillons[]`.

`effectif` et `periode` sont des plages par fiche pour la même raison. La lignée
porte sa propre `periode` — de la première borne à la dernière — et un
`effectif.cumul_historique` qui est le cardinal de l'union des membres, jamais
une somme.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional

from schema_lignee import make_empty_profil_lignee


def ordonner_maillons(
    fiches: dict[str, dict[str, Any]], lignee: Iterable[str]
) -> list[str]:
    """Les `groupe_id` d'une lignée, du plus ancien au plus récent.

    L'ordre vient de `succede_a` — B succède à A, donc A précède B — et non des
    dates : une fiche peut ne pas porter de `periode.debut` quand aucune de ses
    appartenances n'est datée, et la chaîne, elle, est toujours déclarée.

    Un cycle dans les déclarations est refusé plutôt que parcouru : mieux vaut
    une lignée manquante qu'une lignée qui boucle en silence.
    """
    membres = [g for g in lignee if g in fiches]
    precede: dict[str, set[str]] = {
        g: {s for s in _predecesseurs(fiches[g]) if s in membres} for g in membres
    }
    ordonnes: list[str] = []
    restants = dict(precede)
    while restants:
        libres = sorted(g for g, p in restants.items() if not (p - set(ordonnes)))
        if not libres:
            raise ValueError(
                "cycle dans `succede_a` pour la lignée "
                f"{sorted(restants)} : une lignée qui boucle n'est pas une lignée."
            )
        ordonnes.extend(libres)
        for g in libres:
            restants.pop(g)
    return ordonnes


def _predecesseurs(fiche: dict[str, Any]) -> list[str]:
    return [
        bloc.get("groupe_id")
        for bloc in (fiche.get("succede_a") or [])
        if isinstance(bloc, dict) and bloc.get("groupe_id")
    ]


def _union_membres(fiches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """L'union des membres sur `membre_id`, bornes élargies au passage.

    Un membre présent sous plusieurs maillons n'apparaît qu'une fois, et ses
    bornes couvrent toute sa présence dans la lignée. Ses `periodes[]` (#809)
    sont concaténées : deux maillons décrivent deux tranches distinctes, jamais
    la même.
    """
    par_id: dict[str, dict[str, Any]] = {}
    for fiche in fiches:
        for membre in fiche.get("membres") or []:
            mid = membre.get("membre_id")
            if not mid:
                continue
            connu = par_id.get(mid)
            if connu is None:
                par_id[mid] = {
                    "membre_id": mid,
                    "nom": membre.get("nom"),
                    "debut_dans_lignee": membre.get("debut_dans_groupe"),
                    "fin_dans_lignee": membre.get("fin_dans_groupe"),
                    "maillons": [fiche.get("groupe_id")],
                }
                if membre.get("periodes"):
                    par_id[mid]["periodes"] = list(membre["periodes"])
                continue
            connu["maillons"].append(fiche.get("groupe_id"))
            debut = membre.get("debut_dans_groupe")
            if debut and (not connu["debut_dans_lignee"] or debut < connu["debut_dans_lignee"]):
                connu["debut_dans_lignee"] = debut
            fin = membre.get("fin_dans_groupe")
            # `None` l'emporte : une appartenance ouverte ne se referme pas
            # parce qu'un maillon antérieur, lui, s'est terminé (#526).
            if connu["fin_dans_lignee"] is not None:
                connu["fin_dans_lignee"] = None if fin is None else max(connu["fin_dans_lignee"], fin)
            if membre.get("periodes"):
                connu.setdefault("periodes", []).extend(membre["periodes"])
    for membre in par_id.values():
        if membre.get("periodes"):
            membre["periodes"] = sorted(
                membre["periodes"], key=lambda p: (p.get("debut") or "")
            )
    return sorted(par_id.values(), key=lambda m: m["membre_id"])


def _union_cohesion(fiches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Les scrutins de cohésion, unis sur `scrutin_id`.

    Les maillons **ne sont pas disjoints** : la session UI a mesuré 4 104
    doublons sur la lignée socialiste, 20 524 entrées pour une union plus
    petite. Un scrutin vu par deux maillons est le même scrutin.

    Le premier vu l'emporte, et l'ordre des maillons étant chronologique, c'est
    le plus ancien — celui de la fiche sous laquelle le vote a eu lieu.
    """
    par_scrutin: dict[Any, dict[str, Any]] = {}
    sans_id: list[dict[str, Any]] = []
    for fiche in fiches:
        for vote in fiche.get("cohesion_votes") or []:
            sid = vote.get("scrutin_id")
            if not sid:
                sans_id.append(vote)
                continue
            par_scrutin.setdefault(sid, vote)
    return list(par_scrutin.values()) + sans_id


def _fusion_mandats(fiches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Les mandats agrégés, fusionnés sur `(categorie, label)`.

    Les compteurs de membres ne se somment pas : un membre présent sous deux
    maillons compterait deux fois. C'est l'**union de leurs `membres[]`** qui
    fait foi, et le compteur en découle.
    """
    par_cle: dict[tuple, dict[str, Any]] = {}
    for fiche in fiches:
        for entree in fiche.get("mandats_agreges") or []:
            cle = (entree.get("categorie"), entree.get("label"))
            connu = par_cle.get(cle)
            if connu is None:
                connu = dict(entree)
                connu["membres"] = list(entree.get("membres") or [])
                par_cle[cle] = connu
                continue
            connus = {m.get("membre_id") if isinstance(m, dict) else m
                      for m in connu["membres"]}
            for m in entree.get("membres") or []:
                mid = m.get("membre_id") if isinstance(m, dict) else m
                if mid not in connus:
                    connu["membres"].append(m)
                    connus.add(mid)
    for entree in par_cle.values():
        for compteur in ("nb_membres_a_la_date_de_reference",
                         "nb_membres_cumul_historique"):
            if compteur in entree:
                # Recomputé sur l'union, jamais sommé.
                entree[compteur] = len(entree["membres"])
    return sorted(
        par_cle.values(),
        key=lambda e: (-len(e.get("membres") or []), str(e.get("label") or "")),
    )


def _periode_de_la_lignee(fiches: list[dict[str, Any]]) -> dict[str, Optional[str]]:
    debuts = [
        (f.get("periode") or {}).get("debut") for f in fiches
        if (f.get("periode") or {}).get("debut")
    ]
    fins = [(f.get("periode") or {}).get("fin") for f in fiches]
    return {
        "debut": min(debuts) if debuts else None,
        # Une fin absente sur un maillon veut dire « encore ouverte » : elle
        # l'emporte sur toutes les autres.
        "fin": None if any(f is None for f in fins) or not fins else max(fins),
    }


def _union_sources(fiches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Les sources, dédoublonnées sur `(type, url)` — comme la fiche de groupe."""
    vues: set[tuple] = set()
    sources: list[dict[str, Any]] = []
    for fiche in fiches:
        for source in fiche.get("sources") or []:
            cle = (source.get("type") or "", source.get("url") or "")
            if cle not in vues:
                vues.add(cle)
                sources.append(source)
    return sources


def composer_lignee(
    lignee_id: str,
    lignee_nom: str,
    chambre: str,
    fiches_ordonnees: list[dict[str, Any]],
    agregats_recalcules: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """La fiche de lignée, depuis ses maillons **déjà ordonnés**.

    `agregats_recalcules` porte `tags_thematiques_agreges` et
    `amendements_agreges`, que l'appelant obtient en repassant par les profils
    des membres — ils ne se dédoublonnent pas au niveau des fiches. Sans eux,
    les deux champs restent **vides** plutôt que faux : une somme de maillons y
    compterait un amendement cosigné autant de fois qu'il a de signataires
    répartis sur la lignée.
    """
    profil = make_empty_profil_lignee(lignee_id, lignee_nom, chambre)
    profil["maillons"] = [
        {
            "groupe_id": f.get("groupe_id"),
            "groupe_sigle": f.get("groupe_sigle"),
            "groupe_nom": f.get("groupe_nom"),
            "legislature": f.get("legislature"),
            "fichier": f"groupe-{str(f.get('groupe_id') or '').replace(':', '-')}.json",
            "periode": f.get("periode"),
            # Recopiée, jamais réunie : l'AN qualifie par législature (#686).
            "position_politique": f.get("position_politique"),
        }
        for f in fiches_ordonnees
    ]
    membres = _union_membres(fiches_ordonnees)
    profil["membres"] = membres
    profil["effectif"] = {"cumul_historique": len(membres)}
    profil["periode"] = _periode_de_la_lignee(fiches_ordonnees)
    profil["cohesion_votes"] = _union_cohesion(fiches_ordonnees)
    profil["mandats_agreges"] = _fusion_mandats(fiches_ordonnees)
    profil["sources"] = _union_sources(fiches_ordonnees)
    if agregats_recalcules:
        for champ in ("tags_thematiques_agreges", "amendements_agreges"):
            if champ in agregats_recalcules:
                profil[champ] = agregats_recalcules[champ]
    return profil


# ---------------------------------------------------------------------------
# Les deux agrégats qui se recalculent, et pourquoi ils ne se somment pas
# ---------------------------------------------------------------------------

def recalculer_agregats(
    profils_par_maillon: list[tuple[Optional[str], list[dict[str, Any]]]],
    amendements_index: Any = None,
) -> dict[str, Any]:
    """`tags_thematiques_agreges` et `amendements_agreges` d'une lignée.

    ## Pourquoi on ne peut pas sommer les maillons

    Un amendement cosigné par deux membres compte **une fois dans chaque
    maillon** où ils siègent, et rien dans les fiches ne dit que c'est le même :
    la somme des maillons de la lignée socialiste donne 88 709 amendements, un
    chiffre qui ne veut rien dire. Il faut repasser par
    `profiles[].amendements`, où l'`amendement_id` permet la déduplication
    (#643).

    ## Pourquoi on ne peut pas non plus ignorer les législatures

    Chaque maillon est apparié à **sa** législature, et le filtre de #821/#825
    s'applique maillon par maillon. Agréger la lignée « sans filtre » ferait
    revenir le défaut que ces deux lots viennent de corriger : `LR-16`
    publiait 159 274 amendements dont 20 % seulement déposés sous la XVIe.

    Un membre présent sous trois maillons est donc lu trois fois — une par
    législature — et ses amendements dédupliqués par le cumul **partagé**, qui
    est ce qui rend le compte en amendements distincts et non en signatures.

    ## `amendements_index` n'est pas optionnel en pratique

    Une entrée d'`amendements[]` ne porte qu'un `amendement_id` depuis #431 :
    son `sort` et son `type_deposant` vivent dans l'index partagé. Sans index,
    `contribution_amendements` ne résout rien et le compte sort à **0** —
    vérifié, 0 au lieu de 88 709 signatures sur la lignée socialiste. L'appelant
    doit donc charger l'index, comme `group_profile` le fait pour une fiche de
    groupe ; ne pas le passer est un mode de test, pas un mode de production.
    """
    from group_profile import (  # noqa: PLC0415 — import tardif : group_profile est lourd
        CumulAmendementsDistincts,
        _aggregate_amendements,
        aggregate_tags_thematiques,
    )

    cumul = CumulAmendementsDistincts()
    tags_par_membre: dict[str, set[str]] = {}

    for legislature, profils in profils_par_maillon:
        # Un tag porté par le même membre sous deux maillons ne compte qu'une
        # fois : c'est la PERSONNE qui porte l'étiquette, pas la fiche. D'où le
        # relevé par membre, et `nb_membres_porteurs` reconstruit sur l'union.
        for profil in profils:
            from group_profile import contribution_amendements  # noqa: PLC0415
            contribution_amendements(
                profil.get("amendements"), amendements_index, cumul, legislature
            )
            for tag in aggregate_tags_thematiques([profil], legislature=legislature).tags:
                tags_par_membre.setdefault(tag["tag"], set()).add(profil.get("id"))

    n_membres = len({p.get("id") for _, ps in profils_par_maillon for p in ps})
    tags = sorted(
        (
            {
                "tag": tag,
                "nb_membres_porteurs": len(porteurs),
                "poids_relatif": round(len(porteurs) / n_membres, 4) if n_membres else 0.0,
            }
            for tag, porteurs in tags_par_membre.items()
            if porteurs
        ),
        key=lambda e: (-e["nb_membres_porteurs"], e["tag"]),
    )
    total, par_type = cumul.compter()
    total["par_type_deposant"] = par_type
    total["nb_amendements_sans_identifiant"] = cumul.nb_sans_identifiant
    return {
        "tags_thematiques_agreges": tags,
        "amendements_agreges": total,
    }
