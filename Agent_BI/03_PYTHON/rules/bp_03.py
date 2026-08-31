"""BP-03 — Éviter les relations bidirectionnelles et many-to-many.

Implémente l'algorithme documenté dans
Agent_BI/01_ALGORITHMES/03_AvoidBidirectional.md. Toute évolution de la
logique OK/KO/NA doit d'abord être répercutée dans ce document — ce fichier
ne doit jamais diverger silencieusement de sa spécification fonctionnelle.

Portée : uniquement le contrôle par relation (cardinalité + filtrage croisé)
décrit dans ce document. La topologie globale du star schema (chaînes
dimension→dimension, cycles) relève de BP-01 (§2 du document), non implémenté
ici — ne pas étendre ce fichier pour la couvrir sans d'abord lire et
implémenter 01_Relations.md séparément.

Politique d'entreprise : le pseudo-code de référence conditionne plusieurs
verdicts à un `company_policy` externe (`bp03_forbid_bidirectional`,
`bp03_is_excluded`, exceptions nommées) qui n'existe nulle part dans ce
dépôt. Le tableau de décision (§10) présente cependant `BOTH_DIRECTIONS`
comme un `KO` inconditionnel, sans la condition « si policy » qui encadre la
prose du §7 : on adopte donc cette lecture comme posture par défaut du
projet (même logique que `CONFORMING_VALUE` codé en dur dans bp_22.py) :
filtrage bidirectionnel interdit, aucune relation exclue, aucune exception
nommée. Documenté ici plutôt qu'inventé silencieusement.
"""

from engine.context import AnalysisContext
from engine.models import Finding, RuleResult

RULE_ID = "BP-03"
RULE_NAME = "Éviter les relations bidirectionnelles et many-to-many"

# Défauts Power BI quand la propriété est omise en TMDL (TMDL n'écrit une
# propriété que lorsqu'elle diverge de son défaut) : une relation standard
# est *:1 (from = many, to = one) avec filtrage à sens unique. Vérifié sur
# l'unique extrait réel disponible (Agent_BI/01_ALGORITHMES/21_ConciseNames.md
# §3.2), qui n'écrit aucune des trois propriétés pour une relation normale.
DEFAULT_FROM_CARDINALITY = "many"
DEFAULT_TO_CARDINALITY = "one"
DEFAULT_CROSS_FILTER = "onedirection"

KNOWN_CARDINALITIES = {"one", "many"}
KNOWN_CROSS_FILTERS = {"onedirection", "bothdirections", "automatic"}


def _cardinality_shape(rel) -> "str | None":
    frm = (rel.from_cardinality or DEFAULT_FROM_CARDINALITY).strip().lower()
    to = (rel.to_cardinality or DEFAULT_TO_CARDINALITY).strip().lower()
    if frm not in KNOWN_CARDINALITIES or to not in KNOWN_CARDINALITIES:
        return None
    if frm == "many" and to == "many":
        return "MANY_TO_MANY"
    if frm == "one" and to == "one":
        return "ONE_TO_ONE"
    return "ONE_TO_MANY"  # inclut MANY_TO_ONE, symétrique pour cette règle


def _evaluate_relationship(rel) -> Finding:
    object_name = rel.id
    evidence = {
        "from": f"{rel.from_table}.{rel.from_column}",
        "to": f"{rel.to_table}.{rel.to_column}",
        "from_cardinality": rel.from_cardinality,
        "to_cardinality": rel.to_cardinality,
        "cross_filtering_behavior": rel.cross_filtering_behavior,
        "is_active": rel.is_active,
        "source_file": rel.source_file,
    }

    shape = _cardinality_shape(rel)
    if shape is None:
        return Finding(
            rule_id=RULE_ID,
            object_type="relationship",
            object=object_name,
            expected="ONE_TO_MANY / MANY_TO_ONE",
            actual=None,
            status="NA",
            reason="Cardinalité non résolue",
            evidence=evidence,
        )

    if shape == "MANY_TO_MANY":
        return Finding(
            rule_id=RULE_ID,
            object_type="relationship",
            object=object_name,
            expected="ONE_TO_MANY / MANY_TO_ONE",
            actual="MANY_TO_MANY",
            status="KO",
            reason="Relation many-to-many directe",
            evidence=evidence,
        )

    if shape == "ONE_TO_ONE":
        # §9 : Power BI filtre dans les deux sens sur une relation 1:1,
        # indépendamment de ce qu'affiche crossFilteringBehavior.
        return Finding(
            rule_id=RULE_ID,
            object_type="relationship",
            object=object_name,
            expected="ONE_TO_MANY / MANY_TO_ONE",
            actual="ONE_TO_ONE",
            status="KO",
            reason="Relation 1:1 incompatible avec l'interdiction du filtrage bidirectionnel",
            evidence=evidence,
        )

    cross = (rel.cross_filtering_behavior or DEFAULT_CROSS_FILTER).strip().lower()
    if cross not in KNOWN_CROSS_FILTERS:
        return Finding(
            rule_id=RULE_ID,
            object_type="relationship",
            object=object_name,
            expected="ONE_DIRECTION",
            actual=rel.cross_filtering_behavior,
            status="NA",
            reason="crossFilteringBehavior non résolu",
            evidence=evidence,
        )

    if cross == "bothdirections":
        return Finding(
            rule_id=RULE_ID,
            object_type="relationship",
            object=object_name,
            expected="ONE_DIRECTION",
            actual="BOTH_DIRECTIONS",
            status="KO",
            evidence=evidence,
        )

    if cross == "automatic":
        # §8 : le comportement effectif d'AUTOMATIC dépend du moteur au
        # runtime (mode DirectQuery/composite) — jamais résolu statiquement.
        return Finding(
            rule_id=RULE_ID,
            object_type="relationship",
            object=object_name,
            expected="ONE_DIRECTION",
            actual="AUTOMATIC",
            status="NA",
            reason="Comportement AUTOMATIC non déterminable statiquement",
            evidence=evidence,
        )

    return Finding(
        rule_id=RULE_ID,
        object_type="relationship",
        object=object_name,
        expected="ONE_DIRECTION",
        actual="ONE_DIRECTION",
        status="OK",
        evidence=evidence,
    )


def check(context: AnalysisContext) -> RuleResult:
    if not context.relationships:
        return RuleResult(
            rule_id=RULE_ID,
            rule_name=RULE_NAME,
            execution_status="SUCCESS",
            rule_status="NA",
            summary={
                "reason": "Aucune relation trouvée dans relationships.tmdl",
                "total_relationships": 0,
            },
        )

    findings = [_evaluate_relationship(rel) for rel in context.relationships]

    ko = [f for f in findings if f.status == "KO"]
    na = [f for f in findings if f.status == "NA"]

    if ko:
        rule_status = "KO"
    elif na:
        rule_status = "NA"
    else:
        rule_status = "OK"
    execution_status = "SUCCESS" if not na else "PARTIAL"

    return RuleResult(
        rule_id=RULE_ID,
        rule_name=RULE_NAME,
        execution_status=execution_status,
        rule_status=rule_status,
        findings=findings,
        summary={
            "total_relationships": len(findings),
            "ko_details": [f.to_dict() for f in ko],
            "na_details": [f.to_dict() for f in na],
        },
    )
