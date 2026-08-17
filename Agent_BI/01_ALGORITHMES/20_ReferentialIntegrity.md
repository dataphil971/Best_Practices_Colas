# BP-20 — Intégrité référentielle des relations du modèle

## 1. Objectif de la bonne pratique

Une relation Power BI relie une colonne « clé étrangère » (`fromColumn`, côté « plusieurs ») à une colonne « clé primaire » (`toColumn`, côté « un »). Lorsque des valeurs de `fromColumn` n'ont pas de correspondance dans `toColumn` (valeurs dites « orphelines »), Power BI matérialise automatiquement ces lignes dans un groupe fictif « (Blank) » lors des agrégations croisant les deux tables via cette relation — ce qui fausse silencieusement les totaux et dégrade la lisibilité des visuels pour l'utilisateur final, sans qu'aucune erreur ne soit levée.

L'objectif de cette règle est de vérifier, pour chaque relation du modèle, l'absence d'un volume significatif de valeurs orphelines côté `fromColumn`, en distinguant deux phénomènes à ne pas confondre :

- les **valeurs nulles/vides** de `fromColumn` (absence de donnée à la source, souvent acceptable et attendue selon le contexte métier) ;
- les **valeurs non nulles mais orphelines** de `fromColumn` (incohérence réelle entre les deux tables, à corriger : erreur de jointure en amont, référentiel désynchronisé, clé mal formatée...).

Point de méthode essentiel : les fichiers TMDL décrivent la **structure** des relations (`fromColumn`, `toColumn`, cardinalité, direction de filtre), mais **pas le contenu des données**. Le calcul d'un taux d'orphelins nécessite un accès aux données elles-mêmes, via l'une des méthodes suivantes, à préciser explicitement dans le rapport d'audit :

1. **Accès complet** : requête DAX exécutée via XMLA/ADOMD (`EVALUATE EXCEPT(VALUES(FactTable[FKColumn]), VALUES(DimTable[PKColumn]))`) ou requête SQL équivalente sur la source, donnant un taux d'orphelins exact ;
2. **Accès partiel (échantillonnage)** : lorsque seule une extraction partielle des données est disponible (export CSV limité, aperçu de requête Power Query, accès restreint à la source), un échantillon aléatoire des valeurs de `fromColumn` est tiré avec une graine (`seed`) fixée pour la reproductibilité, et le taux d'orphelins est estimé sur cet échantillon avec un niveau de confiance explicitement indiqué (par exemple : marge d'erreur approximative liée à la taille d'échantillon, méthode de calcul documentée).

Sans accès aux données (ni complet ni échantillonné), la règle ne peut pas être évaluée et doit retourner `NA`, jamais deviner un taux.

La règle doit être générique et fonctionner indépendamment :

- du nom du rapport Power BI ;
- du nombre de relations du modèle ;
- du sens de la relation (à sens unique ou bidirectionnel) et de sa cardinalité déclarée (un-à-plusieurs, plusieurs-à-plusieurs) ;
- de la méthode d'accès aux données effectivement disponible au moment de l'audit.

---

## 2. Emplacement des fichiers concernés

```text
<SEMANTIC_MODEL_PATH>\definition\relationships.tmdl     (liste des relations : fromColumn / toColumn)
<SEMANTIC_MODEL_PATH>\definition\tables\*.tmdl           (types de données des colonnes concernées)
```

Exemple pour ce projet — extrait réel de `relationships.tmdl` :

```tmdl
relationship dcfa4256-14b7-93c2-78fc-7761f1cee873
	fromColumn: F_RESPONSES.AI_USAGE_FREQ_LEVEL
	toColumn: D_USAGE_FREQUENCY_LEVELS.USAGE_FREQUENCY_LEVELS

relationship AutoDetected_04792bd7-6479-4ee6-8d14-fc0d680fe50f
	fromColumn: F_RESPONSES.CAMPAIGN_ID
	toColumn: D_CAMPAIGNS.CAMPAIGN_ID

relationship 042e7191-b191-d1bd-8e18-4a51c781eafd
	fromColumn: F_RESPONSES.CAMPAIGN_USER_LOGIN
	toColumn: D_USERS.CAMPAIGN_USER_LOGIN

relationship 12ca7fb2-4dee-f9cf-d271-dbdcbb0d26c7
	fromColumn: P_EVOLUTION_LEGEND_TOP.'P_LEGEND Order'
	toColumn: D_CHOICE.'ID '
```

En complément, l'agent doit recevoir un accès aux données (connexion live/XMLA, ou extrait/échantillon fourni), documenté dans le contexte d'audit.

---

## 3. Élément(s) / propriété(s) à contrôler

### 3.1 Structure d'une relation TMDL

```tmdl
relationship <ID>
	fromColumn: <TABLE_FAITS>.<COLONNE_FK>
	toColumn: <TABLE_DIMENSION>.<COLONNE_PK>
```

Des propriétés complémentaires peuvent être présentes (`crossFilteringBehavior`, `isActive`, `joinOnDateBehavior`) mais ne modifient pas le périmètre de cette règle : seules `fromColumn` et `toColumn` sont nécessaires pour identifier les deux ensembles de valeurs à comparer.

### 3.2 Requête de contrôle (accès complet)

```dax
EVALUATE
SUMMARIZECOLUMNS(
    "OrphanCount",
    CALCULATE(
        COUNTROWS(
            EXCEPT(
                VALUES('F_RESPONSES'[CAMPAIGN_USER_LOGIN]),
                VALUES('D_USERS'[CAMPAIGN_USER_LOGIN])
            )
        )
    ),
    "TotalDistinct", DISTINCTCOUNT('F_RESPONSES'[CAMPAIGN_USER_LOGIN])
)
```

### 3.3 Méthode d'échantillonnage (accès partiel)

```python
def sample_orphan_rate(from_values_sample, to_values_full_or_sample, seed):
    # from_values_sample : échantillon aléatoire (graine fixée) des valeurs non nulles de fromColumn
    # to_values_full_or_sample : idéalement l'ensemble complet des valeurs de toColumn (petite dimension),
    #                             ou un échantillon si la dimension elle-même est trop volumineuse
    orphan_values = [v for v in from_values_sample if v not in to_values_full_or_sample]
    return len(orphan_values) / len(from_values_sample) if from_values_sample else None
```

---

## 4. Règle(s) d'évaluation

| Situation détectée | Statut | Interprétation |
|---|---|---|
| Accès complet aux données, `orphan_rate = 0 %` (hors valeurs nulles) | `OK` | Intégrité référentielle totale sur cette relation. |
| Accès complet, `orphan_rate` compris entre 0 % (exclu) et le seuil (ex. 1 %) | `WARN` | Quelques orphelins résiduels, non bloquant mais à surveiller. |
| Accès complet, `orphan_rate` supérieur au seuil | `KO` | Volume significatif de valeurs orphelines : lignes « (Blank) » impactant les agrégations. |
| Accès par échantillonnage, `orphan_rate` estimé supérieur au seuil avec une taille d'échantillon jugée suffisante (ex. ≥ 384 valeurs pour une confiance de 95 % / marge ±5 %) | `KO` | Anomalie détectée avec un niveau de confiance explicite, à confirmer par un contrôle exhaustif si possible. |
| Accès par échantillonnage, taille d'échantillon insuffisante pour conclure de façon fiable | `NA` | Résultat trop incertain pour trancher ; l'agent doit signaler la taille d'échantillon minimale recommandée. |
| Aucun accès aux données (ni complet, ni échantillon) | `NA` | Règle non évaluable ; la structure de la relation seule ne permet pas de conclure. |
| `toColumn` ou `fromColumn` de type incompatible ou colonne introuvable dans le modèle (erreur de configuration de la relation) | `KO` | Anomalie structurelle détectable sans accès aux données : la relation elle-même est mal formée. |

Exemple issu des relations réelles de ce projet (accès aux données supposé disponible, seuil `KO` fixé à 1 %) :

| Relation | `fromColumn` | `toColumn` | Méthode | `orphan_rate` estimé | Statut |
|---|---|---|---|---|---|
| `AutoDetected_04792bd7...` | `F_RESPONSES.CAMPAIGN_ID` | `D_CAMPAIGNS.CAMPAIGN_ID` | Accès complet | 0 % | `OK` |
| `042e7191-...` | `F_RESPONSES.CAMPAIGN_USER_LOGIN` | `D_USERS.CAMPAIGN_USER_LOGIN` | Accès complet | 0.4 % | `WARN` |
| `12ca7fb2-...` | `P_EVOLUTION_LEGEND_TOP.'P_LEGEND Order'` | `D_CHOICE.'ID '` | Accès complet | 3.1 % | `KO` |
| `dcfa4256-...` | `F_RESPONSES.AI_USAGE_FREQ_LEVEL` | `D_USAGE_FREQUENCY_LEVELS.USAGE_FREQUENCY_LEVELS` | Aucun accès aux données fourni | — | `NA` |

---

## 5. Parcours complet du modèle

### Étape 1 — Localiser et charger
1. Lire `relationships.tmdl` et extraire toutes les relations (`fromColumn`, `toColumn`).
2. Lister les fichiers `tables\*.tmdl` pour vérifier l'existence et le type de chaque colonne référencée.
3. Déterminer la méthode d'accès aux données disponible pour cet audit (complet, échantillon, ou aucun) à partir du contexte fourni.
4. Si `relationships.tmdl` est introuvable, retourner `NON_EVALUE`.

### Étape 2 — Valider la structure de chaque relation
Pour chaque relation, vérifier que `fromColumn` et `toColumn` référencent des colonnes existantes dans les fichiers de tables ; si l'une des deux colonnes est introuvable, classer immédiatement `KO` (anomalie structurelle) sans nécessiter d'accès aux données.

### Étape 3 — Calculer ou estimer le taux d'orphelins
Pour chaque relation structurellement valide : si un accès complet est disponible, exécuter la requête de contrôle (section 3.2) ; sinon, si un échantillon est disponible, appliquer la méthode d'échantillonnage (section 3.3) et vérifier que la taille d'échantillon est suffisante ; sinon, classer `NA`.

### Étape 4 — Isoler le taux de valeurs nulles
Calculer séparément le taux de valeurs nulles/vides de `fromColumn`, à ne jamais additionner au taux d'orphelins dans le verdict, mais à signaler comme information complémentaire dans les preuves.

### Étape 5 — Ne pas s'arrêter à la première anomalie
Toutes les relations du modèle doivent être évaluées, même après un premier `KO`.

### Étape 6 — Terminer l'analyse
Produire le nombre total de relations analysées, la répartition `OK`/`WARN`/`KO`/`NA`, le détail de chaque relation `KO` et `WARN` avec le taux d'orphelins, la méthode utilisée et le niveau de confiance.

---

## 6. Détection robuste / normalisation

- Les noms de colonnes contenant des espaces ou des caractères spéciaux sont encadrés de guillemets simples en TMDL (`D_CHOICE.'ID '`, `P_EVOLUTION_LEGEND_TOP.'P_LEGEND Order'`) : l'agent doit retirer ces guillemets pour résoudre le nom réel de la colonne, **sans** supprimer les espaces internes ou finaux qui font partie du nom réel de la colonne (l'espace final de `'ID '` fait partie du nom de colonne tel que défini dans le modèle, ce n'est pas une erreur de parsing — voir aussi [BP-21](21_ConciseNames.md) qui traite ce type d'anomalie de nommage).
- La comparaison des valeurs pour détecter les orphelins doit tenir compte du type de données déclaré (`dataType`) : une comparaison texte insensible à la casse peut être pertinente pour des clés textuelles selon la configuration de la source, mais l'agent doit documenter explicitement la méthode de comparaison retenue plutôt que de l'appliquer silencieusement.
- Les valeurs nulles, vides (`""`) et les espaces purs doivent être traitées comme une seule catégorie « valeur manquante », distincte des valeurs orphelines non nulles, avec un comptage séparé.
- La taille d'échantillon minimale recommandée pour une estimation à ±5 % avec un niveau de confiance de 95 % est d'environ 384 valeurs (formule statistique standard pour une population infinie/grande) ; en deçà, le résultat doit être qualifié `NA` avec la raison explicite « échantillon insuffisant », jamais présenté comme un `OK` ou un `KO` définitif.
- Une relation peut être inactive (`isActive: false`) : elle reste soumise à cette règle si elle est utilisée par au moins une mesure via `USERELATIONSHIP`, sinon elle peut être signalée séparément comme relation dormante (information complémentaire, pas un motif de `NA` automatique).
- L'ordre des relations dans `relationships.tmdl` est arbitraire et ne doit jamais influencer le résultat.

---

## 7. Pseudo-code détaillé

```python
ORPHAN_RATE_KO_THRESHOLD = 0.01     # 1%, paramètre configurable
MIN_SAMPLE_SIZE = 384               # confiance 95% / marge ±5%, paramètre configurable

def resolve_column(table_name, column_name, model_columns):
    key = f"{table_name}.{column_name}"
    return model_columns.get(key)

def compute_orphan_rate_full_access(relationship, data_access):
    from_values = data_access.get_distinct_values(relationship.from_table, relationship.from_column)
    to_values = data_access.get_distinct_values(relationship.to_table, relationship.to_column)

    non_null_from_values = [v for v in from_values if v not in (None, "", " ")]
    null_count = len(from_values) - len(non_null_from_values)

    orphan_values = [v for v in non_null_from_values if v not in to_values]
    orphan_rate = len(orphan_values) / len(non_null_from_values) if non_null_from_values else 0

    return orphan_rate, null_count / len(from_values) if from_values else 0

def compute_orphan_rate_sample(relationship, data_access, seed):
    sample = data_access.get_sample_values(relationship.from_table, relationship.from_column,
                                            seed=seed, min_size=MIN_SAMPLE_SIZE)
    if len(sample) < MIN_SAMPLE_SIZE:
        return None, len(sample)   # échantillon insuffisant

    to_values = data_access.get_distinct_values(relationship.to_table, relationship.to_column)
    non_null_sample = [v for v in sample if v not in (None, "", " ")]
    orphan_values = [v for v in non_null_sample if v not in to_values]
    orphan_rate = len(orphan_values) / len(non_null_sample) if non_null_sample else 0
    return orphan_rate, len(sample)


ok_results, warn_results, ko_results, na_results = [], [], [], []

relationships = parse_relationships_tmdl("<SEMANTIC_MODEL_PATH>/definition/relationships.tmdl")
if relationships is None:
    return {"execution_status": "ERROR", "rule_status": "NON_EVALUE",
            "reason": "relationships.tmdl introuvable ou illisible"}

model_columns = collect_all_column_identifiers("<SEMANTIC_MODEL_PATH>/definition/tables/")
data_access = get_audit_data_access_context()   # None, "full", ou objet d'accès échantillonné

for rel in relationships:
    if resolve_column(rel.from_table, rel.from_column, model_columns) is None or \
       resolve_column(rel.to_table, rel.to_column, model_columns) is None:
        ko_results.append({"relationship": rel.id, "status": "KO",
                            "reason": "Colonne fromColumn ou toColumn introuvable dans le modèle"})
        continue

    if data_access is None:
        na_results.append({"relationship": rel.id, "status": "NA",
                            "reason": "Aucun accès aux données fourni pour cet audit"})
        continue

    if data_access.mode == "full":
        orphan_rate, null_rate = compute_orphan_rate_full_access(rel, data_access)
        method = "full_scan"
    else:
        orphan_rate, sample_size = compute_orphan_rate_sample(rel, data_access, seed=data_access.seed)
        if orphan_rate is None:
            na_results.append({"relationship": rel.id, "status": "NA",
                                "reason": f"Échantillon insuffisant ({sample_size} < {MIN_SAMPLE_SIZE})"})
            continue
        method = f"sample(n={sample_size}, seed={data_access.seed})"
        null_rate = None

    evidence = {"relationship": rel.id, "from": f"{rel.from_table}.{rel.from_column}",
                "to": f"{rel.to_table}.{rel.to_column}", "orphan_rate": round(orphan_rate, 4),
                "null_rate": null_rate, "method": method}

    if orphan_rate == 0:
        ok_results.append({**evidence, "status": "OK"})
    elif orphan_rate <= ORPHAN_RATE_KO_THRESHOLD:
        warn_results.append({**evidence, "status": "WARN"})
    else:
        ko_results.append({**evidence, "status": "KO",
                            "reason": "Taux d'orphelins au-dessus du seuil"})
```

---

## 8. Calcul du statut global

```python
if ko_results:
    rule_status = "KO"
elif warn_results:
    rule_status = "WARN"
elif na_results and not ok_results:
    rule_status = "NA"
else:
    rule_status = "OK"
```

Priorité des statuts : `KO > WARN > NA > OK`.

| Résultat de l'analyse | Statut global |
|---|---|
| Toutes les relations ont un taux d'orphelins de 0 % | `OK` |
| Au moins une relation a un taux d'orphelins résiduel non bloquant | `WARN` |
| Au moins une relation dépasse le seuil, ou présente une anomalie structurelle | `KO` |
| Aucune relation n'a pu être évaluée (absence d'accès aux données) | `NA` |

---

## 9. Structure du résultat

Exemple `OK` :

```json
{
  "rule_id": "BP-20",
  "rule_name": "Intégrité référentielle des relations du modèle",
  "execution_status": "SUCCESS",
  "rule_status": "OK",
  "orphan_rate_threshold": 0.01,
  "total_relationships": 9,
  "ok_relationships": 9,
  "warn_relationships": 0,
  "ko_relationships": 0,
  "na_relationships": 0,
  "ok_details": [
    {"relationship": "AutoDetected_04792bd7-6479-4ee6-8d14-fc0d680fe50f",
     "from": "F_RESPONSES.CAMPAIGN_ID", "to": "D_CAMPAIGNS.CAMPAIGN_ID",
     "orphan_rate": 0.0, "null_rate": 0.0, "method": "full_scan"}
  ]
}
```

Exemple `KO` :

```json
{
  "rule_id": "BP-20",
  "rule_name": "Intégrité référentielle des relations du modèle",
  "execution_status": "SUCCESS",
  "rule_status": "KO",
  "orphan_rate_threshold": 0.01,
  "total_relationships": 9,
  "ok_relationships": 6,
  "warn_relationships": 1,
  "ko_relationships": 1,
  "na_relationships": 1,
  "ko_details": [
    {
      "relationship": "12ca7fb2-4dee-f9cf-d271-dbdcbb0d26c7",
      "from": "P_EVOLUTION_LEGEND_TOP.'P_LEGEND Order'",
      "to": "D_CHOICE.'ID '",
      "orphan_rate": 0.031,
      "null_rate": 0.0,
      "method": "full_scan",
      "reason": "Taux d'orphelins au-dessus du seuil"
    }
  ]
}
```

---

## 10. Message présenté à l'utilisateur

### Exemple `OK`

```text
BP-20 — Intégrité référentielle des relations : OK

9 relations analysées par accès complet aux données : aucune ne présente
de valeur orpheline (taux d'orphelins nul sur les 9 relations).
```

### Exemple `KO`

```text
BP-20 — Intégrité référentielle des relations : KO

6 relations conformes, 1 en avertissement, 1 non conforme sur 9 relations
analysées (1 non évaluable, accès aux données non fourni).

Relation non conforme :
- P_EVOLUTION_LEGEND_TOP.'P_LEGEND Order' -> D_CHOICE.'ID ' : taux
  d'orphelins de 3.1 % (accès complet aux données). Ces valeurs génèrent
  une ligne "(Blank)" dans les visuels croisant ces deux tables.

Correction attendue :
identifier les valeurs de P_LEGEND Order absentes de D_CHOICE.'ID '
(écart potentiellement lié à l'espace final présent dans le nom de la
colonne ID, à corriger également au titre de BP-21), et compléter la
table de référence D_CHOICE ou corriger la source amont produisant ces
valeurs orphelines.
```

---

## 11. Conditions empêchant un faux OK

L'agent ne doit déclarer la bonne pratique `OK` que si toutes les conditions suivantes sont réunies :

- `relationships.tmdl` a été lu intégralement et toutes les relations ont été extraites ;
- pour chaque relation, l'existence de `fromColumn` et `toColumn` dans le modèle a été vérifiée ;
- un accès aux données (complet ou échantillonné avec une taille suffisante) a été utilisé pour **chaque** relation, jamais supposé ;
- la méthode utilisée (accès complet ou échantillonnage, avec graine et taille d'échantillon) est explicitement documentée dans le résultat ;
- le taux de valeurs nulles a été calculé séparément du taux d'orphelins, sans jamais les confondre dans le verdict ;
- aucune relation n'a été omise de l'analyse.

L'agent ne doit jamais produire `OK` en l'absence d'accès aux données, ni sur la base d'un échantillon dont la taille est inférieure au minimum statistiquement recommandé.

---

## 12. Résumé de la règle

```text
RÈGLE BP-20

LIRE relationships.tmdl → EXTRAIRE toutes les relations
DÉTERMINER la méthode d'accès aux données disponible (complet / échantillon / aucun)

POUR chaque relation

    SI fromColumn ou toColumn introuvable dans le modèle
        relation = KO (anomalie structurelle)
        CONTINUER

    SI aucun accès aux données
        relation = NA
        CONTINUER

    SI accès complet
        CALCULER orphan_rate = valeurs fromColumn non nulles absentes de toColumn / total non nulles
    SINON (échantillon)
        TIRER un échantillon (graine fixée, taille >= 384)
        SI taille insuffisante
            relation = NA
            CONTINUER
        ESTIMER orphan_rate sur l'échantillon

    CALCULER séparément null_rate (valeurs manquantes de fromColumn)

    SI orphan_rate == 0
        relation = OK
    SINON SI orphan_rate <= seuil
        relation = WARN
    SINON
        relation = KO

    ENREGISTRER le résultat avec la méthode, le taux et le niveau de confiance
FIN POUR

SI au moins une relation KO
    règle = KO
SINON SI au moins une relation WARN
    règle = WARN
SINON SI aucune relation évaluable
    règle = NA
SINON
    règle = OK

AFFICHER toutes les relations KO et WARN avec taux d'orphelins et méthode utilisée
```

---

## Annexe — Schéma de flux de l'algorithme

```text
┌──────────────────────────────────────────────────────────────────┐
│ DÉBUT : BP-20 — Intégrité référentielle des relations du modèle      │
└────────────────────────────┬───────────────────────────────────────┘
                              ▼
          ┌────────────────────────────────────────┐
          │ LIRE relationships.tmdl → EXTRAIRE          │
          │ toutes les relations (fromColumn/            │
          │ toColumn)                                     │
          │ DÉTERMINER la méthode d'accès aux             │
          │ données (complet / échantillon / aucun)       │
          └────────────────┬───────────────────────────────┘
               ┌───────────┴───────────┐
               ▼                       ▼
         ╔═════════════╗       ┌──────────────────┐
         ║ Fichier      ║       │ Introuvable ❌       │
         ║ lisible ✅   ║       └─────────┬──────────┘
         ╚══════╤═══════╝                 ▼
                │                ┌────────────────┐
                │                │ Retour :        │
                │                │ NON_EVALUE      │
                │                └────────────────┘
                ▼
     ┌──────────────────────────────────────────┐
     │ POUR chaque relation (boucle)                │
     └────────────────┬────────────────────────────┘
                      ▼
        ┌───────────────────────────────┐
        │ fromColumn et toColumn           │
        │ existent dans le modèle ?        │
        └──────────┬──────────────────────┘
             ┌──────┴──────┐
             ▼             ▼
       ╔═══════════╗  ┌──────────┐
       ║ NON = KO  ║  │ OUI         │
       ║(anomalie   ║  └────┬──────┘
       ║structurelle)         ▼
       ╚═══════════╝ ┌───────────────────────┐
                      │ Accès aux données          │
                      │ disponible ?                │
                      └──────────┬─────────────────┘
                           ┌──────┴──────┐
                           ▼             ▼
                     ┌──────────┐  ┌──────────────┐
                     │ NON = NA │  │ OUI              │
                     └──────────┘  └──────┬──────────┘
                                          ▼
                              ┌───────────────────────┐
                              │ Accès complet ou            │
                              │ échantillon ?                │
                              └──────────┬─────────────────┘
                                   ┌──────┴──────┐
                                   ▼             ▼
                        ┌──────────────────┐ ┌──────────────────────┐
                        │ COMPLET :             │ │ ÉCHANTILLON :             │
                        │ CALCULER               │ │ TIRER un échantillon      │
                        │ orphan_rate exact       │ │ (graine fixée)             │
                        └─────────┬──────────┘ └──────────┬─────────────────┘
                                  │                        ▼
                                  │             ┌───────────────────────┐
                                  │             │ taille >= 384 ?             │
                                  │             └──────────┬─────────────────┘
                                  │                  ┌──────┴──────┐
                                  │                  ▼             ▼
                                  │            ┌──────────┐  ┌──────────────┐
                                  │            │ NON = NA │  │ OUI : ESTIMER    │
                                  │            │(échantillon│ │ orphan_rate       │
                                  │            │insuffisant)│ └──────┬──────────┘
                                  │            └──────────┘         │
                                  └───────────────────┬──────────────┘
                                                      ▼
                                  ┌────────────────────────────┐
                                  │ CALCULER séparément            │
                                  │ null_rate (valeurs manquantes) │
                                  └──────────────┬────────────────┘
                                                 ▼
                                      ┌──────────┴──────────┐
                                      ▼                     ▼
                                ╔═══════════╗        ┌──────────────┐
                                ║orphan_rate║        │orphan_rate>0    │
                                ║== 0 = OK  ║        └───────┬──────────┘
                                ╚═══════════╝                ▼
                                                    ┌──────────┴──────────┐
                                                    ▼                     ▼
                                              ╔═══════════╗        ╔═══════════╗
                                              ║<= seuil    ║        ║> seuil     ║
                                              ║= WARN      ║        ║= KO        ║
                                              ╚═══════════╝        ╚═══════════╝
                                    FIN DE BOUCLE (relation suivante)
                                                      │
                                                      ▼
                    ┌────────────────────────────────────────────┐
                    │ CALCUL DU RÉSULTAT FINAL                      │
                    │ KO présent ?               → règle = KO        │
                    │ Sinon WARN présent ?       → règle = WARN       │
                    │ Sinon NA seul (aucun OK)   → règle = NA         │
                    │ Sinon                       → règle = OK        │
                    └────────────────────┬───────────────────────────┘
                                         ▼
                 RETOUR rule_status (OK/WARN/KO/NA)
```
