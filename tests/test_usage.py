import json,os,subprocess,tempfile,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parents[1];USAGE=HERE/"scripts"/"usage.py"
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
if __name__=="__main__":unittest.main()
