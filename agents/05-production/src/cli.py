#!/usr/bin/env python3
"""
Production Agent CLI — Run video generation from a shot list.

Examples:

  # Dry run (no API calls, just show what would happen):
  python -m src.cli run shot-list.json output/ --dry-run

  # Preview pass (fast tier, 480p, cheap):
  python -m src.cli run shot-list.json output/ --pass preview

  # Final pass (standard tier, 720p):
  python -m src.cli run shot-list.json output/ --pass final

  # Generate specific shots only:
  python -m src.cli run shot-list.json output/ --pass final --shots s01-sh01 s02-sh03

  # Upload a reference image to fal storage:
  python -m src.cli upload path/to/character-ref.png

  # Show cost estimate without generating:
  python -m src.cli estimate shot-list.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from .config import Resolution, Tier, estimate_cost
from .fal_client import upload_file
from .pipeline import ProductionPipeline, load_shot_list, select_endpoint, _endpoint_type


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def cmd_run(args):
    """Execute a generation pass."""
    pipeline = ProductionPipeline(
        shot_list_path=args.shot_list,
        output_dir=args.output_dir,
        max_retries=args.retries,
        generation_timeout=args.timeout,
    )
    results = pipeline.run(
        pass_type=args.pass_type,
        shot_ids=args.shots or None,
        dry_run=args.dry_run,
    )

    succeeded = sum(1 for r in results if r.success)
    failed = sum(1 for r in results if not r.success)
    total_cost = sum(r.cost_usd for r in results)

    print(f"\n{'='*50}")
    print(f"Pass: {args.pass_type.upper()}")
    print(f"Shots: {len(results)} total, {succeeded} succeeded, {failed} failed")
    print(f"Cost: ${total_cost:.2f}")
    print(f"Output: {args.output_dir}")
    print(f"{'='*50}")

    if failed > 0:
        print("\nFailed shots:")
        for r in results:
            if not r.success:
                print(f"  {r.shot_id}: {r.error}")

    return 0 if failed == 0 else 1


def cmd_estimate(args):
    """Show cost estimate for a shot list without generating."""
    shots = load_shot_list(args.shot_list)

    print(f"Cost Estimate for: {args.shot_list}")
    print(f"Total shots: {len(shots)}\n")

    for pass_type, tier, resolution in [
        ("preview", Tier.FAST, Resolution.P480),
        ("final", Tier.STANDARD, Resolution.P720),
    ]:
        total = 0.0
        print(f"--- {pass_type.upper()} pass ({tier.value} / {resolution.value}) ---")
        for shot in shots:
            endpoint = select_endpoint(shot, tier)
            ep_type = _endpoint_type(endpoint)
            cost = estimate_cost(
                tier, resolution, ep_type,
                shot.target_duration_seconds,
                has_video_inputs=bool(shot.video_ref_urls),
            )
            total += cost
            print(f"  {shot.shot_id}: {shot.target_duration_seconds}s → {ep_type} → ${cost:.2f}")
        print(f"  TOTAL: ${total:.2f}\n")

    return 0


def cmd_upload(args):
    """Upload a file to fal storage."""
    url = upload_file(args.file_path)
    print(f"Uploaded: {url}")
    return 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        prog="production-agent",
        description="Movie Swarm Production Agent — Seedance 2.0 via fal.ai",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Debug logging")
    sub = parser.add_subparsers(dest="command", required=True)

    # run
    p_run = sub.add_parser("run", help="Execute a generation pass")
    p_run.add_argument("shot_list", type=Path, help="Path to shot-list.json")
    p_run.add_argument("output_dir", type=Path, help="Output directory for clips and metadata")
    p_run.add_argument("--pass", dest="pass_type", choices=["preview", "final"], default="final")
    p_run.add_argument("--shots", nargs="+", help="Only generate these shot IDs")
    p_run.add_argument("--dry-run", action="store_true", help="Show payloads without calling fal")
    p_run.add_argument("--retries", type=int, default=3, help="Max retries per shot")
    p_run.add_argument("--timeout", type=int, default=300, help="Timeout per generation (seconds)")

    # estimate
    p_est = sub.add_parser("estimate", help="Show cost estimate for a shot list")
    p_est.add_argument("shot_list", type=Path, help="Path to shot-list.json")

    # upload
    p_up = sub.add_parser("upload", help="Upload a file to fal storage")
    p_up.add_argument("file_path", type=Path, help="Local file to upload")

    args = parser.parse_args()
    setup_logging(args.verbose)

    commands = {
        "run": cmd_run,
        "estimate": cmd_estimate,
        "upload": cmd_upload,
    }
    sys.exit(commands[args.command](args))


if __name__ == "__main__":
    main()
