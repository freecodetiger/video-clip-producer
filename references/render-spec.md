# Render Spec

`scripts/render_clip.py` 的 final/draft 成片入口只接受 `render_spec.json`。不要把零散命令参数当最终状态。

## 必填字段

```json
{
  "source_video": "source/source.mp4",
  "segment_start": 483.6,
  "segment_end": 532.32,
  "subtitle_source": "subtitles/normalized_cues.json",
  "subtitle_lead_sec": 0.8,
  "subtitle_mode": "rolling_bilingual",
  "layout_profile": {},
  "broll_plan": [],
  "output_profile": {}
}
```

## 字段说明

- `source_video`：干净源视频，不能是已烧字幕的二次源。
- `segment_start` / `segment_end`：源视频绝对时间。
- `subtitle_source`：必须指向 `normalized_cues.json`。
- `subtitle_lead_sec`：默认 `0.8`，只提前 `display_start`。
- `subtitle_mode`：默认 `rolling_bilingual`。
- `layout_profile`：分辨率、fps、lane 数、字幕轨位置、字号、行长。
- `broll_plan`：素材路径、时间段、来源、覆盖位置、字幕避让策略。
- `output_profile`：输出目录、最终文件名、编码参数。

`render_final` 还必须设置：

```json
{
  "subtitle_burn_source_is_clean": true
}
```

## B-roll Plan

```json
[
  {
    "type": "a",
    "start": 0.0,
    "end": 4.4,
    "source": "source_video",
    "subtitle_avoidance": "bottom_safe_lanes"
  },
  {
    "type": "b",
    "start": 4.4,
    "end": 8.9,
    "file": "assets/broll/01_storm.mp4",
    "offset": 0.0,
    "source": "local|auto_web_royalty_free",
    "license": "source page or local owner note",
    "subtitle_avoidance": "do_not_cover_bottom_lanes"
  }
]
```

## 输出产物

- `subtitles_preview.ass`
- `subtitles_final.ass`
- `subtitles_final.srt`
- `subtitle_timing_report.json`
- `broll_plan.json`
- `render_manifest.json`
- `final.mp4`

## 命令

```bash
python3 scripts/render_clip.py --print-spec-template
python3 scripts/render_clip.py --spec render_specs/render_spec.json --dry-run
python3 scripts/render_clip.py --spec render_specs/render_spec.json
```

渲染后必须运行：

```bash
python3 scripts/verify_render.py --spec render_specs/render_spec.json --video renders/final.mp4 --strict --json
```
