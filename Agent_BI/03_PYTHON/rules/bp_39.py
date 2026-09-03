"""BP-39 — Configurer et tester les filtres du rapport.

Implémente l'algorithme documenté dans
Agent_BI/01_ALGORITHMES/39_ConfigAndTestFilters.md. Toute évolution de la
logique OK/KO/NA doit d'abord être répercutée dans ce document — ce fichier
ne doit jamais diverger silencieusement de sa spécification fonctionnelle.

PORTÉE PARTIELLE ASSUMÉE. Le document définit DEUX sous-contrôles :

  1. §3/§10 — validation des RÉFÉRENCES : chaque filtre pointe-t-il vers un
     objet qui existe réellement dans le modèle ? Entièrement déterministe,
     implémenté ici.
  2. §6/§11 — détection des CONTRADICTIONS entre niveaux de filtres
     (intersection de contraintes vide). Exige un solveur de contraintes et
     la normalisation typée des littéraux PBIR (§8). NON implémenté : le
     §6 n'autorise un KO que si l'intersection est « mathématiquement vide
     avec une représentation complète », et le §7 impose NA dès qu'une
     condition (Top N, date relative, filtre sur mesure) n'est pas
     intégralement interprétable. Produire ces constats sans solveur ne
     donnerait que des NA.

Conséquence : cette règle ne rend jamais KO pour une contradiction, seulement
pour une référence cassée. C'est un sous-ensemble honnête du document, pas
une divergence — ne pas « compléter » ce fichier par une heuristique de
contradiction sans implémenter le solveur exigé.

La couverture du modèle (§3, `semantic_model_coverage`) est considérée
COMPLÈTE dès qu'au moins une table a été lue : le moteur lit
systématiquement tout `definition/tables/*.tmdl`, il n'existe pas de lecture
partielle dans ce dépôt. Sans aucune table lue, la règle rend NA.
"""

from engine.context import AnalysisContext
from engine.models import Finding, RuleResult, SourceLocation

RULE_ID = "BP-39"
RULE_NAME = "Configurer et tester les filtres du rapport"


def _build_model_object_index(context: AnalysisContext) -> "set[tuple[str, str, str]]":
    """(kind, table, propriété) pour chaque colonne et mesure du modèle."""
    index: set[tuple[str, str, str]] = set()
    for table in context.tables:
        for column in table.columns:
            index.add(("Column", table.name, column.name))
        for measure in table.measures:
            index.add(("Measure", table.name, measure.name))
    return index


def _describe(filter_def) -> str:
    """Identifiant lisible d'un filtre pour la preuve : le `name` PBIR est un
    hachage opaque, seul le niveau + page/visuel permet de le retrouver."""
    location = filter_def.level
    if filter_def.page_id:
        location += f"/{filter_def.page_id}"
    if filter_def.visual_id:
        location += f"/{filter_def.visual_id}"
    return f"{location}#{filter_def.name}" if filter_def.name else location


def _evaluate_filter(filter_def, model_index) -> Finding:
    object_name = _describe(filter_def)
    evidence = {
        "level": filter_def.level,
        "page_id": filter_def.page_id,
        "visual_id": filter_def.visual_id,
        "filter_type": filter_def.filter_type,
        "source_file": filter_def.source_file,
    }

    references = list(filter_def.field_references)
    if not references:
        # §4 : une construction PBIR non supportée par le parser ne doit
        # jamais être considérée comme un filtre cassé.
        return Finding(
            rule_id=RULE_ID,
            object_type="filter",
            object=object_name,
            expected="champ filtré résolu et existant",
            actual=None,
            status="NA",
            reason="Champ filtré non résolvable (construction PBIR non supportée)",
            evidence=evidence,
        )

    missing = []
    unresolved = []
    for kind, entity, prop in references:
        if not entity or not prop:
            unresolved.append({"kind": kind, "entity": entity, "property": prop})
        elif (kind, entity, prop) not in model_index:
            missing.append({"kind": kind, "entity": entity, "property": prop})

    if missing:
        cible = ", ".join(f"{m['entity']}[{m['property']}]" for m in missing)
        return Finding(
            rule_id=RULE_ID,
            object_type="filter",
            object=object_name,
            expected="champ filtré existant dans le modèle",
            actual=cible,
            status="KO",
            reason="Filtre référençant un objet absent du modèle sémantique",
            evidence={**evidence, "missing_references": missing, "model_coverage_complete": True},
            location=SourceLocation.from_file(filter_def.source_file, filter_def.line, context_lines=2),
            explanation=(
                f"Ce filtre pointe vers {cible}, qui n'existe pas dans le modèle. "
                "Le champ a probablement été renommé ou déplacé dans une autre table "
                "sans que le filtre soit mis à jour : il ne filtre donc plus rien, et "
                "les visuels de la page affichent silencieusement des données non "
                "filtrées — sans aucun message d'erreur pour l'utilisateur."
            ),
            remediation=(
                "Rouvrir la page dans Power BI Desktop et repointer le filtre vers la "
                "table qui porte réellement ce champ, ou le supprimer s'il est obsolète"
                + (
                    f" (déclaré ligne {filter_def.line} de {filter_def.source_file})."
                    if filter_def.line
                    else "."
                )
            ),
        )

    if unresolved:
        return Finding(
            rule_id=RULE_ID,
            object_type="filter",
            object=object_name,
            expected="champ filtré résolu et existant",
            actual=None,
            status="NA",
            reason="Référence de champ incomplète",
            evidence={**evidence, "unresolved_references": unresolved},
        )

    return Finding(
        rule_id=RULE_ID,
        object_type="filter",
        object=object_name,
        expected="champ filtré existant dans le modèle",
        actual=", ".join(f"{e}[{p}]" for _k, e, p in references),
        status="OK",
        evidence=evidence,
    )


def check(context: AnalysisContext) -> RuleResult:
    if not context.tables:
        # Sans modèle lu, l'absence d'un objet ne prouve rien (§3, couverture
        # incomplète -> NA).
        return RuleResult(
            rule_id=RULE_ID,
            rule_name=RULE_NAME,
            execution_status="ERROR",
            rule_status="NA",
            summary={"reason": "Aucun fichier de table TMDL trouvé : couverture modèle incomplète"},
        )

    if context.report_path is None:
        return RuleResult(
            rule_id=RULE_ID,
            rule_name=RULE_NAME,
            execution_status="SUCCESS",
            rule_status="NA",
            summary={
                "reason": "Aucun dossier <Nom>.Report/ trouvé : aucun filtre à analyser",
                "total_filters": 0,
            },
        )

    if not context.report_filters:
        # §13 : aucun filtre explicite -> la règle n'a rien à tester.
        return RuleResult(
            rule_id=RULE_ID,
            rule_name=RULE_NAME,
            execution_status="SUCCESS",
            rule_status="NA",
            summary={"reason": "Aucun filtre déclaré dans le rapport", "total_filters": 0},
        )

    model_index = _build_model_object_index(context)
    findings = [_evaluate_filter(f, model_index) for f in context.report_filters]

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
            "total_filters": len(findings),
            "valid_filters": len(findings) - len(ko) - len(na),
            "broken_filters": len(ko),
            "na_filters": len(na),
            "ko_details": [f.to_dict() for f in ko],
        },
    )
