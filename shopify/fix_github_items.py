# Post-fix for items scraped by shopify/scrape.mjs (GitHub): strip the colour from product_line, French garment words
import csv,re,sys
csv.field_size_limit(10**9)
FR=[(r'brassi[eè]re',  'sports bra'),(r'd[ée]bardeur','top'),(r'\bjupe[- ]short','skort'),(r'\bcycliste\b','shorts')]
for p in sys.argv[1:]:
    R=list(csv.reader(open(p,encoding='utf-8'),delimiter='\t',quoting=csv.QUOTE_NONE)); h=R[0]; I={k:i for i,k in enumerate(h)}; a=b=0
    for r in R[1:]:
        if len(r)<len(h): continue
        pl=r[I['product_line']]
        for c in sorted([x.strip() for x in r[I['colours']].split('|') if x.strip()],key=len,reverse=True):
            new=re.sub(r'(?i)[\s\-–—/]*\b'+re.escape(c)+r'\s*$','',pl).strip()
            if new and new!=pl: pl=new; a+=1; break
        r[I['product_line']]=pl
        if r[I['product_type']]=='other':
            for pat,t in FR:
                if re.search(pat,r[I['product_title']],re.I): r[I['product_type']]=t; b+=1; break
    open(p,'w',encoding='utf-8').write('\n'.join('\t'.join(x) for x in R))
    if a or b: print(p.split('/')[-1],'colour stripped',a,'type fixed',b)
