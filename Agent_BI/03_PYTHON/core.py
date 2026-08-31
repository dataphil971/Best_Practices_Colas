"""Types et constantes transverses du moteur Agent BI.

Ce module ne contient aucune logique : uniquement le vocabulaire partagé par
l'ensemble des couches (moteur, règles, restitution). Il joue le même rôle que
`pytoolbox.core` dans la PyToolBox.
"""

from typing import Final, Literal, TypeAlias

RuleStatus: TypeAlias = Literal["OK", "KO", "NA"]
"""Statut métier d'un contrôle.

- `OK` : la conformité est démontrée ;
- `KO` : la non-conformité est démontrée ;
- `NA` : les informations disponibles ne permettent pas de conclure.

`NA` n'est jamais un synonyme de `KO` : l'absence de preuve ne vaut pas
non-conformité. Aucun autre statut (`WARN`, `INFO`, ...) n'est autorisé.
"""

ExecutionStatus: TypeAlias = Literal["SUCCESS", "PARTIAL", "ERROR"]
"""Statut technique d'exécution d'une règle, indépendant du statut métier.

Une règle peut s'exécuter parfaitement (`SUCCESS`) et conclure `KO` : ce sont
deux dimensions distinctes, à ne jamais confondre.
"""

RuleScope: TypeAlias = Literal["SEMANTIC_MODEL", "REPORT", "CROSS"]
"""Périmètre analysé par une règle.

- `SEMANTIC_MODEL` : le modèle sémantique seul (TMDL) ;
- `REPORT` : le rapport seul (PBIR / JSON) ;
- `CROSS` : les deux sont nécessaires pour conclure (ex. une colonne du modèle
  jugée inutilisée uniquement si aucun visuel du rapport ne la référence).

Le périmètre n'est pas encodé dans l'identifiant `BP-NN` : il se déduit de la
section « Emplacement des fichiers concernés » de l'algorithme.
"""

ImplementationStatus: TypeAlias = Literal["IMPLEMENTED", "PLANNED"]
"""État d'implémentation d'une bonne pratique.

- `IMPLEMENTED` : la règle est codée, testée et exécutable par le moteur ;
- `PLANNED` : l'algorithme fonctionnel existe, le code non. La règle n'est pas
  « désactivée » au sens métier, elle n'existe simplement pas encore.
"""

RULE_STATUSES: Final[tuple[RuleStatus, ...]] = ("OK", "KO", "NA")
EXECUTION_STATUSES: Final[tuple[ExecutionStatus, ...]] = ("SUCCESS", "PARTIAL", "ERROR")

SEMANTIC_MODEL_SUFFIX: Final[str] = ".SemanticModel"
REPORT_SUFFIX: Final[str] = ".Report"
