"""Garde-fou #568 : la vérification d'archivage doit rendre vrai, et surtout
rendre le BON état — sans jamais joindre Software Heritage depuis la CI.

`src/verifier_archivage_swh.py` est le seul outil qui autorise la coupure
d'historique de #434/#551 : il répond « les SHA cités survivront-ils ? ». Deux
façons de se tromper coûtent cher et se ressemblent :

  - **rendre `absente` pour un SHA qu'on n'a pas pu interroger** (quota, réseau)
    ferait renoncer à une coupure légitime, ou pire, ferait relancer un
    archivage complet pour rien ;
  - **rendre `absente` pendant une visite en cours** ferait croire à un échec
    d'archivage là où l'ingestion n'est pas finie — et le contraire,
    **conclure sur une visite non `full`**, autoriserait une coupure sur une
    archive incomplète.

D'où des tests qui portent sur le VERDICT, pas seulement sur le code.

**Aucun de ces tests ne sort sur le réseau** (AGENTS.md §3, et #551 : « aucune
mesure lourde en CI, la vérification d'archivage est un geste de pré-coupure,
pas un contrôle de run »). Toutes les dépendances externes du script — git,
`gh`, le disque, HTTP — sont injectables, et c'est précisément ce qui rend ce
fichier possible. La fixture `_reseau_coupe` de `conftest.py` reste le filet :
un appel réel échouerait bruyamment.
"""

import re
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "src"))

import verifier_archivage_swh as v  # noqa: E402

SCRIPT_BORNAGE = RACINE / "scripts" / "borner_historique_donnees.sh"

# Des SHA de 40 caractères fabriqués, pour que rien ici ne dépende de
# l'historique réel du dépôt : la suite doit rester verte après la coupure
# qu'elle protège.
SHA_A = "a" * 40
SHA_B = "b" * 40


# ── Extraction ───────────────────────────────────────────────────────────────


def test_extraction_prend_sept_caracteres_au_minimum():
    """7 est la longueur d'abrégé que git rend par défaut, et celle des
    citations du dépôt. En dessous, on ratisserait les mots courants."""
    assert v.extraire_chaines("voir deb28a7 pour le détail") == ["deb28a7"]
    assert v.extraire_chaines("le champ abcdef reste vide") == []


def test_extraction_ignore_les_fragments_d_un_mot_plus_long():
    """Sans les gardes lookbehind/lookahead, une chaîne de 41 caractères
    rendrait ses 40 premiers et `deadbeefcafe` sortirait de `xdeadbeefcafe` —
    des SHA inventés qui ne résoudraient jamais et pollueraient le rapport."""
    assert v.extraire_chaines("xdeadbeefcafe") == []
    assert v.extraire_chaines("deadbeefcafez") == []
    assert v.extraire_chaines("a" * 41) == []


def test_extraction_attrape_un_sha_dans_une_url():
    """Une citation dans une URL d'archive est une citation : c'est même la
    forme que prend une vérification par un tiers."""
    url = "https://archive.softwareheritage.org/api/1/revision/deb28a7/"
    assert v.extraire_chaines(url) == ["deb28a7"]


def test_extraction_normalise_la_casse():
    assert v.extraire_chaines("DEB28A7") == []  # majuscules : pas un SHA git
    assert v.extraire_chaines("`deb28a7`") == ["deb28a7"]


def test_les_lieux_md_portent_le_numero_de_ligne():
    """« cité dans docs/technical_decisions.md » envoie chercher dans 2 000
    lignes ; « docs/technical_decisions.md:412 » s'ouvre."""
    fichiers = {"docs/x.md": "rien\nmesuré sur deb28a7\n"}
    citations = v.citations_des_fichiers_md(
        "/racine", lambda p: fichiers[p.removeprefix("/racine/")], fichiers
    )
    assert [(c.chaine, c.lieu) for c in citations] == [("deb28a7", "docs/x.md:2")]


def test_un_fichier_illisible_ne_stoppe_pas_le_balayage():
    """Un fichier suivi mais absent du disque ne doit pas faire renoncer à
    toute la vérification : c'est le genre d'échec qui pousse à sauter
    l'étape."""

    def lire(chemin):
        if chemin.endswith("absent.md"):
            raise OSError("pas là")
        return "voir deb28a7"

    citations = v.citations_des_fichiers_md(
        "/r", lire, ["absent.md", "present.md"]
    )
    assert [c.lieu for c in citations] == ["present.md:1"]


def test_les_lieux_d_issue_portent_le_numero():
    citations = v.citations_des_issues(
        [{"number": 429, "body": "mesuré sur deb28a7"}, {"number": 430, "body": None}]
    )
    assert [(c.chaine, c.lieu) for c in citations] == [("deb28a7", "#429")]


# ── Résolution ───────────────────────────────────────────────────────────────


def test_seuls_les_commits_sont_retenus_et_la_population_est_nommee():
    """Le chiffre qui compte est un rapport, pas un total : « 42 SHA cités sur
    124 chaînes extraites ». Un blob, un tree ou un nombre décimal fait de
    chiffres hexadécimaux passent l'extraction et doivent tomber ici."""
    citations = [
        v.Citation("aaaaaaa", "docs/a.md:1"),
        v.Citation("bbbbbbb", "#12"),
        v.Citation("1787931", "docs/a.md:9"),  # un horodatage, pas un commit
    ]
    commits, nb_chaines = v.resoudre_commits(
        citations,
        lambda chaines: {"aaaaaaa": SHA_A, "bbbbbbb": None, "1787931": None},
    )
    assert nb_chaines == 3
    assert [c.sha for c in commits] == [SHA_A]


def test_une_forme_abregee_et_une_forme_complete_fusionnent():
    """Sinon le même commit serait compté deux fois, et la moitié de ses lieux
    de citation disparaîtrait du rapport de manque."""
    citations = [
        v.Citation("aaaaaaa", "docs/a.md:1"),
        v.Citation(SHA_A, "#12"),
        v.Citation("aaaaaaa", "docs/a.md:1"),  # doublon exact
    ]
    commits, nb_chaines = v.resoudre_commits(
        citations, lambda chaines: {c: SHA_A for c in chaines}
    )
    assert nb_chaines == 2
    assert len(commits) == 1
    assert commits[0].lieux == ["docs/a.md:1", "#12"]


def test_le_rapport_est_ordonne_du_plus_ancien_au_plus_recent():
    """L'ordre dans lequel une coupure les emporte."""
    citations = [v.Citation(SHA_A, "a"), v.Citation(SHA_B, "b")]
    commits, _ = v.resoudre_commits(
        citations,
        lambda chaines: {SHA_A: SHA_A, SHA_B: SHA_B},
        dater=lambda shas: {SHA_A: "2026-08-28", SHA_B: "2026-08-12"},
    )
    assert [c.sha for c in commits] == [SHA_B, SHA_A]


# ── Interrogation de l'API, sans réseau ──────────────────────────────────────


def _quota_neuf():
    return v.Quota()


def test_200_donne_presente_et_404_donne_absente():
    quota = _quota_neuf()
    assert v.interroger_revision(
        SHA_A, lambda url: v.Reponse(200, {}), quota
    )[0] == "presente"
    assert v.interroger_revision(
        SHA_A, lambda url: v.Reponse(404, {}), quota
    )[0] == "absente"


def test_une_panne_reseau_ne_devient_jamais_absente():
    """LA confusion à ne pas faire : ne pas trouver et ne pas avoir regardé
    sont deux choses différentes. La première fait relancer un archivage, la
    seconde fait réessayer."""

    def fetch(url):
        raise ConnectionError("DNS")

    etat, detail = v.interroger_revision(SHA_A, fetch, _quota_neuf())
    assert etat == "indetermine"
    assert "ConnectionError" in detail


def test_un_429_temporise_puis_reessaie_et_le_dit():
    """La limite anonyme est de 120 requêtes/heure. Échouer en silence dessus
    rendrait « absent » un SHA parfaitement archivé."""
    reponses = [
        v.Reponse(429, None, {"X-RateLimit-Reset": "1000", "X-RateLimit-Limit": "120"}),
        v.Reponse(200, {}),
    ]
    dodos, dits = [], []
    etat, _ = v.interroger_revision(
        SHA_A,
        lambda url: reponses.pop(0),
        _quota_neuf(),
        dormir=dodos.append,
        horloge=lambda: 990.0,
        journal=dits.append,
    )
    assert etat == "presente"
    assert dodos == [11.0], "attente mal calculée (reset + 1 s de marge)"
    assert any("attente" in m for m in dits), "temporisation silencieuse"


def test_un_429_persistant_rend_indetermine_jamais_absente():
    etat, detail = v.interroger_revision(
        SHA_A,
        lambda url: v.Reponse(429, None, {"X-RateLimit-Reset": "10"}),
        _quota_neuf(),
        dormir=lambda s: None,
        horloge=lambda: 0.0,
        journal=lambda m: None,
    )
    assert etat == "indetermine"
    assert "429" in detail


def test_l_attente_est_bornee_plutot_que_de_veiller_une_heure():
    """Un lancement de pré-coupure ne doit pas pouvoir se transformer en veille
    silencieuse : au-delà de `--attente-max`, on rend INDÉTERMINÉ."""
    dodos = []
    etat, detail = v.interroger_revision(
        SHA_A,
        lambda url: v.Reponse(429, None, {"X-RateLimit-Reset": "3600"}),
        _quota_neuf(),
        dormir=dodos.append,
        horloge=lambda: 0.0,
        attente_max=60.0,
        journal=lambda m: None,
    )
    assert etat == "indetermine"
    assert dodos == [], "a dormi malgré le plafond d'attente"
    assert "attente-max" in detail or "quota" in detail


def test_le_quota_est_lu_dans_les_entetes_pas_compte_localement():
    """Un compteur local se désynchronise dès qu'un autre outil consomme le
    même quota depuis la même IP — ce qui arrive exactement le jour où l'on
    vérifie à la main en parallèle."""
    quota = _quota_neuf()
    quota.lire({"x-ratelimit-limit": "120", "X-RateLimit-Remaining": "67"})
    assert (quota.limite, quota.restant) == (120, 67)
    quota.lire({"X-RateLimit-Remaining": "pas un nombre"})
    assert quota.restant == 67, "une valeur illisible a écrasé la précédente"


def test_un_seau_vide_declenche_une_attente_preventive_annoncee():
    """Aller chercher le 429 quand la réponse précédente annonçait un seau vide
    gaspille une requête et une minute."""
    quota = v.Quota(limite=120, restant=0, reset=1000)
    dodos, dits = [], []
    etat, _ = v.interroger_revision(
        SHA_A,
        lambda url: v.Reponse(200, {}),
        quota,
        dormir=dodos.append,
        horloge=lambda: 995.0,
        journal=dits.append,
    )
    assert etat == "presente"
    assert dodos == [6.0]
    assert any("quota épuisé" in m for m in dits)


def test_le_seau_de_la_route_visite_ne_contamine_pas_celui_des_revisions():
    """Mesuré le 28/08/2026 : `/origin/.../visit/latest/` annonce 700
    requêtes/heure, `/revision/` en annonce 120. Recopier le premier ferait
    croire au script qu'il a six fois plus de marge qu'en réalité, et la
    temporisation n'arriverait qu'après un `429`."""
    quota = _quota_neuf()
    v.interroger_visite(
        "https://exemple/x",
        lambda url: v.Reponse(
            200,
            {"status": "full", "snapshot": "x", "visit": 1},
            {"X-RateLimit-Limit": "700", "X-RateLimit-Remaining": "699"},
        ),
        quota,
    )
    assert quota.requetes == 1, "la requête n'est pas comptée"
    assert quota.limite is None and quota.restant is None


def test_un_restant_perime_ne_declenche_pas_d_attente():
    """Observé en conditions réelles le 28/08/2026 : vingt « quota épuisé —
    attente de 1 s » d'affilée après un reset, chacun suivi d'une requête qui
    passait très bien.

    `restant` est une photographie de la réponse précédente ; passé
    l'horodatage `reset`, elle est périmée et la seule façon de connaître le
    nouveau compte est d'émettre une requête. Un garde-fou qui crie sans raison
    finit par n'être plus lu — et ce bavardage masquait les deux VRAIES
    temporisations de la même exécution (702 s et 1 504 s)."""
    quota = v.Quota(limite=120, restant=0, reset=1000)
    dodos, dits = [], []
    etat, _ = v.interroger_revision(
        SHA_A,
        lambda url: v.Reponse(200, {}),
        quota,
        dormir=dodos.append,
        horloge=lambda: 1500.0,  # le reset est PASSÉ
        journal=dits.append,
    )
    assert etat == "presente"
    assert dodos == [], "a dormi sur un compteur périmé"
    assert dits == [], "a crié « quota épuisé » sans raison"


def test_le_seau_vide_avant_son_reset_fait_bien_attendre():
    """Le pendant du test précédent : tant que le reset est à venir, le compteur
    est valide et l'attente est la bonne réponse. Sans les deux, la correction
    du bavardage supprimerait la temporisation elle-même."""
    assert v._seau_vide(v.Quota(restant=0, reset=1000), 900.0) is True
    assert v._seau_vide(v.Quota(restant=0, reset=1000), 1100.0) is False
    assert v._seau_vide(v.Quota(restant=5, reset=1000), 900.0) is False
    assert v._seau_vide(v.Quota(restant=None), 900.0) is False


def test_la_visite_est_lue_sans_confondre_inconnue_et_non_full():
    visite = v.interroger_visite(
        "https://exemple/x",
        lambda url: v.Reponse(200, {"status": "partial", "snapshot": None, "visit": 1}),
        _quota_neuf(),
    )
    assert visite["connue"] is True and visite["statut"] == "partial"

    inconnue = v.interroger_visite(
        "https://exemple/x", lambda url: v.Reponse(404, {}), _quota_neuf()
    )
    assert inconnue["connue"] is False


# ── Le verdict : la partie qui décide ────────────────────────────────────────

VISITE_FULL = {"connue": True, "statut": "full", "snapshot": "6ad9782", "visite": 1}
VISITE_EN_COURS = {"connue": True, "statut": "ongoing", "snapshot": None, "visite": 2}


def _commit(sha, etat, atteignable=None):
    return v.CommitCite(sha=sha, lieux=["#429"], etat=etat, atteignable=atteignable)


def test_visite_full_et_tout_resout_autorise_la_coupure():
    code, message = v.rendre_verdict(VISITE_FULL, [_commit(SHA_A, "presente")])
    assert code == v.VERIFIE
    assert "rituel" in message


def test_visite_full_et_sha_atteignable_absent_bloque():
    code, message = v.rendre_verdict(
        VISITE_FULL, [_commit(SHA_A, "presente"), _commit(SHA_B, "absente", True)]
    )
    assert code == v.MANQUANTS
    assert "NE PAS COUPER" in message


def test_visite_non_full_et_sha_absent_est_indetermine_pas_un_manque():
    """L'exigence explicite de #568 : une visite en cours n'est pas un échec
    d'archivage. Les confondre ferait renoncer à une coupure légitime — ou
    l'autoriser à tort."""
    code, message = v.rendre_verdict(
        VISITE_EN_COURS, [_commit(SHA_A, "absente", True)]
    )
    assert code == v.INDETERMINE
    assert "ingestion" in message and "NE PAS COUPER" in message


def test_visite_non_full_mais_tout_resout_reste_verifie():
    """Si tous les SHA cités résolvent déjà, la condition de l'étape 2b est
    remplie, que l'ingestion soit finie ou non : ce qu'on protège, ce sont les
    citations, pas la complétude du snapshot."""
    code, message = v.rendre_verdict(VISITE_EN_COURS, [_commit(SHA_A, "presente")])
    assert code == v.VERIFIE
    assert "ongoing" in message


def test_un_seul_indetermine_suffit_a_ne_pas_conclure():
    code, _ = v.rendre_verdict(
        VISITE_FULL, [_commit(SHA_A, "presente"), _commit(SHA_B, "indetermine")]
    )
    assert code == v.INDETERMINE


def test_une_citation_orpheline_est_signalee_sans_bloquer():
    """Un commit atteignable depuis aucune ref vient d'une branche de PR
    récrite : l'origine ne l'a jamais servi, Software Heritage n'a jamais pu le
    voir, et relancer l'archivage n'y changera rien. Il est déjà irrésolvable
    pour un tiers, donc la coupure ne lui fait rien perdre — le bloquer
    rendrait le garde-fou rouge en permanence, et un rouge permanent n'est plus
    lu.

    Ce n'est pas une hypothèse : `efed279`, cité dans
    `docs/technical_decisions.md`, est dans ce cas au 28/08/2026."""
    orpheline = _commit(SHA_B, "absente", atteignable=False)
    code, message = v.rendre_verdict(
        VISITE_FULL, [_commit(SHA_A, "presente"), orpheline]
    )
    assert orpheline.orpheline is True
    assert code == v.VERIFIE
    assert "orpheline" in message


def test_la_recherche_de_ref_ignore_ce_que_l_origine_ne_sert_pas():
    """« Atteignable » veut dire « atteignable depuis une ref que l'origine
    offre à un archiveur », pas « présent dans ce clone ».

    `refs/pull/<n>/head` en est exclue : GitHub la sert, Software Heritage ne
    l'archive pas. `refs/claude/*` et `refs/stash` aussi : elles n'existent que
    localement, et les compter ferait passer pour un trou d'archive un commit
    que l'origine n'a jamais porté — donc bloquer à tort une coupure légitime.
    """
    familles = v.FAMILLES_DE_REFS_DE_L_ORIGINE
    assert "refs/heads" in familles
    assert "refs/remotes/origin" in familles
    assert not [f for f in familles if f.startswith("refs/pull")]
    assert not [f for f in familles if "claude" in f or "stash" in f]


def test_une_population_vide_ne_vaut_pas_un_succes():
    """Si l'extraction rend zéro SHA, il n'y a rien à conclure — et surtout pas
    « tout va bien ». C'est le mode de panne d'une expression régulière cassée."""
    code, _ = v.rendre_verdict(VISITE_FULL, [])
    assert code == v.INDETERMINE


# ── Bout en bout, entièrement simulé ─────────────────────────────────────────


def _verifier_simule(reponses_par_sha, visite_corps, **kwargs):
    md = {"docs/journal.md": f"mesuré sur {SHA_A[:7]}\nvoir aussi {SHA_B[:7]}\n"}

    def fetch(url):
        if "/visit/latest/" in url:
            return v.Reponse(200, visite_corps)
        sha = url.rstrip("/").rsplit("/", 1)[-1]
        return v.Reponse(reponses_par_sha[sha], {})

    return v.verifier(
        "/r",
        fetch=fetch,
        lire=lambda p: md[p.removeprefix("/r/")],
        lister_md=lambda: list(md),
        lister_issues=lambda: [{"number": 429, "body": f"régression à {SHA_B[:7]}"}],
        batch_check=lambda chaines: {
            SHA_A[:7]: SHA_A, SHA_B[:7]: SHA_B,
        },
        dater=lambda shas: {SHA_A: "2026-08-12T00:00:00+02:00",
                            SHA_B: "2026-08-20T00:00:00+02:00"},
        journal=lambda m: None,
        **kwargs,
    )


def test_bout_en_bout_nomme_le_manquant_et_ou_il_est_cite():
    """La demande centrale de #568 : « 3 manquants » n'aide personne ;
    « `deb28a7`, cité dans #429, ne résout pas » se traite."""
    code, donnees, texte = _verifier_simule(
        {SHA_A: 200, SHA_B: 404},
        {"status": "full", "snapshot": "6ad9782", "visit": 1},
        ref_contenant=lambda sha: "refs/heads/main",
    )
    assert code == v.MANQUANTS
    assert SHA_B[:7] in texte
    assert "#429" in texte and "docs/journal.md:2" in texte
    assert SHA_A[:7] not in texte, "un SHA présent n'a pas à encombrer le rapport"
    assert donnees["population"]["sha_resolus_en_commit"] == 2


def test_bout_en_bout_nomme_la_population_de_chaque_chiffre():
    """Un total sans population est ininterprétable — c'est l'erreur que ce
    dépôt corrige le plus souvent."""
    _, donnees, texte = _verifier_simule(
        {SHA_A: 200, SHA_B: 200}, {"status": "full", "snapshot": "x", "visit": 1}
    )
    assert "chaînes hexadécimales extraites" in texte
    assert "fichier .md suivi" in texte and "corps d'issue" in texte
    assert "commentaires d'issues EXCLUS" in texte, (
        "la réserve de périmètre doit être dans la sortie, pas seulement dans "
        "le code : c'est la sortie qu'on lit avant de couper"
    )
    assert donnees["population"] == {
        "chaines_extraites": 2,
        "fichiers_md": 1,
        "issues": 1,
        "sha_resolus_en_commit": 2,
    }


def test_bout_en_bout_le_quota_apparait_dans_la_sortie():
    _, _, texte = _verifier_simule(
        {SHA_A: 200, SHA_B: 200}, {"status": "full", "snapshot": "x", "visit": 1}
    )
    assert "quota" in texte and "3 requêtes émises" in texte


def test_gh_indisponible_degrade_le_perimetre_sans_echouer():
    """`gh` absent ou non authentifié ne doit pas faire échouer la
    vérification : un demi-périmètre annoncé vaut mieux qu'un échec qui pousse
    à sauter l'étape juste avant une opération irréversible."""

    def lister_issues():
        raise FileNotFoundError("gh")

    code, donnees, _ = v.verifier(
        "/r",
        fetch=lambda url: v.Reponse(200, {"status": "full", "snapshot": "x", "visit": 1}),
        lire=lambda p: f"mesuré sur {SHA_A[:7]}",
        lister_md=lambda: ["docs/journal.md"],
        lister_issues=lister_issues,
        batch_check=lambda chaines: {SHA_A[:7]: SHA_A},
        dater=lambda shas: {},
        journal=lambda m: None,
    )
    assert code == v.VERIFIE
    assert donnees["population"]["issues"] == 0


# ── Branchement dans la procédure de bornage ─────────────────────────────────


def test_l_etape_2b_appelle_le_script_et_non_une_boucle_curl():
    """#568 : « la vérification est un geste manuel décrit en prose […] elle
    sera faite sous pression, juste avant une opération irréversible ». Une
    boucle `curl` à recopier n'est pas une commande à lancer.

    La boucle remplacée itérait de surcroît sur `git log --format=%H`, soit
    tout l'historique — 677 commits pour un quota de 120 requêtes/heure."""
    texte = SCRIPT_BORNAGE.read_text(encoding="utf-8")
    assert "verifier_archivage_swh.py" in texte, "étape 2b non branchée"
    assert "|| echo \"MANQUANT" not in texte, "boucle curl en prose toujours là"
    assert "for sha in $(git log --format=%H)" not in texte


def test_le_script_de_bornage_n_execute_pas_la_verification():
    """L'étape 2b vit dans le `cat <<FIN` d'instructions, jamais dans le code.

    Deux raisons. `--preparer` s'exécute AVANT que « Save Code Now » soit
    déclenché (étape 2a) : appelée là, la vérification échouerait toujours. Et
    faire sortir sur le réseau un script dont la garantie centrale est de ne
    rien pousser élargirait sa surface sans rien prouver."""
    lignes_de_code, dans_heredoc = [], False
    for ligne in SCRIPT_BORNAGE.read_text(encoding="utf-8").split("\n"):
        if dans_heredoc:
            dans_heredoc = ligne.strip() != "FIN"
            continue
        if "<<FIN" in ligne:
            dans_heredoc = True
            continue
        if not ligne.lstrip().startswith("#"):
            lignes_de_code.append(ligne)
    code = "\n".join(lignes_de_code)
    assert "verifier_archivage_swh" not in code, (
        "la vérification est exécutée par le script de bornage : elle doit "
        "rester une commande que l'humaine lance après l'archivage"
    )
    assert "curl" not in code, "le script de bornage sort sur le réseau"


def test_aucun_workflow_n_appelle_la_verification():
    """#551 a tranché : aucune mesure lourde en CI, et la vérification
    d'archivage est un geste de pré-coupure, pas un contrôle de run. La brancher
    dans un workflow consommerait le quota anonyme partagé de 120 requêtes/heure
    à chaque push, et ferait échouer des jobs sur l'état d'un service tiers."""
    for workflow in (RACINE / ".github" / "workflows").glob("*.yml"):
        assert "verifier_archivage_swh" not in workflow.read_text(encoding="utf-8"), (
            f"{workflow.name} invoque la vérification d'archivage"
        )


def test_le_script_ne_sort_sur_le_reseau_qu_en_un_seul_point():
    """Tout le reste est injectable — c'est ce qui rend ce fichier de tests
    possible sans jamais joindre l'API. Si un second `requests` apparaissait
    ailleurs, la suite pourrait se mettre à sortir sans qu'on le voie."""
    source = (RACINE / "src" / "verifier_archivage_swh.py").read_text(encoding="utf-8")
    imports = re.findall(r"^\s*(?:import|from) +requests\b.*$", source, re.MULTILINE)
    assert len(imports) == 1, f"import de requests attendu une fois : {imports}"
    # Et il doit être DANS `_fetch_reel`, pas au sommet du module : un import
    # de module rendrait l'unique point de sortie moins évident à retrouver.
    assert imports[0].startswith("    "), "requests importé au niveau du module"
    avant_fetch = source.split("def _fetch_reel")[0]
    assert "requests" not in avant_fetch.split("BASE_SWH")[-1]


@pytest.mark.parametrize("option", ["--sans-issues", "--attente-max", "--json"])
def test_les_options_citees_dans_l_etape_2b_existent(option):
    """L'étape 2b nomme `--sans-issues` et `--json` ; l'en-tête nomme
    `--attente-max`. Une option citée dans une procédure irréversible et
    absente du script ferait perdre le seul lancement disponible avant la
    coupure — et on ne le découvrirait qu'à ce moment-là."""
    aide = v.construire_parseur().format_help()
    assert option in aide, f"{option} annoncée mais absente du script"


def test_les_defauts_du_parseur_ne_font_rien_d_irreversible():
    """Un lancement sans argument lit et interroge ; il n'écrit nulle part."""
    defauts = vars(v.construire_parseur().parse_args([]))
    assert defauts["json_out"] is None
    assert defauts["sans_issues"] is False
    assert defauts["origine"] == v.ORIGINE_PAR_DEFAUT
