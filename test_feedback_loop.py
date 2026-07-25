# test_feedback_loop.py
import unittest
import analytics
import db_access

class TestTokenTotals(unittest.TestCase):
    def test_analytics_total_tokens(self):
        data = analytics.compute_analytics()
        overview = data.get("global_overview", {})
        total_tokens = overview.get("total_tokens", 0)
        
        # Total tokens logged across all telemetry streams should reflect the complete usage (~3.1B tokens)
        # Currently, analytics.compute_analytics() only returns ~694M tokens.
        print(f"[TEST FEEDBACK LOOP] Computed Total Tokens: {total_tokens:,}")
        
        # Assertion threshold: should be > 3,000,000,000 (3.0 Billion)
        self.assertGreaterEqual(
            total_tokens, 
            3000000000, 
            f"Total tokens ({total_tokens:,}) is undercounted! Expected ~3.08B - 3.16B tokens."
        )

if __name__ == "__main__":
    unittest.main()
