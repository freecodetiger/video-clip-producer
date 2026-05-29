# Output Layout

最终切片产物使用统一的视频级根目录。

## 根目录

```text
outputs/
  <source_title>_<platform>_<theme>/
```

示例：

```text
outputs/黄仁勋2026演讲_抖音励志切片/
outputs/鲁豫对话刘晓庆_抖音共鸣切片/
```

## 推荐目录结构

```text
outputs/<source_title>_<platform>_<theme>/
  00_source/
    source.mp4
    source.srt
    source.ass
    manifest.json
  00_assets/
    broll/
      01_storm_at_sea.mp4
      02_lightning_clouds.mp4
    asset_manifest.json
  00_index/
    切片目录.md
  00_concat/
    <source_title>_合集_横屏.mp4
  01_<片段主题>/
    <片段主题>.mp4
    <片段主题>_分镜版.mp4
    <片段主题>_Aroll版.mp4
    <片段主题>_分镜双语字幕版.mp4
    双语字幕.srt
    双语字幕.ass
    配文.md
    推荐标题.md
    render_manifest.json
    preview_frames/
  02_<片段主题>/
    ...
```

## 命名规则

- 目录前缀用两位数递增：`01_`、`02_`
- 主题目录名要短、可读、适合展示
- 成片文件名与目录主题一致
- 字幕统一命名为 `双语字幕.srt` 和 `双语字幕.ass`
- 文案统一命名为 `配文.md`
- 标题建议统一命名为 `推荐标题.md`
- 渲染记录统一命名为 `render_manifest.json`
- 预览抽帧放在 `preview_frames/`

## 可选产物

根据任务需要可额外放：

- `封面_3x4.png`
- `封面_9x16.png`
- `分镜版.mp4`
- `参考帧/`
- `subtitle_preview/`
- `timing_report.json`
- `00_assets/broll/`
- `00_assets/asset_manifest.json`

## 原则

- 生成目录只承载最终交付物
- `source/` 只放输入落盘结果
- `00_assets/` 只放可复用素材和素材来源清单
- 临时文件放 `tmp/` 或系统临时目录
- 不要把不同视频混在同一目录层级
- 同一视频的所有切片必须落在同一根目录下
- 最终成片目录不要塞进一次性草稿文件
