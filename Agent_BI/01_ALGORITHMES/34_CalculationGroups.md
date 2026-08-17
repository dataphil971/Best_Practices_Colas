# BP-34 — Opportunité de groupes de calcul (Calculation Groups)

## 1. Objectif de la bonne pratique

L'objectif de cette règle est de détecter, dans les mesures DAX du modèle sémantique, des familles de mesures répétitives partageant le même patron de calcul (même structure d'expression, seules les colonnes ou constantes référencées changent), qui pourraient être factorisées en un **groupe de calcul** (Calculation Group) : une table technique spéciale (`calculationGroup` en TMDL) dont chaque `calculationItem` applique une transformation paramétrable à une mesure de base sélectionnée dynamiquement, au lieu de dupliquer une mesure par variante. Les cas d'usage typiques sont l'intelligence temporelle (MTD, YTD, comparaison N-1) déclinée sur de nombreuses mesures de base, ou des variantes de mise en forme/filtrage répétées à l'identique sur plusieurs dimensions d'analyse.

Cette règle ne détecte pas des doublons stricts ([BP-28](28_KeepOnlyNecessaryMeasures.md) s'en charge) mais des **familles de mesures structurellement similaires** dont la prolifération pourrait être évitée par une factorisation architecturale. Elle produit une recommandation (jamais bloquante au sens strict) car un groupe de calcul est un choix de conception qui a un coût de mise en œuvre et n'est pas toujours justifié pour un nombre restreint de mesures similaires.

La règle doit être générique et fonctionner indépendamment :

- du nom du rapport Power BI ;
- du nombre total de mesures ;
- des noms de colonnes ou de tables référencés dans les mesures ;
- du nombre de mesures composant chaque famille détectée.

---

## 2. Emplacement des fichiers concernés

```text
<SEMANTIC_MODEL_PATH>\definition\tables\*.tmdl
```

Exemple pour ce projet :

```text
AI_BAROMETER_BI-CDS.SemanticModel\definition\tables\MEASURE.tmdl
```

Si le modèle contient déjà un ou plusieurs groupes de calcul, ceux-ci se trouvent dans une table dédiée portant la propriété `calculationGroup` :

```text
<SEMANTIC_MODEL_PATH>\definition\tables\<NomGroupeCalcul>.tmdl
```

---

## 3. Élément(s) / propriété(s) à contrôler

**Famille de mesures répétitives réellement observée dans le modèle audité** — sept mesures de type « pourcentage d'un niveau par rapport au total » partageant rigoureusement le même patron `CALCULATE( [Nb_Responses], ALL(...) )` puis `DIVIDE(...)`, seules les colonnes filtrées changeant :

```tmdl
measure pct_Worry_Level_On_ALL = ```
        VAR Total_Nb_Responses =
            CALCULATE( [Nb_Responses], ALL( F_RESPONSES[WORRY_LEVEL], F_RESPONSES[WORRY_LEGEND] ) )
        RETURN
            DIVIDE( [Nb_Responses], Total_Nb_Responses )
        ```

measure pct_Interest_Level_On_ALL = ```
        VAR Total_Nb_Responses =
            CALCULATE( [Nb_Responses], ALL( F_RESPONSES[INTEREST_LEVEL], F_RESPONSES[INTEREST_LEGEND_ORDER] ) )
        RETURN
            DIVIDE( [Nb_Responses], Total_Nb_Responses )
        ```

measure pct_Training_Level_On_ALL = ...        -- même patron, colonnes RECEIVED_TRAINING_*
measure pct_ResourcesVisbility_Level_On_ALL = ...  -- même patron, colonnes RESOURCES_*
measure pct_Tested_Knowledge_Level_On_ALL = ...    -- même patron, colonnes TESTED_KNOWLEDGE_*
measure pct_SelfPerceived_Knowledge_Level_On_ALL = ... -- même patron, colonnes SELFPERCEIVED_KNOWLEDGE_*
measure pct_Frequency_Level_On_ALL = ...           -- même patron (REMOVEFILTERS), colonnes AI_USAGE_FREQ_*
```

**Seconde famille détectée dans le même modèle** — sept mesures `Color_*` partageant le patron « résoudre la couleur associée au niveau actuellement sélectionné » :

```tmdl
measure Color_Worry =
        VAR CurrentLevel = SELECTEDVALUE(F_RESPONSES[WORRY_LEVEL])
        RETURN
            CALCULATE( MAX(F_RESPONSES[WORRY_COLOUR]), F_RESPONSES[WORRY_LEVEL] = CurrentLevel )

measure Color_Interest =
        VAR CurrentLevel = SELECTEDVALUE(F_RESPONSES[INTEREST_LEVEL])
        RETURN
            CALCULATE( MAX(F_RESPONSES[INTEREST_COLOUR]), F_RESPONSES[INTEREST_LEVEL] = CurrentLevel )

-- + Color_Training, Color_TestedKnowledge, Color_UsageFrequency, Color_UsageDiversity, Color_Resources
```

Ces deux familles de sept mesures chacune sont des candidates naturelles à l'examen : un groupe de calcul ne les remplacerait pas nécessairement terme à terme (les colonnes de base diffèrent par table logique), mais leur volume et leur régularité doivent au minimum déclencher une revue de conception documentée.

---

## 4. Règle(s) d'évaluation

| Situation détectée | Statut | Interprétation |
|---|---|---|
| Aucune famille de mesures structurellement similaires dépassant le seuil de répétition | `OK` | Pas de candidat identifié pour un groupe de calcul. |
| Famille de 2 ou 3 mesures partageant un même patron structurel | `NA` | Trop peu de répétitions pour justifier une recommandation (le coût de mise en place d'un groupe de calcul dépasserait le bénéfice). |
| Famille de 4 mesures ou plus partageant un même patron structurel, sans groupe de calcul existant couvrant ce patron | `WARN` | Candidat sérieux à une factorisation via Calculation Group ; recommandation non bloquante à documenter. |
| Famille de mesures similaires alors qu'un groupe de calcul existe déjà dans le modèle mais ne couvre pas ce patron | `WARN` | Occasion manquée d'étendre le groupe de calcul existant. |
| Groupe de calcul (`calculationGroup`) déjà présent et couvrant le patron détecté | `OK` | La factorisation est déjà en place. |

---

## 5. Parcours complet du modèle

### Étape 1 — Localiser et charger
1. Lister tous les fichiers `tables\*.tmdl`.
2. Identifier les tables portant la propriété `calculationGroup` (groupes de calcul déjà existants) et leurs `calculationItem`.
3. Extraire toutes les mesures « classiques » (hors table de calculation group) avec leur corps DAX.

### Étape 2 — Construire une empreinte structurelle par mesure
Pour chaque mesure, produire une empreinte structurelle identique à celle utilisée dans [BP-28](28_KeepOnlyNecessaryMeasures.md) : normaliser l'expression puis remplacer les identifiants de colonnes/mesures et les constantes littérales par des jetons génériques, en conservant la structure des fonctions et des opérateurs.

### Étape 3 — Regrouper les mesures par empreinte structurelle
Regrouper toutes les mesures partageant la même empreinte structurelle (hors mesures strictement identiques, déjà couvertes par BP-28).

### Étape 4 — Appliquer le seuil de répétition
Pour chaque groupe de 2 mesures ou plus : si la taille du groupe est ≥ 4, considérer le groupe comme candidat sérieux ; si elle est de 2 ou 3, le documenter à titre informatif sans le faire remonter comme non-conformité.

### Étape 5 — Vérifier la couverture par un groupe de calcul existant
Pour chaque groupe candidat, vérifier si un `calculationGroup` du modèle couvre déjà ce patron (par exemple si les `calculationItem` référencent dynamiquement une mesure de base via `SELECTEDMEASURE()` selon une logique équivalente).

### Étape 6 — Terminer l'analyse
Parcourir la totalité des mesures avant de conclure, sans s'arrêter au premier groupe détecté. Produire la liste complète des familles candidates avec leurs membres.

---

## 6. Détection robuste / normalisation

- L'empreinte structurelle doit être calculée sur l'expression DAX **complète** (y compris les blocs `VAR`/`RETURN`), en remplaçant systématiquement chaque référence `Table[Colonne]` ou `[Mesure]` par un jeton positionnel générique, de sorte que deux mesures suivant le même patron avec des colonnes différentes produisent la même empreinte.
- Les noms de variables locales (`Total_Nb_Responses`, `CurrentLevel`) ne doivent pas influencer l'empreinte structurelle : seule la séquence de fonctions, opérateurs et jetons génériques compte.
- Un même modèle peut contenir plusieurs familles distinctes non reliées entre elles (dans l'exemple réel : la famille `pct_*_On_ALL` et la famille `Color_*` sont deux patrons différents) : l'agent doit toutes les identifier indépendamment, pas seulement la plus grande.
- La reconnaissance d'un `calculationGroup` existant repose sur la propriété TMDL `calculationGroup` au niveau de la table, et sur la présence de blocs `calculationItem` en son sein, chacun portant sa propre expression DAX utilisant typiquement `SELECTEDMEASURE()`.
- Deux mesures peuvent avoir une structure très proche sans être de bonnes candidates à un groupe de calcul si leurs tables ou colonnes de base sont sémantiquement non interchangeables (ex. une mesure de comptage et une mesure de somme structurellement similaires par accident) : l'agent doit privilégier les familles où le nom des mesures suit lui-même un patron cohérent (préfixe/suffixe commun, ex. `pct_*_On_ALL`, `Color_*`), en complément de la similarité structurelle du DAX.

```python
def structural_fingerprint_for_calc_group(dax_code):
    code = normalize_dax(dax_code)
    code = re.sub(r"var\s+\w+", "var V", code)                 # noms de variables -> jeton
    code = re.sub(r"\[[a-z0-9_ ]+\]", "[COL]", code)            # colonnes/mesures -> jeton
    code = re.sub(r"'[^']+'\[[a-z0-9_ ]+\]", "'TBL'[COL]", code)
    code = re.sub(r'"[^"]*"', "STR", code)
    code = re.sub(r"\b\d+(\.\d+)?\b", "NUM", code)
    return code

def shares_naming_pattern(measure_names):
    prefixes = {name.split("_")[0] for name in measure_names}
    suffixes = {"_".join(name.split("_")[-2:]) for name in measure_names}
    return len(prefixes) == 1 or len(suffixes) == 1
```

---

## 7. Pseudo-code détaillé

```python
def analyze_calculation_group_opportunities(table_files):
    existing_calc_groups = []
    regular_measures = []

    for table_file in table_files:
        table = parse_tmdl_table(table_file)
        if table.has_property("calculationGroup"):
            existing_calc_groups.append(table)
            continue
        for measure in table.measures:
            regular_measures.append({
                "table": table.name, "name": measure.name,
                "dax": measure.dax_expression,
            })

    groups_by_fingerprint = {}
    for m in regular_measures:
        fp = structural_fingerprint_for_calc_group(m["dax"])
        groups_by_fingerprint.setdefault(fp, []).append(m)

    candidate_families = []
    informational_families = []

    for fp, members in groups_by_fingerprint.items():
        if len(members) < 2:
            continue

        names = [m["name"] for m in members]
        already_covered = any(
            calc_group_covers_pattern(cg, fp) for cg in existing_calc_groups
        )

        if len(members) >= 4 and not already_covered:
            candidate_families.append({
                "members": names, "size": len(members),
                "naming_pattern_consistent": shares_naming_pattern(names),
                "status": "WARN",
            })
        elif len(members) >= 2:
            informational_families.append({
                "members": names, "size": len(members), "status": "NA",
            })

    return {
        "candidate_families": candidate_families,
        "informational_families": informational_families,
        "existing_calc_groups": [cg.name for cg in existing_calc_groups],
    }
```

---

## 8. Calcul du statut global

```python
if candidate_families:
    rule_status = "WARN"
else:
    rule_status = "OK"
```

Priorité des statuts : cette règle ne produit jamais `KO` (il s'agit d'une recommandation architecturale, pas d'une non-conformité bloquante). `WARN > OK`. Les familles de 2-3 mesures (`NA`) sont documentées mais ne changent jamais le statut global.

| Résultat de l'analyse | Statut global |
|---|---|
| Aucune famille de 4 mesures ou plus au même patron structurel non couvert | `OK` |
| Au moins une famille de 4 mesures ou plus au même patron structurel, non couverte par un groupe de calcul existant | `WARN` |

---

## 9. Structure du résultat

Exemple `OK` :

```json
{
  "rule_id": "BP-34",
  "rule_name": "Opportunité de groupes de calcul",
  "execution_status": "SUCCESS",
  "rule_status": "OK",
  "candidate_families": [],
  "informational_families": []
}
```

Exemple `WARN` (état réel du projet audité) :

```json
{
  "rule_id": "BP-34",
  "rule_name": "Opportunité de groupes de calcul",
  "execution_status": "SUCCESS",
  "rule_status": "WARN",
  "candidate_families": [
    {
      "members": ["pct_Worry_Level_On_ALL", "pct_Interest_Level_On_ALL", "pct_Training_Level_On_ALL",
                  "pct_ResourcesVisbility_Level_On_ALL", "pct_Tested_Knowledge_Level_On_ALL",
                  "pct_SelfPerceived_Knowledge_Level_On_ALL", "pct_Frequency_Level_On_ALL"],
      "size": 7,
      "naming_pattern_consistent": true
    },
    {
      "members": ["Color_Worry", "Color_Interest", "Color_Training", "Color_TestedKnowledge",
                  "Color_UsageFrequency", "Color_UsageDiversity", "Color_Resources"],
      "size": 7,
      "naming_pattern_consistent": true
    }
  ],
  "informational_families": [],
  "existing_calc_groups": []
}
```

---

## 10. Message présenté à l'utilisateur

### Exemple `OK`

```text
BP-34 — Opportunité de groupes de calcul : OK

Aucune famille de 4 mesures ou plus partageant un même patron structurel n'a
été détectée. Pas de recommandation de groupe de calcul à ce stade.
```

### Exemple `WARN`

```text
BP-34 — Opportunité de groupes de calcul : recommandation (WARN)

Deux familles de mesures fortement répétitives ont été détectées :

1. 7 mesures "pct_*_On_ALL" (pct_Worry_Level_On_ALL, pct_Interest_Level_On_ALL,
   pct_Training_Level_On_ALL, pct_ResourcesVisbility_Level_On_ALL,
   pct_Tested_Knowledge_Level_On_ALL, pct_SelfPerceived_Knowledge_Level_On_ALL,
   pct_Frequency_Level_On_ALL) partagent exactement le même patron
   CALCULATE([Nb_Responses], ALL(...)) / DIVIDE(...), seules les colonnes
   filtrées changent.

2. 7 mesures "Color_*" (Color_Worry, Color_Interest, Color_Training,
   Color_TestedKnowledge, Color_UsageFrequency, Color_UsageDiversity,
   Color_Resources) partagent le même patron de résolution de couleur par
   SELECTEDVALUE + CALCULATE(MAX(...)).

Recommandation (non bloquante) :
évaluer la faisabilité d'un groupe de calcul (ou, à défaut, d'une fonction
DAX paramétrée si le modèle ne peut pas encore migrer vers les groupes de
calcul) pour factoriser chacune de ces deux familles, en documentant la
décision retenue (facteur de risque : les colonnes de base restent réparties
sur des dimensions logiques différentes, à valider avant refactorisation).
```

---

## 11. Conditions empêchant un faux OK

- tous les fichiers `tables\*.tmdl` ont été lus, y compris les éventuelles tables de groupes de calcul déjà en place ;
- l'empreinte structurelle a été calculée sur l'ensemble des mesures classiques du modèle ;
- les familles ont été regroupées par empreinte structurelle avant application du seuil de taille ;
- la couverture par un groupe de calcul existant a été vérifiée avant de classer une famille comme candidate ;
- aucune famille de 4 mesures ou plus n'a été omise de l'analyse ;
- le statut `WARN` n'a jamais été rétrogradé silencieusement en `OK` sans justification de couverture par un groupe de calcul existant.

---

## 12. Résumé de la règle

```text
RÈGLE BP-34

POUR chaque table du modèle sémantique
    SI table est un calculationGroup
        ENREGISTRER comme groupe de calcul existant
    SINON
        POUR chaque mesure
            CALCULER l'empreinte structurelle (colonnes/constantes -> jetons génériques)
        FIN POUR
FIN POUR

REGROUPER les mesures classiques par empreinte structurelle identique
POUR chaque groupe de 2 mesures ou plus
    SI taille du groupe >= 4 ET non couvert par un calculationGroup existant
        SIGNALER famille candidate (WARN)
    SINON
        SIGNALER famille informative (NA, non bloquant)
FIN POUR

SI au moins une famille candidate détectée
    règle = WARN
SINON
    règle = OK
```

---

## Annexe — Schéma de flux de l'algorithme

```text
┌──────────────────────────────────────────────────────────────────┐
│ DÉBUT : BP-34 — Opportunité de groupes de calcul (Calc Groups)    │
└────────────────────────┬───────────────────────────────────────────┘
                          │
                          ▼
          ┌────────────────────────────────────┐
          │ Lister tous les tables\*.tmdl       │
          │ du modèle sémantique                │
          └──────────────┬───────────────────────┘
                          │
                          ▼
     ┌──────────────────────────────────────────────────┐
     │ POUR chaque table                                 │
     │   SI propriété "calculationGroup" présente        │
     │     -> ENREGISTRER comme calc group existant       │
     │     -> ne pas extraire ses mesures                 │
     │   SINON                                            │
     │     -> EXTRAIRE chaque mesure classique             │
     └──────────────┬─────────────────────────────────────┘
                     │
                     ▼
     ┌──────────────────────────────────────────────────┐
     │ POUR chaque mesure classique                      │
     │   CALCULER l'empreinte structurelle                │
     │   (colonnes/constantes/variables -> jetons)        │
     └──────────────┬─────────────────────────────────────┘
                     │
                     ▼
     ┌──────────────────────────────────────────────────┐
     │ REGROUPER les mesures par empreinte identique      │
     └──────────────┬─────────────────────────────────────┘
                     │
        ┌────────────┴─────────────┐
        ▼                           ▼
 ┌───────────────┐         ┌─────────────────────┐
 │ Taille groupe  │         │ Taille groupe >= 2   │
 │ < 2 -> ignoré  │         └──────────┬────────────┘
 └───────────────┘                     │
                          ┌─────────────┴──────────────┐
                          ▼                              ▼
                 ╔═════════════════╗           ╔═════════════════════╗
                 ║ Taille 2 ou 3    ║           ║ Taille >= 4          ║
                 ║  -> NA           ║           ║ (candidat sérieux)   ║
                 ║ (informatif,     ║           ╚══════════╤═══════════╝
                 ║  non bloquant)   ║                      │
                 ╚═════════════════╝                      ▼
                                          ┌──────────────────────────────────┐
                                          │ Un calculationGroup existant       │
                                          │ couvre-t-il déjà ce patron ?       │
                                          └──────────────┬──────────────────────┘
                                             ┌─────────────┴─────────────┐
                                             ▼                           ▼
                                      ╔═════════════╗            ┌───────────────┐
                                      ║ OUI -> OK    ║            │ NON -> WARN    │
                                      ║ (déjà factor)║            │ (famille       │
                                      ╚═════════════╝            │ candidate)     │
                                                                  └───────┬────────┘
                                                                          │
                     ┌────────────────────────────────────────────────────┘
                     ▼
     ┌──────────────────────────────────────────┐
     │ CALCUL DU RÉSULTAT FINAL                  │
     │ Priorité : WARN > OK (jamais de KO)       │
     │ Au moins 1 famille candidate WARN ?       │
     └──────────────┬─────────────────────────────┘
                     │
          ┌──────────┴──────────┐
          ▼                     ▼
   ╔═════════════╗       ┌─────────────┐
   ║ OUI -> WARN ║       │ NON -> OK    │
   ╚═════════════╝       └─────────────┘
          │                     │
          └──────────┬──────────┘
                      ▼
        RETOUR rule_status (WARN / OK — jamais KO)
```
