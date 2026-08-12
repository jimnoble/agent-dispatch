#!/usr/bin/env python3
"""Adaptive local orchestration telemetry, model×effort exploration, policy learning, and reporting."""
from __future__ import annotations
import argparse, datetime as dt, json, os, statistics, sys
from collections import defaultdict
from pathlib import Path

SCHEMA=3
TIERS=("frontier","general","cheap","alternate_pool")
EFFORT_ORDER=("none","minimal","low","medium","high","xhigh")
DEFAULT_CONFIG={
 "schema":SCHEMA,"min_samples":8,"promotion_min_samples":12,"promotion_min_clean_success":0.90,
 "promotion_max_rework":0.08,"promotion_min_utility_margin":0.03,"exploration_rate":0.05,"half_life_days":45.0,
 "max_recursive_depth":2,"default_concurrency":3,"max_concurrency":5,"tune_every":8,
 "scarcity_penalty":{"frontier":0.22,"general":0.08,"cheap":0.02,"alternate_pool":0.01},
 "effort_penalty":{"none":0.0,"minimal":0.002,"low":0.006,"medium":0.015,"high":0.03,"xhigh":0.05,"unknown":0.015},
 "rework_penalty":0.35,"escalation_penalty":0.16,"failure_penalty":0.55,"latency_penalty_per_minute":0.002,
 "review_failure_required_rate":0.10,"review_failure_recommended_rate":0.03,"collision_conservative_rate":0.10,
}
DEFAULT_CLASS_PRIORS={"architecture":"frontier","planning":"frontier","ambiguous_debugging":"frontier","adjudication":"frontier",
 "bounded_implementation":"general","ordinary_debugging":"general","code_review":"general","investigation":"general",
 "repository_inventory":"alternate_pool","mechanical_edit":"cheap","formatting":"cheap","simple_test":"cheap","metadata_extraction":"cheap"}
DEFAULT_REVIEW={"frontier":"required","general":"recommended","cheap":"optional","alternate_pool":"recommended"}

def now_iso(): return dt.datetime.now(dt.timezone.utc).isoformat()
def state_dir():
    if os.environ.get("AGENT_DISPATCH_HOME"): return Path(os.environ["AGENT_DISPATCH_HOME"]).expanduser()
    return Path(os.environ.get("CODEX_HOME",Path.home()/".codex")).expanduser()/"agent-dispatch"
def paths():
    r=state_dir(); return r/"telemetry.jsonl",r/"routing-state.json",r/"config.json",r/"cells.json"
def load_json(p,default):
    try:return json.loads(p.read_text())
    except FileNotFoundError:return default
    except json.JSONDecodeError as e:raise SystemExit(f"Invalid JSON in {p}: {e}")
def init_state_silent():
    t,r,c,cells=paths();t.parent.mkdir(parents=True,exist_ok=True);t.touch(exist_ok=True)
    if not c.exists():c.write_text(json.dumps(DEFAULT_CONFIG,indent=2)+"\n")
    if not r.exists():r.write_text(json.dumps({"schema":SCHEMA,"generated_at":now_iso(),"routes":{},"policies":{}},indent=2)+"\n")
    if not cells.exists():cells.write_text(json.dumps({"schema":SCHEMA,"cells":[]},indent=2)+"\n")
def init_state():init_state_silent();print(f"Agent Dispatch state initialized at {state_dir()}")
def boolish(v):
    if v is None:return None
    if v.lower() in {"1","true","yes","pass","passed"}:return True
    if v.lower() in {"0","false","no","fail","failed"}:return False
    raise argparse.ArgumentTypeError(v)
def append_event(e):
    init_state_silent();t,_,_,_=paths();e={k:v for k,v in e.items() if v is not None}
    with t.open("a") as f:f.write(json.dumps(e,sort_keys=True)+"\n")
    return e
def all_events(kind=None):
    init_state_silent();t,_,_,_=paths();out=[]
    for i,line in enumerate(t.read_text().splitlines(),1):
        if not line.strip():continue
        try:e=json.loads(line)
        except json.JSONDecodeError:print(f"warning: skipping invalid telemetry line {i}",file=sys.stderr);continue
        if kind is None or e.get("event")==kind:out.append(e)
    return out
def age_weight(ts,half):
    try:
        x=dt.datetime.fromisoformat(str(ts).replace("Z","+00:00"));x=x if x.tzinfo else x.replace(tzinfo=dt.timezone.utc)
        return .5**(max(0,(dt.datetime.now(dt.timezone.utc)-x).total_seconds()/86400)/max(1e-6,half))
    except:return 1.0
def evidence(e):
    if e.get("tests_pass") is False:return 0.0,"tests"
    if e.get("review_pass") is False:return .15,"review"
    if e.get("accepted") is False:return 0.0,"parent"
    if e.get("tests_pass") is True:return 1.0,"tests"
    if e.get("review_pass") is True:return .95,"review"
    if e.get("accepted") is True:return .85,"parent"
    if e.get("outcome")=="pass":return .55,"self_report"
    return 0.0,"none"
def clean_success(e):
    s,_=evidence(e);return s>=.85 and e.get("rework") is not True and e.get("parallel_collision") is not True
def effective_model(e):return e.get("effective_model") or e.get("requested_model") or e.get("worker_model") or e.get("tier","unknown")
def effective_effort(e):return e.get("effective_effort") or e.get("requested_effort") or e.get("worker_reasoning") or "unknown"
def utility(e,cfg):
    ev,_=evidence(e);score=ev
    if ev==0:score-=cfg["failure_penalty"]
    if e.get("rework") is True:score-=cfg["rework_penalty"]
    score-=cfg["escalation_penalty"]*float(e.get("escalations",0) or 0)
    score-=cfg["scarcity_penalty"].get(e.get("tier"),.05)
    score-=cfg["effort_penalty"].get(effective_effort(e),cfg["effort_penalty"]["unknown"])
    if e.get("duration_s") is not None:score-=cfg["latency_penalty_per_minute"]*float(e["duration_s"])/60
    return score
def maybe_tune():
    _,_,cp,_=paths();cfg=load_json(cp,DEFAULT_CONFIG);n=len(all_events("delegated_task"))
    if n and n%int(cfg.get("tune_every",8))==0:tune_internal()
def record_task(a):
    e={"schema":SCHEMA,"timestamp":a.timestamp or now_iso(),"event":"delegated_task","task_id":a.task_id,"run_id":a.run_id,
       "parent_task_id":a.parent_task_id,"project":a.project,"task_class":a.task_class,"domain":a.domain,
       "front_door_model":a.front_door_model,"front_door_revision":a.front_door_revision,"front_door_reasoning":a.front_door_reasoning,
       "requested_model":a.requested_model or a.worker_model,"requested_effort":a.requested_effort or a.worker_reasoning,
       "effective_model":a.effective_model,"effective_effort":a.effective_effort,"worker_revision":a.worker_revision,"tier":a.tier,
       "delegation_depth":a.delegation_depth,"parallel":a.parallel,"parallel_group_size":a.parallel_group_size,"parallel_collision":a.parallel_collision,
       "write_class":a.write_class,"shadow":a.shadow,"consultation_mode":a.consultation_mode,"frontier_use":a.frontier_use,"frontier_calls":a.frontier_calls,
       "duration_s":a.duration_s,"input_tokens":a.input_tokens,"output_tokens":a.output_tokens,"usage_source":a.usage_source,
       "retries":a.retries,"escalations":a.escalations,"failure_mode":a.failure_mode,"review_pass":a.review_pass,"tests_pass":a.tests_pass,
       "rework":a.rework,"accepted":a.accepted,"outcome":a.outcome,"notes":a.notes,"skill_version":a.skill_version}
    print(json.dumps(append_event(e),indent=2,sort_keys=True));maybe_tune()
def record_run(a):
    e={"schema":SCHEMA,"timestamp":a.timestamp or now_iso(),"event":"run_summary","run_id":a.run_id,"project":a.project,
       "front_door_model":a.front_door_model,"front_door_revision":a.front_door_revision,"front_door_reasoning":a.front_door_reasoning,
       "duration_s":a.duration_s,"input_tokens":a.input_tokens,"output_tokens":a.output_tokens,"usage_source":a.usage_source,
       "frontier_calls":a.frontier_calls,"frontier_tokens":a.frontier_tokens,"delegated_tasks":a.delegated_tasks,"max_parallelism":a.max_parallelism,
       "rework":a.rework,"accepted":a.accepted,"tests_pass":a.tests_pass,"review_pass":a.review_pass,"outcome":a.outcome,"skill_version":a.skill_version,"notes":a.notes}
    print(json.dumps(append_event(e),indent=2,sort_keys=True))
def aggregate(rows,cfg):
    tw=sum(w for _,w in rows) or 1;rev=[(e,w) for e,w in rows if e.get("review_pass") is not None];cols=[(e,w) for e,w in rows if e.get("parallel") is True]
    pg=[int(e["parallel_group_size"]) for e,_ in rows if e.get("parallel_group_size") and e.get("parallel_collision") is not True and clean_success(e)]
    d=[float(e["duration_s"]) for e,_ in rows if e.get("duration_s") is not None]
    return {"samples":len(rows),"effective_samples":round(tw,3),"clean_success_rate":round(sum(w for e,w in rows if clean_success(e))/tw,4),
      "rework_rate":round(sum(w for e,w in rows if e.get("rework") is True)/tw,4),"mean_escalations":round(sum(w*float(e.get("escalations",0) or 0) for e,w in rows)/tw,4),
      "utility":round(sum(utility(e,cfg)*w for e,w in rows)/tw,4),"review_failure_rate":round(sum(w for e,w in rev if e.get("review_pass") is False)/(sum(w for _,w in rev) or 1),4) if rev else 0,
      "parallel_collision_rate":round(sum(w for e,w in cols if e.get("parallel_collision") is True)/(sum(w for _,w in cols) or 1),4) if cols else 0,
      "successful_parallel_group_median":statistics.median(pg) if pg else None,"median_duration_s":round(statistics.median(d),3) if d else None}
def tune_internal():
    init_state_silent();_,rp,cp,_=paths();cfg=load_json(cp,DEFAULT_CONFIG);evs=all_events("delegated_task");groups=defaultdict(list);buckets=defaultdict(list)
    for e in evs:
        w=age_weight(e.get("timestamp"),cfg["half_life_days"]);model=effective_model(e);eff=effective_effort(e)
        for p,d in ((e.get("project") or "*",e.get("domain") or "*"),(e.get("project") or "*","*"),("*",e.get("domain") or "*"),("*","*")):
            groups["|".join([p,e.get("task_class","unknown"),d,model,e.get("worker_revision") or "*",eff,e.get("skill_version") or "*"])].append((e,w))
            buckets["|".join([p,e.get("task_class","unknown"),d,e.get("write_class") or "*"])].append((e,w))
    routes={k:aggregate(v,cfg) for k,v in groups.items()};policies={}
    for k,rows in buckets.items():
        m=aggregate(rows,cfg);esc=sum(1 for e,_ in rows if int(e.get("escalations",0) or 0)>0)/max(1,len(rows));rb=0 if esc>.45 else (1 if esc>.15 else 2)
        rev="required" if m["review_failure_rate"]>=cfg["review_failure_required_rate"] else ("recommended" if m["review_failure_rate"]>=cfg["review_failure_recommended_rate"] else "optional")
        conc=cfg["default_concurrency"];med=m["successful_parallel_group_median"]
        if med:conc=min(cfg["max_concurrency"],max(2,int(round(med))))
        if m["parallel_collision_rate"]>=cfg["collision_conservative_rate"]:conc=max(1,conc-1)
        policies[k]={"samples":len(rows),"retry_budget":rb,"escalate_after_failures":1 if esc>.25 else 2,"reviewer_policy":rev,"preferred_concurrency":conc,"parallel_collision_rate":m["parallel_collision_rate"]}
    rp.write_text(json.dumps({"schema":SCHEMA,"generated_at":now_iso(),"routes":routes,"policies":policies},indent=2,sort_keys=True)+"\n");return len(evs)
def tune_cmd(_):print(f"Updated {paths()[1]} from {tune_internal()} delegated-task events")
def cells():return load_json(paths()[3],{"cells":[]}).get("cells",[])
def register_cell(a):
    init_state_silent();p=paths()[3];data=load_json(p,{"schema":SCHEMA,"cells":[]});cell={"model":a.model,"effort":a.effort,"tier":a.tier,"revision":a.revision}
    if cell not in data["cells"]:data["cells"].append(cell);p.write_text(json.dumps(data,indent=2,sort_keys=True)+"\n")
    print(json.dumps(cell,indent=2))
def route_candidates(a,state,cfg):
    out=[]
    for key,m in state.get("routes",{}).items():
        p,tc,d,model,rev,eff,skillver=key.split("|",6)
        if tc!=a.task_class or m["samples"]<cfg["min_samples"]:continue
        spec=0
        if a.project and p==a.project:spec+=4
        elif p!="*":continue
        if a.domain and d==a.domain:spec+=2
        elif d!="*":continue
        if a.worker_revision and rev==a.worker_revision:spec+=1
        elif a.worker_revision and rev!="*":continue
        if a.skill_version and skillver==a.skill_version:spec+=1
        elif a.skill_version and skillver!="*":continue
        out.append({"model":model,"revision":rev,"effort":eff,"skill_version":skillver,"specificity":spec,**m})
    return sorted(out,key=lambda x:(x["specificity"],x["utility"],x["clean_success_rate"]),reverse=True)
def policy_for(a,state,cfg):
    wc=a.write_class or "*";keys=[]
    if a.project and a.domain:keys += [f"{a.project}|{a.task_class}|{a.domain}|{wc}",f"{a.project}|{a.task_class}|{a.domain}|*"]
    if a.project:keys.append(f"{a.project}|{a.task_class}|*|{wc}")
    if a.domain:keys.append(f"*|{a.task_class}|{a.domain}|{wc}")
    keys += [f"*|{a.task_class}|*|{wc}",f"*|{a.task_class}|*|*"]
    for k in dict.fromkeys(keys):
        p=state.get("policies",{}).get(k)
        if p and p.get("samples",0)>=cfg["min_samples"]:return k,p
    tier=DEFAULT_CLASS_PRIORS.get(a.task_class,"general");return None,{"retry_budget":1,"escalate_after_failures":1 if tier=="frontier" else 2,"reviewer_policy":DEFAULT_REVIEW[tier],"preferred_concurrency":cfg["default_concurrency"]}
def observed_counts(a):
    count=defaultdict(int)
    for e in all_events("delegated_task"):
        if e.get("task_class")!=a.task_class:continue