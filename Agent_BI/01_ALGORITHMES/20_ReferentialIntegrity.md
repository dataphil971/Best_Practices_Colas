# BP-20 — Intégrité référentielle des relations

> **Statut d'implémentation : ⏳ Non implémenté** — spécification fonctionnelle uniquement. Aucune règle exécutable dans le moteur : cette bonne pratique n'est ni contrôlée ni comptée dans un résultat d'analyse.

## 1. Objectif

Vérifier que les valeurs non nulles du côté référencé comme clé étrangère d'une relation possèdent une correspondance du côté référentiel.

Cette règle nécessite une preuve issue des **données**.

La structure TMDL seule ne permet pas de conclure sur l'existence d'orphelins.

Statuts :

```text
OK / KO / NA
```

`WARN` n'est pas un statut Agent BI.

---

## 2. Sources structurelles

```text
<SEMANTIC_MODEL_PATH>/definition/relationships.tmdl
<SEMANTIC_MODEL_PATH>/definition/tables/*.tmdl
```

Informations :

```text
from_table
from_column
to_table
to_column
relationship_id
```

---

## 3. Sources de données

Niveaux de preuve :

```text
FULL_DATA
SAMPLE
NONE
```

### FULL_DATA

Permet de produire :

```text
OK / KO
```

### SAMPLE

Permet de produire un diagnostic statistique, mais pas une preuve exhaustive.

Par défaut :

```text
NA
```

### NONE

```text
NA
```

---

## 4. Métrique principale

La métrique principale doit être explicitement définie.

Par défaut :

```text
orphan_row_rate
=
nombre de lignes non nulles côté from sans correspondance
/
nombre total de lignes non nulles côté from
```

Métriques complémentaires :

```text
orphan_row_count
orphan_distinct_key_count
non_null_from_row_count
missing_value_row_count
```

Le checker ne doit pas mélanger :

```text
taux sur valeurs distinctes
```

et :

```text
taux sur lignes
```

dans un même seuil.

---

## 5. Valeurs manquantes

Les valeurs manquantes doivent être comptées séparément.

Exemples :

```text
NULL
blank
chaîne vide
```

La politique d'entreprise doit définir les valeurs considérées comme manquantes pour le type de colonne.

Elles ne sont pas incluses dans `orphan_row_rate`.

---

## 6. Seuil

Deux modes sont possibles.

### Tolérance zéro

```text
MAX_ORPHAN_ROW_RATE = 0
```

### Tolérance explicite

```text
MAX_ORPHAN_ROW_RATE = valeur configurée
```

Le seuil doit provenir de :

```text
COMPANY_POLICY
```

ou de la configuration de la règle.

Si aucun seuil n'est défini :

```text
NA
```

Le checker ne doit pas imposer silencieusement `1 %`.

---

## 7. Contrôle structurel

Avant l'analyse des données, vérifier que les deux références peuvent être résolues.

Si le modèle analysé est **complet** et qu'une relation référence un objet inexistant :

```text
KO
```

Si l'échec peut venir :

- d'un fichier manquant ;
- d'un parse incomplet ;
- d'un nom TMDL mal résolu ;

alors :

```text
NA
```

Pseudo-code :

```python
def validate_relationship_structure(
    rel,
    context,
):
    from_obj = context.model_index.resolve_column(
        rel.from_table,
        rel.from_column,
    )

    to_obj = context.model_index.resolve_column(
        rel.to_table,
        rel.to_column,
    )

    if from_obj and to_obj:
        return "VALID"

    if context.model_coverage_complete:
        return "INVALID"

    return "UNKNOWN"
```

---

## 8. Accès complet

Pseudo-code conceptuel :

```python
def compute_full_referential_metrics(
    relationship,
    data_access,
    missing_policy,
):
    from_rows = data_access.get_column_rows(
        relationship.from_table,
        relationship.from_column,
    )

    to_values = data_access.get_distinct_values(
        relationship.to_table,
        relationship.to_column,
    )

    non_missing = [
        value
        for value in from_rows
        if not missing_policy.is_missing(value)
    ]

    orphan_rows = [
        value
        for value in non_missing
        if value not in to_values
    ]

    orphan_distinct_keys = set(
        orphan_rows
    )

    return {
        "non_null_from_row_count": len(non_missing),
        "orphan_row_count": len(orphan_rows),
        "orphan_distinct_key_count": len(orphan_distinct_keys),
        "orphan_row_rate": (
            len(orphan_rows) / len(non_missing)
            if non_missing
            else 0.0
        ),
        "missing_value_row_count": (
            len(from_rows) - len(non_missing)
        ),
    }
```

En pratique, le backend peut exécuter une requête DAX, SQL ou équivalente côté source plutôt que charger toutes les lignes en mémoire.

---

## 9. Échantillonnage

Un échantillon peut fournir :

```text
estimated_orphan_rate
confidence_interval
sample_size
sampling_method
seed
```

Mais il ne prouve pas l'intégrité totale.

Par défaut :

```text
sample -> NA
```

avec diagnostic.

Exemple :

```json
{
  "rule_status": "NA",
  "diagnostic_level": "WARNING",
  "estimated_orphan_rate": 0.032,
  "confidence_interval_95": [0.018, 0.051]
}
```

Une future `COMPANY_POLICY` peut autoriser explicitement une décision statistique, mais cette politique doit définir :

- méthode d'échantillonnage ;
- niveau de confiance ;
- taille minimale ;
- règle de décision sur l'intervalle.

Le checker générique ne doit pas inventer ces paramètres.

---

## 10. Décision avec accès complet

```python
def evaluate_full_metrics(
    relationship,
    metrics,
    threshold,
):
    if metrics["orphan_row_rate"] > threshold:
        return finding_ko(
            object=relationship.id,
            expected=f"orphan_row_rate <= {threshold}",
            actual=metrics["orphan_row_rate"],
            evidence=metrics,
        )

    return finding_ok(
        object=relationship.id,
        expected=f"orphan_row_rate <= {threshold}",
        actual=metrics["orphan_row_rate"],
        evidence=metrics,
    )
```

---

## 11. Décision globale par relation

```python
def evaluate_relationship(
    relationship,
    context,
):
    structure = validate_relationship_structure(
        relationship,
        context,
    )

    if structure == "INVALID":
        return finding_ko(
            object=relationship.id,
            reason="Relation référence une table/colonne inexistante dans un modèle complet",
        )

    if structure == "UNKNOWN":
        return finding_na(
            object=relationship.id,
            reason="Structure de relation non résolue de manière fiable",
        )

    threshold = (
        context.company_policy
        .max_orphan_row_rate
    )

    if threshold is None:
        return finding_na(
            object=relationship.id,
            reason="Seuil d'intégrité référentielle non configuré",
        )

    access = context.data_access.get_level(
        relationship
    )

    if access == "NONE":
        return finding_na(
            object=relationship.id,
            reason="Aucun accès aux données",
        )

    if access == "SAMPLE":
        stats = context.data_access.sample_metrics(
            relationship
        )

        return finding_na(
            object=relationship.id,
            reason="Échantillon disponible mais preuve exhaustive absente",
            diagnostics=stats,
        )

    metrics = context.data_access.full_referential_metrics(
        relationship
    )

    if metrics is None:
        return finding_na(
            object=relationship.id,
            reason="Métriques d'intégrité non disponibles",
        )

    return evaluate_full_metrics(
        relationship,
        metrics,
        threshold,
    )
```

---

## 12. Relations inactives

Une relation inactive reste une relation du modèle.

La règle peut l'évaluer si l'accès aux données est disponible.

Son usage via `USERELATIONSHIP` n'est pas nécessaire pour déterminer l'existence d'orphelins.

L'activité de la relation peut être conservée comme diagnostic :

```text
isActive
```

mais ne modifie pas la définition de l'intégrité référentielle.

---

## 13. Types et comparaison

La méthode de comparaison doit respecter :

```text
dataType
collation / sensibilité à la casse si disponible
normalisation de la source
```

Le checker ne doit pas appliquer arbitrairement :

```text
lower()
trim()
```

aux valeurs métiers avant comparaison.

Toute normalisation doit être :

- définie par le contrat source ;
- ou appliquée de manière identique aux deux côtés avec une justification explicite.

---

## 14. Statut global

```python
if any(r.status == "KO" for r in results):
    rule_status = "KO"

elif any(r.status == "NA" for r in results):
    rule_status = "NA"

else:
    rule_status = "OK"
```

Priorité :

```text
KO > NA > OK
```

---

## 15. Preuve obligatoire

Un `KO` de données doit contenir :

```text
relationship_id
from_table
from_column
to_table
to_column
access_level = FULL_DATA
threshold
threshold_source
non_null_from_row_count
orphan_row_count
orphan_distinct_key_count
orphan_row_rate
missing_value_row_count
evidence
```

Un échantillon seul ne suffit pas par défaut pour produire `KO`.

---

## 16. Exemple

```json
{
  "rule_id": "BP-20",
  "rule_status": "KO",
  "ko_items": [
    {
      "relationship_id": "REL-001",
      "from": "F_SALES[PRODUCT_ID]",
      "to": "D_PRODUCT[PRODUCT_ID]",
      "access_level": "FULL_DATA",
      "orphan_row_count": 187,
      "non_null_from_row_count": 12000,
      "orphan_row_rate": 0.015583,
      "threshold": 0.01
    }
  ],
  "na_items": []
}
```

---

## 17. Résumé

```text
RÈGLE BP-20

POUR chaque relation
    VALIDER la structure

    SI structure prouvée invalide
        -> KO

    SI structure indéterminable
        -> NA

    LIRE le seuil entreprise

    SI seuil absent
        -> NA

    DÉTERMINER le niveau d'accès

    NONE
        -> NA

    SAMPLE
        -> NA + diagnostic

    FULL_DATA
        CALCULER orphan_row_rate

        SI taux > seuil
            -> KO
        SINON
            -> OK
FIN
```
