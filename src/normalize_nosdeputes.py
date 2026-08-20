#!/usr/bin/env python3
"""
normalize_nosdeputes.py — Adaptateur NosDéputés/NosSénateurs → schéma pivot v1.

Convertit un profil JSON produit par candidate_profile.py (format brut
NosDéputés.fr / NosSénateurs.fr) vers le schéma pivot commun défini dans
schema_pivot.py.

Ce module est volontairement découplé de la collecte : il ne fait aucun
appel réseau et ne connaît pas le mécanisme de téléchargement.

Usage :
    from normalize_nosdeputes import normalize_nosdeputes
    pivot = normalize_nosdeputes(raw_profile)

    # Enrichissement optionnel depuis candidats.json :
    pivot["parti"] = "La France Insoumise"
"""

import time
from typing import Any, Optional

from schema_pivot import (
    CHAMBRE_COLLECTE_VERS_PIVOT,
    SCHEMA_VERSION,
    appliquer_chambres,
    make_empty_profil,
)
from amendements_index import cle_amendement
from scrutins_index import ScrutinsIndex, cle_scrutin
from scrutins_legislature import legislature_du_calendrier

# Correspondance chambre (clé du profil brut) → valeur normalisée du pivot.
# Vit dans `schema_pivot` depuis #494 : `lire_chambres()` doit appliquer la même
# tolérance côté lecture, et deux tables auraient pu diverger sans que rien ne le
# dise. L'alias local garde les appels du module inchangés.
_CHAMBRE_MAP: dict[str, str] = CHAMBRE_COLLECTE_VERS_PIVOT

# Type de source selon la chambre.
_SOURCE_TYPE_MAP: dict[str, str] = {
    "deputes": "nosdeputes",
    "senateurs": "nossenateurs",
}

# Préfixe de warning publié dans `meta.warnings` (#492). Même convention que
# candidate_profile.WARNING_PREFIX_* : le texte avant le premier ':' est le
# *type* agrégé par audit_pivot_dataset.compute_agregation_warnings.
WARNING_PREFIX_CHAMBRE_MANDAT_NON_RESOLUE = "chambre de mandat électif non résolue"

# Préfixe de warning publié dans `meta.warnings` (#493) quand `chambres` n'est
# pas entièrement étayée par les mandats : une chambre y figure au seul titre de
# la collecte, ou un `mandat_electif` reste sans chambre. Cette liste-là est
# utilisable, pas vérifiée, et ce warning est exactement ce qui l'empêche d'être
# trompeuse. Son décompte agrégé par
# `audit_pivot_dataset.compute_agregation_warnings` est la mesure de la
# migration : il tombe à zéro quand `chambre` peut être retiré.
WARNING_PREFIX_CHAMBRES_NON_CORROBOREE = "chambres du profil non corroborée"


def _first(*values: Any) -> Any:
    """Retourne la première valeur non-None parmi les arguments."""
    for v in values:
        if v is not None:
            return v
    return None


# ---------------------------------------------------------------------------
# Normaliseurs de sections individuelles
# ---------------------------------------------------------------------------

def _normalize_vote(
    v: dict[str, Any], scrutins_index: Optional[ScrutinsIndex] = None
) -> dict[str, Any]:
    """Normalise un vote brut vers le **mapping** pivot (#432).

    Un scrutin est identique pour tous ses votants : son méta (`texte`, `date`,
    `sort`…) vit une seule fois dans `pivot_data/scrutins.json`, et le profil ne
    garde que ce qui est propre au membre. Mesuré : 179,8 → 18,0 Mo de mapping
    plus 8,7 Mo de liste partagée, soit −85 %.

    `groupe_au_moment_du_vote` n'est écrit que s'il est renseigné. Son absence
    signifie « non renseigné », exactement comme `null` — exception documentée
    à la convention « missing = null » d'AGENTS.md §4, et elle seule : le champ
    n'est aujourd'hui jamais peuplé (0 sur 398 085) et l'écrire quand même
    coûtait **12,1 Mo de `null`, soit 40 % du mapping**.

    Résolution de l'identifiant, dans cet ordre :

    1. **l'index** — il porte la résolution de corpus (jointure sur un jumeau
       étiqueté, `scrutins_legislature`), la seule qui voie au-delà du profil ;
    2. **la législature du vote lui-même**, quand il la porte ;
    3. **le calendrier des législatures**, dérivation locale et déterministe.

    Si rien ne résout, le vote n'est **ni supprimé ni doté d'une clé inventée** :
    il conserve son enregistrement complet sous `scrutin_non_resolu`, avec
    `scrutin_id` à `null`. Une donnée qu'on ne sait pas normaliser reste une
    donnée (AGENTS.md §2.5) — et elle est visible plutôt que muette.
    """
    numero = str(v["numero_scrutin"]) if v.get("numero_scrutin") is not None else None
    legislature = str(v["legislature"]) if v.get("legislature") is not None else None

    scrutin_id = scrutins_index.identifiant_de_vote(v) if scrutins_index is not None else None
    if scrutin_id is None and numero is not None:
        legislature_resolue = legislature or legislature_du_calendrier(v.get("date"))
        if legislature_resolue:
            scrutin_id = cle_scrutin(legislature_resolue, numero)

    vote: dict[str, Any] = {
        "scrutin_id": scrutin_id,
        "position": v.get("position") or None,
    }
    if v.get("groupe_au_moment_du_vote"):
        vote["groupe_au_moment_du_vote"] = v["groupe_au_moment_du_vote"]

    if scrutin_id is None:
        vote["scrutin_non_resolu"] = {
            "numero_scrutin": numero,
            "legislature": legislature,
            "date": v.get("date"),
            "texte": v.get("texte") or v.get("titre") or None,
            "sort": v.get("sort"),
            "type_scrutin": v.get("type_scrutin"),
            "type_vote": v.get("type_vote") or "vote_texte",
            "texte_lie_id": v.get("texte_lie_id"),
            "source_url": v.get("source_url") or v.get("url_source"),
        }
    return vote


def _normalize_mandat(m: dict[str, Any]) -> dict[str, Any]:
    """Normalise un mandat/responsabilité brut vers le format pivot.

    `chambre` (#492) n'est portée que par les `mandat_electif`, et **lue sur le
    mandat lui-même**, jamais sur `raw_profile["chambre"]`. La distinction n'est
    pas cosmétique : la fusion additive accumule dans un même profil des mandats
    collectés lors de runs différents, donc potentiellement sous des chambres
    différentes. Mesuré sur `f5a828b` : `jean-luc-melenchon` est un profil brut
    `chambre: "senateurs"` qui porte trois `mandat_electif`, dont deux
    manifestement AN (2017-2022, groupe LFI). Reprendre la chambre du profil
    aurait donc estampillé « Sénat » deux mandats de l'Assemblée — un fait faux
    de plus, exactement ce que l'épic #486 reproche au champ de niveau profil.
    Un mandat non estampillé (collecté avant #492) reste à `null` : la chambre
    d'un mandat déjà collecté n'est pas reconstituable a posteriori, et une
    valeur par défaut est interdite (AGENTS.md §2.5).
    """
    mandat = {
        "label": m.get("label") or None,
        "categorie": m.get("categorie") or None,
        # Dans le format brut, la fonction s'appelle "type" (héritage de l'API)
        "fonction": m.get("type") or "membre",
        "debut": m.get("debut"),
        "fin": m.get("fin"),
        "actif": bool(m.get("actif")),
        "source_url": m.get("source_url"),
        "position_dans_hemicycle": m.get("position_dans_hemicycle"),
        "mode_declenchement": m.get("mode_declenchement"),
        "suspendu_pour_fonction_gouvernementale": m.get("suspendu_pour_fonction_gouvernementale"),
    }
    if mandat["categorie"] == "mandat_electif":
        chambre_brute = m.get("chambre")
        mandat["chambre"] = _CHAMBRE_MAP.get(chambre_brute) if chambre_brute else None
    return mandat


def _normalize_texte_porte(d: dict[str, Any]) -> dict[str, Any]:
    """Normalise un dossier législatif brut vers le format pivot `textes_portes`.

    NosDéputés ne distingue pas systématiquement auteur et rapporteur dans les
    dossiers. Le rôle reste donc nul quand la source ne le fournit pas : aucune
    inférence n'est faite à partir du volume d'interventions.
    """
    return {
        "titre": d.get("titre") or None,
        "role": d.get("role"),
        "type_rapport": d.get("type_rapport"),
        "stade_procedural": d.get("stade_procedural"),
        "date_min": d.get("date_min"),
        "date_max": d.get("date_max"),
        "legislature": d.get("legislature"),
        "source_url": _first(d.get("url_source"), d.get("url_institution")),
    }


def _normalize_intervention(i: dict[str, Any]) -> dict[str, Any]:
    """Normalise une intervention brute vers le format pivot."""
    result: dict[str, Any] = {
        "date": _first(i.get("date"), i.get("created_at")),
        "type_detail": i.get("type_detail"),
        "sujet": i.get("sujet"),
        "texte": i.get("texte"),
        "fonction": i.get("fonction"),
        "format": i.get("format"),
        "mots_cles": list(i.get("mots_cles") or []),
        "source_url": _first(i.get("url_detail"), i.get("url")),
        # Champs pivot officiels — renseignés depuis les données Syceron (débats AN)
        # quand disponibles, null sinon (interventions NosDéputés scraping).
        # La présence de seance_ref ou session_ref identifie une intervention Syceron.
        "theme_officiel": i.get("sujet") if i.get("seance_ref") or i.get("session_ref") else None,
        "seance": (
            {
                "ref": i.get("seance_ref"),
                "session_ref": i.get("session_ref"),
            }
            if i.get("seance_ref")
            else None
        ),
        "dossier": (
            {"point_ordre_du_jour": i.get("point_ordre_du_jour")}
            if i.get("point_ordre_du_jour")
            else None
        ),
        "source": (
            {
                "type": "syceron",
                "url": i.get("source_url") or i.get("url"),
                "source_id": i.get("source_id"),
                "legislature": i.get("legislature"),
            }
            if i.get("seance_ref") or i.get("session_ref")
            else None
        ),
    }
    # Champs supplémentaires pour les questions parlementaires officielles (type_detail == "question").
    if i.get("type_detail") == "question":
        result["sous_type"] = i.get("sous_type")      # "QE" | "QG" | "QOSD"
        result["ministere"] = i.get("ministere")       # ministère interrogé
        result["reponse"] = i.get("reponse")           # texte de la réponse (si disponible)
        result["date_reponse"] = i.get("date_reponse") # date JO de la réponse
    return result


def _normalize_amendement(a: dict[str, Any], own_id: str) -> dict[str, Any]:
    """Normalise un amendement brut vers le **mapping** pivot (#431).

    Un amendement est identique pour tous ses signataires : `texte_vise`,
    `sort`, `date`, `type_deposant`, `premier_signataire` et surtout
    `co_signataires` vivent une seule fois dans `pivot_data/amendements/`, et le
    profil ne garde que ce qui est propre au membre — son `role_signataire`.

    Mesuré sur les 209 profils committés : 810 552 paires (membre, amendement)
    pour 207 238 amendements distincts, et **77,7 M entrées de cosignatures pour
    4,96 M distinctes** (× 15,7). C'est cette recopie qui pèse 1 083,9 Mo.

    Un amendement sans `uid` n'a pas de clé — le `numero` repart à chaque texte
    ([[amendements-cle-uid]]) — et on ne lui en invente pas : il conserve son
    enregistrement complet sous `amendement_non_resolu`, avec `amendement_id` à
    `null`. Ni supprimé, ni deviné (AGENTS.md §2.5). Zéro cas sur les données
    actuelles, dont la couverture `uid` est de 100 %.
    """
    role_signataire = a.get("role_signataire")
    amendement_id = cle_amendement(a.get("uid"))

    amendement: dict[str, Any] = {
        "amendement_id": amendement_id,
        "role_signataire": role_signataire,
    }

    if amendement_id is None:
        premier_signataire = a.get("premier_signataire")
        # Compatibilité ascendante : pour les données historiques sans rôle
        # explicite, on conserve le comportement ancien (premier_signataire =
        # élu du profil). Ne vaut que pour l'enregistrement non résolu : la
        # liste partagée, elle, ne peut porter qu'une valeur indépendante du
        # lecteur (voir amendements_index._valeur_amendement).
        if role_signataire != "cosignataire":
            premier_signataire = own_id
        amendement["amendement_non_resolu"] = {
            "texte_vise": a.get("texte_vise"),
            "sort": a.get("sort"),
            "base_juridique_irrecevabilite": a.get("base_juridique_irrecevabilite"),
            "premier_signataire": premier_signataire,
            "co_signataires": list(a.get("co_signataires") or []),
            "type_deposant": a.get("type_deposant"),
            "date": a.get("date"),
            "numero": a.get("numero"),
            "source_url": a.get("source_url"),
        }
    return amendement


# ---------------------------------------------------------------------------
# Fonction principale
# ---------------------------------------------------------------------------

def normalize_nosdeputes(
    raw_profile: dict[str, Any],
    parti: Optional[str] = None,
    provenance: str = "candidat_declare",
    scrutins_index: Optional[ScrutinsIndex] = None,
) -> dict[str, Any]:
    """Convertit un profil brut NosDéputés/NosSénateurs vers le schéma pivot v1.

    Args:
        raw_profile: dict produit par candidate_profile.build_profile().
        parti: parti politique de l'élu (optionnel ; peut être passé depuis
               candidats.json car non fourni par l'API NosDéputés).
        scrutins_index: index partagé des scrutins (#432). Porte la résolution
               de corpus de la législature — la seule qui voie au-delà du
               profil courant. Facultatif : sans lui, chaque vote se résout sur
               sa propre législature puis sur le calendrier, ce qui suffit pour
               un profil isolé mais ne peut pas exploiter un jumeau étiqueté
               vivant dans un autre fichier.
        provenance: "candidat_declare" (défaut) ou "roster_groupe" — voir
                    schema_pivot.KNOWN_PROVENANCES. Propagé tel quel vers
                    meta.provenance du profil pivot.

    Returns:
        Profil pivot dict conforme au schéma v1.
    """
    slug = raw_profile.get("slug") or ""
    chambre_raw = raw_profile.get("chambre") or ""
    # `chambre_collecte` (#493) : la chambre dont le jeu de données a répondu.
    # Elle n'est plus publiée telle quelle — elle devient le **repli** de
    # `deriver_chambres()`, qui l'ajoute toujours à `chambres` sans jamais la
    # substituer à ce que disent les mandats ni la laisser les évincer.
    # `_CHAMBRE_MAP.get(x, x or None)` laisse passer une chambre brute non mappée
    # telle quelle : elle est écartée par `deriver_chambres`, qui n'accepte comme
    # repli qu'une valeur de KNOWN_CHAMBRES.
    chambre_collecte = _CHAMBRE_MAP.get(chambre_raw, chambre_raw or None)
    source_type = _SOURCE_TYPE_MAP.get(chambre_raw, "nosdeputes")

    identite = raw_profile.get("identite") or {}
    nom = identite.get("nom_complet") or slug.replace("-", " ").title()

    # Timestamp de synchro depuis le méta du profil brut (ou maintenant si absent)
    meta_raw = raw_profile.get("meta") or {}
    synchro_sources = meta_raw.get("synchro_sources") or {}
    synchro_le = synchro_sources.get("nosdeputes")
    if "nosdeputes" not in synchro_sources:
        synchro_le = meta_raw.get("genere_le") or time.strftime("%Y-%m-%dT%H:%M:%S%z")
    # --- Profil pivot de base ---
    # L'`id` est le slug, SANS préfixe de provenance (#487, épic #486). Le slug
    # est une donnée d'entrée — le nom du fichier du profil, fixé par
    # `raw_data/candidats.json` ou par le roster —, jamais un résultat de
    # collecte. Le préfixe `nosdeputes:`/`nossenateurs:` dérivait au contraire
    # de la chambre qui avait répondu ce jour-là : entre `25f7bc7` et
    # `01ffa7f`, `jean-luc-melenchon` est passé à `nossenateurs` et
    # `stephane-mazars` à `nosdeputes` — deux bascules en sens opposés, sur des
    # carrières inchangées. Un identifiant que la météo du réseau fait varier
    # n'en est pas un.
    # `source_type` reste utilisé plus bas pour `sources[].type`, où il décrit
    # bien la provenance d'UNE source : c'est vrai, stable, et à sa place.
    profil: dict[str, Any] = make_empty_profil(slug, nom, provenance=provenance)
    # `chambre` n'est plus posée ici (#493) : elle est dérivée plus bas, une fois
    # `mandats[]` normalisé, par `deriver_chambres()` — la seule fabrique du
    # couple `chambres`/`chambre`. `chambre_collecte` n'est plus qu'une entrée de
    # cette dérivation (le repli), plus un champ publié directement.
    profil["parti"] = parti
    profil["groupe"] = identite.get("groupe_nom") or identite.get("groupe_sigle")

    # --- Sources ---
    source_url = raw_profile.get("source") or f"https://www.nosdeputes.fr/{slug}"
    sources: list[dict[str, Any]] = [
        {
            "type": source_type,
            "url": source_url,
            "synchro_le": synchro_le,
        }
    ]
    votes_source = raw_profile.get("votes_source")
    if votes_source and "assemblee-nationale" in (votes_source or "").lower():
        an_synchro = (meta_raw.get("synchro_sources") or {}).get("assemblee_nationale") or synchro_le
        sources.append({
            "type": "assemblee_nationale",
            "url": "https://data.assemblee-nationale.fr/",
            "synchro_le": an_synchro,
        })
    profil["sources"] = sources

    # --- Identité (profession/naissance/HATVP) : uniquement si au moins un champ
    # est renseigné, sinon on laisse `identite` à None (valeur par défaut). ---
    identite_champs = {
        "profession": identite.get("profession"),
        "date_naissance": identite.get("date_naissance"),
        "lieu_naissance": identite.get("lieu_naissance"),
        "num_circo": identite.get("num_circo"),
        "uri_hatvp": identite.get("uri_hatvp"),
        "source_url": identite.get("url_an_ou_senat") or source_url,
    }
    if any(v for k, v in identite_champs.items() if k != "source_url"):
        profil["identite"] = identite_champs

    # --- Sections principales ---
    profil["mandats"] = [_normalize_mandat(m) for m in (raw_profile.get("mandats") or [])]
    profil["votes"] = [_normalize_vote(v, scrutins_index) for v in (raw_profile.get("votes") or [])]
    profil["textes_portes"] = [_normalize_texte_porte(d) for d in (raw_profile.get("dossiers_legislatifs") or [])]
    profil["interventions"] = [_normalize_intervention(i) for i in (raw_profile.get("interventions") or [])]
    profil["amendements"] = [_normalize_amendement(a, profil["id"]) for a in (raw_profile.get("amendements") or [])]

    # --- chambres / chambre (#493) ---
    # Dérivées ici, APRÈS `mandats[]`, et pas avant : les deux champs sortent de
    # la même fabrique et ne peuvent donc pas se contredire. C'est la condition
    # non négociable de leur coexistence — un champ collecté à côté d'un champ
    # dérivé garderait le mensonge à côté de la vérité, en ajoutant la question
    # « lequel croire ».
    profil["chambre"] = chambre_collecte     # repli, consommé par appliquer_chambres
    derivation_chambres = appliquer_chambres(profil)

    # --- Tags thématiques bruts : source hybride — thème officiel Syceron (quand
    # disponible via `theme_officiel`) ou mots-clés scraping NosDéputés en fallback.
    # `theme_officiel` est préféré car il provient du compte rendu officiel de l'AN.
    tags: set[str] = set()
    for i in profil.get("interventions") or []:
        theme = i.get("theme_officiel")
        if theme and isinstance(theme, str):
            cleaned = theme.strip().lower()
            if cleaned:
                tags.add(cleaned)
        else:
            for kw in (i.get("mots_cles") or []):
                cleaned = kw.strip().lower()
                if cleaned:
                    tags.add(cleaned)
    profil["tags_thematiques"] = sorted(tags)

    # --- Métadonnées ---
    profil["meta"]["licence_donnees"] = meta_raw.get("licence_donnees") or ""
    profil["meta"]["warnings"] = list(meta_raw.get("warnings") or [])

    # Propagation des avertissements de synchro depuis le profil brut
    synchro_sources = meta_raw.get("synchro_sources") or {}
    if synchro_sources.get("nosdeputes") is None:
        profil["meta"]["warnings"].append(
            "synchro_sources.nosdeputes : aucune synchro réussie enregistrée dans le profil source."
        )

    # Mandats électifs dont la chambre n'est pas résolue (#492) : `null` publié,
    # jamais une valeur par défaut (§2.5). **Un seul warning par profil**, et non
    # un par mandat : le cas est uniforme et déterministe (un mandat collecté
    # avant #492 n'a pas d'estampille, et n'en aura une qu'à sa prochaine
    # collecte), et `audit_pivot_dataset.compute_agregation_warnings` agrège par
    # préfixe — un warning par mandat ferait 214 occurrences sur 207 profils
    # (mesuré sur `f5a828b`) là où une par profil dit exactement la même chose.
    # Ce n'est pas le cas de #474 (les 92 parlementaires en mission sont écartés
    # sans warning parce que leur exclusion est le comportement attendu et
    # permanent) : ici le `null` est un manque transitoire, et le compte est
    # précisément la mesure qui dit quand la migration est terminée.
    n_sans_chambre = sum(
        1 for m in profil["mandats"]
        if m.get("categorie") == "mandat_electif" and not m.get("chambre")
    )
    if n_sans_chambre:
        profil["meta"]["warnings"].append(
            f"{WARNING_PREFIX_CHAMBRE_MANDAT_NON_RESOLUE} : {n_sans_chambre} mandat(s) "
            "électif(s) sans chambre déterminée, publiés à null (#492). La chambre est "
            "estampillée à la collecte ; un mandat conservé par la fusion additive et "
            "collecté avant #492 n'en porte pas, et elle n'est pas reconstituable a "
            "posteriori — ni depuis `source_url` (jamais renseignée sur un mandat électif "
            "AN/Sénat), ni depuis la chambre du profil (la fusion additive y accumule des "
            "mandats des deux chambres)."
        )

    # `chambres` non corroborée (#493) : déclarée, jamais muette. C'est ce qui
    # sépare « utilisable » de « trompeur » — un consommateur migré tôt (#494)
    # peut distinguer une liste que les mandats étayent entièrement d'une liste
    # où la chambre de collecte figure sur sa seule parole. Un warning par
    # profil, comme celui de #492 et pour la même raison : le cas est uniforme,
    # et c'est le compte de profils qui est l'information utile.
    if not derivation_chambres.corroboree:
        profil["meta"]["warnings"].append(
            f"{WARNING_PREFIX_CHAMBRES_NON_CORROBOREE} : "
            f"chambres={derivation_chambres.chambres}, dont "
            f"{derivation_chambres.chambres_non_corroborees or 'aucune'} sans mandat "
            f"électif estampillé pour l'étayer, et "
            f"{derivation_chambres.mandats_non_estampilles} mandat(s) électif(s) "
            "encore sans chambre (#493). Une chambre non corroborée est celle de la "
            "collecte : elle dit quel jeu de données a répondu, pas où la personne a "
            "siégé — l'épic #486 a mesuré qu'elle peut être fausse dans les deux sens."
        )

    return profil
