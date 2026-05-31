# Video Clip Producer

Codex skill for turning long YouTube, Bilibili, or local videos into ranked short-video candidates and renderable final clips with normalized subtitles, B-roll planning, burned ASS subtitles, QA reports, and delivery manifests.

The skill is now organized as a stage-gated video production pipeline: every step has explicit inputs, outputs, commands, blocking conditions, and verification.

## Modes

- `candidate_only`: ingest source, normalize subtitles, rank candidates, then stop for selection.
- `render_draft`: generate a reviewable draft; visual or B-roll gaps are allowed if recorded.
- `render_final`: require clean source video, structured subtitles, B-roll/source manifest, render manifest, strict QA, and delivery artifacts.

## Standard Output Layout

```text
<video_root>/
  source/
  subtitles/
  segments/
  assets/
  render_specs/
  renders/
  qa/
  delivery/
```

Final delivery must include `final.mp4`, `render_manifest.json`, `normalized_cues.json`, `subtitles_final.ass`, and `qa_report.json`.

## Quick Start

Check task-specific capabilities:

```bash
python3 scripts/check_env.py --task ingest --json
python3 scripts/check_env.py --task subtitle --json
python3 scripts/check_env.py --task render --json
python3 scripts/check_env.py --task final --json
```

Ingest a URL:

```bash
python3 scripts/ingest_source.py \
  --url "https://www.bilibili.com/video/BVxxxx" \
  --out ./outputs/my_video/source \
  --cookies-from-browser chrome \
  --json
```

Adopt a local source:

```bash
python3 scripts/ingest_source.py \
  --local ./source.mp4 \
  --out ./outputs/my_video/source \
  --json
```

Normalize subtitles:

```bash
python3 scripts/parse_transcript.py \
  --input ./outputs/my_video/source/source.srt \
  --out ./outputs/my_video/subtitles/normalized_cues.json \
  --lead-sec 0.8 \
  --json
```

Rank candidate segments:

```bash
python3 scripts/rank_segments.py \
  --input ./outputs/my_video/subtitles/normalized_cues.json \
  --mode traffic \
  --top-k 5 \
  --json
```

Create a render spec template:

```bash
python3 scripts/render_clip.py --print-spec-template
```

Dry-run or render:

```bash
python3 scripts/render_clip.py --spec ./outputs/my_video/render_specs/render_spec.json --dry-run
python3 scripts/render_clip.py --spec ./outputs/my_video/render_specs/render_spec.json
```

Strict verification:

```bash
python3 scripts/verify_render.py \
  --spec ./outputs/my_video/render_specs/render_spec.json \
  --video ./outputs/my_video/renders/final.mp4 \
  --strict \
  --json > ./outputs/my_video/qa/qa_report.json
```

## Key Artifacts

- `normalized_cues.json`: structured subtitle cues with `cue_id`, source timing, display timing, `en`, `zh`, source file, and optional speaker.
- `render_spec.json`: replayable render contract containing source video, segment boundaries, subtitle source, subtitle lead, layout profile, B-roll plan, and output profile.
- `subtitles_preview.ass` / `subtitles_final.ass`: ASS subtitles generated from normalized cues.
- `subtitle_timing_report.json`: cue timing, lane assignment, lead, and overlap-related metadata.
- `broll_plan.json` / `asset_manifest.json`: B-roll timing, source, license/source note, and subtitle avoidance strategy.
- `render_manifest.json`: final render metadata, cue count, lead, B-roll coverage, ffmpeg info, input/output hashes, and delivery paths.

## Bilibili Notes

Bilibili downloads must be validated with `ffprobe`: a file can appear complete while the video stream is truncated. The ingest script prefers H.264 mp4 tracks, supports cookies and `ffmpeg-full`, records `media_probe`, and retries with a fallback format when stream validation fails.

## Repository Layout

- `SKILL.md`: main stage-gated agent workflow.
- `references/`: detailed workflow references.
- `scripts/`: ingestion, subtitle normalization, ranking, rendering, and verification helpers.
- `tests/`: contract tests for the productized pipeline.
- `agents/`: UI metadata for the skill.

## Verification

Recommended checks before committing changes:

```bash
python3 -m py_compile scripts/*.py
python3 -m unittest tests/test_pipeline_contracts.py
python3 scripts/check_env.py --task render --json
python3 scripts/render_clip.py --print-spec-template
```
