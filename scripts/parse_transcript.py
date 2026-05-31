#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
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


def split_bilingual_text(text: str) -> tuple[str, str]:
    zh_parts: list[str] = []
    en_parts: list[str] = []
    for part in re.split(r"\s*(?:\n|/|\|)\s*", text):
        cleaned = clean_text(part)
        if not cleaned:
            continue
        if re.search(r"[\u4e00-\u9fff]", cleaned):
            zh_parts.append(cleaned)
        else:
            en_parts.append(cleaned)
    if not zh_parts and not en_parts:
        en_parts.append(clean_text(text))
    return " ".join(en_parts).strip(), " ".join(zh_parts).strip()


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


def should_merge(previous: Segment, current: Segment, max_gap: float) -> bool:
    if current.start - previous.end > max_gap:
        return False
    prev_text = previous.text.strip()
    if not prev_text:
        return True
    if prev_text.endswith((".", "?", "!", "。", "？", "！")):
        return False
    return True


def merge_fragmented_segments(segments: list[Segment], max_gap: float = 0.35) -> list[Segment]:
    if not segments:
        return []
    ordered = sorted(segments, key=lambda item: (item.start, item.end))
    merged: list[Segment] = []
    current = Segment(ordered[0].start, ordered[0].end, ordered[0].text, ordered[0].speaker)
    for item in ordered[1:]:
        if should_merge(current, item, max_gap):
            current.end = max(current.end, item.end)
            current.text = clean_text(f"{current.text} {item.text}")
            if not current.speaker:
                current.speaker = item.speaker
        else:
            merged.append(current)
            current = Segment(item.start, item.end, item.text, item.speaker)
    merged.append(current)
    return merged


def normalize_cues(
    segments: list[Segment],
    source_file: Path,
    lead_sec: float = 0.8,
    merge_gap: float = 0.35,
) -> dict:
    cues = []
    for idx, segment in enumerate(merge_fragmented_segments(segments, merge_gap), 1):
        en, zh = split_bilingual_text(segment.text)
        source_start = round(float(segment.start), 3)
        source_end = round(float(segment.end), 3)
        cues.append(
            {
                "cue_id": f"cue_{idx:04d}",
                "source_start": source_start,
                "source_end": source_end,
                "display_start": round(max(0.0, source_start - lead_sec), 3),
                "display_end": source_end,
                "en": en,
                "zh": zh,
                "speaker_optional": segment.speaker,
                "source_file": str(source_file),
            }
        )
    return {
        "schema": "normalized_cues.v1",
        "source_file": str(source_file),
        "lead_sec": lead_sec,
        "cue_count": len(cues),
        "cues": cues,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse transcript/subtitle files into normalized segments.")
    parser.add_argument("--input", required=True, help="Transcript file path.")
    parser.add_argument("--out", help="Write normalized_cues.json to this path.")
    parser.add_argument("--lead-sec", type=float, default=0.8, help="Seconds to advance cue display_start.")
    parser.add_argument("--merge-gap", type=float, default=0.35, help="Maximum gap for merging platform subtitle fragments.")
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

    payload = normalize_cues(segments, path, args.lead_sec, args.merge_gap)
    if args.out:
        out = Path(args.out).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif args.out:
        print(str(Path(args.out).expanduser()))
    else:
        for cue in payload["cues"]:
            text = cue["zh"] or cue["en"]
            print(f"{cue['source_start']:.2f}\t{cue['source_end']:.2f}\t{text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
