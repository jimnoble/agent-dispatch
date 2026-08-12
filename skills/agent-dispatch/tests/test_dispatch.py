import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
DISPATCH = HERE / "scripts" / "dispatch.py"
BOOTSTRAP = HERE / "scripts" / "bootstrap_agents.py"


class DispatchTests(unittest.TestCase):
    def run_cmd(self, *args, env=None):
        return subprocess.run(["python3", str(DISPATCH), *args], check=True, text=True, capture_output=True, env=env)

    def test_init_record_tune_recommend_report(self):
        with tempfile.TemporaryDirectory() as td:
            env = os.environ.copy()
            env["AGENT_DISPATCH_HOME"] = td
            self.run_cmd("init", env=env)
            for i in range(8):
                self.run_cmd(
                    "record", "--task-id", f"t{i}", "--project", "demo", "--task-class", "repository_inventory",
                    "--domain", "git", "--front-door-model", "terra", "--worker-model", "spark", "--tier", "alternate_pool",
                    "--accepted", "true", "--rework", "false", "--duration-s", "10", env=env,
                )
            self.run_cmd("tune", env=env)
            rec = json.loads(self.run_cmd("recommend", "--task-class", "repository_inventory", "--domain", "git", "--project", "demo", env=env).stdout)
            self.assertTrue(rec["learned_override"])
            self.assertEqual(rec["recommendation"]["model_or_tier"], "spark")
            rep = json.loads(self.run_cmd("report", "--project", "demo", env=env).stdout)
            self.assertEqual(rep["events"], 8)

    def test_bootstrap_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            env = os.environ.copy()
            env["CODEX_HOME"] = td
            subprocess.run(["python3", str(BOOTSTRAP)], check=True, env=env, capture_output=True, text=True)
            subprocess.run(["python3", str(BOOTSTRAP)], check=True, env=env, capture_output=True, text=True)
            text = (Path(td) / "AGENTS.md").read_text()
            self.assertEqual(text.count("<!-- agent-dispatch:start -->"), 1)
            self.assertEqual(text.count("<!-- agent-dispatch:end -->"), 1)


if __name__ == "__main__":
    unittest.main()
