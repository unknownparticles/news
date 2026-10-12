"""补齐已经结束且与现有日报重叠的周期，缺失日报显式展示。"""
import argparse
import copy
import calendar
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from .common import KINDS, NEWS_DOMAINS, load_reports, save_report, news_domain


def bounds(day, kind):
    if kind == "weekly":
        start = day - timedelta(days=day.weekday())
        return start, start + timedelta(days=6)
    if kind == "monthly":
        return day.replace(day=1), day.replace(day=calendar.monthrange(day.year, day.month)[1])
    if kind == "quarterly":
        month = (day.month - 1) // 3 * 3 + 1
        return date(day.year, month, 1), date(day.year, month + 2, calendar.monthrange(day.year, month + 2)[1])
    if kind == "yearly":
        return date(day.year, 1, 1), date(day.year, 12, 31)
    raise ValueError("未知周期")


def period_id(start, kind):
    if kind == "weekly":
        year, week, _ = start.isocalendar()
        return f"{year}-w{week:02d}"
    if kind == "monthly":
        return start.strftime("%Y-%m")
    if kind == "quarterly":
        return f"{start.year}-q{(start.month - 1) // 3 + 1}"
    return str(start.year)


def aggregate(dailies, kind, start, end, generated_at):
    relevant = [r for r in dailies if start.isoformat() <= r["period"]["start"] <= end.isoformat()]
    dates = {r["period"]["start"] for r in relevant}
    missing = []
    day = start
    while day <= end:
        if day.isoformat() not in dates:
            missing.append(day.isoformat())
        day += timedelta(days=1)
    events = {}
    opportunities = {}
    for report in sorted(relevant, key=lambda r: r["generated_at"]):
        for item in report["items"]:
            current = copy.deepcopy(item)
            current["daily_report"] = report["id"]
            events[item["event_id"]] = current
        for opportunity in report.get("opportunities", []):
            current = copy.deepcopy(opportunity)
            current["daily_report"] = report["id"]
            if current.get("deadline") and datetime.fromisoformat(current["deadline"]) < datetime.fromisoformat(generated_at):
                current["status"] = "closed"
            opportunities[opportunity["opportunity_id"]] = current
    ranked = sorted(events.values(), key=lambda item: item["score"], reverse=True)
    selected = [item for domain in NEWS_DOMAINS for item in [x for x in ranked if news_domain(x["category"]) == domain][:15]]
    identifier = period_id(start, kind)
    return {"id": identifier, "kind": kind, "title": f"{identifier.upper()} · {KINDS[kind]}",
            "period": {"start": start.isoformat(), "end": end.isoformat()}, "generated_at": generated_at,
            "coverage": {"expected_days": (end - start).days + 1, "available_days": len(dates), "missing_dates": missing},
            "summary": f"本期已有 {len(dates)} 天日报，去重后收录 {len(events)} 个新闻事件，展示前 {len(selected)} 条，并整理 {len(opportunities)} 个机会，最多展示十个。内容来自已保存日报；已截止的机会标明关闭，缺失日期不补造新闻。",
            "items": selected,
            "opportunities": sorted(opportunities.values(), key=lambda item: item["score"], reverse=True)[:10],
            "daily_reports": [r["id"] for r in sorted(relevant, key=lambda r: r["period"]["start"])]}


def run(today, root=None):
    reports = load_reports() if root is None else load_reports(root)
    dailies = [r for r in reports if r["kind"] == "daily"]
    if not dailies:
        return []
    now = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
    saved = []
    for kind in list(KINDS)[1:]:
        periods = {bounds(date.fromisoformat(r["period"]["start"]), kind) for r in dailies}
        for start, end in sorted(periods):
            if end >= today:
                continue
            report = aggregate(dailies, kind, start, end, now)
            previous = next((r for r in reports if r["kind"] == kind and r["id"] == report["id"]), None)
            if previous and all(previous.get(k) == report.get(k) for k in ("items", "opportunities", "coverage", "daily_reports", "summary")):
                continue
            # 日报内容变更后重新汇总，旧的人工周期分析须重新核对，故不沿用。
            saved.append(str(save_report(report) if root is None else save_report(report, root)))
    return saved


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--today", default=datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat())
    args = parser.parse_args()
    for path in run(date.fromisoformat(args.today)):
        print(path)
