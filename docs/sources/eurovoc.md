# EuroVoc — le thésaurus qui donne un nom aux matières européennes

> **Statut : vivant, interrogé depuis le 16/09/2026 (#901).** Une seule chose
> lui est demandée : le **libellé français** d'un concept dont le Parlement
> européen a déjà donné l'identifiant. Rien n'est découvert ici, rien n'est
> classé ici.

## Ce que le fournisseur publie

EuroVoc est le thésaurus multilingue et multidisciplinaire de l'Union
européenne, géré par l'**Office des publications**. Chaque concept porte un
identifiant numérique et un libellé dans une vingtaine de langues.

| | |
| --- | --- |
| Point d'accès | `https://publications.europa.eu/webapi/rdf/sparql` |
| Forme d'un concept | `http://eurovoc.europa.eu/2155` → « opposition politique » |
| Propriété lue | `skos:prefLabel`, filtrée sur `lang = "fr"` |
| Licence | **CC BY 4.0** — attribution, et indication des modifications |

## Ce que nous en faisons, et ce que nous n'en faisons pas

**Nous ne collectons pas EuroVoc.** Les concepts d'un document viennent du
portail du Parlement (`is_about`), dans la réponse que `ResolveurDocuments`
télécharge déjà. EuroVoc n'est interrogé que pour **traduire un identifiant en
mot lisible** — sans quoi une fiche afficherait « 2155 ».

**Nous ne classons rien nous-mêmes.** La matière d'un document est un fait du
Parlement, pas une lecture que nous ferions de son titre. C'est la condition
pour qu'elle soit publiable (§2 règles 2 et 8).

## Le piège : une requête par concept, ou une pour cent

Le point SPARQL accepte `VALUES` : une requête rend une centaine de libellés
d'un coup. Mesuré le 16/09/2026 — **4 concepts en 0,22 s**. Interroger concept
par concept multiplierait les appels par cent pour le même résultat, et c'est ce
que `resoudre_libelles()` évite par construction (`LOT_SPARQL = 100`).

## Le second piège : un code sans libellé

Un identifiant que le thésaurus ne rend pas n'est **jamais inventé ni deviné**.
Le document garde les libellés trouvés et déclare les autres —
`matieres_non_resolu.motif = "libelle_eurovoc_introuvable"`, avec les codes
concernés. Une matière perdue en silence serait indétectable.

Si EuroVoc ne répond pas du tout, `resoudre_libelles()` **lève** au lieu de
rendre des codes nus : un index de matières illisibles vaut moins que pas
d'index.

## Attribution

Le fichier produit le dit dans son entête, et les deux sources y sont nommées
ensemble :

```
"licence_donnees": "Parlement européen (data.europarl.europa.eu, attribution) ;
                    EuroVoc — Office des publications de l'Union européenne, CC BY 4.0"
```

→ `docs/decisions/matieres-eurovoc-documents-901.md`, `AGENTS.md` §7.
