---
title: "IDP éphémère #1 — Construire sa plateforme avec Claude Code, sans dérive ni facture surprise"
date: 2026-11-16T09:00:00+01:00
description: >
  Un agent IA code vite. Le vrai sujet, c'est de le garder sur les rails et de maîtriser ce qu'il
  coûte. Règles écrites, garde-fous exécutables, contexte économe, revues IA à coût
  borné : le cadre que j'ai mis en place sur ma plateforme, avec ce qui a marché et ce qui a raté.
tags:
  - Platform engineering
  - Claude Code
  - IA
  - DevOps
  - Supply chain
categories:
  - Série IDP éphémère
menu:
  sidebar:
    name: "#1 Construire avec Claude Code"
    identifier: idp-ephemere-01
    parent: idp-ephemere
    weight: 1
---

Ma plateforme est développée avec **Claude Code**, l'agent de code d'Anthropic. La question n'est
plus de savoir s'il sait écrire du Terraform — il sait. La question, c'est celle qu'on se pose pour
n'importe quel nouveau membre de l'équipe qui a les droits d'écriture :

- comment **l'empêcher de dériver** (anticiper, improviser, sortir du périmètre) ?
- comment **l'empêcher de casser ou de facturer** quelque chose sans accord ?
- comment **maîtriser ce qu'il coûte** en tokens, en local comme en CI ?

Voici le cadre mis en place dans
[`platform-project`](https://github.com/Shinr0/platform-project) pendant la phase 1, avec un
incident réel et un raté instructif.

---

## 1. Un cadre écrit avant la première ligne de code

L'agent lit trois choses à chaque session :

| Fichier | Rôle |
|---|---|
| `PLAN.md` | La spécification et des **phases** numérotées, avec un critère d'acceptation chacune |
| `CLAUDE.md` | Les **règles du projet** : une phase à la fois, versions épinglées vérifiées dans la doc officielle, aucun secret, label obligatoire sur les ressources GCP, jamais de `terraform apply` sans demande explicite |
| `docs/adr/` | Une **décision par fichier** : ce qui est choisi, ce qui est écarté, pourquoi |

L'effet est concret. Quand l'agent a écrit la couche Terraform de bootstrap, il n'a pas « choisi »
une version du provider Google : il a interrogé le registre Terraform, trouvé `8.10.0` publiée la
semaine précédente, et lu la documentation de la ressource `google_billing_budget` à ce tag
précis. C'est là qu'il a trouvé un piège documenté : avec des identifiants utilisateur, l'API
Billing Budgets renvoie un 403 sans `billing_project` et `user_project_override` dans le provider.

Le cadre écrit sert aussi à **changer d'avis proprement**. En cours de route, j'ai retiré les GPU,
puis reporté l'IA intégrée à la plateforme. Chaque fois : un nouvel ADR qui remplace l'ancien, le
plan révisé, le README aligné. Rien n'est réécrit en silence.

---

## 2. L'incident : le mauvais compte cloud

Avant tout déploiement, un doute m'a pris : l'agent n'allait-il pas utiliser le compte de mon
client ? Je lui ai demandé de vérifier. Résultat : la configuration `gcloud` globale de ma machine
— CLI **et** identifiants par défaut utilisés par Terraform — était bien connectée au **compte d'un
client**. L'agent, lui, ne l'avait pas signalé de lui-même. Je suis consultant ; c'est le cas de
beaucoup de postes de travail.

Rien n'avait encore été exécuté. Mais une seule règle dans `CLAUDE.md` (« utilise mon compte
perso ») n'aurait pas suffi : une règle écrite se respecte *en général*, un garde-fou s'applique
*toujours*. Trois couches ont été ajoutées :

1. **Une configuration `gcloud` isolée pour le projet**. Le `Makefile` exporte `CLOUDSDK_CONFIG`
   et `GOOGLE_APPLICATION_CREDENTIALS` vers un dossier dédié. La configuration globale (celle du
   client) n'est ni lue ni modifiée.
2. **Une vérification d'identité dans les scripts**. Avant toute action GCP, ils comparent le
   compte de la CLI *et* celui des identifiants applicatifs (via `tokeninfo`) au compte attendu,
   ainsi que le projet actif. Au moindre écart, ils s'arrêtent.
3. **Un hook Claude Code**. Avant chaque commande shell de l'agent, un script bloque tout appel à
   `gcloud` qui ne passe pas par la configuration isolée.

---

## 3. Des garde-fous exécutables… et testés

Claude Code lit un fichier `.claude/settings.json` **versionné dans le dépôt**. Deux mécanismes :

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

- `permissions.ask` : tout ce qui crée, détruit, facture ou publie exige **ma confirmation**, et
  cette liste est partagée avec le code, pas cachée dans ma configuration personnelle.
- le hook `PreToolUse` reçoit la commande en JSON et renvoie le code `2` pour la bloquer, avec un
  message qui explique à l'agent quoi faire à la place.

**Le raté.** La première version du hook cherchait le mot `gcloud` n'importe où dans la
commande. Quelques minutes plus tard, il a bloqué… le `git commit` de l'agent, parce que le message
de commit parlait de `gcloud`. Pire : la commande qui devait corriger le hook contenait elle aussi
le mot, et a été bloquée à son tour. L'agent a dû passer par ses outils d'édition de fichiers, que
le hook ne surveille pas.

La correction : ne détecter `gcloud` qu'en **position de commande** (début de ligne, après `;`,
`&&`, `|`, `$(`, `sudo`, `env`…). Et surtout, la leçon : **un garde-fou est du code, il se teste**.
`make test` rejoue désormais 12 cas — 6 doivent être bloqués, 6 autorisés, dont le fameux message
de commit — et la CI les exécute à chaque push.

---

## 4. Un contexte économe : chaque ligne se paie à chaque requête

Ce qui coûte avec un agent, ce n'est pas tant ce qu'il écrit que ce qu'il **relit**. À chaque
requête, il renvoie au modèle ses instructions, l'historique de la session et tout ce qu'il a lu.
Avant d'ajouter un outil, j'ai donc réduit ce qu'il porte en permanence.

**Un `CLAUDE.md` court et stable.** Ma première version disait : « Lire `PLAN.md` avant toute
tâche ». Or `PLAN.md` fait 22 Ko — environ 380 lignes relues au début de chaque session, même pour
corriger une faute de frappe. La version actuelle tient en 24 lignes : les règles non négociables,
les commandes, et un pointeur — « la phase en cours est dans le tableau Avancement du README ; ne
lis de `PLAN.md` que la section utile ». Et il change rarement, ce qui laisse le cache de prompt
faire son travail.

**Des consignes chargées seulement quand elles servent.**

- Des *skills* de projet pour les routines : `new-adr` (numéroter, rédiger, mettre l'index à jour)
  et `close-phase` (critère d'acceptation, `make test`, README, mesures pour l'article). Seule leur
  description d'une ligne est chargée en permanence ; le détail ne l'est qu'à l'usage.
- À partir de la phase 2, un `CLAUDE.md` par dossier (`infra/`, `gitops/`, `portal/`) : les
  conventions Terraform ne sont chargées que quand l'agent travaille dans `infra/`.

**Des lectures interdites.** Une règle `permissions.deny` empêche de lire `.terraform/`, les states,
les fichiers de lock, les `*.tfvars` et `.env`. Moins de tokens gaspillés sur des fichiers générés —
et la garantie qu'un state Terraform ou un fichier de configuration local n'atterrit jamais dans le
contexte d'un modèle.

**De l'hygiène de session.** Une session par tâche, `/clear` entre deux, le mode plan pour
démarrer une phase, `/context` et `/cost` pour voir ce qui pèse, et le modèle adapté à la tâche :
Sonnet pour l'exécution courante, le plus gros modèle pour concevoir une phase. Le gain le plus
important ne vient d'aucun outil : il vient de ne pas laisser une conversation s'allonger
indéfiniment.

---

## 5. Des revues IA à coût borné

Deux niveaux, du moins cher au plus cher.

**En local, avant chaque push : `/code-review`.** Une commande intégrée à Claude Code qui relit le
diff de la branche. Aucun coût de CI ; le réflexe est inscrit dans `CLAUDE.md`.

**En CI : [`claude-code-action`](https://github.com/anthropics/claude-code-action)**, avec un
workflow dont chaque ligne est un levier de coût :

| Levier | Réglage |
|---|---|
| Quand | À l'ouverture d'une PR prête, au passage brouillon → prête, ou sur le label `ai-review`. **Jamais à chaque push.** |
| Quoi | Le diff (`gh pr diff`) ; les autres fichiers seulement s'il y fait référence |
| Combien | `--max-turns 12`, `timeout-minutes: 10`, `concurrency` qui annule une revue obsolète |
| Avec quel modèle | Sonnet, pas le plus gros modèle |
| Pour qui | PR du dépôt uniquement, jamais depuis un fork |
| Sur quoi | Les **dérives par rapport à `CLAUDE.md`** d'abord (version non épinglée, secret, ressource sans label, travail d'une phase future), puis les bugs ; pas le style, ni ce que la CI vérifie déjà |

Le dernier levier est le plus rentable : la revue ne cherche pas « tout ce qui pourrait être
mieux », elle vérifie **le contrat du dépôt**. Des remarques moins nombreuses, plus utiles, et
moins de tokens.

**Aucune clé API stockée.** L'action sait s'authentifier par *Workload Identity Federation* : le
jeton OIDC que GitHub délivre au workflow est échangé contre un jeton Anthropic de courte durée,
lié à un compte de service et à une règle qui ne reconnaît que ce dépôt. C'est exactement le
principe que j'applique côté GCP avec Workload Identity (aucune clé de compte de service) ; il
aurait été incohérent de stocker un secret longue durée pour la revue. Dernier verrou : une
**limite de dépense** sur le workspace Anthropic du compte de service.

Pour comparaison, Anthropic propose aussi une
[revue de code managée](https://claude.com/blog/code-review), plus approfondie et nettement plus
chère par PR. Pour un dépôt vitrine, le workflow borné suffit. Le coût réel par revue sera
mesuré et publié dans l'épisode suivant.

---

## 6. Supply chain : l'outillage IA est aussi une dépendance

L'action de revue, les plugins, les serveurs MCP et les skills tiers exécutent du code sur ma
machine ou dans ma CI. Trois règles :

- **Épingler** : les actions GitHub par SHA de commit, les paquets par version exacte.
- **Laisser mûrir** : aucune version publiée depuis moins de **7 jours**. Pour l'action de revue,
  j'ai retenu la v1.0.268 plutôt que la dernière, sortie deux jours plus tôt.
- **Vérifier la provenance** : avant d'installer un paquet, contrôler que ses métadonnées pointent
  vers le dépôt officiel. Un nom de paquet inhabituel, c'est exactement là que se cache le
  typosquatting. Et regarder qui maintient l'outil : un projet de deux semaines porté par une seule
  personne peut être excellent, mais il ne doit pas devenir une dépendance de votre chaîne.

---

## Ce que je dirais à un client

Un agent de code, c'est un nouveau membre de l'équipe, très rapide et sans mémoire. Traitez-le
comme tel :

| Pour un humain | Pour un agent | Dans ce dépôt |
|---|---|---|
| Onboarding | Règles et plan écrits | `CLAUDE.md`, `PLAN.md`, ADR |
| Moindre privilège | Confirmation sur tout ce qui détruit ou facture | `permissions.ask` |
| Contrôles automatiques | Hooks, **testés comme du code** | `guard-gcloud.sh`, `make test` |
| Documentation | Courte, à jour, chargée au bon moment | `CLAUDE.md`, skills, ADR |
| Revue de code | Revue IA ciblée sur le contrat, à coût plafonné | `/code-review`, `claude-review.yml` |
| Budget | Limite de dépense, déclenchements rares | workspace Anthropic, triggers |

Le prochain épisode attaque le Resource Plane : `make up`, `make down`, et la chasse aux
ressources orphelines — avec le compteur de durées et de coûts, réels.
