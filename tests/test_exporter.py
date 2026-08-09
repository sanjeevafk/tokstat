# test_exporter.py
import os
import tempfile
import unittest

from tokstat import exporter


class TestExporterReconciliation(unittest.TestCase):
    def _report(self, gap=0):
        return {
            "global_overview": {
                "total_tokens": 1000,
                "total_input": 700,
                "total_output": 300,
                "cached_tokens": 0,
                "cache_hit_pct": 0.0,
                "requests_count": 1,
                "sessions_count": 1,
                "active_repositories_count": 1,
                "active_models_count": 1,
                "active_tools_count": 1,
                "avg_context_size": 700,
                "avg_tokens_per_request": 1000,
                "peak_usage_day": "2026-08-01",
                "peak_usage_tokens": 1000,
                "longest_session_duration": 60,
                "estimated_cost": 1.0,
                "estimated_savings": 0.0,
                "provider_reported_tokens": 6000,
                "local_event_tokens": 1000,
                "coverage_gap_tokens": gap,
            },
            "repositories": [],
            "sessions": [],
            "events": [],
            "models": [],
            "tools": [],
            "time_analytics": {"busiest_coding_day": "N/A"},
            "productivity_metrics": {
                "output_input_ratio": 0.0,
                "cache_savings": 0.0,
                "tokens_per_request": 0,
                "sessions_per_day": 0.0,
                "average_coding_session_length": 0,
            },
        }

    def test_markdown_has_reconciliation_section_when_gap(self):
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "report.md")
        self.assertTrue(exporter.export_markdown(self._report(gap=5000), path))
        with open(path, encoding="utf-8") as f:
            text = f.read()
        self.assertIn("## Provider Reconciliation", text)
        self.assertIn("tokstat sync", text)
        self.assertIn("5.0k", text)  # format_tokens(5000)

    def test_markdown_no_section_when_no_gap(self):
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "report.md")
        self.assertTrue(exporter.export_markdown(self._report(gap=0), path))
        with open(path, encoding="utf-8") as f:
            text = f.read()
        self.assertNotIn("Provider Reconciliation", text)

    def test_pdf_renders_with_gap(self):
        # The reconciliation row must not break PDF generation.
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "report.pdf")
        self.assertTrue(exporter.export_pdf(self._report(gap=5000), path))
        self.assertTrue(os.path.exists(path))
        self.assertGreater(os.path.getsize(path), 0)


if __name__ == "__main__":
    unittest.main()
