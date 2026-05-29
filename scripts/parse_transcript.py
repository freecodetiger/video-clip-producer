#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path


TIME_RE = re.compile(r"(\d+):(\d+):(\d+)[,.:](\d+)")
ASS_EVENT_RE = re.compile(r"^Dialogue:\s*\d+,([^,]+),([^,]+),[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,(.*)$")
HTML_TAG_RE = re.compile(r"<[^>]+>")
ASS_TAG_RE = re.compile(r"\{\\[^}]+\}")


@dataclass
class Segment:
    start: float
    end: float
    text: str
    speaker: str | None = None


def ts_to_seconds(ts: str) -> float:
    m = TIME_RE.search(ts.strip())
    if not m:
        raise ValueError(f"bad timestamp: {ts}")
    h, mnt, sec, ms = map(int, m.groups())
    scale = 10 ** len(m.group(4))
    return h * 3600 + mnt * 60 + sec + ms / scale


def clean_text(text: str) -> str:
    text = text.replace(r"\N", " ").replace(r"\n", " ")
    text = ASS_TAG_RE.sub("", text)
    text = HTML_TAG_RE.sub("", text)
    text = text.replace("\u200b", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_srt(text: str) -> list[Segment]:
    chunks = re.split(r"\n\s*\n", text.strip(), flags=re.M)
    items: list[Segment] = []
    for chunk in chunks:
        lines = [line.rstrip() for line in chunk.splitlines() if line.strip()]
        if len(lines) < 2:
            continue
        timing = lines[1] if "-->" in lines[1] else lines[0]
        body = lines[2:] if "-->" in lines[1] else lines[1:]
        if "-->" not in timing:
            continue
        start_raw, end_raw = [x.strip() for x in timing.split("-->")]
        body_text = clean_text(" ".join(body))
        if body_text:
            items.append(Segment(ts_to_seconds(start_raw), ts_to_seconds(end_raw), body_text))
    return items


def parse_ass(text: str) -> list[Segment]:
    items: list[Segment] = []
    for line in text.splitlines():
        m = ASS_EVENT_RE.match(line)
        if not m:
            continue
        start, end, rest = m.groups()
        text_part = clean_text(rest)
        if text_part:
            items.append(Segment(ts_to_seconds(start), ts_to_seconds(end), text_part))
    return items


def parse_vtt(text: str) -> list[Segment]:
    chunks = re.split(r"\n\s*\n", text.strip(), flags=re.M)
    items: list[Segment] = []
    for chunk in chunks:
        lines = [line.rstrip() for line in chunk.splitlines() if line.strip()]
        if not lines:
            continue
        if lines[0].startswith("WEBVTT") or lines[0].startswith("NOTE") or lines[0].startswith("STYLE"):
            continue
        timing_idx = None
        for idx, line in enumerate(lines):
            if "-->" in line:
                timing_idx = idx
                break
        if timing_idx is None:
            continue
        timing = lines[timing_idx]
        body = lines[timing_idx + 1 :]
        if "-->" not in timing:
            continue
        start_raw, end_raw = [x.strip().split(" ", 1)[0] for x in timing.split("-->")]
        body_text = clean_text(" ".join(body))
        if body_text:
            items.append(Segment(ts_to_seconds(start_raw), ts_to_seconds(end_raw), body_text))
    return items


def parse_jsonish(path: Path, text: str) -> list[Segment]:
    if path.suffix.lower() == ".jsonl":
        rows = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    else:
        rows = json.loads(text)
        if isinstance(rows, dict):
            rows = rows.get("segments") or rows.get("items") or rows.get("data") or []

    items: list[Segment] = []
    for row in rows:
        start = row.get("start") or row.get("start_time") or row.get("from")
        end = row.get("end") or row.get("end_time") or row.get("to")
        text = row.get("text") or row.get("content") or row.get("utterance") or ""
        speaker = row.get("speaker") or row.get("name")
        if start is None or end is None:
            continue
        text = clean_text(str(text))
        if text:
            items.append(Segment(float(start), float(end), text, speaker))
    return items


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse transcript/subtitle files into normalized segments.")
    parser.add_argument("--input", required=True, help="Transcript file path.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    args = parser.parse_args()

    path = Path(args.input).expanduser()
    text = path.read_text(encoding="utf-8", errors="ignore")
    suffix = path.suffix.lower()

    if suffix == ".srt":
        segments = parse_srt(text)
    elif suffix == ".ass":
        segments = parse_ass(text)
    elif suffix in {".vtt", ".webvtt"}:
        segments = parse_vtt(text)
    elif suffix in {".json", ".jsonl"}:
        segments = parse_jsonish(path, text)
    else:
        raise SystemExit(f"Unsupported transcript format: {suffix}")

    payload = [asdict(s) for s in segments]
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for seg in payload:
            print(f"{seg['start']:.2f}\t{seg['end']:.2f}\t{seg['text']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
