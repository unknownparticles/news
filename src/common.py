"""公开报告的校验、去重和存储，不依赖第三方库。"""
import hashlib
import json
import re
from datetime import date, datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
KINDS = {"daily": "日报", "weekly": "周报", "monthly": "月报", "quarterly": "季报", "yearly": "年报"}
CONFIG = json.loads((ROOT / "config/sources.json").read_text())
STATUSES = {"official_confirmed": "官方已确认", "project_documented": "项目文档支持", "unverified": "尚未核实", "conflicting": "信息存在冲突"}


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
    if not isinstance(items, list) or len(items) > (5 if report["kind"] == "daily" else 15):
        raise ValueError("报告条数超出限制")
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
        sources = item["sources"]
        if not sources:
            raise ValueError("新闻必须有证据链接")
        for source in sources:
            safe_url(source["url"])
            if not source["label"].strip() or not source.get("excerpt", "").strip():
                raise ValueError("证据必须有名称和支持结论的原文摘录")
            if datetime.fromisoformat(source["checked_at"]).tzinfo is None:
                raise ValueError("核验时间必须包含时区")
        if item["verification_status"] == "official_confirmed" and not any(
            s["url"].startswith(tuple(CONFIG["official_url_prefixes"])) for s in sources
        ):
            raise ValueError("官方确认需要已配置的官方证据地址；还需人工核对具体结论")
        if item.get("commercial_status") == "eligible" and not item.get("license_evidence"):
            raise ValueError("商业推荐必须提供许可证证据")
        if item.get("license_evidence"):
            safe_url(item["license_evidence"])
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
