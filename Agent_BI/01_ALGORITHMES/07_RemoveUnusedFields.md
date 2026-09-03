# BP-07 — Éliminer les colonnes visibles et inutilisées du modèle

> **Statut d'implémentation : ✅ Implémenté** — moteur : [`03_PYTHON/rules/bp_07.py`](../03_PYTHON/rules/bp_07.py), tests : `03_PYTHON/tests/test_bp_07.py`.

## 1. Objectif

Identifier les colonnes **visibles** dont l'absence d'utilisation peut être démontrée dans le périmètre du PBIP analysé.

La règle doit éviter les faux `KO`.

L'absence d'une référence dans un simple regex ne constitue pas une preuve suffisante qu'une colonne est inutilisée.

Statuts :

```text
OK / KO / NA
```

---

## 2. Périmètre de la conclusion

Par défaut, la règle conclut uniquement sur :

```text
usage_scope = CURRENT_PBIP
```

Elle ne prétend pas connaître :

- d'autres rapports connectés au même modèle ;
- des usages XMLA externes ;
- Analyse dans Excel ;
- des outils tiers ;
- des consommateurs hors du projet fourni.

Le message utilisateur doit donc parler de :

> colonne inutilisée dans le PBIP analysé

et non de :

> colonne inutilisée partout.

Une politique d'entreprise peut élargir le périmètre seulement si les sources supplémentaires sont effectivement accessibles.

---

## 3. Sources

### Modèle sémantique

```text
<SEMANTIC_MODEL_PATH>/definition/tables/*.tmdl
<SEMANTIC_MODEL_PATH>/definition/relationships.tmdl
<SEMANTIC_MODEL_PATH>/definition/roles.tmdl
```

Selon la structure disponible, le contexte peut également inclure :

```text
hierarchies
perspectives
calculation groups
calculated columns
calculated tables
```

### Rapport

```text
<REPORT_PATH>/definition/pages/**/*.json
<REPORT_PATH>/definition/report.json
<REPORT_PATH>/definition/filters.json
```

Les chemins exacts peuvent varier selon la version PBIR.

Le moteur doit utiliser les données normalisées du `AnalysisContext` et non dépendre d'un seul chemin JSON codé en dur.

---

## 4. UsageIndex partagé

Cette règle doit consommer un index central :

```text
usage_index
```

Il est construit une seule fois pour le PBIP et peut être réutilisé par les autres règles.

Structure possible :

```python
usage_index = {
    ("TABLE", "COLUMN"): {
        "dax": [],
        "relationships": [],
        "sort_by": [],
        "hierarchies": [],
        "roles": [],
        "report_visuals": [],
        "report_filters": [],
        "report_sort": [],
        "drillthrough": [],
        "tooltips": [],
        "other": [],
    }
}
```

Chaque référence conserve sa provenance.

---

## 5. Références à rechercher

Une colonne est considérée comme utilisée si elle apparaît de manière résolue dans au moins une catégorie pertinente.

### 5.1 DAX

Inclure les références provenant notamment :

- des mesures ;
- des colonnes calculées ;
- des tables calculées ;
- des expressions de calculation groups lorsque disponibles ;
- des expressions RLS si elles sont présentes dans le contexte.

### 5.2 Modèle

Inclure :

- `fromColumn` / `toColumn` des relations ;
- `sortByColumn` ;
- hiérarchies ;
- propriétés de modèle faisant explicitement référence à une colonne.

### 5.3 Rapport

Inclure les usages dans :

- axes ;
- valeurs ;
- légendes ;
- lignes / colonnes de matrices ;
- info-bulles ;
- tris ;
- slicers ;
- filtres de visuel ;
- filtres de page ;
- filtres de rapport ;
- drillthrough ;
- autres projections PBIR structurées.

---

## 6. Ne pas parser le DAX avec un regex unique

Le pseudo-code suivant est insuffisant :

```python
re.findall(r"([A-Za-z_][\w]*)\[([^\]]+)\]", dax)
```

Il ne couvre correctement qu'une partie des références qualifiées et ne résout pas les ambiguïtés de contexte.

Le moteur doit préférer :

```text
tokenizer / parser / AST DAX
```

ou un index de références déjà produit par l'extracteur DAX partagé.

Pseudo-code :

```python
def extract_dax_column_references(expression, host_object, context):
    parsed = context.dax_parser.parse(expression)

    if not parsed.success:
        return ReferenceExtraction(
            resolved=set(),
            unresolved=[{
                "expression": expression,
                "reason": parsed.error,
            }],
        )

    resolved = set()
    unresolved = []

    for ref in parsed.references:
        if ref.kind == "COLUMN" and ref.is_resolved:
            resolved.add((ref.table_name, ref.column_name))

        elif ref.may_reference_column and not ref.is_resolved:
            unresolved.append(ref)

    return ReferenceExtraction(
        resolved=resolved,
        unresolved=unresolved,
    )
```

---

## 7. Références non qualifiées ou ambiguës

Une référence comme :

```dax
[Amount]
```

ne doit jamais être attribuée arbitrairement à toutes les colonnes nommées `Amount`.

Selon le contexte DAX, elle peut représenter :

- une mesure ;
- une colonne en contexte de ligne ;
- une référence non résolue.

Le moteur doit utiliser :

- le type d'objet hôte ;
- la table hôte ;
- le contexte de ligne ;
- les symboles disponibles ;
- l'AST DAX.

Si la référence ne peut pas être résolue de manière fiable :

```text
unresolved_reference
```

Cette ambiguïté doit empêcher un `KO` pour toute colonne candidate potentiellement concernée.

---

## 8. Extraction PBIR

Le moteur ne doit pas dépendre d'un chemin JSON unique.

Il doit parcourir les objets structurés et collecter les références reconnues.

Exemple :

```python
def collect_report_field_references(node, refs, unresolved):
    if isinstance(node, dict):
        field = try_resolve_pbir_field(node)

        if field.is_resolved:
            refs.add((field.entity, field.property))

        elif field.looks_like_field_reference:
            unresolved.append(field.raw)

        for value in node.values():
            collect_report_field_references(
                value,
                refs,
                unresolved,
            )

    elif isinstance(node, list):
        for item in node:
            collect_report_field_references(
                item,
                refs,
                unresolved,
            )
```

Le parser PBIR doit être versionné ou tolérant aux variations de structure.

---

## 9. Complétude de l'analyse

Pour produire un `KO`, la règle doit savoir si les principales surfaces d'usage ont été analysées.

Exemple :

```python
coverage = {
    "semantic_model": True,
    "relationships": True,
    "dax": True,
    "report": True,
    "report_filters": True,
}
```

Si le rapport est attendu mais absent ou illisible :

```text
coverage.report = False
```

Une colonne visible non utilisée dans le modèle ne peut alors pas être déclarée inutilisée avec certitude dans le PBIP complet.

Elle devient :

```text
NA
```

sauf si la politique de la règle a explicitement été configurée pour analyser uniquement le modèle sémantique.

---

## 10. Décision par colonne

### Colonne masquée

La bonne pratique cible les colonnes visibles.

```text
isHidden présent -> NA
```

avec éventuellement :

```text
diagnostic_level = INFO
```

si la colonne semble également inutilisée.

### Colonne visible avec usage résolu

```text
au moins une référence fiable -> OK
```

### Colonne visible sans usage résolu

Avant de produire `KO`, vérifier :

1. la couverture d'analyse ;
2. les références non résolues ;
3. les erreurs de parsing pouvant concerner cette colonne.

```python
def evaluate_column(table, column, context):
    if column.is_hidden:
        return finding_na(
            object=column.qualified_name,
            reason="Colonne masquée : hors périmètre de la règle",
        )

    key = canonical_column_key(
        table.name,
        column.name,
    )

    usages = context.usage_index.get(key, [])

    if usages:
        return finding_ok(
            object=column.qualified_name,
            evidence={"usages": usages},
        )

    blockers = find_uncertainty_blockers(
        column=column,
        unresolved_references=context.unresolved_references,
        coverage=context.usage_coverage,
    )

    if blockers:
        return finding_na(
            object=column.qualified_name,
            reason="Absence d'usage non démontrable avec certitude",
            evidence={
                "blockers": blockers,
                "usage_scope": "CURRENT_PBIP",
            },
        )

    return finding_ko(
        object=column.qualified_name,
        reason="Colonne visible sans aucune utilisation détectée dans le PBIP analysé",
        evidence={
            "usage_scope": "CURRENT_PBIP",
            "searched_surfaces": context.usage_coverage,
        },
    )
```

---

## 11. Matrice de décision

| Situation | Statut |
|---|---|
| colonne masquée | `NA` |
| colonne visible, au moins un usage résolu | `OK` |
| colonne visible, aucun usage, couverture complète, aucune ambiguïté | `KO` |
| colonne visible, aucun usage, rapport absent/incomplet | `NA` |
| colonne visible potentiellement concernée par une référence DAX non résolue | `NA` |
| parsing TMDL/PBIR insuffisant pour la colonne | `NA` |

---

## 12. Statut global

Les colonnes masquées classées `NA` car hors périmètre ne doivent pas à elles seules faire basculer la règle globale en `NA`.

Pseudo-code :

```python
evaluable = [
    r for r in results
    if not r.reason_code == "HIDDEN_OUT_OF_SCOPE"
]

if any(r.status == "KO" for r in evaluable):
    rule_status = "KO"

elif any(r.status == "NA" for r in evaluable):
    rule_status = "NA"

elif evaluable:
    rule_status = "OK"

else:
    rule_status = "NA"
```

Priorité sur le périmètre évaluable :

```text
KO > NA > OK
```

---

## 13. Preuve obligatoire pour `KO`

Chaque colonne `KO` doit comporter au minimum :

```text
table
column
visibility
usage_scope
searched_surfaces
resolved_usage_count = 0
unresolved_reference_count_relevant = 0
coverage_complete = true
evidence
```

Sans preuve de couverture suffisante :

```text
NA
```

---

## 14. Exemple de résultat

```json
{
  "rule_id": "BP-07",
  "rule_status": "KO",
  "usage_scope": "CURRENT_PBIP",
  "coverage": {
    "semantic_model": true,
    "relationships": true,
    "dax": true,
    "report": true,
    "report_filters": true
  },
  "ko_items": [
    {
      "table": "D_USERS",
      "column": "LEGACY_COMMENT_FIELD",
      "resolved_usage_count": 0,
      "unresolved_reference_count_relevant": 0,
      "coverage_complete": true
    }
  ],
  "na_items": []
}
```

---

## 15. Résumé

```text
RÈGLE BP-07

CONSTRUIRE une seule fois usage_index

POUR chaque colonne
    SI colonne masquée
        -> NA hors périmètre

    SINON SI usage résolu présent
        -> OK

    SINON
        VÉRIFIER couverture + références non résolues

        SI analyse incomplète ou ambiguë
            -> NA

        SINON
            -> KO
FIN
```

La règle ne doit jamais produire `KO` uniquement parce qu'une recherche regex n'a trouvé aucune occurrence.
