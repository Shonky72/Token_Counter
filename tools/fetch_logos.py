"""Fetch real brand marks and rasterise them into bundled PNGs.

Pulls monochrome brand glyphs from the simple-icons set (CC0-licensed icon
*files*; the brands themselves are trademarks of their owners, bundled here only
to identify each service), recolours them to each brand's accent, and writes
``src/token_counter/assets/logos/<service_id>.png`` at 64px.

Run from the repo root:  ``python tools/fetch_logos.py``

Requires ``cairosvg`` (``pip install cairosvg``) and network access. Any service
not covered keeps its in-code drawn glyph at runtime — this script only fills in
the ones with a clean public icon, and is safe to re-run.
"""

from __future__ import annotations

import io
import sys
import urllib.request
from pathlib import Path

# service_id -> (simple-icons slug, brand hex). Only brands with a clean,
# recognisable public mark; the rest stay as drawn glyphs.
ICONS = {
    "openai": ("openai", "#10a37f"),
    "claude": ("anthropic", "#d97757"),
    "gemini": ("googlegemini", "#4285f4"),
    "mistral": ("mistralai", "#ff8f00"),
    "perplexity": ("perplexity", "#20b2aa"),
    "deepseek": ("deepseek", "#4d6bfe"),
    "cohere": ("cohere", "#d8647a"),
    "grok": ("x", "#ececed"),
    "groq": ("groq", "#f24e1e"),
    "openrouter": ("openrouter", "#7c5cdc"),
    "together": ("togetherdotai", "#f05a5a"),
}

CDNS = (
    "https://cdn.jsdelivr.net/npm/simple-icons/icons/{slug}.svg",
    "https://unpkg.com/simple-icons/icons/{slug}.svg",
    "https://raw.githubusercontent.com/simple-icons/simple-icons/develop/icons/{slug}.svg",
)
UA = "Mozilla/5.0 (X11; Linux x86_64) tokn-logo-fetch/1.0"
OUT = Path(__file__).resolve().parent.parent / "src" / "token_counter" / "assets" / "logos"


def _fetch_svg(slug: str) -> str | None:
    for tmpl in CDNS:
        url = tmpl.format(slug=slug)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=20) as resp:
                return resp.read().decode("utf-8")
        except Exception:
            continue
    return None


def _recolour(svg: str, hex_color: str) -> str:
    # simple-icons are single-path monochrome; force our brand fill.
    hexc = hex_color.lstrip("#")
    if "fill=" not in svg:
        svg = svg.replace("<svg", f'<svg fill="#{hexc}"', 1)
    else:
        import re

        svg = re.sub(r'fill="[^\"]*"', f'fill="#{hexc}"', svg)
    return svg


def main() -> int:
    try:
        import cairosvg
    except Exception:
        print("cairosvg not installed — run: pip install cairosvg", file=sys.stderr)
        return 1

    OUT.mkdir(parents=True, exist_ok=True)
    ok = 0
    for service_id, (slug, hexc) in ICONS.items():
        svg = _fetch_svg(slug)
        if svg is None:
            print(f"  skip {service_id} ({slug}): not reachable")
            continue
        svg = _recolour(svg, hexc)
        png = OUT / f"{service_id}.png"
        try:
            cairosvg.svg2png(bytestring=svg.encode("utf-8"), write_to=str(png),
                             output_width=64, output_height=64)
        except Exception as exc:
            print(f"  fail {service_id}: {exc}")
            continue
        ok += 1
        print(f"  wrote {png.relative_to(OUT.parent.parent.parent.parent)}")
    print(f"done: {ok}/{len(ICONS)} logos written to {OUT}")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
