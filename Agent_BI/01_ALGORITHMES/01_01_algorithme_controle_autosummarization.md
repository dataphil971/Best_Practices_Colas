# SEM-001 — Document historique redirigé vers BP-22

> **Statut : OBSOLÈTE / NON CANONIQUE**
>
> Ce fichier est conservé uniquement pour préserver l'historique du projet. Il ne doit plus être utilisé comme définition fonctionnelle active d'une règle Agent BI.

La règle canonique correspondant à `SEM-001` est désormais :

```text
22_DisableSummarization.md
```

## Pourquoi cette redirection ?

Ce document et `22_DisableSummarization.md` décrivaient le même contrôle : vérifier, pour chaque colonne du modèle sémantique, que la propriété TMDL est configurée ainsi :

```tmdl
summarizeBy: none
```

Maintenir deux définitions actives pour un même identifiant de règle introduit un risque de divergence entre l'algorithme, l'implémentation Python, les tests et les résultats d'audit.

Agent BI applique donc :

```text
1 Rule ID
   |
   v
1 algorithme canonique
   |
   v
1 checker Python
   |
   v
1 suite de tests
```

## Référence active

Utiliser exclusivement :

```text
Agent_BI/01_ALGORITHMES/22_DisableSummarization.md
```

La logique canonique reste :

```text
summarizeBy: none
    -> OK

summarizeBy présent avec une autre valeur
    -> KO

summarizeBy absent, vide, illisible ou inconnu
    -> NA
```

`SummarizationSetBy` est informatif uniquement et ne participe jamais au verdict.
