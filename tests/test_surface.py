import json,os,subprocess,tempfile,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parents[1];SURFACE=HERE/"scripts"/"surface.py"
class SurfaceTests(unittest.TestCase):
 def run(self,*a,env=None):return subprocess.run(["python3",str(SURFACE),*a],check=True,text=True,capture_output=True,env=env)
 def test_register_and_suggest_cross_surface(self):
  with tempfile.TemporaryDirectory() as td:
   e=os.environ.copy();e["AGENT_DISPATCH_HOME"]=td
   for m,r,t in (("luna","high","cheap"),("sol","low","frontier"),("terra","medium","general")):self.run("register-cell","--model",m,"--effort",r,"--tier",t,env=e)
   x=json.loads(self.run("suggest","--task-class","bounded_implementation","--current-model","terra","--current-effort","medium",env=e).stdout)
   self.assertIn(x["candidate"]["model"],{"luna","sol"});self.assertIn(x["candidate"]["effort"],{"high","low"})
 def test_promote_project_route(self):
  with tempfile.TemporaryDirectory() as td,tempfile.TemporaryDirectory() as repo:
   e=os.environ.copy();e["AGENT_DISPATCH_HOME"]=td
   state={"routes":{"demo|bounded_implementation|rust|luna|*|high|*":{"samples":16,"clean_success_rate":.95,"rework_rate":.01,"utility":.88},"demo|bounded_implementation|rust|terra|*|medium|*":{"samples":16,"clean_success_rate":.92,"rework_rate":.02,"utility":.80}}}
   Path(td,"routing-state.json").write_text(json.dumps(state));Path(td,"config.json").write_text(json.dumps({"promotion_min_samples":12,"promotion_min_clean_success":.9,"promotion_max_rework":.08,"promotion_min_utility_margin":.03}))
   x=json.loads(self.run("promote","--repo-root",repo,"--project","demo","--task-class","bounded_implementation","--domain","rust",env=e).stdout)
   self.assertTrue(x["promoted"]);d=json.loads(Path(repo,".agent-dispatch","defaults.json").read_text());self.assertEqual(next(iter(d["routes"].values()))["model"],"luna")
if __name__=="__main__":unittest.main()
