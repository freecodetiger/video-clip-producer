---
name: video-clip-producer
description: URL-first long-video clip skill for YouTube and Bilibili links, or already-downloaded local sources. Downloads or adopts HD video, fetches subtitles with login-state cookies, normalizes subtitles into structured cues, ranks high-traffic candidates, and can continue through render_spec-driven bilingual subtitle/B-roll rendering, strict verification, and final delivery. Use whenever the user gives a YouTube/Bilibili link, a local source file, asks for subtitle extraction, wants ranked short-video cut candidates, or needs a rendered clip package.
---

# Video Clip Producer

把每个视频任务当成阶段门禁流水线处理。每个阶段都要有明确输入、输出、命令、阻塞条件和可继续条件；不要靠临场猜测跳过字幕、B-roll、ffmpeg 能力或最终验收。

默认目标是稳定生成可交付短视频。候选推荐仍然按“冲流量”排序，但不能编造、断章取义或扭曲原意。

## 模式

- `candidate_only`：只摄取、规范化字幕、推荐候选片段。停在选择门。
- `render_draft`：生成可审阅草稿，允许 B-roll 或视觉包装缺口，但必须写明缺口。
- `render_final`：必须通过字幕、B-roll、音视频、manifest 和交付清单验证。

如果用户没有明确模式：

- 只要求找片段或推荐：用 `candidate_only`。
- 要“直接成片/带字幕/带 B-roll”：用 `render_final`，除非素材或环境只能支持 `render_draft`。
- 用户说“你自动选”：输出候选依据后自动选择，不等待用户确认。

## 输出目录

统一使用视频级根目录，分阶段产物固定落位：

```text
<video_root>/
  source/
  subtitles/
  segments/
  assets/
  render_specs/
  renders/
  qa/
  delivery/
```

细节见 [output-layout.md](references/output-layout.md)。

## 十阶段流水线

### 1. Intake

输入：用户 URL、本地视频、字幕、目标模式、B-roll 状态。

输出：任务模式、视频根目录、选择策略。

命令：无。

阻塞：输入既不是 URL，也不是本地视频/字幕。

可继续：B-roll 状态未知时，`candidate_only` 可继续；`render_final` 默认自动素材获取或要求本地素材清单。

### 2. Env Check

输入：任务模式、URL/本地路径、输出目录。

输出：环境能力 JSON。

命令：

```bash
python3 scripts/check_env.py --task ingest --json
python3 scripts/check_env.py --task subtitle --json
python3 scripts/check_env.py --task render --json
python3 scripts/check_env.py --task final --json
```

阻塞：当前阶段所需能力缺失。`render_final` 必须验证 `ffmpeg`、`ffprobe`、`ass/subtitles/libass`、`scale/crop/format/loudnorm`、`libx264`、`aac`。

可继续：optional warning 不阻塞。macOS 字幕烧录或 codec 缺失时优先建议 `brew install ffmpeg-full`；自定义安装优先用 `FFMPEG` / `FFPROBE`。

### 3. Source Ingest

输入：URL 或本地视频。

输出：`source/manifest.json`、源视频、字幕文件。

命令：

```bash
python3 scripts/ingest_source.py --url <url> --out <video_root>/source
python3 scripts/ingest_source.py --local <video> --out <video_root>/source
```

兼容旧脚本参数时可用 `python3 scripts/ingest_source.py <url-or-local> --output-dir <dir> --json`。

阻塞：视频文件不可用；Bilibili 下载后视频轨或音轨异常短；需要平台字幕但没有登录态且未提供本地字幕。

可继续：本地视频已存在时直接接管，不要强行重下。Bilibili 实战规则见 [source-ingestion.md](references/source-ingestion.md)。

### 4. Subtitle Normalize

输入：平台字幕、SRT/VTT/ASS/JSON 转写。

输出：`subtitles/normalized_cues.json`。

命令：

```bash
python3 scripts/parse_transcript.py --input <subtitle-file> --out <video_root>/subtitles/normalized_cues.json --lead-sec 0.8 --json
```

硬规则：

- 平台碎字幕先合并成语义完整 cue，但时间戳继承源字幕，不重新估时。
- `display_start = max(0, source_start - lead_sec)`，默认 `lead_sec = 0.8`。
- `display_end = source_end`，提前显示只影响开始时间，不拉长到话音结束后很久。
- 双语字幕作为一个 cue 管理，中英文同起同落。

`normalized_cues.json` 必含：

```json
{
  "cue_id": "cue_0001",
  "source_start": 10.0,
  "source_end": 12.0,
  "display_start": 9.2,
  "display_end": 12.0,
  "en": "English text",
  "zh": "中文文本",
  "speaker_optional": null,
  "source_file": "source.srt"
}
```

阻塞：没有可用字幕且用户未授权转写。

可继续：`candidate_only` 可以只用单语字幕；`render_final` 必须有可渲染 cue。

### 5. Candidate Rank

输入：`subtitles/normalized_cues.json`。

输出：`segments/candidates.json` 和 Top 候选列表。

命令：

```bash
python3 scripts/rank_segments.py --input <video_root>/subtitles/normalized_cues.json --mode traffic --top-k 5 --json
```

阻塞：字幕不可读或候选明显扭曲原意。

可继续：没有高分候选时，说明原因并给降级候选，不要编造观点。

### 6. User Or Agent Selection

输入：`candidates.json`、任务模式。

输出：选定片段和选择理由。

`candidate_only` 或 `user_select`：先停住，要求用户从 Top 候选中选一个。

`agent_auto_select`：输出 Top 候选和自动选择依据，然后继续下一阶段。

阻塞：`user_select` 模式未获得用户选择。

可继续：用户明确“直接做/自动选”时不再二次停住。

### 7. Render Spec

输入：选定片段、源视频、`normalized_cues.json`、字幕策略、B-roll 策略、输出规格。

输出：`render_specs/render_spec.json`。

命令：

```bash
python3 scripts/render_clip.py --print-spec-template
python3 scripts/render_clip.py --spec <video_root>/render_specs/render_spec.json --dry-run
```

`render_spec.json` 必含：

- `source_video`
- `segment_start`
- `segment_end`
- `subtitle_source`
- `subtitle_lead_sec`
- `subtitle_mode`
- `layout_profile`
- `broll_plan`
- `output_profile`

默认 `subtitle_mode` 是 `rolling_bilingual`。默认字幕视觉为 YouTube 风格滚动字幕：允许短暂错位，但同一视觉区域不能重叠到不可读。

阻塞：`render_final` 中 `subtitle_burn_source_is_clean` 不是 `true`。

可继续：`render_draft` 可以保留空 `broll_plan`，但必须写明缺口。

### 8. Asset And B-roll Resolve

输入：`broll_plan`、本地素材目录或自动素材策略。

输出：`assets/broll_plan.json`、`assets/asset_manifest.json`。

规则：

- B-roll plan 必须记录素材路径、时间段、来源、覆盖位置和字幕避让策略。
- 用户无本地素材时，默认获取免版权自然素材并记录来源。
- final 模式不能只有“会找素材”的说明，必须有来源清单。

阻塞：`render_final` 需要 B-roll 但素材不存在、来源未知或许可/来源说明缺失。

可继续：`render_draft` 可以用纯 A-roll 或占位，但要在 manifest 标记。

### 9. Render

输入：`render_spec.json`、`normalized_cues.json`、B-roll 素材。

输出：`renders/final.mp4`、`subtitles_final.ass`、`subtitles_preview.ass`、`subtitle_timing_report.json`、`broll_plan.json`、`render_manifest.json`。

命令：

```bash
python3 scripts/render_clip.py --spec <video_root>/render_specs/render_spec.json
```

硬规则：

- ASS 只从 `normalized_cues.json` 生成，不直接吃零碎 SRT/VTT。
- 不要把已烧字幕的视频当 clean source 再烧字幕；无法确认 clean source 时 final 阻塞。
- 滚动字幕使用 lane/slot 分配，生成前后检查同层时间重叠。
- manifest 写入字幕 lead、cue 数、B-roll 覆盖率、ffmpeg 路径、输入 hash、输出 hash 和验证结果。

### 10. Verify And Deliver

输入：`render_spec.json`、最终视频、ASS、manifest。

输出：`qa/qa_report.json`、QA 帧图、`delivery/`。

命令：

```bash
python3 scripts/verify_render.py --spec <render_spec.json> --video <final.mp4> --strict --json
```

`render_final` 交付必须包含：

- `final.mp4`
- `render_manifest.json`
- `normalized_cues.json`
- `subtitles_final.ass`
- `qa_report.json`

严格检查至少覆盖：音视频轨、时长、分辨率、字幕 cue 数、ASS 重叠、字幕生命周期、manifest 一致性、开头/中段/结尾/字幕密集处/B-roll 叠加处 QA 帧。

阻塞：strict verification 失败。

可继续：draft 可交付失败报告和待补项；final 不可跳过。

## 常用参考

- 环境检查：[environment-checklist.md](references/environment-checklist.md)
- 来源摄取：[source-ingestion.md](references/source-ingestion.md)
- 字幕稳定：[subtitle-stability.md](references/subtitle-stability.md)
- 字幕校准：[subtitle-alignment.md](references/subtitle-alignment.md)
- B-roll 获取：[broll-sourcing.md](references/broll-sourcing.md)
- 输出目录：[output-layout.md](references/output-layout.md)
- 渲染规格：[render-spec.md](references/render-spec.md)
- 渲染流程：[render-pipeline.md](references/render-pipeline.md)
- 最终验收：[verification-checklist.md](references/verification-checklist.md)
