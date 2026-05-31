#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import re
from dataclasses import dataclass, asdict
from pathlib import Path


EMOTION = {
    "我", "我们", "自己", "人生", "失败", "痛苦", "激动", "震惊", "遗憾", "骄傲", "泪", "坚持", "勇敢", "改变",
    "i ", "we ", "you ", "my ", "our ", "life", "failure", "failed", "hard", "humbling", "humiliated",
    "dream", "hope", "afraid", "courage", "change", "opportunity", "resilience", "heart",
}
CONFLICT = {
    "不是", "错", "问题", "反对", "争议", "危险", "取代", "必须", "不能", "应该", "代价", "冲突", "失败",
    "not ", "never", "wrong", "problem", "danger", "replace", "replaced", "but ", "however", "hard",
    "must", "should", "can't", "cannot", "fail", "failed", "cost", "risk", "challenge",
}
QUOTE = {
    "一句话", "记住", "金句", "总结", "本质", "答案", "真正", "关键", "核心",
    "remember", "the truth", "the key", "the point", "the answer", "what matters", "really",
    "not about", "is not", "isn't", "this is", "that is", "so run", "don't walk",
}
HOOK = {
    "你", "我们", "如果", "其实", "今天", "先", "先说", "重点", "听我说",
    "you ", "we ", "if ", "today", "first", "let me", "imagine", "what if", "yes,", "but ",
}
VISUAL = {
    "海", "浪", "风暴", "雷", "雨", "雪", "山", "云", "火", "光", "路", "厂", "城", "人群", "舞台",
    "storm", "mountain", "ocean", "wave", "rain", "thunder", "lightning", "factory", "city",
    "build", "infrastructure", "computer", "chip", "ai", "future", "world",
}


@dataclass
class Candidate:
    start: float
    end: float
    duration: float
    text: str
    score: float
    content_value: float
    emotion: float
    controversy: float
    quote_density: float
    hook: float
    visual: float
    titleability: float
    reason: str


def clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def read_segments(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("cues") or data.get("segments") or data.get("items") or data.get("data") or []
    rows = []
    for item in data:
        if "source_start" in item or "source_end" in item:
            text = " ".join(
                str(item.get(key) or "").strip()
                for key in ("zh", "en")
                if str(item.get(key) or "").strip()
            )
            rows.append(
                {
                    "start": item.get("source_start", item.get("display_start")),
                    "end": item.get("source_end", item.get("display_end")),
                    "text": text,
                }
            )
        else:
            rows.append(item)
    return rows


def score_text(text: str, mode: str) -> dict:
    t = text.strip()
    tl = f" {t.lower()} "
    chars = len(t)
    short = 1.0 if chars <= 28 else max(0.0, 1.0 - (chars - 28) / 60.0)
    exclaim = t.count("！") + t.count("!") + t.count("？") + t.count("?")

    def kw(words: set[str]) -> int:
        return sum(1 for w in words if w in t or w in tl)

    emotion = kw(EMOTION) * 8 + exclaim * 6 + short * 10
    controversy = kw(CONFLICT) * 7 + (t.count("不") > 1) * 5 + (t.count("为什么") > 0) * 6
    quote_density = kw(QUOTE) * 9 + short * 8 + (1 if chars <= 24 else 0) * 8
    hook = kw(HOOK) * 6 + (1 if t[:1] in {"你", "我", "“】【"} else 0) * 8 + (1 if chars <= 18 else 0) * 5
    visual = kw(VISUAL) * 5 + (1 if any(p in t for p in "。！？") else 0) * 3
    content = min(20, (emotion + controversy + quote_density) / 5)
    titleability = min(10, quote_density / 3 + hook / 10)

    base = {
        "content_value": clamp(content, 0, 20),
        "emotion": clamp(emotion, 0, 25),
        "controversy": clamp(controversy, 0, 20),
        "quote_density": clamp(quote_density, 0, 15),
        "hook": clamp(hook, 0, 15),
        "visual": clamp(visual, 0, 15),
        "titleability": clamp(titleability, 0, 10),
    }

    weights = {
        "traffic": {"emotion": 1.0, "controversy": 1.15, "quote_density": 1.05, "hook": 1.2, "visual": 1.0, "titleability": 1.15, "content_value": 0.9},
        "controversy": {"emotion": 0.9, "controversy": 1.4, "quote_density": 1.0, "hook": 1.1, "visual": 0.85, "titleability": 1.0, "content_value": 0.8},
        "emotion": {"emotion": 1.4, "controversy": 0.9, "quote_density": 1.1, "hook": 0.9, "visual": 1.0, "titleability": 0.9, "content_value": 1.1},
        "inspiration": {"emotion": 1.25, "controversy": 0.85, "quote_density": 1.15, "hook": 1.0, "visual": 1.15, "titleability": 0.95, "content_value": 1.2},
        "balanced": {"emotion": 1.0, "controversy": 1.0, "quote_density": 1.0, "hook": 1.0, "visual": 1.0, "titleability": 1.0, "content_value": 1.0},
    }.get(mode, {})

    score = (
        base["content_value"] * 1.0 * weights.get("content_value", 1.0)
        + base["emotion"] * 1.0 * weights.get("emotion", 1.0)
        + base["controversy"] * 1.0 * weights.get("controversy", 1.0)
        + base["quote_density"] * 1.0 * weights.get("quote_density", 1.0)
        + base["hook"] * 1.0 * weights.get("hook", 1.0)
        + base["visual"] * 1.0 * weights.get("visual", 1.0)
        + base["titleability"] * 1.0 * weights.get("titleability", 1.0)
    )

    return {"score": round(clamp(score, 0, 100), 1), **base}


def reason_for(text: str, score: dict) -> str:
    reasons = []
    if score["emotion"] >= 15:
        reasons.append("情绪张力高")
    if score["controversy"] >= 12:
        reasons.append("争议/讨论空间大")
    if score["quote_density"] >= 10:
        reasons.append("有可直接做标题的金句")
    if score["hook"] >= 10:
        reasons.append("开头 hook 强")
    if score["visual"] >= 8:
        reasons.append("适合 B-roll 包装")
    if not reasons:
        reasons.append("语义完整，适合做中段观点推进")
    return "，".join(reasons)


def merge_segments(rows: list[dict], min_gap: float = 2.5) -> list[tuple[float, float, str]]:
    if not rows:
        return []
    rows = sorted(rows, key=lambda r: float(r["start"]))
    merged = []
    cur_s = float(rows[0]["start"])
    cur_e = float(rows[0]["end"])
    texts = [rows[0].get("text", "").strip()]
    for row in rows[1:]:
        s = float(row["start"])
        e = float(row["end"])
        txt = row.get("text", "").strip()
        if s - cur_e <= min_gap:
            cur_e = max(cur_e, e)
            texts.append(txt)
        else:
            merged.append((cur_s, cur_e, " ".join(t for t in texts if t)))
            cur_s, cur_e, texts = s, e, [txt]
    merged.append((cur_s, cur_e, " ".join(t for t in texts if t)))
    return merged


def main() -> int:
    parser = argparse.ArgumentParser(description="Rank long-video clip candidates.")
    parser.add_argument("--input", required=True, help="Parsed transcript JSON file.")
    parser.add_argument("--mode", default="traffic", choices=["traffic", "controversy", "emotion", "inspiration", "balanced"])
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--min-duration", type=float, default=12.0)
    parser.add_argument("--max-duration", type=float, default=180.0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    segments = read_segments(Path(args.input).expanduser())
    if not segments:
        raise SystemExit("No transcript segments found.")

    scored_rows = []
    for seg in segments:
        txt = str(seg.get("text", "")).strip()
        if not txt:
            continue
        score = score_text(txt, args.mode)
        if score["score"] < 20:
            continue
        row = {**seg, **score}
        row["reason"] = reason_for(txt, score)
        scored_rows.append(row)

    if not scored_rows:
        scored_rows = []

    # Merge adjacent high-signal segments into candidate windows.
    high_signal = [r for r in scored_rows if r["score"] >= 35]
    if not high_signal:
        high_signal = sorted(scored_rows, key=lambda r: r["score"], reverse=True)[: args.top_k * 2]
    clusters = merge_segments(high_signal)
    candidates: list[Candidate] = []
    for s, e, text in clusters:
        duration = e - s
        if duration < 3:
            continue
        merged_score = score_text(text, args.mode)
        if duration > args.max_duration:
            merged_score["score"] *= 0.85
        if duration < args.min_duration:
            merged_score["score"] *= 0.9
        candidates.append(
            Candidate(
                start=round(s, 2),
                end=round(e, 2),
                duration=round(e - s, 2),
                text=text[:300],
                score=round(clamp(merged_score["score"]), 1),
                content_value=round(merged_score["content_value"], 1),
                emotion=round(merged_score["emotion"], 1),
                controversy=round(merged_score["controversy"], 1),
                quote_density=round(merged_score["quote_density"], 1),
                hook=round(merged_score["hook"], 1),
                visual=round(merged_score["visual"], 1),
                titleability=round(merged_score["titleability"], 1),
                reason=reason_for(text, merged_score),
            )
        )

    candidates.sort(key=lambda c: (c.score, c.emotion, c.hook, c.titleability), reverse=True)
    candidates = candidates[: max(args.top_k, 3)]

    if args.json:
        print(json.dumps([asdict(c) for c in candidates], ensure_ascii=False, indent=2))
    else:
        print("| 排名 | 起止时间 | 时长 | 分数 | 片段 | 理由 |")
        print("| --- | --- | --- | ---: | --- | --- |")
        for idx, c in enumerate(candidates, 1):
            print(f"| {idx} | {c.start:.2f}-{c.end:.2f} | {c.duration:.2f} | {c.score:.1f} | {c.text[:40]} | {c.reason} |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
