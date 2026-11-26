# colour written in quotes at the end of the title (TEVEO: Timeless Scrunch Leggings ‘Black’) -> colours + clean product_line
import csv,re,sys,glob
csv.field_size_limit(10**9)
Q=re.compile(r"\s*[‘'\"“„«]([^‘’'\"“”„«»]{2,40})[’'\"”»]\s*$")
tot=0
for p in sys.argv[1:]:
    R=list(csv.reader(open(p,encoding='utf-8'),delimiter='\t',quoting=csv.QUOTE_NONE)); h=R[0]; I={k:i for i,k in enumerate(h)}; n=0
    for r in R[1:]:
        if len(r)<len(h): continue
        m=Q.search(r[I['product_title']])
        if not m: continue
        c=m.group(1).strip()
        if not r[I['colours']]: r[I['colours']]=c; r[I['colour_count']]='1'
        r[I['product_line']]=Q.sub('',r[I['product_line']]).strip(); n+=1
    if n: open(p,'w',encoding='utf-8').write('\n'.join('\t'.join(x) for x in R)); print(p.split('/')[-1],n); tot+=n
print('fixed',tot)
