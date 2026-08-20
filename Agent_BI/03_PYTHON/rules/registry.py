"""Registre des règles Agent BI actuellement implémentées.

Ajouter une règle ici la rend exécutable par `main.py`. Une règle absente
du registre n'est pas "désactivée" au sens métier : elle n'existe
simplement pas encore côté Python (cf. Cycle de vie d'une bonne pratique
du README — l'algorithme peut exister sans implémentation).
"""

from rules import (
    bp_03, bp_07, bp_09, bp_10, bp_11, bp_15,
    bp_17, bp_21, bp_22, bp_25, bp_32, bp_37, bp_38, bp_39, bp_41,
)

ALL_RULES = [
    bp_03.check,
    bp_07.check,
    bp_09.check,
    bp_10.check,
    bp_11.check,
    bp_15.check,
    bp_17.check,
    bp_21.check,
    bp_22.check,
    bp_25.check,
    bp_32.check,
    bp_37.check,
    bp_38.check,
    bp_39.check,
    bp_41.check,
]
