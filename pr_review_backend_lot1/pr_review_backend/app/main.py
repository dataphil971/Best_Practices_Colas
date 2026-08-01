"""
Point d'entrée de l'API FastAPI (Lot 1 — Fondations).

Assemble : santé, authentification (Entra ID + repli local), profil, gestion
des utilisateurs. Les lots suivants brancheront référentiel, revues, etc.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.routes import auth, profile, users

app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0 (Lot 1)",
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
    return {"status": "ok", "environment": settings.ENVIRONMENT}


# Montage des routeurs sous le préfixe /api/v1
app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(profile.router, prefix=settings.API_V1_PREFIX)
app.include_router(users.router, prefix=settings.API_V1_PREFIX)
