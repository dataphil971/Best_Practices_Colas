"""Point d'entrée du moteur Agent BI.

Appelé par `run-agent.ps1` (cf. section « Lancement » du README) et par le
serveur Node (`05_NODE/services/python-runner.js`) :

    python main.py <chemin_projet_pbip>

`<chemin_projet_pbip>` est la racine du projet PBIP, c'est-à-dire le dossier
contenant `<Nom>.SemanticModel/` (et, le cas échéant, `<Nom>.Report/`).

Le contrat d'appel est FIGÉ : un seul argument positionnel, l'enveloppe JSON
sur la sortie standard, rien d'autre. Le serveur Node parse cette sortie
telle quelle ; toute ligne supplémentaire sur stdout la rendrait illisible.
Les messages d'erreur vont donc sur stderr, jamais sur stdout.

Codes de sortie :

| Code | Signification                                                     |
|------|-------------------------------------------------------------------|
| `0`  | L'analyse a produit un résultat structuré (même avec des `KO`).    |
| `2`  | L'analyse n'a pas pu être menée (chemin invalide, règle inconnue). |

Un `rule_status = KO` est un résultat métier valide, pas une erreur
d'exécution : l'appelant ne doit pas le confondre avec un crash. Le code de
sortie reste donc `0` dès lors que le moteur a produit un résultat structuré
pour chaque règle.
"""

import argparse
import json
import sys

from engine.api import analyze_project
from errors import AgentBIError

EXIT_SUCCESS = 0
EXIT_ERROR = 2


def main(argv=None) -> int:
    # Le terminal Windows n'utilise pas UTF-8 par défaut : sans ce
    # reconfigure, les accents des messages (français) seraient mal
    # encodés dans la sortie, pas seulement mal affichés.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="Agent BI - moteur d'analyse de bonnes pratiques Power BI (PBIP)",
    )
    parser.add_argument(
        "project_path",
        help="Chemin vers la racine du projet PBIP (dossier contenant *.SemanticModel)",
    )
    args = parser.parse_args(argv)

    try:
        envelope = analyze_project(args.project_path)
    except AgentBIError as error:
        # Erreur d'usage (chemin inexistant, règle inconnue) : diagnostic
        # lisible sur stderr et code non nul, plutôt qu'une trace Python que
        # l'appelant devrait interpréter.
        print(f"Erreur : {error}", file=sys.stderr)
        return EXIT_ERROR

    print(json.dumps(envelope, indent=2, ensure_ascii=False))
    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(main())
