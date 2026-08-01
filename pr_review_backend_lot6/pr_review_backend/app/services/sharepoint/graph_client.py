"""
Client Microsoft Graph pour SharePoint / OneDrive (Lot 6, §7.1).

Récupère des fichiers de revue depuis SharePoint selon des règles définies par
l'admin. Authentification par **OAuth 2.0 client credentials** (application
enregistrée dans Entra ID) ; permissions Graph minimales en lecture seule
(`Sites.Read.All` / `Files.Read.All`).

Les secrets (client secret) ne vivent jamais en base : ils sont résolus à
l'exécution depuis le coffre via `secret_ref`. Le client est **tolérant** : sans
configuration réseau exploitable, il expose `is_operational() == False`, ce qui
permet au reste du code de se comporter proprement (aucun plantage), exactement
comme le repli du connecteur de matching.

Le token applicatif est mis en cache le temps de sa validité pour limiter les
appels au point de terminaison OAuth.
"""
from __future__ import annotations

import fnmatch
import time
from dataclasses import dataclass

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
LOGIN_BASE = "https://login.microsoftonline.com"


@dataclass
class RemoteFile:
    """Métadonnées minimales d'un fichier distant SharePoint."""
    id: str
    name: str
    path: str
    last_modified: str
    size: int
    download_url: str | None = None


class GraphClient:
    def __init__(
        self,
        *,
        tenant_id: str | None,
        client_id: str | None,
        client_secret: str | None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.tenant_id = tenant_id
        self.client_id = client_id
        self._client_secret = client_secret
        self.timeout = timeout_seconds
        self._token: str | None = None
        self._token_exp: float = 0.0

    def is_operational(self) -> bool:
        """Vrai si l'on dispose du minimum pour appeler Graph."""
        return bool(self.tenant_id and self.client_id and self._client_secret)

    # ------------------------------------------------------------------ auth
    def _get_token(self) -> str:
        now = time.time()
        if self._token and now < self._token_exp - 60:
            return self._token
        import httpx

        url = f"{LOGIN_BASE}/{self.tenant_id}/oauth2/v2.0/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self._client_secret,
            "scope": "https://graph.microsoft.com/.default",
        }
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, data=data)
            resp.raise_for_status()
            payload = resp.json()
        self._token = payload["access_token"]
        self._token_exp = now + float(payload.get("expires_in", 3600))
        return self._token

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._get_token()}"}

    # ------------------------------------------------------------- resolution
    def _resolve_site_id(self, site_url: str) -> str:
        """Résout l'ID de site Graph à partir d'une URL SharePoint."""
        import httpx
        from urllib.parse import urlparse

        parsed = urlparse(site_url)
        host = parsed.netloc
        site_path = parsed.path  # ex. /sites/BI
        url = f"{GRAPH_BASE}/sites/{host}:{site_path}"
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(url, headers=self._headers())
            resp.raise_for_status()
            return resp.json()["id"]

    def _resolve_drive_id(self, site_id: str, drive_name: str) -> str:
        import httpx

        url = f"{GRAPH_BASE}/sites/{site_id}/drives"
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(url, headers=self._headers())
            resp.raise_for_status()
            drives = resp.json().get("value", [])
        for d in drives:
            if d.get("name") == drive_name:
                return d["id"]
        if drives:
            return drives[0]["id"]  # repli sur la bibliothèque par défaut
        raise ValueError(f"Aucune bibliothèque de documents trouvée ({drive_name!r}).")

    # -------------------------------------------------------------- listing
    def list_files(
        self, *, site_url: str, drive: str, folder: str, pattern: str
    ) -> list[RemoteFile]:
        """
        Liste les fichiers d'un dossier correspondant au motif (`PR_*.xlsx`).

        Retourne une liste vide si le connecteur n'est pas opérationnel.
        """
        if not self.is_operational():
            return []
        import httpx

        site_id = self._resolve_site_id(site_url)
        drive_id = self._resolve_drive_id(site_id, drive)
        folder_path = folder.strip("/")
        url = f"{GRAPH_BASE}/drives/{drive_id}/root:/{folder_path}:/children"

        files: list[RemoteFile] = []
        with httpx.Client(timeout=self.timeout) as client:
            while url:
                resp = client.get(url, headers=self._headers())
                resp.raise_for_status()
                body = resp.json()
                for item in body.get("value", []):
                    if "file" not in item:  # ignore les sous-dossiers
                        continue
                    name = item.get("name", "")
                    if not fnmatch.fnmatch(name, pattern):
                        continue
                    files.append(
                        RemoteFile(
                            id=item["id"],
                            name=name,
                            path=f"{folder}/{name}",
                            last_modified=item.get("lastModifiedDateTime", ""),
                            size=int(item.get("size", 0)),
                            download_url=item.get("@microsoft.graph.downloadUrl"),
                        )
                    )
                url = body.get("@odata.nextLink")
        return files

    # ------------------------------------------------------------- download
    def download(self, remote: RemoteFile) -> bytes:
        import httpx

        if remote.download_url:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(remote.download_url)
                resp.raise_for_status()
                return resp.content
        # Repli : endpoint /content par ID.
        url = f"{GRAPH_BASE}/drives/items/{remote.id}/content"
        with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
            resp = client.get(url, headers=self._headers())
            resp.raise_for_status()
            return resp.content
