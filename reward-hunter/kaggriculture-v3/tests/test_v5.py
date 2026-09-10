import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from policy import V3_DEFAULT,validate_params,_animal_targets,_crop_score,make_v3
from features import features

class V5EconomyTests(unittest.TestCase):
    def obs(self):
        from kaggle_environments import make
        e=make('kaggriculture',configuration={'seed':551});e.reset(2)
        return e.state[0].observation,e.configuration
    def test_v5_params(self):
        p=validate_params(None);self.assertEqual(p['herd_mode'],'dynamic');self.assertEqual(p['crop_mode'],'roi')
        with self.assertRaises(ValueError):validate_params({'cow_max':99})
    def test_initial_land_has_priority(self):
        o,c=self.obs();a=make_v3()(o,c)
        self.assertTrue(any(x[0]=='BUY_LAND' for x in a['market']))
    def test_public_features_only_and_repeatable(self):
        o,c=self.obs();before=copy.deepcopy(o);f=features(o,c);self.assertEqual(o,before);self.assertIn('demand',f);self.assertIn('productive_utilization',f)
    def test_roi_prefers_fast_cash_when_land_starved(self):
        o,c=self.obs();f=features(o,c);p=validate_params(None)
        f['money']=0;f['next_land_cost']=1000;f['full_farm']=False
        self.assertGreater(max(_crop_score('WHEAT',f,p),_crop_score('CARROT',f,p)),_crop_score('MELON',f,p))
    def test_dynamic_egg_requires_public_signal(self):
        o,c=self.obs();f=features(o,c);p=validate_params({'goose_max':4})
        f['demand']['EGG']=0;f['price_ratios']['EGG']=1.0
        self.assertEqual(_animal_targets(f,p)['GOOSE'],0)

if __name__=='__main__':unittest.main()
