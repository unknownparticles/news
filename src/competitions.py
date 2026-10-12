"""国内 AI 竞赛公开候选采集与资格校验。原始候选和个人条件只保留本地。"""
import argparse
import json
import math
import re
from datetime import datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from zoneinfo import ZoneInfo

from .common import ROOT, safe_url
from .collect import fetch

SETTINGS = json.loads((ROOT / 'config/competitions.json').read_text())
CATALOG = ROOT / 'competitions/catalog.json'
TZ = ZoneInfo('Asia/Shanghai')


class PublicPage(HTMLParser):
    def __init__(self):
        super().__init__()
        self.skipped = 0
        self.parts = []
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style'}:
            self.skipped += 1
        if tag == 'a' and dict(attrs).get('href'):
            self.links.append(dict(attrs)['href'])

    def handle_endtag(self, tag):
        if tag in {'script', 'style'}:
            self.skipped = max(0, self.skipped - 1)

    def handle_data(self, value):
        if not self.skipped and value.strip():
            self.parts.append(value.strip())


def competition_state(entry, at=None):
    at = at or datetime.now(TZ)
    if entry['registration_status'] == 'closed':
        return 'closed'
    if entry.get('registration_deadline') and datetime.fromisoformat(entry['registration_deadline']) < at:
        return 'closed'
    if entry['qualification_status'] == 'excluded':
        return 'excluded'
    if entry['qualification_status'] == 'conditional' or entry['registration_status'] == 'uncertain':
        return 'conditional'
    # 赛事状态需要近期官方核验；超出七日不继续推荐报名。
    if at - datetime.fromisoformat(entry['checked_at']) > timedelta(days=7):
        return 'conditional'
    return 'eligible'


def validate_catalog(catalog):
    if set(catalog) - {'checked_at', 'competitions', 'source_checks'}:
        raise ValueError('公开竞赛库不能包含个人资料或未约定的字段')
    if datetime.fromisoformat(catalog['checked_at']).tzinfo is None:
        raise ValueError('竞赛核验时间必须包含时区')
    seen = set()
    for entry in catalog['competitions']:
        if not re.fullmatch(r'[a-z0-9-]{5,90}', entry['id']) or entry['id'] in seen:
            raise ValueError('竞赛编号错误或重复')
        seen.add(entry['id'])
        for key in ('name', 'organizer', 'platform', 'topic', 'eligibility', 'format', 'cost', 'prizes', 'first_step', 'cautions'):
            if not isinstance(entry[key], str) or not entry[key].strip():
                raise ValueError('竞赛必须包含资格、方式、费用、奖励、准备步骤和注意事项')
        if entry['qualification_status'] not in {'confirmed', 'conditional', 'excluded'}:
            raise ValueError('竞赛资格状态错误')
        if entry['registration_status'] not in {'open', 'closed', 'uncertain'}:
            raise ValueError('竞赛报名状态错误')
        if entry['kind'] not in {'prize', 'practice', 'academic'}:
            raise ValueError('竞赛类型错误')
        if entry['mode'] not in {'online', 'online_stage', 'offline_required', 'unknown'}:
            raise ValueError('竞赛参与方式错误')
        stamp = datetime.fromisoformat(entry['checked_at'])
        if stamp.tzinfo is None:
            raise ValueError('竞赛核验时间必须带时区')
        if stamp > datetime.fromisoformat(catalog['checked_at']):
            raise ValueError('单项核验时间不能晚于竞赛库更新时间')
        deadline = entry.get('registration_deadline')
        if deadline and datetime.fromisoformat(deadline).tzinfo is None:
            raise ValueError('报名截止时间必须带时区')
        if deadline and datetime.fromisoformat(deadline) < stamp and entry['registration_status'] == 'open':
            raise ValueError('报名已经截止的竞赛不能标为开放')
        if entry['qualification_status'] == 'confirmed' and not (
            entry.get('individual_allowed') is True and entry.get('non_student_allowed') is True
            and entry['mode'] in {'online', 'online_stage'} and entry.get('rules_consistent') is True
        ):
            raise ValueError('推荐竞赛需要单人、社会人士、线上阶段和一致规则证据')
        for key in ('url', 'registration_url'):
            safe_url(entry[key])
            if urlsplit(entry[key]).hostname not in SETTINGS['official_domains']:
                raise ValueError('竞赛入口必须来自已配置的官方平台')
        if not entry['evidence']:
            raise ValueError('竞赛资格必须有原文证据')
        for evidence in entry['evidence']:
            safe_url(evidence['url'])
            if urlsplit(evidence['url']).hostname not in SETTINGS['official_domains'] or not evidence['excerpt'].strip():
                raise ValueError('竞赛证据必须来自官方规则')
        if any(key in entry for key in ('profile', 'age', 'employment', 'personal_conditions', 'user')):
            raise ValueError('公开赛题不得包含用户个人资料')
    return catalog


def load_catalog(path=CATALOG):
    if not path.exists():
        return {'checked_at': datetime.now(TZ).isoformat(), 'competitions': [], 'source_checks': []}
    return validate_catalog(json.loads(path.read_text()))


def discover(output=ROOT / '.local/competition-candidates.json'):
    result = {'checked_at': datetime.now(TZ).isoformat(), 'candidates': [], 'source_checks': []}
    directory = output.parent / 'competition-pages'
    directory.mkdir(parents=True, exist_ok=True)
    for source in SETTINGS['sources']:
        try:
            if source['adapter'] == 'tianchi':
                records = {}
                total_pages = 1
                page = 1
                # 页面的 hasNextPage 不可靠，使用 total/pageSize 计算并设请求上限。
                while page <= min(total_pages, 10):
                    url = 'https://tianchi.aliyun.com/v3/proxy/competition/api/race/page?visualTab=&raceName=&isActive=1&pageNum=' + str(page)
                    data = json.loads(fetch(url))['data']
                    total_pages = math.ceil(data['total'] / (data.get('pageSize') or 10))
                    for record in data['list']:
                        for entry in record.get('trackList') or [record]:
                            if entry.get('raceId'):
                                records[entry['raceId']] = entry
                    page += 1
                detail_failures = []
                for entry in list(records.values())[:SETTINGS['max_detail_requests']]:
                    identity = entry['raceId']
                    try:
                        detail = json.loads(fetch('https://tianchi.aliyun.com/v3/proxy/competition/api/race/getDetail?raceId=' + str(identity)))
                        race = detail['data']['race']
                    except Exception as exc:
                        detail_failures.append({'race_id': identity, 'error': type(exc).__name__})
                        continue
                    # 报名协议和个人接口字段不进入候选，不抓取账户、团队成员或报名信息。
                    result['candidates'].append({'platform': source['name'], 'url': 'https://tianchi.aliyun.com/competition/entrance/' + str(identity),
                        'race_id': identity, 'name': race.get('name'), 'registration_start': race.get('signupStartTime'),
                        'registration_end': race.get('signupEndTime'), 'race_end': race.get('raceEndTime'),
                        'platform_status': race.get('raceListStatus'), 'introduction': race.get('introduction', ''),
                        'task': race.get('information', ''), 'requires_rule_and_phase_check': True})
                result['source_checks'].append({'name': source['name'], 'url': source['url'], 'status': 'collected', 'count': len(records), 'detail_failures': detail_failures})
            else:
                body = fetch(source['url']).decode('utf-8', errors='replace')
                parsed = PublicPage()
                parsed.feed(body)
                name = re.sub(r'[^a-z0-9]', '-', urlsplit(source['url']).hostname)
                (directory / (name + '.txt')).write_text('\n'.join(parsed.parts))
                links = list(dict.fromkeys(urljoin(source['url'], link) for link in parsed.links if re.search(r'competition|challenge|contest', link)))
                result['candidates'].append({'platform': source['name'], 'url': source['url'], 'text': '\n'.join(parsed.parts)[:100000], 'detail_links': links, 'requires_browser': source['adapter'] == 'browser'})
                result['source_checks'].append({'name': source['name'], 'url': source['url'], 'status': 'browser_required' if source['adapter'] == 'browser' else 'listing_only', 'count': len(links)})
        except Exception as exc:
            result['source_checks'].append({'name': source['name'], 'url': source['url'], 'status': 'failed', 'error': type(exc).__name__})
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--discover', action='store_true')
    args = parser.parse_args()
    if args.discover:
        result = discover()
        print(json.dumps({'candidates': len(result['candidates']), 'source_checks': result['source_checks']}, ensure_ascii=False, indent=2))
    else:
        catalog = load_catalog()
        print(json.dumps({'competitions': len(catalog['competitions']), 'eligible': sum(competition_state(c) == 'eligible' for c in catalog['competitions'])}, ensure_ascii=False))
