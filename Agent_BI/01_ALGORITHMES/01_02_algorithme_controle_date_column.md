# SEM-002 — Document historique redirigé vers BP-02

> **Statut : OBSOLÈTE / NON CANONIQUE**
>
> Ce fichier est conservé uniquement pour préserver l'historique du projet.

La règle canonique correspondant à `SEM-002` est désormais :

```text
02_DateTable.md
```

L'ancienne version imposait notamment un nom de fichier/table très spécifique (`D_DATES.tmdl`) et une colonne `DATE`. La version canonique est volontairement plus générique : elle recherche une table de dates à partir de plusieurs signaux (nom, propriétés, colonnes de type date, relations) au lieu de dépendre d'un nom unique.

## Principe

```text
1 Rule ID -> 1 algorithme canonique -> 1 checker -> 1 suite de tests
```

Utiliser exclusivement :

```text
Agent_BI/01_ALGORITHMES/02_DateTable.md
```
