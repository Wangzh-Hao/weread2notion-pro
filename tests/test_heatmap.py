import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from weread2notionpro.heatmap import generate_heatmap


class HeatmapTests(unittest.TestCase):
    def test_generates_svg_with_daily_tooltip(self):
        timestamp = int(
            datetime(
                2026,
                1,
                2,
                tzinfo=timezone(timedelta(hours=8)),
            ).timestamp()
        )
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "weread.svg"
            generate_heatmap({timestamp: 3600}, 2026, output, name="Reader")
            svg = output.read_text(encoding="utf-8")

        self.assertIn("Reader 2026 微信读书", svg)
        self.assertIn("2026-01-02：60 分钟", svg)
        self.assertIn("共 1.0 小时", svg)


if __name__ == "__main__":
    unittest.main()
