# 环境检查清单

在开始 URL 摄取和切片分析前，先确认以下环境条件。

## 必需

- 可用的 Agent 工具
- 可执行的 shell / 文件读写权限
- `python3`
- `yt-dlp`
- `ffmpeg`
- `ffprobe`
- 输出目录可写

## 强烈建议

- `ffmpeg` 已编译字幕能力：`subtitles`
- `ffmpeg` 已编译文字渲染能力：`drawtext`
- `ffmpeg` 已编译 `libass`
- Python 可导入 `PIL`
- Python 可导入 `cv2`

## 认证相关

如果 URL 需要登录态才能拿到高清视频或字幕，准备其中一种即可：

- `--cookies-from-browser <browser>`
- 已导出的 `cookies.txt`

## 输入资源

- YouTube / Bilibili URL
- 字幕文件：`srt` / `ass` / `vtt`
- 转写文件：`json` / `jsonl`
- 本地 B-roll 目录（如有）

## 环境通过后的最低输出

只要环境通过，skill 至少要能输出：

1. 下载与字幕摄取结果
2. 候选片段列表
3. 排序分数
4. 用户确认提示

## 环境未通过时的输出

只报告：

- 缺少什么
- 哪些步骤还能继续
- 需要什么命令或路径补齐
