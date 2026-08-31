# BP-08 — Filtrer tôt le volume de données en phase de développement

> **Statut d'implémentation : ⏳ Non implémenté** — spécification fonctionnelle uniquement. Aucune règle exécutable dans le moteur : cette bonne pratique n'est ni contrôlée ni comptée dans un résultat d'analyse.

## 1. Objectif

Évaluer, avec les preuves disponibles dans le projet, si un mécanisme de réduction de volume de données est prévu pour la phase de développement et s'il est appliqué suffisamment tôt pour éviter de traiter inutilement le volume complet.

Cette bonne pratique contient une dimension de **processus de développement** qui n'est pas toujours observable dans un PBIP de production.

Le moteur doit donc distinguer :

1. ce qui est observable statiquement dans les fichiers ;
2. ce qui nécessite une preuve de processus ou une politique d'entreprise.

Statuts autorisés :

```text
OK / KO / NA
```

Un avertissement non bloquant éventuel doit être porté par :

```text
diagnostic_level = INFO | WARNING | CRITICAL
```

et jamais par `rule_status = WARN`.

---

## 2. Sources

```text
<SEMANTIC_MODEL_PATH>/definition/expressions.tmdl
<SEMANTIC_MODEL_PATH>/definition/tables/*.tmdl
```

Le moteur consomme le `AnalysisContext` déjà construit.

Il ne relit pas le PBIP complet pour cette règle.

Informations utiles :

```text
parameters
m_queries
m_steps
query_dependencies
company_policy
process_evidence
```

---

## 3. Ce que l'agent peut réellement prouver

Le PBIP peut permettre de démontrer :

- qu'un paramètre de développement existe ;
- qu'il est utilisé ;
- qu'il est appliqué avant ou après des étapes lourdes ;
- qu'il est actuellement neutralisé ou actif ;
- qu'un filtre d'échantillonnage explicite existe.

Le PBIP ne permet pas toujours de prouver :

- que ce mécanisme a réellement été utilisé pendant toute la phase de développement ;
- qu'un développeur n'a pas utilisé un filtre temporaire ensuite supprimé ;
- qu'une stratégie externe de réduction de volume n'a pas été utilisée.

Par conséquent :

```text
absence de mécanisme observable ≠ non-conformité prouvée
```

sauf si `COMPANY_POLICY` impose explicitement que ce mécanisme reste présent dans le projet.

---

## 4. Identification des mécanismes candidats

Un mécanisme candidat peut être :

- paramètre booléen de mode développement ;
- paramètre de date ou plage de dates ;
- paramètre de nombre maximal de lignes ;
- paramètre d'échantillonnage ;
- logique M explicite activable/désactivable.

Exemples :

```m
if IsDevelopmentMode
then Table.FirstN(Source, DevRowLimit)
else Source
```

```m
if IsDevelopmentMode
then Table.SelectRows(Source, each [DATE] >= DevStartDate)
else Source
```

La détection par nom n'est qu'un indice.

```python
DEV_NAME_HINTS = (
    "dev",
    "development",
    "sample",
    "test",
    "rowlimit",
    "date_range",
)
```

Un nom contenant `dev` ne suffit pas à lui seul pour conclure qu'un paramètre contrôle le volume.

---

## 5. Validation de l'usage

Pour chaque mécanisme candidat, vérifier :

1. qu'il est réellement référencé ;
2. qu'il agit sur le volume ;
3. qu'il est appliqué avant les transformations lourdes ;
4. qu'il est neutralisé dans l'état destiné à la production.

Pseudo-code :

```python
def analyze_dev_filter(candidate, context):
    usages = resolve_parameter_usages(
        candidate,
        context.m_ast,
    )

    if not usages:
        return {
            "state": "ORPHAN",
            "evidence": [],
        }

    volume_usages = [
        usage for usage in usages
        if usage_changes_row_volume()
    ]

    if not volume_usages:
        return {
            "state": "NOT_A_VOLUME_FILTER",
            "evidence": usages,
        }

    applied_early = all(
        is_before_first_heavy_step(
            usage.query,
            usage.step,
            context.m_step_index,
        )
        for usage in volume_usages
    )

    activation = determine_current_activation(
        candidate,
        context,
    )

    return {
        "state": "VALID_FILTER",
        "applied_early": applied_early,
        "activation": activation,
        "evidence": volume_usages,
    }
```

---

## 6. État d'activation

Valeurs possibles :

```text
ACTIVE
INACTIVE
UNKNOWN
```

Le moteur ne doit pas deviner qu'une plage de dates est « complète » à partir d'une durée arbitraire.

Exemple non autorisé :

```python
is_full_range = days >= 365
```

La neutralisation doit être démontrée par :

- un booléen explicite ;
- une branche `else Source` ;
- une politique/configuration connue ;
- une valeur de paramètre dont la sémantique est explicitement définie.

Sinon :

```text
UNKNOWN
```

---

## 7. Décision

### Cas 1 — mécanisme présent, appliqué tôt et neutralisé

```text
OK
```

Preuve attendue :

```text
parameter
queries
filter_steps
position
activation = INACTIVE
```

### Cas 2 — filtre de développement explicitement actif dans l'état de production

Si le projet ou la politique indique que l'état analysé correspond à la version de production :

```text
KO
```

Le `KO` doit être fondé sur une activation réellement démontrée.

### Cas 3 — mécanisme appliqué après des transformations lourdes

Le moteur peut prouver que le filtre existe mais qu'il ne respecte pas l'objectif « filtrer tôt ».

```text
KO
```

uniquement si la bonne pratique entreprise exige explicitement un filtrage avant ces transformations.

Sinon :

```text
NA + diagnostic_level = WARNING
```

### Cas 4 — paramètre orphelin

```text
NA + diagnostic
```

Un paramètre inutilisé ne prouve pas que la pratique de développement a échoué.

### Cas 5 — aucun mécanisme identifiable

Par défaut :

```text
NA
```

avec :

```text
diagnostic_level = INFO
```

Si `COMPANY_POLICY` impose explicitement la présence permanente d'un mécanisme de filtrage de développement :

```text
KO
```

---

## 8. Matrice de décision

| Situation | Statut |
|---|---|
| filtre de développement prouvé, appliqué tôt, neutralisé | `OK` |
| filtre explicitement actif dans une version identifiée comme production | `KO` |
| filtre tardif et politique entreprise exigeant un filtre précoce | `KO` |
| filtre tardif sans politique explicite | `NA` + diagnostic |
| paramètre candidat orphelin | `NA` + diagnostic |
| aucun mécanisme observable | `NA` par défaut |
| absence de mécanisme + obligation explicite `COMPANY_POLICY` | `KO` |
| activation impossible à déterminer | `NA` |
| code M illisible | `NA` |

---

## 9. Pseudo-code

```python
def evaluate_bp08(context, company_policy):
    candidates = detect_dev_volume_filter_candidates(
        context.parameters,
        context.m_ast,
    )

    if not candidates:
        if company_policy.dev_filter_must_remain_in_project:
            return rule_ko(
                reason="Mécanisme de filtrage de développement obligatoire non détecté"
            )

        return rule_na(
            reason="Aucun mécanisme observable ; pratique de développement non démontrable",
            diagnostic_level="INFO",
        )

    results = []

    for candidate in candidates:
        analysis = analyze_dev_filter(
            candidate,
            context,
        )

        if analysis["state"] == "ORPHAN":
            results.append(
                finding_na(
                    object=candidate.name,
                    reason="Paramètre candidat non utilisé",
                    diagnostic_level="INFO",
                )
            )
            continue

        if analysis["state"] == "NOT_A_VOLUME_FILTER":
            results.append(
                finding_na(
                    object=candidate.name,
                    reason="Le paramètre ne modifie pas le volume de données",
                )
            )
            continue

        if analysis["activation"] == "UNKNOWN":
            results.append(
                finding_na(
                    object=candidate.name,
                    reason="État d'activation non déterminable",
                )
            )
            continue

        if (
            analysis["activation"] == "ACTIVE"
            and context.environment == "PRODUCTION"
        ):
            results.append(
                finding_ko(
                    object=candidate.name,
                    reason="Filtre de développement actif dans l'état de production",
                    evidence=analysis["evidence"],
                )
            )
            continue

        if not analysis["applied_early"]:
            if company_policy.dev_filter_must_be_before_heavy_steps:
                results.append(
                    finding_ko(
                        object=candidate.name,
                        reason="Filtre appliqué après des transformations lourdes",
                    )
                )
            else:
                results.append(
                    finding_na(
                        object=candidate.name,
                        reason="Filtre tardif ; exigence non explicitement bloquante",
                        diagnostic_level="WARNING",
                    )
                )
            continue

        if analysis["activation"] == "INACTIVE":
            results.append(
                finding_ok(
                    object=candidate.name,
                    evidence=analysis["evidence"],
                )
            )

    return aggregate_ok_ko_na(results)
```

---

## 10. Statut global

```text
au moins un KO -> KO
sinon au moins un élément nécessaire non démontrable -> NA
sinon -> OK
```

Un `OK` global ne peut être produit que si la conformité est réellement observable dans le périmètre configuré.

---

## 11. Preuve obligatoire

Un résultat doit conserver :

```text
rule_id
candidate
candidate_type
queries
filter_steps
position_relative_to_heavy_steps
activation
environment
company_policy
evidence
rule_status
diagnostic_level
```

Un `KO` pour filtre actif doit démontrer simultanément :

```text
filtre actif
+
version/environnement de production identifié
```

Sans cette seconde preuve :

```text
NA
```

---

## 12. Résumé

```text
RÈGLE BP-08

DÉTECTER les mécanismes de réduction de volume

SI aucun mécanisme
    SI politique impose sa présence
        -> KO
    SINON
        -> NA

POUR chaque mécanisme
    VÉRIFIER qu'il agit réellement sur le volume
    VÉRIFIER sa position
    DÉTERMINER son état d'activation

    SI état inconnu
        -> NA

    SI actif ET production prouvée
        -> KO

    SI appliqué tard
        SI politique explicite
            -> KO
        SINON
            -> NA + diagnostic

    SI appliqué tôt ET neutralisé
        -> OK
FIN
```
