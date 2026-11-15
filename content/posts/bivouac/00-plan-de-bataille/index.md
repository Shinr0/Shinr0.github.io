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
make up     # un projet GCP vide devient une plateforme en self-service, en quelques minutes
            # … on teste un concept, on mesure, on casse, on recommence …
make down   # tout disparaît — et un script échoue s'il reste un seul disque facturé
```

Bivouac sert à **rechercher et à tester** : comparer des approches sur du réel plutôt que sur des
slides, mesurer ce qu'elles coûtent, et en garder une trace écrite (une décision documentée par
choix). Il sert aussi de démonstration devant un client : vingt minutes avant le rendez-vous, et
plus rien sur la facture le lendemain.

Je le construis avec un agent IA, **Claude Code**, encadré par des règles et des garde-fous que je
publie avec le code. Ce premier épisode pose le décor : d'où je pars, comment j'ai choisi les
outils, et ce que la série va construire, un plan à la fois. Tout est public dans le dépôt
[`platform-project`](https://github.com/Shinr0/platform-project).

---

## Pourquoi repartir de zéro

La [première version de ce projet](https://github.com/Shinr0/platform-project/tree/archive/v1-crossplane-forge) provisionnait
des VM Compute Engine avec Crossplane, déclenchées par un portail HTML et des GitHub Actions. Elle
fonctionnait, mais elle avait trois défauts que je n'accepterais pas chez un client :

- **un token GitHub dans le navigateur** ;
- **pas de garde-fous** : rien n'empêchait une demande non conforme d'arriver jusqu'au cloud ;
- **pas de fin de vie** : rien ne garantissait qu'un `destroy` ne laisse pas d'IP ou de disque
  facturé derrière lui.

La v1 est archivée dans une branche du dépôt. La v2 part d'un cahier des charges écrit avant la
première ligne de code, avec des décisions tracées dans des
[ADR](https://github.com/Shinr0/platform-project/tree/main/docs/adr).

---

## Le landscape : 5 plans, ~210 outils, et une case vide

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

Et un détail m'a frappé : il existe une catégorie **« Copilot/Agent/LLM »**… et aucun outil n'y
est rangé. L'IA est partout dans les discours sur le platform engineering, mais sa place reste à
dessiner. Ma première réponse est pragmatique : avant de mettre de l'IA *dans* la plateforme, je
m'en sers pour la **construire** — et je montre comment la garder sous contrôle.

---

## Ma règle : le plus petit chemin qui traverse les 5 plans

Plutôt que « quel est le meilleur outil ? », je me pose la question : **quel est le minimum, dans
chaque plan, pour qu'une équipe obtienne quelque chose d'utile de bout en bout ?**

| Plan | Mes choix | Dans le landscape ? |
|---|---|---|
| Developer Control Plane | GitHub · API de plateforme **kro** · portail FastAPI + HTMX | GitHub oui ; kro non |
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
  Google, sait créer ~200 types de ressources GCP depuis Kubernetes ; c'est la couche primitive.
  **kro** compose le catalogue par-dessus et crée les ressources **dans l'ordre de leurs
  dépendances**. Des équipes l'utilisent ainsi en production : les deux s'empilent au lieu de
  se concurrencer.

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

Et ce que j'exclus volontairement : **Backstage** (trop lourd pour une plateforme qui vit deux
heures), les **orchestrateurs de plateforme** commerciaux, le **multi-cluster** et les **GPU**.
L'IA *intégrée* à la plateforme — un accès LLM par équipe et un assistant qui ouvre des pull
requests — est **reportée en fin de série**, en option : elle n'a de sens qu'une fois le socle solide.

---

## L'architecture cible

{{< mermaid >}}
flowchart LR
  subgraph dev["Developer Control Plane"]
    PORTAL["Portail\nFastAPI + HTMX"]
    GH["GitHub\nclaims/"]
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

  PORTAL -->|"pull request"| GH
  GH --> CI
  GH -->|"sync"| ARGO
  ARGO --> KRO
  KRO --> TEAM
  KRO --> KCC
  KCC --> GCP
  TEAM --> COST
{{< /mermaid >}}

Le flux d'une demande tient en une phrase : **une équipe ouvre une pull request, Kyverno la valide
en CI puis à l'admission, Argo CD la synchronise, kro crée les ressources Kubernetes et les objets Config
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

La phase 1 est terminée : squelette du dépôt, 21 ADR, un `Makefile` qui expose toutes les
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
| 5 | Developer Control | kro + Config Connector : objets cloud et Kubernetes en self-service |
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
ressource qui tourne, un coût qui s'affiche. Le portail n'est qu'un client de ce chemin — on peut
le changer plus tard, pas le chemin.
