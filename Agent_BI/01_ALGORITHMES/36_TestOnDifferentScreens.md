# BP-36 — Test et validation du rapport sur différents écrans, résolutions et navigateurs

## 1. Objectif

Séparer clairement :

1. les contrôles statiques réellement observables dans PBIR ;
2. la validation réelle multi-écrans / multi-navigateurs, qui ne peut pas être prouvée à partir des fichiers seuls.

Statuts Agent BI :

```text
OK / KO / NA
```

---

## 2. Sources statiques

```text
<REPORT_PATH>/definition/pages/pages.json
<REPORT_PATH>/definition/pages/<pageId>/page.json
```

Éventuellement :

- structure PBIR mobile si elle est présente ;
- document de plan de test comme contexte de gouvernance.

La présence d'un plan de test ne prouve jamais que les tests ont été exécutés.

---

## 3. Sous-contrôle A — cohérence des dimensions

Pour chaque page visible :

- `width` ;
- `height`.

Décision :

```text
dimensions illisibles -> NA
dimensions incohérentes entre pages comparables -> KO
dimensions cohérentes -> OK
```

---

## 4. Sous-contrôle B — mise en page mobile

La présence d'un layout mobile est observable.

Son absence n'est cependant pas une preuve universelle de non-conformité, sauf si la politique de l'entreprise l'impose explicitement.

Par défaut :

```text
layout mobile présent -> OK pour ce sous-contrôle
layout mobile absent -> NA + diagnostic
```

Si `COMPANY_POLICY` contient une exigence obligatoire de layout mobile pour certaines pages :

```text
absence -> KO
```

---

## 5. Sous-contrôle C — test réel navigateur / écran

À partir d'un PBIP seul, l'agent ne peut pas prouver qu'un rapport a été réellement testé :

- Edge ;
- Chrome ;
- Safari ;
- application Power BI Mobile ;
- tablette ;
- différentes résolutions.

Par conséquent :

```text
cross_device_runtime_validation = NA
```

sauf si une preuve d'exécution externe fiable est fournie (résultats de tests, artefacts CI, captures avec métadonnées, etc.).

---

## 6. Pseudo-code

```python
def evaluate_screen_compatibility(report, company_policy):
    static_results = []

    dimensions = collect_visible_page_dimensions(report)

    if dimensions.unreadable_pages:
        static_results.append(
            finding_na(
                reason="Dimensions de page non déterminables",
                evidence=dimensions.unreadable_pages,
            )
        )

    if dimensions.has_inconsistency:
        static_results.append(
            finding_ko(
                reason="Dimensions incohérentes entre pages visibles",
                evidence=dimensions.inconsistent_pages,
            )
        )
    elif dimensions.visible_pages:
        static_results.append(finding_ok(reason="Dimensions cohérentes"))

    for page in report.visible_pages:
        has_mobile = detect_mobile_layout(page)

        if company_policy.mobile_layout_required(page):
            static_results.append(
                finding_ok(page=page.name)
                if has_mobile
                else finding_ko(
                    page=page.name,
                    reason="Mise en page mobile obligatoire absente",
                )
            )
        elif not has_mobile:
            add_diagnostic(
                page=page.name,
                diagnostic_type="MOBILE_LAYOUT_NOT_DETECTED",
                diagnostic_level="INFO",
            )

    runtime_validation = finding_na(
        reason="Validation réelle multi-écrans/multi-navigateurs non observable dans PBIP"
    )

    return aggregate(
        static_results=static_results,
        runtime_validation=runtime_validation,
    )
```

---

## 7. Statut global

La pratique complète contient un volet humain non observable.

Par défaut :

```text
si une non-conformité statique prouvée existe -> KO
sinon si la validation réelle n'est pas prouvée -> NA
sinon -> OK
```

Ainsi, l'absence de preuve n'est jamais transformée en conformité.
