#!/usr/bin/env python3
"""
parse_syceron.py — Parseur XML Syceron (comptes rendus de séance AN).

Extrait les interventions, la date, le numéro de séance, l'orateur, le texte
et les signaux de contexte (titre de point/thème) depuis les fichiers XML
produits par le système Syceron de l'Assemblée nationale.

Format source :
    ZIP par législature disponible sur data.assemblee-nationale.fr
    (voir docs/extract-syceron-an.md pour URLs et structure détaillée).

Usage :
    from parse_syceron import parse_syceron_xml

    with open("CRSANR5L17S2025O1N037.xml", "rb") as f:
        result = parse_syceron_xml(f.read())

    result["seance"]         # métadonnées de la séance
    result["interventions"]  # liste d'interventions (format compatible pivot)

Principes :
    - Champs manquants → None (jamais "" ni 0).
    - Pas d'appel réseau, pas de dépendance externe (xml.etree uniquement).
    - Robuste aux fichiers incomplets ou provisoires.
"""

import re
import xml.etree.ElementTree as ET
from typing import Any, Optional, Union

# Namespace XML des fichiers Syceron AN.
_NS = "http://schemas.assemblee-nationale.fr/referentiel"
_NSP = f"{{{_NS}}}"

# Seuil (en mots) pour distinguer une réaction courte d'une prise développée.
_FORMAT_SEUIL_MOTS = 50

# Préfixes de type_detail inférés depuis le titre de point.
_TYPE_DETAIL_MAP: list[tuple[re.Pattern, str]] = [
    (re.compile(r"question.*gouvernement", re.I), "question_gouvernement"),
    (re.compile(r"question.*orale", re.I), "question_orale"),
    (re.compile(r"question", re.I), "question"),
    (re.compile(r"motion de censure", re.I), "motion_censure"),
    (re.compile(r"explication.*vote", re.I), "explication_vote"),
    (re.compile(r"projet de loi|proposition de loi|PLFSS|PLF", re.I), "loi"),
]


def _tag(local: str) -> str:
    """Retourne le nom de tag qualifié avec le namespace Syceron."""
    return f"{_NSP}{local}"


def _text(element: Optional[ET.Element], path: str) -> Optional[str]:
    """Retourne le texte d'un sous-élément, ou None si absent/vide."""
    if element is None:
        return None
    found = element.find(path)
    if found is None or not (found.text or "").strip():
        return None
    return found.text.strip()


def _extract_texte(paragraphe: ET.Element) -> Optional[str]:
    """Extrait le texte d'un <paragraphe> en normalisant les balises inline.

    Balises inline gérées :
    - <br/> et ses variantes avec namespace (ex. <ns0:br/>) → espace
    - <italique>, <sup>, etc. → contenu texte conservé, balise supprimée
    """
    texte_el = paragraphe.find(_tag("texte"))
    if texte_el is None:
        return None
    # Sérialise l'arbre sous-jacent avec les éventuels préfixes de namespace.
    raw = ET.tostring(texte_el, encoding="unicode", method="xml")
    # Remplace toutes les variantes de <br> (avec ou sans préfixe namespace) par un espace.
    raw = re.sub(r"<[^>]*\bbr\b[^>]*/?>", " ", raw)
    # Retire toutes les balises restantes (dont l'élément racine texte lui-même).
    text = re.sub(r"<[^>]+>", "", raw)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _infer_type_detail(titre: Optional[str]) -> str:
    """Infère le type_detail depuis le titre du point de l'ordre du jour."""
    if not titre:
        return "debat"
    for pattern, type_detail in _TYPE_DETAIL_MAP:
        if pattern.search(titre):
            return type_detail
    return "debat"


def _infer_format(texte: Optional[str]) -> str:
    """Déduit le format d'une intervention depuis son volume."""
    if not texte:
        return "reaction_courte"
    nb_mots = len(texte.split())
    return "reaction_courte" if nb_mots < _FORMAT_SEUIL_MOTS else "prise_de_parole_developpee"


def _parse_date_seance(raw: Optional[str]) -> Optional[str]:
    """Convertit le format compact Syceron (YYYYMMDD...) en date ISO YYYY-MM-DD."""
    if not raw or len(raw) < 8:
        return None
    return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"


def _parse_metadonnees(root: ET.Element) -> dict[str, Any]:
    """Extrait les métadonnées de séance depuis <metadonnees>."""
    meta = root.find(_tag("metadonnees"))

    def m(local: str) -> Optional[str]:
        return _text(meta, _tag(local)) if meta is not None else None

    date_raw = m("dateSeance")
    return {
        "uid": (_text(root, _tag("uid"))),
        "seance_ref": (_text(root, _tag("seanceRef"))),
        "session_ref": (_text(root, _tag("sessionRef"))),
        "date": _parse_date_seance(date_raw),
        "legislature": m("legislature"),
        "numero_seance": m("numSeance"),
        "etat": m("etat"),
        "version": m("version"),
    }


def _parse_orateur(paragraphe: ET.Element) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Extrait (id_source, nom, qualite) du premier orateur du paragraphe.

    Retourne (None, None, None) si aucun orateur n'est renseigné.
    """
    orateurs_el = paragraphe.find(_tag("orateurs"))
    if orateurs_el is None:
        return None, None, None
    orateur_el = orateurs_el.find(_tag("orateur"))
    if orateur_el is None:
        return None, None, None
    oid = _text(orateur_el, _tag("id"))
    nom = _text(orateur_el, _tag("nom"))
    qualite = _text(orateur_el, _tag("qualite"))
    if not oid and not nom:
        return None, None, None
    return oid, nom, qualite


def _parse_interventions(
    root: ET.Element,
    seance: dict[str, Any],
) -> list[dict[str, Any]]:
    """Extrait toutes les interventions (paragraphes avec orateur+texte) du contenu.

    Un paragraphe est retenu comme intervention dès qu'il possède au moins un
    orateur identifié (id ou nom) ou un texte non-vide.  Les éléments
    <ouvertureSeance> et <finSeance> sont ignorés.

    Clé de déduplication recommandée pour les consommateurs :
        source_id + index(point) + index(paragraphe) + orateur_id_source
    """
    contenu = root.find(_tag("contenu"))
    if contenu is None:
        return []

    date_seance = seance.get("date")
    uid = seance.get("uid")
    seance_ref = seance.get("seance_ref")
    session_ref = seance.get("session_ref")
    etat = seance.get("etat")
    version = seance.get("version")

    interventions: list[dict[str, Any]] = []

    for point in contenu.findall(_tag("point")):
        # Titre du point (signal de contexte / thème)
        titre_struct = point.find(_tag("titreStruct"))
        titre = _text(titre_struct, _tag("intitule")) if titre_struct is not None else None
        type_detail = _infer_type_detail(titre)

        for paragraphe in point.findall(_tag("paragraphe")):
            texte = _extract_texte(paragraphe)
            oid, nom_orateur, qualite = _parse_orateur(paragraphe)

            # On retient le paragraphe s'il a un orateur identifié ou un texte.
            if not oid and not nom_orateur and not texte:
                continue

            interventions.append({
                # Champs compatibles avec le format pivot interventions[]
                "date": date_seance,
                "type_detail": type_detail,
                "sujet": titre,
                "texte": texte,
                "fonction": qualite,
                "format": _infer_format(texte),
                "mots_cles": [],
                "source_url": None,
                # Champs contextuels Syceron (traçabilité et audit qualité)
                "source_id": uid,
                "seance_ref": seance_ref,
                "session_ref": session_ref,
                "orateur_id_source": oid,
                "orateur_nom": nom_orateur,
                "point_ordre_du_jour": titre,
                "etat_compte_rendu": etat,
                "version_compte_rendu": version,
            })

    return interventions


def parse_syceron_xml(xml_content: Union[str, bytes]) -> dict[str, Any]:
    """Parse un fichier XML Syceron et retourne séance + interventions.

    Args:
        xml_content: contenu XML brut (str ou bytes).

    Returns:
        {
            "seance": {
                "uid": str | None,
                "seance_ref": str | None,
                "session_ref": str | None,
                "date": str | None,          # YYYY-MM-DD
                "legislature": str | None,
                "numero_seance": str | None,
                "etat": str | None,          # "complet" | "provisoire"
                "version": str | None,       # "JO" | "avant_JO"
            },
            "interventions": [
                {
                    # Champs pivot interventions[]
                    "date": str | None,
                    "type_detail": str,
                    "sujet": str | None,
                    "texte": str | None,
                    "fonction": str | None,
                    "format": str,           # "reaction_courte" | "prise_de_parole_developpee"
                    "mots_cles": list,
                    "source_url": None,
                    # Champs contextuels Syceron
                    "source_id": str | None,
                    "seance_ref": str | None,
                    "session_ref": str | None,
                    "orateur_id_source": str | None,
                    "orateur_nom": str | None,
                    "point_ordre_du_jour": str | None,
                    "etat_compte_rendu": str | None,
                    "version_compte_rendu": str | None,
                },
                ...
            ],
        }

    Raises:
        ET.ParseError: si le XML est malformé (pas intercepté — l'appelant décide).
    """
    if isinstance(xml_content, str):
        xml_content = xml_content.encode("utf-8")

    root = ET.fromstring(xml_content)

    seance = _parse_metadonnees(root)
    interventions = _parse_interventions(root, seance)

    return {"seance": seance, "interventions": interventions}
