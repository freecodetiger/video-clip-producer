# Output Layout

每个来源视频使用一个视频级根目录。不要把最终成片、字幕、素材清单散落在临时目录。

## 标准结构

```text
<video_root>/
  source/
    source.mp4
    source.srt
    manifest.json
  subtitles/
    normalized_cues.json
    subtitles_preview.ass
    subtitles_final.ass
    subtitle_timing_report.json
  segments/
    candidates.json
    selected_segment.json
  assets/
    broll/
    broll_plan.json
    asset_manifest.json
  render_specs/
    render_spec.json
  renders/
    final.mp4
    render_manifest.json
  qa/
    qa_report.json
    frames/
  delivery/
    final.mp4
    render_manifest.json
    normalized_cues.json
    subtitles_final.ass
    qa_report.json
    配文.md
    推荐标题.md
```

## 命名规则

- 最终视频固定叫 `final.mp4`，除非用户指定平台命名。
- 字幕中间数据固定叫 `normalized_cues.json`。
- 最终视觉字幕固定叫 `subtitles_final.ass`。
- 可审阅字幕固定叫 `subtitles_preview.ass`。
- QA 帧放入 `qa/frames/`。
- 临时渲染文件只能放 `_tmp_render/`、`tmp/` 或系统临时目录。

## 交付规则

`render_final` 交付至少包含：

- `delivery/final.mp4`
- `delivery/render_manifest.json`
- `delivery/normalized_cues.json`
- `delivery/subtitles_final.ass`
- `delivery/qa_report.json`

`render_draft` 可以缺 B-roll 或 QA 帧，但 manifest 和 QA report 必须说明缺口。
