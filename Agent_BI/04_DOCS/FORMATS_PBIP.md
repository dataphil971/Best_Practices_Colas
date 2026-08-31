# Formats PBIP — référence de sourcing

> Document de référence pour `agent-bi-evidence-sourcing`. Chaque fait porte son
> **niveau d'autorité** (1 = documentation Microsoft, 4 = observation sur un
> fichier réel). Un fait de niveau 4 autorise à écrire un parseur tolérant ; il
> n'autorise pas à écrire « le format impose que ».
>
> Attribution : une partie des faits de structure provient de
> [`santoshkanthety/powerbi-agent`](https://github.com/santoshkanthety/powerbi-agent)
> (licence MIT), skills `powerbi-pbip-format` et `powerbi-pbir-format-enhanced`.

---

## 1. Arborescence d'un projet PBIP

```text
<Projet>/
├── <Nom>.pbip                  point d'entrée, optionnel — tableau artifacts[]
├── <Nom>.Report/               REQUIS
│   ├── definition.pbir         point d'entrée du rapport
│   ├── definition/             (format PBIR)  ─┐ mutuellement
│   ├── report.json             (format legacy) ─┘ exclusifs
│   ├── StaticResources/
│   └── .pbi/                   état local, optionnel
└── <Nom>.SemanticModel/        OPTIONNEL — absent pour un rapport « fin »
    ├── definition.pbism
    ├── definition/             (TMDL)   ─┐ mutuellement
    ├── model.bim               (TMSL)   ─┘ exclusifs
    └── .pbi/
```

**Autorité 1–2.** Le dossier `.Report/` est requis ; `.SemanticModel/` est
optionnel — un rapport fin ne contient que `.Report/` et pointe vers un modèle
distant.

`definition.pbir` déclare le mode de liaison :

```text
byPath          modèle embarqué      (rapport « épais »)
byConnection    modèle distant       (rapport « fin »)
```

**Conséquence pour Agent BI :** une analyse peut légitimement ne trouver aucun
modèle sémantique. Ce n'est pas une erreur, c'est un rapport fin. Aucune règle
de périmètre `SEMANTIC_MODEL` ne doit rendre `KO` dans ce cas — `NA`.

Les dossiers `.pbi/` (`localSettings.json`, `cache.abf`, …) sont un **état par
utilisateur et par machine**, entièrement optionnels. Ne jamais en faire une
source de preuve, ne jamais les versionner.

---

## 2. Rapport — deux sérialisations

### 2.1 PBIR (format étendu)

**Autorité 1–2.**

```text
<Nom>.Report/
└── definition/
    ├── version.json
    ├── report.json                 ← à la racine de definition/
    ├── reportExtensions.json
    ├── pages/
    │   ├── pages.json
    │   └── <pageId>/
    │       ├── page.json
    │       └── visuals/<visualId>/visual.json
    └── bookmarks/
        ├── bookmarks.json
        └── <id>.bookmark.json
```

- Un fichier JSON par visuel, portant sa mise en forme **et** ses liaisons de
  champs.
- Thèmes : `StaticResources/RegisteredResources/<Theme>.json`.
- **JSON strict : aucun commentaire autorisé.**
- Le format PBIR ne supporte ni `report.json` legacy, ni les métadonnées
  `layout`.

### 2.2 Legacy

**Autorité 4 — observé, non spécifié.** Microsoft ne documente pas ce format au
même niveau que PBIR. Tout ce qui suit provient de rapports réels.

```text
<Nom>.Report/
└── report.json                     ← à la RACINE de .Report/, fichier unique
```

Caractéristiques constatées :

```text
configs sérialisées comme des CHAÎNES JSON imbriquées, à décoder récursivement
références de champ par alias : SourceRef.Source → résolu via From[].Name/Entity
groupes de visuels                : type singleVisualGroup
interactions                      : section.config.relationships
signets                           : report.config.bookmarks, sous forme d'arbre
filtres                           : aux trois niveaux (rapport / page / visuel)
```

Le fichier peut dépasser plusieurs Mo d'un seul tenant.

### 2.3 Détection — le piège

Les deux formats possèdent un fichier nommé `report.json`. **Seul son
emplacement les distingue :**

```text
<Nom>.Report/definition/report.json   → PBIR
<Nom>.Report/report.json              → legacy
```

Implémenté dans `report_legacy_parser.is_legacy_report()`, qui teste la
présence du fichier **à la racine** de `.Report/`. Une détection par nom de
fichier seul confondrait les deux.

### 2.4 Ne pas confondre avec le PBIX

**Autorité 1.** À l'intérieur d'un `.pbix`, le rapport est stocké soit dans
`Report/definition/` (PBIR), soit dans `Report/Layout` (legacy, UTF-16LE,
JSON monolithique à chaînes imbriquées) — jamais les deux.

`Report/Layout` est le legacy **du PBIX**. Il est distinct du `report.json`
legacy **du PBIP** décrit en 2.2, même si les deux partagent le principe des
chaînes JSON imbriquées. Agent BI ne lit que le PBIP.

---

## 3. Modèle sémantique — deux sérialisations

**Autorité 1.**

```text
definition/     TMDL, dossier de fichiers texte      (moderne, préféré)
model.bim       TMSL, fichier JSON unique            (legacy)
```

Les deux sont mutuellement exclusifs. **Agent BI ne lit aujourd'hui que le
TMDL** — un projet en `model.bim` n'est pas analysable et doit produire une
erreur d'analyse explicite, jamais un verdict.

### 3.1 Partitions et nature de source

**Autorité 4 — observé.** L'en-tête d'une partition déclare la nature de sa
source après le `=` :

```tmdl
partition F_SALES = m                 code Power Query
partition MEASURE = calculated        expression DAX — PAS de code M
partition X       = entity            …
```

Une partition `calculated` n'a pas de requête Power Query. Toute règle
raisonnant sur du M doit la classer hors périmètre plutôt que `KO` ou `NA`
(cf. BP-15).

### 3.2 Colonnes de tables calculées

**Autorité 4 — observé, à confirmer en autorité 1.**

Les colonnes d'une table `calculated` **ne portent pas de `dataType`** : Power
BI le déduit de l'expression DAX. Vérifié sur `AI_BAROMETER_BI-CDS` — 16
colonnes sans `dataType`, 16 appartenant à une table `calculated`, sans
exception.

Elles portent en revanche un `sourceColumn` positionnel :

```tmdl
partition T_CHOICE = calculated
    source = {
        ("Per job",     NAMEOF(D_USERS[USER_JOB]),     0),
        ("Per country", NAMEOF(D_USERS[USER_COUNTRY]), 1) }

column NEW_T_CHOICE            sourceColumn: [Value1]   → position 1
column 'NEW_T_CHOICE Champs'   sourceColumn: [Value2]   → position 2
column 'NEW_T_CHOICE Commande' sourceColumn: [Value3]   → position 3
```

`[ValueN]` désigne la N-ième position du constructeur de table DAX. Le type de
chaque position est lisible sur le littéral qui l'occupe.

**Statut : NON SOURCÉ.** La correspondance `[ValueN]` → position est une
déduction cohérente sur tous les cas observés, pas une spécification lue. Elle
doit être confirmée sur Microsoft Learn avant d'être utilisée comme preuve de
type au sens du §4 de `11_DataTypesPrecision.md`.

Contre-exemple connu, à traiter : `Row("Column", BLANK())` ne porte aucun type.

---

## 4. Ce qui reste à sourcer

| Sujet | Statut | Enjeu |
|---|---|---|
| Correspondance `[ValueN]` → position DAX | NON SOURCÉ | preuve de type BP-11 |
| Schéma du `report.json` legacy | NON SOURCÉ | robustesse du parseur legacy |
| Valeurs possibles de la nature de partition | NON SOURCÉ | périmètre BP-15 |
| Encodage garanti du legacy (`utf-8-sig` supposé) | NON SOURCÉ | lecture du fichier |
