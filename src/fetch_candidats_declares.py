#!/usr/bin/env python3
"""
fetch_candidats_declares.py — Récupère les candidats DÉCLARÉS et met à jour
`raw_data/candidats.json` (#753).

## Pourquoi ce script existe

`raw_data/candidats.json` décide de qui reçoit une fiche : c'est lui qui
dimensionne la matrice `extract-an` (un shard par candidat à slug résolvable) et
c'est sur lui que porte la PREMIÈRE passe pivot de `merge-and-pivot`. Il était
tenu **à la main**, et sa `_meta.derniere_verification` valait `2026-07-18` —
**51 jours** au 07/09/2026. Mesuré ce jour-là contre la source :

  - **19** candidats déclarés au tableau principal, **11** de plus déclarés dans
    le cadre d'une primaire, soit **30** ;
  - **13** entrées chez nous, dont **11** présentes des deux côtés ;
  - donc **19 déclarés absents** de notre fichier, et **2 entrées périmées** —
    Laurent Wauquiez (`declare`) et Jordan Bardella (`pressenti`) figurent tous
    deux sous « Candidats pressentis ayant décliné ».

Le script qui devait signaler cette dérive, `fetch_wikipedia_candidates.py`, ne
la voyait pas : il visait l'article de l'élection et non l'article des
candidatures, sa regex de titre attrapait « **Conditions de candidature** » — il
rendait « nationalité française » et « droits civiques » comme des candidats — et
sa requête Wikidata imposait une classe d'élection (`Q869519`) que l'élément
2027 ne porte pas. Il est retiré par ce lot.

## Le périmètre : tout candidat déclaré, sans filtre

« A déclaré sa candidature » est un fait, sourçable ligne à ligne. Tout autre
critère — la notoriété, le score attendu, la taille du parti — reviendrait à
arbitrer qui mérite une fiche, ce que la §2 règle 1 interdit. Les
sous-sections de primaire sont dans le périmètre : elles sont, dans la source,
des sous-sections de « Candidats déclarés ».

## Ce que la source impose, et qui n'est pas devinable

1. **La liste ne vit pas dans l'article de l'élection** mais dans l'article
   dédié aux candidatures. L'article de l'élection ne fait que la transclure.
2. **Le wikitext ne suffit pas.** Les primaires y sont transcluses
   (`{{#section-h:}}`) depuis d'autres articles : lire le wikitext du seul
   article dédié perd Mélenchon, Tondelier, Guedj et Royal. C'est le **HTML
   rendu** (`action=parse&prop=text`) qui développe les transclusions, et c'est
   la seule raison pour laquelle ce script parle HTML plutôt que wikitext.
3. **Le nom se lit dans le TEXTE de la cellule, jamais dans son premier lien.**
   Deux déclarés n'ont pas d'article — Selma Labib, Benoît Mathieu — et leur
   premier lien est celui du parti : une extraction par lien publierait
   « Nouveau Parti anticapitaliste » comme nom de candidat.
4. **La cellule d'en-tête est un empilement `<br>`** : nom, âge, parti. Trois
   parasites s'y intercalent et sont retirés avant lecture — la clé de tri de
   `{{TriNom}}` (`<span style="display:none">Arthaud, Nathalie</span>`), l'âge
   (`<span class="datasortkey">`) et les appels de note (`<sup class="reference">`,
   trois sur la seule ligne Fabien Roussel).

## Rien n'est écrit sur une collecte en échec (#511)

Le patron est celui de `generate_roster_candidats.py`, et pour la même raison :
le 20/08/2026, un `Read timed out` avait fait écrire un roster de **0 candidat**
avec un code de sortie 0. Ici, **trois anomalies bloquent l'écriture**, et
aucune n'est un seuil chiffré :

1. **la page n'a pas pu être lue** — réseau, HTTP, JSON illisible ;
2. **la section « Candidats déclarés » est introuvable** — l'article a été
   restructuré, et un titre qui bouge ne doit pas se lire comme une liste vide ;
3. **zéro candidat extrait** alors que la section existe — le filet de dernier
   recours.

Une ligne dont le nom ne se laisse pas lire ne bloque pas : elle est **comptée
et nommée** (`LIGNE_ILLISIBLE`), comme `ROSTER_SANS_SLUG` le fait des membres
sans slug (#527). Un run ne meurt pas parce qu'une ligne a changé de forme ; il
meurt quand il ne sait plus ce qu'il lit.

## L'écriture est additive, et le slug se fabrique quand un identifiant le porte

Trois interdits, tous déjà écrits ailleurs dans le dépôt :

  - **une entrée existante n'est jamais supprimée ni réécrite.** Un `slug`
    publié est immuable (#460/#470) et renommer un fichier publié est une
    suppression qu'`audit_diff_profils` bloque. La **seule** écriture sur une
    entrée existante est le comblement d'un `slug: null` — remplir un trou,
    jamais remplacer une valeur ;
  - **un déclaré qui n'est plus déclaré est SIGNALÉ, jamais modifié.** Le
    script lit la section des déclarés ; il ne peut donc pas distinguer un
    retrait d'un déplacement de section, et trancher à sa place serait inventer
    une cause (§2 règle 5) ;
  - **un slug ne se fabrique que si un identifiant externe le corrobore**
    (`--resoudre-identifiants`, #757). Sans lui, l'entrée entre avec
    `slug: null`, ce qui la tient hors de la matrice `extract-an` — donc hors
    collecte et hors publication — jusqu'à ce qu'une main tranche.

## Pourquoi le slug se fabrique ici, et ce qu'il déclenche (#757)

`slug: null` était le régime de #753, et il ne tient pas un périmètre à jour :
sans slug, pas de shard, donc pas de collecte, donc un périmètre qui n'avance
que lorsqu'une main y pense. D'ici avril 2027 la liste bougera des dizaines de
fois.

Le slug vient donc de `text_utils.slugify(nom)` — la seule fabrique de slugs du
dépôt (#487, #708) — **à condition** que `identifiants_wikidata` ait résolu un
acteur AN par identifiant externe, ou établi que la personne n'en a pas. Le nom
ne sert jamais de clé de rapprochement : voir le module, qui dit pourquoi.

**Les deux populations passent par la même chaîne** : les déclarés que le
fichier ignore, et ceux qu'il porte déjà **sans slug**. Oublier la seconde
laisserait les entrées créées avant la boucle bloquées pour toujours, ce qui est
l'immobilité que #539 a payée.

`famille_politique` et `date_declaration` restent `null` : le tableau des
déclarés ne les porte pas, et une absence se publie en absence (§2 règle 5).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Optional
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup, Tag

sys.path.insert(0, str(Path(__file__).resolve().parent))

import gha  # noqa: E402
import identifiants_wikidata as iw  # noqa: E402
from text_utils import slugify  # noqa: E402

#: L'article qui porte la liste. L'article de l'élection ne fait que la
#: transclure, et le viser rendait « Conditions de candidature » (#753).
ARTICLE = "Candidatures à l'élection présidentielle française de 2027"

#: Le titre de section qui délimite le périmètre. Ses sous-sections de primaire
#: en font partie : la lecture s'arrête au titre de niveau 2 SUIVANT.
SECTION_DECLARES = "Candidats déclarés"

API = "https://fr.wikipedia.org/w/api.php"

#: L'API MediaWiki refuse les agents anonymes et demande un contact.
HEADERS = {
    "User-Agent": (
        "EmpreintePolitique/1.0 "
        "(https://github.com/stephieED/Empreinte-politique-src) "
        "python-requests"
    )
}

TIMEOUT = 30

DEFAULT_CANDIDATS_PATH = "raw_data/candidats.json"

#: Le statut attribué à toute entrée créée ici. Le script ne lit QUE la section
#: des déclarés : il n'a aucun moyen d'écrire autre chose.
STATUT_DECLARE = "declare"

#: Préfixes d'anomalie, repris tels quels dans les annotations GitHub Actions.
ANOMALIE_PAGE = "CANDIDATS_PAGE_ILLISIBLE"
ANOMALIE_SECTION = "CANDIDATS_SECTION_INTROUVABLE"
ANOMALIE_VIDE = "CANDIDATS_AUCUN_DECLARE"
AVERTISSEMENT_LIGNE = "CANDIDATS_LIGNE_ILLISIBLE"
AVERTISSEMENT_PLUS_DECLARE = "CANDIDATS_PLUS_DECLARE"

EXIT_OK = 0
EXIT_COLLECTE_INCOMPLETE = 1
EXIT_ECART = 3


class CollecteIncomplete(Exception):
    """Une anomalie qui interdit d'écrire. Porte le message de l'annotation."""


@dataclass(frozen=True)
class CandidatDeclare:
    """Une ligne du tableau des déclarés, telle que la source la donne."""

    nom: str
    parti: Optional[str]
    url: Optional[str]
    #: Vrai si la ligne vient d'une sous-section de primaire — porté dans les
    #: notes de l'entrée créée, jamais dans le statut.
    primaire: bool = False


@dataclass
class Ecarts:
    """Le résultat de la comparaison, dans les deux sens."""

    absents_du_fichier: list[CandidatDeclare] = field(default_factory=list)
    plus_declares: list[dict[str, Any]] = field(default_factory=list)
    communs: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return bool(self.absents_du_fichier or self.plus_declares)


# ---------------------------------------------------------------------------
# Collecte
# ---------------------------------------------------------------------------


def url_section() -> str:
    """L'URL humaine de la section, celle qu'on écrit dans `source`."""
    return (
        f"https://fr.wikipedia.org/wiki/{quote(ARTICLE.replace(' ', '_'))}"
        f"#{quote(SECTION_DECLARES.replace(' ', '_'))}"
    )


def telecharger_html(article: str = ARTICLE, session: Any = None) -> str:
    """Rend le HTML **rendu** de l'article (transclusions développées).

    Raises:
        CollecteIncomplete: réseau, HTTP, ou réponse d'API inexploitable. Le
            message porte la cause, pas seulement le fait de l'échec (#524) :
            « en échec » ne dit pas s'il faut relancer ou corriger le code.
    """
    get = (session or requests).get
    params = {"action": "parse", "page": article, "prop": "text", "format": "json"}
    try:
        reponse = get(API, params=params, headers=HEADERS, timeout=TIMEOUT)
        reponse.raise_for_status()
        charge = reponse.json()
    except requests.RequestException as exc:
        raise CollecteIncomplete(f"{ANOMALIE_PAGE} — {article} : {exc}") from exc
    except ValueError as exc:
        raise CollecteIncomplete(
            f"{ANOMALIE_PAGE} — {article} : réponse d'API non JSON ({exc})"
        ) from exc

    if "error" in charge:
        detail = (charge.get("error") or {}).get("info", "erreur d'API sans détail")
        raise CollecteIncomplete(f"{ANOMALIE_PAGE} — {article} : {detail}")

    html = (((charge.get("parse") or {}).get("text") or {})).get("*")
    if not html:
        raise CollecteIncomplete(
            f"{ANOMALIE_PAGE} — {article} : la réponse ne porte aucun HTML rendu."
        )
    return html


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------


def _est_titre(bloc: Tag, niveau: int) -> bool:
    """Vrai pour l'enveloppe `div.mw-heading{niveau}` d'un titre rendu."""
    classes = bloc.get("class") or []
    return "mw-heading" in classes and f"mw-heading{niveau}" in classes


def _enveloppe_du_titre(soup: BeautifulSoup, titre: str) -> Optional[Tag]:
    """L'enveloppe du titre de section, retrouvée par son texte.

    Par le texte et non par l'`id` : l'`id` est dérivé du titre, mais MediaWiki
    l'échappe (`Candidats_d.C3.A9clar.C3.A9s` cohabite avec la forme accentuée),
    et la forme servie a déjà changé une fois entre deux versions du rendu.
    """
    for balise in soup.find_all(["h2", "h3"]):
        if " ".join(balise.get_text(" ", strip=True).split()) == titre:
            enveloppe = balise.parent
            return enveloppe if isinstance(enveloppe, Tag) else None
    return None


def _segments_br(cellule: Tag) -> list[str]:
    """Découpe une cellule en segments séparés par `<br>`, parasites retirés.

    Les trois parasites sont documentés en tête de module : clé de tri de
    `{{TriNom}}`, âge, appels de note.
    """
    copie = BeautifulSoup(str(cellule), "html.parser")
    for parasite in copie.select(
        'sup.reference, span.datasortkey, span[style*="display:none"]'
    ):
        parasite.decompose()

    racine = copie.find(["th", "td"]) or copie
    segments: list[list[str]] = [[]]
    for enfant in racine.children:
        if getattr(enfant, "name", None) == "br":
            segments.append([])
            continue
        texte = enfant.get_text(" ") if isinstance(enfant, Tag) else str(enfant)
        segments[-1].append(texte)

    rendus = []
    for segment in segments:
        texte = " ".join("".join(segment).split())
        texte = texte.strip(" ()·,;")
        if texte:
            rendus.append(texte)
    return rendus


def _lien_personne(cellule: Tag) -> Optional[str]:
    """L'URL de l'article de la personne, ou `None` si elle n'en a pas.

    Cherchée dans le PREMIER segment seulement : le lien du parti vit dans le
    dernier, et deux déclarés sans article ne portent que celui-là.
    """
    for enfant in cellule.children:
        if getattr(enfant, "name", None) == "br":
            return None
        if not isinstance(enfant, Tag):
            continue
        ancre = enfant if enfant.name == "a" else enfant.find("a")
        if ancre is None:
            continue
        href = ancre.get("href") or ""
        if href.startswith("/wiki/") and ":" not in href.split("/wiki/")[-1]:
            return f"https://fr.wikipedia.org{href}"
    return None


def _ligne_en_candidat(cellule: Tag, primaire: bool) -> Optional[CandidatDeclare]:
    """Rend le candidat d'une cellule d'en-tête de ligne, ou `None`."""
    segments = _segments_br(cellule)
    if not segments:
        return None
    nom = segments[0]
    # Une ligne d'en-tête de colonnes ne porte pas un nom de personne.
    if not nom or nom.lower().startswith("candidat"):
        return None
    parti = segments[-1] if len(segments) > 1 else None
    return CandidatDeclare(
        nom=nom, parti=parti, url=_lien_personne(cellule), primaire=primaire
    )


def extraire_declares(html: str) -> tuple[list[CandidatDeclare], list[str]]:
    """Les candidats déclarés du HTML rendu, et les anomalies non bloquantes.

    Lit de « Candidats déclarés » jusqu'au titre de **niveau 2** suivant, donc
    sous-sections de primaire comprises et « Candidats pressentis » exclus.

    Raises:
        CollecteIncomplete: section introuvable, ou aucun candidat extrait.
    """
    soup = BeautifulSoup(html, "html.parser")
    depart = _enveloppe_du_titre(soup, SECTION_DECLARES)
    if depart is None:
        raise CollecteIncomplete(
            f"{ANOMALIE_SECTION} — aucun titre « {SECTION_DECLARES} » dans "
            f"« {ARTICLE} » : l'article a été restructuré, et un titre qui bouge "
            "ne doit pas se lire comme une liste vide."
        )

    candidats: list[CandidatDeclare] = []
    anomalies: list[str] = []
    vus: set[str] = set()
    primaire = False

    bloc = depart.find_next_sibling()
    while bloc is not None:
        if isinstance(bloc, Tag):
            if _est_titre(bloc, 2):
                break
            if _est_titre(bloc, 3) or _est_titre(bloc, 4):
                primaire = True
            for tableau in _tableaux(bloc):
                for cellule in _cellules_de_ligne(tableau):
                    candidat = _ligne_en_candidat(cellule, primaire)
                    if candidat is None:
                        brut = " ".join(cellule.get_text(" ", strip=True).split())
                        if brut:
                            anomalies.append(f"{AVERTISSEMENT_LIGNE} — « {brut[:80]} »")
                        continue
                    cle = cle_nom(candidat.nom)
                    if cle in vus:
                        continue
                    vus.add(cle)
                    candidats.append(candidat)
        bloc = bloc.find_next_sibling()

    if not candidats:
        raise CollecteIncomplete(
            f"{ANOMALIE_VIDE} — la section « {SECTION_DECLARES} » existe mais "
            "n'a rendu aucun candidat : la forme des tableaux a changé."
        )
    return candidats, anomalies


def _tableaux(bloc: Tag) -> Iterable[Tag]:
    """Les tableaux de candidats portés par un bloc de la section."""
    classes = bloc.get("class") or []
    if bloc.name == "table" and "wikitable" in classes:
        yield bloc
        return
    yield from bloc.select("table.wikitable")


def _cellules_de_ligne(tableau: Tag) -> Iterable[Tag]:
    """Les cellules d'en-tête de ligne — une par candidat.

    Une ligne **d'en-tête de colonnes** n'a que des `th` ; une ligne de candidat
    a un `th` puis des `td`. Les distinguer ici, et non sur le libellé, est ce
    qui évite de signaler quatre « lignes illisibles » par run pour les quatre
    en-têtes « Candidat (nom et âge) et parti politique » — un avertissement
    qu'on apprend à ignorer est un avertissement perdu.
    """
    for ligne in tableau.select("tr"):
        cellule = ligne.find("th", recursive=False)
        if cellule is None or ligne.find("td", recursive=False) is None:
            continue
        yield cellule


# ---------------------------------------------------------------------------
# Comparaison
# ---------------------------------------------------------------------------


def cle_nom(nom: str) -> str:
    """Clé de comparaison d'un nom : sans casse, sans accent, sans ponctuation.

    « Jordan BARDELLA » et « Jordan Bardella » sont la même personne ; c'est la
    seule normalisation que ce script s'autorise sur un nom propre.
    """
    decompose = unicodedata.normalize("NFKD", nom.lower())
    sans_accents = "".join(c for c in decompose if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", sans_accents)).strip()


def comparer(
    declares: list[CandidatDeclare], locaux: list[dict[str, Any]]
) -> Ecarts:
    """Compare la source et le fichier, dans les deux sens."""
    par_cle_source = {cle_nom(c.nom): c for c in declares}
    par_cle_local = {cle_nom(c.get("nom", "")): c for c in locaux}

    ecarts = Ecarts()
    for cle, candidat in par_cle_source.items():
        if cle not in par_cle_local:
            ecarts.absents_du_fichier.append(candidat)
        else:
            ecarts.communs.append(candidat.nom)
    for cle, entree in par_cle_local.items():
        if cle not in par_cle_source:
            ecarts.plus_declares.append(entree)
    return ecarts


# ---------------------------------------------------------------------------
# Écriture
# ---------------------------------------------------------------------------


#: Motifs de refus d'un slug. Fermés et nommés, comme `MOTIFS_SLUG_NON_ATTRIBUE`
#: de `an_roster` (#708) : un slug non attribué doit dire pourquoi, sinon il se
#: lit comme « personne n'a regardé ».
MOTIF_SLUG_VIDE = "slug_vide"
MOTIF_SLUG_DEJA_PRIS = "slug_deja_pris"
MOTIF_IDENTIFIANT_INDETERMINE = "identifiant_indetermine"


def attribuer_slugs(
    absents: list[CandidatDeclare],
    resolutions: dict[str, iw.Resolution],
    slugs_pris: dict[str, Optional[str]],
) -> tuple[dict[str, str], list[str]]:
    """`nom → slug` pour les déclarés qui peuvent en recevoir un, et les refus.

    Le slug vient de `text_utils.slugify`, **la seule fabrique de slugs du
    dépôt** (#487, #708) — jamais d'un identifiant de source.

    Trois refus, et aucun n'est un seuil :

    1. `slug_vide` — le nom ne rend aucun slug ;
    2. `slug_deja_pris` — le slug visé appartient à **quelqu'un d'autre**. Un
       slug déjà porté par la **même** personne n'est pas une collision : c'est
       le cas des candidats déjà collectés comme membres de roster, et c'est
       l'`acteur_ref` qui tranche, jamais le nom ;
    3. `identifiant_indetermine` — Wikidata ne décrit pas cette personne, donc
       rien ne corroborera son acteur AN hors ligne. Lui fabriquer un slug la
       ferait collecter puis publier, et la §5b bloquerait le run entier sur
       une entrée que la passe hors ligne ne peut pas écrire.

    Args:
        slugs_pris: `slug → acteur_ref` déjà attribués (entrées du fichier et
            table de correspondance confondues). `None` en valeur signifie
            « porté par quelqu'un dont on ne connaît pas l'acteur ».
    """
    attribues: dict[str, str] = {}
    refus: list[str] = []

    for candidat in absents:
        resolution = resolutions.get(candidat.nom)
        if resolution is None or resolution.issue is iw.Issue.INDETERMINE:
            refus.append(
                f"{MOTIF_IDENTIFIANT_INDETERMINE} — « {candidat.nom} » : aucun "
                "élément Wikidata ne décrit cette personne, donc aucun "
                "identifiant AN à corroborer. Entrée créée sans slug, à relire."
            )
            continue

        slug = slugify(candidat.nom)
        if not slug:
            refus.append(f"{MOTIF_SLUG_VIDE} — « {candidat.nom} » ne rend aucun slug.")
            continue

        if slug in slugs_pris or slug in attribues.values():
            porteur = slugs_pris.get(slug)
            if porteur is not None and porteur == resolution.acteur_ref:
                # Même acteur AN : c'est la même personne, déjà collectée par la
                # voie du roster. Le slug est le sien, on le reprend.
                attribues[candidat.nom] = slug
                continue
            refus.append(
                f"{MOTIF_SLUG_DEJA_PRIS} — « {candidat.nom} » vise le slug "
                f"{slug!r}, déjà porté par {porteur or 'une entrée sans acteur AN'} "
                f"(cette personne-ci : {resolution.acteur_ref or 'aucun acteur AN'}). "
                "Entrée créée sans slug, à arbitrer."
            )
            continue

        attribues[candidat.nom] = slug

    return attribues, refus


def nouvelle_entree(
    candidat: CandidatDeclare, le_jour: str, slug: Optional[str] = None
) -> dict[str, Any]:
    """L'entrée créée pour un déclaré absent du fichier.

    `slug` vaut `null` quand la chaîne d'identifiants n'a rien pu corroborer :
    c'est ce qui tient le candidat hors de la matrice `extract-an`, donc hors
    collecte et hors publication, tant qu'une main n'a pas tranché. Avec un
    slug, il entre dans le périmètre du run suivant, et sa correspondance est
    écrite hors ligne par `build_correspondance_acteurs_an.py`.
    """
    origine = "déclaré dans le cadre d'une primaire" if candidat.primaire else "déclaré"
    if slug:
        notes = (
            f"Ajouté le {le_jour} par src/fetch_candidats_declares.py ({origine}). "
            "Slug fabriqué depuis le nom ; l'acteur AN est résolu par identifiant "
            "externe et corroboré hors ligne (#757). Famille politique, date et "
            "source primaire de la déclaration restent à compléter."
        )
    else:
        notes = (
            f"Ajouté le {le_jour} par src/fetch_candidats_declares.py ({origine}). "
            "Sans slug : la chaîne d'identifiants n'a rien pu corroborer, donc ce "
            "candidat n'a pas de shard extract-an et n'est pas publié. À relire — "
            "slug, famille politique, date et source primaire (#753, #757)."
        )
    return {
        "nom": candidat.nom,
        "slug": slug,
        "parti": candidat.parti,
        "famille_politique": None,
        "statut": STATUT_DECLARE,
        "date_declaration": None,
        "source": candidat.url or url_section(),
        "notes": notes,
    }


def slugs_pris(
    document: dict[str, Any], table: Optional[dict[str, Any]] = None
) -> dict[str, Optional[str]]:
    """`slug → acteur_ref` de tout ce qui porte déjà un slug.

    Les deux sources sont réunies exprès : `candidats.json` dit ce que la liste
    éditoriale a déjà attribué, la table de correspondance dit ce que le corpus
    publié porte — un membre de roster n'est dans que la seconde.
    """
    pris: dict[str, Optional[str]] = {}
    for entree in document.get("candidats") or []:
        if entree.get("slug"):
            pris[entree["slug"]] = None
    for slug, entree in (table or {}).items():
        pris[slug] = (entree.get("identifiants") or {}).get("an") or entree.get("acteur_ref")
    return pris


def appliquer(
    document: dict[str, Any],
    absents: list[CandidatDeclare],
    le_jour: str,
    slugs: Optional[dict[str, str]] = None,
) -> dict[str, Any]:
    """Rend le document mis à jour — additif, aucune entrée existante touchée.

    Les nouvelles entrées sont **ajoutées à la fin**, dans l'ordre de la source :
    l'ordre du fichier est éditorial (par famille politique) et le recalculer
    ferait un diff que personne ne peut relire.
    """
    mis_a_jour = json.loads(json.dumps(document))
    mis_a_jour.setdefault("candidats", [])

    # Le comblement d'un `slug: null` est la SEULE modification qu'une entrée
    # existante subisse ici, et c'en est une par nature additive : on remplit un
    # trou, on ne réécrit pas une valeur. Un slug déjà posé n'est jamais touché
    # — il est immuable une fois publié (#460/#470).
    for entree in mis_a_jour["candidats"]:
        if entree.get("slug"):
            continue
        slug = (slugs or {}).get(entree.get("nom"))
        if slug:
            entree["slug"] = slug

    mis_a_jour["candidats"].extend(
        nouvelle_entree(c, le_jour, (slugs or {}).get(c.nom)) for c in absents
    )
    mis_a_jour.setdefault("_meta", {})["derniere_verification"] = le_jour
    return mis_a_jour


def _charger_table(chemin: Path) -> dict[str, Any]:
    """La table de correspondance, ou `{}` si elle est absente ou illisible.

    Absente, elle ne bloque rien ici : elle sert à savoir quels slugs sont déjà
    pris, et son absence rend la vérification moins informée, pas fausse — la
    §5b reste le contrôle qui refuse un slug sans entrée.
    """
    try:
        with open(chemin, encoding="utf-8") as fichier:
            return json.load(fichier).get("correspondances") or {}
    except (OSError, json.JSONDecodeError):
        return {}


def charger(chemin: Path) -> dict[str, Any]:
    """Charge `candidats.json`.

    Raises:
        CollecteIncomplete: fichier absent ou illisible — on n'écrit pas un
            fichier qu'on n'a pas su lire.
    """
    try:
        with open(chemin, encoding="utf-8") as fichier:
            return json.load(fichier)
    except (OSError, json.JSONDecodeError) as exc:
        raise CollecteIncomplete(f"{ANOMALIE_PAGE} — {chemin} illisible : {exc}") from exc


def ecrire(chemin: Path, document: dict[str, Any]) -> None:
    """Écrit le document en préservant la forme du fichier tenu à la main.

    `indent=2`, UTF-8 non échappé, saut de ligne final : le fichier existant
    fait un aller-retour à 6 lignes près, toutes dans un seul tableau compacté à
    la main. Un format qui churne à chaque écriture rendrait le diff illisible,
    ce qui est la seule chose que la relectrice a à faire ici.
    """
    chemin.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Rapport
# ---------------------------------------------------------------------------


def rendre_rapport(
    declares: list[CandidatDeclare],
    ecarts: Ecarts,
    anomalies: list[str],
    ecrit: bool,
    slugs: Optional[dict[str, str]] = None,
) -> str:
    """Le rapport de relecture, sur la sortie standard."""
    lignes = [
        f"=== Candidats déclarés — {len(declares)} en ligne, "
        f"{len(ecarts.communs)} déjà dans le fichier ===",
        "",
    ]

    if ecarts.absents_du_fichier:
        verbe = "AJOUTÉS" if ecrit else "À AJOUTER (relance avec --ecrire)"
        lignes.append(f"[{len(ecarts.absents_du_fichier)} DÉCLARÉS {verbe}]")
        for candidat in ecarts.absents_du_fichier:
            marque = " · primaire" if candidat.primaire else ""
            slug = (slugs or {}).get(candidat.nom)
            identite = f" → {slug}" if slug else " → SANS SLUG"
            lignes.append(
                f"  + {candidat.nom} ({candidat.parti or 'parti inconnu'}{marque}){identite}"
            )
    else:
        lignes.append("✓ Aucun déclaré manquant dans raw_data/candidats.json.")

    combles = {
        nom: slug
        for nom, slug in (slugs or {}).items()
        if nom not in {c.nom for c in ecarts.absents_du_fichier}
    }
    if combles:
        verbe = "COMBLÉS" if ecrit else "À COMBLER (relance avec --ecrire)"
        lignes += ["", f"[{len(combles)} SLUGS {verbe} sur des entrées existantes]"]
        lignes += [f"  = {nom} → {slug}" for nom, slug in sorted(combles.items())]

    if ecarts.plus_declares:
        lignes += [
            "",
            f"[{len(ecarts.plus_declares)} ENTRÉES QUI NE SONT PLUS DÉCLARÉES — "
            "signalées, jamais modifiées]",
            "  (retrait, candidature déclinée, ou déplacement de section : la "
            "cause n'est pas lisible ici)",
        ]
        for entree in ecarts.plus_declares:
            lignes.append(
                f"  ? {entree.get('nom')} (statut: {entree.get('statut')}, "
                f"slug: {entree.get('slug')})"
            )

    if anomalies:
        lignes += ["", f"[{len(anomalies)} LIGNES NON LUES — non bloquant]"]
        lignes += [f"  ! {a}" for a in anomalies]

    return "\n".join(lignes)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _construire_parseur() -> argparse.ArgumentParser:
    parseur = argparse.ArgumentParser(
        description=(
            "Récupère les candidats déclarés à la présidentielle et met à jour "
            "raw_data/candidats.json (additif, jamais destructif)."
        )
    )
    parseur.add_argument(
        "--candidats",
        default=DEFAULT_CANDIDATS_PATH,
        help=f"Fichier candidats.json (défaut : {DEFAULT_CANDIDATS_PATH}).",
    )
    parseur.add_argument(
        "--ecrire",
        action="store_true",
        help="Écrit les ajouts dans le fichier (défaut : rapport seul).",
    )
    parseur.add_argument(
        "--html",
        help=(
            "Lit le HTML rendu depuis un fichier local au lieu du réseau — "
            "rejoue une capture, ne télécharge rien."
        ),
    )
    parseur.add_argument(
        "--article",
        default=ARTICLE,
        help="Titre de l'article Wikipédia à lire (défaut : l'article des candidatures).",
    )
    parseur.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Sortie JSON au lieu du rapport texte.",
    )
    parseur.add_argument(
        "--echouer-si-ecart",
        action="store_true",
        help=f"Sort en {EXIT_ECART} si la source et le fichier diffèrent.",
    )
    parseur.add_argument(
        "--resoudre-identifiants",
        action="store_true",
        help=(
            "Résout l'acteur AN de chaque déclaré neuf par identifiant externe "
            "(Wikidata P4123) et lui fabrique un slug quand la chaîne aboutit (#757)."
        ),
    )
    parseur.add_argument(
        "--resolutions-out",
        help=(
            "Écrit les résolutions dans ce fichier, que la passe hors ligne de "
            "merge-and-pivot relit. Implique --resoudre-identifiants."
        ),
    )
    parseur.add_argument(
        "--correspondance",
        default="raw_data/correspondance_acteurs_an.json",
        help="Table slug ↔ acteur AN, lue pour savoir quels slugs sont déjà pris.",
    )
    return parseur


def main(argv: Optional[list[str]] = None) -> int:
    args = _construire_parseur().parse_args(argv)
    chemin = Path(args.candidats)

    try:
        html = (
            Path(args.html).read_text(encoding="utf-8")
            if args.html
            else telecharger_html(args.article)
        )
        declares, anomalies = extraire_declares(html)
        document = charger(chemin)
    except CollecteIncomplete as exc:
        # L'annotation d'abord : c'est la seule trace qui survit à la fermeture
        # d'un run (#518). Le fichier n'est PAS touché (#511).
        gha.annoter("error", str(exc))
        print(f"[!] {exc}", file=sys.stderr)
        print(f"[!] {chemin} n'a pas été modifié.", file=sys.stderr)
        return EXIT_COLLECTE_INCOMPLETE
    except OSError as exc:
        gha.annoter("error", f"{ANOMALIE_PAGE} — {args.html} illisible : {exc}")
        print(f"[!] {exc}", file=sys.stderr)
        return EXIT_COLLECTE_INCOMPLETE

    locaux = document.get("candidats") or []
    ecarts = comparer(declares, locaux)

    slugs: dict[str, str] = {}
    refus_slug: list[str] = []
    resolutions: dict[str, iw.Resolution] = {}
    if args.resoudre_identifiants or args.resolutions_out:
        # Deux populations, la même chaîne : les déclarés que le fichier ignore,
        # et ceux qu'il porte DÉJÀ sans slug. Oublier la seconde laisserait les
        # entrées créées avant la boucle bloquées pour toujours — c'est
        # exactement l'immobilité que #539 a payée.
        a_resoudre = [
            {"nom": c.nom, "source": c.url or url_section()}
            for c in ecarts.absents_du_fichier
        ] + [
            {"nom": e["nom"], "source": e.get("source")}
            for e in locaux
            if not e.get("slug") and e.get("statut") == STATUT_DECLARE
        ]
        if a_resoudre:
            try:
                resolutions = iw.resoudre(a_resoudre)
            except iw.ResolutionIndisponible as exc:
                # Une panne d'identifiants n'est pas un fait négatif : on n'écrit
                # aucun slug plutôt que d'en fabriquer sans corroboration (#511).
                gha.annoter("error", f"CANDIDATS_RESOLUTION_INDISPONIBLE — {exc}")
                print(f"[!] {exc}", file=sys.stderr)
                print(f"[!] {chemin} n'a pas été modifié.", file=sys.stderr)
                return EXIT_COLLECTE_INCOMPLETE

            table = _charger_table(Path(args.correspondance))
            a_slugger = list(ecarts.absents_du_fichier) + [
                CandidatDeclare(nom=e["nom"], parti=e.get("parti"), url=e.get("source"))
                for e in locaux
                if not e.get("slug") and e.get("statut") == STATUT_DECLARE
            ]
            slugs, refus = attribuer_slugs(
                a_slugger, resolutions, slugs_pris(document, table)
            )
            for message in refus:
                gha.annoter("warning", f"CANDIDATS_SANS_SLUG — {message}")
            refus_slug = refus

            if args.resolutions_out:
                iw.ecrire_resolutions(
                    Path(args.resolutions_out), resolutions, date.today().isoformat()
                )

    for anomalie in anomalies:
        gha.annoter("warning", anomalie)
    for entree in ecarts.plus_declares:
        gha.annoter(
            "warning",
            f"{AVERTISSEMENT_PLUS_DECLARE} — « {entree.get('nom')} » "
            f"(statut: {entree.get('statut')}) n'est plus dans la section des "
            "déclarés ; entrée laissée telle quelle, à relire.",
        )

    if args.ecrire and (ecarts.absents_du_fichier or slugs):
        ecrire(
            chemin,
            appliquer(document, ecarts.absents_du_fichier, date.today().isoformat(), slugs),
        )

    if args.json_output:
        json.dump(
            {
                "declares_en_ligne": [
                    {
                        "nom": c.nom,
                        "parti": c.parti,
                        "url": c.url,
                        "primaire": c.primaire,
                    }
                    for c in declares
                ],
                "absents_du_fichier": [c.nom for c in ecarts.absents_du_fichier],
                "plus_declares": [e.get("nom") for e in ecarts.plus_declares],
                "communs": ecarts.communs,
                "lignes_non_lues": anomalies,
                "slugs_fabriques": slugs,
                "sans_slug": refus_slug,
                "resolutions": {
                    nom: r.en_dict() for nom, r in sorted(resolutions.items())
                },
                "ecrit": bool(args.ecrire and ecarts.absents_du_fichier),
            },
            sys.stdout,
            ensure_ascii=False,
            indent=2,
        )
        print()
    else:
        print(
            rendre_rapport(
                declares, ecarts, anomalies + refus_slug, ecrit=args.ecrire, slugs=slugs
            )
        )

    if args.echouer_si_ecart and ecarts:
        return EXIT_ECART
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
