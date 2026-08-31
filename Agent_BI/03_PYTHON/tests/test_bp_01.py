"""Tests de non-régression pour BP-01.

Scénarios alignés sur Agent_BI/01_ALGORITHMES/01_Relations.md :
si un de ces tests doit changer, l'algorithme doit changer en premier.
"""

from pathlib import Path

from engine.context import AnalysisContext
from rules import bp_01

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "bp_01"


def _context_for(scenario: str) -> AnalysisContext:
    return AnalysisContext.from_semantic_model_path(FIXTURES / scenario)


def test_ok_when_every_reference_resolves():
    result = bp_01.check(_context_for("ok"))

    assert result.rule_status == "OK"
    assert result.summary["broken_references"] == 0
    assert result.summary["relationships_checked"] == 1


def test_a_galaxy_sharing_dimensions_is_not_ambiguous():
    # §4.2 — LE test de non-régression de cette règle. Deux faits partageant
    # deux dimensions forment un cycle dans le graphe NON orienté : une lecture
    # non orientée rendrait ici plusieurs KO, tous faux. Le filtre ne remonte
    # jamais d'un fait vers une dimension, donc aucun chemin n'est ambigu.
    result = bp_01.check(_context_for("ok_galaxy"))

    assert result.rule_status == "OK"
    assert result.summary["ambiguous_pairs"] == 0
    assert result.summary["schema_type"] == "GALAXY"


def test_quoted_names_with_significant_spaces_resolve():
    # §3.1 — `D_CHOICE.'ID '` porte un espace final significatif. Le comparer
    # à sa forme brute (guillemets compris) le déclarerait absent, donc KO.
    result = bp_01.check(_context_for("ok_quoted_name"))

    assert result.rule_status == "OK"
    assert result.summary["broken_references"] == 0


def test_a_cycle_broken_by_an_inactive_relationship_is_not_ambiguous():
    # §4.2 — mécanisme normal des relations de rôle (USERELATIONSHIP).
    result = bp_01.check(_context_for("ok_inactive_cycle"))

    assert result.rule_status == "OK"
    assert result.summary["ambiguous_pairs"] == 0


def test_ko_when_a_referenced_column_does_not_exist():
    result = bp_01.check(_context_for("ko_broken_column"))

    assert result.rule_status == "KO"
    assert result.summary["broken_references"] == 1
    ko = [f for f in result.findings if f.status == "KO"]
    assert ko[0].evidence["missing"] == ["D_PRODUCT.CLE_ABSENTE"]
    assert ko[0].location is not None
    assert ko[0].remediation


def test_ko_when_a_referenced_table_does_not_exist():
    result = bp_01.check(_context_for("ko_broken_table"))

    assert result.rule_status == "KO"
    ko = [f for f in result.findings if f.status == "KO"]
    assert ko[0].evidence["missing"] == ["table D_INTROUVABLE"]


def test_ko_when_two_active_paths_reach_the_same_table():
    # §4.2 — Date atteint Sales directement ET via Product. Ambiguïté réelle,
    # qui subsiste en lecture orientée.
    result = bp_01.check(_context_for("ko_ambiguous"))

    assert result.rule_status == "KO"
    assert result.summary["ambiguous_pairs"] == 1
    pair = [f for f in result.findings if f.object_type == "table_pair"][0]
    assert pair.object == "D_DATE -> F_SALES"
    assert result.summary["schema_type"] == "SNOWFLAKE"


def test_cardinality_is_delegated_to_bp03_and_never_sinks_the_status():
    # §1 et §4.3 — un many-to-many est un KO de BP-03. BP-01 le signale en NA
    # délégué, exclu de son statut global : deux KO pour une même cause
    # rendraient le rapport illisible.
    result = bp_01.check(_context_for("na_delegated_m2m"))

    assert result.rule_status == "NA"
    assert result.summary["delegated_to_bp03"] == 1
    assert result.summary["relationships_checked"] == 0
    delegated = [f for f in result.findings if f.status == "NA"]
    assert "BP-03" in delegated[0].reason


def test_na_when_the_model_has_no_relationship():
    # §4.3 — un modèle sans relation n'est pas non conforme.
    result = bp_01.check(_context_for("na_no_relationships"))

    assert result.rule_status == "NA"
    assert result.summary["relationships_total"] == 0


def test_na_when_no_table_is_readable():
    # §4.1 — sans table, l'existence des références est indécidable. Un OK
    # serait un faux OK : la règle n'aurait rien vérifié.
    context = _context_for("ok")
    context.tables = []

    result = bp_01.check(context)

    assert result.rule_status == "NA"
    assert result.execution_status == "ERROR"


def test_schema_type_never_drives_the_status():
    # §9 — la forme du modèle est descriptive. Un flocon conforme reste OK.
    snowflake = bp_01.check(_context_for("ok_inactive_cycle"))

    assert snowflake.summary["schema_type"] in {"STAR", "SNOWFLAKE", "GALAXY"}
    assert snowflake.rule_status == "OK"


def test_every_relationship_is_reported_not_only_the_first():
    # §5 — parcours complet : l'utilisateur doit recevoir tous les constats.
    result = bp_01.check(_context_for("ok_galaxy"))

    assert len([f for f in result.findings if f.object_type == "relationship"]) == 4
