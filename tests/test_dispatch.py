import json, os, subprocess, tempfile, unittest
from pathlib import Path
HERE=Path(__file__).resolve().parents[1]
DISPATCH=HERE/"scripts"/"dispatch.py"
BOOTSTRAP=HERE/"scripts"/"bootstrap_agents.py"
USAGE=HERE/"scripts"/"usage.py"

class DispatchTests(unittest.TestCase):
    def run_cmd(self,*args,env=None):
        return subprocess.run(["python3",str(DISPATCH),*args],check=True,text=True,capture_output=True,env=env)

    def run_usage(self,*args,env=None):
        return subprocess.run(["python3",str(USAGE),*args],check=True,text=True,capture_output=True,env=env)

    def test_global_project_learning_and_policy_packet(self):
        with tempfile.TemporaryDirectory() as td:
            env=os.environ.copy();env["AGENT_DISPATCH_HOME"]=td
            self.run_cmd("init",env=env)
            for project in ("a","b"):
                for i in range(8):
                    self.run_cmd("record","--task-id",f"{project}{i}","--project",project,"--task-class","repository_inventory",
                        "--domain","git","--front-door-model","terra","--worker-model","spark","--worker-reasoning","low",
                        "--tier","alternate_pool","--accepted","true","--tests-pass","true","--review-pass","true",
                        "--rework","false","--parallel","true","--parallel-group-size","4","--parallel-collision","false",
                        "--duration-s","10",env=env)
            rec=json.loads(self.run_cmd("recommend","--task-class","repository_inventory","--domain","git","--project","new",env=env).stdout)
            self.assertTrue(rec["learned_override"])
            self.assertEqual(rec["recommendation"]["model_or_tier"],"spark")
            self.assertIn("execution_policy",rec)
            self.assertGreaterEqual(rec["execution_policy"]["preferred_concurrency"],3)
            self.assertEqual(rec["recursive_delegation"]["max_depth"],2)

    def test_evidence_failure_overrides_parent_acceptance(self):
        with tempfile.TemporaryDirectory() as td:
            env=os.environ.copy();env["AGENT_DISPATCH_HOME"]=td
            for i in range(8):
                self.run_cmd("record","--task-id",str(i),"--task-class","bounded_implementation","--worker-model","terra",
                    "--tier","general","--accepted","true","--tests-pass","false","--rework","false",env=env)
            self.run_cmd("tune",env=env)
            state=json.loads((Path(td)/"routing-state.json").read_text())
            vals=[v for k,v in state["routes"].items() if "bounded_implementation" in k]
            self.assertTrue(vals)
            self.assertTrue(all(v["clean_success_rate"]==0 for v in vals))

    def test_run_level_front_door_reporting(self):
        with tempfile.TemporaryDirectory() as td:
            env=os.environ.copy();env["AGENT_DISPATCH_HOME"]=td
            self.run_cmd("record-run","--run-id","r1","--project","demo","--front-door-model","terra",
                "--front-door-reasoning","medium","--accepted","true","--tests-pass","true","--rework","false",
                "--frontier-calls","1","--duration-s","120",env=env)
            rep=json.loads(self.run_cmd("report","--project","demo",env=env).stdout)
            self.assertEqual(rep["basis"],"run_summary")
            self.assertEqual(rep["front_doors"][0]["runs"],1)
            self.assertEqual(rep["front_doors"][0]["frontier_calls_per_run"],1.0)

    def test_frontier_shadow_guidance_and_depth(self):
        with tempfile.TemporaryDirectory() as td:
            env=os.environ.copy();env["AGENT_DISPATCH_HOME"]=td
            rec=json.loads(self.run_cmd("recommend","--task-class","architecture","--delegation-depth","1",env=env).stdout)
            self.assertEqual(rec["default_tier"],"frontier")
            self.assertEqual(rec["exploration"]["mode"],"shadow")
            self.assertEqual(rec["recursive_delegation"]["remaining_depth"],1)
            self.assertIn("frontier_consultation",rec)

    def test_bootstrap_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            env=os.environ.copy();env["CODEX_HOME"]=td
            subprocess.run(["python3",str(BOOTSTRAP)],check=True,env=env,capture_output=True,text=True)
            subprocess.run(["python3",str(BOOTSTRAP)],check=True,env=env,capture_output=True,text=True)
            text=(Path(td)/"AGENTS.md").read_text()
            self.assertEqual(text.count("<!-- agent-dispatch:start -->"),1)
            self.assertEqual(text.count("<!-- agent-dispatch:end -->"),1)

    def test_bootstrap_bumps_global_instruction_version_once(self):
        with tempfile.TemporaryDirectory() as td:
            env=os.environ.copy();env["CODEX_HOME"]=td
            path=Path(td)/"AGENTS.md"
            path.write_text("# Global AGENTS.md V10\n\nBegin every request's commentary with exactly `COMPLYING WITH GLOBAL AGENTS.MD\nV10`.\n\n<!-- agent-dispatch:start -->\nold\n<!-- agent-dispatch:end -->\n")
            subprocess.run(["python3",str(BOOTSTRAP)],check=True,env=env,capture_output=True,text=True)
            first=path.read_text();self.assertIn("# Global AGENTS.md V11",first);self.assertIn("GLOBAL AGENTS.MD\nV11`",first);self.assertIn("pre-spawn receipt",first)
            subprocess.run(["python3",str(BOOTSTRAP)],check=True,env=env,capture_output=True,text=True)
            second=path.read_text();self.assertEqual(first,second);self.assertNotIn("V12",second)

    def test_managed_lifecycle_unknown_usage_and_summary(self):
        with tempfile.TemporaryDirectory() as td:
            env=os.environ.copy();env["AGENT_DISPATCH_HOME"]=td
            self.run_cmd("begin-run","--run-id","r1","--project","demo","--front-door-model","sol",env=env)
            self.run_cmd("begin-task","--run-id","r1","--task-id","t1","--task-class","code_review","--tier","general","--worker-model","terra",env=env)
            self.run_cmd("bind-task","--run-id","r1","--task-id","t1","--agent-id","a1",env=env)
            terminal=json.loads(self.run_cmd("finish-task","--run-id","r1","--task-id","t1","--actual-worker-model","terra-v2","--actual-worker-reasoning","high","--outcome","pass","--accepted","true",env=env).stdout)
            self.assertEqual(terminal["requested_worker_model"],"terra");self.assertEqual(terminal["worker_model"],"terra-v2");self.assertEqual(terminal["worker_reasoning"],"high")
            self.run_usage("record-turn","--turn-id","turn1","--run-id","r1","--unknown-usage","root,front_door,sol,max,counters_unavailable","--unknown-task-usage","t1,a1,worker,terra,high,counters_unavailable",env=env)
            audit=json.loads(self.run_cmd("audit-run","--run-id","r1","--expected-agent-id","a1","--expected-task-count","1",env=env).stdout)
            self.assertTrue(audit["ok"]);self.assertEqual(audit["unknown_usage_tasks"],1)
            missing_runtime=subprocess.run(["python3",str(DISPATCH),"record-run","--run-id","r1","--delegated-tasks","1"],text=True,capture_output=True,env=env)
            self.assertNotEqual(missing_runtime.returncode,0);self.assertIn("require --expected-agent-id",missing_runtime.stderr)
            summary=json.loads(self.run_cmd("record-run","--run-id","r1","--project","demo","--delegated-tasks","1","--expected-agent-id","a1","--accepted","true","--outcome","pass",env=env).stdout)
            self.assertEqual(summary["telemetry_audit"],"pass")

    def test_audit_and_summary_fail_closed_on_missing_terminal_or_usage(self):
        with tempfile.TemporaryDirectory() as td:
            env=os.environ.copy();env["AGENT_DISPATCH_HOME"]=td
            self.run_cmd("begin-run","--run-id","r1",env=env)
            self.run_cmd("begin-task","--run-id","r1","--task-id","t1","--task-class","code_review","--tier","general",env=env)
            self.run_cmd("bind-task","--run-id","r1","--task-id","t1","--agent-id","a1",env=env)
            audit=subprocess.run(["python3",str(DISPATCH),"audit-run","--run-id","r1"],text=True,capture_output=True,env=env)
            self.assertNotEqual(audit.returncode,0);self.assertIn("terminal events",audit.stdout);self.assertIn("missing turn_usage",audit.stdout)
            summary=subprocess.run(["python3",str(DISPATCH),"record-run","--run-id","r1","--delegated-tasks","1"],text=True,capture_output=True,env=env)
            self.assertNotEqual(summary.returncode,0);self.assertIn("telemetry audit failed",summary.stderr)

    def test_failed_spawn_closes_without_worker_usage(self):
        with tempfile.TemporaryDirectory() as td:
            env=os.environ.copy();env["AGENT_DISPATCH_HOME"]=td
            self.run_cmd("begin-run","--run-id","r1",env=env)
            self.run_cmd("begin-task","--run-id","r1","--task-id","t1","--task-class","code_review","--tier","general",env=env)
            self.run_cmd("finish-task","--run-id","r1","--task-id","t1","--spawned","false","--outcome","fail",env=env)
            self.run_usage("record-turn","--turn-id","turn1","--run-id","r1","--unknown-usage","root,front_door,sol,max",env=env)
            audit=json.loads(self.run_cmd("audit-run","--run-id","r1","--expected-task-count","1",env=env).stdout)
            self.assertTrue(audit["ok"]);self.assertEqual(audit["observed_agent_ids"],[])

    def test_reactivation_reuses_agent_but_requires_distinct_task_receipts(self):
        with tempfile.TemporaryDirectory() as td:
            env=os.environ.copy();env["AGENT_DISPATCH_HOME"]=td
            self.run_cmd("begin-run","--run-id","r1",env=env)
            for task in ("t1","t2"):
                self.run_cmd("begin-task","--run-id","r1","--task-id",task,"--task-class","code_review","--tier","general","--agent-id","a1",env=env)
                self.run_cmd("finish-task","--run-id","r1","--task-id",task,"--outcome","pass",env=env)
            self.run_usage("record-turn","--turn-id","turn1","--run-id","r1","--unknown-usage","root,front_door,sol,max","--unknown-task-usage","t1,a1,worker,terra,high","--unknown-task-usage","t2,a1,worker,terra,high",env=env)
            audit=json.loads(self.run_cmd("audit-run","--run-id","r1","--expected-agent-id","a1","--expected-task-count","2",env=env).stdout)
            self.assertTrue(audit["ok"]);self.assertEqual(audit["task_receipts"],2);self.assertEqual(audit["observed_agent_ids"],["a1"])

    def test_expected_runtime_agent_and_task_count_are_reconciled(self):
        with tempfile.TemporaryDirectory() as td:
            env=os.environ.copy();env["AGENT_DISPATCH_HOME"]=td
            self.run_cmd("begin-run","--run-id","r1",env=env)
            self.run_usage("record-turn","--turn-id","turn1","--run-id","r1","--unknown-usage","root,front_door,sol,max",env=env)
            audit=subprocess.run(["python3",str(DISPATCH),"audit-run","--run-id","r1","--expected-agent-id","missing","--expected-task-count","1"],text=True,capture_output=True,env=env)
            self.assertNotEqual(audit.returncode,0);self.assertIn("expected 1 task receipts; found 0",audit.stdout);self.assertIn("expected runtime agent is missing",audit.stdout)

    def test_rough_message_estimate_does_not_satisfy_front_door_usage(self):
        with tempfile.TemporaryDirectory() as td:
            env=os.environ.copy();env["AGENT_DISPATCH_HOME"]=td
            self.run_cmd("begin-run","--run-id","r1",env=env)
            self.run_usage("record-turn","--turn-id","turn1","--run-id","r1","--message","root,front_door,sol,max",env=env)
            audit=subprocess.run(["python3",str(DISPATCH),"audit-run","--run-id","r1","--expected-task-count","0"],text=True,capture_output=True,env=env)
            self.assertNotEqual(audit.returncode,0);self.assertIn("missing measured, estimated, or unknown front-door usage",audit.stdout)

    def test_lifecycle_task_cannot_be_recorded_or_finished_twice(self):
        with tempfile.TemporaryDirectory() as td:
            env=os.environ.copy();env["AGENT_DISPATCH_HOME"]=td
            self.run_cmd("begin-run","--run-id","r1",env=env)
            self.run_cmd("begin-task","--run-id","r1","--task-id","t1","--task-class","code_review","--tier","general","--agent-id","a1",env=env)
            direct=subprocess.run(["python3",str(DISPATCH),"record","--run-id","r1","--task-id","t1","--task-class","code_review","--tier","general"],text=True,capture_output=True,env=env)
            self.assertNotEqual(direct.returncode,0);self.assertIn("finish-task",direct.stderr)
            self.run_cmd("finish-task","--run-id","r1","--task-id","t1","--outcome","pass",env=env)
            duplicate=subprocess.run(["python3",str(DISPATCH),"finish-task","--run-id","r1","--task-id","t1","--outcome","pass"],text=True,capture_output=True,env=env)
            self.assertNotEqual(duplicate.returncode,0);self.assertIn("already finished",duplicate.stderr)

if __name__=="__main__":unittest.main()
