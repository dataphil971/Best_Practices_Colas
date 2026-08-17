"""Point d'entrée du moteur Agent BI.

Appelé par `run-agent.ps1` (cf. section « Lancement » du README) :

    python main.py <chemin_projet_pbip>

`<chemin_projet_pbip>` est la racine du projet PBIP, c'est-à-dire le dossier
contenant `<Nom>.SemanticModel/` (et, le cas échéant, `<Nom>.Report/`).
"""

import argparse
import json
import sys
from pathlib import Path

from engine.context import AnalysisContext
from engine.runner import run_rules
from rules.registry import ALL_RULES


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Agent BI - moteur d'analyse de bonnes pratiques Power BI (PBIP)",
    )
    parser.add_argument(
        "project_path",
        help="Chemin vers la racine du projet PBIP (dossier contenant *.SemanticModel)",
    )
    args = parser.parse_args(argv)

    context = AnalysisContext.load(Path(args.project_path))
    results = run_rules(context, ALL_RULES)

    # Le terminal Windows n'utilise pas UTF-8 par défaut : sans ce
    # reconfigure, les accents des messages (français) seraient mal
    # encodés dans la sortie, pas seulement mal affichés.
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps([result.to_dict() for result in results], indent=2, ensure_ascii=False))

    return 1 if any(result.rule_status == "KO" for result in results) else 0


if __name__ == "__main__":
    sys.exit(main())
