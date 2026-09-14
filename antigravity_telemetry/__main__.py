"""
CLI interface for antigravity_telemetry.

Usage examples:
    python -m antigravity_telemetry dump --json
    python -m antigravity_telemetry conversations --json
    python -m antigravity_telemetry models --json
    python -m antigravity_telemetry --help
"""

from pathlib import Path
import argparse
import json
import sys
from typing import List, Optional

from . import (
    __version__,
    DEFAULT_ANTIGRAVITY_DIR,
    discover_all_conversations,
    load_model_census,
    read_all_turns,
)


def main(args: Optional[List[str]] = None) -> int:
    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument(
        "--antigravity-dir",
        type=Path,
        default=DEFAULT_ANTIGRAVITY_DIR,
        help="Path to Antigravity directory (default: ~/.gemini/antigravity)",
    )

    parser = argparse.ArgumentParser(
        prog="antigravity_telemetry",
        parents=[common_parser],
        description="Zero-dependency telemetry extractor and protobuf parser for Google Antigravity.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # 'dump' subcommand
    dump_parser = subparsers.add_parser(
        "dump",
        parents=[common_parser],
        help="Dump parsed model turns from local Antigravity runtime",
    )
    dump_parser.add_argument(
        "--json",
        action="store_true",
        help="Output turns as JSON array to stdout",
    )
    dump_parser.add_argument(
        "--max-conversations",
        type=int,
        default=None,
        help="Maximum conversations to inspect (default: all)",
    )
    dump_parser.add_argument(
        "--compact",
        action="store_true",
        help="Output compact JSON instead of indented",
    )

    # 'conversations' subcommand
    conv_parser = subparsers.add_parser(
        "conversations",
        parents=[common_parser],
        help="List discovered conversation databases and metadata",
    )
    conv_parser.add_argument(
        "--json",
        action="store_true",
        help="Output conversations as JSON to stdout",
    )
    conv_parser.add_argument(
        "--max-conversations",
        type=int,
        default=None,
        help="Maximum conversations to inspect (default: all)",
    )

    # 'models' subcommand
    models_parser = subparsers.add_parser(
        "models",
        parents=[common_parser],
        help="Inspect canonical 19-model census",
    )
    models_parser.add_argument(
        "--json",
        action="store_true",
        help="Output models census as JSON to stdout",
    )

    # Handle top-level fallback for `python -m antigravity_telemetry --json`
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output turns as JSON array (shorthand for dump --json)",
    )

    parsed = parser.parse_args(args)
    cmd = parsed.command

    # If no subcommand was passed but --json was specified, treat as 'dump --json'
    if cmd is None:
        if getattr(parsed, "json", False):
            cmd = "dump"
        else:
            parser.print_help()
            return 0

    if cmd == "dump":
        max_c = getattr(parsed, "max_conversations", None)
        turns = read_all_turns(antigravity_dir=parsed.antigravity_dir, max_conversations=max_c)
        if getattr(parsed, "json", False):
            indent = None if getattr(parsed, "compact", False) else 2
            json.dump(turns, sys.stdout, indent=indent)
            sys.stdout.write("\n")
        else:
            total_input = sum(t.get("total_input_tokens", 0) for t in turns)
            cached_input = sum(t.get("cached_tokens", 0) for t in turns)
            total_output = sum(t.get("output_tokens_total", 0) for t in turns)
            cache_pct = (cached_input / total_input * 100.0) if total_input > 0 else 0.0
            print(f"Discovered {len(turns)} generation turns across Antigravity runtime.")
            print(f"Total Input: {total_input:,} | Cached: {cache_pct:.2f}% | Output: {total_output:,}")

    elif cmd == "conversations":
        max_c = getattr(parsed, "max_conversations", None)
        convos = discover_all_conversations(antigravity_dir=parsed.antigravity_dir, max_conversations=max_c)
        if getattr(parsed, "json", False):
            json.dump(convos, sys.stdout, indent=2)
            sys.stdout.write("\n")
        else:
            print(f"Discovered {len(convos)} conversation databases:")
            for c in convos[:20]:
                print(f"  - [{c['convo_id'][:8]}] {c.get('workspace_name', 'Unknown')}: {c.get('title', '')}")
            if len(convos) > 20:
                print(f"  ... and {len(convos) - 20} more.")

    elif cmd == "models":
        census = load_model_census()
        if getattr(parsed, "json", False):
            json.dump(census, sys.stdout, indent=2)
            sys.stdout.write("\n")
        else:
            print(f"Canonical Model Census ({len(census)} models):")
            for mid, info in sorted(census.items()):
                print(f"  - ID {mid:>4}: {info.get('name', 'Unknown')} ({info.get('family', '')})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
