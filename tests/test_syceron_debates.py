"""
tests/test_syceron_debates.py — Tests unitaires pour syceron_debates.py.

Couvre :
  - Cache présent : retourne le chemin sans téléchargement.
  - Législature avec valeur None : retourne None sans accès réseau.
  - Législature inconnue : retourne None sans accès réseau.
  - Téléchargement réussi : crée le fichier et retourne le chemin.
  - Téléchargement échoué : retourne None.
  - force_download=True ignore le cache existant.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import syceron_debates as sd


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_zip_bytes() -> bytes:
    """Retourne quelques octets simulant un contenu ZIP valide."""
    return b"PK\x03\x04" + b"\x00" * 26  # local file header minimal


# ---------------------------------------------------------------------------
# Tests : législature non disponible / inconnue
# ---------------------------------------------------------------------------


def test_unavailable_legislature_returns_none(tmp_path):
    """Législature marquée None dans SYCERON_ZIP_NAMES → retourne None sans téléchargement."""
    with patch.object(sd, "SYCERON_DEBATES_CACHE_DIR", tmp_path):
        result = sd.ensure_debates_zip("14")
    assert result is None


def test_unknown_legislature_returns_none(tmp_path):
    """Législature absente du mapping → retourne None sans téléchargement."""
    with patch.object(sd, "SYCERON_DEBATES_CACHE_DIR", tmp_path):
        result = sd.ensure_debates_zip("99")
    assert result is None


# ---------------------------------------------------------------------------
# Tests : cache présent
# ---------------------------------------------------------------------------


def test_cache_hit_returns_cached_path(tmp_path):
    """ZIP déjà présent → retourné directement sans appel réseau."""
    legislature = "17"
    _, zip_name = sd.SYCERON_ZIP_NAMES[legislature]
    cached = tmp_path / legislature / zip_name
    cached.parent.mkdir(parents=True)
    cached.write_bytes(_fake_zip_bytes())

    with patch.object(sd, "SYCERON_DEBATES_CACHE_DIR", tmp_path), \
         patch("syceron_debates.requests.get") as mock_get:
        result = sd.ensure_debates_zip(legislature, force_download=False)

    assert result == cached
    mock_get.assert_not_called()


def test_force_download_ignores_cache(tmp_path):
    """force_download=True re-télécharge même si le cache existe."""
    legislature = "16"
    _, zip_name = sd.SYCERON_ZIP_NAMES[legislature]
    cached = tmp_path / legislature / zip_name
    cached.parent.mkdir(parents=True)
    cached.write_bytes(_fake_zip_bytes())

    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.iter_content.return_value = [_fake_zip_bytes()]

    with patch.object(sd, "SYCERON_DEBATES_CACHE_DIR", tmp_path), \
         patch("syceron_debates.requests.get", return_value=mock_resp) as mock_get:
        result = sd.ensure_debates_zip(legislature, force_download=True)

    mock_get.assert_called_once()
    assert result == cached


# ---------------------------------------------------------------------------
# Tests : téléchargement réussi
# ---------------------------------------------------------------------------


def test_successful_download_creates_file(tmp_path):
    """Téléchargement réussi → fichier créé dans le cache, chemin retourné."""
    legislature = "15"
    _, zip_name = sd.SYCERON_ZIP_NAMES[legislature]
    expected_path = tmp_path / legislature / zip_name

    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.iter_content.return_value = [_fake_zip_bytes()]

    with patch.object(sd, "SYCERON_DEBATES_CACHE_DIR", tmp_path), \
         patch("syceron_debates.requests.get", return_value=mock_resp):
        result = sd.ensure_debates_zip(legislature, force_download=False)

    assert result == expected_path
    assert expected_path.is_file()


def test_successful_download_correct_url(tmp_path):
    """L'URL construite utilise le bon dataset et le bon nom de fichier."""
    legislature = "17"
    dataset, zip_name = sd.SYCERON_ZIP_NAMES[legislature]
    expected_url = f"{sd.AN_OPENDATA_BASE}/{legislature}/vp/{dataset}/{zip_name}"

    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.iter_content.return_value = [_fake_zip_bytes()]

    with patch.object(sd, "SYCERON_DEBATES_CACHE_DIR", tmp_path), \
         patch("syceron_debates.requests.get", return_value=mock_resp) as mock_get:
        sd.ensure_debates_zip(legislature, force_download=False)

    called_url = mock_get.call_args[0][0]
    assert called_url == expected_url


# ---------------------------------------------------------------------------
# Tests : téléchargement échoué
# ---------------------------------------------------------------------------


def test_download_failure_returns_none(tmp_path):
    """Erreur réseau → retourne None sans lever d'exception."""
    import requests as _requests

    legislature = "17"

    with patch.object(sd, "SYCERON_DEBATES_CACHE_DIR", tmp_path), \
         patch(
             "syceron_debates.requests.get",
             side_effect=_requests.ConnectionError("réseau indisponible"),
         ):
        result = sd.ensure_debates_zip(legislature, force_download=False)

    assert result is None


def test_download_http_error_returns_none(tmp_path):
    """Réponse HTTP 404 → retourne None sans lever d'exception."""
    import requests as _requests

    legislature = "16"

    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = _requests.HTTPError("404 Not Found")

    with patch.object(sd, "SYCERON_DEBATES_CACHE_DIR", tmp_path), \
         patch("syceron_debates.requests.get", return_value=mock_resp):
        result = sd.ensure_debates_zip(legislature, force_download=False)

    assert result is None
