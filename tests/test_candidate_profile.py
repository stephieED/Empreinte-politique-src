import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from candidate_profile import build_profile


def test_build_profile_reports_empty_api_payloads():
    with patch("candidate_profile.fetch_identity", return_value={}), patch(
        "candidate_profile.fetch_votes", return_value={}
    ), patch("candidate_profile.time.sleep", return_value=None):
        profile = build_profile("deputes", "slug-inexistant")

    assert profile["identite"] is None
    assert profile["mandats"] == []
    assert profile["votes"] == []
    assert any("identité" in warning for warning in profile["meta"]["warnings"])
    assert any("vote" in warning for warning in profile["meta"]["warnings"])
