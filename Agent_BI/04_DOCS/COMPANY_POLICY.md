# COMPANY_POLICY — conventions et exigences de l'entreprise

> **État : §1 renseignée à partir d'un seul modèle, à valider. §2 à §5 vides.**
>
> Les entrées de la §1 ont été **relevées automatiquement** le 30/08/2026 sur
> `AI_BAROMETER_BI-CDS`, **un seul projet**, à la demande explicite du
> mainteneur (cf. la troisième puce de « Ce que ce fichier n'est pas » : la
> règle reste qu'un agent ne complète pas ce fichier de sa propre initiative).
> Rien n'y est déduit ni supposé : chaque entrée porte le décompte qui la fonde,
> et ce qui n'était pas mesurable est resté vide.
>
> Un modèle n'est pas une entreprise. Tant qu'un responsable BI n'a pas confirmé
> qu'il s'agit bien du standard interne, ces entrées décrivent une **pratique
> observée**, pas une exigence Colas. Les valider ou les corriger est un acte
> humain, et c'est cette validation — pas ce relevé — qui les rend opposables.
>
> Tant qu'une section reste vide, les règles qui en dépendent se comportent
> exactement comme aujourd'hui — elles rendent `NA` faute de preuve de niveau 1.
>
> **Attention — ce fichier n'est encore lu par aucun code.** Il n'est cité que
> dans les docstrings de `bp_11.py` et `bp_37.py` ; la convention réellement
> appliquée par le moteur est écrite en dur dans `rules/bp_21.py`. Renseigner
> une section ne change donc rien au comportement tant que le branchement n'est
> pas fait (cf. `CHECKLIST_AGENT_BI.md`).

## Ce que ce fichier est

La frontière entre deux choses que l'agent ne doit jamais confondre :

```text
Recommandation Power BI        ≠        Règle de gouvernance entreprise
(vraie partout)                         (vraie ici, décidée par l'entreprise)
```

Une recommandation Microsoft ne devient jamais une exigence Colas
automatiquement. C'est ce fichier, et lui seul, qui opère ce passage.

## Ce que ce fichier n'est pas

- Ce n'est pas une source de `KO` par défaut. Une politique absente ne rend rien
  non conforme : elle rend le contrôle `NA`.
- Ce n'est pas un lieu d'intuition. Une convention qui n'est pas réellement
  appliquée dans l'entreprise n'a pas sa place ici — elle produirait des `KO`
  fondés sur une règle que personne ne suit.
- Ce n'est pas modifiable par un agent. Aucun skill ne doit inventer, deviner ou
  compléter ce fichier (cf. `agent-bi-skill-creator`, `agent-bi-bpa-mapper`).

## Règles qui en dépendent

Treize algorithmes le consultent. Renseigner une section ci-dessous change le
comportement des règles correspondantes — et de rien d'autre.

| Algorithme | Ce que la politique apporterait |
|---|---|
| `08_EarlyDevFilter` | mécanisme de filtrage de développement imposé en permanence |
| `11_DataTypesPrecision` | type attendu par colonne — **preuve de niveau 1** |
| `14_DisableLoadIntermediate` | convention explicite de table de staging |
| `16_IncrementalRefresh` | seuils de volume / durée déclenchant l'exigence |
| `18_ReduceCardinality` | seuils de cardinalité acceptables |
| `20_ReferentialIntegrity` | exigence d'intégrité référentielle |
| `21_ConciseNames` | conventions de nommage, et **périmètre** : objet masqué jugé ou non |
| `25_HideTechnicalFields` | ce qui vaut démonstration qu'un champ est technique |
| `28_KeepOnlyNecessaryMeasures` | méthode d'échantillonnage autorisée |
| `37_OrganizeVisualsBookmarks` | conventions d'organisation du rapport |
| `38_EliminateVisualInteractions` | interactions interdites ou imposées |
| `40_SyncSlicers` | synchronisation de segments imposée |
| `41_RemoveRedundantVisuals` | répétitions explicitement autorisées |

---

## 1. Conventions de nommage

> Relevé sur `AI_BAROMETER_BI-CDS` le 30/08/2026. Colonne « Observé » = ce que
> le modèle démontre. **À valider avant de faire foi.**

### 1.1 Préfixes de table

| Préfixe | Signification | Observé |
|---|---|---|
| `D_` | Dimension | 4 tables, toutes visibles |
| `F_` | Table de faits | 2 tables, toutes visibles |
| `P_` | Table de paramètres de champs Power BI | 4 tables, **toutes** générées par la fonctionnalité *Nouveau paramètre → Champs* (`sourceColumn: [ValueN]`, `relatedColumnDetails/groupByColumn`) |
| `T_` | Table technique | 4 tables, **toutes** `isHidden` au niveau table |

Une table sans préfixe : `MEASURE`, table porteuse des mesures. Déjà traitée
comme exemption par `bp_21.py` (`TABLE_NAME_EXEMPTIONS`).

**Conformité observée : 14 tables sur 14.**

### 1.2 Nommage des colonnes — et son périmètre

| Périmètre | Convention | Observé |
|---|---|---|
| Colonne **visible** | `UPPER_SNAKE_CASE` | **36 / 37 conformes** — un seul écart, `F_ADOPTION_QUESTION.'USAGE LABEL'` |
| Colonne **masquée** | *aucune convention appliquée* | **17 / 32 conformes** — soit un tirage à pile ou face |

C'est l'entrée la plus lourde de conséquences de ce fichier. Le modèle démontre
que la convention est **réellement appliquée aux colonnes visibles**, et
**réellement non appliquée aux colonnes masquées**. Sur 15 colonnes masquées non
conformes, 10 portent un nom que Power BI **impose** (`… Fields`, `… Order` des
paramètres de champs) : l'auteur ne peut pas s'y conformer sans se battre contre
l'outil.

**Appliqué.** `BP-21` exclut désormais les colonnes masquées de son périmètre,
comme `BP-07` le faisait déjà — les deux règles partagent la constante
`HIDDEN_COLUMN_REASON`, si bien qu'elles ne peuvent plus diverger sans qu'un
test le voie. Effet mesuré sur `AI_BAROMETER_BI-CDS` : **18 `KO` de BP-21
tombent à 3**, et le total du projet passe de **30 à 15**. Voir
`01_ALGORITHMES/21_ConciseNames.md` §4.1 pour le raisonnement complet.

Ce qui reste en `KO` est ce que la convention vise réellement :
`F_ADOPTION_QUESTION.'USAGE LABEL'` (colonne visible, espace interne) et les
deux mesures `'Dynamic Title Top'` / `'Dynamic Title bottom'`.

### 1.3 Nommage des mesures

Pas d'espace interne. Casse mixte avec séparateur `_` : `pct_RespondentsPerUsage`,
`Nb_Responses`, `NOTIF_Title`, `Response_Rate`.

**Conformité observée : 35 mesures sur 37.** Les deux écarts —
`'Dynamic Title Top'` et `'Dynamic Title bottom'` — sont des exceptions à la
pratique du modèle lui-même, pas la pratique normale. La convention Power BI
courante (Title Case avec espaces, parce que le nom est ce que l'utilisateur lit
dans le volet Champs) n'est **pas** celle appliquée ici.

## 2. Types de données attendus

<!-- Preuve de niveau 1 pour BP-11 (cf. 11_DataTypesPrecision.md §4).
Format attendu : une correspondance explicite et vérifiable, par exemple

| Table | Colonne | Type attendu | Justification |
|---|---|---|---|

Une entrée ici autorise BP-11 à conclure OK ou KO sur la colonne concernée.
Sans entrée, elle rend NA — ce qui est le comportement actuel. -->

*(non renseigné — et non renseignable à partir d'un modèle)*

> `AI_BAROMETER_BI-CDS` ne démontre aucun type attendu. `BP-11` y rend 56 `NA`,
> dont 40 « colonne hors périmètre numérique » et le reste « type métier attendu
> non démontrable (aucune conversion Power Query résolue) ». Un `dataType`
> constaté dans le TMDL dit ce que le modèle **fait**, jamais ce qu'il
> **devrait** faire : le recopier ici ne serait pas une politique, seulement un
> miroir qui rendrait tout conforme par construction.
>
> Cette section demande une décision métier, table par table. C'est la plus
> rentable des sections vides : 56 `NA` sur ce seul projet.

## 3. Seuils

<!-- Volumes, durées de rafraîchissement, cardinalités — utilisés par
16_IncrementalRefresh et 18_ReduceCardinality. Un seuil déclaré ici doit être
un seuil réellement décidé, pas une valeur ronde plausible. -->

*(non renseigné)*

> Aucune trace exploitable dans le modèle : un seuil est une décision, il ne
> laisse pas d'empreinte dans un fichier PBIP. Les règles concernées (`BP-16`,
> `BP-18`) ne sont d'ailleurs pas encore implémentées.

## 4. Exigences de gouvernance

<!-- Intégrité référentielle, filtrage de développement, sécurité. -->

*(non renseigné)*

> **Le modèle démontre ici le contraire d'une exigence.** `BP-10` y relève
> 5 relations dont les deux clés sont de type `string`
> (`F_RESPONSES.CAMPAIGN_ID`, `CAMPAIGN_USER_LOGIN`, …). La recommandation
> « clés de relation entières » n'est donc **pas** appliquée sur ce projet.
>
> Elle reste une bonne pratique Power BI, et `BP-10` continue de la signaler
> comme telle. Mais la déclarer ici en ferait une exigence Colas, ce que rien
> n'établit — et ce serait exactement l'erreur que ce fichier existe pour
> empêcher : promouvoir une recommandation en règle d'entreprise sans décision.

## 5. Conventions de rapport

<!-- Organisation, interactions, synchronisation de segments, répétitions
autorisées — utilisées par 37, 38, 40, 41. -->

*(non renseigné)*

> Le rapport de `AI_BAROMETER_BI-CDS` passe `BP-37` (organisation) et `BP-38`
> (interactions) en `OK` sans politique : rien à déclarer tant qu'aucune
> exigence ne va au-delà de ce que les règles vérifient déjà.
>
> `BP-41` y laisse 7 candidats à la redondance en `NA` (« qualification
> contextuelle requise »), dont des groupes de 6 et 7 visuels de signature
> identique. Si ces répétitions sont **voulues** — une même carte déclinée par
> page, par exemple — c'est ici qu'il faut le déclarer pour que la règle cesse
> de les remonter. Cela suppose de regarder le rapport, pas le fichier.

---

## Comment renseigner une section

1. Vérifier que la convention est **réellement appliquée** dans l'entreprise,
   pas seulement souhaitable.
2. L'écrire de façon vérifiable par un parseur : un nom de propriété, une
   valeur, un seuil — pas une intention.
3. Répercuter dans l'algorithme concerné (`01_ALGORITHMES/NN_*.md`) si sa
   logique `OK/KO/NA` change, **avant** de toucher au Python
   (cf. `tools/check_spec_sync.py`).
4. Ajouter une fixture et un test pour le nouveau cas
   (cf. `agent-bi-test-generator`).
