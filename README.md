# bcs-uk-golf-course-maps

Golf course maps for Great Britain and Ireland, built from OpenStreetMap.

One JSON file per course: the tees, greens, hazards and hole lines, plus a
status saying how complete the mapping is. An `index.json` lists every course.

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
PYTHONPATH=src uv run python -m bcs_golf_maps.cli tests/fixtures/mannings_heath.overpass.json out
```

This project is not affiliated with or endorsed by the OpenStreetMap
Foundation.
