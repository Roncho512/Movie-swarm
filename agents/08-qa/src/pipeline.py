"""
pipeline.py — The QA agent's review pipeline.

Extracts frames from the rough cut, sends them to Claude for visual
analysis against the style bible and character references, and produces
a structured QA report.

Usage:
    from src.pipeline import QAPipeline
    qa = QAPipeline(production_dir="productions/the-last-marker")
    report = qa.review()
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
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
# JSON parsing — robust extraction from LLM responses
# ---------------------------------------------------------------------------


def parse_json_from_llm(response_text: str) -> dict:
    """
    Extract JSON from an LLM response that may contain:
      - Preamble text before JSON ("Here's my analysis:\n```json\n{...}")
      - Trailing commentary after JSON ("```\nLet me know if...")
      - Multiple markdown code fences
      - Raw JSON with no fences
      - JSON split across multiple text blocks

    Strategy (in order):
      1. Try the whole response as raw JSON
      2. Extract content from ```json ... ``` fences
      3. Extract content from ``` ... ``` fences (no language tag)
      4. Find the largest { ... } block via brace-matching
      5. Give up and return an error structure
    """
    clean = response_text.strip()

    # ------------------------------------------------------------------
    # Strategy 1: Raw JSON (model obeyed the prompt perfectly)
    # ------------------------------------------------------------------
    if clean.startswith("{"):
        try:
            return json.loads(clean)
        except json.JSONDecodeError:
            pass  # Has trailing text, fall through

    # ------------------------------------------------------------------
    # Strategy 2: ```json ... ``` fenced block
    # ------------------------------------------------------------------
    fenced = re.findall(r"```json\s*\n(.*?)```", clean, re.DOTALL)
    for block in fenced:
        try:
            return json.loads(block.strip())
        except json.JSONDecodeError:
            continue

    # ------------------------------------------------------------------
    # Strategy 3: ``` ... ``` fenced block (no language tag)
    # ------------------------------------------------------------------
    fenced_plain = re.findall(r"```\s*\n(.*?)```", clean, re.DOTALL)
    for block in fenced_plain:
        stripped = block.strip()
        if stripped.startswith("{"):
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                continue

    # ------------------------------------------------------------------
    # Strategy 4: Brace-matched extraction
    # Find the first '{' and walk forward counting braces until balanced.
    # This handles preamble + trailing text with no fences.
    # ------------------------------------------------------------------
    first_brace = clean.find("{")
    if first_brace != -1:
        depth = 0
        in_string = False
        escape_next = False
        end_pos = -1

        for i in range(first_brace, len(clean)):
            ch = clean[i]

            if escape_next:
                escape_next = False
                continue

            if ch == "\\":
                if in_string:
                    escape_next = True
                continue

            if ch == '"' and not escape_next:
                in_string = not in_string
                continue

            if in_string:
                continue

            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end_pos = i
                    break

        if end_pos != -1:
            candidate = clean[first_brace : end_pos + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                logger.warning(
                    "Brace-matched block (%d chars) failed to parse",
                    len(candidate),
                )

    # ------------------------------------------------------------------
    # Strategy 5: Give up
    # ------------------------------------------------------------------
    logger.error("Could not extract JSON from LLM response (%d chars)", len(clean))
    logger.debug("Response preview: %.500s", clean[:500])
    return {
        "overall_verdict": "error",
        "overall_notes": "Failed to parse QA analysis from model response.",
        "raw_response": response_text,
        "findings": [],
        "shot_grades": {},
    }


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
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    results = []

    if shots:
        for shot in shots:
            sid = shot["shot_id"]
            start = shot["start_time"]
            dur = shot["duration"]
            positions = {
                "start": start + 0.1,
                "mid": start + dur / 2,
                "end": start + dur - 0.1,
            }
            for pos_name, ts in positions.items():
                ts = max(0, ts)
                out_file = output_dir / f"{sid}-{pos_name}.png"
                _ffmpeg_extract_frame(video_path, ts, out_file)
                results.append({
                    "shot_id": sid,
                    "position": pos_name,
                    "timestamp": ts,
                    "frame_path": str(out_file),
                })

    elif timestamps:
        for i, ts in enumerate(timestamps):
            out_file = output_dir / f"frame-{i:04d}.png"
            _ffmpeg_extract_frame(video_path, ts, out_file)
            results.append({
                "shot_id": f"frame-{i:04d}",
                "position": "exact",
                "timestamp": ts,
                "frame_path": str(out_file),
            })

    logger.info("Extracted %d frames → %s", len(results), output_dir)
    return results


def _ffmpeg_extract_frame(video_path, timestamp: float, output_path: Path):
    """Extract a single frame at the given timestamp."""
    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{timestamp:.3f}",
        "-i", str(video_path),
        "-vframes", "1",
        "-q:v", "2",
        str(output_path),
    ]
    try:
        subprocess.run(
            cmd, capture_output=True, text=True, timeout=15, check=True,
        )
    except subprocess.CalledProcessError as e:
        logger.warning("Frame extraction failed at %.1fs: %s", timestamp, e.stderr[:200])
    except subprocess.TimeoutExpired:
        logger.warning("Frame extraction timed out at %.1fs", timestamp)


def _encode_frame_b64(frame_path: Path) -> str:
    """Read a PNG frame and return base64-encoded string."""
    with open(frame_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


# ---------------------------------------------------------------------------
# Claude vision analysis
# ---------------------------------------------------------------------------


def analyze_frames_with_claude(
    frames: list[dict],
    shot_list_context: str = "",
    model: str = "claude-sonnet-4-20250514",
    raw_response_dir: Optional[Path] = None,
) -> dict:
    """
    Send extracted frames to Claude for visual QA analysis.

    Args:
        raw_response_dir: If provided, saves Claude's raw text response
            to this directory for debugging. This is the fix for the
            NameError on 'output_dir' from the prior version.

    Returns parsed JSON report from Claude's response.
    """
    import requests

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY not set")

    # Build the analysis prompt
    system_prompt = """You are a film continuity supervisor reviewing an AI-generated short film.

You will receive frames extracted from the assembled cut (start, mid, end of each shot).

Analyze for:
1. Visual continuity — character appearance, vehicle, environment consistency across shots
2. Temporal continuity — time of day, lighting direction, shadow consistency
3. Spatial continuity — screen direction, 180-degree rule, geography
4. Technical quality — artifacts, resolution drops, generation glitches
5. Style adherence — does each shot match the intended visual style?

Respond with ONLY a JSON object (no preamble, no commentary, no markdown fences).

The JSON must have this exact structure:
{
  "overall_verdict": "approved" | "revise" | "reject",
  "overall_notes": "summary string",
  "findings": [
    {
      "finding_id": "F001",
      "severity": "critical" | "major" | "minor" | "note",
      "category": "visual_continuity" | "temporal_continuity" | "spatial_continuity" | "audio_continuity" | "narrative_continuity" | "technical_quality" | "style_adherence",
      "shots_affected": ["s01-sh01", "s01-sh02"],
      "timestamp": "25.0s",
      "description": "what is wrong",
      "evidence_frames": ["frames/s01-sh02-end.png"],
      "recommendation": "how to fix",
      "assigned_to": "production" | "sound_designer" | "editor" | "art_director"
    }
  ],
  "shot_grades": [
    {
      "shot_id": "s01-sh01",
      "grade": "A",
      "notes": "reason"
    }
  ]
}

CRITICAL: Output ONLY the JSON object. No text before it. No text after it.
No markdown code fences. Just the raw JSON starting with { and ending with }."""

    # Build multimodal content array
    content: list[dict] = []

    if shot_list_context:
        content.append({
            "type": "text",
            "text": f"Shot list for reference:\n{shot_list_context}",
        })

    content.append({
        "type": "text",
        "text": f"Review the following {len(frames)} frames extracted from the rough cut:",
    })

    # Group frames by shot
    shots_seen: dict[str, list[dict]] = {}
    for f in frames:
        shots_seen.setdefault(f["shot_id"], []).append(f)

    for shot_id, shot_frames in shots_seen.items():
        content.append({
            "type": "text",
            "text": f"\n--- Shot: {shot_id} ---",
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
            "system": system_prompt,
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

    logger.info("Raw Claude response length: %d chars", len(response_text))

    # Save raw response for debugging
    if raw_response_dir:
        raw_path = Path(raw_response_dir) / "claude-raw-response.txt"
        raw_path.write_text(response_text)
        logger.info("Saved raw response → %s", raw_path)

    # Parse JSON — using the robust parser
    return parse_json_from_llm(response_text)


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


class QAPipeline:
    """
    Orchestrates QA review of an assembled cut.

    Usage:
        qa = QAPipeline("productions/the-last-marker")
        report = qa.review()
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
        # Try EDL first
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
        if not clips_dir.exists():
            logger.warning("No EDL and no clips directory at %s", clips_dir)
            return []

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
            prompt_preview = s.get("generation_prompt", "")[:120]
            lines.append(f"  {s['shot_id']}: {prompt_preview}...")
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
            raw_response_dir=self.qa_dir,
        )

        # 5. Build report
        self.report = self._build_report(cut_filename)

        # 6. Write outputs
        self._write_report()
        self._write_summary()

        return self.report

    def review_local(
        self,
        cut_filename: str = "rough-cut-v1.mp4",
    ) -> list[dict]:
        """
        Extract frames only — no API call.
        For manual review or when you want to inspect frames before
        spending API credits.
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
        return self.frames

    def _build_report(self, cut_filename: str) -> QAReport:
        """Convert raw Claude analysis into a typed QAReport."""
        a = self.analysis
        production_id = self.prod_dir.name

        # Parse findings
        findings = []
        for f in a.get("findings", []):
            findings.append(Finding(
                finding_id=f.get("finding_id", "F???"),
                severity=f.get("severity", "note"),
                category=f.get("category", "unknown"),
                shots_affected=f.get("shots_affected", []),
                timestamp=f.get("timestamp", ""),
                description=f.get("description", ""),
                evidence_frames=f.get("evidence_frames", []),
                recommendation=f.get("recommendation", ""),
                assigned_to=f.get("assigned_to", ""),
            ))

        # Parse shot grades — handle both list and dict formats
        shot_grades = []
        raw_grades = a.get("shot_grades", [])
        if isinstance(raw_grades, list):
            for sg in raw_grades:
                shot_grades.append(ShotGrade(
                    shot_id=sg.get("shot_id", "???"),
                    grade=sg.get("grade", "?"),
                    notes=sg.get("notes", ""),
                ))
        elif isinstance(raw_grades, dict):
            # Claude sometimes returns {shot_id: {grade, notes}} instead of list
            for shot_id, info in raw_grades.items():
                if isinstance(info, dict):
                    shot_grades.append(ShotGrade(
                        shot_id=shot_id,
                        grade=info.get("grade", "?"),
                        notes=info.get("notes", ""),
                    ))
                elif isinstance(info, str):
                    shot_grades.append(ShotGrade(
                        shot_id=shot_id,
                        grade=info,
                        notes="",
                    ))

        # Compute statistics
        severity_counts = {"critical": 0, "major": 0, "minor": 0, "note": 0}
        for f in findings:
            sev = f.severity.lower()
            if sev in severity_counts:
                severity_counts[sev] += 1
        severity_counts["total_findings"] = len(findings)

        return QAReport(
            production_id=production_id,
            cut_reviewed=cut_filename,
            review_date=datetime.now(timezone.utc).isoformat(),
            overall_verdict=a.get("overall_verdict", "error"),
            overall_notes=a.get("overall_notes", ""),
            findings=findings,
            shot_grades=shot_grades,
            statistics=severity_counts,
        )

    def _write_report(self):
        """Write the structured JSON report."""
        if not self.report:
            return

        # Version the report
        version = 1
        while (self.qa_dir / f"qa-report-v{version}.json").exists():
            version += 1

        out = self.qa_dir / f"qa-report-v{version}.json"
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
            # Count key is "note", the severity stored by _build_report.
            f"  Notes: {self.report.statistics.get('note', 0)}",
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

        # Version the summary
        version = 1
        while (self.qa_dir / f"qa-summary-v{version}.txt").exists():
            version += 1

        out = self.qa_dir / f"qa-summary-v{version}.txt"
        out.write_text("\n".join(lines))
        logger.info("Wrote QA summary → %s", out)
