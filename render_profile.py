#!/usr/bin/env python3
import argparse
import html
import json
from pathlib import Path
from typing import Any


def load_profile(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def render_html(profile: dict[str, Any]) -> str:
    identite = profile.get("identite") or {}
    mandats = profile.get("mandats") or []
    votes = profile.get("votes") or []
    dossiers = profile.get("dossiers_legislatifs") or []
    interventions = profile.get("interventions") or []

    def bullet_list(items: list[dict[str, Any]], field: str) -> str:
        if not items:
            return "<li>Aucune information disponible.</li>"
        return "".join(
            f"<li>{html.escape(str(item.get(field, '')))}</li>"
            for item in items
            if item.get(field)
        ) or "<li>Aucune information disponible.</li>"

    mandats_html = "".join(
        f"<li><strong>{html.escape(str(m.get('type', 'mandat')))}</strong>: {html.escape(str(m.get('label') or ''))}"
        + (f" — de {html.escape(str(m.get('debut') or ''))}" if m.get("debut") else "")
        + (f" à {html.escape(str(m.get('fin') or ''))}" if m.get("fin") else "")
        + "</li>"
        for m in mandats
    ) or "<li>Aucun mandat renseigné.</li>"

    votes_html = "".join(
        f"<li><strong>{html.escape(str(v.get('date') or ''))}</strong> — {html.escape(str(v.get('titre') or ''))} ({html.escape(str(v.get('position') or ''))})</li>"
        for v in votes
    ) or "<li>Aucun vote renseigné.</li>"

    dossiers_html = "".join(
        f"<li><strong>{html.escape(str(d.get('titre') or ''))}</strong> — {html.escape(str(d.get('date_min') or ''))} / {html.escape(str(d.get('date_max') or ''))}</li>"
        for d in dossiers
    ) or "<li>Aucun dossier législatif renseigné.</li>"

    interventions_html = "".join(
        f"<li><strong>{html.escape(str(i.get('type') or ''))}</strong> — {html.escape(str(i.get('id') or ''))} — <a href='{html.escape(str(i.get('url') or ''))}'>{html.escape(str(i.get('url') or ''))}</a></li>"
        for i in interventions
    ) or "<li>Aucune intervention renseignée.</li>"

    return f"""<!doctype html>
<html lang=\"fr\">
<head>
  <meta charset=\"utf-8\">
  <title>CV politique - {html.escape(str(identite.get('nom_complet') or profile.get('slug', '')))}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 2rem; line-height: 1.5; }}
    h1, h2 {{ color: #1f4e79; }}
    .card {{ border: 1px solid #ddd; padding: 1rem; margin-bottom: 1rem; border-radius: 8px; }}
    ul {{ padding-left: 1.2rem; }}
  </style>
</head>
<body>
  <h1>CV politique - {html.escape(str(identite.get('nom_complet') or profile.get('slug', '')))}</h1>
  <p><strong>Chambre :</strong> {html.escape(str(profile.get('chambre', '')))}</p>

  <div class=\"card\">
    <h2>Identité</h2>
    <ul>
      <li><strong>Nom :</strong> {html.escape(str(identite.get('nom_complet') or ''))}</li>
      <li><strong>Groupe :</strong> {html.escape(str(identite.get('groupe_nom') or identite.get('groupe_sigle') or ''))}</li>
      <li><strong>Profession :</strong> {html.escape(str(identite.get('profession') or ''))}</li>
      <li><strong>Circonscription :</strong> {html.escape(str(identite.get('num_circo') or ''))}</li>
    </ul>
  </div>

  <div class=\"card\">
    <h2>Mandats</h2>
    <ul>{mandats_html}</ul>
  </div>

  <div class=\"card\">
    <h2>Votes</h2>
    <ul>{votes_html}</ul>
  </div>

  <div class=\"card\">
    <h2>Dossiers législatifs</h2>
    <ul>{dossiers_html}</ul>
  </div>

  <div class=\"card\">
    <h2>Interventions</h2>
    <ul>{interventions_html}</ul>
  </div>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Génère une page HTML à partir d’un profil JSON")
    parser.add_argument("profile_json", help="Chemin vers le fichier JSON généré par candidate_profile.py")
    parser.add_argument("--out", default="profile.html", help="Chemin du fichier HTML de sortie")
    args = parser.parse_args()

    profile = load_profile(args.profile_json)
    html_output = render_html(profile)
    out_path = Path(args.out)
    out_path.write_text(html_output, encoding="utf-8")
    print(f"HTML écrit dans {out_path}")


if __name__ == "__main__":
    main()
