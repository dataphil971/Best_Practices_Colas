"""BP-11 — Vérifier les types de données et la précision numérique.

Implémente l'algorithme documenté dans
Agent_BI/01_ALGORITHMES/11_DataTypesPrecision.md. Toute évolution de la
logique OK/KO/NA doit d'abord être répercutée dans ce document — ce fichier
ne doit jamais diverger silencieusement de sa spécification fonctionnelle.

Source de preuve utilisée : la **conversion Power Query** (§4 niveau 3, §12
`expectation_source = POWER_QUERY`), c'est-à-dire le type déclaré dans un
`Table.TransformColumnTypes`. Les niveaux 1 et 2 (`COMPANY_POLICY`,
`SOURCE_SCHEMA`) n'existent pas dans ce dépôt et ne sont donc jamais
consultés — sans conversion M résolue, la règle rend NA, jamais un verdict
fabriqué.

INTERDIT et non implémenté (§4, §6, §12) : déduire le type attendu d'un nom
ou d'un suffixe de colonne (`_AMOUNT`, `_YEAR`...). Ces indices ne peuvent
produire qu'un diagnostic, jamais un KO — aucune preuve de ce type n'étant
disponible ici, ils ne sont pas exploités du tout.
"""

from engine.context import AnalysisContext
from engine.models import Finding, RuleResult
from powerbi.m_lang import find_function_calls, parse_type_transform_list

RULE_ID = "BP-11"
RULE_NAME = "Vérifier les types de données et la précision numérique"

TYPE_TRANSFORM_FUNCTION = "Table.TransformColumnTypes"

# Périmètre de la règle (§3) : seules les colonnes NUMÉRIQUES du modèle sont
# évaluées ; les autres sont hors périmètre et ne font pas basculer le statut.
NUMERIC_TYPES = {"int64", "double", "decimal"}

# Correspondance type M -> type TMDL. Une valeur None signale un type M
# volontairement NON convertible (trop générique pour prouver une intention),
# qui doit donner NA plutôt qu'une comparaison hasardeuse.
M_TO_TMDL_TYPE = {
    "Int64.Type": "int64",
    "type number": "double",
    "Double.Type": "double",
    "Currency.Type": "decimal",
    "Decimal.Type": "decimal",
    "Percentage.Type": "double",
    "type text": "string",
    "Text.Type": "string",
    "type datetime": "dateTime",
    "type date": "dateTime",
    "type logical": "boolean",
    "type any": None,
    "type duration": None,
}


def _build_m_type_index(context: AnalysisContext) -> "dict[str, set[str]]":
    """Nom de colonne source -> ensemble des types M qui lui sont attribués.

    L'index couvre les partitions des tables ET les requêtes partagées de
    `expressions.tmdl` : les données d'une table transitent souvent par une
    expression amont où la conversion de type est réellement déclarée
    (confirmé sur AI_BAROMETER_BI-CDS.SemanticModel).

    Un ensemble de plusieurs types pour un même nom signale une ambiguïté
    (deux requêtes typent différemment une colonne homonyme) : le §4 exige
    une conversion « explicite et RÉSOLUE », donc ce cas donne NA.
    """
    index: "dict[str, set[str]]" = {}
    m_sources = [p.m_source for table in context.tables for p in table.partitions]
    m_sources += [expr.m_source for expr in context.expressions]

    for m_source in m_sources:
        for call in find_function_calls(m_source, TYPE_TRANSFORM_FUNCTION):
            if len(call.raw_arguments) < 2:
                continue
            for column_name, m_type in parse_type_transform_list(call.raw_arguments[1]):
                index.setdefault(column_name, set()).add(m_type)
    return index


def _evaluate_column(table, column, m_type_index) -> "tuple[Finding, bool]":
    """Retourne (constat, hors_perimetre). `hors_perimetre` = colonne non
    numérique (§11), qui ne doit jamais faire basculer le statut global."""
    object_name = f"{table.name}.{column.raw_name}"
    raw_type = column.get_property("dataType")
    actual = str(raw_type) if raw_type is not None else None

    evidence = {"table": table.name, "column": column.raw_name,
                "source_file": column.source_file, "actual_type": actual}

    if actual is None:
        # §9.5 : dataType absent ou illisible -> NA (et non hors périmètre :
        # on ne peut pas affirmer que la colonne n'est pas numérique).
        return Finding(
            rule_id=RULE_ID, object_type="column", object=object_name,
            expected="type modèle conforme à l'intention de type démontrée",
            actual=None, status="NA",
            reason="dataType absent ou illisible", evidence=evidence,
        ), False

    if actual not in NUMERIC_TYPES:
        return Finding(
            rule_id=RULE_ID, object_type="column", object=object_name,
            expected="colonne numérique", actual=actual, status="NA",
            reason="Colonne hors périmètre numérique", evidence=evidence,
        ), True

    # §5 : la conversion M porte sur le nom de la colonne SOURCE, qui peut
    # différer du nom de la colonne dans le modèle.
    source_column = column.get_property("sourceColumn")
    lookup_keys = []
    if source_column is not None:
        lookup_keys.append(str(source_column).strip().strip('"'))
    lookup_keys.append(column.name)

    candidates = None
    for key in lookup_keys:
        if key in m_type_index:
            candidates = m_type_index[key]
            break

    if not candidates:
        return Finding(
            rule_id=RULE_ID, object_type="column", object=object_name,
            expected="type modèle conforme à l'intention de type démontrée",
            actual=actual, status="NA",
            reason="Type métier attendu non démontrable (aucune conversion Power Query résolue)",
            evidence=evidence,
        ), False

    if len(candidates) > 1:
        return Finding(
            rule_id=RULE_ID, object_type="column", object=object_name,
            expected="type modèle conforme à l'intention de type démontrée",
            actual=actual, status="NA",
            reason="Conversions Power Query contradictoires pour ce nom de colonne",
            evidence={**evidence, "m_types": sorted(candidates)},
        ), False

    m_type = next(iter(candidates))
    expected = M_TO_TMDL_TYPE.get(m_type)
    evidence = {**evidence, "m_type": m_type, "expectation_source": "POWER_QUERY"}

    if expected is None:
        return Finding(
            rule_id=RULE_ID, object_type="column", object=object_name,
            expected="type modèle conforme à l'intention de type démontrée",
            actual=actual, status="NA",
            reason="Type Power Query non convertible vers le contrat TMDL",
            evidence=evidence,
        ), False

    if expected == actual:
        return Finding(
            rule_id=RULE_ID, object_type="column", object=object_name,
            expected=expected, actual=actual, status="OK", evidence=evidence,
        ), False

    return Finding(
        rule_id=RULE_ID, object_type="column", object=object_name,
        expected=expected, actual=actual, status="KO",
        reason="Type du modèle différent du type déclaré dans Power Query",
        evidence=evidence,
        location=column.locate("dataType", context_lines=1),
        explanation=(
            f"Power Query convertit cette colonne en `{m_type}` (soit `{expected}`), mais le "
            f"modèle la déclare en `{actual}`. Un écart entre les deux force une conversion "
            "au chargement et peut changer le résultat des calculs — un `double` là où un "
            "entier est attendu introduit des erreurs d'arrondi invisibles."
        ),
        remediation=(
            f"Aligner les deux : soit corriger `dataType: {actual}` en `dataType: {expected}` "
            f"(ligne {column.property_lines.get('dataType', '?')} de {column.source_file}), "
            f"soit corriger la conversion Power Query si c'est elle qui se trompe."
        ),
    ), False


def check(context: AnalysisContext) -> RuleResult:
    if not context.tables:
        return RuleResult(
            rule_id=RULE_ID,
            rule_name=RULE_NAME,
            execution_status="ERROR",
            rule_status="NA",
            summary={"reason": "Aucun fichier de table TMDL trouvé"},
        )

    m_type_index = _build_m_type_index(context)
    results = [
        _evaluate_column(table, column, m_type_index)
        for table in context.tables
        for column in table.columns
    ]
    findings = [f for f, _out_of_scope in results]
    evaluable = [f for f, out_of_scope in results if not out_of_scope]

    ko = [f for f in evaluable if f.status == "KO"]
    na = [f for f in evaluable if f.status == "NA"]

    if ko:
        rule_status = "KO"
    elif na:
        rule_status = "NA"
    elif evaluable:
        rule_status = "OK"
    else:
        rule_status = "NA"

    return RuleResult(
        rule_id=RULE_ID,
        rule_name=RULE_NAME,
        execution_status="SUCCESS" if not na else "PARTIAL",
        rule_status=rule_status,
        findings=findings,
        summary={
            "total_columns": len(findings),
            "numeric_columns": len(evaluable),
            "conforming_columns": len(evaluable) - len(ko) - len(na),
            "nonconforming_columns": len(ko),
            "na_columns": len(na),
            "ko_details": [f.to_dict() for f in ko],
        },
    )
