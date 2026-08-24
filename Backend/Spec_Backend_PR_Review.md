# Spécification Backend — Plateforme de Peer Review Power BI

**Version 1.2 · Document de conception technique**
Destiné à l'équipe de développement. À versionner dans le dépôt, à côté du code.

**Contexte arrêté (v1.2)** : outil **interne** hébergé sur **Azure**, identité via **Microsoft Entra ID (SSO)**, **type d'IA ET type de stockage configurables par l'admin** (couches d'abstraction pluggables, changement à chaud sans redéploiement), IA par défaut **Mistral (EU)** avec bascule possible vers une **IA interne d'entreprise**, rétention des fichiers **1 mois par défaut, modifiable par l'admin**, visibilité reviewer **strictement limitée aux revues partagées/soumises**.

**Nouveautés v1.2** (par rapport à v1.1) : vue complète d'une revue pour les reviewers/admins (y compris les points non renseignés) · journal d'activité du référentiel avec attribution multi-admins · retrait/restauration de règles avec historique conservé · recherche (revues, référentiel, file de validation) · **stockage pluggable configurable par l'admin** (Azure Blob / S3 / stockage interne).


---

## 1. Objet du document

Ce document décrit l'architecture serveur complète de la plateforme de Peer Review Power BI dont le prototype front a validé les parcours. Il couvre : le modèle de données, le schéma SQL exécutable, l'API REST, le modèle de permissions, les connecteurs (moteur de correspondance / IA, import SharePoint), la sécurité, et une feuille de route de livraison.

Le principe fondateur, hérité du prototype, reste **le versionnement immuable des règles** : une revue référence toujours la *version* d'une règle telle qu'elle existait au moment de l'évaluation, jamais la règle mutable. C'est ce qui permet d'exploiter l'historique des revues même quand le référentiel évolue.

---

## 2. Décisions d'architecture

### 2.1 Stack retenue

| Couche | Choix | Justification |
|---|---|---|
| Langage / framework API | **Python 3.12 + FastAPI** | Écosystème idéal pour l'Excel (`openpyxl`), la similarité (`rapidfuzz`), et l'appel de modèles d'IA ; typage via Pydantic ; OpenAPI généré automatiquement. |
| Base de données | **PostgreSQL 16** | Intégrité relationnelle (clés étrangères, transactions), indispensable pour le versionnement et l'audit. |
| ORM / migrations | **SQLAlchemy 2.x + Alembic** | Migrations versionnées, requêtes paramétrées (anti-injection). |
| Auth | **Microsoft Entra ID (SSO, OIDC)** en principal, email/mot de passe (Argon2id) en repli optionnel | Outil interne : l'identité d'entreprise est la source de vérité. Une seule identité pour l'app, SharePoint et l'IA interne. |
| File d'attente asynchrone | **Celery + Redis** (ou `arq`) | Import Excel, appels IA et synchro SharePoint sont des tâches longues → hors requête HTTP. |
| Stockage fichiers | **Pluggable** — Azure Blob (défaut), S3, ou stockage interne, **choisi par l'admin** | Interface commune (§7bis) ; l'admin change de backend de stockage sans redéploiement. |
| Secrets | **Azure Key Vault** | Clés IA, secrets Graph, chaînes de connexion stockage, jamais en base ni dans le code. |
| Front | React + TypeScript (le prototype) | Consomme l'API via TanStack Query. |
| Déploiement | **Azure** (Container Apps / AKS) + reverse-proxy TLS | Cohérent avec Entra ID + SharePoint ; secrets via Key Vault. |

### 2.2 Vue d'ensemble des composants

```
┌─────────────┐      HTTPS/JSON      ┌──────────────────────┐
│  Front React│ ───────────────────► │   API FastAPI        │
└─────────────┘                      │  - Auth / RBAC       │
                                     │  - CRUD référentiel  │
                                     │  - Revues            │
                                     │  - Validation        │
                                     └───────┬──────────────┘
                                             │
                        ┌────────────────────┼────────────────────┐
                        ▼                     ▼                    ▼
                 ┌────────────┐        ┌────────────┐       ┌────────────┐
                 │ PostgreSQL │        │  Redis +   │       │ Stockage   │
                 │            │        │  Celery    │       │ pluggable  │
                 └────────────┘        └─────┬──────┘       └────────────┘
                                             │ tâches asynchrones
                        ┌────────────────────┼────────────────────┐
                        ▼                     ▼                    ▼
                 ┌────────────┐        ┌────────────┐       ┌────────────┐
                 │ Moteur de  │        │ Connecteur │       │ Connecteur │
                 │ matching   │        │ IA (LLM)   │       │ SharePoint │
                 │ (local)    │        │ pluggable  │       │ (Graph API)│
                 └────────────┘        └────────────┘       └────────────┘
```

Le **moteur de matching local** (le moteur sémantique du prototype, porté en Python) reste le comportement par défaut, gratuit et sans réseau. Le **connecteur IA** est optionnel et configurable par l'admin ; il n'est appelé que si activé. Le **connecteur SharePoint** récupère automatiquement les fichiers selon des règles définies par l'admin.

---

## 3. Modèle de données

### 3.1 Entités et relations

Le schéma comprend onze tables principales. Les relations clés :

- Un **référentiel** est identifié par `checklist_type` (`powerbi` / `appbi` / `build`). Chaque type possède ses propres catégories et règles.
- Une **règle** (`rules`) est une identité stable ; son **contenu** vit dans `rule_versions`, immuable. Une seule version est `is_current` par règle.
- Une **revue** (`reviews`) fige, à sa création, un ensemble de `review_items`, chacun pointant vers une `rule_version_id` précise (le snapshot).
- Une **validation** tierce (`validations`) enregistre la décision d'un reviewer/admin, avec des commentaires par point (`validation_item_comments`).
- Un **lien de partage** (`share_links`) permet à un tiers d'accéder à une revue.
- Toute action sensible est tracée dans `audit_log` (technique, global). Les actions sur le **référentiel** (création, proposition, révision, approbation, rejet, retrait, restauration d'une règle) sont en plus enregistrées dans `rule_activity`, le **journal d'activité** présenté aux admins, avec attribution (« qui a fait quoi »).
- Le retrait d'une règle est **réversible** : la règle passe `status = retired` (sortie du référentiel actif) mais reste consultable et **restaurable** ; son historique de versions n'est jamais détruit.

### 3.2 Cycle de vie

**Règle** : `pending` → (admin) → `approved` | `rejected`. Une modification d'une règle `approved` crée une nouvelle version `approved` et bascule l'ancienne `is_current = false`. Une règle approuvée peut être **retirée** (`status = retired`, sortie du référentiel actif) puis **restaurée** (`status = active`) par un admin — l'historique est toujours conservé.

**Revue** : `draft` → `in_progress` → `submitted` → (`validated` | `changes_requested`). Depuis `changes_requested`, l'auteur corrige et repasse en `submitted`.

**Point de remédiation** (`review_items` en KO/Partiel) : `todo` → `in_progress` → `done`.

---

## 4. Schéma SQL (PostgreSQL)

```sql
-- ========== Extensions ==========
CREATE EXTENSION IF NOT EXISTS "pgcrypto";      -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "pg_trgm";       -- similarité trigramme (fallback matching)

-- ========== Énumérations ==========
CREATE TYPE checklist_type AS ENUM ('powerbi', 'appbi', 'build');
CREATE TYPE user_role       AS ENUM ('user', 'reviewer', 'admin');
CREATE TYPE criticality     AS ENUM ('blocking', 'recommended', 'optional');
CREATE TYPE lifecycle_state AS ENUM ('pending', 'approved', 'rejected');
CREATE TYPE item_status     AS ENUM ('ok', 'ko', 'partial', 'na', 'unset');
CREATE TYPE progress_state  AS ENUM ('todo', 'in_progress', 'done');
CREATE TYPE review_status   AS ENUM ('draft','in_progress','submitted','validated','changes_requested');

-- ========== Utilisateurs ==========
CREATE TABLE users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email         CITEXT UNIQUE NOT NULL,           -- CITEXT : unicité insensible à la casse
    password_hash TEXT   NOT NULL,                  -- Argon2id
    display_name  TEXT   NOT NULL,
    role          user_role NOT NULL DEFAULT 'user',
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    email_verified BOOLEAN NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ========== Catégories (par référentiel) ==========
CREATE TABLE categories (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    checklist_type checklist_type NOT NULL,
    name           TEXT NOT NULL,
    order_index    INT  NOT NULL DEFAULT 0,
    UNIQUE (checklist_type, name)
);

-- ========== Règles : identité stable ==========
CREATE TABLE rules (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    checklist_type checklist_type NOT NULL,
    category_id    UUID NOT NULL REFERENCES categories(id) ON DELETE RESTRICT,
    status         TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','retired')),
    created_by     UUID REFERENCES users(id),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_rules_type      ON rules(checklist_type);
CREATE INDEX idx_rules_category  ON rules(category_id);

-- ========== Versions de règles : contenu IMMUABLE ==========
CREATE TABLE rule_versions (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_id        UUID NOT NULL REFERENCES rules(id) ON DELETE CASCADE,
    version_number INT  NOT NULL,
    text           TEXT NOT NULL,
    subs           JSONB NOT NULL DEFAULT '[]',      -- sous-points (les "->")
    criticality    criticality NOT NULL DEFAULT 'recommended',
    is_current     BOOLEAN NOT NULL DEFAULT TRUE,
    lifecycle      lifecycle_state NOT NULL DEFAULT 'pending',
    proposed_by    UUID REFERENCES users(id),
    reviewed_by    UUID REFERENCES users(id),
    review_comment TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (rule_id, version_number)
);
-- Une seule version courante par règle :
CREATE UNIQUE INDEX uniq_current_version
    ON rule_versions(rule_id) WHERE is_current;
CREATE INDEX idx_rv_lifecycle ON rule_versions(lifecycle) WHERE is_current;
-- Recherche floue sur le texte (fallback local du matching) :
CREATE INDEX idx_rv_text_trgm ON rule_versions USING gin (text gin_trgm_ops);

-- ========== Revues ==========
CREATE TABLE reviews (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_name    TEXT NOT NULL,
    checklist_type checklist_type NOT NULL,
    author_id      UUID NOT NULL REFERENCES users(id),
    status         review_status NOT NULL DEFAULT 'in_progress',
    compliance_score INT,                            -- recalculé au fil de l'eau, mis en cache
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    submitted_at   TIMESTAMPTZ,
    validated_at   TIMESTAMPTZ
);
CREATE INDEX idx_reviews_author ON reviews(author_id);
CREATE INDEX idx_reviews_status ON reviews(status);

-- ========== Items de revue (snapshot immuable) ==========
CREATE TABLE review_items (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    review_id        UUID NOT NULL REFERENCES reviews(id) ON DELETE CASCADE,
    rule_version_id  UUID NOT NULL REFERENCES rule_versions(id),  -- snapshot
    status           item_status NOT NULL DEFAULT 'unset',
    progress         progress_state NOT NULL DEFAULT 'todo',
    comment          TEXT DEFAULT '',
    risk             TEXT DEFAULT '',
    risk_comment     TEXT DEFAULT '',
    proposed_solution TEXT DEFAULT '',
    estimated_days   TEXT DEFAULT '',
    target_date      DATE,
    definition_of_done TEXT DEFAULT '',
    priority         TEXT DEFAULT '',
    responsible      TEXT DEFAULT '',
    last_update      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_items_review ON review_items(review_id);

-- ========== Validations tierces ==========
CREATE TABLE validations (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    review_id     UUID NOT NULL REFERENCES reviews(id) ON DELETE CASCADE,
    reviewer_id   UUID NOT NULL REFERENCES users(id),
    decision      TEXT NOT NULL CHECK (decision IN ('approved','rejected')),
    global_comment TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE validation_item_comments (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    validation_id  UUID NOT NULL REFERENCES validations(id) ON DELETE CASCADE,
    review_item_id UUID NOT NULL REFERENCES review_items(id) ON DELETE CASCADE,
    comment        TEXT NOT NULL
);

-- ========== Liens de partage ==========
CREATE TABLE share_links (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    review_id   UUID NOT NULL REFERENCES reviews(id) ON DELETE CASCADE,
    token       TEXT UNIQUE NOT NULL,                -- aléatoire, 256 bits, base64url
    created_by  UUID NOT NULL REFERENCES users(id),
    expires_at  TIMESTAMPTZ NOT NULL,
    revoked     BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_share_token ON share_links(token) WHERE NOT revoked;

-- Reviewers explicitement ciblés par un partage (un partage peut viser plusieurs
-- reviewers ; c'est ce qui ouvre la visibilité — jamais un accès de large périmètre).
CREATE TABLE share_targets (
    share_link_id UUID NOT NULL REFERENCES share_links(id) ON DELETE CASCADE,
    reviewer_id   UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    PRIMARY KEY (share_link_id, reviewer_id)
);
CREATE INDEX idx_share_targets_reviewer ON share_targets(reviewer_id);

-- ========== Paramètres applicatifs (modifiables par l'admin) ==========
CREATE TABLE app_settings (
    key         TEXT PRIMARY KEY,                    -- ex. 'retention_days'
    value       JSONB NOT NULL,
    updated_by  UUID REFERENCES users(id),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Valeur par défaut de rétention : 1 mois (modifiable par l'admin).
INSERT INTO app_settings(key, value) VALUES ('retention_days', '30');

-- ========== Config des connecteurs (admin) ==========
-- Un même 'kind' peut avoir plusieurs lignes (fournisseurs configurés) mais un
-- seul is_active à la fois — c'est ce qui permet à l'admin de BASCULER le type
-- d'IA ou de stockage à chaud, sans redéploiement.
CREATE TABLE integration_config (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kind          TEXT NOT NULL CHECK (kind IN ('matching','storage','sharepoint')),
    provider      TEXT NOT NULL,                     -- matching: 'local'|'mistral'|'enterprise'|'openai'|'azure'
                                                     -- storage : 'azure_blob'|'s3'|'internal'
    settings      JSONB NOT NULL DEFAULT '{}',       -- endpoints, régions, buckets, patterns (JAMAIS de secret ici)
    secret_ref    TEXT,                              -- référence vers le coffre à secrets (clé/chaîne de connexion)
    is_active     BOOLEAN NOT NULL DEFAULT FALSE,
    updated_by    UUID REFERENCES users(id),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Un seul fournisseur actif par type (matching / storage / sharepoint) :
CREATE UNIQUE INDEX uniq_active_integration
    ON integration_config(kind) WHERE is_active;

-- ========== Jobs d'import (traçabilité asynchrone) ==========
CREATE TABLE import_jobs (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    review_id     UUID REFERENCES reviews(id) ON DELETE SET NULL,
    source        TEXT NOT NULL CHECK (source IN ('upload','sharepoint')),
    file_ref      TEXT,                              -- clé S3/Blob
    status        TEXT NOT NULL DEFAULT 'queued'
                    CHECK (status IN ('queued','running','done','failed')),
    result        JSONB,                             -- {matched, ambiguous, filled, details[]}
    error         TEXT,
    created_by    UUID REFERENCES users(id),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at   TIMESTAMPTZ
);

-- ========== Journal d'audit (immuable) ==========
CREATE TABLE audit_log (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id     UUID REFERENCES users(id),
    action      TEXT NOT NULL,                       -- 'rule.approve', 'review.validate', ...
    entity      TEXT NOT NULL,
    entity_id   UUID,
    metadata    JSONB,
    ip          INET,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_entity ON audit_log(entity, entity_id);

-- ========== Journal d'activité du référentiel (visible par les admins) ==========
-- Distinct de audit_log (technique/global) : celui-ci est présenté dans l'UF admin
-- du référentiel, filtrable, avec attribution multi-admins (« qui a fait quoi »).
CREATE TABLE rule_activity (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    action          TEXT NOT NULL CHECK (action IN
                      ('rule_created','rule_proposed','rule_revised',
                       'rule_approved','rule_rejected','rule_retired','rule_restored')),
    rule_id         UUID REFERENCES rules(id) ON DELETE SET NULL,
    rule_version_id UUID REFERENCES rule_versions(id) ON DELETE SET NULL,
    actor_id        UUID NOT NULL REFERENCES users(id),
    rule_text       TEXT NOT NULL,                     -- libellé figé au moment de l'action (lisibilité)
    checklist_type  checklist_type NOT NULL,
    detail          TEXT,                              -- ex. 'v2 → v3', motif de rejet…
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_activity_type  ON rule_activity(checklist_type, created_at DESC);
CREATE INDEX idx_activity_rule  ON rule_activity(rule_id);
CREATE INDEX idx_activity_actor ON rule_activity(actor_id);
```


### 4.1 Règle d'or applicative (invariant)

Toute écriture qui « modifie » une règle **n'écrase jamais** `rule_versions`. Le service crée une nouvelle ligne (`version_number + 1`, `is_current = true`) et met l'ancienne à `is_current = false` dans **la même transaction**. Les `review_items` existants ne bougent pas : ils continuent de pointer vers l'ancienne version. C'est l'invariant qui garantit la comparabilité historique.

---

## 5. API REST

Base : `/api/v1`. Format JSON. Auth par `Authorization: Bearer <access_token>` sauf endpoints publics explicitement marqués. Toutes les réponses d'erreur suivent `{ "error": { "code": "...", "message": "..." } }`.

### 5.1 Authentification

L'authentification principale se fait via **Microsoft Entra ID** (OpenID Connect). L'email/mot de passe reste disponible en repli (comptes de service, tests) mais n'est pas le chemin nominal.

| Méthode | Chemin | Rôle | Description |
|---|---|---|---|
| GET | `/auth/login` | public | Redirige vers Entra ID (OIDC authorization code + PKCE). |
| GET | `/auth/callback` | public | Callback OIDC : valide le jeton Entra, crée/rapproche le compte, émet les jetons applicatifs. |
| POST | `/auth/refresh` | public (cookie) | Renouvelle l'access token. |
| POST | `/auth/logout` | auth | Révoque le refresh token + déconnexion Entra (front-channel logout). |
| POST | `/auth/login/local` | public | **Repli** email/mot de passe (si activé). Retourne `access_token` (15 min) + `refresh_token`. |
| POST | `/auth/password/*` | public | Réinitialisation mot de passe (uniquement pour les comptes locaux de repli). |

**Provisioning des comptes** : au premier login Entra, le compte est créé automatiquement (JIT provisioning) à partir des claims (email, nom). Le **rôle** applicatif (`user`/`reviewer`/`admin`) n'est **pas** dérivé aveuglément d'Entra : il est attribué par un admin dans l'app, ou mappé depuis des groupes Entra selon une correspondance définie par l'admin (ex. groupe `BI-Reviewers` → rôle `reviewer`). Ce mapping est configurable et auditée.

> Avantage de tout adosser à Entra : la même identité d'entreprise sert à l'application, au connecteur SharePoint (§7) et, le cas échéant, à l'IA interne (§6.3). Un seul point d'identité, une seule gouvernance.

### 5.2 Profil / utilisateurs

| Méthode | Chemin | Rôle | Description |
|---|---|---|---|
| GET | `/me` | auth | Profil courant. |
| PATCH | `/me` | auth | Modifier nom, prénom, e-mail (re-vérification si e-mail change). |
| POST | `/me/password` | auth | Changer son mot de passe (ancien requis). |
| GET | `/users` | admin | Lister les utilisateurs. |
| PATCH | `/users/{id}` | admin | Modifier le rôle / activer / désactiver un utilisateur. |

> Le changement de **rôle** est réservé à l'admin (au-delà du prototype où l'on simule les rôles). Un utilisateur ne peut pas s'auto-promouvoir.

### 5.3 Référentiel

| Méthode | Chemin | Rôle | Description |
|---|---|---|---|
| GET | `/referentials/{type}` | auth | Référentiel actif. Paramètres : `?q=` (recherche texte sur libellé + sous-points), `?sort=category\|recent\|criticality`. |
| GET | `/referentials/{type}/export` | auth | Export Excel formaté du référentiel. |
| POST | `/rules` | auth | Proposer une règle. Admin → `approved` direct ; sinon `pending`. |
| PATCH | `/rules/{id}` | admin | Reformuler → **crée une nouvelle version** (jamais d'écrasement). |
| POST | `/rules/{id}/retire` | admin | Retirer une règle (les revues passées restent intactes ; réversible). |
| POST | `/rules/{id}/restore` | admin | Restaurer une règle retirée. |
| GET | `/rules/retired?type=` | admin | Lister les règles retirées (historique consultable). |
| GET | `/rules/{id}/versions` | auth | Historique des versions d'une règle (navigable, triable). |
| GET | `/referentials/{type}/activity` | admin | **Journal d'activité** du référentiel : qui a créé / proposé / révisé / approuvé / rejeté / retiré / restauré. Filtrable par `?action=` et `?actor=`. |
| GET | `/rules/pending` | admin | File d'attente des propositions. Paramètre `?q=` (recherche). |
| POST | `/rules/{versionId}/approve` | admin | Approuver une proposition → entre au référentiel. |
| POST | `/rules/{versionId}/reject` | admin | Rejeter (avec motif). |
| POST | `/referentials/{type}/import` | auth | Importer un fichier de **règles** (fuzzy matching, cf. §6). |

### 5.4 Revues

| Méthode | Chemin | Rôle | Description |
|---|---|---|---|
| GET | `/reviews` | auth | `user` → les siennes ; `reviewer`/`admin` → visibles selon droits. Paramètres : `?q=` (recherche par nom de rapport ou type), `?status=`, `?type=`. |
| POST | `/reviews` | auth | Créer une revue (fige le snapshot des versions courantes). |
| GET | `/reviews/{id}` | auth+accès | Détail d'une revue. Renvoie **tous** les items groupés par catégorie, y compris ceux laissés `unset` par l'auteur, avec un compteur `unset_count`. Un reviewer/admin voit ainsi l'intégralité, même ce que l'auteur n'a pas renseigné. |
| PATCH | `/reviews/{id}` | auteur | Renommer, changer le statut (`submitted`…). |
| DELETE | `/reviews/{id}` | auteur/admin | Supprimer. |
| PATCH | `/reviews/{id}/items/{itemId}` | auteur | Mettre à jour statut / progress / bloc remédiation. |
| POST | `/reviews/{id}/import-answers` | auteur | **Pré-remplir les statuts** depuis un fichier (cf. §6.2). Asynchrone → renvoie un `import_job`. |
| GET | `/reviews/{id}/export` | auth+accès | Export Excel formaté de la revue (colonnes OK/KO/… cochées). |
| GET | `/import-jobs/{jobId}` | auth | Suivi d'un job d'import (statut + résultat). |

### 5.5 Validation tierce

| Méthode | Chemin | Rôle | Description |
|---|---|---|---|
| POST | `/reviews/{id}/share` | auteur | Génère un `share_link` (token, expiration). |
| DELETE | `/share/{id}` | auteur/admin | Révoque un lien. |
| GET | `/share/{token}` | public | Métadonnées de la revue partagée (lecture seule limitée). |
| POST | `/share/{token}/validate` | reviewer/admin authentifié | Approuver ou refuser (+ commentaires par point). |

> **Sécurité clé** : le endpoint de validation exige un **compte authentifié** avec le rôle `reviewer` ou `admin`. L'écran « Qui êtes-vous ? » du front ne fait qu'orienter l'affichage ; il ne confère aucun droit. L'autorisation réelle est vérifiée côté serveur à partir du JWT.

### 5.6 Monitoring

| Méthode | Chemin | Rôle | Description |
|---|---|---|---|
| GET | `/monitoring/portfolio` | auth | Agrégats portefeuille (scores, bloquants, avancement) filtrables. |
| GET | `/monitoring/reviews/{id}` | auth+accès | Détail d'avancement d'un projet (par catégorie, par remédiation). |

### 5.7 Configuration des connecteurs (admin)

Ces endpoints alimentent l'écran **Paramètres → section admin**, d'où l'admin choisit à la fois le **type d'IA** et le **type de stockage**, et bascule de l'un à l'autre à chaud.

| Méthode | Chemin | Rôle | Description |
|---|---|---|---|
| GET | `/admin/integrations` | admin | État de tous les connecteurs (matching, storage, SharePoint) : fournisseur actif + fournisseurs configurés. |
| GET | `/admin/integrations/matching/providers` | admin | Liste des fournisseurs d'IA disponibles (`local`, `mistral`, `enterprise`, `openai`, `azure`) + leur état. |
| PUT | `/admin/integrations/matching` | admin | **Choisir/basculer le type d'IA** (`provider`), régler les paramètres (endpoint, modèle) ; secret via coffre. Prend effet immédiatement. |
| POST | `/admin/integrations/matching/test` | admin | Tester la connexion au fournisseur d'IA avant de l'activer. |
| GET | `/admin/integrations/storage/providers` | admin | Liste des backends de stockage disponibles (`azure_blob`, `s3`, `internal`) + leur état. |
| PUT | `/admin/integrations/storage` | admin | **Choisir/basculer le type de stockage** (`provider`), régler les paramètres (compte, conteneur/bucket, région) ; chaîne de connexion via coffre. |
| POST | `/admin/integrations/storage/test` | admin | Tester l'accès au stockage (lecture/écriture d'un objet témoin) avant de l'activer. |
| PUT | `/admin/integrations/sharepoint` | admin | Définir les sources et motifs de fichiers. |
| POST | `/admin/integrations/sharepoint/sync` | admin | Déclencher une synchro manuelle. |
| GET | `/admin/settings` | admin | Lire les paramètres applicatifs (dont `retention_days`). |
| PUT | `/admin/settings/retention` | admin | Modifier la durée de rétention des fichiers (jours). Défaut : 30. |
| PUT | `/admin/settings/role-mapping` | admin | Mapper des groupes Entra ID vers des rôles applicatifs. |

> **Bascule à chaud (IA et stockage)** : changer de fournisseur écrit une nouvelle configuration active dans `integration_config` (un seul `is_active` par `kind`, garanti par l'index unique). Le service lit dynamiquement le fournisseur actif à chaque opération — **aucun redéploiement**. Il est recommandé de lancer le endpoint `/test` correspondant avant d'activer, et de conserver l'ancienne configuration (désactivée) pour un retour arrière immédiat.
>
> **Note sur le changement de stockage** : basculer de backend de stockage n'entraîne pas de migration automatique des fichiers existants (les anciens fichiers restent lisibles depuis leur backend d'origine tant qu'ils ne sont pas purgés par la rétention). Une tâche de migration optionnelle peut être déclenchée si l'admin souhaite déplacer l'existant.

---

## 6. Connecteur de correspondance (matching) et IA

C'est le cœur du besoin exprimé : comprendre des fichiers Excel hétérogènes et associer chaque ligne à la bonne règle, même quand la phrase change ou comporte des fautes, et détecter le statut (OK/KO/Partiel/N/A) même exprimé autrement. Le connecteur est **pluggable** : un fournisseur par défaut *local* (gratuit, sans réseau) et des fournisseurs *IA* optionnels activables par l'admin.

### 6.1 Interface commune

Tous les fournisseurs implémentent la même interface, ce qui permet de les interchanger sans toucher au reste du code :

```python
class MatchProvider(Protocol):
    def match_rules(
        self,
        imported_texts: list[str],
        referential: list[RuleRef],   # (rule_version_id, text)
    ) -> list[MatchResult]:
        """Associe chaque texte importé à la règle la plus proche + un score [0,1]."""

    def detect_status(self, raw: str) -> ItemStatus | None:
        """Déduit OK/KO/Partiel/N/A d'une valeur cellule, même formulée librement."""
```

`MatchResult = { imported_index, rule_version_id | None, confidence, verdict }`
où `verdict ∈ {identical, probable, new}` selon les seuils.

### 6.2 Fournisseur local (défaut) — porté depuis le prototype

Le moteur sémantique du prototype est réimplémenté en Python. Étapes :

1. **Normalisation** : minuscules, suppression des accents, ponctuation, mots-vides français/anglais.
2. **Canonicalisation par synonymes métier** : un dictionnaire de familles de sens (Power BI / DAX / Power Query) réduit les variantes à un terme canonique (« measures » → « mesure », « cacher » → « masquer »…).
3. **Pondération IDF** : les tokens rares et distinctifs (« bidirectionnelle », « explicite ») pèsent davantage que les tokens fréquents (« dax », « rapport »), ce qui limite les faux positifs.
4. **Score** : combinaison Jaccard pondéré + couverture du sens de la règle de référence.
5. **Robustesse d'entrée Excel** : détection dynamique de la colonne de texte (chaînes les plus longues), gestion des booléens stockés en texte (`'True'`, `x`, `oui`…), colonnes de statut détectées où qu'elles soient.

En Python, on s'appuie sur **`rapidfuzz`** (distances rapides) et un lexique de synonymes maintenable en base ou en fichier de config.

**Seuils par défaut** (ajustables) : `≥ 0.95` identique · `0.70–0.95` à confirmer par l'utilisateur · `< 0.70` nouvelle règle. Pour le *pré-remplissage de statuts*, on retient le meilleur match s'il dépasse un seuil bas **et** se détache nettement du second candidat.

### 6.3 Fournisseur IA (optionnel, activable par l'admin)

Quand l'admin sélectionne un fournisseur IA, l'appel se fait **côté serveur, dans un worker asynchrone**, jamais depuis le navigateur. Le connecteur envoie au modèle : la liste des règles du référentiel + les lignes importées, avec une consigne de correspondance stricte, et attend un JSON structuré (`imported_index → rule_version_id + statut + confiance`).

**Fournisseur par défaut : Mistral (EU)** — retenu pour la souveraineté des données. L'architecture pluggable permet à l'admin de **basculer à tout moment, par simple configuration (sans redéploiement)**, vers un autre fournisseur, en particulier **l'IA interne de l'entreprise**.

Points de conception :

- **Fournisseurs supportés** :
  - `mistral` — **par défaut**, endpoint EU.
  - `enterprise` — **IA interne de l'entreprise** : n'importe quel endpoint privé exposant une API compatible (souvent OpenAI-compatible). L'admin fournit l'URL de l'endpoint interne et la référence du secret. Idéal quand l'entreprise dispose de son propre modèle hébergé — les données ne quittent jamais le réseau interne.
  - `openai`, `azure` — disponibles si besoin.
  - Chaque fournisseur est un adaptateur derrière l'interface `MatchProvider` ; **changer de fournisseur = changer une ligne de configuration**, rien d'autre.
- **Secrets** : la clé / le jeton d'accès n'est **jamais** stocké dans `integration_config.settings` ni renvoyé au front. Il vit dans **Azure Key Vault**, référencé par `secret_ref`.
- **Confidentialité** : n'envoyer au modèle **que** les libellés de règles et de lignes, jamais de données d'entreprise sensibles. Avec le fournisseur `enterprise`, les données restent intégralement sur le réseau interne. Journaliser les appels (sans le contenu) pour l'audit et le coût.
- **Repli** : si l'appel IA échoue ou dépasse un délai, on retombe automatiquement sur le fournisseur local. L'import n'échoue jamais totalement.
- **Coût maîtrisé** : batching des lignes, cache des correspondances déjà vues, limite de débit.

### 6.4 Flux d'import de réponses (pré-remplissage)

```
Front (upload .xlsx)
   → POST /reviews/{id}/import-answers        (fichier → stockage S3, crée import_job=queued)
   → 202 Accepted { job_id }

Worker Celery
   1. Télécharge le fichier, le parse (openpyxl) de façon robuste
   2. Pour chaque item de la revue : match via le provider actif (local ou IA)
   3. Détecte le statut de chaque ligne importée
   4. Applique les statuts au-dessus du seuil ; marque les cas ambigus
   5. Écrit le résultat dans import_jobs.result, statut=done

Front (polling GET /import-jobs/{job_id})
   → affiche « N statuts pré-remplis, M à vérifier »
```

Les cas *ambigus* (score intermédiaire) ne sont pas appliqués silencieusement : ils sont retournés au front pour confirmation par l'utilisateur, comme dans le prototype.

---

## 7. Connecteur SharePoint / Excel en ligne

Permet de récupérer automatiquement des fichiers de revue depuis SharePoint / OneDrive selon des règles définies par l'admin, puis de pré-remplir les revues correspondantes.

### 7.1 Authentification Microsoft

- **Microsoft Graph API** avec **OAuth 2.0 client credentials** (application enregistrée dans Entra ID) ou **on-behalf-of** si l'accès doit être au nom de l'utilisateur.
- Permissions Graph minimales : `Sites.Read.All` / `Files.Read.All` (lecture seule), accordées par un admin Microsoft du tenant.
- Jetons stockés côté serveur, chiffrés ; jamais exposés au front.

### 7.2 Configuration (par l'admin)

Dans `integration_config` (kind=`sharepoint`), l'admin définit une liste de sources :

```json
{
  "sources": [
    { "name": "Revues Power BI",
      "site": "https://contoso.sharepoint.com/sites/BI",
      "drive": "Documents",
      "folder": "/Revues",
      "pattern": "PR_*.xlsx",
      "target_checklist": "powerbi" }
  ]
}
```

### 7.3 Flux de synchronisation

```
Déclencheur (manuel ou planifié)
   → Worker liste les fichiers correspondant au pattern via Graph
   → Pour chaque fichier nouveau/modifié :
        - télécharge le contenu
        - parse + match (réutilise le connecteur §6)
        - crée ou met à jour la revue cible, pré-remplit les statuts
        - trace un import_job (source='sharepoint')
   → Notifie les utilisateurs concernés
```

La logique de parsing et de matching est **partagée** avec l'import manuel : un seul moteur, deux sources d'entrée.

---

## 7bis. Connecteur de stockage (pluggable, configurable par l'admin)

Comme le connecteur d'IA, le stockage des fichiers (Excel importés, exports générés) passe par une **interface commune** avec plusieurs implémentations interchangeables. L'admin choisit et bascule le backend depuis ses paramètres, à chaud, sans redéploiement.

### 7bis.1 Interface commune

```python
class StorageProvider(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> str:  # retourne une référence
        ...
    def get(self, ref: str) -> bytes:
        ...
    def delete(self, ref: str) -> None:
        ...
    def presigned_url(self, ref: str, ttl_seconds: int) -> str | None:
        ...   # URL temporaire de téléchargement direct, si le backend le permet
```

Tout le code applicatif manipule des **références opaques** (`ref`) et ne connaît jamais le backend concret. Changer de fournisseur ne change pas le reste du code.

### 7bis.2 Backends supportés

| Provider | Usage | Paramètres (`settings`) | Secret (`secret_ref`) |
|---|---|---|---|
| `azure_blob` | **Défaut** ; cohérent avec l'hébergement Azure | compte, conteneur | chaîne de connexion / identité managée |
| `s3` | Compatibilité AWS ou S3-compatible (MinIO…) | région, bucket, endpoint | clés d'accès |
| `internal` | Stockage interne on-prem / volume monté | chemin de base, URL de service | jeton éventuel |

### 7bis.3 Bascule et sécurité

- Un seul backend `is_active` à la fois (index unique sur `integration_config` où `kind='storage'`).
- Le service résout le fournisseur actif **à chaque opération** → bascule immédiate.
- Le endpoint `POST /admin/integrations/storage/test` écrit puis relit un objet témoin pour valider la configuration **avant** activation.
- Les chaînes de connexion / clés vivent dans **Key Vault**, jamais en base ni renvoyées au front.
- **Rétention** : la purge (§9) appelle `delete()` via l'interface, quel que soit le backend — la logique de rétention est indépendante du stockage choisi.
- **Migration** : changer de backend n'impose pas de déplacer l'existant (les anciens `ref` restent résolus par leur backend d'origine jusqu'à purge). Une tâche de migration optionnelle est disponible si l'admin veut consolider.

---

## 8. Modèle de permissions (RBAC)

L'autorisation est vérifiée **côté serveur à chaque endpoint**, à partir du rôle porté par le JWT. Le rôle n'est jamais décidé par le client.

| Capacité | user | reviewer | admin |
|---|:---:|:---:|:---:|
| Créer / remplir ses revues | ✔ | ✔ | ✔ |
| Voir ses propres revues | ✔ | ✔ | ✔ |
| Voir les revues qui lui sont partagées ou soumises | ✔ (lecture) | ✔ | ✔ |
| Voir **toutes** les revues (accès global) | ✘ | ✘ | ✔ |
| Proposer une règle | ✔ (→ pending) | ✔ (→ pending) | ✔ (→ approuvée) |
| Voir une revue **en entier**, y compris points non renseignés | ✔ (les siennes) | ✔ (partagées) | ✔ |
| Approuver / rejeter une règle | | | ✔ |
| Reformuler une règle (nouvelle version) | | | ✔ |
| Retirer / restaurer une règle | | | ✔ |
| Consulter le journal d'activité du référentiel | | | ✔ |
| Valider / refuser une revue | | ✔ | ✔ |
| Gérer les utilisateurs / rôles | | | ✔ |
| Configurer les connecteurs (**type d'IA, type de stockage**, SharePoint) | | | ✔ |

> L'admin a **tous les droits partout** (conformément à la décision produit). Le reviewer valide les revues qui lui sont partagées ou soumises. L'utilisateur agit sur ses propres revues et peut proposer des règles.

**Politique de visibilité reviewer (arrêtée)** : un reviewer accède **uniquement** aux revues qui lui ont été **explicitement partagées ou soumises**. Un même partage peut cibler plusieurs reviewers, mais il n'existe **aucun accès de large périmètre** (pas de « toutes les revues de l'équipe », pas d'accès global). Techniquement, la visibilité d'une revue pour un reviewer découle de l'existence d'un `share_link` le ciblant ou d'une soumission le désignant — vérifiée à chaque requête. Seul l'admin dispose d'un accès global.

---

## 9. Sécurité

Exigences non négociables, en plus du RBAC :

- **Mots de passe** : hachage **Argon2id** (paramètres coût mémoire/temps adaptés) ; jamais en clair, jamais journalisés.
- **Jetons** : access token JWT court (15 min), refresh token en cookie `httpOnly`+`Secure`+`SameSite=Strict`, révocable. Rotation des refresh tokens.
- **Injection SQL** : exclusivement via requêtes paramétrées / ORM. Aucune concaténation de SQL.
- **Uploads Excel** : validation type MIME + extension + taille max + nombre de lignes max ; parsing dans un worker isolé ; fichiers stockés hors du webroot.
- **Injection de formule Excel (à l'export)** : préfixer d'une apostrophe toute cellule commençant par `= + - @` (déjà appliqué dans le prototype).
- **Liens de partage** : token aléatoire 256 bits, expiration obligatoire, révocable ; l'accès au contenu exige tout de même l'authentification pour toute action d'écriture.
- **Rate limiting** : sur `/auth/login`, `/auth/register`, les imports et les appels IA.
- **CORS** restreint aux origines connues ; **CSRF** géré pour les flux cookie.
- **Secrets** : dans un coffre, jamais en base applicative ni dans le code ni renvoyés au front.
- **Audit** : `audit_log` immuable pour toute action sensible (validation, approbation de règle, changement de rôle, configuration de connecteur), avec IP et horodatage.
- **TLS partout**, HSTS activé.
- **RGPD** : les appels IA n'envoient que des libellés de règles ; fournisseur **Mistral (EU)** par défaut, ou **IA interne** (données jamais sorties du réseau) ; droit à l'effacement des comptes.
- **Rétention** : les fichiers Excel importés et les `import_jobs` associés sont purgés automatiquement après **`retention_days` jours (défaut 30, modifiable par l'admin** via `/admin/settings/retention`). Une **tâche planifiée quotidienne** (Celery beat) appelle `StorageProvider.delete()` (quel que soit le backend actif) et supprime les enregistrements associés. Les revues et leur contenu ne sont pas concernés par cette purge — seule la matière première d'import l'est.

---

## 10. Feuille de route de livraison

Découpage en incréments livrables, chacun testable indépendamment.

**Lot 1 — Fondations (2–3 sem.)**
Schéma SQL + migrations Alembic · **Auth Microsoft Entra ID (OIDC) + provisioning JIT + mapping groupes→rôles** · repli email/mot de passe optionnel · CRUD utilisateurs & profil · RBAC de base · tests d'intégration.

**Lot 2 — Référentiel versionné (2 sem.)**
Import du seed (v2 + v3) · CRUD règles avec versionnement immuable · file d'attente d'approbation admin · **retrait/restauration de règles** · **journal d'activité (`rule_activity`) avec attribution** · **recherche + tri** · export Excel du référentiel.

**Lot 3 — Revues (2–3 sem.)**
Création avec snapshot · remplissage items (statut, progress, remédiation) · score de conformité · **vue complète (points non renseignés inclus)** · **recherche de revues** · export Excel formaté (colonnes cochées) · suppression.

**Lot 4 — Validation tierce (1–2 sem.)**
Liens de partage **ciblant des reviewers précis (`share_targets`)** · endpoint de validation authentifié · commentaires par point · cycle `changes_requested`.

**Lot 5 — Import intelligent + stockage pluggable (2–3 sem.)**
Worker asynchrone · parsing Excel robuste · connecteur de matching local (port du moteur sémantique) · pré-remplissage des statuts · gestion des cas ambigus · **connecteur de stockage pluggable (Azure Blob / S3 / interne) + config admin + test de connexion**.

**Lot 6 — Connecteur IA (1–2 sem.)**
Interface pluggable · adaptateurs **Mistral (défaut) / entreprise / OpenAI / Azure** · **bascule du type d'IA par l'admin (à chaud)** · configuration + coffre à secrets · repli automatique sur le local.

**Lot 7 — SharePoint (2 sem.)**
Intégration Graph API · configuration des sources · synchro planifiée · réutilisation du moteur d'import.

**Lot 8 — Monitoring & durcissement (2 sem.)**
Endpoints d'agrégation · rate limiting · audit complet · revue de sécurité · charge et performances.

---

## 11. Décisions arrêtées

Les points laissés ouverts en v1.0 sont désormais tranchés et intégrés au document :

1. **Visibilité reviewer** — strictement limitée aux revues **explicitement partagées ou soumises**. Un partage peut cibler plusieurs reviewers (table `share_targets`) mais aucun accès de large périmètre n'existe. Seul l'admin a un accès global. (§8)
2. **Identité** — outil **interne** → **Microsoft Entra ID (SSO OIDC)** dès le Lot 1, avec provisioning automatique et mapping groupes Entra → rôles applicatifs. Email/mot de passe en repli optionnel. (§2.1, §5.1)
3. **IA — configurable par l'admin** — **Mistral (EU) par défaut** ; l'admin peut **basculer le type d'IA à chaud** (vers l'**IA interne de l'entreprise** ou un autre fournisseur), **sans redéploiement**. (§5.7, §6.3)
4. **Stockage — configurable par l'admin** — **Azure Blob par défaut** ; l'admin peut **basculer le type de stockage** (S3, stockage interne) depuis ses paramètres, via une couche d'abstraction commune, avec test de connexion avant activation. (§5.7, §7bis)
5. **Hébergement** — **Azure** (Container Apps / AKS), aligné avec Entra ID et SharePoint ; secrets dans **Key Vault**. (§2.1)
6. **Rétention** — fichiers importés purgés après **30 jours par défaut, modifiable par l'admin** ; tâche planifiée quotidienne indépendante du backend de stockage ; les revues ne sont jamais purgées. (§5.7, §9)

Fonctionnalités du prototype désormais reflétées dans la conception : **vue complète d'une revue** pour reviewers/admins (points non renseignés inclus, §5.4), **journal d'activité** du référentiel avec attribution (`rule_activity`, §4/§5.3), **retrait/restauration** de règles avec historique conservé (§3.2, §5.3), **recherche** dans revues/référentiel/validation (§5.3, §5.4).

### Prochaines étapes proposées

Le document de conception est complet et cohérent. Pour démarrer le développement, deux options concrètes :

- **Générer les migrations Alembic du Lot 1** (schéma exécutable prêt à lancer) accompagnées du squelette FastAPI (auth Entra, RBAC, modèles SQLAlchemy).
- **Coder le connecteur de matching local en Python** (port fidèle du moteur sémantique du prototype, avec `rapidfuzz`), directement réutilisable dans le worker d'import.

---

*Fin du document — v1.2.*
