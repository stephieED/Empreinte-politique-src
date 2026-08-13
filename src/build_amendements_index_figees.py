#!/usr/bin/env python3
"""
build_amendements_index_figees.py

Construit et committe l'index amendements d'une législature AN définitivement
close (`AN_AMENDEMENTS_LEGISLATURES_FIGEES`, candidate_profile.py) à partir
d'une archive déjà téléchargée localement, hors du budget réseau/temps de la
CI qui échoue de façon récurrente sur ces deux archives (350-650 Mo,
IncompleteRead / HTTP2 PROTOCOL_ERROR répétés — voir
docs/technical_decisions.md#amendements-legislatures-figees).

Usage (depuis la racine du dépôt, après téléchargement manuel de l'archive) :
    python3 src/build_amendements_index_figees.py --legislature 15 --zip /tmp/Amendements_XV.json.zip
    python3 src/build_amendements_index_figees.py --legislature 16 --zip /tmp/Amendements.json.zip

Écrit raw_data/amendements_an_figes/<legislature>/{index_par_acteur.json,
fraicheur.json} — à committer dans le dépôt. `fraicheur.json` porte un
marqueur `figee: true`, lu par `check_quality_gate.py` (section 3d) pour ne
jamais signaler ces deux législatures comme périmées : elles ne seront plus
jamais reconstruites, l'archive source AN étant close.
"""

import argparse
import json
import sys
import time
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from candidate_profile import (  # noqa: E402
    AMENDEMENTS_FRAICHEUR_FILENAME,
    AN_AMENDEMENTS_FIGEES_DIR,
    AN_AMENDEMENTS_LEGISLATURES_FIGEES,
    _parse_amendements_zip,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--legislature",
        required=True,
        choices=sorted(AN_AMENDEMENTS_LEGISLATURES_FIGEES),
        help="Législature figée à (re)construire.",
    )
    parser.add_argument(
        "--zip",
        required=True,
        type=Path,
        help="Archive amendements AN (Amendements.json.zip / Amendements_XV.json.zip) déjà téléchargée localement.",
    )
    args = parser.parse_args()

    if not args.zip.is_file():
        print(f"Archive introuvable : {args.zip}", file=sys.stderr)
        return 1

    print(f"-> Parsing de {args.zip} (législature {args.legislature})...")
    try:
        index = _parse_amendements_zip(args.zip)
    except zipfile.BadZipFile as exc:
        print(f"Archive invalide : {exc}", file=sys.stderr)
        return 1

    out_dir = AN_AMENDEMENTS_FIGEES_DIR / args.legislature
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "index_par_acteur.json", "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False)
    with open(out_dir / AMENDEMENTS_FRAICHEUR_FILENAME, "w", encoding="utf-8") as f:
        json.dump(
            {
                "derniere_construction_reussie": True,
                "horodatage": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "figee": True,
            },
            f,
            ensure_ascii=False,
        )

    print(f"  -> {len(index)} acteur(s) indexé(s), écrit dans {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
