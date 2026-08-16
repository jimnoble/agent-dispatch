import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "benchmarks" / "model_characterization"
SPEC = importlib.util.spec_from_file_location("model_characterization_score", BENCHMARK / "score.py")
SCORE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(SCORE)


class ModelCharacterizationScoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        suite = json.loads((BENCHMARK / "tasks.json").read_text(encoding="utf-8"))
        cls.tasks = {task["id"]: task for task in suite["tasks"]}

    def response(self, recommendation, *, escalate=False, uncertainties=None):
        return {
            "analysis_summary": "bounded result",
            "recommendation": recommendation,
            "evidence": [],
            "uncertainties": uncertainties or [],
            "should_escalate": escalate,
        }

    def test_exact_structured_answer(self):
        result = SCORE.score_response(
            self.tasks["structured-extraction"],
            self.response('{"alpha":[2,5],"beta":[1]}'),
        )
        self.assertEqual(result["score"], 1.0)
        self.assertTrue(result["passed"])

    def test_generated_chunked_function_is_executed(self):
        source = "def chunked(seq, size):\n    if size <= 0: raise ValueError()\n    return [seq[i:i+size] for i in range(0, len(seq), size)]"
        result = SCORE.score_response(self.tasks["code-synthesis"], self.response(source))
        self.assertEqual(result["score"], 1.0)
        self.assertTrue(result["passed"])

    def test_generated_coalesce_function_is_executed(self):
        hard_suite = json.loads((BENCHMARK / "tasks-hard.json").read_text(encoding="utf-8"))
        task = next(item for item in hard_suite["tasks"] if item["id"] == "hard-interval-coalescing")
        source = """def coalesce(intervals):
    result = []
    cleaned = []
    for item in intervals:
        if len(item) != 2 or any(isinstance(x, bool) or not isinstance(x, int) for x in item) or item[0] >= item[1]:
            raise ValueError()
        cleaned.append(tuple(item))
    for start, end in sorted(cleaned):
        if result and start <= result[-1][1]:
            result[-1] = (result[-1][0], max(result[-1][1], end))
        else:
            result.append((start, end))
    return result"""
        result = SCORE.score_response(task, self.response(source))
        self.assertEqual(result["score"], 1.0)
        self.assertTrue(result["passed"])

    def test_ambiguity_synonyms_receive_full_credit(self):
        result = SCORE.score_response(
            self.tasks["ambiguity-calibration"],
            self.response(
                "Escalate without inventing a period.",
                escalate=True,
                uncertainties=["jurisdiction", "record/data class", "contractual requirements"],
            ),
        )
        self.assertEqual(result["score"], 1.0)
        self.assertTrue(result["passed"])

    def test_invented_retention_period_does_not_pass(self):
        result = SCORE.score_response(
            self.tasks["ambiguity-calibration"],
            self.response(
                "Retain for 7 years.",
                escalate=False,
                uncertainties=["jurisdiction", "record class", "contract"],
            ),
        )
        self.assertFalse(result["passed"])


if __name__ == "__main__":
    unittest.main()
