import json,pathlib,tempfile,unittest,importlib.util
P=pathlib.Path(__file__).parents[1]/"monitor.py"
S=importlib.util.spec_from_file_location("monitor",P);m=importlib.util.module_from_spec(S);S.loader.exec_module(m)

class T(unittest.TestCase):
    def payload(self,score=80):
        return {"generated_at":"2026-09-16T00:00:00+00:00","coverage":{"success_rate":1},
                "opportunities":[{"topic":"photo manager","opportunity_score":score}],
                "alerts":[{"topic":"photo manager","opportunity_score":score,"reasons":["score>=70"],"examples":[]}]}
    def test_safe_name(self):
        self.assertEqual(m.safe_name("a/b c"),"a-b-c")
    def test_snapshot_and_latest(self):
        with tempfile.TemporaryDirectory() as d:
            p=m.snapshot_path(d,"ideas");p.write_text("{}")
            self.assertEqual(m.latest_snapshot(d,"ideas"),p)
    def test_index_retention(self):
        with tempfile.TemporaryDirectory() as d:
            for n in ("20260101T000000Z.json","20260102T000000Z.json","20260103T000000Z.json"):
                p=pathlib.Path(d)/"ideas"/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_text("{}")
                m.update_index(d,"ideas",p,self.payload(),2)
            xs=m.snapshots(d,"ideas")
            self.assertEqual(len(xs),2)
            idx=json.loads((pathlib.Path(d)/"ideas/index.json").read_text())
            self.assertEqual(len(idx["runs"]),2)
    def test_alert_jsonl(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)/"alerts.jsonl"
            self.assertEqual(m.append_alerts(p,self.payload(),"ideas"),1)
            row=json.loads(p.read_text().splitlines()[0]);self.assertEqual(row["search"],"ideas")
    def test_command_uses_previous(self):
        c=m.build_command("ideas","out.json","prev.json","saved.json",False)
        self.assertIn("--previous",c);self.assertIn("--run-saved",c)

if __name__=="__main__":unittest.main()
