#!/usr/bin/env python3
"""
gouvernement_textes.py — Collecte des dossiers législatifs d'origine
gouvernementale et extraction de leur statut, depuis le dump bulk
`Dossiers_Legislatifs.json.zip` de l'Assemblée nationale.

Suit le même principe que `syceron_debates.py`/`parse_syceron.py`
(téléchargement/cache réseau séparé du parsing pur, pour un parseur testable
sans réseau — voir docs/technical_decisions.md#syceron), mais dans un seul
fichier : `ensure_dossiers_zip_downloaded()` est la seule fonction de ce
module à toucher le réseau ou le disque ; le reste opère sur un
`zipfile.ZipFile` déjà ouvert (fixture locale possible pour les tests).

Réutilisation de l'infrastructure existante (issue #210) : `candidate_profile.py`
téléchargeait/cachait déjà `Dossiers_Legislatifs.json.zip` (deux fois, de
façon dupliquée, dans `_build_texte_titre_index` et
`_build_acteur_textes_portes_index`) sous les mêmes `AN_DOSSIERS_ZIP_URL`/
`DOSSIERS_CACHE_DIR`. Ce module en devient la source canonique :
`candidate_profile.py` importe désormais ces constantes et
`ensure_dossiers_zip_downloaded()` depuis ici plutôt que de dupliquer le
téléchargement — un seul cache, un seul verrou, pas de second téléchargement
du même fichier ~10 Mo.

Origine gouvernementale (art. 39 de la Constitution) — signal retenu :
préfixe de `titreDossier.titre` (« Projet de loi » = gouvernemental,
« Proposition de loi » = parlementaire). Spike #207 (docs/an_opendata.md,
section « Spike : origine ... ») : couvre 689/3044 dossiers sans jointure ni
faux positif, contre ~15 % de faux positifs pour la chaîne alternative
`initiateur.acteurs.acteur[] -> mandat GOUVERNEMENT -> organeRef` (dataset
`AMO30`, historique complet) sans filtrage par date de mandat vs date de
dépôt. Cette chaîne AMO30 n'est PAS implémentée ici (repli volontairement
laissé pour un futur complément) : seul le préfixe de titre est utilisé, donc
les 2355 dossiers sans préfixe standard (motions, résolutions, textes
transmis du Sénat sans préfixe, etc.) sont exclus du résultat plutôt que mal
classés.

Statut (nomenclature fermée `schema_gouvernement.KNOWN_STATUTS_TEXTE_GOUVERNEMENTAL`) :
porté par `statutConclusion.fam_code` d'un acte de décision de séance
(`codeActe` contenant `-DEBATS-` et se terminant par `-DEC` — voir
`_est_decision_de_seance` : AN1-DEBATS-DEC, SN1-DEBATS-DEC,
CMP-DEBATS-{AN,SN}-DEC, {AN,SN}NLEC-DEBATS-DEC constatés — un simple
`endswith("-DEBATS-DEC")` manquerait les codes de commission mixte
paritaire), PAS par `codeActe` seul (qui ne distingue pas les issues, voir
spike #207). Seule la décision de séance chronologiquement la plus récente
détermine le statut courant du dossier : un dossier peut accumuler
plusieurs décisions de séance au fil des lectures (ex. adopté en 1ère
lecture puis modifié par la seconde chambre — la navette continue, ce n'est
pas un statut final ; c'est le cas de `TSORTF05`, « modifié »). 7 `fam_code`
sont mappés : 4 confirmés par le spike #207, 3 ajoutés en #397 après
constat que leur absence excluait 45 dossiers sur 106 du jeu de données.
Tout autre `fam_code` rencontré sur la décision de séance la plus récente
produit un warning explicite et `statut = None` — jamais un statut par
défaut (règle AGENTS.md §2.5). Les décisions du Conseil
constitutionnel (`CC-CONCLUSION`) et les constats d'accord/désaccord de CMP
(`CMP-DEC`) portent aussi un `statutConclusion` mais ne sont pas des
décisions de séance sur le texte : ils sont volontairement exclus du calcul
du statut. `fam_code == "TSORTFnull"` est un artefact du dataset source signalant
l'absence de statut réel (constaté sur un acte de « décision » sans issue
tranchée) : traité comme absence d'événement, jamais comme un `fam_code`
inconnu à signaler.

Retrait : `codeActe` dédié (`AN1-RTRINI`/`ANLUNI-RTRINI`), sans
`statutConclusion` associé (spike #207).

`TSORTF24` (« rejeté via 49.3, motion de censure adoptée », ex. le budget
2025 sous le gouvernement Barnier) est mappé à `statut = "rejete_49_3"` avec
`sort_49_3 = True`, symétrique d'`adopte_49_3` — le 49.3 reste un fait
procédural distinct de l'issue du vote, jamais fusionné avec elle (règle
AGENTS.md §2.4). `rejete_49_3` a été ajouté à la nomenclature fermée de #208
après coup (docs/technical_decisions.md#gouvernement-textes-statut-49-3-rejete),
donc cette combinaison est représentable par
`schema_gouvernement.validate_profil_gouvernement` sans warning.

`TSORTF18` (« adopté, dans les conditions prévues à l'article 45, alinéa 3,
de la Constitution » : approbation du texte élaboré en commission mixte
paritaire, sur demande du Gouvernement) suit la même logique et est mappé à
un statut dédié `adopte_cmp`, avec `sort_49_3 = False`. L'issue est bien une
adoption, mais la voie procédurale est distincte et n'est pas fondue dans
`adopte` — arbitrage tranché en #397, symétrique de celui de #208 sur le
49.3. Un texte de CMP sur lequel le Gouvernement engagerait ensuite sa
responsabilité relève de `TSORTF06`/`TSORTF24`, pas de `TSORTF18` : seule la
décision de séance la plus récente compte, il n'y a donc pas de cumul
possible entre `adopte_cmp` et les statuts 49.3.

Rattachement à un gouvernement (hors périmètre de ce module, implémenté dans
`gouvernement_profile.py` — #211) : par date de dépôt initial (`date_depot`,
calculée ici), jamais par date de statut final — décision actée dans le plan
d'implémentation de #184 (issue #210) : un texte déposé sous un gouvernement A
puis conclu sous un gouvernement B reste crédité au gouvernement A, qui l'a
initié. Voir `docs/technical_decisions.md#gouvernement-profile-rattachement`.

Hors périmètre : couverture Sénat comme chambre de dépôt *primaire* d'un
dossier (le Sénat n'a pas de dataset équivalent exploitable — voir
docs/technical_decisions.md#hors-perimetre) ; seuls les dossiers du dump AN
sont vus ici, y compris ceux transmis en 2e lecture au Sénat (`chambre_depot_initial`
peut valoir `"Senat"` si un dossier AN a été déposé au Sénat en 1ère lecture).
"""

import json
import threading
import zipfile
from pathlib import Path
from typing import Any, Optional

import requests

from download_watchdog import download_with_watchdog
from schema_gouvernement import KNOWN_STATUTS_TEXTE_GOUVERNEMENTAL

AN_OPENDATA_BASE = "https://data.assemblee-nationale.fr/static/openData/repository"
AN_DOSSIERS_ZIP_URL = f"{AN_OPENDATA_BASE}/17/loi/dossiers_legislatifs/Dossiers_Legislatifs.json.zip"
DOSSIERS_CACHE_DIR = Path(".cache") / "dossiers_an"

HEADERS = {
    "User-Agent": "cv-politique-gouvernement-textes/0.1 (usage personnel / non commercial)"
}
TIMEOUT = (15, 600)

_ZIP_DOWNLOAD_LOCK = threading.Lock()

# Préfixes de titre signalant l'origine gouvernementale/parlementaire d'un
# dossier (art. 39 de la Constitution) — voir docstring du module. Couvre
# aussi "Projet de loi organique"/"Projet de loi constitutionnelle" (même
# préfixe). Comparaison insensible à la casse.
_TITRE_PREFIX_GOUVERNEMENTAL = "projet de loi"
_TITRE_PREFIX_PARLEMENTAIRE = "proposition de loi"

# fam_code -> (statut, sort_49_3). Toute autre valeur produit un warning et
# `statut = None` (voir docstring du module) : la nomenclature reste fermée.
#
# Le libellé cité en commentaire est celui porté par le dataset AN lui-même
# (`statutConclusion.libelle`), pas une interprétation de notre part — c'est
# la seule justification acceptable d'un mapping, et elle est vérifiable en
# relisant l'archive.
_FAM_CODE_STATUT_MAP: dict[str, tuple[str, bool]] = {
    # Confirmés par le spike #207 (docs/an_opendata.md).
    "TSORTF01": ("adopte", False),           # « adopté » / « adoptée »
    "TSORTF07": ("rejete", False),           # « rejeté » / « rejetée »
    "TSORTF06": ("adopte_49_3", True),       # « considéré comme adopté […] 49 al. 3 »
    "TSORTF24": ("rejete_49_3", True),       # « considéré comme rejeté […] 49 al. 3 »
    # Ajoutés en #397 : non mappés, ils excluaient 45 dossiers sur 106 du jeu
    # de données (42 %), dont le PLF 2025.
    "TSORTF03": ("adopte", False),           # « adopté sans modification »
    "TSORTF18": ("adopte_cmp", False),       # « adopté […] art. 45 al. 3 » (texte de CMP)
    "TSORTF05": ("navette_en_cours", False), # « modifié » — la navette continue
}

# Sentinelle du dataset source : absence de statut réel, pas un fam_code
# inconnu (voir docstring du module).
_FAM_CODE_SENTINEL_VIDE = "TSORTFnull"

# codeActe dédiés au retrait, sans statutConclusion associé (spike #207).
_CODE_ACTE_RETRAIT = frozenset({"AN1-RTRINI", "ANLUNI-RTRINI"})


def _est_decision_de_seance(code_acte: str) -> bool:
    """Décision de séance sur le texte lui-même (adoption/rejet/49.3), par
    opposition à un simple constat (`CMP-DEC`, accord/désaccord de la
    commission mixte paritaire) ou à une conclusion hors séance (`CC-CONCLUSION`,
    Conseil constitutionnel) — les deux portent aussi un `statutConclusion`
    mais ne tranchent pas le sort du texte. Constaté sur : `AN1-DEBATS-DEC`,
    `SN1-DEBATS-DEC`, `CMP-DEBATS-AN-DEC`, `CMP-DEBATS-SN-DEC`,
    `ANNLEC-DEBATS-DEC`, `SNNLEC-DEBATS-DEC` (spike #207) — d'où un motif
    `-DEBATS-` + suffixe `-DEC` plutôt qu'un simple `endswith("-DEBATS-DEC")`,
    qui manquerait les codes de commission mixte paritaire (`CMP-DEBATS-{AN,SN}-DEC`)."""
    return "-DEBATS-" in code_acte and code_acte.endswith("-DEC")


assert set(statut for statut, _ in _FAM_CODE_STATUT_MAP.values()) <= KNOWN_STATUTS_TEXTE_GOUVERNEMENTAL


def ensure_dossiers_zip_downloaded(*, force_download: bool = False) -> Optional[Path]:
    """Télécharge (si nécessaire) et met en cache `Dossiers_Legislatifs.json.zip`.

    Fonction réseau canonique pour ce dump : réutilisée par
    `candidate_profile.py` (index titre/acteur) et par la collecte des
    dossiers gouvernementaux de ce module, pour éviter un second
    téléchargement/cache indépendant du même fichier ~10 Mo (voir issue #210).
    Écriture atomique (fichier temporaire puis renommage) pour ne jamais
    laisser un cache partiellement écrit en cas d'échec réseau en cours de
    téléchargement.

    Returns:
        Chemin local de l'archive, ou None si le téléchargement échoue.
    """
    with _ZIP_DOWNLOAD_LOCK:
        zip_path = DOSSIERS_CACHE_DIR / "dossiers.zip"
        if not force_download and zip_path.is_file():
            return zip_path

        print(f"-> Téléchargement des dossiers législatifs (Assemblée nationale) : {AN_DOSSIERS_ZIP_URL}")
        try:
            zip_path.parent.mkdir(parents=True, exist_ok=True)
            # download_with_watchdog (#370) gère déjà l'écriture atomique
            # (fichier .part renommé seulement en cas de succès complet) et
            # ajoute un budget mur indépendant du timeout requests.
            download_with_watchdog(AN_DOSSIERS_ZIP_URL, zip_path, headers=HEADERS, timeout=TIMEOUT)
        except (requests.RequestException, OSError, TimeoutError) as exc:
            print(f"  [!] Échec du téléchargement des dossiers législatifs : {exc}")
            return None
        return zip_path


def _origine(titre: str) -> Optional[str]:
    """Classe un dossier en `"gouvernemental"`/`"parlementaire"`/`None` (non
    déterminable) à partir du préfixe de son titre. Voir docstring du module :
    seul signal utilisé ici (chaîne AMO30 non implémentée)."""
    titre_normalise = (titre or "").strip().lower()
    if titre_normalise.startswith(_TITRE_PREFIX_GOUVERNEMENTAL):
        return "gouvernemental"
    if titre_normalise.startswith(_TITRE_PREFIX_PARLEMENTAIRE):
        return "parlementaire"
    return None


def _iter_actes(node: Any):
    """Parcourt récursivement l'arbre `actesLegislatifs` d'un dossier et
    produit chaque acte (dict) rencontré, à n'importe quelle profondeur."""
    if isinstance(node, dict):
        yield node
        for key, value in node.items():
            if key != "statutConclusion":
                yield from _iter_actes(value)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_actes(item)


def _acte_dates(actes_legislatifs: Any) -> tuple[Optional[str], Optional[str]]:
    """Calcule `(date_depot, date_dernier_evenement)` : `date_depot` est la
    date minimale parmi les actes de premier dépôt (`codeActe` se terminant
    par `-DEPOT`) ; `date_dernier_evenement` est la date maximale parmi tous
    les actes du dossier, quel que soit leur type."""
    toutes_dates: list[str] = []
    dates_depot: list[str] = []
    for acte in _iter_actes(actes_legislatifs):
        date_acte = acte.get("dateActe")
        if not isinstance(date_acte, str) or not date_acte:
            continue
        date_courte = date_acte[:10]
        toutes_dates.append(date_courte)
        code_acte = acte.get("codeActe")
        if isinstance(code_acte, str) and code_acte.endswith("-DEPOT"):
            dates_depot.append(date_courte)
    date_depot = min(dates_depot) if dates_depot else (min(toutes_dates) if toutes_dates else None)
    date_dernier_evenement = max(toutes_dates) if toutes_dates else None
    return date_depot, date_dernier_evenement


def _chambre_depot_initial(actes_legislatifs: Any) -> Optional[str]:
    """Déduit la chambre de dépôt initial du dossier à partir du préfixe du
    `codeActe` du premier acte de dépôt chronologique (`AN...` -> `"AN"`,
    `SN...` -> `"Senat"`)."""
    meilleur: Optional[tuple[str, str]] = None  # (date, chambre)
    for acte in _iter_actes(actes_legislatifs):
        code_acte = acte.get("codeActe")
        date_acte = acte.get("dateActe")
        if not isinstance(code_acte, str) or not code_acte.endswith("-DEPOT"):
            continue
        if not isinstance(date_acte, str) or not date_acte:
            continue
        if code_acte.startswith("AN"):
            chambre = "AN"
        elif code_acte.startswith("SN"):
            chambre = "Senat"
        else:
            continue
        if meilleur is None or date_acte < meilleur[0]:
            meilleur = (date_acte, chambre)
    return meilleur[1] if meilleur else None


def _determine_statut(
    dossier_id: str, actes_legislatifs: Any
) -> tuple[Optional[str], Optional[bool], Optional[str]]:
    """Détermine `(statut, sort_49_3, warning)` du dossier à partir de la
    décision de séance (`_est_decision_de_seance`) ou de l'acte de retrait
    le plus récent. Voir docstring du module pour la justification du
    filtre et le traitement de la sentinelle `TSORTFnull`.

    Si aucun acte décisif n'est trouvé, le dossier est considéré `"depose"`
    (seul un dépôt existe) ou `"navette_en_cours"` (des actes existent
    au-delà du dépôt, sans décision de séance encore atteinte) — ce n'est
    pas un cas de warning : l'absence de conclusion est un état légitime,
    pas une donnée inconnue.
    """
    candidats: list[tuple[str, str, Optional[str]]] = []  # (date, kind, fam_code)
    a_acte_hors_depot = False
    for acte in _iter_actes(actes_legislatifs):
        code_acte = acte.get("codeActe")
        date_acte = acte.get("dateActe")
        if not isinstance(code_acte, str):
            continue
        if not code_acte.endswith("-DEPOT"):
            a_acte_hors_depot = True

        if code_acte in _CODE_ACTE_RETRAIT and isinstance(date_acte, str) and date_acte:
            candidats.append((date_acte, "retrait", None))
            continue

        if not _est_decision_de_seance(code_acte):
            continue
        statut_conclusion = acte.get("statutConclusion")
        if not isinstance(statut_conclusion, dict):
            continue
        fam_code = statut_conclusion.get("fam_code")
        if not fam_code or fam_code == _FAM_CODE_SENTINEL_VIDE:
            continue
        if not isinstance(date_acte, str) or not date_acte:
            continue
        candidats.append((date_acte, "statut", fam_code))

    if not candidats:
        statut = "navette_en_cours" if a_acte_hors_depot else "depose"
        return statut, None, None

    _date, kind, fam_code = max(candidats, key=lambda c: c[0])
    if kind == "retrait":
        return "retire", None, None

    mapping = _FAM_CODE_STATUT_MAP.get(fam_code)
    if mapping is None:
        warning = (
            f"gouvernement_textes: dossier {dossier_id} : fam_code inconnu "
            f"{fam_code!r} — statut non déterminé."
        )
        return None, None, warning

    statut, sort_49_3 = mapping
    return statut, sort_49_3, None


def _source_url(legislature: Optional[str], titre_chemin: Optional[str]) -> Optional[str]:
    if legislature and titre_chemin:
        return f"https://www.assemblee-nationale.fr/dyn/{legislature}/dossiers/{titre_chemin}"
    return None


def parse_dossier_gouvernemental(dossier: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Extrait un enregistrement de dossier gouvernemental à partir d'un
    `dossierParlementaire` brut (déjà désérialisé), ou `None` si son origine
    n'est pas gouvernementale (signal de préfixe de titre, voir docstring).

    Pure : aucun effet de bord, aucun accès réseau. `warnings` (liste, jamais
    absente) accompagne l'enregistrement pour tout `fam_code` non mappé ou
    toute combinaison non représentable en l'état par le schéma cible.
    """
    titre_dossier = dossier.get("titreDossier") or {}
    titre = titre_dossier.get("titre")
    if not titre or _origine(titre) != "gouvernemental":
        return None

    dossier_id = dossier.get("uid")
    actes_legislatifs = dossier.get("actesLegislatifs")
    date_depot, date_dernier_evenement = _acte_dates(actes_legislatifs)
    chambre_depot_initial = _chambre_depot_initial(actes_legislatifs)
    statut, sort_49_3, warning = _determine_statut(dossier_id, actes_legislatifs)
    legislature = dossier.get("legislature")

    return {
        "dossier_id": dossier_id,
        "titre": titre,
        "statut": statut,
        "sort_49_3": sort_49_3,
        "chambre_depot_initial": chambre_depot_initial,
        "date_depot": date_depot,
        "date_dernier_evenement": date_dernier_evenement,
        "legislature": legislature,
        "source_url": _source_url(legislature, titre_dossier.get("titreChemin")),
        "warnings": [warning] if warning else [],
    }


def collect_dossiers_gouvernementaux(zf: zipfile.ZipFile) -> dict[str, Any]:
    """Parcourt un `Dossiers_Legislatifs.json.zip` déjà ouvert et retourne
    `{"dossiers": [...], "warnings": [...]}` : un enregistrement par dossier
    d'origine gouvernementale identifiable, plus la liste consolidée des
    warnings (fam_code non mappés, combinaisons non représentables). Pure
    (aucun accès réseau) : c'est la fonction testée par une fixture ZIP
    locale.
    """
    dossiers: list[dict[str, Any]] = []
    warnings: list[str] = []
    noms = [
        n for n in zf.namelist()
        if n.startswith("json/dossierParlementaire/") and n.endswith(".json")
    ]
    for nom in noms:
        try:
            with zf.open(nom) as f:
                data = json.load(f)
        except (OSError, ValueError):
            continue
        dossier = data.get("dossierParlementaire") if isinstance(data, dict) else None
        if not isinstance(dossier, dict):
            continue
        record = parse_dossier_gouvernemental(dossier)
        if record is None:
            continue
        warnings.extend(record["warnings"])
        dossiers.append(record)

    dossiers.sort(key=lambda d: (d.get("date_depot") or "", d.get("titre") or ""), reverse=True)
    return {"dossiers": dossiers, "warnings": warnings}


def fetch_dossiers_gouvernementaux() -> dict[str, Any]:
    """Point d'entrée réseau : télécharge (si nécessaire) le dump, puis
    collecte les dossiers d'origine gouvernementale. Retourne
    `{"dossiers": [], "warnings": [...]}` si le téléchargement échoue
    (non-fatal, comme les autres index bulk de `candidate_profile.py`)."""
    zip_path = ensure_dossiers_zip_downloaded()
    if zip_path is None:
        return {
            "dossiers": [],
            "warnings": ["gouvernement_textes: téléchargement de Dossiers_Legislatifs.json.zip impossible."],
        }
    try:
        with zipfile.ZipFile(zip_path) as zf:
            return collect_dossiers_gouvernementaux(zf)
    except zipfile.BadZipFile as exc:
        return {
            "dossiers": [],
            "warnings": [f"gouvernement_textes: archive des dossiers législatifs invalide : {exc}"],
        }
