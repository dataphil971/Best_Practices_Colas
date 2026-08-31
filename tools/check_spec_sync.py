"""Garde-fou déterministe : le .md d'algorithme change avant le .py de règle.

Le dépôt pose la règle dans chaque `bp_NN.py` : « toute évolution de la logique
OK/KO/NA doit d'abord être répercutée dans ce document ». Cette règle était
jusqu'ici une convention en prose, que rien ne faisait respecter — elle a déjà
été enfreinte (sémantique de BP-15 modifiée dans le code avant son algorithme).

Le contrôle est en Python et non en skill : `agent-bi-skill-creator` classe
DETERMINISTE toute capacité dont l'information est explicitement disponible,
dont la même entrée produit toujours le même résultat, et dont les conditions
sont objectives. Les trois sont vraies ici.

La décision (`evaluate`) est séparée de la plomberie git (`check`) pour être
testable sans dépôt : un contrôle qui ne peut être mis en échec dans un test
ne prouve rien.

Usage :
    python tools/check_spec_sync.py [BASE_REF]

Sortie : 0 si cohérent, 1 sinon. Destiné à un hook pre-commit et à la CI.
"""

import re
import subprocess
import sys
from collections.abc import Callable, Iterable
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RULE_PATTERN = re.compile(r"(?:^|/)Agent_BI/03_PYTHON/rules/bp_(\d+)\.py$")
ALGO_DIR = "Agent_BI/01_ALGORITHMES"

# Un changement qui ne touche aucun de ces marqueurs ne peut pas modifier la
# sémantique OK/KO/NA : renommage, commentaire, reformulation de message.
SEMANTIC_MARKERS = (
    "status=",
    "rule_status",
    "out_of_scope",
    "execution_status",
    "return Finding",
    '"NA"',
    '"KO"',
    '"OK"',
)


def evaluate(
    changed_files: Iterable[str],
    algo_lookup: Callable[[str], str | None],
    touches_semantics: Callable[[str], bool],
) -> list[str]:
    """Décision pure : quelles règles ont bougé sans leur algorithme ?

    `algo_lookup(numéro)` rend le chemin du .md attendu, ou None s'il n'existe
    pas. `touches_semantics(chemin)` dit si le diff du fichier touche une ligne
    portant un marqueur sémantique.
    """
    changed = list(changed_files)
    problems = []

    for path in changed:
        match = RULE_PATTERN.search(path)
        if match is None:
            continue
        rule_number = match.group(1)
        algo_path = algo_lookup(rule_number)

        if algo_path is None:
            problems.append(f"BP-{rule_number} : aucun algorithme {ALGO_DIR}/{rule_number}_*.md")
            continue
        if algo_path in changed:
            continue
        if not touches_semantics(path):
            continue

        problems.append(
            f"BP-{rule_number} : {path} modifie la logique OK/KO/NA sans que "
            f"{algo_path} soit modifié. L'algorithme est la référence "
            f"fonctionnelle : le mettre à jour d'abord."
        )
    return problems


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True).stdout


def _algo_for(rule_number: str) -> str | None:
    matches = sorted((REPO_ROOT / ALGO_DIR).glob(f"{rule_number}_*.md"))
    return f"{ALGO_DIR}/{matches[0].name}" if matches else None


def _touches_semantics(path: str, base_ref: str) -> bool:
    diff = _git("diff", "--unified=0", base_ref, "--", path)
    changed_lines = [
        line
        for line in diff.splitlines()
        if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
    ]
    return any(marker in line for line in changed_lines for marker in SEMANTIC_MARKERS)


def check(base_ref: str = "HEAD") -> list[str]:
    return evaluate(
        _git("diff", "--name-only", base_ref).splitlines(),
        _algo_for,
        lambda path: _touches_semantics(path, base_ref),
    )


def main() -> int:
    base_ref = sys.argv[1] if len(sys.argv) > 1 else "HEAD"
    problems = check(base_ref)
    if not problems:
        print("Spec sync : OK - aucune regle modifiee sans son algorithme.")
        return 0
    print("Spec sync : INCOHERENT\n")
    for problem in problems:
        print(f"  - {problem}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
