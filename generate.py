#!/usr/bin/env python3
"""
SSG (Static Site Generation) для сайта "Цена Дня | Яндекс.Маркет".

Читает data/products.json и data/categories.json,
генерирует:
  - /categories/{slug}/index.html  — страницы категорий
  - /products/{article}/index.html — страницы товаров
  - /sitemap.xml                   — карта сайта
  - обновляет robots.txt           — ссылка на sitemap
"""

import json
import hashlib
import os
import re
import shutil
import sys
import html as html_mod
import math
from datetime import datetime
from pathlib import Path

# ─── Paths ──────────────────────────────────────────────────────────
SITE_DIR = Path(__file__).resolve().parent
PRODUCTS_JSON = SITE_DIR / "data" / "products.json"
CATEGORIES_JSON = SITE_DIR / "data" / "categories.json"
HASH_FILE = SITE_DIR / ".products_hash"
BASE_URL = "https://kristall2002-art.github.io/tsena-dnya-yandex-site"

# ─── Transliteration ───────────────────────────────────────────────
TRANSLIT_MAP = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e',
    'ё': 'yo', 'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k',
    'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r',
    'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'kh', 'ц': 'ts',
    'ч': 'ch', 'ш': 'sh', 'щ': 'shch', 'ъ': '', 'ы': 'y', 'ь': '',
    'э': 'e', 'ю': 'yu', 'я': 'ya',
}


def transliterate(text: str) -> str:
    """Транслитерация русского текста в slug."""
    result = []
    for ch in text.lower():
        if ch in TRANSLIT_MAP:
            result.append(TRANSLIT_MAP[ch])
        elif ch == ' ':
            result.append('-')
        elif ch.isascii() and (ch.isalnum() or ch == '-'):
            result.append(ch)
    # Убрать двойные дефисы и крайние
    slug = '-'.join(part for part in ''.join(result).split('-') if part)
    return slug


# ─── Price helpers ────────────────────────────────────────────────
def format_price(n: int) -> str:
    return f"{n:,}".replace(",", "\u00a0") + " ₽"


def esc(s: str) -> str:
    return html_mod.escape(s) if s else ""


# ─── CSS (yellow theme for Yandex Market) ────────────────────────
COMMON_CSS = """\
*{margin:0;padding:0;box-sizing:border-box}
:root{
  --bg:#1a1400;
  --bg2:#2a2000;
  --bg3:#3a3010;
  --purple:#FFD700;
  --purple-dark:#FF9800;
  --purple-light:#FFD700;
  --accent:#e74c3c;
  --green:#27ae60;
  --text:#fff8e0;
  --text2:#ccb870;
  --text3:#8a7a4a;
  --card-radius:14px;
  --max-w:1200px;
  --price-color:#fff;
  --header-bg:linear-gradient(135deg,var(--purple-dark),#e68900);
  --shadow-color:rgba(255,152,0,.4);
}
html.light{
  --bg:#fffde7;
  --bg2:#fff;
  --bg3:#fff3cd;
  --purple:#FF9800;
  --purple-dark:#FF9800;
  --purple-light:#e68900;
  --text:#1a1400;
  --text2:#5a4d20;
  --text3:#8a7a4a;
  --price-color:#1a1400;
  --shadow-color:rgba(255,152,0,.15);
}
body{
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
  background:var(--bg);
  color:var(--text);
  min-height:100vh;
  -webkit-font-smoothing:antialiased;
}
a{color:inherit;text-decoration:none}
.header{
  background:linear-gradient(135deg,var(--purple-dark),#e68900);
  padding:14px 20px;
  z-index:100;
  box-shadow:0 2px 20px rgba(255,152,0,.4);
}
.header-inner{max-width:var(--max-w);margin:0 auto;display:flex;align-items:center;gap:14px}
.header-logo{width:48px;height:48px;border-radius:12px;flex-shrink:0}
.header-center{flex:1}
.header-row1{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap}
.logo{font-size:22px;font-weight:800;letter-spacing:-.5px}
.logo span{color:var(--purple-light)}
.header-sub{font-size:14px;color:rgba(255,255,255,.75);font-weight:500}
.header-tg{font-size:13px;color:#fff;background:rgba(255,255,255,.15);padding:4px 12px;border-radius:12px;display:inline-block;transition:background .2s}
.header-tg:hover{background:rgba(255,255,255,.25)}
.header-row2{display:flex;align-items:center;gap:12px;margin-top:4px;flex-wrap:wrap}
.header-info{font-size:12px;color:rgba(255,255,255,.5)}
.header-right{display:flex;align-items:center;flex-shrink:0}
.theme-toggle{
  display:flex;align-items:center;gap:6px;
  background:rgba(255,255,255,.15);
  border:none;color:#fff;
  padding:6px 14px;border-radius:18px;
  cursor:pointer;font-size:13px;
  transition:background .2s;white-space:nowrap;
}
.theme-toggle:hover{background:rgba(255,255,255,.25)}
.theme-toggle .icon{font-size:16px}
.main{max-width:var(--max-w);margin:0 auto;padding:20px}
.section-title{
  font-size:18px;font-weight:700;
  margin-bottom:16px;
  display:flex;align-items:center;gap:8px;
}
.section-title .emoji{font-size:22px}
.grid{
  display:grid;
  grid-template-columns:repeat(auto-fill,minmax(280px,1fr));
  gap:16px;
  margin-bottom:32px;
}
.card{
  background:var(--bg2);
  border-radius:var(--card-radius);
  overflow:hidden;
  border:1px solid var(--bg3);
  transition:transform .2s,box-shadow .2s;
  cursor:pointer;
}
.card:hover{
  transform:translateY(-2px);
  box-shadow:0 8px 25px rgba(255,152,0,.3);
  border-color:var(--purple-dark);
}
.card-img{
  width:100%;
  aspect-ratio:3/4;
  object-fit:contain;
  background:var(--bg3);
  display:block;
}
.card-img.no-img{
  display:flex;align-items:center;justify-content:center;
  font-size:48px;color:var(--text3);
}
.card-body{padding:14px}
.card-brand{font-size:12px;color:var(--purple-light);font-weight:600;text-transform:uppercase;letter-spacing:.5px}
.card-name{font-size:14px;color:var(--text);margin-top:4px;line-height:1.3;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.card-prices{margin-top:10px;display:flex;align-items:baseline;gap:8px;flex-wrap:wrap}
.price-now{font-size:22px;font-weight:800;color:var(--price-color)}
.price-old{font-size:14px;color:var(--text3);text-decoration:line-through}
.price-discount{
  font-size:12px;font-weight:700;
  background:var(--accent);color:#fff;
  padding:2px 8px;border-radius:6px;
}
.card-footer{
  display:flex;align-items:center;justify-content:space-between;
  margin-top:10px;padding-top:10px;
  border-top:1px solid var(--bg3);
}
.card-rating{font-size:13px;color:var(--text2)}
.card-rating .star{color:#f1c40f}
.card-reviews{font-size:12px;color:var(--text3)}
.footer{
  text-align:center;padding:24px;
  color:var(--text3);font-size:13px;
  border-top:1px solid var(--bg3);
  margin-top:40px;
}
.footer a{color:var(--purple-light)}
.ad-btn{
  display:inline-block;
  margin-top:12px;
  padding:10px 24px;
  background:var(--header-bg);
  color:#fff;
  border-radius:8px;
  text-decoration:none;
  font-size:14px;
  font-weight:600;
  transition:opacity .2s;
}
.ad-btn:hover{opacity:.85}
"""

# Extra CSS for SSG pages (breadcrumbs, product page, buttons)
SSG_EXTRA_CSS = """\
.breadcrumbs{
  max-width:var(--max-w);margin:0 auto;
  padding:12px 20px;font-size:13px;color:var(--text3);
}
.breadcrumbs a{color:var(--purple-light);text-decoration:none}
.breadcrumbs a:hover{text-decoration:underline}
.breadcrumbs .sep{margin:0 6px;color:var(--text3)}
.product-page{
  max-width:var(--max-w);margin:0 auto;padding:20px;
  display:grid;grid-template-columns:1fr 1fr;gap:30px;
}
.product-image{
  width:100%;max-width:500px;aspect-ratio:3/4;
  object-fit:contain;background:var(--bg3);
  border-radius:var(--card-radius);display:block;
}
.product-image.no-img{
  display:flex;align-items:center;justify-content:center;
  font-size:72px;color:var(--text3);
  border-radius:var(--card-radius);background:var(--bg3);
  width:100%;max-width:500px;aspect-ratio:3/4;
}
.product-info h1{font-size:22px;font-weight:700;line-height:1.3;margin-bottom:6px}
.product-brand{font-size:14px;color:var(--purple-light);font-weight:600;text-transform:uppercase;letter-spacing:.5px;margin-bottom:12px}
.product-prices{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;margin-bottom:8px}
.product-prices .price-now{font-size:30px}
.product-rating{font-size:15px;color:var(--text2);margin-bottom:20px}
.product-rating .star{color:#f1c40f}
.product-actions{display:flex;flex-direction:column;gap:10px;margin-top:10px}
.btn-ym{
  display:inline-flex;align-items:center;justify-content:center;gap:8px;
  padding:14px 28px;
  background:linear-gradient(135deg,#FF9800,#FFD700);
  color:#fff;border:none;border-radius:12px;
  font-size:16px;font-weight:700;cursor:pointer;
  text-decoration:none;transition:opacity .2s;
}
.btn-ym:hover{opacity:.85}
.btn-track{
  display:inline-flex;align-items:center;justify-content:center;gap:8px;
  padding:12px 28px;
  background:var(--bg3);
  color:var(--text);border:1px solid var(--purple-dark);border-radius:12px;
  font-size:15px;font-weight:600;cursor:pointer;
  text-decoration:none;transition:all .2s;
}
.btn-track:hover{background:var(--purple-dark);color:#fff}
.cat-link{
  display:inline-block;padding:8px 20px;
  border-radius:22px;border:1px solid var(--bg3);
  background:transparent;color:var(--text2);
  font-size:15px;text-decoration:none;
  transition:all .2s;margin-bottom:8px;margin-right:8px;
}
.cat-link:hover{border-color:var(--purple);color:var(--text)}
.cat-link.active{background:var(--purple-dark);border-color:var(--purple);color:#fff}
.cat-bar-static{
  background:var(--bg2);
  padding:12px 20px;
  overflow-x:auto;
  -webkit-overflow-scrolling:touch;
  scrollbar-width:none;
  border-bottom:1px solid var(--bg3);
}
.cat-bar-static::-webkit-scrollbar{display:none}
.cat-bar-inner{max-width:var(--max-w);margin:0 auto;display:flex;gap:8px;flex-wrap:nowrap}
@media(max-width:600px){
  .grid{grid-template-columns:1fr;gap:12px}
  .card-body{padding:12px}
  .price-now{font-size:20px}
  .card-name{font-size:14px}
  .header{position:relative;padding:10px 14px}
  .header-logo{width:40px;height:40px;border-radius:10px}
  .logo{font-size:17px}
  .header-sub{font-size:12px}
  .header-row1{gap:6px}
  .main{padding:14px}
  .product-page{grid-template-columns:1fr;gap:16px}
  .product-image{max-width:100%}
  .product-prices .price-now{font-size:24px}
  .breadcrumbs{padding:10px 14px}
}
"""

THEME_JS = """\
<script>
const themeBtn=document.getElementById('themeBtn'),themeLabel=document.getElementById('themeLabel'),themeIcon=document.getElementById('themeIcon');
function updateThemeBtn(l){themeLabel.textContent=l?'Тёмная тема':'Светлая тема';themeIcon.textContent=l?'🌙':'☀️'}
if(localStorage.getItem('theme')==='light'){document.documentElement.classList.add('light');updateThemeBtn(true)}
themeBtn.addEventListener('click',()=>{const l=document.documentElement.classList.toggle('light');updateThemeBtn(l);localStorage.setItem('theme',l?'light':'dark')});
</script>
"""


# ─── HTML builders ─────────────────────────────────────────────────
def build_header(base_path: str = "../../") -> str:
    return f"""\
<header class="header">
  <div class="header-inner">
    <a href="{base_path}"><img class="header-logo" src="{base_path}logo.png" alt="Цена Дня"></a>
    <div class="header-center">
      <div class="header-row1">
        <a href="{base_path}" style="text-decoration:none;color:inherit"><h1 class="logo">Цена Дня <span>| Яндекс Маркет</span></h1></a>
        <div class="header-sub">Поиск самых низких цен на товары каждый день</div>
      </div>
      <div class="header-row2">
        <span class="header-tg">Ещё больше товаров в нашей Telegram-группе 👉 <a href="https://t.me/tsena_dnya_ym" target="_blank" style="color:#fff;text-decoration:underline">Цена Дня | ЯМ</a></span>
      </div>
    </div>
    <div class="header-right">
      <button class="theme-toggle" id="themeBtn"><span id="themeLabel">Светлая тема</span> <span class="icon" id="themeIcon">☀️</span></button>
    </div>
  </div>
</header>"""


def build_footer() -> str:
    return """\
<footer class="footer">
  Цена Дня | Яндекс Маркет — лучшие цены на Яндекс Маркете каждый день<br>
  <a href="https://t.me/tsena_dnya_yandex" target="_blank">Telegram-канал</a> ·
  <a href="https://t.me/tsena_dnya_yandex_bot" target="_blank">Telegram-бот</a> ·
  Данные обновляются каждые 10 минут<br>
  <a class="ad-btn" href="https://t.me/tsena_dnya_yandex_bot?start=ad" target="_blank">📢 Заказ рекламы на сайте и в Telegram-канале</a>
</footer>"""


def build_cat_bar(categories: list, active_slug: str = "", base_path: str = "../../") -> str:
    links = [f'<a class="cat-link" href="{base_path}">Все товары</a>']
    for cat in categories:
        slug = transliterate(cat["name"])
        active = ' active' if slug == active_slug else ''
        links.append(
            f'<a class="cat-link{active}" href="{base_path}categories/{slug}/">'
            f'{cat["emoji"]} {esc(cat["name"])}</a>'
        )
    return f'<nav class="cat-bar-static"><div class="cat-bar-inner">{"".join(links)}</div></nav>'


def get_product_image_html(p: dict) -> str:
    if p.get("image"):
        img = p["image"]
        return f'<img class="card-img" src="{img}" alt="{esc(p.get("name", ""))}" loading="lazy" onerror="this.outerHTML=\'<div class=\\\'card-img no-img\\\'>📦</div>\'">'
    return '<div class="card-img no-img">📦</div>'


def get_product_image_url(p: dict) -> str:
    """Get clean image URL for OG tags."""
    if p.get("image"):
        return p["image"]
    return ""


def build_card_html(p: dict, cat_name: str = "", cat_emoji: str = "", base_path: str = "../../") -> str:
    price = p["price"]
    has_discount = p.get("oldPrice") and p["oldPrice"] > price
    discount = round((p["oldPrice"] - price) / p["oldPrice"] * 100) if has_discount else 0
    article = p.get("article", "")
    product_url = f"{base_path}products/{article}/" if article else "#"
    img_html = get_product_image_html(p)

    brand_html = f'<div class="card-brand">{esc(p.get("brand", ""))}</div>' if p.get("brand") else ""
    discount_html = (
        f'<span class="price-old">{format_price(p["oldPrice"])}</span>'
        f'<span class="price-discount">-{discount}%</span>'
    ) if has_discount else ""
    cat_html = f'<div style="font-size:11px;color:var(--text2);margin-top:4px;opacity:0.7">{cat_emoji} {esc(cat_name)}</div>' if cat_name else ""

    return f"""\
<a class="card" href="{product_url}">
  {img_html}
  <div class="card-body">
    {brand_html}
    <div class="card-name">{esc(p.get("name", ""))}</div>
    <div class="card-prices">
      <span class="price-now">{format_price(price)}</span>
      {discount_html}
    </div>
    <div class="card-footer">
      <span class="card-rating"><span class="star">⭐</span> {esc(p.get("rating", "—"))}</span>
      <span class="card-reviews">{esc(p.get("reviews", ""))}</span>
    </div>
    {cat_html}
  </div>
</a>"""


# ─── Page generators ───────────────────────────────────────────────
def generate_category_page(
    cat_info: dict,
    products: list,
    categories: list,
    updated_at: str,
) -> str:
    slug = transliterate(cat_info["name"])
    title = f'{cat_info["emoji"]} {cat_info["name"]} — Цена Дня | Яндекс Маркет'
    desc = f'Лучшие цены на {cat_info["name"].lower()} на Яндекс Маркете. {len(products)} товаров со скидками. Обновлено каждый день.'
    base = "../../"
    canonical = f"{BASE_URL}/categories/{slug}/"

    cards = "\n".join(build_card_html(p, base_path=base) for p in products)
    cat_bar = build_cat_bar(categories, active_slug=slug, base_path=base)

    return f"""\
<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<meta name="theme-color" content="#FF9800">
<link rel="icon" type="image/svg+xml" href="{base}icon.svg">
<link rel="apple-touch-icon" href="{base}icon-192.png">
<link rel="canonical" href="{canonical}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:image" content="{BASE_URL}/icon-512.png">
<meta property="og:url" content="{canonical}">
<meta property="og:type" content="website">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="{esc(title)}">
<meta name="twitter:description" content="{esc(desc)}">
<style>
{COMMON_CSS}
{SSG_EXTRA_CSS}
</style>
</head>
<body>
{build_header(base)}
{cat_bar}
<div class="breadcrumbs">
  <a href="{base}">Главная</a><span class="sep">›</span>
  {cat_info["emoji"]} {esc(cat_info["name"])}
</div>
<main class="main">
  <h2 class="section-title"><span class="emoji">{cat_info["emoji"]}</span>{esc(cat_info["name"])} <span style="font-size:14px;color:var(--text3);font-weight:400;margin-left:8px">{len(products)} товаров</span></h2>
  <div class="grid">
    {cards}
  </div>
</main>
{build_footer()}
{THEME_JS}
</body>
</html>"""


def generate_product_page(
    product: dict,
    cat_name: str,
    cat_emoji: str,
    categories: list,
) -> str:
    article = product.get("article", "")
    name = product.get("name", "Товар")
    brand = product.get("brand", "")
    price = product["price"]
    has_discount = product.get("oldPrice") and product["oldPrice"] > price
    discount = round((product["oldPrice"] - price) / product["oldPrice"] * 100) if has_discount else 0
    ym_url = f"https://market.yandex.ru/product/{article}" if article else "#"
    track_url = f"https://t.me/tsena_dnya_yandex_bot?start=track_{article}" if article else "#"
    base = "../../"
    canonical = f"{BASE_URL}/products/{article}/"
    cat_slug = transliterate(cat_name)
    img_url = get_product_image_url(product)
    posted_at = product.get("postedAt", "")

    title = f"{name} — купить на Яндекс Маркете | Цена Дня"
    desc = f"{name}"
    if brand:
        desc = f"{brand} — {desc}"
    desc += f" за {format_price(price)}"
    if has_discount:
        desc += f" (скидка {discount}%)"
    desc += ". Лучшая цена на Яндекс Маркете."

    # Image HTML for product page
    if product.get("image"):
        img_src = product["image"]
        img_html = f'<img class="product-image" src="{img_src}" alt="{esc(name)}" onerror="this.outerHTML=\'<div class=\\\'product-image no-img\\\'>📦</div>\'">'
    else:
        img_html = '<div class="product-image no-img">📦</div>'

    brand_html = f'<div class="product-brand">{esc(brand)}</div>' if brand else ""
    discount_html = (
        f'<span class="price-old">{format_price(product["oldPrice"])}</span>'
        f'<span class="price-discount">-{discount}%</span>'
    ) if has_discount else ""

    # Schema.org JSON-LD
    schema = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": name,
        "url": canonical,
        "offers": {
            "@type": "Offer",
            "url": canonical,
            "priceCurrency": "RUB",
            "price": price,
            "availability": "https://schema.org/InStock",
            "seller": {
                "@type": "Organization",
                "name": "Яндекс Маркет",
            },
        },
    }
    if brand:
        schema["brand"] = {"@type": "Brand", "name": brand}
    if img_url:
        schema["image"] = img_url
    if product.get("rating"):
        try:
            rating_val = float(product["rating"])
            schema["aggregateRating"] = {
                "@type": "AggregateRating",
                "ratingValue": rating_val,
                "bestRating": 5,
            }
            # Extract review count from "129 отзывов" string
            reviews_str = product.get("reviews", "")
            if reviews_str:
                review_count = "".join(ch for ch in reviews_str if ch.isdigit())
                if review_count:
                    schema["aggregateRating"]["reviewCount"] = int(review_count)
        except (ValueError, TypeError):
            pass

    # BreadcrumbList schema
    breadcrumb_schema = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": 1,
                "name": "Главная",
                "item": BASE_URL + "/",
            },
            {
                "@type": "ListItem",
                "position": 2,
                "name": cat_name,
                "item": f"{BASE_URL}/categories/{cat_slug}/",
            },
            {
                "@type": "ListItem",
                "position": 3,
                "name": name,
            },
        ],
    }

    schema_json = json.dumps(schema, ensure_ascii=False)
    breadcrumb_json = json.dumps(breadcrumb_schema, ensure_ascii=False)

    og_image = f'<meta property="og:image" content="{esc(img_url)}">' if img_url else ""
    twitter_image = f'<meta name="twitter:image" content="{esc(img_url)}">' if img_url else ""

    return f"""\
<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<meta name="theme-color" content="#FF9800">
<link rel="icon" type="image/svg+xml" href="{base}icon.svg">
<link rel="apple-touch-icon" href="{base}icon-192.png">
<link rel="canonical" href="{canonical}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
{og_image}
<meta property="og:url" content="{canonical}">
<meta property="og:type" content="product">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(title)}">
<meta name="twitter:description" content="{esc(desc)}">
{twitter_image}
<script type="application/ld+json">{schema_json}</script>
<script type="application/ld+json">{breadcrumb_json}</script>
<style>
{COMMON_CSS}
{SSG_EXTRA_CSS}
</style>
</head>
<body>
{build_header(base)}
<div class="breadcrumbs">
  <a href="{base}">Главная</a><span class="sep">›</span>
  <a href="{base}categories/{cat_slug}/">{cat_emoji} {esc(cat_name)}</a><span class="sep">›</span>
  {esc(name)}
</div>
<main class="main">
  <div class="product-page">
    <div>
      {img_html}
    </div>
    <div class="product-info">
      {brand_html}
      <h1>{esc(name)}</h1>
      <div style="font-size:12px;color:var(--text3);margin:6px 0">Артикул: {esc(article)}</div>
      <div class="product-prices">
        <span class="price-now">{format_price(price)}</span>
        {discount_html}
      </div>
      <div class="product-rating">
        <span class="star">⭐</span> {esc(product.get("rating", "—"))} · {esc(product.get("reviews", ""))}
      </div>
      <div class="product-actions">
        <a class="btn-ym" href="{ym_url}" target="_blank" rel="noopener">🛒 Купить на Яндекс Маркете</a>
        <a class="btn-track" href="{track_url}" target="_blank" rel="noopener">🔔 Следить за ценой</a>
      </div>
    </div>
  </div>
</main>
{build_footer()}
{THEME_JS}
</body>
</html>"""


def generate_sitemap(
    categories: list,
    all_products: list,
    updated_at: str,
) -> str:
    """Generate sitemap.xml."""
    # Parse updatedAt to ISO date
    try:
        dt = datetime.strptime(updated_at, "%Y-%m-%d %H:%M:%S")
        lastmod = dt.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        lastmod = datetime.now().strftime("%Y-%m-%d")

    urls = []
    # Main page
    urls.append(f"""\
  <url>
    <loc>{BASE_URL}/</loc>
    <lastmod>{lastmod}</lastmod>
    <changefreq>hourly</changefreq>
    <priority>1.0</priority>
  </url>""")

    # Category pages
    for cat in categories:
        slug = transliterate(cat["name"])
        urls.append(f"""\
  <url>
    <loc>{BASE_URL}/categories/{slug}/</loc>
    <lastmod>{lastmod}</lastmod>
    <changefreq>daily</changefreq>
    <priority>0.8</priority>
  </url>""")

    # Product pages
    for p in all_products:
        article = p.get("article", "")
        if not article:
            continue
        p_lastmod = lastmod
        if p.get("postedAt"):
            try:
                p_dt = datetime.strptime(p["postedAt"], "%Y-%m-%d %H:%M:%S")
                p_lastmod = p_dt.strftime("%Y-%m-%d")
            except (ValueError, TypeError):
                pass
        urls.append(f"""\
  <url>
    <loc>{BASE_URL}/products/{article}/</loc>
    <lastmod>{p_lastmod}</lastmod>
    <changefreq>daily</changefreq>
    <priority>0.6</priority>
  </url>""")

    return f"""\
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{"".join(urls)}
</urlset>
"""


def generate_robots_txt() -> str:
    return f"""\
User-agent: *
Allow: /

Sitemap: {BASE_URL}/sitemap.xml
"""


# ─── Main ──────────────────────────────────────────────────────────
def main():
    # Validate input files
    if not PRODUCTS_JSON.exists():
        print(f"ERROR: {PRODUCTS_JSON} not found", file=sys.stderr)
        sys.exit(1)
    if not CATEGORIES_JSON.exists():
        print(f"ERROR: {CATEGORIES_JSON} not found", file=sys.stderr)
        sys.exit(1)

    # Read products.json
    try:
        raw = PRODUCTS_JSON.read_bytes()
        data = json.loads(raw)
    except (json.JSONDecodeError, IOError) as e:
        print(f"ERROR: Cannot parse products.json: {e}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(data, dict) or "categories" not in data:
        print("ERROR: products.json has invalid structure", file=sys.stderr)
        sys.exit(1)

    # Check hash — skip if not changed
    current_hash = hashlib.md5(raw).hexdigest()
    if HASH_FILE.exists():
        saved_hash = HASH_FILE.read_text().strip()
        if saved_hash == current_hash:
            print("products.json not changed, skipping generation")
            return

    # Read categories.json
    try:
        categories = json.loads(CATEGORIES_JSON.read_bytes())
    except (json.JSONDecodeError, IOError) as e:
        print(f"ERROR: Cannot parse categories.json: {e}", file=sys.stderr)
        sys.exit(1)

    updated_at = data.get("updatedAt", "")
    cats_data = data.get("categories", {})

    # Filter categories list: only those that have products
    valid_cat_names = {c["name"] for c in categories}

    # Build category → products mapping
    cat_products = {}
    for cat in categories:
        name = cat["name"]
        prods = cats_data.get(name, [])
        if prods:
            cat_products[name] = prods

    # Collect all products with category info
    all_products = []
    product_cat_map = {}  # article → (cat_name, cat_emoji)
    for cat in categories:
        name = cat["name"]
        emoji = cat["emoji"]
        for p in cats_data.get(name, []):
            article = p.get("article", "")
            if article and article not in product_cat_map:
                product_cat_map[article] = (name, emoji)
                all_products.append(p)

    # Stats
    n_categories = 0
    n_products = 0

    # Safety: don't wipe existing pages if no products parsed
    if not all_products:
        print("WARNING: No products found, keeping existing pages")
        return

    # Clean up old generated directories
    categories_dir = SITE_DIR / "categories"
    products_dir = SITE_DIR / "products"
    if categories_dir.exists():
        shutil.rmtree(categories_dir)
    if products_dir.exists():
        shutil.rmtree(products_dir)

    # Generate category pages
    for cat in categories:
        name = cat["name"]
        products = cat_products.get(name, [])
        if not products:
            continue
        slug = transliterate(name)
        cat_dir = categories_dir / slug
        cat_dir.mkdir(parents=True, exist_ok=True)
        html = generate_category_page(cat, products, categories, updated_at)
        (cat_dir / "index.html").write_text(html, encoding="utf-8")
        n_categories += 1

    # Generate product pages
    for p in all_products:
        article = p.get("article", "")
        if not article:
            continue
        cat_name, cat_emoji = product_cat_map.get(article, ("", ""))
        prod_dir = products_dir / article
        prod_dir.mkdir(parents=True, exist_ok=True)
        html = generate_product_page(p, cat_name, cat_emoji, categories)
        (prod_dir / "index.html").write_text(html, encoding="utf-8")
        n_products += 1

    # Generate sitemap.xml
    sitemap = generate_sitemap(categories, all_products, updated_at)
    (SITE_DIR / "sitemap.xml").write_text(sitemap, encoding="utf-8")

    # Generate robots.txt
    robots = generate_robots_txt()
    (SITE_DIR / "robots.txt").write_text(robots, encoding="utf-8")

    # Save hash
    HASH_FILE.write_text(current_hash, encoding="utf-8")

    print(f"Generated: {n_categories} category pages, {n_products} product pages")
    print(f"Updated: sitemap.xml ({1 + n_categories + n_products} URLs), robots.txt")


if __name__ == "__main__":
    main()
