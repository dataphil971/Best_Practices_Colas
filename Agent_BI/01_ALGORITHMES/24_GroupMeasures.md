# BP-24 — Centraliser les mesures dans une ou plusieurs tables dédiées

> **Statut d'implémentation : ⏳ Non implémenté** — spécification fonctionnelle uniquement. Aucune règle exécutable dans le moteur : cette bonne pratique n'est ni contrôlée ni comptée dans un résultat d'analyse.

## 1. Objectif

Vérifier que toutes les mesures du modèle sémantique sont déclarées uniquement dans une ou plusieurs tables dédiées aux mesures.

Le programme analyse tous les fichiers `.tmdl` présents dans :

```text
<SEMANTIC_MODEL_PATH>/definition/tables/*.tmdl
```

Une mesure trouvée dans une table autorisée est considérée comme **OK**.

Une mesure trouvée dans une autre table est considérée comme **KO**.

Si le programme ne peut pas déterminer de façon fiable l'emplacement des mesures, le résultat est **NA**.

### Statuts

- `OK`
- `KO`
- `NA`

---

## 2. Source analysée

```text
<SEMANTIC_MODEL_PATH>/definition/tables/*.tmdl
```

Le programme doit parcourir **tous les fichiers `.tmdl` du dossier**.

Exemple :

```text
tables/
├── Date.tmdl
├── FactSales.tmdl
├── Customer.tmdl
├── Product.tmdl
├── MEASURES.tmdl
└── Geography.tmdl
```

Le contrôle ne doit donc pas se limiter au fichier `MEASURES.tmdl`.

---

## 3. Identification d'une table de mesures

Pour BP-24, une table est considérée comme une table dédiée aux mesures lorsque son nom correspond à une variante autorisée.

Les variantes suivantes sont acceptées :

```text
MEASURE
MEASURES
MESURE
MESURES
```

La comparaison est insensible à la casse.

Ainsi, les noms suivants sont équivalents :

```text
MEASURES
Measures
measures

MESURES
Mesures
mesures
```

### Noms autorisés après normalisation

```python
AUTHORIZED_MEASURE_TABLE_NAMES = {
    "measure",
    "measures",
    "mesure",
    "mesures",
}
```

### Normalisation

```python
def normalize_table_name(name: str) -> str:
    return name.strip().lower()
```

---

## 4. Le nom réel de la table doit être utilisé

Le programme doit utiliser le nom de la table déclaré dans le contenu TMDL et non uniquement le nom du fichier.

Exemple :

Fichier :

```text
MEASURES.tmdl
```

Contenu :

```tmdl
table 'Calculations'
```

Dans ce cas, le nom de la table est :

```text
Calculations
```

et non :

```text
MEASURES
```

Le contrôle doit donc se baser en priorité sur la déclaration TMDL :

```tmdl
table 'NomDeLaTable'
```

---

## 5. Recensement des mesures

Le programme doit parcourir chaque fichier `.tmdl` et identifier :

1. le nom de la table ;
2. toutes les mesures déclarées dans cette table.

Exemple :

```tmdl
table 'MEASURES'

    measure 'Total Sales' = SUM(...)
    measure 'Total Cost' = SUM(...)
    measure 'Margin' = [...]
```

Le programme doit produire conceptuellement :

```text
Total Sales -> MEASURES
Total Cost  -> MEASURES
Margin      -> MEASURES
```

Si une mesure apparaît dans une autre table :

```tmdl
table 'FactSales'

    measure 'Average Sales' = AVERAGE(...)
```

le programme doit produire :

```text
Average Sales -> FactSales -> KO
```

---

## 6. Classification des tables

Valeurs possibles :

- `MEASURE_TABLE`
- `OTHER_TABLE`

Pseudo-code :

```python
def classify_table_for_bp24(table):
    normalized_name = normalize_table_name(table.name)

    if normalized_name in {
        "measure",
        "measures",
        "mesure",
        "mesures",
    }:
        return "MEASURE_TABLE"

    return "OTHER_TABLE"
```

---

## 7. Décision par mesure

Pour chaque mesure :

```text
SI la mesure appartient à une table de mesures autorisée
    -> OK

SINON
    -> KO
```

Exemple :

| Mesure | Table | Résultat |
|---|---|---|
| Total Sales | MEASURES | OK |
| Margin | Mesures | OK |
| Revenue YTD | FactSales | KO |
| Customer Count | Customer | KO |

---

## 8. Gestion du statut NA

Le statut `NA` doit être utilisé uniquement lorsque le programme ne peut pas conclure de manière fiable.

Exemples :

- aucun fichier `.tmdl` exploitable ;
- erreur de parsing empêchant de connaître la table d'une mesure ;
- structure TMDL non supportée ;
- fichier nécessaire impossible à lire ;
- analyse incomplète ne permettant pas de garantir que toutes les mesures ont été recensées.

Si le modèle ne contient réellement aucune mesure :

```text
NA — Aucune mesure trouvée dans le modèle
```

Une mesure trouvée dans une table non autorisée doit être `KO`, et non `NA`.

---

## 9. Algorithme principal

```python
def evaluate_bp24(semantic_model):

    measures = semantic_model.all_measures()

    if not measures:
        return rule_na(
            reason="Aucune mesure trouvée dans le modèle"
        )

    results = []

    for measure in measures:

        table_name = measure.table_name
        normalized_table_name = normalize_table_name(table_name)

        is_measure_table = normalized_table_name in {
            "measure",
            "measures",
            "mesure",
            "mesures",
        }

        if is_measure_table:
            results.append(
                finding_ok(
                    object=measure.qualified_name,
                    evidence={
                        "measure": measure.name,
                        "host_table": table_name,
                        "normalized_table_name": normalized_table_name,
                        "reason": (
                            "Mesure hébergée dans une table dédiée aux mesures"
                        ),
                    },
                )
            )

        else:
            results.append(
                finding_ko(
                    object=measure.qualified_name,
                    reason=(
                        "La mesure est déclarée dans une table "
                        "qui n'est pas une table dédiée aux mesures"
                    ),
                    evidence={
                        "measure": measure.name,
                        "host_table": table_name,
                        "normalized_table_name": normalized_table_name,
                    },
                )
            )

    return aggregate_bp24_results(results)
```

---

## 10. Gestion des erreurs de parsing

Le programme doit distinguer :

```text
Aucune mesure n'existe réellement
```

de :

```text
Aucune mesure n'a été trouvée parce que certains fichiers n'ont pas pu être analysés
```

Pseudo-code :

```python
def evaluate_bp24(semantic_model):

    parsing_uncertainty = semantic_model.has_parsing_errors

    measures = semantic_model.all_measures()

    if not measures:

        if parsing_uncertainty:
            return rule_na(
                reason=(
                    "Impossible de déterminer si le modèle contient "
                    "des mesures car certains fichiers TMDL "
                    "n'ont pas pu être analysés"
                )
            )

        return rule_na(
            reason="Aucune mesure trouvée dans le modèle"
        )

    # poursuite de l'analyse...
```

---

## 11. Statut global

Priorité :

```text
KO > NA > OK
```

Pseudo-code :

```python
def aggregate_bp24_results(results):

    if any(result.status == "KO" for result in results):
        return "KO"

    if any(result.status == "NA" for result in results):
        return "NA"

    return "OK"
```

### Exemple 1 — Tout est correctement rangé

```text
MEASURES.Total Sales      -> OK
MEASURES.Margin           -> OK
MEASURES.Total Customers  -> OK
```

Résultat global :

```text
OK
```

### Exemple 2 — Une mesure est mal rangée

```text
MEASURES.Total Sales      -> OK
MEASURES.Margin           -> OK
FactSales.Total Revenue   -> KO
```

Résultat global :

```text
KO
```

Même si 99 mesures sur 100 sont bien rangées :

```text
99 OK
1 KO
```

le résultat global reste :

```text
KO
```

---

## 12. Plusieurs tables de mesures

La règle autorise une ou plusieurs tables dédiées aux mesures.

Exemple :

```text
MEASURES
MESURES
```

ou :

```text
Measures
Mesures
```

Toutes sont considérées comme valides après normalisation.

Exemple :

```text
MEASURES.Total Sales      -> OK
Mesures.Total Customers   -> OK
FactSales.Total Margin    -> KO
```

Résultat global :

```text
KO
```

---

## 13. Preuves obligatoires

### Pour un OK

```json
{
    "measure": "Total Sales",
    "host_table": "MEASURES",
    "normalized_host_table": "measures",
    "status": "OK",
    "reason": "Mesure hébergée dans une table dédiée aux mesures"
}
```

### Pour un KO

```json
{
    "measure": "Total Revenue",
    "host_table": "FactSales",
    "normalized_host_table": "factsales",
    "status": "KO",
    "reason": "Mesure déclarée en dehors d'une table dédiée aux mesures"
}
```

### Pour un NA

```json
{
    "status": "NA",
    "reason": "Impossible d'analyser complètement les fichiers TMDL"
}
```

---

## 14. Résumé de la règle

```text
RÈGLE BP-24

PARCOURIR tous les fichiers :
    definition/tables/*.tmdl

POUR chaque fichier :
    identifier la table
    identifier les mesures déclarées

NORMALISER le nom de la table :
    trim()
    lower()

UNE table est une table de mesures si son nom est :
    measure
    measures
    mesure
    mesures

POUR chaque mesure :

    SI table autorisée
        -> OK

    SINON
        -> KO

SI aucune mesure dans le modèle
    -> NA

SI analyse impossible ou incomplète
    -> NA

STATUT GLOBAL :

    SI au moins un KO
        -> KO

    SINON SI au moins un NA
        -> NA

    SINON
        -> OK
```

---

## 15. Schéma logique

```text
              +--------------------------+
              | definition/tables/*.tmdl |
              +------------+-------------+
                           |
                           v
                  Lire tous les TMDL
                           |
                           v
                 Identifier les tables
                           |
                           v
                 Identifier les mesures
                           |
                 +---------+----------+
                 |                    |
          aucune mesure          mesure trouvée
                 |                    |
                 v                    v
                NA           récupérer table hôte
                                      |
                                      v
                              normaliser son nom
                                      |
                       +--------------+--------------+
                       |                             |
              measure / measures                autre nom
              mesure / mesures                      |
                       |                             |
                       v                             v
                      OK                            KO
```

---

## 16. Principe fondamental

Le checker doit vérifier que toutes les mesures sont centralisées dans les tables explicitement autorisées.

Il doit donc :

- analyser tous les fichiers `.tmdl` ;
- ne pas se limiter au fichier `MEASURES.tmdl` ;
- identifier le nom réel de la table depuis le contenu TMDL ;
- accepter les variantes de casse ;
- signaler toute mesure présente dans une autre table ;
- retourner `NA` uniquement lorsqu'une conclusion fiable est impossible.
