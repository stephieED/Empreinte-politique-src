#!/usr/bin/env python3
"""
documents_europeens.py — L'index des documents du Parlement européen (#901).

## Ce que cet index résout

`dossiers_europeens.json` porte la matière d'un **dossier** de procédure. Mais
sur les 694 textes portés européens des fiches de candidats déclarés, **628**
ne citent aucun dossier : ce sont des propositions de résolution déposées en
séance, motif `activite_sans_dossier`. Elles n'ouvrent pas de procédure, donc
elles n'ont ni commission saisie au fond, ni entrée dans l'index des dossiers.
Mesuré le 16/09/2026, l'axe thématique plafonnait à **66 textes sur 694**.

Le portail du Parlement classe pourtant ces documents : `is_about` rend 2 à 9
concepts **EuroVoc** par document — 11 sur la résolution commune
`RC-9-2024-0227`, vérifiée une à une.

## Un index, et pas un champ sur chaque texte porté

628 occurrences ne recouvrent que **279 documents distincts** : un même texte
est porté par plusieurs candidats, et l'écrire sur chaque fiche le répéterait
2,25 fois. Même raison qu'en #431 pour les amendements, et même forme que
`scrutins.json` : la fiche cite une clé, l'index porte le fait.

## Deux sources, deux licences

Les **concepts** viennent du portail du Parlement (`is_about`), dans la réponse
que `ResolveurDocuments` télécharge déjà pour l'existence et le titre : cet
index ne coûte **aucune requête de plus** au Parlement.

Les **libellés** viennent d'EuroVoc, publié par l'Office des publications sous
**CC BY 4.0** — attribution, et indication des modifications. Ils se résolvent
par SPARQL, et par LOTS : une requête `VALUES` rend une centaine de libellés
d'un coup. Mesuré le 16/09/2026 : 4 concepts en 0,22 s.

## Les libellés sont en français

C'est ce qui distingue cet index de celui des dossiers, dont les intitulés
restent en anglais faute d'équivalent : EuroVoc est multilingue, et `prefLabel`
filtré sur `fr` rend « opposition politique », « prisonnier politique »,
« Azerbaïdjan ».
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Iterable, Optional

SCHEMA_VERSION = "documents-europeens-v1"

#: Le point SPARQL de l'Office des publications — il sert EuroVoc.
SPARQL_EUROVOC = "https://publications.europa.eu/webapi/rdf/sparql"

#: Concepts par requête. Cent tiennent largement dans une URL, et la mesure du
#: 16/09/2026 rend quatre libellés en 0,22 s : le coût est dans le nombre de
#: requêtes, pas dans leur taille.
LOT_SPARQL = 100

TIMEOUT_SPARQL = 60
PAUSE_ENTRE_LOTS = 0.5

LICENCE = (
    "Parlement européen (data.europarl.europa.eu, attribution) ; "
    "EuroVoc — Office des publications de l'Union européenne, CC BY 4.0"
)

_REQUETE = """PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
SELECT ?c ?l WHERE {
  VALUES ?c { %s }
  ?c skos:prefLabel ?l . FILTER(lang(?l) = "fr")
}"""


class LibellesEurovocIndisponibles(RuntimeError):
    """EuroVoc n'a pas répondu : publier des codes nus serait illisible."""


def uri_eurovoc(code: str) -> str:
    """`2155` → `http://eurovoc.europa.eu/2155`, l'URI que SPARQL interroge."""
    return f"http://eurovoc.europa.eu/{code}"


#: Le chemin d'un document sur le site public, SANS son schéma.
#:
#: Les deux schémas cohabitent dans le corpus, et c'est le piège de ce lot :
#: mesuré le 16/09/2026, **625** `source_url` de textes portés européens sont en
#: `http://` contre **56** en `https://`. Un filtre sur la seule forme moderne
#: — celle de `DOCEO_BASE` — rendait 56 documents au lieu de 279, sans erreur ni
#: avertissement. Le schéma est donc retiré avant comparaison.
_CHEMIN_DOCEO = "www.europarl.europa.eu/doceo/document"


def _reference_depuis_url(url: Any) -> Optional[str]:
    """`…/doceo/document/RC-9-2024-0227_EN.html` → `RC-9-2024-0227`."""
    if not isinstance(url, str) or _CHEMIN_DOCEO not in url:
        return None
    nom = url.split(_CHEMIN_DOCEO, 1)[1].strip("/").split(".")[0]
    for suffixe in ("_EN", "_FR"):
        nom = nom.removesuffix(suffixe)
    return nom or None


def references_documents(profils_dir: Path) -> set[str]:
    """Les documents `doceo` que les textes portés européens citent.

    La référence est tirée du `source_url` publié, jamais reconstruite d'un
    titre : c'est l'adresse que la collecte a vérifiée (#827).
    """
    refs: set[str] = set()
    for chemin in sorted(Path(profils_dir).glob("*.pivot.json")):
        try:
            profil = json.loads(chemin.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for texte in profil.get("textes_portes") or []:
            if not isinstance(texte, dict):
                continue
            if texte.get("institution") != "parlement_europeen":
                continue
            reference = _reference_depuis_url(texte.get("source_url"))
            if reference:
                refs.add(reference)
    return refs


def resoudre_libelles(
    codes: Iterable[str], session: Any, lot: int = LOT_SPARQL
) -> dict[str, str]:
    """`code → libellé français`, par requêtes groupées.

    Un code sans libellé n'est pas inventé : il manque simplement du résultat,
    et l'appelant le déclare (§2 règle 5).
    """
    restants = sorted({str(c).strip() for c in codes if str(c).strip()})
    libelles: dict[str, str] = {}
    for depart in range(0, len(restants), lot):
        tranche = restants[depart:depart + lot]
        requete = _REQUETE % " ".join(f"<{uri_eurovoc(c)}>" for c in tranche)
        try:
            reponse = session.get(
                SPARQL_EUROVOC,
                params={"query": requete},
                headers={"Accept": "application/sparql-results+json"},
                timeout=TIMEOUT_SPARQL,
            )
        except Exception as exc:
            raise LibellesEurovocIndisponibles(
                f"EuroVoc injoignable : {exc}. Publier des codes nus donnerait "
                "une matière que personne ne peut lire."
            ) from exc
        if reponse.status_code != 200:
            raise LibellesEurovocIndisponibles(
                f"EuroVoc a répondu {reponse.status_code}."
            )
        for ligne in reponse.json().get("results", {}).get("bindings", []):
            code = str(ligne["c"]["value"]).rstrip("/").rsplit("/", 1)[-1]
            libelle = str(ligne["l"]["value"]).strip()
            if libelle:
                libelles[code] = libelle
        if depart + lot < len(restants):
            time.sleep(PAUSE_ENTRE_LOTS)
    return libelles


def _entree(doceo: str, codes: Optional[list[str]], libelles: dict[str, str]) -> dict[str, Any]:
    """Une entrée d'index, avec le motif quand elle ne porte pas de matière."""
    entree: dict[str, Any] = {"id": doceo, "matieres": []}
    if codes is None:
        entree["matieres_non_resolu"] = {"motif": "portail_non_interroge"}
        return entree
    if not codes:
        entree["matieres_non_resolu"] = {"motif": "source_sans_concept"}
        return entree
    connus = [c for c in codes if c in libelles]
    entree["matieres"] = [{"code": c, "libelle": libelles[c]} for c in connus]
    manquants = [c for c in codes if c not in libelles]
    if manquants:
        # Le document garde les libellés trouvés ET déclare les autres : une
        # matière perdue en silence serait indétectable.
        entree["matieres_non_resolu"] = {
            "motif": "libelle_eurovoc_introuvable",
            "codes": manquants,
        }
    return entree


def construire(references: Iterable[str], resolveur: Any, session: Any) -> list[dict[str, Any]]:
    """Les entrées d'index des documents cités, triées par identifiant."""
    voulues = sorted({r for r in references if r})
    if not voulues:
        return []
    concepts_par_doc: dict[str, Optional[list[str]]] = {}
    for doceo in voulues:
        concepts_par_doc[doceo] = resolveur.concepts_eurovoc(doceo)
    tous = {c for codes in concepts_par_doc.values() if codes for c in codes}
    libelles = resoudre_libelles(tous, session) if tous else {}
    return [_entree(d, concepts_par_doc[d], libelles) for d in voulues]


def document(entrees: list[dict[str, Any]]) -> dict[str, Any]:
    """L'index complet, entête comprise — même forme que les autres index."""
    return {
        "schema_version": SCHEMA_VERSION,
        "genere_le": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "licence_donnees": LICENCE,
        "documents": entrees,
    }


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--profils-dir", type=Path, default=Path("pivot_data/profiles"))
    parser.add_argument("--out", type=Path, default=Path("pivot_data/documents_europeens.json"))
    args = parser.parse_args(argv)

    import requests  # noqa: PLC0415
    from europarl_documents import resolveur_par_defaut  # noqa: PLC0415

    references = references_documents(args.profils_dir)
    print(f"→ documents cités par les textes portés européens : {len(references)}")
    resolveur = resolveur_par_defaut()
    entrees = construire(references, resolveur, requests.Session())
    resolveur.enregistrer()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(document(entrees), ensure_ascii=False), encoding="utf-8")

    avec = sum(1 for e in entrees if e["matieres"])
    print(f"  {len(entrees)} document(s) → {args.out}")
    print(f"  avec au moins une matière : {avec}")
    print(f"  sans : {len(entrees) - avec} (motif déclaré)")
    stats = resolveur.statistiques
    if stats.get("disjoncte"):
        print("  ⚠ la passe s'est ARRÊTÉE en route (portail muet) : la couverture "
              "ci-dessus ne dit rien de la source.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
