#!/usr/bin/env python3
"""Adaptive local orchestration telemetry, policy learning, and reporting for Agent Dispatch."""
from __future__ import annotations
import argparse, datetime as dt, json, os, statistics, sys, uuid
from collections import defaultdict
from pathlib import Path

SCHEMA=3
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
    with t.open("a") as f:
        f.write(json.dumps(e,sort_keys=True)+"\n");f.flush();os.fsync(f.fileno())
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

def run_events(run_id):return [e for e in all_events() if e.get("run_id")==run_id]
def require_one(events,label):
    if len(events)!=1:raise SystemExit(f"Expected exactly one {label}; found {len(events)}")
    return events[0]
def lifecycle_start(run_id,task_id):
    return require_one([e for e in run_events(run_id) if e.get("event")=="delegated_task_started" and e.get("task_id")==task_id],f"start receipt for task {task_id}")

def begin_run(a):
    rid=a.run_id or str(uuid.uuid4())
    if any(e.get("run_id")==rid for e in all_events()):raise SystemExit(f"Run ID already exists: {rid}")
    e={"schema":SCHEMA,"timestamp":a.timestamp or now_iso(),"event":"run_started","run_id":rid,"project":a.project,
       "front_door_model":a.front_door_model,"front_door_revision":a.front_door_revision,
       "front_door_reasoning":a.front_door_reasoning,"skill_version":a.skill_version,"notes":a.notes}
    print(json.dumps(append_event(e),indent=2,sort_keys=True))

def begin_task(a):
    evs=run_events(a.run_id);run=require_one([e for e in evs if e.get("event")=="run_started"],f"run start for {a.run_id}")
    if any(e.get("event")=="run_summary" for e in evs):raise SystemExit(f"Run is already summarized: {a.run_id}")
    tid=a.task_id or str(uuid.uuid4())
    if any(e.get("task_id")==tid for e in evs):raise SystemExit(f"Task ID already exists in run {a.run_id}: {tid}")
    e={"schema":SCHEMA,"timestamp":a.timestamp or now_iso(),"event":"delegated_task_started","lifecycle_managed":True,
       "receipt_status":"pre_spawn","task_id":tid,"run_id":a.run_id,"parent_task_id":a.parent_task_id,
       "agent_id":a.agent_id,"project":a.project or run.get("project"),"task_class":a.task_class,"domain":a.domain,
       "front_door_model":run.get("front_door_model"),"front_door_revision":run.get("front_door_revision"),
       "front_door_reasoning":run.get("front_door_reasoning"),"requested_worker_model":a.worker_model,
       "requested_worker_revision":a.worker_revision,"requested_worker_reasoning":a.worker_reasoning,"tier":a.tier,
       "delegation_depth":a.delegation_depth,"parallel":a.parallel,"parallel_group_size":a.parallel_group_size,
       "write_class":a.write_class,"shadow":a.shadow,"consultation_mode":a.consultation_mode,
       "skill_version":a.skill_version or run.get("skill_version"),"notes":a.notes}
    print(json.dumps(append_event(e),indent=2,sort_keys=True))

def bind_task(a):
    start=lifecycle_start(a.run_id,a.task_id);evs=run_events(a.run_id)
    if any(e.get("event")=="delegated_task" and e.get("task_id")==a.task_id for e in evs):raise SystemExit(f"Task is already finished: {a.task_id}")
    if start.get("agent_id"):raise SystemExit(f"Task already has agent ID {start['agent_id']}: {a.task_id}")
    if any(e.get("event")=="delegated_task_bound" and e.get("task_id")==a.task_id for e in evs):raise SystemExit(f"Task is already bound: {a.task_id}")
    e={"schema":SCHEMA,"timestamp":a.timestamp or now_iso(),"event":"delegated_task_bound","lifecycle_managed":True,
       "run_id":a.run_id,"task_id":a.task_id,"agent_id":a.agent_id}
    print(json.dumps(append_event(e),indent=2,sort_keys=True))

def finish_task(a):
    start=lifecycle_start(a.run_id,a.task_id);evs=run_events(a.run_id)
    if any(e.get("event")=="delegated_task" and e.get("task_id")==a.task_id for e in evs):raise SystemExit(f"Task is already finished: {a.task_id}")
    binds=[e for e in evs if e.get("event")=="delegated_task_bound" and e.get("task_id")==a.task_id]
    if len(binds)>1:raise SystemExit(f"Task has duplicate agent bindings: {a.task_id}")
    ids={x for x in (start.get("agent_id"),binds[0].get("agent_id") if binds else None,a.agent_id) if x}
    if len(ids)>1:raise SystemExit(f"Task has conflicting agent IDs: {a.task_id}")
    agent_id=next(iter(ids),None);spawned=True if a.spawned is None else a.spawned
    if spawned and not agent_id:raise SystemExit("A spawned task must be bound to an agent ID before it can finish")
    if not spawned and agent_id:raise SystemExit("A not-spawned task cannot have an agent ID")
    if not spawned and a.outcome not in {"blocked","fail"}:raise SystemExit("A not-spawned task must finish blocked or fail")
    e={"schema":SCHEMA,"timestamp":a.timestamp or now_iso(),"event":"delegated_task","lifecycle_managed":True,
       "task_id":a.task_id,"run_id":a.run_id,"parent_task_id":start.get("parent_task_id"),"agent_id":agent_id,
       "spawned":spawned,"project":start.get("project"),"task_class":start.get("task_class"),"domain":start.get("domain"),
       "front_door_model":start.get("front_door_model"),"front_door_revision":start.get("front_door_revision"),
       "front_door_reasoning":start.get("front_door_reasoning"),"requested_worker_model":start.get("requested_worker_model"),
       "requested_worker_revision":start.get("requested_worker_revision"),"requested_worker_reasoning":start.get("requested_worker_reasoning"),
       "worker_model":a.actual_worker_model or start.get("requested_worker_model"),
       "worker_revision":a.actual_worker_revision or start.get("requested_worker_revision"),
       "worker_reasoning":a.actual_worker_reasoning or start.get("requested_worker_reasoning"),"tier":start.get("tier"),
       "delegation_depth":start.get("delegation_depth",0),"parallel":start.get("parallel"),
       "parallel_group_size":start.get("parallel_group_size"),"parallel_collision":a.parallel_collision,
       "write_class":start.get("write_class"),"shadow":start.get("shadow"),"consultation_mode":start.get("consultation_mode"),
       "frontier_use":a.frontier_use,"frontier_calls":a.frontier_calls,"duration_s":a.duration_s,
       "input_tokens":a.input_tokens,"output_tokens":a.output_tokens,"usage_source":a.usage_source,
       "retries":a.retries,"escalations":a.escalations,"review_pass":a.review_pass,"tests_pass":a.tests_pass,
       "rework":a.rework,"accepted":a.accepted,"outcome":a.outcome,"notes":a.notes,
       "skill_version":start.get("skill_version")}
    print(json.dumps(append_event(e),indent=2,sort_keys=True));maybe_tune()

def audit_run_data(run_id,expected_agent_ids=None,expected_task_count=None):
    evs=run_events(run_id);errors=[];warnings=[]
    run_starts=[e for e in evs if e.get("event")=="run_started"]
    if len(run_starts)!=1:errors.append(f"expected one run_started event; found {len(run_starts)}")
    starts=[e for e in evs if e.get("event")=="delegated_task_started"]
    if expected_task_count is not None and len(starts)!=expected_task_count:errors.append(f"expected {expected_task_count} task receipts; found {len(starts)}")
    task_ids=[e.get("task_id") for e in starts]
    for tid in sorted({x for x in task_ids if x}):
        if task_ids.count(tid)!=1:errors.append(f"duplicate task receipts: {tid}")
    turns=[e for e in evs if e.get("event")=="turn_usage"]
    components=[c for turn in turns for c in turn.get("components",[])]
    if not turns:errors.append("missing turn_usage event")
    front_usage=[c for c in components if c.get("role")=="front_door" and c.get("token_source") in {"measured","estimated","unknown"}]
    if turns and not front_usage:errors.append("missing measured, estimated, or unknown front-door usage component")
    for c in front_usage:
        source=c.get("token_source");vals=[c.get(k) for k in ("input_tokens","cached_input_tokens","output_tokens")]
        if source=="unknown" and any(v is not None for v in vals):errors.append("unknown front-door usage must not contain token counts")
        if source in {"measured","estimated"} and any(not isinstance(v,int) or v<0 for v in vals):errors.append("known front-door usage requires non-negative integer token counts")
    observed_agents=set();unknown_usage=0;completed=0
    for start in starts:
        tid=start.get("task_id");terms=[e for e in evs if e.get("event")=="delegated_task" and e.get("task_id")==tid]
        if len(terms)!=1:
            errors.append(f"task {tid} has {len(terms)} terminal events; expected 1");continue
        completed+=1;term=terms[0];binds=[e for e in evs if e.get("event")=="delegated_task_bound" and e.get("task_id")==tid]
        if len(binds)>1:errors.append(f"task {tid} has duplicate agent bindings")
        ids={x for x in (start.get("agent_id"),*(e.get("agent_id") for e in binds),term.get("agent_id")) if x}
        if len(ids)>1:errors.append(f"task {tid} has conflicting agent IDs")
        agent_id=next(iter(ids),None);spawned=term.get("spawned",True)
        if spawned and not agent_id:errors.append(f"task {tid} is spawned but unbound")
        if agent_id:observed_agents.add(agent_id)
        task_usage=[c for c in components if c.get("task_id")==tid]
        if spawned and len(task_usage)!=1:errors.append(f"task {tid} has {len(task_usage)} task-aware usage components; expected 1")
        if not spawned and task_usage:errors.append(f"task {tid} was not spawned but has usage")
        if task_usage:
            c=task_usage[0];source=c.get("token_source")
            if c.get("agent_id")!=agent_id:errors.append(f"task {tid} usage agent ID does not match its binding")
            if source not in {"measured","estimated","unknown"}:errors.append(f"task {tid} has invalid token source {source!r}")
            if source=="unknown":
                unknown_usage+=1
                if any(c.get(k) is not None for k in ("input_tokens","cached_input_tokens","output_tokens")):errors.append(f"task {tid} unknown usage must not contain token counts")
            elif source in {"measured","estimated"}:
                vals=[c.get(k) for k in ("input_tokens","cached_input_tokens","output_tokens")]
                if any(not isinstance(v,int) or v<0 for v in vals):errors.append(f"task {tid} known usage requires non-negative integer token counts")
    expected=set(expected_agent_ids or [])
    if expected:
        for aid in sorted(expected-observed_agents):errors.append(f"expected runtime agent is missing from receipts: {aid}")
        for aid in sorted(observed_agents-expected):errors.append(f"receipt agent is missing from runtime expectations: {aid}")
    summaries=[e for e in evs if e.get("event")=="run_summary"]
    if len(summaries)>1:errors.append(f"duplicate run summaries: {len(summaries)}")
    return {"ok":not errors,"run_id":run_id,"task_receipts":len(starts),"completed_tasks":completed,
            "observed_agent_ids":sorted(observed_agents),"unknown_usage_tasks":unknown_usage,"errors":errors,"warnings":warnings}

def audit_run(a):
    result=audit_run_data(a.run_id,a.expected_agent_id,a.expected_task_count)
    print(json.dumps(result,indent=2,sort_keys=True))
    if not result["ok"]:raise SystemExit(1)

def record_task(a):
    if a.run_id and any(e.get("event")=="delegated_task_started" and e.get("task_id")==a.task_id for e in run_events(a.run_id)):
        raise SystemExit("Lifecycle-managed tasks must be finalized with finish-task")
    e={"schema":SCHEMA,"timestamp":a.timestamp or now_iso(),"event":"delegated_task","task_id":a.task_id,
       "run_id":a.run_id,"parent_task_id":a.parent_task_id,"agent_id":a.agent_id,"project":a.project,"task_class":a.task_class,"domain":a.domain,
       "front_door_model":a.front_door_model,"front_door_revision":a.front_door_revision,"front_door_reasoning":a.front_door_reasoning,
       "worker_model":a.worker_model,"worker_revision":a.worker_revision,"worker_reasoning":a.worker_reasoning,"tier":a.tier,
       "delegation_depth":a.delegation_depth,"parallel":a.parallel,"parallel_group_size":a.parallel_group_size,
       "parallel_collision":a.parallel_collision,"write_class":a.write_class,"shadow":a.shadow,
       "consultation_mode":a.consultation_mode,"frontier_use":a.frontier_use,"frontier_calls":a.frontier_calls,
       "duration_s":a.duration_s,"input_tokens":a.input_tokens,"output_tokens":a.output_tokens,"usage_source":a.usage_source,
       "retries":a.retries,"escalations":a.escalations,"review_pass":a.review_pass,"tests_pass":a.tests_pass,
       "rework":a.rework,"accepted":a.accepted,"outcome":a.outcome,"notes":a.notes,"skill_version":a.skill_version}
    print(json.dumps(append_event(e),indent=2,sort_keys=True)); maybe_tune()
def record_run(a):
    evs=run_events(a.run_id)
    if any(e.get("event")=="run_summary" for e in evs):raise SystemExit(f"Run is already summarized: {a.run_id}")
    managed=any(e.get("event")=="run_started" for e in evs);audit=None
    if managed:
        expected_count=a.expected_task_count if a.expected_task_count is not None else a.delegated_tasks
        if expected_count is None:raise SystemExit("Managed run summaries require --delegated-tasks or --expected-task-count")
        spawned_ids={e.get("agent_id") for e in evs if e.get("event")=="delegated_task" and e.get("spawned",True) and e.get("agent_id")}
        if spawned_ids and not a.expected_agent_id:raise SystemExit("Managed run summaries with spawned tasks require --expected-agent-id for runtime reconciliation")
        audit=audit_run_data(a.run_id,a.expected_agent_id,expected_count)
        if not audit["ok"]:
            print(json.dumps(audit,indent=2,sort_keys=True),file=sys.stderr)
            raise SystemExit("Refusing to summarize run because telemetry audit failed")
    e={"schema":SCHEMA,"timestamp":a.timestamp or now_iso(),"event":"run_summary","run_id":a.run_id,"project":a.project,
       "front_door_model":a.front_door_model,"front_door_revision":a.front_door_revision,"front_door_reasoning":a.front_door_reasoning,
       "duration_s":a.duration_s,"input_tokens":a.input_tokens,"output_tokens":a.output_tokens,"usage_source":a.usage_source,
       "frontier_calls":a.frontier_calls,"frontier_tokens":a.frontier_tokens,"delegated_tasks":a.delegated_tasks,
       "max_parallelism":a.max_parallelism,"rework":a.rework,"accepted":a.accepted,"tests_pass":a.tests_pass,
       "review_pass":a.review_pass,"outcome":a.outcome,"skill_version":a.skill_version,"notes":a.notes,
       "telemetry_audit":"pass" if managed else None}
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
            buckets["|".join([p,e.get("task_class","unknown"),d,e.get("write_class") or "*"])].append((e,w))
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
    keys=[]; wc=a.write_class or "*"
    if a.project and a.domain:keys.append(f"{a.project}|{a.task_class}|{a.domain}|{wc}")
    if a.project and a.domain and wc!="*":keys.append(f"{a.project}|{a.task_class}|{a.domain}|*")
    if a.project:keys.append(f"{a.project}|{a.task_class}|*|{wc}")
    if a.domain:keys.append(f"*|{a.task_class}|{a.domain}|{wc}")
    keys.append(f"*|{a.task_class}|*|{wc}")
    if wc!="*":keys.append(f"*|{a.task_class}|*|*")
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
            "exploration":{"rate":cfg["exploration_rate"],"direct_control_eligible":prior!="frontier","shadow_eligible":True,"candidate":alt["model"] if alt else None,"mode":"shadow" if prior=="frontier" else "controlled"},
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
    for e in source:
        parts=[str(e.get("front_door_model") or "unknown"),str(e.get("front_door_revision") or ""),str(e.get("front_door_reasoning") or ""),str(e.get("skill_version") or "")]
        by["/".join(x for x in parts if x)].append(e)
    rows=[]
    for front,items in by.items():
        n=len(items);acc=sum(1 for e in items if clean_success(e))/n;rew=sum(1 for e in items if e.get("rework") is True)/n
        d=[float(e["duration_s"]) for e in items if e.get("duration_s") is not None];ft=sum(int(e.get("frontier_calls",0) or 0) for e in items)
        tok=[int(e.get("input_tokens",0) or 0)+int(e.get("output_tokens",0) or 0) for e in items if e.get("usage_source")=="measured"]
        rows.append({"front_door":front,"runs" if runs else "delegated_tasks":n,"clean_success_rate":round(acc,4),"rework_rate":round(rew,4),
                     "frontier_calls_per_run":round(ft/n,3) if runs else None,"median_duration_s":statistics.median(d) if d else None,"measured_tokens_sum":sum(tok) if tok else None})
    frontier=defaultdict(int);frontier_tokens=0
    for e in tasks:
        if e.get("tier")=="frontier" or int(e.get("frontier_calls",0) or 0)>0:frontier[e.get("frontier_use","unknown")]+=max(1,int(e.get("frontier_calls",0) or 0))
    for e in runs:frontier_tokens+=int(e.get("frontier_tokens",0) or 0)
    print(json.dumps({"run_events":len(runs),"delegated_task_events":len(tasks),"basis":"run_summary" if runs else "delegated_task_fallback","front_doors":rows,"frontier_use":dict(frontier),"frontier_tokens_sum":frontier_tokens or None},indent=2,sort_keys=True))
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
    br=s.add_parser("begin-run")
    for x in ("run-id","project","front-door-model","front-door-revision","front-door-reasoning","skill-version","notes","timestamp"):br.add_argument("--"+x)
    br.set_defaults(func=begin_run)
    bt=s.add_parser("begin-task")
    for x,req in (("run-id",True),("task-id",False),("parent-task-id",False),("agent-id",False),("project",False),("task-class",True),("domain",False),("worker-model",False),("worker-revision",False),("worker-reasoning",False),("skill-version",False),("notes",False),("timestamp",False)):bt.add_argument("--"+x,required=req)
    bt.add_argument("--tier",choices=TIERS,required=True);bt.add_argument("--delegation-depth",type=int,default=0)
    for x in ("parallel","shadow"):bt.add_argument("--"+x,type=boolish)
    bt.add_argument("--parallel-group-size",type=int);bt.add_argument("--write-class",choices=["read_only","write_isolated","write_shared"]);bt.add_argument("--consultation-mode",choices=["plan","consult","subtree","adjudicate"]);bt.set_defaults(func=begin_task)
    bind=s.add_parser("bind-task");bind.add_argument("--run-id",required=True);bind.add_argument("--task-id",required=True);bind.add_argument("--agent-id",required=True);bind.add_argument("--timestamp");bind.set_defaults(func=bind_task)
    ft=s.add_parser("finish-task")
    for x in ("run-id","task-id"):ft.add_argument("--"+x,required=True)
    for x in ("agent-id","actual-worker-model","actual-worker-revision","actual-worker-reasoning","notes","timestamp"):ft.add_argument("--"+x)
    for x in ("spawned","parallel-collision","review-pass","tests-pass","rework","accepted"):ft.add_argument("--"+x,type=boolish)
    ft.add_argument("--frontier-use",choices=["necessary","rescue","avoidable","unknown"]);ft.add_argument("--frontier-calls",type=int,default=0);ft.add_argument("--duration-s",type=float);ft.add_argument("--input-tokens",type=int);ft.add_argument("--output-tokens",type=int)
    ft.add_argument("--usage-source",choices=["measured","derived","unknown"],default="unknown");ft.add_argument("--retries",type=int,default=0);ft.add_argument("--escalations",type=int,default=0);ft.add_argument("--outcome",choices=["pass","partial","blocked","fail"],required=True);ft.set_defaults(func=finish_task)
    ar=s.add_parser("audit-run");ar.add_argument("--run-id",required=True);ar.add_argument("--expected-agent-id",action="append");ar.add_argument("--expected-task-count",type=int);ar.set_defaults(func=audit_run)
    r=s.add_parser("record")
    for x,req in (("task-id",True),("run-id",False),("parent-task-id",False),("agent-id",False),("project",False),("task-class",True),("domain",False),("front-door-model",False),("front-door-revision",False),("front-door-reasoning",False),("worker-model",False),("worker-revision",False),("worker-reasoning",False),("skill-version",False),("notes",False),("timestamp",False)):r.add_argument("--"+x,required=req)
    r.add_argument("--tier",choices=TIERS,required=True);r.add_argument("--delegation-depth",type=int,default=0)
    for x in ("parallel","parallel-collision","shadow","review-pass","tests-pass","rework","accepted"):r.add_argument("--"+x,type=boolish)
    r.add_argument("--parallel-group-size",type=int);r.add_argument("--write-class",choices=["read_only","write_isolated","write_shared"]);r.add_argument("--consultation-mode",choices=["plan","consult","subtree","adjudicate"])
    r.add_argument("--frontier-use",choices=["necessary","rescue","avoidable","unknown"]);r.add_argument("--frontier-calls",type=int,default=0);r.add_argument("--duration-s",type=float);r.add_argument("--input-tokens",type=int);r.add_argument("--output-tokens",type=int)
    r.add_argument("--usage-source",choices=["measured","derived","unknown"],default="unknown");r.add_argument("--retries",type=int,default=0);r.add_argument("--escalations",type=int,default=0);r.add_argument("--outcome",choices=["pass","partial","blocked","fail"]);r.set_defaults(func=record_task)
    rr=s.add_parser("record-run")
    for x,req in (("run-id",True),("project",False),("front-door-model",False),("front-door-revision",False),("front-door-reasoning",False),("skill-version",False),("notes",False),("timestamp",False)):rr.add_argument("--"+x,required=req)
    rr.add_argument("--expected-agent-id",action="append");rr.add_argument("--expected-task-count",type=int)
    for x in ("rework","accepted","tests-pass","review-pass"):rr.add_argument("--"+x,type=boolish)
    for x in ("frontier-calls","frontier-tokens","delegated-tasks","max-parallelism","input-tokens","output-tokens"):rr.add_argument("--"+x,type=int)
    rr.add_argument("--duration-s",type=float);rr.add_argument("--usage-source",choices=["measured","derived","unknown"],default="unknown");rr.add_argument("--outcome",choices=["pass","partial","blocked","fail"]);rr.set_defaults(func=record_run)
    s.add_parser("tune").set_defaults(func=tune_cmd)
    for name in ("recommend","explain"):
        q=s.add_parser(name);q.add_argument("--task-class",required=True);q.add_argument("--domain");q.add_argument("--project");q.add_argument("--write-class",choices=["read_only","write_isolated","write_shared"]);q.add_argument("--worker-revision");q.add_argument("--skill-version");q.add_argument("--delegation-depth",type=int,default=0);q.set_defaults(func=recommend)
    rep=s.add_parser("report");rep.add_argument("--project");rep.add_argument("--days",type=int);rep.set_defaults(func=report)
    rs=s.add_parser("reset");rs.add_argument("--learned-only",action="store_true");rs.add_argument("--yes",action="store_true");rs.set_defaults(func=reset);return p
def main():a=parser().parse_args();a.func(a);return 0
if __name__=="__main__":raise SystemExit(main())
