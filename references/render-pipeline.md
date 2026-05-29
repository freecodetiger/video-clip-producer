# Render Pipeline

这个流程适用于用户已经确认某个候选片段，要继续生成最终成片的阶段。

## 输入

- 已确认的片段起止时间
- 源视频或已接管本地视频
- 源字幕或转写
- 本地 B-roll 目录（如有）
- 输出根目录

## 标准步骤

1. 固化片段配置
   - 记录起止时间
   - 记录 B-roll 插入点
   - 记录字幕模式
   - 记录字幕偏移量
   - 记录字幕布局参数：底边距、单行长度、断句策略

2. 生成视频轨
   - 先做纯 A-roll
   - 再拼接分镜 B-roll
   - 保持总时长与音频一致

3. 生成音轨
   - 从源视频截取对应区间
   - 如果需要，做响度归一

4. 生成字幕
   - 优先使用源时间戳
   - 先做全局 offset
   - 再做局部 patch
   - 对长句做语义断句和多行拆分
   - 字幕位置先保可读，再保美观
   - 输出 `ass` 和 `srt`

5. 烧录字幕并合成
   - 使用 `libass`
   - 保证中文主、英文副
   - 输出最终 mp4

6. 生成交付文件
   - `配文.md`
   - `推荐标题.md`
   - `render_manifest.json`
   - 可选预览帧

## `render_manifest.json` 建议字段

```json
{
  "source_url": "...",
  "source_title": "...",
  "clip_title": "...",
  "start": 0.0,
  "end": 48.72,
  "subtitle_mode": "source_offset",
  "subtitle_offset": 1.0,
  "subtitle_layout": {
    "bottom_margin_px": 108,
    "max_chars_per_line": 22,
    "semantic_breaks": true,
    "split_long_lines": true
  },
  "broll_used": true,
  "final_video": "...",
  "subtitle_ass": "...",
  "subtitle_srt": "...",
  "notes_md": "...",
  "title_md": "..."
}
```

## 原则

- 不要把字幕对齐当成一次性黑盒
- 不要让 B-roll 破坏字幕可读性
- 不要在最终目录里塞临时文件
- 不要在用户未确认前进入渲染
