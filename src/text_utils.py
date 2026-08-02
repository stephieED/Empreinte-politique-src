#!/usr/bin/env python3
"""Module documentation in English."""

import re
import unicodedata


def slugify(text: str) -> str:
    """English docstring for slugify."""  decomposed = unicodedata.normalize("NFKD", text)
    ascii_only = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", ascii_only.lower())).strip("-")
