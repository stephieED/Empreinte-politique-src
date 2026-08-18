#!/usr/bin/env bash
#
# mesure_volumetrie_roster.sh — Génère les profils du roster complet HORS DÉPÔT
# et produit le rapport de volumétrie qui arbitre #429.
#
# Pourquoi un script dédié plutôt que generate_data_local.sh : celui-ci écrit
# dans raw_data/profiles et pivot_data/profiles, donc dans l'arbre versionné.
# À 752 membres cela ferait ~6 Go de churn dans `git status` — précisément le
# volume qui pose problème, et un risque de commit accidentel. Ici la sortie va
# dans un répertoire hors dépôt, et rien n'est jamais committé.
#
# Options d'entrée :
#   OUT_DIR=<chemin>     (défaut: ../empreinte-mesure-volumetrie, HORS du dépôt)
#   WORKERS=<n>          (défaut: 1 — mesuré sans gain au-delà, voir plus bas)
#   LIMIT=<n>            (défaut: 0 = tous les membres du roster)
#   ECHANTILLON=<n>      (défaut: 60 — profils analysés en profondeur)
#   BACKGROUND=true|false (défaut: true — se relance via nohup, rend la main)
#
# Logs : logs/mesure_volumetrie_<horodatage>.log (dossier git-ignoré).
#
# WORKERS reste à 1 : mesuré 2,6 / 2,4 / 2,3 / 2,2 s par membre à 1 / 2 / 4 / 8
# workers, soit 15 % d'écart — du bruit. L'extraction roster ne fait AUCUNE
# requête HTTP par membre (tout vient des caches locaux depuis la migration
# vers l'open data AN), donc rien à gagner à paralléliser. C'est aussi le
# défaut du projet, adopté sur retour d'expérience utilisatrice quant à la
# robustesse d'appels parallèles vers une même source
# (docs/technical_decisions.md).
#
# --no-merge est délibéré : on mesure ce que le code produit AUJOURD'HUI. La
# fusion additive mélangerait données fraîches et profils committés périmés
# (antérieurs à #400/#403), et ne mesurerait alors ni l'un ni l'autre. Ce flag
# serait FAUX pour un run de production, qui doit fusionner.
#
# Exemple : ./scripts/mesure_volumetrie_roster.sh
# Suivre : tail -f logs/mesure_volumetrie_*.log

set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

mkdir -p logs

# Relance auto en arrière-plan, même mécanisme que generate_data_local.sh —
# y compris `< /dev/null`, sans lequel un stdin hérité invalide (terminal non
# interactif, panneau IDE) fait échouer bash au relancement.
if [ "${BACKGROUND:-true}" = "true" ] && [ -z "${_MVR_CHILD:-}" ]; then
  LOG_FILE="logs/mesure_volumetrie_$(date -u +%Y%m%dT%H%M%SZ).log"
  echo "Lancement en arrière-plan — logs : $LOG_FILE"
  _MVR_CHILD=1 nohup "$0" "$@" < /dev/null > "$LOG_FILE" 2>&1 &
  BG_PID=$!
  disown
  echo "PID : $BG_PID"
  echo "Suivre : tail -f $LOG_FILE"
  echo "Arrêter : kill $BG_PID"
  exit 0
fi

OUT_DIR="${OUT_DIR:-../empreinte-mesure-volumetrie}"
WORKERS="${WORKERS:-1}"
LIMIT="${LIMIT:-0}"
ECHANTILLON="${ECHANTILLON:-60}"
HORODATAGE="$(date -u +%Y%m%dT%H%M%SZ)"
RAPPORT="audit/volumetrie_roster_${HORODATAGE}"

export PYTHONUNBUFFERED=1
[ -d .venv ] && source .venv/bin/activate

# Garde-fou : refuser une sortie DANS le dépôt, ce que ce script existe
# précisément pour éviter.
if [ -z "${OUT_DIR##"$PWD"*}" ]; then
  echo "[!] OUT_DIR ($OUT_DIR) est dans le dépôt. Choisir un chemin externe." >&2
  exit 1
fi
mkdir -p "$OUT_DIR"

echo "=== Mesure de volumétrie du roster ==="
echo "  sortie      : $OUT_DIR (hors dépôt, jamais committé)"
echo "  workers     : $WORKERS"
echo "  limite      : ${LIMIT} (0 = roster complet)"
echo

# raw_data/roster_candidats.json est git-ignoré (source de vérité =
# groupes_reels.json), donc absent d'un dépôt fraîchement cloné.
echo "=== [1/3] Construction de la liste roster ==="
python3 src/generate_roster_candidats.py || exit 1

LIMIT_FLAG=()
[ "$LIMIT" != "0" ] && LIMIT_FLAG=(--limit "$LIMIT")

echo
echo "=== [2/3] Extraction des profils (hors dépôt) ==="
/usr/bin/time -v python3 src/generate_all_profiles.py \
  --candidats raw_data/roster_candidats.json \
  --workers "$WORKERS" \
  --skip-interventions --skip-dossiers-legislatifs \
  --no-merge --no-checkpoint \
  --out-dir "$OUT_DIR" \
  "${LIMIT_FLAG[@]}" 2>&1 | grep -vE "^\s+(Command being|User time|System time|Percent of|Average|Major|Minor|Voluntary|Involuntary|Swaps|File system|Socket|Signals|Page size|Exit status)"

echo
echo "=== [3/3] Rapport de volumétrie ==="
mkdir -p audit
python3 src/audit_volumetrie_profils.py \
  --profils-dir "$OUT_DIR" \
  --facteur-duplication 1.0 \
  --cible 752 \
  --echantillon "$ECHANTILLON" \
  --out "${RAPPORT}.md" --out-json "${RAPPORT}.json" || exit 1

echo
echo "=== Terminé ==="
echo "Rapport  : ${RAPPORT}.md"
echo "Profils  : $OUT_DIR ($(du -sh "$OUT_DIR" 2>/dev/null | cut -f1))"
echo
echo "Les profils ne sont PAS versionnés : ce run mesure, il ne produit pas de"
echo "données destinées au dépôt. Supprimer $OUT_DIR une fois le rapport lu."
