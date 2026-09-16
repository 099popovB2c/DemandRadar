#!/usr/bin/env python3
import argparse,csv,json,math,os,re,sys,time,urllib.parse,urllib.request
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path

VERSION="0.4.0"
UA=f"DemandRadar/{VERSION} (+https://github.com/099popovB2c/DemandRadar)"
STOP=set("a an the and or to of for in on with is are was were be this that it i you we they my our your app software tool program need want looking alternative wish there like have has had can could would should".split())
TEMPLATES=['"looking for" app','"is there an app"','"alternative to"','"wish there was"','"need a tool"','"looking for software"']
PATTERNS=[
 ("buying",re.compile(r"\bwould pay\b|\bpay for\b|\bbudget for\b",re.I),5),
 ("wish",re.compile(r"\bwish there (?:was|were)\b",re.I),5),
 ("solution_request",re.compile(r"\bis there an? (?:app|tool|software)\b|\bneed an? (?:app|tool|software)\b",re.I),4),
 ("searching",re.compile(r"\blooking for\b",re.I),3),
 ("replacement",re.compile(r"\balternative to\b|\breplacement for\b",re.I),3),
 ("pain",re.compile(r"\bcan't find\b|\bcannot find\b|\bfrustrat(?:ed|ing)\b|\bhate\b|\bannoy(?:ed|ing)\b",re.I),3),
 ("workaround",re.compile(r"\bmanual(?:ly)?\b|\bspreadsheet\b|\bworkaround\b",re.I),1),
]

def fetch_json(url,headers=None,timeout=12):
 h={"User-Agent":UA,"Accept":"application/json"};h.update(headers or {})
 with urllib.request.urlopen(urllib.request.Request(url,headers=h),timeout=timeout) as r:return json.loads(r.read().decode())

def iso_epoch(v):
 if not v:return None
 try:return datetime.fromisoformat(v.replace("Z","+00:00")).timestamp()
 except Exception:return None

def reddit(q,limit=30):
 d=fetch_json(f"https://www.reddit.com/search.json?q={urllib.parse.quote(q)}&sort=new&limit={min(limit,100)}&t=year")
 return [{"source":"reddit","title":x["data"].get("title",""),"text":x["data"].get("selftext",""),"url":"https://reddit.com"+x["data"].get("permalink",""),"score":int(x["data"].get("score") or 0),"comments":int(x["data"].get("num_comments") or 0),"created":x["data"].get("created_utc")} for x in d.get("data",{}).get("children",[])]

def hn(q,limit=30):
 d=fetch_json(f"https://hn.algolia.com/api/v1/search_by_date?query={urllib.parse.quote(q)}&tags=story&hitsPerPage={min(limit,100)}")
 return [{"source":"hn","title":x.get("title") or "","text":x.get("story_text") or "","url":x.get("url") or f"https://news.ycombinator.com/item?id={x.get('objectID')}","score":int(x.get("points") or 0),"comments":int(x.get("num_comments") or 0),"created":x.get("created_at_i")} for x in d.get("hits",[])]

def github(q,limit=30):
 h={};tok=os.getenv("GITHUB_TOKEN")
 if tok:h["Authorization"]=f"Bearer {tok}"
 d=fetch_json(f"https://api.github.com/search/issues?q={urllib.parse.quote(q+' is:issue')}&per_page={min(limit,100)}&sort=created&order=desc",h)
 return [{"source":"github","title":x.get("title",""),"text":x.get("body") or "","url":x.get("html_url",""),"score":int(x.get("reactions",{}).get("total_count") or 0),"comments":int(x.get("comments") or 0),"created":iso_epoch(x.get("created_at"))} for x in d.get("items",[])]

def canonical_url(url):
 try:
  u=urllib.parse.urlsplit(url);return urllib.parse.urlunsplit((u.scheme.lower(),u.netloc.lower(),u.path.rstrip("/"),"",""))
 except Exception:return url

def dedupe(items):
 out=[];seen=set()
 for it in items:
  k=canonical_url(it.get("url","")) or re.sub(r"\W+"," ",it.get("title","").lower()).strip()
  if k not in seen:seen.add(k);out.append(it)
 return out

def tokens(t):return [x for x in re.findall(r"[a-zA-Z0-9][a-zA-Z0-9+._-]{2,}",t.lower()) if x not in STOP and not x.startswith("http")]
def vector(x):return Counter(tokens((x.get("title","")+" ")*2+x.get("text","")))
def cosine(a,b):
 dot=sum(a[k]*b[k] for k in set(a)&set(b));na=sum(v*v for v in a.values())**.5;nb=sum(v*v for v in b.values())**.5
 return dot/(na*nb) if na and nb else 0
def intent_tags(x):
 t=x.get("title","")+" "+x.get("text","");return sorted({n for n,r,_ in PATTERNS if r.search(t)})
def intent_score(x):
 t=x.get("title","")+" "+x.get("text","");return min(10,sum(w for _,r,w in PATTERNS if r.search(t)))
def freshness(c,now=None):
 if not c:return .5
 return max(0,1-max(0,((now or time.time())-float(c))/86400)/365)
def excerpt(x,n=180):
 t=re.sub(r"\s+"," ",x.get("text","")).strip() or x.get("title","");return t[:n]+("…" if len(t)>n else "")

def rank(items,threshold=.20):
 groups=[]
 for raw in dedupe(items):
  x=dict(raw);x["intent_score"]=intent_score(x);x["intent_tags"]=intent_tags(x);x["freshness"]=round(freshness(x.get("created")),3);v=vector(x);best=None;sim=0
  for g in groups:
   s=cosine(v,g["vector"])
   if s>sim:best,sim=g,s
  if best is not None and sim>=threshold:best["items"].append(x);best["vector"].update(v)
  else:groups.append({"items":[x],"vector":Counter(v)})
 out=[]
 for g in groups:
  xs=g["items"];src=sorted({x["source"] for x in xs});eng=sum(min(5000,max(0,x["score"])+2*max(0,x["comments"])) for x in xs)
  intent=round(sum(x["intent_score"] for x in xs)/len(xs),2);fresh=round(sum(x["freshness"] for x in xs)/len(xs),2)
  comp={"frequency":min(100,len(xs)*18),"engagement":min(100,math.log1p(eng)*13),"source_diversity":min(100,len(src)*30),"intent":intent*10,"freshness":fresh*100}
  score=round(.28*comp["frequency"]+.24*comp["engagement"]+.18*comp["source_diversity"]+.20*comp["intent"]+.10*comp["freshness"],1)
  c=Counter()
  for x in xs:c.update(tokens((x.get("title","")+" ")*2+x.get("text","")))
  label=" ".join(x for x,_ in Counter(t for z in xs for t in tokens(z.get("title",""))).most_common(4)) or "uncategorized"
  key="-".join(sorted(x for x,_ in c.most_common(6))) or "uncategorized"
  mix=Counter(t for x in xs for t in x["intent_tags"])
  best=sorted(xs,key=lambda x:x["intent_score"]*15+x["score"]+2*x["comments"],reverse=True)[:5]
  out.append({"topic":label,"topic_key":key,"mentions":len(xs),"engagement":eng,"sources":src,"demand_intent":intent,"intent_mix":dict(mix),"freshness":fresh,"opportunity_score":score,"components":{k:round(v,1) for k,v in comp.items()},"examples":[{"title":x["title"],"url":x["url"],"source":x["source"],"intent_score":x["intent_score"],"intent_tags":x["intent_tags"],"excerpt":excerpt(x)} for x in best]})
 return sorted(out,key=lambda x:x["opportunity_score"],reverse=True)

def demo():
 n=time.time()
 return [
 {"source":"reddit","title":"Looking for a simple shared budget app for couples","text":"We need something easier than a spreadsheet and would pay for a simple option.","url":"https://reddit.com/a","score":146,"comments":71,"created":n-86400*5},
 {"source":"reddit","title":"Is there an offline Google Photos alternative?","text":"Local timeline and duplicate finder would be enough.","url":"https://reddit.com/b","score":91,"comments":43,"created":n-86400*20},
 {"source":"github","title":"Feature request: visual repository health report","text":"Need a tool to check docs, secrets, outdated deps and CI.","url":"https://github.com/x/issues/1","score":44,"comments":12,"created":n-86400*35},
 {"source":"hn","title":"Ask HN: looking for simple self-hosted family budget","text":"Need CSV import and shared household categories.","url":"https://news.ycombinator.com/item?id=1","score":63,"comments":32,"created":n-86400*8}]

def collect(queries,sources,limit):
 items=[];cov={"attempted":0,"successful":0,"failed":[],"by_source":{s:0 for s in sources}}
 for q in queries:
  for s in sources:
   cov["attempted"]+=1
   try:
    got={"reddit":reddit,"hn":hn,"github":github}[s](q,limit);items+=got;cov["successful"]+=1;cov["by_source"][s]+=len(got)
   except Exception as e:cov["failed"].append({"source":s,"query":q,"error":str(e)[:180]});print(f"[{s}] {q}: {e}",file=sys.stderr)
   time.sleep(.35)
 cov["success_rate"]=round(cov["successful"]/cov["attempted"],3) if cov["attempted"] else 1
 return dedupe(items),cov

def load_json(p,default):
 try:return json.loads(Path(p).read_text(encoding="utf8"))
 except Exception:return default
def save_json(p,x):Path(p).parent.mkdir(parents=True,exist_ok=True);Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding="utf8")
def save_search(path,name,queries,sources,limit,threshold,min_intent):
 cfg=load_json(path,{"searches":{}});cfg.setdefault("searches",{})[name]={"queries":queries,"sources":sources,"limit":limit,"threshold":threshold,"min_intent":min_intent};save_json(path,cfg)
def match_old(row,olds):
 a=set(row.get("topic_key","").replace("-"," ").split());best=None;bs=0
 for old in olds:
  b=set((old.get("topic_key") or old.get("topic","")).replace("-"," ").split());u=a|b;s=len(a&b)/len(u) if u else 0
  if s>bs:best,bs=old,s
 return best if bs>=.35 else None
def add_trends(rows,previous):
 olds=(previous or {}).get("opportunities",[])
 for r in rows:
  o=match_old(r,olds)
  if not o:r["trend"]={"state":"new","previous_score":None,"score_delta":None,"mentions_delta":None}
  else:
   d=round(r["opportunity_score"]-float(o.get("opportunity_score",0)),1);md=r["mentions"]-int(o.get("mentions",0))
   r["trend"]={"state":"rising" if d>=5 else "falling" if d<=-5 else "stable","previous_score":o.get("opportunity_score"),"score_delta":d,"mentions_delta":md}
 return rows
def alerts(rows,score=70,rise=10):
 out=[]
 for r in rows:
  why=[];tr=r["trend"]
  if r["opportunity_score"]>=score:why.append(f"score>={score}")
  if tr.get("score_delta") is not None and tr["score_delta"]>=rise:why.append(f"score rose {tr['score_delta']:+.1f}")
  if tr["state"]=="new" and r["demand_intent"]>=5:why.append("new high-intent cluster")
  if why:out.append({"topic":r["topic"],"opportunity_score":r["opportunity_score"],"reasons":why,"examples":r["examples"][:2]})
 return out

def main():
 ap=argparse.ArgumentParser();ap.add_argument("--query",action="append",default=[]);ap.add_argument("--preset",choices=["software-requests"]);ap.add_argument("--sources",default="reddit,hn,github");ap.add_argument("--limit",type=int,default=30);ap.add_argument("--threshold",type=float,default=.20);ap.add_argument("--min-intent",type=int,default=0);ap.add_argument("--out",default="data/results.json");ap.add_argument("--csv");ap.add_argument("--demo",action="store_true");ap.add_argument("--saved-file",default="data/saved_searches.json");ap.add_argument("--save-search");ap.add_argument("--run-saved");ap.add_argument("--list-saved",action="store_true");ap.add_argument("--previous");ap.add_argument("--alert-score",type=float,default=70);ap.add_argument("--alert-rise",type=float,default=10)
 a=ap.parse_args();cfg=load_json(a.saved_file,{"searches":{}})
 if a.list_saved:print(json.dumps(cfg,indent=2));return
 queries=a.query or (TEMPLATES if a.preset else ["software request"]);sources=[x.strip() for x in a.sources.split(",") if x.strip()]
 if a.run_saved:
  s=cfg.get("searches",{}).get(a.run_saved)
  if not s:raise SystemExit(f"Saved search not found: {a.run_saved}")
  queries,sources,a.limit,a.threshold,a.min_intent=s["queries"],s["sources"],s["limit"],s["threshold"],s["min_intent"]
 if a.save_search:save_search(a.saved_file,a.save_search,queries,sources,a.limit,a.threshold,a.min_intent)
 items,cov=(demo(),{"attempted":0,"successful":0,"failed":[],"by_source":{},"success_rate":1}) if a.demo else collect(queries,sources,a.limit)
 items=[x for x in items if intent_score(x)>=a.min_intent];rows=add_trends(rank(items,a.threshold),load_json(a.previous,None) if a.previous else None);al=alerts(rows,a.alert_score,a.alert_rise)
 payload={"version":VERSION,"generated_at":datetime.now(timezone.utc).isoformat(),"queries":queries,"sources":sources,"coverage":cov,"items":items,"opportunities":rows,"alerts":al};save_json(a.out,payload)
 if a.csv:
  with open(a.csv,"w",newline="",encoding="utf8") as f:
   fields=["topic","mentions","engagement","sources","demand_intent","freshness","opportunity_score","trend_state","score_delta"];w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
   for r in rows:w.writerow({"topic":r["topic"],"mentions":r["mentions"],"engagement":r["engagement"],"sources":",".join(r["sources"]),"demand_intent":r["demand_intent"],"freshness":r["freshness"],"opportunity_score":r["opportunity_score"],"trend_state":r["trend"]["state"],"score_delta":r["trend"]["score_delta"]})
 print(f"Saved {len(items)} signals, {len(rows)} groups and {len(al)} alerts to {a.out}")
 for x in al[:10]:print(f"ALERT {x['opportunity_score']:>5.1f} {x['topic']}: {', '.join(x['reasons'])}")
if __name__=="__main__":main()
