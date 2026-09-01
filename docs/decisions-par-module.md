# Les décisions qui gouvernent chaque module

**Fichier généré — ne pas le modifier à la main.**
`python3 scripts/generer_decisions_par_module.py` le réécrit ;
`tests/test_decisions_par_module.py` échoue s'il a dérivé.

[`docs/technical_decisions.md`](technical_decisions.md) va des décisions vers le
code et se lit par date. Cette table va dans l'autre sens : **ce module → ces
décisions**, pour qu'un agent qui ouvre un fichier de `src/` sache ce qui le
gouverne sans avoir à fouiller les 203 décisions
du répertoire. Le critère, ce qu'il rate et pourquoi la table est générée :
[`docs/decisions/table-inversee-decisions-par-module.md`](decisions/table-inversee-decisions-par-module.md).

## Ce que « gouverne » veut dire ici

Une décision **gouverne** un module quand elle nomme **un symbole de tête de ce
module** — une fonction, une classe ou une constante définie au niveau du module —
soit qualifié (`merge_profile.fusionner_couverture`), soit nu à condition que ce
symbole soit défini dans ce seul module de `src/`. La colonne « nomme » dit
lesquels.

Une décision qui ne nomme que le **fichier** (`merge_profile.py`) ou le module nu
le **mentionne** sans le gouverner : elle dit qu'il est concerné, pas quel contrat
il doit tenir. Ces décisions-là sont listées à part, en fin de section.

Le critère est mécanique et volontairement faillible dans un sens précis : il rate
une décision qui gouverne un module sans nommer aucune de ses fonctions. En
échange il ne rouille pas — un symbole renommé ou supprimé retire le lien au lieu
de le laisser pointer vers du code qui n'existe plus.

---

## Les modules qui ne citent aucune de leurs décisions

Ce que ce fichier existe pour rendre visible. `tests/test_decisions_par_module.py`
échoue au-delà du seuil qu'il fixe.

| Module | Décisions qui le gouvernent |
| --- | ---: |
| `src/groupes_config.py` | 4 |
| `src/budget_collecte.py` | 3 |
| `src/normalize_parltrack_dumps.py` | 3 |
| `src/profil_brut.py` | 3 |
| `src/schema_groupe.py` | 3 |
| `src/scrutins_index.py` | 3 |
| `src/audit_gouvernement_dataset.py` | 2 |
| `src/audit_pipeline.py` | 2 |
| `src/gouvernement_profile.py` | 2 |
| `src/parse_syceron.py` | 2 |
| `src/avertissements.py` | 1 |
| `src/build_amendements_index.py` | 1 |
| `src/candidate_profile_ue.py` | 1 |
| `src/json_io.py` | 1 |
| `src/licences.py` | 1 |
| `src/purge_mandats_dupliques.py` | 1 |
| `src/scrutins_legislature.py` | 1 |
| `src/textes_vises_figes.py` | 1 |

---

## `src/amendements_index.py`

2 décision(s) le gouvernent ; le module en cite 1.

| Décision | Nomme |
| --- | --- |
| [Un amendement retrouve son dossier, et la clé qu'on lui avait retirée (#639, rang 3)](decisions/dossier-des-amendements-639.md) | `AmendementsIndex`, `resoudre_textes` |
| [Le `texte_vise` fautif se reprend depuis l'archive figée, pas par une fusion plus permissive (#696, 01/09/2026)](decisions/report-texte-vise-source-696.md) | `backfill_texte_vise`, `merge_amendements_index`, `resoudre_textes` |

Le mentionnent sans le gouverner : [`lectures-pipeline-par-projection-635`](decisions/lectures-pipeline-par-projection-635.md), [`normalisation-amendements`](decisions/normalisation-amendements.md), [`partition-profils-legislature-580`](decisions/partition-profils-legislature-580.md), [`point-de-sauvegarde-dans-les-profils-518`](decisions/point-de-sauvegarde-dans-les-profils-518.md).

## `src/an_roster.py`

6 décision(s) le gouvernent ; le module en cite 3.

| Décision | Nomme |
| --- | --- |
| [La bascule : le roster des groupes AN vient d'AMO30 (#527, lot 1b de l'épic « une seule source AN ») (2026-08-26)](decisions/bascule-roster-an-amo30-527.md) | `AN_ROSTER_ACTIF`, `RosterAnInactif`, `RosterAnIndisponible`, `fetch_full_roster_an` |
| [`debut_dans_groupe` se lit sur le mandat de groupe, plus sur le premier mandat électif (#653) (2026-08-31)](decisions/dates-appartenance-groupe-653.md) | `deriver_membres_organes`, `organes_du_groupe` |
| [La position politique d'un groupe est celle que l'Assemblée déclare, lue dans une table committée (#686) (2026-09-01)](decisions/position-politique-groupes-686.md) | `VERSION_INDEX_GP` |
| [NosDéputés sort du pipeline (#529, lot 5 de l'épic « une seule source AN ») (2026-08-27)](decisions/retrait-nosdeputes-529.md) | `AN_ROSTER_ACTIF`, `RosterAnInactif` |
| [Le Sénat sort du périmètre, et le job qui concluait vert sans rien produire est retiré (#528, lot 3 de l'épic « une seule source AN ») (2026-08-26)](decisions/retrait-senat-528.md) | `AN_ROSTER_ACTIF` |
| [Le roster des groupes AN est dérivé d'AMO30, derrière un drapeau baissé (#526, lot 1 de l'épic « une seule source AN ») (2026-08-26)](decisions/roster-an-derive-amo30-526.md) | `AN_ROSTER_ACTIF`, `RosterAnIndisponible`, `fetch_full_roster_an` |

## `src/audit_collecte_non_publiee.py`

Le mentionnent sans le gouverner : [`cle-fusion-interventions-540`](decisions/cle-fusion-interventions-540.md), [`cloisonnement-branche-roster-524`](decisions/cloisonnement-branche-roster-524.md), [`collecte-non-publiee`](decisions/collecte-non-publiee.md), [`collecte-vs-publie-545`](decisions/collecte-vs-publie-545.md), [`extraction-groupe-suspendue-516`](decisions/extraction-groupe-suspendue-516.md), [`partition-profils-legislature-580`](decisions/partition-profils-legislature-580.md), [`roster-unique-par-run-518`](decisions/roster-unique-par-run-518.md).

## `src/audit_collecte_vs_publie.py`

1 décision(s) le gouvernent ; le module en cite 1.

| Décision | Nomme |
| --- | --- |
| [Le seuil de blob sort du critère de sortie, et les profils bruts se partitionnent par législature (#580) (2026-08-29)](decisions/partition-profils-legislature-580.md) | `compter_listes_profil_brut` |

Le mentionnent sans le gouverner : [`cle-fusion-textes-portes-668`](decisions/cle-fusion-textes-portes-668.md), [`collecte-vs-publie-545`](decisions/collecte-vs-publie-545.md), [`defaut-collecte-vs-panne-562`](decisions/defaut-collecte-vs-panne-562.md), [`dossier-des-amendements-639`](decisions/dossier-des-amendements-639.md), [`populations-profils-portees-par-les-outils-630`](decisions/populations-profils-portees-par-les-outils-630.md), [`qualification-scrutins-et-cle-dossier-639`](decisions/qualification-scrutins-et-cle-dossier-639.md).

## `src/audit_diff_profils.py`

4 décision(s) le gouvernent ; le module en cite 2.

| Décision | Nomme |
| --- | --- |
| [Les agrégats publiés entrent dans le contrôle de perte, et l'ordre de grandeur reste hors contrat (#649) (2026-08-31)](decisions/agregats-publies-controle-perte-649.md) | `_resume_scalaire` |
| [Un amendement cosigné n'est pas N amendements : deux grandeurs, deux noms (#643) (2026-08-31)](decisions/amendements-distincts-et-signatures-643.md) | `COLLECTION_GROUPES`, `Collection` |
| [L'`id` d'un profil pivot est le slug : le préfixe de provenance était instable (#487) (2026-08-20)](decisions/id-pivot-sans-prefixe.md) | `COLLECTION_PROFILS` |
| [Le libellé d'organe du chef du gouvernement s'accorde en genre, la qualité jamais (#658) (2026-08-31)](decisions/libelle-chef-du-gouvernement-au-feminin-658.md) | `COLLECTION_GOUVERNEMENTS` |

Le mentionnent sans le gouverner : [`bascule-roster-an-amo30-527`](decisions/bascule-roster-an-amo30-527.md), [`cache-amendements-existence-nest-pas-conformite`](decisions/cache-amendements-existence-nest-pas-conformite.md), [`chambres-profil-derivees`](decisions/chambres-profil-derivees.md), [`civilite-et-pcs-insee-659`](decisions/civilite-et-pcs-insee-659.md), [`cle-fusion-interventions-540`](decisions/cle-fusion-interventions-540.md), [`cle-fusion-textes-portes-668`](decisions/cle-fusion-textes-portes-668.md), [`collecte-interventions-reduite-au-theme-657`](decisions/collecte-interventions-reduite-au-theme-657.md), [`collecte-non-publiee`](decisions/collecte-non-publiee.md), [`collecte-vs-publie-545`](decisions/collecte-vs-publie-545.md), [`consommateurs-chambres-migres`](decisions/consommateurs-chambres-migres.md), [`controle-de-perte-avant-commit`](decisions/controle-de-perte-avant-commit.md), [`correspondance-acteurs-an-525`](decisions/correspondance-acteurs-an-525.md), [`date-de-reference-des-comptes-de-groupe-653`](decisions/date-de-reference-des-comptes-de-groupe-653.md), [`dates-appartenance-groupe-653`](decisions/dates-appartenance-groupe-653.md), [`destinataire-avertissements-642`](decisions/destinataire-avertissements-642.md), [`dossier-des-amendements-639`](decisions/dossier-des-amendements-639.md), [`extraction-groupe-suspendue-516`](decisions/extraction-groupe-suspendue-516.md), [`fenetre-historique-donnees`](decisions/fenetre-historique-donnees.md), [`fenetre-recalibrage-551`](decisions/fenetre-recalibrage-551.md), [`filtre-publication-apres-fusion-641`](decisions/filtre-publication-apres-fusion-641.md), [`identite-profils-539`](decisions/identite-profils-539.md), [`licence-lot-6-530`](decisions/licence-lot-6-530.md), [`mandat-electif-perdu-fausse-le-denominateur`](decisions/mandat-electif-perdu-fausse-le-denominateur.md), [`mandats-agreges-siege-vs-passe-656`](decisions/mandats-agreges-siege-vs-passe-656.md), [`mandats-electifs-liste-complete-640`](decisions/mandats-electifs-liste-complete-640.md), [`overwrite-profiles-sans-purge-cache`](decisions/overwrite-profiles-sans-purge-cache.md), [`partition-profils-legislature-580`](decisions/partition-profils-legislature-580.md), [`profession-code-nomenclature-641`](decisions/profession-code-nomenclature-641.md), [`publication-dun-job-annule`](decisions/publication-dun-job-annule.md), [`publication-scopee-artifacts`](decisions/publication-scopee-artifacts.md), [`qualification-perdue-a-la-fusion-639`](decisions/qualification-perdue-a-la-fusion-639.md), [`qualification-scrutins-et-cle-dossier-639`](decisions/qualification-scrutins-et-cle-dossier-639.md), [`qualification-textes-portes-689`](decisions/qualification-textes-portes-689.md), [`restauration-interventions`](decisions/restauration-interventions.md), [`retrait-nosdeputes-529`](decisions/retrait-nosdeputes-529.md), [`retrait-senat-528`](decisions/retrait-senat-528.md), [`roster-an-derive-amo30-526`](decisions/roster-an-derive-amo30-526.md).

## `src/audit_gouvernement_dataset.py`

2 décision(s) le gouvernent ; le module en cite 0.

| Décision | Nomme |
| --- | --- |
| [Épic #316 — tableaux croisés des plages temporelles (#317/#318/#320/#321) : bilan et décisions transverses (2026-08-15)](decisions/audit-plages-temporelles.md) | `compute_plage_dates_gouvernements` |
| [Un test d'acceptation adossé au corpus vivant rougit quand la donnée s'améliore (#457) (2026-08-20)](decisions/test-adosse-au-corpus-vivant.md) | `compute_taux_portefeuille_renseigne` |

Le mentionnent sans le gouverner : [`audit-pipeline-gouvernement`](decisions/audit-pipeline-gouvernement.md), [`couverture-dossiers-hors-couverture-vs-zero`](decisions/couverture-dossiers-hors-couverture-vs-zero.md).

## `src/audit_groupe_dataset.py`

3 décision(s) le gouvernent ; le module en cite 1.

| Décision | Nomme |
| --- | --- |
| [Épic #316 — tableaux croisés des plages temporelles (#317/#318/#320/#321) : bilan et décisions transverses (2026-08-15)](decisions/audit-plages-temporelles.md) | `compute_plage_dates_groupes` |
| [Tous les comptes d'une fiche de groupe se rapportent à une date, et elle est publiée (#653) (2026-08-31)](decisions/date-de-reference-des-comptes-de-groupe-653.md) | `CHAMPS_EFFECTIF` |
| [Tableau croisé des plages temporelles par groupe (#318, sous-issue 2/6 de #316) (2026-08-15)](decisions/plage-dates-groupes.md) | `compute_plage_dates_groupes`, `compute_tableau_croise_groupes` |

Le mentionnent sans le gouverner : [`audit-pipeline-gouvernement`](decisions/audit-pipeline-gouvernement.md), [`consommateurs-chambres-migres`](decisions/consommateurs-chambres-migres.md), [`merge-and-pivot-budget-permissions-413`](decisions/merge-and-pivot-budget-permissions-413.md), [`quality-gate-gouvernements`](decisions/quality-gate-gouvernements.md), [`senat-periode-debut`](decisions/senat-periode-debut.md), [`seuil-couverture-groupe`](decisions/seuil-couverture-groupe.md).

## `src/audit_integrite_referentielle.py`

Le mentionnent sans le gouverner : [`collecte-non-publiee`](decisions/collecte-non-publiee.md), [`collecte-vs-publie-545`](decisions/collecte-vs-publie-545.md), [`dossier-des-amendements-639`](decisions/dossier-des-amendements-639.md), [`perimetre-controle-perte`](decisions/perimetre-controle-perte.md), [`qualification-perdue-a-la-fusion-639`](decisions/qualification-perdue-a-la-fusion-639.md), [`qualification-scrutins-et-cle-dossier-639`](decisions/qualification-scrutins-et-cle-dossier-639.md), [`retrait-senat-528`](decisions/retrait-senat-528.md).

## `src/audit_legislature_votes.py`

Le mentionnent sans le gouverner : [`partition-profils-legislature-580`](decisions/partition-profils-legislature-580.md), [`point-de-sauvegarde-dans-les-profils-518`](decisions/point-de-sauvegarde-dans-les-profils-518.md), [`resolution-legislature-deux-mecanismes-432`](decisions/resolution-legislature-deux-mecanismes-432.md).

## `src/audit_pipeline.py`

2 décision(s) le gouvernent ; le module en cite 0.

| Décision | Nomme |
| --- | --- |
| [`audit_pipeline.py` : intégration du rapport gouvernement (#321, sous-issue 5/6 de #316) (2026-08-15)](decisions/audit-pipeline-gouvernement.md) | `compute_vue_ensemble` |
| [Épic #316 — tableaux croisés des plages temporelles (#317/#318/#320/#321) : bilan et décisions transverses (2026-08-15)](decisions/audit-plages-temporelles.md) | `compute_vue_ensemble` |

Le mentionnent sans le gouverner : [`lectures-pipeline-par-projection-635`](decisions/lectures-pipeline-par-projection-635.md).

## `src/audit_pivot_dataset.py`

11 décision(s) le gouvernent ; le module en cite 4.

| Décision | Nomme |
| --- | --- |
| [Épic #316 — tableaux croisés des plages temporelles (#317/#318/#320/#321) : bilan et décisions transverses (2026-08-15)](decisions/audit-plages-temporelles.md) | `_plage_dates_champ_simple`, `compute_plage_dates_candidats`, `compute_tableau_croise_candidats` |
| [Rapport d'audit pivot : détail réservé aux candidats déclarés, indicateurs de distribution retirés (2026-08-18)](decisions/audit-rapport-perimetre-candidats.md) | `_est_candidat`, `_stats_volumes` |
| [La chambre est un fait du mandat, pas du profil : `mandats[].chambre` estampillée à la collecte (#492) (2026-08-20)](decisions/chambre-par-mandat-electif.md) | `compute_agregation_warnings` |
| [`chambres` au niveau profil : une liste dérivée, et `chambre` qui n'en est plus que le premier élément (#493) (2026-08-20)](decisions/chambres-profil-derivees.md) | `MAPPING_CHAMBRE_SOURCES`, `compute_agregation_warnings`, `compute_coherence_chambre_sources` |
| [Les consommateurs de `chambre` migrés vers `chambres`, et le garde-fou qui datera son retrait (#494) (2026-08-20)](decisions/consommateurs-chambres-migres.md) | `MAPPING_CHAMBRE_SOURCES`, `compute_coherence_chambre_sources`, `compute_plage_dates_candidats`, `compute_repartition_chambre`, `compute_tableau_croise_candidats` |
| [La corroboration porte sur les chambres publiées, pas sur la complétude des mandats — et la condition de retrait de `chambre` devient atteignable (#486) (2026-08-30)](decisions/corroboration-chambres-publiees-486.md) | `MAPPING_CHAMBRE_SOURCES` |
| [Un paramètre commandait ce qu'il ne nommait pas (#578) (2026-08-29)](decisions/deux-axes-formulaire-578.md) | `compute_profils_perimes` |
| [Le passé sénatorial est un fait de carrière, pas une donnée d'activité : bicaméral pour les candidats seulement (#488) (2026-08-20)](decisions/deux-chambres-interrogees.md) | `compute_agregation_warnings` |
| [Trois lectures du corpus passent à la projection, et chacune a son plafond dans un test (#635, 2026-08-30)](decisions/lectures-pipeline-par-projection-635.md) | `BLOCS_LUS_AUDIT`, `ListeReduite`, `_cle_groupe`, `_plage_dates_champ_simple`, `_plage_dates_textes_portes`, `compute_plage_dates_candidats`, `compute_taux_remplissage`, `load_pivot_directory`, `reduire_liste` |
| [`--limit` + `--skip-existing` sur `extract-roster-groupes` : sélection progressive + rafraîchissement (2026-08-12)](decisions/limit-skip-existing-roster-groupes.md) | `compute_profils_perimes` |
| [NosDéputés sort du pipeline (#529, lot 5 de l'épic « une seule source AN ») (2026-08-27)](decisions/retrait-nosdeputes-529.md) | `MAPPING_CHAMBRE_SOURCES`, `compute_agregation_warnings` |

Le mentionnent sans le gouverner : [`audit-599-projection-blocs-lus-628`](decisions/audit-599-projection-blocs-lus-628.md), [`audit-pipeline-gouvernement`](decisions/audit-pipeline-gouvernement.md), [`destinataire-avertissements-642`](decisions/destinataire-avertissements-642.md), [`plage-dates-groupes`](decisions/plage-dates-groupes.md), [`populations-profils-portees-par-les-outils-630`](decisions/populations-profils-portees-par-les-outils-630.md), [`quality-gate-gouvernements`](decisions/quality-gate-gouvernements.md), [`retrait-senat-528`](decisions/retrait-senat-528.md).

## `src/audit_volumetrie_profils.py`

2 décision(s) le gouvernent ; le module en cite 2.

| Décision | Nomme |
| --- | --- |
| [La coupure d'historique a tourné pour la première fois — et `--preparer` n'avait jamais imprimé sa procédure (#567) (2026-08-28)](decisions/bornage-execute-567.md) | `MOTIF_COMMIT_DONNEES` |
| [La fenêtre de 30 ne pose pas le plateau qu'on croit, et la table mesurée ne le dit pas (#551) (2026-08-28)](decisions/fenetre-recalibrage-551.md) | `FENETRE_COMMITS_DONNEES`, `MOTIF_COMMIT_DONNEES` |

Le mentionnent sans le gouverner : [`fenetre-historique-donnees`](decisions/fenetre-historique-donnees.md), [`partition-profils-legislature-580`](decisions/partition-profils-legislature-580.md), [`perimetre-coupure-575`](decisions/perimetre-coupure-575.md), [`point-de-sauvegarde-dans-les-profils-518`](decisions/point-de-sauvegarde-dans-les-profils-518.md), [`populations-profils-portees-par-les-outils-630`](decisions/populations-profils-portees-par-les-outils-630.md), [`profils-json-compact`](decisions/profils-json-compact.md), [`volumetrie-arbre-de-travail-nest-pas-depot`](decisions/volumetrie-arbre-de-travail-nest-pas-depot.md).

## `src/avertissements.py`

1 décision(s) le gouvernent ; le module en cite 0.

| Décision | Nomme |
| --- | --- |
| [`meta.warnings[]` déclare son destinataire, dans un jumeau typé et aligné (#642) (2026-08-31)](decisions/destinataire-avertissements-642.md) | `AVERTISSEMENTS_HERITES`, `Avertissement`, `DESTINATAIRES_AVERTISSEMENT`, `PREFIXES_HERITES`, `avertissement`, `deriver_avertissements` |

Le mentionnent sans le gouverner : [`amendements-zero-pas-de-hard-fail`](decisions/amendements-zero-pas-de-hard-fail.md), [`bloc-sans-fond-484`](decisions/bloc-sans-fond-484.md), [`couverture-dossiers-hors-couverture-vs-zero`](decisions/couverture-dossiers-hors-couverture-vs-zero.md), [`profil-de-groupe-lecture-329`](decisions/profil-de-groupe-lecture-329.md), [`retrait-senat-528`](decisions/retrait-senat-528.md), [`union-warnings-extinction-600`](decisions/union-warnings-extinction-600.md), [`verification-bout-en-bout-legislatures-figees`](decisions/verification-bout-en-bout-legislatures-figees.md).

## `src/budget_collecte.py`

3 décision(s) le gouvernent ; le module en cite 0.

| Décision | Nomme |
| --- | --- |
| [Une source injoignable ne consomme plus le timeout d'un job, et son silence cesse de se lire comme un constat (#514) (2026-08-21)](decisions/budget-collecte-source-injoignable-514.md) | `BudgetCollecte` |
| [`extract-senat` ne collecte plus d'interventions : la collecte n'en retenait aucune, par construction (#501) (2026-08-20)](decisions/interventions-senat-501.md) | `BudgetCollecte` |
| [Un seul roster par run, une reprise sur ce qui est retentable, et des échecs qu'on peut lire (#518) (2026-08-24)](decisions/roster-unique-par-run-518.md) | `annoncer_troncature` |

Le mentionnent sans le gouverner : [`budget-collecte-interventions`](decisions/budget-collecte-interventions.md).

## `src/build_amendements_index.py`

1 décision(s) le gouvernent ; le module en cite 0.

| Décision | Nomme |
| --- | --- |
| [Job CI dédié `extract-amendements-an` : construction inconditionnelle des 3 index de législature (#251) (2026-08-13)](decisions/amendements-index-job-dedie-ci.md) | `build_all_amendements_index` |

Le mentionnent sans le gouverner : [`amendements-index-cache-only-consumers`](decisions/amendements-index-cache-only-consumers.md), [`cache-amendements-existence-nest-pas-conformite`](decisions/cache-amendements-existence-nest-pas-conformite.md), [`index-amendements-sharde-par-acteur`](decisions/index-amendements-sharde-par-acteur.md), [`oom-lecture-amendements-par-candidat`](decisions/oom-lecture-amendements-par-candidat.md), [`oom-reconstruction-amendements-figees`](decisions/oom-reconstruction-amendements-figees.md), [`pythonunbuffered-generate-data`](decisions/pythonunbuffered-generate-data.md).

## `src/build_amendements_index_figees.py`

Le mentionnent sans le gouverner : [`amendements-cle-uid`](decisions/amendements-cle-uid.md), [`amendements-legislatures-figees`](decisions/amendements-legislatures-figees.md), [`defaut-collecte-vs-panne-562`](decisions/defaut-collecte-vs-panne-562.md), [`telechargement-an-prefixe-valide-443`](decisions/telechargement-an-prefixe-valide-443.md).

## `src/build_amendements_index_pivot.py`

Le mentionnent sans le gouverner : [`dossier-des-amendements-639`](decisions/dossier-des-amendements-639.md), [`fenetre-historique-donnees`](decisions/fenetre-historique-donnees.md), [`integrite-referentielle-pivot`](decisions/integrite-referentielle-pivot.md), [`report-texte-vise-source-696`](decisions/report-texte-vise-source-696.md).

## `src/build_correspondance_acteurs_an.py`

Le mentionnent sans le gouverner : [`bascule-roster-an-amo30-527`](decisions/bascule-roster-an-amo30-527.md), [`correspondance-acteurs-an-525`](decisions/correspondance-acteurs-an-525.md).

## `src/build_scrutins_index.py`

Le mentionnent sans le gouverner : [`fenetre-historique-donnees`](decisions/fenetre-historique-donnees.md), [`integrite-referentielle-pivot`](decisions/integrite-referentielle-pivot.md), [`qualification-perdue-a-la-fusion-639`](decisions/qualification-perdue-a-la-fusion-639.md), [`rattachement-au-dossier-interventions-et-scrutins-639`](decisions/rattachement-au-dossier-interventions-et-scrutins-639.md).

## `src/build_scrutins_index_figes.py`

Le mentionnent sans le gouverner : [`qualification-scrutins-et-cle-dossier-639`](decisions/qualification-scrutins-et-cle-dossier-639.md), [`votes-multi-legislature`](decisions/votes-multi-legislature.md).

## `src/cache_an_empreinte.py`

Le mentionnent sans le gouverner : [`cache-completude-interventions-550`](decisions/cache-completude-interventions-550.md).

## `src/cache_an_fraicheur.py`

Le mentionnent sans le gouverner : [`cache-fraicheur-interventions-555`](decisions/cache-fraicheur-interventions-555.md).

## `src/candidate_profile.py`

73 décision(s) le gouvernent ; le module en cite 12.

| Décision | Nomme |
| --- | --- |
| [Trois absences publiées comme des faits (#556, #558, #560) (2026-08-29)](decisions/absences-publiees-comme-faits-556-558-560.md) | `AN_SCRUTINS_LEGISLATURES`, `NOM_INDEX_IDENTITE`, `NOM_INDEX_ORGANES`, `WARNING_PREFIX_INTERVENTIONS_SYCERON_AUCUNE`, `WARNING_PREFIX_INTERVENTIONS_SYCERON_INDISPONIBLES`, `WARNING_PREFIX_VOTES_INTROUVABLES`, `_TYPE_ORGANE_NON_MAPPES`, `_champ_identite_an`, `_format_lieu_naissance`, `_format_nom_complet`, `_texte_an` |
| [Amendements : la clé du store est l'`uid`, jamais le `numero` (préalable à #431) (2026-08-18)](decisions/amendements-cle-uid.md) | `_aggregate_amendements_index`, `_load_frozen_amendement_index`, `_read_cached_amendements_acteur` |
| [Un amendement cosigné n'est pas N amendements : deux grandeurs, deux noms (#643) (2026-08-31)](decisions/amendements-distincts-et-signatures-643.md) | `_periodes_mandats_assemblee` |
| [Marqueur disque inter-jobs pour le cache d'échec amendements par législature (#246) (2026-08-13)](decisions/amendements-failed-legislature-marker-inter-jobs.md) | `AMENDEMENTS_DOWNLOAD_MAX_ATTEMPTS`, `AMENDEMENTS_DOWNLOAD_READ_TIMEOUT_SECONDS`, `_amendements_failed_legislatures` |
| [Spike : budget CI pour un job dédié `extract-amendements-an` et granularité de cache (#249) (2026-08-13)](decisions/amendements-index-budget-ci-cache-granularite.md) | `AMENDEMENTS_DOWNLOAD_BACKOFF_SECONDS`, `AMENDEMENTS_DOWNLOAD_CHUNK_BYTES`, `AMENDEMENTS_DOWNLOAD_MAX_ATTEMPTS`, `AMENDEMENTS_DOWNLOAD_READ_TIMEOUT_SECONDS`, `_download_amendements_zip` |
| [Bascule d'`extract-an`/`extract-roster-groupes` vers la lecture cache-only des amendements (#252) (2026-08-13)](decisions/amendements-index-cache-only-consumers.md) | `AN_AMENDEMENTS_PATH`, `AmendementsIndexError`, `WARNING_PREFIX_AMENDEMENTS_INDISPONIBLES`, `_download_and_build_amendement_index`, `fetch_amendements_officiels` |
| [Séparer téléchargement/construction et lecture cache-only dans `_build_acteur_amendement_index` (#250) (2026-08-13)](decisions/amendements-index-cache-only-split.md) | `_download_and_build_amendement_index`, `_get_amendements_lock`, `fetch_amendements_officiels` |
| [Job CI dédié `extract-amendements-an` : construction inconditionnelle des 3 index de législature (#251) (2026-08-13)](decisions/amendements-index-job-dedie-ci.md) | `AN_AMENDEMENTS_PATH`, `_download_and_build_amendement_index`, `fetch_amendements_officiels` |
| [Non-régression sur échec de reconstruction d'un index amendements + indicateur de fraîcheur (#253) (2026-08-13)](decisions/amendements-index-non-regression-fraicheur.md) | `AmendementsIndexError`, `_amendements_legislature_failed_this_run`, `_download_and_build_amendement_index`, `_write_amendements_fraicheur` |
| [Quality gate : distinguer un index amendements jamais construit d'un index périmé (#254) (2026-08-13)](decisions/amendements-index-quality-gate-fraicheur.md) | `AN_AMENDEMENTS_PATH` |
| [Index amendements des législatures 15/16 : construction manuelle hors CI, committée (2026-08-13)](decisions/amendements-legislatures-figees.md) | `AMENDEMENTS_DOWNLOAD_CHUNK_BYTES`, `AMENDEMENTS_DOWNLOAD_MAX_ATTEMPTS`, `AMENDEMENTS_FIGEES_AMENDEMENTS_FILENAME`, `AMENDEMENTS_FIGEES_INDEX_PAR_ACTEUR_FILENAME`, `AN_AMENDEMENTS_LEGISLATURES_FIGEES`, `AN_AMENDEMENTS_PATH`, `_AMENDEMENT_SORT_MAP`, `_AMENDEMENT_TYPE_AUTEUR_MAP`, `_LEGACY_AMENDEMENT_SORT_EN_SEANCE_MAP`, `_aggregate_amendements_index`, `_derive_amendement_sort`, `_derive_amendement_sort_legacy`, `_download_amendements_zip`, `_download_and_build_amendement_index`, `_expand_aggregated_amendements_index`, `_extract_cosignataire_refs`, `_load_frozen_amendement_index`, `_parse_amendement_entry`, `_parse_amendement_entry_legacy`, `_parse_amendements_zip`, `_probe_amendements_total_size`, `fetch_amendements_officiels` |
| [Téléchargement par plages (Range) + isolation par législature pour les amendements officiels (#241) (2026-08-13)](decisions/amendements-range-download-legislature-isolation.md) | `AMENDEMENTS_DOWNLOAD_CHUNK_BYTES`, `AMENDEMENTS_DOWNLOAD_MAX_ATTEMPTS`, `AN_AMENDEMENTS_PATH`, `WARNING_PREFIX_AMENDEMENTS_INDISPONIBLES`, `_amendements_failed_legislatures`, `_download_amendements_zip`, `build_profile`, `fetch_amendements_officiels` |
| [Le retry avec backoff des amendements (#225) transforme un échec instantané en blocage de plusieurs minutes par candidat (#239) (2026-08-13)](decisions/amendements-retry-blocage-legislature.md) | `AMENDEMENTS_DOWNLOAD_MAX_ATTEMPTS`, `AMENDEMENTS_DOWNLOAD_READ_TIMEOUT_SECONDS`, `AN_AMENDEMENTS_PATH`, `AmendementsIndexError`, `_amendements_failed_legislatures`, `fetch_amendements_officiels` |
| [Zéro amendement silencieux quand l'acteurRef est introuvable (#265, fix 5) (2026-08-17)](decisions/amendements-zero-silencieux-acteur-ref.md) | `WARNING_PREFIX_AMENDEMENTS_INDISPONIBLES`, `build_profile`, `fetch_amendements_officiels` |
| [`fetch_identity` : identité (bio) des députés basculée sur l'AN comme source primaire, mandats/groupe restent sur NosDéputés (#355) (2026-08-16)](decisions/bascule-identite-an-primaire.md) | `_acteur_ref_to_pseudo_url`, `_build_acteur_nom_index`, `_build_organe_index`, `build_profile`, `fetch_identite_officielle`, `fetch_identite_officielle_par_slug` |
| [La bascule : le roster des groupes AN vient d'AMO30 (#527, lot 1b de l'épic « une seule source AN ») (2026-08-26)](decisions/bascule-roster-an-amo30-527.md) | `_ensure_acteurs_historique_zip_downloaded` |
| [Un bloc structuré sans fond n'écrase plus un bloc collecté (#484) (2026-08-30)](decisions/bloc-sans-fond-484.md) | `WARNING_AUCUN_MANDAT_FR` |
| [Une source injoignable ne consomme plus le timeout d'un job, et son silence cesse de se lire comme un constat (#514) (2026-08-21)](decisions/budget-collecte-source-injoignable-514.md) | `_mark_amendements_legislature_failed` |
| [Budget d'exécution à pleine échelle : 630 min annoncées, 55 mesurées (#467) (2026-08-20)](decisions/budget-execution-pleine-echelle-467.md) | `ACTEURS_HISTORIQUE_CACHE_DIR`, `_extract_mandats_officiels`, `_get_amendements_lock`, `fetch_amendements_officiels`, `fetch_organe` |
| [Budget CI de `extract-roster-groupes` : mesure réelle (#376) (2026-08-17)](decisions/budget-roster-mesure.md) | `fetch_amendements_officiels` |
| [L'existence d'un cache n'est pas la preuve de son contenu — et #447 n'avait pas de seconde cause (2026-08-19)](decisions/cache-amendements-existence-nest-pas-conformite.md) | `_cache_amendements_au_format_uid`, `_download_and_build_amendement_index`, `_read_cached_amendements_acteur`, `_scrutins_shard_path_acteur`, `_write_cached_amendements_agreges`, `_write_cached_scrutins`, `amendements_index_deja_figee`, `fetch_amendements_officiels` |
| [Cache amendements stocké et lu sous forme dédupliquée (#377) (2026-08-17)](decisions/cache-amendements-forme-dedupliquee.md) | `AMENDEMENTS_CACHE_DIR`, `_aggregate_amendements_index`, `_download_and_build_amendement_index`, `_expand_aggregated_amendements_index`, `_load_frozen_amendement_index`, `_parse_amendements_zip`, `_read_cached_amendements_acteur`, `_write_cached_amendements_agreges`, `amendements_index_deja_figee`, `fetch_amendements_officiels` |
| [La clé de cache AN porte la COMPLÉTUDE, et la sauvegarde devient explicite (#550) (2026-08-28)](decisions/cache-completude-interventions-550.md) | `AMENDEMENTS_FRAICHEUR_FILENAME`, `AN_QUESTIONS_PATH`, `AN_SCRUTINS_LEGISLATURES_FIGEES`, `_build_acteur_questions_index`, `_read_cached_interventions_syceron_acteur` |
| [Les `restore-keys` du cache AN traversaient les semaines : la fraîcheur ne se met pas dans la clé, elle se lit dans celle qu'on a restaurée (#555) (2026-08-28)](decisions/cache-fraicheur-interventions-555.md) | `AMENDEMENTS_FRAICHEUR_FILENAME`, `AN_AMENDEMENTS_LEGISLATURES_FIGEES`, `AN_SCRUTINS_LEGISLATURES_FIGEES`, `_build_acteur_questions_index`, `_ensure_acteurs_historique_zip_downloaded`, `_read_cached_interventions_syceron_acteur` |
| [La clé de cache AN porte le MODE, et le job roster ne l'écrit plus (#505) (2026-08-20)](decisions/cache-mode-interventions-505.md) | `_build_acteur_interventions_syceron_index`, `_build_acteur_questions_index`, `_parse_syceron_intervention_entry`, `fetch_questions_officielles` |
| [La chambre est un fait du mandat, pas du profil : `mandats[].chambre` estampillée à la collecte (#492) (2026-08-20)](decisions/chambre-par-mandat-electif.md) | `build_profile` |
| [La civilité et la nomenclature PCS de l'INSEE traversaient le pipeline sans y laisser de trace (#659) (2026-08-31)](decisions/civilite-et-pcs-insee-659.md) | `NOM_INDEX_IDENTITE`, `_build_acteur_identite_index`, `_champ_identite_an`, `_profession_an`, `_socproc_insee_an` |
| [La correspondance slug ↔ acteur AN devient un artefact committé (#525, lot 2 de l'épic « une seule source AN ») (2026-08-26)](decisions/correspondance-acteurs-an-525.md) | `_resolve_acteur_ref_par_slug` |
| [Ce qu'une liste vide veut dire : les quatre états de couverture (#539) (2026-08-28)](decisions/couverture-listes-539.md) | `AN_AMENDEMENTS_PATH`, `AN_SCRUTINS_LEGISLATURES`, `WARNING_PREFIX_VOTES_INTROUVABLES`, `_resolve_acteur_ref_par_slug` |
| [`debut_dans_groupe` se lit sur le mandat de groupe, plus sur le premier mandat électif (#653) (2026-08-31)](decisions/dates-appartenance-groupe-653.md) | `fetch_positions_hemicycle_officielles` |
| [`membres[]` publiait deux fois le même fait : dédupliquer sans effacer les changements de portefeuille (#480) (2026-08-20)](decisions/deduplication-entrees-membres.md) | `_build_acteur_positions_hemicycle_index` |
| [Une exception n'est pas une preuve, et un défaut de notre code n'est pas une panne de l'Assemblée nationale (#562) (2026-08-28)](decisions/defaut-collecte-vs-panne-562.md) | `AmendementsIndexError`, `ERREURS_SOURCE`, `WARNING_PREFIX_DEFAUT_COLLECTE`, `WARNING_PREFIX_VOTES_INTROUVABLES`, `_parse_amendement_entry`, `_texte_an`, `_tracer_echec_collecte`, `build_profile`, `fetch_amendements_officiels` |
| [`meta.warnings[]` déclare son destinataire, dans un jumeau typé et aligné (#642) (2026-08-31)](decisions/destinataire-avertissements-642.md) | `WARNING_PREFIX_INTERVENTIONS_SYCERON_INDISPONIBLES`, `WARNING_PREFIX_VOTES_INTROUVABLES` |
| [Un amendement retrouve son dossier, et la clé qu'on lui avait retirée (#639, rang 3)](decisions/dossier-des-amendements-639.md) | `fetch_amendements_officiels` |
| [Un filtre de publication posé avant la fusion ne filtre rien (#641, réouverture) (2026-08-31)](decisions/filtre-publication-apres-fusion-641.md) | `_profession_an` |
| [`gouvernement_profile` : `premier_ministre` et `portefeuille` câblés depuis les mandats `MINISTERE` (#398) (2026-08-18)](decisions/gouvernement-premier-ministre-portefeuille.md) | `AN_ACTEURS_HISTORIQUE_ZIP_URL`, `_extract_mandats_officiels` |
| [`gouvernement_textes.py` : filtre de statut par décision de séance, pas par `codeActe`/`fam_code` seul (#210) (2026-08-14)](decisions/gouvernement-textes-statut.md) | `_build_acteur_textes_portes_index` |
| [`gouvernement_textes.py` : filtre de statut par décision de séance, pas par `codeActe`/`fam_code` seul (#210) (2026-08-14)](decisions/gouvernement-textes-statut-210-version-initiale.md) | `_build_acteur_textes_portes_index` |
| [`_build_acteur_identite_index` : couvrir les élu⋅e⋅s dont le mandat est terminé via `AMO30`, pas en combinant `AMO20` par législature (#354) (2026-08-16)](decisions/identite-acteurs-amo30.md) | `AN_ACTEURS_HISTORIQUE_ZIP_URL`, `_build_acteur_identite_index`, `_build_acteur_positions_hemicycle_index`, `_build_organe_index`, `_ensure_acteurs_historique_zip_downloaded`, `_select_mandat_assemblee_courant`, `build_profile` |
| [Index amendements shardé par acteur (#392) (2026-08-17)](decisions/index-amendements-sharde-par-acteur.md) | `_download_and_build_amendement_index`, `_expand_aggregated_amendements_index`, `fetch_amendements_officiels` |
| [`extract-senat` ne collecte plus d'interventions : la collecte n'en retenait aucune, par construction (#501) (2026-08-20)](decisions/interventions-senat-501.md) | `build_profile`, `fetch_questions_officielles` |
| [Le libellé d'organe du chef du gouvernement s'accorde en genre, la qualité jamais (#658) (2026-08-31)](decisions/libelle-chef-du-gouvernement-au-feminin-658.md) | `_build_acteur_mandats_index` |
| [Un profil publie tous ses mandats de député, et le compteur devient un témoin de couverture (#640) (2026-08-31)](decisions/mandats-electifs-liste-complete-640.md) | `_select_mandat_assemblee_courant`, `_select_mandat_par_type_courant` |
| [Mandats commission/groupe_amitie/extra_parlementaire sourcés depuis l'AN, fetch_identity NosDéputés rendu conditionnel (#369, complet), watchdog générique sur tous les téléchargements zip (#370, complet) (2026-08-17)](decisions/mandats-officiels-an-369.md) | `_TYPE_ORGANE_TO_CATEGORIE`, `_build_acteur_identite_index`, `_build_acteur_mandats_index`, `_build_organe_index`, `_ensure_acteurs_historique_zip_downloaded`, `_extract_mandats_officiels`, `build_profile`, `fetch_identite_officielle_par_slug`, `fetch_organe`, `fetch_votes_officiels` |
| [Mode d'extraction léger pour `extract-roster-groupes` (#357, sous-issue 6/6 de #351) (2026-08-16)](decisions/mode-extraction-leger-roster.md) | `build_profile`, `fetch_textes_portes_officiels` |
| [Suppression de l'archive brute `amendements.zip` après construction de l'index (#264) (2026-08-17)](decisions/nettoyage-archive-brute-amendements.md) | `_download_amendements_zip`, `_download_and_build_amendement_index`, `_read_cached_amendements_acteur` |
| [Normaliser les amendements : le coût n'est pas l'amendement, c'est sa liste de cosignataires (#431) (2026-08-19)](decisions/normalisation-amendements.md) | `_expand_aggregated_amendements_index`, `_load_frozen_amendement_index`, `_parse_amendement_entry` |
| [Normalisation de `par_fonction` dans `mandats_agreges`, et requalification du défaut « catégorie commission » (#379) (2026-08-17)](decisions/normalisation-fonction-mandats-agreges.md) | `_TYPE_ORGANE_TO_CATEGORIE` |
| [OOM persistant : lecture per-candidat de l'index amendements, tentative de mémoïsation revertée (2026-08-17)](decisions/oom-lecture-amendements-par-candidat.md) | `AN_AMENDEMENTS_PATH`, `fetch_amendements_officiels` |
| [OOM lors de la relecture d'un index amendements figé déjà en cache (exécution locale) (2026-08-17)](decisions/oom-reconstruction-amendements-figees.md) | `AN_AMENDEMENTS_LEGISLATURES_FIGEES`, `AN_AMENDEMENTS_PATH`, `_download_and_build_amendement_index`, `amendements_index_deja_figee` |
| [`_build_organe_index` : résoudre `organeRef` via `AMO30` (historique) sans filtrage par `codeType` (#353) (2026-08-16)](decisions/organe-index-organeref.md) | `AN_ACTEURS_HISTORIQUE_ZIP_URL`, `_ACTEURS_HISTORIQUE_ZIP_LOCK`, `_build_acteur_positions_hemicycle_index`, `_build_organe_index`, `_build_organe_positions_index`, `_ensure_acteurs_historique_zip_downloaded`, `fetch_positions_hemicycle_officielles` |
| [Parallèle RAM entre l'exécution locale et les runners GitHub Actions hébergés, diagnostic ajouté (2026-08-17)](decisions/parallele-oom-local-runner-ci.md) | `build_profile`, `fetch_amendements_officiels` |
| [Un code de nomenclature n'est pas une profession, et « sans activité professionnelle » n'en est pas une (#641) (2026-08-31)](decisions/profession-code-nomenclature-641.md) | `_profession_an` |
| [La qualification d'un scrutin et la clé de son dossier étaient lues puis jetées (#639, rangs 1 et 2)](decisions/qualification-scrutins-et-cle-dossier-639.md) | `_load_frozen_scrutins_index`, `_parse_scrutins_zip`, `_scrutins_store_qualifie` |
| [Un projet de loi porté au nom du Gouvernement n'est pas une production personnelle (#689) (2026-09-01)](decisions/qualification-textes-portes-689.md) | `_build_acteur_textes_portes_index` |
| [Rattacher une intervention ou un scrutin à son dossier : les deux volets restants sont écartés, mesure à l'appui (#639) (2026-09-01)](decisions/rattachement-au-dossier-interventions-et-scrutins-639.md) | `_parse_scrutins_zip`, `_reduire_au_theme` |
| [Le `texte_vise` fautif se reprend depuis l'archive figée, pas par une fusion plus permissive (#696, 01/09/2026)](decisions/report-texte-vise-source-696.md) | `fetch_amendements_officiels` |
| [Résilience de `generate-data.yml` face aux `shutdown signal` runner : continue-on-error généralisé, watchdog réseau, retry générique sur `_get_payload`, retry `retry-generate-data.yml` non-régressif, et appels NosDéputés morts pour les députés (dossiers, votes) (2026-08-16)](decisions/resilience-generate-data-shutdown-signal.md) | `WARNING_PREFIX_VOTES_INTROUVABLES`, `build_profile`, `fetch_textes_portes_officiels`, `fetch_votes_officiels` |
| [Bug de résolution AN pour les prénoms composés, et gel runner déplacé sur l'étape 0 (run #47) (2026-08-17)](decisions/resolution-an-prenom-compose-et-gel-runner-etape0.md) | `_build_acteur_nom_index`, `_ensure_acteurs_historique_zip_downloaded`, `_normalize_search_query`, `fetch_identite_officielle_par_slug` |
| [Retrait de `fetch_activity_synthesis` (#356) (2026-08-16)](decisions/retrait-fetch-activity-synthesis.md) | `build_profile` |
| [NosDéputés sort du pipeline (#529, lot 5 de l'épic « une seule source AN ») (2026-08-27)](decisions/retrait-nosdeputes-529.md) | `CHAMBRES_COLLECTEES`, `WARNING_PREFIX_INTERVENTIONS_SYCERON_INDISPONIBLES`, `_build_acteur_nom_index`, `_ensure_acteurs_historique_zip_downloaded`, `_normalize_search_query`, `_resolve_acteur_ref_par_slug`, `build_profile`, `fetch_textes_portes_officiels` |
| [Le Sénat sort du périmètre, et le job qui concluait vert sans rien produire est retiré (#528, lot 3 de l'épic « une seule source AN ») (2026-08-26)](decisions/retrait-senat-528.md) | `build_profile` |
| [Le roster des groupes AN est dérivé d'AMO30, derrière un drapeau baissé (#526, lot 1 de l'épic « une seule source AN ») (2026-08-26)](decisions/roster-an-derive-amo30-526.md) | `_ensure_acteurs_historique_zip_downloaded` |
| [Scission du cache CI `.cache` par sous-répertoire : écartée (#374, fermée non planifiée) (2026-08-17)](decisions/scission-cache-ci-ecartee.md) | `build_profile`, `fetch_amendements_officiels` |
| [Syceron : remplacement du scraping NosDéputés pour les débats en séance (2026-08-07)](decisions/syceron.md) | `_build_acteur_interventions_syceron_index`, `fetch_interventions_syceron` |
| [Syceron publie l'identifiant d'orateur NU, et n'a donc jamais rien indexé (#510) (2026-08-20)](decisions/syceron-acteur-ref-nu-510.md) | `_build_acteur_interventions_syceron_index`, `_normaliser_orateur_id_syceron`, `_parse_syceron_intervention_entry`, `_shard_path_acteur` |
| [Syceron activé, repli NosDéputés retiré, index tranché par acteur (#510) (2026-08-27)](decisions/syceron-actif-510.md) | `RefusDrapeauInterventionsSyceron`, `_normaliser_orateur_id_syceron`, `_parse_syceron_intervention_entry`, `_read_cached_interventions_syceron_acteur` |
| [Suite du 26/08/2026 : les trois archives vérifiées, les deux défauts de parseur corrigés](decisions/syceron-archives-verifiees-parseur-510.md) | `_scrutins_shard_path_acteur` |
| [`synchro_sources` publie la dernière récupération réussie, et pas son origine (#600) (2026-08-30)](decisions/synchro-sources-derniere-recuperation-600.md) | `_telecharger_flux`, `fetch_interventions_syceron`, `fetch_questions_officielles` |
| [Taxonomie des mandats : exploitation des `typeOrgane` AN non mappés (#382, option « mixte ») (2026-08-17)](decisions/taxonomie-mandats-typeorgane-an.md) | `_TYPE_ORGANE_NON_MAPPES`, `fetch_positions_hemicycle_officielles` |
| [Téléchargement AN : trois modes de défaillance, un seul principe — ne jamais jeter un préfixe valide (#443) (2026-08-19)](decisions/telechargement-an-prefixe-valide-443.md) | `AMENDEMENTS_DOWNLOAD_CHUNK_BYTES`, `AMENDEMENTS_SOURCE_STALL_MAX_CYCLES`, `AMENDEMENTS_SOURCE_STALL_WAIT_SECONDS`, `SourceAmendementsIndisponibleError`, `_download_amendements_zip`, `_est_erreur_http_definitive`, `_telecharger_flux`, `_tenter_get_sequentiel` |
| [L'union des avertissements peut ressusciter un démenti, et deux familles Syceron s'éteignent (#600) (2026-08-30)](decisions/union-warnings-extinction-600.md) | `WARNING_PREFIX_QUESTIONS_INDISPONIBLES` |
| [Votes : agrégation des législatures 14 à 17, index dédupliqué, 14/15/16 figées (#403) (2026-08-18)](decisions/votes-multi-legislature.md) | `AN_SCRUTINS_LEGISLATURES`, `AN_SCRUTINS_LEGISLATURES_FIGEES`, `AN_SCRUTIN_UID_PREFIXE`, `fetch_votes_officiels` |

Le mentionnent sans le gouverner : [`consommateurs-chambres-migres`](decisions/consommateurs-chambres-migres.md), [`dossiers-multi-archives-origine-document`](decisions/dossiers-multi-archives-origine-document.md), [`gouvernement-roster-desambiguisation`](decisions/gouvernement-roster-desambiguisation.md), [`licences`](decisions/licences.md), [`mandats-agreges-famille-1`](decisions/mandats-agreges-famille-1.md), [`parlementaire-en-mission-nest-pas-ministre`](decisions/parlementaire-en-mission-nest-pas-ministre.md), [`partition-profils-legislature-580`](decisions/partition-profils-legislature-580.md), [`perimetre-controle-perte`](decisions/perimetre-controle-perte.md), [`plafond-roster-et-commit-518`](decisions/plafond-roster-et-commit-518.md), [`pythonunbuffered-generate-data`](decisions/pythonunbuffered-generate-data.md), [`qualification-perdue-a-la-fusion-639`](decisions/qualification-perdue-a-la-fusion-639.md), [`roster-unique-par-run-518`](decisions/roster-unique-par-run-518.md), [`trame-profil-candidat-328`](decisions/trame-profil-candidat-328.md).

## `src/candidate_profile_ue.py`

1 décision(s) le gouvernent ; le module en cite 0.

| Décision | Nomme |
| --- | --- |
| [Données UE — investigation des sources (2026-08-04)](decisions/investigation-sources-ue.md) | `find_mep_by_name` |

## `src/check_quality_gate.py`

8 décision(s) le gouvernent ; le module en cite 9.

| Décision | Nomme |
| --- | --- |
| [Quality gate : distinguer un index amendements jamais construit d'un index périmé (#254) (2026-08-13)](decisions/amendements-index-quality-gate-fraicheur.md) | `_AMENDEMENTS_INDISPONIBLES_PREFIX`, `_AMENDEMENTS_LEGISLATURES`, `_report_amendements_freshness` |
| [Index amendements des législatures 15/16 : construction manuelle hors CI, committée (2026-08-13)](decisions/amendements-legislatures-figees.md) | `_AMENDEMENTS_LEGISLATURES`, `_AMENDEMENTS_LEGISLATURES_FIGEES` |
| [Quality gate : « 0 amendement collecté » reste non bloquant, mais cesse d'être discret (#378) (2026-08-18)](decisions/amendements-zero-pas-de-hard-fail.md) | `_report_amendements_coverage` |
| [Les consommateurs de `chambre` migrés vers `chambres`, et le garde-fou qui datera son retrait (#494) (2026-08-20)](decisions/consommateurs-chambres-migres.md) | `_report_amendements_coverage`, `_report_groupes`, `_report_low_interventions`, `_report_low_syceron_coverage` |
| [Suspendre l'extraction des deux groupes Sénat, sans les retirer de la config (#516) (2026-08-24)](decisions/extraction-groupe-suspendue-516.md) | `_report_groupes` |
| [`check_quality_gate.py` : section gouvernements (§5), couverture ministérielle proxy par `portefeuille` (#212) (2026-08-14)](decisions/quality-gate-gouvernements.md) | `_GROUPE_NETWORK_SIGNALS`, `_report_gouvernements`, `_report_groupes` |
| [Un seul roster par run, une reprise sur ce qui est retentable, et des échecs qu'on peut lire (#518) (2026-08-24)](decisions/roster-unique-par-run-518.md) | `_gha_annotation` |
| [Seuil de couverture de groupe (`--groupe-min-members`) : conservé faute de chiffres réels à pleine échelle (2026-08-12)](decisions/seuil-couverture-groupe.md) | `_report_groupes` |

Le mentionnent sans le gouverner : [`absences-publiees-comme-faits-556-558-560`](decisions/absences-publiees-comme-faits-556-558-560.md), [`audit-599-projection-blocs-lus-628`](decisions/audit-599-projection-blocs-lus-628.md), [`audit-plages-temporelles`](decisions/audit-plages-temporelles.md), [`chambres-profil-derivees`](decisions/chambres-profil-derivees.md), [`corroboration-chambres-publiees-486`](decisions/corroboration-chambres-publiees-486.md), [`couverture-dossiers-hors-couverture-vs-zero`](decisions/couverture-dossiers-hors-couverture-vs-zero.md), [`deux-chambres-interrogees`](decisions/deux-chambres-interrogees.md), [`gouvernement-doc-cloture`](decisions/gouvernement-doc-cloture.md), [`gouvernement-profile-rattachement`](decisions/gouvernement-profile-rattachement.md), [`mode-extraction-leger-roster`](decisions/mode-extraction-leger-roster.md), [`oom-reconstruction-amendements-figees`](decisions/oom-reconstruction-amendements-figees.md), [`partition-profils-legislature-580`](decisions/partition-profils-legislature-580.md), [`populations-profils-portees-par-les-outils-630`](decisions/populations-profils-portees-par-les-outils-630.md), [`retry-generate-data-preemption`](decisions/retry-generate-data-preemption.md), [`test-adosse-au-corpus-vivant`](decisions/test-adosse-au-corpus-vivant.md).

## `src/correspondance_acteurs_an.py`

2 décision(s) le gouvernent ; le module en cite 1.

| Décision | Nomme |
| --- | --- |
| [La bascule : le roster des groupes AN vient d'AMO30 (#527, lot 1b de l'épic « une seule source AN ») (2026-08-26)](decisions/bascule-roster-an-amo30-527.md) | `CorrespondanceInvalide` |
| [La correspondance slug ↔ acteur AN devient un artefact committé (#525, lot 2 de l'épic « une seule source AN ») (2026-08-26)](decisions/correspondance-acteurs-an-525.md) | `est_declare_hors_an`, `resoudre_acteur_ref` |

Le mentionnent sans le gouverner : [`civilite-et-pcs-insee-659`](decisions/civilite-et-pcs-insee-659.md), [`identite-profils-539`](decisions/identite-profils-539.md), [`position-politique-groupes-686`](decisions/position-politique-groupes-686.md), [`roster-an-derive-amo30-526`](decisions/roster-an-derive-amo30-526.md), [`sparse-checkout-extract-an-674`](decisions/sparse-checkout-extract-an-674.md).

## `src/couverture_dossiers.py`

6 décision(s) le gouvernent ; le module en cite 3.

| Décision | Nomme |
| --- | --- |
| [Couverture des dossiers : « hors couverture de la source » ≠ « réellement à zéro » (#399) (2026-08-18)](decisions/couverture-dossiers-hors-couverture-vs-zero.md) | `AN_DOSSIERS_ARCHIVES`, `LEGISLATURES_DEBUT`, `borne_couverture_textes`, `statut_couverture_textes` |
| [Ce qu'une liste vide veut dire : les quatre états de couverture (#539) (2026-08-28)](decisions/couverture-listes-539.md) | `AN_DOSSIERS_ARCHIVES` |
| [Un amendement retrouve son dossier, et la clé qu'on lui avait retirée (#639, rang 3)](decisions/dossier-des-amendements-639.md) | `AN_DOSSIERS_ARCHIVES` |
| [Dossiers législatifs : ingestion multi-archives, origine par document déposé, statut `promulgue` (#400) (2026-08-18)](decisions/dossiers-multi-archives-origine-document.md) | `AN_DOSSIERS_ARCHIVES` |
| [Profils de gouvernement : ne jamais réécrire sur une collecte incomplète, et cache dossiers dédié (#427) (2026-08-18)](decisions/gouvernement-textes-non-ecrasement.md) | `legislatures_ingerees` |
| [Résoudre la `legislature` d'un vote : deux mécanismes, pas un seul (#432) (2026-08-19)](decisions/resolution-legislature-deux-mecanismes-432.md) | `LEGISLATURES_DEBUT` |

Le mentionnent sans le gouverner : [`absences-publiees-comme-faits-556-558-560`](decisions/absences-publiees-comme-faits-556-558-560.md).

## `src/couverture_profil.py`

5 décision(s) le gouvernent ; le module en cite 3.

| Décision | Nomme |
| --- | --- |
| [Trois absences publiées comme des faits (#556, #558, #560) (2026-08-29)](decisions/absences-publiees-comme-faits-556-558-560.md) | `DECISIONS_PIPELINE`, `MOTIFS_JAMAIS_PANNE`, `legislatures_du_profil` |
| [La collecte d'interventions des membres de roster est réduite au thème (#657) (2026-08-31)](decisions/collecte-interventions-reduite-au-theme-657.md) | `DECISIONS_ROSTER` |
| [Ce qu'une liste vide veut dire : les quatre états de couverture (#539) (2026-08-28)](decisions/couverture-listes-539.md) | `DECISIONS_PIPELINE`, `MOTIFS_PANNE` |
| [Une exception n'est pas une preuve, et un défaut de notre code n'est pas une panne de l'Assemblée nationale (#562) (2026-08-28)](decisions/defaut-collecte-vs-panne-562.md) | `MOTIFS_PANNE`, `_preuve_defaut_collecte` |
| [`meta.warnings[]` déclare son destinataire, dans un jumeau typé et aligné (#642) (2026-08-31)](decisions/destinataire-avertissements-642.md) | `MOTIFS_DEFAUT_COLLECTE`, `MOTIFS_JAMAIS_PANNE`, `MOTIFS_PANNE` |

Le mentionnent sans le gouverner : [`couverture-remplacee-par-liste-602`](decisions/couverture-remplacee-par-liste-602.md).

## `src/download_watchdog.py`

1 décision(s) le gouvernent ; le module en cite 1.

| Décision | Nomme |
| --- | --- |
| [Mandats commission/groupe_amitie/extra_parlementaire sourcés depuis l'AN, fetch_identity NosDéputés rendu conditionnel (#369, complet), watchdog générique sur tous les téléchargements zip (#370, complet) (2026-08-17)](decisions/mandats-officiels-an-369.md) | `download_with_watchdog` |

Le mentionnent sans le gouverner : [`budget-collecte-interventions`](decisions/budget-collecte-interventions.md).

## `src/garde_fou_blobs.py`

1 décision(s) le gouvernent ; le module en cite 1.

| Décision | Nomme |
| --- | --- |
| [Le seuil de blob sort du critère de sortie, et les profils bruts se partitionnent par législature (#580) (2026-08-29)](decisions/partition-profils-legislature-580.md) | `CONDUITE_A_TENIR` |

Le mentionnent sans le gouverner : [`collecte-interventions-reduite-au-theme-657`](decisions/collecte-interventions-reduite-au-theme-657.md), [`dossier-des-amendements-639`](decisions/dossier-des-amendements-639.md), [`qualification-scrutins-et-cle-dossier-639`](decisions/qualification-scrutins-et-cle-dossier-639.md), [`rattachement-au-dossier-interventions-et-scrutins-639`](decisions/rattachement-au-dossier-interventions-et-scrutins-639.md).

## `src/generate_all_profiles.py`

21 décision(s) le gouvernent ; le module en cite 3.

| Décision | Nomme |
| --- | --- |
| [Un bloc structuré sans fond n'écrase plus un bloc collecté (#484) (2026-08-30)](decisions/bloc-sans-fond-484.md) | `build_minimal_profile` |
| [Une source injoignable ne consomme plus le timeout d'un job, et son silence cesse de se lire comme un constat (#514) (2026-08-21)](decisions/budget-collecte-source-injoignable-514.md) | `_manifest_append`, `build_profile_any_chambre`, `process_candidat`, `valider_budgets` |
| [Budget d'exécution à pleine échelle : 630 min annoncées, 55 mesurées (#467) (2026-08-20)](decisions/budget-execution-pleine-echelle-467.md) | `_select_candidats_couverture`, `process_candidat` |
| [La chambre est un fait du mandat, pas du profil : `mandats[].chambre` estampillée à la collecte (#492) (2026-08-20)](decisions/chambre-par-mandat-electif.md) | `build_profile_any_chambre` |
| [Un timeout ne peut plus écraser le roster, et rien de collecté ne reste non publié (#511) (2026-08-20)](decisions/collecte-non-publiee.md) | `build_minimal_profile`, `process_candidat` |
| [Une exception n'est pas une preuve, et un défaut de notre code n'est pas une panne de l'Assemblée nationale (#562) (2026-08-28)](decisions/defaut-collecte-vs-panne-562.md) | `build_profile_any_chambre` |
| [Un paramètre commandait ce qu'il ne nommait pas (#578) (2026-08-29)](decisions/deux-axes-formulaire-578.md) | `_select_candidats_couverture`, `process_candidat` |
| [Le passé sénatorial est un fait de carrière, pas une donnée d'activité : bicaméral pour les candidats seulement (#488) (2026-08-20)](decisions/deux-chambres-interrogees.md) | `build_minimal_profile`, `build_profile_any_chambre`, `process_candidat` |
| [Un amendement retrouve son dossier, et la clé qu'on lui avait retirée (#639, rang 3)](decisions/dossier-des-amendements-639.md) | `_rafraichir_index_amendements` |
| [Borner l'historique de données : ce que ça rend vraiment, et quand (#434) (2026-08-20)](decisions/fenetre-historique-donnees.md) | `_select_existants` |
| [Comment naît l'identité d'un profil, et où vont les identifiants de source (#539) (2026-08-28)](decisions/identite-profils-539.md) | `WARNING_PREFIX_CHAMBRE_EN_ECHEC`, `_effective_slug`, `_select_existants`, `process_candidat` |
| [`extract-senat` ne collecte plus d'interventions : la collecte n'en retenait aucune, par construction (#501) (2026-08-20)](decisions/interventions-senat-501.md) | `_manifest_append`, `build_profile_any_chambre` |
| [`--limit` + `--skip-existing` sur `extract-roster-groupes` : sélection progressive + rafraîchissement (2026-08-12)](decisions/limit-skip-existing-roster-groupes.md) | `_select_candidats`, `_select_candidats_couverture`, `process_candidat` |
| [`extract-an` en matrix strategy par candidat, pour isoler la perte en cas de shutdown signal runner (#344) (2026-08-16)](decisions/matrix-extract-an-par-candidat.md) | `process_candidat` |
| [Un fichier de progression dans un répertoire de données (#518, troisième incident) (2026-08-24)](decisions/point-de-sauvegarde-dans-les-profils-518.md) | `DEFAULT_CHECKPOINT_PATH`, `_save_checkpoint` |
| [Le `texte_vise` fautif se reprend depuis l'archive figée, pas par une fusion plus permissive (#696, 01/09/2026)](decisions/report-texte-vise-source-696.md) | `_rafraichir_index_amendements` |
| [Retrait de `fetch_activity_synthesis` (#356) (2026-08-16)](decisions/retrait-fetch-activity-synthesis.md) | `build_minimal_profile` |
| [NosDéputés sort du pipeline (#529, lot 5 de l'épic « une seule source AN ») (2026-08-27)](decisions/retrait-nosdeputes-529.md) | `process_candidat` |
| [Le Sénat sort du périmètre, et le job qui concluait vert sans rien produire est retiré (#528, lot 3 de l'épic « une seule source AN ») (2026-08-26)](decisions/retrait-senat-528.md) | `SOURCE_VALUES` |
| [Un seul roster par run, une reprise sur ce qui est retentable, et des échecs qu'on peut lire (#518) (2026-08-24)](decisions/roster-unique-par-run-518.md) | `_annoter_github` |
| [Régénérer l'existant : `--refresh-existing`, l'inverse de `--skip-existing` (#445) (2026-08-19)](decisions/telechargement-an-trois-modes-defaillance.md) | `_select_candidats_couverture` |

Le mentionnent sans le gouverner : [`amendements-legislatures-figees`](decisions/amendements-legislatures-figees.md), [`chambres-profil-derivees`](decisions/chambres-profil-derivees.md), [`cle-fusion-interventions-540`](decisions/cle-fusion-interventions-540.md), [`collecte-vs-publie-545`](decisions/collecte-vs-publie-545.md), [`consommateurs-chambres-migres`](decisions/consommateurs-chambres-migres.md), [`id-pivot-sans-prefixe`](decisions/id-pivot-sans-prefixe.md), [`integrite-referentielle-pivot`](decisions/integrite-referentielle-pivot.md), [`libelles-formulaire`](decisions/libelles-formulaire.md), [`licence-lot-6-530`](decisions/licence-lot-6-530.md), [`licences`](decisions/licences.md), [`limit-sample`](decisions/limit-sample.md), [`mode-extraction-leger-roster`](decisions/mode-extraction-leger-roster.md), [`normalisation-amendements`](decisions/normalisation-amendements.md), [`normalisation-votes`](decisions/normalisation-votes.md), [`oom-reconstruction-amendements-figees`](decisions/oom-reconstruction-amendements-figees.md), [`partition-profils-legislature-580`](decisions/partition-profils-legislature-580.md), [`pivot-freshness-timestamps-stables`](decisions/pivot-freshness-timestamps-stables.md), [`provenance-pivot`](decisions/provenance-pivot.md), [`publication-scopee-artifacts`](decisions/publication-scopee-artifacts.md), [`retry-generate-data-preemption`](decisions/retry-generate-data-preemption.md), [`sparse-checkout-extract-an-674`](decisions/sparse-checkout-extract-an-674.md), [`workers-fige-a-1`](decisions/workers-fige-a-1.md).

## `src/generate_gouvernement_profiles.py`

5 décision(s) le gouvernent ; le module en cite 3.

| Décision | Nomme |
| --- | --- |
| [Cloisonnement de la branche roster, et le code 2 « suspension totale » (#524) (2026-08-26)](decisions/cloisonnement-branche-roster-524.md) | `EXIT_COLLECTE_INCOMPLETE` |
| [Extension de la stabilité des horodatages aux profils groupe/gouvernement/parti (#343, complet) (2026-08-17)](decisions/freshness-timestamps-groupes-gouvernements-partis.md) | `generate_all` |
| [Profils de gouvernement : ne jamais réécrire sur une collecte incomplète, et cache dossiers dédié (#427) (2026-08-18)](decisions/gouvernement-textes-non-ecrasement.md) | `COLLECTE_INCOMPLETE` |
| [Le `label` d'un mandat `MINISTERE` ne dit pas si c'est un maroquin (#474) (2026-08-20)](decisions/parlementaire-en-mission-nest-pas-ministre.md) | `COLLECTE_INCOMPLETE` |
| [Le plafond de lecture du roster, et le commit qui ne paie plus pour une source lente (#518, second incident) (2026-08-24)](decisions/plafond-roster-et-commit-518.md) | `EXIT_COLLECTE_INCOMPLETE` |

Le mentionnent sans le gouverner : [`audit-599-projection-blocs-lus-628`](decisions/audit-599-projection-blocs-lus-628.md), [`gouvernement-ci-integration`](decisions/gouvernement-ci-integration.md), [`gouvernement-profile-rattachement`](decisions/gouvernement-profile-rattachement.md), [`lectures-pipeline-par-projection-635`](decisions/lectures-pipeline-par-projection-635.md).

## `src/generate_group_profiles.py`

2 décision(s) le gouvernent ; le module en cite 1.

| Décision | Nomme |
| --- | --- |
| [Cloisonnement de la branche roster, et le code 2 « suspension totale » (#524) (2026-08-26)](decisions/cloisonnement-branche-roster-524.md) | `EXIT_ROSTER_INDISPONIBLE` |
| [Le plafond de lecture du roster, et le commit qui ne paie plus pour une source lente (#518, second incident) (2026-08-24)](decisions/plafond-roster-et-commit-518.md) | `ResultatGeneration` |

Le mentionnent sans le gouverner : [`consommateurs-chambres-migres`](decisions/consommateurs-chambres-migres.md), [`extraction-groupe-suspendue-516`](decisions/extraction-groupe-suspendue-516.md), [`gouvernement-profile-rattachement`](decisions/gouvernement-profile-rattachement.md), [`integrite-referentielle-pivot`](decisions/integrite-referentielle-pivot.md), [`position-politique-groupes-686`](decisions/position-politique-groupes-686.md), [`roster-an-derive-amo30-526`](decisions/roster-an-derive-amo30-526.md), [`senat-periode-debut`](decisions/senat-periode-debut.md).

## `src/generate_roster_candidats.py`

6 décision(s) le gouvernent ; le module en cite 3.

| Décision | Nomme |
| --- | --- |
| [La bascule : le roster des groupes AN vient d'AMO30 (#527, lot 1b de l'épic « une seule source AN ») (2026-08-26)](decisions/bascule-roster-an-amo30-527.md) | `build_roster_candidats_detaille`, `membres_sans_slug` |
| [Cloisonnement de la branche roster, et le code 2 « suspension totale » (#524) (2026-08-26)](decisions/cloisonnement-branche-roster-524.md) | `anomalies_roster`, `fetch_rosters_bruts`, `resume_exception` |
| [Un timeout ne peut plus écraser le roster, et rien de collecté ne reste non publié (#511) (2026-08-20)](decisions/collecte-non-publiee.md) | `fetch_rosters_bruts` |
| [Suspendre l'extraction des deux groupes Sénat, sans les retirer de la config (#516) (2026-08-24)](decisions/extraction-groupe-suspendue-516.md) | `fetch_rosters_bruts` |
| [NosDéputés sort du pipeline (#529, lot 5 de l'épic « une seule source AN ») (2026-08-27)](decisions/retrait-nosdeputes-529.md) | `membres_sans_slug` |
| [Le roster des groupes AN est dérivé d'AMO30, derrière un drapeau baissé (#526, lot 1 de l'épic « une seule source AN ») (2026-08-26)](decisions/roster-an-derive-amo30-526.md) | `build_roster_candidats_detaille`, `membres_sans_slug` |

Le mentionnent sans le gouverner : [`collecte-interventions-reduite-au-theme-657`](decisions/collecte-interventions-reduite-au-theme-657.md), [`consommateurs-chambres-migres`](decisions/consommateurs-chambres-migres.md), [`merge-and-pivot-budget-permissions-413`](decisions/merge-and-pivot-budget-permissions-413.md), [`plafond-roster-et-commit-518`](decisions/plafond-roster-et-commit-518.md), [`provenance-pivot`](decisions/provenance-pivot.md), [`revue-workflows-ci-342`](decisions/revue-workflows-ci-342.md), [`roster-unique-par-run-518`](decisions/roster-unique-par-run-518.md), [`telechargement-an-trois-modes-defaillance`](decisions/telechargement-an-trois-modes-defaillance.md), [`web-v3-ui`](decisions/web-v3-ui.md).

## `src/gha.py`

Le mentionnent sans le gouverner : [`plafond-roster-et-commit-518`](decisions/plafond-roster-et-commit-518.md), [`roster-unique-par-run-518`](decisions/roster-unique-par-run-518.md).

## `src/gouvernement_profile.py`

2 décision(s) le gouvernent ; le module en cite 0.

| Décision | Nomme |
| --- | --- |
| [`gouvernement_profile.py` : rattachement des textes par `date_depot`, exclusion silencieuse des dossiers non classifiables (#211) (2026-08-14)](decisions/gouvernement-profile-rattachement.md) | `build_gouvernement_profile` |
| [Trois lectures du corpus passent à la projection, et chacune a son plafond dans un test (#635, 2026-08-30)](decisions/lectures-pipeline-par-projection-635.md) | `_index_acteur_ref_vers_membre`, `build_gouvernement_profile` |

Le mentionnent sans le gouverner : [`audit-599-projection-blocs-lus-628`](decisions/audit-599-projection-blocs-lus-628.md), [`audit-pipeline-gouvernement`](decisions/audit-pipeline-gouvernement.md), [`freshness-timestamps-groupes-gouvernements-partis`](decisions/freshness-timestamps-groupes-gouvernements-partis.md), [`gouvernement-premier-ministre-portefeuille`](decisions/gouvernement-premier-ministre-portefeuille.md), [`gouvernement-textes-fam-codes-archives`](decisions/gouvernement-textes-fam-codes-archives.md), [`gouvernement-textes-fam-codes-manquants`](decisions/gouvernement-textes-fam-codes-manquants.md), [`gouvernement-textes-initiateurs`](decisions/gouvernement-textes-initiateurs.md), [`hors-perimetre`](decisions/hors-perimetre.md), [`parlementaire-en-mission-nest-pas-ministre`](decisions/parlementaire-en-mission-nest-pas-ministre.md), [`pivot-freshness-timestamps-stables`](decisions/pivot-freshness-timestamps-stables.md).

## `src/gouvernement_roster.py`

12 décision(s) le gouvernent ; le module en cite 3.

| Décision | Nomme |
| --- | --- |
| [Un audit lit le corpus par projection, et son plafond de mémoire est dans un test (#628, 2026-08-30)](decisions/audit-599-projection-blocs-lus-628.md) | `load_profils_from_dir` |
| [La civilité et la nomenclature PCS de l'INSEE traversaient le pipeline sans y laisser de trace (#659) (2026-08-31)](decisions/civilite-et-pcs-insee-659.md) | `_normalise_fonction` |
| [`membres[]` publiait deux fois le même fait : dédupliquer sans effacer les changements de portefeuille (#480) (2026-08-20)](decisions/deduplication-entrees-membres.md) | `_source_url_portefeuille`, `build_gouvernement_roster`, `build_premier_ministre` |
| [`gouvernement_profile` : `premier_ministre` et `portefeuille` câblés depuis les mandats `MINISTERE` (#398) (2026-08-18)](decisions/gouvernement-premier-ministre-portefeuille.md) | `_est_mandat_appartenance_gouvernement` |
| [`gouvernement_roster.py` : désambiguïsation par libellé exact + garde-fou de période, pas l'inverse (#209) (2026-08-14)](decisions/gouvernement-roster-desambiguisation.md) | `build_gouvernement_roster` |
| [Profils de gouvernement : le lien ministre → texte (#435) (2026-08-18)](decisions/gouvernement-textes-initiateurs.md) | `acteur_ref_depuis_profil` |
| [L'`id` d'un profil pivot est le slug : le préfixe de provenance était instable (#487) (2026-08-20)](decisions/id-pivot-sans-prefixe.md) | `build_gouvernement_roster` |
| [Trois lectures du corpus passent à la projection, et chacune a son plafond dans un test (#635, 2026-08-30)](decisions/lectures-pipeline-par-projection-635.md) | `BLOCS_LUS_COMPOSITION`, `acteur_ref_depuis_profil`, `build_premier_ministre`, `load_profils_from_dir` |
| [Le libellé d'organe du chef du gouvernement s'accorde en genre, la qualité jamais (#658) (2026-08-31)](decisions/libelle-chef-du-gouvernement-au-feminin-658.md) | `FONCTIONS_MINISTERIELLES_OBSERVEES`, `LABELS_PORTEFEUILLE_PREMIER_MINISTRE_OBSERVES`, `_normalise_fonction`, `_normalise_libelle_organe`, `_normalise_typographique`, `build_gouvernement_roster`, `build_premier_ministre` |
| [Le `label` d'un mandat `MINISTERE` ne dit pas si c'est un maroquin (#474) (2026-08-20)](decisions/parlementaire-en-mission-nest-pas-ministre.md) | `FONCTIONS_MINISTERIELLES`, `FONCTIONS_MINISTERIELLES_OBSERVEES`, `_est_mandat_appartenance_gouvernement`, `_normalise_fonction`, `_portefeuilles_du_mandat`, `_qualite_portefeuille`, `build_gouvernement_roster`, `build_premier_ministre` |
| [`check_quality_gate.py` : section gouvernements (§5), couverture ministérielle proxy par `portefeuille` (#212) (2026-08-14)](decisions/quality-gate-gouvernements.md) | `build_gouvernement_roster` |
| [Un test d'acceptation adossé au corpus vivant rougit quand la donnée s'améliore (#457) (2026-08-20)](decisions/test-adosse-au-corpus-vivant.md) | `build_gouvernement_roster` |

Le mentionnent sans le gouverner : [`gouvernement-ci-integration`](decisions/gouvernement-ci-integration.md), [`gouvernement-profile-rattachement`](decisions/gouvernement-profile-rattachement.md), [`mandat-electif-perdu-fausse-le-denominateur`](decisions/mandat-electif-perdu-fausse-le-denominateur.md), [`perimetre-controle-perte`](decisions/perimetre-controle-perte.md).

## `src/gouvernement_textes.py`

10 décision(s) le gouvernent ; le module en cite 5.

| Décision | Nomme |
| --- | --- |
| [Dossiers législatifs : ingestion multi-archives, origine par document déposé, statut `promulgue` (#400) (2026-08-18)](decisions/dossiers-multi-archives-origine-document.md) | `iter_dossiers_bruts` |
| [`gouvernement_textes` : 3 derniers `fam_code` mappés ; `TSORTF02` tranché sur données réelles (#402) (2026-08-18)](decisions/gouvernement-textes-fam-codes-archives.md) | `_FAM_CODE_STATUT_MAP`, `_STATUTS_CORRIGES_PAR_PROMULGATION` |
| [`gouvernement_textes` : 3 `fam_code` manquants excluaient 42 % des textes ; `adopte_cmp` ajouté à la nomenclature (#397) (2026-08-18)](decisions/gouvernement-textes-fam-codes-manquants.md) | `_FAM_CODE_STATUT_MAP` |
| [Profils de gouvernement : le lien ministre → texte (#435) (2026-08-18)](decisions/gouvernement-textes-initiateurs.md) | `parse_dossier_gouvernemental` |
| [Profils de gouvernement : ne jamais réécrire sur une collecte incomplète, et cache dossiers dédié (#427) (2026-08-18)](decisions/gouvernement-textes-non-ecrasement.md) | `fetch_dossiers_gouvernementaux` |
| [`gouvernement_textes.py` : filtre de statut par décision de séance, pas par `codeActe`/`fam_code` seul (#210) (2026-08-14)](decisions/gouvernement-textes-statut.md) | `DOSSIERS_CACHE_DIR`, `_est_decision_de_seance`, `ensure_dossiers_zip_downloaded` |
| [`gouvernement_textes.py` : filtre de statut par décision de séance, pas par `codeActe`/`fam_code` seul (#210) (2026-08-14)](decisions/gouvernement-textes-statut-210-version-initiale.md) | `DOSSIERS_CACHE_DIR`, `_est_decision_de_seance`, `ensure_dossiers_zip_downloaded` |
| [Mandats commission/groupe_amitie/extra_parlementaire sourcés depuis l'AN, fetch_identity NosDéputés rendu conditionnel (#369, complet), watchdog générique sur tous les téléchargements zip (#370, complet) (2026-08-17)](decisions/mandats-officiels-an-369.md) | `ensure_dossiers_zip_downloaded` |
| [Un projet de loi porté au nom du Gouvernement n'est pas une production personnelle (#689) (2026-09-01)](decisions/qualification-textes-portes-689.md) | `nature_texte_depose` |
| [Résilience de `generate-data.yml` face aux `shutdown signal` runner : continue-on-error généralisé, watchdog réseau, retry générique sur `_get_payload`, retry `retry-generate-data.yml` non-régressif, et appels NosDéputés morts pour les députés (dossiers, votes) (2026-08-16)](decisions/resilience-generate-data-shutdown-signal.md) | `ensure_dossiers_zip_downloaded` |

Le mentionnent sans le gouverner : [`audit-pipeline-gouvernement`](decisions/audit-pipeline-gouvernement.md), [`couverture-dossiers-hors-couverture-vs-zero`](decisions/couverture-dossiers-hors-couverture-vs-zero.md), [`gouvernement-ci-integration`](decisions/gouvernement-ci-integration.md), [`gouvernement-doc-cloture`](decisions/gouvernement-doc-cloture.md), [`gouvernement-profile-rattachement`](decisions/gouvernement-profile-rattachement.md), [`gouvernement-textes-statut-49-3-rejete`](decisions/gouvernement-textes-statut-49-3-rejete.md), [`hors-perimetre`](decisions/hors-perimetre.md), [`plafond-roster-et-commit-518`](decisions/plafond-roster-et-commit-518.md), [`quality-gate-gouvernements`](decisions/quality-gate-gouvernements.md).

## `src/group_profile.py`

22 décision(s) le gouvernent ; le module en cite 4.

| Décision | Nomme |
| --- | --- |
| [Un amendement cosigné n'est pas N amendements : deux grandeurs, deux noms (#643) (2026-08-31)](decisions/amendements-distincts-et-signatures-643.md) | `ContributionAmendements`, `CumulAmendementsDistincts`, `_aggregate_amendements`, `_compute_cohesion_votes`, `_member_eligibility_intervals`, `load_profil_from_file` |
| [Un audit lit le corpus par projection, et son plafond de mémoire est dans un test (#628, 2026-08-30)](decisions/audit-599-projection-blocs-lus-628.md) | `generate_groupe_profile_from_roster` |
| [La bascule : le roster des groupes AN vient d'AMO30 (#527, lot 1b de l'épic « une seule source AN ») (2026-08-26)](decisions/bascule-roster-an-amo30-527.md) | `_avertissement_fraicheur_an` |
| [La chambre est un fait du mandat, pas du profil : `mandats[].chambre` estampillée à la collecte (#492) (2026-08-20)](decisions/chambre-par-mandat-electif.md) | `_aggregate_mandats`, `_compute_cohesion_votes`, `_is_eligible_at`, `_mandats_electifs`, `_member_eligibility_intervals`, `build_groupe_profile`, `compute_ecarts_cohesion_internes` |
| [Tous les comptes d'une fiche de groupe se rapportent à une date, et elle est publiée (#653) (2026-08-31)](decisions/date-de-reference-des-comptes-de-groupe-653.md) | `_intervals_overlap`, `_select_mandat_a_la_date`, `_select_mandat_entree_unique` |
| [`debut_dans_groupe` se lit sur le mandat de groupe, plus sur le premier mandat électif (#653) (2026-08-31)](decisions/dates-appartenance-groupe-653.md) | `build_groupe_profile` |
| [Le passé sénatorial est un fait de carrière, pas une donnée d'activité : bicaméral pour les candidats seulement (#488) (2026-08-20)](decisions/deux-chambres-interrogees.md) | `_is_eligible_at`, `_member_eligibility_intervals` |
| [Extension de la stabilité des horodatages aux profils groupe/gouvernement/parti (#343, complet) (2026-08-17)](decisions/freshness-timestamps-groupes-gouvernements-partis.md) | `generate_groupe_profile_from_roster` |
| [Juxtaposer deux positions sourcées n'est pas mesurer un écart (#328) — 01/09/2026](decisions/juxtaposition-position-groupe-328.md) | `compute_ecarts_cohesion_internes` |
| [Trois lectures du corpus passent à la projection, et chacune a son plafond dans un test (#635, 2026-08-30)](decisions/lectures-pipeline-par-projection-635.md) | `BLOCS_LUS_MEMBRE`, `_aggregate_amendements`, `_aggregate_mandats`, `_is_pivot_v1`, `aggregate_tags_thematiques`, `build_groupe_profile`, `compute_ecarts_cohesion_internes`, `contribution_amendements`, `generate_groupe_profile_from_roster`, `load_profil_from_file` |
| [Un mandat électif perdu ne manque pas seulement sur la fiche : il sort le membre du dénominateur de son groupe (#465) (2026-08-20)](decisions/mandat-electif-perdu-fausse-le-denominateur.md) | `_aggregate_amendements`, `_member_eligibility_intervals` |
| [`mandats_agreges` : agrégation catégorielle sur `mandats[]`, famille 1 (#361, sous-issue de #349) (2026-08-16)](decisions/mandats-agreges-famille-1.md) | `MANDATS_AGREGES_CATEGORIES`, `_aggregate_mandats`, `_compute_cohesion_votes`, `_intervals_overlap`, `_is_eligible_at`, `_member_eligibility_intervals`, `_select_mandat_entree_unique` |
| [`mandats_agreges` : « qui y siège » et « qui y est passé » sont deux nombres, pas un (#656) (2026-08-31)](decisions/mandats-agreges-siege-vs-passe-656.md) | `_aggregate_mandats` |
| [Normaliser les amendements : le coût n'est pas l'amendement, c'est sa liste de cosignataires (#431) (2026-08-19)](decisions/normalisation-amendements.md) | `_aggregate_amendements` |
| [Normalisation de `par_fonction` dans `mandats_agreges`, et requalification du défaut « catégorie commission » (#379) (2026-08-17)](decisions/normalisation-fonction-mandats-agreges.md) | `_aggregate_mandats`, `_normalize_fonction_mandat` |
| [Normaliser les votes : une liste partagée, un mapping, et deux invariants devenus des jointures (#432) (2026-08-19)](decisions/normalisation-votes.md) | `_votes_de_legislature` |
| [Résoudre la `legislature` d'un vote : deux mécanismes, pas un seul (#432) (2026-08-19)](decisions/resolution-legislature-deux-mecanismes-432.md) | `_votes_de_legislature` |
| [Restaurer 789 interventions sans revenir sur le reste du schéma (#460) (2026-08-19)](decisions/restauration-interventions.md) | `aggregate_tags_thematiques` |
| [NosDéputés sort du pipeline (#529, lot 5 de l'épic « une seule source AN ») (2026-08-27)](decisions/retrait-nosdeputes-529.md) | `_avertissement_fraicheur_an` |
| [Groupes Sénat : ne pas renseigner `senat_periode_debut` dans `groupes_reels.json` (2026-08-12)](decisions/senat-periode-debut.md) | `generate_groupe_profile_from_roster` |
| [Taxonomie des mandats : exploitation des `typeOrgane` AN non mappés (#382, option « mixte ») (2026-08-17)](decisions/taxonomie-mandats-typeorgane-an.md) | `MANDATS_AGREGES_CATEGORIES` |
| [Votes : agrégation des législatures 14 à 17, index dédupliqué, 14/15/16 figées (#403) (2026-08-18)](decisions/votes-multi-legislature.md) | `_compute_cohesion_votes` |

Le mentionnent sans le gouverner : [`civilite-et-pcs-insee-659`](decisions/civilite-et-pcs-insee-659.md), [`consommateurs-chambres-migres`](decisions/consommateurs-chambres-migres.md), [`id-pivot-sans-prefixe`](decisions/id-pivot-sans-prefixe.md), [`identite-profils-539`](decisions/identite-profils-539.md), [`mandats-electifs-liste-complete-640`](decisions/mandats-electifs-liste-complete-640.md), [`ne-jamais-committer-un-build-perime`](decisions/ne-jamais-committer-un-build-perime.md), [`pivot-freshness-timestamps-stables`](decisions/pivot-freshness-timestamps-stables.md), [`populations-profils-portees-par-les-outils-630`](decisions/populations-profils-portees-par-les-outils-630.md), [`profil-de-groupe-lecture-329`](decisions/profil-de-groupe-lecture-329.md), [`provenance-par-champ-603`](decisions/provenance-par-champ-603.md), [`syceron-acteur-ref-nu-510`](decisions/syceron-acteur-ref-nu-510.md), [`syceron-archives-verifiees-parseur-510`](decisions/syceron-archives-verifiees-parseur-510.md).

## `src/group_roster.py`

7 décision(s) le gouvernent ; le module en cite 3.

| Décision | Nomme |
| --- | --- |
| [La bascule : le roster des groupes AN vient d'AMO30 (#527, lot 1b de l'épic « une seule source AN ») (2026-08-26)](decisions/bascule-roster-an-amo30-527.md) | `ERREURS_ROSTER`, `fetch_full_roster` |
| [Suspendre l'extraction des deux groupes Sénat, sans les retirer de la config (#516) (2026-08-24)](decisions/extraction-groupe-suspendue-516.md) | `fetch_full_roster` |
| [Le plafond de lecture du roster, et le commit qui ne paie plus pour une source lente (#518, second incident) (2026-08-24)](decisions/plafond-roster-et-commit-518.md) | `fetch_full_roster` |
| [NosDéputés sort du pipeline (#529, lot 5 de l'épic « une seule source AN ») (2026-08-27)](decisions/retrait-nosdeputes-529.md) | `ERREURS_ROSTER`, `fetch_full_roster`, `filter_roster_by_sigle` |
| [Le Sénat sort du périmètre, et le job qui concluait vert sans rien produire est retiré (#528, lot 3 de l'épic « une seule source AN ») (2026-08-26)](decisions/retrait-senat-528.md) | `ERREURS_ROSTER`, `filter_roster_by_sigle` |
| [Le roster des groupes AN est dérivé d'AMO30, derrière un drapeau baissé (#526, lot 1 de l'épic « une seule source AN ») (2026-08-26)](decisions/roster-an-derive-amo30-526.md) | `fetch_full_roster`, `filter_roster_by_sigle` |
| [Un seul roster par run, une reprise sur ce qui est retentable, et des échecs qu'on peut lire (#518) (2026-08-24)](decisions/roster-unique-par-run-518.md) | `fetch_full_roster` |

Le mentionnent sans le gouverner : [`cloisonnement-branche-roster-524`](decisions/cloisonnement-branche-roster-524.md), [`profil-de-groupe-lecture-329`](decisions/profil-de-groupe-lecture-329.md), [`senat-periode-debut`](decisions/senat-periode-debut.md), [`votes-multi-legislature`](decisions/votes-multi-legislature.md).

## `src/groupes_config.py`

4 décision(s) le gouvernent ; le module en cite 0.

| Décision | Nomme |
| --- | --- |
| [Trois absences publiées comme des faits (#556, #558, #560) (2026-08-29)](decisions/absences-publiees-comme-faits-556-558-560.md) | `anomalies_suspension`, `index_membres_de_groupes_suspendus` |
| [La bascule : le roster des groupes AN vient d'AMO30 (#527, lot 1b de l'épic « une seule source AN ») (2026-08-26)](decisions/bascule-roster-an-amo30-527.md) | `CorrespondanceSiglesInvalide` |
| [Suspendre l'extraction des deux groupes Sénat, sans les retirer de la config (#516) (2026-08-24)](decisions/extraction-groupe-suspendue-516.md) | `anomalies_suspension` |
| [La position politique d'un groupe est celle que l'Assemblée déclare, lue dans une table committée (#686) (2026-09-01)](decisions/position-politique-groupes-686.md) | `CHEMIN_CONFIG_GROUPES`, `CLE_CORRESPONDANCE_SIGLES`, `CorrespondanceSiglesInvalide`, `charger_correspondance_sigles`, `entree_correspondance`, `position_politique_publiee` |

## `src/json_io.py`

1 décision(s) le gouvernent ; le module en cite 0.

| Décision | Nomme |
| --- | --- |
| [Un timeout ne peut plus écraser le roster, et rien de collecté ne reste non publié (#511) (2026-08-20)](decisions/collecte-non-publiee.md) | `ecrire_profil_json` |

Le mentionnent sans le gouverner : [`profils-json-compact`](decisions/profils-json-compact.md).

## `src/licences.py`

1 décision(s) le gouvernent ; le module en cite 0.

| Décision | Nomme |
| --- | --- |
| [Le versant AN passe en Licence Ouverte, et `meta.licence_donnees` devient un champ dérivé (#530, lot 6 de l'épic « une seule source AN ») (2026-08-27)](decisions/licence-lot-6-530.md) | `appliquer_licence_donnees` |

Le mentionnent sans le gouverner : [`licences`](decisions/licences.md), [`pages-statiques-methodologie-mentions-legales`](decisions/pages-statiques-methodologie-mentions-legales.md).

## `src/mep_profile.py`

Le mentionnent sans le gouverner : [`chambres-profil-derivees`](decisions/chambres-profil-derivees.md), [`consommateurs-chambres-migres`](decisions/consommateurs-chambres-migres.md), [`id-pivot-sans-prefixe`](decisions/id-pivot-sans-prefixe.md), [`licences`](decisions/licences.md), [`mandats-officiels-an-369`](decisions/mandats-officiels-an-369.md).

## `src/merge_profile.py`

49 décision(s) le gouvernent ; le module en cite 5.

| Décision | Nomme |
| --- | --- |
| [Un bloc structuré sans fond n'écrase plus un bloc collecté (#484) (2026-08-30)](decisions/bloc-sans-fond-484.md) | `BLOCS_PROTEGES_DU_VIDE`, `_merge_pivot_sources`, `_prefer_non_empty`, `_synchro_la_plus_recente`, `bloc_sans_fond`, `merge_raw_profile`, `preserver_collectes_non_vides` |
| [Le correctif de #540 validé en conditions réelles, et les deux budgets qu'il a périmés (#546) (2026-08-27)](decisions/budgets-extract-an-perimes-546.md) | `clean_stale_interventions` |
| [La chambre est un fait du mandat, pas du profil : `mandats[].chambre` estampillée à la collecte (#492) (2026-08-20)](decisions/chambre-par-mandat-electif.md) | `backfill_mandat_chambre`, `merge_lists_by_key`, `merge_raw_dirs` |
| [`chambres` au niveau profil : une liste dérivée, et `chambre` qui n'en est plus que le premier élément (#493) (2026-08-20)](decisions/chambres-profil-derivees.md) | `_prefer_non_empty`, `backfill_mandat_chambre`, `merge_lists_by_key`, `merge_pivot_profile` |
| [Une URL de source n'est pas un identifiant : la clé de fusion des interventions (#540) (2026-08-27)](decisions/cle-fusion-interventions-540.md) | `_intervention_key`, `_pivot_amendement_key`, `_pivot_intervention_key`, `_pivot_mandat_key`, `_pivot_texte_key`, `_pivot_vote_key`, `clean_stale_interventions`, `clean_stale_textes_portes`, `merge_lists_by_key` |
| [Une clé de fusion en `a or b` change d'identité quand `a` se remplit (#668) (2026-08-31)](decisions/cle-fusion-textes-portes-668.md) | `_dossier_key`, `_intervention_key`, `_pivot_amendement_key`, `_pivot_intervention_key`, `_pivot_texte_key`, `_pivot_vote_key`, `_repli_texte_key`, `clean_stale_interventions`, `clean_stale_textes_portes`, `merge_dossier_records`, `merge_pivot_profile` |
| [La collecte d'interventions des membres de roster est réduite au thème (#657) (2026-08-31)](decisions/collecte-interventions-reduite-au-theme-657.md) | `merge_pivot_profile` |
| [Ce que la normalisation a le droit de faire : la table de relations collecté → publié (#545) (2026-08-28)](decisions/collecte-vs-publie-545.md) | `_pivot_vote_key` |
| [Les consommateurs de `chambre` migrés vers `chambres`, et le garde-fou qui datera son retrait (#494) (2026-08-20)](decisions/consommateurs-chambres-migres.md) | `_prefer_non_empty`, `merge_pivot_profile`, `merge_raw_profile` |
| [La corroboration porte sur les chambres publiées, pas sur la complétude des mandats — et la condition de retrait de `chambre` devient atteignable (#486) (2026-08-30)](decisions/corroboration-chambres-publiees-486.md) | `FAMILLES_WARNINGS`, `_prefer_non_empty`, `backfill_mandat_chambre`, `merge_pivot_profile` |
| [Ce qu'une liste vide veut dire : les quatre états de couverture (#539) (2026-08-28)](decisions/couverture-listes-539.md) | `_prefer_non_empty` |
| [La couverture se remplace à la maille où #539 la publie, et un cas non tranchable se déclare (#602) (2026-08-30)](decisions/couverture-remplacee-par-liste-602.md) | `FAMILLES_WARNINGS`, `_prefer_non_empty`, `fusionner_couverture` |
| [`meta.warnings[]` déclare son destinataire, dans un jumeau typé et aligné (#642) (2026-08-31)](decisions/destinataire-avertissements-642.md) | `_prune_stale_warnings`, `unir_warnings` |
| [Le passé sénatorial est un fait de carrière, pas une donnée d'activité : bicaméral pour les candidats seulement (#488) (2026-08-20)](decisions/deux-chambres-interrogees.md) | `_prefer_non_empty`, `merge_raw_profile` |
| [Un amendement retrouve son dossier, et la clé qu'on lui avait retirée (#639, rang 3)](decisions/dossier-des-amendements-639.md) | `_amendement_key` |
| [Borner l'historique de données : ce que ça rend vraiment, et quand (#434) (2026-08-20)](decisions/fenetre-historique-donnees.md) | `merge_raw_profile` |
| [Un filtre de publication posé avant la fusion ne filtre rien (#641, réouverture) (2026-08-31)](decisions/filtre-publication-apres-fusion-641.md) | `FILTRES_PUBLICATION_IDENTITE`, `_composer_identite`, `bloc_sans_fond`, `deriver_provenance_champs`, `filtrer_identite_publiee`, `merge_pivot_profile` |
| [Extension de la stabilité des horodatages aux profils groupe/gouvernement/parti (#343, complet) (2026-08-17)](decisions/freshness-timestamps-groupes-gouvernements-partis.md) | `load_existing_document`, `preserve_stable_freshness_timestamps` |
| [Profils de gouvernement : ne jamais réécrire sur une collecte incomplète, et cache dossiers dédié (#427) (2026-08-18)](decisions/gouvernement-textes-non-ecrasement.md) | `preserve_stable_freshness_timestamps` |
| [L'`id` d'un profil pivot est le slug : le préfixe de provenance était instable (#487) (2026-08-20)](decisions/id-pivot-sans-prefixe.md) | `merge_pivot_profile`, `merge_raw_profile` |
| [Index amendements shardé par acteur (#392) (2026-08-17)](decisions/index-amendements-sharde-par-acteur.md) | `_amendement_key` |
| [`extract-senat` ne collecte plus d'interventions : la collecte n'en retenait aucune, par construction (#501) (2026-08-20)](decisions/interventions-senat-501.md) | `preserver_collectes_non_vides` |
| [Le versant AN passe en Licence Ouverte, et `meta.licence_donnees` devient un champ dérivé (#530, lot 6 de l'épic « une seule source AN ») (2026-08-27)](decisions/licence-lot-6-530.md) | `_merge_pivot_sources`, `merge_pivot_profile` |
| [Un profil publie tous ses mandats de député, et le compteur devient un témoin de couverture (#640) (2026-08-31)](decisions/mandats-electifs-liste-complete-640.md) | `_pivot_mandat_key` |
| [`merge-and-pivot` : garde-fou #390 hors `main`, entrées de configuration, budget de temps mur, permissions (#413) (2026-08-18)](decisions/merge-and-pivot-budget-permissions-413.md) | `merge_pivot_profile` |
| [`overwrite_profiles` : écraser les profils sans purger le cache (2026-08-19)](decisions/overwrite-profiles-sans-purge-cache.md) | `merge_lists_by_key` |
| [Le `label` d'un mandat `MINISTERE` ne dit pas si c'est un maroquin (#474) (2026-08-20)](decisions/parlementaire-en-mission-nest-pas-ministre.md) | `preserve_stable_freshness_timestamps` |
| [Le seuil de blob sort du critère de sortie, et les profils bruts se partitionnent par législature (#580) (2026-08-29)](decisions/partition-profils-legislature-580.md) | `merge_raw_dirs` |
| [Un champ d'identité publié ne meurt plus sans un run à perte déclarée (#601) (2026-08-30)](decisions/permanence-champs-identite-601.md) | `fusionner_identite` |
| [`genere_le`/`synchro_le` des pivots ne doivent avancer que si le contenu change réellement (#343) (2026-08-16)](decisions/pivot-freshness-timestamps-stables.md) | `_pivot_content_fingerprint`, `merge_pivot_profile`, `preserve_stable_freshness_timestamps` |
| [Un fichier de progression dans un répertoire de données (#518, troisième incident) (2026-08-24)](decisions/point-de-sauvegarde-dans-les-profils-518.md) | `merge_raw_dirs` |
| [Profils écrits en JSON compact, groupes et gouvernements indentés (#433) (2026-08-18)](decisions/profils-json-compact.md) | `_pivot_content_fingerprint`, `preserve_stable_freshness_timestamps` |
| [Quelle source a rempli quel champ, et quand — un bloc à côté d'`identite` (#603) (2026-08-30)](decisions/provenance-par-champ-603.md) | `_accorder_hatvp`, `_composer_identite`, `_merge_pivot_sources`, `fusionner_identite` |
| [Provenance des profils pivot : candidat_declare vs roster_groupe (2026-08-10)](decisions/provenance-pivot.md) | `_prefer_non_empty`, `merge_pivot_profile` |
| [Un préfixe de flux est valide, un préfixe de profil est faux (#460) (2026-08-20)](decisions/publication-dun-job-annule.md) | `merge_raw_profile` |
| [Un artifact = la contribution d'un job : ce qu'on publie décide de ce qu'on peut corriger (#450) (2026-08-19)](decisions/publication-scopee-artifacts.md) | `merge_raw_dirs` |
| [La qualification d'un scrutin se perdait entre la collecte et le profil brut (#639, rang 1) (2026-08-31)](decisions/qualification-perdue-a-la-fusion-639.md) | `CHAMPS_QUALIFICATION_VOTE`, `_pivot_vote_key`, `_vote_key`, `backfill_mandat_chambre`, `backfill_vote_qualification`, `merge_lists_by_key`, `merge_raw_profile` |
| [Un projet de loi porté au nom du Gouvernement n'est pas une production personnelle (#689) (2026-09-01)](decisions/qualification-textes-portes-689.md) | `_dossier_key`, `backfill_dossier_nature`, `backfill_mandat_chambre`, `backfill_vote_qualification`, `merge_raw_profile` |
| [Le `texte_vise` fautif se reprend depuis l'archive figée, pas par une fusion plus permissive (#696, 01/09/2026)](decisions/report-texte-vise-source-696.md) | `backfill_dossier_nature` |
| [Résilience de `generate-data.yml` face aux `shutdown signal` runner : continue-on-error généralisé, watchdog réseau, retry générique sur `_get_payload`, retry `retry-generate-data.yml` non-régressif, et appels NosDéputés morts pour les députés (dossiers, votes) (2026-08-16)](decisions/resilience-generate-data-shutdown-signal.md) | `merge_raw_dirs` |
| [Retrait de `fetch_activity_synthesis` (#356) (2026-08-16)](decisions/retrait-fetch-activity-synthesis.md) | `merge_raw_profile` |
| [NosDéputés sort du pipeline (#529, lot 5 de l'épic « une seule source AN ») (2026-08-27)](decisions/retrait-nosdeputes-529.md) | `merge_lists_by_key` |
| [Le Sénat sort du périmètre, et le job qui concluait vert sans rien produire est retiré (#528, lot 3 de l'épic « une seule source AN ») (2026-08-26)](decisions/retrait-senat-528.md) | `_merge_pivot_sources`, `merge_lists_by_key` |
| [Revue transversale des workflows GitHub Actions : ce qui est gardé, ce qui est corrigé (#342) (2026-08-18)](decisions/revue-workflows-ci-342.md) | `merge_pivot_profile` |
| [`synchro_sources` publie la dernière récupération réussie, et pas son origine (#600) (2026-08-30)](decisions/synchro-sources-derniere-recuperation-600.md) | `merge_raw_profile` |
| [Régénérer l'existant : `--refresh-existing`, l'inverse de `--skip-existing` (#445) (2026-08-19)](decisions/telechargement-an-trois-modes-defaillance.md) | `merge_raw_dirs` |
| [L'union des avertissements peut ressusciter un démenti, et deux familles Syceron s'éteignent (#600) (2026-08-30)](decisions/union-warnings-extinction-600.md) | `_defaut_collecte_dementi_par_les_donnees`, `merge_pivot_profile`, `merge_raw_profile` |
| [Vérification de bout en bout des législatures figées 15/16 (#273, clôture de l'epic #268) (2026-08-17)](decisions/verification-bout-en-bout-legislatures-figees.md) | `_amendement_key`, `_prune_stale_warnings` |
| [Votes : agrégation des législatures 14 à 17, index dédupliqué, 14/15/16 figées (#403) (2026-08-18)](decisions/votes-multi-legislature.md) | `merge_lists_by_key` |

Le mentionnent sans le gouverner : [`bascule-identite-an-primaire`](decisions/bascule-identite-an-primaire.md), [`deux-axes-formulaire-578`](decisions/deux-axes-formulaire-578.md), [`investigation-sources-ue`](decisions/investigation-sources-ue.md), [`profession-code-nomenclature-641`](decisions/profession-code-nomenclature-641.md), [`restauration-interventions`](decisions/restauration-interventions.md).

## `src/normalize_europarl.py`

Le mentionnent sans le gouverner : [`chambre-par-mandat-electif`](decisions/chambre-par-mandat-electif.md), [`chambres-profil-derivees`](decisions/chambres-profil-derivees.md), [`collecte-non-publiee`](decisions/collecte-non-publiee.md), [`consommateurs-chambres-migres`](decisions/consommateurs-chambres-migres.md), [`deux-chambres-interrogees`](decisions/deux-chambres-interrogees.md), [`id-pivot-sans-prefixe`](decisions/id-pivot-sans-prefixe.md), [`identite-profils-539`](decisions/identite-profils-539.md), [`licence-lot-6-530`](decisions/licence-lot-6-530.md), [`pivot-freshness-timestamps-stables`](decisions/pivot-freshness-timestamps-stables.md), [`provenance-par-champ-603`](decisions/provenance-par-champ-603.md), [`provenance-pivot`](decisions/provenance-pivot.md), [`retrait-nosdeputes-529`](decisions/retrait-nosdeputes-529.md).

## `src/normalize_parltrack_dumps.py`

3 décision(s) le gouvernent ; le module en cite 0.

| Décision | Nomme |
| --- | --- |
| [`meta.warnings[]` déclare son destinataire, dans un jumeau typé et aligné (#642) (2026-08-31)](decisions/destinataire-avertissements-642.md) | `WARNING_PREFIX_PARLTRACK_AUCUNE_DONNEE` |
| [L'`id` d'un profil pivot est le slug : le préfixe de provenance était instable (#487) (2026-08-20)](decisions/id-pivot-sans-prefixe.md) | `enrich_pivot_with_parltrack` |
| [Le versant AN passe en Licence Ouverte, et `meta.licence_donnees` devient un champ dérivé (#530, lot 6 de l'épic « une seule source AN ») (2026-08-27)](decisions/licence-lot-6-530.md) | `enrich_pivot_with_parltrack` |

Le mentionnent sans le gouverner : [`investigation-sources-ue`](decisions/investigation-sources-ue.md).

## `src/normalize_profil.py`

8 décision(s) le gouvernent ; le module en cite 4.

| Décision | Nomme |
| --- | --- |
| [Trois absences publiées comme des faits (#556, #558, #560) (2026-08-29)](decisions/absences-publiees-comme-faits-556-558-560.md) | `_uri_hatvp_publiable` |
| [Une URL de source n'est pas un identifiant : la clé de fusion des interventions (#540) (2026-08-27)](decisions/cle-fusion-interventions-540.md) | `_normalize_intervention` |
| [Une clé de fusion en `a or b` change d'identité quand `a` se remplit (#668) (2026-08-31)](decisions/cle-fusion-textes-portes-668.md) | `_normalize_texte_porte` |
| [Un filtre de publication posé avant la fusion ne filtre rien (#641, réouverture) (2026-08-31)](decisions/filtre-publication-apres-fusion-641.md) | `_profession_publiable` |
| [Normaliser les amendements : le coût n'est pas l'amendement, c'est sa liste de cosignataires (#431) (2026-08-19)](decisions/normalisation-amendements.md) | `_normalize_amendement` |
| [Un code de nomenclature n'est pas une profession, et « sans activité professionnelle » n'en est pas une (#641) (2026-08-31)](decisions/profession-code-nomenclature-641.md) | `_ACTEUR_REF_DANS_URL`, `_profession_publiable`, `_uri_hatvp_publiable` |
| [La qualification d'un scrutin et la clé de son dossier étaient lues puis jetées (#639, rangs 1 et 2)](decisions/qualification-scrutins-et-cle-dossier-639.md) | `_normalize_texte_porte` |
| [Restaurer 789 interventions sans revenir sur le reste du schéma (#460) (2026-08-19)](decisions/restauration-interventions.md) | `_normalize_intervention` |

Le mentionnent sans le gouverner : [`civilite-et-pcs-insee-659`](decisions/civilite-et-pcs-insee-659.md), [`collecte-interventions-reduite-au-theme-657`](decisions/collecte-interventions-reduite-au-theme-657.md), [`collecte-vs-publie-545`](decisions/collecte-vs-publie-545.md), [`corroboration-chambres-publiees-486`](decisions/corroboration-chambres-publiees-486.md), [`identite-profils-539`](decisions/identite-profils-539.md), [`licence-lot-6-530`](decisions/licence-lot-6-530.md), [`provenance-par-champ-603`](decisions/provenance-par-champ-603.md), [`qualification-perdue-a-la-fusion-639`](decisions/qualification-perdue-a-la-fusion-639.md), [`qualification-textes-portes-689`](decisions/qualification-textes-portes-689.md), [`retrait-nosdeputes-529`](decisions/retrait-nosdeputes-529.md).

## `src/parltrack_dumps.py`

Le mentionnent sans le gouverner : [`investigation-sources-ue`](decisions/investigation-sources-ue.md), [`mandats-officiels-an-369`](decisions/mandats-officiels-an-369.md).

## `src/parse_syceron.py`

2 décision(s) le gouvernent ; le module en cite 0.

| Décision | Nomme |
| --- | --- |
| [Syceron publie l'identifiant d'orateur NU, et n'a donc jamais rien indexé (#510) (2026-08-20)](decisions/syceron-acteur-ref-nu-510.md) | `_parse_interventions`, `_parse_orateur` |
| [Suite du 26/08/2026 : les trois archives vérifiées, les deux défauts de parseur corrigés](decisions/syceron-archives-verifiees-parseur-510.md) | `_parse_orateur` |

Le mentionnent sans le gouverner : [`cle-fusion-interventions-540`](decisions/cle-fusion-interventions-540.md), [`syceron`](decisions/syceron.md).

## `src/parti_profile.py`

Le mentionnent sans le gouverner : [`freshness-timestamps-groupes-gouvernements-partis`](decisions/freshness-timestamps-groupes-gouvernements-partis.md), [`mandat-electif-perdu-fausse-le-denominateur`](decisions/mandat-electif-perdu-fausse-le-denominateur.md), [`pivot-freshness-timestamps-stables`](decisions/pivot-freshness-timestamps-stables.md).

## `src/population_profils.py`

1 décision(s) le gouvernent ; le module en cite 2.

| Décision | Nomme |
| --- | --- |
| [Les deux populations de `pivot_data/profiles/` sont portées par les outils, pas par une consigne (#630, 2026-08-30)](decisions/populations-profils-portees-par-les-outils-630.md) | `Ventilation`, `ventiler_chemins` |

## `src/profil_brut.py`

3 décision(s) le gouvernent ; le module en cite 0.

| Décision | Nomme |
| --- | --- |
| [Un audit lit le corpus par projection, et son plafond de mémoire est dans un test (#628, 2026-08-30)](decisions/audit-599-projection-blocs-lus-628.md) | `charger_socle` |
| [Le seuil de blob sort du critère de sortie, et les profils bruts se partitionnent par législature (#580) (2026-08-29)](decisions/partition-profils-legislature-580.md) | `PartitionIllisible`, `charger_profil_brut`, `ecrire_profil_brut`, `partitionner`, `recomposer` |
| [Un shard d'extraction ne matérialise que son propre profil (#674) — 31/08/2026](decisions/sparse-checkout-extract-an-674.md) | `slugs_du_repertoire` |

Le mentionnent sans le gouverner : [`absences-publiees-comme-faits-556-558-560`](decisions/absences-publiees-comme-faits-556-558-560.md).

## `src/purge_mandats_dupliques.py`

1 décision(s) le gouvernent ; le module en cite 0.

| Décision | Nomme |
| --- | --- |
| [Purge des mandats hérités dupliqués : appariement prudent (#387) (2026-08-17)](decisions/purge-mandats-dupliques-prudence.md) | `_PREFIXES_NATURE` |

Le mentionnent sans le gouverner : [`collecte-vs-publie-545`](decisions/collecte-vs-publie-545.md), [`partition-profils-legislature-580`](decisions/partition-profils-legislature-580.md), [`point-de-sauvegarde-dans-les-profils-518`](decisions/point-de-sauvegarde-dans-les-profils-518.md).

## `src/schema_gouvernement.py`

9 décision(s) le gouvernent ; le module en cite 1.

| Décision | Nomme |
| --- | --- |
| [Les agrégats publiés entrent dans le contrôle de perte, et l'ordre de grandeur reste hors contrat (#649) (2026-08-31)](decisions/agregats-publies-controle-perte-649.md) | `KNOWN_STATUTS_TEXTE_GOUVERNEMENTAL`, `validate_profil_gouvernement` |
| [`gouvernement_profile.py` : rattachement des textes par `date_depot`, exclusion silencieuse des dossiers non classifiables (#211) (2026-08-14)](decisions/gouvernement-profile-rattachement.md) | `KNOWN_CHAMBRES_DEPOT_TEXTE`, `KNOWN_STATUTS_TEXTE_GOUVERNEMENTAL` |
| [`gouvernement_textes` : 3 `fam_code` manquants excluaient 42 % des textes ; `adopte_cmp` ajouté à la nomenclature (#397) (2026-08-18)](decisions/gouvernement-textes-fam-codes-manquants.md) | `KNOWN_STATUTS_TEXTE_GOUVERNEMENTAL`, `make_empty_comptages_statuts` |
| [Profils de gouvernement : le lien ministre → texte (#435) (2026-08-18)](decisions/gouvernement-textes-initiateurs.md) | `REQUIRED_TEXTE_KEYS`, `validate_profil_gouvernement` |
| [`gouvernement_textes.py` : filtre de statut par décision de séance, pas par `codeActe`/`fam_code` seul (#210) (2026-08-14)](decisions/gouvernement-textes-statut.md) | `validate_profil_gouvernement` |
| [`gouvernement_textes.py` : filtre de statut par décision de séance, pas par `codeActe`/`fam_code` seul (#210) (2026-08-14)](decisions/gouvernement-textes-statut-210-version-initiale.md) | `validate_profil_gouvernement` |
| [`KNOWN_STATUTS_TEXTE_GOUVERNEMENTAL` : ajout de `rejete_49_3` (#208, réouverte) (2026-08-14)](decisions/gouvernement-textes-statut-49-3-rejete.md) | `KNOWN_STATUTS_TEXTE_GOUVERNEMENTAL`, `validate_profil_gouvernement` |
| [La qualification d'un scrutin et la clé de son dossier étaient lues puis jetées (#639, rangs 1 et 2)](decisions/qualification-scrutins-et-cle-dossier-639.md) | `REQUIRED_TEXTE_KEYS` |
| [`check_quality_gate.py` : section gouvernements (§5), couverture ministérielle proxy par `portefeuille` (#212) (2026-08-14)](decisions/quality-gate-gouvernements.md) | `validate_profil_gouvernement` |

Le mentionnent sans le gouverner : [`deduplication-entrees-membres`](decisions/deduplication-entrees-membres.md), [`gouvernement-doc-cloture`](decisions/gouvernement-doc-cloture.md), [`gouvernement-premier-ministre-portefeuille`](decisions/gouvernement-premier-ministre-portefeuille.md), [`hors-perimetre`](decisions/hors-perimetre.md), [`pivot-freshness-timestamps-stables`](decisions/pivot-freshness-timestamps-stables.md), [`web-v3-ui`](decisions/web-v3-ui.md).

## `src/schema_groupe.py`

3 décision(s) le gouvernent ; le module en cite 0.

| Décision | Nomme |
| --- | --- |
| [Les agrégats publiés entrent dans le contrôle de perte, et l'ordre de grandeur reste hors contrat (#649) (2026-08-31)](decisions/agregats-publies-controle-perte-649.md) | `make_empty_amendements_stats` |
| [Tous les comptes d'une fiche de groupe se rapportent à une date, et elle est publiée (#653) (2026-08-31)](decisions/date-de-reference-des-comptes-de-groupe-653.md) | `validate_profil_groupe` |
| [La position politique d'un groupe est celle que l'Assemblée déclare, lue dans une table committée (#686) (2026-09-01)](decisions/position-politique-groupes-686.md) | `POSITIONS_POLITIQUES_GROUPE`, `resumer_position_politique` |

Le mentionnent sans le gouverner : [`audit-plages-temporelles`](decisions/audit-plages-temporelles.md), [`consommateurs-chambres-migres`](decisions/consommateurs-chambres-migres.md), [`dates-appartenance-groupe-653`](decisions/dates-appartenance-groupe-653.md), [`pivot-freshness-timestamps-stables`](decisions/pivot-freshness-timestamps-stables.md), [`plage-dates-groupes`](decisions/plage-dates-groupes.md).

## `src/schema_parti.py`

Le mentionnent sans le gouverner : [`pivot-freshness-timestamps-stables`](decisions/pivot-freshness-timestamps-stables.md).

## `src/schema_pivot.py`

32 décision(s) le gouvernent ; le module en cite 5.

| Décision | Nomme |
| --- | --- |
| [Trois absences publiées comme des faits (#556, #558, #560) (2026-08-29)](decisions/absences-publiees-comme-faits-556-558-560.md) | `validate_profil` |
| [`chambres` au niveau profil : une liste dérivée, et `chambre` qui n'en est plus que le premier élément (#493) (2026-08-20)](decisions/chambres-profil-derivees.md) | `ChambresDerivees`, `KNOWN_CHAMBRES`, `ORDRE_CHAMBRES`, `appliquer_chambres`, `deriver_chambres`, `validate_profil` |
| [La civilité et la nomenclature PCS de l'INSEE traversaient le pipeline sans y laisser de trace (#659) (2026-08-31)](decisions/civilite-et-pcs-insee-659.md) | `CHAMPS_IDENTITE_TEXTE_LIBRE`, `validate_profil` |
| [La collecte d'interventions des membres de roster est réduite au thème (#657) (2026-08-31)](decisions/collecte-interventions-reduite-au-theme-657.md) | `KNOWN_COLLECTES_INTERVENTION` |
| [Les consommateurs de `chambre` migrés vers `chambres`, et le garde-fou qui datera son retrait (#494) (2026-08-20)](decisions/consommateurs-chambres-migres.md) | `appliquer_chambres`, `deriver_chambres`, `lire_chambres` |
| [La corroboration porte sur les chambres publiées, pas sur la complétude des mandats — et la condition de retrait de `chambre` devient atteignable (#486) (2026-08-30)](decisions/corroboration-chambres-publiees-486.md) | `ChambresDerivees`, `ORDRE_CHAMBRES`, `deriver_chambres`, `lire_chambres` |
| [La couverture se remplace à la maille où #539 la publie, et un cas non tranchable se déclare (#602) (2026-08-30)](decisions/couverture-remplacee-par-liste-602.md) | `LISTES_COUVERTES`, `valider_couverture` |
| [Une exception n'est pas une preuve, et un défaut de notre code n'est pas une panne de l'Assemblée nationale (#562) (2026-08-28)](decisions/defaut-collecte-vs-panne-562.md) | `marqueur_defaut_code`, `validate_profil`, `valider_couverture` |
| [`meta.warnings[]` déclare son destinataire, dans un jumeau typé et aligné (#642) (2026-08-31)](decisions/destinataire-avertissements-642.md) | `KNOWN_SOURCE_TYPES`, `validate_profil`, `valider_avertissements` |
| [Un amendement retrouve son dossier, et la clé qu'on lui avait retirée (#639, rang 3)](decisions/dossier-des-amendements-639.md) | `validate_amendements_index` |
| [Un filtre de publication posé avant la fusion ne filtre rien (#641, réouverture) (2026-08-31)](decisions/filtre-publication-apres-fusion-641.md) | `CHAMPS_IDENTITE_TEXTE_LIBRE` |
| [Deferred / out-of-scope investigations](decisions/hors-perimetre.md) | `KNOWN_CATEGORIES` |
| [Comment naît l'identité d'un profil, et où vont les identifiants de source (#539) (2026-08-28)](decisions/identite-profils-539.md) | `KNOWN_SOURCE_TYPES`, `poser_identifiant`, `validate_profil` |
| [Rien ne vérifiait que les clés publiées résolvent : le contrôle d'invariance (#485) (2026-08-20)](decisions/integrite-referentielle-pivot.md) | `validate_profil` |
| [Données UE — investigation des sources (2026-08-04)](decisions/investigation-sources-ue.md) | `validate_profil` |
| [Trois lectures du corpus passent à la projection, et chacune a son plafond dans un test (#635, 2026-08-30)](decisions/lectures-pipeline-par-projection-635.md) | `lire_chambres` |
| [Normaliser les amendements : le coût n'est pas l'amendement, c'est sa liste de cosignataires (#431) (2026-08-19)](decisions/normalisation-amendements.md) | `validate_amendements_index`, `validate_profil` |
| [Normaliser les votes : une liste partagée, un mapping, et deux invariants devenus des jointures (#432) (2026-08-19)](decisions/normalisation-votes.md) | `validate_profil`, `validate_scrutins_index` |
| [`genere_le`/`synchro_le` des pivots ne doivent avancer que si le contenu change réellement (#343) (2026-08-16)](decisions/pivot-freshness-timestamps-stables.md) | `make_empty_profil` |
| [Les deux populations de `pivot_data/profiles/` sont portées par les outils, pas par une consigne (#630, 2026-08-30)](decisions/populations-profils-portees-par-les-outils-630.md) | `KNOWN_PROVENANCES` |
| [La position politique d'un groupe est celle que l'Assemblée déclare, lue dans une table committée (#686) (2026-09-01)](decisions/position-politique-groupes-686.md) | `POSITION_POLITIQUE_AN_VERS_PIVOT` |
| [Quelle source a rempli quel champ, et quand — un bloc à côté d'`identite` (#603) (2026-08-30)](decisions/provenance-par-champ-603.md) | `BLOCS_PROVENANCE_CHAMPS`, `valider_provenance_champs` |
| [Provenance des profils pivot : candidat_declare vs roster_groupe (2026-08-10)](decisions/provenance-pivot.md) | `KNOWN_PROVENANCES`, `validate_profil` |
| [La qualification d'un scrutin se perdait entre la collecte et le profil brut (#639, rang 1) (2026-08-31)](decisions/qualification-perdue-a-la-fusion-639.md) | `validate_scrutins_index` |
| [La qualification d'un scrutin et la clé de son dossier étaient lues puis jetées (#639, rangs 1 et 2)](decisions/qualification-scrutins-et-cle-dossier-639.md) | `KNOWN_TYPES_SCRUTIN`, `validate_scrutins_index` |
| [Un projet de loi porté au nom du Gouvernement n'est pas une production personnelle (#689) (2026-09-01)](decisions/qualification-textes-portes-689.md) | `KNOWN_ROLES_TEXTE`, `validate_profil` |
| [Rattacher une intervention ou un scrutin à son dossier : les deux volets restants sont écartés, mesure à l'appui (#639) (2026-09-01)](decisions/rattachement-au-dossier-interventions-et-scrutins-639.md) | `LISTES_COUVERTES` |
| [Restaurer 789 interventions sans revenir sur le reste du schéma (#460) (2026-08-19)](decisions/restauration-interventions.md) | `validate_profil` |
| [NosDéputés sort du pipeline (#529, lot 5 de l'épic « une seule source AN ») (2026-08-27)](decisions/retrait-nosdeputes-529.md) | `KNOWN_SOURCE_TYPES`, `validate_profil` |
| [Le Sénat sort du périmètre, et le job qui concluait vert sans rien produire est retiré (#528, lot 3 de l'épic « une seule source AN ») (2026-08-26)](decisions/retrait-senat-528.md) | `KNOWN_CHAMBRES`, `KNOWN_SOURCE_TYPES` |
| [Taxonomie des mandats : exploitation des `typeOrgane` AN non mappés (#382, option « mixte ») (2026-08-17)](decisions/taxonomie-mandats-typeorgane-an.md) | `KNOWN_CATEGORIES`, `validate_profil` |
| [La trame du profil candidat : l'institution est une colonne, jamais un chapitre (#328)](decisions/trame-profil-candidat-328.md) | `KNOWN_POSITIONS_HEMICYCLE`, `lire_chambres` |

Le mentionnent sans le gouverner : [`gouvernement-premier-ministre-portefeuille`](decisions/gouvernement-premier-ministre-portefeuille.md), [`retrait-fetch-activity-synthesis`](decisions/retrait-fetch-activity-synthesis.md), [`synchro-sources-derniere-recuperation-600`](decisions/synchro-sources-derniere-recuperation-600.md), [`verification-bout-en-bout-legislatures-figees`](decisions/verification-bout-en-bout-legislatures-figees.md).

## `src/scrutins_index.py`

3 décision(s) le gouvernent ; le module en cite 0.

| Décision | Nomme |
| --- | --- |
| [Le seuil de blob sort du critère de sortie, et les profils bruts se partitionnent par législature (#580) (2026-08-29)](decisions/partition-profils-legislature-580.md) | `iter_votes_du_repertoire` |
| [La qualification d'un scrutin se perdait entre la collecte et le profil brut (#639, rang 1) (2026-08-31)](decisions/qualification-perdue-a-la-fusion-639.md) | `_valeur_scrutin`, `merge_scrutins_index` |
| [La qualification d'un scrutin et la clé de son dossier étaient lues puis jetées (#639, rangs 1 et 2)](decisions/qualification-scrutins-et-cle-dossier-639.md) | `merge_scrutins_index` |

Le mentionnent sans le gouverner : [`normalisation-votes`](decisions/normalisation-votes.md), [`point-de-sauvegarde-dans-les-profils-518`](decisions/point-de-sauvegarde-dans-les-profils-518.md).

## `src/scrutins_legislature.py`

1 décision(s) le gouvernent ; le module en cite 0.

| Décision | Nomme |
| --- | --- |
| [Ce qu'une liste vide veut dire : les quatre états de couverture (#539) (2026-08-28)](decisions/couverture-listes-539.md) | `LEGISLATURES_AN` |

## `src/syceron_debates.py`

6 décision(s) le gouvernent ; le module en cite 3.

| Décision | Nomme |
| --- | --- |
| [Trois absences publiées comme des faits (#556, #558, #560) (2026-08-29)](decisions/absences-publiees-comme-faits-556-558-560.md) | `SYCERON_AVAILABLE_LEGISLATURES` |
| [La clé de cache AN porte la COMPLÉTUDE, et la sauvegarde devient explicite (#550) (2026-08-28)](decisions/cache-completude-interventions-550.md) | `SYCERON_AVAILABLE_LEGISLATURES` |
| [Ce qu'une liste vide veut dire : les quatre états de couverture (#539) (2026-08-28)](decisions/couverture-listes-539.md) | `SYCERON_AVAILABLE_LEGISLATURES` |
| [Mandats commission/groupe_amitie/extra_parlementaire sourcés depuis l'AN, fetch_identity NosDéputés rendu conditionnel (#369, complet), watchdog générique sur tous les téléchargements zip (#370, complet) (2026-08-17)](decisions/mandats-officiels-an-369.md) | `_download_syceron_zip` |
| [Syceron publie l'identifiant d'orateur NU, et n'a donc jamais rien indexé (#510) (2026-08-20)](decisions/syceron-acteur-ref-nu-510.md) | `SYCERON_AVAILABLE_LEGISLATURES` |
| [Suite du 26/08/2026 : les trois archives vérifiées, les deux défauts de parseur corrigés](decisions/syceron-archives-verifiees-parseur-510.md) | `SYCERON_AVAILABLE_LEGISLATURES` |

Le mentionnent sans le gouverner : [`plafond-roster-et-commit-518`](decisions/plafond-roster-et-commit-518.md), [`syceron`](decisions/syceron.md).

## `src/textes_dossiers_an.py`

Le mentionnent sans le gouverner : [`dossier-des-amendements-639`](decisions/dossier-des-amendements-639.md).

## `src/textes_vises_figes.py`

1 décision(s) le gouvernent ; le module en cite 0.

| Décision | Nomme |
| --- | --- |
| [Le `texte_vise` fautif se reprend depuis l'archive figée, pas par une fusion plus permissive (#696, 01/09/2026)](decisions/report-texte-vise-source-696.md) | `est_uid_texte`, `lire_textes_vises` |

## `src/verifier_archivage_swh.py`

1 décision(s) le gouvernent ; le module en cite 2.

| Décision | Nomme |
| --- | --- |
| [Un garde-fou qui bloquait sur ce que la coupure garde, et une procédure qui se saute (#575, #576) (2026-08-29)](decisions/perimetre-coupure-575.md) | `ORIGINE_PAR_DEFAUT` |

Le mentionnent sans le gouverner : [`donnees-versionnees-integrite`](decisions/donnees-versionnees-integrite.md), [`fenetre-recalibrage-551`](decisions/fenetre-recalibrage-551.md).
