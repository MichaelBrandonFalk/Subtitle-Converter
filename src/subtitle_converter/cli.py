from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .core import convert_file
from .gui import launch_gui


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert subtitle files between SRT, VTT, and TTML.")
    parser.add_argument("paths", nargs="*", help="Input subtitle files")
    parser.add_argument("--to-srt", action="store_true", help="Create SRT output")
    parser.add_argument("--to-vtt", action="store_true", help="Create VTT output")
    parser.add_argument("--to-ttml", action="store_true", help="Create TTML output")
    parser.add_argument("--gui", action="store_true", help="Launch the desktop app")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.gui or not args.paths:
        launch_gui()
        return 0

    to_srt = args.to_srt
    to_vtt = args.to_vtt
    to_ttml = args.to_ttml
    if not any((to_srt, to_vtt, to_ttml)):
        to_srt = to_vtt = to_ttml = True

    failures = 0
    for raw_path in args.paths:
        path = Path(raw_path)
        try:
            written = convert_file(path, to_srt, to_vtt, to_ttml)
            for out_path in written:
                print(f"{path.name} -> {out_path.name}")
        except Exception as exc:  # pragma: no cover
            failures += 1
            print(f"Failed to convert {path}: {exc}", file=sys.stderr)

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

