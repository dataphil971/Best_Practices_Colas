"""BP-41 — Détection des visuels redondants ou dupliqués.

Implémente l'algorithme documenté dans
Agent_BI/01_ALGORITHMES/41_RemoveRedundantVisuals.md. Toute évolution de la
logique OK/KO/NA doit d'abord être répercutée dans ce document — ce fichier
ne doit jamais diverger silencieusement de sa spécification fonctionnelle.

RÈGLE HYBRIDE — première du moteur à produire des CANDIDATS plutôt que des
verdicts. Le §2 est explicite : la partie Python détecte, la qualification
appartient à une revue contextuelle, et

    « Le checker Python ne doit jamais transformer seul un candidat en KO
      sur la simple égalité des signatures. »

Ce fichier s'y tient strictement : il ne renvoie JAMAIS `KO`. Il produit des
`Candidate` destinés au skill `.claude/skills/agent-bi-context-review`, qui
les qualifiera en JUSTIFIE / NON_CONFORME_CONFIRME / NON_RESOLU. Le statut de
la règle reste `NA` tant qu'aucune qualification n'est revenue — conforme au
principe partagé par l'algorithme et le skill : `candidat != violation`.

Une répétition est très souvent légitime (§1) : même KPI rappelé sur
plusieurs pages, volet de navigation dupliqué, page de détail. Le contexte de
revue fourni avec chaque candidat (pages concernées, même page ou non,
visuels masqués, appartenance à un groupe) sert précisément à trancher cela.
"""

import hashlib
from collections import defaultdict

from engine.context import AnalysisContext
from engine.models import Candidate, Finding, RuleResult

RULE_ID = "BP-41"
RULE_NAME = "Détection des visuels redondants ou dupliqués"


def _candidate_id(signature) -> str:
    """Identifiant STABLE d'un groupe candidat, dérivé de la seule signature.

    Volontairement indépendant de l'ordre de parcours des fichiers : une
    même analyse relancée doit produire le même `candidate_id`, sinon une
    décision de revue déjà rendue ne pourrait plus être rattachée à son
    candidat.
    """
    payload = repr(signature).encode("utf-8")
    return "DUP-" + hashlib.sha1(payload).hexdigest()[:8]


def check(context: AnalysisContext) -> RuleResult:
    if context.report_path is None:
        return RuleResult(
            rule_id=RULE_ID,
            rule_name=RULE_NAME,
            execution_status="PARTIAL",
            rule_status="NA",
            summary={
                "reason": "Aucun dossier <Nom>.Report/ trouvé : visuels non analysables",
                "duplicate_candidates": 0,
            },
        )

    visuals = context.report_visuals
    if not visuals:
        return RuleResult(
            rule_id=RULE_ID,
            rule_name=RULE_NAME,
            execution_status="SUCCESS",
            rule_status="NA",
            summary={"reason": "Aucun visuel lu dans le rapport", "duplicate_candidates": 0},
        )

    groups = defaultdict(list)
    out_of_scope = 0
    for visual in visuals:
        if visual["signature"] is None:
            # §4 : visuel décoratif/navigation, ou sans champ projeté.
            out_of_scope += 1
            continue
        groups[visual["signature"]].append(visual)

    analytical = sum(len(v) for v in groups.values())
    duplicates = {sig: occ for sig, occ in groups.items() if len(occ) >= 2}

    findings = []
    candidates = []

    for signature, occurrences in sorted(duplicates.items(), key=lambda kv: _candidate_id(kv[0])):
        candidate_id = _candidate_id(signature)
        pages = sorted({o["page_id"] for o in occurrences})
        visual_type, references = signature

        candidates.append(
            Candidate(
                rule_id=RULE_ID,
                candidate_id=candidate_id,
                candidate_type="DUPLICATE_VISUAL",
                objects=[
                    {
                        "page_id": o["page_id"],
                        "visual_id": o["visual_id"],
                        "is_hidden": o["is_hidden"],
                        "parent_group": o["parent_group"],
                        "source_file": o["source_file"],
                    }
                    for o in occurrences
                ],
                technical_evidence={
                    "visual_type": visual_type,
                    "field_references": list(references),
                    "occurrence_count": len(occurrences),
                },
                # §8 : ce que le reviewer doit avoir sous les yeux pour trancher.
                review_context={
                    "same_page": len(pages) == 1,
                    "pages": pages,
                    "distinct_page_count": len(pages),
                    "all_hidden": all(o["is_hidden"] for o in occurrences),
                    "grouped": [o["parent_group"] for o in occurrences],
                    "question": (
                        "Cette répétition est-elle un rappel volontaire (volet de navigation, "
                        "KPI de synthèse, page de détail) ou une duplication à supprimer ?"
                    ),
                },
            )
        )

        findings.append(
            Finding(
                rule_id=RULE_ID,
                object_type="visual_group",
                object=candidate_id,
                expected="répétition justifiée ou supprimée",
                actual=f"{len(occurrences)} visuels de signature identique",
                status="NA",
                reason="Candidat à la redondance : qualification contextuelle requise",
                evidence={
                    "visual_type": visual_type,
                    "pages": pages,
                    "field_references": list(references),
                },
                explanation=(
                    f"{len(occurrences)} visuels `{visual_type}` projettent exactement les mêmes "
                    f"champs ({', '.join(references)}) sur {len(pages)} page(s). Une signature "
                    "identique NE prouve PAS une redondance : le même indicateur peut être rappelé "
                    "volontairement. Seule une revue du contexte (navigation, rôle de chaque page) "
                    "permet de trancher."
                ),
                remediation=(
                    f"Soumettre le candidat {candidate_id} au skill `agent-bi-context-review` "
                    "pour qualification (JUSTIFIE / NON_CONFORME_CONFIRME / NON_RESOLU)."
                ),
            )
        )

    # §2 et principe du skill : un candidat n'est jamais une violation. La
    # règle reste donc NA — jamais KO — tant que la revue n'a pas tranché.
    rule_status = "NA" if candidates else ("OK" if analytical else "NA")

    return RuleResult(
        rule_id=RULE_ID,
        rule_name=RULE_NAME,
        execution_status="SUCCESS",
        rule_status=rule_status,
        findings=findings,
        candidates=candidates,
        summary={
            "total_visuals": len(visuals),
            "analytical_visuals": analytical,
            "out_of_scope_visuals": out_of_scope,
            "duplicate_candidates": len(candidates),
            "requires_context_review": bool(candidates),
            "review_skill": "agent-bi-context-review",
        },
    )
