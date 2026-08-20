"""Structures de données partagées par le moteur Agent BI.

Ces structures reflètent directement les conventions décrites dans
Agent_BI/README_Agent_BI.md (statuts OK/KO/NA, principe de preuve) : toute
évolution de ces conventions doit être répercutée ici.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class SourceLocation:
    """Où se trouve exactement un constat, à la ligne près.

    Sans cette information, un utilisateur qui reçoit « la colonne X est non
    conforme » doit rouvrir le fichier et chercher — ce qui est précisément ce
    que l'agent doit lui éviter. `line` est 1-INDEXÉE (comme un éditeur), pas
    0-indexée.

    `excerpt` est recopié depuis le fichier au moment du constat : un
    consommateur (frontend, LLM d'explication) n'a jamais à relire le projet
    pour afficher le code fautif.
    """

    source_file: str
    line: Optional[int] = None
    end_line: Optional[int] = None
    excerpt: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_file": self.source_file,
            "line": self.line,
            "end_line": self.end_line,
            "excerpt": self.excerpt,
        }

    @classmethod
    def from_file(
        cls, source_file: str, line: Optional[int],
        end_line: Optional[int] = None, context_lines: int = 0,
    ) -> "SourceLocation":
        """Construit une localisation en y recopiant l'extrait réel du fichier.

        `context_lines` ajoute des lignes avant/après pour rendre l'extrait
        lisible hors contexte. Toute erreur de lecture est absorbée : une
        localisation sans extrait reste utile, alors qu'une exception ferait
        échouer une règle pour un simple problème d'affichage.
        """
        location = cls(source_file=source_file, line=line, end_line=end_line or line)
        if line is None:
            return location
        try:
            lines = Path(source_file).read_text(encoding="utf-8-sig").splitlines()
        except OSError:
            return location
        start = max(1, line - context_lines)
        stop = min(len(lines), (end_line or line) + context_lines)
        if start > len(lines):
            return location
        location.excerpt = "\n".join(lines[start - 1:stop])
        return location


@dataclass
class ColumnDef:
    """Une colonne telle qu'extraite d'un bloc `column` TMDL.

    `name` est la valeur utile (guillemets retirés) ; `raw_name` conserve la
    forme brute telle qu'écrite dans le TMDL (guillemets compris) pour les
    preuves et les messages utilisateur.

    `line` situe la déclaration `column <Nom>` ; `property_lines` situe
    CHAQUE propriété du corps. Une règle qui reproche une propriété précise
    (`summarizeBy`, `dataType`...) doit pointer la ligne de CETTE propriété,
    pas celle de la colonne — c'est la ligne que l'utilisateur doit corriger.
    """

    name: str
    raw_name: str
    properties: Dict[str, Any]
    source_file: str
    line: Optional[int] = None
    end_line: Optional[int] = None
    property_lines: Dict[str, int] = field(default_factory=dict)

    def get_property(self, key: str) -> Optional[Any]:
        return self.properties.get(key)

    def locate(self, property_name: Optional[str] = None, context_lines: int = 0) -> SourceLocation:
        """Localisation de la colonne, ou de l'une de ses propriétés.

        Retombe sur la ligne de la colonne si la propriété n'existe pas —
        c'est le cas d'une règle qui reproche une propriété ABSENTE : il n'y a
        alors aucune ligne fautive, seulement l'endroit où l'ajouter.
        """
        line = self.property_lines.get(property_name) if property_name else None
        return SourceLocation.from_file(
            self.source_file, line or self.line, context_lines=context_lines
        )


@dataclass
class PartitionDef:
    """Une partition telle qu'extraite d'un bloc `partition <Nom> = m` dans le
    TMDL d'une table : le mode de stockage et le code M source (Power Query).

    `m_source` est le texte BRUT de l'expression M (potentiellement
    multi-lignes), jamais reparsé en dur ici — cf. `powerbi/m_lang.py` pour
    les utilitaires d'inspection de ce texte (recherche d'appel de fonction).
    """

    name: str
    mode: Optional[str]  # "import" | "directQuery" | autre, brut (non normalisé)
    m_source: Optional[str]
    source_file: str
    line: Optional[int] = None
    # Ligne du fichier où commence RÉELLEMENT le code M (première ligne après
    # `source =`). Permet de convertir un décalage d'étape M en numéro de
    # ligne absolu dans le TMDL — cf. `powerbi/m_lang.py`, `MStep.line_offset`.
    m_source_line: Optional[int] = None


@dataclass
class ExpressionDef:
    """Une requête partagée ou un paramètre, tel qu'extrait d'un bloc
    `expression <Nom> = ...` de `definition/expressions.tmdl`.

    Contrairement à une `PartitionDef`, une expression n'a pas de `mode`
    (import/directQuery) : ce n'est pas elle qui charge une table, c'est une
    table (ou une autre expression) qui la référence. Une table dont la
    partition référence une expression par son seul nom (`source = D_X`)
    hérite du mode de LA PARTITION, jamais de l'expression elle-même.
    """

    name: str
    m_source: Optional[str]
    source_file: str
    line: Optional[int] = None
    m_source_line: Optional[int] = None


@dataclass
class ReportFilterDef:
    """Un filtre déclaré dans le rapport PBIR (`filterConfig`), à l'un des
    trois niveaux : rapport, page ou visuel.

    `field_references` est la liste des (kind, entity, property) trouvés dans
    le champ filtré — une liste et non un couple unique : un champ peut être
    imbriqué (hiérarchie, agrégation) et porter plusieurs références selon la
    version PBIR. Une liste vide signifie « référence non résolue », jamais
    « filtre sans champ ».
    """

    name: str
    level: str  # "report" | "page" | "visual"
    page_id: Optional[str]
    visual_id: Optional[str]
    filter_type: Optional[str]
    field_references: List[Any]  # list[tuple[str, Optional[str], Optional[str]]]
    source_file: str
    line: Optional[int] = None


@dataclass
class TableDef:
    name: str
    source_file: str
    line: Optional[int] = None
    columns: List[ColumnDef] = field(default_factory=list)
    # Mesures du bloc `measure` (même forme qu'une colonne : nom + propriétés
    # brutes). L'expression DAX elle-même n'est volontairement pas isolée des
    # autres propriétés du corps du bloc : aucune règle actuelle n'en a besoin.
    measures: List[ColumnDef] = field(default_factory=list)
    partitions: List[PartitionDef] = field(default_factory=list)


@dataclass
class RelationshipDef:
    """Une relation telle qu'extraite d'un bloc `relationship` de
    `definition/relationships.tmdl`.

    `from_cardinality`/`to_cardinality`/`cross_filtering_behavior` sont les
    valeurs BRUTES lues (ou `None` si la propriété est absente) : TMDL omet
    une propriété quand elle vaut son défaut Power BI plutôt que de l'écrire
    explicitement, donc l'absence n'est pas une valeur "inconnue" au même
    titre qu'un problème de lecture — c'est aux règles appelantes de résoudre
    le défaut applicable (cf. rules/bp_03.py).
    """

    id: str
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    from_cardinality: Optional[str]
    to_cardinality: Optional[str]
    cross_filtering_behavior: Optional[str]
    is_active: bool
    source_file: str
    line: Optional[int] = None
    property_lines: Dict[str, int] = field(default_factory=dict)

    def locate(self, property_name: Optional[str] = None, context_lines: int = 0) -> SourceLocation:
        line = self.property_lines.get(property_name) if property_name else None
        return SourceLocation.from_file(
            self.source_file, line or self.line, context_lines=context_lines
        )


@dataclass
class Finding:
    """Un constat unitaire, conforme au « Principe de preuve » du README :
    Rule ID / Object / Expected / Actual / Evidence / Status.

    Trois champs servent l'EXPLICABILITÉ, c'est-à-dire ce qu'un humain (ou un
    assistant IA) doit recevoir pour comprendre et corriger sans rouvrir le
    projet :

      * `location`    — fichier + ligne exacte + extrait du code fautif ;
      * `remediation` — l'action concrète à faire, formulée à l'impératif ;
      * `explanation` — pourquoi c'est un problème (la conséquence), pas la
                        répétition de la règle.

    Ces champs sont OPTIONNELS : une règle qui ne peut pas situer son constat
    (agrégation d'un modèle entier, absence d'un fichier) laisse `location` à
    None plutôt que d'inventer une ligne.
    """

    rule_id: str
    object_type: str
    object: str
    expected: str
    actual: Any
    status: str  # OK | KO | NA
    evidence: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    location: Optional[SourceLocation] = None
    remediation: str = ""
    explanation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "object_type": self.object_type,
            "object": self.object,
            "expected": self.expected,
            "actual": self.actual,
            "status": self.status,
            "evidence": self.evidence,
            "reason": self.reason,
            "location": self.location.to_dict() if self.location else None,
            "remediation": self.remediation,
            "explanation": self.explanation,
        }


@dataclass
class Candidate:
    """Un CANDIDAT contextuel : une situation que le checker déterministe a
    détectée sans pouvoir trancher seul, à soumettre au skill
    `agent-bi-context-review`.

    Principe fondamental du skill, repris ici tel quel :

        candidat != violation

    Un candidat ne fait donc JAMAIS basculer `rule_status` en KO. Une règle
    qui n'émet que des candidats reste NA : c'est la revue contextuelle
    (humaine ou assistée) qui qualifiera chacun en JUSTIFIE /
    NON_CONFORME_CONFIRME / NON_RESOLU.

    Les champs reprennent le contrat d'entrée du skill (« Entrées à
    privilégier ») : `candidate_type` = `type_candidat`, `objects` = les
    objets concernés, `technical_evidence` = la preuve déterministe déjà
    établie, que le reviewer doit accepter comme un FAIT.
    """

    rule_id: str
    candidate_id: str
    candidate_type: str
    objects: List[Any] = field(default_factory=list)
    technical_evidence: Dict[str, Any] = field(default_factory=dict)
    review_context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "candidate_id": self.candidate_id,
            "candidate_type": self.candidate_type,
            "objects": self.objects,
            "technical_evidence": self.technical_evidence,
            "review_context": self.review_context,
        }


@dataclass
class RuleResult:
    """Résultat global d'une règle, tel que sérialisé dans le résultat d'audit."""

    rule_id: str
    rule_name: str
    execution_status: str  # SUCCESS | ERROR | PARTIAL
    rule_status: str       # OK | KO | NA — jamais un autre statut
    alias: Optional[str] = None
    findings: List[Finding] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    candidates: List[Candidate] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {"rule_id": self.rule_id}
        if self.alias:
            result["alias"] = self.alias
        result["rule_name"] = self.rule_name
        result["execution_status"] = self.execution_status
        result["rule_status"] = self.rule_status
        result.update(self.summary)
        # `summary` ne contient que ce que chaque règle choisit d'y mettre
        # (ex: ko_details/na_details pour BP-22). `findings` porte la preuve
        # complète (object/expected/actual/evidence) pour CHAQUE objet,
        # y compris les OK — nécessaire pour un consommateur externe
        # (API, frontend) qui ne doit jamais avoir à redériver une preuve.
        result["findings"] = [finding.to_dict() for finding in self.findings]
        # `candidates` n'apparaît que si la règle en produit : une règle
        # purement déterministe ne doit pas exposer une clé vide qui
        # laisserait croire qu'une revue contextuelle est attendue.
        if self.candidates:
            result["candidates"] = [c.to_dict() for c in self.candidates]
        return result
