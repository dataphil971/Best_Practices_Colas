---
name: agent-bi-rule-engineer
description: Transformer une bonne pratique Power BI en algorithme Agent BI (BP-XX) rigoureux, avec sources PBIP/TMDL/PBIR explicites, preuves, conditions OK/KO/NA, cas limites et exigences d'implémentation. À utiliser pour créer ou améliorer les règles de Agent_BI/01_ALGORITHMES.
---

# Agent BI Rule Engineer

## Mission

Transformer une bonne pratique Power BI en algorithme Agent BI prêt à implémenter.

L'algorithme est la référence fonctionnelle. Il décrit CE QUI doit être contrôlé, indépendamment de la façon dont Python l'implémente (cf. `README_Agent_BI.md`).

## À lire avant de commencer

```text
Agent_BI/README_Agent_BI.md
Agent_BI/01_ALGORITHMES/           (fichiers existants, pour respecter le style et le gabarit établis)
Agent_BI/04_DOCS/CONVENTIONS.md    (si présent)
Agent_BI/04_DOCS/COMPANY_POLICY.md (si présent)
```

Ne jamais inventer une propriété Power BI. En cas de doute sur une propriété TMDL/PBIR, le signaler explicitement plutôt que de la supposer.

Procédure de sourcing et hiérarchie d'autorité : `agent-bi-evidence-sourcing`.

## Déroulé

### 1. Comprendre la bonne pratique

Identifier :

```text
Intention métier
Intention technique
Résultat attendu
```

Distinguer :

```text
recommandation Power BI générique
```

de :

```text
règle de gouvernance propre à l'entreprise
```

(cf. section `COMPANY_POLICY.md` du README)

### 2. Déterminer le périmètre

Utiliser l'un de :

```text
SEMANTIC_MODEL
REPORT
HYBRIDE
PROJET
```

### 3. Localiser les preuves

Identifier les sources exactes, par exemple :

```text
<SEMANTIC_MODEL_PATH>/definition/tables/*.tmdl
<SEMANTIC_MODEL_PATH>/definition/relationships.tmdl

# Rapport — DEUX sérialisations, mutuellement exclusives.
# Une BP de périmètre rapport doit traiter les deux, ou dire laquelle elle ne
# traite pas et rendre NA — jamais un OK sur un format qu'elle n'a pas lu.

# PBIR
<REPORT_PATH>/definition/report.json
<REPORT_PATH>/definition/pages/**/page.json
<REPORT_PATH>/definition/pages/**/visual.json

# legacy — fichier unique à la RACINE de .Report/, configs en chaînes JSON
<REPORT_PATH>/report.json
```

Détection, structures et pièges des deux formats :
`Agent_BI/04_DOCS/FORMATS_PBIP.md`.

Un `OK` rendu sur une sérialisation non lue est un faux `OK` — c'est le défaut
qu'a présenté BP-32 sur les rapports legacy.

Pour chaque propriété, définir :

```text
source
objet
propriété
représentation (TMDL / JSON)
exigence de parsing
```

### 4. Classifier l'automatisation

```text
DETERMINISTE
HYBRIDE
CONTEXTUELLE
```

Toujours privilégier DETERMINISTE quand c'est possible. Sinon, s'appuyer sur `agent-bi-skill-creator` pour trancher.

### 5. Définir OK

`OK` exige une preuve démontrant la conformité.

### 6. Définir KO

`KO` exige une preuve démontrant la non-conformité.

Ne jamais convertir en `KO` :

```text
absent
inconnu
non supporté
illisible
```

sauf si l'absence elle-même constitue la violation.

### 7. Définir NA

`NA` s'applique quand les preuves disponibles ne permettent pas de conclure de manière fiable.

`NA` n'est jamais un synonyme de `KO`.

### 8. Définir la preuve

Structure de résultat attendue (cf. `Principe de preuve` du README) :

```json
{
  "rule_id": "BP-XX",
  "object_type": "...",
  "object": "...",
  "expected": "...",
  "actual": "...",
  "evidence": "...",
  "status": "OK|KO|NA"
}
```

### 9. Définir l'agrégation

Par défaut :

```text
au moins une violation démontrée
→ KO

aucun KO + au moins une preuve requise non résolue
→ NA

tous les contrôles requis sont conclusifs et conformes
→ OK
```

Priorité par défaut : `KO > NA > OK`.

### 10. Définir les cas limites

Envisager, quand pertinent :

- fichiers absents ;
- TMDL malformé ;
- PBIR inconnu ;
- modèle vide ;
- noms entre guillemets (caractères spéciaux) ;
- objets masqués ;
- objets calculés ;
- violations multiples ;
- parsing partiel ;
- différences de version Power BI.

## Structure BP-XX attendue

Générer les algorithmes en suivant le gabarit réellement utilisé dans `01_ALGORITHMES/` (ne pas s'en écarter, ne pas inventer une structure différente) :

```text
# BP-XX — Nom

## 1. Objectif de la bonne pratique
## 2. Emplacement des fichiers concernés (sources TMDL/PBIR)
## 3. Élément(s) / propriété(s) à contrôler
## 4. Règle(s) d'évaluation (table Situation → Statut → Interprétation)
## 5. Parcours complet du modèle (ne jamais s'arrêter à la première anomalie)
## 6. Détection robuste / normalisation
## 7. Pseudo-code détaillé
## 8. Calcul du statut global (priorité KO > NA > OK)
## 9. Structure du résultat (exemples JSON OK et KO)
## 10. Message présenté à l'utilisateur (exemples OK et KO)
## 11. Conditions empêchant un faux OK
## 12. Résumé de la règle (pseudo-algorithme condensé)
## Annexe — Schéma de flux (optionnel)
```

Certaines règles ajoutent des sections spécifiques (ex. BP-01 ajoute une section sur le rôle structurel des tables) : c'est acceptable tant que le squelette ci-dessus reste respecté dans son ensemble.

## Règle fondamentale

Ne jamais exiger un raisonnement par agent/LLM quand un parsing déterministe suffit.

Le nom de fichier Python attendu en aval est `bp_xx.py`, et le test `test_bp_xx.py` (cf. section `Convention des règles` du README) — le garder à l'esprit pour que l'algorithme reste directement mappable.
