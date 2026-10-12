"""将经核验的日报导入归档；默认拒绝覆盖已发布报告。"""
import argparse
import json

from .common import ROOT, load_reports, save_report, validate_report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("--replace", action="store_true", help="显式修订已有报告")
    args = parser.parse_args()
    from pathlib import Path
    report = validate_report(json.loads(Path(args.input).read_text()))
    if report["kind"] != "daily":
        parser.error("周期报告应由 src.periods 从日报生成")
    target = ROOT / "reports/daily" / (report["id"] + ".json")
    if target.exists() and not args.replace:
        parser.error("此日报已归档，修订须显式使用 --replace")
    previous = [r for r in load_reports() if r["kind"] == "daily" and r["id"] != report["id"]]
    seen = {item["event_id"] for r in previous for item in r["items"]}
    duplicates = [item["headline"] for item in report["items"] if item["event_id"] in seen and not item.get("update_reason")]
    if duplicates:
        parser.error("重复事件必须说明实质更新：" + "、".join(duplicates))
    seen_opportunities = {opportunity["opportunity_id"] for r in previous for opportunity in r.get("opportunities", [])}
    duplicates = [opportunity["headline"] for opportunity in report.get("opportunities", []) if opportunity["opportunity_id"] in seen_opportunities and not opportunity.get("update_reason")]
    if duplicates:
        parser.error("重复机会必须说明实质更新：" + "、".join(duplicates))
    print(save_report(report))
