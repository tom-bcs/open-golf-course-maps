"""Usage: python -m bcs_golf_maps.cli OVERPASS_JSON OUT_DIR"""

from __future__ import annotations

import sys
from pathlib import Path

from .normalise import build_courses
from .overpass import load_overpass
from .publish import write_output


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    source, out_dir = Path(argv[0]), Path(argv[1])
    loaded = load_overpass(source)
    result = build_courses(loaded.features)
    write_output(result, out_dir)
    print(f"{len(result.courses)} courses written to {out_dir}")
    if loaded.skipped_relations:
        print(f"{loaded.skipped_relations} relations ignored")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
