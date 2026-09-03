"""BP-01 — Intégrité structurelle du graphe relationnel.

Implémente l'algorithme documenté dans
Agent_BI/01_ALGORITHMES/01_Relations.md. Toute évolution de la logique
OK/KO/NA doit d'abord être répercutée dans ce document — ce fichier ne doit
jamais diverger silencieusement de sa spécification fonctionnelle.

Portée : ce que BP-03 ne voit pas. La cardinalité et le filtrage croisé
appartiennent entièrement à BP-03 (§1 du document) ; une relation dont la
cardinalité est en cause sort ici en NA « délégué » et n'entre pas dans le
statut global. Deux KO pour une même cause rendraient le rapport illisible, et
un désaccord entre les deux règles détruirait leur crédibilité.

La topologie (étoile, flocon, constellation, hybride) N'EST PAS un critère de
conformité (§1). `schema_type` est publié dans le résumé à titre descriptif et
n'apparaît dans aucune condition de statut.

Piège central, mesuré avant d'être écrit (§4.2) : le graphe d'ambiguïté est
ORIENTÉ, du côté `one` vers le côté `many`. Parcouru sans orientation, un
modèle en constellation parfaitement sain produit un KO par couple de tables —
9 faux KO sur AI_BAROMETER_BI-CDS, 0 en lecture orientée.
"""

from engine.context import AnalysisContext
from engine.models import Finding, RuleResult

# Défauts TMDL de cardinalité : source unique du dépôt, déjà sourcée et
# documentée dans bp_03.py. Les redéclarer ici créerait deux vérités pour un
# même fait de format.
from rules.bp_03 import DEFAULT_FROM_CARDINALITY, DEFAULT_TO_CARDINALITY

RULE_ID = "BP-01"
RULE_NAME = "Intégrité structurelle du graphe relationnel"

# Garde contre l'explosion combinatoire de l'énumération des chemins simples.
# Dépassée, la détection d'ambiguïté rend NA — jamais OK : ne pas avoir fini de
# chercher n'est pas une preuve d'absence.
MAX_PATH_STEPS = 200_000


def _build_column_index(tables) -> "dict[str, set[str]]":
    """table -> noms de colonnes. Construit UNE fois pour tout le contrôle.

    Les noms sont ceux de `ColumnDef.name` et de `RelationshipDef.*_column`,
    tous deux déjà dénormalisés par le parseur TMDL (guillemets retirés, espaces
    significatifs conservés : `D_CHOICE.'ID '` devient la colonne `"ID "`).
    """
    return {table.name: {column.name for column in table.columns} for table in tables}


def _orientation(rel) -> "tuple[str, str] | None":
    """(côté one, côté many) pour une relation exploitable, sinon None.

    None signale une cardinalité qui relève de BP-03 (`*:*`, `1:1`) ou une
    valeur illisible : dans les deux cas BP-01 ne se prononce pas.
    """
    frm = (rel.from_cardinality or DEFAULT_FROM_CARDINALITY).strip().lower()
    to = (rel.to_cardinality or DEFAULT_TO_CARDINALITY).strip().lower()
    if frm == "many" and to == "one":
        return rel.to_table, rel.from_table
    if frm == "one" and to == "many":
        return rel.from_table, rel.to_table
    return None


def _missing_references(rel, column_index) -> list[str]:
    """Extrémités de la relation absentes du modèle, dans l'ordre de lecture."""
    missing = []
    for table, column in ((rel.from_table, rel.from_column), (rel.to_table, rel.to_column)):
        if table not in column_index:
            missing.append(f"table {table}")
        elif column not in column_index[table]:
            missing.append(f"{table}.{column}")
    return missing


def _evaluate_relationship(rel, column_index) -> "tuple[Finding, bool]":
    """Retourne (constat, délégué). `délégué` = cardinalité relevant de BP-03
    (§4.3), qui ne doit jamais faire basculer le statut global de BP-01.

    Le drapeau voyage à côté du constat plutôt que dedans : `Finding` n'a pas
    de `reason_code`, et c'est déjà la façon dont bp_11.py porte son
    « hors périmètre ».
    """
    object_name = rel.id or f"{rel.from_table}.{rel.from_column} -> {rel.to_table}.{rel.to_column}"
    evidence = {
        "from": f"{rel.from_table}.{rel.from_column}",
        "to": f"{rel.to_table}.{rel.to_column}",
        "is_active": rel.is_active,
        "source_file": rel.source_file,
    }

    if _orientation(rel) is None:
        return Finding(
            rule_id=RULE_ID,
            object_type="relationship",
            object=object_name,
            expected="références existantes",
            actual=None,
            status="NA",
            reason="Cardinalité contrôlée par BP-03",
            evidence=evidence,
        ), True

    missing = _missing_references(rel, column_index)
    if missing:
        return Finding(
            rule_id=RULE_ID,
            object_type="relationship",
            object=object_name,
            expected="table et colonne existantes aux deux extrémités",
            actual=", ".join(missing),
            status="KO",
            reason="Relation référençant un objet absent du modèle",
            evidence={**evidence, "missing": missing},
            location=rel.locate(context_lines=1),
            explanation=(
                f"Cette relation référence {', '.join(missing)}, qui n'existe pas dans le "
                "modèle sémantique. Power BI ne peut pas l'établir : le filtrage attendu "
                "entre ces deux tables ne se produira pas, silencieusement."
            ),
            remediation=(
                "Corriger le nom référencé dans relationships.tmdl, ou rétablir l'objet "
                "supprimé dans definition/tables/. Si la relation n'a plus lieu d'être, "
                "la supprimer."
            ),
        ), False

    return Finding(
        rule_id=RULE_ID,
        object_type="relationship",
        object=object_name,
        expected="table et colonne existantes aux deux extrémités",
        actual="références résolues",
        status="OK",
        evidence=evidence,
    ), False


def _count_paths(source, target, edges, seen, budget) -> "tuple[int, list[int]]":
    """Nombre de chemins simples orientés source -> target, plafonné à 2.

    S'arrête dès le deuxième chemin : la règle a besoin de savoir s'il y en a
    plus d'un, pas combien. `budget` est une liste d'un élément servant de
    compteur partagé (§4.2, garde MAX_PATH_STEPS).
    """
    if source == target:
        return 1, budget
    total = 0
    for nxt in edges.get(source, ()):
        if nxt in seen:
            continue
        budget[0] -= 1
        if budget[0] <= 0:
            return total, budget
        found, budget = _count_paths(nxt, target, edges, seen | {nxt}, budget)
        total += found
        if total > 1:
            return total, budget
    return total, budget


def _detect_ambiguous_paths(relationships) -> "tuple[list[Finding], bool]":
    """(constats d'ambiguïté, budget épuisé).

    Graphe ORIENTÉ one -> many, relations actives et non déléguées uniquement.
    """
    edges: dict[str, list[str]] = {}
    nodes: set[str] = set()
    for rel in relationships:
        if rel.is_active is False:
            continue
        orientation = _orientation(rel)
        if orientation is None:
            continue
        one_end, many_end = orientation
        edges.setdefault(one_end, []).append(many_end)
        nodes.update((one_end, many_end))

    findings: list[Finding] = []
    budget = [MAX_PATH_STEPS]
    for source in sorted(nodes):
        for target in sorted(nodes):
            if source == target:
                continue
            count, budget = _count_paths(source, target, edges, {source}, budget)
            if budget[0] <= 0:
                return findings, True
            if count > 1:
                findings.append(
                    Finding(
                        rule_id=RULE_ID,
                        object_type="table_pair",
                        object=f"{source} -> {target}",
                        expected="un seul chemin de propagation de filtre",
                        actual=f"{count} chemins ou plus",
                        status="KO",
                        reason="Plusieurs chemins de filtrage entre deux tables",
                        evidence={"source": source, "target": target},
                        explanation=(
                            f"Le filtre de `{source}` atteint `{target}` par plusieurs "
                            "chemins. Power BI en choisit un arbitrairement : le résultat "
                            "d'une mesure peut changer sans qu'aucune formule ne bouge."
                        ),
                        remediation=(
                            "Désactiver l'une des relations du cycle et l'invoquer "
                            "explicitement par USERELATIONSHIP là où elle est nécessaire."
                        ),
                    )
                )
    return findings, False


def _schema_type(relationships) -> str:
    """Forme du modèle — DESCRIPTIVE (§9). N'entre dans aucune condition de statut."""
    one_ends: set[str] = set()
    many_ends: set[str] = set()
    for rel in relationships:
        orientation = _orientation(rel)
        if orientation is None:
            continue
        one_end, many_end = orientation
        one_ends.add(one_end)
        many_ends.add(many_end)

    if not one_ends and not many_ends:
        return "UNKNOWN"
    if one_ends & many_ends:
        return "SNOWFLAKE"
    if len(many_ends) > 1:
        return "GALAXY"
    return "STAR"


def check(context: AnalysisContext) -> RuleResult:
    if not context.relationships:
        return RuleResult(
            rule_id=RULE_ID,
            rule_name=RULE_NAME,
            execution_status="SUCCESS",
            rule_status="NA",
            summary={
                "reason": "Aucune relation trouvée dans relationships.tmdl",
                "relationships_total": 0,
            },
        )

    if not context.tables:
        return RuleResult(
            rule_id=RULE_ID,
            rule_name=RULE_NAME,
            execution_status="ERROR",
            rule_status="NA",
            summary={
                "reason": "Aucune table lisible : existence des références indécidable",
                "relationships_total": len(context.relationships),
            },
        )

    column_index = _build_column_index(context.tables)
    evaluated = [_evaluate_relationship(rel, column_index) for rel in context.relationships]
    findings = [finding for finding, _delegated in evaluated]
    evaluable = [finding for finding, delegated in evaluated if not delegated]

    ambiguous, budget_exhausted = _detect_ambiguous_paths(context.relationships)
    findings.extend(ambiguous)
    evaluable.extend(ambiguous)

    if budget_exhausted:
        interrupted = Finding(
            rule_id=RULE_ID,
            object_type="model",
            object="graphe relationnel",
            expected="détection d'ambiguïté menée à terme",
            actual=None,
            status="NA",
            reason="Exploration des chemins interrompue : graphe trop dense",
            evidence={"max_path_steps": MAX_PATH_STEPS},
        )
        findings.append(interrupted)
        evaluable.append(interrupted)

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

    delegated = len(findings) - len(evaluable)
    return RuleResult(
        rule_id=RULE_ID,
        rule_name=RULE_NAME,
        execution_status="SUCCESS" if not na else "PARTIAL",
        rule_status=rule_status,
        findings=findings,
        summary={
            # Descriptif, jamais évalué (§9).
            "schema_type": _schema_type(context.relationships),
            "relationships_total": len(context.relationships),
            "relationships_checked": len(context.relationships) - delegated,
            "delegated_to_bp03": delegated,
            "broken_references": len([f for f in ko if f.object_type == "relationship"]),
            "ambiguous_pairs": len([f for f in ko if f.object_type == "table_pair"]),
            "ko_details": [f.to_dict() for f in ko],
        },
    )
