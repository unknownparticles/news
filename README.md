# 个人情报观察室

公开站点：<https://alunapp.cn/news/>。本仓库 Pages 继承账号现有自定义域名，GitHub 默认地址 <https://unknownparticles.github.io/news/> 会使用该域名。

主页直接展示科技前沿、金融市场、政治与政策、近期机会和全国 AI 竞赛，并关联所有日报、周报、月报、季报和年报。每个新闻领域独立收录，目标每日三至五条，每领域最多五条、合计最多十五条；机会最多三个，竞赛有独立数据库。原文链接直接展示，新闻不足时注明覆盖，不能凑数。

主页采用现代简报版式：首屏显示期次与三个领域的重点新闻，下面以可筛选的单列速览展示短标题、摘要、原文时间、来源与核验标记。桌面右侧提供本期阅读指南，手机按单栏阅读。点击新闻或机会进入独立详情页，阅读完整内容、影响分析、行动建议与原文链接。整期日报继续保留完整内容供集中阅读。

竞赛列表采用表格比较报名截止、状态、赛制、参与方式、费用和奖励，点击赛题或“详情”进入独立规则页。手机上表格可左右滚动。可选的 `short_headline`、`short_summary` 和竞赛 `short_name`、`cost_brief`、`prize_brief` 用于编辑精简展示，不能改变完整信息的含义；完整证据与限制保留在详情中。

## 运行与发布

使用 Python 3.10 及以上，仅依赖标准库：

```bash
python3 scripts/automation.py prepare
python3 scripts/automation.py read https://新闻原文地址
# 核对候选和原文，生成 .local/daily.json
# 竞赛人工核验结果可保存为 .local/competition-reviewed.json
python3 scripts/automation.py publish
```

固定脚本统一增量采集、竞赛发现、日期校验、周期汇总、测试构建、内部链接检查、中文提交、推送及部署核验。原文保存在 `.local/evidence/`，助手仍须判断证据是否支持结论。脚本不接受任意 Shell 命令，不执行新闻正文，不自动替用户报名。`check` 子命令只做本地检查；`verify` 只重试已推送内容的部署核验。公共页面必须与本次构建相符，不能只凭成功状态码宣称上线。

自动化使用固定入口可避免每天更换临时脚本导致重新授权。权限仍由运行时沙箱、命令规则和自动审查决定，skill 不能替代授权。优先在项目可写的沙箱运行本地操作，联网受限时只申请固定入口的具体子命令，不需要开放整个 Python 或全盘访问。首次允许的规则是否复用取决于宿主是否保存并加载；详细约定见 [自动化流程](AUTOMATION.md)。

原有 `python3 -m src.collect`、`src.competitions`、`src.publish_report`、`src.periods`、`src.build` 入口仍可用于独立排错。

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

分类和官方来源地址范围见 `config/sources.json`。核验状态：`official_confirmed`（官方已确认）、`media_reported`（媒体报道）、`project_documented`（项目文档支持）、`unverified`（未核实）、`conflicting`（冲突）。地址范围校验只能防止误填，不能证明摘录支持全部结论；发布者仍需核对具体事实。官方来源只证明其明确陈述的内容，性能和商业效果不能由此推定。政治表态、智库估算和已经生效的政策要分开表述，注明媒体归属。

三类前沿新闻必须提供带时区的 `published_at`，超过二十四小时的内容须用 `context_note` 明确说明回看或补采原因。默认优先近二十四小时新增内容，可从近七日重要官方公告补充前沿背景；禁止把旧报道改写为今日发布。

## 每日 GitHub 热榜与研究方向

每天北京时间 08:30 的现有自动化新增独立栏目：直接核对 [GitHub Trending 全语言日榜](https://github.com/trending?since=daily) 前十，保留原始排名、中文用途、研究方向、今日新增 Star、总 Star 和仓库链接。归纳三至五个方向并提供对应项目依据与学习或验证步骤。榜单反映近期关注度，上榜不代表新发布、学术质量或商业许可；不占新闻与机会名额。首页与当日日报展示，历史快照保留在日报。已有日报不补造历史热榜。

日报可选字段 `github_trending` 的结构如下（仅为格式，不是真实榜单；实际完整榜单需要十项及三至五段分析）：

```json
{
  "source_url": "https://github.com/trending?since=daily",
  "checked_at": "2026-10-27T08:25:00+08:00",
  "coverage_note": "格式示例，仅展示一项；实际不足十项时填写真实原因。",
  "items": [{
    "rank": 1,
    "repository": "example/project",
    "url": "https://github.com/example/project",
    "summary": "核对仓库文档后填写中文用途。",
    "direction": "核对后填写研究方向",
    "stars_today": null,
    "total_stars": null
  }],
  "analysis": ["点名对应仓库，说明方向、关注信号和下一步验证方法。"]
}
```

`checked_at` 必须属于日报的北京时间日期且不晚于生成时间。Star 未展示时填 `null`，不能填零或估算。不足十条必须写 `coverage_note`；完全失败保留空列表并记录来源失败，不用旧榜、周榜、关键词检索或总 Star 排名补齐。自动化由助手直接核验官方页面和项目文档，现有候选采集器的仓库搜索不等于 Trending。

## 全国 AI 竞赛

`competitions/catalog.json` 存储经过官方规则核验的公开赛题；`config/competitions.json` 配置天池、DataFountain、讯飞、百度 AI Studio 和金蝶等来源。采集命令将公开候选保存到 `.local/competition-candidates.json`，原始候选不直接成为报名推荐。公开竞赛库需校验后才生成 `docs/archive/competitions.html`。

首页优先展示允许社会人士、单人、线上参与且报名窗口有效的赛题。奖励赛、长期练习、学术评测分别标注；线上初赛不代表决赛也在线上。核对正式规则中的首轮报名、必须提交的材料截止与晋级条件，不能把复赛重新开放入口当作新选手可报名。官方字段与规则正文冲突时标为待确认；核验超过七天则停止作为可报名推荐。平台列表、详细规则、当前报名状态的覆盖程度分别标明。

竞赛字段包括 `registration_deadline`、`qualification_status`、`registration_status`、`individual_allowed`、`non_student_allowed`、`mode`、`rules_consistent`、费用、奖励、第一步和官方证据。当前报名或获奖的具体条件仍由本人在官网确认。公开数据库不能包含个人资料，个人筛选条件保留在 `.local/competition-profile.json`，不提交、不上传。采集与发布流程只搜集信息，不代为注册、报名、缴费、接受协议或提交作品。

数据库包含核验来源和局限，不能宣称已经穷尽全国所有赛事。百度、讯飞等需要浏览器加载的来源继续按官方页面补查；只读取到平台列表不等于确认了全部赛事资格。

`opportunities` 为独立列表，日报最多三个、周期报告最多十个。每个机会提供 `opportunity_id`、`headline`、`category`、`score`、`status`、`verification_status`、`signal`、`audience`、`first_step`、`risks`、`time_window` 和 `sources`。`status` 是 `research`（待验证）、`actionable`（可以开始验证）或 `closed`（窗口结束）。真实申请或活动有截止日时提供带时区的 `deadline`，不得把已经结束的窗口标为可行动。机会证据证明变化信号，不证明付费需求或投资回报；公开截止日、已上线状态和许可证也不能由模型编造。重复机会复用原编号，只有提供实质 `update_reason` 才再次收录。

同一事件跨来源合并，并复用稳定的 `event_id`；仅删除追踪参数不能自动识别同一事件。重复新闻默认拒绝导入，确有实质变化时提供 `update_reason`。许可证未知的仓库只作为研究候选；商业推荐需 `commercial_status: eligible` 和公开 `license_evidence`，并明确未验证的部署成本与依赖限制。

## 自动化与周期规则

本聊天中的自动化每天北京时间 08:30 唤醒，采集并核验公开候选资料，生成日报、补齐已经结束的周期报告，更新主页，测试、提交并推送。实际生成和部署需要时间，不承诺页面精确在 08:30 完成更新。

- 日报：每日运行，默认最近二十四小时；运行中断后从最近日报采集截止时间继续，注明跨日窗口。
- 周报：周一汇总上一自然周（周一至周日）。
- 月报：每月首日汇总上月。
- 季报：一、四、七、十月首日汇总上一季度。
- 年报：一月一日汇总上一年。
- 错过首日后下次运行补齐已结束且有日报的周期；不生成从未有任何日报的历史周期。
- 汇总从已经归档的日报去重整理，每个新闻领域最多十五条、共最多四十五条，并保留证据与日报索引。当前自动汇总是重点事件回顾，不宣称得出了长期趋势。缺失日报日期显式列出。

本地自动化需要 Mac 开机、应用运行及可用的网络与 GitHub 写权限。GitHub Pages 部署由云端 Actions 执行。自动化失败时保留现有网页，不发布伪造成功内容。采集器只记录限流状态和 Retry-After；自动化在总截止时间内选择稍后重试或跳过该来源，不无限等待。

采集器支持可选环境变量 `GITHUB_TOKEN` 或 `GH_TOKEN`，仅向 GitHub API 使用令牌。`src.collect` 不自动加载 `.env`。支持 gzip 和 deflate 解压，解压前后都限制响应大小；DeepMind 的压缩 RSS 能正确解析，HTTP 成功但非 RSS/Atom 的网页会明确报错。AIHOT 结构和日期需运行时检查，过期的 latest 结果不能当作今天的新闻。GitHub Star 快照在 `.local/state.sqlite3`，无七天历史时增量为未知。模型使用当前 Codex 自动化的能力，不需要本项目另行配置模型网关。

个人反馈暂不采集 iMessage 回复。后续本地反馈必须使用固定报告编号加条目编号，影响推荐排序但不改变可信度；不得上传私人反馈或个人业务资料。

## 设计说明

网站设计参考 Axios、TLDR 与 1440 的重点导读、短摘要和按需深入阅读，调研与设计取舍见 [设计调研](DESIGN.md)。使用本机系统字体，不依赖远程字体或新闻配图。

## 本地预览

```bash
python3 -m http.server 8000 --directory docs
```

打开 <http://localhost:8000/>。日报或周期报告失败时，不要覆盖已经发布的内容。可通过 Git 历史追溯和恢复报告。
