"""
tests/test_parltrack_dumps.py — Tests unitaires pour parltrack_dumps.py.

Ces tests utilisent des données fictives compressées en mémoire pour éviter
tout accès réseau ou lecture de fichiers réels.
"""

import io
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import zstandard as zstd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from parltrack_dumps import (
    _resolve_mepref_as_int,
    build_amendments_index,
    build_dossiers_index,
    get_amendments_for_mep,
    get_dossiers_for_mep,
    iter_ndjson_zst,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_zst_bytes(records: list[dict]) -> bytes:
    """Compresse une liste de dicts en NDJSON .zst en mémoire."""
    ndjson = "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n"
    cctx = zstd.ZstdCompressor()
    return cctx.compress(ndjson.encode("utf-8"))


def _write_zst_file(path: Path, records: list[dict]) -> None:
    """Écrit un fichier .zst NDJSON fictif sur disque."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_make_zst_bytes(records))


# ---------------------------------------------------------------------------
# Tests : iter_ndjson_zst
# ---------------------------------------------------------------------------


def test_iter_ndjson_zst_basic(tmp_path):
    """Lecture streaming d'un fichier .zst minimal."""
    records = [{"a": 1}, {"b": 2}]
    p = tmp_path / "test.json.zst"
    _write_zst_file(p, records)
    result = list(iter_ndjson_zst(p))
    assert result == records


def test_iter_ndjson_zst_empty_lines(tmp_path):
    """Les lignes vides sont ignorées sans erreur."""
    ndjson = '{"x": 1}\n\n{"y": 2}\n'
    cctx = zstd.ZstdCompressor()
    data = cctx.compress(ndjson.encode("utf-8"))
    p = tmp_path / "test.json.zst"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    result = list(iter_ndjson_zst(p))
    assert result == [{"x": 1}, {"y": 2}]


def test_iter_ndjson_zst_invalid_json_skipped(tmp_path):
    """Les lignes JSON invalides sont ignorées sans lever d'exception."""
    ndjson = '{"ok": true}\nNOT_JSON\n{"ok2": true}\n'
    cctx = zstd.ZstdCompressor()
    data = cctx.compress(ndjson.encode("utf-8"))
    p = tmp_path / "test.json.zst"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    result = list(iter_ndjson_zst(p))
    assert result == [{"ok": True}, {"ok2": True}]


# ---------------------------------------------------------------------------
# Tests : _resolve_mepref_as_int
# ---------------------------------------------------------------------------


def test_resolve_mepref_int():
    assert _resolve_mepref_as_int(131580) == 131580


def test_resolve_mepref_str_int():
    assert _resolve_mepref_as_int("131580") == 131580


def test_resolve_mepref_hash_returns_none():
    """Un hash hexadécimal historique de 24 caractères retourne None."""
    assert _resolve_mepref_as_int("5479da7eb01f9fc4c71bb6a1") is None


def test_resolve_mepref_none():
    assert _resolve_mepref_as_int(None) is None


def test_resolve_mepref_garbage():
    assert _resolve_mepref_as_int("not_a_number") is None


# ---------------------------------------------------------------------------
# Tests : build_dossiers_index
# ---------------------------------------------------------------------------


def _dossier_record(reference: str, mepref: int, titre: str = "Titre test") -> dict:
    return {
        "procedure": {"reference": reference, "title": titre},
        "committees": [
            {
                "committee": "AFET",
                "rapporteur": [{"mepref": mepref, "date": "2024-03-15"}],
            }
        ],
        "meta": {"source": f"https://parltrack.org/dossier/{reference}"},
    }


def test_build_dossiers_index_known_meps(tmp_path):
    """L'index rapporteur contient les 3 MEP IDs tests."""
    records = [
        _dossier_record("2024/0001(COD)", 131580, "Dossier Bardella"),
        _dossier_record("2020/0001(INI)", 28210, "Dossier Le Pen"),
        _dossier_record("2020/0002(INI)", 96742, "Dossier Mélenchon"),
    ]
    zst_path = tmp_path / "ep_dossiers.json.zst"
    _write_zst_file(zst_path, records)

    with patch("parltrack_dumps.ensure_dump", return_value=zst_path), \
         patch("parltrack_dumps.PARLTRACK_CACHE_DIR", tmp_path):
        index = build_dossiers_index(force_download=False)

    assert 131580 in index
    assert 28210 in index
    assert 96742 in index
    assert index[131580][0]["role"] == "rapporteur"
    assert index[131580][0]["reference"] == "2024/0001(COD)"


def test_build_dossiers_index_hash_mepref_ignored(tmp_path):
    """Un mepref hash est ignoré sans lever d'exception, pas ajouté à l'index."""
    records = [
        {
            "procedure": {"reference": "2014/0802(NLE)", "title": "Ancien dossier"},
            "committees": [
                {
                    "committee": "AFET",
                    "rapporteur": [{"mepref": "5479da7eb01f9fc4c71bb6a1", "date": "2014-01-01"}],
                }
            ],
            "meta": {"source": "https://parltrack.org/dossier/2014/0802(NLE)"},
        }
    ]
    zst_path = tmp_path / "ep_dossiers.json.zst"
    _write_zst_file(zst_path, records)

    with patch("parltrack_dumps.ensure_dump", return_value=zst_path), \
         patch("parltrack_dumps.PARLTRACK_CACHE_DIR", tmp_path):
        index = build_dossiers_index(force_download=False)

    assert len(index) == 0


def test_build_dossiers_index_cache_used(tmp_path):
    """L'index JSON sur disque est utilisé si plus récent que le dump."""
    import time as _time

    cached = {
        "131580": [{"reference": "from_cache", "titre": "Cached", "role": "rapporteur",
                    "comite": "AFET", "date": "2024-01-01",
                    "source_url": "https://parltrack.org/dossier/from_cache"}]
    }
    index_path = tmp_path / "index_dossiers_rapporteur.json"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(cached), encoding="utf-8")

    # Créer un dump fictif plus ancien
    dump_path = tmp_path / "ep_dossiers.json.zst"
    _write_zst_file(dump_path, [])
    # S'assurer que le dump est plus ancien que le cache
    import os
    old_time = _time.time() - 100
    os.utime(dump_path, (old_time, old_time))

    with patch("parltrack_dumps.ensure_dump", return_value=dump_path), \
         patch("parltrack_dumps.PARLTRACK_CACHE_DIR", tmp_path):
        index = build_dossiers_index(force_download=False)

    assert 131580 in index
    assert index[131580][0]["reference"] == "from_cache"


# ---------------------------------------------------------------------------
# Tests : build_amendments_index
# ---------------------------------------------------------------------------


def _plenary_amd_record(amd_id: str, reference: str, mep_id: int) -> dict:
    return {
        "id": amd_id,
        "reference": reference,
        "date": "2023-05-10",
        "meps": [mep_id],
        "meta": {"source": f"https://parltrack.org/amendments/{amd_id}"},
    }


def _committee_amd_record(amd_id: str, reference: str, mep_id: int) -> dict:
    return {
        "id": amd_id,
        "reference": reference,
        "committee": ["AFET"],
        "date": "2023-06-01",
        "meps": [mep_id],
        "meta": {"source": f"https://parltrack.org/amendments/{amd_id}"},
    }


def test_build_amendments_index_bardella(tmp_path):
    """Jordan Bardella (131580) : amendements plénière + comité."""
    plenary = [
        _plenary_amd_record(f"A9-0052/2023-{i}", "2020/2202(INI)", 131580)
        for i in range(15)
    ]
    committee = [
        _committee_amd_record(f"PE529.899-{i}", "2014/2021(INI)", 131580)
        for i in range(510)
    ]

    plenary_path = tmp_path / "ep_plenary_amendments.json.zst"
    committee_path = tmp_path / "ep_amendments.json.zst"
    _write_zst_file(plenary_path, plenary)
    _write_zst_file(committee_path, committee)

    with patch("parltrack_dumps.ensure_dump") as mock_ensure, \
         patch("parltrack_dumps.PARLTRACK_CACHE_DIR", tmp_path):
        def _side(name, force_download=False):
            if "plenary" in name:
                return plenary_path
            return committee_path
        mock_ensure.side_effect = _side
        index = build_amendments_index(force_download=True)

    assert 131580 in index
    assert len(index[131580]) == 15 + 510


def test_build_amendments_index_multiple_meps(tmp_path):
    """Marine Le Pen (28210) et Mélenchon (96742) ont aussi des amendements."""
    plenary = [_plenary_amd_record("AMD-1", "2020/2202(INI)", 28210)]
    committee = [
        _committee_amd_record(f"PE001-{i}", "2014/2021(INI)", 96742)
        for i in range(154)
    ]

    plenary_path = tmp_path / "ep_plenary_amendments.json.zst"
    committee_path = tmp_path / "ep_amendments.json.zst"
    _write_zst_file(plenary_path, plenary)
    _write_zst_file(committee_path, committee)

    with patch("parltrack_dumps.ensure_dump") as mock_ensure, \
         patch("parltrack_dumps.PARLTRACK_CACHE_DIR", tmp_path):
        def _side(name, force_download=False):
            if "plenary" in name:
                return plenary_path
            return committee_path
        mock_ensure.side_effect = _side
        index = build_amendments_index(force_download=True)

    assert 28210 in index
    assert len(index[28210]) == 1
    assert 96742 in index
    assert len(index[96742]) == 154


def test_build_amendments_index_missing_dump_returns_empty(tmp_path):
    """Si un dump est indisponible (None), retourne dict vide sans exception."""
    with patch("parltrack_dumps.ensure_dump", return_value=None), \
         patch("parltrack_dumps.PARLTRACK_CACHE_DIR", tmp_path):
        index = build_amendments_index(force_download=False)
    assert index == {}


# ---------------------------------------------------------------------------
# Tests : get_dossiers_for_mep / get_amendments_for_mep (API publique)
# ---------------------------------------------------------------------------


def test_get_dossiers_for_mep_unknown_returns_empty(tmp_path):
    """Un MEP ID inconnu retourne une liste vide."""
    records = [_dossier_record("2024/0001(COD)", 131580, "Dossier")]
    zst_path = tmp_path / "ep_dossiers.json.zst"
    _write_zst_file(zst_path, records)

    with patch("parltrack_dumps.ensure_dump", return_value=zst_path), \
         patch("parltrack_dumps.PARLTRACK_CACHE_DIR", tmp_path):
        result = get_dossiers_for_mep(99999, force_download=False)

    assert result == []


def test_get_amendments_for_mep_known(tmp_path):
    """get_amendments_for_mep retourne les amendements du MEP."""
    plenary = [_plenary_amd_record("A9-0001", "2020/0001(INI)", 28210)]
    committee = []

    plenary_path = tmp_path / "ep_plenary_amendments.json.zst"
    committee_path = tmp_path / "ep_amendments.json.zst"
    _write_zst_file(plenary_path, plenary)
    _write_zst_file(committee_path, committee)

    with patch("parltrack_dumps.ensure_dump") as mock_ensure, \
         patch("parltrack_dumps.PARLTRACK_CACHE_DIR", tmp_path):
        def _side(name, force_download=False):
            if "plenary" in name:
                return plenary_path
            return committee_path
        mock_ensure.side_effect = _side
        result = get_amendments_for_mep(28210, force_download=True)

    assert len(result) == 1
    assert result[0]["id"] == "A9-0001"
