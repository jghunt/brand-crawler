// Free Shopify scraper -> collection_items rows (activewear_data_model column order).
// Usage: node scrape.mjs [brand_id ...]   (no args = all brands in brands.json)
import fs from 'fs';
const UA={'user-agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131 Safari/537.36','accept':'application/json'};
const HEAD=['product_key','collection_key','brand_id','brand_name','status','product_title','product_url','source_product_id','product_type','scope_category','product_line','description','price_current','price_full','currency','price_full_chf','on_sale','colours','colour_count','sizes','size_range','stated_inseam_in','stated_inseam_cm','stated_rise','fabric_name','fabric_blend','elastane_pct','stated_compression','squat_proof_claim','stated_features','sizing_advice','size_chart_url','image_urls','brand_tags','published_at','brand_updated_at','first_seen','last_seen','content_hash','needs_assessment','source','notes'];
const today=new Date().toISOString().slice(0,10);
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const MEN=/(\bmen'?s\b|\bmens\b|\bmale\b|\bboys?\b|\bkids?\b|\bgirls\b|\bjunior\b|\byouth\b|department_man\b|\bfor him\b)/i;
const ACC=/\b(bottles?|bags?|backpacks?|socks?|caps?|hats?|beanies?|gift\s*cards?|shoes?|sneakers?|slides?|towels?|mats?|headbands?|scrunchies?|hair|jewel\w*|necklaces?|candles?|stickers?|keyrings?|wallets?|belts?|gloves?|wrist\w*|lifting|shakers?|insurance|shipping|protection|samples?|e-?gift|vouchers?|water)\b/i;
const NOUN=/\b(women'?s|womens|ladies|leggings?|tights|joggers?|sweatpants?|pants?|trousers?|bike\s*shorts|biker\s*shorts|cycling\s*shorts|shorts?|sports?\s*bras?|bras?|bralettes?|t-shirts?|tees?|shirts?|tops?|unitards?|bodysuits?|jumpsuits?|rompers?|skorts?|skirts?|underwear|with|and|the|for)\b/gi;
async function getJSON(url){for(let a=0;a<12;a++){const r=await fetch(url,{headers:UA});if(r.status===429){const ra=+(r.headers.get('retry-after')||60);await sleep((ra+5)*1000);continue}if(!r.ok)throw new Error('HTTP '+r.status);return r.json()}throw new Error('rate limited')}
function rowsFor(cfg,all){const out=[];
for(const x of all){
 const tags=(x.tags||[]); const meta=(x.title+' '+x.product_type+' '+tags.join(' '));
 if(cfg.women_tag){ if(!tags.includes(cfg.women_tag)) continue } else if(MEN.test(meta)) continue;
 if(ACC.test(x.title+' '+x.product_type)) continue;
 const t=x.title, tt=t.toLowerCase(), tts=tt.replace(/short[\s-]*sleeves?/g,''), tl=meta.toLowerCase();
 let ty= /bikini/.test(tt)?(/bottom|brief|short/.test(tts)?'bikini bottom':'bikini top'): /bodysuit|jumpsuit|unitard|romper|onesie|all[\s-]in[\s-]one|catsuit/.test(tt)?'bodysuit': /\bbras?\b|bralette/.test(tt)?'sports bra': /flare/.test(tt)?'flares': /skort|skirt/.test(tt)?'skort': /short/.test(tts)?'shorts': /legging|tights|capri/.test(tt)?'leggings': /pant|jogger|trouser|sweatpant/.test(tt)?'pants': /top|tank|tee|shirt|sleeve|hoodie|sweat|crop|cami|jacket|pullover|vest|zip/.test(tt)?'top': /\bbras?\b/.test(tl)?'sports bra': /legging/.test(tl)?'leggings': /short/.test(tl)?'shorts':'other';
 let s=t.replace(/\(.*?\)/g,' ').replace(/\d+([.,]\d+)?\s*(''|"|â€|cm\b|inch(es)?\b|in\b)/gi,' ').replace(new RegExp('^'+cfg.name.replace(/[^\w ]/g,'.')+'\\s*','i'),'');
 if(cfg.cut) s=s.replace(new RegExp(cfg.cut,'gi'),' ');
 s=s.replace(/\s[-â€“|]\s.*$/,m=>/seam|waist|rise|back|neck|pocket|scrunch|flare|lift|sculpt|v-|halter|strap/i.test(m)?' '+m:'');
 s=s.replace(/short[\s-]*sleeves?/gi,'shortsleeve').replace(NOUN,' ').replace(/shortsleeve/g,'Short Sleeve').replace(/[,|/â€“]/g,' ').replace(/\s-\s/g,' ').replace(/\s+/g,' ').replace(/^[\s-]+|[\s-]+$/g,'').trim();
 if(!s) s=ty;
 const opt=n=>{const o=(x.options||[]).find(o=>n.test(o.name));return o?o.values:[]};
 let cols=opt(/colou?r|farbe|couleur|shade/i); const sizes=opt(/size|grÃ¶ÃŸe|taille/i);
 if(!cols.length){const m=t.match(/\s[-â€“|]\s([^-â€“|]+)$/); if(m && !/seam|waist|rise|back|neck|pocket|scrunch|flare|lift/i.test(m[1])) cols=[m[1].trim()];}
 const pr=x.variants.map(v=>+v.price), cmp=x.variants.map(v=>+(v.compare_at_price||0));
 const pc=Math.min(...pr), pf=Math.max(Math.max(...cmp),Math.max(...pr));
 const body=(x.body_html||'').replace(/<[^>]+>/g,' ').replace(/&[a-z#0-9]+;/g,' ').replace(/\s+/g,' ').trim();
 const bl=(body.match(/\d+([.,]\d+)?\s*%\s*(recycled\s+)?(nylon|polyamide?|elastane|spandex|polyester|cotton|lycra|modal|viscose|lyocell|tencel|wool|cashmere|rayon|elasthan\w*|polyamid\w*|baumwolle|Ã©lasthanne|coton)/gi)||[]);
 const blend=[...new Set(bl.map(b=>b.replace(/\s+/g,' ')))].join(' / ');
 const el=(blend.match(/(\d+([.,]\d+)?)\s*%\s*(elastane|spandex|lycra|elasthan\w*|Ã©lasthanne)/i)||[])[1]||'';
 const inch=(t.match(/(\d+([.,]\d+)?)\s*(''|"|â€|inch)/i)||[])[1]||'', cm=(t.match(/(\d+([.,]\d+)?)\s*cm/i)||[])[1]||'';
 const rise=/high[\s-]*(waist|rise)/i.test(t)?'high':/mid[\s-]*(waist|rise)/i.test(t)?'mid':/low[\s-]*(waist|rise)/i.test(t)?'low':'';
 const feat=[[/pocket/i,'pockets'],[/scrunch/i,'scrunch'],[/seamless/i,'seamless'],[/no front seam/i,'no front seam'],[/compression/i,'compression'],[/moisture|sweat-wicking|quick.?dry/i,'moisture-wicking'],[/4-way|four-way/i,'4-way stretch'],[/removable pad|padded/i,'removable pads'],[/push.?up/i,'push-up'],[/squat.?proof|non-see-through|not see.?through/i,'squat-proof'],[/built.?in bra|shelf bra/i,'built-in bra']].filter(([r])=>r.test(t+' '+body)).map(f=>f[1]);
 const fab=cfg.fabric_tag?((tags.find(g=>g.startsWith(cfg.fabric_tag))||'').slice(cfg.fabric_tag.length)):'';
 out.push([cfg.brand+':'+x.handle,'',cfg.brand,cfg.name,'live',t,cfg.origin+'/products/'+x.handle,x.id,ty,x.product_type||'',s,body.slice(0,300),pc,pf,cfg.cur,'',pf>pc?'TRUE':'FALSE',cols.join(' | '),cols.length,sizes.join(' | '),sizes.length?sizes[0]+'-'+sizes[sizes.length-1]:'',inch,cm||(inch?Math.round(inch*2.54):''),rise,fab,blend,el,/compression/i.test(body)?'compression':'',/squat.?proof|non-see-through/i.test(t+' '+body)?'TRUE':'',feat.join('; '),'','',(x.images||[]).map(i=>i.src.split('?')[0]).join(' | '),tags.join(', ').slice(0,500),(x.published_at||'').slice(0,10),(x.updated_at||'').slice(0,10),today,today,String(x.updated_at).replace(/\D/g,'').slice(0,14)+'-'+pf,'TRUE','shopify_json','scraped from '+cfg.origin.replace('https://','')+' on '+today].map(v=>String(v).replace(/[\t\n\r]/g,' ')));
}
return out}
const brands=JSON.parse(fs.readFileSync(new URL('./brands.json',import.meta.url)));
const pick=process.argv.slice(2); const log=[];
for(const cfg of brands.filter(b=>!pick.length||pick.includes(b.brand))){
 try{let all=[];for(let p=1;p<80;p++){const j=await getJSON(`${cfg.origin}/products.json?limit=250&page=${p}`);if(!j.products||!j.products.length)break;all.push(...j.products);await sleep(3000)}
  const rows=rowsFor(cfg,all);
  fs.writeFileSync(new URL(`./out/items_${cfg.brand}.tsv`,import.meta.url),[HEAD,...rows].map(r=>r.join('\t')).join('\n'));
  log.push({brand:cfg.brand,products:all.length,rows:rows.length,blend:rows.filter(r=>r[25]).length});console.log(new Date().toISOString(),cfg.brand,all.length,rows.length);await sleep(20000);
 }catch(e){log.push({brand:cfg.brand,error:e.message});console.log(new Date().toISOString(),cfg.brand,'ERROR',e.message)}
}
fs.writeFileSync(new URL('./out/log_'+today+'.json',import.meta.url),JSON.stringify(log,null,1));
console.log('DONE');

