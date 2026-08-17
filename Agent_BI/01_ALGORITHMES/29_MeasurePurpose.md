# BP-29 — Documentation systématique de l'objectif métier de chaque mesure

## 1. Objectif de la bonne pratique

L'objectif de cette règle est de vérifier que **100 % des mesures DAX** du modèle sémantique disposent d'une description (commentaire `///` immédiatement au-dessus de la définition, ou propriété `description` dans le bloc) qui explique le calcul réalisé et l'usage métier attendu de la mesure. Les mesures sont les objets les plus consommés par les utilisateurs finaux d'un rapport Power BI (elles apparaissent directement dans les visuels, les infobulles, les cartes) : une mesure non documentée oblige tout consommateur — analyste, développeur reprenant le modèle, auditeur — à relire l'intégralité de son code DAX pour en comprendre le sens, ce qui n'est pas acceptable à l'échelle d'un modèle de production.

Cette règle se distingue de [BP-26](26_AddFieldDescriptions.md), qui documente uniquement les champs (colonnes et mesures) jugés **ambigus** au cas par cas. BP-29 est plus stricte et plus large : elle exige une description sur **toutes** les mesures visibles, y compris celles dont le nom paraît explicite à première vue (ex. `Nb_Responses`), car l'objectif ici n'est pas seulement de lever une ambiguïté ponctuelle mais d'assurer une documentation exhaustive et homogène de la couche de calcul du modèle.

La règle doit être générique et fonctionner indépendamment :

- du nom du rapport Power BI ;
- du nombre total de mesures ;
- de la table dans laquelle se trouve chaque mesure ;
- du format d'écriture de l'expression DAX (ligne unique ou triple backticks) ;
- de la complexité apparente du calcul.

---

## 2. Emplacement des fichiers concernés

```text
<SEMANTIC_MODEL_PATH>\definition\tables\*.tmdl
```

Exemple pour ce projet :

```text
AI_BAROMETER_BI-CDS.SemanticModel\definition\tables\MEASURE.tmdl
```

L'agent doit parcourir tous les fichiers `tables\*.tmdl`, une mesure pouvant en théorie être définie dans n'importe quelle table du modèle, même si dans ce projet elles sont centralisées dans `MEASURE.tmdl` (cf. [BP-24](24_GroupMeasures.md)).

---

## 3. Élément(s) / propriété(s) à contrôler

Exemple de mesure **conforme**, avec description exploitable juste au-dessus de sa définition :

```tmdl
/// Ratio of responses at the current worry level against the total number of responses across all worry levels
measure pct_Worry_Level_On_ALL = ```
        VAR Total_Nb_Responses =
            CALCULATE(
                [Nb_Responses],
                ALL( F_RESPONSES[WORRY_LEVEL], F_RESPONSES[WORRY_LEGEND] )
            )
        RETURN
            DIVIDE( [Nb_Responses], Total_Nb_Responses )
        ```
    formatString: 0%;-0%;0%
    displayFolder: PERCEPTION
    lineageTag: 38006254-49a7-420a-b5fe-4a01f08a74cd
```

Exemple de mesure **non conforme**, sans aucune description, observée telle quelle dans le modèle réel :

```tmdl
measure Nb_Responses = COUNT(F_RESPONSES[CAMPAIGN_USER_LOGIN])
    formatString: 0
    displayFolder: CAMPAIGNS STATS
    lineageTag: 41157889-d0e7-4d7b-92ff-d870f629f75f
```

Bien que le nom `Nb_Responses` paraisse explicite, cette règle exige tout de même une description, car cette mesure sert de brique de base à de nombreuses autres mesures du modèle (`pct_Worry_Level_On_ALL`, `pct_Interest_Level_On_ALL`, `Response_Rate`...) : documenter précisément son périmètre exact (ex. compte-t-elle les doublons ? sur quelle granularité ?) évite des erreurs d'interprétation en cascade.

---

## 4. Règle(s) d'évaluation

| Situation détectée | Statut | Interprétation |
|---|---|---|
| Mesure avec commentaire `///` ou propriété `description` non vide et suffisamment développée | `OK` | La mesure est documentée conformément à l'exigence. |
| Mesure sans commentaire `///` ni propriété `description` | `KO` | Aucune documentation, quelle que soit l'apparente simplicité du nom. |
| Mesure avec description présente mais trop courte ou non informative (ex. `/// mesure`, `description: KPI`, `/// TODO`) | `KO` | La documentation existe formellement mais n'explique ni le calcul ni l'usage. |
| Mesure masquée (`isHidden`), utilisée uniquement comme brique technique interne (ex. construction de SVG, gestion de bannière de notification) | `WARN` | Recommandé mais non bloquant : la mesure n'est jamais exposée directement à l'utilisateur final, une description reste utile pour la maintenance mais l'absence est tolérée avec avertissement plutôt que non-conformité bloquante. |
| Le modèle ne contient aucune mesure | `NA` | La règle ne s'applique pas. |

---

## 5. Parcours complet du modèle

### Étape 1 — Localiser et charger
1. Lister tous les fichiers `tables\*.tmdl`.
2. Extraire toutes les mesures de toutes les tables.
3. Si aucune mesure n'est trouvée, retourner `NA`.

### Étape 2 — Rechercher la description de chaque mesure
Pour chaque mesure : rechercher un ou plusieurs commentaires `///` consécutifs immédiatement au-dessus de la ligne `measure <nom> =` ; à défaut, rechercher une propriété `description` dans le bloc de la mesure ; concaténer le texte trouvé si réparti sur plusieurs lignes `///`.

### Étape 3 — Évaluer la qualité de la description trouvée
Vérifier que le texte n'est pas vide, qu'il dépasse une longueur minimale significative, et qu'il ne s'agit pas d'un texte de type placeholder (`TODO`, `N/A`, simple répétition du nom de la mesure).

### Étape 4 — Distinguer mesures visibles et mesures techniques masquées
Déterminer si la mesure porte `isHidden`, afin d'appliquer la tolérance `WARN` plutôt que `KO` en cas d'absence de description sur les mesures techniques internes.

### Étape 5 — Terminer l'analyse
Parcourir la totalité des mesures du modèle sans s'arrêter à la première mesure non documentée. Produire le taux de couverture global (nombre de mesures documentées / nombre total de mesures visibles), la liste complète des mesures `KO`, et la liste des mesures `WARN`.

---

## 6. Détection robuste / normalisation

- Le commentaire `///` doit être recherché **immédiatement** au-dessus de `measure <nom> =`, en tolérant plusieurs lignes `///` consécutives (à concaténer) mais pas une ligne vide intercalée qui indiquerait que le commentaire documente un autre élément.
- Une mesure peut être écrite sur une seule ligne ou encadrée de triples backticks : la recherche du commentaire `///` précédent ne dépend pas du format de l'expression qui suit.
- La propriété `description` (moins utilisée dans ce projet que le commentaire `///`, mais syntaxiquement valide en TMDL) doit être recherchée dans l'intégralité du bloc, indépendamment de sa position par rapport aux autres propriétés (`formatString`, `displayFolder`, `lineageTag`).
- La longueur minimale significative doit être appliquée après normalisation (suppression des espaces en début/fin) pour éviter de valider une description composée uniquement d'espaces ou de ponctuation.
- La détection de `isHidden` suit la même logique que [BP-25](25_HideTechnicalFields.md) : présence de la ligne dans le bloc, indépendamment de sa position.

```python
def get_measure_description(measure, table_lines):
    triple_slash_lines = collect_consecutive_triple_slash_above(table_lines, measure.line_number)
    if triple_slash_lines:
        return " ".join(line.strip() for line in triple_slash_lines)
    return measure.get_property("description")

def is_valid_description(text, min_length=15):
    if text is None:
        return False
    normalized = text.strip()
    if len(normalized) < min_length:
        return False
    if normalized.lower() in {"todo", "tbd", "n/a", "na", "kpi", "mesure", "measure"}:
        return False
    return True
```

---

## 7. Pseudo-code détaillé

```python
def analyze_measure_purpose_documentation(table_files):
    ok_items, ko_items, warn_items = [], [], []
    total_measures = 0

    for table_file in table_files:
        table = parse_tmdl_table(table_file)
        raw_lines = read_lines(table_file)

        for measure in table.measures:
            total_measures += 1
            description = get_measure_description(measure, raw_lines)
            documented = is_valid_description(description)
            hidden = measure.has_flag("isHidden")

            if documented:
                ok_items.append({
                    "table": table.name, "name": measure.name, "status": "OK",
                })
            elif hidden:
                warn_items.append({
                    "table": table.name, "name": measure.name, "status": "WARN",
                    "reason": "Mesure technique masquée sans description (recommandé mais non bloquant)",
                })
            else:
                ko_items.append({
                    "table": table.name, "name": measure.name, "status": "KO",
                    "reason": "Aucune description exploitable (/// ou description:)",
                })

    if total_measures == 0:
        return {"rule_status": "NA", "reason": "Aucune mesure dans le modèle"}

    coverage_rate = len(ok_items) / total_measures

    return {
        "total_measures": total_measures,
        "documented": len(ok_items),
        "coverage_rate": coverage_rate,
        "ko_details": ko_items,
        "warn_details": warn_items,
    }
```

---

## 8. Calcul du statut global

```python
if ko_items:
    rule_status = "KO"
elif warn_items:
    rule_status = "WARN"
elif total_measures == 0:
    rule_status = "NA"
else:
    rule_status = "OK"
```

Priorité des statuts : `KO > WARN > NA > OK`. Contrairement à BP-26, cette règle n'admet aucune exemption `NA` pour une mesure visible individuelle : soit elle est documentée (`OK`), soit elle ne l'est pas (`KO`), à l'exception des mesures techniques masquées qui basculent en `WARN` plutôt qu'en `KO`.

| Résultat de l'analyse | Statut global |
|---|---|
| 100 % des mesures visibles sont documentées | `OK` |
| Au moins une mesure visible n'est pas documentée | `KO` |
| Aucun `KO`, mais au moins une mesure technique masquée non documentée | `WARN` |
| Aucune mesure dans le modèle | `NA` |

---

## 9. Structure du résultat

Exemple `OK` :

```json
{
  "rule_id": "BP-29",
  "rule_name": "Documentation systématique de l'objectif métier de chaque mesure",
  "execution_status": "SUCCESS",
  "rule_status": "OK",
  "total_measures": 34,
  "documented": 34,
  "coverage_rate": 1.0,
  "ko_details": [],
  "warn_details": []
}
```

Exemple `KO` :

```json
{
  "rule_id": "BP-29",
  "rule_name": "Documentation systématique de l'objectif métier de chaque mesure",
  "execution_status": "SUCCESS",
  "rule_status": "KO",
  "total_measures": 34,
  "documented": 30,
  "coverage_rate": 0.882,
  "ko_details": [
    {"table": "MEASURE", "name": "Nb_Responses", "reason": "Aucune description exploitable"},
    {"table": "MEASURE", "name": "Response_Rate", "reason": "Aucune description exploitable"},
    {"table": "MEASURE", "name": "'Dynamic Title Top'", "reason": "Aucune description exploitable"},
    {"table": "MEASURE", "name": "'Dynamic Title bottom'", "reason": "Aucune description exploitable"}
  ],
  "warn_details": []
}
```

---

## 10. Message présenté à l'utilisateur

### Exemple `OK`

```text
BP-29 — Documentation systématique de l'objectif métier de chaque mesure : OK

34 mesures analysées, 100 % disposent d'une description exploitable (via /// 
ou description:) expliquant le calcul et l'usage attendu.
```

### Exemple `KO`

```text
BP-29 — Documentation systématique de l'objectif métier de chaque mesure : KO

30 mesures documentées sur 34 (couverture 88,2 %).

Mesures non documentées :
- MEASURE[Nb_Responses] : aucune description, alors que cette mesure sert de
  brique de base à de nombreuses autres mesures du modèle.
- MEASURE[Response_Rate] : aucune description du mode de calcul du taux de
  réponse.
- MEASURE['Dynamic Title Top'] et MEASURE['Dynamic Title bottom'] : aucune
  description de la logique de construction du titre dynamique.

Correction attendue :
ajouter un commentaire /// juste avant chacune des 4 mesures listées,
expliquant précisément le calcul réalisé et le contexte d'usage attendu
(ex. : "/// Nombre total de réponses distinctes enregistrées, tous filtres
appliqués, utilisé comme dénominateur de la plupart des mesures de
pourcentage").
```

---

## 11. Conditions empêchant un faux OK

- tous les fichiers `tables\*.tmdl` ont été lus et toutes les mesures extraites ;
- pour chaque mesure, la recherche de description a couvert à la fois le commentaire `///` (avec concaténation des lignes consécutives) et la propriété `description` ;
- une description vide, trop courte ou de type placeholder n'a jamais été comptée comme conforme ;
- le statut masqué (`isHidden`) de chaque mesure a été vérifié avant d'appliquer la tolérance `WARN` ;
- 100 % des mesures visibles du modèle ont été évaluées, sans exception non justifiée ;
- le taux de couverture a été calculé sur l'ensemble des mesures et non sur un échantillon.

---

## 12. Résumé de la règle

```text
RÈGLE BP-29

POUR chaque table du modèle sémantique
    POUR chaque mesure
        RECHERCHER la description (/// consécutifs ou description:)
        SI description valide (non vide, longueur suffisante, non générique)
            mesure = OK
        SINON SI mesure masquée (isHidden)
            mesure = WARN
        SINON
            mesure = KO
        ENREGISTRER le résultat
    FIN POUR
FIN POUR

CALCULER coverage_rate = nb mesures OK / nb total de mesures

SI au moins une mesure KO
    règle = KO
SINON SI au moins une mesure WARN
    règle = WARN
SINON SI aucune mesure dans le modèle
    règle = NA
SINON
    règle = OK
```

---

## Annexe — Schéma de flux de l'algorithme

```text
┌────────────────────────────────────────────────────────────┐
│ DÉBUT : BP-29 — Documentation systématique de l'objectif      │
│         métier de chaque mesure                               │
└────────────────────────┬───────────────────────────────────────┘
                          ▼
           ┌───────────────────────────────────┐
           │ Extraire toutes les mesures de       │
           │ tables\*.tmdl                         │
           └───────────────────┬─────────────────┘
                  ┌──────────────┴──────────────┐
                  ▼                              ▼
            ╔═════════════╗                ┌───────────────┐
            ║ Mesures     ║                │ Aucune mesure  │
            ║ trouvées ✅ ║                │ dans le modèle │
            ╚══════╤═══════╝                └───────┬────────┘
                   │                                 ▼
                   │                         ┌────────────────┐
                   │                         │ Retour : NA     │
                   │                         └────────────────┘
                   ▼
   ┌────────────────────────────────────────────┐
   │ POUR chaque mesure                            │
   │ (boucle sur toutes les mesures du modèle)     │
   └───────────────────────┬─────────────────────────┘
                           ▼
        ┌───────────────────────────────────────────┐
        │ RECHERCHER description (/// consécutifs      │
        │ concaténés, ou propriété description:)        │
        └───────────────────┬─────────────────────────────┘
                            ▼
              ┌──────────────────────────────┐
              │ Description valide ? (non vide,│
              │ longueur suffisante, non        │
              │ générique/placeholder)          │
              └───────────────┬────────────────┘
             ┌──────────────────┴──────────────────┐
             ▼                                      ▼
       ╔═════════╗                             ┌────────────┐
       ║ OUI ✅  ║                             │ NON        │
       ╚════╤════╝                             └─────┬──────┘
            ▼                                         ▼
     ┌─────────────┐                       ┌────────────────────┐
     │ mesure = OK  │                       │ Mesure masquée       │
     └─────────────┘                       │ (isHidden) ?         │
                                            └──────────┬────────────┘
                                              ┌──────────┴──────────┐
                                              ▼                     ▼
                                        ╔═════════╗          ┌──────────┐
                                        ║ OUI     ║          │ NON ❌   │
                                        ╚════╤════╝          └────┬─────┘
                                             ▼                    ▼
                                     ┌───────────────┐   ┌───────────────┐
                                     │ mesure = WARN  │   │ mesure = KO    │
                                     │ (technique,     │   │ (aucune         │
                                     │  toléré)        │   │  description)   │
                                     └───────────────┘   └───────────────┘
                 │ (répéter pour toutes les mesures, calculer coverage_rate)
                 ▼
     ┌──────────────────────────────────────┐
     │ CALCUL DU STATUT GLOBAL                │
     │ Au moins une mesure KO ?               │
     │        -> règle = KO                    │
     │ Sinon au moins une mesure WARN ?        │
     │        -> règle = WARN                  │
     │ Sinon aucune mesure dans le modèle ?    │
     │        -> règle = NA                    │
     │ Sinon  -> règle = OK                    │
     └────────────────────┬─────────────────────┘
                          ▼
                RETOUR rule_status
                (OK / KO / WARN / NA)
```
