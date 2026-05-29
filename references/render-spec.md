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
- `render`
- `subtitle`
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

## `subtitle` 结构

```json
{
  "mode": "source_offset",
  "advance_seconds": 0.5,
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
