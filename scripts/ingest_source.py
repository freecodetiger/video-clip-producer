#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
from pathlib import Path


PLATFORM_PATTERNS = [
    ("youtube", re.compile(r"(youtube\.com|youtu\.be)", re.I)),
    ("bilibili", re.compile(r"(bilibili\.com|b23\.tv)", re.I)),
]


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True)


def detect_platform(url: str) -> str:
    for name, pattern in PLATFORM_PATTERNS:
        if pattern.search(url):
            return name
    return "local"


def load_metadata(url: str, cookies_file: str | None, cookies_from_browser: str | None) -> dict:
    cmd = [
        sys.executable,
        "-m",
        "yt_dlp",
        "--no-playlist",
        "--skip-download",
        "--dump-single-json",
        url,
    ]
    if cookies_file:
        cmd[6:6] = ["--cookies", cookies_file]
    if cookies_from_browser:
        cmd[6:6] = ["--cookies-from-browser", cookies_from_browser]
    proc = run(cmd)
    if proc.returncode != 0:
        raise SystemExit((proc.stderr or proc.stdout or "yt-dlp metadata fetch failed").strip())
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Failed to parse yt-dlp metadata JSON: {exc}") from exc


def build_download_cmd(
    url: str,
    outdir: Path,
    cookies_file: str | None,
    cookies_from_browser: str | None,
    sub_langs: str,
) -> list[str]:
    cmd = [
        sys.executable,
        "-m",
        "yt_dlp",
        "--no-playlist",
        "--format",
        "bv*+ba/b",
        "--merge-output-format",
        "mp4",
        "--write-subs",
        "--write-auto-subs",
        "--sub-langs",
        sub_langs,
        "--convert-subs",
        "srt",
        "-P",
        str(outdir),
        "-o",
        "%(id)s.%(ext)s",
        url,
    ]
    if cookies_file:
        cmd[6:6] = ["--cookies", cookies_file]
    if cookies_from_browser:
        cmd[6:6] = ["--cookies-from-browser", cookies_from_browser]
    return cmd


def fnmatch_any(name: str, patterns: list[str]) -> bool:
    lowered = name.lower()
    return any(fnmatch.fnmatchcase(lowered, pattern.lower()) for pattern in patterns)


def find_downloaded_files(outdir: Path, video_id: str) -> tuple[Path | None, list[Path]]:
    video_file: Path | None = None
    subtitle_files: list[Path] = []
    for path in sorted(outdir.glob(f"{video_id}.*")):
        suffix = path.suffix.lower()
        if suffix in {".srt", ".ass", ".vtt", ".ssa"}:
            subtitle_files.append(path)
        elif suffix in {".mp4", ".mkv", ".webm", ".mov"}:
            video_file = path
    return video_file, subtitle_files


def choose_subtitle_file(subtitle_files: list[Path], preferred_langs: list[str]) -> Path | None:
    if not subtitle_files:
        return None

    def lang_token(path: Path) -> str:
        parts = path.name.split(".")
        if len(parts) <= 2:
            return ""
        mid = parts[1:-1]
        for token in mid:
            if token.lower() not in {"auto", "orig", "default"}:
                return token
        return mid[0] if mid else ""

    ranked: list[tuple[int, int, Path]] = []
    for path in subtitle_files:
        lang = lang_token(path)
        lang_rank = len(preferred_langs)
        for idx, pattern in enumerate(preferred_langs):
            if fnmatch_any(lang, [pattern]):
                lang_rank = idx
                break
        auto_rank = 1 if ".auto." in path.name.lower() else 0
        ranked.append((lang_rank, auto_rank, path))
    ranked.sort(key=lambda item: (item[0], item[1], item[2].name))
    return ranked[0][2]


def main() -> int:
    parser = argparse.ArgumentParser(description="Download a URL video and its subtitles.")
    parser.add_argument("url", help="YouTube or Bilibili URL.")
    parser.add_argument("--output-dir", required=True, help="Root directory for downloaded assets.")
    parser.add_argument("--cookies-file", help="Exported cookies.txt file.")
    parser.add_argument("--cookies-from-browser", help="Browser source name for yt-dlp.")
    parser.add_argument(
        "--sub-langs",
        default="zh.*,en.*",
        help="Subtitle language patterns passed to yt-dlp.",
    )
    parser.add_argument(
        "--preferred-sub-langs",
        default="zh-Hans,zh-CN,zh,zh-TW,en,en-US",
        help="Comma-separated subtitle preference order for the selected transcript file.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable manifest.")
    args = parser.parse_args()

    root = Path(args.output_dir).expanduser()
    source_path = Path(args.url).expanduser()
    preferred_langs = [item.strip() for item in args.preferred_sub_langs.split(",") if item.strip()]

    if source_path.exists():
        platform = "local"
        video_id = source_path.stem
        meta = {"id": video_id, "title": source_path.stem}
        outdir = root / platform / video_id
        outdir.mkdir(parents=True, exist_ok=True)

        video_file = source_path
        prefix = f"{source_path.stem}."
        subtitle_files = [
            path
            for path in sorted(source_path.parent.iterdir())
            if path.is_file()
            and path.name.startswith(prefix)
            and path.suffix.lower() in {".srt", ".ass", ".vtt", ".ssa"}
        ]
        selected_subtitle = choose_subtitle_file(subtitle_files, preferred_langs)
        manifest = {
            "url": args.url,
            "platform": platform,
            "id": video_id,
            "title": source_path.stem,
            "duration": None,
            "uploader": None,
            "upload_date": None,
            "output_dir": str(outdir),
            "video_file": str(video_file),
            "subtitle_files": [str(p) for p in subtitle_files],
            "selected_subtitle": str(selected_subtitle) if selected_subtitle else None,
            "subtitle_languages": [],
            "cookies_mode": "none",
            "ready_for_transcript": bool(selected_subtitle),
        }
    else:
        platform = detect_platform(args.url)
        meta = load_metadata(args.url, args.cookies_file, args.cookies_from_browser)
        video_id = str(meta.get("id") or "").strip()
        if not video_id:
            raise SystemExit("Could not resolve video id from source metadata.")

        outdir = root / platform / video_id
        outdir.mkdir(parents=True, exist_ok=True)

        download_cmd = build_download_cmd(
            args.url,
            outdir,
            args.cookies_file,
            args.cookies_from_browser,
            args.sub_langs,
        )
        proc = run(download_cmd)
        if proc.returncode != 0:
            raise SystemExit((proc.stderr or proc.stdout or "yt-dlp download failed").strip())

        video_file, subtitle_files = find_downloaded_files(outdir, video_id)
        selected_subtitle = choose_subtitle_file(subtitle_files, preferred_langs)
        manifest = {
            "url": args.url,
            "platform": platform,
            "id": video_id,
            "title": meta.get("title"),
            "duration": meta.get("duration"),
            "uploader": meta.get("uploader"),
            "upload_date": meta.get("upload_date"),
            "output_dir": str(outdir),
            "video_file": str(video_file) if video_file else None,
            "subtitle_files": [str(p) for p in subtitle_files],
            "selected_subtitle": str(selected_subtitle) if selected_subtitle else None,
            "subtitle_languages": sorted(
                set(
                    list((meta.get("subtitles") or {}).keys())
                    + list((meta.get("automatic_captions") or {}).keys())
                )
            ),
            "cookies_mode": (
                f"browser:{args.cookies_from_browser}"
                if args.cookies_from_browser
                else ("file" if args.cookies_file else "none")
            ),
            "ready_for_transcript": bool(selected_subtitle),
        }

    manifest_path = outdir / "manifest.json"
    manifest["manifest_path"] = str(manifest_path)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
    else:
        print(f"platform: {platform}")
        print(f"title: {manifest['title']}")
        print(f"video: {manifest['video_file']}")
        print(f"subtitle: {manifest['selected_subtitle']}")
        print(f"manifest: {manifest['manifest_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
