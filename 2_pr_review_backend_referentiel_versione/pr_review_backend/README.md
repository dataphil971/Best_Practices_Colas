# PR Review — Backend (Lot 1 : Fondations)

Socle du backend de la plateforme de Peer Review Power BI : base de données,
authentification **Microsoft Entra ID** (SSO OIDC) avec repli local, contrôle
d'accès par rôle (RBAC), et gestion des utilisateurs.

Ce lot pose les fondations. Les lots suivants (référentiel versionné, revues,
validation, import intelligent, connecteurs IA/stockage) s'appuient dessus.

---

## Pile technique

- **FastAPI** (Python 3.12) — API REST, OpenAPI auto-généré (`/docs`)
- **PostgreSQL 16** + **SQLAlchemy 2** + **Alembic** (migrations versionnées)
- **Microsoft Entra ID** (OpenID Connect) + repli email/mot de passe (**Argon2id**)
- **JWT** applicatifs (access court + refresh en cookie httpOnly)

---

## Démarrage rapide (Docker)

```bash
cp .env.example .env          # renseigner si besoin (Entra ID facultatif en dev)
docker compose up --build
```

L'API applique les migrations puis démarre sur http://localhost:8000
Documentation interactive : http://localhost:8000/docs

## Démarrage manuel (sans Docker)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# PostgreSQL doit tourner et DATABASE_URL être renseignée
alembic upgrade head          # crée les tables
uvicorn app.main:app --reload
```

---

## Structure du projet

```
app/
  core/        config, base de données, sécurité (hachage, JWT)
  models/      modèles SQLAlchemy (users) + énumérations
  schemas/     schémas Pydantic (validation entrées/sorties)
  auth/        Entra ID (OIDC), provisioning, dépendances RBAC
  services/    mapping groupe Entra -> rôle
  api/routes/  auth, profil (/me), utilisateurs (admin)
  main.py      assemblage de l'application
alembic/       migrations (0001 : table users)
tests/         tests unitaires (sécurité, RBAC)
```

---

## Endpoints du Lot 1

| Méthode | Chemin | Accès | Rôle |
|---|---|---|---|
| GET | `/health` | public | — |
| GET | `/api/v1/auth/login` | public | Démarre le SSO Entra ID |
| GET | `/api/v1/auth/callback` | public | Callback OIDC → jetons applicatifs |
| POST | `/api/v1/auth/register` | public | Repli local (si activé) |
| POST | `/api/v1/auth/login/local` | public | Repli local |
| POST | `/api/v1/auth/refresh` | cookie | Renouvelle l'access token |
| POST | `/api/v1/auth/logout` | auth | Déconnexion |
| GET | `/api/v1/me` | auth | Profil courant |
| PATCH | `/api/v1/me` | auth | Modifier nom / e-mail |
| POST | `/api/v1/me/password` | auth | Changer mot de passe (comptes locaux) |
| GET | `/api/v1/users` | admin | Lister / rechercher les utilisateurs |
| PATCH | `/api/v1/users/{id}/role` | admin | Changer le rôle |
| PATCH | `/api/v1/users/{id}/active` | admin | Activer / désactiver |

### Lot 2 — Référentiel versionné

| Méthode | Route | Rôle | Description |
|---|---|---|---|
| GET | `/api/v1/referentials/{type}` | auth | Référentiel actif. `?q=` (recherche libellé + sous-points), `?sort=category\|recent\|criticality` |
| GET | `/api/v1/referentials/{type}/export` | auth | Export Excel formaté du référentiel |
| GET | `/api/v1/referentials/{type}/categories` | auth | Lister les catégories d'un référentiel |
| POST | `/api/v1/referentials/{type}/categories` | admin | Créer une catégorie |
| GET | `/api/v1/referentials/{type}/activity` | admin | Journal d'activité. `?action=` et `?actor=` |
| POST | `/api/v1/rules` | auth | Proposer une règle (admin → approuvée ; sinon `pending`) |
| PATCH | `/api/v1/rules/{rule_id}` | admin | Reformuler → **nouvelle version** (jamais d'écrasement) |
| GET | `/api/v1/rules/pending` | admin | File d'attente des propositions. `?q=` |
| POST | `/api/v1/rules/{version_id}/approve` | admin | Approuver une proposition |
| POST | `/api/v1/rules/{version_id}/reject` | admin | Rejeter (motif obligatoire) |
| POST | `/api/v1/rules/{rule_id}/retire` | admin | Retirer une règle (réversible) |
| POST | `/api/v1/rules/{rule_id}/restore` | admin | Restaurer une règle retirée |
| GET | `/api/v1/rules/retired?type=` | admin | Lister les règles retirées |
| GET | `/api/v1/rules/{rule_id}/versions` | auth | Historique des versions. `?sort=recent\|asc` |

**Import initial du référentiel** (102 règles, 15 catégories, issues des templates v2 + v3) :

```bash
python -m app.seed_referential                    # attribué à un admin « système »
python -m app.seed_referential --actor a@cds.com  # attribué à un admin réel
```

Le seed est **idempotent** : relançable sans créer de doublons.

---

## Sécurité (rappel des principes appliqués)

- Le **rôle n'est jamais décidé par le client** : il est lu du jeton signé puis
  revérifié en base à chaque requête (voir `app/auth/deps.py`).
- Mots de passe hachés en **Argon2id**, jamais stockés en clair.
- Secrets (JWT, Entra, base) via variables d'environnement → **Azure Key Vault**
  en production, jamais dans le code.
- Refresh token en cookie `httpOnly` + `SameSite=strict`, avec rotation.

---

## Tests

```bash
pytest
```

Les tests du Lot 1 couvrent la logique sans base de données (hachage, JWT,
mapping de rôles). Le Lot 2 ajoute `tests/test_referential.py`, qui valide les
invariants du versionnement immuable sur une base SQLite en mémoire :
immuabilité des versions, unicité de la version courante, transitions de cycle
de vie (approbation / rejet), retrait / restauration, et traçabilité dans le
journal d'activité. **8 tests au total, tous verts.**

---

## Notes d'implémentation

- Le cache mémoire des états OIDC (`_pending_states`) et l'absence de liste de
  révocation des refresh tokens sont des simplifications de Lot 1 : à remplacer
  par **Redis** en production (déjà prévu dans la spec pour les tâches async).
- Le mapping groupe Entra → rôle démarre depuis la configuration ; il deviendra
  modifiable par l'admin via `app_settings` dans un lot ultérieur.
