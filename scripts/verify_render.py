#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path


DEFAULT_FFPROBE = "/opt/homebrew/opt/ffmpeg-full/bin/ffprobe"


def ffprobe_bin() -> str:
    env = os.environ.get("FFPROBE")
    if env and Path(env).exists():
        return env
    candidate = Path(DEFAULT_FFPROBE)
    if candidate.exists():
        return str(candidate)
    return "ffprobe"


def ffmpeg_bin() -> str:
    env = os.environ.get("FFMPEG")
    if env and Path(env).exists():
        return env
    found = shutil.which("ffmpeg")
    return found or "ffmpeg"


def probe_media(path: Path) -> dict | None:
    if not path.exists():
        return None
    cmd = [
        ffprobe_bin(),
        "-v",
        "error",
        "-show_entries",
        "stream=index,codec_type,width,height,duration:format=duration",
        "-of",
        "json",
        str(path),
    ]
    try:
        data = json.loads(subprocess.check_output(cmd, text=True))
    except Exception:
        return None
    streams = data.get("streams") or []
    video_streams = [item for item in streams if item.get("codec_type") == "video"]
    audio_streams = [item for item in streams if item.get("codec_type") == "audio"]
    duration = None
    try:
        duration = float((data.get("format") or {}).get("duration"))
    except Exception:
        pass
    return {
        "duration": duration,
        "has_video": bool(video_streams),
        "has_audio": bool(audio_streams),
        "width": video_streams[0].get("width") if video_streams else None,
        "height": video_streams[0].get("height") if video_streams else None,
        "video_streams": len(video_streams),
        "audio_streams": len(audio_streams),
    }


def probe_duration(path: Path) -> float | None:
    if not path.exists():
        return None


def expected_duration_from_spec(spec: dict) -> float | None:
    try:
        if "segment_start" in spec and "segment_end" in spec:
            return float(spec["segment_end"]) - float(spec["segment_start"])
        if "source_start" in spec and "source_end" in spec:
            return float(spec["source_end"]) - float(spec["source_start"])
        if "duration" in spec:
            return float(spec["duration"])
    except Exception:
        return None
    return None


def expected_size_from_spec(spec: dict) -> tuple[int | None, int | None]:
    layout = spec.get("layout_profile") or {}
    output = spec.get("output_profile") or {}
    width = output.get("width", layout.get("width"))
    height = output.get("height", layout.get("height"))
    return (int(width) if width else None, int(height) if height else None)


def extract_qa_frames(video: Path, output_dir: Path, duration: float | None) -> list[str]:
    if duration is None or duration <= 0:
        return []
    frames_dir = output_dir / "qa" / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    points = [
        ("start", min(0.25, duration / 2)),
        ("middle", duration / 2),
        ("subtitle_dense", duration / 2),
        ("broll_overlay", duration / 2),
        ("end", max(0.0, duration - 0.25)),
    ]
    outputs = []
    for label, second in points:
        out = frames_dir / f"{label}.jpg"
        cmd = [
            ffmpeg_bin(),
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            f"{second:.3f}",
            "-i",
            str(video),
            "-frames:v",
            "1",
            str(out),
        ]
        try:
            subprocess.run(cmd, check=True)
        except Exception:
            continue
        if out.exists():
            outputs.append(str(out))
    return outputs
    cmd = [
        ffprobe_bin(),
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=nw=1:nk=1",
        str(path),
    ]
    try:
        out = subprocess.check_output(cmd, text=True).strip()
        return float(out)
    except Exception:
        return None


def parse_ass_time(value: str) -> float:
    match = re.fullmatch(r"(\d+):(\d{2}):(\d{2})\.(\d{2})", value.strip())
    if not match:
        raise ValueError(f"invalid ASS time: {value}")
    h, m, s, cs = map(int, match.groups())
    return h * 3600 + m * 60 + s + cs / 100


def parse_srt_time(value: str) -> float:
    match = re.fullmatch(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})", value.strip())
    if not match:
        raise ValueError(f"invalid SRT time: {value}")
    h, m, s, ms = map(int, match.groups())
    return h * 3600 + m * 60 + s + ms / 1000


def load_manifest(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_spec(path: Path | None) -> dict:
    if path is None or not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def output_dir_from_spec(spec: dict, fallback: str | None) -> Path:
    if fallback:
        return Path(fallback).expanduser()
    output_profile = spec.get("output_profile") or {}
    return Path(output_profile.get("output_dir") or spec.get("output_dir") or ".").expanduser()


def count_ass_events(path: Path) -> int | None:
    if not path.exists():
        return None
    count = 0
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.startswith("Dialogue:"):
            count += 1
    return count


def parse_ass_events(path: Path) -> list[dict]:
    events = []
    if not path.exists():
        return events
    for lineno, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
        if not line.startswith("Dialogue:"):
            continue
        parts = line.split(",", 9)
        if len(parts) < 10:
            events.append({"lineno": lineno, "error": "malformed-dialogue"})
            continue
        layer_raw = parts[0].split(":", 1)[1].strip()
        try:
            start = parse_ass_time(parts[1])
            end = parse_ass_time(parts[2])
        except ValueError as exc:
            events.append({"lineno": lineno, "error": str(exc)})
            continue
        events.append({
            "lineno": lineno,
            "layer": layer_raw or "0",
            "start": start,
            "end": end,
            "style": parts[3].strip(),
            "text": parts[9],
        })
    return events


def parse_srt_cues(path: Path) -> list[dict]:
    cues = []
    if not path.exists():
        return cues
    blocks = re.split(r"\n\s*\n", path.read_text(encoding="utf-8", errors="ignore").strip())
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        timing = next((line for line in lines if "-->" in line), None)
        if not timing:
            continue
        start_raw, end_raw = [part.strip() for part in timing.split("-->", 1)]
        try:
            cues.append({
                "start": parse_srt_time(start_raw),
                "end": parse_srt_time(end_raw),
                "text": "\n".join(line for line in lines if "-->" not in line and not line.isdigit()),
            })
        except ValueError:
            cues.append({"error": f"invalid-timing:{timing}"})
    return cues


def same_layer_overlaps(events: list[dict], gap: float = 0.0) -> list[dict]:
    overlaps = []
    grouped: dict[str, list[dict]] = {}
    for event in events:
        if "error" in event:
            continue
        grouped.setdefault(event["layer"], []).append(event)
    for layer, layer_events in grouped.items():
        layer_events.sort(key=lambda event: (event["start"], event["end"]))
        previous = None
        for event in layer_events:
            if previous and event["start"] < previous["end"] + gap:
                overlaps.append({
                    "layer": layer,
                    "previous_lineno": previous["lineno"],
                    "current_lineno": event["lineno"],
                    "previous_end": previous["end"],
                    "current_start": event["start"],
                })
            if previous is None or event["end"] > previous["end"]:
                previous = event
    return overlaps


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify rendered clip outputs.")
    parser.add_argument("--spec", help="Render spec JSON path.")
    parser.add_argument("--output-dir")
    parser.add_argument("--video", help="Final rendered video path.")
    parser.add_argument("--ass", help="ASS subtitle path.")
    parser.add_argument("--srt", help="SRT subtitle path.")
    parser.add_argument("--manifest", help="Render manifest path.")
    parser.add_argument("--strict", action="store_true", help="Treat final-delivery warnings as blocking issues.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    spec_path = Path(args.spec).expanduser() if args.spec else None
    spec_data = load_spec(spec_path)
    output_dir = output_dir_from_spec(spec_data, args.output_dir)
    manifest = Path(args.manifest).expanduser() if args.manifest else output_dir / "render_manifest.json"
    manifest_data = load_manifest(manifest)
    video_arg = args.video or manifest_data.get("final_video")
    ass_arg = args.ass or manifest_data.get("subtitle_ass")
    srt_arg = args.srt or manifest_data.get("subtitle_srt")
    report = {
        "output_dir": str(output_dir),
        "spec": str(spec_path) if spec_path else None,
        "exists": output_dir.exists(),
        "writable": os.access(output_dir, os.W_OK) if output_dir.exists() else False,
        "video": None,
        "ass_events": None,
        "srt_cues": None,
        "srt_exists": None,
        "manifest_exists": None,
        "subtitle_checks": {},
        "ok": True,
        "issues": [],
        "warnings": [],
    }

    if spec_path and not spec_path.exists():
        report["issues"].append("spec-missing")

    if video_arg:
        video = Path(video_arg).expanduser()
        media = probe_media(video)
        report["video"] = {
            "path": str(video),
            "exists": video.exists(),
            "duration": media.get("duration") if media else None,
            "has_video": media.get("has_video") if media else False,
            "has_audio": media.get("has_audio") if media else False,
            "width": media.get("width") if media else None,
            "height": media.get("height") if media else None,
        }
        if not video.exists():
            report["issues"].append("video-missing")
        if args.strict and video.exists() and report["video"]["duration"] is None:
            report["issues"].append("video-probe-failed")
        if args.strict and media:
            if not media["has_video"]:
                report["issues"].append("video-track-missing")
            if not media["has_audio"]:
                report["issues"].append("audio-track-missing")
            expected_duration = expected_duration_from_spec(spec_data)
            if expected_duration is not None and media["duration"] is not None:
                if abs(media["duration"] - expected_duration) > max(0.35, expected_duration * 0.04):
                    report["issues"].append("video-duration-mismatch")
            expected_width, expected_height = expected_size_from_spec(spec_data)
            if expected_width and media["width"] != expected_width:
                report["issues"].append("video-width-mismatch")
            if expected_height and media["height"] != expected_height:
                report["issues"].append("video-height-mismatch")
            report["qa_frames"] = extract_qa_frames(video, output_dir, media["duration"])
            if not report["qa_frames"]:
                report["warnings"].append("qa-frames-not-generated")
    elif args.strict:
        report["issues"].append("video-not-specified")
    if ass_arg:
        ass = Path(ass_arg).expanduser()
        ass_events = parse_ass_events(ass)
        report["ass_events"] = count_ass_events(ass)
        bad_ass_events = [event for event in ass_events if "error" in event]
        non_positive = [
            event for event in ass_events
            if "error" not in event and event["end"] <= event["start"]
        ]
        overlaps = same_layer_overlaps(ass_events)
        report["subtitle_checks"]["ass_bad_events"] = bad_ass_events
        report["subtitle_checks"]["ass_non_positive_events"] = non_positive
        report["subtitle_checks"]["same_layer_overlaps"] = overlaps
        if not ass.exists():
            report["issues"].append("ass-missing")
        if bad_ass_events:
            report["issues"].append("ass-malformed-dialogue")
        if non_positive:
            report["issues"].append("ass-non-positive-duration")
        if overlaps:
            report["issues"].append("ass-same-layer-overlap")
    elif args.strict:
        report["issues"].append("ass-not-specified")
    if srt_arg:
        srt = Path(srt_arg).expanduser()
        srt_cues = parse_srt_cues(srt)
        report["srt_cues"] = len(srt_cues) if srt.exists() else None
        bad_srt_cues = [cue for cue in srt_cues if "error" in cue]
        non_positive_srt = [
            cue for cue in srt_cues
            if "error" not in cue and cue["end"] <= cue["start"]
        ]
        report["subtitle_checks"]["srt_bad_cues"] = bad_srt_cues
        report["subtitle_checks"]["srt_non_positive_cues"] = non_positive_srt
        report["srt_exists"] = srt.exists()
        if not srt.exists():
            report["issues"].append("srt-missing")
        if bad_srt_cues:
            report["issues"].append("srt-bad-timing")
        if non_positive_srt:
            report["issues"].append("srt-non-positive-duration")
    if args.manifest or args.spec or manifest.exists():
        report["manifest_exists"] = manifest.exists()
        report["manifest"] = {
            "cue_count": manifest_data.get("cue_count"),
            "subtitle_mode": manifest_data.get("subtitle_mode"),
            "source_time_basis": manifest_data.get("source_time_basis"),
            "lead_sec": manifest_data.get("lead_sec"),
            "lane_bottoms": manifest_data.get("lane_bottoms"),
            "subtitle_burn_source_is_clean": manifest_data.get("subtitle_burn_source_is_clean"),
        }
        if not manifest.exists():
            report["issues"].append("manifest-missing")
        cue_count = manifest_data.get("cue_count")
        if isinstance(cue_count, int):
            if report["srt_cues"] is not None and report["srt_cues"] != cue_count:
                report["issues"].append("srt-cue-count-mismatch")
            if report["ass_events"] is not None and report["ass_events"] not in {cue_count, cue_count * 2}:
                report["warnings"].append("ass-event-count-unexpected")
        if manifest.exists() and manifest_data.get("subtitle_burn_source_is_clean") is not True:
            report["warnings"].append("subtitle-clean-source-not-confirmed")
        if manifest.exists() and manifest_data.get("source_time_basis") is None:
            report["warnings"].append("subtitle-source-time-basis-missing")
        if args.strict and manifest.exists():
            required = ["final_video", "subtitle_ass", "cue_count", "lead_sec", "source_time_basis"]
            for key in required:
                if manifest_data.get(key) in {None, ""}:
                    report["issues"].append(f"manifest-missing:{key}")
    elif args.strict:
        report["issues"].append("manifest-missing")

    if not report["exists"]:
        report["issues"].append("output-dir-missing")
    if report["exists"] and not report["writable"]:
        report["issues"].append("output-dir-not-writable")

    if args.strict:
        for warning in report["warnings"]:
            if warning in {"subtitle-clean-source-not-confirmed", "subtitle-source-time-basis-missing"}:
                report["issues"].append(warning)

    report["ok"] = not report["issues"]
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("ok:", report["ok"])
        print("issues:", ", ".join(report["issues"]) or "none")
        print("warnings:", ", ".join(report["warnings"]) or "none")
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
