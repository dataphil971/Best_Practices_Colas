"""
Tests du connecteur SharePoint (Lot 6).

Sans tenant réel, on valide :
  - la porte `is_operational()` (config incomplète → inopérant, aucun plantage) ;
  - le filtrage par motif de fichier (fnmatch) ;
  - une synchronisation COMPLÈTE avec un client Graph simulé, qui réutilise le
    vrai moteur de parsing + matching (§6) : la revue cible est créée et
    pré-remplie ;
  - la déduplication : un même fichier (même date de modif) n'est pas réimporté.
"""
import io

import pytest
from sqlalchemy import select

from app.models.category import Category
from app.models.review import Review, ReviewItem
from app.models.integration import IntegrationConfig, ImportJob
from app.models.enums import ChecklistType, Criticality, ItemStatus
from app.services import referential as ref_svc
from app.services.sharepoint.graph_client import GraphClient, RemoteFile
from app.services.sharepoint import sync as sync_mod


def _make_xlsx(rows):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# --- Porte opérationnelle ---------------------------------------------------
def test_graph_client_not_operational_without_config():
    client = GraphClient(tenant_id=None, client_id=None, client_secret=None)
    assert client.is_operational() is False
    # list_files renvoie une liste vide plutôt que de planter.
    assert client.list_files(site_url="x", drive="d", folder="/", pattern="*.xlsx") == []


def test_graph_client_operational_with_full_config():
    client = GraphClient(tenant_id="t", client_id="c", client_secret="s")
    assert client.is_operational() is True


# --- Synchro complète avec Graph simulé ------------------------------------
class _FakeGraph:
    """Client Graph simulé : sert un fichier Excel en mémoire."""

    def __init__(self, files: dict[str, bytes]):
        self._files = files  # name -> xlsx bytes
        self.name_to_id = {n: f"id-{i}" for i, n in enumerate(files)}

    def is_operational(self) -> bool:
        return True

    def list_files(self, *, site_url, drive, folder, pattern):
        import fnmatch
        out = []
        for name in self._files:
            if fnmatch.fnmatch(name, pattern):
                out.append(RemoteFile(
                    id=self.name_to_id[name], name=name,
                    path=f"{folder}/{name}", last_modified="2026-03-01T10:00:00Z",
                    size=len(self._files[name]), download_url=None,
                ))
        return out

    def download(self, remote: RemoteFile) -> bytes:
        return self._files[remote.name]


def _seed_referential(db, admin):
    cat = Category(checklist_type=ChecklistType.powerbi, name="Modèle", order_index=0)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    for t in [
        "Vérifiez les types de données et la précision des décimales",
        "Masquer les colonnes techniques inutiles du modèle",
    ]:
        ref_svc.create_rule(
            db, actor=admin, checklist_type=ChecklistType.powerbi, category=cat,
            text=t, subs=[], criticality=Criticality.recommended,
        )
    db.commit()


@pytest.fixture()
def _configured(db, admin, tmp_path, monkeypatch):
    _seed_referential(db, admin)
    # Stockage interne pointé sur tmp.
    db.add(IntegrationConfig(kind="storage", provider="internal",
                             settings={"base_path": str(tmp_path)}, is_active=True))
    # Config SharePoint active (les valeurs réelles importent peu : Graph est simulé).
    db.add(IntegrationConfig(
        kind="sharepoint", provider="graph", is_active=True,
        settings={
            "tenant_id": "t", "client_id": "c",
            "sources": [{
                "name": "Revues Power BI",
                "site": "https://contoso.sharepoint.com/sites/BI",
                "drive": "Documents", "folder": "/Revues",
                "pattern": "PR_*.xlsx", "target_checklist": "powerbi",
            }],
        },
    ))
    db.commit()

    xlsx = _make_xlsx([
        ["Règle", "Statut"],
        ["verifier les types de donnees et la precision decimale", "OK"],
        ["cacher les colonnes techniques inutiles", "KO"],
    ])
    fake = _FakeGraph({"PR_Rapport1.xlsx": xlsx, "autre.txt": b"ignore"})
    monkeypatch.setattr(sync_mod, "_get_graph_client", lambda _db: (fake, {
        "tenant_id": "t", "client_id": "c",
        "sources": [{
            "name": "Revues Power BI",
            "site": "https://contoso.sharepoint.com/sites/BI",
            "drive": "Documents", "folder": "/Revues",
            "pattern": "PR_*.xlsx", "target_checklist": "powerbi",
        }],
    }))
    return admin


def test_sync_creates_and_prefills_review(db, _configured):
    admin = _configured
    summary = sync_mod.sync_sources(db, actor=admin)
    db.commit()

    assert summary["operational"] is True
    assert summary["listed"] == 1          # seul PR_*.xlsx retenu, pas autre.txt
    assert summary["imported"] == 1

    # La revue cible a été créée (nom dérivé du fichier) et pré-remplie.
    review = db.scalar(select(Review).where(Review.report_name == "PR_Rapport1"))
    assert review is not None
    items = db.scalars(select(ReviewItem).where(ReviewItem.review_id == review.id)).all()
    assert any(it.status != ItemStatus.unset for it in items)

    # Un import_job source='sharepoint' a été tracé et terminé.
    job = db.scalar(select(ImportJob).where(ImportJob.source == "sharepoint"))
    assert job is not None and job.status == "done"


def test_sync_dedup_skips_unchanged_file(db, _configured):
    admin = _configured
    first = sync_mod.sync_sources(db, actor=admin)
    db.commit()
    assert first["imported"] == 1

    # Deuxième passe : même fichier, même date → ignoré (dédup).
    second = sync_mod.sync_sources(db, actor=admin)
    db.commit()
    assert second["imported"] == 0
    assert second["skipped"] == 1
