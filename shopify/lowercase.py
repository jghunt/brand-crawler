# Lowercase rule for the activewear catalogue (root sheets of *aw):
# every text value is written in lowercase. Urls, emails and drive ids keep their case.
import csv, json, re, sys
URL = re.compile(r'(https?://\S+|www\.\S+|\b[\w.+-]+@[\w-]+\.[\w.]+)')
def lower_text(s):
    if not isinstance(s, str): return s
    parts = URL.split(s)
    return ''.join(p if i % 2 else p.lower() for i, p in enumerate(parts))
def lower_rows(rows):
    return [[lower_text(v) for v in r] for r in rows]
def lower_tsv(path):
    csv.field_size_limit(10**9)
    R = list(csv.reader(open(path, encoding='utf-8'), delimiter='\t', quoting=csv.QUOTE_NONE))
    open(path, 'w', encoding='utf-8').write('\n'.join('\t'.join(lower_text(v) for v in r) for r in R) + '\n')
def lower_json_table(path):
    T = json.load(open(path)); json.dump(lower_rows(T), open(path, 'w'))
if __name__ == '__main__':
    for p in sys.argv[1:]:
        (lower_json_table if p.endswith('.json') else lower_tsv)(p); print('lowercased', p)
