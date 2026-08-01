````markdown
<div align="center">

# Best Practices Colas

### Plateforme de Peer Review Power BI

**Centraliser les contrôles, fiabiliser les validations et assurer la traçabilité des bonnes pratiques BI.**

[![Version](https://img.shields.io/badge/version-MVP%201.0.0-2563EB?style=flat-square)](https://github.com/dataphil971/Best_Practices_Colas)
[![Backend](https://img.shields.io/badge/backend-lots%201--7-7C3AED?style=flat-square)](https://github.com/dataphil971/Best_Practices_Colas)
[![Statut](https://img.shields.io/badge/statut-prototype-F59E0B?style=flat-square)](#statut-du-projet)
[![Documentation](https://img.shields.io/badge/documentation-v1.2-16A34A?style=flat-square)](./Spec_Backend_PR_Review.md)
[![Power BI](https://img.shields.io/badge/Power%20BI-Peer%20Review-F2C811?style=flat-square&logo=powerbi&logoColor=000000)](#fonctionnalités-clés)

</div>

> [!IMPORTANT]
> Le dépôt contient actuellement un **prototype d'interface exécutable dans le navigateur**, une **spécification backend détaillée** et les **archives des lots backend 1 à 7**. Il ne constitue pas encore une application consolidée prête pour un déploiement en production.

---

## Sommaire

- [Pourquoi ce projet ?](#pourquoi-ce-projet-)
- [Le projet en un coup d'œil](#le-projet-en-un-coup-dœil)
- [Fonctionnalités clés](#fonctionnalités-clés)
- [Parcours d'une revue](#parcours-dune-revue)
- [Architecture cible](#architecture-cible)
- [Stack technique](#stack-technique)
- [Structure du dépôt](#structure-du-dépôt)
- [Lancer le prototype](#lancer-le-prototype)
- [Roadmap](#roadmap)
- [Sécurité et gouvernance](#sécurité-et-gouvernance)
- [Documentation](#documentation)
- [Contribution](#contribution)
- [Auteur et licence](#auteur-et-licence)

---

## Pourquoi ce projet ?

La revue qualité de projets Power BI peut rapidement devenir difficile à piloter lorsqu'elle repose sur plusieurs fichiers Excel, des échanges dispersés et différentes versions d'un même référentiel.

**Best Practices Colas** propose un parcours centralisé permettant de :

- évaluer un livrable Power BI à partir d'un référentiel commun ;
- identifier rapidement les écarts, les risques et les actions correctives ;
- partager une revue avec un reviewer identifié ;
- historiser les décisions et les validations ;
- conserver la version exacte des règles appliquées à chaque revue ;
- préparer l'import et le rapprochement de données depuis Excel, SharePoint ou OneDrive.

### Principe structurant : le versionnement immuable

Une revue conserve un **snapshot de la version des règles utilisée lors de sa création**. Une modification ultérieure du référentiel n'altère donc pas l'historique des anciennes revues.

Ce mécanisme garantit :

- la cohérence des résultats dans le temps ;
- l'auditabilité des contrôles ;
- la traçabilité des évolutions du référentiel.

---

## Le projet en un coup d'œil

| Élément | État actuel |
|---|---|
| Prototype de l'interface de Peer Review | ✅ Disponible au format HTML |
| Parcours de navigation et de revue | ✅ Démontrable localement |
| Spécification technique backend | ✅ Version 1.2 documentée |
| Modèle de données et endpoints REST | ✅ Définis dans la spécification |
| Archives backend | ✅ Lots 1 à 7 présents dans le dépôt |
| Backend consolidé dans une arborescence unique | 🟡 À finaliser |
| Tests automatisés et intégration continue | 🟡 À industrialiser |
| Déploiement Azure de production | ⏳ Cible future |

### Utilisateurs visés

| Rôle | Responsabilité principale |
|---|---|
| **Utilisateur / auteur** | Créer, compléter et soumettre une revue |
| **Reviewer** | Examiner une revue partagée, commenter et valider |
| **Administrateur** | Gérer les règles, les rôles, les connecteurs et l'audit |

---

## Fonctionnalités clés

### 1. Gestion des revues

- création et suivi d'une revue ;
- évaluation de chaque règle avec les statuts `OK`, `KO`, `Partiel`, `Non applicable` ou `Non renseigné` ;
- calcul d'un score de conformité ;
- ajout de commentaires, risques et solutions correctives ;
- suivi d'un plan de remédiation avec responsable et date cible ;
- recherche, tri, filtrage et export Excel.

### 2. Référentiel versionné

- gestion de plusieurs checklists : Power BI, App BI et Build ;
- proposition, approbation ou rejet de nouvelles règles ;
- création de versions immuables ;
- conservation de l'historique complet ;
- retrait et restauration sans suppression définitive ;
- journal d'activité du référentiel.

### 3. Validation tierce

- soumission d'une revue à un ou plusieurs reviewers ;
- commentaires globaux ou rattachés à un point de contrôle ;
- validation, refus ou demande de modifications ;
- nouveau cycle de soumission après correction ;
- limitation de l'accès aux seules revues explicitement partagées.

### 4. Import intelligent

- import manuel de fichiers Excel ;
- analyse et rapprochement avec le référentiel ;
- préremplissage des statuts ;
- détection des correspondances ambiguës ;
- validation humaine des cas incertains ;
- traitement asynchrone des imports volumineux ;
- synchronisation planifiée depuis SharePoint ou OneDrive.

### 5. Connecteurs configurables

- moteur de matching local basé sur `rapidfuzz` ;
- connecteurs IA interchangeables : Mistral, IA interne, OpenAI ou Azure OpenAI ;
- stockage pluggable : Azure Blob, Amazon S3, MinIO ou stockage interne ;
- changement du fournisseur actif sans modification du cœur applicatif ;
- solution de repli locale lorsque l'IA est indisponible.

---

## Parcours d'une revue

```mermaid
stateDiagram-v2
    [*] --> Brouillon
    Brouillon --> En_cours: début de l'évaluation
    En_cours --> Soumise: envoi au reviewer
    Soumise --> Validee: validation
    Soumise --> Modifications_demandees: corrections requises
    Modifications_demandees --> En_cours: mise à jour
    Validee --> [*]
```

| État technique | Description |
|---|---|
| `draft` | La revue vient d'être créée |
| `in_progress` | La revue est en cours de remplissage |
| `submitted` | La revue a été soumise pour validation |
| `validated` | La revue a été validée |
| `changes_requested` | Des corrections ont été demandées |

<details>
<summary><strong>Voir les rôles et permissions détaillés</strong></summary>

<br>

| Fonctionnalité | Utilisateur | Reviewer | Administrateur |
|---|:---:|:---:|:---:|
| Créer et compléter ses revues | ✅ | ✅ | ✅ |
| Consulter ses propres revues | ✅ | ✅ | ✅ |
| Consulter une revue partagée | ✅ | ✅ | ✅ |
| Consulter toutes les revues | ❌ | ❌ | ✅ |
| Proposer une règle | ✅ | ✅ | ✅ |
| Valider ou refuser une revue | ❌ | ✅ | ✅ |
| Approuver ou rejeter une règle | ❌ | ❌ | ✅ |
| Retirer ou restaurer une règle | ❌ | ❌ | ✅ |
| Gérer les utilisateurs et les rôles | ❌ | ❌ | ✅ |
| Configurer l'IA, le stockage et SharePoint | ❌ | ❌ | ✅ |
| Consulter le journal complet d'activité | ❌ | ❌ | ✅ |

> Un reviewer accède uniquement aux revues qui lui ont été explicitement partagées ou soumises.

</details>

---

## Architecture cible

```mermaid
flowchart LR
    U[Utilisateur] -->|HTTPS| F[Frontend React / TypeScript]
    F -->|API REST JSON| A[API FastAPI]

    A --> P[(PostgreSQL)]
    A --> R[(Redis)]
    A --> S[Stockage pluggable]
    A --> K[Azure Key Vault]

    R --> W[Workers Celery]

    W --> M[Matching local]
    W --> I[Connecteur IA]
    W --> G[Microsoft Graph API]
    W --> S

    G --> SP[SharePoint / OneDrive]
```

### Principes d'architecture

- le frontend consomme exclusivement l'API ;
- les autorisations sont contrôlées côté serveur ;
- les traitements longs sont délégués à des workers asynchrones ;
- les secrets restent hors du code et du frontend ;
- les fournisseurs d'IA et de stockage sont interchangeables ;
- un moteur local reste disponible comme solution de repli ;
- les actions sensibles sont enregistrées dans un journal d'audit.

<details>
<summary><strong>Voir le modèle de données cible</strong></summary>

<br>

Les principales entités prévues sont :

- `users` ;
- `categories` ;
- `rules` et `rule_versions` ;
- `reviews` et `review_items` ;
- `validations` et `validation_item_comments` ;
- `share_links` et `share_targets` ;
- `audit_log` et `rule_activity` ;
- `import_jobs` ;
- `integration_config`.

Une règle possède une identité stable dans `rules` et plusieurs versions immuables dans `rule_versions`. Chaque revue référence directement les versions utilisées au moment de sa création.

</details>

---

## Stack technique

| Couche | Technologies cibles |
|---|---|
| Frontend | React, TypeScript, TanStack Query |
| API | Python 3.12, FastAPI, Pydantic |
| Base de données | PostgreSQL 16 |
| ORM et migrations | SQLAlchemy 2.x, Alembic |
| Authentification | Microsoft Entra ID, OIDC |
| Authentification de repli | Email, mot de passe, Argon2id |
| Traitements asynchrones | Celery, Redis |
| Import Excel | openpyxl |
| Matching local | rapidfuzz, PostgreSQL `pg_trgm` |
| Intelligence artificielle | Mistral, IA interne, OpenAI, Azure OpenAI |
| Stockage | Azure Blob, Amazon S3, MinIO, stockage interne |
| Gestion des secrets | Azure Key Vault |
| Intégration Microsoft | Microsoft Graph API |
| Conteneurisation | Docker |
| Hébergement cible | Azure Container Apps ou AKS |

> Cette table décrit la **cible d'architecture**. La présence d'une technologie dans cette section ne signifie pas nécessairement que son intégration est déjà consolidée sur la branche principale.

---

## Structure du dépôt

```text
Best_Practices_Colas/
├── README.md
├── PR_Review_PowerBI.html
├── Spec_Backend_PR_Review.md
├── Spec_Backend_PR_Review.html
├── pr_review_backend_lot1.zip
├── pr_review_backend_lot2.zip
├── pr_review_backend_lot3.zip
├── pr_review_backend_lot4.zip
├── pr_review_backend_lot5.zip
├── pr_review_backend_lot6.zip
└── pr_review_backend_lot7.zip
```

| Fichier | Description |
|---|---|
| `PR_Review_PowerBI.html` | Prototype exécutable de l'interface de Peer Review |
| `Spec_Backend_PR_Review.md` | Spécification technique backend au format Markdown |
| `Spec_Backend_PR_Review.html` | Version HTML de la spécification backend |
| `pr_review_backend_lot1.zip` à `lot7.zip` | Archives de livraison ou de travail des différents lots backend |

> [!NOTE]
> Les archives backend permettent de conserver les livraisons par lot. Une prochaine étape d'industrialisation consiste à consolider leur contenu dans une arborescence applicative unique, testable et versionnée fichier par fichier.

---

## Lancer le prototype

Le prototype actuel est autonome : aucun serveur backend n'est nécessaire pour consulter l'interface.

### 1. Cloner le dépôt

```bash
git clone https://github.com/dataphil971/Best_Practices_Colas.git
cd Best_Practices_Colas
```

### 2. Ouvrir l'interface

#### Windows PowerShell

```powershell
Start-Process .\PR_Review_PowerBI.html
```

#### Linux

```bash
xdg-open PR_Review_PowerBI.html
```

#### macOS

```bash
open PR_Review_PowerBI.html
```

Le fichier peut également être ouvert directement depuis l'explorateur de fichiers avec un navigateur moderne.

---

## Roadmap

### Réalisé

- [x] Prototype du parcours de Peer Review — MVP 1.0.0
- [x] Spécification backend v1.2
- [x] Architecture cible, sécurité, RBAC et modèle de données
- [x] Documentation des endpoints REST
- [x] Découpage fonctionnel du backend en lots
- [x] Ajout des archives backend des lots 1 à 7

### Prochaines priorités

- [ ] Extraire et consolider les lots backend dans une arborescence unique
- [ ] Ajouter un fichier `.env.example` sans secret
- [ ] Ajouter une configuration Docker Compose de développement
- [ ] Mettre en place les migrations et données d'initialisation reproductibles
- [ ] Ajouter les tests unitaires, d'intégration et de sécurité
- [ ] Configurer l'intégration continue avec GitHub Actions
- [ ] Documenter le démarrage complet du frontend et du backend
- [ ] Ajouter des captures d'écran ou une démonstration du prototype
- [ ] Préparer le déploiement Azure et le monitoring

<details>
<summary><strong>Voir le découpage fonctionnel des lots</strong></summary>

<br>

| Lot | Périmètre principal |
|---|---|
| **Lot 1** | Fondations, PostgreSQL, migrations, authentification Entra ID et RBAC |
| **Lot 2** | Référentiel versionné, approbation, retrait, restauration et historique |
| **Lot 3** | Gestion des revues, score de conformité, commentaires et remédiations |
| **Lot 4** | Partage ciblé, validation tierce et cycle de resoumission |
| **Lot 5** | Import Excel, matching local, préremplissage et stockage pluggable |
| **Lot 6** | Connecteurs IA configurables et mécanisme de repli local |
| **Lot 7** | Microsoft Graph, SharePoint, OneDrive et synchronisation planifiée |
| **Lot 8** | Monitoring, audit, tests de charge et durcissement de la sécurité |

</details>

---

## Sécurité et gouvernance

L'architecture prévoit notamment :

- une authentification Microsoft Entra ID ;
- un contrôle d'accès RBAC côté serveur ;
- des tokens à durée de vie limitée ;
- un hachage Argon2id pour l'authentification de repli ;
- des requêtes SQL paramétrées ;
- une validation stricte des fichiers importés ;
- une protection contre l'injection de formules Excel ;
- un stockage des secrets dans Azure Key Vault ;
- une journalisation des actions sensibles ;
- TLS, HSTS, CORS restrictif, protection CSRF et rate limiting ;
- une rétention configurable des fichiers importés ;
- une minimisation des données envoyées aux fournisseurs d'IA.

### Confidentialité du dépôt

Ne jamais versionner :

- un mot de passe, un jeton, une clé API ou une chaîne de connexion ;
- un fichier `.env` réel ;
- un fichier Power BI ou Excel contenant des données confidentielles ;
- des informations personnelles non anonymisées ;
- des captures, documents ou informations internes non autorisés à la publication.

> [!WARNING]
> Ce dépôt étant public, chaque fichier doit être vérifié avant publication. Le projet doit rester un prototype technique sans données métier confidentielles ni secrets d'entreprise.

---

## Documentation

- [Spécification backend — Markdown](./Spec_Backend_PR_Review.md)
- [Spécification backend — HTML](./Spec_Backend_PR_Review.html)
- [Prototype Peer Review Power BI](./PR_Review_PowerBI.html)

---

## Contribution

### Workflow recommandé

```bash
# Mettre la branche principale à jour
git switch main
git pull origin main

# Créer une branche dédiée
git switch -c docs/nom-de-la-modification

# Vérifier et enregistrer les changements
git status
git add README.md
git commit -m "docs: improve project README"

# Publier la branche
git push -u origin docs/nom-de-la-modification
```

Ouvrir ensuite une Pull Request vers `main` en décrivant :

- le contenu de la modification ;
- sa raison ;
- son impact ;
- les vérifications réalisées.

### Convention de commits suggérée

- `docs:` documentation ;
- `feat:` nouvelle fonctionnalité ;
- `fix:` correction ;
- `refactor:` restructuration sans changement fonctionnel ;
- `test:` ajout ou modification de tests ;
- `chore:` maintenance technique.

---

## Statut du projet

**Best Practices Colas est actuellement un prototype / MVP en cours d'industrialisation.**

Les parcours fonctionnels, l'architecture cible et la stratégie backend sont documentés. Les prochaines étapes consistent principalement à consolider le code des lots, automatiser les tests, sécuriser la configuration et préparer un déploiement reproductible.

Ce dépôt présente un travail de conception et de prototypage ; il ne constitue pas une publication officielle ni une solution de production validée.

---

## Auteur et licence

Projet développé et documenté par **[dataphil971](https://github.com/dataphil971)**.

- Dépôt : [dataphil971/Best_Practices_Colas](https://github.com/dataphil971/Best_Practices_Colas)
- Licence : aucune licence open source n'est actuellement définie.

En l'absence de fichier `LICENSE`, tous les droits restent réservés à l'auteur du dépôt. Toute réutilisation ou diffusion doit respecter le contexte du projet et les règles de confidentialité applicables.
````
