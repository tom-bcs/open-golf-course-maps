"""Downloads Geofabrik extracts and reads the list of regions to build."""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from urllib.request import Request, urlopen

GEOFABRIK = "https://download.geofabrik.de"
# Geofabrik asks automated downloaders to say who they are.
USER_AGENT = "open-golf-course-maps (https://github.com/tom-bcs/open-golf-course-maps)"
# A Geofabrik path such as europe/great-britain. Strict, because these become
# file paths and URLs.
_REGION = re.compile(r"[a-z0-9][a-z0-9-]*(/[a-z0-9][a-z0-9-]*)*")


def parse_regions(text: str) -> list[str]:
    """One Geofabrik path per line. Blank lines and `#` comments are ignored."""
    regions = []
    for number, line in enumerate(text.splitlines(), start=1):
        region = line.split("#", 1)[0].strip()
        if not region:
            continue
        if not _REGION.fullmatch(region):
            raise ValueError(f"line {number}: {region!r} is not a Geofabrik path like europe/great-britain")
        if region not in regions:
            regions.append(region)
    return regions


def region_url(region: str) -> str:
    return f"{GEOFABRIK}/{region}-latest.osm.pbf"


def region_path(data_dir: Path, region: str) -> Path:
    return data_dir / f"{region}-latest.osm.pbf"


def download(region: str, data_dir: Path, refresh: bool = False) -> Path:
    """Fetches a region's extract unless it is already there."""
    target = region_path(data_dir, region)
    if target.exists() and not refresh:
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".part")
    request = Request(region_url(region), headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=60) as response, partial.open("wb") as out:
        shutil.copyfileobj(response, out, 1 << 20)
    partial.replace(target)  # a half-finished download never looks complete
    return target
