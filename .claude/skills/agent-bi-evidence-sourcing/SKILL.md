---
name: agent-bi-evidence-sourcing
description: Fonder toute affirmation sur un format Power BI (TMDL, PBIR, PBIP, legacy, M, DAX) sur une source faisant autorité, et la citer. À utiliser avant d'écrire un parseur, un algorithme BP-XX ou une fixture, et chaque fois qu'une propriété PBIP est supposée plutôt que constatée.
---

# Agent BI Evidence Sourcing

## Mission

Un algorithme BP-XX affirme des faits sur un format de fichier : « la propriété
`summarizeBy` vaut `none` par défaut », « un filtre de page vit dans
`page.json` », « `sourceColumn: [Value1]` désigne la première colonne du
constructeur DAX ».

Chacune de ces phrases est soit **sourcée**, soit **devinée**. Ce skill impose
la première.

`agent-bi-rule-engineer` pose l'interdit — « ne jamais inventer une propriété
Power BI ». Ce skill fournit la procédure qui le rend applicable.

## Pourquoi

Un fait deviné qui se trouve être vrai sur le projet de test produit exactement
le même résultat qu'un fait sourcé — jusqu'au projet suivant. Le parseur de
rapport legacy de ce dépôt a été écrit par rétro-ingénierie d'un `report.json`
réel, sans spécification : il fonctionne sur les rapports observés, et rien ne
garantit qu'il fonctionne sur les autres.

Le coût d'un fait faux n'est pas un bug, c'est un **verdict faux** : une règle
qui lit la mauvaise propriété rend `OK` ou `KO` avec le même aplomb.

## Déroulé

```text
DETECTER  →  SOURCER  →  IMPLEMENTER  →  CITER
```

### 1. Détecter la version et la sérialisation

Avant toute affirmation, établir de quoi on parle :

```text
sérialisation du modèle    TMDL (definition/) | TMSL (model.bim)
sérialisation du rapport   PBIR (definition/) | legacy (report.json racine)
version                    definition/version.json, definition.pbir
```

Ces variantes n'ont pas les mêmes propriétés aux mêmes endroits. Une
affirmation valable en PBIR peut être fausse en legacy (cf.
`Agent_BI/04_DOCS/FORMATS_PBIP.md`).

Ne jamais supposer la sérialisation : la lire.

### 2. Chercher la source

Hiérarchie d'autorité, du plus fiable au moins fiable :

```text
1. Documentation Microsoft Learn         (TMDL, PBIR, PBIP, TOM, M, DAX)
2. Schéma JSON publié                    (schema.json référencé par le fichier)
3. Spécification de format Microsoft     (release notes, blog Power BI officiel)
4. Fichier PBIP réel produit par Power BI Desktop, version connue
5. Outil tiers reconnu (Tabular Editor, pbi-tools), à titre corroborant
```

Ne pas utiliser comme source :

```text
souvenir d'entraînement du modèle
Stack Overflow, blog personnel, réponse de forum
un autre agent
un seul fichier observé, présenté comme la règle générale
```

Le niveau 4 est une **observation**, pas une spécification. Il autorise à
écrire un parseur ; il n'autorise pas à écrire « le format impose que ».

### 3. Implémenter

Coder d'après la source, pas d'après le fichier d'exemple. Quand les deux
divergent, le signaler : c'est soit une variante de version, soit une
mécompréhension, et les deux méritent d'être écrites.

### 4. Citer

Toute affirmation de format dans un `01_ALGORITHMES/*.md`, un docstring de
parseur ou une revue porte sa source :

```text
Source : https://learn.microsoft.com/...   (autorité 1)
Observé : AI_BAROMETER_BI-CDS, Desktop 2.5+ (autorité 4 — non spécifié)
```

Une affirmation qu'on n'a pas pu sourcer se marque comme telle, en clair :

```text
NON SOURCÉ — déduit de N fichiers observés, à confirmer
```

Un `NON SOURCÉ` explicite vaut mieux qu'une certitude empruntée. C'est la même
discipline que `NA` côté verdict : dire qu'on ne sait pas est un résultat.

## Cas particulier : le format legacy

Le format legacy de rapport n'est pas documenté par Microsoft au même niveau
que PBIR. Les sources d'autorité 1 à 3 y sont souvent muettes.

Conséquence : la plupart des affirmations sur le legacy relèvent de l'autorité
4. Elles sont légitimes, mais doivent être écrites comme des observations, et
le parseur doit rester tolérant — un champ absent est une possibilité normale,
jamais une anomalie.

Ne jamais faire échouer une analyse parce qu'un fichier legacy ne ressemble pas
à ceux qu'on a vus.

## Comportements interdits

Ne jamais :

- affirmer l'existence d'une propriété TMDL ou PBIR sans l'avoir sourcée ou
  observée ;
- généraliser d'un fichier unique à « le format » ;
- présenter une observation comme une spécification ;
- recopier une affirmation d'un autre skill ou d'un dépôt tiers sans remonter à
  sa source ;
- écrire un parseur d'après une seule fixture qu'on a soi-même fabriquée.

## Sortie attendue

Pour chaque fait de format établi :

```text
Fait
Sérialisation concernée   TMDL | TMSL | PBIR | legacy | M | DAX
Niveau d'autorité         1 à 5
Source                    URL ou fichier observé + version
Statut                    SOURCÉ | NON SOURCÉ
```

## Principe fondamental

```text
un fait non sourcé n'est pas un fait, c'est une hypothèse qui a eu de la chance
```
