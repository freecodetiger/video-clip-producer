# Video Clip Producer

Codex skill for turning long YouTube or Bilibili videos into ranked short-video candidates and final rendered clips with subtitles, B-roll, captions, titles, and a render manifest.

## What It Does

- Ingests YouTube, Bilibili, or local video sources.
- Fetches platform subtitles when available.
- Ranks high-potential clip segments.
- Renders confirmed clips with A-roll, optional B-roll, burned subtitles, title suggestions, caption copy, and `render_manifest.json`.

## Quick Start

Check only the capabilities needed for the current task:

```bash
python3 scripts/check_env.py --json --task ingest --url "https://www.bilibili.com/video/BVxxxx"
```

Ingest a Bilibili source with browser cookies:

```bash
python3 scripts/ingest_source.py \
  "https://www.bilibili.com/video/BVxxxx" \
  --output-dir ./outputs/source \
  --cookies-from-browser chrome \
  --json
```

For a specific section:

```bash
python3 scripts/ingest_source.py \
  "https://www.bilibili.com/video/BVxxxx" \
  --output-dir ./outputs/source \
  --cookies-from-browser chrome \
  --download-section "*01:28:00-01:32:03" \
  --expected-duration 243 \
  --json
```

## Bilibili Notes

Bilibili downloads must be validated with `ffprobe`: a file can appear complete while the video stream is truncated. The ingest script prefers H.264 mp4 tracks, supports cookies and `ffmpeg-full`, records `media_probe`, and retries with a fallback format when stream validation fails.

## Repository Layout

- `SKILL.md`: main agent workflow.
- `references/`: detailed workflow references.
- `scripts/`: reusable ingestion, parsing, ranking, rendering, and verification helpers.
- `agents/`: UI metadata for the skill.
