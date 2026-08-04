#!/usr/bin/env python3
"""
parltrack_dumps.py — Accès aux dumps ParlTrack (.zst) pour l'extraction
de données parlementaires européennes par MEP ID.

ParlTrack (https://parltrack.org) publie des dumps JSON compressés Zstandard :
  - ep_dossiers.json.zst        : dossiers législatifs (rapporteurs, comités)
  - ep_plenary_amendments.json.zst : amendements en séance plénière
  - ep_amendments.json.zst      : amendements en commission

Les dumps sont mis en cache localement sous .cache/parltrack/ pour éviter
un re-téléchargement complet à chaque exécution.

Licence données ParlTrack : ODbL v1.0 (Open Database License).
Voir https://parltrack.org/dumps pour les informations de fraîcheur.

Usage (depuis la racine du dépôt) :
    from parltrack_dumps import get_dossiers_for_mep, get_amendments_for_mep
    dossiers = get_dossiers_for_mep(131580)
    amendments = get_amendments_for_mep(131580)
"""

import io
import json
import sys
import time
from pathlib import Path
from typing import Any, Iterator, Optional

import requests
import zstandard as zstd

PARLTRACK_DUMPS_BASE = "https://parltrack.org/dumps"

PARLTRACK_CACHE_DIR = Path(".cache") / "parltrack"

_DUMP_DOSSIERS = "ep_dossiers.json.zst"
_DUMP_PLENARY_AMENDMENTS = "ep_plenary_amendments.json.zst"
_DUMP_COMMITTEE_AMENDMENTS = "ep_amendments.json.zst"

HEADERS = {
    "User-Agent": "cv-politique-parltrack-dumps/0.1 (usage personnel / non commercial)"
}
TIMEOUT = 120  # Les dumps font plusieurs centaines de Mo


# ---------------------------------------------------------------------------
# Téléchargement et cache
# ---------------------------------------------------------------------------


def _download_dump(dump_name: str, dest: Path) -> bool:
    """Télécharge un dump ParlTrack et le sauvegarde localement.

    Returns:
        True si le téléchargement a réussi, False sinon.
    """
    url = f"{PARLTRACK_DUMPS_BASE}/{dump_name}"
    print(f"→ Téléchargement du dump ParlTrack : {url}")
    print("  (peut prendre plusieurs minutes — plusieurs centaines de Mo)")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, stream=True)
        resp.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 256):
                f.write(chunk)
        print(f"  ✓ Dump sauvegardé : {dest}")
        return True
    except requests.RequestException as exc:
        print(f"  [!] Échec du téléchargement : {exc}", file=sys.stderr)
        return False


def ensure_dump(dump_name: str, force_download: bool = False) -> Optional[Path]:
    """Assure que le dump est disponible localement.

    Args:
        dump_name: nom du fichier dump (ex. "ep_dossiers.json.zst").
        force_download: si True, re-télécharge même si un cache existe.

    Returns:
        Chemin vers le fichier .zst, ou None si indisponible.
    """
    dest = PARLTRACK_CACHE_DIR / dump_name
    if not force_download and dest.is_file():
        mtime = dest.stat().st_mtime
        age_days = (time.time() - mtime) / 86400
        print(f"  Dump {dump_name} en cache (âge : {age_days:.0f} j). "
              "Utiliser force_download=True pour rafraîchir.")
        return dest

    if _download_dump(dump_name, dest):
        return dest
    return None


# ---------------------------------------------------------------------------
# Lecture NDJSON .zst (streaming)
# ---------------------------------------------------------------------------


def iter_ndjson_zst(path: Path) -> Iterator[dict[str, Any]]:
    """Lit ligne par ligne un fichier NDJSON compressé Zstandard (.zst).

    Lecture en streaming : n'exige pas de charger l'intégralité du dump
    en mémoire.

    Yields:
        Un dict Python par ligne JSON valide.
    """
    dctx = zstd.ZstdDecompressor()
    with open(path, "rb") as fh:
        with dctx.stream_reader(fh) as reader:
            text_reader = io.TextIOWrapper(reader, encoding="utf-8")
            for line in text_reader:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue


# ---------------------------------------------------------------------------
# Résolution des mepref (format numérique + format hash historique)
# ---------------------------------------------------------------------------


def _resolve_mepref_as_int(mepref: Any) -> Optional[int]:
    """Tente de convertir un `mepref` (champ des dossiers ParlTrack) en
    entier UserID.

    ParlTrack contient deux formats :
    - Format moderne (majoritaire) : entier (ex. 131580) ou chaîne entière.
    - Format hash historique : chaîne hexadécimale de 24 caractères (ex.
      "5479da7eb01f9fc4c71bb6a1"), non convertible directement.

    Returns:
        L'entier UserID si convertible, None sinon (hash historique ou
        valeur inattendue).
    """
    if mepref is None:
        return None
    if isinstance(mepref, int):
        return mepref
    try:
        return int(mepref)
    except (ValueError, TypeError):
        return None  # Hash historique non résolvable sans table de correspondance


# ---------------------------------------------------------------------------
# Index dossiers (rapporteur) : mep_id → liste de dossiers
# ---------------------------------------------------------------------------


def build_dossiers_index(
    force_download: bool = False,
) -> dict[int, list[dict[str, Any]]]:
    """Construit un index UserID → liste de dossiers où le MEP est rapporteur.

    L'index est mis en cache sur disque pour éviter de reconstruire à chaque
    appel.

    Returns:
        dict mep_id (int) → liste de dossiers (avec référence, titre, comité,
        date, source_url).
    """
    index_path = PARLTRACK_CACHE_DIR / "index_dossiers_rapporteur.json"
    dump_path = ensure_dump(_DUMP_DOSSIERS, force_download)
    if dump_path is None:
        return {}

    if (
        not force_download
        and index_path.is_file()
        and index_path.stat().st_mtime >= dump_path.stat().st_mtime
    ):
        try:
            with open(index_path, encoding="utf-8") as f:
                raw = json.load(f)
            return {int(k): v for k, v in raw.items()}
        except (json.JSONDecodeError, OSError, ValueError):
            pass

    index: dict[int, list[dict[str, Any]]] = {}
    warnings: list[str] = []
    print("→ Indexation des dossiers ParlTrack (rapporteurs)…")
    for dossier in iter_ndjson_zst(dump_path):
        procedure = dossier.get("procedure") or {}
        reference = procedure.get("reference") or ""
        titre = procedure.get("title") or procedure.get("subject") or ""
        url = dossier.get("meta", {}).get("source") or f"https://parltrack.org/dossier/{reference}"
        committees = dossier.get("committees") or []
        for committee in committees:
            rapporteurs = committee.get("rapporteur") or []
            committee_name = committee.get("committee") or committee.get("committee_full") or ""
            for rap in rapporteurs:
                mepref = rap.get("mepref")
                date = rap.get("date") or ""
                uid = _resolve_mepref_as_int(mepref)
                if uid is None:
                    if mepref:
                        warnings.append(f"mepref non résolvable : {mepref!r} (dossier {reference!r})")
                    continue
                index.setdefault(uid, []).append({
                    "reference": reference,
                    "titre": titre,
                    "comite": committee_name,
                    "role": "rapporteur",
                    "date": date[:10] if date else None,
                    "source_url": url,
                })

    if warnings:
        print(f"  [!] {len(warnings)} mepref non résolvable(s) (format hash historique ignoré).",
              file=sys.stderr)

    try:
        index_path.parent.mkdir(parents=True, exist_ok=True)
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump({str(k): v for k, v in index.items()}, f, ensure_ascii=False)
        print(f"  ✓ Index dossiers sauvegardé : {index_path}")
    except OSError:
        pass

    return index


# ---------------------------------------------------------------------------
# Index amendements : mep_id → liste d'amendements
# ---------------------------------------------------------------------------


def _index_amendments_from_dump(
    dump_name: str,
    source_label: str,
    force_download: bool = False,
) -> tuple[dict[int, list[dict[str, Any]]], list[str]]:
    """Construit l'index mep_id → amendements depuis un dump donné.

    Returns:
        (index, warnings) — index dict et liste d'avertissements non bloquants.
    """
    dump_path = ensure_dump(dump_name, force_download)
    if dump_path is None:
        return {}, [f"Dump indisponible : {dump_name}"]

    index: dict[int, list[dict[str, Any]]] = {}
    warnings: list[str] = []
    for amd in iter_ndjson_zst(dump_path):
        amd_id = amd.get("id") or ""
        reference = amd.get("reference") or ""
        date = amd.get("date") or ""
        committee = None
        if isinstance(amd.get("committee"), list):
            committee = ", ".join(amd["committee"])
        elif isinstance(amd.get("committee"), str):
            committee = amd["committee"]
        source_url = (
            amd.get("meta", {}).get("source")
            or f"https://parltrack.org/amendments/{amd_id}"
        )
        meps = amd.get("meps") or []
        if not isinstance(meps, list):
            meps = [meps]
        for mepref in meps:
            uid = _resolve_mepref_as_int(mepref)
            if uid is None:
                if mepref:
                    warnings.append(f"mepref non résolvable : {mepref!r} (amendement {amd_id!r})")
                continue
            index.setdefault(uid, []).append({
                "id": amd_id,
                "reference": reference,
                "comite": committee,
                "date": date[:10] if date else None,
                "source": source_label,
                "source_url": source_url,
            })
    return index, warnings


def build_amendments_index(
    force_download: bool = False,
) -> dict[int, list[dict[str, Any]]]:
    """Construit un index UserID → amendements (plénière + comité fusionnés).

    L'index est mis en cache sur disque.

    Returns:
        dict mep_id (int) → liste d'amendements.
    """
    index_path = PARLTRACK_CACHE_DIR / "index_amendements_par_mep.json"

    plenary_path = PARLTRACK_CACHE_DIR / _DUMP_PLENARY_AMENDMENTS
    committee_path = PARLTRACK_CACHE_DIR / _DUMP_COMMITTEE_AMENDMENTS

    # Vérification de cache : valide uniquement si plus récent que les deux dumps
    if not force_download and index_path.is_file():
        oldest_dump_mtime = None
        for p in [plenary_path, committee_path]:
            if p.is_file():
                t = p.stat().st_mtime
                if oldest_dump_mtime is None or t < oldest_dump_mtime:
                    oldest_dump_mtime = t
        if oldest_dump_mtime is not None and index_path.stat().st_mtime >= oldest_dump_mtime:
            try:
                with open(index_path, encoding="utf-8") as f:
                    raw = json.load(f)
                return {int(k): v for k, v in raw.items()}
            except (json.JSONDecodeError, OSError, ValueError):
                pass

    print("→ Indexation des amendements ParlTrack (plénière + comité)…")
    index: dict[int, list[dict[str, Any]]] = {}
    all_warnings: list[str] = []

    plenary_idx, pw = _index_amendments_from_dump(
        _DUMP_PLENARY_AMENDMENTS, "plenary", force_download
    )
    all_warnings.extend(pw)
    for uid, amds in plenary_idx.items():
        index.setdefault(uid, []).extend(amds)

    committee_idx, cw = _index_amendments_from_dump(
        _DUMP_COMMITTEE_AMENDMENTS, "committee", force_download
    )
    all_warnings.extend(cw)
    for uid, amds in committee_idx.items():
        index.setdefault(uid, []).extend(amds)

    if all_warnings:
        print(f"  [!] {len(all_warnings)} mepref non résolvable(s) ignoré(s).",
              file=sys.stderr)

    try:
        index_path.parent.mkdir(parents=True, exist_ok=True)
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump({str(k): v for k, v in index.items()}, f, ensure_ascii=False)
        print(f"  ✓ Index amendements sauvegardé : {index_path}")
    except OSError:
        pass

    return index


# ---------------------------------------------------------------------------
# API publique : extraction par mep_id
# ---------------------------------------------------------------------------


def get_dossiers_for_mep(
    mep_id: int,
    force_download: bool = False,
) -> list[dict[str, Any]]:
    """Retourne la liste des dossiers où le MEP est rapporteur.

    Args:
        mep_id: UserID ParlTrack (entier).
        force_download: re-télécharger les dumps même si un cache existe.

    Returns:
        Liste de dicts dossier (reference, titre, comite, role, date,
        source_url).  Liste vide si aucun dossier trouvé ou dump
        indisponible.
    """
    index = build_dossiers_index(force_download)
    return index.get(mep_id, [])


def get_amendments_for_mep(
    mep_id: int,
    force_download: bool = False,
) -> list[dict[str, Any]]:
    """Retourne la liste des amendements signés par le MEP.

    Args:
        mep_id: UserID ParlTrack (entier).
        force_download: re-télécharger les dumps même si un cache existe.

    Returns:
        Liste de dicts amendement (id, reference, comite, date, source,
        source_url).  Liste vide si aucun amendement trouvé ou dump
        indisponible.
    """
    index = build_amendments_index(force_download)
    return index.get(mep_id, [])
