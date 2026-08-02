#!/usr/bin/env python3
"""Module documentation in English."""

import argparse
import datetime
import io
import json
import lzma
import sys
import time
from pathlib import Path
from typing import Any, Iterator, Optional

import requests

from schema_pivot import SCHEMA_VERSION, make_empty_profil

HEADERS = {
    "User-Agent": "cv-politique-mep-profile/0.1 (usage personnel / non commercial)"
}
TIMEOUT = 120  # Translated comment.

PARLTRACK_DUMPS_BASE = "https://parltrack.org/dumps"
PARLTRACK_MEPS_DUMP = "ep_meps.json.lzma"
PARLTRACK_VOTES_DUMP = "ep_votes.json.lzma"

PARLTRACK_CACHE_DIR = Path(".cache") / "parltrack"
MEPS_CACHE_PATH = PARLTRACK_CACHE_DIR / PARLTRACK_MEPS_DUMP
VOTES_CACHE_PATH = PARLTRACK_CACHE_DIR / PARLTRACK_VOTES_DUMP


# ---------------------------------------------------------------------------
# Translated comment.
# ---------------------------------------------------------------------------

def _download_dump(dump_name: str, dest: Path) -> bool:
    """English docstring for  download dump."""
    url = f"{PARLTRACK_DUMPS_BASE}/{dump_name}"
    print(f"→ Téléchargement du dump Parltrack : {url}")
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


def ensure_meps_dump(force_download: bool = False) -> Optional[Path]:
    """English docstring for ensure meps dump."""
    if not force_download and MEPS_CACHE_PATH.is_file():
        mtime = MEPS_CACHE_PATH.stat().st_mtime
        age_days = (time.time() - mtime) / 86400
        print(f"  Dump MEPs en cache (âge : {age_days:.0f} j). "
              "Utiliser --force-download pour rafraîchir.")
        return MEPS_CACHE_PATH

    if _download_dump(PARLTRACK_MEPS_DUMP, MEPS_CACHE_PATH):
        return MEPS_CACHE_PATH
    return None


def ensure_votes_dump(force_download: bool = False) -> Optional[Path]:
    """English docstring for ensure votes dump."""
    if not force_download and VOTES_CACHE_PATH.is_file():
        mtime = VOTES_CACHE_PATH.stat().st_mtime
        age_days = (time.time() - mtime) / 86400
        print(f"  Dump votes en cache (âge : {age_days:.0f} j). "
              "Utiliser --force-download pour rafraîchir.")
        return VOTES_CACHE_PATH

    if _download_dump(PARLTRACK_VOTES_DUMP, VOTES_CACHE_PATH):
        return VOTES_CACHE_PATH
    return None


def get_cache_date(dump_path: Path) -> Optional[str]:
    """English docstring for get cache date."""
    if not dump_path.is_file():
        return None
    mtime = dump_path.stat().st_mtime
    return datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%dT%H:%M:%S")


# ---------------------------------------------------------------------------
# Lecture NDJSON LZMA
# ---------------------------------------------------------------------------

def _iter_ndjson_lzma(path: Path) -> Iterator[dict[str, Any]]:
    """English docstring for  iter ndjson lzma."""
    with lzma.open(path, "rb") as lzf:
        reader = io.TextIOWrapper(lzf, encoding="utf-8")
        for line in reader:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


# ---------------------------------------------------------------------------
# Translated comment.
# ---------------------------------------------------------------------------

def _name_matches(mep: dict[str, Any], query: str) -> bool:
    """English docstring for  name matches."""  import unicodedata

    def _norm(s: str) -> str:
        decomposed = unicodedata.normalize("NFKD", s.lower())
        return "".join(c for c in decomposed if not unicodedata.combining(c))

    query_norm = _norm(query)
    name_block = mep.get("Name") or {}
    full = _norm(name_block.get("full") or "")
    sur = _norm(name_block.get("sur") or "")
    family = _norm(name_block.get("family") or "")
    aliases = [_norm(a) for a in (name_block.get("aliases") or []) if a]
    return any(query_norm in candidate for candidate in ([full, sur, family] + aliases) if candidate)


def find_mep(
    name: Optional[str] = None,
    ep_id: Optional[int] = None,
    force_download: bool = False,
) -> Optional[dict[str, Any]]:
    """English docstring for find mep."""
    if not name and ep_id is None:
        raise ValueError("Fournir au moins name ou ep_id.")

    dump_path = ensure_meps_dump(force_download)
    if dump_path is None:
        return None

    for mep in _iter_ndjson_lzma(dump_path):
        if ep_id is not None and mep.get("UserID") == ep_id:
            return mep
        if name and _name_matches(mep, name):
            return mep

    return None


def list_meps_fr(force_download: bool = False) -> list[dict[str, str]]:
    """English docstring for list meps fr."""
    dump_path = ensure_meps_dump(force_download)
    if dump_path is None:
        return []

    result: list[dict[str, str]] = []
    for mep in _iter_ndjson_lzma(dump_path):
        constituencies = mep.get("Constituencies") or []
        is_french = any(
            (c.get("country") or "").lower() in ("france", "fr")
            for c in constituencies
        )
        if not is_french:
            continue
        name_block = mep.get("Name") or {}
        groups = mep.get("Groups") or []
        last_group = groups[-1] if groups else {}
        result.append({
            "nom": name_block.get("full") or "",
            "ep_id": str(mep.get("UserID") or ""),
            "groupe": last_group.get("groupid") or "",
            "actif": str(mep.get("active", False)),
        })
    return result


# ---------------------------------------------------------------------------
# Translated comment.
# ---------------------------------------------------------------------------

def _build_mep_vote_index(force_download: bool = False) -> dict[int, list[dict[str, Any]]]:
    """English docstring for  build mep vote index."""
    index_path = PARLTRACK_CACHE_DIR / "index_votes_par_mep.json"

    dump_path = ensure_votes_dump(force_download)
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
            # Translated comment.
            return {int(k): v for k, v in raw.items()}
        except (json.JSONDecodeError, OSError, ValueError):
            pass  # cache corrompu : on reconstruit

    index: dict[int, list[dict[str, Any]]] = {}
    print("→ Indexation des votes Parltrack (opération longue à la première exécution)…")
    for vote_record in _iter_ndjson_lzma(dump_path):
        votes_block = vote_record.get("votes") or {}
        ts = vote_record.get("ts") or ""
        title = vote_record.get("title") or vote_record.get("url") or ""
        url = vote_record.get("url") or ""
        epid = vote_record.get("epid")

        for position, group_label in (
            ("pour", "For"),
            ("contre", "Against"),
            ("abstention", "Abstain"),
        ):
            members = votes_block.get(group_label) or []
            if isinstance(members, dict):
                members = [members]
            for member in members:
                if not isinstance(member, dict):
                    continue
                uid = member.get("UserID") or member.get("userid")
                if uid is None:
                    continue
                try:
                    uid = int(uid)
                except (TypeError, ValueError):
                    continue
                index.setdefault(uid, []).append({
                    "epid": epid,
                    "date": ts[:10] if ts else None,
                    "titre": title,
                    "position": position,
                    "source_url": url,
                })

    try:
        index_path.parent.mkdir(parents=True, exist_ok=True)
        # Translated comment.
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump({str(k): v for k, v in index.items()}, f, ensure_ascii=False)
        print(f"  ✓ Index votes sauvegardé : {index_path}")
    except OSError:
        pass

    return index


# ---------------------------------------------------------------------------
# Normalisation Parltrack → pivot
# ---------------------------------------------------------------------------

def normalize_parltrack(mep_raw: dict[str, Any], votes: Optional[list[dict[str, Any]]] = None) -> dict[str, Any]:
    """English docstring for normalize parltrack."""
    ep_id = mep_raw.get("UserID")
    name_block = mep_raw.get("Name") or {}
    nom = name_block.get("full") or name_block.get("sur") or f"MEP #{ep_id}"
    # Translated comment.
    # Translated comment.
    # Handles multi-word surnames like "VAN DEN BERG Jean".
    nom_parts = nom.split()
    if len(nom_parts) >= 2:
        # Find the split point: last consecutive uppercase word
        uppercase_count = 0
        for part in nom_parts:
            if part.isupper() and len(part) > 1:
                uppercase_count += 1
            else:
                break
        if uppercase_count > 0 and uppercase_count < len(nom_parts):
            surname_parts = nom_parts[:uppercase_count]
            given_parts = nom_parts[uppercase_count:]
            surname = " ".join(p.capitalize() for p in surname_parts)
            given = " ".join(given_parts)
            nom = f"{given} {surname}"

    profil: dict[str, Any] = make_empty_profil(f"parltrack:{ep_id}", nom)
    profil["chambre"] = "PE"

    # Groupe politique actuel (dernier enregistrement)
    groups = mep_raw.get("Groups") or []
    if groups:
        last_group = groups[-1]
        profil["groupe"] = last_group.get("Organization") or last_group.get("groupid")

    # Translated comment.
    constituencies = mep_raw.get("Constituencies") or []
    if constituencies:
        last_cst = constituencies[-1]
        profil["parti"] = last_cst.get("party")

    # Translated comment.
    synchro_le = time.strftime("%Y-%m-%dT%H:%M:%S")
    cache_date = get_cache_date(MEPS_CACHE_PATH)
    profil["sources"] = [
        {
            "type": "parltrack",
            "url": f"https://parltrack.org/mep/{ep_id}",
            "synchro_le": cache_date or synchro_le,
        }
    ]

    # Mandats : groupes politiques
    mandats: list[dict[str, Any]] = []
    for g in groups:
        fin = g.get("end")
        mandats.append({
            "label": g.get("Organization") or g.get("groupid") or "",
            # Translated comment.
            # Translated comment.
            "categorie": "autre",
            "fonction": "membre",
            "debut": g.get("start"),
            "fin": fin if fin and fin != "9999-12-31" else None,
            "actif": not fin or fin == "9999-12-31",
            "source_url": None,
        })

    # Translated comment.
    committees = mep_raw.get("Committees") or []
    for c in committees:
        fin = c.get("end")
        mandats.append({
            "label": c.get("Organization") or c.get("abbr") or "",
            "categorie": "commission",
            "fonction": (c.get("role") or "membre").lower(),
            "debut": c.get("start"),
            "fin": fin if fin and fin != "9999-12-31" else None,
            "actif": not fin or fin == "9999-12-31",
            "source_url": None,
        })
    profil["mandats"] = mandats

    # Votes
    if votes:
        profil["votes"] = [
            {
                "date": v.get("date"),
                "texte": v.get("titre") or "",
                "position": v.get("position") or "",
                "numero_scrutin": str(v.get("epid")) if v.get("epid") is not None else None,
                "sort": None,
                "source_url": v.get("source_url"),
            }
            for v in votes
        ]
        if profil["votes"]:
            profil["sources"].append({
                "type": "parltrack",
                "url": "https://parltrack.org/dumps",
                "synchro_le": get_cache_date(VOTES_CACHE_PATH) or synchro_le,
            })

    profil["meta"]["licence_donnees"] = "Open Data — Parltrack (CC0 / Open Database License)"
    if not mep_raw.get("active"):
        profil["meta"]["warnings"].append("MEP marqué inactif dans le dump Parltrack.")

    return profil


# ---------------------------------------------------------------------------
# Translated comment.
# ---------------------------------------------------------------------------

def build_mep_profile(
    name: Optional[str] = None,
    ep_id: Optional[int] = None,
    include_votes: bool = True,
    force_download: bool = False,
) -> Optional[dict[str, Any]]:
    """English docstring for build mep profile."""
    mep_raw = find_mep(name=name, ep_id=ep_id, force_download=force_download)
    if mep_raw is None:
        print(f"  [!] MEP introuvable : name={name!r}, ep_id={ep_id!r}", file=sys.stderr)
        return None

    votes: list[dict[str, Any]] = []
    if include_votes:
        uid = mep_raw.get("UserID")
        if uid is not None:
            vote_index = _build_mep_vote_index(force_download)
            votes = vote_index.get(uid, [])

    return normalize_parltrack(mep_raw, votes)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--name", help="Nom du MEP (recherche approximative)")
    group.add_argument("--ep-id", type=int, help="UserID Parltrack du MEP")
    group.add_argument("--list", action="store_true", dest="list_meps",
                       help="Lister les MEPs français dans le dump")
    group.add_argument("--show-cache-date", action="store_true",
                       help="Afficher la date des dumps en cache (pour vérifier la fraîcheur)")
    parser.add_argument("--out", help="Fichier de sortie JSON pivot (défaut : stdout)")
    parser.add_argument("--no-votes", action="store_true",
                        help="Ne pas inclure les votes (plus rapide)")
    parser.add_argument("--force-download", action="store_true",
                        help="Re-télécharger les dumps même si un cache existe")
    args = parser.parse_args()

    if args.show_cache_date:
        for name, path in [("MEPs", MEPS_CACHE_PATH), ("Votes", VOTES_CACHE_PATH)]:
            date = get_cache_date(path)
            print(f"  Dump {name} : {date or 'absent'} ({path})")
        return

    if args.list_meps:
        meps = list_meps_fr(force_download=args.force_download)
        print(f"{'Nom':<35} {'EP-ID':<8} {'Groupe':<12} Actif")
        print("-" * 65)
        for m in sorted(meps, key=lambda x: x["nom"]):
            print(f"{m['nom']:<35} {m['ep_id']:<8} {m['groupe']:<12} {m['actif']}")
        print(f"\n{len(meps)} MEPs français.")
        return

    if not args.name and args.ep_id is None:
        parser.error("Fournir --name ou --ep-id (ou --list / --show-cache-date).")

    profil = build_mep_profile(
        name=args.name,
        ep_id=args.ep_id,
        include_votes=not args.no_votes,
        force_download=args.force_download,
    )
    if profil is None:
        sys.exit(1)

    output = json.dumps(profil, ensure_ascii=False, indent=2)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output, encoding="utf-8")
        print(f"✓ Profil MEP écrit dans {args.out}")
    else:
        print(output)


if __name__ == "__main__":
    main()
