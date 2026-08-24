"""Le roster complet a son propre plafond de lecture (#518, second incident).

## Ce que ces tests protègent

Run `32750929942` (24/08/2026) : les 22 autres jobs verts, `merge-and-pivot`
tombé sur `Générer les profils de groupe parlementaire réel` en **56 s**, sans
avoir écrit une seule fiche. Le budget de temps désigne la cause : 3 × 15 s de
timeout + 2 s + 4 s de backoff = 51 s, plus le démarrage. Les trois tentatives
ajoutées par #519 avaient été **épuisées**.

Elles l'ont été parce que `fetch_full_roster` héritait de
`candidate_profile.TIMEOUT` (15 s), une constante dimensionnée pour les pages
**par candidat** — quelques Ko, servies depuis un cache. `/deputes/json` fait
814 Ko et est généré à la volée : son coût est presque tout entier du
time-to-first-byte. Mesuré le 24/08 sur 24 appels : **aucune réponse sous
10 s**, la plus rapide à 10,7 s, médiane des succès ~16,7 s — 0 succès sur 8 à
`timeout=15`, 3 sur 8 à `timeout=30`.

Le plafond de production était donc **à l'intérieur** de la distribution de
réponse de l'endpoint. C'est le point que ces tests figent : retenter trois
fois sous un plafond mal placé ne rachète pas le plafond.

Et la moitié CONNECT ne bouge pas, délibérément : c'est elle qu'emprunte la
détection déterministe de #516 (poignée de main TLS → `SSLError`), et un
verdict qui fonde une suspension d'extraction doit remonter vite.
"""

import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import group_roster
from candidate_profile import TIMEOUT as TIMEOUT_PAR_CANDIDAT


def test_le_plafond_du_roster_est_separe_en_connect_et_read():
    """Même forme que `gouvernement_textes.TIMEOUT` et `syceron_debates.TIMEOUT`,
    les deux autres gros téléchargements du dépôt."""
    assert isinstance(group_roster._ROSTER_TIMEOUT, tuple)
    assert len(group_roster._ROSTER_TIMEOUT) == 2


def test_le_connect_reste_celui_des_pages_par_candidat():
    """LE test de ce fichier avec le suivant.

    Desserrer le connect retarderait le `SSLError` sur lequel #516 s'est appuyé
    pour décider d'une suspension. Seule la LECTURE avait besoin d'air.
    """
    connect, _read = group_roster._ROSTER_TIMEOUT
    assert connect == TIMEOUT_PAR_CANDIDAT


def test_le_read_est_au_dessus_de_la_distribution_mesuree():
    """15 s tombait au milieu des réponses observées (10,7 à 18,1 s) ; 30 s
    seulement au-dessus de la médiane. Le plafond doit laisser passer la queue
    de distribution, pas la trancher."""
    _connect, read = group_roster._ROSTER_TIMEOUT
    assert read > TIMEOUT_PAR_CANDIDAT
    assert read >= 60, (
        "un plafond de lecture au voisinage des latences mesurées (10-18 s) "
        "refait du fetch de roster un pari (#518)."
    )


def test_le_pire_cas_reste_tres_sous_le_timeout_du_job():
    """3 tentatives × read + backoff : ~4,5 min sur un job qui en a 60."""
    _connect, read = group_roster._ROSTER_TIMEOUT
    backoff = sum(
        group_roster._ROSTER_RETRY_BACKOFF_SECONDS * n
        for n in range(1, group_roster._ROSTER_MAX_ATTEMPTS)
    )
    pire_cas = group_roster._ROSTER_MAX_ATTEMPTS * read + backoff
    assert pire_cas < 15 * 60


def test_fetch_full_roster_applique_ce_plafond_et_pas_celui_des_candidats(monkeypatch):
    """Le test qui rend les précédents utiles : la constante peut être juste et
    l'appel continuer d'utiliser l'autre."""
    vus = []

    class _Reponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"deputes": []}

    def faux_get(url, headers=None, timeout=None):
        vus.append(timeout)
        return _Reponse()

    monkeypatch.setattr(group_roster.requests, "get", faux_get)

    group_roster.fetch_full_roster("deputes", legislature="16")

    assert vus == [group_roster._ROSTER_TIMEOUT]
    assert vus != [TIMEOUT_PAR_CANDIDAT]


def test_un_read_timeout_reste_retentable_sous_le_nouveau_plafond():
    """Relever le plafond ne change pas la ligne de partage de #519 : un
    dépassement de lecture reste transitoire, un certificat reste définitif."""
    assert group_roster._erreur_retentable(requests.exceptions.ReadTimeout("Read timed out"))
    assert not group_roster._erreur_retentable(requests.exceptions.SSLError("certificate expired"))
