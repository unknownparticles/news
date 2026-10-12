"""从公开 JSON 报告生成 GitHub Pages 站点。"""
import html
import json
import os
import shutil
from pathlib import Path

from .common import CONFIG, KINDS, ROOT, STATUSES, load_reports

SITE_URL = os.environ.get("SITE_URL", "https://alunapp.cn/news/").replace("http://", "https://", 1).rstrip("/") + "/"


def esc(text):
    return html.escape(str(text), quote=True)


def report_url(report):
    return f"reports/{report['kind']}/{report['id']}.html"


def frame(title, body, prefix="", reports=None):
    nav = ''.join(f'<a href="{prefix}archive/{kind}.html">{label}</a>' for kind, label in KINDS.items())
    return f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="聚焦 AI 编程、开源项目、工作室业务、Solana 基础设施与移动开发的公开情报简报。">
<title>{esc(title)} · 情报观察室</title><link rel="stylesheet" href="{prefix}styles.css"></head>
<body><header class="site-header"><a class="brand" href="{prefix}index.html"><span class="brand-mark">情</span>情报观察室<span class="brand-en">INTELLIGENCE NOTES</span></a>
<nav aria-label="报告导航">{nav}<a class="github" href="https://github.com/unknownparticles/news">GitHub ↗</a></nav></header>
<main>{body}</main><footer><span>情报观察室 · 公开来源，可追溯的判断。</span><span>北京时间 · <a href="{prefix}archive/daily.html">历史归档</a> · <a href="https://github.com/unknownparticles/news">项目与纠错 ↗</a></span></footer>
<script src="{prefix}app.js" defer></script></body></html>'''


def card(report, prefix=""):
    coverage = report["coverage"]
    partial = coverage["available_days"] < coverage["expected_days"]
    text = f"覆盖 {coverage['available_days']}/{coverage['expected_days']} 天" if partial else "日期覆盖完整"
    return f'''<a class="report-card" href="{prefix}{report_url(report)}" data-kind="{report['kind']}" data-search="{esc(report['title'] + ' ' + report['summary'] + ' ' + ' '.join(i['headline'] for i in report['items']))}">
<div class="card-top"><span class="type-label">{KINDS[report['kind']]}</span><span class="coverage {'partial' if partial else ''}">{text}</span></div>
<h3>{esc(report['title'])}</h3><p>{esc(report['summary'])}</p>
<div class="card-bottom"><span>{esc(report['period']['start'])} — {esc(report['period']['end'])}</span><span>{len(report['items'])} 条 <b>↗</b></span></div></a>'''


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
<div class="analysis"><div><h4>为什么值得关注</h4><p>{esc(item['relevance'])}</p></div><div><h4>下一步</h4><p>{esc(item['action'])}</p></div></div>
{license_note}<details><summary>来源与证据 · {len(item['sources'])} 个</summary><ul class="evidence">{sources}</ul></details>{backlink}</div></article>'''


def build(output=ROOT / "docs", report_root=ROOT / "reports"):
    reports = load_reports(report_root)
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
    body = f'''<section class="hero"><div class="hero-copy"><span class="eyebrow"><span class="live-dot"></span> PERSONAL INTELLIGENCE / 持续更新</span><h1>把信息，<br>变成<span>下一步。</span></h1><p>每天少一点噪声，多一点值得行动的判断。<br>从 AI 工具到开源项目，记录变化，也追踪长期趋势。</p>{cta}</div>
<aside class="hero-note"><span class="note-index">01 / 观察原则</span><h2>相关。<br>可信。<br>能行动。</h2><p>保留原文与证据<br>区分事实和推测<br>有价值，才值得占用注意力</p><span class="note-footer">DAILY → YEARLY ↗</span></aside></section>
<section class="period-stats" aria-label="各类报告数量">{stats}</section>{latest_block}
<section id="archive"><div class="section-heading"><div><span class="eyebrow">THE ARCHIVE</span><h2>从今天，看到更远。</h2></div><label class="search-label"><span>搜索报告</span><input id="report-search" type="search" placeholder="搜索主题、标题或日期…"></label></div>
<div class="filters" aria-label="筛选报告类型">{filter_buttons}<span id="result-count" aria-live="polite"></span></div><div class="report-grid">{cards}</div><p id="no-results" class="empty" hidden>没有匹配的报告，请换一个关键词。</p></section>
<section class="topics"><span class="eyebrow">FOCUS AREAS / 关注领域</span><div>{''.join(f'<span>{esc(c)}</span>' for c in CONFIG['categories'])}</div><p>日报保留最多五条重点；周、月、季、年报告汇总已归档内容，并明确标注缺失日期。</p></section>'''
    (output / "index.html").write_text(frame("主页", body))
    for kind, label in KINDS.items():
        target = output / "archive" / (kind + ".html")
        target.parent.mkdir(exist_ok=True)
        subset = [r for r in reports if r['kind'] == kind]
        timing = {"daily": "每日早晨更新", "weekly": "每周一汇总上一自然周", "monthly": "每月首日汇总上月", "quarterly": "每季首日汇总上一季度", "yearly": "每年首日汇总上一年"}[kind]
        body = f'<section class="archive-hero"><a class="back" href="../index.html">← 返回主页</a><span class="eyebrow">{kind.upper()} ARCHIVE</span><h1>{label}归档<span> / {len(subset):02d}</span></h1><p>{timing}。周期结束后生成；历史不足时展示实际覆盖范围。</p></section><div class="report-grid">' + (''.join(card(r, '../') for r in subset) or f'<p class="empty">暂无{label}。首个有日报记录的周期结束后，将生成本期汇总。</p>') + '</div>'
        target.write_text(frame(label + "归档", body, "../"))
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
        body = f'<div class="report-header"><a class="back" href="../../archive/{report["kind"]}.html">← 返回{KINDS[report["kind"]]}归档</a><span class="eyebrow">{report["kind"].upper()} BRIEF / {KINDS[report["kind"]]}</span><h1>{esc(report["title"])}</h1><p class="report-date">{esc(report["period"]["start"])} — {esc(report["period"]["end"])} · {len(report["items"])} 条重点</p><p class="report-summary">{esc(report["summary"])}</p>{window}{warning}{failures}</div><div class="news-list">' + (''.join(item_html(item, i, '../../', report['kind'] == 'daily') for i, item in enumerate(report['items'], 1)) or '<p class="empty">本期没有通过筛选的重点新闻。</p>') + '</div>'
        if report.get('daily_reports'):
            body += '<section class="daily-links"><h2>本期日报索引</h2>' + ''.join(f'<a href="../daily/{esc(identity)}.html">{esc(identity)} →</a>' for identity in report['daily_reports']) + '</section>'
        if report.get('analysis'):
            body += '<section class="period-analysis"><h2>周期观察与下一步</h2>' + ''.join(f'<p>{esc(paragraph)}</p>' for paragraph in report['analysis']) + '</section>'
        body += f'<p class="generated">生成于 {esc(report["generated_at"])} · 公开信息简报，不构成投资建议。</p>'
        target.write_text(frame(report['title'], body, '../../'))
    data_dir = output / "data"
    data_dir.mkdir(exist_ok=True)
    (data_dir / "reports.json").write_text(json.dumps(reports, ensure_ascii=False, indent=2) + "\n")
    sitemap = [SITE_URL] + [SITE_URL + 'archive/' + kind + '.html' for kind in KINDS] + [SITE_URL + report_url(r) for r in reports]
    (output / 'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + ''.join(f'<url><loc>{esc(url)}</loc></url>' for url in sitemap) + '</urlset>')
    (output / 'robots.txt').write_text('User-agent: *\nAllow: /\nSitemap: ' + SITE_URL + 'sitemap.xml\n')
    print(f"生成站点：{len(reports)} 份报告、五类归档与主页")


if __name__ == '__main__':
    build()
