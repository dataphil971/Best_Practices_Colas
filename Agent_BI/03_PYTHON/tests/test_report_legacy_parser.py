"""Tests du parseur de rapport au format legacy (`report.json` unique).

Ce format est celui de la totalité des rapports Power BI exportés avant le
PBIR étendu. Tant qu'il n'était pas lu, les cinq règles à périmètre rapport
étaient aveugles — et BP-32 concluait `OK` sans avoir rien parcouru.

Les tests ci-dessous verrouillent les quatre pièges de forme du format :
configurations sérialisées en chaîne, références de champ par alias, groupes
de visuels, et interactions logées dans la config de section.
"""

from pathlib import Path

import pytest

from engine.context import AnalysisContext
from powerbi import pbir_parser, report_legacy_parser
from rules import bp_32, bp_37, bp_38, bp_39, bp_41

FIXTURES_ROOT = Path(__file__).resolve().parent / "fixtures"
LEGACY_PROJECT = FIXTURES_ROOT / "report_legacy" / "LegacyProject"
LEGACY_REPORT = LEGACY_PROJECT / "LegacyProject.Report"


@pytest.fixture
def legacy_context() -> AnalysisContext:
    return AnalysisContext.load(LEGACY_PROJECT)


# --------------------------------------------------------------------------
# Détection du format
# --------------------------------------------------------------------------


def test_detecte_le_format_legacy():
    assert report_legacy_parser.is_legacy_report(LEGACY_REPORT) is True


def test_ne_confond_pas_un_report_json_de_definition_avec_du_legacy(tmp_path):
    """Un rapport PBIR étendu possède AUSSI un `report.json`, mais dans
    `definition/`. Le confondre ferait choisir le mauvais parseur et rendrait
    le rapport illisible sans qu'aucune erreur ne soit levée."""
    report = tmp_path / "X.Report"
    (report / "definition").mkdir(parents=True)
    (report / "definition" / "report.json").write_text("{}", encoding="utf-8")

    assert report_legacy_parser.is_legacy_report(report) is False


def test_dossier_absent_ou_none_ne_leve_pas():
    assert report_legacy_parser.is_legacy_report(None) is False
    assert report_legacy_parser.parse_report_visuals(None) == []
    assert report_legacy_parser.parse_report_filters(None) == []
    assert report_legacy_parser.parse_report_field_references(None) == set()
    assert report_legacy_parser.parse_report_implicit_aggregations(None) == []
    assert report_legacy_parser.parse_report_structure(None)["visuals"] == {}


def test_report_json_corrompu_rend_des_structures_vides_sans_lever(tmp_path):
    """Un fichier illisible ne doit jamais faire tomber l'analyse : les règles
    doivent recevoir « rien lu » et conclure NA, pas voir une exception."""
    report = tmp_path / "X.Report"
    report.mkdir(parents=True)
    (report / "report.json").write_text("{ ceci n'est pas du JSON", encoding="utf-8")

    assert report_legacy_parser.parse_report_visuals(report) == []
    assert report_legacy_parser.parse_report_filters(report) == []
    assert report_legacy_parser.parse_report_structure(report)["visuals"] == {}


# --------------------------------------------------------------------------
# Résolution des alias — le piège central du format
# --------------------------------------------------------------------------


def test_resout_l_alias_source_vers_l_entite():
    """`{"SourceRef": {"Source": "f"}}` doit devenir l'entité `F_SALES`
    déclarée par la clause `From`. Sans cela, toute référence sort avec
    `entity=None` et disparaît des surfaces d'usage."""
    query = {
        "From": [{"Name": "f", "Entity": "F_SALES"}],
        "Select": [{"Column": {"Expression": {"SourceRef": {"Source": "f"}}, "Property": "Amount"}}],
    }

    references = report_legacy_parser._resolve_field_references(query, query)

    assert ("Column", "F_SALES", "Amount") in references


def test_alias_inconnu_laisse_l_entite_a_none():
    """Une référence non résolue est conservée, pas inventée : elle signale à
    la règle qu'un champ existe sans pouvoir être rattaché à sa table."""
    query = {
        "From": [{"Name": "f", "Entity": "F_SALES"}],
        "Select": [{"Column": {"Expression": {"SourceRef": {"Source": "zzz"}}, "Property": "Amount"}}],
    }

    references = report_legacy_parser._resolve_field_references(query, query)

    assert ("Column", None, "Amount") in references
    assert ("Column", "F_SALES", "Amount") not in references


def test_accepte_aussi_la_forme_directe_entity():
    """Les expressions de filtre legacy portent `Entity` directement. Les deux
    formes cohabitent dans le même fichier."""
    node = {"Column": {"Expression": {"SourceRef": {"Entity": "D_DATE"}}, "Property": "Year"}}

    references = report_legacy_parser._resolve_field_references(node)

    assert ("Column", "D_DATE", "Year") in references


def test_config_en_chaine_json_est_decodee():
    assert report_legacy_parser._decode_embedded('{"a": 1}') == {"a": 1}
    assert report_legacy_parser._decode_embedded({"a": 1}) == {"a": 1}
    assert report_legacy_parser._decode_embedded("pas du json") is None
    assert report_legacy_parser._decode_embedded("") is None


# --------------------------------------------------------------------------
# Surfaces lues
# --------------------------------------------------------------------------


def test_inventorie_tous_les_visuels_y_compris_les_groupes():
    visuals = report_legacy_parser.parse_report_visuals(LEGACY_REPORT)
    identifiers = {v["visual_id"] for v in visuals}

    assert identifiers == {"visImplicit", "visDupA", "visDupB", "grpNav", "visText"}
    assert next(v for v in visuals if v["visual_id"] == "grpNav")["is_group"] is True
    assert next(v for v in visuals if v["visual_id"] == "visDupA")["is_group"] is False


def test_deux_visuels_identiques_partagent_la_meme_signature():
    """La signature ne dépend ni de l'identifiant, ni de la position : c'est ce
    qui permet à BP-41 de rapprocher deux visuels dupliqués."""
    visuals = report_legacy_parser.parse_report_visuals(LEGACY_REPORT)
    a = next(v for v in visuals if v["visual_id"] == "visDupA")
    b = next(v for v in visuals if v["visual_id"] == "visDupB")

    assert a["signature"] is not None
    assert a["signature"] == b["signature"]
    assert a["position"] != b["position"]


def test_visuel_decoratif_et_groupe_n_ont_pas_de_signature():
    """Un textbox ou un groupe ne participe pas à la recherche de doublons —
    sinon tout rapport riche en habillage produirait de faux candidats."""
    visuals = report_legacy_parser.parse_report_visuals(LEGACY_REPORT)

    assert next(v for v in visuals if v["visual_id"] == "visText")["signature"] is None
    assert next(v for v in visuals if v["visual_id"] == "grpNav")["signature"] is None


def test_detecte_l_agregation_implicite_avec_sa_colonne_resolue():
    aggregations = report_legacy_parser.parse_report_implicit_aggregations(LEGACY_REPORT)

    assert len(aggregations) == 1
    assert aggregations[0]["table"] == "F_SALES"
    assert aggregations[0]["column"] == "Amount"
    assert aggregations[0]["page_id"] == "pageOne"


def test_une_colonne_sans_agregation_n_est_jamais_remontee():
    """§5 de BP-32 : une colonne projetée sans nœud `Aggregation` est neutre
    (axe, slicer, ligne de tableau). La remonter serait un faux KO."""
    aggregations = report_legacy_parser.parse_report_implicit_aggregations(LEGACY_REPORT)

    assert all(a["column"] != "Year" for a in aggregations)


def test_collecte_les_filtres_aux_trois_niveaux():
    filters = report_legacy_parser.parse_report_filters(LEGACY_REPORT)
    by_level = {f.level: f for f in filters}

    assert set(by_level) == {"report", "page", "visual"}
    assert by_level["page"].page_id == "pageOne"
    assert by_level["visual"].visual_id == "visDupA"
    assert ("Column", "F_SALES", "Region") in by_level["report"].field_references


def test_le_filtre_porte_sa_ligne_dans_le_fichier_source():
    """Sans localisation, un constat sur un filtre ne pourrait citer que le
    fichier — inexploitable dans un `report.json` de plusieurs mégaoctets."""
    filters = report_legacy_parser.parse_report_filters(LEGACY_REPORT)

    assert all(f.line is not None and f.line > 0 for f in filters)


def test_structure_expose_pages_groupes_liens_interactions_et_signets():
    structure = report_legacy_parser.parse_report_structure(LEGACY_REPORT)

    assert set(structure["visuals"]) == {"pageOne", "pageTwo"}
    assert structure["groups"]["pageOne"] == {"grpNav"}
    assert ("pageOne", "visDupA", "grpNav") in structure["parent_links"]
    assert ("pageOne", "visImplicit", "visDupA", 1) in structure["interactions"]
    assert structure["bookmarks_metadata_present"] is True
    assert structure["bookmark_files"] == {"bmGroupe", "bmReset"}
    assert ("bmGroupe", ["bmReset"]) in structure["bookmark_items"]


def test_references_de_champ_couvrent_visuels_et_filtres():
    """BP-07 s'appuie sur cette surface pour décider qu'une colonne est
    utilisée. Y manquer une surface produit de faux « champ inutilisé »."""
    references = report_legacy_parser.parse_report_field_references(LEGACY_REPORT)

    assert ("Column", "F_SALES", "Amount") in references  # visuel
    assert ("Column", "D_DATE", "Year") in references  # visuel + filtre page
    assert ("Column", "F_SALES", "Region") in references  # filtre rapport
    assert ("Measure", "Mesures", "CA") in references  # filtre visuel


# --------------------------------------------------------------------------
# Intégration : le contexte choisit le bon parseur, les règles voient le rapport
# --------------------------------------------------------------------------


def test_le_contexte_identifie_le_format_legacy(legacy_context: AnalysisContext):
    assert legacy_context.report_format == "LEGACY"
    assert legacy_context.report_path is not None


def test_le_contexte_marque_pbir_quand_le_rapport_est_arborescent(tmp_path):
    project = tmp_path / "P"
    (project / "P.SemanticModel" / "definition" / "tables").mkdir(parents=True)
    (project / "P.Report" / "definition" / "pages").mkdir(parents=True)

    context = AnalysisContext.load(project)

    assert context.report_format == "PBIR"


def test_sans_dossier_report_le_format_reste_none(tmp_path):
    """Distinguer « pas de rapport » de « rapport illisible » : le premier est
    normal (un PBIP peut être livré sans son `.Report/`), le second est un
    défaut de lecture."""
    project = tmp_path / "P"
    (project / "P.SemanticModel" / "definition" / "tables").mkdir(parents=True)

    context = AnalysisContext.load(project)

    assert context.report_format is None


@pytest.mark.parametrize(
    "module",
    [bp_32, bp_37, bp_38, bp_39, bp_41],
    ids=lambda m: m.RULE_ID,
)
def test_chaque_regle_rapport_produit_des_constats_sur_un_projet_legacy(
    legacy_context: AnalysisContext, module
):
    """Le défaut corrigé ici : sur un rapport legacy, ces cinq règles
    rendaient zéro constat. BP-32 concluait même `OK` sans avoir rien lu."""
    result = module.check(legacy_context)

    assert result.findings, f"{module.RULE_ID} n'a produit aucun constat"
    assert result.execution_status in {"SUCCESS", "PARTIAL"}


def test_bp_32_conclut_ko_et_non_ok_sur_une_agregation_implicite_reelle(
    legacy_context: AnalysisContext,
):
    """Régression directe du faux `OK` : avant, faute de parseur, BP-32 ne
    voyait aucune agrégation et déclarait la conformité démontrée."""
    result = bp_32.check(legacy_context)

    assert result.rule_status == "KO"
    ko = [f for f in result.findings if f.status == "KO"]
    assert any(f.object.endswith("F_SALES[Amount]") for f in ko)


def test_bp_41_rapproche_les_deux_visuels_dupliques(legacy_context: AnalysisContext):
    result = bp_41.check(legacy_context)

    assert result.candidates, "aucun candidat de doublon détecté"
    objects = {str(o) for candidate in result.candidates for o in candidate.objects}
    assert any("visDupA" in o for o in objects)
    assert any("visDupB" in o for o in objects)
    # §2 de BP-41 : la règle produit des candidats, jamais un KO.
    assert result.rule_status == "NA"


def test_les_deux_parseurs_exposent_la_meme_interface():
    """Le contexte les substitue l'un à l'autre : une signature qui diverge
    casserait un format sans que l'autre ne le signale."""
    surface = {
        "parse_report_field_references",
        "parse_report_filters",
        "parse_report_implicit_aggregations",
        "parse_report_structure",
        "parse_report_visuals",
    }

    for name in surface:
        assert hasattr(pbir_parser, name), f"pbir_parser.{name} manquant"
        assert hasattr(report_legacy_parser, name), f"report_legacy_parser.{name} manquant"
