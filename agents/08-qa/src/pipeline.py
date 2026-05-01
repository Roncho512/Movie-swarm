"""
pipeline.py — The QA agent's review pipeline.

Extracts frames from the rough cut, sends them to Claude for visual
analysis against the style bible and character references, and produces
a structured QA report.

Usage:
    from src.pipeline import QAPipeline
    qa = QAPipeline(production_dir="productions/the-last-marker")
    qa.extract_frames("edit/rough-cut-v1.mp4")
    qa.review()
    qa.write_report()
"""

from __future__ import annotations

import base64
import json
import logging
import os
import subprocess
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("qa.pipeline")


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class Finding:
    """A single QA finding."""
    finding_id: str
    severity: str              # "critical", "major", "minor", "note"
    category: str              # "visual_continuity", "temporal_continuity", etc.
    shots_affected: list[str]
    timestamp: str
    description: str
    evidence_frames: list[str] = field(default_factory=list)
    recommendation: str = ""
    assigned_to: str = ""      # Which agent should fix this


@dataclass
class ShotGrade:
    """Grade for a single shot."""
    shot_id: str
    grade: str                 # A, B+, B, C, etc.
    notes: str = ""


@dataclass
class QAReport:
    """Complete QA report."""
    production_id: str
    cut_reviewed: str
    review_date: str
    overall_verdict: str       # "approved", "revise", "reject"
    overall_notes: str
    findings: list[Finding]
    shot_grades: list[ShotGrade]
    statistics: dict[str, int] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Frame extraction
# ---------------------------------------------------------------------------


def extract_frames(
    video_path: str | Path,
    output_dir: str | Path,
    timestamps: Optional[list[float]] = None,
    shots: Optional[list[dict]] = None,
) -> list[dict]:
    """
    Extract frames from a video at specified timestamps or per-shot.

    If shots is provided (list of {shot_id, start_time, duration}),
    extracts start/mid/end frames for each shot.

    Returns list of {shot_id, position, timestamp, frame_path}.
    """
    video_path = Path(video_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    frames = []

    if shots:
        for shot in shots:
            sid = shot["shot_id"]
            start = shot["start_time"]
            dur = shot["duration"]

            for position, ts in [
                ("start", start + 0.1),
                ("mid", start + dur / 2),
                ("end", start + dur - 0.1),
            ]:
                frame_name = f"{sid}-{position}.png"
                frame_path = output_dir / frame_name

                _extract_single_frame(video_path, ts, frame_path)

                frames.append({
                    "shot_id": sid,
                    "position": position,
                    "timestamp": ts,
                    "frame_path": str(frame_path),
                })
    elif timestamps:
        for i, ts in enumerate(timestamps):
            frame_name = f"frame-{i:03d}-{ts:.1f}s.png"
            frame_path = output_dir / frame_name
            _extract_single_frame(video_path, ts, frame_path)
            frames.append({
                "shot_id": f"frame-{i:03d}",
                "position": "manual",
                "timestamp": ts,
                "frame_path": str(frame_path),
            })

    logger.info("Extracted %d frames → %s", len(frames), output_dir)
    return frames


def _extract_single_frame(video_path: Path, timestamp: float, output_path: Path):
    """Extract a single frame at the given timestamp."""
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(timestamp),
        "-i", str(video_path),
        "-frames:v", "1",
        "-q:v", "2",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    if result.returncode != 0:
        logger.warning("Frame extraction failed at %.1fs: %s", timestamp, result.stderr[-200:])


def _encode_frame_b64(frame_path: str | Path) -> str:
    """Read a frame and return base64-encoded PNG data."""
    return base64.standard_b64encode(Path(frame_path).read_bytes()).decode()


# ---------------------------------------------------------------------------
# Claude vision analysis
# ---------------------------------------------------------------------------


def _get_anthropic_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise EnvironmentError("ANTHROPIC_API_KEY environment variable is not set.")
    return key


def analyze_frames_with_claude(
    frames: list[dict],
    shot_list_context: str,
    style_context: str = "",
    model: str = "claude-sonnet-4-20250514",
) -> dict[str, Any]:
    """
    Send extracted frames to Claude for visual QA analysis.

    Sends frames in batches (per shot) and asks Claude to evaluate
    continuity, style adherence, and technical quality.

    Returns the parsed analysis as a dict.
    """
    import requests

    api_key = _get_anthropic_key()

    # Group frames by shot
    shots_grouped: dict[str, list[dict]] = {}
    for f in frames:
        sid = f["shot_id"]
        if sid not in shots_grouped:
            shots_grouped[sid] = []
        shots_grouped[sid].append(f)

    # Build message content with all frames
    content = []

    # Add context
    content.append({
        "type": "text",
        "text": f"""You are a film continuity supervisor reviewing an AI-generated short film called "The Last Marker" — a 1967 Baja desert motorcycle story shot in a vintage 16mm Ektachrome style.

SHOT LIST CONTEXT:
{shot_list_context}

{f"STYLE GUIDE: {style_context}" if style_context else ""}

I'm going to show you extracted frames from the rough cut. For each shot, you'll see the start, middle, and end frames. Review them for:

1. VISUAL CONTINUITY: Character appearance, vehicle consistency, environment consistency between shots
2. TEMPORAL CONTINUITY: Time of day, lighting direction, shadow consistency
3. SPATIAL CONTINUITY: Screen direction, 180-degree rule, background consistency
4. STYLE ADHERENCE: Does it look like 1960s 16mm Ektachrome? Film grain, color palette, period accuracy
5. TECHNICAL QUALITY: Artifacts, glitches, resolution issues, AI generation problems

For each issue found, provide:
- severity: "critical", "major", "minor", or "note"
- category: which of the 5 categories above
- description: what's wrong
- recommendation: how to fix it
- assigned_to: which agent should fix it (art_director, production, editor, sound_designer)

Also grade each shot A through F.

Respond in JSON format with this structure:
{{
  "overall_verdict": "approved" or "revise" or "reject",
  "overall_notes": "summary of the cut",
  "findings": [
    {{
      "severity": "major",
      "category": "visual_continuity",
      "shots_affected": ["s01-sh02", "s01-sh03"],
      "timestamp": "25.0s",
      "description": "...",
      "recommendation": "...",
      "assigned_to": "production"
    }}
  ],
  "shot_grades": {{
    "s01-sh01": {{"grade": "A", "notes": "..."}},
    ...
  }}
}}""",
    })

    # Add frames per shot
    for sid, shot_frames in sorted(shots_grouped.items()):
        content.append({
            "type": "text",
            "text": f"\n--- {sid} ---",
        })
        for f in shot_frames:
            frame_path = Path(f["frame_path"])
            if frame_path.exists():
                b64 = _encode_frame_b64(frame_path)
                content.append({
                    "type": "text",
                    "text": f"{f['position']} frame ({f['timestamp']:.1f}s):",
                })
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": b64,
                    },
                })

    # Call Claude API
    logger.info("Sending %d frames to Claude for analysis...", len(frames))

    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "content-type": "application/json",
            "anthropic-version": "2023-06-01",
        },
        json={
            "model": model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": content}],
        },
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()

    # Extract text response
    response_text = ""
    for block in data.get("content", []):
        if block.get("type") == "text":
            response_text += block["text"]

    # Save raw response for debugging
    logger.info("Raw Claude response length: %d chars", len(response_text))
    raw_path = Path(output_dir) / "claude-raw-response.txt" if output_dir else None

    # Parse JSON from response
    try:
        clean = response_text.strip()
        # Strip markdown fences
        if "```json" in clean:
            clean = clean.split("```json", 1)[1]
        if "```" in clean:
            clean = clean.split("```")[0]
        clean = clean.strip()
        return json.loads(clean)
    except (json.JSONDecodeError, IndexError, ValueError) as e:
        logger.warning("Could not parse Claude response as JSON: %s", e)
        logger.info("First 500 chars of response: %s", response_text[:500])
        return {
            "overall_verdict": "error",
            "overall_notes": "Failed to parse QA analysis",
            "raw_response": response_text,
            "findings": [],
            "shot_grades": {},
        }


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


class QAPipeline:
    """
    Orchestrates QA review of an assembled cut.

    Usage:
        qa = QAPipeline("productions/the-last-marker")
        report = qa.review("edit/rough-cut-v1.mp4")
    """

    def __init__(self, production_dir: str | Path):
        self.prod_dir = Path(production_dir)
        self.qa_dir = self.prod_dir / "qa-reports"
        self.frames_dir = self.qa_dir / "frames"
        self.qa_dir.mkdir(parents=True, exist_ok=True)

        self.frames: list[dict] = []
        self.analysis: dict = {}
        self.report: Optional[QAReport] = None

    def _load_shot_timeline(self) -> list[dict]:
        """Build shot timeline from the edit decision list or by probing clips."""
        edl_path = self.prod_dir / "edit" / "edit-decision-list.json"
        if edl_path.exists():
            edl = json.loads(edl_path.read_text())
            return [
                {
                    "shot_id": c["shot_id"],
                    "start_time": c["start_time"],
                    "duration": c["duration"],
                }
                for c in edl.get("clips", [])
            ]

        # Fallback: probe selected clips
        clips_dir = self.prod_dir / "clips" / "selected"
        shots = []
        timeline = 0.0
        for f in sorted(clips_dir.glob("s*-sh*.mp4")):
            result = subprocess.run(
                ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                 "-of", "csv=p=0", str(f)],
                capture_output=True, text=True, timeout=10,
            )
            dur = float(result.stdout.strip())
            shots.append({
                "shot_id": f.stem,
                "start_time": timeline,
                "duration": dur,
            })
            timeline += dur
        return shots

    def _load_shot_list_context(self) -> str:
        """Load shot list for context in the analysis prompt."""
        shot_list_path = self.prod_dir / "shot-lists" / "shot-list.json"
        if not shot_list_path.exists():
            return "Shot list not available."

        raw = json.loads(shot_list_path.read_text())
        lines = []
        for s in raw.get("shots", []):
            lines.append(
                f"  {s['shot_id']}: {s['generation_prompt'][:120]}..."
            )
        return "\n".join(lines)

    def review(
        self,
        cut_filename: str = "rough-cut-v1.mp4",
        model: str = "claude-sonnet-4-20250514",
    ) -> QAReport:
        """
        Run a full QA review on the specified cut.

        1. Extract frames
        2. Send to Claude for analysis
        3. Build structured report
        """
        cut_path = self.prod_dir / "edit" / cut_filename
        if not cut_path.exists():
            raise FileNotFoundError(f"Cut not found: {cut_path}")

        # 1. Get shot timeline
        shots = self._load_shot_timeline()
        logger.info("Reviewing %d shots in %s", len(shots), cut_filename)

        # 2. Extract frames
        self.frames = extract_frames(
            video_path=cut_path,
            output_dir=self.frames_dir,
            shots=shots,
        )

        # 3. Get shot list context
        shot_context = self._load_shot_list_context()

        # 4. Send to Claude for analysis
        self.analysis = analyze_frames_with_claude(
            frames=self.frames,
            shot_list_context=shot_context,
            model=model,
        )

        # 5. Build report
        self.report = self._build_report(cut_filename)

        # 6. Write outputs
        self._write_report()
        self._write_summary()

        return self.report

    def review_local(self, cut_filename: str = "rough-cut-v1.mp4") -> list[dict]:
        """
        Extract frames only (no Claude API call).
        Useful for manual review or when no API key is available.
        """
        cut_path = self.prod_dir / "edit" / cut_filename
        if not cut_path.exists():
            raise FileNotFoundError(f"Cut not found: {cut_path}")

        shots = self._load_shot_timeline()
        self.frames = extract_frames(
            video_path=cut_path,
            output_dir=self.frames_dir,
            shots=shots,
        )

        logger.info("Extracted %d frames for manual review in %s", len(self.frames), self.frames_dir)
        return self.frames

    def _build_report(self, cut_filename: str) -> QAReport:
        """Build a structured QAReport from the Claude analysis."""
        findings = []
        for i, f in enumerate(self.analysis.get("findings", [])):
            findings.append(Finding(
                finding_id=f"F{i+1:03d}",
                severity=f.get("severity", "note"),
                category=f.get("category", "other"),
                shots_affected=f.get("shots_affected", []),
                timestamp=f.get("timestamp", ""),
                description=f.get("description", ""),
                evidence_frames=f.get("evidence_frames", []),
                recommendation=f.get("recommendation", ""),
                assigned_to=f.get("assigned_to", ""),
            ))

        shot_grades = []
        for sid, grade_info in self.analysis.get("shot_grades", {}).items():
            if isinstance(grade_info, dict):
                shot_grades.append(ShotGrade(
                    shot_id=sid,
                    grade=grade_info.get("grade", "?"),
                    notes=grade_info.get("notes", ""),
                ))
            else:
                shot_grades.append(ShotGrade(shot_id=sid, grade=str(grade_info)))

        stats = {
            "total_findings": len(findings),
            "critical": sum(1 for f in findings if f.severity == "critical"),
            "major": sum(1 for f in findings if f.severity == "major"),
            "minor": sum(1 for f in findings if f.severity == "minor"),
            "notes": sum(1 for f in findings if f.severity == "note"),
        }

        return QAReport(
            production_id=self.prod_dir.name,
            cut_reviewed=cut_filename,
            review_date=datetime.now(timezone.utc).isoformat(),
            overall_verdict=self.analysis.get("overall_verdict", "unknown"),
            overall_notes=self.analysis.get("overall_notes", ""),
            findings=findings,
            shot_grades=shot_grades,
            statistics=stats,
        )

    def _write_report(self):
        """Write the structured QA report JSON."""
        if not self.report:
            return
        out = self.qa_dir / "qa-report-v1.json"
        out.write_text(json.dumps(asdict(self.report), indent=2))
        logger.info("Wrote QA report → %s", out)

    def _write_summary(self):
        """Write a human-readable QA summary."""
        if not self.report:
            return

        lines = [
            f"QA REVIEW — {self.report.production_id}",
            f"Cut: {self.report.cut_reviewed}",
            f"Date: {self.report.review_date}",
            f"Verdict: {self.report.overall_verdict.upper()}",
            f"",
            f"Notes: {self.report.overall_notes}",
            f"",
            f"--- Statistics ---",
            f"Total findings: {self.report.statistics.get('total_findings', 0)}",
            f"  Critical: {self.report.statistics.get('critical', 0)}",
            f"  Major: {self.report.statistics.get('major', 0)}",
            f"  Minor: {self.report.statistics.get('minor', 0)}",
            f"  Notes: {self.report.statistics.get('notes', 0)}",
            f"",
            f"--- Shot Grades ---",
        ]
        for sg in self.report.shot_grades:
            lines.append(f"  {sg.shot_id}: {sg.grade} — {sg.notes}")

        lines.append(f"\n--- Findings ---")
        for f in self.report.findings:
            lines.append(f"")
            lines.append(f"  [{f.finding_id}] {f.severity.upper()} — {f.category}")
            lines.append(f"  Shots: {', '.join(f.shots_affected)}")
            lines.append(f"  {f.description}")
            if f.recommendation:
                lines.append(f"  Fix: {f.recommendation}")
            if f.assigned_to:
                lines.append(f"  Assign to: {f.assigned_to}")

        out = self.qa_dir / "qa-summary-v1.txt"
        out.write_text("\n".join(lines))
        logger.info("Wrote QA summary → %s", out)
