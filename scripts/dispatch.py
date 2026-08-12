#!/usr/bin/env python3
"""Adaptive local orchestration telemetry, policy learning, and reporting for Agent Dispatch."""
from __future__ import annotations
import argparse, datetime as dt, json, os, statistics, sys
from collections import defaultdict
from pathlib import Path

SCHEMA=2
TIERS=("frontier","general","cheap","alternate_pool")
DEFAULT_CONFIG={
 "schema":SCHEMA,"min_samples":8,"exploration_rate":0.05,"half_life_days":45.0,
 "max_recursive_depth":2,"default_concurrency":3,"max_concurrency":5,"tune_every":8,
 "prior_success":{"frontier":0.97,"general":0.90,"cheap":0.78,"alternate_pool":0.82},
 "scarcity_penalty":{"frontier":0.22,"general":0.08,"cheap":0.02,"alternate_pool":0.01},
 "rework_penalty":0.35,"escalation_penalty":0.16,"failure_penalty":0.55,
 "latency_penalty_per_minute":0.002,"review_failure_required_rate":0.10,
 "review_failure_recommended_rate":0.03,"collision_conservative_rate":0.10,
}
DEFAULT_CLASS_PRIORS={
 "architecture":"frontier","planning":"frontier","ambiguous_debugging":"frontier","adjudication":"frontier",
 "bounded_implementation":"general","ordinary_debugging":"general","code_review":"general","investigation":"general",
 "repository_inventory":"alternate_pool","mechanical_edit":"cheap","formatting":"cheap","simple_test":"cheap",
 "metadata_extraction":"cheap",
}
DEFAULT_REVIEW={"frontier":"required","general":"recommended","cheap":"optional","alternate_pool":"recommended"}

def now_iso(): return dt.datetime.now(dt.timezone.utc).isoformat()
def state_dir():
    if os.environ.get("AGENT_DISPATCH_HOME"): return Path(os.environ["AGENT_DISPATCH_HOME"]).expanduser()
    return Path(os.environ.get("CODEX_HOME",Path.home()/".codex")).expanduser()/"agent-dispatch"
def paths():
    r=state_dir(); return r/"telemetry.jsonl",r/"routing-state.json",r/"config.json"
def load_json(p,default):
    try:return json.loads(p.read_text())
    except FileNotFoundError:return default
    except json.JSONDecodeError as e: raise SystemExit(f"Invalid JSON in {p}: {e}")
def init_state_silent():
    t,r,c=paths(); t.parent.mkdir(parents=True,exist_ok=True); t.touch(exist_ok=True)
    if not c.exists(): c.write_text(json.dumps(DEFAULT_CONFIG,indent=2)+"\n")
    if not r.exists(): r.write_text(json.dumps({"schema":SCHEMA,"generated_at":now_iso(),"routes":{},"policies":{}},indent=2)+"\n")
def init_state():
    init_state_silent(); print(f"Agent Dispatch state initialized at {state_dir()}")
def boolish(v):
    if v is None:return None
    v=v.lower()
    if v in {"1","true","yes","pass","passed"}:return True
    if v in {"0","false","no","fail","failed"}:return False
    raise argparse.ArgumentTypeError(v)
def append_event(e):
    init_state_silent(); t,_,_=paths(); e={k:v for k,v in e.items() if v is not None}
    with t.open("a") as f:f.write(json.dumps(e,sort_keys=True)+"\n")
    return e
def all_events(kind=None):
    init_state_silent(); t,_,_=paths(); out=[]
    for i,line in enumerate(t.read_text().splitlines(),1):
        if not line.strip():continue
        try:e=json.loads(line)
        except json.JSONDecodeError:
            print(f"warning: skipping invalid telemetry line {i}",file=sys.stderr);continue
        if kind is None or e.get("event")==kind:out.append(e)
    return out
def age_weight(ts,half):
    try:
        x=dt.datetime.fromisoformat(str(ts).replace("Z","+00:00"))
        if x.tzinfo is None:x=x.replace(tzinfo=dt.timezone.utc)
        age=max(0,(dt.datetime.now(dt.timezone.utc)-x).total_seconds()/86400)
        return .5**(age/max(1e-6,half))
    except Exception:return 1.0
def evidence(e):
    if e.get("tests_pass") is False:return (0.0,"tests")
    if e.get("review_pass") is False:return (0.15,"review")
    if e.get("accepted") is False:return (0.0,"parent")
    if e.get("tests_pass") is True:return (1.0,"tests")
    if e.get("review_pass") is True:return (0.95,"review")
    if e.get("accepted") is True:return (0.85,"parent")
    if e.get("outcome")=="pass":return (0.55,"self_report")
    return (0.0,"none")
def clean_success(e):
    s,_=evidence(e); return s>=0.85 and e.get("rework") is not True and e.get("parallel_collision") is not True
def utility(e,cfg):
    ev,_=evidence(e); score=ev
    if ev==0:score-=cfg["failure_penalty"]
    if e.get("rework") is True:score-=cfg["rework_penalty"]
    score-=cfg["escalation_penalty"]*float(e.get("escalations",0) or 0)
    score-=cfg["scarcity_penalty"].get(e.get("tier"),.05)
    if e.get("duration_s") is not None:score-=cfg["latency_penalty_per_minute"]*float(e["duration_s"])/60
    return score
def maybe_tune():
    init_state_silent(); _,_,cp=paths(); cfg=load_json(cp,DEFAULT_CONFIG); n=len(all_events("delegated_task"))
    if n and n % int(cfg.get("tune_every",8))==0:tune_internal()

def record_task(a):
    e={"schema":SCHEMA,"timestamp":a.timestamp or now_iso(),"event":"delegated_task","task_id":a.task_id,
       "run_id":a.run_id,"parent_task_id":a.parent_task_id,"project":a.project,"task_class":a.task_class,"domain":a.domain,
       "front_door_model":a.front_door_model,"front_door_reasoning":a.front_door_reasoning,
       "worker_model":a.worker_model,"worker_revision":a.worker_revision,"worker_reasoning":a.worker_reasoning,"tier":a.tier,
       "delegation_depth":a.delegation_depth,"parallel":a.parallel,"parallel_group_size":a.parallel_group_size,
       "parallel_collision":a.parallel_collision,"write_class":a.write_class,"shadow":a.shadow,
       "consultation_mode":a.consultation_mode,"frontier_use":a.frontier_use,"frontier_calls":a.frontier_calls,
       "duration_s":a.duration_s,"input_tokens":a.input_tokens,"output_tokens":a.output_tokens,"usage_source":a.usage_source,
       "retries":a.retries,"escalations":a.escalations,"review_pass":a.review_pass,"tests_pass":a.tests_pass,
       "rework":a.rework,"accepted":a.accepted,"outcome":a.outcome,"notes":a.notes,"skill_version":a.skill_version}
    print(json.dumps(append_event(e),indent=2,sort_keys=True)); maybe_tune()
def record_run(a):
    e={"schema":SCHEMA,"timestamp":a.timestamp or now_iso(),"event":"run_summary","run_id":a.run_id,"project":a.project,
       "front_door_model":a.front_door_model,"front_door_reasoning":a.front_door_reasoning,
       "duration_s":a.duration_s,"input_tokens":a.input_tokens,"output_tokens":a.output_tokens,"usage_source":a.usage_source,
       "frontier_calls":a.frontier_calls,"frontier_tokens":a.frontier_tokens,"delegated_tasks":a.delegated_tasks,
       "max_parallelism":a.max_parallelism,"rework":a.rework,"accepted":a.accepted,"tests_pass":a.tests_pass,
       "review_pass":a.review_pass,"outcome":a.outcome,"skill_version":a.skill_version,"notes":a.notes}
    print(json.dumps(append_event(e),indent=2,sort_keys=True))
def aggregate_rows(rows,cfg):
    tw=sum(w for _,w in rows) or 1
    clean=sum(w for e,w in rows if clean_success(e))/tw
    rework=sum(w for e,w in rows if e.get("rework") is True)/tw
    esc=sum(w*float(e.get("escalations",0) or 0) for e,w in rows)/tw
    util=sum(utility(e,cfg)*w for e,w in rows)/tw
    revrows=[(e,w) for e,w in rows if e.get("review_pass") is not None]
    revfail=(sum(w for e,w in revrows if e.get("review_pass") is False)/(sum(w for _,w in revrows) or 1)) if revrows else 0
    cols=[(e,w) for e,w in rows if e.get("parallel") is True]
    colrate=(sum(w for e,w in cols if e.get("parallel_collision") is True)/(sum(w for _,w in cols) or 1)) if cols else 0
    pg=[int(e["parallel_group_size"]) for e,_ in rows if e.get("parallel_group_size") and e.get("parallel_collision") is not True and clean_success(e)]
    durs=[float(e["duration_s"]) for e,_ in rows if e.get("duration_s") is not None]
    return {"samples":len(rows),"effective_samples":round(tw,3),"clean_success_rate":round(clean,4),
            "rework_rate":round(rework,4),"mean_escalations":round(esc,4),"utility":round(util,4),
            "review_failure_rate":round(revfail,4),"parallel_collision_rate":round(colrate,4),
            "successful_parallel_group_median":statistics.median(pg) if pg else None,
            "median_duration_s":round(statistics.median(durs),3) if durs else None}
def tune_internal():
    init_state_silent(); _,rp,cp=paths(); cfg=load_json(cp,DEFAULT_CONFIG); evs=all_events("delegated_task"); groups=defaultdict(list)
    for e in evs:
        w=age_weight(e.get("timestamp"),cfg["half_life_days"])
        for p,d in ((e.get("project") or "*",e.get("domain") or "*"),(e.get("project") or "*","*"),("*",e.get("domain") or "*"),("*","*")):
            key="|".join([p,e.get("task_class","unknown"),d,e.get("worker_model") or e.get("tier","unknown"),
                          e.get("worker_revision") or "*",e.get("worker_reasoning") or "*",e.get("skill_version") or "*"])
            groups[key].append((e,w))
    routes={k:aggregate_rows(v,cfg) for k,v in groups.items()}; policies={}; buckets=defaultdict(list)
    for e in evs:
        w=age_weight(e.get("timestamp"),cfg["half_life_days"])
        for p,d in ((e.get("project") or "*",e.get("domain") or "*"),(e.get("project") or "*","*"),("*",e.get("domain") or "*"),("*","*")):
            buckets["|".join([p,e.get("task_class","unknown"),d])].append((e,w))
    for k,rows in buckets.items():
        m=aggregate_rows(rows,cfg); esc_rate=sum(1 for e,_ in rows if int(e.get("escalations",0) or 0)>0)/max(1,len(rows))
        retry_budget=0 if esc_rate>.45 else (1 if esc_rate>.15 else 2); escalation_after=1 if esc_rate>.25 else 2
        rev="required" if m["review_failure_rate"]>=cfg["review_failure_required_rate"] else ("recommended" if m["review_failure_rate"]>=cfg["review_failure_recommended_rate"] else "optional")
        conc=cfg["default_concurrency"]; med=m["successful_parallel_group_median"]
        if med:conc=min(cfg["max_concurrency"],max(2,int(round(med))))
        if m["parallel_collision_rate"]>=cfg["collision_conservative_rate"]:conc=max(1,conc-1)
        policies[k]={"samples":len(rows),"retry_budget":retry_budget,"escalate_after_failures":escalation_after,
                     "reviewer_policy":rev,"preferred_concurrency":conc,"parallel_collision_rate":m["parallel_collision_rate"]}
    rp.write_text(json.dumps({"schema":SCHEMA,"generated_at":now_iso(),"routes":routes,"policies":policies},indent=2,sort_keys=True)+"\n"); return len(evs)
def tune_cmd(_):print(f"Updated {paths()[1]} from {tune_internal()} delegated-task events")
def route_candidates(a,state,cfg):
    out=[]
    for key,m in state.get("routes",{}).items():
        p,tc,d,model,rev,reason,skillver=key.split("|",6)
        if tc!=a.task_class or m["samples"]<cfg["min_samples"]:continue
        specificity=0
        if a.project and p==a.project:specificity+=4
        elif p!="*":continue
        if a.domain and d==a.domain:specificity+=2
        elif d!="*":continue
        if a.worker_revision and rev==a.worker_revision:specificity+=1
        elif rev!="*" and a.worker_revision:continue
        if a.skill_version and skillver==a.skill_version:specificity+=1
        elif a.skill_version and skillver!="*":continue
        out.append({"model":model,"revision":rev,"reasoning":reason,"skill_version":skillver,"specificity":specificity,**m})
    return sorted(out,key=lambda x:(x["specificity"],x["utility"],x["clean_success_rate"]),reverse=True)
def policy_for(a,state,cfg):
    keys=[]
    if a.project and a.domain:keys.append(f"{a.project}|{a.task_class}|{a.domain}")
    if a.project:keys.append(f"{a.project}|{a.task_class}|*")
    if a.domain:keys.append(f"*|{a.task_class}|{a.domain}")
    keys.append(f"*|{a.task_class}|*")
    for k in keys:
        p=state.get("policies",{}).get(k)
        if p and p.get("samples",0)>=cfg["min_samples"]:return k,p
    tier=DEFAULT_CLASS_PRIORS.get(a.task_class,"general")
    return None,{"retry_budget":1,"escalate_after_failures":1 if tier=="frontier" else 2,"reviewer_policy":DEFAULT_REVIEW[tier],"preferred_concurrency":cfg["default_concurrency"]}
def recommend(a):
    init_state_silent(); tune_internal(); _,rp,cp=paths(); state=load_json(rp,{"routes":{},"policies":{}});cfg=load_json(cp,DEFAULT_CONFIG)
    cs=route_candidates(a,state,cfg); prior=DEFAULT_CLASS_PRIORS.get(a.task_class,"general"); pk,pol=policy_for(a,state,cfg); rec={"tier":prior}; learned=False
    if cs:
        b=cs[0];learned=True;rec={"model_or_tier":b["model"],"model_revision":None if b["revision"]=="*" else b["revision"],
             "reasoning":None if b["reasoning"]=="*" else b["reasoning"],
             "evidence":{k:b[k] for k in ("samples","effective_samples","clean_success_rate","rework_rate","mean_escalations","utility","specificity")}}
    alt=None
    if cs:
        best=cs[0]; others=[x for x in cs[1:] if x["model"]!=best["model"]]
        if others:alt=min(others,key=lambda x:x["samples"])
    result={"task_class":a.task_class,"domain":a.domain,"project":a.project,"default_tier":prior,"learned_override":learned,
            "recommendation":rec,"policy_source":pk,"execution_policy":pol,
            "exploration":{"rate":cfg["exploration_rate"],"eligible":prior!="frontier","candidate":alt["model"] if alt else None,"mode":"shadow" if prior=="frontier" else "controlled"},
            "recursive_delegation":{"max_depth":cfg["max_recursive_depth"],"remaining_depth":max(0,cfg["max_recursive_depth"]-(a.delegation_depth or 0))}}
    if prior=="frontier":result["frontier_consultation"]="Prefer plan/consult/adjudicate; use subtree only when frontier-heavy ownership is genuinely cheaper than repeated consultation."
    print(json.dumps(result,indent=2,sort_keys=True))
def report(a):
    tasks=all_events("delegated_task"); runs=all_events("run_summary")
    if a.project:tasks=[e for e in tasks if e.get("project")==a.project];runs=[e for e in runs if e.get("project")==a.project]
    if a.days:
        cut=dt.datetime.now(dt.timezone.utc)-dt.timedelta(days=a.days)
        def recent(e):
            try:return dt.datetime.fromisoformat(str(e.get("timestamp","")).replace("Z","+00:00"))>=cut
            except:return False
        tasks=[e for e in tasks if recent(e)];runs=[e for e in runs if recent(e)]
    by=defaultdict(list); source=runs if runs else tasks
    for e in source:by[f"{e.get('front_door_model','unknown')}/{e.get('front_door_reasoning','')}".rstrip("/")].append(e)
    rows=[]
    for front,items in by.items():
        n=len(items);acc=sum(1 for e in items if clean_success(e))/n;rew=sum(1 for e in items if e.get("rework") is True)/n
        d=[float(e["duration_s"]) for e in items if e.get("duration_s") is not None];ft=sum(int(e.get("frontier_calls",0) or 0) for e in items)
        tok=[int(e.get("input_tokens",0) or 0)+int(e.get("output_tokens",0) or 0) for e in items if e.get("usage_source")=="measured"]
        rows.append({"front_door":front,"runs" if runs else "delegated_tasks":n,"clean_success_rate":round(acc,4),"rework_rate":round(rew,4),
                     "frontier_calls_per_run":round(ft/n,3) if runs else None,"median_duration_s":statistics.median(d) if d else None,"measured_tokens_sum":sum(tok) if tok else None})
    frontier=defaultdict(int)
    for e in tasks:
        if e.get("tier")=="frontier":frontier[e.get("frontier_use","unknown")]+=1
    print(json.dumps({"run_events":len(runs),"delegated_task_events":len(tasks),"basis":"run_summary" if runs else "delegated_task_fallback","front_doors":rows,"frontier_use":dict(frontier)},indent=2,sort_keys=True))
def reset(a):
    t,r,c=paths()
    if a.learned_only:
        r.parent.mkdir(parents=True,exist_ok=True);r.write_text(json.dumps({"schema":SCHEMA,"generated_at":now_iso(),"routes":{},"policies":{}},indent=2)+"\n");print(f"Reset learned routing state; retained telemetry at {t}");return
    if not a.yes:raise SystemExit("Refusing to delete telemetry without --yes (or use --learned-only).")
    for p in (t,r,c):
        if p.exists():p.unlink()
    print(f"Reset Agent Dispatch state at {state_dir()}")
def parser():
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest="cmd",required=True);s.add_parser("init").set_defaults(func=lambda a:init_state())
    r=s.add_parser("record")
    for x,req in (("task-id",True),("run-id",False),("parent-task-id",False),("project",False),("task-class",True),("domain",False),("front-door-model",False),("front-door-reasoning",False),("worker-model",False),("worker-revision",False),("worker-reasoning",False),("skill-version",False),("notes",False),("timestamp",False)):r.add_argument("--"+x,required=req)
    r.add_argument("--tier",choices=TIERS,required=True);r.add_argument("--delegation-depth",type=int,default=0)
    for x in ("parallel","parallel-collision","shadow","review-pass","tests-pass","rework","accepted"):r.add_argument("--"+x,type=boolish)
    r.add_argument("--parallel-group-size",type=int);r.add_argument("--write-class",choices=["read_only","write_isolated","write_shared"]);r.add_argument("--consultation-mode",choices=["plan","consult","subtree","adjudicate"])
    r.add_argument("--frontier-use",choices=["necessary","rescue","avoidable","unknown"]);r.add_argument("--frontier-calls",type=int,default=0);r.add_argument("--duration-s",type=float);r.add_argument("--input-tokens",type=int);r.add_argument("--output-tokens",type=int)
    r.add_argument("--usage-source",choices=["measured","derived","unknown"],default="unknown");r.add_argument("--retries",type=int,default=0);r.add_argument("--escalations",type=int,default=0);r.add_argument("--outcome",choices=["pass","partial","blocked","fail"]);r.set_defaults(func=record_task)
    rr=s.add_parser("record-run")
    for x,req in (("run-id",True),("project",False),("front-door-model",False),("front-door-reasoning",False),("skill-version",False),("notes",False),("timestamp",False)):rr.add_argument("--"+x,required=req)
    for x in ("rework","accepted","tests-pass","review-pass"):rr.add_argument("--"+x,type=boolish)
    for x in ("frontier-calls","frontier-tokens","delegated-tasks","max-parallelism","input-tokens","output-tokens"):rr.add_argument("--"+x,type=int)
    rr.add_argument("--duration-s",type=float);rr.add_argument("--usage-source",choices=["measured","derived","unknown"],default="unknown");rr.add_argument("--outcome",choices=["pass","partial","blocked","fail"]);rr.set_defaults(func=record_run)
    s.add_parser("tune").set_defaults(func=tune_cmd)
    for name in ("recommend","explain"):
        q=s.add_parser(name);q.add_argument("--task-class",required=True);q.add_argument("--domain");q.add_argument("--project");q.add_argument("--worker-revision");q.add_argument("--skill-version");q.add_argument("--delegation-depth",type=int,default=0);q.set_defaults(func=recommend)
    rep=s.add_parser("report");rep.add_argument("--project");rep.add_argument("--days",type=int);rep.set_defaults(func=report)
    rs=s.add_parser("reset");rs.add_argument("--learned-only",action="store_true");rs.add_argument("--yes",action="store_true");rs.set_defaults(func=reset);return p
def main():a=parser().parse_args();a.func(a);return 0
if __name__=="__main__":raise SystemExit(main())
