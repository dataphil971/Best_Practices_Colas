"""Contexte d'analyse partagé.

Cf. section « Principe important » de Agent_BI/README_Agent_BI.md (03_PYTHON) :
le projet PBIP est lu une seule fois, puis toutes les règles réutilisent le
même contexte au lieu de reparcourir le projet chacune de leur côté.
"""

import hashlib
from pathlib import Path
from types import ModuleType

from engine.models import ExpressionDef, RelationshipDef, ReportFilterDef, TableDef
from powerbi import pbir_parser, report_legacy_parser
from powerbi.tmdl_parser import (
    parse_expressions_file,
    parse_model_file,
    parse_relationships_file,
    parse_tables_directory,
)


def _compute_fingerprint(tables: list[TableDef], extra_files: list[Path]) -> str | None:
    """Empreinte légère du projet lu, basée sur (chemin, taille, date de
    modification) de chaque fichier de table effectivement parsé, plus les
    fichiers hors `tables/` que le contexte a lus (`relationships.tmdl`,
    `model.tmdl`) : une empreinte qui ne bougerait pas quand seul l'un de ces
    fichiers change casserait l'idempotence de l'import Agent BI (une
    ré-analyse après correction d'une relation serait prise pour un no-op).

    Volontairement pas une empreinte de contenu (pas de nouvelle lecture des
    fichiers ici, un `stat()` suffit) : cela reste assez fiable pour détecter
    "le projet a changé depuis la dernière analyse" côté appelant (cache,
    ré-analyse incrémentale), sans violer le principe de lecture unique.
    Une empreinte de contenu (type Merkle) reste un raffinement possible plus
    tard si le besoin de fiabilité l'exige.
    """
    paths = sorted({Path(table.source_file) for table in tables} | {p for p in extra_files if p.exists()})
    if not paths:
        return None

    hasher = hashlib.sha256()
    for path in paths:
        stat = path.stat()
        hasher.update(f"{path}:{stat.st_size}:{stat.st_mtime_ns}".encode())
    return f"sha256:{hasher.hexdigest()}"


class AnalysisContext:
    def __init__(self, project_path: Path | None = None):
        self.project_path: Path | None = project_path
        self.semantic_model_path: Path | None = None
        self.tables: list[TableDef] = []
        self.relationships: list[RelationshipDef] = []
        self.model_annotations: dict[str, str] = {}
        self.expressions: list[ExpressionDef] = []
        self.relationships_tmdl_path: Path | None = None
        self.model_tmdl_path: Path | None = None
        self.expressions_tmdl_path: Path | None = None
        # Rapport PBIR (`<Nom>.Report/`) : présent seulement quand le contexte
        # est construit depuis la RACINE du projet, pas depuis le seul dossier
        # `.SemanticModel` — d'où `report_path` à None dans ce dernier cas.
        self.report_path: Path | None = None
        # Sérialisation du rapport effectivement lue : "PBIR" (arborescence
        # definition/), "LEGACY" (report.json unique) ou None si aucun dossier
        # `.Report/` n'a été trouvé. Exposé aux règles pour qu'elles puissent
        # distinguer « rapport absent » de « rapport présent mais illisible ».
        self.report_format: str | None = None
        self.report_filters: list[ReportFilterDef] = []
        # (kind, entity, property) de tout champ référencé quelque part dans
        # le rapport — surface d'usage consommée par BP-07.
        self.report_field_references: set[tuple[str, str, str]] = set()
        # Agrégations implicites sérialisées dans les visuels (BP-32).
        self.report_implicit_aggregations: list[dict] = []
        # Structure du rapport : groupes, liens parents, interactions, signets
        # (BP-37 / BP-38).
        self.report_structure: dict = {}
        # Inventaire des visuels + signature analytique canonique (BP-41).
        self.report_visuals: list[dict] = []
        self.fingerprint: str | None = None

    @classmethod
    def from_semantic_model_path(cls, semantic_model_path: str | Path) -> "AnalysisContext":
        """Construit un contexte à partir du dossier `<Nom>.SemanticModel`
        directement (utile pour les tests, sans avoir à recréer une racine
        de projet PBIP complète)."""
        context = cls()
        context.semantic_model_path = Path(semantic_model_path)
        tables_dir = context.semantic_model_path / "definition" / "tables"
        context.tables = parse_tables_directory(tables_dir)

        context.relationships_tmdl_path = context.semantic_model_path / "definition" / "relationships.tmdl"
        context.relationships = parse_relationships_file(context.relationships_tmdl_path)

        context.model_tmdl_path = context.semantic_model_path / "definition" / "model.tmdl"
        context.model_annotations = parse_model_file(context.model_tmdl_path)

        context.expressions_tmdl_path = context.semantic_model_path / "definition" / "expressions.tmdl"
        context.expressions = parse_expressions_file(context.expressions_tmdl_path)

        context.fingerprint = _compute_fingerprint(
            context.tables,
            [context.relationships_tmdl_path, context.model_tmdl_path, context.expressions_tmdl_path],
        )
        return context

    def _attach_report(self, project_path: Path) -> None:
        """Rattache le dossier `<Nom>.Report/` du projet, s'il existe.

        Séparé de `from_semantic_model_path` : le rapport vit à côté du
        modèle, pas dedans — il n'est donc atteignable que depuis la racine
        du projet. Un contexte construit depuis le seul `.SemanticModel`
        garde `report_filters` vide, ce que les règles rapport doivent
        traiter en NA (« pas de rapport à analyser »), jamais en OK.
        """
        report_dirs = sorted(project_path.glob("*.Report"))
        if not report_dirs:
            return
        self.report_path = report_dirs[0]

        # Deux sérialisations de rapport coexistent dans PBIP. Le choix du
        # parseur est fait ICI, une seule fois : les règles rapport ignorent
        # le format qu'elles analysent et n'ont pas à le tester.
        parser: ModuleType
        if report_legacy_parser.is_legacy_report(self.report_path):
            parser = report_legacy_parser
            self.report_format = "LEGACY"
        else:
            parser = pbir_parser
            self.report_format = "PBIR"

        self.report_filters = parser.parse_report_filters(self.report_path)
        self.report_field_references = parser.parse_report_field_references(self.report_path)
        self.report_implicit_aggregations = parser.parse_report_implicit_aggregations(self.report_path)
        self.report_structure = parser.parse_report_structure(self.report_path)
        self.report_visuals = parser.parse_report_visuals(self.report_path)

    @classmethod
    def load(cls, project_path: str | Path) -> "AnalysisContext":
        """Construit un contexte à partir de la racine d'un projet PBIP
        (dossier contenant `<Nom>.SemanticModel/` et, le cas échéant,
        `<Nom>.Report/`)."""
        project_path = Path(project_path)
        semantic_model_dirs = sorted(project_path.glob("*.SemanticModel"))

        if semantic_model_dirs:
            context = cls.from_semantic_model_path(semantic_model_dirs[0])
            context.project_path = project_path
            context._attach_report(project_path)
            return context

        # Tolérance : l'appelant a pointé directement sur le dossier
        # `<Nom>.SemanticModel` plutôt que sur la racine du projet PBIP qui le
        # contient (erreur d'usage courante — rien dans l'UI ne rend la
        # distinction évidente). Sans ce repli, chaque règle renvoie NA
        # « Aucun fichier de table TMDL trouvé » quel que soit le contenu du
        # modèle, ce qui ressemble à un moteur cassé plutôt qu'à un chemin
        # incorrect. On ne se fie pas qu'au nom : la présence de
        # `definition/tables` confirme qu'il s'agit bien d'un modèle
        # sémantique, pas d'un dossier nommé par coïncidence.
        if (
            project_path.name.endswith(".SemanticModel")
            and (project_path / "definition" / "tables").exists()
        ):
            context = cls.from_semantic_model_path(project_path)
            context.project_path = project_path.parent
            context._attach_report(project_path.parent)
            return context

        return cls(project_path)
