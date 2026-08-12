import json, os, subprocess, tempfile, unittest
from pathlib import Path
HERE=Path(__file__).resolve().parents[1]
DISPATCH=HERE/"scripts"/"dispatch.py"
BOOTSTRAP=HERE/"scripts"/"bootstrap_agents.py"

class DispatchTests(unittest.TestCase):
    def run_cmd(self,*args,env=None):
        return subprocess.run(["python3",str(DISPATCH),*args],check=True,text=True,capture_output=True,env=env)

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

if __name__=="__main__":unittest.main()
