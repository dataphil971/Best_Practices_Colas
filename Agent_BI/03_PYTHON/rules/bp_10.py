"""BP-10 — Utiliser des clés de relation entières.

Implémente l'algorithme documenté dans
Agent_BI/01_ALGORITHMES/10_SurrogateKeys.md. Toute évolution de la logique
OK/KO/NA doit d'abord être répercutée dans ce document — ce fichier ne doit
jamais diverger silencieusement de sa spécification fonctionnelle.

Type accepté : le document énonce `int64` comme LE standard d'entreprise
attendu (§3 exemple de scope, §4 « le type entier TMDL attendu est
généralement int64 », §14 « les clés relationnelles doivent être entières »).
C'est donc une valeur du référentiel, au même titre que `summarizeBy = none`
pour BP-22 — pas un seuil inventé par le checker. Le §4 interdit
explicitement d'accepter silencieusement `int32`/`integer` : seul `int64`
est retenu.

Aucune exclusion automatique : le §3 interdit d'exclure une table sur son
préfixe (`P_`, `T_`...). Toutes les relations sont évaluées, faute d'un
`company_policy` d'exclusion qui n'existe pas dans ce dépôt.

BP-10 ne juge PAS la cardinalité (§9) — c'est le périmètre de BP-03 — ni ne
prétend qu'une clé `int64` est une vraie surrogate key (§6) : elle vérifie
seulement `INTEGER_RELATION_KEY`.
"""

from engine.context import AnalysisContext
from engine.models import Finding, RuleResult

RULE_ID = "BP-10"
RULE_NAME = "Utiliser des clés de relation entières"

ACCEPTED_TYPES = {"int64"}


def _build_column_type_index(context: AnalysisContext) -> "dict[tuple[str, str], str | None]":
    """(table, colonne) -> dataType brut, ou None si la propriété est absente.

    Une colonne de table CALCULÉE n'a pas de `dataType` sérialisé (son type
    est inféré de l'expression DAX) : c'est un cas réel et fréquent, qui doit
    donner NA (§7 « dataType absent / illisible »), jamais un KO par défaut.
    """
    index: "dict[tuple[str, str], str | None]" = {}
    for table in context.tables:
        for column in table.columns:
            value = column.get_property("dataType")
            index[(table.name, column.name)] = str(value) if value is not None else None
    return index


def _evaluate_relationship(rel, column_types) -> Finding:
    object_name = rel.id
    from_qualified = f"{rel.from_table}.{rel.from_column}"
    to_qualified = f"{rel.to_table}.{rel.to_column}"

    from_known = (rel.from_table, rel.from_column) in column_types
    to_known = (rel.to_table, rel.to_column) in column_types

    evidence = {
        "from": from_qualified,
        "to": to_qualified,
        "accepted_types": sorted(ACCEPTED_TYPES),
        "source_file": rel.source_file,
    }

    if not from_known or not to_known:
        # La colonne référencée n'existe dans aucun fichier de table lu :
        # couverture incomplète, pas une non-conformité de type (§7).
        return Finding(
            rule_id=RULE_ID, object_type="relationship", object=object_name,
            expected="deux clés de type int64", actual=None, status="NA",
            reason="Colonnes de relation non résolues dans les tables lues",
            evidence=evidence,
        )

    from_type = column_types[(rel.from_table, rel.from_column)]
    to_type = column_types[(rel.to_table, rel.to_column)]
    evidence = {**evidence, "from_type": from_type, "to_type": to_type}

    if from_type is None or to_type is None:
        return Finding(
            rule_id=RULE_ID, object_type="relationship", object=object_name,
            expected="deux clés de type int64", actual=None, status="NA",
            reason="dataType non disponible pour au moins une clé (colonne de table calculée)",
            evidence=evidence,
        )

    if from_type in ACCEPTED_TYPES and to_type in ACCEPTED_TYPES:
        return Finding(
            rule_id=RULE_ID, object_type="relationship", object=object_name,
            expected="deux clés de type int64", actual=f"{from_type} / {to_type}",
            status="OK", evidence=evidence,
        )

    # §5 : un écart de type entre les deux extrémités est un diagnostic
    # SUPPLÉMENTAIRE, le constat principal reste "type attendu non respecté".
    diagnostics = ["TYPE_MISMATCH"] if from_type != to_type else []

    return Finding(
        rule_id=RULE_ID, object_type="relationship", object=object_name,
        expected="deux clés de type int64", actual=f"{from_type} / {to_type}",
        status="KO", reason="Clé de relation non entière",
        evidence={**evidence, "diagnostics": diagnostics},
        location=rel.locate("fromColumn", context_lines=2),
        explanation=(
            f"La relation s'appuie sur des clés de type `{from_type}` / `{to_type}`. "
            "Une jointure sur du texte occupe beaucoup plus de mémoire qu'un entier "
            "(le dictionnaire VertiPaq stocke chaque valeur distincte) et ralentit "
            "chaque filtre traversant la relation."
            + (" De plus, les deux extrémités n'ont pas le même type, ce qui force une "
               "conversion à chaque évaluation." if "TYPE_MISMATCH" in diagnostics else "")
        ),
        remediation=(
            f"Introduire une clé de substitution entière partagée par {from_qualified} et "
            f"{to_qualified}, la générer en amont (Power Query ou source), puis repointer "
            f"la relation dessus (ligne {rel.line} de {rel.source_file})."
        ),
    )


def check(context: AnalysisContext) -> RuleResult:
    if not context.relationships:
        return RuleResult(
            rule_id=RULE_ID,
            rule_name=RULE_NAME,
            execution_status="SUCCESS",
            rule_status="NA",
            summary={"reason": "Aucune relation trouvée dans relationships.tmdl",
                     "total_relationships": 0},
        )

    column_types = _build_column_type_index(context)
    findings = [_evaluate_relationship(rel, column_types) for rel in context.relationships]

    ko = [f for f in findings if f.status == "KO"]
    na = [f for f in findings if f.status == "NA"]

    if ko:
        rule_status = "KO"
    elif na:
        rule_status = "NA"
    else:
        rule_status = "OK"

    return RuleResult(
        rule_id=RULE_ID,
        rule_name=RULE_NAME,
        execution_status="SUCCESS" if not na else "PARTIAL",
        rule_status=rule_status,
        findings=findings,
        summary={
            "total_relationships": len(findings),
            "conforming_relationships": len(findings) - len(ko) - len(na),
            "nonconforming_relationships": len(ko),
            "na_relationships": len(na),
            "ko_details": [f.to_dict() for f in ko],
        },
    )
