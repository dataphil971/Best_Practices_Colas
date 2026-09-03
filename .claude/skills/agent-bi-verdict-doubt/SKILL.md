---
name: agent-bi-verdict-doubt
description: Soumettre à une revue adverse toute affirmation d'Agent BI avant qu'elle ne tienne — un verdict OK/KO/NA, un gain de performance, une couverture annoncée, une conclusion de revue. À utiliser avant de figer un statut de règle, avant de fermer une revue BP-XX, et chaque fois qu'une conclusion est confiante mais non vérifiée.
---

# Agent BI Verdict Doubt

## Mission

Une conclusion confiante n'est pas une conclusion exacte.

Ce skill matérialise un examinateur indépendant, chargé de **chercher la
faille**, avant qu'une affirmation d'Agent BI ne soit retenue.

Il ne remplace ni `agent-bi-rule-review` (cohérence Algorithme / Python /
Tests), ni `agent-bi-context-review` (qualification d'un candidat). Il
intervient en amont des deux, sur la question qu'aucun des deux ne pose :
**cette affirmation est-elle démontrée, ou seulement plausible ?**

## Pourquoi

Le risque central d'Agent BI n'est pas de manquer une non-conformité. C'est
d'en **affirmer une qui n'existe pas**, ou de déclarer conforme ce qui n'a pas
été contrôlé. Un `KO` infondé fait perdre la confiance dans les 36 autres
règles ; un `OK` infondé est pire, il rassure à tort.

Deux occurrences réelles dans ce dépôt :

```text
BP-32 rendait OK sur les rapports au format legacy sans avoir parsé
      un seul visuel — un faux OK, contraire à sa propre spécification.

Un lru_cache a été présenté comme un gain de performance mesuré.
      Il ne l'était pas. La mesure a montré aucun effet ; le vrai coût
      était ailleurs.
```

Les deux étaient des conclusions confiantes que personne n'avait attaquées.

## Quand l'appliquer

Appliquer à toute affirmation qui :

- fait passer une règle de `NA` à `OK` ou à `KO` ;
- élargit ou restreint le périmètre d'une règle (hors périmètre, exclusion) ;
- modifie la sémantique d'un statut ou l'agrégation du statut global ;
- annonce un chiffre : gain de performance, taux de couverture, nombre de
  constats, nombre de tests ;
- affirme le comportement d'un format Power BI ;
- conclut qu'un problème est résolu.

Ne pas appliquer à : un renommage, une correction de typo, une reformulation de
message, une demande explicite et sans ambiguïté de l'utilisateur.

## Déroulé

### 1. ÉNONCER

Formuler l'affirmation en deux ou trois lignes, et dire ce qu'elle engage.

```text
Affirmation : ...
Ce qu'elle engage : quel statut, quelle règle, quel projet
```

### 2. EXTRAIRE

Isoler ce qui doit être examiné — le code, le constat, la mesure — **en
retirant le raisonnement qui y a mené et la conclusion**.

L'examinateur doit voir la pièce, pas le plaidoyer.

### 3. DOUTER

Soumettre la pièce extraite avec une consigne adverse :

```text
Cherche ce qui cloche. Ne valide pas.
```

Ne jamais transmettre l'affirmation de l'étape 1 : elle oriente l'examinateur
vers l'accord.

Questions à couvrir systématiquement :

```text
Sur quelle preuve exacte repose ce statut ?
Que produit cette règle si le fichier est absent, vide, malformé ?
Que produit-elle sur l'autre sérialisation (PBIR vs legacy, TMDL vs BIM) ?
Un OK peut-il sortir sans qu'aucun objet ait été réellement contrôlé ?
Un NA a-t-il été rendu là où une preuve existait ?
Le chiffre annoncé a-t-il été mesuré, ou estimé ?
```

### 4. RÉCONCILIER

Classer chaque objection, par ordre de priorité :

```text
1. CONTRAT MAL LU      l'algorithme dit autre chose que le code
2. ACTIONNABLE         défaut réel, à corriger avant de conclure
3. ARBITRAGE           choix défendable, à écrire explicitement
4. BRUIT               à écarter, sans y revenir
```

Une objection de niveau 1 ou 2 interdit de retenir l'affirmation en l'état.

### 5. ARRÊTER

S'arrêter dès que les objections deviennent du bruit, après trois cycles, ou
sur décision explicite de l'utilisateur. Ne jamais boucler indéfiniment : au
troisième cycle, remonter la question plutôt que d'insister.

## Le test du faux OK

Contrôle minimal à passer avant tout `OK`, sur toute règle :

```text
Combien d'objets cette règle a-t-elle réellement examinés ?
Si la réponse est zéro, le statut ne peut pas être OK.
```

Un `OK` sans objet examiné est un `NA` déguisé. C'est la forme exacte du défaut
de BP-32, et elle est mécaniquement détectable.

## Comportements interdits

Ne jamais :

- transmettre sa propre conclusion à l'examinateur ;
- traiter l'absence d'objection comme une preuve de justesse ;
- annoncer un chiffre qu'on n'a pas mesuré, ni le présenter comme mesuré ;
- lever un doute en réduisant le périmètre de l'affirmation sans le dire ;
- convertir une objection non résolue en arbitrage pour pouvoir conclure ;
- valider une conclusion parce que les tests passent, quand les tests ont été
  écrits par la même passe que le code.

## Sortie attendue

```text
Affirmation
Objections retenues       niveau + description
Objections écartées       raison
Verdict                   RETENUE | À CORRIGER | NON DÉMONTRÉE
Ce qui reste non vérifié
```

`NON DÉMONTRÉE` est un résultat acceptable et doit être dit tel quel.

## Principe fondamental

```text
la confiance n'est pas une preuve — c'est ce qu'il reste quand on a cessé de vérifier
```
