#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path


DEFAULT_FFPROBE = "/opt/homebrew/opt/ffmpeg-full/bin/ffprobe"


def ffprobe_bin() -> str:
    candidate = Path(DEFAULT_FFPROBE)
    if candidate.exists():
        return str(candidate)
    return "ffprobe"


def probe_duration(path: Path) -> float | None:
    if not path.exists():
        return None
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


def count_ass_events(path: Path) -> int | None:
    if not path.exists():
        return None
    count = 0
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.startswith("Dialogue:"):
            count += 1
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify rendered clip outputs.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--video", help="Final rendered video path.")
    parser.add_argument("--ass", help="ASS subtitle path.")
    parser.add_argument("--srt", help="SRT subtitle path.")
    parser.add_argument("--manifest", help="Render manifest path.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir).expanduser()
    report = {
        "output_dir": str(output_dir),
        "exists": output_dir.exists(),
        "writable": os.access(output_dir, os.W_OK) if output_dir.exists() else False,
        "video": None,
        "ass_events": None,
        "srt_exists": None,
        "manifest_exists": None,
        "ok": True,
        "issues": [],
    }

    if args.video:
        video = Path(args.video).expanduser()
        report["video"] = {
            "path": str(video),
            "exists": video.exists(),
            "duration": probe_duration(video),
        }
        if not video.exists():
            report["issues"].append("video-missing")
    if args.ass:
        ass = Path(args.ass).expanduser()
        report["ass_events"] = count_ass_events(ass)
        if not ass.exists():
            report["issues"].append("ass-missing")
    if args.srt:
        srt = Path(args.srt).expanduser()
        report["srt_exists"] = srt.exists()
        if not srt.exists():
            report["issues"].append("srt-missing")
    if args.manifest:
        manifest = Path(args.manifest).expanduser()
        report["manifest_exists"] = manifest.exists()
        if not manifest.exists():
            report["issues"].append("manifest-missing")

    if not report["exists"]:
        report["issues"].append("output-dir-missing")
    if report["exists"] and not report["writable"]:
        report["issues"].append("output-dir-not-writable")

    report["ok"] = not report["issues"]
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("ok:", report["ok"])
        print("issues:", ", ".join(report["issues"]) or "none")
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
