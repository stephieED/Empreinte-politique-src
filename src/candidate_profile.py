#!/usr/bin/env python3
"""
candidate_profile.py

Construit un profil JSON structuré ("CV politique") d'un parlementaire
à partir des données ouvertes de NosDéputés.fr / NosSénateurs.fr
(Regards Citoyens - licence ODbL / CC-BY-SA), complétées par les votes
officiels de l'Assemblée nationale (data.assemblee-nationale.fr).

Usage (depuis la racine du dépôt) :
    python src/candidate_profile.py jean-luc-melenchon --chambre deputes
    python src/candidate_profile.py bruno-retailleau --chambre senateurs
    python src/candidate_profile.py jean-luc-melenchon --chambre deputes --out raw_data/profiles/jean-luc-melenchon.json

Le script ne fait AUCUNE interprétation ni jugement de valeur : il se
contente d'agréger les faits bruts (mandats, responsabilités, votes,
interventions) tels que fournis par les API, avec des liens vers les sources.

Docs API : https://github.com/regardscitoyens/nosdeputes.fr/blob/master/doc/api.md
"""

import argparse
import concurrent.futures
import gzip
import io
import json
import os
import queue
import re
import shutil
import sys
import threading
import time
import unicodedata
import zipfile
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET

import requests
from bs4 import BeautifulSoup
from download_watchdog import download_with_watchdog
from gouvernement_textes import (
    DOSSIERS_CACHE_DIR,
    ensure_dossiers_zips_downloaded,
    iter_dossiers_bruts,
)
from json_io import ecrire_profil_json
from parse_syceron import parse_syceron_xml
from syceron_debates import SYCERON_AVAILABLE_LEGISLATURES, iter_syceron_xml_files, syceron_zip_url

BASE_URLS = {
    "deputes": [
        "https://www.nosdeputes.fr",
        "https://2017-2022.nosdeputes.fr",
        "https://2012-2017.nosdeputes.fr",
        "https://2007-2012.nosdeputes.fr",
    ],
    "senateurs": [
        # www.nossenateurs.fr a definitivement ferme (le site affiche desormais
        # un message "Le site NosSenateurs.fr est desormais arrete" et redirige
        # vers son archive) : on utilise directement l'archive, qui reste servie.
        "https://archive.nossenateurs.fr",
    ],
}

HEADERS = {
    "User-Agent": "candidate-profile-script/0.1 (usage personnel / non commercial)"
}

TIMEOUT = 15

# Donnees ouvertes officielles de l'Assemblee nationale (scrutins avec detail
# nominatif des votes par depute). Utilisees en remplacement de l'endpoint
# /votes de NosDeputes.fr, qui renvoie systematiquement une erreur HTTP 500
# (verifie y compris sur l'exemple de leur propre documentation, sur tous les
# domaines/legislatures disponibles).
AN_OPENDATA_BASE = "https://data.assemblee-nationale.fr/static/openData/repository"
AN_SCRUTINS_ZIP_NAME = {
    "17": "Scrutins.json.zip",
    "16": "Scrutins.json.zip",
    "15": "Scrutins_XV.json.zip",
    "14": "Scrutins_XIV.json.zip",
    # Pas de donnees ouvertes de scrutins disponibles pour la 13e legislature
    # (2007-2012) sur data.assemblee-nationale.fr.
}
# Legislatures interrogees pour les votes nominatifs, dans l'ordre decroissant
# (la plus recente d'abord). Remplace depuis #403 le mapping domaine
# NosDeputes.fr -> legislature qui servait ici : il figeait chaque profil sur
# UNE seule legislature, celle du domaine ou l'identite avait ete trouvee, donc
# en pratique toujours la 16e depuis l'etape 4 de #369 (identity_base_url vaut
# None pour tout depute resolu via l'AN, et le domaine principal de
# NosDeputes.fr y etait code en dur comme "16"). Un depute peut sieger sur
# plusieurs legislatures successives : ses votes sont desormais agreges sur
# toutes celles disponibles, comme les amendements (AN_AMENDEMENTS_PATH) et les
# dossiers legislatifs (#400).
AN_SCRUTINS_LEGISLATURES: tuple[str, ...] = ("17", "16", "15", "14")
SCRUTINS_CACHE_DIR = Path(".cache") / "scrutins_an"
# Legislatures dont les scrutins ne bougeront plus (dossier legislatif clos ;
# Last-Modified verifie le 18/08/2026 : 2018-03-21 pour la 14e, 2022-06-09 pour
# la 15e, 2024-06-28 pour la 16e). Leur index est construit une fois pour
# toutes hors CI (build_scrutins_index_figes.py) et committe gzippe dans
# AN_SCRUTINS_FIGES_DIR : la CI n'a donc plus a telecharger que la 17e
# (legislature en cours). Meme remede que pour les amendements
# (AN_AMENDEMENTS_LEGISLATURES_FIGEES), a une nuance pres : les archives de
# scrutins sont petites (0,7 a 26 Mo, toutes "Cacheable" par le CDN AN) et ne
# souffrent pas des IncompleteRead chroniques des archives d'amendements
# (283-618 Mo) — le gel evite ici un cout repete inutilement par chaque shard
# CI, pas un echec de telechargement. Voir
# docs/technical_decisions.md#votes-multi-legislature.
AN_SCRUTINS_LEGISLATURES_FIGEES: frozenset[str] = frozenset({"14", "15", "16"})
AN_SCRUTINS_FIGES_DIR = Path("raw_data") / "scrutins_an_figes"
# Forme dedupliquee du cache de votes (#403, remede repris de #377) : le meta
# de chaque scrutin (titre surtout) est stocke UNE fois dans `scrutins.json`
# (uid -> meta), et l'index par acteur ne porte que des references
# [uid, position]. Mesure sur les 4 legislatures : 68 Mo au total contre 741 Mo
# pour la forme plate ou le meta etait recopie pour chaque votant (x11), et
# 138 Mio de RSS au pic de construction (17e, la plus lourde) contre ~660 Mio.
SCRUTINS_CACHE_SCRUTINS_FILENAME = "scrutins.json"
# Une tranche par acteurRef (#403, remede repris de #392) : `fetch_votes_officiels`
# n'a besoin que de la tranche du candidat courant (~55 Ko) au lieu des 357 Mo
# d'index complets de la 17e legislature, relus a chaque candidat.
SCRUTINS_CACHE_INDEX_PAR_ACTEUR_DIRNAME = "index_par_acteur"
# Ancien fichier unique (forme plate, avant #403), conserve pour pouvoir le
# supprimer lors de la migration vers les tranches — il pesait a lui seul
# 132 a 357 Mo par legislature.
SCRUTINS_CACHE_INDEX_PAR_ACTEUR_FILENAME_LEGACY = "index_par_acteur.json"
# Fichiers committes pour une legislature figee (memes formats que le cache,
# gzippes : 0,13 / 1,14 / 1,48 Mo pour les legislatures 14 / 15 / 16).
SCRUTINS_FIGES_SCRUTINS_FILENAME = "scrutins.json.gz"
SCRUTINS_FIGES_INDEX_PAR_ACTEUR_FILENAME = "index_par_acteur.json.gz"
# Memo process du store `uid -> scrutin` par legislature. Volontairement limite
# au store dedupliqué (2,5 Mo au plus, pour la 17e) : memoiser les index par
# acteur complets rouvrirait l'OOM traite par #377/#392.
_SCRUTINS_STORE_MEMO: dict[str, Optional[dict[str, dict[str, Any]]]] = {}
# Page publique d'un scrutin sur assemblee-nationale.fr, par legislature et
# numero : source primaire de chaque vote (regle 2, tracabilite). Verifiee le
# 18/08/2026 sur les legislatures 14, 15 et 17.
AN_SCRUTIN_PAGE_URL = "https://www.assemblee-nationale.fr/dyn/{legislature}/scrutins/{numero}"
# Prefixe d'uid des scrutins de l'Assemblee nationale proprement dits. Les
# archives de scrutins AN contiennent aussi, marginalement, des scrutins du
# CONGRES (prefixe VTCGR) : une seule occurrence sur les quatre legislatures,
# le vote de constitutionnalisation de l'IVG du 04/03/2024 (VTCGR5L16V1).
# Ils sont ecartes, faute de pouvoir les publier correctement : le Congres est
# une assemblee distincte (Assemblee + Senat reunis a Versailles, d'ou les 24
# senateurs qui apparaissent dans sa ventilation nominative), et sa numerotation
# repart de 1 en partageant l'espace de numeros de l'AN — VTCGR5L16V1 porte le
# numero 1, deja pris par la motion de censure du 11/07/2022. Le publier
# donnerait donc une source primaire fausse (verifie le 18/08/2026 :
# /dyn/16/scrutins/1 renvoie bien la motion de censure) et le confondrait avec
# elle dans la cohesion de groupe, qui indexe par numero a legislature donnee.
# Voir docs/technical_decisions.md#votes-multi-legislature et ROADMAP.
AN_SCRUTIN_UID_PREFIXE = "VTANR"

# Donnees ouvertes officielles des amendements (Assemblee nationale). Le nom du
# sous-repertoire et du zip differe selon la legislature : "amendements_div_legis"
# / "Amendements.json.zip" pour les legislatures 16/17, "amendements_legis" /
# "Amendements_XV.json.zip" pour la 15e, "amendements_legis_XIV" /
# "Amendements_XIV.json.zip" pour la 14e. Cette similitude de nommage entre
# 14e et 15e (suffixe numero romain) ne reflete PAS le contenu : verifie le
# 15/08/2026 (#301) via lecture partielle en HTTP Range de l'archive 15e
# (en-tetes locaux ZIP a l'offset 0 et vers 5 Mo) que son zip contient, comme
# les 16e/17e, un fichier JSON par amendement de racine `{"amendement": {...}}`
# (`_parse_amendement_entry`) — pas le schema legacy "fichier unique" /
# `{"textesEtAmendements": {...}}` de la 14e (#299, `_parse_amendement_entry_legacy`).
# Verifie manuellement (HTTP 200) pour chaque entree ci-dessous. La 14e a ete
# trouvee le 15/08/2026 via la page d'archives dediee
# (data.assemblee-nationale.fr/archives-anterieures/archives-14e/amendements),
# pas via le repertoire openData standard qui ne la liste pas directement ;
# aucun equivalent trouve pour la 13e (aucune page d'archives ni chemin
# openData ne repond, contrairement a la 14e/15e qui en ont une).
AN_AMENDEMENTS_PATH: dict[str, tuple[str, str]] = {
    "17": ("amendements_div_legis", "Amendements.json.zip"),
    "16": ("amendements_div_legis", "Amendements.json.zip"),
    "15": ("amendements_legis", "Amendements_XV.json.zip"),
    "14": ("amendements_legis_XIV", "Amendements_XIV.json.zip"),
}
AMENDEMENTS_CACHE_DIR = Path(".cache") / "amendements_an"
# Legislatures dont le dossier legislatif est definitivement clos : l'archive
# amendements AN correspondante (Last-Modified verifie le 13/08/2026 :
# 2022-06-09 pour la 15e, 2024-06-28 pour la 16e ; 2018-03-21 pour la 14e,
# verifie le 15/08/2026) ne sera plus jamais modifiee par l'Assemblee
# nationale. Le telechargement en CI de ces archives (350-650 Mo pour la
# 15e/16e) echoue de facon recurrente dans le budget reseau/temps disponible
# (IncompleteRead/HTTP2 PROTOCOL_ERROR repetes, meme en dehors de la CI - voir
# docs/technical_decisions.md#amendements-legislatures-figees) : leur index
# est construit une fois pour toutes hors CI (build_amendements_index_figees.py)
# et committe dans AN_AMENDEMENTS_FIGEES_DIR, lu par _load_frozen_amendement_index
# au lieu d'un nouveau telechargement reseau. La 14e (~99 Mo, marquee
# "Cacheable" par le CDN contrairement a la 15e/16e/17e) est nettement moins
# a risque de reseau mais reste figee au meme titre : son dossier legislatif
# est clos, donc jamais reconstruite. La 17e reste active (legislature en
# cours) et continue d'etre reconstruite par le job CI dedie
# extract-amendements-an.
AN_AMENDEMENTS_LEGISLATURES_FIGEES: frozenset[str] = frozenset({"14", "15", "16"})
AN_AMENDEMENTS_FIGEES_DIR = Path("raw_data") / "amendements_an_figes"
# Nom du fichier d'indicateur de fraîcheur écrit à côté de `index_par_acteur.json`
# (issue #253, sous-issue 5/6 de #248) : permet à un futur consommateur (quality
# gate, sous-issue 6) de distinguer un index frais d'un index conservé faute de
# mieux après un échec définitif de reconstruction — voir
# `_write_amendements_fraicheur`.
AMENDEMENTS_FRAICHEUR_FILENAME = "fraicheur.json"
# Noms des fichiers committés pour une législature figée (compressés gzip :
# mesuré le 15/08/2026 sur la législature 16, `index_par_acteur.json` allégé
# pèse malgré tout 177 Mo en clair — au-delà de la limite GitHub de 100 Mo par
# blob — contre 10,4 Mo une fois gzippé, la structure très répétitive
# {numero, role_signataire} compressant très bien). `amendements.json`
# regroupe les enregistrements dédupliqués (voir `_aggregate_amendements_index`
# et docs/technical_decisions.md#amendements-legislatures-figees) ; le
# contenu JSON est identique, seule la compression change.
AMENDEMENTS_FIGEES_AMENDEMENTS_FILENAME = "amendements.json.gz"
AMENDEMENTS_FIGEES_INDEX_PAR_ACTEUR_FILENAME = "index_par_acteur.json.gz"
# Noms des fichiers du cache disque (`AMENDEMENTS_CACHE_DIR/<legislature>/`),
# depuis #377 : le cache stocke la MEME forme dedupliquee que le fallback
# committe ci-dessus (simplement non compressee), au lieu de la forme plate
# ou chaque amendement etait recopie integralement pour chacun de ses
# signataires. Mesure sur la legislature 16 : 210 Mo (34 + 176) contre
# 4,67 Go pour la forme plate, soit ~21x — la forme plate approchait a elle
# seule la RAM totale d'un runner GitHub Actions standard (~7 Gio) comme
# d'une machine de developpement modeste, et a declenche l'OOM killer en
# pratique (voir docs/technical_decisions.md#oom-lecture-amendements-par-candidat).
# Un cache ecrit avant #377 ne contient que `index_par_acteur.json` sous
# forme plate, sans `amendements.json` : les deux fichiers sont donc exiges
# ensemble pour qu'un cache soit considere valide (voir
# `_read_cached_amendements_agreges`), ce qui rend l'ancien format
# indiscernable d'un cache absent et force sa reconstruction — jamais sa
# relecture en memoire.
AMENDEMENTS_CACHE_AMENDEMENTS_FILENAME = "amendements.json"
# Depuis #392, l'index par acteur du CACHE RUNTIME est un RÉPERTOIRE d'une
# tranche par acteurRef (`index_par_acteur/PA1567.json`) et non plus un fichier
# unique : `fetch_amendements_officiels` n'a besoin que de la tranche du
# candidat courant, et relire les 673 Mo d'index complets à chaque candidat
# représentait 93 % du coût d'extraction du roster (mesuré en #376).
# Le format COMMITTÉ des législatures figées (AN_AMENDEMENTS_FIGEES_DIR,
# gzippé, fichier unique) est inchangé — il n'est lu qu'une fois, à la
# matérialisation du cache.
AMENDEMENTS_CACHE_INDEX_PAR_ACTEUR_DIRNAME = "index_par_acteur"
# Nom du fichier unique hérité de #377, conservé pour pouvoir le supprimer
# lors de la migration vers les tranches.
AMENDEMENTS_CACHE_INDEX_PAR_ACTEUR_FILENAME_LEGACY = "index_par_acteur.json"

# Mémo process du store `numero -> amendement` par législature (#392).
# Volontairement limité au store dédupliqué (426 Mo résidents pour les 4
# législatures, mesuré) : mémoïser les index par acteur complets coûterait
# 3,84 Go et rouvrirait l'OOM traité par #377.
_AMENDEMENTS_STORE_MEMO: dict[str, Optional[dict[str, dict[str, Any]]]] = {}
# Le fichier Amendements.json.zip pese 283-618 Mo selon la legislature : un
# alea reseau transitoire sur un telechargement de cette taille (deja observe
# en pratique : IncompleteRead en cours de stream) ne doit pas declencher un
# warning permanent si une tentative suivante aboutit. Borne volontairement
# basse (budget CI) : 3 tentatives, backoff court et fixe (pas d'exponentiel,
# le fichier est deja volumineux a re-telecharger).
AMENDEMENTS_DOWNLOAD_MAX_ATTEMPTS = 3
AMENDEMENTS_DOWNLOAD_BACKOFF_SECONDS = 5
# Timeout de lecture (par tentative). Les deux plus grosses archives
# (legislatures 15/16, 363-618 Mo) ne sont pas cacheables par le CDN AN
# (verifie : "x-cacheable: Not cacheable: too big") et frappent donc toujours
# l'origine — un blocage en cours de stream (deja observe : IncompleteRead) y
# est plus probable que sur un petit fichier. 600s etait beaucoup trop large :
# un pire cas de 3 tentatives x 600s (30 min) par legislature, repete pour
# chaque candidat ayant besoin de cette meme legislature (aucun cache
# d'echec avant #239), a suffi a declencher des "runner shutdown signal" en
# CI. Borne desormais a une valeur coherente avec le budget CI du job (cf.
# PARLTRACK_TIMEOUT_MINUTES=30 dans generate-data.yml comme reference) : un
# blocage de plus de 2 min sur un flux CI sain est deja le signe qu'il faut
# abandonner la tentative plutot que d'attendre.
AMENDEMENTS_DOWNLOAD_READ_TIMEOUT_SECONDS = 120

# Taille de segment pour le telechargement par plages (requetes HTTP Range) des
# archives d'amendements (issue #241). Le CDN devant data.assemblee-nationale.fr
# supporte fonctionnellement les requetes par plage (verifie : reponse 206 +
# Content-Range, le 13/08/2026) ; decouper le flux permet de ne retenter que le
# segment en echec (AMENDEMENTS_DOWNLOAD_MAX_ATTEMPTS/BACKOFF_SECONDS
# s'appliquent desormais par segment) au lieu de tout le fichier sur un
# IncompleteRead survenant a un point variable du flux. Valeur choisie comme
# compromis : assez grande pour ne pas multiplier le nombre de requetes sur un
# flux par ailleurs sain (~10-20 segments pour les plus grosses archives,
# 283-618 Mo), assez petite pour qu'un retry de segment reste marginal.
AMENDEMENTS_DOWNLOAD_CHUNK_BYTES = 32 * 1024 * 1024

# Nombre de segments ayant necessite au moins un retry au-dela duquel un
# warning "doux" est journalise (jamais ajoute a meta.warnings : ceci est un
# signal de qualite de flux, pas un echec de collecte) — permet de distinguer
# en CI un alea reseau ponctuel absorbe d'une degradation plus large.
AMENDEMENTS_SEGMENT_RETRY_WARNING_THRESHOLD = 3

# Legislatures dont le telechargement de l'archive amendements a echoue de
# facon definitive (toutes les tentatives de _download_and_build_amendement_index
# epuisees) pour le run (process) courant. Verifie en tete de cette fonction
# avant toute tentative reseau : sans ce cache, chaque candidat suivant ayant
# besoin de la meme legislature repayait l'integralite du cycle de retry
# (issue #239). Raccourci intra-process uniquement : deux jobs CI du meme run
# (ex. extract-an puis extract-roster-groupes, sequences par #222) sont deux
# process Python distincts, donc deux instances vides de ce set — voir
# _amendements_failed_marker_path ci-dessous pour la source de verite
# inter-jobs (issue #246).
_amendements_failed_legislatures: set[str] = set()


def _amendements_failed_marker_path(legislature: str) -> Path:
    """Chemin du marqueur disque d'echec definitif pour une legislature, sur le
    cache disque partage `.cache/amendements_an/` (restaure/sauvegarde par
    chaque job CI grace au sequencement de #222 sur la meme cle de cache,
    voir [[concurrence-ci-roster]]). Contrairement a l'index lui-meme, ce
    marqueur ne contient aucune donnee : juste le `GITHUB_RUN_ID` du run
    l'ayant ecrit, pour distinguer un echec du run courant (a respecter) d'un
    residu d'une semaine ISO precedente via `restore-keys` (a ignorer, issue
    #246)."""
    return AMENDEMENTS_CACHE_DIR / legislature / "failed_run_id"


def _mark_amendements_legislature_failed(legislature: str) -> None:
    """Memorise l'echec definitif d'une legislature : en memoire process
    (raccourci intra-process, #239) et sur le marqueur disque partage entre
    jobs CI du meme run (#246). `GITHUB_RUN_ID` est absent hors CI (ex. tests,
    usage local) : dans ce cas, seul le cache memoire est utilise, comme avant
    #246."""
    _amendements_failed_legislatures.add(legislature)
    run_id = os.environ.get("GITHUB_RUN_ID")
    if not run_id:
        return
    marker_path = _amendements_failed_marker_path(legislature)
    try:
        marker_path.parent.mkdir(parents=True, exist_ok=True)
        marker_path.write_text(run_id, encoding="utf-8")
    except OSError:
        pass  # marqueur best-effort : une legislature non marquee est simplement retentee


def _amendements_legislature_failed_this_run(legislature: str) -> bool:
    """Determine si une legislature a deja echoue definitivement durant le run
    courant, en consultant d'abord le cache memoire intra-process (#239) puis,
    a defaut, le marqueur disque inter-jobs (#246). Un marqueur disque
    referencant un `GITHUB_RUN_ID` different du run courant est ignore (residu
    perime) : comportement de #239 volontairement preserve pour les runs
    suivants, sans TTL explicite a maintenir."""
    if legislature in _amendements_failed_legislatures:
        return True
    run_id = os.environ.get("GITHUB_RUN_ID")
    if not run_id:
        return False
    try:
        marker_run_id = _amendements_failed_marker_path(legislature).read_text(encoding="utf-8").strip()
    except OSError:
        return False
    if marker_run_id != run_id:
        return False
    _amendements_failed_legislatures.add(legislature)  # raccourci pour les prochains appels intra-process
    return True

# Dossiers legislatifs (Assemblee nationale) : plusieurs archives bulk, une par
# legislature (15/16/17 — voir AN_DOSSIERS_ARCHIVES), chacune deja
# multi-legislatures mais ne gardant des precedentes qu'une traine residuelle,
# d'ou l'ingestion des trois (#400). Utilise ici pour resoudre le code source
# d'un texte (texteLegislatifRef d'un amendement, ex. "PIONANR5L17B0904") vers
# son titre lisible, et pour construire l'index acteur -> textes portes.
# DOSSIERS_CACHE_DIR/ensure_dossiers_zips_downloaded/iter_dossiers_bruts sont
# importés depuis gouvernement_textes.py, qui en est la source canonique
# (téléchargement/cache partagé avec la collecte des dossiers gouvernementaux,
# voir issue #210 : un seul cache pour ces archives).
# iter_dossiers_bruts deduplique par uid entre archives : sans cela un dossier
# present dans deux archives serait compte deux fois.

# Acteurs/mandats/organes historique complet (Assemblee nationale) : un seul
# fichier bulk, couvrant TOUTES les legislatures depuis la XIe (3117 acteurs
# constates, contre 577 deputes ACTIFS de la seule legislature en cours pour
# l'ancien jeu de donnees AMO10 "deputes_actifs_mandats_actifs_organes", plus
# utilise depuis l'issue #354 - voir docs/technical_decisions.md pour le choix
# AMO30 plutot que combiner AMO20 par legislature comme envisage initialement).
# Utilise pour :
# - enrichir schema_pivot.identite (nom complet/profession/date+lieu de
#   naissance/uri_hatvp/contact/circonscription/place hemicycle) au-dela de ce
#   que fournit nosdeputes.fr, y compris pour les elus dont le mandat est
#   termine (_build_acteur_identite_index, issue #354) ;
# - reconstituer l'historique date d'appartenance a un groupe politique
#   (acteur.mandats.mandat[].typeOrgane == "GP") et sa qualification officielle
#   organe.positionPolitique ("Majoritaire"/"Minoritaire"/"Opposition"/null).
#   Constat empirique : positionPolitique n'est renseigne par l'AN qu'une fois
#   la legislature terminee (toujours null sur la 17e, en cours, y compris
#   pour les groupes du socle commun) - cette qualification ne couvre donc que
#   les legislatures achevees (jusqu'a la 16e comprise) ;
# - resoudre mandats[].organes.organeRef vers un nom lisible (_build_organe_index,
#   issue #353), a partir des 7126+ organes historiques du meme zip
#   (json/organe/*.json, tous codeType confondus : commissions, groupes
#   d'amitie, engagements extra-parlementaires...).
AN_ACTEURS_HISTORIQUE_ZIP_URL = (
    f"{AN_OPENDATA_BASE}/17/amo/tous_acteurs_mandats_organes_xi_legislature/"
    "AMO30_tous_acteurs_tous_mandats_tous_organes_historique.json.zip"
)
ACTEURS_HISTORIQUE_CACHE_DIR = Path(".cache") / "acteurs_historique_an"

# Questions parlementaires (écrites, au gouvernement, orales sans débat).
# Même pattern d'URL que scrutins/amendements. Un seul parseur générique suffit
# pour les 3 types (seul @xsi:type diffère). URLs confirmées pour les 16e et 17e
# législatures ; les noms pour 14/15 suivent la convention _XIV/_XV des autres jeux
# (inférés — échoueront silencieusement si le fichier n'existe pas côté AN).
AN_QUESTIONS_PATH: dict[str, dict[str, tuple[str, str]]] = {
    "17": {
        "QE":   ("questions_ecrites",           "Questions_ecrites.json.zip"),
        "QG":   ("questions_gouvernement",      "Questions_gouvernement.json.zip"),
        "QOSD": ("questions_orales_sans_debat", "Questions_orales_sans_debat.json.zip"),
    },
    "16": {
        "QE":   ("questions_ecrites",           "Questions_ecrites.json.zip"),
        "QG":   ("questions_gouvernement",      "Questions_gouvernement.json.zip"),
        "QOSD": ("questions_orales_sans_debat", "Questions_orales_sans_debat.json.zip"),
    },
    "15": {
        "QE":   ("questions_ecrites",           "Questions_ecrites_XV.json.zip"),
        "QG":   ("questions_gouvernement",      "Questions_gouvernement_XV.json.zip"),
        "QOSD": ("questions_orales_sans_debat", "Questions_orales_sans_debat_XV.json.zip"),
    },
    "14": {
        "QE":   ("questions_ecrites",           "Questions_ecrites_XIV.json.zip"),
        "QG":   ("questions_gouvernement",      "Questions_gouvernement_XIV.json.zip"),
        "QOSD": ("questions_orales_sans_debat", "Questions_orales_sans_debat_XIV.json.zip"),
    },
}
QUESTIONS_CACHE_DIR = Path(".cache") / "questions_an"

# Verrous par législature pour `_build_acteur_vote_index` : plusieurs threads peuvent
# appeler cette fonction simultanément pour des législatures différentes (pas de blocage
# entre eux), mais on sérialise les accès pour une même législature afin d'éviter un
# double téléchargement de l'archive zip et une écriture concurrente du cache disque.
_SCRUTINS_LOCKS: dict[str, threading.Lock] = {}
_SCRUTINS_LOCKS_META = threading.Lock()

# Même principe que _SCRUTINS_LOCKS, pour l'index des amendements officiels.
_AMENDEMENTS_LOCKS: dict[str, threading.Lock] = {}
_AMENDEMENTS_LOCKS_META = threading.Lock()

# Même principe que _SCRUTINS_LOCKS, pour l'index des questions officielles.
_QUESTIONS_LOCKS: dict[str, threading.Lock] = {}
_QUESTIONS_LOCKS_META = threading.Lock()

# Même principe que _SCRUTINS_LOCKS, pour l'index des débats Syceron.
_SYCERON_LOCKS: dict[str, threading.Lock] = {}
_SYCERON_LOCKS_META = threading.Lock()

# Un seul verrou pour l'index titre des dossiers legislatifs (un seul fichier,
# pas de decoupage par legislature).
_DOSSIERS_TITRE_LOCK = threading.Lock()

# Un seul verrou pour l'index identite des acteurs (un seul fichier, pas de
# decoupage par legislature), construit depuis le meme fichier bulk historique
# que _ACTEURS_HEMICYCLE_LOCK/_ACTEURS_ORGANES_LOCK (issue #354).
_ACTEURS_IDENTITE_LOCK = threading.Lock()

# Un seul verrou pour l'index des positions dans l'hemicycle (construit depuis
# le fichier bulk historique des acteurs/mandats/organes).
_ACTEURS_HEMICYCLE_LOCK = threading.Lock()

# Verrou dedie au telechargement/cache disque de l'archive bulk historique
# elle-meme (AN_ACTEURS_HISTORIQUE_ZIP_URL) : plusieurs index se construisent
# a partir du meme zip (_build_acteur_identite_index, _build_acteur_positions_hemicycle_index,
# _build_organe_index) sans se marcher dessus ni le retelecharger chacun de
# leur cote (voir _ensure_acteurs_historique_zip_downloaded).
_ACTEURS_HISTORIQUE_ZIP_LOCK = threading.Lock()

# Un seul verrou pour l'index des organes (organeRef -> sigle/nom/type),
# construit depuis le meme fichier bulk historique (issue #353).
_ACTEURS_ORGANES_LOCK = threading.Lock()

# Un seul verrou pour l'index des mandats (commissions/groupes d'amitie/
# engagements extra-parlementaires), construit depuis le meme fichier bulk
# historique (issue #369 - complete #353 pour peupler profile["mandats"]).
_ACTEURS_MANDATS_LOCK = threading.Lock()

# Un seul verrou pour l'index des textes portés (auteur/rapporteur), construit
# depuis le même fichier bulk que l'index titre (dossiers legislatifs).
_DOSSIERS_TEXTES_PORTES_LOCK = threading.Lock()

# Nomenclature officielle des types de rapport (typeRapporteur, dossiers
# legislatifs Assemblee nationale) -> nomenclature du schema pivot.
TYPE_RAPPORTEUR_MAP = {
    "rapporteur": "rapporteur_fond",
    "rapporteur pour avis": "rapporteur_avis",
    "rapporteur spécial": "rapporteur_special_budget",
    "rapporteur général": "rapporteur_general",
}

# Préfixes des messages d'avertissement (warnings) ajoutés à profile["meta"]["warnings"].
# Exposés en constantes (plutôt qu'en texte libre dupliqué) pour que merge_profile.py
# puisse détecter de façon fiable les warnings devenus obsolètes après fusion
# (cf. _prune_stale_warnings), sans risquer de désynchronisation si le libellé
# complet du message venait à changer ici.
WARNING_PREFIX_IDENTITE_INTROUVABLE = "identité introuvable"
WARNING_PREFIX_MANDATS_INTROUVABLES = "mandats introuvables"
WARNING_PREFIX_VOTES_INTROUVABLES = "votes introuvables"
WARNING_PREFIX_AMENDEMENTS_INDISPONIBLES = "amendements indisponibles"
WARNING_PREFIX_QUESTIONS_INDISPONIBLES = "questions indisponibles"
WARNING_PREFIX_INTERVENTIONS_FALLBACK_NOSDEPUTES = "interventions syceron indisponibles (fallback nosdeputes)"


def _get_scrutins_lock(legislature: str) -> threading.Lock:
    """Retourne (ou crée) le verrou associé à une législature donnée."""
    with _SCRUTINS_LOCKS_META:
        if legislature not in _SCRUTINS_LOCKS:
            _SCRUTINS_LOCKS[legislature] = threading.Lock()
        return _SCRUTINS_LOCKS[legislature]


def _get_amendements_lock(legislature: str) -> threading.Lock:
    """Retourne (ou crée) le verrou associé à une législature donnée (amendements)."""
    with _AMENDEMENTS_LOCKS_META:
        if legislature not in _AMENDEMENTS_LOCKS:
            _AMENDEMENTS_LOCKS[legislature] = threading.Lock()
        return _AMENDEMENTS_LOCKS[legislature]


def _get_questions_lock(legislature: str) -> threading.Lock:
    """Retourne (ou crée) le verrou associé à une législature donnée (questions)."""
    with _QUESTIONS_LOCKS_META:
        if legislature not in _QUESTIONS_LOCKS:
            _QUESTIONS_LOCKS[legislature] = threading.Lock()
        return _QUESTIONS_LOCKS[legislature]


def _get_syceron_lock(legislature: str) -> threading.Lock:
    """Retourne (ou crée) le verrou associé à une législature donnée (débats Syceron)."""
    with _SYCERON_LOCKS_META:
        if legislature not in _SYCERON_LOCKS:
            _SYCERON_LOCKS[legislature] = threading.Lock()
        return _SYCERON_LOCKS[legislature]


def _is_empty_payload(value: Any) -> bool:
    """Vérifie si une valeur de réponse API est vide ou absente."""
    if value is None:
        return True
    if isinstance(value, (dict, list, tuple, set)):
        return len(value) == 0
    if isinstance(value, str):
        return value.strip() == ""
    return False


def _extract_parlementaire(identity_raw: Any) -> Optional[dict]:
    """Extrait le dict "parlementaire" d'une réponse d'identité NosDéputés/NosSénateurs.

    La clé racine varie selon l'endpoint ("depute" ou "senateur") ; à défaut,
    on retombe sur le payload lui-même (déjà à plat sur certains endpoints).
    """
    if not isinstance(identity_raw, dict):
        return None
    if identity_raw.get("depute") is not None:
        return identity_raw.get("depute")
    if identity_raw.get("senateur") is not None:
        return identity_raw.get("senateur")
    return identity_raw


def _xml_to_data(xml_text: str) -> Optional[Any]:
    """Convertit un XML simple en structure Python de base."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None

    def convert(elem: ET.Element) -> Any:
        children = list(elem)
        if not children:
            return elem.text.strip() if elem.text and elem.text.strip() else None
        result: dict[str, Any] = {}
        for child in children:
            converted = convert(child)
            if child.tag in result:
                if not isinstance(result[child.tag], list):
                    result[child.tag] = [result[child.tag]]
                result[child.tag].append(converted)
            else:
                result[child.tag] = converted
        return result

    return {root.tag: convert(root)}


# Sentinel renvoyé par _get_payload pour signaler un échec déterministe (4xx,
# format non pris en charge) qui ne doit pas déclencher de nouvel essai sur
# d'autres formats ou d'autres bases pour la même ressource.
_TERMINAL_FAILURE = object()

# Marge appliquée au-delà de TIMEOUT dans _get_with_watchdog avant d'abandonner
# une requête bloquée : `timeout=` de `requests` ne couvre pas la résolution
# DNS (getaddrinfo) sur toutes les plateformes, ce qui a déjà fait pendre le
# process bien au-delà de TIMEOUT sans lever la moindre exception Python — le
# runner GitHub Actions finissait tué par l'infra ("shutdown signal" opaque en
# CI, aucune trace applicative) plutôt que le job échouant proprement.
_WATCHDOG_MARGIN_SECONDS = 10


def _get_with_watchdog(url: str, *, timeout: int) -> requests.Response:
    """`requests.get` protégé par un budget mur total, y compris pour les
    blocages hors du contrôle du paramètre `timeout=` de `requests` (résolution
    DNS notamment).

    Exécute la requête dans un thread démon et abandonne après
    ``timeout + _WATCHDOG_MARGIN_SECONDS``. Le thread sous-jacent peut rester
    bloqué indéfiniment (impossible à interrompre depuis Python) : il est
    volontairement laissé en arrière-plan plutôt que joint, mais étant démon,
    il ne bloque jamais la sortie du process principal.
    """
    outcome: "queue.Queue[tuple[bool, Any]]" = queue.Queue(maxsize=1)

    def _worker() -> None:
        try:
            outcome.put((True, requests.get(url, headers=HEADERS, timeout=timeout)))
        except Exception as exc:  # relayé tel quel au thread appelant
            outcome.put((False, exc))

    threading.Thread(target=_worker, daemon=True).start()
    try:
        ok, payload = outcome.get(timeout=timeout + _WATCHDOG_MARGIN_SECONDS)
    except queue.Empty:
        raise requests.exceptions.Timeout(
            f"Aucune réponse de {url} après {timeout + _WATCHDOG_MARGIN_SECONDS}s "
            "(budget mur du watchdog dépassé — probable blocage DNS/réseau non "
            "couvert par timeout= de requests)"
        ) from None
    if ok:
        return payload
    raise payload


# Retry léger sur échec transitoire (5xx, erreur réseau, timeout watchdog).
# _get_payload est le chokepoint partagé par identité/votes/synthèse/dossiers-
# Sénat (voir docs/technical_decisions.md#dossiers-legislatifs-nosdeputes-vs-an-officiel
# et issue #340) : un retry ici bénéficie à tous ces appelants sans dupliquer
# la logique par fonction. N'aide pas contre un vrai gel du runner CI (déjà
# constaté : même le thread du watchdog n'arrive alors pas à s'exécuter), mais
# couvre les hoquets réseau/serveur transitoires réels, plus fréquents.
_GET_PAYLOAD_MAX_ATTEMPTS = 3
_GET_PAYLOAD_RETRY_BACKOFF_SECONDS = 1.5


def _get_payload(url: str) -> Any:
    """GET une URL et renvoie un objet Python (JSON ou XML simple), ou None / _TERMINAL_FAILURE.

    Retourne :
    - Un objet Python exploitable en cas de succès.
    - ``_TERMINAL_FAILURE`` pour les échecs déterministes (4xx, format non pris
      en charge) : aucun essai ultérieur sur d'autres formats ou miroirs ne
      serait utile pour cette ressource — jamais retenté ici non plus.
    - ``None`` pour les échecs transitoires (erreur réseau, timeout, 5xx),
      après épuisement de ``_GET_PAYLOAD_MAX_ATTEMPTS`` tentatives (backoff
      fixe ``_GET_PAYLOAD_RETRY_BACKOFF_SECONDS`` entre chaque) : un nouvel
      essai sur un autre miroir reste légitime côté appelant.
    """
    for attempt in range(1, _GET_PAYLOAD_MAX_ATTEMPTS + 1):
        is_last_attempt = attempt == _GET_PAYLOAD_MAX_ATTEMPTS
        try:
            resp = _get_with_watchdog(url, timeout=TIMEOUT)
            try:
                resp.raise_for_status()
            except requests.HTTPError as exc:
                print(f"  [!] Échec HTTP {resp.status_code} depuis {url} : {exc}", file=sys.stderr)
                # 4xx = erreur déterministe côté serveur (ressource absente, non
                # autorisée...) : inutile de retenter, sur ce format ou un autre.
                if 400 <= resp.status_code < 500:
                    return _TERMINAL_FAILURE
                # 5xx = erreur serveur potentiellement transitoire.
                if not is_last_attempt:
                    time.sleep(_GET_PAYLOAD_RETRY_BACKOFF_SECONDS)
                    continue
                return None
            content_type = resp.headers.get("content-type", "")
            if "json" in content_type.lower() or resp.text.lstrip().startswith("{"):
                try:
                    return resp.json()
                except ValueError as exc:
                    print(f"  [!] Réponse JSON invalide depuis {url} : {exc}", file=sys.stderr)
                    # JSON malformé = réponse serveur incohérente, pas un vrai JSON :
                    # on traite comme terminal pour ne pas réessayer en XML.
                    return _TERMINAL_FAILURE
            if "xml" in content_type.lower() or resp.text.lstrip().startswith("<"):
                parsed = _xml_to_data(resp.text)
                if parsed is not None:
                    return parsed
            print(f"  [!] Format de réponse non pris en charge depuis {url}", file=sys.stderr)
            # Format inconnu = réponse serveur non exploitable de façon déterministe.
            return _TERMINAL_FAILURE
        except requests.RequestException as exc:
            print(
                f"  [!] Échec de requête sur {url} (tentative {attempt}/{_GET_PAYLOAD_MAX_ATTEMPTS}) : {exc}",
                file=sys.stderr,
            )
            if not is_last_attempt:
                time.sleep(_GET_PAYLOAD_RETRY_BACKOFF_SECONDS)
                continue
            return None
    return None  # pragma: no cover - inatteignable, chaque branche ci-dessus retourne déjà


def _try_urls(urls: list[str], label: str, slug: str) -> tuple[Optional[Any], Optional[str]]:
    """Essaie plusieurs URLs jusqu'à trouver un payload exploitable.

    Logique de court-circuit :
    - Si ``_get_payload`` renvoie ``_TERMINAL_FAILURE`` sur le suffixe ``/json``,
      on saute directement le suffixe ``/xml`` pour ce ``base_url`` (même
      ressource, format différent : le serveur a déjà répondu de façon
      déterministe).
    - Si ``_get_payload`` renvoie ``_TERMINAL_FAILURE`` directement sur un
      ``base_url`` (4xx), on passe au ``base_url`` suivant sans essayer ``/xml``.
    """
    for base_url in urls:
        base_terminal = False
        for suffix in ["/json", "/xml"]:
            if base_terminal:
                break
            url = f"{base_url}/{slug}{suffix}"
            print(f"-> {label} : {url}")
            data = _get_payload(url)
            if data is _TERMINAL_FAILURE:
                # Échec déterministe : inutile d'essayer l'autre format sur ce
                # base_url (même ressource servie différemment).
                base_terminal = True
                break
            if not _is_empty_payload(data):
                return data, base_url
            time.sleep(0.2)
    return None, None


def fetch_identity(base_urls: list[str], slug: str) -> tuple[Optional[Any], Optional[str]]:
    """Infos biographiques, mandats, contacts."""
    return _try_urls(base_urls, "Récupération de l'identité", slug)


def fetch_dossiers(base_url: str, legislature: str) -> Optional[dict]:
    """Récupère la liste des dossiers législatifs d'une législature."""
    url = f"{base_url}/{legislature}/dossiers/nom/json"
    print(f"-> Dossiers législatifs : {url}")
    return _get_payload(url)


def fetch_dossiers_for_legislatures(base_url: str, legislatures: list[str]) -> list[dict[str, Any]]:
    """Récupère et fusionne les dossiers législatifs pour plusieurs législatures."""
    dossiers: list[dict[str, Any]] = []
    for legislature in legislatures:
        payload = fetch_dossiers(base_url, legislature)
        if not isinstance(payload, dict):
            continue
        sections = payload.get("sections") or []
        for item in sections:
            if not isinstance(item, dict):
                continue
            section = item.get("section") or item
            if isinstance(section, dict):
                dossiers.append({
                    "legislature": legislature,
                    "id": section.get("id"),
                    "titre": section.get("titre"),
                    "date_min": section.get("min_date"),
                    "date_max": section.get("max_date"),
                    "nb_interventions": section.get("nb_interventions"),
                    "url_institution": section.get("url_institution"),
                    "url_source": section.get("url_nosdeputes"),
                })
        time.sleep(0.2)
    return dossiers


def _normalize_search_query(text: str) -> str:
    """Normalise une requête de recherche (minuscules, sans accents).

    Le moteur de recherche de nosdeputes.fr/nossenateurs.fr renvoie parfois 0
    résultat pour une requête multi-mots contenant une majuscule accentuée en
    première position (ex. "Élisabeth Borne" -> 0 résultat), alors que la même
    requête en minuscules et sans accents ("elisabeth borne") renvoie bien les
    résultats attendus. On normalise donc systématiquement la requête envoyée
    à l'API pour éviter ce comportement erratique.
    """
    decomposed = unicodedata.normalize("NFKD", text)
    without_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    return without_accents.lower()


def fetch_recherche(base_url: str, query: str, object_name: Optional[str] = None, page: int = 1) -> Optional[dict]:
    """Récupère les résultats de recherche API pour un terme donné."""
    params = [f"format=json"]
    if object_name:
        params.append(f"object_name={object_name}")
    if page and page > 1:
        params.append(f"page={page}")
    url = f"{base_url}/recherche/{query}?{'&'.join(params)}"
    print(f"-> Recherche API : {url}")
    return _get_payload(url)


def fetch_all_intervention_results(base_url: str, query: str, object_name: str = "Intervention", max_pages: int = 10) -> dict[str, Any]:
    """Agrège les résultats de recherche sur plusieurs pages jusqu'à épuisement ou plafond."""
    aggregated: list[dict[str, Any]] = []
    normalized_query = _normalize_search_query(query)
    for page in range(1, max_pages + 1):
        payload = fetch_recherche(base_url, normalized_query, object_name=object_name, page=page)
        if not isinstance(payload, dict):
            break
        results = payload.get("results") or []
        if not results:
            break
        aggregated.extend(results)
        time.sleep(0.2)
    return {"results": aggregated}


def fetch_all_intervention_results_from_domains(
    base_urls: list[str],
    query: str,
    object_name: str = "Intervention",
    max_pages: int = 10,
) -> dict[str, Any]:
    """Interroge tous les domaines en parallèle, fusionne les résultats et supprime les doublons."""
    if not base_urls:
        return {"results": []}

    normalized_query = _normalize_search_query(query)

    def _fetch_one(base_url: str) -> list[dict[str, Any]]:
        payload = fetch_all_intervention_results(base_url, normalized_query, object_name=object_name, max_pages=max_pages)
        results = payload.get("results") or []
        enriched: list[dict[str, Any]] = []
        for item in results:
            if not isinstance(item, dict):
                continue
            enriched_item = dict(item)
            enriched_item["_search_base_url"] = base_url
            enriched_item["_search_query"] = normalized_query
            enriched_item["_search_object_name"] = object_name
            enriched.append(enriched_item)
        return enriched

    # Recherche parallèle sur chaque domaine : plusieurs requêtes de recherche
    # distinctes, puis fusion des réponses et déduplication par document_id.
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, len(base_urls))) as executor:
        domain_results = list(executor.map(_fetch_one, base_urls))

    merged_results: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for results in domain_results:
        for item in results:
            if not isinstance(item, dict):
                continue
            document_id = item.get("document_id")
            if not document_id:
                continue
            key = str(document_id)
            if key in seen_ids:
                continue
            seen_ids.add(key)
            merged_results.append(item)

    return {"results": merged_results}


def _extract_acteur_ref(url_an_ou_senat: Optional[str]) -> Optional[str]:
    """Extrait l'identifiant officiel Assemblée nationale (ex: PA2150) depuis une URL de fiche."""
    if not url_an_ou_senat:
        return None
    match = re.search(r"PA\d+", url_an_ou_senat)
    return match.group(0) if match else None


def _scrutins_shard_path_acteur(legislature: str, acteur_ref: str) -> Optional[Path]:
    """Chemin de la tranche d'index de votes d'UN acteur (#403, reprise de #392).

    Retourne `None` si `acteur_ref` n'a pas la forme attendue d'un identifiant
    AN (`PA` suivi de chiffres) : le nom de fichier en étant dérivé, on refuse
    tout ce qui pourrait sortir du répertoire de cache plutôt que d'assainir
    approximativement."""
    if not isinstance(acteur_ref, str) or not re.fullmatch(r"PA\d+", acteur_ref):
        return None
    return (
        SCRUTINS_CACHE_DIR
        / legislature
        / SCRUTINS_CACHE_INDEX_PAR_ACTEUR_DIRNAME
        / f"{acteur_ref}.json"
    )


def _scrutins_zip_url(legislature: str) -> Optional[str]:
    """URL de l'archive open data des scrutins d'une législature, ou `None` si
    l'Assemblée nationale n'en publie pas (13e et antérieures)."""
    zip_name = AN_SCRUTINS_ZIP_NAME.get(legislature)
    if not zip_name:
        return None
    return f"{AN_OPENDATA_BASE}/{legislature}/loi/scrutins/{zip_name}"


def _iter_votants(decompte_nominatif: dict, position: str, list_keys: tuple[str, ...]):
    """Parcourt la liste nominative des votants pour une position donnée.

    `list_keys` énumère les noms de clé possibles pour cette position, les deux
    schémas cohabitant dans les archives réelles (relevé exhaustif du
    18/08/2026 sur les quatre législatures) :
    - pluriel `pours`/`contres`/`abstentions`/`nonVotants` : schéma moderne,
      toute la 15e/17e et 4 105 des 4 106 scrutins de la 16e ;
    - singulier `pour`/`contre` : toute la 14e (avec `abstentions`/`nonVotants`
      au pluriel) ;
    - singulier `pour`/`contre`/`abstention`/`nonVotant` : le scrutin du
      Congrès `VTCGR5L16V1` (4 mars 2024), seule occurrence.

    Ce dernier cas n'est pas théorique : l'indexeur d'avant #403 n'acceptait
    que le pluriel et perdait donc ce scrutin en silence pour tout le jeu de
    données."""
    for list_key in list_keys:
        block = decompte_nominatif.get(list_key)
        if not isinstance(block, dict):
            continue
        votants = block.get("votant")
        if votants is None:
            continue
        if isinstance(votants, dict):
            votants = [votants]
        for v in votants:
            if isinstance(v, dict) and v.get("acteurRef"):
                yield v["acteurRef"], position


# Position du schema pivot -> noms de cle possibles dans decompteNominatif
# (voir `_iter_votants` pour la difference de schema entre la 14e et les
# legislatures suivantes).
_SCRUTINS_POSITION_KEYS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("pour", ("pours", "pour")),
    ("contre", ("contres", "contre")),
    ("abstention", ("abstentions", "abstention")),
    ("non_votant", ("nonVotants", "nonVotant")),
)


def _iter_scrutins_bruts(data: Any):
    """Parcourt les scrutins d'une entrée d'archive, quel que soit son conditionnement.

    Deux conditionnements coexistent chez l'Assemblée nationale (constaté le
    18/08/2026 sur les archives réelles) :
    - légis 15/16/17 : une arborescence `json/`, **un fichier par scrutin**,
      racine `{"scrutin": {...}}` ;
    - légis 14 : un JSON **monolithique** `Scrutins_XIV.json`, racine
      `{"scrutins": {"scrutin": [...]}}`, avec la même structure de scrutin.

    C'est le même changement d'architecture AN entre la 14e et la 15e que pour
    les dossiers législatifs (#400) et les amendements — mais ici les données
    de la 14e sont bien présentes, seul le conditionnement diffère : les
    ignorer perdrait 1 354 scrutins réels. Le conditionnement est détecté par
    la clé racine, jamais par le nom de fichier."""
    if not isinstance(data, dict):
        return
    unitaire = data.get("scrutin")
    if isinstance(unitaire, dict):
        yield unitaire
        return
    groupe = data.get("scrutins")
    if isinstance(groupe, dict):
        scrutins = groupe.get("scrutin")
        if isinstance(scrutins, dict):
            scrutins = [scrutins]
        for scrutin in scrutins or []:
            if isinstance(scrutin, dict):
                yield scrutin


def _parse_scrutins_zip(
    zip_path_or_bytes: Any, legislature: str
) -> tuple[dict[str, dict[str, Any]], dict[str, list[list[str]]]]:
    """Parse une archive de scrutins AN en `(scrutins, index_par_acteur)` dédupliqués.

    Lu directement depuis le zip, sans extraction sur disque : l'arborescence
    décompressée pèse 64 à 182 Mo par législature alors que seul l'index en est
    tiré (extrait de la construction pour être réutilisable par
    `build_scrutins_index_figes.py`, qui parse une archive téléchargée hors CI).

    - `scrutins` : `uid -> {numero, date, titre, sort, legislature}`, le meta
      stocké UNE seule fois (forme dédupliquée, #377) ;
    - `index_par_acteur` : `acteurRef -> [[uid, position], ...]`, référence
      minimale par lien acteur/scrutin.

    L'`uid` (ex. `VTANR5L17V1000`) porte la législature : il est unique toutes
    législatures confondues, contrairement au `numero` qui repart de 1 à chaque
    législature — c'est lui qui sert de clé de déduplication inter-législatures
    dans `fetch_votes_officiels`.

    Lève `zipfile.BadZipFile` si l'archive est invalide (laissé à l'appelant)."""
    scrutins: dict[str, dict[str, Any]] = {}
    index: dict[str, list[list[str]]] = {}
    ignores_hors_an = 0

    with zipfile.ZipFile(zip_path_or_bytes) as zf:
        membres = [m for m in zf.namelist() if m.endswith(".json")]
        for membre in membres:
            try:
                with zf.open(membre) as f:
                    data = json.load(io.TextIOWrapper(f, encoding="utf-8"))
            except (json.JSONDecodeError, OSError, KeyError):
                continue
            for scrutin in _iter_scrutins_bruts(data):
                uid = scrutin.get("uid")
                organe = (scrutin.get("ventilationVotes") or {}).get("organe") or {}
                groupes = (organe.get("groupes") or {}).get("groupe")
                if not uid or groupes is None:
                    continue
                if not str(uid).startswith(AN_SCRUTIN_UID_PREFIXE):
                    # Scrutin du Congrès : hors périmètre, voir AN_SCRUTIN_UID_PREFIXE.
                    ignores_hors_an += 1
                    continue
                if isinstance(groupes, dict):
                    groupes = [groupes]
                scrutins[uid] = {
                    "numero": scrutin.get("numero"),
                    "date": scrutin.get("dateScrutin"),
                    "titre": scrutin.get("titre"),
                    "sort": (scrutin.get("sort") or {}).get("libelle"),
                    "legislature": scrutin.get("legislature") or legislature,
                }
                for groupe in groupes:
                    if not isinstance(groupe, dict):
                        continue
                    decompte = (groupe.get("vote") or {}).get("decompteNominatif") or {}
                    for position, list_keys in _SCRUTINS_POSITION_KEYS:
                        for acteur_ref, pos in _iter_votants(decompte, position, list_keys):
                            index.setdefault(acteur_ref, []).append([uid, pos])

    if ignores_hors_an:
        print(
            f"  [i] {ignores_hors_an} scrutin(s) hors Assemblée nationale (Congrès) "
            f"écarté(s) pour la législature {legislature} — voir AN_SCRUTIN_UID_PREFIXE"
        )
    return scrutins, index


def _write_cached_scrutins(
    legislature: str,
    scrutins: dict[str, dict[str, Any]],
    index_par_acteur: dict[str, list[list[str]]],
) -> None:
    """Écrit (best-effort) le cache disque d'une législature sous forme
    dédupliquée et shardée : `scrutins.json` puis une tranche par acteur.

    `scrutins.json` est écrit en premier et le répertoire de tranches n'est
    considéré valide en lecture que s'il existe : une écriture interrompue
    laisse donc un cache traité comme absent (reconstruit au run suivant),
    jamais un couple incohérent. Écrase au passage l'`index_par_acteur.json`
    plat hérité d'avant #403 et l'arborescence `json/` décompressée, qui
    pesaient ensemble jusqu'à 538 Mo pour la seule 17e législature — la
    migration d'un ancien cache libère donc cette place au premier run."""
    cache_dir = SCRUTINS_CACHE_DIR / legislature
    cache_dir.mkdir(parents=True, exist_ok=True)
    with open(cache_dir / SCRUTINS_CACHE_SCRUTINS_FILENAME, "w", encoding="utf-8") as f:
        json.dump(scrutins, f, ensure_ascii=False)

    index_dir = cache_dir / SCRUTINS_CACHE_INDEX_PAR_ACTEUR_DIRNAME
    # Répertoire reconstruit de zéro : un acteur disparu d'une reconstruction
    # ne doit pas laisser sa tranche périmée derrière lui.
    shutil.rmtree(index_dir, ignore_errors=True)
    index_dir.mkdir(parents=True, exist_ok=True)
    for acteur_ref, refs in index_par_acteur.items():
        shard = _scrutins_shard_path_acteur(legislature, acteur_ref)
        if shard is None:
            continue  # acteurRef hors forme attendue : ignoré plutôt qu'écrit
        with open(shard, "w", encoding="utf-8") as f:
            json.dump(refs, f, ensure_ascii=False)

    (cache_dir / SCRUTINS_CACHE_INDEX_PAR_ACTEUR_FILENAME_LEGACY).unlink(missing_ok=True)
    shutil.rmtree(cache_dir / "json", ignore_errors=True)


def _read_cached_scrutins_store(legislature: str) -> Optional[dict[str, dict[str, Any]]]:
    """Store dédupliqué `uid -> scrutin` d'une législature, mémoïsé en mémoire process.

    Sûr à mémoïser, contrairement aux index par acteur complets : mesuré sur le
    cache réel, les quatre stores réunis pèsent 5,5 Mo (2,5 Mo pour la 17e, la
    plus lourde) là où les quatre index par acteur pèsent 68 Mo — et 741 Mo
    une fois expansés en forme plate, ce qui est exactement le chemin qui a
    déclenché deux OOM sur les amendements (#377, #392).

    Le cache disque n'est jamais réécrit pendant la vie d'un process de collecte
    au-delà de sa première matérialisation, donc mémoïser ne peut pas servir une
    version périmée. La lecture prend le même verrou par législature que cette
    matérialisation : sans lui, un thread pouvant mémoïser un `None` lu avant
    l'écriture du cache juste après que le thread écrivain a purgé le mémo, la
    législature resterait « indisponible » pour tout le reste du process."""
    with _get_scrutins_lock(legislature):
        if legislature in _SCRUTINS_STORE_MEMO:
            return _SCRUTINS_STORE_MEMO[legislature]
        path = SCRUTINS_CACHE_DIR / legislature / SCRUTINS_CACHE_SCRUTINS_FILENAME
        store: Optional[dict[str, dict[str, Any]]] = None
        if path.is_file():
            try:
                with open(path, encoding="utf-8") as f:
                    charge = json.load(f)
                if isinstance(charge, dict):
                    store = charge
            except (json.JSONDecodeError, OSError):
                store = None  # cache corrompu : traité comme absent
        _SCRUTINS_STORE_MEMO[legislature] = store
        return store


def _clear_scrutins_store_memo() -> None:
    """Vide le mémo du store (tests uniquement : un process de collecte ne voit
    jamais le cache disque changer sous lui après matérialisation)."""
    _SCRUTINS_STORE_MEMO.clear()


def _scrutins_cache_present(legislature: str) -> bool:
    """True si le cache disque d'une législature est déjà matérialisé sous la
    forme dédupliquée + shardée (#403). Un cache écrit avant #403 (fichier
    unique, forme plate) est indiscernable d'un cache absent, donc reconstruit
    — jamais relu en mémoire, ce qui est précisément ce qu'il fallait éviter."""
    cache_dir = SCRUTINS_CACHE_DIR / legislature
    return (
        (cache_dir / SCRUTINS_CACHE_SCRUTINS_FILENAME).is_file()
        and (cache_dir / SCRUTINS_CACHE_INDEX_PAR_ACTEUR_DIRNAME).is_dir()
    )


def _load_frozen_scrutins_index(legislature: str) -> bool:
    """Matérialise dans le cache disque l'index committé d'une législature figée
    (`AN_SCRUTINS_LEGISLATURES_FIGEES`), construit hors CI par
    `build_scrutins_index_figes.py` sous forme dédupliquée et gzippée.

    Retourne False si le fallback committé est absent ou illisible : l'appelant
    retombe alors sur le chemin réseau standard (l'archive reste téléchargeable,
    le gel n'est ici qu'une économie de CI — voir
    docs/technical_decisions.md#votes-multi-legislature)."""
    frozen_dir = AN_SCRUTINS_FIGES_DIR / legislature
    frozen_scrutins_path = frozen_dir / SCRUTINS_FIGES_SCRUTINS_FILENAME
    frozen_index_path = frozen_dir / SCRUTINS_FIGES_INDEX_PAR_ACTEUR_FILENAME
    if not frozen_scrutins_path.is_file() or not frozen_index_path.is_file():
        return False
    try:
        with gzip.open(frozen_scrutins_path, "rt", encoding="utf-8") as f:
            scrutins = json.load(f)
        with gzip.open(frozen_index_path, "rt", encoding="utf-8") as f:
            index_par_acteur = json.load(f)
    except (json.JSONDecodeError, OSError):
        return False
    if not isinstance(scrutins, dict) or not isinstance(index_par_acteur, dict):
        return False

    try:
        _write_cached_scrutins(legislature, scrutins, index_par_acteur)
    except OSError:
        return False
    return True


def _ensure_scrutins_index(legislature: str) -> bool:
    """Garantit la présence du cache d'index de votes d'une législature.

    Ordre : cache déjà matérialisé → index committé si la législature est figée
    → téléchargement + parsing de l'archive AN. Retourne False si aucune de ces
    voies n'aboutit (législature sans open data, réseau indisponible, archive
    invalide) — chaque législature étant tentée indépendamment, un échec ici
    n'empêche jamais les autres d'être agrégées.

    Thread-safe : un verrou par législature garantit qu'un seul thread à la fois
    télécharge et écrit le cache d'une législature donnée ; des législatures
    différentes sont traitées sans blocage mutuel."""
    with _get_scrutins_lock(legislature):
        if _scrutins_cache_present(legislature):
            return True

        if legislature in AN_SCRUTINS_LEGISLATURES_FIGEES and _load_frozen_scrutins_index(legislature):
            print(f"-> Index de scrutins figé réutilisé (législature {legislature}, aucun téléchargement)")
            return True

        url = _scrutins_zip_url(legislature)
        if not url:
            return False

        print(f"-> Téléchargement des scrutins officiels (Assemblée nationale) : {url}")
        try:
            resp = requests.get(url, headers=HEADERS, timeout=60)
            resp.raise_for_status()
        except requests.RequestException as exc:
            print(f"  [!] Échec du téléchargement des scrutins officiels : {exc}")
            return False

        try:
            scrutins, index = _parse_scrutins_zip(io.BytesIO(resp.content), legislature)
        except zipfile.BadZipFile as exc:
            print(f"  [!] Archive de scrutins invalide : {exc}")
            return False

        if not scrutins:
            return False

        print(f"-> Indexation de {len(scrutins)} scrutins officiels (législature {legislature})...")
        try:
            _write_cached_scrutins(legislature, scrutins, index)
        except OSError:
            return False
        _SCRUTINS_STORE_MEMO.pop(legislature, None)
        return True


def _read_cached_votes_acteur(legislature: str, acteur_ref: str) -> Optional[list[dict[str, Any]]]:
    """Votes d'UN acteur pour une législature, résolus depuis le cache dédupliqué
    et shardé. Retourne `None` si le cache est absent/illisible, une liste
    éventuellement vide si l'acteur n'y figure pas — distinguer « n'a pas voté
    sous cette législature » de « index indisponible » est ce qui pilote le
    warning côté `fetch_votes_officiels` (règle 5 : une donnée manquante n'est
    jamais un 0).

    Coût : une tranche d'acteur (~55 Ko) plus le store mémoïsé, au lieu des
    132 à 357 Mo d'index complets que la forme d'avant #403 relisait pour
    chaque candidat."""
    store = _read_cached_scrutins_store(legislature)
    if store is None:
        return None

    index_dir = SCRUTINS_CACHE_DIR / legislature / SCRUTINS_CACHE_INDEX_PAR_ACTEUR_DIRNAME
    if not index_dir.is_dir():
        return None

    shard_path = _scrutins_shard_path_acteur(legislature, acteur_ref)
    if shard_path is None or not shard_path.is_file():
        return []

    try:
        with open(shard_path, encoding="utf-8") as f:
            refs = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(refs, list):
        return None

    votes: list[dict[str, Any]] = []
    for ref in refs:
        if not isinstance(ref, (list, tuple)) or len(ref) != 2:
            continue
        uid, position = ref
        base = store.get(uid)
        if base is None:
            continue
        votes.append({**base, "uid": uid, "position": position})
    return votes


def fetch_votes_officiels(
    url_an_ou_senat: Optional[str], warnings: Optional[list[str]] = None
) -> tuple[list[dict[str, Any]], list[str]]:
    """Récupère les votes nominatifs officiels d'un député via l'open data de l'Assemblée nationale.

    L'endpoint /votes de NosDéputés.fr est en panne (HTTP 500 systématique, y
    compris sur l'exemple officiel de leur propre documentation, testé sur tous
    les domaines et législatures disponibles). On utilise donc directement les
    données ouvertes de data.assemblee-nationale.fr, qui contiennent le détail
    nominatif (pour/contre/abstention/non-votant) de chaque scrutin, identifié
    par l'acteurRef (ex: PA2150) du parlementaire.

    Agrège **toutes** les législatures publiées (`AN_SCRUTINS_LEGISLATURES`),
    comme le font déjà les amendements et les dossiers législatifs : jusqu'à
    #403, une seule législature était interrogée — celle déduite du domaine
    NosDéputés où l'identité avait été trouvée, donc en pratique toujours la
    16e, ce qui arrêtait les votes de tout le jeu de données en juin 2024 et en
    perdait 2,7x.

    Chaque législature est tentée indépendamment : une archive indisponible
    n'interrompt jamais l'agrégation des autres (même précaution qu'en #241 sur
    les amendements) ; si `warnings` est fourni, l'absence y est tracée par
    législature.

    Retourne `(votes, legislatures_couvertes)`, les votes triés du plus récent
    au plus ancien et dédupliqués par `uid` de scrutin — jamais par `numero`,
    qui repart de 1 à chaque législature (#400 : un fait ne doit jamais être
    compté deux fois)."""
    acteur_ref = _extract_acteur_ref(url_an_ou_senat)
    if not acteur_ref:
        return [], []

    votes: list[dict[str, Any]] = []
    vus: set[str] = set()
    legislatures_couvertes: list[str] = []
    for legislature in AN_SCRUTINS_LEGISLATURES:
        if not _ensure_scrutins_index(legislature):
            if warnings is not None:
                warnings.append(
                    f"{WARNING_PREFIX_VOTES_INTROUVABLES} (législature {legislature}) : "
                    "index des scrutins indisponible (archive open data non téléchargée ou invalide)."
                )
            continue
        records = _read_cached_votes_acteur(legislature, acteur_ref)
        if records is None:
            if warnings is not None:
                warnings.append(
                    f"{WARNING_PREFIX_VOTES_INTROUVABLES} (législature {legislature}) : "
                    "cache d'index des scrutins illisible."
                )
            continue
        retenus = 0
        for record in records:
            uid = record.get("uid")
            if uid in vus:
                continue
            vus.add(uid)
            votes.append(record)
            retenus += 1
        if retenus:
            legislatures_couvertes.append(legislature)

    votes.sort(key=lambda v: v.get("date") or "", reverse=True)
    return votes, sorted(legislatures_couvertes)


# Type d'auteur (open data amendements) -> type_deposant du schema pivot.
_AMENDEMENT_TYPE_AUTEUR_MAP: dict[str, str] = {
    "Député": "depute",
    # "Depute" (sans accent) : forme observée dans le schéma legacy de la 14e
    # législature (archive réelle, 15/08/2026) — jamais produite par le
    # schéma moderne (15/16/17), ajoutée sans risque de collision.
    "Depute": "depute",
    "Gouvernement": "gouvernement",
    "Rapporteur": "commission_rapporteur",
    "Commission": "commission_rapporteur",
}

# (etat.libelle, sousEtat.libelle) -> sort du schema pivot. Determine
# empiriquement sur ~3000 amendements de la 17e legislature : "En traitement"
# et "A discuter" (sousEtat souvent absent) signifient que le sort n'est pas
# encore connu, et sont volontairement absents de cette table (sort reste
# None). Les etats "Irrecevable"/"Irrecevable 40" sont traites a part (voir
# _derive_amendement_sort) car leurs sousEtat ne sont pas des sorts mais des
# motifs d'irrecevabilite.
_AMENDEMENT_SORT_MAP: dict[tuple[Optional[str], Optional[str]], str] = {
    ("Discuté", "Rejeté"): "rejeté",
    ("Discuté", "Adopté"): "adopté",
    ("Discuté", "Tombé"): "tombé",
    ("Discuté", "Non soutenu"): "non_soutenu",
    ("Discuté", "Retiré"): "retiré",
    ("Retiré", "Retiré après publication"): "retiré",
    ("Retiré", "Retiré avant publication"): "retiré",
}


def _derive_amendement_sort(etat_libelle: Optional[str], sousetat_libelle: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """Déduit (sort, base_juridique_irrecevabilite) depuis les libellés d'état officiels.

    L'open data amendements distingue "Irrecevable 40" (irrecevabilité
    financière, art. 40) d'"Irrecevable" tout court (les nombreux autres motifs
    observés — cavalier art. 45, sous-amendement art. 98, hors délais, etc. —
    ne correspondent pas tous littéralement à l'art. 45, mais le schéma pivot
    ne distingue que "art. 40" | "art. 45" : "art. 45" est donc utilisé comme
    catégorie par défaut pour tout motif d'irrecevabilité non financier).
    """
    if etat_libelle in ("Irrecevable", "Irrecevable 40"):
        base = "art. 40" if etat_libelle == "Irrecevable 40" else "art. 45"
        return "irrecevable", base
    return _AMENDEMENT_SORT_MAP.get((etat_libelle, sousetat_libelle)), None


def _extract_cosignataire_refs(cosignataires_bloc: Any) -> list[str]:
    """Normalise les différentes formes de `signataires.cosignataires`.

    Le bulk AN expose selon les jeux soit `{"acteurRef": ...}`, soit
    `{"acteur": {"acteurRef": ...}}` / `{"acteur": [{"acteurRef": ...}, ...]}`.
    """
    if not isinstance(cosignataires_bloc, dict):
        return []

    refs: list[str] = []

    direct_refs = cosignataires_bloc.get("acteurRef")
    if isinstance(direct_refs, str) and direct_refs:
        refs.append(direct_refs)
    elif isinstance(direct_refs, list):
        refs.extend(ref for ref in direct_refs if isinstance(ref, str) and ref)

    acteurs = cosignataires_bloc.get("acteur")
    items = acteurs if isinstance(acteurs, list) else [acteurs]
    for item in items:
        if isinstance(item, dict):
            acteur_ref = item.get("acteurRef")
            if isinstance(acteur_ref, str) and acteur_ref:
                refs.append(acteur_ref)

    # Déduplication en conservant l'ordre de lecture du payload source.
    return list(dict.fromkeys(refs))


def _parse_amendement_entry(data: Any) -> Optional[list[tuple[str, dict[str, Any]]]]:
    """Extrait les enregistrements indexés par acteurRef d'un amendement brut.

    Construit une entrée pour l'auteur principal et une entrée par cosignataire,
    avec un champ `role_signataire` permettant de distinguer les deux cas dans
    les usages avals.

    Gère le schéma « moderne » des archives amendements AN (légis 15/16/17,
    un fichier JSON par amendement, racine `{"amendement": {...}}`). La
    législature 14 utilise un schéma « legacy » distinct (un unique fichier
    JSON agrégeant tous les amendements, racine `{"textesEtAmendements":
    {...}}`), géré par `_parse_amendement_entry_legacy` — voir #299,
    docs/technical_decisions.md#amendements-legislatures-figees. Le choix
    entre les deux se fait dans `_parse_amendements_zip`, par entrée, selon
    la clé racine du contenu.
    """
    amendement = data.get("amendement") if isinstance(data, dict) else None
    if not isinstance(amendement, dict):
        return None

    signataires = amendement.get("signataires") or {}
    auteur = signataires.get("auteur") or {}
    acteur_ref = auteur.get("acteurRef")
    if not isinstance(acteur_ref, str) or not acteur_ref:
        return None

    cosignataires_bloc = signataires.get("cosignataires") or {}
    cosign_refs = _extract_cosignataire_refs(cosignataires_bloc)

    cycle_de_vie = amendement.get("cycleDeVie") or {}
    etat = cycle_de_vie.get("etatDesTraitements") or {}
    etat_libelle = (etat.get("etat") or {}).get("libelle") if isinstance(etat.get("etat"), dict) else None
    sousetat_libelle = (etat.get("sousEtat") or {}).get("libelle") if isinstance(etat.get("sousEtat"), dict) else None
    sort, base_juridique = _derive_amendement_sort(etat_libelle, sousetat_libelle)

    record_base = {
        # texteLegislatifRef est un code source (ex. "PRJLANR5L17B0324"), pas un
        # titre lisible : resolu en titre humain a posteriori si possible, voir
        # fetch_amendements_officiels/_build_texte_titre_index (dossiers legislatifs).
        "texte_vise": amendement.get("texteLegislatifRef"),
        "sort": sort,
        "base_juridique_irrecevabilite": base_juridique,
        # Prefixe "an:" : ce sont des identifiants Assemblee nationale bruts, pas
        # des identifiants pivot ("nosdeputes:slug") — la resolution vers un
        # candidat suivi par ce projet n'est pas faite ici.
        "premier_signataire": f"an:{acteur_ref}",
        "co_signataires": [f"an:{ref}" for ref in cosign_refs if isinstance(ref, str)],
        "type_deposant": _AMENDEMENT_TYPE_AUTEUR_MAP.get(auteur.get("typeAuteur")),
        "date": cycle_de_vie.get("dateDepot"),
        "numero": (amendement.get("identification") or {}).get("numeroLong"),
        "source_url": None,
    }

    out: list[tuple[str, dict[str, Any]]] = [
        (acteur_ref, {**record_base, "role_signataire": "auteur_principal"})
    ]

    for cosign_ref in cosign_refs:
        if not isinstance(cosign_ref, str) or not cosign_ref or cosign_ref == acteur_ref:
            continue
        out.append((cosign_ref, {**record_base, "role_signataire": "cosignataire"}))

    return out


# sortEnSeance (schéma legacy légis 14, racine `textesEtAmendements`) -> sort du
# schéma pivot. Contrairement à `_AMENDEMENT_SORT_MAP` (paire etat/sousEtat
# ambiguë selon le contexte), `sort.sortEnSeance` porte déjà sans ambiguïté
# l'issue en séance : simple normalisation de casse/accentuation, pas de
# dérivation heuristique. Voir issue #299.
_LEGACY_AMENDEMENT_SORT_EN_SEANCE_MAP: dict[str, str] = {
    "Adopté": "adopté",
    "Rejeté": "rejeté",
    "Tombé": "tombé",
    "Non soutenu": "non_soutenu",
    "Retiré": "retiré",
}


def _derive_amendement_sort_legacy(
    etat: Optional[str], sort_en_seance: Optional[str]
) -> tuple[Optional[str], Optional[str]]:
    """Équivalent de `_derive_amendement_sort` pour le schéma legacy légis 14.

    Même logique d'irrecevabilité (`etat` "Irrecevable"/"Irrecevable 40",
    identique à `_derive_amendement_sort`), mais l'issue en séance est portée
    directement par `sort.sortEnSeance` côté AN : pas de table (etat, sousEtat)
    à interpréter, une simple normalisation suffit.
    """
    if etat in ("Irrecevable", "Irrecevable 40"):
        base = "art. 40" if etat == "Irrecevable 40" else "art. 45"
        return "irrecevable", base
    return _LEGACY_AMENDEMENT_SORT_EN_SEANCE_MAP.get(sort_en_seance), None


def _parse_amendement_legacy_single(
    amendement: dict[str, Any], texte_ref: Optional[str]
) -> list[tuple[str, dict[str, Any]]]:
    """Extrait les enregistrements indexés par acteurRef d'un amendement au
    format legacy (légis 14, déjà déballé d'un `texteleg`). `texte_ref` est
    porté par le `texteleg` parent, pas par l'amendement lui-même."""
    signataires = amendement.get("signataires") or {}
    auteur = signataires.get("auteur") or {}
    acteur_ref = auteur.get("acteurRef")
    if not isinstance(acteur_ref, str) or not acteur_ref:
        return []

    cosignataires_bloc = signataires.get("cosignataires") or {}
    cosign_refs = _extract_cosignataire_refs(cosignataires_bloc)

    identifiant = amendement.get("identifiant") or {}
    sort_bloc = amendement.get("sort") or {}
    sort, base_juridique = _derive_amendement_sort_legacy(
        amendement.get("etat"), sort_bloc.get("sortEnSeance")
    )

    record_base = {
        "texte_vise": texte_ref,
        "sort": sort,
        "base_juridique_irrecevabilite": base_juridique,
        "premier_signataire": f"an:{acteur_ref}",
        "co_signataires": [f"an:{ref}" for ref in cosign_refs if isinstance(ref, str)],
        "type_deposant": _AMENDEMENT_TYPE_AUTEUR_MAP.get(auteur.get("typeAuteur")),
        "date": amendement.get("dateDepot"),
        # `numeroLong` (ex. "7 (Rect)") est à la racine de l'amendement, pas
        # imbriqué sous `identifiant` (qui ne porte que le numéro nu "7" —
        # vérifié sur l'archive réelle le 15/08/2026 : lire depuis
        # `identifiant` ici perdait silencieusement le suffixe de
        # rectification sur tout amendement rectifié).
        "numero": amendement.get("numeroLong") or identifiant.get("numero"),
        "source_url": None,
    }

    out: list[tuple[str, dict[str, Any]]] = [
        (acteur_ref, {**record_base, "role_signataire": "auteur_principal"})
    ]
    for cosign_ref in cosign_refs:
        if not isinstance(cosign_ref, str) or not cosign_ref or cosign_ref == acteur_ref:
            continue
        out.append((cosign_ref, {**record_base, "role_signataire": "cosignataire"}))

    return out


def _parse_amendement_entry_legacy(data: Any) -> Optional[list[tuple[str, dict[str, Any]]]]:
    """Variante de `_parse_amendement_entry` pour le schéma legacy de la 14e
    législature (clé racine `textesEtAmendements`, voir issue #299) : une
    seule entrée JSON regroupe tous les `texteleg`, chacun listant ses
    amendements (`texteleg[].amendements.amendement[]`), au lieu d'un fichier
    par amendement. Produit les mêmes clés de sortie que
    `_parse_amendement_entry`. Retourne `None` seulement si la clé racine
    `textesEtAmendements` elle-même est absente/mal formée ; une liste vide
    est un résultat légitime (aucun amendement exploitable dans l'entrée).
    """
    root = data.get("textesEtAmendements") if isinstance(data, dict) else None
    if not isinstance(root, dict):
        return None

    texteleg_bloc = root.get("texteleg")
    textelegs = texteleg_bloc if isinstance(texteleg_bloc, list) else [texteleg_bloc]

    out: list[tuple[str, dict[str, Any]]] = []
    for texteleg in textelegs:
        if not isinstance(texteleg, dict):
            continue
        texte_ref = texteleg.get("refTexteLegislatif")
        amendement_bloc = (texteleg.get("amendements") or {}).get("amendement")
        amendements = amendement_bloc if isinstance(amendement_bloc, list) else [amendement_bloc]

        for amendement in amendements:
            if not isinstance(amendement, dict):
                continue
            out.extend(_parse_amendement_legacy_single(amendement, texte_ref))

    return out


def _amendements_zip_url(legislature: str) -> Optional[str]:
    entry = AN_AMENDEMENTS_PATH.get(legislature)
    if not entry:
        return None
    path_segment, zip_name = entry
    return f"{AN_OPENDATA_BASE}/{legislature}/loi/{path_segment}/{zip_name}"


class AmendementsIndexError(Exception):
    """Levée quand la construction de l'index amendements échoue (téléchargement ou
    parsing de l'archive AN). Distincte d'un index vide légitime (pas de dataset
    pour cette législature) : ne doit jamais être avalée silencieusement, pour que
    `fetch_amendements_officiels` (et le warning meta.warnings à l'appel) reflète
    l'échec au lieu d'un simple "aucun amendement"."""


def _content_range_total(resp: "requests.Response") -> Optional[int]:
    """Extrait la taille totale de la ressource depuis l'en-tête `Content-Range`
    d'une réponse HTTP 206 (ex. "bytes 100000000-101048575/363306362" -> 363306362).
    Retourne `None` si l'en-tête est absent ou mal formé."""
    content_range = resp.headers.get("Content-Range")
    if not content_range or "/" not in content_range:
        return None
    try:
        return int(content_range.rsplit("/", 1)[-1])
    except ValueError:
        return None


def _probe_amendements_total_size(url: str) -> Optional[int]:
    """Sonde légère (HEAD) pour connaître la taille totale de l'archive avant de
    décider de reprendre un téléchargement partiel préexistant. Best-effort :
    toute erreur réseau ou en-tête `Content-Length` absent/invalide retourne
    `None`, auquel cas l'appelant de `_download_amendements_zip` ne prend pas
    le risque de reprendre un fichier partiel et redémarre proprement depuis
    le début plutôt que de deviner."""
    try:
        resp = requests.head(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        resp.raise_for_status()
        content_length = resp.headers.get("Content-Length")
        return int(content_length) if content_length is not None else None
    except (requests.RequestException, TypeError, ValueError):
        return None


def _download_amendements_zip(
    url: str, zip_path: Path, legislature: str, chunk_bytes: Optional[int] = None,
    max_attempts: Optional[int] = None,
) -> None:
    """Télécharge l'archive zip des amendements par segments (requêtes HTTP Range),
    pour ne retenter que le segment en échec au lieu de tout le fichier sur une
    coupure mi-flux (`IncompleteRead` déjà observé en pratique sur ces archives de
    283-618 Mo — voir issue #241). Le support Range du CDN devant
    data.assemblee-nationale.fr a été vérifié fonctionnellement (réponse 206 +
    Content-Range) le 13/08/2026.

    Écrit séquentiellement dans `zip_path` (jamais en accès aléatoire) : un segment
    n'est écrit qu'une fois intégralement reçu, pour ne jamais laisser de segment
    partiel sur disque. Si le serveur ignore l'en-tête Range (réponse 200 au lieu
    de 206, cas non observé mais possible), bascule sur un téléchargement classique
    en un seul segment.

    Reprend un téléchargement interrompu **entre deux invocations** du script (pas
    seulement entre deux segments d'une même invocation) : si `zip_path` existe déjà
    avec un contenu non vide, une sonde `_probe_amendements_total_size` détermine la
    taille distante avant de décider — fichier déjà complet -> aucune requête envoyée ;
    fichier partiel plus petit que la taille distante -> reprise en mode ajout à partir
    de l'octet déjà présent ; sonde en échec ou taille locale incohérente (plus grande
    que la taille distante) -> redémarrage prudent depuis le début plutôt que de risquer
    une archive corrompue. Le CDN AN étant instable sur ces deux archives (coupures
    aléatoires en cours de segment, pas seulement à la fin), cette reprise évite de
    reperdre à chaque nouvelle invocation les dizaines/centaines de Mo déjà reçus.

    Réutilise `AMENDEMENTS_DOWNLOAD_MAX_ATTEMPTS`/`AMENDEMENTS_DOWNLOAD_BACKOFF_SECONDS`
    (#225), désormais appliqués par segment plutôt qu'au fichier entier. Lève la
    dernière `requests.RequestException`/`OSError` rencontrée si un segment échoue
    après épuisement des tentatives — l'appelant convertit en `AmendementsIndexError`.

    `chunk_bytes` permet de réduire ponctuellement la taille de segment (défaut
    `AMENDEMENTS_DOWNLOAD_CHUNK_BYTES`, 32 Mo) sans toucher au chemin réseau
    partagé de la législature 17 : observé le 14/08/2026, le CDN AN peut
    traverser des fenêtres où même une requête de quelques Ko au-delà des tout
    premiers Mo du fichier échoue systématiquement (`IncompleteRead(0 bytes
    read, ...)`) — un segment de 32 Mo n'a alors quasiment aucune chance
    d'aboutir intégralement, alors que de petits segments (1-2 Mo) ont une
    fenêtre de succès bien plus large à saisir, et la reprise entre
    invocations (ci-dessus) garantit qu'aucun de ces petits gains n'est perdu.

    Affiche une ligne de progression après chaque segment écrit avec succès
    (octets/total, pourcentage) — pas seulement en cas d'échec/retry : avec de
    petits `chunk_bytes`, une invocation peut compter des centaines de segments
    et rester silencieuse plusieurs minutes sans ce retour, au point de
    ressembler à un blocage (observé le 15/08/2026).

    `max_attempts` permet d'augmenter ponctuellement le nombre de tentatives
    par segment (défaut `AMENDEMENTS_DOWNLOAD_MAX_ATTEMPTS`, 3) sans toucher au
    chemin réseau partagé de la législature 17, où cette valeur est
    volontairement basse pour rester dans le budget CI. Reprise entre
    invocations oblige, la reprendre à une valeur plus haute ici ne coûte rien
    au-delà du temps d'attente : chaque tentative supplémentaire ne retente que
    le segment en échec, jamais le fichier entier.
    """
    chunk_bytes = chunk_bytes or AMENDEMENTS_DOWNLOAD_CHUNK_BYTES
    max_attempts = max_attempts or AMENDEMENTS_DOWNLOAD_MAX_ATTEMPTS
    zip_path.parent.mkdir(parents=True, exist_ok=True)

    offset = 0
    total_size: Optional[int] = None
    file_mode = "wb"

    existing_size = zip_path.stat().st_size if zip_path.is_file() else 0
    if existing_size > 0:
        remote_total_size = _probe_amendements_total_size(url)
        if remote_total_size is None:
            print(
                f"  -> Législature {legislature} : impossible de sonder la taille distante, "
                "redémarrage du téléchargement depuis le début (fichier partiel existant ignoré)."
            )
        elif existing_size == remote_total_size:
            print(
                f"  -> Législature {legislature} : archive déjà complète en local "
                f"({existing_size} octets), téléchargement sauté."
            )
            return
        elif existing_size > remote_total_size:
            print(
                f"  -> Législature {legislature} : fichier local ({existing_size} octets) plus "
                f"gros que l'archive distante ({remote_total_size} octets), incohérent — "
                "redémarrage du téléchargement depuis le début."
            )
        else:
            offset = existing_size
            total_size = remote_total_size
            file_mode = "ab"
            print(
                f"  -> Législature {legislature} : reprise du téléchargement à partir de "
                f"l'octet {offset}/{total_size} (tentative précédente interrompue)."
            )

    segments_total = 0
    segments_retried = 0

    with open(zip_path, file_mode) as out:
        while total_size is None or offset < total_size:
            range_end = offset + chunk_bytes - 1
            segments_total += 1
            last_exc: Optional[Exception] = None
            chunk = b""
            status_code: Optional[int] = None
            content_range_total: Optional[int] = None
            for attempt in range(1, max_attempts + 1):
                try:
                    headers = {**HEADERS, "Range": f"bytes={offset}-{range_end}"}
                    with requests.get(
                        url, headers=headers,
                        timeout=(TIMEOUT, AMENDEMENTS_DOWNLOAD_READ_TIMEOUT_SECONDS),
                        stream=True,
                    ) as resp:
                        resp.raise_for_status()
                        chunk = b"".join(resp.iter_content(chunk_size=1024 * 1024))
                        status_code = resp.status_code
                        if status_code == 206:
                            content_range_total = _content_range_total(resp)
                    last_exc = None
                    break
                except (requests.RequestException, OSError) as exc:
                    last_exc = exc
                    if attempt < max_attempts:
                        print(
                            f"  [!] Échec du téléchargement du segment amendements législature "
                            f"{legislature} (offset {offset}, tentative "
                            f"{attempt}/{max_attempts}) : {exc} — nouvel essai du segment seul"
                        )
                        time.sleep(AMENDEMENTS_DOWNLOAD_BACKOFF_SECONDS)
            if last_exc is not None:
                print(
                    f"  [!] Segment amendements législature {legislature} (offset {offset}) en échec "
                    f"définitif après {max_attempts} tentatives : {last_exc}"
                )
                raise last_exc
            if attempt > 1:
                segments_retried += 1

            if status_code == 200 and offset != 0:
                # Le serveur a ignoré l'en-tête Range et renvoyé le fichier entier alors
                # qu'un segment/une reprise à un offset non nul était attendu : l'écrire
                # corromprait l'archive (contenu dupliqué/décalé) — jamais observé en
                # pratique sur ce CDN, mais ne doit jamais être écrit silencieusement.
                raise OSError(
                    f"réponse HTTP 200 inattendue (en-tête Range ignoré) pour le segment "
                    f"amendements législature {legislature} à l'offset {offset} : écriture "
                    "annulée pour ne pas corrompre l'archive déjà partiellement écrite"
                )

            out.write(chunk)
            if status_code == 200:
                # Le serveur a ignoré l'en-tête Range et renvoyé le fichier entier.
                total_size = len(chunk)
                offset = total_size
                break

            if total_size is None:
                total_size = content_range_total or (offset + len(chunk))
            offset += len(chunk)
            if not chunk:
                break  # évite une boucle infinie sur un flux qui ne progresse plus

            if total_size:
                percent = offset / total_size * 100
                print(
                    f"  -> Législature {legislature} : {offset}/{total_size} octets "
                    f"({percent:.1f}%) — segment {segments_total} écrit"
                )
            else:
                print(
                    f"  -> Législature {legislature} : {offset} octets — segment "
                    f"{segments_total} écrit"
                )

    if segments_retried >= AMENDEMENTS_SEGMENT_RETRY_WARNING_THRESHOLD:
        print(
            f"  [!] Législature {legislature} : {segments_retried}/{segments_total} segment(s) ont "
            "nécessité un retry — instabilité réseau notable sur cette archive"
        )
    elif segments_retried:
        print(f"  -> Législature {legislature} : {segments_retried}/{segments_total} segment(s) retenté(s) avec succès")

    final_size = zip_path.stat().st_size
    if total_size is not None and final_size != total_size:
        raise OSError(
            f"taille finale incohérente pour l'archive amendements législature {legislature} : "
            f"{final_size} octets écrits, {total_size} attendus"
        )


def _shard_path_acteur(legislature: str, acteur_ref: str) -> Optional[Path]:
    """Chemin de la tranche d'index d'UN acteur (#392).

    Retourne `None` si `acteur_ref` n'a pas la forme attendue d'un
    identifiant AN (`PA` suivi de chiffres) : le nom de fichier étant dérivé
    de cette valeur, on refuse tout ce qui pourrait sortir du répertoire de
    cache plutôt que d'assainir approximativement."""
    if not isinstance(acteur_ref, str) or not re.fullmatch(r"PA\d+", acteur_ref):
        return None
    return (
        AMENDEMENTS_CACHE_DIR
        / legislature
        / AMENDEMENTS_CACHE_INDEX_PAR_ACTEUR_DIRNAME
        / f"{acteur_ref}.json"
    )


def _read_cached_amendements_store(legislature: str) -> Optional[dict[str, dict[str, Any]]]:
    """Store dédupliqué `numero -> amendement` d'une législature, mémoïsé en
    mémoire process (#392).

    Cette mémoïsation-ci est sûre, contrairement à celle tentée puis revertée
    en #377 — la différence tient à ce qui est gardé résident. Mesuré sur le
    cache réel :
    - les 4 `index_par_acteur` complets résidents : **3,84 Go** (rejeté, c'est
      ce qui avait provoqué l'OOM) ;
    - les 4 `amendements.json` seuls résidents : **426 Mo** (retenu).

    Le store est petit parce qu'il est dédupliqué (89 Mo sur disque pour les 4
    législatures, ~178 000 amendements uniques) ; c'est `index_par_acteur` qui
    pèse (580 Mo), et lui n'est plus jamais chargé en entier depuis #392 —
    seule la tranche de l'acteur demandé est lue.

    Le cache disque n'est jamais réécrit pendant la vie d'un process de
    collecte (seul `build_amendements_index.py`, exécuté avant, le produit),
    donc mémoïser ne peut pas servir une version périmée."""
    with _get_amendements_lock(legislature):
        if legislature in _AMENDEMENTS_STORE_MEMO:
            return _AMENDEMENTS_STORE_MEMO[legislature]
        path = AMENDEMENTS_CACHE_DIR / legislature / AMENDEMENTS_CACHE_AMENDEMENTS_FILENAME
        store: Optional[dict[str, dict[str, Any]]] = None
        if path.is_file():
            try:
                with open(path, encoding="utf-8") as f:
                    charge = json.load(f)
                if isinstance(charge, dict):
                    store = charge
            except (json.JSONDecodeError, OSError):
                store = None  # cache corrompu : traité comme absent
        _AMENDEMENTS_STORE_MEMO[legislature] = store
        return store


def _clear_amendements_store_memo() -> None:
    """Vide le mémo du store (tests uniquement : un process de collecte ne voit
    jamais le cache disque changer sous lui)."""
    _AMENDEMENTS_STORE_MEMO.clear()


def _read_cached_amendements_acteur(
    legislature: str, acteur_ref: str
) -> Optional[list[dict[str, Any]]]:
    """Amendements d'UN acteur pour une législature, résolus depuis le cache
    dédupliqué et **shardé par acteur** (#392). Retourne `None` si le cache
    est absent/illisible (l'appelant trace alors un warning), une liste
    éventuellement vide si l'acteur n'y figure pas.

    Coût : une tranche d'acteur (~285 Ko) au lieu des 673 Mo d'index complets
    que la version #377 relisait à chaque candidat — 93 % du temps
    d'extraction du roster y passait (mesuré en #376, ~10,9 s sur 11,7 s par
    membre, soit ~500 Go de JSON reparsé sur un run complet).

    Le store `amendements.json` est mémoïsé (voir
    `_read_cached_amendements_store`) : c'est lui qui rend la résolution des
    références possible sans relire quoi que ce soit après le premier appel."""
    store = _read_cached_amendements_store(legislature)
    if store is None:
        return None

    shard_path = _shard_path_acteur(legislature, acteur_ref)
    # Répertoire de tranches absent = cache hérité (#377, fichier unique) ou
    # jamais construit : indiscernables, et dans les deux cas il faut le
    # reconstruire plutôt que relire l'ancien format.
    index_dir = AMENDEMENTS_CACHE_DIR / legislature / AMENDEMENTS_CACHE_INDEX_PAR_ACTEUR_DIRNAME
    if not index_dir.is_dir():
        return None
    if shard_path is None or not shard_path.is_file():
        # Acteur simplement absent de cette législature : liste vide, pas None
        # — distinguer « pas d'amendement » de « index indisponible » est ce
        # qui pilote le warning côté fetch_amendements_officiels.
        return []

    try:
        with open(shard_path, encoding="utf-8") as f:
            refs = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(refs, list):
        return None

    entries: list[dict[str, Any]] = []
    for ref in refs:
        if not isinstance(ref, dict):
            continue
        base = store.get(ref.get("numero"))
        if base is None:
            continue
        entries.append({**base, "role_signataire": ref.get("role_signataire")})
    return entries


def _write_amendements_fraicheur(index_path: Path, reussi: bool) -> None:
    """Écrit (best-effort, comme l'index lui-même) le fichier d'indicateur de
    fraîcheur à côté de `index_par_acteur.json` : `derniere_construction_reussie`
    reflète l'issue de la tentative courante, `horodatage` son moment. N'est
    appelée en cas d'échec que lorsqu'un index existe déjà à préserver (issue
    #253) — pas d'indicateur de fraîcheur sans index à qualifier."""
    fraicheur_path = index_path.with_name(AMENDEMENTS_FRAICHEUR_FILENAME)
    try:
        with open(fraicheur_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "derniere_construction_reussie": reussi,
                    "horodatage": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                },
                f,
                ensure_ascii=False,
            )
    except OSError:
        pass


def amendements_index_deja_figee(legislature: str) -> bool:
    """True si le cache disque d'une législature figée
    (`AN_AMENDEMENTS_LEGISLATURES_FIGEES`) est déjà matérialisé
    (`index_par_acteur.json` présent + `fraicheur.json` portant `figee: true`),
    sans jamais charger `index_par_acteur.json` en mémoire pour le vérifier —
    seul `fraicheur.json` (quelques dizaines d'octets) est lu. Une législature
    figée ne change plus jamais une fois matérialisée : un appelant qui
    boucle sur plusieurs législatures (`build_amendements_index.py`) doit
    pouvoir sauter celles déjà figées sans recharger un index potentiellement
    volumineux (mesuré : 4,7 Go en clair pour la législature 16) juste pour
    confirmer sa présence — un run réel a déclenché l'OOM killer du système
    sur cette seule relecture, empêchant toute législature suivante d'être
    ne serait-ce que tentée (voir docs/technical_decisions.md
    #amendements-legislatures-figees)."""
    if legislature not in AN_AMENDEMENTS_LEGISLATURES_FIGEES:
        return False
    cache_dir = AMENDEMENTS_CACHE_DIR / legislature
    amendements_path = cache_dir / AMENDEMENTS_CACHE_AMENDEMENTS_FILENAME
    index_dir = cache_dir / AMENDEMENTS_CACHE_INDEX_PAR_ACTEUR_DIRNAME
    fraicheur_path = cache_dir / AMENDEMENTS_FRAICHEUR_FILENAME
    # `amendements.json` exigé aussi (#377), et le répertoire de tranches
    # depuis #392 : un cache écrit avant l'un ou l'autre de ces formats doit
    # être reconstruit, pas considéré comme déjà figé — sinon il resterait en
    # place indéfiniment sans jamais migrer.
    if not amendements_path.is_file() or not index_dir.is_dir() or not fraicheur_path.is_file():
        return False
    try:
        with open(fraicheur_path, encoding="utf-8") as f:
            fraicheur = json.load(f)
    except (json.JSONDecodeError, OSError):
        return False
    return bool(isinstance(fraicheur, dict) and fraicheur.get("figee"))


def _write_cached_amendements_agreges(
    legislature: str,
    amendements: dict[str, dict[str, Any]],
    index_par_acteur: dict[str, list[dict[str, Any]]],
) -> None:
    """Écrit (best-effort) le cache disque d'une législature sous forme
    dédupliquée : `amendements.json` + `index_par_acteur.json` (#377).

    Les deux fichiers sont écrits ensemble, `amendements.json` en premier :
    `_read_cached_amendements_agreges` exige les deux, donc une écriture
    interrompue entre les deux laisse un cache considéré comme absent
    (reconstruit au prochain run) plutôt qu'un couple incohérent. Écrase au
    passage un éventuel `index_par_acteur.json` plat hérité d'avant #377 —
    la migration d'un ancien cache est donc automatique et libère les
    plusieurs Go qu'il occupait."""
    cache_dir = AMENDEMENTS_CACHE_DIR / legislature
    cache_dir.mkdir(parents=True, exist_ok=True)
    with open(cache_dir / AMENDEMENTS_CACHE_AMENDEMENTS_FILENAME, "w", encoding="utf-8") as f:
        json.dump(amendements, f, ensure_ascii=False)

    # Une tranche par acteur (#392). Le répertoire est reconstruit de zéro :
    # un acteur disparu d'une reconstruction ne doit pas laisser sa tranche
    # périmée derrière lui. Écrit APRÈS amendements.json, et le répertoire
    # n'est considéré valide en lecture que s'il existe — une écriture
    # interrompue laisse donc un cache traité comme absent, jamais un cache
    # incohérent.
    index_dir = cache_dir / AMENDEMENTS_CACHE_INDEX_PAR_ACTEUR_DIRNAME
    shutil.rmtree(index_dir, ignore_errors=True)
    index_dir.mkdir(parents=True, exist_ok=True)
    for acteur_ref, refs in index_par_acteur.items():
        shard = _shard_path_acteur(legislature, acteur_ref)
        if shard is None:
            continue  # acteurRef hors forme attendue : ignoré plutôt qu'écrit
        with open(shard, "w", encoding="utf-8") as f:
            json.dump(refs, f, ensure_ascii=False)
    # Ancien fichier unique hérité (#377) : supprimé une fois les tranches en
    # place, pour libérer les centaines de Mo qu'il occupait.
    (cache_dir / AMENDEMENTS_CACHE_INDEX_PAR_ACTEUR_FILENAME_LEGACY).unlink(missing_ok=True)


def _load_frozen_amendement_index(legislature: str) -> Optional[dict[str, list[dict[str, Any]]]]:
    """Charge l'index amendements committé pour une législature figée
    (`AN_AMENDEMENTS_LEGISLATURES_FIGEES`), construit hors CI une fois pour
    toutes par `build_amendements_index_figees.py` sous forme dédupliquée et
    compressée gzip (`amendements.json.gz` + `index_par_acteur.json.gz`
    allégé, voir `_aggregate_amendements_index` — nécessaire pour rester sous
    la limite GitHub de 100 Mo par blob, voir la révision du 15/08/2026 de
    docs/technical_decisions.md#amendements-legislatures-figees), et le
    matérialise dans le cache disque (`AMENDEMENTS_CACHE_DIR`) en clair, sous
    la MEME forme dédupliquée (`amendements.json` + `index_par_acteur.json`,
    seule la compression change) — depuis #377, plus aucune expansion vers la
    forme plate n'a lieu ici : c'est elle qui faisait passer la législature 16
    de 210 Mo à 4,67 Go et déclenchait l'OOM killer. `fraicheur.json` est
    copié tel quel avec son marqueur `figee: true`.

    Retourne l'index compact acteurRef -> références (`{numero,
    role_signataire}`), ou `None` si le fallback committé est absent ou
    incomplet (ne devrait pas arriver pour une législature figée, mais ne
    lève jamais : l'appelant retombe alors sur le chemin réseau standard)."""
    frozen_dir = AN_AMENDEMENTS_FIGEES_DIR / legislature
    frozen_amendements_path = frozen_dir / AMENDEMENTS_FIGEES_AMENDEMENTS_FILENAME
    frozen_index_path = frozen_dir / AMENDEMENTS_FIGEES_INDEX_PAR_ACTEUR_FILENAME
    if not frozen_amendements_path.is_file() or not frozen_index_path.is_file():
        return None
    try:
        with gzip.open(frozen_amendements_path, "rt", encoding="utf-8") as f:
            amendements = json.load(f)
        with gzip.open(frozen_index_path, "rt", encoding="utf-8") as f:
            index_par_acteur = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    try:
        _write_cached_amendements_agreges(legislature, amendements, index_par_acteur)
        frozen_fraicheur_path = frozen_dir / AMENDEMENTS_FRAICHEUR_FILENAME
        if frozen_fraicheur_path.is_file():
            shutil.copyfile(
                frozen_fraicheur_path,
                AMENDEMENTS_CACHE_DIR / legislature / AMENDEMENTS_FRAICHEUR_FILENAME,
            )
    except OSError:
        pass

    return index_par_acteur


def _parse_amendements_zip(zip_path: Path) -> dict[str, list[dict[str, Any]]]:
    """Parse une archive amendements AN déjà téléchargée en index acteurRef ->
    liste d'amendements (extrait de `_download_and_build_amendement_index`
    pour être réutilisable par `build_amendements_index_figees.py`, qui parse
    une archive téléchargée manuellement hors CI). Lève `zipfile.BadZipFile`
    si l'archive est invalide — laissé à l'appelant à traiter.

    Détecte le schéma de chaque entrée par sa clé racine : `"amendement"`
    (schéma 15/16/17, un amendement par entrée) ou `"textesEtAmendements"`
    (schéma legacy légis 14, une seule entrée regroupant tous les
    texteleg/amendements — voir issue #299). Un schéma ni l'un ni l'autre
    produit toujours un index vide pour cette entrée, mais avec un warning
    explicite au lieu d'un échec silencieux."""
    index: dict[str, list[dict[str, Any]]] = {}
    with zipfile.ZipFile(zip_path) as zf:
        noms = [n for n in zf.namelist() if n.endswith(".json")]
        for nom in noms:
            try:
                with zf.open(nom) as f:
                    data = json.load(f)
            except (json.JSONDecodeError, KeyError):
                continue

            if isinstance(data, dict) and "amendement" in data:
                parsed_entries = _parse_amendement_entry(data)
            elif isinstance(data, dict) and "textesEtAmendements" in data:
                parsed_entries = _parse_amendement_entry_legacy(data)
            else:
                print(
                    f"  [!] Entrée '{nom}' au format inconnu (ni 'amendement' ni "
                    "'textesEtAmendements'), ignorée",
                    file=sys.stderr,
                )
                continue

            if parsed_entries is None:
                continue
            for acteur_ref, record in parsed_entries:
                index.setdefault(acteur_ref, []).append(record)
    return index


def _aggregate_amendements_index(
    index: dict[str, list[dict[str, Any]]],
) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    """Compacte un index acteurRef -> amendements (format `_parse_amendements_zip`)
    pour le committer sans duplication, pour une législature figée
    (`build_amendements_index_figees.py`).

    `_parse_amendement_entry` construit un enregistrement par signataire
    (auteur + chaque cosignataire), chacun portant sa propre copie complète du
    même amendement — `co_signataires` compris. Pour un amendement à N
    cosignataires, le même contenu est donc dupliqué N+1 fois dans `index`
    (mesuré : 3,86 Go décompressés pour la législature 16, committable
    uniquement une fois dédupliqué — voir la révision de
    docs/technical_decisions.md#amendements-legislatures-figees).

    Retourne (amendements, index_par_acteur) :
    - `amendements` : chaque amendement stocké une seule fois, sous la clé
      `numero` (identifiant stable, partagé par toutes les copies d'un même
      amendement en entrée puisqu'elles dérivent du même `record_base`).
    - `index_par_acteur` : acteurRef -> liste de `{numero, role_signataire}`,
      une référence légère vers `amendements` au lieu d'une copie complète.

    Les enregistrements sans `numero` (non observés en pratique, mais pas
    exclus par le schéma AN) reçoivent une clé synthétique non partagée pour
    ne jamais être perdus ni dédupliqués à tort avec un autre amendement.
    Inverse : `_expand_aggregated_amendements_index`.
    """
    amendements: dict[str, dict[str, Any]] = {}
    index_par_acteur: dict[str, list[dict[str, Any]]] = {}
    sans_numero_compteur = 0

    for acteur_ref, records in index.items():
        refs: list[dict[str, Any]] = []
        for record in records:
            numero = record.get("numero")
            if not numero:
                numero = f"_sans_numero_{sans_numero_compteur}"
                sans_numero_compteur += 1
            refs.append({"numero": numero, "role_signataire": record.get("role_signataire")})
            if numero not in amendements:
                amendements[numero] = {k: v for k, v in record.items() if k != "role_signataire"}
        index_par_acteur[acteur_ref] = refs

    return amendements, index_par_acteur


def _expand_aggregated_amendements_index(
    amendements: dict[str, dict[str, Any]],
    index_par_acteur: dict[str, list[dict[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    """Inverse de `_aggregate_amendements_index` : reconstruit la forme plate
    acteurRef -> amendements (avec le contenu de chaque amendement à nouveau
    dupliqué par entrée, `role_signataire` réinjecté) attendue par le reste du
    pipeline — `fetch_amendements_officiels` lit exclusivement cette forme
    depuis le cache disque standard, quelle que soit l'origine (réseau ou
    fallback figé). Une référence dont le `numero` est absent de `amendements`
    (ne devrait pas arriver, les deux fichiers étant committés ensemble) est
    ignorée plutôt que de lever."""
    expanded: dict[str, list[dict[str, Any]]] = {}
    for acteur_ref, refs in index_par_acteur.items():
        entries: list[dict[str, Any]] = []
        for ref in refs:
            base = amendements.get(ref.get("numero"))
            if base is None:
                continue
            entries.append({**base, "role_signataire": ref.get("role_signataire")})
        expanded[acteur_ref] = entries
    return expanded


def _download_and_build_amendement_index(legislature: str) -> dict[str, list[dict[str, Any]]]:
    """Télécharge l'archive AN et construit (en la mettant en cache sur disque) un
    index acteurRef -> liste d'amendements. Reprend telle quelle la logique réseau
    précédemment inline dans l'ex-`_build_acteur_amendement_index` (issue #250).

    Seul point d'entrée réseau restant pour les amendements officiels, appelé
    exclusivement par le job CI dédié `extract-amendements-an`
    (`src/build_amendements_index.py`, #251) : `fetch_amendements_officiels`
    ne l'appelle plus depuis #252 (sous-issue 4/6 de #248), elle lit
    uniquement `_read_cached_amendements_acteur`.

    Pour une législature figée (`AN_AMENDEMENTS_LEGISLATURES_FIGEES`), aucun
    appel réseau n'a lieu : l'index committé est chargé par
    `_load_frozen_amendement_index` (voir aussi
    `docs/technical_decisions.md#amendements-legislatures-figees`).

    Contrairement à `_build_acteur_vote_index`, les ~120k fichiers individuels de
    l'archive ne sont jamais extraits sur disque (uniquement lus en mémoire un par
    un depuis le zip) : seul l'index final (acteurRef -> amendements) est mis en
    cache, pour éviter d'écrire des dizaines de milliers de petits fichiers.
    L'archive téléchargée elle-même est supprimée en fin de tentative, succès
    comme échec (#264) : elle n'est jamais relue ensuite, et la conserver
    gonflait l'artifact et le cache partagé de 283-618 Mo par législature.
    Thread-safe (verrou par législature), même principe que pour les scrutins.

    Lève `AmendementsIndexError` en cas d'échec de téléchargement ou de parsing de
    l'archive (au lieu de retourner un {} indiscernable d'un index vide légitime),
    pour que l'appelant puisse le distinguer et le tracer.

    Un échec définitif (tentatives épuisées) est mémorisé à la fois en mémoire
    process (`_amendements_failed_legislatures`, #239) et sur un marqueur disque
    partagé entre jobs CI du même run (`_mark_amendements_legislature_failed`,
    #246) : les candidats suivants du même job, ou le premier candidat d'un job
    CI suivant (ex. `extract-roster-groupes` après `extract-an`) ayant besoin de
    la même législature durant ce run, lèvent immédiatement
    `AmendementsIndexError` sans nouvelle tentative réseau.

    Un index déjà en cache n'est jamais écrasé par un échec (`index_path` n'est
    ouvert en écriture qu'après succès complet du téléchargement et du parsing
    ci-dessous) : un échec définitif laisse le fichier existant tel quel, s'il y
    en a un (issue #253). Un indicateur de fraîcheur (`fraicheur.json`, voir
    `_write_amendements_fraicheur`) est écrit à côté de l'index à chaque
    tentative qui en concerne un — succès (index remplacé) ou échec définitif
    sur un index préexistant conservé — pour qu'un futur consommateur puisse
    distinguer les deux.
    """
    with _get_amendements_lock(legislature):
        cache_dir = AMENDEMENTS_CACHE_DIR / legislature
        index_dir = cache_dir / AMENDEMENTS_CACHE_INDEX_PAR_ACTEUR_DIRNAME
        amendements_path = cache_dir / AMENDEMENTS_CACHE_AMENDEMENTS_FILENAME
        index_path = cache_dir / AMENDEMENTS_CACHE_INDEX_PAR_ACTEUR_FILENAME_LEGACY
        # Cache-hit : la liste des acteurs indexés se déduit des NOMS des
        # tranches, sans en ouvrir aucune (#392). Le seul consommateur de
        # cette valeur de retour en fait `len()` (build_amendements_index.py),
        # d'où des listes vides en valeurs : matérialiser le contenu coûterait
        # des centaines de Mo pour une information dont personne ne se sert.
        if amendements_path.is_file() and index_dir.is_dir():
            try:
                return {p.stem: [] for p in index_dir.glob("*.json")}
            except OSError:
                pass  # cache illisible : on reconstruit

        if legislature in AN_AMENDEMENTS_LEGISLATURES_FIGEES:
            frozen_index = _load_frozen_amendement_index(legislature)
            if frozen_index is not None:
                return frozen_index

        if _amendements_legislature_failed_this_run(legislature):
            if index_path.is_file():
                _write_amendements_fraicheur(index_path, reussi=False)
            raise AmendementsIndexError(
                f"téléchargement déjà en échec pour la législature {legislature} durant ce run (non retenté)"
            )

        url = _amendements_zip_url(legislature)
        if not url:
            return {}

        print(f"-> Téléchargement des amendements officiels (Assemblée nationale) : {url}")
        zip_path = AMENDEMENTS_CACHE_DIR / legislature / "amendements.zip"
        # try/finally (#264) : l'archive brute (283-618 Mo selon la
        # législature) n'a plus aucune utilité une fois l'index construit —
        # elle n'est jamais relue, ni par la lecture cache-only
        # (`_read_cached_amendements_acteur`), ni pour reprendre un
        # téléchargement entre deux tentatives (`_download_amendements_zip`
        # réécrit toujours depuis zéro). La conserver gonflait l'artifact
        # `amendements-index-an` et le cache hebdomadaire partagé
        # `public-data-cache-an-*` d'autant, pour rien. Supprimée dans TOUS
        # les cas (succès, échec réseau, archive invalide) : un fichier
        # partiel ou invalide n'a pas plus d'utilité qu'une archive
        # correctement parsée.
        try:
            try:
                _download_amendements_zip(url, zip_path, legislature)
            except (requests.RequestException, OSError) as exc:
                print(f"  [!] Échec du téléchargement des amendements officiels : {exc}")
                _mark_amendements_legislature_failed(legislature)
                if index_path.is_file():
                    _write_amendements_fraicheur(index_path, reussi=False)
                raise AmendementsIndexError(f"échec du téléchargement ({exc})") from exc

            try:
                index = _parse_amendements_zip(zip_path)
            except zipfile.BadZipFile as exc:
                print(f"  [!] Archive d'amendements invalide : {exc}")
                _mark_amendements_legislature_failed(legislature)
                if index_path.is_file():
                    _write_amendements_fraicheur(index_path, reussi=False)
                raise AmendementsIndexError(f"archive invalide ({exc})") from exc
        finally:
            try:
                zip_path.unlink(missing_ok=True)
            except OSError:
                pass  # best-effort, comme l'écriture du cache elle-même

        # Déduplication avant écriture (#377) : `_parse_amendements_zip`
        # produit un enregistrement complet par signataire, donc N+1 copies du
        # même amendement pour N cosignataires. Écrire cette forme plate telle
        # quelle produisait un cache de plusieurs Go, relu intégralement par
        # candidat côté `fetch_amendements_officiels` — cause de l'OOM
        # documenté dans #oom-lecture-amendements-par-candidat.
        amendements_dedup, index_par_acteur = _aggregate_amendements_index(index)
        try:
            _write_cached_amendements_agreges(legislature, amendements_dedup, index_par_acteur)
            _write_amendements_fraicheur(index_path, reussi=True)
        except OSError:
            pass

        return index_par_acteur


def _collect_texte_codes(node: Any, codes: set[str]) -> None:
    """Parcourt récursivement un dossier législatif brut et collecte tous les
    codes de texte référencés (clés `texteAssocie`/`refTexteAssocie`), à
    n'importe quel niveau de l'arbre `actesLegislatifs` (récursif, profondeur
    variable selon le dossier)."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key in ("texteAssocie", "refTexteAssocie") and isinstance(value, str):
                codes.add(value)
            else:
                _collect_texte_codes(value, codes)
    elif isinstance(node, list):
        for item in node:
            _collect_texte_codes(item, codes)


def _build_texte_titre_index() -> dict[str, str]:
    """Construit (et met en cache sur disque) un index code de texte -> titre
    lisible du dossier, à partir du jeu de données bulk des dossiers
    législatifs (un seul fichier, déjà multi-législatures). Utilisé pour
    résoudre `texte_vise` des amendements (sinon un simple code source, ex.
    "PIONANR5L17B0904"). Non-fatal en cas d'échec (retourne {})."""
    with _DOSSIERS_TITRE_LOCK:
        # Suffixe de version (#400) : le passage au multi-archives change le
        # contenu de l'index. Sans nouveau nom, un cache CI ou local existant
        # servirait silencieusement l'ancien index mono-archive, et le gain
        # serait invisible sans que rien ne le signale.
        index_path = DOSSIERS_CACHE_DIR / "index_texte_titre_v2.json"
        if index_path.is_file():
            try:
                with open(index_path, encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass  # cache corrompu : on reconstruit

        archives = ensure_dossiers_zips_downloaded()
        if not archives:
            return {}

        index: dict[str, str] = {}
        # Multi-archives dédupliqué par uid (#400) : la législature la plus
        # élevée fait foi pour un dossier présent dans plusieurs archives.
        for _legislature, dossier in iter_dossiers_bruts(archives):
            titre = (dossier.get("titreDossier") or {}).get("titre")
            if not titre:
                continue
            codes: set[str] = set()
            _collect_texte_codes(dossier, codes)
            for code in codes:
                index[code] = titre

        try:
            index_path.parent.mkdir(parents=True, exist_ok=True)
            with open(index_path, "w", encoding="utf-8") as f:
                json.dump(index, f, ensure_ascii=False)
        except OSError:
            pass

        return index


# Stades procéduraux, du moins au plus avancé : sert à déterminer le stade le
# plus avancé réellement atteint par un dossier (un seul stade par dossier,
# pas par acte).
_STADE_RANKS = {
    "depose": 1,
    "examine_commission": 2,
    "discute_seance": 3,
    "adopte": 4,
    "promulgue": 5,
}


def _stade_from_code_acte(code_acte: Optional[str], statut_libelle: Optional[str]) -> Optional[str]:
    """Déduit un stade procédural (nomenclature du schéma pivot) à partir du
    code d'acte officiel (`codeActe`) d'un dossier législatif. Volontairement
    conservateur : ne retient que des signaux non ambigus (voir
    docs/an_opendata.md, section dossiers législatifs)."""
    if not code_acte:
        return None
    if "PROM" in code_acte:
        return "promulgue"
    if code_acte.endswith("-DEBATS-DEC"):
        if statut_libelle and statut_libelle.strip().lower().startswith("adopt"):
            return "adopte"
        return "discute_seance"
    if "DEBATS" in code_acte:
        return "discute_seance"
    if "COM" in code_acte:
        return "examine_commission"
    if "DEPOT" in code_acte:
        return "depose"
    return None


def _collect_initiateurs(dossier: dict, acteur_roles: dict[str, tuple[str, Optional[str]]]) -> None:
    """Ajoute à `acteur_roles` chaque acteur cité comme initiateur (auteur) du
    dossier (`initiateur.acteurs.acteur`, dict unique ou liste selon les cas)."""
    initiateur = dossier.get("initiateur")
    if not isinstance(initiateur, dict):
        return
    acteurs = (initiateur.get("acteurs") or {}).get("acteur")
    items = acteurs if isinstance(acteurs, list) else [acteurs]
    for item in items:
        if isinstance(item, dict):
            acteur_ref = item.get("acteurRef")
            if isinstance(acteur_ref, str) and acteur_ref:
                acteur_roles.setdefault(acteur_ref, ("auteur", None))


def _collect_dossier_facts(
    node: Any,
    acteur_roles: dict[str, tuple[str, Optional[str]]],
    dates: list[str],
    stades: list[str],
) -> None:
    """Parcourt récursivement l'arbre `actesLegislatifs` d'un dossier et
    collecte : le rôle factuel de chaque rapporteur (`rapporteurs`, plusieurs
    rapporteurs sur un même acte -> "co-rapporteur"), les dates d'acte
    (`dateActe`) et les stades procéduraux atteints (`codeActe`/`statutConclusion`)."""
    if isinstance(node, dict):
        date_acte = node.get("dateActe")
        if isinstance(date_acte, str) and date_acte:
            dates.append(date_acte[:10])

        code_acte = node.get("codeActe")
        if isinstance(code_acte, str):
            statut = node.get("statutConclusion")
            statut_libelle = statut.get("libelle") if isinstance(statut, dict) else None
            stade = _stade_from_code_acte(code_acte, statut_libelle)
            if stade:
                stades.append(stade)

        rapporteurs = node.get("rapporteurs")
        if isinstance(rapporteurs, dict):
            entries = rapporteurs.get("rapporteur")
            items = [it for it in (entries if isinstance(entries, list) else [entries]) if isinstance(it, dict)]
            role = "co-rapporteur" if len(items) > 1 else "rapporteur"
            for item in items:
                acteur_ref = item.get("acteurRef")
                if isinstance(acteur_ref, str) and acteur_ref:
                    type_rapport = TYPE_RAPPORTEUR_MAP.get((item.get("typeRapporteur") or "").strip().lower())
                    acteur_roles.setdefault(acteur_ref, (role, type_rapport))

        for key, value in node.items():
            if key != "rapporteurs":
                _collect_dossier_facts(value, acteur_roles, dates, stades)
    elif isinstance(node, list):
        for item in node:
            _collect_dossier_facts(item, acteur_roles, dates, stades)


def _collect_acteur_roles(dossier: dict) -> tuple[dict[str, tuple[str, Optional[str]]], Optional[str], Optional[str], Optional[str]]:
    """Combine initiateurs et rapporteurs d'un dossier en un seul mapping
    acteurRef -> (role, type_rapport), et calcule le stade procédural le plus
    avancé et les dates min/max de l'ensemble du dossier."""
    acteur_roles: dict[str, tuple[str, Optional[str]]] = {}
    _collect_initiateurs(dossier, acteur_roles)
    dates: list[str] = []
    stades: list[str] = []
    _collect_dossier_facts(dossier.get("actesLegislatifs"), acteur_roles, dates, stades)
    date_min = min(dates) if dates else None
    date_max = max(dates) if dates else None
    stade = max(stades, key=lambda s: _STADE_RANKS[s]) if stades else None
    return acteur_roles, stade, date_min, date_max


def _build_acteur_textes_portes_index() -> dict[str, list[dict[str, Any]]]:
    """Construit (et met en cache sur disque) un index acteurRef -> liste de
    dossiers législatifs où l'acteur a un rôle factuel connu (auteur,
    rapporteur ou co-rapporteur), à partir du jeu de données bulk des dossiers
    législatifs (même archive que `_build_texte_titre_index`).

    Contrairement à la liste NosDéputés (voir `fetch_dossiers_for_legislatures`),
    qui renvoie l'intégralité des dossiers d'une législature identiquement pour
    tous les élus (role toujours null, voir docs/an_opendata.md), cet index est
    réellement propre à chaque acteur. Non-fatal en cas d'échec (retourne {})."""
    with _DOSSIERS_TEXTES_PORTES_LOCK:
        index_path = DOSSIERS_CACHE_DIR / "index_acteur_textes_v2.json"  # cf. #400
        if index_path.is_file():
            try:
                with open(index_path, encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass  # cache corrompu : on reconstruit

        archives = ensure_dossiers_zips_downloaded()
        if not archives:
            return {}

        index: dict[str, list[dict[str, Any]]] = {}
        # Multi-archives dédupliqué par uid (#400) : sans déduplication, un
        # dossier présent dans deux archives serait compté deux fois dans les
        # textes portés de chaque acteur.
        for _legislature, dossier in iter_dossiers_bruts(archives):
            titre_dossier = dossier.get("titreDossier") or {}
            titre = titre_dossier.get("titre")
            titre_chemin = titre_dossier.get("titreChemin")
            if not titre:
                continue
            acteur_roles, stade, date_min, date_max = _collect_acteur_roles(dossier)
            if not acteur_roles:
                continue
            legislature = dossier.get("legislature")
            source_url = (
                f"https://www.assemblee-nationale.fr/dyn/{legislature}/dossiers/{titre_chemin}"
                if legislature and titre_chemin else None
            )
            for acteur_ref, (role, type_rapport) in acteur_roles.items():
                index.setdefault(acteur_ref, []).append({
                    "id": dossier.get("uid"),
                    "titre": titre,
                    "role": role,
                    "type_rapport": type_rapport,
                    "stade_procedural": stade,
                    "date_min": date_min,
                    "date_max": date_max,
                    "legislature": legislature,
                    "source_url": source_url,
                })

        try:
            index_path.parent.mkdir(parents=True, exist_ok=True)
            with open(index_path, "w", encoding="utf-8") as f:
                json.dump(index, f, ensure_ascii=False)
        except OSError:
            pass

        return index


def fetch_textes_portes_officiels(url_an_ou_senat: Optional[str]) -> list[dict[str, Any]]:
    """Récupère les dossiers législatifs où l'élu a un rôle factuel connu
    (auteur, rapporteur ou co-rapporteur), depuis le jeu de données officiel
    des dossiers législatifs (Assemblée nationale). Remplace la liste NosDéputés
    (voir `fetch_dossiers_for_legislatures`), qui n'est pas propre à l'élu."""
    acteur_ref = _extract_acteur_ref(url_an_ou_senat)
    if not acteur_ref:
        return []
    index = _build_acteur_textes_portes_index()
    entries = index.get(acteur_ref, [])
    return sorted(entries, key=lambda t: (t.get("date_max") or "", t.get("titre") or ""), reverse=True)


def _format_lieu_naissance(ville: Optional[str], departement: Optional[str], pays: Optional[str]) -> Optional[str]:
    """Formate ville/département/pays de naissance en un texte lisible.

    Le département n'est pertinent que pour une naissance en France : pour un
    pays étranger, on l'omet au profit du pays (ex. "Alger (Algérie)" plutôt
    que d'ignorer l'information géographique disponible).
    """
    if pays and pays != "France":
        complement = pays
    else:
        complement = departement
    if ville and complement:
        return f"{ville} ({complement})"
    return ville or complement or None


_CONTACT_TYPE_LIBELLE_MAP: dict[str, str] = {
    "Mèl": "email",
    "Twitter": "twitter",
    "Facebook": "facebook",
    "Site internet": "site_web",
}


def _extract_contact(adresses: list[Any]) -> dict[str, Optional[str]]:
    """Extrait les coordonnées de contact publiques (email, Twitter, Facebook,
    site web) depuis `acteur.adresses.adresse[]`. Ignore volontairement les
    autres types présents dans ce bloc (adresses postales, téléphone,
    Instagram, Linkedin...) — hors périmètre de cette extraction."""
    contact: dict[str, Optional[str]] = {key: None for key in _CONTACT_TYPE_LIBELLE_MAP.values()}
    for adresse in adresses:
        if not isinstance(adresse, dict):
            continue
        key = _CONTACT_TYPE_LIBELLE_MAP.get(adresse.get("typeLibelle"))
        if key and not contact[key]:
            contact[key] = adresse.get("valElec")
    return contact


def _format_nom_complet(prenom: Optional[str], nom: Optional[str]) -> Optional[str]:
    """Formate prénom/nom (etatCivil.ident) en un nom complet lisible."""
    if prenom and nom:
        return f"{prenom} {nom}"
    return prenom or nom or None


def _select_mandat_par_type_courant(mandats: list[Any], type_organe: str) -> Optional[dict[str, Any]]:
    """Sélectionne, parmi les mandats d'un acteur dont `typeOrgane ==
    type_organe`, celui correspondant à la période la plus pertinente : le
    mandat en cours (`dateFin` absent) s'il en existe un, sinon celui dont
    `dateDebut` est le plus récent (mandat terminé). Généralisé (issue #369)
    à partir de la logique déjà en place pour `typeOrgane == "ASSEMBLEE"`
    (voir `_select_mandat_assemblee_courant`) — même besoin pour `"GP"`
    (groupe politique actuel, quand plusieurs périodes d'appartenance
    successives existent)."""
    best: Optional[dict[str, Any]] = None
    for mandat in mandats:
        if not isinstance(mandat, dict) or mandat.get("typeOrgane") != type_organe:
            continue
        if best is None:
            best = mandat
            continue
        best_en_cours = best.get("dateFin") is None
        mandat_en_cours = mandat.get("dateFin") is None
        if mandat_en_cours and not best_en_cours:
            best = mandat
        elif mandat_en_cours == best_en_cours and (mandat.get("dateDebut") or "") > (best.get("dateDebut") or ""):
            best = mandat
    return best


def _select_mandat_assemblee_courant(mandats: list[Any]) -> Optional[dict[str, Any]]:
    """Sélectionne, parmi les mandats `typeOrgane == "ASSEMBLEE"` d'un acteur,
    celui correspondant à l'élection la plus pertinente pour la circonscription/
    place hémicycle à afficher. Nécessaire depuis le passage à
    `AN_ACTEURS_HISTORIQUE_ZIP_URL` (issue #354) : contrairement à l'ancien
    jeu de données `AMO10` (limité aux mandats actifs, un seul mandat
    ASSEMBLEE possible par acteur), un acteur peut désormais avoir plusieurs
    mandats ASSEMBLEE successifs (réélections sur plusieurs législatures).
    Voir `_select_mandat_par_type_courant` pour la logique de sélection."""
    return _select_mandat_par_type_courant(mandats, "ASSEMBLEE")


def _build_acteur_identite_index() -> dict[str, dict[str, Any]]:
    """Construit (et met en cache sur disque) un index acteurRef -> champs
    d'identité (nom complet, profession, date/lieu de naissance, lien HATVP,
    contact, circonscription, place hémicycle, groupe politique actuel,
    dates/nombre de mandats), à partir du jeu de données bulk historique des
    acteurs de l'Assemblée nationale (`AN_ACTEURS_HISTORIQUE_ZIP_URL`,
    partagé avec `_build_organe_index` / `_build_acteur_positions_hemicycle_index`
    via `_ensure_acteurs_historique_zip_downloaded`).

    `groupe_sigle`/`groupe_nom` (issue #369) proviennent du mandat `typeOrgane
    == "GP"` le plus actuel (voir `_select_mandat_par_type_courant`), résolu
    en sigle/nom lisible via `_build_organe_index` (#353) — nécessaire pour
    que ce référentiel puisse remplacer NosDéputés en source primaire
    d'identité sans perdre le groupe politique déclaré.

    Couvre tous les élu⋅e⋅s référencés depuis la XIe législature, actifs ou
    non (issue #354) — contrairement à l'ancien jeu de données `AMO10`
    ("deputes_actifs_mandats_actifs_organes"), limité aux ~577 député⋅e⋅s
    actifs de la législature en cours. Voir docs/technical_decisions.md pour
    le choix de réutiliser ce zip déjà exploité par #353 plutôt que combiner
    les archives `AMO20` par législature comme envisagé initialement dans
    l'issue.

    Circonscription et place hémicycle proviennent du mandat le plus pertinent
    parmi ceux `typeOrgane == "ASSEMBLEE"` (voir _select_mandat_assemblee_courant) :
    `election.lieu.numDepartement/numCirco` et `mandature.placeHemicycle`.

    Non-fatal en cas d'échec (retourne {})."""
    with _ACTEURS_IDENTITE_LOCK:
        index_path = ACTEURS_HISTORIQUE_CACHE_DIR / "index_identite.json"
        if index_path.is_file():
            try:
                with open(index_path, encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass  # cache corrompu : on reconstruit

        zip_path = _ensure_acteurs_historique_zip_downloaded()
        if zip_path is None:
            return {}

        # Résolution du groupe politique actuel (organeRef -> sigle/nom, #353)
        # depuis le même zip déjà en cache disque après le premier appel —
        # aucun nouveau téléchargement (issue #369, voir aussi
        # _select_mandat_par_type_courant ci-dessus).
        organe_index = _build_organe_index()

        index: dict[str, dict[str, Any]] = {}
        try:
            with zipfile.ZipFile(zip_path) as zf:
                noms = [n for n in zf.namelist() if n.startswith("json/acteur/") and n.endswith(".json")]
                for nom in noms:
                    try:
                        with zf.open(nom) as f:
                            data = json.load(f)
                    except (json.JSONDecodeError, KeyError):
                        continue
                    acteur = data.get("acteur") if isinstance(data, dict) else None
                    if not isinstance(acteur, dict):
                        continue
                    uid = acteur.get("uid")
                    acteur_ref = uid.get("#text") if isinstance(uid, dict) else uid
                    if not isinstance(acteur_ref, str) or not acteur_ref:
                        continue

                    etat_civil = acteur.get("etatCivil") or {}
                    ident = etat_civil.get("ident") or {}
                    info_naissance = etat_civil.get("infoNaissance") or {}
                    profession = (acteur.get("profession") or {}).get("libelleCourant")

                    adresses = (acteur.get("adresses") or {}).get("adresse")
                    if isinstance(adresses, dict):
                        adresses = [adresses]
                    contact = _extract_contact(adresses if isinstance(adresses, list) else [])

                    mandats = (acteur.get("mandats") or {}).get("mandat")
                    if isinstance(mandats, dict):
                        mandats = [mandats]
                    mandats = mandats if isinstance(mandats, list) else []

                    numero_departement = numero_circo = place_hemicycle = None
                    mandat_debut = mandat_fin = None
                    mandat_assemblee = _select_mandat_assemblee_courant(mandats)
                    if mandat_assemblee is not None:
                        lieu = (mandat_assemblee.get("election") or {}).get("lieu") or {}
                        numero_departement = lieu.get("numDepartement")
                        numero_circo = lieu.get("numCirco")
                        place_hemicycle = (mandat_assemblee.get("mandature") or {}).get("placeHemicycle")
                        mandat_debut = mandat_assemblee.get("dateDebut")
                        mandat_fin = mandat_assemblee.get("dateFin")
                    nb_mandats = sum(1 for m in mandats if isinstance(m, dict) and m.get("typeOrgane") == "ASSEMBLEE")

                    # Groupe politique actuel (#369) : sans ça, le seul champ
                    # groupe_sigle/groupe_nom du profil resterait NosDéputés
                    # uniquement, empêchant de rendre fetch_identity
                    # conditionnel (étape 4 de #369) sans perdre cette donnée.
                    groupe_sigle = groupe_nom = None
                    mandat_gp = _select_mandat_par_type_courant(mandats, "GP")
                    if mandat_gp is not None:
                        organe_gp = organe_index.get((mandat_gp.get("organes") or {}).get("organeRef") or "")
                        if organe_gp:
                            groupe_sigle = organe_gp.get("sigle")
                            groupe_nom = organe_gp.get("nom")

                    index[acteur_ref] = {
                        "civilite": ident.get("civ"),
                        "prenom": ident.get("prenom"),
                        "nom": ident.get("nom"),
                        "nom_complet": _format_nom_complet(ident.get("prenom"), ident.get("nom")),
                        "profession": profession,
                        "groupe_sigle": groupe_sigle,
                        "groupe_nom": groupe_nom,
                        "mandat_debut": mandat_debut,
                        "mandat_fin": mandat_fin,
                        "nb_mandats": nb_mandats,
                        "date_naissance": info_naissance.get("dateNais"),
                        "lieu_naissance": _format_lieu_naissance(
                            info_naissance.get("villeNais"),
                            info_naissance.get("depNais"),
                            info_naissance.get("paysNais"),
                        ),
                        "uri_hatvp": acteur.get("uri_hatvp"),
                        "contact": contact,
                        "numero_departement": numero_departement,
                        "numero_circo": numero_circo,
                        "place_hemicycle": place_hemicycle,
                    }
        except zipfile.BadZipFile as exc:
            print(f"  [!] Archive de l'historique des acteurs invalide : {exc}")
            return {}

        try:
            index_path.parent.mkdir(parents=True, exist_ok=True)
            with open(index_path, "w", encoding="utf-8") as f:
                json.dump(index, f, ensure_ascii=False)
        except OSError:
            pass

        return index


def fetch_identite_officielle(url_an_ou_senat: Optional[str]) -> Optional[dict[str, Any]]:
    """Récupère les champs d'identité officiels (Assemblée nationale) pour un
    député, actif ou non (voir _build_acteur_identite_index, issue #354).
    Retourne None si non trouvé/non applicable (ex. sénateur, ou acteur absent
    du référentiel historique de l'AN)."""
    acteur_ref = _extract_acteur_ref(url_an_ou_senat)
    if not acteur_ref:
        return None
    index = _build_acteur_identite_index()
    return index.get(acteur_ref)


def _build_acteur_nom_index() -> dict[str, list[str]]:
    """Index nom complet normalisé (sans accents/casse, voir
    _normalize_search_query) -> liste des acteur_ref partageant ce nom, à
    partir de `_build_acteur_identite_index`. Permet de résoudre un acteur_ref
    depuis un slug NosDéputés.fr sans dépendre de l'URL AN renvoyée par
    NosDéputés (voir fetch_identite_officielle_par_slug, issue #355). Une
    liste de plus d'un acteur_ref pour une même clé signale une homonymie
    dans le référentiel historique AN.

    Les tirets de `nom_complet` sont remplacés par des espaces avant
    normalisation, au même titre que ceux du slug côté appelant
    (`_resolve_acteur_ref_par_slug`) : un prénom composé (ex. "Jean-Luc"
    Mélenchon) garde son tiret dans `nom_complet` mais le slug NosDéputés.fr
    ("jean-luc-melenchon") le remplace par un espace au même titre que le
    séparateur prénom/nom — sans ce traitement symétrique, la clé normalisée
    ne matche jamais ("jean-luc melenchon" vs "jean luc melenchon"), et la
    résolution échoue silencieusement pour tout prénom/nom composé."""
    index: dict[str, list[str]] = {}
    for acteur_ref, fiche in _build_acteur_identite_index().items():
        nom_complet = fiche.get("nom_complet")
        if not nom_complet:
            continue
        cle = _normalize_search_query(nom_complet.replace("-", " "))
        index.setdefault(cle, []).append(acteur_ref)
    return index


def _resolve_acteur_ref_par_slug(slug: str) -> Optional[str]:
    """Résout un acteur_ref AN (ex. "PA2150") directement depuis un slug
    NosDéputés.fr (ex. "jean-luc-melenchon" -> nom normalisé "jean luc
    melenchon"), par correspondance de nom sur `_build_acteur_nom_index` —
    sans appel réseau préalable à NosDéputés pour en extraire l'URL AN.
    Renvoie None si le slug ne correspond à aucun acteur du référentiel, ou à
    plusieurs (homonymie : on renonce plutôt que de risquer une mauvaise
    attribution)."""
    nom_index = _build_acteur_nom_index()
    matches = nom_index.get(_normalize_search_query(slug.replace("-", " ")))
    if not matches or len(matches) != 1:
        return None
    return matches[0]


def fetch_identite_officielle_par_slug(slug: str) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    """Résout l'identité officielle AN directement depuis le slug NosDéputés.fr,
    sans appel réseau préalable à NosDéputés pour en extraire l'URL AN —
    permet d'utiliser le référentiel historique AN comme source primaire de
    `fetch_identity` pour les députés (issue #355). Renvoie (fiche, acteur_ref)
    si trouvé, (None, None) sinon (absent du référentiel, ou homonymie — voir
    _resolve_acteur_ref_par_slug)."""
    acteur_ref = _resolve_acteur_ref_par_slug(slug)
    if not acteur_ref:
        return None, None
    return _build_acteur_identite_index().get(acteur_ref), acteur_ref


def _acteur_ref_to_pseudo_url(acteur_ref: str) -> str:
    """Construit une URL de fiche AN synthétique à partir d'un acteur_ref
    (ex. "PA2150"), au même format que le champ `url_an` renvoyé par
    NosDéputés (ex. "https://www2.assemblee-nationale.fr/deputes/fiche/OMC_PA2150").
    Utilisée quand l'identité a été résolue via l'AN sans passer par
    NosDéputés (voir fetch_identite_officielle_par_slug) : les autres appels
    officiels AN (votes, amendements, textes, questions, positions hémicycle,
    interventions) n'ont besoin que d'en extraire l'acteur_ref via
    _extract_acteur_ref, peu importe la forme exacte de l'URL."""
    return f"https://www2.assemblee-nationale.fr/deputes/fiche/OMC_{acteur_ref}"


# Correspondance organe.positionPolitique (référentiel officiel Assemblée
# nationale) -> valeur du schéma pivot.
_POSITION_POLITIQUE_MAP: dict[str, str] = {
    "Majoritaire": "majorite",
    "Minoritaire": "minoritaire",
    "Opposition": "opposition",
}


def _build_organe_positions_index(zf: zipfile.ZipFile) -> dict[str, dict[str, Any]]:
    """Construit un index organeRef -> {groupe_sigle, position} à partir des
    organes de type "GP" (groupe politique) et "GOUVERNEMENT" (fonction
    ministérielle) du zip acteurs historique.

    Pour un organe "GP", ne conserve que ceux dont positionPolitique est
    qualifié par l'AN (jamais le cas pour la législature en cours, voir
    AN_ACTEURS_HISTORIQUE_ZIP_URL). Pour un organe "GOUVERNEMENT" (ex. libellé
    "BORNE", "CASTEX"), la position est toujours "gouvernement" : l'AN ne
    qualifie pas ces organes par positionPolitique, mais leur codeType suffit
    à identifier sans ambiguïté une période d'appartenance à l'exécutif
    (voir KNOWN_POSITIONS_HEMICYCLE, schema_pivot.py). Note : le référentiel
    AN ne distingue pas le portefeuille ministériel précis (ex. "Ministre de
    l'Intérieur") au sein d'un même gouvernement, seulement le gouvernement
    d'appartenance (libelleAbrege)."""
    index: dict[str, dict[str, Any]] = {}
    noms = [n for n in zf.namelist() if n.startswith("json/organe/") and n.endswith(".json")]
    for nom in noms:
        try:
            with zf.open(nom) as f:
                data = json.load(f)
        except (json.JSONDecodeError, KeyError):
            continue
        organe = data.get("organe") if isinstance(data, dict) else None
        if not isinstance(organe, dict):
            continue
        code_type = organe.get("codeType")
        if code_type == "GOUVERNEMENT":
            position = "gouvernement"
        elif code_type == "GP":
            position = _POSITION_POLITIQUE_MAP.get(organe.get("positionPolitique"))
            if position is None:
                continue
        else:
            continue
        organe_ref = organe.get("uid")
        if not isinstance(organe_ref, str) or not organe_ref:
            continue
        index[organe_ref] = {
            "groupe_sigle": organe.get("libelleAbrege"),
            "position": position,
        }
    return index


def _ensure_acteurs_historique_zip_downloaded() -> Optional[Path]:
    """Télécharge (si absente du cache disque) l'archive bulk historique des
    acteurs/mandats/organes de l'Assemblée nationale (AN_ACTEURS_HISTORIQUE_ZIP_URL)
    et retourne son chemin local. Partagée entre plusieurs index construits à
    partir du même zip (_build_acteur_positions_hemicycle_index,
    _build_organe_index) : un seul téléchargement, jamais deux en parallèle.
    Retourne None en cas d'échec (non-fatal pour l'appelant)."""
    with _ACTEURS_HISTORIQUE_ZIP_LOCK:
        zip_path = ACTEURS_HISTORIQUE_CACHE_DIR / "acteurs_historique.zip"
        if zip_path.is_file():
            return zip_path

        print(f"-> Téléchargement de l'historique des acteurs (Assemblée nationale) : {AN_ACTEURS_HISTORIQUE_ZIP_URL}")
        try:
            zip_path.parent.mkdir(parents=True, exist_ok=True)
            download_with_watchdog(AN_ACTEURS_HISTORIQUE_ZIP_URL, zip_path, headers=HEADERS, timeout=TIMEOUT)
        except (requests.RequestException, OSError, TimeoutError) as exc:
            print(f"  [!] Échec du téléchargement de l'historique des acteurs : {exc}")
            return None
        return zip_path


def _build_acteur_positions_hemicycle_index() -> dict[str, list[dict[str, Any]]]:
    """Construit (et met en cache sur disque) un index acteurRef -> liste de
    périodes datées d'appartenance à un groupe politique qualifié majorité/
    opposition/minoritaire par le référentiel officiel de l'Assemblée nationale,
    ainsi que les périodes d'appartenance à un gouvernement (fonction
    ministérielle, position "gouvernement").

    Limitation connue : la qualification majorité/opposition/minoritaire ne
    couvre que les législatures achevées (positionPolitique n'est jamais
    renseigné par l'AN pour la législature en cours, voir
    AN_ACTEURS_HISTORIQUE_ZIP_URL) ; les périodes gouvernementales n'ont pas
    cette limitation (codeType == "GOUVERNEMENT" est toujours renseigné).
    Non-fatal en cas d'échec (retourne {})."""
    with _ACTEURS_HEMICYCLE_LOCK:
        index_path = ACTEURS_HISTORIQUE_CACHE_DIR / "index_positions_hemicycle.json"
        if index_path.is_file():
            try:
                with open(index_path, encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass  # cache corrompu : on reconstruit

        zip_path = _ensure_acteurs_historique_zip_downloaded()
        if zip_path is None:
            return {}

        index: dict[str, list[dict[str, Any]]] = {}
        try:
            with zipfile.ZipFile(zip_path) as zf:
                organe_positions = _build_organe_positions_index(zf)
                if not organe_positions:
                    return {}

                noms = [n for n in zf.namelist() if n.startswith("json/acteur/") and n.endswith(".json")]
                for nom in noms:
                    try:
                        with zf.open(nom) as f:
                            data = json.load(f)
                    except (json.JSONDecodeError, KeyError):
                        continue
                    acteur = data.get("acteur") if isinstance(data, dict) else None
                    if not isinstance(acteur, dict):
                        continue
                    uid = acteur.get("uid")
                    acteur_ref = uid.get("#text") if isinstance(uid, dict) else uid
                    if not isinstance(acteur_ref, str) or not acteur_ref:
                        continue

                    mandats = (acteur.get("mandats") or {}).get("mandat")
                    if isinstance(mandats, dict):
                        mandats = [mandats]
                    if not isinstance(mandats, list):
                        continue

                    for mandat in mandats:
                        if not isinstance(mandat, dict) or mandat.get("typeOrgane") not in ("GP", "GOUVERNEMENT"):
                            continue
                        organe_ref = (mandat.get("organes") or {}).get("organeRef")
                        organe = organe_positions.get(organe_ref)
                        if not organe:
                            continue
                        index.setdefault(acteur_ref, []).append({
                            "legislature": mandat.get("legislature"),
                            "groupe_sigle": organe["groupe_sigle"],
                            "position": organe["position"],
                            "debut": mandat.get("dateDebut"),
                            "fin": mandat.get("dateFin"),
                        })
        except zipfile.BadZipFile as exc:
            print(f"  [!] Archive de l'historique des acteurs invalide : {exc}")
            return {}

        try:
            index_path.parent.mkdir(parents=True, exist_ok=True)
            with open(index_path, "w", encoding="utf-8") as f:
                json.dump(index, f, ensure_ascii=False)
        except OSError:
            pass

        return index


def fetch_positions_hemicycle_officielles(url_an_ou_senat: Optional[str]) -> list[dict[str, Any]]:
    """Récupère les périodes d'appartenance à un groupe politique qualifiées
    majorité/opposition/minoritaire, ainsi que les périodes d'appartenance à
    un gouvernement (position "gouvernement"), par le référentiel officiel de
    l'Assemblée nationale (voir _build_acteur_positions_hemicycle_index). La
    qualification majorité/opposition/minoritaire ne couvre que les législatures
    achevées : retourne [] si aucune période qualifiée n'existe (législature en
    cours sans fonction gouvernementale, sénateur, ou acteur absent du
    référentiel)."""
    acteur_ref = _extract_acteur_ref(url_an_ou_senat)
    if not acteur_ref:
        return []
    index = _build_acteur_positions_hemicycle_index()
    return index.get(acteur_ref, [])


def _build_organe_index() -> dict[str, dict[str, Any]]:
    """Construit (et met en cache sur disque) un index organeRef -> {sigle,
    nom, type} pour TOUS les organes (commissions permanentes/spéciales,
    groupes politiques, groupes d'amitié, missions d'information, engagements
    extra-parlementaires, gouvernements...) du référentiel historique de
    l'Assemblée nationale, à partir du même zip que
    _build_acteur_positions_hemicycle_index (json/organe/*.json).

    Contrairement à _build_organe_positions_index (limité aux organes de type
    "GP"/"GOUVERNEMENT" qualifiés majorité/opposition/minoritaire), cet index
    couvre tous les codeType sans filtrage : prérequis générique pour
    résoudre mandats[].organes.organeRef (ex. "PO59048" -> commission des
    finances) vers un nom lisible, quel que soit le type d'organe (issue #353).

    "sigle" = organe.libelleAbrege (nom court, ex. "Finances"), "nom" =
    organe.libelle (nom complet, ex. "Commission des finances, de l'économie
    générale et du contrôle budgétaire"), "type" = organe.codeType (ex.
    "COMPER", "GP", "GA", "MISINFO", "GOUVERNEMENT"...). Non-fatal en cas
    d'échec (retourne {})."""
    with _ACTEURS_ORGANES_LOCK:
        index_path = ACTEURS_HISTORIQUE_CACHE_DIR / "index_organes.json"
        if index_path.is_file():
            try:
                with open(index_path, encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass  # cache corrompu : on reconstruit

        zip_path = _ensure_acteurs_historique_zip_downloaded()
        if zip_path is None:
            return {}

        index: dict[str, dict[str, Any]] = {}
        try:
            with zipfile.ZipFile(zip_path) as zf:
                noms = [n for n in zf.namelist() if n.startswith("json/organe/") and n.endswith(".json")]
                for nom in noms:
                    try:
                        with zf.open(nom) as f:
                            data = json.load(f)
                    except (json.JSONDecodeError, KeyError):
                        continue
                    organe = data.get("organe") if isinstance(data, dict) else None
                    if not isinstance(organe, dict):
                        continue
                    organe_ref = organe.get("uid")
                    if not isinstance(organe_ref, str) or not organe_ref:
                        continue
                    index[organe_ref] = {
                        "sigle": organe.get("libelleAbrege"),
                        "nom": organe.get("libelle"),
                        "type": organe.get("codeType"),
                    }
        except zipfile.BadZipFile as exc:
            print(f"  [!] Archive de l'historique des acteurs invalide : {exc}")
            return {}

        try:
            index_path.parent.mkdir(parents=True, exist_ok=True)
            with open(index_path, "w", encoding="utf-8") as f:
                json.dump(index, f, ensure_ascii=False)
        except OSError:
            pass

        return index


def fetch_organe(organe_ref: Optional[str]) -> Optional[dict[str, Any]]:
    """Résout un organeRef (ex. mandats[].organes.organeRef, "PO59048") vers
    {sigle, nom, type} via le référentiel historique de l'Assemblée nationale
    (voir _build_organe_index). Retourne None si organe_ref est vide/absent
    ou introuvable dans le référentiel."""
    if not organe_ref:
        return None
    index = _build_organe_index()
    return index.get(organe_ref)


# Mapping typeOrgane (AN, mandats[].typeOrgane) -> categorie du schema pivot
# (schema_pivot.KNOWN_CATEGORIES), pour que _extract_mandats_officiels
# produise la meme forme de sortie quelle que soit la source (issue #369).
#
# Perimetre elargi par #382/#383 (option "mixte") : le perimetre initial de
# #369 se limitait aux 3 categories deja couvertes par nosdeputes.fr, ce qui
# laissait de cote ~3150 mandats sur 6423 mesures (65 profils resolus AN) -
# presque la moitie du referentiel. Ces mandats existaient malgre tout dans
# les profils, mais uniquement parce que la fusion additive preservait des
# entrees heritees de l'ere NosDeputes, ou _extract_mandats les mappait
# TOUTES en dur vers "commission" : d'ou 197 libelles sur 246 classes
# "Commission" sans en etre (voir #379 et
# docs/technical_decisions.md#taxonomie-mandats-typeorgane-an).
#
# Granularite retenue : une categorie par nature institutionnelle reellement
# distincte pour le lecteur, pas une par typeOrgane - les variantes internes
# sont regroupees (MISINFO/MISINFOCOM/MISINFOPRE, CNPE/CNPS, GE/GEVI,
# DELEG/API/OFFPAR).
_TYPE_ORGANE_TO_CATEGORIE: dict[str, str] = {
    # Commissions permanentes et assimilees.
    "COMPER": "commission",
    "COMNL": "commission",          # commissions non legislatives (affaires europeennes...)
    # Commissions temporaires d'investigation : distinctes d'une commission
    # permanente, c'est tout l'objet de la nouvelle categorie.
    "CNPE": "commission_enquete",   # commissions d'enquete
    "CNPS": "commission_enquete",   # commissions speciales
    # Missions d'information (3 variantes AN, meme nature editoriale).
    "MISINFO": "mission_information",
    "MISINFOCOM": "mission_information",
    "MISINFOPRE": "mission_information",
    # Groupes d'etudes, thematiques (GE) et a vocation internationale (GEVI).
    "GE": "groupe_etudes",
    "GEVI": "groupe_etudes",
    # Delegations permanentes de l'AN, delegations aux assemblees
    # parlementaires internationales, offices parlementaires.
    "DELEG": "delegation",
    "DELEGBUREAU": "delegation",
    "API": "delegation",
    "OFFPAR": "delegation",
    # Groupes d'amitie et organismes extra-parlementaires (perimetre #369).
    "GA": "groupe_amitie",
    "ORGEXTPARL": "extra_parlementaire",
    # Instances de direction de l'assemblee : reelles mais sans categorie
    # dediee justifiee par le volume (35 mandats), rangees dans "autre"
    # plutot que de creer une categorie pour deux organes.
    "BUREAU": "autre",
    "CONFPT": "autre",
    # Portefeuille ministeriel precis (#383) : "Ministere de la cohesion des
    # territoires", "Secretariat d'Etat aupres du ministre de...", 52
    # intitules distincts. Complete (sans le remplacer) le rattachement au
    # gouvernement produit par fetch_positions_hemicycle_officielles, qui ne
    # donne que le gouvernement d'appartenance ("Gouvernement (BORNE)").
    # Leve la limitation documentee dans #hors-perimetre, qui affirmait
    # qu'aucune source open data n'exposait ce niveau de detail.
    "MINISTERE": "fonction_gouvernementale",
}

# typeOrgane volontairement NON mappes, avec la raison - explicites plutot
# qu'omis, pour que ce perimetre reste reevaluable (le silence de #369 sur
# ces types avait rendu son propre perimetre difficile a rediscuter) :
#
# - "ASSEMBLEE"    : c'est le mandat electif lui-meme, deja produit ailleurs
#                    (voir _build_acteur_identite_index / mandat_electif).
# - "GP"           : groupe politique parlementaire, deja collecte par
#                    fetch_positions_hemicycle_officielles -> groupe_politique.
# - "GOUVERNEMENT" : rattachement gouvernemental, deja collecte par la meme
#                    fonction -> fonction_gouvernementale. Le mapper ici
#                    creerait un doublon (MINISTERE ci-dessus apporte le
#                    detail manquant, pas une redite).
# - "CMP"          : commissions mixtes paritaires (616 mandats) - organe
#                    temporaire cree par texte de loi, une entree par texte.
#                    Les agreger au niveau groupe noierait les instances
#                    permanentes sous des centaines d'entrees a membre unique
#                    (#383).
# - "PARPOL"       : partis politiques (222). Recoupe conceptuellement le
#                    champ `parti` du pivot et la categorie groupe_politique ;
#                    l'exposer comme mandat mele appartenance partisane et
#                    mandat institutionnel. Arbitrage distinct, hors #382.
# - types Senat    : DELEGSENAT/COMSENAT/GROUPESENAT/SENAT (4 mandats) -
#                    volume negligeable, et le Senat n'a pas d'equivalent de
#                    ce referentiel cote collecte.
# - "CJR"          : Cour de justice de la Republique (1 mandat).
_TYPE_ORGANE_NON_MAPPES: frozenset[str] = frozenset({
    "ASSEMBLEE", "GP", "GOUVERNEMENT", "CMP", "PARPOL",
    "DELEGSENAT", "COMSENAT", "GROUPESENAT", "SENAT", "CJR",
})


def _build_acteur_mandats_index() -> dict[str, list[dict[str, Any]]]:
    """Construit (et met en cache sur disque) un index acteurRef -> liste de
    mandats (commissions, groupes d'amitié, engagements extra-parlementaires),
    à partir du même zip que `_build_acteur_identite_index`/`_build_organe_index`
    (issue #369 — complète #353 : l'organeRef de chaque mandat était déjà
    résolvable en nom lisible via `fetch_organe`, mais rien ne l'exploitait
    encore pour peupler `profile["mandats"]`, qui restait entièrement sourcé
    depuis NosDéputés).

    Périmètre : `typeOrgane` ∈ `_TYPE_ORGANE_TO_CATEGORIE` uniquement — le
    mandat électif de base (`ASSEMBLEE`) et le groupe politique/fonction
    gouvernementale (`GP`/`GOUVERNEMENT`) restent gérés séparément (étapes 5
    et 5bis de `build_profile`), pas dupliqués ici.

    Non-fatal en cas d'échec (retourne {})."""
    with _ACTEURS_MANDATS_LOCK:
        index_path = ACTEURS_HISTORIQUE_CACHE_DIR / "index_mandats.json"
        if index_path.is_file():
            try:
                with open(index_path, encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass  # cache corrompu : on reconstruit

        zip_path = _ensure_acteurs_historique_zip_downloaded()
        if zip_path is None:
            return {}

        index: dict[str, list[dict[str, Any]]] = {}
        try:
            with zipfile.ZipFile(zip_path) as zf:
                noms = [n for n in zf.namelist() if n.startswith("json/acteur/") and n.endswith(".json")]
                for nom in noms:
                    try:
                        with zf.open(nom) as f:
                            data = json.load(f)
                    except (json.JSONDecodeError, KeyError):
                        continue
                    acteur = data.get("acteur") if isinstance(data, dict) else None
                    if not isinstance(acteur, dict):
                        continue
                    uid = acteur.get("uid")
                    acteur_ref = uid.get("#text") if isinstance(uid, dict) else uid
                    if not isinstance(acteur_ref, str) or not acteur_ref:
                        continue

                    mandats = (acteur.get("mandats") or {}).get("mandat")
                    if isinstance(mandats, dict):
                        mandats = [mandats]
                    if not isinstance(mandats, list):
                        continue

                    entries: list[dict[str, Any]] = []
                    for mandat in mandats:
                        if not isinstance(mandat, dict):
                            continue
                        type_organe = mandat.get("typeOrgane")
                        if type_organe not in _TYPE_ORGANE_TO_CATEGORIE:
                            continue
                        organe_ref = (mandat.get("organes") or {}).get("organeRef")
                        # `organeRef` est parfois une LISTE dans le dataset AN
                        # (un mandat rattaché à plusieurs organes) : cas absent
                        # des 3 typeOrgane du périmètre initial (#369), révélé
                        # par l'élargissement de #382. Sans ce garde-fou,
                        # `fetch_organe` lève `TypeError: unhashable type` sur
                        # un lookup de dict par liste. On retient le premier
                        # organe : le libellé du mandat lui vient de toute
                        # façon d'un seul organe, et un mandat sans organe
                        # résolvable serait ignoré juste après.
                        if isinstance(organe_ref, list):
                            organe_ref = organe_ref[0] if organe_ref else None
                        if not organe_ref or not isinstance(organe_ref, str):
                            continue
                        fin = mandat.get("dateFin")
                        entries.append({
                            "categorie": _TYPE_ORGANE_TO_CATEGORIE[type_organe],
                            "organe_ref": organe_ref,
                            "fonction": (mandat.get("infosQualite") or {}).get("libQualite"),
                            "debut": mandat.get("dateDebut"),
                            "fin": fin,
                            "actif": not fin,
                        })
                    if entries:
                        index[acteur_ref] = entries
        except zipfile.BadZipFile as exc:
            print(f"  [!] Archive de l'historique des acteurs invalide : {exc}")
            return {}

        try:
            index_path.parent.mkdir(parents=True, exist_ok=True)
            with open(index_path, "w", encoding="utf-8") as f:
                json.dump(index, f, ensure_ascii=False)
        except OSError:
            pass

        return index


def _extract_mandats_officiels(acteur_ref: str) -> list[dict[str, Any]]:
    """Équivalent de `_extract_mandats`, sourcé depuis le référentiel officiel
    de l'Assemblée nationale plutôt que NosDéputés (issue #369) : commissions,
    groupes d'amitié, engagements extra-parlementaires, avec `organeRef`
    résolu en nom lisible via `fetch_organe` (#353).

    Ne couvre pas le mandat électif de base ni le groupe politique/fonction
    gouvernementale — traités séparément (étapes 5/5bis de `build_profile`),
    pour rester équivalent à `_extract_mandats` qui construit son mandat
    électif à part des responsabilités."""
    mandats: list[dict[str, Any]] = []
    for entry in _build_acteur_mandats_index().get(acteur_ref, []):
        organe = fetch_organe(entry.get("organe_ref"))
        label = (organe or {}).get("nom") or (organe or {}).get("sigle")
        if not label:
            continue
        mandats.append({
            "categorie": entry["categorie"],
            "type": entry.get("fonction") or "membre",
            "label": label,
            "debut": entry.get("debut"),
            "fin": entry.get("fin"),
            "actif": entry.get("actif", False),
        })
    return mandats


def fetch_amendements_officiels(
    url_an_ou_senat: Optional[str], warnings: Optional[list[str]] = None
) -> list[dict[str, Any]]:
    """Récupère les amendements officiels dont le parlementaire est l'auteur principal.

    Agrège sur toutes les législatures pour lesquelles l'Assemblée nationale
    publie ces données en open data (voir AN_AMENDEMENTS_PATH), pas seulement
    celle de la source d'identité : un même élu peut avoir déposé des
    amendements sous plusieurs législatures successives.

    Chaque législature est tentée indépendamment : l'absence de cache pour une
    législature (ex. légis 16, chroniquement instable côté téléchargement)
    n'interrompt plus l'agrégation des autres — corrige un défaut où la
    première législature en échec empêchait même d'essayer les suivantes,
    faisant perdre par exemple une légis 17 pourtant disponible (issue #241).
    Si `warnings` est fourni, un message `WARNING_PREFIX_AMENDEMENTS_INDISPONIBLES`
    précisant la législature concernée y est ajouté pour chaque absence, au
    lieu d'un échec binaire global.

    Lecture cache-only exclusivement (`_read_cached_amendements_acteur`, #250) :
    ne déclenche jamais de téléchargement depuis ce chemin. La construction de
    l'index (téléchargement + parsing de l'archive AN) est désormais la seule
    responsabilité du job CI dédié `extract-amendements-an`
    (`src/build_amendements_index.py`, #251) — sous-issue 4/6 de #248, pour
    que le coût réseau ne soit plus payé indépendamment par chaque job
    consommateur (`extract-an`/`extract-roster-groupes`, issues #239/#245/#246).

    Depuis #377, seules les entrées de `acteur_ref` sont matérialisées sous
    forme complète, à partir du cache dédupliqué — l'index entier de la
    législature n'est plus expansé en mémoire pour n'en lire qu'une fraction.

    Un `url_an_ou_senat` absent ou non parsable produit une liste vide AVEC un
    warning (#265, fix 5) : cet appel n'a lieu que pour `chambre ==
    "deputes"` (voir `build_profile`), donc l'impossibilité d'en extraire un
    acteurRef est toujours une anomalie — jamais le cas normal d'un sénateur
    ou d'un MEP, qui n'atteignent pas ce chemin. Sans ce warning, le résultat
    était un zéro parfaitement silencieux, indiscernable d'une absence
    légitime d'amendements : constaté en pratique sur des profils dont
    l'identité avait été écrite partiellement par un run interrompu.
    """
    acteur_ref = _extract_acteur_ref(url_an_ou_senat)
    if not acteur_ref:
        if warnings is not None:
            warnings.append(
                f"{WARNING_PREFIX_AMENDEMENTS_INDISPONIBLES} : identifiant Assemblée nationale "
                f"introuvable pour ce profil (url_an_ou_senat={url_an_ou_senat!r}) — "
                "aucun amendement ne peut être collecté"
            )
        return []

    amendements: list[dict[str, Any]] = []
    for legislature in AN_AMENDEMENTS_PATH:
        records = _read_cached_amendements_acteur(legislature, acteur_ref)
        if records is None:
            if warnings is not None:
                warnings.append(
                    f"{WARNING_PREFIX_AMENDEMENTS_INDISPONIBLES} (législature {legislature}) : "
                    "index en cache absent (job extract-amendements-an non exécuté ou en échec pour cette législature)"
                )
            continue
        for record in records:
            amendements.append({**record, "legislature": legislature})

    if amendements:
        titre_index = _build_texte_titre_index()
        if titre_index:
            for record in amendements:
                titre = titre_index.get(record.get("texte_vise"))
                if titre:
                    record["texte_vise"] = titre

    amendements.sort(key=lambda a: a.get("date") or "", reverse=True)
    return amendements


def _parse_question_entry(data: dict, sous_type: str) -> Optional[tuple[str, dict[str, Any]]]:
    """Parse une entrée de question AN (QE/QG/QOSD) et retourne (acteur_ref, record) ou None.

    `data` est un dict issu du JSON d'une question (contenant une clé "question").
    `sous_type` est "QE", "QG" ou "QOSD" (dérivé du dossier/fichier de provenance).
    """
    question = data.get("question")
    if not isinstance(question, dict):
        return None

    auteur = question.get("auteur") or {}
    identite_auteur = auteur.get("identite") or {}
    acteur_ref = identite_auteur.get("acteurRef")
    if not acteur_ref:
        return None

    uid = question.get("uid")

    # Sujet court (indexation AN — peut être une chaîne ou une liste de chaînes).
    indexation = question.get("indexationAN") or {}
    analyses = indexation.get("analyses") or {}
    analyse = analyses.get("analyse")
    if isinstance(analyse, list):
        analyse = " ; ".join(str(a) for a in analyse if a)
    elif not isinstance(analyse, str):
        analyse = None

    # Texte de la question + date JO (texteQuestion peut être un dict ou une liste de dicts).
    textes_question = question.get("textesQuestion") or {}
    texte_q_block = textes_question.get("texteQuestion")
    if isinstance(texte_q_block, list):
        texte_q_block = texte_q_block[-1] if texte_q_block else {}
    if not isinstance(texte_q_block, dict):
        texte_q_block = {}
    texte_question = texte_q_block.get("texte") if isinstance(texte_q_block.get("texte"), str) else None
    info_jo_q = texte_q_block.get("infoJO") or {}
    date_question = info_jo_q.get("dateJO") if isinstance(info_jo_q.get("dateJO"), str) else None

    # Texte de la réponse + date JO (optionnel, absent si la question n'a pas encore reçu de réponse).
    textes_reponse = question.get("textesReponse") or {}
    texte_r_block = textes_reponse.get("texteReponse")
    if isinstance(texte_r_block, list):
        texte_r_block = texte_r_block[-1] if texte_r_block else None
    reponse: Optional[str] = None
    date_reponse: Optional[str] = None
    if isinstance(texte_r_block, dict):
        reponse = texte_r_block.get("texte") if isinstance(texte_r_block.get("texte"), str) else None
        info_jo_r = texte_r_block.get("infoJO") or {}
        date_reponse = info_jo_r.get("dateJO") if isinstance(info_jo_r.get("dateJO"), str) else None

    # Ministère interrogé.
    min_int = question.get("minInt") or {}
    ministere = min_int.get("developpe") if isinstance(min_int.get("developpe"), str) else None

    # Groupe parlementaire au moment du dépôt.
    groupe = auteur.get("groupe") or {}
    groupe_sigle = groupe.get("abrege") if isinstance(groupe.get("abrege"), str) else None

    return acteur_ref, {
        "uid": uid,
        "sous_type": sous_type,
        "sujet": analyse,
        "texte": texte_question,
        "reponse": reponse,
        "ministere": ministere,
        "date": date_question,
        "date_reponse": date_reponse,
        "groupe_sigle": groupe_sigle,
    }


def _build_acteur_questions_index(legislature: str) -> dict[str, list[dict[str, Any]]]:
    """Construit (et met en cache sur disque) un index acteurRef -> liste de questions.

    Agrège les 3 types (QE/QG/QOSD) en un seul index par législature. Les ZIPs
    ne sont jamais extraits sur disque : seul l'index final est mis en cache.
    Thread-safe (verrou par législature), même principe que pour les amendements.
    """
    with _get_questions_lock(legislature):
        index_path = QUESTIONS_CACHE_DIR / legislature / "index_par_acteur.json"
        if index_path.is_file():
            try:
                with open(index_path, encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass  # cache corrompu : on reconstruit

        question_types = AN_QUESTIONS_PATH.get(legislature)
        if not question_types:
            return {}

        index: dict[str, list[dict[str, Any]]] = {}

        for sous_type, (dossier, fichier) in question_types.items():
            url = f"{AN_OPENDATA_BASE}/{legislature}/questions/{dossier}/{fichier}"
            print(f"-> Téléchargement des questions {sous_type} (Assemblée nationale, législature {legislature}) : {url}")
            zip_path = QUESTIONS_CACHE_DIR / legislature / f"{sous_type.lower()}.zip"
            try:
                zip_path.parent.mkdir(parents=True, exist_ok=True)
                download_with_watchdog(url, zip_path, headers=HEADERS, timeout=TIMEOUT)
            except (requests.RequestException, OSError, TimeoutError) as exc:
                print(f"  [!] Questions {sous_type} législature {legislature} indisponibles : {exc}")
                continue

            try:
                with zipfile.ZipFile(zip_path) as zf:
                    noms = [n for n in zf.namelist() if n.endswith(".json")]
                    for nom in noms:
                        try:
                            with zf.open(nom) as f:
                                data = json.load(f)
                        except (json.JSONDecodeError, KeyError):
                            continue
                        parsed = _parse_question_entry(data, sous_type)
                        if parsed is None:
                            continue
                        acteur_ref, record = parsed
                        index.setdefault(acteur_ref, []).append(record)
            except zipfile.BadZipFile as exc:
                print(f"  [!] Archive de questions {sous_type} législature {legislature} invalide : {exc}")

        try:
            index_path.parent.mkdir(parents=True, exist_ok=True)
            with open(index_path, "w", encoding="utf-8") as f:
                json.dump(index, f, ensure_ascii=False)
        except OSError:
            pass

        return index


def fetch_questions_officielles(url_an_ou_senat: Optional[str]) -> list[dict[str, Any]]:
    """Récupère les questions parlementaires officielles (QE/QG/QOSD) d'un député.

    Source : open data Assemblée nationale (data.assemblee-nationale.fr). Agrège
    sur toutes les législatures pour lesquelles ces données sont disponibles (voir
    AN_QUESTIONS_PATH). Retourne une liste d'entrées au format brut interventions[],
    prêtes à être fusionnées dans profile["interventions"] avec type_detail="question".

    Chaque entrée inclut les champs supplémentaires sous_type (QE/QG/QOSD),
    ministere (ministère interrogé) et reponse (texte de la réponse si disponible).
    """
    acteur_ref = _extract_acteur_ref(url_an_ou_senat)
    if not acteur_ref:
        return []

    questions: list[dict[str, Any]] = []
    for legislature in AN_QUESTIONS_PATH:
        index = _build_acteur_questions_index(legislature)
        for record in index.get(acteur_ref, []):
            uid = record.get("uid") or ""
            source_url = (
                f"https://questions.assemblee-nationale.fr/q{legislature}/{uid}.htm"
                if uid else None
            )
            questions.append({
                "id": f"question_{uid}" if uid else None,
                "date": record.get("date"),
                "type_detail": "question",
                "sous_type": record.get("sous_type"),
                "sujet": record.get("sujet"),
                "texte": record.get("texte"),
                "reponse": record.get("reponse"),
                "date_reponse": record.get("date_reponse"),
                "ministere": record.get("ministere"),
                "groupe_sigle": record.get("groupe_sigle"),
                "fonction": None,
                "format": "prise_de_parole_developpee",
                "mots_cles": [],
                "url": source_url,
                "url_detail": source_url,
                "legislature": legislature,
            })

    questions.sort(key=lambda q: q.get("date") or "", reverse=True)
    return questions


def _parse_syceron_intervention_entry(
    intervention: Any,
    legislature: str,
    index_in_source: int,
) -> Optional[tuple[str, dict[str, Any]]]:
    """Convertit une intervention Syceron en entrée d'index acteurRef -> interventions.

    Seules les interventions dont l'orateur est relié sans ambiguïté à un
    `acteurRef` officiel Assemblée nationale (`PA...`) sont indexées.
    """
    if not isinstance(intervention, dict):
        return None

    acteur_ref = intervention.get("orateur_id_source")
    if not isinstance(acteur_ref, str) or not re.fullmatch(r"PA\d+", acteur_ref):
        return None

    source_id = intervention.get("source_id")
    suffix = f"{index_in_source:06d}"
    source_url = syceron_zip_url(legislature)
    record = {
        "id": f"syceron_{source_id or 'inconnu'}_{suffix}",
        "date": intervention.get("date"),
        "type_detail": intervention.get("type_detail"),
        "sujet": intervention.get("sujet"),
        "texte": intervention.get("texte"),
        "fonction": intervention.get("fonction"),
        "format": intervention.get("format"),
        "mots_cles": intervention.get("mots_cles") or [],
        # Compatibilité avec les autres formats bruts d'interventions : `source`
        # est consommé par certains helpers existants, tandis que `url`/`url_detail`
        # restent les clés attendues par le chemin de normalisation NosDéputés.
        "source": source_url,
        "source_url": source_url,
        "url": source_url,
        "url_detail": None,
        "source_id": source_id,
        "seance_ref": intervention.get("seance_ref"),
        "session_ref": intervention.get("session_ref"),
        "orateur_id_source": acteur_ref,
        "orateur_nom": intervention.get("orateur_nom"),
        "point_ordre_du_jour": intervention.get("point_ordre_du_jour"),
        "etat_compte_rendu": intervention.get("etat_compte_rendu"),
        "version_compte_rendu": intervention.get("version_compte_rendu"),
        "legislature": legislature,
    }
    return acteur_ref, record


def _build_acteur_interventions_syceron_index(legislature: str) -> dict[str, list[dict[str, Any]]]:
    """Construit (et met en cache) un index acteurRef -> interventions Syceron.

    Les XML Syceron sont déjà téléchargés/extraits par `syceron_debates.py` ;
    ici on ne sérialise que l'index final des interventions rattachables sans
    ambiguïté à un `acteurRef` officiel.
    """
    with _get_syceron_lock(legislature):
        index_path = Path(".cache") / "syceron_an" / legislature / "index_par_acteur.json"
        if index_path.is_file():
            try:
                with open(index_path, encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass

        index: dict[str, list[dict[str, Any]]] = {}
        for xml_path in iter_syceron_xml_files(legislature):
            try:
                parsed = parse_syceron_xml(xml_path.read_bytes())
            except (ET.ParseError, OSError):
                continue
            for idx, intervention in enumerate(parsed.get("interventions") or []):
                parsed_entry = _parse_syceron_intervention_entry(intervention, legislature, idx)
                if parsed_entry is None:
                    continue
                acteur_ref, record = parsed_entry
                index.setdefault(acteur_ref, []).append(record)

        try:
            index_path.parent.mkdir(parents=True, exist_ok=True)
            with open(index_path, "w", encoding="utf-8") as f:
                json.dump(index, f, ensure_ascii=False)
        except OSError:
            pass

        return index


def fetch_interventions_syceron(url_an_ou_senat: Optional[str]) -> list[dict[str, Any]]:
    """Récupère les débats Syceron d'un député via son `acteurRef` officiel AN."""
    acteur_ref = _extract_acteur_ref(url_an_ou_senat)
    if not acteur_ref:
        return []

    interventions: list[dict[str, Any]] = []
    for legislature in sorted(SYCERON_AVAILABLE_LEGISLATURES, key=int, reverse=True):
        index = _build_acteur_interventions_syceron_index(legislature)
        interventions.extend(index.get(acteur_ref, []))

    interventions.sort(key=lambda entry: (entry.get("date") or "", entry.get("id") or ""), reverse=True)
    return interventions


def fetch_votes(base_urls: list[str], slug: str) -> tuple[Optional[list], Optional[str]]:
    """Liste des scrutins auxquels le parlementaire a participé, avec sa position."""
    for base_url in base_urls:
        for suffix in ["/votes/json", "/votes/xml"]:
            url = f"{base_url}/{slug}{suffix}"
            print(f"-> Récupération des votes : {url}")
            data = _get_payload(url)
            if data is _TERMINAL_FAILURE:
                # Échec déterministe : inutile d'essayer l'autre format sur ce base_url.
                break
            if data is None:
                continue
            votes = data.get("votes", data) if isinstance(data, dict) else data
            if not _is_empty_payload(votes):
                return votes, base_url
            time.sleep(0.2)
    return None, None


def _groupe_label(groupe_field: Any) -> Optional[str]:
    """Le champ « groupe » de l'API est un dict {organisme, fonction, debut_fonction},
    pas une chaîne : on en extrait le nom du groupe politique."""
    if isinstance(groupe_field, dict):
        return groupe_field.get("organisme")
    if isinstance(groupe_field, str):
        return groupe_field
    return None


def _extract_responsabilite_entries(raw_list: Any, categorie: str) -> list[dict[str, Any]]:
    """Normalise une liste de responsabilités (commissions, missions, groupes d'amitié...)
    telle que fournie par les champs `responsabilites`, `historique_responsabilites`,
    `groupes_parlementaires` ou `responsabilites_extra_parlementaires` de l'API."""
    entries: list[dict[str, Any]] = []
    for raw in raw_list or []:
        if not isinstance(raw, dict):
            continue
        resp = raw.get("responsabilite") if isinstance(raw.get("responsabilite"), dict) else raw
        organisme = resp.get("organisme")
        if not organisme:
            continue
        fin = resp.get("fin_fonction")
        entries.append({
            "categorie": categorie,
            "type": resp.get("fonction") or "membre",
            "label": organisme,
            "debut": resp.get("debut_fonction"),
            "fin": fin,
            "actif": not fin,
        })
    return entries


def _extract_mandats(parlementaire: dict[str, Any]) -> list[dict[str, Any]]:
    """Extrait les responsabilités lisibles (commissions, missions, groupes d'amitié,
    engagements extra-parlementaires) et le mandat électif de base, à partir des
    champs réels renvoyés par l'API NosDéputés.fr / NosSénateurs.fr :
    `responsabilites`, `historique_responsabilites`, `groupes_parlementaires`,
    `responsabilites_extra_parlementaires`.

    Chaque entrée a le format {categorie, type (la fonction : membre/président/
    rapporteur/...), label (le nom de l'organisme), debut, fin, actif}.
    """
    mandats: list[dict[str, Any]] = []

    debut_mandat = parlementaire.get("mandat_debut")
    fin_mandat = parlementaire.get("mandat_fin")
    if debut_mandat or fin_mandat:
        groupe_label = _groupe_label(parlementaire.get("groupe"))
        mandats.append({
            "categorie": "mandat_electif",
            "type": "mandat",
            "label": "Mandat parlementaire" + (f" ({groupe_label})" if groupe_label else ""),
            "debut": debut_mandat,
            "fin": fin_mandat,
            "actif": not fin_mandat,
        })

    mandats.extend(_extract_responsabilite_entries(parlementaire.get("responsabilites"), "commission"))
    mandats.extend(_extract_responsabilite_entries(parlementaire.get("historique_responsabilites"), "commission"))
    mandats.extend(_extract_responsabilite_entries(parlementaire.get("groupes_parlementaires"), "groupe_amitie"))
    mandats.extend(_extract_responsabilite_entries(parlementaire.get("responsabilites_extra_parlementaires"), "extra_parlementaire"))

    # Filets de secours pour d'anciens formats d'API (champs génériques non
    # observés dans les réponses actuelles, mais conservés par prudence).
    if not mandats:
        for raw in parlementaire.get("mandats_generiques", []) or []:
            if isinstance(raw, dict):
                mandats.append({
                    "categorie": "autre",
                    "type": raw.get("type") or "mandat",
                    "label": raw.get("label") or raw.get("nom") or raw.get("description"),
                    "debut": raw.get("debut") or raw.get("date_debut"),
                    "fin": raw.get("fin") or raw.get("date_fin"),
                    "actif": not (raw.get("fin") or raw.get("date_fin")),
                })
            elif isinstance(raw, str):
                mandats.append({"categorie": "autre", "type": "mandat", "label": raw, "actif": True})

    return mandats


# Seuil (en nombre de mots, champ `nb_mots` de l'API) en-deçà duquel une intervention
# est considérée comme une réaction/interjection courte plutôt qu'une prise de parole
# développée. Heuristique ajustable : les interjections observées ("Oh !", "Bravo !",
# "Très bien !", "Mais non !") comptent 2 à 3 mots, tandis qu'une intervention
# construite dépasse largement ce seuil.
REACTION_COURTE_NB_MOTS_MAX = 15


def _to_int(value: Any) -> Optional[int]:
    """Convertit une valeur (souvent une chaîne renvoyée par l'API) en entier, sans lever."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _classify_intervention_format(nb_mots: Optional[int]) -> Optional[str]:
    """Distingue une réaction courte (interjection/exclamation lancée depuis les bancs)
    d'une prise de parole développée, à partir de la longueur de l'intervention.
    Ne remplace pas `classification.mode` (qui identifie l'orateur) : les deux se
    combinent pour répondre à « était-il à la tribune/au micro, ou a-t-il juste réagi ? »."""
    if nb_mots is None:
        return None
    return "reaction_courte" if nb_mots <= REACTION_COURTE_NB_MOTS_MAX else "prise_de_parole_developpee"


def fetch_intervention_details(base_url: str, intervention_id: str) -> Optional[dict[str, Any]]:
    """Récupère les détails d’une intervention via l’API de document."""
    url = f"{base_url}/api/document/Intervention/{intervention_id}/json"
    print(f"-> Détail intervention : {url}")
    data = _get_payload(url)
    if isinstance(data, dict):
        intervention = data.get("intervention") or {}
        if isinstance(intervention, dict):
            speaker_name = None
            speaker_url = None
            url_nosdeputes = intervention.get("url_nosdeputes")
            if url_nosdeputes:
                try:
                    page = requests.get(url_nosdeputes, headers=HEADERS, timeout=TIMEOUT)
                    page.raise_for_status()
                    # Le site ne déclare pas toujours son charset : sans cela, requests
                    # utilise ISO-8859-1 par défaut et corrompt les caractères accentués.
                    page.encoding = page.apparent_encoding or page.encoding
                    anchor_id = urlsplit(url_nosdeputes).fragment or None
                    speaker_name, speaker_url = _extract_speaker_identity_from_html(page.text, anchor_id=anchor_id)
                except requests.RequestException:
                    speaker_name, speaker_url = None, None

            return {
                "id": intervention.get("id"),
                "date": intervention.get("date"),
                "created_at": intervention.get("created_at"),
                "type": intervention.get("type"),
                "source": intervention.get("source"),
                "texte": intervention.get("intervention"),
                "url": url_nosdeputes,
                "parlementaire_id": intervention.get("parlementaire_id"),
                "personnalite_id": intervention.get("personnalite_id"),
                "seance_id": intervention.get("seance_id"),
                "speaker_name": speaker_name,
                "speaker_url": speaker_url,
                # `fonction` est le rôle institutionnel officiel occupé par l'orateur au
                # moment précis de cette intervention (ex. "Première ministre", "Rapporteur",
                # "Président de la commission des lois") : vide pour un simple député sans
                # fonction particulière. `nb_mots` sert de proxy pour distinguer une réaction
                # courte (interjection) d'une prise de parole développée.
                "fonction": intervention.get("fonction") or None,
                "nb_mots": _to_int(intervention.get("nb_mots")),
            }
    return None


def fetch_seance_context(detail: Optional[dict[str, Any]]) -> dict[str, Any]:
    """Enrichit une intervention à partir du contenu HTML de la page de séance, quand la page est accessible."""
    if not detail:
        return {"sujet": None, "mots_cles": []}

    url_detail = detail.get("url") or detail.get("source")
    if not url_detail:
        return {"sujet": None, "mots_cles": []}

    try:
        resp = requests.get(url_detail, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        # Même remarque que pour les pages d'intervention : forcer l'encodage détecté
        # évite le mojibake sur les accents lorsque le serveur ne déclare pas de charset.
        resp.encoding = resp.apparent_encoding or resp.encoding
        html_text = resp.text
    except requests.RequestException:
        return {"sujet": detail.get("type"), "mots_cles": []}

    soup = BeautifulSoup(html_text, "html.parser")

    sujet = None
    keywords: list[str] = []

    summary_block = None
    for node in soup.find_all(["div", "section", "aside"]):
        if not node.get("class"):
            continue
        class_names = " ".join(node.get("class", [])).lower()
        if "orga_dossier" in class_names or "sommaire" in class_names or "summary" in class_names:
            summary_block = node
            break

    if summary_block is None:
        summary_block = soup.find(["div", "section"], string=lambda value: value and "sommaire" in value.lower())

    if summary_block is not None:
        link_candidates = []
        for link in summary_block.find_all("a"):
            text = " ".join(link.get_text(" ", strip=True).split())
            if not text:
                continue
            lowered = text.lower()
            if any(skip in lowered for skip in ["voir le dossier", "retour au sommaire", "permalink", "commentaire", "source"]):
                continue
            if len(text) < 120:
                link_candidates.append(text)
        if link_candidates:
            sujet = link_candidates[0]

    if not sujet:
        summary_candidates: list[str] = []

        for node in soup.find_all(["h1", "h2", "h3", "p", "div", "li", "span"]):
            text = " ".join(node.get_text(" ", strip=True).split())
            if not text:
                continue
            lowered = text.lower()
            if any(marker in lowered for marker in ["résumé de la réunion", "resume de la reunion", "résumé de la séance", "resume de la seance", "résumé de la seance", "résumé"]):
                summary_candidates.append(text)
                continue
            if node.name in {"h2", "h3"} and len(text) < 180 and not re.search(r"(mots clés|mot-clé|source|permalien|commentaires)", lowered):
                summary_candidates.append(text)

        for candidate in summary_candidates:
            cleaned = re.sub(r"^(?:résumé|resume)\s*(?:de la|de la séance|de la reunion|de la seance)?\s*[:\-]?\s*", "", candidate, flags=re.I)
            cleaned = re.sub(r"^(?:réunion|seance|séance|session|table ronde|audition)\s*[:\-]?\s*", "", cleaned, flags=re.I)
            cleaned = cleaned.strip(" :.-")
            if cleaned and len(cleaned) < 220:
                sujet = cleaned
                break

    if not sujet:
        title = soup.title.get_text(" ", strip=True) if soup.title else None
        if title:
            title_parts = re.split(r"\s*-\s*", title, flags=re.I)
            title_candidate = title_parts[0].strip() if title_parts else title
            if title_candidate:
                sujet = title_candidate

    if not sujet:
        sujet = detail.get("type")

    tag_block = soup.find(class_="nuage_de_tags")
    if tag_block:
        text = " ".join(tag_block.get_text(" ", strip=True).split())
        if text:
            parts = [p.strip() for p in re.split(r"[\s,;]+", text) if p.strip()]
            keywords = []
            for p in parts:
                cleaned = re.sub(r"^(?:mots\s+clés|mots\s+cles|mot-clé|mot-cle|mots clés|mots cles|clés|cles)\s*[:\-]?\s*", "", p, flags=re.I)
                cleaned = cleaned.strip(" :.-")
                if cleaned and cleaned.lower() not in {"les", "de", "cette", "réunion", "reunion", "mot", "mots", "clé", "cle"}:
                    keywords.append(cleaned)

    return {"sujet": sujet, "mots_cles": keywords[:8]}


def _extract_speaker_identity_from_html(html_text: Optional[str], anchor_id: Optional[str] = None) -> tuple[Optional[str], Optional[str]]:
    """Extrait le nom et l'URL du profil de l'orateur depuis le HTML d'une intervention.

    Une page de séance contient les interventions de tous les orateurs. Si un
    identifiant d'ancre (ex. "inter_abc123", tiré du fragment #... de l'URL de
    l'intervention) est fourni, on restreint la recherche du bloc div.perso au
    conteneur de CETTE intervention précise, plutôt que de prendre le premier
    div.perso de la page (souvent le/la président·e de séance).
    """
    if not html_text:
        return None, None

    try:
        soup = BeautifulSoup(html_text, "html.parser")
    except Exception:
        return None, None

    scope = soup
    restrict_to_scope = False
    if anchor_id:
        anchor = soup.find(id=anchor_id) or soup.find(attrs={"name": anchor_id})
        if anchor is not None:
            classes = anchor.get("class") or []
            container = anchor if "intervention" in classes else anchor.find_parent(class_="intervention")
            scope = container or anchor
            restrict_to_scope = True

    for container in scope.select("div.perso"):
        text = " ".join(container.get_text(" ", strip=True).split())
        if text and len(text) < 220:
            for link in container.find_all("a"):
                href = link.get("href")
                if href:
                    return text, href
            return text, None

    if restrict_to_scope:
        # On ne remonte pas à l'orateur d'une autre intervention de la page :
        # mieux vaut ne rien renvoyer que d'attribuer la mauvaise identité.
        return None, None

    return None, None


def _classify_intervention(item: dict[str, Any], candidate_name: str, candidate_id: Optional[str]) -> dict[str, Any]:
    """Classe une intervention en prise de parole uniquement via l'orateur du bloc div.perso."""
    _ = candidate_id  # Conservé pour compatibilité de signature.
    structured_speaker = item.get("speaker_name") or item.get("speaker") or item.get("orateur")
    speaker_url = item.get("speaker_url") or item.get("speaker_href")
    if not structured_speaker and not speaker_url:
        html_payload = item.get("html")
        if html_payload:
            structured_speaker, speaker_url = _extract_speaker_identity_from_html(str(html_payload))

    if not structured_speaker and not speaker_url:
        return {
            "mode": "mention",
            "reason": "orateur_bloc_perso_introuvable",
        }

    candidate_name_lower = candidate_name.lower()
    speaker_lower = (structured_speaker or "").lower()
    speaker_url_lower = (speaker_url or "").lower()
    # Les URLs nosdeputes.fr sont toujours sans accent (ex. "elisabeth-borne"),
    # contrairement au nom candidat brut : on désaccentue avant de construire le
    # slug pour ne pas rater la correspondance (cf. _normalize_search_query).
    slug = _normalize_search_query(candidate_name).replace(" ", "-")

    if slug and slug in speaker_url_lower:
        return {
            "mode": "prise_de_parole",
            "reason": "orateur_bloc_perso_url_correspondante",
        }

    if structured_speaker and candidate_name_lower in speaker_lower:
        return {
            "mode": "prise_de_parole",
            "reason": "orateur_bloc_perso_nom_correspondant",
        }

    return {
        "mode": "mention",
        "reason": "orateur_bloc_perso_non_correspondant",
    }


def _process_search_result(item: dict[str, Any], base_url: str, candidate_name: str, candidate_id: Optional[str]) -> Optional[dict[str, Any]]:
    """Traite un résultat de recherche unique (détail + contexte de séance) et le nettoie.

    Retourne None si le résultat n'est pas une prise de parole (mention simple).
    Extrait de `_extract_search_results` pour être exécuté en parallèle par résultat.
    """
    document_id = item.get("document_id")
    search_base_url = item.get("_search_base_url") or base_url
    detail = None
    if document_id:
        detail = fetch_intervention_details(search_base_url, str(document_id))
    classification = _classify_intervention(detail or {}, candidate_name, candidate_id) if detail else {"mode": "mention", "reason": "detail_indisponible"}
    cleaned = None
    if classification.get("mode") == "prise_de_parole":
        seance_context = fetch_seance_context(detail) if detail else {"sujet": None, "mots_cles": []}
        sujet = seance_context.get("sujet")
        keywords = seance_context.get("mots_cles") or []
        if not sujet:
            sujet = detail.get("type") if detail else None
        nb_mots = detail.get("nb_mots") if detail else None
        cleaned = {
            "type": item.get("document_type"),
            "id": document_id,
            "url": item.get("document_url"),
            "date": detail.get("date") if detail else None,
            "created_at": detail.get("created_at") if detail else None,
            "type_detail": detail.get("type") if detail else None,
            "source": detail.get("source") if detail else None,
            "texte": detail.get("texte") if detail else None,
            "url_detail": detail.get("url") if detail else None,
            "classification": classification,
            "sujet": sujet,
            "mots_cles": keywords,
            # Rôle institutionnel occupé au moment de l'intervention (ex. "Ministre
            # de l'Intérieur", "Rapporteur") : vide si simple parlementaire sans
            # fonction particulière à cet instant.
            "fonction": detail.get("fonction") if detail else None,
            "nb_mots": nb_mots,
            # "reaction_courte" (interjection) vs "prise_de_parole_developpee",
            # dérivé de nb_mots : permet de distinguer une réaction lancée depuis
            # les bancs d'une véritable prise de parole à la tribune/au micro.
            "format": _classify_intervention_format(nb_mots),
        }
    time.sleep(0.1)
    return cleaned


def _extract_search_results(base_url: str, search_payload: Optional[dict], candidate_name: str, candidate_id: Optional[str]) -> list[dict[str, Any]]:
    """Normalise les résultats de recherche API et enrichit chaque intervention avec un détail.

    Les requêtes de détail/contexte sont indépendantes d'un résultat à l'autre : on les
    parallélise avec un pool limité (comme `fetch_all_intervention_results_from_domains`)
    pour éviter des temps de génération proportionnels au nombre de résultats bruts
    (jusqu'à ~500 avec max_pages=10), tout en restant raisonnablement courtois avec l'API.
    """
    if not isinstance(search_payload, dict):
        return []
    results = [item for item in (search_payload.get("results") or []) if isinstance(item, dict)]
    if not results:
        return []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        processed = list(executor.map(
            lambda item: _process_search_result(item, base_url, candidate_name, candidate_id),
            results,
        ))
    return [item for item in processed if item is not None]



def build_profile(
    chambre: str,
    slug: str,
    intervention_max_pages: int = 10,
    skip_interventions: bool = False,
    skip_dossiers_legislatifs: bool = False,
) -> dict:
    """Construit le profil complet d'un parlementaire (identité, mandats/responsabilités,
    votes, dossiers législatifs, interventions) en enchaînant les appels aux différentes
    sources de données (NosDéputés.fr / NosSénateurs.fr + open data Assemblée nationale).

    Aucune source indisponible ne fait échouer l'appel : chaque section manquante reste
    simplement vide, avec un message explicatif ajouté à `profile["meta"]["warnings"]`.

    Args:
        chambre: "deputes" ou "senateurs".
        slug: identifiant NosDéputés.fr / NosSénateurs.fr du parlementaire
            (ex. "jean-luc-melenchon").
        intervention_max_pages: nombre max. de pages de résultats de recherche
            d'interventions à parcourir (chaque page = jusqu'à 50 résultats, chacun
            nécessitant une requête de détail supplémentaire : réduire ce nombre accélère
            fortement la génération d'un profil, au prix d'une couverture moins complète).
        skip_dossiers_legislatifs: si True, ne fait aucun appel réseau pour les dossiers
            législatifs (`profile["dossiers_legislatifs"]` reste vide) — ni le chemin
            NosDéputés (sénateurs) ni `fetch_textes_portes_officiels` (députés). Voir mode
            d'extraction léger (#357) : utilisé quand seuls identité/mandats/votes/
            amendements sont exploités en aval (agrégats de groupe, #349).

    Returns:
        Le dict de profil, sérialisable en JSON tel quel.
    """
    if chambre not in BASE_URLS:
        raise ValueError(f"chambre invalide : {chambre} (attendu: {list(BASE_URLS)})")

    base_urls = BASE_URLS[chambre]

    # --- 0. Identité/mandats officiels (Assemblée nationale), résolus en tout
    # premier afin que l'étape 1 puisse sauter l'appel NosDéputés dès que
    # l'acteur y est trouvé (#369, étape 4 — c'était jusqu'ici le point d'appel
    # réseau le plus exposé à nosdeputes.fr : 8 requêtes systématiques par
    # candidat, sur un domaine sujet à des ralentissements/gels observés en CI). ---
    pre_profile_warnings: list[str] = []
    identite_an: Optional[dict[str, Any]] = None
    acteur_ref_an: Optional[str] = None
    if chambre == "deputes":
        try:
            identite_an, acteur_ref_an = fetch_identite_officielle_par_slug(slug)
        except Exception as exc:
            pre_profile_warnings.append(f"identité officielle (Assemblée nationale) indisponible : {exc}")

    # --- 1. Identité brute NosDéputés/NosSénateurs. Depuis #369, cet appel est
    # sauté pour les députés dès que l'étape 0 ci-dessus a trouvé l'acteur dans
    # le référentiel officiel AN : reste nécessaire pour les sénateurs (non
    # couverts par l'AN), le nom de recherche d'interventions (étape 2) quand
    # l'AN n'a pas trouvé l'acteur, et en repli complet d'identité si le
    # candidat n'est trouvé ni dans les archives AN ni via NosDéputés. ---
    if chambre != "deputes" or acteur_ref_an is None:
        identity_result = fetch_identity(base_urls, slug)
        if isinstance(identity_result, tuple):
            identity_raw, identity_base_url = identity_result
        else:
            identity_raw = identity_result
            identity_base_url = None
        time.sleep(0.5)  # on reste courtois avec l'API publique
    else:
        identity_raw = None
        identity_base_url = None

    # Votes bruts NosDéputés : uniquement pour les sénateurs. Pour les députés,
    # l'endpoint /votes de NosDéputés.fr est en panne de façon systématique
    # (HTTP 500 sur tous les domaines/législatures, voir docstring de
    # fetch_votes_officiels ci-dessous) : votes_raw y est donc TOUJOURS vide,
    # rendant la branche de repli "else: utiliser votes_raw" (étape 6)
    # inatteignable pour cette chambre. L'appel réseau ici (jusqu'à 8 requêtes :
    # 4 domaines × 2 formats) ne fait donc que risquer un blocage pour un
    # résultat qui ne sera jamais exploité — même logique que le retrait de
    # fetch_dossiers_for_legislatures pour les députés, voir
    # docs/technical_decisions.md#dossiers-legislatifs-nosdeputes-vs-an-officiel.
    votes_raw: Any = None
    if chambre != "deputes":
        votes_result = fetch_votes(base_urls, slug)
        if isinstance(votes_result, tuple):
            votes_raw, _ = votes_result
        else:
            votes_raw = votes_result

    # --- 2. Nom de recherche fiable, dérivé de l'identité, pour l'API de recherche
    # d'interventions : un slug transformé en espaces (ex. "jean luc melenchon")
    # ne renvoie souvent aucun résultat, contrairement au nom complet. ---
    parlementaire_for_search = None
    if isinstance(identity_raw, dict):
        parlementaire_for_search = _extract_parlementaire(identity_raw)
    if isinstance(parlementaire_for_search, dict) and parlementaire_for_search.get("nom"):
        search_candidate_name = parlementaire_for_search.get("nom")
    elif identite_an and identite_an.get("nom_complet"):
        search_candidate_name = identite_an.get("nom_complet")
    else:
        search_candidate_name = slug.replace("-", " ").title()

    # --- 3. Dossiers législatifs et recherche des interventions (sur le
    # meilleur domaine/législature disponible). ---
    dossiers_payload = []
    interventions_payload = None
    interventions_base_url = base_urls[0]
    try:
        # Dossiers via NosDéputés : uniquement pour les sénateurs. Pour les
        # députés, ce résultat est de toute façon écrasé plus bas par l'étape
        # 8bis (fetch_textes_portes_officiels, source officielle AN, propre à
        # chaque élu) — l'appel réseau ici serait fait pour rien, et c'est
        # justement ce point d'appel (dossiers/nom/json) qui pendait
        # régulièrement en CI jusqu'au shutdown du runner (aucun retry, cf.
        # docs/technical_decisions.md#dossiers-legislatifs-nosdeputes-vs-an-officiel).
        if chambre != "deputes" and not skip_dossiers_legislatifs:
            # Les dossiers doivent être demandés sur le domaine où l'identité a
            # réellement été trouvée (donc sa législature) : utiliser systématiquement
            # base_urls[0] (législature courante) renvoie une liste vide pour un
            # parlementaire dont le mandat principal est antérieur (ex. 14e législature).
            dossiers_base_url = identity_base_url or base_urls[0]
            # Cette branche n'est atteinte que pour les sénateurs, dont les
            # domaines (archive.nossenateurs.fr) n'ont jamais figuré dans le
            # mapping domaine -> législature supprimé en #403 : le repli 15/16
            # était donc déjà le seul chemin réellement emprunté ici.
            dossiers_payload = fetch_dossiers_for_legislatures(dossiers_base_url, ["15", "16"])
            time.sleep(0.3)
        # Un parlementaire dont le mandat s'est terminé lors d'une législature
        # précédente (mandat clos) n'a quasiment aucune intervention sur le site de
        # la législature courante : ses interventions réelles sont archivées sur le
        # sous-domaine de sa législature. On sonde donc tous les domaines disponibles
        # pour trouver celui qui contient réellement ses interventions.
        interventions_payload = fetch_all_intervention_results_from_domains(
            base_urls,
            search_candidate_name,
            object_name="Intervention",
            max_pages=0 if skip_interventions else intervention_max_pages,
        )
        interventions_base_url = base_urls[0]
    except Exception as exc:
        pre_profile_warnings.append(f"récupération supplémentaire impossible : {exc}")

    # --- 4. Structure de base du profil, valeurs par défaut si une source manque. ---
    profile: dict[str, Any] = {
        "slug": slug,
        "chambre": chambre,
        "source": f"{identity_base_url or base_urls[0]}/{slug}",
        "identite": None,
        "mandats": [],
        "votes": [],
        "votes_source": None,
        "dossiers_legislatifs": [],
        "amendements": [],
        "interventions": [],
        "meta": {
            "genere_le": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "licence_donnees": "ODbL (Regards Citoyens, à partir de l'Assemblée nationale / Sénat / JO)",
            # Traçabilité de fraîcheur : horodatage ISO-8601 de la dernière synchro
            # réussie pour chaque source (None = source non contactée ou indisponible).
            "synchro_sources": {
                "nosdeputes": None,
                "assemblee_nationale": None,
                "assemblee_nationale_questions": None,
                "assemblee_nationale_syceron": None,
            },
            "warnings": [],
        },
    }

    warnings = profile["meta"]["warnings"]
    warnings.extend(pre_profile_warnings)

    # --- 5. Identité + mandats/responsabilités (commissions, missions, groupes
    # d'amitié...). Depuis #355, l'identité (infos biographiques) des députés est
    # résolue en priorité depuis le référentiel historique officiel de
    # l'Assemblée nationale, par correspondance de nom sur le slug (voir
    # fetch_identite_officielle_par_slug, résolu dès l'étape 0). Depuis #369
    # (étape 4), NosDéputés n'est plus appelé du tout pour un député dès que
    # l'AN a trouvé l'acteur : les mandats commission/groupe_amitie/
    # extra_parlementaire sont sourcés depuis l'AN (_extract_mandats_officiels,
    # organeRef résolu par #353), et le mandat électif de base ainsi que le
    # groupe parlementaire déclaré sont reconstruits ci-dessous depuis
    # identite_an (groupe_sigle/groupe_nom/mandat_debut/mandat_fin/nb_mandats,
    # voir _build_acteur_identite_index) faute d'être normalement sourcés par
    # NosDéputés. NosDéputés reste la source pour les sénateurs (non couverts
    # par l'AN) et en repli complet pour les députés absents des archives AN
    # combinées. ---
    parlementaire = _extract_parlementaire(identity_raw) if isinstance(identity_raw, dict) else None
    parlementaire_valide = isinstance(parlementaire, dict) and not _is_empty_payload(parlementaire)

    if identite_an is None and not parlementaire_valide:
        warnings.append(
            f"{WARNING_PREFIX_IDENTITE_INTROUVABLE} : ni le référentiel officiel Assemblée nationale ni "
            "NosDéputés/NosSénateurs ne renvoient de profil exploitable pour ce slug/chambre."
        )
    else:
        if identite_an is not None:
            profile["meta"]["synchro_sources"]["assemblee_nationale"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        if parlementaire_valide:
            profile["meta"]["synchro_sources"]["nosdeputes"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")

        profile["identite"] = {
            "nom_complet": (identite_an or {}).get("nom_complet") or (parlementaire or {}).get("nom"),
            "groupe_sigle": (parlementaire or {}).get("groupe_sigle") or (identite_an or {}).get("groupe_sigle"),
            "groupe_nom": (
                (parlementaire or {}).get("nom_groupe_politique")
                or _groupe_label((parlementaire or {}).get("groupe"))
                or (identite_an or {}).get("groupe_nom")
            ),
            "profession": (identite_an or {}).get("profession") or (parlementaire or {}).get("profession"),
            "date_naissance": (identite_an or {}).get("date_naissance") or (parlementaire or {}).get("date_naissance"),
            "lieu_naissance": (identite_an or {}).get("lieu_naissance"),
            "num_circo": (
                (parlementaire or {}).get("num_circo")
                or (parlementaire or {}).get("num_deptt")
                or (identite_an or {}).get("numero_circo")
            ),
            "nb_mandats": (parlementaire or {}).get("nb_mandats") or (identite_an or {}).get("nb_mandats"),
            "uri_hatvp": (identite_an or {}).get("uri_hatvp"),
            "url_an_ou_senat": (
                (parlementaire or {}).get("url_an")
                or (parlementaire or {}).get("url_nosdeputes")
                or (_acteur_ref_to_pseudo_url(acteur_ref_an) if acteur_ref_an else None)
            ),
        }

        # Mandats commission/groupe_amitie/extra_parlementaire : sourcés en
        # priorité depuis l'AN (#369) quand l'acteur y est trouvé — NosDéputés
        # ne complète alors que les catégories non couvertes par l'AN (jamais
        # les 3 catégories partagées, pour éviter un doublon du même organisme
        # sous un libellé potentiellement différent).
        mandats_an = _extract_mandats_officiels(acteur_ref_an) if acteur_ref_an else []
        # Depuis #369 (étape 4), NosDéputés n'étant plus appelé quand l'AN a
        # trouvé l'acteur, le mandat électif de base — normalement produit par
        # _extract_mandats(parlementaire) — doit être reconstruit depuis
        # identite_an (mandat_debut/mandat_fin/groupe, voir
        # _build_acteur_identite_index) pour ne pas le perdre silencieusement.
        if not parlementaire_valide and identite_an and identite_an.get("mandat_debut"):
            groupe_label_an = identite_an.get("groupe_nom") or identite_an.get("groupe_sigle")
            mandats_an.append({
                "categorie": "mandat_electif",
                "type": "mandat",
                "label": "Mandat parlementaire" + (f" ({groupe_label_an})" if groupe_label_an else ""),
                "debut": identite_an.get("mandat_debut"),
                "fin": identite_an.get("mandat_fin"),
                "actif": not identite_an.get("mandat_fin"),
            })
        mandats_nosdeputes = _extract_mandats(parlementaire) if parlementaire_valide else []
        if mandats_an:
            categories_an = set(_TYPE_ORGANE_TO_CATEGORIE.values())
            mandats_nosdeputes = [m for m in mandats_nosdeputes if m.get("categorie") not in categories_an]
        profile["mandats"] = mandats_an + mandats_nosdeputes

        if _is_empty_payload(profile["mandats"]):
            if parlementaire_valide or acteur_ref_an:
                warnings.append(
                    f"{WARNING_PREFIX_MANDATS_INTROUVABLES} : aucun mandat/responsabilité trouvé (NosDéputés/"
                    "NosSénateurs et référentiel officiel Assemblée nationale confondus)."
                )
            else:
                warnings.append(
                    f"{WARNING_PREFIX_MANDATS_INTROUVABLES} : candidat absent de NosDéputés/NosSénateurs et du "
                    "référentiel officiel Assemblée nationale."
                )

        # --- 5bis. Positions dans l'hémicycle (Assemblée nationale, référentiel
        # officiel des organes — voir fetch_positions_hemicycle_officielles). Ne
        # couvre que les législatures achevées (positionPolitique jamais qualifié
        # par l'AN pour la législature en cours) pour majorité/opposition/
        # minoritaire : ajoute une entrée de mandat "groupe_politique" par période
        # qualifiée, jamais sans source_url. Ajoute également une entrée de mandat
        # "fonction_gouvernementale" par période d'appartenance à un gouvernement
        # (position "gouvernement"), non limitée aux législatures achevées. ---
        if chambre == "deputes":
            try:
                positions_hemicycle = fetch_positions_hemicycle_officielles(profile["identite"].get("url_an_ou_senat"))
            except Exception as exc:
                warnings.append(f"positions dans l'hémicycle (Assemblée nationale) indisponibles : {exc}")
                positions_hemicycle = []
            for periode in positions_hemicycle:
                sigle = periode.get("groupe_sigle")
                position = periode.get("position")
                if position == "gouvernement":
                    categorie = "fonction_gouvernementale"
                    label = f"Gouvernement ({sigle})" if sigle else "Gouvernement"
                else:
                    categorie = "groupe_politique"
                    label = f"Groupe politique ({sigle})" if sigle else "Groupe politique"
                profile["mandats"].append({
                    "categorie": categorie,
                    "type": "membre",
                    "label": label,
                    "debut": periode.get("debut"),
                    "fin": periode.get("fin"),
                    "actif": not periode.get("fin"),
                    "source_url": AN_ACTEURS_HISTORIQUE_ZIP_URL,
                    "position_dans_hemicycle": position,
                })

    # --- 6. Votes : on privilégie l'open data officiel de l'Assemblée nationale
    # (fiable et à jour) ; pour les sénateurs (pas de source officielle
    # branchée), on retombe sur les champs bruts de NosSénateurs (votes_raw,
    # non interrogé pour les députés — voir étape 1). ---
    official_votes: list[dict[str, Any]] = []
    official_legislatures: list[str] = []
    if chambre == "deputes" and profile.get("identite"):
        try:
            official_votes, official_legislatures = fetch_votes_officiels(
                profile["identite"].get("url_an_ou_senat"), warnings
            )
        except Exception as exc:
            warnings.append(f"votes officiels (Assemblée nationale) indisponibles : {exc}")

    if official_votes:
        profile["votes"] = [
            {
                "date": v.get("date"),
                "titre": v.get("titre"),
                "position": v.get("position"),
                "numero_scrutin": v.get("numero"),
                "sort": v.get("sort"),
                "legislature": v.get("legislature"),
                # Source primaire du scrutin (règle 2). Portée par le vote
                # lui-même et non déduite de `votes_source` : celui-ci couvre
                # désormais plusieurs législatures, dont aucune ne vaut pour
                # tous les votes du profil.
                "url_source": (
                    AN_SCRUTIN_PAGE_URL.format(
                        legislature=v.get("legislature"), numero=v.get("numero")
                    )
                    if v.get("legislature") and v.get("numero")
                    else None
                ),
            }
            for v in official_votes
        ]
        # Reflète l'ENSEMBLE des législatures agrégées : afficher « législature 16 »
        # au singulier alors que plusieurs sont couvertes rendrait la limite du
        # jeu de données illisible (AGENTS.md §2.8).
        libelle_legislatures = (
            f"législature {official_legislatures[0]}"
            if len(official_legislatures) == 1
            else f"législatures {', '.join(official_legislatures)}"
        )
        profile["votes_source"] = (
            f"open data Assemblée nationale (data.assemblee-nationale.fr, {libelle_legislatures})"
        )
        profile["meta"]["synchro_sources"]["assemblee_nationale"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    elif _is_empty_payload(votes_raw):
        if chambre == "deputes":
            warnings.append(
                f"{WARNING_PREFIX_VOTES_INTROUVABLES} : aucune correspondance officielle Assemblée nationale "
                "n'a été trouvée pour ce parlementaire/cette législature (NosDéputés.fr non interrogé pour "
                "les votes, endpoint en panne systématique — voir fetch_votes_officiels)."
            )
        else:
            warnings.append(
                f"{WARNING_PREFIX_VOTES_INTROUVABLES} : l'endpoint /votes de NosSénateurs.fr ne renvoie aucune "
                "donnée exploitable pour ce parlementaire."
            )
    else:
        # On garde uniquement les champs utiles à un affichage type "CV"
        cleaned_votes = []
        votes_payload = votes_raw.get("votes", votes_raw) if isinstance(votes_raw, dict) else votes_raw
        for v in votes_payload:
            if not isinstance(v, dict):
                continue
            scrutin = v.get("vote", v)  # certaines réponses imbriquent sous "vote"
            cleaned_votes.append({
                "date": scrutin.get("date"),
                "titre": scrutin.get("titre") or scrutin.get("title"),
                "position": scrutin.get("position") or scrutin.get("vote"),
                "numero_scrutin": scrutin.get("numero"),
                "url_source": scrutin.get("url_nosdeputes") or scrutin.get("url"),
            })
        profile["votes"] = cleaned_votes
        if _is_empty_payload(profile["votes"]):
            warnings.append(f"{WARNING_PREFIX_VOTES_INTROUVABLES} : aucune information de scrutin n'a été extraite de la réponse API.")

    # --- 6bis. Amendements officiels (Assemblée nationale, auteur principal uniquement,
    # toutes législatures disponibles — voir fetch_amendements_officiels). ---
    if chambre == "deputes" and profile.get("identite"):
        try:
            profile["amendements"] = fetch_amendements_officiels(
                profile["identite"].get("url_an_ou_senat"), warnings
            )
        except Exception as exc:
            warnings.append(f"{WARNING_PREFIX_AMENDEMENTS_INDISPONIBLES} : {exc}")

    if dossiers_payload:
        # --- 8. Dossiers législatifs (sénateurs uniquement, voir étape 3
        # ci-dessus — dossiers_payload reste [] pour les députés), triés du
        # plus récent au plus ancien. ---
        profile["dossiers_legislatifs"] = sorted(
            dossiers_payload,
            key=lambda item: (item.get("date_max") or "", item.get("titre") or ""),
            reverse=True,
        )

    # --- 8bis. Textes portés officiels (Assemblée nationale, rôle factuel
    # auteur/rapporteur/co-rapporteur réel — voir fetch_textes_portes_officiels).
    # Seule source de dossiers législatifs pour les députés (étape 3 : plus
    # d'appel NosDéputés pour cette chambre, voir commentaire à l'appel de
    # fetch_dossiers_for_legislatures). ---
    if chambre == "deputes" and profile.get("identite") and not skip_dossiers_legislatifs:
        try:
            profile["dossiers_legislatifs"] = fetch_textes_portes_officiels(profile["identite"].get("url_an_ou_senat"))
        except Exception as exc:
            warnings.append(f"textes portés officiels (Assemblée nationale) indisponibles : {exc}")

    candidate_name = profile["identite"].get("nom_complet") if profile.get("identite") else slug.replace("-", " ").title()
    candidate_id = None
    if isinstance(identity_raw, dict):
        # --- 9. Interventions : classification prise de parole/mention, format
        # (réaction courte / prise de parole développée), fonction occupée, etc. ---
        parlementaire = _extract_parlementaire(identity_raw)
        if isinstance(parlementaire, dict):
            candidate_id = parlementaire.get("id")

    # --- 9. Interventions : source primaire Syceron (débats officiels AN) pour les
    # députés ; fallback vers le scraping NosDéputés si Syceron ne retourne rien
    # (acteurRef non résolu ou législature hors SYCERON_AVAILABLE_LEGISLATURES).
    # Sénat/PE non couverts par Syceron : chemin NosDéputés uniquement. ---
    if not skip_interventions and chambre == "deputes" and profile.get("identite"):
        try:
            syceron_interventions = fetch_interventions_syceron(profile["identite"].get("url_an_ou_senat"))
        except Exception as exc:
            syceron_interventions = []
            warnings.append(f"{WARNING_PREFIX_INTERVENTIONS_FALLBACK_NOSDEPUTES} : {exc}")
        if syceron_interventions:
            profile["interventions"] = syceron_interventions
            profile["meta"]["synchro_sources"]["assemblee_nationale_syceron"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        else:
            profile["interventions"] = _extract_search_results(interventions_base_url, interventions_payload, candidate_name, candidate_id)
            warnings.append(
                f"{WARNING_PREFIX_INTERVENTIONS_FALLBACK_NOSDEPUTES} : "
                "aucune intervention Syceron trouvée pour cet acteurRef ; "
                "interventions NosDéputés utilisées en fallback."
            )
    else:
        profile["interventions"] = _extract_search_results(interventions_base_url, interventions_payload, candidate_name, candidate_id)

    # --- 9bis. Questions parlementaires officielles (QE/QG/QOSD, Assemblée nationale,
    # auteur uniquement, toutes législatures disponibles). Ajoutées aux interventions
    # déjà collectées (type_detail="question", source AN structurée). ---
    if not skip_interventions and chambre == "deputes" and profile.get("identite"):
        try:
            official_questions = fetch_questions_officielles(profile["identite"].get("url_an_ou_senat"))
            if official_questions:
                profile["interventions"].extend(official_questions)
                profile["meta"]["synchro_sources"]["assemblee_nationale_questions"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        except Exception as exc:
            warnings.append(f"{WARNING_PREFIX_QUESTIONS_INDISPONIBLES} : {exc}")

    return profile


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("slug", help="Identifiant du parlementaire, ex: jean-luc-melenchon")
    parser.add_argument(
        "--chambre",
        choices=["deputes", "senateurs"],
        default="deputes",
        help="Chambre concernée (défaut: deputes)",
    )
    parser.add_argument(
        "--out",
        help="Chemin du fichier JSON de sortie (défaut: raw_data/profiles/<slug>.json)",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=10,
        help="Nombre max. de pages (50 résultats/page) de recherche d'interventions (défaut: 10)",
    )
    args = parser.parse_args()

    profile = build_profile(args.chambre, args.slug, intervention_max_pages=args.max_pages)

    out_path = Path(args.out) if args.out else Path("raw_data/profiles") / f"{args.slug}.json"
    ecrire_profil_json(out_path, profile)

    nb_votes = len(profile["votes"])
    print(f"\n✓ Profil écrit dans {out_path}")
    print(f"  - Identité récupérée : {'oui' if profile['identite'] else 'non'}")
    print(f"  - Votes récupérés : {nb_votes}")
    if profile["meta"].get("warnings"):
        print("  [!] " + " | ".join(profile["meta"]["warnings"]))
    elif nb_votes == 0:
        print("  [!] Aucun vote récupéré : vérifie le slug, la chambre, ou la structure JSON renvoyée par l'API (peut avoir changé).")


if __name__ == "__main__":
    main()
