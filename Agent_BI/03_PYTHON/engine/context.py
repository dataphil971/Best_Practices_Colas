"""Contexte d'analyse partagé.

Cf. section « Principe important » de Agent_BI/README_Agent_BI.md (03_PYTHON) :
le projet PBIP est lu une seule fois, puis toutes les règles réutilisent le
même contexte au lieu de reparcourir le projet chacune de leur côté.
"""

import hashlib
from pathlib import Path
from typing import List, Optional, Union

from engine.models import TableDef
from powerbi.tmdl_parser import parse_tables_directory


def _compute_fingerprint(tables: List[TableDef]) -> Optional[str]:
    """Empreinte légère du projet lu, basée sur (chemin, taille, date de
    modification) de chaque fichier de table effectivement parsé.

    Volontairement pas une empreinte de contenu (pas de nouvelle lecture des
    fichiers ici, un `stat()` suffit) : cela reste assez fiable pour détecter
    "le projet a changé depuis la dernière analyse" côté appelant (cache,
    ré-analyse incrémentale), sans violer le principe de lecture unique.
    Une empreinte de contenu (type Merkle) reste un raffinement possible plus
    tard si le besoin de fiabilité l'exige.
    """
    if not tables:
        return None

    hasher = hashlib.sha256()
    for table in sorted(tables, key=lambda t: t.source_file):
        stat = Path(table.source_file).stat()
        hasher.update(f"{table.source_file}:{stat.st_size}:{stat.st_mtime_ns}".encode("utf-8"))
    return f"sha256:{hasher.hexdigest()}"


class AnalysisContext:
    def __init__(self, project_path: Optional[Path] = None):
        self.project_path: Optional[Path] = project_path
        self.semantic_model_path: Optional[Path] = None
        self.tables: List[TableDef] = []
        self.fingerprint: Optional[str] = None

    @classmethod
    def from_semantic_model_path(cls, semantic_model_path: Union[str, Path]) -> "AnalysisContext":
        """Construit un contexte à partir du dossier `<Nom>.SemanticModel`
        directement (utile pour les tests, sans avoir à recréer une racine
        de projet PBIP complète)."""
        context = cls()
        context.semantic_model_path = Path(semantic_model_path)
        tables_dir = context.semantic_model_path / "definition" / "tables"
        context.tables = parse_tables_directory(tables_dir)
        context.fingerprint = _compute_fingerprint(context.tables)
        return context

    @classmethod
    def load(cls, project_path: Union[str, Path]) -> "AnalysisContext":
        """Construit un contexte à partir de la racine d'un projet PBIP
        (dossier contenant `<Nom>.SemanticModel/` et, le cas échéant,
        `<Nom>.Report/`)."""
        project_path = Path(project_path)
        semantic_model_dirs = sorted(project_path.glob("*.SemanticModel"))

        if not semantic_model_dirs:
            return cls(project_path)

        context = cls.from_semantic_model_path(semantic_model_dirs[0])
        context.project_path = project_path
        return context
