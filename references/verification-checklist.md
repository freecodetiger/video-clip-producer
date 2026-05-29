# Verification Checklist

在把结果交给用户前，至少做下面这些检查。

## 输入检查

- URL 或本地文件是否已识别
- 视频文件是否存在
- 字幕文件是否存在
- B-roll 目录是否存在
- 输出目录是否可写

## 环境检查

- `ffmpeg` 可执行
- `ffprobe` 可执行
- `yt-dlp` 可用
- `ffmpeg` 支持 `subtitles`
- `ffmpeg` 支持 `drawtext`
- `ffmpeg` 包含 `libass`

## 内容检查

- 候选片段排序合理
- 片段没有断章取义到扭曲事实
- 每个候选都能单独成立
- 用户已经明确确认了要剪哪一段

## 成片检查

- 视频时长正确
- 音轨存在
- 字幕已烧录或已明确保留为外挂字幕
- B-roll 没有压过字幕
- 字幕一开口就能跟上
- 双语顺序是中文主、英文副

## 交付检查

- 最终目录结构符合规范
- `配文.md` 已生成
- `推荐标题.md` 已生成
- `render_manifest.json` 已生成
- 已运行 `scripts/verify_render.py`
- 临时文件没有混进最终交付目录
