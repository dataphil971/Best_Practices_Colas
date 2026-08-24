---
applyTo: "Agent_BI/01_ALGORITHMES/**"
---

# Revue des algorithmes Agent BI (BP-NN)

Ces fichiers définissent les bonnes pratiques Power BI contrôlées par Agent BI. Ils font foi : `Agent_BI/03_PYTHON/` doit s'y conformer, pas l'inverse.

Lors d'une revue ou d'une proposition de modification, vérifier strictement :

- **Statuts** : uniquement `OK`, `KO`, `NA` dans `rule_status`. Rejeter tout `WARN`, `WARNING`, `PARTIEL`, `NON_EVALUE` ou 4e statut. `NA` ne doit jamais être utilisé comme synonyme de `KO` (absence de preuve ≠ non-conformité démontrée), et inversement une vraie non-conformité détectée ne doit jamais être diluée en `NA`.
- **Structure minimale** : Objectif, Emplacement des fichiers concernés, Propriété(s) à contrôler, Règle(s) d'évaluation, Parcours complet du modèle, Pseudo-code, Calcul du statut global, Structure du résultat, Message présenté à l'utilisateur, Conditions empêchant un faux OK, Résumé.
- **Preuve obligatoire** : tout `KO` doit être justifiable par Rule ID / Object / Expected / Actual / Evidence.
- **Identifiant** : `BP-NN` (deux chiffres), jamais `SM-XXX-001`/`RP-XXX-001`.
- **Cohérence croisée** : si une règle délègue un cas à une autre BP (ex. « délégué à BP-03 »), vérifier que la BP cible traite bien ce cas en retour.

Signaler explicitement toute violation de ces points plutôt que de la corriger silencieusement dans la review.
