import json, os, subprocess, tempfile, unittest
from pathlib import Path
HERE=Path(__file__).resolve().parents[1]; RES=HERE/"scripts"/"resources.py"

class ResourceTests(unittest.TestCase):
    def cli(self,*args,env=None):
        return subprocess.run(["python3",str(RES),*args],check=True,text=True,capture_output=True,env=env)

    def test_stale_scratch_is_reconciled(self):
        with tempfile.TemporaryDirectory() as td:
            env=os.environ.copy();env["AGENT_DISPATCH_HOME"]=td
            x=json.loads(self.cli("register","--type","scratch","--repo-id","demo","--run-id","r1","--name","tmp","--lease-minutes","0",env=env).stdout)
            p=Path(x["path"]);p.mkdir(parents=True);(p/"junk.bin").write_bytes(b"x")
            out=json.loads(self.cli("reconcile",env=env).stdout)
            self.assertFalse(p.exists());self.assertEqual(out["reconciled"][0]["result"],"removed")

    def test_dirty_worktree_like_resource_is_quarantined(self):
        with tempfile.TemporaryDirectory() as td:
            env=os.environ.copy();env["AGENT_DISPATCH_HOME"]=td
            root=Path(td)/"workspaces"/"demo"/"r1"/"wt";root.mkdir(parents=True)
            subprocess.run(["git","init",str(root)],check=True,capture_output=True,text=True)
            (root/"uncommitted.txt").write_text("valuable")
            x=json.loads(self.cli("register","--type","git_worktree","--repo-id","demo","--run-id","r1","--path",str(root),"--git-repo",str(root),"--lease-minutes","0",env=env).stdout)
            out=json.loads(self.cli("reconcile",env=env).stdout)
            self.assertTrue(root.exists());self.assertIn("quarantine",out["reconciled"][0]["result"])
            reg=json.loads((Path(td)/"resources.json").read_text());r=next(r for r in reg["resources"] if r["id"]==x["id"]);self.assertEqual(r["status"],"quarantined")

    def test_refuses_resource_outside_managed_root(self):
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as outside:
            env=os.environ.copy();env["AGENT_DISPATCH_HOME"]=td
            cp=subprocess.run(["python3",str(RES),"register","--type","scratch","--repo-id","demo","--run-id","r1","--path",outside],text=True,capture_output=True,env=env)
            self.assertNotEqual(cp.returncode,0);self.assertIn("Refusing unmanaged path",cp.stderr+cp.stdout)

if __name__=="__main__":unittest.main()
