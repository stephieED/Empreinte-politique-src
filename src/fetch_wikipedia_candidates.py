#!/usr/bin/env python3
"""
fetch_wikipedia_candidates.py

Veille automatique sur les candidats présidentiables via l'API MediaWiki
(Wikipédia FR) et l'API Wikidata. Compare le résultat avec le fichier local
candidats.json et signale les divergences pour validation manuelle.

Principe : on ne modifie JAMAIS candidats.json automatiquement. Le script
produit un diff lisible ; c'est l'éditeur qui décide d'intégrer les ajouts.

Sources :
  - Wikipédia FR (article sur l'élection) via l'API MediaWiki REST
  - Wikidata (requête SPARQL sur les candidats déclarés) via le Wikidata SPARQL endpoint

Usage (depuis la racine du dépôt) :
    python src/fetch_wikipedia_candidates.py
    python src/fetch_wikipedia_candidates.py --json     # sortie JSON au lieu du texte
    python src/fetch_wikipedia_candidates.py --source wikipedia   # Wikipédia seulement
    python src/fetch_wikipedia_candidates.py --source wikidata    # Wikidata seulement
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "cv-politique-fetch-wikipedia/0.1 (usage personnel / non commercial)"
}
TIMEOUT = 20

# Page Wikipédia de référence pour l'élection présidentielle 2027
WIKIPEDIA_ARTICLE = "Élection_présidentielle_française_de_2027"
WIKIPEDIA_REST_BASE = "https://fr.wikipedia.org/api/rest_v1"
WIKIPEDIA_API_BASE = "https://fr.wikipedia.org/w/api.php"

# Endpoint SPARQL Wikidata
WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"

# Chemin par défaut vers le fichier local des candidats
DEFAULT_CANDIDATS_PATH = "data/candidats.json"


# ---------------------------------------------------------------------------
# Collecte Wikipedia
# ---------------------------------------------------------------------------

def _fetch_wikipedia_html(article: str) -> Optional[str]:
    """Télécharge le HTML de l'article Wikipedia."""
    url = f"{WIKIPEDIA_REST_BASE}/page/html/{quote(article)}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        # Forcer l'encodage détecté avant d'accéder à resp.text, pour éviter
        # le mojibake sur les accents quand le serveur ne déclare pas de charset.
        resp.encoding = resp.apparent_encoding or "utf-8"
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as exc:
        print(f"  [!] Wikipedia HTML inaccessible : {exc}", file=sys.stderr)
        return None


def _extract_names_from_wikipedia_html(html_text: str) -> list[dict[str, str]]:
    """Extrait les noms de candidats depuis le HTML de l'article Wikipedia.

    Stratégie : cherche les listes structurées (ul/ol) sous des titres de section
    qui contiennent "candidat" ou "déclaré". Retourne des dicts {nom, note?}.
    """
    soup = BeautifulSoup(html_text, "html.parser")
    candidates: list[dict[str, str]] = []
    seen: set[str] = set()

    # Cherche les sections candidats par heading
    heading_pattern = re.compile(r"candidat|déclaré|pressenti|en lice", re.IGNORECASE)
    for heading in soup.find_all(["h2", "h3", "h4"]):
        heading_text = heading.get_text(" ", strip=True)
        if not heading_pattern.search(heading_text):
            continue
        # Cherche les listes dans la section suivante
        sibling = heading.find_next_sibling()
        while sibling and sibling.name not in ("h2", "h3", "h4"):
            if sibling.name in ("ul", "ol"):
                for li in sibling.find_all("li", recursive=False):
                    # Le premier lien ou le texte de la li est souvent le nom
                    link = li.find("a")
                    name = None
                    if link:
                        name_raw = link.get_text(" ", strip=True)
                        # Filtre les annotations courtes (notes de bas de page, etc.)
                        if len(name_raw) > 3 and not name_raw.startswith("["):
                            name = name_raw
                    if not name:
                        text = " ".join(li.get_text(" ", strip=True).split())
                        # Prend la partie avant une virgule ou parenthèse (affiliations)
                        name = re.split(r"[,(]", text)[0].strip()
                    if name and len(name) > 3 and name not in seen:
                        seen.add(name)
                        candidates.append({"nom": name, "source": "wikipedia"})
            sibling = sibling.find_next_sibling()

    # Fallback : cherche les liens vers des personnalités politiques dans tout l'article
    if not candidates:
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            if "/wiki/" not in href or ":" in href.split("/wiki/")[-1]:
                continue
            name = link.get_text(" ", strip=True)
            if len(name) > 5 and " " in name and name not in seen:
                # Heuristique : exclure les liens génériques courts
                seen.add(name)
                candidates.append({"nom": name, "source": "wikipedia_fallback"})

    return candidates


def fetch_candidates_wikipedia() -> list[dict[str, Any]]:
    """Récupère la liste des candidats depuis l'article Wikipedia de l'élection.

    Returns:
        Liste de dicts {nom, source}.
    """
    html_text = _fetch_wikipedia_html(WIKIPEDIA_ARTICLE)
    if not html_text:
        return []
    candidates = _extract_names_from_wikipedia_html(html_text)
    print(f"  Wikipedia : {len(candidates)} candidat(s) trouvé(s).")
    return candidates


# ---------------------------------------------------------------------------
# Collecte Wikidata (SPARQL)
# ---------------------------------------------------------------------------

# SPARQL pour trouver les candidats à la présidentielle française 2027.
# P3602 = "candidat dans l'élection"
# Q112289624 = Q-ID de l'élection présidentielle française de 2027 (à vérifier/mettre à jour)
_WIKIDATA_QUERY = """\
SELECT DISTINCT ?person ?personLabel ?partiLabel WHERE {
  ?election wdt:P31 wd:Q869519 ;
            wdt:P17 wd:Q142 ;
            wdt:P585 ?date .
  FILTER(YEAR(?date) = 2027)
  ?person wdt:P3602 ?election .
  OPTIONAL { ?person wdt:P102 ?parti . }
  SERVICE wikibase:label {
    bd:serviceParam wikibase:language "fr,en" .
  }
}
ORDER BY ?personLabel
"""

# Requête de secours par catégorie Wikidata si P3602 n'est pas renseigné
_WIKIDATA_QUERY_FALLBACK = """\
SELECT DISTINCT ?person ?personLabel WHERE {
  ?person wdt:P27 wd:Q142 ;
          wdt:P106 ?occupation .
  VALUES ?occupation { wd:Q82955 wd:Q11696 wd:Q3243002 }
  ?person wikibase:sitelinks ?links .
  FILTER(?links > 3)
  SERVICE wikibase:label {
    bd:serviceParam wikibase:language "fr,en" .
  }
}
LIMIT 50
"""


def fetch_candidates_wikidata() -> list[dict[str, Any]]:
    """Récupère les candidats présidentiables 2027 via Wikidata SPARQL.

    Essaie d'abord la requête ciblée (P3602 candidat dans l'élection),
    puis une requête de secours si la première ne retourne rien.

    Returns:
        Liste de dicts {nom, parti?, source, wikidata_id}.
    """
    candidates: list[dict[str, Any]] = []
    for query, label in [(_WIKIDATA_QUERY, "ciblée"), (_WIKIDATA_QUERY_FALLBACK, "fallback")]:
        try:
            resp = requests.get(
                WIKIDATA_SPARQL,
                params={"query": query, "format": "json"},
                headers={**HEADERS, "Accept": "application/sparql-results+json"},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
        except (requests.RequestException, ValueError) as exc:
            print(f"  [!] Wikidata SPARQL ({label}) inaccessible : {exc}", file=sys.stderr)
            time.sleep(1)
            continue

        bindings = (data.get("results") or {}).get("bindings") or []
        if not bindings:
            print(f"  Wikidata ({label}) : 0 résultat.", file=sys.stderr)
            time.sleep(1)
            continue

        for b in bindings:
            nom = (b.get("personLabel") or {}).get("value") or ""
            parti = (b.get("partiLabel") or {}).get("value") or None
            wikidata_id = (b.get("person") or {}).get("value", "").split("/")[-1]
            if not nom or nom.startswith("Q"):  # Filtre les Q-ID sans label
                continue
            candidates.append({
                "nom": nom,
                "parti": parti,
                "source": f"wikidata ({label})",
                "wikidata_id": wikidata_id,
            })

        print(f"  Wikidata ({label}) : {len(candidates)} candidat(s) trouvé(s).")
        if candidates:
            break
        time.sleep(1)

    return candidates


# ---------------------------------------------------------------------------
# Comparaison avec le fichier local
# ---------------------------------------------------------------------------

def load_local_candidats(path: str) -> list[dict[str, Any]]:
    """Charge la liste locale des candidats depuis candidats.json."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("candidats") or []
    except (OSError, json.JSONDecodeError) as exc:
        print(f"  [!] Impossible de charger {path} : {exc}", file=sys.stderr)
        return []


def _normalize_name(name: str) -> str:
    """Normalise un nom pour la comparaison (minuscules, sans accents, sans ponctuation)."""
    import unicodedata
    decomposed = unicodedata.normalize("NFKD", name.lower())
    without_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"[^a-z\s]", "", without_accents).strip()


def diff_candidates(
    fetched: list[dict[str, Any]],
    local: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compare les candidats récupérés avec la liste locale.

    Args:
        fetched: candidats trouvés par fetch_candidates_wikipedia() / _wikidata().
        local: candidats du fichier candidats.json local.

    Returns:
        Dict avec les clés :
          - "nouveaux": candidats dans fetched mais absents du local (à valider)
          - "absents_en_ligne": candidats dans local mais absents du fetched
          - "ok": candidats présents des deux côtés
    """
    local_noms_norm = {_normalize_name(c["nom"]): c for c in local}
    fetched_noms_norm = {_normalize_name(f["nom"]): f for f in fetched}

    nouveaux = [
        f for norm_nom, f in fetched_noms_norm.items()
        if norm_nom not in local_noms_norm
    ]
    absents_en_ligne = [
        c for norm_nom, c in local_noms_norm.items()
        if norm_nom not in fetched_noms_norm
    ]
    ok = [
        c for norm_nom, c in local_noms_norm.items()
        if norm_nom in fetched_noms_norm
    ]

    return {
        "nouveaux": nouveaux,
        "absents_en_ligne": absents_en_ligne,
        "ok": ok,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--source",
        choices=["wikipedia", "wikidata", "all"],
        default="all",
        help="Source à interroger (défaut : all)",
    )
    parser.add_argument(
        "--candidats",
        default=DEFAULT_CANDIDATS_PATH,
        help=f"Chemin vers candidats.json local (défaut : {DEFAULT_CANDIDATS_PATH})",
    )
    parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Sortie en JSON (défaut : texte lisible)",
    )
    args = parser.parse_args()

    fetched: list[dict[str, Any]] = []
    if args.source in ("wikipedia", "all"):
        print("→ Interrogation Wikipédia…")
        fetched.extend(fetch_candidates_wikipedia())
        time.sleep(1)
    if args.source in ("wikidata", "all"):
        print("→ Interrogation Wikidata…")
        fetched.extend(fetch_candidates_wikidata())

    local = load_local_candidats(args.candidats)
    diff = diff_candidates(fetched, local)

    if args.json_output:
        json.dump(diff, sys.stdout, ensure_ascii=False, indent=2)
        print()
        return

    print(f"\n=== Résultat de la veille ({len(fetched)} candidat(s) en ligne) ===\n")

    if diff["nouveaux"]:
        print(f"[NOUVEAUX — à valider manuellement avant d'ajouter dans candidats.json]")
        for c in diff["nouveaux"]:
            parti = c.get("parti") or ""
            wid = c.get("wikidata_id") or ""
            extras = " | ".join(filter(None, [parti, f"wikidata:{wid}" if wid else None]))
            print(f"  + {c['nom']}" + (f"  ({extras})" if extras else ""))
    else:
        print("✓ Aucun nouveau candidat détecté en ligne.")

    if diff["absents_en_ligne"]:
        print(f"\n[ABSENTS EN LIGNE — présents dans candidats.json mais non trouvés par la veille]")
        print("  (peut indiquer un changement de statut, un retrait, ou une limite de couverture)")
        for c in diff["absents_en_ligne"]:
            print(f"  ? {c['nom']}  ({c.get('parti', '')} — statut: {c.get('statut', '')})")

    print(f"\n✓ {len(diff['ok'])} candidat(s) présents des deux côtés.")


if __name__ == "__main__":
    main()
