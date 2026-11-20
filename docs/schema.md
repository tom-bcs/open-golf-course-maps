# Data format

What a client can rely on in the published files. The JSON Schemas in
[`schema/`](../schema) are the machine-checkable version, and the tests fail if
the output drifts from them. This page explains what they can't: what the
fields mean and what to expect from real data.

Schema version: **1** (the `schema` field in every file).

## Files

Published at https://tom-bcs.github.io/open-golf-course-maps/.

| File | What it is |
|---|---|
| `regions.json` | Every region built, with its bounds and course counts. Start here. |
| `<region>/index.json` | One entry per course in the region. Roughly 760 KB for Great Britain. |
| `<region>/courses/<id>.json` | One course: holes, tees, greens, hazards. Around 20 KB. |
| `<region>/report.md` | How complete the region's mapping is, and why courses aren't ready. |
| `schema/*.schema.json` | The JSON Schemas. |

A region is the path of the Geofabrik extract it was built from, for example
`europe/great-britain`. Northern Ireland is in `europe/ireland-and-northern-ireland`,
not in Great Britain.

A client fetches `regions.json`, picks the region whose `bounds` contain the
course it wants, fetches that region's `index.json` once and caches it, then
fetches individual course files as needed.

## Conventions

- **Coordinates are `[latitude, longitude]`**, in degrees (WGS 84), rounded to
  7 decimal places (about 1 cm). This is the reverse of GeoJSON, which is
  `[longitude, latitude]`. Don't pass these arrays to a GeoJSON parser unchanged.
- **Distances are not stored.** Everything is geometry. A client measures
  distances itself, in metres, and converts for display.
- **Polygons are a list of vertices with the closing point not repeated.** The
  last vertex joins back to the first. Polygons have no holes.
- **`bounds` is `[south, west, north, east]`.**
- **Strings are human text, not codes.** `issues` and `notes` are for people and
  their wording may change. Branch on `status`, never on their text.
- **Tolerate unknown fields.** New fields can be added without a version bump. The
  schemas in this repository are strict on purpose, so a new field can't ship
  undocumented, but a client must not be.

## Course file

| Field | Type | Meaning |
|---|---|---|
| `schema` | `1` | Schema version. |
| `attribution` | string | "© OpenStreetMap contributors (ODbL 1.0)". Must be shown wherever a map drawn from this data appears. |
| `id` | string | See "Ids" below. |
| `name` | string or null | The course's name: its `golf:course:name` if OpenStreetMap has one, otherwise the club's name. Null when nothing is named. |
| `club` | string or null | The name of the outline that holds the course. |
| `status` | `ready`, `partial` or `outline` | See "Status". |
| `issues` | strings | Why the course isn't `ready`. Empty when it is. |
| `notes` | strings | Gaps that don't stop it being `ready`: no par, no tee polygon. |
| `holeCount` | integer | Length of `holes`. |
| `pars` | integers or null | Each hole's par, in hole order. Null where OpenStreetMap has none. |
| `parComplete` | boolean | Whether every hole has a par. |
| `centre` | lat/lon | The middle of `bounds`. |
| `bounds` | 4 numbers | The box around the holes (or the outline, for `outline`). |
| `holes` | holes | In hole-number order. Empty for `outline`. |

### Hole

| Field | Type | Meaning |
|---|---|---|
| `number` | integer or null | The hole's number on the course. Null if OpenStreetMap has no readable one. |
| `par` | integer or null | |
| `name` | string or null | Some courses name each hole. |
| `line` | lat/lon list | The hole's centre line, **from the tee to the green**. Two points on a straight hole. The first point is the tee. |
| `tees` | polygons | Tee boxes. Often empty (a fifth of real holes have none mapped), and often several (one per set of tees, not labelled). Use `line[0]` for the tee position. |
| `green` | object or null | `polygon` and `centre` (the centroid). Null when no green is mapped. |
| `pin` | lat/lon or null | Where someone once mapped the flag. See "Data you can't rely on". |
| `hazards` | list | Each `{kind, polygon}`, `kind` being `bunker`, `water` or `lateral_water`. |

A tee, hazard or pin belongs to the single hole it is nearest. A green can belong
to more than one hole (shared greens exist). A bunker that matters to two
holes appears on only one.

## Status

- **`ready`**: the holes are numbered 1 to N with N equal to 9 or 18, with no gaps
  or repeats, and every hole has a green. Distances to the front, centre and
  back of every green can be computed.
- **`partial`**: holes are mapped but at least one condition above fails. `issues`
  says which: a missing green, a missing or repeated number, or an unusual
  count. Use whatever holes are present, and expect gaps.
- **`outline`**: only the course boundary is mapped (`holes` is empty). There's
  nothing to measure, but the position is still usable for matching.

A missing tee polygon or par doesn't stop a course being `ready`. Neither is
needed for distances.

## Ids

- `w123` is built from OpenStreetMap way 123, `r123` from relation 123. A course
  with its own `golf:course:name` inside a shared outline adds a slug:
  `w123-kingfisher-course`. A course the pipeline had to split out of one outline
  by proximity adds `-h<hole id>`. A course with no outline at all is `h<hole id>`.
- **Ids are stable only as long as the mapping is.** OpenStreetMap editors merge and
  redraw features, and an id can change or disappear between weekly builds. A
  client that stores an id must cope with it vanishing: keep enough about the
  course (its name and position) to match it again.

## Data you can't rely on

This is community-mapped data, and some of it is missing or wrong.

- **Coverage.** About two in five GB courses have an outline and no holes. They are
  `outline`, and there's nothing the pipeline can do about it.
- **Hole numbers.** About a third of mapped holes have no `ref` tag. The pipeline
  doesn't guess an order, so that course is `partial`.
- **Pars** are the mapper's, and may be missing or disagree with the scorecard.
  A client with a scorecard should prefer it, and use `pars` only as a
  cross-check.
- **Pins** are the position someone mapped once. A real pin moves from day to day.
  Treat it as "somewhere on this green", never as where the flag is today.
- **Positions are traced from aerial imagery** by volunteers. They line up with
  Apple's satellite imagery well (checked by eye at Mannings Heath, 2026-11-20),
  but a metre or two of error is normal.
- **Nothing here is elevation, "plays like" distance or club advice**, and nothing
  will be. Under Rule 4.3 of the Rules of Golf, distance information is
  allowed and those aren't.

## Versioning

`schema` is a single integer. It's bumped only for a change that breaks a
client that follows these rules: a field removed or renamed, a type changed, or a
meaning changed. Adding a field, or a new `kind`, is not a bump, which is why
clients must tolerate what they don't recognise. When the version changes, the
old files are not kept, so a client has to be updated before the first build with
the new number.

## Licence

The data is © OpenStreetMap contributors, under the
[ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/). A database derived
from it must be offered under the same licence, and a map drawn from it must credit
OpenStreetMap contributors. The code that builds it is MIT. See
[`DATA_LICENCE.md`](../DATA_LICENCE.md).
