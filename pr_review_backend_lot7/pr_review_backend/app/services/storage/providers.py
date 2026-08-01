"""
Connecteur de stockage pluggable (Lot 5, §7bis).

Tout le code applicatif manipule des RÉFÉRENCES OPAQUES (`ref`) et ne connaît
jamais le backend concret. Changer de fournisseur ne change pas le reste du code.

Backends :
  - 'internal'   : stockage local on-prem / volume monté (défaut hors Azure) ;
  - 'azure_blob' : Azure Blob Storage (défaut cohérent avec l'hébergement Azure) ;
  - 's3'         : AWS S3 ou compatible (MinIO…).

Les secrets (chaînes de connexion / clés) vivent dans le coffre (Key Vault),
jamais en base ni renvoyés au front. Ici, les adaptateurs cloud reçoivent leurs
identifiants résolus au moment de la construction.
"""
from __future__ import annotations

import base64
import hashlib
import uuid
from pathlib import Path
from typing import Protocol


class StorageProvider(Protocol):
    name: str

    def put(self, key: str, data: bytes, content_type: str) -> str:
        """Écrit l'objet et retourne une référence opaque."""
        ...

    def get(self, ref: str) -> bytes:
        ...

    def delete(self, ref: str) -> None:
        ...

    def presigned_url(self, ref: str, ttl_seconds: int) -> str | None:
        """URL temporaire de téléchargement direct, si le backend le permet."""
        ...


def make_object_key(prefix: str, filename: str) -> str:
    """Clé d'objet unique et non devinable (évite les collisions et l'énumération)."""
    token = base64.urlsafe_b64encode(uuid.uuid4().bytes).rstrip(b"=").decode()
    safe = "".join(c for c in filename if c.isalnum() or c in "._-")[:80] or "file"
    return f"{prefix}/{token}_{safe}"


# --------------------------------------------------------------------------
# Backend interne (défaut hors Azure) : volume monté / dossier local
# --------------------------------------------------------------------------
class InternalStorageProvider:
    """
    Stockage sur système de fichiers. La `ref` est de la forme
    `internal://<chemin-relatif>`. Aucune dépendance externe.
    """

    name = "internal"

    def __init__(self, base_path: str = "/var/lib/pr-review/storage") -> None:
        self.base = Path(base_path)
        self.base.mkdir(parents=True, exist_ok=True)

    def _abs(self, key: str) -> Path:
        # Empêche toute évasion hors du répertoire de base.
        target = (self.base / key).resolve()
        if not str(target).startswith(str(self.base.resolve())):
            raise ValueError("Chemin de stockage invalide.")
        return target

    def put(self, key: str, data: bytes, content_type: str) -> str:
        path = self._abs(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return f"internal://{key}"

    def get(self, ref: str) -> bytes:
        key = ref.removeprefix("internal://")
        return self._abs(key).read_bytes()

    def delete(self, ref: str) -> None:
        key = ref.removeprefix("internal://")
        p = self._abs(key)
        if p.exists():
            p.unlink()

    def presigned_url(self, ref: str, ttl_seconds: int) -> str | None:
        # Pas d'URL directe pour le stockage interne ; téléchargement via l'API.
        return None


# --------------------------------------------------------------------------
# Backend Azure Blob (adaptateur ; dépendances chargées à la demande)
# --------------------------------------------------------------------------
class AzureBlobStorageProvider:
    """Adaptateur Azure Blob. `ref` de la forme `azure://<container>/<key>`."""

    name = "azure_blob"

    def __init__(self, *, account: str, container: str, connection_string: str) -> None:
        self.account = account
        self.container = container
        self._conn = connection_string  # résolu depuis le coffre, jamais en base

    def _client(self):
        from azure.storage.blob import BlobServiceClient  # import tardif

        return BlobServiceClient.from_connection_string(self._conn)

    def put(self, key: str, data: bytes, content_type: str) -> str:
        from azure.storage.blob import ContentSettings

        client = self._client().get_blob_client(self.container, key)
        client.upload_blob(
            data, overwrite=True,
            content_settings=ContentSettings(content_type=content_type),
        )
        return f"azure://{self.container}/{key}"

    def get(self, ref: str) -> bytes:
        _, _, path = ref.partition("azure://")
        container, _, key = path.partition("/")
        client = self._client().get_blob_client(container, key)
        return client.download_blob().readall()

    def delete(self, ref: str) -> None:
        _, _, path = ref.partition("azure://")
        container, _, key = path.partition("/")
        client = self._client().get_blob_client(container, key)
        try:
            client.delete_blob()
        except Exception:
            pass

    def presigned_url(self, ref: str, ttl_seconds: int) -> str | None:
        # Génération de SAS possible ici ; laissée à la configuration de prod.
        return None


# --------------------------------------------------------------------------
# Backend S3 / compatible (adaptateur ; dépendances chargées à la demande)
# --------------------------------------------------------------------------
class S3StorageProvider:
    """Adaptateur S3/MinIO. `ref` de la forme `s3://<bucket>/<key>`."""

    name = "s3"

    def __init__(
        self,
        *,
        bucket: str,
        region: str | None = None,
        endpoint_url: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
    ) -> None:
        self.bucket = bucket
        self.region = region
        self.endpoint_url = endpoint_url
        self._access_key = access_key
        self._secret_key = secret_key

    def _client(self):
        import boto3  # import tardif

        return boto3.client(
            "s3",
            region_name=self.region,
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self._access_key,
            aws_secret_access_key=self._secret_key,
        )

    def put(self, key: str, data: bytes, content_type: str) -> str:
        self._client().put_object(
            Bucket=self.bucket, Key=key, Body=data, ContentType=content_type
        )
        return f"s3://{self.bucket}/{key}"

    def get(self, ref: str) -> bytes:
        _, _, path = ref.partition("s3://")
        bucket, _, key = path.partition("/")
        obj = self._client().get_object(Bucket=bucket, Key=key)
        return obj["Body"].read()

    def delete(self, ref: str) -> None:
        _, _, path = ref.partition("s3://")
        bucket, _, key = path.partition("/")
        try:
            self._client().delete_object(Bucket=bucket, Key=key)
        except Exception:
            pass

    def presigned_url(self, ref: str, ttl_seconds: int) -> str | None:
        _, _, path = ref.partition("s3://")
        bucket, _, key = path.partition("/")
        try:
            return self._client().generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": key},
                ExpiresIn=ttl_seconds,
            )
        except Exception:
            return None
