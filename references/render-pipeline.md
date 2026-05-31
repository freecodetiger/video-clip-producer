# Render Pipeline

这个流程只在片段已经选定后执行。未选定片段时，停在候选选择门。

## 输入

- `source/manifest.json`
- 干净源视频
- `subtitles/normalized_cues.json`
- `segments/selected_segment.json`
- `assets/broll_plan.json`
- `render_specs/render_spec.json`

## 步骤

1. 固化 render spec
   - 写入 `segment_start` / `segment_end`
   - 写入 `subtitle_source`、`subtitle_lead_sec`、`subtitle_mode`
   - 写入 `layout_profile`
   - 写入 `broll_plan`
   - `render_final` 必须确认 `subtitle_burn_source_is_clean: true`

2. 生成字幕
   - 只从 `normalized_cues.json` 生成 ASS/SRT
   - 使用 `display_start` / `display_end`
   - 中英文同一个 cue，同起同落
   - 滚动字幕使用 lane/slot 分配
   - 输出 `subtitles_preview.ass`、`subtitles_final.ass`、`subtitle_timing_report.json`

3. 生成视频轨
   - A-roll 从源视频截取
   - B-roll 按 plan 覆盖
   - B-roll 不得遮挡字幕安全区

4. 生成音轨
   - 从源视频同一区间截取
   - 默认做 `loudnorm`

5. 烧录字幕并合成
   - 使用 `ass` / `libass`
   - 使用 `libx264` + `aac`
   - 输出 `final.mp4`

6. 写 manifest
   - 字幕 lead、cue 数、lane 位置
   - B-roll 覆盖率
   - ffmpeg 路径/版本
   - 输入 hash、输出 hash
   - 验证结果

7. 严格校验
   - `verify_render.py --spec ... --strict`
   - 生成 `qa_report.json`
   - 抽帧覆盖开头、中段、结尾、字幕密集处、B-roll 叠加处

## 阻塞条件

- 源视频不可确认干净且需要烧字幕。
- `normalized_cues.json` 缺失或 cue 字段不完整。
- ASS 同层时间重叠。
- final 模式缺 B-roll 来源清单。
- strict verification 失败。

## Manifest 核心字段

```json
{
  "source_video": "source/source.mp4",
  "start": 483.6,
  "end": 532.32,
  "duration": 48.72,
  "subtitle_mode": "rolling_bilingual",
  "source_time_basis": "subtitles/normalized_cues.json",
  "lead_sec": 0.8,
  "subtitle_burn_source_is_clean": true,
  "cue_count": 32,
  "lane_bottoms": [76, 150],
  "broll_used": true,
  "broll_coverage": 0.42,
  "final_video": "renders/final.mp4",
  "subtitle_ass": "subtitles/subtitles_final.ass",
  "input_hash": "...",
  "output_hash": "..."
}
```
