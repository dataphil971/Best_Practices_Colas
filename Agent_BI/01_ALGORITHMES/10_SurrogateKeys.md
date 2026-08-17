# BP-10 — Utiliser des clés de relation entières (surrogate keys) plutôt que textuelles

## 1. Objectif de la bonne pratique

Le moteur VertiPaq encode chaque colonne sous forme de dictionnaire de valeurs distinctes plus un vecteur d'index. Pour une colonne utilisée comme **clé de relation** (`fromColumn`/`toColumn` dans `relationships.tmdl`), le type de données de cette clé a un impact direct sur la taille du dictionnaire, la vitesse des jointures internes lors de l'évaluation des mesures, et la mémoire consommée par les structures d'index du moteur. Une clé de type entier (`int64`/`int32`) est nettement plus compacte et plus rapide à comparer qu'une clé de type texte de longueur variable, en particulier lorsque la colonne texte est longue (identifiants concaténés, logins, GUID) ou présente une cardinalité élevée.

L'objectif de cette règle est de vérifier que les colonnes utilisées comme clé de relation (des deux côtés, `from` et `to`) sont typées en entier plutôt qu'en texte, et de signaler les cas où une clé textuelle à cardinalité élevée est utilisée pour porter une relation — situation particulièrement pénalisante dans un modèle en étoile où cette colonne est parcourue à chaque évaluation de mesure filtrée par la dimension correspondante.

La règle doit être générique et fonctionner indépendamment :

- du nom du rapport Power BI ;
- du nombre de relations du modèle ;
- du nom des tables et des colonnes ;
- de la cardinalité réelle des données (le contrôle porte sur le type déclaré, la cardinalité constatée sert à prioriser la sévérité) ;
- de l'ordre des propriétés dans les fichiers TMDL.

---

## 2. Emplacement des fichiers concernés

```text
<SEMANTIC_MODEL_PATH>\definition\relationships.tmdl
<SEMANTIC_MODEL_PATH>\definition\tables\*.tmdl
```

Exemple pour ce projet :

```text
AI_BAROMETER_BI-CDS.SemanticModel\definition\relationships.tmdl
AI_BAROMETER_BI-CDS.SemanticModel\definition\tables\D_CAMPAIGNS.tmdl
AI_BAROMETER_BI-CDS.SemanticModel\definition\tables\D_USERS.tmdl
AI_BAROMETER_BI-CDS.SemanticModel\definition\tables\F_RESPONSES.tmdl
```

L'agent doit charger `relationships.tmdl` pour identifier toutes les paires de colonnes portant une relation, puis résoudre, pour chacune, le fichier de table correspondant afin de lire le `dataType` déclaré de la colonne.

---

## 3. Élément(s) / propriété(s) à contrôler

Relation réelle du modèle audité :

```tmdl
relationship AutoDetected_04792bd7-6479-4ee6-8d14-fc0d680fe50f
	fromColumn: F_RESPONSES.CAMPAIGN_ID
	toColumn: D_CAMPAIGNS.CAMPAIGN_ID
```

Définition de la colonne côté `from`, dans `F_RESPONSES.tmdl` :

```tmdl
column CAMPAIGN_ID
	dataType: string
	...
```

et côté `to`, dans `D_CAMPAIGNS.tmdl` :

```tmdl
column CAMPAIGN_ID
	dataType: string
	isHidden
	lineageTag: b30938a6-aa65-4080-bd83-dd84d12c599d
	summarizeBy: none
	sourceColumn: CAMPAIGN_ID
```

Dans les deux cas, `dataType: string` : la clé de relation `CAMPAIGN_ID` est **textuelle**, alors qu'elle ne porte qu'un rôle d'identifiant technique de jointure. C'est également le cas de `CAMPAIGN_USER_LOGIN` (`F_RESPONSES.CAMPAIGN_USER_LOGIN -> D_USERS.CAMPAIGN_USER_LOGIN`), également typée `string`.

Une clé conforme à la bonne pratique se présenterait ainsi :

```tmdl
column CAMPAIGN_SK
	dataType: int64
	isHidden
	formatString: 0
	summarizeBy: none
	sourceColumn: CAMPAIGN_SK
```

---

## 4. Règle(s) d'évaluation

| Situation détectée | Statut | Interprétation |
|---|---|---|
| `F_RESPONSES.CAMPAIGN_ID -> D_CAMPAIGNS.CAMPAIGN_ID`, `dataType: string` des deux côtés | `KO` | Clé de relation textuelle : compression et performance de jointure dégradées par rapport à une clé entière. |
| `F_RESPONSES.CAMPAIGN_USER_LOGIN -> D_USERS.CAMPAIGN_USER_LOGIN`, `dataType: string` des deux côtés | `KO` | Idem, clé métier (login) utilisée directement comme clé technique de relation. |
| `F_RESPONSES.AI_USAGE_FREQ_LEVEL -> D_USAGE_FREQUENCY_LEVELS.USAGE_FREQUENCY_LEVELS`, `dataType: string` des deux côtés | `KO` | Relation portée par un libellé textuel plutôt qu'un identifiant numérique. |
| Relation hypothétique `F_SALES.PRODUCT_SK -> D_PRODUCTS.PRODUCT_SK`, `dataType: int64` des deux côtés | `OK` | Clé de relation entière, conforme. |
| Relation impliquant une colonne dont le `dataType` diffère entre les deux côtés (ex. `string` côté `from`, `int64` côté `to`) | `KO` | Incohérence de typage en plus du non-respect de la bonne pratique ; relation potentiellement invalide ou source d'erreurs de jointure. |
| Relation impliquant une table paramètre (`P_*`) ou technique (`T_*`) | `NA` | Hors périmètre analytique prioritaire de cette règle (cohérent avec BP-01/BP-03). |
| `dataType` non déclaré ou illisible pour l'une des deux colonnes | `NA` | Impossible de conclure avec certitude. |

---

## 5. Parcours complet du modèle

### Étape 1 — Localiser et charger
1. Charger `relationships.tmdl` et extraire tous les blocs `relationship`.
2. Charger tous les fichiers `tables/*.tmdl`.
3. Si `relationships.tmdl` est introuvable, retourner `NON_EVALUE`.

### Étape 2 — Résoudre le type de chaque colonne de relation
Pour chaque relation : localiser la table et la colonne côté `from` ; localiser la table et la colonne côté `to` ; lire le `dataType` déclaré de chacune.

### Étape 3 — Exclure les tables hors périmètre
Appliquer la même heuristique de rôle que [BP-01](01_Relations.md) pour exclure les relations impliquant des tables paramètres ou techniques du calcul du statut (elles restent inventoriées en `NA`).

### Étape 4 — Appliquer la grille de décision
Comparer le `dataType` de chaque colonne aux types entiers attendus (`int64`, `int32`, `integer` selon la terminologie du connecteur source) ; signaler toute incohérence de typage entre les deux côtés d'une même relation.

### Étape 5 — Ne pas s'arrêter à la première relation non conforme
L'agent analyse l'intégralité des relations du modèle, même après une première détection `KO`.

### Étape 6 — Terminer l'analyse
Produire : le nombre total de relations analysées ; le nombre de relations `OK`/`KO`/`NA` ; la liste des relations `KO` avec le type constaté de chaque côté ; une estimation de la cardinalité de chaque clé textuelle non conforme si des statistiques de colonne sont disponibles, pour prioriser la correction.

---

## 6. Détection robuste / normalisation

**Types considérés comme entiers valides** : la terminologie TMDL utilise `int64` (le seul type entier natif du modèle tabulaire Power BI ; `int32`/`integer` peuvent apparaître dans des métadonnées source mais sont systématiquement promus en `int64` dans le modèle). L'agent doit donc reconnaître `int64` comme seule valeur strictement conforme, tout en tolérant `integer` ou `int32` comme variantes historiques équivalentes si elles apparaissent dans un export non standard.

```python
INTEGER_KEY_TYPES = {"int64", "int32", "integer"}
TEXT_KEY_TYPES = {"string", "text"}

def normalize_datatype(raw_value):
    return str(raw_value).strip().lower() if raw_value is not None else None
```

**Résolution table/colonne à partir de `fromColumn`/`toColumn`** : la syntaxe TMDL exprime la référence sous la forme `NomTable.NomColonne`, avec des guillemets simples si le nom contient des espaces ou des caractères spéciaux (`P_EVOLUTION_LEGEND_TOP.'P_LEGEND Order'`). L'agent doit séparer correctement le nom de table du nom de colonne dans tous les cas, y compris lorsque le nom de colonne contient lui-même un point (rare mais possible dans un nom entre guillemets).

```python
def parse_column_reference(ref):
    match = re.match(r"^([^.]+)\.(?:'([^']+)'|(\S+))$", ref.strip())
    table_name = match.group(1)
    column_name = match.group(2) or match.group(3)
    return table_name, column_name
```

**Cohérence de typage entre les deux côtés** : bien que Power BI autorise techniquement des types différents entre `fromColumn` et `toColumn` avec conversion implicite dans certains cas, une différence de type sur une clé de relation est en pratique le signe d'une modélisation incohérente (une des deux tables n'a pas été alignée sur la clé surrogate). L'agent doit signaler ce cas indépendamment de la conformité au type entier.

**Table de jonction et cardinalité** : si des statistiques de cardinalité de colonne sont disponibles (nombre de valeurs distinctes), l'agent peut enrichir le résultat en indiquant l'impact estimé (une clé textuelle à faible cardinalité, par exemple un code pays à deux lettres, a un impact bien moindre qu'une clé textuelle à cardinalité élevée comme un identifiant de campagne ou un login utilisateur) — mais cet enrichissement ne change jamais le statut `KO` de base, il ne fait qu'informer la priorisation.

---

## 7. Pseudo-code détaillé

```python
def resolve_column_datatype(table_name, column_name, tables_by_name):
    table = tables_by_name.get(normalize(table_name))
    if table is None:
        return None
    column = table.find_column(column_name)
    if column is None:
        return None
    return normalize_datatype(column.get_property("dataType"))


def evaluate_relationship_key_type(rel, tables_by_name, out_of_scope_tables):
    from_table, from_column = parse_column_reference(rel.from_column_ref)
    to_table, to_column = parse_column_reference(rel.to_column_ref)

    if from_table in out_of_scope_tables or to_table in out_of_scope_tables:
        return {"status": "NA", "reason": "Relation impliquant une table hors périmètre analytique"}

    from_type = resolve_column_datatype(from_table, from_column, tables_by_name)
    to_type = resolve_column_datatype(to_table, to_column, tables_by_name)

    if from_type is None or to_type is None:
        return {"status": "NA", "reason": "dataType non déclaré ou introuvable pour au moins une des colonnes"}

    if from_type != to_type:
        return {
            "status": "KO",
            "reason": f"Incohérence de typage entre les deux côtés de la relation ({from_type} / {to_type})",
            "from_type": from_type, "to_type": to_type,
        }

    if from_type in INTEGER_KEY_TYPES:
        return {"status": "OK", "from_type": from_type, "to_type": to_type}

    if from_type in TEXT_KEY_TYPES:
        return {
            "status": "KO",
            "reason": "Clé de relation textuelle : préférer une clé entière (surrogate key int64)",
            "from_type": from_type, "to_type": to_type,
        }

    return {"status": "NA", "reason": f"Type de données non couvert par la grille de décision ({from_type})"}


results = [
    {"relationship": rel.id, "from": rel.from_column_ref, "to": rel.to_column_ref,
     **evaluate_relationship_key_type(rel, tables_by_name, out_of_scope_tables)}
    for rel in relationships
]
```

---

## 8. Calcul du statut global

```python
if any(r["status"] == "KO" for r in results):
    rule_status = "KO"
elif any(r["status"] == "NA" for r in results):
    rule_status = "NA"
else:
    rule_status = "OK"
```

Priorité des statuts : `KO > NA > OK`.

| Résultat de l'analyse | Statut global |
|---|---|
| Toutes les clés de relation analysables sont typées en entier | `OK` |
| Au moins une clé de relation est typée en texte, ou incohérente entre les deux côtés | `KO` |
| Aucun `KO`, mais au moins une relation avec un type de colonne non déterminable | `NA` |
| Relations `KO` et `NA` présentes simultanément | `KO`, avec analyse partielle signalée |

---

## 9. Structure du résultat

Exemple représentatif de l'état actuel du projet audité, où toutes les clés de relation observées sont typées en texte :

```json
{
  "rule_id": "BP-10",
  "rule_name": "Utiliser des clés de relation entières (surrogate keys) plutôt que textuelles",
  "execution_status": "SUCCESS",
  "rule_status": "KO",
  "total_relationships": 8,
  "ok_relationships": 0,
  "ko_relationships": 6,
  "na_relationships": 2,
  "ko_details": [
    {"from": "F_RESPONSES.CAMPAIGN_ID", "to": "D_CAMPAIGNS.CAMPAIGN_ID", "from_type": "string", "to_type": "string"},
    {"from": "F_ADOPTION_QUESTION.CAMPAIGN_ID", "to": "D_CAMPAIGNS.CAMPAIGN_ID", "from_type": "string", "to_type": "string"},
    {"from": "F_RESPONSES.CAMPAIGN_USER_LOGIN", "to": "D_USERS.CAMPAIGN_USER_LOGIN", "from_type": "string", "to_type": "string"},
    {"from": "F_ADOPTION_QUESTION.CAMPAIGN_USER_LOGIN", "to": "D_USERS.CAMPAIGN_USER_LOGIN", "from_type": "string", "to_type": "string"},
    {"from": "F_RESPONSES.AI_USAGE_FREQ_LEVEL", "to": "D_USAGE_FREQUENCY_LEVELS.USAGE_FREQUENCY_LEVELS", "from_type": "string", "to_type": "string"}
  ],
  "na_details": [
    {"from": "P_EVOLUTION_LEGEND_TOP.'P_LEGEND Order'", "to": "D_CHOICE.'ID '", "reason": "Relation impliquant une table hors périmètre analytique"}
  ]
}
```

Exemple avec clés entières conformes :

```json
{
  "rule_id": "BP-10",
  "rule_name": "Utiliser des clés de relation entières (surrogate keys) plutôt que textuelles",
  "execution_status": "SUCCESS",
  "rule_status": "OK",
  "total_relationships": 8,
  "ok_relationships": 8,
  "ko_relationships": 0,
  "na_relationships": 0,
  "ok_details": [
    {"from": "F_RESPONSES.CAMPAIGN_SK", "to": "D_CAMPAIGNS.CAMPAIGN_SK", "from_type": "int64", "to_type": "int64"}
  ]
}
```

---

## 10. Message présenté à l'utilisateur

### Exemple `KO` (état actuel du projet audité)

```text
BP-10 — Clés de relation entières : KO

0 relation conforme sur 6 relations analysées (2 relations hors
périmètre, tables paramètres).

Relations non conformes :
- F_RESPONSES.CAMPAIGN_ID -> D_CAMPAIGNS.CAMPAIGN_ID : dataType string
- F_ADOPTION_QUESTION.CAMPAIGN_ID -> D_CAMPAIGNS.CAMPAIGN_ID : dataType string
- F_RESPONSES.CAMPAIGN_USER_LOGIN -> D_USERS.CAMPAIGN_USER_LOGIN : dataType string
- F_ADOPTION_QUESTION.CAMPAIGN_USER_LOGIN -> D_USERS.CAMPAIGN_USER_LOGIN : dataType string
- F_RESPONSES.AI_USAGE_FREQ_LEVEL -> D_USAGE_FREQUENCY_LEVELS.USAGE_FREQUENCY_LEVELS : dataType string

Correction attendue :
introduire des colonnes de clé surrogate entières (ex. CAMPAIGN_SK,
USER_SK, type int64, masquées) dans D_CAMPAIGNS et D_USERS ainsi que
dans les tables de faits correspondantes, générées en amont dans
l'ETL ou en Power Query via une table de correspondance, puis
reconstruire les relations de relationships.tmdl sur ces nouvelles
clés entières à la place des colonnes textuelles actuelles.
```

### Exemple `OK`

```text
BP-10 — Clés de relation entières : OK

8 relations analysées, toutes portées par des clés surrogate de type
int64 des deux côtés. Aucune clé de relation textuelle détectée.
```

---

## 11. Conditions empêchant un faux `OK`

L'agent ne doit déclarer la bonne pratique `OK` que si toutes les conditions suivantes sont réunies :

- `relationships.tmdl` a été localisé et intégralement parsé ;
- pour chaque relation, la table et la colonne des deux côtés (`from` et `to`) ont été résolues dans les fichiers `tables/*.tmdl` correspondants ;
- le `dataType` déclaré de chaque colonne impliquée a été lu avec succès ;
- aucune relation ne porte une clé de type texte d'un côté ou de l'autre ;
- aucune incohérence de typage n'existe entre les deux côtés d'une même relation ;
- l'intégralité des relations du fichier a été parcourue, sans limitation aux seules relations jugées prioritaires.

L'agent ne doit jamais produire `OK` en se basant uniquement sur le type déclaré d'un seul côté de la relation : les deux colonnes (`fromColumn` et `toColumn`) doivent être vérifiées.

---

## 12. Résumé de la règle

```text
RÈGLE BP-10

POUR chaque relation de relationships.tmdl
    SI la relation implique une table paramètre/technique
        relation = NA ; PASSER à la suivante

    RÉSOUDRE la colonne et le dataType côté from
    RÉSOUDRE la colonne et le dataType côté to

    SI l'un des deux dataType est introuvable
        relation = NA
    SINON SI dataType from != dataType to
        relation = KO (incohérence de typage)
    SINON SI dataType ∈ {int64, int32, integer}
        relation = OK
    SINON SI dataType ∈ {string, text}
        relation = KO (clé textuelle)
    SINON
        relation = NA

    ENREGISTRER le résultat avec preuve (type constaté des deux côtés)
FIN POUR

SI au moins une relation est KO
    règle = KO
SINON SI au moins une relation est NA
    règle = NA
SINON
    règle = OK

AFFICHER toutes les relations KO avec recommandation de clé surrogate
```

---

## Annexe — Schéma de flux de l'algorithme

```text
┌───────────────────────────────────────────────────────────────┐
│ DÉBUT : BP-10 — Clés de relation entières (surrogate keys)      │
│         plutôt que textuelles                                   │
└────────────────────────┬────────────────────────────────────────┘
                          │
                          ▼
          ┌──────────────────────────────┐
          │ Charger relationships.tmdl   │
          │ Charger tables/*.tmdl         │
          └──────────────┬────────────────┘
                          │
               ┌──────────┴──────────┐
               ▼                     ▼
         ╔═════════════╗    ┌──────────────────────┐
         ║ Trouvé ✅   ║    │ relationships.tmdl    │
         ╚════╤════════╝    │ introuvable ❌         │
              │              └──────────┬────────────┘
              │                         ▼
              │                 ┌───────────────────┐
              │                 │ Retour : NON_EVALUE│
              │                 └───────────────────┘
              ▼
   ┌───────────────────────────────────────────┐
   │ POUR chaque relation de relationships.tmdl │
   │ (boucle, jusqu'à épuisement)               │
   └──────────────────┬──────────────────────────┘
                       ▼
        ┌────────────────────────────────────┐
        │ Table from/to = PARAMETER/TECHNICAL ?│
        └───────┬──────────────────┬───────────┘
              oui│                  │non
                 ▼                  ▼
         ╔═══════════════╗  ┌────────────────────────────┐
         ║ relation = NA ║  │ RÉSOUDRE dataType côté from  │
         ╚═══════════════╝  │ RÉSOUDRE dataType côté to     │
                             └───────────────┬─────────────────┘
                                             ▼
                             ┌────────────────────────────┐
                             │ Un des deux dataType          │
                             │ introuvable/illisible ?       │
                             └───────┬──────────────┬────────┘
                                  oui│                │non
                                     ▼                ▼
                          ╔═══════════════╗  ┌────────────────────────┐
                          ║ relation = NA ║  │ dataType_from ≠           │
                          ╚═══════════════╝  │ dataType_to ?             │
                                              └──────┬──────────┬────────┘
                                                   oui│           │non
                                                      ▼           ▼
                                           ╔═══════════════╗ ┌───────────────────────┐
                                           ║ relation = KO ║ │ dataType ∈ {int64,      │
                                           ║ (incohérence   ║ │ int32, integer} ?       │
                                           ║  de typage)    ║ └──────┬──────────┬────────┘
                                           ╚═══════════════╝     oui│           │non
                                                                    ▼           ▼
                                                         ╔═══════════════╗ ┌───────────────────────┐
                                                         ║ relation = OK ║ │ dataType ∈ {string,     │
                                                         ╚═══════════════╝ │ text} ?                 │
                                                                           └──────┬──────────┬────────┘
                                                                                oui│           │non
                                                                                   ▼           ▼
                                                                        ╔═══════════════╗ ╔═══════════════╗
                                                                        ║ relation = KO ║ ║ relation = NA ║
                                                                        ║ (clé textuelle)║ ╚═══════════════╝
                                                                        ╚═══════════════╝
                       │
                       ▼ (ENREGISTRER le résultat avec le type constaté des
                       │  deux côtés, boucle suivante)
   ┌────────────────────────────────────────────────┐
   │ CALCUL DU STATUT GLOBAL (priorité KO > NA > OK) │
   │ SI au moins une relation KO    → règle = KO     │
   │ SINON SI au moins une relation NA → règle = NA  │
   │ SINON                            → règle = OK   │
   └───────────────────────┬────────────────────────┘
                            ▼
                RETOUR rule_status (OK / KO / NA)
```
