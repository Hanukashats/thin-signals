import copy
import unittest
from score import ROOT, evaluate, rank, read_json, sensitivity, for_stream

class ScoringTests(unittest.TestCase):
    def setUp(self):
        self.model = read_json(ROOT/"model.json")
        self.candidates = read_json(ROOT/"candidates.json")
        self.c = copy.deepcopy(self.candidates[0])

    def test_unknowns_are_not_renormalized_or_approved(self):
        result = evaluate(self.c, self.model)
        self.assertEqual(result["score_lower"],64)
        self.assertEqual(result["score_upper"],74)
        self.assertFalse(result["fully_qualified"])

    def test_funded_business_cannot_buy_its_way_through_gates(self):
        self.c["commercial_status"] = "funded_business"
        self.c["scores"] = {key:5 for key in self.model["weights"]}
        result = evaluate(self.c,self.model)
        self.assertEqual(result["score_lower"],100)
        self.assertEqual(result["decision"],"exclude")
        self.assertFalse(result["partner_review_ready"])

    def test_retraction_blocks_every_score(self):
        self.c["retracted"] = True
        self.assertEqual(evaluate(self.c,self.model)["decision"],"exclude")

    def test_future_evidence_rejected(self):
        self.c["as_of"] = "2026-09-30"
        self.assertIn("future_information", evaluate(self.c,self.model)["failures"])

    def test_future_source_rejected_even_if_record_checked_today(self):
        sources = {s["id"]:s for s in read_json(ROOT/"sources.json")}
        sources["S05"]["published"] = "2026-12-16"
        result = evaluate(self.c,self.model,sources)
        self.assertIn("future_publication",result["failures"])

    def test_strict_twenty_year_policy(self):
        self.model["thresholds"]["minimum_age"] = 20
        self.assertIn("too_young_for_resurrection_profile",evaluate(self.candidates[-1],self.model)["failures"])

    def test_new_discovery_does_not_require_old_history(self):
        self.c['historical_year'] = None
        self.c['scores']['history'] = None
        model = for_stream(self.model,'emergence')
        result = evaluate(self.c,model)
        self.assertNotIn('historical_fit',result['holds'])
        self.assertNotIn('history',result['missing_dimensions'])
        self.assertFalse(result['failures'])
        self.assertEqual(model['weights']['evidence'],25)

    def test_high_score_still_requires_system_comparison_and_protocol(self):
        self.c['scores'] = {key:5 for key in self.model['weights']}
        self.c.update(commercial_status='unoccupied_verified',ip_status='access_verified',retraction_screen='screened_no_flag')
        result = evaluate(self.c,self.model)
        self.assertFalse(result['fully_qualified'])
        self.assertIn('system_comparison',result['holds'])
        self.assertIn('test_protocol',result['holds'])
        self.c.update(system_comparison_status='validated',decisive_test_status='agreed')
        self.assertTrue(evaluate(self.c,self.model)['fully_qualified'])

    def test_invalid_scores_and_weights_fail(self):
        for invalid in (-1,6,float("nan"),True):
            self.c["scores"]["evidence"] = invalid
            with self.assertRaises(ValueError):
                evaluate(self.c,self.model)
        self.model["weights"]["evidence"] = 19
        with self.assertRaises(ValueError):
            evaluate(self.candidates[0],self.model)

    def test_sources_and_ids_are_valid(self):
        sources = read_json(ROOT/"sources.json")
        source_ids = {s["id"] for s in sources}
        self.assertEqual(len(source_ids),len(sources))
        self.assertEqual(len(self.candidates),15)
        for candidate in self.candidates:
            self.assertTrue(set(candidate["source_ids"]) <= source_ids)
            self.assertTrue(candidate["history_sources"])
            self.assertTrue(candidate["current_sources"])
        with self.assertRaises(ValueError):
            rank(self.candidates+[self.candidates[0]],self.model)

    def test_ranking_and_sensitivity(self):
        results = rank(self.candidates,self.model)
        self.assertEqual(results[0]["id"],"T02")
        self.assertTrue(all(not r["fully_qualified"] for r in results))
        audit = sensitivity(self.candidates,self.model)
        self.assertEqual(audit["scenarios"],16)
        self.assertEqual(len(audit["rank_ranges"]),15)

if __name__ == "__main__":
    unittest.main()
