"""
Résolution dynamique des connecteurs actifs (Lot 5).

Le service lit le fournisseur ACTIF depuis `integration_config` à chaque
opération — c'est ce qui permet à l'admin de basculer d'IA ou de stockage à
chaud, sans redéploiement (un seul `is_active` par `kind`, garanti par l'index
unique). En l'absence de configuration, on retombe sur les défauts sûrs :
matching = local, storage = internal.

Les secrets ne sont jamais lus depuis la base : `secret_ref` pointe vers le
coffre. `_resolve_secret` encapsule cette résolution (ici, best-effort via
l'environnement ; en production, Azure Key Vault).
"""
import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.integration import IntegrationConfig
from app.services.matching.base import MatchProvider
from app.services.matching.local import LocalMatchProvider
from app.services.matching.ai import AIMatchProvider
from app.services.storage.providers import (
    StorageProvider,
    InternalStorageProvider,
    AzureBlobStorageProvider,
    S3StorageProvider,
)


def _active_config(db: Session, kind: str) -> IntegrationConfig | None:
    return db.scalar(
        select(IntegrationConfig).where(
            IntegrationConfig.kind == kind,
            IntegrationConfig.is_active.is_(True),
        )
    )


def _resolve_secret(secret_ref: str | None) -> str | None:
    """
    Résout un secret à partir de sa référence de coffre.

    Production : Azure Key Vault via l'identité managée. Ici, best-effort par
    variable d'environnement (`secret_ref` = nom de variable), pour permettre les
    tests d'intégration sans coffre.
    """
    if not secret_ref:
        return None
    return os.environ.get(secret_ref)


# --------------------------------------------------------------------------
# Matching
# --------------------------------------------------------------------------
def get_active_match_provider(db: Session) -> MatchProvider:
    """Construit le fournisseur de matching actif (défaut : local)."""
    cfg = _active_config(db, "matching")
    if cfg is None or cfg.provider == "local":
        return LocalMatchProvider()

    settings = cfg.settings or {}
    return AIMatchProvider(
        cfg.provider,
        endpoint=settings.get("endpoint"),
        model=settings.get("model"),
        secret=_resolve_secret(cfg.secret_ref),
        timeout_seconds=float(settings.get("timeout_seconds", 20.0)),
    )


# --------------------------------------------------------------------------
# Stockage
# --------------------------------------------------------------------------
def get_active_storage_provider(db: Session) -> StorageProvider:
    """Construit le fournisseur de stockage actif (défaut : internal)."""
    cfg = _active_config(db, "storage")
    if cfg is None or cfg.provider == "internal":
        base = (cfg.settings or {}).get("base_path") if cfg else None
        return InternalStorageProvider(base_path=base or "/var/lib/pr-review/storage")

    settings = cfg.settings or {}
    secret = _resolve_secret(cfg.secret_ref)

    if cfg.provider == "azure_blob":
        return AzureBlobStorageProvider(
            account=settings.get("account", ""),
            container=settings.get("container", "pr-review"),
            connection_string=secret or "",
        )
    if cfg.provider == "s3":
        # La clé/le secret S3 peut être passé via secret_ref ("access:secret").
        access_key = secret_key = None
        if secret and ":" in secret:
            access_key, _, secret_key = secret.partition(":")
        return S3StorageProvider(
            bucket=settings.get("bucket", "pr-review"),
            region=settings.get("region"),
            endpoint_url=settings.get("endpoint_url"),
            access_key=access_key,
            secret_key=secret_key,
        )

    # Fournisseur inconnu → repli interne sûr.
    return InternalStorageProvider()


def storage_provider_by_name(name: str, settings: dict, secret: str | None) -> StorageProvider:
    """Construit un fournisseur nommé (utilisé par le endpoint de test admin)."""
    if name == "internal":
        return InternalStorageProvider(base_path=settings.get("base_path") or "/var/lib/pr-review/storage")
    if name == "azure_blob":
        return AzureBlobStorageProvider(
            account=settings.get("account", ""),
            container=settings.get("container", "pr-review"),
            connection_string=secret or "",
        )
    if name == "s3":
        access_key = secret_key = None
        if secret and ":" in secret:
            access_key, _, secret_key = secret.partition(":")
        return S3StorageProvider(
            bucket=settings.get("bucket", "pr-review"),
            region=settings.get("region"),
            endpoint_url=settings.get("endpoint_url"),
            access_key=access_key,
            secret_key=secret_key,
        )
    raise ValueError(f"Backend de stockage inconnu : {name!r}")
