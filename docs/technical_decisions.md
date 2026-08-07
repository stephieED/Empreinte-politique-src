<a id="syceron"></a>
## Syceron : remplacement du scraping NosDéputés pour les débats en séance (2026-08-07)

**Contexte** : l'enrichissement des `interventions[]` avec le texte intégral des prises de
parole reposait jusqu'ici sur les métadonnées extraites via l'API NosDéputés (titre,
date, type) sans le texte complet des débats.

**Décision** : intégrer les comptes rendus de séance Syceron (AN Open Data,
`/vp/syceronbrut/syseron.xml.zip`) comme source primaire pour le texte intégral des
interventions en séance (L15, L16, L17).

**Pourquoi Syceron plutôt que le scraping HTML NosDéputés** : le scraping HTML de
NosDéputés/NosDeputes.fr pour les textes de débat est fragile (structure HTML non
contractuelle, susceptible de changer sans préavis, pas de version JSON officielle pour
le texte brut des interventions). Les données Syceron sont publiées directement par
l'Assemblée nationale sur son portail open data officiel sous licence Open (Etalab),
dans un format XML structuré et stable. *Alternative rejetée* : continuer avec le
scraping NosDéputés seul — non retenu car la source officielle AN est disponible,
plus fiable, et homogène avec le reste du pipeline.

**Pourquoi des modules dédiés (`syceron_debates.py`, `parse_syceron.py`) plutôt qu'une
intégration directe dans `candidate_profile.py`** : les ZIP Syceron sont des dumps
volumineux (55–149 MB) contenant des centaines de fichiers XML par législature. Le
téléchargement/cache et le parsing XML représentent des responsabilités distinctes qui
alourdiraient `candidate_profile.py` sans apport pour sa lisibilité. La séparation permet
aussi de tester le parseur de façon indépendante et de réutiliser `syceron_debates.py`
dans d'autres jobs (par exemple analyse thématique groupes) sans dépendre du pipeline
profil. `candidate_profile.py` appelle ces modules via `_build_acteur_interventions_syceron_index`
et `fetch_interventions_syceron`, ce qui reste cohérent avec le pattern déjà établi pour
les autres jeux AN (scrutins, amendements, dossiers).

Voir [`docs/extract-syceron-an.md`](./extract-syceron-an.md) pour la cartographie
complète des URLs, la structure XML et la stratégie de téléchargement.

<a id="hors-perimetre"></a>
## Deferred / out-of-scope investigations

Findings from explored sources that led to a "not now" verdict, with full
rationale — kept here rather than in `ROADMAP.md` so the reasoning survives
even if the backlog entry itself is reworded or dropped.

### Senate votes, amendments, sponsored texts

Explored `data.senat.fr`'s open data catalog (2026). No structured roll-call
vote dataset exists at all (unlike AN's `Scrutins.json.zip`). `ameli.zip`
(amendments) is a raw 717 MB SQL dump (`ameli.sql`), not per-senator
JSON/CSV — impractical to download/parse on every run. `dossiers-legislatifs.csv`
has no author/sponsor field, so per-senator sponsored texts would require
scraping individual `dossier-legislatif` HTML pages (fragile, out of pattern
with the rest of this project's official-JSON-based sources). A full Senate
pipeline equivalent to the AN one is not currently feasible without a fragile
HTML-scraping approach. No official structured vote source has been found
as an alternative either.

### European Parliament — textes_portés / amendements via the official API

Explored the EP Open Data Portal API v2 (2026). `/plenary-documents`
(reports) and `/documents?work_type=AMENDMENT_LIST` exist, but neither
exposes a structured author/rapporteur field referencing a `person/<id>`
MEP URI — the rapporteur name only appears as free text inside multilingual
titles. No server-side filter works (`creator=person/<id>` and text-search
params are all silently ignored). The `/plenary-documents` corpus is
~10-15k documents with no per-item title in the list response, so
identifying a given MEP's reports would require fetching every document's
detail individually — at the API's 500 req/5min rate limit, a full scan
takes 1h30+ per regeneration run. Amendment-list documents are further
compiled per-report batches, not per-amendment/per-signatory records, so
even textual matching would only attribute a whole batch to the report's
rapporteur, not individual amendments to their actual authors.

**Status: superseded.** A follow-up investigation into third-party
aggregators (Parltrack, HowTheyVote) found a viable path — see
`docs/extract-ue.md` for the comparative
feasibility verdict and implementation brief. This entry is kept for
context on why the official-API-only approach was abandoned.

### Ministerial function — precise portfolio title

`mandats[].categorie == "fonction_gouvernementale"` is sourced from the AN
`acteurs_historique` bulk dataset (`organe.codeType == "GOUVERNEMENT"`),
which only identifies *which* government (e.g. "BORNE", "CASTEX") an
elected official belonged to and the dates — not the specific portfolio
title (e.g. "Ministre de l'Intérieur"). No open-data source for the precise
portfolio has been identified yet.

### Extra-parliamentary bodies

Corresponds to the `extra_parlementaire` category already planned in
`schema_pivot.KNOWN_CATEGORIES`, but matching to a profile can only be done
by free-text name (no `acteurRef`) — a real risk of false positives on
homonyms. Not implemented without a careful matching strategy (e.g. name +
group, or accepting partial coverage rather than a bad match).

### Agenda / committee meetings dataset

`.../vp/reunions/Agenda.json.zip` describes committee/plenary meetings
(agenda, bills examined). Organized by body/meeting, not by individual —
more useful for precisely dating when a bill was examined in committee than
for enriching an individual profile directly. No expressed need for this
today.

### Mayors

No dedicated collection module or source identified yet.