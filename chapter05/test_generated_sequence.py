"""Focused complete-sequence oracle tests; corpus totals are not a substitute."""
from dataclasses import replace
import unittest
from unittest.mock import patch

import chapter5 as lab
import randomized_checks as checks


def omit_and_pad(result,policy):
    """Deliberate same-count fault used only by these disposable test results."""
    rows=result['outputs']
    if len(rows)>=3 and rows[-1].emitted_at<policy.close_at:
        faulty=rows[:1]+rows[2:]+[replace(rows[-1],emitted_at=policy.close_at,input_cutoff=policy.close_at)]
        result=dict(result,outputs=[replace(row,revision=i) for i,row in enumerate(faulty,1)])
    return result


class CompleteSequenceOracleTests(unittest.TestCase):
    def test_base_sequences_match_independent_enumeration(self):
        for policy,values in [(lab.IMMEDIATE,[(600,50),(605,45),(607,85)]),(lab.DELAYED,[(610,85)])]:
            with self.subTest(policy=policy.policy_id):
                expected=checks.oracle_sequence(lab.BASE,policy)
                self.assertEqual([(x['emitted_at'],x['total']) for x in expected],values)
                checks.assert_sequence(lab.simulate(policy)['outputs'],expected,'focused base')

    def test_same_value_provenance_coalescing_and_inclusive_deadline(self):
        scenarios=[
            ([lab.Delivery('x1',600,lab.Event('X',1,550,600,5)),lab.Delivery('x2',605,lab.Event('X',2,550,605,5))],[(600,5),(605,5)]),
            ([lab.Delivery('a',605,lab.Event('A',1,550,605,4)),lab.Delivery('b',605,lab.Event('B',1,551,605,6))],[(600,0),(605,10)]),
            ([lab.Delivery('on',610,lab.Event('on',1,550,610,4)),lab.Delivery('after',611,lab.Event('after',1,551,611,8))],[(600,0),(610,4)]),
        ]
        for deliveries,values in scenarios:
            with self.subTest(values=values):
                expected=checks.oracle_sequence(deliveries,lab.IMMEDIATE)
                self.assertEqual([(x['emitted_at'],x['total']) for x in expected],values)
                checks.assert_sequence(lab.simulate(lab.IMMEDIATE,deliveries)['outputs'],expected,'focused edge')

    def test_missing_intermediate_and_redundant_close_preserve_count_but_fail(self):
        clean=lab.simulate(lab.IMMEDIATE)
        faulty=omit_and_pad(clean,lab.IMMEDIATE)
        self.assertEqual(len(faulty['outputs']),len(clean['outputs']))
        self.assertEqual(faulty['outputs'][-1].total,clean['outputs'][-1].total)
        with self.assertRaisesRegex(AssertionError,r'sequence\[1\]\.emitted_at'):
            checks.assert_sequence(faulty['outputs'],checks.oracle_sequence(lab.BASE,lab.IMMEDIATE),'focused same-count fault')

    def test_seeded_check_rejects_same_count_transition_fault(self):
        original=checks.simulate
        def mutant(policy,*args,**kwargs):
            return omit_and_pad(original(policy,*args,**kwargs),policy)
        with patch.object(checks,'fixture',return_value=list(lab.BASE)),patch.object(checks,'simulate',mutant),self.assertRaisesRegex(AssertionError,r'seed=0.*sequence\[1\]\.emitted_at'):
            checks.check(0,lab.IMMEDIATE)

    def test_expected_sequence_does_not_call_simulator_or_reference(self):
        with patch.object(checks,'simulate',side_effect=AssertionError('simulator forbidden')),patch.object(checks,'reference',side_effect=AssertionError('reference forbidden')),patch.object(lab,'selected',side_effect=AssertionError('selector forbidden')):
            expected=checks.oracle_sequence(lab.BASE,lab.IMMEDIATE)
            self.assertEqual([x['total'] for x in expected],[50,45,85])
            self.assertEqual([x['revision'] for x in expected],[1,2,3])


if __name__=='__main__':
    unittest.main()
