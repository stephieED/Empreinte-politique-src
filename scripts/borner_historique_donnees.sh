#!/usr/bin/env bash
#
# borner_historique_donnees.sh — option D de #434 : borner l'historique DE
# DONNÉES plutôt que son contenu.
#
# Ce script NE POUSSE JAMAIS et NE MODIFIE JAMAIS `main`. Il mesure, ou il
# prépare une ref locale que l'humaine inspectera puis poussera elle-même. La
# réécriture d'historique est irréversible pour tous les clones existants :
# c'est une décision, pas une étape de script.
#
#   --mesurer   (défaut)  clone le dépôt dans un répertoire temporaire, y
#                         applique la coupure, repacke, et rend le gain RÉEL.
#                         Ne touche à rien.
#   --preparer            écrit `refs/heads/main-borne` et le tag de sauvegarde
#                         `archive/pre-borne-<date>` dans le dépôt courant,
#                         puis affiche les commandes de push à exécuter à la
#                         main. `main` reste intacte.
#
#   --fenetre N           nombre de commits de données conservés (défaut : 30).
#
# ── Ce que la mesure a établi (clone du 20/08/2026, main = 0466957) ───────────
#
#   objets atteignables, après repack optimal ......... 284 Mo
#   `.git` sur disque, avant repack ................... 853 Mo
#   taille annoncée par l'API GitHub .................. 395 Mo
#
#   Le dépôt « pèse » donc trois chiffres différents, et un seul compte pour
#   les seuils : 284 Mo. Les 569 Mo d'écart local et les 111 Mo d'écart côté
#   GitHub sont des objets DEVENUS INACCESSIBLES par des rebases et des pushs
#   forcés — pas de l'historique.
#
#   Taille du dépôt selon la fenêtre (mesurée, gc --prune=now compris ;
#   23 commits de données au total, donc « 23 » = historique complet) :
#
#     fenêtre :    0     1     2     3     4     6     8    10    15    20   23
#     dépôt   :  127   169   175   218   246   258   259   280   280   283  284  Mo
#
#   La courbe SATURE à partir de ~10 : les commits de données plus anciens ont
#   été écrits quand le corpus faisait 14 à 30 profils, ils ne pèsent presque
#   rien — tout ce qui précède le 10e commit de données vaut moins de 2 % du
#   dépôt. Aujourd'hui, avec 23 commits de données, borner à 30 ne retire donc
#   RIEN : c'est un plafond pour plus tard, pas un gain immédiat.
#
# ── Trois pièges, tous rencontrés en mesurant ────────────────────────────────
#
#   1. `git replace --graft` NE SUFFIT PAS. `main` porte des commits de merge
#      dont le second parent plonge avant la coupure : greffer un seul commit
#      laisse l'ancien historique atteignable par un autre chemin. Mesuré :
#      677 commits avant, 677 après la greffe. D'où le rejeu explicite
#      ci-dessous, qui remappe TOUS les parents.
#
#   2. Les index bitmap sont calculés sur le graphe NON greffé, et rev-list les
#      utilise en priorité. Sans `-c pack.useBitmaps=false`, une mesure de
#      vérification rend le résultat d'AVANT la coupure sans le signaler.
#
#   3. Les autres refs ré-épinglent l'ancien historique. Au 20/08/2026 le dépôt
#      local porte 18 refs et GitHub 3 branches + 1 tag. Une branche oubliée
#      garde atteignable tout ce que la coupure prétendait retirer, et le gain
#      est nul sans que rien ne le dise.
#
# ── Ce que l'opération ne rend PAS ───────────────────────────────────────────
#
#   Un push forcé ne libère rien tant qu'un `gc` n'a pas tourné, et côté GitHub
#   on ne peut pas en déclencher un. Mesuré sur un dépôt nu local :
#
#     serveur, historique complet, gc fait ............ 284 Mo
#     après push forcé d'une fenêtre à 3 (169 Mo) ..... 284 Mo  ← INCHANGÉ
#     après `gc --prune=now` .......................... 169 Mo
#
#   Sur GitHub, seule la deuxième ligne est atteignable par nos moyens. La
#   troisième dépend du ramasse-miettes de GitHub, dont la date n'est ni
#   annoncée ni déclenchable.
#
#   MAIS il faut séparer deux choses, et la mesure les sépare nettement. Depuis
#   le MÊME serveur non ramassé, un clone passé par le protocole git :
#
#     serveur sur disque, sans gc ..................... 284 Mo
#     clone frais depuis ce serveur ................... 218 Mo  ← déjà borné
#
#   `upload-pack` reconstruit le pack à partir des seuls objets ATTEIGNABLES.
#   Donc : le coût pour les consommateurs — clone, checkout CI, temps de
#   fetch — tombe IMMÉDIATEMENT après le push forcé, sans attendre aucun gc.
#   Ce qui reste haut, c'est l'empreinte disque côté GitHub et le `size`
#   annoncé par l'API. Mesuré le 20/08/2026 : 284 Mo atteignables contre
#   395 Mo annoncés, soit 111 Mo (39 %) de résidus des rebases et pushs forcés
#   de la journée, toujours pas ramassés.
#
#   (Attention en vérifiant : `git clone` sur un CHEMIN local copie le
#   répertoire d'objets tel quel, résidus compris, et rend donc 284 Mo. Il faut
#   `--no-local` ou une URL `file://` pour mesurer ce que sert vraiment un
#   serveur.)
#
set -euo pipefail

FENETRE=30
MODE=mesurer
MOTIF="mise à jour automatique des données"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mesurer)  MODE=mesurer; shift ;;
    --preparer) MODE=preparer; shift ;;
    --fenetre)  FENETRE=$2; shift 2 ;;
    -h|--help)  sed -n '2,80p' "$0"; exit 0 ;;
    *) echo "[!] Option inconnue : $1" >&2; exit 2 ;;
  esac
done

RACINE=$(git rev-parse --show-toplevel)
cd "$RACINE"

# ── Rejeu : la coupure devient un commit racine portant l'arbre COMPLET, tous
# les commits postérieurs sont recréés à l'identique (mêmes arbres, mêmes
# blobs, mêmes auteurs, mêmes dates) avec leurs parents remappés.
_rejouer() {
  local depot=$1 cut=$2 sortie=$3
  local tmsg root tip
  tmsg=$(mktemp); trap 'rm -f "$tmsg"' RETURN
  cut=$(git -C "$depot" rev-parse "$cut")
  printf 'data: socle historique — squash de tout ce qui précède %s (#434)\n' \
         "$(git -C "$depot" rev-parse --short "$cut")" > "$tmsg"
  root=$(git -C "$depot" commit-tree "$cut^{tree}" -F "$tmsg")

  local -A carte=()
  carte[$cut]=$root
  local c p np parents
  for c in $(git -C "$depot" rev-list --reverse --topo-order main "^$cut"); do
    parents=""
    for p in $(git -C "$depot" rev-list --parents -n1 "$c" | cut -d' ' -f2-); do
      np=${carte[$p]:-$root}
      case " $parents " in *" -p $np "*) ;; *) parents="$parents -p $np";; esac
    done
    git -C "$depot" log -1 --format='%B' "$c" > "$tmsg"
    carte[$c]=$(
      GIT_AUTHOR_NAME=$(git -C "$depot" log -1 --format='%an' "$c") \
      GIT_AUTHOR_EMAIL=$(git -C "$depot" log -1 --format='%ae' "$c") \
      GIT_AUTHOR_DATE=$(git -C "$depot" log -1 --format='%aI' "$c") \
      GIT_COMMITTER_NAME=$(git -C "$depot" log -1 --format='%cn' "$c") \
      GIT_COMMITTER_EMAIL=$(git -C "$depot" log -1 --format='%ce' "$c") \
      GIT_COMMITTER_DATE=$(git -C "$depot" log -1 --format='%cI' "$c") \
      git -C "$depot" commit-tree "$c^{tree}" $parents -F "$tmsg"
    )
  done
  tip=${carte[$(git -C "$depot" rev-parse main)]}
  git -C "$depot" update-ref "$sortie" "$tip"
  echo "$tip"
}

# ── La seule vérification qui prouve qu'aucun octet n'a été perdu : l'arbre du
# sommet doit être IDENTIQUE avant et après. Un arbre git est un hachage
# récursif de tout le contenu ; s'il coïncide, chaque fichier coïncide.
_verifier() {
  local depot=$1 avant=$2 apres=$3
  local ta tb
  ta=$(git -C "$depot" rev-parse "$avant^{tree}")
  tb=$(git -C "$depot" rev-parse "$apres^{tree}")
  if [[ "$ta" != "$tb" ]]; then
    echo "[!] ARBRE DIFFÉRENT ($ta != $tb) — ne rien pousser." >&2
    return 1
  fi
  echo "✓ Arbre du sommet identique ($ta) : aucun fichier n'a changé."
}

_coupure() {
  git -C "$1" log --format='%H' --grep="$MOTIF" main \
    | sed -n "$((FENETRE + 1))p"
}

case "$MODE" in

mesurer)
  TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
  echo "→ Clone de mesure dans $TMP (aucune écriture dans $RACINE)…"
  git clone --quiet --mirror --no-hardlinks "$RACINE" "$TMP/m.git"
  git -C "$TMP/m.git" -c pack.threads=4 gc --prune=now --quiet
  AVANT=$(du -sm "$TMP/m.git" | cut -f1)
  NB=$(git -C "$TMP/m.git" log --format='%H' --grep="$MOTIF" main | wc -l)
  echo "   commits de données : $NB — fenêtre demandée : $FENETRE"
  echo "   dépôt, historique complet, après repack : ${AVANT} Mo"

  CUT=$(_coupure "$TMP/m.git" || true)
  if [[ -z "$CUT" ]]; then
    echo "✓ Fenêtre NON contraignante ($NB ≤ $FENETRE) : rien à borner."
    echo "  Aucune réécriture d'historique n'est justifiée aujourd'hui."
    exit 0
  fi
  echo "   coupure : $(git -C "$TMP/m.git" rev-parse --short "$CUT")"
  NEW=$(_rejouer "$TMP/m.git" "$CUT" refs/heads/borne)
  _verifier "$TMP/m.git" main "$NEW"
  # Toutes les autres refs doivent tomber, sinon elles ré-épinglent l'ancien
  # historique et le gain mesuré serait faux (piège n° 3).
  git -C "$TMP/m.git" for-each-ref --format='%(refname)' \
    | grep -v '^refs/heads/borne$' | xargs -r -n1 git -C "$TMP/m.git" update-ref -d
  git -C "$TMP/m.git" reflog expire --all --expire=now
  git -C "$TMP/m.git" -c pack.threads=4 gc --prune=now --quiet
  APRES=$(du -sm "$TMP/m.git" | cut -f1)
  echo "   dépôt, historique borné à $FENETRE, après repack : ${APRES} Mo"
  echo "→ GAIN RÉEL : $((AVANT - APRES)) Mo ($(( (AVANT - APRES) * 100 / AVANT )) %)"
  echo "  (à ne pas confondre avec la somme des coûts par run, qui surestime"
  echo "   d'un facteur 2 à 15 — voir l'en-tête de ce script.)"
  ;;

preparer)
  if [[ -n "$(git status --porcelain)" ]]; then
    echo "[!] Arbre de travail non propre. Refus." >&2; exit 1
  fi
  if [[ "$(git rev-parse --abbrev-ref HEAD)" != "main" ]]; then
    echo "[!] À exécuter depuis main. Refus." >&2; exit 1
  fi
  git fetch --quiet origin
  if [[ "$(git rev-parse main)" != "$(git rev-parse origin/main)" ]]; then
    echo "[!] main et origin/main divergent. Synchroniser d'abord. Refus." >&2; exit 1
  fi

  CUT=$(_coupure "$RACINE" || true)
  if [[ -z "$CUT" ]]; then
    echo "✓ Fenêtre non contraignante : rien à préparer."; exit 0
  fi

  TAG="archive/pre-borne-$(date +%Y%m%d%H%M)"
  git tag "$TAG" main
  NEW=$(_rejouer "$RACINE" "$CUT" refs/heads/main-borne)
  _verifier "$RACINE" main "$NEW"

  cat <<FIN

Préparé, RIEN n'a été poussé et « main » est intacte.

  sauvegarde locale  : $TAG  (= l'ancien main, à ne PAS pousser sur le même
                       dépôt : le tag garderait tout l'historique atteignable
                       et le gain serait nul)
  branche réécrite   : main-borne ($NEW)

À faire à la main, dans cet ordre — chaque étape est un point de non-retour de
plus :

  1. Vérifier qu'aucun run de données n'est en cours ni programmé :
       gh run list --workflow=generate-data.yml --limit 5
     Un push forcé qui croise un run fait committer ce run sur un historique
     qui n'existe plus.

  2. Archiver l'ancien historique AILLEURS, sinon les SHA cités dans
     docs/technical_decisions.md et dans les issues cessent de résoudre :
       git push <depot-archive> $TAG

  3. Pousser la branche bornée :
       git push --force-with-lease origin main-borne:main

  4. Supprimer ou réécrire TOUTE autre branche distante, sinon elle
     ré-épingle l'ancien historique et le gain est nul :
       git ls-remote --heads origin

  5. Prévenir : tout clone existant doit être refait. Un « git pull » sur un
     clone existant recrée l'ancien historique et peut le repousser.

Retour en arrière — possible tant que l'étape 4 n'a pas été faite ET que
GitHub n'a pas ramassé les objets :
       git push --force origin $TAG^{commit}:main
Au-delà, le retour dépend d'un clone tiers encore à jour.
FIN
  ;;
esac
