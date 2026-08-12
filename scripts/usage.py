#!/usr/bin/env python3
"""Per-subagent, turn, and aggregate token/credit accounting for Agent Dispatch."""
from __future__ import annotations
import argparse, datetime as dt, json, os
from collections import defaultdict
from pathlib import Path
SCHEMA=2
RATE_CARD_AS_OF="2026-08-12"
RATE_CARD_SOURCE="https://help.openai.com/en/articles/20001106-codex-rate-card"
DEFAULT_RATES={
 "gpt-5.6-sol":{"input":125.,"cached_input":12.5,"output":750.,"rough_local_message":14.},"sol":{"input":125.,"cached_input":12.5,"output":750.,"rough_local_message":14.},
 "gpt-5.6-terra":{"input":62.5,"cached_input":6.25,"output":375.,"rough_local_message":7.},"terra":{"input":62.5,"cached_input":6.25,"output":375.,"rough_local_message":7.},
 "gpt-5.6-luna":{"input":25.,"cached_input":2.5,"output":150.,"rough_local_message":3.},"luna":{"input":25.,"cached_input":2.5,"output":150.,"rough_local_message":3.},
 "gpt-5.5":{"input":125.,"cached_input":12.5,"output":750.,"rough_local_message":14.},"gpt-5.4":{"input":62.5,"cached_input":6.25,"output":375.,"rough_local_message":7.},
 "gpt-5.4-mini":{"input":18.75,"cached_input":1.875,"output":113.},"gpt-5.3-codex":{"input":43.75,"cached_input":4.375,"output":350.},"gpt-5.2":{"input":43.75,"cached_input":4.375,"output":350.}
}
def now():return dt.datetime.now(dt.timezone.utc).isoformat()
def home():return Path(os.environ.get("AGENT_DISPATCH_HOME",Path(os.environ.get("CODEX_HOME",Path.home()/".codex"))/"agent-dispatch")).expanduser()
def tp():return home()/"telemetry.jsonl"
def rp():return home()/"rate-card.json"
def rates():
 p=rp();p.parent.mkdir(parents=True,exist_ok=True)
 if not p.exists():p.write_text(json.dumps({"schema":SCHEMA,"as_of":RATE_CARD_AS_OF,"source":RATE_CARD_SOURCE,"rates":DEFAULT_RATES},indent=2,sort_keys=True)+"\n")
 return json.loads(p.read_text())
def events():
 if not tp().exists():return []
 out=[]
 for l in tp().read_text().splitlines():
  try:out.append(json.loads(l))
  except json.JSONDecodeError:pass
 return out
def append(e):
 p=tp();p.parent.mkdir(parents=True,exist_ok=True)
 with p.open("a") as f:f.write(json.dumps(e,sort_keys=True)+"\n")
def norm(x):return (x or "").strip().lower()
def credit(model,i,c,o,card):
 r=card.get("rates",{}).get(norm(model));return None if not r else (i*r["input"]+c*r["cached_input"]+o*r["output"])/1e6
def parse_usage(s):
 # agent_id,role,model,effort,input,cached,output,source
 p=[x.strip() for x in s.split(",")]
 if len(p)!=8:raise argparse.ArgumentTypeError("usage must be agent_id,role,model,effort,input,cached_input,output,measured|estimated")
 if p[7] not in {"measured","estimated"}:raise argparse.ArgumentTypeError("source must be measured or estimated")
 try:i,c,o=map(int,p[4:7])
 except:raise argparse.ArgumentTypeError("token counts must be integers")
 return {"agent_id":p[0],"role":p[1],"model":p[2],"effort":p[3],"input_tokens":i,"cached_input_tokens":c,"output_tokens":o,"token_source":p[7]}
def parse_message(s):
 p=[x.strip() for x in s.split(",")]
 if len(p) not in {4,5}:raise argparse.ArgumentTypeError("message must be agent_id,role,model,effort[,count]")
 return {"agent_id":p[0],"role":p[1],"model":p[2],"effort":p[3],"count":int(p[4]) if len(p)==5 else 1}
def baseline_component(x,card,model="gpt-5.6-sol",mult=1.0):
 i=round(x["input_tokens"]*mult);c=round(x["cached_input_tokens"]*mult);o=round(x["output_tokens"]*mult)
 return credit(model,i,c,o,card)
def record(a):
 card=rates();comps=[];actual_known=0.;actual_complete=True;base_known=0.;base_complete=True;tok=0
 for u in a.usage or []:
  x=dict(u);x["derived_credits"]=credit(x["model"],x["input_tokens"],x["cached_input_tokens"],x["output_tokens"],card);x["sol_max_same_token_credits"]=baseline_component(x,card,a.baseline_model,a.baseline_token_multiplier)
  tok+=x["input_tokens"]+x["cached_input_tokens"]+x["output_tokens"]
  if x["derived_credits"] is None:actual_complete=False
  else:actual_known+=x["derived_credits"]
  if x["sol_max_same_token_credits"] is None:base_complete=False
  else:base_known+=x["sol_max_same_token_credits"]
  comps.append(x)
 for m in a.message or []:
  r=card.get("rates",{}).get(norm(m["model"]));v=None if not r or r.get("rough_local_message") is None else r["rough_local_message"]*m["count"]
  comps.append({**m,"credit_source":"rough_message_average","derived_credits":v});actual_complete=False;base_complete=False
 actual=a.measured_credits if a.measured_credits is not None else (actual_known if a.usage and actual_complete else None)
 actual_source="measured" if a.measured_credits is not None else ("derived_from_token_rate_card" if actual is not None else "partial_or_unknown")
 baseline=base_known if a.usage and base_complete else None
 savings=None if actual is None or baseline is None else baseline-actual;savings_pct=None if savings is None or not baseline else 100*savings/baseline
 src={x.get("token_source") for x in comps if x.get("token_source")};token_source="measured" if src=={"measured"} else ("estimated" if src=={"estimated"} else ("mixed" if src else "unknown"))
 e={"schema":SCHEMA,"timestamp":a.timestamp or now(),"event":"turn_usage","turn_id":a.turn_id,"run_id":a.run_id,"project":a.project,"front_door_model":a.front_door_model,"front_door_effort":a.front_door_effort,
 "components":comps,"token_total":tok if a.usage else None,"token_source":token_source,"credit_total":actual,"credit_source":actual_source,"baseline":{"model":a.baseline_model,"effort":"max","token_multiplier":a.baseline_token_multiplier,"method":"same-token-mix rate counterfactual"},"baseline_credits":baseline,"estimated_credit_savings":savings,"estimated_savings_pct":savings_pct,"rate_card_as_of":card.get("as_of"),"notes":a.notes}
 e={k:v for k,v in e.items() if v is not None};append(e);print(json.dumps(e,indent=2,sort_keys=True))
def filtered(a):
 xs=[e for e in events() if e.get("event")=="turn_usage"]
 if getattr(a,"project",None):xs=[e for e in xs if e.get("project")==a.project]
 if getattr(a,"days",None):
  cut=dt.datetime.now(dt.timezone.utc)-dt.timedelta(days=a.days)
  xs=[e for e in xs if dt.datetime.fromisoformat(e["timestamp"].replace("Z","+00:00"))>=cut]
 return xs
def summarize(xs):
 agents=defaultdict(lambda:{"turns":set(),"input":0,"cached":0,"output":0,"credits":0.,"credits_complete":True,"baseline":0.,"baseline_complete":True})
 for e in xs:
  for x in e.get("components",[]):
   if "input_tokens" not in x:continue
   k=f'{x.get("agent_id","unknown")}:{x.get("role","worker")}:{x.get("model","unknown")}/{x.get("effort","unknown")}' ;d=agents[k];d["turns"].add(e.get("turn_id"));d["input"]+=x["input_tokens"];d["cached"]+=x["cached_input_tokens"];d["output"]+=x["output_tokens"]
   if x.get("derived_credits") is None:d["credits_complete"]=False
   else:d["credits"]+=x["derived_credits"]
   if x.get("sol_max_same_token_credits") is None:d["baseline_complete"]=False
   else:d["baseline"]+=x["sol_max_same_token_credits"]
 rows=[]
 for k,d in sorted(agents.items()):
  rows.append({"subagent_route":k,"turns":len(d["turns"]),"input_tokens":d["input"],"cached_input_tokens":d["cached"],"output_tokens":d["output"],"total_tokens":d["input"]+d["cached"]+d["output"],"credits":round(d["credits"],3) if d["credits_complete"] else None,"sol_max_same_token_credits":round(d["baseline"],3) if d["baseline_complete"] else None})
 ac=[e["credit_total"] for e in xs if e.get("credit_total") is not None];bc=[e["baseline_credits"] for e in xs if e.get("baseline_credits") is not None];all_complete=len(ac)==len(xs) and len(bc)==len(xs);actual=sum(ac) if all_complete else None;base=sum(bc) if all_complete else None
 return {"turns":len(xs),"actual_credits":round(actual,3) if actual is not None else None,"sol_max_same_token_credits":round(base,3) if base is not None else None,"estimated_credit_savings":round(base-actual,3) if actual is not None and base is not None else None,"estimated_savings_pct":round(100*(base-actual)/base,2) if actual is not None and base else None,"by_subagent_model_effort":rows}
def report(a):print(json.dumps(summarize(filtered(a)),indent=2,sort_keys=True))
def footer(a):
 xs=filtered(a);xs=[e for e in xs if not a.turn_id or e.get("turn_id")==a.turn_id]
 if not xs:raise SystemExit("No matching turn usage")
 s=summarize([xs[-1]]);actual=s["actual_credits"];base=s["sol_max_same_token_credits"];save=s["estimated_credit_savings"];pct=s["estimated_savings_pct"]
 actual_txt="unknown" if actual is None else f"{actual:.2f}";base_txt="unknown" if base is None else f"~{base:.2f}";save_txt="unknown" if save is None else f"~{save:.2f} ({pct:.1f}%)"
 routes=", ".join(f'{r["subagent_route"]} {r["total_tokens"]:,}t/{r["credits"] if r["credits"] is not None else "?"}cr' for r in s["by_subagent_model_effort"])
 print(f"Agent Dispatch usage — actual {actual_txt} cr; Sol/max same-token baseline {base_txt} cr; estimated savings {save_txt}. {routes}")
def show_rates(_):print(json.dumps(rates(),indent=2,sort_keys=True))
def parser():
 p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest="cmd",required=True);r=s.add_parser("record-turn");r.add_argument("--turn-id",required=True);r.add_argument("--run-id");r.add_argument("--project");r.add_argument("--front-door-model");r.add_argument("--front-door-effort");r.add_argument("--usage",action="append",type=parse_usage);r.add_argument("--message",action="append",type=parse_message);r.add_argument("--measured-credits",type=float);r.add_argument("--baseline-model",default="gpt-5.6-sol");r.add_argument("--baseline-token-multiplier",type=float,default=1.0);r.add_argument("--timestamp");r.add_argument("--notes");r.set_defaults(func=record)
 f=s.add_parser("footer");f.add_argument("--turn-id");f.add_argument("--project");f.add_argument("--days",type=int);f.set_defaults(func=footer)
 q=s.add_parser("report");q.add_argument("--project");q.add_argument("--days",type=int);q.set_defaults(func=report);s.add_parser("show-rates").set_defaults(func=show_rates);return p
if __name__=="__main__":a=parser().parse_args();a.func(a)
