"""Version du moteur, exposée dans l'enveloppe JSON sous `engine_version`.

Source de vérité unique du numéro de version. Ne jamais dupliquer un numéro en
dur ailleurs — un consommateur externe (serveur Node de `05_NODE`, frontend)
doit pouvoir se fier à `engine_version`.

Ce dépôt exécute le moteur DEPUIS LES SOURCES (`python main.py`), sans
packaging : il n'y a ni `pyproject.toml` ni distribution installée d'où lire la
version. Le numéro est donc porté ici, et non déduit de métadonnées absentes.
C'est la seule divergence assumée avec le dépôt Azure DevOps
(`BIPowerBI-Review_Agent`), où le même module lit `pyproject.toml`.

`ENGINE_VERSION` est indépendant de `SCHEMA_VERSION` (cf. `engine/envelope.py`) :
le moteur peut évoluer sans que la forme de l'enveloppe change.
"""

from typing import Final

ENGINE_VERSION: Final[str] = "1.0.0"
