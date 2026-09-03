"""Tests du contrat JSON versionné (`engine/envelope.py`).

Ces tests protègent ce que des consommateurs externes (pont Node, backend,
pipeline) tiennent pour acquis. Un changement qui les casse est, par
définition, un changement de contrat : il impose de faire évoluer
`SCHEMA_VERSION` et de prévenir les appelants.
"""

import re
from pathlib import Path

from engine.context import AnalysisContext
from engine.envelope import SCHEMA_VERSION, build_envelope, derive_overall_status
from engine.models import RuleResult
from engine.runner import run_rules
from rules.registry import resolve_rules
from version import ENGINE_VERSION

FIXTURES = Path(__file__).parent / "fixtures" / "bp_22"

_RULE_ID_PATTERN = re.compile(r"^BP-\d+$")


def _rule_result(rule_status: str, rule_id: str = "BP-XX") -> RuleResult:
    return RuleResult(
        rule_id=rule_id,
        rule_name="regle de test",
        execution_status="SUCCESS",
        rule_status=rule_status,
    )


def test_envelope_shape_for_a_readable_project():
    # Restreint à BP-22 : ce test porte sur la FORME de l'enveloppe, pas sur
    # l'étendue du catalogue. Le laisser dépendre du nombre de règles
    # implémentées le ferait échouer à chaque nouvelle règle ajoutée.
    context = AnalysisContext.from_semantic_model_path(FIXTURES / "ok")
    envelope = build_envelope(context, run_rules(context, resolve_rules(["BP-22"])))

    assert envelope["schema_version"] == SCHEMA_VERSION
    assert envelope["engine_version"] == ENGINE_VERSION
    assert envelope["project"]["format"] == "PBIP"
    assert envelope["project"]["fingerprint"].startswith("sha256:")
    assert len(envelope["results"]) == 1
    assert envelope["results"][0]["rule_id"] == "BP-22"


def test_envelope_carries_a_consolidated_summary():
    context = AnalysisContext.from_semantic_model_path(FIXTURES / "ko")
    envelope = build_envelope(context, run_rules(context, resolve_rules(["BP-22"])))

    summary = envelope["summary"]
    assert summary["overall_status"] == "KO"
    assert summary["rules_evaluated"] == 1
    assert summary["rules_by_status"] == {"OK": 0, "KO": 1, "NA": 0}
    assert summary["findings_by_status"]["KO"] == 1
    assert summary["findings_by_status"]["OK"] == 1


def test_summary_aggregates_every_implemented_rule():
    # Contrepartie du test ci-dessus : ici on vérifie bien que TOUTES les
    # règles implémentées sont exécutées et comptées.
    context = AnalysisContext.from_semantic_model_path(FIXTURES / "ko")
    results = run_rules(context, resolve_rules())
    envelope = build_envelope(context, results)

    summary = envelope["summary"]
    assert summary["rules_evaluated"] == len(results) > 1
    assert sum(summary["rules_by_status"].values()) == summary["rules_evaluated"]
    assert summary["overall_status"] == "KO"


def test_overall_status_is_ko_as_soon_as_one_rule_is_ko():
    assert derive_overall_status([_rule_result("OK"), _rule_result("KO"), _rule_result("NA")]) == "KO"


def test_overall_status_is_na_when_a_rule_could_not_conclude():
    # Pas de KO, mais une règle n'a pas pu conclure : on ne déclare pas le
    # projet conforme pour autant.
    assert derive_overall_status([_rule_result("OK"), _rule_result("NA")]) == "NA"


def test_overall_status_of_an_empty_analysis_is_na_never_ok():
    # Aucune règle exécutée ne démontre aucune conformité : répondre OK ici
    # serait affirmer une conformité jamais contrôlée.
    assert derive_overall_status([]) == "NA"


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
    # Racine de projet sans aucun dossier *.SemanticModel : à distinguer d'un
    # modèle trouvé mais vide (le consommateur externe doit pouvoir faire la
    # différence).
    context = AnalysisContext.load(tmp_path)
    envelope = build_envelope(context, [])

    assert envelope["project"]["semantic_model_path"] is None
    assert envelope["project"]["fingerprint"] is None


def test_results_are_reproducible_for_the_same_project(bp_22_fixtures):
    # Principe directeur du projet : même projet + mêmes règles => même
    # résultat. Seul `generated_at` peut différer d'une exécution à l'autre.
    def analyse() -> dict:
        context = AnalysisContext.from_semantic_model_path(bp_22_fixtures / "ko")
        return build_envelope(context, run_rules(context, resolve_rules()))

    first, second = analyse(), analyse()

    assert first["results"] == second["results"]
    assert first["summary"] == second["summary"]


def test_generated_at_can_be_frozen_for_reproducible_output(bp_22_fixtures, frozen_moment):
    context = AnalysisContext.from_semantic_model_path(bp_22_fixtures / "ok")
    envelope = build_envelope(context, [], generated_at=frozen_moment)

    assert envelope["generated_at"] == frozen_moment.isoformat()


def test_every_registered_rule_yields_exactly_one_uniquely_identified_result():
    # Contrôle du CONTRAT plutôt que de la liste du moment : un identifiant
    # bien formé et unique par règle enregistrée. Lister les BP-xx attendus
    # en dur obligerait à modifier ce test à chaque nouvelle règle, sans rien
    # vérifier de plus.
    context = AnalysisContext.from_semantic_model_path(FIXTURES / "ok")
    envelope = build_envelope(context, run_rules(context, resolve_rules()))

    rule_ids = [r["rule_id"] for r in envelope["results"]]

    assert len(set(rule_ids)) == len(rule_ids), f"identifiants dupliqués : {rule_ids}"
    for rule_id in rule_ids:
        assert _RULE_ID_PATTERN.match(rule_id), f"identifiant mal formé : {rule_id!r}"


def test_every_registered_rule_returns_a_contractual_status():
    # Le contrat n'autorise que trois statuts métier (cf. README_Agent_BI) :
    # aucun quatrième statut ne doit fuiter dans l'enveloppe, quel que soit
    # le projet analysé.
    context = AnalysisContext.from_semantic_model_path(FIXTURES / "ok")
    envelope = build_envelope(context, run_rules(context, resolve_rules()))

    for result in envelope["results"]:
        assert result["rule_status"] in {"OK", "KO", "NA"}
        assert result["execution_status"] in {"SUCCESS", "ERROR", "PARTIAL"}


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
