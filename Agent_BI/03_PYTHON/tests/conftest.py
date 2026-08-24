"""Permet `import engine`, `import powerbi`, `import rules` depuis les tests,
quel que soit le répertoire courant depuis lequel pytest est lancé.

`03_PYTHON` n'est pas un nom de package Python valide (commence par un
chiffre) : ce n'est pas un paquet importable, seulement le répertoire racine
d'exécution du moteur (comme le ferait un `src/`). On l'ajoute donc
directement à sys.path plutôt que de le traiter comme un paquet.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
