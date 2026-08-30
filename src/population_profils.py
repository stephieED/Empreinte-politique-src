"""population_profils.py — les deux populations de `pivot_data/profiles/`, et
la seule façon d'en afficher un compte.

`pivot_data/profiles/` porte **deux populations** que rien, dans le système de
fichiers, ne distingue : un répertoire, un motif de nommage, 481 fichiers. Un
`glob("*.pivot.json")` rend 481 slugs — c'est délibéré (#580 a préservé cette
énumérabilité), et c'est aussi ce qui fait qu'un agent qui mesure quoi que ce
soit lit « 481 » sans savoir ce qu'il compte :

  - `meta.provenance == "candidat_declare"` (**13**) — les candidats déclarés à
    la présidentielle, ceux dont `web/` publie une fiche. Un correctif de
    **fusion d'identité** porte sur cette population-là ;
  - `meta.provenance == "roster_groupe"` (**468**) — les membres des groupes
    parlementaires, collectés pour **alimenter les agrégats** de groupe et de
    gouvernement. `src/group_profile.py` ne lit pas leur bloc `identite` : il
    consomme `nom`, `mandats`, `votes`, `interventions`, `amendements`, qui sont
    des listes.

**Ce qui diffère est l'usage, pas l'exigence.** Un correctif de *qualité*
d'identité porte sur les 481 : c'est dans les 468 que se trouvaient les 191
marqueurs HATVP publiés comme des URI et les 28 lieux de naissance faits de
plomberie XML (#556).

Pourquoi un module plutôt qu'une consigne : voir
`docs/decisions/populations-profils-portees-par-les-outils-630.md`. En résumé,
`AGENTS.md` porte la règle mais ne s'applique qu'à qui se souvient de la lire au
bon moment ; la sortie d'un outil, elle, est lue à la seconde où l'on mesure.
D'où la règle de ce module : **tout compte de profils affiché passe par
`Ventilation`**, et rend la ventilation avec le total.

Rétro-compatibilité : un pivot sans `meta.provenance` (généré avant #189) vaut
`"candidat_declare"`, comme dans `validate_profil()` et
`audit_pivot_dataset.compute_repartition_provenance`
(`docs/decisions/provenance-pivot.md`).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

CANDIDAT_DECLARE = "candidat_declare"
ROSTER_GROUPE = "roster_groupe"

#: Libellés affichés. Au singulier près, ce sont les seuls mots qui doivent
#: nommer les deux populations dans une sortie d'outil — un libellé stable est
#: ce qui rend la ventilation reconnaissable d'un rapport à l'autre.
LIBELLE_CANDIDATS = "candidats déclarés"
LIBELLE_ROSTER = "membres de roster"
LIBELLE_AUTRE = "provenance inconnue"
LIBELLE_ILLISIBLES = "illisibles"

#: Séparateur des postes de la ventilation.
SEPARATEUR = " · "

#: Suffixe du fichier pivot d'un profil.
SUFFIXE_PIVOT = ".pivot.json"

#: Clés retenues à la lecture d'un pivot quand on ne veut que la provenance.
#: Même patron que `audit_collecte_vs_publie._crochet` : le décodeur construit
#: bien la liste des 36 154 amendements, mais une liste de `None`, et les
#: chaînes de chaque entrée sont libérées dès l'objet refermé. Sans ce crochet,
#: ventiler le corpus ferait passer 623 Mo de profils par la mémoire.
_CLES_PROVENANCE = frozenset({"meta", "provenance"})


def _crochet_provenance(pairs: list[tuple[str, Any]]) -> dict[str, Any] | None:
    garde = {cle: valeur for cle, valeur in pairs if cle in _CLES_PROVENANCE}
    return garde or None


def provenance_du_profil(profil: Mapping[str, Any] | None) -> str:
    """Provenance d'un profil pivot, absence comprise.

    `meta.provenance` absente vaut `"candidat_declare"` — rétro-compatibilité
    décidée par `docs/decisions/provenance-pivot.md`, et déjà appliquée par
    `validate_profil()`. Une valeur inconnue est rendue **telle quelle** : la
    ranger d'office dans l'un des deux camps est exactement l'approximation que
    ce module existe pour empêcher (AGENTS.md §2 règle 5).
    """
    if not isinstance(profil, Mapping):
        return CANDIDAT_DECLARE
    meta = profil.get("meta")
    valeur = meta.get("provenance") if isinstance(meta, Mapping) else None
    if valeur is None:
        return CANDIDAT_DECLARE
    return str(valeur)


@dataclass(frozen=True)
class Ventilation:
    """Un compte de profils et sa ventilation par population.

    `total` est la **somme des postes**, jamais un compte tenu à part : un
    fichier illisible reste dans le total, sous son propre poste, pour que
    « 481 » et « 13 + 468 » ne puissent pas diverger en silence.
    """

    candidats_declares: int = 0
    membres_roster: int = 0
    provenance_autre: int = 0
    illisibles: int = 0

    @property
    def total(self) -> int:
        return (self.candidats_declares + self.membres_roster
                + self.provenance_autre + self.illisibles)

    def postes(self) -> list[tuple[int, str]]:
        """Les postes affichables, dans l'ordre : les deux populations
        toujours, les deux anomalies seulement si elles pèsent."""
        postes = [
            (self.candidats_declares, LIBELLE_CANDIDATS),
            (self.membres_roster, LIBELLE_ROSTER),
        ]
        if self.provenance_autre:
            postes.append((self.provenance_autre, LIBELLE_AUTRE))
        if self.illisibles:
            postes.append((self.illisibles, LIBELLE_ILLISIBLES))
        return postes

    def detail(self) -> str:
        """`(13 candidats déclarés · 468 membres de roster)`."""
        return "(" + SEPARATEUR.join(
            f"{effectif} {libelle}" for effectif, libelle in self.postes()
        ) + ")"

    def compte(self) -> str:
        """`481   (13 candidats déclarés · 468 membres de roster)` — la forme
        à coller derrière n'importe quel libellé de compteur console."""
        return f"{self.total}   {self.detail()}"

    def ligne(self, libelle: str) -> str:
        """`Profils publiés : 481   (13 candidats déclarés · …)`."""
        return f"{libelle} : {self.compte()}"

    def cellule_markdown(self) -> str:
        """`481 (13 candidats déclarés · 468 membres de roster)` — une cellule
        de tableau ne supporte pas les espaces d'alignement."""
        return f"{self.total} {self.detail()}"

    @classmethod
    def depuis_dict(cls, valeurs: Mapping[str, Any] | None) -> "Ventilation":
        """Reconstruit une ventilation sérialisée par `as_dict()` — un rapport
        JSON porte la ventilation, son rendu Markdown la relit."""
        if not isinstance(valeurs, Mapping):
            return cls()
        return cls(
            int(valeurs.get(CANDIDAT_DECLARE) or 0),
            int(valeurs.get(ROSTER_GROUPE) or 0),
            int(valeurs.get("provenance_autre") or 0),
            int(valeurs.get("illisibles") or 0),
        )

    def as_dict(self) -> dict[str, int]:
        return {
            "total": self.total,
            CANDIDAT_DECLARE: self.candidats_declares,
            ROSTER_GROUPE: self.membres_roster,
            "provenance_autre": self.provenance_autre,
            "illisibles": self.illisibles,
        }


def ventiler_provenances(provenances: Iterable[str], *, illisibles: int = 0) -> Ventilation:
    """Ventile des valeurs de `meta.provenance` déjà lues."""
    declares = roster = autres = 0
    for provenance in provenances:
        if provenance == ROSTER_GROUPE:
            roster += 1
        elif provenance == CANDIDAT_DECLARE:
            declares += 1
        else:
            autres += 1
    return Ventilation(declares, roster, autres, illisibles)


def ventiler(profils: Iterable[Mapping[str, Any]], *, illisibles: int = 0) -> Ventilation:
    """Ventile des profils pivot déjà chargés — le cas gratuit : une section
    qui lit déjà le corpus n'a rien à relire pour ventiler ses comptes."""
    return ventiler_provenances(
        (provenance_du_profil(profil) for profil in profils), illisibles=illisibles
    )


def lire_provenances(
    repertoire: Path, motif: str = "*" + SUFFIXE_PIVOT
) -> tuple[dict[str, str], list[str]]:
    """`({slug: provenance}, [slugs illisibles])`, en ne lisant que `meta`.

    `Path.glob` rend les dotfiles, contrairement au module `glob` :
    `.generation_checkpoint.json` a déjà été lu comme un profil et a coûté un
    commit (#518). Les fichiers cachés sont donc écartés ici aussi.

    Un fichier illisible n'est pas « 0 profil » : il est rendu à part, pour que
    l'appelant puisse le compter sans le confondre avec une provenance.
    """
    provenances: dict[str, str] = {}
    illisibles: list[str] = []
    if not repertoire.is_dir():
        return provenances, illisibles
    suffixe = motif.lstrip("*")
    for chemin in sorted(repertoire.glob(motif)):
        if chemin.name.startswith("."):
            continue
        slug = chemin.name[: -len(suffixe)] if suffixe else chemin.stem
        try:
            with chemin.open(encoding="utf-8") as flux:
                racine = json.load(flux, object_pairs_hook=_crochet_provenance)
        except (OSError, ValueError):
            illisibles.append(slug)
            continue
        provenances[slug] = provenance_du_profil(
            racine if isinstance(racine, dict) else None
        )
    return provenances, illisibles


def ventiler_chemins(chemins: Iterable[Path]) -> tuple[Ventilation, list[Path]]:
    """Ventile les seuls **pivots** d'une liste de chemins, et rend les autres.

    Un profil **brut** (`raw_data/profiles/<slug>.json`) ne porte pas
    `meta.provenance` — mesuré le 30/08/2026 : `meta` y tient
    `genere_le`, `licence_donnees`, `synchro_sources`, `warnings`,
    `collecte_ecartee`, et rien d'autre. Lui appliquer le repli
    rétro-compatible « absente vaut `candidat_declare` » inventerait 476
    candidats déclarés : la règle de #189 vaut pour un pivot d'avant #189, pas
    pour une couche qui n'a jamais porté le champ (AGENTS.md §2 règle 5).

    D'où le second membre du couple : les chemins **non ventilables**, que
    l'appelant doit nommer plutôt que fondre dans un poste.
    """
    pivots: list[Path] = []
    hors_pivot: list[Path] = []
    for chemin in chemins:
        (pivots if chemin.name.endswith(SUFFIXE_PIVOT) else hors_pivot).append(chemin)

    provenances: list[str] = []
    illisibles = 0
    for chemin in pivots:
        try:
            with chemin.open(encoding="utf-8") as flux:
                racine = json.load(flux, object_pairs_hook=_crochet_provenance)
        except (OSError, ValueError):
            illisibles += 1
            continue
        provenances.append(provenance_du_profil(racine if isinstance(racine, dict) else None))
    return ventiler_provenances(provenances, illisibles=illisibles), hors_pivot


def ventiler_repertoire(repertoire: Path, motif: str = "*" + SUFFIXE_PIVOT) -> Ventilation:
    """Ventile un répertoire de pivots, en ne lisant que `meta.provenance`.

    Un fichier illisible est compté sous son propre poste, et le total continue
    d'égaler le nombre de fichiers.
    """
    provenances, illisibles = lire_provenances(repertoire, motif)
    return ventiler_provenances(provenances.values(), illisibles=len(illisibles))
