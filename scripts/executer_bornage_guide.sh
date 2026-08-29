#!/usr/bin/env bash
#
# executer_bornage_guide.sh — le runner guidé de la procédure de bornage
# (#576, sous-issue de #566).
#
# ── Pourquoi un runner, et pourquoi un SCRIPT DISTINCT ───────────────────────
#
#   La procédure de bornage était de la PROSE, imprimée dans un heredoc par
#   `borner_historique_donnees.sh --preparer`. Sept étapes, dont trois
#   irréversibles, dans un ordre dont une seule inversion est irrattrapable :
#   archiver APRÈS avoir coupé ne rattrape rien.
#
#   Le texte se saute, et le moment où on le lit est précisément celui où l'on
#   est sous pression. La répétition du 28/08/2026 (#569) l'a démontré : les
#   sept étapes ont été déroulées à la main, et UNE A ÉTÉ OUBLIÉE — la
#   suppression du tag `amendements-figes-v1`, qui ré-épinglait 386 commits.
#   L'opératrice a suivi le texte ; le texte était incomplet. Un second écart,
#   assumé celui-là : l'étape 2 a rendu MANQUANTS, on est passé outre après
#   avoir établi que le blocage était injustifié (#575), et rien n'en garde
#   trace ailleurs que dans une conversation.
#
#   Ce que ce runner apporte, et que la prose ne peut pas :
#     1. il IMPOSE L'ORDRE — la seule propriété dont l'erreur est irrattrapable ;
#     2. il REFUSE D'AVANCER quand une précondition échoue, et si l'opératrice
#        passe outre, il le lui fait dire explicitement et le CONSIGNE ;
#     3. il N'OUBLIE PAS D'ÉTAPE, y compris celles que le texte avait omises ;
#     4. il TIENT UN JOURNAL : quoi, quand, avec quel résultat. Cette trace
#        n'existait pas.
#
#   ⚠ DEUX SCRIPTS, DEUX CONTRATS. `scripts/borner_historique_donnees.sh`
#   GARANTIT PAR TEST QU'IL NE POUSSE JAMAIS (`test_le_script_ne_pousse_jamais`,
#   `test_le_script_ne_reecrit_pas_main`). C'est sa propriété centrale, actée
#   par #551, et elle reste vraie. Ce runner est un script DISTINCT : il appelle
#   le premier pour ce qui prépare, et porte LUI-MÊME les gestes irréversibles,
#   après confirmation. L'ancien contrat tient, le nouveau est explicite.
#
#   Il NE DÉCIDE PAS QUAND. La fenêtre est une politique, pas une contrainte —
#   le dépôt tient à 415 Mo contre 2 Go de critère (#429). Le runner exécute une
#   décision ; il ne la prend pas, et IL NE SE DÉCLENCHE JAMAIS TOUT SEUL. C'est
#   la ligne de la question 2 de #551 : la détection est armée, la réécriture
#   reste manuelle. Aucun workflow ne l'appelle, et un test l'interdit.
#
# ── Les confirmations ne sont pas des « y » ──────────────────────────────────
#
#   Pour les étapes 4 et 5, le runner fait TAPER UNE PHRASE, comme GitHub
#   l'exige pour supprimer un dépôt. Un `y` se tape par réflexe, et c'est
#   précisément le réflexe qu'on veut interrompre. La comparaison est stricte :
#   ni casse ignorée, ni espaces rognés, ni abréviation.
#
# ── Les sept étapes ──────────────────────────────────────────────────────────
#
#     n  étape                        réversible  précondition bloquante
#     1  --mesurer                    oui         —
#     2  vérifier l'archivage         oui         verdict ≠ MANQUANTS
#     3  --preparer                   oui (local) arbre propre, `main` à jour
#     4  PUSH FORCÉ                   NON         aucun run de données en cours
#                                                 SUR LE DÉPÔT QU'ON BORNE
#     5  SUPPRIMER LES AUTRES REFS    NON         —
#     6  vérifier la CI               oui         —
#     7  re-mesurer et consigner      oui         —
#
# ── Ce que la répétition a corrigé dans la procédure ─────────────────────────
#
#   Six points, tous relevés le 28/08/2026 en déroulant #569. Ils ne sont pas
#   inventés ici : ils sont le rendu de la répétition.
#
#   a. LES TAGS. L'étape 5 ne parlait que de « branches ». Le tag
#      `amendements-figes-v1`, oublié, ré-épinglait 386 commits — c'est-à-dire
#      annulait l'essentiel du gain sans que rien ne le dise. L'étape 5 traite
#      désormais branches ET tags.
#
#   b. LES `refs/pull/*` NE SONT PAS SUPPRIMABLES. Elles sont gérées par GitHub.
#      Après la répétition il restait `refs/pull/1/head` (846 commits
#      atteignables) et `refs/pull/2/head` (860). Le runner les NOMME pour qu'on
#      ne les cherche pas — et consigne que la taille annoncée a chuté malgré
#      elles (513 → 240 Mo), sans qu'on puisse trancher de l'extérieur si
#      GitHub les exclut de son calcul ou si son ramasse-miettes les traite à
#      part.
#
#   c. `dev` SE REPOINTE, ELLE NE SE SUPPRIME PAS. Mesuré : 0 commit absent de
#      l'ancien `main` — c'est un signet posé sur une position ancienne, pas du
#      travail propre. Mais elle gardait 21 commits de données atteignables,
#      soit l'essentiel des 272 Mo de gain : pas parce qu'elle est grosse, parce
#      qu'elle est ANCIENNE. Il n'y a donc pas de contradiction avec la
#      politique « ne jamais supprimer `dev` » : le geste correct est de la
#      repointer sur le nouveau `main`. Une ligne, aucune perte.
#
#   d. L'ÉTAPE 4 DIT SUR QUEL DÉPÔT vérifier qu'aucun run ne tourne. Ambigu dès
#      qu'on répète ailleurs — et une répétition, c'est exactement le moment où
#      « le dépôt » désigne deux choses. Le runner résout le dépôt depuis
#      `git remote get-url origin` et l'AFFICHE avant de demander.
#
#   e. LE COÛT D'ENTRÉE. `--preparer` exige un arbre propre, donc un checkout
#      complet : 4,9 Go et 45 s sur ce corpus. À annoncer avant, pas à
#      découvrir.
#
#   f. LA DURÉE DE VIE DU TAG DE SAUVEGARDE `archive/pre-borne-<date>`. Rien ne
#      la disait, et c'est la seule sauvegarde immédiate en cas de regret. La
#      règle retenue est écrite à l'étape 7 : le garder jusqu'à ce que Software
#      Heritage ait conclu une visite `full` couvrant l'historique d'AVANT la
#      coupure ET que la CI soit verte sur l'historique borné, avec un plancher
#      de 30 jours. Avant ce point, le tag est la seule reprise possible ; après,
#      l'archive prend le relais et le tag ne fait plus que retenir des objets.
#
# ── Ce que la répétition a INFIRMÉ ───────────────────────────────────────────
#
#   « Le push forcé ne fait pas baisser la taille annoncée par GitHub tant que
#   leur ramasse-miettes n'est pas passé. » C'est écrit dans #434 et repris dans
#   #551. C'est FAUX, au moins dans ce cas : mesuré le 28/08/2026, la taille
#   annoncée est passée de 513 à 240 Mo en quelques minutes, et le clone frais
#   de 534 à 268 Mo. Ne pas prendre une taille qui baisse pour une anomalie.
#
# ── Usage ────────────────────────────────────────────────────────────────────
#
#   --lister                affiche les sept étapes et sort. Ne fait rien.
#   --fenetre N             fenêtre de bornage (défaut : 30, comme le script de
#                           bornage et `audit_volumetrie_profils.py`).
#   --journal FICHIER       journal de la session (défaut :
#                           audit/bornage-<horodatage>.journal).
#   --reprendre FICHIER     reprend une session interrompue : les étapes déjà
#                           consignées comme TERMINÉES ne sont pas refaites, et
#                           l'ordre reste imposé.
#   --etape N               n'exécute QUE l'étape N — et refuse si les
#                           précédentes ne sont pas consignées comme terminées.
#   --jusqu-a N             s'arrête après l'étape N (défaut : 7).
#
#   Le runner est INTERACTIF. Il n'a pas de mode « tout automatique », et c'est
#   délibéré : chaque geste irréversible attend une phrase tapée à la main.
#
set -euo pipefail

FENETRE=30
JOURNAL=""
ETAPE_UNIQUE=""
JUSQU_A=7
DEPUIS=1

# La phrase à taper pour chaque geste irréversible. Elles sont LONGUES et elles
# NOMMENT le geste : c'est ce qui empêche de les taper sans les lire.
PHRASE_PUSH="je reecris main de force"
PHRASE_REFS="je supprime les refs qui reepinglent l ancien historique"
PHRASE_DEROGATION="je passe outre et j en prends la responsabilite"

_horodatage() { date +%Y-%m-%dT%H:%M:%S%z; }

_journaliser() {
  local ligne="[$(_horodatage)] $*"
  printf '%s\n' "$ligne" >&2
  [[ -n "$JOURNAL" ]] && printf '%s\n' "$ligne" >> "$JOURNAL"
  return 0
}

# ── Confirmation : une phrase, jamais un « y » ───────────────────────────────
#
# La comparaison est STRICTE. Rogner les espaces ou ignorer la casse rendrait la
# saisie plus facile, c'est-à-dire plus réflexe — l'inverse de ce qu'on cherche.
_confirmer_phrase() {
  local attendue=$1 raison=$2 saisie=""
  printf '\n  %s\n' "$raison" >&2
  printf '  GESTE IRRÉVERSIBLE. Pour continuer, taper exactement :\n' >&2
  printf '      %s\n  > ' "$attendue" >&2
  IFS= read -r saisie || saisie=""
  if [[ "$saisie" != "$attendue" ]]; then
    _journaliser "REFUS — phrase attendue « $attendue », saisie « $saisie ». Rien n'a été fait."
    return 1
  fi
  _journaliser "CONFIRMÉ — « $attendue »"
  return 0
}

# ── Préconditions : bloquantes, contournables, et le contournement se dit ────
#
# « Il refuse d'avancer quand une précondition échoue — et si l'opératrice passe
# outre, il le lui fait dire explicitement et le consigne » (#576). Le second
# écart de la répétition du 28/08 était exactement ça : passer outre un verdict
# MANQUANTS, à bon droit, sans que rien n'en garde trace.
_precondition() {
  local libelle=$1; shift
  if "$@"; then
    _journaliser "PRÉCONDITION OK — $libelle"
    return 0
  fi
  _journaliser "PRÉCONDITION EN ÉCHEC — $libelle"
  if _confirmer_phrase "$PHRASE_DEROGATION" \
      "La précondition « $libelle » n'est pas remplie."; then
    _journaliser "DÉROGATION — « $libelle » non remplie, passage outre assumé et consigné."
    return 0
  fi
  _journaliser "ARRÊT — précondition « $libelle » non remplie, pas de dérogation."
  return 1
}

# ── L'ordre, qui est la seule propriété dont l'erreur est irrattrapable ──────
_etape_terminee() {
  [[ -n "$JOURNAL" && -f "$JOURNAL" ]] && grep -q "^\[.*\] ÉTAPE $1 — TERMINÉE" "$JOURNAL"
}

_exiger_etapes_precedentes() {
  local n=$1 k manquantes=()
  for ((k = 1; k < n; k++)); do
    _etape_terminee "$k" || manquantes+=("$k")
  done
  if ((${#manquantes[@]} > 0)); then
    _journaliser "ARRÊT — étape $n demandée, mais ${manquantes[*]} non terminée(s). L'ordre n'est pas négociable : archiver APRÈS avoir coupé ne rattrape rien."
    return 1
  fi
  return 0
}

_terminer_etape() { _journaliser "ÉTAPE $1 — TERMINÉE"; }

# ── Le dépôt qu'on borne, nommé (point d) ────────────────────────────────────
_depot_cible() {
  local url
  url=$(git remote get-url origin 2>/dev/null) || return 1
  # `git@github.com:o/r.git` comme `https://github.com/o/r` → `o/r`
  url=${url%.git}
  url=${url##*github.com[:/]}
  printf '%s\n' "$url"
}

_aucun_run_en_cours() {
  local cible=$1 encours
  encours=$(gh run list --repo "$cible" --workflow=generate-data.yml \
              --limit 10 --json status,databaseId \
              --jq '[.[] | select(.status != "completed")] | length' 2>/dev/null) || {
    _journaliser "gh indisponible ou dépôt injoignable : impossible d'établir qu'aucun run ne tourne sur $cible."
    return 1
  }
  [[ "$encours" == "0" ]]
}

# ── Les sept étapes ──────────────────────────────────────────────────────────

_lister_etapes() {
  cat <<'FIN'
Les sept étapes du bornage (#576, telles que la répétition de #569 les a établies) :

   n  étape                      réversible  précondition bloquante
   1  --mesurer                  oui         —
   2  vérifier l'archivage       oui         verdict ≠ MANQUANTS
   3  --preparer                 oui (local) arbre propre, `main` à jour
   4  PUSH FORCÉ                 NON         aucun run de données en cours
                                             SUR LE DÉPÔT QU'ON BORNE
   5  SUPPRIMER LES AUTRES REFS  NON         —
   6  vérifier la CI             oui         —
   7  re-mesurer et consigner    oui         —

Les étapes 4 et 5 demandent une PHRASE tapée, pas un « y ».
Coût d'entrée à connaître avant l'étape 3 : `--preparer` exige un arbre propre,
donc un checkout complet — 4,9 Go et 45 s sur ce corpus (mesuré le 28/08/2026).
FIN
}

_etape_1_mesurer() {
  _journaliser "ÉTAPE 1 — mesure du gain (réversible, n'écrit rien)."
  scripts/borner_historique_donnees.sh --mesurer --fenetre "$FENETRE" 2>&1 | tee -a "$JOURNAL"
  _terminer_etape 1
}

_etape_2_verifier_archivage() {
  _exiger_etapes_precedentes 2 || return 1
  cat <<'FIN' >&2

ÉTAPE 2 — l'archivage, puis sa vérification.

  2a. Déclencher « Save Code Now » : https://archive.softwareheritage.org/save/
      Software Heritage archive ce qui est atteignable AU MOMENT du passage.
      Après la coupure, c'est perdu. CET ORDRE N'EST PAS NÉGOCIABLE : archiver
      après avoir coupé ne rattrape rien, et c'est la seule inversion d'étapes
      que rien ne rattrape.
FIN
  local fait=""
  printf '\n  « Save Code Now » a-t-il été déclenché sur ce dépôt ? [o/N] > ' >&2
  IFS= read -r fait || fait=""
  if [[ "$fait" != "o" && "$fait" != "O" ]]; then
    _journaliser "ARRÊT — étape 2a non faite : rien à vérifier, et rien à couper."
    return 1
  fi
  _journaliser "ÉTAPE 2a — « Save Code Now » déclaré déclenché."

  local code=0
  _journaliser "ÉTAPE 2b — vérification d'archivage sur la coupure de la fenêtre $FENETRE (#575)."
  python3 src/verifier_archivage_swh.py --fenetre "$FENETRE" \
      --json "${JOURNAL%.journal}.swh.json" 2>&1 | tee -a "$JOURNAL" || code=$?
  # `tee` masque le code de sortie du script : c'est PIPESTATUS qui porte le
  # verdict, et le confondre avec celui de `tee` rendrait la précondition
  # toujours verte — un garde-fou qui ne garde rien.
  code=${PIPESTATUS[0]}
  _journaliser "ÉTAPE 2b — verdict $code (0 VÉRIFIÉ, 1 MANQUANTS, 2 INDÉTERMINÉ)."
  _precondition "le verdict d'archivage n'est pas MANQUANTS (code $code)" \
      test "$code" -ne 1 || return 1
  _terminer_etape 2
}

_etape_3_preparer() {
  _exiger_etapes_precedentes 3 || return 1
  cat <<'FIN' >&2

ÉTAPE 3 — préparation (réversible : refs LOCALES seulement, `main` intacte).

  COÛT D'ENTRÉE, à connaître avant de lancer : `--preparer` exige un arbre de
  travail propre, donc un checkout complet du corpus — 4,9 Go et 45 s sur ce
  corpus (mesuré le 28/08/2026). Ce n'est pas une anomalie, c'est le prix.
FIN
  _precondition "l'arbre de travail est propre" \
      test -z "$(git status --porcelain)" || return 1
  _journaliser "ÉTAPE 3 — appel de borner_historique_donnees.sh --preparer."
  scripts/borner_historique_donnees.sh --preparer --fenetre "$FENETRE" 2>&1 | tee -a "$JOURNAL"
  _precondition "la branche refs/heads/main-borne existe" \
      git rev-parse --verify --quiet refs/heads/main-borne || return 1
  local tag
  tag=$(git for-each-ref --format='%(refname:short)' --sort=-creatordate \
          'refs/tags/archive/pre-borne-*' | head -n1)
  _journaliser "ÉTAPE 3 — tag de sauvegarde : ${tag:-AUCUN}. C'est la seule reprise immédiate en cas de regret (voir étape 7 pour sa durée de vie)."
  _terminer_etape 3
}

_etape_4_pousser() {
  _exiger_etapes_precedentes 4 || return 1
  local cible
  cible=$(_depot_cible) || cible="(remote origin introuvable)"
  cat <<'FIN' >&2

ÉTAPE 4 — PUSH FORCÉ. POINT DE NON-RETOUR.

  Ce que ce geste demande, et que la procédure ne disait pas : le rôle
  ADMINISTRATEUR du dépôt. `main` est protégée par le ruleset `20260729_ruleset`
  (règles `deletion` et `non_fast_forward`), et seule la dérogation de rôle
  autorise le push forcé — GitHub la journalise explicitement :
      remote: Bypassed rule violations for refs/heads/main:
      remote: - Cannot force-push to this branch
  Aucun jeton non-administrateur n'y parviendra, `GITHUB_TOKEN` d'Actions
  compris. Si la dérogation était retirée un jour, cette étape cesserait de
  fonctionner en silence jusqu'au prochain bornage.
FIN
  printf '\n  DÉPÔT QU%s ON BORNE : %s\n' "'" "$cible" >&2
  cat <<'FIN' >&2
  C'est LÀ qu'aucun run de données ne doit tourner — pas sur le dépôt depuis
  lequel on lit cette ligne, si ce n'est pas le même. L'ambiguïté ne coûte rien
  tant qu'on n'a qu'un dépôt ; elle apparaît à la première répétition, et une
  répétition est exactement le moment où « le dépôt » désigne deux choses.
FIN
  _precondition "aucun run de données en cours sur $cible" \
      _aucun_run_en_cours "$cible" || return 1
  _confirmer_phrase "$PHRASE_PUSH" \
      "Le push forcé réécrit l'historique de $cible pour TOUS les clones existants." \
      || { _journaliser "ARRÊT — push forcé refusé à l'étape 4."; return 1; }
  _journaliser "ÉTAPE 4 — push forcé de main-borne vers main sur $cible."
  git push --force-with-lease origin main-borne:main 2>&1 | tee -a "$JOURNAL"
  _terminer_etape 4
}

_etape_5_supprimer_les_refs() {
  _exiger_etapes_precedentes 5 || return 1
  cat <<'FIN' >&2

ÉTAPE 5 — SUPPRIMER LES AUTRES REFS. POINT DE NON-RETOUR.

  Une ref oubliée ré-épingle l'ancien historique et LE GAIN EST NUL, sans que
  rien ne le dise. Trois corrections que la répétition du 28/08/2026 a rendues :

    · LES TAGS COMPTENT. Le texte ne parlait que de « branches ».
      `amendements-figes-v1`, oublié, ré-épinglait 386 commits.
    · `dev` SE REPOINTE, ELLE NE SE SUPPRIME PAS. Elle ne porte aucun commit
      propre (mesuré : 0), mais gardait 21 commits de données atteignables —
      pas parce qu'elle est grosse, parce qu'elle est ancienne.
    · LES `refs/pull/*` NE SONT PAS SUPPRIMABLES : GitHub les gère. Ne pas les
      chercher. Elles gardent l'ancien historique atteignable côté serveur, et
      la taille annoncée a pourtant chuté (513 → 240 Mo) : non tranchable de
      l'extérieur, et consigné comme tel.
FIN
  _journaliser "ÉTAPE 5 — refs distantes avant suppression :"
  git ls-remote --heads --tags origin 2>&1 | tee -a "$JOURNAL"
  _confirmer_phrase "$PHRASE_REFS" \
      "Les branches et tags distants autres que main vont être supprimés ou repointés." \
      || { _journaliser "ARRÊT — suppression des refs refusée à l'étape 5."; return 1; }

  local nouveau ref nom
  nouveau=$(git rev-parse main-borne)
  while read -r _ ref; do
    nom=${ref#refs/heads/}
    [[ "$nom" == "main" ]] && continue
    if [[ "$nom" == "dev" ]]; then
      _journaliser "ÉTAPE 5 — dev REPOINTÉE sur le nouveau main ($nouveau) : elle ne porte aucun commit propre, la supprimer serait contraire à la politique et la garder en l'état annulerait le gain."
      git push --force origin "$nouveau:refs/heads/dev" 2>&1 | tee -a "$JOURNAL"
      continue
    fi
    _journaliser "ÉTAPE 5 — suppression de la branche $nom."
    git push origin --delete "$nom" 2>&1 | tee -a "$JOURNAL"
  done < <(git ls-remote --heads origin)

  while read -r _ ref; do
    nom=${ref#refs/tags/}
    nom=${nom%^\{\}}
    _journaliser "ÉTAPE 5 — suppression du tag $nom (le point oublié le 28/08/2026)."
    git push origin --delete "refs/tags/$nom" 2>&1 | tee -a "$JOURNAL"
  done < <(git ls-remote --tags origin | grep -v '\^{}$' || true)

  _journaliser "ÉTAPE 5 — refs restantes (les refs/pull/* sont attendues et NON supprimables) :"
  git ls-remote origin 2>&1 | tee -a "$JOURNAL"
  _terminer_etape 5
}

_etape_6_verifier_la_ci() {
  _exiger_etapes_precedentes 6 || return 1
  local cible
  cible=$(_depot_cible) || cible=""
  # Pas de backtick dans une chaîne entre guillemets : le shell l'EXÉCUTE.
  # C'est le défaut trouvé par #567 — trois substitutions involontaires dans un
  # heredoc non quoté, et `--preparer` mourait avant d'imprimer sa procédure.
  _journaliser "ÉTAPE 6 — la CI sur l'historique borné. C'était la case centrale de #569, et elle est passée : Tests (pytest) vert sur f307be7."
  gh run list --repo "$cible" --limit 5 2>&1 | tee -a "$JOURNAL" || true
  cat <<'FIN' >&2

  À vérifier aussi, et qu'aucun test unitaire n'atteint :
    · le pipeline tourne encore (un run de données sur l'historique borné) ;
    · `audit_diff_profils --ref <commit d'avant la coupure>` REFUSE et le DIT,
      au lieu de conclure « aucune perte » (établi par la PR #581) ;
    · un clone frais pèse bien ce que l'étape 1 avait annoncé.
FIN
  _terminer_etape 6
}

_etape_7_remesurer() {
  _exiger_etapes_precedentes 7 || return 1
  _journaliser "ÉTAPE 7 — re-mesure et consignation."
  scripts/borner_historique_donnees.sh --mesurer --fenetre "$FENETRE" 2>&1 | tee -a "$JOURNAL"
  cat <<'FIN' >&2

  CE QUI EST ATTENDU, et qui contredit la documentation d'avant #569 : la
  taille annoncée par GitHub BAISSE, et vite. Mesuré le 28/08/2026 sur le banc :
  513 → 240 Mo en quelques minutes, clone frais 534 → 268 Mo, 865 → 108 commits
  servis. #434 et #551 écrivaient l'inverse. Ne pas prendre une baisse pour une
  anomalie, ni une absence de baisse pour un échec : les deux ont été observées.

  DURÉE DE VIE DU TAG DE SAUVEGARDE `archive/pre-borne-<date>` (#576, point f) :
  le garder jusqu'à ce que LES DEUX conditions soient remplies —
    · Software Heritage a conclu une visite `full` couvrant l'historique
      d'AVANT la coupure (c'est le moment où l'archive prend le relais) ;
    · la CI est verte sur l'historique borné et un run de données y est passé ;
  avec un PLANCHER DE 30 JOURS, la fenêtre elle-même (#551 : un mois de
  données), au-delà duquel un regret ne porte plus sur cette coupure-ci.
  Avant ce point, le tag est la SEULE reprise immédiate :
      git push --force origin <tag>^{commit}:main
  (et elle ne marche que tant que GitHub n'a pas ramassé les objets). Après, il
  ne fait plus que retenir des objets côté local — le supprimer est alors le
  geste correct, pas un oubli.

  Ne JAMAIS pousser ce tag sur le dépôt borné : il y garderait tout
  l'historique atteignable et le gain serait nul.
FIN
  _terminer_etape 7
}

_principal() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --lister)    _lister_etapes; exit 0 ;;
      --fenetre)   FENETRE=$2; shift 2 ;;
      --journal)   JOURNAL=$2; shift 2 ;;
      --reprendre) JOURNAL=$2; shift 2 ;;
      --etape)     ETAPE_UNIQUE=$2; DEPUIS=$2; JUSQU_A=$2; shift 2 ;;
      --jusqu-a)   JUSQU_A=$2; shift 2 ;;
      -h|--help)   awk 'NR==1{next} /^#/{print; next} {exit}' "$0"; exit 0 ;;
      *) echo "[!] Option inconnue : $1" >&2; exit 2 ;;
    esac
  done

  cd "$(git rev-parse --show-toplevel)"
  if [[ -z "$JOURNAL" ]]; then
    mkdir -p audit
    JOURNAL="audit/bornage-$(date +%Y%m%dT%H%M%S).journal"
  fi
  : >> "$JOURNAL"
  _journaliser "SESSION — fenêtre $FENETRE, étapes $DEPUIS à $JUSQU_A, journal $JOURNAL."
  _journaliser "Ce runner porte les gestes irréversibles ; borner_historique_donnees.sh ne pousse toujours JAMAIS (#551)."

  local n
  for ((n = DEPUIS; n <= JUSQU_A; n++)); do
    if [[ -z "$ETAPE_UNIQUE" ]] && _etape_terminee "$n"; then
      _journaliser "ÉTAPE $n — déjà consignée comme terminée, passée."
      continue
    fi
    case "$n" in
      1) _etape_1_mesurer ;;
      2) _etape_2_verifier_archivage ;;
      3) _etape_3_preparer ;;
      4) _etape_4_pousser ;;
      5) _etape_5_supprimer_les_refs ;;
      6) _etape_6_verifier_la_ci ;;
      7) _etape_7_remesurer ;;
      *) echo "[!] Étape inconnue : $n" >&2; exit 2 ;;
    esac || { _journaliser "SESSION INTERROMPUE à l'étape $n. Le journal est $JOURNAL ; reprendre avec --reprendre $JOURNAL."; exit 1; }
  done
  _journaliser "SESSION TERMINÉE — étapes $DEPUIS à $JUSQU_A."
}

# Exécuté, il déroule ; SOURCÉ, il ne fait que définir ses fonctions. C'est ce
# qui permet de tester les confirmations et l'ordre sans approcher d'un geste
# irréversible.
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  _principal "$@"
fi
