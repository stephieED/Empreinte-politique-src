#!/usr/bin/env python3
"""
syceron_debates.py — Téléchargement/cache des comptes rendus Syceron de
l'Assemblée nationale par législature.

Le dump open data Syceron est publié sous la forme d'une archive ZIP :
https://data.assemblee-nationale.fr/static/openData/repository/{legislature}/vp/syceronbrut/syseron.xml.zip

Les archives sont mises en cache sous .cache/syceron_an/<legislature>/ afin
d'éviter un re-téléchargement complet à chaque exécution.
"""

import shutil
import threading
import zipfile
from pathlib import Path
from typing import Optional

import requests

AN_OPENDATA_BASE = "https://data.assemblee-nationale.fr/static/openData/repository"
SYCERON_ZIP_NAME = "syseron.xml.zip"
SYCERON_CACHE_DIR = Path(".cache") / "syceron_an"
SYCERON_AVAILABLE_LEGISLATURES = {"15", "16", "17"}

HEADERS = {
    "User-Agent": "cv-politique-syceron/0.1 (usage personnel / non commercial)"
}
TIMEOUT = (15, 600)

_SYCERON_LOCKS: dict[str, threading.Lock] = {}
_SYCERON_LOCKS_META = threading.Lock()


def _get_syceron_lock(legislature: str) -> threading.Lock:
    """Retourne (ou crée) le verrou associé à une législature donnée."""
    with _SYCERON_LOCKS_META:
        if legislature not in _SYCERON_LOCKS:
            _SYCERON_LOCKS[legislature] = threading.Lock()
        return _SYCERON_LOCKS[legislature]


def syceron_zip_url(legislature: str) -> Optional[str]:
    """Retourne l'URL du ZIP Syceron pour une législature, ou None si absente."""
    if legislature not in SYCERON_AVAILABLE_LEGISLATURES:
        return None
    return f"{AN_OPENDATA_BASE}/{legislature}/vp/syceronbrut/{SYCERON_ZIP_NAME}"


def _syceron_cache_root(legislature: str) -> Path:
    return SYCERON_CACHE_DIR / legislature


def _syceron_zip_path(legislature: str) -> Path:
    return _syceron_cache_root(legislature) / SYCERON_ZIP_NAME


def _syceron_xml_dir(legislature: str) -> Path:
    return _syceron_cache_root(legislature) / "xml" / "compteRendu"


def _extract_syceron_zip(zip_path: Path, legislature: str) -> Optional[Path]:
    """Extrait le sous-répertoire xml/compteRendu/ du ZIP Syceron."""
    cache_root = _syceron_cache_root(legislature)
    xml_root = cache_root / "xml"
    xml_dir = _syceron_xml_dir(legislature)

    try:
        with zipfile.ZipFile(zip_path) as zf:
            members = [
                name
                for name in zf.namelist()
                if name.startswith("xml/compteRendu/") and name.endswith(".xml")
            ]
            if not members:
                return None
            shutil.rmtree(xml_root, ignore_errors=True)
            cache_root.mkdir(parents=True, exist_ok=True)
            for member in members:
                zf.extract(member, path=cache_root)
    except (OSError, zipfile.BadZipFile):
        return None

    if xml_dir.is_dir() and any(xml_dir.glob("*.xml")):
        return xml_dir
    return None


def _download_syceron_zip(legislature: str, dest: Path) -> bool:
    """Télécharge le ZIP Syceron d'une législature vers le cache local."""
    url = syceron_zip_url(legislature)
    if not url:
        return False

    print(f"-> Téléchargement des débats Syceron (Assemblée nationale) : {url}")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, stream=True)
        resp.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as out:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    out.write(chunk)
        return True
    except (requests.RequestException, OSError) as exc:
        print(f"  [!] Débats Syceron législature {legislature} indisponibles : {exc}")
        return False


def ensure_syceron_downloaded(
    legislature: str,
    *,
    local_zip_path: Optional[Path | str] = None,
    force_download: bool = False,
) -> Optional[Path]:
    """Assure qu'un dump Syceron est disponible et extrait localement.

    Args:
        legislature: numéro de législature AN.
        local_zip_path: archive ZIP locale à utiliser au lieu du réseau.
        force_download: si True, ignore le cache existant et recharge l'archive.

    Returns:
        Le dossier `xml/compteRendu/` extrait, ou None si le dataset n'existe pas
        pour cette législature ou si le téléchargement/extraction échoue.
    """
    with _get_syceron_lock(legislature):
        xml_dir = _syceron_xml_dir(legislature)
        zip_path = _syceron_zip_path(legislature)

        if not force_download and xml_dir.is_dir() and any(xml_dir.glob("*.xml")):
            return xml_dir

        if local_zip_path is not None:
            source = Path(local_zip_path)
            if not source.is_file():
                return None
            zip_path.parent.mkdir(parents=True, exist_ok=True)
            if source.resolve() != zip_path.resolve():
                shutil.copyfile(source, zip_path)
            return _extract_syceron_zip(zip_path, legislature)

        if not force_download and zip_path.is_file():
            extracted = _extract_syceron_zip(zip_path, legislature)
            if extracted is not None:
                return extracted

        if legislature not in SYCERON_AVAILABLE_LEGISLATURES:
            return None

        if not _download_syceron_zip(legislature, zip_path):
            return None
        return _extract_syceron_zip(zip_path, legislature)


def iter_syceron_xml_files(
    legislature: str,
    *,
    local_zip_path: Optional[Path | str] = None,
    force_download: bool = False,
):
    """Retourne les fichiers XML Syceron extraits pour une législature."""
    xml_dir = ensure_syceron_downloaded(
        legislature,
        local_zip_path=local_zip_path,
        force_download=force_download,
    )
    if xml_dir is None:
        return iter(())
    return iter(sorted(xml_dir.glob("*.xml")))
