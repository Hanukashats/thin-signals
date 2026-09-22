import unittest
from policy import route, normalized_growth

def base(**changes):
    s=dict(as_of='2026-09-17',novelty='new',maturity='emerging',critical_claims=['verified','supported'],fatal_finding='none',evidence_events=3,independent_origins=2,countersearch_done=True,source_availability_valid=True,budget_exhausted=False,branches_complete=True,transition_verified=True)
    s.update(changes);return s

def window(start,end,n,N=100,**changes):
    s=dict(start=start,end=end,n=n,N=N,days=30,protocol='fixed-v1',coverage='complete_for_query',complete_period=True)
    s.update(changes);return s

class EvidencePolicyTests(unittest.TestCase):
    def test_verified_fatal_wins_over_deadline(self):
        self.assertEqual(route(base(fatal_finding='verified',budget_exhausted=True))['action'],'REJECT_OR_REFRAME')
    def test_empty_claims_never_eligible(self):
        self.assertEqual(route(base(critical_claims=[]))['action'],'TARGETED_RESEARCH')
    def test_unknown_not_pass(self):
        self.assertEqual(route(base(critical_claims=['unknown'],budget_exhausted=True))['action'],'HOLD')
    def test_weak_negative_not_kill(self):
        self.assertEqual(route(base(fatal_finding='weak'))['action'],'VERIFY_COUNTEREVIDENCE')
    def test_mature_parent_redirect(self):
        self.assertEqual(route(base(maturity='established'))['action'],'REFRAME_CHILD')
    def test_singleton_is_preserved(self):
        self.assertEqual(route(base(evidence_events=1,independent_origins=1))['action'],'WATCHLIST_SINGLETON')
    def test_reposts_do_not_qualify(self):
        self.assertEqual(route(base(evidence_events=10,independent_origins=1))['action'],'WATCHLIST')
    def test_future_evidence_blocks_rank(self):
        self.assertEqual(route(base(source_availability_valid=False))['action'],'HOLD')
    def test_missing_countersearch_blocks_rank(self):
        self.assertEqual(route(base(countersearch_done=False))['action'],'COUNTERSEARCH')
    def test_fully_adjudicated_candidate(self):
        self.assertEqual(route(base())['action'],'RANK_ELIGIBLE')
    def test_missing_key_or_invalid_type(self):
        self.assertEqual(route({})['action'],'HOLD')
        self.assertEqual(route(base(countersearch_done='yes'))['action'],'HOLD')
    def test_partial_cohort_not_zero_growth(self):
        self.assertIsNone(normalized_growth(window('2026-08-01','2026-08-30',10,coverage='partial'),window('2026-07-01','2026-07-30',2)))
    def test_changed_query_not_comparable(self):
        self.assertIsNone(normalized_growth(window('2026-08-01','2026-08-30',10,protocol='new'),window('2026-07-01','2026-07-30',2)))
    def test_growth_and_overlap(self):
        self.assertGreater(normalized_growth(window('2026-08-01','2026-08-30',10),window('2026-07-01','2026-07-30',2)),0)
        self.assertIsNone(normalized_growth(window('2026-07-01','2026-07-30',10),window('2026-07-01','2026-07-30',2)))
    def test_zero_denominator_not_measurement(self):
        self.assertIsNone(normalized_growth(window('2026-08-01','2026-08-30',0,N=0),window('2026-07-01','2026-07-30',2)))

if __name__=='__main__': unittest.main()
