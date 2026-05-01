#!/usr/bin/env python3
"""
QA Agent CLI

Examples:

  # Full review (extracts frames + sends to Claude for analysis):
  python3 -m src.cli review ../../productions/the-last-marker

  # Review a specific cut:
  python3 -m src.cli review ../../productions/the-last-marker --cut rough-cut-v2.mp4

  # Extract frames only (no API call, for manual review):
  python3 -m src.cli frames ../../productions/the-last-marker
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .pipeline import QAPipeline


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def cmd_review(args):
    """Full QA review with Claude analysis."""
    qa = QAPipeline(args.production_dir)
    report = qa.review(cut_filename=args.cut)

    print(f"\n{'='*50}")
    print(f"VERDICT: {report.overall_verdict.upper()}")
    print(f"{'='*50}")
    print(f"\n{report.overall_notes}")
    print(f"\nFindings: {report.statistics.get('total_findings', 0)} total")
    print(f"  Critical: {report.statistics.get('critical', 0)}")
    print(f"  Major: {report.statistics.get('major', 0)}")
    print(f"  Minor: {report.statistics.get('minor', 0)}")
    print(f"  Notes: {report.statistics.get('notes', 0)}")

    print(f"\nShot Grades:")
    for sg in report.shot_grades:
        print(f"  {sg.shot_id}: {sg.grade}")

    if report.findings:
        print(f"\nKey Findings:")
        for f in report.findings:
            if f.severity in ("critical", "major"):
                print(f"  [{f.severity.upper()}] {f.description}")

    print(f"\nFull report: {args.production_dir}/qa-reports/qa-report-v1.json")
    print(f"Summary: {args.production_dir}/qa-reports/qa-summary-v1.txt")
    print(f"Frames: {args.production_dir}/qa-reports/frames/")
    return 0


def cmd_frames(args):
    """Extract frames only for manual review."""
    qa = QAPipeline(args.production_dir)
    frames = qa.review_local(cut_filename=args.cut)

    print(f"\nExtracted {len(frames)} frames:")
    for f in frames:
        print(f"  {f['shot_id']}-{f['position']}: {f['timestamp']:.1f}s → {f['frame_path']}")

    print(f"\nOpen frames directory:")
    print(f"  open {args.production_dir}/qa-reports/frames/")
    return 0


def main():
    parser = argparse.ArgumentParser(
        prog="qa",
        description="Movie Swarm QA Agent — Continuity Review",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    # review
    p_rev = sub.add_parser("review", help="Full QA review with Claude analysis")
    p_rev.add_argument("production_dir", type=Path)
    p_rev.add_argument("--cut", default="rough-cut-v1.mp4", help="Cut filename to review")

    # frames
    p_frm = sub.add_parser("frames", help="Extract frames only (manual review)")
    p_frm.add_argument("production_dir", type=Path)
    p_frm.add_argument("--cut", default="rough-cut-v1.mp4", help="Cut filename")

    args = parser.parse_args()
    setup_logging(args.verbose)

    commands = {
        "review": cmd_review,
        "frames": cmd_frames,
    }
    sys.exit(commands[args.command](args))


if __name__ == "__main__":
    main()
