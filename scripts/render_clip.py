#!/usr/bin/env python3
from __future__ import annotations

import argparse
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


def duration_from_spec(spec: dict[str, Any]) -> float:
    if "duration" in spec:
        return float(spec["duration"])
    if "source_start" in spec and "source_end" in spec:
        return float(spec["source_end"]) - float(spec["source_start"])
    visuals = spec.get("visuals") or []
    if visuals:
        return max(float(item["end"]) for item in visuals)
    raise SystemExit("Missing duration. Provide duration, source_end, or visuals.")


def write_bilingual_subtitles(out_dir: Path, spec: dict[str, Any]) -> tuple[Path | None, Path | None, dict[str, Any]]:
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
    render = spec.get("render", {})
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
    broll = require_path(str(item.get("file") or ""), "visuals[].file")
    render = spec.get("render", {})
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
        "-c:v", "libx264", "-preset", str(spec.get("render", {}).get("preset", "veryfast")),
        "-crf", str(spec.get("render", {}).get("crf", 18)),
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
        "source_start": 483.6,
        "duration": 48.72,
        "output_dir": "outputs/<source>_<platform>_<theme>/01_<clip_title>",
        "clip_title": "clip title",
        "final_name": "clip_title_分镜双语字幕版.mp4",
        "render": {"width": 1280, "height": 720, "fps": 30, "crf": 18, "preset": "veryfast"},
        "visuals": [
            {"type": "a", "start": 0.0, "end": 4.4},
            {"type": "b", "start": 4.4, "end": 8.9, "file": "/path/to/broll.mp4", "offset": 0.0},
        ],
        "subtitle": {
            "mode": "source_offset",
            "advance_seconds": 0.5,
            "items": [
                {"start": 0.28, "end": 2.15, "cn": "中文主字幕", "en": "English subtitle"}
            ],
        },
        "titles": ["推荐标题一", "推荐标题二"],
        "caption": "短视频配文",
        "bgm": ["cinematic motivational"],
    }


def render(spec: dict[str, Any], dry_run: bool = False) -> dict[str, Any]:
    ffmpeg = find_bin("ffmpeg", DEFAULT_FFMPEG)
    source = require_path(spec.get("source_video"), "source_video")
    output_dir = Path(spec.get("output_dir") or ".").expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)
    tmp = output_dir / "_tmp_render"
    tmp.mkdir(parents=True, exist_ok=True)

    source_start = float(spec.get("source_start", 0.0))
    duration = duration_from_spec(spec)
    final_name = str(spec.get("final_name") or f"{spec.get('clip_title', 'clip')}_分镜双语字幕版.mp4")
    final_video = output_dir / final_name

    ass, srt, subtitle_report = write_bilingual_subtitles(output_dir, spec)
    visuals = spec.get("visuals") or [{"type": "a", "start": 0.0, "end": duration}]

    parts: list[Path] = []
    for idx, item in enumerate(visuals, 1):
        start = float(item["start"])
        end = float(item["end"])
        part_duration = max(0.08, end - start)
        part = tmp / f"part_{idx:02d}.mp4"
        if item.get("type") == "b":
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
        "clip_title": spec.get("clip_title"),
        "start": source_start,
        "duration": duration,
        "subtitle": subtitle_report,
        "broll_used": any(item.get("type") == "b" for item in visuals),
        "final_video": str(final_video),
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
