# 个人情报观察室

公开站点：<https://alunapp.cn/news/>。本仓库 Pages 继承账号现有自定义域名，GitHub 默认地址 <https://unknownparticles.github.io/news/> 会使用该域名。

主页关联所有日报、周报、月报、季报和年报；支持分类筛选、关键词搜索和历史归档。每条重点包含来源证据、核验状态、相关性和下一步建议。日报最多五条，允许零条。

## 运行与发布

使用 Python 3.10 及以上，仅依赖标准库：

```bash
python3 -m src.collect
# 分析 .local/candidates.json，核对原文后，按下方结构写入 .local/daily.json
python3 -m src.publish_report .local/daily.json
python3 -m src.periods
python3 -m unittest discover -s tests
python3 -m src.build
```

`reports/` 是公开报告的唯一内容来源；`docs/` 是生成的网页。推送 `main` 后，GitHub Actions 自动验证并部署 GitHub Pages。需要仓库 Pages 设置选择 GitHub Actions；流程只上传 `docs/`，不上传本地候选池、反馈或数据库。

修改前先检查工作区，有改动则用纯中文信息提交保存。完成后测试、生成站点、提交中文信息并正常推送；不使用强制推送。修改失败只撤销本次修改。

## 日报数据约定

以下仅是结构示例，不是真实新闻，不要直接发布：

```json
{
  "id": "2026-10-12",
  "kind": "daily",
  "title": "2026-10-12 · 日报",
  "period": {"start": "2026-10-12", "end": "2026-10-12"},
  "generated_at": "2026-10-12T08:30:00+08:00",
  "collection_window": {"start": "2026-10-11T08:30:00+08:00", "end": "2026-10-12T08:30:00+08:00"},
  "coverage": {"expected_days": 1, "available_days": 1, "missing_dates": []},
  "summary": "本期筛选说明。",
  "source_failures": [],
  "items": [{
    "event_id": "stable-event-identifier",
    "headline": "事件标题",
    "summary": "有证据支持的事实摘要；部分未确认的结论单独写明。",
    "category": "AI 编程",
    "verification_status": "unverified",
    "score": 80,
    "relevance": "面向开发者或小型工作室的实际影响。",
    "action": "可执行的下一步。",
    "sources": [{
      "label": "原文名称",
      "url": "https://example.com/news",
      "excerpt": "支持上述结论的真实原文摘录。",
      "checked_at": "2026-10-12T08:25:00+08:00"
    }]
  }]
}
```

分类和官方来源地址范围见 `config/sources.json`。核验状态：`official_confirmed`（官方已确认）、`project_documented`（项目文档支持）、`unverified`（未核实）、`conflicting`（冲突）。地址范围校验只能防止误填，不能证明摘录支持全部结论；发布者仍需核对具体事实。官方来源只证明其明确陈述的内容，性能和商业效果不能由此推定。

同一事件跨来源合并，并复用稳定的 `event_id`；仅删除追踪参数不能自动识别同一事件。重复新闻默认拒绝导入，确有实质变化时提供 `update_reason`。许可证未知的仓库只作为研究候选；商业推荐需 `commercial_status: eligible` 和公开 `license_evidence`，并明确未验证的部署成本与依赖限制。

## 自动化与周期规则

本聊天中的自动化每天北京时间 08:30 唤醒，采集并核验公开候选资料，生成日报、补齐已经结束的周期报告，更新主页，测试、提交并推送。实际生成和部署需要时间，不承诺页面精确在 08:30 完成更新。

- 日报：每日运行，默认最近二十四小时；运行中断后从最近日报采集截止时间继续，注明跨日窗口。
- 周报：周一汇总上一自然周（周一至周日）。
- 月报：每月首日汇总上月。
- 季报：一、四、七、十月首日汇总上一季度。
- 年报：一月一日汇总上一年。
- 错过首日后下次运行补齐已结束且有日报的周期；不生成从未有任何日报的历史周期。
- 汇总从已经归档的日报去重整理，保留证据与日报索引。当前自动汇总是重点事件回顾，不宣称得出了长期趋势。缺失日报日期显式列出。

本地自动化需要 Mac 开机、应用运行及可用的网络与 GitHub 写权限。GitHub Pages 部署由云端 Actions 执行。自动化失败时保留现有网页，不发布伪造成功内容。采集器只记录限流状态和 Retry-After；自动化在总截止时间内选择稍后重试或跳过该来源，不无限等待。

采集器支持可选环境变量 `GITHUB_TOKEN` 或 `GH_TOKEN`，仅向 GitHub API 使用令牌。`src.collect` 不自动加载 `.env`。AIHOT 结构和日期需运行时检查，过期的 latest 结果不能当作今天的新闻。GitHub Star 快照在 `.local/state.sqlite3`，无七天历史时增量为未知。模型使用当前 Codex 自动化的能力，不需要本项目另行配置模型网关。

个人反馈暂不采集 iMessage 回复。后续本地反馈必须使用固定报告编号加条目编号，影响推荐排序但不改变可信度；不得上传私人反馈或个人业务资料。

## 本地预览

```bash
python3 -m http.server 8000 --directory docs
```

打开 <http://localhost:8000/>。日报或周期报告失败时，不要覆盖已经发布的内容。可通过 Git 历史追溯和恢复报告。
