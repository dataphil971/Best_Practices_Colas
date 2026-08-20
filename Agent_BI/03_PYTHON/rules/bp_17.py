"""BP-17 — Utiliser un SQL Warehouse pour Databricks en DirectQuery.

Implémente l'algorithme documenté dans
Agent_BI/01_ALGORITHMES/17_DatabricksEndpoint.md. Toute évolution de la
logique OK/KO/NA doit d'abord être répercutée dans ce document — ce fichier
ne doit jamais diverger silencieusement de sa spécification fonctionnelle.

Portée réelle par rapport au pseudo-code de référence : `endpoint_metadata`
(une métadonnée structurée externe) n'existe pas dans ce dépôt — seule la
résolution par `httpPath` (§5-6) est implémentée. Un `httpPath` non résolvable
statiquement (paramètre, concaténation, expression) reste NA, jamais deviné.

AVERTISSEMENT — deux briques restent non vérifiées contre un export PBIP
réel :
  1. Le format du bloc `partition` en TMDL (cf. avertissement en tête de
     powerbi/tmdl_parser.py) ;
  2. Le motif reconnu pour COMPUTE_CLUSTER : le document ne fournit aucune
     regex canonique (`classify_known_compute_path` y est référencée sans
     corps — §6 du document). Le motif utilisé ici,
     `/sql/protocolv1/o/<workspace-id>/<cluster-id>`, est la forme connue du
     chemin JDBC/ODBC d'un cluster interactif Databricks (documentation
     Databricks), pas une supposition arbitraire — mais reste, comme le
     reste de ce fichier, à confirmer sur un vrai projet.
"""

import re

from engine.context import AnalysisContext
from engine.models import Finding, PartitionDef, RuleResult
from powerbi.m_lang import find_function_calls, resolve_m_string_literal

RULE_ID = "BP-17"
RULE_NAME = "Utiliser un SQL Warehouse pour Databricks en DirectQuery"

DATABRICKS_CONNECTOR_FUNCTION = "Databricks.Catalogs"

SQL_WAREHOUSE_PATH = re.compile(r"^/sql/1\.0/warehouses/[^/]+$", re.IGNORECASE)
# Cf. avertissement en tête de fichier : forme documentée du endpoint JDBC/ODBC
# d'un cluster interactif Databricks (par opposition à un SQL Warehouse).
COMPUTE_CLUSTER_PATH = re.compile(r"^/sql/protocolv1/o/\d+/[0-9a-fA-F-]+$")


def _classify_endpoint(http_path: str) -> str:
    normalized = http_path.strip()
    if SQL_WAREHOUSE_PATH.fullmatch(normalized):
        return "SQL_WAREHOUSE"
    if COMPUTE_CLUSTER_PATH.fullmatch(normalized):
        return "COMPUTE_CLUSTER"
    return "UNKNOWN"


def _evaluate_partition(table_name: str, partition: PartitionDef) -> "tuple[Finding, bool]":
    """Retourne (constat, hors_perimetre) — `hors_perimetre` distingue une
    partition simplement non concernée (pas DirectQuery, pas Databricks) d'un
    constat qui compte réellement dans le statut global (§9 du document)."""
    object_name = f"{table_name}/{partition.name}"
    mode = (partition.mode or "").strip().lower()

    if mode != "directquery":
        return Finding(
            rule_id=RULE_ID, object_type="partition", object=object_name,
            expected="OK/KO uniquement pour DirectQuery", actual=partition.mode, status="NA",
            reason="Partition hors périmètre DirectQuery",
            evidence={"mode": partition.mode},
        ), True

    calls = find_function_calls(partition.m_source, DATABRICKS_CONNECTOR_FUNCTION)
    if not calls:
        return Finding(
            rule_id=RULE_ID, object_type="partition", object=object_name,
            expected="connecteur Databricks", actual=None, status="NA",
            reason="Partition DirectQuery non Databricks",
            evidence={"mode": partition.mode},
        ), True

    call = calls[0]
    if len(call.raw_arguments) < 2:
        return Finding(
            rule_id=RULE_ID, object_type="partition", object=object_name,
            expected="Databricks.Catalogs(hôte, httpPath, ...)", actual=None, status="NA",
            reason="Appel Databricks.Catalogs sans second argument (httpPath)",
            evidence={"raw_arguments": call.raw_arguments},
        ), False

    http_path = resolve_m_string_literal(call.raw_arguments[1])
    if http_path is None:
        return Finding(
            rule_id=RULE_ID, object_type="partition", object=object_name,
            expected="httpPath résolvable statiquement",
            actual=call.raw_arguments[1], status="NA",
            reason="httpPath Databricks non résolvable (paramètre ou expression dynamique)",
            evidence={"raw_argument": call.raw_arguments[1]},
        ), False

    endpoint = _classify_endpoint(http_path)
    evidence = {"http_path": http_path, "source_file": partition.source_file}

    if endpoint == "SQL_WAREHOUSE":
        return Finding(
            rule_id=RULE_ID, object_type="partition", object=object_name,
            expected="SQL_WAREHOUSE", actual=endpoint, status="OK", evidence=evidence,
        ), False

    if endpoint == "COMPUTE_CLUSTER":
        return Finding(
            rule_id=RULE_ID, object_type="partition", object=object_name,
            expected="SQL_WAREHOUSE", actual=endpoint, status="KO",
            reason="Endpoint Databricks de type compute cluster interactif",
            evidence=evidence,
        ), False

    return Finding(
        rule_id=RULE_ID, object_type="partition", object=object_name,
        expected="SQL_WAREHOUSE", actual=None, status="NA",
        reason="Type d'endpoint Databricks non déterminable",
        evidence=evidence,
    ), False


def check(context: AnalysisContext) -> RuleResult:
    results = [
        _evaluate_partition(table.name, partition)
        for table in context.tables
        for partition in table.partitions
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
