import copy
import gzip
import io
import json
import tempfile
import unittest
import zlib
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

from src.common import canonical_url, save_report, validate_report
from src.collect import collect, feed_items, fetch
from src.periods import aggregate, bounds, period_id, run
from src.build import build, opportunity_state
from src.competitions import competition_state, validate_catalog


def daily(day="2026-10-12", identity="event-12345678"):
    return {"id": day, "kind": "daily", "title": day + " · 日报", "period": {"start": day, "end": day},
            "generated_at": day + "T08:30:00+08:00", "summary": "测试报告，不发布",
            "coverage": {"expected_days": 1, "available_days": 1, "missing_dates": []},
            "items": [{"event_id": identity, "headline": "<script>alert(1)</script>", "summary": "已核对事实",
                       "category": "AI 编程", "verification_status": "official_confirmed", "score": 80,
                       "relevance": "开发效率", "action": "检查更新",
                       "sources": [{"label": "公告", "url": "https://openai.com/index/example", "excerpt": "事实摘录", "checked_at": day + "T08:20:00+08:00"}]}]}


def opportunity():
    return {"opportunity_id": "opportunity-12345678", "headline": "测试机会", "signal": "公开发布信号",
            "audience": "开发者", "first_step": "验证原型", "risks": "需求尚未验证", "time_window": "本周",
            "category": "AI 编程", "status": "research", "score": 80, "verification_status": "official_confirmed",
            "sources": copy.deepcopy(daily()['items'][0]['sources'])}


def competition():
    return {'id':'tianchi-test','name':'测试竞赛','organizer':'测试组织方','platform':'天池','topic':'AI 测试赛题',
            'eligibility':'社会人士单人','format':'线上','cost':'资源成本待核对','prizes':'无承诺','first_step':'阅读规则','cautions':'测试记录，不发布',
            'qualification_status':'confirmed','registration_status':'open','kind':'practice','mode':'online',
            'individual_allowed':True,'non_student_allowed':True,'rules_consistent':True,
            'checked_at':'2026-10-12T08:30:00+08:00','registration_deadline':'2026-10-20T23:59:59+08:00',
            'url':'https://tianchi.aliyun.com/competition/entrance/1','registration_url':'https://tianchi.aliyun.com/competition/entrance/1',
            'evidence':[{'url':'https://tianchi.aliyun.com/competition/entrance/1','excerpt':'面向社会人士、允许单人、线上提交'}]}


class ReportsTest(unittest.TestCase):
    def test_fetch_decompresses_rss_before_xml_parsing(self):
        xml = b'<rss><channel><title>DeepMind</title></channel></rss>'
        for encoding, raw in [('gzip', gzip.compress(xml)), ('', gzip.compress(xml)), ('deflate', zlib.compress(xml))]:
            with self.subTest(encoding=encoding):
                response = io.BytesIO(raw)
                response.headers = {'Content-Encoding': encoding}
                with patch('src.collect.urllib.request.urlopen', return_value=response):
                    decoded = fetch('https://deepmind.google/blog/rss.xml')
                self.assertEqual(decoded, xml)
                self.assertEqual(feed_items(decoded, 'DeepMind', datetime.fromisoformat('2026-10-11T00:00:00+08:00'), datetime.fromisoformat('2026-10-12T00:00:00+08:00')), [])

    def test_fetch_limits_decompressed_size_and_rejects_html(self):
        response = io.BytesIO(gzip.compress(b'x' * 3_000_001))
        response.headers = {'Content-Encoding': 'gzip'}
        with patch('src.collect.urllib.request.urlopen', return_value=response), self.assertRaises(ValueError):
            fetch('https://example.com/feed')
        with self.assertRaises(ValueError):
            feed_items(b'<html><body>not a feed</body></html>', 'Test', datetime.fromisoformat('2026-10-11T00:00:00+08:00'), datetime.fromisoformat('2026-10-12T00:00:00+08:00'))

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

    def test_frontier_dates_and_opportunity_evidence_are_required(self):
        report = daily()
        item = report['items'][0]
        item['category'] = '科技前沿'
        item['published_at'] = '2026-10-13T00:00:00+08:00'
        with self.assertRaises(ValueError):
            validate_report(report)
        item['published_at'] = '2026-10-06T00:00:00+08:00'
        with self.assertRaises(ValueError):
            validate_report(report)
        item['context_note'] = '近期重要前沿回看，非今日发布'
        validate_report(report)
        report['opportunities'] = [opportunity()]
        report['opportunities'][0]['first_step'] = ''
        with self.assertRaises(ValueError):
            validate_report(report)
        report['opportunities'] = [opportunity()]
        report['opportunities'][0]['sources'] = []
        with self.assertRaises(ValueError):
            validate_report(report)

    def test_each_news_domain_has_independent_capacity(self):
        report = daily()
        item = report['items'][0]
        report['items'] = []
        for category in ['科技前沿','金融市场','政治与政策']:
            for i in range(5):
                row = copy.deepcopy(item)
                row.update(category=category,event_id=f'event-{len(report["items"]):08d}',published_at='2026-10-12T07:00:00+08:00')
                report['items'].append(row)
        validate_report(report)
        report['items'][5]['category'] = '科技前沿'
        with self.assertRaises(ValueError):
            validate_report(report)

    def test_competition_qualification_requires_confirmed_rules(self):
        entry = competition()
        catalog = {'checked_at':entry['checked_at'],'competitions':[entry],'source_checks':[]}
        validate_catalog(catalog)
        for field,value in [('individual_allowed',False),('non_student_allowed',False),('mode','offline_required'),('rules_consistent',False)]:
            with self.subTest(field=field):
                altered=copy.deepcopy(catalog);altered['competitions'][0][field]=value
                with self.assertRaises(ValueError):validate_catalog(altered)
        catalog['profile']={'private':True}
        with self.assertRaises(ValueError):validate_catalog(catalog)

    def test_competition_expiry_conflict_and_stale_checks(self):
        entry=competition();at=datetime.fromisoformat('2026-10-12T09:00:00+08:00')
        self.assertEqual(competition_state(entry,at),'eligible')
        self.assertEqual(competition_state(dict(entry,registration_status='uncertain'),at),'conditional')
        self.assertEqual(competition_state(dict(entry,qualification_status='excluded'),at),'excluded')
        self.assertEqual(competition_state(entry,datetime.fromisoformat('2026-10-21T00:00:00+08:00')),'closed')
        self.assertEqual(competition_state(entry,datetime.fromisoformat('2026-10-20T08:31:00+08:00')),'conditional')

    def test_period_opportunities_preserve_latest_and_close_expired_window(self):
        earlier, later = daily('2026-10-12'), daily('2026-10-13')
        earlier['opportunities'] = [opportunity()]
        later['opportunities'] = [dict(opportunity(), first_step='更新后的验证步骤', deadline='2026-10-14T23:59:00+08:00')]
        report = aggregate([earlier, later], 'weekly', date(2026, 10, 12), date(2026, 10, 18), '2026-10-19T08:30:00+08:00')
        validate_report(report)
        self.assertEqual(len(report['opportunities']), 1)
        self.assertEqual(report['opportunities'][0]['first_step'], '更新后的验证步骤')
        self.assertEqual(report['opportunities'][0]['status'], 'closed')

    def test_archive_does_not_promote_expired_opportunity(self):
        entry = dict(opportunity(), deadline='2026-10-14T23:59:00+08:00')
        self.assertEqual(opportunity_state(entry, datetime.fromisoformat('2026-10-15T08:30:00+08:00')), 'closed')
        self.assertEqual(opportunity_state(entry, datetime.fromisoformat('2026-10-13T08:30:00+08:00')), 'research')

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
            report = daily()
            report['opportunities'] = [opportunity()]
            save_report(report, root / 'reports')
            build(root / 'docs', root / 'reports', {'checked_at':'2026-10-12T08:30:00+08:00','competitions':[competition()],'source_checks':[]})
            page = (root / 'docs/reports/daily/2026-10-12.html').read_text()
            self.assertNotIn('<script>alert(1)</script>', page)
            self.assertIn('&lt;script&gt;', page)
            self.assertLess(page.index('阅读原文 · 公告'), page.index('<details>'))
            self.assertIn('opportunity-opportunity-12345678', page)
            home = (root / 'docs/index.html').read_text()
            self.assertIn('archive/yearly.html', home)
            self.assertIn('id="latest-news"', home)
            self.assertIn('id="opportunities"', home)
            self.assertTrue((root / 'docs/archive/opportunities.html').exists())
            self.assertTrue((root / 'docs/archive/quarterly.html').exists())
            self.assertTrue((root / 'docs/archive/competitions.html').exists())
            self.assertIn('官方报名与规则', (root / 'docs/archive/competitions.html').read_text())


if __name__ == '__main__':
    unittest.main()
