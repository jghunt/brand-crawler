"""
FREE brand crawler for the activewear catalogue  (GitHub Actions + Crawl4AI + Google Sheets)
------------------------------------------------------------------------------------------
Covers the brands that block the Google Apps Script (brand_list › scrape_method = crawl4ai):
DFYNE, Alphalete, FLEO, Gymshark, lululemon, PUMA, adidas, NikeSKIMS, Under Armour, Fabletics.

For each brand:
  1. Shopify brands: try the public JSON feed from GitHub's servers first (often allowed here).
  2. Otherwise open the women's listing pages in a real headless browser (Crawl4AI / Chromium),
     scroll, collect product links, open every product page and read the brand's own
     structured product data (schema.org JSON-LD: name, price, currency, colour, images…)
     plus the page text (fabric %, inseam, rise, compression, squat-proof, features).
  3. Same scope rule as the Apps Script: WOMEN'S TOPS & BOTTOMS ONLY.
  4. Upserts rows into product_list › products (same columns, key = brand_id:handle)
     and updates brand_list › last_scraped / products_found / last_error.
     Product lines (product_lines file) are rebuilt by the Apps Script on its next run
     (or straight away: product_list › Scraper › Rebuild product lines now).
  v2 (2026-11-12): FLEO price from the page's price tags + colour from the URL; inseam / fabric with the
     same rules as the Apps Script v2.7; sizes upper-case small→large; stale errors cleared on success.

Run locally:  python crawler/crawl.py --brand gymshark --max-products 30 --dry-run
"""
import argparse, asyncio, datetime as dt, hashlib, json, os, re, statistics, sys, time
from urllib.parse import urljoin, urlparse, urlencode, parse_qsl, urlunparse

import requests, yaml

BRAND_LIST_ID = '1KzNx6zizuuBf5_0OBqWp_JnaHBhcpbpB3DqOdk5xQj8'
PRODUCT_LIST_ID = '17tt4gXB7qKxGt8scyvyIM_wcQUHeV7JGFbas2ObAj0A'
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/126.0 Safari/537.36')
TODAY = dt.datetime.now(dt.timezone(dt.timedelta(hours=1))).strftime('%Y-%m-%d')

# ---------------- scope rules (same as the Apps Script) ----------------
BOTTOM = r"(legging|tights?\b|short|biker|bike|cycling|flare|bootcut|capri|skort|pants?\b|trouser|hose\b|hosen|radler|thigh ?high)"
TOP = (r"(sports? ?bra|\bbras?\b|bralette|brassi[eè]re|\bbhs?\b|sport-?bh|\btops?\b|tank|crop|cami|\btees?\b|t-?shirt|shirt|"
       r"long ?sleeve|longsleeve|short ?sleeve|base ?layer|half[- ]?zip|quarter[- ]?zip|1/[24] zip|bodysuit|unitard|catsuit|"
       r"jumpsuit|onesie|romper|leotard|playsuit|all[- ]in[- ]one|d[ée]bardeur|oberteil|halter|bandeau|bolero|shrug|vest\b|"
       r"brassi[eè]re|maillot|t-shirt)")
INCLUDE_RE = re.compile(BOTTOM + '|' + TOP, re.I)
EXCLUDE_RE = re.compile(
    r"(\bkids?\b|\bgirls?\b|\bboys?\b|shoe|sneaker|trainer|slide|sandal|sock|\bbags?\b|backpack|tote|bottle|shaker|\bcaps?\b|"
    r"\bhats?\b|beanie|headband|scrunchie|hair|towel|\bmat\b|gift ?card|e-?gift|accessor|\bbelt|lifting strap|glove|wrist|"
    r"hoodie|hoody|sweatshirt|sweater|cardigan|\bsweats?\b|sweatshort|jogger|sweatpant|track ?pant|tracksuit|jacket|coat|"
    r"gilet|puffer|parka|windbreaker|anorak|poncho|robe|dress|skirt\b|\bjeans?\b|denim|swim|bikini|underwear|knicker|thong|"
    r"brief|boxer|pyjama|pajama|sleep ?set|nightie|mystery|bundle|insurance|shipping|protection|sticker|poster|voucher|"
    r"veste|jacke|kleid|rock\b|chaussure|schuh)", re.I)
MEN_RE = re.compile(r"(\bmen\b|\bmens\b|men's|\bmale\b|for him|herren|homme|\bhim\b|männer|maenner)", re.I)
BRA_RE = re.compile(r"(sports? ?bra|\bbra\b|bralette|brassi[eè]re|\bbh\b|sport-?bh)", re.I)
WOMEN_URL_RE = re.compile(r"(women|womens|woman|damen|frauen|femme|ladies|her\b|w/)", re.I)
LISTING_HINT_RE = re.compile(r"(legging|tight|short|bra|bh|top|tank|crop|bodysuit|unitard|flare|skort|base-?layer|"
                             r"oberteil|brassiere|t-shirt|tee|long-?sleeve)", re.I)


def in_scope(title, ptype='', url='', curated=False):
    core = ' '.join([title or '', ptype or '', url or ''])
    clean = re.sub(r"women('s|s)?", ' ', core, flags=re.I)
    if MEN_RE.search(clean):
        return False
    if BRA_RE.search(title or '') and not re.search(r"(sock|shoe|bag|bottle|swim|bikini|jacket|coat|skirt|dress|hoodie|"
                                                    r"sweatshirt|jogger|sweatpant)", title or '', re.I):
        return True
    if EXCLUDE_RE.search(clean):
        return False
    return True if curated else bool(INCLUDE_RE.search(core))


def classify(s):
    s = (s or '').lower()
    if re.search(r"sports? ?bra|bralette|\bbra\b|brassi[eè]re|\bbh\b|sport-?bh", s): return 'Sports Bra'
    if re.search(r"unitard|bodysuit|catsuit|jumpsuit|onesie|romper|leotard|turnanzug|combinaison|playsuit", s): return 'Unitard / Bodysuit'
    if re.search(r"bike|biker|cycling|radler", s): return 'Bike Shorts'
    if 'skort' in s: return 'Skort'
    if 'short' in s: return 'Shorts'
    if 'flare' in s or 'bootcut' in s: return 'Flares'
    if re.search(r"capri|3/4|7/8|legging|tights?\b", s): return 'Leggings'
    if re.search(r"pant|trouser|hose", s): return 'Pants'
    if re.search(r"tank|cami|crop|top|tee|t-?shirt|shirt|long ?sleeve|vest|d[ée]bardeur|oberteil|halter|bandeau|base ?layer", s): return 'Top'
    return 'Other'


# ---------------- fact extraction from text (same regexes as the Apps Script) ----------------
FIBRE = (r"(?:recycled |recyceltes? |recyclé )?(?:nylon|polyamide?|polyamid|poliamida|polyester|elastane|elastan|elasthan|"
         r"élasthanne|spandex|lycra|cotton|baumwolle|coton|modal|viscose|viskose|lyocell|tencel|merino|wool|wolle|"
         r"polypropylene|bamboo|cupro|silk|seide|hemp|linen)")


def fabric_blend(s):
    out = []
    for n, f in re.findall(r"(\d{1,3}(?:[.,]\d)?)\s?%\s?(" + FIBRE + ")", s or '', re.I):
        x = f"{n}% {f[:1].upper()}{f[1:].lower()}"
        if x not in out: out.append(x)
    return ' / '.join(out[:6])


def inseam(title, text, cat):
    """Same rule as the Apps Script v2.7: bottoms only, title first, then an 'inseam' mention, plausible range."""
    if not re.search(r"Leggings|Shorts|Flares|Pants|Skort", cat or ''): return '', ''
    short = bool(re.search(r"Short|Skort", cat)); lo, hi = (1.5, 12) if short else (18, 36)
    unit = r"(\"|”|''|-?inch(?:es)?\b|in\b|cm\b)"
    for src, rx in ((title or '', r"(\d{1,2}(?:[.,]\d{1,2})?)\s*" + unit),
                    (text or '', r"(?:inseam|inner leg|leg length|innenbein\w*|schrittl\w*|entrejambe)[^0-9]{0,25}(\d{1,2}(?:[.,]\d{1,2})?)\s*" + unit)):
        m = re.search(rx, src, re.I)
        if not m: continue
        v = float(m.group(1).replace(',', '.')); v = v / 2.54 if 'cm' in m.group(2).lower() else v
        v = round(v + 1e-9, 2)
        if lo <= v <= hi: return v, round(v * 2.54, 1)
    return '', ''


def facts_from_text(title, text, cat=''):
    all_ = f"{title} {text}"
    inch_v, cm_v = inseam(title, text, cat or classify(title))
    el = re.search(r"(\d{1,2})\s?%\s?(elastane|spandex|lycra|elasthan)", all_, re.I)
    feats = []
    for m in re.findall(r"(scrunch[^.,;]{0,40}|v[- ]?(?:shape|back|waist)[^.,;]{0,30}|seamless|pockets?[^.,;]{0,25}|"
                        r"contour[^.,;]{0,30}|sculpt[^.,;]{0,30}|lift[^.,;]{0,25}|non[- ]?see[- ]?through|"
                        r"moisture[- ]wicking|four[- ]way stretch|4[- ]way stretch|anti[- ]camel[- ]toe|gusset)", all_, re.I):
        m = m.strip().lower()
        if m not in feats: feats.append(m)
    rise = re.search(r"(ultra[- ]high|super[- ]high|high|mid|low)[- ]?(rise|waist(?:ed)?)", all_, re.I)
    comp = re.search(r"((?:light|medium|high|firm|maximum|extra)[- ]?)?compression", all_, re.I)
    size_adv = re.search(r"(true to size|size (?:up|down)[^.]{0,60}|runs? (?:small|large)[^.]{0,40}|fits? (?:small|large)[^.]{0,40})", all_, re.I)
    return {
        'stated_inseam_in': inch_v,
        'stated_inseam_cm': cm_v,
        'stated_rise': rise.group(0) if rise else '',
        'fabric_blend': fabric_blend(all_),
        'elastane_pct': int(el.group(1)) if el else '',
        'stated_compression': comp.group(0).strip() if comp else '',
        'squat_proof_claim': 'TRUE' if re.search(r"squat[- ]?proof", all_, re.I) else '',
        'stated_features': '; '.join(feats[:10]),
        'sizing_advice': size_adv.group(0) if size_adv else '',
    }


def strip_html(h):
    h = re.sub(r"<(br|/p|/li|/h\d)[^>]*>", '. ', h or '', flags=re.I)
    h = re.sub(r"<[^>]+>", ' ', h)
    h = h.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&quot;', '"').replace('&#39;', "'")
    return re.sub(r"\s+", ' ', h).strip()


SIZE_ORDER = ['4XS', '3XS', 'XXXS', '2XS', 'XXS', 'XS', 'S', 'M', 'L', 'XL', '2XL', 'XXL', '3XL', 'XXXL', '4XL', '5XL', '6XL']


def norm_sizes(sizes):
    """Upper-case letter sizes and sort them small → large (Gymshark lists 'xxl | xl | … | xxs')."""
    s = [str(x).strip().upper() if re.fullmatch(r"[0-9]?X{0,3}[SML]|XX?L|[2-6]XL|XXXL|XXXS", str(x).strip(), re.I) else str(x).strip() for x in sizes]
    s = list(dict.fromkeys(x for x in s if x))
    if all(x in SIZE_ORDER for x in s): s.sort(key=SIZE_ORDER.index)
    return s


def size_range(sizes):
    if not sizes: return ''
    known = [s for s in SIZE_ORDER if s in [x.upper() for x in sizes]]
    if known: return f"{known[0]}-{known[-1]}"
    return f"{sizes[0]}-{sizes[-1]}"


# ---------------- currency ----------------
_RATES = {}
def chf_rate(cur):
    cur = (cur or '').upper()
    if cur == 'CHF': return 1.0
    if not cur: return None
    if cur not in _RATES:
        try:
            _RATES[cur] = requests.get(f'https://api.frankfurter.app/latest?from={cur}&to=CHF', timeout=20).json()['rates']['CHF']
        except Exception:
            _RATES[cur] = None
    return _RATES[cur]


def key_from_url(brand_id, url):
    path = urlparse(url).path.rstrip('/')
    handle = path.split('/')[-1] or path
    handle = re.sub(r"\.html?$", '', handle)
    segs = [x for x in path.split('/') if x]
    # style-code URLs (adidas /optime-leggings/IT1234.html, lululemon /p/<slug>/LW5DK3S.html) → slug-code
    if len(segs) > 1 and re.fullmatch(r"[A-Za-z0-9_]{4,12}", handle) and re.search(r"\d", handle):
        handle = re.sub(r"\.html?$", '', segs[-2]) + '-' + handle
    return f"{brand_id}:{handle.lower()}"


def base_row(brand, url, title):
    return {'product_key': key_from_url(brand['brand_id'], url), 'brand_id': brand['brand_id'],
            'brand_name': brand['brand_name'], 'status': 'live', 'product_title': title, 'product_url': url,
            'last_seen': TODAY, 'source': 'crawl4ai'}


# ---------------- 1) Shopify JSON from GitHub ----------------
def shopify_products(root):
    out, s = [], requests.Session()
    s.headers.update({'User-Agent': UA, 'Accept': 'application/json'})
    for page in range(1, 41):
        r = s.get(f"{root}/products.json?limit=250&page={page}", timeout=30)
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code} on {root}/products.json")
        lst = r.json().get('products', [])
        if not lst: break
        out += lst
        if len(lst) < 250: break
        time.sleep(0.5)
    return out


def row_from_shopify(brand, base, p, curated):
    if not in_scope(p.get('title'), p.get('product_type'), p.get('handle'), curated):
        return None
    opts = p.get('options') or []
    def vals(rx):
        for o in opts:
            if re.search(rx, o.get('name', ''), re.I): return o.get('values') or []
        return []
    colours = vals(r"colou?r|shade|farbe|couleur")
    sizes = vals(r"size|grösse|größe|taille")
    prices = [float(v['price']) for v in p.get('variants', []) if v.get('price')]
    comps = [float(v['compare_at_price']) for v in p.get('variants', []) if v.get('compare_at_price')]
    cur_p = min(prices) if prices else ''
    full = max(comps) if comps and cur_p != '' and max(comps) > cur_p else cur_p
    text = strip_html(p.get('body_html'))
    url = f"{base}/products/{p['handle']}"
    row = base_row(brand, url, p['title'])
    row.update({'source_product_id': str(p.get('id', '')), 'product_type': p.get('product_type', ''),
                'scope_category': classify(f"{p['title']} {p.get('product_type','')}"), 'description': text[:1500],
                'price_current': cur_p, 'price_full': full, 'currency': brand.get('currency') or '',
                'on_sale': 'TRUE' if comps and cur_p != '' and max(comps) > cur_p else 'FALSE',
                'colours': ' | '.join(colours), 'colour_count': len(colours) or '', 'sizes': ' | '.join(sizes),
                'size_range': size_range(sizes),
                'image_urls': ' | '.join(i['src'] for i in (p.get('images') or [])[:3]),
                'brand_tags': ', '.join(p.get('tags') or [])[:500],
                'published_at': (p.get('published_at') or '')[:10], 'brand_updated_at': (p.get('updated_at') or '')[:10],
                'source': 'shopify_json (github)'})
    row['sizes'] = ' | '.join(norm_sizes(sizes)); row['size_range'] = size_range(norm_sizes(sizes))
    row.update(facts_from_text(p['title'], text, row['scope_category']))
    return row


# ---------------- 2) browser crawl ----------------
SCROLL_JS = """
for (let i = 0; i < 12; i++) {
  window.scrollTo(0, document.body.scrollHeight);
  await new Promise(r => setTimeout(r, 900));
  const more = [...document.querySelectorAll('button, a')].find(b => /load more|show more|mehr laden|voir plus|weitere/i.test(b.innerText || ''));
  if (more) { try { more.click(); } catch (e) {} }
}
"""


def json_ld_products(html):
    out = []
    for block in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', html or '', re.S | re.I):
        try:
            data = json.loads(block.strip())
        except Exception:
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            d = stack.pop()
            if isinstance(d, dict):
                t = d.get('@type')
                types = t if isinstance(t, list) else [t]
                if 'Product' in types or 'ProductGroup' in types:
                    out.append(d)
                for k in ('@graph', 'hasVariant', 'itemListElement'):
                    v = d.get(k)
                    if isinstance(v, list): stack += v
            elif isinstance(d, list):
                stack += d
    return out


def row_from_page(brand, url, html, markdown, curated):
    prods = json_ld_products(html)
    if not prods:
        return None
    main = prods[0]
    title = main.get('name') or ''
    if not title or not in_scope(title, main.get('category', '') if isinstance(main.get('category'), str) else '', url, curated):
        return None
    offers = []
    for p in prods:
        o = p.get('offers')
        if isinstance(o, dict): o = [o] if o.get('@type') != 'AggregateOffer' else [o]
        for x in (o or []):
            if isinstance(x, dict): offers.append(x)
    prices, cur = [], brand.get('currency') or ''
    for o in offers:
        for k in ('price', 'lowPrice', 'highPrice'):
            try:
                if o.get(k) not in (None, ''): prices.append(float(str(o[k]).replace(',', '.')))
            except ValueError:
                pass
        cur = o.get('priceCurrency') or cur
    colours, sizes = [], []
    for p in prods:
        c = p.get('color')
        if isinstance(c, str) and c and c not in colours: colours.append(c)
        s = p.get('size')
        if isinstance(s, str) and s and s not in sizes: sizes.append(s)
    sizes = norm_sizes(sizes)
    # v2: no price in the structured data (FLEO) → the page's price meta tags
    if not prices:
        for rx in (r'<meta[^>]+(?:property|name)="(?:product:price:amount|og:price:amount)"[^>]+content="([\d.,]+)"',
                   r'<meta[^>]+content="([\d.,]+)"[^>]+(?:property|name)="(?:product:price:amount|og:price:amount)"',
                   r'itemprop="price"[^>]+content="([\d.,]+)"'):
            m = re.search(rx, html or '', re.I)
            if m:
                try: prices.append(float(m.group(1).replace(',', '')))
                except ValueError: pass
                break
        m = re.search(r'(?:product:price:currency|og:price:currency)"[^>]+content="([A-Z]{3})"', html or '', re.I)
        if m: cur = m.group(1)
    # v2: no colour in the structured data → the colour words in the URL before the product name
    #     (FLEO /products/heather-sailor-blue-apex-contour-short-… → "Heather Sailor Blue")
    if not colours:
        handle = urlparse(url).path.rstrip('/').split('/')[-1]
        tslug = re.sub(r"[^a-z0-9]+", '-', title.lower()).strip('-')
        first = tslug.split('-')[0] if tslug else ''
        if first and ('-' + first + '-') in ('-' + handle + '-'):
            pre = ('-' + handle + '-').split('-' + first + '-')[0].strip('-')
            if pre and len(pre) < 40: colours = [pre.replace('-', ' ').title()]
    imgs = main.get('image') or []
    if isinstance(imgs, str): imgs = [imgs]
    imgs = [i if isinstance(i, str) else i.get('url', '') for i in imgs][:3]
    desc = strip_html(main.get('description') or '')
    text = desc + ' ' + (markdown or '')[:20000]
    row = base_row(brand, url.split('?')[0], title)
    row.update({'source_product_id': str(main.get('productID') or main.get('sku') or main.get('productGroupID') or ''),
                'product_type': main.get('category', '') if isinstance(main.get('category'), str) else '',
                'scope_category': classify(title + ' ' + url), 'description': desc[:1500],
                'price_current': min(prices) if prices else '', 'price_full': max(prices) if prices else '',
                'currency': cur, 'on_sale': '',
                'colours': ' | '.join(colours), 'colour_count': len(colours) or '',
                'sizes': ' | '.join(sizes), 'size_range': size_range(sizes),
                'image_urls': ' | '.join(i for i in imgs if i)})
    row.update(facts_from_text(title, text, row['scope_category']))
    return row


async def crawl_brand_browser(brand, cfg, max_products, log):
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
    prod_re = re.compile(cfg.get('product_url') or r'/products/[^/?#]+')
    host = urlparse(brand['website']).netloc
    bcfg = BrowserConfig(headless=True, user_agent=UA, viewport_width=1366, viewport_height=900)
    list_cfg = CrawlerRunConfig(cache_mode=CacheMode.BYPASS, js_code=SCROLL_JS, page_timeout=90000,
                                delay_before_return_html=2.0, remove_overlay_elements=True, magic=True,
                                simulate_user=True, override_navigator=True)
    prod_cfg = CrawlerRunConfig(cache_mode=CacheMode.BYPASS, page_timeout=60000, delay_before_return_html=1.5,
                                remove_overlay_elements=True, magic=True, simulate_user=True, override_navigator=True)

    start = list(cfg.get('start_urls') or [])
    start += [u.strip() for u in re.split(r'[\n,|]+', brand.get('collection_urls') or '') if u.strip().startswith('http')]
    rows, errors, product_urls = {}, [], []
    async with AsyncWebCrawler(config=bcfg) as crawler:
        # discover listing pages when needed
        if cfg.get('discover_from'):
            for u in cfg['discover_from']:
                res = await crawler.arun(u, config=list_cfg)
                if not res.success:
                    errors.append(f"discover {u}: {res.error_message or res.status_code}"); continue
                for l in res.links.get('internal', []):
                    href = urljoin(u, l.get('href', ''))
                    path = urlparse(href).path
                    if prod_re.search(path):
                        product_urls.append(href)
                    elif (WOMEN_URL_RE.search(href) or 'women' in u.lower() or 'femme' in u or 'frauen' in u
                          or 'nikeskims' in u) and LISTING_HINT_RE.search(path) and not MEN_RE.search(path):
                        start.append(href)
        start = list(dict.fromkeys(start))[:25]
        log(f"  listing pages: {len(start)}")
        for u in start:
            pages = [u]
            if cfg.get('page_param'):
                pages += [f"{u}{'&' if '?' in u else '?'}{cfg['page_param']}={n}" for n in range(2, 6)]
            for pu in pages:
                res = await crawler.arun(pu, config=list_cfg)
                if not res.success:
                    errors.append(f"{pu}: {res.error_message or res.status_code}"); break
                found = [urljoin(pu, l.get('href', '')) for l in res.links.get('internal', [])
                         if prod_re.search(urlparse(urljoin(pu, l.get('href', ''))).path)]
                if not found: break
                before = len(set(product_urls)); product_urls += found
                if len(set(product_urls)) == before: break
        product_urls = [u for u in dict.fromkeys(x.split('?')[0].split('#')[0] for x in product_urls)
                        if urlparse(u).netloc in ('', host) or host.split('.', 1)[-1] in urlparse(u).netloc]
        product_urls = product_urls[:max_products]
        log(f"  product pages: {len(product_urls)}")
        for i in range(0, len(product_urls), 6):
            batch = product_urls[i:i + 6]
            results = await crawler.arun_many(batch, config=prod_cfg)
            for res in results:
                if not res.success:
                    errors.append(f"{res.url}: {res.error_message or res.status_code}"); continue
                md = res.markdown if isinstance(res.markdown, str) else getattr(res.markdown, 'raw_markdown', '') or ''
                row = row_from_page(brand, res.url, res.html, md, curated=True)
                if row: rows[row['product_key']] = row
    return list(rows.values()), errors


# ---------------- Google Sheets ----------------
def sheets():
    import gspread
    from google.oauth2.service_account import Credentials
    info = json.loads(os.environ['GOOGLE_SERVICE_ACCOUNT_JSON'])
    creds = Credentials.from_service_account_info(info, scopes=['https://www.googleapis.com/auth/spreadsheets'])
    return gspread.authorize(creds)


def col_letter(n):
    s = ''
    while n:
        n, r = divmod(n - 1, 26); s = chr(65 + r) + s
    return s


RECOMPUTED = {'stated_inseam_in', 'stated_inseam_cm', 'fabric_blend'}   # blank result clears an old wrong value
HASH_FIELDS = ['product_title', 'description', 'price_full', 'colours', 'sizes', 'fabric_blend', 'stated_inseam_in',
               'stated_rise', 'stated_compression', 'squat_proof_claim', 'stated_features', 'image_urls']


def write_products(gc, brand_id, rows, dry):
    ws = gc.open_by_key(PRODUCT_LIST_ID).worksheet('products')
    head = ws.row_values(1)
    col = {h: i for i, h in enumerate(head)}
    keys = ws.col_values(col['product_key'] + 1)
    brands = ws.col_values(col['brand_id'] + 1)
    index = {k: i + 1 for i, k in enumerate(keys) if i > 0 and k}
    existing_rows = [r for k, r in index.items() if k.startswith(brand_id + ':')]
    old = {}
    if existing_rows:
        ranges = [f"A{r}:{col_letter(len(head))}{r}" for r in existing_rows]
        for r, vals in zip(existing_rows, ws.batch_get(ranges)):
            v = (vals[0] if vals else []) + [''] * len(head)
            old[r] = v[:len(head)]
    updates, appends, seen = [], [], set()
    for obj in rows:
        k = obj['product_key']; seen.add(k)
        r = index.get(k)
        line = old.get(r) if r else None
        if line is None:
            line = [''] * len(head); line[col['first_seen']] = TODAY
        for f, v in obj.items():
            if f in col and (v not in ('', None) or f in RECOMPUTED):
                line[col[f]] = '' if v is None else v
        rate = chf_rate(line[col['currency']])
        if rate and str(line[col['price_full']]).strip():
            try: line[col['price_full_chf']] = round(float(line[col['price_full']]) * rate, 2)
            except ValueError: pass
        h = hashlib.md5('§'.join(str(line[col[f]]) for f in HASH_FIELDS).encode()).hexdigest()
        if line[col['content_hash']] != h:
            line[col['content_hash']] = h; line[col['needs_assessment']] = 'TRUE'
        (updates if r else appends).append((r, line))
    # products not found any more → discontinued? (only if this crawl looks complete)
    if rows and len(rows) >= 0.5 * max(1, len(existing_rows)):
        for r in existing_rows:
            k = keys[r - 1]
            if k not in seen and str(old[r][col['status']]).startswith('live'):
                line = old[r]; line[col['status']] = 'discontinued?'
                line[col['notes']] = (f"Not found by crawler on {TODAY}. " + str(line[col['notes']]))[:500]
                updates.append((r, line))
    if dry:
        return len(updates), len(appends)
    last = col_letter(len(head))
    for i in range(0, len(updates), 400):
        ws.batch_update([{'range': f"A{r}:{last}{r}", 'values': [line]} for r, line in updates[i:i + 400]],
                        value_input_option='RAW')
    if appends:
        ws.append_rows([line for _, line in appends], value_input_option='RAW')
    return len(updates), len(appends)


def write_brand(gc, brand, found, error, dry):
    if dry: return
    ws = gc.open_by_key(BRAND_LIST_ID).worksheet('brands')
    head = ws.row_values(1)
    cells = []
    for name, val in (('last_scraped', TODAY), ('products_found', found), ('last_error', error[:450])):
        if name in head:
            cells.append({'range': f"{col_letter(head.index(name) + 1)}{brand['_row']}", 'values': [[val]]})
    if cells: ws.batch_update(cells, value_input_option='RAW')


# ---------------- main ----------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--brand', help='only this brand_id')
    ap.add_argument('--max-products', type=int, default=600)
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()
    log = lambda m: print(m, flush=True)
    cfg_all = yaml.safe_load(open(os.path.join(os.path.dirname(__file__), 'brands.yaml'))) or {}
    gc = sheets()
    bws = gc.open_by_key(BRAND_LIST_ID).worksheet('brands')
    vals = bws.get_all_values()
    head = vals[0]
    brands = []
    for i, r in enumerate(vals[1:], start=2):
        b = dict(zip(head, r + [''] * len(head))); b['_row'] = i
        if b.get('status', '').lower() == 'active' and b.get('scrape_method') == 'crawl4ai':
            if not a.brand or b['brand_id'] == a.brand: brands.append(b)
    log(f"{len(brands)} brand(s) to crawl")
    for b in brands:
        bid = b['brand_id']; cfg = cfg_all.get(bid, {}) or {}
        log(f"== {b['brand_name']} ({bid})")
        rows, errors = [], []
        if cfg.get('shopify'):
            base = re.match(r'https?://[^/]+', b['website']).group(0)
            try:
                rows = [x for x in (row_from_shopify(b, base, p, False) for p in shopify_products(base)) if x]
                log(f"  shopify json: {len(rows)} in-scope products")
            except Exception as e:
                errors.append(f"shopify json: {e}")
        if not rows:
            try:
                rows, errs = asyncio.run(crawl_brand_browser(b, cfg, a.max_products, log))
                errors += errs[:5]
            except Exception as e:
                errors.append(f"browser: {e}")
        log(f"  in-scope products: {len(rows)}")
        if not rows:
            errors.insert(0, 'BLOCKED or no products found by crawler → try manual_chrome')
        else:
            errors = []      # v2: earlier failed attempts (e.g. 'shopify json: 404') don't matter once products were found
        try:
            up, ap_ = write_products(gc, bid, rows, a.dry_run) if rows else (0, 0)
            log(f"  written: {up} updated, {ap_} new")
        except Exception as e:
            errors.append(f"sheet write: {e}")
        write_brand(gc, b, len(rows), ' | '.join(str(e) for e in errors), a.dry_run)


if __name__ == '__main__':
    main()
