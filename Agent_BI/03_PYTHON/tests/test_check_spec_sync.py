"""Tests du garde-fou `tools/check_spec_sync.py`.

Un contrôle qu'on ne sait pas mettre en échec ne prouve rien : chaque test
vérifie d'abord que le contrôle DÉTECTE, avant de vérifier qu'il se tait.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[3] / "tools" / "check_spec_sync.py"
RULE = "Agent_BI/03_PYTHON/rules/bp_15.py"
ALGO = "Agent_BI/01_ALGORITHMES/15_QueryFolding.md"


def _load():
    spec = importlib.util.spec_from_file_location("check_spec_sync", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_spec_sync"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def mod():
    return _load()


def _algo(_number: str) -> str:
    return ALGO


def test_regle_modifiee_sans_algorithme_est_signalee(mod):
    """Le cas réellement survenu : sémantique de BP-15 changée dans le code seul."""
    problems = mod.evaluate([RULE], _algo, lambda _path: True)
    assert len(problems) == 1
    assert "BP-15" in problems[0]
    assert ALGO in problems[0]


def test_regle_et_algorithme_modifies_ensemble_passent(mod):
    assert mod.evaluate([RULE, ALGO], _algo, lambda _path: True) == []


def test_changement_non_semantique_passe(mod):
    """Renommage, commentaire, message : rien qui touche OK/KO/NA."""
    assert mod.evaluate([RULE], _algo, lambda _path: False) == []


def test_algorithme_absent_est_signale(mod):
    problems = mod.evaluate([RULE], lambda _number: None, lambda _path: True)
    assert len(problems) == 1
    assert "aucun algorithme" in problems[0]


def test_fichiers_hors_regles_sont_ignores(mod):
    autres = [
        "Agent_BI/03_PYTHON/powerbi/tmdl_parser.py",
        "Agent_BI/03_PYTHON/test/rules/test_bp_15.py",
        "README.md",
    ]
    assert mod.evaluate(autres, _algo, lambda _path: True) == []


def test_plusieurs_regles_produisent_plusieurs_constats(mod):
    bp_11 = "Agent_BI/03_PYTHON/rules/bp_11.py"
    problems = mod.evaluate([RULE, bp_11], _algo, lambda _path: True)
    assert len(problems) == 2


def test_marqueurs_semantiques_couvrent_les_emissions_de_statut(mod):
    """Les marqueurs doivent attraper une ligne qui émet réellement un statut."""
    ligne = '+        return Finding(rule_id=RULE_ID, status="NA", reason="...")'
    assert any(marker in ligne for marker in mod.SEMANTIC_MARKERS)
