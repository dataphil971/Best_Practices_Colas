"""Tests du contrat JSON versionné (`engine/envelope.py`)."""

import re
from pathlib import Path

from engine.context import AnalysisContext
from engine.envelope import ENGINE_VERSION, SCHEMA_VERSION, build_envelope
from engine.runner import run_rules
from rules.registry import ALL_RULES

FIXTURES = Path(__file__).parent / "fixtures" / "bp_22"

_RULE_ID_PATTERN = re.compile(r"^BP-\d+$")


def test_envelope_shape_for_a_readable_project():
    context = AnalysisContext.from_semantic_model_path(FIXTURES / "ok")
    envelope = build_envelope(context, run_rules(context, ALL_RULES))

    assert envelope["schema_version"] == SCHEMA_VERSION
    assert envelope["engine_version"] == ENGINE_VERSION
    assert envelope["project"]["format"] == "PBIP"
    assert envelope["project"]["fingerprint"].startswith("sha256:")
    assert len(envelope["results"]) == len(ALL_RULES)


def test_every_registered_rule_yields_exactly_one_uniquely_identified_result():
    # Contrôle du CONTRAT plutôt que de la liste du moment : un identifiant
    # bien formé et unique par règle enregistrée. Lister les BP-xx attendus
    # en dur obligerait à modifier ce test à chaque nouvelle règle, sans rien
    # vérifier de plus que `len(results) == len(ALL_RULES)` ci-dessus.
    context = AnalysisContext.from_semantic_model_path(FIXTURES / "ok")
    envelope = build_envelope(context, run_rules(context, ALL_RULES))

    rule_ids = [r["rule_id"] for r in envelope["results"]]

    assert len(set(rule_ids)) == len(rule_ids), f"identifiants dupliqués : {rule_ids}"
    for rule_id in rule_ids:
        assert _RULE_ID_PATTERN.match(rule_id), f"identifiant mal formé : {rule_id!r}"


def test_every_registered_rule_returns_a_contractual_status():
    # Le contrat n'autorise que trois statuts métier (cf. README_Agent_BI) :
    # aucun quatrième statut ne doit fuiter dans l'enveloppe, quel que soit
    # le projet analysé.
    context = AnalysisContext.from_semantic_model_path(FIXTURES / "ok")
    envelope = build_envelope(context, run_rules(context, ALL_RULES))

    for result in envelope["results"]:
        assert result["rule_status"] in {"OK", "KO", "NA"}
        assert result["execution_status"] in {"SUCCESS", "ERROR", "PARTIAL"}


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


def test_load_tolerates_a_path_pointing_directly_at_the_semantic_model(tmp_path):
    # Erreur d'usage courante : pointer sur `<Nom>.SemanticModel` lui-même
    # plutôt que sur la racine du projet PBIP qui le contient. Sans repli,
    # chaque règle renvoie NA quel que soit le contenu du modèle — un chemin
    # incorrect se fait alors passer pour un moteur cassé.
    semantic_model = tmp_path / "Fixture.SemanticModel"
    (semantic_model / "definition" / "tables").mkdir(parents=True)

    context = AnalysisContext.load(semantic_model)
    envelope = build_envelope(context, [])

    assert envelope["project"]["semantic_model_path"] == str(semantic_model)
    assert envelope["project"]["project_path"] == str(tmp_path)


def test_load_does_not_mistake_an_unrelated_folder_ending_in_semanticmodel(tmp_path):
    # Le nom seul ne suffit pas : sans `definition/tables`, ce n'est pas un
    # modèle sémantique valide, seulement un dossier nommé par coïncidence.
    fake = tmp_path / "NotReally.SemanticModel"
    fake.mkdir()

    context = AnalysisContext.load(fake)
    envelope = build_envelope(context, [])

    assert envelope["project"]["semantic_model_path"] is None
