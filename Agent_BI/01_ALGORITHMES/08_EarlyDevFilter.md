# BP-08 — Filtrer tôt le volume de données en phase de développement

## 1. Objectif de la bonne pratique

Pendant le développement itératif d'un modèle Power BI (conception des requêtes Power Query, ajustement des relations, écriture des premières mesures), travailler sur le volume complet de données de production ralentit chaque actualisation et chaque aperçu, ce qui pénalise la vélocité de développement. La bonne pratique consiste à introduire un **paramètre Power Query dédié au développement** — une plage de dates réduite, un identifiant de campagne unique, ou un indicateur booléen `IsDevelopmentMode` — appliqué le plus tôt possible dans la chaîne de transformation (idéalement dès l'étape `Source`, avant toute jointure ou agrégation coûteuse), afin de limiter drastiquement le volume traité pendant les itérations de conception.

Ce filtre de développement n'a de valeur que s'il reste **clairement identifiable et désactivable avant la mise en production** : un paramètre orphelin, câblé en dur dans le code M sans passer par un paramètre nommé, ou un paramètre resté actif dans le mode de production, produit l'effet inverse de celui recherché — un modèle de production tronqué silencieusement. L'objectif de cette règle est donc double : vérifier la présence d'un mécanisme de filtrage de développement identifiable, **et** vérifier qu'il est neutralisé (désactivé ou non appliqué) dans l'état actuel du modèle avant chargement en production.

La règle doit être générique et fonctionner indépendamment :

- du nom du rapport Power BI ;
- du nom exact donné au paramètre de développement (`dev_sample`, `DateRangeParam`, `IsDevelopmentMode`, `SAMPLE_MODE`...) ;
- du connecteur de données utilisé ;
- du nombre de requêtes du modèle ;
- de l'ordre des étapes dans le code M.

---

## 2. Emplacement des fichiers concernés

```text
<SEMANTIC_MODEL_PATH>\definition\expressions.tmdl
<SEMANTIC_MODEL_PATH>\definition\tables\*.tmdl
```

Exemple pour ce projet :

```text
AI_BAROMETER_BI-CDS.SemanticModel\definition\expressions.tmdl
AI_BAROMETER_BI-CDS.SemanticModel\definition\tables\
```

L'agent doit charger :

1. `expressions.tmdl`, où sont déclarés les paramètres Power Query marqués `meta [IsParameterQuery=true, ...]` (cf. les paramètres réels du projet : `SPARK_Hostname`, `SPARK_HTTP_Path`, `ReferentialEnvironment`) ;
2. tous les fichiers `tables/*.tmdl`, pour vérifier si un paramètre candidat au filtrage de développement est effectivement **appliqué** dans une étape de filtrage (`Table.SelectRows`) proche de la source, dans une des partitions.

---

## 3. Élément(s) / propriété(s) à contrôler

Un paramètre Power Query se déclare avec la métadonnée `IsParameterQuery=true` :

```tmdl
expression ReferentialEnvironment = "onecolasdata" meta [IsParameterQuery=true, List={"onecolasdata", "onecolasdatarec", "onecolasdatadev"}, DefaultValue="onecolasdata", Type="Text", IsParameterQueryRequired=false]
	lineageTag: a20ed422-7209-4865-b531-96ae939904e1
	queryGroup: PARAMETERS
```

Un paramètre de filtrage de développement candidat suit le même schéma mais son nom, sa liste de valeurs ou son usage renvoient explicitement à une notion de développement/échantillon :

```tmdl
expression IsDevelopmentMode = false meta [IsParameterQuery=true, Type="Logical", DefaultValue=false, IsParameterQueryRequired=false]
	lineageTag: <guid>
	queryGroup: PARAMETERS

expression DateRangeParam = #date(2024, 1, 1) meta [IsParameterQuery=true, Type="Date", DefaultValue=#date(2024,1,1), IsParameterQueryRequired=false]
	lineageTag: <guid>
	queryGroup: PARAMETERS
```

L'application effective du paramètre se recherche dans les étapes M des partitions ou des expressions, sous une forme telle que :

```text
#"Filtered Dev Sample" = Table.SelectRows(Source, each [DATE] >= DateRangeParam)
#"Filtered Dev Sample" = if IsDevelopmentMode then Table.FirstN(Source, 500) else Source
```

---

## 4. Règle(s) d'évaluation

| Situation détectée | Statut | Interprétation |
|---|---|---|
| Aucun paramètre `IsParameterQuery=true` dont le nom, le type ou l'usage évoque le développement (`dev`, `sample`, `test`, `daterange`, `IsDevelopmentMode`) | `WARN` | Aucun mécanisme de filtrage de développement identifiable ; recommandation d'en ajouter un, non bloquant. |
| Paramètre `IsDevelopmentMode` présent, appliqué via `Table.SelectRows`/`Table.FirstN` proche de la source, valeur par défaut (`DefaultValue`) à `false` | `OK` | Mécanisme présent, correctement neutralisé pour la production. |
| Paramètre `IsDevelopmentMode` présent, appliqué, mais `DefaultValue` à `true` dans l'état actuel du fichier | `KO` | Le filtre de développement est actif : le modèle chargé en production serait tronqué. |
| Paramètre `dev_sample` déclaré dans `expressions.tmdl` mais jamais référencé dans une étape M d'une table ou d'une autre expression | `WARN` | Paramètre orphelin : déclaré mais sans effet, ne remplit pas son rôle. |
| Paramètre de filtrage appliqué tardivement (après des jointures lourdes déjà réalisées sur le volume complet) | `WARN` | Le filtrage existe mais n'apporte pas le gain de performance attendu en développement. |
| `ReferentialEnvironment` (paramètre réel du projet, liste `onecolasdata`/`onecolasdatarec`/`onecolasdatadev`) | `NA` | Paramètre d'environnement de données (production/recette/dev), pas un filtre de volume — hors périmètre de cette règle précise. |

---

## 5. Parcours complet du modèle

### Étape 1 — Localiser et charger
1. Charger `expressions.tmdl` et tous les fichiers `tables/*.tmdl`.
2. Extraire tous les paramètres `IsParameterQuery=true`.
3. Si `expressions.tmdl` est introuvable, chercher les paramètres directement au sein des partitions (certains projets ne centralisent pas les expressions partagées) avant de conclure à leur absence.

### Étape 2 — Identifier les paramètres candidats au filtrage de développement
Appliquer une correspondance de nom/type/valeurs par défaut (section 6) pour distinguer les paramètres de volume/échantillonnage des paramètres de configuration technique (environnement, hôte, chemin).

### Étape 3 — Vérifier l'application effective du paramètre
Pour chaque paramètre candidat : rechercher son identifiant dans le corps M de toutes les partitions et expressions ; localiser l'étape qui l'utilise ; évaluer sa position dans la chaîne (proche de la source = conforme à l'esprit de la règle).

### Étape 4 — Vérifier l'état de neutralisation pour la production
Pour chaque paramètre effectivement appliqué : lire sa `DefaultValue` (ou la valeur active si un mécanisme de bascule production/développement existe) et vérifier qu'elle correspond à un état non filtrant (`false`, plage complète, valeur `"prod"`).

### Étape 5 — Ne pas s'arrêter au premier paramètre trouvé
L'agent recense tous les paramètres candidats du modèle et évalue chacun individuellement, même si un premier paramètre conforme a déjà été identifié.

### Étape 6 — Terminer l'analyse
Produire : la liste des paramètres candidats détectés avec leur statut ; si aucun paramètre candidat n'existe, un statut `WARN` explicite recommandant d'en introduire un ; le détail de l'application (requêtes concernées, position dans la chaîne).

---

## 6. Détection robuste / normalisation

**Reconnaissance d'un paramètre candidat au filtrage de développement** — l'agent combine plusieurs signaux, car le nom exact varie d'un projet à l'autre :

```python
DEV_FILTER_NAME_PATTERN = re.compile(r"(dev|sample|test|daterange|date_range|is_?dev)", re.I)

def is_dev_filter_candidate(expr):
    if not expr.get_meta("IsParameterQuery"):
        return False
    name_match = DEV_FILTER_NAME_PATTERN.search(expr.name)
    type_hint = expr.get_meta("Type") in {"Logical", "Date", "DateTime", "Number"}
    return bool(name_match) or (type_hint and name_match)
```

Un paramètre dont le type est `Text` avec une liste fermée de valeurs représentant des environnements de données (ex. `ReferentialEnvironment`) doit être exclu explicitement de la détection, car il répond à un besoin différent (bascule d'environnement de données, pas de volume) — l'agent le classe `NA` plutôt que `WARN`.

**Recherche de l'application effective** — l'agent doit rechercher l'identifiant du paramètre comme token entier (pas de sous-chaîne) dans le corps M de toutes les partitions et expressions du modèle :

```python
def find_usages(param_name, all_m_bodies):
    pattern = re.compile(rf"\b{re.escape(param_name)}\b")
    return [
        (query_name, step_name)
        for query_name, m_body in all_m_bodies.items()
        for step_name, step_expr in parse_steps(m_body)
        if pattern.search(step_expr)
    ]
```

**Évaluation de la position dans la chaîne** — une utilisation est considérée « proche de la source » si elle intervient dans l'une des trois premières étapes suivant `Source`, ou avant toute étape classée `HEAVY` au sens de [BP-04](04_PushTransformUpstream.md) (jointure, agrégation, pivot).

**Normalisation de la valeur booléenne/de plage par défaut** : `DefaultValue` doit être interprétée en tenant compte des variantes d'écriture M (`false`, `FALSE`, `0`) et, pour une plage de dates, comparée à une fenêtre jugée "complète" par rapport à la volumétrie attendue (une plage de dates par défaut correspondant à quelques jours seulement, alors que le modèle est censé couvrir plusieurs années, doit être traitée comme un signal d'activation involontaire).

---

## 7. Pseudo-code détaillé

```python
EXCLUDED_ENVIRONMENT_PARAMS_HINT = {"environment", "referential", "catalog", "database", "hostname", "http_path"}

def classify_parameter(expr):
    name_lower = expr.name.lower()
    if any(hint in name_lower for hint in EXCLUDED_ENVIRONMENT_PARAMS_HINT):
        return "NA"
    if is_dev_filter_candidate(expr):
        return "CANDIDATE"
    return "OTHER"


def evaluate_dev_filter_candidate(expr, all_m_bodies):
    usages = find_usages(expr.name, all_m_bodies)
    if not usages:
        return {"parameter": expr.name, "status": "WARN",
                "reason": "Paramètre déclaré mais jamais référencé dans le code M (orphelin)"}

    close_to_source = any(is_near_source(query_name, step_name, all_m_bodies) for query_name, step_name in usages)
    default_value = expr.get_meta("DefaultValue")
    is_neutralized = is_non_filtering_default(default_value, expr.get_meta("Type"))

    if not close_to_source:
        return {"parameter": expr.name, "status": "WARN", "usages": usages,
                "reason": "Filtre appliqué tardivement, après des transformations lourdes"}

    if not is_neutralized:
        return {"parameter": expr.name, "status": "KO", "usages": usages,
                "reason": f"Valeur par défaut active ({default_value}) : le modèle serait chargé filtré en production"}

    return {"parameter": expr.name, "status": "OK", "usages": usages}


all_expressions = parse_expressions(expressions_file) if expressions_file_exists else []
all_m_bodies = collect_all_m_bodies(table_files, expressions_file)

classified = {expr.name: classify_parameter(expr) for expr in all_expressions}
candidates = [expr for expr in all_expressions if classified[expr.name] == "CANDIDATE"]

if not candidates:
    rule_result = {"rule_status": "WARN",
                    "reason": "Aucun paramètre de filtrage de développement identifiable dans le modèle"}
else:
    evaluations = [evaluate_dev_filter_candidate(expr, all_m_bodies) for expr in candidates]
```

---

## 8. Calcul du statut global

```python
if any(e["status"] == "KO" for e in evaluations):
    rule_status = "KO"
elif not candidates or any(e["status"] == "WARN" for e in evaluations):
    rule_status = "WARN"
else:
    rule_status = "OK"
```

Priorité des statuts : `KO > WARN > OK`. Cette règle n'utilise pas `NA` comme statut global (les paramètres hors périmètre, comme `ReferentialEnvironment`, sont exclus du calcul sans faire basculer le résultat) : soit un filtre de développement actif par erreur est détecté (`KO`), soit aucun mécanisme fiable n'est en place ou son usage est perfectible (`WARN`), soit un mécanisme correct et neutralisé est en place (`OK`).

| Résultat de l'analyse | Statut global |
|---|---|
| Paramètre de développement présent, appliqué tôt, neutralisé (`DefaultValue` non filtrant) | `OK` |
| Paramètre de développement présent mais actif par défaut dans l'état du fichier | `KO` |
| Aucun paramètre candidat identifiable | `WARN` |
| Paramètre déclaré mais jamais utilisé, ou utilisé trop tard dans la chaîne | `WARN` |

---

## 9. Structure du résultat

Exemple avec mécanisme correctement en place et neutralisé :

```json
{
  "rule_id": "BP-08",
  "rule_name": "Filtrer tôt le volume de données en phase de développement",
  "execution_status": "SUCCESS",
  "rule_status": "OK",
  "candidates_found": 1,
  "ok_details": [
    {"parameter": "IsDevelopmentMode", "usages": [["SOURCE", "Filtered Dev Sample"]], "default_value": false}
  ],
  "ko_details": [],
  "warn_details": []
}
```

Exemple représentatif de l'état actuel du projet audité, où aucun paramètre de ce type n'existe (seuls des paramètres de configuration technique sont présents : `SPARK_Hostname`, `SPARK_HTTP_Path`, `ReferentialEnvironment`) :

```json
{
  "rule_id": "BP-08",
  "rule_name": "Filtrer tôt le volume de données en phase de développement",
  "execution_status": "SUCCESS",
  "rule_status": "WARN",
  "candidates_found": 0,
  "excluded_technical_parameters": ["SPARK_Hostname", "SPARK_HTTP_Path", "ReferentialEnvironment"],
  "reason": "Aucun paramètre de filtrage de développement (échantillonnage, plage de dates réduite, mode développement) identifié dans expressions.tmdl"
}
```

---

## 10. Message présenté à l'utilisateur

### Exemple `OK`

```text
BP-08 — Filtre précoce de développement : OK

Paramètre IsDevelopmentMode identifié dans expressions.tmdl, appliqué
dès l'étape "Filtered Dev Sample" de la requête SOURCE, avec une
valeur par défaut désactivée (false) : le modèle charge l'intégralité
des données en production, tout en offrant un mécanisme d'échantillonnage
activable pendant le développement.
```

### Exemple `WARN` (état actuel du projet audité)

```text
BP-08 — Filtre précoce de développement : WARN (recommandation)

Aucun paramètre de filtrage de développement n'a été identifié dans
AI_BAROMETER_BI-CDS.SemanticModel/definition/expressions.tmdl.

Les paramètres présents (SPARK_Hostname, SPARK_HTTP_Path,
ReferentialEnvironment) concernent la configuration technique de la
source de données, pas un filtrage de volume.

Recommandation :
introduire un paramètre Power Query dédié (ex. IsDevelopmentMode de
type Logical, valeur par défaut false) et l'appliquer via
Table.SelectRows ou Table.FirstN le plus tôt possible dans la requête
SOURCE, avant les jointures actuellement réalisées (Merged Queries),
afin d'accélérer les itérations de développement sur ce modèle.
```

---

## 11. Conditions empêchant un faux `OK`

L'agent ne doit déclarer la bonne pratique `OK` que si toutes les conditions suivantes sont réunies :

- `expressions.tmdl` (et, à défaut, les partitions des tables) ont été chargés et tous les paramètres `IsParameterQuery=true` ont été extraits ;
- au moins un paramètre candidat au filtrage de développement a été identifié avec un signal fiable (nom, type, ou usage) ;
- ce paramètre est effectivement référencé dans au moins une étape M d'une requête du modèle ;
- son utilisation intervient avant les transformations lourdes de la requête concernée ;
- sa valeur par défaut (ou l'état actif constaté) correspond à un état non filtrant, cohérent avec un chargement de production complet.

L'agent ne doit jamais produire `OK` sur la seule base de la présence d'un paramètre nommé de façon évocatrice sans avoir vérifié qu'il est réellement utilisé dans le code M, ni si sa valeur par défaut active un filtrage réduit.

---

## 12. Résumé de la règle

```text
RÈGLE BP-08

EXTRAIRE tous les paramètres IsParameterQuery=true (expressions.tmdl + partitions)
EXCLURE les paramètres de configuration technique (environnement, hôte, chemin)
IDENTIFIER les paramètres candidats au filtrage de développement (nom/type)

SI aucun candidat
    règle = WARN (aucun mécanisme identifiable)
SINON
    POUR chaque candidat
        RECHERCHER ses usages dans le code M de toutes les requêtes
        SI aucun usage
            candidat = WARN (paramètre orphelin)
        SINON SI usage tardif (après transformations lourdes)
            candidat = WARN (filtre inefficace)
        SINON SI valeur par défaut active un filtrage
            candidat = KO (risque de chargement tronqué en production)
        SINON
            candidat = OK

    SI au moins un candidat KO
        règle = KO
    SINON SI au moins un candidat WARN
        règle = WARN
    SINON
        règle = OK

AFFICHER tous les candidats avec leur statut et recommandation
```

---

## Annexe — Schéma de flux de l'algorithme

```text
┌───────────────────────────────────────────────────────────────┐
│ DÉBUT : BP-08 — Filtrer tôt le volume de données en             │
│         phase de développement                                  │
└────────────────────────┬────────────────────────────────────────┘
                          │
                          ▼
          ┌──────────────────────────────────┐
          │ Charger expressions.tmdl           │
          │ (à défaut : chercher dans les       │
          │ partitions des tables)              │
          │ EXTRAIRE tous les paramètres         │
          │ IsParameterQuery=true                │
          └──────────────┬────────────────────┘
                          ▼
          ┌──────────────────────────────────┐
          │ EXCLURE les paramètres de           │
          │ configuration technique (environment,│
          │ host, path...) → classés NA,         │
          │ hors périmètre des candidats         │
          └──────────────┬────────────────────┘
                          ▼
          ┌──────────────────────────────────┐
          │ IDENTIFIER les paramètres           │
          │ candidats au filtrage de            │
          │ développement (nom/type : dev,       │
          │ sample, test, daterange...)          │
          └──────────────┬────────────────────┘
                          │
               ┌──────────┴──────────┐
               ▼                     ▼
         ╔═════════════╗    ┌──────────────────────┐
         ║ ≥1 candidat ✅║   │ Aucun candidat trouvé ❌│
         ╚════╤════════╝    └──────────┬────────────┘
              │                        ▼
              │                ╔═══════════════════╗
              │                ║ règle = WARN        ║
              │                ║ (aucun mécanisme     ║
              │                ║  identifiable)        ║
              │                ╚═══════════════════╝
              ▼
   ┌───────────────────────────────────────────┐
   │ POUR chaque candidat (boucle)               │
   │ RECHERCHER ses usages dans le code M de      │
   │ toutes les requêtes                          │
   └──────────────────┬──────────────────────────┘
                       ▼
        ┌────────────────────────────────────┐
        │ Aucun usage trouvé (orphelin) ?      │
        └───────┬──────────────────┬───────────┘
              oui│                  │non
                 ▼                  ▼
         ╔═══════════════╗  ┌────────────────────────────┐
         ║ candidat=WARN ║  │ Usage tardif (après          │
         ╚═══════════════╝  │ transformations lourdes) ?   │
                             └───────┬──────────────┬────────┘
                                  oui│                │non
                                     ▼                ▼
                          ╔═══════════════╗  ┌────────────────────────┐
                          ║ candidat=WARN ║  │ Valeur par défaut active │
                          ╚═══════════════╝  │ un filtrage (≠ neutre) ? │
                                              └──────┬──────────┬────────┘
                                                   oui│           │non
                                                      ▼           ▼
                                           ╔═══════════════╗ ╔═══════════════╗
                                           ║ candidat = KO ║ ║ candidat = OK ║
                                           ╚═══════════════╝ ╚═══════════════╝
                       │
                       ▼ (ENREGISTRER avec preuve, boucle suivante —
                       │  tous les candidats évalués, aucun arrêt prématuré)
   ┌──────────────────────────────────────────────────┐
   │ CALCUL DU STATUT GLOBAL (priorité KO > WARN > OK) │
   │ SI au moins un candidat KO      → règle = KO      │
   │ SINON SI aucun candidat OU ≥1 WARN → règle = WARN │
   │ SINON                             → règle = OK    │
   │ (pas de statut NA au niveau global pour BP-08)     │
   └───────────────────────┬──────────────────────────┘
                            ▼
                RETOUR rule_status (OK / WARN / KO)
```
