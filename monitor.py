#!/usr/bin/env python3
import argparse,json,subprocess,sys,time
from datetime import datetime,timezone
from pathlib import Path

VERSION="0.4.0"
ROOT=Path(__file__).resolve().parent

def load_json(path,default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf8"))
    except Exception:
        return default

def safe_name(name):
    out="".join(c if c.isalnum() or c in "-_." else "-" for c in str(name)).strip("-")
    return out or "search"

def snapshots(history_dir,name):
    d=Path(history_dir)/safe_name(name)
    return sorted((p for p in d.glob("*.json") if p.name!="index.json"), key=lambda p:p.name)

def latest_snapshot(history_dir,name):
    xs=snapshots(history_dir,name)
    return xs[-1] if xs else None

def snapshot_path(history_dir,name,when=None):
    when=when or datetime.now(timezone.utc)
    d=Path(history_dir)/safe_name(name);d.mkdir(parents=True,exist_ok=True)
    return d/(when.strftime("%Y%m%dT%H%M%SZ")+".json")

def summarize(payload):
    rows=payload.get("opportunities",[])
    alerts=payload.get("alerts",[])
    top=rows[0] if rows else {}
    return {
        "generated_at":payload.get("generated_at"),
        "opportunities":len(rows),
        "alerts":len(alerts),
        "top_topic":top.get("topic"),
        "top_score":top.get("opportunity_score"),
        "coverage":payload.get("coverage",{}).get("success_rate")
    }

def append_alerts(path,payload,search_name):
    alerts=payload.get("alerts",[])
    if not alerts:return 0
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("a",encoding="utf8") as f:
        for a in alerts:
            row={"logged_at":datetime.now(timezone.utc).isoformat(),"search":search_name,**a}
            f.write(json.dumps(row,ensure_ascii=False)+"\n")
    return len(alerts)

def update_index(history_dir,name,snapshot,payload,keep=90):
    d=Path(history_dir)/safe_name(name);d.mkdir(parents=True,exist_ok=True)
    index_path=d/"index.json"
    old=load_json(index_path,{"search":name,"runs":[]}) or {"search":name,"runs":[]}
    runs=[r for r in old.get("runs",[]) if r.get("snapshot")!=snapshot.name]
    runs.append({"snapshot":snapshot.name,**summarize(payload)})
    runs=sorted(runs,key=lambda r:r["snapshot"])
    if keep>0 and len(runs)>keep:
        drop=runs[:-keep]
        for r in drop:
            p=d/r["snapshot"]
            if p.exists():p.unlink()
        runs=runs[-keep:]
    index={"version":VERSION,"search":name,"runs":runs}
    index_path.write_text(json.dumps(index,ensure_ascii=False,indent=2),encoding="utf8")
    return index

def build_command(search_name,out,previous=None,saved_file="data/saved_searches.json",demo=False):
    cmd=[sys.executable,str(ROOT/"demandradar.py")]
    if demo:
        cmd+=["--demo"]
    else:
        cmd+=["--run-saved",search_name,"--saved-file",saved_file]
    if previous:cmd+=["--previous",str(previous)]
    cmd+=["--out",str(out)]
    return cmd

def run_once(search_name,history_dir="data/history",alerts_file="data/alerts.jsonl",
             saved_file="data/saved_searches.json",keep=90,demo=False):
    prev=latest_snapshot(history_dir,search_name)
    out=snapshot_path(history_dir,search_name)
    cmd=build_command(search_name,out,prev,saved_file,demo)
    r=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True)
    if r.returncode:
        if out.exists():out.unlink()
        raise RuntimeError((r.stderr or r.stdout or f"DemandRadar exited {r.returncode}").strip())
    payload=load_json(out,{}) or {}
    if not isinstance(payload.get("opportunities",[]),list):
        out.unlink(missing_ok=True)
        raise RuntimeError("Invalid DemandRadar snapshot")
    count=append_alerts(alerts_file,payload,search_name)
    index=update_index(history_dir,search_name,out,payload,keep)
    return {"snapshot":str(out),"alerts_logged":count,"summary":summarize(payload),"runs_kept":len(index["runs"])}

def print_history(history_dir,name,limit=20):
    idx=load_json(Path(history_dir)/safe_name(name)/"index.json",{"runs":[]}) or {"runs":[]}
    rows=idx.get("runs",[])[-max(1,limit):]
    print(json.dumps({"search":name,"runs":rows},ensure_ascii=False,indent=2))

def main():
    ap=argparse.ArgumentParser(description="DemandRadar v0.4 watch runner")
    ap.add_argument("--search",default="software-ideas",help="saved search name")
    ap.add_argument("--saved-file",default="data/saved_searches.json")
    ap.add_argument("--history-dir",default="data/history")
    ap.add_argument("--alerts-file",default="data/alerts.jsonl")
    ap.add_argument("--keep",type=int,default=90)
    ap.add_argument("--interval-minutes",type=int,default=0,help="0 = run once")
    ap.add_argument("--history",action="store_true")
    ap.add_argument("--history-limit",type=int,default=20)
    ap.add_argument("--demo",action="store_true")
    a=ap.parse_args()
    if a.history:
        print_history(a.history_dir,a.search,a.history_limit);return
    interval=max(0,a.interval_minutes)
    while True:
        try:
            result=run_once(a.search,a.history_dir,a.alerts_file,a.saved_file,a.keep,a.demo)
            print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
        except KeyboardInterrupt:
            raise
        except Exception as e:
            print(f"[watch] {e}",file=sys.stderr,flush=True)
            if interval<=0:raise SystemExit(2)
        if interval<=0:return
        time.sleep(max(60,interval*60))

if __name__=="__main__":
    main()
