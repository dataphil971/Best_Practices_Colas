"""BP-15 — Maximiser le query folding vers la source.

Implémente l'algorithme documenté dans
Agent_BI/01_ALGORITHMES/15_QueryFolding.md. Toute évolution de la logique
OK/KO/NA doit d'abord être répercutée dans ce document — ce fichier ne doit
jamais diverger silencieusement de sa spécification fonctionnelle.

Portée réelle par rapport au pseudo-code de référence : aucune preuve
runtime (query plan, diagnostics d'exécution, `View Native Query`) n'est
disponible dans ce dépôt — seules les preuves STATIQUES du document sont
implémentées (§6 ruptures explicites, §5 Value.NativeQuery/EnableFolding,
§8 "aucune transformation"). Les branches qui dépendraient d'une preuve
runtime (§7) ne sont jamais atteintes ; c'est un choix honnête, pas un
oubli — le document lui-même les traite comme une amélioration optionnelle,
prioritaire sur l'heuristique statique quand elle existe.

La classification FOLDABLE / NON_FOLDABLE de la source racine (§4, comme
pour BP-04) n'est fournie par aucun contexte externe dans ce dépôt : elle
repose ici sur une liste de connecteurs Power Query dont le support du
folding (base de données vs fichier/API) est un fait technique documenté
par Microsoft, jamais une politique d'entreprise devinée. Un connecteur
absent de ces deux listes reste UNKNOWN, jamais présumé dans un sens ou
l'autre.
"""

import re

from engine.context import AnalysisContext
from engine.models import Finding, RuleResult, SourceLocation
from powerbi.m_lang import find_function_calls, parse_let_steps

RULE_ID = "BP-15"
RULE_NAME = "Maximiser le query folding vers la source"

# Connecteurs adossés à un moteur de requête capable de replier des
# transformations (SQL généré côté source). Liste non exhaustive : un
# connecteur absent reste UNKNOWN, jamais présumé FOLDABLE.
FOLDABLE_CONNECTORS = [
    "Sql.Database",
    "Sql.Databases",
    "Databricks.Catalogs",
    "Databricks.Query",
    "PostgreSQL.Database",
    "MySQL.Database",
    "Oracle.Database",
    "Snowflake.Databases",
    "AnalysisServices.Database",
    "AnalysisServices.Databases",
    "GoogleBigQuery.Database",
]

# Connecteurs fichier/API sans moteur de requête à répliquer : le folding
# n'a pas de sens pour eux (§4 du document — NOT_APPLICABLE).
NON_FOLDABLE_CONNECTORS = [
    "Csv.Document",
    "Excel.Workbook",
    "Json.Document",
    "Xml.Document",
    "Folder.Files",
    "Folder.Contents",
    "SharePoint.Files",
    "SharePoint.Contents",
    "SharePoint.Tables",
    "Web.Contents",
    "Text.Document",
    "Parquet.Document",
]

FOLD_BREAKING_FUNCTIONS = ("Table.StopFolding", "Table.Buffer")

_ENABLE_FOLDING_TRUE = re.compile(r"EnableFolding\s*=\s*true", re.IGNORECASE)


def _classify_root_source(first_step_expression: str) -> str:
    for name in FOLDABLE_CONNECTORS:
        if find_function_calls(first_step_expression, name):
            return "FOLDABLE"
    for name in NON_FOLDABLE_CONNECTORS:
        if find_function_calls(first_step_expression, name):
            return "NON_FOLDABLE"
    return "UNKNOWN"


def _find_explicit_break(steps):
    for index, step in enumerate(steps):
        for fn in FOLD_BREAKING_FUNCTIONS:
            if find_function_calls(step.expression, fn):
                later = steps[index + 1 :]
                if later:
                    return {
                        "step": step.name,
                        "function": fn,
                        "subsequent_steps": [s.name for s in later],
                        "line_offset": step.line_offset,
                    }
    return None


def _find_native_query(steps):
    for index, step in enumerate(steps):
        calls = find_function_calls(step.expression, "Value.NativeQuery")
        if calls:
            return index, calls[0]
    return None, None


def _evaluate_query(
    object_type: str,
    object_name: str,
    m_source: "str | None",
    source_file: str,
    m_source_line: "int | None" = None,
    source_kind: "str | None" = None,
) -> "tuple[Finding, bool]":
    """Retourne (constat, hors_perimetre) — `hors_perimetre` = source connue
    non repliable (NOT_APPLICABLE, §4/§11 du document), qui ne doit jamais
    faire basculer le statut global.

    Générique sur la NATURE de la requête (partition de table, ou requête
    partagée de `definition/expressions.tmdl`) : le folding ne dépend que du
    code M lui-même, jamais du fait que la requête soit directement chargée
    dans une table ou seulement référencée par une autre requête.
    """
    # Une partition dont la source n'est pas du Power Query (`= calculated`
    # pour une table DAX, `= entity` pour un flux de données) ne peut pas
    # replier de requête : il n'y a pas de source à interroger. Elle est HORS
    # PÉRIMÈTRE, pas indéterminable — la classer NA laisserait croire qu'un
    # contrôle a échoué faute d'information, alors qu'il n'y avait rien à
    # contrôler. Sur un modèle réel (Cockpit), 42 partitions sur 92 sont dans
    # ce cas : les compter en NA suffisait à rendre la règle entière NA.
    if source_kind is not None and source_kind != "m":
        return Finding(
            rule_id=RULE_ID,
            object_type=object_type,
            object=object_name,
            expected="folding maximisé",
            actual=source_kind,
            status="NA",
            reason=f"Source `{source_kind}` : pas de requête Power Query à replier",
        ), True

    if not m_source:
        return Finding(
            rule_id=RULE_ID,
            object_type=object_type,
            object=object_name,
            expected="folding maximisé",
            actual=None,
            status="NA",
            reason="Code M absent ou illisible",
        ), False

    steps = parse_let_steps(m_source)
    if not steps:
        return Finding(
            rule_id=RULE_ID,
            object_type=object_type,
            object=object_name,
            expected="folding maximisé",
            actual=None,
            status="NA",
            reason="Code M non interprétable (aucune étape identifiée)",
        ), False

    root_capability = _classify_root_source(steps[0].expression)
    evidence_base = {"source_file": source_file, "root_capability": root_capability}

    if root_capability == "NON_FOLDABLE":
        return Finding(
            rule_id=RULE_ID,
            object_type=object_type,
            object=object_name,
            expected="folding maximisé",
            actual="NON_FOLDABLE",
            status="NA",
            reason="Source non repliable : le folding n'a pas de sens pour ce connecteur",
            evidence=evidence_base,
        ), True

    explicit_break = _find_explicit_break(steps)
    if explicit_break is not None:
        step_line = m_source_line + explicit_break["line_offset"] if m_source_line is not None else None
        downstream = ", ".join(explicit_break["subsequent_steps"])
        return Finding(
            rule_id=RULE_ID,
            object_type=object_type,
            object=object_name,
            expected="aucune rupture de folding avant la fin de la requête",
            actual=explicit_break["function"],
            status="KO",
            reason="Rupture explicite du folding avant des étapes ultérieures",
            evidence={**evidence_base, **explicit_break},
            location=SourceLocation.from_file(source_file, step_line, context_lines=1),
            explanation=(
                f"L'étape « {explicit_break['step']} » appelle `{explicit_break['function']}`, "
                "qui matérialise la table en mémoire. Toutes les étapes situées APRÈS "
                f"({downstream}) ne peuvent donc plus être traduites en requête envoyée à la "
                "source : elles s'exécutent localement, sur la totalité des lignes déjà "
                "chargées. C'est souvent la cause principale d'un rafraîchissement lent."
            ),
            remediation=(
                f"Déplacer `{explicit_break['function']}` à la FIN de la requête "
                f"(après {downstream}), ou le supprimer s'il n'est pas nécessaire"
                + (
                    f" — étape « {explicit_break['step']} », ligne {step_line} de {source_file}."
                    if step_line
                    else "."
                )
            ),
        ), False

    native_index, native_call = _find_native_query(steps)
    if native_call is not None:
        later_steps = steps[native_index + 1 :]

        if not later_steps:
            return Finding(
                rule_id=RULE_ID,
                object_type=object_type,
                object=object_name,
                expected="folding maximisé",
                actual="Value.NativeQuery",
                status="OK",
                reason="Aucune étape ultérieure à replier après Value.NativeQuery",
                evidence=evidence_base,
            ), False

        if root_capability != "FOLDABLE":
            return Finding(
                rule_id=RULE_ID,
                object_type=object_type,
                object=object_name,
                expected="folding maximisé",
                actual=None,
                status="NA",
                reason="Capacité de folding sur requête native non démontrée pour ce connecteur",
                evidence=evidence_base,
            ), False

        enable_arg = native_call.raw_arguments[3] if len(native_call.raw_arguments) > 3 else ""
        if not _ENABLE_FOLDING_TRUE.search(enable_arg):
            return Finding(
                rule_id=RULE_ID,
                object_type=object_type,
                object=object_name,
                expected="EnableFolding=true",
                actual=enable_arg or None,
                status="KO",
                reason="Étapes après Value.NativeQuery sans EnableFolding=true",
                evidence={**evidence_base, "subsequent_steps": [s.name for s in later_steps]},
            ), False

        return Finding(
            rule_id=RULE_ID,
            object_type=object_type,
            object=object_name,
            expected="folding réel observé",
            actual="EnableFolding=true",
            status="NA",
            reason="EnableFolding activé mais folding réel des étapes suivantes non observable statiquement",
            evidence=evidence_base,
        ), False

    if root_capability != "FOLDABLE":
        return Finding(
            rule_id=RULE_ID,
            object_type=object_type,
            object=object_name,
            expected="folding maximisé",
            actual=None,
            status="NA",
            reason="Capacité de folding de la source non déterminée",
            evidence=evidence_base,
        ), False

    if len(steps) == 1:
        return Finding(
            rule_id=RULE_ID,
            object_type=object_type,
            object=object_name,
            expected="folding maximisé",
            actual="aucune transformation",
            status="OK",
            reason="Aucune transformation après la navigation source",
            evidence=evidence_base,
        ), False

    return Finding(
        rule_id=RULE_ID,
        object_type=object_type,
        object=object_name,
        expected="folding maximisé",
        actual=None,
        status="NA",
        reason="Folding réel non démontré statiquement",
        evidence={**evidence_base, "steps": [s.name for s in steps]},
    ), False


def check(context: AnalysisContext) -> RuleResult:
    # Une requête soumise au folding n'est pas forcément une partition
    # directement chargée : `D_STRUCTURES` (requête partagée de
    # expressions.tmdl, référencée par une autre requête) porte elle-même un
    # `Value.NativeQuery` — invisible pour cette règle tant que les
    # expressions partagées ne sont pas évaluées au même titre que les
    # partitions (bug réel trouvé sur AI_BAROMETER_BI-CDS.SemanticModel,
    # 2026-08-19).
    results = [
        _evaluate_query(
            "partition",
            f"{table.name}/{partition.name}",
            partition.m_source,
            partition.source_file,
            partition.m_source_line,
            partition.source_kind,
        )
        for table in context.tables
        for partition in table.partitions
    ] + [
        _evaluate_query(
            "expression",
            expr.name,
            expr.m_source,
            expr.source_file,
            expr.m_source_line,
        )
        for expr in context.expressions
    ]
    findings = [f for f, _out_of_scope in results]
    evaluable = [f for f, out_of_scope in results if not out_of_scope]

    if any(f.status == "KO" for f in evaluable):
        rule_status = "KO"
    elif any(f.status == "NA" for f in evaluable):
        rule_status = "NA"
    elif evaluable:
        rule_status = "OK"
    else:
        rule_status = "NA"

    return RuleResult(
        rule_id=RULE_ID,
        rule_name=RULE_NAME,
        execution_status="SUCCESS",
        rule_status=rule_status,
        findings=findings,
        summary={
            "total_partitions": len(findings),
            "evaluated_partitions": len(evaluable),
            "ko_details": [f.to_dict() for f in evaluable if f.status == "KO"],
        },
    )
