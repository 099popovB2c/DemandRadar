#!/usr/bin/env python3
import argparse, csv, json, math, os, re, sys, time, urllib.parse, urllib.request
from collections import Counter
from datetime import datetime, timezone

UA = 'DemandRadar/0.2 (+https://github.com/099popovB2c/DemandRadar)'
STOP = set('a an the and or to of for in on with is are was were be this that it i you we they my our your app software tool program need want looking alternative wish there like have has had can could would should'.split())
TEMPLATES = ['"looking for" app','"is there an app"','"alternative to"','"wish there was"','"need a tool"','"looking for software"']
INTENT_PATTERNS = [
    (re.compile(r'\bwould pay\b', re.I), 5), (re.compile(r'\bwish there (?:was|were)\b', re.I), 5),
    (re.compile(r'\bis there an? (?:app|tool|software)\b', re.I), 4), (re.compile(r'\blooking for\b', re.I), 3),
    (re.compile(r'\bneed an? (?:app|tool|software)\b', re.I), 4), (re.compile(r'\balternative to\b|\breplacement for\b', re.I), 3),
    (re.compile(r"\bcan't find\b|\bcannot find\b|\bfrustrat(?:ed|ing)\b", re.I), 3),
    (re.compile(r'\bmanual(?:ly)?\b|\bspreadsheet\b|\bworkaround\b', re.I), 1),
]

def fetch_json(url, headers=None, timeout=12):
    h={'User-Agent':UA,'Accept':'application/json'}; h.update(headers or {})
    req=urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r: return json.loads(r.read().decode('utf-8'))

def reddit(query, limit=30):
    data=fetch_json(f'https://www.reddit.com/search.json?q={urllib.parse.quote(query)}&sort=relevance&limit={min(limit,100)}&t=year')
    out=[]
    for x in data.get('data',{}).get('children',[]):
        d=x.get('data',{}); out.append({'source':'reddit','title':d.get('title',''),'text':d.get('selftext',''),'url':'https://reddit.com'+d.get('permalink',''),'score':int(d.get('score') or 0),'comments':int(d.get('num_comments') or 0),'created':d.get('created_utc')})
    return out

def hn(query, limit=30):
    data=fetch_json(f'https://hn.algolia.com/api/v1/search?query={urllib.parse.quote(query)}&tags=story&hitsPerPage={min(limit,100)}')
    return [{'source':'hn','title':d.get('title') or '','text':d.get('story_text') or '','url':d.get('url') or f"https://news.ycombinator.com/item?id={d.get('objectID')}",'score':int(d.get('points') or 0),'comments':int(d.get('num_comments') or 0),'created':d.get('created_at_i')} for d in data.get('hits',[])]

def github(query, limit=30):
    headers={}; tok=os.getenv('GITHUB_TOKEN')
    if tok: headers['Authorization']=f'Bearer {tok}'
    data=fetch_json(f'https://api.github.com/search/issues?q={urllib.parse.quote(query+" is:issue")}&per_page={min(limit,100)}&sort=reactions&order=desc',headers)
    return [{'source':'github','title':d.get('title',''),'text':d.get('body') or '','url':d.get('html_url',''),'score':int(d.get('reactions',{}).get('total_count') or 0),'comments':int(d.get('comments') or 0),'created':iso_epoch(d.get('created_at'))} for d in data.get('items',[])]

def iso_epoch(value):
    if not value: return None
    try: return datetime.fromisoformat(value.replace('Z','+00:00')).timestamp()
    except ValueError: return None

def canonical_url(url):
    try:
        u=urllib.parse.urlsplit(url); return urllib.parse.urlunsplit((u.scheme.lower(),u.netloc.lower(),u.path.rstrip('/'),'', ''))
    except Exception: return url

def dedupe(items):
    seen=set(); out=[]
    for it in items:
        key=canonical_url(it.get('url','')) or re.sub(r'\W+',' ',it.get('title','').lower()).strip()
        if key in seen: continue
        seen.add(key); out.append(it)
    return out

def tokens(text): return [t for t in re.findall(r"[a-zA-Z0-9][a-zA-Z0-9+._-]{2,}",text.lower()) if t not in STOP and not t.startswith('http')]
def vector(item): return Counter(tokens((item.get('title','')+' ')*2+item.get('text','')))
def cosine(a,b):
    common=set(a)&set(b); dot=sum(a[k]*b[k] for k in common); na=sum(v*v for v in a.values())**.5; nb=sum(v*v for v in b.values())**.5
    return dot/(na*nb) if na and nb else 0.0

def intent_score(item):
    text=item.get('title','')+' '+item.get('text',''); raw=sum(weight for rx,weight in INTENT_PATTERNS if rx.search(text))
    return min(10, raw)

def freshness(created, now=None):
    if not created: return 0.5
    now=now or time.time(); days=max(0,(now-created)/86400)
    return max(0.0, 1.0-days/365)

def excerpt(item, limit=180):
    text=re.sub(r'\s+',' ',item.get('text','')).strip() or item.get('title','')
    return text[:limit]+('…' if len(text)>limit else '')

def label_for(items):
    c=Counter()
    for it in items: c.update(tokens(it.get('title','')))
    return ' '.join(x for x,_ in c.most_common(4)) or 'uncategorized'

def rank(items, threshold=.20):
    clusters=[]
    for it in dedupe(items):
        it=dict(it); it['intent_score']=intent_score(it); it['freshness']=round(freshness(it.get('created')),3); v=vector(it); best=None; best_score=0
        for g in clusters:
            sim=cosine(v,g['vector'])
            if sim>best_score: best,best_score=g,sim
        if best is not None and best_score>=threshold: best['items'].append(it); best['vector'].update(v)
        else: clusters.append({'items':[it],'vector':Counter(v)})
    out=[]
    for g in clusters:
        its=g['items']; sources=sorted({x['source'] for x in its})
        engagement=sum(min(5000,max(0,x['score'])+2*max(0,x['comments'])) for x in its)
        intent=round(sum(x['intent_score'] for x in its)/len(its),2); fresh=round(sum(x['freshness'] for x in its)/len(its),2)
        frequency_score=min(100,len(its)*18); engagement_score=min(100,math.log1p(engagement)*13); diversity_score=min(100,len(sources)*30); intent_component=intent*10; freshness_score=fresh*100
        opportunity=round(.28*frequency_score+.24*engagement_score+.18*diversity_score+.20*intent_component+.10*freshness_score,1)
        best=sorted(its,key=lambda x:(x['intent_score']*15+x['score']+2*x['comments']),reverse=True)[:5]
        out.append({'topic':label_for(its),'mentions':len(its),'engagement':engagement,'sources':sources,'demand_intent':intent,'freshness':fresh,'opportunity_score':opportunity,'components':{'frequency':round(frequency_score,1),'engagement':round(engagement_score,1),'source_diversity':round(diversity_score,1),'intent':round(intent_component,1),'freshness':round(freshness_score,1)},'examples':[{'title':x['title'],'url':x['url'],'source':x['source'],'intent_score':x['intent_score'],'excerpt':excerpt(x)} for x in best]})
    return sorted(out,key=lambda x:x['opportunity_score'],reverse=True)

def demo():
    now=time.time()
    return [
      {'source':'reddit','title':'Looking for a simple shared budget app for couples','text':'We need something easier than a spreadsheet and would pay for a simple option.','url':'https://reddit.com/a','score':146,'comments':71,'created':now-86400*5},
      {'source':'reddit','title':'Is there an offline Google Photos alternative?','text':'Local timeline and duplicate finder would be enough.','url':'https://reddit.com/b','score':91,'comments':43,'created':now-86400*20},
      {'source':'github','title':'Feature request: visual repository health report','text':'Need a tool to check docs, secrets, outdated deps and CI.','url':'https://github.com/x/issues/1','score':44,'comments':12,'created':now-86400*35},
      {'source':'hn','title':'Ask HN: looking for simple self-hosted family budget','text':'Need CSV import and shared household categories.','url':'https://news.ycombinator.com/item?id=1','score':63,'comments':32,'created':now-86400*8},
    ]

def collect(queries, sources, limit):
    items=[]
    for query in queries:
        for s in sources:
            try: items += {'reddit':reddit,'hn':hn,'github':github}[s](query,limit)
            except Exception as e: print(f'[{s}] {query}: {e}',file=sys.stderr)
            time.sleep(.35)
    return dedupe(items)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--query',action='append',default=[]); ap.add_argument('--preset',choices=['software-requests']); ap.add_argument('--sources',default='reddit,hn,github'); ap.add_argument('--limit',type=int,default=30); ap.add_argument('--threshold',type=float,default=.20); ap.add_argument('--min-intent',type=int,default=0); ap.add_argument('--out',default='data/results.json'); ap.add_argument('--csv'); ap.add_argument('--demo',action='store_true')
    a=ap.parse_args(); queries=a.query or (TEMPLATES if a.preset else ['software request']); sources=[x.strip() for x in a.sources.split(',') if x.strip()]
    items=demo() if a.demo else collect(queries,sources,a.limit); items=[x for x in items if intent_score(x)>=a.min_intent]
    payload={'generated_at':datetime.now(timezone.utc).isoformat(),'queries':queries,'items':items,'opportunities':rank(items,a.threshold)}
    os.makedirs(os.path.dirname(a.out) or '.',exist_ok=True); PathLike=open(a.out,'w',encoding='utf8'); json.dump(payload,PathLike,ensure_ascii=False,indent=2); PathLike.close()
    if a.csv:
        with open(a.csv,'w',newline='',encoding='utf8') as f:
            fields=['topic','mentions','engagement','sources','demand_intent','freshness','opportunity_score']; w=csv.DictWriter(f,fieldnames=fields); w.writeheader()
            for r in payload['opportunities']:
                row={k:r[k] for k in fields}; row['sources']=','.join(row['sources']); w.writerow(row)
    print(f"Saved {len(items)} unique signals and {len(payload['opportunities'])} opportunity groups to {a.out}")
if __name__=='__main__': main()
