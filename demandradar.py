#!/usr/bin/env python3
import argparse, csv, json, os, re, sys, time, urllib.parse, urllib.request
from collections import Counter
from datetime import datetime, timezone

UA = 'DemandRadar/0.1 (+https://github.com/099popovB2c/DemandRadar)'
STOP = set('a an the and or to of for in on with is are was were be this that it i you we they my our your app software tool program need want looking alternative wish there like'.split())
TEMPLATES = [
    '"looking for" app', '"is there an app"', '"alternative to"', '"wish there was"',
    '"need a tool"', '"looking for software"'
]

def fetch_json(url, headers=None, timeout=12):
    h={'User-Agent':UA,'Accept':'application/json'}; h.update(headers or {})
    req=urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))

def reddit(query, limit=30):
    q=urllib.parse.quote(query)
    data=fetch_json(f'https://www.reddit.com/search.json?q={q}&sort=relevance&limit={min(limit,100)}&t=year')
    out=[]
    for x in data.get('data',{}).get('children',[]):
        d=x.get('data',{})
        out.append({'source':'reddit','title':d.get('title',''),'text':d.get('selftext',''),'url':'https://reddit.com'+d.get('permalink',''),'score':int(d.get('score') or 0),'comments':int(d.get('num_comments') or 0),'created':d.get('created_utc')})
    return out

def hn(query, limit=30):
    q=urllib.parse.quote(query)
    data=fetch_json(f'https://hn.algolia.com/api/v1/search?query={q}&tags=story&hitsPerPage={min(limit,100)}')
    out=[]
    for d in data.get('hits',[]):
        out.append({'source':'hn','title':d.get('title') or '','text':d.get('story_text') or '','url':d.get('url') or f"https://news.ycombinator.com/item?id={d.get('objectID')}",'score':int(d.get('points') or 0),'comments':int(d.get('num_comments') or 0),'created':d.get('created_at_i')})
    return out

def github(query, limit=30):
    q=urllib.parse.quote(f'{query} is:issue')
    headers={}
    tok=os.getenv('GITHUB_TOKEN')
    if tok: headers['Authorization']=f'Bearer {tok}'
    data=fetch_json(f'https://api.github.com/search/issues?q={q}&per_page={min(limit,100)}&sort=reactions&order=desc', headers)
    out=[]
    for d in data.get('items',[]):
        out.append({'source':'github','title':d.get('title',''),'text':d.get('body') or '','url':d.get('html_url',''),'score':int(d.get('reactions',{}).get('total_count') or 0),'comments':int(d.get('comments') or 0),'created':None})
    return out

def tokens(text):
    return [t for t in re.findall(r"[a-zA-Z0-9][a-zA-Z0-9+._-]{2,}", text.lower()) if t not in STOP and not t.startswith('http')]

def vector(item):
    return Counter(tokens(item['title']+' '+item.get('text','')))

def cosine(a,b):
    common=set(a)&set(b)
    dot=sum(a[k]*b[k] for k in common)
    na=sum(v*v for v in a.values())**0.5; nb=sum(v*v for v in b.values())**0.5
    return dot/(na*nb) if na and nb else 0.0

def label_for(items):
    c=Counter()
    for it in items: c.update(tokens(it['title']))
    return ' '.join(x for x,_ in c.most_common(4)) or 'uncategorized'

def rank(items):
    clusters=[]
    for it in items:
        v=vector(it); best=None; best_score=0
        for g in clusters:
            sim=cosine(v,g['vector'])
            if sim>best_score: best,best_score=g,sim
        if best is not None and best_score>=0.20:
            best['items'].append(it); best['vector'].update(v)
        else:
            clusters.append({'items':[it],'vector':Counter(v)})
    out=[]
    for g in clusters:
        its=g['items']; engagement=sum(min(5000,max(0,x['score'])+2*max(0,x['comments'])) for x in its); sources=sorted({x['source'] for x in its})
        examples=[{'title':x['title'],'url':x['url'],'source':x['source']} for x in sorted(its,key=lambda x:x['score']+2*x['comments'],reverse=True)[:5]]
        score=round(len(its)*14 + min(engagement,3000)/30 + len(sources)*18,1)
        out.append({'topic':label_for(its),'mentions':len(its),'engagement':engagement,'sources':sources,'examples':examples,'opportunity_score':score})
    return sorted(out,key=lambda x:x['opportunity_score'],reverse=True)

def demo():
    return [
      {'source':'reddit','title':'Looking for a simple shared budget app for couples','text':'We want something easier than a spreadsheet.','url':'https://reddit.com/','score':146,'comments':71,'created':None},
      {'source':'reddit','title':'Is there an offline Google Photos alternative?','text':'Local timeline and duplicate finder would be enough.','url':'https://reddit.com/','score':91,'comments':43,'created':None},
      {'source':'github','title':'Feature request: visual repository health report','text':'Check docs, secrets, outdated deps and CI.','url':'https://github.com/','score':44,'comments':12,'created':None},
      {'source':'hn','title':'Ask HN: simple self-hosted family budget?','text':'Need CSV import and shared household categories.','url':'https://news.ycombinator.com/','score':63,'comments':32,'created':None},
    ]

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--query',default='software request'); ap.add_argument('--sources',default='reddit,hn,github'); ap.add_argument('--limit',type=int,default=30); ap.add_argument('--out',default='data/results.json'); ap.add_argument('--csv'); ap.add_argument('--demo',action='store_true')
    a=ap.parse_args(); items=demo() if a.demo else []
    if not a.demo:
        for s in [x.strip() for x in a.sources.split(',') if x.strip()]:
            try:
                items += {'reddit':reddit,'hn':hn,'github':github}[s](a.query,a.limit)
            except Exception as e: print(f'[{s}] {e}', file=sys.stderr)
            time.sleep(.5)
    payload={'generated_at':datetime.now(timezone.utc).isoformat(),'query':a.query,'items':items,'opportunities':rank(items)}
    os.makedirs(os.path.dirname(a.out) or '.', exist_ok=True); json.dump(payload,open(a.out,'w',encoding='utf8'),ensure_ascii=False,indent=2)
    if a.csv:
        with open(a.csv,'w',newline='',encoding='utf8') as f:
            w=csv.DictWriter(f,fieldnames=['topic','mentions','engagement','sources','opportunity_score']); w.writeheader()
            for r in payload['opportunities']:
                row={k:r[k] for k in w.fieldnames}; row['sources']=','.join(row['sources']); w.writerow(row)
    print(f"Saved {len(items)} signals and {len(payload['opportunities'])} opportunity groups to {a.out}")
if __name__=='__main__': main()
