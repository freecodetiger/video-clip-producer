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
6. 下载后必须用 `ffprobe` 校验视频轨和音轨时长

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
  --cookies-from-browser chrome
```

## Bilibili 实战规则

Bilibili 下载最容易浪费时间的坑是：文件看似下载成功，但视频轨异常短，音轨正常。例如实践中遇到过 AV1 组合下载后，最终文件音频约 243 秒，视频轨只有约 0.64 秒。

固定处理顺序：

1. 优先使用登录态：`--cookies-from-browser chrome` 或 `--cookies cookies.txt`
2. 优先选择 H.264 mp4 轨道，不把 AV1 当默认首选
3. 传入 `--ffmpeg-location`，优先使用已验证可用的 ffmpeg 目录
4. 如果只截取片段，使用 `--download-sections "*HH:MM:SS-HH:MM:SS"` 并加 `--force-keyframes-at-cuts`
5. 下载完成后用 `ffprobe` 校验：
   - 至少有一个视频轨
   - 至少有一个音轨
   - 视频轨时长和音轨/预期时长基本一致
6. 如果视频轨缺失或明显短于音轨，删除坏文件，换 H.264 fallback 格式重拉

推荐 Bilibili 格式选择：

```text
30112+30280/30080+30280/bestvideo[vcodec^=avc1][ext=mp4]+bestaudio[ext=m4a]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best
```

如果仍失败，降级：

```text
30080+30280/bestvideo[vcodec^=avc1][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best
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

如果 Bilibili 文件下载成功但 `ffprobe` 发现视频轨异常：

- 不要继续渲染
- 不要只看容器总时长
- 先删除坏文件并用 H.264 fallback 重拉
- 把 `media_probe` 写入 manifest，方便复盘

如果视频已经由用户手动下载：

- 接管本地视频
- 不要重复尝试下载
- 继续做字幕、候选片段和最终渲染
