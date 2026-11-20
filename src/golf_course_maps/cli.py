"""Builds course maps from OpenStreetMap golf data.

  python -m golf_course_maps.cli build REGION SOURCE OUT_DIR
      REGION is a Geofabrik path, e.g. europe/great-britain.
      SOURCE is that region's .osm.pbf extract, or an Overpass .json file
      (used for the test fixtures).

  python -m golf_course_maps.cli build-all REGIONS_FILE DATA_DIR OUT_DIR [--refresh]
      Downloads each region listed in REGIONS_FILE (unless already in
      DATA_DIR) and builds all of them.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .fetch import download, parse_regions
from .normalise import build_courses
from .overpass import load_overpass
from .publish import publish_schemas, write_output


def build(region: str, source: Path, out_dir: Path) -> None:
    if source.suffix == ".json":
        loaded = load_overpass(source)
    else:
        from .pbf import load_pbf  # osmium is only needed for real extracts

        loaded = load_pbf(source)
    result = build_courses(loaded.features)
    region_dir = write_output(result, out_dir, region, loaded.data_timestamp)
    print(f"{region}: {len(result.courses)} courses written to {region_dir}", flush=True)
    if loaded.relations_read:
        print(f"{region}: {loaded.relations_read} multipolygon relations read", flush=True)
    if loaded.skipped_relations:
        print(f"{region}: {loaded.skipped_relations} relations ignored", flush=True)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="golf_course_maps.cli", description=__doc__.split("\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)

    one = commands.add_parser("build", help="build one region from a local source file")
    one.add_argument("region")
    one.add_argument("source", type=Path)
    one.add_argument("out_dir", type=Path)

    many = commands.add_parser("build-all", help="download and build every region in a list")
    many.add_argument("regions_file", type=Path)
    many.add_argument("data_dir", type=Path)
    many.add_argument("out_dir", type=Path)
    many.add_argument("--refresh", action="store_true", help="download again even if already present")

    args = parser.parse_args(argv)
    if args.command == "build":
        build(args.region, args.source, args.out_dir)
        return 0
    regions = parse_regions(args.regions_file.read_text())
    if not regions:
        print(f"{args.regions_file} lists no regions", file=sys.stderr)
        return 1
    for region in regions:
        print(f"{region}: fetching", flush=True)
        source = download(region, args.data_dir, args.refresh)
        build(region, source, args.out_dir)
    publish_schemas(args.out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
