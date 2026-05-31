# Subtitle Stability Pipeline

字幕是最终成片最容易返工的部分。处理字幕时要把“内容、时间、视觉、验收”分开，不要在一次渲染里临时猜。

## 标准流程

每次做双语字幕或滚动字幕时，按这个顺序执行：

1. 保护源材料
   - 保留原始视频、原始字幕和干净无字幕视频轨。
   - 不要把新字幕烧到已经带字幕的视频上。
   - 如果不确定输入视频是否干净，回到源视频重新生成 clean video track。

2. 规范化字幕
   - 先把平台字幕或转写字幕整理成语义完整的 cue。
   - 合并 YouTube 自动字幕这类碎片时，保留原始字幕的时间戳来源。
   - 不要为了滚动字幕重新估整段时间。

3. 固化中间数据
   - 字幕渲染前先形成结构化 cue 数据。
   - 每个 cue 至少包含 `cue_id`、`source_start`、`source_end`、`display_start`、`display_end`、`en`、`zh`、`speaker_optional`、`source_file`。
   - 如果使用滚动或双轨，还要记录 `lane`。

4. 应用时间策略
   - 默认公式是 `display_start = max(0, source_start - lead_sec)`。
   - 默认 `display_end = source_end`。
   - 用户说“偏晚”时，调大 `lead_sec`。
   - 用户说“太早”时，调小 `lead_sec`。
   - 用户说“停留太久”时，调整 `display_end` 或 end policy，不要先改 start。

5. 生成双语字幕
   - 中英文必须作为同一个 cue 的上下两行，同起同落。
   - 如果用 ASS，优先把中英文写进同一个 Dialogue event；只有现有模板要求时才拆成两个 event。
   - SRT 只作为时间稿和可读稿；复杂视觉以 ASS 为准。

6. 处理滚动和重叠
   - 如果下一句提前出现时上一句仍未结束，不要把下一句 start 推迟。
   - 允许短暂出现两个 cue，但必须分轨错位显示。
   - 同一条 lane 内绝不能有时间重叠。
   - 如果两条 lane 不够，先降低 lead 或缩短上一句生命周期，不要让字幕压在一起。

7. 记录参数
   - `render_manifest.json` 必须记录字幕模式、时间策略、视觉布局和输入视频轨。
   - 关键字段见下面的 manifest 模板。

8. 验收
   - 先跑脚本检查，再抽帧看画面。
   - 抽帧点必须覆盖第一句、两句共存区、最长字幕、B-roll 区、最后一句。

## 中间 cue 格式

推荐把字幕整理成这种结构后再生成 SRT/ASS：

```json
{
  "source_start": 333.8,
  "source_end": 336.07,
  "display_start": 332.3,
  "display_end": 336.07,
  "en": "Today I want to talk about purpose.",
  "zh": "今天我想谈谈目的。",
  "source_file": "source.en.srt",
  "speaker_optional": null,
  "lane": 0
}
```

## 推荐 manifest 字段

```json
{
  "subtitle_mode": "rolling_bilingual",
  "source_time_basis": "source.en.srt",
  "lead_sec": 1.2,
  "end_policy": "source_end",
  "allow_two_visible_cues": true,
  "max_visible_cues": 2,
  "no_same_lane_overlap": true,
  "lane_bottoms": [940, 790],
  "font_cn": 54,
  "font_en": 32,
  "subtitle_burn_source_is_clean": true,
  "input_video_track": "_tmp_final/clean_video_track.mp4",
  "input_audio": "_tmp_final/clean_audio.m4a",
  "subtitle_ass": "滚动双语字幕.ass",
  "subtitle_srt": "滚动双语字幕.srt",
  "cue_count": 32
}
```

## 用户反馈到参数的映射

- “字幕晚了”：增大 `lead_sec`。
- “字幕太早”：减小 `lead_sec`。
- “停留太久”：缩短 `display_end` 或改变 `end_policy`。
- “两个字幕距离太大”：调整 `lane_bottoms`，通常先上提低轨。
- “两个字幕重叠”：检查同 lane overlap；必要时增加 lane 间距、缩短字幕、减小字号或换行。
- “英文太抢眼”：降低 `font_en`、颜色亮度或透明度。
- “字幕挡脸”：整体上移或下移字幕轨道，并抽帧验证。

## 失败回退

字幕时间源的优先级：

1. 手动字幕或平台字幕的原始时间戳。
2. 原始时间戳加全局 `lead_sec` / offset。
3. 少量单句 patch。
4. 强制对齐或重新转写。

只有在源字幕缺失、明显错误或不可用时，才进入强制对齐或重新转写。
