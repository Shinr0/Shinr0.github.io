---
title: "Bivouac #0 — Un camp de base pour explorer le platform engineering sur GCP"
date: 2026-11-15T09:00:00+01:00
description: >
  Bivouac est un laboratoire pour rechercher et tester des concepts de platform engineering sur
  GCP : une plateforme interne complète, montée en quelques minutes et démontée sans laisser de
  trace. Point de départ : le landscape de platformengineering.org, ses 5 plans, et un outil par plan.
tags:
  - Platform engineering
  - GCP
  - Kubernetes
  - GitOps
  - FinOps
  - Claude Code
categories:
  - Série Bivouac
menu:
  sidebar:
    name: "#0 Le plan de bataille"
    identifier: bivouac-00
    parent: bivouac
    weight: 0
---

Tester un concept de platform engineering — une API de self-service, une politique de sécurité,
un modèle de coûts par équipe — demande une vraie plateforme. Et une plateforme interne de
développement (IDP), ça coûte cher à garder allumée : des clusters qui tournent entre deux essais,
des ressources cloud oubliées, une facture qui grimpe pour un labo.

Alors j'ai monté **Bivouac** : un camp de base pour explorer le platform engineering sur GCP.
Comme un bivouac en montagne, il se monte vite, on n'y emporte que l'essentiel, et on repart sans
laisser de trace.

```bash
make up     # un projet GCP vide devient une plateforme en self-service
            # … on teste un concept, on mesure, on casse, on recommence …
make down   # tout disparaît — et un script échoue s'il reste un seul disque facturé
```

Bivouac sert à **rechercher et à tester** : comparer des approches sur du réel plutôt que sur des
slides, mesurer ce qu'elles coûtent, et en garder une trace écrite (une décision documentée par
choix). Il sert aussi de démonstration devant un client : montée juste avant le rendez-vous (objectif :
moins de vingt minutes, mesuré à l'épisode 2), et plus rien sur la facture le lendemain.

Je le construis avec un agent IA, **Claude Code**, encadré par des règles et des garde-fous que je
publie avec le code. Ce premier épisode pose le décor : d'où je pars, comment j'ai choisi les
outils, et ce que la série va construire, un plan à la fois. Tout est public dans le dépôt
[`bivouac`](https://github.com/Shinr0/bivouac).

---

## Pourquoi repartir de zéro

La [première version de ce projet](https://github.com/Shinr0/bivouac/tree/archive/v1-crossplane-forge) provisionnait
des VM Compute Engine avec Crossplane, déclenchées par un portail HTML et des GitHub Actions. Elle
fonctionnait, mais elle avait trois défauts que je n'accepterais pas chez un client :

- **un token GitHub dans le navigateur** ;
- **pas de garde-fous** : rien n'empêchait une demande non conforme d'arriver jusqu'au cloud ;
- **pas de fin de vie** : rien ne garantissait qu'un `destroy` ne laisse pas d'IP ou de disque
  facturé derrière lui.

La v1 est archivée dans une branche du dépôt. La v2 part d'un cahier des charges écrit avant la
première ligne de code, avec des décisions tracées dans des
[ADR](https://github.com/Shinr0/bivouac/tree/main/docs/adr).

---

## Le landscape : 5 plans, ~210 outils

[Le landscape de platformengineering.org](https://platformengineering.org/platform-tooling) classe
les outils d'une IDP en **5 plans** :

| Plan | La question à laquelle il répond |
|---|---|
| **Developer Control Plane** | Comment un développeur exprime-t-il ce qu'il veut ? |
| **Integration & Delivery Plane** | Comment une demande devient-elle une ressource déployée ? |
| **Resource Plane** | Qu'est-ce qui tourne réellement ? |
| **Observability Plane** | Qu'est-ce que je vois, et combien ça coûte ? |
| **Security Plane** | Qu'est-ce qui est permis, et avec quelle identité ? |

En le parcourant (mi-novembre 2026), j'ai compté environ **210 fiches outils** réparties dans
**38 catégories**. Le piège est évident : on peut passer des semaines à comparer des outils sans
jamais rien livrer.

L'IA est partout dans les discours sur le platform engineering, mais sa place reste à
dessiner. Ma première réponse est pragmatique : avant de mettre de l'IA *dans* la plateforme, je
m'en sers pour la **construire** — et je montre comment la garder sous contrôle.

---

## Ma règle : le plus petit chemin qui traverse les 5 plans

Plutôt que « quel est le meilleur outil ? », je me pose la question : **quel est le minimum, dans
chaque plan, pour qu'une équipe obtienne quelque chose d'utile de bout en bout ?**

| Plan | Mes choix | Dans le landscape ? |
|---|---|---|
| Developer Control Plane | GitHub · **référentiel d'équipes** au format Backstage · API de plateforme **kro** · portail FastAPI + HTMX | GitHub, Backstage oui ; kro non |
| Integration & Delivery | **Terraform** · GitHub Actions · **Argo CD** | oui, les trois |
| Resource Plane | **GKE** Standard zonal, nœuds spot · **Config Connector** pour les objets GCP des équipes | Kubernetes oui ; Config Connector non |
| Observability Plane | Prometheus / Grafana allégés · **OpenCost** · budget GCP | Prometheus, Grafana oui ; OpenCost non (Kubecost oui) |
| Security Plane | **Kyverno** · Google Secret Manager + External Secrets · **Workload Identity** | Kyverno, Secret Manager oui ; External Secrets non |

Un choix mérite d'être détaillé : **l'API de plateforme**. Une équipe doit pouvoir demander
« un espace de travail » et obtenir d'un coup des objets Kubernetes (namespace, quotas, droits)
**et** des objets cloud (un bucket, un compte de service GCP qui n'accède qu'à ce bucket).

J'ai comparé trois approches :

- **Helm** sait générer des manifestes, mais ce n'est pas une API : pas d'objet « demande » typé
  dans le cluster, pas de statut, et surtout **pas d'ordre** — une liaison IAM peut arriver avant
  le compte de service qu'elle référence, et tout le monde attend que ça converge.
- **Crossplane**, que j'avais utilisé en v1 pour des VM, fait tout : composition et providers
  cloud. Mature et multi-cloud, mais c'est un écosystème entier de contrôleurs à maintenir, et son
  provider GCP n'est pas celui de Google.
- **kro au-dessus de Config Connector** sépare les rôles. **Config Connector**, l'opérateur de
  Google, crée et maintient des ressources GCP (buckets, comptes de service, IAM…) à partir
  d'objets Kubernetes ; c'est la couche primitive.
  **kro** compose le catalogue par-dessus et crée les ressources **dans l'ordre de leurs
  dépendances**. Ce modèle — l'opérateur du cloud comme couche primitive, kro comme catalogue —
  tourne déjà en production chez certaines équipes (sur AWS, avec l'équivalent ACK) : les deux
  s'empilent au lieu de se concurrencer.

J'ai retenu la troisième, natif GCP et au plus petit rayon d'impact, en connaissant ses limites :
kro est encore pré-stable (version épinglée, une seule définition validée avant d'en écrire
d'autres), il n'a pas de contrôle d'admission (Kyverno s'en charge), une demande bloquée nomme
rarement la ressource fautive, et il n'existe pas d'équivalent de `terraform plan`.

Le revers commun à toutes ces options : des ressources cloud créées par un contrôleur, c'est
exactement ce qui survit à un `terraform destroy` mal ordonné. D'où une règle : `make down`
supprime d'abord les demandes, **attend que Config Connector ait supprimé les ressources GCP**, et
seulement ensuite le cluster.

Quatre de mes choix n'apparaissent pas dans le landscape. C'est voulu, et chacun a son ADR :

- **kro** et **Config Connector** : ci-dessus.
- **OpenCost** est le cœur open source (CNCF) dont Kubecost est issu : suffisant pour attribuer
  un coût par équipe.
- **External Secrets** n'est qu'un pont : la source de vérité reste Google Secret Manager, qui,
  lui, est bien dans le landscape.

Et ce que j'exclus volontairement : le moteur **Backstage** (trop lourd pour une plateforme qui vit
deux heures — j'en garde le format de catalogue, voir plus bas), les **orchestrateurs de plateforme** commerciaux, le **multi-cluster** et les **GPU**.
L'IA *intégrée* à la plateforme — un accès LLM par équipe et un assistant qui ouvre des pull
requests — est **reportée en fin de série**, en option : elle n'a de sens qu'une fois le socle solide.

---

## Le référentiel d'équipes : à qui appartient quoi ?

Un outil de platform engineering ne sert à rien s'il ne sait pas **qui** est derrière chaque
demande. Quelles équipes existent ? Qui les manage, comment les joindre, qui est d'astreinte ?
Quelles applications opèrent-elles, sur quel socle technique ? À qui facturer ce bucket, à qui
demander avant de supprimer ce compte de service ?

Dans Bivouac, ce référentiel vit **dans Git**, dossier `catalog/`, un fichier par équipe et par
application. Pour une plateforme éphémère, c'est essentiel : le cluster disparaît à chaque
`make down`, le référentiel, lui, reste — versionné, relu en pull request comme le reste.

J'utilise le **format descripteur du catalogue Backstage**, devenu un standard de fait, sans faire
tourner Backstage. Une équipe (fictive) :

```yaml
apiVersion: backstage.io/v1alpha1
kind: Group
metadata:
  name: payments
  title: Équipe Paiements
  annotations:
    bivouac/manager: "Responsable produit Paiements"
    bivouac/chat-channel: "#team-payments"
    bivouac/on-call: payments-oncall
    bivouac/cost-center: CC-1042
spec:
  type: team
  profile:
    displayName: Équipe Paiements
    email: payments-team@example.com     # adresse de groupe, jamais personnelle
  parent: engineering                     # le rattachement hiérarchique
  children: []
```

Et une de ses applications, avec son socle technique :

```yaml
apiVersion: backstage.io/v1alpha1
kind: Component
metadata:
  name: checkout-api
  tags: [python, fastapi, postgresql]
  links:
    - url: https://runbooks.example.com/checkout-api
      title: Runbook
spec:
  type: service
  lifecycle: production
  owner: payments
  system: checkout
  dependsOn: [resource:payments-bucket]
```

Ce que le format ne prévoit pas — manager, canal de discussion, astreinte, centre de coût — passe
par des annotations préfixées `bivouac/`. Et le référentiel est **branché** sur la plateforme :

- une demande d'espace d'équipe doit citer une équipe qui existe dans `catalog/`, la CI le vérifie ;
- le label `team` posé sur chaque ressource Kubernetes et GCP relie ressources et coûts à l'équipe :
  OpenCost sait qui coûte quoi, et une ressource oubliée a un propriétaire ;
- le portail affiche une page par équipe : manager, contacts, applications, ressources, coûts.

Pourquoi ce format plutôt qu'un tableur, une CMDB ou une CRD dans le cluster ? Parce qu'il est
versionné, validable, compris par l'outil que beaucoup de clients adopteront un jour — un client
qui installe Backstage ingère `catalog/` tel quel — et qu'il survit à la plateforme.

### Et en production ?

Un dossier de fichiers YAML ne tient pas à l'échelle d'une entreprise : il faut chercher, croiser,
filtrer, donner des droits, ouvrir l'outil à des non-développeurs. Il faut donc **une base de
données** — mais pas comme source de vérité. Le bon modèle est hybride, chaque information venant
de là où elle est juste :

| Information | Source de vérité |
|---|---|
| Propriété : à quelle équipe appartient une application, son socle, ses dépendances | **Git**, dans un fichier au format Backstage **dans le dépôt de chaque application** |
| Personnes : membres, managers, rattachements | **L'annuaire** (Google Workspace, Cloud Identity, Entra ID) ou le SIRH — jamais Git |
| Astreinte | L'outil d'astreinte (PagerDuty, Opsgenie…) |
| Données vivantes : déploiements, coûts, conformité | Collectées automatiquement par la plateforme |
| Vue d'ensemble : recherche, requêtes, portail | **Une base de données**, alimentée par les sources ci-dessus |

La base est un **index** : reconstruite à partir des sources, jamais éditée à la main. Une base
qu'on remplit à la main, c'est une CMDB — et elles finissent toutes de la même façon : personne ne
la met à jour, plus personne n'y croit. C'est exactement ainsi que fonctionne Backstage : des
fichiers dans les dépôts, ingérés dans PostgreSQL.

Dans Bivouac, je simplifie : un dossier `catalog/` central, des équipes fictives, pas de base. Pour
un labo, c'est suffisant ; chez un client, c'est le modèle hybride.

---

## L'architecture cible

{{< mermaid >}}
flowchart LR
  subgraph dev["Developer Control Plane"]
    PORTAL["Portail\nFastAPI + HTMX"]
    GH["GitHub\nclaims/"]
    CAT["Référentiel\ncatalog/ (Git)"]
  end

  subgraph delivery["Integration & Delivery"]
    CI["GitHub Actions\n+ Kyverno CLI"]
    ARGO["Argo CD"]
    KRO["kro"]
  end

  subgraph resource["Resource Plane — GKE spot"]
    TEAM["Espaces d'équipe\nnamespace, quotas, RBAC"]
    KCC["Config Connector"]
    GCP["Objets GCP\nbucket, compte de service"]
  end

  subgraph obs["Observability"]
    COST["OpenCost"]
  end

  CAT --> PORTAL
  CAT -->|"équipe propriétaire"| CI
  PORTAL -->|"pull request"| GH
  GH --> CI
  GH -->|"sync"| ARGO
  ARGO --> KRO
  KRO --> TEAM
  KRO --> KCC
  KCC --> GCP
  TEAM --> COST
{{< /mermaid >}}

Le flux d'une demande tient en une phrase : **une équipe déclarée dans le référentiel ouvre une
pull request, Kyverno la valide en CI puis à l'admission, Argo CD la synchronise, kro crée les ressources Kubernetes et les objets Config
Connector qui deviennent des ressources GCP, OpenCost en mesure le coût**. Personne n'écrit directement dans le cluster.

---

## Les principes non négociables

- **Tout est code** : Terraform pour GCP, GitOps pour tout ce qui tourne dans le cluster.
- **Zéro secret dans Git, zéro clé de compte de service** : Workload Identity partout.
- **Rien ne survit à `make down`**, hors un socle persistant quasi gratuit (bucket de state,
  secret, budget). Toute ressource GCP porte un label qui permet de traquer les orphelins.
- **Pas de PVC, pas de LoadBalancer, pas d'IP statique** : ce sont les ressources créées par des
  contrôleurs Kubernetes qui survivent le plus souvent à un `terraform destroy`. Seule exception :
  les objets GCP des équipes, choisis rapides et quasi gratuits, et supprimés avant le cluster.
- **Coûts bornés par construction** : nœuds spot, cluster zonal couvert par le crédit gratuit
  GKE, pas de GPU.
- **L'agent IA qui code travaille sous garde-fous** : règles écrites, actions sensibles soumises à
  confirmation, revues automatiques à coût plafonné. C'est le sujet de l'épisode 1.

---

## Où en est le dépôt

La phase 1 est terminée : squelette du dépôt, 16 ADR, un `Makefile` qui expose toutes les
commandes de la série, le **socle persistant** en Terraform (APIs, bucket de state versionné,
secret vide, budget avec alertes à 50 / 90 / 100 %), et l'outillage pour développer avec Claude
Code. La CI vérifie le code Terraform et les garde-fous à chaque push.

Prochains épisodes :

| # | Plan | Sujet |
|---|---|---|
| 1 | Outillage | Construire sa plateforme avec Claude Code, sans dérive ni facture surprise |
| 2 | Resource | `make up`, `make down`, zéro orphelin — chiffres réels |
| 3 | Integration & Delivery | GitOps : Terraform n'installe qu'une seule chose |
| 4 | Security | Zéro secret, zéro clé |
| 5 | Developer Control | Référentiel d'équipes + kro + Config Connector : objets cloud et Kubernetes en self-service |
| 6 | Observability | Combien coûte une équipe ? |
| 7 | Developer Control | Un portail sans Backstage |
| 8 | Tous | Bilan, chiffres, et version locale sans cloud |
| bonus | Resource + Developer Control | L'IA dans la plateforme : LLM par équipe et assistant |

Chaque épisode ne sera publié qu'une fois la brique construite et **mesurée** : durées, coûts,
captures — pas d'estimation.

---

## Ce que je dirais à un client

Ne commencez pas par le portail. Commencez par **le plus petit chemin qui traverse les cinq
plans** : une demande en Git, une politique qui la valide, un outil qui la réconcilie, une
ressource qui tourne, un coût qui s'affiche. Le portail n'est qu'une étape de ce chemin — on peut
le changer plus tard, pas le socle derrière.
