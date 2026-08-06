# Syceron AN — Cartographie des URLs et stratégie d'intégration

Complète `an_opendata.md` pour la famille de données **comptes rendus de séance**
(système Syceron / SyceronBrut) de l'Assemblée nationale.

## Résumé exécutif

| Législature | Statut | URL | Taille ZIP | Dernière mise à jour |
|---|---|---|---|---|
| 13 (2007-2012) | ❌ Non disponible | — | — | — |
| 14 (2012-2017) | ❌ Non disponible | — | — | — |
| 15 (2017-2022) | ✅ Disponible (archivé) | `…/15/vp/syceronbrut/syseron.xml.zip` | ~149 MB | 09/06/2022 |
| 16 (2022-2024) | ✅ Disponible (archivé) | `…/16/vp/syceronbrut/syseron.xml.zip` | ~57 MB | 28/06/2024 |
| 17 (2024-) | ✅ Disponible (live, quotidien) | `…/17/vp/syceronbrut/syseron.xml.zip` | ~56 MB | quotidien |

Le préfixe commun est :
```
https://data.assemblee-nationale.fr/static/openData/repository/{legislature}/vp/syceronbrut/syseron.xml.zip
```

> **Attention casse** : le chemin utilise `vp` (minuscule) et le fichier s'appelle
> `syseron.xml.zip` (pas `syceronBrut.xml.zip` ni `Syceron.xml.zip`).
> Les variantes `VP/` (majuscule) retournent 404.

## Structure du ZIP et format XML

Chaque ZIP contient un répertoire `xml/compteRendu/` avec un fichier XML par séance.

Nom de fichier type : `CRSANR5L17S2025O1N001.xml`  
Décodage : `CRS` (Compte Rendu Séance) · `AN` (Assemblée nationale) · `R5` (Cinquième République) · `L17` (législature 17) · `S2025O1` (session ordinaire 2025) · `N001` (numéro de séance).

L17 contient **601 fichiers** (au 06/08/2026) ; à titre de comparaison L15 est la plus
dense (~149 MB, législature complète de 5 ans).

### Champs clés dans le XML

```xml
<compteRendu xmlns="http://schemas.assemblee-nationale.fr/referentiel">
  <uid>CRSANR5L17S2025O1N001</uid>
  <seanceRef>RUANR5L17S2025IDS28577</seanceRef>   <!-- clé de jointure vers reunionsAN -->
  <sessionRef>SCR5A2025O1</sessionRef>
  <metadonnees>
    <dateSeance>20241001150000000</dateSeance>
    <legislature>17</legislature>
    <validite>valide</validite>
    <etat>complet</etat>                          <!-- "complet" | "provisoire" -->
    <version>avant_JO</version>                   <!-- "avant_JO" | "JO" -->
  </metadonnees>
  <!-- … contenu des débats (orateurs, tours de parole, textes) … -->
</compteRendu>
```

Le champ `<seanceRef>` permet de joindre avec le dataset `reunionsAN` (agenda/réunions).

## Stratégie de téléchargement : full dump recommandé

**Décision : full dump unique par législature**, pas de téléchargement ciblé par séance.

Justification :
- Le ZIP est auto-contenu et re-publié quotidiennement pour L17 — un seul GET remplace toute la législature en cours.
- Les ZIP sont raisonnables en taille (55–149 MB) ; un téléchargement ciblé par identifiant de séance nécessiterait de connaître les UIDs à l'avance sans API d'index.
- Le pattern est identique aux dumps scrutins/amendements déjà utilisés dans `candidate_profile.py`.
- Pour L15 (archivé), le fichier est figé — un download unique suffit ; aucune raison de répéter le fetch.

**Mise en cache** : même logique que les autres dumps AN (`.cache/` avec vérification
`Last-Modified` ou ETag) — évite le re-téléchargement si le fichier n'a pas changé.

## Recommandation de périmètre — priorité d'intégration

| Priorité | Législature | Justification |
|---|---|---|
| 🟢 P1 | **17** | Législature courante, données quotidiennes, candidats 2027 actifs |
| 🟡 P2 | **16** | Législature récente (2022-2024), couverture directe des mandats candidats |
| 🔵 P3 | **15** | Intéressant pour la profondeur historique ; gros dump (~149 MB) |
| ⛔ — | 13, 14 | Aucun dataset Syceron open data disponible (404 vérifié) |

Pour le périmètre **Empreinte politique 2027**, P1 + P2 couvrent l'intégralité des
mandats des candidats actifs. L15 peut être ajouté si la profondeur historique est requise.

## Utilisation envisagée

Les comptes rendus Syceron permettent d'enrichir les `interventions[]` du pivot avec :
- le texte intégral des prises de parole (au-delà des métadonnées NosDéputés)
- les orateurs identifiés par leur `id_syceron` (à croiser avec l'acteurRef AN)
- le type d'intervention dans le contexte de séance (débat général, questions, etc.)

L'intégration reste **hors périmètre immédiat** (voir `ROADMAP.md` et
`technical_decisions.md#hors-perimetre`) — cette page documente la cartographie
pour préparer l'implémentation future.

## Vérification de disponibilité (audit du 06/08/2026)

```
curl -I https://data.assemblee-nationale.fr/static/openData/repository/15/vp/syceronbrut/syseron.xml.zip
# → HTTP/2 200, content-length: 148954869, last-modified: Thu, 09 Jun 2022

curl -I https://data.assemblee-nationale.fr/static/openData/repository/16/vp/syceronbrut/syseron.xml.zip
# → HTTP/2 200, content-length: 57553703, last-modified: Fri, 28 Jun 2024

curl -I https://data.assemblee-nationale.fr/static/openData/repository/17/vp/syceronbrut/syseron.xml.zip
# → HTTP/2 200, content-length: 55772428, last-modified: Thu, 06 Aug 2026 (quotidien)

curl -I https://data.assemblee-nationale.fr/static/openData/repository/14/vp/syceronbrut/syseron.xml.zip
# → HTTP/2 404

curl -I https://data.assemblee-nationale.fr/static/openData/repository/13/vp/syceronbrut/syseron.xml.zip
# → HTTP/2 404
```
