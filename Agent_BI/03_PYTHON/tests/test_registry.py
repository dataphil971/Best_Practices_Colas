"""Tests du catalogue des bonnes pratiques.

Le catalogue est la source de vérité de l'état d'avancement du moteur. Ces
tests garantissent qu'il ne peut pas mentir : chaque entrée doit pointer vers
un algorithme réel, et toute nouvelle spécification doit y être déclarée.
"""

from pathlib import Path

import pytest

from errors import UnknownRuleError
from rules.registry import (
    CATALOGUE,
    get_spec,
    implemented_specs,
    planned_specs,
    resolve_rules,
)

ALGORITHMS_DIR = Path(__file__).resolve().parents[2] / "01_ALGORITHMES"
BANNER_MARKER = "> **Statut d'implémentation :"


def test_every_catalogue_entry_points_to_an_existing_algorithm():
    missing = [spec.rule_id for spec in CATALOGUE if not (ALGORITHMS_DIR / spec.algorithm).exists()]

    assert missing == [], f"Algorithmes introuvables pour : {missing}"


def test_every_algorithm_is_declared_in_the_catalogue():
    # Sans ce test, une bonne pratique pourrait être spécifiée puis oubliée :
    # invisible dans `agent-bi rules`, donc jamais planifiée.
    documented = {path.name for path in ALGORITHMS_DIR.glob("*.md")} - {"README.md"}
    declared = {spec.algorithm for spec in CATALOGUE}

    assert documented - declared == set(), "Algorithmes absents du catalogue"


def test_rule_ids_are_unique_and_well_formed():
    rule_ids = [spec.rule_id for spec in CATALOGUE]

    assert len(rule_ids) == len(set(rule_ids))
    for rule_id in rule_ids:
        assert rule_id.startswith("BP-"), f"Identifiant hors convention : {rule_id}"
        assert rule_id[3:].isdigit(), f"Identifiant hors convention : {rule_id}"


def test_algorithm_file_number_matches_the_rule_id():
    # `BP-22` <-> `22_DisableSummarization.md` : la correspondance doit être
    # mécanique, sinon une revue croisée algorithme/code devient impossible.
    for spec in CATALOGUE:
        assert spec.algorithm.startswith(f"{spec.rule_id[3:]}_"), (
            f"{spec.rule_id} ne correspond pas à {spec.algorithm}"
        )


def test_every_algorithm_states_its_implementation_status():
    # La bannière est lue par un humain qui décide de faire confiance — ou non
    # — à un résultat d'analyse. Elle ne doit jamais contredire le moteur.
    expected = {True: "✅ Implémenté", False: "⏳ Non implémenté"}

    for spec in CATALOGUE:
        content = (ALGORITHMS_DIR / spec.algorithm).read_text(encoding="utf-8")
        banner = next((line for line in content.splitlines() if line.startswith(BANNER_MARKER)), None)
        assert banner is not None, f"{spec.rule_id} : bannière de statut absente"
        assert expected[spec.is_implemented] in banner, (
            f"{spec.rule_id} : la bannière contredit le catalogue"
        )


def test_the_algorithms_index_exists_and_is_not_declared_as_a_rule():
    # `README.md` est l'index généré, pas un algorithme : le confondre avec une
    # bonne pratique fausserait le décompte affiché à l'utilisateur.
    index = ALGORITHMS_DIR / "README.md"

    assert index.exists()
    assert "README.md" not in {spec.algorithm for spec in CATALOGUE}


def test_implemented_rules_carry_an_executable_check():
    for spec in implemented_specs():
        assert spec.check is not None, f"{spec.rule_id} est déclarée implémentée sans code"


def test_planned_rules_carry_no_executable_check():
    for spec in planned_specs():
        assert spec.check is None, f"{spec.rule_id} est déclarée non implémentée mais a du code"


def test_default_resolution_only_returns_implemented_rules():
    assert len(resolve_rules()) == len(implemented_specs())


def test_a_rule_can_be_resolved_by_its_historic_alias():
    assert get_spec("SEM-001").rule_id == "BP-22"


def test_resolving_an_unknown_rule_is_an_error():
    with pytest.raises(UnknownRuleError):
        resolve_rules(["BP-99"])


def test_resolving_a_planned_rule_is_an_error_not_a_silent_skip():
    # Demander une règle non implémentée et recevoir un rapport vide ferait
    # croire à une conformité jamais contrôlée.
    planned = planned_specs()[0]

    with pytest.raises(UnknownRuleError, match="pas encore implémentée"):
        resolve_rules([planned.rule_id])
