import unittest
import random
from dataclasses import replace
from chapter5 import *

class PolicyTests(unittest.TestCase):
    def values(self, policy=IMMEDIATE, ds=BASE, **kw):
        return [(o.emitted_at,o.total) for o in simulate(policy,ds,**kw)['outputs']]
    def test_immediate_golden(self):
        self.assertEqual(self.values(),[(600,50),(605,45),(607,85)])
    def test_delayed_golden(self):
        self.assertEqual(self.values(DELAYED),[(610,85)])
    def test_original_historical_value(self):
        self.assertEqual(sum(e.amount for e in reference(cutoff=600).values()),50)
    def test_fixed_window_later_cutoff(self):
        self.assertEqual(sum(e.amount for e in reference(cutoff=610).values()),85)
    def test_moving_window_is_different(self):
        self.assertEqual(sum(e.amount for e in reference(start=550,end=610,cutoff=610).values()),95)
    def test_adversarial_audit_value(self):
        self.assertEqual(sum(e.amount for e in reference(BASE+(LATE_E,)).values()),100)
    def test_after_deadline_does_not_change_outputs(self):
        for policy in (IMMEDIATE,DELAYED):
            self.assertEqual(self.values(policy,BASE+(LATE_E,)),self.values(policy))
    def test_reconciliation_deduplicates_versions(self):
        ds=BASE+(LATE_E,replace(LATE_E,delivery_id='e_retry',at=613))
        self.assertEqual(simulate(IMMEDIATE,ds)['reconciliation'],[LATE_E])
    def test_old_revision_retry_cannot_replace_newer(self):
        old=replace(BASE[1],delivery_id='c_old_retry',at=606)
        self.assertEqual(self.values(ds=BASE+(old,)),self.values())
    def test_repeated_physical_input_storage(self):
        self.assertEqual(self.values(ds=BASE*3),self.values())
    def test_retry_after_first_output(self):
        self.assertEqual(self.values(ds=BASE+(Delivery('a_late',601,A),)),self.values())
    def test_retry_after_closure(self):
        self.assertEqual(self.values(ds=BASE+(Delivery('a_later',620,A),)),self.values())
    def test_conflicting_source_version_is_rejected(self):
        with self.assertRaises(ValueError):
            simulate(IMMEDIATE,BASE+(Delivery('bad',590,replace(A,amount=21)),))
    def test_conflicting_delivery_id_is_rejected(self):
        with self.assertRaises(ValueError):
            simulate(IMMEDIATE,BASE+(replace(BASE[0],at=552),))
    def test_event_time_change_is_rejected(self):
        with self.assertRaises(ValueError):
            simulate(IMMEDIATE,BASE+(Delivery('a2',608,Event('A',2,552,608,20)),))
    def test_missing_numeric_field_is_rejected(self):
        with self.assertRaises(ValueError):
            simulate(IMMEDIATE,(Delivery('bad',551,replace(A,available_at=None)),))
    def test_missing_first_usable_delivery_is_rejected(self):
        with self.assertRaises(ValueError):
            simulate(IMMEDIATE,(Delivery('only_retry',590,A),))
    def test_negative_amount_is_rejected(self):
        with self.assertRaises(ValueError):
            simulate(IMMEDIATE,(Delivery('negative',551,replace(A,amount=-1)),))
    def test_processing_cannot_precede_availability(self):
        with self.assertRaises(ValueError):
            simulate(IMMEDIATE,(Delivery('bad',550,A),))
    def test_event_window_boundaries(self):
        ds=tuple(Delivery(str(t),600,Event(str(t),1,t,600,1)) for t in (539,540,599,600))
        self.assertEqual(self.values(ds=ds),[(600,2)])
    def test_first_emission_includes_same_time_arrival(self):
        ds=BASE+(Delivery('k',600,Event('K',1,599,600,7)),)
        self.assertEqual(self.values(ds=ds)[0],(600,57))
    def test_deadline_is_inclusive(self):
        ds=BASE+tuple(Delivery(str(t),t,Event(str(t),1,599,t,1)) for t in (609,610,611))
        self.assertEqual(self.values(DELAYED,ds),[(610,87)])
        self.assertEqual([d.at for d in simulate(DELAYED,ds)['reconciliation']],[611])
    def test_all_same_time_arrivals_precede_delayed_output(self):
        ds=BASE+(Delivery('k',610,Event('K',1,599,610,7)),
                 Delivery('l',610,Event('L',1,598,610,3)))
        self.assertEqual(self.values(DELAYED,ds),[(610,95)])
        self.assertEqual(self.values(IMMEDIATE,ds)[-1],(610,95))
        self.assertEqual(sum(t==610 for t,_ in self.values(IMMEDIATE,ds)),1)
    def test_same_time_revisions_use_highest_source_revision(self):
        ds=(Delivery('z_v2',600,Event('Z',2,590,600,2)),
            Delivery('z_v1',600,Event('Z',1,590,600,9)))
        self.assertEqual(self.values(ds=ds),[(600,2)])
    def test_same_amount_correction_still_updates_provenance(self):
        ds=BASE+(Delivery('c3',609,Event('C',3,585,609,25)),)
        outs=simulate(IMMEDIATE,ds)['outputs']
        self.assertEqual((outs[-1].emitted_at,outs[-1].total),(609,85))
        self.assertIn(('C',3,25,609),outs[-1].contributions)
    def test_storage_order_does_not_change_replay(self):
        expected=simulate(IMMEDIATE,BASE)
        for seed in range(25):
            ds=list(BASE);random.Random(seed).shuffle(ds)
            self.assertEqual(simulate(IMMEDIATE,ds),expected)
    def test_other_entity_is_isolated(self):
        ds=BASE+(Delivery('other',600,Event('A',1,590,600,999,'C2')),)
        self.assertEqual(self.values(ds=ds),self.values())
    def test_future_version_does_not_rewrite_past(self):
        ds=BASE+(Delivery('c9',700,Event('C',9,585,700,999)),)
        self.assertEqual(sum(e.amount for e in reference(ds,cutoff=600).values()),50)
    def test_no_watermarks_does_not_change_policy_outputs(self):
        self.assertEqual(self.values(watermarks=()),self.values())
    def test_changed_watermarks_change_diagnostics_only(self):
        r=simulate(IMMEDIATE,watermarks=((500,1000),))
        self.assertEqual(r['outputs'],simulate(IMMEDIATE)['outputs'])
        self.assertTrue(all(x['behind_watermark'] for x in r['diagnostics']))
    def test_watermark_uses_prior_control_at_equal_time(self):
        ds=(Delivery('k',600,Event('K',1,590,600,1)),)
        r=simulate(IMMEDIATE,ds,watermarks=((580,580),(600,600)))
        self.assertEqual(r['diagnostics'][0]['watermark_before'],580)
        self.assertFalse(r['diagnostics'][0]['behind_watermark'])
    def test_backward_watermark_rejected(self):
        with self.assertRaises(ValueError):
            simulate(IMMEDIATE,watermarks=((500,490),(510,480)))
    def test_unknown_history_not_zero(self):
        with self.assertRaises(ValueError):
            simulate(IMMEDIATE,history_complete=False)
    def test_known_empty_history_yields_zero(self):
        self.assertEqual(self.values(ds=()),[(600,0)])
    def test_invalid_policy_rejected(self):
        with self.assertRaises(ValueError):
            simulate(Policy('bad',610,605))
    def test_output_replay_is_idempotent_and_no_regression(self):
        outs=simulate(IMMEDIATE)['outputs']
        result=latest_outputs(list(reversed(outs))+outs+outs)
        self.assertEqual(list(result.values()),[outs[-1]])
    def test_conflicting_output_revision_rejected(self):
        o=simulate(IMMEDIATE)['outputs'][0]
        with self.assertRaises(ValueError):
            latest_outputs([o,replace(o,total=999)])
    def test_policy_keys_remain_distinct(self):
        outs=simulate(IMMEDIATE)['outputs']+simulate(DELAYED)['outputs']
        self.assertEqual(len(latest_outputs(outs)),2)
    def test_replacement_values_are_not_deltas(self):
        outs=simulate(IMMEDIATE)['outputs']
        self.assertEqual(sum(o.total for o in outs),180)
        self.assertEqual(list(latest_outputs(outs).values())[0].total,85)
    def test_base_first_metrics(self):
        a=reference(); first=simulate(IMMEDIATE)['outputs'][0]
        s=score(first,a)
        self.assertEqual((s['identities_seen'],s['matching_latest_versions'],s['audit_identities']),(2,1,3))
        self.assertEqual((s['window_age'],s['absolute_aggregate_difference']),(0,35))
    def test_late_fixture_metrics_and_error_are_distinct(self):
        a=reference(BASE+(LATE_E,)); outs=simulate(IMMEDIATE)['outputs']
        scored=[score(o,a) for o in outs]
        self.assertEqual([s['absolute_aggregate_difference'] for s in scored],[50,55,15])
        self.assertEqual([s['matching_latest_versions'] for s in scored],[1,2,3])
        self.assertEqual([s['identities_seen'] for s in scored],[2,2,3])
    def test_delayed_window_age_and_coverage(self):
        out=simulate(DELAYED)['outputs'][0]
        s=score(out,reference(BASE+(LATE_E,)))
        self.assertEqual((s['window_age'],s['identity_coverage']),(10,.75))
    def test_empty_audit_denominator_is_unknown(self):
        out=simulate(IMMEDIATE,())['outputs'][0]
        self.assertIsNone(score(out,{})['identity_coverage'])
        self.assertIsNone(score(out,{})['latest_version_agreement'])

if __name__ == '__main__':
    unittest.main()
