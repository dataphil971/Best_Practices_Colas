"""
Service d'audit (Lot 7).

Point d'entrée unique pour tracer une action sensible dans `audit_log` : approbation
de règle, validation de revue, changement de rôle, configuration de connecteur,
purge de rétention, etc. On ne journalise jamais de contenu sensible (ex. libellés
d'entreprise envoyés à l'IA) — seulement le fait, l'acteur, l'entité et l'IP.

L'écriture ne lève jamais d'exception vers l'appelant : une panne d'audit ne doit
pas casser l'action métier, mais elle est rare et loggée applicativement.
"""
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit import AuditLog


def record(
    db: Session,
    *,
    action: str,
    entity: str,
    entity_id: uuid.UUID | str | None = None,
    user_id: uuid.UUID | None = None,
    metadata: dict[str, Any] | None = None,
    ip: str | None = None,
) -> AuditLog | None:
    """
    Écrit une entrée d'audit. `action` suit la convention `entité.verbe`
    (ex. 'rule.approve', 'review.validate', 'user.role_change', 'storage.configure').
    """
    try:
        eid = None
        if entity_id is not None:
            eid = entity_id if isinstance(entity_id, uuid.UUID) else uuid.UUID(str(entity_id))
        entry = AuditLog(
            action=action,
            entity=entity,
            entity_id=eid,
            user_id=user_id,
            audit_metadata=metadata,
            ip=ip,
        )
        db.add(entry)
        db.flush()
        return entry
    except Exception:  # noqa: BLE001
        # L'audit ne doit jamais casser l'action métier.
        return None
