# Agent BI

Agent BI est un moteur d’analyse automatisée de projets **Power BI au format PBIP**.

Son objectif est de contrôler un rapport Power BI au regard des **bonnes pratiques définies par l’entreprise**, puis de catégoriser chaque contrôle selon trois statuts :

- `OK` : la conformité est démontrée ;
- `KO` : la non-conformité est démontrée ;
- `NA` : les informations disponibles ne permettent pas de conclure de manière fiable.

Le projet est conçu pour analyser aussi bien le **modèle sémantique** que le **rapport**, lorsque celui-ci est disponible.

---

## Objectif du projet

Agent BI vise à automatiser une partie des revues Power BI afin de rendre les contrôles :

- reproductibles ;
- traçables ;
- explicables ;
- testables ;
- extensibles ;
- indépendants d'une analyse manuelle systématique.

Le principe central est simple :

> Une règle technique qui peut être déterminée par du code doit être déterminée par du code.

L'utilisation d'un agent ou d'un skill est réservée aux tâches nécessitant réellement du contexte, de l'interprétation ou un contrôle de cohérence.

---

## Fonctionnement général

```text
Projet Power BI PBIP
        |
        v
Lecture du projet
        |
        +----------------------+
        |                      |
        v                      v
Semantic Model              Report
        |                      |
       TMDL                  PBIR / JSON
        |                      |
        +----------+-----------+
                   |
                   v
           Contexte d'analyse
                   |
                   v
            Moteur de règles
                   |
       +-----------+-----------+
       |           |           |
       v           v           v
      OK          KO          NA
       |           |           |
       +-----------+-----------+
                   |
                   v
            Résultat d'audit
```

Le projet Power BI est lu et préparé avant l'exécution des différentes bonnes pratiques.

Les règles utilisent ensuite les informations déjà extraites afin d'éviter de reparcourir inutilement l'ensemble du projet pour chaque contrôle.

---

## Architecture du projet

```text
Agent_BI/
|
├── 01_ALGORITHMES/
│
├── 02_SKILLS/
│
├── 03_PYTHON/
│
├── 04_DOCS/
│
├── SKILLS/
│
├── Agent_BI_Algorithmie_Regles_v1.xlsx
│
├── ALGORITHME_AGENT_BI_v1.md
│
├── Backend/
│
├── PR_Review_PowerBI_agent_scoring_v9.html
│
└── README.md
```

L'architecture cible repose principalement sur les quatre dossiers numérotés :

```text
01_ALGORITHMES
      |
      v
02_SKILLS
      |
      v
03_PYTHON
      |
      v
04_DOCS
```

Ils séparent volontairement la **définition fonctionnelle**, la **couche agentique**, l'**implémentation technique** et la **documentation transverse**.

---

## `01_ALGORITHMES`

Ce dossier contient la définition des bonnes pratiques prises en charge par Agent BI.

Chaque bonne pratique possède son propre algorithme.

L'algorithme doit préciser au minimum :

```text
Quelle bonne pratique ?
        |
        v
Quel périmètre ?
        |
        v
Où chercher l'information ?
        |
        v
Quelle propriété analyser ?
        |
        v
Comment la lire ?
        |
        v
Quelles conditions ?
        |
   +----+----+
   |    |    |
   v    v    v
  OK   KO   NA
```

Le dossier constitue donc la **référence fonctionnelle** du moteur.

Exemple :

```text
01_ALGORITHMES/
|
├── SEMANTIC_MODEL/
│   ├── SM-REL-001.md
│   ├── SM-COL-001.md
│   └── ...
│
└── REPORT/
    ├── RP-VIS-001.md
    ├── RP-PAGE-001.md
    └── ...
```

Un algorithme ne doit pas dépendre du langage utilisé pour son implémentation.

Il décrit **ce que le programme doit faire**, et non uniquement comment Python doit le faire.

---

## `02_SKILLS`

Ce dossier contient les skills utilisés par la couche agentique d'Agent BI.

Les skills n'ont pas vocation à remplacer les contrôles déterministes réalisés en Python.

Ils servent principalement à trois usages :

```text
Création d'une règle
        |
        v
Rule Engineering

Contrôle d'une règle
        |
        v
Rule Review

Analyse non déterministe
        |
        v
Contextual Analysis
```

### Rule Engineering

Le skill accompagne la transformation d'une bonne pratique en algorithme exploitable.

Il peut notamment vérifier :

- que le périmètre est clairement identifié ;
- que les propriétés nécessaires sont accessibles ;
- que les conditions `OK`, `KO` et `NA` sont explicites ;
- que les cas limites sont couverts ;
- que les preuves attendues sont définies ;
- que la règle peut réellement être automatisée.

### Rule Review

Le skill contrôle la cohérence entre :

```text
Algorithme
    |
    v
Implémentation Python
    |
    v
Tests
```

Il doit notamment pouvoir détecter des divergences telles que :

```text
Algorithme :
propriété absente -> NA

Python :
propriété absente -> KO

Résultat :
INCOHERENCE
```

### Contextual Analysis

Ce skill est réservé aux contrôles qui ne peuvent pas être déterminés uniquement par une propriété technique.

Par exemple :

- cohérence visuelle ;
- lisibilité d'une page ;
- compréhension de certains intitulés ;
- organisation de l'information ;
- contrôles nécessitant un jugement contextualisé.

---

## `03_PYTHON`

Ce dossier contient le moteur technique d'Agent BI.

Python est responsable de :

- la lecture du projet PBIP ;
- l'extraction des informations du modèle sémantique ;
- la lecture éventuelle du Report ;
- la construction du contexte d'analyse ;
- l'exécution des règles ;
- la production des statuts `OK`, `KO` ou `NA` ;
- la collecte des preuves ;
- les éventuelles corrections automatisées ;
- la génération des résultats.

Architecture cible :

```text
03_PYTHON/
|
├── main.py
├── engine/
├── powerbi/
├── rules/
│   ├── semantic_model/
│   └── report/
├── fixes/
│   ├── semantic_model/
│   └── report/
└── tests/
```

### Principe important

Les règles ne doivent pas chacune relire entièrement le projet Power BI.

Le fonctionnement attendu est :

```text
PBIP
 |
 v
Lecture unique
 |
 v
Analysis Context
 |
 +-------------------------------+
 |               |               |
 v               v               v
Règle 001     Règle 002       Règle N
 |               |               |
 v               v               v
OK              KO              NA
```

Cette approche permet au moteur de rester performant lorsque le nombre de bonnes pratiques augmente.

---

## `04_DOCS`

Ce dossier contient la documentation transverse du projet.

Il ne doit pas contenir les algorithmes propres à chaque bonne pratique.

Exemple :

```text
04_DOCS/
|
├── README.md
├── ARCHITECTURE.md
├── CONVENTIONS.md
└── COMPANY_POLICY.md
```

### `ARCHITECTURE.md`

Décrit plus précisément l'architecture technique d'Agent BI et les interactions entre les différents composants.

### `CONVENTIONS.md`

Centralise les conventions du projet :

- identifiants des règles ;
- conventions de nommage ;
- organisation des fichiers ;
- format des résultats ;
- règles de développement.

### `COMPANY_POLICY.md`

Contient les conventions et exigences propres à l'entreprise.

Il permet notamment de distinguer :

```text
Recommandation Power BI
        !=
Règle de gouvernance entreprise
```

Exemple :

```text
F_  -> Table de faits
D_  -> Dimension
P_  -> Table de paramètres
```

si ces conventions font partie des standards internes.

---

## Anciennes ressources et prototypes

Plusieurs éléments sont actuellement présents à la racine du projet :

```text
SKILLS/

Agent_BI_Algorithmie_Regles_v1.xlsx

ALGORITHME_AGENT_BI_v1.md

Backend/

PR_Review_PowerBI_agent_scoring_v9.html
```

Ces éléments représentent les travaux, prototypes ou documents ayant servi à construire Agent BI.

À mesure que la nouvelle architecture est mise en place, leur contenu pourra être progressivement :

- conservé comme référence ;
- migré dans les nouveaux dossiers ;
- intégré au moteur Python ;
- ou archivé lorsqu'il n'est plus nécessaire.

L'objectif est que les quatre dossiers principaux deviennent progressivement la structure de référence :

```text
01_ALGORITHMES/
02_SKILLS/
03_PYTHON/
04_DOCS/
```

---

## Statuts de validation

Toutes les règles déterministes utilisent les mêmes trois statuts.

### `OK`

La conformité est démontrée à partir des informations disponibles.

```text
Information disponible
        +
Condition respectée
        |
        v
       OK
```

### `KO`

La non-conformité est démontrée.

```text
Information disponible
        +
Condition non respectée
        |
        v
       KO
```

### `NA`

Le moteur ne dispose pas des informations nécessaires pour conclure de manière fiable.

```text
Information absente / illisible / inconnue
        |
        v
       NA
```

> `NA` ne doit jamais être utilisé comme synonyme de `KO`.

---

## Principe de preuve

Une règle ne doit pas uniquement retourner un statut.

Elle doit être capable d'expliquer pourquoi ce statut a été produit.

Un résultat doit idéalement contenir :

```text
Rule ID
    |
Object
    |
Expected value
    |
Actual value
    |
Evidence
    |
Status
```

Exemple :

```text
Rule ID   : SM-COL-001

Table     : F_SALES
Column    : Amount

Expected  : summarizeBy = none
Actual    : summarizeBy = sum

Status    : KO
```

Cela permet de rendre l'analyse :

- compréhensible ;
- vérifiable ;
- exploitable par un utilisateur ;
- exploitable par un agent ;
- utilisable dans un rapport d'audit.

---

## Analyse et correction

Agent BI sépare strictement l'analyse d'une éventuelle correction.

```text
              Analyse
                 |
                 v
            OK / KO / NA
                 |
                 v
          KO détecté ?
                 |
                Oui
                 |
                 v
      Correction disponible ?
             /       \
           Non       Oui
            |         |
            v         v
       Recommandation
                      |
                      v
               Autorisation
                      |
                      v
                 Correction
                      |
                      v
                 Réanalyse
```

Une analyse ne doit donc jamais modifier silencieusement un projet Power BI.

---

## Types de correction

Les corrections pourront être classées selon leur niveau de risque.

### Auto-fix

Correction déterministe présentant un risque faible.

Exemple :

```text
summarizeBy: sum
        |
        v
summarizeBy: none
```

### Assisted fix

Agent BI peut proposer une modification, mais une validation humaine est nécessaire avant application.

### Manual fix

Agent BI détecte le problème et fournit une recommandation, mais ne modifie pas automatiquement le projet.

Une restructuration complexe du modèle sémantique entre par exemple dans cette catégorie.

---

## Convention des règles

Les règles utilisent un identifiant permettant de retrouver immédiatement leur périmètre.

Exemple :

```text
SM-COL-001
```

Décomposition :

```text
SM  = Semantic Model
COL = Column
001 = numéro de la règle
```

Exemples :

| Identifiant | Périmètre |
|---|---|
| `SM-REL-001` | Semantic Model / Relationships |
| `SM-COL-001` | Semantic Model / Columns |
| `SM-MEA-001` | Semantic Model / Measures |
| `SM-TBL-001` | Semantic Model / Tables |
| `RP-VIS-001` | Report / Visuals |
| `RP-PAGE-001` | Report / Pages |
| `RP-FILT-001` | Report / Filters |

Le même identifiant doit être utilisé dans :

```text
Algorithme
    |
Python
    |
Tests
    |
Résultat d'audit
```

Exemple :

```text
01_ALGORITHMES/
SM-COL-001.md

        ↕

03_PYTHON/
rules/
sm_col_001.py

        ↕

03_PYTHON/
tests/
test_sm_col_001.py
```

---

## Cycle de vie d'une bonne pratique

Une nouvelle bonne pratique suit le processus suivant :

```text
Bonne pratique
      |
      v
Analyse fonctionnelle
      |
      v
Algorithme
      |
      v
Définition OK / KO / NA
      |
      v
Implémentation Python
      |
      v
Tests
      |
      v
Rule Review
      |
      v
Intégration dans Agent BI
```

Cette méthode permet de maintenir une cohérence entre ce qui est demandé, ce qui est implémenté et ce qui est réellement exécuté.

---

## Lancement

L'utilisateur n'a pas vocation à lancer directement les différents modules Python.

Le point d'entrée prévu est PowerShell :

```powershell
.\run-agent.ps1 -ProjectPath "C:\Projects\MyProject"
```

Le rôle de PowerShell reste volontairement limité :

```text
Utilisateur
    |
    v
PowerShell
    |
    v
Python
    |
    v
Agent BI
```

La logique métier reste dans le moteur Python.

---

## Vision cible

Agent BI est conçu pour évoluer progressivement.

```text
Catalogue de bonnes pratiques
          |
          v
Analyse automatisée PBIP
          |
          v
Audit complet
          |
          v
Corrections contrôlées
          |
          v
Intégration CI/CD
          |
          v
Contrôle continu de la gouvernance Power BI
```

L'objectif à terme est de disposer d'un moteur capable de contrôler un projet Power BI de manière systématique tout en conservant, pour chaque décision, une trace claire de :

- la règle appliquée ;
- l'objet analysé ;
- la valeur observée ;
- la valeur attendue ;
- la preuve utilisée ;
- le statut obtenu.

---

## Principes directeurs

```text
Algorithmes   = définition fonctionnelle
Python        = exécution déterministe
Tests         = validation technique
Skills        = intelligence et contrôle
PowerShell    = point d'entrée
Documentation = traçabilité
```

Agent BI doit rester conçu autour d'un principe fondamental :

> **Un même projet, analysé avec les mêmes règles et la même configuration, doit produire le même résultat.**
