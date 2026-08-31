"""Le sparse-checkout d'`extract-an` couvre ce que la collecte AN lit (#498).

**Pourquoi ce garde-fou existe.** Le run `33404236969` (31/08/2026) a tué ses
13 shards l'un après l'autre à 5 min 00 **dans `actions/checkout`**, l'étape
d'extraction restant `skipped`. La cause n'était pas le réseau : l'arbre pesait
8 483 Mio, dont **7 525 dans le seul `raw_data/profiles/`**, et `extract-an` est
le seul job à `timeout-minutes: 5`. Un shard tué par `timeout-minutes` n'écrit
aucun profil (#498) — 40 minutes pour rien.

Le correctif est une **liste blanche** : un shard ne matérialise que le code,
les référentiels de premier niveau, les index figés, et **son propre** profil
brut. Ce qui rend la liste dangereuse est ce qui rend celle de `tests.yml`
dangereuse — un chemin oublié **passe en local et échoue en CI** (#434, #518
deux fois, #520). Ici c'est pire que dans `tests.yml` : un référentiel absent ne
lève pas toujours, il se replie (`correspondance_acteurs_an.json` a un repli
*déclaré*, #525), et la collecte publie alors moins sans que rien n'échoue.

**Ce que ce test relève.** Il ne devine pas : il calcule la **fermeture des
imports** de `src/generate_all_profiles.py` restreinte à `src/`, puis relève
dans ces seuls modules les littéraux de chemin sous `raw_data/`. Un module de
migration ou d'audit, qui ne tourne pas dans le shard, n'entre donc pas dans le
périmètre — et un nouvel import l'y fait entrer tout seul.

Volontairement sans PyYAML (absent de `requirements.txt`), comme les autres
gardes-fous de workflow de ce dépôt.
"""

import ast
import re
from pathlib import Path

import _outils_ci

RACINE = Path(__file__).resolve().parents[1]
WORKFLOW = RACINE / ".github" / "workflows" / "generate-data.yml"
SRC = RACINE / "src"

#: Le point d'entrée du shard, tel que le workflow l'invoque.
POINT_ENTREE = "generate_all_profiles"

#: `Path("raw_data") / "x"` et `Path("raw_data/x")`.
#:
#: Le second motif s'arrête au premier caractère qui ne peut pas appartenir à
#: un chemin : plusieurs messages destinés à l'utilisatrice nomment un fichier
#: **puis continuent la phrase** (`"raw_data/candidats.json, dont extract-an
#: collecte…"`). Sans cette borne, le chemin relevé serait la phrase entière et
#: le test échouerait sur un fichier pourtant couvert.
_LITTERAL_COMPOSE = re.compile(r'"raw_data"\s*(?:/\s*"([^"/]+)")')
_LITTERAL_PLAT = re.compile(r'"raw_data/([\w./-]+)"?')


def _liste_blanche() -> frozenset[str]:
    blanche = _outils_ci.lire_liste_blanche(WORKFLOW)
    assert blanche, (
        "bloc `sparse-checkout: |` absent, vide ou de forme inattendue dans "
        "generate-data.yml — voir `tests/_outils_ci.lire_liste_blanche`.")
    return blanche


def _fermeture_des_imports() -> set[str]:
    """Modules de `src/` atteignables depuis le point d'entrée du shard."""
    vus: set[str] = set()
    a_voir = [POINT_ENTREE]
    while a_voir:
        nom = a_voir.pop()
        if nom in vus:
            continue
        chemin = SRC / f"{nom}.py"
        if not chemin.is_file():
            continue
        vus.add(nom)
        arbre = ast.parse(chemin.read_text(encoding="utf-8"), filename=str(chemin))
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Import):
                a_voir.extend(alias.name.split(".")[0] for alias in noeud.names)
            elif isinstance(noeud, ast.ImportFrom) and noeud.module:
                a_voir.append(noeud.module.split(".")[0])
    return vus


def _sans_prose(texte: str) -> str:
    """Le module amputé de ses commentaires et de ses docstrings.

    **Ce n'est pas de la coquetterie** : la prose de ce dépôt cite les chemins
    en toutes lettres, et les deux premiers chemins relevés par ce test
    l'avaient été dans une phrase, pas dans un appel. Un garde-fou qui échoue
    sur une phrase se fait désarmer. Même règle que #529, qui lit le code
    exécuté et jamais les commentaires.
    """
    arbre = ast.parse(texte)
    lignes = texte.split("\n")
    for noeud in ast.walk(arbre):
        corps = getattr(noeud, "body", None)
        if not isinstance(corps, list) or not corps:
            continue
        if not isinstance(noeud, (ast.Module, ast.ClassDef,
                                  ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        premier = corps[0]
        if not (isinstance(premier, ast.Expr)
                and isinstance(premier.value, ast.Constant)
                and isinstance(premier.value.value, str)):
            continue
        for i in range(premier.lineno - 1, premier.end_lineno):
            lignes[i] = ""
    return "\n".join(
        ligne for ligne in lignes if not ligne.lstrip().startswith("#"))


def _chemins_raw_data_lus() -> set[str]:
    """Chemins sous `raw_data/` que le code du shard construit réellement."""
    trouves: set[str] = set()
    for nom in sorted(_fermeture_des_imports()):
        code = _sans_prose((SRC / f"{nom}.py").read_text(encoding="utf-8"))
        trouves.update(f"raw_data/{m}" for m in _LITTERAL_COMPOSE.findall(code))
        trouves.update(f"raw_data/{m}" for m in _LITTERAL_PLAT.findall(code))
    return trouves


def _couvert(chemin: str, blanche: frozenset[str]) -> bool:
    """Un chemin est couvert par une entrée égale ou par un de ses parents."""
    parts = chemin.split("/")
    return any("/".join(parts[:i]) in blanche for i in range(1, len(parts) + 1))


def test_un_seul_bloc_sparse_checkout_dans_le_workflow():
    """`lire_liste_blanche` rend le PREMIER bloc du fichier. Le jour où un
    second job en reçoit un, ce test lirait celui d'un autre job sans rien
    dire — et validerait une liste blanche qui n'est pas celle d'`extract-an`.
    Ajouter un bloc ailleurs oblige donc à donner son workflow à ce test."""
    texte = WORKFLOW.read_text(encoding="utf-8")
    assert texte.count("sparse-checkout: |") == 1, (
        "plusieurs blocs `sparse-checkout: |` dans generate-data.yml : ce "
        "garde-fou lit le premier et croirait vérifier extract-an")


def test_la_fermeture_des_imports_atteint_bien_le_coeur_de_la_collecte():
    """Sans ce cas, une fermeture cassée rendrait les autres verts pour rien —
    c'est le défaut du diagnostic muet de #518, transposé."""
    modules = _fermeture_des_imports()
    assert POINT_ENTREE in modules
    for attendu in ("candidate_profile", "merge_profile", "profil_brut"):
        assert attendu in modules, (
            f"`{attendu}` n'est plus atteignable depuis `{POINT_ENTREE}` : la "
            "fermeture des imports ne décrit plus ce que le shard exécute.")


def test_la_liste_blanche_couvre_les_referentiels_que_la_collecte_lit():
    blanche = _liste_blanche()
    # `raw_data/profiles` est couvert **partiellement et exprès** : le shard ne
    # matérialise que son propre profil, via les deux entrées `matrix.slug`.
    # C'est tout l'objet du lot — l'y inscrire en entier ramènerait 7 525 Mio.
    non_couverts = sorted(
        chemin for chemin in _chemins_raw_data_lus()
        if not chemin.startswith("raw_data/profiles")
        and not _couvert(chemin, blanche))
    assert not non_couverts, (
        "ces chemins sont lus par la collecte AN mais absents du "
        "sparse-checkout d'extract-an — ils seront absents du disque du "
        f"runner, et la collecte se repliera en silence : {non_couverts}")


def test_le_shard_materialise_son_propre_profil_brut():
    """Socle **et** tranches (#580). Sans le socle, la fusion additive repart de
    zéro et republie un profil amputé sans que rien n'échoue (#465)."""
    blanche = _liste_blanche()
    assert "raw_data/profiles/${{ matrix.slug }}.json" in blanche, (
        "le socle du profil du shard n'est pas dans la liste blanche")
    assert "raw_data/profiles/${{ matrix.slug }}" in blanche, (
        "le répertoire de tranches par législature n'est pas dans la liste "
        "blanche : un profil partitionné (#580) reviendrait sans ses "
        "amendements")


def test_le_corpus_entier_reste_hors_de_la_liste_blanche():
    """L'autre sens de la liste. `raw_data` entier, ou `raw_data/profiles`
    entier, rendrait le lot inutile et le timeout se refermerait."""
    blanche = _liste_blanche()
    assert "raw_data" not in blanche
    assert "raw_data/profiles" not in blanche
    assert "pivot_data" not in blanche, (
        "extract-an ne lit pas le pivot : l'y inscrire ajouterait 894 Mio")


def test_le_filtre_de_blobs_accompagne_la_liste_blanche():
    """Sans `filter: blob:none`, git télécharge les blobs de tout l'arbre avant
    de n'en matérialiser qu'une fraction — le coût qu'on supprime revient."""
    texte = WORKFLOW.read_text(encoding="utf-8")
    debut = texte.index("sparse-checkout: |")
    entete = texte[max(0, debut - 400):debut]
    assert "filter: blob:none" in entete, (
        "`filter: blob:none` manque au checkout d'extract-an")
    assert "sparse-checkout-cone-mode: false" in entete, (
        "le mode cône ne sait pas exprimer `raw_data/profiles/<slug>.json` : "
        "la liste blanche serait silencieusement élargie au répertoire")


def test_le_timeout_du_shard_est_inchange():
    """Le lot supprime la CAUSE, il ne desserre pas la contrainte. Si ce test
    échoue parce que le timeout a été relevé, c'est que quelqu'un a soigné le
    symptôme : `AGENTS.md` §3b interdit de le faire seul (#498)."""
    texte = WORKFLOW.read_text(encoding="utf-8")
    assert "timeout-minutes: ${{ inputs.collect_interventions && 10 || 5 }}" in texte, (
        "le `timeout-minutes` d'extract-an a changé : relire #498 et "
        "docs/decisions/budget-collecte-interventions.md avant de le valider")
