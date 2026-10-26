import copy
import tempfile
import unittest
from pathlib import Path

from src.build import build
from src.common import save_report, validate_report
from src.trending import TRENDING_URL
from test_reports import daily


def snapshot():
    return {'source_url': TRENDING_URL, 'checked_at': '2026-10-12T08:20:00+08:00',
            'items': [{'rank': i, 'repository': f'example/repo-{i}',
                       'url': f'https://github.com/example/repo-{i}',
                       'summary': '<script>用途</script>', 'direction': '模型推理',
                       'stars_today': None if i == 1 else 100, 'total_stars': 1000}
                      for i in range(1, 11)],
            'analysis': ['依据 example/repo-1 观察推理方向，下一步核对基准。',
                         '依据 example/repo-2 观察工具方向，下一步阅读文档。',
                         '依据 example/repo-3 观察部署方向，下一步验证条件。']}


class TrendingTest(unittest.TestCase):
    def test_rejects_wrong_source_stale_rank_duplicates_and_bad_counts(self):
        base = daily()
        base['github_trending'] = snapshot()
        validate_report(base)
        for mutate in (
            lambda s: s.update(source_url='https://github.com/trending?since=weekly'),
            lambda s: s.update(checked_at='2026-10-11T08:20:00+08:00'),
            lambda s: s.update(checked_at='2026-10-12T08:40:00+08:00'),
            lambda s: s['items'][0].update(rank=2),
            lambda s: s['items'][1].update(repository='example/repo-1', url='https://github.com/example/repo-1'),
            lambda s: s['items'][0].update(stars_today=-1),
            lambda s: s['items'][0].update(url='https://example.com/'),
            lambda s: s.update(analysis=[]),
        ):
            report = copy.deepcopy(base)
            mutate(report['github_trending'])
            with self.assertRaises(ValueError):
                validate_report(report)

    def test_partial_and_failed_coverage_must_be_explicit(self):
        report = daily()
        report['github_trending'] = snapshot()
        for count in (0, 5):
            value = report['github_trending']
            value['items'] = snapshot()['items'][:count]
            with self.assertRaises(ValueError):
                validate_report(report)
            value['coverage_note'] = '官方页面读取不完整，未使用其他排名补齐。'
            validate_report(report)
            del value['coverage_note']

    def test_snapshot_renders_on_home_and_daily_without_changing_old_reports(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            save_report(daily('2026-10-11'), root / 'reports')
            report = daily()
            report['github_trending'] = snapshot()
            save_report(report, root / 'reports')
            build(root / 'docs', root / 'reports', {'checked_at': report['generated_at'],
                                                   'competitions': [], 'source_checks': []})
            for path in ('index.html', 'reports/daily/2026-10-12.html'):
                page = (root / 'docs' / path).read_text()
                self.assertIn('GitHub 每日热榜前十', page)
                self.assertIn('example/repo-10', page)
                self.assertIn('未知', page)
                self.assertIn('&lt;script&gt;用途', page)
                self.assertNotIn('<script>用途', page)
            self.assertNotIn('GitHub 每日热榜前十', (root / 'docs/reports/daily/2026-10-11.html').read_text())
