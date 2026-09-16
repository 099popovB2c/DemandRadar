import unittest, importlib.util, pathlib
p=pathlib.Path(__file__).parents[1]/'demandradar.py'; s=importlib.util.spec_from_file_location('d',p); d=importlib.util.module_from_spec(s); s.loader.exec_module(d)
class T(unittest.TestCase):
 def test_rank(self):
  x=d.demo(); r=d.rank(x); self.assertTrue(r); self.assertIn('opportunity_score',r[0])
if __name__=='__main__': unittest.main()
