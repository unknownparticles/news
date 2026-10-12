"""采集公开候选资料；失败显式记录，绝不伪造新闻。"""
import argparse
import json
import os
import re
import sqlite3
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

from .common import CONFIG, ROOT, canonical_url, event_id


def fetch(url, token=None):
    headers = {"User-Agent": "PersonalIntelligence/1.0", "Accept": "application/json, application/rss+xml, application/atom+xml, text/xml"}
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read(3_000_001)
        if len(raw) > 3_000_000:
            raise ValueError("响应超过大小限制")
        return raw


def feed_items(raw, name, start, end):
    root = ET.fromstring(raw)
    out = []
    for node in root.iter():
        if node.tag.split("}")[-1] not in {"item", "entry"}:
            continue
        fields = {}
        for child in node:
            tag = child.tag.split("}")[-1]
            if tag == "link" and child.attrib.get("rel", "alternate") == "alternate":
                fields["link"] = child.attrib.get("href") or child.text
            elif tag != "link":
                fields[tag] = "".join(child.itertext()).strip()
            elif "link" not in fields:
                fields[tag] = child.text
        published = fields.get("pubDate") or fields.get("published") or fields.get("updated")
        if not published or not fields.get("link"):
            continue
        try:
            try:
                stamp = parsedate_to_datetime(published)
            except (ValueError, TypeError):
                stamp = datetime.fromisoformat(published.replace("Z", "+00:00"))
            if stamp.tzinfo is None or not start <= stamp <= end:
                continue
            url = canonical_url(fields["link"])
        except (ValueError, TypeError):
            continue
        text = fields.get("description") or fields.get("summary") or fields.get("content") or ""
        out.append({"event_id": event_id(url), "title": fields.get("title", ""), "url": url,
                    "source": name, "published_at": stamp.isoformat(), "content": re.sub(r"<[^>]+>", " ", text)[:12000]})
    return out[:30]


def collect(now, output, since=None):
    start = since or now - timedelta(hours=24)
    result = {"window_start": start.isoformat(), "window_end": now.isoformat(), "fetched_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
              "articles": [], "repositories": [], "aggregators": [], "source_results": []}
    def attempt(name, url, handler, token=None):
        try:
            raw = fetch(url, token)
            count = handler(raw)
            result["source_results"].append({"name": name, "url": url, "ok": True, "count": count})
        except Exception as exc:
            # 不记录完整请求对象、响应正文或凭据。
            failure = {"name": name, "url": url, "ok": False, "error": type(exc).__name__}
            if isinstance(exc, urllib.error.HTTPError):
                failure["http_status"] = exc.code
                failure["retry_after"] = exc.headers.get("Retry-After")
            result["source_results"].append(failure)
    for source in CONFIG["rss"]:
        def add_feed(raw, source=source):
            items = feed_items(raw, source["name"], start, now)
            result["articles"].extend(items)
            return len(items)
        attempt(source["name"], source["url"], add_feed)
    urls = list(CONFIG["aihot"])
    if now.weekday() == 0:
        urls.append("https://aihot.news/api/v1/weeklies/latest")
    for url in urls:
        def add_aggregate(raw, url=url):
            data = json.loads(raw)
            if not isinstance(data, dict) or data.get("schemaVersion") != 1:
                raise ValueError("聚合接口结构错误")
            if "items" in data:
                if not isinstance(data["items"], list):
                    raise ValueError("聚合条目结构错误")
                filtered = []
                for item in data["items"]:
                    stamp = datetime.fromisoformat(item["publishedAt"].replace("Z", "+00:00"))
                    if stamp.tzinfo and start <= stamp <= now:
                        filtered.append(item)
                data["items"] = filtered
                count = len(filtered)
            else:
                report = data.get("report")
                if not isinstance(report, dict) or not (report.get("date") or report.get("periodEnd")):
                    raise ValueError("聚合报告日期缺失")
                count = sum(len(s.get("items", [])) for s in report.get("sections", []))
            result["aggregators"].append({"url": url, "payload": data, "requires_date_and_original_source_check": True})
            return count
        attempt("AIHOT", url, add_aggregate)
    from urllib.parse import urlencode
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    for query in CONFIG["github_queries"]:
        url = "https://api.github.com/search/repositories?" + urlencode({"q": query + " created:>=" + (now - timedelta(days=30)).date().isoformat() + " stars:>=3 archived:false fork:false", "sort": "updated", "order": "desc", "per_page": 5})
        def add_repos(raw):
            data = json.loads(raw)
            if "items" not in data or data.get("incomplete_results"):
                raise ValueError("仓库搜索不完整")
            for repo in data["items"]:
                if datetime.fromisoformat(repo["created_at"].replace("Z", "+00:00")) > now:
                    continue
                result["repositories"].append({k: repo.get(k) for k in ("id", "full_name", "html_url", "description", "created_at", "pushed_at", "updated_at", "stargazers_count", "forks_count", "license", "topics", "archived")})
            return len(data["items"])
        attempt("GitHub " + query, url, add_repos, token)
    result["articles"] = list({item["event_id"]: item for item in result["articles"]}.values())
    result["repositories"] = list({item["id"]: item for item in result["repositories"]}.values())
    output.parent.mkdir(parents=True, exist_ok=True)
    # 每日快照保留本地，用于后续计算增长，不上传公开站点。
    with sqlite3.connect(output.parent / "state.sqlite3") as db:
        db.execute("CREATE TABLE IF NOT EXISTS repository_snapshots (repo_id INTEGER, day TEXT, stars INTEGER, forks INTEGER, PRIMARY KEY(repo_id, day))")
        for repo in result["repositories"]:
            day = now.date().isoformat()
            previous = db.execute("SELECT stars, day FROM repository_snapshots WHERE repo_id=? AND day<=? ORDER BY day DESC LIMIT 1", (repo["id"], (now - timedelta(days=7)).date().isoformat())).fetchone()
            repo["star_growth"] = None if previous is None else {"since": previous[1], "delta": repo["stargazers_count"] - previous[0]}
            db.execute("INSERT OR REPLACE INTO repository_snapshots VALUES (?, ?, ?, ?)", (repo["id"], day, repo["stargazers_count"], repo["forks_count"]))
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    if not any(s["ok"] for s in result["source_results"]):
        raise RuntimeError("全部采集失败，已保存失败记录；不得发布成功日报")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", help="带时区的采集截止时间，默认当前北京时间")
    parser.add_argument("--since", help="带时区的采集开始时间")
    args = parser.parse_args()
    now = datetime.fromisoformat(args.as_of) if args.as_of else datetime.now(ZoneInfo("Asia/Shanghai"))
    since = datetime.fromisoformat(args.since) if args.since else None
    if now.tzinfo is None or (since and (since.tzinfo is None or since >= now)):
        parser.error("起止时间必须带时区，开始时间必须早于结束时间")
    result = collect(now, ROOT / ".local/candidates.json", since)
    print(json.dumps({"articles": len(result["articles"]), "repositories": len(result["repositories"]), "sources": result["source_results"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
