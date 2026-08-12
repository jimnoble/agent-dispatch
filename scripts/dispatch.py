#!/usr/bin/env python3
"""Adaptive orchestration telemetry, model×effort exploration, learning, and repo-default promotion."""
from __future__ import annotations
import argparse, datetime as dt, json, os, statistics, sys
from collections import defaultdict
from pathlib import Path
SCHEMA=3
TIERS=("frontier","general","cheap","alternate_pool")
EFFORTS=("none","minimal","low","medium","high","xhigh")
CFG={"schema":SCHEMA,"min_samples":8,"promotion_min_samples":12,"promotion_min_clean_success":.90,"promotion_max_rework":.08,"promotion_min_utility_margin":.03,"exploration_rate":.05,"half_life_days":45.,"max_recursive_depth":2,"default_concurrency":3,"max_concurrency":5,"tune_every":8,"scarcity_penalty":{"frontier":.22,"general":.08,"cheap":.02,"alternate_pool":.01},"effort_penalty":{"none":0,"minimal":.002,"low":.006,"medium":.015,"high":.03,"xhigh":.05,"unknown":.015},"rework_penalty":.35,"escalation_penalty":.16,"failure_penalty":.55,"latency_penalty_per_minute":.002,"review_failure_required_rate":.10,"review_failure_recommended_rate":.03,"collision_conservative_rate":.10}
PRIORS={"architecture":"frontier","planning":"frontier","ambiguous_debugging":"frontier","adjudication":"frontier","bounded_implementation":"general","ordinary_debugging":"general","code_review":"general","investigation":"general","repository_inventory":"alternate_pool","mechanical_edit":"cheap","formatting":"cheap","simple_test":"cheap","metadata_extraction":"cheap"}
REV={"frontier":"required","general":"recommended","cheap":"optional","alternate_pool":"recommended"}
def now():return dt.datetime.now(dt.timezone.utc).isoformat()
def home():return Path(os.environ.get("AGENT_DISPATCH_HOME",Path(os.environ.get("CODEX_HOME",Path.home()/".codex"))/"agent-dispatch")).expanduser()
def paths():r=home();return r/"telemetry.jsonl",r/"routing-state.json",r/"config.json",r/"cells.json"
def load(p,d):
 try:return json.loads(p.read_text())
 except FileNotFoundError:return d
 except json.JSONDecodeError as e:raise SystemExit(f"Invalid JSON in {p}: {e}")
def initq():
 t,r,c,x=paths();t.parent.mkdir(parents=True,exist_ok=True);t.touch(exist_ok=True)
 if not c.exists():c.write_text(json.dumps(CFG,indent=2)+"\n")
 if not r.exists():r.write_text(json.dumps({"schema":SCHEMA,"routes":{},"policies":{}},indent=2)+"\n")
 if not x.exists():x.write_text(json.dumps({"schema":SCHEMA,"cells":[]},indent=2)+"\n")
def init():initq();print(f"Agent Dispatch state initialized at {home()}")
def boo(v):
 if v is None:return None
 if v.lower() in {"1","true","yes","pass","passed"}:return True
 if v.lower() in {"0","false","no","fail","failed"}:return False
 raise argparse.ArgumentTypeError(v)
def append(e):
 initq();e={k:v for k,v in e.items() if v is not None}
 with paths()[0].open("a") as f:f.write(json.dumps(e,sort_keys=True)+"\n")
 return e
def events(kind=None):
 initq();out=[]
 for i,l in enumerate(paths()[0].read_text().splitlines(),1):
  if not l.strip():continue
  try:e=json.loads(l)
  except json.JSONDecodeError:print(f"warning: invalid telemetry line {i}",file=sys.stderr);continue
  if kind is None or e.get("event")==kind:out.append(e)
 return out
def weight(ts,h):
 try:
  x=dt.datetime.fromisoformat(str(ts).replace("Z","+00:00"));x=x if x.tzinfo else x.replace(tzinfo=dt.timezone.utc)
  return .5**(max(0,(dt.datetime.now(dt.timezone.utc)-x).total_seconds()/86400)/h)
 except:return 1.
def evscore(e):
 if e.get("tests_pass") is False:return 0.,"tests"
 if e.get("review_pass") is False:return .15,"review"
 if e.get("accepted") is False:return 0.,"parent"
 if e.get("tests_pass") is True:return 1.,"tests"
 if e.get("review_pass") is True:return .95,"review"
 if e.get("accepted") is True:return .85,"parent"
 if e.get("outcome")=="pass":return .55,"self_report"
 return 0.,"none"
def clean(e):return evscore(e)[0]>=.85 and e.get("rework") is not True and e.get("parallel_collision") is not True
def model(e):return e.get("effective_model") or e.get("requested_model") or e.get("worker_model") or e.get("tier","unknown")
def effort(e):return e.get("effective_effort") or e.get("requested_effort") or e.get("worker_reasoning") or "unknown"
def util(e,c):
 s,_=evscore(e)
 if s==0:s-=c["failure_penalty"]
 if e.get("rework") is True:s-=c["rework_penalty"]
 s-=c["escalation_penalty"]*int(e.get("escalations",0) or 0)+c["scarcity_penalty"].get(e.get("tier"),.05)+c["effort_penalty"].get(effort(e),.015)
 if e.get("duration_s") is not None:s-=c["latency_penalty_per_minute"]*float(e["duration_s"])/60
 return s
def agg(rows,c):
 tw=sum(w for _,w in rows) or 1;rr=[(e,w) for e,w in rows if e.get("review_pass") is not None];pp=[(e,w) for e,w in rows if e.get("parallel") is True];pg=[int(e["parallel_group_size"]) for e,_ in rows if e.get("parallel_group_size") and clean(e) and e.get("parallel_collision") is not True];ds=[float(e["duration_s"]) for e,_ in rows if e.get("duration_s") is not None]
 return {"samples":len(rows),"effective_samples":round(tw,3),"clean_success_rate":round(sum(w for e,w in rows if clean(e))/tw,4),"rework_rate":round(sum(w for e,w in rows if e.get("rework") is True)/tw,4),"mean_escalations":round(sum(w*int(e.get("escalations",0) or 0) for e,w in rows)/tw,4),"utility":round(sum(util(e,c)*w for e,w in rows)/tw,4),"review_failure_rate":round(sum(w for e,w in rr if e.get("review_pass") is False)/(sum(w for _,w in rr) or 1),4) if rr else 0,"parallel_collision_rate":round(sum(w for e,w in pp if e.get("parallel_collision") is True)/(sum(w for _,w in pp) or 1),4) if pp else 0,"successful_parallel_group_median":statistics.median(pg) if pg else None,"median_duration_s":statistics.median(ds) if ds else None}
def tune():
 initq();c=load(paths()[2],CFG);es=events("delegated_task");g=defaultdict(list);b=defaultdict(list)
 for e in es:
  w=weight(e.get("timestamp"),c["half_life_days"])
  for p,d in ((e.get("project") or "*",e.get("domain") or "*"),(e.get("project") or "*","*"),("*",e.get("domain") or "*"),("*","*")):
   g["|".join([p,e.get("task_class","unknown"),d,model(e),e.get("worker_revision") or "*",effort(e),e.get("skill_version") or "*"])].append((e,w));b["|".join([p,e.get("task_class","unknown"),d,e.get("write_class") or "*"])].append((e,w))
 routes={k:agg(v,c) for k,v in g.items()};pol={}
 for k,rows in b.items():
  m=agg(rows,c);er=sum(1 for e,_ in rows if int(e.get("escalations",0) or 0)>0)/max(1,len(rows));rv="required" if m["review_failure_rate"]>=c["review_failure_required_rate"] else ("recommended" if m["review_failure_rate"]>=c["review_failure_recommended_rate"] else "optional");cn=c["default_concurrency"];md=m["successful_parallel_group_median"]
  if md:cn=min(c["max_concurrency"],max(2,int(round(md))))
  if m["parallel_collision_rate"]>=c["collision_conservative_rate"]:cn=max(1,cn-1)
  pol[k]={"samples":len(rows),"retry_budget":0 if er>.45 else (1 if er>.15 else 2),"escalate_after_failures":1 if er>.25 else 2,"reviewer_policy":rv,"preferred_concurrency":cn,"parallel_collision_rate":m["parallel_collision_rate"]}
 paths()[1].write_text(json.dumps({"schema":SCHEMA,"generated_at":now(),"routes":routes,"policies":pol},indent=2,sort_keys=True)+"\n");return len(es)
def maybe():
 c=load(paths()[2],CFG);n=len(events("delegated_task"))
 if n and n%int(c["tune_every"])==0:tune()
def record(a):
 e={"schema":SCHEMA,"timestamp":a.timestamp or now(),"event":"delegated_task","task_id":a.task_id,"run_id":a.run_id,"parent_task_id":a.parent_task_id,"project":a.project,"task_class":a.task_class,"domain":a.domain,"front_door_model":a.front_door_model,"front_door_revision":a.front_door_revision,"front_door_reasoning":a.front_door_reasoning,"requested_model":a.requested_model or a.worker_model,"requested_effort":a.requested_effort or a.worker_reasoning,"effective_model":a.effective_model,"effective_effort":a.effective_effort,"worker_revision":a.worker_revision,"tier":a.tier,"delegation_depth":a.delegation_depth,"parallel":a.parallel,"parallel_group_size":a.parallel_group_size,"parallel_collision":a.parallel_collision,"write_class":a.write_class,"shadow":a.shadow,"consultation_mode":a.consultation_mode,"frontier_use":a.frontier_use,"frontier_calls":a.frontier_calls,"duration_s":a.duration_s,"input_tokens":a.input_tokens,"output_tokens":a.output_tokens,"usage_source":a.usage_source,"retries":a.retries,"escalations":a.escalations,"failure_mode":a.failure_mode,"review_pass":a.review_pass,"tests_pass":a.tests_pass,"rework":a.rework,"accepted":a.accepted,"outcome":a.outcome,"notes":a.notes,"skill_version":a.skill_version};print(json.dumps(append(e),indent=2));maybe()
def record_run(a):print(json.dumps(append({"schema":SCHEMA,"timestamp":a.timestamp or now(),"event":"run_summary","run_id":a.run_id,"project":a.project,"front_door_model":a.front_door_model,"front_door_revision":a.front_door_revision,"front_door_reasoning":a.front_door_reasoning,"duration_s":a.duration_s,"input_tokens":a.input_tokens,"output_tokens":a.output_tokens,"usage_source":a.usage_source,"frontier_calls":a.frontier_calls,"frontier_tokens":a.frontier_tokens,"delegated_tasks":a.delegated_tasks,"max_parallelism":a.max_parallelism,"rework":a.rework,"accepted":a.accepted,"tests_pass":a.tests_pass,"review_pass":a.review_pass,"outcome":a.outcome,"skill_version":a.skill_version,"notes":a.notes}),indent=2))
def register(a):
 initq();p=paths()[3];d=load(p,{"schema":SCHEMA,"cells":[]});x={"model":a.model,"effort":a.effort,"tier":a.tier,"revision":a.revision}
 if x not in d["cells"]:d["cells"].append(x);p.write_text(json.dumps(d,indent=2,sort_keys=True)+"\n")
 print(json.dumps(x,indent=2))
def candidates(a,s,c):
 out=[]
 for k,m in s.get("routes",{}).items():
  p,tc,d,mo,rv,ef,sv=k.split("|",6)
  if tc!=a.task_class or m["samples"]<c["min_samples"]:continue
  sp=0
  if a.project and p==a.project:sp+=4
  elif p!="*":continue
  if a.domain and d==a.domain:sp+=2
  elif d!="*":continue
  if a.worker_revision and rv==a.worker_revision:sp+=1
  elif a.worker_revision and rv!="*":continue
  if a.skill_version and sv==a.skill_version:sp+=1
  elif a.skill_version and sv!="*":continue
  out.append({"model":mo,"revision":rv,"effort":ef,"skill_version":sv,"specificity":sp,**m})
 return sorted(out,key=lambda x:(x["specificity"],x["utility"],x["clean_success_rate"]),reverse=True)
def policy(a,s,c):
 wc=a.write_class or "*";ks=[]
 if a.project and a.domain:ks += [f"{a.project}|{a.task_class}|{a.domain}|{wc}",f"{a.project}|{a.task_class}|{a.domain}|*"]
 if a.project:ks.append(f"{a.project}|{a.task_class}|*|{wc}")
 if a.domain:ks.append(f"*|{a.task_class}|{a.domain}|{wc}")
 ks += [f"*|{a.task_class}|*|{wc}",f"*|{a.task_class}|*|*"]
 for k in dict.fromkeys(ks):
  x=s.get("policies",{}).get(k)
  if x and x.get("samples",0)>=c["min_samples"]:return k,x
 t=PRIORS.get(a.task_class,"general");return None,{"retry_budget":1,"escalate_after_failures":1 if t=="frontier" else 2,"reviewer_policy":REV[t],"preferred_concurrency":c["default_concurrency"]}
def cell_counts(a):
 z=defaultdict(int)
 for e in events("delegated_task"):
  if e.get("task_class")!=a.task_class:continue
  if a.domain and e.get("domain") not in {a.domain,None}:continue
  z[(model(e),effort(e))]+=1
 return z
def explore(a,best,c):
 avail=load(paths()[3],{"cells":[]})["cells"];cnt=cell_counts(a)
 if not avail:return None
 safe=[x for x in avail if x.get("model") and x.get("effort")]
 if best:
  same=[x for x in safe if x["model"]==best["model"] and x["effort"]!=best["effort"]]
  cross=[x for x in safe if x["model"]!=best["model"]]
  pool=same+cross
 else:pool=safe
 if not pool:return None
 x=min(pool,key=lambda q:cnt[(q["model"],q["effort"])]);return {**x,"observations":cnt[(x["model"],x["effort"])]}
def repo_defaults(root):return Path(root)/".agent-dispatch"/"defaults.json"
def load_defaults(root):return load(repo_defaults(root),{"schema":SCHEMA,"routes":{}}) if root else {"routes":{}}
def recommend(a):
 initq();tune();c=load(paths()[2],CFG);s=load(paths()[1],{});cs=candidates(a,s,c);pk,po=policy(a,s,c);prior=PRIORS.get(a.task_class,"general");rd=load_defaults(a.repo_root);dk=f"{a.task_class}|{a.domain or '*'}|{a.write_class or '*'}";saved=rd.get("routes",{}).get(dk);best=cs[0] if cs