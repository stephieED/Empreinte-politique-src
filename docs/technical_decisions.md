<a id="debats-officiels"></a>
## Débats officiels — intégration de la source Syceron (2026-08-06)

**Contexte.** Les interventions en séance plénière étaient collectées
exclusivement via l'API de recherche NosDéputés.fr (endpoint
`/api/recherche/Intervention`). Cette approche reposait sur du scraping HTML
de pages de séance pour identifier l'orateur et extraire le sujet (`sujet`,
`mots_cles`), ce qui la rendait fragile face aux mises à jour du site.

**Décision.** Intégrer le jeu de données verbatim Syceron publié par l'AN sur
son portail Open Data (`.../17/vp/sycerondbk/Debats.json.zip`). Cette source
attribue chaque intervention à un `acteurRef` (`PAxxxxx`), ce qui permet une
indexation directe sans fuzzy-matching sur les noms. Elle est disponible pour
les législatures 16 et 17 ; les législatures antérieures restent couvertes par
le fallback NosDéputés.

**Architecture retenue :**

- `fetch_debats_officiels` télécharge et met en cache le ZIP par législature.
- `_build_acteur_debats_index` construit un index `acteurRef -> interventions`.
- `build_profile()` fusionne les entrées Syceron dans `profile["interventions"]`
  avec `source="an_officiel"` et préserve le fallback NosDéputés quand la
  source officielle est absente.
- Un warning qualité `"debats_officiels_indisponibles"` est émis si le fallback
  est utilisé (cohérent avec la logique de la quality gate).

**Alternative écartée.** Garder uniquement NosDéputés : risque de rupture à
chaque refonte du site, plus dépendance à du scraping HTML fragile pour
l'identification de l'orateur. La source AN officielle est préférable pour la
traçabilité (règle 2, AGENTS.md §2).

**Périmètre.** Seul le format JSON `sycerondbk` est intégré, disponible pour
les législatures 16 et 17. La législature 15 dispose d'un dump XML brut
(`syceronbrut`, ~149 MB) dont la structure est incompatible avec l'indexation
directe par `acteurRef` — non implémenté pour l'instant. Pour les législatures
15 et antérieures, le fallback NosDéputés reste la seule source disponible.

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