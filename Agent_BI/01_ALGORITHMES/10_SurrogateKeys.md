# BP-10 — Utiliser des clés de relation entières

## 1. Objectif

Appliquer la bonne pratique d'entreprise consistant à utiliser des clés entières pour porter les relations analytiques du modèle.

Cette règle ne doit pas prétendre qu'une relation textuelle est invalide dans Power BI.

Elle contrôle un **standard de modélisation** :

```text
clé relationnelle attendue = entier
```

Statuts :

```text
OK / KO / NA
```

---

## 2. Sources

```text
<SEMANTIC_MODEL_PATH>/definition/relationships.tmdl
<SEMANTIC_MODEL_PATH>/definition/tables/*.tmdl
```

Contexte :

```text
relationship_graph
model_object_index
table_role_index
company_policy
column_statistics
```

---

## 3. Scope

Le scope doit être explicite.

Exemple :

```yaml
bp_10:
  scope: ANALYTICAL_RELATIONSHIPS
  accepted_types:
    - int64
```

Le checker ne doit pas exclure une table parce que son nom commence par :

```text
P_
T_
```

Les exclusions éventuelles proviennent de :

```text
table_role_index
company_policy
relationship exclusions
```

---

## 4. Type attendu

Dans un modèle Power BI standard, le type entier TMDL attendu est généralement :

```text
int64
```

Le checker compare le `dataType` réellement sérialisé dans le modèle.

Il ne doit pas accepter silencieusement :

```text
int32
integer
```

si ces valeurs ne font pas partie du contrat TMDL/version analysé.

Les alias éventuels sont gérés par le resolver de type central.

---

## 5. Deux côtés de la relation

Les deux colonnes doivent satisfaire le type attendu.

Exemple :

```text
Fact[ProductKey]      int64
Dimension[ProductKey] int64
-> OK
```

```text
Fact[ProductCode]      string
Dimension[ProductCode] string
-> KO
```

```text
Fact[ProductKey]      int64
Dimension[ProductKey] string
-> KO
```

Dans ce dernier cas, le finding principal reste :

```text
type attendu non respecté
```

avec un diagnostic supplémentaire :

```text
TYPE_MISMATCH
```

---

## 6. Surrogate key vs natural key

Le fait qu'une colonne soit `int64` ne prouve pas qu'elle est réellement une surrogate key.

Donc BP-10 vérifie précisément :

```text
INTEGER_RELATION_KEY
```

et peut enregistrer :

```text
surrogate_key_semantics = UNKNOWN
```

si aucune métadonnée n'établit qu'il s'agit d'une clé de substitution.

Ne pas annoncer :

```text
surrogate key confirmée
```

uniquement à partir du type.

---

## 7. Décision

| Situation | Statut |
|---|---|
| deux côtés de type accepté | `OK` |
| au moins un côté de type explicitement différent | `KO` |
| `dataType` absent / illisible | `NA` |
| relation hors scope explicite | `NA` |
| colonne relationnelle non résolue | `NA` si couverture incomplète, sinon défaut structurel à traiter par règle adaptée |

---

## 8. Pseudo-code

```python
def evaluate_relationship_key_type(
    relationship,
    context,
):
    if context.company_policy.bp10_is_excluded(
        relationship.id
    ):
        return finding_na(
            object=relationship.id,
            reason="Relation hors périmètre BP-10",
            reason_code="OUT_OF_SCOPE",
        )

    endpoints = context.relationship_graph.resolve_endpoints(
        relationship.id
    )

    if not endpoints.complete:
        return finding_na(
            object=relationship.id,
            reason="Colonnes de relation non résolues",
        )

    from_type = context.model_object_index.get_datatype(
        endpoints.from_table,
        endpoints.from_column,
    )

    to_type = context.model_object_index.get_datatype(
        endpoints.to_table,
        endpoints.to_column,
    )

    if from_type is None or to_type is None:
        return finding_na(
            object=relationship.id,
            reason="dataType non disponible pour au moins une clé",
        )

    accepted = context.company_policy.bp10_accepted_types

    evidence = {
        "from": endpoints.from_qualified_name,
        "from_type": from_type,
        "to": endpoints.to_qualified_name,
        "to_type": to_type,
        "accepted_types": sorted(accepted),
    }

    if (
        from_type in accepted
        and to_type in accepted
    ):
        return finding_ok(
            object=relationship.id,
            evidence=evidence,
        )

    diagnostics = []

    if from_type != to_type:
        diagnostics.append(
            "TYPE_MISMATCH"
        )

    return finding_ko(
        object=relationship.id,
        expected=f"both endpoints in {sorted(accepted)}",
        actual=f"{from_type} / {to_type}",
        evidence=evidence,
        diagnostics=diagnostics,
    )
```

---

## 9. Cardinalité

La cardinalité de la relation n'est pas utilisée pour deviner si une colonne est « technique ».

BP-10 peut être appliquée :

- aux relations `1:*` ;
- aux relations `*:*` si elles sont encore présentes ;
- aux relations `1:1`;

selon le scope de policy.

BP-03 décide séparément si la cardinalité elle-même est conforme.

---

## 10. Statistiques

Si disponibles :

```text
distinct_count
average_text_length
dictionary_size
```

elles peuvent servir à prioriser la correction.

Exemple :

```json
{
  "diagnostic_level": "INFO",
  "distinct_count": 250000,
  "average_text_length": 32
}
```

Elles ne modifient pas le statut de base.

---

## 11. Aucun lien

Si aucune relation n'est présente :

```text
NA
```

---

## 12. Statut global

```python
evaluable = [
    r for r in results
    if r.reason_code != "OUT_OF_SCOPE"
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

---

## 13. Preuve obligatoire

```text
relationship_id
from_table
from_column
from_type
to_table
to_column
to_type
accepted_types
policy_id
source_files
```

---

## 14. Références techniques

Microsoft recommande les surrogate keys pour prendre en charge la modélisation en étoile lorsque la dimension ne possède pas une colonne unique adaptée.

BP-10 ajoute ici un standard d'entreprise plus précis :

```text
les clés relationnelles doivent être entières
```

Ce standard est donc contrôlé comme une policy, et non présenté comme une contrainte universelle du moteur Power BI.

---

## 15. Résumé

```text
RÈGLE BP-10

POUR chaque relation dans le scope
    RÉSOUDRE les deux colonnes
    LIRE les deux dataType

    SI type illisible
        -> NA

    SI les deux types sont acceptés
        -> OK

    SINON
        -> KO

    SI types différents
        ajouter diagnostic TYPE_MISMATCH
FIN
```
