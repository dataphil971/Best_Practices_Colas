# BP-01 — Intégrité structurelle du graphe relationnel

> **Statut d'implémentation : ✅ Implémenté** — moteur : [`03_PYTHON/rules/bp_01.py`](../03_PYTHON/rules/bp_01.py), tests : `03_PYTHON/tests/test_bp_01.py`.

## 1. Objectif de la bonne pratique

Vérifier que le graphe relationnel du modèle est **structurellement exploitable** :

```text
toute relation pointe vers des objets qui existent
aucun couple de tables n'est relié par plusieurs chemins actifs
```

### Ce que cette règle ne contrôle pas

**La topologie du modèle n'est pas un critère de conformité.** Les formes suivantes sont toutes légitimes :

```text
STAR          SNOWFLAKE          GALAXY / CONSTELLATION          HYBRID
```

Un modèle en flocon n'est pas un défaut. Une constellation non plus. La forme du modèle est une **description**, jamais un verdict — elle est publiée à titre informatif (§9) et ne fait basculer aucun statut.

Cette règle ne déduit jamais le rôle d'une table de son nom :

```text
D_*   F_*   Dim*   Fact*   P_*   T_*
```

Ces conventions peuvent nourrir un diagnostic, jamais une preuve.

### Partage avec BP-03

La **cardinalité** et le **filtrage croisé** appartiennent entièrement à BP-03, qui est implémentée et les traite par relation :

```text
MANY_TO_MANY                  -> BP-03
ONE_TO_ONE                    -> BP-03
crossFilteringBehavior        -> BP-03
défauts TMDL de cardinalité   -> BP-03
```

BP-01 ne doit **jamais** émettre de constat sur ces propriétés : deux `KO` pour une même cause détruisent la lisibilité du rapport, et un désaccord entre les deux règles sur un même objet détruit leur crédibilité.

Une relation dont la cardinalité est en cause est signalée par BP-01 comme :

```text
NA / DELEGATED_BP03
```

et exclue de son statut global.

Statuts :

```text
OK / KO / NA
```

---

## 2. Emplacement des fichiers concernés

```text
<SEMANTIC_MODEL_PATH>/definition/relationships.tmdl
<SEMANTIC_MODEL_PATH>/definition/tables/*.tmdl
```

Le checker consomme le contexte partagé, construit une seule fois à la lecture du PBIP. Il ne relit pas le projet pour chaque relation :

```text
context.relationships
context.tables          (et, par table, ses colonnes)
```

L'index `table -> colonnes` est construit **une fois** par le checker à partir de `context.tables`, à la manière de `_build_m_type_index` dans `bp_11.py`. Le contexte n'expose pas d'index dédié, et il n'a pas à en exposer un pour une seule règle.

---

## 3. Élément(s) / propriété(s) à contrôler

Pour chaque relation :

```text
id
from_table      from_column
to_table        to_column
is_active
```

Pour la résolution des références, l'index des tables et de leurs colonnes.

### 3.1 Normalisation des noms

TMDL entoure de guillemets simples tout nom contenant un caractère spécial ou un espace. La comparaison doit se faire sur le nom **dénormalisé** :

```text
D_CHOICE.'ID '      ->      table = D_CHOICE, colonne = "ID " (espace final conservé)
```

Un espace en début ou fin de nom est significatif : il fait partie de l'identité de la colonne. Le signaler relève de BP-21, pas d'ici — une colonne mal nommée mais existante n'est pas une référence cassée.

---

## 4. Règles d'évaluation

### 4.1 Références cassées

| Situation | Statut | Interprétation |
|---|---|---|
| les 4 extrémités de la relation existent | `OK` | relation exploitable |
| `from_table` ou `to_table` absente du modèle | `KO` | relation pointant vers une table inexistante |
| `from_column` ou `to_column` absente de sa table | `KO` | relation pointant vers une colonne inexistante |
| aucune table lisible dans le modèle | `NA` | existence des références indécidable |

Une référence cassée est une preuve directe : l'objet est nommé dans `relationships.tmdl` et absent des fichiers de tables. Aucune interprétation n'est requise.

### 4.2 Chemins de filtrage multiples

Deux tables reliées par plus d'un chemin de **propagation de filtre** créent une ambiguïté que Power BI résout arbitrairement.

#### Le graphe à parcourir est ORIENTÉ

C'est le point critique de cette section, et l'erreur à ne pas commettre.

Une relation à filtrage simple ne propage que dans **un** sens : du côté `one` vers le côté `many`. Le graphe de propagation n'est donc **pas** le graphe non orienté des relations.

```text
graphe NON orienté   : deux tables « reliées », sans direction   -> FAUX
graphe ORIENTÉ       : one -> many, sens de propagation réel     -> CORRECT
```

Contre-exemple mesuré, sur un modèle en constellation à 9 relations et 2 tables de faits partageant 2 dimensions :

```text
lecture NON orientée   ->  9 couples « ambigus »   -> 9 KO, tous faux
lecture ORIENTÉE       ->  0 couple ambigu          -> OK, correct
```

Une constellation est saine : deux faits partageant des dimensions ne créent aucune ambiguïté, parce qu'un fait ne propage jamais son filtre vers une dimension. Confondre les deux lectures transforme un modèle conforme en 9 non-conformités.

#### Décision

| Situation | Statut | Interprétation |
|---|---|---|
| au plus un chemin orienté entre deux tables | `OK` | filtrage déterminé |
| plusieurs chemins orientés entre deux tables | `KO` | ambiguïté de filtrage |
| chemins multiples dont un seul est actif | `OK` | cas nominal des relations inactives |
| `is_active` non résolu sur un chemin du cycle | `NA` | activité indéterminable |

Cas réel d'ambiguïté, qui subsiste en lecture orientée :

```text
Date  ──1:*──>  Sales
Date  ──1:*──>  Product  ──1:*──>  Sales

Date atteint Sales par deux chemins    ->  KO
```

Un cycle **passant par au moins une relation inactive** n'est pas un défaut : c'est le mécanisme normal des relations de rôle (`USERELATIONSHIP`).

Une relation à **filtrage bidirectionnel** rend son arête franchissable dans les deux sens et peut créer une ambiguïté — mais elle est déjà un `KO` de BP-03. BP-01 l'exclut donc de son calcul et ne produit pas un second `KO` pour la même cause.

### 4.3 Cas délégués et hors périmètre

| Situation | Statut | `reason_code` |
|---|---|---|
| relation `MANY_TO_MANY` ou `ONE_TO_ONE` | `NA` | `DELEGATED_BP03` |
| aucune relation dans le modèle | `NA` | — |
| `relationships.tmdl` absent ou illisible | `NA` | — |

Un modèle sans relation n'est pas non conforme : il peut être légitime (table unique, modèle en cours de construction). Le statut global est `NA`, jamais `KO`.

---

## 5. Parcours complet du modèle

Le checker parcourt **toutes** les relations, et pour la détection d'ambiguïté **tous** les couples de tables reliées. Il ne s'arrête jamais à la première anomalie : un modèle peut porter plusieurs références cassées, et l'utilisateur doit toutes les recevoir en une passe.

---

## 6. Détection robuste

```text
noms entre guillemets simples          -> dénormaliser avant comparaison
casse                                  -> comparaison sensible à la casse (TMDL l'est)
espaces significatifs                  -> conservés, jamais rognés
relation sans id                       -> utiliser from/to comme identifiant
propriété is_active absente            -> défaut TMDL : relation active
```

Le défaut de `is_active` doit être documenté et sourcé, jamais supposé silencieusement (cf. `agent-bi-evidence-sourcing`, et le précédent des défauts de cardinalité dans `bp_03.py`).

---

## 7. Pseudo-code détaillé

```python
def evaluate_relationship_integrity(context):

    if context.relationships is None:
        return rule_na(
            reason="Relations du modèle non analysables"
        )

    if not context.relationships:
        return rule_na(
            reason="Aucune relation dans le modèle"
        )

    if not context.tables:
        return rule_na(
            reason="Aucune table lisible : existence des références indécidable"
        )

    # table -> {noms de colonnes}, construit UNE fois pour tout le contrôle.
    column_index = build_column_index(context.tables)

    results = []

    for relationship in context.relationships:

        if is_delegated_to_bp03(relationship):
            results.append(
                finding_na(
                    object=relationship.id,
                    reason="Cardinalité contrôlée par BP-03",
                    reason_code="DELEGATED_BP03",
                )
            )
            continue

        missing = resolve_missing_references(
            relationship,
            column_index,
        )

        if missing:
            results.append(
                finding_ko(
                    object=relationship.id,
                    reason="Relation référençant un objet absent du modèle",
                    evidence={
                        "missing": missing,
                        "from": qualify(relationship, "from"),
                        "to": qualify(relationship, "to"),
                    },
                )
            )
            continue

        results.append(
            finding_ok(
                object=relationship.id,
                evidence={
                    "from": qualify(relationship, "from"),
                    "to": qualify(relationship, "to"),
                },
            )
        )

    results.extend(
        detect_ambiguous_paths(context.relationships)
    )

    return aggregate(results)
```

```python
def detect_ambiguous_paths(relationships):
    """Ambiguïté = plus d'un chemin ORIENTÉ de propagation de filtre.

    Le graphe est orienté du côté `one` vers le côté `many` : une relation à
    filtrage simple ne propage que dans ce sens. Parcourir le graphe non
    orienté transforme toute constellation saine en non-conformité (§4.2).
    """
    edges = [
        (r.to_table, r.from_table)          # one -> many
        for r in relationships
        if is_active(r) and not is_delegated_to_bp03(r)
    ]
    findings = []

    for pair, paths in group_directed_paths(edges).items():
        if len(paths) <= 1:
            continue
        findings.append(
            finding_ko(
                object=f"{pair[0]} -> {pair[1]}",
                reason="Plusieurs chemins de filtrage entre deux tables",
                evidence={"paths": paths},
            )
        )
    return findings
```

---

## 8. Calcul du statut global

Les éléments délégués et hors périmètre ne comptent pas.

```python
evaluable = [
    result
    for result in results
    if result.reason_code not in {
        "OUT_OF_SCOPE",
        "DELEGATED_BP03",
    }
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

Priorité :

```text
KO > NA > OK
```

---

## 9. Structure du résultat

La forme du modèle est publiée **à côté** du verdict, jamais dedans.

```json
{
  "rule_id": "BP-01",
  "rule_status": "OK",
  "summary": {
    "schema_type": "GALAXY",
    "relationships_total": 9,
    "relationships_checked": 9,
    "delegated_to_bp03": 0,
    "broken_references": 0,
    "ambiguous_pairs": 0
  }
}
```

Exemple non conforme :

```json
{
  "rule_id": "BP-01",
  "rule_status": "KO",
  "summary": {
    "schema_type": "SNOWFLAKE",
    "broken_references": 1
  },
  "ko_items": [
    {
      "object": "rel_sales_product",
      "reason": "Relation référençant un objet absent du modèle",
      "evidence": {
        "missing": ["Product.ProductKey"],
        "from": "Sales.ProductKey",
        "to": "Product.ProductKey"
      }
    }
  ]
}
```

`schema_type` est **descriptif**. Il ne doit apparaître dans aucune condition de statut, et un lecteur ne doit jamais pouvoir déduire un verdict de sa valeur.

---

## 10. Message présenté à l'utilisateur

Conforme :

```text
[OK] BP-01 — Intégrité structurelle du graphe relationnel
     9 relations contrôlées, aucune référence cassée, aucun chemin ambigu.
     Forme du modèle : GALAXY (informatif — non évalué).
```

Non conforme :

```text
[KO] BP-01 — Intégrité structurelle du graphe relationnel
     - rel_sales_product : la relation référence Product.ProductKey, absente
       du modèle sémantique.
```

---

## 11. Conditions empêchant un faux `OK`

Un `OK` n'est valide que si **toutes** ces conditions sont réunies :

```text
relationships.tmdl a été lu, et son contenu interprété
l'index des colonnes a été construit à partir d'au moins une table
au moins une relation a été réellement contrôlée
```

Un `OK` rendu alors que zéro relation a été examinée est interdit : c'est un `NA`. Le contrôle minimal est explicite — *combien de relations cette règle a-t-elle réellement examinées ?* Si la réponse est zéro, le statut ne peut pas être `OK` (cf. `agent-bi-verdict-doubt`).

Une relation dont les références n'ont pas pu être résolues ne doit jamais être comptée comme conforme.

---

## 12. Résumé de la règle

```text
RÈGLE BP-01

LIRE relationships.tmdl et l'index des tables/colonnes

POUR chaque relation

    SI cardinalité MANY_TO_MANY ou ONE_TO_ONE
        -> NA / DELEGATED_BP03

    SINON SI une des 4 extrémités n'existe pas
        -> KO

    SINON
        -> OK

POUR chaque couple de tables, SUR LE GRAPHE ORIENTÉ one -> many

    SI plus d'un chemin de propagation de filtre les relie
        -> KO

    (le graphe NON orienté donnerait des faux KO sur toute constellation)

STATUT GLOBAL : KO > NA > OK, hors délégués et hors périmètre

La forme du modèle (STAR / SNOWFLAKE / GALAXY / HYBRID) est publiée
à titre informatif et ne fait basculer aucun statut.
```

---

## 13. Principe fondamental

```text
une topologie n'est pas un défaut — une référence cassée en est un
```
