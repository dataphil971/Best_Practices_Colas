"""Énumérations métier, alignées sur le schéma SQL de la spécification."""
import enum


class UserRole(str, enum.Enum):
    user = "user"
    reviewer = "reviewer"
    admin = "admin"


class ChecklistType(str, enum.Enum):
    powerbi = "powerbi"
    appbi = "appbi"
    build = "build"


class Criticality(str, enum.Enum):
    blocking = "blocking"
    recommended = "recommended"
    optional = "optional"


class LifecycleState(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class ItemStatus(str, enum.Enum):
    ok = "ok"
    ko = "ko"
    partial = "partial"
    na = "na"
    unset = "unset"


class ProgressState(str, enum.Enum):
    todo = "todo"
    in_progress = "in_progress"
    done = "done"


class ReviewStatus(str, enum.Enum):
    draft = "draft"
    in_progress = "in_progress"
    submitted = "submitted"
    validated = "validated"
    changes_requested = "changes_requested"
