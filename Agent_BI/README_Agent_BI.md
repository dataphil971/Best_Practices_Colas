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
├── 05_NODE/
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

L'architecture cible repose principalement sur les cinq dossiers numérotés :

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

05_NODE (transverse : pont local entre un futur frontend et 03_PYTHON)
```

Ils séparent volontairement la **définition fonctionnelle**, la **couche agentique**, l'**implémentation technique**, la **documentation transverse** et le **pont d'intégration local**. `05_NODE` est transverse plutôt que séquentiel : il ne produit pas de bonne pratique, il expose `03_PYTHON` à un appelant externe (navigateur).

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
├── 01_Relations.md            (BP-01)
├── 02_DateTable.md             (BP-02)
├── 03_AvoidBidirectional.md    (BP-03)
├── 22_DisableSummarization.md  (BP-22, alias SEM-001)
└── ...
```

Les fichiers sont rangés à plat dans `01_ALGORITHMES/`, sans sous-dossiers par périmètre : le périmètre (modèle sémantique ou rapport) n'est pas porté par l'identifiant ni par un dossier, mais par le contenu même de l'algorithme (voir `Convention des règles`).

### Statut d'implémentation

Un algorithme peut exister sans implémentation : c'est une étape normale du cycle de vie d'une bonne pratique, pas une anomalie. Chaque fichier porte donc une **bannière de statut** juste sous son titre :

```text
✅ Implémenté      la règle est codée, testée, et exécutée par le moteur
⏳ Non implémenté  spécification seule — aucun code, donc aucun contrôle
```

`01_ALGORITHMES/README.md` en donne l'index complet. La source de vérité reste le catalogue `03_PYTHON/rules/registry.py`.

Une règle ⏳ n'est pas « désactivée » au sens métier : elle n'existe simplement pas encore côté moteur, et **n'apparaît jamais dans un résultat d'analyse** — surtout pas avec un statut `NA`, qui laisserait croire qu'un contrôle a été tenté.

Un test (`03_PYTHON/tests/test_registry.py`) échoue si un algorithme est ajouté sans être déclaré au catalogue, ou si une bannière contredit l'état réel du moteur.

Un algorithme ne doit pas dépendre du langage utilisé pour son implémentation.

Il décrit **ce que le programme doit faire**, et non uniquement comment Python doit le faire.

---

## `02_SKILLS`

Ce dossier documente la couche agentique d'Agent BI dans l'architecture fonctionnelle du projet.

Les fichiers exécutables `SKILL.md` ne sont pas stockés ici : ils vivent à la racine du dépôt, dans `.claude/skills/` (emplacement lu à la fois par Claude Code et par GitHub Copilot). `02_SKILLS/` ne contient qu'un pointeur vers cet emplacement, afin d'éviter deux sources de vérité pour un même skill.

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
├── main.py           point d'entrée (appelé par run-agent.ps1)
├── engine/            contexte d'analyse partagé, orchestrateur de règles, modèles (Finding, RuleResult)
├── powerbi/            parseurs TMDL / PBIR
├── rules/               une règle par fichier, à plat : bp_21.py, bp_22.py, ...
├── fixes/                une correction par fichier, à plat : bp_22.py, ...
└── tests/
    └── fixtures/          fixtures minimales par règle : fixtures/bp_22/ok|ko|na/
```

`rules/` et `fixes/` sont à plat, sans sous-dossiers `semantic_model/`/`report/` : comme pour `01_ALGORITHMES/`, le périmètre se déduit du contenu de chaque fichier, pas de son emplacement (cf. `Convention des règles`).

### État actuel

```text
Implémenté   : engine/ (contexte, orchestrateur, API, enveloppe), powerbi/ (TMDL, Power Query,
               DAX, rapport PBIR et LEGACY), 16 règles sur 37, catalogue rules/registry.py,
               tests + fixtures
À construire : les 21 BP-NN restantes (cf. 01_ALGORITHMES/README.md), fixes/, run-agent.ps1
```

`BP-22` sert de référence pour implémenter les prochaines règles : même structure (`engine`/`powerbi`/`rules`/`tests`), même correspondance stricte avec son algorithme (`01_ALGORITHMES/22_DisableSummarization.md`), mêmes trois statuts `OK`/`KO`/`NA`.

### Contrat JSON

`main.py` produit une enveloppe versionnée (`engine/envelope.py`), pensée pour être consommée par un appelant externe (serveur Node local, route FastAPI d'import) sans connaître les détails internes du moteur :

```json
{
  "schema_version": "1.1",
  "engine_version": "1.0.0",
  "generated_at": "2026-08-27T09:12:44.512000+00:00",
  "project": {
    "name": "AI_BAROMETER_BI-CDS",
    "format": "PBIP",
    "project_path": "C:\\...\\TEST",
    "semantic_model_path": "C:\\...\\AI_BAROMETER_BI-CDS.SemanticModel",
    "fingerprint": "sha256:..."
  },
  "summary": {
    "overall_status": "KO",
    "rules_evaluated": 16,
    "rules_by_status": { "OK": 7, "KO": 5, "NA": 4 },
    "findings_by_status": { "OK": 569, "KO": 30, "NA": 219 }
  },
  "results": [
    {
      "rule_id": "BP-22",
      "alias": "SEM-001",
      "rule_name": "Désactivation de l'autosummarization",
      "execution_status": "SUCCESS",
      "rule_status": "OK",
      "total_tables": 15,
      "total_columns": 69,
      "conforming_columns": 69,
      "nonconforming_columns": 0,
      "na_columns": 0,
      "ko_details": [],
      "na_details": [],
      "findings": [
        { "rule_id": "BP-22", "object_type": "column", "object": "D_CAMPAIGNS.CAMPAIGN_ID",
          "expected": "summarizeBy = none", "actual": "none", "status": "OK",
          "evidence": { "table": "D_CAMPAIGNS", "column": "CAMPAIGN_ID", "source_file": "..." },
          "reason": "" }
      ]
    }
  ]
}
```

Points de contrat :

- `schema_version` suit `MAJEUR.MINEUR` : le MINEUR n'ajoute que des champs (un consommateur écrit pour `1.0` continue de lire une enveloppe `1.1`), le MAJEUR seul signale une évolution incompatible. Un consommateur externe doit s'y fier plutôt qu'à la présence/absence d'un champ.
- `generated_at` est l'horodatage ISO 8601 (UTC) de l'analyse. C'est le **seul** champ qui varie entre deux analyses du même projet par le même moteur : tout le reste est reproductible à l'octet près.
- `summary.overall_status` consolide les statuts de règle selon la même hiérarchie que les constats : un seul `KO` suffit à faire `KO` ; sinon un seul `NA` suffit à faire `NA` ; `OK` n'est prononcé que si **toutes** les règles concluent `OK`. Une analyse sans aucune règle vaut `NA`, jamais `OK` — n'avoir rien contrôlé ne démontre aucune conformité.
- `project.semantic_model_path` vaut `null` si aucun dossier `*.SemanticModel` n'a été trouvé sous `project_path` — à distinguer d'un modèle trouvé mais sans table lisible (`semantic_model_path` renseigné, `tables` vide côté moteur).
- `project.fingerprint` est une empreinte légère (chemin + taille + date de modification de chaque fichier de table lu, pas le contenu) : suffisante pour détecter qu'un projet a changé depuis la dernière analyse, pas une empreinte cryptographique de contenu.
- `results[].findings` porte la preuve complète (Rule ID / Object / Expected / Actual / Evidence / Status) pour **chaque** objet analysé, y compris les `OK` — un consommateur externe ne doit jamais avoir à redériver une preuve à partir de `ko_details`/`na_details`, qui restent spécifiques à chaque règle.
- Le code de sortie du process est `0` dès que le moteur a produit un résultat structuré, **y compris quand `rule_status = KO`** : un `KO` est un résultat métier valide, pas une erreur d'exécution. Le code `2` signale une analyse qui n'a **pas pu être menée** (chemin de projet inexistant, règle inconnue) ; le diagnostic part alors sur `stderr`, jamais sur `stdout`, pour que la sortie standard reste du JSON exploitable en toutes circonstances.

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

## `05_NODE`

Ce dossier contient le serveur local (`127.0.0.1` uniquement — jamais exposé sur le réseau) qui relie un appelant externe (navigateur) au moteur Python (`03_PYTHON`).

Architecture :

```text
05_NODE/
|
├── package.json
├── server.js               routage HTTP, CORS, jeton d'appairage
└── services/
    ├── pairing.js            appairage par code (TTL 60s), émission de jetons
    ├── analyses.js           registre en mémoire des analyses lancées
    └── python-runner.js      spawn de 03_PYTHON/main.py (jamais shell: true)
```

### Protocole

Compatible avec `Backend/pbi-agent-overlay-v2.js` (prototype frontend déjà écrit mais jamais branché à un vrai agent) : port `27841` par défaut, préfixe `/api/v1`, en-têtes `X-Agent-Protocol` / `X-Agent-Token`.

```text
GET  /api/v1/health
POST /api/v1/pairing/request     { origin } -> {}  (code affiché côté agent, jamais renvoyé au navigateur)
POST /api/v1/pairing/confirm     { code }   -> { token }
POST /api/v1/analyses            { project_path } -> 202 { analysis_id, status }   (jeton requis)
GET  /api/v1/analyses/{id}       -> { analysis_id, status, result, error }         (jeton requis)
```

### Principes de sécurité

- Le serveur n'écoute que sur `127.0.0.1` : il exécute du code Python arbitraire sur la machine locale, il ne doit jamais être accessible depuis le réseau.
- Le code d'appairage n'est **jamais** renvoyé par `/pairing/request` : il est affiché dans la console du process Node, pour garantir qu'un site web quelconque ne peut pas s'auto-appairer sans qu'un humain lise le code sur la machine.
- `/analyses` exige le jeton obtenu après appairage (`X-Agent-Token`) — le CORS ouvert au navigateur ne remplace pas cette vérification.
- Python est lancé via `spawn(executable, [main.py, project_path])`, jamais `{ shell: true }` : aucune interpolation de chaîne dans une commande shell, donc aucune injection possible via le chemin du projet.
- `project_path` est validé (chemin non vide, dossier existant) avant tout `spawn`.

### Hors périmètre (volontairement)

Ce que `Backend/pbi-agent-overlay-v2.js` prévoit mais que `05_NODE` n'implémente pas :

```text
Connexion TOM/AMO live à une instance Power BI Desktop ouverte
Sélecteur de fichier natif Windows
Plans de correction (dry-run, ops à risque, jetons haute confiance)
```

Ces fonctionnalités appartiennent à une itération ultérieure, hors du périmètre Python + Node décidé pour ce projet.

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
Rule ID   : BP-22

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

Les règles utilisent un identifiant plat, sans préfixe de périmètre :

```text
BP-NN
```

Décomposition :

```text
BP  = Bonne Pratique
NN  = numéro de la règle (deux chiffres, séquentiel)
```

Le périmètre (modèle sémantique ou rapport) n'est pas encodé dans l'identifiant. Il se déduit du contenu de l'algorithme, notamment de la section « Emplacement des fichiers concernés », qui référence explicitement :

```text
<SEMANTIC_MODEL_PATH>/definition/...   -> périmètre Semantic Model
<REPORT_PATH>/definition/...           -> périmètre Report
```

Exemples :

| Identifiant | Fichier | Périmètre |
|---|---|---|
| `BP-01` | `01_Relations.md` | Semantic Model / Relationships |
| `BP-21` | `21_ConciseNames.md` | Semantic Model / Nommage |
| `BP-22` | `22_DisableSummarization.md` | Semantic Model / Columns |
| `BP-37` | `37_OrganizeVisualsBookmarks.md` | Report / Visuals |
| `BP-39` | `39_ConfigAndTestFilters.md` | Report / Filters |

La numérotation peut comporter des trous (règles pas encore rédigées) : ce n'est pas une anomalie.

Certaines règles portent un **alias hérité** d'un schéma de nommage antérieur (`SEM-XXX`), conservé uniquement à titre de traçabilité historique. L'identifiant de référence reste toujours `BP-NN` :

```text
BP-04 (alias SEM-003)
BP-22 (alias SEM-001)
```

Le même identifiant `BP-NN` doit être utilisé dans :

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
21_ConciseNames.md   (BP-21)

        ↕

03_PYTHON/
rules/
bp_21.py

        ↕

03_PYTHON/
tests/
test_bp_21.py
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

`run-agent.ps1` n'existe pas encore. En attendant, le point d'entrée réel et fonctionnel est directement `03_PYTHON/main.py` :

```powershell
cd Agent_BI/03_PYTHON
pip install -r requirements.txt
python main.py "C:\Projects\MyProject"
```

`MyProject` doit être la racine d'un projet PBIP (dossier contenant `<Nom>.SemanticModel/`). La sortie est l'enveloppe JSON versionnée décrite dans `03_PYTHON` ci-dessus, avec un résultat par règle du registre (`rules/registry.py` — `BP-22` pour l'instant).

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
