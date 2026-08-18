# BP-40 — Synchronisation des slicers entre pages

## 1. Objectif

Vérifier la synchronisation des slicers multi-pages lorsque cette synchronisation est **attendue par la politique du rapport ou confirmée par le contexte**.

Le simple fait qu'un même champ soit utilisé comme slicer sur plusieurs pages ne prouve pas qu'il doit être synchronisé.

Des slicers identiques peuvent être volontairement indépendants selon la page.

Statuts :

```text
OK / KO / NA
```

---

## 2. Sources

```text
<REPORT_PATH>/definition/pages/**/visual.json
```

Le `AnalysisContext` fournit :

```text
slicer_index
sync_group_index
report_schema_versions
company_policy
sync_review_results
```

---

## 3. Identification d'un slicer

Un slicer est identifié par :

```json
{
  "visual": {
    "visualType": "slicer"
  }
}
```

Le ou les champs liés doivent être résolus à partir du `queryState`.

Un slicer hiérarchique peut contenir plusieurs projections.

Le checker ne doit pas supposer qu'il n'existe qu'un seul champ.

---

## 4. Configuration `syncGroup`

La configuration connue se trouve dans l'objet `visual` :

```json
{
  "visual": {
    "visualType": "slicer",
    "syncGroup": {
      "groupName": "DateSync",
      "fieldChanges": true,
      "filterChanges": true
    }
  }
}
```

Propriétés :

```text
groupName
fieldChanges
filterChanges
```

Le moteur doit lire explicitement :

```text
visual.syncGroup
```

et non rechercher arbitrairement toute clé contenant la chaîne `sync`.

---

## 5. Compatibilité de version

La propriété `syncGroup` n'est pas forcément exposée dans toutes les versions des schémas PBIR publics.

Le moteur doit donc :

1. conserver la version `$schema` du `visual.json` ;
2. lire la propriété si elle est présente ;
3. ne pas conclure que « syncGroup absent = synchronisation absente avec certitude » si le contrat de version analysé n'est pas suffisamment connu.

Valeurs :

```text
SYNC_PRESENT
SYNC_ABSENT_CONFIRMED
SYNC_UNKNOWN
```

---

## 6. Groupe de synchronisation

Deux slicers sont membres du même groupe lorsque le `groupName` résolu est identique.

Le moteur vérifie ensuite les propriétés de propagation :

```text
filterChanges
fieldChanges
```

Pour la synchronisation de sélection, la propriété décisionnelle principale est :

```text
filterChanges
```

Un groupe avec :

```text
filterChanges = false
```

ne doit pas être présenté comme garantissant la synchronisation du filtre utilisateur.

---

## 7. Compatibilité des champs

Des slicers d'un même groupe doivent être compatibles avec la définition attendue du groupe.

Le moteur compare :

```text
visualType
resolved field/projections
groupName
```

Si deux slicers d'un même `groupName` sont liés à des champs incompatibles et que le contrat applicable impose cette compatibilité :

```text
KO
```

Sinon :

```text
NA
```

---

## 8. Besoin de synchronisation

Valeurs :

```text
SYNC_REQUIRED
SYNC_NOT_REQUIRED
UNKNOWN
```

Cette décision provient :

- d'une `COMPANY_POLICY` ;
- d'une configuration du rapport ;
- d'un reviewer contextuel.

Exemple :

```yaml
bp_40:
  required_sync_fields:
    - D_USERS[USER_JOB]
    - D_DATE[Year]
```

---

## 9. Même champ sur plusieurs pages

Le regroupement par champ sert uniquement à détecter des **candidats** :

```text
MULTI_PAGE_SLICER_CANDIDATE
```

Sans policy/review :

```text
NA
```

et non `WARN`.

---

## 10. Synchronisation partielle

Une synchronisation limitée à certaines pages peut être parfaitement intentionnelle.

Elle devient `KO` uniquement si :

```text
SYNC_REQUIRED
```

sur un ensemble précis de pages et que la couverture observée ne correspond pas à cette exigence.

Sans exigence :

```text
NA / diagnostic
```

---

## 11. Décision

### Requirement = `SYNC_REQUIRED`

| Situation | Statut |
|---|---|
| toutes les pages requises appartiennent au même syncGroup avec `filterChanges=true` | `OK` |
| page requise absente du groupe | `KO` |
| groupes différents alors qu'un groupe commun est exigé | `KO` |
| `filterChanges=false` alors que la sélection doit être propagée | `KO` |
| configuration non interprétable | `NA` |

### Requirement = `SYNC_NOT_REQUIRED`

```text
NA / hors périmètre
```

### Requirement = `UNKNOWN`

```text
NA
```

---

## 12. Pseudo-code

```python
def resolve_slicer(
    visual,
    context,
):
    parsed = context.pbir_parser.parse_visual(
        visual
    )

    if not parsed.success:
        return None

    if parsed.visual_type != "slicer":
        return None

    fields = context.pbir_field_resolver.resolve_visual_fields(
        parsed
    )

    sync_group = parsed.visual.get(
        "syncGroup"
    )

    sync_state = context.sync_schema.resolve_state(
        schema_uri=visual.schema_uri,
        raw_sync_group=sync_group,
    )

    return {
        "visual_id": visual.id,
        "page_id": visual.page_id,
        "fields": fields,
        "sync_group": sync_group,
        "sync_state": sync_state,
    }
```

```python
def evaluate_required_sync(
    requirement,
    slicers,
    context,
):
    required_pages = set(
        requirement.pages
    )

    relevant = [
        s for s in slicers
        if s["page_id"] in required_pages
    ]

    if any(
        s["sync_state"] == "SYNC_UNKNOWN"
        for s in relevant
    ):
        return finding_na(
            object=requirement.id,
            reason="Configuration de synchronisation non interprétable",
        )

    if len(relevant) != len(required_pages):
        return finding_ko(
            object=requirement.id,
            reason="Slicer attendu absent sur au moins une page requise",
        )

    group_names = {
        s["sync_group"]["groupName"]
        for s in relevant
        if s["sync_group"]
    }

    if len(group_names) != 1:
        return finding_ko(
            object=requirement.id,
            reason="Pages requises non rattachées au même syncGroup",
        )

    if any(
        not s["sync_group"].get("filterChanges", False)
        for s in relevant
    ):
        return finding_ko(
            object=requirement.id,
            reason="filterChanges n'est pas activé pour tous les slicers requis",
        )

    return finding_ok(
        object=requirement.id,
        evidence={
            "groupName": next(iter(group_names)),
            "pages": sorted(required_pages),
        },
    )
```

---

## 13. Mode sans policy

Le moteur peut produire une liste de candidats :

```json
{
  "candidate_type": "MULTI_PAGE_SLICER",
  "field": "D_USERS[USER_JOB]",
  "pages": [
    "Overview",
    "Usage",
    "Training"
  ],
  "observed_sync_groups": []
}
```

Mais :

```text
rule_status = NA
```

tant que le besoin de synchronisation n'est pas démontré.

---

## 14. Statut global

```python
if any(r.status == "KO" for r in results):
    rule_status = "KO"

elif any(r.status == "NA" for r in results):
    rule_status = "NA"

elif results:
    rule_status = "OK"

else:
    rule_status = "NA"
```

Les slicers présents sur une seule page sont hors périmètre et ne sont pas artificiellement comptés `OK`.

---

## 15. Preuve obligatoire pour KO

```text
requirement_id
field
required_pages
observed_pages
syncGroup.groupName
filterChanges
fieldChanges
schema_uri
policy_id / review_source
evidence
```

Un simple :

```text
même champ sur plusieurs pages
```

n'est jamais suffisant pour produire `KO`.

---

## 16. Références techniques

La configuration actuelle de synchronisation PBIR peut être sérialisée sous :

```text
visual.syncGroup
```

avec notamment :

```text
groupName
fieldChanges
filterChanges
```

Le backend doit conserver le `$schema` du visuel et rester tolérant aux évolutions de PBIR.

---

## 17. Résumé

```text
RÈGLE BP-40

DÉTECTER les slicers
RÉSOUDRE leurs champs
LIRE explicitement visual.syncGroup

POUR chaque besoin de synchronisation
    SI besoin inconnu
        -> NA

    SI synchronisation non requise
        -> NA

    SI requise
        VÉRIFIER pages attendues
        VÉRIFIER groupName commun
        VÉRIFIER filterChanges=true

        SI conforme
            -> OK

        SI violation démontrée
            -> KO

        SI configuration illisible
            -> NA
FIN
```
