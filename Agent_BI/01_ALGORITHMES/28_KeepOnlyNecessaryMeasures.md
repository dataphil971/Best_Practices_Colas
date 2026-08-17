# BP-28 — Conservation des seules mesures nécessaires (détection de doublons)

## 1. Objectif de la bonne pratique

L'objectif de cette règle est de vérifier que le modèle sémantique ne conserve pas de mesures DAX dupliquées ou quasi identiques, c'est-à-dire des mesures dont l'expression DAX, une fois normalisée (suppression des espaces superflus, mise en minuscule, comparaison structurelle des tokens), est strictement équivalente ou trivialement équivalente à une autre mesure déjà présente dans le modèle. Chaque mesure redondante augmente la surface de maintenance (une correction doit être répercutée sur toutes ses copies), dégrade la lisibilité du volet des champs et peut introduire des incohérences silencieuses si les copies divergent au fil du temps sans que personne n'en ait conscience.

Cette règle ne vise pas à juger la pertinence métier de chaque mesure individuelle (ce jugement reste du ressort du concepteur du modèle) mais à détecter mécaniquement les cas où deux ou plusieurs mesures encodent, avec un nom différent, exactement — ou quasiment — le même calcul.

La règle doit être générique et fonctionner indépendamment :

- du nom du rapport Power BI ;
- du nombre total de mesures dans le modèle ;
- de la table dans laquelle se trouvent les mesures ;
- du format d'écriture de l'expression DAX (ligne unique ou bloc encadré par des triples backticks) ;
- de l'ordre des mesures dans les fichiers TMDL.

---

## 2. Emplacement des fichiers concernés

```text
<SEMANTIC_MODEL_PATH>\definition\tables\*.tmdl
```

Exemple pour ce projet :

```text
AI_BAROMETER_BI-CDS.SemanticModel\definition\tables\MEASURE.tmdl
```

Dans ce projet, la quasi-totalité des mesures est centralisée dans `MEASURE.tmdl` (cf. [BP-24](24_GroupMeasures.md)), mais l'agent ne doit pas présupposer cette centralisation : il doit parcourir tous les fichiers `tables\*.tmdl`, une mesure pouvant en théorie se trouver dans n'importe quelle table.

---

## 3. Élément(s) / propriété(s) à contrôler

L'élément décisif est l'expression DAX complète de chaque mesure, quel que soit son format d'écriture.

Exemple de deux mesures présentant une structure très proche (même patron de calcul, colonnes de filtre différentes), observées dans le modèle réel :

```tmdl
measure pct_Worry_Level_On_ALL = ```
        VAR Total_Nb_Responses =
            CALCULATE(
                [Nb_Responses],
                ALL( F_RESPONSES[WORRY_LEVEL], F_RESPONSES[WORRY_LEGEND] )
            )
        RETURN
            DIVIDE( [Nb_Responses], Total_Nb_Responses )
        ```
    displayFolder: PERCEPTION
```

```tmdl
measure pct_Interest_Level_On_ALL = ```
        VAR Total_Nb_Responses =
            CALCULATE(
                [Nb_Responses],
                ALL( F_RESPONSES[INTEREST_LEVEL], F_RESPONSES[INTEREST_LEGEND_ORDER] )
            )
        RETURN
            DIVIDE( [Nb_Responses], Total_Nb_Responses )
        ```
    displayFolder: PERCEPTION
```

Ces deux mesures partagent une structure DAX identique (même patron `CALCULATE( [Nb_Responses], ALL(...) )` suivi d'un `DIVIDE`) mais portent sur des colonnes différentes (`WORRY_*` vs `INTEREST_*`) : il ne s'agit **pas** d'un doublon, mais d'un patron répétitif légitime, pertinent pour [BP-34](34_CalculationGroups.md) (candidat à un groupe de calcul), pas pour BP-28. La distinction entre « structure similaire avec paramètres différents » et « expression strictement équivalente » est essentielle pour ne pas produire de faux positifs.

Exemple de doublon réel (cas à détecter) — deux mesures hypothétiques encodant exactement le même calcul sous des noms différents :

```tmdl
measure Total_Respondents = COUNT(F_RESPONSES[CAMPAIGN_USER_LOGIN])
```

```tmdl
measure Nb_Reponses_Total = COUNT ( F_RESPONSES[CAMPAIGN_USER_LOGIN] )
```

Après normalisation (suppression des espaces, mise en minuscule), les deux expressions deviennent strictement identiques : `count(f_responses[campaign_user_login])`.

---

## 4. Règle(s) d'évaluation

| Situation détectée | Statut | Interprétation |
|---|---|---|
| Deux mesures ou plus ont une expression DAX strictement identique après normalisation (espaces, casse) | `KO` | Doublon exact, candidat direct à suppression/fusion. |
| Deux mesures ont une expression DAX structurellement identique (même arbre de tokens/fonctions) mais référencent des colonnes ou constantes différentes | `NA` | Similarité de patron, hors périmètre de BP-28 (à examiner plutôt sous l'angle BP-34, groupes de calcul). |
| Une mesure référence directement une autre mesure existante sans ajouter de logique propre (ex. `measure B = [A]`) | `WARN` | Redondance fonctionnelle probable, à confirmer manuellement (alias volontaire ou oubli de suppression). |
| Toutes les mesures du modèle ont une expression DAX normalisée unique | `OK` | Aucun doublon détecté. |
| Le modèle ne contient aucune mesure | `NA` | La règle ne s'applique pas. |

---

## 5. Parcours complet du modèle

### Étape 1 — Localiser et charger
1. Lister tous les fichiers `tables\*.tmdl`.
2. Extraire toutes les mesures de toutes les tables, quel que soit leur format d'écriture.
3. Si aucune mesure n'est trouvée dans tout le modèle, retourner `NA`.

### Étape 2 — Normaliser chaque expression
Pour chaque mesure : extraire le corps DAX complet (hors propriétés `formatString`, `displayFolder`, `lineageTag`) ; retirer les commentaires `--` et `//` ; normaliser les espaces et la casse ; produire une empreinte (hash) de l'expression normalisée.

### Étape 3 — Regrouper par empreinte identique
Regrouper toutes les mesures partageant la même empreinte normalisée. Tout groupe de deux mesures ou plus constitue un doublon exact.

### Étape 4 — Détecter les alias directs
Pour chaque mesure dont le corps DAX se limite à une référence unique à une autre mesure (`[NomAutreMesure]`, éventuellement enveloppée d'une fonction triviale comme `ROUND` sans paramètre métier ajouté), signaler un cas `WARN`.

### Étape 5 — Terminer l'analyse
Parcourir la totalité des mesures avant de conclure, sans s'arrêter au premier groupe de doublons détecté. Produire la liste complète des groupes de doublons exacts, la liste des alias suspects, et le nombre total de mesures analysées.

---

## 6. Détection robuste / normalisation

- Une mesure peut être écrite sur une seule ligne ou encadrée par des triples backticks multi-lignes : dans les deux cas, l'agent doit extraire uniquement le corps de l'expression DAX, hors mots-clés `measure <nom> =` et hors propriétés qui suivent.
- Les commentaires DAX (`--` en fin de ligne, `//`, `/* ... */`) doivent être retirés avant normalisation, car deux expressions identiques avec des commentaires différents restent des doublons fonctionnels.
- Les espaces multiples, retours à la ligne et indentation ne doivent jamais influencer la comparaison : seule la séquence de tokens significatifs compte.
- La casse des noms de fonctions DAX (`Calculate` vs `CALCULATE`) et des identifiants ne doit pas influencer la comparaison, DAX n'étant pas sensible à la casse pour les mots-clés.
- La comparaison structurelle (pour détecter les patrons similaires, classés `NA` pour cette règle) doit remplacer les identifiants de colonnes et les constantes littérales par un jeton générique avant de comparer l'arbre de tokens, afin de ne pas confondre similarité de patron et duplication stricte.

```python
import re
import hashlib

def strip_dax_comments(dax_code):
    dax_code = re.sub(r"--.*", "", dax_code)
    dax_code = re.sub(r"//.*", "", dax_code)
    dax_code = re.sub(r"/\*.*?\*/", "", dax_code, flags=re.DOTALL)
    return dax_code

def normalize_dax(dax_code):
    code = strip_dax_comments(dax_code)
    code = re.sub(r"\s+", " ", code).strip().lower()
    return code

def dax_fingerprint(dax_code):
    return hashlib.sha256(normalize_dax(dax_code).encode("utf-8")).hexdigest()

def structural_fingerprint(dax_code):
    code = normalize_dax(dax_code)
    code = re.sub(r"\[[a-z0-9_ ]+\]", "[COL]", code)          # colonnes/mesures -> jeton générique
    code = re.sub(r"'[^']+'\[[a-z0-9_ ]+\]", "'TBL'[COL]", code)
    code = re.sub(r"\b\d+(\.\d+)?\b", "NUM", code)             # constantes numériques -> jeton générique
    code = re.sub(r'"[^"]*"', "STR", code)                      # constantes texte -> jeton générique
    return hashlib.sha256(code.encode("utf-8")).hexdigest()
```

---

## 7. Pseudo-code détaillé

```python
def analyze_measure_duplicates(table_files):
    all_measures = []
    for table_file in table_files:
        table = parse_tmdl_table(table_file)
        for measure in table.measures:
            all_measures.append({"table": table.name, "name": measure.name,
                                  "dax": measure.dax_expression})

    if not all_measures:
        return {"rule_status": "NA", "reason": "Aucune mesure dans le modèle"}

    exact_groups = {}
    structural_groups = {}
    for m in all_measures:
        exact_key = dax_fingerprint(m["dax"])
        exact_groups.setdefault(exact_key, []).append(m)

        structural_key = structural_fingerprint(m["dax"])
        structural_groups.setdefault(structural_key, []).append(m)

    exact_duplicates = [group for group in exact_groups.values() if len(group) > 1]
    structural_only = [
        group for key, group in structural_groups.items()
        if len(group) > 1 and dax_fingerprint(group[0]["dax"]) != dax_fingerprint(group[1]["dax"])
    ]

    alias_warnings = []
    all_measure_names = {m["name"] for m in all_measures}
    for m in all_measures:
        body = normalize_dax(m["dax"])
        referenced = extract_bracket_references(body)
        if len(referenced) == 1 and referenced[0] in all_measure_names \
                and is_trivial_wrapper(body, referenced[0]):
            alias_warnings.append({"table": m["table"], "name": m["name"],
                                    "aliased_measure": referenced[0]})

    return {
        "total_measures": len(all_measures),
        "exact_duplicates": exact_duplicates,
        "structural_similarity_groups": structural_only,
        "alias_warnings": alias_warnings,
    }
```

---

## 8. Calcul du statut global

```python
if exact_duplicates:
    rule_status = "KO"
elif alias_warnings:
    rule_status = "WARN"
else:
    rule_status = "OK"
```

Priorité des statuts : `KO > WARN > OK`. Les groupes de similarité purement structurelle (`structural_similarity_groups`) sont documentés à titre informatif mais ne dégradent jamais le statut de cette règle : ils relèvent de [BP-34](34_CalculationGroups.md).

| Résultat de l'analyse | Statut global |
|---|---|
| Aucune mesure ne partage une expression DAX normalisée avec une autre | `OK` |
| Au moins deux mesures ont une expression DAX strictement identique | `KO` |
| Aucun doublon exact, mais au moins un alias direct suspect détecté | `WARN` |
| Aucune mesure dans le modèle | `NA` |

---

## 9. Structure du résultat

Exemple `OK` :

```json
{
  "rule_id": "BP-28",
  "rule_name": "Conservation des seules mesures nécessaires",
  "execution_status": "SUCCESS",
  "rule_status": "OK",
  "total_measures": 34,
  "exact_duplicates": [],
  "structural_similarity_groups": [
    ["pct_Worry_Level_On_ALL", "pct_Interest_Level_On_ALL", "pct_Training_Level_On_ALL"]
  ],
  "alias_warnings": []
}
```

Exemple `KO` :

```json
{
  "rule_id": "BP-28",
  "rule_name": "Conservation des seules mesures nécessaires",
  "execution_status": "SUCCESS",
  "rule_status": "KO",
  "total_measures": 36,
  "exact_duplicates": [
    [
      {"table": "MEASURE", "name": "Total_Respondents"},
      {"table": "MEASURE", "name": "Nb_Reponses_Total"}
    ]
  ],
  "structural_similarity_groups": [
    ["pct_Worry_Level_On_ALL", "pct_Interest_Level_On_ALL", "pct_Training_Level_On_ALL"]
  ],
  "alias_warnings": []
}
```

---

## 10. Message présenté à l'utilisateur

### Exemple `OK`

```text
BP-28 — Conservation des seules mesures nécessaires : OK

34 mesures analysées, aucun doublon exact détecté. 3 mesures présentent une
structure de calcul similaire (pct_Worry_Level_On_ALL, pct_Interest_Level_On_ALL,
pct_Training_Level_On_ALL) mais portent sur des colonnes différentes : il ne
s'agit pas de doublons, mais d'un candidat potentiel à un groupe de calcul
(cf. BP-34).
```

### Exemple `KO`

```text
BP-28 — Conservation des seules mesures nécessaires : KO

Doublon exact détecté :
- MEASURE[Total_Respondents] et MEASURE[Nb_Reponses_Total] encodent exactement
  le même calcul : COUNT(F_RESPONSES[CAMPAIGN_USER_LOGIN]).

Correction attendue :
conserver une seule des deux mesures (le nom le plus explicite, par exemple
Total_Respondents), remplacer toutes ses références dans le rapport et dans
les autres mesures DAX par la mesure conservée, puis supprimer la mesure
redondante du modèle.
```

---

## 11. Conditions empêchant un faux OK

- tous les fichiers `tables\*.tmdl` ont été lus et toutes les mesures ont été extraites, quel que soit leur format d'écriture ;
- l'expression DAX de chaque mesure a été isolée correctement (hors propriétés `formatString`, `displayFolder`, `lineageTag`) ;
- les commentaires DAX ont été retirés avant la comparaison, pour éviter de manquer un doublon masqué par un commentaire différent ;
- la normalisation (espaces, casse) a été appliquée de façon strictement identique à toutes les mesures ;
- toutes les paires de mesures ont été comparées, pas seulement les mesures adjacentes dans le fichier ;
- la distinction entre doublon exact (`KO`) et similarité structurelle (`NA`, hors périmètre) a été appliquée avant de conclure.

---

## 12. Résumé de la règle

```text
RÈGLE BP-28

POUR chaque table du modèle sémantique
    POUR chaque mesure
        EXTRAIRE le corps DAX
        RETIRER les commentaires
        NORMALISER (espaces, casse)
        CALCULER une empreinte de l'expression normalisée
    FIN POUR
FIN POUR

REGROUPER les mesures par empreinte identique
POUR chaque groupe de 2 mesures ou plus avec la même empreinte
    SIGNALER un doublon exact
FIN POUR

POUR chaque mesure référençant uniquement une autre mesure sans logique ajoutée
    SIGNALER un alias suspect (WARN)

SI au moins un doublon exact détecté
    règle = KO
SINON SI au moins un alias suspect détecté
    règle = WARN
SINON
    règle = OK
```

---

## Annexe — Schéma de flux de l'algorithme

```text
┌────────────────────────────────────────────────────────────┐
│ DÉBUT : BP-28 — Conservation des seules mesures nécessaires   │
│         (détection de doublons)                               │
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
   ┌────────────────────────────────────────────────┐
   │ POUR chaque mesure                                │
   │  EXTRAIRE le corps DAX, retirer commentaires       │
   │  NORMALISER (espaces, casse)                        │
   │  CALCULER empreinte exacte ET empreinte structurelle│
   │  (boucle sur toutes les mesures)                    │
   └───────────────────────┬─────────────────────────────┘
                           ▼
        ┌───────────────────────────────────────────┐
        │ REGROUPER par empreinte exacte identique     │
        │ REGROUPER par empreinte structurelle          │
        └───────────────────┬─────────────────────────────┘
                            ▼
              ┌──────────────────────────────┐
              │ Groupe de 2+ mesures avec la  │
              │ même empreinte EXACTE ?        │
              └───────────────┬────────────────┘
             ┌──────────────────┴──────────────────┐
             ▼                                      ▼
       ╔═════════╗                             ┌────────────┐
       ║ OUI ❌  ║                             │ NON        │
       ╚════╤════╝                             └────────────┘
            ▼
    ┌────────────────────────┐
    │ groupe = doublon exact   │
    │ (contribue au statut KO) │
    └────────────────────────┘
                            │
                            ▼
        ┌───────────────────────────────────────────┐
        │ Groupe structurel identique mais empreintes  │
        │ exactes différentes (mêmes tokens, colonnes/  │
        │ constantes différentes) ?                     │
        └───────────────────┬─────────────────────────────┘
             ┌──────────────────┴──────────────────┐
             ▼                                      ▼
       ╔═════════╗                             ┌────────────┐
       ║ OUI     ║                             │ NON        │
       ╚════╤════╝                             └────────────┘
            ▼
    ┌────────────────────────────┐
    │ groupe = NA (informatif,     │
    │ hors périmètre BP-28,        │
    │ cf. BP-34)                   │
    └────────────────────────────┘
                            │
                            ▼
        ┌───────────────────────────────────────────┐
        │ Mesure référençant uniquement une autre       │
        │ mesure sans logique ajoutée ([Autre]) ?       │
        └───────────────────┬─────────────────────────────┘
             ┌──────────────────┴──────────────────┐
             ▼                                      ▼
       ╔═════════╗                             ┌────────────┐
       ║ OUI     ║                             │ NON        │
       ╚════╤════╝                             └────────────┘
            ▼
    ┌────────────────────────┐
    │ mesure = WARN (alias      │
    │ suspect)                  │
    └────────────────────────┘
                            │
                            ▼
     ┌──────────────────────────────────────┐
     │ CALCUL DU STATUT GLOBAL                │
     │ Au moins un doublon exact ?            │
     │        -> règle = KO                    │
     │ Sinon au moins un alias suspect ?       │
     │        -> règle = WARN                  │
     │ Sinon  -> règle = OK                    │
     └────────────────────┬─────────────────────┘
                          ▼
                RETOUR rule_status
                (OK / KO / WARN / NA)
```
