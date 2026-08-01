"""
Configuration centralisée de l'application.
Toutes les valeurs sensibles proviennent de variables d'environnement — jamais
codées en dur. En production sur Azure, elles sont injectées depuis Key Vault.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Application ---
    APP_NAME: str = "PR Review Backend"
    ENVIRONMENT: str = "development"          # development | staging | production
    API_V1_PREFIX: str = "/api/v1"
    FRONTEND_ORIGIN: str = "http://localhost:5173"   # pour CORS

    # --- Base de données ---
    DATABASE_URL: str = "postgresql+psycopg://prreview:prreview@localhost:5432/prreview"

    # --- JWT applicatifs ---
    JWT_SECRET: str = "change-me-in-production"       # via Key Vault en prod
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14

    # --- Microsoft Entra ID (OIDC) ---
    ENTRA_TENANT_ID: str = ""
    ENTRA_CLIENT_ID: str = ""
    ENTRA_CLIENT_SECRET: str = ""                     # via Key Vault en prod
    ENTRA_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/callback"
    # Le mapping "groupe Entra -> rôle applicatif" est configurable par l'admin.
    # Valeur de démarrage (peut être surchargée en base via app_settings) :
    ENTRA_GROUP_ROLE_MAP: dict[str, str] = {}

    # --- Repli auth locale (comptes de service / tests) ---
    ENABLE_LOCAL_AUTH: bool = True

    @property
    def entra_configured(self) -> bool:
        return bool(self.ENTRA_TENANT_ID and self.ENTRA_CLIENT_ID)

    @property
    def entra_discovery_url(self) -> str:
        return (
            f"https://login.microsoftonline.com/{self.ENTRA_TENANT_ID}"
            "/v2.0/.well-known/openid-configuration"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
