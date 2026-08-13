import json,os,subprocess,tempfile,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parents[1];USAGE=HERE/"scripts"/"usage.py";DISPATCH=HERE/"scripts"/"dispatch.py"
class UsageTests(unittest.TestCase):
 def cli(self,*a,env=None):return subprocess.run(["python3",str(USAGE),*a],check=True,text=True,capture_output=True,env=env)
 def test_subagent_breakdown_and_sol_baseline(self):
  with tempfile.TemporaryDirectory() as td:
   e=os.environ.copy();e["AGENT_DISPATCH_HOME"]=td
   x=json.loads(self.cli("record-turn","--turn-id","t1","--project","demo","--front-door-model","terra","--front-door-effort","medium",
    "--usage","fd,front_door,gpt-5.6-terra,medium,100000,50000,10000,measured",
    "--usage","w1,worker,gpt-5.6-luna,high,200000,0,20000,measured",env=e).stdout)
   self.assertEqual(x["token_total"],380000);self.assertEqual(x["token_source"],"measured");self.assertGreater(x["baseline_credits"],x["credit_total"]);self.assertGreater(x["estimated_credit_savings"],0)
   r=json.loads(self.cli("report","--project","demo",env=e).stdout);self.assertEqual(len(r["by_subagent_model_effort"]),2);self.assertGreater(r["estimated_savings_pct"],0)
   f=self.cli("footer","--turn-id","t1",env=e).stdout.strip();self.assertIn("Sol/max",f);self.assertIn("estimated savings",f);self.assertIn("w1:worker",f)
 def test_unknown_rate_stays_unknown(self):
  with tempfile.TemporaryDirectory() as td:
   e=os.environ.copy();e["AGENT_DISPATCH_HOME"]=td
   x=json.loads(self.cli("record-turn","--turn-id","t1","--usage","w1,worker,gpt-5.3-codex-spark,medium,1000,0,1000,measured",env=e).stdout)
   self.assertIsNone(x.get("credit_total"));self.assertEqual(x["credit_source"],"partial_or_unknown")
 def test_task_aware_usage_preserves_task_id(self):
  with tempfile.TemporaryDirectory() as td:
   e=os.environ.copy();e["AGENT_DISPATCH_HOME"]=td
   x=json.loads(self.cli("record-turn","--turn-id","t1","--run-id","r1","--usage","root,front_door,gpt-5.6-sol,max,10,5,2,measured","--task-usage","task1,w1,worker,gpt-5.6-terra,high,100,20,10,estimated",env=e).stdout)
   task=next(c for c in x["components"] if c.get("task_id")=="task1")
   self.assertEqual(task["agent_id"],"w1");self.assertEqual(task["token_source"],"estimated");self.assertEqual(x["token_source"],"mixed")
 def test_unknown_usage_stays_null_and_visible(self):
  with tempfile.TemporaryDirectory() as td:
   e=os.environ.copy();e["AGENT_DISPATCH_HOME"]=td
   x=json.loads(self.cli("record-turn","--turn-id","t1","--run-id","r1","--unknown-usage","root,front_door,gpt-5.6-sol,max,counters_unavailable","--unknown-task-usage","task1,w1,worker,gpt-5.6-terra,high,counters_unavailable",env=e).stdout)
   self.assertNotIn("token_total",x);self.assertEqual(x["token_source"],"unknown");self.assertIsNone(x.get("credit_total"))
   task=next(c for c in x["components"] if c.get("task_id")=="task1")
   self.assertIsNone(task["input_tokens"]);self.assertEqual(task["token_source"],"unknown")
   report=json.loads(self.cli("report","--project","",env=e).stdout)
   worker=next(r for r in report["by_subagent_model_effort"] if r["subagent_route"].startswith("w1:"))
   self.assertIsNone(worker["total_tokens"]);self.assertFalse(worker["token_counts_complete"])
   footer=self.cli("footer","--turn-id","t1",env=e).stdout;self.assertIn("w1:worker",footer);self.assertIn("?t/?cr",footer)
 def test_capture_task_usage_from_child_rollout(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);state=root/"state";sessions=root/"sessions";day=sessions/"2026"/"08"/"13";day.mkdir(parents=True)
   e=os.environ.copy();e["AGENT_DISPATCH_HOME"]=str(state)
   lifecycle=[
    {"event":"run_started","run_id":"r1","timestamp":"2026-08-13T12:00:00Z"},
    {"event":"delegated_task_started","run_id":"r1","task_id":"t1","timestamp":"2026-08-13T12:00:00Z"},
    {"event":"delegated_task_bound","run_id":"r1","task_id":"t1","agent_id":"/root/reviewer","timestamp":"2026-08-13T12:00:10Z"},
    {"event":"delegated_task","run_id":"r1","task_id":"t1","agent_id":"/root/reviewer","spawned":True,"worker_model":"gpt-5.6-terra","worker_reasoning":"medium","timestamp":"2026-08-13T12:02:00Z"},
   ]
   state.mkdir();(state/"telemetry.jsonl").write_text("".join(json.dumps(x)+"\n" for x in lifecycle))
   rollout=[
    {"timestamp":"2026-08-13T12:00:10Z","type":"session_meta","payload":{"type":"session_meta","id":"child","agent_path":"/root/reviewer","parent_thread_id":"parent"}},
    {"timestamp":"2026-08-13T12:00:10.100Z","type":"event_msg","payload":{"type":"task_started","turn_id":"inherited"}},
    {"timestamp":"2026-08-13T12:00:10.200Z","type":"event_msg","payload":{"type":"token_count","info":{"last_token_usage":{"input_tokens":999,"cached_input_tokens":900,"output_tokens":99,"total_tokens":1098}}}},
    {"timestamp":"2026-08-13T12:00:10.300Z","type":"event_msg","payload":{"type":"task_complete","turn_id":"inherited"}},
    {"timestamp":"2026-08-13T12:00:11Z","type":"event_msg","payload":{"type":"task_started","turn_id":"actual"}},
    {"timestamp":"2026-08-13T12:00:12Z","type":"turn_context","payload":{"model":"gpt-5.6-terra","effort":"medium"}},
    {"timestamp":"2026-08-13T12:00:13Z","type":"event_msg","payload":{"type":"token_count","info":{"last_token_usage":{"input_tokens":100,"cached_input_tokens":80,"output_tokens":10,"total_tokens":110}}}},
    {"timestamp":"2026-08-13T12:00:14Z","type":"event_msg","payload":{"type":"token_count","info":{"last_token_usage":{"input_tokens":50,"cached_input_tokens":0,"output_tokens":5,"total_tokens":55}}}},
    {"timestamp":"2026-08-13T12:01:00Z","type":"event_msg","payload":{"type":"task_complete","turn_id":"actual"}},
   ]
   (day/"rollout-child.jsonl").write_text("".join(json.dumps(x)+"\n" for x in rollout))
   x=json.loads(self.cli("record-turn","--turn-id","turn1","--run-id","r1","--unknown-usage","root,front_door,gpt-5.6-sol,max,counters_unavailable","--capture-task-usage","t1","--sessions-path",str(sessions),"--parent-thread-id","parent",env=e).stdout)
   task=next(c for c in x["components"] if c.get("task_id")=="t1")
   self.assertEqual((task["input_tokens"],task["cached_input_tokens"],task["output_tokens"]),(70,80,15))
   self.assertEqual(task["token_source"],"measured");self.assertEqual(task["request_count"],2)
   self.assertEqual(task["usage_provenance"],"codex_rollout_last_token_usage")
   audit=subprocess.run(["python3",str(DISPATCH),"audit-run","--run-id","r1","--expected-agent-id","/root/reviewer","--expected-task-count","1"],check=True,text=True,capture_output=True,env=e)
   self.assertTrue(json.loads(audit.stdout)["ok"])
 def test_capture_task_usage_fails_closed_on_parent_mismatch(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);state=root/"state";sessions=root/"sessions";day=sessions/"2026"/"08"/"13";day.mkdir(parents=True);state.mkdir()
   e=os.environ.copy();e["AGENT_DISPATCH_HOME"]=str(state)
   rows=[{"event":"delegated_task_started","run_id":"r1","task_id":"t1","timestamp":"2026-08-13T12:00:00Z"},{"event":"delegated_task_bound","run_id":"r1","task_id":"t1","agent_id":"/root/reviewer"},{"event":"delegated_task","run_id":"r1","task_id":"t1","agent_id":"/root/reviewer","timestamp":"2026-08-13T12:02:00Z"}]
   (state/"telemetry.jsonl").write_text("".join(json.dumps(x)+"\n" for x in rows))
   rollout=[{"timestamp":"2026-08-13T12:00:10Z","type":"session_meta","payload":{"agent_path":"/root/reviewer","parent_thread_id":"different"}},{"timestamp":"2026-08-13T12:00:11Z","type":"event_msg","payload":{"type":"task_started","turn_id":"actual"}},{"timestamp":"2026-08-13T12:00:12Z","type":"event_msg","payload":{"type":"token_count","info":{"last_token_usage":{"input_tokens":10,"cached_input_tokens":0,"output_tokens":1,"total_tokens":11}}}},{"timestamp":"2026-08-13T12:01:00Z","type":"event_msg","payload":{"type":"task_complete","turn_id":"actual"}}]
   (day/"rollout-child.jsonl").write_text("".join(json.dumps(x)+"\n" for x in rollout))
   result=subprocess.run(["python3",str(USAGE),"record-turn","--turn-id","turn1","--run-id","r1","--capture-task-usage","t1","--sessions-path",str(sessions),"--parent-thread-id","parent"],text=True,capture_output=True,env=e)
   self.assertNotEqual(result.returncode,0);self.assertIn("found 0",result.stderr)
 def test_capture_task_usage_selects_the_matching_reactivation(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);state=root/"state";sessions=root/"sessions";day=sessions/"2026"/"08"/"13";day.mkdir(parents=True);state.mkdir()
   e=os.environ.copy();e["AGENT_DISPATCH_HOME"]=str(state)
   rows=[]
   for task,start,end in (("t1","12:00:00","12:02:00"),("t2","12:10:00","12:12:00")):
    rows.extend([{"event":"delegated_task_started","run_id":"r1","task_id":task,"agent_id":"/root/reviewer","timestamp":f"2026-08-13T{start}Z"},{"event":"delegated_task","run_id":"r1","task_id":task,"agent_id":"/root/reviewer","worker_model":"gpt-5.6-terra","timestamp":f"2026-08-13T{end}Z"}])
   (state/"telemetry.jsonl").write_text("".join(json.dumps(x)+"\n" for x in rows))
   rollout=[{"timestamp":"2026-08-13T12:00:05Z","type":"session_meta","payload":{"agent_path":"/root/reviewer","parent_thread_id":"parent"}}]
   for turn,start,end,tokens in (("one","12:00:10","12:01:00",10),("two","12:10:10","12:11:00",20)):
    rollout.extend([{"timestamp":f"2026-08-13T{start}Z","type":"event_msg","payload":{"type":"task_started","turn_id":turn}},{"timestamp":f"2026-08-13T{start}.100Z","type":"turn_context","payload":{"model":"gpt-5.6-terra","effort":"high"}},{"timestamp":f"2026-08-13T{start}.200Z","type":"event_msg","payload":{"type":"token_count","info":{"last_token_usage":{"input_tokens":tokens,"cached_input_tokens":0,"output_tokens":1,"total_tokens":tokens+1}}}},{"timestamp":f"2026-08-13T{end}Z","type":"event_msg","payload":{"type":"task_complete","turn_id":turn}}])
   (day/"rollout-child.jsonl").write_text("".join(json.dumps(x)+"\n" for x in rollout))
   first=json.loads(self.cli("record-turn","--turn-id","turn1","--run-id","r1","--capture-task-usage","t1","--sessions-path",str(sessions),"--parent-thread-id","parent",env=e).stdout)
   second=json.loads(self.cli("record-turn","--turn-id","turn2","--run-id","r1","--capture-task-usage","t2","--sessions-path",str(sessions),"--parent-thread-id","parent",env=e).stdout)
   self.assertEqual(first["components"][0]["input_tokens"],10);self.assertEqual(second["components"][0]["input_tokens"],20)
 def test_superseded_unknown_usage_is_excluded_from_report_and_audit(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);e=os.environ.copy();e["AGENT_DISPATCH_HOME"]=str(root)
   lifecycle=[{"event":"run_started","run_id":"r1"},{"event":"delegated_task_started","run_id":"r1","task_id":"t1","agent_id":"a1"},{"event":"delegated_task","run_id":"r1","task_id":"t1","agent_id":"a1","spawned":True}]
   (root/"telemetry.jsonl").write_text("".join(json.dumps(x)+"\n" for x in lifecycle))
   self.cli("record-turn","--turn-id","old","--run-id","r1","--unknown-usage","root,front_door,sol,max","--unknown-task-usage","t1,a1,worker,terra,high",env=e)
   self.cli("record-turn","--turn-id","corrected","--run-id","r1","--supersedes-turn-id","old","--usage","root,front_door,sol,max,10,5,2,measured","--task-usage","t1,a1,worker,terra,high,100,20,10,measured",env=e)
   report=json.loads(self.cli("report",env=e).stdout);self.assertEqual(report["turns"],1)
   worker=next(x for x in report["by_subagent_model_effort"] if x["subagent_route"].startswith("a1:"));self.assertEqual(worker["total_tokens"],130)
   audit=subprocess.run(["python3",str(DISPATCH),"audit-run","--run-id","r1","--expected-agent-id","a1","--expected-task-count","1"],check=True,text=True,capture_output=True,env=e)
   self.assertTrue(json.loads(audit.stdout)["ok"])
if __name__=="__main__":unittest.main()
