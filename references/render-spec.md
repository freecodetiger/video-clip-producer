# Render Spec

`scripts/render_clip.py` 使用一个 JSON spec 作为统一入口。

## 必填字段

- `source_video`
- `output_dir`
- `source_start`
- `duration` 或 `source_end`
- `visuals`

## 推荐字段

- `source_url`
- `source_title`
- `clip_title`
- `final_name`
- `selection`
- `render`
- `subtitle`
- `assets`
- `titles`
- `caption`
- `bgm`

## `visuals` 结构

```json
[
  {"type": "a", "start": 0.0, "end": 4.4},
  {"type": "b", "start": 4.4, "end": 8.9, "file": "/path/to/broll.mp4", "offset": 0.0}
]
```

## `selection` 结构

如果用户选择 Agent 自动选片，render spec 应记录选择模式和理由：

```json
{
  "mode": "agent_auto_select",
  "selected_rank": 1,
  "reason": "情绪张力、争议度、金句密度和视觉包装性综合最高",
  "alternatives_considered": [2, 3, 4]
}
```

## `assets` 结构

当用户没有本地 B-roll 时，Agent 应主动获取免版权自然素材，并记录：

```json
{
  "broll_source": "auto_web_royalty_free",
  "asset_dir": "00_assets/broll",
  "asset_manifest": "00_assets/asset_manifest.json",
  "queries": [
    "storm at sea royalty free video",
    "aurora borealis timelapse royalty free video"
  ]
}
```

## `subtitle` 结构

```json
{
  "mode": "source_offset",
  "advance_seconds": 0.5,
  "layout": {
    "bottom_margin_px": 108,
    "max_chars_per_line": 22,
    "semantic_breaks": true,
    "split_long_lines": true
  },
  "items": [
    {"start": 0.28, "end": 2.15, "cn": "中文主字幕", "en": "English subtitle"}
  ]
}
```

## 输出

- `双语字幕.ass`
- `双语字幕.srt`
- `配文.md`
- `推荐标题.md`
- `render_manifest.json`
- 最终 mp4

## 使用建议

- 先用 `--print-spec-template` 生成样例
- 先用 `--dry-run` 检查路径和命令
- 真正渲染前，先确认字幕偏移值和 B-roll 插入点
- 如果用户已经确认片段，不要再强制回到候选推荐流程
