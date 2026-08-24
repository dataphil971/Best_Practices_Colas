"""
Routes admin des intégrations (Lot 5, §5.7).

Permettent à l'admin de :
  - consulter l'état de tous les connecteurs (fournisseur actif + configurés) ;
  - choisir/basculer le fournisseur de matching (IA) et de stockage ;
  - tester la connexion AVANT activation.

Bascule à chaud : activer un fournisseur écrit une config active dans
`integration_config` (un seul `is_active` par `kind`). Le reste du code lit le
fournisseur actif à chaque opération — aucun redéploiement. Les secrets ne sont
jamais stockés en base ni renvoyés au front (seul `secret_ref` est conservé).
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.auth.deps import require_admin
from app.models.user import User
from app.models.integration import IntegrationConfig
from app.schemas.integration import (
    IntegrationOut,
    IntegrationsState,
    MatchingConfigIn,
    StorageConfigIn,
    ConnectionTestResult,
)
from app.schemas.sharepoint import (
    SharePointConfigIn,
    SharePointConfigOut,
    SharePointSource,
    SyncResult,
)
from app.services import integrations as integ

router = APIRouter(prefix="/admin/integrations", tags=["admin — intégrations"])

_STORAGE_PROVIDERS = ("internal", "azure_blob", "s3")
_MATCHING_PROVIDERS = ("local", "mistral", "enterprise", "openai", "azure")


def _deactivate_others(db: Session, kind: str) -> None:
    """Désactive tous les fournisseurs actifs d'un type (bascule exclusive)."""
    for cfg in db.scalars(
        select(IntegrationConfig).where(
            IntegrationConfig.kind == kind, IntegrationConfig.is_active.is_(True)
        )
    ).all():
        cfg.is_active = False
    db.flush()


def _upsert(
    db: Session, *, kind: str, provider: str, settings: dict,
    secret_ref: str | None, activate: bool, admin: User,
) -> IntegrationConfig:
    """Crée ou met à jour la config (kind, provider) et gère l'activation exclusive."""
    cfg = db.scalar(
        select(IntegrationConfig).where(
            IntegrationConfig.kind == kind, IntegrationConfig.provider == provider
        )
    )
    if cfg is None:
        cfg = IntegrationConfig(kind=kind, provider=provider)
        db.add(cfg)
    cfg.settings = settings or {}
    if secret_ref is not None:
        cfg.secret_ref = secret_ref
    cfg.updated_by = admin.id

    if activate:
        db.flush()
        _deactivate_others(db, kind)
        cfg.is_active = True
    db.flush()
    return cfg


# --------------------------------------------------------------------------
# État global
# --------------------------------------------------------------------------
@router.get("", response_model=IntegrationsState)
def get_integrations_state(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """État de tous les connecteurs : fournisseur actif + fournisseurs configurés."""
    all_cfg = db.scalars(select(IntegrationConfig)).all()
    by_kind: dict[str, list[IntegrationOut]] = {"matching": [], "storage": [], "sharepoint": []}
    active = {"matching": "local", "storage": "internal"}
    for c in all_cfg:
        by_kind.setdefault(c.kind, []).append(IntegrationOut.model_validate(c))
        if c.is_active and c.kind in active:
            active[c.kind] = c.provider
    return IntegrationsState(
        matching=by_kind["matching"],
        storage=by_kind["storage"],
        sharepoint=by_kind.get("sharepoint", []),
        active_matching=active["matching"],
        active_storage=active["storage"],
    )


# --------------------------------------------------------------------------
# Matching (IA)
# --------------------------------------------------------------------------
@router.put("/matching", response_model=IntegrationOut)
def configure_matching(
    payload: MatchingConfigIn,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Choisir/basculer le fournisseur de matching (local ou IA)."""
    cfg = _upsert(
        db, kind="matching", provider=payload.provider, settings=payload.settings,
        secret_ref=payload.secret_ref, activate=payload.activate, admin=admin,
    )
    from app.services import audit
    audit.record(db, action="matching.configure", entity="integration_config",
                 entity_id=cfg.id, user_id=admin.id,
                 metadata={"provider": payload.provider, "active": payload.activate})
    db.commit()
    db.refresh(cfg)
    return cfg


@router.post("/matching/test", response_model=ConnectionTestResult)
def test_matching(
    payload: MatchingConfigIn,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Teste un fournisseur de matching avant activation.

    Le fournisseur local est toujours opérationnel. Pour un fournisseur IA, on
    vérifie qu'il peut produire un résultat (avec repli local en cas d'échec).
    """
    from app.services.matching.local import LocalMatchProvider
    from app.services.matching.ai import AIMatchProvider
    from app.services.matching.base import RuleRef

    if payload.provider == "local":
        return ConnectionTestResult(ok=True, provider="local",
                                    detail="Moteur local opérationnel.")

    secret = integ._resolve_secret(payload.secret_ref)
    provider = AIMatchProvider(
        payload.provider,
        endpoint=payload.settings.get("endpoint"),
        model=payload.settings.get("model"),
        secret=secret,
        timeout_seconds=float(payload.settings.get("timeout_seconds", 20.0)),
    )
    sample_ref = [RuleRef(rule_version_id="test", text="Vérifier les types de données")]
    try:
        provider.match_rules(["types de donnees"], sample_ref)
        operational = provider._is_operational()
        return ConnectionTestResult(
            ok=True,
            provider=payload.provider,
            detail=(
                "Connexion IA opérationnelle."
                if operational
                else "Configuration incomplète : repli local actif (endpoint/secret manquant)."
            ),
        )
    except Exception as exc:  # noqa: BLE001
        return ConnectionTestResult(ok=False, provider=payload.provider, detail=str(exc)[:300])


# --------------------------------------------------------------------------
# Stockage
# --------------------------------------------------------------------------
@router.get("/storage/providers", response_model=list[str])
def list_storage_providers(_: User = Depends(require_admin)):
    """Liste des backends de stockage disponibles."""
    return list(_STORAGE_PROVIDERS)


@router.put("/storage", response_model=IntegrationOut)
def configure_storage(
    payload: StorageConfigIn,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Choisir/basculer le type de stockage (azure_blob / s3 / internal)."""
    cfg = _upsert(
        db, kind="storage", provider=payload.provider, settings=payload.settings,
        secret_ref=payload.secret_ref, activate=payload.activate, admin=admin,
    )
    from app.services import audit
    audit.record(db, action="storage.configure", entity="integration_config",
                 entity_id=cfg.id, user_id=admin.id,
                 metadata={"provider": payload.provider, "active": payload.activate})
    db.commit()
    db.refresh(cfg)
    return cfg


@router.post("/storage/test", response_model=ConnectionTestResult)
def test_storage(
    payload: StorageConfigIn,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Teste un backend de stockage en écrivant puis relisant un objet témoin,
    AVANT activation (§7bis.3).
    """
    from app.services.storage.providers import make_object_key

    secret = integ._resolve_secret(payload.secret_ref)
    try:
        provider = integ.storage_provider_by_name(payload.provider, payload.settings, secret)
        key = make_object_key(prefix="_healthcheck", filename="probe.txt")
        witness = b"pr-review-storage-probe"
        ref = provider.put(key, witness, "text/plain")
        read_back = provider.get(ref)
        provider.delete(ref)
        if read_back == witness:
            return ConnectionTestResult(ok=True, provider=payload.provider,
                                        detail="Écriture/lecture/suppression OK.")
        return ConnectionTestResult(ok=False, provider=payload.provider,
                                    detail="Objet témoin relu incohérent.")
    except Exception as exc:  # noqa: BLE001
        return ConnectionTestResult(ok=False, provider=payload.provider, detail=str(exc)[:300])


# --------------------------------------------------------------------------
# SharePoint (Lot 6)
# --------------------------------------------------------------------------
@router.get("/sharepoint", response_model=SharePointConfigOut)
def get_sharepoint_config(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Configuration SharePoint active (sans jamais exposer le secret)."""
    from app.services.sharepoint.sync import _get_graph_client

    cfg = db.scalar(
        select(IntegrationConfig).where(
            IntegrationConfig.kind == "sharepoint",
            IntegrationConfig.is_active.is_(True),
        )
    )
    client, settings = _get_graph_client(db)
    return SharePointConfigOut(
        tenant_id=settings.get("tenant_id"),
        client_id=settings.get("client_id"),
        sources=[SharePointSource(**s) for s in settings.get("sources", [])],
        is_active=cfg.is_active if cfg else False,
        operational=client.is_operational(),
    )


@router.put("/sharepoint", response_model=SharePointConfigOut)
def configure_sharepoint(
    payload: SharePointConfigIn,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Définir les sources et motifs de fichiers SharePoint (config admin)."""
    settings = {
        "tenant_id": payload.tenant_id,
        "client_id": payload.client_id,
        "sources": [s.model_dump(mode="json") for s in payload.sources],
    }
    cfg = _upsert(
        db, kind="sharepoint", provider="graph", settings=settings,
        secret_ref=payload.secret_ref, activate=payload.activate, admin=admin,
    )
    db.commit()
    db.refresh(cfg)

    from app.services.sharepoint.sync import _get_graph_client
    client, _ = _get_graph_client(db)
    return SharePointConfigOut(
        tenant_id=payload.tenant_id,
        client_id=payload.client_id,
        sources=payload.sources,
        is_active=cfg.is_active,
        operational=client.is_operational(),
    )


@router.post("/sharepoint/sync", response_model=SyncResult)
def trigger_sharepoint_sync(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Déclencher une synchro manuelle.

    Liste les fichiers correspondant aux motifs, télécharge les nouveaux/modifiés,
    crée ou met à jour la revue cible et pré-remplit via le moteur partagé (§6).
    En production, ce déclencheur peut aussi être planifié (Celery beat).
    """
    from app.services.sharepoint.sync import sync_sources

    summary = sync_sources(db, actor=admin)
    db.commit()
    return SyncResult(**summary)
