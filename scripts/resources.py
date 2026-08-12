#!/usr/bin/env python3
"""Crash-recoverable registry for Agent Dispatch managed temporary resources.

Register resources before creation. End-of-turn cleanup is best effort; every later
activation reconciles stale managed resources before new orchestration work.
Only resources explicitly registered by Agent Dispatch are inspected.
"""
from __future__ import annotations
import argparse, datetime as dt, json, os, shutil, subprocess, uuid
from pathlib import Path

SCHEMA=1
DEFAULT_LEASE_MINUTES=120

def now(): return dt.datetime.now(dt.timezone.utc)
def iso(x=None): return (x or now()).isoformat()
def home():
    if os.environ.get("AGENT_DISPATCH_HOME"): return Path(os.environ["AGENT_DISPATCH_HOME"]).expanduser()
    return Path(os.environ.get("CODEX_HOME", Path.home()/".codex")).expanduser()/"agent-dispatch"
def reg_path(): return home()/"resources.json"
def managed_root(): return home()/"workspaces"
def load():
    p=reg_path()
    if not p.exists(): return {"schema":SCHEMA,"resources":[]}
    try: return json.loads(p.read_text())
    except json.JSONDecodeError as e: raise SystemExit(f"Invalid resource registry {p}: {e}")
def save(d):
    p=reg_path();p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,indent=2,sort_keys=True)+"\n")
def parse_time(s):
    try:return dt.datetime.fromisoformat(str(s).replace("Z","+00:00"))
    except:return dt.datetime.min.replace(tzinfo=dt.timezone.utc)
def stale(r):
    return parse_time(r.get("lease_expires_at")) < now() and r.get("status") in {"registered","active","cleanup_pending"}
def path_allowed(p:Path):
    try:p.resolve().relative_to(managed_root().resolve());return True
    except ValueError:return False

def register(a):
    root=managed_root()/a.repo_id/a.run_id
    path=Path(a.path).expanduser().resolve() if a.path else (root/(a.name or str(uuid.uuid4()))).resolve()
    if not path_allowed(path): raise SystemExit(f"Refusing unmanaged path {path}; Agent Dispatch temporary resources must live under {managed_root()}")
    d=load();rid=a.resource_id or str(uuid.uuid4());expiry=now()+dt.timedelta(minutes=a.lease_minutes)
    r={"id":rid,"type":a.type,"repo_id":a.repo_id,"run_id":a.run_id,"path":str(path),"status":"registered","created_at":iso(),"lease_expires_at":iso(expiry),"disposition":a.disposition,"git_repo":a.git_repo,"notes":a.notes}
    d["resources"].append({k:v for k,v in r.items() if v is not None});save(d);print(json.dumps(r,indent=2));
def mark(a,status):
    d=load();found=False
    for r in d["resources"]:
        if r.get("id")==a.resource_id:
            found=True;r["status"]=status;r["updated_at"]=iso()
            if getattr(a,"lease_minutes",None):r["lease_expires_at"]=iso(now()+dt.timedelta(minutes=a.lease_minutes))
    if not found:raise SystemExit("resource not found")
    save(d)
def activate(a): mark(a,"active")
def heartbeat(a): mark(a,"active")
def complete(a): mark(a,"cleanup_pending")

def git_dirty(path:Path):
    try:
        cp=subprocess.run(["git","-C",str(path),"status","--porcelain"],text=True,capture_output=True,timeout=15)
        return cp.returncode==0 and bool(cp.stdout.strip())
    except:return None

def safe_cleanup(r):
    p=Path(r["path"])
    if not path_allowed(p):return "quarantine: path escaped managed root"
    if not p.exists():return "gone"
    typ=r.get("type")
    if typ=="git_worktree":
        dirty=git_dirty(p)
        if dirty is True:return "quarantine: uncommitted changes"
        repo=r.get("git_repo")
        if not repo:return "quarantine: missing git_repo"
        try:
            cp=subprocess.run(["git","-C",repo,"worktree","remove",str(p)],text=True,capture_output=True,timeout=30)
            if cp.returncode!=0:return "quarantine: git worktree remove failed"
            subprocess.run(["git","-C",repo,"worktree","prune"],text=True,capture_output=True,timeout=15)
            return "removed"
        except:return "quarantine: git cleanup exception"
    # scratch/cache resources are removable only inside managed root.
    try:shutil.rmtree(p);return "removed"
    except Exception:return "quarantine: filesystem cleanup failed"

def reconcile(a):
    d=load();out=[]
    for r in d["resources"]:
        if not stale(r):continue
        result=safe_cleanup(r)
        r["reconciled_at"]=iso();r["reconcile_result"]=result
        if result in {"removed","gone"}:r["status"]="cleaned"
        else:r["status"]="quarantined"
        out.append({"id":r.get("id"),"path":r.get("path"),"result":result})
    save(d);print(json.dumps({"checked":len(d["resources"]),"reconciled":out},indent=2))
def list_cmd(_):print(json.dumps(load(),indent=2,sort_keys=True))

def parser():
    p=argparse.ArgumentParser();s=p.add_subparsers(dest="cmd",required=True)
    r=s.add_parser("register");r.add_argument("--resource-id");r.add_argument("--type",required=True,choices=["scratch","cache","workspace","git_worktree"]);r.add_argument("--repo-id",required=True);r.add_argument("--run-id",required=True);r.add_argument("--name");r.add_argument("--path");r.add_argument("--lease-minutes",type=int,default=DEFAULT_LEASE_MINUTES);r.add_argument("--disposition",default="delete_after_use");r.add_argument("--git-repo");r.add_argument("--notes");r.set_defaults(func=register)
    for name,fn in (("activate",activate),("heartbeat",heartbeat),("complete",complete)):
        q=s.add_parser(name);q.add_argument("--resource-id",required=True);q.add_argument("--lease-minutes",type=int,default=DEFAULT_LEASE_MINUTES);q.set_defaults(func=fn)
    s.add_parser("reconcile").set_defaults(func=reconcile);s.add_parser("list").set_defaults(func=list_cmd);return p
if __name__=="__main__":a=parser().parse_args();a.func(a)
