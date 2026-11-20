"""Usage: python -m bcs_golf_maps.cli REGION SOURCE OUT_DIR

REGION is a Geofabrik path, e.g. europe/great-britain.
SOURCE is that region's .osm.pbf extract, or an Overpass .json file (used
for the test fixtures).
"""

from __future__ import annotations

import sys
from pathlib import Path

from .normalise import build_courses
from .overpass import load_overpass
from .publish import write_output


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    region, source, out_dir = argv[0], Path(argv[1]), Path(argv[2])
    if source.suffix == ".json":
        loaded = load_overpass(source)
        timestamp = None
    else:
        from .pbf import load_pbf  # osmium is only needed for real extracts

        loaded = load_pbf(source)
        timestamp = loaded.data_timestamp
    result = build_courses(loaded.features)
    region_dir = write_output(result, out_dir, region, timestamp)
    print(f"{len(result.courses)} courses written to {region_dir}")
    if loaded.relations_read:
        print(f"{loaded.relations_read} multipolygon relations read")
    if loaded.skipped_relations:
        print(f"{loaded.skipped_relations} relations ignored")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
