from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_script(name: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / name), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )


class PipelineContractTests(unittest.TestCase):
    def test_parse_transcript_writes_normalized_cues_with_source_timestamps_and_lead_only_on_start(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_dir = Path(temp)
            subtitle = temp_dir / "source.srt"
            subtitle.write_text(
                "\n".join(
                    [
                        "1",
                        "00:00:10,000 --> 00:00:10,500",
                        "We need",
                        "",
                        "2",
                        "00:00:10,520 --> 00:00:11,200",
                        "better systems.",
                        "",
                        "3",
                        "00:00:13,000 --> 00:00:14,000",
                        "This is the answer.",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            out = temp_dir / "normalized_cues.json"

            proc = run_script("parse_transcript.py", "--input", str(subtitle), "--out", str(out), "--lead-sec", "0.8")

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema"], "normalized_cues.v1")
            self.assertEqual(len(payload["cues"]), 2)
            first = payload["cues"][0]
            self.assertEqual(first["cue_id"], "cue_0001")
            self.assertEqual(first["source_start"], 10.0)
            self.assertEqual(first["source_end"], 11.2)
            self.assertEqual(first["display_start"], 9.2)
            self.assertEqual(first["display_end"], 11.2)
            self.assertEqual(first["en"], "We need better systems.")
            self.assertEqual(first["zh"], "")
            self.assertEqual(first["source_file"], str(subtitle))

    def test_check_env_accepts_standard_task_profiles(self) -> None:
        for task in ("ingest", "subtitle", "render", "final"):
            proc = run_script("check_env.py", "--task", task, "--json", "--skip-deep-ffmpeg-check")
            self.assertNotIn("invalid choice", proc.stderr)
            self.assertIn(proc.returncode, {0, 2})
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["task"], task)

    def test_render_spec_template_exposes_productized_required_fields(self) -> None:
        proc = run_script("render_clip.py", "--print-spec-template")

        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        spec = json.loads(proc.stdout)
        for key in (
            "source_video",
            "segment_start",
            "segment_end",
            "subtitle_source",
            "subtitle_lead_sec",
            "subtitle_mode",
            "layout_profile",
            "broll_plan",
            "output_profile",
        ):
            self.assertIn(key, spec)
        self.assertEqual(spec["subtitle_lead_sec"], 0.8)
        self.assertEqual(spec["subtitle_mode"], "rolling_bilingual")

    def test_render_dry_run_from_normalized_cues_writes_subtitle_artifacts_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_dir = Path(temp)
            source = temp_dir / "source.mp4"
            source.write_bytes(b"not a real video; dry run only")
            cues = temp_dir / "normalized_cues.json"
            cues.write_text(
                json.dumps(
                    {
                        "schema": "normalized_cues.v1",
                        "source_file": "source.srt",
                        "lead_sec": 0.8,
                        "cues": [
                            {
                                "cue_id": "cue_0001",
                                "source_start": 1.0,
                                "source_end": 3.0,
                                "display_start": 0.2,
                                "display_end": 3.0,
                                "en": "Build the system.",
                                "zh": "构建系统。",
                                "speaker_optional": None,
                                "source_file": "source.srt",
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            out_dir = temp_dir / "clip"
            spec = temp_dir / "render_spec.json"
            spec.write_text(
                json.dumps(
                    {
                        "source_video": str(source),
                        "segment_start": 1.0,
                        "segment_end": 5.0,
                        "subtitle_source": str(cues),
                        "subtitle_lead_sec": 0.8,
                        "subtitle_mode": "rolling_bilingual",
                        "layout_profile": {"width": 1280, "height": 720, "lanes": 2},
                        "broll_plan": [],
                        "output_profile": {"output_dir": str(out_dir), "final_name": "final.mp4"},
                        "subtitle_burn_source_is_clean": True,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            proc = run_script("render_clip.py", "--spec", str(spec), "--dry-run")

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            self.assertTrue((out_dir / "subtitles_final.ass").exists())
            self.assertTrue((out_dir / "subtitles_preview.ass").exists())
            self.assertTrue((out_dir / "subtitle_timing_report.json").exists())
            manifest = json.loads((out_dir / "render_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["cue_count"], 1)
            self.assertEqual(manifest["lead_sec"], 0.8)
            self.assertEqual(manifest["subtitle_ass"], str(out_dir / "subtitles_final.ass"))
            self.assertEqual(manifest["subtitle_burn_source_is_clean"], True)

    def test_verify_render_strict_checks_spec_manifest_and_subtitle_overlap(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_dir = Path(temp)
            spec = temp_dir / "render_spec.json"
            video = temp_dir / "final.mp4"
            ass = temp_dir / "subtitles_final.ass"
            manifest = temp_dir / "render_manifest.json"
            video.write_bytes(b"placeholder")
            spec.write_text(
                json.dumps(
                    {
                        "segment_start": 0,
                        "segment_end": 5,
                        "subtitle_source": str(temp_dir / "normalized_cues.json"),
                        "output_profile": {"output_dir": str(temp_dir), "final_name": "final.mp4"},
                    }
                ),
                encoding="utf-8",
            )
            ass.write_text(
                "\n".join(
                    [
                        "[Events]",
                        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
                        "Dialogue: 0,0:00:00.00,0:00:02.00,CN,,0,0,0,,first",
                        "Dialogue: 0,0:00:01.50,0:00:03.00,CN,,0,0,0,,overlap",
                    ]
                ),
                encoding="utf-8",
            )
            manifest.write_text(
                json.dumps(
                    {
                        "final_video": str(video),
                        "subtitle_ass": str(ass),
                        "cue_count": 2,
                        "lead_sec": 0.8,
                        "subtitle_burn_source_is_clean": True,
                        "source_time_basis": "source.srt",
                    }
                ),
                encoding="utf-8",
            )

            proc = run_script(
                "verify_render.py",
                "--spec",
                str(spec),
                "--video",
                str(video),
                "--strict",
                "--json",
            )

            self.assertEqual(proc.returncode, 2)
            report = json.loads(proc.stdout)
            self.assertIn("ass-same-layer-overlap", report["issues"])
            self.assertEqual(report["manifest"]["lead_sec"], 0.8)


if __name__ == "__main__":
    unittest.main()
