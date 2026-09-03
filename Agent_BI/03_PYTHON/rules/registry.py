"""Catalogue des bonnes pratiques Agent BI et registre des règles exécutables.

Ce module est la **source de vérité unique** de l'état d'avancement du moteur :
il liste les 37 bonnes pratiques spécifiées dans `Agent_BI/01_ALGORITHMES/` et,
pour chacune, si elle est réellement implémentée (`IMPLEMENTED`) ou seulement
spécifiée (`PLANNED`).

Le nom et l'alias d'une règle implémentée sont lus **depuis son module**
(`bp_NN.RULE_NAME`), jamais recopiés ici : une seule écriture, donc aucun
risque que le catalogue affiche un libellé différent de celui du résultat
d'analyse.

Une règle `PLANNED` n'est pas « désactivée » au sens métier : elle n'existe
simplement pas encore côté Python (cf. « Cycle de vie d'une bonne pratique »
dans `Agent_BI/README_Agent_BI.md`). Elle n'est donc jamais exécutée et
n'apparaît jamais dans les résultats d'une analyse — ne jamais la faire
apparaître avec un statut `NA`, ce qui laisserait croire qu'un contrôle a été
tenté.

La cohérence entre ce catalogue et les fichiers `01_ALGORITHMES/*.md` est
vérifiée par `03_PYTHON/tests/test_registry.py` : ajouter un algorithme sans
l'inscrire ici fait échouer la suite de tests.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from types import ModuleType

from core import ImplementationStatus, RuleScope
from engine.runner import Rule
from errors import UnknownRuleError
from rules import (
    bp_01,
    bp_03,
    bp_07,
    bp_09,
    bp_10,
    bp_11,
    bp_15,
    bp_17,
    bp_21,
    bp_22,
    bp_25,
    bp_32,
    bp_37,
    bp_38,
    bp_39,
    bp_41,
)


@dataclass(frozen=True)
class RuleSpec:
    """Fiche d'identité d'une bonne pratique, implémentée ou non."""

    rule_id: str
    name: str
    scope: RuleScope
    algorithm: str
    implementation: ImplementationStatus
    alias: str | None = None
    check: Rule | None = None

    @property
    def is_implemented(self) -> bool:
        """Vrai si la règle est exécutable par le moteur."""
        return self.implementation == "IMPLEMENTED"


def _implemented(module: ModuleType, scope: RuleScope, algorithm: str) -> RuleSpec:
    """Déclare une bonne pratique implémentée, d'après les constantes de son module."""
    return RuleSpec(
        rule_id=module.RULE_ID,
        name=module.RULE_NAME,
        scope=scope,
        algorithm=algorithm,
        implementation="IMPLEMENTED",
        alias=getattr(module, "RULE_ALIAS", None),
        check=module.check,
    )


def _planned(
    rule_id: str,
    name: str,
    scope: RuleScope,
    algorithm: str,
    alias: str | None = None,
) -> RuleSpec:
    """Déclare une bonne pratique spécifiée mais pas encore implémentée."""
    return RuleSpec(
        rule_id=rule_id,
        name=name,
        scope=scope,
        algorithm=algorithm,
        implementation="PLANNED",
        alias=alias,
    )


CATALOGUE: tuple[RuleSpec, ...] = (
    _implemented(bp_01, "SEMANTIC_MODEL", "01_Relations.md"),
    _planned(
        "BP-02",
        "Table de dates dédiée et correctement configurée",
        "SEMANTIC_MODEL",
        "02_DateTable.md",
    ),
    _implemented(bp_03, "SEMANTIC_MODEL", "03_AvoidBidirectional.md"),
    _planned(
        "BP-04",
        "Pousser les transformations en amont",
        "SEMANTIC_MODEL",
        "04_PushTransformUpstream.md",
        alias="SEM-003",
    ),
    _implemented(bp_07, "CROSS", "07_RemoveUnusedFields.md"),
    _planned(
        "BP-08",
        "Filtrer tôt le volume de données en phase de développement",
        "SEMANTIC_MODEL",
        "08_EarlyDevFilter.md",
    ),
    _implemented(bp_09, "SEMANTIC_MODEL", "09_DisableAutoDateTime.md"),
    _implemented(bp_10, "SEMANTIC_MODEL", "10_SurrogateKeys.md"),
    _implemented(bp_11, "SEMANTIC_MODEL", "11_DataTypesPrecision.md"),
    _planned(
        "BP-12",
        "Paramétrer les valeurs littérales répétées dans Power Query",
        "SEMANTIC_MODEL",
        "12_ParametrizeRepeatedValues.md",
    ),
    _planned(
        "BP-13",
        "Positionner les merges/appends après les réductions de volume",
        "SEMANTIC_MODEL",
        "13_AvoidEarlyMergesAppends.md",
    ),
    _planned(
        "BP-14",
        "Désactiver le chargement des requêtes strictement intermédiaires",
        "CROSS",
        "14_DisableLoadIntermediate.md",
    ),
    _implemented(bp_15, "SEMANTIC_MODEL", "15_QueryFolding.md"),
    _planned(
        "BP-16",
        "Actualisation incrémentielle des tables volumineuses éligibles",
        "SEMANTIC_MODEL",
        "16_IncrementalRefresh.md",
    ),
    _implemented(bp_17, "SEMANTIC_MODEL", "17_DatabricksEndpoint.md"),
    _planned(
        "BP-18",
        "Éviter les slicers à cardinalité excessive",
        "CROSS",
        "18_ReduceCardinality.md",
    ),
    _planned(
        "BP-19",
        "Documenter les tables et mesures des modèles réutilisables",
        "SEMANTIC_MODEL",
        "19_FillDescriptionsForBuildDatasets.md",
    ),
    _planned(
        "BP-20",
        "Intégrité référentielle des relations",
        "SEMANTIC_MODEL",
        "20_ReferentialIntegrity.md",
    ),
    _implemented(bp_21, "SEMANTIC_MODEL", "21_ConciseNames.md"),
    _implemented(bp_22, "SEMANTIC_MODEL", "22_DisableSummarization.md"),
    _planned(
        "BP-24",
        "Centraliser les mesures dans une ou plusieurs tables dédiées",
        "SEMANTIC_MODEL",
        "24_GroupMeasures.md",
    ),
    _implemented(bp_25, "CROSS", "25_HideTechnicalFields.md"),
    _planned(
        "BP-26",
        "Documenter les champs dont l'ambiguïté est démontrée",
        "SEMANTIC_MODEL",
        "26_AddFieldDescriptions.md",
    ),
    _planned(
        "BP-28",
        "Détecter les mesures potentiellement redondantes",
        "SEMANTIC_MODEL",
        "28_KeepOnlyNecessaryMeasures.md",
    ),
    _planned("BP-30", "Formatage standardisé du code DAX", "SEMANTIC_MODEL", "30_FormatDAX.md"),
    _implemented(bp_32, "REPORT", "32_ExplicitMeasures.md"),
    _planned(
        "BP-33",
        "Utiliser des variables DAX selon une règle de complexité explicite",
        "SEMANTIC_MODEL",
        "33_DAXVariables.md",
    ),
    _planned(
        "BP-34",
        "Identifier les opportunités de Calculation Groups",
        "SEMANTIC_MODEL",
        "34_CalculationGroups.md",
    ),
    _planned(
        "BP-35",
        "Commentaires utiles dans le code complexe",
        "SEMANTIC_MODEL",
        "35_CommentsInCode.md",
    ),
    _implemented(bp_37, "REPORT", "37_OrganizeVisualsBookmarks.md"),
    _implemented(bp_38, "REPORT", "38_EliminateVisualInteractions.md"),
    _implemented(bp_39, "CROSS", "39_ConfigAndTestFilters.md"),
    _planned("BP-40", "Synchronisation des slicers entre pages", "REPORT", "40_SyncSlicers.md"),
    _implemented(bp_41, "REPORT", "41_RemoveRedundantVisuals.md"),
    _planned(
        "BP-42",
        "Application différée des slicers lorsque nécessaire",
        "REPORT",
        "42_ApplyButtonForSlicers.md",
    ),
    _planned(
        "BP-43",
        "Configurer les en-têtes de visuels selon le besoin utilisateur",
        "REPORT",
        "43_DisableVisualHeaders.md",
    ),
    _planned(
        "BP-44",
        "Bandeau de notification piloté par configuration",
        "CROSS",
        "44_AddNotificationBanner.md",
    ),
)


def implemented_specs() -> list[RuleSpec]:
    """Fiches des règles réellement exécutables, dans l'ordre du catalogue."""
    return [spec for spec in CATALOGUE if spec.is_implemented]


def planned_specs() -> list[RuleSpec]:
    """Fiches des bonnes pratiques spécifiées mais pas encore implémentées."""
    return [spec for spec in CATALOGUE if not spec.is_implemented]


def get_spec(rule_id: str) -> RuleSpec:
    """Retourne la fiche d'une bonne pratique par son identifiant `BP-NN`.

    Raises:
        UnknownRuleError: si l'identifiant n'existe pas dans le catalogue.

    """
    normalized = rule_id.strip().upper()
    for spec in CATALOGUE:
        if spec.rule_id == normalized or (spec.alias and spec.alias.upper() == normalized):
            return spec
    raise UnknownRuleError(f"Bonne pratique inconnue : {rule_id}")


def resolve_rules(rule_ids: Sequence[str] | None = None) -> list[Rule]:
    """Résout une sélection d'identifiants en fonctions de contrôle exécutables.

    Args:
        rule_ids: identifiants `BP-NN` (ou alias hérité). `None` retourne
            toutes les règles implémentées.

    Returns:
        Les fonctions de contrôle, dans l'ordre du catalogue.

    Raises:
        UnknownRuleError: si un identifiant est inconnu, ou s'il désigne une
            bonne pratique pas encore implémentée. Demander explicitement une
            règle `PLANNED` est une erreur d'appel : la passer sous silence
            produirait un rapport « tout va bien » sans qu'aucun contrôle
            n'ait été exécuté.

    """
    if rule_ids is None:
        return [spec.check for spec in implemented_specs() if spec.check is not None]

    selected: list[Rule] = []
    for rule_id in rule_ids:
        spec = get_spec(rule_id)
        if spec.check is None:
            raise UnknownRuleError(
                f"La bonne pratique {spec.rule_id} est spécifiée mais pas encore implémentée "
                f"(algorithme : {spec.algorithm})"
            )
        selected.append(spec.check)
    return selected
