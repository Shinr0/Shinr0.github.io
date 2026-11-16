# Site romain-capelle.cloud — règles pour Claude Code

Site vitrine Hugo (thème Toha, module Hugo), en français.

## Publication
- `main` = source. Un push sur `main` lance `.github/workflows/merge-to-main.yml`, qui construit le
  site et pousse le résultat sur `gh-pages`, servie par GitHub Pages (domaine `romain-capelle.cloud`).
  **Ne jamais modifier `gh-pages` à la main.**
- Toujours travailler sur une branche + PR. Le job `build` de la PR doit être vert ; les jobs
  `lighthouse-check` et `markdown-link-check` échouent toujours (aperçu Netlify absent) : les ignorer.
- Merger la PR = publier. Jamais de merge ni de push sur `main` sans demande explicite.
- Article daté dans le futur : Hugo ne le publie pas. Après la date, relancer le déploiement avec
  « Run workflow » sur le workflow de déploiement (GitHub Actions).

## Versions (épinglées, jamais `latest`)
- Hugo 0.169.0 extended (`mise.toml` + workflows), Dart Sass 1.108.0 (workflows).
- Changement de version : une release publiée depuis au moins 7 jours, vérifiée par le build de PR.

## En local
- `mise run server` (installe les outils puis lance `hugo server`), ou
  `hugo server --disableFastRender` ; Dart Sass doit être dans le PATH.
- Bug connu : après un rechargement à chaud, le CSS peut ne plus correspondre à son hash
  d'intégrité et la page s'affiche sans style. Redémarrer le serveur puis Ctrl+Shift+R.
- Ne jamais commiter les fichiers régénérés par `mise run install` : `package.json`,
  `package-lock.json`, `assets/jsconfig.json`, `packages/`.
- Vérifier un build complet avant de pousser : `hugo --destination /tmp/<dossier>` sans `ERROR`.

## Série Bivouac (`content/posts/bivouac/`)
- Un dossier par épisode `NN-slug/` (page bundle) : `index.md`, `hero.png`, `cover.svg`.
- Front matter : `title: "Bivouac #N — …"`, `description` (affichée sur la carte et dans l'aperçu
  LinkedIn), `categories: [Série Bivouac]`, `menu.sidebar` avec `parent: bivouac`,
  `identifier: bivouac-NN`, `weight: N`.
- Visuel : `scripts/bivouac-cover.py <dossier> --label "ÉPISODE N · …" --subtitle "…" --caption "…"`
  génère `cover.svg` et `hero.png` (1200×630, requiert ImageMagick). Pas de `hero.svg` : il s'affiche
  mal dans les cartes.
- Liens vers le code : `https://github.com/Shinr0/bivouac`. Le plan éditorial et les brouillons
  LinkedIn sont dans `~/perso/bivouac/content/plan-editorial.md` (non versionné).
- Règles éditoriales : chiffres réels uniquement (jamais d'estimation présentée comme une mesure),
  chaque affirmation sur un outil vérifiée à la source, ton factuel, chaque épisode se termine par
  « Ce que je dirais à un client ».

## Surcharges du thème
- `layouts/partials/opengraph.html` : aperçus de partage propres à chaque article (titre,
  description, `hero.png`, URL absolue).
- `assets/styles/override.scss` : bandeau d'article affiché sans recadrage (visuels 1200×630).
