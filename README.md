# bcs-golf-course-maps

Golf course maps built from OpenStreetMap, starting with Great Britain and
Ireland.

One JSON file per course: the tees, greens, hazards and hole lines, plus a
status saying how complete the mapping is.

## Layout

Courses are grouped by region, using the path of the Geofabrik extract each
region is built from, so the folders group by continent for free:

```
regions.json                                  every region built, with bounds and counts
europe/great-britain/index.json               one entry per course in the region
europe/great-britain/report.md                how complete the mapping is
europe/great-britain/courses/w386407226.json  one file per course
europe/ireland-and-northern-ireland/…
```

A client fetches `regions.json`, picks the region containing the course it
wants, then fetches only that region's index. Geofabrik's Ireland extract
includes Northern Ireland, and its Great Britain extract does not.

## Data licence

The data is © OpenStreetMap contributors and is available under the
[Open Database Licence (ODbL) 1.0](https://opendatacommons.org/licenses/odbl/1-0/).
Anything you build from it must credit "© OpenStreetMap contributors" and
share the data it derives under the same licence. See `DATA_LICENCE.md`.

## Code licence

The code in this repository is MIT licensed. See `LICENCE`.

## Status

Work in progress. Milestone 1 is done: the normaliser, tested on Mannings
Heath (a 27-hole club that OpenStreetMap maps as an 18-hole course with no
course tag and a tagged 9-hole course). It does not yet read the Geofabrik
extracts, publish to GitHub Pages or run on a schedule.

## Development

```bash
uv sync
uv run pytest

# From the test fixture (Overpass JSON):
PYTHONPATH=src uv run python -m bcs_golf_maps.cli europe/great-britain tests/fixtures/mannings_heath.overpass.json out

# From a Geofabrik extract:
PYTHONPATH=src uv run python -m bcs_golf_maps.cli europe/ireland-and-northern-ireland data/europe/ireland-and-northern-ireland-latest.osm.pbf out
```

This project is not affiliated with or endorsed by the OpenStreetMap
Foundation.
