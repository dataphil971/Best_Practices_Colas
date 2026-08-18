"""Registre des règles Agent BI actuellement implémentées.

Ajouter une règle ici la rend exécutable par `main.py`. Une règle absente
du registre n'est pas "désactivée" au sens métier : elle n'existe
simplement pas encore côté Python (cf. Cycle de vie d'une bonne pratique
du README — l'algorithme peut exister sans implémentation).
"""

from rules import bp_22

ALL_RULES = [
    bp_22.check,
]
