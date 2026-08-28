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

import pathlib
import re

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


def test_les_trois_modes_de_recollecte_se_nomment():
    """Trois modes se cachent derrière deux booléens, et le formulaire de
    lancement masque le nom du champ : la description est tout ce qu'on lit.

    Le défaut invisible a coûté deux runs le 28/08/2026 sur #562 — un
    progressif, puis un à pleine échelle avec `roster_limit=0`. Une extraction
    ne recollecte PAS un profil déjà écrit, et l'en-tête du job roster le dit
    depuis #445 : « un run à pleine échelle ne corrige RIEN de l'existant, il
    ne fait qu'étendre la frontière ».

    Pire, le mode le plus utile était le moins découvrable : `refresh_existing_only`
    recollecte l'existant EN FUSIONNANT — le geste sûr pour propager un
    correctif — et s'annonçait « Limit roster to pre-existing members », c'est-à-dire
    comme un filtre de population.
    """
    contenu = GENERATE.read_text(encoding="utf-8")
    bloc = contenu[contenu.index("  workflow_dispatch:"):contenu.index("\n# Moindre privilège")]
    desc = dict(re.findall(r'^      ([a-z_]+):\n        description: "([^"]*)"', bloc, re.MULTILINE))

    # Les trois options qui recollectent le disent avec le même mot.
    for nom in ("cold_start", "overwrite_profiles", "refresh_existing_only"):
        assert "re-collect" in desc[nom].lower(), (
            f"`{nom}` recollecte l'existant : le libellé doit le dire avec le "
            "même mot que les deux autres, sinon on ne les compare pas."
        )

    # Et ce qui les sépare — écraser ou fusionner — doit être lisible.
    for nom in ("cold_start", "overwrite_profiles"):
        assert "overwrite" in desc[nom].lower(), f"`{nom}` écrase : le dire"
        assert "drops" in desc[nom].lower(), (
            f"`{nom}` perd ce que la collecte du jour ne rend pas : le dire, "
            "c'est la différence qui compte face à l'option fusionnante"
        )
    assert "merging" in desc["refresh_existing_only"].lower(), (
        "`refresh_existing_only` FUSIONNE : c'est le mode sûr, et c'est ce qui "
        "le distingue des deux autres"
    )

    # `roster_limit` dit ce qu'il fait, sans tenter d'expliquer l'anomalie du
    # zéro : `0` rafraîchit MOINS que `20`, parce que sans `--limit` la branche
    # d'exemption au saut n'est pas empruntée. Aucune formulation courte ne rend
    # ça naturel — c'est un défaut de conception, suivi par #578, et un libellé
    # de formulaire n'est pas l'endroit où on documente un piège réductible.
    assert "new ones first" in desc["roster_limit"].lower(), (
        "`roster_limit` est un budget de traitement, pas une borne sur le "
        "roster : il va d'abord aux nouveaux, puis aux profils périmés"
    )


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
