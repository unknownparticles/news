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


def frame(title, body, prefix="", reports=None):
    nav = f'<a href="{prefix}index.html#latest-news">前沿新闻</a><a href="{prefix}index.html#opportunities">机会</a><a href="{prefix}archive/competitions.html">AI 竞赛</a>' + ''.join(f'<a href="{prefix}archive/{kind}.html">{label}</a>' for kind, label in KINDS.items())
    return f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="科技前沿、金融市场、政治政策与近期机会，每条内容保留原文、证据、影响和行动建议。">
<title>{esc(title)} · 情报观察室</title><link rel="stylesheet" href="{prefix}styles.css"></head>
<body><header class="site-header"><a class="brand" href="{prefix}index.html"><span class="brand-mark">情</span>情报观察室<span class="brand-en">INTELLIGENCE NOTES</span></a>
<nav aria-label="报告导航">{nav}<a class="github" href="https://github.com/unknownparticles/news">GitHub ↗</a></nav></header>
<main>{body}</main><footer><span>情报观察室 · 公开来源，可追溯的判断。</span><span>北京时间 · <a href="{prefix}archive/daily.html">历史归档</a> · <a href="https://github.com/unknownparticles/news">项目与纠错 ↗</a></span></footer>
<script src="{prefix}app.js" defer></script></body></html>'''


def card(report, prefix=""):
    coverage = report["coverage"]
    partial = coverage["available_days"] < coverage["expected_days"]
    text = f"覆盖 {coverage['available_days']}/{coverage['expected_days']} 天" if partial else "日期覆盖完整"
    return f'''<a class="report-card" href="{prefix}{report_url(report)}" data-kind="{report['kind']}" data-search="{esc(report['title'] + ' ' + report['summary'] + ' ' + ' '.join(i['headline'] for i in report['items'] + report.get('opportunities', [])))}">
<div class="card-top"><span class="type-label">{KINDS[report['kind']]}</span><span class="coverage {'partial' if partial else ''}">{text}</span></div>
<h3>{esc(report['title'])}</h3><p>{esc(report['summary'])}</p>
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
<p class="competition-topic">{esc(entry['topic'])}</p><p class="competition-deadline">报名截止：{esc(deadline)}</p>
<dl><dt>参赛条件</dt><dd>{esc(entry['eligibility'])}</dd><dt>参与方式</dt><dd>{esc(entry['format'])}</dd><dt>费用与算力</dt><dd>{esc(entry['cost'])}</dd><dt>奖励</dt><dd>{esc(entry['prizes'])}</dd><dt>先做什么</dt><dd>{esc(entry['first_step'])}</dd></dl>
<p class="competition-caution">{esc(entry['cautions'])}</p><div class="original-links"><a href="{esc(entry['registration_url'])}" target="_blank" rel="noopener noreferrer">官方报名与规则 ↗</a></div><details><summary>资格与日期证据 · 核验于 {esc(time_label(entry['checked_at']))}</summary><ul class="evidence">{evidence}</ul></details></article>'''


def headline_card(item, report, number, prefix=''):
    return f'''<article class="headline-card" data-news-category="{news_group(item['category'])}">
<div class="item-meta"><span>{esc(item['category'])}</span><span class="status">{STATUSES[item['verification_status']]}</span></div>
<h3><a href="{prefix}{report_url(report)}#item-{number}">{esc(item['headline'])}</a></h3>
<p>{esc(item['summary'])}</p><small>{esc(time_label(item.get('published_at')))}</small>
{f'<p class="context-note">{esc(item["context_note"])}</p>' if item.get('context_note') else ''}
{original_links(item)}<a class="text-link" href="{prefix}{report_url(report)}#item-{number}">查看影响与行动建议 →</a></article>'''


def opportunity_state(opportunity, at=None):
    at = at or datetime.now(ZoneInfo('Asia/Shanghai'))
    if opportunity.get('deadline') and datetime.fromisoformat(opportunity['deadline']) < at:
        return 'closed'
    return opportunity['status']


def opportunity_card(opportunity, report, prefix=''):
    labels = {'research': '待验证机会', 'actionable': '可开始验证', 'closed': '窗口已结束'}
    return f'''<article class="opportunity-card"><div class="item-meta"><span>{esc(opportunity['category'])}</span><span class="status">{labels[opportunity_state(opportunity)]}</span></div>
<h3><a href="{prefix}{report_url(report)}#opportunity-{opportunity['opportunity_id']}">{esc(opportunity['headline'])}</a></h3>
<p>{esc(opportunity['signal'])}</p><div class="opportunity-step"><b>第一步</b><p>{esc(opportunity['first_step'])}</p></div>
<p class="opportunity-risk"><b>风险：</b>{esc(opportunity['risks'])}</p><small>{esc(opportunity['time_window'])} · 发现于 {esc(report['period']['end'])}</small>
{original_links(opportunity)}<a class="text-link" href="{prefix}{report_url(report)}#opportunity-{opportunity['opportunity_id']}">查看适用人群与完整分析 →</a></article>'''


def opportunity_html(opportunity, prefix=''):
    labels = {'research': '待验证机会', 'actionable': '可开始验证', 'closed': '窗口已结束'}
    sources = ''.join(f'<li><a href="{esc(s["url"])}" target="_blank" rel="noopener noreferrer">{esc(s["label"])} ↗</a><blockquote>{esc(s["excerpt"])}</blockquote><small>核验于 {esc(time_label(s["checked_at"]))}</small></li>' for s in opportunity['sources'])
    backlink = f'<a href="{prefix}reports/daily/{esc(opportunity["daily_report"])}.html">查看收录日报 →</a>' if opportunity.get('daily_report') else ''
    return f'''<article class="opportunity-detail" id="opportunity-{opportunity['opportunity_id']}"><div class="item-meta"><span>{esc(opportunity['category'])}</span><span class="status">{labels[opportunity_state(opportunity)]}</span><span>证据信号：{STATUSES[opportunity['verification_status']]}</span></div>
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
    expected_pages = {output / report_url(r) for r in reports}
    for obsolete in (output / "reports").glob("*/*.html"):
        if obsolete not in expected_pages:
            obsolete.unlink()
    for asset in (ROOT / "web").iterdir():
        if asset.is_file():
            shutil.copyfile(asset, output / asset.name)
    (output / ".nojekyll").write_text("")
    latest_daily = next((r for r in reports if r["kind"] == "daily"), None)
    latest = {kind: next((r for r in reports if r["kind"] == kind), None) for kind in KINDS}
    stats = ''.join(f'<a class="period-stat" href="archive/{kind}.html"><span>{label}</span><strong>{sum(r["kind"] == kind for r in reports):02d}</strong><small>{esc(latest[kind]["period"]["end"]) if latest[kind] else "等待首期"}</small></a>' for kind, label in KINDS.items())
    cta = f'<a class="button" href="{report_url(latest_daily)}">阅读最新日报 <span>↗</span></a>' if latest_daily else '<a class="button" href="#archive">浏览报告归档 ↓</a>'
    latest_block = f'<section class="latest"><div><span class="eyebrow">LATEST BRIEF / 最新简报</span><h2>{esc(latest_daily["title"])}</h2><p>{esc(latest_daily["summary"])}</p></div><a class="text-link" href="{report_url(latest_daily)}">展开阅读 ↗</a></section>' if latest_daily else '<section class="latest"><div><span class="eyebrow">LATEST BRIEF / 最新简报</span><h2>首份日报准备中</h2><p>完成公开来源采集与核验后，将在这里更新。</p></div></section>'
    filter_buttons = '<button class="filter active" data-filter="all" aria-pressed="true">全部</button>' + ''.join(f'<button class="filter" data-filter="{kind}" aria-pressed="false">{label}</button>' for kind, label in KINDS.items())
    cards = ''.join(card(r) for r in reports) or '<p class="empty">暂无已发布报告。后续各期将自动关联到这里。</p>'
    news_cards = ''.join(headline_card(item, latest_daily, i) for i, item in enumerate(latest_daily['items'], 1)) if latest_daily else ''
    opportunity_cards = ''.join(opportunity_card(opportunity, latest_daily) for opportunity in latest_daily.get('opportunities', [])) if latest_daily else ''
    content = f'''<section id="latest-news" class="frontier-section"><div class="section-heading"><div><span class="eyebrow">THE FRONTIER / {esc(latest_daily['period']['end']) if latest_daily else '持续更新'}</span><h2>科技、金融与政治前沿</h2></div><a class="text-link" href="archive/news.html">全部新闻 →</a></div>
<div class="news-filters" aria-label="新闻领域筛选"><button class="filter active" data-news-filter="all" aria-pressed="true">全部新闻</button>{''.join(f'<button class="filter" data-news-filter="{domain}" aria-pressed="false">{label} · {sum(news_domain(i["category"]) == domain for i in latest_daily["items"]) if latest_daily else 0}</button>' for domain, label in NEWS_DOMAINS.items())}</div><p class="section-note">每个领域独立收录，目标每日三至五条；数量不足时注明原因。</p>
<div class="headline-grid">{news_cards or '<p class="empty">暂无通过核验的新闻。</p>'}</div><p id="no-news" class="empty" hidden>本期没有该领域通过筛选的新闻。</p></section>
<section id="opportunities" class="opportunities-section"><div class="section-heading"><div><span class="eyebrow">OPPORTUNITY WATCH</span><h2>近期机会，先小步验证。</h2></div><a class="text-link" href="archive/opportunities.html">机会归档 →</a></div><p class="section-note">从公开变化寻找产品、服务与开发提效的切入点。证据支持变化信号，实际需求与回报仍需验证。</p><div class="opportunity-grid">{opportunity_cards or '<p class="empty">本期暂无足够证据支持的机会；不为凑数推荐。</p>'}</div></section>'''
    eligible = [entry for entry in catalog['competitions'] if competition_state(entry) == 'eligible']
    content += f'''<section id="competitions" class="competitions-section"><div class="section-heading"><div><span class="eyebrow">AI COMPETITIONS / 全国赛事观察</span><h2>个人可以参与的 AI 竞赛</h2></div><a class="text-link" href="archive/competitions.html">全部 {len(catalog['competitions'])} 项与资格筛选 →</a></div><p class="section-note">优先社会人士、单人、线上参赛；当前核验符合条件 {len(eligible)} 项。奖励赛、练习赛和仅线上阶段的赛事分别注明。</p><div class="competition-grid">{''.join(competition_card(entry) for entry in eligible[:6]) or '<p class="empty">暂无已核验符合个人线上条件的赛事，待核对的名单见竞赛页面。</p>'}</div></section>'''
    body = f'''<section class="hero"><div class="hero-copy"><span class="eyebrow"><span class="live-dot"></span> PERSONAL INTELLIGENCE / 持续更新</span><h1>看见前沿，<br>找到<span>机会。</span></h1><p>科技、金融、政治，每天抓住值得关注的变化。<br>直达新闻原文，分清事实与推测，再决定下一步。</p>{cta}<a class="hero-opportunity-link" href="#opportunities">研究近期机会 ↓</a></div>
<aside class="hero-note"><span class="note-index">最新速览 / {esc(latest_daily['period']['end']) if latest_daily else '准备中'}</span><h2>{len(latest_daily['items']) if latest_daily else 0} 条新闻<br>{len(latest_daily.get('opportunities', [])) if latest_daily else 0} 个机会</h2><p>科技 · 金融 · 政治<br>原文、发布时间与影响分析<br>机会附验证步骤和不确定性</p><a class="note-footer" href="#latest-news">浏览最新前沿 ↓</a></aside></section>
{content}<section class="period-stats" aria-label="各类报告数量">{stats}</section>{latest_block}
<section id="archive"><div class="section-heading"><div><span class="eyebrow">THE ARCHIVE</span><h2>从今天，看到更远。</h2></div><label class="search-label"><span>搜索报告</span><input id="report-search" type="search" placeholder="搜索主题、标题或日期…"></label></div>
<div class="filters" aria-label="筛选报告类型">{filter_buttons}<span id="result-count" aria-live="polite"></span></div><div class="report-grid">{cards}</div><p id="no-results" class="empty" hidden>没有匹配的报告，请换一个关键词。</p></section>
<section class="topics"><span class="eyebrow">FOCUS AREAS / 关注领域</span><div>{''.join(f'<span>{esc(c)}</span>' for c in CONFIG['categories'])}</div><p>科技、金融、政治各最多五条新闻，另有三个机会和独立竞赛库；周期报告汇总已归档内容。</p></section>'''
    (output / "index.html").write_text(frame("主页", body))
    for kind, label in KINDS.items():
        target = output / "archive" / (kind + ".html")
        target.parent.mkdir(exist_ok=True)
        subset = [r for r in reports if r['kind'] == kind]
        timing = {"daily": "每日早晨更新", "weekly": "每周一汇总上一自然周", "monthly": "每月首日汇总上月", "quarterly": "每季首日汇总上一季度", "yearly": "每年首日汇总上一年"}[kind]
        body = f'<section class="archive-hero"><a class="back" href="../index.html">← 返回主页</a><span class="eyebrow">{kind.upper()} ARCHIVE</span><h1>{label}归档<span> / {len(subset):02d}</span></h1><p>{timing}。周期结束后生成；历史不足时展示实际覆盖范围。</p></section><div class="report-grid">' + (''.join(card(r, '../') for r in subset) or f'<p class="empty">暂无{label}。首个有日报记录的周期结束后，将生成本期汇总。</p>') + '</div>'
        target.write_text(frame(label + "归档", body, "../"))
    daily_reports = [r for r in reports if r['kind'] == 'daily']
    all_news = ''.join(headline_card(item, report, i, '../') for report in daily_reports for i, item in enumerate(report['items'], 1))
    archive_header = '<section class="archive-hero"><a class="back" href="../index.html">← 返回主页</a><span class="eyebrow">NEWS ARCHIVE</span><h1>前沿新闻归档</h1><p>按日报日期回溯新闻，直接阅读原文或查看影响分析。</p></section>'
    (output / 'archive/news.html').write_text(frame('前沿新闻归档', archive_header + '<div class="headline-grid">' + (all_news or '<p class="empty">暂无新闻。</p>') + '</div>', '../'))
    unique_opportunities = {}
    for report in daily_reports:
        for opportunity in report.get('opportunities', []):
            unique_opportunities.setdefault(opportunity['opportunity_id'], (opportunity, report))
    archive_header = '<section class="archive-hero"><a class="back" href="../index.html">← 返回主页</a><span class="eyebrow">OPPORTUNITY ARCHIVE</span><h1>机会观察归档</h1><p>保留发现日期、证据、验证步骤和不确定性。历史窗口不代表当前仍然开放。</p></section>'
    (output / 'archive/opportunities.html').write_text(frame('机会归档', archive_header + '<div class="opportunity-grid">' + (''.join(opportunity_card(opportunity, report, '../') for opportunity, report in unique_opportunities.values()) or '<p class="empty">暂无机会。</p>') + '</div>', '../'))
    filters = ''.join(f'<button class="filter {"active" if state == "eligible" else ""}" data-competition-filter="{state}" aria-pressed="{"true" if state == "eligible" else "false"}">{label}</button>' for state, label in [('eligible', '个人线上可参与'), ('conditional', '需确认'), ('closed', '报名已截止'), ('excluded', '不符合'), ('all', '全部')])
    source_labels = {'verified': '已核对赛事详情', 'collected': '已采集待核规则', 'listing_only': '已查平台列表', 'browser_required': '详情待补查', 'failed': '本次访问失败'}
    source_table = '<table class="source-coverage"><thead><tr><th>官方来源</th><th>覆盖情况</th></tr></thead><tbody>' + ''.join(f'<tr><td><a href="{esc(s["url"])}" target="_blank" rel="noopener noreferrer">{esc(s["name"])}</a></td><td>{source_labels.get(s["status"], "待核对")}</td></tr>' for s in catalog.get('source_checks', [])) + '</tbody></table>'
    competition_body = f'<section class="archive-hero"><a class="back" href="../index.html">← 返回主页</a><span class="eyebrow">AI COMPETITIONS</span><h1>全国 AI 竞赛观察</h1><p>优先列出面向社会人士、允许单人线上参与的赛题。报名状态、规则冲突和阶段晋级要求分别核对。</p><p>核验时间：{esc(time_label(catalog["checked_at"]))} · {len(catalog["competitions"])} 项记录 · {len(eligible)} 项符合公开参赛条件</p></section><label class="search-label"><span>搜索竞赛</span><input id="competition-search" type="search" placeholder="搜索赛题、方向或平台…"></label><div class="competition-filters">{filters}</div><div class="competition-grid">' + ''.join(competition_card(entry) for entry in catalog['competitions']) + '</div><p id="no-competitions" class="empty" hidden>没有符合当前筛选的赛事。</p><section class="topics"><h2>已查官方来源</h2>' + source_table + '<p>覆盖全国主要赛事平台，尚不代表穷尽所有赛事。只查到列表的来源不会标记为完整核验，报名仍须本人在官网确认。</p></section>'
    (output / 'archive/competitions.html').write_text(frame('全国 AI 竞赛', competition_body, '../'))
    for report in reports:
        target = output / report_url(report)
        target.parent.mkdir(parents=True, exist_ok=True)
        c = report['coverage']
        warning = ''
        if c['missing_dates']:
            warning = f'<details class="coverage-warning"><summary>历史覆盖不完整 · {c["available_days"]}/{c["expected_days"]} 天</summary><p>以下日期没有日报记录：{esc("、".join(c["missing_dates"]))}。本期不代表全周期完整资讯。</p></details>'
        window = ''
        if report.get('collection_window'):
            window = f'<p class="collection-window">采集窗口：{esc(report["collection_window"]["start"])} 至 {esc(report["collection_window"]["end"])}</p>'
        source_failures = report.get("source_failures", [])
        failures = f'<p class="coverage-warning">部分来源未能采集：{esc("、".join(source_failures))}。本期信息覆盖有限。</p>' if source_failures else ''
        body = f'<div class="report-header"><a class="back" href="../../archive/{report["kind"]}.html">← 返回{KINDS[report["kind"]]}归档</a><span class="eyebrow">{report["kind"].upper()} BRIEF / {KINDS[report["kind"]]}</span><h1>{esc(report["title"])}</h1><p class="report-date">{esc(report["period"]["start"])} — {esc(report["period"]["end"])} · {len(report["items"])} 条新闻 · {len(report.get("opportunities", []))} 个机会</p><p class="report-summary">{esc(report["summary"])}</p>{window}{warning}{failures}<nav class="report-sections" aria-label="日报章节"><a href="#frontier-news">前沿新闻 ↓</a><a href="#report-opportunities">近期机会 ↓</a></nav></div><section id="frontier-news"><h2 class="report-section-title">前沿新闻</h2><div class="news-list">' + (''.join(item_html(item, i, '../../', report['kind'] == 'daily') for i, item in enumerate(report['items'], 1)) or '<p class="empty">本期没有通过筛选的重点新闻。</p>') + '</div></section>'
        body += '<section id="report-opportunities" class="report-opportunities"><h2 class="report-section-title">近期机会与验证步骤</h2>' + (''.join(opportunity_html(opportunity, '../../') for opportunity in report.get('opportunities', [])) or '<p class="empty">本期没有足够证据支持的新机会。</p>') + '</section>'
        if report.get('daily_reports'):
            body += '<section class="daily-links"><h2>本期日报索引</h2>' + ''.join(f'<a href="../daily/{esc(identity)}.html">{esc(identity)} →</a>' for identity in report['daily_reports']) + '</section>'
        if report.get('analysis'):
            body += '<section class="period-analysis"><h2>周期观察与下一步</h2>' + ''.join(f'<p>{esc(paragraph)}</p>' for paragraph in report['analysis']) + '</section>'
        body += f'<p class="generated">生成于 {esc(report["generated_at"])} · 公开信息简报，不构成投资建议。</p>'
        target.write_text(frame(report['title'], body, '../../'))
    data_dir = output / "data"
    data_dir.mkdir(exist_ok=True)
    (data_dir / "reports.json").write_text(json.dumps(reports, ensure_ascii=False, indent=2) + "\n")
    (data_dir / 'competitions.json').write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + '\n')
    sitemap = [SITE_URL] + [SITE_URL + 'archive/' + kind + '.html' for kind in [*KINDS, 'news', 'opportunities', 'competitions']] + [SITE_URL + report_url(r) for r in reports]
    (output / 'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + ''.join(f'<url><loc>{esc(url)}</loc></url>' for url in sitemap) + '</urlset>')
    (output / 'robots.txt').write_text('User-agent: *\nAllow: /\nSitemap: ' + SITE_URL + 'sitemap.xml\n')
    print(f"生成站点：{len(reports)} 份报告、五类归档与主页")


if __name__ == '__main__':
    build()
