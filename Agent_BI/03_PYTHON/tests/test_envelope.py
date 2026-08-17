"""Tests du contrat JSON versionné (`engine/envelope.py`)."""

from pathlib import Path

from engine.context import AnalysisContext
from engine.envelope import ENGINE_VERSION, SCHEMA_VERSION, build_envelope
from engine.runner import run_rules
from rules.registry import ALL_RULES

FIXTURES = Path(__file__).parent / "fixtures" / "bp_22"


def test_envelope_shape_for_a_readable_project():
    context = AnalysisContext.from_semantic_model_path(FIXTURES / "ok")
    envelope = build_envelope(context, run_rules(context, ALL_RULES))

    assert envelope["schema_version"] == SCHEMA_VERSION
    assert envelope["engine_version"] == ENGINE_VERSION
    assert envelope["project"]["format"] == "PBIP"
    assert envelope["project"]["fingerprint"].startswith("sha256:")
    assert len(envelope["results"]) == 1
    assert envelope["results"][0]["rule_id"] == "BP-22"


def test_project_name_is_derived_from_the_semantic_model_folder():
    context = AnalysisContext.from_semantic_model_path(FIXTURES / "ok")
    envelope = build_envelope(context, [])

    # Le dossier de fixture s'appelle "ok", pas "*.SemanticModel" : le nom
    # dérivé doit rester "ok" tel quel (pas de suffixe à retirer).
    assert envelope["project"]["name"] == "ok"


def test_fingerprint_is_none_when_no_table_was_read(tmp_path):
    empty_semantic_model = tmp_path / "Empty.SemanticModel"
    (empty_semantic_model / "definition" / "tables").mkdir(parents=True)

    context = AnalysisContext.from_semantic_model_path(empty_semantic_model)
    envelope = build_envelope(context, [])

    assert envelope["project"]["fingerprint"] is None
    assert envelope["project"]["name"] == "Empty"


def test_fingerprint_is_stable_across_two_reads_of_the_same_project():
    first = AnalysisContext.from_semantic_model_path(FIXTURES / "ok").fingerprint
    second = AnalysisContext.from_semantic_model_path(FIXTURES / "ok").fingerprint

    assert first == second


def test_project_block_reports_missing_semantic_model_explicitly(tmp_path):
    # Racine de projet sans aucun dossier *.SemanticModel : à distinguer
    # d'un modèle trouvé mais vide (cf. rapport d'intégration : le
    # consommateur externe doit pouvoir faire la différence).
    context = AnalysisContext.load(tmp_path)
    envelope = build_envelope(context, [])

    assert envelope["project"]["semantic_model_path"] is None
    assert envelope["project"]["fingerprint"] is None
