# open-golf-course-maps

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

Working. A GitHub Actions job rebuilds every region in `regions.txt` each
Monday from the latest Geofabrik extracts, publishes the result to GitHub
Pages and commits the quality reports under `reports/`. To add a country, add
its Geofabrik path to `regions.txt`.

The normaliser groups holes into playable courses and grades each one:

- **ready**: 9 or 18 holes, numbered 1..N, every hole with a green;
- **partial**: some holes are missing a green or a number, or the count is odd;
- **outline**: the course boundary is mapped, with no holes.

Each region's `report.md` says how many courses fall in each grade and why
the partial ones fail. Most of what stops a course being ready is missing
data in OpenStreetMap, not something this code can fix.

## Development

```bash
uv sync
uv run pytest

# Build one region from the test fixture (Overpass JSON):
PYTHONPATH=src uv run python -m golf_course_maps.cli build europe/great-britain tests/fixtures/mannings_heath.overpass.json out

# Download and build everything in regions.txt (about 2.5 GB the first time):
PYTHONPATH=src uv run python -m golf_course_maps.cli build-all regions.txt data out
```

This project is not affiliated with or endorsed by the OpenStreetMap
Foundation.
