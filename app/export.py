"""Command line script: query the API and write the matching characters to a CSV file.

    python -m app.export --output characters.csv
"""
from __future__ import annotations

import argparse
import sys

from .rickandmorty import UpstreamError, find_characters, to_csv


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Alive humans from Earth -> CSV")
    parser.add_argument("-o", "--output", default="characters.csv", help="CSV file to write")
    parser.add_argument(
        "--origin-match",
        choices=("prefix", "exact"),
        default="prefix",
        help='"prefix": Earth and Earth (...) | "exact": only Earth (default: prefix)',
    )
    args = parser.parse_args(argv)
    try:
        characters = find_characters(origin_mode=args.origin_match)
    except UpstreamError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    with open(args.output, "w", encoding="utf-8", newline="") as handle:
        handle.write(to_csv(characters))
    print(f"wrote {len(characters)} characters to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
