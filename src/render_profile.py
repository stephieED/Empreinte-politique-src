#!/usr/bin/env python3
"""
render_profile.py

Convertit un profil JSON généré par candidate_profile.py en une page HTML
lisible (fiche "CV politique"). Utilisé directement en CLI, ou importé par
generate_all_profiles.py pour générer les pages de tous les candidats d'un coup.

Usage :
    python src/render_profile.py data/profiles/jean-luc-melenchon.json
    python src/render_profile.py data/profiles/jean-luc-melenchon.json --out data/profiles/jean-luc-melenchon.html
"""
import argparse
import html
import json
from pathlib import Path
from typing import Any


def load_profile(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


CATEGORIE_LABELS = {
    "mandat_electif": "Mandat électif",
    "commission": "Commission / mission",
    "groupe_amitie": "Groupe d'amitié",
    "extra_parlementaire": "Engagement extra-parlementaire",
    "autre": "Autre",
}

TYPE_DETAIL_LABELS = {
    "loi": "Débat sur un texte de loi",
    "question": "Question au gouvernement",
}

FORMAT_LABELS = {
    "reaction_courte": "Réaction courte",
    "prise_de_parole_developpee": "Prise de parole développée",
}


def _render_mandat(m: dict[str, Any]) -> str:
    label = html.escape(str(m.get("label") or ""))
    type_ = html.escape(str(m.get("type") or "membre"))
    categorie_label = html.escape(str(CATEGORIE_LABELS.get(m.get("categorie"), m.get("categorie") or "")))
    dates = ""
    if m.get("debut") or m.get("fin"):
        fin_label = html.escape(str(m.get("fin"))) if m.get("fin") else ("en cours" if m.get("actif") else "?")
        dates = f" — {html.escape(str(m.get('debut') or '?'))} → {fin_label}"
    return f"<li><strong>{type_}</strong> — {label} <em>({categorie_label})</em>{dates}</li>"


def _render_intervention(i: dict[str, Any]) -> str:
    parts = [f"<strong>{html.escape(str(i.get('date') or i.get('created_at') or ''))}</strong>"]
    type_detail = i.get("type_detail")
    if type_detail:
        parts.append(f"<em>{html.escape(str(TYPE_DETAIL_LABELS.get(type_detail, type_detail)))}</em>")
    fonction = i.get("fonction")
    if fonction:
        parts.append(f"<span style='color:#8a5a00;'>en tant que {html.escape(str(fonction))}</span>")
    fmt = i.get("format")
    if fmt:
        style = "font-weight:bold;" if fmt == "prise_de_parole_developpee" else "font-style:italic;color:#666;"
        parts.append(f"<span style='{style}'>{html.escape(str(FORMAT_LABELS.get(fmt, fmt)))}</span>")
    elif isinstance(i.get("classification"), dict) and i.get("classification", {}).get("mode") == "prise_de_parole":
        parts.append("<span style='font-weight:bold;'>prise de parole</span>")
    if i.get("sujet"):
        parts.append(f"Sujet: {html.escape(str(i.get('sujet')))}")
    if i.get("mots_cles"):
        parts.append(f"Mots-clés: {html.escape(', '.join(i.get('mots_cles')))}")
    if i.get("texte"):
        parts.append(html.escape(str(i.get("texte"))[:180]))
    url = i.get("url_detail") or i.get("url")
    if url:
        parts.append(f"<a href='{html.escape(str(url))}'>{html.escape(str(url))}</a>")
    return "<li>" + " — ".join(parts) + "</li>"


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

    mandats_html = "".join(_render_mandat(m) for m in mandats) or "<li>Aucun mandat renseigné.</li>"

    votes_html = "".join(
        f"<li><strong>{html.escape(str(v.get('date') or ''))}</strong> — {html.escape(str(v.get('titre') or ''))} ({html.escape(str(v.get('position') or ''))})</li>"
        for v in votes
    ) or "<li>Aucun vote renseigné.</li>"

    dossiers_html = "".join(
        f"<li><strong>{html.escape(str(d.get('titre') or ''))}</strong> — {html.escape(str(d.get('date_min') or ''))} / {html.escape(str(d.get('date_max') or ''))}"
        + (f" <em>({html.escape(str(d.get('legislature') or ''))})</em>" if d.get("legislature") else "")
        + "</li>"
        for d in dossiers
    ) or "<li>Aucun dossier législatif renseigné.</li>"

    interventions_html = "".join(_render_intervention(i) for i in interventions) or "<li>Aucune intervention renseignée.</li>"

    votes_source_html = (
        f"<p><em>Source : {html.escape(str(profile.get('votes_source')))}</em></p>"
        if profile.get("votes_source")
        else ""
    )

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
    {votes_source_html}
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
    parser.add_argument("--out", help="Chemin du fichier HTML de sortie (défaut : même chemin que profile_json, avec l'extension .html)")
    args = parser.parse_args()

    profile = load_profile(args.profile_json)
    html_output = render_html(profile)
    out_path = Path(args.out) if args.out else Path(args.profile_json).with_suffix(".html")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html_output, encoding="utf-8")
    print(f"HTML écrit dans {out_path}")


if __name__ == "__main__":
    main()
