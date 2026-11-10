#!/usr/bin/env python3
"""
Sound Designer Agent CLI

Examples:

  # Dry run. Prompts are read from the production's audio/sound-prompts.json:
  python -m src.cli sfx shot-list.json ./audio --dry-run

  # Or pass the library file yourself:
  python -m src.cli sfx shot-list.json ./audio --library audio/sound-prompts.json --dry-run

A run without --dry-run is refused. This build does not call a provider.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .pipeline import SoundDesignPipeline
from .elevenlabs_client import search_voices


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _pipeline(args) -> SoundDesignPipeline:
    return SoundDesignPipeline(args.shot_list, args.output_dir, library_path=args.library)


def cmd_sfx(args):
    """Generate sound effects."""
    pipeline = _pipeline(args)
    results = pipeline.generate_sfx_library(
        asset_ids=args.assets or None,
        dry_run=args.dry_run,
    )
    pipeline.write_audio_manifest()

    generated = sum(1 for a in results if a.generated)
    failed = sum(1 for a in results if a.error)
    print(f"\nSFX: {generated} generated, {failed} failed, {len(results)} total")
    return 0 if failed == 0 else 1


def cmd_dialogue(args):
    """Generate dialogue."""
    if not args.voice_id:
        print("Error: --voice-id required. Use 'voices' command to search.")
        return 1

    pipeline = _pipeline(args)
    results = pipeline.generate_dialogue_assets(
        voice_id=args.voice_id,
        dry_run=args.dry_run,
    )
    pipeline.write_audio_manifest()

    generated = sum(1 for a in results if a.generated)
    print(f"\nDialogue: {generated} generated, {len(results)} total")
    return 0


def cmd_music(args):
    """Generate music/score."""
    pipeline = _pipeline(args)
    results = pipeline.generate_music_assets(dry_run=args.dry_run)
    pipeline.write_audio_manifest()

    generated = sum(1 for a in results if a.generated)
    print(f"\nMusic: {generated} generated, {len(results)} total")
    return 0


def cmd_voices(args):
    """Search for voices."""
    results = search_voices(query=args.query, language=args.language)
    print(f"\nFound {len(results)} voices for '{args.query}':\n")
    for v in results:
        print(f"  {v['voice_id']}  {v['name']}")
        if v.get("description"):
            print(f"    {v['description'][:100]}")
        print()
    return 0


def cmd_all(args):
    """Generate everything."""
    pipeline = _pipeline(args)

    print("=== Sound Effects ===")
    pipeline.generate_sfx_library(dry_run=args.dry_run)

    if args.voice_id:
        print("\n=== Dialogue ===")
        pipeline.generate_dialogue_assets(
            voice_id=args.voice_id,
            dry_run=args.dry_run,
        )
    else:
        print("\n=== Dialogue: SKIPPED (no --voice-id) ===")

    print("\n=== Music ===")
    pipeline.generate_music_assets(dry_run=args.dry_run)

    pipeline.write_audio_manifest()
    print("\nDone. Audio manifest written.")
    return 0


def main():
    parser = argparse.ArgumentParser(
        prog="sound-designer",
        description="Movie Swarm Sound Designer Agent — ElevenLabs",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    # sfx
    p_sfx = sub.add_parser("sfx", help="Generate sound effects")
    p_sfx.add_argument("shot_list", type=Path)
    p_sfx.add_argument("output_dir", type=Path)
    p_sfx.add_argument("--assets", nargs="+", help="Specific asset IDs to generate")
    p_sfx.add_argument("--library", type=Path, help="sound-prompts.json for this production")
    p_sfx.add_argument("--dry-run", action="store_true")

    # dialogue
    p_dlg = sub.add_parser("dialogue", help="Generate dialogue")
    p_dlg.add_argument("shot_list", type=Path)
    p_dlg.add_argument("output_dir", type=Path)
    p_dlg.add_argument("--voice-id", required=True)
    p_dlg.add_argument("--library", type=Path, help="sound-prompts.json for this production")
    p_dlg.add_argument("--dry-run", action="store_true")

    # music
    p_mus = sub.add_parser("music", help="Generate music/score")
    p_mus.add_argument("shot_list", type=Path)
    p_mus.add_argument("output_dir", type=Path)
    p_mus.add_argument("--library", type=Path, help="sound-prompts.json for this production")
    p_mus.add_argument("--dry-run", action="store_true")

    # voices
    p_vox = sub.add_parser("voices", help="Search for voices")
    p_vox.add_argument("query", help="Search query, for example 'low quiet voice'")
    p_vox.add_argument("--language", default="es", help="Language code")

    # all
    p_all = sub.add_parser("all", help="Generate everything")
    p_all.add_argument("shot_list", type=Path)
    p_all.add_argument("output_dir", type=Path)
    p_all.add_argument("--voice-id", help="Voice ID for dialogue")
    p_all.add_argument("--library", type=Path, help="sound-prompts.json for this production")
    p_all.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()
    setup_logging(args.verbose)

    commands = {
        "sfx": cmd_sfx,
        "dialogue": cmd_dialogue,
        "music": cmd_music,
        "voices": cmd_voices,
        "all": cmd_all,
    }
    sys.exit(commands[args.command](args))


if __name__ == "__main__":
    main()
