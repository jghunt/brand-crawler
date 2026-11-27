# v3 id standard for the activewear catalogue (root sheets of *aw)
# - everything lowercase
# - inside one part of an id: words separated by single spaces, exactly as written
#   ("-", "/", ".", "_" and other punctuation become a space; ™ and ® are dropped;
#   "&" is kept; "+" becomes "and")
# - "-" only between the parts of an id; never ":" or "_"
# - every id column is named <thing>_id
#
#   brand_id        brand                                   pursue fitness
#   collection_id   brand-collection-type                   adanola-active hybrid-shorts
#   colour_id       collection_id-colour                    adanola-active hybrid-shorts-navy blue
#   measurement_id  collection_id-size(-length)             adanola-active hybrid-shorts-xxs
#   variant_id      measurement_id-colour                   adanola-active hybrid-shorts-xxs-navy blue
#   item_id         brand-page name (scraped web page)      adanola-active hybrid shorts navy blue
#   ladder_id       brand-ladder-rung                       crzyoga-leggings-6
#   fit_id          brand-size line                         adanola-bottoms
#   running numbers prefix-0001                             w-0001, pa-0001, c-0001, p-0001
#
# vocab values (selects, statuses, types) use spaces instead of "_" (sports bra, dark earth,
# active rotation). column headers keep snake_case (variant_id, size_code).
import re

_DROP = re.compile(r'[™®©]')
_BAD = re.compile(r'[^a-z0-9à-ÿ&]+')


def part(s):
    """one part of an id: lowercase words separated by single spaces"""
    s = str(s or '').lower()
    s = _DROP.sub('', s).replace('+', ' and ')
    return _BAD.sub(' ', s).strip()


def join(*parts):
    return '-'.join(part(p) for p in parts if str(p or '').strip())


def vocab(s):
    """select / status / type value: underscores become spaces"""
    return re.sub(r'\s+', ' ', str(s or '').replace('_', ' ')).strip() if s else s


# ---- old (v2) -> new (v3) converters ------------------------------------------------
def brand(old):                    # pursue-fitness -> pursue fitness
    return part(old)


def collection(old):               # adanola:active-hybrid:shorts -> adanola-active hybrid-shorts
    if ':' not in old:
        return old
    return join(*old.split(':'))


def extend(parent_id, *parts):     # parent id (already v3) + more parts
    rest = join(*parts)
    return parent_id + '-' + rest if rest else parent_id


def colour(collection_old, colour_name):
    return extend(collection(collection_old), colour_name)


def measurement(collection_old, size, length=''):
    return extend(collection(collection_old), size, length)


def variant(collection_old, size, length, colour_name):
    return extend(collection(collection_old), size, length, colour_name)


def item(old):                     # adanola:active-hybrid-shorts-navy-blue -> adanola-active hybrid shorts navy blue
    b, _, h = old.partition(':')
    return join(b, h)


def ladder(old):                   # crzyoga:leggings:6 -> crzyoga-leggings-6
    return join(*old.split(':'))


def fit(old):                      # adanola:bottoms -> adanola-bottoms
    return join(*old.split(':'))


def number(old, width=4):          # w-001 -> w-0001
    m = re.fullmatch(r'([a-z]+)-(\d+)', str(old or ''))
    return f'{m.group(1)}-{int(m.group(2)):0{width}d}' if m else old


def to_internal_brand(new):        # v3 brand id back to the build's internal slug
    return str(new).replace(' ', '-')
