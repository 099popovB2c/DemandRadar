import json
import tempfile
import unittest
from pathlib import Path

import monitor


class MonitorTests(unittest.TestCase):
    def payload(self, score=80):
        return {
            "generated_at": "2026-09-16T00:00:00+00:00",
            "coverage": {"success_rate": 1},
            "opportunities": [{"topic": "photo manager", "opportunity_score": score}],
            "alerts": [
                {
                    "topic": "photo manager",
                    "opportunity_score": score,
                    "reasons": ["score>=70"],
                    "examples": [],
                }
            ],
        }

    def test_safe_name(self):
        self.assertEqual(monitor.safe_name("a/b c"), "a-b-c")
        self.assertEqual(monitor.safe_name(".."), "search")

    def test_snapshot_and_latest(self):
        with tempfile.TemporaryDirectory() as directory:
            path = monitor.snapshot_path(directory, "ideas")
            path.write_text("{}", encoding="utf-8")
            self.assertEqual(monitor.latest_snapshot(directory, "ideas"), path)

    def test_index_retention(self):
        with tempfile.TemporaryDirectory() as directory:
            for name in (
                "20260101T000000Z.json",
                "20260102T000000Z.json",
                "20260103T000000Z.json",
            ):
                path = Path(directory) / "ideas" / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("{}", encoding="utf-8")
                monitor.update_index(directory, "ideas", path, self.payload(), 2)
            self.assertEqual(len(monitor.snapshots(directory, "ideas")), 2)
            index = json.loads((Path(directory) / "ideas" / "index.json").read_text())
            self.assertEqual(len(index["runs"]), 2)

    def test_alert_jsonl(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "alerts.jsonl"
            self.assertEqual(monitor.append_alerts(path, self.payload(), "ideas"), 1)
            row = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(row["search"], "ideas")

    def test_command_uses_previous_snapshot(self):
        command = monitor.build_command("ideas", "out.json", "prev.json", "saved.json", False)
        self.assertIn("--previous", command)
        self.assertIn("--run-saved", command)


if __name__ == "__main__":
    unittest.main()
