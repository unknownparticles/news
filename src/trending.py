"""每日热榜的公开数据约定；排名由官方榜单核验，不由 Star 数推算。"""
import re
from datetime import datetime
from zoneinfo import ZoneInfo

TRENDING_URL = "https://github.com/trending?since=daily"


def validate_trending(value, report):
    if report['kind'] != 'daily' or not isinstance(value, dict):
        raise ValueError('热榜快照仅属于日报')
    if value.get('source_url') != TRENDING_URL:
        raise ValueError('热榜必须来自官方全语言日榜')
    checked = datetime.fromisoformat(value['checked_at'])
    generated = datetime.fromisoformat(report['generated_at'])
    if (checked.tzinfo is None or checked > generated or
            checked.astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat() != report['period']['end']):
        raise ValueError('热榜核验时间必须属于当日报告日期且不晚于生成时间')
    items = value.get('items')
    if not isinstance(items, list) or len(items) > 10:
        raise ValueError('热榜最多十个项目')
    if len(items) < 10 and not str(value.get('coverage_note') or '').strip():
        raise ValueError('不足十个项目必须说明覆盖原因')
    seen = set()
    for rank, item in enumerate(items, 1):
        name = item.get('repository', '')
        if (not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', name)
                or name.lower() in seen or type(item.get('rank')) is not int or item['rank'] != rank):
            raise ValueError('热榜仓库必须唯一且按原始排名连续排列')
        seen.add(name.lower())
        if item.get('url') != 'https://github.com/' + name:
            raise ValueError('热榜项目链接与仓库名不一致')
        for key in ('summary', 'direction'):
            if not isinstance(item.get(key), str) or not item[key].strip():
                raise ValueError('热榜项目必须说明用途和研究方向')
        for key in ('stars_today', 'total_stars'):
            count = item.get(key)
            if count is not None and (type(count) is not int or count < 0):
                raise ValueError('Star 数必须为非负整数或未知')
    analysis = value.get('analysis')
    if (not isinstance(analysis, list) or len(analysis) > 5 or
            any(not isinstance(p, str) or not p.strip() for p in analysis) or
            (len(items) == 10 and len(analysis) < 3)):
        raise ValueError('完整热榜需要三至五段有项目依据的研究方向分析')
