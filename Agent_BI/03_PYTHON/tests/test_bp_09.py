"""Tests de non-régression pour BP-09.

Scénarios alignés sur Agent_BI/01_ALGORITHMES/09_DisableAutoDateTime.md :
si un de ces tests doit changer, l'algorithme doit changer en premier.
"""

from pathlib import Path

from engine.context import AnalysisContext
from rules import bp_09

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "bp_09"


def _context_for(scenario: str) -> AnalysisContext:
    return AnalysisContext.from_semantic_model_path(FIXTURES / scenario)


def test_ok_when_annotation_is_explicitly_zero():
    result = bp_09.check(_context_for("ok"))

    assert result.rule_status == "OK"
    assert result.execution_status == "SUCCESS"
    assert result.summary["raw_value"] == "0"


def test_ko_when_annotation_is_explicitly_one():
    result = bp_09.check(_context_for("ko"))

    assert result.rule_status == "KO"
    assert result.summary["raw_value"] == "1"


def test_na_when_annotation_is_absent_from_an_existing_model_file():
    # L'absence de l'annotation ne doit JAMAIS être interprétée comme
    # "activé" (§4, "Pourquoi l'absence donne NA") : le fichier existe et
    # d'autres annotations y sont bien lues, seule celle-ci manque.
    result = bp_09.check(_context_for("na_absent"))

    assert result.rule_status == "NA"
    assert result.summary["annotation_found"] is False


def test_na_when_model_tmdl_is_absent():
    result = bp_09.check(_context_for("na_no_model"))

    assert result.rule_status == "NA"
    assert result.execution_status == "ERROR"


def test_na_when_annotation_value_is_not_a_recognized_flag(tmp_path):
    semantic_model = tmp_path / "T.SemanticModel"
    (semantic_model / "definition" / "tables").mkdir(parents=True)
    (semantic_model / "definition" / "model.tmdl").write_text(
        "model Model\n\tculture: fr-FR\n\nannotation __PBI_TimeIntelligenceEnabled = true\n",
        encoding="utf-8",
    )

    result = bp_09.check(AnalysisContext.from_semantic_model_path(semantic_model))

    # "true" n'est pas une des deux valeurs contractuellement démontrées
    # (§6) : le moteur ne doit pas deviner qu'elle signifie "activé".
    assert result.rule_status == "NA"


def test_ignores_annotations_nested_under_another_block(tmp_path):
    # Un export réel place les annotations du modèle À LA RACINE du fichier
    # (profondeur 0), au même niveau que `model <Nom>` et `ref table <Nom>` —
    # jamais imbriquées sous ces blocs (confirmé sur un export PBIP réel,
    # AI_BAROMETER_BI-CDS.SemanticModel). Une annotation de même nom mais
    # indentée sous un autre bloc (ex. `ref table`) appartient à CE bloc, pas
    # au modèle, et ne doit jamais être confondue avec la vraie.
    semantic_model = tmp_path / "T.SemanticModel"
    (semantic_model / "definition" / "tables").mkdir(parents=True)
    (semantic_model / "definition" / "model.tmdl").write_text(
        "model Model\n"
        "\tculture: fr-FR\n"
        "\n"
        "annotation __PBI_TimeIntelligenceEnabled = 0\n"
        "\n"
        "ref table D_AUTRE\n"
        "\tannotation __PBI_TimeIntelligenceEnabled = 1\n",
        encoding="utf-8",
    )

    result = bp_09.check(AnalysisContext.from_semantic_model_path(semantic_model))

    assert result.rule_status == "OK"
