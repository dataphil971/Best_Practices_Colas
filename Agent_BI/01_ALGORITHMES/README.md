# Algorithmes des bonnes pratiques

Définition **fonctionnelle** des bonnes pratiques contrôlées par Agent BI.
Un algorithme décrit *ce qui* doit être contrôlé, indépendamment de Python.

**16 implémentée(s) sur 37.**

> Un algorithme peut exister sans implémentation : c'est une étape normale du
> cycle de vie d'une bonne pratique, pas une anomalie. Une règle ⏳ n'est pas
> « désactivée » — elle n'existe simplement pas encore côté moteur, et
> n'apparaît donc jamais dans un résultat d'analyse.

Ce tableau est généré depuis le catalogue
[`03_PYTHON/rules/registry.py`](../03_PYTHON/rules/registry.py),
source de vérité unique.

| Statut | Règle | Bonne pratique | Périmètre | Algorithme |
|:---:|---|---|---|---|
| ✅ | `BP-01` | Intégrité structurelle du graphe relationnel | Modèle sémantique | [`01_Relations.md`](01_Relations.md) |
| ⏳ | `BP-02` | Table de dates dédiée et correctement configurée | Modèle sémantique | [`02_DateTable.md`](02_DateTable.md) |
| ✅ | `BP-03` | Éviter les relations bidirectionnelles et many-to-many | Modèle sémantique | [`03_AvoidBidirectional.md`](03_AvoidBidirectional.md) |
| ⏳ | `BP-04`<br>_SEM-003_ | Pousser les transformations en amont | Modèle sémantique | [`04_PushTransformUpstream.md`](04_PushTransformUpstream.md) |
| ✅ | `BP-07` | Éliminer les colonnes visibles et inutilisées du modèle | Modèle + Rapport | [`07_RemoveUnusedFields.md`](07_RemoveUnusedFields.md) |
| ⏳ | `BP-08` | Filtrer tôt le volume de données en phase de développement | Modèle sémantique | [`08_EarlyDevFilter.md`](08_EarlyDevFilter.md) |
| ✅ | `BP-09` | Désactiver l'option Auto Date/Time | Modèle sémantique | [`09_DisableAutoDateTime.md`](09_DisableAutoDateTime.md) |
| ✅ | `BP-10` | Utiliser des clés de relation entières | Modèle sémantique | [`10_SurrogateKeys.md`](10_SurrogateKeys.md) |
| ✅ | `BP-11` | Vérifier les types de données et la précision numérique | Modèle sémantique | [`11_DataTypesPrecision.md`](11_DataTypesPrecision.md) |
| ⏳ | `BP-12` | Paramétrer les valeurs littérales répétées dans Power Query | Modèle sémantique | [`12_ParametrizeRepeatedValues.md`](12_ParametrizeRepeatedValues.md) |
| ⏳ | `BP-13` | Positionner les merges/appends après les réductions de volume | Modèle sémantique | [`13_AvoidEarlyMergesAppends.md`](13_AvoidEarlyMergesAppends.md) |
| ⏳ | `BP-14` | Désactiver le chargement des requêtes strictement intermédiaires | Modèle + Rapport | [`14_DisableLoadIntermediate.md`](14_DisableLoadIntermediate.md) |
| ✅ | `BP-15` | Maximiser le query folding vers la source | Modèle sémantique | [`15_QueryFolding.md`](15_QueryFolding.md) |
| ⏳ | `BP-16` | Actualisation incrémentielle des tables volumineuses éligibles | Modèle sémantique | [`16_IncrementalRefresh.md`](16_IncrementalRefresh.md) |
| ✅ | `BP-17` | Utiliser un SQL Warehouse pour Databricks en DirectQuery | Modèle sémantique | [`17_DatabricksEndpoint.md`](17_DatabricksEndpoint.md) |
| ⏳ | `BP-18` | Éviter les slicers à cardinalité excessive | Modèle + Rapport | [`18_ReduceCardinality.md`](18_ReduceCardinality.md) |
| ⏳ | `BP-19` | Documenter les tables et mesures des modèles réutilisables | Modèle sémantique | [`19_FillDescriptionsForBuildDatasets.md`](19_FillDescriptionsForBuildDatasets.md) |
| ⏳ | `BP-20` | Intégrité référentielle des relations | Modèle sémantique | [`20_ReferentialIntegrity.md`](20_ReferentialIntegrity.md) |
| ✅ | `BP-21` | Noms d'objets concis, cohérents et conformes à la convention du modèle | Modèle sémantique | [`21_ConciseNames.md`](21_ConciseNames.md) |
| ✅ | `BP-22`<br>_SEM-001_ | Désactivation de l'autosummarization | Modèle sémantique | [`22_DisableSummarization.md`](22_DisableSummarization.md) |
| ⏳ | `BP-24` | Centraliser les mesures dans une ou plusieurs tables dédiées | Modèle sémantique | [`24_GroupMeasures.md`](24_GroupMeasures.md) |
| ✅ | `BP-25` | Masquer les champs techniques démontrés | Modèle + Rapport | [`25_HideTechnicalFields.md`](25_HideTechnicalFields.md) |
| ⏳ | `BP-26` | Documenter les champs dont l'ambiguïté est démontrée | Modèle sémantique | [`26_AddFieldDescriptions.md`](26_AddFieldDescriptions.md) |
| ⏳ | `BP-28` | Détecter les mesures potentiellement redondantes | Modèle sémantique | [`28_KeepOnlyNecessaryMeasures.md`](28_KeepOnlyNecessaryMeasures.md) |
| ⏳ | `BP-30` | Formatage standardisé du code DAX | Modèle sémantique | [`30_FormatDAX.md`](30_FormatDAX.md) |
| ✅ | `BP-32` | Utiliser des mesures explicites plutôt que des agrégations implicites | Rapport | [`32_ExplicitMeasures.md`](32_ExplicitMeasures.md) |
| ⏳ | `BP-33` | Utiliser des variables DAX selon une règle de complexité explicite | Modèle sémantique | [`33_DAXVariables.md`](33_DAXVariables.md) |
| ⏳ | `BP-34` | Identifier les opportunités de Calculation Groups | Modèle sémantique | [`34_CalculationGroups.md`](34_CalculationGroups.md) |
| ⏳ | `BP-35` | Commentaires utiles dans le code complexe | Modèle sémantique | [`35_CommentsInCode.md`](35_CommentsInCode.md) |
| ✅ | `BP-37` | Organiser les visuels et les signets | Rapport | [`37_OrganizeVisualsBookmarks.md`](37_OrganizeVisualsBookmarks.md) |
| ✅ | `BP-38` | Éliminer les interactions croisées inutiles | Rapport | [`38_EliminateVisualInteractions.md`](38_EliminateVisualInteractions.md) |
| ✅ | `BP-39` | Configurer et tester les filtres du rapport | Modèle + Rapport | [`39_ConfigAndTestFilters.md`](39_ConfigAndTestFilters.md) |
| ⏳ | `BP-40` | Synchronisation des slicers entre pages | Rapport | [`40_SyncSlicers.md`](40_SyncSlicers.md) |
| ✅ | `BP-41` | Détection des visuels redondants ou dupliqués | Rapport | [`41_RemoveRedundantVisuals.md`](41_RemoveRedundantVisuals.md) |
| ⏳ | `BP-42` | Application différée des slicers lorsque nécessaire | Rapport | [`42_ApplyButtonForSlicers.md`](42_ApplyButtonForSlicers.md) |
| ⏳ | `BP-43` | Configurer les en-têtes de visuels selon le besoin utilisateur | Rapport | [`43_DisableVisualHeaders.md`](43_DisableVisualHeaders.md) |
| ⏳ | `BP-44` | Bandeau de notification piloté par configuration | Modèle + Rapport | [`44_AddNotificationBanner.md`](44_AddNotificationBanner.md) |

## Légende

| Icône | Signification |
|:---:|---|
| ✅ | Implémentée, testée et exécutée par le moteur |
| ⏳ | Spécifiée uniquement — aucun code, aucun contrôle |

## Ajouter une bonne pratique

La marche à suivre complète est décrite dans
[`../README_Agent_BI.md`](../README_Agent_BI.md#cycle-de-vie-dune-bonne-pratique).

La numérotation peut comporter des trous (règles pas encore rédigées) :
ce n'est pas une anomalie.
