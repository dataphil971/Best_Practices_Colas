# Agent BI de scoring automatique — Algorithmie

**Veridash · Colas — Document de conception technique v1.0**
Remplace l'agent « Power BI Best Practices Agent » (TOM/AMO, Windows) par un moteur d'analyse et de notation automatique, exécutable côté serveur Linux.

---

## 1. Principe directeur

Un agent de conformité n'a de valeur que s'il est **reproductible, explicable et prudent**.

Trois règles structurent toute la conception :

1. **Séparation extraction / évaluation.** L'agent ne lit jamais le fichier Power BI depuis une règle. Il produit d'abord une représentation intermédiaire normalisée (le *MIR*), puis exécute les règles sur cette structure. Conséquence : un même rapport donne le même score qu'il arrive en `.pbip`, en `.pbix` ou via XMLA, et l'ajout d'un format d'entrée ne touche à aucune règle.

2. **Pas de verdict sans preuve.** Un point de contrôle rempli sans objet identifié, sans emplacement et sans valeur observée est refusé par le backend. Une règle qui ne peut pas produire de preuve doit répondre `INDÉTERMINÉ`, jamais `OK`.

3. **L'agent ne décide pas à la place du relecteur, il l'instruit.** Il pré-remplit ce qui est objectivable, signale ce qui est probable, et laisse vide ce qui relève du jugement — en fournissant dans tous les cas le matériau chiffré.

---

## 2. Architecture du pipeline

```
   ┌──────────────┐
   │  1. COLLECTE │  pbip · pbix · XMLA · REST
   └──────┬───────┘
          │  artefacts bruts
   ┌──────▼───────┐
   │ 2. EXTRACTION│  TMDL/model.bim · Section1.m · Layout/report.json · thème · stats VertiPaq
   └──────┬───────┘
          │  objets typés
   ┌──────▼───────────────┐
   │ 3. NORMALISATION MIR │  modèle unique, indépendant du format d'entrée
   └──────┬───────────────┘
          │  MIR + empreinte Merkle
   ┌──────▼───────────────┐
   │ 4. INDEXATION        │  index d'usage · AST DAX · AST M · graphe de relations · lignées
   └──────┬───────────────┘
          │  MIR enrichi (faits pré-calculés, partagés)
   ┌──────▼───────────────┐
   │ 5. ÉVALUATION        │  59 checkers purs, exécutés en parallèle
   └──────┬───────────────┘
          │  Findings (ρ, preuves, confiance)
   ┌──────▼───────────────┐
   │ 6. DÉCISION          │  ρ + profil de seuils + garde-fous de confiance → statut
   └──────┬───────────────┘
          │  Proposition de revue
   ┌──────▼───────────────┐
   │ 7. APPLICATION       │  aperçu (dry-run) → confirmation → écriture des review_items
   └──────────────────────┘
```

Chaque étage a une frontière nette et un contrat de sortie sérialisable. C'est ce qui permet de tester chaque étage isolément et de rejouer une analyse à partir d'un MIR archivé, sans le fichier d'origine.

---

## 3. Étage 1 — Collecte : comment l'agent accède au rapport

Quatre modes, par ordre de fiabilité décroissante.

### 3.1 Mode A — Projet PBIP *(recommandé)*

L'utilisateur dépose une archive du dossier de projet Power BI (`.pbip` + `Rapport.Report/` + `Rapport.SemanticModel/`).

| Avantage | Détail |
|---|---|
| Contenu textuel | TMDL et JSON, lisibles sans moteur Analysis Services |
| Complet | Modèle, DAX, Power Query et rapport, tous accessibles |
| Portable | Aucune dépendance Windows : s'exécute dans le conteneur Linux existant |
| Versionnable | Se prête au suivi Git, cohérent avec l'esprit du référentiel immuable |

C'est le seul mode qui atteint **100 % de couverture** des règles de classe A et B.

### 3.2 Mode B — Fichier `.pbix`

Le `.pbix` est une archive ZIP. Trois parties sont exploitables :

| Partie | Contenu | Lisibilité |
|---|---|---|
| `Report/Layout` | JSON UTF-16LE : pages, visuels, filtres, interactions, signets | **Directe** |
| `DataMashup` | ZIP imbriqué contenant `Section1.m` et les métadonnées de chargement | **Directe** |
| `Report/StaticResources` | Thème, images | **Directe** |
| `DataModel` | Flux Analysis Services compressé (XPress9) | **Indirecte** — nécessite une bibliothèque de décompression |
| `Metadata`, `Settings`, `DiagramLayout` | Options, annotations | Directe |

Conséquence pratique : sans décompression du `DataModel`, les règles portant sur le modèle sémantique (MOD-*, DAX-*, GEN-02, GEN-05) ne sont pas évaluables et passent en `INDÉTERMINÉ`. **C'est le point d'arbitrage n°1** — cf. question Q1.

Deux stratégies possibles :
- intégrer une bibliothèque Python de lecture du `DataModel` ;
- exiger le format PBIP pour la revue de modèle et n'accepter le `.pbix` que pour les règles de rapport et de Power Query, en affichant clairement la couverture obtenue.

### 3.3 Mode C — Point de terminaison XMLA (lecture seule)

Si les espaces de travail sont en capacité Premium ou Fabric, l'agent lit le modèle publié directement, sans téléversement de fichier. C'est le mode le plus propre en gouvernance (aucune copie du livrable ne transite). Il ne donne cependant pas accès au rapport `.pbix`, donc pas aux règles de mise en page : les deux modes sont complémentaires, pas concurrents.

### 3.4 Mode D — API REST Power BI (métadonnées)

Complément pour ce qui n'existe pas dans le fichier : politique d'actualisation configurée côté service, historique des rafraîchissements, appartenance à un espace de travail. Utile pour BIG-04.

### 3.5 Détection automatique

```
detecter_source(entrée):
    si entrée est une archive contenant *.SemanticModel/definition* → MODE_A (pbip)
    si entrée est un ZIP contenant "DataMashup" et "Report/Layout" → MODE_B (pbix)
    si entrée est une chaîne de connexion powerbi://           → MODE_C (xmla)
    sinon → erreur explicite, avec la liste des formats acceptés
```

L'agent annonce toujours à l'utilisateur, avant de commencer, **le taux de couverture attendu** pour le mode détecté (« 59 points sur 59 » ou « 33 points sur 59, le modèle sémantique n'est pas lisible dans ce format »).

---

## 4. Étage 3 — La représentation intermédiaire (MIR)

Le MIR est un graphe d'objets normalisé. Sa structure complète figure dans l'onglet `Schema_MIR` du classeur. Points essentiels :

- **Nommage canonique.** Toute référence d'objet est réduite à une clé unique `Table[Colonne]` ou `[Mesure]`, quelle que soit la façon dont l'artefact d'origine l'écrivait (`queryRef`, `Entity/Property`, TMDL). Sans cette canonicalisation, l'index d'usage est inexploitable.
- **Positions conservées.** Chaque objet garde son emplacement d'origine (fichier, ligne, chemin JSON) pour que les preuves soient cliquables.
- **Empreinte Merkle.** Un hachage est calculé par table, par requête M et par page ; la racine identifie le modèle. Deux usages : cache (ne pas ré-analyser un modèle inchangé) et **ré-analyse incrémentale** (seules les branches dont le hachage a changé sont réévaluées, ainsi que les règles qui en dépendent).

---

## 5. Étage 4 — Indexation : les faits partagés

C'est l'étage qui fait la différence entre un agent lent et un agent rapide. Sans lui, chaque règle reparcourrait le modèle, soit un coût `O(R × N)` pour `R` règles et `N` objets. Avec lui, on paye `O(N)` une fois, puis chaque règle lit un index en temps constant.

Cinq structures sont construites en un seul passage :

| Index | Contenu | Construit une fois pour |
|---|---|---|
| `usageIndex` | objet → ensemble des usages (visuel, mesure, relation, hiérarchie, tri, RLS, format conditionnel, info-bulle, signet) | MOD-03, GEN-01, GEN-04, DAX-01a, DSG-05 |
| `astDax` | arbre syntaxique + jetons + complexité `K` + empreintes de fragments, mémoïsé par hachage d'expression | DAX-01→06, MOD-07, BIG-05 |
| `astM` | arbre par requête, classification de foldabilité par étape | PQ-01→07, BIG-01→04 |
| `relGraph` | graphe des relations + fermeture transitive du filtrage + détection de cycles | MOD-04, GEN-05, DSG-04, DSG-05 |
| `lineage` | visuel → ensemble des tables atteignables par filtrage | DSG-04, DSG-05, DSG-06 |

**Mémoïsation.** Deux mesures au code identique ne sont analysées qu'une fois : la clé de cache est le hachage de l'expression normalisée. Sur les modèles réels, où les mesures se déclinent en variantes, le gain est substantiel.

---

## 6. Étage 5 — Le moteur de règles

### 6.1 Contrat d'un checker

Toute règle est une fonction **pure**, sans effet de bord, qui reçoit le MIR indexé et la configuration, et retourne un objet unique :

```python
@regle(
    id="MOD-04b",
    categorie="Modèle",
    criticite=BLOQUANT,
    classe=DETERMINISTE,          # A | B | C
    profil=P1,                    # profil de seuils
    depend_de=["relGraph"],       # index requis
    precondition=lambda mir: len(mir.relationships) > 0,
)
def relations_bidirectionnelles(mir, cfg) -> Finding:
    total = [r for r in mir.relationships if r.isActive]
    if not total:
        return Finding.non_applicable("Aucune relation active dans le modèle.")

    fautives = [r for r in total
                if r.crossFilteringBehavior == "bothDirections"
                and r.cle not in cfg.EXCEPTIONS_BIDIR]

    return Finding(
        rho          = 1 - len(fautives) / len(total),
        numerateur   = len(total) - len(fautives),
        denominateur = len(total),
        confiance    = 1.00,
        preuves      = [Preuve(objet=r.cle,
                               emplacement=r.chemin,
                               observe="bothDirections",
                               attendu="singleDirection")
                        for r in fautives],
        remediation  = "Passer en filtrage simple ; utiliser CROSSFILTER dans la mesure si nécessaire.",
    )
```

Trois propriétés découlent de ce contrat :

- **Testabilité.** Un checker se teste avec un MIR fabriqué à la main, sans fichier Power BI.
- **Parallélisation.** Les checkers étant purs et ne partageant que des index en lecture, ils s'exécutent dans un pool de processus sans verrou.
- **Versionnement.** Le jeu de règles porte un numéro de version, stocké dans la revue au même titre que `rule_version_id`. Deux analyses ne sont comparables que si les deux versions coïncident.

### 6.2 Ordonnancement

Les règles forment un graphe orienté acyclique par leurs préconditions et leurs dépendances d'index. L'ordonnanceur :

1. calcule les index requis (étage 4), une fois ;
2. évalue les **préconditions de catégorie** en premier — notamment `BIG-00` : si le modèle fait moins de 1 Go, les six règles `BIG-*` sont marquées `NON APPLICABLE` sans être exécutées, ce qui économise l'intégralité de l'analyse de foldabilité ;
3. lance les checkers restants par vagues, du moins coûteux au plus coûteux, avec court-circuit : si `MOD-04a` et `MOD-04b` sont déjà calculées, la règle mère `MOD-04` les agrège sans reparcourir le graphe.

### 6.3 Les trois classes d'automatisation

| Classe | Nb de points | Comportement |
|---|---|---|
| **A — Déterministe** | 39 | La conformité se lit dans les artefacts. Confiance ≥ 0,85. Statut pré-rempli. |
| **B — Heuristique** | 17 | La conformité s'estime par un score et un seuil. Confiance 0,60–0,85. Statut pré-rempli, marqué « à confirmer », plafonné à `PARTIEL` si la confiance est sous `CONFIANCE_MIN_KO`. |
| **C — Humaine** | 3 | L'acte de conformité n'est pas observable (tester sur plusieurs navigateurs, profiler avec DAX Studio, juger un besoin futur). Statut laissé vide, pré-diagnostic chiffré fourni. |

Les **12 règles bloquantes sont toutes de classe A** : l'agent ne bloque jamais un livrable sur une heuristique.

---

## 7. Étage 6 — La fonction de décision

C'est le cœur de la prudence de l'agent. Le passage du taux `ρ` au statut n'est pas une simple comparaison.

```
def decider(finding, regle, cfg) -> (statut, mode_remplissage):

    # 1. Non applicable — précondition non satisfaite
    if finding.non_applicable:
        return ("NA", AUTO)

    # 2. Indéterminé — la règle n'a pas pu observer
    if finding.rho is None or finding.denominateur == 0:
        return ("NON_RENSEIGNE", PRE_DIAGNOSTIC)

    # 3. Classe C — jamais de verdict automatique
    if regle.classe == HUMAINE and not finding.anomalie_objectivable:
        return ("NON_RENSEIGNE", PRE_DIAGNOSTIC)

    # 4. Application du profil de seuils
    statut = profil_vers_statut(regle.profil, finding.rho, cfg)

    # 5. Garde-fou de confiance — on ne durcit jamais sur une estimation faible
    if finding.confiance < cfg.CONFIANCE_MIN_KO and statut == "KO":
        statut = "PARTIEL"
    if finding.confiance < cfg.CONFIANCE_MIN_AUTOREMPLISSAGE:
        return (statut, A_CONFIRMER)

    # 6. Garde-fou de preuve — un KO sans preuve exploitable est refusé
    if statut in ("KO", "PARTIEL") and not finding.preuves:
        return ("NON_RENSEIGNE", PRE_DIAGNOSTIC)

    return (statut, AUTO)
```

### 7.1 Profils de seuils

| Profil | OK | PARTIEL | KO | Usage |
|---|---|---|---|---|
| **P1** strict | ρ = 1 | — | ρ < 1 | Règles bloquantes déterministes |
| **P2** standard | ρ ≥ 0,95 | 0,60 ≤ ρ < 0,95 | ρ < 0,60 | Cas général |
| **P3** souple | ρ ≥ 0,85 | 0,50 ≤ ρ < 0,85 | ρ < 0,50 | Règles heuristiques |
| **P4** seuils absolus | compteur sous seuil | zone intermédiaire | compteur au-dessus | Règles à potentiel (DAX-05, GEN-03) |
| **P5** humain | — | — | — | Pré-diagnostic seul |

### 7.2 Asymétrie volontaire

L'agent est **conservateur sur le KO et exigeant sur le OK**. Un faux `KO` fait perdre du temps à une équipe et discrédite l'outil ; un faux `OK` laisse passer un défaut. Les deux sont coûteux, mais le premier tue l'adoption. D'où :

- le plafonnement à `PARTIEL` sous seuil de confiance ;
- l'exigence de preuve pour tout statut négatif ;
- l'exigence de `ρ = 1` pour un `OK` sur les règles bloquantes.

### 7.3 Score de conformité

**Inchangé.** L'agent ne calcule pas le score : il remplit des statuts, et Veridash applique sa formule existante.

```
score = round((ok + 0,5 × partiel) / évalué × 100)
```

où `évalué` exclut les points `NA` et `NON_RENSEIGNE`. Un rapport dont l'agent n'a pu évaluer que 33 points sur 59 est donc scoré sur 33, et l'interface indique explicitement la couverture. Confondre « conforme » et « non vérifié » serait la faute la plus grave que puisse commettre cet agent.

---

## 8. Compromis qualité / coût / délai

### 8.1 Complexité

Soit `N` objets du modèle, `V` visuels, `S` étapes M, `M` mesures, `R` relations.

| Étage | Complexité | Commentaire |
|---|---|---|
| Extraction | `O(taille du fichier)` | Dominé par la décompression |
| Normalisation MIR | `O(N + V + S)` | Un seul passage |
| Indexation | `O(N + V + S + R)` | Le poste le plus lourd : `usageIndex` et les AST |
| Évaluation (59 règles) | `≈ O(N + V + S)` | Chaque règle lit un index, aucune ne reparcourt |
| Décision | `O(59)` | Négligeable |

Les deux seuls points quadratiques sont traités :
- **Quasi-doublons DAX** (`O(M²)` naïf) → index inversé sur les empreintes de n-grammes (hachage sensible à la localité), ramené à `O(M)` en pratique ;
- **Chevauchement de visuels** (`O(V²)` naïf) → algorithme de balayage, `O(V log V)`.

### 8.2 Budget de temps

| Taille du modèle | Cible p95 | Répartition indicative |
|---|---|---|
| < 100 Mo | 8 s | extraction 5 s · indexation 2 s · règles 1 s |
| 200 Mo | 30 s | extraction 20 s · indexation 7 s · règles 3 s |
| 1,5 Go | 3 min | extraction 2 min · indexation 45 s · règles 15 s |

L'extraction domine toujours. C'est là qu'il faut investir, pas dans l'optimisation des règles.

### 8.3 Les quatre leviers

1. **Cache par empreinte.** Racine Merkle identique → résultat servi depuis le cache, temps de réponse quasi nul. Cas fréquent : un relecteur rouvre une revue.
2. **Ré-analyse incrémentale.** Après correction, seules les branches modifiées sont réévaluées. Une correction de nommage sur une table ne relance pas l'analyse du Power Query.
3. **Court-circuit de précondition.** `BIG-00` évite six analyses lourdes sur la grande majorité des rapports.
4. **Parallélisme.** Les checkers purs s'exécutent sur un pool de processus. Gain réel modéré (les règles ne pèsent que 10 % du temps), à ne mettre en place qu'après avoir optimisé l'extraction.

### 8.4 Coût de la qualité

Le vrai coût n'est pas le temps machine, c'est **le calibrage**. Un agent livré sans calibrage produira des faux positifs sur les règles de nommage et de formatage, et l'équipe cessera de l'utiliser en trois semaines.

Protocole proposé :

1. Constituer un corpus de 8 à 10 rapports **déjà audités manuellement** (les revues existantes dans Veridash font office de vérité terrain).
2. Exécuter l'agent, calculer par règle la précision et le rappel contre l'audit humain.
3. Ajuster les seuils de l'onglet `Parametres` — et **seulement** eux, jamais le code.
4. Critère de mise en service par règle : précision ≥ 0,90 sur les verdicts négatifs. En dessous, la règle est rétrogradée en classe C (pré-diagnostic sans verdict) jusqu'à correction.
5. Conserver le corpus comme jeu de non-régression : toute modification du moteur le rejoue.

Ce protocole est le seul point qui demande du temps humain. C'est aussi celui qui détermine si l'agent sera utilisé ou contourné.

---

## 9. Le parcours « Utiliser l'agent BI »

### 9.1 Machine à états

```
INACTIF
   │  clic « Utiliser l'agent BI »
   ▼
CHOIX_SOURCE ──────────────► (déposer un fichier · indiquer un espace de travail)
   │  source fournie
   ▼
QUESTIONS_CONTEXTE ────────► 3 questions maximum, uniquement si la réponse
   │                          n'est pas déductible du fichier :
   │                          type de livrable · template CDS utilisé ·
   │                          dataset partagé par d'autres rapports
   ▼
EXTRACTION ────────────────► barre de progression, couverture annoncée
   ▼
ANALYSE ───────────────────► 59 points, progression par catégorie
   ▼
APERÇU  ◄──────────────────► l'utilisateur voit ce qui SERA écrit, sans écriture
   │  ├─ « Appliquer tout »
   │  ├─ « Appliquer seulement les points à haute confiance »
   │  └─ « Annuler »
   ▼
APPLIQUÉ ──────────────────► écriture des review_items · annulation possible en un geste
```

**Le mode aperçu n'est pas optionnel.** C'est lui qui transforme l'agent d'une boîte noire en un assistant : l'utilisateur voit le statut proposé, le taux `ρ`, les preuves et le niveau de confiance avant toute écriture.

### 9.2 Les questions posées à l'utilisateur

L'agent ne demande que ce qu'il ne peut pas déduire. Concrètement, trois questions au maximum :

| Question | Pourquoi | Si sans réponse |
|---|---|---|
| Type de livrable (Power BI / App BI / Build) | Conditionne MOD-07a | Déduit de la revue en cours |
| Le template CDS est-il utilisé ? | Conditionne DSG-01 et DSG-09 | Déduit par comparaison du thème ; si ambigu → `NA` |
| Ce modèle est-il partagé avec d'autres rapports ? | Conditionne la détection d'objets orphelins (DAX-01a, GEN-01) | Par défaut « non partagé », les règles passent en pré-diagnostic |

Tout le reste — présence de Databricks, taille du modèle, mode DirectQuery, nombre de pages — est **déduit du fichier**. Chaque question posée est une friction ; on n'en garde que trois.

### 9.3 Endpoints

```
POST   /api/v1/agent/analyses
       multipart (fichier) ou { connexion_xmla, contexte }
       → 202 { analyse_id, mode_detecte, couverture_attendue }

GET    /api/v1/agent/analyses/{id}
       → { statut, progression, etape_courante, resultats?, couverture, duree_ms }

GET    /api/v1/agent/analyses/{id}/apercu?revue_id=…
       → diff proposé : pour chaque point, statut actuel / statut proposé /
         ρ / confiance / preuves / mode (auto | à confirmer | pré-diagnostic)

POST   /api/v1/agent/analyses/{id}/appliquer
       { revue_id, portee: "tout" | "haute_confiance", points_exclus[] }
       → { appliques, ignores, conflits[] }

POST   /api/v1/agent/analyses/{id}/annuler-application
       → restaure l'état antérieur (les points écrasés sont journalisés)
```

L'analyse est asynchrone dès la première seconde (tâche Celery), conformément à l'architecture déjà en place.

### 9.4 Écriture dans la revue

L'agent respecte le principe de versionnement immuable : il écrit sur `rule_version_id`, jamais sur la règle mutable. Chaque point écrit porte :

```
source              = "agent"
agent_version       = "1.0.0"
ruleset_version     = "2026.08.1"
rho                 = 0.87
confiance           = 0.90
mode_remplissage    = "auto" | "a_confirmer" | "pre_diagnostic"
preuves             = JSONB [ { objet, emplacement, observe, attendu } ]
analyse_id          = UUID
```

Ces colonnes sont la condition de l'auditabilité : sans elles, personne ne peut expliquer six mois plus tard pourquoi un point était à `KO`.

**Conflits.** Si un point porte déjà un statut humain, l'agent ne l'écrase pas. Il crée un **écart signalé**, affiché dans l'aperçu et dans la revue : « le relecteur a saisi OK, l'agent calcule KO avec 3 preuves ». C'est souvent l'information la plus utile de toute l'analyse.

---

## 10. Sécurité et gouvernance

| Point | Décision |
|---|---|
| Rétention du fichier | Suppression après analyse, conformément à la rétention déjà paramétrable dans Veridash. Seul le MIR anonymisé peut être conservé pour la ré-analyse incrémentale. |
| Données métier | Lecture en mémoire uniquement, jamais persistée. Les preuves ne citent **jamais** de valeur de donnée métier — uniquement des noms d'objets, des positions et des compteurs. Exception : GEN-05 remonte jusqu'à 5 clés orphelines, à masquer si le paramètre de confidentialité l'exige. |
| Secrets | Les chaînes de connexion extraites du code M sont masquées dans les preuves (`Sql.Database("srv-***", "db-***")`). |
| Traçabilité | Chaque analyse est journalisée : auteur, horodatage, empreinte du modèle, version d'agent, version de règles, durée, couverture. |
| Isolation | L'analyse s'exécute dans un worker sans accès réseau sortant, hors mode XMLA. |

---

## 11. Feuille de route proposée

| Lot | Contenu | Résultat vérifiable |
|---|---|---|
| **A1** | Collecte PBIP + extraction TMDL/M/Layout + MIR + empreinte Merkle | Un fichier donne un MIR JSON complet et stable |
| **A2** | Indexation (usage, AST DAX, AST M, graphe de relations, lignées) | Les 5 index sont produits et testés unitairement |
| **A3** | Les 39 règles de classe A + moteur de décision | Score reproductible sur un rapport témoin |
| **A4** | Les 17 règles de classe B + garde-fous de confiance | Précision mesurée sur le corpus de calibrage |
| **A5** | Parcours « Utiliser l'agent BI » : endpoints, aperçu, application, annulation | Un utilisateur remplit une revue en un clic et peut revenir en arrière |
| **A6** | Calibrage sur corpus, non-régression, tableau de bord de précision par règle | Chaque règle a une précision documentée |
| **A7** *(optionnel)* | Lecture `.pbix` complète, mode XMLA, second passage par modèle de langage | Couverture 59/59 quel que soit le format |

Les lots A1 à A3 constituent le socle utilisable : ils couvrent à eux seuls les 12 règles bloquantes.

---

## 12. Ce que l'agent ne fera pas

Une liste courte, mais qui doit être écrite noir sur blanc pour éviter les malentendus :

- Il **ne juge pas** si un besoin futur justifie une granularité (GEN-04).
- Il **ne teste pas** le rendu sur plusieurs navigateurs et écrans (DSG-02) — il détecte seulement les débordements et chevauchements, qui sont objectivables.
- Il **ne profile pas** les performances DAX (BIG-05) — il produit la liste des mesures à profiler, classée par risque.
- Il **ne remplace pas** le relecteur : sur un rapport type, il pré-remplit environ 45 à 50 points sur 59, dont une partie signalée « à confirmer ». Le travail humain se déplace de la vérification mécanique vers l'arbitrage — ce qui est précisément l'objectif.
