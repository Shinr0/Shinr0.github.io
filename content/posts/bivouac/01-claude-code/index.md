---
title: "Bivouac #1 — Construire sa plateforme avec Claude Code, sans dérive ni facture surprise"
date: 2026-11-16T09:00:00+01:00
weight: 2
description: >
  Un agent IA code vite. Le plus dur est de le garder dans le périmètre et de maîtriser ce qu'il
  coûte. Règles écrites, garde-fous testés, coût mesuré : le cadre mis en place sur Bivouac,
  avec ce qui a marché et ce qui a raté.
tags:
  - Platform engineering
  - Claude Code
  - IA
  - DevOps
  - Supply chain
categories:
  - Série Bivouac
menu:
  sidebar:
    name: "#1 Construire avec Claude Code"
    identifier: bivouac-01
    parent: bivouac
    weight: 2
---

Je développe [Bivouac](https://github.com/Shinr0/bivouac) avec Claude Code, l'agent de code
d'Anthropic. Qu'il sache écrire du Terraform, ce n'est plus vraiment la question. Ce qui
m'intéresse, ce sont les questions qu'on se pose pour toute nouvelle recrue qui a les droits
d'écriture : comment l'empêcher de sortir du périmètre, de casser ou de facturer quelque chose sans
mon accord, et combien elle coûte.

Voici ce que j'ai mis en place pendant la phase 1.

## 1. Des règles écrites

L'agent travaille à partir de trois sources :

- `PLAN.md` : la spécification, découpée en phases avec un critère d'acceptation chacune ;
- `CLAUDE.md` : les règles du projet (une phase à la fois, versions épinglées et vérifiées dans la
  doc officielle, aucun secret, label obligatoire sur les ressources GCP, jamais de
  `terraform apply` sans demande explicite) ;
- `docs/adr/` : une décision par fichier, avec ce qui a été écarté et pourquoi.

Concrètement, l'agent ne choisit pas une version d'outil de mémoire : il la vérifie dans le
registre officiel et lit la documentation correspondant à ce tag.

Les ADR servent aussi à changer d'avis proprement, ce qui arrive souvent dans un labo. Un ADR n'est
jamais réécrit ni supprimé : une décision révisée donne un nouvel ADR, et l'ancien ne change que sa
ligne de statut. L'historique des essais reste lisible dans `docs/adr/`.

## 2. Des garde-fous exécutables, et testés

Une règle écrite est respectée la plupart du temps. Pour ce qui doit l'être à chaque fois, Claude
Code lit un fichier `.claude/settings.json` versionné dans le dépôt :

```json
{
  "permissions": {
    "ask": [
      "Bash(terraform apply:*)", "Bash(terraform destroy:*)",
      "Bash(make up:*)", "Bash(make down:*)", "Bash(make bootstrap:*)",
      "Bash(git push:*)", "Bash(gh pr merge:*)"
    ]
  },
  "hooks": {
    "PreToolUse": [
      { "matcher": "Bash",
        "hooks": [{ "type": "command",
                    "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/guard-gcloud.sh" }] }
    ]
  }
}
```

Tout ce qui crée, détruit, facture ou publie me demande une confirmation. Le hook, lui, reçoit
chaque commande shell de l'agent avant exécution et refuse tout appel à `gcloud` qui ne passe pas
par la configuration isolée du projet.

## 3. Ce que coûte l'agent

### Où part l'argent

Le modèle n'a pas de mémoire. À chaque requête, Claude Code lui renvoie tout le contexte : prompt
système, outils, `CLAUDE.md`, historique, fichiers lus et sorties de commandes. Il y a donc trois
lignes sur la facture, à des prix très différents (par million de tokens) :

| | Opus 5.5 | Sonnet 5.5 |
|---|---|---|
| Contexte relu depuis le cache | 0,20 $ | 0,10 $ |
| Contexte neuf (écrit en cache, durée d'une heure) | 8 $ | 4 $ |
| Sortie (réponse et réflexion du modèle) | 20 $ | 10 $ |

J'ai mesuré la session qui a servi à écrire cet article : 29 requêtes à Opus 5.5, coût recalculé
au prix catalogue (avec un abonnement, c'est la part du forfait consommée) :

| Poste | Tokens | Coût | Part |
|---|---|---|---|
| Contexte relu depuis le cache | 2 283 538 | 0,46 $ | 25 % |
| Contexte neuf | 81 442 | 0,65 $ | 35 % |
| Sortie | 35 954 | 0,72 $ | 39 % |

Deux enseignements. Le contexte relu représente 63 fois plus de tokens que la sortie, mais le cache
le rend bon marché : sans lui, ces 2,4 millions de tokens auraient coûté environ 9,40 `$` au lieu de
1,83 `$`. Et une fois le cache en place, la sortie devient le premier poste : 1,5 % des tokens, 39 %
du coût.

D'où trois leviers, dans cet ordre.

### 1. Ne pas casser le cache

- Choisir le modèle en début de session et ne plus en changer : chaque modèle a son propre cache.
  Sonnet pour exécuter, Opus pour concevoir (le réglage `opusplan` fait ce partage tout seul).
- Enchaîner plutôt qu'étaler : passé la durée de vie du cache, tout le contexte est repayé au prix
  fort.
- Modifier `CLAUDE.md` en cours de session ne casse rien : la nouvelle version est prise en compte
  au prochain `/clear`.

### 2. Faire écrire moins

- Régler l'effort (`/effort`) selon la tâche : la réflexion du modèle est facturée comme de la
  sortie, même quand elle n'est pas affichée.
- Exécuter avec Sonnet : chaque token de sortie coûte deux fois moins qu'avec Opus.
- Préférer des modifications ciblées à des fichiers réécrits en entier, et des réponses courtes.

### 3. Faire lire moins

Chaque fichier lu est payé une fois au prix fort, puis relu à chaque requête jusqu'à la fin de la
session.

- **Un `CLAUDE.md` court.** Ma première version demandait de lire `PLAN.md` (416 lignes, 26 Ko)
  avant toute tâche. Le `CLAUDE.md` actuel fait 28 lignes et pointe vers la section utile du plan.
- **Le reste à la demande.** Les routines (créer un ADR, clore une phase, écrire cet article) sont
  des skills : seule leur description d'une ligne est chargée en permanence, pas leurs 5,2 Ko de
  détail. À partir de la phase 2, chaque dossier aura son `CLAUDE.md`, chargé seulement quand
  l'agent y travaille.
- **Des lectures interdites.** Six règles `permissions.deny` excluent `.terraform/`, les states, le
  fichier de lock, les `*.tfvars` et `.env`. Elles évitent des fichiers générés sans intérêt et
  réduisent le risque de voir un secret local arriver dans le contexte, sans le supprimer : elles
  bloquent `cat` sur ces fichiers, pas un `grep -r` ni un script qui les ouvre lui-même.
- **Des sorties de commandes compactes.** Dans ma configuration personnelle, un hook fait passer
  les commandes shell de l'agent par RTK, qui compacte leur sortie. D'après `rtk gain`, la sortie
  de 1 101 commandes a été réduite de 21,7 % en tokens. Pour la même raison, le projet n'utilise
  aucun serveur MCP : `gh`, `terraform` et `make` suffisent.
- **Les lectures volumineuses dans un sous-agent.** Pour vérifier ce que cet article dit de Claude
  Code, un sous-agent sur Haiku a lu la documentation officielle. Ma session n'a reçu que son
  rapport, et ces lectures ont coûté quelques centimes.
- **Une session par tâche**, `/clear` entre deux, et le mode plan pour démarrer une phase : une
  mauvaise direction corrigée sur le plan évite de réécrire puis relire des fichiers.

### Mesurer

`/context` montre ce qui occupe la fenêtre, `/usage` les tokens par poste. Le tableau ci-dessus
vient du journal de session de Claude Code, et il m'a appris quelque chose : je pensais que le
contexte relu était le premier poste, c'était la sortie.

## 4. Une revue IA en local

Avant chaque push, `make test` doit passer, puis je lance `/code-review`, une commande intégrée à
Claude Code qui relit le diff de la branche à la recherche de bugs. Pour un dépôt où je suis seul à
pousser, ça suffit.

## 5. Supply chain : ce que l'agent installe

Une action GitHub, un plugin, une skill ou un paquet exécutent du code avec mes droits, sur ma
machine ou dans ma CI. S'il est piégé, il voit mes fichiers et mes secrets. Et c'est souvent
l'agent qui propose de les ajouter.

Trois règles, dont les deux premières sont écrites dans `CLAUDE.md` :

- **Épingler par SHA.** Une étiquette comme `v7` peut être déplacée vers un autre code, pas un SHA
  de commit : `actions/checkout@3d3c42e… # v7.0.1`.
- **Attendre 7 jours** avant d'adopter une nouvelle version : une version piégée est généralement
  repérée et retirée avant.
- **Vérifier la provenance** : le paquet pointe vers le dépôt officiel, son nom est exact, son
  mainteneur est identifié. Un agent peut proposer un nom plausible qui n'est pas le bon.

## Ce que je dirais à un client

Un agent de code, c'est une recrue très rapide et sans mémoire. On l'encadre comme une recrue :

| Pour un humain | Pour un agent | Dans ce dépôt |
|---|---|---|
| Onboarding | Règles et plan écrits | `CLAUDE.md`, `PLAN.md`, ADR |
| Moindre privilège | Confirmation avant tout ce qui détruit ou facture | `permissions.ask` |
| Contrôles automatiques | Hooks testés, sans les prendre pour une frontière de sécurité | `guard-gcloud.sh`, `make test` |
| Documentation | Courte, chargée au bon moment | `CLAUDE.md`, skills |
| Revue de code | Revue du diff avant push | `/code-review` |
| Budget | Mesurer, garder le cache, limiter la sortie | `/usage`, `/effort` |

Le coût d'un agent ne se règle pas avec un plafond posé après coup. Il se mesure, puis se réduit
par l'usage : un cache préservé, moins de sortie, moins de lectures.

Le prochain épisode attaque le Resource Plane : `make up`, `make down` et la chasse aux ressources
orphelines, avec les durées et les coûts réels.
