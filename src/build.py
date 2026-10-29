"""从公开 JSON 报告生成 GitHub Pages 站点。"""
import html
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .common import CONFIG, KINDS, NEWS_DOMAINS, ROOT, STATUSES, load_reports, news_domain
from .competitions import competition_state, load_catalog

SITE_URL = os.environ.get("SITE_URL", "https://alunapp.cn/news/").replace("http://", "https://", 1).rstrip("/") + "/"


def esc(text):
    return html.escape(str(text), quote=True)


def report_url(report):
    return f"reports/{report['kind']}/{report['id']}.html"


def news_url(item, report):
    return f"articles/{report['kind']}-{report['id']}-{item['event_id']}.html"


def opportunity_url(opportunity, report):
    return f"opportunities/{report['kind']}-{report['id']}-{opportunity['opportunity_id']}.html"


def competition_url(entry):
    return f"competitions/{entry['id']}.html"


def brief(value, length=65):
    # 首页优先使用编辑后的短摘要，旧报告兼容首句摘要。
    sentence = value.split('。')[0].strip()
    return sentence if len(sentence) <= length else sentence[:length].rstrip('，、；： ') + '…'


def frame(title, body, prefix="", reports=None):
    nav = f'<a href="{prefix}index.html#latest-news">新闻速览</a><a href="{prefix}index.html#github-trending">开源热榜</a><a href="{prefix}index.html#opportunities">机会观察</a><a href="{prefix}archive/competitions.html">AI 竞赛</a><details class="nav-archive"><summary>历史报告</summary><div>' + ''.join(f'<a href="{prefix}archive/{kind}.html">{label}归档</a>' for kind, label in KINDS.items()) + '</div></details>'
    return f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="科技前沿、金融市场、政治政策与近期机会，每条内容保留原文、证据、影响和行动建议。">
<title>{esc(title)} · 情报观察室</title><link rel="stylesheet" href="{prefix}styles.css"></head>
<body><a class="skip-link" href="#main-content">跳到正文</a><header class="site-header"><a class="brand" href="{prefix}index.html"><span class="brand-mark" aria-hidden="true"><i></i><i></i><i></i></span><span>情报观察室<small>THE DAILY BRIEF</small></span></a>
<nav aria-label="报告导航">{nav}<a class="github" href="https://github.com/unknownparticles/news">GitHub ↗</a></nav></header>
<main id="main-content">{body}</main><footer><span>情报观察室 · 公开来源，可追溯的判断。</span><span>北京时间 · <a href="{prefix}archive/daily.html">历史归档</a> · <a href="https://github.com/unknownparticles/news">项目与纠错 ↗</a></span></footer>
<script src="{prefix}app.js" defer></script></body></html>'''


def card(report, prefix=""):
    coverage = report["coverage"]
    partial = coverage["available_days"] < coverage["expected_days"]
    text = f"覆盖 {coverage['available_days']}/{coverage['expected_days']} 天" if partial else "日期覆盖完整"
    return f'''<a class="report-card" href="{prefix}{report_url(report)}" data-kind="{report['kind']}" data-search="{esc(report['title'] + ' ' + report['summary'] + ' ' + ' '.join(i['headline'] for i in report['items'] + report.get('opportunities', [])))}">
<div class="card-top"><span class="type-label">{KINDS[report['kind']]}</span><span class="coverage {'partial' if partial else ''}">{text}</span></div>
<h3>{esc(report['title'])}</h3><p>{esc(brief(report['summary']))}</p>
<div class="card-bottom"><span>{esc(report['period']['start'])} — {esc(report['period']['end'])}</span><span>{len(report['items'])} 条新闻 · {len(report.get('opportunities', []))} 个机会 <b>↗</b></span></div></a>'''


def time_label(value, include_year=False):
    if not value:
        return "发布时间未记录"
    pattern = '%Y-%m-%d %H:%M' if include_year else '%m-%d %H:%M'
    return datetime.fromisoformat(value).astimezone(ZoneInfo('Asia/Shanghai')).strftime(pattern) + ' 北京时间'


def original_links(entry):
    return '<div class="original-links" aria-label="原文链接">' + ''.join(f'<a href="{esc(source["url"])}" target="_blank" rel="noopener noreferrer">阅读原文 · {esc(source["label"])} ↗</a>' for source in entry['sources']) + '</div>'


def news_group(category):
    return news_domain(category)


def competition_card(entry):
    state = competition_state(entry)
    labels = {'eligible': '符合个人线上参赛条件', 'conditional': '时间或资格需核对', 'excluded': '不符合当前筛选条件', 'closed': '新报名已截止'}
    kind = {'prize': '奖励赛事', 'practice': '长期练习 / 打榜', 'academic': '学术评测'}[entry['kind']]
    deadline = time_label(entry.get('registration_deadline'), True) if entry.get('registration_deadline') else '截止时间待核对'
    evidence = ''.join(f'<li><a href="{esc(e["url"])}" target="_blank" rel="noopener noreferrer">官方规则 ↗</a><blockquote>{esc(e["excerpt"])}</blockquote></li>' for e in entry['evidence'])
    return f'''<article class="competition-card" id="competition-{entry['id']}" data-competition-state="{state}" data-deadline="{esc(entry.get('registration_deadline') or '')}" data-checked="{esc(entry['checked_at'])}" data-search="{esc(entry['name'] + ' ' + entry['topic'] + ' ' + entry['platform'])}">
<div class="item-meta"><span>{esc(entry['platform'])} · {kind}</span><span class="competition-status status">{labels[state]}</span></div><h3>{esc(entry['name'])}</h3>
<p class="competition-topic">{esc(entry['topic'])}</p><p class="competition-deadline">报名截止：{esc(deadline)}</p><p class="detail-organizer">主办方：{esc(entry['organizer'])}</p>
<dl><dt>参赛条件</dt><dd>{esc(entry['eligibility'])}</dd><dt>参与方式</dt><dd>{esc(entry['format'])}</dd><dt>费用与算力</dt><dd>{esc(entry['cost'])}</dd><dt>奖励</dt><dd>{esc(entry['prizes'])}</dd><dt>先做什么</dt><dd>{esc(entry['first_step'])}</dd></dl>
<p class="competition-caution">{esc(entry['cautions'])}</p><div class="original-links"><a href="{esc(entry['registration_url'])}" target="_blank" rel="noopener noreferrer">官方报名与规则 ↗</a></div><details><summary>资格与日期证据 · 核验于 {esc(time_label(entry['checked_at']))}</summary><ul class="evidence">{evidence}</ul></details></article>'''


def competition_table(entries, prefix=''):
    labels = {'eligible': '可参与', 'conditional': '需确认', 'excluded': '不符合', 'closed': '已截止'}
    kinds = {'prize': '奖励赛', 'practice': '练习赛', 'academic': '学术赛'}
    modes = {'online': '线上', 'online_stage': '线上阶段', 'offline_required': '含线下', 'unknown': '待确认'}
    rows = []
    for entry in entries:
        state = competition_state(entry)
        date = datetime.fromisoformat(entry['registration_deadline']).astimezone(ZoneInfo('Asia/Shanghai')).strftime('%Y-%m-%d') if entry.get('registration_deadline') else '待确认'
        if entry['registration_status'] == 'uncertain' and not entry['rules_consistent']:
            date = '时间待确认'
        rows.append(f'''<tr role="row" data-competition-state="{state}" data-deadline="{esc(entry.get('registration_deadline') or '')}" data-checked="{esc(entry['checked_at'])}" data-search="{esc(entry['name'] + ' ' + entry['topic'] + ' ' + entry['platform'])}">
<th scope="row" role="rowheader"><a href="{prefix}{competition_url(entry)}">{esc(entry.get('short_name') or entry['name'])}</a><small>{esc(entry['platform'])}</small></th>
<td role="cell" data-label="状态"><span class="competition-status status" data-state="{state}">{labels[state]}</span></td><td role="cell" data-label="报名截止" class="date-cell">{date}</td><td role="cell" data-label="赛制">{kinds[entry['kind']]}</td><td role="cell" data-label="参与方式">{modes[entry['mode']]}</td>
<td role="cell" data-label="费用 / 算力">{esc(entry.get('cost_brief') or brief(entry['cost'], 25))}</td><td role="cell" data-label="奖励">{esc(entry.get('prize_brief') or brief(entry['prizes'], 25))}</td><td role="cell" data-label="详情"><a class="table-details" href="{prefix}{competition_url(entry)}" aria-label="查看规则：{esc(entry.get('short_name') or entry['name'])}">查看规则 →</a></td></tr>''')
    return '<div class="table-scroll" tabindex="0" aria-label="竞赛比较表，窄屏按赛题展示"><table class="competition-table"><caption>AI 竞赛速览</caption><thead role="rowgroup"><tr role="row"><th scope="col" role="columnheader">赛题</th><th scope="col" role="columnheader">状态</th><th scope="col" role="columnheader">报名截止</th><th scope="col" role="columnheader">类型</th><th scope="col" role="columnheader">方式</th><th scope="col" role="columnheader">费用 / 算力</th><th scope="col" role="columnheader">奖励</th><th scope="col" role="columnheader">详情</th></tr></thead><tbody role="rowgroup">' + ''.join(rows) + '</tbody></table></div>'


def trending_html(report):
    value = report.get('github_trending') if report else None
    if value is None:
        return ''
    def stars(count):
        return '未知' if count is None else f'{count:,}'
    rows = ''.join(f'''<tr><td>{item['rank']}</td><th scope="row"><a href="{esc(item['url'])}" target="_blank" rel="noopener noreferrer">{esc(item['repository'])} ↗</a><small>{esc(item['summary'])}</small></th><td>{esc(item['direction'])}</td><td>{stars(item.get('stars_today'))}</td><td>{stars(item.get('total_stars'))}</td></tr>''' for item in value['items'])
    note = f'<p class="coverage-warning">{esc(value["coverage_note"])}</p>' if value.get('coverage_note') else ''
    analysis = ''.join(f'<p>{esc(p)}</p>' for p in value['analysis'])
    return f'''<section id="github-trending" class="opportunities-section trending-section"><div class="section-heading"><h2>GitHub 每日热榜前十</h2><a href="{esc(value['source_url'])}" target="_blank" rel="noopener noreferrer">官方日榜 ↗</a></div><p class="compact-note">全语言榜单 · 核验于 {esc(time_label(value['checked_at'], True))} · 排名反映近期关注度，上榜不代表新发布、研究质量或商业许可。</p>{note}<p class="table-hint">窄屏可左右滑动，查看完整项目与关注度数据 →</p><div class="table-scroll" tabindex="0" aria-label="GitHub 热榜，可左右滚动"><table class="competition-table trending-table"><caption>当日关注项目 · {len(value['items'])} / 10</caption><thead><tr><th scope="col">排名</th><th scope="col">项目与用途</th><th scope="col">研究方向</th><th scope="col">今日新增 Star</th><th scope="col">总 Star</th></tr></thead><tbody>{rows}</tbody></table></div><h3>值得关注的研究方向</h3><div class="trending-analysis">{analysis}</div></section>'''


def headline_card(item, report, number, prefix=''):
    return f'''<article class="headline-card" data-news-category="{news_group(item['category'])}">
<span class="story-number" aria-hidden="true">{number:02d}</span><div class="story-body"><div class="item-meta"><span class="status" data-status="{item['verification_status']}">{STATUSES[item['verification_status']]}</span>{'<span class="context-tag">近期回看</span>' if item.get('context_note') else ''}</div>
<h3><a href="{prefix}{news_url(item, report)}">{esc(item.get('short_headline') or item['headline'])}</a></h3>
<p>{esc(item.get('short_summary') or brief(item['summary']))}</p><div class="teaser-bottom"><small>{esc(time_label(item.get('published_at')))}</small><div><a class="source-link" href="{esc(item['sources'][0]['url'])}" target="_blank" rel="noopener noreferrer">{esc(item['sources'][0]['label'])} ↗</a><a href="{prefix}{news_url(item, report)}" aria-label="阅读全文：{esc(item['headline'])}">深入阅读 →</a></div></div></div></article>'''


def featured_news(report):
    if not report or not report['items']:
        return ''
    selected = []
    for domain in NEWS_DOMAINS:
        entries = [item for item in report['items'] if news_group(item['category']) == domain]
        if entries:
            selected.append(max(entries, key=lambda item: item['score']))
    cards = []
    for index, item in enumerate(selected):
        link = news_url(item, report)
        cards.append(f'''<article class="feature-card {'feature-lead' if index == 0 else ''}">
<div class="feature-meta"><span>{esc(item['category'])}</span><span>{STATUSES[item['verification_status']]}</span></div>
<h3><a href="{link}">{esc(item.get('short_headline') or item['headline'])}</a></h3><p>{esc(item.get('short_summary') or brief(item['summary']))}</p>
<div class="feature-bottom"><span>{esc(time_label(item.get('published_at')))}{' · 近期回看' if item.get('context_note') else ''}</span><a href="{link}" aria-label="重点全文：{esc(item['headline'])}">阅读分析 <span aria-hidden="true">↗</span></a></div></article>''')
    return '<section class="featured-section" aria-labelledby="featured-title"><div class="section-heading"><h2 id="featured-title"><span class="accent-dot" aria-hidden="true"></span>本期重点</h2><span class="section-note">每个领域，先看一条</span></div><div class="feature-grid">' + ''.join(cards) + '</div></section>'


def opportunity_state(opportunity, at=None):
    at = at or datetime.now(ZoneInfo('Asia/Shanghai'))
    if opportunity.get('deadline') and datetime.fromisoformat(opportunity['deadline']) < at:
        return 'closed'
    return opportunity['status']


def opportunity_card(opportunity, report, prefix=''):
    labels = {'research': '待验证机会', 'actionable': '可开始验证', 'closed': '窗口已结束'}
    return f'''<article class="opportunity-card"><div class="item-meta"><span>{esc(opportunity['category'])}</span><span class="status" data-opportunity-state="{opportunity_state(opportunity)}">{labels[opportunity_state(opportunity)]}</span></div>
<h3><a href="{prefix}{opportunity_url(opportunity, report)}">{esc(opportunity.get('short_headline') or opportunity['headline'])}</a></h3>
<p>{esc(opportunity.get('short_summary') or brief(opportunity['signal']))}</p><div class="teaser-bottom"><small>{esc(report['period']['end'])}</small><a href="{prefix}{opportunity_url(opportunity, report)}">查看验证方案 →</a></div></article>'''


def opportunity_html(opportunity, prefix=''):
    labels = {'research': '待验证机会', 'actionable': '可开始验证', 'closed': '窗口已结束'}
    sources = ''.join(f'<li><a href="{esc(s["url"])}" target="_blank" rel="noopener noreferrer">{esc(s["label"])} ↗</a><blockquote>{esc(s["excerpt"])}</blockquote><small>核验于 {esc(time_label(s["checked_at"]))}</small></li>' for s in opportunity['sources'])
    backlink = f'<a href="{prefix}reports/daily/{esc(opportunity["daily_report"])}.html">查看收录日报 →</a>' if opportunity.get('daily_report') else ''
    return f'''<article class="opportunity-detail" id="opportunity-{opportunity['opportunity_id']}"><div class="item-meta"><span>{esc(opportunity['category'])}</span><span class="status" data-opportunity-state="{opportunity_state(opportunity)}">{labels[opportunity_state(opportunity)]}</span><span>证据信号：{STATUSES[opportunity['verification_status']]}</span></div>
<h3>{esc(opportunity['headline'])}</h3><p>{esc(opportunity['signal'])}</p>{original_links(opportunity)}
<dl><dt>适合谁</dt><dd>{esc(opportunity['audience'])}</dd><dt>第一步</dt><dd>{esc(opportunity['first_step'])}</dd><dt>窗口</dt><dd>{esc(opportunity['time_window'])}</dd><dt>风险与不确定性</dt><dd>{esc(opportunity['risks'])}</dd></dl>
<details><summary>支持信号的原文摘录</summary><ul class="evidence">{sources}</ul></details>{backlink}</article>'''


def item_html(item, number, prefix="", daily=False):
    sources = ''.join(f'<li><a href="{esc(s["url"])}" target="_blank" rel="noopener noreferrer">{esc(s["label"])} ↗</a><blockquote>{esc(s["excerpt"])}</blockquote><small>核验于 {esc(s["checked_at"])}</small></li>' for s in item['sources'])
    note = f'<p class="update">更新说明：{esc(item["update_reason"])}</p>' if item.get("update_reason") else ''
    license_note = ''
    if item.get("commercial_status"):
        labels = {"eligible": "许可证证据已提供，商用前仍需核查依赖与权重", "unknown": "商业许可待核查", "restricted": "商业使用存在限制"}
        license_note = f'<p class="license-note">{esc(labels.get(item["commercial_status"], "商业许可待核查"))}</p>'
        if item.get("license_evidence"):
            license_note += f'<a href="{esc(item["license_evidence"])}" target="_blank" rel="noopener noreferrer">许可证证据 ↗</a>'
    backlink = f'<p><a href="{prefix}reports/daily/{esc(item["daily_report"])}.html">查看收录日报 →</a></p>' if item.get("daily_report") else ''
    return f'''<article class="news-item" id="item-{number}"><div class="item-number">{number:02d}</div><div class="item-content">
<div class="item-meta"><span>{esc(item['category'])}</span><span class="status">{STATUSES[item['verification_status']]}</span><span>相关度 {item['score']}</span></div>
<h2>{esc(item['headline'])}</h2><p>{esc(item['summary'])}</p>{note}
<p class="published-at">原文发布：{esc(time_label(item.get('published_at')))}</p>
{f'<p class="context-note">{esc(item["context_note"])}</p>' if item.get('context_note') else ''}{original_links(item)}
<div class="analysis"><div><h4>为什么值得关注</h4><p>{esc(item['relevance'])}</p></div><div><h4>下一步</h4><p>{esc(item['action'])}</p></div></div>
{license_note}<details><summary>证据摘录与核验时间 · {len(item['sources'])} 个</summary><ul class="evidence">{sources}</ul></details>{backlink}</div></article>'''


def build(output=ROOT / "docs", report_root=ROOT / "reports", competition_catalog=None):
    reports = load_reports(report_root)
    catalog = load_catalog() if competition_catalog is None else competition_catalog
    output.mkdir(parents=True, exist_ok=True)
    for asset in (ROOT / 'web').iterdir():
        if asset.is_file():
            shutil.copyfile(asset, output / asset.name)
    (output / '.nojekyll').write_text('')
    generated = []

    def write(path, title, body, prefix=''):
        target = output / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(frame(title, body, prefix))
        generated.append(path)

    def news_digest(reports_to_show, prefix=''):
        blocks = []
        for domain, label in NEWS_DOMAINS.items():
            entries = [(item, report, i) for report in reports_to_show for i, item in enumerate(report['items'], 1) if news_domain(item['category']) == domain]
            cards = ''.join(headline_card(item, report, i, prefix) for item, report, i in entries)
            blocks.append(f'<section class="news-domain" id="{domain}" data-domain="{domain}"><div class="domain-heading"><h3>{label}</h3><small>{len(entries):02d} 条新闻</small></div>{cards or "<p class=empty>本期暂无通过筛选的新闻。</p>"}</section>')
        return '<div class="news-digest">' + ''.join(blocks) + '</div>'

    latest_daily = next((r for r in reports if r['kind'] == 'daily'), None)
    date = latest_daily['period']['end'] if latest_daily else '准备中'
    eligible = [c for c in catalog['competitions'] if competition_state(c) == 'eligible']
    report_filters = '<button class="filter active" data-filter="all" aria-pressed="true">全部</button>' + ''.join(f'<button class="filter" data-filter="{kind}" aria-pressed="false">{label}</button>' for kind, label in KINDS.items())
    edition_date = datetime.fromisoformat(date) if latest_daily else None
    date_title = edition_date.strftime('%m 月 %d 日') if edition_date else '准备中'
    weekday = '星期' + '一二三四五六日'[edition_date.weekday()] if edition_date else ''
    updated = time_label(latest_daily['generated_at']) if latest_daily else '等待首期日报'
    trending_stat = f'<a href="#github-trending"><b>{len(latest_daily["github_trending"]["items"])}</b> 个热榜项目 ↓</a>' if latest_daily and latest_daily.get("github_trending") else ""
    edition = f'''<section class="brief-intro"><div><span class="eyebrow">DAILY INTELLIGENCE / 每日简报</span><h1>每天，读懂重要变化<span>。</span></h1><p>从科技、金融与政策，到值得验证的下一步。</p><div class="edition-stats"><a href="#latest-news"><b>{len(latest_daily['items']) if latest_daily else 0}</b> 条新闻 ↓</a>{trending_stat}<a href="#opportunities"><b>{len(latest_daily.get('opportunities', [])) if latest_daily else 0}</b> 个机会 ↓</a><a href="#competitions"><b>{len(eligible)}</b> 项个人线上竞赛 ↓</a></div></div>
<div class="edition-date"><span>{edition_date.year if edition_date else 'DAILY'} / 本期日报</span><strong>{date_title}</strong><small>{weekday} · 北京时间</small><a href="{report_url(latest_daily) if latest_daily else '#archive'}">阅读完整日报 <span aria-hidden="true">↗</span></a></div></section>'''
    opportunity_cards = ''.join(opportunity_card(o, latest_daily) for o in latest_daily.get('opportunities', [])) if latest_daily else ''
    news_filters = '<button class="filter active" data-domain-filter="all" aria-pressed="true">全部领域</button>' + ''.join(f'<button class="filter" data-domain-filter="{domain}" aria-pressed="false">{label}</button>' for domain, label in NEWS_DOMAINS.items())
    body = edition + featured_news(latest_daily) + '<div class="reading-layout"><section id="latest-news" class="frontier-section"><div class="section-heading"><h2>新闻速览</h2><a href="archive/news.html">新闻归档 ↗</a></div><div class="news-filters" aria-label="按新闻领域筛选">' + news_filters + '</div><p id="news-result-count" class="results-meta" aria-live="polite"></p>' + news_digest([latest_daily] if latest_daily else []) + '</section>'
    trending_guide = '<a href="#github-trending"><span>↗</span><div>开源热榜<small>项目用途与研究方向</small></div><b>↓</b></a>' if latest_daily and latest_daily.get('github_trending') else ''
    body += f'''<aside class="reading-rail"><div class="rail-card"><span class="eyebrow">IN THIS EDITION</span><h2>本期阅读指南</h2>{trending_guide}<a href="#latest-news"><span>01</span><div>新闻速览<small>科技 / 金融 / 政策</small></div><b>↓</b></a><a href="#opportunities"><span>02</span><div>机会观察<small>从变化信号到验证方向</small></div><b>↓</b></a><a href="#competitions"><span>03</span><div>AI 竞赛<small>资格、截止日与奖励比较</small></div><b>↓</b></a><a href="#archive"><span>04</span><div>历史报告<small>日报 / 周报 / 月报 / 季报 / 年报</small></div><b>↓</b></a></div><div class="rail-note"><span class="accent-dot" aria-hidden="true"></span><h3>信息有出处，判断有边界。</h3><p>每条新闻保留原文与核验标记。近期回看单独注明，机会先验证需求。</p><small>本期更新于 {esc(updated)}</small><a href="{report_url(latest_daily) if latest_daily else '#archive'}">查看本期筛选说明 →</a></div></aside></div>'''
    body += trending_html(latest_daily)
    body += f'''<section id="opportunities" class="opportunities-section"><div class="section-heading"><h2>机会观察</h2><a href="archive/opportunities.html">全部机会 →</a></div><div class="opportunity-grid">{opportunity_cards or '<p class="empty">本期暂无新机会。</p>'}</div></section>
<section id="competitions" class="competitions-section"><div class="section-heading"><h2>AI 竞赛</h2><a href="archive/competitions.html">全部 {len(catalog['competitions'])} 项 / 筛选 →</a></div><p class="compact-note">个人、社会人士、线上可参与 · 截止日期与参赛条件已核验，详细限制请点赛题查看。</p>{competition_table(eligible[:6]) if eligible else '<p class="empty">暂无已核验符合条件的赛事。</p>'}</section>
<section id="archive" class="archive-section"><div class="section-heading"><h2>报告归档</h2><label class="search-label"><span>搜索报告</span><input id="report-search" type="search" placeholder="搜索报告…"></label></div><div class="filters">{report_filters}<span id="result-count" aria-live="polite"></span></div><div class="report-grid">{''.join(card(r) for r in reports) or '<p class="empty">暂无报告。</p>'}</div><div id="no-results" class="empty" hidden>没有匹配的报告。<button class="reset-filter" data-reset-reports>清除搜索与筛选</button></div></section>'''
    write('index.html', '主页', body)
    for kind, label in KINDS.items():
        subset = [r for r in reports if r['kind'] == kind]
        timing = {'daily': '每日早晨更新', 'weekly': '每周一汇总上一自然周', 'monthly': '每月首日汇总上月', 'quarterly': '每季首日汇总上一季度', 'yearly': '每年首日汇总上一年'}[kind]
        body = f'<section class="archive-hero"><a class="back" href="../index.html">← 返回主页</a><span class="eyebrow">{kind.upper()} ARCHIVE</span><h1>{label}归档 <span>/ {len(subset):02d}</span></h1><p>{timing}，历史不足时注明覆盖范围。</p></section><div class="report-grid">' + (''.join(card(r, '../') for r in subset) or f'<p class="empty">暂无{label}，有日报记录的周期结束后生成。</p>') + '</div>'
        write(f'archive/{kind}.html', label + '归档', body, '../')
    dailies = [r for r in reports if r['kind'] == 'daily']
    body = '<section class="archive-hero"><a class="back" href="../index.html">← 返回主页</a><span class="eyebrow">NEWS ARCHIVE</span><h1>前沿新闻归档</h1><p>按领域浏览短讯，点击标题阅读完整分析和原文证据。</p></section>' + news_digest(dailies, '../')
    write('archive/news.html', '新闻归档', body, '../')
    unique_opportunities = {}
    for report in dailies:
        for opportunity in report.get('opportunities', []):
            unique_opportunities.setdefault(opportunity['opportunity_id'], (opportunity, report))
    body = '<section class="archive-hero"><a class="back" href="../index.html">← 返回主页</a><span class="eyebrow">OPPORTUNITY ARCHIVE</span><h1>机会观察归档</h1><p>点击查看证据信号、适用人群、验证步骤和风险。</p></section><div class="opportunity-grid">' + (''.join(opportunity_card(o, r, '../') for o, r in unique_opportunities.values()) or '<p class="empty">暂无机会。</p>') + '</div>'
    write('archive/opportunities.html', '机会归档', body, '../')
    filters = ''.join(f'<button class="filter {"active" if state == "eligible" else ""}" data-competition-filter="{state}" aria-pressed="{"true" if state == "eligible" else "false"}">{label}</button>' for state, label in [('eligible', '个人线上可参与'), ('conditional', '需确认'), ('closed', '报名已截止'), ('excluded', '不符合'), ('all', '全部')])
    source_labels = {'verified': '已核对部分详情', 'collected': '已采集待核规则', 'listing_only': '已查平台列表', 'browser_required': '详情待补查', 'failed': '本次访问失败'}
    coverage = '<table class="source-coverage"><thead><tr><th>官方来源</th><th>覆盖情况</th></tr></thead><tbody>' + ''.join(f'<tr><td><a href="{esc(s["url"])}" target="_blank" rel="noopener noreferrer">{esc(s["name"])}</a></td><td>{source_labels.get(s["status"], "待核对")}</td></tr>' for s in catalog.get('source_checks', [])) + '</tbody></table>'
    body = f'<section class="archive-hero"><a class="back" href="../index.html">← 返回主页</a><span class="eyebrow">AI COMPETITIONS</span><h1>全国 AI 竞赛</h1><p>{len(catalog["competitions"])} 项记录 · {len(eligible)} 项符合个人线上条件 · 核验于 {esc(time_label(catalog["checked_at"], True))}</p></section><div class="competition-toolbar"><label class="search-label"><span>搜索竞赛</span><input id="competition-search" type="search" placeholder="搜索赛题、方向或平台…"></label><div class="competition-filters">{filters}</div></div>' + '<p id="competition-result-count" class="results-meta" aria-live="polite"></p>' + competition_table(catalog['competitions'], '../') + '<div id="no-competitions" class="empty" hidden>没有符合当前筛选的赛事。<button class="reset-filter" data-reset-competitions>查看全部赛事</button></div><details class="coverage-details"><summary>来源覆盖与核验说明</summary>' + coverage + '<p>面向全国主要平台搜集，尚不代表穷尽全部赛事。报名仍须本人确认，规则冲突和阶段晋级限制在详情中保留。</p></details>'
    write('archive/competitions.html', '全国 AI 竞赛', body, '../')
    for entry in catalog['competitions']:
        body = '<div class="detail-shell"><a class="back" href="../archive/competitions.html">← 返回竞赛比较表</a><span class="eyebrow">COMPETITION / 官方规则核验</span>' + competition_card(entry) + '</div>'
        body = body.replace('<h3>' + esc(entry['name']) + '</h3>', '<h1>' + esc(entry['name']) + '</h1>', 1)
        write(competition_url(entry), entry['name'], body, '../')
    for report in reports:
        coverage = report['coverage']
        warning = ''
        if coverage['missing_dates']:
            warning = f'<details class="coverage-warning"><summary>历史覆盖不完整 · {coverage["available_days"]}/{coverage["expected_days"]} 天</summary><p>缺失日期：{esc("、".join(coverage["missing_dates"]))}</p></details>'
        failures = f'<p class="coverage-warning">部分来源未能采集：{esc("、".join(report["source_failures"]))}</p>' if report.get('source_failures') else ''
        window = f'<details class="collection-details"><summary>查看采集窗口</summary><p>{esc(report["collection_window"]["start"])} 至 {esc(report["collection_window"]["end"])}</p></details>' if report.get('collection_window') else ''
        intro = f'<div class="report-header"><a class="back" href="../../archive/{report["kind"]}.html">← 返回{KINDS[report["kind"]]}归档</a><span class="eyebrow">{report["kind"].upper()} BRIEF</span><h1>{esc(report["title"])}</h1><p class="report-date">{esc(report["period"]["start"])} — {esc(report["period"]["end"])} · {len(report["items"])} 条新闻 · {len(report.get("opportunities", []))} 个机会</p><p class="report-summary">{esc(report["summary"])}</p>{warning}{failures}{window}<nav class="report-sections"><a href="#frontier-news">新闻 ↓</a><a href="#report-opportunities">机会 ↓</a><a href="../../archive/competitions.html">竞赛比较表 →</a></nav></div>'
        body = intro + '<section id="frontier-news"><h2 class="report-section-title">本期新闻</h2><div class="news-list">' + (''.join(item_html(item, i, '../../', report['kind'] == 'daily') for i, item in enumerate(report['items'], 1)) or '<p class="empty">暂无新闻。</p>') + '</div></section>'
        body += '<section id="report-opportunities" class="report-opportunities"><h2 class="report-section-title">本期机会</h2>' + (''.join(opportunity_html(o, '../../') for o in report.get('opportunities', [])) or '<p class="empty">暂无机会。</p>') + '</section>'
        body += trending_html(report)
        if report.get('daily_reports'):
            body += '<section class="daily-links"><h2>本期日报索引</h2>' + ''.join(f'<a href="../daily/{esc(identity)}.html">{esc(identity)} →</a>' for identity in report['daily_reports']) + '</section>'
        if report.get('analysis'):
            body += '<section class="period-analysis"><h2>周期观察与下一步</h2>' + ''.join(f'<p>{esc(p)}</p>' for p in report['analysis']) + '</section>'
        body += f'<p class="generated">生成于 {esc(report["generated_at"])} · 公开信息简报。</p>'
        write(report_url(report), report['title'], body, '../../')
        for i, item in enumerate(report['items'], 1):
            body = f'<div class="detail-shell"><a class="back" href="../index.html#latest-news">← 返回简报首页</a><p class="detail-edition">收录于 {esc(report["period"]["end"])} · {KINDS[report["kind"]]}</p>' + item_html(item, i, '../') + f'<a class="back detail-return" href="../{report_url(report)}#item-{i}">查看整期报告 →</a></div>'
            body = body.replace('<h2>' + esc(item['headline']) + '</h2>', '<h1>' + esc(item['headline']) + '</h1>', 1)
            write(news_url(item, report), item['headline'], body, '../')
        for opportunity in report.get('opportunities', []):
            body = '<div class="detail-shell"><a class="back" href="../index.html#opportunities">← 返回机会观察</a><span class="eyebrow">OPPORTUNITY / 待验证的行动方向</span>' + opportunity_html(opportunity, '../') + f'<a class="back detail-return" href="../{report_url(report)}#opportunity-{opportunity["opportunity_id"]}">查看整期报告 →</a></div>'
            body = body.replace('<h3>' + esc(opportunity['headline']) + '</h3>', '<h1>' + esc(opportunity['headline']) + '</h1>', 1)
            write(opportunity_url(opportunity, report), opportunity['headline'], body, '../')
    # 清除由旧内容生成的页面，避免已移除内容仍被链接或索引。
    expected = set(generated)
    for directory in ['reports', 'articles', 'opportunities', 'competitions']:
        for page in (output / directory).rglob('*.html'):
            if page.relative_to(output).as_posix() not in expected:
                page.unlink()
    data_dir = output / 'data'
    data_dir.mkdir(exist_ok=True)
    (data_dir / 'reports.json').write_text(json.dumps(reports, ensure_ascii=False, indent=2) + '\n')
    (data_dir / 'competitions.json').write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + '\n')
    sitemap = [SITE_URL + path for path in generated]
    (output / 'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + ''.join(f'<url><loc>{esc(url)}</loc></url>' for url in sitemap) + '</urlset>')
    (output / 'robots.txt').write_text('User-agent: *\nAllow: /\nSitemap: ' + SITE_URL + 'sitemap.xml\n')
    print(f'生成简报主页、{len(reports)} 份报告与 {len(catalog["competitions"])} 项竞赛详情')


if __name__ == '__main__':
    build()
