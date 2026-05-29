# Source Ingestion

这个 skill 的默认入口是 URL 摄取，但也必须支持用户已经下载好的本地源文件。

## 支持来源

- YouTube
- Bilibili
- 本地文件兜底

## 推荐顺序

1. 先识别平台
2. 用 `yt-dlp` 下载高清视频
3. 用登录态 cookies 抓字幕
4. 只在字幕抓不到时，才考虑其他转写方案
5. 如果用户已经给了本地 `source.mp4` / `source.srt`，直接接管继续处理

## 字幕优先级

- 手动字幕优先
- 自动字幕其次
- 中文优先于英文，除非视频本身是英文且中文缺失

## 推荐命令

```bash
python3 scripts/ingest_source.py \
  "https://www.youtube.com/watch?v=VIDEO_ID" \
  --output-dir ./outputs/source \
  --cookies-from-browser chrome
```

或：

```bash
python3 scripts/ingest_source.py \
  "https://www.bilibili.com/video/BVxxxxxxx" \
  --output-dir ./outputs/source \
  --cookies /path/to/cookies.txt
```

## 产物

脚本应落盘：

- 视频文件
- 字幕文件
- 摄取清单 `manifest.json`

如果是本地接管模式，也应该写入 manifest，明确记录：

- 原始路径
- 接管方式
- 已发现的字幕文件
- 选中的字幕文件
- 是否可直接进入 transcript / clip ranking

## 失败处理

如果视频可下但字幕没有抓到：

- 明确写出字幕缺失
- 不要假装 transcript 已存在
- 提示用户补 cookies 或切换字幕语言

如果视频也下不来：

- 报告平台、URL、认证和网络问题
- 不要直接进入片段评分

如果视频已经由用户手动下载：

- 接管本地视频
- 不要重复尝试下载
- 继续做字幕、候选片段和最终渲染
