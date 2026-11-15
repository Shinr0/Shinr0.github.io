---
title: "IDP éphémère #0 — Une plateforme qui s'autodétruit : le plan de bataille"
date: 2026-11-15T09:00:00+01:00
description: >
  Je construis une Internal Developer Platform complète sur GCP, avec de l'IA par-dessus, qui
  n'existe que le temps d'une démo. Point de départ : le landscape de platformengineering.org,
  ses 5 plans, et un outil par plan.
tags:
  - Platform engineering
  - GCP
  - Kubernetes
  - GitOps
  - FinOps
  - IA
categories:
  - Série IDP éphémère
menu:
  sidebar:
    name: "#0 Le plan de bataille"
    identifier: idp-ephemere-00
    parent: idp-ephemere
    weight: 0
---

Une plateforme interne de développement (IDP), ça coûte souvent plus cher à **entretenir** qu'à
**héberger** : des clusters allumés en permanence, un portail que personne ne met à jour, des
ressources cloud dont plus personne ne connaît le propriétaire.

Alors je fais l'inverse : je construis une IDP complète **qui n'existe que le temps d'une démo**.

```bash
make up     # un projet GCP vide devient une plateforme en self-service
make down   # tout disparaît — et un script échoue s'il reste un seul disque facturé
```

Ce premier épisode pose le décor : d'où je pars, comment j'ai choisi les outils, et ce que la
série va construire, un plan à la fois. Tout est public dans le dépôt
[`platform-project`](https://github.com/Shinr0/platform-project).

---

## Pourquoi repartir de zéro

La [première version de ce projet]({{< ref "/posts/platform-engineering/index.md" >}}) provisionnait des VM
Compute Engine avec Crossplane, déclenchées par un portail HTML et des GitHub Actions. Elle
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
est rangé. L'IA est partout dans les discours sur le platform engineering, mais sa place *dans*
la plateforme reste à dessiner. C'est précisément l'un des deux sujets de cette série.

---

## Ma règle : le plus petit chemin qui traverse les 5 plans

Plutôt que « quel est le meilleur outil ? », je me pose la question : **quel est le minimum, dans
chaque plan, pour qu'une équipe obtienne quelque chose d'utile de bout en bout ?**

| Plan | Mes choix | Dans le landscape ? |
|---|---|---|
| Developer Control Plane | GitHub · API de plateforme **kro** · portail FastAPI + HTMX · **agent IA** | GitHub oui ; kro non (voisin : Crossplane) |
| Integration & Delivery | **Terraform** · GitHub Actions · **Argo CD** | oui, les trois |
| Resource Plane | **GKE** Standard zonal, nœuds spot · **Claude sur Vertex AI** derrière **LiteLLM** | Kubernetes oui ; Vertex AI et LiteLLM non |
| Observability Plane | Prometheus / Grafana allégés · **OpenCost** · budgets GCP et LLM | Prometheus, Grafana oui ; OpenCost non (Kubecost oui) |
| Security Plane | **Kyverno** · Google Secret Manager + External Secrets · **Workload Identity** | Kyverno, Secret Manager oui ; External Secrets non |

Une partie de mes choix n'apparaît pas dans le landscape. C'est voulu, et chacun a son ADR :

- **kro plutôt que Crossplane** pour l'API de plateforme : mes demandes composent des objets
  Kubernetes (namespace, quotas, accès LLM), pas des ressources cloud. kro fait ça avec un seul
  fichier par capacité ; Crossplane — que j'ai utilisé en v1 — reste le bon outil quand il faut
  exposer du cloud en self-service.
- **OpenCost** est le cœur open source (CNCF) dont Kubecost est issu : suffisant pour attribuer
  un coût par équipe.
- **External Secrets** n'est qu'un pont : la source de vérité reste Google Secret Manager, qui,
  lui, est bien dans le landscape.
- **Vertex AI + LiteLLM** remplissent la case vide : une API compatible OpenAI, des clés par
  équipe, des budgets plafonnés, et aucun GPU à maintenir.

Et ce que j'exclus volontairement : **Backstage** (trop lourd pour une plateforme qui vit deux
heures), les **orchestrateurs de plateforme** commerciaux, le **multi-cluster**, et — décision
récente — **les GPU et modèles auto-hébergés** : tout passe par Vertex AI.

---

## L'architecture cible

{{< mermaid >}}
flowchart LR
  subgraph dev["Developer Control Plane"]
    PORTAL["Portail\nFastAPI + HTMX"]
    AGENT["Assistant IA"]
    GH["GitHub\nclaims/"]
  end

  subgraph delivery["Integration & Delivery"]
    CI["GitHub Actions\n+ Kyverno CLI"]
    ARGO["Argo CD"]
    KRO["kro"]
  end

  subgraph resource["Resource Plane — GKE spot"]
    TEAM["Espaces d'équipe"]
    LLM["LiteLLM"]
    VERTEX["Vertex AI\n(Claude)"]
  end

  PORTAL -->|"pull request"| GH
  AGENT -->|"pull request\naprès confirmation"| GH
  GH --> CI
  GH -->|"sync"| ARGO
  ARGO --> KRO
  KRO --> TEAM
  KRO --> LLM
  LLM --> VERTEX
{{< /mermaid >}}

Le flux d'une demande tient en une phrase : **une équipe (ou l'assistant IA) ouvre une pull
request, Kyverno la valide en CI puis à l'admission, Argo CD la synchronise, kro crée les
ressources**. Personne — ni humain, ni IA — n'écrit directement dans le cluster.

---

## Deux volets IA, une seule règle

1. **LLM-as-a-Service** : une équipe demande un accès à Claude par un simple fichier YAML. Elle
   reçoit une clé avec un budget mensuel plafonné, sans qu'aucun compte ne soit créé à la main.
2. **Un assistant de plateforme** : un agent en langage naturel qui aide à formuler la demande.
   Il peut tout lire, mais il n'a qu'un seul droit d'écriture : **ouvrir une pull request**,
   après confirmation explicite de l'utilisateur.

C'est, à mon sens, la bonne place de l'IA dans une IDP : **dans le Developer Control Plane, en
amont de la revue**, pas derrière un accès admin au cluster.

---

## Les principes non négociables

- **Tout est code** : Terraform pour GCP, GitOps pour tout ce qui tourne dans le cluster.
- **Zéro secret dans Git, zéro clé de compte de service** : Workload Identity partout.
- **Rien ne survit à `make down`**, hors un socle persistant quasi gratuit (bucket de state,
  secret, budget). Toute ressource GCP porte un label qui permet de traquer les orphelins.
- **Pas de PVC, pas de LoadBalancer, pas d'IP statique** : ce sont les ressources créées par des
  contrôleurs Kubernetes qui survivent le plus souvent à un `terraform destroy`.
- **Coûts bornés par construction** : nœuds spot, cluster zonal couvert par le crédit gratuit
  GKE, pas de GPU, budgets LLM par équipe.

---

## Où en est le dépôt

La phase 1 est terminée : squelette du dépôt, 17 ADR, un `Makefile` qui expose toutes les
commandes de la série, et le **socle persistant** en Terraform (APIs, bucket de state versionné,
secret vide, budget avec alertes à 50 / 90 / 100 %). La CI vérifie `terraform fmt` et
`validate` à chaque push.

Prochains épisodes :

| # | Plan | Sujet |
|---|---|---|
| 1 | Resource | `make up`, `make down`, zéro orphelin — chiffres réels |
| 2 | Integration & Delivery | GitOps : Terraform n'installe qu'une seule chose |
| 3 | Security | Zéro secret, zéro clé |
| 4 | Developer Control | Une API de plateforme avec kro, validée par Kyverno |
| 5 | Resource (IA) | LLM-as-a-Service avec budget |
| 6 | Observability | Combien coûte une équipe ? |
| 7 | Developer Control | Un portail sans Backstage |
| 8 | Developer Control (IA) | L'agent qui n'a le droit que d'ouvrir une PR |
| 9 | Tous | Bilan, chiffres, et version locale sans cloud |

Chaque épisode ne sera publié qu'une fois la brique construite et **mesurée** : durées, coûts,
captures — pas d'estimation.

---

## Ce que je dirais à un client

Ne commencez pas par le portail. Commencez par **le plus petit chemin qui traverse les cinq
plans** : une demande en Git, une politique qui la valide, un outil qui la réconcilie, une
ressource qui tourne, un coût qui s'affiche. Le portail n'est qu'un client de ce chemin — on peut
le changer plus tard, pas le chemin.
