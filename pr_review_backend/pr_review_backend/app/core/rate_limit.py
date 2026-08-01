"""
Rate limiting (Lot 7, §durcissement).

Limiteur à fenêtre glissante, en mémoire par processus. Suffisant pour un
déploiement mono-processus ou en complément d'un WAF/reverse-proxy ; en production
multi-instances, on branche le même contrat sur Redis (INCR + EXPIRE).

Appliqué aux points sensibles : `/auth/login`, `/auth/register`, imports et appels
IA. Identité de limite = IP client (ou utilisateur si authentifié).
"""
import time
from collections import defaultdict, deque

from fastapi import Request, HTTPException, status


class SlidingWindowLimiter:
    def __init__(self, max_requests: int, window_seconds: float) -> None:
        self.max = max_requests
        self.window = window_seconds
        self._hits: dict[str, deque] = defaultdict(deque)

    def check(self, key: str) -> bool:
        """Vrai si la requête est autorisée ; enregistre le hit."""
        now = time.monotonic()
        q = self._hits[key]
        # Purge les hits hors fenêtre.
        while q and now - q[0] > self.window:
            q.popleft()
        if len(q) >= self.max:
            return False
        q.append(now)
        return True

    def retry_after(self, key: str) -> int:
        q = self._hits.get(key)
        if not q:
            return 0
        return max(1, int(self.window - (time.monotonic() - q[0])))


def _client_key(request: Request) -> str:
    # Priorité à l'utilisateur authentifié si présent, sinon IP.
    user = getattr(request.state, "user_id", None)
    if user:
        return f"user:{user}"
    client = request.client.host if request.client else "unknown"
    return f"ip:{client}"


def rate_limit(max_requests: int, window_seconds: float):
    """
    Fabrique une dépendance FastAPI de limitation.

    Usage : `dependencies=[Depends(rate_limit(5, 60))]` sur une route.
    """
    limiter = SlidingWindowLimiter(max_requests, window_seconds)

    def _dependency(request: Request) -> None:
        key = _client_key(request)
        if not limiter.check(key):
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Trop de requêtes, veuillez réessayer plus tard.",
                headers={"Retry-After": str(limiter.retry_after(key))},
            )

    return _dependency
