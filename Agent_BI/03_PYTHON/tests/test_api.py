"""Tests de l'API programmatique (`analyze_project`).

C'est le point d'entrée que partagent `main.py`, le pont Node
(`05_NODE/services/python-runner.js`) et le backend : ce qui est vérifié ici
vaut pour les trois.
"""

import pytest

from engine import analyze_project
from errors import ProjectNotFoundError, UnknownRuleError


def test_analyze_project_returns_a_versioned_envelope(bp_22_fixtures):
    # Les fixtures BP-22 exposent des dossiers de scénario (`ok/`, `ko/`,
    # `na/`), sans `*.SemanticModel` : l'analyse aboutit quand même, avec un
    # verdict NA — c'est le comportement attendu, pas une erreur.
    envelope = analyze_project(bp_22_fixtures)

    assert envelope["schema_version"]
    assert envelope["engine_version"]
    assert envelope["project"]["format"] == "PBIP"
    assert envelope["summary"]["overall_status"] == "NA"


def test_analyze_project_rejects_a_missing_path(tmp_path):
    with pytest.raises(ProjectNotFoundError, match="n'existe pas"):
        analyze_project(tmp_path / "inexistant")


def test_analyze_project_rejects_a_file_path(tmp_path):
    file_path = tmp_path / "projet.pbip"
    file_path.write_text("", encoding="utf-8")

    with pytest.raises(ProjectNotFoundError, match="n'est pas un dossier"):
        analyze_project(file_path)


def test_analyze_project_rejects_an_unknown_rule(bp_22_fixtures):
    with pytest.raises(UnknownRuleError):
        analyze_project(bp_22_fixtures, rule_ids=["BP-99"])


def test_analyze_project_reads_a_real_pbip_layout(tmp_path):
    project = tmp_path / "MyProject"
    tables = project / "MyProject.SemanticModel" / "definition" / "tables"
    tables.mkdir(parents=True)
    (tables / "D_TEST.tmdl").write_text(
        "table D_TEST\n\tcolumn ID\n\t\tsummarizeBy: none\n", encoding="utf-8"
    )

    # Restreint à BP-22 : sur un modèle aussi minimal, les autres règles
    # concluent légitimement NA faute de matière, ce qui rendrait le verdict
    # global NA sans rien dire de la lecture du projet — l'objet du test.
    envelope = analyze_project(project, rule_ids=["BP-22"])

    assert envelope["project"]["name"] == "MyProject"
    assert envelope["summary"]["overall_status"] == "OK"
    assert envelope["project"]["fingerprint"].startswith("sha256:")


def test_generated_at_is_reproducible_when_frozen(tmp_path, frozen_moment):
    project = tmp_path / "MyProject"
    (project / "MyProject.SemanticModel" / "definition" / "tables").mkdir(parents=True)

    envelope = analyze_project(project, generated_at=frozen_moment)

    assert envelope["generated_at"] == frozen_moment.isoformat()
