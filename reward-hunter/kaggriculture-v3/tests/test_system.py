import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from policy import make_v3,task,V3_DEFAULT,validate_params
from package_submission import build
from raw_exec_test import check
from promotion import gate
from opponents import SUITE
from benchmark import summary

class PolicyTests(unittest.TestCase):
    def observation(self):
        from kaggle_environments import make
        e=make('kaggriculture',configuration={'seed':992});e.reset(2)
        return e.state[0].observation,e.configuration

    def test_immature_harvest(self):
        tile={'kind':'PLANT','crop':'WHEAT','yield_units':2,'planted_day':0,'watered_today':True}
        self.assertIsNone(task(tile,1,25,False,V3_DEFAULT))
        self.assertIsNone(task(tile,1,25,False,V3_DEFAULT,True))

    def test_final_day_does_not_plant_or_water(self):
        self.assertIsNone(task(None,29,700,True,V3_DEFAULT,True))
        t={'kind':'PLANT','crop':'MELON','planted_day':28,'yield_units':1,'watered_today':False}
        self.assertIsNone(task(t,29,700,True,V3_DEFAULT,True))

    def test_final_drop_and_sell_same_turn(self):
        o,c=self.observation();o.step=718;o.day=29;o.hour=22
        o.farms[0]['farmer']=[4,4];o.private['inventories']=[{'WHEAT':7}]
        a=make_v3()(o,c)
        self.assertEqual(a['farmer'],['DROP']);self.assertIn(['SELL','WHEAT',7],a['market'])

    def test_locked_shed_access_routes_to_owned_tile(self):
        o,c=self.observation();o.step=715;o.day=29;o.hour=19
        o.farms[0]['farmer']=[5,4];o.private['inventories']=[{'WHEAT':7}]
        self.assertEqual(make_v3()(o,c)['farmer'],['WEST'])

    def test_no_mutation_or_state_leakage(self):
        o,c=self.observation();before=copy.deepcopy(o);a=make_v3()
        first=a(o,c);other=copy.deepcopy(o);other.player=1;a(other,c)
        self.assertEqual(first,a(o,c));self.assertEqual(o,before)

    def test_atomic_seed_budget(self):
        o,c=self.observation();o.farms[0]['farmer']=[0,0];o.farms[0]['hands']=[[1,0],[2,0]]
        o.private['seeds']={'WHEAT':1};o.private['inventories']=[{},{},{}]
        a=make_v3()(o,c);self.assertLessEqual(sum(x==['PLANT','WHEAT'] for x in [a['farmer']]+a['hands']),1)

    def test_parameter_validation(self):
        for p in ({'distance_cost':float('nan')},{'target_hands':True},{'unknown':1},{'crop_mode':'mystery'}):
            with self.assertRaises(ValueError):validate_params(p)

    def test_package_raw_exec_reproducible(self):
        with tempfile.TemporaryDirectory() as d:
            a=build(path=Path(d)/'a.py');b=build(path=Path(d)/'b.py')
            self.assertEqual(a['sha256'],b['sha256']);self.assertEqual(check(a['path'])['raw_exec'],'PASS')

class PromotionTests(unittest.TestCase):
    def report(self,seeds,families=SUITE,margin=100,kind='v3'):
        rows=[dict(seed=s,seat=seat,opponent=f,steps=720,valid=True,statuses=['DONE','DONE'],margin=margin,candidate_money=10000+margin,opponent_money=10000,efficiency=dict(actions=10,noops=0,moves=2,passes=0)) for s in seeds for f in families for seat in (0,1)]
        return dict(rows=rows,seeds=seeds,families=families,steps=720,params=V3_DEFAULT,kind=kind,provenance={'code_hash':'frozen','simulator_hash':'official'})
    def bundle(self):
        return [self.report([1,2]),self.report([11,12,13,14],('incumbent',)),self.report([21,22,23,24]),self.report([31,32,33,34]),self.report([21,22,23,24],margin=50,kind='incumbent'),self.report([31,32,33,34],margin=50,kind='incumbent'),dict(raw_exec='PASS',official_loader='PASS',episode_equivalence='PASS')]
    def test_positive_gate(self):self.assertTrue(gate(*self.bundle())['pass_gate'])
    def test_failures_not_removed_from_denominator(self):
        r=self.report([1],('incumbent',))['rows'];r[0]['valid']=False
        self.assertEqual(summary(r)['win_rate'],.5)
    def test_missing_duplicate_error_partial_and_identity(self):
        for mode in ('missing','duplicate','error','partial','identity'):
            b=self.bundle()
            if mode=='missing':b[2]['rows'].pop()
            if mode=='duplicate':b[2]['rows'].append(b[2]['rows'][0])
            if mode=='error':b[2]['rows'][0]['valid']=False
            if mode=='partial':b[2]['steps']=120
            if mode=='identity':b[2]['provenance']['code_hash']='changed'
            self.assertFalse(gate(*b)['pass_gate'],mode)
    def test_holdout_leakage_and_missing_raw(self):
        b=self.bundle();b[0]=self.report([21,22]);self.assertFalse(gate(*b)['pass_gate'])
        b=self.bundle();b[-1]={};self.assertFalse(gate(*b)['pass_gate'])
    def test_tail_regression_and_noops(self):
        b=self.bundle();b[2]['rows'][0]['margin']=-9000;self.assertFalse(gate(*b)['pass_gate'])
        b=self.bundle();b[2]['rows'][0]['efficiency']['noops']=1;self.assertFalse(gate(*b)['pass_gate'])

if __name__=='__main__':unittest.main()
