#!/usr/bin/env python3
"""
syceron_debates.py — Fetch et cache des jeux de débats Syceron par législature.

L'Assemblée nationale publie des fichiers ZIP de débats en séance
(comptes rendus intégraux Syceron) sur data.assemblee-nationale.fr.
La disponibilité varie selon la législature :
  - Législatures 15, 16, 17 : données disponibles.
  - Législatures antérieures (≤ 14) : non disponibles dans ce format.

Les ZIP sont mis en cache sous .cache/syceron_debates/{legislature}/
pour éviter les re-téléchargements. Un ZIP absent du cache est téléchargé
à la première demande. Si la législature n'est pas disponible, la fonction
retourne None sans lever d'exception.

Usage (depuis la racine du dépôt) :
    from syceron_debates import ensure_debates_zip
    zip_path = ensure_debates_zip("17")   # Path ou None
"""

import sys
import time
from pathlib import Path
from typing import Optional

import requests

AN_OPENDATA_BASE = "https://data.assemblee-nationale.fr/static/openData/repository"

SYCERON_DEBATES_CACHE_DIR = Path(".cache") / "syceron_debates"

HEADERS = {
    "User-Agent": "cv-politique-syceron/0.1 (usage personnel / non commercial)"
}

TIMEOUT = 120  # Les archives peuvent faire plusieurs centaines de Mo

# Mapping législature → (dataset, nom de fichier ZIP), ou None si non disponible.
# Seules les législatures pour lesquelles l'archive est publiée sur
# data.assemblee-nationale.fr sont listées ; toute valeur None indique
# explicitement l'absence du dataset pour cette législature.
SYCERON_ZIP_NAMES: dict[str, Optional[tuple[str, str]]] = {
    "17": ("syceronbrut", "Syceron.json.zip"),
    "16": ("syceronbrut", "Syceron.json.zip"),
    "15": ("syceronbrut", "Syceron.json.zip"),
    "14": None,  # non disponible dans ce format
    "13": None,
}


# ---------------------------------------------------------------------------
# Téléchargement
# ---------------------------------------------------------------------------


def _download_debates_zip(url: str, dest: Path) -> bool:
    """Télécharge le ZIP de débats Syceron et le sauvegarde localement.

    Returns:
        True si le téléchargement a réussi, False sinon.
    """
    print(f"→ Téléchargement des débats Syceron : {url}")
    print("  (peut prendre plusieurs minutes selon la taille de l'archive)")
    tmp = dest.with_suffix(".tmp")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, stream=True)
        resp.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 256):
                f.write(chunk)
        tmp.replace(dest)
        print(f"  ✓ Archive sauvegardée : {dest}")
        return True
    except requests.RequestException as exc:
        print(f"  [!] Échec du téléchargement : {exc}", file=sys.stderr)
        tmp.unlink(missing_ok=True)
        return False


# ---------------------------------------------------------------------------
# API publique
# ---------------------------------------------------------------------------


def ensure_debates_zip(
    legislature: str,
    force_download: bool = False,
) -> Optional[Path]:
    """Assure que le ZIP de débats Syceron est disponible localement pour une législature.

    Si le fichier est déjà présent dans le cache et que ``force_download``
    est False, retourne directement le chemin sans accès réseau.

    Si la législature ne dispose pas de dataset Syceron (valeur None dans
    ``SYCERON_ZIP_NAMES``, ou législature inconnue), retourne None sans
    tenter de téléchargement.

    Args:
        legislature: numéro de législature (ex. ``"17"``, ``"16"``).
        force_download: si True, re-télécharge même si un cache existe.

    Returns:
        Chemin vers le fichier ZIP mis en cache, ou None si indisponible.
    """
    if legislature not in SYCERON_ZIP_NAMES:
        print(
            f"  [!] Législature {legislature!r} inconnue — aucun dataset Syceron configuré.",
            file=sys.stderr,
        )
        return None

    dataset_info = SYCERON_ZIP_NAMES[legislature]
    if dataset_info is None:
        print(
            f"  Législature {legislature} : débats Syceron non disponibles dans ce format.",
        )
        return None

    dataset, zip_name = dataset_info
    dest = SYCERON_DEBATES_CACHE_DIR / legislature / zip_name

    if not force_download and dest.is_file():
        mtime = dest.stat().st_mtime
        age_days = (time.time() - mtime) / 86400
        print(
            f"  Débats Syceron {legislature} en cache (âge : {age_days:.0f} j). "
            "Utiliser force_download=True pour rafraîchir."
        )
        return dest

    url = f"{AN_OPENDATA_BASE}/{legislature}/vp/{dataset}/{zip_name}"
    if _download_debates_zip(url, dest):
        return dest
    return None
