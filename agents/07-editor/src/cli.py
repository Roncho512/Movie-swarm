#!/usr/bin/env python3
"""
Editor Agent CLI

Examples:

  # Assemble rough cut (video only, no audio layering):
  python3 -m src.cli assemble ../../productions/the-last-marker

  # Assemble with audio layers defined in a mix file:
  python3 -m src.cli assemble ../../productions/the-last-marker --mix-file mix.json

  # Just concatenate video (no audio):
  python3 -m src.cli concat ../../productions/the-last-marker

  # Probe clip durations:
  python3 -m src.cli probe ../../productions/the-last-marker
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from .pipeline import EditPipeline, AudioLayer


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def load_mix_file(mix_path: Path, production_dir: Path) -> list[AudioLayer]:
    """Load audio layer definitions from a JSON mix file."""
    raw = json.loads(mix_path.read_text())
    layers = []
    for entry in raw.get("layers", []):
        # Resolve relative paths against production dir
        src = entry["source_path"]
        if not src.startswith("/"):
            src = str(production_dir / src)
        layers.append(AudioLayer(
            asset_id=entry["asset_id"],
            source_path=src,
            layer_type=entry.get("layer_type", "sfx"),
            timeline_start=entry.get("timeline_start", 0.0),
            duration=entry.get("duration"),
            volume=entry.get("volume", 1.0),
            loop=entry.get("loop", False),
            fade_in=entry.get("fade_in", 0.0),
            fade_out=entry.get("fade_out", 0.0),
            trim_start=entry.get("trim_start", 0.0),
            trim_end=entry.get("trim_end", 0.0),
        ))
    return layers


def cmd_assemble(args):
    """Full rough cut assembly."""
    pipeline = EditPipeline(args.production_dir)

    if args.mix_file:
        mix_path = Path(args.mix_file)
        if not mix_path.is_absolute():
            mix_path = Path.cwd() / mix_path
        pipeline.audio_layers = load_mix_file(mix_path, Path(args.production_dir))

    result = pipeline.assemble_rough_cut()
    print(f"\nRough cut assembled: {result}")
    return 0


def cmd_concat(args):
    """Just concatenate video clips."""
    pipeline = EditPipeline(args.production_dir)
    pipeline.discover_clips()
    result = pipeline.concatenate_video()
    print(f"\nConcatenated video: {result}")
    return 0


def cmd_probe(args):
    """Show clip inventory and durations."""
    pipeline = EditPipeline(args.production_dir)
    clips = pipeline.discover_clips()

    total = sum(c.duration for c in clips)
    print(f"\nClip inventory ({len(clips)} clips, {total:.1f}s total):\n")
    for c in clips:
        print(f"  {c.shot_id}: {c.duration:.1f}s  (starts at {c.start_time:.1f}s)")
    print(f"\n  Total: {total:.1f}s")
    return 0


def main():
    parser = argparse.ArgumentParser(
        prog="editor",
        description="Movie Swarm Editor Agent — FFmpeg Assembly",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    # assemble
    p_asm = sub.add_parser("assemble", help="Full rough cut assembly")
    p_asm.add_argument("production_dir", type=Path)
    p_asm.add_argument("--mix-file", type=Path, help="JSON file defining audio layers")

    # concat
    p_cat = sub.add_parser("concat", help="Concatenate video clips only")
    p_cat.add_argument("production_dir", type=Path)

    # probe
    p_prb = sub.add_parser("probe", help="Show clip inventory and durations")
    p_prb.add_argument("production_dir", type=Path)

    args = parser.parse_args()
    setup_logging(args.verbose)

    commands = {
        "assemble": cmd_assemble,
        "concat": cmd_concat,
        "probe": cmd_probe,
    }
    sys.exit(commands[args.command](args))


if __name__ == "__main__":
    main()
