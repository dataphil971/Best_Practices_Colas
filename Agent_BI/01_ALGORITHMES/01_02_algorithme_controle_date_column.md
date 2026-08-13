# SEM-002 — Vérification de la Colonne DATE dans la Table D_DATES

## 1. Objectif de la Bonne Pratique

L'objectif de cette règle est de vérifier que la table de dimension des dates du modèle sémantique Power BI contient une colonne `DATE` correctement configurée avec :

```tmdl
column DATE
    dataType: dateTime
    formatString: Long Date
    summarizeBy: none
```

Cette colonne constitue la clé de base pour toutes les analyses temporelles du modèle.

---

## 2. Chemin Générique d'Accès

### Localisation de la Table

```text
<PROJECT_NAME>.SemanticModel/definition/tables/D_DATES.tmdl
```

### Variantes Possibles

Votre agent doit vérifier ces variantes (par ordre de priorité) :

1. `D_DATES.tmdl` (standard)
2. `D_DATE.tmdl` (singulier)
3. `D_Dates.tmdl` (casse mixte)
4. `D_date.tmdl` (casse mixte)

### Pattern de Recherche (Regex)

```regex
^<PROJECT_NAME>\.SemanticModel/definition/tables/D_DATE[S]?\.tmdl$
```

**Cas insensible** (Power BI accepte les deux variantes).

---

## 3. Propriétés à Contrôler

### Propriété Primaire : Existence de la Table

**Action 1** : Chercher le fichier `D_DATES.tmdl` dans le dossier `<PROJECT_NAME>.SemanticModel/definition/tables/`

| Résultat | Statut | Interprétation |
|----------|--------|---|
| Fichier trouvé | Continuer vers étape 2 | ✅ Table existe |
| Fichier non trouvé | **NA** | ❌ Table n'existe pas |

### Propriété Secondaire : Colonne DATE

**Action 2** : Dans le fichier `D_DATES.tmdl`, chercher un bloc `column` nommé `DATE` (ou variante)

| Résultat | Statut | Interprétation |
|----------|--------|---|
| Colonne `DATE` trouvée | Continuer vers étape 3 | ✅ Colonne existe |
| Colonne `DATE` non trouvée | **KO** | ❌ Colonne manquante |
| Aucune colonne trouvée | **NA** | ❌ Table vide ou corrompue |

### Propriétés Tertiaires : Configuration de la Colonne

**Action 3** : Pour la colonne `DATE`, vérifier les trois propriétés suivantes :

#### 3.1 Propriété `dataType`

```tmdl
dataType: dateTime
```

| Résultat | Statut | Interprétation |
|---|---|---|
| `dataType: dateTime` | ✅ OK | Type de données correct |
| `dataType: <autre>` (ex: `date`, `string`) | ❌ KO | Type incorrect |
| Propriété absente | ❌ NA | Propriété non trouvée |

#### 3.2 Propriété `formatString`

```tmdl
formatString: Long Date
```

| Résultat | Statut | Interprétation |
|---|---|---|
| `formatString: Long Date` | ✅ OK | Format correct |
| `formatString: <autre>` | ❌ KO | Format incorrect |
| Propriété absente | ❌ NA | Propriété non trouvée |

#### 3.3 Propriété `summarizeBy`

```tmdl
summarizeBy: none
```

| Résultat | Statut | Interprétation |
|---|---|---|
| `summarizeBy: none` | ✅ OK | Agrégation désactivée |
| `summarizeBy: <autre>` | ❌ KO | Agrégation activée |
| Propriété absente | ❌ NA | Propriété non trouvée |

---

## 4. Règle d'Évaluation de la Colonne DATE

### Logique Globale

Pour la colonne `DATE`, appliquer cette logique :

```
SI dataType = "dateTime" ET formatString = "Long Date" ET summarizeBy = "none"
    colonne = OK
SINON SI au moins une propriété est absente
    colonne = NA
SINON
    colonne = KO
```

### Matrice de Décision

| Situation | dataType | formatString | summarizeBy | Statut |
|---|---|---|---|---|
| Configuration parfaite | dateTime | Long Date | none | ✅ **OK** |
| Format manquant | dateTime | ABSENT | none | ❌ **KO** |
| DataType incorrect | string | Long Date | none | ❌ **KO** |
| Agrégation activée | dateTime | Long Date | sum | ❌ **KO** |
| Propriété absente | dateTime | Long Date | ABSENT | ⚠️ **NA** |
| Table vide | - | - | - | ⚠️ **NA** |

---

## 5. Algorithme Détaillé

### Pseudo-code Structuré

```python
# ÉTAPE 1 : Localiser la table D_DATES
table_file = find_table_file(
    "<PROJECT_NAME>.SemanticModel/definition/tables/",
    pattern="D_DATE[S]?.tmdl",
    case_insensitive=True
)

if not table_file:
    return {
        "rule_id": "SEM-002",
        "rule_name": "Colonne DATE dans la table D_DATES",
        "execution_status": "SUCCESS",
        "rule_status": "NA",
        "reason": "Table D_DATES n'existe pas",
        "table_found": False,
        "column_found": None,
        "details": []
    }

# ÉTAPE 2 : Chercher la colonne DATE
table = parse_tmdl_table(table_file)
date_column = find_column(table, name="DATE", case_insensitive=True)

if not date_column:
    return {
        "rule_id": "SEM-002",
        "rule_name": "Colonne DATE dans la table D_DATES",
        "execution_status": "SUCCESS",
        "rule_status": "KO",
        "reason": "Colonne DATE introuvable dans la table D_DATES",
        "table_found": True,
        "column_found": False,
        "details": {
            "table_name": table.name,
            "columns_found": [col.name for col in table.columns]
        }
    }

# ÉTAPE 3 : Vérifier les trois propriétés
dataType_value = date_column.get_property("dataType")
formatString_value = date_column.get_property("formatString")
summarizeBy_value = date_column.get_property("summarizeBy")

# Normaliser les valeurs
dataType_normalized = str(dataType_value).strip().lower() if dataType_value else None
formatString_normalized = str(formatString_value).strip() if formatString_value else None
summarizeBy_normalized = str(summarizeBy_value).strip().lower() if summarizeBy_value else None

# Évaluer chaque propriété
checks = {
    "dataType": dataType_normalized == "datetime",
    "formatString": formatString_normalized == "Long Date",
    "summarizeBy": summarizeBy_normalized == "none"
}

# Déterminer le statut
status_details = []

if dataType_value is None:
    status_details.append({
        "property": "dataType",
        "expected": "dateTime",
        "actual": None,
        "status": "NA"
    })
elif not checks["dataType"]:
    status_details.append({
        "property": "dataType",
        "expected": "dateTime",
        "actual": dataType_value,
        "status": "KO"
    })

if formatString_value is None:
    status_details.append({
        "property": "formatString",
        "expected": "Long Date",
        "actual": None,
        "status": "KO"  # Format obligatoire, absence = non-conformité
    })
elif not checks["formatString"]:
    status_details.append({
        "property": "formatString",
        "expected": "Long Date",
        "actual": formatString_value,
        "status": "KO"
    })

if summarizeBy_value is None:
    status_details.append({
        "property": "summarizeBy",
        "expected": "none",
        "actual": None,
        "status": "NA"
    })
elif not checks["summarizeBy"]:
    status_details.append({
        "property": "summarizeBy",
        "expected": "none",
        "actual": summarizeBy_value,
        "status": "KO"
    })

# Calculer le statut global
has_ko = any(detail["status"] == "KO" for detail in status_details)
has_na = any(detail["status"] == "NA" for detail in status_details)

if has_ko:
    rule_status = "KO"
elif has_na:
    rule_status = "NA"
else:
    rule_status = "OK"

# Retourner le résultat
return {
    "rule_id": "SEM-002",
    "rule_name": "Colonne DATE dans la table D_DATES",
    "execution_status": "SUCCESS",
    "rule_status": rule_status,
    "table_found": True,
    "column_found": True,
    "table_name": table.name,
    "column_name": date_column.name,
    "properties": {
        "dataType": dataType_value,
        "formatString": formatString_value,
        "summarizeBy": summarizeBy_value
    },
    "checks": checks,
    "details": status_details
}
```

---

## 6. Normalisation des Valeurs

Avant la comparaison, l'agent doit :

1. **Pour `dataType`** :
   - Supprimer espaces avant/après
   - Convertir en minuscules
   - Comparer avec `datetime` (Power BI accepte `dateTime`, `DateTime`, `DATETIME`)

2. **Pour `formatString`** :
   - Supprimer espaces avant/après
   - Conserver la casse (Power BI distingue la casse pour les formats)
   - Comparer avec `Long Date` exactement

3. **Pour `summarizeBy`** :
   - Supprimer espaces avant/après
   - Convertir en minuscules
   - Comparer avec `none`

### Code de Normalisation

```python
def normalize_value(value, property_name):
    if value is None:
        return None
    
    raw = str(value).strip()
    
    if property_name == "dataType":
        return raw.lower()  # ex: "dateTime" → "datetime"
    elif property_name == "formatString":
        return raw  # Conserver la casse
    elif property_name == "summarizeBy":
        return raw.lower()  # ex: "None" → "none"
    else:
        return raw
```

---

## 7. Résultat Attendu (Exemple OK)

```json
{
  "rule_id": "SEM-002",
  "rule_name": "Colonne DATE dans la table D_DATES",
  "execution_status": "SUCCESS",
  "rule_status": "OK",
  "table_found": true,
  "column_found": true,
  "table_name": "D_DATES",
  "column_name": "DATE",
  "properties": {
    "dataType": "dateTime",
    "formatString": "Long Date",
    "summarizeBy": "none"
  },
  "checks": {
    "dataType": true,
    "formatString": true,
    "summarizeBy": true
  },
  "details": []
}
```

---

## 8. Résultat Attendu (Exemple KO)

```json
{
  "rule_id": "SEM-002",
  "rule_name": "Colonne DATE dans la table D_DATES",
  "execution_status": "SUCCESS",
  "rule_status": "KO",
  "table_found": true,
  "column_found": true,
  "table_name": "D_DATES",
  "column_name": "DATE",
  "properties": {
    "dataType": "dateTime",
    "formatString": "Short Date",
    "summarizeBy": "none"
  },
  "checks": {
    "dataType": true,
    "formatString": false,
    "summarizeBy": true
  },
  "details": [
    {
      "property": "formatString",
      "expected": "Long Date",
      "actual": "Short Date",
      "status": "KO"
    }
  ]
}
```

---

## 9. Résultat Attendu (Exemple NA)

```json
{
  "rule_id": "SEM-002",
  "rule_name": "Colonne DATE dans la table D_DATES",
  "execution_status": "SUCCESS",
  "rule_status": "NA",
  "reason": "Table D_DATES n'existe pas",
  "table_found": false,
  "column_found": null,
  "details": []
}
```

---

## 10. Conditions Préalables

L'agent doit vérifier :

- [ ] Le dossier `<PROJECT_NAME>.SemanticModel/definition/tables/` est accessible
- [ ] Au moins une variante de `D_DATES.tmdl` ou `D_DATE.tmdl` peut être cherchée
- [ ] Le fichier TMDL peut être lu correctement
- [ ] Aucun caractère ou encodage n'altère la lecture

---

## 11. Résumé de la Règle

```text
RÈGLE SEM-002

1. Chercher la table D_DATES
   SI table n'existe pas → NA

2. Chercher la colonne DATE
   SI colonne n'existe pas → KO

3. Vérifier les propriétés :
   - dataType DOIT être "dateTime"
   - formatString DOIT être "Long Date"
   - summarizeBy DOIT être "none"

   SI une propriété est absente → NA
   SI une propriété n'est pas conforme → KO
   SI toutes les propriétés sont conformes → OK
```

---

## 12. Priorité des Statuts

```text
KO > NA > OK
```

| Résultat | Statut |
|----------|--------|
| Toutes les vérifications OK | `OK` |
| Au moins une propriété non conforme | `KO` |
| Au moins une propriété manquante | `NA` |
| Table n'existe pas | `NA` |

---

## 13. Cas d'Audit pour ce Projet (AI_BAROMETER_BI-CDS)

### Résultat Actuel

```
Table D_DATES: ❌ N'EXISTE PAS
Statut prévisible: NA
```

### Chemin Cherché (non trouvé)

```
c:\Users\ROUMBOP\Documents\TEST\
AI_BAROMETER_BI-CDS.SemanticModel\
  definition\
    tables\
      D_DATES.tmdl  ← ❌ Fichier non trouvé
```

---

*Algorithme générique — Spécification SEM-002*
