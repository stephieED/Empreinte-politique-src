"""
parse_syceron.py — Parser XML pour les comptes rendus de séance (format Syceron).

Extrait, pour chaque paragraphe attribué à un orateur identifié :
  - date              : date de la séance (str ISO-8601 ou None)
  - numero_seance     : identifiant de séance (str ou None)
  - legislature       : numéro de législature (str ou None)
  - session           : libellé de session (str ou None)
  - acteur_ref        : identifiant AN de l'orateur (str ou None)
  - prenom_nom        : prénom + nom de l'orateur (str ou None)
  - qualite           : qualité / fonction déclarée (str ou None)
  - texte             : texte de l'intervention, tronqué à 180 caractères (str ou None)
  - dossier_ref       : référence du dossier législatif en cours (str ou None)
  - titre_point       : intitulé du point à l'ordre du jour (str ou None)
  - thematique_ref    : référence thématique du point ODJ (str ou None)

Règles éditoriales respectées :
  - Aucun champ manquant n'est comblé par "" ou 0 — la valeur manquante est None.
  - Les paragraphes sans orateur identifié (présidence, signaux de procédure…)
    sont ignorés.
  - Le texte est normalisé (espaces superflus supprimés) avant troncature.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional
from xml.etree import ElementTree as ET

# Longueur maximale du texte d'intervention conservé (cohérence avec le schéma pivot).
_TEXTE_MAX_CHARS = 180


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _text(element: Optional[ET.Element], tag: str) -> Optional[str]:
    """Retourne le texte nettoyé du premier sous-élément `tag`, ou None."""
    if element is None:
        return None
    child = element.find(tag)
    if child is None or child.text is None:
        return None
    value = re.sub(r"\s+", " ", child.text).strip()
    return value if value else None


def _normalise_texte(raw: Optional[str]) -> Optional[str]:
    """Nettoie et tronque le texte d'un paragraphe à `_TEXTE_MAX_CHARS` caractères."""
    if raw is None:
        return None
    cleaned = re.sub(r"\s+", " ", raw).strip()
    if not cleaned:
        return None
    return cleaned[:_TEXTE_MAX_CHARS] if len(cleaned) > _TEXTE_MAX_CHARS else cleaned


def _collect_text(element: Optional[ET.Element]) -> Optional[str]:
    """Collecte récursivement tout le texte d'un élément XML (texte + tail)."""
    if element is None:
        return None
    parts: list[str] = []
    if element.text:
        parts.append(element.text)
    for child in element:
        sub = _collect_text(child)
        if sub:
            parts.append(sub)
        if child.tail:
            parts.append(child.tail)
    return " ".join(parts) if parts else None


# ---------------------------------------------------------------------------
# Extraction des métadonnées de séance
# ---------------------------------------------------------------------------

def _parse_metadonnees(root: ET.Element) -> dict:
    """Extrait le bloc <metadonnees> (ou <metaDonnees>) de la racine."""
    meta_el = root.find("metadonnees")
    if meta_el is None:
        meta_el = root.find("metaDonnees")
    return {
        "date": _text(meta_el, "dateSeance") or _text(meta_el, "date"),
        "numero_seance": _text(meta_el, "numSeance") or _text(meta_el, "numeroSeance"),
        "legislature": _text(meta_el, "legislature"),
        "session": _text(meta_el, "session"),
    }


# ---------------------------------------------------------------------------
# Extraction des interventions par paragraphe
# ---------------------------------------------------------------------------

def _iter_paragraphes(root: ET.Element):
    """Itère sur tous les <paragraphe> du document, avec leur contexte ODJ."""
    contenu = root.find("contenu")
    if contenu is None:
        contenu = root

    for point_el in contenu.iter("pointODJ"):
        titre_point = _text(point_el, "titrePointODJ") or _text(point_el, "titre")
        dossier_ref = _text(point_el, "dossierRef") or _text(point_el, "dossierId")
        thematique_ref = _text(point_el, "thematiqueRef") or _text(point_el, "thematique")

        for para_el in point_el.iter("paragraphe"):
            orateur_el = para_el.find("orateur")
            if orateur_el is None:
                # Paragraphe sans orateur (présidence, procédure…) — ignoré.
                continue

            texte_el = para_el.find("texte")
            texte_raw = _collect_text(texte_el) if texte_el is not None else None

            yield {
                "orateur_el": orateur_el,
                "texte": _normalise_texte(texte_raw),
                "titre_point": titre_point,
                "dossier_ref": dossier_ref,
                "thematique_ref": thematique_ref,
            }


def _parse_orateur(orateur_el: ET.Element) -> dict:
    """Extrait les champs de l'élément <orateur>."""
    return {
        "acteur_ref": _text(orateur_el, "acteurRef"),
        "prenom_nom": (
            _text(orateur_el, "prenomNom")
            or _text(orateur_el, "nom")
        ),
        "qualite": _text(orateur_el, "qualite"),
    }


# ---------------------------------------------------------------------------
# Point d'entrée principal
# ---------------------------------------------------------------------------

def parse_syceron(source: str | Path | ET.Element) -> list[dict]:
    """
    Parse un compte rendu Syceron et retourne la liste des interventions.

    Paramètres
    ----------
    source :
        Chemin vers un fichier XML, chaîne XML brute, ou un objet ``ET.Element``
        déjà parsé (utile pour les tests).

    Retourne
    --------
    list[dict]
        Une entrée par paragraphe attribué à un orateur identifié.
        Tous les champs manquants valent ``None`` (jamais ``""`` ni ``0``).
    """
    if isinstance(source, ET.Element):
        root = source
    elif isinstance(source, Path):
        root = ET.parse(str(source)).getroot()
    else:
        # str: try file path first, fall back to parsing as raw XML
        p = Path(source)
        if p.exists():
            root = ET.parse(str(p)).getroot()
        else:
            root = ET.fromstring(source)

    meta = _parse_metadonnees(root)
    results: list[dict] = []

    for item in _iter_paragraphes(root):
        orateur = _parse_orateur(item["orateur_el"])

        # Ignore les paragraphes sans orateur référençable (présidence générique…).
        if orateur["acteur_ref"] is None and orateur["prenom_nom"] is None:
            continue

        record: dict = {
            "date": meta["date"],
            "numero_seance": meta["numero_seance"],
            "legislature": meta["legislature"],
            "session": meta["session"],
            "acteur_ref": orateur["acteur_ref"],
            "prenom_nom": orateur["prenom_nom"],
            "qualite": orateur["qualite"],
            "texte": item["texte"],
            "dossier_ref": item["dossier_ref"],
            "titre_point": item["titre_point"],
            "thematique_ref": item["thematique_ref"],
        }
        results.append(record)

    return results
