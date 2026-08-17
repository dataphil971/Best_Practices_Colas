# BP-27 — Disposition organisée du diagramme du modèle

## 1. Objectif

Évaluer les aspects **objectivement observables** du diagramme du modèle :

- chevauchements ;
- séparation spatiale cohérente entre rôles de tables lorsque ces rôles sont déterminables ;
- présence des tables attendues dans le diagramme.

Les notions plus subjectives telles que « la relation paraît trop longue » restent des diagnostics et ne deviennent pas un statut de conformité sans règle objectivable.

Statuts :

```text
OK / KO / NA
```

---

## 2. Sources

```text
<SEMANTIC_MODEL_PATH>/diagramLayout.json
<SEMANTIC_MODEL_PATH>/definition/tables/*.tmdl
<SEMANTIC_MODEL_PATH>/definition/relationships.tmdl
```

---

## 3. Préconditions

Si `diagramLayout.json` est absent, vide ou sans nœud exploitable :

```text
NA
```

La classification des rôles doit provenir d'un index partagé. Une convention de préfixes ne peut être utilisée comme vérité que si elle est explicitement configurée pour le projet.

---

## 4. Contrôles déterministes

### 4.1 Chevauchements

```python
def rectangles_overlap(a, b):
    ax1, ay1 = a.x, a.y
    ax2, ay2 = ax1 + a.width, ay1 + a.height
    bx1, by1 = b.x, b.y
    bx2, by2 = bx1 + b.width, by1 + b.height

    return ax1 < bx2 and ax2 > bx1 and ay1 < by2 and ay2 > by1
```

Un chevauchement réel :

```text
KO
```

### 4.2 Tables absentes du diagramme

Une table du modèle absente du diagramme ne suffit pas automatiquement à conclure `KO`, car plusieurs vues/diagrammes peuvent volontairement présenter des sous-ensembles.

Elle est enregistrée comme diagnostic :

```json
{
  "diagnostic_type": "TABLE_NOT_PRESENT_IN_DIAGRAM"
}
```

Si la politique de l'entreprise impose explicitement que le diagramme principal contienne toutes les tables, cette exigence doit être fournie par `COMPANY_POLICY` et peut alors produire `KO`.

### 4.3 Séparation par rôle

Cette vérification est évaluée seulement si les rôles `fact`, `dimension`, `support` sont connus avec une confiance suffisante.

Si les rôles ne peuvent pas être déterminés :

```text
NA pour ce sous-contrôle
```

Une séparation manifestement incohérente selon une métrique configurée peut produire `KO`.

---

## 5. Tables éloignées de leurs relations

Le critère statistique de distance (`mean + 3 * std`) reste utile comme **pré-diagnostic**, mais ne prouve pas une non-conformité.

```json
{
  "diagnostic_level": "INFO",
  "diagnostic_type": "LONG_RELATION_DISTANCE",
  "distance": 1280.2
}
```

Il ne modifie pas `rule_status`.

---

## 6. Statut global

```text
diagramme absent/non lisible -> NA
au moins un chevauchement prouvé -> KO
séparation de rôles objectivement non conforme -> KO
sinon -> OK
```

Les diagnostics de distance et les tables absentes n'altèrent pas le statut sauf exigence explicite de politique d'entreprise.
