"""Garde-fou : une seule source d'instructions, plusieurs noms de fichiers.

`AGENTS.md` est la source. Les outils qui attendent un autre nom — Claude Code
lit `CLAUDE.md`, GitHub Copilot lit `.github/copilot-instructions.md` — y
accèdent par un **lien symbolique**, pas par une copie.

Pourquoi un lien et pas une copie synchronisée : une copie **peut** diverger,
on ne fait que le détecter. Un lien ne le peut pas, c'est le même objet. La
dérive n'est pas surveillée, elle est impossible.

Ce que ce test attrape, et qu'un lien seul ne dit pas :

1. un checkout Windows sans `core.symlinks=true`, qui remplace le lien par un
   fichier texte d'une ligne contenant le chemin — silencieusement, et un agent
   lirait alors « AGENTS.md » au lieu des instructions ;
2. quelqu'un qui remplace le lien par une copie, croyant simplifier ;
3. un nouvel outil ajouté avec son fichier, sans lien.

Il ne dit RIEN de ce que chaque outil fait du lien : qu'un chargeur le suive
est une propriété de l'outil, vérifiable seulement en l'exécutant. Ce test
garantit la source unique, pas la lecture.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
SOURCE = "AGENTS.md"

# nom du fichier attendu par l'outil -> cible relative, depuis son répertoire
ALIAS: dict[str, str] = {
    "CLAUDE.md": SOURCE,
    ".github/copilot-instructions.md": f"../{SOURCE}",
}


def test_la_source_existe_et_nest_pas_un_lien():
    """`AGENTS.md` est le fichier réel — pas un alias d'autre chose."""
    source = RACINE / SOURCE
    assert source.is_file(), f"{SOURCE} manquant"
    assert not source.is_symlink(), (
        f"{SOURCE} est devenu un lien : la source doit rester le fichier réel, "
        "sinon la chaîne d'alias n'a plus d'origine."
    )


@pytest.mark.parametrize("alias", sorted(ALIAS))
def test_chaque_alias_est_un_lien_vers_la_source(alias: str):
    chemin = RACINE / alias
    assert chemin.exists(), (
        f"`{alias}` manquant. Les outils qui attendent ce nom ne liront aucune "
        f"instruction. Le poser : `ln -s {ALIAS[alias]} {alias}`."
    )
    assert chemin.is_symlink(), (
        f"`{alias}` n'est pas un lien symbolique mais un fichier ordinaire. "
        "Deux causes : un checkout Windows sans `core.symlinks=true` (le fichier "
        f"contient alors la chaîne « {ALIAS[alias]} »), ou une copie posée à la "
        "main. Une copie diverge ; le lien est la seule forme qui ne le peut pas."
    )
    cible = os.readlink(chemin)
    assert cible == ALIAS[alias], (
        f"`{alias}` pointe vers « {cible} », attendu « {ALIAS[alias]} »."
    )


@pytest.mark.parametrize("alias", sorted(ALIAS))
def test_chaque_alias_rend_le_contenu_de_la_source(alias: str):
    """Le lien résout, et il résout au bon endroit.

    `is_symlink` ne dit pas que la cible existe : un lien cassé le passerait.
    """
    lu = (RACINE / alias).read_text(encoding="utf-8")
    attendu = (RACINE / SOURCE).read_text(encoding="utf-8")
    assert lu == attendu, (
        f"`{alias}` ne rend pas le contenu de {SOURCE} — lien cassé, ou cible "
        "déplacée."
    )
