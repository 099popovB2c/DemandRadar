import unittest,importlib.util,pathlib,time,tempfile,json
p=pathlib.Path(__file__).parents[1]/"demandradar.py";s=importlib.util.spec_from_file_location("d",p);d=importlib.util.module_from_spec(s);s.loader.exec_module(d)
class T(unittest.TestCase):
 def test_rank(self):r=d.rank(d.demo());self.assertTrue(r);self.assertIn("topic_key",r[0]);self.assertIn("intent_mix",r[0])
 def test_intent(self):self.assertIn("buying",d.intent_tags({"title":"I would pay for a tool","text":""}))
 def test_dedupe(self):
  x={"title":"x","text":"","url":"https://e.com/a?x=1","source":"reddit","score":0,"comments":0,"created":time.time()};self.assertEqual(len(d.dedupe([x,x])),1)
 def test_saved(self):
  with tempfile.TemporaryDirectory() as td:
   p=pathlib.Path(td)/"s.json";d.save_search(p,"x",["abc"],["reddit"],5,.2,1);self.assertIn("x",d.load_json(p,{})["searches"])
 def test_trends(self):
  rows=d.rank(d.demo());prev={"opportunities":[dict(rows[0],opportunity_score=max(0,rows[0]["opportunity_score"]-20))]};d.add_trends(rows,prev);self.assertIn(rows[0]["trend"]["state"],{"rising","stable","falling","new"})
 def test_alert(self):
  rows=d.add_trends(d.rank(d.demo()),None);self.assertTrue(d.alerts(rows,0,0))
if __name__=="__main__":unittest.main()
