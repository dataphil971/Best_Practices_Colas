# BP-19 — Documenter les tables et mesures des modèles réutilisables

> **Statut d'implémentation : ⏳ Non implémenté** — spécification fonctionnelle uniquement. Aucune règle exécutable dans le moteur : cette bonne pratique n'est ni contrôlée ni comptée dans un résultat d'analyse.

## 1. Objectif

Vérifier que les tables et mesures d'un modèle sémantique identifié comme **réutilisable** possèdent une description TMDL.

Cette règle est déterministe sur la **présence** de la documentation.

Elle ne doit pas utiliser une longueur minimale arbitraire pour conclure qu'une description est « métier » ou « suffisamment informative ».

Statuts :

```text
OK / KO / NA
```

La qualité rédactionnelle ou sémantique peut être analysée séparément par un reviewer contextuel.

---

## 2. Applicabilité

Le statut de modèle réutilisable doit provenir du contexte :

```text
is_reusable_semantic_model = true | false | unknown
```

Sources possibles :

- configuration d'audit ;
- politique d'entreprise ;
- métadonnée de gouvernance fournie au moteur ;
- information du service Power BI/Fabric si elle est réellement disponible.

Décision :

```text
true    -> évaluer la règle
false   -> NA hors périmètre
unknown -> NA
```

Le checker PBIP ne doit pas inventer ce statut.

---

## 3. Source

```text
<SEMANTIC_MODEL_PATH>/definition/tables/*.tmdl
```

Le parser TMDL structuré est à privilégier.

TMDL représente une description à l'aide du bloc :

```tmdl
/// Description de la table
table Sales

    /// Montant total des ventes
    measure 'Sales Amount' = SUM(...)
```

---

## 4. Périmètre des objets

Cette règle contrôle :

```text
TABLE
MEASURE
```

Les colonnes sont couvertes par une règle distincte.

Les objets générés ou techniques peuvent être exclus seulement si une politique explicite le prévoit.

---

## 5. Présence de la description

Valeurs :

```text
PRESENT
ABSENT
UNREADABLE
```

Une description est `PRESENT` si :

- la propriété TMDL est correctement parsée ;
- sa valeur n'est pas vide après normalisation des espaces.

Pseudo-code :

```python
def has_description(obj):
    if obj.description_parse_error:
        return "UNREADABLE"

    if obj.description is None:
        return "ABSENT"

    if not obj.description.strip():
        return "ABSENT"

    return "PRESENT"
```

---

## 6. Parsing TMDL

Le parser structuré doit être préféré.

Si un fallback textuel est utilisé, le bloc `///` appartient à l'objet déclaré immédiatement après.

Le fallback ne doit pas tolérer arbitrairement une ligne vide entre :

```text
/// description
```

et :

```text
table / measure
```

car cette tolérance peut attribuer une description au mauvais objet ou accepter une syntaxe non conforme.

Pseudo-code de fallback :

```python
def extract_description_fallback(
    lines,
    declaration_index,
):
    i = declaration_index - 1

    if i < 0:
        return None

    parts = []

    while i >= 0:
        raw = lines[i]
        stripped = raw.lstrip()

        if not stripped.startswith("///"):
            break

        parts.insert(
            0,
            stripped[3:].strip(),
        )
        i -= 1

    if not parts:
        return None

    return " ".join(parts)
```

---

## 7. Placeholders

Le moteur peut traiter comme absence uniquement des placeholders **explicitement configurés** :

```python
PLACEHOLDERS = context.company_policy.description_placeholders
```

Exemple :

```text
TODO
TBD
À compléter
```

Sans configuration :

```text
description présente -> PRESENT
```

La règle ne doit pas décider seule qu'une phrase courte est mauvaise.

---

## 8. Qualité sémantique

Les questions suivantes sont hors du verdict déterministe :

- la description explique-t-elle réellement le métier ?
- est-elle claire pour un utilisateur externe ?
- contient-elle le bon niveau de détail ?
- est-elle rédigée dans la bonne langue ?

Elles peuvent alimenter :

```text
diagnostic_level
context_review
```

mais ne transforment pas automatiquement `OK` en `KO`.

---

## 9. Décision

| Situation | Statut |
|---|---|
| modèle réutilisable + objet avec description présente | `OK` |
| modèle réutilisable + objet sans description | `KO` |
| placeholder explicitement configuré | `KO` |
| description illisible / parse error | `NA` |
| modèle non réutilisable | `NA` hors périmètre |
| statut de réutilisation inconnu | `NA` |

---

## 10. Pseudo-code

```python
def evaluate_documentation(
    obj,
    context,
):
    state = has_description(obj)

    if state == "UNREADABLE":
        return finding_na(
            object=obj.qualified_name,
            reason="Description non interprétable",
        )

    if state == "ABSENT":
        return finding_ko(
            object=obj.qualified_name,
            expected="description présente",
            actual=None,
        )

    normalized = obj.description.strip()

    placeholders = (
        context.company_policy
        .description_placeholders
    )

    if (
        placeholders
        and normalized.casefold()
        in {p.casefold() for p in placeholders}
    ):
        return finding_ko(
            object=obj.qualified_name,
            reason="Placeholder de description interdit",
            actual=obj.description,
        )

    return finding_ok(
        object=obj.qualified_name,
        evidence={
            "description": obj.description,
        },
    )
```

---

## 11. Statut global

```python
reusable = context.is_reusable_semantic_model

if reusable is not True:
    return rule_na(
        reason="Applicabilité du modèle réutilisable non démontrée"
    )

results = [
    evaluate_documentation(obj, context)
    for obj in semantic_model.tables_and_measures()
]

if any(r.status == "KO" for r in results):
    rule_status = "KO"

elif any(r.status == "NA" for r in results):
    rule_status = "NA"

else:
    rule_status = "OK"
```

---

## 12. Preuve obligatoire

Pour chaque objet :

```text
object_type
table
object_name
description_state
raw_description
source_file
source_location
rule_status
```

---

## 13. Références techniques

TMDL prend nativement en charge les descriptions à l'aide de la syntaxe `///` placée au-dessus des déclarations d'objets.

La documentation du modèle et la qualité rédactionnelle doivent être séparées :

```text
présence -> checker déterministe
qualité -> reviewer contextuel
```

---

## 14. Résumé

```text
RÈGLE BP-19

SI modèle réutilisable non démontré
    -> NA

POUR chaque table et mesure
    LIRE description

    SI parse impossible
        -> NA

    SI absente / vide
        -> KO

    SI placeholder explicitement interdit
        -> KO

    SINON
        -> OK
FIN
```
