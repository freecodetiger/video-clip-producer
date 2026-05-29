#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def which(cmd: str) -> str | None:
    env_name = cmd.upper()
    if os.environ.get(env_name):
        return os.environ[env_name]
    found = shutil.which(cmd)
    candidates = []
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Check long-video clip ranking environment.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument("--url", help="Optional source URL to classify and validate.")
    parser.add_argument("--video", help="Optional video path to check.")
    parser.add_argument("--transcript", help="Optional transcript/subtitle path to check.")
    parser.add_argument("--broll-dir", help="Optional B-roll directory to check.")
    parser.add_argument("--output-dir", help="Optional output directory to check.")
    parser.add_argument("--cookies-file", help="Optional exported cookies file to validate.")
    parser.add_argument("--cookies-from-browser", help="Optional browser source name for yt-dlp cookies.")
    args = parser.parse_args()

    ffmpeg = which("ffmpeg")
    ffprobe = which("ffprobe")
    python3 = which("python3")
    yt_dlp_ok, yt_dlp_version = python_module_version("yt_dlp")

    status = {
        "agent_tools": {
            "shell": True,
            "filesystem": True,
        },
        "binaries": {
            "ffmpeg": ffmpeg,
            "ffprobe": ffprobe,
            "python3": python3,
            "yt_dlp": yt_dlp_version if yt_dlp_ok else None,
        },
        "source": {
            "url": args.url,
            "cookies_file": args.cookies_file,
            "cookies_from_browser": args.cookies_from_browser,
        },
        "ffmpeg_filters": {},
        "paths": {
            "video": check_path(args.video),
            "transcript": check_path(args.transcript),
            "broll_dir": check_path(args.broll_dir),
            "output_dir": check_path(args.output_dir),
        },
        "missing": [],
        "ready": True,
    }

    if not ffmpeg:
        status["missing"].append("ffmpeg")
    else:
        for name in ("subtitles", "drawtext"):
            ok = has_filter(ffmpeg, name)
            status["ffmpeg_filters"][name] = ok
            if not ok:
                status["missing"].append(f"ffmpeg-filter:{name}")
        status["ffmpeg_filters"]["libass"] = has_build_flag(ffmpeg, "--enable-libass")
        if not status["ffmpeg_filters"]["libass"]:
            status["missing"].append("ffmpeg-buildflag:libass")

    if not ffprobe:
        status["missing"].append("ffprobe")
    if not python3:
        status["missing"].append("python3")
    if not yt_dlp_ok:
        status["missing"].append("yt-dlp")

    if args.cookies_file:
        cookie_path = Path(args.cookies_file).expanduser()
        status["source"]["cookies_file_exists"] = cookie_path.exists()
        status["source"]["cookies_file_readable"] = os.access(cookie_path, os.R_OK)
        if not cookie_path.exists() or not os.access(cookie_path, os.R_OK):
            status["missing"].append("cookies-file-invalid")

    try:
        import PIL  # type: ignore

        status["python_modules"] = {"PIL": True}
    except Exception:
        status["python_modules"] = {"PIL": False}
        status["missing"].append("python-module:PIL")

    try:
        import cv2  # type: ignore

        status["python_modules"]["cv2"] = True
    except Exception:
        status["python_modules"]["cv2"] = False

    if args.broll_dir:
        p = Path(args.broll_dir).expanduser()
        if not p.exists():
            status["missing"].append("broll-dir-missing")
        elif not any(p.glob("*.mp4")) and not any(p.glob("*.mov")) and not any(p.glob("*.mkv")):
            status["missing"].append("broll-dir-empty")

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
        "先确认 Agent tools、shell 和文件系统可用。",
        "确保 ffmpeg/ffprobe 可执行，且 ffmpeg 支持 subtitles/drawtext。",
        "确保 ffmpeg 构建包含 libass。",
        "确保 yt-dlp 可用，用于下载高清视频和字幕。",
        "如果字幕或高清下载受限，准备 cookies-from-browser 或 cookies.txt。",
        "准备可读的 transcript / subtitle 文件。",
        "如果要做抖音励志风包装，准备可读的本地 B-roll 目录。",
        "确保输出目录可写。",
    ]

    if args.json:
        print(json.dumps(status, ensure_ascii=False, indent=2))
    else:
        print("ready:", status["ready"])
        print("missing:", ", ".join(status["missing"]) or "none")
    return 0 if status["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
