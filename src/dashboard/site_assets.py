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

INK, AMBER, WHITE = (15, 23, 42), (245, 158, 11), (255, 255, 255)
# logo: navy tile with three rising index bars, the last one highlighted (32-unit grid)
BARS = [((7, 17, 11, 25), WHITE), ((14, 12, 18, 25), WHITE), ((21, 7, 25, 25), AMBER)]
SVG = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'>"
       "<rect width='32' height='32' rx='6' fill='#0f172a'/>"
       + "".join(f"<rect x='{x0}' y='{y0}' width='{x1 - x0}' height='{y1 - y0}' rx='1' "
                 f"fill='#{c[0]:02x}{c[1]:02x}{c[2]:02x}'/>" for (x0, y0, x1, y1), c in BARS)
       + "</svg>")


def logo(px: int) -> Image.Image:
    s = 4 * px                                            # supersample, then downscale
    k = s / 32
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, s - 1, s - 1], radius=int(6 * k), fill=INK)
    for (x0, y0, x1, y1), color in BARS:
        d.rounded_rectangle([x0 * k, y0 * k, x1 * k, y1 * k], radius=int(k), fill=color)
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
    img.paste(logo(120), (80, 80), logo(120))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 618, 1200, 630], fill=AMBER)
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
        "theme_color": "#0f172a", "background_color": "#f7f8fb", "display": "standalone",
        "start_url": "/"}, indent=1), encoding="utf-8")
    (out / "404.html").write_text(
        '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" '
        'content="width=device-width,initial-scale=1"><meta name="robots" content="noindex">'
        '<title>Page not found · Technology Disruption Index</title><link rel="icon" '
        'href="/favicon.svg" type="image/svg+xml"></head><body style="margin:0;min-height:100vh;'
        'display:grid;place-items:center;font:16px system-ui,sans-serif;background:#f7f8fb;'
        'color:#0f172a;text-align:center"><div><img src="/favicon.svg" width="56" height="56" '
        'alt=""><h1 style="margin:16px 0 6px">Page not found</h1><p style="color:#64748b">'
        'This page does not exist.</p><a href="/" style="display:inline-block;margin-top:12px;'
        'padding:10px 18px;border-radius:10px;background:#0f172a;color:#fff;text-decoration:none">'
        'Go to the Technology Disruption Index</a></div></body></html>', encoding="utf-8")
    (out / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {site}/sitemap.xml\n",
                                    encoding="utf-8")
    (out / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"  <url><loc>{site}/</loc><lastmod>{dt.date.today()}</lastmod>"
        "<changefreq>monthly</changefreq><priority>1.0</priority></url>\n</urlset>\n",
        encoding="utf-8")
