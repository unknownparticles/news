import copy
import json
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

from src.common import canonical_url, save_report, validate_report
from src.collect import collect, feed_items
from src.periods import aggregate, bounds, period_id, run
from src.build import build


def daily(day="2026-10-12", identity="event-12345678"):
    return {"id": day, "kind": "daily", "title": day + " · 日报", "period": {"start": day, "end": day},
            "generated_at": day + "T08:30:00+08:00", "summary": "测试报告，不发布",
            "coverage": {"expected_days": 1, "available_days": 1, "missing_dates": []},
            "items": [{"event_id": identity, "headline": "<script>alert(1)</script>", "summary": "已核对事实",
                       "category": "AI 编程", "verification_status": "official_confirmed", "score": 80,
                       "relevance": "开发效率", "action": "检查更新",
                       "sources": [{"label": "公告", "url": "https://openai.com/index/example", "excerpt": "事实摘录", "checked_at": day + "T08:20:00+08:00"}]}]}


class ReportsTest(unittest.TestCase):
    def test_canonical_preserves_significant_query(self):
        self.assertEqual(canonical_url("https://example.com/news/?v=2&utm_source=x#top"), "https://example.com/news?v=2")

    def test_official_host_lookalike_rejected(self):
        report = daily()
        report['items'][0]['sources'][0]['url'] = 'https://openai.com.evil.example/index/x'
        with self.assertRaises(ValueError):
            validate_report(report)

    def test_unsafe_url_and_unlicensed_commercial_rejected(self):
        report = daily()
        report['items'][0]['sources'][0]['url'] = 'javascript:alert(1)'
        with self.assertRaises(ValueError):
            validate_report(report)
        report = daily()
        report['items'][0]['commercial_status'] = 'eligible'
        with self.assertRaises(ValueError):
            validate_report(report)

    def test_coverage_and_max_daily_items(self):
        report = daily()
        report['coverage']['available_days'] = 0
        with self.assertRaises(ValueError):
            validate_report(report)
        report = daily()
        report['items'] = [dict(copy.deepcopy(report['items'][0]), event_id=f'event-{i:08d}') for i in range(6)]
        with self.assertRaises(ValueError):
            validate_report(report)

    def test_calendar_edges(self):
        start, end = bounds(date(2027, 1, 1), 'weekly')
        self.assertEqual((start, end), (date(2026, 12, 28), date(2027, 1, 3)))
        self.assertEqual(period_id(start, 'weekly'), '2026-w53')
        self.assertEqual(bounds(date(2028, 2, 2), 'monthly')[1], date(2028, 2, 29))
        self.assertEqual(bounds(date(2026, 12, 31), 'quarterly'), (date(2026, 10, 1), date(2026, 12, 31)))

    def test_aggregate_deduplicates_and_marks_missing_days(self):
        earlier, later = daily('2026-10-12'), daily('2026-10-13')
        later['items'][0]['summary'] = '最新事实'
        report = aggregate([earlier, later], 'weekly', date(2026, 10, 12), date(2026, 10, 18), '2026-10-19T08:30:00+08:00')
        validate_report(report)
        self.assertEqual(len(report['items']), 1)
        self.assertEqual(report['items'][0]['summary'], '最新事实')
        self.assertEqual(report['coverage']['available_days'], 2)
        self.assertEqual(len(report['coverage']['missing_dates']), 5)

    def test_period_catch_up_and_idempotence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            save_report(daily('2026-09-30'), root)
            self.assertEqual(run(date(2026, 9, 30), root), [])
            paths = run(date(2026, 10, 6), root)
            self.assertEqual(len(paths), 3)  # 已结束的周、月、季；年未结束。
            self.assertEqual(run(date(2026, 10, 6), root), [])

    def test_atom_timezone_window(self):
        raw = b'''<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Fresh</title><link href="https://example.com/new"/><published>2026-10-12T00:00:00Z</published><summary>fact</summary></entry><entry><title>Old</title><link href="https://example.com/old"/><published>2026-10-01T00:00:00Z</published></entry></feed>'''
        rows = feed_items(raw, 'Test', datetime.fromisoformat('2026-10-11T08:30:00+08:00'), datetime.fromisoformat('2026-10-12T08:30:00+08:00'))
        self.assertEqual([r['title'] for r in rows], ['Fresh'])

    def test_all_sources_failed_preserves_diagnostic_and_raises(self):
        with tempfile.TemporaryDirectory() as temp, patch('src.collect.fetch', side_effect=OSError('offline')):
            output = Path(temp) / 'candidates.json'
            with self.assertRaises(RuntimeError):
                collect(datetime.fromisoformat('2026-10-12T08:30:00+08:00'), output)
            self.assertTrue(output.exists())
            self.assertTrue(all(not s['ok'] for s in json.loads(output.read_text())['source_results']))

    def test_build_escapes_news_and_links_archives(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            save_report(daily(), root / 'reports')
            build(root / 'docs', root / 'reports')
            page = (root / 'docs/reports/daily/2026-10-12.html').read_text()
            self.assertNotIn('<script>alert(1)</script>', page)
            self.assertIn('&lt;script&gt;', page)
            home = (root / 'docs/index.html').read_text()
            self.assertIn('archive/yearly.html', home)
            self.assertTrue((root / 'docs/archive/quarterly.html').exists())


if __name__ == '__main__':
    unittest.main()
