#!/usr/bin/env bash
# Équivalent local de .github/workflows/generate-data.yml (workflow_dispatch),
# sans passer par GitHub Actions — utile pour contourner les gels runner
# ("shutdown signal") en générant le jeu de données complet sur sa propre
# machine. Reproduit l'ordre et les commandes exactes des jobs CI ; diffère
# uniquement là où l'orchestration GH Actions (artifacts, matrix par candidat)
# n'a pas d'équivalent utile en local :
#   - extract-an tourne ici sur TOUS les candidats en une fois (pas de matrix
#     par candidat : inutile hors CI, où son seul but est d'isoler la perte
#     en cas de gel runner).
#   - Pas d'étape merge_profile.py --dirs : chaque source écrit déjà
#     directement dans raw_data/profiles/ (fusion additive native de
#     generate_all_profiles.py), il n'y a rien à re-fusionner depuis des
#     artifacts séparés puisque tout tourne sur le même filesystem.
#   - Aucun commit/push automatique (dernière étape du job merge-and-pivot) :
#     vérifier le résultat, puis committer/pousser manuellement si satisfait.
#
# Chaque étape a le même comportement "continue-on-error" que son job CI
# correspondant (voir commentaires) : un échec n'interrompt pas le reste.
#
# Options d'entrée, mêmes défauts que workflow_dispatch dans generate-data.yml :
#   FRESH_RUN=false|true              (défaut: false — fusion additive)
#   THRESHOLD=<n>                     (défaut: 3)
#   WORKERS=<n>                       (défaut: 1 — séquentiel, cf. retour
#                                      d'expérience utilisatrice sur la
#                                      parallélisation, docs/technical_decisions.md)
#   EXTRACT_INTERVENTIONS=false|true  (défaut: false)
#   MAX_PAGES=<n>                     (défaut: 5, ignoré si EXTRACT_INTERVENTIONS=false)
#   ROSTER_EXTRACTION_LIMIT=<n>       (défaut: 20, 0 = pas de limite)
#   BACKGROUND=true|false             (défaut: true — se relance soi-même via
#                                      nohup et rend la main immédiatement ;
#                                      false = tourne au premier plan, logs
#                                      affichés en direct dans le terminal)
#
# Logs : toujours écrits dans logs/generate_data_local_<horodatage>.log
# (dossier créé si absent, git-ignoré comme .cache/) — en plus de la sortie
# terminal si BACKGROUND=false, à la place si BACKGROUND=true (nohup).
#
# Exemple : WORKERS=4 ROSTER_EXTRACTION_LIMIT=0 ./scripts/generate_data_local.sh
# Suivre la progression d'un run en arrière-plan : tail -f logs/generate_data_local_*.log
# Arrêter un run en arrière-plan : kill <PID affiché au lancement>

set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

mkdir -p logs

# Relance auto en arrière-plan (nohup) sauf si déjà relancé (_GDL_CHILD, garde
# anti-récursion) ou BACKGROUND=false explicite (mode premier plan / debug).
if [ "${BACKGROUND:-true}" = "true" ] && [ -z "${_GDL_CHILD:-}" ]; then
  LOG_FILE="logs/generate_data_local_$(date -u +%Y%m%dT%H%M%SZ).log"
  echo "Lancement en arrière-plan — logs : $LOG_FILE"
  # < /dev/null explicite : un stdin hérité fermé/invalide (terminal non
  # interactif, panneau IDE...) fait échouer bash au relancement ("error
  # reading input file: Bad file descriptor") — nohup ne redirige stdin que
  # s'il détecte un terminal, donc ne suffit pas seul dans ce cas.
  _GDL_CHILD=1 nohup "$0" "$@" < /dev/null > "$LOG_FILE" 2>&1 &
  BG_PID=$!
  disown
  echo "PID : $BG_PID"
  echo "Suivre : tail -f $LOG_FILE"
  echo "Arrêter : kill $BG_PID"
  exit 0
fi

FRESH_RUN="${FRESH_RUN:-false}"
THRESHOLD="${THRESHOLD:-3}"
WORKERS="${WORKERS:-1}"
EXTRACT_INTERVENTIONS="${EXTRACT_INTERVENTIONS:-false}"
MAX_PAGES="${MAX_PAGES:-5}"
ROSTER_EXTRACTION_LIMIT="${ROSTER_EXTRACTION_LIMIT:-20}"

if [ -f .venv/bin/activate ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

export PYTHONUNBUFFERED=1

# Mode premier plan (BACKGROUND=false) : sortie dupliquée vers un fichier de
# log, en plus du terminal — même contrat "logs toujours sauvegardés" que le
# mode arrière-plan ci-dessus (qui, lui, redirige déjà tout via nohup).
if [ -z "${_GDL_CHILD:-}" ]; then
  LOG_FILE="logs/generate_data_local_$(date -u +%Y%m%dT%H%M%SZ).log"
  echo "Mode premier plan — logs également sauvegardés dans : $LOG_FILE"
  exec > >(tee -a "$LOG_FILE") 2>&1
fi

MERGE_FLAG=()
[ "$FRESH_RUN" = "true" ] && MERGE_FLAG=(--no-merge)

INTERV_FLAG=()
[ "$EXTRACT_INTERVENTIONS" != "true" ] && INTERV_FLAG=(--skip-interventions)
MAX_PAGES_FLAG=()
[ "$EXTRACT_INTERVENTIONS" = "true" ] && MAX_PAGES_FLAG=(--max-pages "$MAX_PAGES")

if [ "$FRESH_RUN" = "true" ]; then
  echo "=== Nettoyage complet (fresh_run) ==="
  rm -rf .cache
  find raw_data/profiles -name "*.json" -delete
fi

echo "=== [1/7] extract-amendements-an : index amendements (17/16/15) ==="
python3 src/build_amendements_index.py || echo "[!] extract-amendements-an en échec (continue-on-error, comme en CI)"

echo "=== [2/7] extract-an : Assemblée nationale (tous les candidats) ==="
python3 src/generate_all_profiles.py --source an --workers "$WORKERS" "${MAX_PAGES_FLAG[@]}" "${MERGE_FLAG[@]}" "${INTERV_FLAG[@]}" \
  || echo "[!] extract-an en échec (continue-on-error, comme en CI)"

echo "=== [3/7] extract-senat : Sénat (NosSénateurs) ==="
python3 src/generate_all_profiles.py --source senat --workers "$WORKERS" "${MERGE_FLAG[@]}" \
  || echo "[!] extract-senat en échec (continue-on-error, comme en CI)"

echo "=== [4/7] extract-ue-officiel : Parlement européen (Open Data Portal) ==="
python3 src/generate_all_profiles.py --source ue --workers "$WORKERS" "${MERGE_FLAG[@]}" \
  || echo "[!] extract-ue-officiel en échec (continue-on-error, comme en CI)"

echo "=== [5/7] extract-parltrack : dumps ParlTrack (.zst) ==="
# Fichier temporaire plutôt qu'un heredoc (python3 - <<EOF) : un heredoc lit
# depuis le flux du script lui-même, sensible aux mêmes soucis de descripteur
# de fichier hérité qu'expliqué ci-dessus sur le relancement nohup — un
# fichier réel sur disque n'en dépend pas du tout.
PARLTRACK_SCRIPT="$(mktemp -t generate_data_local_parltrack.XXXXXX.py)"
trap 'rm -f "$PARLTRACK_SCRIPT"' EXIT
cat > "$PARLTRACK_SCRIPT" <<'PYEOF'
import sys
sys.path.insert(0, "src")
from parltrack_dumps import ensure_dump, _DUMP_DOSSIERS, _DUMP_PLENARY_AMENDMENTS, _DUMP_COMMITTEE_AMENDMENTS
force = sys.argv[1] == "true"
ok = True
for dump in [_DUMP_DOSSIERS, _DUMP_PLENARY_AMENDMENTS, _DUMP_COMMITTEE_AMENDMENTS]:
    path = ensure_dump(dump, force_download=force)
    if path is None:
        print(f"[!] Échec téléchargement : {dump}", file=sys.stderr)
        ok = False
sys.exit(0 if ok else 1)
PYEOF
python3 "$PARLTRACK_SCRIPT" "$FRESH_RUN" || echo "[!] extract-parltrack en échec (continue-on-error, comme en CI)"
rm -f "$PARLTRACK_SCRIPT"
trap - EXIT

echo "=== [6/7] extract-roster-groupes : membres de groupe (mode léger) ==="
# #511 : sortie non nulle sur une collecte incomplète (fetch en échec, groupe à
# 0 membre, roster vide). Ce script n'a pas `set -e` — sans ce test explicite,
# l'extraction ci-dessous repartirait sur un roster périmé ou absent, ce qui est
# exactement l'enchaînement qui a produit 229 profils bruts pour 209 pivots.
python3 src/generate_roster_candidats.py \
  || { echo "[!] Roster non régénéré (collecte incomplète, #511) — extraction roster sautée."; exit 1; }
LIMIT_FLAG=()
[ -n "$ROSTER_EXTRACTION_LIMIT" ] && [ "$ROSTER_EXTRACTION_LIMIT" != "0" ] && LIMIT_FLAG=(--limit "$ROSTER_EXTRACTION_LIMIT")
python3 src/generate_all_profiles.py \
  --candidats raw_data/roster_candidats.json \
  --workers "$WORKERS" \
  --skip-existing --resume \
  --skip-interventions --skip-dossiers-legislatifs \
  "${LIMIT_FLAG[@]}" "${MERGE_FLAG[@]}" \
  || echo "[!] extract-roster-groupes en échec (continue-on-error, comme en CI)"

echo "=== [7/7] merge-and-pivot : pivots, groupes, gouvernements, quality gate ==="

python3 src/generate_all_profiles.py \
  --pivot-only \
  --enrich-parltrack \
  --parltrack-status-out parltrack-status.json \
  --workers "$WORKERS" \
  "${MERGE_FLAG[@]}"

# #511 : sans ce test, un roster non régénéré fait normaliser la passe suivante
# sur une liste périmée — ou, dans l'incident d'origine, sur une liste vide.
# `--rosters-bruts-out` reproduit ce que le run CI transite par l'artifact
# `roster-candidats` : le step groupes plus bas lit cette liste au lieu d'en
# refetcher une (#518).
python3 src/generate_roster_candidats.py \
  --rosters-bruts-out raw_data/rosters_bruts.json \
  || { echo "[!] Roster non régénéré (collecte incomplète, #511) — pivots roster non produits."; exit 1; }
python3 src/generate_all_profiles.py \
  --pivot-only \
  --candidats raw_data/roster_candidats.json \
  --workers "$WORKERS" \
  "${MERGE_FLAG[@]}"

python3 src/parti_profile.py \
  --candidats raw_data/candidats.json \
  --profiles-dir pivot_data/profiles \
  --out-dir pivot_data/partis

GROUPE_MERGE_FLAG=()
[ "$FRESH_RUN" != "true" ] && GROUPE_MERGE_FLAG=(--merge-existing)
# Même filtrage qu'en CI, et pour la même raison (#518) : le code 2 dit « roster
# indisponible, aucune fiche touchée » — le run continue. Tout autre code reste
# un échec. Ne pas remplacer par un `|| true`, qui avalerait aussi le code 1.
GROUPE_CODE=0
python3 src/generate_group_profiles.py \
  --config raw_data/groupes_reels.json \
  --profiles-dir pivot_data/profiles \
  --out-dir pivot_data/groupes \
  --rosters-bruts raw_data/rosters_bruts.json \
  --validate "${GROUPE_MERGE_FLAG[@]}" || GROUPE_CODE=$?
if [ "$GROUPE_CODE" -eq 2 ]; then
  echo "[!] Roster indisponible : aucune fiche de groupe régénérée, les versions existantes restent en place (#518)."
elif [ "$GROUPE_CODE" -ne 0 ]; then
  exit "$GROUPE_CODE"
fi

python3 src/generate_gouvernement_profiles.py \
  --config raw_data/gouvernements_reels.json \
  --profiles-dir pivot_data/profiles \
  --out-dir pivot_data/gouvernements \
  --validate

python3 src/check_quality_gate.py \
  --profiles-dir      pivot_data/profiles \
  --groupes-dir       pivot_data/groupes \
  --partis-dir        pivot_data/partis \
  --raw-dir           raw_data/profiles \
  --candidats         raw_data/candidats.json \
  --groupes-config    raw_data/groupes_reels.json \
  --gouvernements-dir    pivot_data/gouvernements \
  --gouvernements-config raw_data/gouvernements_reels.json \
  --threshold         "$THRESHOLD" \
  --low-interventions 10 \
  --groupe-min-members 1 \
  --parltrack-status-file parltrack-status.json

echo
echo "=== Terminé ==="
echo "Rien n'a été committé/poussé automatiquement (contrairement au job CI)."
echo "Vérifier 'git status' / 'git diff' sur raw_data/profiles, pivot_data/profiles,"
echo "pivot_data/partis, pivot_data/groupes, pivot_data/gouvernements, puis"
echo "committer/pousser manuellement si le résultat est satisfaisant."
