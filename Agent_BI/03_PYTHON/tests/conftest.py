"""Configuration commune des tests Agent BI.

Permet `import engine`, `import powerbi`, `import rules` depuis les tests,
quel que soit le répertoire courant depuis lequel pytest est lancé.

`03_PYTHON` n'est pas un nom de package Python valide (commence par un
chiffre) : ce n'est pas un paquet importable, seulement le répertoire racine
d'exécution du moteur (comme le ferait un `src/`). On l'ajoute donc
directement à sys.path plutôt que de le traiter comme un paquet.
"""

import shutil
import sys
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

FIXTURES_ROOT = Path(__file__).parent / "fixtures"

# Horodatage figé : permet d'affirmer qu'une enveloppe est reproductible
# octet pour octet, ce qu'un `datetime.now()` rendrait impossible.
FROZEN_MOMENT = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def bp_22_fixtures() -> Path:
    """Racine des fixtures TMDL de BP-22 (`ok/`, `ko/`, `na/`)."""
    return FIXTURES_ROOT / "bp_22"


@pytest.fixture
def frozen_moment() -> datetime:
    """Horodatage figé, pour comparer des enveloppes octet pour octet."""
    return FROZEN_MOMENT


@pytest.fixture
def pbip_project(tmp_path: Path, bp_22_fixtures: Path) -> Callable[[str], Path]:
    """Fabrique une vraie racine de projet PBIP à partir d'un scénario de fixture.

    Les fixtures `bp_22/{ok,ko,na}/` sont des *dossiers de modèle sémantique* :
    elles se prêtent aux tests de règle, qui appellent
    `AnalysisContext.from_semantic_model_path`. L'API, elle, part d'une racine
    de projet et cherche un dossier `*.SemanticModel` — la tester sur la
    fixture brute reviendrait à tester un projet vide.
    """

    def build(scenario: str, name: str = "MyProject") -> Path:
        root = tmp_path / scenario / name
        shutil.copytree(bp_22_fixtures / scenario, root / f"{name}.SemanticModel")
        return root

    return build
