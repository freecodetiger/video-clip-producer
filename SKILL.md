---
name: video-clip-producer
description: URL-first long-video clip skill for YouTube and Bilibili links, or already-downloaded local sources. Downloads or adopts HD video, fetches subtitles with login-state cookies, ranks high-traffic candidates, and after user confirmation can continue into bilingual subtitle rendering, B-roll packaging, and final clip output. Use whenever the user gives a YouTube/Bilibili link, a local source file, asks for subtitle extraction, wants ranked short-video cut candidates, or needs the final rendered clip package.
---

# Video Clip Producer

这个 skill 的主入口是 **视频 URL 或已下载本地源文件**。
默认流程是：

0. 先主动确认交互模式和 B-roll 素材状态
1. 识别平台与环境
2. 抓取或接管高清视频和字幕
3. 解析字幕并发现候选片段
4. 按传播潜力排序
5. 根据交互模式决定是否让用户确认 Top 1 / Top 2 / Top 3
6. 用户确认后，再继续到 B-roll、双语字幕和最终成片

如果用户已经明确要求“直接出成片 / 直接生成带 B-roll 成片 / Agent 自动选”，可以跳过候选确认，只保留必要的选择依据和片段校验后进入渲染。

本 skill 默认目标是 **冲流量**，但前提是不编造、不扭曲原意。

## 核心定位

这个 skill 不是“简单截取精彩片段”，而是一个完整工作流：

- 先把来源视频和字幕拿稳
- 再找最值得剪的候选段
- 再让用户确认要哪一段
- 最后才进入实际成片和落盘

如果用户已经手动下载了 `source.mp4` 或字幕文件，直接接管，不要强行重新下载。

## 何时使用

- 用户给的是 YouTube / Bilibili 链接
- 用户给的是本地已下载视频文件
- 用户要下载高清视频并抓字幕
- 用户要找“最值得剪”的片段，而不是简单摘字幕
- 用户关心情绪、争议、金句、立场输出、强 hook
- 用户希望先推荐片段，再决定剪哪个
- 用户有本地 B-roll 素材库，要做抖音励志风包装
- 用户希望用户确认后继续生成最终切片文件、双语字幕和文案

## 必须先做的环境检查

在开始之前，先确认这些条件。这里是**能力检查**，不是装机检查。

原则：

- 先探测现有环境能不能完成当前任务
- 先复用 PATH、用户已有安装、已知绝对路径
- 只有在“当前任务确实缺能力”时才补缺，不主动新装臃肿环境
- 不为了通过检查而引入新的虚拟环境、conda、容器或包管理层，除非用户明确要求

按任务分层检查：

- 通用：Agent 工具、shell、文件读写、输出目录可写
- 摄取阶段：`python3`、`yt-dlp`、`ffmpeg`、`ffprobe`
- 字幕烧录阶段：`ffmpeg` 支持 `subtitles`，并且当前渲染路径需要时才要求 `libass`
- 文字叠加阶段：只有用到 `drawtext` 时才检查
- 登录态字幕：只有抓字幕时才检查 cookies
- B-roll：只有要做分镜时才要求 B-roll 目录可读

优先运行：

```bash
python3 scripts/check_env.py --json
```

如果这个检查脚本要求过多能力，先用任务实际需要的能力做二次判断，不要因为某个可选能力缺失就把整套环境判死。

## 输入优先级

1. YouTube / Bilibili URL
2. 用户已下载的本地视频文件
3. 本地字幕或转写文件兜底

如果字幕抓取失败，不要默认改成本地大模型转写；先确认 cookies / 登录态 / 字幕源。
如果用户已经提供了可用字幕，不要重做一遍转写。
如果用户明确要求直接成片，不要再强制回到候选列表阶段。

## 工作流

### 0) 先确认交互模式和 B-roll 素材状态

每次加载本 skill 后，一开始就主动问清楚两个问题：

1. 片段选择模式：要我给 Top 候选让你挑，还是我按 skill 自动选择最值得剪的一段并直接继续？
2. B-roll 素材状态：你是否已经准备本地 B-roll 素材目录？

推荐提问：

> 片段选择你希望怎么走：A. 我给 Top 候选你来挑；B. 我自动选择最值得剪的一段并直接做成片。另一个问题：你有本地 B-roll 素材目录吗？如果没有，我会默认从网络找免版权的震撼自然素材，并把素材和来源清单落到输出目录。

如果用户选择 Agent 自动选，后续不要再停住要求用户从 Top 1 / Top 2 / Top 3 中选择。仍需输出 Top 候选和自动选择依据，但输出后直接继续剪辑策略、素材获取和渲染。

如果用户没有素材，或用户没有回答但任务明显需要最终成片 / 带 B-roll，默认进入自动素材获取，不要停在“无素材可用”。自动素材规则见 [broll-sourcing.md](references/broll-sourcing.md)。

如果用户提供本地素材目录，先接管本地素材；如果本地素材数量或主题不够，再自动补免版权自然素材。

### 1) 先做环境检测

先跑环境检查，再决定是 URL 摄取还是本地接管。

### 2) 识别并摄取来源

用 `scripts/ingest_source.py` 完成：

- 平台识别：YouTube / Bilibili / local fallback
- 高清视频下载
- 字幕抓取
- 登录态复用：`--cookies-from-browser` 或 `--cookies`
- 生成下载清单与字幕路径
- Bilibili 下载后用 `ffprobe` 校验视频轨和音轨，避免容器成功但视频轨异常短

当用户已经给了本地视频时，直接接管该文件并继续：

- 视频文件
- 字幕文件
- `manifest.json`

不要要求用户重新下载同一个文件。

优先下载最佳可用画质，并优先拿手动字幕；没有手动字幕时再用自动字幕。

处理 Bilibili 时，必须阅读 [source-ingestion.md](references/source-ingestion.md) 的 Bilibili 实战规则。默认优先 H.264 mp4 轨道和登录态 cookies；如果下载后视频轨明显短于音轨，删除坏文件并用 H.264 fallback 重拉，不要继续拿坏源渲染。

### 3) 规范化字幕

把下载到的字幕转成统一段落数据，再交给评分器。

优先使用：

```bash
python3 scripts/parse_transcript.py --input <subtitle-file> --json
```

如果源字幕存在时间戳，后续字幕渲染必须优先继承这些时间戳。
不要因为想要“滚动字幕”就把整段字幕重新估时。

### 4) 发现候选片段并排序

用评分器找以下片段：

- 情绪化表达强
- 观点尖锐、容易引发讨论
- 有反转、冲突、态度表达
- 有明确金句、总结句、立场句
- 适合作为开头强 hook
- 适合作为结尾落点

先排除会扭曲原意的片段，再按传播潜力排序。

优先使用：

```bash
python3 scripts/rank_segments.py --input <transcript-json> --mode traffic --top-k 5
```

输出时至少给 Top 3，建议 Top 5。
先给推荐列表，再停住等用户确认。

### 5) 先输出推荐列表，再停住等用户确认

默认 `user_select` 模式下，必须先给用户看候选列表，至少 Top 3，建议 Top 5。

`agent_auto_select` 模式下，也要输出候选列表和自动选择依据，但不要等待用户确认，直接把 Top 1 或综合最优片段固化为渲染片段。

`user_select` 模式必须明确加一句：

> 请从 Top 1 / Top 2 / Top 3 中选择一个片段，我再继续输出具体剪辑方案。

`agent_auto_select` 模式必须明确写出：

> 我将自动选择 Top X 作为最终片段，并继续生成成片。

### 6) 用户确认后再给剪辑策略

用户选定某个片段后，再输出：

- 开头 hook 建议
- 中段节奏推进建议
- 转折点建议
- 结尾收束建议
- B-roll 插入建议
- 转场建议
- 字幕强调建议
- 最终产物目录建议

默认风格：

- 开头不要硬切
- 转场偏硬切 / 闪白 / 轻推拉
- 金句点切强画面
- 结尾落在情绪或立场上
- 字幕要高可读，不压画面

如果用户明确要落盘成片，继续进入实际渲染：

- 先生成 A-roll 或分镜版
- 再叠加 B-roll
- 再烧录双语字幕
- 再导出 `配文.md` 和 `推荐标题.md`
- 最后写 `render_manifest.json`

渲染态要显式记录字幕布局参数，至少包括：

- 字幕底边距
- 最大单行长度
- 断句策略
- 字幕是否需要两行拆分

优先调用：

```bash
python3 scripts/render_clip.py --spec <render-spec.json>
```

如需先检查命令，不落盘：

```bash
python3 scripts/render_clip.py --spec <render-spec.json> --dry-run
```

如需生成 spec 模板：

```bash
python3 scripts/render_clip.py --print-spec-template
```

渲染完成后，再用下面的校验入口检查一次：

```bash
python3 scripts/verify_render.py --output-dir <clip-output-dir> --video <final.mp4> --ass <双语字幕.ass> --srt <双语字幕.srt> --manifest <render_manifest.json>
```

### 7) 字幕对齐策略

字幕是这类任务的高风险点，必须按下面顺序处理：

1. 先用源字幕时间戳
2. 如果整体偏晚或偏早，用全局 offset 修正
3. 如果少数句子仍不准，再做单句 patch
4. 如果源字幕缺失或质量太差，最后才考虑强制对齐

默认优先级：

- 句子一开口字幕就出现
- 宁可略早，也不要整体偏晚
- 允许连续滚动，但不要为了滚动破坏口型和可读性
- 中文主字幕，英文副字幕

## B-roll 规则

如果用户提供本地 B-roll 素材库，把它当成可调用资源池。
如果用户没有提供，本 skill 默认主动获取免版权自然素材，优先使用震撼、抽象、情绪强的自然画面。不要因为没有本地素材就放弃 B-roll。

优先标注三类用途：

- 开场压场
- 中段转折
- 结尾收束

优先匹配：

- 极光
- 雷暴
- 暴雨
- 海浪
- 海啸感
- 雪山
- 峡谷
- 云海
- 日出
- 奔流
- 风沙

B-roll 的目标不是喧宾夺主，而是：

- 把情绪压起来
- 给金句留空间
- 避免整段画面单调
- 保护字幕的可读性

自动素材必须写入 `asset_manifest.json`，至少记录素材文件、来源 URL、许可/来源说明、关键词、用途和下载时间。

## 输出格式

候选列表至少包含：

- 排名
- 起止时间
- 时长
- 片段标题
- 核心观点 / 情绪点
- 总分
- 内容价值
- 情绪张力
- 争议度
- 金句密度
- hook
- 视觉包装性
- 推荐 B-roll
- 推荐标题方向
- 为什么值得剪

最终产物还应写清楚：

- 片段目录
- 成片文件名
- 双语字幕文件名
- 文案文件名
- 标题建议文件名
- 是否已做字幕提前或修正

## 最终产物目录

最终切片产物统一落在一个视频级根目录下，不要把最终成片、字幕、配文散落在临时目录里。

推荐结构见 [output-layout.md](references/output-layout.md)。
渲染和校验流程见 [render-pipeline.md](references/render-pipeline.md)。
字幕校准规则见 [subtitle-alignment.md](references/subtitle-alignment.md)。
最终交付前的检查见 [verification-checklist.md](references/verification-checklist.md)。

## 评分模式

默认按“冲流量”权重：

- 情绪张力：25
- 争议/讨论度：20
- 金句密度：15
- 开头 hook 潜力：15
- 视觉包装性：15
- 标题可传播性：10

可按目标重加权：

- 冲争议：提高争议 / 立场 / 冲突
- 冲共鸣：提高情绪 / 内容价值
- 冲励志：提高内容价值 / 结尾收束 / 视觉包装
- 平衡：各项均衡，但仍保留传播优先级

## 常见坑

- 不要编造原视频没说过的话
- 不要断章取义到扭曲事实意义
- 不要只追热度，忽略原意准确性
- 不要在未确认前直接进入剪辑方案
- 不要让 B-roll 抢过字幕可读性
- 不要默认本地转写优先于字幕抓取
- 不要因为想滚动字幕就重新估时整段字幕
- 不要把临时文件混进最终交付目录

## 验证清单

在给出推荐前，确认：

- 环境检查通过
- URL 已识别并成功摄取，或本地源已接管
- 视频文件已落盘
- 字幕文件已抓到或明确说明缺失原因
- transcript 可读
- 候选片段都能独立成立
- 排序与目标模式一致
- 每个候选都解释了为什么值得剪
- 已停在用户确认门
- 已说明 B-roll 的包装位置
- 如果进入成片，确认字幕对齐策略已选定
- 如果进入成片，确认最终目录结构已明确
- 如果进入成片，确认完成了最少一次抽帧或预览检查
- 如果进入成片，确认 render spec 已生成
- 如果进入成片，确认可先 dry-run 再正式执行
- 如果进入成片，确认有一次 verify_render 检查

## 参考文件

- [environment-checklist.md](references/environment-checklist.md)
- [source-ingestion.md](references/source-ingestion.md)
- [broll-sourcing.md](references/broll-sourcing.md)
- [output-layout.md](references/output-layout.md)
- [scoring-rubric.md](references/scoring-rubric.md)
- [output-format.md](references/output-format.md)
- [render-pipeline.md](references/render-pipeline.md)
- [render-spec.md](references/render-spec.md)
- [subtitle-alignment.md](references/subtitle-alignment.md)
- [verification-checklist.md](references/verification-checklist.md)
- `scripts/render_clip.py`
- `scripts/verify_render.py`
