#!/usr/bin/env python3
"""Génère le visuel d'un épisode de la série Bivouac (tente de nuit en montagne).

Écrit `cover.svg` (source éditable) et `hero.png` (1200×630, utilisé par le thème pour la carte,
le bandeau d'article et l'aperçu LinkedIn) dans le dossier de l'article.

Usage :
  scripts/bivouac-cover.py content/posts/bivouac/02-make-up-make-down \\
      --label "ÉPISODE 2 · LE RESOURCE PLANE" \\
      --subtitle "make up, make down, zéro orphelin" \\
      --caption "durées et coûts réels"

Le PNG est rendu avec ImageMagick (`magick`). Les étoiles sont tirées avec une graine fixe :
tous les épisodes partagent le même ciel.
"""
import argparse
import pathlib
import random
import shutil
import subprocess
import sys
from xml.sax.saxutils import escape

TEMPLATE = """<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630" role="img" aria-label="Bivouac : une tente éclairée dans la montagne, la nuit">
  <defs>
    <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#070b18"/><stop offset="0.6" stop-color="#14213d"/><stop offset="1" stop-color="#1f3358"/>
    </linearGradient>
    <linearGradient id="tent" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#3d9ee5"/><stop offset="1" stop-color="#7c5cbf"/>
    </linearGradient>
    <radialGradient id="glow" cx="0.5" cy="0.5" r="0.5">
      <stop offset="0" stop-color="#ffcf7a" stop-opacity="0.55"/><stop offset="1" stop-color="#ffcf7a" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="door" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#ffe2a8"/><stop offset="1" stop-color="#ffb347"/>
    </linearGradient>
  </defs>
  <rect width="1200" height="630" fill="url(#sky)"/>
  {stars}
  <circle cx="1040" cy="95" r="34" fill="#e9eef8" opacity="0.9"/>
  <circle cx="1054" cy="86" r="32" fill="#0b1224" opacity="0.92"/>
  <polygon points="0,470 150,330 250,400 380,250 520,410 640,300 760,420 880,280 1010,400 1100,340 1200,420 1200,630 0,630" fill="#16233f"/>
  <polygon points="380,250 345,290 368,285 392,300 410,280" fill="#c9d6ea" opacity="0.55"/>
  <polygon points="880,280 850,315 872,310 895,322 912,305" fill="#c9d6ea" opacity="0.55"/>
  <polygon points="0,520 200,440 360,500 520,450 700,505 900,455 1060,500 1200,470 1200,630 0,630" fill="#1c2c4d"/>
  <rect y="560" width="1200" height="70" fill="#121c33"/>
  <ellipse cx="600" cy="520" rx="210" ry="70" fill="url(#glow)"/>
  <g stroke="#8aa4c4" stroke-width="1.5" opacity="0.7">
    <line x1="600" y1="395" x2="470" y2="560"/><line x1="600" y1="395" x2="730" y2="560"/>
  </g>
  <polygon points="600,390 500,560 700,560" fill="url(#tent)"/>
  <polygon points="600,390 700,560 650,560" fill="#000" opacity="0.18"/>
  <polygon points="600,445 566,560 634,560" fill="url(#door)"/>
  <line x1="600" y1="380" x2="600" y2="392" stroke="#c9d6ea" stroke-width="3"/>
  <g transform="translate(790,548)">
    <ellipse cx="0" cy="12" rx="70" ry="22" fill="url(#glow)"/>
    <line x1="-22" y1="12" x2="22" y2="4" stroke="#6b4a2e" stroke-width="6" stroke-linecap="round"/>
    <line x1="-22" y1="4" x2="22" y2="12" stroke="#5a3d25" stroke-width="6" stroke-linecap="round"/>
    <path d="M0,-34 C14,-16 16,-4 8,6 C4,10 -4,10 -8,6 C-16,-4 -12,-18 0,-34 Z" fill="#ff9a3c"/>
    <path d="M0,-18 C7,-8 7,0 3,5 C1,7 -2,7 -4,5 C-7,0 -6,-9 0,-18 Z" fill="#ffd27a"/>
  </g>
  <g font-family="Mulish, system-ui, sans-serif" text-anchor="middle">
    <text x="600" y="78" fill="#8aa4c4" font-size="18" letter-spacing="5">{label}</text>
    <text x="600" y="170" fill="#f2f6fc" font-size="88" font-weight="800" letter-spacing="10">{title}</text>
    <text x="600" y="222" fill="#c9d6ea" font-size="28">{subtitle}</text>
    <text x="600" y="608" fill="#8aa4c4" font-size="18" letter-spacing="1">{caption}</text>
  </g>
</svg>
"""


def stars() -> str:
    rnd = random.Random(7)
    return "".join(
        f'<circle cx="{rnd.randint(0, 1200)}" cy="{rnd.randint(0, 330)}" '
        f'r="{rnd.choice([0.8, 1, 1.2, 1.6])}" fill="#e6eefa" opacity="{rnd.choice([0.35, 0.5, 0.7, 0.9])}"/>'
        for _ in range(90)
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("article_dir", type=pathlib.Path, help="dossier de l'article (page bundle)")
    ap.add_argument("--label", required=True, help="ligne du haut, en capitales (ex. « ÉPISODE 2 · … »)")
    ap.add_argument("--title", default="BIVOUAC")
    ap.add_argument("--subtitle", required=True, help="une ligne, ~50 caractères max")
    ap.add_argument("--caption", required=True, help="ligne du bas, ~80 caractères max")
    args = ap.parse_args()

    if not args.article_dir.is_dir():
        print(f"Dossier introuvable : {args.article_dir}", file=sys.stderr)
        return 1
    svg = TEMPLATE.format(
        stars=stars(),
        label=escape(args.label),
        title=escape(args.title),
        subtitle=escape(args.subtitle),
        caption=escape(args.caption),
    )
    svg_path = args.article_dir / "cover.svg"
    png_path = args.article_dir / "hero.png"
    svg_path.write_text(svg, encoding="utf-8")

    magick = shutil.which("magick")
    if not magick:
        print(f"{svg_path} écrit ; ImageMagick absent, PNG non généré.", file=sys.stderr)
        return 2
    subprocess.run([magick, "-density", "96", str(svg_path), "-resize", "1200x630", str(png_path)], check=True)
    print(f"{svg_path}\n{png_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
