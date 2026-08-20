"""BP-22 (alias SEM-001) — Désactivation de l'autosummarization des colonnes.

Implémente l'algorithme documenté dans
Agent_BI/01_ALGORITHMES/22_DisableSummarization.md. Toute évolution de la
logique OK/KO/NA doit d'abord être répercutée dans ce document (cf.
`agent-bi-rule-review` dans .github/skills/) — ce fichier ne doit jamais
diverger silencieusement de sa spécification fonctionnelle.
"""

from engine.context import AnalysisContext
from engine.models import Finding, RuleResult

RULE_ID = "BP-22"
RULE_ALIAS = "SEM-001"
RULE_NAME = "Désactivation de l'autosummarization"

CONFORMING_VALUE = "none"

# Valeurs connues de summarizeBy autres que "none" (§4 de l'algorithme).
# Une valeur absente de cet ensemble et différente de "none" est traitée
# comme illisible/inconnue -> NA, jamais comme un KO implicite.
KNOWN_NONCONFORMING_VALUES = {
    "sum", "average", "count", "distinctcount", "min", "max", "default",
}


def check(context: AnalysisContext) -> RuleResult:
    if not context.tables:
        return RuleResult(
            rule_id=RULE_ID,
            alias=RULE_ALIAS,
            rule_name=RULE_NAME,
            execution_status="ERROR",
            rule_status="NA",
            summary={"reason": "Aucun fichier de table TMDL trouvé"},
        )

    findings = []
    ko_details = []
    na_details = []
    total_columns = 0
    conforming = 0

    for table in context.tables:
        for column in table.columns:
            total_columns += 1
            raw_value = column.get_property("summarizeBy")
            object_name = f"{table.name}.{column.raw_name}"
            evidence = {
                "table": table.name,
                "column": column.raw_name,
                "source_file": column.source_file,
            }

            if raw_value is None:
                findings.append(Finding(
                    rule_id=RULE_ID, object_type="column", object=object_name,
                    expected="summarizeBy = none", actual=None, status="NA",
                    reason="Propriété summarizeBy absente", evidence=evidence,
                    location=column.locate(context_lines=1),
                    explanation=(
                        "La propriété summarizeBy n'est pas écrite dans le TMDL pour cette "
                        "colonne : son comportement d'agrégation dépend alors du défaut "
                        "appliqué par Power BI, que ce fichier ne permet pas de connaître."
                    ),
                    remediation=(
                        f"Ouvrir {column.source_file} au bloc `column {column.raw_name}` et "
                        "ajouter explicitement `summarizeBy: none` pour lever l'ambiguïté."
                    ),
                ))
                na_details.append({
                    "table": table.name, "column": column.raw_name,
                    "summarizeBy": None, "reason": "Propriété summarizeBy absente",
                })
                continue

            normalized = str(raw_value).strip().lower()

            if normalized == CONFORMING_VALUE:
                conforming += 1
                findings.append(Finding(
                    rule_id=RULE_ID, object_type="column", object=object_name,
                    expected="summarizeBy = none", actual=normalized, status="OK",
                    evidence=evidence,
                    location=column.locate("summarizeBy"),
                    explanation=(
                        "Aucune agrégation automatique n'est appliquée à cette colonne : "
                        "elle ne génère donc pas de mesure implicite."
                    ),
                ))
            elif normalized in KNOWN_NONCONFORMING_VALUES:
                findings.append(Finding(
                    rule_id=RULE_ID, object_type="column", object=object_name,
                    expected="summarizeBy = none", actual=normalized, status="KO",
                    reason="Valeur différente de none", evidence=evidence,
                    location=column.locate("summarizeBy", context_lines=1),
                    explanation=(
                        f"Power BI agrège automatiquement cette colonne avec `{normalized}` "
                        "dès qu'un utilisateur la glisse dans un visuel. Cela crée une mesure "
                        "IMPLICITE : le calcul n'est écrit nulle part, il ne peut être ni relu, "
                        "ni réutilisé, ni corrigé de façon centralisée — et deux visuels peuvent "
                        "silencieusement agréger différemment."
                    ),
                    remediation=(
                        f"Remplacer `summarizeBy: {normalized}` par `summarizeBy: none` "
                        f"(ligne {column.property_lines.get('summarizeBy', '?')} de "
                        f"{column.source_file}). Si l'agrégation est réellement voulue, "
                        f"créer une mesure DAX explicite, par exemple "
                        f"`{normalized.upper()}({table.name}[{column.name}])`."
                    ),
                ))
                ko_details.append({
                    "table": table.name, "column": column.raw_name,
                    "summarizeBy": normalized,
                })
            else:
                findings.append(Finding(
                    rule_id=RULE_ID, object_type="column", object=object_name,
                    expected="summarizeBy = none", actual=raw_value, status="NA",
                    reason="Valeur summarizeBy inconnue ou illisible", evidence=evidence,
                ))
                na_details.append({
                    "table": table.name, "column": column.raw_name,
                    "summarizeBy": raw_value,
                    "reason": "Valeur summarizeBy inconnue ou illisible",
                })

    if ko_details:
        rule_status = "KO"
        execution_status = "PARTIAL" if na_details else "SUCCESS"
    elif na_details:
        rule_status = "NA"
        execution_status = "PARTIAL"
    else:
        rule_status = "OK"
        execution_status = "SUCCESS"

    return RuleResult(
        rule_id=RULE_ID,
        alias=RULE_ALIAS,
        rule_name=RULE_NAME,
        execution_status=execution_status,
        rule_status=rule_status,
        findings=findings,
        summary={
            "total_tables": len(context.tables),
            "total_columns": total_columns,
            "conforming_columns": conforming,
            "nonconforming_columns": len(ko_details),
            "na_columns": len(na_details),
            "ko_details": ko_details,
            "na_details": na_details,
        },
    )
