import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from ebs_audit import build_report


class EbsAuditTests(unittest.TestCase):
    def test_only_old_unattached_volumes_are_reported(self):
        fixture = json.loads((Path(__file__).parents[1] / "fixtures" / "volumes.json").read_text())
        report = build_report(
            fixture["accounts"],
            older_than_days=30,
            rate=0.08,
            now=datetime(2026, 10, 29, tzinfo=timezone.utc),
        )
        self.assertEqual(report["volume_count"], 2)
        self.assertEqual(report["estimated_monthly_cost_usd"], 12.0)
        self.assertNotIn("vol-attached-dev", {v["volume_id"] for v in report["volumes"]})


if __name__ == "__main__":
    unittest.main()

