import json,os,subprocess,tempfile,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parents[1];USAGE=HERE/"scripts"/"usage.py"
class UsageTests(unittest.TestCase):
 def cli(self,*a,env=None):return subprocess.run(["python3",str(USAGE),*a],check=True,text=True,capture_output=True,env=env)
 def test_token_rate_credit_derivation_and_footer(self):
  with tempfile.TemporaryDirectory() as td:
   e=os.environ.copy();e["AGENT_DISPATCH_HOME"]=td
   x=json.loads(self.cli("record-turn","--turn-id","t1","--project","demo","--front-door-model","terra","--front-door-effort","medium","--usage","gpt-5.6-sol,100000,50000,10000,measured","--usage","gpt-5.6-luna,200000,0,20000,estimated",env=e).stdout)
   self.assertEqual(x["token_total"],380000);self.assertEqual(x["token_source"],"mixed");self.assertEqual(x["credit_source"],"derived_from_token_rate_card");self.assertGreater(x["credit_total"],0)
   f=self.cli("footer","--turn-id","t1",env=e).stdout.strip();self.assertIn("credits",f);self.assertIn("tokens",f);self.assertTrue(f.startswith("Agent Dispatch usage"))
 def test_rough_message_fallback_is_labeled(self):
  with tempfile.TemporaryDirectory() as td:
   e=os.environ.copy();e["AGENT_DISPATCH_HOME"]=td
   x=json.loads(self.cli("record-turn","--turn-id","t1","--message","terra,2",env=e).stdout)
   self.assertEqual(x["credit_source"],"rough_message_average");self.assertIsNone(x.get("token_total"));self.assertGreater(x["credit_total"],0)
if __name__=="__main__":unittest.main()
