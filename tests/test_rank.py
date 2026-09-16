import unittest, importlib.util, pathlib, time
p=pathlib.Path(__file__).parents[1]/'demandradar.py'; s=importlib.util.spec_from_file_location('d',p); d=importlib.util.module_from_spec(s); s.loader.exec_module(d)
class T(unittest.TestCase):
 def test_rank_components(self):
  r=d.rank(d.demo()); self.assertTrue(r); self.assertIn('components',r[0]); self.assertGreaterEqual(r[0]['opportunity_score'],0)
 def test_intent(self): self.assertGreaterEqual(d.intent_score({'title':'I would pay for a tool','text':''}),5)
 def test_dedupe(self):
  x={'title':'x','text':'','url':'https://example.com/a?x=1','source':'reddit','score':0,'comments':0,'created':time.time()}; self.assertEqual(len(d.dedupe([x,x])),1)
if __name__=='__main__': unittest.main()
