#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any


DEFAULT_FFMPEG = "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg"
DEFAULT_FFPROBE = "/opt/homebrew/opt/ffmpeg-full/bin/ffprobe"


def find_bin(name: str, default: str) -> str:
    env = os.environ.get(name.upper())
    if env and Path(env).exists():
        return env
    if Path(default).exists():
        return default
    found = shutil.which(name)
    if found:
        return found
    raise SystemExit(f"Missing executable: {name}")


def run(cmd: list[str], dry_run: bool = False) -> None:
    print(" ".join(shlex.quote(x) for x in cmd))
    if not dry_run:
        subprocess.run(cmd, check=True)


def ass_time(sec: float) -> str:
    cs = int(round(max(0.0, sec) * 100))
    h, rem = divmod(cs, 3600 * 100)
    m, rem = divmod(rem, 60 * 100)
    s, c = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{c:02d}"


def srt_time(sec: float) -> str:
    ms = int(round(max(0.0, sec) * 1000))
    h, rem = divmod(ms, 3600 * 1000)
    m, rem = divmod(rem, 60 * 1000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def escape_ass(text: str) -> str:
    return text.replace("{", r"\{").replace("}", r"\}").replace("\n", r"\N")


def shift_times(start: float, end: float, advance: float) -> tuple[float, float]:
    shifted_start = max(0.0, start - advance)
    shifted_end = max(shifted_start + 0.08, end - advance)
    return shifted_start, shifted_end


def read_spec(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("Render spec must be a JSON object.")
    return data


def require_path(value: str | None, label: str) -> Path:
    if not value:
        raise SystemExit(f"Missing required field: {label}")
    path = Path(value).expanduser()
    if not path.exists():
        raise SystemExit(f"{label} does not exist: {path}")
    return path


def file_sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def duration_from_spec(spec: dict[str, Any]) -> float:
    if "duration" in spec:
        return float(spec["duration"])
    if "segment_start" in spec and "segment_end" in spec:
        return float(spec["segment_end"]) - float(spec["segment_start"])
    if "source_start" in spec and "source_end" in spec:
        return float(spec["source_end"]) - float(spec["source_start"])
    visuals = spec.get("visuals") or []
    if visuals:
        return max(float(item["end"]) for item in visuals)
    raise SystemExit("Missing duration. Provide duration, source_end, or visuals.")


def segment_start_from_spec(spec: dict[str, Any]) -> float:
    return float(spec.get("segment_start", spec.get("source_start", 0.0)))


def output_dir_from_spec(spec: dict[str, Any]) -> Path:
    output_profile = spec.get("output_profile") or {}
    return Path(output_profile.get("output_dir") or spec.get("output_dir") or ".").expanduser()


def final_name_from_spec(spec: dict[str, Any]) -> str:
    output_profile = spec.get("output_profile") or {}
    return str(
        output_profile.get("final_name")
        or spec.get("final_name")
        or f"{spec.get('clip_title', 'final')}.mp4"
    )


def render_profile(spec: dict[str, Any]) -> dict[str, Any]:
    profile = dict(spec.get("render") or {})
    profile.update(spec.get("layout_profile") or {})
    output_profile = spec.get("output_profile") or {}
    for key in ("width", "height", "fps", "crf", "preset"):
        if key in output_profile:
            profile[key] = output_profile[key]
    profile.update(output_profile.get("render") or {})
    return profile


def ffmpeg_version(ffmpeg: str) -> str | None:
    try:
        out = subprocess.check_output([ffmpeg, "-version"], text=True, stderr=subprocess.STDOUT)
    except Exception:
        return None
    return out.splitlines()[0] if out.splitlines() else None


def load_normalized_cues(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        cues = data
        meta: dict[str, Any] = {"schema": "legacy-list"}
    elif isinstance(data, dict):
        cues = data.get("cues") or data.get("segments") or data.get("items") or []
        meta = data
    else:
        raise SystemExit("subtitle_source must be a JSON object or list.")
    normalized = []
    for idx, cue in enumerate(cues, 1):
        source_start = float(cue.get("source_start", cue.get("start", 0.0)))
        source_end = float(cue.get("source_end", cue.get("end", source_start + 0.08)))
        normalized.append(
            {
                "cue_id": cue.get("cue_id") or f"cue_{idx:04d}",
                "source_start": source_start,
                "source_end": source_end,
                "display_start": float(cue.get("display_start", source_start)),
                "display_end": float(cue.get("display_end", source_end)),
                "zh": str(cue.get("zh") or cue.get("cn") or ""),
                "en": str(cue.get("en") or cue.get("text") or ""),
                "speaker_optional": cue.get("speaker_optional") or cue.get("speaker"),
                "source_file": cue.get("source_file") or meta.get("source_file") or str(path),
            }
        )
    return normalized, meta


def wrap_ass_text(zh: str, en: str) -> str:
    parts = []
    if zh:
        parts.append(escape_ass(zh))
    if en:
        parts.append(r"{\fs30}" + escape_ass(en))
    return r"\N".join(parts) if parts else ""


def assign_lanes(cues: list[dict[str, Any]], lanes: int) -> list[dict[str, Any]]:
    last_end = [0.0 for _ in range(max(1, lanes))]
    assigned = []
    for cue in sorted(cues, key=lambda item: (item["start"], item["end"])):
        lane = next((idx for idx, end in enumerate(last_end) if cue["start"] >= end), None)
        if lane is None:
            lane = min(range(len(last_end)), key=lambda idx: last_end[idx])
            cue["start"] = max(cue["start"], last_end[lane])
            cue["lane_adjusted"] = True
        last_end[lane] = cue["end"]
        cue["lane"] = lane
        assigned.append(cue)
    return assigned


def write_normalized_subtitles(out_dir: Path, spec: dict[str, Any]) -> tuple[Path, Path, dict[str, Any]]:
    source = require_path(str(spec.get("subtitle_source") or ""), "subtitle_source")
    cues, meta = load_normalized_cues(source)
    source_start = segment_start_from_spec(spec)
    duration = duration_from_spec(spec)
    source_end = source_start + duration
    lead_sec = float(spec.get("subtitle_lead_sec", meta.get("lead_sec", 0.8)))
    mode = str(spec.get("subtitle_mode") or "rolling_bilingual")
    layout = render_profile(spec)
    width = int(layout.get("width", 1280))
    height = int(layout.get("height", 720))
    lane_count = int(layout.get("lanes", 2))
    lane_bottoms = layout.get("lane_bottoms") or [76, 154]

    timeline_cues: list[dict[str, Any]] = []
    for cue in cues:
        if cue["source_end"] < source_start or cue["source_start"] > source_end:
            continue
        display_start = float(cue.get("display_start", cue["source_start"] - lead_sec))
        display_end = float(cue.get("display_end", cue["source_end"]))
        start = max(0.0, display_start - source_start)
        end = min(duration, display_end - source_start)
        if end <= start:
            end = min(duration, start + 0.08)
        if end <= 0 or start >= duration:
            continue
        timeline_cues.append({**cue, "start": start, "end": end})

    timeline_cues = assign_lanes(timeline_cues, lane_count)
    ass_header = f"""[Script Info]
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
PlayResX: {width}
PlayResY: {height}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Rolling,Arial Unicode MS,44,&H00FFFFFF,&H000000FF,&H00101010,&H99000000,1,0,0,0,100,100,0,0,1,3,0,2,80,80,76,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ass_events = []
    srt_blocks = []
    report_cues = []
    for idx, cue in enumerate(timeline_cues, 1):
        margin_v = int(lane_bottoms[min(int(cue["lane"]), len(lane_bottoms) - 1)])
        text = wrap_ass_text(cue.get("zh", ""), cue.get("en", ""))
        ass_events.append(
            f"Dialogue: {cue['lane']},{ass_time(cue['start'])},{ass_time(cue['end'])},Rolling,,0,0,{margin_v},,{{\\fad(60,80)}}{text}"
        )
        srt_text = "\n".join(part for part in [cue.get("zh", ""), cue.get("en", "")] if part)
        srt_blocks.append(f"{idx}\n{srt_time(cue['start'])} --> {srt_time(cue['end'])}\n{srt_text}\n")
        report_cues.append(
            {
                "cue_id": cue["cue_id"],
                "source_start": cue["source_start"],
                "source_end": cue["source_end"],
                "display_start": round(cue["start"], 3),
                "display_end": round(cue["end"], 3),
                "lane": cue["lane"],
                "lane_adjusted": bool(cue.get("lane_adjusted")),
            }
        )

    final_ass = out_dir / "subtitles_final.ass"
    preview_ass = out_dir / "subtitles_preview.ass"
    srt = out_dir / "subtitles_final.srt"
    timing_report = out_dir / "subtitle_timing_report.json"
    ass_text = ass_header + "\n".join(ass_events) + "\n"
    final_ass.write_text(ass_text, encoding="utf-8")
    preview_ass.write_text(ass_text, encoding="utf-8")
    srt.write_text("\n".join(srt_blocks), encoding="utf-8")
    report = {
        "subtitle_source": str(source),
        "subtitle_mode": mode,
        "lead_sec": lead_sec,
        "end_policy": "source_end",
        "cue_count": len(timeline_cues),
        "lane_count": lane_count,
        "lane_bottoms": lane_bottoms,
        "cues": report_cues,
    }
    timing_report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return final_ass, srt, report


def write_bilingual_subtitles(out_dir: Path, spec: dict[str, Any]) -> tuple[Path | None, Path | None, dict[str, Any]]:
    if spec.get("subtitle_source"):
        ass, srt, report = write_normalized_subtitles(out_dir, spec)
        return ass, srt, report

    subtitle = spec.get("subtitle") or {}
    existing_ass = subtitle.get("ass_file")
    existing_srt = subtitle.get("srt_file")
    if existing_ass:
        ass_path = require_path(str(existing_ass), "subtitle.ass_file")
        srt_path = require_path(str(existing_srt), "subtitle.srt_file") if existing_srt else None
        return ass_path, srt_path, {
            "mode": subtitle.get("mode", "external_ass"),
            "advance_seconds": float(subtitle.get("advance_seconds", subtitle.get("offset", 0.0))),
            "events": None,
        }

    items = subtitle.get("items") or spec.get("subtitles") or []
    if not items:
        return None, None, {
            "mode": "none",
            "advance_seconds": 0.0,
            "events": 0,
        }

    advance = float(subtitle.get("advance_seconds", subtitle.get("offset", 0.0)))
    ass = out_dir / "双语字幕.ass"
    srt = out_dir / "双语字幕.srt"
    width = int(spec.get("render", {}).get("width", 1280))
    height = int(spec.get("render", {}).get("height", 720))
    cn_size = int(subtitle.get("cn_font_size", 42))
    en_size = int(subtitle.get("en_font_size", 24))

    header = f"""[Script Info]
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
PlayResX: {width}
PlayResY: {height}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: CN,Arial Unicode MS,{cn_size},&H00FFFFFF,&H000000FF,&H00101010,&H99000000,1,0,0,0,100,100,0,0,1,3,0,2,70,70,76,1
Style: EN,Arial Unicode MS,{en_size},&H00E6E6E6,&H000000FF,&H00101010,&H99000000,0,0,0,0,100,100,0,0,1,2,0,2,90,90,38,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ass_events: list[str] = []
    srt_blocks: list[str] = []
    for idx, item in enumerate(items, 1):
        start, end = shift_times(float(item["start"]), float(item["end"]), advance)
        cn = escape_ass(str(item.get("cn") or item.get("zh") or item.get("text") or ""))
        en = escape_ass(str(item.get("en") or ""))
        ass_events.append(f"Dialogue: 0,{ass_time(start)},{ass_time(end)},CN,,0,0,0,,{{\\fad(60,80)}}{cn}")
        if en:
            ass_events.append(f"Dialogue: 1,{ass_time(start)},{ass_time(end)},EN,,0,0,0,,{{\\fad(60,80)}}{en}")
        srt_text = cn.replace(r"\N", " ")
        if en:
            srt_text += "\n" + en.replace(r"\N", " ")
        srt_blocks.append(f"{idx}\n{srt_time(start)} --> {srt_time(end)}\n{srt_text}\n")

    ass.write_text(header + "\n".join(ass_events) + "\n", encoding="utf-8")
    srt.write_text("\n".join(srt_blocks), encoding="utf-8")
    return ass, srt, {
        "mode": subtitle.get("mode", "source_offset" if advance else "source"),
        "advance_seconds": advance,
        "events": len(items),
    }


def make_aroll(ffmpeg: str, source: Path, out_path: Path, abs_start: float, duration: float, spec: dict[str, Any], dry_run: bool) -> None:
    render = render_profile(spec)
    width = int(render.get("width", 1280))
    height = int(render.get("height", 720))
    fps = int(render.get("fps", 30))
    crf = str(render.get("crf", 18))
    preset = str(render.get("preset", "veryfast"))
    fg_width = int(render.get("foreground_width", width * 3 // 4))
    filt = (
        "[0:v]split=2[base][fg];"
        f"[base]scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},boxblur=18:2,eq=brightness=-0.07:saturation=0.9[bg];"
        f"[fg]scale={fg_width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={fg_width}:{height}:(ow-iw)/2:(oh-ih)/2:black,eq=contrast=1.08:saturation=1.05[main];"
        "[bg][main]overlay=(W-w)/2:(H-h)/2,format=yuv420p"
    )
    run([
        ffmpeg, "-y", "-ss", f"{abs_start:.3f}", "-t", f"{duration:.3f}",
        "-i", str(source), "-an", "-vf", filt, "-r", str(fps),
        "-c:v", "libx264", "-preset", preset, "-crf", crf, str(out_path),
    ], dry_run)


def make_broll(ffmpeg: str, out_path: Path, item: dict[str, Any], duration: float, spec: dict[str, Any], dry_run: bool) -> None:
    broll = require_path(str(item.get("file") or item.get("path") or ""), "broll_plan[].file")
    render = render_profile(spec)
    width = int(render.get("width", 1280))
    height = int(render.get("height", 720))
    fps = int(render.get("fps", 30))
    crf = str(render.get("crf", 18))
    preset = str(render.get("preset", "veryfast"))
    offset = float(item.get("offset", 0.0))
    filt = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},eq=contrast=1.14:saturation=1.12,"
        "unsharp=5:5:0.45:3:3:0.25,format=yuv420p"
    )
    run([
        ffmpeg, "-y", "-stream_loop", "-1", "-ss", f"{offset:.3f}",
        "-t", f"{duration:.3f}", "-i", str(broll), "-an", "-vf", filt,
        "-r", str(fps), "-c:v", "libx264", "-preset", preset, "-crf", crf, str(out_path),
    ], dry_run)


def make_audio(ffmpeg: str, source: Path, out_path: Path, source_start: float, duration: float, dry_run: bool) -> None:
    run([
        ffmpeg, "-y", "-ss", f"{source_start:.3f}", "-t", f"{duration:.3f}",
        "-i", str(source), "-vn", "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
        "-c:a", "aac", "-b:a", "160k", str(out_path),
    ], dry_run)


def concat_videos(ffmpeg: str, parts: list[Path], out_path: Path, dry_run: bool) -> None:
    list_file = out_path.parent / "concat_video.txt"
    list_file.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
    run([ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(out_path)], dry_run)


def mux_and_sub(ffmpeg: str, video: Path, audio: Path, ass: Path | None, out_path: Path, spec: dict[str, Any], dry_run: bool) -> None:
    cmd = [ffmpeg, "-y", "-i", str(video), "-i", str(audio)]
    if ass:
        fontsdir = str(spec.get("subtitle", {}).get("fontsdir", "/System/Library/Fonts/Supplemental"))
        escaped_ass = str(ass).replace(":", r"\:")
        cmd += ["-vf", f"ass={escaped_ass}:fontsdir={fontsdir}"]
    cmd += [
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-preset", str(render_profile(spec).get("preset", "veryfast")),
        "-crf", str(render_profile(spec).get("crf", 18)),
        "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(out_path),
    ]
    run(cmd, dry_run)


def write_notes(out_dir: Path, spec: dict[str, Any]) -> None:
    titles = spec.get("titles") or []
    if isinstance(titles, str):
        titles = [line for line in titles.splitlines() if line.strip()]
    caption = str(spec.get("caption") or "")
    bgm = spec.get("bgm") or []
    (out_dir / "推荐标题.md").write_text(
        "# 推荐标题\n\n" + "\n".join(f"- {line}" for line in titles) + "\n",
        encoding="utf-8",
    )
    (out_dir / "配文.md").write_text(
        "# 配文\n\n" + caption + "\n\n# 推荐 BGM\n\n" + "\n".join(f"- {line}" for line in bgm) + "\n",
        encoding="utf-8",
    )


def spec_template() -> dict[str, Any]:
    return {
        "source_video": "/path/to/source.mp4",
        "source_url": "https://www.youtube.com/watch?v=...",
        "source_title": "source title",
        "segment_start": 483.6,
        "segment_end": 532.32,
        "subtitle_source": "subtitles/normalized_cues.json",
        "subtitle_lead_sec": 0.8,
        "subtitle_mode": "rolling_bilingual",
        "layout_profile": {
            "width": 1280,
            "height": 720,
            "fps": 30,
            "lanes": 2,
            "lane_bottoms": [76, 154],
            "crf": 18,
            "preset": "veryfast",
        },
        "broll_plan": [
            {
                "type": "a",
                "start": 0.0,
                "end": 4.4,
                "source": "source_video",
                "subtitle_avoidance": "bottom_safe_lanes",
            },
            {
                "type": "b",
                "start": 4.4,
                "end": 8.9,
                "file": "/path/to/broll.mp4",
                "offset": 0.0,
                "source": "local",
                "subtitle_avoidance": "do_not_cover_bottom_lanes",
            },
        ],
        "output_profile": {
            "output_dir": "outputs/<source>/segments/01_<clip_title>",
            "final_name": "final.mp4",
            "width": 1280,
            "height": 720,
            "fps": 30,
        },
        "subtitle_burn_source_is_clean": True,
        "clip_title": "clip title",
        "titles": ["推荐标题一", "推荐标题二"],
        "caption": "短视频配文",
        "bgm": ["cinematic motivational"],
    }


def render(spec: dict[str, Any], dry_run: bool = False) -> dict[str, Any]:
    ffmpeg = find_bin("ffmpeg", DEFAULT_FFMPEG)
    source = require_path(spec.get("source_video"), "source_video")
    if spec.get("subtitle_source") and spec.get("subtitle_burn_source_is_clean") is not True:
        raise SystemExit("Final render is blocked: subtitle_burn_source_is_clean must be true for subtitle burn-in.")
    output_dir = output_dir_from_spec(spec)
    output_dir.mkdir(parents=True, exist_ok=True)
    tmp = output_dir / "_tmp_render"
    tmp.mkdir(parents=True, exist_ok=True)

    source_start = segment_start_from_spec(spec)
    duration = duration_from_spec(spec)
    final_name = final_name_from_spec(spec)
    final_video = output_dir / final_name

    ass, srt, subtitle_report = write_bilingual_subtitles(output_dir, spec)
    visuals = spec.get("broll_plan") or spec.get("visuals") or [{"type": "a", "start": 0.0, "end": duration}]
    (output_dir / "broll_plan.json").write_text(json.dumps(visuals, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    parts: list[Path] = []
    for idx, item in enumerate(visuals, 1):
        start = float(item["start"])
        end = float(item["end"])
        part_duration = max(0.08, end - start)
        part = tmp / f"part_{idx:02d}.mp4"
        if item.get("type") in {"b", "broll"}:
            make_broll(ffmpeg, part, item, part_duration, spec, dry_run)
        else:
            make_aroll(ffmpeg, source, part, source_start + start, part_duration, spec, dry_run)
        parts.append(part)

    video_track = tmp / "video_track.mp4"
    audio_track = tmp / "audio.m4a"
    concat_videos(ffmpeg, parts, video_track, dry_run)
    make_audio(ffmpeg, source, audio_track, source_start, duration, dry_run)
    mux_and_sub(ffmpeg, video_track, audio_track, ass, final_video, spec, dry_run)
    write_notes(output_dir, spec)

    manifest = {
        "source_url": spec.get("source_url"),
        "source_title": spec.get("source_title"),
        "source_video": str(source),
        "source_hash": file_sha256(source),
        "input_hash": file_sha256(source),
        "clip_title": spec.get("clip_title"),
        "start": source_start,
        "end": source_start + duration,
        "duration": duration,
        "subtitle": subtitle_report,
        "subtitle_mode": subtitle_report.get("subtitle_mode") or subtitle_report.get("mode"),
        "source_time_basis": subtitle_report.get("subtitle_source") or spec.get("subtitle_source"),
        "lead_sec": subtitle_report.get("lead_sec", spec.get("subtitle_lead_sec")),
        "end_policy": subtitle_report.get("end_policy"),
        "lane_bottoms": subtitle_report.get("lane_bottoms"),
        "cue_count": subtitle_report.get("cue_count", subtitle_report.get("events")),
        "subtitle_burn_source_is_clean": spec.get("subtitle_burn_source_is_clean"),
        "broll_used": any(item.get("type") in {"b", "broll"} for item in visuals),
        "broll_coverage_sec": round(sum(max(0.0, float(item.get("end", 0)) - float(item.get("start", 0))) for item in visuals if item.get("type") in {"b", "broll"}), 3),
        "broll_coverage": round(sum(max(0.0, float(item.get("end", 0)) - float(item.get("start", 0))) for item in visuals if item.get("type") in {"b", "broll"}) / duration, 4) if duration > 0 else 0.0,
        "broll_plan": str(output_dir / "broll_plan.json"),
        "final_video": str(final_video),
        "output_hash": file_sha256(final_video),
        "ffmpeg": ffmpeg,
        "ffmpeg_version": ffmpeg_version(ffmpeg),
        "subtitle_ass": str(ass) if ass else None,
        "subtitle_srt": str(srt) if srt else None,
        "notes_md": str(output_dir / "配文.md"),
        "title_md": str(output_dir / "推荐标题.md"),
        "dry_run": dry_run,
    }
    (output_dir / "render_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a confirmed viral clip from a JSON spec.")
    parser.add_argument("--spec", help="Render spec JSON path.")
    parser.add_argument("--dry-run", action="store_true", help="Print ffmpeg commands and write manifest without executing ffmpeg.")
    parser.add_argument("--print-spec-template", action="store_true", help="Print an example JSON spec.")
    args = parser.parse_args()

    if args.print_spec_template:
        print(json.dumps(spec_template(), ensure_ascii=False, indent=2))
        return 0
    if not args.spec:
        raise SystemExit("Provide --spec or --print-spec-template.")

    manifest = render(read_spec(Path(args.spec).expanduser()), dry_run=args.dry_run)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
