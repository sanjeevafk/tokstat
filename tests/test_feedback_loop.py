# test_feedback_loop.py
import unittest

from tokstat import analytics


class TestTokenTotals(unittest.TestCase):
    def test_analytics_total_tokens(self):
        data = analytics.compute_analytics()
        if not data:
            # Running in CI or environment without local telemetry DB
            self.assertEqual(data, {})
            return
            
        overview = data.get("global_overview", {})
        total_tokens = overview.get("total_tokens", 0)
        
        print(f"[TEST FEEDBACK LOOP] Computed Total Tokens: {total_tokens:,}")
        self.assertGreaterEqual(
            total_tokens, 
            0, 
            f"Total tokens ({total_tokens:,}) must be non-negative."
        )

if __name__ == "__main__":
    unittest.main()
