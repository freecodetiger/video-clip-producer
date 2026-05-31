#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def which(cmd: str) -> str | None:
    env_name = cmd.upper()
    candidates = []
    if os.environ.get(env_name):
        candidates.append(os.environ[env_name])
    found = shutil.which(cmd)
    if found:
        candidates.append(found)
    candidates.extend(
        [
            f"/opt/homebrew/opt/ffmpeg-full/bin/{cmd}",
            f"/opt/homebrew/bin/{cmd}",
            f"/usr/local/bin/{cmd}",
            f"/usr/bin/{cmd}",
        ]
    )
    for candidate in candidates:
        path = Path(candidate)
        if path.exists() and os.access(path, os.X_OK):
            version_flag = "--version" if cmd.startswith("python") else "-version"
            code, _ = run([str(path), version_flag])
            if code == 0:
                return str(path)
    return None


def run(cmd: list[str]) -> tuple[int, str]:
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
        return 0, out
    except subprocess.CalledProcessError as e:
        return e.returncode, e.output
    except Exception as e:
        return 1, str(e)


def python_module_version(module: str) -> tuple[bool, str | None]:
    candidates = [module, module.replace("_", "-")]
    code = f"""
import importlib.metadata as m
for name in {candidates!r}:
    try:
        print(m.version(name))
        raise SystemExit(0)
    except Exception:
        pass
try:
    import {module} as mod
    print(getattr(mod, '__version__', 'ok'))
except Exception:
    raise SystemExit(1)
"""
    code, out = run([sys.executable, "-c", code])
    if code == 0:
        return True, out.strip()
    return False, None


def has_filter(ffmpeg: str, name: str) -> bool:
    return name in list_ffmpeg_components(ffmpeg, "-filters")


def has_encoder(ffmpeg: str, name: str) -> bool:
    return name in list_ffmpeg_components(ffmpeg, "-encoders")


def list_ffmpeg_components(ffmpeg: str, flag: str) -> set[str]:
    code, out = run([ffmpeg, "-hide_banner", flag])
    if code != 0:
        return set()
    names = set()
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2 and (parts[0][0] == "." or parts[0][0].isalpha()):
            names.add(parts[1])
    return names


def ffmpeg_version(ffmpeg: str) -> str | None:
    code, out = run([ffmpeg, "-version"])
    if code != 0:
        return None
    return out.splitlines()[0] if out.splitlines() else None


def smoke_test_ass_burn(ffmpeg: str) -> dict:
    with tempfile.TemporaryDirectory(prefix="video-clip-producer-ffmpeg-") as temp:
        temp_dir = Path(temp)
        ass = temp_dir / "subtitle.ass"
        out = temp_dir / "out.mp4"
        ass.write_text(
            """[Script Info]
ScriptType: v4.00+
PlayResX: 320
PlayResY: 180

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,24,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,20,20,20,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:01.00,Default,,0,0,0,,字幕 smoke test
""",
            encoding="utf-8",
        )
        escaped_ass = str(ass).replace(":", r"\:")
        ass_filter = f"ass={escaped_ass}"
        cmd = [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=320x180:d=1",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=48000:cl=stereo",
            "-vf",
            ass_filter,
            "-t",
            "1",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            "-shortest",
            str(out),
        ]
        code, output = run(cmd)
        return {
            "ok": code == 0 and out.exists() and out.stat().st_size > 0,
            "returncode": code,
            "output": output.strip()[-2000:],
        }


def has_filter_legacy(ffmpeg: str, name: str) -> bool:
    code, out = run([ffmpeg, "-hide_banner", "-filters"])
    if code != 0:
        return False
    return name in out


def has_build_flag(ffmpeg: str, flag: str) -> bool:
    code, out = run([ffmpeg, "-buildconf"])
    if code != 0:
        return False
    return flag in out


def check_path(path: str | None) -> dict:
    if not path:
        return {"provided": False, "exists": None, "readable": None, "path": None}
    p = Path(path).expanduser()
    return {
        "provided": True,
        "path": str(p),
        "exists": p.exists(),
        "readable": os.access(p, os.R_OK),
    }


def add_missing(target: list[str], name: str, required: bool) -> None:
    if required:
        target.append(name)


def main() -> int:
    parser = argparse.ArgumentParser(description="Capability-first environment check for video clipping.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument(
        "--task",
        choices=["auto", "ingest", "subtitle", "rank", "render", "final", "render-broll"],
        default="auto",
        help="Task profile. Only capabilities needed by this profile are hard requirements.",
    )
    parser.add_argument("--url", help="Optional source URL to classify and validate.")
    parser.add_argument("--video", help="Optional video path to check.")
    parser.add_argument("--transcript", help="Optional transcript/subtitle path to check.")
    parser.add_argument("--broll-dir", help="Optional B-roll directory to check.")
    parser.add_argument("--output-dir", help="Optional output directory to check.")
    parser.add_argument("--cookies-file", help="Optional exported cookies file to validate.")
    parser.add_argument("--cookies-from-browser", help="Optional browser source name for yt-dlp cookies.")
    parser.add_argument("--need-download", action="store_true", help="Require URL download capability.")
    parser.add_argument("--need-render", action="store_true", help="Require ffmpeg render/mux capability.")
    parser.add_argument("--need-subtitle-burn", action="store_true", help="Require ASS/SRT subtitle burn-in capability.")
    parser.add_argument("--need-drawtext", action="store_true", help="Require ffmpeg drawtext capability.")
    parser.add_argument("--need-broll", action="store_true", help="Require a readable non-empty B-roll directory.")
    parser.add_argument("--deep-ffmpeg-check", action="store_true", help="Run a real ASS burn smoke test.")
    parser.add_argument("--skip-deep-ffmpeg-check", action="store_true", help="Skip the ASS burn smoke test even when rendering subtitles.")
    args = parser.parse_args()

    source_path = Path(args.url).expanduser() if args.url else None
    url_is_local = bool(source_path and source_path.exists())
    task = args.task
    need_download = args.need_download or (task in {"ingest"} and not url_is_local)
    need_render = args.need_render or task in {"render", "final", "render-broll"}
    need_subtitle_burn = args.need_subtitle_burn or task in {"render", "final", "render-broll"}
    need_broll = args.need_broll or task == "render-broll"
    if task == "auto":
        need_download = need_download or bool(args.url and not url_is_local)
        need_render = need_render or bool(args.video)
        need_subtitle_burn = need_subtitle_burn or need_render
        need_broll = need_broll or bool(args.broll_dir)
    deep_ffmpeg_check = args.deep_ffmpeg_check or (need_subtitle_burn and not args.skip_deep_ffmpeg_check)

    ffmpeg = which("ffmpeg")
    ffprobe = which("ffprobe")
    python3 = which("python3")
    yt_dlp_ok, yt_dlp_version = python_module_version("yt_dlp")

    status = {
        "agent_tools": {
            "shell": True,
            "filesystem": True,
        },
        "task": task,
        "binaries": {
            "ffmpeg": ffmpeg,
            "ffprobe": ffprobe,
            "python3": python3,
            "yt_dlp": yt_dlp_version if yt_dlp_ok else None,
        },
        "source": {
            "url": args.url,
            "url_is_local_file": url_is_local,
            "cookies_file": args.cookies_file,
            "cookies_from_browser": args.cookies_from_browser,
        },
        "requirements": {
            "download": need_download,
            "render": need_render,
            "subtitle_burn": need_subtitle_burn,
            "drawtext": args.need_drawtext,
            "broll": need_broll,
            "deep_ffmpeg_check": deep_ffmpeg_check,
        },
        "ffmpeg_filters": {},
        "ffmpeg_encoders": {},
        "ffmpeg_smoke_tests": {},
        "paths": {
            "video": check_path(args.video),
            "transcript": check_path(args.transcript),
            "broll_dir": check_path(args.broll_dir),
            "output_dir": check_path(args.output_dir),
        },
        "missing": [],
        "warnings": [],
        "ready": True,
    }

    if not ffmpeg:
        add_missing(status["missing"], "ffmpeg", need_download or need_render or need_subtitle_burn or args.need_drawtext)
    else:
        status["binaries"]["ffmpeg_version"] = ffmpeg_version(ffmpeg)
        for name in ("scale", "crop", "format", "loudnorm"):
            ok = has_filter(ffmpeg, name)
            status["ffmpeg_filters"][name] = ok
            add_missing(status["missing"], f"ffmpeg-filter:{name}", need_render and not ok)
        for name in ("ass", "subtitles", "drawtext"):
            ok = has_filter(ffmpeg, name)
            status["ffmpeg_filters"][name] = ok
            if name in {"ass", "subtitles"}:
                add_missing(status["missing"], f"ffmpeg-filter:{name}", need_subtitle_burn and not ok)
            elif name == "drawtext":
                add_missing(status["missing"], f"ffmpeg-filter:{name}", args.need_drawtext and not ok)
        for name in ("libx264", "aac"):
            ok = has_encoder(ffmpeg, name)
            status["ffmpeg_encoders"][name] = ok
            add_missing(status["missing"], f"ffmpeg-encoder:{name}", need_render and not ok)
        status["ffmpeg_filters"]["libass"] = has_build_flag(ffmpeg, "--enable-libass")
        if deep_ffmpeg_check:
            smoke = smoke_test_ass_burn(ffmpeg)
            status["ffmpeg_smoke_tests"]["ass_burn_libx264_aac"] = smoke
            add_missing(status["missing"], "ffmpeg-smoke-test:ass-burn", not smoke["ok"])
        if need_subtitle_burn and not status["ffmpeg_filters"]["libass"]:
            smoke_ok = status["ffmpeg_smoke_tests"].get("ass_burn_libx264_aac", {}).get("ok")
            if smoke_ok:
                status["warnings"].append("ffmpeg-buildflag:libass-not-reported-but-smoke-test-passed")
            else:
                status["missing"].append("ffmpeg-buildflag:libass")

    if not ffprobe:
        add_missing(status["missing"], "ffprobe", need_download or need_render)
    if not python3:
        add_missing(status["missing"], "python3", need_download)
    if not yt_dlp_ok:
        add_missing(status["missing"], "yt-dlp", need_download)

    if args.cookies_file:
        cookie_path = Path(args.cookies_file).expanduser()
        status["source"]["cookies_file_exists"] = cookie_path.exists()
        status["source"]["cookies_file_readable"] = os.access(cookie_path, os.R_OK)
        if not cookie_path.exists() or not os.access(cookie_path, os.R_OK):
            status["missing"].append("cookies-file-invalid")
    elif args.url and "bilibili." in args.url and need_download and not args.cookies_from_browser:
        status["warnings"].append("bilibili-cookies-not-provided")

    try:
        import PIL  # type: ignore

        status["python_modules"] = {"PIL": True}
    except Exception:
        status["python_modules"] = {"PIL": False}
        status["warnings"].append("python-module:PIL-missing")

    try:
        import cv2  # type: ignore

        status["python_modules"]["cv2"] = True
    except Exception:
        status["python_modules"]["cv2"] = False
        status["warnings"].append("python-module:cv2-missing")

    if args.broll_dir or need_broll:
        p = Path(args.broll_dir).expanduser() if args.broll_dir else None
        if p is None or not p.exists():
            add_missing(status["missing"], "broll-dir-missing", need_broll)
            if not need_broll:
                status["warnings"].append("broll-dir-missing")
        elif not any(p.glob("*.mp4")) and not any(p.glob("*.mov")) and not any(p.glob("*.mkv")):
            add_missing(status["missing"], "broll-dir-empty", need_broll)
            if not need_broll:
                status["warnings"].append("broll-dir-empty")

    if args.output_dir:
        p = Path(args.output_dir).expanduser()
        if not p.exists():
            try:
                p.mkdir(parents=True, exist_ok=True)
            except Exception:
                status["missing"].append("output-dir-not-writable")
        elif not os.access(p, os.W_OK):
            status["missing"].append("output-dir-not-writable")

    status["ready"] = len(status["missing"]) == 0
    status["recommendations"] = [
        "只补当前任务缺失的 required 能力，不因 optional warning 重装环境。",
        "macOS 上字幕烧录或渲染能力缺失时，优先建议安装 ffmpeg-full，例如：brew install ffmpeg-full。",
        "Bilibili 高清视频和字幕优先使用 --cookies-from-browser chrome 或 cookies.txt。",
        "Bilibili 下载后必须用 ffprobe 校验视频轨和音轨时长。",
        "只有烧录字幕时才要求 ass/subtitles/libass；只有使用文字叠加时才要求 drawtext。",
    ]

    if args.json:
        print(json.dumps(status, ensure_ascii=False, indent=2))
    else:
        print("ready:", status["ready"])
        print("missing:", ", ".join(status["missing"]) or "none")
    return 0 if status["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
