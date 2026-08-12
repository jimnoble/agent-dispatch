#!/usr/bin/env python3
"""Model×reasoning exploration and repository-default promotion for Agent Dispatch."""
import argparse,json,os
from collections import defaultdict
from pathlib import Path
EFFORTS=("none","minimal","low","medium","high","xhigh")
def home():return Path(os.environ.get("AGENT_DISPATCH_HOME",Path(os.environ.get("CODEX_HOME",Path.home()/".codex"))/"agent-dispatch")).expanduser()
def load(p,d):
 try:return json.loads(p.read_text())
 except FileNotFoundError:return d
def events():
 p=home()/"telemetry.jsonl";out=[]
 if not p.exists():return out
 for l in p.read_text().splitlines():
  try:
   e=json.loads(l)
   if e.get("event")=="delegated_task":out.append(e)
  except:pass
 return out
def cells_path():return home()/"cells.json"
def cells():return load(cells_path(),{"cells":[]}).get("cells",[])
def register(a):
 p=cells_path();p.parent.mkdir(parents=True,exist_ok=True);d=load(p,{"schema":1,"cells":[]});x={"model":a.model,"effort":a.effort,"tier":a.tier,"revision":a.revision}
 if x not in d["cells"]:d["cells"].append(x);p.write_text(json.dumps(d,indent=2,sort_keys=True)+"\n")
 print(json.dumps(x,indent=2))
def em(e):return e.get("effective_model") or e.get("requested_model") or e.get("worker_model") or e.get("tier")
def ee(e):return e.get("effective_effort") or e.get("requested_effort") or e.get("worker_reasoning")
def observed(a):
 c=defaultdict(int)
 for e in events():
  if e.get("task_class")!=a.task_class:continue
  if a.domain and e.get("domain") not in {a.domain,None}:continue
  c[(em(e),ee(e))]+=1
 return c
def suggest(a):
 av=cells();cnt=observed(a)
 if not av:
  print(json.dumps({"candidate":None,"reason":"No runtime-supported cells registered. Register only combinations the runtime actually exposes."},indent=2));return
 cur=(a.current_model,a.current_effort);same=[x for x in av if x.get("model")==cur[0] and x.get("effort")!=cur[1]];cross=[x for x in av if x.get("model")!=cur[0]];pool=same+cross if cur[0] else av
 x=min(pool or av,key=lambda q:cnt[(q.get("model"),q.get("effort"))]);mode="shadow" if a.frontier else "controlled"
 print(json.dumps({"candidate":x,"observations":cnt[(x.get("model"),x.get("effort"))],"mode":mode,"principle":"Explore model and reasoning independently; same-model effort neighbors before cross-model cells when equally under-sampled."},indent=2))
def route_rows(project,task,domain):
 state=load(home()/"routing-state.json",{"routes":{}});out=[]
 for k,m in state.get("routes",{}).items():
  parts=k.split("|")
  if len(parts)<7:continue
  p,tc,d,model,rev,eff,sv=parts[:7]
  if p!=project or tc!=task or (domain and d not in {domain,"*"}):continue
  out.append({"model":model,"revision":rev,"effort":eff,"skill_version":sv,**m})
 return sorted(out,key=lambda x:(x.get("utility",-99),x.get("clean_success_rate",0)),reverse=True)
def promote(a):
 if not a.project:raise SystemExit("--project is required")
 cfg=load(home()/"config.json",{});mins=int(cfg.get("promotion_min_samples",12));succ=float(cfg.get("promotion_min_clean_success",.90));rw=float(cfg.get("promotion_max_rework",.08));margin=float(cfg.get("promotion_min_utility_margin",.03));rows=route_rows(a.project,a.task_class,a.domain)
 eligible=[x for x in rows if x.get("samples",0)>=mins and x.get("clean_success_rate",0)>=succ and x.get("rework_rate",1)<=rw]
 if not eligible:print(json.dumps({"promoted":False,"reason":"insufficient high-confidence project-local evidence"},indent=2));return
 best=eligible[0];second=eligible[1] if len(eligible)>1 else None
 if second and best.get("utility",0)-second.get("utility",0)<margin:print(json.dumps({"promoted":False,"reason":"leading cells are too close to promote","best":best,"runner_up":second},indent=2));return
 root=Path(a.repo_root).resolve();p=root/".agent-dispatch"/"defaults.json";p.parent.mkdir(parents=True,exist_ok=True);d=load(p,{"schema":1,"routes":{}});key=f"{a.task_class}|{a.domain or '*'}|{a.write_class or '*'}";d["routes"][key]={"model":best["model"],"effort":None if best["effort"]=="*" else best["effort"],"revision":None if best["revision"]=="*" else best["revision"],"evidence":{"samples":best["samples"],"clean_success_rate":best["clean_success_rate"],"rework_rate":best["rework_rate"],"utility":best["utility"]},"source":"promoted burn-in evidence"};p.write_text(json.dumps(d,indent=2,sort_keys=True)+"\n");print(json.dumps({"promoted":True,"path":str(p),"key":key,"default":d["routes"][key]},indent=2))
def show(a):
 p=Path(a.repo_root).resolve()/".agent-dispatch"/"defaults.json";print(json.dumps(load(p,{"schema":1,"routes":{}}),indent=2,sort_keys=True))
def parser():
 p=argparse.ArgumentParser();s=p.add_subparsers(dest="cmd",required=True);r=s.add_parser("register-cell");r.add_argument("--model",required=True);r.add_argument("--effort",required=True,choices=EFFORTS);r.add_argument("--tier");r.add_argument("--revision");r.set_defaults(func=register)
 q=s.add_parser("suggest");q.add_argument("--task-class",required=True);q.add_argument("--domain");q.add_argument("--current-model");q.add_argument("--current-effort");q.add_argument("--frontier",action="store_true");q.set_defaults(func=suggest)
 m=s.add_parser("promote");m.add_argument("--repo-root",default=".");m.add_argument("--project",required=True);m.add_argument("--task-class",required=True);m.add_argument("--domain");m.add_argument("--write-class");m.set_defaults(func=promote)
 z=s.add_parser("show-defaults");z.add_argument("--repo-root",default=".");z.set_defaults(func=show);return p
if __name__=="__main__":a=parser().parse_args();a.func(a)
