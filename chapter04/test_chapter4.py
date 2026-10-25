import random
import unittest
from dataclasses import replace
from chapter4 import *

class HistoricalFeatureTests(unittest.TestCase):
    def test_original_decision(self):
        self.assertEqual(historical_sum(EVENTS, 'C1', 600), 50)
    def test_later_decision(self):
        self.assertEqual(historical_sum(EVENTS, 'C1', 610), 95)
    def test_corrected_view(self):
        latest = {}
        for e in EVENTS:
            if e.customer == 'C1' and (e.event not in latest or
                                     e.version > latest[e.event].version):
                latest[e.event] = e
        self.assertEqual(sum(e.amount for e in latest.values()
                             if 540 <= e.event_time < 600), 85)
    def test_bad_operation_order(self):
        latest = {}
        for e in EVENTS:
            if e.customer == 'C1' and (e.event not in latest or
                                     e.version > latest[e.event].version):
                latest[e.event] = e
        self.assertEqual(sum(e.amount for e in latest.values()
          if 540 <= e.event_time < 600 and e.available_at <= 600), 20)
    def test_duplicate_replay(self):
        self.assertEqual(historical_sum(EVENTS * 3, 'C1', 600), 50)
    def test_row_order(self):
        for seed in range(20):
            shuffled = list(EVENTS)
            random.Random(seed).shuffle(shuffled)
            self.assertEqual(historical_sum(shuffled, 'C1', 600), 50)
    def test_event_window_boundaries(self):
        extra = [Event('C1','E',1,540,541,5),
                 Event('C1','F',1,600,600,7)]
        self.assertEqual(historical_sum(EVENTS+extra,'C1',600),55)
    def test_availability_boundary(self):
        extra = [Event('C1','E',1,590,600,5)]
        self.assertEqual(historical_sum(EVENTS+extra,'C1',600),55)
        extra = [replace(extra[0], available_at=601)]
        self.assertEqual(historical_sum(EVENTS+extra,'C1',600),50)
    def test_future_correction_does_not_change_history(self):
        e = Event('C1','C',3,585,700,999)
        self.assertEqual(historical_sum(EVENTS+[e],'C1',600),50)
    def test_old_revision_arriving_late(self):
        es = [Event('C1','Z',2,590,595,2),
              Event('C1','Z',1,590,599,9)]
        self.assertEqual(historical_sum(es,'C1',600),2)
    def test_other_customer_isolated(self):
        self.assertEqual(historical_sum(EVENTS+[Event('C2','foreign-event',1,590,591,999)],'C1',600),50)
    def test_conflicting_duplicate_rejected(self):
        with self.assertRaises(ValueError):
            historical_sum(EVENTS+[replace(EVENTS[0],amount=21)],'C1',600)
    def test_null_time_rejected(self):
        with self.assertRaises(ValueError):
            historical_sum([replace(EVENTS[0],available_at=None)],'C1',600)
    def test_nonpositive_width_rejected(self):
        with self.assertRaises(ValueError):
            historical_sum(EVENTS,'C1',600,width=0)
    def test_time_correction_rejected(self):
        with self.assertRaises(ValueError):
            historical_sum(EVENTS+[Event('C1','A',2,551,552,20)],'C1',600)

class LabelAndDatasetTests(unittest.TestCase):
    def test_finalized_positive_and_negative(self):
        self.assertEqual(label_at(DECISIONS[0],OUTCOMES,FINALIZED_AT,1200),1)
        self.assertEqual(label_at(DECISIONS[1],OUTCOMES,FINALIZED_AT,1200),0)
    def test_early_positive_still_waits(self):
        self.assertIsNone(label_at(DECISIONS[3],OUTCOMES,FINALIZED_AT,1200))
    def test_label_window_boundaries(self):
        d=DECISIONS[0]
        self.assertEqual(label_at(d,[Outcome('x','D1',600,601)],{'D1':730},730),0)
        self.assertEqual(label_at(d,[Outcome('x','D1',720,725)],{'D1':730},730),1)
        self.assertEqual(label_at(d,[Outcome('x','D1',721,725)],{'D1':730},730),0)
    def test_finalization_boundary(self):
        d=DECISIONS[0]
        self.assertIsNone(label_at(d,OUTCOMES,FINALIZED_AT,729))
        self.assertEqual(label_at(d,OUTCOMES,FINALIZED_AT,730),1)
    def test_elapsed_horizon_is_not_finalization(self):
        self.assertIsNone(label_at(DECISIONS[1],[],{},1500))
    def test_bad_finalization_rejected(self):
        with self.assertRaises(ValueError):
            label_at(DECISIONS[0],OUTCOMES,{'D1':710},1200)
    def test_late_outcome_contradicts_certificate(self):
        with self.assertRaises(ValueError):
            label_at(DECISIONS[0],[Outcome('late','D1',680,800)],{'D1':730},1200)
    def test_final_dataset(self):
        rows,excluded=build_dataset()
        self.assertEqual([r['decision_id'] for r in rows],['D1','D2','D3','D5','D6'])
        self.assertEqual([r['spend'] for r in rows],[50,95,20,10,40])
        self.assertEqual([r['label'] for r in rows],[1,0,0,1,0])
        self.assertEqual(excluded,[('D4','label not mature at cutoff')])
    def test_unique_decision_guard(self):
        with self.assertRaises(ValueError):
            build_dataset(decisions=DECISIONS+[DECISIONS[0]])
    def test_duplicate_outcome_does_not_multiply_rows(self):
        self.assertEqual(build_dataset(outcomes=OUTCOMES*2),build_dataset())
    def test_future_outcome_outside_horizon_does_not_change_label(self):
        extra=Outcome('after','D2',900,901)
        self.assertEqual(build_dataset(outcomes=OUTCOMES+[extra]),build_dataset())
    def test_feature_future_data_does_not_change_earlier_rows(self):
        rows,_=build_dataset(events=EVENTS+[Event('C1','C',3,585,1700,500)])
        self.assertEqual(rows,build_dataset()[0])
    def test_zero_and_missing_history_are_different(self):
        decisions=[replace(DECISIONS[0],history_complete=False)]+DECISIONS[1:]
        rows,_=build_dataset(decisions=decisions)
        self.assertIsNone(rows[0]['spend'])
        self.assertEqual(historical_sum([], 'C3',1190),0)
    def test_time_split_boundaries(self):
        d=[Decision('B1','C0',1200),Decision('B2','C0',1400)]
        rows,excluded=build_dataset(decisions=d,events=[],outcomes=[],
                                   finalized_at={'B1':1320,'B2':1520})
        self.assertEqual(rows[0]['split'],'validation')
        self.assertEqual(excluded,[('B2','outside evaluation interval')])
    def test_train_labels_use_fit_time(self):
        rows,_=build_dataset()
        self.assertTrue(all(r['label_cutoff']==1200 for r in rows if r['split']=='train'))
        self.assertNotIn('D4',[r['decision_id'] for r in rows])
    def test_join_cardinality(self):
        bad,good=join_demo()
        self.assertEqual(len(bad),4)
        self.assertEqual(good,[('D1',50),('D2',95)])
    def test_training_only_transform(self):
        center=fit_center([50,95,20])
        self.assertEqual(center,55)
        self.assertEqual(transform([50,95,20],center),[-5,40,-35])
        self.assertEqual(transform([10,40],center),[-45,-15])
        self.assertEqual(fit_center([50,95,20,10,40]),43)
    def test_missing_imputation_uses_training(self):
        self.assertEqual(fit_center([50,None,20]),35)
        self.assertEqual(transform([None,100],35),[0,65])
    def test_all_missing_fit_rejected(self):
        with self.assertRaises(ValueError):
            fit_center([None,None])
    def test_new_customer_sensitivity(self):
        rows,_=build_dataset()
        train_customers={r['customer'] for r in rows if r['split']=='train'}
        novel=[r for r in rows if r['split']=='validation' and r['customer'] not in train_customers]
        self.assertEqual([r['decision_id'] for r in novel],['D6'])
    def test_train_and_validation_are_disjoint(self):
        rows,_=build_dataset()
        train={r['decision_id'] for r in rows if r['split']=='train'}
        valid={r['decision_id'] for r in rows if r['split']=='validation'}
        self.assertFalse(train & valid)

if __name__ == '__main__':
    unittest.main()
