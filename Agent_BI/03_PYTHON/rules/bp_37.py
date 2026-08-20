"""BP-37 — Organiser les visuels et les signets.

Implémente l'algorithme documenté dans
Agent_BI/01_ALGORITHMES/37_OrganizeVisualsBookmarks.md. Toute évolution de la
logique OK/KO/NA doit d'abord être répercutée dans ce document — ce fichier
ne doit jamais diverger silencieusement de sa spécification fonctionnelle.

PORTÉE PARTIELLE ASSUMÉE. Le document définit deux familles de contrôles
(§10) ; seule la première est implémentée :

  1. ÉLÉMENTS STRUCTURELS — références de groupe et hiérarchie de signets.
     Entièrement déterministe, implémenté ici.
  2. ORGANISATION / NOMMAGE — noms de groupes et de signets « par défaut »
     (`Group 1`, `Bookmark 2`). NON implémenté : §4 et §9 exigent une liste
     de motifs interdits fournie par `COMPANY_POLICY` ; sans elle, le
     document impose `NA / diagnostic`. Fabriquer une regex `^Group\\s*\\d*$`
     ici reviendrait à inventer la policy.

§5 est également respecté : le nombre de visuels NON groupés ne produit
jamais de KO ni ne modifie le statut — c'est un diagnostic, pas une
non-conformité.
"""

from engine.context import AnalysisContext
from engine.models import Finding, RuleResult

RULE_ID = "BP-37"
RULE_NAME = "Organiser les visuels et les signets"


def _detect_bookmark_cycles(items) -> "list[list[str]]":
    """Cycles dans la hiérarchie `bookmarks.json` (§6.3).

    Parcours en profondeur classique avec pile d'ancêtres : un enfant déjà
    présent dans la pile courante ferme un cycle.
    """
    children_of = {name: list(children) for name, children in items if name}
    cycles: "list[list[str]]" = []
    seen_globally: "set[str]" = set()

    def visit(node, stack):
        if node in stack:
            cycles.append(stack[stack.index(node):] + [node])
            return
        if node in seen_globally or node not in children_of:
            return
        seen_globally.add(node)
        for child in children_of[node]:
            visit(child, stack + [node])

    for name in children_of:
        visit(name, [])
    return cycles


def check(context: AnalysisContext) -> RuleResult:
    if context.report_path is None:
        return RuleResult(
            rule_id=RULE_ID, rule_name=RULE_NAME,
            execution_status="PARTIAL", rule_status="NA",
            summary={"reason": "Aucun dossier <Nom>.Report/ trouvé : structure non analysable"},
        )

    structure = context.report_structure
    findings = []

    # --- Références de groupe (§3) -------------------------------------
    for page_id, visual_name, parent in structure.get("parent_links", []):
        object_name = f"{page_id}/{visual_name}"
        groups = structure.get("groups", {}).get(page_id, set())
        evidence = {"page": page_id, "visual": visual_name, "parentGroupName": parent}

        if parent in groups:
            findings.append(Finding(
                rule_id=RULE_ID, object_type="visual", object=object_name,
                expected="parentGroupName vers un groupe existant de la page",
                actual=parent, status="OK", evidence=evidence,
            ))
        else:
            findings.append(Finding(
                rule_id=RULE_ID, object_type="visual", object=object_name,
                expected="parentGroupName vers un groupe existant de la page",
                actual=parent, status="KO",
                reason="parentGroupName référence un groupe inexistant",
                evidence=evidence,
            ))

    # --- Hiérarchie de signets (§6, §7, §8) -----------------------------
    bookmark_files = structure.get("bookmark_files", set())
    bookmark_items = structure.get("bookmark_items", [])
    metadata_present = structure.get("bookmarks_metadata_present", False)

    if bookmark_files and not metadata_present:
        # §7 : métadonnée absente alors que des signets existent -> NA. Ne
        # jamais supposer la hiérarchie.
        findings.append(Finding(
            rule_id=RULE_ID, object_type="bookmarks", object="bookmarks.json",
            expected="hiérarchie de signets lisible", actual=None, status="NA",
            reason="bookmarks.json absent alors que des fichiers de signets existent",
            evidence={"bookmark_file_count": len(bookmark_files)},
        ))
    elif metadata_present:
        known = set(bookmark_files) | {name for name, _c in bookmark_items if name}
        for name, children in bookmark_items:
            for child in children:
                if child not in known:
                    findings.append(Finding(
                        rule_id=RULE_ID, object_type="bookmark", object=str(name),
                        expected="enfant de signet existant", actual=child, status="KO",
                        reason="bookmarks.json référence un signet inexistant",
                        evidence={"parent": name, "missing_child": child},
                    ))
        for cycle in _detect_bookmark_cycles(bookmark_items):
            findings.append(Finding(
                rule_id=RULE_ID, object_type="bookmark", object=" -> ".join(cycle),
                expected="hiérarchie acyclique", actual="cycle", status="KO",
                reason="Cycle démontré dans la hiérarchie des signets",
                evidence={"cycle": cycle},
            ))

    if not findings:
        return RuleResult(
            rule_id=RULE_ID, rule_name=RULE_NAME,
            execution_status="SUCCESS", rule_status="NA",
            summary={"reason": "Aucun groupe de visuels ni signet à contrôler",
                     "broken_group_references": 0, "broken_bookmark_references": 0},
        )

    ko = [f for f in findings if f.status == "KO"]
    na = [f for f in findings if f.status == "NA"]

    if ko:
        rule_status = "KO"
    elif na:
        rule_status = "NA"
    else:
        rule_status = "OK"

    return RuleResult(
        rule_id=RULE_ID, rule_name=RULE_NAME,
        execution_status="SUCCESS", rule_status=rule_status,
        findings=findings,
        summary={
            "checked_group_references": len(structure.get("parent_links", [])),
            "broken_group_references": sum(1 for f in ko if f.object_type == "visual"),
            "bookmark_count": len(bookmark_files),
            "broken_bookmark_references": sum(1 for f in ko if f.object_type == "bookmark"),
            "ko_details": [f.to_dict() for f in ko],
        },
    )
