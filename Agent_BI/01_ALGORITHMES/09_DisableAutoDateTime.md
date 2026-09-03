# BP-09 — Désactiver l'option Auto Date/Time

> **Statut d'implémentation : ✅ Implémenté** — moteur : [`03_PYTHON/rules/bp_09.py`](../03_PYTHON/rules/bp_09.py), tests : `03_PYTHON/tests/test_bp_09.py`.

## 1. Objectif

Vérifier, uniquement à partir de preuves observables dans le modèle, que l'option Power BI **Auto Date/Time** est désactivée lorsque la politique de gouvernance l'exige.

Statuts Agent BI :

```text
OK / KO / NA
```

La règle ne doit jamais transformer une absence de métadonnée en `KO` sans preuve que cette absence signifie effectivement « activé » pour le fichier analysé.

---

## 2. Source principale

```text
<SEMANTIC_MODEL_PATH>/definition/model.tmdl
```

Métadonnée actuellement exploitée :

```text
annotation __PBI_TimeIntelligenceEnabled = <VALUE>
```

Cette annotation est une métadonnée observée dans les projets Power BI, mais le checker doit rester prudent lorsqu'elle est absente.

---

## 3. Rappel fonctionnel

Lorsque Auto Date/Time est activé, Power BI peut créer des tables de dates automatiques cachées pour les colonnes de date/date-heure éligibles.

La conformité de cette règle porte sur le réglage du modèle, pas sur une estimation du nombre exact de tables cachées.

Le nombre de colonnes date/dateTime peut être conservé comme diagnostic, mais ne doit pas modifier le verdict.

---

## 4. Décision

| Situation | Statut |
|---|---|
| annotation présente avec valeur normalisée `0` | `OK` |
| annotation présente avec valeur normalisée `1` | `KO` |
| annotation absente | `NA` |
| annotation présente mais valeur inconnue/illisible | `NA` |
| `model.tmdl` absent ou illisible | `NA` |

### Pourquoi l'absence donne `NA`

La documentation Power BI indique que les options globales et du fichier courant peuvent être activées ou désactivées.

Elle ne fournit pas, dans le contrat TMDL utilisé ici, une garantie permettant d'affirmer :

```text
annotation absente = option du fichier courant activée
```

Le moteur ne doit donc pas fabriquer cette équivalence.

---

## 5. Lecture robuste

```python
def find_annotation(model, annotation_name):
    for annotation in model.annotations:
        if annotation.name == annotation_name:
            return annotation.value

    return MISSING
```

Si aucun parseur TMDL structuré n'est disponible, un fallback textuel peut être utilisé, mais l'extraction doit conserver :

```text
raw_value
source_file
parse_method
```

---

## 6. Normalisation

```python
def normalize_time_intelligence_flag(raw):
    if raw is MISSING:
        return None

    value = str(raw).strip().strip('"').strip("'")

    if value == "0":
        return False

    if value == "1":
        return True

    return None
```

Le moteur ne doit pas accepter silencieusement :

```text
false
true
disabled
enabled
```

si ces variantes ne sont pas explicitement démontrées comme valides dans le format analysé.

Elles restent :

```text
NA
```

jusqu'à validation du contrat.

---

## 7. Pseudo-code

```python
def evaluate_auto_date_time(context):
    model = context.semantic_model

    if model is None or not model.model_tmdl_readable:
        return rule_na(
            reason="model.tmdl absent ou illisible"
        )

    raw = model.get_annotation(
        "__PBI_TimeIntelligenceEnabled"
    )

    if raw is MISSING:
        return rule_na(
            reason=(
                "Annotation __PBI_TimeIntelligenceEnabled absente : "
                "état du réglage non démontrable à partir de cette preuve"
            ),
            evidence={
                "annotation_found": False,
            },
        )

    normalized = normalize_time_intelligence_flag(raw)

    if normalized is False:
        return rule_ok(
            expected="Auto Date/Time désactivé",
            actual=raw,
            evidence={
                "annotation_found": True,
                "source_file": model.model_tmdl_path,
            },
        )

    if normalized is True:
        return rule_ko(
            expected="Auto Date/Time désactivé",
            actual=raw,
            evidence={
                "annotation_found": True,
                "source_file": model.model_tmdl_path,
            },
        )

    return rule_na(
        reason="Valeur de l'annotation non reconnue",
        evidence={
            "annotation_found": True,
            "raw_value": raw,
        },
    )
```

---

## 8. Statut technique séparé

L'impossibilité de lire le fichier ne doit pas introduire un quatrième statut métier.

Exemple :

```json
{
  "execution_status": "ERROR",
  "rule_status": "NA"
}
```

et non :

```json
{
  "rule_status": "NON_EVALUE"
}
```

Le contrat de conformité reste toujours :

```text
OK / KO / NA
```

---

## 9. Diagnostic optionnel

Lorsque le réglage est explicitement actif (`KO`), le moteur peut recenser les colonnes de type date/dateTime potentiellement concernées.

Exemple :

```json
{
  "diagnostic": {
    "date_columns": [
      "D_DATE[Date]",
      "F_SALES[OrderDate]"
    ]
  }
}
```

Cette liste sert uniquement à illustrer l'impact potentiel.

Elle ne doit pas être utilisée pour modifier le statut.

---

## 10. Résultat attendu

### Exemple OK

```json
{
  "rule_id": "BP-09",
  "execution_status": "SUCCESS",
  "rule_status": "OK",
  "expected": "__PBI_TimeIntelligenceEnabled = 0",
  "actual": "0"
}
```

### Exemple KO

```json
{
  "rule_id": "BP-09",
  "execution_status": "SUCCESS",
  "rule_status": "KO",
  "expected": "__PBI_TimeIntelligenceEnabled = 0",
  "actual": "1"
}
```

### Exemple NA

```json
{
  "rule_id": "BP-09",
  "execution_status": "SUCCESS",
  "rule_status": "NA",
  "actual": null,
  "reason": "Annotation absente : état réel non démontrable"
}
```

---

## 11. Conditions empêchant un faux OK / faux KO

### Pour `OK`

Le moteur doit avoir lu explicitement :

```text
__PBI_TimeIntelligenceEnabled = 0
```

### Pour `KO`

Le moteur doit avoir lu explicitement :

```text
__PBI_TimeIntelligenceEnabled = 1
```

### Sinon

```text
NA
```

---

## 12. Résumé

```text
RÈGLE BP-09

LIRE model.tmdl

SI fichier absent / illisible
    -> NA

RECHERCHER __PBI_TimeIntelligenceEnabled

SI annotation absente
    -> NA

SI valeur = 0
    -> OK

SI valeur = 1
    -> KO

SINON
    -> NA
```
