# B-roll Sourcing

这个流程用于用户没有准备本地 B-roll，或本地素材不够支撑最终成片时。

## 默认策略

- 先问用户是否有本地 B-roll 目录
- 如果没有，默认从网络获取免版权自然素材
- 不因为没有素材而放弃 B-roll
- 素材必须落盘到视频级输出目录，不散落在临时目录
- 素材来源必须写入 `asset_manifest.json`

## 默认素材方向

优先找“震撼自然素材”，适合励志、转折、金句和情绪抬升：

- storm at sea
- dramatic ocean waves
- lightning clouds
- aurora borealis
- mountain sunrise
- cloud sea timelapse
- canyon drone
- waterfall
- desert storm
- snow mountain

中文语义可映射为：

- 雷暴
- 海浪
- 极光
- 雪山
- 云海
- 峡谷
- 日出
- 暴雨
- 奔流

## 来源优先级

默认只使用可公开下载、免版权或开放许可的素材源。优先级：

1. 明确标注免版权 / royalty-free / CC0 / public domain 的视频素材站
2. 可公开下载且许可清楚的视频素材页面
3. 用户明确允许的其他来源

不要默认下载影视片段、新闻画面、带明显平台水印的视频、或许可不清的二创素材。

## 获取流程

1. 根据片段主题和情绪生成 3-6 个英文搜索关键词
2. 优先搜索免版权视频素材
3. 下载 3-6 条可用素材，单条建议 8-20 秒
4. 用 `ffprobe` 验证素材有视频轨、时长大于 4 秒、分辨率不低于 720p
5. 统一转码或在渲染阶段统一 scale/crop 到目标分辨率
6. 写入 `asset_manifest.json`

## 推荐目录

```text
outputs/<source_title>_<platform>_<theme>/
  00_assets/
    broll/
      01_storm_at_sea.mp4
      02_lightning_clouds.mp4
      03_aurora_borealis.mp4
    asset_manifest.json
```

## `asset_manifest.json`

建议字段：

```json
{
  "assets": [
    {
      "file": "broll/01_storm_at_sea.mp4",
      "source_url": "https://...",
      "license": "royalty-free",
      "query": "storm at sea royalty free video",
      "purpose": "opening",
      "duration_seconds": 12.4,
      "width": 1920,
      "height": 1080
    }
  ]
}
```

## 失败处理

如果网络搜索或下载失败：

- 换同义关键词再试
- 换另一个免版权来源
- 降低素材数量要求，但至少保留 1-2 条可用 B-roll
- 如果仍无素材，明确报告失败原因，不要假装已使用 B-roll

## 人工交互边界

这是轻人工、强 Agent 主动流程。除非涉及版权不清、用户品牌限制、或素材风格明显冲突，不要反复追问。

默认假设：

- 风格：震撼自然
- 许可：免版权 / 开放许可优先
- 数量：3-6 条
- 输出：`00_assets/broll/`
