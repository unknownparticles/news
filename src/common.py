"""公开报告的校验、去重和存储，不依赖第三方库。"""
import hashlib
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
KINDS = {"daily": "日报", "weekly": "周报", "monthly": "月报", "quarterly": "季报", "yearly": "年报"}
CONFIG = json.loads((ROOT / "config/sources.json").read_text())
STATUSES = {"official_confirmed": "官方已确认", "media_reported": "媒体报道", "project_documented": "项目文档支持", "unverified": "尚未核实", "conflicting": "信息存在冲突"}
FRONTIER_CATEGORIES = {"科技前沿", "金融市场", "政治与政策"}
NEWS_DOMAINS = {"technology": "科技", "finance": "金融", "politics": "政治"}


def news_domain(category):
    return {"金融市场": "finance", "政治与政策": "politics"}.get(category, "technology")


def validate_evidence(entry):
    sources = entry["sources"]
    if not isinstance(sources, list) or not sources:
        raise ValueError("内容必须有证据链接")
    if entry["verification_status"] not in STATUSES:
        raise ValueError("核验状态错误")
    for source in sources:
        safe_url(source["url"])
        if not source["label"].strip() or not source.get("excerpt", "").strip():
            raise ValueError("证据必须有名称和支持结论的原文摘录")
        if datetime.fromisoformat(source["checked_at"]).tzinfo is None:
            raise ValueError("核验时间必须包含时区")
    if entry["verification_status"] == "official_confirmed" and not any(
        s["url"].startswith(tuple(CONFIG["official_url_prefixes"])) for s in sources
    ):
        raise ValueError("官方确认需要已配置的官方证据地址；还需人工核对具体结论")


def safe_url(url):
    if not isinstance(url, str) or any(c.isspace() for c in url):
        raise ValueError("链接格式错误")
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        raise ValueError("只接受不包含凭据的公开 HTTPS 链接")
    return url


def canonical_url(url):
    parts = urlsplit(safe_url(url))
    query = [(k, v) for k, v in parse_qsl(parts.query) if not k.lower().startswith("utm_") and k.lower() not in {"ref", "fbclid", "gclid"}]
    return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path.rstrip("/"), urlencode(sorted(query)), ""))


def event_id(url):
    return hashlib.sha256(canonical_url(url).encode()).hexdigest()[:20]


def validate_report(report):
    if report["kind"] not in KINDS or not re.fullmatch(r"[a-z0-9-]+", report["id"]):
        raise ValueError("报告类型或编号错误")
    start, end = (date.fromisoformat(report["period"][x]) for x in ("start", "end"))
    if start > end:
        raise ValueError("报告起止日期倒置")
    if report["kind"] == "daily" and start != end:
        raise ValueError("日报必须对应一个报告日期")
    stamp = datetime.fromisoformat(report["generated_at"])
    if stamp.tzinfo is None:
        raise ValueError("生成时间必须包含时区")
    for key in ("title", "summary"):
        if not isinstance(report[key], str) or not report[key].strip():
            raise ValueError("报告标题和摘要不能为空")
    if report.get("collection_window"):
        window = report["collection_window"]
        times = [datetime.fromisoformat(window[key]) for key in ("start", "end")]
        if any(t.tzinfo is None for t in times) or times[0] >= times[1]:
            raise ValueError("采集窗口必须包含时区且起止时间正确")
    if report.get("analysis") is not None and (not isinstance(report["analysis"], list) or any(not isinstance(p, str) or not p.strip() for p in report["analysis"])):
        raise ValueError("周期分析必须是非空段落的列表")
    if 'github_trending' in report:
        from .trending import validate_trending
        validate_trending(report['github_trending'], report)
    coverage = report["coverage"]
    expected = (end - start).days + 1
    if coverage["expected_days"] != expected or not 0 <= coverage["available_days"] <= expected:
        raise ValueError("覆盖天数不正确")
    missing = coverage["missing_dates"]
    if len(set(missing)) != len(missing) or len(missing) != expected - coverage["available_days"]:
        raise ValueError("缺失日期与覆盖天数不一致")
    if any(not start <= date.fromisoformat(day) <= end for day in missing):
        raise ValueError("缺失日期超出报告范围")
    items = report["items"]
    per_domain = 5 if report["kind"] == "daily" else 15
    if not isinstance(items, list) or len(items) > per_domain * len(NEWS_DOMAINS):
        raise ValueError("报告条数超出限制")
    if any(sum(news_domain(item["category"]) == domain for item in items) > per_domain for domain in NEWS_DOMAINS):
        raise ValueError("单个新闻领域条数超出限制")
    seen = set()
    for item in items:
        identity = item["event_id"]
        if not re.fullmatch(r"[a-z0-9-]{8,80}", identity) or identity in seen:
            raise ValueError("新闻编号错误或重复")
        seen.add(identity)
        if item["category"] not in CONFIG["categories"] or item["verification_status"] not in STATUSES:
            raise ValueError("分类或核验状态错误")
        for key in ("headline", "summary", "relevance", "action"):
            if not isinstance(item[key], str) or not item[key].strip():
                raise ValueError("每条新闻必须包含标题、摘要、影响与行动建议")
        if isinstance(item["score"], bool) or not isinstance(item["score"], (int, float)) or not 0 <= item["score"] <= 100:
            raise ValueError("评分必须在零至一百分之间")
        validate_evidence(item)
        if item["category"] in FRONTIER_CATEGORIES or item.get("published_at"):
            published = datetime.fromisoformat(item["published_at"])
            if published.tzinfo is None or published > stamp:
                raise ValueError("新闻发布时间必须带时区且不能晚于报告生成时间")
            if report["kind"] == "daily" and stamp - published > timedelta(hours=24) and not item.get("context_note"):
                raise ValueError("超过二十四小时的新闻必须说明回看或补采原因")
        if item.get("commercial_status") == "eligible" and not item.get("license_evidence"):
            raise ValueError("商业推荐必须提供许可证证据")
        if item.get("license_evidence"):
            safe_url(item["license_evidence"])
    opportunities = report.get("opportunities", [])
    if not isinstance(opportunities, list) or len(opportunities) > (3 if report["kind"] == "daily" else 10):
        raise ValueError("机会条数超出限制")
    identities = set()
    for opportunity in opportunities:
        identity = opportunity["opportunity_id"]
        if not re.fullmatch(r"[a-z0-9-]{8,80}", identity) or identity in identities:
            raise ValueError("机会编号错误或重复")
        identities.add(identity)
        for key in ("headline", "signal", "audience", "first_step", "risks", "time_window"):
            if not isinstance(opportunity[key], str) or not opportunity[key].strip():
                raise ValueError("机会必须说明信号、适用人群、第一步、风险与时间窗口")
        if opportunity["category"] not in CONFIG["categories"]:
            raise ValueError("机会分类错误")
        if opportunity.get("status") not in {"research", "actionable", "closed"}:
            raise ValueError("机会状态错误")
        if isinstance(opportunity["score"], bool) or not isinstance(opportunity["score"], (int, float)) or not 0 <= opportunity["score"] <= 100:
            raise ValueError("机会评分错误")
        validate_evidence(opportunity)
        if opportunity.get("deadline"):
            deadline = datetime.fromisoformat(opportunity["deadline"])
            if deadline.tzinfo is None:
                raise ValueError("机会截止时间必须带时区")
            if deadline < stamp and opportunity["status"] != "closed":
                raise ValueError("已截止的机会不能标记为可行动")
        if opportunity.get("commercial_status") == "eligible" and not opportunity.get("license_evidence"):
            raise ValueError("商业机会必须提供许可证证据")
        if opportunity.get("license_evidence"):
            safe_url(opportunity["license_evidence"])
    return report


def load_reports(root=ROOT / "reports"):
    reports = [validate_report(json.loads(p.read_text())) for p in sorted(root.glob("*/*.json"))]
    keys = [(r["kind"], r["id"]) for r in reports]
    if len(keys) != len(set(keys)):
        raise ValueError("报告编号重复")
    return sorted(reports, key=lambda r: (r["period"]["end"], r["generated_at"]), reverse=True)


def save_report(report, root=ROOT / "reports"):
    validate_report(report)
    target = root / report["kind"] / (report["id"] + ".json")
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    tmp.replace(target)
    return target
