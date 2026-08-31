"""BP-07 — Éliminer les colonnes visibles et inutilisées du modèle.

Implémente l'algorithme documenté dans
Agent_BI/01_ALGORITHMES/07_RemoveUnusedFields.md. Toute évolution de la
logique OK/KO/NA doit d'abord être répercutée dans ce document — ce fichier
ne doit jamais diverger silencieusement de sa spécification fonctionnelle.

PÉRIMÈTRE DE LA CONCLUSION (§2) : `usage_scope = CURRENT_PBIP`. La règle
conclut « inutilisée DANS LE PBIP ANALYSÉ », jamais « inutilisée partout » —
un autre rapport branché sur le même modèle, un usage XMLA ou Analyse dans
Excel restent invisibles ici. Le message de preuve le dit explicitement.

COUVERTURE EXIGÉE AVANT TOUT KO (§9) : sans dossier `.Report/` lisible, une
colonne non référencée dans le modèle ne peut pas être déclarée inutilisée —
elle devient NA. C'est la garde principale contre les faux positifs.

Surfaces d'usage analysées (§5) :
  * DAX (mesures, colonnes/tables calculées) — références QUALIFIÉES ;
  * relations (`fromColumn`/`toColumn`) ;
  * `sortByColumn` et `groupByColumn` ;
  * rapport PBIR : toute référence de champ, toutes surfaces confondues.

Sur le DAX, cf. `powerbi/dax_lang.py` : une référence non qualifiée
(`[Nom]`) n'est jamais convertie en usage — elle devient un BLOQUEUR qui
force NA pour toute colonne portant ce nom (§7).
"""

from engine.context import AnalysisContext
from engine.models import Finding, RuleResult
from engine.usage_index import build_usage_index

RULE_ID = "BP-07"
RULE_NAME = "Éliminer les colonnes visibles et inutilisées du modèle"

#: Motif d'exclusion d'une colonne masquée. Partagé avec `bp_21.py`, qui pose
#: la même question et doit y répondre la même chose : deux formulations
#: divergentes seraient deux dialectes dans un même dépôt.
HIDDEN_COLUMN_REASON = "Colonne masquée : hors périmètre de la règle"


def check(context: AnalysisContext) -> RuleResult:
    if not context.tables:
        return RuleResult(
            rule_id=RULE_ID,
            rule_name=RULE_NAME,
            execution_status="ERROR",
            rule_status="NA",
            summary={"reason": "Aucun fichier de table TMDL trouvé"},
        )

    report_covered = context.report_path is not None
    usage, dax_unqualified = build_usage_index(context)

    coverage = {
        "semantic_model": True,
        "relationships": True,
        "dax": True,
        "report": report_covered,
    }

    findings = []
    ko_details = []
    hidden_count = 0
    visible_count = 0

    for table in context.tables:
        for column in table.columns:
            object_name = f"{table.name}.{column.raw_name}"
            base_evidence = {
                "table": table.name,
                "column": column.raw_name,
                "usage_scope": "CURRENT_PBIP",
                "source_file": column.source_file,
            }

            if column.get_property("isHidden"):
                hidden_count += 1
                findings.append(
                    Finding(
                        rule_id=RULE_ID,
                        object_type="column",
                        object=object_name,
                        expected="colonne visible et utilisée",
                        actual="masquée",
                        status="NA",
                        reason=HIDDEN_COLUMN_REASON,
                        evidence=base_evidence,
                    )
                )
                continue

            visible_count += 1
            surfaces = usage.get((table.name, column.name))

            if surfaces:
                findings.append(
                    Finding(
                        rule_id=RULE_ID,
                        object_type="column",
                        object=object_name,
                        expected="colonne visible et utilisée",
                        actual=", ".join(sorted(set(surfaces))),
                        status="OK",
                        evidence={**base_evidence, "usages": sorted(set(surfaces))},
                    )
                )
                continue

            if not report_covered:
                findings.append(
                    Finding(
                        rule_id=RULE_ID,
                        object_type="column",
                        object=object_name,
                        expected="colonne visible et utilisée",
                        actual=None,
                        status="NA",
                        reason="Absence d'usage non démontrable : rapport absent du périmètre analysé",
                        evidence={**base_evidence, "coverage": coverage},
                    )
                )
                continue

            if column.name in dax_unqualified:
                # §7 : une référence DAX non qualifiée du même nom empêche de
                # conclure pour cette colonne.
                findings.append(
                    Finding(
                        rule_id=RULE_ID,
                        object_type="column",
                        object=object_name,
                        expected="colonne visible et utilisée",
                        actual=None,
                        status="NA",
                        reason="Absence d'usage non démontrable : référence DAX non qualifiée de même nom",
                        evidence={**base_evidence, "blocker": f"[{column.name}]"},
                    )
                )
                continue

            findings.append(
                Finding(
                    rule_id=RULE_ID,
                    object_type="column",
                    object=object_name,
                    expected="colonne visible et utilisée",
                    actual="aucun usage détecté",
                    status="KO",
                    reason="Colonne visible sans aucune utilisation détectée dans le PBIP analysé",
                    evidence={
                        **base_evidence,
                        "coverage": coverage,
                        "resolved_usage_count": 0,
                        "coverage_complete": True,
                    },
                    location=column.locate(context_lines=1),
                    explanation=(
                        "Cette colonne est exposée aux utilisateurs dans le volet des champs mais "
                        "n'est référencée nulle part dans CE projet : ni en DAX, ni par une "
                        "relation, ni par un tri, ni dans un visuel du rapport. Elle occupe de la "
                        "mémoire au rafraîchissement et allonge la liste des champs sans servir. "
                        "Attention : un autre rapport branché sur le même modèle, un accès XMLA ou "
                        "Analyse dans Excel ne sont PAS visibles ici."
                    ),
                    remediation=(
                        f"Vérifier qu'aucun consommateur externe n'utilise "
                        f"`{table.name}[{column.name}]`, puis la supprimer du modèle "
                        f"(ligne {column.line} de {column.source_file}) — ou la masquer avec "
                        "`isHidden` si elle doit rester pour compatibilité."
                    ),
                )
            )
            ko_details.append({"table": table.name, "column": column.raw_name})

    # §12 : les colonnes masquées (hors périmètre) ne font pas basculer le
    # statut global à elles seules.
    evaluable = [f for f in findings if f.reason != HIDDEN_COLUMN_REASON]
    na_evaluable = [f for f in evaluable if f.status == "NA"]

    if ko_details:
        rule_status = "KO"
    elif na_evaluable:
        rule_status = "NA"
    elif evaluable:
        rule_status = "OK"
    else:
        rule_status = "NA"

    return RuleResult(
        rule_id=RULE_ID,
        rule_name=RULE_NAME,
        execution_status="SUCCESS" if report_covered else "PARTIAL",
        rule_status=rule_status,
        findings=findings,
        summary={
            "usage_scope": "CURRENT_PBIP",
            "coverage": coverage,
            "total_columns": hidden_count + visible_count,
            "hidden_columns": hidden_count,
            "visible_columns": visible_count,
            "unused_columns": len(ko_details),
            "ko_details": ko_details,
        },
    )
