"""
Mapping "groupe Entra ID -> rôle applicatif", configurable par l'admin.

Au Lot 1, la valeur de démarrage vient de la configuration (ENTRA_GROUP_ROLE_MAP).
Aux lots suivants, elle sera surchargeable en base (table app_settings) via
l'endpoint PUT /admin/settings/role-mapping.
"""
from app.core.config import settings
from app.models.enums import UserRole

# Ordre de priorité : admin > reviewer > user. Si un utilisateur appartient à
# plusieurs groupes mappés, on retient le rôle le plus élevé.
_PRIORITY = {UserRole.admin: 2, UserRole.reviewer: 1, UserRole.user: 0}


def resolve_role_from_groups(groups: list[str]) -> UserRole | None:
    """
    Retourne le rôle le plus élevé correspondant aux groupes de l'utilisateur,
    ou None si aucun groupe n'est mappé (l'appelant retombe alors sur 'user').
    """
    mapping = settings.ENTRA_GROUP_ROLE_MAP or {}
    best: UserRole | None = None
    for group_id in groups:
        role_str = mapping.get(group_id)
        if not role_str:
            continue
        try:
            role = UserRole(role_str)
        except ValueError:
            continue
        if best is None or _PRIORITY[role] > _PRIORITY[best]:
            best = role
    return best
