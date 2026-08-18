#!/usr/bin/env python3
"""
json_io.py — Écriture JSON des profils : compact pour les profils individuels,
indenté pour les documents relus à la main (#433, sous-issue de l'épic
volumétrie #429).

Mesuré sur les 752 profils du roster complet (`audit_volumetrie_profils.py`) :
8 093 Mo sur disque pour 5 263 Mo de contenu réel — **2 830 Mo, 35 %, ne sont
que de l'indentation**. C'est le seul levier de #429 qui ne touche aucun champ,
aucun schéma et aucun consommateur : tout le pipeline relit ses fichiers par
`json.load()`, jamais ligne à ligne.

Contrepartie assumée
--------------------
Un profil compact n'est plus lisible en diff git : chaque profil modifié
apparaît comme une seule ligne changée. Cet avantage était déjà perdu en
pratique — le commit de données du 2026-08-18 affichait 16,6 millions de lignes
modifiées sur 239 fichiers, un diff que personne ne lit.

D'où le partage :
  - **compact** — `raw_data/profiles/` et `pivot_data/profiles/` (le volume) ;
  - **indenté** — `pivot_data/groupes`, `pivot_data/gouvernements`,
    `pivot_data/partis`, les rosters, les rapports d'audit et les checkpoints :
    9,8 Mo au total, effectivement relus à la main lors des audits.

Le format n'est jamais porteur de sens : `preserve_stable_freshness_timestamps`
et les comparaisons de contenu de #343 travaillent sur la structure déjà
désérialisée (`_pivot_content_fingerprint` re-sérialise avec `sort_keys=True`),
donc « contenu identique » reste détecté indépendamment de l'indentation.
"""

from pathlib import Path
from typing import Any
import json

# Pas d'espace après `,` ni `:` — les valeurs par défaut de `json.dumps` en
# ajoutent un, soit ~1 octet par champ sur des profils qui en portent des
# centaines de milliers.
SEPARATEURS_COMPACTS = (",", ":")


def dumps_profil_json(document: Any) -> str:
    """Sérialise un profil individuel en JSON compact.

    `ensure_ascii=False` : les accents restent en UTF-8 réel plutôt qu'en
    `\\uXXXX`, qui coûterait 6 octets par caractère accentué — sur des profils
    en français, l'échappement annulerait une part du gain.
    """
    return json.dumps(document, ensure_ascii=False, separators=SEPARATEURS_COMPACTS)


def ecrire_profil_json(chemin: Path, document: Any) -> None:
    """Écrit un profil individuel (brut ou pivot) en JSON compact.

    Crée le répertoire parent au besoin : les appelants le faisaient déjà
    séparément, l'opération est idempotente et rend l'helper sûr à appeler
    depuis n'importe quel générateur.
    """
    chemin = Path(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(dumps_profil_json(document), encoding="utf-8")
