"""
Static site assets for search engines and link previews (written into docs/):
favicon.svg / favicon.ico / PNG app icons, og-image.png (1200x630), site.webmanifest,
robots.txt and sitemap.xml. Google shows the favicon in search results only if it is a
crawlable file (multiple of 48 px) linked from the home page, hence real files instead of
a data: URI.
"""
import datetime as dt
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import config

ACC, ACC2, INK = (79, 70, 229), (6, 182, 212), (15, 23, 42)
LINE = [(7, 22), (13, 15), (18, 19), (25, 10)]          # logo chart line on a 32-unit grid
SVG = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><defs><linearGradient "
       "id='g' x1='0' y1='0' x2='1' y2='1'><stop offset='0' stop-color='#4f46e5'/><stop "
       "offset='1' stop-color='#06b6d4'/></linearGradient></defs><rect width='32' height='32' "
       "rx='8' fill='url(#g)'/><path d='M7 22l6-7 5 4 7-9' stroke='white' stroke-width='3' "
       "fill='none' stroke-linecap='round' stroke-linejoin='round'/></svg>")


def gradient(size, c1, c2) -> Image.Image:
    w, h = size
    img = Image.new("RGB", size)
    px = img.load()
    for y in range(h):
        for x in range(w):
            t = (x / w + y / h) / 2
            px[x, y] = tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))
    return img


def logo(px: int) -> Image.Image:
    s = 4 * px                                            # supersample, then downscale
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, s - 1, s - 1], radius=s // 4, fill=255)
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    img.paste(gradient((s, s), ACC, ACC2), (0, 0), mask)
    k = s / 32
    ImageDraw.Draw(img).line([(x * k, y * k) for x, y in LINE], fill="white",
                             width=int(3 * k), joint="curve")
    for x, y in (LINE[0], LINE[-1]):
        r = 1.5 * k
        ImageDraw.Draw(img).ellipse([x * k - r, y * k - r, x * k + r, y * k + r], fill="white")
    return img.resize((px, px), Image.LANCZOS)


def font(size: int, bold: bool = False):
    for name in (["segoeuib.ttf", "arialbd.ttf"] if bold else ["segoeui.ttf", "arial.ttf"]):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def og_image(path: Path, n_companies: str, years: str) -> None:
    img = Image.new("RGB", (1200, 630), (247, 248, 251))
    glow = gradient((1200, 630), (230, 232, 255), (224, 247, 252))
    img.paste(glow)
    img.paste(logo(120), (80, 80), logo(120))
    d = ImageDraw.Draw(img)
    d.text((80, 250), "Technology Disruption Index", font=font(68, True), fill=INK)
    d.text((80, 345), f"Tech-exposure scores for {n_companies} public companies, {years}",
           font=font(36), fill=(71, 85, 105))
    d.text((80, 405), "Patents  ·  Startup ecosystems  ·  SEC fundamentals  ·  Open research",
           font=font(30), fill=(100, 116, 139))
    d.rounded_rectangle([80, 500, 470, 560], radius=14, fill=INK)
    d.text((108, 512), "Explore the data  →", font=font(30, True), fill="white")
    img.save(path, optimize=True)


def write_all(out: Path, n_companies: str, years: str) -> None:
    site = config.SITE_URL.rstrip("/")
    (out / "favicon.svg").write_text(SVG, encoding="utf-8")
    logo(256).save(out / "favicon.ico", sizes=[(48, 48), (32, 32), (16, 16)])
    logo(48).save(out / "favicon-48.png")
    logo(180).convert("RGB").save(out / "apple-touch-icon.png")
    logo(192).save(out / "icon-192.png")
    logo(512).save(out / "icon-512.png")
    og_image(out / "og-image.png", n_companies, years)
    (out / "site.webmanifest").write_text(json.dumps({
        "name": "Technology Disruption Index", "short_name": "TDI",
        "icons": [{"src": "/icon-192.png", "sizes": "192x192", "type": "image/png"},
                  {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png"}],
        "theme_color": "#4f46e5", "background_color": "#f7f8fb", "display": "standalone",
        "start_url": "/"}, indent=1), encoding="utf-8")
    (out / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {site}/sitemap.xml\n",
                                    encoding="utf-8")
    (out / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"  <url><loc>{site}/</loc><lastmod>{dt.date.today()}</lastmod>"
        "<changefreq>monthly</changefreq><priority>1.0</priority></url>\n</urlset>\n",
        encoding="utf-8")
