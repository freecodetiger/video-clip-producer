---
name: video-clip-producer
description: URL-first long-video clip skill for YouTube and Bilibili links, or already-downloaded local sources. Downloads or adopts HD video, fetches subtitles with login-state cookies, ranks high-traffic candidates, and after user confirmation can continue into bilingual subtitle rendering, B-roll packaging, and final clip output. Use whenever the user gives a YouTube/Bilibili link, a local source file, asks for subtitle extraction, wants ranked short-video cut candidates, or needs the final rendered clip package.
---

# Video Clip Producer

这个 skill 的主入口是 **视频 URL 或已下载本地源文件**。
默认流程是：

1. 识别平台与环境
2. 抓取或接管高清视频和字幕
3. 解析字幕并发现候选片段
4. 按传播潜力排序
5. 先让用户确认 Top 1 / Top 2 / Top 3
6. 用户确认后，再继续到 B-roll、双语字幕和最终成片

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

在开始之前，先确认这些条件：

- Agent 工具正常
- shell 和文件系统可用
- `python3` 可用
- `yt-dlp` 可用
- `ffmpeg` / `ffprobe` 可用
- `ffmpeg` 支持 `subtitles`
- `ffmpeg` 支持 `drawtext`
- `ffmpeg` 编译时包含 `libass`
- 输出目录可写
- 如果要抓登录态字幕，cookies 可用
- 如果要做分镜，B-roll 目录存在且可读

优先运行：

```bash
python3 scripts/check_env.py --json
```

## 输入优先级

1. YouTube / Bilibili URL
2. 用户已下载的本地视频文件
3. 本地字幕或转写文件兜底

如果字幕抓取失败，不要默认改成本地大模型转写；先确认 cookies / 登录态 / 字幕源。
如果用户已经提供了可用字幕，不要重做一遍转写。

## 工作流

### 1) 先做环境检测

先跑环境检查，再决定是 URL 摄取还是本地接管。

### 2) 识别并摄取来源

用 `scripts/ingest_source.py` 完成：

- 平台识别：YouTube / Bilibili / local fallback
- 高清视频下载
- 字幕抓取
- 登录态复用：`--cookies-from-browser` 或 `--cookies`
- 生成下载清单与字幕路径

当用户已经给了本地视频时，直接接管该文件并继续：

- 视频文件
- 字幕文件
- `manifest.json`

不要要求用户重新下载同一个文件。

优先下载最佳可用画质，并优先拿手动字幕；没有手动字幕时再用自动字幕。

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

必须先给用户看候选列表，至少 Top 3，建议 Top 5。

不要在用户没选之前直接输出完整剪辑方案。

必须明确加一句：

> 请从 Top 1 / Top 2 / Top 3 中选择一个片段，我再继续输出具体剪辑方案。

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
- [output-layout.md](references/output-layout.md)
- [scoring-rubric.md](references/scoring-rubric.md)
- [output-format.md](references/output-format.md)
- [render-pipeline.md](references/render-pipeline.md)
- [render-spec.md](references/render-spec.md)
- [subtitle-alignment.md](references/subtitle-alignment.md)
- [verification-checklist.md](references/verification-checklist.md)
- `scripts/render_clip.py`
- `scripts/verify_render.py`
