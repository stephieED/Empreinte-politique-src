"""Garde-fou : le contrat d'inputs entre `generate-data.yml` et sa relance
automatique `retry-generate-data.yml`.

Contexte. `retry-generate-data.yml` ne relit pas les inputs du run précédent —
l'API ne les expose pas — il les **reconstruit en analysant les logs**, puis
redéclenche `generate-data.yml` par `gh workflow run -f nom=valeur`. Ce
couplage est réel mais invisible : rien dans l'un ne référence l'autre.

Deux pannes possibles, toutes deux constatées le 20/08/2026 :

1. **Un `-f` qui ne correspond à aucun input.** La suppression de l'input
   `workers` a laissé `-f workers=...` dans la relance : le dispatch aurait
   échoué en 422 « Unexpected inputs provided », et personne ne l'aurait su
   avant la première panne à relancer.

2. **Une sortie écrite sous un nom, lue sous un autre.** Au renommage, les
   lectures `steps.inputs.outputs.X` ont été mises à jour mais pas les
   `echo "X=..." >> $GITHUB_OUTPUT`. La relance serait repartie avec les
   valeurs par défaut au lieu de celles du run d'origine — sans erreur, sans
   trace : un run `cold_start=true` relancé en incrémental. C'est exactement
   la régression que le commentaire de la relance dit avoir déjà corrigée une
   fois.

Aucune des deux ne se voit à la relecture, et aucune ne se manifeste avant
qu'une relance soit nécessaire — c'est-à-dire au pire moment.

Volontairement sans PyYAML (absent de requirements.txt), comme les autres
`test_ci_*`.
"""

import os
import pathlib
import re
import subprocess

WORKFLOWS = pathlib.Path(__file__).resolve().parents[1] / ".github" / "workflows"
GENERATE = WORKFLOWS / "generate-data.yml"
RETRY = WORKFLOWS / "retry-generate-data.yml"


def _inputs_declares() -> set[str]:
    """Noms des inputs de `workflow_dispatch` dans generate-data.yml."""
    contenu = GENERATE.read_text(encoding="utf-8")
    bloc = contenu[contenu.index("  workflow_dispatch:"):contenu.index("\n# Moindre privilège")]
    return set(re.findall(r"^      ([a-z_]+):$", bloc, re.MULTILINE))


def test_chaque_input_passe_a_la_relance_existe():
    """Un `-f` orphelin fait échouer le dispatch en 422, jamais avant."""
    passes = set(re.findall(r"-f ([a-z_]+)=", RETRY.read_text(encoding="utf-8")))
    inconnus = passes - _inputs_declares()
    assert not inconnus, (
        f"retry-generate-data.yml passe des inputs que generate-data.yml ne "
        f"déclare pas : {sorted(inconnus)}. `gh workflow run` échouerait en 422 "
        "« Unexpected inputs provided » — et seulement le jour où une relance "
        "est nécessaire."
    )


def test_chaque_sortie_lue_par_la_relance_est_ecrite():
    """Une sortie lue mais jamais écrite vaut la chaîne vide : la relance
    repart alors sur les défauts, silencieusement."""
    contenu = RETRY.read_text(encoding="utf-8")
    lues = set(re.findall(r"steps\.inputs\.outputs\.([a-z_]+)", contenu))
    ecrites = set(re.findall(r'echo "([a-z_]+)=[^"]*" >> "\$GITHUB_OUTPUT"', contenu))
    manquantes = lues - ecrites
    assert not manquantes, (
        f"sorties lues mais jamais écrites : {sorted(manquantes)}. La relance "
        "repartirait sur les valeurs par défaut au lieu de celles du run "
        "d'origine, sans erreur ni trace."
    )


def _descriptions() -> dict[str, str]:
    contenu = GENERATE.read_text(encoding="utf-8")
    bloc = contenu[contenu.index("  workflow_dispatch:"):contenu.index("\n# Moindre privilège")]
    return dict(re.findall(r'^      ([a-z_]+):\n        description: "([^"]*)"', bloc, re.MULTILINE))


def _options(nom: str) -> list[str]:
    """Valeurs d'un `type: choice`. Elles s'AFFICHENT dans le formulaire, donc
    elles portent une part du sens que la description n'a plus à redire."""
    contenu = GENERATE.read_text(encoding="utf-8")
    bloc = contenu[contenu.index(f"      {nom}:\n"):]
    bloc = bloc[bloc.index("        options:\n") + len("        options:\n"):]
    valeurs = []
    for ligne in bloc.splitlines():
        if not ligne.startswith("          - "):
            break
        valeurs.append(ligne[len("          - "):].strip())
    return valeurs


def test_les_deux_axes_sont_deux_champs_distincts():
    """Un seul champ répondait à deux questions, et c'est pour ça qu'aucune
    réécriture de libellé ne le rendait lisible (#578).

    Axe 1 : ce qu'on fait des profils DÉJÀ écrits — trois états, donc un menu
    et non un booléen. Axe 2 : si on en écrit de NOUVEAUX. Le cache est un
    troisième champ, qui n'appartient à aucun des deux.
    """
    desc = _descriptions()

    assert _options("existing_profiles") == ["leave-as-is", "refresh", "overwrite"]
    assert _options("roster_coverage") == ["current-members-only", "add-uncovered-members"]

    # Le défaut est le mode SÛR : sur #562, le code était juste pendant deux
    # runs et la donnée restait fausse parce qu'il fallait le demander.
    contenu = GENERATE.read_text(encoding="utf-8")
    bloc_axe1 = contenu[contenu.index("      existing_profiles:"):contenu.index("      roster_coverage:")]
    assert "default: refresh" in bloc_axe1, (
        "le mode le plus sûr doit être celui qu'on obtient sans rien cocher"
    )

    # Ce qui sépare les deux modes qui recollectent — fusionner ou remplacer —
    # est ce qu'on lit à l'écran, pas ce qu'on devine.
    axe1 = desc["existing_profiles"].lower()
    assert "merges" in axe1, "`refresh` FUSIONNE : c'est ce qui le rend sûr"
    assert "replaces" in axe1, "`overwrite` REMPLACE"
    assert "drop" in axe1, (
        "`overwrite` perd ce que la collecte du jour ne rend pas : c'est la "
        "différence qui compte face au mode fusionnant"
    )

    # Les anciens champs ne doivent pas survivre : deux façons de demander la
    # même chose, c'est le défaut que #578 corrige.
    assert "overwrite_profiles" not in _inputs_declares()
    assert "refresh_existing_only" not in _inputs_declares()


def test_le_cache_ne_commande_plus_la_politique_d_ecriture():
    """`cold_start` dit à quel point les données SOURCES doivent être fraîches.

    Il portait aussi `--no-merge` et la purge de `raw_data/profiles/`, deux
    politiques d'écriture. Conséquence : « écraser sans purger le cache » —
    le cas courant, on réécrit à partir d'archives déjà téléchargées — était
    demandable, mais « repartir de sources fraîches en fusionnant » ne l'était
    pas.
    """
    contenu = GENERATE.read_text(encoding="utf-8")

    for ligne in contenu.splitlines():
        if "MERGE_FLAG=(--no-merge)" in ligne or "MERGE_FLAG=(--merge-existing)" in ligne:
            assert "$FRESH" not in ligne and "cold_start" not in ligne, (
                f"le cache commande encore la politique d'écriture : {ligne.strip()}"
            )

    assert "find raw_data/profiles -name \"*.json\" -delete" not in contenu, (
        "cold_start effaçait les profils bruts : une politique d'écriture "
        "déguisée en politique de fraîcheur — un profil effacé n'a plus rien "
        "à fusionner."
    )

    assert "cold_start" not in _descriptions()["existing_profiles"], (
        "les libellés sont les LIBELLÉS DU FORMULAIRE : ils ne renvoient "
        "jamais à un autre champ par un nom que personne ne voit à l'écran"
    )


def test_roster_limit_est_un_plafond_et_rien_d_autre():
    """`roster_limit` conflatait « combien » et « faut-il étendre » (#578).

    Avec l'axe couverture explicite, il ne reste qu'un plafond. Son défaut
    passe à 0 : le rollout progressif qu'il budgétait est fini (roster couvert
    à 452/452), et un plafond ferait mentir le défaut `refresh`, qui promet
    qu'un correctif atteint l'existant sans qu'on le demande.
    """
    contenu = GENERATE.read_text(encoding="utf-8")
    bloc = contenu[contenu.index("      roster_limit:"):contenu.index("      collect_interventions:")]
    assert "default: 0" in bloc

    desc = _descriptions()["roster_limit"].lower()
    assert "cap" in desc, "c'est un plafond, et le libellé doit le dire"
    assert "no cap" in desc, "`0` doit annoncer ce qu'il fait : pas de plafond"


# ---------------------------------------------------------------------------
# Les six combinaisons des deux axes
# ---------------------------------------------------------------------------
#
# Le bloc de décision du job roster est EXÉCUTÉ, pas relu : c'est du bash, et
# une table de correspondance vérifiée par lecture de texte ne prouve rien de
# ce qui tourne. Le script est extrait du workflow et tronqué avant l'appel à
# `generate_all_profiles.py` — aucune expression `${{ }}` ne s'y trouve avant
# ce point, elles vivent toutes dans le bloc `env:`.

def _script_decision_roster() -> str:
    contenu = GENERATE.read_text(encoding="utf-8")
    bloc = contenu[contenu.index("      - name: Extraction roster-driven (mode léger)"):]
    bloc = bloc[bloc.index("        run: |\n") + len("        run: |\n"):]
    lignes = []
    for ligne in bloc.splitlines():
        if ligne.strip().startswith("/usr/bin/time"):
            break
        lignes.append(ligne[10:] if ligne.startswith(" " * 10) else ligne)
    script = "\n".join(lignes)
    assert "${{" not in script, (
        "le bloc de décision contient une expression GitHub Actions : elle "
        "doit rester dans `env:`, sinon ce test ne peut plus l'exécuter."
    )
    return script


def _flags(tmp_path, existing: str, coverage: str, limit: str = "0"):
    # `OVERWRITE` est calculé par GHA (`inputs.existing_profiles == 'overwrite'`) :
    # la ligne est vérifiée juste en dessous pour que cette reproduction ne
    # puisse pas diverger en silence.
    script = _script_decision_roster() + (
        '\nprintf "FLAG:%s\\n" "${POP_FLAG[@]}" "${MERGE_FLAG[@]}" "${LIMIT_FLAG[@]}"\n'
    )
    resultat = subprocess.run(
        ["bash", "-c", script],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env={
            "PATH": os.environ["PATH"],
            "EXISTING_PROFILES": existing,
            "ROSTER_COVERAGE": coverage,
            "OVERWRITE": "true" if existing == "overwrite" else "false",
            "ROSTER_LIMIT": limit,
        },
    )
    assert resultat.returncode == 0, resultat.stderr
    drapeaux = [l[len("FLAG:"):] for l in resultat.stdout.splitlines() if l.startswith("FLAG:")]
    return [d for d in drapeaux if d], resultat.stdout


def test_l_expression_overwrite_reste_alignee_sur_l_axe_1():
    assert "OVERWRITE: ${{ inputs.existing_profiles == 'overwrite' }}" in \
        GENERATE.read_text(encoding="utf-8")


def test_les_six_combinaisons_des_deux_axes_sont_atteignables(tmp_path):
    """Deux axes DISJOINTS : 3 × 2, et les six se demandent.

    Celle qui manquait : « recollecter l'existant EN FUSIONNANT et ajouter les
    nouveaux ». Un seul champ ne pouvait pas la produire — c'est le défaut de
    découpage, pas de vocabulaire, que #578 corrige.
    """
    attendu = {
        ("leave-as-is", "add-uncovered-members"): ["--skip-existing"],
        ("refresh", "add-uncovered-members"): [],
        ("overwrite", "add-uncovered-members"): ["--no-merge"],
        ("refresh", "current-members-only"): ["--refresh-existing"],
        ("overwrite", "current-members-only"): ["--refresh-existing", "--no-merge"],
    }
    for (axe1, axe2), flags in attendu.items():
        obtenus, _ = _flags(tmp_path, axe1, axe2)
        assert obtenus == flags, f"{axe1} × {axe2} → {obtenus}, attendu {flags}"

    # La sixième ne traite personne, et c'est une réponse, pas une panne : on
    # ne touche pas à l'existant et on n'étend pas la couverture.
    obtenus, sortie = _flags(tmp_path, "leave-as-is", "current-members-only")
    assert obtenus == []
    assert "Aucun membre à traiter" in sortie
    # Manifeste VIDE et non absent : « ce job n'a écrit aucun profil » plutôt
    # que « le job a échoué » (#450).
    assert (tmp_path / "_manifest" / "profils-ecrits.txt").read_text(encoding="utf-8") == ""


def test_le_plafond_est_orthogonal_aux_deux_axes(tmp_path):
    """`roster_limit` ne déplace aucune des six cases : il les plafonne.

    C'est le couplage que #578 supprime — la présence de `--limit` commandait
    aussi la politique de rafraîchissement, si bien que `roster_limit=0`
    rafraîchissait MOINS que `roster_limit=20`.
    """
    for axe1 in ("leave-as-is", "refresh", "overwrite"):
        for axe2 in ("current-members-only", "add-uncovered-members"):
            # La case vide sort avant tout calcul de plafond : plafonner un
            # lot vide n'a pas de sens, et le dire coûterait un drapeau.
            if (axe1, axe2) == ("leave-as-is", "current-members-only"):
                continue
            sans, _ = _flags(tmp_path, axe1, axe2, limit="0")
            avec, _ = _flags(tmp_path, axe1, axe2, limit="20")
            assert avec == sans + ["--limit", "20"], (
                f"{axe1} × {axe2} : le plafond change la population "
                f"({sans} → {avec})"
            )


def test_les_deux_axes_sont_propages_par_la_relance():
    """Un run préempté doit repartir dans le MÊME mode (#414 §2).

    Un input que la relance ne passe pas retombe sur son défaut sans erreur ni
    trace : un run `overwrite` relancé en fusion additive, c'est le scénario de
    doublons que ce mode existe pour éviter (#440).
    """
    passes = set(re.findall(r"-f ([a-z_]+)=", RETRY.read_text(encoding="utf-8")))
    for nom in ("existing_profiles", "roster_coverage", "cold_start", "roster_limit"):
        assert nom in passes, f"`{nom}` n'est pas propagé par la relance"


def test_aucune_description_d_input_n_est_un_essai():
    """Une description longue n'est pas lue dans un formulaire de lancement.

    Le seuil est délibérément permissif — il n'attrape que la sédimentation,
    pas une phrase un peu longue. Le pourquoi appartient à
    docs/technical_decisions.md, pas à l'écran de lancement.
    """
    contenu = GENERATE.read_text(encoding="utf-8")
    bloc = contenu[contenu.index("  workflow_dispatch:"):contenu.index("\n# Moindre privilège")]
    trop_longues = []
    for nom, desc in re.findall(r'^      ([a-z_]+):\n        description: "([^"]*)"', bloc, re.MULTILINE):
        mots = len(desc.split())
        if mots > 40:
            trop_longues.append(f"{nom} ({mots} mots)")
    assert not trop_longues, (
        "descriptions d'input trop longues pour un formulaire de lancement : "
        f"{trop_longues}. Déplacer le rationale vers docs/technical_decisions.md."
    )
