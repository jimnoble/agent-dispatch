#!/usr/bin/env python3
"""Turn-level token/credit ledger and reporting for Agent Dispatch.

Credit derivation uses a local, editable Codex rate card. Token counts are never
invented: pass measured counts when the runtime exposes them, estimated counts
only when you have a defensible estimate, or use the explicitly rough
message-average fallback.
"""
from __future__ import annotations
import argparse, datetime as dt, json, os
from collections import defaultdict
from pathlib import Path

SCHEMA=1
RATE_CARD_AS_OF="2026-08-12"
RATE_CARD_SOURCE="https://help.openai.com/en/articles/20001106-codex-rate-card"
# Credits per 1M tokens. rough_local_message is a planning fallback only.
DEFAULT_RATES={
 "gpt-5.6-sol":{"input":125.0,"cached_input":12.5,"output":750.0,"rough_local_message":14.0},
 "sol":{"input":125.0,"cached_input":12.5,"output":750.0,"rough_local_message":14.0},
 "gpt-5.6-terra":{"input":62.5,"cached_input":6.25,"output":375.0,"rough_local_message":7.0},
 "terra":{"input":62.5,"cached_input":6.25,"output":375.0,"rough_local_message":7.0},
 "gpt-5.6-luna":{"input":25.0,"cached_input":2.5,"output":150.0,"rough_local_message":3.0},
 "luna":{"input":25.0,"cached_input":2.5,"output":150.0,"rough_local_message":3.0},
 "gpt-5.5":{"input":125.0,"cached_input":12.5,"output":750.0,"rough_local_message":14.0},
 "gpt-5.4":{"input":62.5,"cached_input":6.25,"output":375.0,"rough_local_message":7.0},
 "gpt-5.4-mini":{"input":18.75,"cached_input":1.875,"output":113.0},
 "gpt-5.3-codex":{"input":43.75,"cached_input":4.375,"output":350.0},
 "gpt-5.2":{"input":43.75,"cached_input":4.375,"output":350.0},
 # GPT-5.3-Codex-Spark is research preview; no public numeric rate as of RATE_CARD_AS_OF.
}

def now_iso():return dt.datetime.now(dt.timezone.utc).isoformat()
def home():
 if os.environ.get("AGENT_DISPATCH_HOME"):return Path(os.environ["AGENT_DISPATCH_HOME"]).expanduser()
 return Path(os.environ.get("CODEX_HOME",Path.home()/".codex")).expanduser()/"agent-dispatch"
def telemetry_path():return home()/"telemetry.jsonl"
def rate_path():return home()/"rate-card.json"
def init_rates():
 p=rate_path();p.parent.mkdir(parents=True,exist_ok=True)
 if not p.exists():p.write_text(json.dumps({"schema":SCHEMA,"as_of":RATE_CARD_AS_OF,"source":RATE_CARD_SOURCE,"rates":DEFAULT_RATES},indent=2,sort_keys=True)+"\n")
def rates():
 init_rates()
 try:return json.loads(rate_path().read_text())
 except json.JSONDecodeError as e:raise SystemExit(f"Invalid rate card {rate_path()}: {e}")
def load_events():
 p=telemetry_path()
 if not p.exists():return []
 out=[]
 for line in p.read_text().splitlines():
  try:out.append(json.loads(line))
  except json.JSONDecodeError:pass
 return out
def append(e):
 p=telemetry_path();p.parent.mkdir(parents=True,exist_ok=True)
 with p.open("a") as f:f.write(json.dumps(e,sort_keys=True)+"\n")
def norm_model(m):return (m or "").strip().lower()
def credit_for(model,inp,cached,out,card):
 r=card.get("rates",{}).get(norm_model(model))
 if not r:return None
 return (inp*r["input"]+cached*r["cached_input"]+out*r["output"])/1_000_000
def parse_usage(s):
 # model,input,cached_input,output,source ; source=measured|estimated
 p=[x.strip() for x in s.split(",")]
 if len(p)!=5:raise argparse.ArgumentTypeError("usage must be model,input,cached_input,output,measured|estimated")
 if p[4] not in {"measured","estimated"}:raise argparse.ArgumentTypeError("usage source must be measured or estimated")
 try:i,c,o=map(int,p[1:4])
 except ValueError:raise argparse.ArgumentTypeError("token counts must be integers")
 if min(i,c,o)<0:raise argparse.ArgumentTypeError("token counts must be nonnegative")
 return {"model":p[0],"input_tokens":i,"cached_input_tokens":c,"output_tokens":o,"token_source":p[4]}
def parse_message(s):
 p=[x.strip() for x in s.split(",")]
 if len(p) not in {1,2}:raise argparse.ArgumentTypeError("message must be model or model,count")
 try:n=int(p[1]) if len(p)==2 else 1
 except ValueError:raise argparse.ArgumentTypeError("message count must be an integer")
 if n<1:raise argparse.ArgumentTypeError("message count must be positive")
 return {"model":p[0],"count":n}
def record(a):
 card=rates();components=[];token_total=0;credits_known=0.0;credits_complete=True
 for u in a.usage or []:
  x=dict(u);cr=credit_for(x["model"],x["input_tokens"],x["cached_input_tokens"],x["output_tokens"],card);x["derived_credits"]=cr
  token_total+=x["input_tokens"]+x["cached_input_tokens"]+x["output_tokens"]
  if cr is None:credits_complete=False
  else:credits_known+=cr
  components.append(x)
 rough=0.0;rough_complete=True
 for m in a.message or []:
  r=card.get("rates",{}).get(norm_model(m["model"]));avg=r.get("rough_local_message") if r else None
  c=None if avg is None else avg*m["count"]
  if c is None:rough_complete=False
  else:rough+=c
  components.append({"model":m["model"],"message_count":m["count"],"credit_source":"rough_legacy_message_average","derived_credits":c})
 if a.measured_credits is not None:credit_total=a.measured_credits;credit_source="measured"
 elif (a.usage and credits_complete):credit_total=credits_known;credit_source="derived_from_token_rate_card"
 elif (not a.usage and a.message and rough_complete):credit_total=rough;credit_source="rough_message_average"
 else:credit_total=None;credit_source="partial_or_unknown"
 sources={x.get("token_source") for x in components if x.get("token_source")}
 token_source="measured" if sources=={"measured"} else ("estimated" if sources=={"estimated"} else ("mixed" if sources else "unknown"))
 e={"schema":SCHEMA,"timestamp":a.timestamp or now_iso(),"event":"turn_usage","turn_id":a.turn_id,"run_id":a.run_id,"project":a.project,
    "front_door_model":a.front_door_model,"front_door_effort":a.front_door_effort,"components":components,"token_total":token_total if a.usage else None,
    "token_source":token_source,"credit_total":credit_total,"credit_source":credit_source,"rate_card_as_of":card.get("as_of"),"notes":a.notes}
 e={k:v for k,v in e.items() if v is not None};append(e);print(json.dumps(e,indent=2,sort_keys=True))
def latest_turn(turn_id=None):
 xs=[e for e in load_events() if e.get("event")=="turn_usage" and (not turn_id or e.get("turn_id")==turn_id)]
 return xs[-1] if xs else None
def fmt_num(n):
 if n is None:return "unknown"
 if n>=1_000_000:return f"{n/1_000_000:.2f}M"
 if n>=1000:return f"{n/1000:.1f}k"
 return str(int(n))
def footer(a):
 e=latest_turn(a.turn_id)
 if not e:raise SystemExit("No matching turn usage event")
 cr=e.get("credit_total");cs=e.get("credit_source","unknown");tok=e.get("token_total");ts=e.get("token_source","unknown")
 ctext="unknown credits" if cr is None else f"{cr:.2f} credits"
 if cs!="measured" and cr is not None:ctext="~"+ctext
 ttext=f"{fmt_num(tok)} tokens ({ts})" if tok is not None else "tokens unknown"
 print(f"Agent Dispatch usage — {ctext} [{cs}]; {ttext}.")
def report(a):
 xs=[e for e in load_events() if e.get("event")=="turn_usage"]
 if a.project:xs=[e for e in xs if e.get("project")==a.project]
 if a.days:
  cut=dt.datetime.now(dt.timezone.utc)-dt.timedelta(days=a.days)
  def recent(e):
   try:return dt.datetime.fromisoformat(str(e.get("timestamp","")).replace("Z","+00:00"))>=cut
   except:return False
  xs=[e for e in xs if recent(e)]
 groups=defaultdict(list)
 for e in xs:
  key=e.get("front_door_model") or "unknown";eff=e.get("front_door_effort")
  if eff:key+=f"/{eff}"
  groups[key].append(e)
 rows=[]
 for k,v in sorted(groups.items()):
  known=[e["credit_total"] for e in v if e.get("credit_total") is not None];tokens=[e["token_total"] for e in v if e.get("token_total") is not None]
  rows.append({"front_door":k,"turns":len(v),"credits_known_sum":round(sum(known),3) if known else None,"turns_with_credit_estimate":len(known),
               "tokens_known_sum":sum(tokens) if tokens else None,"turns_with_tokens":len(tokens),"credit_sources":dict(_counts(e.get("credit_source","unknown") for e in v)),
               "token_sources":dict(_counts(e.get("token_source","unknown") for e in v))})
 allc=[e["credit_total"] for e in xs if e.get("credit_total") is not None];allt=[e["token_total"] for e in xs if e.get("token_total") is not None]
 print(json.dumps({"turns":len(xs),"credits_known_sum":round(sum(allc),3) if allc else None,"tokens_known_sum":sum(allt) if allt else None,"front_doors":rows},indent=2,sort_keys=True))
def _counts(it):
 d=defaultdict(int)
 for x in it:d[x]+=1
 return d.items()
def show_rates(_):print(json.dumps(rates(),indent=2,sort_keys=True))
def parser():
 p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest="cmd",required=True)
 r=s.add_parser("record-turn");r.add_argument("--turn-id",required=True);r.add_argument("--run-id");r.add_argument("--project");r.add_argument("--front-door-model");r.add_argument("--front-door-effort");r.add_argument("--usage",action="append",type=parse_usage,help="model,input,cached_input,output,measured|estimated; repeat per model");r.add_argument("--message",action="append",type=parse_message,help="rough fallback: model[,count]");r.add_argument("--measured-credits",type=float);r.add_argument("--timestamp");r.add_argument("--notes");r.set_defaults(func=record)
 f=s.add_parser("footer");f.add_argument("--turn-id");f.set_defaults(func=footer)
 q=s.add_parser("report");q.add_argument("--project");q.add_argument("--days",type=int);q.set_defaults(func=report)
 s.add_parser("show-rates").set_defaults(func=show_rates)
 return p
if __name__=="__main__":a=parser().parse_args();a.func(a)
