# Verification Checklist

最终交付前必须有脚本证据和人工可读报告。`render_final` 不能只说“看起来可以”。

## 命令

```bash
python3 scripts/verify_render.py --spec render_specs/render_spec.json --video renders/final.mp4 --strict --json > qa/qa_report.json
```

## Strict 必查项

- `render_spec.json` 存在且字段完整。
- `render_manifest.json` 存在。
- final video 存在，可被 `ffprobe` 读取。
- 有视频轨和音频轨。
- 时长与 `segment_end - segment_start` 在容忍范围内。
- 分辨率符合 `output_profile` / `layout_profile`。
- `subtitles_final.ass` 存在。
- ASS Dialogue 格式合法。
- 同一 lane/layer 没有不可读时间重叠。
- cue 数与 manifest 一致。
- `lead_sec` 已记录。
- `source_time_basis` 指向 `normalized_cues.json`。
- `subtitle_burn_source_is_clean` 为 true。
- B-roll 来源、许可/来源说明和覆盖位置已记录。

## QA 帧

生成到 `qa/frames/`，至少覆盖：

- 开头第一句字幕。
- 中段普通字幕。
- 字幕密集处。
- B-roll 覆盖处。
- 结尾最后一句字幕。

基础可视检查：

- 字幕没有长时间滞留超过源结束后的容忍阈值。
- 同一时间窗口内不存在不可读叠字。
- B-roll 没有遮挡字幕安全区。
- 中英文上下关系稳定，且同起同落。

## Final Delivery

`delivery/` 必含：

- `final.mp4`
- `render_manifest.json`
- `normalized_cues.json`
- `subtitles_final.ass`
- `qa_report.json`

如果任一项缺失，`render_final` 阻塞。`render_draft` 可以交付但必须标注为 draft，并列出未通过项。
