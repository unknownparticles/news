"""固定的本地自动化入口；公开资料仍须核对后才能导入。"""
import argparse
import ipaddress
import json
import re
import subprocess
import sys
import time
import urllib.error
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.common import event_id, load_reports, safe_url, validate_report
from src.competitions import validate_catalog

REPO = "unknownparticles/news"
SITE = "https://alunapp.cn/news/"
PYTHON = sys.executable
TZ = ZoneInfo("Asia/Shanghai")
PUBLIC_ROOTS = {"src", "scripts", "tests", "config", "competitions", "reports", "docs", "web", ".github"}
PUBLIC_FILES = {"AGENTS.md", "README.md", "AUTOMATION.md", "DESIGN.md", ".gitignore"}
PRIVATE_MARKERS = ("/" + "Users" + "/", "-----BEGIN " + "PRIVATE KEY-----")
TOKEN = re.compile(r"(?:ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|sk-proj-[A-Za-z0-9_-]{20,})")


def command(*args, timeout=600):
    """只执行预先写定的参数列表，不执行 shell 或来源正文。"""
    result = subprocess.run(list(args), cwd=ROOT, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=timeout)
    if result.returncode:
        # 错误保留操作名与诊断，不回显整个命令或环境变量。
        raise RuntimeError(f"{args[0]} 执行失败：{result.stderr.strip() or result.stdout.strip()}")
    return result.stdout.strip()


def changed_paths():
    values = command("git", "diff", "--name-only", "-z", "HEAD").split("\0")
    values += command("git", "ls-files", "--others", "--exclude-standard", "-z").split("\0")
    return sorted(set(filter(None, values)))


def check_public_files(paths):
    for name in paths:
        path = Path(name)
        if path.is_absolute() or ".." in path.parts or not (
            path.parts[0] in PUBLIC_ROOTS or name in PUBLIC_FILES
        ) or any(part.startswith(".env") or part in {".local", ".codex", ".agents"} for part in path.parts):
            raise ValueError("存在公开提交范围以外的文件，已保留，需人工处理")
        file = ROOT / path
        if file.is_symlink():
            raise ValueError("公开提交不接受符号链接")
        if file.exists():
            content = file.read_text()
            # 文档和测试中可出现字段名；真正的本机路径和令牌不得公开。
            if any(marker in content for marker in PRIVATE_MARKERS) or TOKEN.search(content):
                raise ValueError("公开文件检查未通过，未暂存或推送")


def repository():
    remote = command("git", "remote", "get-url", "origin")
    if remote not in {"https://github.com/unknownparticles/news.git", "git@github.com:unknownparticles/news.git"}:
        raise ValueError("远程仓库与授权发布目标不一致")
    if command("git", "branch", "--show-current") != "main":
        raise ValueError("自动发布仅在主分支运行")


def save_changes(message, publish_only=False):
    paths = changed_paths()
    if not paths:
        return False
    check_public_files(paths)
    if publish_only and any(Path(p).parts[0] not in {"reports", "docs", "competitions"} for p in paths):
        raise ValueError("存在程序或配置改动，应先单独检查并提交，再发布内容")
    command("git", "add", "--", *paths)
    command("git", "commit", "-m", message)
    return True


def prepare():
    repository()
    save_changes("保存自动运行前已有改动")
    command("git", "pull", "--ff-only", "origin", "main")
    today = datetime.now(TZ).date().isoformat()
    if not (ROOT / "reports/daily" / (today + ".json")).exists():
        dailies = sorted((r for r in load_reports() if r["kind"] == "daily"), key=lambda r: r["period"]["end"])
        args = [PYTHON, "-m", "src.collect"]
        if dailies and dailies[-1].get("collection_window"):
            args += ["--since", dailies[-1]["collection_window"]["end"]]
        print(command(*args), flush=True)
    else:
        print("当天日报已存在，跳过重复新闻采集", flush=True)
    print(command(PYTHON, "-m", "src.competitions", "--discover"), flush=True)
    print("候选保留在本地；核对原文后写入日报与竞赛审核文件。", flush=True)


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.skip = 0
        self.current = None
        self.parts = []
        self.paragraphs = []
        self.links = []
        self.ids = set()
        self.meta = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {"script", "style", "noscript"}:
            self.skip += 1
        if self.skip:
            return
        if tag == "meta":
            self.meta[attrs.get("property") or attrs.get("name")] = attrs.get("content")
        if attrs.get("id"):
            self.ids.add(attrs["id"])
        self.links.extend(attrs[k] for k in ("href", "src") if attrs.get(k))
        if tag in {"p", "li", "h1", "h2", "h3"}:
            self.current, self.parts = tag, []

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"}:
            self.skip = max(0, self.skip - 1)
        if tag == self.current:
            text = " ".join("".join(self.parts).split())
            if text:
                self.paragraphs.append(text)
            self.current = None

    def handle_data(self, value):
        if self.current and not self.skip:
            self.parts.append(value)


def read_sources(urls):
    from src.collect import fetch
    destination = ROOT / ".local/evidence"
    destination.mkdir(parents=True, exist_ok=True)
    failures = []
    for url in urls:
        safe_url(url)
        host = urlsplit(url).hostname
        try:
            ipaddress.ip_address(host)
        except ValueError:
            if "." not in host or host.endswith((".local", ".localhost", ".internal")):
                raise ValueError("只读取公开 HTTPS 新闻地址")
        else:
            raise ValueError("原文读取不接受直接的网络地址")
        try:
            parser = Page()
            parser.feed(fetch(url).decode("utf-8", errors="replace"))
            if not parser.paragraphs:
                raise ValueError("没有可读正文，需要浏览器核对")
            result = {"url": url, "checked_at": datetime.now(TZ).isoformat(),
                      "published": parser.meta.get("article:published_time") or parser.meta.get("date"),
                      "paragraphs": parser.paragraphs,
                      "links": [urljoin(url, link) for link in parser.links if urljoin(url, link).startswith("https://")]}
            path = destination / (event_id(url) + ".json")
            path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
            print(f"已保存本地原文：{path.relative_to(ROOT)}", flush=True)
        except Exception as error:
            failure = {"url": url, "error": type(error).__name__}
            if isinstance(error, urllib.error.HTTPError):
                failure["http_status"] = error.code
            failures.append(failure)
    (destination / "last-read.json").write_text(json.dumps({"failures": failures}, ensure_ascii=False, indent=2) + "\n")
    if failures:
        raise RuntimeError("部分原文读取失败，详情保留本地；不得更新相应核验时间")


def audit_links():
    root = (ROOT / "docs").resolve()
    pages = {}
    for path in root.rglob("*.html"):
        page = Page()
        page.feed(path.read_text())
        pages[path] = page
    count = 0
    for path, page in pages.items():
        for link in page.links:
            parts = urlsplit(link)
            if parts.scheme or parts.netloc:
                continue
            target_path = unquote(parts.path)
            if target_path.startswith("/news/"):
                target = root / target_path.removeprefix("/news/")
            elif target_path.startswith("/"):
                target = root / target_path.lstrip("/")
            else:
                target = path.parent / target_path if target_path else path
            target = target.resolve()
            if not target.is_relative_to(root):
                raise ValueError("内部链接超出站点范围")
            if target.is_dir():
                target /= "index.html"
            if not target.exists() or (parts.fragment and target in pages and unquote(parts.fragment) not in pages[target].ids):
                raise ValueError(f"内部链接失效：{path.relative_to(root)}")
            count += 1
    print(f"链接检查通过：{len(pages)} 个页面、{count} 个内部引用", flush=True)


def check():
    for report in load_reports():
        validate_report(report)
    validate_catalog(json.loads((ROOT / "competitions/catalog.json").read_text()))
    check_public_files(changed_paths())
    print(command(PYTHON, "-m", "unittest", "discover", "-s", "tests"), flush=True)
    print(command(PYTHON, "-m", "src.build"), flush=True)
    audit_links()
    command("git", "diff", "--check")
    check_public_files(changed_paths())


def import_reviewed(today):
    target = ROOT / "reports/daily" / (today + ".json")
    if not target.exists():
        draft = ROOT / ".local/daily.json"
        if not draft.exists():
            raise ValueError("当天日报缺失；请先核对候选并生成本地日报，不生成占位新闻")
        report = validate_report(json.loads(draft.read_text()))
        if report["kind"] != "daily" or report["id"] != today or report["period"] != {"start": today, "end": today}:
            raise ValueError("审核文件日期与当天不一致，拒绝误发旧日报")
        print(command(PYTHON, "-m", "src.publish_report", str(draft)), flush=True)
    draft_catalog = ROOT / ".local/competition-reviewed.json"
    if draft_catalog.exists():
        catalog = validate_catalog(json.loads(draft_catalog.read_text()))
        if datetime.fromisoformat(catalog["checked_at"]).astimezone(TZ).date().isoformat() != today:
            raise ValueError("竞赛审核文件已过期，需本次重新核验")
        (ROOT / "competitions/catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n")


def verify_deployment():
    sha = command("git", "rev-parse", "HEAD")
    run = None
    for attempt in range(12):
        runs = json.loads(command("gh", "run", "list", "-R", REPO, "--workflow", "pages.yml", "--commit", sha,
                                  "--limit", "1", "--json", "databaseId,status,conclusion,headSha"))
        if runs:
            run = runs[0]
            break
        if attempt < 11:
            time.sleep(5)
    if not run:
        raise RuntimeError("尚未找到本次提交的部署记录，保留提交，下次重试 verify")
    if run["status"] != "completed":
        command("gh", "run", "watch", str(run["databaseId"]), "-R", REPO, "--exit-status", "--interval", "10", timeout=300)
        run = json.loads(command("gh", "run", "view", str(run["databaseId"]), "-R", REPO, "--json", "conclusion,headSha"))
    if run["conclusion"] != "success" or run["headSha"] != sha:
        raise RuntimeError("本次提交的部署尚未成功，不宣称已上线")
    # 逐字核对构建结果，防止只检查到旧页面的成功状态码。
    reports = load_reports()
    latest = max((r for r in reports if r["kind"] == "daily"), key=lambda r: r["period"]["end"])
    paths = ["index.html", "archive/competitions.html", f"reports/daily/{latest['id']}.html"]
    weekly = [r for r in reports if r["kind"] == "weekly"]
    if weekly:
        paths.append(f"reports/weekly/{max(weekly, key=lambda r: r['period']['end'])['id']}.html")
    for path in paths:
        body = command("curl", "--fail", "--silent", "--show-error", "--location", "--proto", "=https",
                       "--max-time", "25", SITE + path + "?v=" + sha, timeout=30)
        if body != (ROOT / "docs" / path).read_text().strip():
            raise RuntimeError("公开页面与本次构建不一致，保留成果，下次重试 verify")
    print("部署和公开页面核对成功：" + SITE, flush=True)


def publish():
    repository()
    import_reviewed(datetime.now(TZ).date().isoformat())
    print(command(PYTHON, "-m", "src.periods"), flush=True)
    check()
    save_changes("发布情报并更新竞赛与周期汇总", publish_only=True)
    command("git", "pull", "--ff-only", "origin", "main")
    command("git", "push", "origin", "main")
    verify_deployment()
    if changed_paths():
        raise RuntimeError("运行期间出现其他改动，已保留，需核对")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    for action in ("prepare", "check", "publish", "verify"):
        sub.add_parser(action)
    reader = sub.add_parser("read")
    reader.add_argument("urls", nargs="+")
    args = parser.parse_args()
    if args.action == "read":
        read_sources(args.urls)
    else:
        {"prepare": prepare, "check": check, "publish": publish, "verify": verify_deployment}[args.action]()


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
