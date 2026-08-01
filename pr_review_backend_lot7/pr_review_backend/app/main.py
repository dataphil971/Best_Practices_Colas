"""
Point d'entrée de l'API FastAPI (Lot 1 — Fondations).

Assemble : santé, authentification (Entra ID + repli local), profil, gestion
des utilisateurs. Les lots suivants brancheront référentiel, revues, etc.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.routes import auth, profile, users, referentials, rules, reviews, share
from app.api.routes import imports, integrations  # Lot 5
from app.api.routes import monitoring, admin_settings  # Lot 7

app = FastAPI(
    title=settings.APP_NAME,
    version="0.7.0 (Lot 7)",
    docs_url="/docs",
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
)

# CORS restreint à l'origine du front.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["santé"])
def health():
    """Liveness simple (l'app répond)."""
    return {"status": "ok", "environment": settings.ENVIRONMENT, "version": app.version}


@app.get("/health/ready", tags=["santé"])
def readiness():
    """Readiness : vérifie la connexion à la base de données."""
    from sqlalchemy import text
    from app.core.database import engine

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ready", "database": "ok"}
    except Exception as exc:  # noqa: BLE001
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "database": "error", "detail": str(exc)[:200]},
        )


# Montage des routeurs sous le préfixe /api/v1
app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(profile.router, prefix=settings.API_V1_PREFIX)
app.include_router(users.router, prefix=settings.API_V1_PREFIX)
# Lot 2 — référentiel versionné
app.include_router(referentials.router, prefix=settings.API_V1_PREFIX)
app.include_router(rules.router, prefix=settings.API_V1_PREFIX)
# Lot 3 — gestion des revues
app.include_router(reviews.router, prefix=settings.API_V1_PREFIX)
# Lot 4 — validation tierce (partage ciblé + validation)
app.include_router(share.review_share_router, prefix=settings.API_V1_PREFIX)
app.include_router(share.share_router, prefix=settings.API_V1_PREFIX)
# Lot 5 — import intelligent + stockage pluggable
app.include_router(imports.review_import_router, prefix=settings.API_V1_PREFIX)
app.include_router(imports.import_jobs_router, prefix=settings.API_V1_PREFIX)
app.include_router(integrations.router, prefix=settings.API_V1_PREFIX)
# Lot 7 — monitoring, paramètres admin & audit
app.include_router(monitoring.router, prefix=settings.API_V1_PREFIX)
app.include_router(admin_settings.router, prefix=settings.API_V1_PREFIX)
