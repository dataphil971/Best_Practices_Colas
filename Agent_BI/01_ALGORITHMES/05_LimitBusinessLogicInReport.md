# BP-05 — Limiter la logique métier complexe dans les mesures DAX

## 1. Objectif

Identifier de manière reproductible les mesures DAX qui embarquent une logique métier anormalement complexe.

La règle doit rester déterministe : elle analyse uniquement des éléments observables dans l'expression DAX. Elle ne doit jamais confondre « complexité syntaxique » et « mauvaise performance prouvée ».

Statuts autorisés :

```text
OK / KO / NA
```

Un avertissement non bloquant éventuel est porté par un champ séparé `diagnostic_level`, jamais par `rule_status`.

---

## 2. Entrées

```text
<SEMANTIC_MODEL_PATH>/definition/tables/*.tmdl
```

Le moteur extrait toutes les mesures de toutes les tables.

Pour chaque mesure :

- table hôte ;
- nom ;
- corps DAX ;
- emplacement source ;
- références vers d'autres mesures.

---

## 3. Indicateurs observables

La règle utilise :

1. profondeur maximale d'imbrication de `IF`/`SWITCH` ;
2. présence de `EARLIER` / `EARLIEST` ;
3. cycle dans le graphe de dépendances entre mesures ;
4. détection d'une construction principalement visuelle (`SVG`, `data:image/...`) afin de ne pas assimiler automatiquement une construction de présentation à une règle métier.

Seuils paramétrables :

```text
NESTING_DEPTH_KO_THRESHOLD = 4
ADVANCED_FUNCTIONS_KO = {"EARLIER", "EARLIEST"}
```

---

## 4. Décision

| Situation | Statut |
|---|---|
| Expression illisible / tronquée / non parsable | `NA` |
| Cycle de dépendances entre mesures | `KO` |
| `EARLIER` ou `EARLIEST` présent | `KO` |
| profondeur >= seuil ET expression non identifiée comme construction visuelle | `KO` |
| profondeur >= seuil mais expression principalement visuelle (SVG, image dynamique) | `OK` + `diagnostic_level = WARNING` |
| profondeur < seuil, sans fonction interdite ni cycle | `OK` |

Le champ `diagnostic_level` est informatif et ne modifie jamais `rule_status`.

---

## 5. Parsing robuste de l'imbrication

Le précédent pseudo-code décrémentait la profondeur à chaque `)` alors que la pile ne contenait que `IF`/`SWITCH`, ce qui pouvait produire des profondeurs fausses.

Le moteur doit conserver une pile représentant **tous les appels de fonctions / parenthèses**, en indiquant si chaque frame correspond ou non à une fonction conditionnelle.

```python
def compute_conditional_nesting_depth(dax_body):
    tokens = tokenize_dax(
        remove_comments(dax_body),
        ignore_string_literals=True,
    )

    stack = []
    conditional_depth = 0
    max_conditional_depth = 0

    i = 0
    while i < len(tokens):
        token = tokens[i]

        # Exemple tokens : IDENT("IF"), LPAREN
        if token.kind == "IDENT" and i + 1 < len(tokens) and tokens[i + 1].kind == "LPAREN":
            function_name = token.value.upper()
            is_conditional = function_name in {"IF", "SWITCH"}

            stack.append({
                "kind": "function",
                "name": function_name,
                "is_conditional": is_conditional,
            })

            if is_conditional:
                conditional_depth += 1
                max_conditional_depth = max(
                    max_conditional_depth,
                    conditional_depth,
                )

            i += 2
            continue

        if token.kind == "LPAREN":
            stack.append({
                "kind": "group",
                "is_conditional": False,
            })
            i += 1
            continue

        if token.kind == "RPAREN":
            if not stack:
                raise DaxParseError("Parenthèse fermante sans ouverture")

            frame = stack.pop()
            if frame["is_conditional"]:
                conditional_depth -= 1

            i += 1
            continue

        i += 1

    if stack:
        raise DaxParseError("Expression DAX incomplète : parenthèse non refermée")

    return max_conditional_depth
```

Le tokenizer doit ignorer les parenthèses et noms de fonctions présents dans :

- chaînes DAX ;
- commentaires `-- ...` ;
- commentaires `/* ... */`.

---

## 6. Dépendances entre mesures

Le moteur construit le graphe des références de mesures avant l'évaluation.

```python
def has_cycle(start, graph):
    visited = set()
    active = set()

    def visit(node):
        if node in active:
            return True
        if node in visited:
            return False

        visited.add(node)
        active.add(node)

        for dep in graph.get(node, []):
            if visit(dep):
                return True

        active.remove(node)
        return False

    return visit(start)
```

Une référence non résolue ne doit pas être considérée comme un cycle : elle produit une preuve technique et, si elle empêche réellement l'analyse, `NA`.

---

## 7. Construction visuelle

```python
def looks_like_visual_construction(dax_body):
    text = dax_body.lower()
    markers = (
        "<svg",
        "<rect",
        "<text",
        "<path",
        "data:image/svg+xml",
    )
    return sum(text.count(marker) for marker in markers) >= 3
```

Cette détection n'autorise pas une exception silencieuse : elle ajoute une preuve et un diagnostic.

---

## 8. Résultat

```json
{
  "rule_id": "BP-05",
  "rule_status": "OK",
  "diagnostic_level": "WARNING",
  "measures_analyzed": 42,
  "ko_items": [],
  "na_items": [],
  "diagnostics": [
    {
      "measure": "NOTIF_Banner_Main",
      "reason": "Complexité élevée liée à une construction SVG",
      "conditional_depth": 4
    }
  ]
}
```

Priorité globale :

```text
au moins un KO -> KO
sinon au moins un NA empêchant de conclure sur une mesure dans le périmètre -> NA
sinon -> OK
```
